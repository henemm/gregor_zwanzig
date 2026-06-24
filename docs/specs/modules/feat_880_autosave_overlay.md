---
entity_id: feat_880_autosave_overlay
type: feature
created: 2026-06-24
updated: 2026-06-24
status: draft
workflow: feat-880-autosave-overlay
---

# Autospeicher-Indikator: Timestamp + fixes Overlay

## Approval

- [ ] Approved

## Purpose

Der Autospeicher-Indikator wird von einer inline eingebetteten Statuszeile in ein fixes Overlay am unteren Bildschirmrand umgebaut. Zusätzlich zeigt er den genauen Zeitpunkt des letzten erfolgreichen Speichervorgangs an (HH:MM), damit der Nutzer auf einen Blick erkennen kann, wann seine Daten zuletzt gesichert wurden.

## Source

- **File:** `frontend/src/lib/components/ui/SaveIndicator.svelte`
- **Identifier:** `SaveIndicator` (Svelte-Komponente)

Schicht: **Frontend / User-UI** — ausschließlich SvelteKit, kein Go-API- oder Python-Backend-Anteil.

## Estimated Scope

- **LoC:** ~80
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveStatusStore.svelte.ts` | store | Liefert `SaveStatus`-Klasse; bekommt neues Feld `savedAt` |
| `TripHeader.svelte` | component | Entfernt inline `<SaveIndicator>` aus der Statuszeile |
| `CompareEditor.svelte` | component | Entfernt inline `<SaveIndicator>` aus dem Editor-Kopf |
| BottomNav (mobile) | layout | z-50, Höhe 64 px, nur ≤ 899 px — Overlay muss darüber sitzen |

## Implementation Details

### 1. `SaveStatus` — neues Feld `savedAt`

`saveStatusStore.svelte.ts` erhält in der Klasse `SaveStatus`:

```ts
savedAt: Date | null = $state(null);
```

In `setSaved()` wird es auf `new Date()` gesetzt:

```ts
setSaved(): void {
    this.state = 'idle';
    this.error = null;
    this.savedAt = new Date();
}
```

### 2. Timestamp-Formatierung (SSR-sicher)

Keine `Date`-Methoden, die vom Locale abhängen. Stattdessen:

```ts
function formatTime(d: Date): string {
    const h = d.getHours();
    const m = d.getMinutes();
    return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
}
```

Anzeige im idle-Zustand: `✓ Gespeichert 14:32` (Uhrzeit in gedimmter Schrift).

### 3. `SaveIndicator.svelte` — fixes Overlay

Positionierung via Inline-Style oder dedizierter CSS-Klasse:

```css
.save-indicator {
    position: fixed;
    bottom: 16px;
    right: 16px;
    z-index: 40;
}

