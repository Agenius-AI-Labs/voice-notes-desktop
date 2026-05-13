"""OS-native credential storage with SQLite fallback.

Uses the `keyring` library to talk to:
  - macOS Keychain
  - Windows Credential Manager
  - Linux Secret Service (GNOME Keyring / KWallet via D-Bus)

If no keyring backend is available (e.g., a headless Linux box without
secret-service) the helpers fall back to the SQLite `settings` table.
Read order in the parsers is: env var → keyring → DB.

Service name on all three platforms is `voice-notes-desktop`. Accounts are
the short slugs `openai`, `anthropic`, `elevenlabs`.

Never log the value. Errors log only the account name.
"""

from __future__ import annotations

from .db import db_get_setting, db_set_setting
from .logging_config import get_logger

_log = get_logger("keystore")

SERVICE_NAME = "voice-notes-desktop"

# Account → DB setting key used for the fallback row.
_ACCOUNTS: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "elevenlabs": "elevenlabs_api_key",
}


def _try_keyring():
    """Return (module, available_bool). Cached at first call."""
    try:
        import keyring
        from keyring.errors import KeyringError, NoKeyringError
        # Touch the backend so we surface NoKeyringError up-front rather than
        # discovering it on the first read.
        backend = keyring.get_keyring()
        # `null.Keyring` on most platforms when nothing is wired up; check by
        # type name rather than importing the private backend class.
        backend_name = type(backend).__module__ + "." + type(backend).__name__
        if "fail" in backend_name.lower() or "null" in backend_name.lower():
            return keyring, False
        return keyring, True
    except Exception as exc:
        _log.info("keyring unavailable: %s", exc)
        return None, False


_KEYRING, _KEYRING_OK = _try_keyring()


def keyring_available() -> bool:
    return _KEYRING_OK


def _db_key_for(account: str) -> str:
    if account in _ACCOUNTS:
        return _ACCOUNTS[account]
    # For unknown accounts, namespace the DB key to avoid collisions.
    return f"secret_{account}"


def get_secret(account: str) -> str:
    """Return the stored value or '' if absent."""
    if _KEYRING_OK and _KEYRING is not None:
        try:
            value = _KEYRING.get_password(SERVICE_NAME, account)
            if value:
                return value
        except Exception as exc:
            _log.warning("keyring read failed for %s, falling through to DB: %s", account, exc)
    # Fallback / migration path.
    return (db_get_setting(_db_key_for(account), "") or "").strip()


def set_secret(account: str, value: str) -> None:
    """Store or update. Empty value deletes the entry."""
    value = (value or "").strip()
    if not value:
        delete_secret(account)
        return
    if _KEYRING_OK and _KEYRING is not None:
        try:
            _KEYRING.set_password(SERVICE_NAME, account, value)
            # Clear any stale DB-fallback copy so we don't leave the secret
            # in two places.
            db_set_setting(_db_key_for(account), "")
            return
        except Exception as exc:
            _log.warning("keyring write failed for %s, storing in DB instead: %s", account, exc)
    db_set_setting(_db_key_for(account), value)


def delete_secret(account: str) -> None:
    if _KEYRING_OK and _KEYRING is not None:
        try:
            _KEYRING.delete_password(SERVICE_NAME, account)
        except Exception:
            # delete_password raises if the entry doesn't exist; that's fine.
            pass
    db_set_setting(_db_key_for(account), "")


def migrate_db_to_keyring() -> int:
    """Push any DB-stored secrets into keyring, then clear the DB rows.

    Returns the number of secrets migrated. Safe to call on every startup
    (idempotent and silent when there's nothing to do).
    """
    if not _KEYRING_OK or _KEYRING is None:
        return 0
    migrated = 0
    for account, db_key in _ACCOUNTS.items():
        db_value = (db_get_setting(db_key, "") or "").strip()
        if not db_value:
            continue
        try:
            existing = _KEYRING.get_password(SERVICE_NAME, account)
        except Exception:
            existing = None
        if existing:
            # Keyring already has a value, just clear the DB fallback.
            db_set_setting(db_key, "")
            continue
        try:
            _KEYRING.set_password(SERVICE_NAME, account, db_value)
            db_set_setting(db_key, "")
            migrated += 1
            _log.info("migrated %s from DB to keyring", account)
        except Exception as exc:
            _log.warning("migration of %s failed: %s", account, exc)
    return migrated
