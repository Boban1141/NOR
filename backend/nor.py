"""Private NOR API. Advanced retrieval with optional server-side AI synthesis."""
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlsplit
from typing import Literal
from contextlib import contextmanager
from threading import BoundedSemaphore

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from engine import investigate, index_embeddings, sync_index
from intelligence import Ollama, ModelUnavailable
from crawler import crawl, fetch_page, save_page

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="NOR private research", docs_url=None, redoc_url=None)
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


def validate_source(url: str):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Invalid source URL.")
    parts = urlsplit(url)
    if (parts.scheme not in ("http", "https") or parts.username or parts.password
            or parts.port not in (None, 80, 443) or parts.fragment
            or not re.fullmatch(r"[a-z2-7]{56}\.onion", parts.hostname or "")):
        raise ValueError("Une adresse onion v3, sans identifiants ni port personnalisé, est requise.")
    return url


def sources():
    path = Path(os.getenv("NOR_SOURCES", str(ROOT / "sources.json")))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) > 50:
        raise ValueError("Le catalogue doit contenir au plus 50 adresses.")
    return [validate_source(url) for url in data]


def collect(url):
    page = fetch_page(url, validate_source)
    save_page(database, page)
    return page


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: Literal["fr", "en"] = "fr"
    refresh: bool = False


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
        refreshed = None
        if request.refresh:
            try:
                refreshed = crawl(sources(), validate_source, database, max_pages=8, max_depth=1, budget=35)
            except (ValueError, OSError):
                raise HTTPException(503, "Invalid source catalogue.")
        result = investigate(database, request.question, request.language)
        result["collection"] = refreshed
        result["capabilities"]["live_search_used"] = bool(refreshed and refreshed["collected"])
        if refreshed and refreshed["failed"]:
            result["warnings"].append("some_live_sources_unavailable")
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
            "live_search_from_app": True, "scope": "configured_onion_sources"}


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
