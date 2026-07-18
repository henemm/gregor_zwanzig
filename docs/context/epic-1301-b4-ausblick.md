# Context: epic-1301-b4-ausblick

## Request Summary

B4 aus Epic #1301: **3-Tage-Ausblick je Ort im Ortsvergleich (neu).** Der bereits
existierende Trip-Ausblick-Renderer (`html.py:1116-1262`) und der Zeilenbau
(`trip_report_scheduler.py:1408-1488`) werden zu **geteilten Bausteinen extrahiert**;
Compare erzeugt seine Ausblick-Zeilen über denselben Weg. Compare-eigen bleiben nur
Tagesschleife + Platzierung. Konfiguration: schlichtes Bool (NICHT `multi_day_trend_reports`
kopieren). Leitplanke des Epics: **erweitern, nicht nachbauen.**

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py` | **Extraktionsquelle Renderer.** `render_html` (:764) enthält ab :1116 den `if multi_day_trend:`-Block, der `outlook_table` (thead :1179, Zeilen :1197-1253 über `format_trend_tokens`, Zell-BG-Helfer `_outlook_cell_bg` :1121, `_otd` :1138, `_acc_dot` :1153, Legende :1265) baut. → freie `render_outlook_table(multi_day_trend, ...)`. |
| `src/services/trip_report_scheduler.py` | **Extraktionsquelle Zeilenbau.** `_build_stage_trend` (:1361) aggregiert je Stage über `aggregate_stage(seg_weather)` (:1408) und baut ab :1460 das Trend-Row-Dict (weekday/temp_lo/temp_hi/precip_mm/wind_kmh/thunder/hourly_*/confidence_pct/rain_probability_pct). Aufruf :838, `show_multi_day_trend` steuert. |
| `src/services/weather_metrics.py` | **Geteilte Naht.** `aggregate_stage` (:1023) und `summarize_points` (:985) liefern **beide** `SegmentWeatherSummary` — feldkompatibel zum Zeilenbau (`.temp_min_c/.temp_max_c/.precip_sum_mm/.wind_max_kmh/.wind_direction_avg_deg/.thunder_level_max/.confidence_pct_min/.pop_max_pct`). `summarize_points` ist der KANONISCHE Compare-Aggregator (Regen SUM, Gewitter MAX-Ordinal, Sicht MIN — identisch zum Trip, AC-15/#1285). |
| `src/output/renderers/email/compare_html.py` | **Ziel der Platzierung.** `render_compare_html` (:881) iteriert `sort_locations_alphabetically(result.locations)`. `_daily_summary` (:354) nutzt bereits `summarize_points(loc.hourly_data)`. Renderer-Commit-Gate #811 greift auf diese Datei. |
| `src/app/user.py` | `LocationResult` (:117): pro Ort `hourly_data: List[ForecastDataPoint]` (:152, flache Punktliste über den Horizont) + #1285-Tages-Aggregate. Kein Segment-Modell wie Trip. |
| `src/services/report_config_resolver.py` | `resolve_compare_render_options` (:166) liest EXAKT top_n/enabled_metrics/hourly_metrics/hourly_enabled/corridors — kein Ausblick-Key. `CompareRenderOptions` (:150) ist der Ort für das neue Bool. |
| `src/output/renderers/comparison.py` | Klartext-Compare-Renderer; iteriert `hourly_data` (:171). Offene Frage: bekommt Klartext auch einen Ausblick? |
| `src/services/scheduler_dispatch_service.py` | Ruft `render_compare_html(...)` im Versandpfad; hier fließt das neue Bool als Kwarg ein (Preview-Pfad: `compare_preview_service.py`). |

## Existing Patterns

- **Ein Aggregat-Typ, zwei Wege:** Trip = `aggregate_stage(list[SegmentWeatherData])`, Compare = `summarize_points(list[ForecastDataPoint])`, beide → `SegmentWeatherSummary`. Der extrahierte Zeilenbau nimmt eine `SegmentWeatherSummary` entgegen → beide Pfade speisen ihn.
- **Tages-Gruppierung im Compare existiert im Kleinen:** `_daily_summary` aggregiert `hourly_data` bereits über `summarize_points` — für B4 nach Kalendertag gruppieren (max. 3 Tage) und je Tag `summarize_points(day_points)`.
- **format_trend_tokens** (`helpers.py:759`) ist die „single source of truth" der Trend-Semantik je Kanal — der extrahierte Renderer nutzt sie unverändert.
- **fail-soft ACC-Dot:** `_acc_dot(None)` → „–". Compare-`hourly_data` trägt evtl. kein Ensemble-Confidence → Spalte zeigt „–" ohne Fehler.
- **Additiver Config-Kwarg mit Default:** `render_compare_html` erweitert um `outlook_enabled: bool = False` (rückwärtskompatibel, wie `hourly_enabled` :889).

## Dependencies

- **Upstream (was B4 nutzt):** `summarize_points`/`aggregate_stage` (`weather_metrics.py`), `format_trend_tokens` (`helpers.py`), `LocationResult.hourly_data`, `WEEKDAYS_DE`, FONT_DATA/Design-Tokens im html.py-Modul.
- **Downstream (was den geänderten Renderer nutzt):** Trip-Versand (`render_html`) — MUSS zeichengleich bleiben; Compare-Versand (`render_compare_html` via `scheduler_dispatch_service`) + Compare-Preview (`compare_preview_service`).

## Existing Specs

- `docs/specs/modules/multi_day_trend.md` (v4.0) — Trip-Ausblick, referenziert in `_build_stage_trend`.
- `docs/specs/modules/model_metric_fallback.md` — WEATHER-05b (A1, bereits live; relevant, weil Alpen-Orte jetzt volle Metriken liefern).
- Epic-Plan: `~/.claude/plans/warum-verweist-du-immer-crispy-ladybug.md`.

## Risks & Considerations

1. **Trip-Regression (hart):** Extraktion aus `html.py:1116-1262` muss die Trip-Ausblick-Tabelle **zeichengleich** lassen — Regressionsschutz Pflicht (Golden-String/Render-Vergleich).
2. **Renderer-Commit-Gate #811:** `compare_html.py`/`comparison.py`-Edits blocken Commit bis `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf. Fachlicher Mail-Nachweis zusätzlich über `email_spec_validator.py` (`X-GZ-Mail-Type: compare`, Exit 0).
3. **LoC > 250 erwartet** (Epic nennt B4 als Grenzen-Reißer) → Override-Freigabe beim PO einholen, nicht eigenmächtig.
4. **Horizont:** A4 hat Compare auf 96h gesetzt — 3-Tage-Ausblick (≥72h) passt. Alpen-Orte liefern seit A2/A3 volle Metriken inkl. Schnee-Herkunft.
5. **Confidence/ACC-Spalte:** `confidence_pct` ist per #710 KEINE per-Ort-Metrik. Compare-`hourly_data` trägt vermutlich kein `confidence_pct_min` → ACC zeigt „–". Analyse-Entscheidung: ACC-Spalte im Compare-Ausblick behalten (fail-soft „–") oder weglassen.
6. **Klartext-Pfad:** `comparison.py` — ob der Ausblick auch im Plain-Text erscheint, ist offene Analyse-Frage (Trip hat Plain-Ausblick via `plain.py`).
7. **Trip/Compare-Teilung (Invariante):** Eine Compare-eigene Renderer-Kopie wäre ein Verstoß — der geteilte `render_outlook_table` ist Pflicht, Compare-eigen nur Tagesschleife + Platzierung.

