---
entity_id: fix_1061_gate_tests_stale
type: bugfix
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [gate-tests, plugin-shim, worktree-isolation, doc-drift, issue-1061]
---

# Fix #1061 — Stale Gate-Tests & Doku-Drift

## Approval

- [ ] Approved

## Purpose

Vier vorbestehende, dauerhaft rote bzw. driftende Gate-Test-/Doku-Befunde aus der #1052-Integration beheben, damit "rot" in der Testsuite wieder einen echten Fehler bedeutet und nicht Infrastruktur-Rauschen (fehlende lokale Plugin-Dateien, Worktree-Env-Leck, überholtes Ausblick-Testdesign, veraltete Befehlsliste in der Architektur-Doku).

## Source

- **File:** `tests/tdd/test_issue_885_adr_guard.py`
- **Identifier:** `_setup_repo()`
- **File:** `tests/tdd/test_issue_894_registry_cleanup.py`
- **Identifier:** `test_get_active_workflow_name_returns_env_value`, `test_get_active_workflow_name_returns_empty_without_env`, `test_renderer_mail_gate_uses_hook_utils_resolver`
- **File:** `tests/tdd/test_issue_898_901_mail_layout.py`
- **Identifier:** `class TestAC7TrendAsChips`
- **File:** `docs/features/architecture.md`
- **Identifier:** Zeile 147 (BOT_COMMANDS-Aufzählung)

## Estimated Scope

