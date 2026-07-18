---
entity_id: rework_1211a_staging_marker
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [testing, pytest, infrastructure, staging-marker]
---

<!-- Issue #1211 — Sammelprojekt #1196 (Test-Aufräum-Programm), Scheibe 2a von 3 (Scheibe 2b: Rot-Triage, Scheibe 2c: Live-Modul-Feinschnitt). Baut auf Scheibe 1 (#1210, Commit 1e30510b) auf. -->

# Testsuite Scheibe 2a — Staging-Dialer aus dem Kern nehmen (Issue #1211a)

## Approval

- [ ] Approved

## Purpose

22 Testdateien, die real gegen `https://staging.gregor20.henemm.com` (bzw. in
zwei Fällen Produktion) dialen, per modul-weitem `pytestmark =
pytest.mark.staging` aus der pytest-Standard-Selektion nehmen (`addopts = "-q
-m 'not email and not live and not staging'"`). Das macht den Kern-Lauf
netzfrei und ist Voraussetzung für die eigentliche Rot-Triage (Scheibe 2b) —
diese Scheibe erzeugt selbst keine grünen/roten Testergebnisse, sondern
verschiebt nur die Selektion. Der bestehende Kollektions-Wächter aus Scheibe 1
(`tests/tdd/test_pytest_collection_and_timeout_safety.py`) wird dafür
ERWEITERT, nicht nachgebaut.

## Source

> Test-Infrastruktur/Tooling — kein Frontend-, Go-API- oder Python-Core-Domain-Code
> betroffen.

- **File:** `tests/tdd/test_pytest_collection_and_timeout_safety.py` — der
  #1210-Kollektions-Wächter, wird um ein `_STAGING_DIALER_FILES`-Tupel und
  zusätzliche Wächter-Tests erweitert.
- **Files (Liste A — 22 Dateien, MODIFY: `pytestmark = pytest.mark.staging`
  auf Modulebene ergänzen):**

| Datei | Beleg (Dial) |
|---|---|
| `test_674_aktivitaetstyp_fahrrad.py` | `page.goto(f"{STAGING_BASE}/login")` :227 |
| `test_701_alerts_metrik_sync.py` | `page.goto(f"{BASE}/login")` :30 (alle 3 Tests) |
| `test_702_alerts_mobile_parity.py` | `page.goto(BASE, networkidle)` :48 |
| `test_794_mobile_metric_label.py` | `page.goto(f"{BASE}/login")` :82 |
| `test_bug_691_autosave_trip_new.py` | `page.goto(f"{STAGING_BASE}/trips/new")` :98 |
| `test_bundle_d_785_yesterday_toggle.py` | `page.goto` :51 + httpx put/get Staging |
| `test_bundle_h_908_973_987_staging_auth.py` | `httpx.get(f"{STAGING_BASE}/api/health")` :106 |
| `test_fix_698_validator_user_sync.py` | Subprozess `curl .../api/auth/register` (setup-validator-user.sh) :55 |
| `test_issue_1010_1006_stille_fehler.py` | `page.goto(f"{BASE}/login")` :81 — trägt bereits `pytestmark = pytest.mark.timeout(180)`; `staging` wird in eine Liste NEBEN diesem Marker ergänzt, nicht ersetzt |
| `test_issue_1020_tmp_cookie_perms.py` | importiert `_ensure_session_state` aus #727 → dialt :46,62 |
| `test_issue_1068_tier_model_display.py` | `httpx.post .../api/auth/register` :83 + Playwright :234 |
| `test_issue_496_layout.py` | `page.goto(f"{BASE}/login")` :38 |
| `test_issue_576_token_values.py` | `page.goto(f"{STAGING}/login")` :35 — Skip greift NICHT (validator.env liefert Creds) |
| `test_issue_577_atoms_values.py` | `page.goto(f"{STAGING}/login")` :44 — fragil, aktuell nur zufällig geskippt |
| `test_issue_675_stage_start_time.py` | `page.goto(f"{BASE}/login")` :28 — null Gating, hartkodierte Creds :19-20 |
| `test_issue_692_telegram_disabled_unconfigured.py` | `httpx.post .../api/auth/register` :54 |
| `test_issue_727_trips_null_safety.py` | `page.goto(BASE, networkidle)` :48 — null Gating, hartkodierte Creds :26-27 |
| `test_issue_830_radar_alert_validator.py` | `httpx.post(f"{STAGING_BASE}{TRIGGER}")` :58 (dialt zusätzlich Prod :359) |
| `test_issue_846_alert_preset_e2e.py` | `page.goto(BASE, networkidle)` :61 |
| `test_prod_selftest_564.py` | Subprozess `prod_selftest.py` → urllib GET gegen Prod :53 |
| `test_prod_selftest_730.py` | Subprozess `prod_selftest.py` → urllib GET gegen Prod :48 |
| `test_ssr_cache_headers.py` | `httpx.get(f"{BASE_URL}{path}")` :29 (Default BASE_URL=Staging :24) |

