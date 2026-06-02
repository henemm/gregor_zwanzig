---
entity_id: issue_500_stage_card_nav
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, waypoint-editor, navigation, stage-card, svelte]
---

# Issue #500 — Etappen-Kacheln im Trip-Editor anklickbar + Edit-Seite erreichbar

## Approval

- [ ] Approved

## Purpose

Die Trip-Edit-Seite (`/trips/[id]/edit`) ist durch einen 301-Redirect derzeit vollständig unerreichbar — sie leitet sofort auf die Trip-Detailseite um, statt den WaypointEditor zu laden. Dieses Spec beschreibt drei eng zusammenhängende Korrekturen: (1) den Redirect in `+page.server.ts` durch einen echten Trip-Load ersetzen, (2) `StageCard` bei gesetztem `onclick`-Prop mit `cursor-pointer` und Hover-Feedback ausstatten, und (3) den veralteten Kommentar in der Skip-Testdatei präzisieren, damit die historische Architektur-Entscheidung dokumentiert bleibt.

## Source

- **File:** `frontend/src/routes/trips/[id]/edit/+page.server.ts` (Trip-Load), `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` (CSS), `frontend/e2e/issue-407-waypoint-editor-screen.spec.ts` (Kommentar)
- **Identifier:** `load` (PageServerLoad), `StageCard` (Svelte-Komponente)

## Estimated Scope

- **LoC:** ~25
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/trips/[id]/+page.server.ts` | Referenz-Implementierung | Muster für Session-Cookie-weitergeleiteten Trip-API-Aufruf — identisch adaptieren |
| `EtappenStrip.svelte` | Svelte-Komponente | Ruft `StageCard` mit `onclick={makeStageActivateHandler(stage.id)}` auf — Klick-Logik ist dort vollständig vorhanden, StageCard muss nur visuell reagieren |
| `$env/dynamic/private` (GZ_API_BASE) | SvelteKit-Env | API-Basis-URL für den Go-Backend-Aufruf in `+page.server.ts` |
| `gz_session` Cookie | Auth | Wird aus `cookies.get('gz_session')` gelesen und als Header weitergeleitet |

## Implementation Details

### 1. `+page.server.ts` — Redirect durch Trip-Load ersetzen

Die bestehende Datei enthält ausschließlich:
```ts
throw redirect(301, `/trips/${params.id}?tab=stages`);
```

Ersetzen durch denselben Load wie `frontend/src/routes/trips/[id]/+page.server.ts`:

```ts
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ params, cookies }) => {
    const session = cookies.get('gz_session');
    const headers: Record<string, string> = {};
    if (session) headers['Cookie'] = `gz_session=${session}`;

    const res = await fetch(`${API()}/api/trips/${params.id}`, { headers });
    if (res.status === 404) {
        throw error(404, `Trip '${params.id}' nicht gefunden`);
    }
    if (!res.ok) {
        throw error(res.status, 'Fehler beim Laden des Trips');
    }

    const trip = await res.json();
    return { trip };
};
```

Keine weiteren Änderungen an `+page.svelte` nötig — die bestehende `WaypointEditorPage`-Komponente erwartet bereits ein `trip`-Prop.

### 2. `StageCard.svelte` — `cursor: default` → `cursor: pointer` wenn `onclick` gesetzt

In der CSS-Sektion: `.stage-card { cursor: default; }` anpassen auf `cursor: default;` als Basis, ergänzt um eine bedingte Klasse.

Da Svelte keine direkte CSS-Bedingung auf Prop-Präsenz erlaubt, wird eine reaktive Klasse genutzt:

```svelte
<!-- Im Template, beide Divs (normal + pause): -->
class:stage-card--clickable={!!onclick}
```

In der `<style>`-Sektion ergänzen:

```css
.stage-card--clickable {
    cursor: pointer;
}

