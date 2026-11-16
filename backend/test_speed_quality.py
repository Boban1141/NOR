import hashlib
import json
import os
from pathlib import Path
import pytest

import nor
from engine import investigate, sync_index, search, query_variants
from intelligence import Plan, Synthesis
from ranking import focus_terms, focused_window
from engine import words
from response_cache import ResponseCache


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "quality.db"))
    return nor.database


def add(db, text, path="/fr/evidence", title="Evidence"):
    url = "http://" + "a" * 56 + ".onion" + path
    with db() as connection:
        connection.execute("DELETE FROM pages WHERE url=?", (url,))
        connection.execute("INSERT INTO pages VALUES (?,?,?,?,?)", (url, title, text, "2026-11-15T00:00:00Z", hashlib.sha256(text.encode()).hexdigest()))
    return url


class Model:
    chat_model = "quality-fixture"
    embed_model = ""
    def __init__(self): self.calls = []
    def structured(self, system, user, schema):
        self.calls.append(schema)
        if schema is Plan: return Plan(queries=["privacy censorship"])
        source = json.loads(user)["sources"][0]
        return Synthesis.model_validate({"claims": [{"text": "La source décrit la confidentialité et la censure.", "evidence": [{"source_id": source["source_id"], "quote": source["excerpt"][:200]}]}], "gaps": []})


def test_balanced_profile_uses_one_chat_call_when_evidence_covers_question(db):
    add(db, "La vie privée est protégée. Les services onion permettent de contourner la censure.")
    model = Model()
    result = investigate(db, "vie privée et censure", "fr", model, use_cache=False)
    assert model.calls == [Synthesis]
    assert result["mode"] == "grounded_synthesis"
    assert not result["capabilities"]["ai_query_planning_used"]


def test_repeated_answer_is_cached_and_corpus_change_invalidates_it(db):
    add(db, "La vie privée est protégée. Les services onion limitent la censure.")
    model = Model()
    first = investigate(db, "vie privée et censure", "fr", model)
    second = investigate(db, "vie privée et censure", "fr", model)
    assert first["mode"] == "grounded_synthesis"
    assert second["cache"]["hit"]
    assert len(model.calls) == 1
    assert first["run_id"] != second["run_id"]
    second["sources"].clear()
    third = investigate(db, "vie privée et censure", "fr", model)
    assert third["sources"], "Callers must not mutate the cached value"
    add(db, "Nouveau texte sur la vie privée et la censure, distinct du premier contenu.")
    changed = investigate(db, "vie privée et censure", "fr", model)
    assert not changed["cache"]["hit"]
    assert len(model.calls) == 2


def test_expired_and_evicted_cache_entries_are_not_returned():
    now = [0.0]
    cache = ResponseCache(capacity=1, ttl=5, clock=lambda: now[0])
    cache.put("one", {"duration_ms": 500})
    cache.put("two", {"duration_ms": 600})
    assert cache.get("one") is None
    now[0] = 6
    assert cache.get("two") is None


def test_query_focused_ranking_prefers_both_topics_to_generic_membership(db):
    generic = add(db, "Join our community of volunteers. Donate to support privacy. Our community is inclusive.", path="/fr/community")
    relevant = add(db, "Les services onion réduisent la surveillance et contournent la censure. Ils protègent la vie privée.", path="/fr/onion-services")
    with db() as connection:
        sync_index(connection)
        result = search(connection, query_variants("Que disent les sources sur la vie privée et la censure ?"), language="fr")[0]
    assert result[0]["url"] == relevant
    assert set(result[0]["matched_query_topics"]) == {"privacy", "censorship"}
    assert len({source["url"] for source in result}) == 2


def test_focused_windows_preserve_original_text_and_hash(db):
    body = "Generic text about volunteers. " * 40 + "Les services onion protègent la vie privée et réduisent la censure." + " Trailing generic text." * 30
    add(db, body)
    with db() as connection:
        sync_index(connection)
        result = search(connection, ["vie privée et censure"])[0]
    for source in result:
        assert body[source["start_offset"]:source["end_offset"]] == source["excerpt"]
        assert hashlib.sha256(source["excerpt"].encode()).hexdigest() == source["content_sha256"]
    assert "censure" in result[0]["excerpt"]
    assert len(result[0]["excerpt"]) <= 700


def test_no_cache_flag_forces_new_synthesis(db):
    add(db, "Privacy protections can reduce censorship and surveillance in this source.")
    model = Model()
    investigate(db, "privacy censorship", "en", model)
    result = investigate(db, "privacy censorship", "en", model, use_cache=False)
    assert not result["cache"]["hit"]
    assert model.calls.count(Synthesis) == 2


def test_empty_corpus_is_not_cached_as_a_success(db):
    model = Model()
    first = investigate(db, "privacy censorship", "en", model)
    second = investigate(db, "privacy censorship", "en", model)
    assert first["sources"] == second["sources"] == []
    assert not second["cache"]["hit"]


def test_html_main_excludes_global_donation_banner(monkeypatch):
    from test_engine import FakeResponse, fake_session
    from crawler import fetch_page
    body = b'<html><title>Privacy</title><header>Donate now!</header><main><p>Privacy and censorship evidence.</p></main></html>'
    fake_session(monkeypatch, FakeResponse(body))
    page = fetch_page("http://" + "a" * 56 + ".onion/", nor.validate_source)
    assert "Donate" not in page["body"]
    assert "Privacy and censorship" in page["body"]


def test_crawler_prioritizes_topic_pages_before_language_switches(monkeypatch):
    from test_engine import FakeResponse, fake_session
    from crawler import fetch_page
    body = b'<a href="/de/">German</a><a href="/fr/">French</a><a href="/onion-services/">Onions</a>'
    fake_session(monkeypatch, FakeResponse(body))
    page = fetch_page("http://" + "a" * 56 + ".onion/", nor.validate_source)
    assert page["links"][0].endswith("/onion-services/")


def test_privacy_question_rejects_membership_claim_and_missing_censorship_support():
    from ranking import filter_topic_claims
    topics = focus_terms("vie privée et censure", words)
    quote = "The privacy policy explains personal data protection."
    claims = [
        {"text": "The community has many contributors.", "evidence": [{"quote": quote}]},
        {"text": "The service defeats censorship.", "evidence": [{"quote": quote}]},
        {"text": "The policy covers privacy.", "evidence": [{"quote": quote}]},
    ]
    accepted, rejected = filter_topic_claims(claims, topics)
    assert accepted == [claims[2]]
    assert rejected == 2


def test_missing_question_topic_is_not_hidden_by_successful_retrieval(db):
    add(db, "This policy describes privacy protection and personal data handling.")
    result = investigate(db, "privacy and censorship", "en", Model(), use_cache=False)
    assert "censorship" in result["coverage"]["missing_query_topics"]
    assert any("censorship" in gap for gap in result["research_gaps"])
    assert not result["claims"], "A quote about privacy alone must not support a censorship claim"
