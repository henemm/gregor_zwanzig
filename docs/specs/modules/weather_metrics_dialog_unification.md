---
entity_id: weather_metrics_dialog_unification
type: module
created: 2026-04-25
updated: 2026-04-25
status: approved
version: "1.1"
tags: [ui, weather-config, refactor, locations, subscriptions, trip, cleanup, bugfix]
---

# Weather Metrics Dialog Unification (Bug #89)

## Approval

- [x] Approved (v1.0 — 2026-04-25, Variante A Architektur-Refactor)
- [x] Approved (v1.1 — 2026-04-25, Cleanup + ursprüngliche Trip-Bugs)

## Purpose

Schließt Bug #89 vollständig ab durch (a) den bereits durchgeführten Strategy-Refactor von Variante A, (b) Aufräumen toter UI-Pfade nach F76-Routen-Cleanup, (c) Behebung der **ursprünglichen User-Beschwerden** im Trip-Dialog (Alert-Defaults, Label-Spalten-Lücken, Dialog-Breite).

**Kontext-Update v1.1:** Browser-Verifikation hat ergeben, dass `show_location_weather_config_dialog` und `show_subscription_weather_config_dialog` seit Commit `9f91f8a` (F76 Alt-Routen-Aufräumen, 2026-04-20) **UI-tot** sind — die zugehörigen NiceGUI-Routes `/locations` und `/subscriptions` wurden auf `/compare` redirected. Die Dialog-Funktionen sowie ihre Save-Factories werden von keinem aktiven Caller mehr genutzt. v1.1 entfernt diesen toten Code und reduziert die Strategy auf Trip-only.

## Source

- **File:** `src/web/pages/weather_config.py`
- **Identifier:** `_render_weather_config_dialog`, `_make_trip_save_fn`, `make_cancel_handler`, `make_save_handler`, `show_weather_config_dialog`

Internal tags used by the spec-enforcement hook:
`renderweatherconfigdialog`, `maketripsavefn`, `makecancelhandler`, `makesavehandler`, `showweatherconfigdialog`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricConfig` | Model (`src/app/models.py`) | 7 Felder: `enabled`, `aggregations`, `morning_enabled`, `evening_enabled`, `use_friendly_format`, `alert_enabled`, `alert_threshold` |
| `UnifiedWeatherDisplayConfig` | Model (`src/app/models.py`) | Container für MetricConfig-Liste; Trip-spezifische Felder |
| `Trip` | Model (`src/app/trip.py`) | Mutable — direkte Mutation vor `save_trip()` |
| `MetricDefinition` | Model (`src/app/metric_catalog.py`) | Liefert `friendly_label`, `default_change_threshold` |
| `build_default_display_config()` | Function (`src/app/metric_catalog.py`) | Default-Konfiguration für Trip |
| `save_trip` | Function (`src/app/loader.py`) | Persistiert Trip nach Metric-Änderung |
| `get_available_providers_for_trip()` | Function (`src/web/pages/weather_config.py`) | Provider-Detection für Trip |
| `save_location` | Function (`src/app/loader.py`) | **Behalten** — wird vom SvelteKit-Frontend / Go-API genutzt |
| `save_compare_subscription` | Function (`src/app/loader.py`) | **Behalten** — wird vom SvelteKit-Frontend / Go-API genutzt |

## Implementation Details

### 1. Cleanup — Toten UI-Code entfernen

**Aus `src/web/pages/weather_config.py` ENTFERNEN:**

- `show_location_weather_config_dialog(loc, user_id)` — UI-tot seit F76 (`/locations` → `/compare` Redirect)
- `show_subscription_weather_config_dialog(subscription, user_id)` — UI-tot seit F76 (`/subscriptions` → `/compare` Redirect)
- `_make_location_save_fn(loc_id, user_id, dialog)` — kein Caller mehr
- `_make_subscription_save_fn(sub_id, user_id, dialog)` — kein Caller mehr
- `_DialogStrategy.full_columns: bool` — entfällt, da nur noch ein Consumer (Trip → immer voll)

**Aus `src/web/pages/locations.py` und `src/web/pages/subscriptions.py`:**

- Imports von `show_location_weather_config_dialog` / `show_subscription_weather_config_dialog` entfernen
- Wenn die Module dadurch leer/ohne aktive Routen werden: vollständig löschen oder auf das Nötigste reduzieren (Module sind seit F76 nicht mehr in `src/web/main.py` registriert)

**Loader-Funktionen `save_location` / `save_compare_subscription`:** **NICHT entfernen** — werden vom SvelteKit-Frontend und Go-API über die JSON-Persistenz konsumiert. Roundtrip-Tests bleiben aktiv.

### 2. `_DialogStrategy` vereinfachen

Da nur Trip übrig bleibt, wird `full_columns` entfernt. Die Render-Funktion zeigt **immer** alle Spalten (Metrik · Wert · Label · Alert · M · A).

```python
@dataclass
class _DialogStrategy:
    title: str
    subtitle: str
    available_providers: set[str]
    current_configs: dict[str, MetricConfig]
    save_fn: Callable
