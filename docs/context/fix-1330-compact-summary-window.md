# Context: fix-1330-compact-summary-window

## Request Summary

Issue #1330 (priority:critical): In der Trip-Briefing-E-Mail widerspricht die Natursprache-
Kopfzeile ("Kurzzusammenfassung", `compact_summary.py`) der darunterstehenden Stundentabelle
UND der SMS für dieselbe Etappe — Regen wird als "trocken" beschrieben, obwohl 17.6 mm Regen ab
15:00 vorliegen (SMS: `R16.6@16`), und Böen werden mit "29 km/h" beschrieben, obwohl die echte
Spitze 65 km/h beträgt (SMS: `G22@4(65@16)`, Metriken-Pille: "Böen ... max 65 (16:00)").

## Root Cause (im Code verifiziert, `src/output/renderers/compact_summary.py`)

Beide betroffenen Formatter-Funktionen lesen den Wert aus dem **Segment-only-Aggregat**
(`summary`, gebaut aus `_aggregate(segments)`, Zeile 136-142 → `aggregate_stage()` in
`src/services/weather_metrics.py:1041`), das **kein** `night_weather` (Wetter am Ziel nach
Ankunft) enthält:

- `_format_precipitation()` (Zeile 200-232): Zeile 208-210 gated auf `summary.precip_sum_mm`
  — Regen, der ausschließlich nach Ankunft am Ziel fällt, ergibt `precip_sum_mm` nahe 0 →
  Rückgabe `"trocken"`, **bevor** die (korrekt tagesfenster-basierte) `hourly`-Liste überhaupt
  konsultiert wird. `hourly` (aus `_collect_hourly_data()` → `build_day_window_points()`,
  `day_window.py`) wird nur für die *Musterdetails* (peak/starts_later/…) genutzt, nie für das
  Ja/Nein "gibt es Regen".
- `_format_wind()` (Zeile 312-353): Zeile 321-322 liest `wind_max = summary.wind_max_kmh` /
  `gust_max = summary.gust_max_kmh` — dasselbe unvollständige Aggregat. Die **Uhrzeit** des
  Böen-Peaks kommt korrekt aus `_find_wind_peak(hourly)` (Zeile 348, tagesfenster-basiert) —
  daher stimmt "ab 16:00", aber der **Wert** "29 km/h" ist der veraltete Segment-Peak, nicht der
  tatsächliche Tagesfenster-Peak (65 km/h).

`_format_thunder()` (Zeile 373ff.) macht es bereits richtig: liest ausschließlich aus `hourly`,
kein Aggregat als Torwächter — das ist der Fix aus #1294 (ADR-0025 Changelog 2026-07-17), der nur
für Gewitter, nicht für Regen/Wind, migriert wurde.

## Bezug zu bestehender Architektur-Vorgabe (wichtig für Spec/Implementierung)

