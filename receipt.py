"""
Session receipt generator for TurboSkillSlug.

Generates a thermal-receipt-style SVG from the same extraction
features dict the shell uses. Narrow, monospace, printable.

The receipt is the practical artifact. The shell is the emotional one.
Together they give the builder two reasons to come back.
"""

import hashlib
from typing import Any


def _esc(text: str) -> str:
    """Escape XML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _truncate(text: str, max_len: int = 32) -> str:
    """Truncate text to fit receipt width."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 2] + ".."


def _barcode_pattern(seed: str, width: int = 260, height: int = 30) -> str:
    """Generate a decorative barcode SVG pattern from a hash seed."""
    h = hashlib.md5(seed.encode()).hexdigest()
    bars = []
    x = 0
    for i, char in enumerate(h):
        val = int(char, 16)
        bar_w = 2 + (val % 3)
        if i % 2 == 0:
            bars.append(
                f'<rect x="{x}" y="0" width="{bar_w}" height="{height}" '
                f'fill="#2a2a2a" opacity="{0.7 + (val % 3) * 0.1:.1f}"/>'
            )
        x += bar_w + 1
        if x > width:
            break
    scale = width / max(x, 1)
    return (
        f'<g transform="scale({scale:.3f}, 1)">'
        + "".join(bars)
        + "</g>"
    )


