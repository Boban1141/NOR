"""Bounded Tor collection: configured hosts only, no redirects or direct fallback."""
from collections import deque
from datetime import datetime, timezone
import hashlib
import os
import time
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests


def fetch_page(url, validate, budget=15):
    validate(url)
    proxy = os.getenv("NOR_TOR_PROXY", "socks5h://127.0.0.1:9050")
    if not proxy.startswith("socks5h://"):
        raise ValueError("socks5h obligatoire pour résoudre les noms via Tor.")
    deadline = time.monotonic() + budget
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, proxies={"http": proxy, "https": proxy}, timeout=(5, min(8, budget)),
                         allow_redirects=False, stream=True,
                         headers={"User-Agent": "NOR-Research/0.3"}) as response:
            if response.status_code != 200:
                raise ValueError("source_unavailable_or_redirect")
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("unsupported_content_type")
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > 1_000_000 or time.monotonic() > deadline:
                    raise ValueError("page_budget_exceeded")
                chunks.append(chunk)
    soup = BeautifulSoup(b"".join(chunks), "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled"
    links = []
    for anchor in soup.find_all("a", href=True, limit=250):
        target = urldefrag(urljoin(url, anchor["href"]))[0]
        try:
            validate(target)
        except ValueError:
            continue
        if urlsplit(target).hostname == urlsplit(url).hostname:
            links.append(target)
    for node in soup(["script", "style", "iframe", "form", "nav", "footer"]):
        node.decompose()
    return {"url": url, "title": title[:300], "body": soup.get_text(" ", strip=True)[:100_000],
            "links": list(dict.fromkeys(links))}


def save_page(db_factory, page):
    digest = hashlib.sha256((page["title"] + "\n" + page["body"]).encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    values = (page["url"], page["title"], page["body"], now, digest)
    with db_factory() as db:
        db.execute("CREATE TABLE IF NOT EXISTS page_versions (url TEXT, title TEXT, body TEXT, collected_at TEXT, digest TEXT, PRIMARY KEY(url,digest))")
        db.execute("DELETE FROM page_versions WHERE julianday(collected_at) < julianday('now','-30 days')")
        db.execute("INSERT OR IGNORE INTO page_versions VALUES (?,?,?,?,?)", values)
        db.execute("DELETE FROM pages WHERE url=?", (page["url"],))
        db.execute("INSERT INTO pages VALUES (?,?,?,?,?)", values)


def crawl(seeds, validate, db_factory, max_pages=20, max_depth=2, budget=90, fetcher=None):
    if not 1 <= max_pages <= 100 or not 0 <= max_depth <= 3 or not 1 <= budget <= 180:
        raise ValueError("invalid_crawl_limits")
    for seed in seeds:
        validate(seed)
    allowed = {urlsplit(seed).hostname for seed in seeds}
    queue = deque((seed, 0) for seed in dict.fromkeys(seeds))
    visited, counts = set(), {"attempted": 0, "collected": 0, "failed": 0}
    deadline = time.monotonic() + budget
    fetcher = fetcher or fetch_page
    while queue and counts["attempted"] < max_pages and time.monotonic() < deadline:
        url, depth = queue.popleft()
        if url in visited or urlsplit(url).hostname not in allowed:
            continue
        visited.add(url)
        counts["attempted"] += 1
        try:
            page = fetcher(url, validate, min(15, max(1, deadline - time.monotonic())))
            save_page(db_factory, page)
            counts["collected"] += 1
            if depth < max_depth:
                for target in page["links"][:100]:
                    try:
                        validate(target)
                    except ValueError:
                        continue
                    if (urlsplit(target).hostname in allowed and target not in visited
                            and len(queue) < 500):
                        queue.append((target, depth + 1))
        except (requests.RequestException, ValueError):
            counts["failed"] += 1
    counts["budget_exhausted"] = bool(queue)
    return counts
