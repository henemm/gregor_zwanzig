---
spec_file: docs/specs/modules/feat_3198_s4b3_compare_anlegen_ohne_profil.md
spec_sha256: 4c69afafaa800eeb64d8592c9efc9de5ab315935dc3642691aa4743c34466417
spec_frozen_sha256: aa6a9795e31b646980df925b6b055650cdff10cc427d13315a8d848c41427bae
---

# PO-Briefing: feature-3198-compare-anlegen-ohne-profil

- **Spec:** docs/specs/modules/feat_3198_s4b3_compare_anlegen_ohne_profil.md
- **Issue:** #3198
- **Erstellt:** 2026-11-21

## Was gebaut wird

Beim Anlegen eines Orts-Vergleichs entfällt die Profil-Auswahl; allein die Vorlage im Reiter Wetter zählt.

## Definition of Done

Am Computer und Handy gibt es beim Anlegen keine Profil-Kacheln mehr, und ein ohne Wetter-Reiter angelegter Vergleich zeigt im Hub „Allgemein“.

## Wie geprüft wird

Automatische Tests und Staging-Abläufe belegen jede Anforderung, auch mit zwei Nutzern; Orts-Profile bleiben unverändert wählbar.

## Kritische Anmerkungen

- Zusatz: Neue Vergleiche starten ohne Wetter-Besuch mit „Allgemein“ statt bisher „Wandern“ (behebt Widerspruch zur Anzeige).
- Wertebereiche sind beim Anlegen immer mit Allgemein-Werten belegt, egal welche Vorlage gewählt wird.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
