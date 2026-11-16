"""Private NOR API. Advanced retrieval with optional server-side AI synthesis."""
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from typing import Literal
from contextlib import contextmanager
from threading import BoundedSemaphore

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from engine import investigate, index_embeddings, sync_index, words
from ranking import focus_terms
from source_catalog import registry, select_seeds, metadata, operator
from intelligence import Ollama, ModelUnavailable
from crawler import crawl, fetch_page, save_page
from networks import validate_source, network as source_network

ROOT = Path(__file__).resolve().parent


class UTF8JSONResponse(JSONResponse):
    # JSON is UTF-8 already. The explicit charset also helps legacy clients
    # such as Windows PowerShell 5.1 decode the response correctly.
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="NOR private research", docs_url=None, redoc_url=None,
              default_response_class=UTF8JSONResponse)
auth = HTTPBearer(auto_error=False)
research_slots = BoundedSemaphore(2)


@contextmanager
def database():
    db = sqlite3.connect(os.getenv("NOR_DB", str(ROOT / "nor.sqlite3")))
    db.row_factory = sqlite3.Row
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(url UNINDEXED, title, body, collected_at UNINDEXED, digest UNINDEXED)")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
    token = os.getenv("NOR_ACCESS_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Configurer un jeton serveur d'au moins 32 caractères.")
    if credentials is None or not secrets.compare_digest(credentials.credentials.encode(), token.encode()):
        raise HTTPException(401, "Accès refusé.")


def sources(network="all"):
    from networks import network as source_network
    if network not in ("all", "tor", "i2p"):
        raise ValueError("invalid_network")
    output = []
    for kind, variable, filename in (("tor", "NOR_SOURCES", "sources.json"), ("i2p", "NOR_I2P_SOURCES", "sources_i2p.json")):
        if network not in ("all", kind):
            continue
        path = Path(os.getenv(variable, str(ROOT / filename)))
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or len(data) > 50:
            raise ValueError("At most 50 sources per network.")
        for url in data:
            validate_source(url)
            if source_network(url) != kind:
                raise ValueError("source_in_wrong_network_catalogue")
            output.append(url)
    return output


def collect(url):
    page = fetch_page(url, validate_source)
    save_page(database, page)
    return page


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: Literal["fr", "en"] = "fr"
    refresh: bool = False
    profile: Literal["balanced", "deep"] = "balanced"
    use_cache: bool = True


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


@app.post("/research", dependencies=[Depends(authorize)])
def research(request: Question):
    tokens = re.findall(r"[^\W_]+", request.question, flags=re.UNICODE)[:20]
    if not tokens:
        raise HTTPException(422, "La question doit contenir des mots." if request.language == "fr" else "The question must contain words.")
    if not research_slots.acquire(blocking=False):
        raise HTTPException(429, "NOR is busy. Retry shortly.")
    try:
        started = time.monotonic()
        refreshed = None
        collection_ms = 0
        if request.refresh:
            try:
                selected = select_seeds(sources(), focus_terms(request.question, words), registry())
                refreshed = crawl(selected, validate_source, database, max_pages=10, max_depth=2,
                                  budget=45, question=request.question, tokenizer=words)
                collection_ms = round((time.monotonic() - started) * 1000)
            except (ValueError, OSError):
                raise HTTPException(503, "Invalid source catalogue.")
        result = investigate(database, request.question, request.language, profile=request.profile,
                             use_cache=request.use_cache and not request.refresh)
        result["collection"] = refreshed
        result["capabilities"]["live_search_used"] = bool(refreshed and refreshed["collected"])
        entries = registry()
        groups = set()
        for source in result["sources"]:
            entry = metadata(source["url"], entries)
            source["network"] = source_network(source["url"])
            source["declared_operator"] = entry.get("operator")
            source["operator_reference"] = entry.get("operator_reference")
            groups.add(operator(source["url"], entries))
        result["coverage"]["distinct_operator_groups"] = len(groups)
        if result["sources"] and len(groups) < 2:
            result["warnings"].append("single_operator_evidence")
        if refreshed and refreshed["collected"]:
            result["warnings"].append("new_pages_lexically_indexed_run_embed_for_semantics")
        if refreshed and refreshed["failed"]:
            result["warnings"].append("some_live_sources_unavailable")
        result["timings"]["collection_ms"] = collection_ms
        result["duration_ms"] = round((time.monotonic() - started) * 1000)
        return result
    finally:
        research_slots.release()


@app.get("/capabilities", dependencies=[Depends(authorize)])
def capabilities():
    with database() as db:
        sync_index(db)
        chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        model = os.getenv("NOR_EMBED_MODEL", "")
        embedded = db.execute("SELECT COUNT(*) FROM embeddings WHERE model=?", (model,)).fetchone()[0]
    return {"version": "0.3.0", "indexed_passages": chunks, "embedded_passages": embedded,
            "chat_model_configured": bool(os.getenv("NOR_CHAT_MODEL")),
            "embedding_model_configured": bool(model), "model_connectivity_verified": False,
            "live_search_from_app": True, "scope": "configured_darknet_sources", "networks": ["tor", "i2p"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "crawl", "token", "index", "embed"])
    parser.add_argument("--rebuild", action="store_true", help="Delete cached vectors for the configured embedding model before embedding.")
    args = parser.parse_args()
    if args.command == "token":
        print(secrets.token_urlsafe(32))
    elif args.command in ("index", "embed"):
        with database() as db:
            sync_index(db)
            if args.command == "embed":
                try:
                    model = Ollama()
                    if args.rebuild:
                        db.execute("DELETE FROM embeddings WHERE model=?", (model.embed_model,))
                        db.commit()
                    print("Passages embedded:", index_embeddings(db, model))
                except ModelUnavailable as exc:
                    parser.exit(1, "Embedding service unavailable: " + str(exc) + "\n")
            print("Passage index ready.")
    elif args.command == "crawl":
        print(json.dumps(crawl(sources(), validate_source, database)))
    else:
        for source in sources():
            try:
                collect(source)
                print("Source collectée.")
            except (requests.RequestException, ValueError):
                print("Échec de collecte : source inaccessible, refusée ou réponse invalide.")
