# Context: Trip Wizard W3 — Report-Konfiguration

## Request Summary
Step 4 im Trip-Wizard: Report-Einstellungen konfigurieren (Zeiten, Channels, Optionen). Letzter Schritt vor dem Speichern.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py` (L540-587) | TripReportConfig DTO — alle verfuegbaren Felder |
| `src/services/trip_report_scheduler.py` | Nutzt report_config fuer Scheduling + Versand |
| `src/app/loader.py` | Parse/Save von report_config |
| `frontend/src/lib/types.ts` (L39) | `report_config?: Record<string, unknown>` |
| `frontend/src/lib/components/wizard/TripWizard.svelte` | Step 4 Placeholder, Save-Logik |
| `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | W2 Pattern-Referenz |
| `docs/specs/modules/report_config.md` | Bestehende Spec (v1.1) |

## TripReportConfig Felder

| Feld | Typ | Default | Scheduler nutzt? |
|------|-----|---------|-------------------|
| `enabled` | bool | true | Ja |
| `morning_time` | time | 07:00 | Ja |
| `evening_time` | time | 18:00 | Ja |
| `send_email` | bool | true | Ja |
| `send_sms` | bool | false | - |
| `send_signal` | bool | false | Ja |
| `send_telegram` | bool | false | Ja |
| `alert_on_changes` | bool | true | - |
| `change_threshold_*` | float | varies | - |
| `wind_exposition_min_elevation_m` | float? | None | Ja |
| `show_compact_summary` | bool | true | Ja |
| `show_daylight` | bool | true | Ja |
| `multi_day_trend_reports` | list[str] | ["evening"] | Ja |

## Existing Patterns
- W2: `bind:displayConfig` mit `$bindable()`, `$state()`, `$effect()` sync
- W1/W2: Props-Interface, onMount fuer API-Calls
- TripWizard: `canProceed()` Validierung pro Step

## Dependencies
- Upstream: TripReportConfig DTO, Trip.report_config
- Downstream: TripReportSchedulerService, E-Mail/Signal/Telegram Channel

## Risks & Considerations
- Viele Felder — UI muss Komplexitaet verstecken (Sections/Accordions)
- Alert-Thresholds sind Power-User-Features, evtl. in "Erweitert" verstecken
- Channel-Auswahl haengt von Server-Konfiguration ab (SMS nicht verfuegbar)
