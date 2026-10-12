---
spec_file: docs/specs/modules/fix_1369_inbound_telegram_poll_entfernen.md
spec_sha256: 208cf67b4e566cc447b4f71bf5edc994e4754e5898da407b783090b78b83f3ea
---

# PO-Briefing: fix-1369-inbound-telegram-poll-entfernen

- **Spec:** docs/specs/modules/fix_1369_inbound_telegram_poll_entfernen.md
- **Issue:** #1369
- **Erstellt:** 2026-10-12

## Was gebaut wird

Der ungenutzte Telegram-Abfragepfad, der den echten Bot-Schlüssel an den Schutzmechanismen vorbeischickt, wird ersatzlos entfernt.

## Definition of Done

Der Aufruf des alten Telegram-Abfrage-Endpunkts liefert "nicht gefunden", Telegram-Befehle über den Webhook und der E-Mail-Abruf funktionieren unverändert.

## Wie geprüft wird

Neue Tests belegen das Fehlen des Pfads; Webhook und E-Mail-Abruf werden nur durch bestehende Tests abgesichert, nicht durch neue.

## Kritische Anmerkungen

- Bewusste Abweichung: Der früher beschlossene Notfall-Fallback entfällt; Wiedereinführung braucht eine neue Spec.
- AC-3 und AC-4 (Webhook, E-Mail unverändert) haben keinen neuen Test, nur Verweis auf bestehende.

## Freigabe-Frage

Darf der Telegram-Abfragepfad endgültig ohne Notfall-Fallback entfernt werden?
