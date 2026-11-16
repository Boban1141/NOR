"""Bounded, server-side Ollama adapter. No automatic model downloads or tools."""
import json
import math
import os
import time
from urllib.parse import urlsplit

import requests
from urllib3.exceptions import ReadTimeoutError
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ModelUnavailable(Exception):
    pass


def error_code(error):
    known = {"model_timeout", "model_connection_error", "model_http_error", "model_response_too_large",
             "model_unavailable", "invalid_structured_response", "model_output_truncated",
             "chat_model_not_configured", "embedding_model_not_configured", "invalid_model_endpoint",
             "invalid_model_limits", "invalid_vector", "invalid_embedding_count", "invalid_embedding_response",
             "inconsistent_dimensions", "embedding_dimensions_changed_reindex_required"}
    value = str(error)
    return value if value in known else "model_error"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Plan(StrictModel):
    queries: list[str] = Field(min_length=1, max_length=5)


class Evidence(StrictModel):
    source_id: str = Field(pattern=r"^S[1-8]$")
    quote: str = Field(min_length=24, max_length=1000)


class Claim(StrictModel):
    text: str = Field(min_length=10, max_length=1200)
    evidence: list[Evidence] = Field(min_length=1, max_length=3)


class Synthesis(StrictModel):
    claims: list[Claim] = Field(max_length=8)
    gaps: list[str] = Field(max_length=5)


def vector(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 8192:
        raise ModelUnavailable("invalid_vector")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ModelUnavailable("invalid_vector")
    norm = math.sqrt(sum(x*x for x in value))
    if norm == 0 or not math.isfinite(norm):
        raise ModelUnavailable("invalid_vector")
    return [x / norm for x in value]


class Ollama:
    def __init__(self):
        self.url = os.getenv("NOR_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        parts = urlsplit(self.url)
        if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment
                or (parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"))):
            raise ModelUnavailable("invalid_model_endpoint")
        self.chat_model = os.getenv("NOR_CHAT_MODEL", "")
        self.embed_model = os.getenv("NOR_EMBED_MODEL", "")
        try:
            self.timeout = min(120, max(5, int(os.getenv("NOR_MODEL_TIMEOUT", "20"))))
            self.context = min(32768, max(2048, int(os.getenv("NOR_MODEL_CONTEXT", "16384"))))
            self.output_limit = min(4096, max(256, int(os.getenv("NOR_MODEL_OUTPUT_LIMIT", "2200"))))
        except ValueError as exc:
            raise ModelUnavailable("invalid_model_limits") from exc

    def post(self, path, payload):
        deadline = time.monotonic() + self.timeout + 5
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.post(self.url + path, json=payload, timeout=(3, self.timeout),
                                  allow_redirects=False, stream=True) as response:
                    if response.status_code != 200:
                        raise ModelUnavailable("model_http_error")
                    chunks, size = [], 0
                    for chunk in response.iter_content(1024):
                        size += len(chunk)
                        if size > 2_000_000:
                            raise ModelUnavailable("model_response_too_large")
                        if time.monotonic() > deadline:
                            raise ModelUnavailable("model_timeout")
                        chunks.append(chunk)
            return json.loads(b"".join(chunks))
        except requests.Timeout as exc:
            raise ModelUnavailable("model_timeout") from exc
        except requests.ConnectionError as exc:
            if any(isinstance(item, ReadTimeoutError) for item in exc.args):
                raise ModelUnavailable("model_timeout") from exc
            raise ModelUnavailable("model_connection_error") from exc
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise ModelUnavailable("model_unavailable") from exc

    def structured(self, system, user, schema):
        if not self.chat_model:
            raise ModelUnavailable("chat_model_not_configured")
        result = self.post("/api/chat", {
            "model": self.chat_model, "stream": False, "format": schema.model_json_schema(),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "num_predict": self.output_limit, "num_ctx": self.context},
        })
        if isinstance(result, dict) and result.get("done_reason") == "length":
            raise ModelUnavailable("model_output_truncated")
        try:
            return schema.model_validate_json(result["message"]["content"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise ModelUnavailable("invalid_structured_response") from exc

    def embed(self, texts):
        if not self.embed_model:
            raise ModelUnavailable("embedding_model_not_configured")
        result = self.post("/api/embed", {"model": self.embed_model, "input": texts, "truncate": False})
        try:
            embeddings = result["embeddings"]
            if len(embeddings) != len(texts):
                raise ModelUnavailable("invalid_embedding_count")
            values = [vector(item) for item in embeddings]
            if len({len(item) for item in values}) != 1:
                raise ModelUnavailable("inconsistent_dimensions")
            return values
        except (KeyError, TypeError) as exc:
            raise ModelUnavailable("invalid_embedding_response") from exc
