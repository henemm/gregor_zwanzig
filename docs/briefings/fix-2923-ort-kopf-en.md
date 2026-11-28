---
spec_file: docs/specs/modules/bug_2923_ort_kopf_en.md
spec_sha256: 756999b823f105a77c4c9df6f31bf35be656654eedb2d52559bb05ebe1f65de1
spec_frozen_sha256: 7be87c7d031b477232cd0493bc5d6f0c0e1208488d0918dc40a45e7fdb140311
---

# PO-Briefing: fix-2923-ort-kopf-en

- **Spec:** docs/specs/modules/bug_2923_ort_kopf_en.md
- **Issue:** #2923
- **Erstellt:** 2026-11-28

## Was gebaut wird

Englische Vergleichs-Mails zeigen im Stundenblock vor jedem Ortsnamen „LOCATION“ statt des deutschen „ORT“.

## Definition of Done

Die zugestellte englische Staging-Mail zeigt je Ort „LOCATION“, die deutsche Mail bleibt unverändert „ORT“, alle Prüfungen und Deploy-Checks sind grün.

## Wie geprüft wird

Der erweiterte Katalogfall und Referenzmails belegen Englisch und Deutsch; der Mail-Prüfer prüft echte Staging-Mails. Andere Kanäle sind nicht betroffen.

## Kritische Anmerkungen

- Ratschen-Lücke nur an dieser Stelle geschlossen; Ratsche bewusst nicht erweitert (etwa 250 Fehlalarme für einen Fund).
- Fußzeile und Risiko-Legende aus Issue #3074 bleiben ausdrücklich ungelöst.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
