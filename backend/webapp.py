"""Same-origin mobile client, one-time pairing and opaque HttpOnly sessions."""
import hashlib
import os
from pathlib import Path
import secrets
import time
from collections import OrderedDict
from threading import Lock

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

COOKIE = "__Host-nor_session"
ATTEMPTS, ATTEMPT_LOCK = OrderedDict(), Lock()


def tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS web_sessions (digest TEXT PRIMARY KEY, binding TEXT, expires INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS web_pairings (digest TEXT PRIMARY KEY, binding TEXT, expires INTEGER)")
    now = int(time.time())
    for table in ("web_sessions", "web_pairings"):
        db.execute("DELETE FROM " + table + " WHERE expires<=?", (now,))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def binding():
    token = os.getenv("NOR_ACCESS_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "NOR is not configured.")
    return digest(token)


def create_pairing(db_factory):
    code = str(secrets.randbelow(100_000_000)).zfill(8)
    stamp = binding()
    with db_factory() as db:
        tables(db)
        # Only the most recent code is valid, including across server restarts.
        db.execute("DELETE FROM web_pairings")
        db.execute("INSERT INTO web_pairings VALUES (?,?,?)", (digest(code), stamp, int(time.time()) + 600))
    return code


def same_origin_client(request):
    if request.headers.get("x-nor-client") != "pwa" or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Use the NOR application on this server.")


def session_valid(request, db_factory):
    same_origin_client(request)
    value = request.cookies.get(COOKIE, "")
    if not 32 <= len(value) <= 128:
        return False
    with db_factory() as db:
        tables(db)
        row = db.execute("SELECT binding FROM web_sessions WHERE digest=? AND expires>?", (digest(value), int(time.time()))).fetchone()
    return bool(row and secrets.compare_digest(row[0], binding()))


class Login(BaseModel):
    code: str = Field(default="", max_length=8)
    token: str = Field(default="", max_length=512)


def login(request, data, db_factory):
    same_origin_client(request)
    stamp = binding()
    address = request.client.host if request.client else "local"
    now = time.monotonic()
    with ATTEMPT_LOCK:
        failures = [value for value in ATTEMPTS.pop(address, []) if now - value < 60]
        if len(failures) >= 5:
            ATTEMPTS[address] = failures
            raise HTTPException(429, "Wait one minute before trying again.")
        ATTEMPTS[address] = failures + [now]
        while len(ATTEMPTS) > 256:
            ATTEMPTS.popitem(last=False)
    accepted = bool(data.token and secrets.compare_digest(digest(data.token), stamp))
    # Acquire the write lock before reading: a pairing code cannot be consumed
    # twice by concurrent requests.
    with db_factory() as db:
        db.execute("BEGIN IMMEDIATE")
        tables(db)
        if not accepted and len(data.code) == 8 and data.code.isascii() and data.code.isdigit():
            row = db.execute("SELECT binding FROM web_pairings WHERE digest=? AND expires>?", (digest(data.code), int(time.time()))).fetchone()
            if row and secrets.compare_digest(row[0], stamp):
                db.execute("DELETE FROM web_pairings WHERE digest=?", (digest(data.code),))
                accepted = True
        if accepted:
            session = secrets.token_urlsafe(32)
            db.execute("INSERT INTO web_sessions VALUES (?,?,?)", (digest(session), stamp, int(time.time()) + 7 * 86400))
    if not accepted:
        raise HTTPException(401, "Invalid or expired pairing code.")
    with ATTEMPT_LOCK:
        ATTEMPTS.pop(address, None)
    response = JSONResponse({"status": "ok"})
    response.set_cookie(COOKIE, session, max_age=7 * 86400, secure=True, httponly=True, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


def install_web(app, root, db_factory):
    directory = Path(root) / "web"
    @app.middleware("http")
    async def private_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'; form-action 'self'; worker-src 'self'"
        return response

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(directory / "index.html", media_type="text/html")

    @app.get("/assets/{name}", include_in_schema=False)
    def asset(name: str):
        allowed = {"app.js", "style.css", "icon-192.png", "icon-512.png", "apple-touch-icon.png"}
        if name not in allowed:
            raise HTTPException(404)
        return FileResponse(directory / "assets" / name)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(directory / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    def worker():
        return FileResponse(directory / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

    @app.post("/session", include_in_schema=False)
    def open_session(request: Request, data: Login):
        return login(request, data, db_factory)

    @app.delete("/session", include_in_schema=False)
    def close_session(request: Request):
        same_origin_client(request)
        with db_factory() as db:
            tables(db)
            db.execute("DELETE FROM web_sessions WHERE digest=?", (digest(request.cookies.get(COOKIE, "")),))
        response = JSONResponse({"status": "signed_out"})
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return response
