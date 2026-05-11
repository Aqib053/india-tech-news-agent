from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: datetime | None
    snippet: str
    content: str
    score: float = 0.0


@dataclass(slots=True)
class VideoPackage:
    title: str
    description: str
    narration: str
    tags: list[str]
    stories: list[NewsItem]
