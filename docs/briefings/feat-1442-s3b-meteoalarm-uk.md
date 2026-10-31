---
spec_file: docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md
spec_sha256: aed084d3d21fa36e13c34ce9c1b5eab2c9660a16737c5067151e978ea3dfc03d
spec_frozen_sha256: a4a8ad1a9a8a9f3f874409481b7c1a3504cbadd0a9d5e2d204bcfb275855829f
---

# PO-Briefing: feat-1442-s3b-meteoalarm-uk

- **Spec:** docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md
- **Issue:** #1442
- **Erstellt:** 2026-10-31

## Was gebaut wird

Wanderpunkte in England, Schottland, Wales und Nordirland bekommen amtliche Unwetterwarnungen auf allen vier Kanälen.

## Definition of Done

Für einen Punkt in einem aktuell gewarnten britischen Gebiet erscheint die amtliche Warnung mit Stufe, Art und Zeitraum; Paris und Dublin bleiben unberührt.

## Wie geprüft wird

Tests mit echter Feed-Probe weisen Zuständigkeit, Treffer, Aufhebung, Ausfall und Kanalweg nach; der Live-Abgleich kann mangels Warnung überspringen.

## Kritische Anmerkungen

- Nur drei Warnungen im Live-Feed: echter Live-Nachweis womöglich nicht erbracht; Absicherung allein durch Probe-Daten.
- Kanalinseln und Isle of Man bleiben ohne Warnungen, bewusst dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
