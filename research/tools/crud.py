"""
tools/crud.py — CRUD-Operationen: research_start, research_save, research_delete, research_cleanup.
"""

import json
import logging
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta

from scout.research.research_hooks import reset_tracker

from .base import (
    PLANS_DIR,
    RESULTS_DIR,
    _err,
    _now,
    _now_dt,
    _ok,
    _read_json,
    _try_create_plan_follow_plan,
    _validate_research_id,
    _write_json,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# research_start
# ---------------------------------------------------------------------------

def research_start(args: dict, **kwargs) -> str:
    """
    Startet eine neue Recherche.

    Validiert die Query, erzeugt eine research_id und legt eine Plan-Datei an.
    Der Agent führt danach die eigentliche Recherche via Firecrawl durch.
    """
    query = args.get("query", "").strip()
    if not query:
        return _err("query ist erforderlich")

    if len(query) < 3:
        return _err("query ist zu kurz (min 3 Zeichen)")

    if query.lower() in ("test", "abc", "foo", "bar", "asdf", "xyz"):
        return _err("query scheint ein Test zu sein — bitte eine aussagekräftige Recherche-Frage eingeben")

    if len(query) > 2000:
        return _err("query ist zu lang (max 2000 Zeichen)")

    depth = max(1, min(5, int(args.get("depth", 3))))
    max_sources = max(1, min(50, int(args.get("max_sources", 10))))

    research_id = str(uuid.uuid4())[:8]

    plan = {
        "id": research_id,
        "query": query,
        "depth": depth,
        "max_sources": max_sources,
        "status": "planned",
        "created_at": _now(),
    }
    _write_json(PLANS_DIR / f"{research_id}.json", plan)

    # Tracker für post_tool_call Hook initialisieren
    try:
        from scout.research.research_hooks import reset_tracker
        reset_tracker(research_id)
    except ImportError as e:
        logger.debug("reset_tracker import skipped: %s", e)

    # Plan im plan_follow Plugin anlegen (lose Kopplung via Registry)
    plan_follow_result = _try_create_plan_follow_plan(query, research_id)
    plan_note = ""
    if plan_follow_result:
        if plan_follow_result.get("status") == "created":
            plan_note = (
                f"\n📋 Plan im plan_follow Plugin erstellt (ID: {plan_follow_result.get('plan_id', '?')}). "
                f"Nutze plan_current() um den ersten Task zu sehen."
            )
        elif plan_follow_result.get("error"):
            plan_note = f"\n⚠️ plan_follow Plugin verfügbar aber Fehler: {plan_follow_result['error']}"

    return _ok({
        "research_id": research_id,
        "status": "planned",
        "query": query,
        "depth": depth,
        "max_sources": max_sources,
        "plan_follow": plan_follow_result,
        "instruction": (
            f"Recherche gestartet (ID: {research_id}). Führe jetzt die Recherche durch:\n"
            f"1. firecrawl_search(query='{query}', limit={max_sources})\n"
            f"2. firecrawl_scrape für jede relevante Quelle\n"
            f"3. Optional: firecrawl_agent für tiefere Recherche\n"
            f"4. Analysiere die Ergebnisse und erstelle eine Zusammenfassung\n"
            f"5. Rufe research_save(research_id='{research_id}', ...) auf, um zu speichern"
            f"{plan_note}"
        ),
        "plan": plan,
    })


MAX_RESULTS = 100


def _enforce_max_results() -> None:
    """Löscht die ältesten Results wenn MAX_RESULTS überschritten."""
    if not RESULTS_DIR.exists():
        return
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    while len(files) > MAX_RESULTS:
        oldest = files.pop(0)
        try:
            oldest.unlink()
        except OSError as e:
            logger.debug("cleanup unlink failed: %s", e)


# ---------------------------------------------------------------------------
# research_save
# ---------------------------------------------------------------------------

def research_save(args: dict, **kwargs) -> str:
    """
    Speichert die Ergebnisse einer Recherche.

    findings und sources werden als native Arrays akzeptiert (kein JSON-String mehr).
    """
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    plan_path = PLANS_DIR / f"{research_id}.json"
    result_path = RESULTS_DIR / f"{research_id}.json"

    if not plan_path.exists() and not result_path.exists():
        return _err(f"Keine Recherche mit ID '{research_id}' gefunden. research_start aufrufen.")

    if result_path.exists():
        return _err(f"Recherche '{research_id}' bereits gespeichert. "
                     "Mit research_delete() löschen vor erneutem Speichern.")

    summary = args.get("summary", "").strip()
    if not summary:
        return _err("summary ist erforderlich")

    status = args.get("status", "completed")
    if status not in ("completed", "partial", "failed"):
        return _err("status muss 'completed', 'partial' oder 'failed' sein")

    # findings als natives Array (Abwärtskompatibel: auch JSON-String)
    findings = args.get("findings", [])
    if isinstance(findings, str):
        try:
            findings = json.loads(findings)
        except (json.JSONDecodeError, TypeError):
            findings = []
    if not isinstance(findings, list):
        findings = []
    normalized = []
    for f in findings:
        if isinstance(f, dict):
            normalized.append({
                "finding": str(f.get("finding", "")),
                "sources": [str(s) for s in (f.get("sources") or [])],
            })
        elif isinstance(f, str):
            normalized.append({"finding": f, "sources": []})
    findings = normalized

    # sources als natives Array (Abwärtskompatibel: auch JSON-String)
    sources = args.get("sources", [])
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except (json.JSONDecodeError, TypeError):
            sources = []
    if not isinstance(sources, list):
        sources = []
    normalized_src = []
    for s in sources:
        if isinstance(s, dict):
            normalized_src.append({
                "url": str(s.get("url", "")),
                "title": str(s.get("title", "")),
                "relevance": float(s.get("relevance", 0.5)),
            })
        elif isinstance(s, str):
            normalized_src.append({"url": s, "title": s, "relevance": 0.5})
    sources = normalized_src

    # Plan laden wenn vorhanden
    plan = _read_json(plan_path)

    result = {
        "id": research_id,
        "query": plan.get("query", ""),
        "depth": plan.get("depth", 0),
        "summary": summary,
        "findings": findings,
        "sources": sources,
        "tags": args.get("tags", []),
        "status": status,
        "created_at": plan.get("created_at", ""),
        "saved_at": _now(),
    }
    _write_json(result_path, result)

    # Cleanup plan file
    if plan_path.exists():
        plan_path.unlink()

    # Tracker zurücksetzen — nach research_save kein stale track mehr
    reset_tracker(None)

    # Max-Limit: älteste Results löschen wenn > 100
    _enforce_max_results()

    # Anweisung für Honcho-Persistenz
    honcho_summary = summary[:2000]

    return _ok({
        "research_id": research_id,
        "status": status,
        "query": result["query"],
        "depth": result["depth"],
        "findings_count": len(findings),
        "sources_count": len(sources),
        "instruction": (
            f"Ergebnisse gespeichert (ID: {research_id}). Persistiere jetzt die Zusammenfassung in Honcho:\n\n"
            f"honcho_conclude(\n"
            f"  peer='research',\n"
            f"  conclusion=json.dumps({{\n"
            f'    "type": "deep_research",\n'
            f'    "research_id": "{research_id}",\n'
            f'    "query": {json.dumps(result["query"])},\n'
            f'    "summary": {json.dumps(honcho_summary)},\n'
            f'    "findings": {json.dumps(findings[:10], ensure_ascii=False)},\n'
            f'    "sources": {json.dumps([s.get("url","") for s in sources[:10]], ensure_ascii=False)},\n'
            f'    "depth": {result["depth"]},\n'
            f'    "status": "{status}",\n'
            f'    "timestamp": "{_now()}"\n'
            f"  }}\n"
            f")\n\n"
            f"Später kannst du die Ergebnisse mit research_search(query='...') oder "
            f"honcho_search(query='...', peer='research') wiederfinden."
        ),
        "result": result,
    })


# ---------------------------------------------------------------------------
# research_delete
# ---------------------------------------------------------------------------

def research_delete(args: dict, **kwargs) -> str:
    """Löscht eine Recherche inklusive Plan- und Ergebnis-Dateien."""
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    plan_path = PLANS_DIR / f"{research_id}.json"
    result_path = RESULTS_DIR / f"{research_id}.json"

    deleted_plan = False
    deleted_result = False

    if plan_path.exists():
        plan_path.unlink()
        deleted_plan = True

    if result_path.exists():
        result_path.unlink()
        deleted_result = True

    if not deleted_plan and not deleted_result:
        return _err(f"Keine Recherche mit ID '{research_id}' gefunden.")

    return _ok({
        "research_id": research_id,
        "deleted_plan": deleted_plan,
        "deleted_result": deleted_result,
        "message": f"Recherche {research_id} gelöscht.",
    })


# ---------------------------------------------------------------------------
# research_cleanup
# ---------------------------------------------------------------------------

def research_cleanup(args: dict, **kwargs) -> str:
    """Bereinigt alte oder verwaiste Research-Daten."""
    action = args.get("action", "plans")
    older_than_days = max(1, int(args.get("older_than_days", 30)))
    cutoff = _now_dt() - timedelta(days=older_than_days)

    if action not in ("plans", "all"):
        return _err("action muss 'plans' oder 'all' sein")

    deleted_plans = 0
    deleted_results = 0

    if action in ("plans", "all"):
        for f in list(PLANS_DIR.glob("*.json")):
            data = _read_json(f)
            created = data.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created)
                    if created_dt < cutoff:
                        rid = data.get("id", f.stem)
                        if not (RESULTS_DIR / f"{rid}.json").exists():
                            f.unlink()
                            deleted_plans += 1
                except (ValueError, TypeError):
                    logger.warning("Überspringe Plan %s: ungültiges created_at '%s'", f.name, created)

    if action == "all":
        for f in list(RESULTS_DIR.glob("*.json")):
            data = _read_json(f)
            saved = data.get("saved_at", "")
            if saved:
                try:
                    saved_dt = datetime.fromisoformat(saved)
                    if saved_dt < cutoff:
                        f.unlink()
                        deleted_results += 1
                except (ValueError, TypeError):
                    logger.warning("Überspringe Ergebnis %s: ungültiges saved_at '%s'", f.name, saved)

    return _ok({
        "action": action,
        "older_than_days": older_than_days,
        "deleted_plans": deleted_plans,
        "deleted_results": deleted_results,
        "message": (
            f"Cleanup abgeschlossen: {deleted_plans} Orphan-Plans und "
            f"{deleted_results} alte Ergebnisse gelöscht (älter als {older_than_days} Tage)."
        ),
    })


