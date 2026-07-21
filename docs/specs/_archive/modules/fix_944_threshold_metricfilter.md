---
entity_id: fix_944_threshold_metricfilter
type: bugfix
created: 2026-07-01
updated: 2026-07-01
status: draft
version: "1.0"
tags: [bug, frontend, backend, sms, thresholds]
---

# Bug #944: Deaktivierte Metriken in Schwellwerten und Briefing-Output

## Approval

- [ ] Approved

## Purpose

Zwei getrennte Bugs mit gemeinsamem Kern: nicht ausgewählte Metriken (z.B. Schneehöhe, Schneefallgrenze) werden dennoch angezeigt bzw. in den Briefing-Output eingebettet.

- **Frontend:** In der „04 Schwellwerte"-Sektion des WeatherMetricsTab werden alle 7 `ThresholdMetricRow`-Zeilen bedingungslos gerendert — unabhängig davon ob die Metrik im Trip aktiviert ist.
- **Backend:** Im SMS/Telegram-Token-Builder gibt `_visible(None, rt)` → `True` zurück wenn kein `MetricSpec` für ein Symbol vorliegt. Dadurch erscheinen SN/SFL-Token im Briefing solange Schneedaten vorhanden sind, auch wenn die Metrik deaktiviert ist.

## Source

- **Frontend:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (Zeilen 536–624)
- **Backend (Adapter):** `src/formatters/trip_report.py` (Zeilen 198–212)
- **Backend (Builder):** `src/output/tokens/builder.py` (Zeilen 126–148, Funktion `_wintersport`)

## Estimated Scope

