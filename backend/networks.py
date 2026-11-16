"""Darknet-only URL validation and explicit transport selection."""
import os
import re
from urllib.parse import parse_qs, urlsplit


def requested_network(question, selection="auto"):
    if selection not in ("auto", "all", "tor", "i2p"):
        raise ValueError("invalid_network_selection")
    if selection != "auto":
        return selection
    i2p = bool(re.search(r"\bi2p\b", question, re.I))
    tor = bool(re.search(r"\b(?:tor|onion)\b", question, re.I))
    return "i2p" if i2p and not tor else "tor" if tor and not i2p else "all"


def network(url):
    host = urlsplit(url).hostname or ""
    if host.endswith(".onion"):
        return "tor"
    if host.endswith(".i2p"):
        return "i2p"
    raise ValueError("darknet_source_required")


def validate_source(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("invalid_source_url")
    parts = urlsplit(url)
    if (parts.scheme not in ("http", "https") or parts.username is not None or parts.password is not None
            or parts.port not in (None, 80, 443) or parts.fragment):
        raise ValueError("invalid_source_url")
    host = parts.hostname or ""
    kind = network(url)
    if kind == "tor":
        valid = re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){0,3}[a-z2-7]{56}\.onion", host)
    else:
        valid = len(host) <= 253 and re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,4}i2p", host)
        if host.endswith(".b32.i2p"):
            valid = re.fullmatch(r"[a-z2-7]{52}\.b32\.i2p", host)
        if host == "proxy.i2p" or host.endswith(".proxy.i2p") or any(
                key.casefold() == "i2paddresshelper" for key in parse_qs(parts.query, keep_blank_values=True)):
            valid = False
    if not valid:
        raise ValueError("invalid_darknet_host")
    return url


def transport_proxy(url):
    validate_source(url)
    if network(url) == "tor":
        proxy = os.getenv("NOR_TOR_PROXY", "socks5h://127.0.0.1:9050")
        parts = urlsplit(proxy)
        if parts.scheme != "socks5h":
            raise ValueError("socks5h required for Tor")
    else:
        proxy = os.getenv("NOR_I2P_PROXY", "http://127.0.0.1:4444")
        parts = urlsplit(proxy)
        if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("local_i2p_proxy_required")
    if (not parts.hostname or not parts.port or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("invalid_proxy_endpoint")
    return proxy
