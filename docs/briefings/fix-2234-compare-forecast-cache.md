---
spec_file: docs/specs/modules/fix_2234_compare_forecast_cache.md
spec_sha256: 14f029f3a2ea9954192111b2cad50d8f7207e59b018500c7dc02e8ed4e6edaa4
spec_frozen_sha256: 5966042c5f395a59da05a198affe96f9e80b1de28ddadff17d0aaa1a0ea648f3
---

# PO-Briefing: fix-2234-compare-forecast-cache

- **Spec:** docs/specs/modules/fix_2234_compare_forecast_cache.md
- **Issue:** #2234
- **Erstellt:** 2026-10-31

## Was gebaut wird

Eine zweite Vorschau, der Versand danach oder ein Doppelklick im Ortsvergleich holt keine Wetterdaten mehr neu ab.

## Definition of Done

Innerhalb von zehn Minuten löst dieselbe Vergleichs-Vorschau oder der anschließende Versand null Wetter-Abrufe aus, bei unveränderten Werten und Mails.

## Wie geprüft wird

Netzfreie Tests mit gezähltem Fake-Anbieter belegen alle acht Kriterien; unveränderte Werte des neuen Zeitfensters werden zusätzlich live auf Staging verglichen.

## Kritische Anmerkungen

- Die erste (kalte) Vorschau bleibt langsam, ca. 27 Sekunden bei drei Orten; nur Wiederholungen werden schneller.
- Vorschau und Versand verbrauchen künftig Tagesbudget je Abruf, werden aber nie gedrosselt.
- Zusatz: Leere Wetterreihen werden auch im Trip-Pfad nicht mehr zwischengespeichert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
