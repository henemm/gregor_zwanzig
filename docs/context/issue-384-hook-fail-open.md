# Context: Issue #384 — Hook-Infrastruktur fail-open härten

## Request Summary
Fehlt eine in `.claude/settings.json` registrierte Hook-Datei im Working-Tree, brechen
alle `PreToolUse`-Hooks mit Exit≠0 ab → Claude Code wertet das als **block** → die
betroffene Session verliert schlagartig Bash/Read/Edit (fail-CLOSED). Ein *fehlender*
Hook ist ein Infrastruktur-Defekt, kein Sicherheitsereignis, und muss **fail-open**
behandelt werden: Datei da → Hook läuft normal (echte Blocks bleiben); Datei weg →
Tool wird erlaubt.

## Root Cause (bereits belegt)
- Alle Hooks laufen als `python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py`.
- `${CLAUDE_PROJECT_DIR}` zeigt für **jede** Session aufs Hauptrepo — auch für isolierte
  Worktree-Sessions. Schaltet eine Fremd-Session den geteilten Hauptrepo-Tree per
  `git checkout`/`git stash branch` auf einen alten Commit ohne die Hook-Datei, ist die
  Datei kurzzeitig weg → `python3 … : No such file or directory` (Exit 127) → PreToolUse
  blockt → **alle** Sessions verlieren ihr Tooling.
- Konkreter Vorfall 2026-05-26 (#353-Session): Auslöser war `git stash branch stash-343-wip`
  → checkout auf `cf87fbc`, wo `session_singleton_guard.py` noch nicht existierte.
- Die Datei ist eine normale git-Datei (Modus 100644), **kein** Symlink.

## Verifizierte Fix-Mechanik (empirisch, bash + sh)
Inline-Guard pro Hook-Eintrag:
```sh
if [ -f "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" ]; then python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" <args>; fi
```
| Situation | Exit-Code | Wirkung | AC |
|-----------|-----------|---------|----|
| Datei fehlt | `0` | Tool erlaubt (fail-open) | AC-1/AC-3 |
| Datei da, Hook blockt (`exit 2`) | `2` | Block bleibt voll wirksam | AC-2 |
| Datei da, Hook OK (`exit 0`) | `0` | unverändert | AC-4 |

**Verworfene Alternative:** `python3 … || exit 0` / `|| true` — wandelt auch *echte*
Blocks (Exit 2) in Exit 0 um → hebelt jedes Gate aus. Empirisch bestätigt. NICHT verwenden.

Quoting der Pfade (`"…"`) ist additiv robust (CLAUDE_PROJECT_DIR mit Leerzeichen),
ändert das Verhalten sonst nicht.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `.claude/settings.json` | **Einziger zu ändernder Produktiv-Artefakt.** Enthält 24 `python3 ${CLAUDE_PROJECT_DIR}`-Hook-Einträge über PreToolUse/SessionStart/Stop/UserPromptSubmit/PostToolUse |
| `.claude/hooks/*.py` (22 referenzierte) | Die Hook-Implementierungen selbst — bleiben **unverändert**; nur ihre Einbindung in settings.json wird gehärtet |
| `tests/tdd/test_issue_348_parallel_workspaces.py` | Präzedenz: `.claude`-Tooling wird mock-frei in `tests/tdd/` getestet — Vorbild für AC-3-Regressionstest |
| `.claude/tools/gz-workspace` | Isolierte Parallel-Arbeitskopie für die Implementierung (Tree ist aktuell dirty) |

## Betroffene settings.json-Einträge (24 Hook-Invocations)
- **PreToolUse / `Edit|Write`** (14): workflow_gate, spec_enforcement, claude_md_protection,
  tdd_enforcement, red_test_gate, post_implementation_gate, scope_guard, plan_validator,
  ui_screenshot_gate, domain_pattern_guard, architecture_guard, track_changes, backlog_guard,
  data_schema_backup
- **PreToolUse / `Bash`** (4): pre_commit_gate, pre_commit_validation, secrets_guard, e2e_commit_gate
- **PreToolUse / `Read`** (1): secrets_guard
- **PreToolUse / `""`** (1): session_singleton_guard guard  ← der konkrete Lockout-Auslöser
- **SessionStart** (1 py): session_singleton_guard register  (+ `bash /home/hem/claude-mq/check-messages.sh` — absoluter Pfad außerhalb Repo, kann nicht via checkout verschwinden)
- **Stop** (1): notify_sound
- **UserPromptSubmit** (1): workflow_state_updater
- **PostToolUse / `Bash`** (1): auto_restart_server

## Existing Patterns
- Hooks geben Exit 2 = block, Exit 0 = allow zurück (Claude-Code-Konvention).
- `.claude/`-only-Änderungen ohne Deploy gab es bereits: #380 (Approval-Hook gehärtet,
  14 mock-freie Tests, kein Prod-Deploy). #379/#348 (session_singleton_guard, gz-workspace).
