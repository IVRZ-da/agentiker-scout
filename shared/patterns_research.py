"""Research-Patterns — wiederverwendbare Recherche-Vorlagen.

Jedes Pattern definiert: Quellen-Typen, Extraktions-Schema, Suchstrategie.
Kann von research_start(pattern=...) geladen werden.
"""

from __future__ import annotations

from typing import Any

# ─── Research-Pattern-Typen ───────────────────────────────────────────────

RESEARCH_PATTERNS: dict[str, dict[str, Any]] = {
    "eu-cbd-regulation": {
        "name": "EU-Länder CBD-Regularien",
        "category": "regulatory",
        "description": "CBD-Gesetzeslage, THC-Grenzwerte und Lizenzanforderungen in EU-Ländern.",
        "strategy": {
            "depth": 3,
            "prefer_official": True,
            "max_sources": 10,
        },
        "sources": [
            {"type": "gov", "hint": "Gesetzesportale (z.B. legifrance.gouv.fr, bundesgesundheitsministerium.de)"},
            {"type": "eu", "hint": "ECDD, EMA, EU-Kommission"},
            {"type": "news", "hint": "Aktuelle Nachrichten zur Gesetzeslage"},
            {"type": "associations", "hint": "Branchenverbände (EIHA, Cannabis Industry Council)"},
        ],
        "schema": {
            "type": "object",
            "properties": {
                "legal_status": {"type": "string"},
                "thc_limit": {"type": "string"},
                "license_required": {"type": "boolean"},
                "novel_food_status": {"type": "string"},
                "prescription_required": {"type": "boolean"},
                "last_updated": {"type": "string"},
            },
        },
        "search_queries": [
            "{country} CBD legal status",
            "{country} cannabis regulation law",
            "{country} THC limit food",
            "EU novel food CBD status {country}",
        ],
    },
    "competitor-analysis": {
        "name": "Wettbewerbsanalyse E-Commerce",
        "category": "competitive",
        "description": "Preise, Features, Tech-Stack und Marketing eines Mitbewerbers analysieren.",
        "strategy": {
            "depth": 2,
            "prefer_official": True,
            "max_sources": 8,
        },
        "sources": [
            {"type": "website", "hint": "Shop-Startseite + Produktseiten"},
            {"type": "pricing", "hint": "Preisstruktur, Staffeln, Rabatte"},
            {"type": "tech", "hint": "BuiltWith, Wappalyzer, StackShare"},
            {"type": "reviews", "hint": "Trustpilot, Google Reviews, Reddit"},
        ],
        "schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "website": {"type": "string"},
                "business_model": {"type": "string"},
                "target_market": {"type": "string"},
                "product_categories": {"type": "array", "items": {"type": "string"}},
                "pricing_tiers": {"type": "array", "items": {"type": "string"}},
                "tech_stack": {"type": "array", "items": {"type": "string"}},
                "estimated_traffic": {"type": "string"},
                "social_media": {"type": "array", "items": {"type": "string"}},
                "rating": {"type": "number"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
            },
        },
        "search_queries": [
            "{company} {industry}",
            "{company} pricing",
            "{company} reviews",
            "builtwith {url}",
        ],
    },
    "tech-research": {
        "name": "Technologie-Recherche",
        "category": "technical",
        "description": "Framework, Bibliothek oder Tool bewerten: Features, Vergleich, Erfahrungen.",
        "strategy": {
            "depth": 3,
            "prefer_official": True,
            "max_sources": 12,
        },
        "sources": [
            {"type": "docs", "hint": "Offizielle Dokumentation + GitHub README"},
            {"type": "comparison", "hint": "Vergleichsseiten, Benchmark-Studien"},
            {"type": "community", "hint": "Stack Overflow, Reddit, DEV.to"},
            {"type": "production", "hint": "Wer setzt es ein? Case Studies"},
        ],
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "type": {"type": "string"},
                "license": {"type": "string"},
                "github_stars": {"type": "number"},
                "key_features": {"type": "array", "items": {"type": "string"}},
                "pros": {"type": "array", "items": {"type": "string"}},
                "cons": {"type": "array", "items": {"type": "string"}},
                "alternatives": {"type": "array", "items": {"type": "string"}},
                "learning_curve": {"type": "string"},
                "community_size": {"type": "string"},
            },
        },
        "search_queries": [
            "{technology} review",
            "{technology} vs {alternative}",
            "{technology} production experience",
            "{technology} getting started tutorial",
        ],
    },
    "news-monitoring": {
        "name": "News-Monitoring (Cannabis-Markt)",
        "category": "news",
        "description": "Aktuelle Nachrichten zu Cannabis-Legalisierung, Marktentwicklung und Unternehmen.",
        "strategy": {
            "depth": 1,
            "prefer_official": False,
            "max_sources": 5,
        },
        "sources": [
            {"type": "news", "hint": "Google News, Yahoo Finance, Reuters"},
            {"type": "press", "hint": "Pressemitteilungen, Unternehmens-Blogs"},
            {"type": "social", "hint": "Reddit r/cannabis, Twitter/X"},
        ],
        "schema": {
            "type": "object",
            "properties": {
                "headlines": {"type": "array", "items": {"type": "string"}},
                "key_developments": {"type": "array", "items": {"type": "string"}},
                "companies_mentioned": {"type": "array", "items": {"type": "string"}},
                "market_trends": {"type": "array", "items": {"type": "string"}},
                "source_urls": {"type": "array", "items": {"type": "string"}},
            },
        },
        "search_queries": [
            "cannabis industry news {date}",
            "cannabis legalization update",
            "CBD market developments",
        ],
    },
}


def get_research_pattern(pattern_id: str) -> dict[str, Any] | None:
    """Get a research pattern by ID."""
    return RESEARCH_PATTERNS.get(pattern_id)


def get_research_patterns_by_category(category: str) -> list[dict[str, Any]]:
    """Get research patterns filtered by category."""
    return [
        p for p in RESEARCH_PATTERNS.values()
        if p.get("category") == category
    ]


def list_research_patterns() -> list[dict[str, Any]]:
    """List all research patterns with metadata."""
    return [
        {"id": pid, "name": p["name"], "category": p["category"], "description": p["description"]}
        for pid, p in RESEARCH_PATTERNS.items()
    ]


def list_categories() -> list[str]:
    """List available research pattern categories."""
    return sorted({p.get("category", "other") for p in RESEARCH_PATTERNS.values()})
