---
spec_file: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md
spec_sha256: 1dc16ecf5ea61da70e4eb9c8be661b8be81e0ba0ab772f54275152f11acab8ea
spec_frozen_sha256: 4d2f93870b404b5983f2435f20f7c77f5e1760a4858a0fb3b3419acf6ada36c4
---

# PO-Briefing: feature-2913-scheibe-c

- **Spec:** docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md
- **Issue:** #2913
- **Erstellt:** 2026-11-11

## Was gebaut wird

Im Wetter-Reiter werden Nicht-im-Briefing, Warnungen, Radar und Tagesfenster aus einheitlichen Bausteinen nach Mockup neu gebaut.

## Definition of Done

Auf Staging stimmen die vier Abschnitte in Deutsch und Englisch mit dem Mockup überein, Einstellungen bleiben je Nutzer nach Neuladen erhalten.

## Wie geprüft wird

Automatische Tests und Staging-Abläufe mit zwei Nutzern prüfen Aussehen, Speichern und Sprachen; eine unabhängige Bildkontrolle vergleicht mit dem Mockup.

## Kritische Anmerkungen

- Radar-Regen fehlt beim Trip, obwohl das Mockup ihn zeigt; Ticket verlangt „lückenlos“. Kommt erst mit Ticket 2800.
- Mockup-Chips für Metriken außerhalb der Vorlage werden nicht nachgebaut, ebenfalls Abweichung von „lückenlos“.
- Alter Tagesfenster-Baustein wird nicht gelöscht, obwohl das Ticket Löschen in derselben Scheibe verlangt.

## Freigabe-Frage

Darf Radar-Regen beim Trip bis Ticket 2800 fehlen, obwohl das Mockup ihn zeigt?

## Ampel

Ampel: rot
