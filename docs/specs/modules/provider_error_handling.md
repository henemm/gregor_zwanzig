---
entity_id: provider_error_handling
type: module
created: 2026-02-16
updated: 2026-02-16
status: active
version: "1.0"
tags: [resilience, error-handling, email, provider]
---

# Provider Error Handling (WEATHER-04)

## Approval

- [x] Approved
- [x] Implemented (2026-02-16)
- [x] Validated (2026-02-16)

## Purpose

Sichtbare Fehlerbehandlung wenn Wetter-Provider nach allen Retries endgueltig fehlschlagen.
Statt stillem Auslassen fehlgeschlagener Segmente wird der Fehler im E-Mail-Report als
Warn-Zeile angezeigt. Bei SMS-only Trips wird eine Service-E-Mail verschickt.

**Kernregel:** Kein stilles Scheitern. Lieber Report mit Luecke als gar kein Report.

## Erweiterung von

- `docs/specs/modules/api_retry.md` (API-Layer Retry — bereits implementiert)

Diese Spec behandelt die **Service-Layer-Ebene** oberhalb der Retry-Logik.

## Source

| Datei | Aenderung |
|-------|-----------|
| `src/app/models.py:329-335` | SegmentWeatherData um Error-Felder erweitern |
| `src/services/segment_weather.py:125-130` | try/catch um `fetch_forecast()` |
| `src/services/trip_report_scheduler.py:470-502` | Error-Tracking in `_fetch_weather()` |
| `src/services/trip_report_scheduler.py:240-300` | Service-E-Mail bei SMS-only + Fehler |
| `src/formatters/trip_report.py:98-108` | Error-Row Rendering in `_extract_hourly_rows()` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SegmentWeatherData` | dataclass | Traegt Error-Felder |
| `ProviderRequestError` | exception | Wird nach Retry-Exhaustion geworfen |
| `TripReportFormatter` | formatter | Rendert Error-Zeilen |
| `EmailOutput` | output | Sendet Service-E-Mail |
| `TripReportConfig` | dataclass | `send_email`/`send_sms` Flags |

## Implementation Details

### 1. SegmentWeatherData Error-Felder (`models.py`)

```python
@dataclass
class SegmentWeatherData:
    """Weather data for a single trip segment."""
    segment: TripSegment
    timeseries: Optional[NormalizedTimeseries]  # None bei Fehler
    aggregated: SegmentWeatherSummary
    fetched_at: datetime
    provider: str
    # Error tracking
    has_error: bool = False
    error_message: Optional[str] = None
```

Aenderungen:
- `timeseries` wird `Optional` (war vorher nicht-optional)
- Zwei neue Felder mit Defaults (abwaertskompatibel)

### 2. Error-Catching in `segment_weather.py`

```python
# In fetch_segment_weather(), um Zeile 125-130:
try:
    timeseries = self._provider.fetch_forecast(
        location,
        start=segment.start_time,
        end=segment.end_time,
    )
except ProviderRequestError as e:
    logger.error(f"Provider failed for segment {segment.segment_id}: {e}")
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider=self._provider.name,
        has_error=True,
        error_message=str(e),
    )
```

Nur `ProviderRequestError` wird gefangen — andere Fehler (ValueError, etc.) bleiben unbehandelt.

### 3. Error-Tracking in `_fetch_weather()` (`trip_report_scheduler.py`)

Aktuelle Implementierung (Zeile 492-502) faengt Exceptions und loggt nur.
Neue Implementierung: Fehler-Segmente bleiben in der Liste.

```python
def _fetch_weather(self, segments: List[TripSegment]) -> List[SegmentWeatherData]:
    provider = get_provider("openmeteo")
    service = SegmentWeatherService(provider)

    weather_data = []
    for segment in segments:
        try:
            data = service.fetch_segment_weather(segment)
            weather_data.append(data)
        except Exception as e:
            logger.error(f"Weather fetch failed for segment {segment.segment_id}: {e}")
            # Statt auslassen: Error-Placeholder einfuegen
            error_data = SegmentWeatherData(
                segment=segment,
                timeseries=None,
                aggregated=SegmentWeatherSummary(),
                fetched_at=datetime.now(timezone.utc),
                provider="unknown",
                has_error=True,
                error_message=str(e),
            )
            weather_data.append(error_data)

    return weather_data
