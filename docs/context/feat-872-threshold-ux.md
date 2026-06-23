# Context: feat-872-threshold-ux

## Request Summary
Issue #872 verbessert den Schwellwerte-Block in WeatherMetricsTab (Abschnitt 04) mit vier Änderungen:
Label-Fix, präzisierter Beschreibungstext, Preset-Auswahl statt Freitext und Gewitter als neue Schwellwert-Metrik (MED/HIGH).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-UI, Zeilen 515–582 (Schwellwerte-Block), Zeile 77 (`SMS_THRESHOLD_METRIC_IDS`) |
| `src/formatters/sms_trip.py` | `SMS_SYMBOL_BY_METRIC` (Zeile 44–49) — thunder muss als `"thunder": "TH:"` ergänzt werden |
| `src/output/tokens/builder.py` | `DEFAULTS["TH:"]: 1.0` (Zeile 54) + `is_level=True` für TH: — bereits korrekt |
| `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` | **Vorlage** für das neue Preset-Dropdown-Pattern (Dropdown + ℹ-Popover) |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | `PresetName`-Type und `METRIC_PRESETS` als strukturelles Vorbild |

## Existing Patterns

- **Alert-Preset-Selektor** (`AlertPresetSelector.svelte`): Dropdown (`entspannt/standard/sensibel`) + ℹ-Button öffnet Popover-Tabelle mit Schwellwerten. Genau dieses Muster soll für die SMS/Token-Schwellwerte übernommen werden, mit anderen Stufen-Namen: `Sensibel / Standard / Robust`.
- **sms_threshold-Persistenz**: `MetricConfig.sms_threshold: Optional[float]` in `src/app/models.py:507`. Loader schreibt/liest additiv (`src/app/loader.py:131–133`). Bei Preset → übersetzen in konkrete float-Werte pro Metrik und auf alle 4 (+ evtl. thunder) MetricConfig-Einträge schreiben.
- **Thunder-Threshold im Builder**: `DEFAULTS = {"TH:": 1.0}` (MED=1, HIGH=2) + `is_level=True` — der Builder verarbeitet integer-Level bereits korrekt als Threshold.

## Backend-Defaults (aus `builder.py DEFAULTS`)

| Metrik | Symbol | Default |
|--------|--------|---------|
| Niederschlag | R | 0.2 mm |
| Regenwahrsch. | PR | 20.0 % |
| Wind | W | 10.0 km/h |
| Böen | G | 20.0 km/h |
| Gewitter | TH: | 1.0 (= MED) |

## E-Mail-Defaults (aus `helpers.py` — anderer Pfad!)

`_DEFAULT_PRECIP_THR=0.5`, `_DEFAULT_WIND_THR=30.0`, `_DEFAULT_GUST_THR=50.0` — diese gelten NUR für den E-Mail-Ausblick/Trend-Block, nicht für SMS/Telegram-Token. Deshalb muss der Beschreibungstext präzisiert werden.

## Was genau geändert wird

### Problem 1: Label-Fix
- Zeile 515: `<Eyebrow>Schwellwerte</Eyebrow>` → `<Eyebrow>04 — Schwellwerte</Eyebrow>`

### Problem 2: Beschreibungstext
- Aktuell: „Gelten für E-Mail, Telegram und SMS" — zu breit
- Korrekt: Gelten für **SMS-Token**, **Telegram-Kurzform** und **E-Mail-Ausblick/Trend-Block**. Die E-Mail-Haupttabelle wird nicht beeinflusst.

### Problem 3: Preset statt Freitext
- 4 `<input type="number">` (Wind, Böen, Niederschlag, Regenwahrsch.) durch Preset-Dropdown ersetzen: `Sensibel / Standard / Robust`
- Beim Wechsel des Presets → konkrete float-Werte in `smsThresholds` State schreiben
- Preset-Werte (Vorschlag, wird in Spec festgelegt):

| Preset | Wind (km/h) | Böen (km/h) | Regen (mm) | Regenw. (%) |
|--------|------------|------------|-----------|------------|
| Sensibel | 8 | 15 | 0.1 | 15 |
| Standard | 10 | 20 | 0.2 | 20 |
| Robust | 15 | 30 | 0.5 | 30 |

