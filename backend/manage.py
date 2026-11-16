"""Manual private NOR activation, independent of GitHub Actions.

Configuration is data, never executed. No installers, services or models are
downloaded by this program. Secrets are never included in diagnostics.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "nor.local.json"
RUNTIME = ROOT / ".runtime"
TOKEN = RUNTIME / "access-token"
DEFAULTS = {
    "ollama_url": "http://127.0.0.1:11434",
    "chat_model": "",
    "embedding_model": "",
    "tor_proxy": "socks5h://127.0.0.1:9050",
    "model_timeout": 20,
    "model_context": 16384,
    "model_output_limit": 2200,
}
DEPENDENCIES = ("fastapi", "uvicorn", "requests", "bs4", "socks")


def load_config(path=None):
    path = path or CONFIG
    if not path.exists():
        return dict(DEFAULTS)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Unknown configuration keys.")
    result = DEFAULTS | value
    for name in ("ollama_url", "chat_model", "embedding_model", "tor_proxy"):
        if not isinstance(result[name], str):
            raise ValueError("Configuration values must be strings.")
    endpoint = urlsplit(result["ollama_url"])
    if (endpoint.scheme not in ("http", "https") or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or (endpoint.scheme == "http" and endpoint.hostname not in ("127.0.0.1", "localhost", "::1"))):
        raise ValueError("Ollama requires HTTPS unless it is on localhost.")
    proxy = urlsplit(result["tor_proxy"])
    if proxy.scheme != "socks5h" or not proxy.hostname or not proxy.port or proxy.username or proxy.password or proxy.path not in ("", "/"):
        raise ValueError("Configure a SOCKS5h proxy without embedded credentials.")
    for name, low, high in (("model_timeout", 5, 120), ("model_context", 2048, 32768), ("model_output_limit", 256, 4096)):
        if type(result[name]) is not int or not low <= result[name] <= high:
            raise ValueError("Invalid model limits.")
    return result


def initialize(chat_model="", embedding_model=""):
    if CONFIG.exists():
        raise ValueError("Configuration already exists. Edit nor.local.json; it will not be overwritten.")
    value = dict(DEFAULTS, chat_model=chat_model, embedding_model=embedding_model)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not TOKEN.exists():
        descriptor = os.open(TOKEN, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(32))
    with CONFIG.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
    return {"configuration_created": True, "token_created_or_preserved": True}


def read_token():
    value = TOKEN.read_text(encoding="utf-8").strip() if TOKEN.is_file() else ""
    return value if len(value) >= 32 else ""


def installed_model_names(url):
    request = urllib.request.Request(url.rstrip("/") + "/api/tags")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError("Model catalogue too large.")
    data = json.loads(payload)
    return {item["name"] for item in data["models"] if isinstance(item, dict) and isinstance(item.get("name"), str)}


def socks_responding(url):
    proxy = urlsplit(url)
    with socket.create_connection((proxy.hostname, proxy.port), timeout=2) as connection:
        connection.settimeout(2)
        connection.sendall(b"\x05\x01\x00")
        reply = bytearray()
        while len(reply) < 2:
            chunk = connection.recv(2 - len(reply))
            if not chunk:
                return False
            reply.extend(chunk)
        return reply == b"\x05\x00"


def model_present(name, installed):
    return bool(name) and (name in installed or (":" not in name and name + ":latest" in installed))


def doctor():
    config = load_config()
    missing = [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]
    report = {"configuration_exists": CONFIG.is_file(), "missing_dependencies": missing,
              "token_configured": bool(read_token()), "ollama_responding": False,
              "chat_model_installed": False, "embedding_model_installed": False,
              "socks_proxy_responding": False, "tor_network_verified": False,
              "indexed_passages": 0, "blockers": []}
    try:
        installed = installed_model_names(config["ollama_url"])
        report["ollama_responding"] = True
        report["chat_model_installed"] = model_present(config["chat_model"], installed)
        report["embedding_model_installed"] = model_present(config["embedding_model"], installed)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        report["socks_proxy_responding"] = socks_responding(config["tor_proxy"])
    except (OSError, ValueError):
        pass
    database = RUNTIME / "nor.sqlite3"
    if database.is_file():
        try:
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
                report["indexed_passages"] = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        except sqlite3.Error:
            pass
    requirements = {
        "configuration_exists": "Run: python backend/manage.py init --chat-model MODEL --embedding-model MODEL",
        "token_configured": "Initialize the private access token.",
        "ollama_responding": "Start the configured Ollama server.",
        "chat_model_installed": "Install and configure your chosen chat model in Ollama.",
        "embedding_model_installed": "Install and configure a multilingual embedding model in Ollama.",
        "socks_proxy_responding": "Start Tor with a local SOCKS proxy on the configured port.",
    }
    report["blockers"] = [message for key, message in requirements.items() if not report[key]]
    if missing:
        report["blockers"].append("Install backend/requirements.txt in a dedicated Python environment.")
    report["engine_prerequisites_met"] = not report["blockers"]
    return report


def apply_environment():
    config = load_config()
    token = read_token()
    if not CONFIG.is_file() or not token:
        raise ValueError("Run manage.py init before starting NOR.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    values = {
        "NOR_ACCESS_TOKEN": token, "NOR_DB": str(RUNTIME / "nor.sqlite3"),
        "NOR_SOURCES": str(Path(__file__).parent / "sources.json"),
        "NOR_OLLAMA_URL": config["ollama_url"], "NOR_CHAT_MODEL": config["chat_model"],
        "NOR_EMBED_MODEL": config["embedding_model"], "NOR_TOR_PROXY": config["tor_proxy"],
        "NOR_MODEL_TIMEOUT": str(config["model_timeout"]), "NOR_MODEL_CONTEXT": str(config["model_context"]),
        "NOR_MODEL_OUTPUT_LIMIT": str(config["model_output_limit"]),
    }
    os.environ.update(values)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manual private NOR activation; no CI required.")
    parser.add_argument("command", choices=["init", "doctor", "collect", "diagnose-sources", "embed", "verify", "serve"])
    parser.add_argument("--chat-model", default="")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print(json.dumps(initialize(args.chat_model, args.embedding_model), indent=2))
            return 0
        if args.command == "doctor":
            report = doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["engine_prerequisites_met"] else 2
        apply_environment()
        if args.command == "serve":
            if not 1024 <= args.port <= 65535:
                raise ValueError("Use a port between 1024 and 65535.")
            import uvicorn
            # Loopback only. A private HTTPS access path must be configured
            # separately for the iPhone; no public listener is opened here.
            uvicorn.run("nor:app", host="127.0.0.1", port=args.port, workers=1, access_log=False)
        elif args.command == "verify":
            from live_smoke import run
            report = run(RUNTIME / "live-smoke.json")
            print(json.dumps(report, indent=2))
            return 0 if report["status"] == "passed" else 1
        else:
            import nor
            from engine import index_embeddings, sync_index
            if args.command in ("collect", "diagnose-sources"):
                seeds = nor.sources()
                if args.command == "diagnose-sources":
                    result = nor.crawl(seeds, nor.validate_source, nor.database,
                                       max_pages=max(1, len(seeds)), max_depth=0, budget=180)
                else:
                    result = nor.crawl(seeds, nor.validate_source, nor.database)
                with nor.database() as db:
                    sync_index(db)
                from source_catalog import registry
                import hashlib
                from urllib.parse import urlsplit
                entries = registry()
                for source in result.get("source_diagnostics", []):
                    entry = next((entry for entry in entries if hashlib.sha256(
                        urlsplit(entry["url"]).hostname.encode()).hexdigest() == source["host_sha256"]), {})
                    source["name"] = entry.get("name", "Configured source")
                    source["declared_operator"] = entry.get("operator")
                result["kind"] = "source_connectivity_diagnostic" if args.command == "diagnose-sources" else "collection_report"
                result["configured_hosts"] = len({urlsplit(url).hostname for url in seeds})
                result["unattempted_hosts"] = result["configured_hosts"] - len(result.get("source_diagnostics", []))
                target = RUNTIME / ("source-diagnostics.json" if args.command == "diagnose-sources" else "collection-report.json")
                temporary = target.with_suffix(".tmp")
                temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                temporary.replace(target)
                print(json.dumps(result, indent=2))
                if args.command == "diagnose-sources":
                    return 0 if not result["failed"] and not result["unattempted_hosts"] and result["collected"] else 1
                return 0 if result["collected"] else 1
            from intelligence import Ollama
            with nor.database() as db:
                print(json.dumps({"embedded_passages": index_embeddings(db, Ollama())}))
        return 0
    except Exception as exc:
        # Configuration errors can include no secret values. Network/model
        # responses are not echoed, to keep credentials out of console output.
        print("NOR could not complete this step: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
