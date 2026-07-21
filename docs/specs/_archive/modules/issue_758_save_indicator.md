---
entity_id: issue_758_save_indicator
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [frontend, ux, trip-editor, compare-editor, auto-save, svelte5]
---

<!-- Issue #758 — Speicher-Status-Indikator + Trip-Editor Auto-Save -->

# Issue 758 — Speicher-Status-Indikator & Trip-Editor Auto-Save

## Approval

- [ ] Approved

## Purpose

Nutzer erkennen derzeit nicht, ob ihre Änderungen im Trip-Editor oder Orts-Vergleich-Editor
gespeichert sind. Dieses Modul führt einen einheitlichen, sichtbaren Speicher-Status-Indikator
in beiden Editoren ein und stellt den Trip-Editor konsequent auf Auto-Save um (explizite
Speichern-Buttons entfallen). Der Compare-Editor behält seinen expliziten Speichern-Button
(Speichern = bewusste Abschluss-/Navigation-Aktion), erhält aber denselben Indikator für
den Dirty-Zustand und den Speicher-Fortschritt.

## Source

### Neu (Frontend / User-UI)

- **File:** `frontend/src/lib/stores/saveStatusStore.svelte.ts` (NEU) — zentraler Svelte-5-Rune-Store (`$state`), den alle Save-Aktionen melden (`setSaving()`, `setSaved()`, `setError(message)`). Schlanke API, kein Framework-Overhead.
- **File:** `frontend/src/lib/components/ui/SaveIndicator.svelte` (NEU) — wiederverwendbares Atom, rendert einen der vier Zustände `idle`/`dirty`/`saving`/`error` als dezentes Label mit Icon/Spinner. Wird einmal pro Editor-Oberfläche eingebunden.

### Geändert (Frontend / User-UI)

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte` — Andock-Stelle für den Trip-Indikator (immer sichtbar über allen Tabs); Name-Save meldet an den Store; expliziter Name-Speichern-Button entfällt.
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — expliziter „Etappen speichern"-Button entfällt; Auto-Save-Debounce (~700 ms) bei allen Änderungen; Datums-Änderung (`handleDateChange`) und Flush vor Navigation melden an den Store.
- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` — expliziter „Briefing-Zeitplan speichern"-Button entfällt; Channel-Änderungen (`handleChannelChange`) mit Auto-Save + Store-Meldung statt `console.error`.
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — expliziter Metriken-Speichern-Button entfällt; Metriken-Änderung triggert Auto-Save mit Store-Meldung.
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte` — Andock-Stelle für Compare-Indikator im Header-Bereich; vorhandene Dirty-Pill (`Ungespeichert`) durch `SaveIndicator`-Atom ersetzt; `saveStatus`/`saveError` aus `compareWizardState` fließen in Indikator.
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — `saveStatus` und `saveError` werden bereits korrekt gesetzt (kein Umbau nötig); neuer `isDirty`-Rune-State für `dirty`-Zustand.

> **Schicht-Hinweis:** Ausschließlich `frontend/src/` — keine Backend-Änderungen (Python `src/`, Go `api/internal/cmd/`). Die bestehenden PUT-Endpunkte und ihre Merge-Semantik (Read-Modify-Write) bleiben vollständig unangetastet.

## Estimated Scope

- **LoC:** ~350–450 (2 neue Dateien ~80 LoC + ~6 Komponenten je ~40–70 LoC Umbau)
- **Files:** 8 (2 neu, 6 geändert)
- **Effort:** high

> Hinweis: Scope überschreitet das Standard-LoC-Limit von 250. Vor Implementierung mit `workflow.py set-field loc_limit_override 500` überschreiben.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/api.ts` | intern | `ApiError` bei HTTP-Fehlern — wird von Auto-Save-catch abgefangen |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | intern | Vorhandener `saveStatus: SaveStatus` und `saveError` werden in den Indikator weitergeleitet |
| `SvelteKit beforeNavigate` | SvelteKit API | Flush-Hook — stellt sicher, dass Debounce-Queue vor Navigation geleert wird |
| `bits-ui` (Spinner) | UI-Lib | Optional für Spinner im `saving`-Zustand, analog zu bestehenden Komponenten |

## Implementation Details

### Zustandsmodell (einheitliches Vokabular)

| Zustand | Label | Wann |
|---------|-------|------|
| `idle` (clean) | „Gespeichert ✓" | Startzustand + nach erfolgreichem Save |
| `dirty` | „Nicht gespeichert" | Compare-Editor: nach jeder Änderung vor explizitem Speichern |
| `saving` | „Speichere …" + Spinner | Während laufendem API-Call |
| `error` | „Fehler beim Speichern" | Nach API-Fehler (mit kurzem Fehlertext) |

