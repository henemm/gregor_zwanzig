# User Story: Trip-Reports (Email/SMS)

**Status:** open
**Created:** 2026-02-01
**Epic:** GPX-basierte Trip-Planung
**Priority:** HIGH (Story 3 of 3)

## Story

Als Weitwanderer
möchte ich 2x täglich (morgens/abends) und bei signifikanten Wetteränderungen automatische Trip-Reports per Email/SMS erhalten
damit ich immer aktuell über das Wetter auf meiner Route informiert bin

## Context

**Wichtige Entscheidungen aus User-Dialog:**
- ✅ **Story 2 als Foundation:** Nutzt SegmentWeatherData (alle Segmente mit Wetter)
- ✅ **2x täglich Scheduled:** Morgens (07:00) + Abends (18:00) Europe/Vienna
- ✅ **Alert bei Änderungen:** Story 2 Change-Detection triggert sofortige Reports
- ✅ **Email + SMS Support:** Beide Channels implementiert
- ✅ **SMS ≤160 chars:** Ultra-kompakt, Format: `E1:T12/18 W30 R5mm RISK:Gewitter@14h | E2:...`
- ✅ **Email HTML Table:** Alle Segmente, aggregierte Summary, vollständig
- ✅ **User Config:** Times, Channels, Metrics per Trip konfigurierbar
- ✅ **Safari Compatibility:** Factory Pattern für Config UI

## Acceptance Criteria

- [ ] System generiert HTML Email mit Segment-Tabelle + Summary
- [ ] System generiert SMS ≤160 chars mit kompaktem Format
- [ ] System scheduled Reports 2x täglich (Morning 07:00, Evening 18:00)
- [ ] System sendet Alert-Reports bei signifikanten Wetteränderungen
- [ ] User konfiguriert Report-Zeiten, Channels, Metriken (WebUI)
- [ ] Email subject: `[Trip-Name] Report-Typ - Datum`
- [ ] Safari-kompatibel (Factory Pattern für Config UI)
- [ ] Real SMTP/IMAP E2E Tests (NO MOCKS!)
- [ ] Email Spec Validator passes (PFLICHT!)

## Feature Breakdown

### P0 Features (Must Have - Story 3 MVP)

---

#### Feature 3.1: Email Trip-Formatter

**Category:** Formatter
**Scoping:** 2-3 files, ~150 LOC, Medium
**Dependencies:** Story 2 (SegmentWeatherData)
**Roadmap Status:** Will be added

**What:**
Format segment weather into HTML email mit Tabelle + Summary

**Acceptance:**
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

**Files:**
- `src/formatters/trip_report.py` (NEW) - Trip Report Formatter
- `src/formatters/trip_email_template.py` (NEW) - HTML Template
- `tests/unit/test_trip_report.py` (NEW) - Unit Tests

**Technical Approach:**
- Folgt Pattern von `src/formatters/wintersport.py`
- HTML Template:
  ```html
  <h1>{trip_name} - {report_type}</h1>
  <table>
    <tr><th>Segment</th><th>Zeit</th><th>Temp</th><th>Wind</th><th>Precip</th></tr>
    {% for seg in segments %}
    <tr>
      <td>{{ seg.segment_id }}</td>
      <td>{{ seg.start_time }} - {{ seg.end_time }}</td>
      <td>{{ seg.aggregated.temp_min_c }}-{{ seg.aggregated.temp_max_c }}°C</td>
      <td>{{ seg.aggregated.wind_max_kmh }} km/h</td>
      <td>{{ seg.aggregated.precip_sum_mm }} mm</td>
    </tr>
    {% endfor %}
  </table>
  <h2>Summary</h2>
  <p>Max Temp: {{ summary.max_temp }}°C, Max Wind: {{ summary.max_wind }} km/h</p>
  ```
- Plain-Text: ASCII-Table Fallback
- Subject: `f"[{trip_name}] {report_type} - {date.strftime('%d.%m.%Y')}"`

**DTO (add to API Contract):**
```python
@dataclass
class TripReport:
    """Generated trip weather report."""
    trip_id: str
    trip_name: str
    report_type: str  # "morning", "evening", "alert"
    generated_at: datetime
    segments: list[SegmentWeatherData]  # From Story 2

    # Formatted content
    email_subject: str
    email_html: str
    email_plain: str
    sms_text: Optional[str] = None  # ≤160 chars (Feature 3.2)

    # Metadata
    triggered_by: Optional[str] = None  # "schedule" or "change_detection"
    changes: list[WeatherChange] = field(default_factory=list)  # If alert
```

