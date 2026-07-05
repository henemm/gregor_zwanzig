---
entity_id: issue_1014_telegram_live_optin
type: module
created: 2026-07-05
updated: 2026-07-05
status: draft
version: "1.0"
tags: [telegram, testing, isolation, bug]
---

<!-- Issue #1014 — Live-Telegram-Tests nur noch opt-in (Versand-Hälfte von "Tests nie über Produktion") -->

# Issue 1014 — Live-Telegram-Tests nur opt-in (GZ_TELEGRAM_LIVE)

## Approval

- [x] Approved (PO 'go', 2026-07-05)

## Purpose

Verhindert, dass ein breiter `pytest tests/tdd`-Lauf ungefragt echte Telegram-Nachrichten
versendet. Root Cause von Issue #1014: `test_issue_1001_telegram_bubbles.py` sourct beim
Modul-**Import** (pytest-Collection) Staging-Creds nach `os.environ` und öffnet damit für
alle nachfolgend importierten Live-Testdateien die `skipif`-Gates, ohne dass ein bewusstes
Opt-in stattgefunden hat.

## Source

- **File:** `tests/tdd/_telegram_live_fixture.py` — neue Funktionen `live_telegram_enabled()`,
  `load_staging_telegram_env()`
- **File:** `tests/tdd/test_issue_1001_telegram_bubbles.py` — Entfernen des Import-Autoloads
- **File:** `tests/tdd/test_issue_686_telegram_functional_live.py`, `test_issue_650_telegram_foundation.py`,
  `test_issue_671_bot_menu_autoset.py`, `test_e2e_telegram_pipeline.py`, `test_952_onset_alert_e2e.py`
  — Umstellung auf zentrales Gate

> Python-Test-Tooling (`tests/tdd/`) — kein Produktcode (`src/`), kein Frontend-, kein Go-API-Anteil.
> Dieser Fix berührt ausschließlich Test-Infrastruktur.

## Estimated Scope

- **LoC:** ~80–120
- **Files:** 9 (1 Fixture-Modul, 6 Live-Testdateien, 1 neue TDD-Testdatei, 1 kleine Doku-Änderung)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/_telegram_live_fixture.py` | intern | Bereits bestehendes zentrales Fixture-Modul (Issue #1013) — Gate wird hier ergänzt, keine neue Datei |
| Issue #1013 (live, 397fe7be) | Vorgänger | Fixture-Guard `GZ_ENV=staging` für `data_dir="data"` bleibt unverändert bestehen — Daten-/Routing-Hälfte |
| PO-Regel Staging-Bot | Prozess | Telegram-Live-Tests laufen ausschließlich gegen Staging-Bot/-Creds (Memory `reference_staging_telegram_bot`) |
| e2e-verify-Skill (`staging_gate.py`) | intern | Erzwingt Live-Test bei Telegram-Scope — Aufruf muss künftig `GZ_TELEGRAM_LIVE=1` setzen |

## Implementation Details

**(1) Zentrales Gate** in `tests/tdd/_telegram_live_fixture.py`:

```python
def live_telegram_enabled() -> bool:
    if os.environ.get("GZ_TELEGRAM_LIVE") != "1":
        return False
    load_staging_telegram_env()
    return bool(
        os.environ.get("GZ_TELEGRAM_BOT_TOKEN")
        and os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID")
    )


def load_staging_telegram_env() -> None:
    # identisch zur bisherigen _load_staging_telegram_env() aus
    # test_issue_1001_telegram_bubbles.py:40-58, aber NUR von
    # live_telegram_enabled() aufgerufen — nie mehr beim Modul-Import.
    ...
```

**(2) Alle Live-Testdateien** ersetzen ihre bisherige `skipif(not os.environ.get(...))`-
Bedingung durch:

```python
from tests.tdd._telegram_live_fixture import live_telegram_enabled

