---
entity_id: e2e_scope_detection
type: module
created: 2026-04-22
updated: 2026-04-24
status: draft
version: "1.1"
tags: [commit-gate, e2e, hooks, git, scope, automation]
---

# E2E Commit Gate: Auto-Scope Detection

## Approval

- [ ] Approved

## Purpose

Erweitert den E2E-Commit-Gate-Hook um eine automatische Erkennung des Verifikationsumfangs, basierend auf den im Staging-Bereich befindlichen Dateien (`git diff --cached --name-only`). Ziel ist es, den bisher pauschalen Full-Stack-Verifikationslauf auf das tatsaechlich betroffene Scope zu reduzieren — reine Dokumentations-Commits werden vollstaendig uebersprungen, reine Frontend-Commits benoetigen nur einen Server-Restart-Check, und das `e2e-verify`-Kommando schreibt den erkannten Scope ohne Code-Duplikation in `e2e_verified.json`.

## Scope

### In Scope

- `.claude/hooks/e2e_commit_gate.py` — `detect_scope()` Funktion + `SCOPE_LEVEL`/`REQUIRED_BY_SCOPE` Dicts **(BEREITS IMPLEMENTIERT)** + Ersatz der `feature_type`-Logik in `check_verification()` durch Scope-Hierarchie-Vergleich **(NOCH AUSSTEHEND)**
- `tests/tdd/test_e2e_scope_detection.py` — 7 Tests fuer `detect_scope()` **(BEREITS IMPLEMENTIERT)** + 13 Tests fuer `check_verification()` **(NOCH AUSSTEHEND)**
- `.claude/commands/e2e-verify.md` — Schritt 6: `scope`-Feld per `detect_scope()`-Import schreiben **(NOCH AUSSTEHEND)**

### Out of Scope

- Aenderungen an anderen Hooks
- Neue Test-Infrastruktur

## Source

- **File:** `.claude/hooks/e2e_commit_gate.py`
- **Identifier:** `detect_scope` (Funktion), `check_verification` (Funktion), `SCOPE_LEVEL` (Dict), `REQUIRED_BY_SCOPE` (Dict)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `subprocess` | Python stdlib | `git diff --cached --name-only` ausfuehren |
| `e2e_verified.json` | JSON-Datei (Laufzeit) | Bestehende Verifikations-Ergebnisse lesen; `scope`-Feld zur Validierung heranziehen |
| `e2e-verify.md` | Command-Datei | Schreibt `e2e_verified.json`; muss `detect_scope()` importieren um `scope`-Feld ohne Duplikation zu schreiben |

## Implementation Details

### Teil A: `.claude/hooks/e2e_commit_gate.py` — BEREITS IMPLEMENTIERT

`detect_scope()`, `SCOPE_LEVEL` und `REQUIRED_BY_SCOPE` sind vollstaendig implementiert:

```python
SCOPE_LEVEL = {
    "docs-only":     0,
    "frontend-only": 1,
    "backend":       2,
    "full-stack":    3,
}

REQUIRED_BY_SCOPE = {
    "frontend-only": ["server_restarted"],
    "backend":       ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"],
    "full-stack":    ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"],
}

def detect_scope() -> str:
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if not files:
        return "docs-only"
    has_frontend = False
    has_backend = False
    for path in files:
        if path.startswith("frontend/"):
            has_frontend = True
        elif path.startswith("src/") or path.startswith("api/"):
            has_backend = True
        elif (
            path.startswith("docs/")
            or path.startswith(".claude/")
            or path.endswith(".md")
            or path.startswith("README")
        ):
            pass  # docs — neutral
        else:
            has_backend = True  # unknown path → conservative
    if has_frontend and has_backend:
        return "full-stack"
    if has_frontend:
        return "frontend-only"
    if has_backend:
        return "backend"
    return "docs-only"
```

### Teil B: `check_verification()` — NOCH AUSSTEHEND

Die bestehenden Zeilen 155–167 in `check_verification()` verwenden noch den alten `feature_type`-Check:

```python
# ALT (zu ersetzen):
if data.get("feature_type") == "ui_only":
    required = ["server_restarted"]
else:
    required = ["server_restarted", "test_trip_created", "emails_checked", "test_trip_cleaned"]
```

Ersatz durch Scope-Hierarchie-Vergleich:

