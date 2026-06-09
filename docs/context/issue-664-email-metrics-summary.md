# Issue #664 — Metriken-Überblick am Beginn der E-Mail

**Workflow:** issue-664-email-metrics-summary
**Typ:** Feature (Full-Stack)
**Phase:** Analyse abgeschlossen, PO-'go' am 2026-06-08

## Wunsch (PO)
Optional zu Beginn der Briefing-E-Mail die gleichen Infos wie in der SMS, nur ausgeschrieben:
eine Pille je **konfigurierter** Metrik — Min/Max + Uhrzeit, „Schwellwert erstmals ab HH",
Regen-Summe. Für alle für den Kanal E-Mail aktivierten Metriken aus `display_config.metrics`.

## Design-Quelle
`Gregor 20 - Mail Vorschau.html` → `screen-output-preview.jsx` → `EmailMetricsSummary`
(eine Pille je Metrik, Farbe nach Schwere ok/warn/risk/info).
URL: https://api.anthropic.com/v1/design/h/mTf3S-r5ZtJSlsj1kkAAXQ?open_file=Gregor+20+-+Mail+Vorschau.html

## PO-Entscheidungen
1. **Gating:** `show_metrics_summary` an → Metriken-Überblick **ersetzt** Quick-Take UND blendet
   Tages-Summe-Block (#621) aus. Aus → Verhalten exakt wie heute (rückwärtskompatibel).
2. Antwort-Kommandos (#670) und ⚡-Gewitter-Badge (#669) sind **separate** Issues, nicht hier.

## Architektur — spiegelt #621-Toggle-Mechanik 1:1
Kette: `TripReportConfig` (models.py) → `loader.py` (load+dump) → `trip_report.py` (Flag auslesen+durchreichen)
→ `render_email()` (`__init__.py`) → `render_html()` (html.py) + `render_plain()` (plain.py).
Frontend: `EditReportConfigSection.svelte` (Toggle) + `reportConfigWrite.ts` (`MailElementUi` + `buildMailElementWrite`).
Go-Persistenz: bestehender PUT-Merge (`internal/handler/trip.go`, ReportConfig-Merge).

## Betroffene Dateien (~9 Quellcode + Tests)
| Datei | Änderung |
|---|---|
| `src/app/models.py` (~Z.726) | `show_metrics_summary: bool = False` in `TripReportConfig` |
| `src/app/loader.py` (~Z.373 load, ~Z.110 dump) | Feld laden + serialisieren |
| `src/output/renderers/email/helpers.py` (~Z.733/776) | neuer Helper `build_metrics_summary_pills(segments, thresholds, metrics)`; `pill_html` reuse |
| `src/output/renderers/email/html.py` (~Z.313 sig, ~Z.585 QT-Gate, ~Z.602 TS-Gate) | Param + Render-Block + Gating |
| `src/output/renderers/email/plain.py` | Param + Plaintext-Block + Gating |
| `src/output/renderers/email/__init__.py` (~Z.31) | Param durchreichen an html+plain |
| `src/formatters/trip_report.py` (~Z.121) | Flag auslesen + an `render_email()` |
| `frontend/.../edit/EditReportConfigSection.svelte` | Toggle (State + onMount-Load + RMW-Write) |
| `frontend/.../edit/reportConfigWrite.ts` | Interface-Feld + Write-Mapping |
| `tests/tdd/test_issue_664_*.py` | RED-Tests (Verhaltensnachweis) |

## Datenstruktur (Felder real vs. Design-Namen)
`ForecastDataPoint` (models.py:85-141): `t2m_c, wind10m_kmh, gust_kmh, wind_direction_deg,
precip_1h_mm, pop_pct, thunder_level (ThunderLevel), cloud_total_pct, cloud_low_pct,
visibility_m, uv_index, freezing_level_m, humidity_pct, dewpoint_c`.
Wind-Chill ("feels") nur als Aggregat `SegmentWeatherSummary.wind_chill_min_c` — pro Stunde
ggf. aus den extrahierten `seg_tables`-Row-Dicts (`_extract_hourly_rows`).
Design-Namen `feels`/`cldLow` ↔ Code `wind_chill`/`cloud_low` beim Mappen beachten.

## Schwellwerte
Pro Metrik aus `MetricConfig.alert_threshold` (wenn `alert_enabled=True`), sonst Default
(Design-Defaults: wind 20, gust 30, rainP 50, thunder 20, vis 2, hum 90 km/h bzw. %/km).
NICHT die `change_threshold_*` (das sind Delta-/Änderungsschwellen, nicht absolut).

## Scope-Flags
- >4–5 Dateien (Toggle zieht sich durch die ganze Render-Kette) — unvermeidbar, jede Änderung klein.
- LoC voraussichtlich >250 → `loc_limit_override` wird gesetzt, sobald absehbar.

## Verifikation
KEINE Mocks. Staging-Test-Trip → echte Mail an `gregor-test@henemm.com` → IMAP +
`email_spec_validator.py` Exit 0. Inaktives Setting: Verhalten byte-nah identisch zu heute.
