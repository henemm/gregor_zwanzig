---
spec_file: docs/specs/modules/sms_daily_limit.md
spec_sha256: 3cc13430e2ce699006b793e9628d52675d4544e14494c7b173a7275a588690f4
---

# PO-Briefing: feat-2153-s4-sms-tageslimit

- **Spec:** docs/specs/modules/sms_daily_limit.md
- **Issue:** #2412 (Sammel-Issue #2153, Epic #2138)
- **Erstellt:** 2026-09-24

## Was gebaut wird

Technische Sperre begrenzt tägliche SMS- und Premium-SMS-Mengen je Nutzer, damit Kosten nicht unbegrenzt steigen.

## Definition of Done

Ab täglich 10 SMS bzw. 15 Premium-SMS blockiert das System weitere Sendungen; E-Mail/Telegram laufen weiter.

## Wie geprüft wird

Tests prüfen Grenzwerte, Alarm-Reserve, Tageswechsel und Nutzertrennung; echte Anbieterkosten misst kein Test.

## Kritische Anmerkungen

- Die verlangte Zähler-Anzeige im Konto fehlt, Issue bleibt nach dieser Auslieferung offen.
- Eine ungeprüfte Reserve senkt dein Tageslimit faktisch: Standard-SMS effektiv 8 statt 10, Premium-SMS 12 statt 15.
- Die Zählweise weicht technisch vom Plan ab; normal gleich, in seltenen Störfällen zählt eine SMS falsch.

## Freigabe-Frage

Reicht dir die Sperre ohne sichtbaren Konto-Zähler schon, oder soll die Anzeige Teil dieser Freigabe sein?
