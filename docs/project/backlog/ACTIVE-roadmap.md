# Active Roadmap - Gregor Zwanziger (Archiv)

**Last Updated:** 2026-04-14 (M5c Weather Config Endpoints)

> **Offene Features, Bugs und Migration-Tasks sind auf GitHub Issues:**
> https://github.com/henemm/gregor_zwanzig/issues
>
> Diese Datei dient nur noch als **Archiv fuer erledigte Features**.
> Neue Features werden als GitHub Issues angelegt.

## Completed Features

| Feature | Completed | Category | Notes |
|---------|-----------|----------|-------|
| CLI Entry Point | 2025-12 | Core | SETUP-02 |
| Config System (INI/ENV) | 2025-12 | Core | SETUP-03 |
| Debug Architecture | 2025-12 | Core | SETUP-04 |
| Open-Meteo Provider | 2026-01 | Provider | Regional Models (AROME, ICON-EU) |
| Data Normalization | 2026-01 | Provider | WEATHER-03 |
| Gewitter Risk Logic | 2026-02-16 | Risk Engine | CAPE-basiert, `_parse_thunder_level()` |
| Starkregen Risk | 2026-02-16 | Risk Engine | Niederschlags-Intensitaet |
| Wind/Hitze Risk | 2026-02-16 | Risk Engine | Windboeen + Hitze-Warnung |
| Provider Error Handling | 2026-02-16 | Provider | ProviderRequestError, Warnings in Emails |
| Configurable Thresholds | 2026-02 | Config | Risk Engine Schwellen konfigurierbar |
| Snapshot Coordinates Fix | 2026-04-12 | Bugfix | Trip reports no longer crash on missing start/end coords |
| Report Types | 2026-01 | Formatter | Morning, Evening, Alert |
| Compact Formatter | 2026-01 | Formatter | <=160 Zeichen |
| SMTP Mailer | 2025-12 | Channel | Gmail SMTP, E2E getestet |
| Retry Logic | 2026-02 | Core | Tenacity-basiert |
| GitHub Actions | 2026-01 | Ops | Lint + Test CI |
| Trip Edit UI | 2026-01 | WebUI | NiceGUI CRUD |
| Compare E-Mail | 2026-01 | WebUI | Skigebiet-Vergleich |
| Cloud Layers | 2026-01 | WebUI | Low/Mid/High Wolkenhoehen |
| GPX Upload (WebUI) | 2026-02 | WebUI | Drag & Drop Upload |
| GPX Parser & Validation | 2026-02 | Core | Komoot GPX 1.0/1.1 |
| Hoehenprofil-Analyse | 2026-02 | Core | Peak/Valley Detection |
| Zeit-Segment-Bildung | 2026-02 | Core | Naismith's Rule |
| Hybrid-Segmentierung | 2026-02 | Core | Snap to Peaks/Valleys |
| Etappen-Config (WebUI) | 2026-02 | WebUI | Segment-Uebersicht |
| Segment-Wetter-Abfrage | 2026-02 | Services | Multi-Segment Forecast |
| Basis-Metriken | 2026-02 | Services | Temp, Wind, Regen |
| Erweiterte Metriken | 2026-02 | Services | UV, Wolken, Sicht |
| Segment-Aggregation | 2026-02 | Services | MIN/MAX/AVG/SUM |
| Wetter-Cache | 2026-02 | Services | API Response Cache |
| Change-Detection | 2026-02 | Services | Delta-Vergleich |
| Wetter-Config (WebUI) | 2026-02 | WebUI | Metrik-Auswahl |
| Email Trip-Formatter | 2026-02 | Formatter | HTML + Plaintext |
| SMS Compact Formatter | 2026-02 | Formatter | <=160 Zeichen Trip |
| Report-Scheduler | 2026-02 | Services | APScheduler Cron |
| Alert bei Aenderungen | 2026-02 | Services | Threshold-basiert |
| Weather Snapshot Service | 2026-02 | Services | Forecast State Capture |
| Report-Config (WebUI) | 2026-02 | WebUI | Morning/Evening Zeiten |
| Kompakt-Summary | 2026-02-17 | Formatter | Natural-language Summary |
| Multi-Day Trend | 2026-02-17 | Formatter | Etappen-Ausblick |
| Wind-Exposition (Grat-Erkennung) | 2026-02-18 | Risk Engine | `WindExpositionService` |
| Wind-Exposition Pipeline | 2026-02-18 | Risk Engine | `detect_exposed_from_segments()` |
| Wind-Exposition Config | 2026-02-18 | Config | Per-Trip min_elevation_m |
| Risk Engine (Daten-Layer) | 2026-02-18 | Risk Engine | MetricCatalog, Risiko-Kategorisierung |
| Model-Metric-Fallback | 2026-02 | Provider | WEATHER-05, Verfuegbarkeits-Probe |
| UV-Index via Air Quality API | 2026-02 | Provider | CAMS, WEATHER-06 |
| Generische Locations (Metrik-Auswahl) | 2026-03 | WebUI | F11, Profil-Dropdown |
| Subscription Metriken-Auswahl (Model+UI) | 2026-04 | WebUI | F14a, Display-Config Dialog |
| Channel-Switch fuer Subscriptions | 2026-04 | WebUI | F12a, Email/Signal |
| GPX Proxy (Go + FastAPI) | 2026-04-14 | API | M5a: GpxProxyHandler leitet Multipart-Upload an Python weiter, gpx_to_stage_data() liefert Stage+Waypoints |
| Subscriptions CRUD (Go) | 2026-04-14 | API | M5b: 5 REST-Endpoints fuer CompareSubscription, Single-File Storage, Validierung, Legacy-Migration, 409 Duplicate Check |
| Weather Config Endpoints (Go) | 2026-04-14 | API | M5c: 6 GET/PUT-Endpoints fuer display_config auf Trip, Location und Subscription als opaque JSON |

## Solved Bugs

| Bug | Solved | Notes |
|-----|--------|-------|
| BUG-01: Letzter Waypoint fehlt | 2026-02 | Commit `ff6a116` |
| BUG-02: AROME Visibility/UV | 2026-02 | Fallback ICON-EU + CAMS |
| BUG-SNAP-01: Snapshot-Koordinaten fehlten | 2026-04-12 | Alert-API-Calls gingen an (0.0, 0.0); Formatter crashte bei elevation_m=None |
| BUG-IMAP-01: IMAP nutzte SMTP-Credentials | 2026-04-12 | inbound_email_reader.py las smtp_user/smtp_pass statt imap_user/imap_pass |