# ---------------------------------------------------------------------------
# research_tag
# ---------------------------------------------------------------------------

def research_tag(args: dict, **kwargs) -> str:
    """Verwaltet Tags für eine Recherche (add/remove/set/clear)."""
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    tags = args.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(t).strip().lower().replace(" ", "-") for t in tags if t]
    action = args.get("action", "add")

    # Lade existierendes Result
    result_path = RESULTS_DIR / f"{research_id}.json"
    plan_path = PLANS_DIR / f"{research_id}.json"

    data = _read_json(result_path)
    if not data:
        data = _read_json(plan_path)
    if not data:
        return _err(f"Keine Recherche mit ID '{research_id}' gefunden.")

    existing = data.get("tags", [])
    if not isinstance(existing, list):
        existing = []

    if action == "add":
        combined = list(dict.fromkeys(existing + tags))  # dedupliziert, Reihenfolge erhalten
    elif action == "remove":
        combined = [t for t in existing if t not in set(tags)]
    elif action == "set":
        combined = tags
    elif action == "clear":
        combined = []
    else:
        return _err(f"Unbekannte Aktion '{action}'. Erlaubt: add, remove, set, clear")

    data["tags"] = combined
    path = result_path if result_path.exists() else plan_path
    _write_json(path, data)

    return _ok({
        "research_id": research_id,
        "tags": combined,
        "action": action,
        "tag_count": len(combined),
    })


