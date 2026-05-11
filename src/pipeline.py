from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.collectors.google_news import fetch_google_news, fetch_india_google_top_stories
from src.collectors.wikipedia_context import fetch_wikipedia_summaries
from src.config import Settings
from src.llm_local import generate_package_with_ollama
from src.models import NewsItem
from src.publishers import publish_video
from src.tts import synthesize_voiceover
from src.video import create_subtitle_srt, ffprobe_audio_duration_seconds, render_video


def _cap_narration_spoken_length(text: str, target_seconds: int) -> str:
    """Limit word count so TTS + FFmpeg stay near target_seconds even if the LLM writes long copy."""
    words_per_second = 2.1
    max_words = max(32, int(target_seconds * words_per_second))
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words]).rstrip(".,;:")
    return f"{clipped}. That's the briefing for now."


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    out: list[NewsItem] = []
    for item in items:
        key = hashlib.sha1(f"{item.title.lower()}|{item.url}".encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _item_key(item: NewsItem) -> str:
    return hashlib.sha1(f"{item.title.lower()}|{item.url}".encode("utf-8")).hexdigest()


def _score(item: NewsItem) -> float:
    recency_bonus = 0.0
    if item.published_at:
        age_hours = max((datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600, 0)
        recency_bonus = max(0.0, 48.0 - age_hours) / 48.0
    source_bonus = 0.38 if item.source in {"google_news", "google_news_india"} else 0.25
    richness_bonus = min(len(item.content) / 2500, 0.4)
    return recency_bonus + source_bonus + richness_bonus


def _persist_run_report(output_dir: Path, payload: dict) -> None:
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    (report_dir / f"run-{ts}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_used_keys(memory_file: Path) -> set[str]:
    if not memory_file.exists():
        return set()
    try:
        data = json.loads(memory_file.read_text(encoding="utf-8"))
        return {str(x) for x in data.get("used_keys", [])}
    except Exception:
        return set()


def _save_used_keys(memory_file: Path, used_keys: set[str]) -> None:
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "used_keys": sorted(used_keys),
    }
    memory_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_daily_pipeline(settings: Settings) -> dict:
    search_items = fetch_google_news(
        query=settings.news_query, max_items=28, region=settings.news_region
    )
    india_items = fetch_india_google_top_stories(max_items=14)
    merged = _dedupe(search_items + india_items)
    memory_file = Path(settings.memory_file)
    used_keys = _load_used_keys(memory_file)

    fresh_items = [item for item in merged if _item_key(item) not in used_keys]
    if len(fresh_items) < settings.max_stories:
        raise RuntimeError(
            f"Only {len(fresh_items)} fresh India news items found; need {settings.max_stories}. "
            "Try again later for new stories."
        )

    for i in fresh_items:
        i.score = _score(i)
    ranked = sorted(fresh_items, key=lambda x: x.score, reverse=True)[: settings.max_stories]

    package = generate_package_with_ollama(
        ollama_url=settings.ollama_url,
        ollama_model=settings.ollama_model,
        stories=ranked,
        title_prefix=settings.video_title_prefix,
        narration_target_seconds=settings.narration_target_seconds,
        max_headlines=settings.max_stories,
    )
    package.narration = _cap_narration_spoken_length(
        package.narration, settings.narration_target_seconds
    )

    wiki_context = fetch_wikipedia_summaries(package.narration)
    if wiki_context:
        package.description += "\n\nContext references:\n"
        for topic, summary in list(wiki_context.items())[:5]:
            package.description += f"- {topic}: {summary[:220]}...\n"

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    audio_file = settings.output_dir / f"voiceover-{stamp}.mp3"
    srt_file = settings.output_dir / f"subtitles-{stamp}.srt"
    video_file = settings.output_dir / f"tech-news-{stamp}.mp4"
    work_dir = settings.output_dir / "scratch" / stamp
    work_dir.mkdir(parents=True, exist_ok=True)

    synthesize_voiceover(package.narration, settings.voice_name, audio_file)
    audio_dur = ffprobe_audio_duration_seconds(audio_file)
    if audio_dur is not None:
        create_subtitle_srt(
            package.narration,
            srt_file,
            segment_seconds=8,
            words_per_chunk=11,
            audio_duration_seconds=audio_dur,
        )
    else:
        create_subtitle_srt(package.narration, srt_file, segment_seconds=8, words_per_chunk=11)
    render_video(
        package.title,
        audio_file,
        srt_file,
        video_file,
        work_dir=work_dir,
        reporter_video_path=settings.reporter_video_path or None,
        reporter_image_path=settings.reporter_image_path or None,
    )

    publish_refs = publish_video(
        video_file=video_file,
        title=package.title,
        description=package.description,
        tags=package.tags,
        settings=settings,
    )
    used_keys.update(_item_key(item) for item in ranked)
    _save_used_keys(memory_file, used_keys)

    report = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "selected_count": len(ranked),
        "fresh_pool_count": len(fresh_items),
        "video_file": str(video_file),
        "publish_refs": publish_refs,
        "title": package.title,
    }
    _persist_run_report(settings.output_dir, report)
    return report
