import json
from pathlib import Path
import pytest

import nor
from intelligence import ModelUnavailable, Ollama
import live_smoke


def test_registered_sources_match_configuration_and_have_provenance():
    registry = json.loads((Path(nor.__file__).parent / "source_registry.json").read_text())
    assert [item["url"] for item in registry] == nor.sources()
    for item in registry:
        assert nor.validate_source(item["url"]) == item["url"]
        assert item["operator_reference"].startswith("https://")
        assert item["exclusive_dark_web_information"] is False
        assert item["reachability_verified"] is False


def test_published_onion_subdomain_allowed_but_external_suffix_rejected():
    host = "a" * 56 + ".onion"
    assert nor.validate_source("https://www." + host + "/")
    with pytest.raises(ValueError):
        nor.validate_source("https://www." + host + ".example.com/")
    with pytest.raises(ValueError):
        nor.validate_source("https://-invalid." + host + "/")


def test_model_limits_are_bounded(monkeypatch):
    monkeypatch.setenv("NOR_MODEL_TIMEOUT", "9999")
    monkeypatch.setenv("NOR_MODEL_CONTEXT", "1")
    monkeypatch.setenv("NOR_MODEL_OUTPUT_LIMIT", "9999")
    model = Ollama()
    assert (model.timeout, model.context, model.output_limit) == (120, 2048, 4096)
    monkeypatch.setenv("NOR_MODEL_TIMEOUT", "not-a-number")
    with pytest.raises(ModelUnavailable):
        Ollama()


def test_live_check_reports_failure_without_fabricating_success(tmp_path, monkeypatch):
    class UnavailableModel:
        def structured(self, *args): raise ModelUnavailable("offline")
        def embed(self, *args): raise ModelUnavailable("offline")
    monkeypatch.setattr(live_smoke, "Ollama", UnavailableModel)
    monkeypatch.setattr(live_smoke, "crawl", lambda *args, **kwargs: {"attempted": 3, "collected": 0, "failed": 3})
    target = tmp_path / "report.json"
    result = live_smoke.run(target)
    assert result["status"] == "partial_or_failed"
    assert not any(result[key] for key in ("chat", "embeddings", "tor", "synthesis"))
    assert json.loads(target.read_text())["quality_benchmark"] is False
