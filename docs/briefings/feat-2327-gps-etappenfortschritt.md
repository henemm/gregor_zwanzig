---
spec_file: docs/specs/modules/feat_2327_gps_etappenfortschritt.md
spec_sha256: 0e1d80857757e1eaeeb842172d95204495e6c184458e407c3aad15a671ce4a2a
spec_frozen_sha256: 420b5ab7af266416b011fe1f8d4cf672b1c870669f2c2a7aa24bfa058c1bebca
---

# PO-Briefing: feat-2327-gps-etappenfortschritt

- **Spec:** docs/specs/modules/feat_2327_gps_etappenfortschritt.md
- **Issue:** #2327
- **Erstellt:** 2026-10-26

## Was gebaut wird

Meldet eine Garmin-Nachricht Koordinaten auf der Trip-Route, rechnen Prognosen und Alarme in allen vier Kanälen von dort weiter.

## Definition of Done

Koordinaten höchstens 100 m neben der heutigen Etappe verschieben Prognosen und Alarme; weiter entfernte Koordinaten ändern nichts.

## Wie geprüft wird

Tests mit den zwei echten Nachrichten prüfen 100-Meter-Grenze, Weiterwandern, Ablauf und Nutzertrennung, nicht aber echte Zustellung.

## Kritische Anmerkungen

- Issue #2327 war nicht lesbar; Deckung der Anfrage ungeprüft.
- Position wandert nach Plan-Tempo weiter; Gültigkeit, stille Nachrichten, Mehrdeutigkeit hat der Tech Lead festgelegt.
- Etappen ohne GPX bleiben wirkungslos; Kanalgleichheit nur indirekt getestet.

## Freigabe-Frage

Soll die gemeldete Position die Planposition ersetzen und ab Meldezeit nach Plan-Tempo weiterwandern, mit den genannten Festlegungen?
