"""Bug-Hunt Pattern Library — 20+ Bug-Patterns in 5 Kategorien.

Jedes Pattern hat:
  pattern_id: Eindeutige ID (S001, C001, T001, R001, A001)
  name: Lesbarer Name
  category: security | code-quality | typescript | react-next | admin-ui
  severity: P0 | P1 | P2 | P3 | INFO
  description: Woran erkennt man den Bug?
  scan_type: code_search | grep | code_diagnostics
  scan_query: Der Such-Query
  scan_file_glob: File-Glob für die Suche
  fix_description: Wie behebt man den Bug?
  false_positive_notes: Wann ist es KEIN Bug?

Import:
  from bughunt_patterns import ALL_PATTERNS, PATTERNS_BY_ID, ...
  Wird von bughunt_core.py beim Start geladen.
"""

from typing import Optional
from datetime import datetime, timezone

# Prefix für benutzerdefinierte Patterns (nicht löschbar via delete-Custom)
CUSTOM_PREFIX = "CUSTOM_"


class BugPattern:
    """Ein Bug-Such-Pattern mit strukturierten Metadaten.

    Neue Felder (v0.6.0):
      source: "built-in" | "custom" — Herkunft des Patterns
      source_session: Session-ID in der das Pattern entdeckt wurde
      source_project: Projekt in dem das Pattern entdeckt wurde
      source_finding_id: Finding-ID das das Pattern generiert hat
      match_count: Wie oft dieses Pattern bereits getroffen hat
      tags: Liste von Schlagworten für Kategorisierung
      created_at: ISO-Timestamp der Erstellung
      updated_at: ISO-Timestamp der letzten Änderung
    """

    def __init__(self, pattern_id: str = "", name: str = "",
                 category: str = "", severity: str = "P2",
                 description: str = "", scan_type: str = "",
                 scan_query: str = "", scan_file_glob: str = "",
                 scan_language: str = "", fix_description: str = "",
                 false_positive_notes: str = "",
                 source: str = "built-in",
                 source_session: str = "", source_project: str = "",
                 source_finding_id: str = "",
                 match_count: int = 0, tags: Optional[list[str]] = None,
                 created_at: str = "", updated_at: str = ""):
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.severity = severity
        self.description = description
        self.scan_type = scan_type
        self.scan_query = scan_query
        self.scan_file_glob = scan_file_glob
        self.scan_language = scan_language
        self.fix_description = fix_description
        self.false_positive_notes = false_positive_notes
        self.source = source
        self.source_session = source_session
        self.source_project = source_project
        self.source_finding_id = source_finding_id
        self.match_count = match_count
        self.tags = tags or []
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "BugPattern":
        p = cls()
        for k, v in d.items():
            setattr(p, k, v)
        return p


# ======================================================================
# SECURITY PATTERNS (S001-S008)
# ======================================================================

