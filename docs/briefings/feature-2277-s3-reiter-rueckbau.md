---
spec_file: docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md
spec_sha256: 598a94ae7ed8c04c854e87c545db7fb32a640dc29e19be6e5d466d0b5d665230
---

# PO-Briefing: feature-2277-s3-reiter-rueckbau

- **Spec:** docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md
- **Issue:** #2277
- **Erstellt:** 2026-10-01

## Was gebaut wird

Beim Anlegen eines Trips heißen und ordnen sich die letzten Reiter wie beim Ortsvergleich, alter Alarm-Code verschwindet.

## Definition of Done

Die Trip-Anlegeseite zeigt Wetter-Metriken, Wertebereiche, Alarme, Versand wie der Ortsvergleich, und Anlegen wird erst nach dem Versand-Besuch aktiv.

## Wie geprüft wird

Automatische Tests und Durchklicken auf Staging belegen Reiter, Sperren und Speichern; ob gelöschte Alt-Tests noch Wichtiges bewachten, bleibt Stichprobe.

## Kritische Anmerkungen

- Anfrage nur teilweise erfüllt: Vergleichs-Sperrlogik und Mail-Inhalt-Baustein bleiben bis S4/S5; Issue bleibt offen.
- Verhaltensänderung: Trip-Anlegen verlangt künftig Besuch von Alarme und Versand, bisher nur Zeitplan.
- Wetter-Metriken-Sperrhinweis bleibt bewusst verschieden; „identisch" ist enger ausgelegt als verlangt.

## Freigabe-Frage

Gibst du frei, dass Anlegen künftig Alarme und Versand voraussetzt und der Rückbau erst in S4/S5 endet?