- **Files (Liste C — 6 Dateien, NICHT ANFASSEN, bleiben offline im Kern):**

| Datei | Grund (kein echter Netzcall) |
|---|---|
| `test_epic_404_phase2_ist_screenshots.py` | reiner Dateiinhalt-Check `assert URL in script` :114 |
| `test_prod_selftest_internal_url_skip.py` | `_http_get` per monkeypatch ersetzt :157,175 — Klassifikator-Tests offline |
| `test_staging_gate.py` | staging_gate.py importiert keine HTTP-Lib; nur git/FS-Subprozesse |
| `test_staging_gate_verdict_merge.py` | `write_verdict()` direkt, `_telegram_live_gate` per autouse auf No-Op gepatcht |
| `test_issue_1148_prod_send_gate.py` | URL nur als Text-Payload an lokalen Hook-Subprozess :179 (Regex-Analyse) |
| `test_issue_339_verify_timing.py` | `assert URL in markdown` :127 — Textprüfung |

- **Files (bereits effektiv aus dem Kern draußen — 5, NICHT ANFASSEN, nur
  verifizieren):**

| Datei | Grund |
|---|---|
| `test_issue_862_849_col_labels.py` | einziger HTTP-Test trägt per-Test `@pytest.mark.staging` :116 |
| `test_stage_reorder.py` | modul-weit `pytestmark = pytest.mark.live` :36 |
| `test_issue_783_startzeit.py` | doppelt gegatet: skipif GZ_STAGING_E2E + unbedingtes `pytest.skip()` :121 |
| `test_issue_1079_staging_telegram_webhook_401.py` | per-Test `skipif(not live_telegram_enabled())` — Opt-in GZ_TELEGRAM_LIVE |
| `test_issue_776_metrics_toggle.py` | skipif GZ_STAGING_E2E + Testkörper ist nur `pytest.skip()` |

- **File:** `tests/helpers/staging_auth.py` — Helfer-Modul (Dateiname ≠
  `test_*`, keine pytest-Collection), zentrale Login-Helfer für die meisten
  der 22 Dialer. Wird nicht verändert.

## Estimated Scope

