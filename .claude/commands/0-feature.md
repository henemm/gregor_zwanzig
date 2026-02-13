# Feature Development

Structured feature development workflow for Gregor Zwanziger.

**Understand first, plan second, implement third!**

## Usage

```bash
# New feature
"Neues Feature: SMS Channel für Reports"

# Modification to existing feature
"Erweitere E-Mail-Formatter um HTML-Tabellen"

# Enhancement
"Verbessere Provider-Auswahl mit Fallback-Logic"
```

## Mode Detection

The feature-planner agent automatically detects the mode:

| Mode | Triggers | Workflow |
|------|----------|----------|
| **NEU** | "neues Feature", "hinzufügen", "implementiere" | New architecture decisions, full planning |
| **ÄNDERUNG** | "erweitere", "anpassen", "modifiziere", "verbessere" | Understand current → identify delta → plan changes |

## Feature Development Phases

### Phase 1: Understanding

**For NEW features:**
- What is the feature? (User perspective)
- Why do we need it? (Business value)
- What are the requirements?
- What are edge cases?

**For MODIFICATIONS:**
- Document current behavior (as-is)
- What should change? (to-be)
- Why change it?
- What stays the same?

### Phase 2: System Analysis

1. **Search codebase** for similar functionality
2. **Identify affected components:**
   - Which modules/files?
   - Which data flows?
   - Which tests?

3. **Architectural decision:**
   - Extend existing system? (preferred)
   - Create new component? (when necessary)
   - Refactor first? (if technical debt blocks)

### Phase 3: Scoping

**MANDATORY constraints:**

- **Max 4-5 files** changed per feature
- **Max ±250 lines** of code changes
- If larger → **split into multiple features**

**Estimate:**
- Which files will change?
- Approximate LOC delta
- Implementation complexity (Small/Medium/Large)

### Phase 4: Documentation

**MANDATORY outputs:**

1. **Roadmap Entry** in `docs/project/backlog/ACTIVE-roadmap.md`
   ```markdown
   | Feature | Status | Priority | Category | Affected Systems |
   |---------|--------|----------|----------|------------------|
   | SMS Channel | open | HIGH | Channel | Formatter, Config |
   ```

2. **Feature Spec** via workflow:
   - Start with `/analyse` (or let feature-planner do it)
   - Create spec via `/write-spec`
   - Get approval
   - Implement via `/implement`

## Scoping Limits

**Single Feature = Single Concern**

✅ **Good scoping:**
- "Add SMS channel with 160-char formatter"
- "Add MOSMIX provider adapter"
- "Add risk score calculation"

❌ **Too large (split!):**
- "Add SMS channel + push notifications + risk engine"
- "Refactor all providers + add caching + add retry logic"

## Integration with Workflow

After feature planning completes:

1. Feature-planner creates/updates roadmap entry
2. Feature-planner starts workflow with `/analyse` (or hands off to you)
3. Follow normal workflow: analyse → write-spec → approve → implement → validate

## STOP Conditions

Agent stops and asks when:
- Intent unclear (need more info)
- Feature spans multiple categories (split?)
- Scoping exceeds limits (>5 files or >250 LOC)
- Existing systems could be extended (avoid duplication)
- User needs to choose between approaches

## Output to User

Feature-planner provides:

1. **Mode Classification** (NEU or ÄNDERUNG)
2. **Feature Summary** (1-2 sentences)
3. **Affected Systems** (components/modules)
4. **Scoping Estimate** (files, LOC, complexity)
5. **Roadmap Status** (entry created/updated)
6. **Next Steps** (workflow handoff)

## Domain Context: Gregor Zwanziger

**Project:** Headless weather data normalization service for long-distance hikers

**Architecture:**
```
CLI → Config → Provider → Normalizer → Risk Engine → Formatter → Channel
```

**Common Feature Categories:**
- **Provider:** New weather data sources (MET Norway, DWD MOSMIX, Geosphere)
- **Channel:** New output channels (Email, SMS, Push)
- **Formatter:** Report formatting (SMS 160-char, HTML email, tables)
- **Risk Engine:** Weather risk assessment logic
- **Config:** Configuration options

**Standards References:**
- API Contract: `docs/reference/api_contract.md`
- Decision Matrix: `docs/reference/decision_matrix.md`
- Architecture: `docs/features/architecture.md`

## No Code Without Planning

The feature-planner agent **WILL NOT** implement code directly.
It only:
- Analyzes
- Plans
- Documents
- Creates roadmap entries
- Hands off to workflow

Implementation happens via normal workflow after spec approval!
