---
spec_file: docs/specs/modules/feat_3155_ein_name_ausblick.md
spec_sha256: c7dfccf6be528414d1987aef1b10376a5d6e009cc6bea6c653291b64e302f564
spec_frozen_sha256: 585f0c52c965c575a797abd6e36fba232e1e1d72ab61b6dd9a7a7dc39d78c113
---

# PO-Briefing: feat-3155-ein-name-ausblick

- **Spec:** docs/specs/modules/feat_3155_ein_name_ausblick.md
- **Issue:** #3155
- **Erstellt:** 2026-11-19

## Was gebaut wird

Der Ausblick heißt überall „3-Tages-Ausblick“ und wird in Mail und Telegram von einem einzigen Schalter gesteuert.

## Definition of Done

Kein Text sagt mehr „Mehrtages-Trend“, der Ausblick erscheint in allen Ausgaben nur im eingestellten Morgen- oder Abend-Briefing, live auf Produktion.

## Wie geprüft wird

Fall-Listen und echt zugestellte Staging-Mails (Morgen/Abend, Deutsch/Englisch) beweisen es; SMS bleibt unberührt, weil sie keinen Ausblick enthält.

## Kritische Anmerkungen

- Bewusste Änderung: Bestands-Trips mit ausgeschaltetem Ausblick zeigen ihn in Telegram nicht mehr.
- Zusatz: Der Haken „Ausblick“ im E-Mail-Inhalt heißt künftig „Großwetterlage“.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
