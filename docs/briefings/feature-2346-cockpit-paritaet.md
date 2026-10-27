---
spec_file: docs/specs/modules/feat_2346_cockpit_paritaet.md
spec_sha256: c4e779943f946573803de994f66a72e003dd47f15fae2402b557d6789bdfd9b4
spec_frozen_sha256: 370d7dea9000f757539e6cb1aeea89c03e55990c3668a0ebcd0fa3d194fd34df
---

# PO-Briefing: feature-2346-cockpit-paritaet

- **Spec:** docs/specs/modules/feat_2346_cockpit_paritaet.md
- **Issue:** #2346
- **Erstellt:** 2026-10-23

## Was gebaut wird

Trip und Ortsvergleich erscheinen auf der Startseite als gleich aufgebaute Kacheln, und die Commit-Sperre erkennt neue einseitige Dateien.

## Definition of Done

Beide Kacheln zeigen Status, nächsten und letzten Versand sowie Kanäle gleich aufgebaut; ein einseitiges Pendant wird beim Commit abgewiesen.

## Wie geprüft wird

Tests prüfen Feldreihenfolge, Kanäle und Sperre; das Aussehen beurteilt nur ein Screenshot-Vergleich auf Staging.

## Kritische Anmerkungen

- Nächster/letzter Versand hängt von Ticket 1969 (noch nicht freigegeben); bis dahin zeigen Kacheln „—“, Ticket bleibt offen.
- Sperre erkennt nur Paare, deren Partner schon existiert; etwa acht ähnlich benannte Paare bleiben unentdeckt.
- Ortsvergleich-Kachel ändert ihr Aussehen; Freigabe verlängert zugleich die Commit-Sperre bis 21.01.2027.

## Freigabe-Frage

Gibst du die Spec frei, inklusive Aussehensänderung der Ortsvergleich-Kachel und Sperren-Verlängerung?
