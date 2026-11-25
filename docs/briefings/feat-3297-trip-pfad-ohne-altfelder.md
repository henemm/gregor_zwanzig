---
spec_file: docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md
spec_sha256: 62920e8a0d363cf55cdcc69199dd142a95b9c0ee3c2a85080581ed2b9ab4f00f
spec_frozen_sha256: 95a2b422958c6248b04884c4d26df636fad394ebd0d46c20c0316303fce10336
---

# PO-Briefing: feat-3297-trip-pfad-ohne-altfelder

- **Spec:** docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md
- **Issue:** #3297 (zusammen mit #3020)
- **Erstellt:** 2026-11-25

## Was gebaut wird

Veralteter, nicht mehr eingebundener Trip-Code wird entfernt; Trips speichern nur noch die Tabelle „Was steht wo“, Home liest sie.

## Definition of Done

Trip anlegen und speichern sendet keine alten Felder mehr, Home zeigt „Layout konfiguriert“ bei Trips mit Tabelle, beide Tickets sind geschlossen.

## Wie geprüft wird

Automatische Tests prüfen gesendete Daten und Home-Anzeige, ein Staging-Durchlauf die Bedienung; Aussehen und Mails bleiben unverändert und werden nicht eigens verglichen.

## Kritische Anmerkungen

- Trips ohne Tabellenzeilen zeigen auf Home „Layout“ als offen; laut Spec betrifft das in Produktion keinen Trip.
- Ob neue Trips ohne geöffneten Wetter-Reiter eine Tabelle erhalten, ist offen; Haken bliebe dann bis zum ersten Speichern leer.
- Acceptance Criterion 9 nennt „korrekt gespeichert“ vage, der zugehörige Staging-Test prüft aber konkret, dass Werte stehen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
