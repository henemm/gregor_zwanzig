---
workflow: issue-160-wizard-shell-stepper
phase: phase1_context
created: 2026-05-10
issue: 160
parent_epic: 136
related_master_spec: epic_136_trip_wizard
---

# Context: Issue #160 — Wizard-Shell + 4-Schritt-Stepper

## Request Summary

Wizard-Shell (`TripWizardShell.svelte`) + Stepper-Komponente (`Stepper.svelte`) als Wrapper-Layout für den neuen 4-Schritt Trip-Wizard auf `/trips/new`. Steps 1–4 sind initial leere Platzhalter; gefüllt werden sie in Sub-Issues #161–#164. Master-Spec `epic_136_trip_wizard.md` ist bereits approved, Datenmodell und State-Klasse implementiert — diese Sub-Spec liefert nur das UI-Detail der Shell und des Stepper-Atoms.

## Master-Spec Vertrag

`docs/specs/modules/epic_136_trip_wizard.md` (approved 2026-05-09) garantiert:
1. `WizardState`-Klasse aus `wizardState.svelte.ts` ist verfügbar — Shell stellt sie via `setContext('trip-wizard-state', state)` bereit.
2. `wizardHelpers.ts` exportiert alle 6 Helper (`newId`, `today`, `addDays`, `mapActivityToProfile`, `formatStageNumber`, `isPauseStage`).
3. Datenmodell-Felder `Trip.shortcode`, `Trip.activity`, `Waypoint.suggested` sind BE+FE persistierbar/typisiert.
4. Save-Pipeline (`state.save()`) liegt in `WizardState` — Step 4 ruft sie nur auf.

