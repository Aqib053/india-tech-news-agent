from __future__ import annotations

from pathlib import Path

import httpx

from src.config import Settings
from src.youtube_upload import upload_video


def publish_video(
    video_file: Path,
    title: str,
    description: str,
    tags: list[str],
    settings: Settings,
) -> dict[str, str]:
    targets = _parse_targets(settings.publish_target)
    refs: dict[str, str] = {}
    for target in targets:
        if target == "local":
            refs["local"] = f"file://{video_file.resolve()}"
            continue
        if target == "telegram":
            refs["telegram"] = _publish_to_telegram(video_file=video_file, caption=title, settings=settings)
            continue
        if target == "youtube":
            refs["youtube"] = _publish_to_youtube(
                video_file=video_file,
                title=title,
                description=description,
                tags=tags,
                settings=settings,
            )
            continue
        raise RuntimeError(
            f"Unsupported publish target '{target}'. Use a comma-separated list from: local, telegram, youtube."
        )
    return refs


def _parse_targets(raw: str) -> list[str]:
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return parts or ["local"]


def _publish_to_telegram(video_file: Path, caption: str, settings: Settings) -> str:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID for Telegram publishing.")

    size = video_file.stat().st_size
    if size > 52 * 1024 * 1024:
        raise RuntimeError(
            f"Video file is {size / (1024 * 1024):.1f} MiB; Telegram bots only allow about 50 MiB for sendVideo. "
            "Shorten narration or lower quality in src/video.py."
        )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendVideo"
    with httpx.Client(timeout=600) as client:
        with video_file.open("rb") as fp:
            response = client.post(
                url,
                data={"chat_id": settings.telegram_chat_id, "caption": caption[:900]},
                files={"video": (video_file.name, fp, "video/mp4")},
            )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 413:
            raise RuntimeError(
                "Telegram returned 413 Request Entity Too Large (bot sendVideo limit is about 50 MiB). "
                "Re-run the pipeline with the updated 720p encoding, or shorten the video further."
            ) from exc
        raise
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram publish failed: {payload}")
    message_id = payload["result"]["message_id"]
    return f"telegram://chat/{settings.telegram_chat_id}/message/{message_id}"


def _publish_to_youtube(
    video_file: Path,
    title: str,
    description: str,
    tags: list[str],
    settings: Settings,
) -> str:
    return upload_video(
        video_file=video_file,
        title=title,
        description=description,
        tags=tags,
        category_id=settings.youtube_category_id,
        privacy_status=settings.youtube_privacy_status,
        client_secrets=settings.youtube_client_secrets,
        token_file=settings.youtube_token_file,
    )
