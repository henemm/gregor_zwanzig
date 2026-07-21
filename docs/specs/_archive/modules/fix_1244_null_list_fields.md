---
entity_id: fix_1244_null_list_fields
type: module
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.0"
tags: [bugfix, trip-loader, corridors, data-integrity, migration]
---

<!-- Issue #1244 — Null-Listenfelder brechen den Trip-Loader -->

# Null-Listenfelder brechen den Trip-Loader (Issue #1244)

## Approval

- [x] Approved — PO-go 2026-07-13

## Purpose

Ein über `POST /api/trips` angelegter Trip ohne explizit gesetzte `corridors`/`stages`
wird als `null` persistiert statt als leere Liste. Der Python-Loader crasht beim Lesen
(`TypeError: 'NoneType' object is not iterable`) und der gesamte Trip verschwindet
lautlos aus jeder Liste (`load_all_trips()` schluckt die Exception als
`logger.warning`) — der Nutzer sieht den Trip zwar in der Übersicht, bekommt aber
nie ein Briefing, und der Sende-Endpoint antwortet `404 Trip not found`. Dieser Fix
schließt die Lücke dreifach ab: Schreibseite (Go-Store erzwingt `[]` statt `null`),
Leseseite (Python-Loader heilt vorhandene `null`-Werte fail-soft) und Bestandsdaten
(Migrationsskript für bereits kaputte Trip-/Preset-Dateien).

## Source

- **File:** `internal/store/trip.go` — `SaveTrip` (Go-API, Port 8090), Nil-Coercion-Block :100-104
- **File:** `internal/store/compare_preset.go` — `SaveComparePresets` (Go-API), :75-88
- **File:** `src/app/loader.py` — `_parse_trip` und `_alert_rule_from_dict` (Python-Core, `src/app/`)
- **File:** `src/app/loader.py` — `load_all_trips`, :1086-1099 (Log-Level für verworfene Trips)
- **File:** `scripts/migrate_1244_null_lists.py` (NEU) — Migration der Bestandsdaten unter `data/users/*/`

> **Schicht-Hinweis:** `internal/store/`, `internal/handler/` = Go-API (Port 8090,
> Production). `src/app/loader.py`, `scripts/` = Python-Core (`src/app/`). Kein
> Frontend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` (`Trip`, `Stage`, `Corridor`) | Go-Struct | Definiert die betroffenen Slice-Felder ohne `omitempty` (Kontrakt "immer `[]`, nie `null`", :111-113) |
| `internal/handler/trip.go` (`CreateTripHandler`) | Go-Handler | Schreibt `model.Trip` ohne DTO direkt aus dem Request-Body — Ursprung der `null`-Werte, bleibt unverändert (Fix sitzt im Store) |
| `internal/handler/compare_preset.go` (`CreateComparePresetHandler`) | Go-Handler | Normalisiert heute nur `LocationIDs`/`Empfaenger`, nicht `Corridors` |
| `scripts/migrate_1231_corridors.py` | Python-Skript | Vorbild-Muster (Dry-Run, `_collect_plan`/`_apply`, Backup, Idempotenz) — heilt `null` selbst NICHT |
| `src/services/report_config_resolver.py` (:216) | Python-Modul | Etabliertes `or []`-Idiom, das im Trip-Loader analog angewendet wird |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/store/trip.go` | MODIFY | Nil-Coercion in `SaveTrip` (:100-104) auf `Corridors`, `Stages` und pro Stage auf `Stage.Waypoints` erweitern |
| `internal/store/compare_preset.go` | MODIFY | Nil-Coercion in `SaveComparePresets` (:75-88) auf `Corridors` je `ComparePreset`-Eintrag erweitern |
| `src/app/loader.py` | MODIFY | `data.get("x", [])` → `data.get("x") or []` (bzw. `or {}`) an :308, :310, :410, :455, :472, :531, :652, :166; Log-Level in `load_all_trips` (:1086-1099) von `warning` auf `error` |
| `scripts/migrate_1244_null_lists.py` | CREATE | Migrationsskript nach dem Muster von `migrate_1231_corridors.py`: Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup, RMW auf `null`→`[]` |
| `internal/store/trip_nil_coercion_test.go` | CREATE | Go-Kern-Test: POST-ähnlicher Save-Roundtrip ohne `corridors`/`stages`/`waypoints` im Input |
| `internal/store/compare_preset_nil_coercion_test.go` | CREATE | Go-Kern-Test: Save-Roundtrip eines ComparePreset ohne `corridors` |
| `tests/tdd/test_null_list_fields.py` | CREATE | Python-Kern-Test: Loader liest `null`-Felder fail-soft, verwerfener Trip loggt `error` |
| `tests/tdd/test_migrate_1244_null_lists.py` | CREATE | Python-Kern-Test: Migrationsskript (Dry-Run, Idempotenz, Feld-Erhalt) |

