# Bug #6: Trips hat aufgehört zu schicken

## Analyse (2026-04-12)

### Symptom
Trip-Reports (Morning/Evening E-Mails) werden seit ~6. April nicht mehr versendet.

### Root Causes (3 unabhaengige Probleme)

#### A: Service Crash-Loop (P0 — Hauptursache)
- **Datei:** `src/web/main.py`, `/etc/systemd/system/gregor_zwanzig.service`
- **Problem:** Service crasht mit `[Errno 98] address already in use` auf Port 8080
- **Ursache:** Nach Restart haelt der alte Prozess den Port noch (TIME_WAIT). `RestartSec=5` ist zu kurz.
- **Wirkung:** 71.382 Crashes, Scheduler laeuft nie, 0 Reports gesendet
- **Fix:** Systemd-Unit: `RestartSec=10`, `TimeoutStopSec=15`. Nicht im Scope dieses Repos (→ henemm-infra).

#### B: Trip-Daten inkonsistent (BEHOBEN)
- **Datei:** `data/users/default/trips/gr221-mallorca.json`
- **Problem:** T1=2026-04-05, T2-T4=Februar 2026 (inkonsistent)
- **Fix:** T2→2026-04-06, T3→2026-04-07, T4→2026-04-08 ✅

#### C: Koordinaten 0.0 bei Alert-Checks (P1 — Design-Bug)
- **Datei:** `src/services/weather_snapshot.py`
- **Problem:** `_reconstruct_segment()` erstellt Dummy-GPXPoints mit lat=0.0, lon=0.0
- **Ursache:** Snapshot persistiert keine Koordinaten, nur segment_id/start_time/end_time
- **Wirkung:** Alert-API-Calls gehen an Golf von Guinea statt echte Locations
- **Fix:** Koordinaten beim Snapshot-Save mit persistieren

#### D: NoneType Crash im Alert-Formatter (Folge von C)
- **Datei:** `src/formatters/trip_report.py` (mehrere Stellen)
- **Problem:** `int(seg.start_point.elevation_m)` crasht bei elevation_m=None
- **Fix:** None-Guard hinzufuegen

### Scope
- **Code-Fixes:** 2 Dateien (weather_snapshot.py, trip_report.py)
- **Infra-Fix:** Systemd-Unit (anderes Repo: henemm-infra)
- **Daten-Fix:** gr221-mallorca.json (bereits erledigt)
- **Geschaetzt:** ~30 LoC
