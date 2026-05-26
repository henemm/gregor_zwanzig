---
entity_id: issue_391_trip_wizard_atomic
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, atomic-design, trip-wizard, epic-368, phase-2, svelte, issue-391]
---

<!-- Issue #391 — Epic #368 Phase 2 (6/6): Touren-Assistent /trips/new auf Atomic-Bibliothek migrieren -->

# Issue #391 — Trip-Wizard Atomic-Migration (`/trips/new`)

## Approval

- [ ] Approved

## Zweck

Der Touren-Assistent (`/trips/new`) nutzt an sieben Stellen noch Inline-Stile und Ad-hoc-HTML-Elemente statt der Atomic-Design-Bibliothek. Diese Migration bringt Stepper, Etappen-Liste, Formulareingaben und Shell-Texte auf die etablierten Atome und Molecules (`Pill`, `Btn`, `Field`, `CheckIcon`), die in Epic #368 Phase 1 aufgebaut wurden. Ergebnis: konsistentes Erscheinungsbild mit dem Rest der Anwendung, keine Drift-Risiken bei Token-Änderungen und ein vollständig testbarer Komponentenbaum ohne Code-Duplizierung.

## Quelle / Source

**Geänderte Dateien (alle im Frontend-Layer):**

| Datei | Art der Änderung |
|-------|-----------------|
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Done-State: Dot → CheckIcon |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | WP-Count Badge hinzufügen |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Vorschläge-Span → Pill-Atom, Header-Btns |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Inputs in Field-Molecule wrappen |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | Aktivitätsprofil-Select in Field wrappen |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Dynamischer H1, Eyebrow-Format, Footer-Hinweise |

**Nicht geänderte Dateien:**

- `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` — bereits Atomic-konform
- `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` — nicht gemountet, nicht anfassen
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` — nicht gemountet, nicht anfassen
- `frontend/src/lib/stores/wizardState.svelte.ts` — WizardState-Logik unverändert
- Stage-Interface — wird nicht erweitert

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im SvelteKit-Frontend-Layer (`frontend/src/lib/components/trip-wizard/`). Python-Backend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/atoms` | Atomic-Bibliothek (Atoms) | Stellt `Pill`, `Btn` bereit |
| `$lib/components/molecules` | Atomic-Bibliothek (Molecules) | Stellt `Field`-Molecule für Label+Input-Wrapping bereit |
| `@lucide/svelte/icons/check` | Icon-Library | Liefert `CheckIcon` für Done-State im Stepper |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Wizard-Komponente | Zeigt Schritt-Fortschritt; Done-State wird von Dot auf CheckIcon migriert |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | Wizard-Komponente | Etappen-Zeile; erhält WP-Count-Badge |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Wizard-Komponente | Etappen-Übersicht; Vorschläge-Span → Pill, Header-Btns |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Wizard-Komponente | Profil-Formular; Inputs werden in Field-Molecule eingebettet |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | Wizard-Komponente | Wetter-Einstellungen; Select wird in Field-Molecule eingebettet |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Wizard-Shell | Rahmen-Komponente; H1, Eyebrow und Footer-Hinweise werden dynamisch per Step |
| `frontend/src/lib/components/trip-wizard/__tests__/*.test.ts` | Test-Suite | Bestehende Tests müssen nach Migration grün bleiben (73+ data-testid erhalten) |
| `frontend/src/lib/contrast-audit.test.ts` | Test-Suite | WCAG-Kontrast-Audit; darf durch Migration keine neuen Verletzungen einführen |

## Implementation Details

### 1. Stepper.svelte — Done-State: Dot → CheckIcon

`Dot`-Import entfernen. Im Done-Zweig des Stepper-Templates `<Dot tone="success" />` ersetzen durch:

```svelte
<CheckIcon class="size-4 text-[var(--g-success)]" />
```

Import ergänzen:

```svelte
import CheckIcon from '@lucide/svelte/icons/check';
```