**Standards:**
- ✅ Email Format (HTML + Plain-Text, inline CSS)
- ✅ Email Validator (`.claude/hooks/email_spec_validator.py` PFLICHT!)
- ✅ No Mocked Tests (Real SegmentWeatherData)
- ✅ Debug Consistency (Generate ONCE, use SAME for Console + Email)
- ✅ API Contracts (Add TripReport DTO)

---

#### Feature 3.2: SMS Compact Formatter

**Category:** Formatter
**Scoping:** 2 files, ~80 LOC, Simple
**Dependencies:** Story 2 (SegmentWeatherSummary)
**Roadmap Status:** Will be added

**What:**
Ultra-compact ≤160 char SMS summary

**Acceptance:**
- [ ] Output MUSS ≤160 Zeichen sein (hard constraint!)
- [ ] Format: `E{N}:T{min}/{max} W{wind} R{precip}mm [RISK:{type}@{time}] | E{N+1}:...`
- [ ] Priorisierung: Risiko > Wetter > Details
- [ ] Abkürzungen: E=Etappe, T=Temp, W=Wind, R=Regen
- [ ] Risiko nur wenn vorhanden: `RISK:Gewitter@14h`
- [ ] Mehrere Segmente: Getrennt mit ` | `
- [ ] Truncate wenn zu lang: Älteste Segmente weglassen, `...` suffix
- [ ] Unit Tests: Verschiedene Segment-Anzahlen (1, 3, 10)
- [ ] Integration Tests: Real SegmentWeatherSummary
- [ ] Validation: Enforciert ≤160 chars (Exception wenn unmöglich)

**Files:**
- `src/formatters/sms_trip.py` (NEW) - SMS Trip Formatter
- `tests/unit/test_sms_trip.py` (NEW) - Unit Tests

**Technical Approach:**
- Template per Segment:
  ```python
  segment_str = f"E{seg.segment_id}:T{seg.temp_min_c}/{seg.temp_max_c} W{seg.wind_max_kmh} R{seg.precip_sum_mm}mm"
  if seg.thunder_level_max != NONE:
      segment_str += f" RISK:Gewitter@{thunder_time}h"
  ```
- Join segments: `" | ".join(segment_strs)`
- Truncate wenn >160:
  ```python
  while len(sms) > 160 and segments:
      segments = segments[:-1]  # Remove oldest
  if len(sms) > 160:
      sms = sms[:157] + "..."
  ```
- Validation: `assert len(sms) <= 160`

**DTO Extension:**
Uses TripReport.sms_text from Feature 3.1 (already defined)

**Standards:**
- ✅ SMS Constraint (≤160 chars enforced)
- ✅ No Mocked Tests (Real SegmentWeatherSummary)
- ✅ API Contracts (TripReport.sms_text already defined in 3.1)

---

#### Feature 3.3: Report-Scheduler

**Category:** Services
**Scoping:** 2-3 files, ~120 LOC, Medium
**Dependencies:** Feature 3.1 (Email), Feature 3.2 (SMS)
**Roadmap Status:** Will be added

**What:**
APScheduler für 2x täglich Trip-Reports

**Acceptance:**
- [ ] Scheduled Jobs: 07:00 (morning) + 18:00 (evening) Europe/Vienna
- [ ] Runs daily für alle aktive Trips
- [ ] Generiert Report via Feature 3.1 + 3.2
- [ ] Sendet Email via SMTP (existing smtp_mailer)
- [ ] Sendet SMS via MessageBird (wenn enabled)
- [ ] Error Handling: Failed jobs logged, nicht gecrasht
- [ ] Configurable Times: User kann Zeiten ändern (Feature 3.5)
- [ ] Timezone-Aware: Nutzt Europe/Vienna
- [ ] Persistent: Scheduler läuft im Web-Server Prozess
- [ ] Integration Tests: Time-Mocking für Scheduler
- [ ] Real E2E Test: Trigger manual job, verify Email/SMS sent

