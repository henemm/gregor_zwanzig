---
entity_id: issue_348_parallel_workspaces
type: infra
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [workflow, hooks, worktree, parallel-sessions, settings, tooling, issue-348]
---

<!-- Issue #348 — Isolierte Parallel-Workspaces für mehrere gleichzeitige Claude-Sessions -->

# Issue #348 — Isolierte Parallel-Workspaces (clone-basiert)

## Approval

- [ ] Approved

## Zweck

Mehrere Claude-Sessions teilen sich heute `/home/hem/gregor_zwanzig` als einen Working-Tree. Das kollidiert auf zwei Ebenen: (1) gemeinsame Dateien — uncommittete Fremd-Arbeit verschmutzt die Sicht, das Commit-Gate fährt die Suite über fremde WIP, `git add -A` würde Fremd-Arbeit mit-committen; (2) gemeinsame Workflow-Buchführung — die Session-/Aufgaben-Zuordnung läuft zentral zusammen und verwechselt Sessions (heute landete „freigegeben" kurz auf der falschen Aufgabe).

Lösung: **eine isolierte Arbeitskopie pro Parallel-Session** via `git clone --local` (Objekte gehardlinkt → platzsparend; eigene `.git`, eigener Index, eigener `.claude/`-State). Voraussetzung dafür ist, dass die Hook-Pfade in `settings.json` portabel werden (`${CLAUDE_PROJECT_DIR}`), damit jede Kopie ihre EIGENEN Hooks ausführt. Dazu ein Workspace-Manager (`new`/`list`/`clean`) und die Regel in CLAUDE.md.

Erwartete Parallelität: 4+ Sessions → Optimierung auf Platz (Hardlinks) und Übersicht (`list`/`clean`).

## Quelle / Source

**Geänderte/Neue Dateien:**
- `.claude/settings.json` — alle 22 repo-relativen Hook-Pfade `/home/hem/gregor_zwanzig/.claude/hooks/...` → `${CLAUDE_PROJECT_DIR}/.claude/hooks/...` (quoted). Der SessionStart-Eintrag `bash /home/hem/claude-mq/check-messages.sh` (geteilte externe Infra) bleibt absolut.
- `.claude/tools/gz-workspace` — NEU: Bash-Workspace-Manager (`new`, `list`, `clean`).
- `tests/tdd/test_issue_348_parallel_workspaces.py` — NEU: Tests gegen die ACs (echte git-Operationen, keine Mocks).
- `CLAUDE.md` — NEU: kurzer Abschnitt „Parallele Sessions" (Regel + Befehle).

> **Schicht-Hinweis:** Reine Tooling-/Config-Schicht (`.claude/`, `CLAUDE.md`, `tests/`). KEIN Produktiv-Code in `src/`, `api/`, `internal/`, `frontend/`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/settings.json` | Config | Hook-Pfade werden portabel (`${CLAUDE_PROJECT_DIR}`) |
| Claude-Code Hook-Runner | Plattform | Expandiert `${CLAUDE_PROJECT_DIR}` pro Session/Kopie (bestätigt: ab v2.1.38, `minimumVersion` ist gesetzt) |
| `git` | CLI | `clone --local` für platzsparende, voll isolierte Kopien |
| Issue #339 | GitHub | Aufgefallen während des #339-Commits (Fremd-WIP im Tree) |
| Issues #325 / #332 | GitHub | Zentrale Session-Bindung — die tiefere Fragilität (separater Folgeschritt) |

## Implementation Details

### 1. `settings.json` — Hook-Pfade portabel

Ersetze in JEDEM `command` mit `/home/hem/gregor_zwanzig/.claude/hooks/<x>.py` den Präfix durch `"${CLAUDE_PROJECT_DIR}"/.claude/hooks/<x>.py` (Shell-Form, Variable gequotet). Betrifft PreToolUse (Edit|Write: 14, Bash: 4, Read: 1), Stop (1), UserPromptSubmit (1), PostToolUse (1) = 22 Stück. Der claude-mq-SessionStart-Pfad bleibt unverändert absolut.

Beispiel:
```json
"command": "python3 \"${CLAUDE_PROJECT_DIR}\"/.claude/hooks/workflow_gate.py"
```

### 2. `.claude/tools/gz-workspace` — Workspace-Manager (Bash)

Konfiguration: `WS_ROOT="${GZ_WS_ROOT:-/home/hem/gz-workspaces}"`. Hauptrepo = das Repo, in dem das Skript liegt (über Skript-Pfad ermittelt).

- **`new <name>`**
  - Name validieren (`^[a-z0-9][a-z0-9-]*$`), sonst Fehler + exit 1.
  - Abbruch wenn `$WS_ROOT/<name>` existiert.
  - `git clone --local <hauptrepo> $WS_ROOT/<name>` (Objekte gehardlinkt).
  - Im Klon: `git checkout -b ws/<name>`.
  - Hinweis ausgeben: `cd $WS_ROOT/<name>` und dort eine neue Claude-Session starten; für Frontend-Arbeit `cd frontend && npm ci`.
  - Sicherstellen, dass der Klon mit sauberem lokalen Workflow-State startet (falls `.claude/workflows/*.json` nicht ohnehin gitignored ist: laufende State-Dateien im Klon entfernen).
- **`list`**
  - Jeden Ordner unter `$WS_ROOT` auflisten mit: Branch, Anzahl uncommitteter Dateien (`git status --porcelain | wc -l`), Ahead/Behind ggü. `origin/<branch>` falls verfügbar.
- **`clean <name>`** (und `clean --merged` optional)
  - Sicherheits-Check: Abbruch (exit 1) wenn uncommittete Änderungen ODER ungepushte Commits vorhanden — außer `--force`.
  - Bei OK: `rm -rf $WS_ROOT/<name>` (Klon hat eigene gehardlinkte Objekte; Hauptrepo bleibt unberührt).
- `--help` / keine Argumente → Usage.

### 3. `CLAUDE.md` — Abschnitt „Parallele Sessions"

Kurz: Ein Projektordner = höchstens eine Claude-Session gleichzeitig. Für Parallelarbeit `bash .claude/tools/gz-workspace new <name>`, dort eine neue Session starten; mit `list` Übersicht, mit `clean` aufräumen. Jeder Workspace ist voll isoliert (eigene Dateien + eigener Workflow-State).

### 4. Verifikation der Portabilität (Risiko-Mitigation)

Nach der `settings.json`-Änderung prüft der Orchestrierer LIVE in der Hauptrepo-Session, dass die Hooks weiter feuern (eine harmlose Edit-/Bash-Aktion löst die Hooks aus; bei „file not found"-Fehlern auf `${CLAUDE_PROJECT_DIR}` sofort Rollback der settings.json). JSON-Gültigkeit + korrekte Pfadform werden zusätzlich im Test geprüft.

## Expected Behavior

- **Input:** `bash .claude/tools/gz-workspace new feature-x`
- **Output:** isolierte Kopie unter `/home/hem/gz-workspaces/feature-x` auf Branch `ws/feature-x`, eigene `.git`/Index/`.claude`-State; Hinweis zum Session-Start. Die Hauptrepo-Session und andere Workspaces bleiben unberührt.
- **Side effects:** keine Änderung am Hauptrepo-Working-Tree; Disk-Bedarf gering (gehardlinkte git-Objekte).

## Acceptance Criteria

- **AC-1:** Given `.claude/settings.json` nach dem Umbau / When der Inhalt geprüft wird / Then enthält kein Hook-`command` mehr den Präfix `/home/hem/gregor_zwanzig/.claude/hooks`, und alle 22 repo-relativen Hook-Pfade nutzen `${CLAUDE_PROJECT_DIR}/.claude/hooks/`.
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given `.claude/settings.json` nach dem Umbau / When es als JSON geparst wird / Then ist es valide, und der SessionStart-Eintrag für `claude-mq/check-messages.sh` bleibt unverändert absolut (geteilte Infra, kein `${CLAUDE_PROJECT_DIR}`).
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given ein Quell-Repo / When `gz-workspace new <name>` läuft / Then existiert `$WS_ROOT/<name>` als eigenständiges git-Repo (eigenes `.git`), ausgecheckt auf Branch `ws/<name>`, und das Quell-Repo-Working-Tree ist unverändert.
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given mind. ein angelegter Workspace / When `gz-workspace list` läuft / Then erscheint der Workspace-Name mit seinem Branch und einem Status-Indikator (Anzahl uncommitteter Dateien).
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given ein Workspace mit uncommitteten Änderungen / When `gz-workspace clean <name>` OHNE `--force` läuft / Then bricht das Skript mit exit != 0 ab und entfernt den Workspace NICHT; mit `--force` wird er entfernt.
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given ein per `new` erzeugter Workspace / When seine `.claude/settings.json` geprüft wird / Then nutzt sie weiterhin `${CLAUDE_PROJECT_DIR}` (keine auf das Hauptrepo zeigenden Hook-Pfade) — die Kopie führt also ihre EIGENEN Hooks aus.
  - Test: (populated after /4-tdd-red)

- **AC-7:** Given Produktiv-Code in `src/`, `api/`, `internal/`, `frontend/` / When der Umbau abgeschlossen ist / Then ist dieser Code zeichengleich zur Pre-Fix-Version (Änderung nur in `.claude/`, `CLAUDE.md`, `tests/`).
  - Test: (populated after /4-tdd-red)

## Known Limitations

- **Frontend-Abhängigkeiten** (`node_modules`) werden pro Workspace nicht automatisch installiert (gitignored, nicht im Klon). Für Frontend-Arbeit `npm ci` im Workspace — bewusst, um keine fehleranfälligen node_modules-Symlinks zu erzeugen.
- **`settings.json`-Reload:** Ob die portablen Pfade in einer bereits laufenden Session sofort greifen oder erst beim nächsten Session-Start, ist plattformabhängig. Der Live-Smoke-Test (Detail §4) deckt das ab; im Zweifel Session neu starten.
- **Tiefere Sanierung** der zentralen Session-Bindung (#325/#332) bleibt separater Folgeschritt — die Klon-Lösung umgeht das Problem, behebt es nicht an der Wurzel.

## Out of Scope

- Umbau auf `git worktree` (bewusst nicht — `worktree_state_routing` zentralisiert den State = die zu vermeidende Kollision).
- Sanierung der zentralen Workflow-Session-Bindung (#325/#332).
- Entfernen des veralteten `auto_restart_server.py` (toter Port 8080) — separate Altlast, eigener Auftrag.
- Automatische node_modules-Verteilung über Workspaces.

## Changelog

- 2026-05-23: Initial spec. Isolierte clone-basierte Parallel-Workspaces + portable Hook-Pfade (`${CLAUDE_PROJECT_DIR}`) + Workspace-Manager. Reine Tooling-/Config-Schicht, kein Produktiv-Code.
