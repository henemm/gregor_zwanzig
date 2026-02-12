# Commands Reference

Available commands (skills) for Gregor Zwanziger project.

## Command Categories

### Workflow Commands (Sequential)

Phase-based workflow for feature development:

| Phase | Command | Purpose |
|-------|---------|---------|
| 0 | `/0-reset` | Reset workflow state |
| 1 | `/1-context` | Gather context for feature |
| 2 | `/2-analyse` | Analyze requirements |
| 3 | `/3-write-spec` | Create specification |
| 4 | User: "approved" | Approve specification |
| 5 | `/4-tdd-red` | Write failing tests (RED) |
| 6 | `/5-implement` | Implement feature (GREEN) |
| 7 | `/6-validate` | Validate implementation |
| 8 | `/7-deploy` | Deploy to production |

### Planning Commands

High-level planning before workflow:

| Command | Purpose | Agent | Output |
|---------|---------|-------|--------|
| `/user-story` | Plan large user need | user-story-planner | Story doc + features in roadmap |
| `/feature` | Plan single feature | feature-planner | Feature brief + roadmap entry |
| `/bug` | Analyze bug | bug-intake | Bug report + analysis |

### Utility Commands

| Command | Purpose |
|---------|---------|
| `/workflow` | Manage parallel workflows |
| `/add-artifact` | Add test artifact |
| `/diary` | Custom diary command |

## Usage Patterns

### For New Large Feature (User Story)

```bash
# 1. Plan user story
/user-story "Als Weitwanderer möchte ich SMS-Berichte..."

# User story planner:
# - Breaks down into features
# - Adds all to roadmap
# - Creates story doc

# 2. Start with first P0 feature
/feature "SMS Channel Integration"

# Feature planner:
# - Analyzes scope
# - Creates feature brief
# - Updates roadmap

# 3. Follow workflow for feature
/1-context          # Or /analyse
/2-analyse          # Or let feature-planner do it
/3-write-spec
# User: "approved"
/4-tdd-red
/5-implement
/6-validate

# 4. Repeat for next feature in story
/feature "SMS Compact Formatter"
# ... workflow ...
```

### For Single Feature

```bash
# 1. Plan feature
/feature "HTML Tables in Email"

# Feature planner:
# - Analyzes scope
# - Creates brief
# - Updates roadmap

# 2. Follow workflow
/2-analyse
/3-write-spec
# User: "approved"
/4-tdd-red
/5-implement
/6-validate
```

### For Bug

```bash
# 1. Analyze bug
/bug

# Bug intake:
# - Captures symptoms
# - Finds root cause
# - Documents

# 2. Fix via workflow
/analyse "Fix bug X"
/write-spec
# ... normal workflow ...
```

## Command → Agent Mapping

| Command | Invokes Agent(s) | Location |
|---------|------------------|----------|
| `/feature` | feature-planner | `.claude/agents/feature-planner.md` |
| `/user-story` | user-story-planner | `.claude/agents/user-story-planner.md` |
| `/bug` | bug-intake | `.claude/agents/bug-intake.md` |
| `/1-context` | - | Direct workflow phase |
| `/2-analyse` | 3x Explore/haiku + Plan/sonnet | Parallel codebase research |
| `/3-write-spec` | spec-writer/sonnet + spec-validator/haiku | `.claude/agents/spec-writer.md` |
| `/5-implement` | Explore/haiku + general-purpose/sonnet | Context loading + parallel tests |
| `/6-validate` | 4x parallel agents + docs-updater/sonnet | `.claude/agents/docs-updater.md` |

## Command Files Structure

Each command file (`.claude/commands/[name].md`) contains:

```markdown
# [Command Name]

[Brief description]

## Purpose
[What this command does]

## Usage
[How to use it]

## Workflow
[Steps the command follows]

## Output
[What the user gets]

## Examples
[Usage examples]
```

## Auto-Registration

Commands are **automatically registered** as skills when:
1. File created in `.claude/commands/[name].md`
2. Claude Code CLI detects new command
3. Skill available as `/[name]`

**No manual registration needed!**

## Creating New Command

1. **Create command file:**
   ```bash
   .claude/commands/my-command.md
   ```

2. **Create agent file (if needed):**
   ```bash
   .claude/agents/my-agent.md
   ```

3. **Use command:**
   ```bash
   /my-command
   ```

## Workflow State

Commands interact with workflow state:

**File:** `.claude/workflow_state.json`

**Managed by:** `workflow_state_multi.py`

**Commands that update state:**
- `/0-reset` - Reset to phase0_idle
- `/1-context` - Advance to phase1_context
- `/2-analyse` - Advance to phase2_analyse
- `/3-write-spec` - Advance to phase3_spec
- User "approved" - Advance to phase4_approved
- `/4-tdd-red` - Advance to phase5_tdd_red
- `/5-implement` - Advance to phase6_implement
- `/6-validate` - Advance to phase7_validate
- Deploy complete - Advance to phase8_complete

## Command Best Practices

### For Planning Commands (feature, user-story)

- Run BEFORE starting workflow
- Creates roadmap entries
- Documents scope and approach
- Hands off to workflow

### For Workflow Commands (analyse, write-spec, implement)

- Run IN SEQUENCE (don't skip phases)
- Each phase has specific purpose
- Hooks enforce phase correctness
- State tracked automatically

### For Utility Commands (workflow, add-artifact)

- Use as needed (not part of main flow)
- Support parallel workflows
- Manage test artifacts

## Parallel Workflows

Multiple features can be in progress:

```bash
# Start workflow 1
/feature "Feature A"
/analyse

# Switch to workflow 2
/workflow switch "Feature B"
/feature "Feature B"
/analyse

# Check status
/workflow list
# → Feature A: Phase 2 (Analysis)
# → Feature B: Phase 2 (Analysis)

# Continue workflow 1
/workflow switch "Feature A"
/write-spec
```

## Command Documentation Updates

When adding/modifying commands:

1. Update this README
2. Update command file itself
3. Update agent file (if applicable)
4. Update ACTIVE-roadmap.md (if planning command)
5. Test command workflow

## References

- Workflow State: `.claude/workflow_state.json`
- Hooks: `.claude/hooks/`
- Agents: `.claude/agents/`
- Standards: `.claude/standards/`
- Roadmap: `docs/project/backlog/ACTIVE-roadmap.md`
