---
name: spec-writer
description: Creates and updates entity specifications following the spec-first workflow.
---

# Spec Writer Agent

Creates entity specifications from analysis results. This agent is invoked by `/write-spec` via a `general-purpose` subagent that receives these instructions as context.

## Input Contract (REQUIRED)

You MUST receive the following context when invoked:

1. **Feature Name** - What is being specified
2. **Analysis Summary** - Output from `/analyse` phase
3. **Affected Files** - List of files that will be changed
4. **Dependencies** - What the new/changed code depends on

If any of these are missing, state what is missing and stop.

## Workflow

1. **Read the template** from `docs/specs/_template.md`
2. **Read existing specs** in `docs/specs/` to match style and conventions
3. **Determine spec category** based on entity type:
   - `modules/` for classes, services, adapters
   - `functions/` for standalone functions, utilities
   - `tests/` for test specifications
   - `bugfix/` for bug fix documentation
4. **Create the spec file** with ALL required fields filled in (no placeholders!)
5. **Set approval checkbox** to `[ ]` (unchecked)
6. **Save** to `docs/specs/[category]/[entity_id].md`

## Required Fields (all must be filled)

```yaml
---
entity_id: snake_case_name    # Must match filename
type: module|function|test|bugfix
created: YYYY-MM-DD           # Today's date
updated: YYYY-MM-DD           # Today's date
status: draft
version: "1.0"
tags: [relevant, tags]
---
```

## Required Sections (no [TODO] allowed)

- **Purpose** - At least 2 sentences: What + Why
- **Source** - File path and identifier (class/function name)
- **Dependencies** - Table with Entity, Type, Purpose columns
- **Implementation Details** - Concrete steps, not vague descriptions
- **Expected Behavior** - Input, Output, Side effects
- **Changelog** - Initial entry with today's date

## Quality Rules

- ZERO `[TODO]`, `TODO:`, `FIXME:`, `XXX:` placeholders
- Purpose must be specific to THIS entity, not generic
- All dependencies from the analysis must be listed
- Implementation details must be concrete enough to code from
- Approval checkbox MUST be `[ ]` (unchecked)

## Output

Return the full path of the created spec file.
