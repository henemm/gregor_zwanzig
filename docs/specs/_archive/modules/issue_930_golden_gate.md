---
entity_id: issue_930_golden_gate
type: feature
created: 2026-06-30
updated: 2026-06-30
status: draft
version: "1.0"
tags: [tooling, gate, mail, golden-test, enforcement]
workflow: fix-930-golden-gate
---

# Issue #930 — Golden-Email-Gate: renderer_mail_gate.py reaktivieren + Golden-Test-Check

## Approval

- [ ] Approved

## Purpose

Repariert das tote `renderer_mail_gate.py`-Commit-Gate (wurde in `ede10a2d` aus der
`PreToolUse:Bash`-Registrierung entfernt) und erweitert es um einen Golden-Test-Check:
Ab diesem Fix blockiert jeder Commit, der Mail-Renderer-Dateien staged, solange
`pytest tests/golden/email/` nicht grün ist — womit Golden-Tests erstmals ein echtes
Commit-Gate werden statt wirkungslose Hinweise.

## Source

- **Datei (Änderung):** `.claude/settings.json` — `PreToolUse:Bash`-Block neu hinzufügen
- **Datei (Änderung):** `.claude/hooks/renderer_mail_gate.py` — `_do_hook()` um `golden_ok`-Check erweitern
- **Datei (neu):** `tests/golden/email/regenerate.py` — Standalone-Skript zum Neueinfrieren der Golden-Snapshots
- **Datei (neu):** `tests/tdd/test_issue_930_golden_gate.py` — TDD-Nachweise für das Gate-Verhalten
- **Identifier:** `_do_hook()` in `.claude/hooks/renderer_mail_gate.py`

> **Schicht:** Reines **Tooling** (Hooks + pytest). Kein Eingriff in Frontend-, Go- oder
> produktiven Python-Backend-Code. Der Golden-Check ruft `pytest tests/golden/email/`
> als Subprozess auf — dieselben Tests, die bereits existieren und nach #928 grün sind.

## Estimated Scope

- **LoC:** ~120 (settings.json ~10, renderer_mail_gate.py ~25, regenerate.py ~50, TDD-Tests ~35)
- **Files:** 2 neu, 2 geändert
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/renderer_mail_gate.py` | Hook | Kern-Gate — erhält den neuen Golden-Check |
| `.claude/settings.json` | Config | Registrierung des Gates als PreToolUse:Bash-Hook |
| `tests/golden/email/test_email_html_golden.py` | Test | Definiert die 5 HTML-Golden-Tests die das Gate ausführt |
| `tests/golden/email/test_email_plain_golden.py` | Test | Definiert die 5 Plain-Text-Golden-Tests die das Gate ausführt |
| `tests/golden/email/conftest.py` | Test-Infra | Friert datetime auf `2026-04-28 12:00:00 UTC` ein (muss regenerate.py nachbilden) |
| `subprocess` | stdlib | Gate ruft `uv run pytest` als Subprozess auf |

## Implementation Details

### 1. settings.json — Gate wieder verdrahten

PreToolUse:Bash-Eintrag hinzufügen, der `renderer_mail_gate.py` bei jeder Bash-Tool-Verwendung
aufruft. Das Gate liest selbst `git diff --cached`, ob Mail-Dateien gestaged sind, und ist
ein No-Op wenn nicht:

```
"PreToolUse": [{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/renderer_mail_gate.py\"",
    "timeout": 60
  }]
}]
```

### 2. renderer_mail_gate.py — Golden-Check in _do_hook()

Nach dem bestehenden Matrix/Validator-Block, aber vor der finalen `if matrix_ok and validator_ok
and radar_ok`-Bedingung, wird ein `golden_ok`-Check eingefügt. Scope: nur bei `briefing_staged`
(identisch wie Matrix/Validator-Check), nicht bei radar-only-Commits.

```
golden_ok = True
if briefing_staged:
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/golden/email/", "-q", "--no-header", "--tb=no"],
        cwd=repo, capture_output=True, text=True, timeout=60,
    )
    golden_ok = (result.returncode == 0)
    # Fehler bei uv/pytest selbst → fail-open (golden_ok bleibt True)
