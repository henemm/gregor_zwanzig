---
spec_file: docs/specs/modules/feat_2284_s2_trip_kopf.md
spec_sha256: 051e3bb9b36e58f0429f1b3ad577120583d33adfd91703086a7570ee0179ef06
---

# PO-Briefing: feat-2284-s2-trip-kopf

- **Spec:** docs/specs/modules/feat_2284_s2_trip_kopf.md
- **Issue:** #2284
- **Erstellt:** 2026-10-03

## Was gebaut wird

Im Trip ändert man Region und Aktivität direkt im Kopf; der Speicher-Chip ist in beiden Seiten identisch.

## Definition of Done

Region und Aktivität lassen sich im Trip-Kopf ändern, bleiben nach Neuladen erhalten; es erscheint genau ein Speicher-Chip.

## Wie geprüft wird

Automatische Tests prüfen Speichern, Fehler, Konflikte, Fremdzugriff und Handy-Karte; das Aussehen beurteilen sie nicht.

## Kritische Anmerkungen

- Aktivität wandert aus dem Etappen-Reiter in den Kopf als 8 Kacheln; mobil wird der Kopf höher.
- Region verschwindet aus der Zeile über dem Namen; leere Region zeigt auch im Vergleich „—".
- Mindest-Kartenhöhe mobil (200 px) ist nur geschätzt und kann sich im Test ändern.

## Freigabe-Frage

Sind Aktivität als Kacheln im Kopf und die höhere Handy-Ansicht für Sie akzeptabel?
