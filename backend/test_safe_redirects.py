import pytest

import nor
from crawler import CollectionError, fetch_page
from test_engine import FakeResponse


def transport(monkeypatch, responses):
    calls = []
    class Session:
        trust_env = True
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return responses.pop(0)
    monkeypatch.setattr("crawler.requests.Session", Session)
    monkeypatch.delenv("NOR_TOR_PROXY", raising=False)
    return calls


def redirect(location):
    response = FakeResponse(b"", status=301)
    response.headers["Location"] = location
    return response


def test_same_host_redirect_resolves_canonical_url_and_relative_links(monkeypatch):
    root = "https://" + "a" * 56 + ".onion/"
    calls = transport(monkeypatch, [redirect("/en/"), FakeResponse(b'<title>Source</title><p>Evidence</p><a href="child">Child</a>')])
    page = fetch_page(root, nor.validate_source, budget=30, max_redirects=2)
    assert page["url"] == root + "en/"
    assert page["links"] == [root + "en/child"]
    assert page["redirect_statuses"] == [301]
    assert len(calls) == 2
    assert all(call[1]["allow_redirects"] is False for call in calls)
    assert all(call[1]["proxies"]["https"].startswith("socks5h://") for call in calls)
    assert calls[0][1]["timeout"] == (8, 20)


@pytest.mark.parametrize("location,expected", [
    ("http://" + "a" * 56 + ".onion/en/", "redirect_tls_downgrade"),
    ("https://" + "b" * 56 + ".onion/", "redirect_other_host"),
    ("https://sub." + "a" * 56 + ".onion/", "redirect_other_host"),
    ("http://127.0.0.1/", "redirect_invalid_target"),
    ("https://user:password@" + "a" * 56 + ".onion/", "redirect_invalid_target"),
])
def test_unsafe_redirect_never_opens_second_connection(monkeypatch, location, expected):
    calls = transport(monkeypatch, [redirect(location)])
    with pytest.raises(CollectionError, match=expected):
        fetch_page("https://" + "a" * 56 + ".onion/", nor.validate_source, max_redirects=2)
    assert len(calls) == 1


def test_redirect_loop_stops_after_two_hops(monkeypatch):
    calls = transport(monkeypatch, [redirect("/"), redirect("/"), redirect("/")])
    with pytest.raises(CollectionError, match="redirect_same_host"):
        fetch_page("https://" + "a" * 56 + ".onion/", nor.validate_source, max_redirects=2)
    assert len(calls) == 3


def test_redirect_hops_share_one_page_budget(monkeypatch):
    calls = transport(monkeypatch, [redirect("/en/"), FakeResponse(b"Evidence")])
    clock = iter([0, 25, 25, 31])
    monkeypatch.setattr("crawler.time.monotonic", lambda: next(clock))
    with pytest.raises(CollectionError, match="page_time_limit"):
        fetch_page("https://" + "a" * 56 + ".onion/", nor.validate_source, budget=30, max_redirects=2)
    assert calls[1][1]["timeout"] == (5, 5)


def test_crawl_uses_safe_redirect_policy_and_reports_statuses(monkeypatch, tmp_path):
    from crawler import crawl
    monkeypatch.setenv("NOR_DB", str(tmp_path / "test.db"))
    root = "https://" + "a" * 56 + ".onion/"
    transport(monkeypatch, [redirect("/en/"), FakeResponse(b"<p>Public source evidence</p>")])
    result = crawl([root], nor.validate_source, nor.database, max_depth=0)
    assert result["collected"] == 1
    assert result["source_diagnostics"][0]["http_statuses"] == {"200": 1, "301": 1}
    with nor.database() as db:
        assert db.execute("SELECT url FROM pages").fetchone()[0] == root + "en/"
