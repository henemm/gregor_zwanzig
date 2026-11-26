---
spec_file: docs/specs/modules/feat_3102_phase3g_abschluss.md
spec_sha256: bfbbd3c2f62ea19f683f7d4286da273f68db1cd6d1c3fe167f68e47932d550c4
spec_frozen_sha256: 1622ab894e4d42a566901cbbdebe3e538797a712182913d48f091756b61a8736
---

# PO-Briefing: feat-3102-phase3g-abschluss

- **Spec:** docs/specs/modules/feat_3102_phase3g_abschluss.md
- **Issue:** #3102
- **Erstellt:** 2026-11-26

## Was gebaut wird

Phase 3 wird abgeschlossen: Nachträglich eingeschaltete Messgrößen erscheinen nachweislich in allen Mails, und die Altlasten-Entfernung ist belegt.

## Definition of Done

Alle Prüfungen der vier Kanäle sind grün, die fünf offenen Fälle erledigt, und die Nachzählung meldet in Staging und Produktion null Altfelder.

## Wie geprüft wird

Automatische Tests mit echten Mails belegen die fünf Fälle; Nachzählung der Altfelder und Doku-Nachzug werden nur manuell belegt, nicht automatisch getestet.

## Kritische Anmerkungen

- Migration, Löschung der Vergleichstests und Import-Sperre werden nicht neu gebaut, sondern als früher erledigt belegt.
- Kein Produktionscode betroffen; bliebe ein neuer Test rot, wäre doch ein Eingriff nötig.
- Fall zur Vorlagen-Reihenfolge bleibt bewusst offen (eigenes Ticket).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
