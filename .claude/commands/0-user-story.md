# User Story Planning

Break down larger user needs into implementable features.

**Epic → User Story → Features → Tasks**

## What is a User Story?

A user story describes a user need in this format:

```
Als [User Persona]
möchte ich [Goal/Need]
damit [Business Value / Reason]
```

**Example:**
```
Als Weitwanderer auf dem GR20
möchte ich Wetterberichte per SMS erhalten
damit ich auch ohne Internet-Zugang Wetterinfos bekomme
```

## When to Use User Stories

Use `/user-story` when:
- ✅ Feature is too large for single implementation (>5 files or >250 LOC)
- ✅ Feature involves multiple system layers (Provider + Formatter + Channel)
- ✅ User need spans multiple related features
- ✅ Need to plan implementation order and dependencies

**Don't use for:**
- ❌ Small, isolated features (use `/feature` directly)
- ❌ Bug fixes (use `/0-bug`)
- ❌ Simple modifications (use `/feature` with ÄNDERUNG mode)

## Usage

```bash
# User provides story
"Als Weitwanderer möchte ich SMS-Berichte, damit ich offline Wetter sehe"

# Or describe need
"Wir brauchen SMS-Support für Reports"

# Agent will structure it
```

## User Story Planning Phases

### Phase 1: Story Capture

**Extract story elements:**
- **User Persona:** Who wants this? (Weitwanderer, Admin, Developer)
- **Goal/Need:** What do they want?
- **Business Value:** Why does it matter?

**Acceptance Criteria:**
- What must be true for story to be "done"?
- How do we test/verify it?

### Phase 2: Feature Breakdown

**Decompose story into features:**

Each feature must:
- Be independently implementable
- Stay within scoping limits (4-5 files, 250 LOC)
- Have clear acceptance criteria
- Fit one of these categories: Provider, Channel, Formatter, Risk Engine, Config

**Example Breakdown:**

```
User Story: SMS-Berichte für Weitwanderer

Features:
1. SMS Provider Integration (Channel Layer)
   - Integrate with SMS gateway API
   - Handle authentication
   - ~3 files, ~150 LOC, Medium complexity

2. SMS Formatter (Formatter Layer)
   - 160-character compact format
   - Prioritize critical weather data
   - ~2 files, ~100 LOC, Simple complexity

3. SMS Channel Config (Config Layer)
   - Add SMS as channel option
   - Phone number configuration
   - ~2 files, ~50 LOC, Simple complexity

4. SMS Retry Logic (Channel Layer)
   - Retry failed sends
   - Exponential backoff
   - ~2 files, ~80 LOC, Medium complexity
```

### Phase 3: Prioritization

**Classify features by priority:**

- **P0 (Must Have):** Core functionality, story incomplete without it
- **P1 (Should Have):** Important, but story deliverable without it
- **P2 (Nice to Have):** Enhancement, can be added later

**Example:**
```
P0: SMS Provider Integration, SMS Formatter, SMS Channel Config
P1: SMS Retry Logic
P2: Delivery Tracking, Cost Monitoring
```

### Phase 4: Dependency Mapping

**Identify dependencies:**

```
SMS Provider Integration (no dependencies)
  ↓
SMS Formatter (needs Provider)
  ↓
SMS Channel Config (needs Provider + Formatter)
  ↓
SMS Retry Logic (needs Provider + Config)
```

**Implementation Order:**
1. Provider Integration (foundation)
2. Formatter (needed by Config)
3. Channel Config (integration point)
4. Retry Logic (enhancement)

### Phase 5: Documentation

**MANDATORY outputs:**

1. **User Story Document:**
   `docs/project/backlog/stories/[story-name].md`

2. **Roadmap Entries:**
   All features added to `docs/project/backlog/ACTIVE-roadmap.md`

3. **Epic Tracking:**
   Story linked to epic in `docs/project/backlog/epics.md` (if applicable)

## Output Format

User-story-planner provides:

```markdown
# User Story: [Name]

## Story
Als [Persona]
möchte ich [Goal]
damit [Value]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Feature Breakdown

### Feature 1: [Name]
- **Category:** Channel
- **Priority:** P0
- **Scoping:** 3 files, ~150 LOC, Medium
- **Dependencies:** None
- **Acceptance:** [specific criteria]

### Feature 2: [Name]
- **Category:** Formatter
- **Priority:** P0
- **Scoping:** 2 files, ~100 LOC, Simple
- **Dependencies:** Feature 1
- **Acceptance:** [specific criteria]

## Implementation Order
1. Feature 1 (foundation)
2. Feature 2 (depends on 1)
3. Feature 3 (integration)

## Roadmap Status
✅ All features added to ACTIVE-roadmap.md
✅ Story document created

## Estimated Effort
Total: ~400 LOC across 7 files
Timeline: 3-4 workflow cycles (one per P0 feature)

## Next Steps
1. Start with Feature 1: Run `/feature "Feature 1 Name"`
2. Complete workflow for Feature 1
3. Move to Feature 2
```

## Integration with Workflow

After user story planning:

1. **User chooses first feature** to implement
2. **Run `/feature [name]`** for detailed feature planning
3. **Follow normal workflow:** analyse → write-spec → approve → implement → validate
4. **Repeat for next feature** in dependency order

## STOP Conditions

Agent stops and asks when:
- Story unclear or too vague
- Story is actually just a single feature (suggest `/feature` instead)
- Features have circular dependencies
- Missing critical information (user persona, acceptance criteria)
- User needs to prioritize features

## Domain Context: Gregor Zwanziger

**Common User Personas:**
- **Weitwanderer:** Long-distance hikers with limited connectivity
- **Admin:** Service administrators managing config
- **Developer:** Future maintainers of the system

**Typical User Stories:**
- New channel support (SMS, Push)
- New weather provider integration
- Enhanced risk assessment
- Report customization

**Story Size Guidelines:**
- Small Story: 2-3 features
- Medium Story: 4-6 features
- Large Story: 7+ features (consider splitting into multiple stories or epic)

## Epic vs Story vs Feature

**Epic:** Large business initiative (multiple stories)
```
Epic: "Multi-Channel Report Delivery"
```

**User Story:** User need (multiple features)
```
Story: "SMS-Berichte für Weitwanderer"
```

**Feature:** Implementable unit (single workflow cycle)
```
Feature: "SMS Provider Integration"
```

## Success Criteria

Story planning complete when:
- [x] Story structured (who, what, why)
- [x] Acceptance criteria defined
- [x] Features identified and scoped
- [x] Priorities assigned (P0, P1, P2)
- [x] Dependencies mapped
- [x] Implementation order clear
- [x] All features in roadmap
- [x] Story document created

**Then:** User starts with first P0 feature via `/feature`
