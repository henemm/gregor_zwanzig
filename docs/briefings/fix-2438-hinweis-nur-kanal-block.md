---
spec_file: docs/specs/modules/fix_2438_hinweis_nur_kanal_block.md
spec_sha256: 314da911987176340775a72fd077e722c8ae5b9e8a2c3aa5a84e6a248b3acb6b
spec_frozen_sha256: 8be698a883ee517f30eb42e9dd5b2f1a61970e6a3ac63d53084512358c5bc06b
---

# PO-Briefing: fix-2438-hinweis-nur-kanal-block

- **Spec:** docs/specs/modules/fix_2438_hinweis_nur_kanal_block.md
- **Issue:** #2438
- **Erstellt:** 2026-10-20

## Was gebaut wird

Der Abwahl-Hinweis erscheint nur noch in den Kanal-Reitern von Trip und Ortsvergleich, nicht mehr im Ausblick-Block.

## Definition of Done

Auf Staging zeigt jeder Kanal-Reiter beider Editoren genau einen Hinweis, der Ausblick keinen, und die Staging-Prüfungen sind wieder grün.

## Wie geprüft wird

Render-Tests prüfen den Baustein; ob beide Kanal-Reiter den Hinweis wirklich erhalten, beweisen nur die Staging-Browsertests.

## Kritische Anmerkungen

- Verdrahtung der beiden Kanal-Reiter ist nur durch Staging-Tests belegt, nicht durch die Standard-CI-Prüfung.
- Zusatz: Bestehende Staging-Tests werden umgebaut (enger gesucht); nötig, sonst bleibt Staging rot.

## Freigabe-Frage

Soll der Hinweis wie beschrieben nur in den Kanal-Reitern stehen und der Ausblick-Block ohne Hinweis bleiben?
