import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonWebApp, Update, WebAppInfo

from app.bot import keyboards
from app.bot.handlers import router
from app.bot.notifier import TelegramNotifier
from app.config import settings
from app.services import notify

log = logging.getLogger(__name__)
ALLOWED_UPDATES = ["message", "callback_query"]


class BotRuntime:
    def __init__(self) -> None:
        self.bot = Bot(settings.bot_token)
        self.dp = Dispatcher()
        self.dp.include_router(router)
        self.notifier = TelegramNotifier(self.bot, settings.admin_chat_id)
        self._tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        notify.set_notifier(self.notifier)
        self.notifier.start()
        await self.bot.set_my_commands([BotCommand(command="start", description="Menu / Меню")])
        if keyboards.webapp_enabled():
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="📱 App", web_app=WebAppInfo(url=settings.miniapp_url))
            )
        if settings.bot_mode == "webhook":
            await self.bot.set_webhook(
                f"{settings.public_url.rstrip('/')}/telegram/webhook",
                secret_token=settings.webhook_secret,
                allowed_updates=ALLOWED_UPDATES,
                drop_pending_updates=False,
            )
            log.info("webhook set")
        elif settings.bot_mode == "polling":
            await self.bot.delete_webhook(drop_pending_updates=False)
            self._spawn(self.dp.start_polling(self.bot, allowed_updates=ALLOWED_UPDATES, handle_signals=False))
            log.info("polling started")

    def feed(self, data: dict) -> None:
        update = Update.model_validate(data, context={"bot": self.bot})
        self._spawn(self.dp.feed_update(self.bot, update))

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        if settings.bot_mode == "polling":
            await self.dp.stop_polling()
        await self.notifier.stop()
        for task in list(self._tasks):
            task.cancel()
        await self.bot.session.close()
