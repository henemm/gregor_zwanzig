# Context: Bug #89 — Weather Metrics Config Dialog Refactor (Variante A)

> Aktiver Workflow: `bug-89-weather-metrics-config`
> Vorgängerkontext (oberflächlich): `docs/context/bug-89-wettermetriken-konfig.md`

## Request Summary

Drei Wetter-Metrik-Dialoge in `src/web/pages/weather_config.py` driften auseinander:

| Dialog | Zeilen | Zustand |
|---|---|---|
| `show_weather_config_dialog` (Trip) | 89-315 | **Voll** — Metrik · Wert · Label · Alert · M · A |
| `show_location_weather_config_dialog` | 459-610 | **Reduziert** — nur Metrik · Wert |
| `show_subscription_weather_config_dialog` | 618-739 | **Reduziert** — nur Metrik · Wert |

Issue #89 fordert (1) Friendly-Toggle überall, (2) saubere Aggregations-UI, (3) Spec-Konformität, (4) Parität mit Trip-Dialog ("alte UI").

User hat **Variante A** gewählt: gemeinsame Render-Funktion mit Strategy-Dispatch.

## Architektur-Entscheidung

**Strategy-Dataclass `_DialogStrategy`** mit Modul-level Render-Funktion `_render_weather_config_dialog(strategy)`.

```python
@dataclass
class _DialogStrategy:
    title: str
    subtitle: str
    available_providers: set[str]
    current_configs: dict[str, MetricConfig]
    full_columns: bool          # True=Trip (Label+Alert+M+A), False=Location/Sub
    save_fn: Callable           # entity-spezifischer Save-Closure (factory-wrapped)
```

Drei Modul-level Save-Factories:
- `_make_trip_save_fn(trip_id, user_id, dialog)` — preserviert `show_compact_summary`/`show_night_block`/`night_interval_hours`/`thunder_forecast_days`/`multi_day_trend_reports`; mutable Trip → `save_trip()`
- `_make_location_save_fn(loc_id, user_id, dialog)` — Copy-Constructor für **frozen** SavedLocation → `save_location()`
- `_make_subscription_save_fn(sub_id, user_id, dialog)` — mutiert `target.display_config` → `save_compare_subscription()`

**Variabilitätsachsen — gelöst durch:**

| Achse | Trip | Location | Subscription | Lösung |
|---|---|---|---|---|
| Provider-Detection | Waypoints | Coords | hardcoded | Caller berechnet vor `_render_*` |
| Default-Config | `build_default_display_config(id)` | `build_default_display_config_for_profile(id, profile)` | `build_default_display_config(id)` | Caller berechnet `current_configs` |
| Persistenz | mutable + `save_trip` | frozen + Copy-Ctor + `save_location` | mutable + `save_compare_subscription` | drei `_make_*_save_fn` Factories |
| Trip-Felder | erhalten | n/a | n/a | Nur in `_make_trip_save_fn` |

## Related Files

| File | Action | Est. LoC |
|---|---|---|
| `src/web/pages/weather_config.py` | Refactor: Strategy + render + 3 save-factories; show_*-Funktionen schrumpfen auf ~25 LoC | -180 +100 = **netto -80** |
| `tests/integration/test_config_persistence.py` | NEW: `TestLocationConfigRoundtrip`, `TestSubscriptionConfigRoundtrip` | +60-80 |

**Gesamt: 2 Dateien, ~140 LoC neu/geändert. Unter Schwellenwert.**

## Existing Specs (Referenzen für die Refactor-Spec)

| Spec | Status | Relevanz |
|---|---|---|
| `docs/specs/modules/weather_metrics_ux.md` v1.1 | APPROVED | Dialog-UX 5-Spalten, Friendly-Toggle |
| `docs/specs/modules/weather_config.md` v2.3 | APPROVED | MetricConfig-Felder + Layout |
| `docs/specs/modules/generic_locations.md` v1.0 | APPROVED | Location nutzt identische `MetricConfig` (incl. alerts/M/A) |
| `docs/specs/modules/subscription_metrics.md` v1.0 | DRAFT | Subscription nutzt identische `MetricConfig` |

**Kein Widerspruch zwischen Specs:** Locations/Subscriptions haben bewusst dieselben Felder wie Trips.

## Loader-Status

`src/app/loader.py` serialisiert/deserialisiert für **alle drei Entities** bereits ALLE `MetricConfig`-Felder (`enabled`, `aggregations`, `morning_enabled`, `evening_enabled`, `use_friendly_format`, `alert_enabled`, `alert_threshold`). Gemeinsame `_parse_display_config()` (Zeile 187-214). **Keine Loader-Änderung nötig.**

## Risiken

1. **Safari-Kompatibilität:** Modul-level `make_cancel_handler` (Zeile 318) muss verwendet werden, nicht lokale Closures. Heutige Location-/Subscription-Dialoge definieren `make_cancel_handler` lokal — Bug, der durch den Refactor mitbehoben wird.
2. **Aggregation-Normalisierung-Asymmetrie:** Location/Sub nutzen `a.lower()`, Trip nutzt `label_to_key` Rückübersetzung. Shared-Funktion vereinheitlicht auf Trip-Pattern.
3. **Widget-Key-Asymmetrie:** Trip nutzt `widgets["agg_select"]`, Location/Sub nutzen `widgets["agg"]`. Vereinheitlicht auf `"agg_select"`.
4. **Trip-Dialog-Regression:** Trip ist heute korrekt — der größte Risikovektor. Bestehende `tests/integration/test_config_persistence.py::TestConfigRoundtrip` schützt vor Loader-Regression.

## Test-Strategie

- **Integration-Tests neu** für Location/Subscription Roundtrip mit `alert_enabled=True`, `morning_enabled=False`, `use_friendly_format=False` → werden sofort grün (Loader fertig), dienen als Regressionsanker.
- **Bestehende Tests** (`TestConfigRoundtrip`, `TestSubscriptionDisplayConfig`) müssen grün bleiben.
- **NiceGUI-E2E ist deaktiviert** (M4b Cutover); manuelle Browser-Verification über `/locations` und `/subscriptions` Seiten via E2E-Hook.

## Backwards-Compat

Bestehende JSON-Dateien (Trips, Locations, Subscriptions) ohne neue Felder defaulten korrekt via `MetricConfig`-Defaults. Loader ist vollständig.

## Bezug zum älteren Kontext

`bug-89-wettermetriken-konfig.md` adressierte oberflächliche Symptome (Alert-Default, Layout-Breite, Lücken in Label-Spalte). Variante A ersetzt diese Punkt-Fixes durch einen strukturellen Refactor — die Symptome verschwinden als Folge der Konsolidierung. Die SMS-Format-Querverweise (sms_format.md v2.0) bleiben relevant für die Output-Seite, sind aber für den UI-Refactor nicht im Scope.
