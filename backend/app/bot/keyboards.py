from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.config import settings
from app.i18n import t
from app.services.notify import Button


def webapp_enabled() -> bool:
    # Telegram only accepts https Mini App URLs.
    return settings.public_url.startswith("https://")


def webapp_url(path: str = "/") -> str:
    url = settings.miniapp_url
    return url if path in ("", "/") else f"{url}?p={quote(path)}"


def language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def contact(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "reg.contact_button"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def terms(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "reg.accept_terms"), callback_data="terms:accept")]]
    )


def main_reply(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "menu.lang")), KeyboardButton(text=t(lang, "menu.help"))]],
        resize_keyboard=True,
    )


def open_app(lang: str, path: str = "/") -> InlineKeyboardMarkup | None:
    if not webapp_enabled():
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "menu.open_app"), web_app=WebAppInfo(url=webapp_url(path)))]]
    )


def from_buttons(rows: list[list[Button]], lang: str) -> InlineKeyboardMarkup | None:
    out = []
    for row in rows:
        r = []
        for b in row:
            text = t(lang, b.text_key)
            if b.callback:
                r.append(InlineKeyboardButton(text=text, callback_data=b.callback))
            elif b.webapp_path is not None and webapp_enabled():
                r.append(InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_url(b.webapp_path))))
        if r:
            out.append(r)
    return InlineKeyboardMarkup(inline_keyboard=out) if out else None
