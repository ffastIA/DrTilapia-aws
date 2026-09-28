# CAMINHO: backend/tests/test_database_secrets.py
"""Origem dos segredos em `app/database.py`: `.env` em desenvolvimento,
AWS Secrets Manager fora dele.

O módulo é re-executado a cada teste, com `boto3`, `load_dotenv` e
`create_client` simulados — nada aqui toca a AWS, o `.env` real ou o Supabase.
"""
import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

DATABASE_PY = Path(__file__).resolve().parent.parent / "app" / "database.py"

SECRET_VALUES = {
    "SUPABASE_URL": "https://from-secret.supabase.co",
    "SUPABASE_KEY": "anon-secret-value-123",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret-value-456",
    "OPENAI_API_KEY": "sk-secret-value-789",
}
ENV_KEYS = [*SECRET_VALUES, "ENVIRONMENT", "SECRET_ID", "AWS_REGION", "AWS_DEFAULT_REGION"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # setenv+delenv registra o estado original, para o pytest restaurá-lo ao
    # final mesmo quando o módulo escreve em os.environ por conta própria.
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "x")
        monkeypatch.delenv(key)


@pytest.fixture
def fake_boto3(monkeypatch):
    client = MagicMock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(SECRET_VALUES)}
    factory = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=factory))
    return SimpleNamespace(factory=factory, client=client)


def _load_database(monkeypatch, dotenv_values=None):
    """Executa app/database.py do zero. `dotenv_values` simula o conteúdo do `.env`."""

    def fake_load_dotenv(*args, **kwargs):
        import os

        for key, value in (dotenv_values or {}).items():
            os.environ.setdefault(key, value)  # como o load_dotenv real: sem override

    monkeypatch.setattr("dotenv.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("supabase.create_client", MagicMock())
    spec = importlib.util.spec_from_file_location("database_under_test", DATABASE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dev_reads_dotenv_even_when_environment_is_not_exported(monkeypatch, fake_boto3):
    dotenv = {**SECRET_VALUES, "SUPABASE_URL": "https://from-dotenv.supabase.co",
              "ENVIRONMENT": "development"}

    module = _load_database(monkeypatch, dotenv)

    assert module.SUPABASE_URL == "https://from-dotenv.supabase.co"
    assert module.secrets_source.startswith(".env")
    fake_boto3.factory.assert_not_called()


def test_production_loads_secrets_from_secrets_manager(monkeypatch, fake_boto3):
    module = _load_database(monkeypatch)

    assert module.SUPABASE_URL == SECRET_VALUES["SUPABASE_URL"]
    assert module.SUPABASE_SERVICE_ROLE_KEY == SECRET_VALUES["SUPABASE_SERVICE_ROLE_KEY"]
    fake_boto3.factory.assert_called_once_with("secretsmanager", region_name="sa-east-1")
    fake_boto3.client.get_secret_value.assert_called_once_with(SecretId="tilapia/backend")
    assert "Secrets Manager" in module.secrets_source


def test_production_secret_id_and_region_come_from_environment(monkeypatch, fake_boto3):
    monkeypatch.setenv("SECRET_ID", "outro/secret")
    monkeypatch.setenv("AWS_REGION", "us-east-2")

    _load_database(monkeypatch)

    fake_boto3.factory.assert_called_once_with("secretsmanager", region_name="us-east-2")
    fake_boto3.client.get_secret_value.assert_called_once_with(SecretId="outro/secret")


def test_secrets_manager_wins_over_stale_environment_value(monkeypatch, fake_boto3):
    monkeypatch.setenv("SUPABASE_URL", "https://stale-from-env-file.supabase.co")

    module = _load_database(monkeypatch)

    assert module.SUPABASE_URL == SECRET_VALUES["SUPABASE_URL"]


def test_production_fails_fast_with_clear_message_when_secret_unreadable(monkeypatch, fake_boto3):
    fake_boto3.client.get_secret_value.side_effect = RuntimeError("AccessDeniedException")
    monkeypatch.setenv("SECRET_ID", "tilapia/backend")

    with pytest.raises(RuntimeError) as exc:
        _load_database(monkeypatch)

    message = str(exc.value)
    assert "tilapia/backend" in message
    assert "sa-east-1" in message
    assert "AccessDeniedException" in message


def test_production_fails_when_boto3_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "boto3", None)  # força ImportError

    with pytest.raises(RuntimeError, match="Secrets Manager"):
        _load_database(monkeypatch)


def test_production_fails_when_secret_lacks_required_key(monkeypatch, fake_boto3):
    incomplete = {k: v for k, v in SECRET_VALUES.items() if k != "SUPABASE_SERVICE_ROLE_KEY"}
    fake_boto3.client.get_secret_value.return_value = {"SecretString": json.dumps(incomplete)}

    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY"):
        _load_database(monkeypatch)


def test_secret_values_never_reach_logs_or_errors(monkeypatch, fake_boto3, caplog):
    with caplog.at_level(logging.DEBUG):
        _load_database(monkeypatch)
    for value in SECRET_VALUES.values():
        assert value not in caplog.text

    fake_boto3.client.get_secret_value.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        _load_database(monkeypatch)
    for value in SECRET_VALUES.values():
        assert value not in str(exc.value)
