---
entity_id: agent_orchestration
type: module
created: 2026-02-12
updated: 2026-02-12
status: active
version: "1.0"
tags: [agents, workflow, tasks, orchestration, openspec]
---

# Agent Orchestration

## Approval

- [x] Approved (2026-02-12)

## Purpose

Restructures the 4-phase workflow skill commands to explicitly use Task subagents with model selection (haiku/sonnet/opus) and improves the 4 agent definition files with input contracts and structured outputs. Enables parallel execution of independent tasks, strategic model selection for cost/quality tradeoffs, and clear handoff contracts between agents.

## Source

- **Files:** `.claude/agents/*.md`, `.claude/commands/*.md`
- **Identifier:** Workflow skill commands: `/analyse`, `/write-spec`, `/implement`, `/validate`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Claude Code Task tool | system | Subagent delegation with model parameter |
| workflow_state.json | data | Workflow state tracking between phases |
| workflow_gate.py | hook | Enforces workflow state before edits |
| spec_enforcement.py | hook | Validates specs exist before implementation |

## Implementation Details

### Phase A: Agent Definitions (~105 LoC)

#### 1. spec-writer.md
- Add input contract requiring: Feature Name, Analysis Summary, Affected Files, Dependencies
- Define structured output: File path of created spec
- Clarify quality rules: ZERO placeholders, concrete implementation details

#### 2. spec-validator.md
- Enforce strict VALID/INVALID output format
- Define validation checks: Frontmatter, Required Sections, No Placeholders, Consistency
- Decision rule: Any ERROR → INVALID, only WARNINGS/OK → VALID

#### 3. docs-updater.md
- Add input contract requiring: Changed files list, Feature summary, Spec file path
- Define documentation locations table
- Clarify update workflow steps

#### 4. bug-intake.md
- Add Explore sub-delegation pattern for autonomous investigation
- Define 3 parallel investigation agents: Error Trail, Recent Changes, State & Config
- Define structured report output format

### Phase B: Skill Commands (~187 LoC)

#### 5. 1_analyse.md
- Step 1: Determine Bug vs Feature (routing decision)
- Step 2a: Features → 3x Explore/haiku parallel (Affected Files, Existing Specs, Dependencies)
- Step 2b: Bugs → bug-intake/haiku agent (which spawns own sub-agents)
- Step 3: Plan/sonnet for strategic assessment
- Present synthesis to user, update workflow state

#### 6. 2_write-spec.md
- Gather context from workflow state
- general-purpose/sonnet creates spec using spec-writer.md instructions
- spec-validator/haiku validates output
- Auto-fix if INVALID, then re-validate
- Update workflow state, present to user for approval

#### 7. 3_implement.md
- Explore/haiku loads context (spec, files, patterns)
- Main context (Opus) implements core functionality
- Parallel: general-purpose/sonnet writes tests + general-purpose/haiku updates config (if needed)
- Integrate, verify syntax, update workflow state

#### 8. 4_validate.md
- Parallel 4 agents:
  - Bash/haiku: Tests & syntax check
  - spec-validator/haiku: Spec compliance
  - Explore/haiku: Regression check
  - general-purpose/haiku: Scope review
- If test failures: general-purpose/sonnet auto-fix (one attempt)
- If all pass: docs-updater/sonnet updates documentation
- Present results, update workflow state

## Architecture

```
/analyse → Determine Type → Feature: 3x Explore/haiku parallel
                         └→ Bug: bug-intake/haiku → 3x Explore/haiku sub-agents
           └→ Plan/sonnet → Synthesis → workflow_state.json

/write-spec → general-purpose/sonnet (spec-writer) → spec file
            └→ spec-validator/haiku → VALID/INVALID
            └→ Auto-fix if needed → workflow_state.json

/implement → Explore/haiku (context loading)
           └→ Main/Opus (core implementation)
           └→ Parallel: general-purpose/sonnet (tests)
                      + general-purpose/haiku (config)
           └→ workflow_state.json

/validate → 4x Parallel agents (Bash/haiku, spec-validator/haiku,
                                Explore/haiku, general-purpose/haiku)
          └→ Auto-fix: general-purpose/sonnet (if tests fail)
          └→ docs-updater/sonnet
          └→ workflow_state.json
```

## Model Selection Strategy

| Model | Purpose | Use Cases |
|-------|---------|-----------|
| haiku | Speed + low cost | Context loading, validation, syntax checks, scope reviews |
| sonnet | Quality + cost balance | Writing specs, writing tests, strategic planning, auto-fixes |
| opus | Highest quality | Core implementation (main context only) |

## Expected Behavior

### Input
- User invokes skill command: `/analyse`, `/write-spec`, `/implement`, `/validate`
- Workflow state must match phase prerequisites (enforced by hooks)

### Output
- Multiple Task subagents spawned with explicit model selection
- Parallel execution where tasks are independent
- Sequential execution where dependencies exist
- Workflow state updated after each phase
- Structured outputs from agents (file paths, VALID/INVALID, reports)

### Side Effects
- `.claude/workflow_state.json` updated after each phase
- Spec files created in `docs/specs/[category]/`
- Documentation updated in `docs/` after validation
- Git commits blocked until validation passes

## Known Limitations

- Model selection is hardcoded in command files (not configurable per-project)
- No retry logic if subagent fails (single attempt only)
- Parallel agent count is fixed (3 for analyse, 4 for validate)
- Auto-fix in validate limited to one attempt
- workflow_state.json does not track subagent execution history

## Changelog

- 2026-02-12: Implementation complete, marked as active
- 2026-02-12: Initial spec created for agent orchestration restructuring
