---
entity_id: epic_191_zeilenlimit
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [hooks, workflow, scope-guard, loc-limit]
---

<!-- Issue #195 — Epic #191: LoC-Delta-Limit (Workflow D) -->

# Epic 191 — Zeilenlimit (Workflow D)

## Approval

- [ ] Approved

## Purpose

`scope_guard.py` wird um einen LoC-Delta-Check erweitert, der bei einem
Code-Edit die Summe der Insertions und Deletions aus `git diff HEAD
--numstat` gegen ein konfigurierbares Limit (Default 250) prüft und bei
Überschreitung mit Exit 2 blockiert. Damit wird verhindert, dass ein
einzelner Bearbeitungsschritt unkontrolliert viele Zeilen verändert; der
Override-Mechanismus über `loc_limit_override` im Workflow-State erlaubt
begründete Ausnahmen ohne Hook-Bypass.

## Source

- **File:** `.claude/hooks/scope_guard.py` — neue Funktionen `_get_loc_delta()` und `_check_loc_delta()`
- **File:** `.claude/hooks/workflow.py` — `cmd_status` zeigt Delta + speichert `loc_delta_current`
- **File:** `.claude/hooks/config_loader.py` — Helper `get_scope_loc_config()`
- **File:** `openspec.yaml` — `scope_guard.max_loc_delta: 250` + `scope_guard.loc_exclude_patterns: [...]`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `subprocess` | stdlib | `git diff HEAD --numstat` aufrufen |
| `re` | stdlib | Exclude-Pattern gegen Dateipfade matchen |
| `config_loader.load_config()` | bestehend | Konfiguration aus `openspec.yaml` laden |
| `epic_191_state_migration` Spec (`docs/specs/modules/epic_191_state_migration.md`) | Vorgänger-Spec | Workflow A — Issue #192; Worktree-Routing, State-Schema, `set-field`-API |
| `epic_191_logbuch_audit` Spec (`docs/specs/modules/epic_191_logbuch_audit.md`) | Vorgänger-Spec | Workflow B — Issue #193; Logbuch-Pflicht, `workflow.py status`-Output-Format |

## Implementation Details

### `openspec.yaml` Erweiterung

Neue Konfigurations-Sektion unter dem bestehenden `scope_guard`-Key:

```yaml
scope_guard:
  max_loc_delta: 250
  loc_exclude_patterns:
    - "\\.xcstrings$"
    - "\\.po$"
    - "package-lock\\.json$"
    - "uv\\.lock$"
    - "yarn\\.lock$"
    - "Cargo\\.lock$"
    - "/_archive/"
    - "/_log/"
    - "/.claude/workflows/"
```

### `config_loader.py` Helper (~12 LoC)

```python
def get_scope_loc_config() -> dict:
    """Returns dict with 'max_loc_delta' and 'loc_exclude_patterns'."""
    config = load_config()
    sg = config.get("scope_guard", {})
    return {
        "max_loc_delta": sg.get("max_loc_delta", 250),
        "loc_exclude_patterns": sg.get("loc_exclude_patterns", []),
    }
```

### `scope_guard.py` Erweiterung (~80 LoC)

Neue Funktion `_get_loc_delta(exclude_patterns)`:

```python
def _get_loc_delta(exclude_patterns: list[str]) -> tuple[int, list[str]]:
    """Run git diff HEAD --numstat, sum insertions+deletions for non-excluded files.

    Returns (total_delta, list_of_counted_files).
    Excluded files (matching any pattern) are NOT counted.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--numstat"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return 0, []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0, []

    total = 0
    counted = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dels, path = parts[0], parts[1], parts[2]
        # Binary files show "-" — skip
        if ins == "-" or dels == "-":
            continue
        # Check exclude
        if any(re.search(p, path) for p in exclude_patterns):
            continue
        total += int(ins) + int(dels)
        counted.append(path)
    return total, counted
```

Neue Funktion `_check_loc_delta(workflow_state)`:

```python
def _check_loc_delta(workflow_state: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Reads from openspec.yaml + workflow state."""
    config = get_scope_loc_config()
    max_delta = workflow_state.get("loc_limit_override") or config["max_loc_delta"]
    delta, counted = _get_loc_delta(config["loc_exclude_patterns"])

    if delta > max_delta:
        return False, (
            f"LoC delta {delta} exceeds limit {max_delta} "
            f"({len(counted)} files counted). "
            f"To override: workflow.py set-field loc_limit_override <higher>"
        )
    return True, f"LoC delta ok: {delta}/{max_delta}"
```

Integration in `main()` — nach dem bestehenden Path-Scope-Check, vor `allow()`:

```python
loc_ok, loc_reason = _check_loc_delta(workflow_state_or_empty_dict)
if not loc_ok:
    print(f"BLOCKED: {loc_reason}", file=sys.stderr)
    sys.exit(2)
```

### `workflow.py` cmd_status Erweiterung (~5 LoC)

