---
workflow: issue-162-wizard-step2-stages
phase: phase1_context
created: 2026-05-10
issue: 162
parent_epic: 136
related_master_spec: epic_136_trip_wizard
related_sub_spec: epic_136_step2_stages
predecessor_issue: 161
---

# Context: Issue #162 — Wizard Step 2: GPX-Multi-Upload + Drag-Sort + Pause

## Request Summary

Schritt 2 des Trip-Wizards: User laedt mehrere GPX-Dateien hoch (Drop-Zone + Multi-Select), bekommt eine sortierbare Etappen-Liste mit T01/T02-Nummerierung. Zwischen Etappen kann er per "+ Pause"-Button (erscheint beim Hover) einen Pausentag einfuegen. Auto-Datierung: erste Etappe = `state.startDate` aus Step 1, jede weitere +1 Tag (inkl. Pausentage). Wiederverwendung der bestehenden GPX-Logik aus dem alten Wizard. Komponente `Step2Stages.svelte` heute Stub.

## Master-Spec Vertrag

`docs/specs/modules/epic_136_trip_wizard.md` (approved 2026-05-09) garantiert fuer Step 2:

1. `WizardState.stages` ist als `$state<Stage[]>([])` deklariert. Methoden `addStage(stage)`, `addPauseStage()`, `reorderStages(from, to)` sind im Code vorhanden (Z. 105–128).
2. Pausentag-Konvention: Stage mit `waypoints.length === 0` ist ein Pausentag. KEIN neues Modell-Feld.
3. `formatStageNumber(index)` liefert "T01", "T02" etc. (`wizardHelpers.ts` Z. 55–57).
4. Step 2 schreibt nur in `WizardState` — kein API-Persistenz-Call (Save erst in Step 4).
5. `endDate` wird in Step 2 abgeleitet (Master-Spec §3.1 Z. 253). Step 1 hat das Startdatum gesetzt; Step 2 berechnet Endedatum aus `startDate + (stages.length - 1)`.

**Sub-Spec #162 muss liefern:** UI-Detail fuer Drop-Zone, sortierbare Etappenliste, "+ Pause"-Button, Auto-Datierung, Validierungslogik (`canAdvanceStep2`). KEINE Backend-Aenderung.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | EDIT — heute 8-Zeilen-Stub, wird mit Inhalt gefuellt |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | NEU — Etappen-Row-Komponente (Pill T01, Name, Datum, Drag-Handle, Delete) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EDIT — `canAdvanceStep2`-Getter ergaenzen (analog `canAdvanceStep1` Z. 80–87) |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | EDIT — Weiter-Button-`disabled`-Bedingung um Step 2 erweitern (Pattern-Refactor Empfehlung) |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | LESE — `isPauseStage`, `formatStageNumber` |
| `frontend/src/lib/api.ts` | LESE — `uploadGpx(file, stageDate, startHour)` Z. 27–50, returnt `Promise<Stage>` |
| `frontend/src/lib/utils/naturalSort.ts` | LESE — `naturalSort<T>(arr, key)` Z. 31–61, sortiert "KHW_00a" vor "KHW_10" |
| `frontend/src/lib/components/wizard/WizardStep1Route.svelte` | REFERENZ (alt) — Multi-Upload-Flow als Vorlage; nicht editieren, lebt parallel im Edit-Pfad |
| `frontend/src/lib/types.ts` | LESE — `Stage` Interface (`id`, `name`, `date`, `waypoints[]`, optional `start_time`) |
| `frontend/e2e/helpers.ts` | EDIT — `fillStep2(page, files?)` Helper analog zu `fillStep1` |
| `frontend/e2e/trip-wizard-shell.spec.ts` | EDIT — AC#5a wird wieder brechen (Step 2 disabled bis Upload) — Migration via `fillStep2` |
| `docs/specs/modules/epic_136_step2_stages.md` | EDIT (Stub fuellen) |
| `docs/specs/modules/gpx_multi_import.md` | LESE — Natural-Sort + Date-Propagation-Pattern (alt-NiceGUI, semantisch uebernommen) |

