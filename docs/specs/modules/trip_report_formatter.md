---
entity_id: trip_report_formatter
type: module
created: 2026-02-02
updated: 2026-02-02
status: draft
version: "1.0"
tags: [formatter, email, story3, trip-reports]
---

# Trip Report Formatter

## Approval

- [x] Approved

## Purpose

Formats trip segment weather data into HTML emails for automated trip weather reports. Generates responsive HTML tables showing all segments with weather metrics, aggregated summary, and plain-text fallback for 2x daily scheduled reports and change-detection alerts.

## Source

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter`
- **Helper:** `src/formatters/trip_html_template.py` (HTML generation)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SegmentWeatherData | DTO (models.py) | Input: Segment + weather data |
| SegmentWeatherSummary | DTO (models.py) | Aggregated metrics per segment |
| TripSegment | DTO (models.py) | Segment metadata (time, location) |
| TripWeatherConfig | DTO (models.py) | User-configured metric selection |
| TripReport | DTO (models.py) | Output: Formatted email content |
| WeatherChange | DTO (models.py) | Change-detection data for alerts |
| EmailOutput | Output (outputs/email.py) | Email sending (used by caller) |

## Feature Context

**Feature:** 3.1 Email Trip-Formatter (Story 3: Trip-Reports Email/SMS)

**Story Context:**
- User needs automated trip weather reports via email
- 2x daily (morning 07:00, evening 18:00) + alerts on weather changes
- Story 2 provides SegmentWeatherData (all segments with weather)
- Story 2.6 provides TripWeatherConfig (user-selected metrics)

**Integration:**
- **Input:** Called by Feature 3.3 (Report-Scheduler) and Feature 3.4 (Alert System)
- **Output:** Returns TripReport DTO → passed to EmailOutput.send()

## Implementation Details

### Class: TripReportFormatter

```python
class TripReportFormatter:
    """
    Formatter for trip weather reports (HTML email).

    Generates HTML tables with segment weather data and aggregated summary.
    Follows pattern from WintersportFormatter and compare.py HTML rendering.
    """

    def format_email(
        self,
        segments: list[SegmentWeatherData],
        trip_name: str,
        report_type: str,  # "morning", "evening", "alert"
        trip_config: Optional[TripWeatherConfig] = None,
        changes: Optional[list[WeatherChange]] = None,
    ) -> TripReport:
        """
        Format trip segments into HTML email.

        Args:
            segments: List of SegmentWeatherData from Story 2
            trip_name: Trip name for subject/header
            report_type: "morning", "evening", or "alert"
            trip_config: User's metric selections (default: all 8 basis)
            changes: Weather changes (for alert reports)

        Returns:
            TripReport with email_html, email_plain, email_subject
        """
```

### HTML Template Structure

**Pattern:** Follows `src/web/pages/compare.py:render_comparison_html()`

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        /* Inline CSS - Responsive design */
        body { font-family: sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; }
        .header { background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 24px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background: #f5f5f5; padding: 12px 8px; font-weight: 600; }
        td { padding: 10px 8px; border-bottom: 1px solid #eee; }
        .risk-high { background: #ffebee; color: #c62828; font-weight: 600; }
        .risk-medium { background: #fff9c4; color: #f57f17; }
        .footer { background: #f5f5f5; padding: 16px; color: #888; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{trip_name}</h1>
            <p>{report_type} Report - {date}</p>
        </div>

        <div class="section">
            <h2>Segments</h2>
            <table>
                <tr>
                    <th>Segment</th>
                    <th>Time</th>
                    <th>Duration</th>
                    <th>Temp</th>
                    <th>Wind</th>
                    <th>Precip</th>
                    <th>Risk</th>
                </tr>
                {for each segment}
                <tr>
                    <td>#{segment_id}</td>
                    <td>{start_time} - {end_time}</td>
                    <td>{duration_hours}h</td>
                    <td>{temp_min}-{temp_max}°C</td>
                    <td>{wind_max} km/h</td>
                    <td>{precip_sum} mm</td>
                    <td class="risk-{level}">{risk_text}</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>Summary</h2>
            <p><strong>Max Temp:</strong> {max_temp}°C</p>
            <p><strong>Max Wind:</strong> {max_wind} km/h</p>
            <p><strong>Total Precip:</strong> {total_precip} mm</p>
        </div>

        {if alert report}
        <div class="section">
            <h2>Changes Detected</h2>
            <ul>
                {for each change}
                <li>{metric}: {old_value} → {new_value} (Δ {delta})</li>
            </ul>
        </div>

        <div class="footer">
            <p>Generated: {generated_at}</p>
            <p>Data: {provider}</p>
        </div>
    </div>
</body>
</html>
```

