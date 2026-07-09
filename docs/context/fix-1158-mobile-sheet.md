# Context: fix-1158-mobile-sheet

Issue: #1158 — „Trips/Mobile" (priority:critical, type:bug, mobile, area:editor)

## Request Summary

Auf Mobile ist der Trip-Editor praktisch unbenutzbar: Der Wegpunkte-Editor
(Bottom-Sheet „Schublade") liegt über allem und lässt sich nicht schließen.
PO-Vorgabe im Issue: „Entweder schließbar machen oder entfernen (wird
wahrscheinlich mobil ohnehin nicht gemacht)."

## Befund (Root-Cause-Hypothese)

1. **Sheet ist `position: fixed` statt im Container verankert.**
   `Sheet.svelte` (Zeile 67) setzt auch bei `variant="embedded"`
   `position: fixed; left:0; right:0; bottom:64px; z-index:61`.
   Der Kommentar in `ProfileSheetEmbedded.svelte` behauptet dagegen, der Host
   (`position:relative; height:calc(100dvh-56px)`) skaliere die %-Höhen — das
   ist bei `fixed` falsch: Das Sheet klebt am **Viewport**, nicht am Tab-Inhalt,
   und überlagert damit die halbe Seite.

2. **Kein Schließen-Zustand.** `ProfileSheetEmbedded` reicht kein `onClose`
   an `Sheet` durch → kein Schließen-Button. Einziger Regler ist der
   „Höhe: peek/half/full"-Cycle-Button; kleinste Stufe `peek` = **32 %** der
   Viewport-Höhe (Sheet.svelte Zeile 39, `heights`), Start ist `half` = 55 %.
   Kommentar verspricht „peek ≈ 92px" — stimmt nicht mit 32 % überein.

3. **Etappen-Tab ist Default-Tab.** `TripEditView.svelte` Zeile 43
   (`activeTab = 'etappen'`) → die Schublade erscheint sofort beim Öffnen
   des Editors; die Vollbild-Karte (`height: calc(100dvh - 56px)`) füllt den
   Rest. Ergebnis: „versperrt alles".

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/mobile/Sheet.svelte` | Snap-Höhen (84/55/32 %), `position:fixed` auch für embedded; Schließen-Button nur wenn `onClose` gesetzt. Geteilt von 7 Komponenten (modal-Variante). |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | Die „Schublade": Profil + Wegpunktliste, Snap-Cycle-Button, kein onClose. |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Mobile-Editor (`@media max-width:899px`): Vollbild-Karte + Sheet + Etappen-Pill. Zeilen 380–422 (Markup), 627–658 (CSS). |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Default-Tab `etappen` (Zeile 43); Header mit Speichern/Abbrechen oben. |
| `frontend/src/lib/components/edit/StageSelectSheet.svelte` | Zweites (modales) Sheet im Mobile-Editor — funktioniert mit onClose, dient als Vorbild. |
| `frontend/src/lib/components/edit/issue_542_mobile_editor.test.ts` | Bestehende Tests des Mobile-Editors (Issue #542) — dürfen nicht brechen bzw. sind anzupassen. |

## Dependents (Blast Radius)

- `EditStagesPanelNew` wird von **TripEditView** (Trip bearbeiten), **TripNewEditor**
  (Trip-Anlage-Wizard) und `EditStagesSection` genutzt → Fix wirkt auf beide Flows.
- `Sheet.svelte` (modal-Variante) nutzen: CompareEditor, MCompareActionSheet,
  WeatherMetricsTab, StageSelectSheet, TripNewEditor — Änderungen an Sheet.svelte
  dürfen die modal-Variante nicht verändern. `variant="embedded"` hat genau
  **einen** Nutzer: ProfileSheetEmbedded.

## Existing Specs

- `docs/specs/modules/wegpunkt_editor_handoff.md` (AC-5: ProfileSheetEmbedded)
- `docs/specs/modules/issue_373_mobile.md` (AC-4/AC-6: Sheet-Grundkomponente)
- `docs/specs/modules/issue_503_wegpunkt_editor_fix.md` (Editor-Grid Desktop)
- `docs/specs/modules/issue_585_waypoint_editor_design.md` (Design-Fidelity Editor)

## Existing Patterns

- `StageSelectSheet` (gleicher Mobile-Editor) nutzt die modal-Variante mit
  `open`/`onClose` und funktioniert — Pattern für „schließbar".
- Design-Fidelity-Regel: Mobile-Editor-Design stammt aus Handoff
  (`wegpunkt_editor_handoff.md`); strukturelle Abweichung = Design-Entscheidung,
  bei UI-Änderung prüft fresh-eyes-inspector Screenshots.

## Risks & Considerations

- **Produktentscheidung nötig (Spec-Phase):** schließbar machen vs. Wegpunkte-
  Editor auf Mobile ganz entfernen (PO tendiert im Issue zur Entfernung als Option).
- `Sheet.svelte` ist geteilt — modal-Verhalten (Overlay, Body-Scroll-Lock,
  z-index 60/61) darf sich nicht ändern.
- Design-Fidelity: fix_622_794_mobile_fidelity.md und #585 haben Pixel-Gates
  für den Editor — Layoutänderung muss als bewusste Bug-Behebung dokumentiert sein.
- E2E: Reproduktion + Nachweis via Playwright mit Mobile-Viewport (<900px)
  gegen Staging, echter Klick-Pfad (Tab-Klick, nicht goto — Memory-Regel).
