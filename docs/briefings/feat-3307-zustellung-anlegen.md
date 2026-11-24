---
spec_file: docs/specs/modules/feat_3332_zustellung_anlegen_trip.md
spec_sha256: 1bc2da864ccb34dd09eceb4b7f98bd552bb62f8bf073fb60efd47a7bcb946852
spec_frozen_sha256: b21902756d4f0114d5ecac7821b3d0502f9a9831ad663678467fb10370deb3a0
---

# PO-Briefing: feat-3307-zustellung-anlegen

- **Spec:** docs/specs/modules/feat_3332_zustellung_anlegen_trip.md
- **Issue:** #3332
- **Erstellt:** 2026-11-24

## Was gebaut wird

Beim Trip-Anlegen bedient der Nutzer Versandzeiten, Kanäle, Alarm-Kanäle und Stille Stunden im selben Reiter wie im Hub.

## Definition of Done

Ein angelegter Trip enthält genau die im Zustellungs-Reiter eingestellten Werte, und der Hub zeigt sie identisch an.

## Wie geprüft wird

Automatische Tests und Staging-Durchlauf mit zwei Nutzern belegen Werte, einen einzigen Anlege-Aufruf und unveränderte Startwerte; Ortsvergleich ist nicht Teil.

## Kritische Anmerkungen

- Nur Trip-Anlegen; Ortsvergleich-Anlegen folgt separat (#3333), das Ziel „beide Anlegeseiten“ ist erst danach erreicht.
- Im Trip-Anlegen entfallen der Schalter Großwetterlage und die Hilfe-Infobox im Zustellungsschritt; nicht verlangt, aber dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
