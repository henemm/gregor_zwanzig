---
entity_id: issue_266_location_preview_map
type: module
created: 2026-05-20
updated: 2026-05-20
status: approved
version: "1.0"
tags: [frontend, compare, ui, map]
---

# Issue #266 — LocationPreviewMap (Mini-Map im NewLocationWizard)

## Approval

- [x] Approved

## Purpose

`LocationPreviewMap.svelte` ist eine nicht-interaktive Kartenvorschau-Komponente für den
`NewLocationWizard.svelte`, die im ersten Schritt unterhalb der Koordinatenfelder eingeblendet
wird, sobald valide Koordinaten vorliegen (d.h. lat/lon nicht beide 0). Sie dient als
unmittelbares visuelles Feedback für den User, dass die eingegebenen oder importierten
Koordinaten korrekt erkannt wurden — ohne echten Tile-Layer, da der Wizard auf minimale
Abhängigkeiten und sofortige Renderzeit ausgelegt ist.

## Source

- **Files:**
  - `frontend/src/lib/components/compare/LocationPreviewMap.svelte` (NEU, ~50 LoC)
  - `frontend/src/lib/components/compare/NewLocationWizard.svelte` (ÄNDERN, ~12 LoC)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Svelte-Komponente (vorhanden) | Dekorativer CSS-Topo-Hintergrund als absolut positionierter Layer im Kartenrahmen |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Svelte-Komponente (vorhanden) | Integriert `LocationPreviewMap` in Schritt 1 nach den Koordinatenfeldern |

## Scope

Nur Frontend. 2 Dateien:

- **Neu:** `frontend/src/lib/components/compare/LocationPreviewMap.svelte`
- **Geändert:** `frontend/src/lib/components/compare/NewLocationWizard.svelte` (Step 1: `$derived coordsValid` + `{#if coordsValid}`-Block)

Keine Änderungen an:
- Go-Backend — keine API-Calls
- `types.ts` — kein neues Interface
- `TopoBg.svelte` — wird unverändert wiederverwendet

## Implementation Details

### LocationPreviewMap.svelte

Props-Interface:

```typescript
interface Props {
  lat: number;
  lon: number;
}

let { lat, lon }: Props = $props();
```

Komponentenstruktur (von außen nach innen):

```svelte
<div
  class="relative overflow-hidden rounded border border-[var(--g-ink-faint)]/20"
  style="width:240px; height:150px;"
>
  <TopoBg opacity={0.4} />

  <svg
    viewBox="0 0 240 150"
    width="240"
    height="150"
    class="absolute inset-0"
    pointer-events="none"
    role="img"
    aria-label="Kartenvorschau"
  >
    <!-- Zentrierter Accent-Pin: Teardrop-Pfad, Spitze zeigt nach unten -->
    <!-- Pin-Breite 20px, Höhe 28px, Radius 7px -->
    <!-- Pin-Zentrum: x=120, y=75 → transform="translate(110, 47)" -->
    <path
      d="M10 7 A7 7 0 0 1 10 21 Q10 28 10 28 Q10 28 10 21 A7 7 0 0 1 10 7 Z"
      fill="var(--g-accent)"
      transform="translate(110, 47)"
    />
  </svg>

  <p class="absolute bottom-1 left-2 text-[10px] text-muted-foreground font-mono">
    {lat.toFixed(4)}, {lon.toFixed(4)}
  </p>
</div>
```

Hinweise zur Geometrie des Accent-Pins:
- Teardrop-SVG-Pfad: Breite 20, Höhe 28, Radius 7 — identische Geometrie wie `WaypointPin` size='md'
- Kein Text oder Zahl im Pin (WaypointPin zeigt immer einen Index — ist hier unerwünscht)
- `transform="translate(110, 47)"` positioniert Pin-Mitte bei x=120, y=61; Spitze bei y=75 (= vertikale Mitte)
- `fill="var(--g-accent)"` — Accent-Farbe aus Design-System
- `pointer-events="none"` auf dem SVG — Komponente ist strikt nicht-interaktiv
- `TopoBg` ist rein dekorativ; der Hintergrund ist nicht geographisch (kein Tile-Layer)

### NewLocationWizard.svelte — Änderungen

**Neuer `$derived` Boolean** im Script-Block (nach bestehenden State-Deklarationen):

```typescript
let coordsValid = $derived(
  !isNaN(Number(lat)) &&
  !isNaN(Number(lon)) &&
  !(Number(lat) === 0 && Number(lon) === 0)
);
```

