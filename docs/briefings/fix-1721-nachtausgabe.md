---
spec_file: docs/specs/modules/fix_1721_nachtausgabe.md
spec_sha256: 4cfc7a21bf2b269adcb513a7124a1f53be2af2d985a184e4e798e802bd9622eb
spec_frozen_sha256: 256d49adbc7dfeea2715e3c7ef33f02510810d711cc03cdfdf5b114f7e81c473
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

Browser-Klickpfad mit zwei Nutzern und zugestellte Staging-Mails belegen Schalter, Nacht-Tiefstwert, Ausblick-Köpfe und die Kürzel-Erklärung „FN"; Mail-Aufbau selbst bleibt unverändert.

## Kritische Anmerkungen

- Ausblick-Spalte „N" und Kürzel „FN" werden nicht gebaut, sondern als bereits behoben nur nachgewiesen (Browserlauf, zugestellte Mail).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
