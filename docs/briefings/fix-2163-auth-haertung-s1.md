---
spec_file: docs/specs/modules/auth_haertung_python_2163.md
spec_sha256: c0f72abf277550909989b2276570e8561feaecb4cfb30f8298e239606dea4b8e
spec_frozen_sha256: 7acfae956b6bc8049fc2cde2a7711ba6b7f124e244822270be550134f5b41408
---

# PO-Briefing: fix-2163-auth-haertung-s1

- **Spec:** docs/specs/modules/auth_haertung_python_2163.md
- **Issue:** #2163
- **Erstellt:** 2026-11-01

## Was gebaut wird

Das Wetter-Backend lehnt ungültige Nutzerkennungen ab, bevor es Dateien liest, und die Geheimnis-Vorlage wird vollständig.

## Definition of Done

Ungültige Kennungen führen zu "nicht gefunden" ohne Dateizugriff, Handversand von Trip und Ortsvergleich funktioniert auf Staging weiter, und die Vorlage nennt alle Geheimnisse.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern auf echten Dateien belegen die Sperre; Staging prüft nur, dass Versand weiter klappt, keinen Angriff.

## Kritische Anmerkungen

- Neue Geheimnis-Einträge stehen nur als Kommentar; die echten 1Password-Einträge fehlen weiterhin und müssen später angelegt werden.
- Fehlerbild ist bewusst "nicht gefunden" statt eigener Meldung; praktische Gefahr war ohnehin gering, da Anmeldung davorliegt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
