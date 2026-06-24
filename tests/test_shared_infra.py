"""Tests für shared/cache.py + shared/registry.py + shared/patterns.py."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from scout.shared.cache import TTLCache, clear_all
from scout.shared.registry import Entry, Registry

# ======================================================================
# TTLCache
# ======================================================================

class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache[int](ttl=60.0)
        cache.set("key1", 42)
        assert cache.get("key1") == 42

    def test_get_missing(self):
        cache = TTLCache[str](ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_expired_returns_none(self):
        cache = TTLCache[int](ttl=0.01)  # 10ms TTL
        cache.set("soon_gone", 99)
        time.sleep(0.02)
        assert cache.get("soon_gone") is None

    def test_invalidate(self):
        cache = TTLCache[str](ttl=60.0)
        cache.set("temp", "value")
        cache.invalidate("temp")
        assert cache.get("temp") is None

    def test_invalidate_missing(self):
        """invalidate auf nicht-existierenden Key wirft keinen Fehler."""
        cache = TTLCache[str](ttl=60.0)
        cache.invalidate("doesnt_exist")  # kein Crash

    def test_clear(self):
        cache = TTLCache[int](ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_size(self):
        cache = TTLCache[str](ttl=60.0)
        assert cache.size == 0
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.size == 2

    def test_maxsize_eviction(self):
        cache = TTLCache[int](ttl=60.0, maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # sollte "a" evicten
        assert cache.get("a") is None
        assert cache.get("d") == 4
        assert cache.size == 3

    def test_lru_reorder(self):
        cache = TTLCache[int](ttl=60.0, maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # LRU refresh
        cache.set("c", 3)  # sollte "b" evicten (LRU ist "b")
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3


class TestClearAll:
    def test_clears_all_global_caches(self):
        from scout.shared.cache import analysis_cache, intent_cache, pattern_cache, research_cache
        intent_cache.set("x", "1")
        pattern_cache.set("y", [{"a": 1}])
        analysis_cache.set("z", "data")
        research_cache.set("w", "info")
        clear_all()
        assert intent_cache.get("x") is None
        assert pattern_cache.get("y") is None
        assert analysis_cache.get("z") is None
        assert research_cache.get("w") is None


# ======================================================================
# Registry
# ======================================================================

class TestRegistry:
    def test_register_and_get(self):
        reg = Registry()
        reg.register("tool1", handler=lambda a: "ok", schema={"type": "object"})
        entry = reg.get_entry("tool1")
        assert entry is not None
        assert entry.handler is not None

    def test_get_missing(self):
        reg = Registry()
        assert reg.get_entry("missing") is None

    def test_dispatch(self):
        reg = Registry()
        reg.register("greet", handler=lambda a: f"Hello {a.get('name', '')}")
        result = reg.dispatch("greet", {"name": "World"})
        assert result == "Hello World"

    def test_dispatch_missing_tool(self):
        reg = Registry()
        result = reg.dispatch("missing")
        assert result is None

    def test_dispatch_no_handler(self):
        reg = Registry()
        reg.register("empty", schema={})
        result = reg.dispatch("empty")
        assert result is None

    def test_deregister(self):
        reg = Registry()
        reg.register("temp", handler=lambda a: "x")
        reg.deregister("temp")
        assert reg.get_entry("temp") is None

    def test_deregister_missing(self):
        """deregister auf nicht-existierendem Namen wirft keinen Fehler."""
        reg = Registry()
        reg.deregister("never_registered")  # kein Crash

    def test_get_all_tool_names(self):
        reg = Registry()
        reg.register("a", handler=lambda a: "")
        reg.register("b", handler=lambda a: "")
        names = reg.get_all_tool_names()
        assert "a" in names
        assert "b" in names


class TestEntry:
    def test_defaults(self):
        entry = Entry()
        assert entry.handler is None
        assert entry.schema == {}

    def test_with_values(self):
        def handler_fn(a):
            return ""
        entry = Entry(handler=handler_fn, schema={"type": "object"})
        assert entry.handler is handler_fn
        assert entry.schema == {"type": "object"}


# ======================================================================
# shared/patterns — File-basierte Test
# ======================================================================

class TestPatterns:
    def test_save_new_pattern(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import save_pattern
                pid = save_pattern({"name": "test pattern", "scan_query": "test()"})
                assert pid == "P001"

    def test_save_and_load(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import _load_patterns as lp
                from scout.shared.patterns import save_pattern
                pid = save_pattern({"name": "my pattern", "scan_query": "find()"})
                loaded = lp()
                assert len(loaded) == 1
                assert loaded[0]["pattern_id"] == pid

    def test_update_existing(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import _load_patterns as lp
                from scout.shared.patterns import save_pattern
                pid = save_pattern({"name": "original"})
                save_pattern({"pattern_id": pid, "name": "updated"})
                loaded = lp()
                assert len(loaded) == 1
                assert loaded[0]["name"] == "updated"

    def test_load_empty(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import _load_patterns as lp
                assert lp() == []

    def test_load_broken_json(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                (tmp_path / "shared_patterns.json").write_text("{broken")
                from scout.shared.patterns import _load_patterns as lp
                assert lp() == []

    def test_get_pattern(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import get_pattern, save_pattern
                pid = save_pattern({"name": "xss", "category": "security"})
                result = get_pattern(pid)
                assert result is not None
                assert result["name"] == "xss"

    def test_get_pattern_not_found(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import get_pattern
                assert get_pattern("NONEXISTENT") is None

    def test_get_patterns_for_analysis(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import get_patterns_for_analysis, save_pattern
                save_pattern({"name": "python pat", "scan_language": "python"})
                save_pattern({"name": "ts pat", "scan_language": "typescript"})
                results = get_patterns_for_analysis(scan_language="python")
                assert len(results) == 1
                assert results[0]["name"] == "python pat"

    def test_get_patterns_for_analysis_no_filter(self, tmp_path: Path):
        with patch("scout.shared.patterns.PATTERNS_DIR", tmp_path):
            with patch("scout.shared.patterns.SHARED_PATTERNS_FILE", tmp_path / "shared_patterns.json"):
                from scout.shared.patterns import get_patterns_for_analysis, save_pattern
                save_pattern({"name": "generic pat"})
                results = get_patterns_for_analysis()
                assert len(results) == 1


class TestPatternsResearch:
    def test_research_patterns_dict_not_empty(self):
        from scout.shared.patterns_research import RESEARCH_PATTERNS
        assert len(RESEARCH_PATTERNS) > 0
        assert "eu-cbd-regulation" in RESEARCH_PATTERNS

    def test_research_pattern_has_required_keys(self):
        from scout.shared.patterns_research import RESEARCH_PATTERNS
        for pid, pat in RESEARCH_PATTERNS.items():
            assert "name" in pat
            assert "category" in pat
            assert "description" in pat
