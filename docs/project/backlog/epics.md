# Epics - Gregor Zwanziger

Epics are large business initiatives that contain multiple user stories.

**Format:** Epic → User Stories → Features

## Active Epics

### Epic: Multi-Channel Report Delivery

**Goal:** Enable weather reports via multiple delivery channels (Email, SMS, Push)

**Business Value:** Hikers can receive reports via their preferred channel based on connectivity

**Status:** In Progress

**User Stories:**
- [x] Email Reports - COMPLETED (MVP)
  - SMTP Mailer implemented with real E2E tests
  - HTML email with tables
  - Gmail integration

- [ ] SMS Reports - PLANNED
  - Story doc: `stories/sms-berichte.md` (to be created)
  - Features: SMS Channel Integration, SMS Compact Formatter, SMS Config, SMS Retry Logic

- [ ] Push Notification Reports - FUTURE
  - Not yet planned

**Target Completion:** Q1 2026 (Email done, SMS planned)

---

### Epic: Weather Data Integration

**Goal:** Integrate multiple weather data providers with normalization layer

**Business Value:** Reliable weather data with fallback options and regional optimization

**Status:** In Progress

**User Stories:**
- [x] Basic Provider Architecture - COMPLETED
  - Provider adapter pattern
  - Open-Meteo integration with regional models

- [ ] Enhanced Provider Support - IN PROGRESS
  - Features: MET Norway Adapter, MOSMIX Adapter, Data Normalization, Error Handling
  - See ACTIVE-roadmap.md for details

- [ ] Provider Selection Logic - PLANNED
  - Automatic provider selection based on location
  - Fallback chains
  - Decision matrix implementation

**Target Completion:** Q2 2026

---

### Epic: Risk Assessment System

**Goal:** Automated weather risk scoring for hiking safety

**Business Value:** Hikers get clear warnings about dangerous weather conditions

**Status:** Planned

**User Stories:**
- [ ] Core Risk Engine - PLANNED
  - Features: Gewitter Risk, Starkregen Risk, Wind/Hitze Risk, Configurable Thresholds
  - See ACTIVE-roadmap.md for details

- [ ] Advanced Risk Detection - FUTURE
  - Avalanche risk (winter)
  - Heat stress
  - Visibility/fog

- [ ] Risk-Based Alerting - FUTURE
  - Real-time alerts when risk changes
  - Configurable notification thresholds

**Target Completion:** Q2 2026 (Core), Q3 2026 (Advanced)

---

### Epic: Web-Based Trip Management

**Goal:** Provide web UI for managing trips and locations

**Business Value:** Easy configuration without editing files

**Status:** In Progress

**User Stories:**
- [x] Trip CRUD Operations - COMPLETED
  - Trip Edit UI
  - Location management
  - Safari compatibility fixes

- [x] Comparison Tools - COMPLETED
  - Compare E-Mail for ski resorts
  - Cloud layers visualization

- [ ] Advanced Trip Features - PLANNED
  - Multi-day trip planning
  - Route optimization based on weather
  - Offline map integration

**Target Completion:** Q1 2026 (CRUD done), Q3 2026 (Advanced)

---

### Epic: GPX-basierte Trip-Planung

**Goal:** Mehrtägige Wanderungen mit GPX-Upload planen und präzise Wettervorhersagen für zeitbasierte Segmente erhalten

**Business Value:** Weitwanderer können ihre Route detailliert planen und wissen genau, welches Wetter sie zu welcher Zeit an welchem Ort erwartet

**Status:** COMPLETED

**User Stories:**
- [x] Story 1: GPX Upload & Segment-Planung - COMPLETED
  - Story doc: `stories/gpx-upload-segment-planung.md`
  - Features: GPX Upload (WebUI), Parser, Höhenprofil, Zeit-Segmente, Hybrid-Segmentierung, Config, Übersicht
  - 7 Features, ~1116 LOC
  - **MVP:** GPX-Upload + Segmente funktionsfähig

- [x] Story 2: Wetter-Engine für Trip-Segmente - COMPLETED
  - Features: Wetter-Abfrage, Multi-Metrik, Aggregation, Cache, Change-Detection, Config
  - 7 Features, alle implementiert und validiert

- [x] Story 3: Trip-Reports (Email/SMS) - COMPLETED
  - Features: Email Trip-Formatter, SMS Compact, Scheduler, Alerts, Config
  - 5 Features, alle implementiert und validiert

**Completed:** 2026-02

---

## Completed Epics

### Epic: MVP Foundation

**Goal:** Build core infrastructure for headless weather reporting

**Status:** COMPLETED (Dec 2025)

**User Stories:**
- [x] Project Setup
  - Test infrastructure
  - CI/CD pipeline
  - Project structure

- [x] Email Delivery MVP
  - SMTP integration
  - HTML email formatting
  - Real E2E tests (no mocking!)

---

## How Epics Work

### Hierarchy

```
Epic: Large business initiative (months)
  ├─ User Story 1: User need (weeks)
  │   ├─ Feature 1: Implementable unit (days)
  │   ├─ Feature 2: Implementable unit (days)
  │   └─ Feature 3: Implementable unit (days)
  ├─ User Story 2: User need (weeks)
  │   ├─ Feature 4: Implementable unit (days)
  │   └─ Feature 5: Implementable unit (days)
  └─ User Story 3: User need (weeks)
      └─ Feature 6: Implementable unit (days)
```

### When to Create an Epic

Create an epic when:
- Multiple related user stories (3+)
- Large business initiative (>1 month)
- Strategic goal requiring multiple iterations
- Cross-cutting concern affecting multiple system areas

**Don't create epic for:**
- Single user story
- Small feature (use `/feature` directly)
- Bug fix (use `/bug`)

### Epic Lifecycle

1. **Planned:** Epic identified, scope defined
2. **In Progress:** At least one story/feature in implementation
3. **Completed:** All stories/features done
4. **Archived:** Completed epics moved to archive

## Adding Stories to Epics

When creating user story with `/user-story`, link to epic:

```markdown
# User Story: SMS-Berichte

**Epic:** Multi-Channel Report Delivery
...
```

Then update this file to add story under the epic.

## Epic Planning

Before starting epic:
1. Define clear business goal
2. Identify target user personas
3. List potential user stories
4. Prioritize stories (must-have vs nice-to-have)
5. Estimate timeline (quarters)

## Notes

- Epics are long-running (months)
- User stories are medium (weeks)
- Features are short (days)
- Keep epic scope manageable (3-8 stories max)
- Review epic status monthly
