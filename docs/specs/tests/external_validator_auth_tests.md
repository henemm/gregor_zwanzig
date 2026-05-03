---
entity_id: external_validator_auth_tests
type: test
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.0"
tags: [validator, auth, tdd, tests]
---

# External Validator Auth — TDD-RED-Tests

## Approval

- [x] Approved

## Purpose

TDD-RED-Tests fuer Issue #110 (External Validator Auth). Decken die in der Modul-Spec
`docs/specs/modules/external_validator_auth.md` definierten Verhalten ab: Datei-Existenz
(Template, Setup-Skript, .gitignore-Eintrag), Dry-Run-Modus des Launchers, Cookie-Injection
in den Validator-Prompt, Warn-Verhalten ohne Credentials, Idempotenz des Setup-Skripts und
Doku-Abschnitt im Validator-Agent. Live-Tests gegen Staging sind als
`pytest.mark.integration` markiert und werden ohne `.claude/validator.env` geskippt.

## Source

- **File:** `tests/tdd/test_external_validator_auth.py`
- **Identifier:** Test-Funktionen `test_validator_env_example_exists_with_required_keys`,
  `test_gitignore_excludes_validator_env`,
  `test_setup_script_exists_and_is_executable`,
  `test_external_validator_agent_documents_authenticated_requests`,
  `test_validate_external_supports_dry_run_mode`,
  `test_validate_external_warns_when_no_credentials`,
  `test_validate_external_injects_cookie_with_real_login` (integration),
  `test_setup_script_idempotent_against_staging` (integration)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/external_validator_auth.md` | Module-Spec | Definiert das zu testende Verhalten |
| `pytest` | Test-Framework | Test-Runner |
| `subprocess` | Python stdlib | Bash-Skripte als Subprozess starten |
| `staging.gregor20.henemm.com` | Externer Service | Ziel der Integration-Tests (Login, Setup) |
| `.claude/validator.env` | Lokale Config (gitignored) | Credentials fuer Integration-Tests |

## Implementation Details

### Pure Datei-/Doku-Tests (kein Live-Call)

- `test_validator_env_example_exists_with_required_keys` — prueft, dass
  `.claude/validator.env.example` existiert und die drei Keys
  `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL` enthaelt.
- `test_gitignore_excludes_validator_env` — prueft, dass die Zeile
  `.claude/validator.env` in `.gitignore` steht (Trim, Zeilen-genaue Suche).
- `test_setup_script_exists_and_is_executable` — prueft, dass
  `scripts/setup-validator-user.sh` existiert, ausfuehrbar ist und einen
  `bash`-Shebang hat.
- `test_external_validator_agent_documents_authenticated_requests` — prueft, dass
  `.claude/agents/external-validator.md` einen Abschnitt `## Authenticated Requests`
  und ein Beispiel mit `Cookie: gz_session=` enthaelt.

### Dry-Run-Tests (Subprocess gegen Launcher, ohne Live-API)

- `test_validate_external_supports_dry_run_mode` — startet
  `bash .claude/validate-external.sh <SPEC>` mit `GZ_VALIDATOR_DRY_RUN=1` und ohne
  Credentials. Erwartet exit 0 und einen Prompt-Text, der „Du bist der External Validator"
  enthaelt — also keine echte `claude --print`-Session, sondern Prompt-Ausgabe.
- `test_validate_external_warns_when_no_credentials` — wie oben, prueft zusaetzlich,
  dass „Auth-Cookie" NICHT im Prompt steht (kein Cookie-Block ohne Login).

### Integration-Tests (echtes Staging, KEINE Mocks)

- `test_validate_external_injects_cookie_with_real_login` — startet Launcher mit
  Dry-Run + echtem Login gegen Staging, prueft dass der Prompt „Auth-Cookie" und
  „gz_session=" enthaelt. Skip wenn `.claude/validator.env` fehlt.
- `test_setup_script_idempotent_against_staging` — startet
  `scripts/setup-validator-user.sh` gegen Staging, erwartet exit 0 und einen Output
  mit „angelegt" oder „existiert bereits". Skip wenn `.claude/validator.env` fehlt.

## Expected Behavior

- **Input:** Tests werden via `uv run pytest tests/tdd/test_external_validator_auth.py`
  ausgefuehrt.
- **Output (RED-Phase):** Alle 6 Pure-/Dry-Run-Tests FAIL, weil die Implementation
  noch fehlt. Integration-Tests SKIP, weil keine Credentials vorhanden sind. Mindestens
  4 explizite Failures sichtbar.
- **Output (GREEN-Phase, nach Implementation):** Pure-/Dry-Run-Tests PASS. Integration-Tests
  PASS, sofern `.claude/validator.env` mit gueltigen Credentials existiert und Staging
  erreichbar ist; sonst SKIP.
- **Side effects:** Integration-Tests senden HTTP-Requests an
  `staging.gregor20.henemm.com` (Login, optional Register). Keine Aenderung an Production.

## Known Limitations

- Integration-Tests brauchen `.claude/validator.env` und einen erreichbaren Staging-Server.
  Werden ohne `.env` geskippt, also kein Hard-Fail in CI ohne Credentials.
- Pure-Tests pruefen Doku-Strings und Datei-Existenz — sie verifizieren NICHT, dass
  der HTTP-Login wirklich gegen Staging klappt (das macht der Integration-Test).
- Tests laufen subprocess-basiert. Bei Bash-Crashes ist das stderr fuer die Diagnose wichtig.

## Changelog

- 2026-05-03: Initial Test-Spec — TDD-RED fuer Issue #110
