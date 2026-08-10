# Context: fix-1478-teil1-gate-fehlalarme

## Request Summary

`broad_test_run_gate.py` blockiert reine Lesebefehle, die zufällig das Wort
"pytest" als Argumentwert enthalten (z.B. `grep -n "pytest" .github/workflows/*.yml`,
`pgrep -af "pytest"`), weil `_pytest_invocations()` jedes Token mit dem
Wortlaut "pytest" für einen echten Aufrufbeginn hält — unabhängig von seiner
Position im Kommando. Belegt von einer Peer-Session am 2026-08-09, Issue
#1478 (Teil 1, dritter Fall derselben Fehlalarm-Familie neben den bereits im
Plugin-Repo behobenen `bash_gate.py`-Fällen).

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/broad_test_run_gate.py` | `_pytest_invocations()` (Zeile 131-138): prüft nur `tok == "pytest"`, keine Positionsprüfung |

## Existing Patterns

- Bereits tokenbasiert (`shlex.split` via `_tokens()`), nicht naiver
  Teilstring-Scan über den ganzen String — die Grundstruktur ist richtig,
  nur die Positionsprüfung fehlt.
- Vorbild für "nicht fragen ob ich einen Aufruf erkenne, sondern ob ich
  sicher bin, dass keiner drinsteckt": `hook_utils.is_git_subcommand`
  (agent-os-openspec, Issue #1431 dort).
- Real genutztes Aufrufmuster in diesem Projekt (CLAUDE.md): ausschließlich
  `uv run pytest ...` — kein bares `pytest`, kein `python -m pytest` in der
  dokumentierten Konvention (aber `-m pytest` wird vom bestehenden Code
  bereits gesondert behandelt, Zeile 137, bleibt unverändert).

## Dependencies

- `hook_utils.find_project_root`, `hook_utils.get_active_workflow_name` —
  unverändert, nicht betroffen
- Keine Tests existieren bisher für diesen Hook (`grep -rl broad_test_run_gate`
  über `tests/` liefert nichts) — neue Testdatei nötig

## Risks & Considerations

- **Sicherheitsrelevant in die andere Richtung:** die Korrektur darf einen
  ECHTEN breiten Testlauf nicht durchrutschen lassen (Grund des Gates:
  2026-08-03, echte Telegram-Nachrichten an Prod, #1477). Die Fix-Richtung
  ("nur an Kommando-Position zählt als Aufruf") verengt die Fehlalarm-Fläche,
  lockert aber nicht die eigentliche Schutzwirkung — ein echter
  `pytest`/`uv run pytest`-Aufruf ohne benannte Dateien bleibt an
  Kommando-Position und wird weiterhin erkannt.
- Muss `uv run pytest` (das im Projekt tatsächlich verwendete Muster)
  weiterhin als Aufruf erkennen — nicht nur bares `pytest` am Segmentanfang.
- Shell-Trenner (`&&`, `||`, `;`, `|`) müssen als neue Segmentanfänge zählen,
  damit `cmd1 && pytest tests/` weiterhin erkannt wird.

## Analysis

### Type
Bug (Gate-Fehlalarm, blockiert legitime Lesebefehle)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/broad_test_run_gate.py` | MODIFY | `_pytest_invocations()`: Positionsprüfung ergänzen (Segmentanfang oder nach `run`) |
| `tests/unit/test_broad_test_run_gate_pytest_word_position.py` | CREATE | Neue Testdatei (keine bestehende vorhanden) |

### Scope Assessment
- Files: 2 (1 Produktivdatei, 1 neue Testdatei)
- Estimated LoC: ~20 (Produktivcode) + ~60 (Tests)
- Risk Level: LOW-MEDIUM (projektweiter Commit-Gate, aber additive Verengung ohne Schutzlockerung)

### Technical Approach
`_pytest_invocations()` erweitern: ein "pytest"-Token (oder `*/pytest`) zählt
nur als Aufrufbeginn, wenn es (a) am Anfang der Token-Liste steht, (b) direkt
nach einem Shell-Trenner (`&&`, `||`, `;`, `|`) steht, oder (c) direkt nach
`run` steht (deckt `uv run pytest`). Die bestehende `-m pytest`-Regel bleibt
unverändert als eigener Zweig. Kein Eingriff an `_tokens()`, `_args_after()`,
`_names_concrete_test_files()`, `_has_safe_flag()` — die Positionsprüfung ist
lokal auf `_pytest_invocations()` begrenzt.

### Open Questions
Keine.
