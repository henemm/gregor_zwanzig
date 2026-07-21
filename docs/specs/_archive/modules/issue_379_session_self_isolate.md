---
entity_id: issue_379_session_self_isolate
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [hooks, infrastructure, session, worktree, parallel-sessions]
---

<!-- Issue #379 — Session-Wächter: Selbst-Isolierung + Leichen-Bug -->

# Issue 379 — Parallele Sitzungen ohne Neustart selbst-isolieren + Leichen-Bug beheben

## Approval

- [ ] Approved

## Purpose

Der Session-Singleton-Wächter sperrt heute (a) fälschlich die einzige verbliebene
Sitzung aus, wenn eine andere Sitzung *sauber* geschlossen wurde (Leichen-Bug), und
(b) zwingt eine legitime zweite Sitzung zum manuellen Beenden/Neustarten in einem
isolierten Ordner. Beides wird behoben: tote Prozesse gelten sofort als beendet,
und eine zweite Sitzung versetzt sich **selbst** per `EnterWorktree` in eine
isolierte Kopie — ohne Neustart, ohne manuelle Handgriffe.

## Source

> **Schicht-Hinweis:** Reine **Hook-/Tooling-Infrastruktur** (`.claude/hooks/`),
> kein `src/`, kein `frontend/`, kein `api/`/`internal/`. Kein Produktions-Code,
> kein Daten-Schema.

- **File:** `.claude/hooks/session_singleton_guard.py` — `_is_alive()`,
  `_is_rescue_command()`, `_do_guard()`, `_block_message()`
