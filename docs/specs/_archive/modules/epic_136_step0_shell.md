---
entity_id: epic_136_step0_shell
type: module
created: 2026-05-09
updated: 2026-05-10
status: draft
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issue: 160
tags: [sveltekit, frontend, wizard, shell, stepper, epic-136]
---

# Epic 136 — Sub-Spec #160: Wizard-Shell + 4-Schritt-Stepper

## Approval

- [ ] Approved

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Definiert das UI-Detail der Wizard-Shell (`TripWizardShell.svelte`) und des `Stepper.svelte`-Atoms
fuer den neuen 4-Schritt Trip-Wizard auf `/trips/new`. Die Shell instanziiert den zentralen
`WizardState` (Master-Spec §3.1), legt ihn via Svelte-Context ab und orchestriert Header,
Stepper, Step-Slot und Footer (Vor/Zurueck/Abbrechen/Speichern). Step-Inhalte selbst sind nicht
Teil dieser Sub-Spec — sie werden in den Folge-Issues #161–#164 implementiert; #160 liefert nur
4 leere Step-Platzhalter mit `data-testid`-Anker, damit Navigations-E2E-Tests schreibbar sind.

## Source

- **Komponenten (NEU):**
  - `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
  - `frontend/src/lib/components/trip-wizard/Stepper.svelte`
  - `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` (Platzhalter)
  - `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` (Platzhalter)
  - `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` (Platzhalter)
  - `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` (Platzhalter)
- **Route (EDIT):** `frontend/src/routes/trips/new/+page.svelte` (mountet Shell statt altem Wizard)
- **Identifier:** `TripWizardShell` (default export), `Stepper` (default export)

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret konsumiert sie:

- **§1.4 Save-Pipeline** — `state.save()` wird in Step 4 vom Speichern-Button aufgerufen; Shell
  rendert nur den Button und liest `state.saveStatus` / `state.saveError`.
- **§3.1 WizardState** — `currentStep`, `nextStep()`, `prevStep()`, `save()`, `saveStatus`,
  `saveError` sind die einzigen Felder/Methoden, die diese Sub-Spec beruehrt.
- **§4 Vertraege Master-Spec ↔ Sub-Specs** — Garantien (1) bis (5) werden eingehalten; insbesondere
  garantiert die Shell den `setContext('trip-wizard-state', state)`-Aufruf (§4.1).

Aenderungen am `WizardState`-Schema sind ausdruecklich NICHT Teil von #160 (siehe
[Step-Validation-Pattern](#step-validation-pattern-folge-issues)).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` (Master-Spec §3.1) | class | Single Source of Truth fuer Step-Navigation und Save-Status |
| `wizardState.svelte.ts` | file | Exportiert `WizardState`-Klasse — Shell instanziiert pro Page-Mount |
| `$lib/components/ui/btn/Btn.svelte` | component (Epic #133) | Footer-Buttons Zurueck/Abbrechen/Weiter/Speichern |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | "Schritt N von 4" ueber dem Header |
| `$lib/components/ui/dot/Dot.svelte` | component (Epic #133) | Stepper-Done-Indikator (`tone="success"`) |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | Optionaler Container fuer Step-Slot (Step-Inhalte verwenden ihn selbst) |
| `frontend/src/app.css` | file | Design-Tokens `--g-accent`, `--g-paper`, `--g-ink`, `--g-ink-faint`, `--g-success`, `--g-danger` |
| `svelte` (`setContext`, `getContext`) | api | Context-Bereitstellung zwischen Shell und Step-Komponenten |
| `$app/navigation` (`goto`) | api | Cancel- und Save-Redirect |
| `frontend/src/routes/trips/new/+page.svelte` | file (edit) | Mountet `TripWizardShell` statt altem `TripWizard` |
| `frontend/e2e/trip-wizard.spec.ts` | file (edit) | Wird per `test.describe.skip()` deaktiviert |

## Implementation Details

### 1. Architektur-Ueberblick

Die Verantwortlichkeiten sind klar getrennt:

```
+page.svelte  ─ instanziiert WizardState (Factory-Pattern, im <script>-Block)
              ─ setContext('trip-wizard-state', state)
              ─ rendert <TripWizardShell />
                │
                ├─ Header (h1 "Neuer Trip" + Eyebrow "Schritt N von 4")
                ├─ <Stepper current={state.currentStep} labels=[...] subLabels=[...] />
                │     ↑ pure presentational, kein Context-Konsum
                ├─ Step-Slot:
                │     {#if state.currentStep === 1} <Step1Profile />
                │     {#if state.currentStep === 2} <Step2Stages />
                │     {#if state.currentStep === 3} <Step3Waypoints />
                │     {#if state.currentStep === 4} <Step4Briefings />
                ├─ Save-Status-Region (role="status", aria-live="polite")
                └─ Footer:
                      ├─ <Btn variant="outline">Zurueck</Btn>   (nur Step > 1)
                      ├─ <Btn variant="ghost">Abbrechen</Btn>
                      ├─ <Btn variant="accent">Weiter</Btn>     (Step < 4)
                      └─ <Btn variant="accent">Speichern</Btn>  (Step === 4)
```

**Begruendung Factory-Pattern (KRITISCH):** `WizardState` darf NICHT als Top-Level-Modul-Singleton
instanziiert werden — Svelte-5-Runen verlieren in Safari die Reaktivitaet, wenn die `$state`-Felder
ausserhalb eines Komponenten-Lebenszyklus angelegt werden. Die Instanziierung erfolgt im
`<script>`-Block von `+page.svelte`. Diese Regel ergaenzt die CLAUDE.md-Konvention "Factory Pattern
fuer NiceGUI `on_click`" auf alle Svelte-5-Klassen-Instanzen.

### 2. `+page.svelte` — Mount-Punkt

```svelte
<script lang="ts">
  import { setContext } from 'svelte';
  import { WizardState } from '$lib/components/trip-wizard/wizardState.svelte';
  import TripWizardShell from '$lib/components/trip-wizard/TripWizardShell.svelte';

  // Factory-Pattern: pro Page-Mount eine eigene State-Instanz.
  // NIEMALS top-level: Safari-Reaktivitaetsrisiko mit Svelte-5-Runen.
  const state = new WizardState();
  setContext('trip-wizard-state', state);
</script>

<TripWizardShell />
```

Der bestehende dreizeilige Mount des alten `TripWizard` wird ersetzt — kein anderer Code in dieser
Route veraendert sich.

### 3. `Stepper.svelte` — pure presentational

**Props:**

```typescript
interface StepperProps {
  current: 1 | 2 | 3 | 4;
  labels: string[];          // exakt 4 Eintraege
  subLabels?: string[];      // exakt 4 Eintraege, optional
}
```

**Status-Indikator pro Step (Index `i`, 0-basiert):**

| Zustand | Bedingung | Markup |
|---------|-----------|--------|
| `done` | `i + 1 < current` | `<Dot tone="success" size="md" />` neben Label |
| `active` | `i + 1 === current` | Border-Kreis `border-[var(--g-accent)]` mit Akzent-Hintergrund + Ziffer in Akzent-Foreground |
| `pending` | `i + 1 > current` | Leerer Border-Kreis `border-[var(--g-ink-faint)]` mit Ziffer in `text-[var(--g-ink-faint)]` |

**Connector-Linie zwischen Steps:**

- `bg-[var(--g-accent)]` zwischen done-Steps und vor active-Step
- `bg-[var(--g-ink-faint)]/30` ab active-Step

**Pseudo-Code (ohne Tailwind-Boilerplate):**

```svelte
<script lang="ts">
  import { Dot } from '$lib/components/ui/dot';

  interface Props {
    current: 1 | 2 | 3 | 4;
    labels: string[];
    subLabels?: string[];
  }
  let { current, labels, subLabels = [] }: Props = $props();

  function stateOf(index: number): 'done' | 'active' | 'pending' {
    if (index + 1 < current) return 'done';
    if (index + 1 === current) return 'active';
    return 'pending';
  }
</script>

<div data-testid="trip-wizard-stepper" class="flex items-center gap-2">
  {#each labels as label, i}
    <div
      data-testid={`trip-wizard-step-${i + 1}`}
      data-state={stateOf(i)}
      class="flex flex-col items-center"
    >
      {#if stateOf(i) === 'done'}
        <Dot tone="success" size="md" />
      {:else if stateOf(i) === 'active'}
        <span class="w-8 h-8 rounded-full border-2 border-[var(--g-accent)]
                     bg-[var(--g-accent)]/10 flex items-center justify-center
                     text-[var(--g-accent)] font-medium">{i + 1}</span>
      {:else}
        <span class="w-8 h-8 rounded-full border border-[var(--g-ink-faint)]
                     flex items-center justify-center
                     text-[var(--g-ink-faint)]">{i + 1}</span>
      {/if}
      <span class="text-sm mt-1">{label}</span>
      {#if subLabels[i]}
        <span class="text-xs text-[var(--g-ink-faint)]">{subLabels[i]}</span>
      {/if}
    </div>
    {#if i < labels.length - 1}
      <div class={stateOf(i) === 'done'
        ? 'flex-1 h-0.5 bg-[var(--g-accent)]'
        : 'flex-1 h-0.5 bg-[var(--g-ink-faint)]/30'}></div>
    {/if}
  {/each}
</div>
```

Stepper konsumiert KEINEN Context — bleibt unit-testbar ohne State-Setup.

### 4. Step-Labels und Sub-Labels (in Shell als Konstante)

| Step | Label | Sub-Label |
|------|-------|-----------|
| 1 | Profil & Eckdaten | Aktivitaet, Name, Zeitraum |
| 2 | GPX-Import | Etappen hochladen |
| 3 | Wegpunkte | KI-Vorschlaege bestaetigen |
| 4 | Briefings | Kanaele und Alerts |

Diese Konstanten leben in `TripWizardShell.svelte`, nicht in `Stepper.svelte` — der Stepper bleibt
generisch, die Wizard-spezifischen Texte gehoeren zur Shell.

### 5. `TripWizardShell.svelte` — Layout & Footer

**Layout:**

- Wrapper: `max-w-3xl mx-auto py-6 px-4`
- Step-Slot: `min-h-[300px]`
- Footer: `flex items-center justify-between mt-8 pt-4 border-t border-[var(--g-ink-faint)]/30`

**Footer-Verhalten:**

| Button | Sichtbar | Aktion | Variant | Disabled |
|--------|----------|--------|---------|----------|
| Zurueck | `state.currentStep > 1` | `state.prevStep()` | `outline` | nie |
| Abbrechen | immer | `goto('/')` (Cockpit) | `ghost` | nie |
| Weiter | `state.currentStep < 4` | `state.nextStep()` | `accent` | **in #160 nie** (siehe §[Step-Validation-Pattern](#step-validation-pattern-folge-issues)) |
| Speichern | `state.currentStep === 4` | `state.save()` | `accent` | `state.saveStatus === 'saving'` |

**Speichern-Button-Text** wechselt dynamisch (Svelte-5-Runen):

```svelte
<script lang="ts">
  const saveLabel = $derived(
    state.saveStatus === 'saving' ? 'Speichern...' :
    state.saveStatus === 'ok'     ? 'Gespeichert'  :
                                     'Speichern'
  );
</script>
```

**Save-Status-Region:**

```svelte
<div data-testid="trip-wizard-save-status" role="status" aria-live="polite">
  {#if state.saveStatus === 'saving'}
    <span>Speichern...</span>
  {:else if state.saveStatus === 'error'}
    <span class="text-[var(--g-danger)]">{state.saveError}</span>
  {:else if state.saveStatus === 'ok'}
    <span class="text-[var(--g-success)]">Gespeichert</span>
  {/if}
  <!-- saveStatus === 'idle': nichts rendern (display: none) -->
</div>
```

**Cancel-Ziel:** `goto('/')` (Cockpit). Begruendung: Master-Spec §1 nennt das Cockpit als
Einstiegspunkt; User-Recovery-Pfad ist Cockpit (Epic #134), nicht `/trips`.

### 6. Step-Platzhalter

Jede der 4 Step-Komponenten ist in #160 ein leerer Container mit `data-testid`-Anker und
Platzhaltertext. Beispiel `Step1Profile.svelte`:

```svelte
<div data-testid="trip-wizard-step1-profile">
  <p class="text-[var(--g-ink-faint)]">Inhalt folgt in Issue #161 — Profil & Eckdaten.</p>
</div>
```

`testid`-Konvention pro Step:

| Step | TestID |
|------|--------|
| 1 | `trip-wizard-step1-profile` |
| 2 | `trip-wizard-step2-stages` |
| 3 | `trip-wizard-step3-waypoints` |
| 4 | `trip-wizard-step4-briefings` |

### 7. TestID-Inventar

Alle TestIDs sind mit Prefix `trip-wizard-*` versehen (verhindert Selektor-Kollision mit dem alten
`wizard-*`-Stepper, der via `TripEditView` parallel weiterlaeuft):

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-shell` | Shell-Container | Root-Anker fuer E2E |
| `trip-wizard-stepper` | Stepper-Container | Stepper-Wrapper |
| `trip-wizard-step-1` ... `trip-wizard-step-4` | Stepper-Step-Indikator | mit `data-state="done\|active\|pending"` |
| `trip-wizard-step1-profile` ... `trip-wizard-step4-briefings` | Step-Slot-Container | Erkennung, welcher Step gerendert ist |
| `trip-wizard-back` | Footer-Button | Zurueck-Klick |
| `trip-wizard-cancel` | Footer-Button | Abbrechen-Klick |
| `trip-wizard-next` | Footer-Button | Weiter-Klick |
| `trip-wizard-save` | Footer-Button | Speichern-Klick (nur Step 4) |
| `trip-wizard-save-status` | Region | Save-Feedback (`role="status"`) |

### 8. Step-Validation-Pattern (Folge-Issues)

**In #160 NICHT implementiert** — Steps sind leer, Weiter-Button ist immer enabled. Pattern wird
hier nur dokumentiert, damit Folge-Issues #161–#164 darauf zugreifen koennen:

- Folge-Issues ergaenzen `WizardState` um pro-Step-Validity-Flags:
  - `step1Valid: boolean = $state(false)`
  - `step2Valid: boolean = $state(false)`
  - `step3Valid: boolean = $state(false)`
  - `step4Valid: boolean = $state(false)`
- Plus ein `canAdvance: boolean = $derived(...)`, das je nach `currentStep` den passenden
  Validity-Flag zurueckgibt.
- Footer-Weiter-Button setzt dann `disabled={!state.canAdvance}`.

**Master-Spec-Update:** Das erste Step-Issue (#161) erweitert die Master-Spec §3.1 um diese Felder.
Bis dahin ist der Weiter-Button in #160 ohne Validation.

### 9. Alte E2E-Tests deaktivieren

`frontend/e2e/trip-wizard.spec.ts` testet den alten Wizard mit Labels `Route/Etappen/Wetter/Reports`
und TestIDs `wizard-*`. Diese ~28 Tests brechen, sobald `/trips/new` auf `TripWizardShell`
umstellt. Mitigation:

```typescript
// frontend/e2e/trip-wizard.spec.ts
test.describe.skip('Trip Wizard (alter Wizard)', () => {
  // Cleanup nach Epic #136-Abschluss — alter Wizard noch im Edit-Pfad
  // (TripEditView.svelte rendert weiterhin den alten Wizard).
  // ... bestehende Tests unveraendert
});
```

Loeschen waere falsch, weil der Edit-Pfad (`/trips/[id]/edit`) den alten Wizard noch verwendet.
Loeschung erfolgt im Cleanup-Folge-Issue (Master-Spec §Delete).

## Expected Behavior

- **Input:** User navigiert auf `/trips/new` (z.B. via Cockpit-CTA aus Epic #134).
- **Output:**
  - `TripWizardShell` rendert mit Header "Neuer Trip", Eyebrow "Schritt 1 von 4", Stepper, leerem
    Step1Profile-Platzhalter und Footer (Abbrechen + Weiter, kein Zurueck).
  - Klick auf Weiter erhoeht `state.currentStep` von 1 auf 2; Stepper-Indikatoren aktualisieren
    `data-state` (Step 1 wird `done`, Step 2 wird `active`).
  - Klick auf Zurueck (in Step 2+) verringert `state.currentStep`.
  - In Step 4 zeigt der Footer "Speichern" statt "Weiter"; Klick ruft `state.save()`.
  - Klick auf Abbrechen navigiert zu `/`.
- **Side effects:**
  - `WizardState`-Instanz wird per `setContext('trip-wizard-state', ...)` allen Step-Komponenten
    bereitgestellt.
  - `state.save()` (Master-Spec §1.4) loest `POST /api/trips` aus — in #160 ohne validen Inhalt
    (leere Steps), daher in der Praxis Validation-Fehler im Backend; Spec-Erfuellung ist die
    Existenz und Verkabelung des Buttons, nicht ein gruener Save-Request.
  - Save-Status-Region zeigt "Speichern..." waehrend `state.saveStatus === 'saving'`,
    `state.saveError` bei Fehler, "Gespeichert" bei Erfolg, sonst nichts.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `/trips/new` rendert `TripWizardShell` (alter `TripWizard` weg vom Mount-Pfad) | E2E `expect(page.getByTestId('trip-wizard-shell')).toBeVisible()` |
| 2 | `WizardState` wird in `+page.svelte` instanziiert (nicht als Modul-Singleton) und via `setContext('trip-wizard-state', state)` bereitgestellt | Code-Inspektion + Step-Komponenten lesen via `getContext` |
| 3 | Stepper rendert 4 Indikatoren mit `data-testid="trip-wizard-step-{1..4}"` und `data-state="done\|active\|pending"` | E2E + Stepper-Unit-Test |
| 4 | Step 1 ist initial aktiv (`data-state="active"`); Steps 2–4 pending | E2E |
| 5 | Klick auf "Weiter" wechselt zu Step 2; "Zurueck" auf Step 2 wechselt zurueck zu Step 1 | E2E |
| 5a | Weiter-Button ist in #160 in allen Steps 1–3 enabled (kein Step-Validation-Gate; siehe §[Step-Validation-Pattern](#step-validation-pattern-folge-issues)) | E2E `expect(weiterBtn).toBeEnabled()` in Steps 1, 2, 3 |
| 6 | Step-Indikatoren aktualisieren `data-state` nach Navigation (Step 1 wird `done`, Step 2 wird `active`) | E2E |
| 7 | Cancel navigiert zu `/` | E2E |
| 8 | Speichern-Button erscheint nur in Step 4; Klick ruft `state.save()` | E2E (Sichtbarkeit + saveStatus-Beobachtung) |
| 9 | Alte E2E-Tests in `trip-wizard.spec.ts` sind via `.skip()` deaktiviert mit Kommentar | Grep `test.describe.skip` + Kommentar-Text |
| 10 | `npm run check` und `npm run build` im `frontend/` gruen | CI-Output |
| 11 | Alle 4 Step-Slot-Container (`trip-wizard-step{N}-{name}`) sind in den jeweiligen Steps sichtbar mit Platzhaltertext | E2E |
| 12 | Stepper-Indikator nutzt Atom `Dot` fuer Done-Status (Token-konform) | Code-Inspektion `import { Dot }` |

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Shell-Komponente (Header, Stepper, Step-Slot, Footer) | ~80 |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Pure presentational 4-Step-Indikator | ~50 |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Platzhalter mit testid-Anker | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Platzhalter mit testid-Anker | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Platzhalter mit testid-Anker | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Platzhalter mit testid-Anker | ~10 |
| `frontend/src/lib/components/trip-wizard/__tests__/Stepper.test.ts` | Unit-Test fuer Stepper-State-Logik | ~30 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | E2E-Tests Acceptance #1, #3–#8, #11 | ~120 |

### EDIT

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/routes/trips/new/+page.svelte` | Mountet `TripWizardShell` statt altem `TripWizard`; instanziiert `WizardState` und setContextet (~15 Zeilen) |
| `frontend/e2e/trip-wizard.spec.ts` | `test.describe.skip(...)` mit Kommentar "Cleanup nach Epic #136-Abschluss — alter Wizard noch im Edit-Pfad" (~3 Zeilen) |

### NICHT BERUEHRT (aus Master-Spec garantiert)

- `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (existiert, Schema unveraendert)
- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` (existiert, kein Aufruf in Shell)
- `frontend/src/lib/components/wizard/*` (alter Wizard, weiterhin im Edit-Pfad aktiv)
- `internal/`, `src/`, `cmd/` (kein Backend-Touch)

## Known Limitations

- **Step-Validation/canAdvance ist nicht implementiert** — Weiter-Button ist immer enabled bis #161
  die `WizardState`-Validity-Flags ergaenzt (siehe §[Step-Validation-Pattern](#step-validation-pattern-folge-issues)).
- **Save-Pipeline funktioniert mit leeren Steps technisch**, schreibt aber unvollstaendigen Trip
  (kein Activity, leere stages). Folge-Issues #161–#164 fuellen die Step-Inhalte und damit den
  Trip-Body. Spec-Erfuellung in #160 ist die Existenz/Verkabelung des Buttons, nicht ein gruener
  Save-Request.
- **Alte E2E-Tests in `trip-wizard.spec.ts` sind skipped, nicht geloescht** — Edit-Pfad
  (`TripEditView.svelte`) braucht sie noch. Loeschung erfolgt im Cleanup-Folge-Issue.
- **Stepper hat keine outline-Variante** — die Pending/Active-Kreise nutzen Custom-Markup statt
  einer Atom-Komponente. `Dot` aus Lauf B kennt keine Outline-Variante; eine Erweiterung waere
  ein eigener Spec gegen Epic #133.

## Not In Scope

- **Inhalte der Steps 1–4** — sind Folge-Issues #161–#164.
- **Vorlagen-Picker** — Folge-Issue #165.
- **Backend-Aenderungen** — keine Touches in `internal/`, `src/`, `cmd/`.
- **Edit-Pfad-Refactor** — `TripEditView.svelte` bleibt auf altem Wizard, eigenes Folge-Issue
  nach Cleanup.
- **`WizardState`-Schema-Erweiterung um Validity-Flags** — gehoert in #161 (mit Master-Spec-Update).
- **Mobile/Responsive-Anpassungen ueber `max-w-3xl`-Wrapper hinaus** — kein Scope der Sub-Spec.

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
  - §1.4 Save-Pipeline
  - §3.1 WizardState
  - §4 Vertraege Master-Spec ↔ Sub-Specs
- **Atom-Komponenten:** Epic #133 Lauf B (`Btn`, `GCard`, `Eyebrow`, `Dot`)
- **Issue:** [#160 — Wizard: Shell + 4-Schritt-Stepper](https://github.com/henemm/gregor_zwanzig/issues/160)
- **Phase-1-Kontext:** `docs/context/issue-160-wizard-shell-stepper.md`

## Changelog

- 2026-05-10: Sub-Spec aus Stub ausgefuellt — Architektur (Factory-Pattern, Context-Bereitstellung,
  pure-presentational Stepper), Step-Labels und Sub-Labels, TestID-Inventar mit Prefix
  `trip-wizard-*`, Footer-Verhalten mit dynamischem Speichern-Button-Text und Save-Status-Region,
  Step-Validation-Pattern fuer Folge-Issues dokumentiert (in #160 nicht implementiert),
  Alt-E2E-Skip-Strategie, 13 Acceptance Criteria, Datei-Liste (8 NEU + 2 EDIT). Status `stub` →
  `draft`, Version `0.1` → `1.0`. Validator-Warnings beruecksichtigt: `--g-danger` zur Token-Liste,
  `$derived`-Pseudo-Code als gueltiges Svelte-5-Snippet, AC #5a fuer Weiter-Button-enabled-Vertrag
  in #160.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
