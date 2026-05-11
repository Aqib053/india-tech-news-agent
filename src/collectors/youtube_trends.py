from __future__ import annotations

from datetime import datetime, timezone

from googleapiclient.discovery import build

from src.models import NewsItem


def _safe_parse_youtube_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def fetch_youtube_news(api_key: str, max_items: int = 20) -> list[NewsItem]:
    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    request = youtube.search().list(
        q="tech news",
        part="snippet",
        type="video",
        order="date",
        maxResults=min(max_items, 50),
        relevanceLanguage="en",
    )
    response = request.execute()
    items: list[NewsItem] = []
    for row in response.get("items", []):
        vid = row.get("id", {}).get("videoId")
        snippet = row.get("snippet", {})
        if not vid:
            continue
        title = snippet.get("title", "").strip()
        channel = snippet.get("channelTitle", "").strip()
        description = snippet.get("description", "").strip()
        published = _safe_parse_youtube_dt(snippet.get("publishedAt"))
        items.append(
            NewsItem(
                source="youtube",
                title=title,
                url=f"https://www.youtube.com/watch?v={vid}",
                published_at=published,
                snippet=description,
                content=f"Channel: {channel}. {description}",
            )
        )
    return items