Neue Zeile am Ende des Status-Outputs; liest Delta live aus `_get_loc_delta()`:

```python
from scope_guard import _get_loc_delta
from config_loader import get_scope_loc_config
config = get_scope_loc_config()
delta, _ = _get_loc_delta(config["loc_exclude_patterns"])
override = data.get("loc_limit_override")
limit = override or config["max_loc_delta"]
print(f"LoC-Delta: +{delta}/{limit}" + (" (override)" if override else ""))
```

State-Field `loc_delta_current` wird optional gespeichert (für späteren Log).

### Override-Mechanismus

Über die bestehende `set-field`-API aus `epic_191_state_migration`:

```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 500
```

`set-field` muss numerische Werte als `int` akzeptieren. Falls der aktuelle
Stand nur Strings speichert, wird die Typ-Behandlung in `set-field` erweitert
(numerische Strings werden zu `int` konvertiert).

## Acceptance Criteria

- **AC-1:** Given ein Workflow mit Default-Limit 250 / When `git diff HEAD --numstat` zeigt 300 Zeilen-Änderung an Nicht-exkludierten Dateien / Then blockiert `scope_guard.py` den Edit mit Exit 2 und Meldung "LoC delta 300 exceeds limit 250"

- **AC-2:** Given ein Workflow mit `loc_limit_override: 500` im State / When der aktuelle Delta 400 LoC beträgt / Then erlaubt `scope_guard.py` den Edit ohne Blockierung (Override greift statt Default)

- **AC-3:** Given `loc_exclude_patterns` enthält `\\.xcstrings$` / When eine `.xcstrings`-Datei mit 1000 geänderten Zeilen im Diff erscheint / Then zählt diese Datei NICHT zum Delta und hat keinen Einfluss auf die Limit-Prüfung

- **AC-4:** Given `git diff HEAD --numstat` schlägt fehl (kein git-Repo, Timeout oder fehlende Binary) / When der Hook läuft / Then liefert `_get_loc_delta()` das Tupel `(0, [])` und der Edit wird erlaubt (fail-soft, kein Crash)

- **AC-5:** Given `workflow.py status` läuft und der aktuelle Delta beträgt 80 LoC bei Limit 250 / When die Statusausgabe erzeugt wird / Then enthält sie die Zeile `LoC-Delta: +80/250` ohne "(override)"-Suffix

- **AC-6:** Given `workflow.py status` läuft und `loc_limit_override: 500` ist gesetzt / When die Statusausgabe erzeugt wird / Then enthält sie die Zeile `LoC-Delta: +N/500 (override)` mit "(override)"-Suffix

- **AC-7:** Given `openspec.yaml` enthält keinen `scope_guard.max_loc_delta`-Key / When `get_scope_loc_config()` aufgerufen wird / Then liefert es `{"max_loc_delta": 250, "loc_exclude_patterns": []}` (Defaults ohne Fehler)

- **AC-8:** Given `git diff HEAD --numstat` enthält eine Binär-Datei (Anzeige `-` statt Zahlen) / When `_get_loc_delta()` diese Zeile verarbeitet / Then wird die Datei übersprungen ohne Exception (kein `int("-")`-Crash)

- **AC-9:** Given ein Code-Edit betrifft ausschließlich Dateien die in `loc_exclude_patterns` gelistet sind / When der Gesamt-Delta dieser Dateien das Limit überschreiten würde / Then ist der Edit erlaubt weil der gezählte Delta nach Exklusion 0 beträgt

## Expected Behavior

- **Input:** Code-Edit-Operation, git-Repo mit modified files im Working Tree, `openspec.yaml` mit optionalem `scope_guard`-Block
- **Output:** Bool (allow/block) plus lesbarer Meldungsstring; bei Block Exit 2 mit Fehlermeldung auf stderr
- **Side effects:** Keine — reiner Read-Only-Check via `git diff`; kein Schreiben in State, keine Netzwerk-Zugriffe

## Known Limitations

- `git diff HEAD --numstat` zeigt nur tracked files mit Änderungen gegenüber HEAD. Neue untracked Dateien (noch nicht gestaged) werden nicht gezählt — bei großen neuen Dateien (z.B. neuer Test mit 500 LoC) kann das Limit umgangen werden, bis die Datei gestaged ist.
- Timeout 10s für den git-Subprocess. Bei extrem großen Repos potenziell zu kurz; für die aktuelle Größenordnung dieses Projekts akzeptabel.
- `loc_limit_override` wirkt global für den gesamten Workflow-State, nicht pro Datei oder per Phase. Bewusst einfach gehalten.
- `_get_loc_delta()` wird bei jedem `workflow.py status`-Aufruf live ausgeführt. Bei häufigen Status-Calls in CI kann dies zu mehrfachen git-Subprocess-Starts führen — kein funktionelles Problem, da read-only.

## Changelog

- 2026-05-11: Initial spec erstellt — Issue #195, Epic #191. Baut auf epic_191_state_migration (#192) und epic_191_logbuch_audit (#193) auf.