- **LoC:** ~+50/-30 (reiner Testcode, zählt laut CLAUDE.md-Konvention nicht gegen das 250-LoC-Workflow-Limit; die Doku-Zeile zählt ohnehin nicht)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `~/.claude/plugins/installed_plugins.json` | Registry-Datei | Enthält die Plugin-Version-Keys (`agent-os-openspec@*`), über die der Plugin-Cache-Pfad aufgelöst wird |
| Plugin-Cache-Verzeichnis (`agent-os-openspec@.../core/hooks/`) | Filesystem | Enthält die tatsächlichen `bash_gate.py`, `workflow.py`, `workflow_state_multi.py`, `override_token.py` seit der Migration ins Plugin (Issue #33) |
| `.claude/hooks/hook_utils.py::_resolve_plugin_module()` | Vorbild-Pattern | Etablierte Shim-Logik: sucht zuerst lokal, dann über die Registry im Plugin-Cache — wird für AC-1 wiederverwendet/adaptiert |
| `src/output/renderers/email/html.py` (`outlook_rows`/`outlook_table`, Zeile ~1163–1270) | Produktionscode (nur gelesen, nicht geändert) | Referenz-Markup, gegen das AC-4 die neuen Tabellen-Assertions schreibt |
| `src/output/channels/telegram.py::BOT_COMMANDS` (Zeile 89–98) | Produktionscode (nur gelesen, nicht geändert) | Quelle der Wahrheit für die 8 tatsächlichen Bot-Befehle in AC-3 |

## Implementation Details

**AC-1 (bash_gate-Plugin-Auflösung):** In `test_issue_885_adr_guard.py` eine Hilfsfunktion `_resolve_plugin_hook(name: str) -> Path | None` ergänzen, die zuerst lokal in `_HOOKS_DIR` sucht und — falls die Datei dort fehlt — `~/.claude/plugins/installed_plugins.json` nach einem Key `agent-os-openspec@*` durchsucht und den Pfad im zugehörigen Plugin-Cache-Verzeichnis zurückgibt (gleiche Kernlogik wie `hook_utils.py::_resolve_plugin_module()`, adaptiert auf Dateipfade statt Python-Modulobjekte). `_setup_repo()` nutzt diese Funktion für `bash_gate.py`, `workflow.py`, `workflow_state_multi.py`, `override_token.py` statt der bisherigen direkten `_HOOKS_DIR`-Pfade. Liefert die Auflösung `None` (Plugin nicht installiert und Datei auch lokal nicht vorhanden), ruft der betroffene Test `pytest.skip("agent-os-openspec Plugin nicht installiert")` statt mit `FileNotFoundError`/`shutil.copy`-Crash abzubrechen.

**AC-2 (Worktree-Env-Isolation):** In `test_issue_894_registry_cleanup.py` bekommen die 3 betroffenen Tests je einen `monkeypatch.chdir(tmp_path)` in ein frisches, leeres Temp-Verzeichnis (kein `.claude/active_workflow`, kein `settings.local.json`) VOR dem Aufruf von `resolve_active_workflow()`, damit `_find_worktree_root()`/`find_project_root()` dort nichts Echtes findet und ausschließlich die gepatchte Env-Var (`OPENSPEC_ACTIVE_WORKFLOW`) greift. Keine Änderung an `hook_utils.py::resolve_active_workflow()` selbst — reine Testisolation.

**AC-3 (Doku-Fix):** `docs/features/architecture.md` Zeile 147 von "7 Befehle: glance, hg, dd, now, status, config, help" auf die tatsächlichen 8 Befehle aus `BOT_COMMANDS` korrigieren: glance, heute, morgen, now, heute_gewitter, timeline_heute, timeline_morgen, hilfe.

**AC-4 (Trend-Tests auf Tabellenformat):** In `test_issue_898_901_mail_layout.py` die Klasse `TestAC7TrendAsChips` zu `TestAC7TrendAsTable` umbenennen. Die beiden Tests `test_no_trend_table_rows` und `test_trend_has_pill_spans` werden durch Assertions gegen das aktuelle `<table>`-Markup ersetzt: Anzahl `<tr>`-Zeilen im Ausblick-Block entspricht der Anzahl Trend-Tage, und der Zellhintergrund jeder Zeile entspricht dem zugehörigen Warnlevel (`_outlook_cell_bg`/`_THUNDER_LEVEL_BG`). Kein Löschen ohne Ersatz — die AC-7-Abdeckung ("Ausblick-Trend hat definiertes, verifiziertes Markup") bleibt erhalten, nur gegen das PO-freigegebene Tabellenformat aus Issue #911 statt des überholten Chip-Formats aus #899.

## Expected Behavior

- **Input:** Bestehende Testsuite (`tests/tdd/test_issue_885_adr_guard.py`, `test_issue_894_registry_cleanup.py`, `test_issue_898_901_mail_layout.py`) plus `docs/features/architecture.md`.
- **Output:** Alle 3 Testdateien laufen vollständig grün (bzw. sauber übersprungen, falls Plugin nicht installiert); die Doku-Zeile spiegelt die tatsächliche Telegram-Befehlsliste wider.
- **Side effects:** Keine — reine Test-/Doku-Änderungen, keine Produktionscode-Pfade betroffen.

## Acceptance Criteria

- **AC-1:** Given ein Repo, in dem `bash_gate.py`/`workflow.py`/`workflow_state_multi.py`/`override_token.py` lokal in `.claude/hooks/` nicht mehr existieren (weil vollständig ins `agent-os-openspec`-Plugin migriert), When `test_issue_885_adr_guard.py::_setup_repo()` läuft, Then löst die Testfixture die vier fehlenden Dateien dynamisch über `~/.claude/plugins/installed_plugins.json` im Plugin-Cache auf (oder skippt sauber mit Begründung, falls das Plugin nicht installiert ist), statt mit `FileNotFoundError` zu crashen.
  - Test: `uv run pytest tests/tdd/test_issue_885_adr_guard.py` läuft komplett grün (alle ~14 vorher roten Tests), inklusive echtem `bash_gate.py`-Subprocess-Aufruf gegen ein echtes Temp-Git-Repo — kein Mock auf die Gate-Logik selbst.

- **AC-2:** Given die drei Env-Var-Tests in `test_issue_894_registry_cleanup.py` laufen innerhalb einer aktiven Worktree-Session mit echtem `.claude/active_workflow`-Pointer, When die Tests `OPENSPEC_ACTIVE_WORKFLOW` patchen und `resolve_active_workflow()` aufrufen, Then liest die Funktion den gepatchten Testwert statt des echten Session-Workflows, weil die Tests zusätzlich in ein pointer-freies Temp-Verzeichnis wechseln.
  - Test: `uv run pytest tests/tdd/test_issue_894_registry_cleanup.py -k "returns_env_value or returns_empty_without_env or renderer_mail_gate_uses_hook_utils_resolver"` läuft grün — echter Aufruf von `hook_utils.resolve_active_workflow()` in einem isolierten `tmp_path`-Verzeichnis, kein `monkeypatch.setattr` auf die Resolver-Funktion selbst.

- **AC-3:** Given `docs/features/architecture.md` Zeile 147 nennt veraltet "7 Befehle: glance, hg, dd, now, status, config, help", When die Doku-Zeile mit den tatsächlichen Einträgen aus `BOT_COMMANDS` abgeglichen wird, Then steht dort korrekt "8 Befehle: glance, heute, morgen, now, heute_gewitter, timeline_heute, timeline_morgen, hilfe".
  - Test: Doku-Compliance-Test (# doc-compliance-test) oder manueller Diff-Check bestätigt, dass die Zeile die exakte, alphabetisch/reihenfolgengetreue Liste aus `src/output/channels/telegram.py::BOT_COMMANDS` (Zeile 89–98) enthält.

- **AC-4:** Given `TestAC7TrendAsChips` testet ein per PO-Entscheidung in Issue #911 verworfenes Chip/Pill-Format für den Ausblick-Trend, When die Klasse zu `TestAC7TrendAsTable` umgeschrieben und gegen das aktuelle `<table>`-Markup in `src/output/renderers/email/html.py` geprüft wird, Then bestätigen die Tests, dass die Anzahl `<tr>`-Zeilen der Anzahl Trend-Tage entspricht und jede Zeile einen warnlevel-abhängigen Zellhintergrund trägt.
  - Test: `uv run pytest tests/tdd/test_issue_898_901_mail_layout.py -k TestAC7TrendAsTable` läuft grün gegen echt gerendertes HTML (kein Datei-String-Check, sondern Struktur-Assertions auf dem geparsten `<table>`-Markup, das mit einer echten Trip-Konfiguration erzeugt wurde).

## Known Limitations

- `tests/tdd/` läuft laut Issue #1061 nicht im CI-äquivalenten Lauf (`--ignore=tests/tdd/`) — dieser Fix stellt lokale Testtreue wieder her, ändert aber nichts an der CI-Pipeline selbst.
- Punkt 2 aus Issue #1061 (Golden-Nachweis, `test_issue_811_renderer_gate.py`) ist bereits durch Commit `98773f73` gelöst und daher NICHT Teil dieser Spec — wird nur als "bereits erledigt" im Issue dokumentiert.
- AC-1 hängt vom Vorhandensein des `agent-os-openspec`-Plugins ab; ist es nicht installiert, werden die betroffenen Tests übersprungen statt zu laufen — das ist beabsichtigtes Fail-Soft-Verhalten, kein vollständiger Ersatz für eine echte Ausführung.
- **Scope-Anpassung während Implementierung (2026-07-09, PO-bestätigt):** Bei der Umsetzung von AC-1 stellte sich heraus, dass die ADR-Enforcement-Logik selbst (Commit-Blockierung bei fehlender ADR-Dokumentation aus #885) seit der Plugin-Migration (#33) nirgendwo mehr wired ist — weder `bash_gate.py` noch `workflow.py::_validate_transition` im Plugin rufen `adr_guard` auf. Das ist eine echte Produktivregression außerhalb des Scopes dieser Spec (reine Test-/Doku-Fixes, kein Produktionscode). Dafür wurde Issue #1164 angelegt.
- **Adversary-Runde 1 (BROKEN → gefixt):** Ursprünglich wurden alle 12 potenziell betroffenen Tests pauschal mit `xfail` markiert; der Adversary deckte auf, dass 3 duplizierte Hilfsmethoden (`_load_validate_transition()` in `TestAC5ValidateTransitionAdrField`, `TestF001BackwardCompatibility`, `TestF004TemplatePlaceholder`) noch auf den stale lokalen Pfad `_HOOKS_DIR / "workflow.py"` zeigten statt auf `_resolve_plugin_hook()` — dadurch scheiterten 10 der 12 an `FileNotFoundError` im Testcode statt an der behaupteten ADR-Lücke. Nach Pfad-Fix (konsolidiert in `_load_validate_transition_from_workflow()`) zeigte `--runxfail`, dass nur **5 Tests** tatsächlich an der fehlenden Blocking-Logik scheitern (`TestAC1BlockWhenDecisionSurfaceWithoutAdr::test_integration_bash_gate_blocks_decision_surface`, `TestAC5ValidateTransitionAdrField::test_blocks_when_adr_field_missing_or_empty`, `TestF001BackwardCompatibility::test_new_spec_with_created_today_enforces_adr`, `TestF004TemplatePlaceholder::test_template_placeholder_keine_blocks_new_spec`, `TestF005SelfExempt::test_integration_bash_gate_blocks_adr_guard_change`) — nur diese 5 tragen `xfail(reason="... siehe #1164", strict=False)`. Die restlichen 7 (Allow-Pfad-Tests: gültiger Fall wird korrekt nicht blockiert) laufen als reguläre grüne Tests, da sie unabhängig vom #1164-Fix wahr bleiben. AC-1 gilt als erfüllt im Sinne von: Datei-Resolution funktioniert vollständig (auch in den Hilfsmethoden), kein Crash mehr, und nur die tatsächlich betroffene Lücke ist sichtbar getrackt. Tatsächliches Testergebnis: 50 passed, 5 xfailed, 0 failed (statt der ursprünglich spezifizierten "alle vollständig grün").

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-/Doku-Korrektur ohne Produktionscode-Änderung und ohne neue Architektur-Entscheidung — das Shim-Pattern (`_resolve_plugin_module()`) existiert bereits und wird nur auf zusätzliche Dateien angewendet.

## Changelog

- 2026-07-09: Initial spec created
