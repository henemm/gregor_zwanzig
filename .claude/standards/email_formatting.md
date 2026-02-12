# Email Formatting Standard

**Domain:** Email Report Formatting for Gregor Zwanziger

## Email Structure

All weather report emails MUST follow this structure:

### 1. Headers
- **From:** Configured sender (e.g., `gregor@example.com`)
- **To:** User email (from config)
- **Subject:** Report type + location + date
  ```
  Subject: [Evening Report] GR20 Etappe 3 - 2026-02-01
  ```

### 2. Body (HTML)

**Format:** HTML with fallback plain text

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        /* Inline CSS for email client compatibility */
        table { border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; }
    </style>
</head>
<body>
    <h1>Weather Report: [Location]</h1>

    <!-- Summary Section -->
    <p><strong>Report Type:</strong> Evening / Morning / Alert</p>
    <p><strong>Date:</strong> 2026-02-01</p>
    <p><strong>Risk Level:</strong> Low / Medium / High</p>

    <!-- Weather Data Table -->
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Temp (°C)</th>
                <th>Precip (mm)</th>
                <th>Wind (km/h)</th>
                <th>Conditions</th>
            </tr>
        </thead>
        <tbody>
            <!-- Hourly data rows -->
        </tbody>
    </table>

    <!-- Risk Warnings (if any) -->
    <div style="background: #fff3cd; padding: 10px; margin: 10px 0;">
        <strong>⚠️ Warning:</strong> Thunderstorm risk high at 14:00-16:00
    </div>

    <!-- Debug Info (if debug mode) -->
    <details>
        <summary>Debug Information</summary>
        <pre>[Debug output - same as console]</pre>
    </details>
</body>
</html>
```

### 3. Plain Text Alternative

**Required** for email clients without HTML support:

```
Weather Report: GR20 Etappe 3
Date: 2026-02-01
Risk Level: Medium

Time    Temp  Precip  Wind    Conditions
08:00   12°C  0mm     10km/h  Partly Cloudy
10:00   15°C  2mm     15km/h  Light Rain
...

⚠️ Warning: Thunderstorm risk high at 14:00-16:00

Debug: [if enabled]
```

## Email Client Compatibility

### Must Support
- Gmail (web, iOS, Android)
- Outlook (web, desktop)
- Apple Mail (macOS, iOS)
- Thunderbird

### Compatibility Rules
1. **Inline CSS only** (no external stylesheets)
2. **Simple table layouts** (no complex CSS grid)
3. **System fonts** (no web fonts)
4. **Conservative HTML** (avoid modern HTML5 features)

### Testing Matrix
- [x] Gmail web (Chrome, Safari)
- [x] Gmail iOS app
- [x] Apple Mail (macOS)
- [x] Apple Mail (iOS)
- [ ] Outlook web
- [ ] Thunderbird

## Report Types

### Evening Report
- **Purpose:** Forecast for next day's hike
- **Data:** Next 24 hours, hourly
- **Focus:** Temperature, precipitation, wind
- **Risk:** Highlight any warnings for next day

### Morning Report
- **Purpose:** Updated forecast for current day
- **Data:** Next 12 hours, hourly
- **Focus:** Changes from evening report
- **Risk:** Immediate warnings (next 6 hours)

### Alert Report
- **Purpose:** Urgent weather change
- **Data:** Next 6 hours, hourly
- **Focus:** Changed conditions
- **Risk:** High/critical warnings only
- **Trigger:** Significant risk increase

## Compact Format (Optional)

For SMS gateway email-to-SMS:
- **Max 160 characters**
- **Format:** `[Location] [Date] [Temp] [Precip] [Wind] [Risk]`
- **Example:** `GR20-E3 01.02 12-18°C 5mm W20 RISK:Thunder@14h`

See: Compact Formatter spec (when implemented)

## Debug Consistency Rule

**CRITICAL:** Debug info in email MUST match console output

```python
# Generate debug info ONCE
debug_info = debug_buffer.get_all()

# Use SAME info for both outputs
console.print(debug_info)
email.attach_debug(debug_info)
```

**Never** generate separate debug for email vs console!

## Size Limits

- **Max email size:** 5 MB (including HTML + plain text)
- **Max table rows:** 50 (limit hourly data)
- **Max debug size:** 1 MB (truncate if larger)

## Attachments

**Avoid attachments** for MVP:
- Inline all data in HTML
- Use `<details>` for optional content
- Future: PDF reports as attachment

## Validation

Before sending, validate:
- [x] Subject contains report type + location + date
- [x] HTML is well-formed (valid tags)
- [x] Plain text alternative exists
- [x] Table has headers and data rows
- [x] Risk warnings (if applicable) are visible
- [x] Debug info matches console (if enabled)

## E2E Test Requirements

Email tests MUST:
1. Send real email via SMTP
2. Retrieve via IMAP
3. Parse HTML content
4. Verify table structure
5. Check data values (plausibility)
6. Verify debug consistency

**Use validator:**
```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

**Reference:** `tests/tdd/test_html_email.py::TestRealGmailE2E`

## Common Issues

### Issue: Email appears as plain text
- **Cause:** HTML not set as primary part
- **Fix:** Use `MIMEMultipart('alternative')` with HTML first

### Issue: Table breaks in Outlook
- **Cause:** Complex CSS
- **Fix:** Use inline styles, simple borders

### Issue: Debug info differs from console
- **Cause:** Separate debug generation
- **Fix:** Generate once, use same data

### Issue: Unicode characters broken
- **Cause:** Missing charset
- **Fix:** Set `Content-Type: text/html; charset=UTF-8`

## References

- Email Spec: `docs/reference/renderer_email_spec.md`
- Real E2E Tests: `tests/tdd/test_html_email.py`
- SMTP Mailer Spec: `docs/specs/modules/smtp_mailer.md`
