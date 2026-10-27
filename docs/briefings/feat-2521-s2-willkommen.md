---
spec_file: docs/specs/modules/onboarding_willkommen_checkliste.md
spec_sha256: be12d5f2540d74ab67fbe7e37bd50976cc78c47a0739ef305456b037c7fea9b3
spec_frozen_sha256: a69a0438f3cae04dd7a619cb9339277d4406d6fcc128a870eb4804330155fd8d
---

# PO-Briefing: feat-2521-s2-willkommen

- **Spec:** docs/specs/modules/onboarding_willkommen_checkliste.md
- **Issue:** #2521
- **Erstellt:** 2026-10-17

## Was gebaut wird

Neue Nutzer sehen Willkommen und Checkliste, senden eine Testmail; „+ Neuer Vergleich" führt zum Anlegen.

## Definition of Done

Neuer Nutzer sieht Willkommen, erhält Testmail an seine Adresse; Bestandsnutzer sehen nichts; Checkliste endet nach erstem planmäßigen Briefing.

## Wie geprüft wird

Tests prüfen Sichtbarkeit, Nutzertrennung, Mailempfänger und Link; echte Zustellung und erstes Briefing sind auf Staging kaum messbar.

## Kritische Anmerkungen

- Einzige Änderung: Testmail-Entscheidung heißt nun ADR-0092 statt 0091 (Nummernkollision); Inhalt gleich, Zustimmung liegt vor.
- Testmail nutzt für echte Nutzer den echten Versandweg und löst eine frühere Regel ab.
- „Ausblenden" versteckt die Checkliste trotz offener Punkte; Issue verlangte „sichtbar bis erledigt".

## Freigabe-Frage

Freigabe mit Umnummerierung auf ADR-0092: Willkommen, Checkliste und echte Testmail nur für neu angelegte Nutzer?
