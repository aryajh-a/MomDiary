"""Unit tests for Argon2id password hasher service — feature 006 T014."""

from __future__ import annotations

import pytest

from momdiary.auth.hasher import PasswordHasherService, get_password_hasher


def test_hash_then_verify_roundtrip() -> None:
    svc = PasswordHasherService()
    pw = "Pa55word!correct"
    h = svc.hash(pw)
    assert h.startswith("$argon2id$"), h
    assert svc.verify(h, pw) is True


def test_verify_returns_false_on_wrong_password() -> None:
    svc = PasswordHasherService()
    h = svc.hash("Pa55word!secret")
    assert svc.verify(h, "Pa55word!nope") is False


def test_verify_returns_false_on_garbage_hash() -> None:
    svc = PasswordHasherService()
    assert svc.verify("not-a-hash", "anything") is False


def test_dummy_verify_is_safe_to_call() -> None:
    PasswordHasherService().dummy_verify()  # no raise


def test_get_password_hasher_is_singleton() -> None:
    assert get_password_hasher() is get_password_hasher()


def test_hash_each_call_uses_fresh_salt() -> None:
    svc = PasswordHasherService()
    a = svc.hash("Pa55word!same")
    b = svc.hash("Pa55word!same")
    assert a != b
