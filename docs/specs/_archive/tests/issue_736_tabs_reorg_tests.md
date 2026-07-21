---
entity_id: issue_736_tabs_reorg_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, frontend, ui-cleanup, tab-reorg, issue-736]
parent: issue_736_tabs_reorg
phase: phase5_tdd_red
---

# Issue #736 — Reiter-Reorganisation "Inhalt" vs. "Versand" (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Implementierung aus
`docs/specs/modules/issue_736_tabs_reorg.md`. Alle Tests sind Playwright-E2E
gegen Staging als eingeloggter Nutzer.

Parent-Spec: `docs/specs/modules/issue_736_tabs_reorg.md` v1.0

## Source

- **File:** `frontend/e2e/issue-736-tabs-reorg.spec.ts` (NEU — RED-Tests für AC-1 bis AC-6)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `AC-1: Tab-Labels "Inhalt" und "Versand"` | AC-1 | `trip-detail-tab-weather` hat Text "Inhalt", `trip-detail-tab-briefings` hat Text "Versand"; `?tab=weather` und `?tab=briefings` aktivieren richtigen Reiter |
| `AC-2: Inhalt-Reiter hat E-Mail-Inhalt, kein Kanal-Toggle` | AC-2 | `channel-email` nicht im DOM bei `?tab=weather`; `report-mail-content` sichtbar |
| `AC-3: Versand-Reiter hat Kanäle genau einmal, kein E-Mail-Inhalt` | AC-3 | `channel-email` count == 1 bei `?tab=briefings`; `report-mail-content` count == 0 |
| `AC-4: Kanal-Toggle setzt display_config + report_config synchron` | AC-4 | E-Mail aktivieren + speichern → beide GET-Endpunkte liefern `true` |
| `AC-5: "Schwellwerte" Überschrift, kein "SMS-Schwellwerte"` | AC-5 | Kein Text "SMS-Schwellwerte" im DOM; "Schwellwerte" und Hinweis "Gelten für E-Mail, Telegram und SMS" sichtbar |
| `AC-6: Bestehender gespeicherter Kanal-Zustand beim Öffnen des Versand-Reiters korrekt` | AC-6 | Trip mit email=false,telegram=true → Versand-Reiter zeigt E-Mail unchecked, Telegram checked |