Im Trip-Editor gibt es keinen `dirty`-Zustand aus Nutzersicht: jede Änderung löst sofort
Auto-Save aus (`idle` → `saving` → `idle`/`error`). `dirty` ist nur im Compare-Editor
relevant (expliziter Speichern-Schritt).

### Store-API (`saveStatusStore.svelte.ts`)

```typescript
// Zustand
export const saveStatus = $state<'idle' | 'dirty' | 'saving' | 'error'>('idle');
export const saveError = $state<string | null>(null);

// Aktionen
export function setSaving(): void
export function setSaved(): void
export function setDirty(): void
export function setError(message: string): void
```

Pro Editor-Oberfläche wird eine eigene Store-Instanz erzeugt (Factory oder Klassen-Instanz),
damit Trip- und Compare-Indikator unabhängig voneinander sind.

### Auto-Save-Debounce (Trip-Editor)

```typescript
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleAutoSave(saveFn: () => Promise<void>) {
    if (debounceTimer) clearTimeout(debounceTimer);
    setDirty(); // optional: kurz dirty zeigen, dann sofort saving
    debounceTimer = setTimeout(() => void doSave(saveFn), 700);
}

async function doSave(saveFn: () => Promise<void>) {
    setSaving();
    try {
        await saveFn();
        setSaved();
    } catch (e) {
        setError(extractErrorMessage(e));
    }
}
```

Debounce-Intervall: 700 ms (Kompromiss — kein Trigger bei jedem Tastendruck,
aber kein merklicher Verzug bei schneller Eingabe).

### Flush vor Navigation (`beforeNavigate`)

```typescript
// In TripHeader.svelte oder +page.svelte
import { beforeNavigate } from '$app/navigation';

beforeNavigate(({ cancel }) => {
    if (debounceTimer) {
        cancel();
        clearTimeout(debounceTimer);
        void doSave(currentSaveFn).then(() => goto(pendingUrl));
    }
});
```

Verhindert Datenverlust bei schnellem Klick auf einen anderen Trip oder Tab.
Analog zu `#498`-Fix (Auto-Save bei Navigation weg in `TripNewEditor`).

### Compare-Editor: Dirty-State

`isDirty` wird nach jeder Nutzereingabe in `compareWizardState` auf `true` gesetzt
und nach `saveComparePreset()` / `saveNewPreset()` zurückgesetzt. Der Indikator
zeigt `dirty` solange der Nutzer nicht gespeichert hat. `saveStatus` aus dem
vorhandenen State (`compareWizardState.svelte.ts` Z. 41) fließt direkt in
`SaveIndicator` — kein Umbau der Save-Methoden nötig.

### Kein Datenverlust durch unvollständige Objekte

Auto-Save ruft dieselben PUT-Endpunkte wie die bisherigen Buttons — mit
denselben vollständigen Payloads (Read-Modify-Write bleibt im Backend). Der
Store im Frontend liest immer den aktuellen Reaktiv-State der Komponente,
nicht einen gecachten Snapshot. Kein partielles Überschreiben.

## Expected Behavior

- **Input:** Nutzer-Interaktion im Trip-Editor (Namens-Änderung, Etappen-Datum, Metriken, Briefing-Zeitplan) oder im Compare-Editor (Feld-Änderung, dann Speichern-Klick)
- **Output:** Sichtbarer Indikator in der Editor-Oberfläche mit aktuellem Speicher-Status; bei Trip-Editor automatisches Speichern nach ~700 ms Pause; bei Compare-Editor expliziter Speichern-Button bleibt erhalten
- **Side effects:** Explizite Speichern-Buttons im Trip-Editor werden entfernt (kein Breaking-Change für Backend oder Daten-Schema)

## Acceptance Criteria

**AC-1:** Given der Nutzer hat einen Trip geöffnet und ist im Tab „Etappen" / When er den Namen einer Etappe ändert und ~700 ms wartet (ohne Speichern-Button zu klicken) / Then zeigt der Indikator in `TripHeader` kurz „Speichere …" und wechselt danach zu „Gespeichert ✓", ohne dass der Nutzer einen Button betätigt hat.
  - Test: Playwright gegen Staging — Etappen-Name in `EditStagesPanelNew` ändern, kein Klick auf Speichern-Button (Button ist nicht mehr vorhanden), nach 1 Sekunde prüfen: `data-testid="save-indicator"` enthält Text „Gespeichert" (oder Checkmark-Icon-Attribut).

