---
entity_id: session_singleton_guard
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [hooks, infrastructure, workflow, session-isolation]
---

<!-- Session-Singleton-Wächter — verhindert parallele Claude-Sitzungen im selben Repo -->

# Session-Singleton-Guard

## Approval

- [ ] Approved

## Purpose

Verhindert, dass mehr als eine Claude-Sitzung gleichzeitig im selben
Arbeitsverzeichnis (Repo-Wurzel) produktiv arbeitet. Genau diese Mehrfach-Nutzung
hat zum aktuellen Chaos geführt: uncommittete Arbeit aus mehreren Aufgaben
vermischt sich, Workflow-Buchführung kollidiert. Die etablierte Lösung
(`gz-workspace` für Parallelarbeit, siehe CLAUDE.md "Parallele Sessions") war bisher
nur eine Konvention ohne technische Durchsetzung. Dieser Wächter erzwingt sie:
Eine zweite, jüngere Sitzung im selben Repo wird hart blockiert, bis sie in einen
eigenen Arbeitsordner wechselt.

## Source

- **File:** `.claude/hooks/session_singleton_guard.py` (NEU, ~140 LoC) — zwei Modi:
  `register` (SessionStart) und `guard` (PreToolUse, catch-all). Eigenständiger Hook,
  keine Änderung an bestehenden Gates.
- **File:** `.claude/settings.json` (ERWEITERT, ~12 Zeilen) — `register` an `SessionStart`
  anhängen (additiv neben `check-messages.sh`); neuen `PreToolUse`-Block mit leerem
  Matcher (alle Tools) für `guard`.
- **File:** `tests/tdd/test_session_singleton_guard.py` (NEU) — echte tmpdir-basierte
  Tests, KEINE Mocks (Dateisystem + Subprozess-Aufrufe des realen Hooks).

