---
entity_id: issue_465_workflow_optimierung
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [hooks, workflow, infrastructure, observability, automation]
---

<!-- Issue #465 — Workflow-Optimierung: Typen, Auto-Advance, Observability -->

# Issue 465 — Workflow-Optimierung: Typen, Auto-Advance, Observability

## Approval

- [ ] Approved

## Purpose

Erweitert den OpenSpec-Workflow um 8 konkrete Verbesserungen in vier Gruppen: Workflow-Typen mit automatischen Phasen-Skips (feature/bugfix/docs), Auto-Advance-Mechanismus für die Spec-Phasen 1–3, strukturiertes Observability-Logging (Phasen-Dauern, E-Mail-Validator-Ergebnis, Aggregat-Statistiken) und kontextbewusste Parallel-Session-Anzeige. Das Ziel ist schnellere Iteration bei Bug- und Dokumentations-Fixes sowie bessere Sichtbarkeit über Workflow-Muster und Bottlenecks ohne bestehende Hooks oder JSON-Schemas zu brechen.

## Source

- **File:** `.claude/hooks/workflow.py` — Hauptmodul; neue Subcommands `cmd_start` (--type-Flag), `cmd_set_type`, `cmd_auto_advance_spec`, `cmd_stats`; neue Hilfsfunktion `_compute_phase_durations`; Erweiterungen in `_new_workflow` und `cmd_write_log`
- **File:** `.claude/hooks/session_singleton_guard.py` — `_do_register()`: Parallel-Session-Info nach eigener Registrierung ausgeben
- **File:** `.claude/hooks/email_spec_validator.py` — neue Funktion `_write_validation_log()`; Aufruf in `main()` vor `sys.exit()`
- **File:** `.claude/hooks/config_loader.py` — neue Funktion `get_spec_auto_advance() -> bool`
- **File:** `.claude/agents/implementation-validator.md` — Prompt-Erweiterung in Schritt 2 für `test_files`-Scope-Erzwingung
- **File:** `docs/specs/_template.md` — neuer Block `## Estimated Scope`
- **File:** `openspec.yaml` — neues Feld `workflow.spec_auto_advance: true`

## Estimated Scope

- **LoC:** ~170 (workflow.py +110, session_singleton_guard.py +20, email_spec_validator.py +35, config_loader.py +5)
- **Files:** 7
- **Effort:** medium (4 Implementierungs-Gruppen, alle additiv)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `workflow.py` — `_new_workflow` | intern | Erstellt den initialen Workflow-State; bekommt 2 neue Felder (`workflow_type`, `estimated_loc`) |
| `workflow.py` — `_atomic_write` | intern | Atomares JSON-Schreiben; wird für Phasen-Skip-Batch in `cmd_start` wiederverwendet |
| `workflow.py` — `cmd_write_log` | intern | Schreibt Execution-Log YAML; bekommt zwei neue Felder (`phase_durations`, `workflow_type`) |
| `workflow.py` — `COMMANDS`-Dict | intern | Eintragspunkt für neue Subcommands `stats`, `auto-advance-spec`, `set-type` |
| `config_loader.get_spec_auto_advance()` | intern (neu) | Liest `workflow.spec_auto_advance` aus `openspec.yaml`; Boolean-Rückgabe mit Default `False` |
| `session_singleton_guard._do_register()` | intern | Registriert die eigene Session; Erweiterungspunkt für Parallel-Session-Info-Ausgabe |
| `email_spec_validator.main()` | intern | Einstiegspunkt des Validators; ruft `_write_validation_log()` vor `sys.exit()` auf |
| `PyYAML` (`yaml.safe_dump`) | stdlib-nah (bereits installiert) | YAML-Serialisierung für `_write_validation_log()` und `cmd_stats`-Output |
| `datetime.fromisoformat` | stdlib | Parst ISO8601-Timestamps aus `phase_transitions[].at` für Dauer-Berechnung |
| `openspec.yaml` | Konfigurationsdatei | Quelle für `workflow.spec_auto_advance`-Flag |
| `.claude/workflows/_log/*.yaml` | Dateisystem | Lese-Quelle für `cmd_stats`-Aggregation |

