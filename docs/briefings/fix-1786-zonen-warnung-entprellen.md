---
spec_file: docs/specs/modules/fix_1786_zonen_warnung_entprellen.md
spec_sha256: 14442b8606d41359e21d2566080af15e3046176289135f24dac59737a27a18de
spec_frozen_sha256: 467db1bdda6872f14b74c88ea7aefa04553b725a7c5e8672ee977a5dce79083d
---

# PO-Briefing: fix-1786-zonen-warnung-entprellen

- **Spec:** docs/specs/modules/fix_1786_zonen_warnung_entprellen.md
- **Issue:** #1786
- **Erstellt:** 2026-11-04

## Was gebaut wird

Die Zeitzonen-Warnung im Protokoll erscheint nur noch einmal pro Preset und Tag statt bis zu 312-mal.

## Definition of Done

Bei unauflösbarer Zeitzone steht je Preset und Tag genau eine Warnzeile im Protokoll, und das Ergebnis bleibt Weltzeit.

## Wie geprüft wird

Automatische Tests mit echten Aufrufen belegen Einmal-Warnung, Tageswechsel und parallele Aufrufe; Verhalten nach Neustart und Live-Protokoll werden nicht geprüft.

## Kritische Anmerkungen

- Ticket-Vorschlag, die Zone erst nach den Prüfungen aufzulösen, entfällt begründet: Fälligkeit und Wochentag würden falsch berechnet.
- Entprellt wird nach Weltzeit-Tag, nicht Ortstag; ein Neustart erzeugt höchstens eine zusätzliche Zeile.
- Aufrufe ohne Preset-Bezeichnung werden nicht entprellt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
