# Context: feat-2277-s4-anlege-lockengine

## Request Summary
#2277 S4 (Epic #2345 P2): Die Freischalt-Logik ("Lock-Engine") der Anlege-Seiten existiert zweimal
(`trip-new/tripNewLogic.ts`, `compare-new/compareNewLogic.ts`). Ziel: EINE geteilte Logik, die
Compare-Kopie fällt (Ticket-AC-5, Teil 2: `compareNewLogic` ohne produktiven Importeur).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/compare-new/compareNewLogic.ts (69 Z.) | Kopie: unlockedTabs/doneTabs/progressCount/canActivate, Progress-Objekt-Signatur, 6 Reiter, Zähler gedeckelt 6 |
| frontend/src/lib/components/trip-new/tripNewLogic.ts (247 Z.) | Gleiche Funktionen, aber 7 positionale Booleans/Strings, 7 Reiter, Fortschritt zählt nur route/etappen/metriken/versand (/4), `canSave` |
| compare-new/CompareNewEditor.svelte:32-137 | einziger produktiver Importeur der Compare-Logik |
| trip-new/TripNewEditor.svelte:40-168 | einziger Importeur der Trip-Logik |
| compare-new/__tests__/compareNewLogic.test.ts (240 Z.), compareNewVorlage.test.ts:21, compare/__tests__/compare_layout_tab_dissolution.test.ts:43, compare/__tests__/issue_683_wizard_remove.test.ts:255/268 | Tests/Wächter, die den Compare-Dateipfad kennen |
| frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts:45,99 | nur Kommentarverweise auf compareNewLogic |
| trip-new/__tests__/tripNewLogic.test.ts (420 Z.) | Tests der Trip-Logik inkl. Payload-Builder (bleibt) |
| docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md | Vorgänger-Scheibe, Reiterkette beider Seiten bereits angeglichen |

## Existing Patterns
- Lock-Kette beider Seiten identisch ab Wetter-Metriken: Metriken -> Wertebereiche -> Alarme -> Versand; Anlegen erst nach Besuch Versand.
- Unterschiede nur vorn: Trip = route/etappen(/wegpunkte), Compare = vergleich/orte (Name + >=2 Orte); Fortschrittszähler Trip /4 vs. Compare /6.
- Geteilte Bausteine liegen in `frontend/src/lib/components/shared/` mit `context="route"|"vergleich"` (Trip/Compare-Code-Teilung, PO-Vorgabe).
- Reine Logik: DOM-frei, node:test-fähig.

## Dependencies
- Upstream: keine (reine Funktionen). tripNewLogic importiert zusätzlich Alarm-Payload-Helfer (bleibt dort).
- Downstream: nur die zwei Editoren und die oben genannten Tests.

## Existing Specs
- feat_2277_s3 / s2a / s2b / s2c unter docs/specs/modules/; Epic-Kontext #2345, Dach #1374.

## Risks & Considerations
- Fortschrittszähler unterscheidet sich bewusst (/4 vs /6): Verhalten je Seite darf sich nicht ändern; Angleichung wäre eine eigene Produktentscheidung.
- Wächtertests (issue_683, layout_tab_dissolution) referenzieren den Compare-Dateipfad — beim Löschen mitziehen, nicht abschwächen.
- Neue geteilte Datei: Ablageort in `shared/` vorher per `ls` prüfen; Pendant-Sperre (pendant_gate) beachten.
- Mutations-Gegenprobe: Freischaltung muss an der Wirkstelle (Editor-Reiterleiste/Anlegen-Knopf) geprüft sein, nicht nur in der Logik.
- Commit im Worktree (drei Wächter, Message-Datei).

## Analysis

### Type
Feature (Refactoring ohne Verhaltensänderung) — Ticket-AC-5 Teil 2 (`compareNewLogic` ohne produktiven Importeur).

### Befund
Beide Dateien haben dieselbe Kette **ab Wetter-Metriken** (Metriken → Wertebereiche → Alarme → Versand; „anlegen/speichern" erst nach Versand-Besuch). Unterschied nur vorn: Trip = name+startDate → etappen → (wegpunkte+metriken per `etDone`); Compare = name → orte (≥2) → metriken. Fortschrittszähler Trip: 4 feste Schritte; Compare: Anzahl erledigter, gedeckelt 6. Signaturen verschieden (Trip: 7 positionale Args, Compare: Progress-Objekt).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| frontend/src/lib/components/shared/anlegeLockEngine.ts | CREATE | Geteilter Kern: Schwanz-Kette (metriken→wertebereiche→alarme→versand), `canFinish`, generische `progressCount(done, steps)`; Vorderteil als Parameter (`frontUnlocked`/`metrikenUnlockable`) |
| trip-new/tripNewLogic.ts | MODIFY | `unlockedTabs`/`doneTabs`/`progressCount`/`canSave` delegieren an Kern (Signaturen bleiben, Payload-Builder unberührt) |
| compare-new/CompareNewEditor.svelte | MODIFY | importiert Kern statt `compareNewLogic`; Compare-eigen nur Vorderteil (name, pickedCount≥2) |
| compare-new/compareNewLogic.ts | DELETE | Kopie fällt |
| compare-new/__tests__/compareNewLogic.test.ts | MOVE/MODIFY | Tests gegen geteilten Kern (Kern-Test in shared/__tests__), Compare-Vorderteil-Test bleibt |
| compare-new/__tests__/compareNewVorlage.test.ts:21, compare/__tests__/compare_layout_tab_dissolution.test.ts:43, compare/__tests__/issue_683_wizard_remove.test.ts:255/268 | MODIFY | Pfadverweise nachziehen, nicht abschwächen |
| frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts:45,99 | MODIFY | nur Kommentarverweise |

### Scope Assessment
- Files: ~8 (1 neu, 1 gelöscht, Rest Anpassungen) · Estimated LoC: +90/-120 produktiv, Tests ±150
- Risk Level: MITTEL — Verhalten muss bit-gleich bleiben (Zähler /4 vs /6, Lock-Hinweise); reine Funktionen, aber Editor-Verdrahtung betroffen.

### Technical Approach
EIN Kern in `shared/` (Muster Trip/Compare-Teilung, `context="route"|"vergleich"` nur wo nötig — hier genügt Parameter für Vorderteil/Schritte). Trip-Wrapper behalten ihre Signatur (minimale Eingriffsfläche in den 1170-Zeilen-Editor); Compare-Editor wird auf den Kern umgestellt, die Datei fällt. Fortschrittszähler-Unterschied bleibt als Parameter erhalten (keine Produktentscheidung). Vorher `ls shared/` (erledigt: keine Namenskollision), Pendant-Sperre beachten (neue shared-Datei ist das Gegenteil eines Pendants).

### Dependencies
Upstream keine; Downstream nur die zwei Editoren + oben gelistete Tests/Wächter.

### Mutations-Gegenprobe (Vorgabe für Phase 5)
Verfälschen: Kern-Kette (z. B. alarme ohne wbVisited), Compare-Vorderteil (pickedCount≥2→≥1), Zähler-Deckel; mindestens ein Test muss an der Wirkstelle (Reiterleiste disabled / Anlegen-Knopf im Editor, SSR-Harness) rot werden — nicht nur in der Logik.

### Open Questions
- [ ] Keine PO-relevanten. (Ticket-AC-3 Reiter-Reihenfolge ist durch S3 erledigt; AC-5 Rückbau-Rest `EditReportConfigSection` ggf. eigene Scheibe — Spec soll klären, ob S4 nur Lock-Engine umfasst.)
