---
spec_file: docs/specs/modules/fix_3437_orte_erklaer_gesperrt.md
spec_sha256: 2879820c734317c1dff287f2b3fc731ca01e412a865e4364c1776a285e48c946
spec_frozen_sha256: 566ccfd4ceb929bc3e1fd26643b7b3f6aea9ccfa8697a2dc2e72930346924432
---

# PO-Briefing: fix-3437-orte-erklaer-gesperrt

- **Spec:** docs/specs/modules/fix_3437_orte_erklaer_gesperrt.md
- **Issue:** #3437
- **Erstellt:** 2026-11-28

## Was gebaut wird

Im Reiter Orte steht der Mockup-Erklärtext, und gesperrte Kanäle zeigen in der Alarm-Spalte nur noch „gesperrt“.

## Definition of Done

Auf Staging und Produktion zeigen Reiter Orte und Zustellung den Mockup-Wortlaut, Deutsch wie Englisch, im Trip wie im Orts-Vergleich; Abgleich ohne Abweichung.

## Wie geprüft wird

Automatische Tests prüfen Wortlaut und Sperrverhalten je Grund; der Live-Abgleich auf Staging zeigt, ob die echte Seite stimmt.

## Kritische Anmerkungen

- Löst die frühere Festlegung „gesperrt: Grund“ ab; folgt dem freigegebenen Mockup, keine neue Entscheidung nötig.
- Test-Schicken-Menü zeigt weiter den Grund; Zellen und Menü sehen bewusst unterschiedlich aus.
- Ursprungsanfrage nur über das Kontextdokument geprüft, Issue-Text selbst war nicht abrufbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