/* Mobile: über BottomNav (64px + safe-area) */
@media (max-width: 899px) {
    .save-indicator {
        bottom: calc(64px + env(safe-area-inset-bottom) + 8px);
    }
}
```

**Idle-Dimming** (nach 3 s Inaktivität):

```css
.save-indicator--idle {
    animation: gz-save-fade 200ms ease-out 3s forwards;
}
@keyframes gz-save-fade {
    to { opacity: 0.5; }
}
```

**Fehler-Zustand:** `opacity: 1` immer, kein Dimming, kein `animation`.

**Barrierefreiheit:** Opacity sinkt maximal auf 0.5 — nie `display: none` oder `visibility: hidden`.

### 4. `TripHeader.svelte` — inline `<SaveIndicator>` entfernen

Der Block in der `status-line`:

```svelte
{#if saveController}
    <SaveIndicator controller={saveController} />
{/if}
```

wird vollständig entfernt. Der `saveController`-Prop bleibt erhalten (Backward-Compat), wird aber nicht mehr für ein inline-Element genutzt.

### 5. `CompareEditor.svelte` — inline `<SaveIndicator>` entfernen

Analoges Vorgehen: Import und Verwendung von `SaveIndicator` im Editor-Kopf entfernen. `compareSaveCtl` bleibt als `SaveStatus`-Instanz erhalten und wird weiterhin an das globale Overlay übergeben.

### 6. Globales Overlay-Mounting

Das Overlay wird in der übergeordneten Layout-Datei (`+layout.svelte` oder `+page.svelte` der Trip-Detail-Route und der Compare-Route) eingebunden, sodass es seitenbreit sichtbar ist:

```svelte
<SaveIndicator controller={saveController} />
```

Der `saveController`-Prop wird via Context oder Prop-Drilling weitergereicht.

## Expected Behavior

- **Input:** `SaveStatus`-Instanz mit `state`, `error` und neuem `savedAt`
- **Output:** Fixes Overlay unten rechts; zeigt Speicherzustand + Uhrzeit des letzten Speicherns
- **Side effects:**
  - Inline-`<SaveIndicator>` verschwindet aus TripHeader-Statuszeile und CompareEditor-Kopf
  - Kein Viewport-Shrink (kein `padding-bottom` auf Body oder Layout)
  - Overlay verdeckt interaktive Elemente nicht dauerhaft (Dimming nach 3 s)

## Acceptance Criteria

**AC-1:** Given der Nutzer öffnet die Trip-Detail-Seite / When die Seite vollständig geladen ist / Then ist kein Speicher-Indikator mehr in der Header-Statuszeile sichtbar — stattdessen erscheint das Overlay unten rechts im Viewport (Playwright: `data-testid="save-indicator"` hat CSS-Property `position: fixed`).

**AC-2:** Given der Nutzer ändert einen Etappen-Wert im Trip-Editor / When der automatische Speichervorgang abgeschlossen ist / Then zeigt das Overlay den Text "Gespeichert" zusammen mit einer Uhrzeit im Format HH:MM (Playwright: `data-testid="save-indicator"` enthält ein Element mit zweistelliger Stundenzahl, Doppelpunkt und zweistelliger Minutenzahl).

**AC-3:** Given das Overlay befindet sich im idle-Zustand nach erfolgreichem Speichern / When 3 Sekunden vergangen sind ohne weitere Benutzeraktion / Then ist die Opacity des Overlays auf 0.5 abgesunken, aber das Element bleibt sichtbar und erreichbar (Playwright: computed opacity ≤ 0.5 und > 0; `display` ist nicht `none`).

**AC-4:** Given der Speichervorgang schlägt fehl (simulierter API-Fehler) / When der Fehler-Zustand eintritt / Then bleibt das Overlay dauerhaft bei opacity: 1 (kein Dimming) und zeigt die Fehlermeldung (Playwright: `data-state="error"` und computed opacity === 1 nach mehr als 3 Sekunden).

**AC-5:** Given der Nutzer verwendet ein Mobilgerät (Viewport ≤ 899 px) mit sichtbarer BottomNav / When das Overlay im idle-Zustand angezeigt wird / Then liegt das Overlay physisch oberhalb der BottomNav ohne diese zu überlagern (Playwright: `bottom`-Offset des Overlays ≥ 64 px gemessen vom Viewport-Unterrand; BottomNav-Elemente bleiben klickbar).

**AC-6:** Given zwei unabhängige Seiten (Trip-Editor und Compare-Editor) sind gleichzeitig in separaten Tabs geöffnet / When in Tab A gespeichert wird / Then zeigt Tab B keinen aktualisierten Timestamp und keinen veränderten Zustand — jede Seite hat eine isolierte `SaveStatus`-Instanz (Playwright: zwei Kontexte, Cross-Tab-Isolation prüfen).

**AC-7:** Given der Compare-Editor ist geöffnet / When der Nutzer eine Änderung vornimmt und der Autosave abgeschlossen ist / Then ist das Overlay unten rechts sichtbar mit Timestamp, und im Compare-Editor-Kopf ist kein zweiter inline-Indikator vorhanden (Playwright: genau ein Element mit `data-testid="save-indicator"` im DOM).

## Known Limitations

- `env(safe-area-inset-bottom)` wird von älteren Android-Browsern nicht unterstützt — dort gilt der Fallback `bottom: calc(64px + 8px)`, was funktional korrekt ist.
- Der Timestamp basiert auf der lokalen Gerätezeit des Nutzers — keine UTC-Normalisierung, kein Server-Zeitstempel.
- Bei sehr langen Fehlermeldungen (> ~200 Zeichen) kann das Overlay breit werden; Truncation mit `max-width: 320px; overflow: hidden; text-overflow: ellipsis` ist empfehlenswert, aber nicht Teil dieses Scopes.

## Scope

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|-------|-------------|--------------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `savedAt: Date \| null` zu `SaveStatus` hinzufügen; `setSaved()` setzt Timestamp |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | `position: fixed` + `bottom/right`-Offset + Mobile-Media-Query + Idle-Dimming-Animation + Timestamp-Anzeige |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | Inline `<SaveIndicator>` aus `status-line` entfernen |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Inline `<SaveIndicator>` aus Editor-Kopf entfernen |

### Estimated Changes

- Files: 4
- LoC: +60 / -15

## Changelog

- 2026-06-24: Initial spec created
