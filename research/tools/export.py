"""
tools/export.py — Export und Analyse: research_export, research_compare, research_synthesize.
"""

import json
import re
from collections import Counter

from scout._fmt import fmt_code, fmt_markdown, fmt_ok

from .base import (
    PLANS_DIR,
    RESULTS_DIR,
    _err,
    _list_results,
    _now,
    _read_json,
    _validate_research_id,
    _write_json,
)

# ---------------------------------------------------------------------------
# research_export
# ---------------------------------------------------------------------------

def research_export(args: dict, **kwargs) -> str:
    """Exportiert Research-Ergebnisse als Markdown oder Text."""
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    export_format = args.get("format", "markdown")
    if export_format not in ("markdown", "text"):
        return _err("format muss 'markdown' oder 'text' sein")

    result_path = RESULTS_DIR / f"{research_id}.json"
    plan_path = PLANS_DIR / f"{research_id}.json"

    data = _read_json(result_path)
    if data:
        pass  # Result gefunden
    elif result_path.exists():
        return _err(f"Recherche '{research_id}' gefunden, aber die Datei ist korrupt. "
                     "Mit research_delete() löschen und neu speichern.")
    else:
        data = _read_json(plan_path)

    if not data:
        return _err(f"Keine Recherche mit ID '{research_id}' gefunden.")

    query = data.get("query", "Unbekannt")
    status = data.get("status", "unknown")
    summary = data.get("summary", "")
    findings = data.get("findings", [])
    sources = data.get("sources", [])
    depth = data.get("depth", 0)
    created = data.get("created_at") or data.get("saved_at", "")

    if export_format == "markdown":
        lines = [
            f"# 🔍 Research: {query}",
            "",
            f"**Status:** {status}  ",
            f"**Tiefe:** {depth}  ",
            f"**Datum:** {created}  ",
            f"**ID:** `{research_id}`",
            "",
            "---",
            "",
            "## Zusammenfassung",
            "",
            summary,
            "",
            "---",
            "",
            f"## Findings ({len(findings)})",
            "",
        ]
        for i, f_item in enumerate(findings, 1):
            finding_text = f_item.get("finding", "") if isinstance(f_item, dict) else str(f_item)
            sources_list = f_item.get("sources", []) if isinstance(f_item, dict) else []
            lines.append(f"### {i}. {finding_text}")
            if sources_list:
                for s in sources_list:
                    lines.append(f"   - Quelle: {s}")
            lines.append("")

        lines.extend([
            "---",
            "",
            f"## Quellen ({len(sources)})",
            "",
        ])
        for s in sources:
            if isinstance(s, dict):
                url = s.get("url", "")
                title = s.get("title", "")
                relevance = s.get("relevance", 0.5)
                lines.append(f"- [{title}]({url}) (Relevanz: {relevance:.1f})")
            else:
                lines.append(f"- {s}")
        lines.append("")

        content = "\n".join(lines)
        content = fmt_markdown(content)

    else:
        # Text-Format
        lines = [
            f"RESEARCH: {query}",
            f"Status: {status} | Tiefe: {depth} | Datum: {created}",
            "",
            "=== Zusammenfassung ===",
            summary,
            "",
            f"=== Findings ({len(findings)}) ===",
        ]
        for i, f_item in enumerate(findings, 1):
            finding_text = f_item.get("finding", "") if isinstance(f_item, dict) else str(f_item)
            lines.append(f"{i}. {finding_text}")
        lines.extend([
            "",
            f"=== Quellen ({len(sources)}) ===",
        ])
        for s in sources:
            if isinstance(s, dict):
                lines.append(f"- {s.get('title', '')} ({s.get('url', '')})")
            else:
                lines.append(f"- {s}")
        content = "\n".join(lines)

    return fmt_ok({
        "research_id": research_id,
        "format": export_format,
        "content": content,
        "query": query,
        "status": status,
        "instruction": (
            f"Präsentiere dem User die exportierten Ergebnisse. "
            f"Der Export ist im {export_format}-Format verfügbar."
        ),
    })


