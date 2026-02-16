# Active Roadmap - Gregor Zwanziger

**Last Updated:** 2026-02-16

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
| Config System (INI/ENV) | in_progress | HIGH | Core | Config | Simple | SETUP-03 |
| Debug Architecture | in_progress | HIGH | Core | Debug | Medium | SETUP-04 |
| MET Norway Adapter | spec_ready | HIGH | Provider | Provider Layer | Medium | WEATHER-01 |
| Open-Meteo Provider | done | MEDIUM | Provider | Provider Layer | Medium | - |
| MOSMIX Adapter | open | MEDIUM | Provider | Provider Layer | Large | WEATHER-02 |
| Data Normalization | done | HIGH | Provider | Normalizer | Medium | WEATHER-03 |
| Provider Error Handling | done | MEDIUM | Provider | Provider Layer | Medium | WEATHER-04 |
| Model-Metric-Fallback | done | MEDIUM | Provider | Provider Layer, Cache | Medium | WEATHER-05 |
| UV-Index via Air Quality API | done | MEDIUM | Provider | Provider Layer | Simple | WEATHER-06 |
| Gewitter Risk Logic | open | HIGH | Risk Engine | Risk Engine | Medium | RISK-01 |
| Starkregen Risk | open | MEDIUM | Risk Engine | Risk Engine | Simple | RISK-02 |
| Wind/Hitze Risk | open | LOW | Risk Engine | Risk Engine | Simple | RISK-03 |
| Configurable Thresholds | open | MEDIUM | Config | Risk Engine, Config | Simple | RISK-04 |
| Report Types | done | HIGH | Formatter | Formatter, CLI | Medium | REPORT-01 |
| Compact Formatter | done | MEDIUM | Formatter | Formatter | Simple | REPORT-02 |
| SMTP Mailer | done | HIGH | Channel | Channel Layer | Medium | REPORT-03 |
| Retry Logic | in_progress | MEDIUM | Core | All Layers | Medium | OPS-01 |
| Logging/Rotation | open | LOW | Core | Logging | Simple | OPS-02 |
| GitHub Actions | done | LOW | Ops | CI/CD | Simple | OPS-03 |
| Trip Edit UI | done | HIGH | WebUI | Frontend | Medium | UI-01 |
| Compare E-Mail | done | MEDIUM | WebUI | Frontend, Email | Medium | UI-02 |
| Cloud Layers | done | MEDIUM | WebUI | Frontend, Provider | Medium | UI-03 |
| GPX Upload (WebUI) | done | HIGH | WebUI | Frontend | Simple | GPX-Story1 |
| GPX Parser & Validation | done | HIGH | Core | GPX Parser | Medium | GPX-Story1 |
| Höhenprofil-Analyse | done | HIGH | Core | Elevation Analysis | Medium | GPX-Story1 |
| Zeit-Segment-Bildung | done | HIGH | Core | Segmentation Engine | Medium | GPX-Story1 |
| Hybrid-Segmentierung | done | HIGH | Core | Segmentation Engine | Medium | GPX-Story1 |
| Etappen-Config (WebUI) | done | HIGH | WebUI | Frontend, Config | Medium | GPX-Story1 |
| Segment-Übersicht (WebUI) | done | HIGH | WebUI | Frontend | Simple | GPX-Story1 |
| Segment-Wetter-Abfrage | done | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Basis-Metriken | done | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Erweiterte Metriken | done | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Segment-Aggregation | done | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Wetter-Cache | done | HIGH | Services | Weather Engine | Simple | GPX-Story2 |
| Change-Detection | done | HIGH | Services | Weather Engine | Medium | GPX-Story2 |
| Wetter-Config (WebUI) | done | HIGH | WebUI | Frontend | Simple | GPX-Story2 |
| Email Trip-Formatter | done | HIGH | Formatter | Report Generation | Medium | GPX-Story3 |
| SMS Compact Formatter | done | HIGH | Formatter | Report Generation | Simple | GPX-Story3 |
| Report-Scheduler | done | HIGH | Services | Scheduler | Medium | GPX-Story3 |
| Alert bei Änderungen | done | HIGH | Services | Alert System | Simple | GPX-Story3 |
| Weather Snapshot Service | done | HIGH | Services | Alert System, Scheduler | Medium | ALERT-01 |
| Letzter Waypoint fehlt in Trip-Report | done | HIGH | Bugfix | Segment Weather, Scheduler | Simple | BUG-01 |
| AROME: Visibility/UV nicht verfuegbar | done | LOW | Provider | Provider Layer | Medium | WEATHER-05 + WEATHER-06 |
| Report-Config (WebUI) | done | HIGH | WebUI | Frontend | Simple | GPX-Story3 |