`docs/specs/modules/sms_daywindow_aggregation.md` (Epic #1319, Scheibe A, **bereits approved
und in Produktion**, Fix-Commit `087f643f`) listet **AC-3 ("Begleitwerte … Regen/
Regenwahrscheinlichkeit/Böen … Kurzzusammenfassung … müssen dieselbe Stunde zeigen")** explizit
als Akzeptanzkriterium. Der zugehörige Test
`tests/tdd/test_sms_daywindow_aggregation.py::TestAC3CompanionValuesAtSameHour` deckt das aber
**nicht vollständig ab**:

- `test_compact_summary_names_rain_start_hour` übergibt `agg_precip_sum_mm=0.5` **explizit** an
  die Segment-Fixture (`_segment()`) — dadurch ist `summary.precip_sum_mm` zufällig bereits
  ungleich Null, der defekte Gate-Pfad in `_format_precipitation` wird nie geprüft (nur, dass
  `_find_rain_pattern` die 14:00-Stunde findet, wenn das Gate schon offen ist).
- Kein Test in `TestAC3CompanionValuesAtSameHour` prüft die **Böen-Formulierung der
  Kurzzusammenfassung** (`"Böen bis … km/h"`) überhaupt — nur die Pille
  (`test_pills_show_rain_pr_gust_at_same_hour`). Zusätzlich ist im Fixture-Default `_segment()`
  `gust_max_kmh=25.0` hartkodiert und deckt sich zufällig mit dem in den AC-3-Tests verwendeten
  Nacht-Böen-Wert `gust=25.0` — selbst ein Test auf den Kurzzusammenfassungs-Wortlaut hätte den
  Bug mit diesen Fixture-Defaults nicht aufgedeckt.

→ #1330 ist damit keine Regression eines vorher korrekten Verhaltens, sondern eine **unvollständig
umgesetzte, bereits freigegebene AC (AC-3)** — die Spec selbst bleibt gültig, es fehlt die
Implementierung für zwei der drei betroffenen compact_summary-Funktionen plus die Testabdeckung,
die das aufgedeckt hätte.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/compact_summary.py` | `_format_precipitation` (Z. 200-232) und `_format_wind` (Z. 312-353) müssen wie `_format_thunder` auf die `hourly`-Liste (Tagesfenster) statt `summary` (Segment-Aggregat) umgestellt werden |
| `src/output/renderers/day_window.py` | Liefert bereits alle nötigen Felder pro Stunde (`precip_1h_mm`, `gust_kmh`, `wind10m_kmh`, `thunder_level`) — kein neuer Fetch nötig |
| `src/services/weather_metrics.py` | `aggregate_stage()` (Z. 1041) — Quelle von `summary`, bewusst Segment-only, bleibt unverändert (wird für Temperatur/Wolken weiter gebraucht) |
| `src/app/models.py` | `SegmentWeatherSummary` (Z. 339) — Datentyp von `summary` |
| `docs/specs/modules/sms_daywindow_aggregation.md` | AC-3 bereits approved, aber für compact_summary Regen/Wind nicht vollständig erfüllt |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | Architekturprinzip: eine Rohdatenquelle, ein Fenster, kein Aggregat als Torwächter — Changelog-Eintrag 2026-07-17 ist die direkte Vorlage für diesen Fix (dort für Gewitter gelöst) |
| `tests/tdd/test_sms_daywindow_aggregation.py` | AC-3-Testklasse `TestAC3CompanionValuesAtSameHour` — Fixture-Blindstelle (s.o.), Vorlage für neue RED-Tests mit `agg_precip_sum_mm=0.0` |
| `tests/tdd/test_compact_summary_arrival_hour.py` | #1220 AC-11 — anderer Bug (exklusive Fensterung am Etappenende), bereits behoben, **nicht** zu verwechseln mit #1330 |
| `tests/integration/test_compact_summary.py` | Bestandstests für `CompactSummaryFormatter` — müssen grün bleiben |

## Existing Patterns

- **ADR-0025-Fix-Muster (aus #1294):** Torwächter-Entscheidung ("gibt es X?") und Werte-Ausgabe
  müssen aus derselben, tagesfenster-basierten `hourly`-Liste kommen wie die Detailtabelle —
  niemals aus einem separaten Aggregat, das andere Daten (hier: `night_weather`) nicht kennt.
  `_format_thunder()` in derselben Datei ist die direkte Vorlage.
- Trip/Compare-Teilung ist hier nicht betroffen — `format_weather_summary()` ist bereits der
  geteilte, kontextneutrale Kern (`context="route"|"vergleich"`, Issue #1278); der Fix wirkt
  automatisch für beide Kontexte.

## Dependencies

- Upstream: `build_day_window_points()` (`day_window.py`) — bereits vollständig implementiert,
  liefert alle benötigten Felder.
- Downstream: `TripReportFormatter._generate_compact_summary()` (`trip_report.py`) ruft
  `format_stage_summary()` auf; wirkt in E-Mail-Kurzzusammenfassung (HTML/Plain/Compact) und im
  Orts-Vergleich (geteilter Kern).

## Existing Specs

- `docs/specs/modules/sms_daywindow_aggregation.md` — AC-3 einschlägig, wird durch diesen Fix
  vervollständigt (kein neuer Architektur-Entscheid nötig, ADR-0025 bleibt unverändert gültig).

## Risks & Considerations

- **Renderer-Mail-Gate #811 (CLAUDE.md, hart, un-überspringbar):** `compact_summary.py` ist eine
  der geschützten Dateien — Commit erfordert `tests/tdd/test_issue_811_mode_matrix.py` grün UND
  erfolgreichen `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Testmail,
  **vor** dem Commit.
- **Scope-Abgrenzung:** `_format_temperature`/`_format_clouds` bleiben unverändert (nutzen
  weiterhin `summary` — laut Spec `sms_daywindow_aggregation.md` "Known Limitations" bewusst so,
  N/D-Temperatur ist Scheibe D, nicht Teil dieser Spec/dieses Fixes).
- **Ungeklärter Nebenpunkt aus dem Screenshot:** Der abgeschnittene Text "⚡ möglich 15:00–…"
  könnte einen Tages- und einen Nacht-Gewitterzeitpunkt (00:00, separates Ereignis) zu einer
  einzigen Zeitspanne verschmelzen. `_format_thunder` selbst gilt als korrekt (ADR-0025-konform);
  falls sich das in der Analyse als eigenständiges Problem bestätigt, ist zu entscheiden, ob es
  in diesen Fix gehört oder ein Sammel-Eintrag (#1199) wird — noch nicht verifiziert, da der
  Screenshot-Text an dieser Stelle abgeschnitten ist.
- **Test-Fixture-Blindstelle beheben:** Die neuen RED-Tests müssen `agg_precip_sum_mm=0.0` (nicht
  `None`/`0.5`) und einen von `summary.gust_max_kmh` **abweichenden** Nacht-Böenwert verwenden,
  sonst wiederholt sich exakt die Lücke, die #1330 erst ermöglicht hat.
- **LoC-Budget:** Fix ist klein (2 Funktionen in 1 Datei + Tests), sollte deutlich unter dem
  250-LoC-Workflow-Limit bleiben.
- Nebenbefund #1220 (offen): Fix bereits in Produktion (Commit `087f643f` ist Vorfahre des
  aktuell deployten `71d53468`), könnte separat geschlossen werden — nicht Teil dieses Workflows.

## Analysis

### Type
Bug. Root Cause bereits code-verifiziert in der Kontext-Phase (kein separater Bug-Intake-Agent
nötig — die Recherche liegt vollständig und mit Zeilenverweisen vor).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compact_summary.py` | MODIFY | `_format_precipitation`: Gate von `summary.precip_sum_mm` auf eine aus `hourly` berechnete Tagesfenster-Regensumme umstellen. `_format_wind`: `wind_max`/`gust_max` aus `hourly` (Tagesfenster-Maximum von `wind10m_kmh`/`gust_kmh`) statt aus `summary` lesen. Muster: `_find_wind_peak`/`_find_rain_pattern` (bereits vorhanden, lesen schon `hourly`). `_format_temperature`/`_format_clouds` bleiben unverändert (Scheibe D, out of scope). |
| `tests/tdd/test_sms_daywindow_aggregation.py` | MODIFY | `TestAC3CompanionValuesAtSameHour` um Fälle ergänzen, die die bisherige Fixture-Blindstelle schließen: `agg_precip_sum_mm=0.0` (statt `0.5`) bei Regen ausschließlich in `night_weather`; Nacht-Böenwert, der vom hartkodierten `summary.gust_max_kmh=25.0` **abweicht** (z. B. 40 km/h), plus eine Assertion auf den Kurzzusammenfassungs-Böen-Wortlaut (bisher gar nicht geprüft). |
| `tests/integration/test_compact_summary.py` | — (nur Regressionscheck) | Bestehende Tests müssen grün bleiben (keine Änderung erwartet, da sie ohne `night_weather` aufrufen und der Fix in diesem Fall bit-identisch bleibt). |

### Scope Assessment
- Files: 2 geändert (1 Produktivdatei, 1 Testdatei)
- Estimated LoC: ~ +25/-10 Produktivcode, ~ +40 Testcode — deutlich unter dem 250-LoC-Limit
- Risk Level: MEDIUM (sicherheitsrelevanter, gate-geschützter Pfad — CLAUDE.md
  Renderer-Mail-Gate #811 —, aber technisch enger, präzedenzbasierter Fix)

### Technical Approach

1. In `_format_precipitation`: den Ja/Nein- und Mengen-Gate auf eine aus `hourly` berechnete
   Summe (`sum(dp.precip_1h_mm or 0.0 for dp in hourly)`) umstellen — analog zur bereits
   vorhandenen Logik in `email/helpers.py::build_metrics_summary_pills` (`metric_id ==
   "precipitation"`, Zeile 1320-1338), aber **ohne** die beiden Renderer auf eine gemeinsame
   Helferfunktion zu heben (ADR-0025 "Verworfene Alternativen" lehnt diesen Umbau explizit ab —
   berührt gate-geschützten Code ohne belegbaren Zusatznutzen). `_find_rain_pattern` (nutzt
   bereits `hourly`) bleibt für die Musterdetails unverändert.
2. In `_format_wind`: `wind_max`/`gust_max` als `max(dp.wind10m_kmh/gust_kmh or 0.0 for dp in
   hourly)` statt aus `summary` — `_find_wind_peak` bleibt für die Peak-Stunde unverändert
   (liefert bereits denselben Wert, aktuell ungenutzt für die Magnitude).
3. Kein Eingriff in `day_window.py`, `weather_metrics.py` oder `_format_thunder` nötig — alle
   Bausteine existieren bereits.
4. Tests: zwei neue Fälle in `TestAC3CompanionValuesAtSameHour` (s.o.), die exakt die Lücke
   abdecken, die #1330 in Produktion sichtbar gemacht hat — RED vor dem Fix, GRÜN danach, nach
   Projekt-Testpolitik keine Mocks, echter `TripReportFormatter.format_email()`-Aufruf.

### Dependencies
Keine neuen — `hourly`/`build_day_window_points()` liefert bereits alle benötigten Felder
(s. Context oben).

### Open Questions
Keine blockierenden. Eine bewusste Abgrenzung: Der im Screenshot sichtbare, abgeschnittene
Gewitter-Zeitraumtext wird nicht Teil dieses Fixes, bis unabhängig verifiziert (s. Risks oben).