## Implementation Details

### Gruppe A: Schema-Erweiterungen

#### A1 — Workflow-Typen (`workflow.py start <name> --type`)

`cmd_start` (aktuell Z. ~551) bekommt einen argparse-Parameter `--type` mit Choices `["feature", "bugfix", "docs"]` und Default `"feature"`.

`_new_workflow` bekommt zwei neue optionale Felder, die backward-kompatibel via `data.get(field, default)` gelesen werden:

```python
"workflow_type": args.type if hasattr(args, "type") else "feature",
"estimated_loc": None,
```

Bei `--type bugfix` trägt `cmd_start` nach `_new_workflow()` in einem einzigen `_atomic_write`-Schwung die Phasen-Skip-Transitions für Phase 1, 2 und 3 ein und setzt `current_phase` auf `phase4_approved` (Wert 4). Die Skip-Einträge in `phase_transitions[]` erhalten `trigger="auto:type_skip"` und `from/to/at`-Felder.

Bei `--type docs` werden zusätzlich zu Phasen 1–3 auch die Phasen 5, 6b und 7 übersprungen; `current_phase` wird auf `phase3_spec` (Wert 3) gesetzt, sodass nur Spec-Erstellung und Commit verbleiben.

`cmd_set_type` ist ein neuer Subcommand der das `workflow_type`-Feld im aktiven Workflow überschreibt (kein Phasen-Neuschrieb):

```python
def cmd_set_type(args):
    wf = _load_active()
    wf["workflow_type"] = args.type_value
    _atomic_write(_active_path(), wf)
    print(f"workflow_type set to: {args.type_value}")
```

#### A2 — Estimated Scope im Spec-Template

In `docs/specs/_template.md` wird nach `## Source` und vor `## Dependencies` ein neuer Block eingefügt:

```markdown
## Estimated Scope

- **LoC:** [Zahl oder Bereich, z.B. ~50 oder 30–80]
- **Files:** [Anzahl betroffener Dateien]
- **Effort:** [low | medium | high]
```

### Gruppe B: Log-Erweiterungen

#### B1 — Phasen-Dauern in Execution-Log

Neue Hilfsfunktion in `workflow.py`:

```python
def _compute_phase_durations(transitions: list) -> dict:
    """Berechnet Verweildauer pro Phase in Sekunden aus phase_transitions."""
    from datetime import datetime
    durations = {}
    for i, t in enumerate(transitions):
        phase_name = t.get("to") or t.get("from")
        if not phase_name:
            continue
        t_at = datetime.fromisoformat(t["at"])
        if i + 1 < len(transitions):
            next_at = datetime.fromisoformat(transitions[i + 1]["at"])
            seconds = int((next_at - t_at).total_seconds())
        else:
            seconds = int((datetime.utcnow() - t_at).total_seconds())
        durations[phase_name] = seconds
    return durations
```

`cmd_write_log` erweitert das YAML um zwei Felder am Ende des bestehenden Dicts:

```python
yaml_data["phase_durations"] = _compute_phase_durations(wf.get("phase_transitions", []))
yaml_data["workflow_type"] = wf.get("workflow_type", "feature")
```

#### B2 — email_spec_validator schreibt strukturiertes Ergebnis

Neue Funktion in `email_spec_validator.py`:

