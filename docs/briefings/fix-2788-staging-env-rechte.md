---
spec_file: docs/specs/bugfix/fix_2788_staging_env_rechte.md
spec_sha256: f9fc14b999557a61be6e8368cd583f6898f67a19d9ca9402e37dba6b634b4fdf
spec_frozen_sha256: 8cc23c5ea06362a9d7b4637d25aff94989ec9583020baebfa64689a2e8ad2ebe
---

# PO-Briefing: fix-2788-staging-env-rechte

- **Spec:** docs/specs/bugfix/fix_2788_staging_env_rechte.md
- **Issue:** #2788
- **Erstellt:** 2026-11-11

## Was gebaut wird

Das Anlege-Skript für den englischen Testnutzer sperrt den Staging-Dienst nicht mehr aus und versteht den reinen Benutzernamen.

## Definition of Done

Nach dem Anlegen behält die Staging-Konfigurationsdatei ihre Rechte, der Staging-Versand läuft ohne Fehler, und die Anlage mit reinem Benutzernamen gelingt.

## Wie geprüft wird

Automatische Tests lassen das Skript wirklich laufen und prüfen Rechte und Adresse; die Zugriffsliste wird nur dort geprüft, wo das Werkzeug existiert.

## Kritische Anmerkungen

- Ticket wollte die Basisadresse aus der Konfiguration ableiten; die Spec setzt fest henemm.com und schliesst Ableitung ausdrücklich aus.
- Statt "640 mit Maske" fasst die Spec die Rechte bestehender Dateien gar nicht an (bewusst begründet).

## Freigabe-Frage

Ist es für dich in Ordnung, dass die Domain fest henemm.com bleibt, statt aus der Konfiguration abgeleitet zu werden?

## Ampel

Ampel: rot