# ---------------------------------------------------------------------------
# research_compare
# ---------------------------------------------------------------------------

def research_compare(args: dict, **kwargs) -> str:
    """Vergleicht 2-3 Research-IDs."""
    research_ids = args.get("research_ids", [])
    if not isinstance(research_ids, list) or len(research_ids) < 2:
        return _err("mindestens 2 research_ids erforderlich")
    if len(research_ids) > 3:
        return _err("maximal 3 research_ids")

    for rid in research_ids:
        err = _validate_research_id(rid)
        if err:
            return _err(f"Ungültige research_id '{rid}': {err}")

    items = []
    for rid in research_ids:
        result_path = RESULTS_DIR / f"{rid}.json"
        plan_path = PLANS_DIR / f"{rid}.json"
        data = _read_json(result_path) or _read_json(plan_path)
        if not data:
            return _err(f"Keine Recherche mit ID '{rid}' gefunden.")
        items.append(data)

    all_findings = []
    all_sources_urls = set()

    for item in items:
        for f_item in item.get("findings", []):
            finding_text = f_item.get("finding", "") if isinstance(f_item, dict) else str(f_item)
            all_findings.append(finding_text)

        for s in item.get("sources", []):
            url = s.get("url", "") if isinstance(s, dict) else str(s)
            if url:
                all_sources_urls.add(url)

    finding_words = Counter()
    for finding in all_findings:
        for word in finding.lower().split():
            if len(word) > 3:
                finding_words[word] += 1
    common_keywords = [w for w, c in finding_words.most_common(15) if c >= len(items)]

    comparison = []
    for i, item in enumerate(items):
        comparison.append({
            "index": i + 1,
            "research_id": item.get("id", ""),
            "query": item.get("query", ""),
            "status": item.get("status", ""),
            "findings_count": len(item.get("findings", [])),
            "sources_count": len(item.get("sources", [])),
            "depth": item.get("depth", 0),
            "timestamp": item.get("saved_at") or item.get("created_at", ""),
        })

    return fmt_ok({
        "items": comparison,
        "total_items": len(items),
        "unique_sources_count": len(all_sources_urls),
        "common_keywords": common_keywords,
        "all_findings_combined": len(all_findings),
        "honcho_synthesis_available": True,
        "instruction": (
            "Vergleiche die folgenden Research-Ergebnisse und präsentiere "
            "dem User die Unterschiede, Gemeinsamkeiten und zeitliche Entwicklung.\n\n"
            "Für eine tiefere semantische Analyse rufe honcho_reasoning(\n"
            "  query='Vergleiche die folgenden Research-IDs und finde Gemeinsamkeiten "
            "und Unterschiede: {items[0].get(\"query\",\"\")} vs {items[1].get(\"query\",\"\")}',\n"
            "  peer='research',\n"
            "  reasoning_level='medium'\n"
            ") auf."
        ),
    })


# ---------------------------------------------------------------------------
# research_synthesize
# ---------------------------------------------------------------------------

