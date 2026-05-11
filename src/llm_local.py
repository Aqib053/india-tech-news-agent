from __future__ import annotations

import json
import re

import httpx

from src.models import NewsItem, VideoPackage


def _fallback_package(
    stories: list[NewsItem],
    title_prefix: str,
    *,
    max_headlines: int = 4,
) -> VideoPackage:
    lines = []
    for i, s in enumerate(stories[:max_headlines], start=1):
        lines.append(f"Story {i}: {s.title}. Source: {s.url}.")
    narration = (
        "Namaste. Here is a quick India news update from the wires. "
        + " ".join(lines)
        + " Follow the links in the description for the full reports. Thank you."
    )
    return VideoPackage(
        title=f"{title_prefix}: {stories[0].title[:70] if stories else 'Daily Update'}",
        description="Automated daily tech briefing generated from Google News and YouTube signals.",
        narration=narration,
        tags=["tech", "news", "ai", "startups", "daily update"],
        stories=stories,
    )


def _strip_json_block(text: str) -> str:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else text


def generate_package_with_ollama(
    ollama_url: str,
    ollama_model: str,
    stories: list[NewsItem],
    title_prefix: str,
    *,
    narration_target_seconds: int = 60,
    max_headlines: int = 6,
) -> VideoPackage:
    if not stories:
        return _fallback_package([], title_prefix, max_headlines=max_headlines)

    lo = max(20, narration_target_seconds - 12)
    hi = narration_target_seconds + 25

    def _story_block(s: NewsItem) -> str:
        body = (s.content or "").strip().replace("\n", " ")
        excerpt = body[:520] if body else ""
        ex_line = f"\n  Article excerpt (from India/Google News scrape): {excerpt}" if excerpt else ""
        return (
            f"- Headline: {s.title}\n"
            f"  Feed: {s.source}\n"
            f"  URL: {s.url}\n"
            f"  Snippet: {s.snippet[:420]}{ex_line}"
        )

    source_blob = "\n".join(_story_block(s) for s in stories)
    prompt = (
        "You are the scriptwriter for an India-focused TV-style tech and national-interest news bulletin.\n"
        "Facts must come ONLY from the Snippet and Article excerpt lines below. Do not invent names, "
        "numbers, dates, or quotes.\n"
        "Return strict JSON with keys: title, description, narration, tags.\n"
        "title: short headline suitable for YouTube, start with the given TITLE_PREFIX when it fits.\n"
        "description: bullet list; for each story one line = headline + ' — ' + URL from the item.\n"
        f"narration: Indian English, clear broadcast voice. Target about {narration_target_seconds} seconds "
        f"spoken (stay roughly between {lo} and {hi} seconds). Follow this format exactly:\n"
        "  (1) One-line greeting, e.g. Namaste, here is your India news update.\n"
        "  (2) For EACH story in the same order as STORIES: say 'Story one / two / three' then the headline "
        "in plain words, then one or two short sentences summarising ONLY what the Snippet/excerpt support. "
        "Mention India or Indians only when the text supports it.\n"
        "  (3) One-line sign-off, e.g. Follow the links in the description for full reports.\n"
        "tags: array of short strings, include India and relevant topics.\n\n"
        f"TITLE_PREFIX: {title_prefix}\n"
        f"STORIES:\n{source_blob}"
    )

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{ollama_url.rstrip('/')}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = str(resp.json().get("response", ""))
            data = json.loads(_strip_json_block(raw))
            title = str(data.get("title", "")).strip() or f"{title_prefix}: Daily Tech Briefing"
            description = str(data.get("description", "")).strip() or "Automated daily tech briefing."
            narration = str(data.get("narration", "")).strip()
            tags = [str(t).strip() for t in data.get("tags", []) if str(t).strip()]
            if not narration:
                return _fallback_package(stories, title_prefix, max_headlines=max_headlines)
            return VideoPackage(
                title=title[:100],
                description=description[:5000],
                narration=narration,
                tags=tags[:20] if tags else ["tech", "news", "ai"],
                stories=stories,
            )
    except Exception:
        return _fallback_package(stories, title_prefix, max_headlines=max_headlines)
