# Context: fix-930-golden-gate

## Request Summary
Golden-Email-Tests sollen echtes Commit-Gate werden: wenn Renderer-Dateien gestaget sind,
muss `pytest tests/golden/email/` grün sein, sonst blockiert der Commit.

## Kernbefund (tiefere Ursache als im Issue dokumentiert)

Issue #930 sagt: "Golden-Suite ist faktisch kein Gate." Das stimmt — aber die Ursache
ist doppelt:

1. **Goldens waren NICHT in renderer_mail_gate.py eingebaut** — das Gate prüft nur
   Matrix-Test + briefing_mail_validator, keine Golden-Tests.

2. **renderer_mail_gate.py ist selbst tot** — wurde in Commit `ede10a2d`
   ("Veraltete v2-Hooks aus settings.json entfernen") aus der `PreToolUse:Bash`-
   Registrierung entfernt, ohne in den Plugin-Hooks neu registriert zu werden.
   Aktiv ist nur `${CLAUDE_PLUGIN_ROOT}/core/hooks/bash_gate.py` (Plugin-Hook),
   das `renderer_mail_gate.py` nicht aufruft.

Dasselbe gilt für `adr_guard` im Projekt-eigenen `.claude/hooks/bash_gate.py`:
beide Dateien sind vorhanden aber nicht verdrahtet.

## Was zu reparieren ist

| # | Was | Datei | Beschreibung |
|---|-----|-------|-------------|
| 1 | Wiederanschließen | `.claude/settings.json` | `renderer_mail_gate.py` zurück als `PreToolUse:Bash`-Hook |
| 2 | Golden-Check hinzufügen | `.claude/hooks/renderer_mail_gate.py` | Bei gestagten Briefing-Mail-Dateien: `pytest tests/golden/email/` ausführen, bei Fehler blockieren |
| 3 | Regenerations-Skript | `tests/golden/email/regenerate.py` | Einzeiler: Fixtures neu rendern, `.txt`-Dateien überschreiben |

## Related Files

