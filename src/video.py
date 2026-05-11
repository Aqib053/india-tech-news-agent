from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from src.video_graphics import build_caption_assets, render_anchor_card


def _path_or_none(p: str | None) -> Path | None:
    s = (p or "").strip()
    if not s:
        return None
    return Path(s).expanduser()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ffprobe_audio_duration_seconds(path: Path) -> float | None:
    """Duration of media file in seconds (uses container duration; good for our voiceover mp3)."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        d = float(proc.stdout.strip())
        return d if d > 0.2 else None
    except Exception:
        return None


def _srt_timestamp(t: float) -> str:
    t = max(0.0, t)
    total_ms = int(round(t * 1000))
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _pack_cues(phrases: list[str], *, max_chars: int) -> list[str]:
    cues: list[str] = []
    for phrase in phrases:
        words = phrase.split()
        cur: list[str] = []
        for w in words:
            trial = " ".join(cur + [w])
            if len(trial) <= max_chars:
                cur.append(w)
            else:
                if cur:
                    cues.append(" ".join(cur))
                cur = [w]
        if cur:
            cues.append(" ".join(cur))
    return cues if cues else ["."]


def _split_into_display_cues(text: str, *, max_chars: int = 96) -> list[str]:
    t = " ".join(text.split())
    if not t:
        return ["."]
    bits = re.split(r"(?<=[.!?।])\s+", t)
    bits = [b.strip() for b in bits if b.strip()]
    if not bits:
        bits = [t]
    return _pack_cues(bits, max_chars=max_chars)


def _cue_time_ranges(cues: list[str], total: float) -> list[tuple[float, float, str]]:
    n = len(cues)
    if n == 0:
        return [(0.0, total, ".")]
    weights = [max(len(c), 14) ** 0.9 for c in cues]
    sw = sum(weights) or 1.0
    durs = [total * w / sw for w in weights]
    cap = min(16.0, max(3.5, total / max(2, n // 2 + 1)))
    durs = [min(cap, max(1.15, d)) for d in durs]
    scale = total / sum(durs)
    durs = [d * scale for d in durs]
    out: list[tuple[float, float, str]] = []
    acc = 0.0
    for i, (cue, d) in enumerate(zip(cues, durs, strict=True)):
        if i == n - 1:
            out.append((acc, total, cue))
        else:
            end = acc + d
            out.append((acc, end, cue))
            acc = end
    return out


def create_subtitle_srt(
    text: str,
    out_file: Path,
    *,
    segment_seconds: int = 9,
    words_per_chunk: int = 20,
    audio_duration_seconds: float | None = None,
) -> Path:
    lines: list[str] = []
    if audio_duration_seconds is not None and audio_duration_seconds > 0.3:
        cues = _split_into_display_cues(text, max_chars=96)
        ranges = _cue_time_ranges(cues, audio_duration_seconds)
        for idx, (a, b, body) in enumerate(ranges, start=1):
            lines.append(str(idx))
            lines.append(f"{_srt_timestamp(a)} --> {_srt_timestamp(b)}")
            lines.append(body)
            lines.append("")
    else:
        words = text.split()
        chunks = [
            " ".join(words[i : i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)
        ]
        for idx, chunk in enumerate(chunks, start=1):
            start = (idx - 1) * segment_seconds
            end = idx * segment_seconds
            lines.append(str(idx))
            lines.append(
                f"00:{start // 60:02d}:{start % 60:02d},000 --> 00:{end // 60:02d}:{end % 60:02d},000"
            )
            lines.append(chunk)
            lines.append("")
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


def _bright_gradients() -> str:
    return (
        "gradients=s=1920x1080:r=30:n=4:c0=0xf8fafc:c1=0xe0f2fe:c2=0xbfdbfe:c3=0x2563eb:"
        "d=86400:speed=0.05:type=spiral"
    )


def render_video(
    title: str,
    narration_mp3: Path,
    subtitles_srt: Path,
    out_mp4: Path,
    *,
    work_dir: Path,
    reporter_video_path: str | None = None,
    reporter_image_path: str | None = None,
) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    rep_vid = _path_or_none(reporter_video_path)
    rep_img = _path_or_none(reporter_image_path)
    use_video = rep_vid is not None and rep_vid.exists()

    caps = build_caption_assets(srt_path=subtitles_srt, work_dir=work_dir / "caps", max_segments=22)

    anchor_card = work_dir / "anchor-card.png"
    avatar_path: Path | None = None
    if not use_video:
        if rep_img is not None and rep_img.exists():
            avatar_path = rep_img
        else:
            render_anchor_card(anchor_card, headline=title)
            avatar_path = anchor_card

    cmd: list[str] = ["ffmpeg", "-y", "-f", "lavfi", "-i", _bright_gradients()]
    graph: list[str] = []

    if use_video:
        cmd += ["-stream_loop", "-1", "-i", str(rep_vid)]
        graph.append(
            "[1:v]fps=30,format=yuv420p,"
            "scale=1040:-1:force_original_aspect_ratio=decrease,"
            "pad=1040:1240:(ow-iw)/2:(oh-ih)/2,eq=gamma=1.12:brightness=0.03[avatar]"
        )
        graph.append("[0:v]format=yuv420p,eq=gamma=1.06[bg];[bg][avatar]overlay=70:70:format=auto[stage0]")
        next_idx = 2
    else:
        assert avatar_path is not None
        cmd += ["-loop", "1", "-framerate", "30", "-i", str(avatar_path)]
        # Subtle zoom/pan on still reporter image (broadcast-style motion; not lip-sync).
        graph.append(
            "[1:v]fps=30,format=rgba,"
            "zoompan=z='1.02+0.018*sin(2*3.1415926*on/270)':"
            "x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s=920x1180:fps=30,"
            "scale=920:-1[avatar];"
            "[0:v]format=yuv420p,eq=gamma=1.06[bg];"
            "[bg][avatar]overlay=70:70:format=auto[stage0]"
        )
        next_idx = 2

    cmd += ["-i", str(narration_mp3)]
    audio_idx = next_idx
    next_idx += 1

    cap_first_idx = next_idx
    for cap in caps:
        cmd += ["-loop", "1", "-framerate", "30", "-i", str(cap.png_path)]

    graph.append(
        f"[{audio_idx}:a]showwaves=s=1920x240:mode=line:colors=0xffffff|0x38bdf8:rate=30,format=yuv420p[waves];"
        f"[stage0][waves]overlay=0:H-240:format=auto[stage1]"
    )

    label = "stage1"
    cur_in = cap_first_idx
    for i, cap in enumerate(caps):
        scaled = f"cs{i}"
        nxt = f"L{i}"
        graph.append(
            f"[{cur_in}:v]format=rgba,scale=1180:-1[{scaled}];"
            f"[{label}][{scaled}]overlay=(W-w)/2:main_h-overlay_h-268:"
            f"enable='between(t,{cap.start:.3f},{cap.end:.3f})'[{nxt}]"
        )
        label = nxt
        cur_in += 1

    # Scale to 720p at the end: smaller files for Telegram (bot sendVideo limit ~50 MB).
    graph.append(
        f"[{label}]eq=brightness=0.02:gamma=1.02,scale=1280:720:flags=lanczos[outv]"
    )

    cmd += [
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[outv]",
        "-map",
        f"{audio_idx}:a:0",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(out_mp4),
    ]

    try:
        _run(cmd)
    except subprocess.CalledProcessError:
        if use_video and rep_img is not None and rep_img.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            work_dir.mkdir(parents=True, exist_ok=True)
            return render_video(
                title,
                narration_mp3,
                subtitles_srt,
                out_mp4,
                work_dir=work_dir,
                reporter_video_path=None,
                reporter_image_path=str(rep_img),
            )
        raise
    return out_mp4
