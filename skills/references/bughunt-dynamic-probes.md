# Behauptungen dynamisch nachweisen (Bug-Hunt R4)

Zweck: Ein Finding, das nur aus Code-Lesen stammt, ist eine Hypothese. Vor dem Report
muss es an der echten Funktion laufen — sonst wandern Fehlklassifikationen in den
Report und der Nutzer prüft nach. Das gilt besonders für Befunde von Subagenten.

## Grundregeln

- **Read-only.** Das Projekt wird nicht verändert; Probes liegen im Scratch-Verzeichnis
  (`$BH_AGENT_WORKSPACE` / `~/.hermes/cache/scratch/`) und importieren die echten Module
  über absolute Pfade. Kein Testfile im Repo anlegen, keine Dependencies installieren.
- **Probe gegen den Produktivcode, nicht gegen eine Kopie.** Die Kopie driftet und
  belegt nichts.
- Ein Probe-Skript pro Themenblock (Datums-/Parserlogik, Auth, Retry), Ausgabe als
  Tabelle `eingabe | ergebnis | erwartet` — direkt in den Report übernehmbar.

## Die CJS-Falle bei `npx tsx`

Ein Probe-Skript **außerhalb** des Zielprojekts wird als CJS kompiliert, wenn im
Zielverzeichnis keine `package.json` mit `"type":"module"` liegt:

```
ERROR: Top-level await is currently not supported with the "cjs" output format
```

Fix: Datei mit `.mts`-Endung schreiben (oder sie innerhalb eines `type:module`-Pakets
ablegen). Danach läuft `await` auf oberster Ebene ohne `main()`-Wrapper:

```bash
npx tsx /home/jo/.hermes/cache/scratch/probe.mts
```

`npx tsx` funktioniert nur, wenn im Zielprojekt `node_modules` installiert ist — vor dem
Hunt einmal `npm ci` laufen lassen, auch wenn die Tests später grün sind.

## Probe-Template

```ts
// read-only Probe gegen die echten Module
import { fraglicheFunktion } from '/pfad/zum/projekt/src/modul.ts';

const show = (label: string, value: unknown) => console.log(label.padEnd(40), '|', JSON.stringify(value));

for (const input of ['fall-1', 'fall-2', 'randfall']) {
  try {
    show(input, await fraglicheFunktion(input));
  } catch (error) {
    show(input, { wirft: (error as Error).name + ': ' + (error as Error).message });
  }
}
```

Immer drei Fallgruppen abdecken: **Normalfall** (Gegenprobe, dass die Funktion überhaupt
korrekt arbeitet), **Verdachtsfall** und **Randfall** (leer, kaputt, fremdes Format).
Ohne Normalfall ist nicht unterscheidbar, ob die Funktion generell defekt ist oder nur
am Verdachtspunkt.

## Probe-Muster, die sich bewährt haben

| Verdacht | Probe | Worauf achten |
|---|---|---|
| Parser akzeptiert fremdes Format | alle realistischen Eingabevarianten durchschicken, inkl. weggelassener Teile (Jahr fehlt, Zeitteil dabei, ein-/zweistellig) | Plausibilität gegen den Kalender, nicht nur gegen „kein Fehler": `3.11.` → Jahr 2001 fällt sonst nicht auf |
| Auth-Vergleich fail-open | gespeicherten Hash mit Platzhaltern/Sonderzeichen füllen (`...`, `!!`, `CHANGEME`) | Länge der dekodierten Puffer: dekodieren beide Seiten zu 0 Byte, ist `timingSafeEqual` wahr |
| Backoff/Retry tot | `Number(null)`, `Number('')`, `Number(' ')` prüfen | `Number(null) === 0` erfüllt `isFinite && >= 0` → Wartezeit 0, Exponential-Fallback ist toter Code |
| Prototype-Keys als Eingabe | `constructor`, `toString`, `__proto__`, `hasOwnProperty` durch den Parser schicken | erst prüfen, ob der Lookup vorher schon auf die geerbte Funktion fällt — dann ist es kein Bug |
| Cache/TTL wird nicht invalidiert | Fehlerantwort (401) injizieren und Aufruf wiederholen | zweiter Aufruf muss einen neuen Token/Request auslösen, sonst hängt der Ausfall bis zum TTL-Ende |

## Ablauf vor dem Report

1. Kandidatenliste aus Scan + Subagenten + eigener Lektüre zusammenführen.
2. Pro Kandidat: zitierte Zeile selbst lesen. Stimmt sie nicht → verwerfen und den
   Grund notieren („durch SDK abgefangen", „Service-Methode prüft tiefer").
3. Pro verbleibendem P1/P2: Probe schreiben oder bewusst als „Code-Befund, nicht
   ausgeführt" kennzeichnen.
4. Findings per `bug_hunt_finding` eintragen (Beleg = Probe-Ausgabe oder Zeile).
5. Alle geprüften IDs in EINEM `bug_hunt_triage(status="verified")` markieren.
6. Report: Befund, Stelle, Root Cause, konkreter Fehlerfall, Fix, Quelle
   (`verifiziert` vs. `Subagent, nicht gegengeprüft`). Die Quellen-Spalte ist Pflicht —
   sie sagt dem Leser, wie viel Vertrauen jede Zeile verdient.
