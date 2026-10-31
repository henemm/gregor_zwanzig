---
spec_file: docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md
spec_sha256: df2d022cb6de33d2d6a4d68116d1be94084cf2083436f0af9793897866a1600d
spec_frozen_sha256: e3da38795056cd11074550e244e30c0f01bb634d30f19a82e7810317dcfea03e
---

# PO-Briefing: feat-1442-s3-rest-eu

- **Spec:** docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md
- **Issue:** #1442
- **Erstellt:** 2026-10-30

## Was gebaut wird

Wanderer in Portugal, den Niederlanden und Polen erhalten amtliche Unwetterwarnungen in Alarmen und Briefings.

## Definition of Done

Für Orte in diesen drei Ländern erscheinen aktuelle amtliche Warnungen; fällt der Warndienst aus, steht „nicht abrufbar"; auf Staging bestätigt.

## Wie geprüft wird

Tests mit echten Feed-Proben und ein Live-Test je Land belegen Treffer, Ausfall und Grenzorte; die Lizenzfrage prüfen sie nicht.

## Kritische Anmerkungen

- Ticket verlangte sechs Länder; Spanien, UK, Belgien fehlen hier. Der Mallorca-Trip hängt an der separaten Spanien-Lieferung.
- Lizenz der Zonendaten ungeklärt; drei weitere Länder stützen sich darauf, Klärung liegt beim PO.
- Spanien muss vorher live sein, sonst stoppt die Umsetzung.

## Freigabe-Frage

Sollen Portugal, Niederlande und Polen jetzt ausgeliefert werden, obwohl Spanien, UK, Belgien später folgen und die Datenlizenz ungeklärt bleibt?

## Ampel

Ampel: rot
