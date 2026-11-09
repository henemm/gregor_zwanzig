---
spec_file: docs/specs/fast/fix-2876-tg-test-trip.md
spec_sha256: 7f2d7710e7d7fb7deb3a09c4261377f3cf3c0f8881a73dd4ebfbad737bafedfa
spec_frozen_sha256: 5e7ffa55afff3e38b70f81793fb3c1bd5c3cd61e1ac8722e42a70063c3c013cb
---

# PO-Briefing: fix-2876-tg-test-trip

- **Spec:** docs/specs/fast/fix-2876-tg-test-trip.md
- **Issue:** #2876
- **Erstellt:** 2026-11-09

## Was gebaut wird

Der Telegram-Live-Test legt seinen Test-Trip selbst mit aktuellen Etappen an und scheitert nicht mehr, sobald das Datum weiterwandert.

## Definition of Done

Der Telegram-Live-Test auf Staging läuft grün, auch wenn der gesicherte Test-Trip veraltet ist, ohne dass jemand ihn von Hand auffrischt.

## Wie geprüft wird

Der Live-Test selbst läuft gegen Staging mit echter Zustellung; er beweist den Fix, ein Datumswechsel nach dem 12.11. wird nur simuliert.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
