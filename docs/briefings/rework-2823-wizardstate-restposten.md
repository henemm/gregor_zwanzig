---
spec_file: docs/specs/modules/rework_2823_wizardstate_restposten.md
spec_sha256: 60e4c9bd3a680e3e31a801af7df132790806f79ba46a3df90ee39c33ca15bfcf
spec_frozen_sha256: 60f629de15089f265a4ee4cfa25de2cc245dbffacd0a82b956884578c57dce2e
---

# PO-Briefing: rework-2823-wizardstate-restposten

- **Spec:** docs/specs/modules/rework_2823_wizardstate_restposten.md
- **Issue:** #2823
- **Erstellt:** 2026-11-05

## Was gebaut wird

Ein veralteter Staging-Test wird repariert und irreführende Kommentare im Code werden bereinigt; für Nutzer ändert sich nichts.

## Definition of Done

Der reparierte Staging-Test läuft gegen Staging grün, und kein Kommentar nennt mehr den gelöschten Zustandsträger.

## Wie geprüft wird

Staging-Lauf und Gegenprobe mit absichtlich verfälschter Speicherung belegen die Kanal-Abwahl; Kommentare werden nur per Textsuche und Zeilenzählung geprüft, nicht durch Verhalten.

## Kritische Anmerkungen

- Der Staging-Test läuft nicht in der automatischen Prüfung, nur manuell; er kann künftig erneut unbemerkt veralten.
- Anfrage nennt 11 Dateien, Spec 12 Kommentarstellen; harmlos, da kein Verhalten betroffen ist.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