```

### 4. Service-E-Mail bei SMS-only + Fehler (`trip_report_scheduler.py`)

In `_send_trip_report()` nach dem Formatter-Aufruf:

```python
# Nach Zeile 291 (Email senden):
# Pruefe ob Segmente fehlgeschlagen sind
errors = [s for s in segment_weather if s.has_error]
if errors:
    # Bei SMS-only Trip: Service-E-Mail senden
    config = trip.report_config
    is_sms_only = config and config.send_sms and not config.send_email
    if is_sms_only:
        self._send_service_error_email(trip, errors, report_type)
```

Neue Methode:

```python
def _send_service_error_email(
    self,
    trip: "Trip",
    errors: list[SegmentWeatherData],
    report_type: str,
) -> None:
    """Service-E-Mail bei Provider-Fehler fuer SMS-only Trips."""
    error_lines = "\n".join(
        f"  - Segment {e.segment.segment_id}: {e.error_message}"
        for e in errors
    )
    subject = f"[{trip.name}] Wetterdaten nicht verfuegbar"
    body = (
        f"<h3>Service-Benachrichtigung</h3>"
        f"<p><b>Trip:</b> {trip.name}<br>"
        f"<b>Report:</b> {report_type.title()}<br>"
        f"<b>Problem:</b> Wetterdaten konnten nicht abgerufen werden.</p>"
        f"<p><b>Betroffene Segmente:</b></p>"
        f"<pre>{error_lines}</pre>"
        f"<p><small>Diese E-Mail wurde automatisch gesendet, weil Ihr Trip "
        f"nur SMS aktiviert hat und Anbieter-Fehler aufgetreten sind.</small></p>"
    )
    try:
        EmailOutput(self._settings).send(subject=subject, body=body, html=True)
        logger.info(f"Service error email sent for {trip.name}")
    except Exception as e:
        logger.error(f"Failed to send service error email: {e}")
```

### 5. Error-Row Rendering im Formatter (`trip_report.py`)

In `_extract_hourly_rows()` (Zeile 98-108):

```python
def _extract_hourly_rows(
    self, seg_data: SegmentWeatherData, dc: UnifiedWeatherDisplayConfig,
) -> list[dict]:
    """Extract hourly data points within segment time window."""
    # Error-Segment: keine Daten verfuegbar
    if seg_data.has_error or seg_data.timeseries is None:
        return []

    start_h = seg_data.segment.start_time.hour
    # ... Rest unveraendert
```

In der HTML-Rendering-Methode, wo Segmente iteriert werden — vor dem Tabellen-Block
fuer jedes Segment eine Fehler-Box einfuegen wenn `has_error`:

```html
<!-- Error-Segment -->
<div style="background:#fff3e0; border-left:4px solid #e65100; padding:12px; margin:8px 0;">
  <strong style="color:#e65100;">Wetterdaten nicht verfuegbar</strong>
  <p style="margin:4px 0 0 0; color:#666; font-size:13px;">
    Segment {segment_id}: Anbieter-Fehler nach 5 Versuchen
  </p>
