"""Query-focused evidence windows. Relevance is not a truth score."""
import re
import unicodedata

TOPICS = (
    ("privacy", {"privacy", "vie privee", "privee", "confidentialite", "confidentiality", "personal data", "donnees personnelles", "surveillance", "anonymat", "anonymity", "anonymous", "anonyme"}),
    ("censorship", {"censure", "censorship", "censored", "censoring", "blocage", "blocking", "blocked"}),
    ("network_tunnels", {"tunnel", "tunnels", "tunneling", "tunnelling", "tunnelisation"}),
)
META_WORDS = set("disent dit dites source sources selon expliquer explique explain tell says say about regarding concerning quels quelles que question sujet".split())


def folded(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def contains(text, term):
    return re.search(r"(?<![^\W_])" + re.escape(term) + r"(?![^\W_])", text) is not None


def focus_terms(question, tokenizer):
    tokens = [word for word in tokenizer(question) if word not in META_WORDS]
    normalized = folded(question)
    concepts = [(name, terms) for name, terms in TOPICS if any(contains(normalized, term) for term in terms)]
    covered = {word for _, terms in concepts for term in terms for word in term.split()}
    identities = {"tor", "i2p", "onion", "amnesty", "international"}
    remaining = [(word, {word}) for word in dict.fromkeys(tokens)
                 if word not in covered and word not in identities
                 and not (word in {"reseau", "network"} and any(name == "network_tunnels" for name, _ in concepts))]
    return (concepts + remaining)[:12]


def topic_matches(text, topics):
    value = folded(text)
    return [name for name, terms in topics if any(contains(value, term) for term in terms)]


def focused_window(body, topics, size=700):
    if len(body) <= size:
        window, start = body, 0
    else:
        anchors = [0]
        terms = {term for _, values in topics for term in values}
        for match in re.finditer(r"[^\W_]+", body):
            word = folded(match.group())
            if word in terms or any(word in term.split() for term in terms):
                anchors.append(max(0, match.start() - 140))
        candidates = []
        for start in dict.fromkeys(anchors):
            if start and not body[start - 1].isspace():
                boundary = body.find(" ", start, min(len(body), start + 50))
                if boundary >= 0:
                    start = boundary + 1
            end = min(len(body), start + size)
            if end < len(body):
                end = body.rfind(" ", start + size // 2, end)
            text = body[start:end]
            hits = len(topic_matches(text, topics))
            # Prefer concentrated evidence to donation and membership banners.
            penalty = 0.2 if re.search(r"donate|donors|donation|join the movement", folded(text)) else 0
            candidates.append((hits * 3 - penalty, -len(text), -start, start, text))
        _, _, _, start, window = max(candidates)
    matched = topic_matches(window, topics)
    return start, window, matched


def filter_topic_claims(claims, topics):
    recognized = [(name, terms) for name, terms in topics if name in {item[0] for item in TOPICS}]
    if not recognized:
        return claims, 0
    accepted = []
    for claim in claims:
        claimed = set(topic_matches(claim["text"], recognized))
        quoted = {name for evidence in claim["evidence"] for name in topic_matches(evidence["quote"], recognized)}
        if claimed and claimed <= quoted:
            accepted.append(claim)
    return accepted, len(claims) - len(accepted)
