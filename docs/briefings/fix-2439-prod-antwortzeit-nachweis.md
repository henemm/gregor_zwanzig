---
spec_file: docs/specs/modules/feat_2439_prod_antwortzeit_nachweis.md
spec_sha256: b7d6b67c68d6cdd2cc16ba6ea0a03b81d36c6114bd345346d6eff53ca07d51e9
spec_frozen_sha256: 0a7d9d9a5a8cdbfc6ff1bbc65d894c624d47a0474a8319b3afdce67567b69ed3
---

# PO-Briefing: fix-2439-prod-antwortzeit-nachweis

- **Spec:** docs/specs/modules/feat_2439_prod_antwortzeit_nachweis.md
- **Issue:** #2439
- **Erstellt:** 2026-10-26

## Was gebaut wird

Das Messwerkzeug prüft die Antwortzeit der Befehle auf Produktion für Korsika, Premium-SMS und Telegram gegen die Zielgröße.

## Definition of Done

Auf Produktion belegt das Werkzeug je Befehl mindestens drei kalte Läufe unter 60 Sekunden; der Test-Trip ist danach wieder entfernt.

## Wie geprüft wird

Tests mit aufgezeichneten Journalzeilen prüfen Grenzwerte und Zählung; die echte Produktionsmessung ist ein manuelles Protokoll, nicht automatisiert.

## Kritische Anmerkungen

- Telegram auf Produktion womöglich nicht gebunden; dann bleibt Telegram unbelegt und #2439 lässt sich nicht sauber schließen.
- Neu: Unter drei kalten Läufen gilt „nicht belegt“ statt Median-Urteil; die Median-Grenze 45 Sekunden ist strenger als das Ticket.
- Zwei der vier roten Staging-Messtests vom 24.10. sind ungeklärt und nicht abgedeckt.

## Freigabe-Frage

Freigeben, obwohl Telegram womöglich unbelegt bleibt und zwei rote Messtests ungeklärt sind?
