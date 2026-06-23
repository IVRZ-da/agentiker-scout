"""
tools/search.py — Suche und Status: research_search, research_status, research_stats.
"""

import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from scout._fmt import fmt_err, fmt_ok, fmt_research_status  # noqa: E402

from .base import (  # noqa: E402
    PLANS_DIR,
    RESULTS_DIR,
    _list_orphan_plans,
    _list_results,
    _read_json,
    _validate_research_id,
)

# ---------------------------------------------------------------------------
# BM25-ähnliche Volltextsuche (keine externen Dependencies)
# ---------------------------------------------------------------------------

# BM25 Parameter
_K1 = 1.5   # Term-Sättigungsfaktor
_B = 0.75   # Längen-Normalisierung


def _tokenize(text: str) -> list[str]:
    """Tokenisiert Text in einzelne Terme (Kleinschreibung, min 2 Zeichen)."""
    tokens = re.findall(r'[a-zäöüß0-9]+', text.lower())
    return [t for t in tokens if len(t) > 1]


def _bm25_score(query_terms: list[str], doc_text: str,
                doc_count: int, df_map: dict[str, int],
                avgdl: float) -> float:
    """
    Berechnet BM25-Score für ein Dokument gegen eine Query.

    BM25 Formel:
    score = sum(IDF(q) * (tf * (k1+1)) / (tf + k1 * (1 - b + b * dl/avgdl)))

    IDF(q) = log(1 + (N - df + 0.5) / (df + 0.5))
    """
    doc_tokens = _tokenize(doc_text)
    dl = len(doc_tokens)

    if dl == 0 or avgdl == 0:
        return 0.0

    # TF für Query-Terme im Dokument
    tf_counter = Counter(doc_tokens)
    doc_terms_set = set(doc_tokens)

    score = 0.0
    for term in query_terms:
        if term not in doc_terms_set:
            continue

        tf = tf_counter.get(term, 0)
        df = df_map.get(term, 1)

        # IDF
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))

        # TF-Normalisierung
        tf_norm = (tf * (_K1 + 1)) / (tf + _K1 * (1 - _B + _B * (dl / avgdl)))

        score += idf * tf_norm

    return score


def _build_index() -> tuple[list[dict], dict[str, int], float, int]:
    """
    Baut einen Suchindex über alle Ergebnisse.

    Returns: (dokumente, df_map, avgdl, N)
    """
    documents = []
    term_doc_counts = Counter()  # df: in wie vielen Dokumenten kommt ein Term vor
    total_terms = 0

    search_dir = RESULTS_DIR if RESULTS_DIR.exists() else None
    if not search_dir:
        return [], {}, 0.0, 0

    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        data = _read_json(f)
        if not data:
            continue

        # Suchbaren Text aus allen relevanten Feldern bauen
        searchable_parts = [
            data.get("query", ""),
            data.get("summary", ""),
        ]
        # Findings
        for f_item in data.get("findings", []):
            if isinstance(f_item, dict):
                searchable_parts.append(f_item.get("finding", ""))
            elif isinstance(f_item, str):
                searchable_parts.append(f_item)
        # Sources
        for s in data.get("sources", []):
            if isinstance(s, dict):
                searchable_parts.append(s.get("title", ""))
                searchable_parts.append(s.get("url", ""))

        doc_text = " ".join(searchable_parts)
        doc_tokens = _tokenize(doc_text)
        total_terms += len(doc_tokens)

        # Unique Terms für DF
        for t in set(doc_tokens):
            term_doc_counts[t] += 1

        documents.append({
            "data": data,
            "stem": f.stem,
            "text": doc_text,
        })

    N = len(documents)
    avgdl = total_terms / N if N > 0 else 0.0
    df_map = dict(term_doc_counts)

    return documents, df_map, avgdl, N


# ---------------------------------------------------------------------------
# research_search
# ---------------------------------------------------------------------------

