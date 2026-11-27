---
spec_file: docs/specs/modules/fix_1987_s2_compare_kanal_anker.md
spec_sha256: b1032320cf02cb2aeaff0c5a86fe1b27fdaff03fa0675096148a844e9daeb7cf
spec_frozen_sha256: 1839f7895ca96b0387ee1bbe260172db770ee1f4f40d3f5002436619185a61e7
---

# PO-Briefing: fix-1987-compare-kanal-anker

- **Spec:** docs/specs/modules/fix_1987_s2_compare_kanal_anker.md
- **Issue:** #1987
- **Erstellt:** 2026-11-27

## Was gebaut wird

Ortsvergleich-Alarme vergleichen je Kanal gegen die letzte dort tatsächlich zugestellte Meldung, Briefing oder Alarm.

## Definition of Done

Nach einem zugestellten Alarm vergleicht der nächste Alarm dieses Kanals gegen ihn; gescheiterte Zustellungen verschieben nichts; Bestandsdaten funktionieren weiter.

## Wie geprüft wird

Automatische Tests mit echten Dateien decken alle 13 Kriterien ab, auch mit zwei Nutzern; echten Versand an Geräte weist erst die Staging-Prüfung nach.

## Kritische Anmerkungen

- Weicht bewusst vom Trip-Modell ab (eine 26-Stunden-Grenze, Briefing nicht immer vorrangig); Trip-Korrektur separat in #3481.
- Ein nicht zugestelltes Briefing kann nach einem Fehler als Vergleichsbasis dienen; dokumentierte, bewusst akzeptierte Grenze.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