**Files:**
- `src/services/trip_report_scheduler.py` (NEW) - Report Scheduler Service
- `src/web/scheduler.py` (MODIFIED) - Integrate Trip-Report Jobs
- `tests/integration/test_trip_report_scheduler.py` (NEW) - Integration Tests

**Technical Approach:**
- APScheduler (bereits verwendet in src/web/scheduler.py):
  ```python
  from apscheduler.schedulers.asyncio import AsyncIOScheduler

  scheduler = AsyncIOScheduler(timezone="Europe/Vienna")

  # Morning report
  scheduler.add_job(
      send_morning_reports,
      trigger="cron",
      hour=7, minute=0,
      id="morning_trip_reports"
  )

  # Evening report
  scheduler.add_job(
      send_evening_reports,
      trigger="cron",
      hour=18, minute=0,
      id="evening_trip_reports"
  )
  ```
- `send_morning_reports()`:
  1. Load all active trips
  2. For each trip: Generate TripReport (type="morning")
  3. Send via Email + SMS (if enabled)
  4. Log success/failure

**DTO Usage:**
Uses TripReport from Feature 3.1 (already defined)

**Standards:**
- ✅ Extends existing scheduler pattern (src/web/scheduler.py)
- ✅ No Mocked Tests (Real scheduled jobs mit time-mocking)

---

#### Feature 3.4: Alert bei Änderungen

**Category:** Services
**Scoping:** 2 files, ~100 LOC, Simple
**Dependencies:** Story 2 Feature 2.5 (Change-Detection), Feature 3.1 (Email), Feature 3.2 (SMS)
**Roadmap Status:** Will be added

**What:**
Immediate report bei signifikanten Wetteränderungen

**Acceptance:**
- [ ] Triggered by Story 2 Feature 2.5 Change-Detection
- [ ] Threshold: WeatherChange.severity >= "moderate"
- [ ] Generiert Report (type="alert")
- [ ] Subject: `[{trip_name}] WETTER-ÄNDERUNG - {date}`
- [ ] Email enthält: Changed Metriken, Old vs New, Delta
- [ ] SMS enthält: `ALERT: {metric} {old}→{new} (+{delta})`
- [ ] Alert-Throttling: Max 1 Alert pro 2h (kein Spam)
- [ ] User kann Alerts enable/disable (Feature 3.5)
- [ ] Unit Tests mit bekannten WeatherChange
- [ ] Integration Tests: Real Change-Detection → Alert flow
- [ ] Real E2E Test: Trigger alert, verify Email/SMS

**Files:**
- `src/services/trip_alert.py` (NEW) - Trip Alert Service
- `tests/integration/test_trip_alert.py` (NEW) - Integration Tests

**Technical Approach:**
- Listener auf Change-Detection:
  ```python
  def handle_weather_change(segment_id: str, changes: list[WeatherChange]):
      # Filter: Only moderate/major severity
      significant = [c for c in changes if c.severity in ["moderate", "major"]]
      if not significant:
          return

      # Throttling: Check last alert time
      if time_since_last_alert(segment_id) < timedelta(hours=2):
          return  # Skip, too soon

      # Generate Alert Report
      report = generate_trip_report(
          trip_id=get_trip_for_segment(segment_id),
          report_type="alert",
          triggered_by="change_detection",
          changes=significant
      )

      # Send via Email + SMS
      send_report(report)
  ```
- Throttling: In-memory dict `{segment_id: last_alert_time}`

**DTO Usage:**
Uses TripReport (type="alert") + WeatherChange from Story 2

**Standards:**
- ✅ No Mocked Tests (Real Change-Detection integration)
- ✅ Email Validator (for alert emails)

---

#### Feature 3.5: Report-Config (WebUI)

**Category:** WebUI
**Scoping:** 2 files, ~80 LOC, Simple
**Dependencies:** Feature 3.3 (Scheduler), Feature 3.4 (Alerts)
**Roadmap Status:** Will be added

**What:**
User konfiguriert Report-Preferences (Times, Channels, Metrics)

