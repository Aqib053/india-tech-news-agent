from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import edge_tts

# Microsoft Edge neural voices (India). Tried in order until one succeeds.
_INDIAN_EDGE_VOICES = (
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "hi-IN-MadhurNeural",
    "hi-IN-SwaraNeural",
)


async def _render(text: str, voice: str, out_file: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(out_file))


def synthesize_voiceover(text: str, voice: str, out_file: Path) -> Path:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    candidates: list[str] = []
    v = (voice or "").strip()
    if v:
        candidates.append(v)
    for alt in _INDIAN_EDGE_VOICES:
        if alt not in candidates:
            candidates.append(alt)

    for vtry in candidates[:5]:
        try:
            asyncio.run(_render(text=text, voice=vtry, out_file=out_file))
            return out_file
        except Exception:
            continue

    preferred = (os.getenv("MACOS_SAY_VOICE") or "Veena").strip()
    _fallback_macos_say(text=text, out_file=out_file, preferred_voice=preferred)
    return out_file


def _fallback_macos_say(text: str, out_file: Path, *, preferred_voice: str = "") -> None:
    # Keep chunks moderate so `say` handles long scripts reliably.
    safe_text = " ".join(text.split())[:50000]
    with tempfile.TemporaryDirectory() as tmp_dir:
        aiff_file = Path(tmp_dir) / "voiceover.aiff"
        if preferred_voice:
            r = subprocess.run(
                ["say", "-v", preferred_voice, "-o", str(aiff_file), safe_text],
                check=False,
            )
            if r.returncode != 0:
                subprocess.run(["say", "-o", str(aiff_file), safe_text], check=True)
        else:
            subprocess.run(["say", "-o", str(aiff_file), safe_text], check=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(aiff_file),
                "-ac",
                "1",
                "-ar",
                "44100",
                "-b:a",
                "192k",
                str(out_file),
            ],
            check=True,
        )