## Completed Features (Last 10)

| Feature | Completed | Category | Notes |
|---------|-----------|----------|-------|
| Model-Metric-Fallback | 2026-02-16 | Provider | Phase A: Empirischer Probe aller Modelle. Phase B: Automatischer Fallback-Call fuer fehlende Metriken (visibility, precip_prob, freezing_level via ICON-EU). |
| Provider Error Handling | 2026-02-16 | Provider | Catches ProviderRequestError, renders error warnings in emails, service emails for SMS-only trips |
| GPX Parser & Validation | 2026-02 | Core | gpxpy-basiert, 13 Tests mit echten GPX-Dateien |
| Höhenprofil-Analyse | 2026-02 | Core | Sliding-Window Peak/Valley Detection |
| Zeit-Segment-Bildung | 2026-02 | Core | Naismith's Rule, konfigurierbare Geschwindigkeiten |
| Hybrid-Segmentierung | 2026-02 | Core | Waypoint-Snapping mit Prioritäten |
| Etappen-Config (WebUI) | 2026-02 | WebUI | Datum, Startzeit, Geschwindigkeits-Parameter |
| Segment-Übersicht (WebUI) | 2026-02 | WebUI | Tabelle + "Als Trip speichern" |
| Report Types | 2026-02 | Formatter | evening/morning/alert via CLI, Scheduler, Alert-Service |
| Compact Formatter | 2026-02 | Formatter | SMS ≤160 Zeichen mit harter Constraint |
| Report-Config (WebUI) | 2026-02 | WebUI | Per-Trip Morning/Evening Zeiten, Metriken-Config |

## Known Bugs

| Bug | Severity | Location | Description |
|-----|----------|----------|-------------|
| ~~BUG-01: Letzter Waypoint fehlt~~ | ~~HIGH~~ | SOLVED | Geloest: `ff6a116` — Ziel-Segment wird jetzt als eigener Forecast abgefragt |
| ~~BUG-02: AROME Visibility/UV~~ | ~~LOW~~ | SOLVED | Visibility: WEATHER-05 Fallback ICON-EU. UV: WEATHER-06 Air Quality API (CAMS) |

## Blocked Features

| Feature | Blocked By | Notes |
|---------|------------|-------|
| _(keine)_ | | |

## Upcoming (Next 3 Sprints)

### Sprint 1 (Current)
- [ ] CLI Entry Point (in_progress, --config fehlt)
- [ ] Config System (in_progress, INI-Parsing fehlt)
- [ ] Debug Architecture (in_progress, Email-Integration fehlt)

### Sprint 2
- [ ] MET Norway Adapter (spec exists)
- [x] Data Normalization (done — Provider-Adapter-Pattern mit NormalizedTimeseries)
- [ ] Gewitter Risk Logic

### Sprint 3
- [ ] Starkregen Risk
- [ ] MOSMIX Adapter
- [ ] Logging/Rotation

## Feature Categories

### Core (Infrastructure)
- CLI Entry Point, Config System, Debug Architecture, Retry Logic, Logging

### Provider (Weather Data Sources)
- MET Norway, MOSMIX, Open-Meteo (done), Data Normalization, Error Handling, Model-Metric-Fallback (done), UV via Air Quality API

### Risk Engine (Weather Assessment)
- Gewitter Risk, Starkregen Risk, Wind/Hitze Risk, Configurable Thresholds

### Formatter (Report Generation)
- Report Types (done), Compact Formatter (done)

### Channel (Delivery)
- SMTP Mailer (done)

### WebUI (Frontend)
- Trip Edit (done), Compare E-Mail (done), Cloud Layers (done), GPX Upload (done), Etappen-Config (done), Segment-Übersicht (done)

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
