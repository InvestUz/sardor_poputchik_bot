from datetime import datetime, timedelta, timezone

UTC = timezone.utc
# Uzbekistan has a fixed UTC+5 offset with no DST.
TASHKENT = timezone(timedelta(hours=5), "Asia/Tashkent")


def now() -> datetime:
    return datetime.now(UTC)


def local(dt: datetime) -> datetime:
    return dt.astimezone(TASHKENT)


def fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return local(dt).strftime("%d.%m.%Y %H:%M")
