# Context: feat-1349-telegram-unavailable (Scheibe 2 von #1349)

## Request Summary
Das Telegram-Trip-Briefing ("rich", `render_telegram_bubbles`) soll — analog zur E-Mail
(#1348) und SMS (Scheibe 1) — eine Hinweiszeile "amtliche Warnungen aktuell nicht abrufbar"
zeigen, wenn für mindestens ein Segment `official_alerts_unavailable=True` gesetzt ist.
Kein Zeichen-Limit → volle Hinweiszeile (kein Kürzel). Geteilten Baustein aus
`unavailable_hint.py` WIEDERVERWENDEN.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/narrow.py` | `render_telegram_bubbles()` (Zeile 423ff); Kopf-Bubble bei 470, Warn-Bubble `_official_alert_bubble` bei 474 — Einhängepunkt für den Hinweis |
| `src/output/renderers/email/unavailable_hint.py` | Geteilte Bausteine `any_official_alerts_unavailable`, `render_official_alerts_unavailable_plain(ascii_safe=False)` (⚠️-Prefix) |
| `src/app/models.py:426` | `SegmentWeatherData.official_alerts_unavailable` — Quelle |

## Existing Patterns
- Kurzform-Telegram sendet `report.sms_text` direkt (notification_service.py:306ff) → erbt den `W?`-Marker automatisch aus Scheibe 1; hier NICHTS zu tun.
- Der Warn-Bubble `_official_alert_bubble` sitzt „direkt nach dem Kopf, weil sicherheitsrelevant" (narrow.py:472-476). Der Nicht-abrufbar-Hinweis ist ebenso sicherheitsrelevant und gehört an dieselbe Stelle.
- `render_official_alerts_unavailable_plain(ascii_safe=False)` liefert `⚠️ Amtliche Warnungen aktuell nicht abrufbar — bitte selbst pruefen.` — Telegram kann Emoji, kein Char-Limit.

## Analysis

### Type
Feature (Kanal-Ausweitung).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/narrow.py` | MODIFY (~+6 LoC) | Nach dem Kopf-Bubble, wenn `any_official_alerts_unavailable(segments)`: eigenen `TelegramBubble` mit `render_official_alerts_unavailable_plain(ascii_safe=False)` einfügen (via `_esc`) |
| `tests/tdd/test_telegram_trip_unavailable_hint.py` | CREATE (~+30 LoC) | Kern-Test: Flag gesetzt → Hinweis in einer Bubble; Flag nicht gesetzt → keine Hinweis-Bubble; echter Fail-soft-Pfad (AC-4) |

### Scope Assessment
- Files: 2 (1 MODIFY + 1 CREATE)
- Estimated LoC: +36
- Risk Level: LOW — additive Bubble, nur bei gesetztem Flag; ohne Flag Telegram-Ausgabe unverändert.

### Technical Approach
1. In `render_telegram_bubbles` nach `bubbles.append(head)` prüfen `any_official_alerts_unavailable(segments)`; bei True eine dedizierte Hinweis-Bubble anhängen (vor oder direkt beim Warn-Bubble, sicherheitsrelevant nahe dem Kopf).
2. Text aus dem geteilten Baustein — KEIN neuer Textbaustein.
3. Ohne Flag: keine zusätzliche Bubble (Bubble-Anzahl + Inhalt unverändert).

### Dependencies
- Upstream: `official_alerts_unavailable` (Scheduler, #1348). Renderer liest nur.
- Downstream: keine.

### Open Questions
- Keine PO-Frage offen (Wortlaut = geteilter E-Mail-Baustein, kein Kürzel nötig).
