"""Zugriff auf eine Firecrawl-Instanz (self-hosted).

Bewusst schlank: nur ``urllib`` aus der Standardbibliothek, kein zusaetzliches
Dependency. Fehler werden zu leeren Ergebnissen degradiert — eine Recherche
soll nicht abstuerzen, weil die Suchmaschine gerade nicht antwortet; der
Aufrufer entscheidet, ob das ein Fehler ist.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:3002"
ENV_BASE_URL = "SCOUT_FIRECRAWL_URL"
ENV_TIMEOUT = "SCOUT_FIRECRAWL_TIMEOUT"

DEFAULT_TIMEOUT = 25.0
DEFAULT_RETRIES = 2
BACKOFF_BASE = 1.5


@dataclass
class SearchHit:
    """Ein Suchtreffer."""

    url: str
    title: str = ""
    description: str = ""
    score: float = 0.0

    def as_dict(self) -> dict:
        return {"url": self.url, "title": self.title,
                "description": self.description, "score": self.score}


@dataclass
class Page:
    """Eine geladene Seite."""

    url: str
    title: str = ""
    content: str = ""
    status: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.content) and not self.error

    def as_dict(self) -> dict:
        return {"url": self.url, "title": self.title, "status": self.status,
                "chars": len(self.content), "error": self.error}


@dataclass
class Fetcher:
    """Firecrawl-Client mit Retry.

    ``search_fn``/``scrape_fn`` sind injizierbar, damit Tests ohne Netzwerk
    laufen und der Orchestrator gegen Fehler getestet werden kann.
    """

    base_url: str = ""
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    search_fn: object | None = None
    scrape_fn: object | None = None
    calls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL).rstrip("/")
        if self.timeout == DEFAULT_TIMEOUT:
            try:
                self.timeout = float(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT))
            except ValueError:
                pass

    # -- oeffentliche API -------------------------------------------------

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        self.calls.append(f"search:{query}")
        if self.search_fn is not None:
            return list(self.search_fn(query, limit) or [])

        payload = {"query": query, "limit": limit}
        data = self._post("/v1/search", payload)
        if data is None:
            return []
        raw = data.get("data") if isinstance(data, dict) else None
        if isinstance(raw, dict):
            raw = raw.get("web") or raw.get("results") or []
        if not isinstance(raw, list):
            return []

        hits: list[SearchHit] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            if not url:
                continue
            hits.append(SearchHit(
                url=url,
                title=(item.get("title") or "")[:200],
                description=(item.get("description") or item.get("markdown") or "")[:1000],
                score=float(item.get("score") or 0.0),
            ))
        return hits[:limit]

    def scrape(self, url: str) -> Page:
        self.calls.append(f"scrape:{url}")
        if self.scrape_fn is not None:
            result = self.scrape_fn(url)
            return result if isinstance(result, Page) else Page(url=url, error="leer")

        data = self._post("/v1/scrape", {"url": url, "formats": ["markdown"]})
        if data is None:
            return Page(url=url, error="keine Antwort")

        body = data.get("data") if isinstance(data, dict) else None
        if not isinstance(body, dict):
            return Page(url=url, error="unerwartete Antwort")

        return Page(
            url=url,
            title=(body.get("metadata") or {}).get("title", "")[:200],
            content=(body.get("markdown") or "")[:20000],
            status=int(body.get("metadata", {}).get("statusCode") or 200),
        )

    # -- intern -----------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict | None:
        body = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}{path}"
        last_error = ""

        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                # 4xx ausser 429 sind nicht wiederholbar
                if 400 <= exc.code < 500 and exc.code != 429:
                    logger.warning("firecrawl %s: %s (kein Retry)", path, last_error)
                    return None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            except json.JSONDecodeError as exc:
                logger.warning("firecrawl %s: ungueltiges JSON (%s)", path, exc)
                return None

            if attempt < self.retries:
                time.sleep(BACKOFF_BASE ** attempt)

        logger.warning("firecrawl %s endgueltig fehlgeschlagen: %s", path, last_error)
        return None