### Estimated Changes

- Files: 9 (4 geändert, 5 neu)
- LoC: +180/-15

## Implementation Details

### 1. Go-Schreibseite: Nil-Coercion im Store erweitern

`internal/store/trip.go::SaveTrip` bekommt zusätzlich zur bestehenden
`AlertRules`-Coercion (:102-104) analoge Blöcke für:

```go
if trip.Corridors == nil {
    trip.Corridors = []model.Corridor{}
}
if trip.Stages == nil {
    trip.Stages = []model.Stage{}
}
for i := range trip.Stages {
    if trip.Stages[i].Waypoints == nil {
        trip.Stages[i].Waypoints = []model.Waypoint{}
    }
}
```

Der Store ist der einzige Trip-Schreibpfad (alle Handler-Aufrufer laufen über
`SaveTrip`), deckt damit POST, PUT, State-Update, Confirm-Waypoint und
Weather-Config-Änderungen gleichzeitig ab. Kein `omitempty` an den Struct-Tags —
das würde den in `internal/model/trip.go:111-113` dokumentierten Kontrakt
("Corridors immer im JSON, auch leer") brechen und von `AlertRules` divergieren.

`internal/store/compare_preset.go::SaveComparePresets` bekommt analog eine
Schleife über `presets`, die pro Preset `Corridors == nil → []model.Corridor{}`
setzt (zusätzlich zur bestehenden äußeren `presets == nil`-Coercion, :80-82).

### 2. Python-Leseseite: fail-soft beim Lesen

`src/app/loader.py::_parse_trip` (und `_alert_rule_from_dict`) wechseln vom
Idiom `data.get("x", [])` auf `data.get("x") or []` an den in der Analyse
identifizierten Stellen (:308 stages, :310 waypoints, :410 display_config →
`or {}`, :455 corridors, :472 avalanche_regions, :531 metrics, :652 sms_metrics,
:166 channels in `_alert_rule_from_dict`). Der `.get(key, default)`-Default
greift bei explizitem JSON-`null` nicht (liefert `None`), das `or`-Idiom greift
in jedem Falsy-Fall — dieses Muster ist im Compare-Pfad bereits etabliert
(`src/services/report_config_resolver.py:216`).

Dieser Schritt macht bereits geschriebene `null`-Werte beim nächsten Lesen
harmlos, unabhängig von der Migration — Altdaten "heilen" sich selbst beim
ersten erfolgreichen Ladeversuch nach dem Deploy.

### 3. Migration der Bestandsdaten

`scripts/migrate_1244_null_lists.py`, strukturell identisch zu
`scripts/migrate_1231_corridors.py`:

- Iteriert über `data/users/*/trips/*.json` und `data/users/*/compare_presets.json`
- Zweiphasig: `_collect_plan(root)` ermittelt betroffene Dateien und Felder
  (`corridors`, `stages`, `stage[].waypoints`, `avalanche_regions`, `metrics`,
  `sms_metrics`, `channels`, `display_config`), `_apply(plan)` schreibt
