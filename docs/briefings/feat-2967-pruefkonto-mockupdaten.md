---
spec_file: docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md
spec_sha256: f4bd707da7a6fcc5d31ce488c17bbaf00ff244ab3e32553499e2fb7747955c54
spec_frozen_sha256: 0fcbb256085d9c33832a56419adf1be549e2fb02b9158dd7cfb198e266b1e3f8
---

# PO-Briefing: feat-2967-pruefkonto-mockupdaten

- **Spec:** docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md
- **Issue:** #2967
- **Erstellt:** 2026-11-19

## Was gebaut wird

Ein Werkzeug füllt das Staging-Prüfkonto mit den Mockup-Beispieldaten: Trip Mallorca, Vorlage, Orts-Vergleich und alle vier verbundenen Kanäle.

## Definition of Done

Das Werkzeug läuft zweimal nacheinander auf Staging fehlerfrei, der zweite Lauf ändert nichts, und ein Runbook beschreibt Seed und Abgleich.

## Wie geprüft wird

Automatische Tests gegen einen Nachbau des Servers decken alle Kriterien ab; der echte Staging-Lauf bleibt manuell, der Abgleich selbst gehört zu #3151.

## Kritische Anmerkungen

- Die 247 Scheinabweichungen verschwinden erst durch Folge-Issue #3151, nicht durch dieses Ticket (PO-Entscheid vom 19.11.).
- Der Vergleich heißt womöglich „Westfalen“ statt „Münsterland“, falls die Suche kollidiert; Kriterium nennt nur „Münsterland“.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
