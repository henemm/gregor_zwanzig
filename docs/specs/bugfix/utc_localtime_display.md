---
entity_id: utc_localtime_display
type: bugfix
created: 2026-03-03
updated: 2026-03-03
version: "1.0"
status: draft
severity: HIGH
tags: [trip-report, timezone, daylight, formatter, display]
---

# Bugfix: Report-Zeiten in UTC statt Lokalzeit

## Approval

- [ ] Approved for implementation

## Symptom

Alle Uhrzeiten im Trip-Report werden in **UTC** angezeigt statt in der **Lokalzeit des Standorts**. Für Mallorca (CET = UTC+1) sind alle Zeiten 1 Stunde zu früh.

**Beispiel: GR221 Mallorca — Tag 3 (Sóller → Tossals Verds)**

- "Ohne Stirnlampe: **06:13** – 17:42" → sollte **07:13** – 18:42 sein
- Stündliche Tabelle zeigt "06, 07, 08..." → sollte "07, 08, 09..." sein
- "Gewitter möglich ab 14:00" → sollte "15:00" sein

**Business Impact:**
- Wanderer plant mit falschen Zeiten → Stirnlampe zu früh eingepackt, oder im Dunkeln losgelaufen
- Besonders kritisch bei Tageslicht-Feature: das ganze Feature wird nutzlos wenn Zeiten falsch sind

## Root Cause

1. **Astral-Bibliothek** (`daylight_service.py:68-71`): `dawn()`, `sunrise()` etc. werden mit `tzinfo=timezone.utc` aufgerufen — korrekt intern, aber keine Konvertierung vor Anzeige
2. **OpenMeteo API** (`openmeteo.py:209,429,593`): Parameter `"timezone": "UTC"` → alle `dp.ts` Timestamps sind UTC
3. **Formatter** (`trip_report.py`, `compact_summary.py`, `sms_trip.py`): `.strftime('%H:%M')` und `.hour` direkt auf UTC-Datetimes ohne Konvertierung

## Design-Entscheidung: Convert at Render Time

### Invariante: Interne Pipeline bleibt 100% UTC

Die gesamte interne Datenverarbeitung MUSS in UTC bleiben. Begründung:

- **Fallback-Model-Merging** (`openmeteo.py:288-310`): Matcht Timestamps exakt per Dict-Key → verschiedene Zeitzonen = Merge bricht
- **UV-Daten-Merging** (`openmeteo.py:621-637`): Naive-Datetime-Lookup → Timezone-Mismatch = UV-Daten verloren
- **Daylight-Wetterkorrektur** (`daylight_service.py:94-95`): Vergleicht Astral-UTC mit Forecast-UTC → Mismatch = falsche Wetterpenalties
- **Segment-Filterung** (`trip_report.py:129`): `start_h <= dp.ts.hour <= end_h` → Stunden müssen konsistent sein
- **API-Contract** (`docs/reference/api_contract.md`): "Zeit: ISO-8601 UTC (Z)" — Systemweite Garantie

**Konsequenz:** Provider, Services, Models, DaylightWindow — KEINE Änderungen. Konvertierung NUR im Formatter.

### Segment-Header-Zeiten: NICHT konvertieren

User gibt "08:00" als Startzeit ein (meint Lokalzeit). Das wird als "08:00 UTC" gespeichert. Anzeige als "08:00" ist zufällig korrekt. Eine UTC→Lokal-Konvertierung würde "09:00" anzeigen — falsch.

**Regel:** Segment `start_time`/`end_time` aus User-Input werden NICHT konvertiert. Nur Provider-Daten (`dp.ts`) und berechnete Zeiten (Astral) werden konvertiert.

## Betroffene Dateien

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `src/utils/timezone.py` | Utility: Koordinaten→Timezone, UTC→Lokal-Konvertierung |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `pyproject.toml` | Dependency `timezonefinder` hinzufügen |
| `src/formatters/trip_report.py` | `tz`-Parameter empfangen, ~25 Display-Stellen konvertieren |
| `src/formatters/compact_summary.py` | `tz`-Parameter empfangen, 6 Display-Stellen konvertieren |
| `src/formatters/sms_trip.py` | `tz`-Parameter empfangen, 1 Display-Stelle konvertieren |
| `src/services/trip_report_scheduler.py` | `trip_tz` berechnen, an Formatter durchreichen |

### NICHT geänderte Dateien

| Datei | Begründung |
|-------|------------|
| `src/providers/openmeteo.py` | `"timezone": "UTC"` bleibt — Pipeline-Invariante |
| `src/services/daylight_service.py` | DaylightWindow bleibt UTC — Formatter konvertiert |
| `src/app/models.py` | Kein neues Feld nötig — Timezone wird aus Koordinaten berechnet |

