---
entity_id: weather_templates
type: module
created: 2026-04-20
updated: 2026-04-20
status: draft
version: "1.0"
tags: [config, templates, api, metric_catalog, wizard, locations, svelte]
---

# Wetter-Templates Phase A: Template Registry + API

## Approval

- [ ] Approved

## Purpose

Zentralisiert die 7 Wetter-Aktivitaets-Templates (bisher nur hardcoded im Frontend) im Backend als Single Source of Truth und stellt sie ueber eine API bereit. Dadurch koennen sowohl der Trip-Wizard (WizardStep3Weather) als auch der Orts-Vergleich (WeatherConfigDialog) dieselbe Template-Liste beziehen — ohne Doppelung und ohne dass neue Templates an zwei Stellen gepflegt werden muessen.

## Source

- **Files:**
  - `src/app/metric_catalog.py` (MODIFY) — WEATHER_TEMPLATES + get_all_templates() + build_default_display_config_for_profile()
  - `api/routers/config.py` (MODIFY) — GET /templates Endpoint
  - `cmd/server/main.go` (MODIFY) — Proxy-Route /api/templates
  - `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` (MODIFY) — API-fetch statt hardcoded
  - `frontend/src/lib/components/WeatherConfigDialog.svelte` (MODIFY or CREATE) — Template-Selektor

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricDefinition` | dataclass | Metric-Definitionen aus MetricCatalog |
| `WEATHER_TEMPLATES` | dict | Neue zentrale Template-Registry in metric_catalog.py |
| `get_all_metrics()` | function | Validierung: alle Template-Metric-IDs muss im Katalog existieren |
| `build_default_display_config_for_profile()` | function | Wird angepasst, liest kuenftig aus WEATHER_TEMPLATES |
| Go HTTP server (`cmd/server/main.go`) | service | Proxy-Route /api/templates → Python /templates |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardStep3Weather.svelte` | component | Bezieht Template-Liste kuenftig per API-Call |
| `WeatherConfigDialog.svelte` | component | Neu: Template-Selektor via GET /api/templates |
| `build_default_display_config_for_profile()` | function | Liest Profile aus WEATHER_TEMPLATES statt PROFILE_METRIC_IDS |
| `tests/e2e/trip-wizard.spec.ts` | test | Assertiert Template-Anzahl (~209), muss auf 7 aktualisiert werden |

---

## Implementation Details

### 1. metric_catalog.py — WEATHER_TEMPLATES ersetzen PROFILE_METRIC_IDS

**Loeschen:** `PROFILE_METRIC_IDS` (3 Eintraege)

**Hinzufuegen:** `WEATHER_TEMPLATES` dict mit 7 Eintraegen:

```python
WEATHER_TEMPLATES: dict[str, dict] = {
    "alpen-trekking": {
        "label": "Alpen-Trekking",
        "metrics": [
            "temperature", "wind_chill", "wind", "gust", "precipitation",
            "thunder", "cape", "rain_probability", "snowfall_limit",
            "freezing_level", "cloud_total", "cloud_low", "visibility", "uv_index",
        ],
    },
    "wandern": {
        "label": "Wandern",
        "metrics": [
            "temperature", "humidity", "wind", "gust", "precipitation",
            "rain_probability", "cloud_total", "sunshine", "uv_index",
        ],
    },
    "skitouren": {
        "label": "Skitouren",
        "metrics": [
            "temperature", "wind_chill", "wind", "gust", "precipitation",
            "fresh_snow", "snow_depth", "snowfall_limit", "freezing_level",
            "cloud_total", "cloud_low", "visibility",
        ],
    },
    "wintersport": {
        "label": "Wintersport",
        "metrics": [
            "temperature", "wind_chill", "wind", "gust", "precipitation",
            "fresh_snow", "snow_depth", "cloud_total", "sunshine", "visibility",
        ],
    },
    "radtour": {
        "label": "Radtour",
        "metrics": [
            "temperature", "wind", "wind_direction", "gust", "precipitation",
            "rain_probability", "thunder", "cape", "cloud_total", "sunshine", "uv_index",
        ],
    },
    "wassersport": {
        "label": "Wassersport",
        "metrics": [
            "temperature", "wind", "gust", "wind_direction", "precipitation",
            "rain_probability", "thunder", "cape", "cloud_total", "visibility",
        ],
    },
    "allgemein": {
        "label": "Allgemein",
        "metrics": [
            "temperature", "wind", "gust", "precipitation",
            "rain_probability", "cloud_total", "sunshine",
        ],
    },
}
```

