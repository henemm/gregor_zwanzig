# Context: fix-1727-s5f-weather-cache-tz

## Request Summary
S5f zu #1727: drei `raw_astimezone`-Fundstellen (9 Codestellen) aus `KNOWN_VIOLATIONS`
(`tests/test_output_timezone_guard.py`) abbauen — `weather_cache.py::get/put`,
`trip_segments.py::convert_trip_to_segments`, `segment_weather.py::_aggregate_for_segment`.
Der ursprüngliche Verdacht (analog zum S5e-Cache-Key-Bug in `massif_closure.py`) wurde
recherchiert und **widerlegt** — siehe Existing Patterns.

## Related Files

| File | Relevanz |
|------|----------|
| `src/services/weather_cache.py` (get :126-127, put :177-178) | Cache-Key aus Fenstergrenzen via `.astimezone(timezone.utc)` |
| `src/services/trip_segments.py::convert_trip_to_segments` (:194, :199, :287 — Zeilendrift ggü. KNOWN_VIOLATIONS-Ordinalen :184/:189/:275) | Segmentstart/-ende aus Etappentag+Startstunde in Ortszone, dann UTC; Ankunftstag am Ziel in Zielortzone |
| `src/services/segment_weather.py::_aggregate_for_segment` (:246/:249 — Zeilendrift ggü. :254/:257) | Segmentbeginn/-ende auf volle UTC-Stunde gerundet (naiv), Adversary-Fund F001 |
| `src/app/models.py:412-413` | `TripSegment.start_time`/`end_time` Vertrag: bereits UTC-aware (`# UTC!`) |
| `src/services/official_alerts/massif_closure.py` | Vorbild für S5e-Cache-Key-Fix (Tag im Key) — hier NICHT einschlägig, siehe unten |
| `tests/test_output_timezone_guard.py:526-654` | `KNOWN_VIOLATIONS`-Register, hier abzubauende Einträge |

## Existing Patterns

- **Muster A (S5a–S5d):** Umgebungsuhr (`date.today()`/`datetime.now()` ohne Zone) → ersetzt durch expliziten Auflöser (`tz_for_coords(lat, lon)`, `trip_local_today(trip, now_utc)`). Nicht einschlägig für S5f (kein Muster-A-Fund hier).
- **Cache-Key-Fix (S5e, `massif_closure.py`, Commit `fdc8443c`):** Bug war ein zu grober Key (`cache_key=src`, Kalendertag NICHT im Schlüssel) → über Mitternacht stale Vortagsdaten. Fix: `cache_key = f"{src}:{ymd}"`.
  **Recherche-Ergebnis für S5f:** `weather_cache.py::_storage_key` baut den Key bereits aus vollen ISO-Zeitstempeln (`f"{bucket}|{window_start.isoformat()}|{window_end.isoformat()}"`), zusätzlich strukturelles Coverage-Matching statt Key-Gleichheit. **Kein analoger Bug** — die drei Funde dort sind laut Rubrik-Kommentar in `test_output_timezone_guard.py:601-604` reine "Umrechnungen NACH UTC (nach Hausnorm #1345 unauffällig)", die der AST-Scanner nur deshalb listet, weil er nicht zwischen rohem und korrektem `.astimezone()` unterscheiden kann.
