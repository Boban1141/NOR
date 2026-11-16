"""Bounded Tor collection: configured hosts only, no redirects or direct fallback."""
from collections import deque
from datetime import datetime, timezone
import hashlib
import os
import re
import time
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests
from ranking import focus_terms
from source_catalog import relevance


class CollectionError(ValueError):
    def __init__(self, code, status=None):
        super().__init__(code)
        self.code = code
        self.status = status


def failure_details(error):
    """Fixed codes only: never expose response bodies, URLs or proxy credentials."""
    if isinstance(error, CollectionError):
        return error.code, error.status
    for kind, code in ((requests.exceptions.ProxyError, "proxy_error"),
                       (requests.exceptions.SSLError, "tls_error"),
                       (requests.Timeout, "network_timeout"),
                       (requests.ConnectionError, "connection_error")):
        if isinstance(error, kind):
            return code, None
    # Streaming read timeouts can arrive wrapped in ConnectionError. They are
    # intentionally reported as connection_error rather than parsing raw text.
    return ("request_error" if isinstance(error, requests.RequestException) else "page_rejected"), None


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
                status = response.status_code
                code = "http_error"
                if 300 <= status < 400:
                    code = "redirect_blocked"
                    location = response.headers.get("Location")
                    if location:
                        try:
                            target = urljoin(url, location)
                            validate(target)
                            code = "redirect_same_host" if urlsplit(target).hostname == urlsplit(url).hostname else "redirect_other_host"
                        except ValueError:
                            code = "redirect_invalid_target"
                raise CollectionError(code, status)
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise CollectionError("unsupported_content_type", 200)
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > 1_000_000:
                    raise CollectionError("page_size_limit", 200)
                if time.monotonic() > deadline:
                    raise CollectionError("page_time_limit", 200)
                chunks.append(chunk)
    soup = BeautifulSoup(b"".join(chunks), "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled"
    links, link_titles = [], {}
    for anchor in soup.find_all("a", href=True, limit=250):
        target = urldefrag(urljoin(url, anchor["href"]))[0]
        try:
            validate(target)
        except ValueError:
            continue
        if urlsplit(target).hostname == urlsplit(url).hostname:
            links.append(target)
            link_titles[target] = anchor.get_text(" ", strip=True)[:250]
    for node in soup(["script", "style", "iframe", "form", "nav", "footer"]):
        node.decompose()
    content = soup.find("main") or soup.find("article") or soup
    def priority(target):
        path = urlsplit(target).path
        locale_only = bool(re.fullmatch(r"/(?:[a-z]{2,3}(?:-[A-Za-z]{2,4})?)?/?", path))
        topical = bool(re.search(r"privacy|censor|onion|surveillance|research|documentation", path, re.I))
        return (locale_only, not topical, target)
    return {"url": url, "title": title[:300], "body": content.get_text(" ", strip=True)[:100_000],
            "links": sorted(dict.fromkeys(links), key=priority), "link_titles": link_titles}


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
        db.execute("CREATE TABLE IF NOT EXISTS discovered_links (parent TEXT, url TEXT, title TEXT, PRIMARY KEY(parent,url))")
        db.execute("DELETE FROM discovered_links WHERE parent=?", (page["url"],))
        db.executemany("INSERT OR IGNORE INTO discovered_links VALUES (?,?,?)", [
            (page["url"], url, page.get("link_titles", {}).get(url, "")[:250]) for url in page.get("links", [])[:250]])


def crawl(seeds, validate, db_factory, max_pages=20, max_depth=2, budget=90, fetcher=None,
          question=None, tokenizer=None):
    if not 1 <= max_pages <= 100 or not 0 <= max_depth <= 3 or not 1 <= budget <= 180:
        raise ValueError("invalid_crawl_limits")
    for seed in seeds:
        validate(seed)
    allowed = {urlsplit(seed).hostname for seed in seeds}
    queue = deque((seed, 0) for seed in dict.fromkeys(seeds))
    topics = focus_terms(question, tokenizer) if question and tokenizer else []
    titles = {}
    # Reuse previously observed links only inside the explicitly configured scope.
    if topics:
        with db_factory() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='discovered_links'").fetchone()
            if exists:
                for parent, url, title in db.execute("SELECT parent,url,title FROM discovered_links ORDER BY parent,url LIMIT 12500"):
                    try:
                        validate(url)
                    except ValueError:
                        continue
                    if (urlsplit(parent).hostname in allowed and urlsplit(url).hostname in allowed
                            and relevance(url + " " + title, topics) and len(queue) < 500):
                        titles[url] = title
                        queue.append((url, 1))
    visited, counts = set(), {"attempted": 0, "collected": 0, "failed": 0}
    host_attempts, collected_hosts = {}, set()
    host_reports = {}
    deadline = time.monotonic() + budget
    fetcher = fetcher or fetch_page
    while queue and counts["attempted"] < max_pages and time.monotonic() < deadline:
        if queue:
            # Visit each selected host, then its best matching links. No remote
            # search endpoint receives the question or an automatically built URL.
            queue = deque(sorted(queue, key=lambda item: (
                host_attempts.get(urlsplit(item[0]).hostname, 0),
                -relevance(item[0] + " " + titles.get(item[0], ""), topics), item[1])))
        url, depth = queue.popleft()
        if url in visited or depth > max_depth or urlsplit(url).hostname not in allowed:
            continue
        visited.add(url)
        counts["attempted"] += 1
        host = urlsplit(url).hostname
        host_attempts[host] = host_attempts.get(host, 0) + 1
        report = host_reports.setdefault(host, {"host_sha256": hashlib.sha256(host.encode()).hexdigest(),
            "attempted": 0, "collected": 0, "failed": 0, "failure_codes": {}, "http_statuses": {}})
        report["attempted"] += 1
        try:
            page = fetcher(url, validate, min(15, max(1, deadline - time.monotonic())))
            save_page(db_factory, page)
            counts["collected"] += 1
            collected_hosts.add(host)
            report["collected"] += 1
            if depth < max_depth:
                for target in page["links"][:100]:
                    try:
                        validate(target)
                    except ValueError:
                        continue
                    if (urlsplit(target).hostname in allowed and target not in visited
                            and len(queue) < 500):
                        queue.append((target, depth + 1))
                        titles[target] = page.get("link_titles", {}).get(target, "")
        except (requests.RequestException, ValueError) as exc:
            counts["failed"] += 1
            report["failed"] += 1
            code, status = failure_details(exc)
            report["failure_codes"][code] = report["failure_codes"].get(code, 0) + 1
            if status is not None:
                key = str(status)
                report["http_statuses"][key] = report["http_statuses"].get(key, 0) + 1
    counts["budget_exhausted"] = bool(queue)
    counts["stop_reason"] = ("page_limit" if queue and counts["attempted"] >= max_pages else
                             "time_budget" if queue else "completed")
    counts["source_diagnostics"] = list(host_reports.values())
    if question:
        counts["query_guided"] = bool(topics)
        counts["selected_hosts"] = len(allowed)
        counts["collected_hosts"] = len(collected_hosts)
    return counts
