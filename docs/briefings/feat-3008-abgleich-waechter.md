---
spec_file: docs/specs/modules/feat_3008_abgleich_waechter.md
spec_sha256: e36dd71e0d80ff0b205f5d114d761a3c739cf095a7cb055d508480d009be6e75
spec_frozen_sha256: 6fe582051777f3401d5106cef63596d38d4131b2213b650253bb5636a18eea18
---

# PO-Briefing: feat-3008-abgleich-waechter

- **Spec:** docs/specs/modules/feat_3008_abgleich_waechter.md
- **Issue:** #3008 und #3011
- **Erstellt:** 2026-11-19

## Was gebaut wird

Automatische Prüfungen melden veraltete Besitzer-Einträge, vertauschte Kopf-Knöpfe und fälschlich als bekannt geltende „+ …“-Texte sofort als Fehler.

## Definition of Done

Alle acht Kriterien sind durch grüne Tests belegt, die Gegenprobe findet keine unbewachte Verfälschung, und die Abnahme gegen Staging läuft ohne neue Fehlbefunde.

## Wie geprüft wird

Netzfreie Tests mit den echten Listen und verfälschten Kopien belegen jede Anforderung; die Produktoberfläche selbst wird nicht verändert oder geprüft.

## Kritische Anmerkungen

- Zusatz: Geprüft werden auch Abschnitts-Besitzer, nicht nur Element-IDs. Die Abnahme kann dadurch künftig strenger anschlagen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
