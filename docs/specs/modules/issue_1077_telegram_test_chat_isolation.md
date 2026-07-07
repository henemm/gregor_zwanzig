---
entity_id: issue_1077_telegram_test_chat_isolation
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [telegram, testing, isolation, bug]
---

<!-- Issue #1077 — Telegram-Test-Leak: Test-Nutzer erhielten Briefings im echten Chat -->

# Issue 1077 — Telegram-Test-Chat-Isolation (with_user_profile Override-Reihenfolge)

## Approval

- [x] Approved (PO 'go', 2026-07-07)

## Purpose

Verhindert, dass Test-/Staging-Telegram-Versand im ECHTEN Chat des Nutzerprofils landet.
Root Cause: `Settings.with_user_profile()` setzt `force_test = True` für Test-Nutzer/Staging
und leitet über `for_testing()` bereits SMTP korrekt auf das Stalwart-Test-Konto um, überschreibt
danach aber bedingungslos `telegram_chat_id` mit der im Profil hinterlegten (echten) Chat-ID.
`for_testing()` selbst fasst `telegram_chat_id` bisher nie an — es gibt kein Telegram-Pendant zur
SMTP-Test-Umleitung. Ergebnis: Test-Nutzer `tg-live-e2e` mit gesetzter echter `telegram_chat_id`
im Profil erhielt Test-Briefings im Chat des PO statt in einem dedizierten Test-Chat.

## Source

- **File:** `src/app/config.py` — `Settings.for_testing()` (Z.166-190), `Settings.with_user_profile()` (Z.197-233)
- **File:** `src/app/config.py` — neues Feld `telegram_test_chat_id` (Z.142/143)

> Python-Backend-Schicht (`src/app/`) — kein Frontend-, Go-API-Anteil.

## Estimated Scope

- **LoC:** ~40–60
- **Files:** 2 (config.py, neue TDD-Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GZ_TELEGRAM_TEST_CHAT_ID` | Env | Neue Env-Var, automatisch gemappt über `env_prefix="GZ_"` auf `telegram_test_chat_id` |
| `Settings._is_test_user()` / `is_test_user_id()` | intern | Bestimmt `force_test` zusammen mit `env == "staging"` (bereits vorhanden, Issue #1013) |

## Implementation Details

**(1) Neues Settings-Feld** — `telegram_test_chat_id: str = Field(default="", ...)` neben
`telegram_chat_id`. Kein manuelles Env-Mapping nötig: `env_prefix="GZ_"` bildet automatisch
`GZ_TELEGRAM_TEST_CHAT_ID` → `telegram_test_chat_id` ab (verifiziert per Python-Snippet).

**(2) `for_testing()` — Telegram-Pendant zur SMTP-Umleitung** — in BEIDEN `model_copy(update={...})`-
Branches zusätzlich `"telegram_chat_id": self.telegram_test_chat_id or self.telegram_chat_id`
aufnehmen. Damit routet `for_testing()` Telegram genauso konsequent wie SMTP auf den Test-Kanal,
mit Fallback auf den bisherigen Wert falls kein Test-Chat konfiguriert ist (fail-soft, kein Bruch
bestehender Aufrufer ohne `telegram_test_chat_id`).

**(3) `with_user_profile()` — Override-Reihenfolge korrigieren** — Profil-Override von
`telegram_chat_id` nur anwenden, wenn NICHT `force_test`:
`if profile.get("telegram_chat_id") and not force_test:`. Für echte Nutzer (kein Test-Nutzer,
keine Staging-Umgebung) bleibt das Verhalten unverändert — die Profil-Chat-ID gewinnt weiterhin.

**Reihenfolge:** 1 (Feld) → 2 (`for_testing()` routet Telegram) → 3 (`with_user_profile()` lässt
den Test-Chat aus (2) nicht mehr überschreiben).

## Expected Behavior

- **Input:** Test-Nutzer-Profil (`is_test_user: true` oder Namens-Substring „test"/„tdd") mit
  gesetzter, echter `telegram_chat_id`; `Settings.env == "staging"` oder Test-Nutzer-ID
- **Output:** `with_user_profile()` liefert `telegram_chat_id == telegram_test_chat_id`
  (Fallback: unveränderte globale `telegram_chat_id`, falls kein Test-Chat konfiguriert),
  NIEMALS die Profil-Chat-ID
- **Side effects:** Keine für echte Nutzer/Produktion — dort bleibt die Profil-Chat-ID
  wie bisher maßgeblich (`force_test == False`)

## Acceptance Criteria

- **AC-1:** Given ein Test-Nutzer (`is_test_user: true` im Profil) mit einer echten `telegram_chat_id` im Profil und konfiguriertem `telegram_test_chat_id` / When `with_user_profile(user_id)` aufgerufen wird / Then ist `telegram_chat_id` des Ergebnisses gleich `telegram_test_chat_id` und NICHT die Profil-Chat-ID.
  - Test: `test_test_user_telegram_forced_to_test_chat_not_profile_chat` — Profil `tg-live-e2e` mit `telegram_chat_id="8346977700"`, `Settings(env="staging", telegram_test_chat_id="TESTCHAT999")`, `with_user_profile("tg-live-e2e")` liefert `"TESTCHAT999"` und beweist explizit `!= "8346977700"`.

- **AC-2:** Given ein echter Nutzer (kein Test-Nutzer, `env` nicht `staging`) mit `telegram_chat_id` im Profil / When `with_user_profile(user_id)` aufgerufen wird / Then bleibt `telegram_chat_id` wie bisher aus dem Profil übernommen (kein Regress).
  - Test: `test_real_user_telegram_still_taken_from_profile` — Profil `henning` mit `telegram_chat_id="REALCHAT"`, `Settings(env="production")`, `with_user_profile("henning")` liefert `"REALCHAT"`.

## Known Limitations

- Ist `telegram_test_chat_id` nicht konfiguriert (leerer String), fällt `for_testing()` auf die
  bisherige globale `telegram_chat_id` zurück — kein Hard-Fail, aber auch kein Schutz vor dem
  Leak in diesem Grenzfall. Betrieb MUSS `GZ_TELEGRAM_TEST_CHAT_ID` auf Staging setzen, damit der
  Fix greift.
- Betrifft ausschließlich `telegram_chat_id`. `mail_to`/`sms_to` waren von diesem Bug nicht
  betroffen (E-Mail-Routing über `for_testing()` war bereits korrekt, SMS außerhalb Scope).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix — überträgt das bereits etablierte Muster der SMTP-Test-Umleitung
  (`for_testing()`) 1:1 auf Telegram und korrigiert die Override-Reihenfolge in
  `with_user_profile()`. Keine neue Architektur-Entscheidung.

## Testplan

**Datei:** `tests/tdd/test_issue_1077_telegram_test_chat_isolation.py`

Keine Mocks (Projektregel) — echte `Settings`-Roundtrip-Tests gegen ein temporäres
`data/`-Verzeichnis (`tmp_path` + `monkeypatch.chdir`), keine `Mock()`/`patch()`/`MagicMock`.

| AC | Test-Funktion |
|----|---------------|
| AC-1 | `test_test_user_telegram_forced_to_test_chat_not_profile_chat` |
| AC-2 | `test_real_user_telegram_still_taken_from_profile` |

## Changelog

- 2026-07-07: Initial spec erstellt — Issue #1077