Das Attribut `data-state="done|active|pending"` am Step-Element bleibt unverändert erhalten.

### 2. StageRow.svelte — WP-Count Badge

Nach dem Stage-Pill, aber nur wenn `!isPause && stage.waypoints.length > 0`, ein Pill-Atom einfügen:

```svelte
{#if !isPause && stage.waypoints.length > 0}
  <Pill tone="ghost" data-testid="trip-wizard-step2-stage-wp-count-{index}">
    {stage.waypoints.length} WP
  </Pill>
{/if}
```

Import ergänzen:

```svelte
import { Pill } from '$lib/components/atoms';
```

Hinweis: Das Stage-Interface hat keine `km`/`ascent`-Felder — diese Felder werden nicht implementiert. Das `<input type="date">` für die Datumseingabe bleibt unverändert (Editing-Funktionalität erhalten).

### 3. Step2Stages.svelte — Vorschläge-Span → Pill + Header-Btns

**Vorschläge-Span ersetzen** (Zeile ~130–137):

```svelte
<!-- Vorher -->
<span class="shrink-0 rounded-full border border-dashed border-[var(--g-accent)]/60 ...">
  +{suggested} Vorschläge
</span>

<!-- Nachher -->
<Pill
  tone="accent"
  data-outlined
  class="border-dashed shrink-0"
  data-testid="trip-wizard-step2-suggested-pill-{i}"
>
  +{suggested} Vorschläge
</Pill>
```

**Header-Buttons hinzufügen** (Platzhalter, benannte No-op-Handler):

```svelte
<Btn onclick={handleMerge} data-testid="trip-wizard-step2-btn-merge">
  Zusammenführen
</Btn>
<Btn onclick={handleInsert} data-testid="trip-wizard-step2-btn-insert">
  + Etappe einschieben
</Btn>
```

Handler im `<script>`-Block (No-ops, Safari-konform):

```ts
function handleMerge() {}
function handleInsert() {}
```

Imports ergänzen:

```svelte
import { Pill, Btn } from '$lib/components/atoms';
```

### 4. Step1Profile.svelte — Inputs in Field-Molecule wrappen

Die drei Felder TRIP-NAME, REGION und STARTDATUM werden in das `Field`-Molecule eingebettet. Native `<input>`-Elemente bleiben erhalten (bind:value funktioniert); `data-testid` bleibt am `<input>`, nicht am Field-Wrapper.

```svelte
import { Field } from '$lib/components/molecules';
```

Beispiel für TRIP-NAME:

```svelte
<Field label="TRIP-NAME">
  <input
    bind:value={wizardState.name}
    data-testid="trip-wizard-step1-name"
    type="text"
    ...
  />
</Field>
```

Analog für REGION (`data-testid="trip-wizard-step1-region"`) und STARTDATUM (`data-testid="trip-wizard-step1-start-date"`).

Das Field-Molecule setzt automatisch Mono-Uppercase-Label-Stil (`font-mono`, `text-transform: uppercase`) — keine zusätzliche CSS-Klasse nötig.

### 5. Step3Weather.svelte — Aktivitätsprofil-Select in Field wrappen

Das bestehende `<select>` für das Aktivitätsprofil wird in ein Field-Molecule eingebettet:

```svelte
import { Field } from '$lib/components/molecules';
```

```svelte
<Field label="AKTIVITÄTSPROFIL">
  <select
    bind:value={wizardState.activityProfile}
    data-testid="activity-dropdown"
    ...
  >
    <!-- Options unverändert -->
  </select>
</Field>
```

`data-testid="activity-dropdown"` bleibt am `<select>` (nicht am Field-Wrapper). Die Badges "AM WICHTIGSTEN" / "HINZUGEFÜGT" werden nicht implementiert — kein State-Fundament vorhanden; Folge-Issue.