**Acceptance:**
- [ ] WebUI Page: "Report-Einstellungen"
- [ ] Time-Picker: Morning-Time (default 07:00)
- [ ] Time-Picker: Evening-Time (default 18:00)
- [ ] Checkboxes: send_email (default ON), send_sms (default OFF)
- [ ] Checkbox: alert_on_changes (default ON)
- [ ] Threshold-Slider: Temp-Change (default 5°C, range 1-10°C)
- [ ] Threshold-Slider: Wind-Change (default 20 km/h, range 5-50 km/h)
- [ ] Threshold-Slider: Precip-Change (default 10 mm, range 1-20 mm)
- [ ] Metrics-Selection: Referenziert Story 2 Feature 2.6 (Wetter-Metriken)
- [ ] Save-Button: Speichert Config pro Trip
- [ ] Safari-kompatibel: Factory Pattern für Save-Button!
- [ ] Validation: Morning < Evening time
- [ ] Config gespeichert in Database (per trip_id)
- [ ] E2E Test: Safari Browser Test
- [ ] UI Feedback: "Einstellungen gespeichert" Notification

**Files:**
- `src/web/pages/report_config.py` (NEW) - Report Config UI
- `tests/e2e/test_report_config.py` (NEW) - E2E Test (Safari!)

**Technical Approach:**
- NiceGUI Page mit Form:
  ```python
  def make_save_handler(trip_id):
      def do_save():
          config = TripReportConfig(
              trip_id=trip_id,
              morning_time=morning_picker.value,
              evening_time=evening_picker.value,
              send_email=email_checkbox.value,
              send_sms=sms_checkbox.value,
              alert_on_changes=alert_checkbox.value,
              change_threshold_temp_c=temp_slider.value,
              change_threshold_wind_kmh=wind_slider.value,
              change_threshold_precip_mm=precip_slider.value,
          )
          save_trip_report_config(config)
          ui.notify("Report-Einstellungen gespeichert!")
      return do_save

  save_btn = ui.button("Speichern", on_click=make_save_handler(trip_id))
  ```
- Factory Pattern mandatory (Safari!)
- Config Storage: Database table `trip_report_config`

**DTO (add to API Contract):**
```python
@dataclass
class TripReportConfig:
    """Configuration for trip weather reports."""
    trip_id: str
    enabled: bool = True

    # Schedule
    morning_time: time = time(7, 0)
    evening_time: time = time(18, 0)
    timezone: str = "Europe/Vienna"

    # Channels
    send_email: bool = True
    send_sms: bool = False

    # Alerts
    alert_on_changes: bool = True
    change_threshold_temp_c: float = 5.0
    change_threshold_wind_kmh: float = 20.0
    change_threshold_precip_mm: float = 10.0

    # Content (references Story 2 Feature 2.6 TripWeatherConfig)
    include_metrics: list[str] = field(default_factory=lambda: [
        "temperature", "wind", "precipitation", "thunder", "visibility"
    ])

    # Metadata
    updated_at: datetime = field(default_factory=datetime.now)
```

**Standards:**
- ✅ Safari Compatibility (Factory Pattern for Save-Button)
- ✅ No Mocked Tests (Real browser E2E test)
- ✅ API Contracts (Add TripReportConfig DTO)

---

## Implementation Order

**Dependency-optimiert:**

```
Story 2 (SegmentWeatherData)
         ↓
    ┌────┴────┐
    ↓         ↓
[3.1 Email] [3.2 SMS]
    ↓         ↓
    └────┬────┘
         ↓
   [3.3 Scheduler]
         ↓
   [3.4 Alerts] ← Story 2.5 (Change-Detection)
         ↓
   [3.5 Config UI]
```

**Empfohlene Reihenfolge:**
1. Feature 3.1 (Email Trip-Formatter) - Foundation
2. Feature 3.2 (SMS Compact Formatter) - Parallel möglich mit 3.1
3. Feature 3.3 (Report-Scheduler) - Automated delivery
4. Feature 3.4 (Alert bei Änderungen) - Real-time alerts
5. Feature 3.5 (Report-Config UI) - User control

## Dependency Graph

```
           [Story 2: SegmentWeatherData]
                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
  [3.1 Email Formatter]    [3.2 SMS Formatter]
         ↓                         ↓
         └────────────┬────────────┘
                      ↓
            [3.3 Report-Scheduler]
                      ↓
            [3.4 Alert Service] ← [Story 2.5: Change-Detection]
                      ↓
            [3.5 Report-Config UI]
```

