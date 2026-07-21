---
entity_id: issue_624_metric_thresholds
type: module
created: 2026-06-06
updated: 2026-06-06
status: implemented
version: "1.0"
tags: [output, sms, telegram, threshold, config]
---

# Konfigurierbare Schwellwerte pro Metrik (SMS/Telegram-Kurzform) — #624

## Approval

- [ ] Approved (PO „go")

## Purpose

In der SMS- und Telegram-Kurzform markiert der **erste Wert** eines Metrik-Tokens
(`W18@10`) die erste Stunde, in der ein Schwellwert überschritten wird; der Klammerwert
ist das Tagesmaximum. Diese Schwellwerte sind heute fest eingebaut (`DEFAULTS` in
`builder.py`) und für alle Trips identisch. Diese Spec macht den Schwellwert **pro Metrik
optional konfigurierbar** (Trip-DisplayConfig). Leer = bisheriger Standardwert
(bit-identisches Verhalten). Betroffen sind SMS und die Telegram-Kurzform (#614, gleicher
Token-Renderer). Die E-Mail-Tabelle (eigenes `display_thresholds`-Farbkonzept) bleibt außen vor.

## Source

- **File (Python):** `src/app/models.py` (`MetricConfig`), `src/formatters/sms_trip.py`
  (`format_sms`), `src/formatters/trip_report.py` (Aufrufer), `src/output/tokens/builder.py`
  (`build_token_line`/`_mk_metric`/`DEFAULTS`), `src/app/loader.py` (Roundtrip)
- **File (Go-API):** keine Struct-Änderung — Wert läuft durch `DisplayConfig
  map[string]interface{}` (additiver Map-Key je MetricConfig, Merge bleibt erhalten)
- **File (Frontend):** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  (Schwellwert-Input pro threshold-fähiger Metrik), `frontend/src/lib/types.ts`
- **Identifier:** `MetricConfig.sms_threshold`, `metric_id`→Symbol-Mapping `SMS_SYMBOL_BY_METRIC`,
  `build_token_line(..., thresholds=...)`

## Estimated Scope

- **LoC:** ~180–240 (Backend-Threading + Mapping + Persistenz + Frontend-Input)
- **Files:** 5–7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `build_token_line` / `_mk_metric` | extend | wendet pro-Symbol-Schwellwert an statt nur `DEFAULTS` |
| `MetricSpec.threshold` | reuse | existierendes Feld, wird jetzt aus User-Config befüllt |
| `MetricConfig` | extend | neues additives Feld `sms_threshold` |
| `SMSTripFormatter.format_sms` | extend | nimmt optionale Schwellwert-Map entgegen |
| `DisplayConfig` (Go-Map) | passthrough | persistiert das Feld ohne Struct-Änderung |
| `format_sms`-Aufrufer in `trip_report.py` | reuse | SMS- UND Telegram-Kurzform-Pfad reichen Map durch |

## Implementation Details

```
# src/app/models.py — MetricConfig (additiv)
sms_threshold: Optional[float] = None   # None = Catalog/DEFAULTS-Fallback

# Neues Mapping metric_id -> SMS-Symbol (nur threshold-fähige Metriken)
SMS_SYMBOL_BY_METRIC = {
    "precipitation": "R", "rain_probability": "PR",
    "wind": "W", "gust": "G",
}

# src/formatters/sms_trip.py — format_sms(..., thresholds: dict[str,float] | None = None)
# Map {symbol: wert} aus aktiven MetricConfig.sms_threshold ableiten und an
# build_token_line weiterreichen.

# src/output/tokens/builder.py — build_token_line(..., thresholds=None)
# in _mk_metric: thr-Priorität = thresholds[symbol] -> spec.threshold -> DEFAULTS.get(symbol)

# src/formatters/trip_report.py — beim SMS- und beim Telegram-Kurzform-Aufruf
# thresholds aus display_config.metrics ableiten und übergeben.
```

Persistenz: Go-API liest/schreibt `display_config` als generische Map → Read-Modify-Write-
Merge bereits gegeben; `sms_threshold` round-trippt ohne Go-Code-Änderung.

## Expected Behavior

- **Input:** Trip-DisplayConfig mit aktiven MetricConfig-Einträgen, optional je Eintrag
  `sms_threshold` (float). Forecast-Segmente wie bisher.
- **Output:** SMS-/Telegram-Kurzform-String, in dem der „erste-Überschreitung"-Wert jeder
  threshold-fähigen Metrik (R/PR/W/G) gegen den konfigurierten Schwellwert berechnet wird;
  ohne Konfiguration identisch zum bisherigen Defaultverhalten.

## Acceptance Criteria

**AC-1:** Given eine MetricConfig für Wind (`metric_id="wind"`) mit `sms_threshold = 25.0`,
When eine SMS/Telegram-Kurzform für einen Trip gerendert wird, dessen Wind erst um 14 Uhr
25 km/h erreicht (vorher darunter), Then zeigt das `W`-Token als erste-Überschreitung
`W25@14` (bzw. mit Tagesmaximum in Klammern), nicht den niedrigeren früheren Wert.

**AC-2:** Given eine MetricConfig OHNE gesetzten `sms_threshold` (None) für alle Metriken,
When SMS und Telegram-Kurzform für denselben Trip gerendert werden, Then ist der Output
bit-identisch zu den bestehenden Golden-Mastern in `tests/golden/sms/` (fixe DEFAULTS bleiben
Fallback, keine ungewollte Verhaltensänderung).

**AC-3:** Given ein Trip-DisplayConfig mit `metrics[i].sms_threshold = 5.0`, When der Trip
über die Go-API gespeichert und erneut geladen wird, Then ist `sms_threshold` weiterhin `5.0`
UND alle übrigen MetricConfig-/DisplayConfig-Felder sind unverändert erhalten
(Read-Modify-Write-Merge, kein Datenverlust).

**AC-4:** Given eine Metrik ohne SMS-Schwellwert-Bedeutung (z.B. `temperature`), When der
Nutzer den Wetter-Metriken-Tab öffnet, Then wird für diese Metrik KEIN Schwellwert-Eingabefeld
angezeigt; nur für die threshold-fähigen Metriken (Niederschlag, Regenwahrscheinlichkeit, Wind, Böen).

**AC-5:** Given der Wetter-Metriken-Tab eines Trips, When der Nutzer für eine threshold-fähige
Metrik einen Schwellwert einträgt und speichert, Then wird `sms_threshold` persistiert und ist
nach Neuladen der Seite weiterhin im Eingabefeld sichtbar.

## Known Limitations

- Nur die vier threshold-fähigen Metriken (R/PR/W/G) erhalten ein Feld; Temperatur/Level-
  Metriken haben kein „erste-Überschreitung"-Konzept.
- E-Mail-Tabelle nutzt weiterhin das separate `display_thresholds`-Farbkonzept (nicht vereinheitlicht).
- Schwellwert-Einheit folgt der Metrik (mm, %, km/h); keine Einheitenumrechnung.

## Out of Scope

- Vereinheitlichung mit dem E-Mail-`display_thresholds`-Farbkonzept.
- Schwellwerte für nicht-threshold-fähige Metriken (Temperatur etc.).
- Änderung des Token-Wire-Formats selbst (sms_format.md v2.0 bleibt).

## Changelog

- 2026-06-06: v1.0 — Initiale Spec (Issue #624), Schwellwert pro Metrik konfigurierbar.