```

`_render_weather_config_dialog(strategy)` rendert unkonditional die volle Spaltentabelle.

**Alternative (gleichwertig akzeptabel):** Strategy ganz entfernen und Render-Logik zurück in `show_weather_config_dialog` inlinen. Beide Varianten sind erlaubt — Entscheidung dem Developer überlassen, wer den Code besser lesbar findet.

### 3. Trip-Bug-Fixes (ursprüngliche User-Beschwerden aus Issue #89)

Diese drei Bugs waren der eigentliche Trigger für Issue #89 und wurden in v1.0 nicht adressiert.

#### 3a. Alert-Default = `False` für Initial-Build

**Problem:** Wenn ein Trip ohne gespeicherte `display_config` geöffnet wird, sind Alert-Checkboxen für Temperatur, Gefühlte Temperatur, Wind und Böen standardmäßig **aktiviert**. Spec (`sms_format.md` v2.0) und Bug-Kontext fordern: Alerts sind **explizite Opt-ins**, Default = `False`.

**Fix:** In `build_default_display_config(trip_id)` (oder in der Render-Funktion beim Build der Default-`MetricConfig`) `alert_enabled=False` für alle Metriken setzen — auch wenn `MetricDefinition.default_change_threshold` einen Wert hat (der Threshold ist die Δ-Voreinstellung *falls* der Alert aktiviert wird, nicht ein Aktivierungs-Trigger).

**Backwards-Compat:** Bestehende Trips mit `alert_enabled=True` in JSON behalten ihren Wert. Nur **neue** Trips bzw. Trips ohne gespeicherte Config bekommen den korrekten Default.

#### 3b. Label-Spalten-Lücken entfernen

**Problem:** Die Label-Spalte hat eine `min-width`-Constraint (heute ~130px), wodurch Metriken ohne `MetricDefinition.friendly_label` (z.B. `TH+`) eine sichtbare Lücke hinterlassen.

**Fix:** In `_render_weather_config_dialog`:
- Label-Zelle nur befüllen, wenn `friendly_label` für die Metrik existiert
- `min-width` durch `gap`-Layout ersetzen — leere Zellen erzeugen keine Lücke
- Ziel: Reihen mit Friendly-Label fluchten, Reihen ohne Label haben ihre Wert-Spalte näher an der Alert-Spalte ohne sichtbares Loch

#### 3c. Dialog-Breite reduzieren

**Problem:** Heute `max-width: 960px`. In Browser-Fenstern <1100px wird die rechte Seite (M/A-Spalte) abgeschnitten oder horizontaler Scroll erscheint.

**Fix:** `max-width: 820px` (oder bis 880px wenn nötig nach Visual-Test). Spalten kompakter packen, Padding reduzieren falls 6 Spalten nicht mehr passen.

### 4. Tests

**Behalten (Regression-Anker für Persistenz-Layer, der vom SvelteKit/Go-API genutzt wird):**
- `tests/integration/test_config_persistence.py::TestLocationConfigRoundtrip` (3 Tests)
- `tests/integration/test_config_persistence.py::TestSubscriptionConfigRoundtrip` (2 Tests)
- `tests/integration/test_config_persistence.py::TestConfigRoundtrip` (Trip-Persistenz)
- `tests/integration/test_config_persistence.py::TestTripEditPreservesConfig`
- `tests/integration/test_config_persistence.py::TestDisabledMetricsExcluded`

**Anpassen (`tests/unit/test_weather_config_strategy.py`):**
- Tests für `_make_location_save_fn` und `_make_subscription_save_fn` entfernen
- `_DialogStrategy.full_columns`-Test entfernen (Feld weg)
- Verbleibende Strategy/Render/Trip-Save-Tests behalten

**Neu (für die Trip-Bug-Fixes, neue RED-Tests):**
- `test_alert_default_is_false_for_new_trip` — neuer Trip ohne JSON → alle MetricConfigs haben `alert_enabled=False`
- `test_existing_trip_keeps_alert_enabled` — Trip-JSON mit `alert_enabled=True` → bleibt `True` nach Re-Open
- `test_label_cell_empty_for_metric_without_friendly_label` — Render-Output enthält keine `min-width:130px` mehr; Metriken ohne `friendly_label` rendern keine Label-Zelle

Visuelle Regression (Dialog-Breite): manuell via Browser-Test, kein automatisierter Test.

## Expected Behavior

### Trip-Dialog — primärer und einziger Use-Case

- **Input:** User öffnet Wetter-Metriken-Dialog auf `/trips`
- **Output:** Tabelle mit 6 Spalten (Metrik · Wert · Label · Alert · M · A); `max-width: 820px`; Label-Spalte ohne Lücken bei Metriken ohne `friendly_label`
- **Side effects:** Keine bis "Speichern" geklickt

### Alert-Default

- **Input:** Neuer Trip ohne `display_config`
- **Output:** Alle MetricConfigs starten mit `alert_enabled=False`; User muss Alert explizit aktivieren

- **Input:** Bestehender Trip mit `alert_enabled=True` in JSON
- **Output:** Wert bleibt `True`, wird im Dialog angezeigt

### Save-Roundtrip

- **Input:** User aktiviert Alert für `temp_max` mit Δ=5.0 und speichert
- **Output:** `trip.display_config.metrics[*].alert_enabled = True`, `alert_threshold = 5.0` in JSON; Trip-spezifische Felder (`show_compact_summary`, `show_night_block`, `night_interval_hours`, `thunder_forecast_days`, `multi_day_trend_reports`) bleiben erhalten

### Backwards-Compat (unverändert)

- **Input:** Bestehende Trip-JSONs ohne neue Felder
- **Output:** Defaults via `MetricConfig` greifen

### Safari-Kompatibilität (unverändert)

- **Input:** Dialog in Safari, Speichern oder Abbrechen klicken
- **Output:** Aktion wird ausgeführt, Dialog schließt
- **Side effects:** Modul-level `make_cancel_handler` und `make_save_handler` — keine lokalen Closures

## Validation Strategy

**Automatisierte Tests:**
- Alle bestehenden `test_config_persistence.py`-Tests bleiben grün (Regression-Anker)
- Angepasste `test_weather_config_strategy.py`-Tests grün
- Neue Tests für Alert-Default + Label-Spalte grün

**Browser-Verifikation (manuell + Playwright-Skript):**
1. `/trips` → Wetter-Metriken-Dialog öffnen → Screenshot vergleichen mit Soll-Layout
2. Dialog-Breite: Browser-Fenster auf 1100px schrumpfen — kein horizontaler Scroll, M/A-Spalte sichtbar
3. Alert-Default: Neuer Trip → keine Alert-Checkbox aktiviert
4. Label-Spalte: Metrik mit `friendly_label="N/S/W/E"` (Windrichtung) zeigt Toggle; Metrik ohne `friendly_label` zeigt keine Lücke

**Pre-Commit-Gate:** `python3 .claude/validate.py` muss grün sein.

## Files to Change

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/web/pages/weather_config.py` | Cleanup tote Funktionen + Strategy vereinfachen + 3 Trip-Bugs fixen | -180 +60 = netto -120 |
| 2 | `src/web/pages/locations.py` | Tote `show_location_weather_config_dialog`-Aufrufe entfernen oder Datei löschen | -10 oder -240 |
| 3 | `src/web/pages/subscriptions.py` | Tote `show_subscription_weather_config_dialog`-Aufrufe entfernen oder Datei löschen | -10 oder -270 |
| 4 | `tests/unit/test_weather_config_strategy.py` | Location/Subscription-Factory-Tests entfernen, neue Tests für Alert-Default + Label-Spalte | -50 +50 = netto 0 |

