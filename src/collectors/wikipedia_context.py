from __future__ import annotations

import re

import httpx


def _topic_candidates(text: str, limit: int = 6) -> list[str]:
    candidates = re.findall(r"\b([A-Z][a-zA-Z0-9\-\+]{2,}(?:\s+[A-Z][a-zA-Z0-9\-\+]{2,}){0,2})\b", text)
    unique: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
        if len(unique) >= limit:
            break
    return unique


def fetch_wikipedia_summaries(narration_seed: str) -> dict[str, str]:
    topics = _topic_candidates(narration_seed)
    context: dict[str, str] = {}
    with httpx.Client(timeout=10) as client:
        for topic in topics:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '%20')}"
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                extract = str(data.get("extract", "")).strip()
                if extract:
                    context[topic] = extract
            except Exception:
                continue
    return context
