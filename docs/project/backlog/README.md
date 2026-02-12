# Backlog Structure

This directory contains project planning and tracking documents.

## Directory Structure

```
backlog/
├── README.md                    # This file
├── ACTIVE-roadmap.md            # Main feature tracking (auto-updated)
├── epics.md                     # Epic tracking (large initiatives)
├── stories/                     # User story documents
│   └── [story-name].md         # Individual story with feature breakdown
└── features/                    # Feature brief documents
    └── [feature-name].md       # Individual feature planning
```

## Hierarchy

```
Epic (months)
  └─ User Story (weeks)
      └─ Feature (days)
          └─ Tasks (hours)
```

## Documents Explained

### ACTIVE-roadmap.md

**Purpose:** Single source of truth for all features across the project

**Updated by:**
- `/feature` command (adds new features)
- `/user-story` command (adds multiple features from a story)
- Workflow state changes (status updates)
- Manual updates (priority changes, blocking)

**Contains:**
- All features with status, priority, category
- Upcoming sprints
- Completed features
- Blocked features

**View it to:**
- See what's planned
- Check feature status
- Plan next sprint
- Understand project scope

### epics.md

**Purpose:** Track large business initiatives containing multiple stories

**Updated by:**
- Manual updates when starting/completing epics
- Links to user stories

**Contains:**
- Active epics with goals and user stories
- Completed epics
- Epic lifecycle and status

**Use it when:**
- Planning multi-month initiatives
- Grouping related user stories
- Communicating strategic goals

### stories/[story-name].md

**Purpose:** Individual user story with feature breakdown

**Created by:**
- `/user-story` command via user-story-planner agent

**Contains:**
- Story in "Als/möchte/damit" format
- Acceptance criteria
- Feature breakdown with priorities (P0/P1/P2)
- Dependencies and implementation order
- Effort estimates

**Example:**
```
stories/
└── sms-berichte.md              # SMS Reports story
    Features: SMS Channel, SMS Formatter, SMS Config, SMS Retry
```

### features/[feature-name].md

**Purpose:** Individual feature brief with planning details

**Created by:**
- `/feature` command via feature-planner agent

**Contains:**
- Feature summary (what, why, for whom)
- Affected systems
- Scoping (files, LOC, complexity)
- Dependencies
- Next steps (workflow handoff)

**Example:**
```
features/
└── sms-channel-integration.md   # SMS Channel feature
    Brief for implementing SMS sending
```

## Workflow

### For Large User Needs (User Story)

1. **User describes need:**
   ```
   "Als Weitwanderer möchte ich SMS-Berichte, damit ich offline Wetter sehe"
   ```

2. **Run user story command:**
   ```bash
   /user-story "Als Weitwanderer möchte ich SMS-Berichte..."
   ```

3. **Agent creates:**
   - `stories/sms-berichte.md` (story document)
   - Entries in `ACTIVE-roadmap.md` (all features)
   - Updates `epics.md` if part of epic

4. **User picks first feature:**
   ```bash
   /feature "SMS Channel Integration"
   ```

5. **Agent creates:**
   - `features/sms-channel-integration.md` (feature brief)
   - Entry in `ACTIVE-roadmap.md` (if not already there)

6. **User follows workflow:**
   ```bash
   /analyse → /write-spec → approve → /implement → /validate
   ```

7. **Repeat for next feature** in the story

### For Single Features

1. **User describes feature:**
   ```
   "Erweitere E-Mail-Formatter um HTML-Tabellen"
   ```

2. **Run feature command:**
   ```bash
   /feature "HTML Tables in Email Formatter"
   ```

3. **Agent creates:**
   - `features/html-tables-email.md` (feature brief)
   - Entry in `ACTIVE-roadmap.md`

4. **User follows workflow:**
   ```bash
   /analyse → /write-spec → approve → /implement → /validate
   ```

## Status Tracking

Features move through these statuses:

```
open → spec_ready → in_progress → done
   ↓
blocked (when dependencies found)
```

**Status meanings:**
- `open` - Planned, not started
- `spec_ready` - Spec approved, ready to implement
- `in_progress` - Currently implementing
- `done` - Completed and validated
- `blocked` - Blocked by dependencies

## Priority Levels

**HIGH:** Critical for MVP or user-requested
**MEDIUM:** Important but not urgent
**LOW:** Nice-to-have, can wait

## Scoping Limits

Each feature must stay within:
- **Max 4-5 files** changed
- **Max ±250 lines** of code

If larger → split into multiple features

## Related Commands

| Command | Purpose | Creates |
|---------|---------|---------|
| `/user-story` | Plan large user need | Story doc + roadmap entries |
| `/feature` | Plan single feature | Feature brief + roadmap entry |
| `/bug` | Analyze bug | Bug report |
| `/workflow` | Manage workflows | - |

## Maintenance

**Weekly:**
- Review `ACTIVE-roadmap.md`
- Update feature statuses
- Identify blocked features

**Monthly:**
- Review `epics.md`
- Update epic progress
- Plan next sprint

**After Feature Completion:**
- Move feature to "Completed" section in roadmap
- Update story progress if part of larger story
- Check if story is now complete
