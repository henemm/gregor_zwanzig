---
spec_file: docs/specs/modules/rework_2845_hub_reiterleiste.md
spec_sha256: d2c7525754bf93a7edcff6f14c97aa808a8d805a3d3cdad5537262217168ec91
spec_frozen_sha256: 2cfe844bf849980b7ca6f7f0ce3e184b6f8344c48d7421e78584deb7ee4d90bd
---

# PO-Briefing: rework-2845-hub-reiterleiste

- **Spec:** docs/specs/modules/rework_2845_hub_reiterleiste.md
- **Issue:** #2845
- **Erstellt:** 2026-11-09

## Was gebaut wird

Trip und Ortsvergleich bekommen am Computer exakt dieselbe Reiterleiste: gleiche Schrift, Farbe, Linie und Höhe.

## Definition of Done

Bei 1440 Pixel Breite sehen die Reiterleisten beider Seiten gleich aus, ohne Höhenunterschied, und auf dem Handy ist alles unverändert.

## Wie geprüft wird

Automatische Browser-Tests messen beide Seiten gegeneinander, auch Kontrast und Handy; ob es gefällt, beurteilt nur dein Blick.

## Kritische Anmerkungen

- Abweichung vom Ticket: Die Uhrzeit-Auffälligkeit (CEST gegen CET) ist ausgegliedert in Issue #2869; #2845 bleibt dafür offen.
- Der Ortsvergleich wird am Computer etwa 6 Pixel höher und seine Reiter dunkler; der Trip bleibt unverändert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
