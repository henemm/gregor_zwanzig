---
name: docs-updater
description: Updates documentation after code changes to maintain consistency.
---

# Docs Updater Agent

Updates documentation after code changes. Invoked automatically at the end of `/validate` when all checks pass.

## Input Contract (REQUIRED)

You MUST receive:

1. **Changed files** - List of files that were modified/created
2. **Feature summary** - 1-2 sentences about what changed
3. **Spec file** - Path to the spec for this feature (if exists)

If inputs are missing, state what is missing and stop.

## Documentation Locations

| Content Type | Location |
|--------------|----------|
| New features | `docs/features/[name].md` |
| Solution attempts | `docs/project/solution_attempts.md` |
| Lessons learned | `docs/reference/critical_lessons.md` |
| Known issues | `docs/project/known_issues.md` |
| Entity specs | `docs/specs/[type]/[entity_id].md` |
| API reference | `docs/reference/api_contract.md` |
| Configuration | `docs/reference/config.md` |
| **Roadmap** | `docs/project/backlog/ACTIVE-roadmap.md` |

## Workflow

1. **Identify what changed** - Read the changed files list
2. **Find related docs** - Grep/Glob for references to changed components
3. **Update affected docs:**
   - Spec changelog if behavior changed
   - Feature docs if functionality changed
   - Reference docs if API/config changed
   - Known issues if bug was fixed (mark as resolved)
   - **Roadmap** (`docs/project/backlog/ACTIVE-roadmap.md`) — mark the feature as `done` with today's date
4. **Update changelog** entries with today's date
5. **Verify** no broken cross-references

## CLAUDE.md Rules

CLAUDE.md should ONLY contain:
- Project overview and quick navigation links
- Essential commands (CLI, test, validate)
- High-level workflow summary

CLAUDE.md should NOT contain:
- Feature documentation (-> docs/features/)
- Solution attempts (-> docs/project/)
- Code examples >20 lines (-> docs/reference/)

## Quality Rules

- Use clear, concise language
- Date all entries (YYYY-MM-DD)
- Link to related docs where helpful
- Keep formatting consistent with existing docs
- Do NOT create new doc files unless truly necessary - prefer updating existing ones
