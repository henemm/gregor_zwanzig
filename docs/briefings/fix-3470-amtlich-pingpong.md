---
spec_file: docs/specs/modules/fix_3470_amtlich_nachbarperioden.md
spec_sha256: b0332a6746159d07aac35984965d8858ec76bddd9b296e50ffa977cb0332a5a5
spec_frozen_sha256: db80f2f1dce3849d388692201c3e5af66ab812aaef796d69afe5a1ffe841054a
---

# PO-Briefing: fix-3470-amtlich-pingpong

- **Spec:** docs/specs/modules/fix_3470_amtlich_nachbarperioden.md
- **Issue:** #3470
- **Erstellt:** 2026-11-27

## Was gebaut wird

Eine amtliche Warnung wird dem Nutzer nur einmal gemeldet, auch wenn der Wetterdienst sie in zwei aneinandergrenzenden Zeiträumen liefert.

## Definition of Done

Bei zwei aneinandergrenzenden Warnzeiträumen kommt über mehrere Prüfläufe nur eine Meldung, danach eine Entwarnung; echte Verschärfungen und Vorverlegungen werden weiterhin gemeldet.

## Wie geprüft wird

Automatische Mehrlauf-Tests für Trip und Ortsvergleich in beiden Feed-Reihenfolgen; der echte Meteoalarm-Feed wird nur simuliert.

## Kritische Anmerkungen

- Zusatz zum Ticket: Entwarnungen werden ebenfalls entdoppelt, damit es je Warnung nur eine Entwarnung gibt.
- Erstauftritt mit beiden Zeiträumen im selben Lauf liefert weiterhin eine Meldung mit beiden Zeiträumen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
