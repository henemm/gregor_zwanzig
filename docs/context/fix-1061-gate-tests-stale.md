# Context: fix-1061-gate-tests-stale (Issue #1061)

## Request Summary
Fünf Nebenbefunde aus der #1052-Integration bündeln: dauerhaft rote (nicht durch produktiven Code verursachte) Tests in der Gate-Test-Familie plus ein Doku-Drift in `architecture.md`. Ziel: Testsuite wieder aussagekräftig machen (rot = echter Fehler, nicht Infrastruktur-Rauschen).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `tests/tdd/test_issue_885_adr_guard.py` | `_setup_repo()` (Zeile 68–105) kopiert `_BASH_GATE_SRC = _HOOKS_DIR / "bash_gate.py"` (Zeile 36) — Datei existiert lokal nicht mehr |
| `.claude/hooks/bash_gate.py`, `workflow.py`, `workflow_state_multi.py`, `override_token.py` | Fehlen lokal komplett (auch kein Shim) — vollständig ins Plugin migriert |
| `.claude/hooks/hook_utils.py`, `config_loader.py` | Haben Shims (`_resolve_plugin_module()`), die per `~/.claude/plugins/installed_plugins.json` auf den Plugin-Cache-Pfad auflösen |
| `tests/tdd/test_issue_811_renderer_gate.py` | `test_pass_with_both_evidences` — **bereits grün**, siehe unten |
| `.claude/hooks/renderer_mail_gate.py` (Zeile 314–334) | Golden-Check-Logik: `golden_ok=True` wenn `tests/golden/email/` fehlt UND kein `pyproject.toml` (Fixture-Repo-Fall) |
| `tests/tdd/test_issue_894_registry_cleanup.py` | 3 Tests (Zeile 43–90) patchen nur Env-Vars, nicht `find_project_root()`/`_find_worktree_root()` — lesen daher den echten Worktree-Pointer |
| Plugin `hook_utils.py::resolve_active_workflow()` | Priorität in Worktree-Sessions: 1) `{worktree}/.claude/active_workflow`-Datei, 2) `settings.local.json`, 3) Env-Var. Datei/Settings gewinnen immer gegen Env — Tests isolieren das nicht |
| `tests/tdd/test_issue_898_901_mail_layout.py::TestAC7TrendAsChips` (Zeile ~520–580) | `test_no_trend_table_rows` + `test_trend_has_pill_spans` erwarten Chip-Format für den Ausblick-Trend |
| `src/output/renderers/email/html.py` (Zeile ~1163–1270) | Aktuelle Implementierung rendert Trend explizit als `<table>` mit `<tr>`-Zeilen (Ausblick-Tabelle) |
| `docs/features/architecture.md` (Zeile 147) | Nennt „7 Befehle: glance, hg, dd, now, status, config, help" |
| `src/output/channels/telegram.py::BOT_COMMANDS` (Zeile 89–98) | Tatsächlich 8 Befehle: glance, heute, morgen, now, heute_gewitter, timeline_heute, timeline_morgen, hilfe |

## Rechercheergebnis pro Punkt

