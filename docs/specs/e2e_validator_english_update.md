---
entity_id: e2e_validator_english_update
type: fix
created: 2026-01-12
updated: 2026-01-12
status: draft
version: "1.0"
tags: [e2e, validator, i18n, testing]
---

# E2E Validator English Update

## Approval

- [x] Approved (2026-01-12)

## Purpose

Update E2E validators to match the current English UI structure. The application was translated to English (commit 0225f3f) and Cloud Layer row was removed (commit e17c649), but the validators still expect the old German structure with 9 rows.

**Current state (RED):**
- Validators expect: German labels, 9 rows, "VERGLEICHEN" button
- Application delivers: English labels, 8 rows, "COMPARE" button

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **File:** `.claude/hooks/e2e_browser_test.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/cloud_cover_simplification.md` | spec | Removed Cloud Layer row (8 instead of 9) |
| `docs/specs/email_html_translation.md` | spec | Translated labels to English |

## Implementation Details

### 1. email_spec_validator.py - Update expected labels

**Before (line ~111-121):**
```python
expected_labels = [
    "Metrik",
    "Score",
    "Schneehöhe",
    "Neuschnee",
    "Wind/Böen",
    "Temperatur (gefühlt)",
    "Sonnenstunden",
    "Bewölkung",
    "Wolkenlage",
]

if len(rows) != 9:
    errors.append(f"STRUKTUR: {len(rows)} Zeilen, erwartet: 9")
```

**After:**
```python
expected_labels = [
    "Metric",
    "Score",
    "Snow Depth",
    "New Snow",
    "Wind/Gusts",
    "Temperature (felt)",
    "Sunny Hours",
    "Cloud Cover",
    # Cloud Layer removed per cloud_cover_simplification.md
]

if len(rows) != 8:
    errors.append(f"STRUKTUR: {len(rows)} Zeilen, erwartet: 8")
```

### 2. email_spec_validator.py - Update required sections

**Before (line ~133-137):**
```python
required_sections = [
    ("Zeitfenster", "Header mit Zeitfenster"),
    ("Stündliche", "Stündliche Übersicht"),
    ("Empfehlung", "Winner-Box"),
]
```

**After:**
```python
required_sections = [
    (["Time Window", "Zeitfenster"], "Header mit Zeitfenster"),
    (["Hourly", "Stündliche"], "Hourly Overview"),
    (["Recommendation", "Empfehlung"], "Winner-Box"),
]

for keywords, name in required_sections:
    if not any(kw in body for kw in keywords):
        errors.append(f"STRUKTUR: {name} fehlt")
```

### 3. email_spec_validator.py - Update plausibility checks

**Before:** Checks for "sonnenstunden" and "wolkenlage" (German)
**After:** Check for "cloud cover" and "sunny hours" format validation

### 4. email_spec_validator.py - Update format validation

**Before (line ~216):** `"wind" in row[0].lower() and "böen" in row[0].lower()`
**After:** `"wind" in row[0].lower() and "gust" in row[0].lower()`

**Before (line ~232):** `"sonnenstunden" in row[0].lower()`
**After:** `"sunny" in row[0].lower() and "hour" in row[0].lower()`

### 5. e2e_browser_test.py - Update button selectors

**Before (line 76, 145):**
```python
page.locator('button:has-text("VERGLEICHEN")').click(timeout=3000)
```

**After:**
```python
page.locator('button:has-text("COMPARE")').click(timeout=3000)
```

## Expected Behavior

After implementation:
- `email_spec_validator.py` returns exit code 0 (all checks pass)
- `e2e_browser_test.py` can click COMPARE button successfully
- Both validators accept the English UI structure

## Test Cases

1. **email_spec_validator.py** exits with code 0
2. **Browser test** finds "Cloud Cover" after clicking COMPARE
3. **Email test** finds "Hourly Overview" in sent email
4. **Negative test**: "Wolkenlage" NOT found (removed)

## Changelog

- 2026-01-12: Initial spec created
