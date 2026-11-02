---
spec_file: docs/specs/modules/fix_1721_nachtausgabe.md
spec_sha256: c18370aa42e1436e7c9275f1473535c75148fa69f8f67d0bbbc9b7995bd156ae
spec_frozen_sha256: 18cfa2e0aa0a108f5b39818f42316f4a2960cfab86bca33ffdafe9718ec61468
---

# PO-Briefing: fix-1721-nachtausgabe

- **Spec:** docs/specs/modules/fix_1721_nachtausgabe.md
- **Issue:** #1721
- **Erstellt:** 2026-11-02

## Was gebaut wird

Im Wetter-Metriken-Reiter eines Trips gibt es einen Schalter, mit dem die Nacht-Stundentabelle der Mail abgeschaltet werden kann.

## Definition of Done

Der Schalter erscheint nur im Trip, bleibt nach Speichern und Neuladen erhalten, und die zugestellte Mail zeigt die Nachttabelle genau bei „an".

## Wie geprüft wird

Browser-Klickpfad mit zwei Nutzern und zugestellte Staging-Mails belegen Schalter, Nacht-Tiefstwert, Ausblick-Köpfe und die Kürzel-Erklärung „FN"; Code-Änderung an Mail-Aufbau entfällt.

## Kritische Anmerkungen

- Ausblick-Spalte „N" und Kürzel „FN" werden nicht gebaut, nur als bereits behoben nachgewiesen; Ticketwortlaut konnte ich nicht einsehen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
