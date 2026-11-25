---
spec_file: docs/specs/modules/feat_3373_sms_beispiel_karte.md
spec_sha256: 68ae8169b9f59cc414b9cb958a503394ded1cd13bca44e9a2f8432e0c6754238
spec_frozen_sha256: c986426694e77ea0c72accd0e3562bfd1af1eabb546b8f9460b5ef258955a606
---

# PO-Briefing: feat-3373-sms-beispiel-karte

- **Spec:** docs/specs/modules/feat_3373_sms_beispiel_karte.md
- **Issue:** #3373
- **Erstellt:** 2026-11-25

## Was gebaut wird

Das SMS-Beispiel in „Was steht wo“ zeigt für Trips Zeichen für Zeichen die echte SMS, ohne doppelte Temperatur-Angaben.

## Definition of Done

In der Karte eines Prüf-Trips beginnt das Beispiel mit E1, zeigt Nacht und Gewitter-Folgetag, und der Temperatur-Haken ist gesperrt.

## Wie geprüft wird

Tests vergleichen Beispiel und echte SMS zeichengleich bei vier Trips und zwei Nutzern; unverändert bleibt der Versand, nicht geprüft wird echtes Wetter.

## Kritische Anmerkungen

- Beim Temperatur-Haken wurde „sperren“ gewählt, nicht „durchreichen“; beides war im Ticket erlaubt, sichtbar ändert sich die Bedienung.
- E-Mail- und Telegram-Beispiel zeigen künftig ebenfalls die Nacht; das hat niemand verlangt, folgt aber aus dem gemeinsamen Beispiel.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
