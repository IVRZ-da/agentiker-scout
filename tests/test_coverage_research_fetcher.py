"""Fehler- und Parsing-Pfade in ``research/fetcher.py``.

Der Fetcher degradiert Netzwerkfehler bewusst zu leeren Ergebnissen — genau
diese Pfade waren bisher ungetestet (bisher nur „Host nicht erreichbar", also
``URLError`` beim Verbindungsaufbau). Hier wird
``urllib.request.urlopen`` durch einen Fake ersetzt; es geht kein Request über
das Netz, ``time.sleep`` wird gepatcht (kein echter Backoff-Wartezeit).
"""

from __future__ import annotations

import json
import urllib.error

from scout.research import fetcher as fetcher_mod
from scout.research.fetcher import Fetcher, Page


class _FakeResponse:
    """Minimaler Context-Manager wie ihn urlopen liefert."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _urlopen_returning(payload: dict):
    def fake(request, timeout=None):  # noqa: ARG001
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    return fake


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://firecrawl.test", code, "kaputt", {}, None)


def _client(retries: int = 0) -> Fetcher:
    return Fetcher(base_url="http://firecrawl.test", timeout=1.0, retries=retries)


# ---------------------------------------------------------------------------
# search(): Antwort-Parsing
# ---------------------------------------------------------------------------

def test_search_parses_web_hits_and_skips_unusable_items(monkeypatch):
    payload = {"data": {"web": [
        {"url": " https://a.test ", "title": "A", "markdown": "lang", "score": 0.9},
        "kein-dict",
        {"url": ""},
        {"title": "ohne url"},
    ]}}
    monkeypatch.setattr(fetcher_mod.urllib.request, "urlopen", _urlopen_returning(payload))

    client = _client()
    hits = client.search("frage", limit=5)

    assert [h.url for h in hits] == ["https://a.test"]
    assert hits[0].title == "A"
    assert hits[0].description == "lang"  # fallback auf markdown
    assert hits[0].score == 0.9
    assert client.calls == ["search:frage"]


# ---------------------------------------------------------------------------
# _post(): Fehlerpfade
# ---------------------------------------------------------------------------

def test_client_error_is_not_retried(monkeypatch):
    calls: list[int] = []

    def fake(request, timeout=None):  # noqa: ARG001
        calls.append(1)
        raise _http_error(404)

    monkeypatch.setattr(fetcher_mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(fetcher_mod.time, "sleep", lambda _s: None)

    client = _client(retries=2)

    assert client.scrape("https://a.test/x") == Page(url="https://a.test/x", error="keine Antwort")
    assert len(calls) == 1


def test_invalid_json_returns_empty_without_retry(monkeypatch):
    calls: list[int] = []

    def fake(request, timeout=None):  # noqa: ARG001
        calls.append(1)
        return _FakeResponse(b"kein json")

    monkeypatch.setattr(fetcher_mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(fetcher_mod.time, "sleep", lambda _s: None)

    assert _client(retries=2).search("frage") == []
    assert len(calls) == 1


def test_server_error_is_retried_with_backoff(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []

    def fake(request, timeout=None):  # noqa: ARG001
        calls.append(1)
        raise _http_error(503)

    monkeypatch.setattr(fetcher_mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(fetcher_mod.time, "sleep", sleeps.append)

    assert _client(retries=1).search("frage") == []

    assert len(calls) == 2
    # Backoff nur zwischen den Versuchen, nicht nach dem letzten.
    assert sleeps == [1.0]
