import json
import os
import sys
from types import SimpleNamespace

import pytest

import manage


@pytest.fixture
def local_state(tmp_path, monkeypatch):
    monkeypatch.setattr(manage, "ROOT", tmp_path)
    monkeypatch.setattr(manage, "CONFIG", tmp_path / "nor.local.json")
    monkeypatch.setattr(manage, "RUNTIME", tmp_path / ".runtime")
    monkeypatch.setattr(manage, "TOKEN", tmp_path / ".runtime" / "access-token")
    return tmp_path


def test_initialization_never_prints_or_overwrites_private_token(local_state, capsys):
    assert manage.main(["init", "--chat-model", "chat", "--embedding-model", "embed"]) == 0
    token = manage.read_token()
    assert len(token) >= 32
    assert token not in capsys.readouterr().out
    assert manage.main(["init"]) == 1
    assert manage.read_token() == token


@pytest.mark.parametrize("extra", [{"execute": "anything"}, {"ollama_url": "http://remote.example"}, {"model_timeout": True}, {"tor_proxy": "socks5://127.0.0.1:9050"}])
def test_invalid_local_configuration_rejected(local_state, extra):
    manage.CONFIG.write_text(json.dumps(manage.DEFAULTS | extra))
    with pytest.raises(ValueError):
        manage.load_config()


def test_doctor_requires_installed_models_and_preserves_tor_uncertainty(local_state, monkeypatch):
    manage.initialize("chat", "embedding")
    monkeypatch.setattr(manage.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(manage, "installed_model_names", lambda url: {"chat:latest", "embedding:latest"})
    monkeypatch.setattr(manage, "socks_responding", lambda url: True)
    report = manage.doctor()
    assert report["engine_prerequisites_met"]
    assert report["tor_network_verified"] is False
    assert report["indexed_passages"] == 0
    assert manage.read_token() not in json.dumps(report)


def test_doctor_does_not_equate_ollama_with_installed_models(local_state, monkeypatch):
    manage.initialize("chat", "embedding")
    monkeypatch.setattr(manage.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(manage, "installed_model_names", lambda url: set())
    monkeypatch.setattr(manage, "socks_responding", lambda url: False)
    report = manage.doctor()
    assert report["ollama_responding"]
    assert not report["chat_model_installed"]
    assert not report["engine_prerequisites_met"]
    assert len(report["blockers"]) == 3


def test_serve_is_loopback_only_and_uses_private_runtime(local_state, monkeypatch):
    manage.initialize("chat", "embedding")
    # Isolate environment changes from the other tests.
    for key in ("NOR_ACCESS_TOKEN", "NOR_DB", "NOR_SOURCES", "NOR_OLLAMA_URL", "NOR_CHAT_MODEL", "NOR_EMBED_MODEL", "NOR_TOR_PROXY", "NOR_MODEL_TIMEOUT", "NOR_MODEL_CONTEXT", "NOR_MODEL_OUTPUT_LIMIT"):
        monkeypatch.setenv(key, os.getenv(key, ""))
    calls = []
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *args, **kwargs: calls.append((args, kwargs))))
    assert manage.main(["serve", "--port", "8001"]) == 0
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["access_log"] is False
    assert calls[0][1]["workers"] == 1
    assert os.environ["NOR_ACCESS_TOKEN"] == manage.read_token()
    assert os.environ["NOR_DB"] == str(manage.RUNTIME / "nor.sqlite3")


def test_failure_does_not_echo_configured_secret(local_state, capsys):
    manage.CONFIG.write_text('{"unknown": "sensitive-value-not-for-output"}')
    assert manage.main(["doctor"]) == 1
    output = capsys.readouterr()
    assert "sensitive-value" not in output.out + output.err


def test_doctor_reports_missing_services_without_claiming_readiness(local_state, monkeypatch):
    monkeypatch.setattr(manage, "installed_model_names", lambda url: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(manage, "socks_responding", lambda url: (_ for _ in ()).throw(OSError("offline")))
    report = manage.doctor()
    assert not report["engine_prerequisites_met"]
    assert not report["configuration_exists"]
    assert not report["token_configured"]
    assert not report["ollama_responding"]
