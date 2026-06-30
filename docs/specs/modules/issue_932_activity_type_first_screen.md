---
entity_id: issue_932_activity_type_first_screen
type: module
created: 2026-06-30
updated: 2026-06-30
status: draft
version: "1.0"
tags: [frontend, trip-new, ux]
---

# #932 — Aktivitätstyp auf ersten Screen (Route-Tab)

## Approval

- [ ] Approved

## Purpose

Das Aktivitätstyp-Dropdown in der Touren-Erstellung (`TripNewEditor`) soll auf den "Route"-Tab (erster Tab) verschoben werden. Von dort soll es automatisch das passende Wetter-Metrik-Template vorauswählen, wenn der User zum "Metriken"-Tab wechselt. Der überflüssige "Speichern"-Button in `WeatherMetricsTab` wird im Create-Modus ausgeblendet.

## Source

- **Files:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Schicht:** Frontend / User-UI (SvelteKit)

## Estimated Scope

- **LoC:** ~40
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripNewEditor.svelte` | Modified | Dropdown verschieben, stubTrip erweitern |
| `WeatherMetricsTab.svelte` | Modified | Speichern ausblenden, Template-Auto-Select |
| `/api/templates` | Upstream | Backend liefert Template-IDs + Metriklisten |

## Implementation Details

### 1. Aktivitätstyp-Dropdown: Metriken-Tab → Route-Tab

In `TripNewEditor.svelte`:
- Das `<Select>` "Aktivitätstyp" (Desktop: ~Z.726–740, Mobile: ~Z.943–956) aus dem `metriken`-Tab entfernen.
- Im `route`-Tab (Desktop: nach Startdatum-Feld; Mobile: nach Startdatum) einfügen — gleiche Optionen, gleiches `selectedActivity`-Binding.

### 2. Aktivitätstyp in stubTrip eintragen

```typescript
const stubTrip = $derived<Trip>({
    id: '__new__',
    name: name || 'Neue Tour',
    stages: [],
    activity: selectedActivity ?? '',     // NEU
    display_config: { channels, metrics: weatherMetrics } as unknown as Trip['display_config'],
});
```

### 3. WeatherMetricsTab: Template-Auto-Select bei Aktivitätstyp

In `WeatherMetricsTab.svelte`, nach `load()` (Templates geladen):

```typescript
const ACTIVITY_TO_TEMPLATE: Record<string, string> = {
    trekking: 'alpen-trekking',
    hochtour: 'alpen-trekking',
    klettersteig: 'alpen-trekking',
    mountaineering: 'alpen-trekking',
    ski_touring: 'skitouren',
    skitour: 'skitouren',
    hiking: 'wandern',
    fahrrad_15: 'radtour',
    fahrrad_20: 'radtour',
    fahrrad_25: 'radtour',
    mtb: 'radtour',
};

// Nach load() — in createMode mit bekanntem Aktivitätstyp Template voranwählen:
$effect(() => {
    if (!createMode || !trip.activity || isDirty || templates.length === 0) return;
    const tmplId = ACTIVITY_TO_TEMPLATE[trip.activity];
    if (tmplId && templates.some(t => t.id === tmplId)) {
        applyPreset(tmplId);
    }
});
```

### 4. Speichern-Button in createMode ausblenden

```svelte
<!-- ALT -->
{#if !saveController}
    <Btn ...>Speichern</Btn>
{/if}

<!-- NEU -->
{#if !saveController && !createMode}
    <Btn ...>Speichern</Btn>
{/if}
```

Gleiche Bedingung auch für "Ungespeicherte Änderungen"-Pill und "Gespeichert"-Meldung.

## Expected Behavior

- **Route-Tab**: Aktivitätstyp-Dropdown erscheint als viertes Feld (nach Startdatum).
- **Metriken-Tab**: Kein Aktivitätstyp-Dropdown mehr. Kein "Speichern"-Button. Wenn ein Aktivitätstyp gewählt wurde, ist das passende Template automatisch aktiv und die Metriken entsprechend vorausgewählt.
- **Kein Auto-Select**: Wenn kein Aktivitätstyp gewählt (leer), bleibt die Standard-Auswahl.
- **Nicht überschreiben**: Auto-Select feuert nur wenn `!isDirty` — manuell angepasste Metriken werden nicht zurückgesetzt.

## Acceptance Criteria

**AC-1:** Given Neue Tour anlegen / When Route-Tab geöffnet / Then erscheint das Aktivitätstyp-Dropdown unterhalb des Startdatums (Desktop + Mobile).
- Test: Playwright — `[data-testid="trip-new-editor"]` Route-Tab aufrufen, Aktivitätstyp-Dropdown sichtbar und bedienbar.

**AC-2:** Given Aktivitätstyp "Wandern" gewählt im Route-Tab / When Metriken-Tab geöffnet / Then ist Template "wandern" automatisch aktiv (passende Metriken vorausgewählt).
- Test: Playwright — Route-Tab: "hiking" wählen → Metriken-Tab öffnen → Template-Badge "Wandern" oder entsprechende Metriken sichtbar.

**AC-3:** Given Metriken-Tab geöffnet im Create-Modus / When keine Änderungen vorgenommen / Then kein "Speichern"-Button sichtbar.
- Test: Playwright — Metriken-Tab öffnen, `[data-testid="weather-metrics-tab-save"]` nicht im DOM.

**AC-4:** Given Aktivitätstyp gewählt + Metriken-Tab manuell angepasst / When Aktivitätstyp nochmals geändert / Then bestehende manuelle Anpassungen bleiben (kein Auto-Select mehr nach isDirty=true).
- Test: Playwright — Metriken manuell ändern → isDirty → Aktivitätstyp erneut setzen → Metriken unverändert.

**AC-5:** Given Metriken-Tab im Edit-Modus (bestehende Tour) / When geöffnet / Then Speichern-Button weiterhin sichtbar (kein Regress).
- Test: Playwright — `/trips/:id/edit` → Wetter-Tab → `[data-testid="weather-metrics-tab-save"]` im DOM.

## Known Limitations

- Der Auto-Select feuert einmalig nach Template-Load. Falls der User den Aktivitätstyp ändert NACHDEM er den Metriken-Tab besucht hat (isDirty=true), findet kein weiterer Auto-Select statt — das ist Absicht (manuelle Anpassungen schützen).
- Die Verbindung im 5-Schritt-Wizard (Step1Profile/Step3Weather) wird in diesem Issue NICHT geändert — der Wizard ist für `/trips/new` deprecated.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine UI-Verlagerung + reaktiver $effect-Hook. Kein neues Datenmodell, kein API-Endpoint, keine Architekturentscheidung nötig.

## Changelog

- 2026-06-30: Initial spec created (Issue #932)
