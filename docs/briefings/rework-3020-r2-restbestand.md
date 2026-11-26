---
spec_file: docs/specs/modules/rework_3020_altbausteine_entfernen.md
spec_sha256: 0ee75edde919755fc128fe04f473cd6bf5321ed1965b4710572bbc562dc3c853
spec_frozen_sha256: a60aedf35394a1fd4427113b4cb142b061104e9ee159c12de1528c2f6c81673b
---

# PO-Briefing: rework-3020-r2-restbestand

- **Spec:** docs/specs/modules/rework_3020_altbausteine_entfernen.md
- **Issue:** #3020
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die letzten elf ungenutzten Bausteine der alten Wetter- und Zustellungs-Oberfläche werden gelöscht; Nutzer sehen keinen Unterschied.

## Definition of Done

Alle Prüfungen laufen grün, die Elementliste von Trip- und Orte-Seiten ist in Deutsch und Englisch vorher wie nachher identisch, Produktion ist ausgeliefert.

## Wie geprüft wird

Wächter-Tests belegen die Löschung und gesenkte Obergrenzen; Sichtgleichheit belegt nur der Elementlisten-Vergleich plus Rauchtest, kein eigener Verhaltenstest.

## Kritische Anmerkungen

- Die Spec nennt nun 11 statt 42 Dateien, weil der Rest schon anderweitig gelöscht wurde; kein Umfangsverlust.
- Mehrere Löschungs-Prüfungen sind reine Strukturprüfungen, keine Verhaltensnachweise; so in der Spec offen benannt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