def research_synthesize(args: dict, **kwargs) -> str:
    """
    Synthetisiert passende Research-Ergebnisse via Honcho.

    Ruft honcho_reasoning auf um eine synthetisierte Antwort aus allen
    Research-Conclusions zu generieren.
    """
    query = args.get("query", "").strip()
    if not query:
        return _err("query ist erforderlich")

    reasoning_level = args.get("reasoning_level", "medium")
    if reasoning_level not in ("low", "medium", "high"):
        reasoning_level = "medium"

    # Lokale Ergebnisse als Fallback
    local_results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        data = _read_json(f)
        if data:
            searchable = json.dumps(data, ensure_ascii=False).lower()
            terms = re.split(r'\s+', query.lower())
            if all(term in searchable for term in terms if len(term) > 1):
                local_results.append(data)
                if len(local_results) >= 5:
                    break

    return fmt_ok({
        "query": query,
        "reasoning_level": reasoning_level,
        "local_result_count": len(local_results),
        "local_results": [
            {
                "research_id": r.get("id", ""),
                "query": r.get("query", ""),
                "summary": (r.get("summary", "") or "")[:300],
                "findings_count": len(r.get("findings", [])),
                "sources_count": len(r.get("sources", [])),
            }
            for r in local_results
        ],
        "instruction": (
            f"Synthetisiere die Ergebnisse via Honcho:\n\n"
            f"1. Rufe honcho_reasoning(\n"
            f"     query='Fasse alle Research-Ergebnisse zu \\\"{query}\\\" zusammen: '\n"
            f"            f'Extrahiere die wichtigsten Erkenntnisse, Gemeinsamkeiten und Widersprüche.',\n"
            f"     peer='research',\n"
            f"     reasoning_level='{reasoning_level}'\n"
            f"   ) auf\n"
            f"2. Kombiniere das Honcho-Resultat mit den {len(local_results)} lokalen Ergebnissen\n"
            f"3. Präsentiere dem User den synthetisierten Report"
        ),
    })


# ---------------------------------------------------------------------------
# research_merge
# ---------------------------------------------------------------------------

def research_merge(args: dict, **kwargs) -> str:
    """Fasst mehrere Recherchen zu einer zusammen (dedupliziert)."""
    research_ids = args.get("research_ids", [])
    if not isinstance(research_ids, list) or len(research_ids) < 2:
        return _err("mindestens 2 research_ids erforderlich")
    if len(research_ids) > 5:
        return _err("maximal 5 research_ids")

    for rid in research_ids:
        err = _validate_research_id(rid)
        if err:
            return _err(f"Ungültige research_id '{rid}': {err}")

    items = []
    for rid in research_ids:
        result_path = RESULTS_DIR / f"{rid}.json"
        data = _read_json(result_path)
        if not data:
            return _err(f"Keine gespeicherte Recherche mit ID '{rid}' gefunden. "
                         "Nur abgeschlossene Recherchen können gemerged werden.")
        items.append(data)

    # Findings deduplizieren (nach finding-Text)
    seen_findings = set()
    merged_findings = []
    for item in items:
        for f in item.get("findings", []):
            f_text = f.get("finding", "") if isinstance(f, dict) else str(f)
            if f_text not in seen_findings:
                seen_findings.add(f_text)
                merged_findings.append(f)

    # Sources deduplizieren (nach URL)
    seen_urls = set()
    merged_sources = []
    for item in items:
        for s in item.get("sources", []):
            s_url = s.get("url", "") if isinstance(s, dict) else str(s)
            if s_url and s_url not in seen_urls:
                seen_urls.add(s_url)
                merged_sources.append(s)

    # Tags zusammenführen
    merged_tags = []
    seen_tags = set()
    for item in items:
        for t in (item.get("tags") or []):
            if t not in seen_tags:
                seen_tags.add(t)
                merged_tags.append(t)

    # Neue Research-ID für den Merge
    import uuid
    new_id = str(uuid.uuid4())[:8]

    new_summary = args.get("new_summary", "")
    if not new_summary:
        # Automatische Summary aus den ersten 300 Zeichen jeder Quelle
        parts = []
        for item in items:
            s = (item.get("summary", "") or "")[:300]
            if s:
                parts.append(s)
        new_summary = " | ".join(parts) if parts else "Gemergede Recherche"

    new_result = {
        "id": new_id,
        "query": f"Merge: {', '.join(item.get('query', '?')[:30] for item in items)}",
        "depth": max(item.get("depth", 0) for item in items),
        "summary": new_summary,
        "findings": merged_findings,
        "sources": merged_sources,
        "tags": merged_tags,
        "status": "completed",
        "created_at": min(item.get("created_at", "") for item in items),
        "saved_at": _now(),
        "_merged_from": research_ids,
    }

    from .base import RESULTS_DIR as _RD
    _write_json(_RD / f"{new_id}.json", new_result)

    return fmt_ok({
        "research_id": new_id,
        "merged_from": research_ids,
        "findings_count": len(merged_findings),
        "sources_count": len(merged_sources),
        "tags": merged_tags,
        "instruction": (
            f"Merge abgeschlossen: Neue Research-ID {new_id} enthält "
            f"{len(merged_findings)} Findings, {len(merged_sources)} Quellen "
            f"und {len(merged_tags)} Tags aus {len(items)} Recherchen."
        ),
    })