## Estimated Effort

**Total (Story 3):**
- **LOC:** ~530 lines
- **Files:** ~10 files (5 features, ~2 files each)
- **Workflow Cycles:** 5 (one per feature)
- **Timeline:** 5-7 Tage (sequential implementation)

**Per Feature:**
- Simple (3.2, 3.4, 3.5): ~80-100 LOC, 1-2 Tage
- Medium (3.1, 3.3): ~120-150 LOC, 2-3 Tage

## MVP Definition (Story 3)

**MVP = Alle P0 Features Complete**

**User kann:**
- ✅ Automatische Trip-Reports 2x täglich erhalten (Email + SMS)
- ✅ Sofortige Alerts bei signifikanten Wetteränderungen
- ✅ Report-Zeiten konfigurieren (Morning, Evening)
- ✅ Channels wählen (Email, SMS, beide)
- ✅ Alert-Thresholds anpassen
- ✅ Metriken pro Trip konfigurieren (via Story 2.6)

**Nach Story 3: GPX Epic KOMPLETT! Vollständig automatisiert!**

## Testing Strategy

### Real E2E Tests (NO MOCKS!)

**Real SMTP/IMAP:**
1. Send Email via Gmail SMTP
2. Retrieve Email via IMAP
3. Validate content mit `.claude/hooks/email_spec_validator.py`
4. Check HTML structure, subject, recipient
5. Verify Plain-Text fallback exists

**Real SMS API:**
1. Send SMS via MessageBird (or test provider)
2. Verify delivery status
3. Check ≤160 chars constraint
4. Test with different segment counts

**Browser Tests (Safari mandatory!):**
1. Report Config UI: Time-Pickers, Checkboxes, Sliders
2. Save config per trip
3. Verify saved config loaded
4. Test validation (morning < evening)

**Integration Tests:**
1. Full pipeline: Story 2 Weather → Story 3 Report → Email/SMS
2. Scheduler: Time-mocking für cron jobs
3. Alert flow: Change-Detection → Alert → Email/SMS
4. End-to-end: GPX Upload (Story 1) → Weather (Story 2) → Report (Story 3)

**Email Spec Validator (PFLICHT!):**
```bash
uv run python3 .claude/hooks/email_spec_validator.py
```
**NUR bei Exit 0 darfst du "E2E Test bestanden" sagen!**

## Standards to Follow

- ✅ **API Contracts:** Add ALL DTOs before implementation (TripReport, TripReportConfig)
- ✅ **Email Format:** HTML + Plain-Text, inline CSS, subject format
- ✅ **Email Validator:** `.claude/hooks/email_spec_validator.py` PFLICHT!
- ✅ **Real SMTP/IMAP:** E2E tests send + retrieve (NO MOCKS!)
- ✅ **SMS Constraint:** ≤160 chars enforced (hard constraint!)
- ✅ **Safari Compatibility:** Factory Pattern für Feature 3.5 UI
- ✅ **Debug Consistency:** Generate ONCE, use SAME for Console + Email
- ✅ **No Mocked Tests:** Real MessageBird API calls

## Security & Privacy

### Email
- User email address in config (encrypted at rest)
- SMTP credentials in environment variables
- No logging of email content (only metadata)

### SMS
- Phone number in config (encrypted at rest)
- MessageBird API key in environment variables
- No logging of SMS content (only delivery status)

### Weather Data
- Public data (no privacy concerns)
- GPS coordinates from user's GPX files (already covered in Story 1)

### Opt-Out
- User can disable all reports (enabled=false)
- User can disable specific channels (send_email, send_sms)
- User can disable alerts (alert_on_changes=false)

## Configuration

### Config File Extensions

```ini
[trip_reports]
# Default schedule
default_morning_time = 07:00
default_evening_time = 18:00
timezone = Europe/Vienna

# Default channels
default_send_email = true
default_send_sms = false

# Default alert settings
default_alert_on_changes = true
default_change_threshold_temp_c = 5.0
default_change_threshold_wind_kmh = 20.0
default_change_threshold_precip_mm = 10.0

# Alert throttling
alert_min_interval_hours = 2

# Email settings (references existing smtp_mailer config)
email_from = ${EMAIL_FROM}
email_to = ${EMAIL_TO}

# SMS settings (new)
sms_provider = messagebird
sms_api_key = ${SMS_API_KEY}
sms_from_number = ${SMS_FROM_NUMBER}
sms_to_number = ${SMS_TO_NUMBER}

# Scheduler
scheduler_enabled = true
scheduler_timezone = Europe/Vienna
```

