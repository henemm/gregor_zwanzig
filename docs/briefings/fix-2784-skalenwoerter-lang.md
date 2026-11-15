---
spec_file: docs/specs/modules/i18n_skalenwoerter_lang_2784.md
spec_sha256: ee75875fc8be70a619edc768bb9804cc4e106f8bc0d6d440aeea891f7abc0cd0
spec_frozen_sha256: add98b17dc64e3e9e111fc82c42e7e7bc500745a0afb48d1f1fc84bf26f5930b
---

# PO-Briefing: fix-2784-skalenwoerter-lang

- **Spec:** docs/specs/modules/i18n_skalenwoerter_lang_2784.md
- **Issue:** #2784
- **Erstellt:** 2026-11-15

## Was gebaut wird

Englischsprachige Nutzer sehen in Telegram-Briefing und Alarm-Stundenzeilen englische Stufenwörter statt „leicht“ oder „kein“.

## Definition of Done

Ein englisches Briefing und ein englischer Alarm zeigen kein deutsches Stufenwort mehr, deutsche Ausgaben bleiben unverändert, und die Änderung läuft auf Produktion.

## Wie geprüft wird

Tests rendern echte Briefings und Alarme auf Englisch und Deutsch; sie belegen die Wörter, nicht das Aussehen in der echten Zustellung.

## Kritische Anmerkungen

- Im englischen Telegram-Ausblick bleibt das Gewitterwort deutsch, gemäß früherer Entscheidung; Himmelsrichtungen bleiben unverändert (Punkt 3 des Tickets bewusst nicht angefasst).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
