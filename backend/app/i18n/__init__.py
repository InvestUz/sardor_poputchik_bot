"""Centralised UI texts for the bot and notifications (TZ §16). Edit the JSON files, not the code."""

import json
from pathlib import Path

_DIR = Path(__file__).parent
LANGS = ("uz", "ru")
_texts: dict[str, dict[str, str]] = {
    lang: json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS
}


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def t(lang: str, key: str, **params) -> str:
    text = _texts.get(lang, {}).get(key) or _texts["uz"].get(key) or key
    return text.format_map(_Safe(params))


def has(key: str) -> bool:
    return all(key in _texts[lang] for lang in LANGS)


def keys(lang: str) -> set[str]:
    return set(_texts[lang])


def money(v: int | None) -> str:
    return f"{v:,}".replace(",", " ") if v is not None else ""