SECURITY_PATTERNS = [
    BugPattern(
        pattern_id="S001",
        name="execSync/execFile mit potenziellem User-Input",
        category="security",
        severity="P0",
        description="child_process.execSync oder execFile mit user-gesteuerten Parametern → Shell-Injection",
        scan_type="code_search",
        scan_query=r"execSync",
        scan_file_glob="**/*.ts",
        fix_description="execSync durch execFile mit param-Array ersetzen, oder Input strikt validieren/escapen",
        false_positive_notes="Constructor-time execSync (Startup, kein Request-Handler) ist meist safe",
    ),
    BugPattern(
        pattern_id="S002",
        name="Hardcodierte Secrets/API-Keys",
        category="security",
        severity="P0",
        description="Hardcodierte API-Keys, Tokens oder Passwörter im Source-Code",
        scan_type="grep",
        scan_query=r'(api[_-]?key|secret|token|password)\\s*[:=]\\s*["\'][A-Za-z0-9_]{16,}',
        scan_file_glob="**/*.{ts,js,py,go}",
        fix_description="Secrets in .env oder Secret-Manager auslagern. NIEMALS hardcoden.",
        false_positive_notes="Test-Secrets ('test-key-123') in Test-Dateien ausschliessen",
    ),
    BugPattern(
        pattern_id="S003",
        name="Open Redirect (res.redirect mit user URL)",
        category="security",
        severity="P0",
        description="res.redirect() mit benutzergesteuerter URL → Phishing-Vektor",
        scan_type="code_search",
        scan_query="res.redirect",
        scan_file_glob="**/*.ts",
        fix_description="Redirect-URL gegen Whitelist prüfen oder nur relative Pfade erlauben",
        false_positive_notes="Redirect zu fest codierten URLs (kein User-Input) ist safe",
    ),
    BugPattern(
        pattern_id="S004",
        name="SQL/Raw-Query Injection",
        category="security",
        severity="P0",
        description="Raw SQL-Queries mit String-Concatenation statt Prepared Statements",
        scan_type="code_search",
        scan_query=r"execute\\(.*\\${",
        scan_file_glob="**/*.ts",
        fix_description="Prepared Statements oder Query-Builder verwenden. Kein ${} in SQL-Strings.",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="S005",
        name="Path Traversal (user File-Path)",
        category="security",
        severity="P1",
        description="readFile/execFile mit user-gesteuertem Pfad → Directory Traversal",
        scan_type="code_search",
        scan_query="execFile",
        scan_file_glob="**/*.ts",
        fix_description="Pfad gegen Whitelist + resolve() prüfen. ../ und Null-Bytes blockieren.",
        false_positive_notes="execFile mit festen Parametern (kein User-Input) ist safe",
    ),
    BugPattern(
        pattern_id="S006",
        name="JWT Fallback Secret",
        category="security",
        severity="P0",
        description="JWT-Secret hat Fallback-Wert in Source-Code (vorhersagbar → Token-Fälschung)",
        scan_type="grep",
        scan_query=r'(jwt[_-]?secret|JWT[_-]?SECRET)\\s*[:=]\\s*["\'].{5,}',
        scan_file_glob="**/*.{ts,js}",
        fix_description="Harten Error werfen wenn Env-Variable fehlt. KEIN Fallback-Secret.",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="S007",
        name="Auth Bypass (Route ohne authenticate)",
        category="security",
        severity="P0",
        description="Admin/Protected Route ohne authenticate()-Middleware",
        scan_type="code_search",
        scan_query="MedusaRequest",
        scan_file_glob="**/api/**/route.ts",
        fix_description="authenticate()-Middleware hinzufügen oder sicherstellen dass globaler Auth greift",
        false_positive_notes="MedusaRequest ist TS-only Type — Framework kann Auth global anwenden. Live-testen!",
    ),
    BugPattern(
        pattern_id="S008",
        name="Error Leakage (err.message an Client)",
        category="security",
        severity="P1",
        description="Interne Error-Details (Stack-Trace, DB-Schema) werden an den Client gesendet",
        scan_type="grep",
        scan_query=r'err\\.message.*res\\.status|e\\.message.*\\.json',
        scan_file_glob="**/api/**/*.ts",
        fix_description="Logge err.message via Logger, sende nur generischen Fehler an Client",
        false_positive_notes="",
    ),
    # ─── Python Security Patterns (S009-S010) ──────────────────────────
    BugPattern(
        pattern_id="S009",
        name="Python eval()/exec() ohne Input-Validierung",
        category="security",
        severity="P0",
        description="eval() oder exec() mit potenziellem User-Input → Remote Code Execution",
        scan_type="grep",
        scan_query=r"^(eval|exec)\(",
        scan_file_glob="**/*.py",
        fix_description="eval()/exec() vermeiden. Wenn nötig: ast.literal_eval() für sichere Ausdrücke.",
        false_positive_notes="eval()/exec() ohne User-Input (konstante Strings) sind safe. Config-Time eval ist ok.",
    ),
    BugPattern(
        pattern_id="S010",
        name="Python subprocess(shell=True) ohne Validierung",
        category="security",
        severity="P0",
        description="subprocess mit shell=True und potenziellem User-Input → Shell-Injection",
        scan_type="grep",
        scan_query=r"subprocess\..*shell=True",
        scan_file_glob="**/*.py",
        fix_description="shell=True vermeiden. subprocess.run(['cmd', 'arg']) ohne Shell. Oder Input strikt escapen.",
        false_positive_notes="subprocess mit festen (konstanten) Strings ist safe. shell=False ist Default.",
    ),
    # ─── Python Security (S011-S012) ─────────────────────────────────
    BugPattern(
        pattern_id="S011",
        name="pickle.loads() aus unsicherer Quelle",
        category="security",
        severity="P0",
        description="pickle.loads() mit Daten aus externen Quellen → Remote Code Execution via beliebigem Code beim Deserialisieren",
        scan_type="grep",
        scan_query=r"pickle\.loads?\(",
        scan_file_glob="**/*.py",
        fix_description="json.loads() oder andere sichere Serialisierung verwenden. NIEMALS pickle mit User-Input.",
        false_positive_notes="pickle.loads() mit selbst-erzeugten (signierten) Daten ist akzeptabel",
    ),
    BugPattern(
        pattern_id="S012",
        name="yaml.load() statt safe_load()",
        category="security",
        severity="P0",
        description="yaml.load() ohne Loader=yaml.SafeLoader → Code Execution via !!python/object",
        scan_type="grep",
        scan_query=r"yaml\.load\(|yaml\.load_all\(",
        scan_file_glob="**/*.py",
        fix_description="yaml.safe_load() oder yaml.load(..., Loader=yaml.SafeLoader) verwenden",
        false_positive_notes="yaml.load() mit eigenem Loader (yaml.SafeLoader) ist sicher",
    ),
]

