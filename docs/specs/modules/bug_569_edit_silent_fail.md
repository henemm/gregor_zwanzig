---
entity_id: bug_569_edit_silent_fail
type: module
created: 2026-06-03
updated: 2026-06-03
status: draft
version: "1.0"
tags: [harness, bug, hooks]
---

# PostToolUse Edit-Verifikation (Bug #569)

## Approval

- [ ] Approved

## Purpose

Ein PostToolUse-Hook für `Edit|Write`, der nach jedem File-Edit prüft ob `new_string` tatsächlich in der Datei steht. Bei Misserfolg (stille Falschmeldung des Edit-Tools) wird eine klare Fehlermeldung in das Tool-Ergebnis eingefügt, damit Claude das Fehlschlagen erkennt statt weiterzumachen.

## Source

- **File:** `.claude/hooks/edit_verify.py`
- **Identifier:** `main()`

## Estimated Scope

- **LoC:** ~70
- **Files:** 2 (neuer Hook + settings.json)
- **Effort:** low

## Dependencies

- `.claude/settings.json` — PostToolUse-Hook-Eintrag für `Edit|Write`
- `.claude/hooks/` — Hook-Verzeichnis

## Acceptance Criteria

**AC-1:** Given ein Edit/Write-Tool-Call mit `new_string` auf eine existierende Datei / When der Hook nach dem Tool-Call läuft / Then liest er die Zieldatei und prüft ob `new_string` darin vorkommt — bei Erfolg: kein Output, exit 0.

**AC-2:** Given ein Edit-Tool-Call dessen Änderung NICHT auf der Platte gelandet ist (stille Falschmeldung) / When der Hook prüft / Then gibt er auf stdout eine klare Fehlermeldung aus (sichtbar als Tool-Ergebnis-Annotation für Claude) und beendet sich mit exit 0 (kein Block, nur Warnung).

**AC-3:** Given ein Write-Tool-Call mit `content`-Parameter / When der Hook prüft / Then liest er die ersten 200 Zeichen des `content`-Strings und prüft ob dieser Prefix in der Datei vorkommt — gleiche Logik wie AC-1/AC-2.

**AC-4:** Given der Hook kann die Datei nicht lesen (z.B. Berechtigungsfehler, Binary-Datei) / When ein OSError oder UnicodeDecodeError auftritt / Then beendet er sich mit exit 0 ohne Fehlermeldung (fail-open, kein false positive).

**AC-5:** Given ein Edit/Write auf eine `.py`-, `.go`-, `.ts`-, `.svelte`- oder `.md`-Datei im Worktree-Kontext / When der Hook die Verifikation durchführt / Then nutzt er den absoluten Pfad aus `tool_input.file_path` direkt (keine Pfad-Neu-Auflösung via `get_project_root()`).

**AC-6:** Given `tool_input` enthält keinen `file_path`, kein `new_string` und kein `content` / When der Hook läuft / Then beendet er sich sofort mit exit 0 (kein false positive für Tool-Calls ohne Datei-Output).

## Implementation Notes

- **Kein Block** — Hook gibt immer exit 0. Ziel ist SICHTBARKEIT, nicht Blockieren.
- **Prüf-Logik:** `new_string` → suche exakten Substring in Datei-Inhalt. Bei Write: erste 200 Zeichen von `content`.
- **Payload-Quelle:** `stdin` (JSON) → `tool_input` Objekt mit `file_path`, `new_string` (Edit) oder `content` (Write).
- **PostToolUse JSON-Format:** `{"tool_name": "Edit", "tool_input": {...}, "tool_response": {...}}` — Hook liest aus `tool_input`.
- **settings.json Eintrag:** PostToolUse Matcher `Edit|Write`, neuer Hook-Eintrag nach `auto_restart_server.py`.
- **Fail-open:** Jeder unerwartete Fehler → exit 0 (konsistent mit anderen Hooks via `if [ -f ... ]`-Wrapper).
