---
entity_id: issue_685_selftest_menu_gate_tests
type: tests
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [tests, prod-selftest, telegram, bot-menu, deploy-gate, issue-685]
parent: issue_685_selftest_menu_gate
phase: phase5_tdd_red
---

# Issue #685 — Bot-Menü-Wächter umgebungsunabhängig (Tests v1.0)

## Approval

- [x] Approved (2026-06-09, PO — „go")

## Purpose

Test-Manifest für #685. Beweist mock-frei: (1) `_load_bot_commands()` lädt
`BOT_COMMANDS` auch ohne importierbares `pydantic` (echte Deploy-Bedingung im
Subprozess reproduziert), (2) der Menü-Check meldet dann PASS statt SKIPPED,
(3) bei Abweichung FAIL + korrekter Fazit-Text (F001), (4) fail-soft SKIPPED bei
nicht-parsebarer Quelle.

Parent-Spec: `docs/specs/modules/issue_685_selftest_menu_gate.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_685_selftest_menu_gate.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/issue_685_selftest_menu_gate.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_load_bot_commands_without_pydantic` | AC-1 | `_load_bot_commands()` in Subprozess mit blockiertem `pydantic` (reproduziert System-Python-Deploy) liefert die 7 echten Befehle, nicht None, kein ModuleNotFoundError. |
| `ac2_menu_check_pass_when_live_matches` | AC-2 | Live-Menü (echter Socket) == BOT_COMMANDS → `check_bot_menu` status PASS, nicht SKIPPED. |
| `ac3_menu_fail_report_text_is_fail` | AC-3 | Abweichendes Live-Menü → check_bot_menu FAIL; `_render_full_report(verdict="FAIL", ...)` Fazit-Text nennt FAIL, nicht „PARTIAL". |
| `ac4_load_bot_commands_unparseable_returns_none` | AC-4 | Quelle ohne literal-auswertbares BOT_COMMANDS → `_load_bot_commands()` gibt None (fail-soft), Menü-Check SKIPPED. |

## Expected RED-State (vor GREEN-Phase)

- **AC-1** rot: aktuelles `_load_bot_commands()` importiert `outputs.telegram` →
  bei blockiertem `pydantic` `ModuleNotFoundError` → verschluckt → `None` (Subprozess
  druckt `null`).
- **AC-3** rot: `_render_full_report` Fazit-Text ist im `else`-Zweig hart „PARTIAL",
  auch bei verdict==FAIL.
- **AC-2/AC-4** prüfen das Zielverhalten des gefixten Loaders/Checks.

## Changelog

- 2026-06-09: Initial test manifest (Issue #685).
