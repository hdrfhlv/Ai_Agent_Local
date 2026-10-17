import hashlib
import hmac
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTH_DB = PROJECT_ROOT / "data" / "owner_auth.sqlite3"
_SESSIONS: dict[str, str] = {}
_SESSIONS_LOCK = threading.Lock()
_OWNER_LOCK = threading.Lock()
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_LENGTH = 64
_SCRYPT_MAX_MEMORY = 64 * 1024 * 1024


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(AUTH_DB, timeout=10)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_auth_store() -> None:
    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS owner (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL UNIQUE,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            )
            """
        )


def owner_exists() -> bool:
    with _connection() as connection:
        row = connection.execute("SELECT 1 FROM owner WHERE id = 1").fetchone()
    return row is not None


def create_owner(username: str, password: str) -> None:
    normalized_username = username.strip().casefold()
    salt = secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_LENGTH,
        maxmem=_SCRYPT_MAX_MEMORY,
    )
    with _OWNER_LOCK, _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM owner WHERE id = 1").fetchone():
            raise FileExistsError("Akun pemilik sudah dibuat. Silakan masuk.")
        connection.execute(
            "INSERT INTO owner (id, username, salt, password_hash) VALUES (1, ?, ?, ?)",
            (normalized_username, salt, password_hash),
        )


def authenticate_owner(username: str, password: str) -> str | None:
    normalized_username = username.strip().casefold()
    with _connection() as connection:
        row = connection.execute(
            "SELECT username, salt, password_hash FROM owner WHERE id = 1"
        ).fetchone()

    if row is None:
        return None

    stored_username, salt, expected_hash = row
    actual_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_LENGTH,
        maxmem=_SCRYPT_MAX_MEMORY,
    )
    if normalized_username != stored_username or not hmac.compare_digest(
        actual_hash, expected_hash
    ):
        return None
    return stored_username


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    with _SESSIONS_LOCK:
        _SESSIONS.clear()
        _SESSIONS[token] = username
    return token


def session_username(token: str) -> str | None:
    with _SESSIONS_LOCK:
        return _SESSIONS.get(token)


def revoke_session(token: str) -> None:
    with _SESSIONS_LOCK:
        _SESSIONS.pop(token, None)


def clear_sessions() -> None:
    with _SESSIONS_LOCK:
        _SESSIONS.clear()
