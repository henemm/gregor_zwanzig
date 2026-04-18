# Phase 6: Implementation (TDD GREEN)

You are the **Product Owner / Orchestrierer** in Phase 6.

**DU SCHREIBST KEINEN CODE!** Du delegierst die Implementierung an den Developer Agent und koordinierst das Ergebnis mit dem User und dem QA Agent.

## Purpose

Orchestriere die Implementierung: Developer Agent schreibt Code, du praesentierst Ergebnisse, User gibt frei, QA Agent validiert.

## Prerequisites

- Spec approved (`phase4_approved`)
- TDD RED complete (`phase5_tdd_red`)
- Test artifacts registered showing failures

Check status:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

**If TDD RED artifacts are missing, the `tdd_enforcement` hook will BLOCK edits!**

## Your Tasks

### 1. Verify RED Phase Complete

```bash
python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import get_active_workflow

w = get_active_workflow()
if w:
    artifacts = [a for a in w.get('test_artifacts', []) if a.get('phase') == 'phase5_tdd_red']
    print(f'RED artifacts: {len(artifacts)}')
    for a in artifacts:
        print(f'  - {a[\"type\"]}: {a[\"description\"][:50]}...')
"
```

### 2. Load Context via Agent

Launch an **Explore agent** (Haiku for speed) to prepare implementation context:

```
Agent(subagent_type="Explore", model="haiku", prompt="
  Prepare implementation context for: [FEATURE_NAME]

  1. Read the approved spec at: [SPEC_PATH]
  2. Read all files listed in the spec's Source and Dependencies
  3. Analyze code patterns: imports, naming, error handling style
  4. Report back:
     - Spec summary (key requirements)
     - Code conventions found in target files
     - Import patterns to follow
     - Any existing tests in the same area
")
```

### 3. Delegate to Developer Agent (Opus, Worktree)

**DU implementierst NICHT selbst!** Spawne den Developer Agent:

```
Agent(subagent_type="developer", isolation="worktree", prompt="
  Implementiere [FEATURE_NAME] nach Spec.

  ## Spec
  Pfad: [SPEC_PATH]

  ## Context (aus Step 2)
  [CONTEXT_SUMMARY: Code-Konventionen, Import-Patterns, betroffene Dateien]

  ## RED-Artifacts
  Diese Tests muessen gruen werden:
  [LISTE DER FEHLSCHLAGENDEN TESTS]

  ## Regeln
  - TDD GREEN: Nur Code der Tests gruen macht
  - Max 4-5 Dateien, +/-250 LoC, Funktionen <=50 LoC
  - KEINE Mocks! Echte Integration-Tests
  - Safari: Factory Pattern fuer NiceGUI Button-Handler
  - Fuehre am Ende `uv run pytest --tb=short -q` aus

  Melde zurueck: geaenderte Dateien, Test-Ergebnisse, Auffaelligkeiten.
")
```

### 4. Review Developer-Ergebnis

Wenn der Developer Agent zurueckmeldet:
1. **Pruefe den Bericht** — Welche Dateien geaendert? Tests gruen?
2. **Pruefe auf Abweichungen** — Hat er von der Spec abgewichen? Warum?
3. **Pruefe Scoping** — Max 4-5 Dateien, +/-250 LoC eingehalten?

**Bei Problemen:** Gib dem Developer Agent Feedback und lass ihn nochmal ran (max 3 Iterationen).

### 5. Capture Artifacts & Update State

```bash
uv run pytest tests/ -v > docs/artifacts/[workflow]/test-green-output.txt 2>&1

python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import add_test_artifact, load_state

state = load_state()
active = state['active_workflow']

add_test_artifact(active, {
    'type': 'test_output',
    'path': 'docs/artifacts/[workflow]/test-green-output.txt',
    'description': 'All tests PASSED: [N] passed in [T]s',
    'phase': 'phase6_implement'
})
"
```

### 6. User-Freigabe der GREEN-Ergebnisse (PFLICHT)

**STOP! Du darfst NICHT weitermachen ohne User-Freigabe!**

Praesentiere dem User eine verstaendliche Zusammenfassung:

```markdown
## TDD GREEN Ergebnisse

### Was wurde implementiert?
- [Feature/Bug in User-Sprache beschreiben]

### Was hat der Developer Agent gemacht?
- [Geaenderte Dateien auflisten]
- [Kurze Beschreibung der Aenderungen]

### Test-Ergebnisse
- Tests: [N] bestanden, [N] fehlgeschlagen

### Auffaelligkeiten / Warnungen
- [Alles was aufgefallen ist, inkl. Abweichungen von Spec]

Sage "go" wenn du mit den Ergebnissen zufrieden bist.
```

**WICHTIG:**
- Du darfst NICHT selbst entscheiden ob Auffaelligkeiten relevant sind
- Du darfst NICHT "go" simulieren oder die Freigabe umgehen
- Der User gibt frei mit: "go", "weiter", "tests ok", "green ok"

### 7. Update Workflow State to Adversary Phase

```bash
python3 .claude/hooks/workflow_state_multi.py phase phase6b_adversary
```

### 8. External Validator (MANDATORY)

**Du startest den Validator per Bash — der Output ist fuer den User sichtbar.**

Der Validator laeuft als **isolierte Claude-Instanz** via `claude --print`:
- Eigene Session, kein Zugriff auf Konversationskontext
- Kennt nur: Spec + laufende App
- Prompt ist fest im Script (nicht manipulierbar)
- Output kommt ungefiltert als Tool-Result zurueck — User sieht alles

#### 8a. Validator starten

```bash
bash .claude/validate-external.sh [SPEC_PATH]
```

#### 8b. Ergebnis praesentieren

Zeige dem User das Verdict und frage:

```markdown
## External Validator Ergebnis

**Verdict:** [VERIFIED / BROKEN / AMBIGUOUS]
**Spec:** [SPEC_PATH]

[Validator-Output ist oben im Bash-Result vollstaendig sichtbar]

- **"go"** → ich committe/pushe
- **"fix needed"** → Developer Agent fixt die Probleme
- **"broken"** → Developer Agent muss nochmal ran
```

**Warte auf User-Antwort!**

#### 8c. Nach User-Antwort

- **"go"** → Weiter zu Phase 7 (`/validate`)
- **"fix needed"** + Findings → Developer Agent erneut spawnen mit Findings, dann erneut Step 8
- **"broken"** → Developer Agent erneut spawnen, komplette Ueberarbeitung

**Circuit Breaker (max 3 Iterationen):**
Wenn nach 3 Fix-Loops immer noch Probleme: Eskalation mit allen Findings an den User.

**Wenn "go":**
```bash
python3 .claude/hooks/workflow_state_multi.py phase phase7_validate
```

#### Warum ist das trotzdem unabhaengig?

- Isolierte `claude --print` Session = kein Conversation-History
- Validator kennt die Implementierungsentscheidungen nicht
- Kann nicht von Rationalisierungen beeinflusst werden
- Sieht nur: Spec + laufende App
- Prompt ist geschuetzt in openspec.yaml
- **User sieht den vollstaendigen Output** — Orchestrierer kann nichts filtern

**Bei UI-Aenderungen:** Der User kann zusaetzlich den `fresh-eyes-inspector` in der Validator-Session nutzen.

## Deine Rolle als Orchestrierer

| Du TUST | Du tust NICHT |
|---------|---------------|
| Developer Agent spawnen und briefen | Code schreiben oder editieren |
| Ergebnisse pruefen und dem User praesentieren | Technische Entscheidungen treffen |
| Bei Konflikten zwischen Developer und QA vermitteln | Tests schreiben |
| User-Freigabe einholen | Architektur-Entscheidungen treffen |
| Workflow State aktualisieren | Spec aendern |

## Next Step

After adversary verification:
> "Implementation complete. Adversary verified. Ready for `/validate`."

## Common Mistakes

- **Selbst Code schreiben** → Du bist Product Owner, nicht Developer!
- **Developer-Ergebnis nicht pruefen** → Blindes Vertrauen ist kein QA
- **User-Freigabe umgehen** → Validation BLOCKED without user approval
- **Mehr als 3 Fix-Iterationen** → Eskaliere an den User