# ---------------------------------------------------------------------------
# research_update
# ---------------------------------------------------------------------------

def research_update(args: dict, **kwargs) -> str:
    """Aktualisiert eine bestehende Recherche (erweitern/korrigieren)."""
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    result_path = RESULTS_DIR / f"{research_id}.json"
    PLANS_DIR / f"{research_id}.json"

    # Nur gespeicherte Ergebnisse updatebar
    if not result_path.exists():
        return _err(f"Keine gespeicherte Recherche mit ID '{research_id}' gefunden. "
                     "research_save zuerst aufrufen oder research_start für neue Recherche.")

    data = _read_json(result_path)
    if not data:
        return _err(f"Recherche '{research_id}' ist korrupt. Mit research_delete löschen.")

    updated = False

    # Summary aktualisieren
    if "summary" in args and isinstance(args["summary"], str):
        data["summary"] = args["summary"].strip()
        updated = True

    # Status aktualisieren
    if "status" in args:
        status = args["status"]
        if status not in ("completed", "partial", "failed"):
            return _err("status muss 'completed', 'partial' oder 'failed' sein")
        data["status"] = status
        updated = True

    # Findings anhängen
    if "append_findings" in args:
        new_findings = args["append_findings"]
        if isinstance(new_findings, str):
            try:
                new_findings = json.loads(new_findings)
            except (json.JSONDecodeError, TypeError):
                new_findings = []
        if isinstance(new_findings, list):
            for f in new_findings:
                if isinstance(f, dict):
                    data.setdefault("findings", []).append({
                        "finding": str(f.get("finding", "")),
                        "sources": [str(s) for s in (f.get("sources") or [])],
                    })
                elif isinstance(f, str):
                    data.setdefault("findings", []).append({"finding": f, "sources": []})
            updated = True

    # Sources anhängen
    if "append_sources" in args:
        new_sources = args["append_sources"]
        if isinstance(new_sources, str):
            try:
                new_sources = json.loads(new_sources)
            except (json.JSONDecodeError, TypeError):
                new_sources = []
        if isinstance(new_sources, list):
            for s in new_sources:
                if isinstance(s, dict):
                    data.setdefault("sources", []).append({
                        "url": str(s.get("url", "")),
                        "title": str(s.get("title", "")),
                        "relevance": float(s.get("relevance", 0.5)),
                    })
                elif isinstance(s, str):
                    data.setdefault("sources", []).append({"url": s, "title": s, "relevance": 0.5})
            updated = True

    if not updated:
        return _err("Keine Änderungen vorgenommen. Unterstützte Felder: summary, status, append_findings, append_sources")

    data["updated_at"] = _now()
    _write_json(result_path, data)

    return _ok({
        "research_id": research_id,
        "updated": True,
        "findings_count": len(data.get("findings", [])),
        "sources_count": len(data.get("sources", [])),
        "updated_at": data["updated_at"],
    })


