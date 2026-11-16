import hashlib
import json
import math
import pytest
from pydantic import ValidationError

import nor
from crawler import crawl, fetch_page
from engine import investigate, passages, sync_index, index_embeddings, search
from intelligence import ModelUnavailable, Ollama, Plan, Synthesis, vector


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "engine.db"))
    monkeypatch.delenv("NOR_CHAT_MODEL", raising=False)
    monkeypatch.delenv("NOR_EMBED_MODEL", raising=False)
    return nor.database


def seed(database, body, host="a", title="Research", path="/"):
    url = "http://" + host * 56 + ".onion" + path
    with database() as db:
        db.execute("DELETE FROM pages WHERE url=?", (url,))
        db.execute("INSERT INTO pages VALUES (?,?,?,?,?)", (url, title, body, "2026-11-15T20:00:00Z", hashlib.sha256(body.encode()).hexdigest()))
    return url


def test_cross_language_origins_retrieval(database):
    seed(database, "Modern human origins are discussed using fossil and genetic evidence.")
    seed(database, "A catalogue about gardens and furniture.", host="b")
    result = investigate(database, "Qui est à l’origine des humains ?", "fr")
    assert len(result["sources"]) == 1
    assert "human origins" in result["sources"][0]["excerpt"]
    assert not result["capabilities"]["semantic_search_used"]
    assert not result["verified"]


def test_chunk_offsets_and_overlap_preserve_end():
    text = " ".join("word" + str(i) for i in range(1000))
    chunks = list(passages(text))
    assert len(chunks) > 1
    assert chunks[-1][1] == len(text)
    assert all(text[start:end] == body for start, end, body in chunks)
    assert chunks[1][0] < chunks[0][1]


def test_matching_passage_in_long_page(database):
    seed(database, "gardening plants " * 500 + " UNIQUE_IDENTIFIER_90210 is the relevant passage. " + "plants " * 100)
    result = investigate(database, "UNIQUE_IDENTIFIER_90210", "en")
    assert "UNIQUE_IDENTIFIER_90210" in result["sources"][0]["excerpt"]
    assert len(result["sources"][0]["excerpt"]) <= 1500


def test_index_updates_remove_stale_passages_and_embeddings(database):
    url = seed(database, "The first document discusses fossil evidence.")
    with database() as db:
        sync_index(db)
        identifier = db.execute("SELECT id FROM chunks").fetchone()[0]
        db.execute("INSERT INTO embeddings VALUES (?,?,?)", (identifier, "model", "[1,0]"))
    seed(database, "The updated document discusses housing.")
    with database() as db:
        sync_index(db)
        assert db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
        assert not search(db, ["fossil"])[0]
        assert search(db, ["housing"])[0]
        db.execute("DELETE FROM pages WHERE url=?", (url,))
        sync_index(db)
        assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0


def test_source_diversity_and_copies_are_not_independent(database):
    text = "fraud evidence " * 500
    seed(database, text, path="/one")
    seed(database, text, host="b", path="/copy")
    seed(database, "fraud evidence from another publisher", host="c")
    result = investigate(database, "fraud evidence", "en")
    from collections import Counter
    from urllib.parse import urlsplit
    hosts = Counter(urlsplit(item["url"]).hostname for item in result["sources"])
    assert max(hosts.values()) <= 2
    assert len({item["content_sha256"] for item in result["sources"]}) == len(result["sources"])
    assert result["coverage"]["independence_established"] is False


class FakeModel:
    chat_model = "fixture-chat"
    embed_model = ""

    def __init__(self, answer=None, fail=False):
        self.answer = answer
        self.fail = fail
        self.calls = []

    def structured(self, system, user, schema):
        self.calls.append((system, json.loads(user)))
        if self.fail:
            raise ModelUnavailable("offline")
        if schema is Plan:
            return Plan(queries=["fraud document evidence"])
        return Synthesis.model_validate(self.answer)


def test_grounded_synthesis_retains_verbatim_evidence(database):
    body = "This source reports suspicious document alterations, without independent confirmation."
    seed(database, body)
    model = FakeModel({"claims": [{"text": "The source reports document alterations.", "evidence": [{"source_id": "S1", "quote": body}]}], "gaps": ["Is there an independent confirmation?"]})
    result = investigate(database, "document alterations", "en", model)
    assert result["mode"] == "grounded_synthesis"
    assert "[S1]" in result["answer"]
    assert result["claims"][0]["evidence"][0]["quote"] == body
    assert result["claims"][0]["verification"] == "quoted_source_only"
    assert result["verified"] is False
    assert result["research_gaps"]
    assert "UNTRUSTED DATA" in model.calls[-1][0]


