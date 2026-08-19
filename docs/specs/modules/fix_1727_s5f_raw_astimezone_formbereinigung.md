---
entity_id: fix_1727_s5f_raw_astimezone_formbereinigung
type: refactor
created: 2026-08-19
updated: 2026-08-19
status: draft
workflow: fix-1727-s5f-weather-cache-tz
tags: [timezone, weather-cache, trip-segments, segment-weather, adr-0051]
---

# Fix #1727 S5f — raw_astimezone-Formbereinigung (weather_cache.py, trip_segments.py, segment_weather.py)

## Approval

- [ ] Approved

## Purpose

Reine Formbereinigung, **kein Bugfix**: die 9 `KNOWN_VIOLATIONS`-Fundstellen in `weather_cache.py`,
`segment_weather.py` und `trip_segments.py`, die roh `.astimezone(timezone.utc)` aufrufen, werden
durch einen zentralen, benannten Helfer `to_utc()` in `src/utils/timezone.py` ersetzt (an einer
Stelle durch den bereits bestehenden `local_dt()`). Die Recherche in der Analyse-Phase hat den
ursprünglichen Verdacht eines S5e-artigen Cache-Key-Bugs widerlegt (siehe Known Limitations) — es
gibt hier kein fehlerhaftes Verhalten, nur eine vom AST-Scanner nicht von einer echten Verletzung
unterscheidbare, aber nach Hausnorm #1345 unauffällige Aufrufform.

## Source

- **File A:** `src/services/weather_cache.py`
- **Identifier A:** `get`/`put` (je 2 Call-Sites, `:126-127`/`:177-178`)
- **File B:** `src/services/segment_weather.py`
- **Identifier B:** `_aggregate_for_segment` (2 Call-Sites, `:246`/`:249`)
- **File C:** `src/services/trip_segments.py`
- **Identifier C:** `convert_trip_to_segments` (Segmentstart/-ende `:194`/`:199` → `to_utc()`;
  Ankunftstag `:287` → `local_dt()`)
- **File D (neu):** `src/utils/timezone.py`
- **Identifier D:** neue Funktion `to_utc(dt)`

## Estimated Scope

- **LoC:** ~20-30 Produktivcode
- **Files:** 4 Produktivdateien + 1 Testdatei-Änderung + optional 1 neue Testdatei
- **Effort:** low-medium (kein Konzeptrisiko, aber dichtes Golden-Master-Testnetz an
  `convert_trip_to_segments`/`_aggregate_for_segment`)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/utils/timezone.py` | MODIFY | neue Funktion `to_utc(dt)` = `_as_utc(dt).astimezone(timezone.utc)` |
| `src/services/weather_cache.py` | MODIFY | `get`/`put` auf `to_utc()` umgestellt (4 Call-Sites), praktisch No-op |
| `src/services/segment_weather.py` | MODIFY | `_aggregate_for_segment` auf `to_utc()` umgestellt (2 Call-Sites), neuer Import aus `utils.timezone` |
| `src/services/trip_segments.py` | MODIFY | Segmentstart/-ende auf `to_utc()`, Ankunftstag am Ziel auf `local_dt()`, ungenutzten `timezone`-Import aus `datetime` entfernt |
| `tests/test_output_timezone_guard.py` | MODIFY | 9 `KNOWN_VIOLATIONS`-Einträge entfernt |
| `tests/unit/test_utils_timezone.py` | CREATE (optional) | isolierter Unit-Test für `to_utc()` (naiv/UTC-aware/Offset-aware) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils.timezone._as_utc` | function | Bestehender naiver Guard, Basis für den neuen `to_utc()`-Helfer |
| `utils.timezone.local_dt` | function | Bereits bestehender Helfer, für die 9. Fundstelle (Ankunftstag am Ziel) genutzt statt eines neuen Codes |
| `TripSegment.start_time`/`end_time` | Datenmodell-Vertrag | `src/app/models.py:412-413` — bereits UTC-aware per Vertrag; Umbau ändert daran nichts |
| `docs/specs/modules/weather_cache.md` | Spec | bestehende Modul-Spec, hier nur um den Aufruf-Formwechsel ergänzt, nicht dupliziert |
| `docs/specs/modules/segment_weather.md` | Spec | bestehende Modul-Spec, hier nur um den Aufruf-Formwechsel ergänzt, nicht dupliziert |
| `stage_weather.py`, `trip_report_scheduler.py`, `trip_command_processor.py`, `preview_service.py`, `api/routers/validator.py`, `api/routers/debug.py` | Caller | Downstream-Aufrufer von `convert_trip_to_segments` — sehr breite Aufruferfläche, Verhalten unverändert |
| `trip_alert.py`, `compare_location_weather_source.py` | Caller | Downstream-Aufrufer von `_aggregate_for_segment` über `fetch_segment_weather` — Verhalten unverändert |

