# OpenSpec 8-Phasen-Workflow

## Überblick

Das Gregor Zwanzig Projekt nutzt den OpenSpec Framework Workflow, der aus 8 sequentiellen Phasen besteht (inkl. Phase 6b Adversary Verification). Jede Phase wird durch einen Skill-Command ausgelöst und delegiert Aufgaben an spezialisierte Sub-Agenten mit strategischer Model-Auswahl.

**Command Naming:** Projekt nutzt die canonische OpenSpec-Namenskonvention mit Dashes (`/2-analyse`, `/3-write-spec`). Frühere Underscore-Varianten (`/1_analyse`, `/2_write-spec`) wurden im Februar 2026 gemerged und entfernt.

## Die 8 Phasen

### 1. Analyse (`/2-analyse`)

**Ziel:** Request verstehen, Codebase durchsuchen, Strategie entwickeln

**Ablauf:**
1. **Type Detection** - Bug oder Feature?
2. **Investigation:**
   - **Features:** 3x parallele Explore/haiku Agents
     - Affected Files Agent
     - Existing Specs Agent
     - Dependencies Agent
   - **Bugs:** bug-intake/haiku Agent (spawnt eigene Sub-Agents)
     - Error Trail Agent
     - Recent Changes Agent
     - State & Config Agent
3. **Strategic Planning:** Plan/sonnet synthethisiert Erkenntnisse
4. **Output:** Analyse-Zusammenfassung + workflow_state.json Update

### 2. Spec schreiben (`/3-write-spec`)

**Ziel:** Vollständige, konkrete Spezifikation erstellen

**Ablauf:**
1. **Context Loading** aus workflow_state.json
2. **Spec Creation:** general-purpose/sonnet nutzt spec-writer.md
3. **Validation:** spec-validator/haiku prüft Vollständigkeit
4. **Auto-Fix Loop:** Bei INVALID → Korrektur → Re-Validierung
5. **Output:** Spec-Datei in `docs/specs/[category]/` + Freigabe-Anfrage

**Validation-Checks:**
- Frontmatter komplett (entity_id, type, status, etc.)
- Alle Required Sections vorhanden
- KEINE Placeholders (TBD, TODO, etc.)
- Konsistenz zwischen Sections

### 3. Kontext sammeln (`/1-context`)

**Ziel:** Relevanten Kontext für das Feature sammeln

**Ablauf:**
1. **Codebase Exploration:** Explore/haiku durchsucht relevante Dateien
2. **Context Document:** Erstellt `docs/context/[workflow-name].md`
3. **Output:** Kontext-Zusammenfassung + workflow_state.json Update

### 4. TDD RED (`/4-tdd-red`)

**Ziel:** Fehlschlagende Tests schreiben, bevor Code existiert

**Ablauf:**
1. **Test-Dateien schreiben:** Tests die das gewünschte Verhalten beschreiben
2. **Tests ausführen:** Müssen FEHLSCHLAGEN (RED)
3. **Artifacts registrieren:** Echte Test-Failure-Outputs
4. **Output:** Registrierte RED-Artifacts + phase5_tdd_red

### 5. Implementieren (`/5-implement`)

**Ziel:** Spec in Code umsetzen, Tests grün machen

**Ablauf:**
1. **Context Loading:** Explore/haiku lädt Spec + betroffene Dateien
2. **Core Implementation:** Main Context (Opus) implementiert Hauptfunktionalität
3. **Parallel Tasks:**
   - general-purpose/sonnet schreibt Tests
   - general-purpose/haiku updated Config (falls nötig)
4. **Integration:** Syntax-Check, Tests ausführen
5. **User-Freigabe:** User muss GREEN-Ergebnisse mit "go" bestätigen
6. **Output:** Implementierte Dateien + Tests + GREEN-Artifacts

### 5b. Adversary Verification (phase6b_adversary)

**Ziel:** Unabhängige QA-Prüfung durch gegnerischen Agenten

**Konzept:** Zwei Rollen spielen gegeneinander:
- **Fixer (Implementierer/Opus):** Hat den Code geschrieben, liefert Beweise
- **QA-Tester (implementation-validator/Sonnet):** Versucht aktiv die Implementierung zu brechen

**Context Isolation:** Der QA-Tester bekommt NUR die Spec und Test-Outputs, NICHT die Reasoning-Chain des Implementierers. Das verhindert Confirmation Bias.