.stage-card--clickable:hover {
    background: var(--g-paper-alt, #f0ede6);
    border-color: var(--g-ink-subtle, #a0998c);
}
```

Die Pause-Variante erhält dieselbe Klasse (identische Bedingung: `!!onclick`), da Pausentage ebenfalls anklickbar sein können.

### 3. `issue-407-waypoint-editor-screen.spec.ts` — Kommentar präzisieren

Den bestehenden Kommentar (Zeilen 13–14) ersetzen:

```ts
// Deaktiviert in #494: WaypointEditorPage ist nicht mehr der Einstieg auf /edit.
// Navigation Etappen-Kachel → WaypointEditor folgt in Folge-Issue.
```

Durch:

```ts
// Deaktiviert in #494: Diese Tests beschreiben eine verworfene Architektur,
// in der /edit direkt WaypointEditorPage als Root-View öffnete.
// Die aktuelle Architektur (ab #500) lädt die TripEditView auf /edit;
// der WaypointEditor wird über Etappen-Kachel-Klick aktiviert.
// Tests NICHT löschen (historische Referenz) und NICHT aktivieren (Architektur überholt).
```

## Expected Behavior

- **Input (AC-1):** Nutzer navigiert zu `/trips/[id]/edit` (z.B. via „Bearbeiten"-Button auf Trip-Detailseite)
- **Output (AC-1):** Seite lädt ohne Redirect; `TripEditView` wird gerendert mit Trip-Daten aus der API
- **Input (AC-2):** `StageCard` erhält `onclick`-Prop (gesetzt durch `EtappenStrip` via `makeStageActivateHandler`)
- **Output (AC-2):** Kachel zeigt `cursor: pointer` und einen sichtbaren Hover-Effekt (`background`- und `border-color`-Änderung)
- **Input (AC-3):** Nutzer klickt auf eine Etappen-Kachel im EtappenStrip
- **Output (AC-3):** `makeStageActivateHandler(stage.id)` wird ausgelöst; `activeStageId` im EtappenStrip-Store wechselt; Karte, Höhenprofil und Wegpunktliste aktualisieren sich (keine Änderung an dieser Logik erforderlich — sie funktioniert bereits)
- **Side effects:** Keine Datenpersistenz, kein API-Call beim Klick

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer mit einer vorhandenen Tour / When er `/trips/[id]/edit` direkt aufruft oder über den „Bearbeiten"-Button navigiert / Then wird die TripEditView gerendert (HTTP 200, kein Redirect auf `?tab=stages`)
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Etappen-Kachel (`StageCard`) mit gesetztem `onclick`-Prop im EtappenStrip / When der Nutzer mit der Maus darüber fährt / Then zeigt die Kachel `cursor: pointer` und einen sichtbaren Hover-Zustand (geänderter Hintergrund oder Rahmen)
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Nutzer befindet sich im WaypointEditor auf `/trips/[id]/edit` mit mindestens zwei Etappen / When er auf eine nicht-aktive Etappen-Kachel klickt / Then wird diese Etappe im Editor aktiv (Karte, Höhenprofil und Wegpunktliste zeigen die Daten dieser Etappe)
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Datei `issue-407-waypoint-editor-screen.spec.ts` / When sie gelesen wird / Then ist klar dokumentiert, dass die Skip-Tests eine verworfene Architektur beschreiben — nicht löschen, nicht aktivieren
  - Test: (populated after /tdd-red)

## Known Limitations

- `--g-paper-alt` ist ein angenommener Token-Name für den Hover-Hintergrund. Falls der Token im Design-System nicht existiert, Fallback auf einen konkreten Hex-Wert aus der bestehenden Token-Palette verwenden (z.B. `#f0ede6`).
- AC-3 setzt voraus, dass `EtappenStrip` und `makeStageActivateHandler` bereits korrekt verdrahtet sind — das ist laut Analyse der Fall und erfordert keine Codeänderung.

## Changelog

- 2026-06-02: Initial spec created (Issue #500)
