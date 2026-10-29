---
spec_file: docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md
spec_sha256: be2a02ddb80dd97de554d67a3e7235a580c7b19b34e8ec0f4acabe0580b06344
spec_frozen_sha256: c2f26355a4f2207fbd489bafb82445676c10354b43594205673668b4fce522f1
---

# PO-Briefing: fix-1814-telegram-webhook-header

- **Spec:** docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md
- **Issue:** #1814
- **Erstellt:** 2026-10-29

## Was gebaut wird

Telegram-Befehle kommen über eine Adresse ohne Geheimnis an; die alte Adresse läuft übergangsweise weiter.

## Definition of Done

Beide Umgebungen sind neu registriert, ohne Geheimnis in der Adresse, und der Staging-Bot beantwortet einen Befehl.

## Wie geprüft wird

Tests prüfen Skript und Zugang automatisch; Neuregistrierung und Bot-Antwort werden nur live beim Deploy nachgewiesen.

## Kritische Anmerkungen

- Abweichung vom Ticket: Auch Prod betroffen; Header-Prüfung gab es schon, nur die Adresse ändert sich.
- Altes Geheimnis bleibt bis zur Folge-Scheibe gültig; Rotation und Abschalten der alten Adresse stehen aus.
- Zwei-Nutzer-Kriterium widerspricht der Spec („nicht einschlägig“), prüft nur Weiterreichung; überzogen, harmlos.

## Freigabe-Frage

Soll die Adresse geändert und Rotation samt Abschaltung der alten Adresse als Folge-Scheibe im selben Ticket nachgezogen werden?

## Ampel

Ampel: rot
