import json
import pytest

import nor
from crawler import save_page
from engine import investigate, search, sync_index, words
from intelligence import Plan, Synthesis
from language_quality import LocalizedText, wrong_language
from networks import requested_network
from ranking import focus_terms


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "research.db"))
    return nor.database


def seed(db, url, text):
    save_page(db, {"url": url, "title": "Privacy", "body": text, "links": []})


@pytest.mark.parametrize("question,scope", [
    ("sources I2P sur la confidentialité", "i2p"),
    ("Tor privacy", "tor"), ("compare Tor and I2P tunnels", "all"),
    ("privacy", "all"), ("sites .onion", "tor")])
def test_infer_network_scope(question, scope):
    assert requested_network(question) == scope
    assert requested_network(question, "all") == "all"


def test_all_question_facets_remain_tracked():
    topics = {name for name, _ in focus_terms("Que disent les sources I2P sur la confidentialité et les tunnels réseau ?", words)}
    assert topics == {"privacy", "network_tunnels"}
    assert "bananas" in {name for name, _ in focus_terms("privacy and bananas", words)}


def test_i2p_scope_filters_lexical_and_semantic_results_before_limits(db):
    seed(db, "http://i2p-projekt.i2p/", "Privacy source with tunnels.")
    seed(db, "http://" + "a" * 56 + ".onion/", "Tor privacy source with tunnels.")
    class Model:
        embed_model = "fixture"
        def embed(self, texts): return [[1.0, 0.0] for text in texts]
    with db() as connection:
        sync_index(connection)
        for row in connection.execute("SELECT id FROM chunks").fetchall():
            connection.execute("INSERT INTO embeddings VALUES (?,?,?)", (row[0], "fixture", "[1.0,0.0]"))
        result = search(connection, ["I2P privacy tunnels"], Model())[0]
        assert result and all(".i2p/" in source["url"] for source in result)
        assert len(search(connection, ["I2P privacy tunnels"], Model(), network_scope="all")[0]) == 2


class EnglishModel:
    chat_model = "fixture"
    embed_model = ""
    def __init__(self, repair=True):
        self.calls, self.repair = [], repair
    def structured(self, system, user, schema):
        self.calls.append(schema)
        if schema is Plan:
            return Plan(queries=["I2P privacy tunnels"])
        if schema is LocalizedText:
            return LocalizedText(texts=["La source décrit la confidentialité du réseau I2P." if self.repair
                else "The source describes privacy in the I2P network."])
        source = json.loads(user)["sources"][0]
        return Synthesis.model_validate({"claims": [{
            "text": "The source describes privacy in the I2P network.",
            "evidence": [{"source_id": source["source_id"], "quote": source["excerpt"]}]}], "gaps": []})


def test_repairs_french_answer_preserves_quotes_and_reports_missing_tunnels(db):
    quote = "The I2P source describes privacy protection for its users."
    seed(db, "http://i2p-projekt.i2p/", quote)
    model = EnglishModel()
    result = investigate(db, "Que disent les sources I2P sur la confidentialité et les tunnels réseau ?", "fr", model, use_cache=False)
    assert result["claims"][0]["text"].startswith("La source")
    assert result["claims"][0]["evidence"][0]["quote"] == quote
    assert "network_tunnels" in result["coverage"]["missing_query_topics"]
    assert any("tunnels réseau" in gap for gap in result["research_gaps"])
    assert "response_language_repaired" in result["warnings"]
    assert model.calls.count(LocalizedText) == 1
    assert result["network_scope"] == "i2p"


def test_failed_language_repair_does_not_present_english_as_french(db):
    seed(db, "http://i2p-projekt.i2p/", "The source describes privacy for all users.")
    model = EnglishModel(repair=False)
    result = investigate(db, "I2P confidentialité", "fr", model, use_cache=False)
    assert not result["claims"]
    assert "The source describes" not in result["answer"]
    assert "response_language_unavailable" in result["warnings"]
    assert model.calls.count(LocalizedText) == 1


def test_missing_synthesis_facet_is_reported_even_if_sources_contain_it(db):
    seed(db, "http://i2p-projekt.i2p/", "The source describes privacy and network tunnels for all users.")
    result = investigate(db, "I2P confidentialité et tunnels réseau", "fr", EnglishModel(), use_cache=False)
    assert result["coverage"]["missing_query_topics"] == []
    assert "network_tunnels" in result["coverage"]["unanswered_query_topics"]
    assert any("Point non traité" in gap for gap in result["research_gaps"])


def test_language_heuristic_is_bilingual_and_allows_neutral_names():
    assert wrong_language("The network provides privacy for its users.", "fr")
    assert wrong_language("Le réseau protège les données des utilisateurs.", "en")
    assert not wrong_language("La source décrit la confidentialité du réseau.", "fr")
    assert not wrong_language("I2P Tor", "fr")


def test_explicit_i2p_scope_never_falls_back_to_tor_when_empty(db):
    seed(db, "http://" + "a" * 56 + ".onion/", "The source describes privacy and tunnels.")
    result = investigate(db, "I2P privacy tunnels", "en", use_cache=False)
    assert not result["sources"]
    assert result["network_scope"] == "i2p"
