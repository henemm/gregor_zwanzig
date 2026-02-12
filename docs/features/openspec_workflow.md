# OpenSpec 4-Phasen-Workflow

## Überblick

Das Gregor Zwanzig Projekt nutzt den OpenSpec Framework Workflow, der aus 4 sequentiellen Phasen besteht. Jede Phase wird durch einen Skill-Command ausgelöst und delegiert Aufgaben an spezialisierte Sub-Agenten mit strategischer Model-Auswahl.

**Command Naming:** Projekt nutzt die canonische OpenSpec-Namenskonvention mit Dashes (`/2-analyse`, `/3-write-spec`). Frühere Underscore-Varianten (`/1_analyse`, `/2_write-spec`) wurden im Februar 2026 gemerged und entfernt.

## Die 4 Phasen

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

### 3. Implementieren (`/5-implement`)

**Ziel:** Spec in Code umsetzen, Tests schreiben

**Ablauf:**
1. **Context Loading:** Explore/haiku lädt Spec + betroffene Dateien
2. **Core Implementation:** Main Context (Opus) implementiert Hauptfunktionalität
3. **Parallel Tasks:**
   - general-purpose/sonnet schreibt Tests
   - general-purpose/haiku updated Config (falls nötig)
4. **Integration:** Syntax-Check, workflow_state.json Update
5. **Output:** Implementierte Dateien + Tests

### 4. Validieren (`/6-validate`)

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
