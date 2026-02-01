# Active Roadmap - Gregor Zwanziger

**Last Updated:** 2026-02-01

This roadmap tracks all features across the project lifecycle.
Features are added via `/feature` or `/user-story` commands.

## Status Legend

| Status | Meaning |
|--------|---------|
| `open` | Planned, not started yet |
| `spec_ready` | Specification approved, ready for implementation |
| `in_progress` | Currently being implemented |
| `done` | Completed and validated |
| `blocked` | Blocked by dependencies or external factors |

## Priority Legend

| Priority | Meaning |
|----------|---------|
| `HIGH` | Critical for MVP or user-requested |
| `MEDIUM` | Important but not urgent |
| `LOW` | Nice-to-have, can wait |

## Features

| Feature | Status | Priority | Category | Affected Systems | Estimate | Story/Epic |
|---------|--------|----------|----------|------------------|----------|------------|
| CLI Entry Point | in_progress | HIGH | Core | CLI | Medium | SETUP-02 |
| Config System (INI/ENV) | open | HIGH | Core | Config | Simple | SETUP-03 |
| Debug Architecture | open | HIGH | Core | Debug | Medium | SETUP-04 |
| MET Norway Adapter | spec_ready | HIGH | Provider | Provider Layer | Medium | WEATHER-01 |
| Open-Meteo Provider | done | MEDIUM | Provider | Provider Layer | Medium | - |
| MOSMIX Adapter | open | MEDIUM | Provider | Provider Layer | Large | WEATHER-02 |
| Data Normalization | open | HIGH | Provider | Normalizer | Medium | WEATHER-03 |
| Provider Error Handling | open | MEDIUM | Provider | Provider Layer | Medium | WEATHER-04 |
| Gewitter Risk Logic | open | HIGH | Risk Engine | Risk Engine | Medium | RISK-01 |
| Starkregen Risk | open | MEDIUM | Risk Engine | Risk Engine | Simple | RISK-02 |
| Wind/Hitze Risk | open | LOW | Risk Engine | Risk Engine | Simple | RISK-03 |
| Configurable Thresholds | open | MEDIUM | Config | Risk Engine, Config | Simple | RISK-04 |
| Report Types | open | HIGH | Formatter | Formatter, CLI | Medium | REPORT-01 |
| Compact Formatter | open | MEDIUM | Formatter | Formatter | Simple | REPORT-02 |
| SMTP Mailer | done | HIGH | Channel | Channel Layer | Medium | REPORT-03 |
| Retry Logic | open | MEDIUM | Core | All Layers | Medium | OPS-01 |
| Logging/Rotation | open | LOW | Core | Logging | Simple | OPS-02 |
| GitHub Actions | done | LOW | Ops | CI/CD | Simple | OPS-03 |
| Trip Edit UI | done | HIGH | WebUI | Frontend | Medium | UI-01 |
| Compare E-Mail | done | MEDIUM | WebUI | Frontend, Email | Medium | UI-02 |
| Cloud Layers | done | MEDIUM | WebUI | Frontend, Provider | Medium | UI-03 |
| GPX Upload (WebUI) | open | HIGH | WebUI | Frontend | Simple | GPX-Story1 |
| GPX Parser & Validation | open | HIGH | Core | GPX Parser | Medium | GPX-Story1 |
| Höhenprofil-Analyse | open | HIGH | Core | Elevation Analysis | Medium | GPX-Story1 |
| Zeit-Segment-Bildung | open | HIGH | Core | Segmentation Engine | Medium | GPX-Story1 |
| Hybrid-Segmentierung | open | HIGH | Core | Segmentation Engine | Medium | GPX-Story1 |
| Etappen-Config (WebUI) | open | HIGH | WebUI | Frontend, Config | Medium | GPX-Story1 |
| Segment-Übersicht (WebUI) | open | HIGH | WebUI | Frontend | Simple | GPX-Story1 |
| Segment-Wetter-Abfrage | open | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Basis-Metriken | open | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Erweiterte Metriken | open | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Segment-Aggregation | open | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Wetter-Cache | open | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Change-Detection | open | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Wetter-Config (WebUI) | open | HIGH | WebUI | Frontend | Simple | GPX-Story2 |
| Email Trip-Formatter | open | HIGH | Formatter | Report Generation | Medium | GPX-Story3 |
| SMS Compact Formatter | open | HIGH | Formatter | Report Generation | Simple | GPX-Story3 |
| Report-Scheduler | open | HIGH | Services | Scheduler | Medium | GPX-Story3 |
| Alert bei Änderungen | open | HIGH | Services | Alert System | Simple | GPX-Story3 |
| Report-Config (WebUI) | open | HIGH | WebUI | Frontend | Simple | GPX-Story3 |

