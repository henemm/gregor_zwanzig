---
spec_file: docs/specs/modules/store_scope_call_guard.md
spec_sha256: 7828c6fb1e7b5e3b064a9d6109c4e1dc8060acfe7f4adef69240094e0c557419
---

# PO-Briefing: feat-2156-mandanten-waechter

- **Spec:** docs/specs/modules/store_scope_call_guard.md (Version 2.0)
- **Issue:** #2156
- **Erstellt:** 2026-09-20

## Was gebaut wird

Zwei automatische Prüfungen verhindern künftig, dass Programmcode Nutzerdaten ohne korrekte Kontobindung verarbeitet; Ausnahmen stehen sichtbar begründet im Code.

## Definition of Done

Beide Prüfungen laufen fehlerfrei durch den bestehenden Code, jede Ausnahme trägt eine Begründung im Quelltext, ein Hinweis-Eintrag mit Prüftermin steht in der Betriebsdoku.

## Wie geprüft wird

Automatisierte Tests bestätigen aktuell null Verstöße; geprüft wird nur die Form der Begründung, nicht ihre Richtigkeit.

## Kritische Anmerkungen

- Diese Lieferung ändert Produktivdateien mit Kommentarzeilen — deshalb sind erneut Staging-Prüfung und Produktions-Deployment nötig, anders als reine Testarbeit.
- Eine falsch begründete Ausnahme-Markierung bleibt unentdeckt — der Wächter prüft nur Vorhandensein der Begründung, nicht ihre Richtigkeit.
- Der Wächter deckt nur direkte Handler-Aufrufe ab, nicht dahinterliegende Hilfsfunktionen — heute unauffällig, aber technisch nicht ausgeschlossen.

## Freigabe-Frage

Sollen wir freigeben, obwohl Marker nur formal geprüft werden und ein Prod-Deploy nötig wird?
