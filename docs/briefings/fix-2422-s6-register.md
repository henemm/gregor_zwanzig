---
spec_file: docs/specs/modules/fix_2422_s6_register_leeren.md
spec_sha256: a64866b056e1b717233da7733d84c80c63b7e42ccd7e16a808c472069adb473e
---

# PO-Briefing: fix-2422-s6-register

- **Spec:** docs/specs/modules/fix_2422_s6_register_leeren.md
- **Issue:** #2422
- **Erstellt:** 2026-09-30

## Was gebaut wird

Gefühlte Temperatur, Roh/Einfach und Windrichtung wirken in SMS und Telegram künftig genau wie eingestellt.

## Definition of Done

Der Abgleich-Test kennt nur noch die bewusste Telegram-Grenze; SMS zeigt Gefühlte Temperatur, Telegram keine leere Windrichtungs-Spalte.

## Wie geprüft wird

Tests schicken echte Trips durch alle Kanäle und vergleichen Einstellung mit Text; echte Handy-Zustellung bleibt ungeprüft.

## Kritische Anmerkungen

- Gefühlte Temperatur erscheint als TF, obwohl FL fast dasselbe misst; Alternative liegt bereit, Ihre Entscheidung nötig.
- Wolken und CAPE erscheinen für Bestandsnutzer in SMS als Stufe (CT:SCT@4) statt Zahl; Stufenwörter sind ein Vorschlag.
- Zusatz: Editor bietet Roh/Einfach im SMS-Reiter für Gewitter, Wind, Sonne nicht mehr an; niemand verlangte das.

## Freigabe-Frage

Geben Sie TF, die neuen Wolken-Stufen und den Wegfall der SMS-Umschalter frei?
