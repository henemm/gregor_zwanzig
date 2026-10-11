---
spec_file: docs/specs/modules/begriff_erklaerung_infobox.md
spec_sha256: 90963ac7c1871e44088fa5882bb94e31936b0ce5a2b56447a91791ba05a2def4
---

# PO-Briefing: feat-2521-s1-erklaerung-infobox

- **Spec:** docs/specs/modules/begriff_erklaerung_infobox.md
- **Issue:** #2521
- **Erstellt:** 2026-10-09

## Was gebaut wird

Neue Nutzer sehen beim Anlegen eines Trips oder Ortsvergleichs Erklärungen zu vier Fachbegriffen und feste Überspringen-Hinweise.

## Definition of Done

Überspringbare Anlege-Reiter zeigen den Standard-Hinweis; Tippen auf ⓘ öffnet die Erklärung, Esc oder Tippen daneben schließt sie.

## Wie geprüft wird

Tests belegen Hinweise, Öffnen, Schließen, Kontrast und Wortwahl; ob die genannten Standardwerte im System wirklich gelten, prüft nur ein Teil.

## Kritische Anmerkungen

- Abweichung: Infobox fehlt beim Bearbeiten bestehender Trips; Anfrage verlangte „immer sichtbar“ in jedem überspringbaren Reiter.
- Alarm-Standard (Telegram an) im Ortsvergleich unsicher; Analyse sah dort nur E-Mail, Text könnte falsch sein.
- Zusatz: neues sichtbares Label „Dringlichkeits-Schwelle“; Umfang über Standardgrenze.

## Freigabe-Frage

Passt es dir, dass die Infobox nur beim Anlegen erscheint und nicht beim Bearbeiten bestehender Trips und Ortsvergleiche?
