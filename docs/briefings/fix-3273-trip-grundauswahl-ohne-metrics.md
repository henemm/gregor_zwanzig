---
spec_file: docs/specs/modules/fix_3273_trip_grundauswahl_ohne_metrics.md
spec_sha256: d967b58e193077b9e15a2029ad46618a4dc4cff5f9768609bf5eb300dca2d469
spec_frozen_sha256: 67a08d85bb26824a358140c806d74878ee76731ee360f94e312fe3912b4382c0
---

# PO-Briefing: fix-3273-trip-grundauswahl-ohne-metrics

- **Spec:** docs/specs/modules/fix_3273_trip_grundauswahl_ohne_metrics.md
- **Issue:** #3273
- **Erstellt:** 2026-11-23

## Was gebaut wird

Der Mail-Prüfer erwartet bei Trips ohne gespeicherte Auswahl dieselben Spalten wie die echte Mail, statt Fehlalarme zu melden.

## Definition of Done

Die Mail-Prüfung des Befundfalls aus dem Ticket meldet keine Soll-Verletzungen mehr, und der Vergleich mit dem echten Laden aller Profile stimmt.

## Wie geprüft wird

Automatische Tests vergleichen mit von Hand notierten Listen und dem echten Laden aller Profile; ein Lauf gegen eine Staging-Mail ist nicht vorgesehen.

## Kritische Anmerkungen

- Zusatz: Die Spec behandelt auch Trips mit alter Wetter-Konfiguration; im Ticket nicht genannt, folgt aber der Produktregel.
- Quelle weicht vom Ticket-Wortlaut ab (Profil-Tabellen statt Produktfunktion), bewusst, damit Produktfehler auffallen; Ergebnis gleich.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