## Implementation Details

Reihenfolge (sicherstes zuerst), siehe Analyse in `docs/context/fix-1727-s5f-weather-cache-tz.md`:

1. **`to_utc(dt)` in `src/utils/timezone.py`:** `return _as_utc(dt).astimezone(timezone.utc)`. Naiver
   Input wird nach Hausnorm #1345 als UTC gelabelt (kein Wert-Sprung); aware Input in Nicht-UTC-Zone
   wird echt konvertiert (Regressionsschutz Adversary-Fund F001, nicht nur `tzinfo`-Ersatz).
2. **`weather_cache.py::get`/`put`:** 4 Call-Sites auf `to_utc()` umstellen. Praktisch No-op, da
   `segment.start_time`/`end_time` per Vertrag schon UTC-aware sind.
3. **`segment_weather.py::_aggregate_for_segment`:** 2 Call-Sites auf `to_utc()` umstellen, Kettung an
   `.replace(minute=0, second=0, microsecond=0)` bleibt erhalten (`to_utc(x).replace(...)`) — die
   replace-Kette selbst wird nicht angefasst. Neuer Import aus `utils.timezone` nötig (bisher keiner
   vorhanden).
4. **`trip_segments.py::convert_trip_to_segments`:** Segmentstart/-ende (2 Call-Sites) → `to_utc()`.
   Ankunftstag am Ziel (1 Call-Site, `:287`) → `local_dt()` statt `to_utc()` — bewusst NICHT
   vereinheitlicht, weil `to_utc()` an dieser Stelle einen Westziel-Tagesverschiebungsbug einführen
   würde (der Ankunftstag muss der Ortstag am Ziel bleiben, kein UTC-Tag). Der `timezone`-Import aus
   `datetime` wird nach dem Umbau ungenutzt (er wurde nur für die entfallenden rohen
   `.astimezone(timezone.utc)`-Aufrufe gebraucht) und muss entfernt werden.
5. **`tests/test_output_timezone_guard.py`:** die 9 zugehörigen Einträge aus `KNOWN_VIOLATIONS`
   entfernen (funktionsbezogene Schlüssel — die im Register vermerkten Zeilennummern sind gegenüber
   dem aktuellen Stand verschoben, das ist für die Entfernung selbst irrelevant, siehe Known
   Limitations).

Keine Migration der fünf anderswo bereits vorhandenen, lokal duplizierten `_as_utc`-Varianten
(`weather_change_detection.py`, `meteoalarm.py`, `dwd_eu.py`, `dwd.py`, `meteofrance.py`) — bewusst
außerhalb des Scopes dieser Scheibe.

## Expected Behavior

- **Input:** dieselben Eingaben wie heute (Segment-Zeitgrenzen, Etappentag+Startstunde in Ortszone,
  Ankunftszeit am Ziel).
- **Output:** identische Werte wie vor dem Umbau — die Umstellung ist reine Aufrufform, keine
  Verhaltensänderung. Einzige beobachtbare Änderung ist das Schrumpfen von `KNOWN_VIOLATIONS` um
  genau 9 Einträge.
