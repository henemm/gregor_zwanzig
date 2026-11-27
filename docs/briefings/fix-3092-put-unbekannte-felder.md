---
spec_file: docs/specs/modules/fix_3092_unbekannte_felder_erhalten.md
spec_sha256: 28e8c35faedc08c88c1373d595414f33e1647f6bc35d81af100429cf82d3a9fc
spec_frozen_sha256: 98b24025ad5e5b774604713088c0d8c3bb61de3685fcd9a185f5f3d51c1af6cb
---

# PO-Briefing: fix-3092-put-unbekannte-felder

- **Spec:** docs/specs/modules/fix_3092_unbekannte_felder_erhalten.md
- **Issue:** #3092
- **Erstellt:** 2026-11-27

## Was gebaut wird

Beim Speichern von Trips und Orts-Vergleichen gehen unbekannte Zusatzfelder in der gespeicherten Datei nicht mehr verloren.

## Definition of Done

Nach dem Speichern auf Staging steht ein zusätzlich eingetragenes Feld weiterhin in der Trip- und Vergleichsdatei, und der Produktions-Selbsttest läuft fehlerfrei.

## Wie geprüft wird

Automatische Tests lesen die gespeicherte Datei nach PUT und PATCH, mit zwei Nutzern; verschachtelte Felder und der Python-Speicherweg sind nicht abgedeckt.

## Kritische Anmerkungen

- Nur oberste Feldebene geschützt; unbekannte Felder innerhalb von Etappen oder Anzeige-Einstellungen gehen weiterhin verloren (dokumentierte Einschränkung).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
