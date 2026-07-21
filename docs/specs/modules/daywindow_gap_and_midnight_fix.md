---
entity_id: daywindow_gap_and_midnight_fix
type: module
created: 2026-07-21
updated: 2026-07-21
status: draft
version: "1.0"
tags: [sms, kurzform, daywindow, segment-aggregation, bug, 1331, 1334]
---

# Tagesfenster-Aggregation: Restlöcher (#1331 + #1334)

## Approval

- [x] Approved (PO 'go' 2026-07-21)

## Purpose

Zwei Korrektheits-Restlöcher der ausgelieferten Tagesfenster-Aggregation (Epic #1319
Scheibe A) schließen, die weiterhin falsche Sicherheitsaussagen erzeugen:
**#1331** — Fehl-Entwarnung, wenn die Zielort-Stunden nach Ankunft ausfallen, weil die
Lücken-Erkennung `night_weather` nicht kennt; **#1334** — falsche Min/Max-Werte bei
Etappen über Mitternacht, weil der Segment-Filter nur die Stunde, nicht das volle Datum
vergleicht.

## Source

- **File:** `src/services/segment_weather.py` — **Identifier:** `SegmentWeatherService._aggregate_for_segment` (Z.226-257) — #1334
- **File:** `src/output/renderers/day_window.py` — **Identifier:** `segments_have_gap` (Z.59-66) — #1331 (gemeinsame Lücken-Erkennung)
- **File:** `src/output/renderers/sms_trip.py` — **Identifier:** `_segments_to_normalized_forecast` (Call-Site Z.228) — #1331 (SMS-`?`)
- **File:** `src/output/renderers/compact_summary.py` — **Identifier:** `_collect_hourly_data` / Prosa-Aussagen — #1331 (E-Mail-Kurzzusammenfassung)
- **File:** `src/output/renderers/narrow.py` — **Identifier:** `_tg_day_footer` — #1331 (Telegram-Fußzeile)
- **File:** `src/output/renderers/email/helpers.py` — **Identifier:** `build_metrics_summary_pills` — #1331 (Kopf-Pille)

Alle liegen im **Python-Core / Domain-Backend** (`src/services/`, `src/output/`). Keine Go-API-, keine SvelteKit-Berührung.

## Estimated Scope

- **LoC:** ~+90/-30 (PO-Entscheidung 2026-07-21: Unsicherheits-Kennzeichnung für **alle vier** Kurzformen, nicht nur SMS)
- **Files:** 6 Quell- + 2 Testdateien
- **Effort:** medium

## Dependencies

- **Upstream #1334:** `TripSegment.start_time/.end_time` (volle UTC-`datetime`), `NormalizedTimeseries.data[].ts` (UTC-aware, stündlich).
- **Upstream #1331:** `SegmentWeatherData.has_error/.timeseries`, `NormalizedTimeseries`, `local_hour`, `DAY_WINDOW_END_HOUR` (bereits in `day_window.py` importiert).
- **Downstream #1334:** `SegmentWeatherData`-Aggregat → Briefing-Werte **und** Schwellen-/Alarm-Auswertungen (Golden-Baseline nötig).
- **Downstream #1331:** `has_data_gap` → `output/tokens/builder.py:227` (`has_gap`) → alle vier Kurzformen (SMS, E-Mail-Kurzzusammenfassung, „Pille", Telegram-Fußzeile).
- **Gates:** #1331 fasst `sms_trip.py` (Kurzform-Renderer) an → `renderer_mail_gate.py` + `briefing_mail_validator.py` beim Commit.

## Behaviour

