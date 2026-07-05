---
entity_id: issue_1013_telegram_test_isolation
type: module
created: 2026-07-05
updated: 2026-07-05
status: draft
version: "1.0"
tags: [telegram, testing, isolation, bug]
---

<!-- Issue #1013 — Telegram-Live-Test-Artefakte laufen über Produktion -->

# Issue 1013 — Telegram-Test-Isolation (Fixture-Guard, Lookup-Vorrang, zentrale Test-User-Erkennung)

## Approval

- [x] Approved (PO 'go', 2026-07-05)

## Purpose

Verhindert, dass Live-Telegram-Test-Läufe (`ensure_test_user_with_active_trip`) Test-Artefakte
(`data/users/tg-live-e2e/`) in Produktionsdaten anlegen, und macht den Chat-ID-/E-Mail-Lookup
deterministisch, damit ein Test-User bei einer Kollision niemals vor einem echten User zurück-
gegeben wird. Root Cause von Issue #1013: der PO erhielt Test-Briefings über den Prod-Bot, weil
die Fixture ungeschützt CWD-relativ in `data/` schrieb und der Lookup den ersten `iterdir()`-
Treffer nahm.

## Source

- **File:** `tests/tdd/_telegram_live_fixture.py` — `ensure_test_user_with_active_trip()`
- **File:** `src/app/loader.py` — `list_all_user_ids()`, `lookup_user_by_telegram_chat_id()`, `lookup_user_by_email()`
- **File:** `src/app/config.py` — `Settings._is_test_user()`

> Python-Backend-Schicht (`src/app/`) + Test-Tooling (`tests/tdd/`) — kein Frontend-, Go-API-Anteil.

## Estimated Scope