```python
# NEU:
verified_scope = data.get("scope", "full-stack")  # Backward-Kompatibilitaet: kein scope → full-stack
if SCOPE_LEVEL.get(verified_scope, 0) < SCOPE_LEVEL.get(scope, 0):
    return False, (
        f"Scope-Konflikt: Verifikation war '{verified_scope}', "
        f"aber Commit benoetigt '{scope}'. Fuehre `/e2e-verify` erneut aus!"
    )
required = REQUIRED_BY_SCOPE[scope]
```

Daraus ergibt sich fuer `check_verification()` nach dem Timestamp-Check folgender Ablauf:
1. `scope = detect_scope()` — Scope des aktuellen Commits bestimmen
2. `if scope == "docs-only"` → sofort `(True, "Scope: docs-only — E2E Gate uebersprungen.")` zurueckgeben
3. JSON-Datei laden (bestehende Logik bleibt)
4. Timestamp pruefen (bestehende Logik bleibt)
5. `verified_scope = data.get("scope", "full-stack")` — Scope aus JSON lesen, Fallback auf full-stack
6. `if SCOPE_LEVEL[verified_scope] < SCOPE_LEVEL[scope]` → `(False, Fehlermeldung mit scope-Details)` — Exit-Code `sys.exit(2)` in `main()`
7. `required = REQUIRED_BY_SCOPE[scope]` — Pflichtfelder scope-spezifisch bestimmen
8. Fehlende Felder pruefen (bestehende Logik bleibt)
9. Erfolgs-Message um Scope-Info erweitern: `f"E2E verifiziert vor {age_minutes} Minuten. [Scope: {scope}]"`

Hinweis: Der Scope-Hierarchie-Vergleich blockiert mit `sys.exit(2)` (einheitlich mit allen anderen Blockierungen im Hook).

### Teil C: `tests/tdd/test_e2e_scope_detection.py` — 13 neue Tests fuer `check_verification()` NOCH AUSSTEHEND

Die 7 bestehenden Tests decken nur `detect_scope()` ab. Die 13 neuen Tests decken `check_verification()`:

**Happy-Path-Tests (3):**
- `test_check_verification_docs_only_skips_gate` — `detect_scope()` gibt `docs-only` → Gate ueberspringen, `(True, ...)` ohne JSON-Lesen
- `test_check_verification_frontend_only_needs_only_server_restarted` — JSON mit `scope="frontend-only"`, nur `server_restarted=True`, alle anderen Felder fehlen → `(True, ...)`
- `test_check_verification_full_stack_needs_all_fields` — JSON mit `scope="full-stack"` und allen 4 Feldern `True` → `(True, ...)`

**Fehler-Tests (7):**
- `test_check_verification_no_json_returns_false` — JSON-Datei fehlt → `(False, ...)`
- `test_check_verification_corrupt_json_returns_false` — JSON-Datei ist nicht parsebar → `(False, ...)`
- `test_check_verification_stale_timestamp_returns_false` — Timestamp > 2 Stunden → `(False, ...)`
- `test_check_verification_missing_verified_at_returns_false` — Kein `verified_at`-Feld → `(False, ...)`
- `test_check_verification_missing_required_field_returns_false` — `backend`-Scope, `emails_checked` fehlt → `(False, ...)`
- `test_check_verification_scope_too_low_returns_false` — Commit-Scope `backend`, JSON-Scope `frontend-only` → `(False, "Scope-Konflikt...")`
- `test_check_verification_scope_too_low_full_stack_vs_frontend` — Commit-Scope `full-stack`, JSON-Scope `frontend-only` → `(False, "Scope-Konflikt...")`

**Backward-Kompatibilitaets-Tests (3):**
- `test_check_verification_no_scope_field_falls_back_to_full_stack` — JSON ohne `scope`-Feld, Commit-Scope `backend` → kein Blockieren (full-stack deckt backend ab), `(True, ...)`
- `test_check_verification_no_scope_field_full_stack_commit` — JSON ohne `scope`-Feld, Commit-Scope `full-stack` → kein Blockieren, `(True, ...)`
- `test_check_verification_legacy_feature_type_ignored` — JSON mit altem `feature_type="ui_only"` aber ohne `scope`-Feld → Fallback auf full-stack, `(True, ...)` wenn alle 4 Felder gesetzt (kein Regressionsrisiko)

### Teil D: `.claude/commands/e2e-verify.md` — Schritt 6 NOCH AUSSTEHEND

