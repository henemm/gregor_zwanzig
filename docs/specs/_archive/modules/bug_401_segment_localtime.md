---
entity_id: bug_401_segment_localtime
type: module
created: 2026-05-26
updated: 2026-05-27
status: draft
version: "1.1"
tags: [bug, timezone, scheduler, trip_report, segment, night_block, alert]
---

# Bug #400 + #401 — Lokalzeit-Korrektur (Alert-Mail tz + Segment-Startzeiten)

> Kombinierter Workflow `bug-400-401-timezone-localtime`. Zwei verwandte
> Timezone-Bugfixes mit gemeinsamer Wurzel (`utils.timezone.tz_for_coords`).

## Approval

- [ ] Approved

## Purpose

**Bug #400:** `_send_alert()` in `trip_alert.py` ruft `format_email()` ohne `tz=` auf →
Default `ZoneInfo("UTC")` → Alert-Mails zeigen UTC-Zeiten in Segment-Headern statt Lokalzeit.

**Bug #401:** Abfahrtszeiten, die der User im Wizard eingibt ("08:00" = 8 Uhr morgens lokal),
werden in `_convert_trip_to_segments` mit `tzinfo=timezone.utc` abgestempelt statt korrekt
lokal→UTC zu konvertieren. Für CEST-Nutzer (UTC+2) werden dadurch Wetterdaten für die falsche
Tageszeit geladen (2h zu spät).

