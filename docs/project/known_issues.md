# Known Issues & Bug Report Log (Archiv)

> **Offene Bugs sind auf GitHub Issues:**
> https://github.com/henemm/gregor_zwanzig/issues?q=label%3Abug
>
> Diese Datei bleibt als Detail-Referenz fuer Root-Cause-Analysen bestehen.

## BUG-DATALOSS-GR221: 4 → 1 Stage Konsolidierung (GR221 Mallorca)

**Status:** RESOLVED — Recovery (2026-04-29) | **Severity:** High | **GitHub Issue:** #102

### Symptom

User wanderte den GR221 Ende Februar 2026 über **4 Etappen** (23.–26.02.) und erhielt während der Wanderung täglich Trip-Reports von Gregor Zwanzig. Bei einer späteren Sichtung des Trip-Files war nur noch **1 Stage** ("Tag 1: von Valldemossa nach Deià") vorhanden.

### Forensik

**Git-Spurenlage:**
- `data/users/default/trips/gr221-mallorca.json` taucht erstmalig in Git auf in Commit `51abdad` (2026-04-16) — bereits mit nur 1 Stage
- Vor diesem Commit lebte die Datei rein lokal außerhalb von Git (`data/` wurde erst durch `392ecc0` am 2026-02-11 versioniert, gr221-mallorca war zu dem Zeitpunkt nicht dabei)
- Stash `3f60e9c` (2026-04-29 pre-deploy) enthält ebenfalls nur 1 Stage — der Verlust passierte VOR dem Stash
- **Aber:** Im Stash liegen 4 GPX-Dateien (`Tag 1` bis `Tag 4`) untracked → die GPX-Daten überlebten, nur das aggregierte Trip-JSON war geschrumpft

**Vermutlicher Tatort:** `BUG-03/04` Pattern (gefixt am 2026-02-17 in `8de1a78`):

```python
updated_trip = Trip(
    id=trip_id,
    name=name_input.value,
    stages=stages,         # aus aktuellem UI-State neu gebaut
    avalanche_regions=regions,
)
save_trip(updated_trip)    # überschreibt persistierte Datei
```

Trip-Edit baute neues Trip-Objekt aus dem UI-Form-State, ohne Persistenz-Felder zu erhalten. Wenn das Frontend zu irgendeinem Zeitpunkt nach der Wanderung nur 1 Stage zeigte (z.B. beim Laden eines korrupten oder älteren Zustands) und der User editierte, wurden die anderen Stages überschrieben. `8de1a78` fixte zwar `display_config`/`weather_config`/`report_config`, aber die `stages` selbst wurden weiterhin aus `stages_data` (UI-State) ohne Backend-Merge neu gebaut.

**Limitation der Forensik:** Da die 4-Stage-Version nie comittet war, lässt sich der exakte Konsolidierungs-Commit nicht eindeutig identifizieren. Plausibles Zeitfenster: zwischen Wanderungs-Ende (2026-02-26) und erstem Commit (2026-04-16).

### Recovery

- 4 GPX-Dateien aus Stash `3f60e9c` extrahiert nach `data/users/default/gpx/`
- `gr221-mallorca.json` rekonstruiert: 4 Stages × 4 Waypoints (G1=Start, G2/G3=Zwischenpunkte, G4=Ziel), Datumssequenz 2026-02-23 bis 2026-02-26, Höhen aus GPX-Tracks
- `aggregation.profile=wintersport` und vollständige `report_config` aus Pre-Recovery-Zustand erhalten
- Frontend-Sichtbarkeit verifiziert (`/trips`, `/trips/gr221-mallorca/edit`)

### Lessons Learned

1. **Daten ohne Versionierung sind verloren, sobald sie modifiziert werden** — `data/` gehört von Anfang an in Git (oder zumindest in regelmäßige Backups mit History)
2. **Edit-Handler dürfen niemals Felder fallen lassen, die das UI nicht kennt** — Backend muss Merge statt Replace machen, oder der Client muss Read-Modify-Write korrekt umsetzen
3. **Schema-/Refactor-Reworks brauchen Pre/Post-Snapshot-Tests** — vor jeder Daten-Migration muss eine Roundtrip-Verifikation stattfinden

### Follow-up

- **Issue #99** (Backend Defense-in-Depth): `UpdateTripHandler` macht weiterhin `Replace` statt `Merge` — gleiches Bug-Pattern auf Go-Seite
- **Issue #102 Sub-Task 3** (Migrations-Hygiene): Pre-Rework-Backup-Hook in CLAUDE.md / settings.json

### Files Changed (Recovery)

`data/users/default/trips/gr221-mallorca.json`, `data/users/default/gpx/2026-01-17_*_Tag {1..4}_*.gpx`

---

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
