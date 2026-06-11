---
entity_id: test_hygiene_754_755_756_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, hygiene, compliance, telegram, issue-754, issue-755, issue-756]
---

# Tests: Test-Hygiene-Sweep #754 + #755 + #756

## Approval

- [x] Approved

## Purpose

Manifest für die Test-Artefakte des Hygiene-Sweeps. Deckt das Compliance-Gate
(#754/#755) sowie die korrigierten Telegram-E2E-Tests (#756) ab.

## Source

- **File:** `tests/tdd/test_754_755_test_hygiene_compliance.py`
- **Identifier:** Funktionen mit Prefix `test_*`, namentlich:
  - `test_754_no_source_content_read` — jede der 19 #754-Dateien ist gelöscht
    oder enthält keinen `read_text()`-Quelltext-Assert mehr.
  - `test_755_no_channel_signal_in_e2e_and_tests` — kein `channel-signal`-Locator
    mehr in `frontend/e2e/` oder `tests/` (#610/#755).
- **File:** `tests/tdd/test_e2e_telegram_pipeline.py` (#756 — korrigierte Asserts
  auf Loading-`send` + `editMessageText`).
- **File:** `tests/tdd/test_inbound_telegram_reader.py` (#756 — `test_hilfe_command_in_processor`
  gegen #731-Befehlssatz).

## Bezug

- Spec: `docs/specs/modules/test_hygiene_754_755_756.md`
- GitHub Issues #754, #755, #756 (Nebenbefunde #753/#744)

## Test-Strategie

- **Compliance-Gate** (`# doc-compliance-test`): prüft Test-Artefakte selbst gegen
  das CLAUDE.md-Verbot von Datei-Inhalt-Asserts. Dokumentierte Ausnahme.
- **Telegram-E2E** (#756): mock-frei via lokalem HTTP-Boundary-Capture-Server, der
  — wie echtes Telegram — eine `message_id` liefert, sodass der reale Loading+Edit-Pfad
  ausgeübt wird.
- Kein Produkt-Code betroffen; Scope test-/tooling-only, kein Prod-Deploy.