# ---------------------------------------------------------------------------
# research_verify — Citation-Accuracy-Prüfung
# ---------------------------------------------------------------------------

def research_verify(args: dict, **kwargs) -> str:
    """
    Prüft Quellen-URLs auf Erreichbarkeit und validiert Findings.

    Führt HTTP HEAD/GET-Checks für alle Quellen-URLs durch
    und meldet tote oder nicht erreichbare Quellen.
    """
    research_id = args.get("research_id", "").strip()
    if not research_id:
        return _err("research_id ist erforderlich")

    err = _validate_research_id(research_id)
    if err:
        return _err(err)

    result_path = RESULTS_DIR / f"{research_id}.json"
    if not result_path.exists():
        return _err(f"Keine gespeicherte Recherche mit ID '{research_id}' gefunden.")

    data = _read_json(result_path)
    if not data:
        return _err("Recherche-Daten sind korrupt.")

    sources = data.get("sources", [])
    if not sources:
        return _ok({
            "research_id": research_id,
            "total_sources": 0,
            "verified": 0,
            "failed": 0,
            "details": [],
            "message": "Keine Quellen zu prüfen.",
        })

    results = []
    verified = 0
    failed = 0

    for s in sources:
        url = s.get("url", "") if isinstance(s, dict) else str(s)
        if not url:
            continue

        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; DeepResearch/1.0)")
            # Timeout nach 10 Sekunden
            resp = urllib.request.urlopen(req, timeout=10)
            status = "ok" if resp.status < 400 else "error"
            if status == "ok":
                verified += 1
            else:
                failed += 1
            results.append({
                "url": url,
                "status": status,
                "http_code": resp.status,
            })
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            code = getattr(e, "code", 0)
            failed += 1
            results.append({
                "url": url,
                "status": "error",
                "http_code": code,
                "error": str(e.reason) if hasattr(e, "reason") else str(e),
            })
        except Exception as e:
            failed += 1
            results.append({
                "url": url,
                "status": "error",
                "http_code": 0,
                "error": str(e),
            })

    return _ok({
        "research_id": research_id,
        "total_sources": len(sources),
        "verified": verified,
        "failed": failed,
        "details": results[:20],
        "message": (
            f"{verified}/{len(sources)} Quellen erreichbar. "
            f"{failed} Quellen nicht erreichbar."
        ),
    })


