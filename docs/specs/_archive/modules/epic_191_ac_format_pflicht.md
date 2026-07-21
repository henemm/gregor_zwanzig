---
entity_id: epic_191_ac_format_pflicht
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [hooks, workflow, spec-validation, acceptance-criteria]
---

<!-- Issue #194 — Epic #191: AC-N Format Enforcement (Workflow C) -->

# Epic 191 — AC-Format-Pflicht (Workflow C)

## Approval

- [ ] Approved

## Purpose

Neue Specs (erstellt ab Stichtag `2026-05-11`) müssen eine
`## Acceptance Criteria`-Sektion mit mindestens einem `AC-N`-Eintrag im
Given/When/Then-Format enthalten. Die Pflicht wird in zwei Stufen
durchgesetzt: ein Soft-Check im `spec-validator`-Agent (Phase 3, vor
User-Approval) erzeugt ein INVALID-Verdict, ein Hard-Block in
`workflow_gate.py` (Phase 6, Code-Edit) beendet mit Exit 2. 164
Bestands-Specs bleiben über eine Stichtagsregel grandfathered.

## Source

- **File:** `.claude/hooks/workflow_gate.py` — Hard-Block in `phase6_implement` via `_spec_has_valid_ac_format()`
- **File:** `.claude/hooks/config_loader.py` — Helper `get_ac_format_required_since()`
- **File:** `openspec.yaml` — Konfig-Key `spec_validation.ac_format_required_since`
- **File:** `.claude/agents/spec-validator.md` — Soft-Check Doku (neue Sektion 5)
- **File:** `docs/specs/_template.md` — Template um AC-N-Beispielsektion erweitert

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `re` | stdlib | Regex für `AC-\d+`-Match und Frontmatter-Parsing |
| `pathlib.Path` | stdlib | Spec-Datei lesen |
| Frontmatter-Parser | inline (Regex) | YAML zwischen `---`-Linien parsen — kein PyYAML nötig für diesen Use-Case |
| `config_loader.load_config()` | bestehend | Stichtag aus `openspec.yaml` lesen |
| `epic_191_state_migration` Spec (`docs/specs/modules/epic_191_state_migration.md`) | Vorgänger-Spec | Workflow A — Issue #192; Worktree-Routing bleibt erhalten, keine Kollision |
| `epic_191_logbuch_audit` Spec (`docs/specs/modules/epic_191_logbuch_audit.md`) | Vorgänger-Spec | Workflow B — Issue #193; Logbuch-Pflicht bleibt erhalten, kein Overlap |

## Implementation Details

### `openspec.yaml` Erweiterung

Eine neue Konfigurations-Sektion:

```yaml
spec_validation:
  ac_format_required_since: "2026-05-11"  # Stichtag — Specs mit created >= diesem Datum müssen AC-N nutzen
```

### `config_loader.py` Helper (~10 LoC)

```python
def get_ac_format_required_since() -> str | None:
    """Returns Stichtag-Datum (YYYY-MM-DD) oder None wenn nicht konfiguriert."""
    config = load_config()
    return config.get("spec_validation", {}).get("ac_format_required_since")
```

### `workflow_gate.py` Erweiterung (~40 LoC)

Neue Hilfsfunktion:

```python
def _spec_has_valid_ac_format(spec_path: Path, stichtag: str | None) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    - Wenn kein Stichtag konfiguriert oder Spec fehlt: valid (Legacy).
    - Wenn Spec created < Stichtag: valid (grandfathered).
    - Wenn Spec created >= Stichtag: muss `## Acceptance Criteria` + min. 1 AC-N enthalten.
    """
    if not stichtag or not spec_path.exists():
        return True, "no stichtag configured or spec missing"

    content = spec_path.read_text()

    # Frontmatter created lesen
    fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return True, "no frontmatter — legacy assumption"
    fm = fm_match.group(1)
    created_match = re.search(r'^created:\s*(\d{4}-\d{2}-\d{2})', fm, re.MULTILINE)
    if not created_match:
        return True, "no created field — legacy assumption"

    if created_match.group(1) < stichtag:
        return True, f"legacy spec (created {created_match.group(1)} < {stichtag})"

    # Neue Spec — AC-Section + min. 1 AC-N pflicht
    if "## Acceptance Criteria" not in content:
        return False, f"new spec (created {created_match.group(1)}) missing `## Acceptance Criteria` section"

    # Mindestens 1 AC-N mit nicht-trivialem Inhalt (>=30 Zeichen)
    ac_entries = re.findall(r'\*\*AC-\d+:\*\*[^\n]{30,}', content)
    if not ac_entries:
        return False, "new spec needs at least one `**AC-N:**` entry with >=30 chars description"

    return True, f"AC-format ok ({len(ac_entries)} criteria)"
```

Aufruf vor Phase-Block-Logik (wenn Phase = `phase6_implement` und Edit auf Code-Datei):

```python
if state.get("current_phase") == "phase6_implement" and state.get("spec_file"):
    spec_path = get_project_root() / state["spec_file"]
    stichtag = get_ac_format_required_since()
    ok, reason = _spec_has_valid_ac_format(spec_path, stichtag)
    if not ok:
        print(f"BLOCKED: Spec format violation — {reason}", file=sys.stderr)
        print(f"Spec: {state['spec_file']}", file=sys.stderr)
        print("Add `## Acceptance Criteria` with `**AC-N:**` Given/When/Then entries.", file=sys.stderr)
        sys.exit(2)
```

### `.claude/agents/spec-validator.md` Erweiterung

Neue Sektion nach Sektion 4 "Consistency" (vor "Approval Status"):

```markdown
### 5. Acceptance-Criteria-Format (für neue Specs)

If frontmatter `created >= ac_format_required_since` (read from openspec.yaml):

REQUIRED:
- [ ] Section `## Acceptance Criteria` present
- [ ] At least one `**AC-N:**` entry where N is a positive integer
- [ ] Each AC-entry contains >=30 chars (Given/When/Then template recommended)

Flag as ERROR:
- Missing `## Acceptance Criteria` section
- Section present but no `AC-N` entries
- AC-entries are placeholders or too short

Legacy specs (created < stichtag) skip this check.
```

### `docs/specs/_template.md` Erweiterung

Neue Sektion nach "Expected Behavior":

```markdown
## Acceptance Criteria

- **AC-1:** Given <precondition> / When <action> / Then <observable outcome>
  - Test: (populated after /tdd-red)

- **AC-2:** Given <precondition> / When <action> / Then <observable outcome>
  - Test: (populated after /tdd-red)
```

## Acceptance Criteria

- **AC-1:** Given eine neue Spec mit `created: 2026-05-15` ohne `## Acceptance Criteria`-Sektion / When ein Code-Edit in `phase6_implement` versucht wird / Then blockiert `workflow_gate` mit Exit 2 und klarer Fehlermeldung "BLOCKED: Spec format violation"

- **AC-2:** Given eine neue Spec mit `## Acceptance Criteria`-Sektion aber ohne `**AC-N:**`-Einträge (oder nur Einträge mit <30 Zeichen) / When ein Code-Edit versucht wird / Then blockiert `workflow_gate` mit "needs at least one `**AC-N:**` entry with >=30 chars description"

- **AC-3:** Given eine Legacy-Spec mit `created: 2026-04-01` ohne AC-N / When ein Code-Edit in `phase6_implement` versucht wird / Then erlaubt `workflow_gate` den Edit ohne Blockierung (Stichtag-Grandfathering schützt 164 Bestands-Specs)

- **AC-4:** Given eine Spec ohne Frontmatter oder ohne `created`-Feld / When ein Code-Edit versucht wird / Then erlaubt `workflow_gate` den Edit (defensives Default — `legacy assumption`)

- **AC-5:** Given `openspec.yaml` enthält `spec_validation.ac_format_required_since: "2026-05-11"` / When `get_ac_format_required_since()` aus `config_loader` aufgerufen wird / Then liefert es den String `"2026-05-11"`

- **AC-6:** Given keine Konfiguration für `ac_format_required_since` in `openspec.yaml` / When `_spec_has_valid_ac_format()` aufgerufen wird / Then liefert es `(True, "no stichtag configured or spec missing")` — kein Block ohne Stichtag

- **AC-7:** Given eine neue Spec mit gültigem AC-N-Format (>=1 Eintrag, jeder >=30 Zeichen) / When ein Code-Edit in `phase6_implement` versucht wird / Then erlaubt `workflow_gate` den Edit ohne Blockierung

- **AC-8:** Given `docs/specs/_template.md` / When es gelesen wird / Then enthält es eine `## Acceptance Criteria`-Sektion mit `**AC-1:**`- und `**AC-2:**`-Beispielen im Given/When/Then-Format

- **AC-9:** Given `.claude/agents/spec-validator.md` / When es gelesen wird / Then enthält es eine Sektion "Acceptance-Criteria-Format" mit dokumentierter Stichtagslogik und den drei REQUIRED-Checkboxen

## Expected Behavior

- **Input:** Spec-Datei mit Frontmatter (`created`-Feld) und optional `## Acceptance Criteria`-Sektion; `openspec.yaml` mit optionalem Stichtag-Key
- **Output:** `(True, reason)` oder `(False, reason)` aus `_spec_has_valid_ac_format()` — bei `False` folgt Exit 2 in `workflow_gate`
- **Side effects:** Keine — reiner Read-Only-Check der Spec-Datei; kein State-Schreiben, keine Netzwerk-Zugriffe

## Known Limitations

- Frontmatter wird via Regex geparst (kein vollständiges YAML-Parsing). Bei exotischem YAML (mehrzeilige Strings, Anchors) kann der `created`-Wert unerkannt bleiben — in diesem Fall greift das defensive Default (`legacy assumption`).
- Stichtag ist global konfiguriert — keine per-Spec-Override-Möglichkeit (bewusst einfach gehalten, da Single-Cutoff für diesen Use-Case ausreicht).
- AC-N-Regex matcht `**AC-1:**` bis `**AC-99:**`; bei >100 Kriterien (unwahrscheinlich) kein funktionelles Problem.
- 164 Bestands-Specs sind grandfathered und werden nie nachträglich geprüft — auch nicht wenn sie nachträglich editiert werden. Nur `created`-Datum zählt.
- Soft-Check im `spec-validator`-Agent kann manuell ignoriert werden (kein Exit-Code, nur Verdict im Agenten-Output). Der Hard-Block in `workflow_gate` ist die verbindliche Schranke.

## Test Coverage

Tests in `tests/tdd/test_epic_191_ac_format_pflicht.py`:

- `test_new_spec_without_ac_section_is_blocked` — prüft Exit 2 + Fehlermeldung bei fehlender AC-Sektion
- `test_new_spec_with_ac_section_but_no_entries_is_blocked` — prüft Exit 2 bei leerer AC-Sektion
- `test_new_spec_with_valid_ac_entries_is_allowed` — prüft dass gültige AC-N-Einträge den Block aufheben
- `test_legacy_spec_before_stichtag_is_allowed` — prüft Grandfathering bei `created < stichtag`
- `test_spec_without_frontmatter_is_allowed` — prüft defensives Default ohne Frontmatter
- `test_spec_without_created_field_is_allowed` — prüft defensives Default ohne `created`-Feld
- `test_no_stichtag_configured_is_allowed` — prüft dass ohne Stichtag-Konfig kein Block erfolgt
- `test_get_ac_format_required_since_returns_stichtag` — prüft `config_loader`-Helper gegen `openspec.yaml`
- `test_get_ac_format_required_since_returns_none_without_config` — prüft None-Return bei fehlendem Key

## Changelog

- 2026-05-11: Initial spec erstellt — Issue #194, Epic #191. Baut auf #192 (epic_191_state_migration) und #193 (epic_191_logbuch_audit) auf.
