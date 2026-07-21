---
entity_id: issue_679_compare_editor_edit
type: module
created: 2026-06-09
updated: 2026-06-09
status: implemented
version: "1.0"
tags: [frontend, compare, editor, edit-mode, dirty-tracking, datenloss-protection]
---

# Compare-Editor — Edit-Modus + Dirty/Save-Flow (Slice 2/6, Epic #677)

## Approval

- [x] Approved (Implemented 2026-06-09)

## Purpose

Schaltet die `/compare/[id]/edit`-Route vom alten Schritt-für-Schritt-`CompareWizard` auf den
neuen Tab-Editor (`CompareEditor mode="edit"`) um und implementiert den vollständigen
Dirty/Save-Flow (Dirty-Tracking, „Ungespeichert"-Pill, Speichern/Verwerfen, Status-Dot).
Löst zwei kritische Altlasten: (1) `state.save()` traf `/api/subscriptions/{id}` statt
`/api/compare/presets/{id}` — dadurch war das Speichern effektiv kaputt (404, #644-Kernursache);
(2) beim Speichern wurden Empfänger gelöscht, weil der Loader `empfaenger` nicht lädt und das
Backend keinen Merge dafür macht — behoben durch vollständigen Preset-Spread beim PUT.

## Source

- **File (geändert):** `frontend/src/lib/components/compare/CompareEditor.svelte`
- **File (geändert):** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
- **File (geändert):** `frontend/src/routes/compare/[id]/edit/+page.svelte`
- **Identifier:** `CompareEditor` (isEdit-Zweig), `compareWizardState.save()`, `EditPage`

> Schicht: **Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).
> Kein Backend-Change — `PUT /api/compare/presets/{id}` ist korrekt und unverändert.

## Design-Quelle (bindend)

`claude-code-handoff/handoff-2026-06-04-v3/claude-code-handoff/current/jsx/screen-compare-editor.jsx`
Z. 583–699: `isEdit`-Zweig mit `dirty`/`markDirty`, Breadcrumb `Orts-Vergleiche / [Name]`,
Status-Dot (aktiv/pausiert), „Ungespeichert"-Pill, Buttons „Verwerfen"/"Speichern".

## Estimated Scope

- **LoC:** ~120 (Editor isEdit-Zweig ~60, State save-Fix ~25, Edit-Page ~35)
- **Files:** 3 (alle geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareEditor.svelte` (Slice 1, #678) | upstream | Gerüst + Tab-Bar + Lock-Engine; isEdit-aware (`open = isEdit \|\| unlocked.has(...)`) |
| `compareWizardState.svelte.ts` | changed | State-Container; `save()` erhält korrekten Endpunkt + Round-Trip-Spread |
| `PUT /api/compare/presets/{id}` (`internal/handler/compare_preset.go:166`) | reuse | RMW-Merge, mandantengetrennt via `UserIDFromContext`; bleibt unverändert |
| `CompareTabs.svelte:175` | reference | Kanonisches Preset-PUT-Muster: `api.put('/api/compare/presets/{id}', {...preset, ...})` |
| `ConfirmDialog` | reuse | Bestätigung beim Verwerfen von ungespeicherten Änderungen |
| Step2Orte / Step3Idealwerte / Step4Layout / Step5Versand | reuse | Werden in Tabs 2–5 vom Editor gemountet; unverändert |
| `/compare/[id]/edit/+page.server.ts` | reuse | Loader lädt Preset via `GET /api/compare/presets/{id}`; bleibt unverändert |

## Implementation Details

```
1. CompareEditor.svelte — isEdit-Zweig

   Props erweitern:
     { mode: 'create'|'edit', locations, preset?: ComparePreset }
     (preset = volles Preset-Objekt aus dem Loader, für Round-Trip-Spread)

   Neuer lokaler State:
     dirty = $state(false)
     markDirty(): dirty = true  (wird bei jeder Feldänderung aufgerufen)

   Dirty-Propagation:
     Alle Felder (Name, Region, Profil, Orte-Auswahl, Idealwerte, Layout, Versand)
     rufen markDirty() auf — per on:change-Handler oder reaktiv über $effect.

   Breadcrumb im Edit-Modus:
     Zeile: „Orts-Vergleiche / [Vergleichsname]"  (nicht „Neuer Vergleich")
     Rechts:
       - „Ungespeichert"-Pill  (nur wenn dirty === true)
       - Status-Dot + Label:
           schedule === 'manual'  → grauer Punkt + „pausiert"
           sonst                  → grüner Punkt + „aktiv"
       - Button „Verwerfen" (ghost) → öffnet ConfirmDialog
       - Button „Speichern" (primary/accent) → ruft save() auf

   Fortschrittsbalken CE_Progress:
     KEIN Render wenn mode === 'edit' (nur Create nutzt CE_Progress).

   Tab-Lock:
     Bereits vorhanden: open = isEdit || unlocked.has(tab)
     → alle 5 Tabs sofort anklickbar, keine Änderung nötig.

   Hero-Eyebrow:
     mode === 'edit'  → „Orts-Vergleich bearbeiten"
     mode === 'create' → unverändert

   Nach erfolgreichem Speichern:
     dirty = false
     Navigation zur Detail-Seite /compare/[id]

   Verwerfen (ConfirmDialog bestätigt):
     Änderungen verworfen (State reset oder Seite neu laden)
     Navigation zur Detail-Seite /compare/[id]

2. compareWizardState.svelte.ts — save() Fix

   VORHER (kaputt):
     api.put(`/api/subscriptions/${id}`, payload)   // falscher Store, 404

   NACHHER:
     api.put(`/api/compare/presets/${id}`, {
       ...preset,          // vollständiger Round-Trip des geladenen Preset-Objekts
       name:   state.name,
       region: state.region,
       activity_profile: state.activityProfile,
       picked_location_ids: state.pickedIds,
       // schedule/hour_from/hour_to/weekday/empfaenger/previous_schedule
       // kommen aus dem Preset-Spread → werden NICHT neu abgeleitet
     })

   Schlüsselregel Round-Trip-Spread:
     Das volle `preset`-Objekt (aus dem Loader, an save() übergeben) wird als Basis
     genutzt. Nur explizit geänderte Felder werden überschrieben. Damit überleben:
       - empfaenger (nicht vom Editor bearbeitet → nicht gelöscht)
       - schedule, hour_from, hour_to, weekday
       - previous_schedule, archived_at, display_config (server-managed)
     Das folgt exakt dem Muster in CompareTabs.svelte:175.

   schedule-Mismatch:
     State-interne Repräsentation (daily_morning|daily_evening|weekly) wird im
     Edit-Save NICHT in das ComparePreset-Format umgerechnet. Die geladenen Werte
     (schedule, hour_from, hour_to, weekday) kommen unverändert aus dem Preset-Spread.
     Step5-Versand-Änderungen im Edit-Modus sind Out of Scope für diesen Slice.

3. /compare/[id]/edit/+page.svelte

   VORHER: <CompareWizard .../>

   NACHHER:
     <CompareEditor
       mode="edit"
       locations={data.locations}
       preset={data.preset}
     />

   State-Initialisierung:
     compareWizardState aus data.preset.* befüllen (wie bisher):
       name = data.preset.name
       region = data.preset.region
       activityProfile = data.preset.activity_profile
       pickedIds = data.preset.picked_location_ids

   Zusätzlich: das volle `data.preset`-Objekt an CompareEditor/State-save() weiterreichen,
   damit der Round-Trip-Spread alle nicht editierten Felder erhalten kann.
```

## Expected Behavior

- **Input:** Authentifizierter Nutzer öffnet `/compare/[id]/edit`; Preset existiert unter
  `data/users/<user_id>/compare_presets.json`.
- **Output:** Editor zeigt alle 5 Tabs sofort freigeschaltet, Breadcrumb mit Preset-Name,
  Status-Dot, kein Fortschrittsbalken. Nach Speichern ist die Änderung in der JSON-Datei
  persistent, bestehende Empfänger unverändert, Nutzer auf Detail-Seite.
- **Side effects:** Schreibt via `PUT /api/compare/presets/{id}` in
  `data/users/<user_id>/compare_presets.json`. Kein Cross-User-Schreiben (Backend:
  `s.WithUser(UserIDFromContext)`).

## Acceptance Criteria

- **AC-1:** Given ein bestehender Vergleich unter `/compare/[id]/edit`, When die Seite geöffnet
  wird, Then sind alle 5 Tabs (Vergleich · Orte · Idealwerte · Layout · Versand) sofort
  anklickbar und es gibt keinen Fortschrittsbalken im Viewport.
  - Test: Playwright @ Staging, eingeloggter Nutzer — alle 5 Tab-Buttons klickbar, kein
    Fortschrittsbalken-Element im DOM sichtbar.

- **AC-2:** Given die Edit-Seite geöffnet und ein Feld geändert (z. B. Name), When die
  Breadcrumb-Zeile betrachtet wird, Then ist die „Ungespeichert"-Pill sichtbar und der Button
  „Speichern" aktiv; vor jeder Änderung ist die Pill nicht sichtbar.
  - Test: Playwright — Name-Feld ändern, Pill-Element erscheint im DOM; Reload ohne Änderung,
    Pill fehlt.

- **AC-3:** Given eine Änderung vorgenommen und „Speichern" geklickt (echter PUT als Nutzer A),
  When die Detail-Seite nach Redirect geladen und anschließend `/compare/[id]/edit` erneut
  geöffnet wird, Then ist die Änderung persistent sichtbar, das Preset liegt unter
  `data/users/<A>/compare_presets.json` (nicht `data/users/default/`), und bestehende
  Empfänger des Presets sind unverändert erhalten.
  - Test: Playwright — Name ändern + Speichern, Reload Edit-Seite, neuer Name im Feld; DB-Check
    per GET `/api/compare/presets/{id}` (als Nutzer A), Feld `empfaenger` mit Vorher-Wert
    vergleichen.

- **AC-4:** Given eine Änderung vorgenommen und „Verwerfen" geklickt, When der ConfirmDialog
  bestätigt wird, Then wird zur Detail-Seite `/compare/[id]` navigiert und die Änderung ist
  nicht gespeichert (Reload zeigt alten Wert).
  - Test: Playwright — Name ändern, Verwerfen bestätigen, URL ist `/compare/[id]`, Edit-Seite
    reload zeigt Original-Name.

- **AC-5:** Given zwei Nutzer A und B mit je eigenem Preset, When Nutzer B `/compare/[id-A]/edit`
  aufruft, Then antwortet die Seite mit 403/404 (nicht mit Nutzer-A-Daten), und Nutzer A kann
  sein Preset weiterhin speichern ohne Interferenz durch B.
  - Test: Playwright mit 2 Nutzer-Sessions — Cross-User-Zugriff liefert Fehlerseite;
    paralleles Speichern von A und B ändert nur die eigene `compare_presets.json`.

- **AC-6 (optional, Status-Dot):** Given ein Vergleich mit `schedule === 'manual'` (pausiert),
  When `/compare/[id]/edit` geöffnet wird, Then zeigt die Breadcrumb-Zeile einen grauen Punkt
  mit Label „pausiert"; bei einem Vergleich mit `schedule !== 'manual'` einen grünen Punkt
  mit Label „aktiv".
  - Test: Playwright — pausierter Vergleich (schedule=manual) öffnen, grauer Dot + „pausiert"
    im DOM; aktiver Vergleich (schedule=daily), grüner Dot + „aktiv".

## Known Limitations

- Step5-Versand-Änderungen (schedule, hour_from, hour_to, weekday) im Edit-Modus sind in
  diesem Slice Out of Scope: der Round-Trip-Spread bewahrt bestehende Versandeinstellungen,
  aber Änderungen daran werden nicht gespeichert. Vollständiger Versand-Edit folgt in einem
  späteren Slice (Fidelity-Feinschliff, #680 ff.).
- `CompareWizard.svelte` wird in diesem Slice nicht gelöscht — Entfernung erfolgt in Slice 6
  wenn der Editor alle Pfade trägt.
- Mobile-Edit-Modus ist Out of Scope (Slice 5 / `CEM_`-Komponenten).

## Out of Scope (dieser Slice)

- Fidelity-Feinschliff der Tab-Inhalte Orte/Idealwerte/Layout (Slices 3–4)
- Mobile-Editor (Slice 5)
- Löschen von `CompareWizard.svelte` (Slice 6)
- Step5-Versand ändern und speichern (Folge-Slice)

## Changelog

- 2026-06-09: Implemented (Slice 2/6, Epic #677, löst #644) — CompareEditor isEdit-Zweig, compareWizardState.save() Fix, compareEditorSave.ts Round-Trip, /compare/[id]/edit Route aktiviert. All 6 AC fulfilled. Issues #678 + #679 complete.
