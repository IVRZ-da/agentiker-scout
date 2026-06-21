---
name: framework-detection
description: "Framework Auto-Detection für Scout Plugin — erkennt 30+ Technologien via FrameworkDetector, steuert Framework-spezifische Bug-Patterns."
version: 0.1.3
author: agentiker
tags: [framework, detection, medusa, nextjs, react, go, python, patterns, presets]
---

# Framework Detection — Scout Plugin

Dieser Skill dokumentiert die **Framework Detection Engine** im Scout Plugin (`shared/framework_detector.py`) und die Integration in Bug-Hunt Patterns, Analysis und Intent-Erkennung.

## Architektur

```
scout/
├── shared/
│   ├── framework_detector.py   ← Framework Detection Engine (30+ Technologien)
│   └── patterns.py             ← get_patterns_for_frameworks() Filter
├── bughunt/
│   ├── bughunt_patterns.py     ← BugPattern.frameworks + PRESETS
│   └── bughunt_tools.py        ← bug_hunt_scan() Auto-Framework-Detection
└── analysis/
    └── analysis_tools.py       ← analysis_framework() Tool + pattern_discover framework-bewusst
```

## FrameworkDetector — Kernklasse

```python
from shared.framework_detector import FrameworkDetector, detect_frameworks

# Vollständiger Scan
detector = FrameworkDetector("/path/to/project")
profile = detector.detect()
print(profile.to_dict())

# Schneller Scan (nur High-Confidence-Marker)
profile = detector.detect_fast()

# Convenience-API (gibt dict zurück)
result = detect_frameworks("/path/to/project", fast=True)

# Formatierte Ausgabe
from shared.framework_detector import format_profile_summary
print(format_profile_summary(result))
```

### FrameworkProfile — Struktur

```python
profile.frameworks = {
    "backend": [DetectedFramework(name="medusa-v2", category="backend", ...)],
    "frontend": [DetectedFramework(name="nextjs", category="frontend", ...)],
    "database": [DetectedFramework(name="postgresql", ...)],
    "language": [DetectedFramework(name="typescript", ...)],
    "testing": [...],
    "infra": [...],
    "ci": [...],
    "package_manager": [...],
}
profile.overall_confidence  # 0.0 - 1.0
profile.has_framework("medusa-v2")  # True/False
profile.get_framework("nextjs")     # DetectedFramework | None
```

## Erkannte Technologien (30+)

### Backend
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| medusa-v2 | medusa-config.ts, @medusajs/medusa | high |
| nextjs | next.config.ts, "next" in package.json | high |
| express | "express" in package.json | high |
| fastify | "fastify" in package.json | high |
| go-chi | go.mod + chi.NewRouter | high |
| go-fiber | go.mod + fiber.New | high |
| fastapi | requirements.txt + "from fastapi import" | high |
| django | manage.py + "django" | high |

### Frontend
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| react | "react" in package.json | high |
| vue | "vue" in package.json | high |
| svelte | "svelte" in package.json | high |
| vite | vite.config.ts | high |

### UI Libraries
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| tailwindcss | tailwind.config.ts | high |
| shadcn-ui | components.json | high |
| @medusajs/ui | @medusajs/ui in package.json | high |

### Datenbanken
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| postgresql | "pg" in package.json, docker-compose postgres: | high |
| redis | "redis"/"ioredis" in package.json | high |

### Sprachen
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| typescript | tsconfig.json | high |
| go | go.mod | high |
| rust | Cargo.toml | high |
| python | *.py, requirements.txt | medium |

### Testing
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| jest | jest.config.ts | high |
| vitest | vitest.config.ts | high |
| playwright | @playwright in package.json | high |

### Infrastructure
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| docker | Dockerfile, docker-compose.yml | high |
| systemd | *.service mit [Unit] | high |
| nginx | nginx.conf | high |
| terraform | *.tf | high |
| npm-workspaces | "workspaces" in package.json | high |
| turborepo | turbo.json | high |

