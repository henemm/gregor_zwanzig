---
entity_id: epic_136_step3_waypoints
type: module
created: 2026-05-09
updated: 2026-05-10
status: draft
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issue: 163
tags: [sveltekit, frontend, wizard, step3, waypoints, ai, epic-136]
---

# Epic 136 — Sub-Spec #163: Step 3 Wegpunkt-Vorschlaege bestaetigen

## Begriffsklaerung

Die Wegpunkte stammen aus deterministischer Heuristik — Wetterscheiden-Erkennung
(`detect_waypoints` in `src/core/elevation_analysis.py`) und Segment-Optimierung
(`optimize_segments` in `src/core/hybrid_segmentation.py`). Keine KI/ML/LLM.
Sub-Spec verwendet daher konsistent **„Wegpunkt-Vorschlaege"** /
**„automatische Vorschlaege"** statt „KI-Waypoints". Das transiente Flag
`Waypoint.suggested` ist neutral benannt und bleibt unveraendert.

## Approval

- [x] Approved (2026-05-11)

## Status

**Approved** — Phase 5 (TDD RED) kann starten.

## Purpose

Definiert das UI-Detail von Schritt 3 des Trip-Wizards (`Step3Waypoints.svelte`,
`ProfileChart.svelte`, `WaypointRow.svelte`): links eine Etappen-Liste zur Auswahl
der aktiven Etappe, rechts eine Confirm-UI mit SVG-Hoehenprofil (gestrichelte
Vorschlags-Pins) und Waypoint-Liste (Bestaetigen/Verwerfen pro Wegpunkt).

