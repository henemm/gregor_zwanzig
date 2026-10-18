---
spec_file: docs/specs/modules/feat_2278_aktionsmodell.md
spec_sha256: 8162027b5be5efbcb2e1510dfb0cba4b4bf2b54e5cb1b0b7179eddf7bb67717d
spec_frozen_sha256: 062a8ea0f0edfa68ac92a9bdb8562252cdbddf8bd376e6fedc030e9116bf3b0f
---

# PO-Briefing: feat-2278-aktionsmodell

- **Spec:** docs/specs/modules/feat_2278_aktionsmodell.md
- **Issue:** #2278
- **Erstellt:** 2026-10-17

## Was gebaut wird

Trip und Ortsvergleich bieten in Liste, Detailseite und Handy dieselben Aktionen, gleich beschriftet und wirksam.

## Definition of Done

Jede Aktion ist bei beiden Arten auf Desktop und Handy erreichbar, wirkt, und „Senden" nennt das echte Ziel.

## Wie geprüft wird

Tabellen- und Dialogtests plus Durchklick beider Arten prüfen ausgelöste Anfragen, nicht die tatsächliche Zustellung.

## Kritische Anmerkungen

- Dialog „Alert-Konfiguration" entfällt; alte Änderungs-Schwellen sind nirgends mehr einstellbar, wirken aber weiter.
- Archivierte Trips verschwinden aus der Trip-Liste, nur noch im Archiv auffindbar.
- Ortsvergleich-Senden fragt künftig nach und sperrt ohne Kanal; frühere Entscheidung „Handy-Liste nur Link" wird aufgehoben.

## Freigabe-Frage

Gibst du den Umbau frei, einschließlich Wegfall der Alert-Konfiguration und Ausblenden archivierter Trips in der Liste?
