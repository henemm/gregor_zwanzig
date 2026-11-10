---
spec_file: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md
spec_sha256: 771e16514d8efc29246178d5ba7ef80d33431b9e84aa8261d4886207099514fe
spec_frozen_sha256: 4757027394128b2abd00391bbdcc459248f2a83d0aced81ab59212637e0a3cbd
---

# PO-Briefing: einstellungen-neu-neustart

- **Spec:** docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md
- **Issue:** #2913
- **Erstellt:** 2026-11-10

## Was gebaut wird

Eine Regel samt Prüfwerkzeug, damit neue Oberflächen nur aus Design-Bausteinen entstehen, plus Soll-Liste des Mockups zum Abgleich.

## Definition of Done

Regel steht in der Doku, der Wächter blockiert Verstöße im Merge, Elementliste und Abgleich-Bericht liegen vor, App-Verhalten unverändert.

## Wie geprüft wird

Automatische Tests mit Beispieldateien und echtem Quellbaum prüfen den Wächter; Abgleich läuft gegen Staging; Optik und Bild-Agent nur per Probelauf.

## Kritische Anmerkungen

- Nur Schritt 1–2 des Tickets; Issue #2913 darf danach nicht geschlossen werden, Bausteine und Seiten folgen separat.
- Staging-Abgleich läuft nicht in der automatischen Prüfung; nur der Hash-Vergleich schützt vor veraltetem Mockup.
- Der Bild-Agent wird nur per Probelauf geprüft; sein Befund ist schwer messbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
