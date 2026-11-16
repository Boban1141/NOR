import json
import pytest

import nor
from crawler import crawl, save_page
from engine import search, sync_index, words
from ranking import focus_terms
from source_catalog import select_seeds


def onion(letter):
    return "http://" + letter * 56 + ".onion/"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "collection.db"))
    return nor.database


def test_seed_selection_prefers_topics_and_different_operators():
    seeds = [onion(letter) for letter in "abcd"]
    entries = [{"url": url, "operator": group, "topics": topics} for url, group, topics in zip(
        seeds, ["Tor", "Tor", "News", "Rights"], [[], ["privacy", "censorship"], [], ["privacy"]])]
    selected = select_seeds(seeds, focus_terms("privacy censorship", words), entries, limit=3)
    assert selected == [seeds[1], seeds[3], seeds[2]]


def test_question_prioritizes_anchor_text_and_stays_in_scope(db):
    root, other = onion("a"), onion("b")
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        return {"url": url, "title": "Source", "body": "Source content", "links": [root + "sports", root + "article-42", other],
                "link_titles": {root + "article-42": "Vie privée et censure"}}
    result = crawl([root], nor.validate_source, db, max_pages=2, question="vie privée et censure", tokenizer=words, fetcher=fetch)
    assert visits == [root, root + "article-42"]
    assert result["query_guided"] and result["collected_hosts"] == 1
    assert other not in visits


def test_saved_links_reused_but_removed_hosts_never_fetched(db):
    root, external = onion("a"), onion("b")
    save_page(db, {"url": root, "title": "Source", "body": "Content", "links": [root + "privacy", external + "privacy"]})
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        return {"url": url, "title": "Source", "body": "Content", "links": []}
    crawl([root], nor.validate_source, db, max_pages=1, question="privacy", tokenizer=words, fetcher=fetch)
    assert visits == [root + "privacy"]


def test_query_collection_visits_other_host_before_second_page(db):
    roots = [onion("a"), onion("b")]
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        return {"url": url, "title": "Source", "body": "Content", "links": [url + "privacy"]}
    crawl(roots, nor.validate_source, db, max_pages=2, question="privacy", tokenizer=words, fetcher=fetch)
    assert visits == roots


def test_query_collection_respects_zero_depth_with_stored_links(db):
    root = onion("a")
    save_page(db, {"url": root, "title": "Source", "body": "Content", "links": [root + "privacy"]})
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        return {"url": url, "title": "Source", "body": "Content", "links": []}
    crawl([root], nor.validate_source, db, max_depth=0, question="privacy", tokenizer=words, fetcher=fetch)
    assert visits == [root]


def test_search_limits_same_operator_across_multiple_domains(db, tmp_path, monkeypatch):
    urls = [onion(letter) for letter in "abcd"]
    entries = [{"url": url, "operator": "Tor" if i < 3 else "Other"} for i, url in enumerate(urls)]
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setenv("NOR_SOURCE_REGISTRY", str(path))
    for i, url in enumerate(urls):
        save_page(db, {"url": url, "title": "Privacy", "body": "Privacy censorship evidence " + str(i), "links": []})
    with db() as connection:
        sync_index(connection)
        found = search(connection, ["privacy censorship"])[0]
    assert len(found) == 3
    assert urls[3] in [source["url"] for source in found[:2]]


def test_refresh_passes_question_and_reports_live_collection(db, monkeypatch):
    calls = []
    def collect(seeds, *args, **kwargs):
        calls.append((seeds, kwargs))
        return {"collected": 1, "failed": 0}
    monkeypatch.setattr(nor, "crawl", collect)
    result = nor.research(nor.Question(question="privacy censorship", refresh=True))
    assert calls[0][1]["question"] == "privacy censorship"
    assert calls[0][1]["max_pages"] == 10
    assert result["capabilities"]["live_search_used"]
    assert "new_pages_lexically_indexed_run_embed_for_semantics" in result["warnings"]
    assert "collection_ms" in result["timings"]


def test_result_limit_still_applies_with_many_operator_groups(db):
    for letter in "abcdefghijkl":
        save_page(db, {"url": onion(letter), "title": "Privacy", "body": "Privacy evidence " + letter, "links": []})
    with db() as connection:
        sync_index(connection)
        assert len(search(connection, ["privacy"], limit=8)[0]) == 8
