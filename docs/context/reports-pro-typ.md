# Context: Reports pro Typ

## Request Summary
Unterschiedliche Metrik-Sets pro Report-Typ (Abend/Morgen/Warnung) und Kanäle pro Report wählbar. Aktuell werden alle Reports mit denselben Metriken gesendet.

## Ist-Zustand
- MetricConfig hat bereits `morning_enabled` / `evening_enabled` Felder — aber UNGENUTZT
- TripReportConfig hat globale Channel-Flags (send_email, send_signal, send_telegram) — nicht pro Report-Typ
- Formatter ignoriert report_type bei Metrik-Filterung
- Loader serialisiert morning_enabled / evening_enabled nicht

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:443-455` | MetricConfig mit morning_enabled/evening_enabled (vorhanden, ungenutzt) |
| `src/app/models.py:539-587` | TripReportConfig — globale Channel-Flags |
| `src/formatters/trip_report.py:39-138` | format_email() — nutzt display_config ohne Report-Typ-Filterung |
| `src/services/trip_report_scheduler.py:66-228` | send_reports(), _send_trip_report() — Channel-Dispatch |
| `src/services/trip_report_scheduler.py:350-382` | Channel-Auswahl (Email/Signal/Telegram) — global, nicht pro Typ |
| `src/app/metric_catalog.py` | WEATHER_TEMPLATES — könnte Report-Typ-Defaults definieren |
| `src/app/loader.py:187-214` | _parse_display_config() — serialisiert MetricConfig |
| `src/outputs/email.py` | EmailOutput Channel |
| `src/outputs/signal.py` | SignalOutput Channel |
| `src/outputs/telegram.py` | TelegramOutput Channel |
| `src/web/pages/report_config.py` | Report-Config UI Dialog |

## Existing Patterns
- MetricConfig.morning_enabled/evening_enabled: Optional[bool], None = folgt global enabled
- TripReportConfig: Flache Flags pro Channel (send_email, send_signal, etc.)
- Formatter: dc.metrics iteriert und prüft mc.enabled — kein Report-Typ-Filter

## Dependencies
- Upstream: MetricCatalog, WEATHER_TEMPLATES, UnifiedWeatherDisplayConfig
- Downstream: TripReportFormatter, TripReportSchedulerService, Channel Outputs

## Existing Specs
- `docs/specs/modules/weather_config.md` — Phase 3 beschreibt per-Report-Type Overrides (definiert, nicht implementiert)
- `docs/specs/modules/report_config.md` — v1.1, Report-Config UI
- `docs/specs/modules/trip_wizard_w3.md` — Wizard Step 4

## Risks & Considerations
- Scope-Risiko: Kanäle pro Report-Typ ist ein größerer Umbau der TripReportConfig
- Warn-Reports (Alert) sind ein separates System (trip_alert.py) — Integration komplex
- MetricConfig morning_enabled/evening_enabled existieren aber werden nirgends serialisiert/geladen
