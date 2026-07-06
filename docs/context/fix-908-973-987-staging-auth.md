# Context: fix-908-973-987-staging-auth

## Request Summary
Seit dem nginx-Basic-Auth-Rollout auf Staging (henemm-infra #159, 28.06.2026) schlagen
diverse Test- und Gate-Läufe gegen `https://staging.gregor20.henemm.com` strukturell mit
401 fehl, weil weder die betroffenen Testdateien noch die Playwright-Staging-Config noch
`prod_selftest.py`'s Prod-Probe Basic-Auth-Credentials mitsenden. Ziel: zentraler
Auth-Mechanismus + Nachrüstung der betroffenen Stellen (#908, #973, #987), **ohne** die
offene 500-Root-Cause-Analyse am Radar-Debug-Trigger (Teil von #987, aber bewusst
ausgeklammert — potenziell eigener Produkt-Bug).

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/validator.env` (Hauptrepo, gitignored) | Enthält `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL` — Single Source of Truth für Staging-Basic-Auth-Creds, synchronisiert von `henemm-infra/scripts/sync-staging-validator-creds.sh` aus `/etc/henemm/secrets.env` |
| `.claude/hooks/design_fidelity_diff.py:144-153` | `load_validator_env()` — bestehendes, dupliziertes Python-Parser-Pattern für `validator.env` (kein zentrales Modul) |
| `tests/tdd/test_794_mobile_metric_label.py:26-40` | Zweites, fast identisches Kopie-Pattern desselben Parsers |
| `.claude/hooks/prod_selftest.py` (569 Zeilen) | Enthält `_probe_ac()` (142-191), `_URL_SENTINELS` (51), `_is_probeable_url()`, `_staging_to_prod_url()` (83-89), `_derive_verdict()` (338-352) — hier muss der Skip für Mail-Preview-ACs mit Staging-Test-Trip-URLs andocken |
| `frontend/playwright.staging.config.ts` (21 Zeilen) | Betroffene Config aus #973 — kein `httpCredentials` im `use`-Block, `setup`-Project macht nur App-Login |
| `frontend/playwright.880.staging.config.ts`, `frontend/playwright.953.staging.config.ts` | **Bereits funktionierendes Vorbild** — `httpCredentials: { username, password }` aus `GZ_VALIDATOR_USER`/`PASS` im `use`-Block, zusätzlich im Setup-Script gesetzt |
| `frontend/e2e/feat-880.staging.setup.ts`, `frontend/e2e/issue-953.staging.setup.ts` | Vorbild für Setup-Script-seitige `httpCredentials` in `playwright.request.newContext()` |
| `tests/tdd/test_issue_830_radar_alert_validator.py` | httpx-Calls ohne Auth gegen `STAGING_BASE` (Zeilen 54, 77); Prod-Call (352) erwartet bewusst 401/404 — **nicht** Teil des Bugs |
| `tests/tdd/test_issue_727_trips_null_safety.py`, `test_issue_496_layout.py`, `test_issue_692_telegram_disabled_unconfigured.py`, `test_issue_846_alert_preset_e2e.py` | Playwright-Tests mit App-Login, aber ohne `httpCredentials`/Basic-Auth |
| `tests/tdd/test_issue_577_atoms_values.py` | Playwright, App-Login via `GZ_VALIDATOR_USER/PASS`, kein Basic-Auth |
| `tests/tdd/test_issue_339_verify_timing.py`, `test_epic_404_phase2_ist_screenshots.py`, `test_staging_gate.py`, `test_issue_776_metrics_toggle.py` | **Nicht direkt 401-betroffen** (kein echter HTTP-Call zur Laufzeit bzw. bereits per Skip-Marker geschützt) — aus Scope-Liste raus |
| `tests/conftest.py`, `tests/tdd/conftest.py` | Einzige bestehenden "geteilten" Test-Utility-Orte — kein `tests/helpers/`-Ordner existiert bisher |

## Existing Patterns

- **Shell-seitiges Sourcing:** `scripts/setup-validator-user.sh:8-18` — `set -a; source .claude/validator.env; set +a`, danach `${VAR:?...}`-Pflichtprüfung. Referenz-Pattern fürs Team.
- **Env-Override-Vorrang:** `.claude/validate-external.sh:26-42` — explizite Env-Variablen gewinnen vor Datei-Werten.
- **Skip-Pattern in `prod_selftest.py`:** `_URL_SENTINELS` (wertbasiert) und `_is_probeable_url()` (Freitext-Erkennung) liefern bereits `SKIPPED_NO_URL`/`ATTESTED_SKIPPED`, ohne PARTIAL/FAIL auszulösen — direktes Vorbild für einen neuen pfadbasierten Skip (`/api/preview/{trip}/email` + bekannter Staging-Test-Trip).
- **`playwright.880`/`.953.staging.config.ts`:** funktionierendes `httpCredentials`-Muster aus `GZ_VALIDATOR_USER`/`PASS` mit Fallback auf `E2E_USER`/`E2E_PASS` — direkt übertragbar auf `playwright.staging.config.ts`.
- **Opt-in-Gating:** `test_issue_776_metrics_toggle.py:19-23` (`@pytest.mark.skipif(not os.environ.get("GZ_STAGING_E2E"), ...)`) — Vorbild für "läuft nur explizit, sonst Skip statt Fail".
- **Zwei parallele URL-Env-Var-Namen im Repo:** `GZ_SVELTE_BASE` (9 Dateien, Frontend/Playwright) vs. `GZ_VALIDATION_URL` (3 Dateien, aus `validator.env`) vs. 19 Dateien mit hartkodiertem Literal `"https://staging.gregor20.henemm.com"`. Kein Konsens — Konsolidierungskandidat, aber Vorsicht: Umbenennung aller 19+ Stellen wäre Scope-Explosion; ein zentraler Helper sollte beide Env-Var-Namen als Fallback unterstützen, nicht die Testdateien selbst umbenennen.

## Dependencies

- **Upstream:** `.claude/validator.env` ← `henemm-infra/scripts/sync-staging-validator-creds.sh` ← `/etc/henemm/secrets.env` (`GZ_STAGING_VALIDATOR_*`). Wir lesen nur, ändern die Sync-Kette nicht.
- **Downstream:** `prod_selftest.py`'s Verdict entscheidet laut Post-Deploy-Workflow über Issue-Close-Freigabe (`docs/reference/operations_playbook.md`) — Änderungen an der Skip-Logik wirken direkt auf den Deploy-Gate.
- Playwright-Configs mit `httpCredentials` werden vom `staging-validator`-Agent und von `/e2e-verify` genutzt.

## Existing Specs
Keine dedizierte Spec zu Staging-Auth-Infrastruktur gefunden — dies ist reine
Test-/Tooling-Infrastruktur, keine produktseitige Entity.

## Risks & Considerations
- **Kein zentrales Python-Loader-Modul für `validator.env` existiert** — neuer Helper
  (`tests/helpers/staging_auth.py` o.ä.) wäre ein neuer Namensraum unter `tests/`; Stil an
  `tests/tdd/conftest.py` orientieren.
- **`prod_selftest.py`-Änderung ist Gate-Logik** — jeder neue Skip-Fall muss durch die
  vorhandenen Regressionstests (`test_prod_selftest_730.py`, `test_prod_selftest_564.py`)
  eng geführt werden, sonst Gefahr eines zu großzügigen Skips (falsches PASS).
- **Scope-Grenze zum 500-Bug:** Der Radar-Debug-Trigger-500 (`user_id=default` evtl. nicht
  auf Staging vorhanden) bleibt außerhalb dieses Workflows — `test_issue_830_...`'s
  Prod-Call, der 401/404 erwartet, ist **kein** Bug und darf nicht "gefixt" werden.
- **Zwei Namensräume für dieselbe URL** (`GZ_SVELTE_BASE` vs. `GZ_VALIDATION_URL` vs.
  Literal) — der Helper sollte beide unterstützen, statt bestehende Tests umzubenennen
  (Scope-Disziplin, LoC-Limit).
- **Hartkodierte Test-User-Credentials** in mehreren Dateien (`test_issue_496_layout.py`,
  `test_issue_846_alert_preset_e2e.py` etc.) sind App-Login-Credentials, NICHT die
  nginx-Basic-Auth — beide Schichten sind unabhängig und müssen im Helper sauber getrennt
  bleiben (Basic-Auth zusätzlich, nicht anstelle des App-Logins).

## Analysis

### Type
Bug (3 verwandte, bereits gelabelte Bugs — Bündel H).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `tests/helpers/staging_auth.py` | CREATE | Zentraler Helper: liest `GZ_VALIDATOR_USER/PASS` aus `.claude/validator.env` (Fallback-Kette `GZ_VALIDATION_URL`/`GZ_SVELTE_BASE`), liefert httpx-Auth-Tupel + Playwright-`http_credentials`-Dict. Vorbild: bereits korrektes Muster in `tests/tdd/test_issue_1010_1006_stille_fehler.py:31-48` (trennt `_HTTP_CREDS` von `_APP_PASS`) |
| `frontend/playwright.staging.config.ts` | MODIFY | `httpCredentials` im `use`-Block ergänzen, 1:1 nach Vorbild `playwright.880.staging.config.ts` |
| `frontend/e2e/issue-661.staging.setup.ts` | MODIFY | `httpCredentials` zusätzlich im `newContext()`-Aufruf setzen (Vorbild: `feat-880.staging.setup.ts:9-17`) |
| `tests/tdd/test_issue_830_radar_alert_validator.py` | MODIFY | Helper-Auth für Staging-Calls ergänzen (Prod-Call bleibt unverändert — erwartet weiterhin 401/404) |
| `tests/tdd/test_issue_727_trips_null_safety.py` | MODIFY | Helper-Auth ergänzen |
| `tests/tdd/test_issue_496_layout.py` | MODIFY | Helper-Auth ergänzen (Playwright-Context) |
| `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py` | MODIFY | Helper-Auth ergänzen |
| `tests/tdd/test_issue_846_alert_preset_e2e.py` | MODIFY | Helper-Auth ergänzen (Playwright-Context) |
| `tests/tdd/test_issue_577_atoms_values.py` | MODIFY | Helper-Auth ergänzen (Playwright-Context) |
| `.claude/hooks/prod_selftest.py` | MODIFY | Neuer pfadbasierter Skip-Zweig vor `_staging_to_prod_url()` (Zeile ~159): Pfad-Muster `^/api/preview/[^/]+/email$` + Test-Trip-Erkennung (z.B. `-test`-Suffix) → neuer `prod_status="SKIPPED_PREVIEW_TEST_TRIP"`, eigenständig von `SKIPPED_NO_URL` |
| Neuer Regressionstest für `prod_selftest.py` | CREATE | Analog `test_prod_selftest_730.py`/`_564.py`: deckt sowohl den neuen Skip-Fall als auch ab, dass ein echter Prod-404 weiterhin PARTIAL bleibt (verhindert zu großzügigen Skip) |

### Scope Assessment
- Files: ~11 (1 neuer Helper, 1 neue Config-Änderung + 1 Setup-Script, 6 Testdateien, 1 Gate-Script, 1 neuer Regressionstest)
- Estimated LoC: Produktivcode ca. +100–150 (Helper ~40–60, prod_selftest.py ~15–25, Playwright-Config/Setup ~10–15, Testdatei-Migrationen ~30–50); Tests separat, unter dem 250-LoC-Limit
- Risk Level: MEDIUM (prod_selftest.py-Änderung ist Gate-Logik mit Einfluss auf Issue-Close-Entscheidungen — Hauptrisiko: zu weit gefasster Skip maskiert echte Defekte)

### Technical Approach
Reihenfolge: (1) zentraler Helper `tests/helpers/staging_auth.py` nach Vorbild `test_issue_1010_1006_stille_fehler.py` (beide Env-Var-Namen als Fallback, KEINE Migration der 19 Literal-Vorkommen), (2) #973 Playwright-Config + Setup-Script (1:1-Vorbild `playwright.880.staging.config.ts`), (3) #987-Testdateien auf Helper umstellen (minimal-invasiv: nur Auth-Parameter ergänzen), (4) #908 zuletzt — enger pfadbasierter Skip in `prod_selftest.py` (kein authentifizierter Prod-Probe-Versuch, da strukturell unmöglich ohne echten Prod-User/Trip) mit eigenem Regressionstest.

### Dependencies
- Upstream: `.claude/validator.env` (nur lesen, keine Änderung an der Sync-Kette)
- Downstream: `prod_selftest.py`-Verdict entscheidet über Issue-Close (Post-Deploy-Workflow) — Skip-Logik muss eng bleiben
- #973 und #987-Migration profitieren beide vom Helper aus Schritt 1, sind aber technisch unabhängig voneinander und von #908

### Open Questions
- [ ] Sollen `test_issue_339_verify_timing.py`, `test_epic_404_phase2_ist_screenshots.py`, `test_staging_gate.py`, `test_issue_776_metrics_toggle.py` (aus #987-Liste, aber ohne echten Live-Call) explizit als "nicht betroffen" im Issue vermerkt werden, oder reicht die Erwähnung im PR?