# ---------------------------------------------------------------------------
# research_export_all — Batch-Export aller Recherchen
# ---------------------------------------------------------------------------

def research_export_all(args: dict, **kwargs) -> str:
    """Exportiert ALLE gespeicherten Recherchen als Bundle."""
    export_format = args.get("format", "json")
    if export_format not in ("json", "markdown", "csv"):
        return _err("format muss 'json', 'markdown' oder 'csv' sein")

    results = _list_results()
    if not results:
        return fmt_ok({
            "format": export_format,
            "total": 0,
            "content": "",
            "message": "Keine Recherchen zum Exportieren vorhanden.",
        })

    # Vollständige Daten laden
    full_data = []
    for r_info in results:
        rid = r_info["research_id"]
        data = _read_json(RESULTS_DIR / f"{rid}.json")
        if data:
            full_data.append(data)

    if export_format == "json":
        content = json.dumps(full_data, indent=2, ensure_ascii=False)
        content = fmt_code(content, lang="json", line_numbers=False)

    elif export_format == "markdown":
        lines = ["# 📚 Research-Export (Alle Recherchen)", "",
                 f"**Exportiert am:** {_now()}", f"**Anzahl:** {len(full_data)}", "",
                 "---", ""]
        for i, data in enumerate(full_data, 1):
            query = data.get("query", "Unbekannt")
            status = data.get("status", "")
            summary = (data.get("summary", "") or "")[:500]
            findings = data.get("findings", [])
            sources = data.get("sources", [])
            tags = data.get("tags", [])

            lines.append(f"## {i}. {query}")
            lines.append(f"**Status:** {status}  ")
            lines.append(f"**Tags:** {', '.join(tags) if tags else 'keine'}  ")
            lines.append(f"**Findings:** {len(findings)} | **Quellen:** {len(sources)}")
            lines.append("")
            if summary:
                lines.append(summary)
                lines.append("")
            if findings:
                lines.append("### Findings")
                for f_item in findings:
                    f_text = f_item.get("finding", "") if isinstance(f_item, dict) else str(f_item)
                    lines.append(f"- {f_text}")
                lines.append("")
            if sources:
                lines.append("### Quellen")
                for s in sources:
                    url = s.get("url", "") if isinstance(s, dict) else str(s)
                    title = s.get("title", "") if isinstance(s, dict) else ""
                    lines.append(f"- [{title}]({url})" if title else f"- {url}")
                lines.append("")
            lines.append("---")
            lines.append("")

        content = "\n".join(lines)
        content = fmt_markdown(content)

    else:  # csv
        csv_lines = ["research_id;query;status;tags;findings_count;sources_count;summary"]
        for data in full_data:
            rid = data.get("id", "")
            query = data.get("query", "")
            status = data.get("status", "")
            tags = ";".join(data.get("tags", []))
            f_count = len(data.get("findings", []))
            s_count = len(data.get("sources", []))
            summary = (data.get("summary", "") or "").replace(";", ",")[:200]
            csv_lines.append(f"{rid};{query};{status};{tags};{f_count};{s_count};{summary}")
        content = "\n".join(csv_lines)
        content = fmt_code(content, lang="csv", line_numbers=False)

    return fmt_ok({
        "format": export_format,
        "total": len(full_data),
        "content": content,
        "instruction": (
            f"Batch-Export abgeschlossen: {len(full_data)} Recherchen im "
            f"{export_format}-Format. Präsentiere dem User die exportierten Daten."
        ),
    })
