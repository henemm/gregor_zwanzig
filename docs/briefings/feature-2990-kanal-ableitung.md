---
spec_file: docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md
spec_sha256: 4e1ab3ca75e08c0871b6c97ac02aea492a91e5196aa4227e7b6d2aa81b47ed9b
spec_frozen_sha256: 301e0d5335f0cc7a104bcebbec73b9ba7069b99fd323cffabdc355d988d7002d
---

# PO-Briefing: feature-2990-kanal-ableitung

- **Spec:** docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md
- **Issue:** #2990
- **Erstellt:** 2026-11-26

## Was gebaut wird

Trip und Ortsvergleich zeigen bei gleichen Einstellungen dieselben aktiven Versandkanäle, abgeleitet aus einer gemeinsamen Regel.

## Definition of Done

Ein Ortsvergleich mit abgeschalteter Orts-Mail zeigt kein "Email" mehr, und Trip und Vergleich zeigen gleiche Kanäle in gleicher Reihenfolge.

## Wie geprüft wird

Automatische Tests prüfen Kanalliste, Reihenfolge und Sonderfälle für beide Kontexte; Versand selbst und Backend bleiben ungeprüft, weil unberührt.

## Kritische Anmerkungen

- Verhaltensänderung: Ortsvergleiche mit abgeschalteter E-Mail zeigen künftig kein "Email" mehr; folgt der früheren Entscheidung #2795.
- Hub-Übersicht und Zustellungs-Reiter bleiben bewusst außerhalb; Folge-Issue #3413. Dort kann die Doppelung vorerst bestehen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
