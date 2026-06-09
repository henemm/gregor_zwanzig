---
entity_id: issue_678_compare_editor_shell
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [frontend, compare, editor, design-compliance]
---

# Compare-Editor — Gerüst + Lock-Engine + Tab „Vergleich" (Slice 1/6, Epic #677)

## Approval

- [x] Approved (PO 'go' 2026-06-09)

## Purpose

Ersetzt die Schritt-für-Schritt-Wizard-Shell des Orts-Vergleichs durch **einen** Editor mit
fünf Tabs (Vergleich · Orte · Idealwerte · Layout · Versand) — analog zum Trip-Editor (#622/#616).
Dieser Slice liefert das **Gerüst** (Tab-Bar + Fortschrittsbalken + Breadcrumb/Hero), die **reine
Progressive-Lock-Logik** (welche Tabs sind freigeschaltet / erledigt) und den voll funktionsfähigen
**Tab „Vergleich"** (Name · Region · Aktivitätsprofil) im Create-Modus unter `/compare/new`.
Tabs 2–5 mounten vorerst die bestehenden, funktionierenden Step-Komponenten in gesperrten Panels
(kein Funktionsverlust). Edit-Modus, Fidelity-Feinschliff und Mobile folgen in Slices 2–5.

## Source

- **File (neu):** `frontend/src/lib/components/compare/CompareEditor.svelte`
- **File (neu):** `frontend/src/lib/components/compare/compareEditorLogic.ts`
- **File (geändert):** `frontend/src/routes/compare/new/+page.svelte`
- **Identifier:** `CompareEditor`, `unlockedTabs()`, `doneTabs()`

> Schicht: **Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).

## Design-Quelle (bindend)

`claude-code-handoff/current/jsx/screen-compare-editor.jsx` — `ScreenCompareEditor`, `CE_TabBar`,
`CE_Progress`, `CE_unlocked`, `CE_doneSet`, `CE_VergleichTab`. Spec: `body-25-compare-editor.md`.

## Estimated Scope

- **LoC:** ~230 (Shell ~120, Logik ~40, Tab-Vergleich ~55, Route ~15)
- **Files:** 3 (2 neu, 1 geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareWizardState` | reuse | State-Container (Name/Region/Profil/pickedIds …) wird vom Editor weitergenutzt |
| `Step2Orte…Step5Versand` | reuse | werden in Tabs 2–5 als gesperrte Panels gemountet (kein Funktionsverlust) |
| `ACTIVITY_PROFILE_OPTIONS` (`$lib/types`) | reuse | bestehende App-Profile (Slice hält Bestandsprofile, **nicht** die 5 Design-Profile) |
| atoms `Btn/Eyebrow/TopoBg`, molecules `Field` | reuse | Bausteine |

## Implementation Details

```
compareEditorLogic.ts (pure, DOM-frei, unit-testbar):
  TAB_ORDER = ['vergleich','orte','idealwerte','layout','versand']
  unlockedTabs({name, pickedCount, idealsVisited, layoutVisited}) -> Set
     vergleich immer; orte wenn name.trim(); idealwerte wenn pickedCount>=2;
     layout wenn idealsVisited; versand wenn layoutVisited
  doneTabs({name, pickedCount, idealsVisited, layoutVisited, versandVisited}) -> Set
     vergleich wenn name.trim(); orte wenn pickedCount>=2; idealwerte wenn idealsVisited;
     layout wenn layoutVisited; versand wenn versandVisited

CompareEditor.svelte:
  Props: { mode: 'create'|'edit', locations }  (Slice 1 nutzt nur 'create')
  liest CompareWizardState aus Context
  visited-Flags (idealsVisited/layoutVisited/versandVisited) lokal als $state
  switchTab(id): im create-Modus nur wenn unlocked; setzt visited-Flag des Ziels
  Render: Breadcrumb (Orts-Vergleiche / Neuer Vergleich), Hero mit Live-Name +
          CE_Progress (5 Segmente, "N / 5 Abschnitte eingerichtet"), Tab-Bar (Lock-Hint
          + ✓/⊘), Tab-Panel. Gesperrter Tab-Klick: kein Wechsel + Lock-Hint sichtbar.
  Tab 'vergleich': Name(max 80)/Region(max 60)/Profil-Kacheln + "Orte hinzufügen →"
  Tabs 'orte'/'idealwerte'/'layout'/'versand': bestehende Step-Komponenten

/compare/new/+page.svelte: CompareWizardState instanziieren (Factory, wie bisher),
  setContext, <CompareEditor mode="create" locations={data.locations} />
```

## Expected Behavior

- **Input:** Nutzer öffnet `/compare/new`, tippt Name, wählt Profil, klickt „Orte hinzufügen →".
- **Output:** Tab-Bar schaltet „Orte" frei, „Vergleich" wird ✓; aktiver Tab wechselt auf „Orte".
- **Side effects:** keine Persistenz in diesem Slice (nur UI-State im bestehenden Container).

## Acceptance Criteria

- **AC-1:** Given `/compare/new` frisch geöffnet (kein Name), When der Nutzer auf den Tab „Orte"
  klickt, Then bleibt der aktive Tab „Vergleich" und „Orte" zeigt den Lock-Zustand (⊘ / Lock-Hint).
  - Test: Playwright @ Staging eingeloggt — Klick auf gesperrten Tab, aktiver Tab unverändert.
- **AC-2:** Given ein nicht-leerer Name eingegeben, When die Tab-Bar betrachtet wird, Then ist „Orte"
  anklickbar/freigeschaltet und „Vergleich" trägt das ✓-Done-Kennzeichen.
  - Test: Playwright — Name tippen, Tab „Orte" klickbar, Wechsel erfolgt.
- **AC-3:** Given Create-Modus, When der Hero betrachtet wird, Then zeigt der Fortschrittsbalken
  5 Segmente und den Text „N / 5 Abschnitte eingerichtet" (N steigt mit erledigten Tabs).
  - Test: Playwright — vor Eingabe „0 / 5"/„Noch nichts", nach Name „1 / 5".
- **AC-4:** Given die Profil-Kacheln, When eine Kachel geklickt wird, Then ist genau diese Kachel
  aktiv markiert (Accent) und der Wert bleibt nach Tab-Wechsel erhalten.
  - Test: Playwright — Profil wählen, Tab wechseln und zurück, Auswahl persistiert.
- **AC-5:** Given Name gesetzt, When „Orte hinzufügen →" geklickt wird, Then wechselt der aktive Tab
  auf „Orte" (gemountete bestehende Orte-Auswahl sichtbar).
  - Test: Playwright — Button-Klick führt zu sichtbarem Orte-Panel.

## Out of Scope (dieser Slice)

- Edit-Modus + Dirty/Save (Slice 2 / #679)
- 1:1-Fidelity-Feinschliff der Tab-Inhalte Orte/Idealwerte/Layout/Versand (Slices 3–4)
- Mobile-Editor `CEM_` (Slice 5)
- Adoption der 5 Design-Profile statt der 4 Bestandsprofile (separat / Backend-Abstimmung)
- Löschen von `CompareWizard.svelte` (Slice 6, wenn Editor alle Pfade trägt)
