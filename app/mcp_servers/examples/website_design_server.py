from mcp.server.fastmcp import FastMCP

mcp = FastMCP("website-design-tools")

_PALETTES = {
    "modern": ["#1a1a2e", "#16213e", "#0f3460", "#e94560"],
    "minimal": ["#ffffff", "#f5f5f5", "#333333", "#666666"],
    "vibrant": ["#ff6b6b", "#feca57", "#48dbfb", "#ff9ff3"],
    "corporate": ["#003366", "#0066cc", "#ffffff", "#f0f0f0"],
}

_FONTS = {
    "modern": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
    "minimal": {"heading": "Helvetica Neue", "body": "Georgia", "mono": "Courier New"},
    "corporate": {"heading": "Roboto", "body": "Open Sans", "mono": "Roboto Mono"},
    "creative": {"heading": "Playfair Display", "body": "Lato", "mono": "Fira Code"},
}

_SECTIONS = {
    "saas": ["Hero", "Features", "Pricing", "Testimonials", "FAQ", "CTA", "Footer"],
    "agency": ["Hero", "Services", "Portfolio", "About", "Team", "Contact", "Footer"],
    "ecommerce": ["Hero", "Featured Products", "Categories", "Promotions", "Reviews", "Footer"],
    "portfolio": ["Hero", "About", "Work", "Skills", "Testimonials", "Contact", "Footer"],
}


@mcp.tool()
def generate_color_palette(style: str) -> dict:
    """Generate a color palette for a given style (modern, minimal, vibrant, corporate)."""
    colors = _PALETTES.get(style.lower(), _PALETTES["modern"])
    return {
        "style": style,
        "colors": colors,
        "primary": colors[0],
        "secondary": colors[1],
        "accent": colors[-1],
    }


@mcp.tool()
def generate_landing_page_sections(industry: str, style: str) -> dict:
    """Generate recommended landing page sections for an industry and style."""
    sections = _SECTIONS.get(industry.lower(), _SECTIONS["saas"])
    return {
        "industry": industry,
        "style": style,
        "sections": sections,
        "total_sections": len(sections),
    }


@mcp.tool()
def generate_font_pairing(style: str) -> dict:
    """Generate a font pairing recommendation for a given style."""
    fonts = _FONTS.get(style.lower(), _FONTS["modern"])
    return {"style": style, **fonts}


if __name__ == "__main__":
    mcp.run()