## Implementation Details

### 1. Utility-Modul `src/utils/timezone.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo

_tf_instance = None

def _get_tf():
    """Lazy singleton — TimezoneFinder lädt ~12MB beim ersten Aufruf."""
    global _tf_instance
    if _tf_instance is None:
        from timezonefinder import TimezoneFinder
        _tf_instance = TimezoneFinder()
    return _tf_instance

def tz_for_coords(lat: float, lon: float) -> ZoneInfo:
    """Koordinaten → ZoneInfo. Fallback UTC bei Fehler."""
    try:
        name = _get_tf().timezone_at(lat=lat, lng=lon)
        if name:
            return ZoneInfo(name)
    except Exception:
        pass
    return ZoneInfo("UTC")

def local_hour(dt: datetime, tz: ZoneInfo) -> int:
    """UTC-Datetime → lokale Stunde."""
    return dt.astimezone(tz).hour

def local_fmt(dt: datetime, tz: ZoneInfo, fmt: str = "%H:%M") -> str:
    """UTC-Datetime → formatierter String in Lokalzeit."""
    return dt.astimezone(tz).strftime(fmt)
```

### 2. Scheduler: Timezone berechnen und durchreichen

In `_send_trip_report()`, nach Extraktion der Koordinaten des ersten Segments:

```python
from utils.timezone import tz_for_coords
trip_tz = tz_for_coords(first_seg.start_point.lat, first_seg.start_point.lon)
```

Durchreichen an:
- `TripReportFormatter.format_email(..., tz=trip_tz)`
- `_build_thunder_forecast(..., tz=trip_tz)`
- `SMSTripFormatter.format_sms(..., tz=trip_tz)` (falls SMS aktiv)

### 3. TripReportFormatter: `self._tz` Pattern

```python
def format_email(self, ..., tz: ZoneInfo | None = None) -> EmailPayload:
    self._tz = tz or ZoneInfo("UTC")
    # ... rest wie bisher
```

Alle privaten Methoden nutzen `self._tz`. Kein Parameter-Threading nötig.

### 4. Konvertierungsstellen (vollständig)

#### trip_report.py — Aus `dp.ts` (Provider-Daten):

| Zeile | Alt | Neu |
|-------|-----|-----|
| 262 | `f"{dp.ts.hour:02d}"` | `f"{local_hour(dp.ts, self._tz):02d}"` |
| 184 | `dps[0].ts.hour` (Night-Block) | `local_hour(dps[0].ts, self._tz)` |
| 129 | `start_h <= dp.ts.hour <= end_h` | `start_h <= local_hour(dp.ts, self._tz) <= end_h` |
| 125-126 | `seg_data.segment.start_time.hour` (Filterung) | NICHT ändern — s. Design-Entscheidung |
| 346 | `dp.ts.strftime('%H:%M')` (Gewitter) | `local_fmt(dp.ts, self._tz)` |
| 367 | `max_gust_ts.strftime('%H:%M')` | `local_fmt(max_gust_ts, self._tz)` |
| 404 | `max_wind_ts.strftime('%H:%M')` | `local_fmt(max_wind_ts, self._tz)` |

#### trip_report.py — Aus Astral (DaylightWindow):

| Zeile | Alt | Neu |
|-------|-----|-----|
| 662 | `dl.usable_start.strftime('%H:%M')` | `local_fmt(dl.usable_start, self._tz)` |
| 662 | `dl.usable_end.strftime('%H:%M')` | `local_fmt(dl.usable_end, self._tz)` |
| 673 | `dl.civil_dawn.strftime('%H:%M')` | `local_fmt(dl.civil_dawn, self._tz)` |
| 678 | `dl.usable_start.strftime('%H:%M')` | `local_fmt(dl.usable_start, self._tz)` |
| 682 | `dl.sunset.strftime('%H:%M')` | `local_fmt(dl.sunset, self._tz)` |
| 687 | `dl.usable_end.strftime('%H:%M')` | `local_fmt(dl.usable_end, self._tz)` |
| 693-694 | civil_dawn, sunrise, sunset `.strftime` | `local_fmt(...)` für alle drei |
| 717-749 | Plain-Text Variante — identische Stellen | `local_fmt(...)` |

#### trip_report.py — Nachtblock-Datumslogik:

| Zeile | Alt | Neu |
|-------|-----|-----|
| ~145 | `dp.ts.date()` | `dp.ts.astimezone(self._tz).date()` |
| ~150 | `is_same_day = dp.ts.date() == first_date` | Vergleich in Lokalzeit |

#### compact_summary.py:

| Zeile | Alt | Neu |
|-------|-----|-----|
| 200 | `h = dp.ts.hour` | `h = local_hour(dp.ts, tz)` |
| 212 | `dp.ts.hour` (peak) | `local_hour(dp.ts, tz)` |
| 302 | `dp.ts.hour` (wind) | `local_hour(dp.ts, tz)` |
| 323 | `dp.ts.hour` (thunder) | `local_hour(dp.ts, tz)` |

#### sms_trip.py:

| Zeile | Alt | Neu |
|-------|-----|-----|
| 192 | `seg_data.segment.start_time.strftime("%Hh")` | NICHT ändern (User-Input) |

#### trip_report_scheduler.py:

| Zeile | Alt | Neu |
|-------|-----|-----|
| 738 | `max_level.ts.strftime('%H:%M')` | `local_fmt(max_level.ts, trip_tz)` |
| 744 | `max_level.ts.strftime('%H:%M')` | `local_fmt(max_level.ts, trip_tz)` |

### 5. Segment-Filterung: Konsistenz-Problem

`_extract_hourly_rows` (Zeile 125-129):
```python
start_h = seg_data.segment.start_time.hour  # "Lokal" (User-Input als UTC)
end_h = seg_data.segment.end_time.hour      # "Lokal" (User-Input als UTC)
if start_h <= dp.ts.hour <= end_h:          # UTC
```

Aktuell: User-Input "09:00" (Lokal) gespeichert als UTC → `start_h=9`. Forecast `dp.ts.hour=9` (UTC, also 10:00 Lokal). Filter matcht "zufällig" weil beide in UTC sind.

**Fix:** NICHT ändern! Beide Seiten sind "falsch" in derselben Richtung → Ergebnis korrekt. Eine einseitige Korrektur (nur dp.ts) würde den Filter brechen.

Nur die **Anzeige** der dp.ts-Stunde im Table-Output wird konvertiert.

## Expected Behavior

**Vorher (Mallorca, CET=UTC+1, März):**
```
🌅 Ohne Stirnlampe: 06:13 – 17:42 (11h 29m)
   Dämmerung 05:58 + 15min (Tal) = 06:13
