---
spec_file: docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md
spec_sha256: f122a8bf2b4cc7c5ae98b2321b89e53828b1f57555d1549bffc9173c8e270e6d
spec_frozen_sha256: cf1b44ef58510a62ce5c9905d52ca2a2543dc38abbd27759123663c46525fa4b
---

# PO-Briefing: b6b2-3276-altfelder-frontend

- **Spec:** docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md
- **Issue:** #3276
- **Erstellt:** 2026-11-23

## Was gebaut wird

Beim Anlegen und Speichern eines Ortsvergleichs gilt nur noch die Tabelle „Was steht wo“; die alten Einstellflächen verschwinden.

## Definition of Done

Ortsvergleich lässt sich anlegen und speichern, Stundenverlauf und Ausblick sind nur noch in der Tabelle einstellbar, Mails kommen unverändert an.

## Wie geprüft wird

Tests prüfen gesendete Daten, fehlende alte Flächen, Nutzertrennung und Mail-Ausgabe in vier Kanälen; Trip-Verhalten wird als unverändert abgesichert.

## Kritische Anmerkungen

- Nur der Ortsvergleich ist erledigt; Trip, Ausblick-Schalter und Typen folgen in den Tickets 3297 und 3298 (laut Ticket-Kommentar so zerlegt).
- Alte Werte bleiben in bestehenden Daten liegen, wirkungslos; Aufräumen folgt mit Ticket 3277.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
