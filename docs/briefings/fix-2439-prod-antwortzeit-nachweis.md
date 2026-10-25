---
spec_file: docs/specs/modules/feat_2439_prod_antwortzeit_nachweis.md
spec_sha256: 49039406afea416575dd225a6a1c9d13ea463e162cd1aacb0271ee25f6ca8305
spec_frozen_sha256: 693f4535df071743c7be06c93345e69f73178468f71d17ab7ebff3bda3b41324
---

# PO-Briefing: fix-2439-prod-antwortzeit-nachweis

- **Spec:** docs/specs/modules/feat_2439_prod_antwortzeit_nachweis.md
- **Issue:** #2439
- **Erstellt:** 2026-10-25

## Was gebaut wird

Messwerkzeug und Test werden angepasst, damit die Antwortzeit der Befehle auf Produktion für Korsika, Premium-SMS und Telegram belegbar wird.

## Definition of Done

Auf Produktion belegt das Werkzeug je Kanal mindestens drei kalte Läufe unter 60 Sekunden, der Test-Trip ist danach wieder entfernt.

## Wie geprüft wird

Deterministische Tests mit aufgezeichneten Journalzeilen prüfen Grenzwerte und Zählung; die echte Produktionsmessung ist ein manuelles Protokoll im Issue, nicht automatisiert.

## Kritische Anmerkungen

- Telegram auf Produktion eventuell nicht gebunden; dann bleibt Telegram unbelegt, Schließen von #2439 unklar.
- Zwei der vier roten Messtests vom 24.10. sind ungeklärt und nicht abgedeckt.
- Median-Grenze 45 Sekunden für Korsika ist strenger als das Ticket.

## Freigabe-Frage

Freigeben, obwohl Telegram womöglich unbelegt bleibt und zwei rote Messtests ungeklärt sind?
