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
| `obsolete` | No longer needed (superseded by other solution) |

## Priority Legend

| Priority | Meaning |
|----------|---------|
| `HIGH` | Critical for MVP or user-requested |
| `MEDIUM` | Important but not urgent |
| `LOW` | Nice-to-have, can wait |

## Features

| Feature | Status | Priority | Category | Affected Systems | Estimate | Story/Epic |
|---------|--------|----------|----------|------------------|----------|------------|
| CLI Entry Point | done | HIGH | Core | CLI | Medium | SETUP-02 |
| Config System (INI/ENV) | done | HIGH | Core | Config | Simple | SETUP-03 |
| Debug Architecture | done | HIGH | Core | Debug | Medium | SETUP-04 |
| ~~MET Norway Adapter~~ | obsolete | ~~HIGH~~ | Provider | Provider Layer | Medium | WEATHER-01 |
| Open-Meteo Provider | done | MEDIUM | Provider | Provider Layer | Medium | - |
| ~~MOSMIX Adapter~~ | obsolete | ~~MEDIUM~~ | Provider | Provider Layer | Large | WEATHER-02 |
| Data Normalization | done | HIGH | Provider | Normalizer | Medium | WEATHER-03 |
| Provider Error Handling | done | MEDIUM | Provider | Provider Layer | Medium | WEATHER-04 |
| Model-Metric-Fallback | done | MEDIUM | Provider | Provider Layer, Cache | Medium | WEATHER-05 |
| UV-Index via Air Quality API | done | MEDIUM | Provider | Provider Layer | Simple | WEATHER-06 |
| Gewitter Risk Logic | done | HIGH | Risk Engine | Risk Engine | Medium | RISK-01 |
| Starkregen Risk | done | MEDIUM | Risk Engine | Risk Engine | Simple | RISK-02 |
| Wind/Hitze Risk | done | LOW | Risk Engine | Risk Engine | Simple | RISK-03 |
| Configurable Thresholds | done | MEDIUM | Config | Risk Engine, Config | Simple | RISK-04 |
| Report Types | done | HIGH | Formatter | Formatter, CLI | Medium | REPORT-01 |
| Compact Formatter | done | MEDIUM | Formatter | Formatter | Simple | REPORT-02 |
| SMTP Mailer | done | HIGH | Channel | Channel Layer | Medium | REPORT-03 |
| Retry Logic | done | MEDIUM | Core | All Layers | Medium | OPS-01 |
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
| Kompakt-Summary | open | HIGH | Formatter | Formatter, Email, SMS | Simple | F2 |
| SMS-Kanal | open | HIGH | Channel | Channel Layer, Formatter | Medium | F1 |
| Multi-Day Trend | open | MEDIUM | Formatter | Formatter, Provider | Simple | F3 |
| Trip-Briefing (Kompakt-Tabelle) | open | MEDIUM | Formatter | Formatter, Scheduler | Medium | F4 |
| Biwak-/Zelt-Modus | open | MEDIUM | Config | Config, Formatter, Night-Block | Simple-Medium | F5 |
| Trip-Umplanung per Kommando | open | MEDIUM | Services | Scheduler, Email-Reply, SMS-Reply | Medium-Large | F6 |
| Wind-Exposition (Grat-Erkennung) | open | LOW | Risk Engine | GPX Elevation, Risk Engine | Medium | F7 |
| Risk Engine (Daten-Layer) | open | LOW | Risk Engine | Risk Engine, Formatter | Large | F8 |
| Satellite Messenger (Garmin inReach) | open | LOW | Channel | Channel Layer, Formatter | Simple | F9 |
| Lawinen-Integration (SLF/EAWS) | open | LOW | Provider | Provider Layer, Risk Engine | Large | F10 |

## Completed Features (Last 10)

| Feature | Completed | Category | Notes |
|---------|-----------|----------|-------|
| UV-Index via Air Quality API | 2026-02-16 | Provider | CAMS Air Quality API, Timestamp-Merge in fetch_forecast() |
| Model-Metric-Fallback | 2026-02-16 | Provider | Phase A: Empirischer Probe aller Modelle. Phase B: Automatischer Fallback-Call fuer fehlende Metriken (visibility, precip_prob, freezing_level via ICON-EU). |
| CLI Entry Point | 2026-02-16 | Core | python -m src.app.cli, --report, --channel, --debug flags |
| Debug Architecture | 2026-02-16 | Core | Debug-Buffer mit Email-Integration |
| Retry Logic | 2026-02-16 | Core | tenacity-basiert, Provider + SMTP |
| Gewitter Risk Logic | 2026-02-16 | Risk Engine | CAPE-basiert, _parse_thunder_level() in OpenMeteo |
| Starkregen Risk | 2026-02-16 | Risk Engine | Niederschlags-Intensitaet in Formatter |
| Wind/Hitze Risk | 2026-02-16 | Risk Engine | Windboeen + Hitze-Warnung in Formatter |
| Provider Error Handling | 2026-02-16 | Provider | Catches ProviderRequestError, renders error warnings in emails |
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

### Sprint 1 (Current) — Quick Wins
- [ ] Kompakt-Summary (F2, Gering — enabler fuer SMS + Satellite)
- [ ] Multi-Day Trend (F3, Gering — 3-5 Tage Trend im Evening-Report)
- [ ] Biwak-/Zelt-Modus (F5, Gering-Mittel — erweiterter Night-Block)

### Sprint 2 — SMS/Satellite-Kanal
- [ ] SMS-Kanal (F1, Mittel — setzt F2 voraus)
- [ ] Satellite Messenger / Garmin inReach (F9, Gering — setzt F2 voraus)
- [ ] Logging/Rotation (OPS-02)

### Sprint 3 — Trip Intelligence
- [ ] Trip-Briefing Kompakt-Tabelle (F4, Mittel)
- [ ] Trip-Umplanung per Kommando (F6, Mittel-Hoch)

## Feature Categories

### Core (Infrastructure)
- CLI Entry Point (done), Config System (done), Debug Architecture (done), Retry Logic (done), Logging

### Provider (Weather Data Sources)
- ~~MET Norway~~ (obsolete), ~~MOSMIX~~ (obsolete), Open-Meteo (done), Data Normalization (done), Error Handling (done), Model-Metric-Fallback (done), UV via Air Quality API (done)

### Risk Engine (Weather Assessment)
- Gewitter Risk (done), Starkregen Risk (done), Wind/Hitze Risk (done), Configurable Thresholds (done)
- Risk Engine Daten-Layer (F8), Wind-Exposition (F7), Lawinen-Integration (F10)

### Formatter (Report Generation)
- Report Types (done), Compact Formatter (done)
- Kompakt-Summary (F2), Multi-Day Trend (F3), Trip-Briefing (F4), Biwak-/Zelt-Modus (F5)

### Channel (Delivery)
- SMTP Mailer (done)
- SMS-Kanal (F1), Satellite Messenger (F9)

### Services (Trip Intelligence)
- Trip-Umplanung per Kommando (F6)

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