| Datei | Relevanz |
|-------|----------|
| `.claude/hooks/renderer_mail_gate.py` | Kern-Gate — hier kommt der Golden-Check hinein |
| `.claude/settings.json` | Hier kommt die PreToolUse:Bash-Registrierung zurück |
| `tests/golden/email/test_email_html_golden.py` | Definitiert die 5 HTML-Golden-Tests |
| `tests/golden/email/test_email_plain_golden.py` | Definitiert die 5 Plain-Text-Golden-Tests |
| `tests/golden/email/*.txt` | Die eigentlichen Golden-Snapshots (10 Stück, aktuell grün nach #928) |
| `/home/hem/agent-os-openspec/core/hooks/bash_gate.py` | Plugin-bash_gate — ruft renderer_mail_gate.py NICHT auf |
| `/home/hem/agent-os-openspec/hooks/hooks.json` | Plugin-Hook-Registrierung — kein renderer_mail_gate.py-Eintrag |

## Existing Patterns

- **renderer_mail_gate.py Architektur:** `_do_hook()` liest `git diff --cached`, prüft
  ob Mail-Dateien gestaged sind, liest Workflow-State, prüft zwei Nachweise
  (matrix + validator). Bei Fehler: `_block(msg)` → `sys.exit(2)`.
  Die Golden-Check-Logik folgt demselben Muster: `subprocess.run(["uv", "run", "pytest",
  "tests/golden/email/", "-q"])`, Exit != 0 → `_block(...)`.

- **PreToolUse:Bash in settings.json (vorher):**
  ```
  "if [ -f \"${CLAUDE_PROJECT_DIR}/.claude/hooks/renderer_mail_gate.py\" ]; then
    python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/renderer_mail_gate.py\"; fi"
  ```
  → Wird zu direktem Eintrag ohne Shell-Guard (Datei existiert dauerhaft).

- **Scope:** Golden-Check nur bei `briefing_staged` (nicht bei radar-only-Commits),
  analog zum Matrix/Validator-Check (Zeile 294 in renderer_mail_gate.py).

- **Regenerations-Workflow:** Test-Framework-Fixtures sind bereits vollständig in
  `test_email_html_golden.py` und `test_email_plain_golden.py` — Regenerations-Skript
  importiert die gleichen Fixtures und schreibt `.txt` neu.

## Dependencies

- Upstream: `uv`, `pytest`, `tests/golden/email/conftest.py` (friert datetime ein)
- Downstream: Alle Commits, die `src/output/renderers/email/`, `src/formatters/`,
  `src/outputs/email.py` anfassen, werden jetzt auch durch Golden-Check gegated

## Analysis

### Type
Feature (Gate-Erweiterung + Wiederanschluss)

### Betroffene Dateien

| Datei | Änderungstyp | Beschreibung |
|-------|-------------|-------------|
| `.claude/settings.json` | MODIFY | `PreToolUse:Bash`-Block hinzufügen (renderer_mail_gate.py) |
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | `_do_hook()`: `golden_ok`-Check + `missing`-Eintrag |
| `tests/golden/email/regenerate.py` | CREATE | Standalone-Skript: datetime einfrieren, Formatter aufrufen, `.txt`-Dateien schreiben |

### Scope-Abschätzung
- Dateien: 3
- Geschätzte LoC: +~105 / -0
- Risiko-Level: **LOW** — Golden-Tests sind aktuell grün, Gate ist rein additiv

### Technischer Ansatz

**1. settings.json** — `PreToolUse:Bash`-Block hinzufügen:
```json
"PreToolUse": [{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "if [ -f \"${CLAUDE_PROJECT_DIR}/.claude/hooks/renderer_mail_gate.py\" ]; then python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/renderer_mail_gate.py\"; fi",
    "timeout": 60
  }]
}]
```

**2. renderer_mail_gate.py** — Golden-Check in `_do_hook()`, nach dem Matrix/Validator-Block (vor dem `if matrix_ok and validator_ok and radar_ok`):
```python
golden_ok = True
if briefing_staged:
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/golden/email/", "-q", "--no-header", "--tb=no"],
            cwd=repo, capture_output=True, text=True, timeout=60,
        )
        golden_ok = (result.returncode == 0)
    except Exception:
        golden_ok = True  # fail-open bei uv/pytest-Fehler
```
Anpassungen:
- `if matrix_ok and validator_ok and radar_ok and golden_ok` (Zeile 314)
- `if not golden_ok: missing.append(...)` mit Regenerations-Anleitung

**3. tests/golden/email/regenerate.py** — Standalone-Skript das:
- Datetime auf `2026-04-28 12:00:00 UTC` einfriert (kein monkeypatch nötig — direkt patchen)
- Alle 5 Szenarien mit identischen Parametern wie die Tests aufruft
- HTML→`*-html.txt` und Plain→`*-plain.txt` überschreibt

### Konftest-Constraint
`conftest.py` patcht `datetime` via `monkeypatch` in drei Modulen:
- `formatters.trip_report`
- `src.output.renderers.email.plain`
- `src.output.renderers.email.html`

Das Regenerations-Skript muss diese drei Module DIREKT patchen (nicht via pytest).

### TDD RED Tests
Neue Datei: `tests/tdd/test_issue_930_golden_gate.py`
- AC-1: `renderer_mail_gate.py` blockiert Commit wenn Golden-Tests fehlschlagen (bei gestagten Briefing-Mail-Dateien)
- AC-2: `renderer_mail_gate.py` erlaubt Commit wenn Golden-Tests grün sind (alles OK)
- AC-3: `settings.json` hat `PreToolUse:Bash`-Block für renderer_mail_gate.py

Muster: `tests/tdd/test_issue_811_renderer_gate.py` (existiert, zeigt Gate-Test-Pattern)

## Risks & Considerations

1. **Performance:** `pytest tests/golden/email/` braucht ~1s (22 Tests laufen in 0.82s).
   Akzeptabel als Commit-Gate.

2. **Fail-safe:** Wenn `uv` nicht verfügbar oder pytest schlägt mit unerwartetem Fehler
   fehl → Gate sollte fail-open (Exit 0, Warning) wie der ADR-Guard (`pass`-Fallback).

3. **settings.json-Schreibrecht:** Liegt im Projekt unter `.claude/settings.json`.
   Der Harness-Schutz greift nur bei State-Manipulationen via Bash — eine Edit-Operation
   durch den Developer Agent (mit aktivem Workflow) ist erlaubt.

4. **Doppel-Registrierung vermeiden:** renderer_mail_gate.py in settings.json; 
   Plugin-bash_gate.py bleibt unberührt. Kein Eingriff in Plugin-Code.
