"""Operator-declared metadata; never a claim of independent verification."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, unquote

from ranking import topic_matches


def registry():
    path = Path(os.getenv("NOR_SOURCE_REGISTRY", str(Path(__file__).with_name("source_registry.json"))))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or len(data) > 50:
            return []
        return [entry for entry in data if isinstance(entry, dict)
                and isinstance(entry.get("url"), str)
                and isinstance(entry.get("operator", ""), str)
                and isinstance(entry.get("topics", []), list)
                and all(isinstance(topic, str) for topic in entry.get("topics", []))]
    except (OSError, ValueError):
        return []


def metadata(url, entries):
    host = urlsplit(url).hostname
    return next((entry for entry in entries if urlsplit(entry.get("url", "")).hostname == host), {})


def operator(url, entries):
    return metadata(url, entries).get("operator", urlsplit(url).hostname)


def relevance(text, topics):
    return len(topic_matches(unquote(text).replace("-", " ").replace("_", " "), topics))


def select_seeds(seeds, topics, entries, limit=6):
    ranked = sorted(enumerate(seeds), key=lambda item: (
        -relevance(item[1] + " " + " ".join(metadata(item[1], entries).get("topics", [])), topics), item[0]))
    output, seen = [], set()
    for distinct in (True, False):
        for _, url in ranked:
            group = operator(url, entries)
            if url in output or (distinct and group in seen):
                continue
            output.append(url)
            seen.add(group)
            if len(output) == limit:
                return output
    return output