### Plain-Text Generation

Auto-generated from HTML (EmailOutput handles this) OR explicit:

```
{trip_name} - {report_type} Report
{date}

SEGMENTS
========
#1  08:00-10:00 (2.0h)  12-18°C  25 km/h  5mm  ⚠️ Thunder
#2  10:00-12:00 (2.0h)  15-20°C  15 km/h  2mm  ✓ OK
#3  12:00-14:00 (2.0h)  18-22°C  30 km/h  0mm  ⚠️ Wind

SUMMARY
=======
Max Temp: 22°C
Max Wind: 30 km/h
Total Precip: 7mm

---
Generated: 2026-02-02 07:00:00 UTC
Data: openmeteo
```

### Column Selection (User Config)

```python
# Use TripWeatherConfig.enabled_metrics to filter columns
# Default if no config: all 8 basis metrics

enabled = trip_config.enabled_metrics if trip_config else [
    "temp_min_c", "temp_max_c", "temp_avg_c",
    "wind_max_kmh", "gust_max_kmh", "precip_sum_mm",
    "cloud_avg_pct", "humidity_avg_pct"
]

# Only show columns for enabled metrics
columns = []
if any(m.startswith("temp") for m in enabled):
    columns.append("Temp")
if "wind_max_kmh" in enabled:
    columns.append("Wind")
if "precip_sum_mm" in enabled:
    columns.append("Precip")
# ... etc
```

### Risk Detection

```python
def _determine_risk(segment: SegmentWeatherData) -> tuple[str, str]:
    """
    Determine risk level and description for segment.

    Returns:
        (level, text) where level is "high", "medium", "none"
    """
    agg = segment.aggregated

    # HIGH risk conditions
    if agg.thunder_level_max and agg.thunder_level_max.value >= 2:  # HIGH
        return ("high", "⚠️ Thunder")
    if agg.wind_max_kmh and agg.wind_max_kmh > 70:
        return ("high", "⚠️ Storm")
    if agg.wind_chill_min_c and agg.wind_chill_min_c < -20:
        return ("high", "⚠️ Extreme Cold")
    if agg.visibility_min_m and agg.visibility_min_m < 100:
        return ("high", "⚠️ Low Visibility")

    # MEDIUM risk conditions
    if agg.wind_max_kmh and agg.wind_max_kmh > 50:
        return ("medium", "⚠️ High Wind")
    if agg.precip_sum_mm and agg.precip_sum_mm > 20:
        return ("medium", "⚠️ Heavy Rain")

    return ("none", "✓ OK")
```

### Summary Aggregation

```python
def _compute_summary(segments: list[SegmentWeatherData]) -> dict:
    """
    Aggregate statistics across all segments.

    Returns:
        {
            "max_temp_c": float,
            "min_temp_c": float,
            "max_wind_kmh": float,
            "total_precip_mm": float,
            "max_gust_kmh": float,
            ...
        }
    """
    temps_max = [s.aggregated.temp_max_c for s in segments if s.aggregated.temp_max_c]
    temps_min = [s.aggregated.temp_min_c for s in segments if s.aggregated.temp_min_c]
    winds = [s.aggregated.wind_max_kmh for s in segments if s.aggregated.wind_max_kmh]
    precips = [s.aggregated.precip_sum_mm for s in segments if s.aggregated.precip_sum_mm]

    return {
        "max_temp_c": max(temps_max) if temps_max else None,
        "min_temp_c": min(temps_min) if temps_min else None,
        "max_wind_kmh": max(winds) if winds else None,
        "total_precip_mm": sum(precips) if precips else None,
    }
```

## Expected Behavior

