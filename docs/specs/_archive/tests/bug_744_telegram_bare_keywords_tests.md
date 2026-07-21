---
entity_id: bug_744_telegram_bare_keywords_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, telegram, bare-keywords, channel-consistency, issue-744]
parent: bug_744_telegram_bare_keywords
phase: phase5_tdd_red
---

# Bug #744 — Telegram bare Keywords (Tests v1.0)

## Approval

- [x] Approved (2026-06-11, PO)

## Purpose

Test-Manifest für Bug #744. Beweist aus Nutzerperspektive: echter HTTP-POST gegen die
reale FastAPI-App (`/api/internal/telegram-webhook`) mit bare Text-Message-Body;
ausgehende Bot-API-Calls an einem echten lokalen `http.server`-Socket beobachtet
(Boundary-Capture via `TELEGRAM_API_BASE`); echter `TripCommandProcessor`, echter Trip +
Snapshot, echte User-Auflösung, echter Persistenz-Roundtrip (`enabled`-Toggle).
**Keine Mocks der Logik unter Test.**

Parent-Spec: `docs/specs/modules/bug_744_telegram_bare_keywords.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_744_telegram_bare_keywords.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/bug_744_telegram_bare_keywords.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_bare_weiter_reactivates` | AC-1 | bare `weiter` → enabled=True persistiert, Bestätigung „reaktiviert", NICHT „Unbekannter Befehl". |
| `ac2_bare_stop_cancels` | AC-2 | bare `stop` → enabled=False persistiert, Bestätigung „beendet/deaktiviert", NICHT „Unbekannter Befehl". |
| `ac3_shared_bare_keywords_recognized` | AC-3 | bare `help`/`jetzt`/`gewitter` (parametrisiert) → kanalgleich erkannt, NICHT „Unbekannter Befehl". |
| `ac4_unknown_command_lists_current_set` | AC-4 | bare `quatsch` → „Unbekannter Befehl" + Fehlermeldung nennt aktuellen Satz (weiter/stop/jetzt). |
| `ac5_slash_shortcut_still_works` | AC-5 | Regression: `/h` bleibt gültig. |
| `ac5_known_bare_command_still_works` | AC-5 | Regression: bare `status` (schon vor Fix gültig) bleibt gültig. |

## Changelog

- **2026-06-11 v1.0:** Initiales Test-Manifest (Bug #744).
