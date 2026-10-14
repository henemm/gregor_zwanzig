---
spec_file: docs/specs/modules/avalanche_report_bulletin.md
spec_sha256: 5532c9fc3b7cdc16d29888c4a26520ef8bf362b06957ec1bd705b8322f26d6a6
---

# PO-Briefing: feat-1441-s1-lawinenlagebericht

- **Spec:** docs/specs/modules/avalanche_report_bulletin.md
- **Issue:** #1441
- **Erstellt:** 2026-10-14

## Das ist neu gegenüber der letzten Freigabe

Quellenname und Link stehen jetzt auch in der eigenständigen Warnungs-Mail; Telegram-Kurzstil bleibt wie SMS ohne Link.

## Was gebaut wird

Der amtliche Lawinen-Lagebericht (Stufe 1–5) erscheint für Trips in Tirol, Südtirol, Trentino und Kärnten in allen vier Kanälen.

## Definition of Done

Trip-Punkte dort zeigen in Mail, Telegram, SMS und Premium-SMS die Originalstufe; Stufe 5 erscheint nie als 4.

## Wie geprüft wird

Aufgezeichnete Winter-Berichte laufen durch die echten Kanäle; Live-Stufe erst ab Saisonstart prüfbar.

## Kritische Anmerkungen

- Entwarnung bei sinkender Stufe fehlt bis S2.
- Nur vier Regionen.

## Freigabe-Frage

Geben Sie die Spec mit Link-Pflicht in der Warnungs-Mail frei?