- Test-Ablage für Tooling: `tests/tdd/test_issue_<n>_*.py`, mock-frei.

## Dependencies
- **Upstream:** keine — reine Config-Härtung, kein Anwendungscode.
- **Downstream:** Jede laufende Claude-Code-Session hängt am Hook-Dispatch aus settings.json.
  settings.json wird beim Session-Start geladen → Änderung greift für **neue** Sessions;
  evtl. `/hooks`-Reload oder Neustart nötig, damit die laufende Session profitiert (in
  Validierung klären).

## Existing Specs
- `docs/specs/modules/session_singleton_guard.md` — der Hook, dessen Fehlen den Vorfall auslöste.
- `docs/specs/modules/issue_379_session_self_isolate.md` — verwandte Session-Isolierung.
- Neue Spec nötig: `docs/specs/modules/issue_384_hook_fail_open.md` (Phase 3).

## Risks & Considerations
- **R1 — Dirty Tree / Fremd-WIP:** Working-Tree enthält uncommitted Arbeit aus #383
  (Höhenprofil-Kontrast: ProfileEditor/ProfileChart/CONTRAST-AUDIT + specs/tests) und #296
  (waypointEditor.test.ts, 3 RED-Tests). Implementierung daher **isoliert in gz-workspace**
  (nicht im verschmutzten Hauptrepo), Artefakte gezielt einspielen. Stash/checkout im
  geteilten Hauptrepo ist verboten — genau die Ursache von #384.
- **R2 — Selbstreferenz:** Der Fix ändert die Datei, die die Hooks der eigenen Session
  steuert. Editieren von settings.json kann durch die Edit/Write-Gates laufen (workflow_gate
  etc.). Während Phase 6 in korrektem Workflow-Zustand sein.
- **R3 — Vollständigkeit:** Alle 24 Einträge müssen einheitlich gehärtet werden — ein
  übersehener Eintrag reißt das Loch wieder auf. Regressionstest (AC-3) muss settings.json
  **vollständig** parsen und jeden `python3 ${CLAUDE_PROJECT_DIR}`-Eintrag prüfen.
- **R4 — JSON-Validität:** Das `if … fi` muss als einzeiliger String in JSON korrekt
  escaped sein; nach der Änderung `python3 -m json.tool` validieren.
- **R5 — Scope sekundär:** Issue nennt sekundär Prozess-/Doku-Härtung (WIP-Recovery nie im
  geteilten Hauptrepo) für CLAUDE.md. CLAUDE.md ist aktuell bereits modifiziert (Fremd-WIP) —
  in Analyse entscheiden, ob Doku-Teil in diesen Workflow gehört oder separat.

## Akzeptanzkriterien (aus Issue)
- AC-1: fehlende Hook-Datei → Tool erlaubt (kein Lockout).
- AC-2: vorhandene blockende Datei (Exit 2) → Block bleibt wirksam.
- AC-3: automatisierter Test simuliert fehlenden Hook → Aufruf schlägt NICHT fehl.
- AC-4: alle bestehenden Gates bei vorhandener Datei unverändert.

---

## Analyse (Phase 2)

