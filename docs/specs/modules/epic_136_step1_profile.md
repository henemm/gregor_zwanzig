---
entity_id: epic_136_step1_profile
type: module
created: 2026-05-09
updated: 2026-05-10
status: draft
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issue: 161
tags: [sveltekit, frontend, wizard, step1, profile, epic-136]
---

# Epic 136 — Sub-Spec #161: Step 1 Aktivitaetsprofil + Eckdaten

## Approval

- [ ] Approved

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Definiert das UI-Detail von Schritt 1 des Trip-Wizards (`Step1Profile.svelte`): fuenf Aktivitaets-Profil-Chips
(Trekking, Skitour, Hochtour, Klettersteig, MTB), drei Eingabefelder (Name, Kuerzel, Startdatum) und die
Validierungslogik fuer die Vorwaerts-Bedingung. Step 1 schreibt ausschliesslich in `WizardState`-Felder, die
durch die Master-Spec (§3.1) bereits angelegt sind. Zusaetzlich wird die Master-Spec um ein additives
`$derived`-Feld `canAdvanceStep1` erweitert (siehe §10) und die Shell aus #160 erhaelt einen 1-Zeilen-Edit am
Weiter-Button, damit dieser disabled bleibt, solange Pflichtfelder leer sind.

## Source

- **Komponente (EDIT, Stub fuellen):** `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`
- **State-Erweiterung (EDIT):** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **Shell-Mini-Edit (EDIT):** `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- **Identifier:** `Step1Profile` (default export), `WizardState.canAdvanceStep1` (derived field)

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret konsumiert sie:

- **§1.2 Datenmodell** — `ActivityType` (5 Werte), `Trip.shortcode?`, `Trip.activity?`.
- **§1.3 Mapping** — `mapActivityToProfile()` wird in Step 1 NICHT direkt aufgerufen (Step 4-Concern), aber `state.activity` ist die Eingabe fuer das spaetere Mapping.
- **§3.1 WizardState** — Step 1 schreibt `activity`, `name`, `shortcode`, `startDate`. `endDate` bleibt Step-2-Concern (Master-Spec Z. 253: `// derived in Step 2`).
- **§4 Vertraege Master-Spec ↔ Sub-Specs** — Sub-Specs duerfen das Schema nicht aendern „ohne Update dieser Master-Spec". Diese Sub-Spec **erweitert** das Schema additiv um `canAdvanceStep1` und liefert den Master-Spec-Changelog-Eintrag mit (siehe §10).