**Status:** Bug #398 (`arrival_hour = local_hour(...)`) und #399 (Mitternachts-Übergang) wurden
in Commit `2eb9169` bereits behoben. Diese Spec fokussiert ausschließlich auf `_convert_trip_to_segments`
(eine Stelle, ~6 Zeilen). Die bestehenden Fixes (#398/#399) sind mit dieser Änderung kompatibel
und bleiben korrekt.

## Source

- **Layer:** Backend / Scheduler
- **Scope:** 1 Datei, ~6 geänderte Zeilen, kein Frontend-Change

| Datei | Änderungstyp |
|-------|-------------|
| `src/services/trip_alert.py` | Bug #400: `tz_for_coords`-Import + `tz=` in `format_email()`-Aufruf in `_send_alert()` |
| `src/services/trip_report_scheduler.py` | Bug #401: Fix in `_convert_trip_to_segments` (Z. 587–596) |
| `tests/tdd/test_bug_400_alert_tz.py` | Bug #400: Source-Inspection-Tests |
| `tests/tdd/test_bug_401_segment_localtime.py` | Bug #401: Source-Inspection + CEST→UTC-Integration |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/utils/timezone.py` | Upstream | `tz_for_coords`, `local_hour` — bereits in beiden Dateien verfügbar |
| `src/app/models.py` | Constraint | `TripSegment.start_time/end_time: datetime` mit UTC-tzinfo |
| `tests/tdd/test_issue_397_segment_timezone.py` | Referenz-Tests | Muster für UTC→CEST-Fixtures |
| `docs/specs/modules/bug_397_segment_timezone_display.md` | Vorgänger | Anzeige-Konsistenz; dieser Fix macht Zeitfenster semantisch korrekt |

## Implementation Details

### Fix 0 — Alert-Mail Zeitzone (Bug #400, trip_alert.py)

Top-Level-Import `from utils.timezone import tz_for_coords` ergänzen. In `_send_alert()` vor dem
`format_email()`-Aufruf die Zeitzone aus den Koordinaten des ersten Segments bestimmen und als
`tz=` übergeben:

```python
alert_tz = tz_for_coords(
    weather[0].segment.start_point.lat,
    weather[0].segment.start_point.lon,
)
report = self._formatter.format_email(
    segments=weather,
    trip_name=trip.name,
    report_type="alert",
    display_config=trip.display_config,
    changes=changes,
    profile=trip.aggregation.profile,
    stage_name=stage_name,
    tz=alert_tz,   # NEU — sonst Default ZoneInfo("UTC")
)
```

### Fix 1 — `_convert_trip_to_segments` (trip_report_scheduler.py)

**Ersetze Z. 586–596:**
```python
# Convert time to datetime with UTC timezone
start_dt = datetime.combine(
    target_date,
    wp1_start,
    tzinfo=timezone.utc
)
end_dt = datetime.combine(
    target_date,
    wp2_start,
    tzinfo=timezone.utc
)
```

**Durch:**
```python
# User-konfigurierte Zeiten sind lokale Zeiten (Wizard-Eingabe).
# Koordinaten des ersten Wegpunkts bestimmen die Zeitzone.
from utils.timezone import tz_for_coords
_seg_tz = tz_for_coords(wp1.lat, wp1.lon)
start_dt = (
    datetime.combine(target_date, wp1_start)
    .replace(tzinfo=_seg_tz)
    .astimezone(timezone.utc)
)
end_dt = (
    datetime.combine(target_date, wp2_start)
    .replace(tzinfo=_seg_tz)
    .astimezone(timezone.utc)
)
```

`tz_for_coords` ist bereits am Anfang des Moduls importiert (Z. 328 im Format-Kontext;
der Import-Block im Scheduler muss geprüft / ergänzt werden — `from utils.timezone import tz_for_coords`).

### Kompatibilität mit bereits ausgelieferten Fixes

- **#398 (`arrival_hour = local_hour(end_time, tz)`, Z. 90):** Bleibt korrekt. Nach Fix 1 hat
  `end_time = UTC 12` (für CEST 14:00); `local_hour(UTC 12, CEST) = 14` ✓
- **#399 (Mitternachts-Übergang in `_extract_hourly_rows`):** Bleibt korrekt. `start_h = 6`
  (UTC 6 für CEST 8) ist normaler Stundenwert, kein Mitternachts-Fall.

### `_extract_hourly_rows` — kein Fix nötig

Vergleicht `seg.start_time.hour` (UTC, korrekt nach Fix 1) mit `dp.ts.hour` (UTC, Open-Meteo).
UTC-auf-UTC bleibt konsistent und selektiert nach Fix 1 das richtige Fenster automatisch.

## Expected Behavior

Gegeben: User konfiguriert Abfahrt "08:00" in Corsica (CEST = UTC+2, Sommer).

| | Vorher (Bug) | Nachher (Fix) |
|--|--|--|
| Gespeicherte start_time | 08:00 UTC (= 10:00 CEST) | 06:00 UTC (= 08:00 CEST) ✓ |
| Angezeigte Startzeit | 10:00 CEST | 08:00 CEST ✓ |
| Wetterdaten für | UTC 08–10 = CEST 10–12 | UTC 06–08 = CEST 08–10 ✓ |
| Night-Block ab | CEST 14:00 (acc.) | CEST 14:00 ✓ |

Für UTC-Touren (tz = UTC): `tz_for_coords` liefert UTC, `.replace(tzinfo=utc)` und `local_hour(..., utc)` liefern exakt die gleichen Werte wie vorher → kein Verhaltensunterschied.

## Acceptance Criteria

- **AC-1:** Given `trip_alert.py` / When die Datei nach dem #400-Fix gelesen wird / Then importiert sie `tz_for_coords` (sonst keine Zeitzonen-Quelle für die Alert-Mail)
  - Test: `test_alert_imports_tz_for_coords` (in `tests/tdd/test_bug_400_alert_tz.py`)

- **AC-2:** Given `_send_alert()` ruft `format_email()` auf / When ein Alert versendet wird / Then wird ein `tz=`-Parameter übergeben (aus den Segment-Koordinaten abgeleitet), nicht der UTC-Default
  - Test: `test_alert_passes_tz_to_format_email` (in `tests/tdd/test_bug_400_alert_tz.py`)

- **AC-3:** Given `trip_report_scheduler.py` / When die Datei nach dem #401-Fix gelesen wird / Then importiert sie `from utils.timezone import tz_for_coords` top-level
  - Test: `test_scheduler_imports_tz_for_coords` (in `tests/tdd/test_bug_401_segment_localtime.py`)

- **AC-4:** Given User konfiguriert Abfahrt "08:00" für eine Tour in CEST (UTC+2) / When `_convert_trip_to_segments` ausgeführt wird / Then nutzt der Code `.replace(tzinfo=seg_tz).astimezone(timezone.utc)`, sodass `segment.start_time` UTC 06:00 statt UTC 08:00 ist
  - Test: `test_scheduler_uses_replace_astimezone` (in `tests/tdd/test_bug_401_segment_localtime.py`)

- **AC-5:** Given die Konvertierungslogik / When CEST 08:00 (Europe/Paris, Sommer) konvertiert wird / Then ergibt die echte Konvertierung UTC 06:00
  - Test: `test_cest_to_utc_conversion` (in `tests/tdd/test_bug_401_segment_localtime.py`)

- **AC-6:** Given User kommt um CEST 14:00 (UTC 12:00) am Ziel an / When `format_email` den Night-Block berechnet / Then beginnt `night_rows` bei CEST 14:00, nicht bei 12:00 (Zeile 740 `next_morning` bleibt korrekt UTC)
  - Test: (bereits abgedeckt durch bestehende #398-Tests in `test_bug_397_output_localtime.py`)

## Known Limitations

- `tz_for_coords` macht einen API-Call (timezonefinder-Library, lokal). Falls Koordinaten ungültig oder Library-Fehler: Fallback auf UTC (bestehende Logik des Schedulers unverändert).
- Ankunfts-Zeit am Folgetag (Mitternacht-Überschreitung): kein separater Fix in diesem Scope.

## Changelog

- 2026-05-26: Spec erstellt (Bug #401 + #398, Workflow bug-401-segment-localtime)