- Dry-Run per Default, `--execute` zum tatsächlichen Schreiben, `--root` für
  alternativen Datenwurzelpfad (Tests)
- tar.gz-Pre-Snapshot nach `.backups/` vor jedem `--execute`-Lauf
- Read-Modify-Write: nur die identifizierten `null`-Felder werden auf `[]`
  (bzw. `{}` für `display_config`) gesetzt, alle anderen Keys — auch
  unbekannte, dem Skript nicht bekannte — bleiben unverändert erhalten
  (BUG-DATALOSS-GR221-Prinzip)
- Idempotent: zweiter Lauf über bereits migrierte Dateien erzeugt einen leeren
  Plan und schreibt nichts

Abweichend vom Vorbild `migrate_1231_corridors.py` darf dieses Skript einen
leeren Plan NICHT als Fehler werten (dort Zeile 176) — ein leerer Plan ist der
Erfolgsfall des zweiten (idempotenten) Laufs.

### 4. Observability

`src/app/loader.py::load_all_trips` (:1086-1099) wechselt für den
Skip-Pfad von `logger.warning` auf `logger.error`, inklusive Trip-Datei und
Fehlermeldung. Ein unladbarer Trip ist ein Datenintegritätsproblem, kein
erwartbarer Nebeneffekt — die bisherige `warning`-Stufe hat drei kaputte Trips
auf Staging monatelang unsichtbar gemacht, weil niemand `warning`-Logs
routinemäßig sichtet.

## Expected Behavior

- **Input:** `POST /api/trips` ohne `corridors`/`stages` im Body; `POST
  /api/compare-presets` ohne `corridors`; Bestandsdatei mit
  `"corridors": null` auf Platte
- **Output:** Persistierte JSON-Datei enthält `[]` statt `null` für alle
  betroffenen Felder; der Trip ist über `GET /api/trips/{id}` ladbar und über
  den Sende-Endpoint versendbar (kein 404); Bestandsdatei mit `null` ist auch
  ohne Migration wieder ladbar (fail-soft im Loader)
- **Side effects:** Migrationsskript räumt Bestandsdateien beim `--execute`-Lauf
  physisch auf (Backup vorher); verworfene Trips erscheinen als `logger.error`
  statt `logger.warning`

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt über die App einen neuen Trip an, ohne Korridore oder Etappen zu konfigurieren / When der Trip anschließend geöffnet oder ein Briefing dafür ausgelöst wird / Then ist der Trip normal ladbar und erhält ein Briefing statt eines Fehlers oder eines stillen Verschwindens aus der Liste
  - Test: `internal/store/trip_nil_coercion_test.go` speichert einen Trip ohne `Corridors`/`Stages`/`Waypoints`, lädt die geschriebene JSON-Datei roh und prüft `[]` statt `null`; `tests/tdd/test_null_list_fields.py` lädt dieselbe Datei über `load_trip()` und prüft ein erfolgreiches `Trip`-Objekt ohne Exception.

- **AC-2:** Given ein Trip oder Orts-Vergleich wird angelegt oder geändert, ohne dass Korridore, Etappen oder Wegpunkte mitgeschickt werden / When die Daten anschließend auf der Festplatte nachgesehen werden / Then stehen dort leere Listen, niemals `null` — unabhängig davon, ob es sich um ein Neuanlegen, eine Änderung oder eine Bestätigung eines Wegpunkts handelt
  - Test: `internal/store/trip_nil_coercion_test.go` deckt Save-Aufrufe mit `nil`-Slices für alle drei Felder ab; `internal/store/compare_preset_nil_coercion_test.go` deckt denselben Fall für ein `ComparePreset` ohne `Corridors` ab.

