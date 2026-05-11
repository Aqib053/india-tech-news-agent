from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    video_title_prefix: str
    news_query: str
    news_region: str
    ollama_url: str
    ollama_model: str
    voice_name: str
    reporter_video_path: str
    reporter_image_path: str
    output_dir: Path
    max_stories: int
    narration_target_seconds: int
    memory_file: str
    publish_target: str
    telegram_bot_token: str
    telegram_chat_id: str
    youtube_client_secrets: str
    youtube_token_file: str
    youtube_category_id: str
    youtube_privacy_status: str


def load_settings() -> Settings:
    load_dotenv()
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        video_title_prefix=os.getenv("VIDEO_TITLE_PREFIX", "Top Tech News"),
        news_query=os.getenv(
            "NEWS_QUERY",
            "(India OR Indian OR Delhi OR Mumbai OR Bengaluru OR ISRO OR RBI OR TRAI OR MeitY) "
            "AND (technology OR startup OR artificial intelligence OR telecom OR policy OR cybersecurity)",
        ),
        news_region=os.getenv("NEWS_REGION", "IN"),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        voice_name=os.getenv("VOICE_NAME", "en-IN-NeerjaNeural"),
        reporter_video_path=os.getenv("REPORTER_VIDEO_PATH", "./assets/reporter.mp4").strip(),
        reporter_image_path=os.getenv("REPORTER_IMAGE_PATH", "").strip(),
        output_dir=output_dir,
        max_stories=int(os.getenv("MAX_STORIES", "6")),
        narration_target_seconds=max(20, min(600, int(os.getenv("NARRATION_TARGET_SECONDS", "60")))),
        memory_file=os.getenv("MEMORY_FILE", "./output/used_news.json"),
        publish_target=os.getenv("PUBLISH_TARGET", "local").strip().lower(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        youtube_client_secrets=os.getenv("YOUTUBE_CLIENT_SECRETS", "./credentials/client_secrets.json").strip(),
        youtube_token_file=os.getenv("YOUTUBE_TOKEN_FILE", "./credentials/youtube_token.json").strip(),
        youtube_category_id=os.getenv("YOUTUBE_CATEGORY_ID", "28").strip(),
        youtube_privacy_status=os.getenv("YOUTUBE_PRIVACY_STATUS", "private").strip(),
    )