</div>
```

In der Plain-Text-Rendering:

```
--- Segment {segment_id}: WETTERDATEN NICHT VERFUEGBAR ---
Anbieter-Fehler nach 5 Versuchen
```

## Expected Behavior

### Szenario 1: Ein Segment fehlgeschlagen

- **Input:** 3 Segmente, Segment 2 hat Provider-Fehler
- **Output:** E-Mail mit Segment 1 (normal), Segment 2 (Warn-Box), Segment 3 (normal)
- **Subject:** Normaler Report-Betreff (nicht veraendert)
- **Night/Thunder:** Wird normal generiert (nutzt letztes erfolgreiches Segment)

### Szenario 2: Alle Segmente fehlgeschlagen

- **Input:** 3 Segmente, alle haben Provider-Fehler
- **Output:** E-Mail mit 3 Warn-Boxen, Summary-Zeile "Keine Wetterdaten verfuegbar"
- **Night/Thunder:** Wird uebersprungen (kein valides letztes Segment)

### Szenario 3: SMS-only Trip mit Fehler

- **Input:** Trip hat `send_email=False, send_sms=True`, Segment 2 fehlgeschlagen
- **Output:** SMS wird normal generiert (fehlende Segmente ausgelassen),
  PLUS Service-E-Mail mit Fehlerdetails

### Szenario 4: Kein Fehler (Normal-Fall)

- **Input:** Alle Segmente erfolgreich
- **Output:** Unveraendertes Verhalten, keine Error-Felder gesetzt

## Side Effects

- E-Mails koennen Warn-Boxen enthalten (visuell auffaellig, orange)
- SMS-only Trips koennen Service-E-Mails ausloesen
- Snapshot wird auch mit Error-Segmenten gespeichert (fuer spaetere Vergleichbarkeit)

## Known Limitations

- **Kein Provider-Fallback:** Wenn OpenMeteo fehlschlaegt, wird NICHT automatisch GeoSphere versucht.
  Fallback-Chains sind ein separates Feature (ggf. in WEATHER-04 v2.0).
- **Kein Circuit-Breaker:** Wiederholte Fehler desselben Providers werden nicht erkannt.
- **Service-E-Mail nur bei SMS-only:** Wenn `send_email=True`, wird der Fehler nur im Report sichtbar
  (keine separate Benachrichtigung).
- **Error-Message ist technisch:** Zeigt Provider-Name und HTTP-Status, nicht benutzerfreundlich uebersetzt.

## Testplan

### Unit Tests (test_provider_error_handling.py)

1. **test_segment_weather_catches_provider_error:**
   SegmentWeatherService gibt error-flagged SegmentWeatherData zurueck wenn Provider ProviderRequestError wirft.

2. **test_error_segment_has_empty_timeseries:**
   Error-Segment hat `timeseries=None`, `has_error=True`, `error_message` gesetzt.

3. **test_scheduler_includes_error_segments:**
   `_fetch_weather()` gibt auch fehlgeschlagene Segmente in der Liste zurueck (nicht auslassen).

4. **test_formatter_renders_error_box_html:**
   HTML-Output enthaelt Warn-Box mit "Wetterdaten nicht verfuegbar" fuer Error-Segment.

5. **test_formatter_renders_error_plain_text:**
   Plain-Text-Output enthaelt "WETTERDATEN NICHT VERFUEGBAR" fuer Error-Segment.

6. **test_service_email_sent_for_sms_only:**
   Bei `send_sms=True, send_email=False` UND Error-Segment: Service-E-Mail wird gesendet.

7. **test_no_service_email_when_email_enabled:**
   Bei `send_email=True`: Keine separate Service-E-Mail (Error ist im Report sichtbar).

### Integration Tests

8. **test_partial_report_with_real_data:**
   Trip mit 3 Segmenten, davon 1 simulierter Fehler → Report enthaelt 2 normale + 1 Error-Segment.

## Implementation Status

- [x] SegmentWeatherData error fields added (models.py)
- [x] Error catching in SegmentWeatherService (segment_weather.py)
- [x] Error tracking in TripReportScheduler (trip_report_scheduler.py)
- [x] Service email for SMS-only trips (trip_report_scheduler.py)
- [x] Error row rendering in TripReportFormatter (trip_report.py)
- [x] Unit tests passing (test_provider_error_handling.py)

## Changelog

- 2026-02-16: Implementation completed and validated
- 2026-02-16: Initial spec created (WEATHER-04)