- **AC-3:** Given auf der Festplatte liegt bereits ein Trip mit `"corridors": null` aus der Zeit vor diesem Fix / When der Trip geladen wird, ohne dass zuvor ein Migrationsskript gelaufen ist / Then wird der Trip trotzdem erfolgreich geladen (kein Absturz, keine Fehlermeldung an den Nutzer)
  - Test: `tests/tdd/test_null_list_fields.py` erzeugt eine JSON-Datei mit `"corridors": null`, `"stages": null` und `"channels": null` in einem verschachtelten `alert_rule` und lädt sie über `load_trip()` — Ergebnis ist ein valides `Trip`-Objekt mit leeren Listen an den betroffenen Stellen.

- **AC-4:** Given ein Nutzer legt einen Orts-Vergleich (Compare-Preset) über die App an, ohne Wertebereiche (Korridore) zu setzen / When der Vergleich anschließend gespeichert wird / Then enthält die gespeicherte Datei für das Korridor-Feld eine leere Liste statt `null`
  - Test: `internal/store/compare_preset_nil_coercion_test.go` speichert ein `ComparePreset` mit `Corridors == nil`, liest die geschriebene JSON-Datei roh und prüft `[]`.

- **AC-5:** Given das Migrationsskript wird zweimal nacheinander gegen denselben Datenbestand mit kaputten Trip- und Vergleichsdateien ausgeführt / When der zweite Lauf abgeschlossen ist / Then verändert der zweite Lauf keine Datei mehr (Plan ist leer), und alle Felder, die dem Skript unbekannt sind, sind über beide Läufe hinweg unverändert erhalten geblieben
  - Test: `tests/tdd/test_migrate_1244_null_lists.py` führt `_collect_plan`/`_apply` zweimal aus, prüft leeren Plan beim zweiten Lauf sowie Byte-Gleichheit aller Nicht-Ziel-Felder vor/nach dem ersten Lauf.

- **AC-6:** Given ein Trip auf der Festplatte ist trotz aller Fixes weiterhin nicht ladbar (z.B. wegen eines anderen strukturellen Defekts) / When der Trip beim Laden aller Trips eines Nutzers übersprungen wird / Then erscheint dafür eine Fehlermeldung im Log (nicht nur eine unauffällige Warnung), die Dateiname und Ursache benennt
  - Test: `tests/tdd/test_null_list_fields.py` erzeugt eine strukturell defekte Trip-Datei (z.B. fehlendes Pflichtfeld `id`), ruft `load_all_trips()` auf und prüft per `caplog`, dass ein `ERROR`-Log-Eintrag mit Dateiname erzeugt wird.

## Known Limitations

- Loader-Stellen außerhalb des Trip-Pfads (User/Locations/Subscriptions/Recipients,
  `loader.py:757,771,785,1420,1433,1445`) werden NICHT angefasst — dort erzeugt
  heute kein Schreiber `null`, ein Fix wäre vorsorglich, nicht ursachenbezogen.
- Keine Umstellung des Create-Handlers (`internal/handler/trip.go::CreateTripHandler`)
  auf ein explizites Request-DTO. Das würde die Ursache strukturell näher an der
  Wurzel schließen, ist aber ein größerer Umbau (alle Handler-Aufrufer betroffen)
  und wird hier bewusst nicht mitgemacht — der Store-Fix deckt alle fünf
  Schreibpfade bereits ab.
- Die Migration muss pro Host separat ausgeführt werden (`data/users/` ist
  gitignored, liegt außerhalb des Deploy-Artefakts) — kein automatischer Teil
  dieses Workflows, sondern ein eigener Deploy-Schritt (Staging, dann Prod) als
  `claude-gregor`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bugfix innerhalb eines bestehenden, dokumentierten Musters
  (Nil-Coercion in der Store-Schicht, Issue #205 F002; `or []`-Idiom im
  Loader, bereits an anderen Stellen etabliert). Keine neue Architektur-
  Entscheidung, keine neue Abhängigkeit, keine strukturelle Weichenstellung.

## Changelog

- 2026-07-13: Initial spec created — Issue #1244
