---
spec_file: docs/specs/modules/feat_3196_trip_tempo_etappen.md
spec_sha256: 2963f41e6ee4326f0d031e804b28f26fbc79d8ecbe3b03bfb8226599d1e643db
spec_frozen_sha256: 0f1b1d21cacb3c37a2d17b03a891ab8c98107f53e67d1c1ebcc9f236d4143da4
---

# PO-Briefing: feat-3196-trip-tempo-etappen

- **Spec:** docs/specs/modules/feat_3196_trip_tempo_etappen.md
- **Issue:** #3196
- **Erstellt:** 2026-11-20

## Was gebaut wird

Im Reiter Etappen wählt man Fortbewegung und Grundtempo; die Aktivitäts-Chips im Trip-Kopf entfallen, Gehzeiten folgen dem Alpenverein-Modell.

## Definition of Done

Jeder Trip zeigt Fortbewegung und Grundtempo, der Kopf hat keine Chips mehr, Texte sind deutsch und englisch, die Staging-Prüfung ist bestanden.

## Wie geprüft wird

Automatische Tests und Staging-Abnahme belegen Rechnung, Migration, Nutzertrennung und Sprachen; ob die neuen Gehzeiten im Gelände stimmen, prüft kein Test.

## Kritische Anmerkungen

- Alle Bestandstrips bekommen einmalig kürzere Gehzeiten, daher verschieben sich bewertete Stunden und Alarme (von dir akzeptiert).
- Alte Aktivitäten Skitour und MTB werden zu „zu Fuß 4 km/h“; im Bestand gibt es sie nicht.
- Karte zeigt nur Grundtempo; Issue nannte noch Aufstieg, dies entspricht deiner Entscheidung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
