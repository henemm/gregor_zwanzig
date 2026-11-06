---
spec_file: docs/specs/modules/rework_2837_s1_hub_kopf.md
spec_sha256: b3062502e8e673316710220e063eb793b8872d2beaf74ca7ba25b6ea438a8469
spec_frozen_sha256: 29c75ccb6aa52a5f05701323f1f37877a12c8e6a97a6374da4d64b0c505c47a5
---

# PO-Briefing: rework-2837-hub-kopf-anlege-rahmen

- **Spec:** docs/specs/modules/rework_2837_s1_hub_kopf.md
- **Issue:** #2837
- **Erstellt:** 2026-11-06

## Was gebaut wird

Trip- und Ortsvergleich-Detailseiten bekommen denselben Kopf: gleiche Senden-Lage und -Farbe, Pfad, Status, Menü-Symbol und Reiter-Zähler.

## Definition of Done

Trip und Ortsvergleich zeigen bei 1440 und 390 Pixeln Senden schwarz an gleicher Stelle, Status als Schild, neutrale Zähler; Screenshot-Paar liegt im Epic.

## Wie geprüft wird

Automatische Browser-Tests beider Seiten bei Desktop und Handy prüfen jede Anforderung; die Gleichheit im Screenshot-Vergleich und die Doku bleiben Handprüfung.

## Kritische Anmerkungen

- Anlege-Rahmen (Neu-Anlegen-Seiten) fehlt, obwohl im Ticket gefordert; Ticket bleibt bis zur Folge-Scheibe offen.
- Senden wird beim Trip von orange auf schwarz geändert; das Ticket verlangte nur „gleich".

## Freigabe-Frage

Akzeptieren Sie, dass jetzt nur der Hub-Kopf kommt und der Anlege-Rahmen erst in einer Folge-Scheibe?

## Ampel

Ampel: rot