**Erwarteter Netto-Effekt:** ~120 bis 600 LoC weniger im Repo, abhängig davon ob `locations.py`/`subscriptions.py` ganz gelöscht werden.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tote Datei `locations.py` enthält noch nicht-Dialog-Code, der genutzt wird | LOW | Vor Löschen `grep -rn` auf alle Funktionen der Datei prüfen |
| Loader-Roundtrip-Tests scheitern, weil sie auf gelöschten UI-Code referenzieren | LOW | Tests prüfen nur Loader, nicht UI — sollten unverändert grün bleiben |
| Alert-Default-Fix bricht bestehende Trips | LOW | Fix greift nur beim Initial-Build aus Defaults, nicht beim Laden gespeicherter JSONs |
| Dialog-Breite 820px zu schmal für 6 Spalten | MEDIUM | Visuell verifizieren, Padding anpassen, ggf. auf 880px gehen |
| Label-Spalten-Layout-Änderung bricht bestehende Optik | MEDIUM | Browser-Screenshot-Vergleich vor/nach |

## Related Specs

- `docs/specs/modules/weather_metrics_ux.md` v1.1 (APPROVED) — 5-Spalten-Layout, Friendly-Toggle
- `docs/specs/modules/weather_config.md` v2.3 (APPROVED) — MetricConfig-Felder
- `docs/specs/modules/sms_format.md` v2.0 (APPROVED) — Alert = Opt-in (`change_threshold`)
- `docs/specs/modules/output_token_builder.md` v1.0 (APPROVED, Epic #96 β1) — Wird Friendly/Alert/M/A zur Laufzeit konsumieren

## Known Limitations

- Renderer-Pfad: F14b respektiert `display_config` von Subscriptions/Locations noch nicht im Output — Epic #96 (β5) adressiert das.
- Dialog-Breite ist Visual-Tuning; eine spätere Responsive-Lösung wäre wünschenswert, aber außerhalb dieses Scopes.

## Changelog

- 2026-04-25: v1.0 — Initial Spec für Bug #89, Variante A (Strategy-basierte Render-Funktion).
- 2026-04-25: v1.1 — Cleanup nach Browser-Test-Erkenntnis: Location/Subscription-Dialoge UI-tot seit F76; Strategy auf Trip-only reduziert; ursprüngliche Trip-Bugs (Alert-Default, Label-Lücken, Dialog-Breite) explizit in Scope aufgenommen.
