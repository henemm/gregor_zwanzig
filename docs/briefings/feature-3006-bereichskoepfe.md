---
spec_file: docs/specs/modules/feat_3006_bereichskoepfe.md
spec_sha256: 4c91185972b71206da7f7643a7a2d4b5e12541b8034e0661ff28eda6db56410b
spec_frozen_sha256: 88405194a958ca83fd8040dfec204186691eddf1ab9901a64de60114d832361f
---

# PO-Briefing: feature-3006-bereichskoepfe

- **Spec:** docs/specs/modules/feat_3006_bereichskoepfe.md
- **Issue:** #3006
- **Erstellt:** 2026-11-17

## Was gebaut wird

Jeder Reiter von Trip und Orten zeigt oben eine einheitliche Überschrift mit Erklärsatz, auf Deutsch und Englisch.

## Definition of Done

Alle acht Reiter zeigen ihren Kopf in Deutsch und Englisch wie im Mockup, und der Abgleich meldet ihn auf Staging als gefunden.

## Wie geprüft wird

Automatische Darstellungstests je Reiter und Sprache sowie Abgleich auf Staging; der Reiter Übersicht nur per Test, nicht im Abgleich.

## Kritische Anmerkungen

- Übersicht-Kopf ist im Abgleich nicht nachweisbar, weil die Elementliste ihn noch nicht erfasst (#2969); nur Testnachweis.
- Orte: Überschrift „Verglichene Orte" entfällt, der Knopf wandert nach oben und heißt „+ Ort hinzufügen" (Mockup).
- Der Übersicht-Satz ist ein Platzhalter aus dem Mockup.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
