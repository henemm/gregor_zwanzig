---
entity_id: issue_686_telegram_functional_live_tests
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [telegram, e2e, live-test, test-infrastructure, fixture, issue-686]
---

# Echte funktionale Telegram-Live-Tests ermöglichen (Issue #686)

## Approval

- [x] Approved (2026-06-09, PO — „go")

## GitHub-Issue (Single Source of Truth)

Maßgeblich ist **GitHub Issue #686** mit seinen 4 Akzeptanzkriterien. Diese Spec ist
die feinere technische Zerlegung; jedes Issue-AC ist vollständig abgedeckt:

| Issue-AC (#686) | Spec-AC | Abdeckung |
|-----------------|---------|-----------|
| AC-1 — reproduzierbare Staging-Test-Fixture (User + Chat + aktiver Trip) | AC-1 | 1:1 |
| AC-2 — alle 7 Befehle durch echte Pipeline, real zugestellt, Inhalt geprüft (mock-frei) | AC-2 (send→message_id, technisch nötig fürs Cleanup) + AC-3 (Inhalt) + AC-4 (Zustellung) | aufgeteilt |
| AC-3 — gesendete Test-Nachrichten nach Prüfung gelöscht (kein Chat-Müll) | AC-4 (deleteMessage-Teil) | 1:1 |
| AC-4 — Test in `/e2e-verify` verankert, SKIPPED/Fehlschlag blockt das Close-Gate | AC-5 | 1:1 — **muss echt blockieren, unabhängig adversarial geprüft** |

Kein Issue-AC wird verschlankt oder ausgelagert. Scope-Änderungen erfolgen ausschließlich
am GitHub-Issue durch den PO, nicht in dieser lokalen Spec.

## Purpose

**#686 — der Telegram-Bot wurde nie getestet, wie ein Nutzer ihn erlebt.**

`tests/tdd/test_e2e_telegram_pipeline.py` (das #672-Artefakt) prüft die Pipeline nur
gegen einen lokalen Socket (AC-1..4), und der einzige echte-Bot-Test (AC-5) war wegen
fehlender `GZ_TELEGRAM_TEST_CHAT_ID` **immer `SKIPPED`** — und selbst der ist nur ein
„kann der Bot senden"-Smoke, nicht „liefert Befehl X eine sinnvolle Wetter-Antwort".
Es existiert also **kein** Test, der die funktionale Wirklichkeit gegen den echten Bot
beweist.

Ursache des Blockers (2026-06-09 behoben): Der separate Staging-Bot war in keinem Chat
gestartet → `sendMessage` scheiterte mit „chat not found". Inzwischen hat der PO dem
Bot geschrieben → Chat `8346977700` ist sendbar (send→edit→delete verifiziert), und ein
erster echter `/heute`-Live-Lauf durch `_process_update` wurde vom PO in Telegram gesehen.

**Was fehlt** ist die dauerhafte Test-Infrastruktur — das Telegram-Pendant zu
`gregor-test@henemm.com`: eine reproduzierbare Test-Identität (Nutzer + Chat + aktiver
Trip) und ein automatischer Harness, der alle 7 Menü-Befehle real gegen den Bot fährt,
die Antworten inhaltlich prüft, danach aufräumt — und so verankert ist, dass ein
übersprungener Live-Test das Close-Gate blockiert.

## Source

- **File (neu, Fixture-Helper):** `tests/tdd/_telegram_live_fixture.py` — stellt
  idempotent Staging-Test-User + aktiven Trip sicher; liefert `(token, chat_id, user_id)`.
- **File (neu, Harness):** `tests/tdd/test_issue_686_telegram_functional_live.py`
- **File (Fix, klein):** `src/outputs/telegram.py` — `send()` gibt `message_id` zurück.
- **File (Verankerung):** `.claude/hooks/e2e_telegram_live.py` (neu, dependency-arm) +
  Aufruf in der `/e2e-verify`-Kette, sodass `SKIPPED` im Telegram-Scope als
  Nicht-bestanden gilt.
- **Server-Config (kein Code):** `GZ_TELEGRAM_TEST_CHAT_ID=8346977700` in
  `gregor_zwanzig_staging/.env` (über infra-Instanz).
- **Unter Test, nicht verändert:** `src/services/inbound_telegram_reader.py`
  (`_process_update`, `_resolve_user_for_chat`, `_find_active_trip`, `_parse_command`),
  `src/services/trip_command_processor.py` (`.process`, `_QUERY_KEYS`).

## Estimated Scope

- **LoC:** src ~10 (send-Rückgabe) + Tooling ~40 + Test/Fixture ~180 = ~230
- **Files:** 1 src berührt, 4 neu (Fixture, Harness, e2e-Hook) — LoC-Override evtl. nötig.
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@GregorZwanzigStaging_bot` | extern | Live-Bot (Token in `gregor_zwanzig_staging/.env`) |
| `src/outputs/telegram.py` | Output | `send`/`delete_message`, `BOT_COMMANDS` (7 Befehle) |
| `src/services/inbound_telegram_reader.py` | Service | echter Eintrittspunkt `_process_update` |
| `src/services/trip_command_processor.py` | Service | erzeugt die Antwort (echte Wetterdaten) |
| `src/app/loader.py` | Loader | `lookup_user_by_telegram_chat_id`, `load_all_trips` |

## Implementation Details

**Test-Fixture (`_telegram_live_fixture.py`):**
- Liest `GZ_TELEGRAM_BOT_TOKEN` + `GZ_TELEGRAM_TEST_CHAT_ID` aus der Umgebung.
- Stellt idempotent einen Staging-Test-User (z.B. `tg-live-e2e`) sicher: `user.json`
  mit `telegram_chat_id == GZ_TELEGRAM_TEST_CHAT_ID`; ein gültiger Trip mit
  `start_date <= heute <= end_date` (Vorlage aus einem bestehenden gültigen Trip, Datum
  auf das aktuelle Fenster gesetzt) → `_find_active_trip` liefert ihn.
- Read-modify-write: vorhandenen Test-User nicht zerstören (Datenerhalt-Regel).

**`send()`-Rückgabe (AC-2):**
- Bei HTTP 200 + `ok` die `result.message_id` (int) zurückgeben; sonst `None`.
- Rückwärtskompatibel: bestehende Aufrufer (die den Rückgabewert ignorieren) brechen nicht.

**Funktionaler Harness (gated hinter Token + Test-Chat-ID):**
- **Inhalt (AC-3):** Für jeden der 7 Befehle die echte Verarbeitungs-Pipeline fahren
  (user-scoped auf die Fixture, echte Wetterdaten) → `CommandResult.confirmation_body`
  prüfen: nicht leer, **kein** „Unbekannter Befehl", **kein** „Kein aktiver Trip".
- **Zustellung + Cleanup (AC-4):** Antwort real via `TelegramOutput.send` an den
  Test-Chat zustellen → `message_id` (≠ None) beweist Zustellung → sofort
  `delete_message(chat_id, message_id)` (`ok=True`). Keine Mocks — echte Telegram-API.
- Der echte Eintrittspunkt `_process_update` wird mindestens einmal voll durchlaufen
  (Webhook-realistisch).

**Verankerung (`e2e_telegram_live.py` + /e2e-verify, AC-5):**
- Hook führt den funktionalen Live-Test aus, wenn Token + Test-Chat-ID vorhanden sind.
- Fehlt die Test-Chat-ID, obwohl der Change-Scope Telegram berührt → **Nicht-bestanden**
  (kein stilles SKIPPED-als-grün). Exit-Code blockt das Close-Gate.

## Expected Behavior

- **Input:** Staging-Bot-Token + `GZ_TELEGRAM_TEST_CHAT_ID`; die 7 Menü-Befehle.
- **Output:** pro Befehl eine inhaltlich geprüfte, real zugestellte und wieder gelöschte
  Antwort; Gesamt-Verdict PASS/FAIL (SKIPPED nur außerhalb Telegram-Scope erlaubt).
- **Side effects:** kurzzeitige Test-Nachrichten im Test-Chat (sofort gelöscht);
  idempotente Test-User-/Trip-Dateien unter `gregor_zwanzig_staging/data/users/`.

## Acceptance Criteria

- **AC-1:** Given `GZ_TELEGRAM_TEST_CHAT_ID` ist gesetzt /
  When der Fixture-Helper ausgeführt wird /
  Then existiert ein Staging-Test-User, dessen `telegram_chat_id` exakt
  `GZ_TELEGRAM_TEST_CHAT_ID` ist und für den `_find_active_trip` einen Trip (nicht `None`)
  mit `start_date <= heute <= end_date` liefert; ein zweiter Aufruf verändert nichts
  (idempotent, keine Daten-Duplikate).

- **AC-2:** Given ein erfolgreicher `sendMessage` (HTTP 200, `ok=true`) /
  When `TelegramOutput.send(subject, body)` aufgerufen wird /
  Then gibt es die numerische `message_id` der gesendeten Nachricht zurück (vorher `None`);
  bei Fehler-Status oder fehlendem Ziel `None` — und bestehende Aufrufer, die den
  Rückgabewert ignorieren, funktionieren unverändert.

- **AC-3:** Given die aktive Test-Fixture (User + aktiver Trip) /
  When jeder der 7 Menü-Befehle (`glance`, `heute`, `morgen`, `heute_gewitter`,
  `timeline_heute`, `timeline_morgen`, `hilfe`) durch die echte Verarbeitungs-Pipeline
  gefahren wird /
  Then ist die erzeugte Antwort jeweils nicht leer und enthält **weder** „Unbekannter
  Befehl" **noch** „Kein aktiver Trip" — d.h. jeder Menü-Befehl liefert sinnvollen Inhalt.

- **AC-4:** Given Token + Test-Chat-ID gesetzt /
  When die Antwort jedes der 7 Befehle real an den Test-Chat zugestellt wird /
  Then liefert die echte Telegram-API je eine `message_id` (Zustellung bewiesen, mock-frei)
  und jede dieser Nachrichten wird anschließend per `deleteMessage` wieder entfernt
  (`ok=true`) — kein Chat-Müll bleibt zurück.

- **AC-5:** Given ein Change, dessen Scope den Telegram-Pfad berührt /
  When `/e2e-verify` läuft und `GZ_TELEGRAM_TEST_CHAT_ID` fehlt oder der funktionale
  Live-Test nicht ausgeführt wurde /
  Then meldet die Verankerung **Nicht-bestanden** (Exit ≠ 0) und blockiert das
  Issue-Close-Gate — ein `SKIPPED` im Telegram-Live-Pfad zählt nicht mehr als grün.

## Known Limitations

- Ein Telegram-Bot kann seine eigenen gesendeten Nachrichten nicht per API zurücklesen;
  „Zustellung" wird über die zurückgegebene `message_id` + erfolgreiches `deleteMessage`
  bewiesen, nicht über Read-Back. Inhaltsprüfung erfolgt am erzeugten Antworttext vor dem
  Senden (identisch zum gesendeten, da derselbe Pipeline-Output).
- Live-Test setzt einen erreichbaren Staging-Bot + gestarteten Test-Chat voraus
  (einmalige menschliche Aktion, bereits erfolgt).

## Changelog

- 2026-06-09: Initial spec (Issue #686 — funktionale Telegram-Live-Test-Infrastruktur).
