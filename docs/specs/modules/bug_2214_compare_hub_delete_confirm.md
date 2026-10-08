---
entity_id: bug_2214_compare_hub_delete_confirm
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [compare, hub, delete, confirm-dialog, bug]
---

# Compare-Hub: Bestätigungsdialog vor „Löschen" (#2214)

## Approval

- [ ] Approved

## Purpose

Im Compare-Hub (`/compare/[id]`) löscht die Kebab-Aktion „Löschen" den Ortsvergleich sofort und
unwiderruflich — ohne Rückfrage (Datenverlust-Risiko, #1199 C1-38). Der Trip-Hub und die
Compare-Liste fragen bereits per `ConfirmDialog` nach; der Compare-Hub zieht gleich.

## Source

- **File:** `frontend/src/routes/compare/[id]/+page.svelte`
- **Identifier:** `handleAction` (Zweig `'delete' | 'trash'`), `deletePreset`

## Estimated Scope

- **LoC:** ~30
- **Files:** 1 Quelle + 1 Test
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ConfirmDialog` (`$lib/components/molecules`) | Molecule | geteilter Bestätigungsdialog — dasselbe Bauteil wie Trip-Hub (`trips/[id]/+page.svelte`) und Compare-Liste |

## Implementation Details

```
handleAction('delete' | 'trash')  ->  deleteDialogOpen = true   (kein fetch)
ConfirmDialog
  title="Vergleich endgültig löschen?"
  description='"<Name>" wird unwiderruflich gelöscht.'
  confirmLabel="Löschen", confirmVariant="destructive"
  data-testid="compare-detail-delete-confirm-dialog"
  cancelTestid="compare-detail-delete-confirm-cancel"
  confirmTestid="compare-detail-delete-confirm-yes"
  disabled={isDeleting}
  onConfirm -> deletePreset()  (DELETE /api/compare/presets/{id}, dann /compare)
  onCancel / onOpenChange(false) -> deleteDialogOpen = false
```

Beide Einstiege (Desktop-Kebab `CompareKebab` und Mobil-Pfad `onAction={handleAction}`) laufen
über `handleAction` — eine Änderung deckt beide ab. Testids folgen dem Trip-Hub-Muster
(`trip-detail-delete-confirm-*`). Kein neues Bauteil (Pendant-Regel erfüllt).

## Expected Behavior

- **Input:** Klick auf „Löschen" im Hub-Kebab
- **Output:** Bestätigungsdialog; Löschung erst nach „Löschen" im Dialog
- **Side effects:** DELETE-Request nur nach Bestätigung

## Acceptance Criteria

- **AC-1:** Given ein geöffneter Ortsvergleich im Compare-Hub / When der Nutzer im Kebab-Menü „Löschen" wählt / Then erscheint ein Bestätigungsdialog mit dem Namen des Vergleichs und es wird noch kein Lösch-Request gesendet.
  - Test: Komponententest klickt Kebab → „Löschen", prüft sichtbaren Dialog (Name im Text) und dass `fetch` keinen DELETE erhalten hat.

- **AC-2:** Given der Bestätigungsdialog ist offen / When der Nutzer „Abbrechen" klickt oder den Dialog schließt / Then schließt sich der Dialog, der Vergleich bleibt erhalten und es wird kein Lösch-Request gesendet.
  - Test: Komponententest klickt „Abbrechen", prüft Dialog weg und kein DELETE.

- **AC-3:** Given der Bestätigungsdialog ist offen / When der Nutzer „Löschen" im Dialog bestätigt / Then wird genau ein DELETE an `/api/compare/presets/{id}` gesendet und der Nutzer landet auf `/compare`.
  - Test: Komponententest bestätigt, prüft genau einen DELETE auf die richtige URL und Navigation nach `/compare`.

- **AC-4:** Given das Löschen schlägt serverseitig fehl / When der Nutzer bestätigt hat / Then bleibt der Nutzer im Hub und sieht „Löschen fehlgeschlagen."
  - Test: Komponententest mit DELETE-Antwort 500, prüft Fehlermeldung und keine Navigation.

## Known Limitations

- Kein Undo/Papierkorb — außerhalb des Scopes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Angleichung an bestehendes Trip-Hub-Muster mit vorhandenem Molecule.

## Changelog

- 2026-10-08: Initial spec created (#2214)
