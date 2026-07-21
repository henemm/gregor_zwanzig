---
entity_id: issue_588_location_new
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [locations, modal, frontend, svelte, issue-588, atomic-design, smart-import]
---

# Issue #588 — Neuer-Ort-Modal: NewLocationWizard durch 1:1-JSX-Modal ersetzen

## Approval

- [ ] Approved

## Zweck

`LocationNewModal.svelte` ersetzt den bestehenden 3-Schritt-Stepper-Wizard (`NewLocationWizard.svelte`) durch ein vollflächiges Modal-Overlay, das exakt dem SOLL-Template `claude-code-handoff/current/jsx/screen-location-new.jsx` entspricht. Das neue Modal rendert sein eigenes Overlay ohne Shadcn-Dialog-Wrapper, zeigt alle drei Eingabe-Sektionen (Verortung/Smart-Import, Benennung, Meteorologische Brille) auf einmal und folgt dem Design-System-Kontrast-Prinzip: weiße Card auf abgedunkeltem Hintergrund.

## Quelle / Source

**Layer:** Frontend / User-UI (`frontend/src/`)

**Neue Datei:**
- `frontend/src/lib/components/compare/LocationNewModal.svelte` — Hauptkomponente

**Geänderte Dateien:**
- `frontend/src/routes/locations/+page.svelte` — Shadcn-Dialog-Create-Block durch `<LocationNewModal>` ersetzen
- `frontend/src/routes/locations/__tests__/issue_408_location_wizard.test.ts` — Tests auf neue Komponente anpassen

**Nicht ändern:**
- `frontend/src/lib/components/compare/NewLocationWizard.svelte` (wird abgelöst, aber nicht gelöscht — bleibt ggf. für `/compare`-Route)
- Go-API und Python-Backend werden nicht angefasst

> **Schicht-Hinweis:** Ausschließlich Frontend (`frontend/src/`). Go-API und Python-Backend werden nicht angefasst.

## Estimated Scope

- **LoC:** ~350–450 (neue Komponente ~320, Seiten-Änderung ~15, Test-Anpassung ~30)
- **Files:** 3
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/Eyebrow.svelte` | Atom | Modul-Bezeichner im Modal-Header |
| `frontend/src/lib/components/atoms/Pill.svelte` | Atom | `tone="good"` Erkennungs-Badge neben Smart-Import-Input |
| `frontend/src/lib/components/atoms/KV.svelte` | Atom | Key-Value-Zeilen in der Vorschau-Card (Quelle, Koordinaten, Höhe, Zeitzone, Daten-Quelle, Land/Region) |
| `frontend/src/lib/components/atoms/Card.svelte` | Atom | Container für Vorschau-KV-Grid und Aktivitätsprofil-Karten |
| `frontend/src/lib/components/atoms/Btn.svelte` | Atom | Footer-Buttons „Abbrechen" (variant=ghost) und „Ort speichern" (variant=primary) |
| `frontend/src/lib/components/atoms/TopoBg.svelte` | Atom | Mini-Map-Placeholder rechts im Vorschau-Grid |
| `$lib/types` — `ACTIVITY_PROFILE_OPTIONS`, `ActivityProfile` | Types | Alle 4 Aktivitätsprofile für Sektion 3 |
| `POST /api/locations/resolve` | Go-API-Endpoint | Smart-Import-Auflösung — liefert Quelle, Koordinaten, Höhe, Zeitzone, Land/Region |
| `POST /api/locations` | Go-API-Endpoint | Ort speichern nach Formular-Abschluss |
| `frontend/src/routes/locations/+page.svelte` | Svelte-Route | Einbindung des neuen Modals statt Shadcn-Dialog |
| `claude-code-handoff/current/jsx/screen-location-new.jsx` | JSX-Template | Bindende SOLL-Vorlage für Struktur, CSS-Werte, Sektions-Layout |
| `claude-code-handoff/current/jsx/tokens.css` | Design-Tokens | Alle `var(--g-*)` Token-Werte; kein rohes Hex/px erlaubt |
| `claude-code-handoff/current/soll/M-location-new.png` | Screenshot-Referenz | Visuelles SOLL für fresh-eyes-inspector Mode-2-Vergleich |

## Implementation Details

### 1. Overlay-Struktur (kein Shadcn-Dialog-Wrapper)

Das Modal rendert sein eigenes Overlay als `position: fixed; inset: 0; z-index: var(--g-z-modal)`.
Drei Ebenen:

```svelte
<!-- Äußerer Fullscreen-Container -->
<div style="position:fixed; inset:0; z-index:var(--g-z-modal);">
  <!-- Ebene 1: Hintergrund (abgedunkelt, verschwommen) -->
  <div style="position:absolute; inset:0; opacity:0.35; filter:blur(2px); pointer-events:none;">
    <!-- Placeholder oder TopoBg -->
  </div>

  <!-- Ebene 2: Dunkle Overlay-Schicht -->
  <div style="position:absolute; inset:0; background:rgba(26,26,24,0.45);"></div>

  <!-- Ebene 3: Modal-Card -->
  <div style="
    position:absolute;
    top:60px;
    left:50%;
    transform:translateX(-50%);
    width:720px;
    border-radius:var(--g-r-4);
    box-shadow:var(--g-shadow-3);
    background:var(--g-card);
  ">
    <!-- Header, Sektionen, Footer -->
  </div>