## Completed Features (Last 5)

| Feature | Completed | Category | Notes |
|---------|-----------|----------|-------|
| Cloud Layers | 2026-01 | WebUI | Open-Meteo cloud height integration |
| Compare E-Mail | 2026-01 | WebUI | Ski resort comparison via email |
| Trip Edit UI | 2026-01 | WebUI | Edit existing trips |
| Open-Meteo Provider | 2026-01 | Provider | Regional model selection |
| SMTP Mailer | 2025-12 | Channel | Gmail SMTP with real E2E tests |

## Blocked Features

| Feature | Blocked By | Notes |
|---------|------------|-------|
| Data Normalization | MET Norway Adapter | Needs provider data structure |
| Report Types | Compact Formatter | Needs formatter implementation |

## Upcoming (Next 3 Sprints)

### Sprint 1 (Current)
- [ ] CLI Entry Point
- [ ] Config System
- [ ] Debug Architecture

### Sprint 2
- [ ] MET Norway Adapter (spec exists)
- [ ] Data Normalization
- [ ] Report Types

### Sprint 3
- [ ] Gewitter Risk Logic
- [ ] Compact Formatter
- [ ] Retry Logic

## Feature Categories

### Core (Infrastructure)
- CLI Entry Point, Config System, Debug Architecture, Retry Logic, Logging

### Provider (Weather Data Sources)
- MET Norway, MOSMIX, Open-Meteo (done), Data Normalization, Error Handling

### Risk Engine (Weather Assessment)
- Gewitter Risk, Starkregen Risk, Wind/Hitze Risk, Configurable Thresholds

### Formatter (Report Generation)
- Report Types, Compact Formatter

### Channel (Delivery)
- SMTP Mailer (done)

### WebUI (Frontend)
- Trip Edit (done), Compare E-Mail (done), Cloud Layers (done)

### Ops (Operations)
- GitHub Actions (done), Logging/Rotation

## How to Add Features

### New Feature
```bash
# Use feature command for single, scoped feature
/feature "Your Feature Name"
```

The feature-planner agent will:
1. Analyze and scope the feature
2. Create entry in this roadmap
3. Create feature brief in `features/[name].md`
4. Hand off to workflow

### User Story (Multiple Features)
```bash
# Use user-story command for larger initiatives
/user-story "Als [X] möchte ich [Y], damit [Z]"
```

The user-story-planner agent will:
1. Break down story into features
2. Add all features to this roadmap
3. Create story document in `stories/[name].md`
4. Prioritize and sequence features

## Roadmap Maintenance

**Auto-updated by:**
- `/feature` command (adds new features)
- `/user-story` command (adds multiple features)
- Workflow state changes (status updates)

**Manual updates:**
- Change priority when business needs shift
- Mark features as blocked when dependencies discovered
- Move features to "Upcoming" when planning sprints

## Notes

- **Scoping Limits:** Each feature should be ≤5 files, ≤250 LOC
- **MVP Focus:** Prioritize HIGH priority features in Core, Provider, Risk Engine categories
- **WebUI:** Separate track, already functional
- **Testing:** All features require real E2E tests (no mocking!)
