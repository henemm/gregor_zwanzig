---
spec_file: docs/specs/modules/paritaets_bestandsaufnahme.md
spec_sha256: 966e960249e10358ea1a411a8af5a9460fcfda8eb89f799834fb9a18e5678633
spec_frozen_sha256: bb836a7c85fb584ee8a1c9ad7ddfb4e947e2589740966144f3433997b42e2e20
---

# PO-Briefing: feature-1986-paritaets-bestandsaufnahme

- **Spec:** docs/specs/modules/paritaets_bestandsaufnahme.md
- **Issue:** #1986
- **Erstellt:** 2026-11-13

## Was gebaut wird

Eine vollständige, priorisierte Liste aller doppelt gepflegten Stellen samt Urteil, ob zusammenführbar, ohne Änderung am Produkt.

## Definition of Done

Die Liste steht im Ticket, jedes Paar hat ein Urteil, jede zusammenführbare Doppelung hat ein Folge-Ticket mit Priorität, Produktcode bleibt unverändert.

## Wie geprüft wird

Ein automatischer Test prüft die Begründungs-Kommentare der begründet getrennten Tests; Liste, Folge-Tickets und unveränderter Produktcode werden nur durch Durchsicht abgenommen.

## Kritische Anmerkungen

- Echte Menge ist rund 65 Testdateien statt der im Titel genannten zwölf; Titel wird nur im Text korrigiert.
- Vier von fünf früheren Unklar-Fällen wurden technisch als „begründet getrennt" entschieden, einer als zusammenführbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
