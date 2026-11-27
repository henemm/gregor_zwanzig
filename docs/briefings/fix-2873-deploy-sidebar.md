---
spec_file: docs/specs/modules/workflow_deploy_status.md
spec_sha256: bac2219d5f4e91a203c77a08efe3ee16c038ec20b1fd4c4f06e605e72f24ad2f
spec_frozen_sha256: 047925156466718d64154a8590ed55d8f0004971fb75376733eb294b67ddb24c
---

# PO-Briefing: fix-2873-deploy-sidebar

- **Spec:** docs/specs/modules/workflow_deploy_status.md
- **Issue:** #2873
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Seitenleiste zeigt den Prod-Deploy eindeutig als offen, läuft, fertig oder fehlgeschlagen und schlägt ihn nur vor, solange offen.

## Definition of Done

Nach Phase 8 zeigt die Leiste nie „nicht eingerichtet“, sondern nacheinander offen, läuft, fertig oder fehlgeschlagen; Tests grün, Issue geschlossen.

## Wie geprüft wird

Echte Aufrufe des Werkzeugs prüfen Anzeige und Endzustand; die Anleitungsschritte werden nur per Textsuche geprüft, nicht im echten Deploy durchlaufen.

## Kritische Anmerkungen

- Zusätzlich zum Ticket wird auch der Auslieferungsstatus (Merge) gesetzt; sonst bliebe die Deploy-Zeile dauerhaft grau. Technisch nötig.
- Tests werden ohne installiertes Plugin übersprungen, etwa in CI; dort fehlt dann der Nachweis.
- Zwischenzustand heisst „▶ Deploy (offen)“ statt „○ Deploy“ wie im Ticket; geringfügige Wortlautabweichung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
