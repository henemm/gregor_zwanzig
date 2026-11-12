---
spec_file: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md
spec_sha256: bf9ec1ac9cfa253453be092fcc698934e754e32f9c089a65c6fcfa3700806c13
spec_frozen_sha256: bff5e8339de7e40a14db3399d33dc8782908354c9b7a326d287002996cf4c276
---

# PO-Briefing: feature-2794-s3a-teil4b

- **Spec:** docs/specs/modules/feat_2794_s3a_teil4_entfernen.md
- **Issue:** #2794
- **Erstellt:** 2026-11-12

## Was gebaut wird

Übersicht, Listen-Menüs, Hilfe und Texte nennen nur noch die neuen Reiter Wetter und Zustellung, nicht mehr die alten Namen.

## Definition of Done

Trip-Übersicht zeigt den Alarm-ab-Zähler, Menü „Wetter“ und „Alarme“ führen in die richtigen Reiter, kein Text nennt alte Reiter, Soll/Ist-Bild liegt vor.

## Wie geprüft wird

Automatische Tests prüfen Übersicht, Texte in Deutsch und Englisch sowie alte Reiternamen; Klicktests auf Staging prüfen die Sprünge, das Mockup vergleicht ein Prüfer-Agent.

## Kritische Anmerkungen

- Mockup-Abgleich gilt nur für Änderungen dieses Schritts; Abweichungen der Reiter Wetter und Zustellung gehen an #2913.
- Menü-Wortlaut „Wetter“ und „Alarme“ ist ein Vorschlag, den deine Freigabe mitbestätigt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
