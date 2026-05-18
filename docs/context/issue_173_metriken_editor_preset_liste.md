---
entity_id: issue_173_metriken_editor_preset_liste
type: issue
created: 2026-05-18
updated: 2026-05-18
status: ready_for_analysis
version: "1.0"
tags: [frontend, sveltekit, weather-config, trip-detail, metrics, presets, epic-138, ui-component]
related_issues: [#138, #206]
related_epics: [#138]
---

# Issue #173 — Metriken-Editor: Preset-Liste

## Request Summary

Implementiere eine **PresetRow-Komponente** innerhalb des WeatherMetricsTab (Epic #138), die eine Übersicht aller verfügbaren Presets darstellt. Jede Zeile zeigt:
- **Name** des Presets (z.B. "Wandern", "Skitouren")
- **Anzahl** der Metriken im Preset
- **Beschreibung** des Presets (optional)
- **Badge** (builtin/eigen) — markiert Presets als Standard oder benutzerdefiniert
- **Active Highlight** — hebt das aktuell angewendete Preset visuell hervor

**Kontext:** Teil von Epic #138 (Wetter-Metriken-Editor). Issue #173 spezifiziert die detaillierte Liste aller 7 Standard-Presets mit visueller Auszeichnung, während der Template-Select im Editor nur ein Dropdown-Feld ist.

---

## Related Files

| Datei | Relevanz | Status | Notizen |
|-------|----------|--------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | **Core** | ✓ Existiert | Template-Select (Dropdown) implementiert; PresetRow-Komponente fehlt noch |
| `frontend/src/lib/types.ts` | **Core** | ✓ Existiert | `WeatherConfigMetric`, `WeatherConfig`, `DisplayConfig` Interfaces |
| `frontend/src/lib/utils/rightColumn.ts` | **Reference** | ✓ Existiert | `TEMPLATE_LABELS` Map (8 Template-Namen) + `getPresetLabel()` Funktion |
| `src/app/metric_catalog.py` | **Reference** | ✓ Existiert | `WEATHER_TEMPLATES` (7 Presets mit `id`, `label`, `metrics[]`) |
| `cmd/server/main.go` | **Reference** | ✓ Existiert | Proxy-Routen: `GET /api/metrics`, `GET /api/templates` |
| `frontend/e2e/epic-138-metriken-editor.spec.ts` | **Reference** | ✓ Existiert | E2E-Test für WeatherMetricsTab; PresetRow nicht getestet |
| `docs/specs/modules/epic_138_metriken_editor.md` | **Reference** | ✓ Existiert | Vollständige Epic-Spec; §5 (WeatherMetricsTab) ohne PresetRow-Details |
| `docs/context/issue_206_weather_config_preset_name.md` | **Reference** | ✓ Existiert | `preset_name` in `display_config` speichern; PresetRow benötigt diesen Wert |

---

## Existing Patterns

### §1 Template-Datenquelle: Backend

**Backend-Quelle:** `src/app/metric_catalog.py` (Single Source of Truth)

```python
WEATHER_TEMPLATES: dict[str, dict] = {
    "alpen-trekking": {
        "label": "Alpen-Trekking",
        "metrics": [...14 Metriken...],
    },
    "wandern": {...},
    "skitouren": {...},
    "wintersport": {...},
    "radtour": {...},
    "wassersport": {...},
    "allgemein": {
        "label": "Allgemein",
        "metrics": [...8 Metriken...],
    },
}
```

**API-Endpunkt:** `GET /api/templates` → Returns `list[{id, label, metrics}]`

**Reihenfolge (insertion order):**
1. alpen-trekking (14)
2. wandern (9)
3. skitouren (13)
4. wintersport (10)
5. radtour (11)
6. wassersport (10)
7. allgemein (8)

### §2 Frontend-Pattern: Template-Dropdown in WeatherMetricsTab

**Aktuelles Template-Select-Pattern (Zeilen 161–176 in WeatherMetricsTab.svelte):**

```svelte
{#if templates.length > 0}
    <div class="template-row">
        <label for="metrics-tpl-sel" class="template-label">Template</label>
        <select
            id="metrics-tpl-sel"
            data-testid="weather-metrics-tab-template"
            bind:value={selectedTemplate}
            class="template-select"
        >
            <option value="">— Eigene Auswahl —</option>
            {#each templates as t}
                <option value={t.id}>{t.label}</option>
            {/each}
        </select>
    </div>
{/if}
```

**State in WeatherMetricsTab:**
```typescript
let selectedTemplate = $state('');  // Aktuell ausgewähltes Template
let lastAppliedTemplate = '';       // Guard gegen Re-Trigger
```

**Beim Template-Wechsel:**
- `$effect` überwacht `selectedTemplate`
- Setzt `enabledMap` basierend auf Template-Metriken
- Guard: `lastAppliedTemplate` verhindert Re-Trigger
- Manuelle Checkbox-Änderung → `selectedTemplate = '__custom__'`

### §3 Preset-Label-Lookup: rightColumn.ts Pattern

**Bestehende Map (rightColumn.ts, Zeilen 14–23):**

```typescript
const TEMPLATE_LABELS: Record<string, string> = {
    wandern: 'Wandern',
    wintersport: 'Wintersport',
    skitouren: 'Skitouren',
    'alpen-trekking': 'Alpen-Trekking',
    radtour: 'Radtour',
    wassersport: 'Wassersport',
    allgemein: 'Allgemein',
    summer_trekking: 'Sommer-Trekking',  // Legacy fallback
};

export function getPresetLabel(trip: Trip): string {
    const savedKey = trip.display_config?.preset_name;
    if (savedKey && savedKey in TEMPLATE_LABELS) {
        return TEMPLATE_LABELS[savedKey];
    }
    // Fallback zu activity_profile...
}
```

**Muster:** String-String Map, redundant zu Backend-Templates (keine Single Source of Truth im Frontend).

### §4 WeatherConfigDialog Pattern: Metriken + Format-Toggle

**Relevante Struktur (WeatherConfigDialog.svelte):**

```typescript
interface Template {
    id: string;
    label: string;
    metrics: string[];
}

let templates: Template[] = $state([]);
let enabledMap: Record<string, boolean> = $state({});
let friendlyMap: Record<string, boolean> = $state({});

function applyTemplate(event: Event) {
    const templateId = (event.target as HTMLSelectElement).value;
    // Setzt enabledMap basierend auf template.metrics
}
```

**Muster:** Toggle-Komponente für Format (Roh/Indikator) nur wenn `metric.has_friendly_format === true`.

---

## Epic #138 Context: Was bereits fertig ist

| Komponente | Status | Details |
|-----------|--------|---------|
| WeatherMetricsTab.svelte | ✓ Existiert | Template-Select + Metrik-Checkboxen + Roh/Indikator-Buttons + Save-Button |
| `/api/templates` Endpunkt | ✓ Existiert | Go Proxy zu Python; liefert 7 Templates mit Label + Metriken |
| `/api/metrics` Endpunkt | ✓ Existiert | Go Proxy zu Python; liefert 26 Metriken mit `has_friendly_format` Flag |
| `use_friendly_format` in Save-Payload | ✓ Implementiert | WeatherMetricsTab schreibt `{metric_id, enabled, use_friendly_format}` |
| WeatherConfigDialog Bug-Fix | ✓ Implementiert | `use_friendly_format` in Save-Payload aufgenommen |
| EditWeatherSection Bug-Fix | ✓ Implementiert | `use_friendly_format` in `displayConfig` Emission aufgenommen |

---

## PresetRow-Komponente: Design-Anforderungen

### §1 Datenstruktur

**Input (per Preset):**
```typescript
interface PresetRow {
    id: string;              // "wandern", "skitouren", etc.
    label: string;           // "Wandern", "Skitouren", etc.
    metricCount: number;     // Länge des `metrics` Arrays
    description?: string;    // Optional: "Hochalpine Touren" oder ähnlich
    isBuiltin: boolean;      // true für alle 7 Standard-Presets
    isActive: boolean;       // true wenn trip.display_config?.preset_name === id
}
```

**Quelle:** Templates von `/api/templates` + `trip.display_config.preset_name` für Active-Marker.

### §2 Visuelle Komponenten

**Empfohlenes Layout pro PresetRow:**

```
[Badge] Name           Metriken  Beschreibung (optional)    [Highlight]
┌────────────────────────────────────────────────────────┐
│ [🔧]  Wandern       9 Metriken    Tagestouren & leichte... │ ← active
│ [🔧]  Skitouren    13 Metriken    Schnee & Sicherheit      │
│ [🔧]  Allgemein     8 Metriken    Minimal Setup            │
└────────────────────────────────────────────────────────┘
```

**Komponenten:**
- **Badge** ("builtin" Icon/Text): Kennzeichnet Standard-Presets (alle 7)
- **Name** (Text): Template-Label
- **Metrik-Count** (Zahl): Länge `template.metrics`
- **Beschreibung** (optional, gekürzt): Max. 40–50 Zeichen
- **Active Highlight** (visuell): Border, Hintergrund-Farbe oder Stern-Icon

### §3 Interaktivität

**Klick-Verhalten:**
- PresetRow **klickbar** → wendet Preset an (analog zu Template-Dropdown-Select)
- Setzt `selectedTemplate = id` in WeatherMetricsTab
- `$effect` reagiert und aktualisiert `enabledMap`
- Zeigt aktives Preset visuell hervor

**Alternative (nur anzeigen):**
- PresetRow nur Informations-Widget, kein Klick
- Dropdown bleibt einzige Interaktion
- Minder-Anforderung aus Issue #173 Text ("PresetRow-Komponente")

---

## Beschreibungs-Text für Presets (optional)

Falls Issue #173 auch einen Description-Text pro Preset möchte:

| Template | Suggestion | Metriken |
|----------|-----------|----------|
| alpen-trekking | Hochalpine Touren mit vollem Metriken-Set | 14 |
| wandern | Leichte bis mittelschwere Tagestouren | 9 |
| skitouren | Schnee, Sicherheit und Wintersport-Fokus | 13 |
| wintersport | Wintersport mit Schnee und Sichtbarkeit | 10 |
| radtour | Fahrrad-spezifische Metriken (Wind, Richtung) | 11 |
| wassersport | Wasser-Sicherheit und Windrichtung | 10 |
| allgemein | Minimales Setup für Schnellüberblick | 8 |

**Backend-Quelle:** Müsste in `metric_catalog.py` ergänzt oder in neue API-Field aufgenommen werden. Aktuell nicht vorhanden.

---

## Implementation-Ansätze

### Ansatz A: PresetRow als eigenständige Komponente

**Datei:** `frontend/src/lib/components/trip-detail/PresetRow.svelte`

```svelte
<script lang="ts">
    interface Props {
        id: string;
        label: string;
        metricCount: number;
        isBuiltin: boolean;
        isActive: boolean;
        onSelect?: (id: string) => void;
    }
    let { id, label, metricCount, isBuiltin, isActive, onSelect }: Props = $props();
</script>

<div class="preset-row" class:active={isActive} onclick={() => onSelect?.(id)}>
    <span class="badge">{isBuiltin ? '🔧' : '⭐'}</span>
    <span class="label">{label}</span>
    <span class="count">{metricCount} Metriken</span>
    {#if isActive}
        <span class="active-marker">✓</span>
    {/if}
</div>

<style>
    .preset-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        border: 1px solid var(--g-border, #ddd);
        border-radius: 4px;
        cursor: pointer;
        background: var(--g-surface, #fff);
    }
    .preset-row.active {
        border-color: var(--g-accent, #c45a2a);
        background: var(--g-accent-light, #f5ede8);
    }
    .badge {
        flex-shrink: 0;
    }
    .label {
        flex: 1;
        font-weight: 500;
    }
    .count {
        font-size: 0.875rem;
        color: var(--g-ink-faint, #888);
        flex-shrink: 0;
    }
    .active-marker {
        color: var(--g-accent, #c45a2a);
        font-weight: 600;
    }
</style>
```

**Integration in WeatherMetricsTab:**
```svelte
<section class="presets-section">
    <h3 class="section-heading">Verfügbare Presets</h3>
    <div class="preset-list">
        {#each templates as t}
            <PresetRow
                id={t.id}
                label={t.label}
                metricCount={t.metrics.length}
                isBuiltin={true}
                isActive={selectedTemplate === t.id}
                onSelect={(id) => { selectedTemplate = id; }}
            />
        {/each}
    </div>
</section>
```

### Ansatz B: PresetRow inline in WeatherMetricsTab

**Einfacher:** Kein Export, Rendering direkt im Tab. Ersetzt oder ergänzt das Template-Dropdown.

---

## Dependencies

### Upstream
- **`GET /api/templates`** — Datenquelle für Presets (bereits implementiert)
- **`trip.display_config.preset_name`** — Markiert aktives Preset (Issue #206)
- **Epic #138** — WeatherMetricsTab (Parent-Container)

### Downstream
- **WeatherMetricsTab** — nutzt PresetRow zur Visualisierung
- **WeatherMetricsPreviewCard** — nutzt `getPresetLabel()` aus rightColumn.ts (indirekt)

---

## Risks & Considerations

### 1. Redundanz: rightColumn.ts TEMPLATE_LABELS vs. Backend Templates

**Problem:** `rightColumn.ts` hat eine hardcodierte Map der Template-Label, die mit `metric_catalog.py` redundant ist.

**Mitigation:** 
- PresetRow sollte Labels von `/api/templates` beziehen (Single Source of Truth)
- rightColumn.ts `TEMPLATE_LABELS` als Fallback behalten (defensive Programmierung)

### 2. Active-Preset-Marker setzt voraus: Issue #206 abgeschlossen

**Annahme:** `trip.display_config.preset_name` wird vom WeatherMetricsTab geschrieben (Issue #206).

**Falls nicht:** Active-Marker kann nicht zuverlässig gesetzt werden. → Abhängigkeit klären vor Implementierung.

### 3. Klick-vs.-Anzeige: UI/UX-Anforderung unklar

**Issue #173 schreibt:** "PresetRow-Komponente (Name, Anzahl, Beschreibung, builtin/eigen, aktiv-Highlight)"

**Offen:** Ist PresetRow klickbar oder nur informativ? 

- **Klickbar:** Ersetzt oder ergänzt Template-Dropdown. User kann direkt aus Liste wählen.
- **Nur Anzeige:** Zeigt Überblick, aber Template-Dropdown bleibt einzige Interaktion.

**Empfehlung:** Klickbar implementieren — bessere UX als reines Dropdown.

### 4. Beschreibungs-Text nicht im Backend vorhanden

**Problem:** Backend `WEATHER_TEMPLATES` hat nur `{id, label, metrics}`, kein Description-Feld.

**Lösung:** 
- **Option A:** Hardcode im Frontend (Anti-Pattern, siehe rightColumn.ts Redundanz)
- **Option B:** Backend ergänzen mit `description` Feld in `metric_catalog.py`
- **Option C:** Weglassen, nur Name + Count anzeigen

**Empfehlung:** Option C (MVP) — Beschreibung ist optional, kann später ergänzt werden.

### 5. Styling: Design System Compliance

**Anforderung:** PresetRow-Styling muss mit `var(--g-border)`, `var(--g-accent)`, etc. konsistent sein (siehe WeatherMetricsTab).

**Risiko:** Keine Figma-Design für diese Komponente vorhanden → Styling-Iterationen möglich.

### 6. Metrik-Count Kalkulation

**Einfach:** `template.metrics.length` bei jedem Render (keine Caching nötig).

**Aber:** Wenn `templates` asynchron geladen werden, muss Fallback existieren (Loading-State).

---

## Test-Artefakte (TDD)

### Unit Tests (geplant für Issue #173)
- PresetRow renders mit korrekten Props
- isActive-Klasse wird gesetzt wenn `isActive === true`
- onSelect-Callback wird beim Klick aufgerufen

### E2E Tests (in epic-138-metriken-editor.spec.ts erweitern)
- PresetRow-Liste wird angezeigt mit allen 7 Presets
- Klick auf PresetRow setzt `selectedTemplate` und aktualisiert Checkboxen
- Active-Marker zeigt das aktuell angewendete Preset

### data-testid Inventar
```
weather-metrics-preset-list           // Container
weather-metrics-preset-row-{id}       // Einzelne Zeile (z.B. wandern)
weather-metrics-preset-row-{id}-name  // Label-Text
weather-metrics-preset-row-{id}-count // Metrik-Zahl
weather-metrics-preset-row-{id}-active// Active-Marker
```

---

## Acceptance Criteria (Entwurf)

Basierend auf Issue #173 Anforderungen:

- **AC-1:** PresetRow-Komponente zeigt alle 7 Standard-Presets mit Name, Metrik-Anzahl und builtin-Badge
- **AC-2:** Aktives Preset wird visuell hervorgehoben (Border/Hintergrund/Icon)
- **AC-3:** PresetRow ist klickbar und wendet Preset an (wechselt enabledMap)
- **AC-4:** Alle PresetRows sind in WeatherMetricsTab sichtbar (oberhalb oder neben Template-Dropdown)
- **AC-5:** Description-Feld ist optional; MVP-Version zeigt nur Name + Count

---

## Scope Abgrenzung

| In Scope (Issue #173) | Out of Scope |
|----------------------|-------------|
| PresetRow-Komponente Visual Design | Benutzerdefinierte Presets (speichern/löschen) |
| Alle 7 Standard-Presets anzeigen | Preset-Management-UI (editieren, umbenennen) |
| Active-Highlight (if Issue #206 done) | Preset-Beschreibung von Backend laden |
| Klick-Interaktion (Preset anwenden) | Inline-Preset-Editor |
| CSS/Styling mit Design-Tokens | Neue API-Felder für Beschreibungen |

---

## Zeitschätzung

- **PresetRow.svelte (neu):** 50–100 LoC (HTML + CSS + Props)
- **WeatherMetricsTab Integration:** 20–30 LoC (Loop + onSelect-Handler)
- **E2E Tests:** 100–150 LoC (Playwright)
- **Gesamt (mit Tests):** ~300 LoC

---

## Summary for Workflow

- **Epic:** #138 (Wetter-Metriken-Editor)
- **Issue:** #173 (Metriken-Editor: Preset-Liste)
- **Status:** Ready for /2-analyse
- **Key Blockers:** Issue #206 (preset_name Persistierung) sollte abgeschlossen sein
- **Related:** rightColumn.ts (TEMPLATE_LABELS redundancy check)
- **Architecture:** Neue Komponente + WeatherMetricsTab Integration
