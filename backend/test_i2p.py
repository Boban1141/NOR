import json
import pytest

import manage
import nor
from crawler import CollectionError, fetch_page
from networks import network, transport_proxy
from test_engine import FakeResponse, fake_session
from test_safe_redirects import redirect, transport


@pytest.mark.parametrize("url", ["http://i2p-projekt.i2p/", "http://i2pforum.i2p/", "http://" + "a" * 52 + ".b32.i2p/"])
def test_i2p_sources_are_validated(url):
    assert nor.validate_source(url) == url
    assert network(url) == "i2p"


@pytest.mark.parametrize("url", ["http://example.com/", "http://example.i2p.com/", "http://127.0.0.1/",
    "http://user:pass@example.i2p/", "http://proxy.i2p/", "http://sub.proxy.i2p/",
    "http://short.b32.i2p/", "http://example.i2p:7657/", "http://-bad.i2p/",
    "http://example.i2p/?i2paddresshelper=untrusted", "http://example.i2p/#fragment"])
def test_i2p_rejects_non_darknet_and_proxy_control_targets(url):
    with pytest.raises(ValueError):
        nor.validate_source(url)


def test_i2p_fetch_uses_local_http_proxy_without_direct_dns(monkeypatch):
    monkeypatch.setenv("NOR_I2P_PROXY", "http://127.0.0.1:4444")
    monkeypatch.setenv("NOR_TOR_PROXY", "invalid-tor-value")
    calls = fake_session(monkeypatch, FakeResponse(b"<p>Public I2P source text.</p>"))
    result = fetch_page("http://i2p-projekt.i2p/", nor.validate_source)
    assert "Public I2P" in result["body"]
    assert calls[0][1]["proxies"] == {"http": "http://127.0.0.1:4444", "https": "http://127.0.0.1:4444"}
    assert calls[0][2] is False


@pytest.mark.parametrize("proxy", ["http://remote.example:4444", "socks5h://127.0.0.1:4444",
    "http://user:secret@127.0.0.1:4444", "http://127.0.0.1:4444/?target=example.com"])
def test_i2p_proxy_requires_local_endpoint_without_credentials(monkeypatch, proxy):
    monkeypatch.setenv("NOR_I2P_PROXY", proxy)
    with pytest.raises(ValueError):
        transport_proxy("http://i2p-projekt.i2p/")


def test_i2p_redirect_to_clearnet_or_tor_is_never_followed(monkeypatch):
    for target in ("https://example.com/", "http://" + "a" * 56 + ".onion/"):
        calls = transport(monkeypatch, [redirect(target)])
        with pytest.raises(CollectionError):
            fetch_page("http://i2p-projekt.i2p/", nor.validate_source, max_redirects=2)
        assert len(calls) == 1


def test_i2p_catalogue_separate_and_network_mismatch_rejected(tmp_path, monkeypatch):
    assert all(network(url) == "i2p" for url in nor.sources("i2p"))
    assert all(network(url) == "tor" for url in nor.sources("tor"))
    path = tmp_path / "i2p.json"
    path.write_text('["http://' + 'a' * 56 + '.onion/"]', encoding="utf-8")
    monkeypatch.setenv("NOR_I2P_SOURCES", str(path))
    with pytest.raises(ValueError, match="wrong_network"):
        nor.sources("i2p")


def test_existing_configuration_gets_i2p_default_without_overwrite(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"chat_model": "installed-model"}), encoding="utf-8")
    before = path.read_bytes()
    config = manage.load_config(path)
    assert config["i2p_proxy"] == "http://127.0.0.1:4444"
    assert config["chat_model"] == "installed-model"
    assert path.read_bytes() == before


def test_legacy_clearnet_page_cannot_be_used_for_answer(tmp_path, monkeypatch):
    from engine import sync_index, search
    monkeypatch.setenv("NOR_DB", str(tmp_path / "legacy.db"))
    with nor.database() as db:
        db.execute("INSERT INTO pages VALUES (?,?,?,?,?)", (
            "https://example.com/", "Privacy", "Privacy censorship evidence", "2026-11-16", "fixture"))
        sync_index(db)
        assert not search(db, ["privacy censorship"])[0]


def test_mixed_catalogue_can_retrieve_i2p_evidence(tmp_path, monkeypatch):
    from crawler import save_page
    from engine import sync_index, search
    monkeypatch.setenv("NOR_DB", str(tmp_path / "i2p.db"))
    save_page(nor.database, {"url": "http://i2p-projekt.i2p/", "title": "Privacy", "body": "I2P privacy and censorship evidence.", "links": []})
    with nor.database() as db:
        sync_index(db)
        assert search(db, ["privacy censorship"])[0][0]["url"] == "http://i2p-projekt.i2p/"
