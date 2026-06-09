# Epic 677: Compare-Editor — Tab-Basierte Oberfläche

**Status:** In Progress (Slice 3/6 Complete — 2026-06-09)  
**Epic Scope:** Umbau der Orts-Vergleich-Schnittstelle von 5-Schritt-Wizard zu Tab-Editor (analog zu Trip-Editor #616/#622)  
**Related Specs:**
- `docs/specs/modules/issue_678_compare_editor_shell.md` (Slice 1 — Gerüst + Lock-Engine + Tab 1)
- `docs/specs/modules/issue_679_compare_editor_edit.md` (Slice 2 — Edit-Modus + Dirty/Save-Flow)
- `docs/specs/modules/issue_680_compare_editor_slice3.md` (Slice 3 — Fidelity Tabs „Orte" + „Idealwerte")

**Child Issues:** #678 ✓, #679 ✓, #680 ✓ (Slices 1–3 complete)

---

## Overview

Epic #677 ersetzt die linearen 5-Schritt-Wizards des Orts-Vergleichs durch einen **Tab-Editor mit Progressive-Lock-Logik**:

- **Create-Modus** (`/compare/new`): Tab-by-Tab schrittweise aufbaubar, Tabs schalten frei basierend auf Validierung
- **Edit-Modus** (`/compare/[id]/edit`): Alle Tabs sofort freigeschaltet, Dirty/Save-Flow mit Bestätigungs-Dialogen
- **Progressive Lock:** Tabs sind gesperrt bis vorherige vollständig validiert; abgerundete Iconographie (aktiv/erledigt/gesperrt)
- **Kein Funktionsverlust:** Bestehende Step-Komponenten (Step2Orte bis Step5Versand) mounten in Tabs, Logik unverändert

**Nutzerfall:** Weitwanderer kann Vergleich-Presets jederzeit anlegen (Create) oder später anpassen (Edit), ohne starre 5-Schritte durchklicken zu müssen.

---

## Slices (2026-06-09 onwards)

### Slice 1: Gerüst + Lock-Engine + Tab 1 (Issue #678 ✓)

**Status:** ✓ Completed 2026-06-09

- **New Component:** `CompareEditor.svelte` — Shell mit Tab-Bar + Fortschrittsbalken + Progressive-Lock-Logik
- **New Module:** `compareEditorLogic.ts` — `unlockedTabs()`, `doneTabs()`, Validierungschain
- **Create-Flow:** `/compare/new` nutzt `CompareEditor mode="create"`; Tab 1 „Vergleich" vollständig; Tabs 2–5 mit Step-Komponenten gemountet (gesperrt)
- **Edit-Flow:** Vorbereitungen; noch keine Live-Route
- **LoC:** ~230

**Key Decisions:**

- Tab-Montage via `{#if currentTab === n} <StepX /> {/if}` — keine volle Refaktorierung
- Lock-Zustände aus Frontend-State (nicht Backend) — ermöglicht Prototypen-Navigation im Create-Modus
- Fortschrittsbalken nur in Create-Modus (kein Progress im Edit)
- Hero-Eyebrow ändert sich je Mode: „Neuer Vergleich" (Create) vs. „Orts-Vergleich bearbeiten" (Edit)

### Slice 2: Edit-Modus + Dirty/Save-Flow (Issue #679 ✓)

**Status:** ✓ Completed 2026-06-09

- **Route Aktiviert:** `/compare/[id]/edit` nutzt `CompareEditor mode="edit"`
- **Dirty-Tracking:** lokaler `dirty`-State; markDirty() bei jeder Feldänderung
- **UI Ergänzungen:**
  - Breadcrumb: „Orts-Vergleiche / [Vergleichsname]"
  - Status-Dot + Label: grün „aktiv" oder grau „pausiert" (basierend auf `schedule`)
  - „Ungespeichert"-Pill (nur wenn `dirty === true`)
  - Buttons: „Verwerfen" + „Speichern"
  - Kein Fortschrittsbalken
- **Save-Fix:** Korrekter Endpoint `/api/compare/presets/{id}` (statt kaputtem `/api/subscriptions`)
- **Datenverlust-Schutz:** Round-Trip-Spread bewahrt unveränderte Felder (v.a. `empfaenger`)
- **LoC:** ~120

**Altlasten behoben:**

1. **#644 F1:** `state.save()` traf falschen Store (`/api/subscriptions/{id}` → 404) — jetzt `/api/compare/presets/{id}`
2. **#644 F2:** Empfänger wurden beim Speichern gelöscht — jetzt vollständiger Preset-Spread

### Slice 3: Fidelity Tabs „Orte" + „Idealwerte" (Issue #680 ✓)

**Status:** ✓ Completed 2026-06-09

- **Step2Orte.svelte:** Nummerierte Picked-Liste mit Entfernen-Button, Region-gruppierte Bibliothek (Checkbox-Buttons), Counter mit Warn-Hinweis
- **Step3Idealwerte.svelte:** Vollständig verdrahtet — Dual-Handle-Slider für Range-Metriken, Segmented-Control für Enum-Metriken, hinzufügen/entfernen von Metriken, Persistenz in `display_config.active_metrics`
- **New Component:** `RangeSlider.svelte` — reine UI-Komponente mit Pointer-Events, Tastatur-Navigation, ARIA-Labels
- **Neue Katalog-Module:** `ALL_METRICS`, `deriveIdealText()` in compareMetricDefs.ts
- **State Erweiterung:** `activeMetricKeys`, `metricsManuallyEdited` in compareWizardState.svelte.ts
- **LoC:** ~550
- **Key Decision:** PO-Direktive „optisch angedeutet aber nicht funktional ist nicht akzeptiert" — alle Funktionen vollständig verdrahtet (Slider-Drag, Add/Remove-Metrik, Persistenz)

### Slice 4: Validierungsmeldungen (planned)

Fehlermeldungen für Grenzwert-Verletzungen, Min > Max, etc.  Warnsystem für unplausible Idealwertbereiche.

### Slice 5: Mobile (planned)

Responsive Tab-Editor für kleine Viewports (<900px).

### Slice 6: Cleanup (planned)

Entfernung von `CompareWizard.svelte` nach Vollständigkeit aller Slices. Finalisierung Tab-Editor-Umstieg.

---

## Architecture

### Component Hierarchy

```
frontend/src/routes/compare/
├── new/
│   └── +page.svelte
│       └── <CompareEditor mode="create" />
│
└── [id]/
    └── edit/
        └── +page.svelte
            └── <CompareEditor mode="edit" preset={data.preset} />

frontend/src/lib/components/compare/
├── CompareEditor.svelte (Gerüst, Tabs, Dirty-Tracking)
├── compareWizardState.svelte.ts (State-Container + save() Fix)
├── compareEditorLogic.ts (unlockedTabs(), doneTabs(), Validierung)
├── compareEditorSave.ts (buildComparePresetSavePayload — Round-Trip)
│
├── steps/ (unverändert, gemountet in Tabs)
│   ├── Step1Vergleich.svelte
│   ├── Step2Orte.svelte
│   ├── Step3Idealwerte.svelte
│   ├── Step4Layout.svelte
│   └── Step5Versand.svelte
│
└── CompareWizard.svelte (Legacy — wird in Slice 6 gelöscht)
```

### State Management

**File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`

```typescript
// Editor-State
name: string;                               // Step 1
region: string;
activityProfile: ActivityProfile;
pickedIds: string[];                        // Step 2
// ... weitere Felder aus Steps 3–5

// Edit-Mode State
dirty: boolean = $state(false);             // Neu für Edit
mode: 'create' | 'edit';                    // Neu

// Methoden
markDirty(): void;                          // Neu
save(preset?: ComparePreset): Promise;      // Updated — korrekter Endpoint
reset(): void;
```

### Dirty/Save-Flow (Edit-Modus)

```
User öffnet /compare/[id]/edit
  ↓
CompareEditor mount mit mode="edit" + preset={data.preset}
  ↓
State initialized aus preset (name, region, pickedIds, etc.)
  ↓
[User ändert Feld] → markDirty() → dirty = true
  ↓
Breadcrumb zeigt „Ungespeichert"-Pill
  ↓
[User klickt „Speichern"]
  → buildComparePresetSavePayload({ ...preset, ...changedFields })
  → PUT /api/compare/presets/{id}
  → dirty = false
  → Navigate zu /compare/[id]
  ↓
[User klickt „Verwerfen"]
  → ConfirmDialog öffnen
  → [User bestätigt]
  → Navigate zu /compare/[id]
```

### Data Flow (Round-Trip-Spread)

**BEFORE (kaputt):**
```typescript
// Loader lädt: { name, region, activity_profile, picked_location_ids, empfaenger, schedule, ... }
// Edit ändert: Name, Region, Profil, Ortsliste
// Save baut: { name_neu, region_neu, activity_profile_neu, picked_location_ids_neu }
// Result: empfaenger GELÖSCHT (nicht im Payload), schedule GELÖSCHT
```

**AFTER (korrekt):**
```typescript
// Loader lädt: const preset = { name, region, activity_profile, picked_location_ids, empfaenger, schedule, ... }
// Edit ändert: Name, Region, Profil, Ortsliste
// Save baut:
//   { ...preset,           // vollständiger Spread ALLER Felder aus dem Loader
//     name: editName,      // überschreibe nur geänderte Felder
//     region: editRegion,
//     activity_profile: editProfile,
//     picked_location_ids: editIds }
// Result: empfaenger ERHALTEN, schedule ERHALTEN, alle server-managed Felder ERHALTEN
```

---

## Implementation Details (Slice 2)

### Files Modified

| File | Change | LoC |
|------|--------|-----|
| `CompareEditor.svelte` | Add isEdit-Zweig: Breadcrumb, Status-Dot, Dirty-Pills, Save/Discard-Buttons, kein Progress | +60 |
| `compareWizardState.svelte.ts` | Add markDirty(), fix save() endpoint + payload, add mode field | +25 |
| `compare/[id]/edit/+page.svelte` | Mount CompareEditor mode="edit" statt CompareWizard | +35 |
| `compareEditorSave.ts` | NEW: buildComparePresetSavePayload — Round-Trip-Spread | +40 |
| **Total** | | **~160** |

### Key Fixes

**1. Endpoint-Fix (compareWizardState.ts)**

```typescript
// BEFORE (kaputt)
await api.put(`/api/subscriptions/${id}`, payload);  // 404: kein Endpoint hier

// AFTER (korrekt)
await api.put(`/api/compare/presets/${id}`, payload);
```

**2. Round-Trip-Spread (compareEditorSave.ts)**

```typescript
export function buildComparePresetSavePayload(
  currentState: CompareWizardState,
  loadedPreset: ComparePreset
): Partial<ComparePreset> {
  return {
    ...loadedPreset,                       // START mit vollständigem Preset
    name: currentState.name,               // ÜBERSCHREIBE nur geänderte Felder
    region: currentState.region,
    activity_profile: currentState.activityProfile,
    picked_location_ids: currentState.pickedIds,
    // schedule, empfaenger, hour_from, etc. kommen aus loadedPreset → nicht gelöscht
  };
}
```

**3. Dirty-Tracking**

```typescript
let dirty = $state(false);

function markDirty() {
  dirty = true;
}

// In Tabs: jede on:change → markDirty()
<input on:change={(e) => { state.name = e.target.value; markDirty(); }} />
```

---

## Acceptance Criteria (Slice 2)

All 6 AC from spec Issue #679:

- **AC-1:** Alle 5 Tabs sofort anklickbar in Edit-Modus, kein Fortschrittsbalken ✓
- **AC-2:** Dirty-Pill erscheint nach Feldänderung, verschwindet nach Reload ohne Änderung ✓
- **AC-3:** Änderung persistent nach Speichern (user_id correct, empfaenger erhalten) ✓
- **AC-4:** Verwerfen verwirft Änderung, zeigt Confirm-Dialog ✓
- **AC-5:** Keine Cross-User-Interferenz (403/404 bei fremdem Preset) ✓
- **AC-6 (optional):** Status-Dot zeigt aktiv/pausiert je schedule ✓

---

## Limitations & Out of Scope

### Slice 2 Out of Scope

- Step 5 (Versand) Änderungen speichern — Round-Trip bewahrt bestehende Einstellungen, Änderungen folgen später
- Mobile-Optimierungen (Slice 5)
- `CompareWizard.svelte` Deletion (Slice 6)

### Known Issues Resolved

| Issue | Problem | Solution |
|-------|---------|----------|
| #644 F1 | Speichern traf `/api/subscriptions/{id}` (404) | Endpoint auf `/api/compare/presets/{id}` korrigiert |
| #644 F2 | Empfänger wurden beim Speichern gelöscht | Round-Trip-Spread bewahrt `empfaenger` |

---

## Deployment & Testing

### Staging Validation (Post-Push)

1. Navigate to `/compare/new` — Create-Editor lädt, alle Tabs gesperrt außer Tab 1 ✓
2. Navigate to bestehender Preset-ID `/compare/[id]/edit` — Edit-Editor lädt, alle 5 Tabs sofort freigeschaltet ✓
3. Ändere Name → „Ungespeichert"-Pill erscheint ✓
4. Klicke „Speichern" → PUT an `/api/compare/presets/{id}` erfolgreich, Redirect zu `/compare/[id]` ✓
5. Reload Edit-Seite → neue Name-Wert im Input-Feld sichtbar ✓
6. DB-Check: `data/users/<user_id>/compare_presets.json` enthält neue Name, `empfaenger` unverändert ✓

### E2E Tests (Playwright)

- Load `/compare/[id]/edit` als Nutzer A, ändere Name, speichere
- Reload Edit-Page, verifiziere neue Name
- GET `/api/compare/presets/{id}` (als Nutzer A), vergleiche `empfaenger`-Feld mit Vorher-Wert (identisch)
- Verwerfen: Ändere Name, klicke „Verwerfen", bestätige Dialog
- Reload Edit-Page, verifiziere Originalname (Änderung nicht gespeichert)

### Production Rollout

No special migration needed — pure frontend + endpoint routing fix. Legacy `CompareWizard` still available until Slice 6. No data loss risk (Round-Trip ensures preservation).

---

## Design System

**Components (existing, reused):**
- `Btn` — Save/Discard/Back buttons
- `Input` — Text fields
- `GCard` — Tab containers
- `Eyebrow` + `Pill` — Breadcrumb labels
- `ConfirmDialog` — Save/Discard confirmation

**Design Tokens:**
- `--g-accent` — Primary action (Save button)
- `--g-warning` — Status-Dot (pause/active states)
- `--g-ink` — Text and labels

---

## Changelog

| Date | Slice | Change |
|------|-------|--------|
| 2026-06-09 | 3 | Fidelity Tabs „Orte" + „Idealwerte": nummerierte Picked-Liste + Region-Gruppierung, Dual-Handle-Slider, Segmented-Control, Add/Remove-Metrik, Persistenz display_config.active_metrics. RangeSlider.svelte neu. ALL_METRICS Katalog. Issue #680 ✓ |
| 2026-06-09 | 2 | Edit-Modus implementiert, Dirty/Save-Flow, Endpoint-Fix #644, Round-Trip-Spread. Issue #679 ✓ |
| 2026-06-09 | 1 | Compare-Editor Gerüst + Lock-Engine + Tab 1 (Vergleich). Issue #678 ✓ |

---

## Future Work

- **Slice 4:** Validierungsmeldungen (Min > Max, Grenzwert-Verletzungen)
- **Slice 5:** Mobile-Responsive Editor
- **Slice 6:** CompareWizard-Deletion, Full Tab-Editor-Umstieg
- **Follow-ups:** Step 5 (Versand) Edit-Support, Voransicht vor Speichern, Template-Library, Metrik-Sortierung (Drag)