### 6. TripWizardShell.svelte — Dynamischer H1, Eyebrow, Footer-Hinweise

**H1-Titel-Map** (readonly, im `<script>`-Block):

```ts
const stepTitles: Record<number, string> = {
  1: 'Route — wie kennt das System deinen Weg?',
  2: 'Etappen — stimmt die Tagesaufteilung?',
  3: 'Wetter — welche Daten gehen ins Briefing?',
  4: 'Reports — wann und wohin?'
};
```

**Footer-Hinweis-Map**:

```ts
const stepHints: Record<number, string | null> = {
  1: 'GPX-Upload empfohlen — manuelle Eingabe geht auch.',
  2: 'Algorithmische Wegpunkte sind orange gestrichelt — bestätigen oder verwerfen.',
  3: null,
  4: 'Unterwegs läuft alles autark. Kein Eingreifen nötig.'
};
```

**Eyebrow** (reaktiv auf `currentStep`):

```svelte
<Eyebrow>SCHRITT {currentStep} VON 4 · NEUE TOUR</Eyebrow>
```

**H1**:

```svelte
<h1>{stepTitles[currentStep]}</h1>
```

**Footer-Hinweis** (zwischen Zurück- und Weiter-Button, italic, zentriert):

```svelte
{#if stepHints[currentStep]}
  <p class="text-center italic text-[var(--g-ink-muted)]">
    {stepHints[currentStep]}
  </p>
{/if}
```

### LoC-Budget

| Datei | Δ LoC (geschätzt) | Zählt |
|-------|-------------------|-------|
| `Stepper.svelte` | ~5 | ja |
| `StageRow.svelte` | ~8 | ja |
| `Step2Stages.svelte` | ~18 | ja |
| `Step1Profile.svelte` | ~20 | ja |
| `Step3Weather.svelte` | ~10 | ja |
| `TripWizardShell.svelte` | ~25 | ja |
| **Gesamt (netto)** | **~86** | **unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Nutzer navigiert durch die 4 Schritte des Touren-Assistenten (`/trips/new`)
- **Output:**
  - Stepper zeigt für abgeschlossene Schritte ein `CheckIcon` statt eines Dots
  - Etappen mit Wegpunkten zeigen einen WP-Count-Badge (ghost-Pill)
  - Vorschläge-Elemente sind `Pill`-Atome mit accent-tone und gestricheltem Rand
  - Formular-Eingaben (TRIP-NAME, REGION, STARTDATUM, AKTIVITÄTSPROFIL) haben Mono-Uppercase-Labels via Field-Molecule
  - Shell zeigt step-spezifische H1-Titel, Eyebrow im Format "SCHRITT N VON 4 · NEUE TOUR" und (wo definiert) einen kursiven Footer-Hinweis
- **Side effects:** Keine Änderungen an WizardState-Logik, keinen Stage-Interface-Feldern, keinen bestehenden data-testid-Attributen oder an nicht gemounteten Step-Komponenten

## Acceptance Criteria

- **AC-1:** Given der Wizard ist auf Schritt 3 (Wetter) / When der Nutzer den Stepper sieht / Then zeigen Schritt 1 und 2 ein Checkmark-Icon (nicht einen Dot), Schritt 3 eine orange Kreis-Zahl und Schritt 4 eine ausgegraunte Kreis-Zahl

- **AC-2:** Given der Wizard ist auf Schritt 2 (Etappen) / When die Seite gerendert wird / Then zeigt die Eyebrow "SCHRITT 2 VON 4 · NEUE TOUR" und der H1 zeigt "Etappen — stimmt die Tagesaufteilung?"

- **AC-3:** Given der Wizard ist auf Schritt 1 / When die Seite gerendert wird / Then erscheint im Footer der kursive Hinweistext "GPX-Upload empfohlen — manuelle Eingabe geht auch." und auf Schritt 3 erscheint kein Footer-Hinweis