### Input

```python
# Example: 3 segments from Story 2
segments = [
    SegmentWeatherData(
        segment=TripSegment(
            segment_id=1,
            start_time=datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            ...
        ),
        aggregated=SegmentWeatherSummary(
            temp_min_c=12, temp_max_c=18,
            wind_max_kmh=25, precip_sum_mm=5,
            thunder_level_max=ThunderLevel.MEDIUM,
            ...
        ),
        ...
    ),
    # ... more segments
]

formatter = TripReportFormatter()
report = formatter.format_email(
    segments=segments,
    trip_name="GR20 Etappe 3",
    report_type="morning",
    trip_config=trip_config,  # From Story 2.6
)
```

### Output

```python
TripReport(
    trip_id="gr20-etappe3",
    trip_name="GR20 Etappe 3",
    report_type="morning",
    generated_at=datetime.now(timezone.utc),
    segments=segments,

    # Formatted content
    email_subject="[GR20 Etappe 3] Morning Report - 29.08.2026",
    email_html="<!DOCTYPE html><html>...",  # Full HTML
    email_plain="GR20 Etappe 3 - Morning Report\n...",  # Plain-text
    sms_text=None,  # Feature 3.2

    # Metadata
    triggered_by="schedule",
    changes=[],
)
```

### Side Effects

**None.** Pure formatting function - no I/O, no state changes.

## Acceptance Criteria

**From Story 3 Feature 3.1:**

- [ ] Generiert HTML Email mit Segment-Tabelle
- [ ] Tabelle-Spalten: Segment-Nr, Zeit, Dauer, Temp, Wind, Precip, Risiko
- [ ] Summary-Section: Gesamt-Statistiken (Max-Temp, Max-Wind, Total-Precip)
- [ ] Enthält nur User-konfigurierte Metriken (Story 2 Feature 2.6)
- [ ] Subject: `[{trip_name}] {report_type} - {date}`
- [ ] HTML + Plain-Text Version (beide!)
- [ ] Inline CSS (keine externen Stylesheets)
- [ ] Responsive: Lesbar auf Mobile
- [ ] Color-Coding: Risiken highlighted (rot für HIGH, gelb für MED)
- [ ] Footer: Metadata (Provider, Generated-At)
- [ ] Unit Tests mit bekannten Segment-Daten
- [ ] Integration Tests mit Real SegmentWeatherData
- [ ] Email Spec Validator passes (PFLICHT!)
- [ ] Debug Consistency: Same data für Console + Email

## DTO Definition

**Add to `src/app/models.py`:**

```python
@dataclass
class TripReport:
    """
    Generated trip weather report.

    Contains formatted content ready for email/SMS delivery.
    Generated by TripReportFormatter (Feature 3.1).

    Example:
        TripReport(
            trip_id="gr20-etappe3",
            trip_name="GR20 Etappe 3",
            report_type="morning",
            generated_at=datetime.now(timezone.utc),
            segments=[...],
            email_subject="[GR20 Etappe 3] Morning - 29.08.2026",
            email_html="<!DOCTYPE html>...",
            email_plain="GR20 Etappe 3\n...",
            triggered_by="schedule"
        )
    """
    trip_id: str
    trip_name: str
    report_type: str  # "morning", "evening", "alert"
    generated_at: datetime
    segments: list[SegmentWeatherData]  # From Story 2

    # Formatted content
    email_subject: str
    email_html: str
    email_plain: str
    sms_text: Optional[str] = None  # Feature 3.2 will populate

    # Metadata
    triggered_by: Optional[str] = None  # "schedule" or "change_detection"
    changes: list[WeatherChange] = field(default_factory=list)  # If alert
```

## Testing Strategy

### Unit Tests (`tests/unit/test_trip_report_formatter.py`)

