from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cybersecurity-lab-tools")


@mcp.tool()
def summarize_security_headers(headers_text: str) -> dict:
    """Summarize HTTP security headers from provided text. Input should be raw HTTP response headers."""
    required = [
        "content-security-policy",
        "strict-transport-security",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
    ]
    lower = headers_text.lower()
    return {
        "present": [h for h in required if h in lower],
        "missing": [h for h in required if h not in lower],
        "summary": "Security header analysis complete.",
    }


@mcp.tool()
def format_pentest_finding(
    title: str,
    severity: str,
    issue_detail: str,
    impact: str,
    remediation: str,
) -> dict:
    """Format a report-ready pentest finding in markdown."""
    md = (
        f"## {title}\n\n"
        f"**Severity:** {severity}\n\n"
        f"### Issue\n{issue_detail}\n\n"
        f"### Impact\n{impact}\n\n"
        f"### Remediation\n{remediation}"
    )
    return {"status": "success", "finding_markdown": md}


@mcp.tool()
def parse_nmap_output(nmap_text: str) -> dict:
    """Parse text-format nmap output and summarize open ports and services."""
    lines = nmap_text.splitlines()
    open_ports = [l.strip() for l in lines if "/tcp" in l and "open" in l]
    hosts = [
        l.replace("Nmap scan report for", "").strip()
        for l in lines
        if l.startswith("Nmap scan report")
    ]
    return {"hosts": hosts, "open_ports": open_ports, "raw_line_count": len(lines)}


@mcp.tool()
def calculate_cvss_draft(
    attack_vector: str,
    complexity: str,
    privileges: str,
    user_interaction: str,
    confidentiality: str,
    integrity: str,
    availability: str,
) -> dict:
    """Estimate CVSSv3 base score from parameters. Returns rough score and vector string. For scoping only, not official scoring."""
    scores = {
        "none": 0.0,
        "low": 0.22,
        "high": 0.56,
        "network": 0.85,
        "adjacent": 0.62,
        "local": 0.55,
        "physical": 0.2,
        "required": 0.5,
        "changed": 0.0,
    }
    base = round(
        min(
            10.0,
            sum(
                scores.get(x.lower(), 0.3)
                for x in [
                    attack_vector,
                    complexity,
                    privileges,
                    user_interaction,
                    confidentiality,
                    integrity,
                    availability,
                ]
            ),
        ),
        1,
    )
    vector = (
        f"CVSS:3.1/AV:{attack_vector[0].upper()}"
        f"/AC:{complexity[0].upper()}"
        f"/PR:{privileges[0].upper()}"
        f"/UI:{user_interaction[0].upper()}"
        f"/S:U"
        f"/C:{confidentiality[0].upper()}"
        f"/I:{integrity[0].upper()}"
        f"/A:{availability[0].upper()}"
    )
    return {
        "estimated_base_score": base,
        "vector_string": vector,
        "note": "Draft estimate only — use official CVSS calculator for final scoring.",
    }


@mcp.tool()
def generate_test_plan(target_description: str, scope: str, test_type: str) -> dict:
    """Generate a basic penetration test plan structure for authorized engagements."""
    phases = [
        "Reconnaissance",
        "Enumeration",
        "Vulnerability Analysis",
        "Exploitation (authorized scope only)",
        "Post-Exploitation (authorized scope only)",
        "Reporting",
    ]
    return {
        "target": target_description,
        "scope": scope,
        "test_type": test_type,
        "phases": phases,
        "note": "Confirm written authorization before beginning. All activity must stay within agreed scope.",
    }


if __name__ == "__main__":
    mcp.run()
