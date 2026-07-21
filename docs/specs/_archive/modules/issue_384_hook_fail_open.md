---
entity_id: issue_384_hook_fail_open
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [bug, workflow, hook, infra]
---

# Issue #384 — Hook-Infrastruktur fail-open härten

## Approval

- [ ] Approved

## Purpose

Verhindert den Total-Tool-Lockout, wenn eine in `.claude/settings.json` registrierte
Hook-Datei kurzzeitig im geteilten Hauptrepo-Working-Tree fehlt (z. B. weil eine
Parallel-Session den Tree per `git checkout` auf einen Commit ohne die Datei schaltet).
Ein **fehlender** Hook ist ein Infrastruktur-Defekt und muss **fail-open** sein
(Tool erlaubt), während ein **vorhandener** Hook bei echtem Verstoß (Exit 2)
weiterhin **fail-closed** blockt. Behebt #384.

## Source

- **File:** `.claude/settings.json` (die Hook-**Command-Strings**, nicht die `.py`-Dateien)
- **Identifier:** alle 24 `${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py`-Invocations über
  die Events `PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`, `UserPromptSubmit`
- **Schicht:** Claude-Code-Hook-/Konfigurations-Infrastruktur. **Keine** App-Schicht —
  weder Go-API (`internal/`, `cmd/`) noch Python-Backend (`src/`) noch SvelteKit
  (`frontend/`) werden berührt. Die 22 Hook-`.py`-Dateien bleiben **unverändert**;
  geändert wird nur ihre Einbindung. Test in `tests/tdd/`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/*.py` (22 referenzierte) | Hook-Skripte | Implementieren die Gates; Verhalten bei vorhandener Datei unverändert |
| `${CLAUDE_PROJECT_DIR}` | Env-Var | Zeigt für jede Session aufs Hauptrepo — Wurzel der geteilten Verwundbarkeit |
| `bash /home/hem/claude-mq/check-messages.sh` | externes Kommando | SessionStart, absoluter Pfad außerhalb Repo → kann nicht via checkout verschwinden → **nicht** Teil des Fixes |

## Implementation Details

Ursache: Jeder Hook läuft als `python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py`.
Fehlt die Datei, endet `python3` mit Exit 127 (`No such file or directory`). PreToolUse
wertet Exit≠0 als **block** → die Session verliert Bash/Read/Edit. `${CLAUDE_PROJECT_DIR}`
zeigt für **jede** Session aufs Hauptrepo, daher schützt Worktree-Isolation NICHT.

Fix: Jede der 24 Invocations in einen Inline-Existenz-Guard wickeln (Pfade gequotet):

```sh
if [ -f "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" ]; then python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" <args>; fi
```

Etwaige Argumente stehen **außerhalb** der Quotes nach dem Pfad
(z. B. `… session_singleton_guard.py" guard; fi`).

Exit-Code-Semantik (empirisch unter `bash` und `sh` verifiziert):

| Situation | Exit | Wirkung | AC |
|-----------|------|---------|----|
| Datei fehlt | `0` | Tool erlaubt (fail-open) | AC-1/AC-3 |
| Datei da, Hook blockt (`exit 2`) | `2` | Block bleibt voll wirksam | AC-2 |
| Datei da, Hook OK (`exit 0`) | `0` | unverändert | AC-4 |

**Verworfen:** `python3 … || exit 0` / `|| true` — wandelt auch echte Blocks (Exit 2)
in Exit 0 um und hebelt jedes Gate aus. Empirisch bestätigt. Inline-`if` ist die einzig
korrekte Form und braucht kein zentrales Wrapper-Script (das selbst fehlen könnte).

Nach der Änderung MUSS `.claude/settings.json` valides JSON bleiben
(`python3 -m json.tool` als Smoke-Check).

## Expected Behavior

- **Input:** Claude Code lädt `.claude/settings.json` und dispatcht Hooks pro Event.
- **Output:** Bei vorhandener Hook-Datei identisches Verhalten wie bisher (inkl. echter
  Blocks); bei fehlender Hook-Datei wird das Tool erlaubt statt blockiert.
- **Side effects:** Kein Tool-Lockout mehr durch fehlende Hook-Dateien. Keine Änderung
  an der Gate-Logik selbst.

## Acceptance Criteria

- **AC-1:** Given ein PreToolUse-Hook ist in `settings.json` registriert / When die
  zugehörige Hook-Datei im Working-Tree fehlt / Then wird das Tool **erlaubt** (Exit 0),
  nicht blockiert — kein Tool-Lockout.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine vorhandene Hook-Datei, die einen echten Verstoß blockiert (Exit 2) /
  When das Tool aufgerufen wird / Then bleibt der Block voll wirksam (Exit 2 propagiert,
  kein Aufweichen durch die fail-open-Logik).
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein automatisierter Test, der einen fehlenden Hook simuliert (Datei
  temporär wegnehmen) / When das gehärtete Command-String ausgeführt wird / Then ist der
  Exit-Code 0 — Regressionsschutz gegen erneuten Lockout.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine vorhandene Hook-Datei, die mit Exit 0 endet (erlaubt) / When das
  gehärtete Command-String ausgeführt wird / Then ist der Exit-Code 0 — bestehende Gates
  verhalten sich bei vorhandener Datei unverändert.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `.claude/settings.json` wird vollständig geparst / When über alle Events
  iteriert wird / Then entspricht **jeder** `${CLAUDE_PROJECT_DIR}`-Hook-Command-String dem
  fail-open-Guard-Muster (`if [ -f … ]; then python3 … ; fi`) — fängt künftig neu
  hinzugefügte, ungehärtete Hooks (Schutz gegen Wieder-Aufreißen des Lochs, R3).
  - Test: (populated after /tdd-red)

- **AC-6:** Given die geänderte `.claude/settings.json` / When sie geparst wird / Then ist
  sie valides JSON (kein Syntaxfehler durch das eingebettete `if … fi`).
  - Test: (populated after /tdd-red)

## Known Limitations

- Schützt gegen **fehlende** Hook-Dateien. Eine vorhandene, aber **fehlerhafte** Hook-Datei
  (Syntaxfehler, Crash) endet weiterhin mit Exit≠0 und kann blocken — das ist gewollt
  (echter Defekt im Gate-Code soll sichtbar werden, kein stilles Verschlucken).
- Das externe `check-messages.sh` (absoluter Pfad außerhalb Repo) wird nicht gehärtet, da
  es nicht via `git checkout` verschwinden kann und nicht die Fehlerquelle ist.
- Damit eine **laufende** Session vom Fix profitiert, kann ein `/hooks`-Reload bzw.
  Session-Neustart nötig sein (settings.json wird beim Session-Start geladen) — in der
  Validierung zu klären; für neue Sessions greift der Fix sofort.

## Out of Scope

- Keine Änderung an der Logik der 22 Hook-`.py`-Dateien.
- Keine Änderung an `~/.claude/settings.json` (global) oder `.claude/settings.local.json`
  (hat keinen hooks-Block) — der Lockout-Vektor liegt allein in der Repo-`settings.json`.
- Sekundäre Doku-Härtung in `CLAUDE.md` (Issue „Sekundär"): separater Folgeschritt; Wissen
  bereits in Memory `feedback_shared_repo_hook_lockout` gesichert, CLAUDE.md aktuell durch
  Fremd-WIP belegt.
- Schwester-Repos (infra/n8n/website): ggf. via MQ-`broadcast` nach Verifikation informieren —
  nicht Teil dieses Fixes.

## Changelog

- 2026-05-26: Initial spec created (#384)
- 2026-05-26: Adversary VERIFIED; Doku-Korrektur 21→22 Hook-Dateien (`e2e_commit_gate.py` wurde im ursprünglichen Zähl-Grep wegen der Ziffer verschluckt; Invocation-Zahl 24 war stets korrekt)