Step 3 schreibt ausschliesslich in `WizardState.stages[i].waypoints` — keine API-Calls,
kein Map-Rendering, keine Persistenz. Das `suggested`-Flag (markiert
„automatischer Vorschlag, noch nicht bestaetigt") wird von `WizardState.addStage()`
zentral gesetzt (Variante A, User-Entscheidung 2026-05-10); Step 3 liest es und mutiert
es via `confirmWaypoint` / `rejectWaypoint`. Der Weiter-Button ist immer enabled
(`canAdvanceStep3 = true`): alle noch als `suggested` markierten Waypoints gelten beim
Save implizit als akzeptiert, weil `toTripPayload()` das Flag sowieso strippt.

## Source

- **Komponente (EDIT, Stub fuellen):** `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte`
- **State-Erweiterung (EDIT):** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **E2E-Tests (NEU):** `frontend/e2e/trip-wizard-step3.spec.ts`
- **Identifier:** `Step3Waypoints` (default export), `ProfileChart` (default export),
  `WaypointRow` (default export), `WizardState.canAdvanceStep3`,
  `WizardState.confirmWaypoint`, `WizardState.rejectWaypoint`

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret
konsumiert sie:

- **§3.4 Waypoint.suggested** — transientes Frontend-Flag (`boolean | undefined`),
  wird in `toTripPayload()` gestrippt (`stripSuggested`, `wizardState.svelte.ts`
  Z. 263–266). Sub-Spec **setzt** das Flag via `addStage`-Patch in jedem
  eingehenden Waypoint.
- **§1.4 Save-Pipeline / `stripSuggested`** — bestehend; Step 3 ergaenzt keine
  neue Strip-Logik, sondern verlaesst sich auf die bestehende.
- **§3.1 `canAdvanceCurrent`-Pattern** — Sub-Spec ergaenzt `canAdvanceStep3`-Getter
  und case 3 im Switch.
- **§4 Vertraege Master-Spec — Sub-Specs** — Erweiterung erfolgt mit
  Master-Spec-Changelog-Eintrag (§12 dieser Spec).

Vorgaenger-Sub-Specs:
- [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) (#161, `canAdvanceStepN` + `fillStepN`-Pattern)
- [`epic_136_step2_stages.md`](./epic_136_step2_stages.md) (#162, Layout-Pattern, TestID-Konvention)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` (Master-Spec §3.1) | class | Single Source of Truth fuer Stages + Waypoints |
| `wizardState.svelte.ts` | file (edit) | `addStage`-Patch, 2 neue Methoden, 1 neuer Getter, Switch-Update |
| `wizardHelpers.ts` | file | `isPauseStage`, `formatStageNumber`, `newId` |
| `frontend/src/lib/types.ts` | file (lesen) | `Stage`, `Waypoint`, `Waypoint.suggested?` — unveraendert |
| `$lib/components/ui/btn/Btn.svelte` | component (Epic #133) | Bestaetigen/Verwerfen-Buttons, Weiter-Button |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | Container links + rechts |
| `$lib/components/ui/pill/Pill.svelte` | component (Epic #133) | T01-Anzeige in linker Etappen-Liste |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Abschnitts-Eyebrows |
| `@lucide/svelte` (icons `map-pin`, `check`, `x`) | NPM | Pin-Indikator, Bestaetigen-, Verwerfen-Icons |
| `--g-warning` CSS-Token | CSS | `#c8882a` — Farbe fuer gestrichelte Vorschlags-Pins (`app.css:48`) |
| `--g-ink-strong` CSS-Token | CSS | Farbe fuer bestaetigte Pins (solid) |
| `--g-ink-faint` CSS-Token | CSS | Pause-Stage-Text, Borders |
| `frontend/e2e/helpers.ts` | file (edit) | `fillStep3`-Helper |
| `frontend/e2e/trip-wizard-shell.spec.ts` | file (edit) | AC#5a, AC#8, AC#11 ergaenzen `fillStep3` |

## Implementation Details

### §1 Layout-Wireframe

```
┌────────────────────────────────────────────────────────────────────────┐
│ Eyebrow: „Etappen"                     Eyebrow: „Wegpunkte"            │
│                                                                        │
│ ┌──────────────────────┐  ┌─────────────────────────────────────────┐  │
│ │ [T01] 2026-06-01     │  │ [ProfileChart SVG ~360x120px]           │  │
│ │ Stubai-Etappe-1  ◀   │  │  ○──○--○--○──○  (Polyline + Pins)      │  │
│ │                      │  │  ↑           ↑                          │  │
│ │ [T02] 2026-06-02     │  │  solid       gestrichelt (Vorschlag)    │  │
│ │ Stubai-Etappe-2      │  ├─────────────────────────────────────────┤  │
│ │                      │  │ WaypointRow: ○ Gipfelkreuz    2345m     │  │
│ │ [  ] Pausentag       │  │             10:30             [✓] [x]   │  │
│ │ (nicht klickbar)     │  │ WaypointRow: ○ Kuhsee          1890m    │  │
│ │                      │  │ (suggested)   11:15            [✓] [x]  │  │
│ │ [T03] 2026-06-04     │  │                                         │  │
│ │ Stubai-Etappe-3      │  │ (aktive Stage hat 0 Waypoints:)         │  │
│ │                      │  │  „Keine Waypoints mehr."                │  │
│ └──────────────────────┘  └─────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

Aeusserer Container: `flex flex-row gap-6`. Linke Spalte: fixe Breite ~200px, rechts:
`flex-1`. Beide in `<GCard>`. Bei Viewport < md: Stack (linke Liste oben, Detail unten
— Mobile-Optimierung ist not-in-scope, wird aber nicht aktiv gebrochen).

### §2 Datenmodell-Erweiterung

Keine Aenderung an `types.ts`. `Waypoint.suggested?: boolean` ist bereits vorhanden
(Master-Spec §3.4, `frontend/src/lib/types.ts`). `Stage.dateOverridden?: boolean`
ist aus Sub-Spec #162 vorhanden. Step 3 beruehrt keine Typ-Definitionen.

### §3 WizardState-Erweiterungen

Alle Aenderungen sind additiv. Das bestehende `canAdvanceCurrent`-Switch
(Z. 105–116) hat bereits `case 3: return true` — es wird durch den neuen Getter
abgesichert, aber der Switch-Case selbst ist bereits korrekt.

#### §3.1 `addStage`-Patch — `suggested: true` zentral setzen

`WizardState.addStage()` (Z. 134–139) wird erweitert: alle Waypoints der
eingehenden Stage erhalten `suggested: true`, sofern sie noch kein explizites
`suggested`-Flag tragen.

```typescript
addStage(stage: Stage): void {
  const stageWithId: Stage = stage.id ? stage : { ...stage, id: newId() };
  // Sub-Spec #163 §3.1: Waypoints aus GPX-Upload als automatische Vorschlaege
  // markieren. Zentralisiert (Variante A, User-Entscheidung 2026-05-10) statt
  // Mount-Hook in Step 3 — funktioniert auch fuer zukuenftige Pfade
  // (#165 Vorlagen).
  const withSuggested: Stage = {
    ...stageWithId,
    waypoints: stageWithId.waypoints.map((wp) =>
      wp.suggested !== undefined ? wp : { ...wp, suggested: true }
    )
  };
  this.stages = [...this.stages, withSuggested];
}
```

Konsequenz fuer bestehende Tests: Jeder `addStage`-Test, der Waypoints ohne
`suggested`-Flag hinzufuegt und danach `wp.suggested` prueft, muss erwaarten,
dass es `true` ist. Neue Test-Cases decken das ab (§3.4 dieser Spec).

#### §3.2 `confirmWaypoint(stageId: string, waypointId: string): void` (NEU)

Entfernt `suggested`-Flag aus einem Wegpunkt — der Wegpunkt gilt danach als
bestaetigt. Mutiert `this.stages` (neue Referenz fuer Svelte-5-Reaktivitaet).

```typescript
confirmWaypoint(stageId: string, waypointId: string): void {
  this.stages = this.stages.map((stage) => {
    if (stage.id !== stageId) return stage;
    return {
      ...stage,
      waypoints: stage.waypoints.map((wp) => {
        if (wp.id !== waypointId) return wp;
        const { suggested: _ignored, ...rest } = wp;
        return rest;
      })
    };
  });
}
```

#### §3.3 `rejectWaypoint(stageId: string, waypointId: string): void` (NEU)

Entfernt den Wegpunkt vollstaendig aus `stage.waypoints`.

```typescript
rejectWaypoint(stageId: string, waypointId: string): void {
  this.stages = this.stages.map((stage) => {
    if (stage.id !== stageId) return stage;
    return {
      ...stage,
      waypoints: stage.waypoints.filter((wp) => wp.id !== waypointId)
    };
  });
}
```

#### §3.4 `canAdvanceStep3`-Getter (NEU)

```typescript
get canAdvanceStep3(): boolean {
  return true;  // User-Entscheidung 2026-05-10: kein Mindest-Bestaetigung erzwingen
}
```

Begruendung: `stripSuggested` in `toTripPayload` entfernt das Flag sowieso — alle
noch unbestaetigt verbliebenen Waypoints werden beim Save automatisch ohne Flag
persistiert, d.h. faktisch akzeptiert. Explizites Verwerfen ist die einzige
Aktion mit fachlicher Konsequenz.

#### §3.5 `canAdvanceCurrent`-Switch-Update

Case 3 wird von `return true` auf `return this.canAdvanceStep3` umgestellt.
Der Wert ist aktuell identisch, aber der Getter macht die Semantik explizit und
ermoeglicht spaetere Aenderung ohne Switch-Refactor.

```typescript
get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return this.canAdvanceStep3;
    case 4: return true;
  }
}
```

### §4 Linke Etappen-Liste (`Step3Waypoints.svelte`)

Gerendert analog zur linken Seite in Step 2: T-Pills (`formatStageNumber`),
Pause-Marker fuer Pausentage, Datum als Subtext.

Unterschiede zu Step 2:
- **Kein Drag-Handle, kein Delete-Button, kein Date-Override** — die Liste ist
  in Step 3 read-only bezueglich Reihenfolge und Datierung.
- **Pausentage sind sichtbar** (User sieht den vollstaendigen Trip), aber **nicht
  klickbar** — `pointer-events: none` + `opacity: 0.5`.
- **Aktive Etappe** (`activeStageId`) wird visuell hervorgehoben (z.B. `bg-[var(--g-surface-raised)]`).
- Klick auf eine Nicht-Pause-Stage setzt `activeStageId`.

Lokaler State in `Step3Waypoints.svelte`:

```typescript
let activeStageId = $state<string>(
  state.stages.find((s) => !isPauseStage(s))?.id ?? ''
);
```

Init: erste Nicht-Pause-Stage. Falls keine Nicht-Pause-Stage existiert: leerer
String, rechte Seite zeigt Edge-Case (§8b).

### §5 `ProfileChart.svelte` (NEU)

SVG ~360×120px mit Padding 8px allseits (innere Zeichenflaeche ~344×104px).
Zeigt das Hoehenprofil der aktiven Etappe (`stage.waypoints[].elevation_m`).

**Polyline:** x-Position proportional zum Wegpunkt-Index
`x = padding + (i / (N - 1)) * innerWidth` (bei N >= 2; bei N === 1: einzelner
Punkt mittig). y-Position elevation-skaliert:
`y = padding + (1 - (elev - minElev) / (maxElev - minElev)) * innerHeight`
(invertiert: hohe Werte oben). Wenn `maxElev === minElev`: alle Punkte auf `y = padding + innerHeight / 2`.

**Pins (circles):** pro Wegpunkt ein `<circle r="5">` an `(x, y)`.
- `suggested === true`: `stroke="var(--g-warning)" stroke-dasharray="3,3" fill="white" stroke-width="2"`
- bestaetigt (kein `suggested`): `stroke="var(--g-ink-strong)" fill="var(--g-ink-strong)" stroke-width="0"`

**ARIA:** `<svg aria-label={`Hoehenprofil mit ${N} Wegpunkten`} role="img">`.
Keine interaktiven Elemente in dieser Sub-Spec — Klick auf Pin selektiert keine
Liste-Row (nice-to-have, Folge-Issue).

**Props:**

```typescript
interface Props {
  stage: Stage;
  width?: number;  // default 360
  height?: number; // default 120
}
let { stage, width = 360, height = 120 }: Props = $props();
```

Kein `data-testid` auf einzelnen Pins — SVG-interne Elemente schwer per Playwright
selektierbar; E2E verifiziert via aria-label des SVG-Containers.

### §6 `WaypointRow.svelte` (NEU)

Row-Komponente fuer einen einzelnen Wegpunkt in der rechten Confirm-UI.

**Props:**

```typescript
interface Props {
  waypoint: Waypoint;
  onConfirm: () => void;
  onReject: () => void;
}
let { waypoint, onConfirm, onReject }: Props = $props();
```

**Layout (horizontal, `flex items-center gap-3`):**
1. Pin-Indikator: kleiner `<circle>` (inline SVG 14×14px) — gleiche Style-Logik
   wie in `ProfileChart` (`suggested`: orange dashed, bestaetigt: solid ink-strong).
   ARIA: `aria-label={waypoint.suggested ? 'Vorschlag (unbestaetigt)' : 'Bestaetigt'}`.
2. Wegpunkt-Name (`waypoint.name`), Klasse `flex-1 truncate`.
3. Hoehe: `waypoint.elevation_m ? `${waypoint.elevation_m} m` : ''`, Klasse `text-sm text-[var(--g-ink-faint)]`.
4. Zeit: `waypoint.time_window ?? ''`, Klasse `text-sm text-[var(--g-ink-faint)]`.
5. Bestaetigen-Button: `<Btn variant="primary" size="sm">` mit Lucide `Check`-Icon.
   Nur sichtbar wenn `waypoint.suggested === true`. ARIA: `aria-label="Vorschlag bestaetigen"`.
6. Verwerfen-Button: `<Btn variant="ghost" size="sm">` mit Lucide `X`-Icon.
   Immer sichtbar. ARIA: `aria-label="Wegpunkt verwerfen"`.

### §7 Selektions-Logik

`activeStageId` ist `$state` in `Step3Waypoints.svelte` (nicht in `WizardState` —
rein UI-lokaler State).

- **Init:** erste Stage aus `state.stages`, die kein Pausentag ist.
- **Klick links:** `activeStageId = stage.id` (nur bei Nicht-Pause-Stage).
- **Nach Reject:** wenn alle Waypoints der aktiven Stage verworfen wurden,
  bleibt `activeStageId` unveraendert. Die rechte Seite zeigt dann den
  Empty-State „Keine Wegpunkte mehr — alle verworfen." (§8c). Kein
  Auto-Advance auf naechste Stage.
- **Pausentag geklickt:** Event wird ignoriert (`onclick={null}` oder
  `pointer-events-none`-CSS). Kein State-Wechsel.

Aktive Stage in der Liste: `border-[var(--g-accent)]` oder
`bg-[var(--g-surface-raised)]` (genaues CSS in Implementation-Phase entscheiden —
Spec gibt nur semantische Anforderung: aktive Stage ist visuell unterscheidbar).

### §8 Empty- und Edge-Cases

| Case | Bedingung | Anzeige |
|------|-----------|---------|
| a | `state.stages.length === 0` | Rechte Seite + Liste: „Bitte zuerst in Schritt 2 GPX-Dateien hochladen." Weiter-Button enabled (canAdvanceStep3 = true). |
| b | Alle Stages sind Pausentage | Rechte Seite: „Trip enthaelt nur Pausentage — keine Wegpunkte." |
| c | Aktive Stage hat 0 Waypoints (alle verworfen) | Rechte Seite: „Keine Wegpunkte mehr — alle verworfen." `ProfileChart` zeigt leere Zeichenflaeche (Polyline ohne Punkte). |
| d | Aktive Stage hat Waypoints ohne `elevation_m` | `ProfileChart` zeigt alle Punkte auf Mittellinie (y = padding + innerHeight / 2). |
| e | N === 1 Waypoint | `ProfileChart` zeigt einzelnen Pin mittig horizontal. Keine Polyline-Linie (nur der Punkt). |

### §9 TestID-Inventar

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-step3-container` | `Step3Waypoints.svelte` (Root) | Schritt-3-Sichtbarkeit |
| `trip-wizard-step3-stages-list` | Linke Etappen-Liste | Etappen-Auswahl |
| `trip-wizard-step3-stage-row-{i}` | Stage-Row links | Klick selektiert aktive Stage |
| `trip-wizard-step3-stage-pill-{i}` | T-Pill links | T01/T02-Anzeige |
| `trip-wizard-step3-pause-marker-{i}` | Pause-Label links | "Pausentag" (nicht klickbar) |
| `trip-wizard-step3-profile-chart` | `ProfileChart.svelte` | SVG-Container |
| `trip-wizard-step3-waypoints-list` | Waypoint-Liste rechts | Liste der Waypoints |
| `trip-wizard-step3-waypoint-row-{i}` | `WaypointRow.svelte` | Einzelner Wegpunkt |
| `trip-wizard-step3-confirm-{i}` | Bestaetigen-Button pro Row | Confirm-Aktion |
| `trip-wizard-step3-reject-{i}` | Verwerfen-Button pro Row | Reject-Aktion |
| `trip-wizard-step3-empty-no-stages` | Empty-State (§8a) | Kein Etappen-Hinweis |
| `trip-wizard-step3-empty-only-pauses` | Empty-State (§8b) | Nur-Pausentage-Hinweis |
| `trip-wizard-step3-empty-no-waypoints` | Empty-State (§8c) | Alle-verworfen-Hinweis |

### §10 E2E-Helper `fillStep3`

Datei: `frontend/e2e/helpers.ts`

```typescript
export interface Step3Input {
  confirmAll?: boolean;       // default false — alle bleiben suggested
  rejectByName?: string[];    // Wegpunkt-Namen, die verworfen werden sollen
}

export async function fillStep3(page: Page, input: Step3Input = {}): Promise<void> {
  await page.getByTestId('trip-wizard-step3-container').waitFor({ state: 'visible' });

  if (input.confirmAll) {
    const confirmBtns = page.getByTestId(/^trip-wizard-step3-confirm-/);
    const count = await confirmBtns.count();
    for (let i = 0; i < count; i++) {
      await confirmBtns.nth(i).click();
    }
  }

  if (input.rejectByName && input.rejectByName.length > 0) {
    for (const name of input.rejectByName) {
      const row = page.locator('[data-testid^="trip-wizard-step3-waypoint-row-"]',
        { hasText: name });
      const idx = await row.getAttribute('data-waypoint-index');
      if (idx) {
        await page.getByTestId(`trip-wizard-step3-reject-${idx}`).click();
      }
    }
  }

  // Default: keine Aktion — alle Waypoints bleiben suggested (canAdvanceStep3 = true)
  await page.getByTestId('trip-wizard-next').click();
  // Warten bis Step 4 sichtbar. Heute traegt Step 4 die TestID
  // `trip-wizard-step4-briefings`; sobald Sub-Issue #164 (Step 4 Save-Pipeline)
  // gemerged ist, sollte das auf `trip-wizard-step4-container` umbenannt werden,
  // analog Step 3.
  await page.getByTestId('trip-wizard-step4-briefings').waitFor({ state: 'visible' });
}
```

Default-Verhalten: kein Confirm, kein Reject — klickt nur Weiter. Da
`canAdvanceStep3 = true` immer, braucht der Helper keinen Enabled-Check vor dem
Weiter-Klick. `confirmAll` und `rejectByName` sind optional fuer gezielte
Szenarien in Step-3-eigenen Tests.

### §11 Migration `trip-wizard-shell.spec.ts`

Tests AC#5a, AC#8, AC#11 navigieren durch alle Steps bis Step 4. Nach dem
Step-2-`fillStep2`-Aufruf muss `fillStep3(page)` eingebaut werden, damit
Step 3 uebersprungen wird und der Test in Step 4 landet.

Beispiel AC#5a (Auszug):

```typescript
await fillStep1(page, DEFAULT_STEP1);
await page.getByTestId('trip-wizard-next').click();  // → Step 2
await fillStep2(page);
await page.getByTestId('trip-wizard-next').click();  // → Step 3
await fillStep3(page);                               // → Step 4
// Heute: trip-wizard-step4-briefings (Step 4 Container-TestID kommt mit #164)
await expect(page.getByTestId('trip-wizard-step4-briefings')).toBeVisible();
```

Hinweis: `fillStep3` klickt intern schon Weiter — kein zusaetzlicher `next.click()`
nach `fillStep3` erforderlich.

Betroffene Tests: AC#5a (Weiter-Button-Kette), AC#8 (alle Step-Container sichtbar),
AC#11 (Full-Navigation bis Step 4). Tests die nur Step 1+2 pruefen: keine Aenderung.

### §12 Master-Spec-Changelog-Eintrag

`docs/specs/modules/epic_136_trip_wizard.md` erhaelt einen neuen Changelog-Eintrag
(kein Approval-Reset, weil rein additive Erweiterungen):

```markdown
- 2026-05-10: §3.1 erweitert um additive Methoden/Getter (Sub-Spec #163):
  `addStage()`-Patch: alle Waypoints der eingehenden Stage erhalten `suggested: true`
  (Variante A, zentralisiert). `confirmWaypoint(stageId, waypointId)` — entfernt
  `suggested`-Flag. `rejectWaypoint(stageId, waypointId)` — entfernt Wegpunkt aus
  `stage.waypoints`. `get canAdvanceStep3(): boolean` (immer true — keine
  Mindest-Bestaetigung). `canAdvanceCurrent` case 3 zeigt auf `canAdvanceStep3`
  statt literal `true`. Detail in Sub-Spec
  [`epic_136_step3_waypoints.md`](./epic_136_step3_waypoints.md).
```

## Expected Behavior

- **Input:** User in Step 3, nachdem Step 2 mindestens eine Etappe mit Waypoints
  angelegt hat. Waypoints tragen `suggested: true` (gesetzt von `addStage`-Patch).
- **Output:**
  - Linke Liste zeigt alle Stages (Nicht-Pause klickbar, Pause grayed-out).
  - Rechts: `ProfileChart` rendert Hoehenprofil der aktiven Stage mit
    orange-gestrichelten Pins fuer Vorschlaege (`suggested === true`), solid
    Pins fuer bestaetigte Wegpunkte.
  - Waypoint-Liste zeigt alle Waypoints der aktiven Stage mit Name, Hoehe, Zeit,
    Bestaetigen/Verwerfen-Buttons.
  - Klick Bestaetigen: `confirmWaypoint` entfernt `suggested`, Pin wird solid.
  - Klick Verwerfen: `rejectWaypoint` entfernt Waypoint aus Array, Row
    verschwindet, ProfileChart-Pin verschwindet.
  - Klick Weiter: immer enabled, navigiert zu Step 4.
- **Side effects:**
  - `WizardState.stages[i].waypoints` wird mutiert (neue Array-Referenzen
    fuer Svelte-5-Reaktivitaet).
  - Kein API-Call in Step 3.
  - Kein Persistenz-Write vor Step 4.
  - `activeStageId` (lokaler State) wird bei Stage-Klick links aktualisiert.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `Step3Waypoints.svelte` rendert Container mit TestID `trip-wizard-step3-container` | E2E |
| 2 | Linke Liste zeigt alle Stages inkl. Pausentage | E2E (nach fillStep2 mit 1 Etappe + 1 Pause: 2 Rows links) |
| 3 | Pausentage in linker Liste haben TestID `trip-wizard-step3-pause-marker-{i}` und sind nicht klickbar | E2E (click → activeStageId unveraendert) |
| 4 | Klick auf Nicht-Pause-Stage setzt diese Stage als aktiv (visuell hervorgehoben) | E2E (Klick + CSS-Check via `evaluate` oder aria-attribute) |
| 5 | Init: erste Nicht-Pause-Stage ist aktiv ohne Klick | E2E (kein Klick, erste Stage rechts sichtbar) |
| 6 | Rechte Seite rendert `ProfileChart` mit aria-label „Hoehenprofil mit N Wegpunkten" | E2E |
| 7 | `ProfileChart` zeigt gestrichelte Pins fuer `suggested: true`-Waypoints | E2E via SVG-Attribut-Check (`evaluate` auf `stroke-dasharray`) |
| 8 | `ProfileChart` zeigt solid Pins fuer bestaetigte Waypoints | E2E (nach confirmWaypoint: Pin-Attribut solid) |
| 9 | Waypoint-Liste rendert Rows mit TestID `trip-wizard-step3-waypoint-row-{i}` | E2E |
| 10 | Jede Row zeigt Wegpunkt-Name, Hoehe (falls vorhanden), Zeit (falls vorhanden) | E2E (Text-Content-Check) |
| 11 | Bestaetigen-Button nur sichtbar wenn `waypoint.suggested === true` | E2E (bestaetiger Waypoint: Button hidden) |
| 12 | Klick Bestaetigen: Pin wird solid, Bestaetigen-Button verschwindet | E2E |
| 13 | Klick Verwerfen: Waypoint-Row verschwindet, ProfileChart-Pins-Anzahl sinkt | E2E |
| 14 | `confirmWaypoint` entfernt `suggested`-Flag aus Waypoint-Objekt | Unit-Test |
| 15 | `rejectWaypoint` entfernt Waypoint aus `stage.waypoints` | Unit-Test |
| 16 | `addStage`-Patch setzt `suggested: true` auf alle Waypoints ohne vorhandenes Flag | Unit-Test (3 Cases: ohne Flag / mit Flag=true / mit Flag=false) |
| 17 | `canAdvanceStep3` gibt immer `true` zurueck | Unit-Test |
| 18 | `canAdvanceCurrent` mit currentStep=3 delegiert auf `canAdvanceStep3` | Unit-Test |
| 19 | Weiter-Button ist in Step 3 immer enabled | E2E (ohne jede Aktion: Button enabled) |
| 20 | Empty-State §8a: keine Stages → Hinweis mit TestID `trip-wizard-step3-empty-no-stages` | Unit-Test (Komponente direkt mit leerem WizardState mounten — UI-Pfad ist nicht erreichbar, weil Step 2 den Weiter-Button bei `stages.length === 0` blockiert) |
| 21 | Empty-State §8b: nur Pausentage → Hinweis mit TestID `trip-wizard-step3-empty-only-pauses` | Unit-Test (Komponente mit WizardState mounten, der nur Pause-Stages enthaelt — UI-Pfad nicht erreichbar) |
| 22 | Empty-State §8c: aktive Stage hat 0 Waypoints → Hinweis mit TestID `trip-wizard-step3-empty-no-waypoints` | E2E (alle Waypoints verwerfen) |
| 23 | `fillStep3()` ohne Parameter klickt Weiter und landet in Step 4 (heute: TestID `trip-wizard-step4-briefings`; mit #164 spaeter `-container`) | E2E (Helper-Test) |
| 24 | Master-Spec hat neuen Changelog-Eintrag fuer Step-3-Erweiterungen | Grep |
| 25 | `npm run check` und `npm run build` im `frontend/` gruen | CI-Output |

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` | SVG-Hoehenprofil mit Pin-Markern | ~80 |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | Wegpunkt-Row mit Confirm/Reject-Buttons | ~60 |
| `frontend/e2e/trip-wizard-step3.spec.ts` | E2E-Tests AC#1–#23 | ~150 |

### EDIT

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Stub gefuellt: linke Liste, rechte Confirm-UI, ProfileChart + WaypointRow eingebunden | ~120 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `addStage`-Patch + `confirmWaypoint` + `rejectWaypoint` + `canAdvanceStep3`-Getter + `canAdvanceCurrent`-Switch-Update | +~30 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | Neue Test-Cases fuer `addStage`-Patch, `confirmWaypoint`, `rejectWaypoint`, `canAdvanceStep3`, `canAdvanceCurrent` case 3 | +~50 |
| `frontend/e2e/helpers.ts` | `fillStep3`-Helper + `Step3Input`-Typ | +~25 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | AC#5a, AC#8, AC#11: `fillStep3`-Aufruf zwischen Step 2 und Step 4 | +~10 |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec-Changelog-Eintrag | +~8 |

### NICHT BERUEHRT

- `frontend/src/lib/types.ts` (`Waypoint.suggested?` ist bereits da — kein Edit)
- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` (alle benoetigten Helper vorhanden)
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` (kein Edit — `canAdvanceCurrent` Switch-Update ist in `wizardState.svelte.ts`)
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte`
- `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte`
- `internal/`, `src/`, `cmd/`, `api/` (kein Backend-Touch)

## Known Limitations

- **Reset „verworfen rueckgaengig"** ist nicht in Scope. Wer einen Wegpunkt
  versehentlich verwirft, muss in Step 2 zurueckgehen und die GPX-Datei neu
  hochladen (loest `addStage` + `suggested: true`-Patch neu aus).
- **`ProfileChart` skaliert nicht bei sehr vielen Wegpunkten.** Bei >= 50
  Wegpunkten pro Etappe werden Pins sehr eng — Overlapping, keine Scroll-/Zoom-
  Option. Tolerierbar fuer typische GR20-Etappen mit 5–20 Wegpunkten.
- **Kein Tooltip-on-hover fuer Pins.** Hovern ueber einen Pin im `ProfileChart`
  hebt den entsprechenden Waypoint in der Liste nicht hervor. Nice-to-have,
  Folge-Issue.
- **Klick auf Pin in `ProfileChart` selektiert keine Liste-Row.** Die SVG-Interaktion
  ist in Step 3 rein visuell. Folge-Issue.
- **Kein Auto-Advance nach letztem Waypoint verworfen.** Wenn alle Waypoints einer
  Stage verworfen sind, bleibt die Stage aktiv; kein automatischer Sprung zur
  naechsten Stage.
- **Mobile-Responsive nicht spezifiziert.** Side-by-Side-Layout (Links/Rechts)
  bricht auf schmalem Viewport um (Stack). CSS wird in Implementation-Phase
  entschieden; nicht aktiv getestet.
- **Re-Upload in Step 2 verwirft Step-3-Aktionen.** Geht User in Step 2 zurueck
  und laedt eine Etappe neu hoch, ruft `addStage` erneut `suggested: true` auf —
  alle vorherigen Confirm/Reject-Aktionen fuer diese Stage sind verloren. Bewusst
  akzeptiert (UI-Logik: neu parsen = neuer Vorschlag).

## Not In Scope

- **Karte / Map-Rendering** — ist Epic #137 (Wegpunkt-Editor).
- **Begriffs-Korrektur in Master-Spec §3.4** — die Master-Spec sagt heute
  „KI-Waypoint-Vorschlaege". Eine Korrektur dort ist Folge-PR (kein Approval-
  Reset noetig, da rein redaktionell). Diese Sub-Spec verwendet eigenstaendig
  die korrekte Terminologie.
- **Bulk-Aktion „Alle bestaetigen"** — Folge-Issue falls Bedarf besteht.
- **Reset „verworfen rueckgaengig"** — Folge-Issue.
- **Backend-Aenderungen** — `POST /api/gpx/parse` liefert bereits Waypoints.
- **Trip-Vorlagen** (#165).
- **Step 4 Save-Pipeline scharfschalten** (#164).
- **Tooltip-on-hover / Klick-auf-Pin in ProfileChart** (nice-to-have, s.o.).
- **Virtualisierung der Waypoint-Liste** (bei > 50 Items — nicht noetig fuer MVP).
- **A11y-Erweiterungen ueber ARIA-Labels hinaus** (z.B. Keyboard-Navigation im SVG).
- **localStorage-Persistenz** (Verlust bei Browser-Close vor Step 4 ist bekannt).

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
  - §3.1 WizardState (Erweiterungen)
  - §3.4 Waypoint.suggested
  - §1.4 Save-Pipeline (`stripSuggested`)
- **Vorgaenger-Sub-Spec:** [`epic_136_step2_stages.md`](./epic_136_step2_stages.md)
  (#162 — Layout-Pattern, TestID-Konvention, `fillStepN`-Helper-Form)
- **Vorgaenger-Sub-Spec:** [`epic_136_step1_profile.md`](./epic_136_step1_profile.md)
  (#161 — `canAdvanceStepN`-Pattern, Master-Spec-Changelog)
- **Atom-Komponenten:** Epic #133 (`Btn`, `GCard`, `Pill`, `Eyebrow`)
- **Backend-Specs:** [`elevation_analysis.md`](./elevation_analysis.md),
  [`hybrid_segmentation.md`](./hybrid_segmentation.md), [`gpx_upload.md`](./gpx_upload.md)
- **Issue:** [#163 — Step 3: KI-Waypoints bestaetigen](https://github.com/henemm/gregor_zwanzig/issues/163)
- **Epic:** [#136 — EPIC 4 Trip-Wizard](https://github.com/henemm/gregor_zwanzig/issues/136)
- **Phase-1+2-Kontext:** `docs/context/issue-163-wizard-step3-waypoints.md`

## Changelog

- 2026-05-11: External-Validator-Patch (Verdict AMBIGUOUS → VERIFIED): F-1
  AC#23 aufgeloest via Spec-Anpassung statt Code-Aenderung. §10 `fillStep3` und
  §11 Migration warten jetzt auf TestID `trip-wizard-step4-briefings` (heutiger
  Stand); Container-Konvention `trip-wizard-step4-container` wird mit Sub-Issue
  #164 (Step 4 Save-Pipeline) einheitlich nachgezogen. AC#20/21 von „E2E" auf
  „Unit-Test" umgestellt — UI-Pfad zu Step 3 ohne Stages/nur Pausen ist nicht
  erreichbar, weil Step 2 den Weiter-Button bei `stages.length === 0` blockiert.
  Render-Branch bleibt defensiv im Markup. Keine Code-Aenderung in
  `Step4Briefings.svelte` (out of scope nach Datei-Liste).
- 2026-05-11: Terminologie korrigiert — „KI-Waypoints" / „KI-Pins" /
  „KI-Vorschlaege" → „Wegpunkt-Vorschlaege" / „Vorschlags-Pins" /
  „automatische Vorschlaege". Begruendung: die Wegpunkte stammen aus
  deterministischer Heuristik (`detect_waypoints` Wetterscheiden-Erkennung +
  `optimize_segments` Hike-Speed-Optimierung), nicht aus ML/LLM. `suggested`-Flag
  bleibt unveraendert (neutral benannt). Neue Sektion „Begriffsklaerung" am
  Anfang. Master-Spec §3.4-Korrektur als Folge-PR (siehe Not In Scope).
- 2026-05-10: Stub ausgefuellt — Layout-Wireframe (Etappen-Liste links, Confirm-UI rechts),
  `ProfileChart.svelte` als neue SVG-Komponente (~360x120px, Polyline + Pin-Marker,
  orange-gestrichelt fuer `suggested`, solid fuer bestaetigt), `WaypointRow.svelte` als
  neue Zeilen-Komponente (Name, Hoehe, Zeit, Bestaetigen/Verwerfen-Buttons),
  `addStage`-Patch (Variante A: zentral `suggested: true` auf alle eingehenden Waypoints),
  `confirmWaypoint` + `rejectWaypoint` als neue WizardState-Methoden,
  `canAdvanceStep3 = true` (User-Entscheidung: kein Mindest-Bestaetigung),
  Switch-Update `canAdvanceCurrent` case 3, lokaler `activeStageId`-State,
  5 Edge-Cases (leer/nur-Pausen/alle-verworfen/keine-Elevation/1-Waypoint),
  TestID-Inventar mit Prefix `trip-wizard-step3-*`, `fillStep3`-E2E-Helper
  (confirmAll, rejectByName, Default: nur Weiter), Migration von 3 Shell-Tests
  (AC#5a, AC#8, AC#11), 25 Acceptance Criteria, Datei-Liste (3 NEU + 6 EDIT,
  geschaetzt ~260 LoC Produktionscode + ~200 LoC Tests + ~18 LoC Spec-Patches).
  Status `stub` → `draft`, Version `0.1` → `1.0`.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