**Neue Funktion:**

```python
def get_all_templates() -> list[dict]:
    """
    Return all weather templates as a list of structured dicts.

    Returns:
        List of {"id": str, "label": str, "metrics": list[str]}
        in insertion order (alpen-trekking first, allgemein last).
    """
    return [
        {"id": tid, "label": tdata["label"], "metrics": tdata["metrics"]}
        for tid, tdata in WEATHER_TEMPLATES.items()
    ]
```

**Anpassung bestehender Funktion:**

```python
# Vorher: liest aus PROFILE_METRIC_IDS
# Nachher: liest aus WEATHER_TEMPLATES
def build_default_display_config_for_profile(
    trip_id: str, profile: str
) -> "UnifiedWeatherDisplayConfig":
    """
    Build display config pre-populated with a named template's metrics.

    Raises ValueError if profile is not in WEATHER_TEMPLATES.
    """
    if profile not in WEATHER_TEMPLATES:
        raise ValueError(f"Unknown template profile: {profile!r}")
    metric_ids = WEATHER_TEMPLATES[profile]["metrics"]
    # ... build MetricConfig list from metric_ids ...
```

### 2. api/routers/config.py — GET /templates Endpoint

```python
@router.get("/templates")
def get_templates() -> list[dict]:
    """
    Return all weather activity templates.

    Response shape:
        [
            {"id": "alpen-trekking", "label": "Alpen-Trekking", "metrics": ["temperature", ...]},
            ...
        ]
    """
    from app.metric_catalog import get_all_templates
    return get_all_templates()
```

Kein Auth erforderlich — Templates sind oeffentliche, read-only Konfigurationsdaten.
Einzufuegen in bestehende Router-Datei (analog zu GET /metrics).

### 3. cmd/server/main.go — Proxy-Route

Ein einzelner neuer Proxy-Eintrag analog zum bestehenden `/api/metrics`-Proxy:

```go
// GET /api/templates  →  Python /templates
router.GET("/api/templates", reverseProxy(pythonBackendURL + "/templates"))
```

Registrierung VOR etwaigen kuenftigen `/api/templates/:id`-Routen, um keine Kollision zu erzeugen.

### 4. WizardStep3Weather.svelte — Hardcoded TEMPLATES ersetzen

**Vorher (Zeilen 21-50):**

```svelte
const TEMPLATES = [
  { id: "alpen-trekking", label: "Alpen-Trekking", metrics: [...] },
  // ... 6 weitere hardcoded Eintraege
];
```

**Nachher:**

```svelte
<script>
  import { onMount } from "svelte";

  let templates = [];

  onMount(async () => {
    const res = await fetch("/api/templates");
    if (res.ok) {
      templates = await res.json();
    }
  });
</script>
```

Die restliche Komponentenlogik bleibt unveraendert:
- Template-Dropdown: `{#each templates as t}`
- `matchesTemplate(template, enabledMap)`: vergleicht template.metrics mit enabledMap
- `enabledMap` wird bei Template-Auswahl befuellt

Fallback bei Ladefehler: `templates = []` → Dropdown bleibt leer, User kann manuell waehlen.

### 5. WeatherConfigDialog.svelte — Template-Selektor hinzufuegen

Zieldatei: `frontend/src/lib/components/WeatherConfigDialog.svelte`
(Falls Datei nicht existiert: analog zur Trip-Wizard-Implementierung suchen und ggf. Dateinamen anpassen.)

**Template-Fetch (onMount, identisch zu WizardStep3Weather):**

```svelte
let templates = [];

onMount(async () => {
  const res = await fetch("/api/templates");
  if (res.ok) templates = await res.json();
});
```

**Template-Dropdown (oberhalb der Metrik-Checkboxen):**

