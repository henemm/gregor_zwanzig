---
entity_id: egress_guard_telegram
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [egress, isolation, telegram, staging]
workflow: fix-1363-telegram-egress
---

<!-- Issue #1363 — Scheibe C von #1337: Telegram-Egress-Isolation (alle schreibenden Methoden) -->

# Egress Guard Telegram — Alle schreibenden Bot-API-Methoden (Scheibe C von #1337)

## Approval

- [x] Approved

## Purpose

Telegram hat bereits einen dedizierten Staging-Bot (`@GregorZwanzigStaging_bot`,
getrennt vom Prod-Bot `@GregorZwanzig_bot`) und einen bestehenden Chat-ID-Guard
(`_guard_test_mode_chat_id`, #1288) — aber beide sind Insellösungen: die
Bot-Trennung ist reine Umgebungskonfiguration, die niemand erzwingt (geht die
Staging-`.env` verloren, läuft Staging still über den Prod-Bot), und der
bestehende Chat-Guard prüft nur `settings.telegram_chat_id`, nicht die
`chat_id`, die drei weitere schreibende Methoden (`_send_fallback_without_parse_mode`,
`delete_message`, `edit_message_text`) als Argument entgegennehmen. Deshalb steht
`api.telegram.org` im zentralen Egress-Wächter (`docs/specs/modules/egress_guard.md`)
noch hart auf `BLOCKED` — Staging kann Telegram aktuell gar nicht testen. Diese
Spec schließt beide Lücken nach dem Vorbild der SMS-Scheibe (#1336,
`docs/specs/modules/egress_guard_sms.md`): ein fail-closed Token-Guard erzwingt
strukturell den Test-Bot, ein erweiterter Chat-Guard erzwingt den Test-Chat auch
für die argument-basierten Methoden. Danach kann der Wächter `api.telegram.org`
von `BLOCKED` auf `TEST_ACCESS` heben.

## Source

- **File:** `src/output/channels/telegram.py`
- **Identifier:** `class TelegramOutput`, neue Methoden `_guard_test_mode_bot_token()`, `_guard_test_mode_target_chat(chat_id)`

> **Schicht-Hinweis:** Python-Core (`src/output/channels/`, `src/app/config.py`,
> `src/app/egress_guard.py`) plus die Go-Zwillingsliste (`internal/egress/inventory.go`,
> nur eine Zeile). Kein Frontend, keine Go-API-Handler betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/config.py` (`Settings`) | module | Trägt das neue Feld `telegram_test_bot_token`; `for_testing()` swappt `telegram_bot_token` darauf (beide `model_copy(update=...)`-Zweige) |
| `src/output/channels/telegram.py::_guard_test_mode_chat_id` | function | Bestehender Guard (#1288) — Fehlertext/Fail-closed-Verhalten bleiben unverändert; neue Methoden bauen strukturell darauf auf |
| `src/output/channels/sms.py::_guard_test_mode_sandbox_key` | function | Direktes Vorbild für den neuen Token-Guard (#1336) — identisches Fail-closed-Muster, hier auf Bot-Token statt API-Key übertragen |
| `src/app/egress_guard.py` (`INVENTORY`) | module | Python-Hälfte des zentralen Egress-Wächters (#1337, Scheibe A) — `api.telegram.org` wechselt von `BLOCKED` auf `TEST_ACCESS` |
| `internal/egress/inventory.go` (`Inventory`) | module | Go-Zwillingsliste — muss deckungsgleich mit `egress_guard.py::INVENTORY` bleiben |
| `tests/test_egress_inventory_drift.py` | test | Erzwingt Python==Go Deckungsgleichheit; MUSS nach beiden Änderungen weiterhin grün sein |
| `src/output/channels/base.py::OutputConfigError` | class | Exception-Typ des Guards, identisch zum bestehenden #1288-Guard |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/config.py` | MODIFY | Neues Feld `telegram_test_bot_token: str` (env `GZ_TELEGRAM_TEST_BOT_TOKEN`); in `for_testing()` `telegram_bot_token` → `telegram_test_bot_token` umgelenkt (beide `model_copy(update=...)`-Zweige, analog `seven_sandbox_key`) |
| `src/output/channels/telegram.py` | MODIFY | Neue Methoden `_guard_test_mode_bot_token()` und `_guard_test_mode_target_chat(chat_id)`; Aufrufe als erste Zeile in `send()`, `_send_fallback_without_parse_mode()`, `delete_message()`, `edit_message_text()`, `set_my_commands()` |
| `src/app/egress_guard.py` | MODIFY | `INVENTORY["api.telegram.org"]`: `BLOCKED` → `TEST_ACCESS` |
| `internal/egress/inventory.go` | MODIFY | `Inventory["api.telegram.org"]`: `Blocked` → `TestAccess` |
| `tests/tdd/test_telegram_test_isolation.py` | CREATE | Kern-Tests (Verhaltens-Name, nicht issue-nummeriert — `test_naming_gate.py` blockt sonst) |

### Estimated Changes
- Files: 4 geändert, 1 neu
- LoC: +80/-2

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein Mock-Theater) in
`tests/tdd/test_telegram_test_isolation.py`. Strategie identisch zum zentralen
Egress-Wächter und zu Scheibe B: `httpx.post` im Modul `output.channels.telegram`
wird durch einen Sentinel ersetzt, der bei Erreichen eine `AssertedNetworkTouch`-
Exception wirft — das beweist, dass der Guard *vor* jedem Netzwerk-Touch
entscheidet, ohne dass ein Mock die eigene Annahme zurückspiegelt.

