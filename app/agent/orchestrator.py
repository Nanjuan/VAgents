import json
import logging
from sqlmodel import Session

from app.agent.context import AgentContext
from app.agent.memory import AgentMemory
from app.agent.prompts import build_system_prompt
from app.agent.profile_manager import ProfileManager
from app.llm.router import ModelRouter
from app.security.approvals import ApprovalManager
from app.security.audit_service import record_tool_run
from app.tools.gateway import ToolGateway
from app.tools.schemas import ToolDefinition

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 10


def _tool_defs_to_llm_format(tools: list[ToolDefinition]) -> list[dict]:
    return [
        {
            "name": t.tool_id.replace(":", "_").replace(".", "_"),
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


class AgentOrchestrator:
    def __init__(
        self,
        model_router: ModelRouter,
        tool_gateway: ToolGateway,
        profile_manager: ProfileManager,
        memory: AgentMemory,
    ) -> None:
        self._router = model_router
        self._gateway = tool_gateway
        self._profiles = profile_manager
        self._memory = memory

    async def run_turn(
        self,
        context: AgentContext,
        user_message: str,
        session: Session,
    ) -> dict:
        profile = self._profiles.get_profile(context.profile_name)
        if not profile:
            return {
                "content": f"Profile '{context.profile_name}' not found.",
                "tool_calls_made": [],
                "requires_approval": [],
            }

        # Load history; append user message unless resuming after MCP approvals
        history = self._memory.load_history(context.project_id, session)
        if not context.continuation:
            self._memory.save_message(context.project_id, "user", user_message, session)
            history.append({"role": "user", "content": user_message})
        elif context.continuation:
            pend = ApprovalManager().get_pending(context.project_id, session)
            if pend:
                # Still waiting on other tool approvals — do not call the LLM with an incomplete tool round
                return {
                    "content": "",
                    "tool_calls_made": [],
                    "requires_approval": [
                        {
                            "tool_id": r.tool_id
                            or (
                                f"mcp:{r.server_name}.{r.tool_name}"
                                if r.server_name
                                else f"native:{r.tool_name}"
                            ),
                            "approval_id": r.id,
                            "arguments": json.loads(r.arguments_json) if r.arguments_json else {},
                        }
                        for r in pend
                    ],
                    "continuation_needed": True,
                }

        system_prompt = build_system_prompt(profile)
        tool_defs = await self._gateway.list_tools(context.profile_name)
        llm_tools = _tool_defs_to_llm_format(tool_defs) if tool_defs else None

        # Build tool id lookup by LLM name
        tool_id_map = {
            t.tool_id.replace(":", "_").replace(".", "_"): t.tool_id for t in tool_defs
        }

        messages = [{"role": "system", "content": system_prompt}] + history

        tool_calls_made: list[dict] = []
        requires_approval: list[dict] = []

        using_lmstudio = bool(context.lmstudio_model_id)
        if using_lmstudio:
            from app.config.settings import get_settings
            lmstudio_base_url = get_settings().lm_studio_base_url
            provider_type = "openai_compatible"
            native_tools_supported = True  # LM Studio models support OpenAI tool calling
        else:
            provider_type = self._router.get_provider_type(context.model_key)
            native_tools_supported = self._router.model_supports_tools(context.model_key)

        async def _call_model(msgs, tool_list):
            if using_lmstudio:
                mk_cfg = self._router.get_model_config(context.model_key)
                temp = float(mk_cfg.get("temperature", 0.7))
                return await self._router.route_dynamic(
                    lmstudio_base_url,
                    context.lmstudio_model_id,
                    msgs,
                    tool_list,
                    max_tokens=context.max_tokens,
                    temperature=temp,
                )
            return await self._router.route(
                context.model_key,
                msgs,
                tool_list,
                max_tokens_override=context.max_tokens,
            )

        def _push_tool_msg(call_id: str, tool_result_content: str) -> None:
            if provider_type == "anthropic":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call_id,
                                "content": tool_result_content,
                            }
                        ],
                    }
                )
            else:
                messages.append(
                    {"role": "tool", "content": tool_result_content, "tool_call_id": call_id}
                )

        for _iteration in range(_MAX_TOOL_ITERATIONS):
            response = await _call_model(messages, llm_tools)
            content = response.get("content", "")
            raw_tool_calls = response.get("tool_calls")

            # Fall back to JSON block detection only for text-only models (no native tool calling)
            if raw_tool_calls is None and not native_tools_supported:
                raw_tool_calls = _parse_json_tool_calls(content)

            if not raw_tool_calls:
                # Final answer
                self._memory.save_message(context.project_id, "assistant", content, session)
                return {
                    "content": content,
                    "tool_calls_made": tool_calls_made,
                    "requires_approval": requires_approval,
                }

            # Persist assistant turn that requested tools (reload + approvals need this)
            self._memory.save_message(
                context.project_id,
                "assistant",
                content or "",
                session,
                tool_calls=raw_tool_calls,
            )

            oa_tool_calls = []
            for tc in raw_tool_calls:
                oa_tool_calls.append(
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments", {}))
                            if isinstance(tc.get("arguments"), dict)
                            else str(tc.get("arguments", "")),
                        },
                    }
                )
            messages.append(
                {
                    "role": "assistant",
                    "content": content if content else None,
                    "tool_calls": oa_tool_calls,
                }
            )

            # Phase 1: gate every tool call (creates approval rows when needed)
            gates: list[dict] = []
            for tc in raw_tool_calls:
                llm_tool_name = tc["name"]
                tool_id = tool_id_map.get(llm_tool_name, llm_tool_name)
                arguments = tc.get("arguments", {})
                call_id = tc.get("id", "")
                gate_result = await self._gateway.request_tool_call(
                    context.profile_name,
                    tool_id,
                    arguments,
                    reason="agent tool call",
                    session=session,
                    project_id=context.project_id,
                    tool_call_id=call_id or None,
                )
                gates.append(
                    {
                        "tc": tc,
                        "tool_id": tool_id,
                        "arguments": arguments,
                        "call_id": call_id,
                        "gate": gate_result,
                    }
                )

            batch_requires: list[dict] = []
            seen_appr: set[str] = set()
            for item in gates:
                if item["gate"].get("status") == "pending_approval":
                    aid = item["gate"]["approval_id"]
                    if aid not in seen_appr:
                        seen_appr.add(aid)
                        batch_requires.append(
                            {
                                "tool_id": item["tool_id"],
                                "approval_id": aid,
                                "arguments": item["arguments"],
                            }
                        )

            if batch_requires:
                # Do not execute any tool in this assistant turn until approvals resolve.
                # (Partial tool outputs break OpenAI-style tool_call / tool message pairing.)
                return {
                    "content": "",
                    "tool_calls_made": tool_calls_made,
                    "requires_approval": batch_requires,
                    "continuation_needed": True,
                }

            # No approvals required — execute every tool call in order
            for item in gates:
                tool_id = item["tool_id"]
                arguments = item["arguments"]
                call_id = item["call_id"]
                gr = item["gate"]
                if gr.get("status") == "error":
                    err_txt = json.dumps({"error": gr.get("error", "unknown")})
                    self._memory.save_message(
                        context.project_id,
                        "tool",
                        err_txt,
                        session,
                        tool_name=tool_id,
                        tool_args=arguments,
                        tool_call_id=call_id or None,
                    )
                    _push_tool_msg(call_id, err_txt)
                    continue
                exec_result = await self._gateway.execute_tool_call(
                    None, context.profile_name, tool_id, arguments
                )
                try:
                    record_tool_run(
                        session,
                        context.project_id,
                        context.profile_name,
                        tool_id,
                        arguments,
                        exec_result,
                        approved_by_user=False,
                    )
                except Exception:
                    logger.exception("record_tool_run failed")
                tool_result_content = json.dumps(
                    {"result": exec_result.result, "error": exec_result.error}
                )
                tool_calls_made.append(
                    {
                        "tool_id": tool_id,
                        "arguments": arguments,
                        "status": exec_result.status,
                        "duration_ms": exec_result.duration_ms,
                    }
                )
                self._memory.save_message(
                    context.project_id,
                    "tool",
                    tool_result_content,
                    session,
                    tool_name=tool_id,
                    tool_args=arguments,
                    tool_call_id=call_id or None,
                )
                _push_tool_msg(call_id, tool_result_content)

        # Exceeded iteration limit — ask model for final answer without tools
        final_response = await _call_model(messages, None)
        final_content = final_response.get("content", "")
        self._memory.save_message(context.project_id, "assistant", final_content, session)
        return {
            "content": final_content,
            "tool_calls_made": tool_calls_made,
            "requires_approval": requires_approval,
        }


def _parse_json_tool_calls(content: str) -> list[dict] | None:
    """Attempt to extract JSON tool call from model output for text-only providers."""
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(1))
        if "tool" in obj and "arguments" in obj:
            return [{"name": obj["tool"], "arguments": obj["arguments"], "id": "text-0"}]
    except (json.JSONDecodeError, KeyError):
        pass
    return None
