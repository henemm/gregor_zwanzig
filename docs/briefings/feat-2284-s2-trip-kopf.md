---
spec_file: docs/specs/modules/feat_2284_s2_trip_kopf.md
spec_sha256: ba187bbe68ebc1b3a5ecd24f1aee0decdcf0396d771f23893f57cf42df3fa2ac
---

# PO-Briefing: feat-2284-s2-trip-kopf

- **Spec:** docs/specs/modules/feat_2284_s2_trip_kopf.md (Version 1.1)
- **Issue:** #2284
- **Erstellt:** 2026-10-03

## Was gebaut wird

Trip-Kopf wie beim Ortsvergleich: Name, Region und Aktivität dort änderbar, am Handy Aktivität als ein Knopf.

## Definition of Done

Region und Aktivität sind im Kopf änderbar und bleiben nach Neuladen; die Handy-Karte liegt in drei Messfällen nicht tiefer als zuvor.

## Wie geprüft wird

Browser-Tests prüfen Speichern, Fehler, Konflikt und Kartenhöhe; Handy-Höhen außerhalb der drei Messfälle bleiben ungeprüft.

## Kritische Anmerkungen

- Knappster Fall 390x700: nur etwa 13 px Reserve, Einsparungen sind Schätzungen; Messung kann scheitern.
- Region leeren zeigt „—" auch im Ortsvergleich: ungefragte Zusatzänderung.
- Nach Nochmal-Speichern bauen sich Reiter neu auf; offener Zustand geht verloren (Tech-Entscheidung, nicht PO).

## Freigabe-Frage

Gibst du die geänderte Handy-Darstellung (Aktivitäts-Knopf, enger Kopf, Karte nicht tiefer als vorher) für beide Hubs frei?