## Existing Patterns

### Multi-Upload-Flow (aus altem Wizard, semantisch uebernommen)

```
1. ondrop / <input type="file" multiple> → pendingFiles: File[]
2. UI zeigt: Datumspicker (default: state.startDate aus Step 1) + "X Etappen anlegen"-Btn
3. commitPending():
   a. naturalSort(pendingFiles, f => f.name)
   b. for each file (index i): uploadGpx(file, addDays(stageDate, i), 8) → Stage
   c. state.addStage(stage)
   d. Bei Fehler: Stage skippen, Warning anzeigen, Loop weiter
4. pendingFiles = []  (clear)
```

### State-Konsum-Pattern (aus #161 etabliert)

```svelte
import { getContext } from 'svelte';
import type { WizardState } from '../wizardState.svelte';

const state = getContext<WizardState>('trip-wizard-state');
```

### Factory-Handler-Pattern (CLAUDE.md Safari-Regel)

```svelte
function handleAddPause(afterIndex: number) {
  // Pause zwischen index und index+1 einfuegen
  state.addPauseStage();  // append
  state.reorderStages(state.stages.length - 1, afterIndex + 1);  // an Position schieben
}
```

### Test-Setup (etabliert in #161)

- **Unit:** `node --experimental-strip-types --test` mit Identity-Mocks fuer `$state`/`$derived`
- **E2E:** Playwright unter `frontend/e2e/`, Auth via `playwright/.auth/admin.json`
- **TestID-Konvention:** `trip-wizard-step2-*` (Drop-Zone, Stage-Row, Pause-Button)

## Dependencies