Schritt 6 (JSON schreiben) wird um das `scope`-Feld erweitert. Der Scope wird per Import aus dem Hook bestimmt — keine Code-Duplikation:

```python
python3 -c "
import json, datetime, sys
sys.path.insert(0, '.claude/hooks')
from e2e_commit_gate import detect_scope

scope = detect_scope()
data = {
    'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': scope,
    'server_restarted': True,
    'test_trip_created': True,
    'reports_sent': ['morning', 'evening'],
    'emails_checked': True,
    'test_trip_cleaned': True,
    'feature_checks': ['HIER BESCHREIBEN WAS GEPRUEFT WURDE']
}
with open('.claude/e2e_verified.json', 'w') as f:
    json.dump(data, f, indent=2)
print(f'e2e_verified.json geschrieben (scope: {scope})')
"
```

## Expected Behavior

- **Input:** Gestagezte Dateien im Git-Index zum Zeitpunkt des Commit-Hooks; `e2e_verified.json` mit optionalem `scope`-Feld.
- **Output:**
  - `detect_scope()` gibt einen Scope-String zurueck: `docs-only` | `frontend-only` | `backend` | `full-stack`
  - `check_verification()` gibt `(True, message)` oder `(False, message)` zurueck; `main()` bricht bei `False` mit `sys.exit(2)` ab
- **Side effects:**
  - Bei Commit-Scope `docs-only`: Hook beendet sich sofort mit `exit 0` ohne JSON zu lesen
  - Bei `frontend-only`: Nur `server_restarted` als Pflichtfeld geprueft
  - Bei `backend` oder `full-stack`: Vollstaendiger Verifikationslauf (alle 4 Felder)
  - Bei Scope-Hierarchie-Verletzung (z.B. Commit braucht `backend`, JSON hat `frontend-only`): `exit 2` mit erklaerenden Fehlermeldung

### Scope-Tabelle

| Geaenderte Pfade | Scope | Pflicht-Gates |
|-----------------|-------|---------------|
| Nur `frontend/` | `frontend-only` | `server_restarted` |
| `src/`, `api/`, unbekannte Pfade | `backend` | alle 4 |
| `frontend/` + `src/`/`api/` | `full-stack` | alle 4 |
| `docs/`, `.claude/`, `*.md` | `docs-only` | Gate uebersprungen |

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| `git diff` schlaegt fehl | `subprocess` Fehler propagiert; Hook bricht mit Fehler ab |
| Keine Dateien gestaget | Scope `docs-only` → Gate uebersprungen |
| Unbekannte Pfade (z.B. `config.ini`) | Konservativ als `backend` behandelt |
| `e2e_verified.json` fehlt | `(False, "Keine E2E-Verifikation gefunden...")` |
| JSON korrupt | `(False, "e2e_verified.json ist korrupt: ...")` |
| Timestamp > 2 Stunden | `(False, "E2E-Verifikation ist N Minuten alt...")` |
| Scope zu niedrig (z.B. JSON=frontend-only, Commit=backend) | `(False, "Scope-Konflikt: ...")` → `sys.exit(2)` |
| JSON ohne `scope`-Feld (Legacy) | Fallback auf `full-stack` → kein Blockieren (konservativ) |

## Known Limitations

- Pfad-Klassifikation basiert auf String-Praefixen, nicht auf Build-Graphen. Dateien ausserhalb der definierten Praefixe (z.B. `go.mod`, `pyproject.toml`) werden konservativ als `backend` behandelt.
- `.claude/`-Aenderungen (inkl. Hook-Aenderungen selbst) sind als `docs-only` klassifiziert und uebergehen das E2E-Gate. Das ist gewollt: Hook-Aenderungen erfordern keinen E2E-Produktivtest.
- Mehrere Worktrees oder ungewoehnliche Repo-Layouts koennen dazu fuehren, dass `git diff --cached` nicht das erwartete Ergebnis liefert. Fuer den Standard-Workflow ausreichend.

## Changelog

- 2026-04-22: Initial spec (Auto-Scope Detection fuer E2E Commit Gate) — nur `detect_scope()` und `check_verification()`-Anpassung als Scope
- 2026-04-24: v1.1 — Scope erweitert auf vollstaendige Implementation: 13 neue `check_verification()`-Tests, `e2e-verify.md` Schritt-6-Aenderung mit `detect_scope()`-Import; bereits implementierte Teile als solche markiert
