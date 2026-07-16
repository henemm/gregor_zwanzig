# Context: fix-1269-save-status-lie

## Request Summary
Die Speicher-Status-Anzeige lügt in zwei Richtungen: (a) bloßes Öffnen eines Tabs setzt „● Nicht gespeichert" ohne jede Nutzereingabe (Trip + Vergleich), (b) der Chip springt danach auf „✓ Gespeichert HH:MM", obwohl kein Schreibvorgang (PUT) stattfand (aktuell nur Vergleichs-Editor). Reines Frontend-Anzeige-/Vertrauensproblem — Voraussetzung für Epic #1273.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Geteiltes Anzeige-Atom (idle→„Gespeichert", dirty→„Nicht gespeichert"); rendert rein aus `controller.state`/`savedAt` (Z. 20-45) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | Controller: `state`/`savedAt` (Z. 17-22), `setDirty`/`setSaved` (Z. 32-36), `doSave()` = setSaved erst nach `await saveFn()` (Z. 47-57) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | **Root-Cause (b):** Sync-`$effect` Z. 237-243 ruft `setSaved()` Z. 240-241 unbedingt bei dirty→clean, ohne PUT. Mount-Snapshot `initial` Z. 163-205 vs. `channelLayouts`-Rewrite Z. 728-741 → false dirty. Katalog-Load Z. 715-720. Controller Z. 73. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | **Root-Cause (a) Trip:** reportConfig-Watch-`$effect` Z. 507-513 → `scheduleAutoSave`→Gate `skip`→`setDirty()` Z. 490-493. Baseline `_lastReportConfigJson` Z. 506/270. Touch-Handler Z. 531-538/781-787. |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Mount-Normalisierung + Write-Back Z. 104-171 / 174-216 (`toHHMMSS`, Feld-Materialisierung) — erzeugt den Diff, der (a) im Trip auslöst |
| `frontend/src/lib/components/trip-detail/weatherSaveGate.ts` | #1234-Gate: `skip` außer `catalogLoaded && userTouched` (Z. 39-43) — das **richtige** Ursachen-Signal |
| `frontend/src/lib/components/compare/compareAutosave.ts` | Compare-Wrapper um weatherSaveGate (dirty + userTouched + catalogLoaded) |
| `frontend/src/lib/components/compare/CorridorEditor.svelte` | Wertebereiche-Dual-Write `syncToWizard()` Z. 102-118 (Prefill nur im Create → kein Mount-Dirty im Edit, aber selbe Baseline-Familie) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Rendert SaveIndicator (Z. 194-195); Controller `tripSaveCtl` aus `routes/trips/[id]/+page.svelte:22`, durchgereicht `TripTabs.svelte:207-215` |

