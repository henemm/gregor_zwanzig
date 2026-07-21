---
entity_id: bug_198_notify_test_resend
type: bugfix
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [bugfix, mail, channel-test, resend]
---

<!-- Issue #198 — Channel-Test sendet über Resend statt Gmail -->

# Bug #198 — Channel-Test sendet über Resend statt Gmail

## Approval

- [ ] Approved

## Purpose

`POST /api/notify/test` (Channel-Test-Button auf `/account`-Seite) sendet Test-Mails über Production-SMTP (Resend), nicht über Gmail. Memory-Regel "Test-Mails IMMER über Gmail" wird verletzt, weil `_is_test_user("default")` False liefert (kein "test"/"tdd" im Namen).

Fix: Channel-Tests sind konzeptionell **immer** Tests. Endpoint zwingt `Settings().for_testing()` unabhängig vom User.

## Source

- **File:** `api/routers/notify.py` Z. 27-29 — fehlende `.for_testing()`-Anwendung
- **Identifier:** `test_notify()` Endpoint

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.app.config.Settings` | bestehend | `for_testing()` und `with_user_profile()` Pattern |
| `_is_test_user` | bestehend | Bleibt unverändert |

## Implementation Details

Eine Zeilenänderung:

```python
# vorher
settings = Settings().with_user_profile(user_id)

# nachher
settings = Settings().with_user_profile(user_id).for_testing()
```

`for_testing()` setzt `smtp_host` auf `google_smtp_host` etc. Damit gehen alle Channel-Test-Mails über Gmail.

## Acceptance Criteria

- **AC-1:** Given `api/routers/notify.py` / When der Source-Code gelesen wird / Then enthält die Settings-Zeile in `test_notify()` `.for_testing()` als letzten Call
- **AC-2:** Given `Settings().with_user_profile("default").for_testing()` / When `smtp_host` gelesen wird / Then liefert es den Gmail-Host (`smtp.gmail.com` o.ä., aus `google_smtp_host`), NICHT `smtp.resend.com`
- **AC-3:** Given Channel-Test-Endpoint mit user_id "default" / When er aufgerufen wird / Then nutzt EmailOutput die `for_testing()`-Settings (smtp_host = google_smtp_host)

## Expected Behavior

- **Input:** POST /api/notify/test mit body `{"channel": "email"}` + query `?user_id=default`
- **Output:** Mail geht über Gmail (`smtp.gmail.com`), nicht über Resend
- **Side effects:** Keine — User-Profil wird nicht verändert

## Known Limitations

- Auth-Check fehlt nach wie vor — separater Issue
- Wenn `google_smtp_host`/`google_smtp_user` nicht konfiguriert sind, fällt `for_testing()` zurück auf den normalen Host (siehe `for_testing()`-Implementation)

## Changelog

- 2026-05-11: Initial spec — Issue #198
