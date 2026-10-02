---
spec_file: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md
spec_sha256: 7862889027b8879185b3f13a7bb1797f185161b470c37227a077e18ecf20ccf1
---

# PO-Briefing: fix-2229-premium-sms-kanallisten-b

- **Spec:** docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md
- **Issue:** #2229
- **Erstellt:** 2026-10-02

## Was gebaut wird

Ortsvergleich nennt Premium-SMS als Kanal in Kachel, Übersicht und Sendedialog; die Vorschau erklärt, dass sie den SMS-Text sendet.

## Definition of Done

Eingeschaltete Premium-SMS steht auf Kachel und Übersicht, im Sendedialog nur wenn zustellbar, und die Vorschau zeigt den Hinweis.

## Wie geprüft wird

Tests prüfen Anzeigetexte und Quelltext-Suche; ob der Vorschau-Hinweis wirklich erscheint, prüft nur Staging manuell.

## Kritische Anmerkungen

- Ticket nannte den Alarm-Editor; der ist entfernt. Spec repariert stattdessen drei andere Anzeigen — Ticket-Titel passt nicht mehr.
- Kachel zeigt gesperrte Premium-SMS, Sendedialog nicht — bewusst, kann Nutzer aber verwirren.
- Quelltext-Suche erkennt nur exakt geschriebene Dreierlisten.

## Freigabe-Frage

Soll Premium-SMS im Ortsvergleich bei Einschaltung angezeigt werden, im Sendedialog aber nur, wenn sie zustellbar ist?