**Upstream (was Step 2 nutzt):**
- `WizardState`: `state.stages`, `state.startDate` (aus Step 1), `addStage`, `addPauseStage`, `reorderStages`
- `uploadGpx` aus `$lib/api.ts` — Backend-Endpoint `POST /api/gpx/parse`
- `naturalSort` aus `$lib/utils/naturalSort.ts`
- `formatStageNumber`, `isPauseStage` aus `wizardHelpers.ts`
- `addDays` aus `wizardHelpers.ts` (fuer Auto-Datierung)
- Atom-Komponenten Btn, GCard, Pill, Eyebrow, Input (Epic #133)
- Optional: DnD-Library (Entscheidung in Phase 2)

**Downstream (was Step 2 produziert):**
- `state.stages` mit Stages (mit/ohne `waypoints`) — wird in Step 3 (#163) fuer Wegpunkt-Bestaetigung gelesen, in Step 4 (#164) gespeichert
- `canAdvanceStep2` (neu) — wird vom Shell-Footer fuer Weiter-Button-Disabled gelesen

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec (approved); §3.1 (State-Schema), §3.2 (Pausentag-Konvention), §3.3 (T-Nummerierung)
- `docs/specs/modules/epic_136_step2_stages.md` — **Stub**, zu fuellen
- `docs/specs/modules/epic_136_step1_profile.md` — Vorgaenger (#161, abgeschlossen): Pattern fuer `canAdvanceStepN` + Shell-Edit + `fillStepN`-Helper
- `docs/specs/modules/gpx_multi_import.md` — Natural-Sort-Logik + Date-Propagation (alt-NiceGUI; UI-Detail veraltet, Semantik gueltig)
- `docs/specs/modules/gpx_upload.md` — Single-Upload-Spec; weniger relevant
- `docs/specs/modules/gpx_parser.md` — Backend-Parser-Vertrag

## Risks & Considerations

### R1: DnD-Library-Entscheidung — `svelte-dnd-action` vs. native HTML5

`svelte-dnd-action` ist **nicht** installiert. Optionen:

- **A: `svelte-dnd-action` hinzufuegen** (~2 KB, Svelte-5-kompatibel, Standard-Lib, deklarativ, ARIA-unterstuetzt). Neue Dependency, aber Branchen-Standard. ~1–2h Dev-Aufwand.
- **B: Native HTML5 DnD** (`draggable=true` + `ondragstart` + `ondrop`). Keine Dependency, aber komplexere Index-Logik (Drag-Over-Detection, Reorder-Pivot). ~3–4h Dev-Aufwand. Mobile-DnD ist mit nativem HTML5 brueckenlos.
- **C: Up/Down-Buttons** (kein Drag, dafuer ▲ / ▼ pro Row). Stoesst Issue-Anforderung "drag-sortierbar" zurueck. Akzeptabel als MVP-Fallback.

**Empfehlung:** **A**. `svelte-dnd-action` ist klein, gut gewartet, Svelte-5-ready. Mobile-Support ist sauber (Touch-DnD). User hat im Issue "drag-sortierbar" explizit genannt.

**Tech-Lead-Entscheidung in Phase 2 noetig** — nur User kann „neue Dependency" abnicken.

### R2: Bestehender E2E-Test AC#5a bricht erneut

`frontend/e2e/trip-wizard-shell.spec.ts` AC#5a Z. 66–72: nach `fillStep1` klickt der Test sich durch Steps 2-3 ohne Inhalt — Weiter-Button war bisher in Step 2-3 enabled. Sobald `canAdvanceStep2` greift, schlaegt das fehl.

**Mitigation:** `fillStep2(page)`-Helper bauen (laedt Test-GPX hoch). AC#5a wird zu „nach `fillStep1` + `fillStep2` enabled in Step 3". Test-GPX muss verfuegbar sein — Repo hat ggf. Fixtures unter `tests/fixtures/` oder wir generieren sie inline.

### R3: Shell-Edit-Pattern (verschachteltes Ternary unleserlich)

`TripWizardShell.svelte` heute Z. 126:
```svelte
disabled={state.currentStep === 1 ? !state.canAdvanceStep1 : false}
```

Erweitert um Step 2 wuerde das zu:
```svelte
disabled={
  state.currentStep === 1 ? !state.canAdvanceStep1 :
  state.currentStep === 2 ? !state.canAdvanceStep2 :
  false
}
```

Mit Steps 3+4 wird das chaotisch. **Empfehlung:** Refactor zu Helper-Getter `WizardState.canAdvanceCurrent` (or `state.canAdvance` als generic switch ueber `currentStep`). Dann Shell zu `disabled={!state.canAdvanceCurrent}`.

```typescript
get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return true;  // bis #163
    case 4: return true;  // bis #164
  }
}
```

Saubere Erweiterung in Folge-Issues, kein Schema-Bruch. Master-Spec-Changelog-Eintrag analog zu #161.

### R4: Auto-Datierung von Pausentagen

Issue sagt: Pause "zwischen Etappen". Wenn User zwischen Etappe T02 (Datum 2026-06-02) und T03 (Datum 2026-06-03) eine Pause einfuegt, soll Pause-Datum 2026-06-03 sein und T03 wird zu 2026-06-04 verschoben. Konkret: alle Stages NACH der eingefuegten Pause bekommen +1 Tag.

**Tech-Lead-Entscheidung Phase 2:** Auto-Re-Date oder lassen wir Datum manuell? Empfehlung: **Auto-Re-Date** beim Einfuegen. Beim Reorder via DnD ebenfalls Re-Date (Reihenfolge bestimmt Datum). User kann Datum manuell ueberschreiben (Date-Input pro Row).

### R5: Etappen-Namen-Quelle aus GPX

`uploadGpx` returnt `Stage` — woher kommt der `name`? Backend (siehe `gpx_parser.md`) extrahiert vermutlich den Track-Name aus GPX-Metadaten. Bei fehlendem Track-Name: Fallback auf Dateiname (ohne `.gpx`-Endung). Pruefen in Phase 2.

### R6: Gleichzeitige Multi-Datei-Uploads — Race Conditions

Bei 5 GPX-Dateien parallel uploaden vs. seriell. **Empfehlung:** seriell (`for ... of` mit `await`) — gleiche Reihenfolge wie `naturalSort`-Output, gleiche Date-Propagation-Logik wie alter Wizard. Parallele Promise.all wuerde Reihenfolge nicht garantieren.

### R7: Datei-Validation vor Upload

Was passiert bei nicht-GPX-Dateien (z.B. .jpg, .pdf)? Frontend-Filter via `accept=".gpx"` am `<input>` — aber Drop-Zone akzeptiert alles. Validate nach Drop: `file.name.endsWith('.gpx')` clientseitig; Backend hat sowieso eigene Validierung (`parse_gpx()`). Bei Fehler: Notify, skip.

### R8: WizardState-Schema-Erweiterung — Master-Spec-Sync

`canAdvanceStep2` und `canAdvanceCurrent` sind additive `$derived`/getter-Erweiterungen — keine Schema-Aenderung im strikten Sinn. Master-Spec Changelog-Eintrag wie in #161.

### R9: Drop-Zone-A11y

Drop-Zone muss tastatur-erreichbar sein: `<button>` oder `<input type="file">`-Trigger fuer User ohne Maus. Visueller Drop-Hinweis (Border) bei `dragover`. Fokus-Ring sichtbar.

### R10: Worktree-Isolation und neue Dependency

Wenn DnD-Library installiert wird, muss `package.json` + `package-lock.json` im Worktree geaendert werden. Beim Merge: keine Konflikte erwartet, weil Hauptrepo aktuell keine konkurrierenden Lockfile-Aenderungen hat.

## Vorab-Tech-Lead-Empfehlung (fuer Phase 2)

1. **Layout (vertikal):** Drop-Zone oben (gross, mit Eyebrow „GPX-Dateien"); darunter Etappen-Liste mit StageRow-Komponenten; "+ Pause"-Button erscheint zwischen Rows beim Hover.
2. **`StageRow`:** `<div role="listitem">` mit Drag-Handle (Lucide `GripVertical`), Pill (T01), Datum-Input, Stage-Name (read-only), Delete-Button.
3. **DnD:** **`svelte-dnd-action`** (User-Bestaetigung in Phase 2 einholen; AskUserQuestion).
4. **Validierung:** `canAdvanceStep2 = $derived(this.stages.length > 0)` (mind. 1 Etappe).
5. **Shell-Refactor:** `canAdvanceCurrent`-switch-Getter, Master-Spec-Changelog.
6. **Auto-Datierung:** beim `addStage`/`addPauseStage`/`reorderStages` re-datieren — neue Methode `WizardState.recomputeStageDates()` die alle Stage-Dates aus `startDate + index` setzt. User-Override pro Row moeglich? **Phase-2-Entscheidung.**
7. **Helper `fillStep2(page)`:** in `e2e/helpers.ts` ergaenzen, mit Test-Fixture-GPX.
8. **Test-IDs:** `trip-wizard-step2-dropzone`, `trip-wizard-step2-stage-row-{i}`, `trip-wizard-step2-stage-pill-{i}` (T01-Anzeige), `trip-wizard-step2-stage-delete-{i}`, `trip-wizard-step2-pause-after-{i}`, `trip-wizard-step2-add-stage`.

---

## Phase 2 — Analyse-Ergebnisse (2026-05-10)

### Tech-Lead-Entscheidungen

| # | Frage | Entscheidung | Begruendung |
|---|-------|--------------|-------------|
| **R1** | DnD-Library | **`svelte-dnd-action`** (User-Entscheidung 2026-05-10) | Standard-Lib fuer Svelte 5, ~2 KB, Mobile-Touch-DnD sauber, ARIA eingebaut. Neue Dependency akzeptiert. |
| **R4** | Auto-Datierung | **Auto-Re-Date bei jeder Aenderung, User-Override per Row erlaubt** (User-Entscheidung 2026-05-10) | 95% Use-Case automatisch korrekt; Flexibilitaet fuer Splitten/Skipping. |
| **R3** | Shell-Edit-Pattern | **Refactor zu `state.canAdvanceCurrent`-Getter** (Tech-Lead-Entscheidung) | Verschachteltes Ternary skaliert nicht. Switch-Getter ist sauber, additive `WizardState`-Erweiterung, Master-Spec-Changelog wie in #161. Folge-Steps #163/#164 ergaenzen analog `canAdvanceStep3/4`. |

### Architektur-Skizze

```
Step2Stages.svelte
├── Drop-Zone (oben, Eyebrow „GPX-Dateien")
│     ├── ondrop / <input type="file" multiple accept=".gpx">
│     ├── pendingFiles: File[] (lokaler State)
│     └── Datumspicker + „X Etappen anlegen"-Btn
│           → commitPending() → naturalSort → for each: uploadGpx → state.addStage
├── Etappen-Liste (svelte-dnd-action `dndzone`)
│     {#each state.stages as stage, i}
│        <StageRow stage={stage} index={i} />  ← Pill T01, Date-Input (Override),
│                                                 Drag-Handle, Delete-Btn
│        {#if hover-area} <PauseInsertButton afterIndex={i} /> {/if}
│     {/each}
└── (kein Footer — Shell rendert Weiter-Button)
```

**Neue WizardState-Methoden (additiv):**

```typescript
get canAdvanceStep2(): boolean {
  return this.stages.length > 0;
}

get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return true;  // bis #163
    case 4: return true;  // bis #164
  }
}

addPauseStageAt(afterIndex: number): void {
  // Pause nach gegebenem Index einfuegen, dann Reorder + Re-Date
  const pause: Stage = { id: newId(), name: 'Pause', date: '', waypoints: [] };
  this.stages = [...this.stages.slice(0, afterIndex + 1), pause, ...this.stages.slice(afterIndex + 1)];
  this.recomputeStageDates();
}

deleteStage(id: string): void {
  this.stages = this.stages.filter(s => s.id !== id);
  this.recomputeStageDates();
}

recomputeStageDates(): void {
  // Nur Stages die NICHT user-overridden sind. Heuristik: leeres Datum oder
  // Datum ist schon == Auto-Wert. Fuer Phase 3: einfach alle re-daten,
  // User-Override-Flag pro Stage in spaeterem Issue (oder direkt jetzt).
  if (!this.startDate) return;
  this.stages = this.stages.map((s, i) => ({
    ...s,
    date: addDays(this.startDate!, i)
  }));
}
```

**WICHTIG:** User hat „User-Override pro Row erlaubt" gewaehlt — das heisst beim Reorder/Pause-Insert duerfen wir NICHT manuelle User-Daten ueberschreiben. Fuer Phase 3: Spec entscheidet eines von beiden:

- **A:** Override-Flag pro Stage (`Stage.dateOverridden?: boolean` im Frontend, transient — nicht persistieren)
- **B:** Heuristik: wenn aktuelles Datum != errechnetes Auto-Datum, dann „overridden" (impliziert)

Empfehlung **A** (explizit, keine Mehrdeutigkeit). Sub-Spec #162 fuegt Frontend-only-Feld zu `Stage` hinzu, beim Save (Step 4) wird es gestrippt — analog `Waypoint.suggested`.

### Scope (basierend auf Entscheidungen)

| Datei | Status | LoC |
|-------|--------|-----|
| `frontend/package.json` + `package-lock.json` | EDIT (svelte-dnd-action) | +1 + lockfile |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | EDIT (Stub fuellen) | ~150 |
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | NEU | ~80 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EDIT (`canAdvanceStep2`, `canAdvanceCurrent`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates`) | +50 |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | LESE / minimal EDIT (ggf. `addDays`-Variante) | 0 |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | EDIT (`disabled={!state.canAdvanceCurrent}`) | -1 / +1 |
| `frontend/src/lib/types.ts` | EDIT (`Stage.dateOverridden?: boolean` transient) | +1 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | EDIT (15-20 neue Cases) | +80 |
| `frontend/src/lib/components/trip-wizard/__tests__/Step2Stages.test.ts` | NEU (optional, ggf. nur E2E) | ~40 |
| `frontend/e2e/helpers.ts` | EDIT (`fillStep2`-Helper) | +30 |
| `frontend/e2e/trip-wizard-step2.spec.ts` | NEU | ~150 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | EDIT (AC#5a Migration) | +10 |
| `frontend/e2e/fixtures/test-trip.gpx` | NEU | ~50 |
| `docs/specs/modules/epic_136_step2_stages.md` | EDIT (Stub fuellen) | ~250 |
| `docs/specs/modules/epic_136_trip_wizard.md` | EDIT (Changelog) | +5 |
| **Total** | **15 Dateien** | **~900 LoC** |

**FLAG:** Volumen weit ueber 4-5 Files / 250 LoC. Aufteilung waere kuenstlich (Step 2 ist eine kohaerente UX-Einheit). Ca. 60% sind Tests + Sub-Spec; eigentlicher Produktionscode ~280 LoC.

### Implementierungs-Reihenfolge (TDD-RED → GREEN)

1. Master-Spec-Changelog (`canAdvanceCurrent`, `canAdvanceStep2`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates`)
2. Sub-Spec `epic_136_step2_stages.md` ausfuellen
3. **User-Approval** der Sub-Spec
4. **TDD-RED:** Unit-Tests fuer `canAdvanceStep2`, `canAdvanceCurrent`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates`. E2E-Tests fuer Drop-Zone, StageRow, DnD, Pause-Einfuegen, Auto-Date, Override.
5. **GREEN:** `svelte-dnd-action` installieren, `wizardState.svelte.ts` erweitern, `StageRow.svelte`, `Step2Stages.svelte`, Shell-Edit, Test-GPX-Fixture
6. **GREEN:** `trip-wizard-shell.spec.ts` AC#5a migrieren
7. `npm run check` + `npm run build` gruen
8. Adversary Validator + Validierung gegen Staging nach Push

### Wesentliche Risiken (verbleibend)

- **R-A: svelte-dnd-action Bundle-Impact** — minimal (~2 KB), aber neue Dependency erhoeht Maintenance-Surface. Gewicht akzeptiert (User-Entscheidung).
- **R-B: Auto-Date vs. User-Override-Konflikt** — `dateOverridden`-Flag ist transient; User koennte beim Reload die Override verlieren. Akzeptabel weil Step 2 vor Save nicht persistiert; nur waehrend Wizard-Session relevant.
- **R-C: Test-GPX-Fixture** — wir brauchen eine echte (kleine) GPX-Datei fuer E2E. Ohne Backend-Mock: echter `POST /api/gpx/parse` muss reagieren. Falls Fixture-GPX nicht parsebar: Test-Helper alternativ `state.addStage`-Direct-Injection ueber Page-evaluate (`page.evaluate(() => state.addStage(...))`). **Phase-3-Entscheidung.**
- **R-D: AC#5a in Shell-Spec bricht** — Migration via `fillStep2(page)` analog #161.
- **R-E: Mobile-DnD-Touch** — `svelte-dnd-action` unterstuetzt Touch-DnD, aber Issue-Beschreibung sagt nichts ueber Mobile-Anforderung. Akzeptabel.

---

**Naechster Schritt:** `/3-write-spec` — fuelle `epic_136_step2_stages.md` mit Layout, DnD-Pattern (`dndzone`), StageRow-Markup, WizardState-Erweiterungen (`canAdvanceCurrent`, `addPauseStageAt`, `deleteStage`, `recomputeStageDates`), Auto-Date-Logik mit `dateOverridden`-Flag, TestID-Inventar, `fillStep2`-Helper, GPX-Fixture-Strategie und Master-Spec-Changelog.
