---
spec_file: docs/specs/modules/feat_2913_abgleich_ganzseite.md
spec_sha256: 8cd89509a369e657ac6a2ab069deb8a0441b67dc35a3fe691c4168af5d660e57
spec_frozen_sha256: 96c8a7df1d86c080106f82a5a412741d8bfbad6e6c7251c0146545ca9b638d3d
---

# PO-Briefing: feature-2913-abgleich-ganzseite

- **Spec:** docs/specs/modules/feat_2913_abgleich_ganzseite.md
- **Issue:** #2913
- **Erstellt:** 2026-11-12

## Was gebaut wird

Der Seitenabgleich prüft die ganze Seite, meldet zusätzliche Texte und wird rot, solange eine Abweichung keinen Verantwortlichen hat.

## Definition of Done

Der Abgleich auf der Testumgebung läuft in Deutsch und Englisch ohne Rot durch, jede Abweichung hat einen Verantwortlichen, die Tabelle steht im Ticket.

## Wie geprüft wird

Automatische Tests belegen Logik und Abnahmeregel; die echte Seite wird nur auf der Testumgebung geprüft, Aussehen bleibt ungeprüft.

## Kritische Anmerkungen

- Gefundene Abweichungen werden nicht behoben, nur zugeordnet; die Zuordnungsliste könnte zum Abstellgleis werden.
- Gegenrichtung prüft nur Desktop und Normalzustand; Handy-Ansicht und Fehlerzustände folgen als eigenes Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
