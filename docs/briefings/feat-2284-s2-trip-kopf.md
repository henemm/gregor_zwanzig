---
spec_file: /home/hem/gregor_zwanzig/.claude/worktrees/peaceful-conjuring-hartmanis/docs/specs/modules/feat_2284_s2_trip_kopf.md
spec_sha256: 2f8b96a49b8086ea442eabcac35e83d864f18f3ebe63d00014371cbfb37964eb
---

# PO-Briefing: feat-2284-s2-trip-kopf

- **Spec:** docs/specs/modules/feat_2284_s2_trip_kopf.md (v1.3)
- **Issue:** #2284
- **Erstellt:** 2026-10-04

## Was gebaut wird

Trip-Kopf erlaubt Name, Region, Aktivität direkt zu ändern; Speicher-Hinweis sieht in Trip und Ortsvergleich gleich aus.

## Definition of Done

Region und Aktivität sind im Trip-Kopf änderbar und bleiben nach Neuladen; Handy-Etappen-Liste rutscht nicht tiefer.

## Wie geprüft wird

Browser- und Server-Tests prüfen Speichern, Fehlerfälle, Fremdzugriff und Handy-Maße; echte Daten und optische Güte prüfen sie nicht.

## Kritische Anmerkungen

- Auf dem Handy liegt die Etappen-Liste aktuell 5 px zu tief; die Straffung fehlt noch.
- Nicht verlangt: Vergleich-Titel wird mobil von 16 auf 20 px größer; Test-Briefing wandert mobil in die Pausieren-Zeile.
- Bewusst nicht enthalten: Speichern-Knopf im Versand-Reiter entfernen (Folgescheibe S3).

## Freigabe-Frage

Gibst du den Umbau frei, inklusive größerem Vergleich-Titel und verschobenem Test-Briefing auf dem Handy?
