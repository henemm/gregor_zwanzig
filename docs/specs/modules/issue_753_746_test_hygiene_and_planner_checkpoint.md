---
entity_id: issue_753_746_test_hygiene_and_planner_checkpoint
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tooling, tests, agents, hygiene]
---

# Issue #753 + #746 — Test-Hygiene & user-story-planner Checkpoint

## Approval

- [x] Approved (PO, 2026-06-11)

## Purpose

Zwei unabhängige Tooling-/Test-Hygiene-Bugs: (#753) Entfernen eines verbotenen Datei-Inhalt-Prüf-Tests, der `.svelte`-Quelltext statt Verhalten prüft und bereits falsch-rot ist; (#746) Einbau eines harten PO-Bestätigungs-Checkpoints in den `user-story-planner`-Agent, damit keine GitHub-Issues ohne PO-Freigabe entstehen.

## Source

- **File:** `tests/tdd/test_issue_299_edit_report_config_polish.py` (#753 — zu löschen)
- **File:** `docs/specs/modules/issue_299_edit_report_config_section_polish.md` (#753 — obsolete Spec, zu löschen)
- **File:** `.claude/agents/user-story-planner.md` (#746 — Checkpoint einbauen)
- **Identifier:** Markdown-Agent-Definition, keine Code-Symbole

## Estimated Scope

- **LoC:** ~25 (Agent-Markdown; Test-Löschung zählt nicht gegen Source-Limit)
- **Files:** 3 (1 gelöscht + 1 obsolete Spec gelöscht + 1 Markdown editiert)
- **Effort:** low

## Dependencies

- Keine Code-Dependencies. `frontend/e2e/issue-88-report-config-dialog.spec.ts` nutzt die Reports-Tab-Testids unabhängig — die Löschung des Python-Tests verliert keine Verhaltens-Abdeckung.

## Acceptance Criteria

- **AC-1:** Given das Repo nach dem Fix / When in `tests/` nach `read_text()`-Aufrufen auf `EditReportConfigSection.svelte` gesucht wird / Then existiert `tests/tdd/test_issue_299_edit_report_config_polish.py` nicht mehr und kein anderer Test prüft den Quelltext dieser Komponente per Datei-Inhalt-Assert.

- **AC-2:** Given die Pytest-Suite / When `uv run pytest tests/tdd/ -q` läuft / Then bricht kein Test mit „channel-signal fehlt" o.ä. Datei-Inhalt-Assert aus #299 ab (der falsch-rote Regressions-Test ist weg), und die Suite ist nicht durch die Löschung neu rot.

- **AC-3:** Given die obsolete Spec zu #299 / When das Repo durchsucht wird / Then ist `docs/specs/modules/issue_299_edit_report_config_section_polish.md` entfernt, sodass keine verwaiste Spec auf einen gelöschten Test verweist.

- **AC-4:** Given die Datei `.claude/agents/user-story-planner.md` / When der Abschnitt zwischen „Phase 4: Dependency Mapping" und „Phase 5: Documentation" gelesen wird / Then enthält sie einen klar als PFLICHT markierten Checkpoint, der vor Phase 5 Story (Als/möchte/damit) + Acceptance Criteria + Feature-Liste dem PO präsentiert und auf explizite Bestätigung („go"/„ja"/„ok") wartet.

- **AC-5:** Given derselbe Checkpoint / When der PO nicht bestätigt / Then schreibt die Agent-Definition explizit STOP vor: keine GitHub-Issues anlegen (`gh issue create`) und kein Story-Dokument erstellen, bis die Bestätigung vorliegt.

## Expected Behavior

- **Input:** Bestehendes Repo mit verbotenem Datei-Inhalt-Test und einem `user-story-planner`-Agent ohne PO-Gate.
- **Output:** Test + obsolete Spec gelöscht; Agent-Markdown mit hartem Checkpoint-Block.
- **Side effects:** Keine Laufzeit-/Produktiv-Auswirkung (test/docs/tooling-only). Der Checkpoint wirkt erst beim nächsten `user-story-planner`-Lauf.

## Known Limitations

- Die weiteren ~22 `tests/tdd/`-Dateien mit demselben Datei-Inhalt-Anti-Pattern werden hier **nicht** mitbehandelt (250-LoC-Limit, Einzelurteil pro Datei nötig) — dafür wird ein Follow-up-Issue (systematischer Sweep + Regressions-Guard) angelegt.
- Der Checkpoint ist eine Prompt-Konvention, kein Hook-erzwungenes Gate — er verlässt sich auf Agent-Befolgung (analog zu den bestehenden STOP-Conditions desselben Agents).

## Test Coverage

Tests in `tests/tdd/test_issue_753_746_hygiene.py` (alle `# doc-compliance-test`, da Workflow-Artefakte geprüft werden):

- `test_forbidden_filecontent_test_removed` — prüft, dass `test_issue_299_edit_report_config_polish.py` nicht mehr existiert (AC-1).
- `test_no_test_reads_editreportconfig_source` — durchsucht `tests/tdd/` und stellt sicher, dass kein Test `EditReportConfigSection.svelte` per `read_text()` liest (AC-1).
- `test_obsolete_spec_removed` — prüft, dass die #299-Spec entfernt ist (AC-3).
- `test_planner_has_po_checkpoint_before_phase5` — prüft, dass `user-story-planner.md` einen PFLICHT-Checkpoint mit Bestätigungs-Erwartung zwischen Phase 4 und Phase 5 enthält (AC-4).
- `test_planner_checkpoint_mandates_stop` — prüft, dass der Checkpoint STOP (keine Issues / kein Dokument ohne Bestätigung) vorschreibt (AC-5).

Hinweis: AC-2 wird durch einen echten `uv run pytest`-Lauf der Gesamtsuite verifiziert (nicht durch einen Datei-Inhalt-Check), siehe Validierungsphase.

## Changelog

- 2026-06-11: Initial spec erstellt — Issues #753, #746
