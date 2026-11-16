import hashlib
import json
from urllib.parse import urlsplit

import pytest
import requests

import manage
import nor
from crawler import CollectionError, crawl, failure_details, fetch_page
from test_engine import FakeResponse, fake_session


@pytest.mark.parametrize("error,expected", [
    (requests.exceptions.ProxyError("secret-token"), "proxy_error"),
    (requests.exceptions.SSLError("private-source"), "tls_error"),
    (requests.ReadTimeout("private-source"), "network_timeout"),
    (requests.ConnectionError("secret-token"), "connection_error"),
    (requests.RequestException("private-source"), "request_error"),
    (ValueError("secret-token"), "page_rejected"),
])
def test_failure_codes_do_not_echo_exception_text(error, expected):
    assert failure_details(error) == (expected, None)


@pytest.mark.parametrize("status,location,code", [
    (404, None, "http_error"), (403, None, "http_error"),
    (302, None, "redirect_blocked"), (301, "/canonical", "redirect_same_host"),
    (302, "http://" + "b" * 56 + ".onion/", "redirect_other_host"),
    (302, "http://127.0.0.1/private?token=secret", "redirect_invalid_target"),
])
def test_http_failures_are_precise_and_redirects_still_blocked(monkeypatch, status, location, code):
    monkeypatch.delenv("NOR_TOR_PROXY", raising=False)
    response = FakeResponse(b"private response body", status=status)
    if location:
        response.headers["Location"] = location
    calls = fake_session(monkeypatch, response)
    with pytest.raises(CollectionError) as exc:
        fetch_page("http://" + "a" * 56 + ".onion/", nor.validate_source)
    assert failure_details(exc.value) == (code, status)
    assert len(calls) == 1
    assert "secret" not in str(exc.value)


def test_collection_reports_per_host_and_spreads_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "test.db"))
    first, second = ["http://" + letter * 56 + ".onion/" for letter in "ab"]
    visits = []
    def fetch(url, validate, budget):
        visits.append(url)
        if url == second:
            raise CollectionError("http_error", 503)
        return {"url": url, "title": "Fixture", "body": "Evidence", "links": [first + "child"]}
    result = crawl([first, second], nor.validate_source, nor.database, max_pages=2, fetcher=fetch)
    assert visits == [first, second]
    assert result["stop_reason"] == "page_limit"
    assert result["failed"] == 1
    failed = result["source_diagnostics"][1]
    assert failed["failure_codes"] == {"http_error": 1}
    assert failed["http_statuses"] == {"503": 1}
    assert first not in json.dumps(result)


def test_diagnostic_command_saves_safe_report_and_signals_partial_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(manage, "ROOT", tmp_path)
    monkeypatch.setattr(manage, "CONFIG", tmp_path / "nor.local.json")
    monkeypatch.setattr(manage, "RUNTIME", tmp_path / ".runtime")
    monkeypatch.setattr(manage, "TOKEN", tmp_path / ".runtime/access-token")
    manage.initialize("fixture", "fixture")
    token = manage.read_token()
    capsys.readouterr()
    monkeypatch.setenv("NOR_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(manage, "apply_environment", lambda: None)
    roots = nor.sources()
    calls = []
    def collect(seeds, *args, **kwargs):
        calls.append(kwargs)
        return {"attempted": 1, "collected": 0, "failed": 1, "budget_exhausted": True,
                "source_diagnostics": [{"host_sha256": hashlib.sha256(
                    urlsplit(roots[0]).hostname.encode()).hexdigest(),
                    "failure_codes": {"network_timeout": 1}}]}
    monkeypatch.setattr(nor, "crawl", collect)
    assert manage.main(["diagnose-sources"]) == 1
    report = json.loads((tmp_path / ".runtime/source-diagnostics.json").read_text(encoding="utf-8"))
    assert report["unattempted_hosts"] == len(roots) - 1
    assert report["source_diagnostics"][0]["name"].startswith("Tor Project")
    assert calls[0]["max_depth"] == 0
    assert token not in capsys.readouterr().out
