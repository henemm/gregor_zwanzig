---
workflow: issue-161-wizard-step1-profil
phase: phase1_context
created: 2026-05-10
issue: 161
parent_epic: 136
related_master_spec: epic_136_trip_wizard
related_sub_spec: epic_136_step1_profile
predecessor_issue: 160
---

# Context: Issue #161 — Wizard Step 1: Aktivitätsprofil + Eckdaten

## Request Summary

Step 1 des Trip-Wizards mit Inhalt füllen: 5 ProfileChips (Trekking / Skitour / Hochtour / Klettersteig / MTB) + Formularfelder für Name, Kürzel (`shortcode`) und Zeitraum (Datum von/bis). Validierung der Pflichtfelder so, dass der "Weiter"-Button erst aktiv wird, wenn alle Eingaben vorhanden sind. Komponente: `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` — heute leerer Platzhalter.

## Master-Spec Vertrag

`docs/specs/modules/epic_136_trip_wizard.md` (approved 2026-05-09) garantiert für Step 1:

1. `WizardState` aus `wizardState.svelte.ts` hat **alle Felder bereits angelegt**: `activity`, `name`, `shortcode`, `startDate`, `endDate`. Sub-Spec #161 darf das Schema NICHT erweitern (außer `canAdvanceStep1` — siehe R3).
2. `ActivityType` ist abschließend definiert: `'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb'`.
3. `mapActivityToProfile()` existiert in `wizardHelpers.ts` — wird beim Save (Step 4) aufgerufen, **nicht** in Step 1.
4. Save-Pipeline (`state.save()`) liegt in Step 4 — Step 1 schreibt nur in den State, persistiert nichts.
5. `Pill`-Atom (Epic #133, `data-tone`-System) ist die kanonische Chip-Komponente.

**Sub-Spec #161 muss liefern:** UI-Detail (Layout, Atom-Verwendung, Validierungslogik, Tests). KEINE neuen `WizardState`-Felder, KEINE neuen Atom-Komponenten, KEINE Backend-Änderungen.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | EDIT — heute 8-Zeiler-Platzhalter, wird mit Inhalt gefüllt |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EXISTIERT — `activity` (Z. 51), `name` (Z. 52), `shortcode` (Z. 53), `startDate` (Z. 55), `endDate` (Z. 56) |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | EXISTIERT — `mapActivityToProfile()` (Z. 71); für Step 1 nicht direkt aufgerufen |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | LESE — Konsumiert State via `getContext('trip-wizard-state')` (Z. 26); Footer rendert "Weiter"-Button — muss Step-Disabled-Flag respektieren (siehe R3) |
| `frontend/src/lib/types.ts` | LESE — `ActivityType` (Z. 14), `Trip.shortcode`/`Trip.activity` (Z. 34–45) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | DEPENDENCY — Chip-Atom mit `tone`-Variante; Token-CSS in `app.css` Z. 128–142 |
| `frontend/src/lib/components/ui/input/input.svelte` | DEPENDENCY — Text- und Date-Inputs; HTML5 `type="date"` reicht |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | DEPENDENCY — Container für Step-Inhalt (optional, Layout-Frage) |
| `frontend/src/app.css` | DEPENDENCY — Tokens `--g-accent`, `--g-ink`, `--g-ink-faint`, `--g-paper`, `--g-radius-pill` |
| `frontend/e2e/trip-wizard-shell.spec.ts` | KONFLIKT-NIEDRIG — Shell-Tests prüfen Stepper-Navigation; Step-1-Validierung darf "Weiter"-Button blockieren → bestehende Navigations-Tests prüfen, ggf. State-Setup anpassen |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | EXISTIERT — Smoke-Tests, optional erweitern um `canAdvanceStep1`-Tests |
| `docs/specs/modules/epic_136_step1_profile.md` | EDIT (Stub füllen) — Sub-Spec für Phase 3 |

## Existing Patterns

### Atom-Verwendung (aus Cockpit Epic #134 + Shell #160)

```svelte
import { Btn } from '$lib/components/ui/btn';
import { Pill } from '$lib/components/ui/pill';
import { Input } from '$lib/components/ui/input';
import { Eyebrow } from '$lib/components/ui/eyebrow';

<Pill tone="accent">Trekking</Pill>           // ausgewählt
<Pill tone="default">Skitour</Pill>           // nicht ausgewählt
<Input type="text" bind:value={state.name} />
<Input type="date" bind:value={state.startDate} />
```

### State-Konsum-Pattern (aus TripWizardShell.svelte Z. 26)

```svelte
import { getContext } from 'svelte';
import type { WizardState } from '../wizardState.svelte';

const state = getContext<WizardState>('trip-wizard-state');
```

Step1Profile bindet direkt an `state.activity`, `state.name`, etc. via `bind:value` — Svelte-5-Runes-Reaktivität sorgt für State-Update.

### Factory-Handler-Pattern (aus TripWizardShell.svelte Z. 47–61)

CLAUDE.md fordert benannte Handler statt anonymer Closures (Safari-Reaktivität). Für Chip-Klicks gilt das gleiche Prinzip:

```svelte
function handleSelectActivity(activity: ActivityType) {
  state.activity = activity;
}

<Pill onclick={() => handleSelectActivity('trekking')}>Trekking</Pill>
```

### Test-Setup

- **Unit-Tests:** `node --experimental-strip-types --test` (kein Vitest); Runes als Identity-Funktionen gepatcht — siehe `wizardState.test.ts`
- **E2E:** Playwright unter `frontend/e2e/`, Auth via `playwright/.auth/admin.json`, `webServer: bash e2e/start-preview.sh` Port 4173
- **Test-IDs:** Konvention `trip-wizard-step1-*` (z.B. `trip-wizard-step1-profile`, `trip-wizard-step1-chip-trekking`, `trip-wizard-step1-name`, `trip-wizard-step1-shortcode`, `trip-wizard-step1-startdate`, `trip-wizard-step1-enddate`)

## Dependencies

**Upstream (was Step 1 benutzt):**
- `WizardState`-Klasse (Felder Step 1, alle bereits da)
- Atom-Komponenten `Pill`, `Input`, `Eyebrow`, `GCard` (Epic #133)
- `ActivityType` aus `$lib/types`
- Token-CSS aus `app.css` (Epic #133 Lauf B)

**Downstream (was Step 1 produziert):**
- Updated `state.activity`, `state.name`, `state.shortcode`, `state.startDate`, `state.endDate` — werden in Step 2 (#162: `addDays(startDate, ...)` für Etappen-Datierung) und Step 4 (`save()` → `mapActivityToProfile`) gelesen
- Step-Vorwärts-Bedingung (`canAdvanceStep1`) — wird vom Shell-Footer ("Weiter"-Button-Disabled) konsumiert (siehe R3)

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — **Master-Spec (approved)**, §1.2/1.3 (Datenmodell + Mapping), §3.1 (State-Schema)
- `docs/specs/modules/epic_136_step1_profile.md` — **Stub**, wird in Phase 3 ausgefüllt (diese Sub-Spec)
- `docs/specs/modules/epic_136_step0_shell.md` — **Approved/Implemented** (Issue #160), Vertrag für Footer-Buttons + Context-Setup
- `docs/specs/modules/activity_profile.md` — kanonische 4-Werte-Whitelist für `aggregation.profile` (Backend-Behavior-Key); Step 1 schreibt nur `activity`, nicht `aggregation.profile`
- `docs/specs/modules/epic_133_design_system_lauf_b.md` — Atom-Komponenten Pill/Input/GCard/Btn/Eyebrow

## Risks & Considerations

### R1: Shell-Footer ignoriert aktuell den Validierungs-Status

`TripWizardShell.svelte` Z. 121: `<Btn data-testid="trip-wizard-next" ...>Weiter</Btn>` hat **keinen `disabled`-Prop**. Sub-Spec #160 hat das absichtlich offen gelassen ("Steps validieren selbst, Shell delegiert"; Master-Spec #160 §Entscheidung 1: `canAdvance` soll als Folge-Issue eingeführt werden).

**Mitigation:**
- Sub-Spec #161 erweitert `WizardState` um ein `$derived` Flag `canAdvanceStep1` (oder generischer: `canAdvance`).
- `TripWizardShell.svelte` muss in dieser Sub-Spec einen Mini-Edit erhalten (`disabled={!state.canAdvance}` am Weiter-Button) — das ist 1 Zeile, kein Architektur-Eingriff.
- Master-Spec wird mit dem Schema-Patch synchronisiert (oder via Changelog-Notiz, weil `$derived` keine echte Schema-Änderung ist).

### R2: Pill als selektierbares Element

`Pill.svelte` ist ein `<span>` ohne native Click-Semantik. Für Tastatur-/Screenreader-Zugänglichkeit muss der ProfileChip als `<button>` gerendert werden — Pill ist nur das visuelle Pattern. Vorschlag: einen Wrapper-Button erstellen, der intern Pill mit dynamischem `tone` rendert (oder direkt im Step1Profile inline TailwindCSS-Buttons mit Pill-Optik). Sub-Spec entscheidet.

**Empfehlung:** `<button>`-Wrapper mit `aria-pressed={state.activity === 'trekking'}` und `<Pill tone={state.activity === 'trekking' ? 'accent' : 'default'}>` als visuelle Hülle. Saubere a11y, keine neue Atom-Komponente nötig.

### R3: `canAdvanceStep1` — wo wohnt die Validierungslogik?

Optionen:
- **A:** `state.canAdvanceStep1 = $derived(activity !== null && name.trim().length > 0 && startDate !== null && endDate !== null)` — Logik in WizardState
- **B:** Step1Profile exportiert ein `valid: boolean` via Context — Logik in Step
- **C:** Shell ruft `state.canAdvance` als Generic-Flag, jeder Step mutiert es — fragil, weil Step-Mounting/Unmounting

**Empfehlung A:** State-zentrierte Validierung. Bleibt konsistent mit "Single Source of Truth"-Prinzip der Master-Spec, ist trivial unit-testbar, und erlaubt späteren Steps (#162ff.) parallel `canAdvanceStep2/3/4` zu ergänzen. Master-Spec sagt §3.1 nichts gegen `$derived`-Felder.

### R4: `endDate` — derived oder eingegeben?

Master-Spec §3.1 Z. 253 sagt: `endDate = $state('')` mit Kommentar `// derived in Step 2`. Im aktuellen Code ist es `string | null` (wizardState Z. 56). Issue-Beschreibung #161 fordert "Zeitraum" — also Datum von **und** bis im UI eingegeben.

**Konflikt:** Master-Spec sagt "derived in Step 2" (aus Anzahl Etappen), Issue sagt "User-Eingabe in Step 1".

**Empfehlung:** Step 1 erfasst `startDate` als Pflicht und `endDate` als **optional** (User-Override). Wenn User nichts angibt, errechnet Step 2 das `endDate` aus Stage-Anzahl. Reihenfolge: User-Wahl gewinnt. Diese Entscheidung muss in Sub-Spec klar dokumentiert werden — andernfalls überschreibt Step 2 silent eine User-Eingabe (UX-Falle).

**Alternative:** Step 1 erfasst nur `startDate`, `endDate` ist Step-2-Concern. Streng nach Master-Spec, einfacher zu implementieren. **Empfohlen, weil Master-Spec approved und Issue-Text "Zeitraum" auch durch Start + Etappenanzahl darstellbar ist.** Aber: Issue-Beschreibung explizit prüfen — User könnte beide Daten erwarten.

→ **Tech-Lead-Entscheidung in Phase 2 nötig.** Default für Sub-Spec: `endDate` bleibt Step-2-Concern, Step 1 zeigt nur Startdatum. Falls User-Feedback anders: einfach hinzufügen, Schema ist da.

### R5: Shortcode-Format-Validierung

Master-Spec sagt nur `shortcode?: string` (omitempty). Keine Regex, keine Längen-Begrenzung. Issue-Text: "Kürzel" (deutsch). Pragmatisch: 2–10 Zeichen, alphanumerisch + Bindestrich (z.B. "GR20", "KHW", "stubai-25"). Frontend-only Validierung; Backend speichert beliebige Strings.

**Empfehlung:** Sub-Spec setzt **weiche** Validierung: `maxLength={20}`, optional Regex `^[A-Za-z0-9-]+$` als Soft-Hint (kein Blocker). Pflicht-Status: **optional** (Master-Spec sagt `omitempty`; Issue-Text macht das nicht zur Pflicht). Step 1 lässt das Feld leer durchgehen.

### R6: Profil-Chip-Reihenfolge und Default

Issue-Text gibt Reihenfolge: Trekking / Skitour / Hochtour / Klettersteig / MTB. **Default ist `null`** (User MUSS aktiv wählen). Begründung: Mapping zu `aggregation.profile` ist behavior-relevant — kein silent-Default. Entspricht `state.activity = $state<ActivityType | null>(null)` in `wizardState.svelte.ts` Z. 51.

### R7: Tests

- **Unit-Tests:** `Step1Profile.test.ts` testet Render mit verschiedenen `state.activity`-Werten; Klick auf Chip → `state.activity` updated; `canAdvanceStep1` richtig abgeleitet
- **E2E-Tests:** `trip-wizard-shell.spec.ts` erweitern (oder neue Datei `trip-wizard-step1.spec.ts`): User füllt Step 1 aus → "Weiter"-Button enabled; leerer Name → disabled; Chip-Selection visuell sichtbar (data-active oder pill-tone="accent")
- **Existing E2E Konflikt:** Shell-E2E (`trip-wizard-shell.spec.ts`) prüft Stepper-Navigation — sobald Weiter-Button initial disabled wird, brechen ggf. Tests, die ohne Step-1-Inputs Step 2 ansteuern. **Anpassung nötig:** entweder Step-1-Validierung im Test umgehen (Test-Daten setzen) oder die alten Tests so umschreiben, dass sie zuerst Step 1 ausfüllen.

### R8: TripWizardShell.svelte minimal-invasiv anfassen

Issue #161 ist **frontend-only Step-1-Inhalt** — aber R1/R3 erfordern eine **kleine** Änderung an der Shell (Z. 121: `disabled={!state.canAdvance}`). Sub-Spec dokumentiert das explizit als "1-Zeilen-Edit" und nicht als Re-Design der Shell.

## Vorab-Tech-Lead-Empfehlung (für Phase 2)

1. **Layout:** Vertikales Stack — oben 5 ProfileChips (horizontal scrollbar/wrappable), darunter 3 Input-Felder (Name, Kürzel, Startdatum). Optional: Endedatum als Step-1-User-Override (siehe R4 — Tech-Lead-Entscheidung).
2. **Pflichtfelder:** `activity` + `name` + `startDate`. `shortcode` + `endDate` optional.
3. **Validierungs-Pattern:** `state.canAdvanceStep1 = $derived(...)` in WizardState; Shell-Footer-Button bekommt `disabled={state.currentStep === 1 ? !state.canAdvanceStep1 : ...}`.
4. **Chip-Selection als Buttons:** `<button aria-pressed={selected}>` wrapping `<Pill tone={selected ? 'accent' : 'default'}>` — keine neue Atom-Komponente.
5. **Test-IDs:** `trip-wizard-step1-profile` (Container, schon da), `trip-wizard-step1-chip-{activity}` (5 Chips), `trip-wizard-step1-name`, `trip-wizard-step1-shortcode`, `trip-wizard-step1-startdate`, optional `trip-wizard-step1-enddate`.
6. **Master-Spec-Sync:** Sub-Spec #161 dokumentiert die `canAdvanceStep1`-Erweiterung explizit; Master-Spec Changelog-Eintrag (kein Approval-Reset, weil rein additive `$derived`-Erweiterung).
7. **Worktree-only:** Developer-Agent in Worktree-Isolation. Keine `internal/`, `src/`, `cmd/` Dateien — kein Backend-Build, kein Schema-Snapshot.
8. **E2E nach Push:** Validator gegen Staging (gemäß `feedback_validator_after_push.md`). Browser: Safari first (CLAUDE.md NiceGUI-Pattern für Svelte-Closures gilt analog).

---

## Phase 2 — Analyse-Ergebnisse (2026-05-10)

### Tech-Lead-Entscheidungen

| # | Frage | Entscheidung | Begründung |
|---|-------|--------------|------------|
| **R4** | Endedatum-Eingabe in Step 1 | **Nur Startdatum** | User-Entscheidung (AskUserQuestion 2026-05-10) deckt sich mit approved Master-Spec §3.1 Zeile 253: `endDate = $state('') // derived in Step 2`. Step 2 berechnet `endDate` aus Etappen-Anzahl (Stages + Pausentage). Vermeidet Doppeleingabe und Konflikt-Logik. |
| **R5** | Shortcode-Format | **Optional, max 20 Zeichen, kein Regex** | Master-Spec sagt `omitempty` (kein Pflicht). Issue-Text "Kürzel" ohne Format-Vorgabe. Soft-Limit verhindert Datenqualitäts-Probleme im UI (z.B. Trip-Liste). Backend nimmt beliebige Strings entgegen — keine Frontend-Regex. |
| **R8** | TripWizardShell-Edit | **1-Zeilen-Edit:** `disabled={state.currentStep === 1 ? !state.canAdvanceStep1 : false}` am Weiter-Button | Sub-Spec #160 §Entscheidung 1 hat `canAdvance` explizit als Folge-Issue-Konzern markiert. Step 1 zieht den Pattern jetzt ein, bleibt aber **additiv** — Schema-Erweiterung über `$derived` (kein neuer State). Master-Spec Changelog-Eintrag, kein Approval-Reset. |

### Scope (Recherche bestätigt)

| Datei | Status | LoC |
|-------|--------|-----|
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | EDIT (Stub füllen) | ~80 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EDIT (`canAdvanceStep1` als `$derived`) | +5 |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | EDIT (Weiter-Button `disabled`) | +1 |
| `frontend/src/lib/components/trip-wizard/__tests__/Step1Profile.test.ts` | NEU | ~60 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | EDIT (`canAdvanceStep1`-Tests) | +20 |
| `frontend/e2e/trip-wizard-step1.spec.ts` | NEU | ~100 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | EDIT (5 Tests anpassen, siehe unten) | ~30 |
| `docs/specs/modules/epic_136_step1_profile.md` | EDIT (Stub füllen) | ~150 |
| `docs/specs/modules/epic_136_trip_wizard.md` | EDIT (Changelog-Eintrag für `canAdvanceStep1`) | +3 |
| **Total** | **9 Dateien** | **~450 LoC** |

**FLAG:** Überschreitet 4–5 Files / 250 LoC. Volumen-getrieben, nicht Komplexität-getrieben (~150 LoC Sub-Spec, ~160 LoC Tests, ~30 LoC E2E-Test-Anpassungen). Eigentlicher Produktionscode ist nur ~85 LoC. Splitten wäre künstlich (z.B. Tests-only-PR), Cleanup-Aufwand höher als Nutzen. **Empfehlung: zusammen lassen.**

### Bestehende E2E-Tests, die brechen

`frontend/e2e/trip-wizard-shell.spec.ts` enthält 5 Tests, die `[data-testid="trip-wizard-next"]` klicken, ohne Step-1-Felder auszufüllen. Sobald `disabled` greift, werden alle 5 fehlschlagen:

| Test | Zeilen | Was tut der Test |
|------|--------|------------------|
| AC#5+#6 | 38–44 | Step 1 → Step 2 ohne Eingaben |
| AC#5 | 46–52 | Hin- und Rück-Navigation |
| AC#5a | 54–61 | **Explizit:** `.toBeEnabled()` in Step 1, dann 3× klicken |
| AC#8 | 69–77 | 3× klicken bis Step 4 |
| AC#11 | 79–88 | 4× klicken bis Save-Status |

**Mitigation:** Pro Test eine Test-Helper-Funktion `fillStep1(page, { activity, name, startDate })` einführen, die vor dem Navigieren die Pflichtfelder ausfüllt. Sub-Spec #161 dokumentiert die Helper-Signatur. AC#5a ändert die Semantik: Statt `.toBeEnabled()` ohne Eingaben → `.toBeDisabled()` ohne Eingaben + `.toBeEnabled()` nach `fillStep1()`.

### Implementierungs-Reihenfolge (TDD-RED → GREEN)

1. Master-Spec Changelog-Eintrag (`canAdvanceStep1` als additive `$derived`-Erweiterung)
2. Sub-Spec `epic_136_step1_profile.md` ausfüllen (Phase 3 / `/3-write-spec`)
3. **User-Approval** der Sub-Spec
4. **TDD-RED:** `__tests__/wizardState.test.ts` (canAdvanceStep1-Cases) + `__tests__/Step1Profile.test.ts` + `e2e/trip-wizard-step1.spec.ts` (alle rot)
5. **GREEN:** `wizardState.svelte.ts` `$derived` ergänzen
6. **GREEN:** `Step1Profile.svelte` mit ProfileChips, Inputs, Validierung
7. **GREEN:** `TripWizardShell.svelte` 1-Zeilen-Edit (`disabled`-Prop)
8. **Migration:** Bestehende `trip-wizard-shell.spec.ts`-Tests anpassen (5× `fillStep1`)
9. `npm run check` + `npm run build` grün
10. Adversary Validator + Fresh-Eyes (Screenshot-Review)
11. Validierung gegen Staging nach Push

### Frontend-Tech-Stack-Bestätigung

- **Svelte 5.55** (Runes-Mode)
- **TailwindCSS 4.2** + Token-CSS (`--g-accent` etc. in `app.css`)
- **shadcn-svelte 1.0.0-next.19** (bits-ui)
- **HTML5 `<input type="date">`** ist im Repo bisher nirgends verwendet — Step 1 ist der erste Use-Case. Acceptable: Browser-native Picker, später ggf. shadcn DateField. Für Mobile (iOS/Android) reicht die native Implementierung.

### Wesentliche Risiken

- **R-A: Master-Spec-Drift** — `canAdvanceStep1` ist additive `$derived`-Erweiterung; Master-Spec wird via Changelog synchronisiert. Kein Approval-Reset, weil Sub-Spec #160 die Lücke explizit für Folge-Issues offen gelassen hat (Master-Spec §Entscheidung 1).
- **R-B: 5 bestehende E2E-Tests brechen** — wird via `fillStep1`-Helper migriert. AC#5a-Semantik ändert sich. Sub-Spec dokumentiert das.
- **R-C: ProfileChip a11y** — `<button aria-pressed={...}><Pill tone={...}></button>` Pattern; Tastatur-Bedienung pflicht (Tab + Space/Enter). Sub-Spec spezifiziert.
- **R-D: Safari-Reaktivität** — Factory-Handler-Pattern (CLAUDE.md NiceGUI-Pattern auf Svelte erweitert): `function handleSelectActivity(activity)` benannt, kein anonymer Closure-Inline.
- **R-E: Worktree-Isolation** — Frontend-only, kein Backend, kein Schema-Snapshot. Developer-Agent in Worktree.

---

**Nächster Schritt:** `/3-write-spec` — fülle `docs/specs/modules/epic_136_step1_profile.md` mit Layout-Wireframe, Atom-Verwendung, ProfileChip-a11y-Pattern, Validierungslogik (`canAdvanceStep1`), Test-IDs, fillStep1-Helper, und Master-Spec-Changelog-Eintrag.