## Existing Patterns
- **Ursachen-Regel statt Symptom-Regel (#1234):** `weatherSaveGate` setzt „ohne Nutzergeste (`userTouched`) + geladenen Katalog kein Schreibzugriff" durch. Dieses Gesten-Signal existiert bereits und gatet den PUT — es sollte auch die **Anzeige** treiben.
- **Legitimer „Gespeichert"-Pfad:** `saveStatusStore.doSave()` setzt `setSaved()` erst nach erfolgreichem `await saveFn()`. Der Trip-Editor nutzt ausschließlich diesen Weg → (b) im Trip nicht reproduzierbar.
- **Geteiltes Anzeige-Atom:** SaveIndicator + saveStatusStore werden von Trip und Vergleich geteilt (Trip/Compare-Teilungs-Invariante). Der Fix gehört in diese geteilte Mechanik, nicht per-Editor.

## Dependencies
- **Upstream:** `saveStatusStore.svelte.ts` (Controller), `weatherSaveGate.ts`/`compareAutosave.ts` (Gesten-Signal), `api.put` (echter Schreibvorgang)
- **Downstream:** SaveIndicator-Anzeige (Trip-Header + Compare-Overlay). **Epic #1273** („EINE Fläche wie Trip") setzt voll auf vertrauenswürdiges Auto-Save auf — deshalb #1269 zuerst.

## Existing Specs
- `docs/specs/fast/` bzw. Trip/Compare-Editor-Specs — Auto-Save-Gate #1234 (kein separates Spec-File, siehe Memory `project_issue_1234_autosave_gate`)
- Epic #1273 (Ein-Flächen-Umstellung) — separater Scope, NICHT Teil von #1269

## Risks & Considerations
- **Legit-Dirty erhalten:** Echte Nutzeränderungen MÜSSEN weiter sofort „● Nicht gespeichert" zeigen — der Fix darf Dirty nicht generell unterdrücken.
- **Legit-Saved erhalten:** Nach echtem, erfolgreichem PUT MUSS „✓ Gespeichert HH:MM" erscheinen.
- **Zwei Editor-Kontexte:** Trip (a lebt, b korrekt) + Vergleich (a und b leben) — beide abdecken, Trip-Regression vermeiden.
- **Race-Familie (F002/S3):** Svelte-5-`$effect`/`$derived`-Timing; Baseline wird gegen anderen Zustand als Post-Mount-Zustand gebildet. Fix muss deterministisch sein, nicht timing-abhängig.
- **Teilungs-Invariante:** Fix im geteilten Baustein, damit er #1273 überlebt und nicht throwaway ist.
- **#1234-Gesten-Signal nicht duplizieren:** `userTouched` wiederverwenden, keine parallele Mechanik erfinden.

## Analysis

### Type
Bug (Reaktivitäts-Timing / Auto-Save-Vertrauen).

### Adversary-Challenge-Urteil: NEEDS REVIEW — zwei Korrekturen an meiner Ausgangshypothese
1. **Fix-Design-Korrektur (kritisch):** `setDirty` an `userTouched` zu koppeln (mein Hypothesen-Schritt 1) ist FALSCH und riskant. Der Gesten-Erfassungs-Selektor hatte nachweislich schon zweimal Lücken (F003 Corridor-Slider `.ce-handle`, F004 drag-`svelte-dnd-action` feuert nur Custom-Events). Heute führt eine Lücke nur zu harmlosem False-„Nicht gespeichert"; unter meiner Hypothese würde dieselbe Lücke die Anzeige fälschlich auf „Gespeichert" setzen, WÄHREND echte Änderungen ungespeichert im State liegen und der Auto-Save (selber Gate) nicht greift → **stiller Datenverlust**. #1234 hat sich bewusst dagegen entschieden: Anzeige darf konservativ-falsch „dirty" sein, aber ein SCHREIBZUGRIFF darf nie ohne Geste passieren. **Konsequenz:** (a) NICHT durch Gating von `setDirty` lösen, sondern die spurious Dirty an der QUELLE beseitigen (Mount-Normalisierung darf keinen Diff erzeugen — z. B. Re-Baseline auf die kanonisierte Form beim bekannten Normalisierungs-Write, ereignis-gebunden, nicht timing-flag-gebunden).
2. **Scope-Korrektur:** Compare-Bug (a) ist NUR über den Layout-Tab reproduzierbar (Orte/Idealwerte/Alarme im Compare-Editor lösen es nicht aus). Trip-Bug (a) ist vermutlich EIN Trigger (Inhalt-Tab) mit globaler Anzeige-Persistenz (eine page-weite `tripSaveCtl`, ein fixes Overlay), nicht drei unabhängige Trigger — vor Implementierung empirisch verifizieren.

### NEUER KRITISCHER BEFUND (nicht im Ticket) — schwerer als die Anzeige-Lüge
`frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte:56-70` + `frontend/src/lib/components/shared/VersandTab.svelte:76-130` (context="route"): Das bloße Öffnen des Trip-Editor-Tabs **„Versand"** kann einen **echten, ungesteuerten PUT** auf `/api/trips/{id}` auslösen — der `$effect` ruft `saveController.doSave(...)` bei jeder `reportConfig`-Änderung OHNE `userTouched`-Gate; die Mount-Normalisierung im VersandTab erzeugt genau diese Änderung. `TripTabs.svelte:217` mountet die Komponente bei jedem Tab-Wechsel neu → live. Schlägt der PUT fehl, sieht der Nutzer einen „Fehler beim Speichern"-Banner, ohne etwas getan zu haben. Das ist **dieselbe Wurzel** wie #1234/#1269, aber in schwererer Form (echter Schreibzugriff statt nur Anzeige) — und die #1234-Lücke, die dort nie geschlossen wurde.

### Root-Cause (konsolidiert)
Gemeinsame Wurzel: **Mount-Normalisierung/Hydration mutiert den verglichenen/gebundenen Zustand** und wird dadurch fälschlich als Nutzerabsicht gewertet:
- (a) false-„Nicht gespeichert": Compare-Layout-Tab (`CompareEditor.svelte:728-741` vs Mount-Baseline `:163-205`); Trip-Inhalt-Tab (`EditReportConfigSection.svelte:174-216` → `WeatherMetricsTab.svelte:507-513/490-493`).
- (b) false-„✓ Gespeichert HH:MM" ohne PUT: **lokal** `CompareEditor.svelte:240-241` (unbedingtes `setSaved()`) — einziger PUT-loser `setSaved`-Aufruf im gesamten FE (Grep bestätigt).
- (NEU) echter ungated PUT: Trip-Versand-Tab (`BriefingScheduleTab.svelte:56-70` + `VersandTab.svelte:76-130`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | (b) unbedingtes `setSaved()` Z. 240-241 entfernen/an echten PUT binden; (a) Layout-Baseline gegen Post-Hydration kanonisieren |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | (a) Mount-Normalisierungs-Diff nicht als dirty werten (Re-Baseline auf kanonisierte Form) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | MODIFY (evtl.) | Quelle des Trip-(a)-Diffs; ggf. idempotente Normalisierung |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | MODIFY (falls Scope A) | (NEU) `doSave()` Z. 68 hinter `userTouched`-Gate legen |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY (falls Scope A) | (NEU) Mount-Write-Back darf keinen ungewollten Save auslösen |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | evtl. MODIFY | ggf. Re-Baseline-/idle-ohne-Restempeln-Primitiv als geteilte Mechanik |

### Scope Assessment
- Files: 3 (nur Anzeige-Lügen a/b) bis 6 (inkl. neuem Versand-Write-Bug + geteiltes Primitiv)
- Risk Level: MEDIUM (Reaktivitäts-Timing; darf echtes Dirty/Saved nicht unterdrücken; Silent-Data-Loss-Falle bewusst vermeiden)

### Technical Approach (empfohlen)
Prinzip aus #1234 wörtlich befolgen: **Anzeige darf konservativ sein; nur SCHREIBEN wird gesten-gegatet.** Konkret: (a) an der Normalisierungs-Quelle beseitigen (kein spurious Diff), NICHT setDirty gaten. (b) `setSaved` nur aus echtem PUT. (NEU) das #1234-Gate-Primitiv (`weatherSaveGate`/`computeCompareAutoSaveAction`) auf den Versand/BriefingSchedule-Route-Pfad ausweiten — der hat heute GAR KEIN Gate.

### Scope-Entscheidung (PO 2026-07-16): ENTSCHIEDEN
**Alles unter #1269, EINE wartbare Lösung für Trip UND Ortsvergleich.** PO-Vorgabe wörtlich: „Thema nur einmal richtig lösen, für Trips und Ortsvergleiche gleichermaßen. Wartbarer Code ist oberste Maxime — keine individuellen, nicht wartbaren Lösungen." Versand-Write-Bug NICHT abgespalten.

### Design-Entscheidung (Best Practice + PO-Wartbarkeitsmaxime)
**Recherche-Grundlage:** Etablierte Auto-Save-Regeln (Quellen unten): (1) programmatische Änderungen ≠ Nutzeränderungen — „dirty" nur bei echter Geste; (2) eine Single Source of Truth für den Speicher-Zustand; (3) sicheres Scheitern.

**Kernbefund:** Die geteilten Primitive existieren bereits und sind gut entworfen:
- `SaveStatus` (`saveStatusStore.svelte.ts`) = Zustandsmaschine (idle/dirty/saving/error, savedAt), Single Source of Truth für den Speicher-Zustand. Regel: `setSaved()` (stempelt `savedAt`) ist NUR über `doSave()` nach erfolgreichem `saveFn()` erreichbar.
- `weatherSaveGate` (`weatherSaveGate.ts`) = reines Schreib-Gate (`catalogLoaded && userTouched → save`), context-agnostisch; `compareAutosave.ts` reused es bereits („keine Compare-eigene Gabelung").

**Das Problem ist Anwendung, nicht Architektur:** drei Flächen wenden die Primitive uneinheitlich an. Konsolidierungs-Fix (kein Neubau):
1. **Zustandsmaschine strikt einhalten:** rogue direkter `setSaved()` in `CompareEditor.svelte:240-241` entfernen → `setSaved` ausschließlich aus `doSave`-Erfolg. Fixt (b).
2. **Schreib-Gate überall:** JEDER Auto-Save-Trigger (Trip-Inhalt ✅, Compare ✅, **Trip-Versand ❌ heute gate-los**) läuft durch `weatherSaveGate`. Versand/`BriefingScheduleTab.doSave()` hinter das Gate legen. Fixt den neuen Write-Bug.
3. **Baseline-Korrektheit (fixt (a)):** die „clean"-Baseline muss die kanonisierte (post-Normalisierungs-)Editier-Form sein, damit Mount-Kanonisierung KEINEN Diff erzeugt. Einheitlich dort, wo beim Laden normalisiert wird (Compare-Layout, Trip-Inhalt, Versand). **Nicht** `setDirty` an `userTouched` gaten (Challenger-Warnung Silent-Loss) — echte Nutzer-Edits fließen unverändert über den Diff → konservativ „dirty".

**Robustheits-Invariante (der Grund, warum das sicher ist):** Anzeige und Schreiben scheitern asymmetrisch-sicher — Anzeige zeigt im Zweifel „dirty" (nie fälschlich „saved"), Schreiben unterbleibt im Zweifel (nie ungewollt). Keiner der Mechanismen muss perfekt sein; die ehrliche Anzeige ist das Sicherheitsnetz für ein evtl. übersehenes Gesten-Signal (F003/F004-Klasse).

### Open Questions (RED-Phase, empirisch)
- [ ] Lösen Trip-„Wertebereiche"/„Alarme" (a) unabhängig aus, oder ist es Anzeige-Persistenz eines einzigen Inhalt-Tab-Triggers? (bestimmt Anzahl der Baseline-Fixstellen)

### Best-Practice-Quellen
- To save or to autosave: Autosaving patterns (Medium/Brooklyn Dippo) — https://medium.com/@brooklyndippo/to-save-or-to-autosave-autosaving-patterns-in-modern-web-applications-39c26061aa6b
- Autosave design pattern (ui-patterns.com) — https://ui-patterns.com/patterns/autosave
- Saving and feedback (GitLab Pajamas Design System) — https://design.gitlab.com/patterns/saving-and-feedback/
