# Context: fix-1331-1334-daywindow-gaps

## Request Summary
Zwei Korrektheits-Restlöcher der bereits ausgelieferten Tagesfenster-Aggregation
(Epic #1319 Scheibe A) schließen: (#1331) Fehl-Entwarnung, wenn die Zielort-Stunden
nach Ankunft ausfallen, weil die Lücken-Erkennung `night_weather` nicht kennt;
(#1334) falsche Min/Max bei Etappen über Mitternacht, weil der Segment-Filter nur
die Stunde, nicht das volle Datum vergleicht.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/day_window.py:59-66` | `segments_have_gap()` iteriert nur über `segments`, prüft `night_weather` nicht (#1331 Kern) |
| `src/output/renderers/day_window.py:105-110` | `build_day_window_points()` zieht Nach-Ankunft-Stunden ausschließlich aus `night_weather`; genau diese Stunden fehlen still bei `night_weather=None` |
| `src/output/renderers/sms_trip.py:122-160,228` | `_segments_to_normalized_forecast()` ruft `segments_have_gap(segments)` (Z.228) und `build_day_window_points(segments, night_weather, …)` (Z.160) — hier muss `night_weather` in die Lücken-Erkennung mit |
| `src/services/trip_report_scheduler.py:1275-1287` | `_fetch_night_weather()` schluckt jede Exception, liefert still `None`, setzt **kein** `has_error` → Ausfall strukturell unsichtbar (#1331 Sekundär) |
| `src/services/segment_weather.py:226-257` | `_aggregate_for_segment()` filtert per `dp.ts.hour` statt vollem Zeitstempel → Über-Mitternacht-Kontamination (#1334 Kern) |

## Existing Patterns
- **#1328 (Vorbild für #1331):** ausgefallenes *Segment* → `-` wird zu `?` (Kennzeichnung statt Fehl-Entwarnung). Invariante #1328 AC-2: ein *gefundener* Wert bleibt unverändert sichtbar. #1331 ist die identische Regel, angewandt auf die Zielort-Stunden.
- **Ein Fenster, eine Quelle für alle Kurzformen** (ADR-0025): Die Lücken-/Aggregations-Logik sitzt zentral in `day_window.py` bzw. `segment_weather.py` und speist SMS, E-Mail-Kurzzusammenfassung, „Pille" und Telegram-Fußzeile gemeinsam — ein Fix wirkt auf alle vier.
- **#806/#856 (Kontext für #1334):** Der Stunden-Filter wurde bewusst so gebaut (Randstunde exklusiv, <1h-Fallback), aber ohne Datumsvergleich. Der Fix muss diese beiden Invarianten (jede Stunde genau einem Segment; Segment <1h) beim Umstieg auf vollen Zeitstempel bewahren.

## Dependencies
- **Upstream #1331:** `SegmentWeatherData.has_error/.timeseries`, `NormalizedTimeseries`, `_fetch_night_weather()`.
- **Upstream #1334:** `TripSegment.start_time/.end_time` (volle `datetime`), `NormalizedTimeseries.data[].ts`.
- **Downstream #1331:** `_segments_to_normalized_forecast()` → `has_data_gap` → alle vier Kurzform-Renderer (`?`-Kennzeichnung).
- **Downstream #1334:** `SegmentWeatherData`-Aggregat → Briefing-Werte **und** potenziell Schwellen-/Alarm-Auswertungen, die auf `temp_min_c/temp_max_c` aufsetzen.

## Existing Specs
- `docs/specs/modules/sms_daywindow_aggregation.md` — Spec zu #1317/#1319 Scheibe A (day_window-Modul, AC-2/AC-9). Direkte Grundlage; #1331 ist deren Nachschärfung.
- `docs/reference/sms_briefing_overview.md` — Leitlinie SMS/Kurzform (Fenster, ADR-0025, „keine erfundenen Uhrzeiten").

## Risks & Considerations
- **#1334 Regressionsgefahr:** Umstieg von Stunden- auf Zeitstempel-Filter muss die #806/#856-Fälle bitgleich erhalten (jede Stunde genau einem Segment; Segment <1h). Golden-/Bestandstests von `_aggregate_for_segment` vorher grün baselinen.
- **#1331 zwei Ebenen:** (a) `segments_have_gap()` um `night_weather` erweitern (nutzersichtbar, Kern), (b) `_fetch_night_weather()` seinen Fehlerfall überhaupt nach außen signalisieren lassen. (b) ist Voraussetzung, damit ein *echter Provider-Fehler* (nicht nur `None`) sichtbar wird — Scope prüfen, evtl. minimaler Rückgabe-Kontrakt.
- **Mail-Pfad-Gate:** #1331 fasst Kurzform-Renderer an (`sms_trip.py`) → `renderer_mail_gate.py` + `briefing_mail_validator.py` greifen. Beim Commit einplanen.
- **Kein neuer Fetch:** Beide Fixes arbeiten auf bereits vorhandenen Daten (day-window nutzt vorhandene `night_weather`; #1334 filtert vorhandene Zeitreihe). Kein zusätzlicher open-meteo-Verbrauch (#1329).
- **Test-Schicht:** Beide reproduzierbar im deterministischen Kern (Adversary hat es netzfrei mit Fixtures nachgestellt) — keine Live-E2E nötig für den Bug-Nachweis.

## Analysis

### Type
Bug (2 Stück, gemeinsamer Pfad Tagesfenster-/Segment-Aggregation)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/segment_weather.py` | MODIFY | `_aggregate_for_segment` (Z.240-257): Stunden-Filter → Stunden-Floor + voller Zeitstempel (#1334) |
| `src/output/renderers/day_window.py` | MODIFY | `segments_have_gap()` (Z.59-66): `night_weather`+`tz`-Parameter, Nach-Ankunft-Lücke spiegelbildlich zu `build_day_window_points` (#1331 a) |
| `src/output/renderers/sms_trip.py` | MODIFY | Z.228: `night_weather`/`tz` an `segments_have_gap` durchreichen (#1331 a) |
| `tests/unit/test_forecast_cache_sharing.py` | MODIFY | Neue netzfreie Fälle für #1334 (Über-Mitternacht, #806/#856-Guards) |
| `tests/tdd/test_sms_daywindow_aggregation.py` | MODIFY | Neue Fälle für #1331 (`?` statt `-`, Über-Flagging-Guard, Regressions-Guard) |

### Scope Assessment
- Files: 3 Quell- + 2 Test-Dateien
- Estimated LoC: ~+40/-20 (2 chirurgische Kernänderungen)
- Risk Level: MEDIUM (#1334 speist Alarm-Snapshots → Golden-Baseline nötig; #1331 berührt Mail-Pfad → renderer_mail_gate + briefing_mail_validator)

### Technical Approach
**#1334** (`segment_weather.py:240-257`): Start/Ende auf volle Stunde flooren, dann Zeitstempel statt `.hour` vergleichen:
`start_floor == end_floor` → `dp.ts == start_floor` (bewahrt #856, Sub-Stunden-Segment bekommt seine Stunde); sonst `start_floor <= dp.ts < end_floor` (bewahrt #806 Rand-exklusiv + korrekte Datumsabgrenzung über Mitternacht). Der bisherige Wraparound-Zweig (Z.254) entfällt komplett. Voraussetzung: `dp.ts` und `segment.start_time` beide UTC-aware (bereits gegeben).

**#1331 Teil (a)** (`day_window.py` + `sms_trip.py`): `segments_have_gap(segments, night_weather=None, tz=UTC)` — zusätzlich zur Segment-Lücke prüfen: `night_expected = arrival_hour <= DAY_WINDOW_END_HOUR` UND `night_missing = night_weather is None or not night_weather.data`. Die `arrival_hour`-Schranke verhindert Über-Flagging bei Ankunft nach 19:00. Erfüllt #1328-Invariante (`?` ersetzt nur `-`, gefundener Wert bleibt sichtbar). 1 Aufrufer, mit Default-Args abwärtskompatibel.

**#1331 Teil (b)** (`_fetch_night_weather` Fehler-Signal): **NICHT im Scope.** Aus Empfängersicht ist „keine Nach-Ankunft-Daten" mit `?` korrekt gekennzeichnet, unabhängig von der Ursache — Teil (a) fängt echten Fehler UND legitim-leer, weil er auf `None`/leer prüft, nicht auf `has_error`. (b) wäre nur interne Telemetrie ohne Rendering-Unterschied → separater, entkoppelter Diagnose-Change (Sammel-Eintrag #1199), nicht hier.

### Reihenfolge
Zuerst #1334 (strikt lokal, kein Mail-Gate, liefert korrekte Extremwerte als Baseline), dann #1331 Teil (a) (berührt Mail-Pfad → Gate/Validator ans Ende). Beide vor Release nötig.

### Open Questions
- [ ] Scope-Bestätigung: #1331 Teil (b) bewusst aus dem Workflow raus (nur Teil a)? — Empfehlung: ja.

