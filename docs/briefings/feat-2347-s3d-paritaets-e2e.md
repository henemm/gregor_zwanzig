---
spec_file: docs/specs/modules/feat_2347_s3d_paritaets_e2e.md
spec_sha256: 483fe975852b336c43b74736d060ee7e3920976bea04b0b290cb38beeaded09c
spec_frozen_sha256: 4d6b973a16aa457002b0b72e144954ec5e0f399a7c57c9c58437e069fa5b97a7
---

# PO-Briefing: feat-2347-s3d-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s3d_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-29

## Was gebaut wird

Trip und Ortsvergleich werden von denselben automatischen Prüfungen abgedeckt; der Rückstand schrumpft von 29 auf 14.

## Definition of Done

Alle sechs CI-Prüfungen sind grün, neue Prüfungen laufen dreimal stabil, der Rückstand steht bei 14.

## Wie geprüft wird

Neue Prüfungen testen Trip und Ortsvergleich und werden per gezielter Verfälschung gegengeprüft; die acht Staging-Prüfungen laufen weiterhin nicht automatisch.

## Kritische Anmerkungen

- Abweichung: Stundenverlauf-Prüfung wird nicht gelöscht, sondern gekennzeichnet; Metrik-Reihenfolge wird für beide geprüft statt gekennzeichnet.
- Trip-Verhalten beim Ziehen und Etappen-Ändern ist ungemessen; rote Fälle erzwingen Produktänderungen im selben Ticket, Umfang offen.
- Drei Altprüfungen und eine Staging-Prüfung werden gelöscht; Gleichwertigkeit zeigt erst der Lauf.

## Freigabe-Frage

Gibst du diese Aufteilung frei, inklusive möglicher Produktkorrekturen, falls die neuen Trip-Prüfungen rot werden?

## Ampel

Ampel: rot