Default-Werte `lat=47.0 / lon=11.0` erfüllen die Bedingung und zeigen die Map sofort beim Öffnen des Wizards — das ist semantisch korrekt (Österreich-Zentrum als Orientierungspunkt).

**Neuer Template-Block** in Schritt 1, direkt nach den Koordinatenfeldern (nach Zeile 214, vor dem schließenden `{/if}` des Step-1-Blocks):

```svelte
{#if coordsValid}
  <div data-testid="location-wizard-map-preview" class="mt-3">
    <LocationPreviewMap lat={Number(lat)} lon={Number(lon)} />
  </div>
{/if}
```

**Neuer Import** im Script-Block:

```typescript
import LocationPreviewMap from '$lib/components/compare/LocationPreviewMap.svelte';
```

## Expected Behavior

- **Input:** `lat: number`, `lon: number` (valide Dezimalkoordinaten, nicht 0/0)
- **Output:** Renderiert einen 240×150 px Kartenrahmen mit TopoBg-Hintergrund, zentriertem Accent-Pin und Koordinatentext unten links
- **Side effects:** Keine — reine Anzeigekomponente, keine API-Calls, kein State außerhalb der Props

Reaktivität: Da `LocationPreviewMap` die Props `lat` und `lon` direkt aus dem Svelte-State des Wizards bezieht, aktualisiert sich die Darstellung (insbesondere der Koordinatentext) bei jeder Änderung automatisch durch Svelte-Reaktivität.

## Acceptance Criteria

**AC-1:** Given `LocationPreviewMap` wird mit `lat=47.0` und `lon=11.0` gerendert / When die Komponente im DOM erscheint / Then ist ein Container mit `width=240px`, `height=150px`, `overflow:hidden` und einer `border`-Klasse vorhanden; darin ein `<svg>`-Element mit `role="img"` und ein `<p>`-Element mit dem Text "47.0000, 11.0000".

**AC-2:** Given Step 1 des NewLocationWizard wird geöffnet mit Default-Koordinaten `lat=47.0`, `lon=11.0` / When der Dialog erscheint / Then ist das Element mit `data-testid="location-wizard-map-preview"` sichtbar, weil 47.0/11.0 die `coordsValid`-Bedingung erfüllen.

**AC-3:** Given Step 1 des NewLocationWizard zeigt die Kartenvorschau / When der User lat und lon manuell auf `0` und `0` setzt / Then verschwindet das Element mit `data-testid="location-wizard-map-preview"` aus dem DOM (0/0 ist nicht valide).

**AC-4:** Given `LocationPreviewMap` wird mit `lat=46.8523` und `lon=10.7673` gerendert / When die Komponente im DOM erscheint / Then zeigt der Koordinatentext exakt "46.8523, 10.7673" (4 Dezimalstellen, Komma-getrennt, `font-mono`-Klasse).

**AC-5:** Given ein Smart-Import via `resolvePreview` hat Koordinaten aufgelöst und in den Wizard-State geschrieben / When die aufgelösten lat/lon-Werte nicht beide 0 sind / Then erscheint `data-testid="location-wizard-map-preview"` automatisch ohne manuellen Reload — durch Svelte-Reaktivität auf den veränderten State.

**AC-6:** Given Step 1 des NewLocationWizard zeigt die Kartenvorschau mit Koordinaten A / When der User die lat- oder lon-Felder auf Koordinaten B ändert / Then aktualisiert sich der Koordinatentext im `<p>`-Element unmittelbar auf die neuen Werte, da `LocationPreviewMap` reaktiv an den Wizard-State gebunden ist.

## Known Limitations

- **Kein echter Tile-Layer:** `TopoBg` ist ein dekorativer CSS-Hintergrund — die Karte zeigt keine geographisch korrekte Kartenansicht. Der Pin ist immer zentriert und nicht auf die tatsächlichen Koordinaten projiziert. Dies ist explizit gewollt (Orientierungsvorschau, kein GIS-Viewer).
- **Feste Größe:** Die Komponente ist auf 240×150 px hardcodiert. Responsive Anpassung ist nicht vorgesehen, da der Wizard auf dem Desktop-Planungstool läuft und eine Side-by-Side-Layout-Änderung des Dialogs nicht Teil dieses Issues ist.
- **Keine Fehlerbehandlung für NaN:** `coordsValid` filtert NaN heraus — die Komponente empfängt niemals NaN als Prop, sofern der Wizard-State korrekt initialisiert ist.

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #266 — LocationPreviewMap im NewLocationWizard).