> **Schicht-Hinweis:** Reines Hook-/Workflow-Tooling im `.claude/`-Bereich. Kein
> Produkt-Code (src/, frontend/, internal/). Nicht in `protected_paths` → kein
> Spec-Enforcement-Zwang, dennoch Spec für sauberes Adversary-Ziel.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pathlib.Path` | stdlib | Registry-Dateien lesen/schreiben |
| `json` | stdlib | stdin-Payload + Registry-Einträge |
| `subprocess` / `/proc` | stdlib/OS | git-Toplevel-Auflösung + PID-Liveness |
| `gz-workspace` | tool | Rettungsweg, den eine blockierte Sitzung weiterhin ausführen darf |

## Implementation Details

### Registry-Layout
`.claude/.session-locks/<repo-key>/<session_id>.json` mit
`{session_id, cwd, repo_root, pid, started_at, last_seen}`.
- `<repo-key>` = Hash bzw. sicherer Slug der **git-Repo-Wurzel** des cwd
  (`git rev-parse --show-toplevel`, Fallback: nächstes `.git` nach oben, sonst cwd).
  Damit kollidieren Sitzungen aus Unterordnern desselben Repos, aber NICHT
  Sitzungen in separaten `gz-workspace`-Klonen (eigenes `.git`).
- Verzeichnis wird in `.gitignore` aufgenommen (lokaler Laufzeitzustand).

### Modus `register` (SessionStart)
1. session_id, cwd aus stdin-Payload lesen; repo_root + repo-key bestimmen.
2. Abgelaufene Einträge im repo-key-Ordner aufräumen (PID tot **und** last_seen
   älter als `STALE_SECONDS`).
3. Eigenen Eintrag schreiben (`pid` = `os.getppid()`, `started_at` = `last_seen` = jetzt).

### Modus `guard` (PreToolUse, alle Tools)
1. session_id, cwd, tool_name, tool_input aus stdin-Payload lesen.
2. **Übergangsschutz:** Existiert KEIN eigener Registry-Eintrag (Sitzung lief vor
   Hook-Einführung, kein SessionStart durchlaufen) → **erlauben** (exit 0).
3. Heartbeat: eigenen `last_seen` aktualisieren.
4. Lebende Sitzungen im repo-key ermitteln. „Lebend" = PID in `/proc` vorhanden
   **oder** (Fallback) `last_seen` jünger als `STALE_SECONDS`.
5. Inhaber = lebende Sitzung mit kleinstem `started_at` (Tie-Break: session_id
   lexikografisch kleiner).
6. Eigene Sitzung == Inhaber → **erlauben**.
7. Sonst Rettungsweg-Prüfung: `tool_name == "Bash"` und das Kommando ist ein
   reiner `gz-workspace`-Aufruf (Regex auf Anfang, keine Shell-Metazeichen
   `;`, `&&`, `||`, `|`, `$(`, Backtick) → **erlauben**.
8. Andernfalls → **blockieren** (exit 2, deutsche Meldung mit Anleitung auf stderr).

### Fail-safe (oberste Regel)
Jeder unerwartete Zustand erlaubt: leerer/unparsebarer Payload, fehlendes cwd,
IO-Fehler an der Registry, git-Auflösung schlägt fehl, Exception irgendwo →
`sys.exit(0)`. Der Wächter darf **niemals** eine Sitzung fälschlich blockieren.

### Konstanten
`STALE_SECONDS` (Default 900) konfigurierbar über `openspec.yaml`-Schlüssel bzw.
ENV `GZ_SESSION_STALE_SECONDS`. Registry-Pfad relativ zum repo_root.

## Expected Behavior

- **Input:** stdin-Payload von Claude Code (`session_id`, `cwd`, `tool_name`,
  `tool_input`).
- **Output:** Exit 0 (erlauben, ggf. Heartbeat-Schreibvorgang) oder Exit 2 mit
  deutscher Blockmeldung auf stderr.
- **Side effects:** Anlegen/Aktualisieren/Aufräumen von Registry-Dateien unter
  `.claude/.session-locks/`.

## Acceptance Criteria

- **AC-1:** Given ein leeres Repo ohne Registry-Einträge / When sich Sitzung A per
  `register` einträgt und danach einen beliebigen Tool-Aufruf über `guard` schickt /
  Then erlaubt der Wächter (exit 0) — A ist alleiniger Inhaber.
  - Test: (populated after /tdd-red)

- **AC-2:** Given Sitzung A ist als lebender Inhaber registriert / When eine jüngere
  Sitzung B (späteres started_at) sich registriert und einen Edit-/Write-/Bash-Aufruf
  über `guard` schickt / Then blockiert der Wächter B (exit 2) mit deutscher Anleitung
  zum Anlegen eines eigenen Arbeitsordners.
  - Test: (populated after /tdd-red)

- **AC-3:** Given Sitzung B ist als Nicht-Inhaber blockiert / When B einen reinen
  `gz-workspace`-Aufruf als Bash-Kommando schickt / Then erlaubt der Wächter (exit 0),
  damit der Rettungsweg offen bleibt; ein verkettetes Kommando (`gz-workspace … ; rm …`)
  wird hingegen blockiert.
  - Test: (populated after /tdd-red)

- **AC-4:** Given zwei Sitzungen mit cwd in verschiedenen git-Repos (unterschiedliche
  Toplevel, z.B. Hauptrepo und ein gz-workspace-Klon) / When beide registriert sind und
  Tool-Aufrufe schicken / Then erlaubt der Wächter beide (exit 0) — kein Repo-übergreifender
  Block.
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine Sitzung hat KEINEN eigenen Registry-Eintrag (lief vor Einführung
  des Hooks, kein SessionStart) / When sie einen beliebigen Tool-Aufruf über `guard`
  schickt / Then erlaubt der Wächter immer (exit 0) — laufende Bestands-Sitzungen werden
  nie abgewürgt.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein fehlerhafter Zustand (leerer stdin-Payload, kaputtes JSON,
  nicht beschreibbare Registry, fehlendes cwd) / When `guard` aufgerufen wird / Then
  erlaubt der Wächter (exit 0) und wirft keine Exception nach außen — Fail-safe.
  - Test: (populated after /tdd-red)

- **AC-7:** Given Inhaber A ist nicht mehr am Leben (PID nicht in `/proc` und last_seen
  älter als STALE_SECONDS) / When die verbliebene Sitzung B `guard` aufruft / Then wird
  B neuer Inhaber und der Wächter erlaubt (exit 0); A's veralteter Eintrag wird aufgeräumt.
  - Test: (populated after /tdd-red)

- **AC-8:** Given der `register`-Hook wird von Claude Code über einen kurzlebigen
  Wrapper-Prozess gestartet (sodass `os.getppid()` NICHT die langlebige Sitzung trifft) /
  When eine Sitzung sich registriert / Then speichert der Eintrag die echte
  Claude-Sitzungs-PID (ermittelt durch Hochlaufen der Eltern-Prozesskette bis zum
  `claude`-Prozess), damit `_pid_alive` eine geschlossene Sitzung SOFORT als tot erkennt
  und ihren Inhaber-Anspruch nicht bis zum STALE-Fenster (Default 900 s) blockiert.
  Fail-safe: schlägt die Ermittlung fehl, wird auf `os.getppid()` zurückgefallen.
  - Test: (populated after /tdd-red)

## Known Limitations

- Greift nur für Sitzungen, die nach Einführung des Hooks **neu gestartet** werden
  (Hooks werden beim Sitzungsstart geladen; AC-5 schützt Bestands-Sitzungen bewusst).
  Das aktuelle akute Chaos (6 laufende Sitzungen) wird dadurch nicht rückwirkend
  aufgelöst — das ist gewollt und mit dem PO abgestimmt ("erst nur die Sperre").
- Eine länger idle, aber offen gelassene Inhaber-Sitzung hält ihren Anspruch bis
  STALE_SECONDS bzw. PID-Tod. Bewusster Trade-off zugunsten Fail-safe.
- PID-Liveness nutzt `/proc` (Linux); auf Nicht-Linux greift nur der
  Heartbeat-Fallback. Für diese Server-Umgebung (Ubuntu) ausreichend.

## Changelog

- 2026-05-25: Initial spec created (Sperre gegen parallele Sitzungen im selben Repo)
- 2026-05-25: AC-8 ergänzt — echte Sitzungs-PID via Eltern-Prozesskette statt
  `os.getppid()` (Bugfix: getppid traf nur den kurzlebigen Wrapper → tote Sitzungen
  blockierten bis STALE-Fenster statt sofort freizugeben)
</content>
</invoke>
