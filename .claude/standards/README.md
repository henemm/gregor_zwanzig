# Standards Library

Domain-specific standards for Gregor Zwanziger project.

## Purpose

These standards provide **domain knowledge** that gets **automatically injected** into agent prompts when relevant.

## Available Standards

### Core Standards

| Standard | Purpose | When Applicable |
|----------|---------|-----------------|
| `api_contracts.md` | DTO and data format compliance | All features touching data layer |
| `no_mocked_tests.md` | Real E2E testing mandate | All testing scenarios |

### Domain Standards

| Standard | Purpose | When Applicable |
|----------|---------|-----------------|
| `provider_selection.md` | Weather provider selection logic | Provider features |
| `email_formatting.md` | Email report formatting rules | Email/channel features |
| `safari_compatibility.md` | NiceGUI Safari compatibility | Web UI features |

## How Standards Work

### Manual Reference

Agents can reference standards explicitly:

```markdown
# In agent prompt
When implementing email features, follow:
- Email Formatting Standard (.claude/standards/email_formatting.md)
- No Mocked Tests Standard (.claude/standards/no_mocked_tests.md)
```

### Agent Injection (Future)

Standards can be auto-injected based on context:

```python
# Feature category: "Channel" → Inject email_formatting.md
# Feature category: "Provider" → Inject provider_selection.md
# Feature category: "WebUI" → Inject safari_compatibility.md
# ALL features → Inject api_contracts.md, no_mocked_tests.md
```

## Standard Structure

Each standard follows this structure:

```markdown
# [Standard Name]

**Domain:** [Specific area]

## Purpose
[Why this standard exists]

## Rules
[Specific rules to follow]

## Examples
[Good and bad examples]

## Enforcement
[How compliance is checked]

## References
[Related documents]
```

## When to Create New Standard

Create new standard when:
- ✅ Pattern applies to multiple features (not one-off)
- ✅ Knowledge is domain-specific (not generic)
- ✅ Violations cause real issues (not just style)
- ✅ Can be clearly documented with rules

**Don't create standard for:**
- ❌ One-time decisions
- ❌ Generic programming practices
- ❌ Personal preferences
- ❌ Vague guidelines

## Using Standards in Features

### During Feature Planning

Feature-planner agent references relevant standards:

```markdown
# Feature: SMS Channel Integration

## Standards to Follow
- API Contracts: SMS DTOs must be in contract
- No Mocked Tests: Real SMS send + receive tests
- Provider Selection: SMS gateway fallback strategy
```

### During Implementation

Developer/AI reads standards before coding:

1. Check which standards apply (based on category)
2. Read relevant standards
3. Follow rules during implementation
4. Validate compliance during review

### During Validation

Reviewer checks compliance:

- [ ] API contract updated (if DTOs changed)
- [ ] Real E2E tests (no mocks)
- [ ] Safari tested (if UI changed)
- [ ] Provider fallback (if provider added)
- [ ] Email format (if email changed)

## Standard Categories

### Quality Standards
- `no_mocked_tests.md` - Testing quality

### Data Standards
- `api_contracts.md` - Data format compliance

### Architecture Standards
- `provider_selection.md` - Provider architecture

### UX Standards
- `email_formatting.md` - Email UX
- `safari_compatibility.md` - Browser compatibility

## Maintaining Standards

### When to Update

Update standard when:
- New pattern emerges (add to examples)
- Rule changes (update rules section)
- Better practice found (improve examples)
- Violation pattern found (add to "Don't" list)

### Review Frequency

- **Monthly:** Check if standards are followed
- **After incidents:** Update standard if violation caused issue
- **After feature completion:** Add learnings to relevant standard

## Enforcement Levels

### CRITICAL (Zero Tolerance)
- No Mocked Tests (blocks deployment)
- API Contracts (breaks integration)
- Safari Compatibility (breaks user experience)

### IMPORTANT (Review Required)
- Provider Selection (reliability impact)
- Email Formatting (UX impact)

### RECOMMENDED (Best Practice)
- Code style
- Documentation
- Comments

## References

Standards reference these core documents:

- `docs/reference/` - Technical references
- `docs/features/` - Feature documentation
- `docs/specs/` - Specifications
- `CLAUDE.md` - Project instructions

## Adding Standards to Agents

To reference standard in agent:

```markdown
# In .claude/agents/[agent].md

## Standards to Follow

Read and comply with:
- `.claude/standards/api_contracts.md`
- `.claude/standards/no_mocked_tests.md`

[Rest of agent instructions...]
```

## Future: Auto-Injection

Goal: Automatically inject relevant standards based on:
- Feature category (Provider → provider_selection.md)
- Affected systems (Email → email_formatting.md)
- Tools used (Browser tests → safari_compatibility.md)

Implementation: Hook or agent configuration.
