---
spec_file: docs/specs/modules/feat_1441_s2_entwarnung.md
spec_sha256: ac4d4a801080192fc8e92fa7d8a5ab55805c3d5ed7b6c820ef562c2ee9213fcf
---

# PO-Briefing: feat-1441-s2-entwarnung

- **Spec:** docs/specs/modules/feat_1441_s2_entwarnung.md
- **Issue:** #1441
- **Erstellt:** 2026-10-15

## Was gebaut wird

Sinkt oder endet eine amtliche Warnung, erhalten Nutzer eine Entwarnung über alle vier Kanäle bei Trip und Ortsvergleich.

## Definition of Done

Eine abgesenkte oder vorzeitig beendete Warnung erzeugt genau eine Entwarnung pro Nutzer; Ausfall, Neuausgabe oder bereits informierendes Briefing erzeugen keine.

## Wie geprüft wird

Automatische Tests prüfen alle Fälle in beiden Flächen und vier Kanälen; echte Zustellung wird erst auf Staging mit einer Testmail geprüft.

## Kritische Anmerkungen

- Neu: Zeigte das Briefing die Warnung zwischendurch noch, kommt „beendet" erst einen Alarm-Lauf später.
- Neu: Briefing-Regel gilt auch für Ortsvergleich; Umfang wächst auf rund 705 statt 665 Zeilen.
- Planmäßig auslaufende Warnungen und Altbestand ohne Quelle melden keine Entwarnung; Ersteres ist Tech-Lead-Entscheid, nicht Ihrer.

## Freigabe-Frage

Geben Sie die überarbeitete Spec mit diesen Änderungen frei?
