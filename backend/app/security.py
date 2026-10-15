import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qsl


class InvalidInitData(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    """Validates Telegram Mini App initData (HMAC-SHA256) and returns the `user` object."""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        raise InvalidInitData("malformed")
    received_hash = pairs.pop("hash", None)
    if not received_hash or not bot_token:
        raise InvalidInitData("no hash")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InvalidInitData("bad signature")
    try:
        auth_date = int(pairs.get("auth_date", "0"))
        user = json.loads(pairs["user"])
    except (ValueError, KeyError):
        raise InvalidInitData("bad payload")
    if time.time() - auth_date > max_age_seconds:
        raise InvalidInitData("expired")
    if not isinstance(user, dict) or "id" not in user:
        raise InvalidInitData("no user")
    return user


def sign_init_data(fields: dict, bot_token: str) -> str:
    """Builds a valid initData string (used by tests)."""
    from urllib.parse import urlencode

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


# ---- admin passwords (stdlib scrypt, no extra dependency)

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calc.hex(), dk)
    except (ValueError, TypeError):
        return False