# ---------------------------------------------------------------------------
# research_auto — Autonome Recherche via Sub-Agent
# ---------------------------------------------------------------------------

def research_auto(args: dict, **kwargs) -> str:
    """
    Startet eine vollautonome Recherche.

    Rüstet einen Sub-Agenten aus (via delegate_task/deep-research skill)
    der selbstständig: firecrawl_search → firecrawl_scrape → synthesize → save
    durchführt.
    """
    query = args.get("query", "").strip()
    if not query:
        return _err("query ist erforderlich")

    depth = max(1, min(5, int(args.get("depth", 3))))
    max_sources = max(1, min(20, int(args.get("max_sources", 5))))

    # Intern research_start aufrufen, um Plan + Tracking zu initialisieren
    start_result = research_start({"query": query, "depth": depth, "max_sources": max_sources})
    import json as _json
    start_data = _json.loads(start_result)
    if "error" in start_data:
        return start_result
    research_id = start_data["research_id"]

    # Für den Agenten: Erstelle eine Step-by-Step Instruction
    instruction = (
        f"Führe eine autonome Recherche zum Thema '{query}' durch (ID: {research_id}, Tiefe: {depth}):\n\n"
        f"1. **Quellen suchen:** firecrawl_search(query='{query}', limit={max_sources})\n"
        f"   - Öffne jede gefundene Quelle\n"
        f"2. **Inhalte extrahieren:** firecrawl_scrape(url, formats=['markdown'], onlyMainContent=True)\n"
        f"   - Extrahiere die Hauptinhalte aus jeder Quelle\n"
        f"3. **Analysieren:** Arbeite die Ergebnisse durch und identifiziere Key Findings\n"
        f"4. **Speichern:** Rufe research_save(\n"
        f'     research_id="{research_id}",\n'
        f'     summary="<Deine Zusammenfassung>",\n'
        f'     findings=[{{"finding": "<Finding 1>", "sources": ["<url>"]}}, ...],\n'
        f'     sources=[{{"url": "<url>", "title": "<Titel>", "relevance": 0.9}}, ...],\n'
        f'     status="completed"\n'
        f"   ) auf\n"
        f"5. **Persistieren:** honcho_conclude(peer='research', conclusion=json.dumps({{...}}))\n\n"
        f"Wenn die Recherche abgeschlossen ist, präsentiere dem User die Ergebnisse."
    )

    return _ok({
        "research_id": research_id,
        "query": query,
        "depth": depth,
        "max_sources": max_sources,
        "auto_mode": True,
        "instruction": instruction,
        "message": f"Autonome Recherche gestartet (ID: {research_id}). Folge der Anleitung um die Recherche durchzuführen.",
    })
