---
spec_file: docs/specs/modules/admin_ui_s4.md
spec_sha256: 56b43b878ceb089d2e75a60e1aed4e46f3f1591dfd8f5503e5388bf3a0fe949c
---

# PO-Briefing: feature-2155-s4-admin-ui

- **Spec:** docs/specs/modules/admin_ui_s4.md
- **Issue:** #2155 (Scheibe S4)
- **Erstellt:** 2026-09-30

## Was gebaut wird

Administratoren verwalten Nutzer auf einer eigenen Admin-Seite: Tier ändern, Konten sperren und entsperren; Nicht-Admins sehen sie nicht.

## Definition of Done

Ein Admin sieht auf Staging den Menüeintrag, ändert ein Tier, sperrt und entsperrt ein Testkonto; ein Nicht-Admin wird abgewiesen.

## Wie geprüft wird

Automatische Tests prüfen Zugriffsschutz und Hilfsfunktionen; Menü, Sperrdialog und Bedienung prüft nur ein Browsertest gegen Staging.

## Kritische Anmerkungen

- Produktion: Admin-Liste leer, niemand sieht die Seite, bis Sie die Einstellung setzen.
- Sperren-Dialog, Menüsichtbarkeit und Hervorhebung des Antrags sind nur im Browsertest abgedeckt, nicht in schnellen Tests.
- „Deutlich hervorgehoben“ ist nicht messbar; Aussehen bleibt Geschmackssache.

## Freigabe-Frage

Geben Sie die Admin-Seite frei, obwohl sie auf Produktion erst nach Ihrer Einstellung sichtbar wird?
