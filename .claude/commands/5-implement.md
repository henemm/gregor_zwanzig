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

### Kontext komprimieren (JETZT — vor allen anderen Schritten)

Die Phasen 1–4 haben viel Analyse- und Diskussions-Kontext angehäuft, der ab jetzt nicht mehr gebraucht wird — die Spec ist die einzige Quelle der Wahrheit. Komprimiere den Kontext:

```
/compact
```

Danach normal weiterfahren. Der Workflow-State und die Spec-Datei bleiben erhalten.

## Your Tasks

### 0. Workflow-Name pinnen (ZUERST — vor allem anderen!)

**Noch bevor du irgendeinen anderen Befehl ausfuehrst**, lese den aktiven Workflow-Namen:

```bash
python3 .claude/hooks/workflow.py status
```

Notiere den `Workflow:`-Wert (z.B. `issue_294_home_kachel`).
Verwende **ab jetzt fuer ALLE** `workflow.py`-Aufrufe diesen Workflow explizit als Prefix:

```bash
GZ_ACTIVE_WORKFLOW=<name> python3 .claude/hooks/workflow.py <command>
```

Damit arbeitet diese Session unveraenderlich auf dem richtigen Workflow — auch wenn ein anderes Fenster den `.active`-Symlink zwischendurch umbeansprucht.

### 1. Verify RED Phase Complete

```bash
GZ_ACTIVE_WORKFLOW=<name> python3 -c "
import os, sys; os.environ['GZ_ACTIVE_WORKFLOW'] = '<name>'; sys.path.insert(0, '.claude/hooks')
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

### 3. Workflow-Name für Developer Agent ermitteln

Lese den aktiven Workflow-Namen **bevor** du den Agent spawst:

```bash
python3 .claude/hooks/workflow.py status
```

Notiere den `Workflow:`-Wert (z.B. `issue_294_home_kachel`). Dieser wird als `GZ_ACTIVE_WORKFLOW` an den Developer Agent übergeben.

### 4. Delegate to Developer Agent (Sonnet, kein Worktree)

**DU implementierst NICHT selbst!** Spawne den Developer Agent — **OHNE** `isolation="worktree"` (Worktrees kennen den Workflow-State nicht):

```
Agent(subagent_type="developer", prompt="
  Implementiere [FEATURE_NAME] nach Spec.

  ## Pflicht: Workflow-Kontext setzen (ZUERST ausführen!)
  export GZ_ACTIVE_WORKFLOW=[WORKFLOW_NAME]

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

### 5. Review Developer-Ergebnis

Wenn der Developer Agent zurueckmeldet:
1. **Pruefe den Bericht** — Welche Dateien geaendert? Tests gruen?
2. **Pruefe auf Abweichungen** — Hat er von der Spec abgewichen? Warum?
3. **Pruefe Scoping** — Max 4-5 Dateien, +/-250 LoC eingehalten?

**Bei Problemen:** Gib dem Developer Agent Feedback und lass ihn nochmal ran (max 3 Iterationen).

### 6. Capture Artifacts & Update State

```bash
uv run pytest tests/ -v > docs/artifacts/[workflow]/test-green-output.txt 2>&1

GZ_ACTIVE_WORKFLOW=<name> python3 -c "
import os, sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import add_test_artifact

active = os.environ['GZ_ACTIVE_WORKFLOW']

add_test_artifact(active, {
    'type': 'test_output',
    'path': 'docs/artifacts/[workflow]/test-green-output.txt',
    'description': 'All tests PASSED: [N] passed in [T]s',
    'phase': 'phase6_implement'
})
"
```

### 7. Update Workflow State to Adversary Phase

```bash
GZ_ACTIVE_WORKFLOW=<name> python3 .claude/hooks/workflow.py phase phase6b_adversary
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
# Default: gegen Production (gregor20.henemm.com)
bash .claude/validate-external.sh [SPEC_PATH]

# Pre-Push gegen Staging (sinnvoll wenn der neue Code noch nicht auf Prod ist):
GZ_VALIDATION_URL=https://staging.gregor20.henemm.com bash .claude/validate-external.sh [SPEC_PATH]
```

**Wichtig (Issue #113):** Vor dem Push ist Production noch beim alten Stand —
ein Validator-Lauf gegen Production prueft also alten Code. Die ehrliche Variante:
- **Pre-Push:** Validator gegen `localhost` (laufender Dev-Server) oder `staging` (nach manuellem Auto-Deploy-Trigger).
- **Post-Push + nach Auto-Staging-Deploy:** Validator gegen `staging.gregor20.henemm.com`.
- **Nach `deploy-gregor-prod.sh`:** Validator gegen `gregor20.henemm.com` (final).

**Setup (einmalig):** `cp .claude/validator.env.example .claude/validator.env`, Passwort eintragen, dann `bash scripts/setup-validator-user.sh`. Der Launcher loggt sich danach automatisch ein und uebergibt dem Validator das Cookie.

#### 8b. Ergebnis präsentieren und weiterfahren

Zeige das Verdict:

> **Validator-Ergebnis:** [VERIFIED / BROKEN / AMBIGUOUS]
> Spec: [SPEC_PATH]

- **VERIFIED** → Direkt weiter zu Phase 7 (`/validate`). Kein "go" nötig.
- **BROKEN** → Developer Agent erneut spawnen mit Findings, dann erneut validieren.
- **AMBIGUOUS** → Developer Agent erneut spawnen, dann erneut validieren.

Bei VERIFIED: sofort `GZ_ACTIVE_WORKFLOW=<name> python3 .claude/hooks/workflow.py phase phase7_validate` ausführen.

**Circuit Breaker (max 3 Iterationen):**
Wenn nach 3 Fix-Loops immer noch Probleme: Eskalation mit allen Findings an den User.

### Abschluss: Tech-Lead-Brief vorbereiten

Wenn VERIFIED und bereit für Deploy, bereite den Brief vor (wird in `/7-deploy` ausgegeben):

Merke dir:
- Was wurde gebaut (1-2 Sätze Nutzerperspektive)
- Welche ACs wurden erfüllt
- Welche Nebenbefunde entdeckt und als Issue erfasst
- Risikobewertung

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
