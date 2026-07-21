# Spec: Issue #726 — Portable Renderer-Pfade im Compliance-Test

- **Status:** Draft
- **Created:** 2026-06-11
- **Issue:** #726
- **Typ:** Bug (Test-Portabilität, kein Produktionscode)

## Kontext

`tests/tdd/test_issue_623_trend_channels.py::TestTokenConsolidation::test_format_trend_tokens_is_sole_threshold_evaluator` (markiert als `# doc-compliance-test`) prüft strukturell, dass die drei Channel-Renderer keine rohen Schwellenwert-Vergleiche enthalten. Dazu öffnet er die Renderer-Quelldateien — aktuell über **hartkodierte absolute Pfade** auf einen fremden Worktree (`/home/hem/gregor_zwanzig/.claude/worktrees/idempotent-strolling-cray/...`). Dieser Worktree existiert in anderen Umgebungen nicht → `FileNotFoundError`.

## Ziel

Die Renderer-Pfade werden **relativ zum Repo-Root** aufgelöst, sodass der Test in jedem Worktree und im Hauptrepo läuft — ohne die Prüflogik zu verändern.

## Acceptance Criteria

**AC-1:** Given der Test wird in einem beliebigen Worktree/Hauptrepo ausgeführt (in dem die Renderer-Dateien unter `src/output/renderers/` existieren), When `test_format_trend_tokens_is_sole_threshold_evaluator` läuft, Then öffnet er die drei Renderer-Dateien des **aktuellen** Repos (kein `FileNotFoundError`) und besteht.

**AC-2:** Given der Test-Quelltext, When man ihn inspiziert, Then enthält er **keinen** absoluten Pfad mehr, der auf `.claude/worktrees/` oder einen festen Worktree-Namen verweist; die Pfade werden über `Path(__file__).resolve().parents[N]` relativ zum Repo-Root gebildet.

**AC-3:** Given ein hypothetischer Renderer mit einem rohen Schwellenwert-Vergleich (z.B. `wk > 30`), When der Test gegen eine solche Datei läuft, Then schlägt er weiterhin fehl (die Bad-Pattern-Liste und die Verstoß-Erkennung bleiben unverändert wirksam — der Fix ändert nur die Pfadauflösung, nicht die Prüflogik).

## Out of Scope

- `test_issue_613_email_redesign.py::TestAC6SectionsPreserved` (vorbestehend rot, Footer-Änderung durch #670) → gehört zu #723.
- Jegliche Änderung an Produktions-Renderern.

## Test-Manifest

RED-Artefakt: `tests/tdd/test_issue_726_path_portability.py`

| Test | AC |
|------|-----|
| `test_renderer_paths_resolve_in_current_repo` | AC-1 |
| `test_no_hardcoded_worktree_path_in_source` | AC-2 |
| `test_scanner_still_flags_threshold_violation` | AC-3 |
| `test_scanner_clean_file_has_no_violations` | AC-3 (Gegenprobe) |
| `test_bad_pattern_list_unchanged` | AC-3 |

## Changelog

- 2026-06-11: Initiale Spec (Issue #726).
