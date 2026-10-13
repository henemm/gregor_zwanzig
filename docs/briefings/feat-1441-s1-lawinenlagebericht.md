---
spec_file: docs/specs/modules/avalanche_report_bulletin.md
spec_sha256: efa579493a8bfaf5cc6cedbbe2d7fdaf44bfdb2d03f0dd105b8895843c21ccbd
---

# PO-Briefing: feat-1441-s1-lawinenlagebericht

- **Spec:** docs/specs/modules/avalanche_report_bulletin.md
- **Issue:** #1441
- **Erstellt:** 2026-10-13

## Was gebaut wird

Der amtliche Lawinen-Lagebericht (Stufe 1–5, Höhe, Problem) erscheint für Tirol, Südtirol, Trentino und Kärnten in allen vier Kanälen.

## Definition of Done

Ein Trip-Punkt in diesen Regionen zeigt in Mail, Telegram, SMS und Premium-SMS die Originalstufe samt Quelle; Stufe 5 erscheint nie als 4.

## Wie geprüft wird

Tests nutzen aufgezeichnete Winter-Berichte durch die echten Kanäle; eine echte aktuelle Stufe lässt sich erst ab Saisonstart live nachweisen.

## Kritische Anmerkungen

- Abweichung von Ihrer Vorgabe: Der alte Lawinen-Zweig der SMS-Metrik wird entfernt statt genutzt; die Stufe kommt über den Warnblock.
- Alte Lawinen-Datenstruktur wird bewusst nicht genutzt, entgegen Ihrem Ticket-Kommentar; ein neues Architektur-Dokument wird angelegt.
- Salzburg, Bayern und übrige Länder erhalten vorerst keinen Lagebericht; Stufe 1 erscheint in der SMS nicht.

## Freigabe-Frage

Geben Sie die Spec frei, obwohl die SMS-Stufe anders als von Ihnen vorgegeben läuft und nur vier Regionen abgedeckt sind?
