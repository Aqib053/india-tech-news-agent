from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx
import trafilatura

from src.models import NewsItem


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_article_text(url: str) -> str:
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
            return text or ""
    except Exception:
        return ""


def _items_from_feed(
    entries: list[object],
    *,
    max_items: int,
    source: str,
    extract_body: bool,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    for entry in entries[:max_items]:
        url = entry.get("link", "").strip()
        if not url:
            continue
        content = _extract_article_text(url) if extract_body else ""
        item = NewsItem(
            source=source,
            title=entry.get("title", "").strip(),
            url=url,
            published_at=_parse_dt(entry.get("published")),
            snippet=entry.get("summary", "").strip(),
            content=content,
        )
        items.append(item)
    return items


def fetch_google_news(
    query: str = "technology",
    max_items: int = 20,
    region: str = "IN",
    language: str = "en",
) -> list[NewsItem]:
    region = (region or "IN").upper()
    language = (language or "en").lower()
    rss_url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}+when:2d&hl={language}-{region}&gl={region}&ceid={region}:{language}"
    )
    feed = feedparser.parse(rss_url)
    return _items_from_feed(feed.entries, max_items=max_items, source="google_news", extract_body=True)


def fetch_india_google_top_stories(max_items: int = 14) -> list[NewsItem]:
    """India edition Google News homepage RSS (broad Indian coverage, English)."""
    rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return _items_from_feed(
        feed.entries,
        max_items=max_items,
        source="google_news_india",
        extract_body=True,
    )