## Related

- **Epic:** GPX-basierte Trip-Planung (`epics.md`)
- **Story 1:** GPX Upload & Segment-Planung (provides segments)
- **Story 2:** Wetter-Engine für Trip-Segmente (provides weather data)
- **Architecture:** `docs/features/architecture.md`
- **API Contract:** `docs/reference/api_contract.md` (MUST UPDATE with Story 3 DTOs!)
- **Email Channel (reference):** `src/channels/smtp_mailer.py`
- **Email Validator:** `.claude/hooks/email_spec_validator.py`
- **SMS Example:** `docs/project/backlog/stories/EXAMPLE-sms-berichte.md`

## Notes

- Story 3 ist finale Story im GPX Epic
- Nach Story 3: Epic komplett, voll automatisiert
- Email Formatter folgt Pattern von `src/formatters/wintersport.py`
- SMS Format nutzt ultra-kompakte Abkürzungen (≤160 chars hard constraint)
- Scheduler erweitert bestehendes `src/web/scheduler.py`
- Alert-Throttling verhindert Spam (max 1 Alert pro 2h)

## Integration Points

### Story 2 → Story 3

**Input (from Story 2):**
```python
# List of all segment weather for a trip
trip_weather = [
    SegmentWeatherData(
        segment=TripSegment(...),
        timeseries=NormalizedTimeseries(...),
        aggregated=SegmentWeatherSummary(
            temp_min_c=12, temp_max_c=18,
            wind_max_kmh=25, precip_sum_mm=5,
            # ...
        ),
    ),
    # ... more segments
]
```

**Output (Story 3):**
```python
# Generated report
trip_report = TripReport(
    trip_id="gr20-etappe3",
    trip_name="GR20 Etappe 3",
    report_type="morning",
    generated_at=datetime.now(),
    segments=trip_weather,
    email_subject="[GR20 Etappe 3] Wetter-Morgen - 29.08.2025",
    email_html="<html>...table with all segments...</html>",
    email_plain="GR20 Etappe 3 Wetter-Morgen\n\nSegment 1: 12-18°C...",
    sms_text="E1:T12/18 W25 R5mm | E2:T15/20 W15 R2mm",
    triggered_by="schedule"
)

# Send via Email
smtp_mailer.send(
    to=config.email_to,
    subject=trip_report.email_subject,
    html=trip_report.email_html,
    plain=trip_report.email_plain
)

# Send via SMS (if enabled)
if config.send_sms:
    sms_sender.send(
        to=config.sms_to_number,
        text=trip_report.sms_text
    )
```

### Full Epic Flow (Story 1 → 2 → 3)

```
1. User uploads GPX (Story 1)
   → GPX parsed, segments created (TripSegment[])

2. System fetches weather (Story 2)
   → Weather for each segment (SegmentWeatherData[])

3. System generates & sends reports (Story 3)
   → 2x daily scheduled (morning, evening)
   → Alert on weather changes
   → Email + SMS delivery
```

## Next Steps

**To start implementation:**

```bash
# 1. Update API Contract FIRST
# Add DTOs: TripReport, TripReportConfig
vim docs/reference/api_contract.md

# 2. Start with Feature 3.1 (Email Formatter)
/feature "Email Trip-Formatter"

# 3. Follow workflow
/analyse
/write-spec
# User: "approved"
/tdd-red
/implement
/validate

# WICHTIG: Nach Email-Feature IMMER Email Spec Validator ausführen!
uv run python3 .claude/hooks/email_spec_validator.py

# 4. Move to Feature 3.2 (SMS)
/feature "SMS Compact Formatter"
# ... workflow ...

# 5. Continue with remaining features
# Feature 3.3 → 3.4 → 3.5

# 6. Story 3 Complete!
# 7. GPX Epic Complete! 🎉
# Test full flow: GPX Upload → Weather → Reports
```

---

**Story 3 ready for implementation! 🚀**
**Nach Story 3: GPX Epic vollständig abgeschlossen! 🎉**