**Ablauf:**
1. **Spec parsen:** `adversary_dialog.py parse <spec>` extrahiert Expected-Behavior-Checkliste
2. **Dialog führen:** implementation-validator Agent prüft jeden Punkt
   - Min. 2 Runden Pflicht (Early-Agreement-Skepticism)
   - Structured Findings: ID, Severity, Category, Evidence, Remediation
3. **Dialog-Protokoll speichern:** `docs/artifacts/<workflow>/adversary-dialog.md`
4. **QA-Gate:** `qa_gate.py` validiert Test-Output + Checklist → setzt Verdict

**Tri-State Verdict:**
- **VERIFIED** — Implementierung hat Adversary-Testing bestanden
- **BROKEN** — Defekte gefunden → zurück zur Implementierung (max 3 Iterationen)
- **AMBIGUOUS** — Unklare Befunde → User-Review empfohlen (blockiert nicht)

**Circuit Breaker:** Nach 3 QA-Fixer-Loops → Eskalation an User

**Fresh Eyes Inspector:** Bei UI-Änderungen zusätzlich `fresh-eyes-inspector` Agent — beschreibt Screenshots NEUTRAL ohne Bug-Kontext.

### 6. Validieren (`/6-validate`)

**Ziel:** Alles prüfen, Auto-Fix, Doku aktualisieren

**Ablauf:**
1. **4x Parallel Validation:**
   - Bash/haiku: Tests ausführen + Syntax-Check
   - spec-validator/haiku: Spec-Compliance prüfen
   - Explore/haiku: Regression-Check
   - general-purpose/haiku: Scope-Review (±250 LoC Limit)
2. **Auto-Fix (bei Failures):**
   - general-purpose/sonnet: Ein Fix-Versuch
   - Re-Run Tests
3. **Documentation Update:**
   - docs-updater/sonnet aktualisiert betroffene Docs
4. **Output:** Validierungs-Report + workflow_state.json Update

## Model Selection Strategy

| Model | Einsatz | Rationale |
|-------|---------|-----------|
| **haiku** | Context loading, Validation, Syntax checks, Scope reviews | Schnell, günstig, ausreichend für strukturierte Tasks |
| **sonnet** | Spec writing, Test writing, Strategic planning, Auto-fixes | Balance zwischen Qualität und Kosten |
| **opus** | Core implementation (nur Main Context) | Höchste Qualität für kritische Implementierung |

## Workflow Enforcement

### Hooks

**workflow_gate.py:**
- Blockiert Edit/Write auf geschützte Dateien ohne korrekten workflow_state
- Erzwingt sequentielle Phasen (kein `/5-implement` ohne approved spec)

**spec_enforcement.py:**
- Prüft ob Spec existiert vor Implementation
- Validiert Spec-Status (muss `active` oder `approved` sein)

### State-Datei

`.claude/workflow_state.json` speichert:
- Current Phase
- Spec Path
- Analysis Summary
- Approval Status

## Architektur

```
User Command → Skill (.claude/commands/N_*.md)
             ↓
   Task Delegation (model=haiku/sonnet/opus)
             ↓
   Agent Definitions (.claude/agents/*.md)
             ↓
   Structured Output (file paths, VALID/INVALID, reports)
             ↓
   workflow_state.json Update
```

## Agent Definitions

| Agent | Input Contract | Output | Model |
|-------|---------------|---------|-------|
| **spec-writer** | Feature Name, Analysis, Files, Dependencies | Spec file path | sonnet |
| **spec-validator** | Spec file path | VALID/INVALID + Errors | haiku |
| **implementation-validator** | Spec + Test outputs (NO implementer reasoning) | VERDICT: VERIFIED/BROKEN/AMBIGUOUS + Findings | sonnet |
| **fresh-eyes-inspector** | Screenshot only (NO bug context) | Neutral UI observation report | sonnet |
| **docs-updater** | Changed files, Summary, Spec path | Updated doc paths | sonnet |
| **bug-intake** | Bug description, Error messages | Investigation report | haiku |

## Known Limitations

- Model selection ist hardcoded (nicht per-Project konfigurierbar)
- Keine Retry-Logik bei Subagent-Failures (nur 1 Versuch)
- Parallele Agent-Anzahl ist fix (3 bei analyse, 4 bei validate)
- Auto-Fix in validate limitiert auf 1 Versuch
- workflow_state.json tracked nicht Subagent-Execution-History

## Siehe auch

- `docs/specs/modules/agent_orchestration.md` - Vollständige Spec
- `.claude/agents/*.md` - Agent Definitions
- `.claude/commands/*.md` - Skill Commands
- `.claude/hooks/workflow_gate.py` - Workflow Enforcement
