---
spec_file: docs/specs/modules/email_login_identifier.md
spec_sha256: 15ae8ce42f74cab14a8f456bec84c4819f07820bfa238d633819f357da8a5f03
spec_frozen_sha256: 8647786b686d6f4de03e90d793eab3971d800796f3a1d9e62cd97096dfe864a8
---

# PO-Briefing: feat-2194-email-login

- **Spec:** docs/specs/modules/email_login_identifier.md
- **Issue:** #2194
- **Erstellt:** 2026-11-02

## Was gebaut wird

Nutzer melden sich künftig mit ihrer E-Mail-Adresse statt eines selbst gewählten Benutzernamens an.

## Definition of Done

Anmeldung, Passwort-vergessen und Passkey funktionieren mit E-Mail; neue Konten entstehen ohne Benutzernamen; Testkonten und Altkonten loggen weiter mit ihrer Kennung ein.

## Wie geprüft wird

Automatisierte Tests belegen Login, Mehrfachtreffer, Testkonten und Nutzertrennung; Staging-Skripte laufen erst im Deploy, Dokumentation wird nur per Textprüfung belegt.

## Kritische Anmerkungen

- Altkonten und Testkonten behalten dauerhaft den Login per Kennung; der Benutzername entfällt also nur in der Oberfläche, nicht im System.
- Bei doppelt vergebener E-Mail-Adresse gelingt der E-Mail-Login nicht; aktuell gibt es laut Messung keine Duplikate.
- Registrierung als Testkonto ist ohne Admin-Recht möglich und erlaubt freie Kennung; bekannt, bewusst nicht Teil dieses Tickets.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
