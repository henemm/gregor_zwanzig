# External Validator Report

**Spec:** `docs/specs/bugfix/update_trip_handler_merge.md`
**Datum:** 2026-05-01T04:45Z
**Server:** http://localhost:8095 (lokaler Issue-99 Build)

## Setup

- Auth: `POST /api/auth/login` mit `default` / Passwort aus `.env` → `gz_session` Cookie
- Test-Trip: `gr221-mallorca` (User `default`)
- Persistenz-Pfad: `data/users/default/trips/gr221-mallorca.json`
- Initial-State: 5 Top-Level-Keys (`id`, `name`, `stages`, `aggregation`, `report_config`); `weather_config`, `display_config`, `avalanche_regions` nicht vorhanden

Evidenz-Verzeichnis: `docs/artifacts/bug-99-update-trip-merge/external-validator/`

## Checklist

| # | Expected Behavior (aus Spec) | Beweis | Verdict |
|---|------------------------------|--------|---------|
| 1 | PUT mit Minimal-Body `{id,name,stages}` → HTTP 200, `aggregation` + `report_config` bleiben erhalten | `01-after-minimal-put.json`: `aggregation={"profile":"wintersport"}`, `report_config` mit allen Schluesseln vorhanden | **PASS** |
| 2 | PUT mit Body inkl. `aggregation:{"x":1}` → `aggregation` ersetzt durch `{x:1}`, `report_config` weiterhin erhalten | `02-after-put.json`: `aggregation={"x":1}`, `report_config.evening_time="18:00:00"` (preserved) | **PASS** |
| 3 | (Erweitert) Alle 5 optionalen Felder bleiben bei Minimal-PUT erhalten — nach Seed mit `aggregation`, `report_config`, `weather_config`, `display_config`, `avalanche_regions` | `03-after-seed.json` (alle 5 vorhanden) → Minimal-PUT (`name` geaendert) → `04-after-minimal-put.json` (alle 5 weiterhin vorhanden, `name` korrekt aktualisiert) | **PASS** |
| 4 | (Adversary) 404-Pfad bleibt unberuehrt fuer nicht-existierende Trip-IDs | `PUT /api/trips/nonexistent` → HTTP 404 | **PASS** |
| 5 | (Adversary) `validateTrip` laeuft nach Merge: leere Stages-Liste wird mit 400 abgelehnt | `{"id":"…","stages":[]}` → 400 `at least one stage required` | **PASS** |
| 6 | (Adversary) Explizit leerer `name` wird nach Merge mit 400 abgelehnt | `{"name":"",…}` → 400 `name required` | **PASS** |
| 7 | (Disk-Persistenz) Datei auf Disk enthaelt gemergten Zustand inkl. nicht gesendeter Felder | `data/users/default/trips/gr221-mallorca.json` enthaelt alle 8 Top-Level-Keys nach Minimal-PUT | **PASS** |

## Findings

### Finding 1 — `null` clears Semantik weicht von Spec-Tabelle ab

- **Severity:** LOW (nicht blockierend)
- **Expected (Spec, Semantic Rules table line 135):** "Field present, value `null` → Pointer non-nil but dereferences to zero — **explicit clear** is permitted by this contract."
- **Actual:** Body `{"avalanche_regions": null, …}` loescht das Feld NICHT. `avalanche_regions` bleibt `["AT-02-01","AT-02-02"]` (siehe `05-after-null.json`).
- **Begruendung:** Das ist Standard-Go-`encoding/json`-Verhalten — beim Decoden eines JSON-`null` in einen Pointer-Field, der noch `nil` ist, bleibt der Pointer `nil`. Damit greift `req.X != nil` nicht und der Merge-Schritt wird uebersprungen → Feld bleibt erhalten.
- **Evidence:** `05-null-clear-body.json`, `05-after-null.json`
- **Hinweis:** Die Spec selbst markiert diese Edge-Case als "not actively used by any current client" und "not actively tested as a primary case" (Known Limitations). Die *primaeren* Expected-Behavior-Punkte aus der Spec stellen keinen Anspruch auf null-clear-Semantik. → Diskrepanz ist auf Spec-Ebene zu klaeren, nicht auf Implementations-Ebene.

### Finding 2 — Test-Trip nach Validierung mit zusaetzlichen Feldern (Cleanup-Debt)

- **Severity:** INFO
- Waehrend der Tests wurden `weather_config`, `display_config`, `avalanche_regions` als Seed-Daten in `gr221-mallorca` geschrieben. Eine abschliessende Restore-PUT mit Minimal-Body konnte diese Felder *erwartungsgemaess nicht entfernen* (genau das ist das Merge-Verhalten, das gefixt wurde). State auf Disk enthaelt diese Test-Felder weiterhin.
- **Aktion:** Falls Produktion-Daten betroffen waeren, manueller Cleanup noetig — hier auf Test-Server irrelevant.

## Verdict: VERIFIED

### Begruendung

Beide in der Spec unter "Expected Behavior" formulierten Anforderungen sind reproduzierbar und nachweisbar erfuellt:

1. **Minimal-Body-PUT bewahrt nicht gesendete `omitempty`-Felder** — sowohl die zwei vorab vorhandenen (`aggregation`, `report_config`) als auch die drei zusaetzlich geseedeten (`weather_config`, `display_config`, `avalanche_regions`).
2. **Field-Level-Replace funktioniert korrekt** — explizit gesendetes `aggregation:{x:1}` ersetzt den alten Wert vollstaendig (kein Deep-Merge), waehrend andere Felder unberuehrt bleiben.

Die Persistenz auf Disk wurde verifiziert (Datei enthaelt tatsaechlich die nicht gesendeten Felder), nicht nur die HTTP-Antwort. Validierungspfad (404, leere Stages, leerer Name) bleibt funktionsfaehig.

Die einzige beobachtete Abweichung (null-clear-Semantik) ist von der Spec selbst als Edge-Case mit "not actively tested" gekennzeichnet und betrifft kein produktives Client-Verhalten — Diskrepanz auf Dokumentations-Ebene, kein Implementations-Defekt.
