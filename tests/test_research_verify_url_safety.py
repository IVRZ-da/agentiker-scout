"""research_verify prüft nur öffentliche http/https-Ziele (Review #157391 Punkt 3).

Vorher ging für jede gespeicherte URL ein HEAD-Request raus — auch für file://,
LAN-Adressen und Cloud-Metadata-Endpunkte. Jetzt gilt Hermes' eigene Policy
(`tools.url_safety.is_safe_url`), und Redirects werden nicht verfolgt.
"""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from scout.research.tools import crud


@pytest.fixture
def result_with_urls(tmp_path, monkeypatch):
    """Eine gespeicherte Recherche mit frei waehlbaren Quellen-URLs anlegen."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monkeypatch.setattr(crud, "RESULTS_DIR", results_dir)

    def _make(urls: list[str]) -> str:
        rid = "2026-11-20-abcdef"
        (results_dir / f"{rid}.json").write_text(
            json.dumps({"id": rid, "query": "q", "summary": "s",
                        "sources": [{"url": u} for u in urls], "findings": []}),
            encoding="utf-8",
        )
        return rid

    return _make


def _verify(rid: str) -> dict:
    return json.loads(crud.research_verify({"research_id": rid}))


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/x",
    "gopher://example.com/",
    "javascript:alert(1)",
])
def test_non_http_schemes_are_refused_without_request(result_with_urls, url):
    rid = result_with_urls([url])
    with patch.object(crud._VERIFY_OPENER, "open") as opener:
        payload = _verify(rid)
    opener.assert_not_called()
    assert payload["details"][0]["status"] == "refused"
    assert "nicht erlaubt" in payload["details"][0]["error"]


@pytest.mark.parametrize("url", [
    "http://localhost:8080/status",
    "http://127.0.0.1/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://10.0.0.5/internal",
    "http://[::1]/local",
])
def test_private_and_metadata_targets_are_refused(result_with_urls, url):
    rid = result_with_urls([url])
    with patch.object(crud._VERIFY_OPENER, "open") as opener:
        payload = _verify(rid)
    opener.assert_not_called()
    assert payload["details"][0]["status"] == "refused"


def test_public_url_is_requested(result_with_urls):
    rid = result_with_urls(["https://example.com/article"])
    response = MagicMock(status=200)
    with patch.object(crud._VERIFY_OPENER, "open", return_value=response) as opener, \
         patch.object(crud, "_safe_url_checker", return_value=lambda url: True):
        payload = _verify(rid)
    opener.assert_called_once()
    assert payload["details"][0]["status"] == "ok"


def test_redirects_are_not_followed(result_with_urls):
    import urllib.error

    rid = result_with_urls(["https://example.com/moved"])
    err = urllib.error.HTTPError("https://example.com/moved", 302, "Found", {}, None)
    with patch.object(crud._VERIFY_OPENER, "open", side_effect=err), \
         patch.object(crud, "_safe_url_checker", return_value=lambda url: True):
        payload = _verify(rid)
    detail = payload["details"][0]
    assert detail["status"] == "redirect"
    assert detail["http_code"] == 302
    assert "nicht verfolgt" in detail["note"]


def test_fallback_checker_blocks_private_literals():
    is_safe = crud._fallback_is_safe_url
    assert is_safe("https://example.com/x") is True
    assert is_safe("http://127.0.0.1/") is False
    assert is_safe("http://169.254.169.254/") is False
    assert is_safe("file:///etc/passwd") is False


def test_safe_url_checker_uses_host_module_when_present(monkeypatch):
    """Im Hermes-Kontext kommt die Policy aus tools.url_safety, nicht aus dem Fallback."""
    sentinel = lambda url: True  # noqa: E731
    monkeypatch.setitem(sys.modules, "tools.url_safety",
                        types.SimpleNamespace(is_safe_url=sentinel))
    assert crud._safe_url_checker() is sentinel


def test_safe_url_checker_falls_back_without_host_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "tools.url_safety", None)
    assert crud._safe_url_checker() is crud._fallback_is_safe_url