- **LoC:** ~40–60 (Marker je 1–2 Zeilen in 22 Dateien + Wächter-Erweiterung)
- **Files:** 23 (22 Marker-Dateien + 1 Wächter-Erweiterung)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pyproject.toml` Marker-Registry (`email`/`live`/`staging`) | intern | Einzige addopts-wirksame Ausschlussmechanik für den Standardlauf; `staging` bereits registriert |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` (Scheibe 1) | intern | Bestehender Kollektions-Wächter, wird erweitert, nicht ersetzt |
| `tests/helpers/staging_auth.py` | intern | Login-Helfer, über den die meisten der 22 Dialer laufen |
| CLAUDE.md „Test-Politik: Zwei Schichten" (PO-go 2026-07-09) | Policy | Definiert Kern vs. Live-E2E; diese Scheibe stellt die Trennung für die Staging-Dialer mechanisch her |
| Issue #1210 / Scheibe 1 | GitHub Issue | Vorgänger-Scheibe (Live-Leck-Marker, Timeout-Netz), Commit `1e30510b` |
| Sammelprojekt #1196 | GitHub Issue | Übergeordnetes Test-Aufräum-Programm |
| Scheibe 2b / 2c (#1211 Folge) | GitHub Issue | Rot-Triage der zurückgeholten Tests bzw. Granular-Feinschnitt der teilbaren live-Module — beides explizit NICHT Teil dieser Scheibe |

## Implementation Details

```
1. Wächter erweitern (RED zuerst):
   - `_STAGING_DIALER_FILES` = die 22 Dateipfade aus Liste A.
   - Neuer Test `test_default_selection_excludes_staging_dialers`:
     `pytest --collect-only -q -m 'not email and not live and not staging'`
     als Subprozess, prüft 0 gesammelte Test-IDs je Datei aus der Liste.
     Schlägt zunächst fehl (Dateien noch ungemarkert im Kern).
   - Neuer Test `test_staging_marker_run_still_collects_dialers`:
     `pytest --collect-only -q -m staging`, prüft >=1 gesammelte Test-ID je
     Datei aus der Liste.
   - Neuer Test `test_offline_files_remain_in_default_selection`: Standard-
     Selektion sammelt weiterhin alle 6 Dateien aus Liste C (kein
     Coverage-Verlust durch Fehl-Markierung).

2. 22 Dateien aus Liste A: `pytestmark = pytest.mark.staging` auf
   Modulebene ergänzen. Ausnahme `test_issue_1010_1006_stille_fehler.py`:
   bestehender `pytestmark = pytest.mark.timeout(180)` wird zu einer Liste
   `pytestmark = [pytest.mark.timeout(180), pytest.mark.staging]` erweitert,
   NICHT ersetzt.

3. GREEN: alle drei Wächter-Tests grün — 22 Dateien deselektiert im
   Standardlauf, unter `-m staging` weiterhin sammelbar, Liste C unverändert
   im Kern.

4. Nachweis ausschließlich über `pytest --collect-only`-Subprozesse. Die 22
   Dialer werden zu keinem Zeitpunkt dieser Scheibe tatsächlich ausgeführt.
```

## Expected Behavior

- **Input:** `uv run pytest` (Standardlauf, keine expliziten Marker-Optionen)
  bzw. `uv run pytest -m staging` (expliziter Lauf)
- **Output:**
  - Standardlauf sammelt keine der 22 Dialer-Dateien mehr (0 Tests je Datei)
  - `-m staging` sammelt weiterhin alle 22 Dateien mit mindestens einem Test
    je Datei (Marker verschiebt, löscht nicht)
  - Die 6 Offline-Dateien aus Liste C bleiben unverändert im Standardlauf
  - `test_issue_1010_1006_stille_fehler.py` behält seinen `timeout(180)`-Marker
- **Side effects:** Keine — reine Marker-Verschiebung, kein Produktivcode
  betroffen, `addopts` selbst bleibt unverändert

## Acceptance Criteria

- **AC-1:** Given die pytest-Standard-Selektion `pytest --collect-only -q -m 'not email and not live and not staging'`, When sie die volle Suite sammelt, Then erscheint KEINE der 22 Dialer-Dateien aus Liste A mit einem gesammelten Test (jede deselektiert / 0 Tests).
  - Test: `test_default_selection_excludes_staging_dialers` — echter Subprozess-Collection-Lauf, zählt Test-IDs je Datei aus `_STAGING_DIALER_FILES`.

- **AC-2:** Given `pytest --collect-only -q -m staging`, When es läuft, Then erscheint jede der 22 Dateien aus Liste A mit mindestens einem gesammelten Test — der Marker verschiebt sie nur, löscht keinen Test.
  - Test: `test_staging_marker_run_still_collects_dialers` — echter Subprozess-Collection-Lauf mit `-m staging`, prüft >=1 Test-ID je Datei.

- **AC-3:** Given die 6 Offline-Kern-Dateien aus Liste C (test_epic_404_phase2_ist_screenshots.py, test_prod_selftest_internal_url_skip.py, test_staging_gate.py, test_staging_gate_verdict_merge.py, test_issue_1148_prod_send_gate.py, test_issue_339_verify_timing.py), When die Standard-Selektion sammelt, Then bleiben alle 6 weiterhin gesammelt — keine wird versehentlich mit-markiert (kein Coverage-Verlust).
  - Test: `test_offline_files_remain_in_default_selection` — echter Subprozess-Collection-Lauf, prüft >=1 Test-ID je Datei aus Liste C in der Standard-Selektion.

- **AC-4:** Given der Kollektions-Wächter test_pytest_collection_and_timeout_safety.py, When er ausgeführt wird, Then belegen neue Testfunktionen AC-1/AC-2/AC-3 ausschließlich über echte `pytest --collect-only`-Subprozesse (kein Mock, keine Dateiinhalt-Greps als Verhaltensnachweis).
  - Test: Code-Review der drei neuen Wächter-Tests — jeder ruft `subprocess.run(["uv","run","pytest","--collect-only",...], timeout=<N>)` auf und parst die Ausgabe auf Test-IDs, kein `Mock`/`patch`, kein `assert "..." in datei.read_text()`.

- **AC-5:** Given test_issue_1010_1006_stille_fehler.py trug vor der Änderung `pytestmark = pytest.mark.timeout(180)`, When der staging-Marker ergänzt wird, Then bleibt der timeout(180)-Marker erhalten (pytestmark ist danach eine Liste beider Marker) — der Hänger-Schutz geht nicht verloren.
  - Test: Diff-Prüfung der Datei + `pytest --collect-only -q -m 'timeout'`-artiger Introspektion (bzw. direkte Prüfung von `pytestmark` im Modul) zeigt beide Marker gleichzeitig aktiv.

## Known Limitations

- **Keine Rot-Triage:** Kein zurückgeholter oder verschobener Test wird hier
  "grün gemacht" — das ist explizit Scheibe 2b (#1211).
- **Kein Live-Modul-Feinschnitt:** Die 21 teilbaren `live`-Module (Scheibe 1,
  Known Limitations) und ihr Granular-Feinschnitt sind explizit Scheibe 2c,
  nicht Teil dieser Scheibe.
- **`addopts` bleibt unverändert:** Diese Scheibe verschiebt nur Tests
  zwischen Marker-Kategorien, senkt keine Test-Schwellen und lockert kein
  Gate.
- **Die 5 „schon draußen"-Dateien und die 6 Offline-Dateien werden NICHT
  angefasst** — sie sind bereits korrekt klassifiziert (siehe Source),
  Änderung würde nur Risiko ohne Nutzen erzeugen.
- **Die 22 Dialer werden NIE ausgeführt:** Der Nachweis dieser Scheibe läuft
  ausschließlich über `--collect-only`-Subprozesse; ein tatsächlicher Lauf der
  22 Dateien (mit echtem Netzzugriff auf Staging/Prod) ist nicht Teil des
  Testplans dieser Scheibe.
- **prod_selftest-Nuance:** `test_prod_selftest_564.py` und
  `test_prod_selftest_730.py` rufen technisch Produktion an, nicht Staging —
  siehe ADR unten für die bewusste Vereinheitlichungsentscheidung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Test-Infrastruktur-Konvention, keine
  produktseitige Architektur — analog Scheibe 1)
- **Rationale:** Alle 22 Dialer werden einheitlich mit `pytest.mark.staging`
  markiert — auch `test_prod_selftest_564.py` und `test_prod_selftest_730.py`,
  die technisch die Produktion anrufen statt Staging. Begründung: (a)
  funktional erreicht jeder der drei Exclude-Marker (`email`/`live`/`staging`)
  das gleiche Ziel — raus aus der Standard-Selektion; (b) Einheitlichkeit
  bedeutet, dass ein einziger Wächter-Mechanismus ("Marker verschiebt, löscht
  nicht") alle 22 Dateien gleichermaßen absichert, statt für zwei Dateien eine
  Sonderbehandlung mit `live` zu benötigen — weniger Fehlerquellen; (c)
  semantisch sind alle 22 Dateien "E2E gegen eine laufende deployte Umgebung",
  die prod/staging-Unterscheidung ist dafür nicht die relevante Achse.
  Verworfene Alternative: separater `live`-Marker nur für die 2
  prod_selftest-Dateien — verworfen wegen höherer Fehleranfälligkeit (zwei
  Ausschlussmechanismen für dieselbe Testklasse "Dialer", ohne fachlichen
  Mehrwert) und weil ein späterer HTTP-Seam-Refactor dieser beiden Meta-Tests
  ohnehin ein eigenständiger #1199-Nebeneintrag wäre, kein Blocker dieser
  Scheibe.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1211, Sammelprojekt #1196,
  Scheibe 2a (Scheibe 2b: Rot-Triage, Scheibe 2c: Live-Modul-Feinschnitt)
