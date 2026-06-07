# Context: bug-645-telegram-outputerror-arity

## Request Summary
`src/outputs/telegram.py` konstruiert `OutputError` an drei Stellen (Z. 54/57/60) mit nur **einem**
Argument, `OutputError.__init__(self, channel, message)` (base.py:55) verlangt jedoch **zwei**. Im
Fehlerpfad eines ausgehenden Telegram-Sends entsteht dadurch ein `TypeError` statt eines sauberen
`[telegram] ...`-`OutputError`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/outputs/telegram.py` | Enthält die 3 fehlerhaften `raise OutputError(...)` (Z. 54/57/60) — zu fixen |
| `src/outputs/base.py` | `OutputError.__init__(self, channel, message)` (Z. 55) — die Signatur |
| `src/outputs/email.py` | Korrekte Referenz: `OutputError("email", ...)` (Z. 178/195) |
| `src/outputs/sms.py` | Korrekte Referenz: `OutputError("sms", ...)` (Z. 54) |
| `tests/tdd/test_telegram_output.py` | Bestehende Telegram-Tests — hier Fehlerpfad-Test ergänzen |

## Existing Patterns
- `email.py`/`sms.py` rufen `OutputError(channel, message)` mit zwei Args auf → Fehlermeldung wird
  zu `[email] ...` bzw. `[sms] ...`. `telegram.py` soll identisch `[telegram] ...` liefern.
- Mock-freie Tests (CLAUDE.md): ein echter HTTP-Call gegen `https://api.telegram.org/bot<ungültig>/sendMessage`
  liefert HTTP 404 → triggert den realen Fehlerpfad ohne Mock. Vor Fix: `TypeError`, nach Fix: `OutputError`.

## Dependencies
- Upstream: `httpx` (echte API-Calls), `outputs.base.OutputError`
- Downstream: Scheduler/Router, die `TelegramOutput.send()` aufrufen und `OutputError` erwarten;
  ein `TypeError` würde deren Fehlerbehandlung durchbrechen.

## Existing Specs
- `docs/specs/modules/telegram_output.md` (Issue #11) — Basis-Spec des Kanals

## Risks & Considerations
- Severität niedrig–mittel: nur Fehlerpfad, kein Happy-Path betroffen → kein Datenrisiko.
- Vorbestehend seit a9d3a45a (2026-04-22), unabhängig von #637.
- Reiner Backend-Fix in `src/` → voller Staging/Prod-Deploy nötig (kein docs-only).
- Trivial: 3 Zeilen ändern. Risiko v.a. darin, den Test wirklich mock-frei + verhaltensbeweisend zu halten.
