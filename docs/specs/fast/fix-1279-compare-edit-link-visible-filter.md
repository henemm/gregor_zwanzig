# Mini-Spec: fix-1279-compare-edit-link-visible-filter

## Update nach Erst-Implementierung (PO-Entscheidung)

Der Developer Agent hat den `:visible`-Fix umgesetzt, aber dabei einen echten
fachlichen Widerspruch aufgedeckt: Commit `addf58a3` (#1261, "Bearbeiten
auffindbar + Autospeichern, Trip-Parität") hat **nach** der #530-Regel
("kein Bearbeiten-Link auf den Compare-Tabs") bewusst einen dauerhaften
Header-Bearbeiten-Button eingeführt, der unabhängig vom aktiven Tab sichtbar
ist. Die AC-5-Tests aus #530 sind damit für aktive Presets strukturell
unerfüllbar — nicht durch einen Test-Bug, sondern weil #1261 die Regel
inhaltlich überholt hat.

**PO-Entscheidung (2026-07-16):** AC-5 ist veraltet. Die 4 Tests werden
entfernt.

## Was ändert sich
- `frontend/e2e/design-compliance-group-a.spec.ts` — der gesamte
  `test.describe('#530 Compare Hub · Keine Wizard-Links in Tabs', ...)`-Block
  (die 4 `AC-5: <tab>-Tab hat keinen Link auf /edit`-Tests) wird entfernt, da
  die zugrunde liegende Regel durch #1261 überholt ist.
- Kurzer Kommentar an der Löschstelle: Verweis auf #1261 (Header-Bearbeiten-
  Button ist gewollt) und #1279 (Testentfernung), damit die Historie
  nachvollziehbar bleibt.

## Was darf sich nicht ändern
- Kein Eingriff in `frontend/src/routes/compare/[id]/+page.svelte`.
- AC-2/AC-3 (Draft zeigt "Setup abschließen", aktives Preset zeigt "Test
  senden" + "Bearbeiten" im Header) bleiben unverändert bestehen — sie sind
  die aktuell gültige Regel.
- `seedComparePresets`/`cleanupComparePresets`/`activePresetId` bleiben
  erhalten, falls sie von anderen Tests in der Datei (#531 etc.) noch
  gebraucht werden — vor dem Löschen prüfen.

## Manuelle Test-Schritte
1. `npx playwright test design-compliance-group-a.spec.ts` gegen Staging
   laufen lassen (volle Datei, nicht nur `-g "AC-5"` — sicherstellen, dass
   keine anderen Tests durch das Entfernen des Blocks kaputtgehen).
2. Keine `AC-5`-Tests mehr vorhanden; alle verbleibenden Tests grün.

## Inline-Test (wird während Implementierung geschrieben)
- [x] Entfernter Test-Block — kein Ersatztest nötig, da die Regel selbst
  entfällt (nicht "Bug behoben", sondern "Anforderung obsolet").