@pytest.mark.parametrize("identifier,quote", [("S8", "A completely invented quote about evidence."), ("S1", "A completely invented quote about evidence.")])
def test_fabricated_reference_or_quote_is_rejected(database, identifier, quote):
    seed(database, "This document describes fraud evidence for investigators.")
    model = FakeModel({"claims": [{"text": "An unsupported answer must not appear.", "evidence": [{"source_id": identifier, "quote": quote}]}], "gaps": []})
    result = investigate(database, "fraud", "en", model)
    assert not result["claims"]
    assert "unsupported_citations_rejected" in result["warnings"]
    assert "unsupported answer" not in result["answer"]


def test_provider_failure_falls_back_without_inventing(database):
    seed(database, "This document describes fraud evidence for investigators.")
    result = investigate(database, "fraud", "en", FakeModel(fail=True))
    assert result["sources"]
    assert result["mode"] == "advanced_extractive"
    assert "synthesis_unavailable" in result["warnings"]
    assert not result["capabilities"]["synthesis_used"]
    assert result["diagnostics"] == [{"stage": "synthesis", "code": "model_error"}]


def test_empty_catalogue_does_not_call_synthesis(database):
    model = FakeModel()
    result = investigate(database, "origins", "en", model)
    assert not result["sources"]
    assert len(model.calls) == 1


class SemanticModel:
    chat_model = ""
    embed_model = "fixture-embedding"

    def embed(self, texts):
        return [[1.0, 0.0] for text in texts]


def test_semantic_search_can_retrieve_without_shared_words(database):
    seed(database, "A historical account of ancient populations.")
    model = SemanticModel()
    with database() as db:
        assert index_embeddings(db, model) == 1
        assert index_embeddings(db, model) == 0
    result = investigate(database, "palaeogenomics", "en", model)
    assert result["capabilities"]["semantic_search_used"]
    assert result["sources"][0]["retrieval_methods"] == ["semantic"]
    assert result["mode"] == "hybrid_extractive"


@pytest.mark.parametrize("value", [[], [0, 0], [math.nan], [math.inf], [True], ["1"]])
def test_invalid_vectors_rejected(value):
    with pytest.raises(ModelUnavailable):
        vector(value)


def test_model_endpoint_requires_tls_outside_localhost(monkeypatch):
    monkeypatch.setenv("NOR_OLLAMA_URL", "http://remote.example")
    with pytest.raises(ModelUnavailable):
        Ollama()


def test_run_log_excludes_question_and_content(database):
    seed(database, "Private source text about fraud evidence.")
    result = investigate(database, "unique_private_question", "en")
    with database() as db:
        record = dict(db.execute("SELECT * FROM research_runs WHERE id=?", (result["run_id"],)).fetchone())
    assert "unique_private_question" not in json.dumps(record)
    assert "Private source text" not in json.dumps(record)


def test_crawler_enforces_scope_and_depth(database):
    root = "http://" + "a" * 56 + ".onion/"
    external = "http://" + "b" * 56 + ".onion/"
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        return {"url": url, "title": "Fixture", "body": "Collected fixture content.", "links": [root + "child", external, "http://127.0.0.1/", root + "grandchild"] if url == root else [root + "beyond-depth"]}
    result = crawl([root], nor.validate_source, database, max_pages=10, max_depth=1, fetcher=fetch)
    assert set(visits) == {root, root + "child", root + "grandchild"}
    assert result["collected"] == 3
    assert external not in visits


def test_crawler_page_limit_and_partial_failure(database):
    root = "http://" + "a" * 56 + ".onion/"
    def fetch(url, validate, budget):
        if url.endswith("bad"):
            raise ValueError("unavailable")
        return {"url": url, "title": "Fixture", "body": "Content", "links": [root + "bad", root + "extra"]}
    result = crawl([root], nor.validate_source, database, max_pages=2, fetcher=fetch)
    assert result["attempted"] == 2
    assert result["failed"] == 1
    assert result["budget_exhausted"]


def test_source_refresh_keeps_prior_versions(database):
    from crawler import save_page
    page = {"url": "http://" + "a" * 56 + ".onion/", "title": "Source", "body": "First text", "links": []}
    save_page(database, page)
    save_page(database, dict(page, body="Changed text"))
    with database() as db:
        assert db.execute("SELECT COUNT(*) FROM page_versions").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1


def test_ollama_structured_contract_and_invalid_output(monkeypatch):
    monkeypatch.setenv("NOR_CHAT_MODEL", "fixture")
    model = Ollama()
    calls = []
    def post(path, payload):
        calls.append((path, payload))
        return {"message": {"content": '{"queries":["human origins"]}'}}
    monkeypatch.setattr(model, "post", post)
    assert model.structured("system", "question", Plan).queries == ["human origins"]
    assert calls[0][0] == "/api/chat"
    assert calls[0][1]["format"] == Plan.model_json_schema()
    assert calls[0][1]["stream"] is False
    monkeypatch.setattr(model, "post", lambda *args: {"message": {"content": '{"queries":[],"tool":"execute"}'}})
    with pytest.raises(ModelUnavailable):
        model.structured("system", "question", Plan)


