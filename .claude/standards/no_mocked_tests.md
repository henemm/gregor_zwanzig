# No Mocked Tests Standard

**CRITICAL:** Mocked tests are **BANNED** in Gregor Zwanziger!

## The Problem with Mocks

Mocked tests prove NOTHING because:
- They test that mocks behave like mocks
- They DON'T test real API behavior
- They MISS real integration issues
- They give false confidence

## The Rule

**ALL tests MUST use real external systems:**

### Email Tests
- ✅ Real SMTP send via Gmail
- ✅ Real IMAP retrieve and verify
- ✅ Check actual email content
- ❌ NO `Mock()` for email client
- ❌ NO `patch()` for SMTP

**Reference:** `tests/tdd/test_html_email.py::TestRealGmailE2E`

### API Tests
- ✅ Real API calls to weather providers
- ✅ Real HTTP requests (not mocked)
- ✅ Handle real rate limits
- ❌ NO `responses` library
- ❌ NO `requests-mock`

### E2E Browser Tests
- ✅ Real server start/restart
- ✅ Real Playwright browser automation
- ✅ Real screenshots
- ✅ Real Safari testing (strictest!)
- ❌ NO Python function calls as "E2E"
- ❌ NO headless-only testing

**Reference:** `.claude/hooks/e2e_browser_test.py`

## How to Write Real Tests

### Email Test Pattern

```python
def test_email_delivery():
    # 1. Send real email via SMTP
    smtp_client.send(email)

    # 2. Wait for delivery
    time.sleep(2)

    # 3. Retrieve via IMAP
    imap_client = imaplib.IMAP4_SSL('imap.gmail.com')
    imap_client.login(user, password)
    emails = imap_client.search(...)

    # 4. Verify content
    assert subject in email.subject
    assert expected_text in email.body
```

### API Test Pattern

```python
def test_weather_provider():
    # Real API call
    response = requests.get(
        'https://api.met.no/weatherapi/...',
        headers={'User-Agent': 'Gregor-Zwanziger'}
    )

    # Real validation
    assert response.status_code == 200
    data = response.json()
    assert 'temperature' in data
```

### E2E Test Pattern

```bash
# 1. Stop old server
pkill -f "python3 -m src.app.main"

# 2. Start new server with current code
python3 -m src.app.main &

# 3. Run browser test
uv run python3 .claude/hooks/e2e_browser_test.py browser \
    --check "Feature Name" \
    --action "compare"

# 4. Check screenshot visually
# 5. Test email via SMTP+IMAP
```

## What About Unit Tests?

**Unit tests CAN use mocks** for:
- Internal dependencies (within codebase)
- Fast feedback during development
- Edge case simulation

**BUT:**
- Must ALSO have real E2E test
- E2E test is proof of correctness
- Unit tests are supplementary

## E2E Validation Gates

**BEFORE saying "E2E Test bestanden":**

### For Email Features
```bash
# MANDATORY: Run email spec validator
uv run python3 .claude/hooks/email_spec_validator.py

# ONLY if exit 0 → E2E passed
```

Checks:
- Email structure (headers, body, HTML)
- Location count (expected number)
- Data plausibility (values in range)
- Format compliance (contract)
- Completeness (no missing fields)

### For Browser Features
```bash
# MANDATORY: Run browser E2E hook
uv run python3 .claude/hooks/e2e_browser_test.py browser \
    --check "Feature" \
    --action "compare"

# ONLY if exit 0 → E2E passed
```

Checks:
- Server starts without errors
- Browser loads page
- Feature works in Safari (strictest)
- Screenshot comparison (visual regression)

## Simple String Checks Are NOT E2E

❌ **This is NOT an E2E test:**
```python
def test_email():
    result = generate_email()
    assert "Subject" in result  # Too simple!
```

✅ **This IS an E2E test:**
```python
def test_email():
    send_via_smtp(email)
    received = retrieve_via_imap()
    assert received.subject == expected
    assert parse_html(received.body) == expected_data
```

## Enforcement

Violations will be caught by:
- Code review during spec approval
- Hook blocking (`tdd_enforcement.py`)
- Manual verification before "test passed" declaration

## Exceptions

None. This is a zero-tolerance policy.

If testing is too slow:
- Use test environment with test accounts
- Cache API responses (but test cache miss path!)
- Run expensive tests less frequently (but run them!)

## Why This Matters

Real tests catch real bugs:
- Wrong SMTP authentication
- HTML rendering issues in email clients
- Safari-specific JavaScript failures
- API changes by providers
- Network timeout handling

Mocked tests would miss ALL of these!