### Automated Tests (TDD RED)

- [ ] Test 1 — Token-Guard blockt Fehlkonfiguration (parametrisiert über alle 5
  schreibenden Methoden): GIVEN `is_test_mode=True` und der aktive
  `telegram_bot_token` ist ungleich `telegram_test_bot_token`, WHEN `send()`,
  `_send_fallback_without_parse_mode()`, `delete_message()`,
  `edit_message_text()` oder `set_my_commands()` einzeln aufgerufen wird, THEN
  wirft die jeweilige Methode `OutputConfigError`, bevor der Sentinel erreicht
  wird.
- [ ] Test 2 — Fail-closed ohne Test-Bot-Token: GIVEN `is_test_mode=True` und
  `telegram_test_bot_token=""` (nicht provisioniert), WHEN eine der 5 Methoden
  aufgerufen wird, THEN wirft der Token-Guard ebenfalls `OutputConfigError`
  statt den unveränderten Prod-Token durchzulassen.
- [ ] Test 3 — Chat-Argument-Guard blockt (parametrisiert über die 3
  argument-basierten Methoden): GIVEN `is_test_mode=True`, korrekter
  Test-Bot-Token, aber die übergebene `chat_id` ist ungleich
  `telegram_test_chat_id`, WHEN `_send_fallback_without_parse_mode(chat_id=...)`,
  `delete_message(chat_id=...)` oder `edit_message_text(chat_id=...)` aufgerufen
  wird, THEN wirft `_guard_test_mode_target_chat()` `OutputConfigError` vor dem
  Sentinel.
