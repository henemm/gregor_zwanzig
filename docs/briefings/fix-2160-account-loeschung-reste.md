---
spec_file: docs/specs/modules/account_deletion.md
spec_sha256: 89fdefdf6cecf0fcd15a981a7cd7035b8a0b50b6081f9c8edd5d1dbd03cfc024
---

# PO-Briefing: fix-2160-account-loeschung-reste

- **Spec:** docs/specs/modules/account_deletion.md
- **Issue:** #2160
- **Erstellt:** 2026-10-03

## Was gebaut wird

Konto-Löschung verlangt Passwort oder E-Mail-Code und räumt Telegram-Verknüpfungen und offene Login-Codes des Nutzers mit ab.

## Definition of Done

Löschen ohne gültigen Nachweis wird abgewiesen; danach bleiben keine Telegram-Verknüpfung oder Login-Codes zurück, andere Nutzer bleiben unberührt.

## Wie geprüft wird

Tests mit zwei Nutzern belegen Abweisung und Aufräumen; echte Zustellung der Lösch-Mail ist nur auf Staging messbar.

## Kritische Anmerkungen

- Ohne Test: Ratenbegrenzung, entfallener alter Lösch-Aufruf, Start des Aufräum-Jobs, atomares Speichern.
- Anfrage nannte frischen Login-Code; Spec nutzt eigenen Lösch-Code, Passkey-Konten können nur so löschen.
- Protokoll-Einträge mit Nutzerkennung bleiben bestehen.

## Freigabe-Frage

Darf die Löschung Passwort oder E-Mail-Code verlangen, obwohl einige Anforderungen ungetestet sind?
