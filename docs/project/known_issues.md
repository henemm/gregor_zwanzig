# Known Issues & Bug Report Log (Archiv)

> **Offene Bugs sind auf GitHub Issues:**
> https://github.com/henemm/gregor_zwanzig/issues?q=label%3Abug
>
> Diese Datei bleibt als Detail-Referenz fuer Root-Cause-Analysen bestehen.

## BUG-SNAP-01: Snapshot Coordinates Missing — Alert Calls Sent to (0.0, 0.0)

**Status:** RESOLVED (2026-04-12) | **Severity:** High | **Spec:** `docs/specs/bugfix/snapshot_missing_coordinates.md`

### Symptom

Alert checks called Open-Meteo with `lat=0.0, lon=0.0` (Gulf of Guinea) instead of actual trip coordinates. The trip report formatter also crashed with `TypeError: int() argument must be ... not 'NoneType'` when elevation_m was None.

### Root Cause

`weather_snapshot.py save()` only stored `segment_id`, `start_time`, `end_time` — no coordinates. On load, `_reconstruct_segment()` created `GPXPoint(lat=0.0, lon=0.0)` as placeholder. `trip_report.py` called `int(seg.start_point.elevation_m)` without a None guard.

### Fix

- `save()` now writes `start_lat`, `start_lon`, `start_elevation_m`, `end_lat`, `end_lon`, `end_elevation_m` per segment
- `_reconstruct_segment()` reads these fields with `.get(..., 0.0)` fallback (backwards compatible)
- `trip_report.py` replaced all 7 `int(elevation_m)` calls with `int(elevation_m or 0)`

### Files Changed

`src/services/weather_snapshot.py`, `src/formatters/trip_report.py`, `tests/tdd/test_snapshot_coordinates.py`

---

## BUG-IMAP-01: IMAP Reader Used SMTP Credentials

**Status:** RESOLVED (2026-04-12) | **Severity:** Medium

### Symptom

`InboundEmailReader` failed to authenticate against IMAP because it passed `smtp_user`/`smtp_pass` from config instead of the dedicated IMAP credentials.

### Root Cause

`src/services/inbound_email_reader.py` read `settings.smtp_user` and `settings.smtp_pass` for the IMAP login. SMTP and IMAP use separate accounts/credentials.

### Fix

`inbound_email_reader.py` now reads `settings.imap_user` / `settings.imap_pass`. `src/app/config.py` and `src/web/scheduler.py` updated accordingly.

### Files Changed

`src/app/config.py`, `src/services/inbound_email_reader.py`, `src/web/scheduler.py`

---

## BUG-TZ-01: Timezone Mismatch — All Trip Report Times in UTC

**GitHub Issue:** #21 | **Status:** Confirmed | **Severity:** High | **Date:** 2026-03-03

### Symptom

All timestamps in trip reports display in UTC instead of local time for the trip location:

- **Daylight Banner ("Ohne Stirnlampe"):** Shows 06:13 for Soller (Mallorca) instead of 07:13 (CET = UTC+1)
- **Hourly Weather Table:** All times 1h early (UTC instead of CET+1)
- **Thunder Highlights:** Times formatted as UTC
- **Wind Peak Labels:** Formatted as UTC
- **Compact Summary:** Peak times referenced in UTC
- **SMS Trip Formatter:** Start times in UTC

### Root Cause (Summary)

Multi-point failure across 5 files:
1. `src/services/daylight_service.py` — astral hardcoded to UTC
2. `src/providers/openmeteo.py` — API requests `"timezone": "UTC"`
3. `src/formatters/trip_report.py` — direct `.hour` on UTC datetimes
4. `src/formatters/compact_summary.py` — direct `.hour` on UTC
5. `src/formatters/sms_trip.py` — `.strftime()` on UTC

### Fix Strategy

Wird moeglicherweise durch Tech-Stack-Migration (M2, #23) direkt geloest.
Falls vorher gefixt: `timezonefinder` + `TimezoneService` + Formatter-Anpassungen.
