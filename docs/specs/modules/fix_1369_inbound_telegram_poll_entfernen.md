---
entity_id: fix_1369_inbound_telegram_poll_entfernen
type: module
created: 2026-10-12
updated: 2026-10-12
status: draft
version: "1.0"
tags: [bug, telegram, egress, security, rueckbau]
workflow: fix-1369-inbound-telegram-poll-entfernen
---

# Telegram-Poll-Pfad entfernen (#1369)

## Approval

- [ ] Approved

## Purpose

`InboundTelegramReader._get_updates` ruft `getUpdates` mit dem rohen
Produktiv-Bot-Token direkt über `httpx` auf und läuft damit an den
Egress-Guards aus #1363 vorbei. Der Pfad hat seit der Webhook-Umstellung (#637)
keinen Aufrufer mehr (Go-Scheduler plant den Job nicht mehr). Statt ihn
abzusichern, wird er **entfernt**: kleinere Angriffsfläche, kein Guard-Code zu
pflegen. Der Webhook-Eingang (`_process_update`, `_process_start_command`)
bleibt unberührt.

## Scope

Entfernt wird:
- `src/services/inbound_telegram_reader.py`: `poll_and_process`, `_get_updates`,
  `self._offset`, `TELEGRAM_API_BASE` und der dann ungenutzte `httpx`-Import
  (`httpx` wird dort nur in `_get_updates` genutzt).
- `api/routers/scheduler.py`: Endpoint `POST /inbound-telegram` und der
  Singleton `_telegram_reader`. Der E-Mail-Poll (`poll_and_process` des
  Mail-Readers) bleibt.
- Obsolete Tests: Singleton-/Endpoint-Teil in
  `tests/tdd/test_bug599_telegram_persistent.py`; die zugehörigen
  Ratschen-Einträge in `tests/test_success_status_guard.py` werden gestrichen
  (nicht aufgeweicht). `tests/tdd/test_bug590_signal_removal_telegram_start.py`
  patcht `services.inbound_telegram_reader.httpx` und wird so angepasst, dass
  der Patch entfällt.
- Doku: Rest-Lücke in `egress_guard_telegram.md` (Known Limitations) streichen;
  in `telegram_webhook_inbound.md` die Zeile „als deprecated markieren (nicht
  löschen — Notfall-Fallback)" und den Rollback-Hinweis auf „Poll-Job
  reaktivieren" durch den Rückbau ersetzen.

**Bewusste Abweichung von einer früheren Entscheidung:** `telegram_webhook_inbound.md`
hatte den Poll-Code als Notfall-Fallback behalten wollen. Das wird hier
ausdrücklich zurückgenommen (Sicherheitslücke wiegt schwerer; der Pfad ist seit
Monaten ungenutzt). Rückweg, falls Polling je wieder gebraucht wird: neue Spec
mit Guard von Anfang an, nicht stilles Wiedereinfügen.

## Acceptance Criteria

- **AC-1:** Given der Python-Core läuft / When jemand `POST /inbound-telegram` aufruft / Then antwortet er mit 404, weil der Endpoint nicht mehr existiert.
  - Test: `tests/tdd/test_telegram_poll_pfad_entfernt.py::test_endpoint_inbound_telegram_existiert_nicht` (pytest, FastAPI-TestClient gegen die echte App).

- **AC-2:** Given `InboundTelegramReader` / When man seine Methoden und Attribute prüft / Then gibt es weder `_get_updates` noch `poll_and_process` noch `_offset`, und das Modul enthält keinen `getUpdates`-Aufruf mehr.
  - Test: `tests/tdd/test_telegram_poll_pfad_entfernt.py::test_reader_hat_keinen_poll_pfad` (pytest; Attribut-Prüfung auf Klasse und Instanz plus Quellcode-Wächter `# doc-compliance-test` auf `getUpdates`).

- **AC-3:** Given der Webhook `POST /api/webhooks/telegram/{secret}` mit einem gültigen `/start TOKEN`-Update / When er verarbeitet wird / Then funktioniert die Befehlsverarbeitung unverändert (`_process_update` → `_process_start_command` liefert `True`).
  - Test: bestehende Tests `tests/tdd/test_bug590_signal_removal_telegram_start.py` (angepasst, ohne `httpx`-Patch) und Webhook-Router-Tests bleiben grün.

- **AC-4:** Given der E-Mail-Poll-Endpoint des Schedulers / When er aufgerufen wird / Then verhält er sich unverändert (nur der Telegram-Teil ist entfernt).
  - Test: bestehende Tests zu `trigger_inbound_email` in `tests/test_success_status_guard.py` bleiben grün; die Telegram-Einträge dort sind entfernt.

- **AC-5:** Given die Doku / When ein Leser `egress_guard_telegram.md` und `telegram_webhook_inbound.md` liest / Then steht dort keine offene Rest-Lücke `_get_updates` mehr und kein „Notfall-Fallback"-Hinweis; stattdessen der Rückbau mit Verweis auf #1369.
  - Test: `tests/tdd/test_telegram_poll_pfad_entfernt.py::test_doku_nennt_rueckbau` (pytest, `# doc-compliance-test`).

## Tests / Mutations-Gegenprobe

Der Rückbau-Wächter (neu, nach Verhalten benannt) muss rot werden, wenn der
Endpoint oder `_get_updates` wieder eingefügt wird. Mutations-Gegenprobe per
String-Ersetzung mit externer Sicherungskopie.

## Risiken

- `httpx`-Import nur entfernen, wenn kein anderer Nutzer im Modul (geprüft:
  nur `_get_updates`, Zeile 196).
- Kein Nutzerendpoint betroffen → kein Zwei-Nutzer-Test nötig.
- Datenmodell/Persistenz unberührt.

## Regel-Budget

Keine neue Pflicht-Regel, kein neues Gate; Netto-Löschung (~+40/−150 LoC).

## Changelog

- 2026-10-12: Initial spec erstellt — Issue #1369
