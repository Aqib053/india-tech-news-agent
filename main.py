"""Re-export so `python main.py` still works. Implementation lives in `run_news_video.py`.

For Vercel: keep the project's Root Directory set to `web/` so this file is not used as a Python serverless entrypoint.
"""

from run_news_video import main

if __name__ == "__main__":
    main()
