"""Authorized Telegram text and voice gateway for the Go2 agent."""

from __future__ import annotations

import asyncio
import io
import threading
from dataclasses import dataclass
from queue import Empty, Queue

from openai import OpenAI
from telegram import Update
from telegram.ext import Application, MessageHandler, filters


@dataclass(frozen=True)
class TelegramEvent:
    text: str


class TelegramGateway:
    """Translate Telegram updates into agent events without touching ROS."""

    def __init__(
        self,
        token: str,
        chat_id: int,
        event_queue: Queue,
    ):
        self.token = token
        self.chat_id = chat_id
        self.event_queue = event_queue
        self.outgoing_queue: Queue[str] = Queue()
        self._openai = OpenAI()
        self._application: Application | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._stopping = threading.Event()
        self._outgoing_task: asyncio.Task | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="go2-telegram",
            daemon=True,
        )
        self._thread.start()
        if not self._started.wait(timeout=10.0):
            raise RuntimeError("Telegram gateway did not start")

    def stop(self) -> None:
        if (
            not self._loop
            or not self._thread
            or not self._thread.is_alive()
        ):
            return
        self._stopping.set()
        future = asyncio.run_coroutine_threadsafe(
            self._shutdown(), self._loop
        )
        try:
            future.result(timeout=10.0)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10.0)

    def send_message(self, text: str) -> None:
        self.outgoing_queue.put(text)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_application())
            self._started.set()
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()

    async def _start_application(self) -> None:
        application = Application.builder().token(self.token).build()
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self._on_text
            )
        )
        application.add_handler(
            MessageHandler(filters.VOICE, self._on_voice)
        )
        self._application = application
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        self._outgoing_task = asyncio.create_task(
            self._drain_outgoing_messages()
        )

    async def _shutdown(self) -> None:
        if self._outgoing_task:
            self._outgoing_task.cancel()
            await asyncio.gather(
                self._outgoing_task, return_exceptions=True
            )
            self._outgoing_task = None
        application = self._application
        if application is None:
            return
        if application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        self._application = None

    async def _on_text(self, update: Update, _context) -> None:
        message = update.effective_message
        if message is None or not self._is_allowed(update):
            return
        text = (message.text or "").strip()
        if text:
            self._enqueue_event(text)

    async def _on_voice(self, update: Update, _context) -> None:
        message = update.effective_message
        if (
            message is None
            or message.voice is None
            or not self._is_allowed(update)
        ):
            return
        try:
            telegram_file = await message.voice.get_file()
            audio_bytes = await telegram_file.download_as_bytearray()
            text = await asyncio.to_thread(
                self._transcribe_voice, bytes(audio_bytes)
            )
        except Exception as exc:
            await message.reply_text(f"Voice transcription failed: {exc}")
            return
        if text:
            self._enqueue_event(text)

    def _enqueue_event(self, text: str) -> None:
        self.event_queue.put(TelegramEvent(text=text))

    def _transcribe_voice(self, audio_bytes: bytes) -> str:
        audio = io.BytesIO(audio_bytes)
        audio.name = "telegram_voice.ogg"
        transcription = self._openai.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio,
        )
        return (transcription.text or "").strip()

    async def _drain_outgoing_messages(self) -> None:
        while not self._stopping.is_set():
            try:
                text = self.outgoing_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.2)
                continue
            try:
                await self._application.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                )
            except Exception as exc:
                print(f"Telegram send failed: {exc}")

    def _is_allowed(self, update: Update) -> bool:
        chat = update.effective_chat
        return chat is not None and chat.id == self.chat_id
