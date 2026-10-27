---
spec_file: docs/specs/modules/shared_preview_tab.md
spec_sha256: 725e52eee11a0c52f329524b8635a144d98131b848d539512b3d500a2760e001
spec_frozen_sha256: ad8ed170bfd77a231e86e375257928381fd981c65482c76140de71870ec49d1d
---

# PO-Briefing: feat-2283-vorschau-baustein

- **Spec:** docs/specs/modules/shared_preview_tab.md
- **Issue:** #2283
- **Erstellt:** 2026-10-19

## Was gebaut wird

Trip und Ortsvergleich zeigen im Vorschau-Reiter dieselbe Anordnung für E-Mail, SMS und Telegram; Ortsvergleich bekommt echte Alarm-Vorschau.

## Definition of Done

In beiden Ansichten erscheint die Vorschau gleich mit drei Kanälen, ohne Senden-Knopf, und die Alarm-Vorschau im Ortsvergleich zeigt echte Daten.

## Wie geprüft wird

Automatische Tests vergleichen Vorschau mit dem echten Versandtext und prüfen Nutzertrennung; Premium-SMS wird nur als Hinweis gezeigt, nicht vorab dargestellt.

## Kritische Anmerkungen

- Senden-Knopf im Vorschau-Reiter entfällt; Senden geht nur noch über den Hub-Kopf, bisher gab es zwei Wege.
- Trip-Vorschau bekommt neu Telegram und Umschalter; das Ticket verlangte "Anordnung wie im Trip".
- Ortsvergleich-Vorschau bleibt langsam, bis zu 75 Sekunden.

## Freigabe-Frage

Gleiche Vorschau in beiden Ansichten, ohne Senden-Knopf im Reiter und mit neuem Telegram im Trip — einverstanden?
