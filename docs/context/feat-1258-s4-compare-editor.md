# Context: feat-1258-s4-compare-editor

**Issue:** #1258, Scheibe **S4** — Compare-Editor-Integration des geteilten Alarme-Tabs (AC-16…AC-18)
**Track:** Full Process (Intake-Score 4: Scope High, Blast Radius Medium, Unsicherheit Medium)
**Programm-Spec:** `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` (AC-16/17/18 = S4; Abschnitt 7 Flächen)
**Programm-Context:** `docs/context/feat-1258-compare-alarme-tab.md` · **S3-Vorlage:** `docs/context/feat-1258-s3-trip-alarme-tab.md`
**Voraussetzungen:** S1 ✅ (official_warnings Datenmodell+RMW, auch ComparePreset), S2 ✅ (Baustein), S3 ✅ live (285c5c16, Trip-Wiring als Muster)

## Request Summary

Der Compare-Editor rendert den geteilten `AlarmeTab context="vergleich"` statt
der bespoke `CompareAlarmSection` (#1170-Ablösung), der Tab „Alarme" wird auch
im Create-Wizard sichtbar (F3, Position zwischen „Wertebereiche" und
„Versand"), `compareWizardState.officialWarningsEnabled` wird persistent
verdrahtet, und der `VersandTab`-vergleich-Zweig verliert seine Alert-Karten.

## Related Files (alle Befunde verifiziert, Stand 285c5c16)

### Compare-Editor
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | `TAB_DEFS` :110-117 (`alarme` edit-only am ENDE, Gating :116); weitere `id !== 'alarme'`-Gating-Stellen :255, :454-462, :963-969, :1219; CompareAlarmSection-Render Desktop :1168-1169 + Mobile :1312-1313 (Import :53); VersandTab-Render :1162-1167/:1306-1311; `handleSave` :277-383 — Alarm-Felder in edits :322-336, Dirty-Tracking `initial` :136-174/`dirty` :175-201, Post-Save-Reset :353-376 — **officialWarningsEnabled fehlt überall**; Desktop-Create-CTAs :1131/:1148/**:1158** (`continue-versand` im Layout-Fuß ← F3-Umbau); Mobile `handleMobileNext` :464-471 + Floating-CTA-Labels :1320-1346 |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | `TAB_ORDER` :8 = `['vergleich','orte','idealwerte','layout','versand']` (Progression/unlock/done — `alarme` einfügen) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `CompareEditorEdits` :14-63 + Body-Bau :116-159 — kein `officialWarnings`-Feld |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | `officialWarningsEnabled` :56 (S2, unverdrahtet); `saveNewPreset`-POST :91-135 und `saveComparePreset`-edits :157-176 tragen es NICHT |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | Edit-Hydration :39-61 (alle Alarm-Felder AUSSER officialWarningsEnabled) |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | bespoke #1170; einzige Referenz = CompareEditor → **nach Umstellung löschen** (Hub referenziert sie nicht) |
| `frontend/src/lib/types.ts` | `ComparePreset` :483-526 hat **KEIN `official_warnings`** → Typ ergänzen (Trip hat es :311) |

### Geteilte Bausteine
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | vergleich-Zweig bindet an `wiz.*` inkl. `wiz.officialWarningsEnabled` :90-104; speichert NUR im route-Zweig selbst (:207-222 `if (context !== 'route') return`) — Compare-Persistenz bleibt beim Editor-`handleSave` |
| `frontend/src/lib/components/shared/VersandTab.svelte` | vergleich-Zweig :227-285; Alert-Sektion :272-279 (CooldownCard :275, QuietHoursCard :276, VTAlertSample :278) zieht aus; betroffene Imports :20-21/:26 |
| `frontend/src/lib/components/shared/versand-tab/alertDeliveryPayload.ts` | seit S3 ohne Produktiv-Import (Kommentar :27-31), hängt nur noch am eigenen Unit-Test → **in S4 löschen (Modul + Test)** |

### Backend (existiert seit S1 — S4 ist FE-only)
| Datei | Relevanz |
|---|---|
| `internal/model/compare_preset.go` | `OfficialWarnings` :85 |
| `internal/handler/compare_preset.go` | Create-Default `{Enabled:false}` :231-232; Update-RMW :331-342 (bewahrt Bestand + Sources, wenn Body das Feld nicht trägt — Editor-PUT ohne Feld war bisher deshalb verlustfrei) |

### E2E (brechen beim Umbau)
| Datei | Bruchstelle |
|---|---|
| `frontend/e2e/compare-alarm-config.spec.ts` | AC-1 :56-75 (`compare-alarm-section`-Testid verschwindet; Cooldown/Quiet ziehen Versand→Alarme), AC-2 :78-110 (Cooldown-Persistenz über Versand-Tab) |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | AC-1 :56 (Alert-Zustellung im Versand), AC-4 :110-127 (prüft Cooldown NICHT im Alarme-Tab — kehrt sich um; Spec-AC-18 ersetzt versand_tab_vergleich AC-4), AC-6 :189-233 (Create-Tab-Kette orte→idealwerte→layout→versand + POST-Body — um `alarme` erweitern) |
| `compare-editor-fidelity-s8d.spec.ts`, `compare-flow-navigation.spec.ts`, `compare-mobile-vervollstaendigung.spec.ts` | Create-Wizard-Tab-Ketten / Mobile-CTA-Labels — prüfen und mitziehen |

## Existing Patterns

- **S3-Vorlage:** Tab-Einfügung + atomarer VersandTab-Rückbau in einem Schritt (F002-Race-Klasse); E2E-Umverdrahtung im selben Commit.
- **Persistenz-Weiche des Bausteins:** vergleich-Zweig schreibt nur `wiz.*` — Persistenz macht Editor-Save (POST `saveNewPreset` / PUT `compareEditorSave`) bzw. später Hub-Bridge (S5).
- **Go-RMW deckt Übergang:** Handler bewahrt `official_warnings` bei Bodies ohne das Feld — die neue Verdrahtung muss das Feld explizit senden, Altbestand bleibt bei Nicht-Änderung erhalten.

## Dependencies

- **Upstream:** S2-Baustein (`AlarmeTab` vergleich-Zweig fertig), S1-Backend (Feld+RMW), compareWizardState-Context.
- **Downstream/Abgrenzung:** **Hub (`CompareTabs`) + `compareHubWizardBridge` sind S5** (AC-19: Hydration + `handleAlarmeCommit`) — S4 fasst die Bridge NICHT an; `hydrateWizardStateFromPreset`/`buildHubPutPayload` bleiben ohne officialWarnings (Known-Gap bis S5). S8d-Staging-Suite (Tab-Ketten-Semantik).

## Analysis

### Type
Feature (Full Process, Scheibe S4 des PO-approved Programms #1258)

### Entscheidungen (Analyse-Synthese + PO-Entscheid 2026-07-15)

- **E1 Wizard-Kette = ECHTE STATION (PO via AskUserQuestion, F3 wörtlich):**
  `alarme` wird reguläre Station der Create-Progression. `TAB_ORDER`
  (`compareEditorLogic.ts:8`) wächst auf
  `['vergleich','orte','idealwerte','layout','alarme','versand']`,
  Progress um `alarmeVisited` erweitert; Desktop-CTA im Layout-Fuß zeigt
  auf `alarme` (neue Testid `compare-editor-continue-alarme`), neuer CTA
  im Alarme-Fuß auf `versand`; Mobile `handleMobileNext` + Floating-CTA-
  Labels analog. Fachlicher Grund: Neuanlagen starten mit amtlichen
  Warnungen AUS (F1) — die Station führt Anleger bewusst an die
  Alarm-Optionen. Bewusst brechende Tests (mitzuziehen):
  `compareEditorLogic.test.ts:29-36` (TAB_ORDER=5),
  `compare-editor-slice1.spec.ts:50-59` („5 Segmente"/„1 / 5"),
  `compare-flow-navigation.spec.ts:446-469` (CTA-Kette),
  `compare-editor-fidelity-s8d.spec.ts:296-327` (Mobile-Labels),
  `versand-tab-vergleich.spec.ts:189-233` (AC-6-Kette).
- **E2 Position: … idealwerte → layout → alarme → versand** („alarme vor
  versand", F3-Wortlaut; bei Station die günstigere Kante — nur die
  letzte Progression-Kante layoutVisited→versand wird ersetzt, die
  ältere idealsVisited→layout-Kante bleibt unberührt). Erfüllt AC-16
  („zwischen Wertebereiche und Versand").
- **E3 officialWarnings-Verdrahtung (6 Stellen, verifiziert):**
  `saveNewPreset`-POST (`compareWizardState.svelte.ts:100`ff,
  unconditional `official_warnings: {enabled}` analog Geschwister-
  Booleans), `compareEditorSave.ts` Edits-Typ :14-63 + Body-Bau
  :116-159, `CompareEditor.handleSave` 4 Touch-Points (initial :136-174,
  dirty :175-201, snapshot/build :277-349, reset :353-376),
  Edit-Hydration (`routes/compare/[id]/edit/+page.svelte:39-61`),
  `ComparePreset`-Typ (`types.ts:483-526`). **`sources` sendet das FE
  nie** — Go-RMW (`compare_preset.go:331-342`) erhält Bestand-Sources
  feldgenau (verifiziert).
- **E4 notifyCount/Jump vergleich:** kein neuer Container nötig —
  `CompareEditor` ist der Container; `notifyCount = $derived(
  wiz.corridors.filter(c => c.notify).length)` (CorridorEditor vergleich
  schreibt corridors live in wiz), `onJumpToWertebereiche={() =>
  switchTab('idealwerte')}`; `AlarmeTab context="vergleich" {wiz}` an
  BEIDEN Render-Stellen (Desktop :1168-1169, Mobile :1312-1313).
- **E5 Atomarer Umzug + Aufräumen:** Persistenz-Verdrahtung (E3) zuerst
  und separat verifizierbar; dann in EINEM Schritt: TAB_DEFS-Gating weg
  + Station (E1/E2) + beide Render-Stellen auf AlarmeTab +
  VersandTab-vergleich-Alert-Sektion raus (:272-279, Imports :20-21/:26)
  + `CompareAlarmSection.svelte` löschen (einziger Referenzort) +
  `versand-tab/alertDeliveryPayload.ts` samt Unit-Test löschen (ohne
  Produktiv-Import seit S3) + E2E-Umverdrahtung im selben Commit.
  Cooldown/Quiet binden in beiden UIs an DIESELBEN wiz-Runen (kein
  Datenverlust-Race wie S3-F001 — zentraler handleSave), aber
  Doppel-Sichtbarkeit verletzt AC-18 → atomar.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `compare/CompareEditor.svelte` | MODIFY | Gating weg, Station-CTAs, AlarmeTab-Render 2x, handleSave 4 Touch-Points, notifyCount |
| `compare/compareEditorLogic.ts` (+ .test.ts) | MODIFY | TAB_ORDER 6, alarmeVisited |
| `compare/compareEditorSave.ts` | MODIFY | officialWarnings Edit-Feld + Body |
| `compare/compareWizardState.svelte.ts` | MODIFY | saveNewPreset-POST official_warnings |
| `routes/compare/[id]/edit/+page.svelte` | MODIFY | Hydration officialWarningsEnabled |
| `types.ts` | MODIFY | ComparePreset.official_warnings |
| `shared/VersandTab.svelte` | MODIFY | vergleich-Alert-Sektion Rückbau |
| `compare/CompareAlarmSection.svelte` | DELETE | durch geteilten Baustein ersetzt (#1170-Ablösung) |
| `shared/versand-tab/alertDeliveryPayload.ts` (+ Test) | DELETE | ohne Produktiv-Import |
| E2E: compare-alarm-config, versand-tab-vergleich, compare-flow-navigation, compare-editor-slice1, compare-editor-fidelity-s8d | MODIFY | Testid-/Ketten-Migration |

### Scope Assessment
- Files: ~14 · Estimated LoC: ~250-350 → **LoC-Override nötig (bei
  Spec-Freigabe einholen)** · Risk: MEDIUM-HIGH (Create-Wizard-Progression
  ist S8d-fidelity-getestet; FE-only, kein Schema/Backend)

### Implementierungs-Reihenfolge (risikogetrieben)
1. `types.ts` + `compareEditorSave.ts` + `saveNewPreset` + Hydration + handleSave-Touch-Points (Persistenz separat verifizierbar)
2. ATOMAR: Station (TAB_ORDER/CTAs/Progress) + Gating weg + AlarmeTab-Render 2x + VersandTab-Rückbau + Löschungen + E2E-Migration
3. Staging-E2E (AC-16/17/18 + AC-9/AC-10 vergleich inkl. Radar-Positivfall)

## Geklärte Analyse-Punkte (Ausgangsfragen)

1. **Position relativ zu `layout`:** AC-16 sagt „zwischen Wertebereiche und Versand". Heute: vergleich→orte→idealwerte(Wertebereiche)→layout→versand. Option A: …layout→**alarme**→versand (minimale CTA-Änderung: Layout-CTA zeigt auf alarme, neuer alarme-CTA auf versand; „Alarme direkt vor Versand" wie im Trip). Option B: …idealwerte→**alarme**→layout→versand (Wertebereiche↔Alarme benachbart wie im Trip, aber CTA-Kette + done/unlock-Logik stärker berührt). Design-Soll `screen-compare-editor.jsx:19-25` hinkt hinterher (kennt kein alarme).
2. **Create-Wizard-Semantik:** `alarme` wird Teil der `TAB_ORDER`-Progression (unlock/done/CTA) — was ist der „done"-Zustand eines optionalen Alarm-Tabs (alles Default = übersprungen erlaubt)? S8d-CTA-Kette laut F3 um `alarme` vor `versand` erweitern.
3. **`notifyCount`/`onJumpToWertebereiche` im vergleich-Kontext:** Woher kommt der Warnen-Zähler (CorridorEditor vergleich synct in wiz — welches Feld) und wohin springt der Jump-Link (Tab `idealwerte`)?
4. **officialWarnings-Sendeformat:** POST/PUT senden `official_warnings: {enabled}` (Pflichtfeld-Guard analog alarmeDeliveryPayload F002?) — `sources` nie vom FE schreiben (Handler-RMW merged Sources).
5. **Aufräum-Umfang:** CompareAlarmSection.svelte löschen + zugehörige Tests; versand-tab/alertDeliveryPayload.ts + Test löschen.

## Risks & Considerations

- **Create-Wizard-Regression:** Die Progression (unlock/done/CTA) ist S8d-fidelity-getestet — Tab-Ketten-Specs müssen konsistent mitgezogen werden, sonst Staging-E2E rot.
- **Doppel-Schreibpfad-Übergang:** Cooldown/Quiet binden heute in VersandTab-vergleich UND (nach Umstellung) im AlarmeTab an dieselben `wiz.*`-Runen — beide gleichzeitig sichtbar wäre kein Datenverlust (gleiche Rune), aber der Rückbau muss im selben Schritt erfolgen (Konsistenz, AC-18).
- **Hub zeigt bis S5 keinen Alarme-Tab** — gewollt (AC-19 = S5); Editor-Verdrahtung darf die Bridge nicht anfassen.
- **officialWarnings-Dirty-Tracking:** Vergessenes Feld in initial/dirty/reset (CompareEditor :136-201/:353-376) → Save-Button bleibt tot oder Reset verliert Zustand — alle drei Stellen müssen erweitert werden.
- **LoC-Budget 250:** FE-only, aber viele Berührpunkte (~10 Dateien + 3-5 E2E-Specs) — Überschreitung möglich, ggf. Override bei Spec-Freigabe einholen.
