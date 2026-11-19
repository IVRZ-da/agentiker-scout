# Vom Hunt-Report zur Fix-Runde

Gilt, wenn ein Hunt-/Audit-Ergebnis (BUGHUNT.md, Scout-Session, Review-Report)
abgearbeitet wird, statt einen einzelnen Bug zu jagen.

## 1. Ausgangslage feststellen

- Report-Datei lesen, nicht nur die Session: gute Reports haben `file:line`, eine
  Severity und einen Status (`verifiziert` vs. `R3 unbestätigt`). Unbestätigte
  Punkte zuerst reproduzieren, sonst fixst du ein Phantom.
- Scout-Sessions: `bughunt(op="history")`, dann je Session
  `bughunt(op="list", session_id=…)`. Liegen zwei offene Sessions zum selben
  Projekt vor (Projektwurzel und `src/`), ist die Wurzel-Session meist mit
  Fremdcode-Rauschen (`node_modules`, `@types`) gefüllt — die `src`-Session ist
  die echte Fundstelle. Nicht blind alles übernehmen.
- **Baseline messen, bevor der erste Fix läuft**: Typecheck + volle Suite, mit
  Anzahl Prüfungen und Laufzeit notieren. Ohne Baseline ist später nicht
  belegbar, dass der Fehlschlag nicht von dir kommt.

## 2. Plan bauen

- Ein Task pro **Datei-Gruppe**, nicht pro Finding (siehe SKILL.md).
- Im Task-Feld `files` die wirklich berührten Pfade nennen (auch Doku und
  `.env.example`) — das ist die Drift-Prüfung beim Abschluss.
- Verify-Kommando so schreiben, dass es scheitern kann:
  `npx tsc -p tsconfig.test.json --noEmit && npx tsx test/smoke-test.ts`
  (das zweite `tsconfig` deckt `test/` und `scripts/` mit ab; das reine
  `tsconfig.json` prüft nur `src`).
- Nach jedem Fix: `plan_current` lesen, dann verifizieren, dann `plan_complete`.
  Kein „weiter im Kopf" — der Plan ist das Gedächtnis bei 20+ Tasks.

## 3. Test-Infrastruktur erweitern, nicht umgehen

**Hängender Endpunkt (Timeout-Test):**
```ts
const hang = createHttpServer(() => { /* absichtlich keine Antwort */ });
await new Promise<void>((done) => hang.listen(0, '127.0.0.1', () => done()));
try { /* … assert.rejects auf 504 … */ }
finally { hang.closeAllConnections(); hang.close(); }
```
Ohne `closeAllConnections()` im `finally` hängt der Testlauf minutenlang.
Zeitlimits dafür als Konstruktor-/Options-Parameter mit Produktions-Default
(`{ json: 20_000, file: 120_000 }` bzw. `timeoutMs?: number`) — im Test 250 ms.

**Body-Limit / 413:** Gefälschte `Content-Length` (Header größer als der Body)
erzeugt **kein** 413: Express/body-parser wartet auf den Body, die Antwort kommt
nie. Echten Übergrößen-Body senden — 40 MB JSON gegen ein 36-MB-Limit antworten
in ~150 ms. Limit erst prüfen, wenn der Body gelesen wird, und `express.json()`
NACH Auth/Rate-Limit einhängen, damit fremde Riesenanfragen nichts kosten.

**Mock-Fault-Injection:**

| Zweck | Mechanik |
|---|---|
| dauerhaft kaputt | `failNext` mit **nicht** wiederholbarem Status (403) |
| gedrosselt | 429/503 + `Retry-After`; ohne Header muss Backoff greifen |
| „kam an, meldete aber Fehler" | eigener Hook: Änderung anwenden, ETag neu setzen, DANN 503 |

Ein `failNext` mit 503 wird vom Retry-Loop verbraucht — der zweite Versuch
gelingt und der Test belegt nichts.

**Zwei Vorbedingungen, sonst greift der Fault gar nicht:**

1. **Kalter Cache.** Hält ein Produktions-Cache (Labels, Personennamen, ETags,
   Plan-Details) die Antwort schon, wird der Fehler nie verbraucht — der Test
   prüft dann den Cache-Pfad und ist grün, obwohl der Fehlerpfad ungetestet
   bleibt. Entweder eine frische Entität anlegen (neue Plan-ID, damit der
   Cache-Key kalt ist) oder die Service-Klasse direkt mit eigenem Client
   instanziieren — deren Cache ist leer. Ein Cache-TTL von 5–10 Minuten macht
   „der vorige Test hat das schon geladen" zur häufigsten Ursache eines
   wirkungslosen Faults.