Vorgaenger-Sub-Spec: [`epic_136_step0_shell.md`](./epic_136_step0_shell.md) (#160), die das `canAdvance`-Pattern fuer Folge-Issues explizit offen gelassen hat (§Step-Validation-Pattern).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` (Master-Spec §3.1) | class | Single Source of Truth fuer Step-1-Felder + neues `canAdvanceStep1` |
| `wizardState.svelte.ts` | file (edit) | Erweiterung um `$derived canAdvanceStep1` |
| `wizardHelpers.ts` | file | `mapActivityToProfile` (in Step 1 nicht aufgerufen, aber Schema-Konsistenz) |
| `TripWizardShell.svelte` | file (edit) | 1-Zeilen-Edit: Weiter-Button `disabled`-Prop |
| `frontend/src/lib/types.ts` | file | `ActivityType`-Union (5 Werte) — Single Source of Truth |
| `$lib/components/ui/pill/Pill.svelte` | component (Epic #133) | Visuelle Chip-Optik in den 5 ProfileChips |
| `$lib/components/ui/input/input.svelte` | component (Epic #133) | Text-Inputs Name + Kuerzel und Date-Input Startdatum |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Optional: Abschnitts-Eyebrows „Aktivitaet"/„Eckdaten" |
| `frontend/src/app.css` | file | Tokens `--g-accent`, `--g-ink`, `--g-ink-faint`, `--g-paper`, `--g-radius-pill` |
| `svelte` (`getContext`) | api | Step1Profile konsumiert State via `getContext('trip-wizard-state')` |
| `frontend/e2e/trip-wizard-shell.spec.ts` | file (edit) | 5 bestehende Tests werden durch den `disabled`-Mechanismus brechen — Migration via `fillStep1`-Helper |

## Implementation Details

### 1. Layout-Wireframe

```
┌──────────────────────────────────────────────────────────┐
│ Eyebrow: „Aktivitaet"                                    │
│                                                          │
│ ┌──────────┬──────────┬──────────┬─────────────┬───────┐ │
│ │ Trekking │ Skitour  │ Hochtour │ Klettersteig│  MTB  │ │  ← 5 ProfileChips
│ └──────────┴──────────┴──────────┴─────────────┴───────┘ │     (gewaehlt = tone="accent",
│                                                          │      sonst tone="default")
│ Eyebrow: „Eckdaten"                                      │
│                                                          │
│ Label: Name *                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Input type=text                                      │ │  ← Pflicht
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Label: Kuerzel (optional)                                │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Input type=text, maxLength=20                        │ │  ← Optional
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Label: Startdatum *                                      │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Input type=date                                      │ │  ← Pflicht
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Hinweis: „Das Enddatum wird in Schritt 2 aus den         │  ← `text-[var(--g-ink-faint)]`
│  Etappen berechnet."                                     │     (1-zeilig, klein)
└──────────────────────────────────────────────────────────┘
```

Container nutzt `flex flex-col gap-6` mit ggf. `<GCard>` als Wrapper. Feld-Labels liegen oberhalb der Inputs (nicht inline). Pflicht-Sterne sind visuell `text-[var(--g-accent)]`.

### 2. ProfileChip — Atom-Verwendung und a11y

Pill ist visuelles Atom (ein `<span>`). Klick + Tastatur + Screenreader-Semantik fehlt — daher
**Wrapper-Pattern**: ein `<button>` umschliesst eine `<Pill>` mit dynamischem `tone`.

```svelte
<script lang="ts">
  import { Pill } from '$lib/components/ui/pill';
  import type { ActivityType } from '$lib/types';

  interface Props {
    activity: ActivityType;
    label: string;
    selected: boolean;
    onSelect: (activity: ActivityType) => void;
  }
  let { activity, label, selected, onSelect }: Props = $props();
</script>

<button
  type="button"
  data-testid={`trip-wizard-step1-chip-${activity}`}
  aria-pressed={selected}
  class="focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)] rounded-full"
  onclick={() => onSelect(activity)}
>
  <Pill tone={selected ? 'accent' : 'default'}>{label}</Pill>
</button>
```

Diese Inline-Definition lebt im `<script>`-Block von `Step1Profile.svelte` als lokale Snippet-Funktion oder kleine Untertypisierung — **keine neue Atom-Komponente**, weil das Pattern auf Step 1 begrenzt ist.

**A11y-Garantien:**

- `aria-pressed={selected}` (Toggle-Semantik fuer Screenreader)
- `type="button"` (verhindert Form-Submit-Default in unerwartetem Submit-Kontext)
- `focus-visible:ring-2` (sichtbarer Tastatur-Fokus)
- `rounded-full` matcht Pill-Form (`--g-radius-pill`) — Fokus-Ring liegt nicht ausserhalb der visuellen Form
- Tab-Reihenfolge: Chips → Name → Kuerzel → Startdatum → Footer-Buttons (DOM-Reihenfolge entspricht Layout)

### 3. ProfileChip-Reihenfolge und Default

```typescript
const PROFILES: { activity: ActivityType; label: string }[] = [
  { activity: 'trekking',     label: 'Trekking' },
  { activity: 'skitour',      label: 'Skitour' },
  { activity: 'hochtour',     label: 'Hochtour' },
  { activity: 'klettersteig', label: 'Klettersteig' },
  { activity: 'mtb',          label: 'MTB' }
];
```

Initial ist `state.activity === null` — kein Chip ausgewaehlt. User MUSS aktiv waehlen. Begruendung: Mapping zu `aggregation.profile` ist behavior-relevant (Master-Spec §1.3) — kein silent-Default.

### 4. Eingabefelder

| Feld | Pflicht | Bind-Target | Validierung (UI-Soft) |
|------|---------|-------------|------------------------|
| Name | ja | `state.name` (`string`) | Pflicht: `state.name.trim().length > 0`. Max ist Backend-side; UI hat kein Limit. |
| Kuerzel | nein | `state.shortcode` (`string`) | `maxLength={20}`. **Kein Regex** — Backend nimmt beliebige Strings. Leerer String wird beim Save als `undefined` persistiert (siehe `wizardState.svelte.ts` `toTripPayload()`). |
| Startdatum | ja | `state.startDate` (`string \| null`) | Pflicht: `state.startDate !== null` und nicht-leer. Format: ISO `yyyy-mm-dd` (HTML5 native). |

**Enddatum:** wird in Step 1 NICHT erfasst. Master-Spec §3.1 sagt explizit „derived in Step 2". Der Hilfetext unter dem Startdatum erklaert das dem User in einem Satz.

### 5. State-Bindung (Svelte-5-Runes)

```svelte
<script lang="ts">
  import { getContext } from 'svelte';
  import type { ActivityType } from '$lib/types';
  import type { WizardState } from '../wizardState.svelte';

  const state = getContext<WizardState>('trip-wizard-state');

  // Factory-Handler (CLAUDE.md Safari-Pattern) — benannte Handler statt anonymer Closures.
  function handleSelectActivity(activity: ActivityType) {
    state.activity = activity;
  }
</script>

<!-- Inputs binden direkt zwei-Wege: -->
<input type="text" bind:value={state.name}      data-testid="trip-wizard-step1-name" />
<input type="text" bind:value={state.shortcode} data-testid="trip-wizard-step1-shortcode" maxlength="20" />
<input type="date" bind:value={state.startDate} data-testid="trip-wizard-step1-startdate" />
```

Svelte-5 erlaubt `bind:value={state.startDate}` auch fuer `string | null` — leerer Date-Picker setzt den String auf `''`, NICHT `null`. **Wichtig:** Die Validierung in §6 muss daher leeren String akzeptieren als „nicht gesetzt".

### 6. `WizardState.canAdvanceStep1` (additive Erweiterung)

Wird zu `wizardState.svelte.ts` hinzugefuegt **direkt nach** `derivedAggregationProfile`:

```typescript
canAdvanceStep1 = $derived(
  this.activity !== null &&
  this.name.trim().length > 0 &&
  typeof this.startDate === 'string' &&
  this.startDate.length > 0
);
```

**Bewusste Eigenschaften:**

- `this.activity !== null` — kein Chip-Default; User muss waehlen.
- `this.name.trim().length > 0` — Whitespace-only zaehlt als leer.
- `typeof this.startDate === 'string' && this.startDate.length > 0` — akzeptiert sowohl `null` (Initial-Zustand) als auch `''` (HTML5-Date-Input nach Loeschen) als „nicht gesetzt".
- `shortcode` und `endDate` sind NICHT Teil der Bedingung (optional bzw. Step-2-Concern).

### 7. Shell-Mini-Edit fuer `disabled`-Verkabelung

`TripWizardShell.svelte` Zeile 121 (heute):

```svelte
<Btn data-testid="trip-wizard-next" variant="accent" size="md" onclick={handleNext}>
  Weiter
</Btn>
```

Wird zu (1-Zeilen-Edit):

```svelte
<Btn
  data-testid="trip-wizard-next"
  variant="accent"
  size="md"
  onclick={handleNext}
  disabled={state.currentStep === 1 ? !state.canAdvanceStep1 : false}
>
  Weiter
</Btn>
```

Die Bedingung pruegt explizit `currentStep === 1`, damit Step 2/3-Weiter-Buttons unangetastet bleiben (gehoeren zu #162/#163, jede Sub-Spec ergaenzt analog `canAdvanceStep2`/`canAdvanceStep3`). Fallback `false` heisst: enabled fuer Steps ohne eigene Validierung.

**Begruendung Inline-Bedingung statt Generic `state.canAdvance`:** Vermeidet Schema-Erweiterung um ein generisches `canAdvance` ohne klares Wachstumsmodell — jedes Step-Issue dokumentiert seinen eigenen Validity-Flag. In #164 wird die Shell-Bedingung dann zu einem Pattern-Match konsolidiert (oder ein `state.canAdvance = $derived(switch currentStep)` eingefuehrt). Bis dahin: Inline-Bedingung pro Step.

### 8. TestID-Inventar

Alle TestIDs sind mit Prefix `trip-wizard-step1-*` versehen (kollisionsfrei zu Shell-IDs aus #160):

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-step1-profile` | Step-Container | Existiert bereits aus #160; bleibt als Wrapper |
| `trip-wizard-step1-chip-trekking` | Chip-Button | Toggle Trekking |
| `trip-wizard-step1-chip-skitour` | Chip-Button | Toggle Skitour |
| `trip-wizard-step1-chip-hochtour` | Chip-Button | Toggle Hochtour |
| `trip-wizard-step1-chip-klettersteig` | Chip-Button | Toggle Klettersteig |
| `trip-wizard-step1-chip-mtb` | Chip-Button | Toggle MTB |
| `trip-wizard-step1-name` | Text-Input | Trip-Name |
| `trip-wizard-step1-shortcode` | Text-Input | Trip-Kuerzel |
| `trip-wizard-step1-startdate` | Date-Input | Startdatum (ISO yyyy-mm-dd) |

Selektor-Strategie in E2E: `page.getByTestId('trip-wizard-step1-chip-skitour')`.

### 9. E2E-Helper `fillStep1` (Migration bestehender Tests)

5 Tests in `frontend/e2e/trip-wizard-shell.spec.ts` klicken aktuell ohne Step-1-Eingaben auf den Weiter-Button. Sobald `disabled` greift, brechen sie. Migration via Helper:

```typescript
// frontend/e2e/helpers.ts (oder als named export in trip-wizard-step1.spec.ts)
import type { Page } from '@playwright/test';

export interface Step1Input {
  activity: 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';
  name: string;
  shortcode?: string;
  startDate: string;  // 'YYYY-MM-DD'
}

export async function fillStep1(page: Page, input: Step1Input): Promise<void> {
  await page.getByTestId(`trip-wizard-step1-chip-${input.activity}`).click();
  await page.getByTestId('trip-wizard-step1-name').fill(input.name);
  if (input.shortcode !== undefined) {
    await page.getByTestId('trip-wizard-step1-shortcode').fill(input.shortcode);
  }
  await page.getByTestId('trip-wizard-step1-startdate').fill(input.startDate);
}
```

**Migration-Mapping fuer `trip-wizard-shell.spec.ts`:**

| Test | Aktion |
|------|--------|
| AC#5+#6 (Z. 38–44) | Vor `next.click()`: `await fillStep1(page, { activity: 'trekking', name: 'Test', startDate: '2026-06-01' })` |
| AC#5 (Z. 46–52) | Vor `next.click()`: gleicher `fillStep1`-Call |
| AC#5a (Z. 54–61) | **Semantik-Wechsel**: `await expect(next).toBeDisabled()` (initial), dann `fillStep1(...)`, dann `await expect(next).toBeEnabled()`, dann 3× klicken (bei jedem Step bleibt enabled, weil keine weiteren `canAdvance`-Flags existieren) |
| AC#8 (Z. 69–77) | Vor erstem `next.click()`: `fillStep1(...)` |
| AC#11 (Z. 79–88) | Vor erstem `next.click()`: `fillStep1(...)` |

### 10. Master-Spec-Changelog-Eintrag

`docs/specs/modules/epic_136_trip_wizard.md` erhaelt einen neuen Changelog-Eintrag (kein Approval-Reset, weil rein additive `$derived`-Erweiterung):

```markdown
- 2026-05-10: §3.1 erweitert um additives Feld
  `canAdvanceStep1 = $derived(activity !== null && name.trim().length > 0 && startDate != null && startDate.length > 0)`.
  Detail in Sub-Spec [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) §6. Folge-Steps
  (#162–#164) ergaenzen analog `canAdvanceStep2/3/4`.
```

## Expected Behavior

- **Input:** User navigiert zu `/trips/new` und sieht initial Step 1.
- **Output:**
  - 5 ProfileChips horizontal nebeneinander (oder umbrochen auf schmalen Viewports), jeder mit `aria-pressed`, alle initial `tone="default"`.
  - Drei Eingabefelder mit Labels „Name *", „Kuerzel" (optional-Marker), „Startdatum *".
  - Hilfetext unter Startdatum: „Das Enddatum wird in Schritt 2 aus den Etappen berechnet."
  - Weiter-Button im Footer initial **disabled**.
  - Klick auf Chip selektiert genau diesen einen (Toggle-Verhalten: Klick auf bereits gewaehlten Chip macht ihn NICHT ab — Auswahl ist exklusiv und Pflicht; Re-Klick wechselt auf gleichen Wert, kein no-op).
  - Sobald Activity + Name + Startdatum gesetzt sind, wird Weiter-Button enabled.
  - Klick auf Weiter wechselt zu Step 2 (Stage-Aufbau via #162).
- **Side effects:**
  - State-Mutationen: `state.activity`, `state.name`, `state.shortcode`, `state.startDate`.
  - Keine API-Calls in Step 1 (Save erfolgt erst in Step 4).
  - `state.canAdvanceStep1` ist `$derived` und reagiert reaktiv auf alle drei Pflicht-Bindings.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `Step1Profile.svelte` rendert 5 ProfileChips mit TestIDs `trip-wizard-step1-chip-{trekking,skitour,hochtour,klettersteig,mtb}` | E2E |
| 2 | Initial sind alle Chips `aria-pressed="false"`; nach Klick auf einen ist genau dieser `aria-pressed="true"` | E2E |
| 3 | Klick auf einen anderen Chip wechselt die Auswahl (genau ein Chip ist immer selektiert nach erstem Klick) | E2E |
| 4 | `Step1Profile.svelte` rendert drei Eingabefelder mit TestIDs `trip-wizard-step1-name`, `trip-wizard-step1-shortcode`, `trip-wizard-step1-startdate` | E2E |
| 5 | Kuerzel-Input hat `maxlength="20"` | E2E `getAttribute('maxlength')` |
| 6 | Startdatum-Input ist `type="date"` | E2E `getAttribute('type')` |
| 7 | Initial ist `[data-testid="trip-wizard-next"]` **disabled** | E2E `toBeDisabled` |
| 8 | Mit nur Activity gesetzt: Weiter weiterhin disabled | E2E |
| 9 | Mit Activity + Name (nur leer-getrimmt = `'   '`): Weiter weiterhin disabled | Unit-Test (`canAdvanceStep1` mit `name='   '` → false) |
| 10 | Mit Activity + Name + Startdatum: Weiter wird **enabled** | E2E |
| 11 | Mit Activity + Name + Kuerzel + Startdatum: Weiter enabled (Kuerzel optional) | E2E |
| 12 | Klick auf enabled Weiter-Button wechselt zu Step 2; Step-Indikator updated `data-state` (1=done, 2=active) | E2E |
| 13 | `Step1Profile`-Inhalt verschwindet beim Wechsel zu Step 2; State-Werte bleiben erhalten beim Zurueck-Klick | E2E (Werte in Inputs nach `Zurueck` noch da) |
| 14 | `state.activity`, `state.name`, `state.shortcode`, `state.startDate` werden korrekt mutiert (Unit-Test gegen `WizardState`-Instanz) | Unit-Test |
| 15 | `WizardState.canAdvanceStep1` ist `false` initial, `true` nach Setzen aller 3 Pflichtfelder, `false` wenn ein Pflichtfeld geloescht wird | Unit-Test (5 Cases: initial / nur activity / nur activity+name / activity+name+date / nach Loeschen) |
| 16 | Bestehende `trip-wizard-shell.spec.ts`-Tests AC#5, AC#5+#6, AC#5a, AC#8, AC#11 sind via `fillStep1`-Helper migriert; keine Test-Coverage geht verloren | Test-Run gruen |
| 17 | Master-Spec §3.1 hat neuen Changelog-Eintrag fuer `canAdvanceStep1` | Grep |
| 18 | `npm run check` und `npm run build` im `frontend/` gruen | CI-Output |
| 19 | Alle 5 ProfileChips sind ueber Tab-Taste erreichbar; Space oder Enter selektiert | E2E (`page.keyboard.press('Tab')` × N, dann `'Space'`) |
| 20 | ProfileChip hat sichtbaren Fokus-Ring (CSS `focus-visible:ring`) | E2E Visual-Check oder Screenshot |

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-wizard/__tests__/Step1Profile.test.ts` | Unit-Test fuer ProfileChip-Toggle-Logik (sofern in Plain-Node testbar) und Bindings-Smoke | ~60 |
| `frontend/e2e/trip-wizard-step1.spec.ts` | E2E-Tests AC #1–#13, #19, #20 | ~120 |

### EDIT

| Datei | Aenderung | LoC (Schaetzung) |
|-------|-----------|------------------|
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Stub gefuellt: ProfileChip-Loop, 3 Inputs, State-Bindings, Hilfetext | ~80 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `canAdvanceStep1` als `$derived` ergaenzen | +5 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | 5 Test-Cases fuer `canAdvanceStep1` ergaenzen (AC #15) | +25 |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Weiter-Button `disabled`-Prop ergaenzen (1-Zeilen-Edit) | +1 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | 5 Tests (AC#5, AC#5+#6, AC#5a, AC#8, AC#11) via `fillStep1`-Helper migrieren; AC#5a wechselt Semantik (`toBeDisabled` vor `fillStep1`) | ~30 |
| `frontend/e2e/helpers.ts` | Optional: `fillStep1` und `Step1Input` exportieren (Wieder-Verwendung) | +25 |
| `docs/specs/modules/epic_136_trip_wizard.md` | Changelog-Eintrag fuer `canAdvanceStep1` | +5 |

### NICHT BERUEHRT

- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` (Schema unveraendert; `mapActivityToProfile` erst in #164 wieder relevant)
- `frontend/src/routes/trips/new/+page.svelte` (Mount-Punkt unveraendert)
- `frontend/src/lib/components/trip-wizard/Stepper.svelte` (pure presentational, keine Aenderung)
- Andere `steps/Step{2,3,4}*.svelte` (Folge-Issues #162–#164)
- `internal/`, `src/`, `cmd/` (kein Backend-Touch)

## Known Limitations

- **`endDate` wird nicht in Step 1 erfasst.** Issue-Beschreibung sagt „Zeitraum"; Master-Spec sagt „derived in Step 2". Spec folgt der Master-Spec, weil Doppeleingabe-Konflikt-Logik vermieden wird. Falls User-Feedback Enddatum-Eingabe in Step 1 fordert, ist die Erweiterung trivial: zusaetzlicher Date-Input + `state.endDate`-Binding + Erweiterung von `canAdvanceStep1`.
- **Kein Datums-Konflikt-Check** zwischen `startDate` und `endDate` (Letzterer wird in Step 2 gesetzt). Wenn User ein vergangenes Startdatum waehlt, kein Block — Free-Text wie alle anderen Felder.
- **Kein Konflikt-Check fuer ueberlappende Trip-Zeitraeume.** Master-Spec §Known Limitations dokumentiert das als Folge-Issue-Konzern — Sub-Spec #161 implementiert das nicht.
- **Kein Shortcode-Eindeutigkeits-Check.** Backend speichert beliebige Strings. Falls UI spaeter „Trip-Liste sortiert nach Kuerzel" implementiert und Konflikte auftreten, ist das ein eigener Spec.
- **Inline-Bedingung am Weiter-Button** statt Generic `state.canAdvance`: Verfrueht zu konsolidieren, weil Wachstumsmodell unklar (jeder Step hat eigene Validity-Regeln). Konsolidierung in #164 oder Cleanup-Folge-Issue moeglich.
- **HTML5-Date-Picker UX** ist Browser-nativ — auf iOS/Android-Mobile vergleichsweise begrenzt. Kein Show-Stopper; Wechsel auf eine shadcn-DateField-Variante ist Folge-Issue.
- **ProfileChip ohne Icons** — Issue-Text gibt nur Text-Labels vor. Lucide-Icons (z.B. mountain, ski, hammer, helmet, bike) waeren Visual-Polish, sind aber Spec-Erweiterung; Sub-Spec haelt Initial-Implementierung minimal.
- **Re-Klick auf gewaehlten Chip macht ihn NICHT ab.** Pattern: einmal gewaehlt, bleibt gewaehlt (Wechsel nur durch anderen Chip-Klick). Begruendung: `activity` ist Pflichtfeld; "deselect" wuerde den State invalidisieren ohne UI-Path zur Recovery (User muesste anderen Chip klicken). Akzeptierter UX-Trade-off.

## Not In Scope

- **Step-2/3/4-Inhalte und deren `canAdvance`-Flags** — eigene Sub-Issues #162–#164.
- **`state.canAdvance` als generisches Switch-`$derived`** — Konsolidierung in #164 oder Cleanup.
- **Shortcode-Eindeutigkeit** und Konflikt-Warnung bei ueberlappenden Trip-Zeitraeumen.
- **Backend-Aenderungen.**
- **Lucide-Icons fuer ProfileChips.**
- **Mobile-spezifische Date-Picker-Anpassungen.**
- **Vorausfuellung aus Trip-Vorlagen** (#165 — Vorlagen-Picker).

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
  - §1.2 Datenmodell (`ActivityType`, `Trip.shortcode`, `Trip.activity`)
  - §1.3 Mapping UI-Aktivitaet → Aggregations-Profil
  - §3.1 WizardState (Felder Step 1, Erweiterung um `canAdvanceStep1`)
  - §4 Vertraege Master-Spec ↔ Sub-Specs
- **Vorgaenger-Sub-Spec:** [`epic_136_step0_shell.md`](./epic_136_step0_shell.md) (#160 Shell + Stepper, §Step-Validation-Pattern)
- **Atom-Komponenten:** Epic #133 Lauf B (`Pill`, `Btn`, `Eyebrow`, `GCard`, `Input`)
- **Issue:** [#161 — Step 1: Aktivitaetsprofil + Eckdaten](https://github.com/henemm/gregor_zwanzig/issues/161)
- **Phase-1+2-Kontext:** `docs/context/issue-161-wizard-step1-profil.md`

## Changelog

- 2026-05-10: Sub-Spec aus Stub ausgefuellt — Layout-Wireframe, ProfileChip-a11y-Pattern (button-Wrapper um Pill mit `aria-pressed`), 5 Profile in fester Reihenfolge, drei Eingabefelder (Name Pflicht, Kuerzel optional max 20, Startdatum Pflicht ISO), `endDate` bewusst NICHT in Step 1 erfasst (User-Entscheidung deckt sich mit Master-Spec §3.1 Z. 253), `WizardState.canAdvanceStep1` als additive `$derived`-Erweiterung mit Master-Spec-Changelog, Shell-Mini-Edit (1-Zeilen-`disabled`-Prop am Weiter-Button mit `currentStep === 1`-Gate), TestID-Inventar mit Prefix `trip-wizard-step1-*`, `fillStep1`-E2E-Helper fuer Migration der 5 brechenden Shell-Tests (AC#5a wechselt Semantik), 20 Acceptance Criteria, Datei-Liste (2 NEU + 7 EDIT, geschaetzt ~85 LoC Produktionscode + ~205 LoC Tests + ~5 LoC Spec-Patches). Status `stub` → `draft`, Version `0.1` → `1.0`.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
