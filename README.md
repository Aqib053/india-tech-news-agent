# India Tech News Agent

An automated pipeline that collects **India-relevant** stories from Google News, drafts a structured TV-style bulletin with a **local LLM (Ollama)**, synthesizes **Indian English (or Hindi) neural speech**, composites a **720p captioned video** with FFmpeg, and publishes to **Telegram**, **YouTube**, or local disk.

---

## Features

| Area | Details |
|------|---------|
| **Sources** | Google News RSS: configurable India query (`when:2d`) plus the **India English homepage** feed for broader coverage. Optional article text via [trafilatura](https://trafilatura.readthedocs.io/). |
| **Script** | Ollama generates strict JSON (title, description with per-story URLs, narration, tags). Facts are grounded in provided snippets and excerpts. |
| **Voice** | Primary: **Microsoft Edge TTS** (`VOICE_NAME`, e.g. `en-IN-NeerjaNeural`). Automatic fallbacks across other India neural voices; then **macOS `say`** with `MACOS_SAY_VOICE` (e.g. `Veena`). |
| **Video** | Bright studio gradient, reporter **image** (Ken Burns motion) or **looping clip**, audio waveform, **timed captions** aligned to real audio duration, **720p H.264** for Telegram’s ~50 MB bot limit. |
| **Dedup** | `MEMORY_FILE` tracks used stories so repeats are avoided across runs. |
| **Triggers** | `run_news_video.py` for batch runs; `run_bot.py` for Telegram inline **Generate New Video**. |

---

## Requirements

Python dependencies are listed in **`requirements.pipeline.txt`** (that name avoids Vercel treating this repo as a Python serverless app when you connect Git).

- **Python** 3.11+ (3.12+ recommended)
- **FFmpeg** on `PATH`
- **Ollama** with a pulled model (default `llama3.1:8b`)
- Optional: **YouTube OAuth** desktop client JSON; **Telegram** bot token and chat ID

---

## Quick start

```bash
git clone https://github.com/Aqib053/india-tech-news-agent.git
cd "AI Agent"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.pipeline.txt
cp .env.example .env
```

1. Edit **`.env`** (never commit it).  
2. Place **YouTube** `client_secrets.json` and complete OAuth locally → `youtube_token.json` under `credentials/` (paths match `.env`).  
3. Add **`assets/reporter.png`** (or set `REPORTER_VIDEO_PATH` to a short loop). Reporter assets are **gitignored** by default.  
4. Start Ollama and pull a model:

```bash
ollama serve
ollama pull llama3.1:8b
```

5. Run once:

```bash
python run_news_video.py
```

Artifacts appear under `output/` (`voiceover-*.mp3`, `subtitles-*.srt`, `tech-news-*.mp4`, `reports/run-*.json`).

---

## Environment variables

Copy from **`.env.example`** and adjust. Common keys:

| Variable | Purpose |
|----------|---------|
| `NEWS_QUERY` | Google News search query (India-focused). |
| `NEWS_REGION` | Region code, default `IN`. |
| `OLLAMA_URL` / `OLLAMA_MODEL` | LLM endpoint and model name. |
| `VOICE_NAME` | Edge voice, e.g. `en-IN-NeerjaNeural` or `hi-IN-MadhurNeural`. |
| `MACOS_SAY_VOICE` | Used when Edge TTS fails (`Veena`, `Lekha`, etc.). |
| `REPORTER_IMAGE_PATH` / `REPORTER_VIDEO_PATH` | On-screen anchor; video wins if the file exists. |
| `NARRATION_TARGET_SECONDS` / `MAX_STORIES` | Script length and story count. |
| `PUBLISH_TARGET` | Comma list: `local`, `telegram`, `youtube`. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | For Telegram sends and trigger bot. |
| `YOUTUBE_*` | OAuth paths, category, privacy (`public` / `private`). |

---

## Telegram trigger bot

```bash
source .venv/bin/activate
python run_bot.py
```

In Telegram: `/start` → **Generate New Video**. Only **one** bot process per token (avoid duplicate `getUpdates` / 409 errors).

---

## Scheduling (cron example)

```cron
30 6 * * * cd /path/to/AI\ Agent && . .venv/bin/activate && python run_news_video.py >> output/cron.log 2>&1
```

---

## Deploy on Vercel

The **`web/`** folder is a **static-only** microsite (HTML + minimal `package.json`) so Vercel never scans the Python worker at the repo root.

**Live site:** [https://india-tech-news-agent-web.vercel.app](https://india-tech-news-agent-web.vercel.app)

1. Import [the GitHub repository](https://github.com/Aqib053/india-tech-news-agent) in [Vercel](https://vercel.com) **or** use the CLI from `web/` (see below).  
2. Open **Project → Settings → General → Root Directory** and set it to **`web`**.  
3. **Build Command:** leave empty. **Output Directory:** leave default (`.`).  
4. **Install Command:** leave default (`npm install` is fine; there are no dependencies).

CLI from your machine:

```bash
cd web && vercel deploy --prod
```

The **pipeline** (Ollama, FFmpeg, long encodes, Telegram long-polling) must run on a **Mac, Linux VPS, or CI runner** — not inside Vercel serverless timeouts.

---

## Security

- Do **not** commit `.env`, `credentials/*.json`, or personal reporter media.  
- Rotate **Telegram** tokens and **Google OAuth** secrets if they were ever exposed.  
- Use **YouTube OAuth** “Test users” while in Testing mode; move to Production when ready for public uploads.

---

## License

MIT — use at your own risk; verify rights for news excerpts, voices, and reporter imagery before publishing.
