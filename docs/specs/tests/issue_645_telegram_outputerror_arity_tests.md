---
entity_id: issue_645_telegram_outputerror_arity_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, outputs, error-handling, tests]
---

# Tests: #645 OutputError in telegram.py mit korrekter Arität

Test-Spec zu `docs/specs/modules/bug_645_telegram_outputerror_arity.md`.
Mock-frei: echter HTTP-Call gegen die Telegram-API mit ungültigem Bot-Token
(reale HTTP-4xx-Antwort, faktisch 401 Unauthorized → realer Fehlerpfad).

## Test-Fälle

- **test_non_200_raises_outputerror_not_typeerror** — ausgehender Send mit ungültigem Token löst
  einen `OutputError` (KEIN `TypeError`) aus; `channel == "telegram"`, String beginnt mit `[telegram]`
  (AC-1). RED vor Fix (`TypeError` entweicht `pytest.raises(OutputError)`), GRÜN danach.
- **test_non_200_message_contains_status_code** — die `OutputError`-Meldung enthält den realen
  HTTP-Statuscode (statuscode-agnostisch geprüft via Regex `\b\d{3}\b`; reale API antwortet 401) (AC-1).
  RED vor Fix, GRÜN danach.
- **test_http_error_path_raises_clean_outputerror** — mock-frei: die API-Basis wird via `monkeypatch`
  auf `http://127.0.0.1:1` (Connection refused) umgelenkt; httpx führt einen ECHTEN Verbindungsversuch
  aus und wirft eine reale `httpx.ConnectError` (Subklasse von `httpx.HTTPError`). `send()` muss einen
  `OutputError` (kein `TypeError`) mit `channel == "telegram"` und Präfix `[telegram]` werfen — deckt den
  dritten `raise`-Pfad ab (AC-2/AC-3). RED vor Fix, GRÜN danach.

## Behavior-Preservation

Der Happy-Path (HTTP 200) bleibt unverändert; nur der Fehlerpfad wirft jetzt einen sauberen
`OutputError` statt eines `TypeError`.
