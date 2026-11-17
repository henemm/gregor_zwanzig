---
spec_file: docs/specs/modules/compare_briefing_aufbau.md
spec_sha256: f7890855ffb67360cbdea54aeb21304d5b514ff14c4067ebe3228e5ef2a15452
spec_frozen_sha256: 288fa4dc17dc52d907edc61c6ddc7c5a5049a56a6ae0554a0adb795e62236b1c
---

# PO-Briefing: feat-2983-gemeinsamer-berichtsaufbau

- **Spec:** docs/specs/modules/compare_briefing_aufbau.md
- **Issue:** #2983
- **Erstellt:** 2026-11-17

## Was gebaut wird

Der Ortsvergleich setzt seinen Bericht für Vorschau und Versand an einer einzigen Stelle zusammen, sodass beide nicht mehr abweichen können.

## Definition of Done

Versandte Ortsvergleichs-Berichte sind Zeichen für Zeichen unverändert, die Vorschau zeigt dieselben Texte, und eine echt zugestellte Staging-Mail besteht die Prüfung.

## Wie geprüft wird

Automatische Tests vergleichen Versand vorher und nachher sowie Vorschau gegen Versand, mit zwei Nutzern; Inhalt der Mail beurteilt nur die Staging-Prüfung.

## Kritische Anmerkungen

- Nur der Ortsvergleich wird umgebaut; der Trip-Teil des Tickets ist als #3128 abgespalten und bleibt vorerst doppelt.
- Die Vorschau zeigt Telegram bei Kurzform künftig wie der Versand: kleine, gewollte Verhaltensänderung.
- Die Vorschau hat im Produkt keinen Aufrufer mehr; Nutzen liegt vor allem in der Absicherung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