```svelte
<label>Template laden</label>
<select on:change={applyTemplate}>
  <option value="">-- Kein Template --</option>
  {#each templates as t}
    <option value={t.id}>{t.label}</option>
  {/each}
</select>
```

**applyTemplate Handler:**

```js
function applyTemplate(event) {
  const templateId = event.target.value;
  if (!templateId) return;
  const tpl = templates.find(t => t.id === templateId);
  if (!tpl) return;
  // Setze enabledMetrics auf tpl.metrics (ersetzt bestehende Auswahl)
  enabledMetrics = new Set(tpl.metrics);
}
```

Template-Auswahl ueberschreibt die aktuelle Metrik-Auswahl. Kein Auto-Save: User muss danach explizit speichern.

---

## Expected Behavior

- **Input (GET /api/templates):** Kein Request-Body, keine Parameter.
- **Output:** JSON-Array mit 7 Elementen. Jedes Element hat `id` (string, kebab-case), `label` (string, deutsch), `metrics` (string-array mit Metric-IDs aus MetricCatalog).
- **Side effects:** Keine — rein lesend.

**WizardStep3Weather nach Migration:**
- Beim Laden der Seite wird `/api/templates` aufgerufen.
- Dropdown zeigt dieselben 7 Templates wie bisher (gleiche Reihenfolge, gleiche Labels).
- `matchesTemplate()` funktioniert identisch, da metric-IDs unveraendert sind.

**WeatherConfigDialog nach Erweiterung:**
- Template-Dropdown erscheint oberhalb der Metrik-Checkboxen.
- Auswahl eines Templates setzt Metrik-Checkboxen entsprechend.
- Bestehende manuelle Auswahl wird durch Template-Auswahl ersetzt.
- Kein Template ausgewaehlt = bestehende Konfiguration bleibt unveraendert.

**build_default_display_config_for_profile() nach Umbau:**
- Liest Metric-IDs aus `WEATHER_TEMPLATES[profile]["metrics"]`.
- Wirft `ValueError` bei unbekanntem Profil.
- Alle 3 bisherigen PROFILE_METRIC_IDS-Profile sind in WEATHER_TEMPLATES enthalten — kein Verhalten-Regression.

---

## Files to Change

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/app/metric_catalog.py` | MODIFY | +40 |
| 2 | `api/routers/config.py` | MODIFY | +15 |
| 3 | `cmd/server/main.go` | MODIFY | +1 |
| 4 | `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | MODIFY | -30 / +15 |
| 5 | `frontend/src/lib/components/WeatherConfigDialog.svelte` | MODIFY or CREATE | +50 |
| 6 | `tests/e2e/trip-wizard.spec.ts` | MODIFY | ~1 (Template-Count-Assert) |

**Total: ~90 LoC netto**

---

## Known Limitations

- `sunshine` ist in mehreren Templates referenziert, aber nicht in der MetricDefinition-Tabelle in `weather_config.md` aufgefuehrt. Vor Implementierung pruefen ob `sunshine` im MetricCatalog existiert — falls nicht, aus betroffenen Templates entfernen oder Metric nachtraegen.
- Phase B (User-saved custom templates) ist Out of Scope. Die Registry ist in dieser Phase read-only.
- WeatherConfigDialog-Dateiname muss vor Implementierung verifiziert werden — Analyse-Output nennt den Pfad als unsicher.
- E2E-Test `trip-wizard.spec.ts` Zeile ~209 assertiert Template-Anzahl und muss auf 7 aktualisiert werden falls der Test aktuell eine andere Zahl erwartet.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `sunshine` metric fehlt im Katalog | MEDIUM | Vor Implementierung in metric_catalog.py nachschlagen |
| WeatherConfigDialog existiert nicht unter erwartetem Pfad | MEDIUM | Dateipfad im Developer-Briefing verifizieren lassen |
| Route-Kollision /api/templates vs. /api/templates/:id | LOW | Proxy-Route vor specifischeren Routen registrieren |
| E2E-Test-Regression (Template-Count) | LOW | trip-wizard.spec.ts Zeile ~209 explizit im Briefing adressieren |

## Changelog

- 2026-04-20: v1.0 Initial spec created (Wetter-Templates Phase A)