```python
def _write_validation_log(success: bool, errors: list, min_locations: int) -> None:
    import yaml, os
    from datetime import datetime
    wf_id = os.environ.get("GZ_ACTIVE_WORKFLOW", "unknown")
    log_dir = Path(".claude/workflows/_log")
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{date_str}_{wf_id}_email_validation.yaml"
    data = {
        "validator": "email_spec_validator",
        "validated_at": datetime.utcnow().isoformat(),
        "workflow_id": wf_id,
        "passed": success,
        "error_count": len(errors),
        "errors": errors,
        "min_locations_checked": min_locations,
    }
    with open(log_path, "w") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
```

`main()` ruft `_write_validation_log(success, errors, min_locations)` direkt vor `sys.exit(0 if success else 1)` auf. Falls `yaml` nicht verfügbar ist, wird der Fehler per `print` auf stderr ausgegeben und die Funktion überspringt das Schreiben (fail-soft, kein Abbruch des Validators).

### Gruppe C: Neuer Command `workflow.py stats`

```python
def cmd_stats(args):
    log_dir = _get_workflows_root() / "_log"
    yamls = list(log_dir.glob("*.yaml")) if log_dir.exists() else []

    # Optionales Tages-Filter
    if hasattr(args, "days") and args.days:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=args.days)
        yamls = [p for p in yamls if datetime.utcfromtimestamp(p.stat().st_mtime) >= cutoff]

    total = len(yamls)
    verdicts = {"VERIFIED": 0, "BROKEN": 0, "AMBIGUOUS": 0, "none": 0}
    fix_loops = []
    loc_deltas = []

    for p in yamls:
        with open(p) as f:
            d = yaml.safe_load(f) or {}
        v = d.get("adversary_verdict") or "none"
        verdicts[v if v in verdicts else "none"] += 1
        if "fix_loop_iterations" in d:
            fix_loops.append(d["fix_loop_iterations"])
        if "scope_loc_delta" in d:
            loc_deltas.append(d["scope_loc_delta"])

    result = {
        "total_workflows": total,
        "verdicts": verdicts,
        "verdict_rate": {k: round(v / total, 2) if total else 0 for k, v in verdicts.items()},
        "avg_fix_loop_iterations": round(sum(fix_loops) / len(fix_loops), 1) if fix_loops else None,
        "avg_scope_loc_delta": round(sum(loc_deltas) / len(loc_deltas), 0) if loc_deltas else None,
    }

    if hasattr(args, "json") and args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"Total workflows: {total}")
        for k, v in verdicts.items():
            pct = round(v / total * 100) if total else 0
            print(f"  {k}: {v} ({pct}%)")
        if result["avg_fix_loop_iterations"] is not None:
            print(f"Avg fix-loop iterations: {result['avg_fix_loop_iterations']}")
        if result["avg_scope_loc_delta"] is not None:
            print(f"Avg LoC delta: {result['avg_scope_loc_delta']}")
```

Flags: `--json` (maschinenlesbarer JSON-Output), `--days=N` (Filter auf letzte N Tage).

### Gruppe D: Verhaltensänderungen

#### D1 — Spec Auto-Advance (Phase 1→2→3)

Neuer Subcommand `auto-advance-spec` in `workflow.py`:

```python
def cmd_auto_advance_spec(args):
    if not get_spec_auto_advance():
        return  # Feature-Flag nicht gesetzt — kein-op
    wf = _load_active()
    advance_phases = {"phase1_context", "phase2_analyse"}
    if wf.get("current_phase_name") in advance_phases:
        _do_advance(wf, trigger="auto:spec_advance")
        print(f"auto-advance-spec: advanced to {wf['current_phase_name']}")
```

`get_spec_auto_advance()` in `config_loader.py`:

```python
def get_spec_auto_advance() -> bool:
    cfg = _load_openspec()
    return bool(cfg.get("workflow", {}).get("spec_auto_advance", False))
```

Die Skill-Dateien `/1-context` und `/2-analyse` rufen am Ende `python3 .claude/hooks/workflow.py auto-advance-spec` auf. Kein UserPromptSubmit-Hook-Eingriff.

`openspec.yaml` erhält unter dem `workflow:`-Block:

