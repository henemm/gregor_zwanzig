---
spec_file: docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md
spec_sha256: feea2f77cd93ec5f2a1ce999cf51aa8ac79acc7c0b5e9d002b0297023ffe0975
spec_frozen_sha256: 418fe4e06f7e0459dc332e230a1199cfa96aa57fdcd8d45c0703c510016620bc
---

# PO-Briefing: feature-2990-kanal-ableitung

- **Spec:** docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md
- **Issue:** #2990
- **Erstellt:** 2026-11-26

## Was gebaut wird

Trip und Ortsvergleich zeigen ihre aktiven Versandkanäle künftig aus einer gemeinsamen Regel, in gleicher Reihenfolge.

## Definition of Done

Bei gleichen Kanal-Einstellungen zeigen Trip und Ortsvergleich überall dieselben Kanäle, und abgeschaltete Orts-Mail erscheint nicht mehr als „Email".

## Wie geprüft wird

Automatische Tests prüfen Kanalliste, Reihenfolge und Abschalt-Fälle; Versand selbst bleibt unberührt und ungeprüft, nur die Anzeige ändert sich.

## Kritische Anmerkungen

- Zusatz zum Ticket: Anzeige-Fehler beim Ortsvergleich (abgeschaltete Orts-Mail zeigte „Email") wird mitbehoben, gestützt auf frühere Entscheidung #2795.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