```

**Nachher:**
```
🌅 Ohne Stirnlampe: 07:13 – 18:42 (11h 29m)
   Dämmerung 06:58 + 15min (Tal) = 07:13
```

**Stündliche Tabelle vorher:** `06 | 07 | 08 | ...`
**Stündliche Tabelle nachher:** `07 | 08 | 09 | ...`

**Duration (11h 29m):** Bleibt identisch — wird aus UTC-Differenz berechnet, nicht aus formatierten Zeiten.

## Known Limitations

- **Segment-Start/Endzeiten** werden NICHT konvertiert (zufällig korrekt durch symmetrischen Fehler)
- **Segment-Filterung** bleibt in UTC (korrekt durch symmetrischen Fehler, s. oben)
- **Timezone pro Trip, nicht pro Segment** — für Timezone-überschreitende Wanderungen ungenau (irrelevant für typische Etappen <50km)
- **TimezoneFinder Fallback:** Bei Koordinaten über Ozeanen oder Fehlern → UTC (wie bisher)
- **Langfristiger Fix:** Datenmodell sollte Segment-Zeiten explizit als Lokalzeit speichern mit Timezone-Feld → separates Feature

## Test Strategy

### TDD RED Test

```python
def test_daylight_banner_shows_local_time():
    """Tageslicht-Zeiten müssen in Lokalzeit angezeigt werden, nicht UTC."""
    # Sóller, Mallorca (CET = UTC+1 im März)
    # Astral civil dawn für 39.77°N 2.72°E am 03.03.2026 ≈ 05:51 UTC = 06:51 CET
    # Mit Tal-Penalty 15min → usable_start ≈ 06:06 UTC = 07:06 CET
    # Report MUSS "07:" zeigen, NICHT "06:"
```

### E2E Verifikation

1. Test-Trip mit Mallorca-Koordinaten erstellen
2. Report über UI triggern
3. E-Mail via IMAP abrufen
4. Prüfen: Daylight-Banner zeigt ~07:xx (nicht 06:xx)
5. Prüfen: Stündliche Tabelle Stunden sind CET
6. Prüfen: Segment-Header noch "09:00" (nicht "10:00")
7. Test-Trip löschen

## Changelog

- 2026-03-03: Initial spec created