### Typ & Vorgehen
Bug mit **bereits bewiesener Ursache** (git reflog im Issue) und **empirisch verifizierter
Fix-Mechanik** (bash+sh: fehlende Datei→exit 0, blockende Datei→exit 2). Daher **kein
bug-intake-Agent** (würde Bekanntes reproduzieren — „keine Agenten für Triviales").
Unabhängige Verifikation erfolgt über den AC-3-Regressionstest + Adversary in der Test-Phase.

### Konfigurations-Landschaft (verifiziert)
- `.claude/settings.json` — **24** `${CLAUDE_PROJECT_DIR}`-Hook-Invocations (verwundbar) +
  1 externes Kommando `bash /home/hem/claude-mq/check-messages.sh` (absoluter Pfad außerhalb
  Repo → kann nicht via `git checkout` verschwinden → **nicht** die Fehlerquelle).
- `.claude/settings.local.json` — **kein** hooks-Block (nichts zu härten).
- `~/.claude/settings.json` (global, repo-übergreifend) — hat **keine** PreToolUse-Hooks
  (nur SessionStart) → der Lockout-Vektor existiert **ausschließlich** in der Repo-settings.json.
  Scope damit sauber auf dieses Repo begrenzt.

### Entscheidung: ALLE 24 Einträge härten (nicht nur PreToolUse)
Issue nennt primär PreToolUse/PostToolUse. Erweiterte Empfehlung: **alle** 24
`${CLAUDE_PROJECT_DIR}`-Einträge über **alle** Events einheitlich härten. Begründung:
- `UserPromptSubmit` (workflow_state_updater): Exit≠0 kann die Prompt-Abgabe blockieren →
  ebenfalls sitzungs-lähmend.
- Einheitlichkeit verhindert, dass ein übersehener Eintrag das Loch wieder aufreißt (R3).
- `SessionStart`/`Stop`/`PostToolUse`: weniger kritisch, aber Härtung kostet nichts und
  AC-3 verlangt ohnehin vollständiges Parsen.
Das externe `check-messages.sh` bleibt unangetastet (kann nicht verschwinden).

### Fix-Form (final)
Pro Eintrag, Pfad gequotet:
```sh
if [ -f "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" ]; then python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" <args>; fi
```

### Test-Design (AC-3, mock-frei, in tests/tdd/)
`tests/tdd/test_issue_384_hook_fail_open.py`:
1. **Strukturell:** settings.json parsen; jeder `${CLAUDE_PROJECT_DIR}`-Eintrag MUSS dem
   fail-open-Guard-Muster entsprechen (Regex/Substring) — fängt künftig neu hinzugefügte,
   ungehärtete Hooks (Regressionsschutz gegen Wieder-Aufreißen).
2. **Verhalten — fehlende Datei:** Guard-Kommando mit nicht-existentem Pfad ausführen →
   `exit 0` (AC-1/AC-3).
3. **Verhalten — blockende Datei:** temp-Hook der `sys.exit(2)` macht → Guard-Kommando →
   `exit 2` bleibt (AC-2).
4. **Verhalten — OK-Datei:** temp-Hook `exit 0` → `exit 0` (AC-4).
Keine Mocks: echte Subprozesse, echtes settings.json.

### Scope-Schätzung
- **Dateien:** 2 (1 geänderte Config `.claude/settings.json`; 1 neuer Test in `tests/tdd/`).
  Spec-Doc (Phase 3) + dieses Kontext-Doc separat.
- **LoC:** settings.json ~24 geänderte Zeilen (Wrapping); Test ~90–120 LoC. **Gesamt < 250.**
  Keine Scope-Flags überschritten.

### Abgegrenzt / Folgearbeiten (NICHT in #384)
- **CLAUDE.md-Doku-Härtung (Issue sekundär):** Wissen ist bereits in Memory
  `feedback_shared_repo_hook_lockout` + `feedback_isolate_parallel_work_upfront` festgehalten;
  CLAUDE.md ist aktuell mit Fremd-WIP (#383) modifiziert → Anfassen riskiert Verflechtung.
  Empfehlung: separater Mini-Schritt **nach** #384, oder bewusst weglassen (Wissen existiert).
- **Schwester-Repos (infra/n8n/website):** könnten dieselbe fail-closed-Form haben. Nach
  Verifikation eine MQ-`broadcast` mit der Muster-Empfehlung senden (Folge, nicht #384-Scope).

### Implementierungsort
Wegen verschmutztem Tree (R1): isolierte **gz-workspace**-Kopie. settings.json + Test dort
bauen, dann gezielt nach main einspielen. Kein stash/checkout im geteilten Hauptrepo.
