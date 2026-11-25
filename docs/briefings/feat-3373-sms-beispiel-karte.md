---
spec_file: docs/specs/modules/feat_3373_sms_beispiel_karte.md
spec_sha256: f3a645c8b5d3a76b678a160d74a7af342542d7aa9eefb3adec1c0224516fcddb
spec_frozen_sha256: 21d273b22ae57e639406e17770070547971d46efa012a529b042043ba4e407f8
---

# PO-Briefing: feat-3373-sms-beispiel-karte

- **Spec:** docs/specs/modules/feat_3373_sms_beispiel_karte.md
- **Issue:** #3373
- **Erstellt:** 2026-11-25

## Was gebaut wird

Das SMS-Beispiel in „Was steht wo“ zeigt exakt die echte Trip-SMS, und die Zeile Temperatur hat keine doppelten Werte mehr.

## Definition of Done

Die Karte zeigt Kopf E1, Nachtwert, Spitzen und Gewitter-Folgetag wie die versandte SMS; der SMS-Haken bei Temperatur ist gesperrt.

## Wie geprüft wird

Automatische Tests vergleichen Beispiel und echte SMS Zeichen für Zeichen, auch mit zwei Nutzern; echte Wetterlagen bildet das feste Beispiel nicht ab.

## Kritische Anmerkungen

- Zusatz: E-Mail- und Telegram-Beispiel zeigen künftig ebenfalls die Nacht; nicht verlangt, aber getestet, Versand bleibt unverändert.
- Haken bei Temperatur wird gesperrt statt durchgereicht; vom Ticket erlaubt. Gespeicherte Haken bleiben, wirken aber nicht.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