# ======================================================================
# CODE QUALITY PATTERNS (C001-C011)
# ======================================================================

QUALITY_PATTERNS = [
    BugPattern(
        pattern_id="C001",
        name="Silent Catch (leere catch-Blöcke)",
        category="code-quality",
        severity="P1",
        description="catch {} ohne Fehlerbehandlung — Fehler werden stumm geschluckt",
        scan_type="code_search",
        scan_query=r"catch\\s*\\{\\s*\\}",
        scan_file_glob="**/*.{ts,tsx}",
        fix_description="catch (err) { logger.error(err); /* oder toast / user feedback */ }",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="C002",
        name="console.log in Production",
        category="code-quality",
        severity="P2",
        description="console.log/warn/error in Production-Code (ausser Logger)",
        scan_type="code_search",
        scan_query=r"console\\.(log|warn|error)",
        scan_file_glob="**/*.{ts,tsx}",
        fix_description="Durch Logger (pino/winston) ersetzen. console.log nur in Test-Dateien erlauben.",
        false_positive_notes="console.warn/error in API-Routen ist teilweise gewollt",
    ),
    BugPattern(
        pattern_id="C003",
        name="N+1 Query Pattern (Loop-Queries)",
        category="code-quality",
        severity="P1",
        description="Loop-basierte DB-Queries (for...of mit await query → N+1)",
        scan_type="grep",
        scan_query='for.*of.*await.*(find|list|query|load)',
        scan_file_glob="**/*.ts",
        fix_description="Promise.all() + batch-loading. Oder IN-Clause / JOIN statt N Einzel-Queries.",
        false_positive_notes="Kleine N (<5) sind tolerierbar. Erst ab N>10 wirklich relevant.",
    ),
    BugPattern(
        pattern_id="C004",
        name="Timer Leak (setTimeout/setInterval ohne Cleanup)",
        category="code-quality",
        severity="P1",
        description="setTimeout/setInterval in React/Next ohne clearTimeout → Memory Leak",
        scan_type="code_search",
        scan_query="setInterval",
        scan_file_glob="**/*.{tsx,ts}",
        fix_description="useEffect cleanup: return () => clearInterval(id). Oder useRef für Timer-ID.",
        false_positive_notes="setInterval in Server-Komponenten ist kein Leak",
    ),
    BugPattern(
        pattern_id="C005",
        name="as any Type Abuse",
        category="code-quality",
        severity="P2",
        description="Übermässige Nutzung von 'as any' — Type-Safety ausgehebelt",
        scan_type="grep",
        scan_query="as any",
        scan_file_glob="**/*.{ts,tsx}",
        fix_description="Proper Types definieren. as any nur als letztes Mittel.",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="C006",
        name="force-dynamic defeatet ISR",
        category="code-quality",
        severity="P2",
        description="Layout setzt force-dynamic → alle Unterseiten werden dynamisch (kein CDN-Caching)",
        scan_type="grep",
        scan_query="force-dynamic",
        scan_file_glob="**/layout.{tsx,ts}",
        fix_description="export const revalidate = 60 statt force-dynamic.",
        false_positive_notes="Wenn Seite wirklich dynamisch sein muss: ok. Aber bewusste Entscheidung.",
    ),
    # ─── Python Patterns (C007-C009) ────────────────────────────────────
    BugPattern(
        pattern_id="C007",
        name="print() in Python Production-Code",
        category="code-quality",
        severity="P2",
        description="print() statt Logger — kein Timestamp, kein Level, kein Channel",
        scan_type="grep",
        scan_query=r"^print\(",
        scan_file_glob="**/*.py",
        fix_description="Durch logging.getLogger() ersetzen. print() nur in CLI-Scripts/Tests erlauben.",
        false_positive_notes="Scripts ohne Logger-Setup sind ok. Tests dürfen print() nutzen.",
    ),
    BugPattern(
        pattern_id="C008",
        name="Mutable Default Arguments (Python)",
        category="code-quality",
        severity="P2",
        description="def f(x=[]) / def f(x={}) — mutable Defaults werden zwischen Calls geteilt → Seiteneffekte",
        scan_type="grep",
        scan_query=r'def \w+\([^)]*=\[\]|def \w+\([^)]*=\{\}',
        scan_file_glob="**/*.py",
        fix_description="Default auf None setzen: def f(x=None) + if x is None: x = []",
        false_positive_notes="Wenn das Mutable im Body nicht mutiert wird, ist es safe (selten).",
    ),
    BugPattern(
        pattern_id="C009",
        name="Python Silent Catch (except: pass)",
        category="code-quality",
        severity="P1",
        description="except: pass — Fehler werden stumm geschluckt, keine Fehlerbehandlung",
        scan_type="grep",
        scan_query=r"^except.*:\s*$",
        scan_file_glob="**/*.py",
        fix_description="except Exception as e: logger.error(...) oder mindestens minimales Error-Handling",
        false_positive_notes="except: pass in finally-Blöcken oder shutdown-Handlern ist akzeptabel",
    ),
    # ─── Python Quality (C010-C011) ─────────────────────────────────
    BugPattern(
        pattern_id="C010",
        name="requests ohne Timeout",
        category="code-quality",
        severity="P1",
        description="requests.get/post ohne timeout → Blockade bei ausbleibender Antwort (Resource Leak)",
        scan_type="grep",
        scan_query=r"requests\.(get|post|put|delete|patch|head)\(",
        scan_file_glob="**/*.py",
        fix_description="Immer timeout=<sekunden> setzen: requests.get(url, timeout=10)",
        false_positive_notes="Streaming-Requests (stream=True) brauchen oft keinen Timeout",
    ),
    BugPattern(
        pattern_id="C011",
        name="assert für Production-Checks",
        category="code-quality",
        severity="P2",
        description="assert statements werden mit python -O deaktiviert → Sicherheitslücke in Production",
        scan_type="grep",
        scan_query=r"^assert ",
        scan_file_glob="**/*.py",
        fix_description="assert nur in Tests verwenden. In Production: if not condition: raise ...",
        false_positive_notes="assert in Test-Dateien und __debug__-geguardten Blöcken ist ok",
    ),
]

