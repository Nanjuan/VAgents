import socket
import ssl
import xml.etree.ElementTree as ET
from pathlib import Path
import httpx


WORKSPACE_ROOT = Path("./workspace").resolve()


class NativeToolRunner:
    async def run(self, tool_name: str, arguments: dict) -> dict:
        handlers = {
            "http_get_headers": self._http_get_headers,
            "dns_lookup": self._dns_lookup,
            "check_ssl_cert": self._check_ssl_cert,
            "parse_nmap_xml": self._parse_nmap_xml,
            "list_workspace_files": self._list_workspace_files,
            "read_workspace_file": self._read_workspace_file,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"status": "error", "result": None, "error": f"Unknown tool: {tool_name}"}
        try:
            return await handler(**arguments)
        except Exception as e:
            return {"status": "error", "result": None, "error": str(e)}

    async def _http_get_headers(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.head(url)
        return {
            "status": "success",
            "result": {"status_code": response.status_code, "headers": dict(response.headers)},
            "error": None,
        }

    async def _dns_lookup(self, hostname: str) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: socket.getaddrinfo(hostname, None))
        addresses = list({entry[4][0] for entry in info})
        return {"status": "success", "result": {"hostname": hostname, "addresses": addresses}, "error": None}

    async def _check_ssl_cert(self, hostname: str, port: int = 443) -> dict:
        import asyncio
        import datetime

        def _get_cert() -> dict:
            cert_pem = ssl.get_server_certificate((hostname, port))
            ctx = ssl.create_default_context()
            conn = ctx.wrap_socket(
                socket.create_connection((hostname, port), timeout=10),
                server_hostname=hostname,
            )
            cert_info = conn.getpeercert()
            conn.close()
            return cert_info

        loop = asyncio.get_event_loop()
        cert = await loop.run_in_executor(None, _get_cert)

        not_before = cert.get("notBefore", "")
        not_after = cert.get("notAfter", "")
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))

        return {
            "status": "success",
            "result": {
                "hostname": hostname,
                "subject": subject,
                "issuer": issuer,
                "not_before": not_before,
                "not_after": not_after,
            },
            "error": None,
        }

    async def _parse_nmap_xml(self, xml_content: str) -> dict:
        root = ET.fromstring(xml_content)
        hosts = []
        for host in root.findall("host"):
            addr_el = host.find("address")
            addr = addr_el.get("addr", "unknown") if addr_el is not None else "unknown"
            ports_data = []
            ports_el = host.find("ports")
            if ports_el is not None:
                for port_el in ports_el.findall("port"):
                    state_el = port_el.find("state")
                    service_el = port_el.find("service")
                    if state_el is not None and state_el.get("state") == "open":
                        ports_data.append(
                            {
                                "port": port_el.get("portid"),
                                "protocol": port_el.get("protocol"),
                                "service": service_el.get("name", "") if service_el is not None else "",
                            }
                        )
            hosts.append({"address": addr, "open_ports": ports_data})

        return {"status": "success", "result": {"hosts": hosts, "host_count": len(hosts)}, "error": None}

    async def _list_workspace_files(self) -> dict:
        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
        files = [str(p.relative_to(WORKSPACE_ROOT)) for p in WORKSPACE_ROOT.rglob("*") if p.is_file()]
        return {"status": "success", "result": {"files": files, "count": len(files)}, "error": None}

    async def _read_workspace_file(self, relative_path: str) -> dict:
        safe = (WORKSPACE_ROOT / relative_path).resolve()
        if not str(safe).startswith(str(WORKSPACE_ROOT)):
            return {"status": "error", "result": None, "error": "Path traversal blocked"}
        if not safe.exists():
            return {"status": "error", "result": None, "error": "File not found"}
        if safe.stat().st_size > 1_048_576:
            return {"status": "error", "result": None, "error": "File exceeds 1MB limit"}
        content = safe.read_text(errors="replace")
        return {"status": "success", "result": {"content": content, "path": relative_path}, "error": None}
