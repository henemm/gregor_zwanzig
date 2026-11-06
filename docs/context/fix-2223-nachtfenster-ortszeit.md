# Context: fix-2223-nachtfenster-ortszeit

## Request Summary
`fetch_night_weather` bildet das Ende des Nachtfensters ("06:00 Folgetag") ueber den UTC-Kalendertag der Ankunft. Kommt der Trip nach UTC-Mitternacht (aber am Ziel noch am selben Ortsabend) an, springt das Fenster von ~6 h auf ~30 h (bis 2,5x Provider-Stunden). Soll: 06:00 Ortszeit am Ziel. Issue #2223 (Triage C4-12 aus #1199), Naehe #2150 (Tageskontingente).

## Related Files
| File | Relevance |
|------|-----------|
| src/services/segment_weather.py:569-640 `fetch_night_weather` | BUG: Z.608-614 `datetime.combine(arrival.date()+1d, min.time(), tzinfo=utc).replace(hour=6)` |
| src/utils/timezone.py `tz_for_coords`, `resolve_location_tz`, `location_tz` | vorhandener, einziger Zeitzonen-Aufloeser (Trip UND Vergleich) |
| src/app/day_window.py:148 `display_end_time` | liefert `arrival` (UTC-aware) |
| src/services/trip_report_scheduler.py:2713 `_fetch_night_weather` | duenner Delegator (Versand) |
| src/services/preview_service.py:235-240 | zweiter Aufrufer (Vorschau, ggf. FixtureProvider) |
| src/output/renderers/trip_report.py:536 `_extract_night_rows` | Rendering rechnet schon in Ortszeit (#1402 `local_dt`), Fetch ist der einzige UTC-Teil |

## Existing Patterns
- Interne Pipeline UTC, Umrechnung nur an der Grenze (utils/timezone.py Kopf).
- Ortstag-Anker: Specs fix_1695_anker_ortsmitternacht, fix_1721_nachtausgabe; #1402 `local_dt()`.
- `resolve_location_tz` -> None = nicht aufloesbar; `location_tz` -> UTC-Rueckfall.

## Dependencies
- Upstream: `display_end_time`, `tz_for_coords` (timezonefinder), `SegmentWeatherService.fetch_segment_weather`.
- Downstream: Nacht-Stundentabelle, Nacht-Tiefsttemperatur (#1484), Nacht-Gewitter-Zusatz (#1651), Provider-Call-Log/Kontingent (`briefing_nacht`).

## Existing Specs
- docs/specs/modules/segment_weather.md, fix_1339_nachtwetter_fallback.md, fix_1695_anker_ortsmitternacht.md, thunder_night_at_destination_channels.md. fix_2314 ist nur Test-Fixtures (nicht verwandt).

## Risks & Considerations
- Reihenfolge: Ortsdatum der Ankunft bestimmen, +1 Tag, 06:00 Ortszeit, nach UTC. Sommerzeit-Wechsel (ZoneInfo regelt, aber Test sinnvoll).
- Ankunft nach 06:00 Ortszeit des Ankunftstags ist normal; Ankunft vor 06:00 Ortszeit (Nachtankunft)? Dann waere "Folgetag 06:00" ~30 h — Verhalten bewusst in der Analyse klaeren (heute ebenso).
- Rueckfall bei nicht aufloesbarer Zone: UTC wie bisher.
- Gemeinsamer Pfad Versand+Vorschau: ein Fix, beide wirken. Mail-Renderer-Gate greift nur bei Mail-Inhalts-Dateien (segment_weather.py vermutlich nicht).
- Test: Ankunft z. B. 23:30 UTC Mallorca-/Korsika-Ziel (Ortszeit 00:30/01:30) und westliche Zone (UTC-Mitternacht noch Vortag lokal).

## Analysis

### Type
Bug (Betriebsrisiko, Provider-Kontingent #2150).

### Root Cause
`fetch_night_weather` (src/services/segment_weather.py:610-614) bildet das Fensterende als `arrival.date()+1 Tag, 06:00, tzinfo=UTC`. Zwei Folgen:
1. **Westliche Zonen (UTC-x):** Ankunft am Ortsabend nach UTC-Mitternacht (z. B. 20:00 Ortszeit = 01:00 UTC) → UTC-Datum ist schon der Folgetag → Ende = übernächster Tag 06:00 UTC ≈ 29 h statt ~10 h (bis 2,5x Provider-Stunden).
2. **Europa (Hauptfall GR20/GR221):** Ende ist 06:00 UTC = 07:00/08:00 Ortszeit statt 06:00 Ortszeit (1–2 h zu lang, kein Sprung). Der Renderer (`_extract_night_rows`, trip_report.py:~560) schneidet in Ortszeit bei `h <= 6` am Folgetag; der Fetch ist der einzige UTC-Teil.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/segment_weather.py | MODIFY | Ende = 06:00 Ortszeit am Ortsdatum(Ankunft)+1, danach nach UTC; Zone via `location_tz(seg.end_point)` aus utils/timezone.py (UTC-Rückfall wie bisher) |
| tests/tdd/test_night_window_ortszeit.py | CREATE | Verhaltenstests (echter Provider-Stub zählt abgefragte Stunden): Ankunft 20:00 Ortszeit UTC-5 → ~10 h; Mallorca/Korsika → Ende 06:00 Ortszeit; Sommerzeit-Wechsel; nicht auflösbare Zone → UTC-Rückfall |

Versand (`trip_report_scheduler._fetch_night_weather`) und Vorschau (`preview_service`) rufen dieselbe Funktion → ein Fix wirkt auf beide. Keine Mail-Inhalts-Datei → Renderer-Gate greift nicht.

### Scope Assessment
- Files: 2 (1 Code, 1 Test)
- Estimated LoC: +~15/-5 Code, ~+80 Test
- Risk Level: LOW (isolierte Funktion, ein Aufrufpfad)

### Technical Approach
```
tz = location_tz(seg.end_point)           # EIN Aufloeser, UTC-Rueckfall
local_arr = local_dt(arrival, tz)
end_local = datetime.combine(local_arr.date()+1d, time(6,0), tzinfo=tz)
next_morning = end_local.astimezone(timezone.utc)
```
Nachtankunft vor 06:00 Ortszeit bleibt bewusst wie bisher ("Folgetag 06:00"): der Renderer ankert ebenfalls auf Ankunftsdatum+1 — Änderung wäre Verhaltensänderung außerhalb des Tickets. `ZoneInfo` löst Sommerzeit korrekt auf (nicht per Offset rechnen).

### Dependencies
`display_end_time` (liefert UTC-aware `arrival`), `utils.timezone.location_tz/local_dt`, `SegmentWeatherService.fetch_segment_weather` (Cache/Kontingent `briefing_nacht`).

### Open Questions
- [ ] keine offen (Nachtankunft-Verhalten: unverändert, siehe oben)
