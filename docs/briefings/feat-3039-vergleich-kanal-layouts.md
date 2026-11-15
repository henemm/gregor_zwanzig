---
spec_file: docs/specs/modules/feat_3039_vergleich_kanal_layouts.md
spec_sha256: 389968dd326ac54392a1c52522e589797e13c68e8db1340c80e92938fb27ffaa
spec_frozen_sha256: d16d96ba7f82f9946541bce5fcd793498f134f1b9e0ce0a1f972a55bcf8c9055
---

# PO-Briefing: feat-3039-vergleich-kanal-layouts

- **Spec:** docs/specs/modules/feat_3039_vergleich_kanal_layouts.md
- **Issue:** #3039
- **Erstellt:** 2026-11-15

## Was gebaut wird

Beim Ortsvergleich lässt sich je Kanal einstellen, welche Werte erscheinen, in welcher Reihenfolge und ob als Zahl oder einfach.

## Definition of Done

Auf Staging zeigt ein Vergleich Böen in der Mail einfach und in Telegram als Zahl; ein Bestandsvergleich liefert unveränderte Ausgabe.

## Wie geprüft wird

Tests prüfen die erzeugte Ausgabe je Kanal, mit zwei Nutzern und unveränderten Referenzmails; die Bedienoberfläche selbst kommt erst mit #3031.

## Kritische Anmerkungen

- Ohne Angabe gilt im Vergleich "Zahl", nicht der Katalog-Standard wie beim Trip; so bleibt der Bestand unverändert.
- Zusätzlich: Speichern in anderen Reitern löscht die Kanal-Einstellungen nicht mehr; alte Löschfunktion und Skript entfallen (neues ADR).
- Telegram zeigt bei Werten ohne eigene Einfach-Darstellung weiterhin die Zahl.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
