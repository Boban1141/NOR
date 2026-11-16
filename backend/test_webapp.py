import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import nor
import webapp


def request(cookie="", extra=None):
    headers = {"x-nor-client": "pwa", "sec-fetch-site": "same-origin"}
    if cookie: headers["cookie"] = webapp.COOKIE + "=" + cookie
    headers.update(extra or {})
    return Request({"type":"http", "method":"POST", "scheme":"https", "path":"/session", "headers": [(key.encode(),value.encode()) for key,value in headers.items()], "client":("test-client",123), "server":("nor.example",443)})


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NOR_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("NOR_ACCESS_TOKEN", "x" * 40)
    webapp.ATTEMPTS.clear()
    return nor.database


def cookie(response):
    return response.headers["set-cookie"].split(";",1)[0].split("=",1)[1]


def test_pairing_issues_secure_opaque_session_and_is_single_use(db):
    code = webapp.create_pairing(db)
    response = webapp.login(request(), webapp.Login(code=code), db)
    assert json.loads(response.body) == {"status":"ok"}
    for flag in ("Secure", "HttpOnly", "SameSite=strict", "Path=/"):
        assert flag in response.headers["set-cookie"]
    assert webapp.session_valid(request(cookie(response)), db)
    with pytest.raises(HTTPException) as error:
        webapp.login(request(), webapp.Login(code=code), db)
    assert error.value.status_code == 401
    with db() as connection:
        values = [tuple(row) for row in connection.execute("SELECT * FROM web_sessions")]
    assert code not in str(values) and cookie(response) not in str(values) and "x" * 40 not in str(values)


def test_pairing_is_atomic_across_simultaneous_logins(db):
    code = webapp.create_pairing(db)
    def attempt(_):
        try: return webapp.login(request(), webapp.Login(code=code), db).status_code
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(attempt, range(2))) == [200,401]


def test_new_pairing_invalidates_old_code(db):
    old = webapp.create_pairing(db)
    new = webapp.create_pairing(db)
    if new == old: pytest.skip("Random codes coincided")
    with pytest.raises(HTTPException): webapp.login(request(), webapp.Login(code=old), db)
    assert webapp.login(request(), webapp.Login(code=new), db).status_code == 200


def test_expired_code_and_session_rejected_and_token_rotation_revokes(db, monkeypatch):
    code = webapp.create_pairing(db)
    with db() as connection: connection.execute("UPDATE web_pairings SET expires=0")
    with pytest.raises(HTTPException): webapp.login(request(), webapp.Login(code=code), db)
    response = webapp.login(request(), webapp.Login(token="x" * 40), db)
    value = cookie(response)
    monkeypatch.setenv("NOR_ACCESS_TOKEN", "y" * 40)
    assert not webapp.session_valid(request(value), db)
    monkeypatch.setenv("NOR_ACCESS_TOKEN", "x" * 40)
    with db() as connection: connection.execute("UPDATE web_sessions SET expires=0")
    assert not webapp.session_valid(request(value), db)


@pytest.mark.parametrize("headers", [{"x-nor-client":""},{"sec-fetch-site":"cross-site"}])
def test_cross_site_or_missing_client_header_cannot_login(db, headers):
    with pytest.raises(HTTPException) as error:
        webapp.login(request(extra=headers), webapp.Login(token="x" * 40), db)
    assert error.value.status_code == 403


def test_pairing_attempts_are_rate_limited(db):
    for _ in range(5):
        with pytest.raises(HTTPException) as error: webapp.login(request(), webapp.Login(code="invalid!"), db)
        assert error.value.status_code == 401
    with pytest.raises(HTTPException) as error: webapp.login(request(), webapp.Login(code="invalid!"), db)
    assert error.value.status_code == 429


def endpoint(path, method="GET"):
    return next(route.endpoint for route in nor.app.routes if getattr(route,"path",None) == path and method in route.methods)


def test_existing_api_bearer_auth_and_web_cookie_both_work(db):
    from fastapi.security import HTTPAuthorizationCredentials
    nor.authorize(HTTPAuthorizationCredentials(scheme="Bearer", credentials="x"*40))
    session = cookie(webapp.login(request(), webapp.Login(token="x"*40), db))
    nor.authorize(None, request(session))
    with pytest.raises(HTTPException): nor.authorize(None, request())


def test_logout_revokes_persistent_session(db):
    value = cookie(webapp.login(request(), webapp.Login(token="x"*40), db))
    response = endpoint('/session','DELETE')(request(value))
    assert not webapp.session_valid(request(value), db)
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_only_explicit_public_assets_are_served():
    root = Path(nor.ROOT) / 'web'
    assert Path(endpoint('/')().path) == root / 'index.html'
    for name in ('app.js','style.css','icon-192.png','icon-512.png','apple-touch-icon.png'):
        assert Path(endpoint('/assets/{name}')(name).path).is_file()
    for name in ('../nor.local.json','access-token','nor.py'):
        with pytest.raises(HTTPException): endpoint('/assets/{name}')(name)
    manifest = json.loads((root/'manifest.webmanifest').read_text(encoding='utf-8'))
    assert manifest['display'] == 'standalone'
    assert manifest['start_url'] == '/'


def test_worker_caches_only_shell_not_sessions_or_research():
    source = (Path(nor.ROOT)/'web/sw.js').read_text(encoding='utf-8')
    allowed = source.split('const SHELL = ',1)[1].split(';',1)[0]
    assert '/session' not in allowed and '/research' not in allowed and '/capabilities' not in allowed
    assert "event.request.method !== 'GET'" in source


def test_frontend_never_stores_credentials_or_renders_html_from_sources():
    source = (Path(nor.ROOT)/'web/assets/app.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in source
    assert "save('token'" not in source and "save('code'" not in source
    assert "voice.localService" in source and 'processLocally = true' in source
    assert "redirect: 'error'" in source
