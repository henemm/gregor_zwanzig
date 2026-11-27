---
spec_file: docs/specs/modules/fix_3462_testalarm_beispielwerte.md
spec_sha256: ece00ba7917a7f38e9d8c6e6fa0f2f1de05644c3337ebc7a508de7a7d74b4420
spec_frozen_sha256: b3a57198397f138e4226fb7cbdbeec662fae92fc13129574771c6569eb9ed766
---

# PO-Briefing: fix-3462-testalarm-beispielwerte

- **Spec:** docs/specs/modules/fix_3462_testalarm_beispielwerte.md
- **Issue:** #3462
- **Erstellt:** 2026-11-27

## Was gebaut wird

Der Test-Alarm zeigt Beispielwerte, die die Schwelle klar überschreiten, und jede Wettergröße steht darin nur einmal.

## Definition of Done

In zugestellten Test-Alarm-Mails (Trip und Ortsvergleich, Deutsch und Englisch) steht nie „unter deiner Alarm-Schwelle“ und keine Wettergröße doppelt.

## Wie geprüft wird

Automatische Tests am echten Mail-Aufbau für alle vier Kanäle, dazu echt zugestellte Staging-Mails; echte Alarme bleiben unberührt.

## Kritische Anmerkungen

- Sind Kälte- und Hitze-Alarm beide aktiv, zeigt das Beispiel nur „Temp“ einmal; die Hitzeseite fehlt dann im Beispiel.
- Der Rückfall-Beispielalarm ändert sich von 40→60 auf 40→100 km/h, wörtlich nicht verlangt, aber zweckmäßig.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
