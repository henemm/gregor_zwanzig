---
spec_file: docs/specs/modules/fix_2630_telegram_gate_modus_aenderung.md
spec_sha256: e2812a576975986d73eab49312a3b5963726ab028e0d7ebbf58224d6f4aafa0e
spec_frozen_sha256: b2dc802d41513bae3ae2fab885f5fde564d843436f18ef96122b3deb7fbaf449
---

# PO-Briefing: fix-2630-telegram-gate-scope

- **Spec:** docs/specs/modules/fix_2630_telegram_gate_modus_aenderung.md
- **Issue:** #2630
- **Erstellt:** 2026-10-27

## Was gebaut wird

Das Staging-Gate verlangt den Telegram-Live-Test nicht mehr, wenn sich an Telegram-Dateien nur Dateirechte ändern.

## Definition of Done

Eine Lieferung, die an Telegram-Dateien nur Dateirechte ändert, passiert das Staging-Gate ohne Test-Chat; jede andere Telegram-Änderung wird weiter blockiert.

## Wie geprüft wird

Tests mit echten temporären Git-Repos belegen Durchlassen reiner Rechte-Änderungen und Blockieren gemischter, unlesbarer oder neuer Dateien; echter Telegram-Versand wird nicht getestet.

## Kritische Anmerkungen

- Zweiter Befund (Teardown-Fehler im Telegram-Live-Test) wird nicht behoben, nur als Sammel-Eintrag gebucht; Ursache bleibt unbekannt.
- Erkennung ist eine enge Textliste; andere Querschnittsänderungen lösen das Gate weiter aus, und die Liste kann Schlupflöcher haben.

## Freigabe-Frage

Genehmigst du, dass nur reine Dateirechte-Änderungen den Telegram-Test überspringen und der Teardown-Fehler separat bleibt?
