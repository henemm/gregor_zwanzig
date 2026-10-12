# Context: fix-1369-inbound-telegram-poll-entfernen

## Request Summary
#1369: `InboundTelegramReader._get_updates` ruft `getUpdates` mit dem rohen Produktiv-Bot-Token an den Egress-Guards aus #1363 vorbei. Der Poll-Pfad ist totes Holz (Webhook seit #637) -> laut Issue bevorzugt **entfernen** statt absichern.

## Befund (am Code belegt, Stand origin/main ebac1b42f)
- Einziger Aufrufer von `poll_and_process` -> `_get_updates`: Endpoint `POST /inbound-telegram` (`api/routers/scheduler.py:226-238`, Singleton `_telegram_reader` Zeile 27).
- Kein Go-Aufrufer: `internal/scheduler/telegram_poll_removed_test.go` belegt, dass der Job nicht mehr geplant wird. Keine Treffer fuer `inbound-telegram` in `henemm-infra`, `internal/`, Frontend.
- Die Klasse `InboundTelegramReader` LEBT: `api/routers/webhook.py:70/88` nutzt `_process_update` (Webhook-Eingang). Entfernt wird nur der Poll-Pfad.

## Related Files
| File | Relevanz |
|------|----------|
| `src/services/inbound_telegram_reader.py` | `poll_and_process` (~159), `_get_updates` (~188), `self._offset` (__init__), `TELEGRAM_API_BASE`, ggf. `httpx`-Import (pruefen, ob sonst genutzt) |
| `api/routers/scheduler.py` | Endpoint `trigger_inbound_telegram` + `_telegram_reader` entfernen |
| `tests/tdd/test_bug599_telegram_persistent.py` | Zeilen 14-75 testen Singleton/Endpoint -> obsolet (loeschen); Zeilen ab ~90 (`_process_start_command`) bleiben |
| `tests/test_success_status_guard.py` | Ratschen-Eintraege fuer `trigger_inbound_telegram` (1520, 1850) und `poll_and_process` (1538, 1922, 2035) mitziehen |
| `tests/tdd/test_bug590_signal_removal_telegram_start.py:97` | patcht `services.inbound_telegram_reader.httpx` -> Import muss bleiben oder Test anpassen |
| `docs/specs/modules/egress_guard_telegram.md` | Known Limitation (Zeilen ~277-289) streichen, Changelog-Zeile |
| `docs/specs/modules/telegram_webhook_inbound.md` | erwaehnt Poll-Rueckbau, ggf. Hinweis ergaenzen |

## Existing Patterns
- Rueckbau toten Pfads mit Guard-Test: `internal/scheduler/telegram_poll_removed_test.go` (Go). Python-Pendant: Test, der zeigt, dass Endpoint und `_get_updates` nicht mehr existieren.
- Ratschen in `test_success_status_guard.py` sind eintragsweise zu pflegen (Regel-Budget: Eintraege entfernen, nicht aufweichen).

## Dependencies / Dependents
- Upstream: `httpx`, `Settings`, `NotificationService`.
- Downstream: Webhook-Router (`_process_update`) darf nicht beruehrt werden; alle `tests/tdd/*` die `InboundTelegramReader()` bauen nutzen `__init__` -> `_offset` entfernen ist unkritisch, solange kein Test `_offset` setzt (nur test_bug599).

## Risks & Considerations
- Falsches Loeschen von `httpx`-Import oder Hilfen, die `_process_update`/`_process_start_command` nutzen.
- Ratschen-Tests (`test_success_status_guard`) schlagen sonst rot an -> Eintraege gezielt entfernen.
- Kein Nutzerendpoint -> kein Zwei-Nutzer-Test noetig. Hoher Adversary-Level (Guard-/Sicherheitspfad), Mutations-Gegenprobe: Endpoint wieder einfuegen / `_get_updates` wieder einfuegen muss einen Test rot machen.
- Rueckweg falls Poll je wieder gebraucht wird: ueber neues ADR/Spec, nicht still (Runbook `deleteWebhook`).

## Analysis

### Type
Bug (Sicherheits-/Guard-Umgehung), Lösung: toten Poll-Pfad entfernen (Variante 1 aus dem Issue, bevorzugt).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/inbound_telegram_reader.py | MODIFY | `poll_and_process`, `_get_updates`, `self._offset`, `TELEGRAM_API_BASE` entfernen; `httpx`-Import nur behalten, wenn sonst genutzt (test_bug590 patcht ihn) |
| api/routers/scheduler.py | MODIFY | Endpoint `/inbound-telegram` + `_telegram_reader` entfernen (Email-`poll_and_process` Z.186/212 bleibt!) |
| tests/tdd/test_bug599_telegram_persistent.py | MODIFY | Singleton-/Endpoint-Tests (Z.14-75) löschen, `_process_start_command`-Teil bleibt |
| tests/test_success_status_guard.py | MODIFY | Ratschen-Einträge Telegram-`trigger_inbound_telegram`/`poll_and_process` entfernen (nicht aufweichen) |
| tests/ (neu, nach Verhalten benannt) | CREATE | Rückbau-Wächter: Endpoint + `_get_updates` existieren nicht mehr (Python-Pendant zu telegram_poll_removed_test.go) |
| docs/specs/modules/egress_guard_telegram.md, telegram_webhook_inbound.md | MODIFY | Known Limitation streichen, Changelog |

### Scope Assessment
- Files: ~6 (+ 1 neu), Estimated LoC: +40/-150 (Netto-Löschung)
- Risk Level: LOW — Poll-Pfad hat keinen Aufrufer (Go-Scheduler plant ihn nicht, kein Treffer in internal/, Frontend, infra); Webhook (`_process_update`) bleibt unberührt.

### Technical Approach
Löschen, nicht absichern: verkleinert Angriffsfläche, kein Guard-Code zu pflegen. Rückbau-Wächter-Test + Mutations-Gegenprobe (Endpoint/`_get_updates` wieder einfügen → Test rot).

### Dependencies
`webhook.py:70/88` nutzt `InboundTelegramReader._process_update` — bleibt. Nutzerisolation nicht berührt (kein Nutzerendpoint, kein Zwei-Nutzer-Test nötig).

### Open Questions
- [ ] Keine für den PO. Technisch in Phase 3 prüfen: `httpx` anderweitig im Modul genutzt?
