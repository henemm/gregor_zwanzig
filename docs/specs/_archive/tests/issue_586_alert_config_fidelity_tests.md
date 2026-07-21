---
entity_id: issue_586_alert_config_fidelity_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [tests, frontend, design-fidelity, alert-config, issue-586]
parent: issue_586_alert_config_fidelity_gate
phase: phase5_tdd_red
---

# #586 — Alert-Config Design-Fidelity: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_586_alert_config_fidelity_gate.md`.
Behaviorale Pixel-Diff-Prüfung der Live-Alert-Config gegen die bindende JSX
`screen-alert-config.jsx` (keine Mocks, keine String-Checks).

Parent-Spec: `docs/specs/modules/issue_586_alert_config_fidelity_gate.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_586_alert_config_fidelity.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_live_and_reference_screenshots_exist` | AC-1/AC-2 | Live-Screenshot (Alarme-Tab @1440px) und JSX-gerenderte Referenz liegen vor und sind nicht leer |
| `test_live_matches_binding_jsx_under_threshold` | AC-3 | Eigenständig berechneter Pixel-Diff Live vs. JSX-Referenz `< 10 %` |
| `test_gate_artifact_passed` | AC-3/AC-5 | Close-Gate-Artefakt `design-diff-K-alert-config-list.json` existiert mit `passed: true` und `diff_pct < 10` |

Entity-Stems (Hook-Mapping): `live_and_reference_screenshots_exist`,
`live_matches_binding_jsx_under_threshold`, `gate_artifact_passed`.

## Test-Ausführung

```bash
uv run pytest tests/tdd/test_issue_586_alert_config_fidelity.py -v
```

RED: Live- und Referenz-PNG existieren noch nicht → Tests schlagen fehl.
GREEN: Nach der Messung (Phase 6) liegen die Bilder vor und der Diff < 10 %.
