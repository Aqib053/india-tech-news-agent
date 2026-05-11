from __future__ import annotations

from src.config import load_settings
from src.telegram_trigger_bot import TelegramTriggerBot


def main() -> None:
    settings = load_settings()
    bot = TelegramTriggerBot(settings=settings)
    bot.run_forever()


if __name__ == "__main__":
    main()
