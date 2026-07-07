# Spec: Issue #976 — Telegram HTML-Truncation überschreitet max_len nicht

created: 2026-07-07

## Problem
`_truncate_html` (src/output/channels/telegram.py) kürzt HTML-Nachrichten bei parse_mode=HTML tag-schonend,
kann aber `max_len` (4096) um wenige Zeichen überschreiten, wenn kleine Tags dicht an der Grenze liegen
(reproduziert: bis 4101). Telegram lehnt Nachrichten >4096 mit ok:false ab — derselbe Fehlermodus, den der
Fix beseitigen soll.

## Acceptance Criteria

**AC-1:** Given eine HTML-Nachricht beliebiger Tag-Dichte, die länger als `max_len` ist,
When `_truncate_html(message, max_len)` sie kürzt,
Then ist `len(ergebnis) <= max_len` für JEDEN Fall (harte Invariante, auch bei dicht gepackten kleinen Tags).

**AC-2:** Given eine gekürzte HTML-Nachricht,
When das Ergebnis geprüft wird,
Then sind alle öffnenden Tags durch schließende ausgeglichen (keine mittig abgeschnittenen oder unbalancierten Tags).

**AC-3:** Given eine reine Plaintext-Nachricht oder eine HTML-Nachricht <= `max_len`,
When `_truncate_html` angewendet wird,
Then bleibt das bisherige Verhalten unverändert (Plaintext hart auf max_len, Kurznachricht unverändert).

**AC-4:** Given eine echte HTML-Nachricht > 4096 Zeichen mit mehreren Tags nahe der Grenze,
When sie über den echten `TelegramOutput.send(parse_mode="HTML")` an den Staging-Bot gesendet wird,
Then nimmt die echte Telegram-API die gekürzte Nachricht an (ok:true / gültige message_id) — kein Mock.

## Known Limitations
- AC-4 läuft nur mit `GZ_TELEGRAM_LIVE=1` (Opt-in, Staging-Bot), sonst Skip — konform zu #1014.

## Out of Scope
- Keine Änderung an der Nachrichten-Komposition/Formatierung selbst, nur an der Kürzungs-Invariante.