### Problem 4: Gewitter als Metrik
- Frontend: `SMS_THRESHOLD_METRIC_IDS` um `'thunder'` ergänzen
- Frontend: statt number-input → 2-Option-Toggle „MED / HIGH" (values: 1.0 / 2.0)
- Backend `sms_trip.py`: `SMS_SYMBOL_BY_METRIC["thunder"] = "TH:"` ergänzen
- `MetricConfig.sms_threshold` trägt dann 1.0 (MED) oder 2.0 (HIGH) — builder.py verarbeitet bereits korrekt via `is_level=True`

## Dependencies

- Upstream: `MetricConfig.sms_threshold` → loader → builder DEFAULTS
- Downstream: SMS/Telegram-Token-Render, E-Mail-Ausblick-Block (helper.py `sms_threshold_*` keys)
- **Kein Breaking Change**: Bestehende `sms_threshold`-Werte bleiben erhalten; Preset-Wahl überschreibt nur explizit

## Analysis

### Betroffene Dateien (final)

| Datei | Typ | Beschreibung | LoC |
|-------|-----|-------------|-----|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | Label-Fix, Preset-UI statt 4 Freitext-Inputs, thunder in SMS_THRESHOLD_METRIC_IDS | ~70 |
| `src/formatters/sms_trip.py` | MODIFY | `SMS_SYMBOL_BY_METRIC["thunder"] = "TH:"` | 1 |
| `src/services/trip_report_scheduler.py` | MODIFY | `"sms_threshold_thunder": _sms_thr.get("thunder")` im Trend-Dict (Zeile ~1067) | 1 |
| `tests/tdd/test_issue_624_metric_thresholds.py` | MODIFY | Assert für thunder in SMS_SYMBOL_BY_METRIC | 2 |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | MODIFY | Assertions für neues Label + Preset-UI | 3–5 |

**Neues CREATE:** `frontend/src/lib/components/trip-detail/ThresholdPresetSelector.svelte` (~120 LoC) — nach AlertPresetSelector-Vorlage

### Scope
- Dateien: 6 (MODIFY) + 1 (CREATE)
- LoC: ~+120 / -60 = Netto +60
- Risiko: **LOW** — kein Schema-Rework, kein API-Change, reine UI + 2 Backend-Ergänzungen

### Technischer Ansatz
1. Neue Svelte-Komponente `ThresholdPresetSelector.svelte` (Dropdown Sensibel/Standard/Robust + ℹ-Popover) nach AlertPresetSelector-Muster
2. In WeatherMetricsTab: `smsThresholds`-State wird beim Preset-Wechsel mit konkreten float-Werten befüllt; bestehende Speicher-Logik bleibt unverändert
3. Thunder: 2-Toggle MED/HIGH statt Zahlen-Input, schreibt 1.0/2.0 in `smsThresholds["thunder"]`
4. Backend: 2 Einzeiler-Ergänzungen (sms_trip.py + trip_report_scheduler.py)

### Thunder-Pfad — bestätigt
- `SMS_SYMBOL_BY_METRIC["thunder"] = "TH:"` → preview_service.py filtert korrekt
- `"sms_threshold_thunder"` im Trend-Dict → Scheduler leitet Wert durch
- builder.py: bereits korrekt (`is_level=True`, DEFAULTS["TH:"]=1.0)

## Risks & Considerations

- **Preset-Persistenz**: Wie wird der aktuell gewählte Preset-Name gespeichert? Optionen: (a) nur implizit aus gespeicherten float-Werten ableiten, (b) neues Feld `sms_threshold_preset` in MetricConfig/UnifiedWeatherDisplayConfig. Option (a) ist einfacher und rückwärtskompatibel — beim Laden wird kein Preset angezeigt, wenn Werte von keinem Preset exakt matchen.
- **Thunder in `sms_threshold_rain_probability`-Pfad**: `rain_probability` wird in `trip_report_scheduler.py` nicht als `sms_threshold_*`-Key weitergegeben. Thunder läuft über `thresholds`-Dict in `sms_trip.py build_sms_report()`. Muss geprüft werden ob `thunder` durch denselben Pfad fließt.
- **Scope**: Rein Frontend-seitig für Label, Text, Preset-UI; Backend-Change minimal nur für `SMS_SYMBOL_BY_METRIC`-Ergänzung.