```yaml
workflow:
  spec_auto_advance: true
```

#### D2 — Parallel-Session-Info beim Session-Start

In `session_singleton_guard.py`, `_do_register()` nach dem Schreiben des eigenen Eintrags:

```python
# Andere lebende Sessions ermitteln
sessions = _load_sessions()
own_pid = os.getpid()
others = [s for s in sessions.values() if s.get("pid") != own_pid and _is_alive(s)]
if others:
    lines = [f"[session-guard] {len(others)} weitere aktive Session(s):"]
    for s in others:
        wf = s.get("active_workflow", "—")
        started = s.get("started_at", "?")
        lines.append(f"  PID {s['pid']} | Workflow: {wf} | seit {started}")
    print("\n".join(lines))
# sys.exit(0) bleibt unverändert — Register blockiert nie
```

Die Ausgabe geht auf stdout. Wenn keine anderen Sessions aktiv sind, keine Ausgabe.

#### D3 — Adversary-Scope via `test_files`

In `.claude/agents/implementation-validator.md`, Schritt 2 (Run the Test Suite), wird folgender Absatz eingefügt:

> **Scope-Erzwingung:** Wenn die Spec oder das Workflow-Briefing ein Feld `test_files:` definiert (kommaseparierte Pfade oder Pytest-Nodeids), MUSST du ausschliesslich diese Dateien ausfuehren: `uv run pytest <test_files>`. Wenn `test_files:` nicht definiert ist, gilt `uv run pytest tests/` als Fallback. Dieses Feld begrenzt Fehlalarme aus unreleatierten Testsuiten.

## Expected Behavior

- **Input (cmd_start --type):** Name des neuen Workflows + optionaler `--type`-Wert (`feature`/`bugfix`/`docs`)
- **Output (cmd_start --type):** Neue Workflow-JSON mit `workflow_type`-Feld; bei `bugfix` / `docs` sind entsprechende Phasen-Transitions als Skip eingetragen und `current_phase` gesetzt
- **Input (cmd_stats):** Optionale Flags `--json`, `--days=N`
- **Output (cmd_stats):** Aggregierte Statistik über alle `_log/*.yaml`-Eintraege: Verdict-Verteilung, Raten, Durchschnittswerte
- **Input (cmd_auto_advance_spec):** Kein Argument; liest aktiven Workflow und `openspec.yaml`-Flag
- **Output (cmd_auto_advance_spec):** Advance-Transition im Workflow wenn Phase in `{phase1_context, phase2_analyse}` und Flag `true`; sonst kein-op
- **Input (_write_validation_log):** `success: bool`, `errors: list[str]`, `min_locations: int`
- **Output (_write_validation_log):** YAML-Datei in `.claude/workflows/_log/<timestamp>_<wf>_email_validation.yaml`
- **Input (_compute_phase_durations):** `phase_transitions[]`-Liste aus Workflow-JSON
- **Output (_compute_phase_durations):** Dict `{phase_name: seconds_int}`
- **Side effects:** `cmd_start --type bugfix/docs` schreibt Phasen-Skips in die Workflow-JSON (irreversibel bis `workflow.py reset`); `_write_validation_log` erzeugt eine neue Datei in `_log/`; `_do_register` schreibt Parallel-Info auf stdout (keine Datei, kein Exit)

## Acceptance Criteria

- **AC-1:** Given kein aktiver Workflow existiert / When `workflow.py start my-fix --type bugfix` läuft / Then enthält die neue `my-fix.json` `workflow_type: "bugfix"`, `current_phase` entspricht `phase4_approved`, und `phase_transitions` enthält Skip-Eintraege fuer Phase 1, 2 und 3 mit `trigger="auto:type_skip"`

