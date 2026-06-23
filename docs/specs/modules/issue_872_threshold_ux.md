---
entity_id: issue_872_threshold_ux
type: feature
created: 2026-06-23
updated: 2026-06-23
status: draft
workflow: feat-872-threshold-ux
---

# UX: Schwellwerte-Block — Label-Fix + Presets statt Freitext + Gewitter (MED/HIGH)

## Approval

- [ ] Approved

## Purpose

Verbessert den Schwellwerte-Abschnitt im Inhalt-Reiter (WeatherMetricsTab) in vier Teilschritten: korrektes Abschnitts-Label, korrigierter Beschreibungstext, Ablösung der vier Freitext-Inputs durch ein Preset-Dropdown (Sensibel / Standard / Robust), und Erweiterung um Gewitter als fünfte threshold-fähige Metrik mit einem MED/HIGH-Toggle.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** Schwellwerte-Card (Zeile 513–582)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` | component | Vorlage für Dropdown + ℹ-Popover-Muster |
| `src/output/tokens/builder.py` | module | Bereits korrekt (is_level=True, DEFAULTS["TH:"]=1.0) — kein Change nötig |
| `src/formatters/sms_trip.py` | module | SMS_SYMBOL_BY_METRIC muss "thunder" -> "TH:" erhalten |
| `src/services/trip_report_scheduler.py` | module | Trend-Dict muss sms_threshold_thunder aufnehmen |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | test | Bestehende E2E-Assertions für Schwellwerte-Abschnitt |
| `tests/tdd/test_issue_624_metric_thresholds.py` | test | Bestehende Backend-Tests für SMS_SYMBOL_BY_METRIC |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | Label-Fix Z.515, Beschreibungstext Z.516, SMS_THRESHOLD_METRIC_IDS Z.77 um 'thunder' erweitern, 4 Freitext-Inputs durch `<ThresholdPresetSelector>` + Gewitter-Toggle ersetzen |
| `frontend/src/lib/components/trip-detail/ThresholdPresetSelector.svelte` | CREATE | Neue Komponente nach AlertPresetSelector-Muster: Dropdown (Sensibel/Standard/Robust) + ℹ-Popover mit Wertetabelle |
| `src/formatters/sms_trip.py` | MODIFY | `SMS_SYMBOL_BY_METRIC["thunder"] = "TH:"` hinzufügen |
| `src/services/trip_report_scheduler.py` | MODIFY | `"sms_threshold_thunder": _sms_thr.get("thunder")` im Trend-Dict ergänzen (~Z.1067) |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | MODIFY | Assertions für neues Label + Preset-Dropdown statt Freitext-Inputs |
| `tests/tdd/test_issue_624_metric_thresholds.py` | MODIFY | Assert für "thunder" in SMS_SYMBOL_BY_METRIC ergänzen |

### Estimated Changes

- Files: 6
- LoC: +197/-62 (netto ~135; ThresholdPresetSelector ~120 neu, WeatherMetricsTab ~62 raus/~10 rein, Backend je 1, Tests je ~2–5)

## Implementation Details

### Teiländerung 1 — Label-Fix (WeatherMetricsTab.svelte Z.515)

```
Vorher: <Eyebrow style="margin-bottom:8px">Schwellwerte</Eyebrow>
Nachher: <Eyebrow style="margin-bottom:8px">04 — Schwellwerte</Eyebrow>
```

Alle anderen Abschnitte tragen bereits Nummern (01 Metriken, 02 Inhaltsformat, 03 Telegram). Dieser fehlte.

### Teiländerung 2 — Beschreibungstext (WeatherMetricsTab.svelte Z.516)

```
Vorher: "Gelten für E-Mail, Telegram und SMS"
Nachher: "Gelten für SMS-Token, Telegram-Kurzform und E-Mail-Ausblick/Trend-Block"
```

Die Haupt-E-Mail-Tabelle wird von den Schwellwerten NICHT beeinflusst. Der alte Text war irreführend.

### Teiländerung 3 — ThresholdPresetSelector.svelte (neue Komponente)

Struktur analog zu `AlertPresetSelector.svelte`:
- Dropdown mit drei Optionen: Sensibel / Standard / Robust
- ℹ-Button öffnet Popover mit Wertetabelle (5 Metriken × 3 Presets)
- Bei Preset-Wahl: schreibt konkrete float-Werte via `onchange`-Callback in `smsThresholds`-State des Parent
- Preset-Werte (PO-bestätigt):

| Stufe    | Wind    | Böen    | Regen   | Regenw. | Gewitter |
|----------|---------|---------|---------|---------|---------|
| Sensibel | 15 km/h | 30 km/h | 0,3 mm  | 25 %    | MED (1.0) |
| Standard | 20 km/h | 40 km/h | 0,8 mm  | 40 %    | MED (1.0) |
| Robust   | 30 km/h | 50 km/h | 1,5 mm  | 60 %    | HIGH (2.0) |

Der Parent (WeatherMetricsTab) ersetzt die bisherigen 4 Freitext-Inputs (Z.521–580) durch `<ThresholdPresetSelector bind:value={selectedPreset} onchange={applyPreset} />`. Die bestehende Speicher-Logik (sms_threshold in MetricConfig, PATCH /api/trips/{id}) bleibt unverändert.

### Teiländerung 4 — Gewitter als neue threshold-fähige Metrik

**Frontend:**
- `SMS_THRESHOLD_METRIC_IDS` (Z.77) um `'thunder'` erweitern
- Unterhalb des Preset-Dropdowns: 2-Option-Toggle "MED / HIGH" (schreibt 1.0 / 2.0 in `smsThresholds["thunder"]`)
- data-testid: `sms-threshold-thunder-med` und `sms-threshold-thunder-high`

**Backend sms_trip.py:**
```python
SMS_SYMBOL_BY_METRIC: dict[str, str] = {
    "precipitation": "R",
    "rain_probability": "PR",
    "wind": "W",
    "gust": "G",
    "thunder": "TH:",   # NEU
}
```

**Backend trip_report_scheduler.py (~Z.1064–1069):**
```python
"sms_threshold_precip": _sms_thr.get("precipitation"),
"sms_threshold_wind": _sms_thr.get("wind"),
"sms_threshold_gust": _sms_thr.get("gust"),
"sms_threshold_thunder": _sms_thr.get("thunder"),   # NEU
```

`builder.py` ist bereits korrekt (is_level=True, DEFAULTS["TH:"]=1.0) — keine Änderung nötig.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer öffnet den Inhalt-Reiter eines Trips / When er den Schwellwerte-Block betrachtet / Then lautet die Eyebrow-Überschrift genau "04 — Schwellwerte" und der Hinweistext enthält "SMS-Token" und "Telegram-Kurzform" aber nicht "E-Mail, Telegram und SMS"
  - Test: Playwright gegen Staging; `page.locator('[data-testid="sms-thresholds"]').textContent()` prüfen; kein Mock

- **AC-2:** Given der Schwellwerte-Block ist sichtbar / When der Nutzer das Preset-Dropdown öffnet / Then sieht er genau drei Optionen (Sensibel, Standard, Robust) und kein Freitext-Eingabefeld für Wind, Böen, Niederschlag oder Regenwahrscheinlichkeit mehr
  - Test: Playwright gegen Staging; `page.locator('select[data-testid="threshold-preset-select"]')` hat 3 Optionen; kein `input[data-testid="sms-threshold-wind"]` mehr auffindbar

- **AC-3:** Given der Nutzer wählt Preset "Sensibel" / When er speichert und der Trip neu geladen wird / Then enthält der gespeicherte display_config Werte wind=15, gust=30, precipitation=0.3, rain_probability=25 in den jeweiligen MetricConfig.sms_threshold-Feldern
  - Test: Playwright wählt Preset, klickt Speichern, dann `GET /api/trips/{id}` und assert auf display_config-Felder; echter HTTP-Call, kein Mock

- **AC-4:** Given ein Trip mit aktiviertem SMS-Kanal hat Gewitter-Schwellwert "HIGH" gesetzt / When der Scheduler einen SMS-Trend-Block aufbaut / Then enthält der Trend-Dict den Schlüssel `sms_threshold_thunder` mit Wert 2.0
  - Test: Echter Scheduler-Run auf Staging mit Test-Trip; IMAP-Prüfung oder direkter API-Call auf `/api/trips/{id}` nach Scheduler-Lauf; kein Mock

- **AC-5:** Given der Nutzer klickt den ℹ-Button neben dem Preset-Dropdown / When das Popover erscheint / Then zeigt es eine Tabelle mit allen fünf Metriken (Wind, Böen, Niederschlag, Regenwahrsch., Gewitter) und den drei Preset-Spalten mit den PO-bestätigten Werten
  - Test: Playwright gegen Staging; `page.locator('[data-testid="threshold-preset-popover"]')` ist sichtbar und enthält "15 km/h" (Sensibel/Wind) und "MED" (Sensibel/Gewitter); kein Mock

- **AC-6:** Given `SMS_SYMBOL_BY_METRIC` in `src/formatters/sms_trip.py` / When pytest `test_issue_624_metric_thresholds.py` läuft / Then ist der Schlüssel "thunder" mit Wert "TH:" im Dict vorhanden
  - Test: Echter Import ohne Mock; pytest-Lauf muss grün sein

## Known Limitations

- Das Preset-Dropdown speichert keine "Preset-Bezeichnung" im Backend — es schreibt nur die konkreten float-Werte in die bestehenden MetricConfig.sms_threshold-Felder. Beim erneuten Öffnen kann daher kein Preset vorausgewählt werden (kein Reverse-Mapping).
- Der Gewitter-Toggle (MED/HIGH) ist unabhängig vom Preset-Dropdown — ein nachträgliches Umschalten des Toggles überschreibt den vom Preset gesetzten thunder-Wert.

## Changelog

- 2026-06-23: Initial spec created