```

Anpassungen in der Bedingung:
- `if matrix_ok and validator_ok and radar_ok and golden_ok`
- `if not golden_ok: missing.append("Golden-Tests fehlgeschlagen — uv run pytest tests/golden/email/ ausführen, dann regenerate.py wenn Snapshots veraltet")`

### 3. tests/golden/email/regenerate.py — Snapshot-Regeneration

Standalone-Skript (kein pytest, kein monkeypatch) das:
- Datetime in den drei betroffenen Modulen direkt patcht: `formatters.trip_report`,
  `src.output.renderers.email.plain`, `src.output.renderers.email.html`
- Einfrierzeit: `datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)`
- Alle 5 Szenarien mit identischen Parametern wie `test_email_html_golden.py` /
  `test_email_plain_golden.py` aufruft
- HTML-Ergebnis → `tests/golden/email/*-html.txt`, Plain → `*-plain.txt`
- Überschreibt die bestehenden Snapshot-Dateien in-place

Aufruf: `uv run python3 tests/golden/email/regenerate.py`

### 4. tests/tdd/test_issue_930_golden_gate.py — TDD-Nachweise

Drei Tests die Gate-Verhalten ohne pytest-Tricks nachweisen:

- AC-1-Test: Echtes Temp-Git-Repo, Mail-Datei stagen, Golden-Snapshot manipulieren
  (ungültig machen), `renderer_mail_gate.py` als Subprozess mit git-commit-stdin → Exit 2
- AC-2-Test: Wie AC-1, aber Golden-Snapshots korrekt → Gate lässt durch (Exit 0)
- AC-3-Test: `settings.json` auf PreToolUse:Bash-Eintrag prüfen
  (doc-compliance-test, markiert mit `# doc-compliance-test`)

## Expected Behavior

- **Input:** Commit-Versuch, der eine Mail-Inhalts-Datei staged; aktiver Workflow-State.
- **Output:** Exit 0 (Gate lässt durch, alle Nachweise frisch und Golden grün) ODER
  Exit 2 + stderr mit konkreter Abhilfe-Anleitung (welcher Nachweis fehlt).
- **Side effects:** Kein Schreiben in Workflow-State (Golden-Check ist zustandslos,
  anders als Matrix-Nachweis). `regenerate.py` überschreibt `tests/golden/email/*.txt`.

## Acceptance Criteria

- **AC-1:** Given ein Commit der `src/output/renderers/email/*.py`, `src/formatters/*.py`
  oder `src/outputs/email.py` staged / When mindestens ein Golden-Snapshot in
  `tests/golden/email/` nicht mehr mit dem Renderer-Output übereinstimmt / Then blockiert
  `renderer_mail_gate.py` den Commit mit Exit 2 und gibt eine Anleitung aus, wie die
  Snapshots mit `regenerate.py` neu eingefroren werden.
  - Test: `tests/tdd/test_issue_930_golden_gate.py::test_gate_blocks_on_golden_failure` —
    Temp-Git-Repo, Mail-Datei stagen, einen Snapshot korrumpieren, Gate als Subprozess
    aufrufen → Exit 2.

- **AC-2:** Given ein Commit der Mail-Renderer-Dateien staged / When alle Golden-Tests
  in `tests/golden/email/` grün sind und Matrix-Test sowie briefing_mail_validator-Nachweis
  vorliegen / Then lässt `renderer_mail_gate.py` den Commit durch (Exit 0).
  - Test: `tests/tdd/test_issue_930_golden_gate.py::test_gate_passes_on_golden_success` —
    Temp-Git-Repo, Mail-Datei stagen, alle Nachweise korrekt hinterlegen, Gate aufrufen → Exit 0.

- **AC-3:** Given das Projekt-Repository / When `.claude/settings.json` gelesen wird / Then
  existiert ein `PreToolUse:Bash`-Hook-Eintrag, der `renderer_mail_gate.py` aufruft — sodass
  das Gate bei jedem Commit-Versuch im laufenden Workflow aktiv ist.
  - Test: `tests/tdd/test_issue_930_golden_gate.py::test_settings_json_has_preToolUse_hook`
    — `# doc-compliance-test`, liest `.claude/settings.json` und prüft Vorhandensein des
    Hook-Eintrags.

## Known Limitations

- Golden-Check ist **fail-open** wenn `uv` nicht gefunden wird oder pytest selbst abstürzt —
  um nicht bei infrastrukturellen Problemen Commits zu blockieren. Beabsichtigt und analog
  zum ADR-Guard-Fallback.
- Golden-Check läuft nur bei `briefing_staged`; Radar-Alert-only-Commits sind nicht betroffen
  (Radar-Renderer nutzt keinen HTML-Formatter).
- `regenerate.py` muss nach jeder absichtlichen Renderer-Änderung manuell ausgeführt werden
  (kein automatisches Neueinfrieren im Gate-Pfad — bewusste Entscheidung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Gate-Erweiterung; keine neue Architektur-Richtung. Der Fail-Open-Ansatz
  bei uv/pytest-Infrastrukturfehlern folgt dem bestehenden ADR-Guard-Muster (kein neuer ADR nötig).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/settings.json` | MODIFY | PreToolUse:Bash-Block hinzufügen (renderer_mail_gate.py) |
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | golden_ok-Check in _do_hook() + missing-Eintrag |
| `tests/golden/email/regenerate.py` | CREATE | Standalone-Snapshot-Regenerationsskript |
| `tests/tdd/test_issue_930_golden_gate.py` | CREATE | TDD-Nachweise für AC-1, AC-2, AC-3 |

### Estimated Changes

- Files: 4
- LoC: +~120 / -0

## Changelog

- 2026-06-30: Initial spec created