def research_search(args: dict, **kwargs) -> str:
    """
    Durchsucht gespeicherte Research-Ergebnisse mit BM25-Volltextsuche.

    Unterstützt facettierte Suche via tags, status, date_from, date_to.
    Ergebnisse werden nach Relevanz sortiert.
    """
    query = args.get("query", "").strip()
    limit = max(1, min(50, int(args.get("limit", 5))))
    filter_tags = args.get("tags", None)
    filter_status = args.get("status", None)
    date_from = args.get("date_from", None)
    date_to = args.get("date_to", None)

    # Filter normalisieren
    if filter_tags is not None:
        if isinstance(filter_tags, str):
            filter_tags = [filter_tags]
        filter_tags = [t.strip().lower().replace(" ", "-") for t in filter_tags if t]

    if filter_status is not None:
        filter_status = filter_status.strip().lower()

    if not query and not filter_tags and not filter_status and not date_from and not date_to:
        results = _list_results()
        return fmt_ok({
            "results": results[:limit],
            "total": len(results),
            "query": "",
            "instruction": (
                "Nutze honcho_search(query='...', peer='research') für semantische "
                "Suche in Honcho — dort sind alle Research-Conclusions gespeichert."
            ),
        })

    # Index bauen
    documents, df_map, avgdl, N = _build_index()
    query_terms = _tokenize(query) if query else []

    scored = []
    for doc in documents:
        data = doc["data"]

        # Tag-Filter
        if filter_tags is not None:
            data_tags = [t.strip().lower() for t in (data.get("tags") or [])]
            if not any(t in data_tags for t in filter_tags):
                continue

        # Status-Filter
        if filter_status is not None:
            doc_status = data.get("status", "").strip().lower()
            if doc_status != filter_status:
                continue

        # Datum-Filter
        if date_from or date_to:
            saved_at = data.get("saved_at", "")
            if saved_at:
                try:
                    dt = datetime.fromisoformat(saved_at)
                    if date_from:
                        dt_from = datetime.fromisoformat(date_from)
                        if dt < dt_from:
                            continue
                    if date_to:
                        dt_to = datetime.fromisoformat(date_to)
                        if dt > dt_to:
                            continue
                except (ValueError, TypeError) as e:
                    logger.debug("date filter parse failed: %s", e)

        # BM25-Score
        score = 0.0
        if query_terms and N > 0:
            score = _bm25_score(query_terms, doc["text"], N, df_map, avgdl)

        scored.append((score, data, doc["stem"]))

    # Sortieren: BM25-Score absteigend, dann saved_at absteigend
    scored.sort(key=lambda x: (-x[0], x[1].get("saved_at", "")), reverse=False)

    # Results formatieren
    matches = []
    for score, data, stem in scored:
        if query and score < 0.01:
            continue  # Nur relevante Ergebnisse bei Query
        matches.append({
            "research_id": data.get("id", stem),
            "query": data.get("query", ""),
            "summary": (data.get("summary", "") or "")[:300],
            "status": data.get("status", ""),
            "tags": data.get("tags", []),
            "score": round(score, 3) if score > 0 else None,
            "timestamp": data.get("saved_at", ""),
            "findings_count": len(data.get("findings", [])),
            "sources_count": len(data.get("sources", [])),
        })

    # Orphan-Plans (nur wenn keine Filter aktiv)
    plan_fallback = []
    if not filter_tags and not filter_status:
        for f in sorted(PLANS_DIR.glob("*.json"), reverse=True):
            rid = f.stem
            if not (RESULTS_DIR / f"{rid}.json").exists():
                data = _read_json(f)
                if data:
                    if query:
                        p_text = f"{data.get('query', '')} {data.get('summary', '')}"
                        p_terms = _tokenize(query)
                        if p_terms:
                            p_score = _bm25_score(p_terms, p_text, N, df_map, avgdl)
                            if p_score < 0.01:
                                continue
                    plan_fallback.append({
                        "research_id": rid,
                        "query": data.get("query", ""),
                        "status": data.get("status", "planned"),
                        "timestamp": data.get("created_at", ""),
                        "message": "Recherche gestartet aber noch nicht abgeschlossen.",
                    })

    # Versuche Honcho-Suche (via Registry, lose Kopplung)
    try:
        from tools.registry import registry
        honcho_search_entry = registry.get_entry("honcho_search")
        honcho_available = honcho_search_entry is not None
    except Exception:
        honcho_available = False

    return fmt_ok({
        "results": matches[:limit],
        "in_progress": plan_fallback[:limit] if plan_fallback else [],
        "total": len(matches),
        "query": query,
        "bm25_enabled": True,
        "honcho_search_available": honcho_available,
        "instruction": (
            "Tipp: Nutze honcho_search(query=..., peer='research') für semantische Suche "
            "in Honcho. Dort sind alle Research-Conclusions gespeichert, "
            "die über die reine Text-Suche hinausgehen."
        ),
    })


# ---------------------------------------------------------------------------
# research_status
# ---------------------------------------------------------------------------

