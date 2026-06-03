# Context: Bug #569 — Edit-Tool schlägt lautlos fehl bei .claude/commands/*.md

## Request Summary
Das Edit-Tool meldet "success" beim Bearbeiten von `.claude/commands/*.md`-Dateien, aber die Dateien bleiben unverändert. Python/Bash-Write funktioniert als Workaround. Bug wurde bei Commit 5c0c80b5 beobachtet.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/settings.json` | 14 PreToolUse-Hooks für Edit/Write definiert |
| `.claude/hooks/workflow_gate.py` | Haupt-Gate: `.md$` → always_allowed → exit 0 |
| `.claude/hooks/scope_guard.py` | `.md` in ALWAYS_ALLOWED (hardcoded) → exit 0 |
| `.claude/hooks/spec_enforcement.py` | Prüft nur `protected_paths` (src/*.py etc.) → exit 0 |
| `.claude/hooks/track_changes.py` | Exit 0 always, nur Tracking |
| `.claude/hooks/config_loader.py` | `get_project_root()` via `find_main_repo_from_worktree` → IMMER `/home/hem/gregor_zwanzig` |
| `.claude/openspec.yaml` | `always_allowed: ['\\.md$', ...]` — alle .md-Dateien erlaubt |
| `.claude/commands/6-validate.md` | Betroffene Skill-Datei |
| `.claude/commands/7-deploy.md` | Betroffene Skill-Datei |
| `.claude/commands/e2e-verify.md` | Betroffene Skill-Datei |

## Existing Patterns
- `.md$` in `always_allowed` → sämtliche Hooks lassen `.md`-Dateien durch (verifiziert: alle 9 Hooks exit 0)
- `get_project_root()` nutzt `find_main_repo_from_worktree()` — gibt IMMER den Haupt-Repo-Pfad zurück, auch aus dem Worktree
- `CLAUDE_PROJECT_DIR` ist im Bash-Shell NICHT gesetzt; wird von Claude Code gesetzt wenn Hooks laufen

## Root Cause (beste Hypothese)
**Path-Diskrepanz beim EnterWorktree-Übergang:**

Wenn eine Session via `EnterWorktree` in den Worktree wechselt (`.claude/worktrees/eventual-moseying-bentley`), besteht möglicherweise ein Unterschied, WOHIN das Edit-Tool schreibt und WOHIN das Read-Tool liest:
- Edit-Tool nutzt `CLAUDE_PROJECT_DIR` zur Pfad-Auflösung → Hauptrepo-Pfad → modifiziert `/home/hem/gregor_zwanzig/.claude/commands/6-validate.md`
- Read-Tool nutzt CWD (Worktree) → liest `/home/hem/gregor_zwanzig/.claude/worktrees/eventual-moseying-bentley/.claude/commands/6-validate.md`
- Diese zwei Dateien sind VERSCHIEDENE Inodes (git worktree ≠ gz-workspace hardlinks)
- Ergebnis: Edit meldet Erfolg (hat die Hauptrepo-Datei geändert), Read zeigt alten Inhalt (Worktree-Datei unverändert)

**Beweis:**
- Test-Edit mit absolutem Worktree-Pfad: MODIFIZIERT Worktree-Datei, Hauptrepo unverändert ✓
- `diff` zwischen Hauptrepo und Worktree: identischer Inhalt JETZT (5c0c80b5 bereits auf main)
- Worktree-Branch `worktree-eventual-moseying-bentley` HEAD = `0afe7c85` (VOR 5c0c80b5)
- 3 Dateien als "M" im Worktree → Python/Bash hat in den Worktree geschrieben, Commit von main

## Dependencies
- Upstream: Claude Code harness (Edit/Read-Pfadauflösung in Worktrees)
- Downstream: Alle `.claude/commands/` Skill-Dateien — bei Selbstverbesserung des Workflows

## Risks & Considerations
- Risk 1: "Stille Falschmeldung" — Claude arbeitet weiter mit unmodifizierter Datei
- Risk 2: Nur bei Workflow-Selbstverbesserung (sehr selten), nicht bei normalen Features
- Risk 3: Keine Reproduzierbarkeit im laufenden Session-Kontext (absoluter Pfad = OK)

## Fix-Optionen
1. **PostToolUse-Hook für Edit** (detektiert stille Fehler) → bestes Nutzen/Aufwand-Verhältnis
2. **Write-Tool statt Edit in Skill-Dateien** (expliziter)
3. **Warnung in CLAUDE.md** (nur Dokumentation)
