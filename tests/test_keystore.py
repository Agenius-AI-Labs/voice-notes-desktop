"""Keystore tests.

The keystore module is imported once at process start and caches whether
keyring is available. To exercise both paths cleanly we drive it through
its public API and let the runtime keyring backend (or lack of one)
decide the path. On CI there's no GNOME Keyring / Credential Manager, so
the DB fallback exercises itself naturally.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def keystore(isolated_data_dir):
    # Reload keystore so it picks up the reloaded db module from the fixture.
    import voice_notes.core.keystore as ks
    importlib.reload(ks)
    return ks


def test_set_then_get_roundtrip(keystore):
    keystore.set_secret("openai", "sk-test-123")
    assert keystore.get_secret("openai") == "sk-test-123"


def test_get_missing_returns_empty(keystore):
    assert keystore.get_secret("anthropic") == ""


def test_empty_value_deletes(keystore):
    keystore.set_secret("openai", "sk-keep")
    assert keystore.get_secret("openai") == "sk-keep"
    keystore.set_secret("openai", "")
    assert keystore.get_secret("openai") == ""


def test_delete_secret(keystore):
    keystore.set_secret("openai", "sk-x")
    keystore.delete_secret("openai")
    assert keystore.get_secret("openai") == ""


def test_unknown_account_namespaced_in_db(keystore, isolated_data_dir):
    """Unknown account names get a 'secret_<name>' DB key when keyring is
    unavailable, so they don't collide with the canonical settings."""
    keystore.set_secret("custom-thing", "val")
    if not keystore.keyring_available():
        # DB-fallback path; verify the namespaced key.
        assert isolated_data_dir.db_get_setting("secret_custom-thing", "") == "val"
    assert keystore.get_secret("custom-thing") == "val"


def test_migration_pushes_db_to_keyring_when_available(keystore, isolated_data_dir):
    # Seed the DB with a stale value as if from a pre-keyring install.
    isolated_data_dir.db_set_setting("openai_api_key", "sk-legacy")
    migrated = keystore.migrate_db_to_keyring()
    if keystore.keyring_available():
        assert migrated >= 1
        # DB row should now be empty.
        assert isolated_data_dir.db_get_setting("openai_api_key", "") == ""
        # Keyring (or fallback) should have the value.
        assert keystore.get_secret("openai") == "sk-legacy"
    else:
        # No keyring backend: migration is a no-op and the DB stays as-is.
        assert migrated == 0
        assert isolated_data_dir.db_get_setting("openai_api_key", "") == "sk-legacy"
