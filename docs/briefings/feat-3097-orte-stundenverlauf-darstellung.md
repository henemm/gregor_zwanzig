---
spec_file: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md
spec_sha256: e368ad09f863fe512bb70d6db932bc99943ed7db4ac043076b951ffacf0b8fa5
spec_frozen_sha256: 5ebee8990ddc69ed7754705f62b91c95487b4f02c039821d5fe4523cf11cc358
---

# PO-Briefing: feat-3097-orte-stundenverlauf-darstellung

- **Spec:** docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md
- **Issue:** #3097
- **Erstellt:** 2026-11-17

## Was gebaut wird

Im Stundenverlauf der Orts-Vergleich-Mail lässt sich je Zeile zwischen Zahl und Einfach-Darstellung umschalten.

## Definition of Done

Eine umgestellte Zeile erscheint in Mail und Editor-Vorschau einfach, ohne Einstellung bleibt die Mail unverändert, und beide Prüffälle stehen auf grün.

## Wie geprüft wird

Automatische Tests rendern echte Mails und prüfen Zellen, Nutzertrennung und Speichern; zusätzlich wird eine echt zugestellte Staging-Mail geprüft.

## Kritische Anmerkungen

- Temperatur und Gewitter bekommen keinen Umschalter, weil keine Einfachform existiert; bewusst ausgenommen, dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
