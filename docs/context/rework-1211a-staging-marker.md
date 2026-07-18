# Context: rework-1211a-staging-marker

## Request Summary
Scheibe 2a von #1211 (Sammelprojekt #1196): Die ungemarkten Testdateien, die REAL gegen `https://staging.gregor20.henemm.com` (bzw. Produktion) dialen, aus der deterministischen Kern-Selektion nehmen, indem sie den addopts-wirksamen `staging`-Marker erhalten. Sichere Richtung (Tests raus aus dem Kern) — Voraussetzung für die eigentliche Rot-Triage (Scheibe 2b). Baut auf Scheibe 1 (#1210, `1e30510b`) auf.

## Klassifikation aller 34 Staging-referenzierenden Dateien (3 parallele Sonnet-Sweeps, 2026-07-18, alle mit Datei:Zeile belegt)

### A) MARKIEREN — 22 echte Netz-Dialer → `pytestmark = pytest.mark.staging`

| Datei | Beleg (Dial) |
|---|---|
| test_674_aktivitaetstyp_fahrrad.py | `page.goto(f"{STAGING_BASE}/login")` :227 |
| test_701_alerts_metrik_sync.py | `page.goto(f"{BASE}/login")` :30 (alle 3 Tests) |
| test_702_alerts_mobile_parity.py | `page.goto(BASE, networkidle)` :48 |
| test_794_mobile_metric_label.py | `page.goto(f"{BASE}/login")` :82 |
| test_bug_691_autosave_trip_new.py | `page.goto(f"{STAGING_BASE}/trips/new")` :98 |
| test_bundle_d_785_yesterday_toggle.py | `page.goto` :51 + httpx put/get Staging |
| test_bundle_h_908_973_987_staging_auth.py | `httpx.get(f"{STAGING_BASE}/api/health")` :106 |
| test_fix_698_validator_user_sync.py | Subprozess `curl .../api/auth/register` (setup-validator-user.sh) :55 |
| test_issue_1010_1006_stille_fehler.py | `page.goto(f"{BASE}/login")` :81 — **hat bereits `pytestmark = pytest.mark.timeout(180)`**, staging in Liste ergänzen |
| test_issue_1020_tmp_cookie_perms.py | importiert `_ensure_session_state` aus #727 → dialt :46,62 |
| test_issue_1068_tier_model_display.py | `httpx.post .../api/auth/register` :83 + Playwright :234 |
| test_issue_496_layout.py | `page.goto(f"{BASE}/login")` :38 |
| test_issue_576_token_values.py | `page.goto(f"{STAGING}/login")` :35 — Skip greift NICHT (validator.env liefert Creds) |
| test_issue_577_atoms_values.py | `page.goto(f"{STAGING}/login")` :44 — **fragil**: aktuell nur zufällig geskippt (GZ_AUTH_PASS leer), identischer ungegateter Code wie #576 → markieren |
| test_issue_675_stage_start_time.py | `page.goto(f"{BASE}/login")` :28 — **null Gating**, hartkodierte Creds :19-20 (der #1210-Beispielfall) |
| test_issue_692_telegram_disabled_unconfigured.py | `httpx.post .../api/auth/register` :54 |
| test_issue_727_trips_null_safety.py | `page.goto(BASE, networkidle)` :48 — null Gating, hartkodierte Creds :26-27 |
| test_issue_830_radar_alert_validator.py | `httpx.post(f"{STAGING_BASE}{TRIGGER}")` :58 (dialt zusätzlich Prod :359) |
| test_issue_846_alert_preset_e2e.py | `page.goto(BASE, networkidle)` :61 |
| test_prod_selftest_564.py | Subprozess `prod_selftest.py` → urllib GET gegen **Prod** :53 |
| test_prod_selftest_730.py | Subprozess `prod_selftest.py` → urllib GET gegen **Prod** :48 |
| test_ssr_cache_headers.py | `httpx.get(f"{BASE_URL}{path}")` :29 (Default BASE_URL=Staging :24) |

**Marker-Entscheidung (Tech-Lead):** Alle 22 einheitlich `staging`, auch die 2 prod_selftest-Dateien, die technisch die **Produktion** anrufen. Begründung: (a) funktional erreicht jeder der drei Exclude-Marker das Ziel (raus aus dem Kern); (b) Einheitlichkeit = ein `staging_collect`-Wächter deckt „Marker verschiebt, löscht nicht" für alle ab, weniger Fehlerquellen; (c) semantisch sind alle 22 „E2E gegen eine laufende deployte Umgebung". Die Prod-Nuance der 2 selftest-Dateien ist dokumentiert; ein späterer HTTP-Seam-Refactor dieser Meta-Tests wäre ein #1199-Nebeneintrag, nicht Teil dieser Scheibe.

### B) NICHT ANFASSEN — bereits effektiv aus dem Kern (5, nur verifizieren)

| Datei | Grund |
|---|---|
| test_issue_862_849_col_labels.py | einziger HTTP-Test trägt per-Test `@pytest.mark.staging` :116 |
| test_stage_reorder.py | modul-weit `pytestmark = pytest.mark.live` :36 |
| test_issue_783_startzeit.py | doppelt gegatet: skipif GZ_STAGING_E2E + unbedingtes `pytest.skip()` :121 |
| test_issue_1079_staging_telegram_webhook_401.py | per-Test `skipif(not live_telegram_enabled())` — Opt-in GZ_TELEGRAM_LIVE |
| test_issue_776_metrics_toggle.py | skipif GZ_STAGING_E2E + Testkörper ist nur `pytest.skip()` |

### C) NICHT ANFASSEN — bleibt zu Recht im Kern, offline (6)

| Datei | Grund (kein echter Netzcall) |
|---|---|
| test_epic_404_phase2_ist_screenshots.py | reiner Dateiinhalt-Check `assert URL in script` :114 |
| test_prod_selftest_internal_url_skip.py | `_http_get` per monkeypatch ersetzt :157,175 — Klassifikator-Tests offline |
| test_staging_gate.py | staging_gate.py importiert keine HTTP-Lib; nur git/FS-Subprozesse |
| test_staging_gate_verdict_merge.py | `write_verdict()` direkt, `_telegram_live_gate` per autouse auf No-Op gepatcht |
| test_issue_1148_prod_send_gate.py | URL nur als Text-Payload an lokalen Hook-Subprozess :179 (Regex-Analyse) |
| test_issue_339_verify_timing.py | `assert URL in markdown` :127 — Textprüfung |

### D) KEIN TEST GESAMMELT (1)
- `tests/helpers/staging_auth.py` — Helfer-Modul, Dateiname ≠ `test_*` → keine pytest-Collection.

**Summe: 22 markieren + 5 schon draußen + 6 offline im Kern + 1 Helfer = 34 ✓**

## Related Files
| File | Relevance |
|------|-----------|
| `pyproject.toml` `[tool.pytest.ini_options]` | `addopts = "-q -m 'not email and not live and not staging'"`; `timeout = 30`; Marker-Registry inkl. `staging` |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | **Der #1210-Kollektions-Wächter — wird ERWEITERT** (nicht nachgebaut): echte `--collect-only`-Subprozesse, Count-pro-Datei, „Marker verschiebt, löscht nicht"-Partition |
| `tests/helpers/staging_auth.py` | zentrale Staging-Login-Helfer (`httpx_auth`, `staging_base_url`, Playwright-Creds) — die meisten Dialer laufen hierüber |
| 22 Dateien (Liste A) | MODIFY: `pytestmark = pytest.mark.staging` (bei #1010_1006 in Liste mit vorhandenem timeout-Marker) |

## Existing Patterns
- **Marker auf Modulebene** (`pytestmark = pytest.mark.staging`), Standard-Selektion schließt aus. #1210-Präzedenz: modul-weit für Voll-Dialer, per-Test bei gemischten Dateien.
- **`timeout=15` an echten IMAP/SMTP/HTTP-Aufrufen** als Hänger-Schutz (Scheibe 1). Für die 22 Playwright/httpx-Dialer sekundär — der `staging`-Marker nimmt sie ohnehin aus dem Kern; das globale `timeout=30` bleibt Sicherheitsnetz.
- **Wächter erweitern statt neu:** neue `_STAGING_DIALER_FILES`-Tupel + Test „nicht im Standardlauf, aber unter `-m staging` sammelbar", analog zu `_B1_FILES`.

## Dependencies
- Upstream: pytest 8.4.1, Marker-Registry `pyproject.toml`, `--collect-only`-Subprozess-Muster.
- Downstream: **Commit-Gate aller Sessions** (die 22 Dialer verrauschen sonst jeden Kern-Lauf); Scheibe 2b (#1211) misst erst nach dieser Scheibe eine belastbare Rot-Liste.

## Existing Specs
- `docs/specs/modules/rework_1210_testsuite_s1.md` (Scheibe 1). Politik: CLAUDE.md „Test-Politik: Zwei Schichten".

## Risks & Considerations
- **Fehl-Markierung = stiller Test-Verlust:** Jede der 6 Offline-Dateien (Liste C) darf NICHT markiert werden — sie sind echter Kern-Coverage. Wächter beweist ihr Verbleib im Standardlauf.
- **Marker-Setzen ist die sichere Richtung** (kann kein neues Rot erzeugen); trotzdem gilt: Nachweis netzfrei nur via `--collect-only` (kein Ausführen der 22 Dialer!).
- **Parallel-Sessions:** a1/a2/a3-compare, fix-1268/1275/1300 fassen Compare-/SMS-Tests an — KEINE Überlappung mit den 22 UI-/E2E-Dateien. Vor Implementierung kurz gegenprüfen (Kollisionsvorsicht).
- **Import-Zeit netzfrei:** Alle Dials liegen in Funktionen/Fixtures, nicht auf Modul-Top-Level (stichprobenhaft verifiziert) → `--collect-only` dialt nicht.
- **prod_selftest-Nuance:** #564/#730 rufen Prod an; `staging`-Marker ist funktional korrekt (raus aus Kern), semantisch approximativ — dokumentiert, kein Blocker.
- **Kein Threshold-/Gate-Aufweichen:** `addopts` bleibt unverändert; nur Marker gesetzt + Wächter erweitert.

## Analysis (Standard Track — kombiniert)

### Type
Rework/Infrastruktur der Testsuite (kein Produktverhalten betroffen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| 22 Test-Dateien (Liste A) | MODIFY | `pytestmark = pytest.mark.staging` (Modulebene; bei #1010_1006 als Liste neben timeout-Marker) |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | MODIFY | `_STAGING_DIALER_FILES`-Tupel + 2 Wächter-Tests (default-exclude · `-m staging`-still-collects) + Offline-Verbleib-Assertion für Liste C |

### Scope Assessment
- Files: 23 (22 Marker + 1 Wächter) · Estimated LoC: +40–60 (Marker je 1–2 Zeilen + Wächter-Erweiterung). Generierte/Doku-Dateien zählen nicht.
- Risk Level: MEDIUM (größtes Risiko: eine Offline-Datei versehentlich mit-markieren → Coverage-Verlust; abgesichert durch Wächter-Verbleib-Assertion + explizite Liste-C-Nichtberührung).

### Technical Approach
1. Wächter erweitern (RED): `_STAGING_DIALER_FILES` = 22 Dateien; Test `test_default_selection_excludes_staging_dialers` schlägt fehl (Dateien noch im Kern).
2. `pytestmark = pytest.mark.staging` in die 22 Dateien (bei #1010_1006 Liste).
3. GREEN: Wächter grün — 22 deselektiert, unter `-m staging` sammelbar, Liste C bleibt im Kern.
4. Netzfreier Nachweis ausschließlich über `--collect-only`-Subprozesse; die 22 Dialer NIE ausführen.

### Open Questions
- [ ] Keine blockierenden. Marker-Vereinheitlichung (`staging` auch für prod_selftest) ist Tech-Lead-Entscheidung, über AC-Freigabe bestätigt.
