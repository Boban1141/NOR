"""Small synthetic retrieval benchmark. Not a real dark-web or LLM evaluation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import tempfile

import nor
from engine import investigate

DOCUMENTS = [
    ("a", "Human origins", "Modern human origins, fossils, genetic evidence and ancient populations are discussed in this research note."),
    ("b", "Identity forgery", "A forged identity document can contain altered dates and inconsistent portraits. These observations require human review."),
    ("c", "Data breach", "The incident report describes a data breach and exposed credentials. The claims have not been independently verified."),
    ("d", "Signature comparison", "Handwritten signature comparison requires reference samples and careful consideration of natural variation."),
    ("e", "Audio provenance", "An audio recording may contain synthetic speech. Acoustic artifacts alone do not establish who produced it."),
    ("f", "Garden catalogue", "Roses, herbs, soil, watering and garden furniture are listed in a seasonal catalogue."),
    ("g", "Astronomy", "A telescope observation log records planets, distant stars and atmospheric conditions."),
    ("h", "Cooking", "Bread recipes describe flour, water, yeast, kneading and baking temperatures."),
]
CASES = [
    ("Qui est à l’origine des humains ?", "fr", "a"),
    ("human origins genetic evidence", "en", "a"),
    ("document identite falsifie", "fr", "b"),
    ("forged identity document", "en", "b"),
    ("fuite de donnees", "fr", "c"),
    ("data breach credentials", "en", "c"),
    ("signature reference samples", "en", "d"),
    ("synthetic speech audio recording", "en", "e"),
    ("garden watering soil", "en", "f"),
    ("telescope stars planets", "en", "g"),
    ("bread yeast baking", "en", "h"),
]


class NoModel:
    chat_model = ""
    embed_model = ""


def evaluate():
    previous = os.environ.get("NOR_DB")
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="nor-eval-") as directory:
            os.environ["NOR_DB"] = str(Path(directory) / "evaluation.db")
            with nor.database() as db:
                for host, title, body in DOCUMENTS:
                    db.execute("INSERT INTO pages VALUES (?,?,?,?,?)", ("http://" + host * 56 + ".onion/", title, body, datetime.now(timezone.utc).isoformat(), hashlib.sha256(body.encode()).hexdigest()))
            for question, language, expected in CASES:
                answer = investigate(nor.database, question, language, NoModel())
                urls = [s["url"] for s in answer["sources"]]
                expected_url = "http://" + expected * 56 + ".onion/"
                rank = urls.index(expected_url) + 1 if expected_url in urls else None
                results.append({"question": question, "language": language, "relevant_rank": rank, "duration_ms": answer["duration_ms"]})
    finally:
        if previous is None:
            os.environ.pop("NOR_DB", None)
        else:
            os.environ["NOR_DB"] = previous
    return {"scope": "small synthetic retrieval fixture, not real dark-web or model performance",
            "documents": len(DOCUMENTS), "queries": len(results),
            "hit_at_3": sum(r["relevant_rank"] is not None and r["relevant_rank"] <= 3 for r in results) / len(results),
            "mean_reciprocal_rank": statistics.mean(1 / r["relevant_rank"] if r["relevant_rank"] else 0 for r in results),
            "median_duration_ms": statistics.median(r["duration_ms"] for r in results),
            "model_used": False, "real_tor_used": False, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
