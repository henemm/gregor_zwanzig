---
spec_file: docs/specs/modules/feat_3037_abnahme_teil2.md
spec_sha256: d59e8161211fb2778b019a482452cfd71ad2c0d79f833078a49766ed4ec9e086
spec_frozen_sha256: fa9c2acb7ac80a2a7731643b571880ac854438d2a869e5cf1657b73447b929e8
---

# PO-Briefing: abnahme-3037-teil2

- **Spec:** docs/specs/modules/feat_3037_abnahme_teil2.md
- **Issue:** #3037
- **Erstellt:** 2026-11-26

## Was gebaut wird

Der Mail-Prüfweg weist nach, dass „Einstellung = Mail-Inhalt“ für Trip, drei Orte und einen Ort stimmt.

## Definition of Done

Prüf-Mails für Trip, drei Orte und einen Ort bestehen die Prüfung, Bilder und Soll/Ist-Vergleiche liegen Henning vor, danach wird #3037 geschlossen.

## Wie geprüft wird

Werkzeug-Tests ohne Netz prüfen Aufruf, Aufräumen und Fehlerfall; echte Staging-Mails und Bilder werden live gemessen, nicht in der Automatik.

## Kritische Anmerkungen

- Die Ampelfarbe der Form „Einfach“ ist im Staging-Mailnachweis nicht prüfbar; Nachweis nutzt „Roh“, „Einfach“ nur im Kern-Test.
- Die Zusage, den Test-Trip mit Form „Roh“ anzulegen, hat keinen eigenen Automatik-Test, nur den Live-Lauf.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
