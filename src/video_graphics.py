from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True, slots=True)
class CaptionSegment:
    start: float
    end: float
    text: str
    png_path: Path


def _parse_srt_time(line: str) -> tuple[float, float] | None:
    m = re.match(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})",
        line.strip(),
    )
    if not m:
        return None

    def to_sec(h: str, m_: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m_) * 60 + int(s) + int(ms) / 1000.0

    t0 = to_sec(m.group(1), m.group(2), m.group(3), m.group(4))
    t1 = to_sec(m.group(5), m.group(6), m.group(7), m.group(8))
    return t0, t1


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    raw = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[float, float, str]] = []
    i = 0
    while i < len(raw):
        line = raw[i].strip()
        if line.isdigit():
            i += 1
            if i >= len(raw):
                break
            times = _parse_srt_time(raw[i])
            i += 1
            if times is None:
                continue
            t0, t1 = times
            text_lines: list[str] = []
            while i < len(raw) and raw[i].strip() != "":
                text_lines.append(raw[i].strip())
                i += 1
            text = " ".join(text_lines).strip()
            if text:
                out.append((t0, t1, text))
        i += 1
    return out


def merge_segments(segments: list[tuple[float, float, str]], max_segments: int) -> list[tuple[float, float, str]]:
    segs = list(segments)
    while len(segs) > max_segments:
        merged: list[tuple[float, float, str]] = []
        j = 0
        while j < len(segs):
            if j + 1 < len(segs):
                a0, _a1, at = segs[j]
                _b0, b1, bt = segs[j + 1]
                merged.append((a0, b1, f"{at} {bt}".strip()))
                j += 2
            else:
                merged.append(segs[j])
                j += 1
        segs = merged
    return segs


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/NotoSansDevanagari.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def render_caption_png(text: str, out_path: Path, *, max_width: int = 1120) -> None:
    font = _pick_font(44)
    lines = wrap_text(text, font, max_width=max_width)
    line_height = int(font.getbbox("Ay")[3] - font.getbbox("Ay")[1]) + 12
    height = max(130, min(260, 28 + line_height * len(lines)))
    width = 1200
    # High-contrast bar for readability on bright backgrounds and after 720p downscale.
    img = Image.new("RGBA", (width, height), (0, 0, 0, 252))
    draw = ImageDraw.Draw(img)
    y = 18
    for ln in lines:
        draw.text(
            (22, y),
            ln,
            fill=(255, 255, 230, 255),
            font=font,
            stroke_width=4,
            stroke_fill=(0, 0, 0, 255),
        )
        y += line_height
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def render_anchor_card(out_path: Path, *, headline: str) -> None:
    """Stylized on-screen anchor card (not a licensed photo). Replace with REPORTER_IMAGE_PATH for a real face."""
    w, h = 920, 1180
    img = Image.new("RGBA", (w, h), (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)

    # India-inspired accent bands (simplified; not the official flag geometry)
    draw.rectangle((0, 0, w, 26), fill=(250, 204, 21, 255))
    draw.rectangle((0, 26, w, 52), fill=(248, 250, 252, 255))
    draw.rectangle((0, 52, w, 78), fill=(5, 150, 105, 255))

    # Soft panel
    draw.rounded_rectangle((40, 110, w - 40, h - 40), radius=36, fill=(30, 41, 59, 255))

    # "Avatar" circle (generic)
    cx, cy, r = w // 2, 430, 220
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(253, 224, 200, 255), outline=(248, 250, 252, 220), width=6)
    draw.arc((cx - r - 10, cy - r - 30, cx + r + 10, cy - r + 40), start=200, end=340, fill=(30, 27, 24, 255), width=26)

    title_font = _pick_font(40)
    sub_font = _pick_font(28)
    draw.text((60, 820), "AI News Anchor", fill=(226, 232, 240, 255), font=title_font)
    draw.text((60, 880), "India desk (auto visuals)", fill=(148, 163, 184, 255), font=sub_font)

    hf = _pick_font(30)
    hl = wrap_text(headline[:140], hf, max_width=w - 120)
    y = 940
    for ln in hl[:2]:
        draw.text((60, y), ln, fill=(248, 250, 252, 255), font=hf)
        y += 40

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def build_caption_assets(
    *,
    srt_path: Path,
    work_dir: Path,
    max_segments: int = 22,
) -> list[CaptionSegment]:
    work_dir.mkdir(parents=True, exist_ok=True)
    segs = merge_segments(parse_srt(srt_path), max_segments=max_segments)
    out: list[CaptionSegment] = []
    for idx, (t0, t1, text) in enumerate(segs, start=1):
        png = work_dir / f"caption-{idx:03d}.png"
        render_caption_png(text, png)
        out.append(CaptionSegment(start=t0, end=t1, text=text, png_path=png))
    return out