```python
def test_format_email_generates_html():
    """HTML output contains DOCTYPE, table, proper structure."""
    segments = [create_test_segment(1, temp_min=12, temp_max=18)]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test Trip", "morning")

    assert "<!DOCTYPE html>" in report.email_html
    assert "<table>" in report.email_html
    assert "Test Trip" in report.email_html
    assert report.email_subject == "[Test Trip] Morning Report - {date}"

def test_format_email_generates_plain_text():
    """Plain-text output is readable, contains all data."""
    segments = [create_test_segment(1, temp_min=12, temp_max=18)]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test Trip", "morning")

    assert report.email_plain
    assert "Test Trip" in report.email_plain
    assert "12-18°C" in report.email_plain or "12" in report.email_plain

def test_format_email_respects_user_config():
    """Only shows metrics enabled in TripWeatherConfig."""
    segments = [create_test_segment(1)]
    config = TripWeatherConfig(
        trip_id="test",
        enabled_metrics=["temp_min_c", "temp_max_c"],  # Only temp
        updated_at=datetime.now(timezone.utc)
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test", "morning", config)

    # Should show temp, not show wind/precip columns
    assert "Temp" in report.email_html
    assert "Wind" not in report.email_html or "Wind" in report.email_html.count < 2

def test_format_email_color_codes_risks():
    """High risks get red background, medium get yellow."""
    segments = [
        create_test_segment(1, thunder_level=ThunderLevel.HIGH),
        create_test_segment(2, wind_max=55),  # Medium
    ]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test", "morning")

    assert 'class="risk-high"' in report.email_html or 'risk-high' in report.email_html
    assert 'class="risk-medium"' in report.email_html or 'risk-medium' in report.email_html

def test_format_email_computes_summary():
    """Summary shows max/sum aggregations across segments."""
    segments = [
        create_test_segment(1, temp_max=18, wind_max=25, precip_sum=5),
        create_test_segment(2, temp_max=22, wind_max=30, precip_sum=2),
    ]
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "Test", "morning")

    assert "22" in report.email_html  # max temp
    assert "30" in report.email_html  # max wind
    assert "7" in report.email_html   # total precip (5+2)
```

### Integration Tests

```python
def test_format_email_with_real_segment_data():
    """Integration: Use real SegmentWeatherData from Story 2."""
    from services.segment_weather import SegmentWeatherService

    # Fetch real segment weather
    segment = TripSegment(...)  # Real segment
    service = SegmentWeatherService()
    weather_data = service.fetch_segment_weather(segment)

    # Format into email
    formatter = TripReportFormatter()
    report = formatter.format_email([weather_data], "Integration Test", "morning")

    # Verify structure
    assert "<!DOCTYPE html>" in report.email_html
    assert report.email_plain
    assert weather_data.aggregated.temp_max_c in report.email_html
```

### Email Spec Validator

**MANDATORY before claiming "tests pass":**

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Must validate:
- Struktur (DOCTYPE, table, sections)
- Plausibilität (reasonable values, not None everywhere)
- Format (inline CSS, responsive, proper encoding)
- Vollständigkeit (all segments shown, summary present)

## Standards Compliance

- ✅ **Email Format:** HTML + Plain-Text (multipart/alternative)
- ✅ **Inline CSS:** No external stylesheets
- ✅ **Responsive:** Mobile-friendly design
- ✅ **Email Validator:** Must pass `.claude/hooks/email_spec_validator.py`
- ✅ **No Mocked Tests:** Use real SegmentWeatherData
- ✅ **Debug Consistency:** Single render, same output
- ✅ **API Contracts:** TripReport DTO added to models.py
- ✅ **Subject Format:** `[{trip_name}] {report_type} - {date}`

## Known Limitations

1. **No Templating Engine:** Uses f-strings for simplicity (following compare.py pattern). Could migrate to Jinja2 if templates become complex.

2. **Fixed Column Order:** Columns always shown in same order (Segment, Time, Temp, Wind, Precip, Risk). User config only shows/hides columns, doesn't reorder.

3. **Static Risk Rules:** Risk detection uses hardcoded thresholds. Could make configurable in future.

4. **Plain-Text Auto-Generation:** If explicit plain-text not provided, EmailOutput auto-strips HTML. Manual plain-text generation could be more readable.

5. **Mobile Optimization:** Basic responsive design via max-width. Could enhance with media queries for very small screens.

6. **No Localization:** All text in German. English/multi-language support could be added.

## Changelog

- 2026-02-02: Initial spec created (Feature 3.1, Story 3)