**Sub-Spec #160 muss liefern:** UI-Detail Layout/Atom-Verwendung/Validierung/E2E-Tests für **TripWizardShell** und **Stepper** — KEINE Änderungen am State-Schema, KEINE Step-Inhalte.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EXISTIERT — Shell instanziiert `new WizardState()` und setContextet |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | EXISTIERT — keine Aufrufe in Shell direkt nötig |
| `frontend/src/lib/components/trip-wizard/__tests__/*.test.ts` | EXISTIERT — Helper-/State-Smoke-Tests grün, Shell braucht eigenen Test |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | NEU — diese Sub-Spec |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | NEU — diese Sub-Spec |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | NEU als leerer Platzhalter (Inhalt = Folge-Issue #161) |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | NEU als leerer Platzhalter (#162) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | NEU als leerer Platzhalter (#163) |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | NEU als leerer Platzhalter (#164) |
| `frontend/src/routes/trips/new/+page.svelte` | EDIT — mountet `TripWizardShell` statt altem `TripWizard` |
| `frontend/src/lib/components/wizard/TripWizard.svelte` | UNANGETASTET (Edit-Pfad-Folge-Issue) |
| `frontend/src/lib/components/wizard/WizardStepper.svelte` | REFERENZ — alter Stepper, Layout-Inspiration |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | DEPENDENCY — Vor/Zurück/Speichern-Buttons (variant: accent/ghost/outline, size sm/md/lg) |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | DEPENDENCY — Stepper-State-Indikator (tone success für done) |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | DEPENDENCY — Step-Eyebrow ("Schritt 2 von 4") |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | DEPENDENCY — Container für Step-Inhalt |
| `frontend/src/app.css` | DEPENDENCY — Design-Tokens (--g-accent, --g-paper, --g-ink, --g-success) |
| `frontend/e2e/trip-wizard.spec.ts` | KONFLIKT — testet ALTEN Wizard mit Labels Route/Etappen/Wetter/Reports → neue Tests für #160 brauchen neue Labels und neue Datei (siehe §Risks) |
| `docs/specs/modules/epic_136_step0_shell.md` | EDIT — Stub ist da, Phase 3 füllt aus |

## Existing Patterns

### Stepper-Pattern (alter `WizardStepper.svelte`)
- Props: `steps: string[]`, `current: number` (0-based)
- Pro Step: Kreis (8×8 rounded-full) mit Nummer oder CheckIcon, darunter Label
- Connector-Linie zwischen Steps (`flex-1 h-0.5`)
- Tone via Tailwind-Token-Klassen (`bg-primary`, `bg-muted`)
- `data-testid="wizard-stepper"` + `data-testid="wizard-step-{n}"` + `data-active="true|false"`

**Neuer Stepper soll:**
- Atom `Dot` für Status-Indikator nutzen (Token-konsistent: `tone="success"` für done; aktiv = Akzent-Background)
- Done/Active/Pending-Visualisierung (Spec §Stepper-Komponente: 1–4, aktiv/done/pending)
- Sub-Label aus Issue-Beschreibung Epic #136 ("Stepper oben: Schritt-Nummer, Label, Sub-Label, Done-Checkmark")
- testIDs neu: `data-testid="trip-wizard-stepper"`, `data-testid="trip-wizard-step-{1..4}"`, `data-state="done|active|pending"` (Konvention statt `data-active`)

### Shell-Pattern (alter `TripWizard.svelte`)
- Header (`h1`): "Neuer Trip"
- Stepper
- Step-Slot (`min-h-[300px]`)
- saveError-Box
- Footer mit Zurück/Abbrechen/Weiter|Speichern
- testIDs: `trip-wizard`, `wizard-back`, `wizard-cancel`, `wizard-next`, `wizard-save`

**Neue Shell soll:**
- WizardState via `setContext('trip-wizard-state', state)` (Vertrag Master-Spec §4.1)
- Step-Komponenten via `{#if state.currentStep === N}` rendern (Step1Profile.svelte etc.)
- Vor: Master-Spec sagt nichts dazu, ob `canProceed` zentralisiert werden soll → Sub-Spec entscheidet (Empfehlung: Validierung pro Step bleibt in Step-Komponente, Shell ruft `state.nextStep()` ohne Validation; Steps disablen den Weiter-Button selbst via Context)
- Save-Button im letzten Schritt: `state.save()`, gibt UI-Feedback aus `state.saveStatus` und `state.saveError`
- Cancel-Verhalten: `goto('/')` (Cockpit) — Begründung: Master-Spec §1 nennt Trip-Cockpit als Einstiegspunkt
- testIDs: `trip-wizard-shell`, `trip-wizard-back`, `trip-wizard-cancel`, `trip-wizard-next`, `trip-wizard-save`

### Atom-Verwendung (Bsp. aus Cockpit)
```svelte
import { Btn } from '$lib/components/ui/btn';
import { Eyebrow } from '$lib/components/ui/eyebrow';
import { GCard } from '$lib/components/ui/g-card';
import { Dot } from '$lib/components/ui/dot';

<Btn variant="accent" size="md" onclick={...}>Weiter</Btn>
<Btn variant="ghost" onclick={...}>Abbrechen</Btn>
<Eyebrow>Schritt 2 von 4</Eyebrow>
<Dot tone="success" size="sm" />
```

### Test-Setup
- Unit-Tests: `node --experimental-strip-types --test` (kein Vitest)
- Svelte-5-Runen werden in Tests als Identity-Funktionen gepatcht (`$state = (v) => v`) — siehe `wizardState.test.ts`
- E2E: Playwright unter `frontend/e2e/`, `webServer: bash e2e/start-preview.sh` auf Port 4173, Auth via `playwright/.auth/admin.json` (siehe `global.setup.ts`)

## Dependencies

**Upstream (was Shell+Stepper benutzen):**
- `WizardState`-Klasse (Master-Spec §3.1) — Single Source of Truth für `currentStep`, `nextStep()`, `prevStep()`, `save()`, `saveStatus`, `saveError`
- Atom-Komponenten Btn, Dot, Eyebrow, GCard aus Epic #133
- SvelteKit `goto` für Cancel/Save-Redirect
- Lucide Icon `CheckIcon` (oder Atom-Dot mit tone success — Sub-Spec entscheidet)

**Downstream (was Shell+Stepper benutzen wird):**
- `frontend/src/routes/trips/new/+page.svelte` — mountet `TripWizardShell`
- Sub-Issues #161–#164 — Step-Komponenten konsumieren WizardState via `getContext('trip-wizard-state')`

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — **Master-Spec (approved)**, Single Source of Truth für Datenmodell, State, Helper, Verzeichnisstruktur
- `docs/specs/modules/epic_136_step0_shell.md` — **Stub**, wird in Phase 3 ausgefüllt (diese Sub-Spec)
- `docs/specs/modules/epic_133_design_system_lauf_b.md` — Atom-Komponenten Btn/GCard/Eyebrow/Dot/Pill (Vertrag, was Stepper nutzen darf)

## Risks & Considerations

### R1: Alte E2E-Tests werden brechen
`frontend/e2e/trip-wizard.spec.ts` testet den ALTEN Wizard (Labels Route/Etappen/Wetter/Reports, testIDs `wizard-stepper`, `wizard-step-*`, `wizard-back/next/cancel/save`). Sobald `/trips/new` auf `TripWizardShell` umstellt, brechen ~20 Tests dieser Datei. **Mitigation:** Sub-Spec #160 sagt explizit:
- Neue Tests in `frontend/e2e/trip-wizard-shell.spec.ts` (separater Spec)
- Alte `trip-wizard.spec.ts` als `.skip` markieren oder löschen, mit Verweis auf das Cleanup-Folge-Issue (Master-Spec §Delete: gehört in Cleanup-Issue, nicht hier)
- Nicht löschen, weil der alte Edit-Pfad noch den alten Wizard rendern könnte (über `TripEditView`) — kurz prüfen, dann entscheiden

### R2: Cancel-Ziel
Master-Spec äußert sich nicht zu Cancel-Verhalten. Alter Wizard geht zu `/trips` (Liste). Cockpit-Pattern (Epic #134) hat `/` als Hauptseite. **Empfehlung:** Cancel → `/` (Cockpit), weil Issue-Beschreibung Epic #136 das Cockpit als Einstiegspunkt benennt; bei kontroverser Entscheidung in Sub-Spec dokumentieren.

### R3: Step-Validation-Verantwortung
Shell vs. Step: Alter Wizard hatte `canProceed()` zentral in `TripWizard.svelte`. Neue Architektur mit Context-State öffnet zwei Pfade:
- **A:** Step-Komponenten setzen `state.canAdvance` Flag
- **B:** Step-Komponenten exportieren ein `valid()`-Snippet
- **C:** Shell delegiert nur, jeder Step disabled seinen eigenen "Weiter"-Button via Context

**Empfehlung:** **C** — disabled-Logik bleibt im Step. Shell rendert "Weiter"-Button mit `disabled={false}` und Step kann via `disableNext` im State setzen. Alternativ: jeder Step rendert seinen eigenen Footer (wäre aber Bruch der Shell-Verantwortung). Sub-Spec wählt eine Option und begründet.

### R4: Stepper Sub-Label
Epic #136 Beschreibung sagt "Schritt-Nummer, Label, Sub-Label, Done-Checkmark". **Sub-Label** ist nicht definiert — Vorschlag: kurze Beschreibung (z.B. Step 2 = "GPX-Import", Sub-Label "Mehrere Dateien hochladen"). Wird in Sub-Spec #160 fixiert; einzelne Steps können ihn dort als Konstante einsetzen.

### R5: Worktree-Isolation für Developer
Issue ist UI-only (kein Backend). Developer arbeitet in Worktree, schreibt nur:
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` (NEU)
- `frontend/src/lib/components/trip-wizard/Stepper.svelte` (NEU)
- `frontend/src/lib/components/trip-wizard/steps/Step{1..4}*.svelte` (NEU, leere Platzhalter)
- `frontend/src/routes/trips/new/+page.svelte` (EDIT, 3 Zeilen)
- `frontend/e2e/trip-wizard-shell.spec.ts` (NEU)
- `frontend/src/lib/components/trip-wizard/__tests__/Stepper.test.ts` (NEU, optional — Stepper ist pure-render, E2E reicht ggf.)

Keine Berührung von `internal/`, `src/`, `cmd/` — daher kein Backend-Build, kein Schema-Snapshot.

### R6: ESLint/Prettier/svelte-check
SvelteKit-Config nutzt `svelte-check`. Nach Implementierung muss `npm run check` im `frontend/` grün sein. Auch Playwright-Webserver baut über `vite build` — nach Änderung: `npm run build` muss durchlaufen.

## Vorab-Tech-Lead-Empfehlung (für Phase 2 Analyse)

1. **Stepper als pure presentational Komponente:** nimmt `current: 1|2|3|4` und liefert reine Darstellung. Keine eigene State-Klasse, kein Context-Konsum. Macht Stepper testbar ohne State-Setup.
2. **Shell hält den Context:** instanziiert `WizardState`, setContextet ihn, rendert Stepper + dynamische Step-Komponente + Footer.
3. **Pattern C** für Step-Validation (jeder Step kontrolliert seinen Weiter-Button-Disabled-Zustand via Context-Flag, das vom State-Schema her ergänzt werden muss — Master-Spec ist hier offen, könnte mit `state.canAdvance` ergänzt werden, was wir in der Sub-Spec festlegen).
4. **TestIDs neu prefixen** (`trip-wizard-*`) statt alte (`wizard-*`) — vermeidet Kollisionen mit dem alten Wizard, der parallel existiert.
5. **Cancel → `/`** (Cockpit), nicht `/trips`.
6. **Alte E2E-Datei `trip-wizard.spec.ts`** in dieser Sub-Spec NICHT anfassen — der alte Wizard läuft noch im Edit-Pfad. Stattdessen alte Datei `.skip()`-en mit Kommentar "deprecated by Epic #136 — gone with cleanup issue".

---

## Phase 2 — Analyse-Ergebnisse (2026-05-10)

### Architektur-Empfehlung

- **Single-Source-of-Truth-State per Svelte-Context.** `+page.svelte` instanziiert `WizardState` (innerhalb `<script>`-Block, nicht top-level — Safari-Reaktivität!) und legt sie via `setContext('trip-wizard-state', state)` ab. Shell und Step-Platzhalter konsumieren via `getContext`.
- **Stepper ist 100% pure presentational** — Props `current: 1|2|3|4` und `labels: string[]`. Wiederverwendbar, trivial unit-testbar, kein State-Setup nötig.
- **Shell orchestriert** — Header (`<h1>` + `Eyebrow`), Stepper, Step-Slot via `{#if state.currentStep === N}`, Footer mit `Btn`-Atomen, Save-Status-Region (`role="status"`).
- **4 leere Step-Platzhalter** mit eindeutigem `data-testid="trip-wizard-step{N}"`-Anker — sonst sind Navigations-E2E-Tests nicht schreibbar.

### Implementierungsreihenfolge (TDD-RED)

1. E2E-Tests in `frontend/e2e/trip-wizard-shell.spec.ts` (alle rot)
2. Stepper-Unit-Test in `frontend/src/lib/components/trip-wizard/__tests__/Stepper.test.ts` (rot)
3. `Stepper.svelte` implementieren — pure presentational
4. 4 Step-Platzhalter (`steps/Step{1..4}*.svelte`) — je ~10 LoC
5. `TripWizardShell.svelte` mit Footer-Buttons und Save-Status
6. `frontend/src/routes/trips/new/+page.svelte` umstellen (mountet Shell)
7. Alte E2E-Tests `frontend/e2e/trip-wizard.spec.ts` per `.skip()` deaktivieren
8. `frontend/npm run check` und `npm run build` grün

### Begründete Entscheidungen

| # | Frage | Entscheidung | Begründung |
|---|-------|--------------|------------|
| 1 | Step-Validation | **In Sub-Spec dokumentieren** (`state.canAdvance` als `$derived` mit pro-Step-Validity-Flags) — **in #160 NICHT implementieren** (Steps sind leer, Footer-Button immer enabled). Master-Spec-Erweiterung erfolgt in #161 ff. | Vermeidet Schema-Erweiterung im Sub-Issue ohne Master-Spec-Update; Pattern wird in Sub-Spec festgelegt für Folge-Issues. |
| 2 | Cancel-Ziel | **`/` (Cockpit)** | Cockpit ist der User-Recovery-Pfad (Epic #134); `/trips` ist Zwischenschritt. |
| 3 | TestID-Prefix | **`trip-wizard-*`** (z.B. `trip-wizard-shell`, `trip-wizard-stepper`, `trip-wizard-step-{1..4}`, `trip-wizard-next/back/cancel/save`, `trip-wizard-save-status`) | Alter Wizard lebt parallel in `/trips/[id]/edit`; Prefix verhindert Selektor-Kollisionen. |
| 4 | Alte E2E-Tests | **`test.describe.skip()`** mit Kommentar "Cleanup nach Epic #136-Abschluss — alter Wizard noch im Edit-Pfad" | Löschen würde Edit-Pfad-Coverage silently verlieren; Anpassen ist verfrüht. |
| 5 | Stepper-Indikator | **Atom `Dot`** mit `tone="success"` für done; pending/active = Border-Kreis mit Ziffer (Custom-Markup, weil `Dot` keine outline-Variante hat) | Lauf B führt `Dot` als kanonischen Status-Indikator ein (Token-System-konform); Lucide-Check umgeht Token-System. |

### Umfang

| Datei | Status | LoC |
|-------|--------|-----|
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | NEU | ~80 |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | NEU | ~50 |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | NEU | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | NEU | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | NEU | ~10 |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | NEU | ~10 |
| `frontend/src/lib/components/trip-wizard/__tests__/Stepper.test.ts` | NEU | ~30 |
| `frontend/src/routes/trips/new/+page.svelte` | EDIT | ~15 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | NEU | ~120 |
| `frontend/e2e/trip-wizard.spec.ts` | EDIT (skip) | ~3 |
| `docs/specs/modules/epic_136_step0_shell.md` | EDIT (Stub füllen) | ~150 |
| **Total** | **11 Dateien** | **~490 LoC** |

**FLAG:** Überschreitet 4–5 Files / 250 LoC. Volumen-getrieben, nicht Komplexität-getrieben (4× 10-LoC-Step-Platzhalter, 120-LoC-E2E-Spec, 150-LoC-Sub-Spec). Splitten der Step-Platzhalter in #161–#164 würde E2E-Navigationstests blockieren — daher in #160 belassen.

### Wesentliche Risiken

- **Safari-Reaktivität:** `WizardState` darf NICHT als Modul-Singleton/top-level instanziiert werden. Pflicht: Instanziierung im `<script>`-Block von `+page.svelte` mit Factory-Pattern. CLAUDE.md-Regel "Factory Pattern für `on_click`" ist hier verschärft auf alle Svelte-5-Klassen-Instanzen.
- **Alte E2E-Tests brechen ~28 Tests:** muss durch `.skip()` ohne Coverage-Verlust gemacht werden (siehe Entscheidung 4).
- **Master-Spec-Vertrag:** Sub-Spec darf `WizardState`-Schema NICHT erweitern. `state.canAdvance` ist daher Folge-Issue-Konzern.

---

**Nächster Schritt:** `/3-write-spec` füllt `epic_136_step0_shell.md` aus.
