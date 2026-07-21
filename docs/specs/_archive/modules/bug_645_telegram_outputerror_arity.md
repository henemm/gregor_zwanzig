# Spec: Bug #645 — OutputError in telegram.py mit korrekter Arität

- **Created:** 2026-06-07
- **Issue:** #645
- **Type:** bug
- **Scope:** Backend (`src/outputs/telegram.py`)

## Problem

`src/outputs/telegram.py` konstruiert `OutputError` an drei Stellen (Z. 54/57/60) mit nur **einem**
Positionsargument. `OutputError.__init__(self, channel, message)` (`src/outputs/base.py:55`) verlangt
**zwei**. Im Fehlerpfad eines ausgehenden Telegram-Sends (HTTP-Status ≠ 200, Timeout, Netzwerkfehler)
entsteht dadurch:

```
TypeError: OutputError.__init__() missing 1 required positional argument: 'message'
```

statt eines sauberen `OutputError` mit der Meldung `[telegram] ...`. `email.py` und `sms.py` rufen den
Konstruktor korrekt mit zwei Argumenten auf.

## Ziel

`TelegramOutput.send()` wirft in allen drei Fehlerfällen einen korrekt konstruierten `OutputError` mit
`channel="telegram"` und einer aussagekräftigen Meldung — niemals einen `TypeError`.

## Acceptance Criteria

**AC-1:** Given ein ausgehender Telegram-Send, dessen HTTP-Antwort einen Status ungleich 200 hat, When
`TelegramOutput.send()` aufgerufen wird, Then wird ein `OutputError` (kein `TypeError`) geworfen, dessen
`channel`-Attribut `"telegram"` ist und dessen String-Darstellung mit `[telegram]` beginnt und den
HTTP-Statuscode enthält.

**AC-2:** Given ein ausgehender Telegram-Send, der mit einem `httpx.HTTPError` (z. B. Netzwerk-/Verbindungsfehler)
fehlschlägt, When `TelegramOutput.send()` aufgerufen wird, Then wird ein `OutputError` (kein `TypeError`)
geworfen, dessen `channel`-Attribut `"telegram"` ist und dessen String-Darstellung mit `[telegram]` beginnt.

**AC-3:** Given die drei `raise OutputError(...)`-Aufrufe in `telegram.py`, When der Fix angewendet ist,
Then übergeben alle drei das `channel`-Argument `"telegram"` als ersten Parameter, konsistent mit der
Aufrufkonvention in `email.py` und `sms.py`.

## Out of Scope

- Kein Retry-/Resilienz-Umbau des Telegram-Kanals (fire-and-forget bleibt unverändert).
- Keine Änderung an `OutputError`, `email.py`, `sms.py`.
- Kein Eingriff in den Inbound-Webhook-Pfad (#637).

## Test-Strategie (mock-frei)

Echter HTTP-Call gegen `https://api.telegram.org/bot<ungültiger-token>/sendMessage`: Die Telegram-API
antwortet real mit HTTP 404 (Status ≠ 200) → realer Fehlerpfad (AC-1). Verifiziert wird der Exception-Typ
(`OutputError`, nicht `TypeError`), das `channel`-Attribut und das `[telegram]`-Präfix. Vor dem Fix ist
der Test rot (`TypeError`), nach dem Fix grün. Kein `Mock`/`patch`.
