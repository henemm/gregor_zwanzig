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

- [ ] SMS Reports — Moved to Epic: Low-Connectivity Delivery (F1, F2, F9)

- [ ] Push Notification Reports - FUTURE (deprioritized)

**Target Completion:** Q1 2026 (Email done) — SMS moved to dedicated epic

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
  - **Model-Metric-Fallback (WEATHER-05):** Verfuegbarkeits-Probe + Fallback fuer fehlende Metriken
    - Feature-Spec: `features/model-metric-fallback.md`

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

### Epic: Low-Connectivity Delivery (SMS/Satellite)

**Goal:** Wetter-Reports ueber SMS und Satellit zustellen — fuer Situationen ohne Internet

**Business Value:** Auf GR20/GR221 oft nur GSM verfuegbar, kein Internet. SMS ist Game-Changer. Garmin inReach ermoeglicht Empfang ueber Baumgrenze.

**Status:** Planned

**Dependencies:** F2 (Kompakt-Summary) ist Enabler fuer alle Kanaele

**User Stories:**
- [ ] Kompakt-Summary (F2) — Prerequisite
  - 3-5 Zeilen Kurzfassung, SMS-kompatibles Format
  - Enabler fuer SMS + Satellite

- [ ] SMS-Kanal (F1)
  - SMS Gateway Integration (Twilio o.ae.)
  - SMS Formatter (<=160 Zeichen)
  - SMS Config pro Trip

- [ ] Satellite Messenger / Garmin inReach (F9)
  - Email-Bridge (160 Zeichen) an Garmin inReach
  - Baut auf F2 Kompakt-Format auf

**Target Completion:** Q2 2026

---

### Epic: Enhanced Trip Reports

**Goal:** Reports mit mehr Kontext — Trends, Biwak-Details, Trip-Briefing

**Business Value:** Mehrtages-Strategie und Ruhetag-Planung. Zelter bekommen relevante Nacht-Details. Trip-Briefing am Vorabend gibt Gesamtueberblick.

**Status:** Planned

**User Stories:**
- [ ] Multi-Day Trend (F3)
  - 3-5 Tage Trend-Block im Evening-Report
  - Emoji-basiert: `Mo☀️18° Di🌤15° Mi🌧12°⚠️`

- [ ] Biwak-/Zelt-Modus (F5)
  - Uebernachtungstyp pro Etappe (Huette/Zelt/Biwak)
  - Erweiterter Night-Block bei Zelt/Biwak

- [ ] Trip-Briefing Kompakt-Tabelle (F4)
  - Einmaliger Report am Vorabend
  - Alle Etappen als Tabelle (Tag | Temp | Wind | Regen | Besonderheit)

**Target Completion:** Q2 2026

---

### Epic: Asynchrone Trip-Steuerung

**Goal:** Trip unterwegs per Kommando anpassen — ohne Web-UI

**Business Value:** Innovativstes Feature. Asynchrone Steuerung per SMS/Email-Reply. Passt perfekt zum Low-Connectivity-Paradigma.

**Status:** Planned

**Dependencies:** F1 (SMS-Kanal) fuer SMS-Reply, Email-Reply als Einstieg

**User Stories:**
- [ ] Trip-Umplanung per Kommando (F6)
  - "Ruhetag heute" → Folge-Etappen +1 Tag verschieben
  - Email-Reply und SMS-Reply als Input-Kanal
  - Bestaetigung per SMS/Email

**Target Completion:** Q3 2026

---

### Epic: Advanced Risk & Terrain Analysis

**Goal:** Risiko-Kategorisierung und terrain-bewusste Warnungen

**Business Value:** Differenzierte Darstellung (low/med/high) pro Metrik. Wind-Exposition beruecksichtigt Gelaendef orm. Lawinen-Daten fuer Skitouren.

**Status:** Planned

**Dependencies:** F8 ist Enabler fuer F7

**User Stories:**
- [ ] Risk Engine Daten-Layer (F8)
  - Risiko-Kategorisierung (low/med/high) pro Metrik
  - OHNE Handlungsempfehlung — reine Daten
  - Draft-Spec existiert

- [ ] Wind-Exposition / Grat-Erkennung (F7)
  - Aus GPX-Profil exponierte Abschnitte erkennen
  - Wind-Warnung fuer Grat/Gipfel verschaerfen

- [ ] Lawinen-Integration (F10)
  - SLF/EAWS Adapter
  - Datenmodell hat bereits `avalanche_regions`
  - Naechste Wintersaison

**Target Completion:** Q3 2026 (F8, F7), Winter 2026/27 (F10)

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