### CI/CD
| Technologie | Marker | Confidence |
|-------------|--------|------------|
| github-actions | .github/workflows/*.yml | high |
| forgejo-actions | .forgejo/workflows/*.yml | high |

## Neue Technologie hinzufügen

Jede Technologie ist ein `_TechDetector` mit Markern:

```python
MEIN_DETECTOR = type("_MeinDetector", (_TechDetector,), {
    "name": "meine-tech",
    "category": "backend",  # backend | frontend | ui_library | database | language | testing | infra | ci | package_manager
    "markers": [
        ("package.json", '"meine-tech"', "high"),
        ("meine-tech.config.ts", "", "high"),
        ("**/*.ts", "from 'meine-tech'", "medium"),
    ],
})()

# In ALL_DETECTORS eintragen
ALL_DETECTORS: List[_TechDetector] = [
    ...
    MEIN_DETECTOR,
]
```

Marker-Format: `(file_glob, search_pattern, confidence)`
- `file_glob`: `"package.json"`, `"next.config.ts"`, `"**/*.go"`, `"docker-compose.yml"`, `"**/*.py"`
- `search_pattern`: String oder Regex. Leerer String "" = nur Datei-Existenz prüfen
- `confidence`: `"high"`, `"medium"`, `"low"`

## Framework-spezifische BugPatterns

Seit v0.1.3 hat jedes `BugPattern` ein `frameworks`-Feld:

```python
BugPattern(
    pattern_id="A001",
    name="Delete-Stub (Promise.resolve statt API-Call)",
    category="medusa-admin-ui",
    frameworks=["medusa"],           # Nur für Medusa-Projekte
    frameworks_required=True,        # Nur bei erkanntem Framework aktivieren
    ...
)
```

### Automatische Framework-Zuordnung (Kategorie-basiert)

| Kategorie | frameworks | frameworks_required |
|-----------|------------|-------------------|
| security (S001-S012) | ["*"] | False (generisch) |
| code-quality (C001-C011) | ["*"] | False (generisch) |
| typescript (T001-T003) | ["typescript"] | True |
| go (G001-G005) | ["go"] | True |
| rust (RST001-RST004) | ["rust"] | True |
| react-next (R001-R003) | ["react", "nextjs"] | True |
| medusa-admin-ui (A001-A005) | ["medusa"] | True |

### Framework-spezifischer Scan

```python
# Auto-Detection + Filter (empfohlen)
bug_hunt_scan(session_id="...", patterns=["medusa"])
# → Erkennt Framework automatisch, filtert Patterns

# Explizite Framework-Angabe
bug_hunt_scan(session_id="...", patterns=["all"], frameworks=["medusa", "nextjs"])

# Mit Preset (bequemste Variante)
bug_hunt_scan(session_id="...", preset="medusa-full")
```

## Presets

8 vordefinierte Pattern-Sets:

| Preset | Patterns | Beschreibung |
|--------|----------|-------------|
| `medusa-full` | 31 | Medusa Backend + Admin UI + Security |
| `medusa-admin` | 5 | Nur Admin UI spezifisch |
| `medusa-backend` | 26 | Medusa Backend + Security |
| `nextjs-storefront` | 26 | Next.js + React Patterns |
| `go-backend` | 28 | Go + Security |
| `python-backend` | 23 | Python + Security |
| `typescript-generic` | 26 | TypeScript allgemein |
| `all` | 43 | Vollscan |

Programmatisch:
```python
from bughunt.bughunt_patterns import resolve_preset, list_presets

# Preset auflösen
pattern_ids = resolve_preset("medusa-full")

# Alle Presets anzeigen
for p in list_presets():
    print(f"{p['name']}: {p['pattern_count']} Patterns")
```

## Tools

### analysis_framework(path, fast)

Zeigt das Framework-Profil eines Projekts an.

```python
analysis_framework(path="/home/jo/ivory-green-poc")
# → Framework-Profil mit allen erkannten Technologien
```

## Intent-Erkennung

`shared/intent.py` erkennt Framework-bezogene Anfragen:

| Eingabe | Erkannt |
|---------|---------|
| "welche technologien werden verwendet?" | framework |
| "erkenne den techstack" | framework |
| "analyse das framework profil" | framework |

Priority: `bug > research > framework > db > web > code`