# ======================================================================
# TYPESCRIPT PATTERNS (T001-T003)
# ======================================================================

TYPESCRIPT_PATTERNS = [
    BugPattern(
        pattern_id="T001",
        name="TypeScript Compiler Errors",
        category="typescript",
        severity="P0",
        description="tsc --noEmit zeigt Fehler — Code compiliert nicht sauber",
        scan_type="code_diagnostics",
        scan_query="",
        scan_file_glob="",
        fix_description="Jeden TS-Fehler fixen oder mit // @ts-expect-error kommentieren",
        false_positive_notes="Build-Tools (esbuild) haben manchmal andere Typ-Defs als tsc",
    ),
    BugPattern(
        pattern_id="T002",
        name="Fehlende Return Types",
        category="typescript",
        severity="P2",
        description="Funktionen ohne expliziten Return-Type — TypeScript inferred, aber oft falsch",
        scan_type="grep",
        scan_query=r":.*=>\\s*\\{|function\\s+\\w+\\s*\\([^)]*\\)\\s*\\{",
        scan_file_glob="**/*.ts",
        fix_description="Explizite Return-Type-Annotation hinzufügen",
        false_positive_notes="Kleine Arrow-Functions in JSX sind ok ohne Return-Type",
    ),
    BugPattern(
        pattern_id="T003",
        name="'any' statt 'unknown'",
        category="typescript",
        severity="P2",
        description="any wird verwendet wo unknown korrekt wäre (unsafe)",
        scan_type="grep",
        scan_query=r": any[^\w]|as any[^\w]",
        scan_file_glob="**/*.ts",
        fix_description="unknown erzwingt Type-Check vor Nutzung. any umgeht den Check.",
        false_positive_notes="",
    ),
]

