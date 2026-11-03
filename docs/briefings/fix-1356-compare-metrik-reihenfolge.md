---
spec_file: docs/specs/modules/compare_metric_default_order_ssot.md
spec_sha256: ef9f830220b5c4718f057a9f3fb80504295891804d31fbcf12a3927609679f8e
spec_frozen_sha256: 34739306aa3f1c81eb265f95babe5b4e8b13c183b5dda5b129639a769d6d79c5
---

# PO-Briefing: fix-1356-compare-metrik-reihenfolge

- **Spec:** docs/specs/modules/compare_metric_default_order_ssot.md
- **Issue:** #1356
- **Erstellt:** 2026-11-03

## Was gebaut wird

Die Orts-Vergleichs-Mail zeigt ihre Messwerte im Textteil in derselben Reihenfolge wie im HTML-Teil, wenn keine eigene Auswahl gespeichert ist.

## Definition of Done

Eine echt zugestellte Vergleichs-Mail eines Altbestands-Vergleichs zeigt Text- und HTML-Teil mit identischer Zeilenreihenfolge, und der Prüflauf auf Staging meldet Erfolg.

## Wie geprüft wird

Tests vergleichen beide Reihenfolgen, schützen Telegram, SMS und gespeicherte Auswahlen vor Änderungen; die echte Zustellung wird nur live auf Staging nachgewiesen.

## Kritische Anmerkungen

- Die Textreihenfolge ändert sich für Altbestand einmalig und bewusst, entgegen der früheren Zusage "nichts ändert sich ungefragt".
- Telegram, SMS und Premium-SMS bleiben unverändert; das Ticket verlangt dort nichts, die Analyse nahm Änderungen an.
- Der Ticket-Verschärfer bei gespeicherter Auswahl ist überholt; der Text geht nur an Test-Empfänger, die ihn annehmen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
