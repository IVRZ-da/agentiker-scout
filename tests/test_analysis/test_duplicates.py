"""Tests für analysis_duplicates.
"""
from __future__ import annotations

from scout.analysis.tools.duplicates import analysis_duplicates_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisDuplicates:
    def test_requires_path(self):
        result = analysis_duplicates_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "summary" in parsed
        assert "path" in parsed

    def test_custom_params(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "min_lines": 3,
            "similarity_threshold": 0.9,
            "top_n": 5,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"

    def test_path_traversal_returns_error(self):
        """Path-Traversal → fmt_err."""
        result = analysis_duplicates_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_control_chars_returns_error(self):
        """Control-Zeichen im Pfad → fmt_err."""
        result = analysis_duplicates_tool({
            "path": "/good/pa\x00th",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_size(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_duplicates_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_has_findings_key(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert "findings" in parsed

    # ─── Path resolution error (line 30) ──────────────────────────────

    def test_path_resolution_error(self, monkeypatch):
        """_validate_and_resolve_path returns error → fmt_err."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: ("directory not allowed", None)
        )

        result = analysis_duplicates_tool({"path": "/some/path"})
        parsed = _parse(result)
        assert parsed.get("status") == "error"
        assert "directory not allowed" in (parsed.get("raw", "") or str(parsed))

    # ─── Exception in _call_tool (lines 61-63) ────────────────────────

    def test_call_tool_exception(self, monkeypatch):
        """_call_tool wirft Exception → fmt_err."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )

        def _raise(*a, **kw):
            raise RuntimeError("internal scanner error")

        monkeypatch.setattr(dup_mod, "_call_tool", _raise)

        result = analysis_duplicates_tool({"path": "/some/path"})
        parsed = _parse(result)
        assert parsed.get("status") == "error"
        # fmt_err returns valid JSON → check the raw result string
        assert "internal scanner error" in result

    # ─── Findings display (lines 70-75) ───────────────────────────────

    def test_with_findings_shows_top_funde(self, monkeypatch):
        """Erfolg mit findings → 'Top-Funde' in summary."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        monkeypatch.setattr(
            dup_mod,
            "_call_tool",
            lambda *a, **kw: {
                "duplicates": [
                    {
                        "file": "a.py",
                        "lines": "10-20",
                        "similarity": 0.95,
                        "content": "def foo(): pass",
                    },
                    {
                        "file": "b.py",
                        "lines": "30-40",
                        "similarity": 0.82,
                        "content": "def bar(): return 42",
                    },
                ]
            },
        )

        result = analysis_duplicates_tool({"path": "/some/path"})
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        findings = parsed.get("findings", [])
        assert len(findings) == 2
        assert findings[0]["file"] == "a.py"
        assert findings[0]["similarity"] == 0.95
        assert findings[1]["file"] == "b.py"
        summary = parsed.get("summary", "")
        assert "Top-Funde" in summary
        assert "a.py" in summary
        assert "b.py" in summary
        assert "95%" in summary or "Ähnlichkeit" in summary

    def test_with_findings_uses_fallback_keys(self, monkeypatch):
        """Findings aus 'data'- und 'blocks'-Fallback-Keys."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        monkeypatch.setattr(
            dup_mod,
            "_call_tool",
            lambda *a, **kw: {
                "data": [
                    {
                        "path": "c.py",
                        "line_range": "50-60",
                        "score": 0.75,
                        "code": "if True: pass",
                    },
                ]
            },
        )

        result = analysis_duplicates_tool({"path": "/some/path"})
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        findings = parsed.get("findings", [])
        assert len(findings) == 1
        assert findings[0]["file"] == "c.py"
        assert findings[0]["lines"] == "50-60"
        assert findings[0]["similarity"] == 0.75
        assert "True" in findings[0]["content_preview"]

    def test_empty_findings_no_top_funde(self, monkeypatch):
        """Keine findings → kein 'Top-Funde' in summary."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        monkeypatch.setattr(
            dup_mod, "_call_tool", lambda *a, **kw: {"duplicates": []}
        )

        result = analysis_duplicates_tool({"path": "/some/path"})
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert parsed.get("findings") == []
        assert "Top-Funde" not in parsed.get("summary", "")

    # ─── Clamping (lines 20-22) ───────────────────────────────────────

    def test_min_lines_clamped_to_at_least_3(self, monkeypatch):
        """min_lines=1 → wird auf 3 geclamped."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        call_args = {}

        def capture(*a, **kw):
            call_args.update(kw)
            return None

        monkeypatch.setattr(dup_mod, "_call_tool", capture)

        analysis_duplicates_tool({"path": "/x", "min_lines": 1})
        assert call_args.get("min_lines") == 3

    def test_similarity_clamped_low(self, monkeypatch):
        """similarity_threshold=0.1 → wird auf 0.5 geclamped."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        call_args = {}

        def capture(*a, **kw):
            call_args.update(kw)
            return None

        monkeypatch.setattr(dup_mod, "_call_tool", capture)

        analysis_duplicates_tool({"path": "/x", "similarity_threshold": 0.1})
        assert call_args.get("similarity_threshold") == 0.5

    def test_similarity_clamped_high(self, monkeypatch):
        """similarity_threshold=1.5 → wird auf 1.0 geclamped."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        call_args = {}

        def capture(*a, **kw):
            call_args.update(kw)
            return None

        monkeypatch.setattr(dup_mod, "_call_tool", capture)

        analysis_duplicates_tool({"path": "/x", "similarity_threshold": 1.5})
        assert call_args.get("similarity_threshold") == 1.0

    def test_top_n_clamped_to_max_50(self, monkeypatch):
        """top_n=100 → wird auf 50 geclamped."""
        import scout.analysis.tools.duplicates as dup_mod

        monkeypatch.setattr(dup_mod, "_validate_path", lambda p: None)
        monkeypatch.setattr(
            dup_mod, "_validate_and_resolve_path", lambda p: (None, "/resolved")
        )
        call_args = {}

        def capture(*a, **kw):
            call_args.update(kw)
            return None

        monkeypatch.setattr(dup_mod, "_call_tool", capture)

        analysis_duplicates_tool({"path": "/x", "top_n": 100})
        assert call_args.get("top_n") == 50
