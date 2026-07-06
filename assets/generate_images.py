"""Generate architecture diagram and cover banner for Incident Commander."""

import math
import os

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_font(size, bold=True):
    path = FONT_PATH if bold else FONT_REG_PATH
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_hexagon(draw, cx, cy, r, outline, width=2):
    pts = []
    for i in range(6):
        angle = 2 * math.pi * i / 6 - math.pi / 2
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(pts, fill=None, outline=outline, width=width)


def generate_architecture_diagram():
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#0a0e1a")
    draw = ImageDraw.Draw(img)

    font_title = get_font(32)
    font_node = get_font(18)
    font_small = get_font(14, bold=False)
    font_tiny = get_font(13, bold=False)

    draw.text((60, 30), "Incident Commander \u2014 Agent Workflow", fill="#00ff88", font=font_title)

    nodes = [
        ("START", 60, 200, 120, 50, "#1a1a2e", "#00ff88"),
        ("Security\nCheckpoint", 60, 320, 180, 80, "#1a1a2e", "#ff6600"),
        ("Orchestrator", 60, 480, 180, 70, "#1a1a2e", "#00ccff"),
        ("Triage\nAgent", 340, 200, 180, 80, "#1a1a2e", "#aa66ff"),
        ("Diagnosis\nAgent", 340, 360, 180, 80, "#1a1a2e", "#aa66ff"),
        ("Human\nApproval", 340, 520, 180, 80, "#1a1a2e", "#4488ff"),
        ("Documentation\nAgent", 640, 200, 200, 80, "#1a1a2e", "#aa66ff"),
        ("Final\nOutput", 640, 400, 180, 80, "#1a1a2e", "#00ff88"),
        ("Security\nViolation", 340, 640, 180, 80, "#1a1a2e", "#ff4444"),
    ]

    for name, x, y, w, h, bg, border in nodes:
        draw_rounded_rect(draw, (x, y, x + w, y + h), 12, fill=bg, outline=border, width=2)
        lines = name.split("\n")
        line_h = 22
        total_h = len(lines) * line_h
        start_y = y + (h - total_h) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_node)
            tw = bbox[2] - bbox[0]
            draw.text((x + (w - tw) // 2, start_y + i * line_h), line, fill="#ffffff", font=font_node)

    roles = {
        "Security\nCheckpoint": "PII scrub + injection detect",
        "Orchestrator": "Route to triage",
        "Triage\nAgent": "Classify severity",
        "Diagnosis\nAgent": "Root cause analysis",
        "Human\nApproval": "Approve / Deny",
        "Documentation\nAgent": "Incident report",
        "Final\nOutput": "Compile results",
        "Security\nViolation": "Block incident",
    }
    for name, x, y, w, h, bg, border in nodes:
        if name in roles:
            role = roles[name]
            bbox = draw.textbbox((0, 0), role, font=font_small)
            tw = bbox[2] - bbox[0]
            draw.text((x + (w - tw) // 2, y + h + 5), role, fill="#8899aa", font=font_small)

    def arrow(x1, y1, x2, y2, color="#445566", label=""):
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        if label:
            bbox = draw.textbbox((0, 0), label, font=font_small)
            tw = bbox[2] - bbox[0]
            draw.text((mx - tw // 2, my - 18), label, fill="#ffcc00", font=font_small)

    arrow(120, 225, 240, 330, "#445566")
    arrow(150, 400, 150, 480, "#445566")
    arrow(240, 400, 340, 550, "#ff4444", "SECURITY_EVENT")
    arrow(210, 515, 340, 240, "#445566")
    arrow(430, 280, 430, 360, "#445566")
    arrow(430, 440, 430, 520, "#445566")
    arrow(520, 540, 640, 240, "#00ff88", "APPROVED")
    arrow(520, 580, 640, 440, "#ff4444", "DENIED")
    arrow(740, 280, 730, 400, "#445566")

    mx, my, mw, mh = 900, 200, 320, 700
    draw_rounded_rect(draw, (mx, my, mx + mw, my + mh), 16, fill="#0d1520", outline="#00ff88", width=2)
    draw.text((mx + 20, my + 15), "MCP Server", fill="#00ff88", font=font_node)

    mcp_tools = [
        "get_service_health",
        "search_runbooks",
        "create_incident_ticket",
        "get_recent_deployments",
        "escalate_to_team",
    ]
    for i, tool in enumerate(mcp_tools):
        ty = my + 60 + i * 45
        draw_rounded_rect(draw, (mx + 15, ty, mx + mw - 15, ty + 35), 8, fill="#1a2740", outline="#00ccff", width=1)
        draw.text((mx + 25, ty + 7), tool, fill="#bbddff", font=get_font(15, bold=False))

    draw.line([(900, 250), (840, 250)], fill="#00ff88", width=1)
    draw.line([(900, 300), (840, 400)], fill="#00ff88", width=1)
    draw.line([(900, 350), (840, 420)], fill="#00ff88", width=1)

    draw.text((mx + 15, my + mh - 30), "Used by: Triage, Diagnosis, Documentation", fill="#667788", font=get_font(13, bold=False))

    img.save(os.path.join(OUT_DIR, "architecture_diagram.png"))
    print("Saved architecture_diagram.png")


def generate_cover_banner():
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#0a0e1a")
    draw = ImageDraw.Draw(img)

    font_title = get_font(72)
    font_sub = get_font(28)
    font_feat = get_font(18, bold=False)

    draw.text((80, 180), "INCIDENT", fill="#00ff88", font=font_title)
    draw.text((80, 260), "COMMANDER", fill="#ffffff", font=font_title)
    draw.text((80, 360), "Automated  |  Secure  |  Intelligent", fill="#8899aa", font=font_sub)

    features = ["Multi-Agent AI", "MCP-Powered", "Human Oversight"]
    for i, feat in enumerate(features):
        fx, fy = 80, 600 + i * 55
        draw_rounded_rect(draw, (fx, fy, fx + 220, fy + 45), 10, fill="#1a2740", outline="#00ccff", width=1)
        draw.text((fx + 15, fy + 10), feat, fill="#bbddff", font=font_feat)

    shapes = [
        (1400, 200, 200, 200),
        (1600, 400, 150, 150),
        (1300, 600, 180, 180),
        (1550, 150, 100, 100),
    ]
    for sx, sy, sw, sh in shapes[:2]:
        draw.ellipse((sx, sy, sx + sw, sy + sh), fill=None, outline="#00ff88", width=2)
    for sx, sy, sw, sh in shapes[2:]:
        draw_hexagon(draw, sx + sw // 2, sy + sh // 2, sw // 2, outline="#aa66ff", width=2)

    for i in range(10):
        lx = 1200 + i * 60
        ly = 100 + (i % 5) * 40
        draw.line([(lx, ly), (lx + 30, ly + 80)], fill="#1a2740", width=1)

    draw.text((80, H - 80), "Powered by Google ADK", fill="#445566", font=get_font(20, bold=False))

    img.save(os.path.join(OUT_DIR, "cover_page_banner.png"))
    print("Saved cover_page_banner.png")


if __name__ == "__main__":
    generate_architecture_diagram()
    generate_cover_banner()