- **AC-4:** Given der Wizard zeigt Schritt 1 (Route) / When die Formularfelder gerendert werden / Then haben TRIP-NAME, REGION und STARTDATUM Mono-Uppercase-Labels via Field-Molecule; die data-testid-Attribute liegen an den `<input>`-Elementen, nicht am Field-Wrapper

- **AC-5:** Given Schritt 2 zeigt eine Etappe mit mindestens einem Wegpunkt / When die Stage-Zeile gerendert wird / Then erscheint ein Badge "X WP" (Pill, ghost-tone) mit `data-testid="trip-wizard-step2-stage-wp-count-{index}"`; bei Etappen ohne Wegpunkte erscheint kein Badge

- **AC-6:** Given Schritt 2 zeigt eine Etappe mit vorgeschlagenen Wegpunkten / When die Stage-Zeile gerendert wird / Then ist das Element `data-testid="trip-wizard-step2-suggested-pill-N"` ein Pill-Atom (`data-slot="pill"`) mit accent-tone und `data-outlined`-Attribut und hat die CSS-Klasse `border-dashed`

- **AC-7:** Given Schritt 2 wird angezeigt / When der Header der Etappen-Liste gerendert wird / Then sind Buttons "Zusammenführen" (`data-testid="trip-wizard-step2-btn-merge"`) und "+ Etappe einschieben" (`data-testid="trip-wizard-step2-btn-insert"`) sichtbar; ein Klick löst keinen Fehler aus

- **AC-8:** Given alle 6 Dateien sind implementiert / When `cd frontend && npx svelte-check` und `node --test src/lib/contrast-audit.test.ts` laufen / Then gibt es 0 Typ-Fehler, 0 Kontrast-Verletzungen und 0 Console-Errors

- **AC-9:** Given alle Änderungen sind implementiert / When `cd frontend && node --experimental-strip-types --test src/lib/components/trip-wizard/__tests__/*.test.ts` läuft / Then sind alle bestehenden Tests grün (WizardState-Logik byte-gleich, 73+ data-testid erhalten)

## Known Limitations

- **Header-Btns sind No-ops:** "Zusammenführen" und "+ Etappe einschieben" in Step 2 sind Platzhalter ohne Logik. Die tatsächliche Zusammenführungs- und Einschub-Funktion ist ein Folge-Issue und setzt Erweiterungen am WizardState voraus.
- **Badges "AM WICHTIGSTEN" / "HINZUGEFÜGT"** in Step 3 werden nicht implementiert — kein State-Fundament vorhanden. Folge-Issue.
- **Kein km/ascent in StageRow:** Das Stage-Interface hat keine `km`/`ascent`-Felder; diese Anzeige ist in dieser Migration nicht umsetzbar.
- **Field-Molecule-Stil:** Die Mono-Uppercase-Labels in Field setzen voraus, dass das Molecule die korrekte CSS-Variable (`font-mono`, `text-transform: uppercase`) intern setzt. Abweichungen vom Soll-Design sind ein Upstream-Problem in der Molecules-Schicht.

## Out of Scope

- Änderungen an `WizardState` (`wizardState.svelte.ts`) oder am Stage-Interface
- Step4Reports.svelte (bereits Atomic-konform)
- Step3Waypoints.svelte und Step4Briefings.svelte (nicht gemountet im aktuellen Shell)
- Echtfunktionalität der Platzhalter-Buttons in Step 2
- "AM WICHTIGSTEN" / "HINZUGEFÜGT" Badges in Step 3
- Python-Backend oder Go-API

## Changelog

- 2026-05-26: Initial spec erstellt. Epic #368 Phase 2 (6/6): Migration von 6 Wizard-Komponenten auf Atomic-Bibliothek. Stepper Done-State, WP-Count Badge, Vorschläge-Pill, Field-Molecule für Inputs, dynamischer H1/Eyebrow/Footer im Shell. ~86 LoC Netto-Delta.