**AC-2:** Given der Trip-Editor ist geladen und es wurden keine Änderungen vorgenommen / When die Seite initial gerendert ist / Then zeigt der Indikator in `TripHeader` den Ruhezustand „Gespeichert ✓" (dezentes Label sichtbar, kein Fehler, kein Spinner).
  - Test: Playwright gegen Staging — Trip-Detailseite laden, `data-testid="save-indicator"` sofort nach Render prüfen: enthält Klasse oder Attribut für `idle`-Zustand, kein Spinner-Element sichtbar.

**AC-3:** Given der Nutzer ist im Compare-Editor und ändert den Namen des Vergleichs / When die Änderung erfolgt (vor Klick auf „Speichern") / Then zeigt der Indikator im Compare-Editor-Header „Nicht gespeichert" (dirty); nach Klick auf den expliziten Speichern-Button wechselt er zu „Speichere …" und dann zu „Gespeichert ✓".
  - Test: Playwright gegen Staging — Compare-Editor öffnen, Name-Feld ändern, prüfen: `data-testid="save-indicator"` zeigt `dirty`-Zustand; „Speichern"-Button klicken, prüfen: Zustand wechselt `saving` → `idle` (Text/Attribut).

**AC-4:** Given eine gültige Änderung im Trip-Editor wird gespeichert / When der API-Call fehlschlägt (simuliert via Netzwerk-Intercept oder gezielter Fehler-Route) / Then zeigt der Indikator „Fehler beim Speichern" mit einem kurzen Fehlerhinweis — kein stilles Scheitern, kein `console.error` ohne UI-Feedback.
  - Test: Playwright gegen Staging — `page.route` auf PUT-Endpunkt mit `{ status: 500 }` antworten lassen; Änderung triggern; nach Debounce prüfen: `data-testid="save-indicator"` enthält `error`-Zustand und nicht-leeren Fehlertext.

**AC-5:** Given der Nutzer macht eine Änderung im Trip-Editor (Debounce läuft noch) / When er sofort auf einen Link zu einem anderen Trip oder Tab navigiert / Then wird der noch ausstehende Save vor der Navigation ausgeführt (Flush), und die Änderung ist nach Reload der Zielseite erhalten.
  - Test: Playwright gegen Staging — Etappen-Name ändern, sofort (< 500 ms) auf einen anderen Navigations-Link klicken; nach Abschluss der Navigation zurücknavigieren und prüfen: geänderter Name ist im Trip-Objekt persistiert (API GET /api/trips/{id} liefert neuen Namen).

**AC-6:** Given beide Editoren (Trip-Editor und Compare-Editor) sind zu unterschiedlichen Zeitpunkten geöffnet / When ein Save im Trip-Editor fehlschlägt (Indikator = error) / Then ist der Compare-Editor-Indikator davon unberührt (zeigt weiterhin seinen eigenen Zustand) — kein geteilter globaler State.
  - Test: Playwright gegen Staging — zwei Tabs öffnen oder sequenziell prüfen: Fehler-State in Trip-Editor (via Route-Intercept) setzt Compare-Indikator nicht auf error; beide `data-testid="save-indicator"`-Instanzen zeigen unabhängige Zustände.

**AC-7:** Given der Trip-Editor-Tab „Briefing" oder „Metriken" ist geöffnet / When der Nutzer eine Kanal-Einstellung oder eine Metrik-Auswahl ändert / Then zeigt `TripHeader`-Indikator kurz „Speichere …" und wechselt zu „Gespeichert ✓" — kein expliziter „Speichern"-Button ist mehr sichtbar in diesen Tabs.
  - Test: Playwright gegen Staging — `BriefingScheduleTab` und `WeatherMetricsTab` jeweils prüfen: kein Element mit `data-testid` des alten Speichern-Buttons vorhanden; Änderung triggern und Save-Indikator-State prüfen wie AC-1.

## Known Limitations

- Debounce-Flush via `beforeNavigate` setzt voraus, dass die Navigation über SvelteKit-Links läuft; Browser-Back-Button oder externer Link flushen nicht (Risiko: sehr selten, da Nutzer normalerweise SvelteKit-Navigation verwendet).
- Bei sehr schlechter Verbindung (`saving`-Zustand lange) kann der Nutzer erneut tippen — der neue Debounce cancelt den laufenden Timer, aber der laufende API-Call läuft noch. Race: letzter Call gewinnt (Backend Read-Modify-Write, kein Datenverlust, aber ggf. zwei Calls kurz hintereinander).
- `compareWizardState.isDirty` wird derzeit nicht persistent gespeichert — nach Browser-Refresh ist Dirty-State weg (unkritisch: Zustand liegt ja im Backend, `idle` nach Reload ist korrekt).

## Changelog

- 2026-06-12: Initial spec erstellt — Issue #758
