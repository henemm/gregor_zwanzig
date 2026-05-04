# Context: Trip-Wizard W2 (Wetter-Templates)

## Request Summary

Schritt 3 des Trip-Wizards: Wetter-Template-Auswahl und Metrik-Konfiguration. User waehlt ein Template (z.B. Alpen-Trekking), kann Metriken an/abwaehlen, und das Ergebnis wird als display_config im Trip gespeichert.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/wizard/TripWizard.svelte` | Container — Step 3 Placeholder ersetzen |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Bestehendes Metrik-UI (Checkboxen nach Kategorie) — Referenz |
| `src/app/metric_catalog.py` | 23 Metriken in 5 Kategorien, PROFILE_METRIC_IDS Templates |
| `src/app/models.py` | UnifiedWeatherDisplayConfig, MetricConfig Dataclasses |
| `api/routers/config.py` | GET /api/metrics Endpoint |
| `internal/handler/weather_config.go` | GET/PUT /api/trips/{id}/weather-config |
| `docs/specs/modules/weather_config.md` | Weather Config Spec (Phase 1-3) |
| `docs/specs/modules/weather_config_endpoints.md` | Go API Endpoints Spec |
| `docs/specs/ux_redesign_navigation.md` | Wizard Schritt 3 Design (Zeilen 136-158) |
| `frontend/src/lib/types.ts` | Trip.display_config Typ |

## Existing Patterns

- **PROFILE_METRIC_IDS** in metric_catalog.py: 3 vordefinierte Profile (wintersport, wandern, allgemein)
- **WeatherConfigDialog**: Laedt /api/metrics, zeigt Checkboxen nach Kategorie, speichert {metrics: [{metric_id, enabled}]}
- **display_config**: Opaque JSON im Trip, Go speichert als map[string]interface{}, Python parsed als UnifiedWeatherDisplayConfig
- **MetricConfig**: metric_id + enabled + aggregations + alert_enabled

## Dependencies

### Upstream
- GET /api/metrics — Metrik-Katalog (existiert, liefert id/label/unit/category/default_enabled)
- PUT /api/trips/{id}/weather-config — display_config speichern (existiert)
- PROFILE_METRIC_IDS — Template-Definitionen (existiert in Python, nicht via API exponiert)

### Downstream
- W3 (Reports): Baut auf display_config auf fuer Report-spezifische Metrik-Sets
- Trip Report Formatter: Nutzt display_config um Metriken in E-Mail darzustellen

## Existing Specs

- `docs/specs/modules/weather_config.md` — Phase 1 approved, Phase 2/3 spezifiziert
- `docs/specs/modules/weather_config_endpoints.md` — Implementiert
- `docs/specs/ux_redesign_navigation.md` — Approved, definiert Template-Konzept

## Risiken & Ueberlegungen

1. **Templates nur in Python**: PROFILE_METRIC_IDS existiert nur im Backend. Fuer den Wizard brauchen wir sie im Frontend — entweder API-Endpoint oder hardcoded im Frontend.
2. **Template-Speicherung im Profil**: UX Spec sagt "im Profil speichern" — braucht neue API-Endpoints fuer User-Templates. Koennte Out of Scope sein fuer W2.
3. **Per-Metrik Zeithorizont**: UX Spec zeigt heute/morgen/uebermorgen Checkboxen pro Metrik — das ist Phase 3 der Weather Config Spec. Unklar ob W2 oder spaeter.
4. **Provider-Erkennung**: Metriken sollten ausgegraut sein wenn Provider nicht verfuegbar — braucht Waypoint-Koordinaten-Check.
5. **/api/metrics erweitern**: Aktuell fehlen aggregations und providers im Response — W2 braucht diese Info.
