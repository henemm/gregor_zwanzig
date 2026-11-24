---
spec_file: docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
spec_sha256: d4ddc4d2faa986180cfe5a9c8617e566c5746cb147a8822bdee9dc42d3bddfbf
spec_frozen_sha256: 3329f7bfd3baa6a454ab438c005ef2eafd0851e57982d5d73f13295fa9bd841e
---

# PO-Briefing: feat-3305-tabelle-trip-anlegen

- **Spec:** docs/specs/modules/feat_3305_tabelle_trip_anlegen.md
- **Issue:** #3305
- **Erstellt:** 2026-11-24

## Was gebaut wird

Beim Anlegen eines Trips erscheint im Schritt Wetter dieselbe Tabelle „Was steht wo“ samt Schaltern, und deine Einstellungen werden mitgespeichert.

## Definition of Done

Nach dem Anlegen zeigt der Reiter Wetter des neuen Trips genau die Haken, Formate, Reihenfolge und Schalter, die du beim Anlegen eingestellt hast.

## Wie geprüft wird

Automatische Tests und ein Durchlauf gegen Staging mit zwei Nutzern prüfen Speichern, Nachladen und genau einen Anlege-Aufruf; Orte und Zustellung sind nicht enthalten.

## Kritische Anmerkungen

- Mail-Format und Telegram-Kurzstil sind bis zum Folgeticket #3307 an zwei Stellen einstellbar; die Spec dokumentiert das als bekannte Einschränkung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
