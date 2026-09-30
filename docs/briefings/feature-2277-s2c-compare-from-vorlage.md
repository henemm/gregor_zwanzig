---
spec_file: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md
spec_sha256: 2f2df4a440ff3b77ef65b9c3a491c9256ee4b8bf10877da4ad3bff89a5ef34f9
---

# PO-Briefing: feature-2277-s2c-compare-from-vorlage

- **Spec:** docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md
- **Issue:** #2277 (Scheibe S2c, nur Ticket-AC-4)
- **Erstellt:** 2026-09-30

## Was gebaut wird

Die Anlege-Seite für Ortsvergleiche lässt sich per Adresse mit den Werten eines bestehenden Vergleichs vorausfüllen.

## Definition of Done

Alle Einstellungen erscheinen vorausgefüllt, Speichern erzeugt einen neuen Vergleich, das Original bleibt unverändert.

## Wie geprüft wird

Tests prüfen jedes Feld; ein Zwei-Nutzer-Test prüft, dass fremde Vergleiche nie sichtbar werden.

## Abweichungen vom Ticket

- Nur Ortsvergleich, kein Trip: Trip-Vorlagenweg ist tot, eigene Scheibe, Vermerk in #1199.
- Kein Button „Als Vorlage verwenden", erst mit #2278; nur per Adresszeile erreichbar.
- Name mit Zusatz „(Kopie)".

## Kritische Anmerkungen

- Ohne Button findet kein Nutzer die Funktion; sie bleibt bis #2278 praktisch unsichtbar.
- Ticket-AC-4 ist nur halb erfüllt; #2277 darf danach nicht geschlossen werden.
- Der Ortsvergleich mobil wurde nie im Browser gemessen; dieser Test ist die erste Messung.

## Freigabe-Frage

Einverstanden mit Ortsvergleich-only, ohne Button?
