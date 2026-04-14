---
entity_id: e2e_imap_stalwart_migration
type: bugfix
created: 2026-04-14
updated: 2026-04-14
status: draft
version: "1.0"
tags: [imap, email, stalwart, e2e, bugfix, configuration]
---

# E2E IMAP Stalwart Migration

## Approval

- [ ] Approved

## Purpose

Replace all hardcoded Gmail IMAP references (`imap.gmail.com`, `[Google Mail]/Gesendet`, Gmail credentials) with the configured Stalwart IMAP settings already present in `.env`. Six files retain relics from the Gmail era that cause E2E email verification and test runs to fail against the production Stalwart server at `mail.henemm.com`.

## Source

- **File:** Multiple (6 files, see Implementation Details)
- **Identifier:** IMAP connection setup in E2E hooks, validators, and tests
- **Reference Implementation:** `src/services/inbound_email_reader.py` lines 46–56

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings` | Class (`src/app/config.py`) | Provides `imap_host`, `imap_user`, `imap_pass`, `imap_port` fields |
| `GZ_IMAP_HOST` | Env var (`.env`) | Stalwart host — value: `mail.henemm.com` |
| `GZ_IMAP_USER` | Env var (`.env`) | Stalwart user — value: `gregor_zwanzig` |
| `GZ_IMAP_PASS` | Env var (`.env`) | Stalwart password |
| `inbound_email_reader.py` | Module | Canonical reference pattern for IMAP connection |

## Root Cause Analysis

### Current State (BROKEN)

All six files connect to IMAP using one of these patterns:

```python
# Pattern A — hardcoded Gmail host + Gmail folder
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(settings.smtp_user, settings.smtp_pass)
imap.select("[Google Mail]/Gesendet")

# Pattern B — wrong env var names
imap_user = os.getenv("GZ_SMTP_USER")
imap.select("[Google Mail]/Gesendet")
```

These patterns fail because:
1. `imap.gmail.com` is unreachable from the production server
2. `GZ_SMTP_USER` / `GZ_SMTP_PASS` are SMTP credentials, not IMAP credentials
3. Gmail folder names (`[Google Mail]/Gesendet`) do not exist on Stalwart

### Working Pattern (from `inbound_email_reader.py`)

```python
imap_host = settings.imap_host or settings.smtp_host
imap_user = settings.imap_user or settings.smtp_user
imap_pass = settings.imap_pass or settings.smtp_pass
imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
imap.login(imap_user, imap_pass)
imap.select("INBOX")
```

Stalwart standard folder names: `INBOX`, `Sent Items`, `Drafts`, `Junk Mail`, `Deleted Items`

## Implementation Details

Apply the reference pattern to all six files. Each change is a pure substitution with no logic changes.

### File 1: `.claude/hooks/e2e_browser_test.py` (lines 163–165)

Replace:
```python
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(settings.smtp_user, settings.smtp_pass)
imap.select("[Google Mail]/Gesendet")
```
With:
```python
imap_host = settings.imap_host or settings.smtp_host
imap_user = settings.imap_user or settings.smtp_user
imap_pass = settings.imap_pass or settings.smtp_pass
imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
imap.login(imap_user, imap_pass)
imap.select("INBOX")
```

### File 2: `.claude/hooks/email_spec_validator.py` (lines 38–40)

Same substitution as File 1.

### File 3: `.claude/tools/output_validator.py` (line 106)

Replace the Gmail default fallback string `"imap.gmail.com"` with `settings.imap_host or settings.smtp_host`. This file uses a dict-based config — change the `host` default from `"imap.gmail.com"` to `None` and fix env var fallbacks from `IMAP_USER`/`IMAP_PASSWORD` to `GZ_IMAP_USER`/`GZ_IMAP_PASS`.

### File 4: `tests/tdd/test_html_email.py` (lines 475, 479)

Replace hardcoded `"imap.gmail.com"` host and Gmail folder reference with settings-based values using the reference pattern.

### File 5: `tests/e2e/test_e2e_story3_reports.py` (lines 307–309)

Locate all `imap.gmail.com` references and replace with the reference pattern. Select `"INBOX"` instead of any Gmail-specific folder.

### File 6: `tests/e2e/test_e2e_friendly_format_config.py` (lines 34, 35, 74)

Replace `"imap.gmail.com"` host, Gmail folder, and `GZ_SMTP_USER` / `os.getenv("GZ_SMTP_USER")` with the reference pattern using `settings.imap_user`.

## Expected Behavior

- **Input:** E2E hooks or tests that need to verify a sent email exists in the mailbox
- **Output:** Successful IMAP login to `mail.henemm.com` and retrieval of messages from `INBOX`
- **Side effects:** None — all other logic (search queries, message parsing) remains unchanged

## Known Limitations

- The `settings.imap_port` default must be 993 (SSL). Verify this is set in `Settings` before applying changes.
- Tests that search the sent folder by Gmail name will need to search `INBOX` or `Sent Items` on Stalwart; confirm correct folder per test intent.

## Changelog

- 2026-04-14: Initial spec created — 6-file Gmail IMAP relic removal, migration to Stalwart settings
