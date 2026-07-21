---
entity_id: issue_811_mail_quality_gate_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tests, tooling, gate, mail, quality, issue-811]
parent: issue_811_mail_quality_gate
phase: phase5_tdd_red
---

# Issue #811 — Mail-Qualitäts-Gate: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_811_mail_quality_gate.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_811_mail_quality_gate.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_811_mode_matrix.py` (NEU) — AC-1
- **File:** `tests/tdd/test_issue_811_renderer_gate.py` (NEU) — AC-2, AC-3

## Test Inventory — AC-1 (Modus-Matrix-Vertragstest)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_raw_full_html_no_ampel_in_data_cells` | AC-1 | Roh+full HTML: keine Ampel-Emoji in Daten-Zellen (reproduziert #810 RED) |
| `test_friendly_full_html_has_ampel` | AC-1 | Einfach+full HTML: ≥1 Ampel-Emoji vorhanden |
| `test_compact_ascii_no_emoji_no_hourly_table` | AC-1 | compact (beide Modi): ASCII, kein Emoji, keine Stundentabelle |

## Test Inventory — AC-2/AC-3 (Renderer-Gate)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_block_when_no_evidence` | AC-2 | Mail-Datei gestaged, kein Nachweis → Exit 2 |
| `test_pass_with_both_evidences` | AC-2 | beide Nachweise vorhanden → Exit 0 |
| `test_noop_when_no_mail_file` | AC-2 | Commit ohne Mail-Datei → Exit 0 (kein False-Positive) |
| `test_record_matrix_writes_hash` | AC-2 | `record-matrix` schreibt sha256 in Workflow-State |
| `test_block_when_validator_log_older_than_mail_file` | AC-2 | Validator-Log älter als Mail-Datei-mtime → Exit 2 (F001 Freshness) |
| `test_stale_evidence_reblocked_after_change` | AC-3 | Nachweis hinterlegt, Mail-Datei geändert → Exit 2 (Hash-Mismatch) |
| `test_no_env_global_bypass` | AC-3 | kein ENV/globaler Bypass erzeugt gültigen Nachweis |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — Tests sollen FAIL/ERROR sein)
uv run pytest tests/tdd/test_issue_811_mode_matrix.py \
             tests/tdd/test_issue_811_renderer_gate.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_811_mode_matrix.py \
             tests/tdd/test_issue_811_renderer_gate.py -v
```

## Changelog

- 2026-06-14: Initial test manifest erstellt für Issue #811 (RED-Phase).
