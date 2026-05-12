from __future__ import annotations

import json
import threading
import time
from dataclasses import replace

import httpx

from src.config import Settings
from src.pipeline import run_daily_pipeline


class TelegramTriggerBot:
    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run trigger bot.")
        self.settings = settings
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self._offset = 0
        self._lock = threading.Lock()
        self._is_running_job = False

    def run_forever(self) -> None:
        print("Trigger bot started. Use /start or /menu in Telegram.")
        with httpx.Client(timeout=70) as client:
            self._delete_webhook(client)
            while True:
                try:
                    updates = self._get_updates(client)
                except (
                    httpx.ReadError,
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RemoteProtocolError,
                ) as exc:
                    print(f"Telegram connection dropped ({type(exc).__name__}: {exc!s}). Reconnecting in 5s…")
                    time.sleep(5)
                    continue
                for update in updates:
                    self._offset = max(self._offset, update["update_id"] + 1)
                    self._handle_update(client, update)

    def _delete_webhook(self, client: httpx.Client) -> None:
        try:
            response = client.post(
                f"{self.base_url}/deleteWebhook",
                json={"drop_pending_updates": True},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return

    def _get_updates(self, client: httpx.Client) -> list[dict]:
        for attempt in range(6):
            response = client.get(
                f"{self.base_url}/getUpdates",
                params={"timeout": 60, "offset": self._offset},
            )
            if response.status_code == 409:
                self._delete_webhook(client)
                time.sleep(min(2 * (attempt + 1), 15))
                continue
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram getUpdates error: {json.dumps(data)}")
            return data.get("result", [])
        raise RuntimeError(
            "Telegram getUpdates returned 409 repeatedly. "
            "Stop any other bot processes using the same token, then restart run_bot.py."
        )

    def _handle_update(self, client: httpx.Client, update: dict) -> None:
        message = update.get("message")
        callback = update.get("callback_query")
        if message:
            text = str(message.get("text", "")).strip().lower()
            chat_id = str(message.get("chat", {}).get("id", "")).strip()
            if text in {"/start", "/menu", "/trigger"} and chat_id:
                self._send_trigger_button(client, chat_id)
                return
        if callback:
            data = str(callback.get("data", ""))
            callback_id = str(callback.get("id", ""))
            chat_id = str(callback.get("message", {}).get("chat", {}).get("id", "")).strip()
            if data == "generate_video" and chat_id:
                self._answer_callback(client, callback_id, "Generating video now...")
                self._run_generation_job(client, chat_id)

    def _send_trigger_button(self, client: httpx.Client, chat_id: str) -> None:
        payload = {
            "chat_id": chat_id,
            "text": "Tap to generate and publish a fresh tech news video.",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "Generate New Video", "callback_data": "generate_video"}]
                ]
            },
        }
        response = client.post(f"{self.base_url}/sendMessage", json=payload)
        response.raise_for_status()

    def _answer_callback(self, client: httpx.Client, callback_id: str, text: str) -> None:
        if not callback_id:
            return
        try:
            response = client.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # Callback queries can expire quickly; do not crash listener.
            return

    def _run_generation_job(self, client: httpx.Client, chat_id: str) -> None:
        with self._lock:
            if self._is_running_job:
                self._send_message(client, chat_id, "A generation job is already running. Please wait.")
                return
            self._is_running_job = True
        try:
            self._send_message(client, chat_id, "Starting pipeline. This can take a few minutes...")
            per_chat_settings = replace(self.settings, telegram_chat_id=chat_id)
            result = run_daily_pipeline(per_chat_settings)
            self._send_message(
                client,
                chat_id,
                f"Done. New video published.\n\nRefs: {result.get('publish_refs', {})}",
            )
        except Exception as exc:
            self._send_message(client, chat_id, f"Pipeline failed: {exc}")
        finally:
            with self._lock:
                self._is_running_job = False

    def _send_message(self, client: httpx.Client, chat_id: str, text: str) -> None:
        response = client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
        )
        response.raise_for_status()
