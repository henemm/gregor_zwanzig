---
spec_file: docs/specs/modules/feat_2913_s3_bausteine.md
spec_sha256: cf7857d28feb53fd8e1e000041643691a0602d4f9158820145754c6c5391e4e2
spec_frozen_sha256: 47f6d3964d02976a078c4611692da24e00f819faf990727782ec46fe26b50c5d
---

# PO-Briefing: feature-2913-teil2

- **Spec:** docs/specs/modules/feat_2913_s3_bausteine.md
- **Issue:** #2913
- **Erstellt:** 2026-11-11

## Was gebaut wird

Der Wetter-Reiter wird nach dem angenommenen Mockup aus gemeinsamen Bausteinen gebaut, für Trip und Orts-Briefing identisch.

## Definition of Done

Auf Staging sehen Trip und Orts-Briefing in Hell und Dunkel, Deutsch und Englisch gleich aus, Ampelfarben sind lesbar, Grenzen speichern korrekt.

## Wie geprüft wird

Automatische Tests prüfen Farbkontraste, Bausteine und Regeltreue; das Aussehen auf Staging wird nur per Sichtvergleich abgenommen.

## Kritische Anmerkungen

- Gelb (hell) und Rot (dunkel) weichen vom Mockup ab, damit der Kontrast reicht; Folge: leicht andere Farbtöne.
- Die beiden Schalter (Warnungen, Radar) bleiben vorerst Altbau; Umbau folgt in eigenem Issue.
- Spec nennt keine Meldung mit Bild an den PO; die Staging-Screenshots werden nur intern verglichen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
