---
spec_file: docs/specs/modules/account_deletion.md
spec_sha256: 5e1228f7a1879f91231e841f750d1db949300934108b97e8e61cff1cc35c44ff
---

# PO-Briefing: fix-2160-account-loeschung-reste

- **Spec:** docs/specs/modules/account_deletion.md
- **Issue:** #2160
- **Erstellt:** 2026-10-03

## Was gebaut wird

Konto-Löschung verlangt Passwort oder E-Mail-Code und räumt alle Reste des Nutzers weg.

## Definition of Done

Löschen ohne Nachweis wird abgewiesen; danach bleibt kein Telegram-Link und kein offener Login-Code des Nutzers übrig.

## Wie geprüft wird

Tests mit zwei Nutzern belegen Abweisung und Aufräumen; echte E-Mail-Zustellung des Lösch-Codes ist nur auf Staging messbar.

## Kritische Anmerkungen

- Anonymisierung von Protokoll-Einträgen mit Nutzerkennung fehlt bewusst; diese Spuren bleiben bestehen.
- Zusätzlich: Lösch-Code per E-Mail; alter Lösch-Aufruf entfällt; Passkey-Konten brauchen den Code.
- Sperrliste für Sitzungen existiert nicht mehr; Aufräum-Job daher nur für Login-Codes, Telegram-Links, Lösch-Codes.

## Freigabe-Frage

Darf die Löschung Passwort oder E-Mail-Code verlangen, obwohl Protokoll-Anonymisierung nicht enthalten ist?
