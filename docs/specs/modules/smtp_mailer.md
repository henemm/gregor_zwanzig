---
entity_id: smtp_mailer
type: module
created: 2025-12-27
updated: 2025-12-27
status: implemented
version: "1.0"
tags: [email, smtp, channel]
---

# SMTP Mailer

## Approval

- [x] Approved

## Purpose

Versendet E-Mails ueber SMTP. Einziger aktiver Kommunikationskanal im MVP.

## Source

- **File:** `src/app/core.py`
- **Identifier:** `send_mail()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| smtplib | stdlib | SMTP-Verbindung |
| email.mime.text | stdlib | E-Mail-Formatierung |

## Implementation Details

```
Benoetigte Environment-Variablen:
- SMTP_HOST
- SMTP_PORT (default: 587)
- SMTP_USER
- SMTP_PASS
- MAIL_TO

Verbindung: STARTTLS
```

## Expected Behavior

- **Input:** subject (str), body (str)
- **Output:** None (E-Mail wird gesendet)
- **Side effects:** E-Mail-Versand an MAIL_TO

## Known Limitations

- Keine Retry-Logik
- Kein HTML-Support (nur Plain-Text)
- Kein Attachment-Support

## Changelog

- 2025-12-27: Initial spec created (migrated from existing code)