2. **Passender Key.** Test-Doubles schlüsseln Faults häufig als
   `"${method} ${pathname}"` — ohne Query-String und ohne API-Präfix
   (`/v1.0`). Den Schlüssel aus der Mock-Datei ablesen (die Zeile, die
   `failNext.get(...)` aufruft), nicht aus der URL im Client bauen; sonst wird
   der Fault stumm nie gefunden.

**Nutzlast zwischen den beiden Limits wählen.** Wer eine Encoder-/Größengrenze
prüfen will, muss mit dem Payload *über* dieser Grenze und *unter* der
transportseitigen Body-Grenze bleiben — sonst testet man den 413-Pfad. Beispiel:
35 MB kodiert bei 36 MB Body-Limit prüft die eigene Längenprüfung; 36 MB prüft
nur noch den Body-Parser.

**Ergebnisform vor der Assertion lesen:** Werkzeuge formatieren unterschiedlich
(`{ task, changed, warnings, nextTask }` gegen flach `{ id, title, status }`).
Den `ok(...)`-Aufruf im Handler ansehen, nicht raten — sonst debugst du eine
Assertion, die nie stimmen konnte.

**Neue Fälle gezielt verifizieren, nicht die Suite-Ausgabe lesen.**

- Fall einfügen: Ankerblock per Python-Heredoc ersetzen/erweitern, **jede**
  Ersetzung mit `assert s.count(alt) == 1` absichern. Der Assert läuft vor dem
  Schreiben, die Datei bleibt bei einem Fehlschlag unverändert — ein Retry mit
  korrigiertem Anker ist deshalb gefahrlos. Ankerzeichenketten aus dem Gedächtnis
  treffen selten (Testnamen werden umformuliert): erst `grep -n "<Stichwort>"`,
  dann den echten Text als Anker nehmen.
- Lauf filtern: `npx tsx test/smoke-test.ts 2>&1 | grep -E "<Neuer Fall 1>|<Neuer Fall 2>|Prüfungen|FAIL"`.
  Die `FAIL`-Zeile ist das Signal, **nicht** der Exit-Code — bei einer Pipe ist
  das der Code von `grep`. Bei Rot einmal gezielt nachfassen
  (`grep -A 8 "FAIL <Name>"`), statt die Suite erneut blind zu starten; die
  Assertion-Details (`actual`/`expected`) stehen dort im Klartext.
- Ergebnisform der Antwort prüfen, bevor du `json(...)` benutzt: viele Tools
  antworten bei „nichts gefunden" mit Fließtext statt JSON — `json()` wirft dann
  `SyntaxError: Unexpected token` und man sucht am falschen Ende.

## 4. Paritäts-Checks, die den Fix sonst rot machen

Viele Projekte prüfen automatisch:

- README-Tool-Tabelle gegen die registrierten Schemas (jedes neue Feld muss in
  die Tabelle),
- `.env.example` gegen die Env-Schema-Keys (jede neue Variable an drei Stellen:
  Schema, `.env.example`, README-Tabelle),
- `.env`-Doku gegen die tatsächlich gelesenen Variablen.

Das sind gute Tests — sie schlagen aber bei einem korrekten Fix fehl, wenn die
Doku fehlt. Im selben Task mitpflegen.

## 5. Verhaltensändernde Fixes

Sicherheitsfixes ändern oft die Bedienung: Überschreiben nur mit `confirm`,
Dateizugriff nur innerhalb einer Allowlist. Richtig so — aber dann gilt:

1. Default sicher wählen (Arbeitsverzeichnis statt „alles"), nicht „Allowlist
   leer = alles erlaubt".
2. Fehlermeldung nennt die Variable, die es freischaltet.
3. Bestehenden Test auf das neue Verhalten umschreiben (nicht löschen) und das
   alte Verhalten negativ prüfen.
4. Dem Nutzer die Änderung am Ende explizit als Verhaltensänderung nennen.

## 6. Struktur-Änderungen mit `patch`, nicht per String-Replace

Beim Einfügen von Kontrollfluss (`if (…) { … } else {`) per Python-Replace
entsteht falsch eingerückter Code, der beim nächsten Lesen wie ein Fehler
aussieht. Für Strukturänderungen `patch` mit dem kompletten alten Block und dem
komplett neu formatierten neuen Block nehmen; String-Replace nur für
Einzeiler und Umbenennungen.

## 7. Abschluss

- Report auf „FIXED" setzen (pro Finding Status, nicht nur ein Häkchen am Ende).
- Final: Typecheck + volle Suite, Anzahl Prüfungen vorher/nachher nennen.
- Abschlussbericht als Tabelle Finding → Fix → Test, plus die bewusst
  gebrochenen Erwartungen (Verhaltensänderungen) und offene Rest-Tasks.
- Offene Punkte aus dem Plan nicht verschweigen: lieber „T12–T21 offen" als ein
  glattes „fertig".