def research_status(args: dict, **kwargs) -> str:
    """Zeigt Status und Details einer Recherche an."""
    research_id = args.get("research_id", "").strip()
    show_orphans = args.get("show_orphans", False)

    if research_id:
        err = _validate_research_id(research_id)
        if err:
            return fmt_err(err)

    if not research_id and not show_orphans:
        return fmt_err("research_id ist erforderlich (oder show_orphans=true)")

    if show_orphans and not research_id:
        orphans = _list_orphan_plans()
        return fmt_research_status({
            "orphans_count": len(orphans),
            "orphans": orphans[:20],
            "message": (
                f"{len(orphans)} hängengebliebene Recherchen gefunden (gestartet mit "
                f"research_start aber nie mit research_save gespeichert). "
                f"Nutze research_cleanup(action='plans') zum Bereinigen."
            ),
        })

    if not research_id:
        return fmt_err("research_id ist erforderlich")

    plan_path = PLANS_DIR / f"{research_id}.json"
    if plan_path.exists():
        plan = _read_json(plan_path)
        return fmt_research_status({
            "research_id": research_id,
            "status": plan.get("status", "planned"),
            "query": plan.get("query", ""),
            "depth": plan.get("depth", 0),
            "created_at": plan.get("created_at", ""),
            "message": "Recherche ist noch in Planung oder wird gerade durchgeführt. Ergebnisse mit research_save speichern wenn fertig.",
        })

    result_path = RESULTS_DIR / f"{research_id}.json"
    if result_path.exists():
        result = _read_json(result_path)

        # Dauer berechnen
        created = result.get("created_at", "")
        saved = result.get("saved_at", "")
        duration_str = ""
        if created and saved:
            try:
                from datetime import datetime
                dt_c = datetime.fromisoformat(created)
                dt_s = datetime.fromisoformat(saved)
                delta = dt_s - dt_c
                secs = int(delta.total_seconds())
                if secs < 60:
                    duration_str = f"{secs}s"
                elif secs < 3600:
                    duration_str = f"{secs // 60}m {secs % 60}s"
                else:
                    hours = secs // 3600
                    mins = (secs % 3600) // 60
                    duration_str = f"{hours}h {mins}m"
            except (ValueError, TypeError) as e:
                logger.debug("duration parse failed: %s", e)

        return fmt_research_status({
            "research_id": research_id,
            "status": result.get("status", "unknown"),
            "query": result.get("query", ""),
            "depth": result.get("depth", 0),
            "summary": (result.get("summary", "") or "")[:500],
            "tags": result.get("tags", []),
            "findings_count": len(result.get("findings", [])),
            "sources_count": len(result.get("sources", [])),
            "duration": duration_str or "unbekannt",
            "merged_from": result.get("_merged_from", []),
            "saved_at": saved,
            "updated_at": result.get("updated_at", ""),
            "message": "Recherche abgeschlossen. Ergebnisse via honcho_search in Honcho verfügbar.",
        })

    return fmt_research_status({
        "research_id": research_id,
        "status": "not_found",
        "message": f"Keine Recherche mit ID '{research_id}' gefunden.",
    })


# ---------------------------------------------------------------------------
# research_stats
# ---------------------------------------------------------------------------

def research_stats(args: dict, **kwargs) -> str:
    """Zeigt Metriken und Statistiken über alle Recherchen."""
    results = _list_results()
    orphans = _list_orphan_plans()

    total = len(results)
    orphan_count = len(orphans)

    # Status-Verteilung
    status_dist = {}
    for r in results:
        s = r.get("status", "unknown")
        status_dist[s] = status_dist.get(s, 0) + 1

    # Tag-Verteilung
    tag_dist = {}
    for r_path in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        data = _read_json(r_path)
        if data:
            for t in (data.get("tags") or []):
                tag_dist[t] = tag_dist.get(t, 0) + 1
    top_tags = sorted(tag_dist.items(), key=lambda x: -x[1])[:10]

    # Quellen-Statistik
    total_sources = sum(r.get("sources_count", 0) for r in results)
    total_findings = sum(r.get("findings_count", 0) for r in results)

    # Altersverteilung (in Tagen)
    age_dist = {"< 1 Tag": 0, "1-7 Tage": 0, "7-30 Tage": 0, "> 30 Tage": 0}
    now = datetime.now(timezone.utc)
    for r in results:
        ts = r.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                days = (now - dt).days
                if days < 1:
                    age_dist["< 1 Tag"] += 1
                elif days < 7:
                    age_dist["1-7 Tage"] += 1
                elif days < 30:
                    age_dist["7-30 Tage"] += 1
                else:
                    age_dist["> 30 Tage"] += 1
            except (ValueError, TypeError) as e:
                logger.debug("age distribution parse failed: %s", e)

    return fmt_ok({
        "total_researches": total,
        "orphan_plans": orphan_count,
        "status_distribution": status_dist,
        "top_tags": dict(top_tags),
        "total_sources": total_sources,
        "total_findings": total_findings,
        "age_distribution": age_dist,
        "instruction": (
            f"Insgesamt {total} Recherchen, {orphan_count} Orphan-Plans. "
            f"{total_findings} Findings aus {total_sources} Quellen. "
            f"Top-Tags: {', '.join(f'{t}({c})' for t,c in top_tags[:5]) if top_tags else 'keine'}"
        ),
    })