- **LoC:** ~90–125
- **Files:** 4 (Fixture, loader.py, config.py, neue TDD-Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.config.Settings().env` | intern | Liefert `GZ_ENV` (bereits load-bearing Signal; Staging-`.env:42` setzt `GZ_ENV=staging`, Prod nicht) |
| `app.loader.list_all_user_ids()` | intern | Wird von beiden Lookup-Funktionen konsumiert — Sortier-/Nachrang-Logik landet hier zentral |
| PO-Regel Staging-Bot | Prozess | Telegram-Live-Tests laufen ausschließlich gegen Staging-Bot/-Creds (siehe Memory `reference_staging_telegram_bot`) |

## Implementation Details

**(a) Fixture-Guard, Root-Cause-Fix** — `ensure_test_user_with_active_trip(chat_id, data_dir="data")`
wirft `RuntimeError`, wenn `data_dir == "data"` UND `Settings().env.lower() != "staging"`. Alle
anderen Aufrufer (Unit-Tests) übergeben explizit `tmp_path` und sind vom Guard nicht betroffen.

```
if data_dir == "data" and Settings().env.lower() != "staging":
    raise RuntimeError(
        "ensure_test_user_with_active_trip() darf nur in Staging (GZ_ENV=staging) "
        "gegen den echten data-Ordner laufen — sonst Test-Artefakte in Produktion "
        "(Issue #1013). Für Unit-Tests explizit data_dir=tmp_path übergeben."
    )
```

**(c) Zentrale Test-User-Erkennung** — eine Prädikatsfunktion in `src/app/config.py` (oder als
Modul-Funktion importierbar von `loader.py`), die sowohl die bestehende Substring-Konvention
(„test"/„tdd") als auch den Fixture-User `tg-live-e2e` erkennt. Die Fixture schreibt beim Anlegen
zusätzlich `is_test_user: true` in `user.json`; das Prädikat prüft `user_id`-Substring ODER dieses
Flag aus dem Profil. `config.py._is_test_user` wird Thin-Wrapper auf dieses Prädikat (Konsolidierung
der bisher zwei inkonsistenten Konventionen: `config.py:168` Substring-only vs. `loader.py:794`
Prefix-only).

**(b) Lookup deterministisch** — `list_all_user_ids`, `lookup_user_by_telegram_chat_id` und
`lookup_user_by_email` iterieren sortiert und stellen echte User vor Test-Usern (Nachrang über
das Prädikat aus (c)). Damit gewinnt bei einer `telegram_chat_id`-Kollision immer der echte User,
unabhängig von Dateisystem-Iterationsreihenfolge.

**Reihenfolge:** a (Root-Cause) → c (Prädikat) → b (Lookup nutzt Prädikat).

## Expected Behavior

- **Input:** Fixture-Aufruf mit `data_dir="data"` außerhalb Staging; Chat-ID-/E-Mail-Kollision
  zwischen echtem User und Test-User; Test-User-IDs unterschiedlicher Namensmuster
- **Output:** `RuntimeError` statt stillem Schreiben in Prod-Daten; Lookup liefert deterministisch
  den echten User; einheitliches Test-User-Prädikat für alle Konsumenten
- **Side effects:** Keine — reine Guard-/Sortier-/Konsolidierungs-Logik, kein neuer Schreib- oder
  Versandpfad

## Acceptance Criteria

- **AC-1:** Given eine Umgebung mit `GZ_ENV != staging` (z.B. Hauptrepo/Prod) / When `ensure_test_user_with_active_trip(chat_id, data_dir="data")` aufgerufen wird / Then wirft die Fixture `RuntimeError` und es entsteht KEIN `data/users/tg-live-e2e/`-Verzeichnis. Mit explizitem `tmp_path`-`data_dir` bleibt sie erlaubt — bestehende Unit-Tests laufen weiter.
  - Test: `Settings().env` auf einen Nicht-Staging-Wert setzen, Fixture mit `data_dir="data"` aufrufen, `RuntimeError` erwarten und `Path("data/users/tg-live-e2e").exists()` als `False` beweisen; zusätzlich denselben Aufruf mit `data_dir=tmp_path` erfolgreich (kein Fehler, Verzeichnis existiert) durchführen.

- **AC-2:** Given `GZ_ENV=staging` (Staging-Tree) / When die Fixture mit `data_dir="data"` läuft / Then legt sie den Test-User wie bisher an (kein Regress der Staging-Live-Tests).
  - Test: `Settings().env` auf `"staging"` setzen, Fixture mit `data_dir="data"` aufrufen und beweisen, dass `data/users/tg-live-e2e/user.json` existiert und `telegram_chat_id` gesetzt ist (echtes Dateisystem-Verhalten, kein Mock).

- **AC-3:** Given zwei User mit identischer `telegram_chat_id` — ein echter (z.B. `henning`) und ein Test-User (`tg-live-e2e`) / When `lookup_user_by_telegram_chat_id(chat_id)` aufgerufen wird / Then wird deterministisch der echte User zurückgegeben (Test-User nachrangig, Iteration sortiert). Gleiches Verhalten für `lookup_user_by_email`.
  - Test: In einem `tmp_path`-`data_dir` zwei `user.json`-Profile mit identischer `telegram_chat_id` (bzw. identischer `mail_to`) anlegen — eines mit echter User-ID, eines mit Test-User-ID — und beweisen, dass beide Lookup-Funktionen konsistent die echte User-ID zurückgeben, unabhängig von der Anlage-/Dateisystem-Reihenfolge.

- **AC-4:** Given die User-IDs `test_xyz`, `tdd-123`, `tg-live-e2e` sowie `henning`, `steffi`, `admin`, `default`, `design_tdd` / When das zentrale Test-User-Prädikat angewendet wird / Then klassifiziert es `test_xyz`/`tdd-123`/`tg-live-e2e` als Test-User und die übrigen als echte User; `config.py._is_test_user` nutzt dieses Prädikat (eine Quelle).
  - Test: Prädikat direkt mit allen genannten IDs aufrufen und die erwartete Boolean-Klassifikation für jede ID beweisen; zusätzlich beweisen, dass `Settings()._is_test_user` für dieselben IDs identische Ergebnisse liefert wie das zentrale Prädikat (Delegation, keine Duplizierung der Logik).

## Known Limitations

- `design_tdd` bleibt wie bisher Test-klassifiziert (enthält Substring „tdd" — das zentrale
  Prädikat matcht das schon heute). Dieses Verhalten wird durch diesen Fix NICHT geändert.
- Der Guard schützt ausschließlich den Fixture-Aufrufpfad (`ensure_test_user_with_active_trip`
  mit `data_dir="data"`). Ein manuelles Anlegen von Test-Usern direkt in Produktionsdaten (z.B.
  per Hand oder über ein anderes Skript) wird davon nicht verhindert.
- Kein Telegram-Pendant zu `Settings.for_testing()` in diesem Fix — der Bot-Token bleibt global
  (SMTP/Telegram-Infrastruktur bleibt geteilt). Der Schutz vor Prod-Leck entsteht ausschließlich
  durch den Fixture-Guard (AC-1), nicht durch eine Token-Umleitung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix an bestehender Test-Isolation und Lookup-Determinismus, keine neue
  Architektur-Entscheidung — konsolidiert lediglich zwei bereits existierende, inkonsistente
  Test-User-Konventionen auf eine gemeinsame Quelle.

## Testplan

**Datei:** `tests/tdd/test_issue_1013_telegram_test_isolation.py`

Keine Mocks (Projektregel) — alle Tests arbeiten gegen das echte Dateisystem (`tmp_path` bzw.
gezielt gegen `Settings().env`), keine `Mock()`/`patch()`/`MagicMock` und keine reinen
Dateiinhalt-String-Checks. Jeder Test beweist beobachtbares Verhalten (Exception geworfen,
Verzeichnis existiert/existiert nicht, zurückgegebene User-ID).

| AC | Test-Funktion |
|----|---------------|
| AC-1 | `test_fixture_guard_raises_outside_staging_and_creates_no_prod_dir` |
| AC-1 | `test_fixture_guard_allows_explicit_tmp_path` |
| AC-2 | `test_fixture_allowed_in_staging_creates_test_user` |
| AC-3 | `test_lookup_by_telegram_chat_id_prefers_real_user_over_test_user` |
| AC-3 | `test_lookup_by_email_prefers_real_user_over_test_user` |
| AC-4 | `test_central_test_user_predicate_classifies_known_ids_correctly` |
| AC-4 | `test_is_test_user_delegates_to_central_predicate` |

## Changelog

- 2026-07-05: Initial spec erstellt — Issue #1013
