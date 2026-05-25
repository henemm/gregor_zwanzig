---
entity_id: issue_381_guard_message
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [hook, session-guard, dx]
---

# Session-Wächter: selbsterklärende Block-Meldung (Issue #381)

## Approval

- [x] Approved (User, 2026-05-25 — via Workflow phase3_spec → phase4_approved)

## Purpose

Die Block-Meldung des Session-Wächters soll eine geblockte Zweit-Sitzung beim
**ersten** Versuch korrekt zur Selbst-Isolierung führen. Aktuell weist sie auf
`EnterWorktree` hin, sagt aber nicht, dass dieses Werkzeug **direkt und parameterlos**
aufzurufen ist — ohne den sonst üblichen Aktivierungs-Umweg (Tool-Schema-Nachladen
via `ToolSearch`), der vom selben Wächter ebenfalls geblockt wird. Diese Lücke führte
real zu ~6–8 verschwendeten Tool-Aufrufen und dem Fehlschluss „neue Sitzung nötig".

## Source

- **File:** `.claude/hooks/session_singleton_guard.py`
- **Identifier:** `_block_message()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_session_singleton_guard.py` | Test | Prüft Meldungs-Inhalt (Z. 219–221) und F002 (keine `<>`-Platzhalter, Z. 504+) |
| Issue #379 | Vorgänger | Hat die `EnterWorktree`-Selbst-Isolierung eingeführt, die Sackgasse aber übersehen |

## Implementation Details

Reine Text-Änderung an `_block_message()`. Die Wächter-**Logik** (`_do_guard`,
`_is_rescue_command`, PID-Liveness, Owner-Auflösung) bleibt **unverändert**.

Ergänzt wird eine explizite Zeile, die klarstellt:

```
WICHTIG: Rufe EnterWorktree DIREKT auf (es braucht keine Parameter).
Versuche NICHT, es vorher per ToolSearch/Schema-Nachladen zu aktivieren —
das wird ebenfalls geblockt. Direkt aufrufen genügt.
```

Bestehende Bestandteile (gz-workspace-Fallback, „kein Neustart nötig") bleiben erhalten.
Keine spitzen Klammern `<` `>` (F002 bleibt grün).

## Expected Behavior

- **Input:** Tool-Aufruf einer geblockten Zweit-Sitzung (Nicht-Inhaber).
- **Output:** exit 2 + Block-Meldung auf stderr — jetzt mit explizitem Direkt-Aufruf-Hinweis.
- **Side effects:** keine; Logik/Exit-Codes/Rettungswege unverändert.

## Acceptance Criteria

- **AC-1:** Given eine geblockte Zweit-Sitzung liest die Block-Meldung, When sie die
  Isolierungs-Anweisung verarbeitet, Then steht dort explizit, `EnterWorktree`
  **direkt aufzurufen** und **keinen** `ToolSearch`-/Schema-Nachlade-Vorlauf zu versuchen.
  - Test: `tests/tdd/test_session_singleton_guard.py::test_issue381_block_message_directs_direct_enterworktree`

- **AC-2:** Given die geänderte Meldung, When die Guard-Test-Suite läuft, Then prüft ein
  Test den neuen Hinweistext (Erwähnung von `ToolSearch` + „direkt"), und die bestehenden
  Asserts (`gz-workspace`-Hinweis vorhanden, keine `<>`-Platzhalter) bleiben grün.
  - Test: `tests/tdd/test_session_singleton_guard.py::test_issue381_block_message_directs_direct_enterworktree`

## Known Limitations

- Behebt das *Auffinden* des Notausgangs, nicht den darunterliegenden Harness-Umstand,
  dass `EnterWorktree` ein deferred tool ist. Der robustere Vorschlag #2 aus #381
  (`ToolSearch`-Aufrufe für `EnterWorktree` gezielt durchlassen) ist bewusst **nicht**
  Teil dieses Specs (optional, invasiver) und kann separat folgen.
- Wächter ist load-bearing: Umsetzung über vollen TDD-Lauf der Guard-Suite, kein Hot-Patch
  einer fremden, aktiv abhängigen Sitzung.

## Changelog

- 2026-05-25: Initial spec created (Folge-Fund zu #379)
