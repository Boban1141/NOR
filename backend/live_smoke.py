"""Explicit live integration check. No raw source contents in the report."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from crawler import crawl
from engine import index_embeddings, investigate
from intelligence import ModelUnavailable, Ollama, Plan, error_code
import nor


def run(output):
    report = {"kind": "live_connectivity_smoke_test", "quality_benchmark": False,
              "chat": False, "embeddings": False, "tor": False, "synthesis": False,
              "public_mirrors_only": True, "failures": []}
    previous = os.environ.get("NOR_DB")
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="nor-live-") as directory:
            os.environ["NOR_DB"] = str(Path(directory) / "live.db")
            model = Ollama()
            try:
                plan = model.structured("Return one search query in the requested JSON schema.", "Tor privacy documentation", Plan)
                report["chat"] = bool(plan.queries)
            except ModelUnavailable as exc:
                report["failures"].append("chat:" + str(exc))
            try:
                vectors = model.embed(["privacy and censorship", "vie privée et censure"])
                report["embeddings"] = len(vectors) == 2 and len(vectors[0]) == len(vectors[1])
            except ModelUnavailable as exc:
                report["failures"].append("embeddings:" + str(exc))
            collection = crawl(nor.sources(), nor.validate_source, nor.database, max_pages=3, max_depth=0, budget=90)
            report["collection"] = collection
            report["tor"] = collection["collected"] > 0
            if report["tor"]:
                if report["embeddings"]:
                    try:
                        with nor.database() as db:
                            report["embedded_passages"] = index_embeddings(db, model)
                    except ModelUnavailable as exc:
                        report["failures"].append("indexing:" + str(exc))
                # This question is a connectivity diagnostic, not a user research claim.
                result = investigate(nor.database, "What do these sources say about privacy or censorship?", "en", model)
                report["synthesis"] = result["capabilities"]["synthesis_used"]
                report["mode"] = result["mode"]
                report["result_count"] = len(result["sources"])
                report["accepted_claims"] = len(result["claims"])
                report["warnings"] = result["warnings"]
                report["diagnostics"] = result.get("diagnostics", [])
                report["failures"].extend(item["stage"] + ":" + item["code"] for item in report["diagnostics"])
            else:
                report["failures"].append("tor:no_source_collected")
    except (ModelUnavailable, OSError, ValueError) as exc:
        report["failures"].append(type(exc).__name__ + ":" + str(exc)[:200])
    finally:
        if previous is None:
            os.environ.pop("NOR_DB", None)
        else:
            os.environ["NOR_DB"] = previous
        report["duration_seconds"] = round(time.monotonic() - started, 2)
        report["status"] = "passed" if all(report[key] for key in ("chat", "embeddings", "tor", "synthesis")) else "partial_or_failed"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("live-smoke.json"))
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
