# CAMINHO: backend/tests/test_login_profile_complete.py
"""`AuthService.login` informa `profile_complete` sem nunca falhar o login por causa disso
(spec `profile-onboarding-gate`, requisito "Backend informa se o cadastro está completo no login")."""

import asyncio
from types import SimpleNamespace

import pytest

import app.auth.auth_service as auth_service_module
from app.auth.auth_service import AuthService, _has_profile

USER_ID = "2198e4ab-14b4-454e-a0c8-502aa68bb8a6"


class _Query:
    """Imita a cadeia `.table().select().eq().limit().execute()` do cliente Supabase."""

    def __init__(self, tables):
        self._tables = tables
        self._name = None

    def table(self, name):
        self._name = name
        return self

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        value = self._tables[self._name]
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(data=value)


def _patch_admin(monkeypatch, tables):
    monkeypatch.setattr(auth_service_module, "supabase_admin", _Query(tables))


def test_has_profile_true_when_row_exists(monkeypatch):
    _patch_admin(monkeypatch, {"user_profiles": [{"user_id": USER_ID}]})
    assert _has_profile(USER_ID) is True


def test_has_profile_false_when_no_row(monkeypatch):
    _patch_admin(monkeypatch, {"user_profiles": []})
    assert _has_profile(USER_ID) is False


def test_has_profile_false_and_logged_when_query_fails(monkeypatch, caplog):
    _patch_admin(monkeypatch, {"user_profiles": RuntimeError("supabase fora do ar")})
    with caplog.at_level("ERROR", logger="AuthService"):
        assert _has_profile(USER_ID) is False
    assert "user_profiles" in caplog.text


def _fake_auth_client():
    session = SimpleNamespace(access_token="token123")
    user = SimpleNamespace(id=USER_ID, email="ffasti.iot01@gmail.com")
    auth = SimpleNamespace(sign_in_with_password=lambda _creds: SimpleNamespace(user=user, session=session))
    return SimpleNamespace(auth=auth)


@pytest.mark.parametrize("profiles, expected", [
    ([], False),
    ([{"user_id": USER_ID}], True),
    (RuntimeError("falha"), False),
])
def test_login_includes_profile_complete(monkeypatch, profiles, expected):
    monkeypatch.setattr(auth_service_module, "_fresh_auth_client", _fake_auth_client)
    _patch_admin(monkeypatch, {
        "users": [{"id": USER_ID, "email": "ffasti.iot01@gmail.com", "role": "user"}],
        "user_profiles": profiles,
    })
    result = asyncio.run(AuthService.login("ffasti.iot01@gmail.com", "senha"))
    assert result["profile_complete"] is expected
    assert result["access_token"] == "token123"
