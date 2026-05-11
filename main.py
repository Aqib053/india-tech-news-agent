from __future__ import annotations

import argparse


def _cmd_run() -> None:
    from run_news_video import main as run_once

    run_once()


def _cmd_bot() -> None:
    from run_bot import main as run_bot_main

    run_bot_main()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="News video pipeline: run once or start the Telegram trigger bot.",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    sub.add_parser("run", help="Generate one video and publish per PUBLISH_TARGET (e.g. telegram,youtube).")
    sub.add_parser("bot", help="Start Telegram long-poll bot (/start → Generate New Video).")

    args = parser.parse_args()
    cmd = args.command or "run"

    if cmd == "run":
        _cmd_run()
    elif cmd == "bot":
        _cmd_bot()
    else:
        parser.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()