# ======================================================================
# GO PATTERNS (G001-G005)
# ======================================================================

GO_PATTERNS = [
    BugPattern(
        pattern_id="G001",
        name="exec.Command mit User-Input",
        category="go",
        severity="P0",
        description="exec.Command mit benutzergesteuerten Argumenten → Shell-Injection",
        scan_type="grep",
        scan_query=r"exec\.Command\(.*\$|exec\.CommandContext\(.*\$",
        scan_file_glob="**/*.go",
        fix_description="Input strikt validieren oder allowlist-basiert arbeiten. Kein User-Input in Command-Args.",
        false_positive_notes="Feste, konstante Strings in exec.Command sind safe",
    ),
    BugPattern(
        pattern_id="G002",
        name="SQL Query mit String-Concatenation",
        category="go",
        severity="P0",
        description="sql.Query/sql.Exec mit fmt.Sprintf oder String-Concatenation → SQL Injection",
        scan_type="grep",
        scan_query=r"db\.(Query|Exec|QueryRow)\(.*\+|fmt\.Sprintf.*SELECT",
        scan_file_glob="**/*.go",
        fix_description="Prepared Statements mit Platzhaltern ($1, $2) verwenden",
        false_positive_notes="Konstante Queries (kein User-Input) sind mit String-Concatenation akzeptabel",
    ),
    BugPattern(
        pattern_id="G003",
        name="Goroutine ohne Sync (Race Condition)",
        category="go",
        severity="P1",
        description="go func() ohne WaitGroup, Mutex oder Channel → Race Condition / Data Race",
        scan_type="grep",
        scan_query=r"go func\(|go \w+\(",
        scan_file_glob="**/*.go",
        fix_description="sync.WaitGroup, sync.Mutex oder Channels für Synchronisation verwenden",
        false_positive_notes="Fire-and-Forget Goroutinen (Logging, Metrics) brauchen keinen Sync",
    ),
    BugPattern(
        pattern_id="G004",
        name="t.Error statt t.Errorf / t.Fatal",
        category="go",
        severity="P2",
        description="t.Error() in Tests — bricht nicht ab, Tests laufen weiter mit inkonsistentem State",
        scan_type="grep",
        scan_query=r"t\.Error\(|t\.Log\(|fmt\.Print",
        scan_file_glob="**/*_test.go",
        fix_description="t.Errorf() oder t.Fatalf() verwenden für klare Test-Failures",
        false_positive_notes="t.Log() für Debug-Ausgaben ist ok",
    ),
    BugPattern(
        pattern_id="G005",
        name="http.Client ohne Timeout",
        category="go",
        severity="P1",
        description="Default http.Client ohne Timeout → Goroutine-Leak bei ausbleibender Antwort",
        scan_type="grep",
        scan_query=r"http\.DefaultClient|http\.Get\(|http\.Post\(",
        scan_file_glob="**/*.go",
        fix_description="Custom http.Client mit Timeout erstellen: &http.Client{Timeout: 10 * time.Second}",
        false_positive_notes="http.Client mit explizitem Timeout (< 30s) ist ok",
    ),
]

# ======================================================================
# RUST PATTERNS (RST001-RST004)
# ======================================================================