- [ ] Test 4 — Durchlass bei korrekter Konfiguration: GIVEN `is_test_mode=True`,
  aktiver Token == `telegram_test_bot_token` UND (bei den 3 argument-basierten
  Methoden) `chat_id` == `telegram_test_chat_id`, WHEN eine der 5 Methoden
  aufgerufen wird, THEN wirft kein Guard und der Sentinel wird erreicht (Beweis
  „durchgelassen" ohne echten Netzwerk-Touch).
- [ ] Test 5 — `for_testing()` swappt den Bot-Token: GIVEN
  `telegram_bot_token="prod-token"` und `telegram_test_bot_token="staging-token"`,
  WHEN `settings.for_testing()` aufgerufen wird, THEN ist
  `for_testing().telegram_bot_token == "staging-token"` in BEIDEN
  Rückgabezweigen (mit und ohne gesetzte Test-SMTP-Creds).
- [ ] Test 6 — Prod-No-Op: GIVEN `is_test_mode=False`, WHEN
  `TelegramOutput(settings)` eine der 5 Methoden mit unverändertem
  Prod-`telegram_bot_token` aufruft, THEN werfen weder Token- noch
  Chat-Argument-Guard, und der Prod-Token/-Chat bleibt exakt der konfigurierte
  Wert.
- [ ] Test 7 — Bestehender #1288-Guard bleibt unverändert: GIVEN dieselbe
  Fehlkonfiguration wie vor dieser Spec (Chat-ID-Mismatch über
  `settings.telegram_chat_id` in `send()`), WHEN `send()` aufgerufen wird, THEN
  ist Fehlertext und Verhalten von `_guard_test_mode_chat_id()` identisch zum
  Stand vor #1363 — Regressionsschutz für #1288.
- [ ] Test 8 — Inventar-Flip + Drift-Wächter: GIVEN das aktualisierte
  `egress_guard.INVENTORY`, WHEN `INVENTORY["api.telegram.org"]` gelesen wird,
  THEN ist der Wert `IsolationKind.TEST_ACCESS`; UND der bestehende
  `tests/test_egress_inventory_drift.py` bleibt grün.

**Regressionsschutz (explizite Anforderung):** alle bestehenden Telegram-Tests
(inkl. der #1288-Chat-Guard-Tests) müssen nach dieser Änderung unverändert grün
bleiben — kein Test wird zur Anpassung an den neuen Guard umgeschrieben.

**Live-E2E (Marker `live`, nur bei `/e2e-verify`):** auf Staging echten Versand
über den Staging-Bot an den Test-Chat auslösen; Gegenprobe, dass der Prod-Chat
nichts erhält. Läuft unter dem bestehenden Opt-in-Gate `GZ_TELEGRAM_LIVE=1`
(#1014/#686). Nicht Teil der Kern-Schicht.

## Implementation Details

### Config-Feld + `for_testing()`-Swap (`src/app/config.py`)
Neues Feld analog `seven_sandbox_key` (siehe `egress_guard_sms.md`):
```
telegram_test_bot_token: str = Field(
    default="",
    description="Telegram Test-Bot-Token (env: GZ_TELEGRAM_TEST_BOT_TOKEN) — "
                 "Staging-Bot, nie der Produktiv-Bot",
)
```
In `for_testing()` wird in **beiden** `model_copy(update={...})`-Zweigen
zusätzlich zu `telegram_chat_id` und `seven_api_key` gesetzt:
`"telegram_bot_token": self.telegram_test_bot_token or self.telegram_bot_token`
— exakt dasselbe Muster. Fehlt der Test-Bot-Token, bleibt der Prod-Token
unverändert stehen; das ist die Fallback-Lücke, die der Channel-Guard
(nicht `for_testing()`) fail-closed abfängt.

### Token-Guard (`_guard_test_mode_bot_token`)
Struktur wie `SMSOutput._guard_test_mode_sandbox_key` (#1336):
- No-Op, wenn `self._settings.is_test_mode` False ist.
- Sonst: `test_token = self._settings.telegram_test_bot_token`,
  `active_token = self._settings.telegram_bot_token`.
- Wenn `not test_token or active_token != test_token`: `OutputConfigError(
  "telegram", "Test-Modus aktiv, aber es ist nicht der Test-Bot-Token
  (GZ_TELEGRAM_TEST_BOT_TOKEN) — Versand blockiert (#1363).")`.
- Aufruf als **erste Zeile** in allen 5 schreibenden Methoden: `send()`,
  `_send_fallback_without_parse_mode()`, `delete_message()`,
  `edit_message_text()`, `set_my_commands()`.

Dies ist die strukturelle Sicherung — sie deckt auch `set_my_commands()` ab,
das keine `chat_id` hat und deshalb vom Chat-Argument-Guard nicht erfasst
werden kann.

### Chat-Argument-Guard (`_guard_test_mode_target_chat`)
Der bestehende `_guard_test_mode_chat_id()` prüft ausschließlich
`self._settings.telegram_chat_id` (das Feld, nicht ein Methodenargument) und
bleibt für `send()` unverändert — Fehlertext und Verhalten aus #1288 dürfen
sich nicht ändern (Regressionsschutz, Test 7).

Neu: `_guard_test_mode_target_chat(chat_id)` prüft die **übergebene**
`chat_id`:
- No-Op, wenn `is_test_mode` False ist.
- Sonst: `test_chat_id = self._settings.telegram_test_chat_id`; wenn
  `not test_chat_id or str(chat_id) != str(test_chat_id)`:
  `OutputConfigError("telegram", "Test-Modus aktiv, aber chat_id={chat_id!r}
  ist nicht die konfigurierte Test-Chat-ID (GZ_TELEGRAM_TEST_CHAT_ID) —
  Versand blockiert (#1363).")`.
- Aufruf als erste Zeile in `_send_fallback_without_parse_mode(chat_id, ...)`,
  `delete_message(chat_id, ...)`, `edit_message_text(chat_id, ...)` — jeweils
  mit dem Methodenargument, nicht mit `self._settings.telegram_chat_id`.

`_guard_test_mode_chat_id()` kann intern `_guard_test_mode_target_chat(
self._settings.telegram_chat_id)` aufrufen, um Duplikation zu vermeiden —
solange der nach außen sichtbare Fehlertext für `send()` identisch bleibt.

### Bewusst OHNE Guard
- `answer_callback_query()` — hat keine `chat_id`, quittiert nur einen
  Ladespinner ohne Nebenwirkung auf fremde Chats.
- `get_my_commands()` — rein lesend, kein Egress-Risiko.

Details siehe `## Known Limitations`.

### Egress-Inventar-Flip (Andock an Scheibe A)
Nach obigen Änderungen ist `api.telegram.org` durch Token-Guard +
Chat-Argument-Guard + `for_testing()`-Swap genauso abgesichert wie
`gateway.seven.io` (Scheibe B) und `mail.henemm.com`. Damit kann der zentrale
Wächter den Host von einer harten Blockade auf einen deklarierten Test-Zugang
heben:
- `src/app/egress_guard.py:47`: `"api.telegram.org": IsolationKind.BLOCKED` →
  `"api.telegram.org": IsolationKind.TEST_ACCESS`
- `internal/egress/inventory.go:35`: `"api.telegram.org": Blocked` →
  `"api.telegram.org": TestAccess`

Beide Zeilen MÜSSEN deckungsgleich bleiben — erzwungen von
`tests/test_egress_inventory_drift.py`.

## Expected Behavior

- **Input:** `Settings`-Objekt mit `is_test_mode`, `telegram_bot_token`,
  `telegram_test_bot_token`, `telegram_chat_id`, `telegram_test_chat_id`;
  Aufrufe der 5 schreibenden `TelegramOutput`-Methoden
- **Output:** Im Test-/Staging-Modus entweder durchgelassener Aufruf
  (aktiver Token == Test-Token, und bei chat-basierten Methoden zusätzlich
  chat_id == Test-Chat-ID) oder `OutputConfigError`; in Prod
  (`is_test_mode=False`) unverändertes Original-Verhalten mit echtem Prod-Token
  und echter Prod-Chat-ID
- **Side effects:** Keine — reine Config-Feld-Ergänzung und zusätzliche
  Guard-Checks vor bestehenden `httpx.post`-Aufrufen; keine neue Persistenz,
  kein neuer Netzwerkaufruf

## Acceptance Criteria

- **AC-1:** Given `is_test_mode=True` und der aktive `telegram_bot_token` ist ungleich dem konfigurierten `telegram_test_bot_token` / When eine der 5 schreibenden Methoden (`send`, `_send_fallback_without_parse_mode`, `delete_message`, `edit_message_text`, `set_my_commands`) aufgerufen wird / Then wirft die jeweilige Methode `OutputConfigError`, bevor der HTTP-Sentinel erreicht wird — kein Netzwerk-Touch vor dem Raise
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_token_guard_blocks_mismatched_bot_token_before_transport` (parametrisiert über alle 5 Methoden)

- **AC-2:** Given `is_test_mode=True` und `telegram_test_bot_token=""` (nicht provisioniert) / When eine der 5 Methoden aufgerufen wird / Then wirft der Token-Guard ebenfalls `OutputConfigError` statt stillschweigend den Prod-Token zu verwenden (Fail-closed gegen die Fallback-Lücke)
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_token_guard_fails_closed_without_test_bot_token`

- **AC-3:** Given `is_test_mode=True`, korrekter `telegram_test_bot_token` aktiv, aber die übergebene `chat_id` ist ungleich `telegram_test_chat_id` / When `_send_fallback_without_parse_mode`, `delete_message` oder `edit_message_text` mit dieser `chat_id` aufgerufen wird / Then wirft `_guard_test_mode_target_chat()` `OutputConfigError` vor dem Sentinel
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_chat_argument_guard_blocks_wrong_target_chat` (parametrisiert über die 3 argument-basierten Methoden)

- **AC-4:** Given `is_test_mode=True`, aktiver Token == `telegram_test_bot_token` UND (bei chat-basierten Methoden) `chat_id` == `telegram_test_chat_id` / When eine der 5 Methoden aufgerufen wird / Then wirft kein Guard und der Transport-Sentinel wird erreicht (Beweis „durchgelassen" ohne echten Netzwerk-Touch)
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_guards_pass_through_matching_test_config`

- **AC-5:** Given `telegram_bot_token="prod-token"` und `telegram_test_bot_token="staging-token"` / When `settings.for_testing()` aufgerufen wird / Then ist `for_testing().telegram_bot_token == "staging-token"` in beiden Rückgabezweigen (mit und ohne gesetzte Test-SMTP-Creds)
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_for_testing_swaps_telegram_bot_token_both_branches`

- **AC-6:** Given `is_test_mode=False` (Prod) / When `TelegramOutput(settings)` eine der 5 Methoden mit unverändertem Prod-`telegram_bot_token` aufruft / Then sind beide Guards ein No-Op — kein `OutputConfigError`, Prod-Token und Prod-Chat-ID bleiben exakt die konfigurierten Werte
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_guards_are_noop_in_production_mode`

- **AC-7:** Given dieselbe Chat-ID-Fehlkonfiguration wie vor #1363 (Mismatch über `settings.telegram_chat_id` in `send()`) / When `send()` aufgerufen wird / Then ist Fehlertext und Verhalten von `_guard_test_mode_chat_id()` identisch zum Stand vor dieser Spec — kein Regress von #1288
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_existing_1288_chat_guard_unchanged`

- **AC-8:** Given das aktualisierte `egress_guard.INVENTORY` und die Go-Zwillingsliste / When `INVENTORY["api.telegram.org"]` gelesen wird / Then ist der Wert `IsolationKind.TEST_ACCESS`, UND `tests/test_egress_inventory_drift.py` bleibt grün (Python und Go bleiben deckungsgleich)
  - Test: `tests/tdd/test_telegram_test_isolation.py::test_inventory_flip_to_test_access` und der bestehende `tests/test_egress_inventory_drift.py`

## Known Limitations

- Die Provisionierung des Test-Bot-Tokens selbst (`GZ_TELEGRAM_TEST_BOT_TOKEN`
  auf Staging UND Prod setzen, Wert = bestehender Staging-Bot-Token) ist ein
  operativer Deploy-Schritt, kein Code-Änderungsteil dieser Spec. Ohne
  provisionierten Token bleibt der Kanal auf Staging dank Fail-closed-Guard
  (AC-2) weiterhin sicher blockiert. **Wichtig in Prod:** `is_test_mode`
  springt dort für Test-Nutzer an (`with_user_profile()` → `force_test` →
  `for_testing()`); ohne gesetzten `GZ_TELEGRAM_TEST_BOT_TOKEN` in Prod würde
  der fail-closed Guard dann den Telegram-Versand für Test-Nutzer blockieren
  — der Token muss deshalb in **beiden** Umgebungen liegen, nicht nur Staging.
- `answer_callback_query()` und `get_my_commands()` bleiben bewusst ohne
  Guard: Ersteres hat keine `chat_id` und quittiert nur einen clientseitigen
  Ladespinner ohne Nebenwirkung auf fremde Chats; Letzteres ist rein lesend.
  Beide bleiben in Prod wie in Test/Staging unverändert erreichbar — kein
  Sicherheitsrisiko, da keine Schreibwirkung auf einen fremden Chat/Bot
  entsteht.
- `with_user_profile()` (`config.py`) übernimmt Empfängerfelder aus dem
  Nutzerprofil auch im `force_test`-Fall ungebremst — identische, bereits in
  `egress_guard_sms.md` dokumentierte Restlücke. Bleibt hier bewusst
  unverändert, da der Chat-Argument-Guard bereits jeden Versand an eine
  Nicht-Test-Chat-ID blockiert.
- **Rest-Lücke `_get_updates` (eigene Klasse, nicht Teil dieser Spec):**
  `src/services/inbound_telegram_reader.py::InboundTelegramReader._get_updates`
  (Zeile ~120–139) liest `settings.telegram_bot_token` direkt und ruft
  `httpx.get()` ohne einen der beiden neuen Guards auf — weder Token- noch
  Chat-Argument-Guard sitzen in `TelegramOutput`, diese Klasse ist eine andere.
  Durch den Inventar-Flip (`api.telegram.org`: `BLOCKED` → `TEST_ACCESS`) ist
  dieser Aufruf jetzt zum ersten Mal überhaupt passierbar (vorher hätte der
  zentrale Wächter ihn ohnehin geblockt). Praktisch tot: Telegram-Updates
  laufen seit der Webhook-Umstellung (#637) per Push über
  `/api/webhooks/telegram/{secret}`, `_get_updates()` (Poll-Pfad) wird im
  Produktivbetrieb nicht mehr aufgerufen. Damit die Aussage „Telegram-Egress
  ist isoliert" ehrlich bleibt, ist dieser tote Poll-Pfad dennoch als offene
  Lücke dokumentiert statt stillschweigend als erledigt zu gelten —
  ausgelagert als **#1369**.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Übernimmt die bereits in `egress_guard.md` getroffene
  Grundsatzentscheidung (zentraler Wächter + Andock-Fläche für Scheiben B–E
  per Inventar-Zeile) und die in `egress_guard_sms.md` etablierte
  Fail-closed-Guard-Bauart. Diese Spec ist reine Feinjustierung eines
  einzelnen Hosts (plus Ausweitung des bestehenden #1288-Musters auf
  argument-basierte Methoden) nach demselben, bereits etablierten Muster —
  kein neuer Architektur-Entscheid nötig.

## Regel-Budget

Kein neues Gate und keine neue Pflicht-Regel — diese Spec fügt ausschließlich
eine Inventar-Zeile und zwei Channel-Guard-Methoden (Vorbild bereits etabliert
durch Telegram #1288 und SMS #1336) hinzu und dockt an den bestehenden
zentralen Egress-Wächter an. Sie erbt dessen Prüfdatum **2026-10-19** (siehe
`docs/specs/modules/egress_guard.md`) — kein eigenes, neues Prüfdatum nötig.

## Changelog

- 2026-07-24: Initial spec erstellt — Issue #1363, Scheibe C von #1337
- 2026-07-24: Umgesetzt — Token-Guard (`_guard_test_mode_bot_token`) + Chat-Argument-Guard (`_guard_test_mode_target_chat`) auf 5 schreibenden Methoden, `telegram_test_bot_token`-Feld inkl. `for_testing()`-Swap, Inventar-Flip `api.telegram.org` → `TEST_ACCESS` (Python + Go). Known Limitations um Rest-Lücke `inbound_telegram_reader.py::_get_updates` (→ #1369) ergänzt.
