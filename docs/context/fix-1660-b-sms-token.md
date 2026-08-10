# Context: fix-1660-b-sms-token (#1660 Teil B)

## Request Summary

14 der 25 wählbaren Metriken haben keinen SMS-Token und bleiben in der Kurzform
(SMS **und** Telegram-Kurzform, gleicher Pfad) wirkungslos, obwohl der Editor sie
pro Kanal anbietet. PO-Entscheidung (Issue-Kommentar 2026-08-09): **alle 14
verdrahten**, keine neue Editor-UI — die Pro-Kanal-Kaskade (#429/#434) existiert
und wird seit #1575 S3 gelesen.

Die 14 Metriken: humidity, dewpoint, wind_direction, cape, precip_type,
cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine, uv_index,
pressure, freezing_level.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/sms_trip.py` | `_SMS_SYMBOL_METRIC_IDS` (Ableitung aus Register) + `SMS_MULTI_SYMBOLS_BY_METRIC`; `_segments_to_normalized_forecast()` = Wertebeschaffung (Stunden-Samples je Metrik aus `build_day_window_points`) |
| `src/output/tokens/builder.py` | Grammatik: `PRIORITY`, `POSITIONAL`, `DEFAULTS`, `_mk_metric()`, `_wintersport()`. **Schichtgrenze: importiert nichts aus `src/app/`** — Kürzel dort als Literale |
| `src/output/tokens/render.py` | `DROP_ORDER` (Kürzungsreihenfolge bei >160 Zeichen), `_truncate()` |
| `src/output/tokens/dto.py` | `DailyForecast` braucht neue Felder (Stunden-Samples bzw. Tageswerte je neuer Metrik), `MetricSpec` unverändert |
| `src/output/tokens/metrics.py` | `render_threshold_peak_value()` (`{val}@{h}(…)`-Grammatik), `_fmt_num()` (symbolabhängige Formatierung) |
| `src/output/renderers/trip_report.py:282-365` | Verdrahtung: `sms_metric_ids` aus Kanal-Kaskade, `_sms_thr` (Schwellwerte #624), `_disabled_sms_specs` (Abwahl wirkt, #944/#1415) |
| `src/app/metric_catalog.py` | `sms_code` für ALLE 14 bereits vergeben: HU, DP, WD, CP, PT, CT, CL, CM, CH, VS, SU, UV, HP, NL — Teil B definiert also keine neuen Kürzel, nur Verdrahtung |
| `src/output/renderers/day_window.py` | `build_day_window_points()` — geteilte Tagesfenster-Punktliste (04:00–19:00), Quelle der Stunden-Samples |
| `src/app/models.py::ForecastDataPoint` | Stundenfelder: `humidity_pct`, `dewpoint_c`, `wind_direction_deg`, `cape_jkg`, `precip_type`, `cloud_total_pct`, `cloud_low/mid/high_pct`, `visibility_m`, `uv_index`, `pressure_msl_hpa`, `freezing_level_m`. **`sunshine` hat KEIN Stundenfeld** — wird aus DNI berechnet (`WeatherMetricsService.calculate_sunny_hours`) |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | Ratsche: Builder-/Renderer-Symbole müssen dem Register entsprechen (echter Import, keine Regex); neue Symbole werden automatisch mitgeprüft |
| `docs/reference/sms_format.md` | Format-Spec v2.x (§2 POSITIONAL, §5 Threshold+Peak, §6 Kürzungspriorität) — muss um die neuen Token erweitert werden |

## Existing Patterns

1. **Threshold-Peak-Token** (R/PR/W/G/TH): Stunden-Samples sammeln (nur Werte > 0),
   `_dedup_by_hour`, dann `render_threshold_peak_value()` → `HU85@14(92@17)`.
   Schwellwert aus `MetricConfig.sms_threshold` via `_sms_thr` (#624), sonst
   `DEFAULTS`, sonst None (= Peak ohne Filter).
2. **Wintersport-Token** (SD/NS24+/SL/AV/WC): EIN Tageswert (`render_int`), nur bei
   vorhandenen Daten, Schwellwert-Gate direkt in `_wintersport()`; SL ist INVERS
   (nur zeigen wenn `val <= threshold`, #873).
3. **Abwahl-Verdrahtung** (#944/#1415): jedes Symbol MUSS über
   `SMS_SYMBOL_BY_METRIC` (1:1, speist auch Schwellwerte) oder
   `SMS_MULTI_SYMBOLS_BY_METRIC` (1:n) erreichbar sein, sonst wirkt die Abwahl
   im Editor nicht → genau die Fehlerklasse #1450/#1482/#1415.
4. **Register-Ableitung** (#1435 E3b): `_SMS_SYMBOL_METRIC_IDS` listet nur
   metric_ids; Kürzel kommen aus `get_sms_code()`. Grammatik-Ausnahmen
   (`TH:`, `NS24+`) explizit in `_SMS_SYMBOL_GRAMMAR`.
5. **Gap-Regel** (#1328/#1483): `"-"` (Entwarnung) wird bei Datenlücke zu `"?"`.

## Dependencies

- **Upstream:** `build_day_window_points()` (Tagesfenster), `ForecastDataPoint`-Felder
  (Provider befüllen sie bereits — E-Mail-Stundentabelle zeigt alle 14),
  `metric_catalog.get_sms_code()`, Kanal-Kaskade `get_metrics_for_channel("sms", …)`.
- **Downstream:** `render.py` (Kürzung auf 160), Telegram-Kurzform (gleiche
  TokenLine), E-Mail-Subject-Filter (`filter_for_subject`), Goldens/Fixtures
  bestehender SMS-Tests (dürfen sich NICHT ändern, solange die neuen Metriken
  nicht gewählt sind — Default-Auswahl enthält sie nicht).

## Existing Specs

- `docs/reference/sms_format.md` — Format-SSoT (POSITIONAL, Priorität, §5-Grammatik)
- `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` — Register-Ableitung + Ratsche
- `docs/specs/modules/fix_1660a_temp_trennung.md` — Scheibe A (Vorbild-Mechanik)
- `docs/specs/modules/sms_daywindow_aggregation.md` — Tagesfenster-Aggregation
- `docs/specs/modules/fix_1613_sms_multi_symbols.md` — Mehrfach-Symbol-Tabelle

## Risks & Considerations

1. **160-Zeichen-Grenze:** 14 zusätzliche Token können die Zeile sprengen —
   Kürzungsreihenfolge (`PRIORITY`/`DROP_ORDER`/POSITIONAL) muss für alle neuen
   Symbole definiert sein (`PRIORITY[sym]` wird teils UNGESCHÜTZT gelesen,
   builder.py:301 — fehlender Eintrag = KeyError).
2. **Schichtgrenze `output/tokens/`:** darf `metric_catalog` nicht importieren —
   Kürzel als Literale, Ratsche prüft Übereinstimmung automatisch (neue Symbole
   in PRIORITY/POSITIONAL werden von der Ratsche erfasst; Soll = Register).
3. **Semantik je Metrik ist NICHT einheitlich:** „über"-Größen (HU/CP/UV/CT…)
   passen ins Threshold-Peak-Muster; VS/NL sind INVERS („unter", Muster SL);
   WD (Windrichtung, 0–360°) und PT (kategorial) brauchen eigene Wertegrammatik;
   SU hat keine Stundenreihe (DNI-Ableitung, Tageswert).
4. **Byte-Identität für Bestands-Trips:** Wer keine der 14 Metriken wählt, muss
   eine zeichengleiche SMS bekommen (Goldens bleiben grün).
5. **`DailyForecast` wächst um ~13 Felder** — additiv mit Default, sonst brechen
   Bestandsaufrufer (Muster #1410/#1475).
6. **LoC-Limit 250:** 14 Metriken × (DTO-Feld + Beschaffung + Builder + Tests)
   wird das Limit reißen — Override-Bedarf früh ansprechen (Vorbild Scheibe A:
   PO genehmigte 500).
7. **Prüfort = Wirkort:** Nachweis am Ende an der ZUGESTELLTEN Kurzform
   (Staging), nicht nur am Renderer-Unit-Test.
