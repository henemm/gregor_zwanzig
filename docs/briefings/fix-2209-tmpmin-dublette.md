---
spec_file: docs/specs/bugfix/fix_2209_tmpmin_dublette.md
spec_sha256: 2bb349b29ae6dda609bf2d1a58b33407377d8fd0711098e3b908def9b07229ed
spec_frozen_sha256: 696ddf6a4aae94238b5734f3d60bb592e660916ec8bb166ad97852b6b353187a
---

# PO-Briefing: fix-2209-tmpmin-dublette

- **Spec:** docs/specs/bugfix/fix_2209_tmpmin_dublette.md
- **Issue:** #2209
- **Erstellt:** 2026-11-02

## Was gebaut wird

Die Trip-Mail zeigt die Temperatur nur noch einmal; die doppelte Spalte „TmpMin" verschwindet.

## Definition of Done

In einer echten Staging-Trip-Mail fehlen Spalte und Legendeneintrag „TmpMin", „Temp" bleibt, und Kälte-Alarme kommen weiterhin in allen vier Kanälen.

## Wie geprüft wird

Tests lesen Kopfzeile und Legende der gerenderten Mail sowie die Alarme vor und nach dem Fix; die Staging-Mail bestätigt es real.

## Kritische Anmerkungen

- Issue-Text war nicht abrufbar; Abgleich nur gegen das Kontext-Dokument zum Issue.
- Die zwei parallelen Zeilenbauer bleiben bestehen; Konsolidierung kommt als Folge-Issue.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
