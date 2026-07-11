# Mini-Spec: fix-1202-worktree-setup

## Ausgangslage
Neue Worktree-Sessions (`EnterWorktree`) bringen kein lauffähiges `.venv` und kein
`frontend/node_modules` mit. Beobachtet in Issue #1202:
- `.venv` (Haupt- und Worktree-Repo) gehört `claude-gregor`, ist für den ausführenden
  User nicht nutzbar (Permission denied) → Backend-Tests brauchten eine isolierte
  Scratchpad-venv als Workaround.
- `frontend/node_modules` fehlt in neuen Worktrees → Playwright-E2E-Läufe brauchten
  einen manuellen, danach wieder entfernten Symlink auf das Hauptrepo.

Beides ist reine Tooling-Reibung (kein Produktbug), kostet aber bei jeder neuen
Worktree-Session Zeit.

## Was ändert sich
- Neuer Hook `.claude/hooks/session_start.py`, registriert unter `SessionStart` in
  `.claude/settings.json` (Pfad ist bereits im globen `~/.claude/settings.json`
  konditional vorgesehen: `[ -f .claude/hooks/session_start.py ] && python3 ...`).
- Der Hook erkennt, ob die aktuelle Session in einem Worktree unter
  `.claude/worktrees/<name>/` läuft (cwd-Präfix-Check).
- Falls ja:
  - `frontend/node_modules` fehlt oder ist kaputt → Symlink auf
    `<hauptrepo>/frontend/node_modules` anlegen (wie bisher manuell gemacht).
  - `.venv` fehlt oder ist für den aktuellen User nicht lesbar/ausführbar → per
    `chown -R $(whoami) .venv` korrigieren, sofern der Prozess das darf; scheitert
    das (kein sudo), Klartext-Hinweis ausgeben statt stillem Fehlschlag.
- Kein Eingriff, wenn die Session NICHT in einem Worktree läuft (Hauptrepo bleibt
  unangetastet).

## Was sich nicht ändern darf
- Produktionscode (`src/`, `internal/`, `frontend/src/`) bleibt unberührt.
- Der Hook darf beim Fehlschlagen die Session nicht blockieren (nur Hinweis
  ausgeben, `exit 0`).
- Keine Änderung an bestehenden Gates/Hooks (`renderer_mail_gate.py` etc.).

## Manuelle Test-Schritte
1. Neuen Worktree per `EnterWorktree` anlegen.
2. Neue Claude-Session dort starten (oder Hook manuell mit
   `python3 .claude/hooks/session_start.py` ausführen).
3. Prüfen: `frontend/node_modules` ist ein gültiger Symlink/Verzeichnis, `.venv`
   ist für den aktuellen User nutzbar (`.venv/bin/python -c "print(1)"` läuft ohne
   Permission-Fehler).
4. Hauptrepo-Session (kein Worktree) starten → Hook greift nicht ein, keine
   Fehlermeldung.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test für: Hook erkennt Worktree-Kontext korrekt (Pfad unter
      `.claude/worktrees/`) und lässt Hauptrepo-Pfade unangetastet.
- [ ] Test für: fehlender `frontend/node_modules`-Symlink wird angelegt, ohne
      bestehende reguläre Verzeichnisse zu überschreiben.