def test_embedding_dimension_change_degrades_to_lexical(database):
    seed(database, "fraud document evidence")
    model = SemanticModel()
    with database() as db:
        index_embeddings(db, model)
    model.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    result = investigate(database, "fraud", "en", model)
    assert result["sources"]
    assert "semantic_search_unavailable" in result["warnings"]
    assert not result["capabilities"]["semantic_search_used"]
    assert result["sources"][0]["retrieval_methods"] == ["lexical"]


def test_no_made_up_source_without_evidence_schema():
    with pytest.raises(ValidationError):
        Synthesis.model_validate({"claims": [{"text": "Unsupported speculation here.", "evidence": []}], "gaps": []})


class FakeResponse:
    def __init__(self, content, status=200, content_type="text/html"):
        self.content = content
        self.status_code = status
        self.headers = {"Content-Type": content_type}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, size):
        for index in range(0, len(self.content), size):
            yield self.content[index:index + size]


def fake_session(monkeypatch, response):
    calls = []
    class Session:
        trust_env = True
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            calls.append((url, kwargs, self.trust_env))
            return response
    monkeypatch.setattr("crawler.requests.Session", Session)
    return calls


def test_tor_transport_and_html_extraction(monkeypatch):
    monkeypatch.delenv("NOR_TOR_PROXY", raising=False)
    root = "http://" + "a" * 56 + ".onion/"
    body = b'<html><title>Evidence</title><script>steal_secrets()</script><p>Useful source text.</p><a href="/next">Next</a><a href="http://127.0.0.1">Forbidden</a></html>'
    calls = fake_session(monkeypatch, FakeResponse(body))
    page = fetch_page(root, nor.validate_source)
    assert "steal_secrets" not in page["body"]
    assert page["links"] == [root + "next"]
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["proxies"]["http"].startswith("socks5h://")
    assert calls[0][2] is False


@pytest.mark.parametrize("response", [FakeResponse(b"", status=302), FakeResponse(b"binary", content_type="application/octet-stream"), FakeResponse(b"x" * 1_000_001)])
def test_tor_rejects_redirects_binary_and_oversized_pages(monkeypatch, response):
    monkeypatch.delenv("NOR_TOR_PROXY", raising=False)
    fake_session(monkeypatch, response)
    with pytest.raises(ValueError):
        fetch_page("http://" + "a" * 56 + ".onion/", nor.validate_source)


def test_second_research_round_can_find_competing_source(database):
    seed(database, "The alpha signal is described by the first source.")
    expected = seed(database, "The counterargument archive describes a competing interpretation.", host="b")
    class FollowupModel(FakeModel):
        def structured(self, system, user, schema):
            payload = json.loads(user)
            if schema is Plan:
                return Plan(queries=["counterargument archive"] if "previous_queries" in payload else ["alpha signal"])
            return Synthesis(claims=[], gaps=["Which interpretation is supported independently?"])
    result = investigate(database, "alpha signal", "en", FollowupModel(), profile="deep")
    assert result["capabilities"]["research_rounds"] == 2
    assert expected in [item["url"] for item in result["sources"]]
    assert result["coverage"]["independence_established"] is False


@pytest.mark.parametrize("exception_name,expected", [("ReadTimeout", "model_timeout"), ("ConnectionError", "model_connection_error"), ("WrappedTimeout", "model_timeout")])
def test_model_transport_reports_safe_error_category(monkeypatch, exception_name, expected):
    import requests
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            if exception_name == "WrappedTimeout":
                from urllib3.exceptions import ReadTimeoutError
                raise requests.ConnectionError(ReadTimeoutError(None, None, "sensitive-provider-details"))
            raise getattr(requests, exception_name)("sensitive-provider-details")
    monkeypatch.setattr("intelligence.requests.Session", Session)
    with pytest.raises(ModelUnavailable) as caught:
        Ollama().post("/api/chat", {})
    assert str(caught.value) == expected
    assert "sensitive" not in str(caught.value)


def test_truncated_model_json_is_reported_explicitly(monkeypatch):
    monkeypatch.setenv("NOR_CHAT_MODEL", "fixture")
    model = Ollama()
    monkeypatch.setattr(model, "post", lambda *args: {"done_reason": "length", "message": {"content": '{"queries":['}})
    with pytest.raises(ModelUnavailable, match="model_output_truncated"):
        model.structured("system", "question", Plan)
