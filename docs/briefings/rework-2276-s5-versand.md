---
spec_file: docs/specs/modules/rework_2276_s5_versand.md
spec_sha256: 77b97f3441bd2abf4eb04d0a2ffe9923de516a7208087cd8e66785590642a592
---

# PO-Briefing: rework-2276-s5-versand

- **Spec:** docs/specs/modules/rework_2276_s5_versand.md
- **Issue:** #2276
- **Erstellt:** 2026-09-20

## Was gebaut wird

Der Versand-Reiter im Ortsvergleich speichert Einstellungen künftig sofort selbst, wie bereits Alarme und Wertebereiche.

## Definition of Done

Eine Änderung im Versand-Reiter wird sofort gespeichert und zeigt bei einem Konflikt „Nochmal speichern" statt einer allgemeinen Fehlermeldung.

## Wie geprüft wird

Automatisierte Tests prüfen jede der zwölf Anforderungen einzeln; die alte, nicht automatisch mitlaufende Testspur wird vor Abschluss von Hand nachvollzogen.

## Kritische Anmerkungen

- Diff-basierter Rollback ist eine bewusste Verhaltensänderung, kein reiner Umbau — schützt gleichzeitige Alarm-Änderungen vor Verlust.
- Der alte Regressionstest für diesen Reiter läuft künftig nur noch manuell gegen die Testumgebung, nicht automatisch.
- Drei ungenutzte Alarm-Altfelder bleiben bewusst im Speicherpfad erhalten, weil ihr Entfernen aktuell Daten löschen würde.

## Freigabe-Frage

Sind der bewusste Rollback-Verhaltenswechsel und der nur manuell geprüfte Alt-Test für Sie akzeptabel, um diese Scheibe freizugeben?
