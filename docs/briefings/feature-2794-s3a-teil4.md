---
spec_file: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md
spec_sha256: a794abf9c5d8e3c1c73b3e68339425c319774c7cc11a0d7bb2ee237398ca577d
spec_frozen_sha256: 86a4f0fcac63c5d8f8a55417e37bc2a9dcb336ee32dd2f52038adde4b3587384
---

# PO-Briefing: feature-2794-s3a-teil4

- **Spec:** docs/specs/modules/feat_2794_s3a_teil4_entfernen.md
- **Issue:** #2794
- **Erstellt:** 2026-11-12

## Was gebaut wird

Alte Wertebereiche-Oberfläche entfällt; Übersicht, Menüs und Hilfe nennen nur noch die Reiter Wetter und Zustellung.

## Definition of Done

Anlegen von Trip und Orts-Briefing liefert dieselben Wertebereiche wie vorher, keine alten Reiternamen mehr, Soll/Ist-Bild liegt vor.

## Wie geprüft wird

Automatische Tests und Anlege-Läufe mit zwei Nutzern; Optik gegen das Mockup beurteilt nur ein Prüfer per Screenshot.

## Kritische Anmerkungen

- Abweichung: Alarm-Bausteine bleiben bis zur Neugestaltung der Zustellung, das Ticket verlangte Entfernung.
- Menüeintrag „Wetter-Metriken“ heißt künftig „Wetter“, „Alarme“ bleibt; Wortlaut ist nur Vorschlag, nicht entschieden.
- Risiko: Vorbelegung der Wertebereiche beim Anlegen wird neu gebaut; dafür sind Tests vorgesehen.

## Freigabe-Frage

Dürfen die Alarm-Bausteine vorerst bleiben und heißt der Menüeintrag künftig „Wetter“ statt „Wetter-Metriken“?

## Ampel

Ampel: rot
