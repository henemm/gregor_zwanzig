---
spec_file: docs/specs/modules/feat_2327_gps_etappenfortschritt.md
spec_sha256: 19437f81edbb5f582e18383b284e7a6359799834de0b24793e7fe63d4e973691
spec_frozen_sha256: e892c0ee73e254e86ed05d4c605e0e15386a4e6f94396dc64f8cf4f5c60f73ca
---

# PO-Briefing: feat-2327-gps-etappenfortschritt

- **Spec:** docs/specs/modules/feat_2327_gps_etappenfortschritt.md
- **Issue:** #2327
- **Erstellt:** 2026-10-26

## Was gebaut wird

Meldet eine Garmin-Nachricht Koordinaten nahe der Route, rechnen Wetter-Prognosen und Alarme in allen vier Kanälen ab dieser Position.

## Definition of Done

Eine Nachricht mit Koordinaten höchstens 100 m neben dem Trip verschiebt die Prognosen; weiter entfernte Koordinaten ändern nichts.

## Wie geprüft wird

Tests mit den zwei echten Nachrichten prüfen 99/101-Meter-Grenze, Ablauf und Nutzertrennung, nicht aber echte Mail-Zustellung.

## Kritische Anmerkungen

- Gültigkeitsdauer, stille Positions-Nachrichten und Mehrdeutigkeit hat der Tech Lead festgelegt, nicht Sie.
- Etappen ohne GPX-Datei bleiben wirkungslos; dort wird kein Fix übernommen.
- Gleiches Verhalten in allen vier Kanälen ist nur indirekt getestet.

## Freigabe-Frage

Soll die GPS-Position die Planposition ersetzen, mit den genannten Festlegungen?