- **AC-2:** Given kein aktiver Workflow existiert / When `workflow.py start my-doc --type docs` läuft / Then enthält die neue `my-doc.json` `workflow_type: "docs"`, `current_phase` entspricht `phase3_spec`, und `phase_transitions` enthalten Skips fuer Phasen 1, 2 sowie 5, 6b und 7

- **AC-3:** Given `workflow.py start my-fix --type invalid` wird aufgerufen / When argparse den Wert prueft / Then endet der Prozess mit Exit-Code ungleich 0 und einer Fehlermeldung die die gueltigen Choices nennt

- **AC-4:** Given mindestens ein abgeschlossener Workflow mit Execution-Log in `_log/` / When `workflow.py stats` laeuft / Then enthaelt die Ausgabe die Verdict-Verteilung (VERIFIED, BROKEN, AMBIGUOUS, none) mit absoluten Zahlen und Prozentraten

- **AC-5:** Given `workflow.py stats --json` laeuft / When Logs vorhanden sind / Then ist der gesamte stdout valides JSON mit den Schluesseln `total_workflows`, `verdicts`, `verdict_rate`

- **AC-6:** Given `openspec.yaml` enthaelt `workflow.spec_auto_advance: true` und der aktive Workflow ist in Phase `phase1_context` / When `workflow.py auto-advance-spec` laeuft / Then ist der aktive Workflow danach in `phase2_analyse` und `phase_transitions` enthaelt einen Eintrag mit `trigger="auto:spec_advance"`

- **AC-7:** Given `openspec.yaml` enthaelt `workflow.spec_auto_advance: false` oder das Feld fehlt / When `workflow.py auto-advance-spec` laeuft / Then aendert sich keine Phase und der Exit-Code ist 0 (kein-op)

- **AC-8:** Given zwei Sessions sind registriert in `session_workflows.json` (eigene + eine andere mit lebendem PID) / When die eigene Session `_do_register()` durchlaeuft / Then erscheint auf stdout eine Zeile mit der Anzahl anderer Sessions, dem Workflow-Namen und dem Start-Zeitstempel der Fremd-Session; `sys.exit()` wird nicht aufgerufen

- **AC-9:** Given `workflow.py write-log success` wird nach einem Workflow mit mindestens 2 `phase_transitions`-Eintraegen aufgerufen / When das YAML geschrieben wird / Then enthaelt das Log-File die Schlueessel `phase_durations` (Dict mit mindestens einem Phase-Name als Key und einem positiven Integer als Value) und `workflow_type`

- **AC-10:** Given `email_spec_validator.py` wird gegen eine Staging-Mail ausgefuehrt / When die Validierung abgeschlossen ist (Erfolg oder Fehler) / Then existiert in `.claude/workflows/_log/` eine neue YAML-Datei mit den Feldern `validator`, `validated_at`, `workflow_id`, `passed`, `error_count`, `errors`

## Known Limitations

- `_compute_phase_durations` berechnet die letzte Phase bis `datetime.utcnow()` — bei langen offenen Workflows entsteht eine kuenstlich hohe Dauer fuer die letzte Phase
- `cmd_stats` liest alle `_log/*.yaml` ungefiltert — Email-Validierungs-YAMLs (vom `email_spec_validator`) werden mit aggregiert, haben aber kein `adversary_verdict`-Feld und zaehlen daher als `"none"`. Ein `--type=execution|email`-Filter ist nicht implementiert.
- Phasen-Skips bei `--type bugfix/docs` sind nicht automatisch rueckgaengig zu machen; `workflow.py reset` setzt den gesamten State zurueck
- `get_spec_auto_advance()` cached den `openspec.yaml`-Inhalt nicht — bei sehr haeufigen Aufrufen in derselben Session kann ein lokales Cache-Dict ergaenzt werden
- Auto-Advance in Phase 3 (Spec) wird nicht ausgeloest — Phase 3 endet erst durch explizite User-Freigabe ("approved")

## Changelog

- 2026-05-30: Initial spec erstellt — Issue #465
