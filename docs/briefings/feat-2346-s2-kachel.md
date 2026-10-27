---
spec_file: docs/specs/modules/feat_2346_cockpit_paritaet.md
spec_sha256: 7627690ca1b3e85ce03397ec76b20cf47eee1cefc97d15d050375b2a9fae4b08
spec_frozen_sha256: e470eeb0ed7f2361118f986b23c92d762a7fb60535111196ef51de3bd981e100
---

# PO-Briefing: feat-2346-s2-kachel

- **Spec:** docs/specs/modules/feat_2346_cockpit_paritaet.md (nur Scheibe S2)
- **Issue:** #2346
- **Erstellt:** 2026-10-24

## Was gebaut wird

Trip- und Vergleichs-Kachel auf der Startseite zeigen dieselben Angaben, gleich angeordnet, aus einem gemeinsamen Baustein.

## Definition of Done

Beide Kacheln sind gleich aufgebaut; Trip-Kanäle folgen den eingeschalteten Kanälen; die alten Doppel-Bausteine sind entfernt.

## Wie geprüft wird

Automatische Tests prüfen Feldreihenfolge, Kanäle und Links; Optik und echtes Klicken prüft nur eine Sichtprüfung auf Staging.

## Kritische Anmerkungen

- Letzter Versand beim Trip bleibt „—" bis Scheibe S4; Ticket bleibt offen.
- Vergleichs-Kachel sieht danach anders aus; Test-Kennung der Trip-Kachel ändert sich.
- Status-Anzeige und Karten-Klick haben keinen eigenen Test.

## Freigabe-Frage

Gibst du Scheibe S2 frei, trotz sichtbarer Änderung der Vergleichs-Kachel und „—" beim letzten Trip-Versand bis S4?