**1. bash_gate.py fehlt (Test 885, ~14 Tests rot)** — Bestätigt. Migration ins Plugin (`migrate_to_plugin.py`, Issue #33) hat `bash_gate.py`, `workflow.py`, `workflow_state_multi.py`, `override_token.py` komplett entfernt, ohne Shim. `hook_utils.py`/`config_loader.py` haben einen etablierten Shim-Pattern (`_resolve_plugin_module()` liest `~/.claude/plugins/installed_plugins.json`). Fix-Ansatz: Testfixture `_setup_repo()` löst `_BASH_GATE_SRC` (und die anderen fehlenden Helfer) über denselben Plugin-Registry-Mechanismus auf, statt nur lokal zu suchen.

**2. Golden-Nachweis (Test 811)** — **Bereits gelöst.** Commit `98773f73` (2026-07-07, "fix(#916,#988): Gate-Marker statt letzter-Commit-Scope + Golden-Check-Fixture-Unterscheidung") hat genau diese Fixture/Real-Repo-Unterscheidung eingeführt. `uv run pytest tests/tdd/test_issue_811_renderer_gate.py` läuft komplett grün (8/8). Kein weiterer Handlungsbedarf — nur als „erledigt" dokumentieren/schließen.

**3. Worktree-Env-Isolation (Test 894, 3 Tests rot)** — Bestätigt reproduziert. Ursache: `resolve_active_workflow()` prüft in Worktree-Sessions zuerst die Datei `{worktree}/.claude/active_workflow` und dann `settings.local.json`, bevor die Env-Var greift. Die Tests patchen nur `OPENSPEC_ACTIVE_WORKFLOW`/`CLAUDE_PROJECT_DIR`, nicht diese beiden vorrangigen Quellen — dadurch lesen sie den echten aktiven Workflow dieser Session (aktuell `fix-1061-gate-tests-stale`) statt des Test-Werts. Fix-Ansatz: Tests müssen zusätzlich `monkeypatch.chdir(tmp_path)` in ein Repo ohne `.claude/active_workflow`/`settings.local.json` setzen, oder `_find_worktree_root()`/die Pointer-Datei gezielt mocken/verstecken.

**4. Doku-Drift** — Bestätigt exakt wie im Issue beschrieben. Reine Doku-Korrektur in `architecture.md` Zeile 147.

**5. AC-7-Trend-Chip-Tests (Nachtrag vom 2026-07-08)** — **Kein Bug, sondern überholte Spec.** `TestAC7TrendAsChips` wurde mit #899 (Teil von #898-901, Commit `41d921b8`) für ein Chip/Pill-Format eingeführt. Danach hat der PO in Issue #911 ("Ausblick" SOLL-Bild, „Issue 12: Tabelle übernehmen, Inhalte analog SMS, Cell-Hintergrund = Warnlevel") explizit das Tabellenformat wieder angefordert — Commit "fix(#911): Tabellen-Renderer nach JSX-Vorlage" hat das umgesetzt und ist Adversary-verifiziert im Repo. Die beiden Chip-Tests sind seitdem strukturell unerfüllbar, weil sie ein per PO-Entscheidung verworfenes Design testen. Fix-Ansatz: Tests entfernen/durch AC-konforme Tabellen-Assertions ersetzen — **keine Produktionscode-Änderung**.

## Existing Patterns
- Plugin-Shim-Pattern (`_resolve_plugin_module()`) in `hook_utils.py`/`config_loader.py` ist die etablierte Lösung für „lokale Datei existiert nicht mehr, liegt im Plugin".
- Mock-freie Integrationstests via echtem Temp-Git-Repo + Subprocess sind projektweiter Standard (CLAUDE.md „KEINE MOCKED TESTS").

## Dependencies
- Upstream: `~/.claude/plugins/installed_plugins.json` (Registry), Plugin-Cache-Verzeichnis `agent-os-openspec@.../core/hooks/`.
- Downstream: Keine Produktionscode-Pfade betroffen — ausschließlich Testinfrastruktur + eine Doku-Zeile.

## Existing Specs
- Keine dedizierte Spec für die Gate-Test-Familie; nächstliegend `docs/reference/mail_validators.md` (Validator-Übersicht, nicht direkt betroffen).

## Risks & Considerations
- Punkt 5 erfordert explizite User-Freigabe, da bestehende (wenn auch stale) Tests gelöscht werden — nicht einfach "reparieren".
- Punkt 1: Fix darf keine Produktionslogik in `bash_gate.py` selbst berühren (liegt im Plugin, nicht im Repo) — nur die Testfixture ändert sich.
- Punkt 3: Fix muss ohne Seiteneffekte auf andere Worktree-Sessions auskommen (keine echten Dateien im Hauptrepo anfassen).
- Alle Fixes sind reine Test-/Doku-Änderungen — Blast Radius bleibt niedrig, LoC-Limit (250) unkritisch.

## Analysis

### Type
**Bug** (Testinfrastruktur-Regress + 1 Doku-Drift). Kein Feature, keine Produktionscode-Änderung außer der bereits erledigten Golden-Nachweis-Fix (Punkt 2, nicht Teil dieses Workflows).

### Affected Files (with changes)

| Datei | Änderungstyp | Beschreibung |
|-------|--------------|--------------|
| `tests/tdd/test_issue_885_adr_guard.py` | MODIFY | Plugin-Pfad-Auflösung für `bash_gate.py`, `workflow.py`, `workflow_state_multi.py`, `override_token.py` nach Shim-Vorbild (`hook_utils.py`); Skip mit Begründung falls Plugin nicht gefunden |
| `tests/tdd/test_issue_894_registry_cleanup.py` | MODIFY | Isolation gegen Worktree-Pointer (`.claude/active_workflow`, `settings.local.json`) in allen 3 betroffenen Tests, z.B. via `monkeypatch.chdir` in ein pointer-freies Temp-Repo |
| `tests/tdd/test_issue_898_901_mail_layout.py` | MODIFY | `TestAC7TrendAsChips` (2 Tests) an das PO-freigegebene Tabellenformat aus #911 anpassen bzw. entfernen |
| `docs/features/architecture.md` | MODIFY | Zeile 147: 7→8 Befehle, korrekte Namen aus `BOT_COMMANDS` |

Punkt 2 (Golden-Nachweis, #811) ist bereits gelöst (Commit `98773f73`) — keine Änderung nötig, wird im Workflow nur als "kein Handlungsbedarf" dokumentiert/als AC mit Status "bereits erfüllt" geführt.

### Scope Assessment
- Files: 4 (3 Testdateien + 1 Doku-Zeile)
- Estimated LoC: ~+50/-30 (Testdateien zählen nicht gegen das 250-LoC-Limit, da es sich um Testcode handelt — reine Doku-Zeile zählt ohnehin nicht)
- Risk Level: **LOW** — ausschließlich Test-/Doku-Änderungen, keine Produktionspfade, keine CI-Kopplung (tests/tdd läuft laut Issue nicht im CI-äquivalenten Lauf)

### Technical Approach
1. **#885 bash_gate:** Hilfsfunktion `_resolve_plugin_hook(name: str) -> Path | None` einführen, die zuerst lokal (`_HOOKS_DIR`) sucht, sonst `~/.claude/plugins/installed_plugins.json` nach `agent-os-openspec@*` durchsucht (gleiche Logik wie `hook_utils.py::_resolve_plugin_module`) und den Pfad im Plugin-Cache liefert. `_setup_repo()` nutzt das für alle vier fehlenden Dateien. Kein Plugin gefunden → `pytest.skip("agent-os-openspec Plugin nicht installiert")`.
2. **#894 Worktree-Isolation:** Jeder der 3 Tests bekommt zusätzlich `monkeypatch.chdir(tmp_path)` (leeres Verzeichnis ohne `.claude/`) VOR dem `import hook_utils`, damit `_find_worktree_root()`/`find_project_root()` nichts Echtes findet. Alternativ: `monkeypatch.setattr(hook_utils, "resolve_active_workflow", ...)` direkt — aber das würde den eigentlichen Resolver umgehen statt ihn korrekt zu testen. Erste Variante (chdir in echtes leeres Temp-Repo) bevorzugt, da mock-frei (CLAUDE.md-Pflicht).
3. **#898/#901 AC-7:** Nach User-Freigabe (siehe offene Frage unten) `TestAC7TrendAsChips` entweder löschen (Design ist überholt) oder in `TestAC7TrendAsTable` umbenennen/umschreiben mit Assertions gegen das aktuelle `<table>`-Markup (z.B. `tr_count == len(trend)`, Zellhintergrund nach Warnlevel).
4. **Doku-Drift:** Ein-Zeilen-Fix in `architecture.md`.

### Dependencies
- Kein Produktionscode betroffen — keine Downstream-Abhängigkeiten.
- Upstream: `~/.claude/plugins/installed_plugins.json`-Format muss stabil bleiben (bereits etabliertes Muster, kein neues Risiko).

### Open Questions
- [x] Punkt 2 bestätigt bereits erledigt — kein Aufwand im Workflow.
- [x] Punkt 5: **User-Entscheidung (2026-07-09): Umschreiben** — `TestAC7TrendAsChips` → `TestAC7TrendAsTable`, Assertions gegen aktuelles `<table>`-Markup (Zeilenzahl je Trend-Tag, Zellhintergrund nach Warnlevel). Kein Löschen ohne Ersatz.