@pytest.mark.skipif(
    not live_telegram_enabled(),
    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)",
)
```

`skipif` wird zur Import-/Collection-Zeit ausgewertet — `live_telegram_enabled()` muss daher
idempotent und billig sein (kein Netzwerk-Call, nur env-Lookup + optionales Datei-Sourcing).

**(3) Kein `Settings()`-Token in Live-Sends:** `test_issue_671_bot_menu_autoset.py:195` baut
aktuell `TelegramOutput()` bzw. `Settings()` ohne expliziten Token — das würde in einem
Worktree mit kopierter Prod-`.env` den Prod-Bot-Token nutzen. Fix: Live-Send-Pfad baut Settings
explizit mit `os.environ["GZ_TELEGRAM_BOT_TOKEN"]` (aus dem Staging-Sourcing durch
`live_telegram_enabled()`), z.B. `Settings(telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"], ...)`
bzw. `TelegramOutput(settings)` mit so gebauten `settings`.

**(4) e2e-verify-Doku:** Schritt 3c (Telegram-Live-Aufruf) wird um `GZ_TELEGRAM_LIVE=1`
ergänzt — der bewusste Live-Lauf im Staging-Tree bleibt unverändert möglich, nur explizit
statt implizit.

**Reihenfolge:** (1) Gate zentral bauen → (2) alle Live-Dateien umstellen (inkl. Entfernen des
Import-Autoloads in `test_issue_1001_telegram_bubbles.py`) → (3) Token-Fix in `test_671` →
(4) Doku.

## Expected Behavior

- **Input:** Ein breiter `pytest tests/tdd`-Lauf ohne `GZ_TELEGRAM_LIVE`; derselbe Lauf mit
  `GZ_TELEGRAM_LIVE=1` und vorhandenen Staging-Creds; reiner Modul-Import der Live-Testdateien
- **Output:** Ohne Opt-in werden alle Live-Telegram-Tests übersprungen und `os.environ` bleibt
  um `GZ_TELEGRAM_*` unverändert. Mit Opt-in laufen sie wie bisher gegen den Staging-Bot.
- **Side effects:** Keine neuen — reine Gate-/Sourcing-Konsolidierung, kein neuer Versandpfad,
  kein Produktcode betroffen

## Acceptance Criteria

- **AC-1 (Opt-in-Pflicht):** Given `GZ_TELEGRAM_LIVE` ist NICHT gesetzt (Umgebung mit oder ohne
  Telegram-Creds, auch mit vorhandener CWD-`.env`) / When ein breiter pytest-Lauf über
  `tests/tdd` startet / Then werden ALLE Live-Telegram-Tests übersprungen (skipped) und es wird
  KEINE Telegram-API-Nachricht versendet; `load_staging_telegram_env()` schreibt NICHTS in
  `os.environ`.
  - Test: Neuer, isolierter Subprocess-pytest-Lauf (z.B. `subprocess.run([sys.executable, "-m",
    "pytest", "tests/tdd", "-k", "telegram", "-v"], env=<env ohne GZ_TELEGRAM_LIVE>)`) beweist
    anhand der Ausgabe, dass alle gefundenen Live-Telegram-Tests als `SKIPPED` markiert sind
    und kein Test fehlschlägt oder eine echte Sendung protokolliert; zusätzlich direkter Aufruf
    von `os.environ` vor/nach `live_telegram_enabled()` beweist unveränderten Zustand für die
    `GZ_TELEGRAM_*`-Keys.

- **AC-2 (Opt-in aktiv):** Given `GZ_TELEGRAM_LIVE=1` und `gregor_zwanzig_staging/.env` mit
  Bot-Token+Test-Chat-ID vorhanden / When `live_telegram_enabled()` ausgewertet wird / Then
  liefert es `True` und die Staging-Creds stehen in `os.environ` (Sourcing genau dann, nie
  beim Import).
  - Test: `GZ_TELEGRAM_LIVE=1` setzen, vorherigen Zustand von `os.environ["GZ_TELEGRAM_BOT_TOKEN"]`
    als nicht gesetzt beweisen, `live_telegram_enabled()` aufrufen, `True` sowie befüllte
    `os.environ["GZ_TELEGRAM_BOT_TOKEN"]`/`GZ_TELEGRAM_TEST_CHAT_ID"]` beweisen (echtes
    Dateisystem-Sourcing aus der realen `gregor_zwanzig_staging/.env`, kein Mock).

- **AC-3 (kein Import-Nebeneffekt):** Given der pure Import aller Live-Telegram-Testmodule
  (Collection) ohne `GZ_TELEGRAM_LIVE` / When die Module importiert werden / Then verändert
  kein Modul `os.environ` um `GZ_TELEGRAM_*`-Keys (der bisherige Autoload in `test_issue_1001`
  beim Import ist entfernt).
  - Test: Frischer Subprocess-Import via `subprocess.run([sys.executable, "-c", "import
    tests.tdd.test_issue_1001_telegram_bubbles; import os; assert not any(k.startswith(
    'GZ_TELEGRAM_') for k in os.environ)"], env=<env ohne GZ_TELEGRAM_LIVE und ohne
    GZ_TELEGRAM_* vorbelegt>)` mit Exit-Code 0 beweist, dass der Import allein keine
    `GZ_TELEGRAM_*`-Keys setzt.

- **AC-4 (kein CWD-.env-Token in Live-Sends):** Given ein Live-Send in einem der Live-Tests /
  When die Settings dafür gebaut werden / Then stammt der Bot-Token explizit aus
  `os.environ["GZ_TELEGRAM_BOT_TOKEN"]` (gesourcte Staging-Creds), nie implizit aus der
  CWD-`.env` via `Settings()`/`TelegramOutput()` ohne Token-Argument (konkret zu fixen:
  `test_issue_671_bot_menu_autoset.py` Live-Teil).
  - Test: Im Live-Teil von `test_issue_671_bot_menu_autoset.py` (nur unter `GZ_TELEGRAM_LIVE=1`
    ausgeführt) beweisen, dass der tatsächlich für den Send verwendete `Settings`/`TelegramOutput`-
    Token mit `os.environ["GZ_TELEGRAM_BOT_TOKEN"]` übereinstimmt (z.B. über
    `settings.telegram_bot_token == os.environ["GZ_TELEGRAM_BOT_TOKEN"]` direkt am gebauten
    Objekt, vor dem echten API-Call) — kein impliziter `Settings()`-Aufruf ohne Token-Argument
    mehr im Live-Send-Codepfad dieser Datei.

## Known Limitations

- EnterWorktree kopiert weiterhin die Prod-`.env` 1:1 in neue Worktrees (Harness-Verhalten,
  nicht repo-seitig fixbar) — durch AC-1/AC-4 wird dieses Risiko für Test-Läufe entschärft
  (kein implizites Opt-in, kein impliziter Token-Bezug aus der CWD-`.env`), aber die Kopie
  selbst bleibt bestehen.
- Das Gate schützt ausschließlich pytest-Live-Tests. Ein manuelles Skript oder ein direkter
  Python-Aufruf außerhalb der Testsuite, der `TelegramOutput()` ohne Token instanziiert, wird
  davon nicht erfasst.
- `e2e-verify` Schritt 3c erfordert künftig zusätzlich `GZ_TELEGRAM_LIVE=1` in seinem Aufruf —
  diese Doku-Anpassung ist Teil dieses Fixes, ein vergessenes Nachziehen in abgeleiteten
  Runbooks/Skripten außerhalb des Repos wird davon nicht automatisch erfasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Test-Tooling-Fix (Opt-in-Gate + Konsolidierung bestehender
  `skipif`-Bedingungen), keine neue Architektur-Entscheidung — Produktcode bleibt unberührt.

## Testplan

**Datei:** `tests/tdd/test_issue_1014_live_optin.py`

Keine Mocks (Projektregel) — alle Tests arbeiten gegen den echten Prozess-/Dateisystem-Zustand.
AC-1 und AC-3 sind **prozess-isoliert** zu beweisen: ein subprocess-pytest-Lauf bzw. ein
frischer Modul-Import via `subprocess`, damit der `os.environ`-Zustand des aufrufenden
Testprozesses selbst nicht durch das Setzen von `GZ_TELEGRAM_LIVE` im aktuellen Prozess
verfälscht wird. Kein `assert 'xyz' in file.read_text()` — jeder Test beweist beobachtbares
Verhalten (Skip-Status, `os.environ`-Zustand, Token-Identität).

| AC | Test-Funktion |
|----|---------------|
| AC-1 | `test_without_optin_all_live_tests_skip_and_env_unchanged` |
| AC-2 | `test_with_optin_gate_returns_true_and_sources_env` |
| AC-3 | `test_module_import_alone_sets_no_telegram_env_vars` |
| AC-4 | `test_issue_671_live_send_uses_sourced_token_not_cwd_env` |

## Changelog

- 2026-07-05: Initial spec erstellt — Issue #1014