- **Erwartete Lösungsform für S5f:** Form-Bereinigung — rohe `.astimezone(timezone.utc)`-Aufrufe durch einen benannten, zentralen Helfer ersetzen. `utils/timezone.py` ist vom Scanner explizit ausgenommen (dort existiert aktuell nur ein naiver `_as_utc(dt)`-Guard, kein exportierter `to_utc()`); mehrere Module haben stattdessen lokal duplizierte `_as_utc`-Helfer (`weather_change_detection.py:284`, `meteoalarm.py:358`, `dwd_eu.py:188`, `dwd.py:173`, `meteofrance.py:257`). Ein zentraler, exportierter `to_utc()`-Helfer in `utils/timezone.py` wäre konsistent mit dem Vorbild der übrigen Scheiben.
- **`trip_segments.py`-Konvertierung selbst ist historisch korrekt und bewusst** (Fix für Bug #401, `tests/tdd/test_bug_401_segment_localtime.py`): lokale Etappenzeit wird über `tz_for_coords()` aufgelöst und explizit nach UTC gewandelt, damit der `# UTC!`-Vertrag von `TripSegment` gilt. Auch hier ist der Umbau reine Aufrufform, keine Verhaltensänderung.
- **`segment_weather.py::_aggregate_for_segment`** hat bereits einen dedizierten Pinning-Test für das Zonenverhalten: `tests/test_provider_tz_normalization.py::test_f001_aggregate_for_segment_converts_non_utc_offset_before_flooring` (:465).

## Existing Specs

- `docs/specs/modules/weather_cache.md`
- `docs/specs/modules/segment_weather.md`
- Kein Spec-Eintrag für `trip_segments.py` gefunden — ggf. in `/30-write-spec` als neue oder erweiterte Spec berücksichtigen.

## Dependencies

- **Upstream:** `TripSegment`-Datenmodell (`src/app/models.py`), `tz_for_coords()` (Ortszonen-Auflösung).
- **Downstream (sehr breite, produktionskritische Aufruferfläche):**
  - `convert_trip_to_segments`: `stage_weather.py:49`, `trip_report_scheduler.py::_convert_trip_to_segments`-Wrapper (Briefing-Versand, mehrfach aufgerufen), `trip_command_processor.py:301-302`, `preview_service.py:153`, `api/routers/validator.py:325/388`, `api/routers/debug.py:69/76`, rekursiv in `trip_segments.py` selbst.
  - `_aggregate_for_segment`: über `fetch_segment_weather` (public Entry-Point) an Briefing-Pfad, Radar-/Onset-Alarmpfad (`trip_alert.py`), Compare-Pfad (`compare_location_weather_source.py`); zusätzlich direkt in vielen TDD-Tests aufgerufen (Bypass des Public-Pfads).
  - `weather_cache.py::get/put`: ausschließlich über `segment_weather.py:144`/`:222`.

## Bestehende Tests als TDD-Vorbild

| Datei | Bezug |
|---|---|
| `tests/unit/test_weather_cache.py` | Direkte Unit-Tests `WeatherCacheService` |
| `tests/integration/test_segment_weather_cache.py` | Integration Cache ↔ `SegmentWeatherService` |
| `tests/unit/test_forecast_cache_sharing.py` | Cache-Sharing (#1329-Kontext) |
| `tests/test_provider_tz_normalization.py:465` | Bestes Vorbild für `_aggregate_for_segment`-Zonenverhalten |
| `tests/tdd/test_bug_401_segment_localtime.py` | Historischer RED-Test für das UTC-Konvertierungsverhalten von `convert_trip_to_segments` |
| `tests/tdd/test_issue_1004_ssot_callers.py`, `test_issue_995_segment_start_time.py`, `test_onset_respects_configured_day_window.py` | Golden-Master/Symmetrie-Tests, dürfen sich nicht ändern |
| `tests/unit/test_alarm_zeitfenster_ziel.py` | Ziel-Segment-Fenster (Ankunftstag) |

## Risks & Considerations

- **Sehr hohe Aufruferfläche mit dichtem Golden-Master-Testnetz** — Umbau muss "gleiche Semantik, andere Aufrufform" bleiben, keine Verhaltensänderung. Höheres Regressionsrisiko als die vorangegangenen Muster-A-Scheiben.
- **Zeilendrift in `KNOWN_VIOLATIONS`:** die dort eingetragenen Zeilennummern (:184/:189/:275 bzw. :254/:257) stimmen nicht mehr mit dem aktuellen Stand überein (:194/:199/:287 bzw. :246/:249) — beim Eintragen des Fixes/der Entfernung korrigieren, sonst entsteht dieselbe Falle wie in `reference_bei_formataenderungen_nach_dem_wert_suchen.md`.
- **Kein funktionaler Bug gefunden** — anders als bei S5e ist dies eine reine Formbereinigung. Sollte in der Spec klar so benannt werden, damit keine falsche Erwartung ("Bug behoben") entsteht.
- **Möglicher zentraler Helfer (`to_utc()` in `utils/timezone.py`)** würde auch die lokal duplizierten `_as_utc`-Varianten in anderen Modulen als Vorbild dienen können — Scope-Entscheidung für `/20-analyse`: nur die 9 KNOWN_VIOLATIONS-Stellen umbauen, oder gleich zentralisieren? Tendenz: nur die 9 Stellen, Zentralisierung wäre Scope-Creep für eine Standard-Track-Scheibe.

## Analysis

### Type
Feature/Tech-Debt-Cleanup (kein Bug — siehe Risks: reine Formbereinigung, kein funktionaler Fehler).

### Wichtige Korrektur ggü. Context-Phase
Die 9 Fundstellen sind **nicht alle gleichartig**: 8 konvertieren Richtung UTC, **1 Stelle**
(`trip_segments.py:287`, `arrival_time.astimezone(dest_tz)` — Ankunftstag am Ziel) konvertiert
Richtung **Ortszone des Ziels**. Dafür existiert bereits der passende öffentliche Helfer
`local_dt(dt, tz)` in `utils/timezone.py` — dort ist kein neuer Code nötig, nur die
Aufrufform tauschen.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/utils/timezone.py` | MODIFY | neue Funktion `to_utc(dt)` = `_as_utc(dt).astimezone(timezone.utc)` — naiv wird nach Hausnorm #1345 als UTC gelabelt, aware wird ECHT konvertiert (Regressionsschutz Adversary-Fund F001) |
| `src/services/weather_cache.py` | MODIFY | `get`/`put` (4 Call-Sites) auf `to_utc()` umstellen — praktisch No-op, da `segment.start_time`/`end_time` per Vertrag schon UTC-aware sind |
| `src/services/segment_weather.py` | MODIFY | `_aggregate_for_segment` (2 Call-Sites) auf `to_utc()` umstellen, **Kettung an `.replace(minute=0,...)` erhalten** (`to_utc(x).replace(...)`, nicht die replace-Kette anfassen); neuer Import aus `utils.timezone` nötig (bisher keiner vorhanden) |
| `src/services/trip_segments.py` | MODIFY | Segmentstart/-ende (2 Call-Sites) → `to_utc()`; Ankunftstag (:287) → `local_dt()` statt `to_utc()` (sonst Westziel-Tagesverschiebungsbug); `timezone`-Import aus `datetime` wird nach dem Umbau ungenutzt und muss raus (nur dafür importiert) |
| `tests/test_output_timezone_guard.py` | MODIFY | 9 Einträge aus `KNOWN_VIOLATIONS` entfernen (funktionsbezogene Schlüssel, Zeilendrift in den Begründungstexten ist für die Entfernung selbst irrelevant) |
| `tests/unit/test_utils_timezone.py` | CREATE (optional) | Isolierter Unit-Test für `to_utc()`: naiv/UTC-aware/Offset-aware |

### Scope Assessment
- Files: 4 Produktivdateien + 1 Testdatei (+ optional 1 neue Testdatei)
- Estimated LoC: **~20–30 Produktivcode** (weit unter dem 250-LoC-Limit)
- Risk Level: MEDIUM — kein Konzeptrisiko (da `to_utc()` für aware Eingaben bit-identisch zum bisherigen rohen Aufruf ist), aber dichtes Golden-Master-Testnetz an `convert_trip_to_segments`/`_aggregate_for_segment` macht Ausführungsfehler teuer

### Technical Approach
Zentraler `to_utc()`-Helfer in `utils/timezone.py` (Komposition aus vorhandenem `_as_utc` +
`.astimezone(timezone.utc)`) für die 8 UTC-Zielstellen; die 9. Stelle (`trip_segments.py:287`)
auf den bereits existierenden `local_dt()`-Helfer umstellen. Keine Migration der fünf
anderswo duplizierten lokalen `_as_utc`-Varianten (bleibt bewusst außerhalb dieser Scheibe).

**Umbau-Reihenfolge (sicherstes zuerst):**
1. `to_utc()` schreiben + isoliert testen (naiv/UTC-aware/Offset-aware, 3 Fälle)
2. `weather_cache.py` (No-op-Risiko am geringsten) — Tests: `test_weather_cache.py`, `test_segment_weather_cache.py`, `test_forecast_cache_sharing.py`
3. `segment_weather.py` (hat dedizierten F001-Test als Sicherheitsnetz) — Test: `test_provider_tz_normalization.py::test_f001_...`
4. `trip_segments.py` (dichtestes Golden-Master-Netz, zwei verschiedene Helfer in einer Funktion) — Golden-Master-Tests aus der Tabelle oben
5. `KNOWN_VIOLATIONS` bereinigen — `test_known_violations_only_shrink` + `test_no_unlisted_output_timezone_violations` müssen grün werden
6. Volle Testsuite: `pytest tests/ -k "timezone or trip_segments or weather_cache or segment_weather or output_timezone_guard or provider_tz_normalization or bug_401"`

### Dependencies
Siehe oben (Related Files/Dependencies) — keine neuen Erkenntnisse ggü. Context-Phase.

### AC-Kandidaten für /30-write-spec
1. `to_utc()`: naiver Zeitstempel → als UTC gelabelt (Hausnorm #1345), identischer Wanduhrwert.
2. `to_utc()`: aware Zeitstempel in Nicht-UTC-Zone (z. B. +02:00) → korrekt nach UTC konvertiert, nicht nur `tzinfo`-Ersatz (Regressionsschutz F001).
3. Die 9 gelisteten Fundstellen verschwinden exakt aus `KNOWN_VIOLATIONS`, kein anderer Eintrag ändert sich, Guard-Tests bleiben grün.
4. Golden-Master-Suiten für `convert_trip_to_segments` und `_aggregate_for_segment` bleiben unverändert grün — keine Werteänderung.
5. `trip_segments.py:287` nutzt `local_dt()`, Ankunftstag bleibt Ortstag am Ziel (nicht UTC-Tag).
6. Keine unbenutzten Imports (`timezone` aus `datetime` in `trip_segments.py` entfernt), keine neuen Lint-Fehler.

### Open Questions
- [ ] Soll `tests/unit/test_utils_timezone.py` als eigene neue Testdatei angelegt werden, oder reicht Abdeckung über die bestehenden Verbraucher-Tests? (Empfehlung: eigene Datei, da `to_utc()` sonst nie isoliert getestet wäre.)