- **LoC:** ~40
- **Files:** 2 (Frontend: 1, Backend: 1 primär + 1 für Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsTab.svelte` | Frontend | Schwellwert-UI, Buckets-State |
| `trip_report.py` | Backend | SMS-Threshold-Dict-Aufbau |
| `builder.py` | Backend | `_wintersport()` Token-Filterung via `_visible()` |
| `sms_trip.py` | Backend | `SMS_SYMBOL_BY_METRIC` Mapping |

## Implementation Details

### Frontend-Fix

In `WeatherMetricsTab.svelte` jeden `ThresholdMetricRow`-Block mit einer `{#if}`-Bedingung auf Basis von `buckets.off` umschließen. `buckets.off` enthält die IDs der deaktivierten Metriken.

Für jede der 7 Zeilen:
```svelte
{#if !buckets.off.includes('snow_depth')}
  <ThresholdMetricRow metricId="snow_depth" ... />
{/if}
```

Metrik-ID-Mapping (Frontend-`metricId` → `buckets.off`-Eintrag):
- `wind` → `wind`
- `gust` → `gust`
- `precipitation` → `precipitation`
- `rain_probability` → `rain_probability`
- `thunder` → `thunder`
- `snow_depth` → `snow_depth`
- `snowfall_limit` → `snowfall_limit`

### Backend-Fix

In `trip_report.py` beim Aufbau von `_sms_thr` zusätzlich explizit deaktivierte `MetricSpec`-Einträge für alle Symbole übergeben, die in `SMS_SYMBOL_BY_METRIC` verzeichnet sind, aber NICHT in den aktiven Metriken (`dc.metrics`) enthalten sind.

**Empfohlener Weg:** `trip_report.py` baut eine `_disabled_sms_specs`-Liste mit `MetricSpec(symbol=sym, enabled=False)` für alle SMS-Symbole, deren `metric_id` nicht in den aktiven Metriken vorhanden ist. Diese wird an `format_sms()` als zusätzlicher `disabled_specs`-Parameter weitergereicht. In `format_sms()` werden diese ans Config-Ende angehängt (nach WE-Label, vor dem `build_token_line`-Aufruf). In `builder.py` ist keine Änderung nötig — `_visible(spec_with_enabled_false, rt)` → `False` funktioniert bereits korrekt (Zeile 60).

```python
# In trip_report.py — nach Zeile 203
active_metric_ids = {m.metric_id for m in dc.metrics}
_disabled_sms_specs = [
    MetricSpec(symbol=sym, enabled=False)
    for metric_id, sym in SMS_SYMBOL_BY_METRIC.items()
    if metric_id not in active_metric_ids
]
# Weitergabe an format_sms() via neuen Parameter disabled_specs
```

```python
# In sms_trip.py format_sms() — am Ende der config-Aufbau-Sektion (nach Zeile 265)
if disabled_specs:
    existing_syms = {s.symbol for s in config}
    config.extend(s for s in disabled_specs if s.symbol not in existing_syms)
```

**Achtung:** `SMS_SYMBOL_BY_METRIC` muss aus `sms_trip.py` importiert werden — der Import ist in `trip_report.py` bereits vorhanden (Zeile 198). `MetricSpec` wird ebenfalls bereits importiert.

## Expected Behavior

- **Frontend:** Threshold-Zeilen werden nur für aktivierte Metriken angezeigt. Deaktiviert man Schneehöhe im Metriken-Tab, verschwindet die entsprechende Zeile im Schwellwert-Block sofort (reaktiv via `buckets.off`).
- **Backend:** SN/SFL-Token erscheinen im SMS/Telegram-Output nur, wenn die entsprechende Metrik im Trip aktiviert ist — unabhängig davon ob tatsächlich Schneedaten in der Wettervorhersage vorhanden sind.

## Acceptance Criteria

**AC-1:** Given ein Trip ohne aktivierte Schneehöhe-Metrik / When der Nutzer den Wetter-Metriken-Tab öffnet / Then ist im Abschnitt „04 Schwellwerte" keine Zeile für Schneehöhe sichtbar.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer: Trip ohne `snow_depth` öffnen → WeatherMetricsTab → kein Element mit `data-testid="threshold-value-snow_depth"`.

**AC-2:** Given ein Trip ohne aktivierte Schneefallgrenze-Metrik / When der Nutzer den Wetter-Metriken-Tab öffnet / Then ist im Abschnitt „04 Schwellwerte" keine Zeile für Schneefallgrenze sichtbar.
  - Test: Playwright-E2E gegen Staging: kein Element mit `data-testid="threshold-value-snowfall_limit"`.

**AC-3:** Given ein Trip mit aktivierter Schneehöhe-Metrik / When der Nutzer den Wetter-Metriken-Tab öffnet / Then ist die Schneehöhe-Zeile sichtbar (Regression-Guard).
  - Test: Playwright-E2E gegen Staging: Trip mit `snow_depth` aktiviert → Element `data-testid="threshold-value-snow_depth"` vorhanden.

**AC-4:** Given ein Trip ohne aktivierte Schneehöhe- und Schneefallgrenze-Metriken / When ein Briefing-SMS generiert wird und Schneedaten in der Vorhersage vorhanden sind / Then enthält der SMS-Text weder `SN` noch `SFL`-Token.
  - Test: Echter Python-Unit-Test: `SMSTripFormatter.format_sms()` mit Segmenten die Schneedaten enthalten, `disabled_specs=[MetricSpec("SN", enabled=False), MetricSpec("SFL", enabled=False)]` → Ergebnis enthält weder `SN` noch `SFL`.

## Known Limitations

- Die Frontend-Filterung ist reaktiv: bestehende, bereits gespeicherte Schwellwert-Werte für deaktivierte Metriken bleiben in `display_config` erhalten und werden beim erneuten Aktivieren wiederhergestellt (kein Datenverlust, erwünschtes Verhalten).
- `thunder`-Metrik wird im SMS-Token-Pfad über einen anderen Mechanismus (TH:-Token) geroutet — der Backend-Fix betrifft ausschließlich `_wintersport()`-Tokens (SN, SFL, WC, AV).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Änderung folgt dem bestehenden `_visible()`-Muster in `builder.py`. Kein neues Konzept notwendig — deaktivierte MetricSpec-Einträge sind das vorhandene Mechanismus für diesen Zweck.

## Changelog

- 2026-07-01: Initial spec created (Bug #944)