### #1334 — Segment-Filter über Mitternacht
`_aggregate_for_segment` filtert die (evtl. breitere/gecachte) Zeitreihe auf genau das
Segment-Fenster über **volle Zeitstempel** statt reiner Stundenzahl. Start/Ende werden auf
die volle Stunde geflooret; danach:
- `start_floor == end_floor` (Sub-Stunden-Segment innerhalb einer Stunde) → nur `dp.ts == start_floor` (bewahrt #856).
- sonst → `start_floor <= dp.ts < end_floor` (bewahrt #806 Rand-exklusiv **und** grenzt korrekt nach Datum ab).

Der bisherige Wraparound-Zweig (`dp.ts.hour >= seg_start_h or dp.ts.hour < seg_end_h`, Z.254),
der Stunden von **jedem** Tag zog, entfällt ersatzlos. Voraussetzung — `dp.ts` und
`segment.start_time` sind beide UTC-aware — ist bereits erfüllt.

### #1331 — Lücken-Erkennung inkl. Zielort-Stunden
`segments_have_gap()` bekommt `night_weather` und `tz` als Parameter (Default `None`/UTC,
abwärtskompatibel). Zusätzlich zur bestehenden Segment-Lücke meldet die Funktion eine
Lücke, wenn das Tagesfenster Nach-Ankunft-Stunden erwartet, diese aber fehlen:
- `night_expected = arrival_hour <= DAY_WINDOW_END_HOUR` (arrival_hour aus dem letzten Segment)
- `night_missing = night_weather is None or not night_weather.data`
- Lücke, wenn Segment-Lücke **oder** (`night_expected` **und** `night_missing`).

Die `arrival_hour`-Schranke verhindert Über-Flagging bei Ankunft nach 19:00 (keine
erwarteten Fensterstunden am Ziel). Die vier Kurzformen ziehen dieselbe erkannte Lücke und
ersetzen die betroffene **Entwarnungs**-Aussage durch einen Unsicherheitsmarker — ein
tatsächlich gefundener Wert bleibt in jeder Kurzform sichtbar (#1328-Invariante):

- **SMS** (`sms_trip.py`): `has_data_gap=True` → Token-Builder zeigt `?` statt `-` für die fünf Fenster-Symbole (R/PR/W/G/TH:) — Mechanismus aus #1328 bereits vorhanden.
- **E-Mail-Kurzzusammenfassung** (`compact_summary.py`): keine positive Entwarnung ("trocken"/"kein Gewitter") bei unvollständigem Zielfenster; stattdessen ein Fließtext-Unsicherheitsmarker (`?` bzw. knapper Hinweis).
- **Telegram-Fußzeile** (`narrow.py::_tg_day_footer`) und **Kopf-Pille** (`email/helpers.py::build_metrics_summary_pills`): dasselbe — die Entwarnungs-Aussage (`⚡ kein` etc.) wird bei Lücke durch einen Unsicherheitsmarker ersetzt, nicht als "sicher entwarnt" gerendert.

**Leitplanke (PO-Entscheidung 2026-07-21):** Kein Kanal darf bei unvollständigem
Zielfenster eine positive Entwarnung aussprechen — Konsistenz über alle Kurzformen
(ADR-0025: keine Widersprüche zwischen den Kanälen). Die exakte Marker-Wortwahl je Kanal
legt die Umsetzung fest; geprüft wird über die echte Ausgabe (Abwesenheit der
Entwarnungs-Phrase + Anwesenheit eines Unsicherheitsmarkers).

**Nicht im Scope:** Teil (b) — `_fetch_night_weather()` einen echten Provider-Fehler nach
außen signalisieren zu lassen. Aus Empfängersicht kein Rendering-Unterschied (Teil a fängt
Fehler wie legitim-leer gleichermaßen); reine interne Diagnose → Sammel-Eintrag #1199.

## Acceptance Criteria

- **AC-1:** Given eine Etappe über Mitternacht (Start 22:00 Tag 1 → Ende 02:00 Tag 2) und eine Zeitreihe mit vollen Tagen (48 h) / When `_aggregate_for_segment` das Aggregat bildet / Then fließen ausschließlich die Stunden 22:00, 23:00, 00:00, 01:00 der **korrekten** Tage ein, `temp_min_c`/`temp_max_c` stammen nur aus diesen vier Stunden, und Punkte gleicher Uhrzeit vom Vor- oder Folgetag sind ausgeschlossen.

- **AC-2:** Given ein normales Tag-Segment 10:00 → 13:00 / When das Aggregat gebildet wird / Then ist die Endstunde 13:00 ausgeschlossen (Stunden 10, 11, 12) — die #806-Invariante bleibt bitgleich erhalten.

- **AC-3:** Given ein Sub-Stunden-Segment 10:15 → 10:45 auf einer stündlichen Zeitreihe / When das Aggregat gebildet wird / Then enthält es genau den 10:00-Datenpunkt (nicht leer) — die #856-Invariante bleibt erhalten.

- **AC-4:** Given ein Trip-Briefing mit fehlerfreien Segmenten, Ankunft 12:00 und `night_weather=None`, sodass das 12–19-Uhr-Fenster am Ziel keine Daten hat / When die vier Kurzformen (SMS, E-Mail-Kurzzusammenfassung, Kopf-Pille, Telegram-Fußzeile) gerendert werden / Then spricht **keine** von ihnen eine positive Entwarnung für das unvollständige Zielfenster aus (kein `-`, kein "trocken"/"kein Gewitter"/"⚡ kein"), sondern zeigt einen Unsicherheitsmarker (SMS: `?` statt `-` für R/PR/W/G/TH:; Fließtext-Kanäle: Marker statt Entwarnungs-Phrase).

- **AC-5:** Given denselben Fall wie AC-4, aber mit einem tatsächlich gefundenen Wert in einer belegten Stunde (z.B. Regen aus einem Segment vor Ankunft) / When gerendert wird / Then bleibt dieser gefundene Wert in jeder Kurzform unverändert sichtbar und wird **nicht** durch den Unsicherheitsmarker ersetzt (#1328-Invariante AC-2).

- **AC-6:** Given ein Trip-Briefing mit Ankunft nach 19:00 Uhr und `night_weather=None` / When die Lücken-Erkennung läuft / Then wird **keine** Zielort-Lücke gemeldet (kein `?`), weil im Tagesfenster keine Nach-Ankunft-Stunden erwartet werden — Über-Flagging-Guard.

- **AC-7:** Given ein vollständiges Briefing mit fehlerfreien Segmenten und vollständigem `night_weather` / When gerendert wird / Then meldet `segments_have_gap` keine Lücke und es erscheint kein neues `?` — kein Fehlalarm gegenüber dem bisherigen Verhalten (Regressions-Guard).

## Test Plan

Deterministischer Kern, netzfrei, mit versionierten Fixtures — kein Mock-Theater, Beweis über die echte Ausgabe (`format_sms()` bzw. `_aggregate_for_segment`).

| AC | Test (Datei) | Art |
|----|--------------|-----|
| AC-1 | `tests/unit/test_forecast_cache_sharing.py` — Über-Mitternacht-Segment auf 48h-Fixture (`HourlyCountingFakeProvider`, `t2m_c=float(h)`) | neu |
| AC-2 | `tests/unit/test_forecast_cache_sharing.py` — 10:00→13:00, Endstunde ausgeschlossen | neu |
| AC-3 | `tests/unit/test_forecast_cache_sharing.py` — 10:15→10:45, genau 1 Punkt | neu |
| AC-4 | `tests/tdd/test_sms_daywindow_aggregation.py` — Ankunft 12:00, `night_weather=None` → `?` in allen 4 Kanälen | neu |
| AC-5 | `tests/tdd/test_sms_daywindow_aggregation.py` — gefundener Wert bleibt sichtbar | neu |
| AC-6 | `tests/tdd/test_sms_daywindow_aggregation.py` — Ankunft nach 19:00 → kein `?` | neu |
| AC-7 | `tests/tdd/test_sms_daywindow_aggregation.py` — vollständige Daten → kein neues `?` | neu |

Vor der Änderung: bestehende Golden-/Snapshot-Tests von `_aggregate_for_segment` und der
Kurzform-Suiten grün baselinen (Baseline-Lauf), damit die #1334-Extremwert-Korrektur nicht
als Fremd-Regression missgedeutet wird.

## Risks & Considerations

- **#1334 Golden-Baseline:** Über-Mitternacht-Etappen bekommen jetzt engere, korrekte Extremwerte → Alarm-Snapshots dieser Etappen können sich ändern (gewollt). Vorher baselinen.
- **#1331 Mail-Gate:** `sms_trip.py` ist Mail-Inhalt → `renderer_mail_gate.py` + `briefing_mail_validator.py` beim Commit einplanen.
- **AC-9-Bestandstest** (`test_sms_daywindow_aggregation.py`, „night_weather=None crasht nicht"): erwartet ggf. jetzt bewusst `?` statt `-` — Testanpassung, semantisch gewollt.
- **Kein neuer Fetch:** Beide Fixes arbeiten auf vorhandenen Daten — kein zusätzlicher open-meteo-Verbrauch (#1329).