- **File:** `.worktreeinclude` (NEU) — Mitnahme-Liste nicht eingecheckter Dateien
- **File:** `CLAUDE.md` (Abschnitt „Parallele Sessions") — Anweisung zur
  automatischen Selbst-Isolierung
- **Test:** `tests/tdd/test_issue_379_session_self_isolate.py` (NEU)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EnterWorktree` (Claude-Code-Builtin) | Tool | Versetzt die laufende Sitzung in einen isolierten git-Worktree unter `.claude/worktrees/`, Kontext bleibt erhalten |
| `_pid_alive(pid)` | intern | Prüft `/proc/<pid>`-Existenz (Linux) — die zuverlässige Lebend-Quelle |
| `worktree_state_routing` (Spec) | intern | Workflow-Buchführung ist bereits worktree-fähig (zentrales Routing ins Hauptrepo) |
| `.gitignore` | config | `.worktreeinclude` kopiert nur Dateien, die **matchen UND** gitignored sind |

## Implementation Details

### B1 — Leichen-Bug: `_is_alive()` (Problem 1)

Heute (ODER-Logik) hält eine Sitzung für lebend, solange `last_seen` jünger als
`DEFAULT_STALE_SECONDS` (900 s) ist — **auch wenn die PID nachweislich tot ist**.
Dadurch bleibt eine sauber geschlossene Sitzung bis zu 15 Min Inhaber.

```python
def _is_alive(entry: dict, now: float, stale: int) -> bool:
    """Lebend = PID in /proc. Ohne verwertbare PID: last_seen-Fenster (Fallback)."""
    pid = entry.get("pid")
    if isinstance(pid, int):
        # PID ist die zuverlaessige Wahrheit (Linux /proc). Tote PID => tot,
        # unabhaengig von last_seen.
        return _pid_alive(pid)
    last_seen = entry.get("last_seen")
    return isinstance(last_seen, (int, float)) and (now - last_seen) < stale
```

Das `last_seen`-Fenster bleibt nur noch Fallback für Alt-Einträge ohne `pid`.

### B2 — `EnterWorktree` als Rettungsweg (Problem 2)

`_is_rescue_command()` lässt zusätzlich zum bestehenden `gz-workspace`-Bash-Aufruf
das Builtin-Tool `EnterWorktree` durch, damit die blockierte Sitzung sich selbst
isolieren kann:

```python
def _is_rescue_command(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "EnterWorktree":
        return True
    if tool_name != "Bash":
        return False
    # ... bestehende gz-workspace-Logik unverändert ...
```

`ExitWorktree` wird **nicht** freigegeben (würde in den belegten Hauptordner
zurückführen).

### B3 — Worktree-Sitzungen nie blockieren (Endlos-Isolierung verhindern)

`_do_guard()` erlaubt sofort, wenn das aufrufende `cwd` (bzw. die aufgelöste
Repo-Wurzel) innerhalb eines `.claude/worktrees/`-Pfads liegt. Eine bereits
isolierte Sitzung darf sich nicht erneut isolieren oder blockiert werden.

### B4 — Block-Meldung an Claude richten (`_block_message()`)

Die Meldung adressiert künftig **Claude**, nicht den Nutzer: Anweisung, sofort
`EnterWorktree` aufzurufen und danach normal weiterzuarbeiten. Der Nutzer muss
nichts tun. Der Hinweis auf `gz-workspace` bleibt als manueller Ausweg erhalten.

### B5 — `.worktreeinclude` (Konfiguration)

`.gitignore`-Syntax; kopiert nur gematchte **und** gitignorierte Dateien in neue
Worktrees:

```
.env
.claude/validator.env
.claude/settings.local.json
```

`node_modules/` und `.venv/` werden bewusst **nicht** kopiert (per `npm ci` bzw.
`uv` im Worktree neu aufbauen). Die konkrete Dateiliste wird bei der Umsetzung
gegen `.gitignore` verifiziert (nur tatsächlich ignorierte Pfade aufnehmen).

### B6 — `CLAUDE.md`

Abschnitt „Parallele Sessions" um die Regel ergänzen: *Erkennt der Wächter eine
zweite Sitzung, ruft Claude unaufgefordert `EnterWorktree` auf und arbeitet in der
Kopie weiter — kein Neustart.*

## Expected Behavior

- **Input:** PreToolUse-Payload (`session_id`, `cwd`, `tool_name`, `tool_input`);
  Registry-Einträge unter `.claude/.session-locks/<repo_key>/`.
- **Output:** `exit 0` (erlaubt) oder `exit 2` mit Block-Meldung.
- **Side effects:** `_reap_dead()` löscht tote Einträge (jetzt inkl. tote-PID-Leichen).

## Acceptance Criteria

- **AC-1:** Given ein Registry-Eintrag mit einer PID, deren `/proc`-Eintrag nicht
  (mehr) existiert, und einem frischen `last_seen` (< 900 s) / When `_is_alive()`
  ausgewertet wird / Then liefert es `False` (die Leiche gilt als tot).
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Registry-Eintrag mit der PID eines tatsächlich laufenden
  Prozesses (z.B. `os.getpid()` des Testprozesses) / When `_is_alive()` ausgewertet
  wird / Then liefert es `True`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Alt-Eintrag **ohne** `pid`-Feld / When `_is_alive()` mit
  frischem `last_seen` ausgewertet wird / Then `True`; mit `last_seen` älter als
  `stale` / Then `False` (Fallback-Verhalten unverändert).
  - Test: (populated after /tdd-red)

- **AC-4:** Given zwei Registry-Einträge — einer mit toter PID + frischem
  `last_seen`, einer mit lebender PID / When `_reap_dead()` läuft / Then bleibt nur
  der lebende Eintrag übrig, und `_owner_sid()` benennt diesen als Inhaber.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `tool_name == "EnterWorktree"` / When `_is_rescue_command()`
  ausgewertet wird / Then `True` (Selbst-Isolierung ist als Rettungsweg erlaubt).
  - Test: (populated after /tdd-red)

- **AC-6:** Given `tool_name == "ExitWorktree"` / When `_is_rescue_command()`
  ausgewertet wird / Then `False` (kein Rückweg in den belegten Hauptordner).
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein `cwd` innerhalb eines `.claude/worktrees/<name>/`-Pfads und
  ein anderer Inhaber im Hauptrepo / When `_do_guard()` läuft / Then `exit 0`
  (eine isolierte Sitzung wird nie blockiert — keine Endlos-Isolierung).
  - Test: (populated after /tdd-red)

- **AC-8:** Given der bestehende `gz-workspace`-Bash-Rettungsweg / When
  `_is_rescue_command()` mit einem reinen `bash .claude/tools/gz-workspace …`-Aufruf
  ausgewertet wird / Then `True` (Regression-Schutz: bestehendes Verhalten bleibt).
  - Test: (populated after /tdd-red)

- **AC-9:** Given `.worktreeinclude` existiert / When es gelesen wird / Then
  enthält es ausschließlich Pfade, die in `.gitignore` ignoriert sind (kein
  toter Eintrag), und schließt `node_modules/`/`.venv/` aus.
  - Test: (populated after /tdd-red)

## Known Limitations

- **PID-Recycling:** Wird die PID einer toten Sitzung vom OS an einen
  Fremdprozess neu vergeben, hält `_pid_alive()` den Eintrag kurzzeitig für
  lebend (gleiche Eigenschaft wie bisher; selten, da Linux PIDs erst nach
  Wrap-Around recycelt). Bewusst nicht gehärtet, um die Logik einfach/testbar zu
  halten (kein `comm`-Vergleich).
- **Worktree-Basis:** `EnterWorktree` (Default `worktree.baseRef: fresh`) zweigt
  von `origin/<default>` ab — die isolierte Sitzung sieht **nicht** den
  uncommitteten Stand des Hauptordners. Für unabhängige Parallelaufgaben korrekt.
- **Frontend im Worktree:** `node_modules` wird nicht kopiert → einmalig
  `cd frontend && npm ci` nötig.

## Changelog

- 2026-05-25: Initial spec created (Issue #379)
