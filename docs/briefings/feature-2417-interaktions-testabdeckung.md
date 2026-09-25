---
spec_file: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
spec_sha256: 555b67b42f27f1ae722dac98c0b9b0238ccb2d434f5cfe37bc7cbd04ac0969e6
---

# PO-Briefing: feature-2417-interaktions-testabdeckung

- **Spec:** docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
- **Issue:** #2417
- **Erstellt:** 2026-09-25

## Was gebaut wird

Jeder angebotene Befehl wird über den echten Eingang jedes Kanals geprüft; dabei gefundene Fehler werden behoben.

## Definition of Done

Jeder angebotene Befehl liefert nachweislich die richtige Antwort auf jedem geprüften Kanal, ohne Falsch- oder Fehlermeldungen.

## Wie geprüft wird

Automatisierte Tests senden echte Befehle mit und ohne Kartenlink über E-Mail, Telegram und Satelliten-SMS; das physische Garmin-Gerät wird nicht getestet.

## Kritische Anmerkungen

- Ortsvergleichs-Mail zeigt gar keine Befehle, manche Befehle sind nutzbar aber unsichtbar — beides nur ins Nachfolge-Ticket verschoben.
- Vier Kanäle gelten als gleichrangig, doch normale SMS bleibt in dieser Spec komplett ungetestet und unrepariert.
- Telegram-Befehl /status ändert sich dauerhaft: liefert künftig die Etappenliste, Wetterüberblick nur noch über /glance.

## Freigabe-Frage

Akzeptierst du, dass die fehlenden Befehle in der Vergleichs-Mail und der geänderte /status-Befehl separat behandelt werden?