def generate_receipt_svg(features: dict[str, Any]) -> str:
    """Generate a thermal-receipt-style SVG from session features."""
    duration = features.get("duration_minutes", 0)
    themes = features.get("themes", []) or []
    approaches = features.get("approaches_tried", []) or []
    dead_ends = features.get("dead_ends", []) or []
    breakthroughs = features.get("breakthroughs", []) or []
    gotchas = features.get("gotchas", []) or []
    sentiment = features.get("sentiment_arc", {}) or {}
    slug_voice = features.get("slug_voice", []) or []

    start_mood = sentiment.get("start", "unknown")
    end_mood = sentiment.get("end", "unknown")

    W = 320
    MARGIN = 20
    LINE_H = 18
    SECTION_GAP = 12
    FONT = "Courier New, Courier, monospace"
    TEXT_COLOR = "#2a2a2a"
    BG_COLOR = "#f7f2e8"
    FAINT = "#8a8578"
    ACCENT = "#5a4e3a"

    lines = []  # (y_offset, content_type, data)
    y = MARGIN

    def add_line(text: str, bold: bool = False, color: str = TEXT_COLOR,
                 size: int = 12, align: str = "middle"):
        nonlocal y
        lines.append((y, "text", text, bold, color, size, align))
        y += LINE_H

    def add_gap(height: int = SECTION_GAP):
        nonlocal y
        y += height

    def add_dashes():
        nonlocal y
        lines.append((y, "dashes", None, False, FAINT, 0, ""))
        y += 10

    def add_dotted_row(left: str, right: str):
        nonlocal y
        lines.append((y, "dotrow", (left, right), False, TEXT_COLOR, 12, ""))
        y += LINE_H

    # === HEADER ===
    add_gap(5)
    add_line("TURBOSKILLSLUG", bold=True, size=14, color=ACCENT)
    add_line("session receipt", size=10, color=FAINT)
    add_gap(4)
    add_dashes()

    # === SESSION INFO ===
    add_gap(2)
    if themes:
        session_name = _truncate(", ".join(themes), 34)
        add_line(session_name, size=11, color=TEXT_COLOR)
    add_gap(2)

    # Duration
    if duration >= 1:
        dur_str = f"{int(duration)} min"
    else:
        dur_str = f"{int(duration * 60)} sec"
    add_dotted_row("DURATION", dur_str)
    add_dotted_row("MOOD IN", start_mood)
    add_dotted_row("MOOD OUT", end_mood)
    add_dashes()

    # === APPROACHES ===
    add_gap(2)
    add_line("APPROACHES", bold=True, size=11, color=ACCENT, align="start")
    add_gap(2)
    for i, approach in enumerate(approaches, 1):
        name = approach.get("approach", "unknown")
        failed = approach.get("why_it_failed", "")
        status = "FAIL" if failed else "OK"
        add_dotted_row(f"  {_truncate(name, 24)}", status)
    if not approaches:
        add_line("  (none recorded)", size=10, color=FAINT, align="start")
    add_dashes()

    # === DEAD ENDS ===
    add_gap(2)
    n_dead = len(dead_ends)
    n_gotchas = len(gotchas)
    n_breakthroughs = len(breakthroughs)
    add_dotted_row("DEAD ENDS", f"x{n_dead}")
    add_dotted_row("GOTCHAS", f"x{n_gotchas}")
    add_dotted_row("BREAKTHROUGHS", f"x{n_breakthroughs}")
    add_dashes()

    # === GOTCHA DETAILS ===
    if gotchas:
        add_gap(2)
        add_line("WATCH OUT FOR", bold=True, size=11, color=ACCENT, align="start")
        add_gap(2)
        for gotcha in gotchas[:5]:
            add_line(f"  ! {_truncate(str(gotcha), 30)}", size=10,
                     color=TEXT_COLOR, align="start")
        add_dashes()

    # === BREAKTHROUGH ===
    if breakthroughs:
        add_gap(2)
        add_line("BREAKTHROUGH", bold=True, size=11, color=ACCENT, align="start")
        add_gap(2)
        for bt in breakthroughs[:2]:
            what = bt.get("what_worked", "")
            pos = bt.get("position", 0)
            add_line(f"  @ {int(pos * 100)}%: {_truncate(what, 26)}",
                     size=10, color=TEXT_COLOR, align="start")
        add_dashes()

    # === TOTAL ===
    add_gap(4)
    add_dotted_row("TOTAL TIME", dur_str)
    add_dotted_row("TOTAL APPROACHES", str(len(approaches)))
    add_dotted_row("TOTAL STUMBLES", str(n_dead))
    add_gap(4)
    add_dashes()

    # === BARCODE ===
    add_gap(8)
    barcode_seed = f"{duration}-{n_dead}-{start_mood}-{end_mood}-{len(approaches)}"
    barcode_y = y
    y += 35

    # === FOOTER ===
    add_gap(6)
    add_line("the slug was here.", size=10, color=FAINT)
    add_gap(4)
    add_line("keep this receipt.", size=9, color=FAINT)
    add_gap(MARGIN)

    H = y

    # === BUILD SVG ===
    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
    )

    # Receipt paper background with slight texture
    svg.append(f'<rect width="{W}" height="{H}" fill="{BG_COLOR}" rx="2"/>')
    # Torn top edge
    svg.append(
        f'<path d="M0,4 '
        + " ".join(f"L{x},{2 + (x * 7 % 5)}" for x in range(0, W + 10, 8))
        + f' L{W},0 L0,0 Z" fill="{BG_COLOR}"/>'
    )

    # Render lines
    cx = W // 2
    lx = MARGIN
    rx = W - MARGIN

    for item in lines:
        if item[1] == "text":
            y_pos, _, text, bold, color, size, align = item
            weight = "bold" if bold else "normal"
            if align == "start":
                anchor = "start"
                x_pos = lx
            elif align == "end":
                anchor = "end"
                x_pos = rx
            else:
                anchor = "middle"
                x_pos = cx
            svg.append(
                f'<text x="{x_pos}" y="{y_pos}" text-anchor="{anchor}" '
                f'font-family="{FONT}" font-size="{size}" '
                f'font-weight="{weight}" fill="{color}">'
                f'{_esc(text)}</text>'
            )
        elif item[1] == "dashes":
            y_pos = item[0]
            svg.append(
                f'<line x1="{lx}" y1="{y_pos}" x2="{rx}" y2="{y_pos}" '
                f'stroke="{FAINT}" stroke-width="0.8" '
                f'stroke-dasharray="4,3"/>'
            )
        elif item[1] == "dotrow":
            y_pos = item[0]
            left, right = item[2]
            # Left text
            svg.append(
                f'<text x="{lx}" y="{y_pos}" text-anchor="start" '
                f'font-family="{FONT}" font-size="11" fill="{TEXT_COLOR}">'
                f'{_esc(left)}</text>'
            )
            # Right text
            svg.append(
                f'<text x="{rx}" y="{y_pos}" text-anchor="end" '
                f'font-family="{FONT}" font-size="11" fill="{TEXT_COLOR}">'
                f'{_esc(right)}</text>'
            )
            # Dots in between
            dot_start = lx + len(left) * 6.5 + 8
            dot_end = rx - len(right) * 6.5 - 8
            if dot_end > dot_start + 10:
                svg.append(
                    f'<line x1="{dot_start}" y1="{y_pos - 3}" '
                    f'x2="{dot_end}" y2="{y_pos - 3}" '
                    f'stroke="{FAINT}" stroke-width="0.5" '
                    f'stroke-dasharray="1.5,3"/>'
                )

    # Barcode
    svg.append(
        f'<g transform="translate({lx}, {barcode_y})">'
        f'{_barcode_pattern(barcode_seed, width=rx - lx, height=28)}'
        f'</g>'
    )

    # Torn bottom edge
    svg.append(
        f'<path d="M0,{H - 4} '
        + " ".join(
            f"L{x},{H - 2 - (x * 11 % 5)}"
            for x in range(0, W + 10, 8)
        )
        + f' L{W},{H} L0,{H} Z" fill="white"/>'
    )

    svg.append("</svg>")
    return "\n".join(svg)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path

    sample = {
        "duration_minutes": 1.6,
        "themes": ["WebSocket", "Real-time updates", "Debugging"],
        "approaches_tried": [
            {"approach": "ws basic example", "why_it_failed": "Connection refused"},
            {"approach": "npm install ws", "why_it_failed": "Still refused"},
            {"approach": "socket.io", "why_it_failed": ""},
        ],
        "dead_ends": [
            {"position": 0.25, "what_happened": "Connection refused"},
            {"position": 0.5, "what_happened": "Native module failed"},
            {"position": 0.75, "what_happened": "Emit did nothing"},
        ],
        "breakthroughs": [
            {"position": 0.95, "what_worked": "Event name string mismatch fixed"},
        ],
        "gotchas": [
            "Always grep event names across client and server",
        ],
        "sentiment_arc": {"start": "frustrated", "end": "joyful"},
        "slug_voice": [
            "You tried three different libraries before the strings matched.",
        ],
    }

    Path("sample_receipt.svg").write_text(generate_receipt_svg(sample))
    print("wrote sample_receipt.svg")
