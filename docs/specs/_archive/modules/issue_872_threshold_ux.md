---
entity_id: issue_872_threshold_ux
type: feature
created: 2026-06-23
updated: 2026-06-23
status: draft
workflow: feat-872-threshold-ux
---

# UX: Schwellwerte-Block — Label-Fix + Pro-Metrik-Stufen + Gewitter (MED/HIGH)

## Approval

- [ ] Approved

## Purpose

Verbessert den Schwellwerte-Abschnitt im Inhalt-Reiter (WeatherMetricsTab) in vier Schritten: korrektes Abschnitts-Label, präzisierter Beschreibungstext, Ablösung der vier Freitext-Inputs durch pro-Metrik Segmented-Controls (Sensibel / Standard / Robust — analog zum Alerts-Tab mit `AlertMetricLevelRow`), und Erweiterung um Gewitter als fünfte threshold-fähige Metrik mit einem MED/HIGH-Toggle.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** Schwellwerte-Card (Zeile 513–582)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte` | component | Vorlage für pro-Metrik Segmented-Control-Muster |
| `src/output/tokens/builder.py` | module | Bereits korrekt (is_level=True, DEFAULTS["TH:"]=1.0) — kein Change nötig |
| `src/formatters/sms_trip.py` | module | ✅ Bereits deployed: SMS_SYMBOL_BY_METRIC["thunder"] = "TH:" |
| `src/services/trip_report_scheduler.py` | module | ✅ Bereits deployed: sms_threshold_thunder im Trend-Dict |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | test | Bestehende E2E-Assertions für Schwellwerte-Abschnitt |
| `tests/tdd/test_issue_624_metric_thresholds.py` | test | ✅ Bereits grün: "thunder" in SMS_SYMBOL_BY_METRIC |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | Label-Fix Z.515, Beschreibungstext Z.516, SMS_THRESHOLD_METRIC_IDS Z.77 um 'thunder' erweitern, 4 Freitext-Inputs durch 5 ThresholdMetricRow-Komponenten ersetzen |
| `frontend/src/lib/components/trip-detail/ThresholdMetricRow.svelte` | CREATE | Pro-Metrik Segmented-Control: [Metrik-Label] [Sensibel\|Standard\|Robust] [Wert] — analog zu AlertMetricLevelRow.svelte |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | MODIFY | Assertions für neues Label + Segmented-Controls statt Freitext-Inputs |

### Estimated Changes

- Files: 3
- LoC: +130/-62 (netto ~68; ThresholdMetricRow ~80 neu, WeatherMetricsTab ~62 raus / ~12 rein, E2E-Test ~20)

## Implementation Details

### Teiländerung 1 — Label-Fix (WeatherMetricsTab.svelte Z.515)

```
Vorher: <Eyebrow style="margin-bottom:8px">Schwellwerte</Eyebrow>
Nachher: <Eyebrow style="margin-bottom:8px">04 — Schwellwerte</Eyebrow>
```

### Teiländerung 2 — Beschreibungstext (WeatherMetricsTab.svelte Z.516–519)

```
Vorher: "Gelten für E-Mail, Telegram und SMS"
Nachher: "Gelten für SMS-Token, Telegram-Kurzform und den E-Mail-Ausblick/Trend-Block"
```

Die Haupttabelle der E-Mail wird **nicht** beeinflusst; der Ausblick/Trend-Block und die SMS/Telegram-Kurzform-Token schon.

### Teiländerung 3 — ThresholdMetricRow.svelte (neue Komponente)

Struktur analog zu `AlertMetricLevelRow.svelte`. Jede Metrik bekommt eine eigene Zeile:

```
[Metrik-Label]   [Sensibel]  [Standard]  [Robust]   [aktueller Wert]
Wind              ○           ●           ○           20 km/h
Böen              ○           ●           ○           40 km/h
Niederschlag      ●           ○           ○           0,3 mm
Regenwahrsch.     ○           ●           ○           40 %
Gewitter          [MED]       [HIGH]                  MED
```

**Preset-Werte (PO-bestätigt):**

| Metrik | Sensibel | Standard | Robust |
|--------|----------|----------|--------|
| Wind | 15 km/h | 20 km/h | 30 km/h |
| Böen | 30 km/h | 40 km/h | 50 km/h |
| Niederschlag | 0,3 mm | 0,8 mm | 1,5 mm |
| Regenwahrsch. | 25 % | 40 % | 60 % |
| Gewitter | — | — | — |

Gewitter hat nur MED (1.0) und HIGH (2.0) — kein 3-Stufen-Schema.

**Props ThresholdMetricRow:**
```typescript
interface Props {
  metricId: string;          // 'wind' | 'gust' | 'precipitation' | 'rain_probability' | 'thunder'
  label: string;             // Anzeige-Label
  levels: Level[];           // [{value: 'sensibel', label: 'Sensibel', float: 15}, ...]
  currentFloat: number | null;
  onChange: (metricId: string, float: number) => void;
}
```

**Reverse-Mapping (Laden):** Wenn `currentFloat` exakt einem Preset-Float entspricht → entsprechende Stufe aktiv. Kein Treffer → nächste Stufe anzeigen (kein Error-Zustand nötig, da initial nie benutzerdefinierte Werte existieren).

**data-testids:**
- `threshold-level-{metricId}-sensibel` / `-standard` / `-robust` (Buttons der 3-Stufen)
- `threshold-level-thunder-med` / `-high` (Gewitter-Buttons)

**Parent WeatherMetricsTab:** ersetzt den `<div class="sms-threshold-fields">` Block (Z.521–580) durch 5 `<ThresholdMetricRow>`-Instanzen. `smsThresholds`-State und die bestehende Speicher-Logik bleiben unverändert.

### Teiländerung 4 — SMS_THRESHOLD_METRIC_IDS (WeatherMetricsTab.svelte Z.77)

```javascript
// Vorher:
const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust'];
// Nachher:
const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust', 'thunder'];
```

Backend (AC-4 + AC-6) ist bereits deployed — keine weiteren Backend-Änderungen nötig.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer öffnet den Inhalt-Reiter eines Trips / When er den Schwellwerte-Block betrachtet / Then lautet die Eyebrow-Überschrift genau "04 — Schwellwerte" und der Hinweistext enthält "SMS-Token", "Telegram-Kurzform" und "E-Mail-Ausblick" — aber nicht mehr "Gelten für E-Mail, Telegram und SMS"
  - Test: Playwright gegen Staging; `page.locator('[data-testid="sms-thresholds"]').textContent()` prüfen; kein Mock

- **AC-2:** Given der Schwellwerte-Block ist sichtbar / When der Nutzer die Metrik-Zeilen betrachtet / Then gibt es für jede der vier Metriken (Wind, Böen, Niederschlag, Regenwahrsch.) drei Buttons (Sensibel/Standard/Robust) statt eines Freitext-Eingabefelds — und für Gewitter zwei Buttons (MED/HIGH)
  - Test: Playwright gegen Staging; `page.locator('[data-testid="threshold-level-wind-standard"]')` ist klickbar; kein `input[data-testid="sms-threshold-wind"]` mehr auffindbar; kein Mock

- **AC-3:** Given der Nutzer klickt für alle vier Metriken auf "Sensibel" (Wind/Böen/Niederschlag/Regenwahrsch.) / When er speichert und der Trip neu geladen wird / Then enthält der gespeicherte display_config die Werte wind=15, gust=30, precipitation=0.3, rain_probability=25 in den jeweiligen MetricConfig.sms_threshold-Feldern
  - Test: Playwright wählt Sensibel je Metrik, klickt Speichern, dann `GET /api/trips/{id}` und assert auf display_config-Felder; echter HTTP-Call, kein Mock

- **AC-4:** ✅ Bereits deployed (Backend-Teil; Scheduler-Trend-Dict enthält sms_threshold_thunder=2.0 bei Gewitter HIGH)

- **AC-5:** Given der Nutzer wählt für Gewitter "HIGH" / When er speichert und der Trip neu geladen wird / Then ist der Gewitter-Button "HIGH" beim nächsten Laden aktiv (Reverse-Mapping float 2.0 → HIGH)
  - Test: Playwright klickt HIGH, speichert, lädt Trip neu, prüft `data-testid="threshold-level-thunder-high"` hat aria-pressed="true" oder active-Klasse; kein Mock

- **AC-6:** ✅ Bereits deployed (Backend-Test; "thunder" in SMS_SYMBOL_BY_METRIC mit Wert "TH:")

## Known Limitations

- Kein "Benutzerdefiniert"-Zustand: wenn ein Trip aus alter Zeit einen Float-Wert hat der keinem Preset-Level entspricht, wird der nächste Standard-Button aktiv angezeigt. Beim Speichern wird dieser Standard-Wert übernommen (kein Datenverlust — nur Normalisierung auf Preset-Level).
- Gewitter-MED und Standard/Sensibel sind für die numerischen Metriken unabhängige Achsen — es gibt keine "alles auf Standard"-Schaltfläche.

## Changelog

- 2026-06-23: Initial spec created
- 2026-06-23: Überarbeitung: pro-Metrik Segmented-Controls statt globalem Preset-Dropdown; Hinweistext präzisiert (E-Mail-Ausblick/Trend-Block explizit genannt); Backend-ACs als deployed markiert
