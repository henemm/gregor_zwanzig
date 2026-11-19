---
spec_file: docs/specs/modules/ganzseitenaufnahme_fixed_ausblenden.md
spec_sha256: d8296248c20da19b03d1b48e0dc88f26732297d821284c4f2e543eba1cfc32a9
spec_frozen_sha256: 0e261208fc524c1159d4243d767a0955cb22fac050879ffad8792a9a528e9b3b
---

# PO-Briefing: feat-3013-aufnahme-fixed-ausblenden

- **Spec:** docs/specs/modules/ganzseitenaufnahme_fixed_ausblenden.md
- **Issue:** #3013
- **Erstellt:** 2026-11-19

## Was gebaut wird

Ganzseiten-Aufnahmen für den Bildabgleich zeigen keine schwebende Handy-Navigation mehr, der Inhalt bleibt unverdeckt.

## Definition of Done

Selbsttest grün, und eine Staging-Aufnahme in Handybreite für Trip und Orte zeigt den Inhalt ohne schwebende Navigation.

## Wie geprüft wird

Fünf Browser-Tests mit Pixelprüfung belegen Ausblenden und Wiederherstellen; echte App-Seiten prüft nur der manuelle Staging-Lauf.

## Kritische Anmerkungen

- Abweichung: Ticket nennt fixed und sticky, die Spec blendet nur fixed aus; sticky bleibt sichtbar.
- Ticket sagt "außerhalb des geprüften Bereichs"; die Spec blendet alle fixed-Elemente aus, auch offene Dialoge.

## Freigabe-Frage

Darf mitlaufende (sticky) Elemente im Foto sichtbar bleiben, obwohl das Ticket sie ebenfalls ausblenden wollte?

## Ampel

Ampel: rot