## Analysis

### Type
Feature (mit einer Engine-Datenlücke als Vorbedingung).

### Kritischer Befund (Plan-Gegenprüfung, verifiziert)
**`LocationResult.hourly_data` trägt nur EINEN Tag.** `comparison_engine.py:97-101` filtert `raw_data` auf `dp.ts.date() == target_date` (+ Fenster) und setzt genau diesen Slice als `hourly_data` (`:249`). Die vollen 96h werden gefetcht (`:91 raw_data`), aber verworfen. „Nach Tag gruppieren" ergäbe eine Gruppe → **B4 braucht zuerst eine Engine-Retention** eines Mehrtages-Slice.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/services/comparison_engine.py` | MODIFY | **Schritt 0.** Additiver Mehrtages-Slice aus `raw_data` (VOR Fenster-Filter) auf neuem `LocationResult`-Feld; durchreichen an Live-Pfad (:249) + `dict_to_comparison_result` (:303). Kein Extra-Fetch. |
| `src/app/user.py` | MODIFY | `LocationResult`: additives Feld `outlook_hourly_data: List[ForecastDataPoint] = []` (transient, keine Persistenz → kein Datenschema-Risiko). |
| `src/output/renderers/email/html.py` | MODIFY | Block :1116-1271 → freie `render_outlook_table(rows, *, show_acc=True)`. `render_html` ruft mit `show_acc=True` (zeichengleich). |
| `src/services/trip_report_scheduler.py` | MODIFY | Row-Bau :1460-1488 → freie `build_outlook_row(summary, points, weekday, tz, ...)`; Hourly-Samples intern aus flacher Punktliste. `_build_stage_trend` biegt darauf um (reine Funktion, kein I/O — Call-Counter-Test grün halten). |
| `src/output/renderers/email/compare_html.py` | MODIFY | Compare-eigen: Slice je Ort nach Kalendertag gruppieren (Cap 3), `summarize_points`/Tag → `build_outlook_row(tz=loc.timezone)` → `render_outlook_table(show_acc=False)`; Platzierung je Ort. Neuer Kwarg `outlook_enabled=False`. |
| `src/services/report_config_resolver.py` | MODIFY | `outlook_enabled` in `CompareRenderOptions` + `resolve_compare_render_options` (Top-Level-Preset-Feld). |
| `src/services/scheduler_dispatch_service.py`, `src/services/compare_preview_service.py` | MODIFY | Kwarg durchreichen (Versand + Preview synchron — Divergenz = Fehlerklasse #1297). |
| geteiltes Renderer-Modul | CREATE/MOVE | `render_outlook_table`/`build_outlook_row` in geteilte Lage (nicht Compare-eigen). |
| Tests | CREATE | Trip-Regression (zeichengleich), Compare-3-Tage-Neubau, Engine-Slice-Retention. |

### Scope Assessment
- Dateien: ~8 Produktiv + Tests
- Geschätzte LoC: **~120–165 produktiv**, mit Tests **realistisch 300+** → **250-Limit wird gerissen, Override-Freigabe nötig**.
- Risiko: **MEDIUM-HIGH** (Trip-Zeichengleichheit + Engine-Datenpfad + Mail-Gate #811).

### Technical Approach (empfohlene Reihenfolge)
0. **Engine:** Mehrtages-Slice auf `LocationResult` retten (+ `dict_to_comparison_result`). Ohne dies keine Daten.
1. `render_outlook_table` extrahieren, `show_acc`-Branch nur im False-Zweig (Default byte-identisch). Golden-Substring-Tests grün halten (`test_issue_898_901`, `_888_896_902`, `_721`).
2. `build_outlook_row` aus Scheduler extrahieren, Hourly intern aus Punkten+tz. `_build_stage_trend` umbiegen.
3. Compare-Tagesschleife: Slice gruppieren (Cap 3 in 96h), `summarize_points`/Tag → `build_outlook_row(tz=loc-tz)` → `render_outlook_table(show_acc=False)`.
4. Config `outlook_enabled` end-to-end.

### Entschieden (durch Evidenz, keine PO-Frage)
- **ACC-Spalte im Compare entfällt** (`show_acc=False`): `summarize_points` setzt kein `confidence_pct_min`; #710 verbietet Confidence als Ort-Spalte. Zwingend, nicht kosmetisch.
- **Hourly-Samples werden NICHT auf `summary.gust_max_kmh` umgestellt** — Trip-Tabelle liest `hourly_gust`-Max; `build_outlook_row` emittiert weiter `hourly_gust` (sonst Trip-Zeichengleichheit gefährdet).

### PO-Entscheidungen (2026-07-18)
- [x] **Ausblick-Default: AN.** Erscheint sofort in jeder Vergleichs-Mail nach Auslieferung; `outlook_enabled` Default `True` bei fehlendem Preset-Key. C schaltet später ab-/anwählbar.
- [x] **Beide Fassungen: HTML + Klartext.** Erweitert Scope: Trip-Plain-Ausblick (`plain.py:242`) wird ebenfalls geteilter Baustein (`render_outlook_plain`); Compare-Plain (`comparison.py`) nutzt ihn mit `show_acc=False`. → +LoC, Override nötig.
