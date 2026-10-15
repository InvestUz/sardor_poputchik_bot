"""Bot: registration (language -> contact -> terms), main menu, quick actions from notifications."""

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot import keyboards as kb
from app.config import settings
from app.db import uow
from app.i18n import t
from app.models import User
from app.services import offers, orders, users
from app.services import settings as settings_svc
from app.services.errors import DomainError

log = logging.getLogger(__name__)
router = Router()

LANG_BUTTONS = {t("uz", "menu.lang"), t("ru", "menu.lang")}
HELP_BUTTONS = {t("uz", "menu.help"), t("ru", "menu.help")}


def terms_url(lang: str) -> str:
    return f"{settings.public_url.rstrip('/')}/terms?lang={lang}"


async def _blocked(message: Message, user: User) -> bool:
    if not user.is_blocked:
        return False
    async with uow() as s:
        support = await settings_svc.get(s, "support_contact")
    await message.answer(t(user.lang, "blocked", reason=user.block_reason or "-", support=support))
    return True


async def send_menu(message: Message, lang: str) -> None:
    await message.answer(t(lang, "menu.main"), reply_markup=kb.main_reply(lang))
    markup = kb.open_app(lang)
    if markup:
        await message.answer(t(lang, "menu.open_app"), reply_markup=markup)


async def continue_registration(message: Message, user: User) -> None:
    if not user.phone:
        await message.answer(t(user.lang, "reg.ask_contact"), reply_markup=kb.contact(user.lang))
    elif user.terms_accepted_at is None:
        await message.answer(
            t(user.lang, "reg.terms", url=html.escape(terms_url(user.lang))),
            reply_markup=kb.terms(user.lang),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        await send_menu(message, user.lang)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    async with uow() as s:
        user, _ = await users.get_or_create(s, message.from_user.model_dump())
    if await _blocked(message, user):
        return
    if not user.is_registered:
        await message.answer(t(user.lang, "lang.choose"), reply_markup=kb.language())
        return
    await send_menu(message, user.lang)


@router.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    async with uow() as s:
        user, _ = await users.get_or_create(s, cb.from_user.model_dump())
        users.set_lang(user, lang)
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    if user.is_registered:
        await cb.message.answer(t(lang, "lang.changed"))
        await send_menu(cb.message, lang)
    else:
        await continue_registration(cb.message, user)


@router.message(F.contact)
async def on_contact(message: Message) -> None:
    async with uow() as s:
        user, _ = await users.get_or_create(s, message.from_user.model_dump())
        if message.contact.user_id != message.from_user.id:
            await message.answer(t(user.lang, "reg.contact_not_own"), reply_markup=kb.contact(user.lang))
            return
        users.set_phone(user, message.contact.phone_number)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    await continue_registration(message, user)


@router.callback_query(F.data == "terms:accept")
async def on_terms(cb: CallbackQuery) -> None:
    async with uow() as s:
        user, _ = await users.get_or_create(s, cb.from_user.model_dump())
        if not user.phone:
            await cb.answer()
            await continue_registration(cb.message, user)
            return
        await users.accept_terms(s, user)
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await cb.message.answer(t(user.lang, "reg.done"))
    await send_menu(cb.message, user.lang)


@router.message(F.text.in_(LANG_BUTTONS))
async def on_lang_menu(message: Message) -> None:
    await message.answer(t("uz", "lang.choose"), reply_markup=kb.language())


@router.message(F.text.in_(HELP_BUTTONS))
async def on_help(message: Message) -> None:
    async with uow() as s:
        user, _ = await users.get_or_create(s, message.from_user.model_dump())
        support = await settings_svc.get(s, "support_contact")
    await message.answer(t(user.lang, "help.text", support=support))


# ---------------------------------------------------------------- quick actions from notifications

ORDER_ACTIONS = {
    "confirm": orders.confirm,
    "start": orders.start,
    "complete": orders.complete,
    "deliver": orders.deliver,
}
OFFER_ACTIONS = {"accept": offers.accept, "reject": offers.reject}


@router.callback_query(F.data.regexp(r"^(o|of):[a-z]+:\d+$"))
async def on_quick_action(cb: CallbackQuery) -> None:
    prefix, action, raw_id = cb.data.split(":")
    fn = (ORDER_ACTIONS if prefix == "o" else OFFER_ACTIONS).get(action)
    lang = "uz"
    try:
        async with uow() as s:
            user = await users.get_by_telegram_id(s, cb.from_user.id)
            lang = user.lang if user else lang
            if fn is None:
                raise DomainError("not_found")
            await fn(s, users.ensure_active(user), int(raw_id))
    except DomainError as e:
        key = f"err.{e.code}"
        text = t(lang, key) if t(lang, key) != key else t(lang, "err.generic")
        await cb.answer(text, show_alert=True)
        return
    except Exception:
        log.exception("quick action %s failed", cb.data)
        await cb.answer(t(lang, "err.generic"), show_alert=True)
        return
    await cb.answer(t(lang, "act.done"))
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


@router.message()
async def fallback(message: Message) -> None:
    async with uow() as s:
        user, _ = await users.get_or_create(s, message.from_user.model_dump())
    if await _blocked(message, user):
        return
    if not user.is_registered:
        await continue_registration(message, user) if user.phone else await message.answer(
            t(user.lang, "lang.choose"), reply_markup=kb.language()
        )
        return
    await send_menu(message, user.lang)
