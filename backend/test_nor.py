import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import nor
from pydantic import ValidationError


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("NOR_ACCESS_TOKEN", "x" * 40)


def test_auth_and_empty_catalogue(isolated_db):
    with pytest.raises(HTTPException) as exc:
        nor.authorize(None)
    assert exc.value.status_code == 401
    nor.authorize(HTTPAuthorizationCredentials(scheme="Bearer", credentials="x" * 40))
    result = nor.research(nor.Question(question="humains"))
    assert result["sources"] == []
    assert result["verified"] is False


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://example.com", "file:///etc/passwd", "http://short.onion", "http://user@" + "a" * 56 + ".onion", "http://" + "a" * 56 + ".onion:8080"])
def test_refuse_non_onion_and_credentials(url):
    with pytest.raises(ValueError):
        nor.validate_source(url)


def test_search_deduplicates_without_marking_verified(isolated_db):
    with nor.database() as db:
        for suffix in ("a", "b"):
            db.execute("INSERT INTO pages VALUES (?, ?, ?, ?, ?)", ("http://" + suffix * 56 + ".onion", "Origines", "Les humains et leurs origines", "2026-11-16T00:00:00Z", "same"))
    result = nor.research(nor.Question(question="humains"))
    assert len(result["sources"]) == 1
    assert "humains" in result["sources"][0]["excerpt"]
    assert result["verified"] is False


def test_no_direct_network_fallback(monkeypatch):
    monkeypatch.setenv("NOR_TOR_PROXY", "http://127.0.0.1:8080")
    with pytest.raises(ValueError, match="socks5h"):
        nor.collect("http://" + "a" * 56 + ".onion")


def test_english_empty_catalogue(isolated_db):
    result = nor.research(nor.Question(question="human origins", language="en"))
    assert result["answer"].startswith("I found no results")
    assert result["language"] == "en"
    assert not result["verified"]


def test_english_sources_keep_original_text(isolated_db):
    with nor.database() as db:
        db.execute("INSERT INTO pages VALUES (?, ?, ?, ?, ?)",
                   ("http://" + "a" * 56 + ".onion", "Origines", "Les humains et leurs origines", "2026-11-16T00:00:00Z", "unique"))
    result = nor.research(nor.Question(question="humains", language="en"))
    assert result["answer"].startswith("These excerpts")
    assert "humains" in result["sources"][0]["excerpt"]
    assert result["language"] == "en"


def test_unsupported_language_rejected():
    with pytest.raises(ValidationError):
        nor.Question(question="origins", language="es")


def test_empty_words_english_error(isolated_db):
    with pytest.raises(HTTPException) as exc:
        nor.research(nor.Question(question="???", language="en"))
    assert exc.value.detail == "The question must contain words."