</div>
```

### 2. Svelte-Snippets für JSX-Helper-Funktionen

Die JSX-Hilfsfunktionen werden als Svelte-`{#snippet}`-Blöcke implementiert:

- `{#snippet LocSectionTag(nr)}` — nummerierter Kreis (24px, Akzent-Hintergrund, weiße Ziffer)
- `{#snippet LocFormatChip(label, active)}` — klickbarer Chip mit `tone="active"`-Rand wenn aktiv
- `{#snippet LocPseudoInput(value, placeholder)}` — Texteingabe mit Link-Icon links, optionalem Pill rechts
- `{#snippet LocProfileCard(profile, isActive)}` — Aktivitätsprofil-Karte mit Akzent-Border + Akzent-Tint bei `isActive`

### 3. State-Variablen

```ts
let resolvedPreview: ResolvedLocation | null = $state(null);
let importInput: string = $state('');
let activeFormat: string = $state('komoot');  // einer der 6 Format-Chips
let nameInput: string = $state('');
let groupInput: string = $state('');
let activeProfile: ActivityProfile = $state('wandern');
let resolving: boolean = $state(false);
let saving: boolean = $state(false);
```

### 4. Smart-Import — POST /api/locations/resolve

```ts
async function resolveImport() {
  if (!importInput.trim()) return;
  resolving = true;
  try {
    const res = await api.post('/api/locations/resolve', { url: importInput });
    resolvedPreview = res;
  } catch (e) {
    resolvedPreview = null;
  } finally {
    resolving = false;
  }
}
```

Trigger: `oninput` debounced (300ms) oder `onblur`.

### 5. Ort speichern — POST /api/locations

```ts
async function saveLocation() {
  if (!nameInput.trim()) return;
  saving = true;
  try {
    await api.post('/api/locations', {
      name: nameInput,
      group: groupInput || null,
      activity_profile: activeProfile,
      ...(resolvedPreview ?? {}),
    });
    onsave();
  } catch (e) {
    // Fehlermeldung im Footer anzeigen
  } finally {
    saving = false;
  }
}
```

### 6. Header

```svelte
<header>
  {@render Eyebrow('Modul 1 · Location anlegen')}
  <h2 style="font-size:22px; font-weight:600;">Neuer Ort</h2>
  <p style="font-size:13px; color:var(--g-ink-3);">
    Gib eine URL oder Koordinaten ein — der Smart-Import erkennt das Format automatisch.
  </p>
  <button onclick={oncancel} aria-label="Schließen">×</button>
</header>
```

### 7. Sektion 1 — Verortung · Smart-Import

- `{@render LocSectionTag(1)}` + Sektions-Titel
- `{@render LocPseudoInput(importInput, 'Komoot-URL, Google-Maps-Link oder Koordinaten …')}` mit Pill wenn `resolvedPreview` gesetzt
- 6 Format-Chips: Komoot-URL, Google Maps, DMS-Koordinaten, Dezimal, UTM, GPX-Wegpunkt
- 2-Spalten-Grid:
  - Links: `<Card>` mit `<KV>` Einträgen (Quelle, Koordinaten, Höhe, Zeitzone, Daten-Quelle, Land/Region) aus `resolvedPreview` oder leer
  - Rechts: `<TopoBg>` mit Marker-Dot bei vorhandener Koordinate

### 8. Sektion 2 — Benennung

- `{@render LocSectionTag(2)}`
- 2-Spalten-Grid `grid-template-columns: 2fr 1fr`:
  - Name-Input (required, aria-label "Name des Ortes")
  - Gruppe-Input mit Hint-Text "Tippen für neue Gruppe"

### 9. Sektion 3 — Meteorologische Brille

- `{@render LocSectionTag(3)}`
- Beschreibungstext (12px, `var(--g-ink-3)`)
- 3-Spalten-Grid: alle 4 Einträge aus `ACTIVITY_PROFILE_OPTIONS` als `{@render LocProfileCard(p, activeProfile === p.value)}`
  - Aktive Karte: `border: 2px solid var(--g-accent); background: var(--g-accent-tint)`
  - Inaktive Karte: `border: 1px solid var(--g-rule-soft); background: var(--g-card)`

### 10. Footer

```svelte
<footer style="background:var(--g-card-alt); border-top:1px solid var(--g-rule-soft);">
  <label>
    <input type="checkbox" />
    Nach Speichern als Compare-Kandidat vormerken
  </label>
  <div>
    <Btn variant="ghost" onclick={oncancel}>Abbrechen</Btn>
    <Btn variant="primary" onclick={saveLocation} disabled={!nameInput.trim() || saving}>
      Ort speichern
    </Btn>
  </div>
</footer>
```

### 11. Einbindung in +page.svelte

Den Shadcn-Dialog-Block für `dialogMode === 'create'` ersetzen:

```svelte
import LocationNewModal from '$lib/components/compare/LocationNewModal.svelte';

{#if showNewModal}
  <LocationNewModal
    onsave={() => { showNewModal = false; refetchLocations(); }}
    oncancel={() => { showNewModal = false; }}
  />
{/if}
```

`showNewModal` ersetzt den alten `dialogMode === 'create'`-Zweig. Der Edit-Pfad (`LocationForm`) bleibt unverändert.

### 12. LoC-Budget

| Datei | Δ LoC |
|---|---|
| `LocationNewModal.svelte` (neu) | ~350 |
| `+page.svelte` (Modal einbinden, Dialog-Block ersetzen) | ~15 |
| `issue_408_location_wizard.test.ts` (Tests anpassen) | ~30 |
| **Gesamt** | **~395 LoC** |

Über 250-LoC-Standard-Limit → `workflow.py set-field loc_limit_override 500` vor dem Implementieren.

## Expected Behavior

- **Input:** Nutzer klickt „Neuer Ort" auf `/locations`; optionale URL/Koordinaten-Eingabe; Name; Aktivitätsprofil-Auswahl
- **Output:** Vollflächiges Modal-Overlay öffnet sich. Nach erfolgreichem Speichern: Modal schließt, Locations-Liste aktualisiert sich.
- **Side effects:** `POST /api/locations/resolve` wird bei Eingabe im Smart-Import-Feld gefeuert. `POST /api/locations` wird beim Klick auf „Ort speichern" gefeuert. `oncancel`/`onsave`-Callback steuert Sichtbarkeit in der Parent-Route.

## Acceptance Criteria

**AC-1:** Given der User klickt „Neuer Ort" auf der Locations-Seite, When das Modal öffnet, Then erscheint ein vollflächiger, abgedunkelter Hintergrund mit einem zentrierten 720px-weißen Modal-Card — kein Shadcn-Dialog-Wrapper ist im DOM vorhanden.

- Test: (populated after /tdd-red)

**AC-2:** Given das Modal ist offen, When der User eine Komoot-URL in das Smart-Import-Feld eingibt, Then wird `POST /api/locations/resolve` aufgerufen und das Vorschau-Grid (KV-Einträge: Quelle, Koordinaten, Höhe, Zeitzone, Daten-Quelle, Land/Region) wird mit den Auflösungs-Ergebnissen befüllt.

- Test: (populated after /tdd-red)

**AC-3:** Given der User hat einen Namen eingetragen und auf „Ort speichern" geklickt, When die Anfrage erfolgreich ist, Then wird `POST /api/locations` aufgerufen und das Modal schließt sich (onsave-Callback wird gefeuert).

- Test: (populated after /tdd-red)

**AC-4:** Given das Modal ist offen, When der User auf „Abbrechen" oder den ×-Button klickt, Then schließt sich das Modal ohne Änderungen (oncancel-Callback wird gefeuert, kein API-Call).

- Test: (populated after /tdd-red)

**AC-5:** Given das Modal ist offen, When der User eine Aktivitätsprofil-Karte anklickt, Then wird diese Karte als aktiv markiert (Akzent-Border + Akzent-Tint-Hintergrund) und alle anderen Karten wechseln in den inaktiven Zustand.

- Test: (populated after /tdd-red)

**AC-6:** Given die Komponente wird gerendert, When ein Playwright-Screenshot @ 1440px erstellt wird, Then besteht der `fresh-eyes-inspector` Mode-2-Vergleich gegen `claude-code-handoff/current/soll/M-location-new.png` mit PASS.

- Test: (populated after /tdd-red)

## Known Limitations

- **Mini-Map ist Placeholder:** Die rechte Spalte im Vorschau-Grid zeigt `<TopoBg>` mit Marker-Dot — keine echte interaktive Karte. Echte Karten-Integration ist Out of Scope für dieses Issue.
- **Gruppen-Freitext:** Das Gruppe-Input ist ein freies Textfeld; es gibt keine Autocomplete-API für bestehende Gruppen. Hinweis-Text „Tippen für neue Gruppe" macht dies transparent.
- **Compare-Kandidat-Checkbox:** Die Checkbox im Footer ist ein visueller Placeholder; das Backend-Handling für „Als Compare-Kandidat vormerken" ist Out of Scope für dieses Issue.
- **Shadcn-Dialog-Abhängigkeit entfällt:** `+page.svelte` nutzt nach dieser Änderung keinen Shadcn-Dialog-Wrapper mehr für den Create-Pfad — der Edit-Pfad (`LocationForm`) bleibt weiterhin im Shadcn-Dialog.

## Out of Scope

- Änderungen an `NewLocationWizard.svelte` (bleibt erhalten für `/compare`-Route)
- Echte Karten-Integration in den Mini-Map-Placeholder
- Compare-Kandidat-Backend-Logik
- Gruppen-Autocomplete-API
- Go-API- oder Python-Backend-Änderungen

## Changelog

- 2026-06-04: Initial spec erstellt. Beschreibt Ersatz des 3-Schritt-Wizards durch 1:1-JSX-Modal `LocationNewModal.svelte`; 3 Dateien, ~395 LoC, 6 Acceptance Criteria mit AC-6 fresh-eyes-Vergleich.
