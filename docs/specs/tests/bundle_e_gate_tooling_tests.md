---
entity_id: bundle_e_gate_tooling_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tests, tooling, gate, prod_selftest, briefing_mail_validator, issue-788, issue-786, issue-780]
parent: bundle_e_gate_tooling
phase: phase5_tdd_red
---

# Bundle E — Gate-Tooling-Verlässlichkeit (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/bundle_e_gate_tooling.md`. Jeder pytest-Test
mappt 1:1 auf ein Acceptance Criterion der Parent-Spec. Mock-frei: echte Git-Repos
(`tmp_path`), echte `email.message.Message`-Objekte, echte Funktionsaufrufe gegen
die isoliert geladenen Hook-Module. Kein Netzwerk.

Parent-Spec: `docs/specs/modules/bundle_e_gate_tooling.md` v1.0

## Source

- **File:** `tests/tdd/test_bundle_e_gate_tooling.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_bundle_e_gate_tooling.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_sentinel_url_skipped_no_http` | AC-1 | Sentinel-URL (`n/a`, `na`, `-`, `none`, `—`, `interaktiv`, leer, case-insensitive/getrimmt) → `_probe_ac` liefert `SKIPPED_NO_URL`, kein HTTP-GET. |
| `test_ac1_null_url_skipped_no_crash` | AC-1 (F001) | `url=None` (JSON null) → kein AttributeError, `prod_status == SKIPPED_NO_URL`. |
| `test_ac2_all_sentinel_pass_findings_not_partial` | AC-2 | Alle PASS-Findings mit Sentinel-URL → `_derive_verdict` ≠ PARTIAL (PASS/SKIPPED_ALL). |
| `test_ac3_docs_only_scope_skips_despite_stale_attestation` | AC-3 | `run_selftest(scope="docs-only")` → Return 0 trotz stale Attestation (keine Commit-Mismatch-Prüfung). |
| `test_ac4_backend_scope_does_not_early_skip` | AC-4 | `run_selftest(scope="backend")` skippt nicht vorzeitig; regulärer Pfad wird erreicht. |
| `test_ac5_detect_scope_docs_only` | AC-5 | `_detect_committed_scope(repo)` gegen echtes Git-Repo, letzter Commit nur `.claude/` → `docs-only`. |
| `test_ac5_detect_scope_backend` | AC-5 | `_detect_committed_scope(repo)`, letzter Commit unter `src/` → `backend`. |
| `test_ac6_matches_own_marker_mail` | AC-6 | `_message_matches` matcht nur eigene markierte Mail (X-GZ-Mail-Type + Subject-Token); fremde nicht. |
| `test_ac7_rfc2047_subject_decoded_before_substring` | AC-7 | RFC-2047-Subject (Em-Dash/Umlaut) wird via `_decode_subject` dekodiert vor Substring-Vergleich. |
| `test_ac8_no_filters_returns_true` | AC-8 | `_message_matches` ohne Filter (beide None) → True (rückwärtskompatibel). |

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt / When
  `pytest tests/tdd/test_bundle_e_gate_tooling.py -q` läuft / Then schlagen die
  Tests fehl (RED-Phase erfolgreich).
- **AC-T2:** Given GREEN-Phase abgeschlossen / When der Lauf wiederholt wird /
  Then alle Tests grün, keine Mocks.

## Changelog

- 2026-06-14: Initial — Test-Manifest für Bundle E (#788/#786/#780).