- **Side effects:** keine.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein naiver `datetime`-Wert WHEN `to_utc(dt)` aufgerufen wird THEN ist das Ergebnis
  UTC-aware mit identischem Wanduhrwert (Hausnorm #1345 — kein Wert-Sprung durch das Labeln).
- [ ] Test 2: GIVEN ein aware `datetime`-Wert in einer Nicht-UTC-Zone (z.B. `+02:00`) WHEN `to_utc(dt)`
  aufgerufen wird THEN wird der Wert echt nach UTC konvertiert (Stundenverschiebung sichtbar, nicht
  nur `tzinfo`-Ersatz — Regressionsschutz Adversary-Fund F001).
- [ ] Test 3: GIVEN die 9 in `KNOWN_VIOLATIONS` gelisteten Fundstellen aus `weather_cache.py`/
  `segment_weather.py`/`trip_segments.py` WHEN der Umbau abgeschlossen ist THEN verschwinden genau
  diese 9 Einträge aus dem Register, kein anderer Eintrag ändert sich, und
  `test_known_violations_only_shrink` sowie `test_no_unlisted_output_timezone_violations` laufen grün.
- [ ] Test 4: GIVEN die bestehenden Golden-Master-Suiten für `convert_trip_to_segments` (u.a.
  `test_bug_401_segment_localtime.py`, `test_issue_1004_ssot_callers.py`,
  `test_issue_995_segment_start_time.py`, `test_onset_respects_configured_day_window.py`,
  `test_alarm_zeitfenster_ziel.py`) und für `_aggregate_for_segment`
  (`test_provider_tz_normalization.py::test_f001_aggregate_for_segment_converts_non_utc_offset_before_flooring`)
  WHEN der Umbau abgeschlossen ist THEN laufen alle unverändert grün, ohne dass ein Assert angepasst
  werden musste.
- [ ] Test 5: GIVEN ein Trip mit einer Zielzone westlich der Startzone (z.B. Zielankunft die lokal noch
  am Vortag des UTC-Tages liegt) WHEN `convert_trip_to_segments` den Ankunftstag am Ziel berechnet
  THEN bleibt der Ankunftstag der Ortstag am Ziel (über `local_dt()`), nicht der ggf. abweichende
  UTC-Tag.
- [ ] Test 6: GIVEN der fertige Umbau WHEN ein Linter/Import-Check über die vier geänderten
  Produktivdateien läuft THEN gibt es keine unbenutzten Imports (insbesondere `timezone` aus
  `datetime` in `trip_segments.py`) und keine neuen Lint-Fehler.

## Acceptance Criteria

- **AC-1:** Given ein naiver (zonenloser) `datetime`-Wert, When `to_utc(dt)` in
  `src/utils/timezone.py` aufgerufen wird, Then ist das Ergebnis UTC-aware mit identischem
  Wanduhrwert — der naive Wert wird nach Hausnorm #1345 als UTC gelabelt, nicht umgerechnet.
  - Test: Unit-Test in `tests/unit/test_utils_timezone.py` — naiver `datetime(2026, 8, 19, 12, 0)`
    rein, erwartet `datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)` raus (Stunde und Minute
    unverändert).

- **AC-2:** Given ein aware `datetime`-Wert in einer Nicht-UTC-Zone (z.B. `+02:00`), When `to_utc(dt)`
  aufgerufen wird, Then wird der Wert echt nach UTC konvertiert — die Wanduhrzeit verschiebt sich um
  genau die Zonendifferenz (Regressionsschutz gegen Adversary-Fund F001, nicht nur `tzinfo`-Ersatz).
  - Test: Unit-Test in `tests/unit/test_utils_timezone.py` —
    `datetime(2026, 8, 19, 14, 0, tzinfo=timezone(timedelta(hours=2)))` rein, erwartet
    `datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)` raus.

- **AC-3:** Given die 9 in `KNOWN_VIOLATIONS` (`tests/test_output_timezone_guard.py`) gelisteten
  Fundstellen aus `weather_cache.py::get/put` (4), `segment_weather.py::_aggregate_for_segment` (2)
  und `trip_segments.py::convert_trip_to_segments` (3), When der Umbau auf `to_utc()`/`local_dt()`
  abgeschlossen ist, Then sind genau diese 9 Einträge aus dem Register entfernt, kein anderer Eintrag
  hat sich geändert, und `test_known_violations_only_shrink` sowie
  `test_no_unlisted_output_timezone_violations` laufen grün.
  - Test: `uv run pytest tests/test_output_timezone_guard.py -k "known_violations_only_shrink or
    no_unlisted_output_timezone_violations"` — beide grün, Registergröße um exakt 9 geschrumpft.

- **AC-4:** Given die bestehenden Golden-Master-Testsuiten für `convert_trip_to_segments` und
  `_aggregate_for_segment` (u.a. `test_bug_401_segment_localtime.py`,
  `test_issue_1004_ssot_callers.py`, `test_issue_995_segment_start_time.py`,
  `test_onset_respects_configured_day_window.py`, `test_alarm_zeitfenster_ziel.py`,
  `test_provider_tz_normalization.py::test_f001_aggregate_for_segment_converts_non_utc_offset_before_flooring`),
  When der Umbau abgeschlossen ist, Then laufen alle Suiten unverändert grün — kein Assert-Wert musste
  angepasst werden.
  - Test: `uv run pytest tests/tdd/test_bug_401_segment_localtime.py
    tests/tdd/test_issue_1004_ssot_callers.py tests/tdd/test_issue_995_segment_start_time.py
    tests/tdd/test_onset_respects_configured_day_window.py tests/unit/test_alarm_zeitfenster_ziel.py
    tests/test_provider_tz_normalization.py -k f001` — alle grün, Diff der Testdateien selbst leer.

- **AC-5:** Given ein Trip, dessen Zielzone westlich der Startzone liegt und dessen Ankunftszeitpunkt
  lokal noch auf dem vorherigen Kalendertag der UTC-Zeit liegt, When `convert_trip_to_segments` den
  Ankunftstag am Ziel berechnet, Then bleibt der ermittelte Ankunftstag der Ortstag am Ziel (Aufruf
  über `local_dt()`), nicht der davon abweichende UTC-Tag.
  - Test: bestehender Golden-Master `tests/unit/test_alarm_zeitfenster_ziel.py` erweitert bzw.
    gegengeprüft um einen Westziel-Fall mit UTC-Tagesgrenze; erwartet wird der Ortstag, nicht der
    UTC-Tag.

- **AC-6:** Given die vier geänderten Produktivdateien (`utils/timezone.py`, `weather_cache.py`,
  `segment_weather.py`, `trip_segments.py`), When der Umbau abgeschlossen ist, Then enthält keine der
  vier einen unbenutzten Import — insbesondere ist der `timezone`-Import aus `datetime` in
  `trip_segments.py` entfernt, da er nach dem Umbau keine Verwendung mehr hat — und der Lint-Lauf
  zeigt keine neuen Findings gegenüber dem Stand vor dieser Scheibe.
  - Test: `uv run ruff check src/utils/timezone.py src/services/weather_cache.py
    src/services/segment_weather.py src/services/trip_segments.py` (bzw. das projektübliche
    Lint-Kommando) — keine `F401`-Findings (unused import) und keine neuen Findings insgesamt.

## Known Limitations

- **Kein funktionaler Bug** — anders als S5e (Cache-Key-Bug in `massif_closure.py`) ist dies eine
  reine Formbereinigung. Der ursprüngliche Verdacht wurde in der Analyse-Phase recherchiert und
  widerlegt: `weather_cache.py::_storage_key` baut den Cache-Key bereits aus vollen
  ISO-Zeitstempeln mit strukturellem Coverage-Matching, kein analoger Bug zu S5e.
- **Zeilendrift im `KNOWN_VIOLATIONS`-Register:** die dort eingetragenen Zeilennummern (`:184`/`:189`/
  `:275` bzw. `:254`/`:257`) stimmen nicht mehr mit dem aktuellen Stand überein (`:194`/`:199`/`:287`
  bzw. `:246`/`:249`) — beim Entfernen der Einträge ist über den funktionsbezogenen Schlüssel zu
  identifizieren, nicht über die veraltete Zeilennummer.
- **Die fünf anderswo bereits vorhandenen, lokal duplizierten `_as_utc`-Varianten**
  (`weather_change_detection.py:284`, `meteoalarm.py:358`, `dwd_eu.py:188`, `dwd.py:173`,
  `meteofrance.py:257`) werden NICHT migriert — bewusst außerhalb des Scopes dieser Scheibe. Eine
  Zentralisierung dieser fünf Stellen wäre Scope-Creep für eine Standard-Track-Scheibe und bliebe
  künftiger Arbeit vorbehalten.
- **Sehr hohe Aufruferfläche** (Briefing-Versand, Radar-/Onset-Alarmpfad, Compare-Pfad, mehrere
  API-Router, Debug-Router) — das dichte Golden-Master-Testnetz aus AC-4 ist der primäre Schutz
  gegen eine unbeabsichtigte Verhaltensänderung, nicht ein neuer dedizierter Test.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Umsetzung folgt ADR-0051 Regel 1/2 (Zeitpunkt vs. Kalenderzeit, Zone an
  den Daten), Status dort weiterhin „Vorgeschlagen". Die Hausnorm aus #1345 (Wetterdaten tragen
  zonenlose UTC-Zeitstempel) bleibt unverändert gültig und ist die Grundlage für `to_utc()`.
- **Rationale:** Diese Scheibe führt kein neues Architekturmuster ein, sondern zentralisiert eine
  bereits etablierte, korrekte Umrechnung in einen benannten Helfer — konsistent mit dem in
  ADR-0051 beschriebenen Wächter-Modell (`KNOWN_VIOLATIONS` darf nur schrumpfen). Ein eigenes ADR
  wäre für eine reine Aufruf-Formbereinigung ohne Verhaltensänderung unangemessen.

## Changelog

- 2026-08-19: Initial spec created
