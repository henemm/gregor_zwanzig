# Context: Wetter-Templates

## Request Summary
Template-System für Wetter-Metriken (Alpen-Trekking, Küsten-Wandern, Skitouren, etc.) mit Override-Möglichkeit und Zeithorizont pro Metrik. Templates sollen im User-Profil speicherbar sein.

## Ist-Zustand
Templates existieren bereits **hardcoded im Frontend** (`WizardStep3Weather.svelte:21-50`) als 7 Profile mit festen Metrik-Listen. Sie werden nur im Trip-Wizard Step 3 verwendet und nirgends persistiert oder wiederverwendet.

Parallel existiert `PROFILE_METRIC_IDS` in `metric_catalog.py:382-397` mit 3 Profilen (wintersport/wandern/allgemein) für Locations.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | Hardcoded Templates (7 Stück), Override-Logik |
| `src/app/metric_catalog.py` | MetricDefinition, PROFILE_METRIC_IDS, build_default_display_config_for_profile() |
| `src/app/models.py:443-494` | MetricConfig, UnifiedWeatherDisplayConfig DTOs |
| `src/app/trip.py:163-234` | Trip model mit display_config |
| `src/app/user.py:50-69,195-228` | SavedLocation.activity_profile, User model |
| `src/app/loader.py` | load_trip, _parse_display_config, load_location |
| `api/routers/config.py:23-39` | GET /metrics endpoint |
| `src/formatters/trip_report.py` | format_email() nutzt display_config |
| `src/services/risk_engine.py` | risk_thresholds aus MetricCatalog |
| `docs/specs/modules/weather_config.md` | Bestehende Spec (v2.3) |

## Existing Patterns

- **Activity Profile → Metrics:** `build_default_display_config_for_profile()` mappt Profile auf Metriken
- **UnifiedWeatherDisplayConfig:** Zentrale Config mit MetricConfig-Liste, wird in Trip + Location genutzt
- **Frontend Template → Config:** WizardStep3Weather wählt Template → füllt enabledMap → erzeugt displayConfig
- **Factory Pattern:** UI-Handler nutzen `make_*_handler()` Pattern (Safari-Kompatibilität)

## Dependencies
- **Upstream:** MetricCatalog (metric definitions), User model, Trip model
- **Downstream:** TripReportFormatter, RiskEngine, WizardStep3Weather, weather_config.py dialog

## Existing Specs
- `docs/specs/modules/weather_config.md` — v2.3, Phase 2 (API-Aware UI) + Phase 3 (Per-Report-Type)

## Kernfragen für Analyse
1. Templates Backend oder Frontend? (Aktuell Frontend-only)
2. Wie Template-Persistierung im User-Profil?
3. Zeithorizont pro Metrik — wie in MetricConfig integrieren?
4. Vereinheitlichung der 7 Frontend-Templates mit den 3 Backend-Profilen?
5. Template-Sharing zwischen Trip-Wizard und Orts-Vergleich?

## Risks & Considerations
- Migration bestehender Trips die ohne Template-Referenz gespeichert wurden
- Zwei Template-Quellen (Frontend hardcoded vs Backend PROFILE_METRIC_IDS) müssen konsolidiert werden
- Zeithorizont pro Metrik erfordert Änderungen am Formatter und ggf. Provider-Layer