RUST_PATTERNS = [
    BugPattern(
        pattern_id="RST001",
        name="unsafe Block ohne Safety-Kommentar",
        category="rust",
        severity="P0",
        description="unsafe { } Block ohne Begründung → Memory Corruption, UB",
        scan_type="grep",
        scan_query=r"unsafe\s*\{",
        scan_file_glob="**/*.rs",
        fix_description="Jeder unsafe Block braucht einen // SAFETY: Kommentar.",
        false_positive_notes="unsafe mit SAFETY-Kommentar und enger scope ist akzeptabel",
    ),
    BugPattern(
        pattern_id="RST002",
        name="unwrap()/expect() ohne Error-Handling",
        category="rust",
        severity="P1",
        description="unwrap()/expect() auf Result oder Option → Panic bei None/Err",
        scan_type="grep",
        scan_query=r"\.unwrap\(\)|\.expect\(",
        scan_file_glob="**/*.rs",
        fix_description="match, if let, ?-Operator oder map/and_then verwenden.",
        false_positive_notes="unwrap() in Tests und unwrap_or_default() sind akzeptabel",
    ),
    BugPattern(
        pattern_id="RST003",
        name="std::mem::forget ohne Manual Drop",
        category="rust",
        severity="P2",
        description="mem::forget umgeht Drop → Resource Leak (File-Handle, Lock, Connection)",
        scan_type="grep",
        scan_query=r"mem::forget|std::mem::forget",
        scan_file_glob="**/*.rs",
        fix_description="mem::forget nur in dokumentierten Ausnahmen verwenden (FFI, ManuallyDrop)",
        false_positive_notes="mem::forget in FFI-Kontext (Ownership an C-Code übergeben) ist korrekt",
    ),
    BugPattern(
        pattern_id="RST004",
        name="Arc::unwrap_or_clone in hot path",
        category="rust",
        severity="P2",
        description="Arc::unwrap_or_clone() in engen Loops → unnötiger Clone-Overhead",
        scan_type="grep",
        scan_query=r"unwrap_or_clone|Arc::unwrap_or_clone",
        scan_file_glob="**/*.rs",
        fix_description="Arc::clone() oder Arc::try_unwrap() nutzen",
        false_positive_notes="unwrap_or_clone ausserhalb von Loops ist ok",
    ),
]

# ======================================================================
# REACT / NEXT.JS PATTERNS (R001-R003)
# ======================================================================

REACT_PATTERNS = [
    BugPattern(
        pattern_id="R001",
        name="Fehlende useEffect Cleanup",
        category="react-next",
        severity="P1",
        description="useEffect ohne Return-Cleanup — Subscriptions/Timer laufen weiter",
        scan_type="grep",
        scan_query=r'useEffect\\(\\s*\\(\\)\\s*=>\\s*\\{[^}]*$',
        scan_file_glob="**/*.{tsx,ts}",
        fix_description='useEffect(() => { const sub = subscribe(); return () => sub.unsubscribe(); }, [])',
        false_positive_notes="useEffect ohne Side-Effects (nur Daten-laden) braucht kein Cleanup",
    ),
    BugPattern(
        pattern_id="R002",
        name="Fehlender 'key' Prop in Listen",
        category="react-next",
        severity="P2",
        description="map() ohne key-Prop → React Reconciliation-Probleme",
        scan_type="code_search",
        scan_query=r"\\.map\\s*\\(\\s*\\([^)]*\\)\\s*=>",
        scan_file_glob="**/*.tsx",
        fix_description='key={item.id} oder key={index} als letzten Ausweg hinzufügen',
        false_positive_notes="Fragment-Short-Syntax <>...</> braucht keinen key",
    ),
    BugPattern(
        pattern_id="R003",
        name="useState für derived Values",
        category="react-next",
        severity="P2",
        description="useState + useEffect für Werte die aus Props/State berechnet werden können",
        scan_type="grep",
        scan_query=r'const \\[.*useState.*\\].*=\\s*(props|values|items)',
        scan_file_glob="**/*.{tsx,ts}",
        fix_description="useMemo statt useState+useEffect für derived values",
        false_positive_notes="Wenn der derived Value selten gebraucht wird, ist useState ok",
    ),
]

