---
entity_id: fix_908_973_987_staging_auth
type: bugfix
created: 2026-07-05
updated: 2026-07-05
status: draft
version: "1.0"
tags: [tooling, testing, staging, auth, prod-selftest, playwright]
---

<!-- Issues #908, #973, #987 — Bündel H: Staging-Basic-Auth-Nachrüstung -->

# Fix #908/#973/#987 — Staging-Basic-Auth-Nachrüstung für Test-/Gate-Infrastruktur

## Approval

- [x] Approved (2026-07-05)

## Purpose

Seit dem nginx-Basic-Auth-Rollout auf Staging (henemm-infra #159, 28.06.2026)
schlagen diverse Test- und Gate-Läufe gegen `https://staging.gregor20.henemm.com`
strukturell mit 401 fehl, weil weder die betroffenen Testdateien noch die
Playwright-Staging-Config noch `prod_selftest.py`'s Prod-Probe Basic-Auth-
Credentials mitsenden. Diese Spec bündelt drei zusammenhängende Fixes:
ein zentraler Auth-Helper (#987-Kern), die Playwright-Staging-Config (#973)
und ein enger, pfadbasierter Skip für eine strukturell unmögliche Prod-Probe
in `prod_selftest.py` (#908). Der 500-Bug am Radar-Debug-Trigger (Teil der
ursprünglichen #987-Beschreibung) ist **bewusst nicht Teil** dieser Spec —
potenziell eigener Produkt-Bug, separat zu analysieren.

## Source

- **File:** `tests/helpers/staging_auth.py` (NEU, ~40–60 LoC) — zentraler Helper für httpx- und Playwright-Basic-Auth-Credentials
- **File:** `.claude/hooks/prod_selftest.py` — `_probe_ac()` (Zeilen 142–191), `_URL_SENTINELS` (Zeile 51), `_staging_to_prod_url()` (Zeilen 83–89), `_derive_verdict()` (Zeilen 338–352)
- **File:** `frontend/playwright.staging.config.ts` (21 Zeilen) — fehlendes `httpCredentials`
- **File:** `frontend/e2e/issue-661.staging.setup.ts` — fehlendes `httpCredentials` im `newContext()`-Aufruf
- **Identifier:** `tests/helpers/staging_auth.py::load_staging_auth()` (neu)

> **Schicht-Hinweis:** Reine Test-/Tooling-Infrastruktur (`tests/`, `.claude/hooks/`,
> `frontend/*.config.ts`, `frontend/e2e/*.setup.ts`) — keine produktseitige Backend-
> oder Frontend-Entity betroffen.

## Estimated Scope

- **LoC:** ~100–150 (Helper ~40–60, `prod_selftest.py` ~15–25, Playwright-Config/Setup ~10–15, Testdatei-Migrationen ~30–50); Tests separat unter dem 250-LoC-Limit
- **Files:** ~11 (1 neuer Helper, 1 Config + 1 Setup-Script, 6 Testdateien, 1 Gate-Script, 1 neuer Regressionstest)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/validator.env` (Hauptrepo, gitignored) | Upstream (nur lesend) | Single Source of Truth für `GZ_VALIDATOR_USER`/`GZ_VALIDATOR_PASS`/`GZ_VALIDATION_URL`, synchronisiert von `henemm-infra/scripts/sync-staging-validator-creds.sh` aus `/etc/henemm/secrets.env` — wir ändern die Sync-Kette nicht |
| `prod_selftest.py`-Verdict | Downstream | Entscheidet laut Post-Deploy-Workflow (`docs/reference/operations_playbook.md`) über die Issue-Close-Freigabe — Änderungen an der Skip-Logik wirken direkt auf das Deploy-Gate |
| `frontend/playwright.880.staging.config.ts` / `.953.staging.config.ts` | Vorbild | Bereits funktionierendes `httpCredentials`-Muster (`GZ_VALIDATOR_USER`/`PASS`, Fallback `E2E_USER`/`E2E_PASS`) |
| `tests/tdd/test_issue_1010_1006_stille_fehler.py:31-48` | Vorbild | Bestehendes, sauber getrenntes Muster: `_load_validator_env()` liest `.claude/validator.env`, trennt `_HTTP_CREDS` (Nginx-Basic-Auth) von `_APP_PASS` (App-Login) |
| `staging-validator`-Agent, `/e2e-verify` | Nutzer | Beide verwenden Playwright-Staging-Configs mit `httpCredentials` |

## Implementation Details

### 1. Zentraler Helper `tests/helpers/staging_auth.py`

Bisher existiert kein `tests/helpers/`-Ordner und kein zentrales Python-Loader-
Modul für `validator.env` — das Parser-Pattern ist dupliziert in
`.claude/hooks/design_fidelity_diff.py:144-153` und
`tests/tdd/test_794_mobile_metric_label.py:26-40`, und noch einmal (bereits
korrekt getrennt in Basic-Auth vs. App-Login) in
`tests/tdd/test_issue_1010_1006_stille_fehler.py:31-48`. Der neue Helper
konsolidiert dieses Muster an einer Stelle:

```python
"""tests/helpers/staging_auth.py — zentraler Staging-Basic-Auth-Helper.

Liefert Nginx-Basic-Auth-Credentials für Staging aus .claude/validator.env,
getrennt von App-Login-Credentials (siehe test_issue_1010_1006_stille_fehler.py).
Kein Mock — echte Datei, echte Werte für echte HTTP-Calls.
"""
from __future__ import annotations

from pathlib import Path

_VALIDATOR_ENV = Path("/home/hem/gregor_zwanzig/.claude/validator.env")


def _load_validator_env() -> dict:
    env = {}
    for line in _VALIDATOR_ENV.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def staging_base_url() -> str:
    """Fallback-Kette: GZ_VALIDATION_URL -> GZ_SVELTE_BASE -> Literal-Default.

    Beide Env-Var-Namen bleiben im Repo bestehen (Konsolidierung aller 19+
    Vorkommen ist bewusst NICHT Teil dieses Fixes — Scope-Disziplin)."""
    import os
    env = _load_validator_env()
    return (
        os.environ.get("GZ_VALIDATION_URL")
        or os.environ.get("GZ_SVELTE_BASE")
        or env.get("GZ_VALIDATION_URL")
        or "https://staging.gregor20.henemm.com"
    )


def httpx_auth() -> tuple[str, str]:
    """Basic-Auth-Tupel für httpx.get(url, auth=httpx_auth())."""
    env = _load_validator_env()
    return (env["GZ_VALIDATOR_USER"], env["GZ_VALIDATOR_PASS"])


def playwright_http_credentials() -> dict:
    """Dict für playwright.request.newContext(http_credentials=...) bzw.
    httpCredentials im Playwright-Config (TS-seitig äquivalent per process.env)."""
    user, password = httpx_auth()
    return {"username": user, "password": password}
```

### 2. `frontend/playwright.staging.config.ts` — `httpCredentials` ergänzen

1:1 nach Vorbild `playwright.880.staging.config.ts`:

```ts
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	// ... projects unverändert
});
```

`frontend/e2e/issue-661.staging.setup.ts` bekommt analog zu
`feat-880.staging.setup.ts:9-17` `httpCredentials` im
`playwright.request.newContext()`-Aufruf, zusätzlich zum bestehenden
App-Login (`/api/auth/login`) — beide Schichten bleiben unabhängig.

### 3. Sechs Testdateien aus #987 auf den Helper umstellen

Minimal-invasiv: nur die Auth-Parameter ergänzen, bestehende App-Login-Logik
bleibt unverändert.

- `tests/tdd/test_issue_830_radar_alert_validator.py` — httpx-Calls gegen
  `STAGING_BASE` (Zeilen 54, 77) bekommen `auth=httpx_auth()`. Der Prod-Call
  (Zeile 352), der bewusst 401/404 erwartet, bleibt **unverändert** — das ist
  kein Bug, sondern erwartetes Verhalten außerhalb dieses Scopes.
- `tests/tdd/test_issue_727_trips_null_safety.py`
- `tests/tdd/test_issue_496_layout.py`
- `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`
- `tests/tdd/test_issue_846_alert_preset_e2e.py`
- `tests/tdd/test_issue_577_atoms_values.py`

Die letzten vier nutzen Playwright — dort wird `playwright_http_credentials()`
in den jeweiligen `browser.new_context(...)`- bzw.
`playwright.request.newContext(...)`-Aufruf eingespeist.

### 4. `prod_selftest.py` — enger pfadbasierter Skip (#908)

`_probe_ac()` (Zeile ~159, vor `_staging_to_prod_url()`) bekommt einen neuen
Zweig, der **ausschließlich** greift, wenn (a) der Pfad dem Muster
`^/api/preview/[^/]+/email$` entspricht **und** (b) der Trip-Bezeichner ein
bekanntes Staging-Test-Trip-Suffix trägt (z.B. `-test`). Nur dann wird die
Probe als `SKIPPED_PREVIEW_TEST_TRIP` markiert — analog zum bestehenden
`SKIPPED_NO_URL`-Muster (Zeilen 155–160), aber mit eigenem Status-String,
damit die beiden Fälle im Bericht unterscheidbar bleiben:

```python
import re

_PREVIEW_EMAIL_PATH = re.compile(r"^/api/preview/[^/]+/email$")
_TEST_TRIP_SUFFIX = ("-test", "-tdd", "-adv-test")  # bekannte Staging-Test-Trip-Marker

def _is_staging_test_trip_preview(raw_url: str) -> bool:
    parsed = urlparse(_strip_ac_suffix(raw_url))
    if not _PREVIEW_EMAIL_PATH.match(parsed.path or ""):
        return False
    trip_id = parsed.path.split("/")[3]  # /api/preview/{trip}/email
    return trip_id.endswith(_TEST_TRIP_SUFFIX)
```

In `_probe_ac()`, **vor** dem generischen `_staging_to_prod_url()`-Aufruf:

```python
if _is_staging_test_trip_preview(raw_url):
    return {
        **finding,
        "prod_url": "",
        "prod_http": "—",
        "prod_status": "SKIPPED_PREVIEW_TEST_TRIP",
    }
```

Wichtig für `_derive_verdict()` (Zeilen 338–352): `SKIPPED_PREVIEW_TEST_TRIP`
zählt (wie `SKIPPED_NO_URL`) **nicht** als `"FAIL"` in
`[p for p in pass_probes if p.get("prod_status") == "FAIL"]` — der Skip
verhindert also PARTIAL, ohne die Verdict-Logik selbst anzufassen.

**Regressionsschutz (Kernrisiko dieser Änderung):** Ein echter Prod-404 bei
einem Preview-Pfad, der **nicht** auf ein Test-Trip-Suffix endet, muss
weiterhin `PASS: FAIL` bzw. Gesamtverdict `PARTIAL` auslösen — der neue
Regressionstest deckt exakt diese Abgrenzung ab (siehe AC-4).

## Expected Behavior

- **Input:** Staging-Basic-Auth-geschützte URL (Nginx, henemm-infra #159); Test-/Gate-Läufe, die bisher ohne Credentials gegen Staging liefen
- **Output:** Helper liefert korrekte Credentials aus `.claude/validator.env`; Playwright-Staging-Config + betroffene Testdateien authentifizieren sich; `prod_selftest.py` markiert die strukturell unprobbare Mail-Preview-Prod-Probe als eigenständigen Skip statt PARTIAL
- **Side effects:** Keine Änderung an der Credential-Sync-Kette (`henemm-infra`); keine Migration der bestehenden 19+ hartkodierten `GZ_SVELTE_BASE`/Literal-URL-Vorkommen (bewusst außerhalb des Scopes)

## Acceptance Criteria

- **AC-1:** Given `.claude/validator.env` enthält gültige `GZ_VALIDATOR_USER`/`GZ_VALIDATOR_PASS` (mit Fallback-Kette `GZ_VALIDATION_URL`/`GZ_SVELTE_BASE` für die Basis-URL) / When ein Test einen echten HTTP-Call gegen Staging mit den von `tests/helpers/staging_auth.py` gelieferten Credentials macht / Then liefert der Call HTTP 200 statt 401 (kein Mock — echter HTTP-Call gegen die reale Staging-Instanz, siehe CLAUDE.md "KEINE MOCKED TESTS")

- **AC-2:** Given `frontend/playwright.staging.config.ts` und `frontend/e2e/issue-661.staging.setup.ts` senden `httpCredentials` aus den Validator-Env-Werten / When `npx playwright test --config=playwright.staging.config.ts` direkt gegen Staging ausgeführt wird / Then schlägt das `setup`-Project nicht mehr mit HTTP 401 fehl

- **AC-3:** Given die 6 betroffenen Testdateien (`test_issue_830_radar_alert_validator`, `test_issue_727_trips_null_safety`, `test_issue_496_layout`, `test_issue_692_telegram_disabled_unconfigured`, `test_issue_846_alert_preset_e2e`, `test_issue_577_atoms_values`) nutzen den zentralen Helper / When sie gegen Staging ausgeführt werden / Then laufen sie ohne 401-Fehler durch, während die bestehende App-Login-Logik unverändert zusätzlich funktioniert (Basic-Auth kommt on top, ersetzt nicht den App-Login)

- **AC-4:** Given `prod_selftest.py` prüft ein Finding mit Preview-Pfad-Muster `/api/preview/{trip}/email` und einem erkannten Staging-Test-Trip-Suffix / When das Script läuft / Then wird dieses Finding als `SKIPPED_PREVIEW_TEST_TRIP` markiert und fließt NICHT als PARTIAL/FAIL ins Gesamtverdict ein — UND ein echter Prod-404 bei einem Preview-Pfad OHNE Test-Trip-Suffix bleibt weiterhin PARTIAL/FAIL (Regressionsschutz gegen einen zu großzügigen Skip, der echte Defekte maskieren würde)

## Known Limitations

- Vier der ursprünglich in #987 genannten Testdateien
  (`test_issue_339_verify_timing.py`, `test_epic_404_phase2_ist_screenshots.py`,
  `test_staging_gate.py`, `test_issue_776_metrics_toggle.py`) machen **keinen**
  echten Live-HTTP-Call zur Laufzeit gegen Staging (bzw. sind bereits per
  Skip-Marker geschützt) — sie sind **nicht** Teil dieser Spec und werden nicht
  angefasst.
- Der 500-Fehler am Radar-Debug-Trigger (potenziell `user_id=default` nicht auf
  Staging vorhanden) bleibt **außerhalb** dieses Fixes — separater, potenziell
  eigener Produkt-Bug, nicht Teil von Bündel H.
- Die bestehende Doppel-Namensraum-Situation (`GZ_SVELTE_BASE` in 9 Dateien vs.
  `GZ_VALIDATION_URL` in 3 Dateien vs. 19+ Dateien mit hartkodiertem Literal
  `"https://staging.gregor20.henemm.com"`) wird durch den Helper nicht bereinigt
  — er unterstützt beide Namen als Fallback, ohne die bestehenden Vorkommen zu
  migrieren (Scope-Disziplin, LoC-Limit).
- Der neue Skip-Zweig in `prod_selftest.py` erkennt Test-Trips ausschließlich
  über Namens-Suffixe (`-test`, `-tdd`, `-adv-test`); ein Staging-Test-Trip mit
  abweichender Namenskonvention würde nicht erkannt und liefe weiterhin in die
  reguläre (potenziell PARTIAL-auslösende) Probe — akzeptables Risiko, da neue
  Test-Trip-Namen unter Kontrolle des Teams stehen.
- **Nachträglich entdeckte Credential-Schicht-Verwechslung (Adversary-Findings
  F001/F002, nach ursprünglicher Freigabe):** `GZ_VALIDATOR_USER`/`PASS` sind
  die (alle paar Minuten rotierenden) Nginx-Basic-Auth-Credentials — sie
  gehören ausschließlich in `httpCredentials`. Der App-Login
  (`/api/auth/login` bzw. das `/login`-Formular) braucht das davon **unabhängige,
  stabile** Konto `GZ_AUTH_USER`/`GZ_AUTH_PASS` (aus
  `gregor_zwanzig_staging/.env`, etabliertes Muster in
  `tests/tdd/test_account_page.py:28-30`). Drei Dateien verwendeten
  fälschlich die Validator-Creds auch für den App-Login und wurden
  nachträglich korrigiert: `frontend/e2e/issue-661.staging.setup.ts` (Login-
  Body, `httpCredentials` bleibt bei den Validator-Creds),
  `tests/tdd/test_issue_496_layout.py` (`USER`/`PASS`-Konstanten),
  `tests/tdd/test_issue_577_atoms_values.py` (`USER`/`PASS`-Konstanten). Dies
  war zum Zeitpunkt der ursprünglichen PO-Freigabe nicht bekannt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-/Tooling-Infrastruktur-Konsolidierung (Auth-Helper,
  Playwright-Config, Gate-Skip-Logik) ohne Produktarchitektur-Impact. Die
  ADR-Guard-Entscheidungsflächen-Patterns (`.claude/hooks/adr_guard.py`,
  `DEFAULT_DECISION_SURFACE_PATTERNS`) greifen hier nicht: `prod_selftest.py`
  matcht nicht `.*_(gate|guard)\.py$`, und `tests/`, `frontend/*.config.ts`
  sowie `frontend/e2e/*.setup.ts` sind keine gelisteten Entscheidungsflächen
  (`src/outputs/`, `src/output/renderers/`, `src/providers/`, `src/*metric*`,
  `docs/reference/decision_matrix.md`). Commit trotzdem mit `[no-adr]` markieren,
  um den Guard nicht unnötig zu triggern, falls sich Pattern-Overlap ergibt.

## Changelog

- 2026-07-05: Initial spec erstellt — Issues #908, #973, #987 (Bündel H)
