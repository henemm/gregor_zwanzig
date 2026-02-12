# Testing the New Workflows

This guide demonstrates how to test the new feature and user-story commands.

## Quick Test: Feature Command

### Test Case: Simple Feature

```bash
# Invoke feature command
/feature "Add weather icon to email reports"
```

**Expected behavior:**
1. Feature-planner agent activates
2. Detects mode (NEU or ÄNDERUNG)
3. Analyzes codebase for similar features
4. Scopes the feature (files, LOC, complexity)
5. Creates feature brief in `docs/project/backlog/features/`
6. Updates `ACTIVE-roadmap.md`
7. Hands off to workflow

**Output should include:**
- Mode classification (NEU/ÄNDERUNG)
- Feature summary
- Affected systems
- Scoping estimate
- Roadmap status
- Next steps

### Test Case: Feature Too Large

```bash
/feature "Rewrite entire provider layer with caching, retry logic, and monitoring"
```

**Expected behavior:**
1. Feature-planner analyzes scope
2. **STOPS** because >5 files or >250 LOC
3. Asks user to split into smaller features
4. Suggests split points

**Output should include:**
- "Feature zu groß"
- Scoping analysis showing why (>5 files)
- Suggested split into sub-features

## Quick Test: User Story Command

### Test Case: User Story with Multiple Features

```bash
# Invoke user story command
/user-story "Als Admin möchte ich Monitoring-Dashboards, damit ich Service-Health sehen kann"
```

**Expected behavior:**
1. User-story-planner agent activates
2. Captures story (Als/möchte/damit format)
3. Defines acceptance criteria
4. Breaks down into features (2-6 features)
5. Assigns priorities (P0/P1/P2)
6. Maps dependencies
7. Creates story doc in `docs/project/backlog/stories/`
8. Updates `ACTIVE-roadmap.md` with all features
9. Hands off to first feature

**Output should include:**
- Structured story
- Feature breakdown with scoping
- Priorities assigned
- Implementation order
- Roadmap updated
- Next steps (start first P0 feature)

### Test Case: Story is Actually Single Feature

```bash
/user-story "Als User möchte ich die E-Mail Betreffzeile anpassen"
```

**Expected behavior:**
1. User-story-planner analyzes
2. **STOPS** because only one feature
3. Suggests using `/feature` instead

**Output should include:**
- "Das sieht nach einem einzelnen Feature aus"
- Suggestion to use `/feature` command

## Integration Test: Full Workflow

### Scenario: New Feature from Story to Implementation

```bash
# Step 1: Plan user story
/user-story "Als Weitwanderer möchte ich Push-Notifications für Wetterberichte"

# User-story-planner creates:
# - Story doc with 3-4 features
# - Roadmap entries
# - Priority P0/P1

# Step 2: Start first P0 feature
/feature "Push Notification Channel Integration"

# Feature-planner creates:
# - Feature brief
# - Roadmap entry (if not exists)
# - Scoping analysis

# Step 3: Follow normal workflow
/analyse "Push Notification Channel"
# ... analyse phase ...

/write-spec
# ... spec creation ...

# User: "approved"

/tdd-red
# ... write failing tests ...

/implement
# ... implement feature ...

/validate
# ... validation ...

# Step 4: Repeat for next feature
/feature "Push Notification Config"
# ... workflow ...
```

**Expected result:**
- Story doc in `stories/`
- Multiple feature briefs in `features/`
- All features in `ACTIVE-roadmap.md`
- Workflow state tracks each feature
- Each feature goes through full workflow

## Verification Checklist

After running tests, verify:

### Roadmap Updated
```bash
cat docs/project/backlog/ACTIVE-roadmap.md | grep "Feature Name"
```

Should show new feature entry with:
- Status (open)
- Priority (HIGH/MEDIUM/LOW)
- Category
- Affected Systems
- Estimate

### Feature Brief Created
```bash
ls docs/project/backlog/features/ | grep "feature-name"
```

Should exist: `feature-name.md` with:
- What/Why/For Whom
- Affected systems
- Scoping
- Dependencies
- Next steps

### Story Document Created (for user-story)
```bash
ls docs/project/backlog/stories/ | grep "story-name"
```

Should exist: `story-name.md` with:
- Story (Als/möchte/damit)
- Acceptance criteria
- Feature breakdown
- Priorities (P0/P1/P2)
- Implementation order

### Workflow State Updated
```bash
cat .claude/workflow_state.json
```

Should show:
- Active workflow name
- Current phase
- Spec file (if created)

## Example Tests Included

### Example Feature Brief
```bash
cat docs/project/backlog/features/EXAMPLE-sms-channel-integration.md
```

Demonstrates:
- Complete feature brief structure
- Scoping within limits
- Dependencies
- Testing strategy (real E2E, no mocks!)
- Standards to follow

### Example User Story
```bash
cat docs/project/backlog/stories/EXAMPLE-sms-berichte.md
```

Demonstrates:
- User story format
- Feature breakdown (6 features)
- Priorities (P0/P1/P2)
- Dependencies and order
- MVP definition
- Effort estimation

## Standards Verification

After feature planning, check standards compliance:

```bash
# Check which standards apply
ls .claude/standards/

# For email features
cat .claude/standards/email_formatting.md

# For provider features
cat .claude/standards/provider_selection.md

# For UI features
cat .claude/standards/safari_compatibility.md

# Universal standards
cat .claude/standards/api_contracts.md
cat .claude/standards/no_mocked_tests.md
```

## Common Issues

### Issue: Command not found

**Symptom:** `/feature` or `/user-story` not recognized

**Cause:** Command file not detected

**Fix:**
```bash
ls .claude/commands/feature.md
ls .claude/commands/user-story.md
# Should exist
```

### Issue: Agent not found

**Symptom:** "Agent XYZ not found"

**Cause:** Agent file missing or misnamed

**Fix:**
```bash
ls .claude/agents/feature-planner.md
ls .claude/agents/user-story-planner.md
# Should exist
```

### Issue: Roadmap not updated

**Symptom:** Feature not in ACTIVE-roadmap.md

**Cause:** Agent didn't complete successfully

**Fix:**
- Check agent output for errors
- Manually add entry if needed
- Re-run command

## Next Steps After Testing

Once tests pass:

1. **Use for real features:**
   ```bash
   /feature "Your Real Feature Name"
   ```

2. **Update roadmap regularly:**
   - Mark features as done when complete
   - Update priorities as needs change
   - Add new features as discovered

3. **Maintain standards:**
   - Update standards when patterns emerge
   - Add examples from real implementations
   - Review compliance during validation

4. **Extend system:**
   - Add new agents for specialized tasks
   - Create new standards for new domains
   - Customize workflows for team needs

## Success Criteria

Testing successful when:
- [x] `/feature` creates feature brief
- [x] `/feature` updates roadmap
- [x] `/user-story` creates story doc
- [x] `/user-story` breaks down into features
- [x] `/user-story` updates roadmap with all features
- [x] Feature scoping catches too-large features
- [x] Story planner catches single-feature stories
- [x] Standards are documented and referenced
- [x] Example docs demonstrate full workflow

All criteria met = System ready for production use! 🎉