# ======================================================================
# MEDUSA ADMIN UI PATTERNS (A001-A005)
# Hinweis: Diese Patterns sind spezifisch für Medusa Dashboard (@medusajs/ui).
# Für andere Admin-UIs bitte eigene Patterns definieren.
# ======================================================================

ADMIN_PATTERNS = [
    BugPattern(
        pattern_id="A001",
        name="Delete-Stub (Promise.resolve statt API-Call)",
        category="medusa-admin-ui",
        severity="P1",
        description="mutationFn verwendet Promise.resolve() statt DELETE-API-Call → Delete tut nichts",
        scan_type="code_search",
        scan_query=r"Promise\\.resolve",
        scan_file_glob="**/admin/**/*.{ts,tsx}",
        fix_description="sdk.client.fetch(api.endpoint, { method: 'DELETE' }) + onError toast",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="A002",
        name="Native HTML statt Medusa UI",
        category="medusa-admin-ui",
        severity="P2",
        description="<select>/<input> in Admin UI statt @medusajs/ui Komponenten",
        scan_type="grep",
        scan_query="<select|<input|<textarea",
        scan_file_glob="**/admin/**/*.tsx",
        fix_description="<Select>, <Input>, <Textarea> aus @medusajs/ui verwenden",
        false_positive_notes="<input type='hidden'> ist ok (kein UI-Element)",
    ),
    BugPattern(
        pattern_id="A003",
        name="Select-Item mit value='' (Crash)",
        category="medusa-admin-ui",
        severity="P1",
        description="<Select.Item value=''> crasht bei @medusajs/ui v4.1.9+",
        scan_type="grep",
        scan_query=r"value=['\"]{2}",
        scan_file_glob="**/admin/**/*.tsx",
        fix_description="value='' → value='all' oder eindeutigen Nicht-Leerstring",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="A004",
        name="Fehlende Loading States (isPending in Buttons)",
        category="medusa-admin-ui",
        severity="P2",
        description="Prompt.Action ohne disabled={isPending} → Doppelklick möglich",
        scan_type="grep",
        scan_query=r"Prompt\\.Action[^d]*disabled",
        scan_file_glob="**/admin/**/*.tsx",
        fix_description="<Prompt.Action disabled={isPending}> — verhindert Doppel-Submit",
        false_positive_notes="",
    ),
    BugPattern(
        pattern_id="A005",
        name="Silent Error in UI (catch ohne Feedback)",
        category="medusa-admin-ui",
        severity="P1",
        description="onError/try-catch ohne toast oder User-Feedback",
        scan_type="code_search",
        scan_query=r"catch\\s*\\(\\s*\\)\\s*\\{",
        scan_file_glob="**/admin/**/*.{ts,tsx}",
        fix_description="catch (err) { toast.error(err?.message || 'Fehler') }",
        false_positive_notes="",
    ),
]

# ======================================================================
# ZUSAMMENFASSUNG — Alle Patterns in Collections
# ======================================================================

ALL_PATTERNS: list[BugPattern] = (
    SECURITY_PATTERNS + QUALITY_PATTERNS + TYPESCRIPT_PATTERNS
    + GO_PATTERNS + RUST_PATTERNS + REACT_PATTERNS + ADMIN_PATTERNS
)

PATTERNS_BY_ID: dict[str, BugPattern] = {p.pattern_id: p for p in ALL_PATTERNS}
PATTERNS_BY_CATEGORY: dict[str, list[BugPattern]] = {}
for p in ALL_PATTERNS:
    PATTERNS_BY_CATEGORY.setdefault(p.category, []).append(p)


def get_pattern(pattern_id: str) -> Optional[BugPattern]:
    return PATTERNS_BY_ID.get(pattern_id)


def get_patterns_by_category(category: str) -> list[BugPattern]:
    return PATTERNS_BY_CATEGORY.get(category, [])


def get_patterns_by_ids(pattern_ids: list[str]) -> list[BugPattern]:
    return [p for p in (get_pattern(pid) for pid in pattern_ids) if p]


def list_categories() -> list[dict]:
    return [
        {"category": cat, "count": len(patterns)}
        for cat, patterns in sorted(PATTERNS_BY_CATEGORY.items())
    ]


def list_all_patterns() -> list[dict]:
    return [p.to_dict() for p in ALL_PATTERNS]
