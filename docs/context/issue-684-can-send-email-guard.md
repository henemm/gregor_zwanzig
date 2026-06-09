# Context: Issue #684 — asymmetrischer `can_send_email()`-Guard im Alert-Versand

## Request Summary
Der Briefing-Alert-Pfad (`_send_alert`) versendet E-Mail ohne `can_send_email()`-Guard (asymmetrisch zum Telegram-Pfad und zum Radar-Pfad). Bei email-only effektivem Kanal mit unkonfiguriertem SMTP wird der Alert nicht zugestellt, aber Throttle + Alert-Log werden geschrieben und `check_and_send_alerts` gibt `True` zurück → stille Nicht-Zustellung mit positivem Status (False-Positive in Cockpit „Alarme · letzte 24 h").

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:634-713` | `_send_alert` — der buggy E-Mail-Pfad (kein `can_send_email()`-Guard) |
| `src/services/trip_alert.py:80-176` | `check_and_send_alerts` — schreibt Throttle (168) + Alert-Log (174) + `return True` unbedingt nach `_send_alert` |
| `src/services/trip_alert.py:550-594` | Radar-Pfad — Referenz-Pattern: `can_email/can_telegram`-Check, skip wenn kein Kanal, best-effort send, dann record |
| `src/app/config.py:123-130` | `can_send_email()` (host/user/pass/mail_to vorhanden) |
| `src/outputs/email.py:44-54` | `EmailOutput.__init__` wirft `OutputConfigError` bei unvollständigem SMTP |

## Existing Patterns
- **Radar-Pfad (Referenz, Z.553-592):** `can_email = can_send_email()`; wenn `not can_email and not can_telegram` → `continue` (kein Record). Best-Effort-Send je Kanal in try/except. Record (`_append_alert_log` + Throttle) **immer** nach Best-Effort — aber nur erreicht, wenn mind. 1 Kanal deliverable war.
- **Telegram-Pfad im selben `_send_alert` (Z.692):** bereits `if send_telegram and self._settings.can_send_telegram():` — die zu spiegelnde Symmetrie.
- **#656-Lehre (Memory):** Alert-Recording NIE an Live-SMTP-**Erfolg** koppeln (Rate-Limit→flaky). „Deliverable" = Kanal konfiguriert, nicht „send hat geklappt".

## Dependencies
- Upstream: `Settings.can_send_email/telegram`, `_effective_alert_channels` (#638), `EmailOutput`, `TelegramOutput`.
- Downstream: `check_and_send_alerts` (Throttle/Log/Return), `check_all_trips` (zählt `True`), Cockpit-Kachel „Alarme · letzte 24 h" (liest Alert-Log).

## Existing Specs
- Issue #638 (gerade gelandet) führte `_effective_alert_channels` ein; #684 ist F003 aus dessen Adversary-Review (bewusst aus #638-Scope gelassen).

## Risks & Considerations
- **Nicht** an SMTP-Erfolg koppeln (sonst #656-Anti-Pattern, flaky Throttle). „Tatsächlich erfolgte Zustellung" = mind. ein effektiver Kanal war **konfiguriert/deliverable**, Send selbst bleibt best-effort.
- Top-Level-Guard (Z.99) prüft „irgendein Kanal konfiguriert" — fängt den Fall email-only-effektiv + nur-Telegram-konfiguriert NICHT ab. Genau dieser Fall ist der Bug.
- Rückgabewert von `_send_alert` muss an `check_and_send_alerts` weitergereicht werden, um Throttle/Log/Return zu gaten.
