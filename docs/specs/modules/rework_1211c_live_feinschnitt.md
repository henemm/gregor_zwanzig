---
entity_id: rework_1211c_live_feinschnitt
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [testing, pytest, live-marker, testsuite]
---

<!-- Issue #1211 — Sammelprojekt #1196 (Test-Aufräum-Programm), Scheibe 2c von 3
     (Scheibe 2a: Staging-Marker, Commit 41eb5727, LIVE; Scheibe 2b: Rot-Triage,
     docs/specs/modules/rework_1211b_rot_triage.md, LIVE). Scheibe 2c ist der
     Abschluss: modul-weite live-Marker auf test-genaue Marker feinschneiden.
     Workflow: rework-1211c-live-feinschnitt. -->

# Testsuite Scheibe 2c — Live-Feinschnitt: modul-weite Live-Marker test-genau schneiden (Issue #1211c)

## Approval

- [ ] Approved

## Purpose

Die aus Scheibe 2a/2b geerbten modul-weiten `pytestmark = pytest.mark.live`
auf 13 subprozess-freien Kandidaten-Dateien werden per Netz-Sperre-Probe
(142 Tests) auf ihren tatsächlichen Dialer-Anteil vermessen: 74 Tests waren
unter Netz-Sperre grün und damit nachweislich netzfrei-lauffähig, kommen
aber wegen des groben Modul-Markers derzeit nicht in der Standard-Selektion
vor. Diese Scheibe schneidet die Marker test-/klassengenau auf die 50
tatsächlich dialenden Tests zurück, holt die 74 grünen (+2 aus
`test_issue_338`) in den Kern zurück, fixt 9 Format-/Fixture-Drift-Tests
minimal und behebt einen Vakuum-Test, der bislang immer grün meldete ohne
etwas zu prüfen. Danach ist jeder verbleibende `live`-Marker in den
betroffenen Dateien semantisch echt — nur noch echte Netzwerk-Anrufer.

## Source

> Reine Test-Infrastruktur, keine einzelne Produktionscode-Stelle (Ausnahme:
> die per Detail-Triage belegten Fail-soft-Fetch-Stellen in
> `src/providers/openmeteo.py` und `src/services/forecast.py`, die als
> Beleg für die live-Markierung zitiert werden, aber selbst nicht verändert
> werden).

- **File:** die 13 Kandidaten-Dateien aus der Netz-Sperre-Probe (siehe
  Betroffene-Dateien-Tabelle in Implementation Details, Quelle:
  `docs/artifacts/rework-1211c-live-feinschnitt/offline_rote_2c.json` +
  `docs/context/rework-1211c-live-feinschnitt.md`) sowie die Datei
  `tests/tdd/test_issue_338_go_geosphere_counter.py` (Marker-Feinschnitt +
  Vakuum-Test-Fix, Code-Inspektion statt Probe wegen Subprozess-Aufruf) und
  der Wächter `tests/tdd/test_pytest_collection_and_timeout_safety.py`.
- **Identifier:** pro teilbarer Datei — modul-weites `pytestmark =
  pytest.mark.live` entfernen, stattdessen `@pytest.mark.live`
  test-/klassengenau auf die per Probe/Code belegten Dialer setzen; in
  `test_issue_338_go_geosphere_counter.py` zusätzlich `test_ac3` (Vakuum-Test)
  per `-o addopts=`-Override reparieren; Wächter um die 2c-Partition
  erweitern.

## Estimated Scope

- **LoC:** Additions ~120–180 (Marker-Zeilen, Fixture-/Assertion-Fixes,
  Wächter-Erweiterung) — LoC-Limit-Riss nur mit expliziter PO-Erlaubnis
  überschreiten.
- **Files:** ~12 Dateien (9 teilbare Kandidaten-Dateien MODIFY +
  `test_issue_338_go_geosphere_counter.py` MODIFY + Wächter-Datei MODIFY +
  `docs/context/rework-1211c-live-feinschnitt.md` Status-Update).
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-1211c-live-feinschnitt.md` | intern | Single-Source-Messung, Probe-Tabelle, Detail-Triage, Umsetzungsplan dieser Scheibe |
| `docs/artifacts/rework-1211c-live-feinschnitt/offline_rote_2c.json` | intern | Rohdaten der 18 offline-roten Tests (Testname + Fehlersignatur je Datei) |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | intern | Kollektions-Wächter (Scheibe 1/2a/2b-Muster), wird um die 2c-Rückholungs-Partition erweitert |
| `docs/specs/modules/rework_1211b_rot_triage.md` | intern | Format-Vorbild dieser Spec; Marker-Muster (Modul- vs. Teil-Marker) aus Scheibe 2a/2b |
| CLAUDE.md „Test-Politik: Zwei Schichten" (PO-go 2026-07-09) | Policy | Kern muss netzfrei/deterministisch sein; Live-Schicht ist der bewusste Rest |
| CLAUDE.md „Nebenbefund-Triage" (PO-go 2026-07-09) | Policy | Falls bei Umsetzung neue echte Befunde auftauchen: Sammel-Eintrag #1199 statt neuem Issue, sofern nicht blockierend |
| Sammelprojekt #1196 / Issue #1211 | GitHub Issue | Übergeordnetes Test-Aufräum-Programm; Scheibe 2c ist dessen Abschluss |
| Scheibe 2a — Commit `41eb5727` | intern | Marker-Partitions-Muster für den Wächter (Vorbild für die 2c-Erweiterung) |
| #1301-Session | GitHub Issue / parallele Session | `test_compare_provider_routing.py` bleibt unberührt (Nicht-Kandidat, #1301-Territorium) |

## Implementation Details

### Betroffene Dateien — Probe-Ergebnis (142 Tests, Netz-Sperre in-process, 13 subprozess-freie Kandidaten-Dateien): 74 grün · 50 NETBLOCK (echte Dialer) · 18 offline-rot

| Datei | grün (zurückholbar) | NETBLOCK (bleibt live) | offline-rot (Triage) |
|---|---|---|---|
| tests/integration/test_snapshot_plausibility.py | 0 | 19 | 0 — **bleibt komplett live** ✓ |
| tests/tdd/test_geosphere_parsing.py | 0 | 7 | 0 — bleibt komplett live ✓ |
| tests/integration/test_segment_weather_metrics.py | 0 | 5 | 0 — bleibt komplett live ✓ |
| tests/integration/test_segment_weather_cache.py | 0 | 2 | 0 — bleibt komplett live ✓ |
| tests/integration/test_multi_day_trend.py | 17 | 0 | 4 |
| tests/integration/test_trip_segment_weather.py | 9 | 4 | 0 |
| tests/tdd/test_forecast_confidence_backend.py | 16 | 2 | 0 |
| tests/unit/test_openmeteo_endpoint_routing.py | 9 | 2 | 0 |
| tests/unit/test_metric_availability_probe.py | 7 | 0 | 2 |
| tests/unit/test_uv_air_quality.py | 1 | 5 | 2 |
| tests/e2e/test_e2e_story3_reports.py | 9 | 1 | 6 |
| tests/tdd/test_go_api_setup.py | 5 | 0 | 4 |
| tests/tdd/test_snowgrid.py | 1 | 3 | 0 |

**Nicht-Kandidaten (bleiben unverändert live, verifizierte Dialer):**
test_account_page(+_extend), test_change_password, test_register_page,
test_feature_770, test_stage_reorder, test_compare_provider_routing
(#1301-Territorium), test_bug_338/test_issue_338 (je nach
Teil-2-Inspektion).

### Rückhol-Regel (Kern-Prinzip der Scheibe)

NUR Tests, die unter der Netz-Sperre GRÜN waren, kommen zurück (Beweis
Netzfreiheit + Funktion in einem). Umsetzung: modul-weiten `pytestmark`-live
entfernen, stattdessen `@pytest.mark.live` test-/klassengenau auf die
NETBLOCK-Dialer; offline-rote werden nach 2b-Mechanik behandelt (nie
unmarkiert-rot zurück in den Kern).

### Detail-Triage der 18 offline-Roten — Urteile

**LIVE-ABHÄNGIG → test-genau live-markieren (9):** metric_availability_probe
beide (fail-soft `probe_model_availability` `openmeteo.py:307-327`) ·
uv_air_quality beide (fail-soft `_fetch_uv_data` `:680-685`) · story3
`test_fetch_real_weather` (SegmentWeatherSummary mit None-Feldern bei
ProviderRequestError) · go_api_setup alle 4 (KEIN Server nötig — TestClient
in-process; 502 = dokumentierte Fail-soft-Antwort des echten
OpenMeteoProvider-Calls `forecast.py:39-60`).

**Format-/Fixture-Drift → minimal fixen (9, Verhalten weiterhin gültig, nur
Soll-Strings/Fixtures stale):** multi_day_trend 4 (2× altes 2-Zeilen-Layout
→ #911-Tabellenformat, Commits `9f14fd39`/`2205639e`; 2× `"Etappen" not in`
strukturell unhaltbar durch #1241-Footer-Label → spezifischerer String) ·
story3 5 (`segment_time_windows`: Fixture nutzt entmachtetes
`Waypoint.time_window`, #1004/`cb39d05c`; html/plain: „Summary"/„SEGMENTS" →
„Metriken-Überblick", #790/#795; sms 2×: Legacy „E1:" → v2.0-Token,
`sms_trip.py`-Docstring). Tech-Lead-Begründung fürs Fixen statt Löschen:
Story-Level-E2E-Tests mit weiterhin gültiger Verhaltens-Erwartung — nur
Soll-Strings driften (anders als die gelöschten issue-spezifischen
Design-Tests aus 2b-K4).

### Subprozess-Dateien (Code-Inspektion, nicht per Probe messbar)

- **test_cli_wintersport:** bleibt Modul-live — `--dry-run` verhindert NUR
  Versand, nicht den echten Provider-Fetch (`cli.py:160-185`); Subprozess
  erbt Env ohne Fixture-Pfad.
- **test_bug_338:** bleibt Modul-live (ac1-ac3 rufen Provider real; ac4 wäre
  offline-fähig, Feinschnitt nicht lohnend).
- **test_issue_338:** ac2 bleibt live; ac4 + call_log-Test offline →
  zurückholbar (2 Tests zusätzlich zu den 74). **ECHTER BEFUND: ac3 ist ein
  Vakuum-Test** — Subprozess `uv run pytest <datei> -q` OHNE
  Marker-Override → addopts deselektiert alle 6 Zieltests → Exit 5 (no
  tests collected) — Zieltests wurden deselektiert, Lauf verifizierte
  nichts (empirisch verifiziert, Adversary F002 korrigiert). Fix in dieser
  Scheibe (Testfehler-Mechanik): `-o addopts=`-Override ergänzen; `test_ac3`
  selbst bleibt hinter dem live-Marker (Subprozess dialt unkontrolliert).

### Umsetzungsplan

```
1. RED: Wächter um `_C2_RETURNED_FILES`-Partition erweitern (zurückgeholte
   Dateien müssen im Standard ≥N Tests zeigen, Dialer-Rest unter -m live;
   schlägt fehl solange Modul-Marker stehen).
2. 9 teilbare Dateien: Modul-`pytestmark`-live entfernen; `@pytest.mark.live`
   auf die per Probe/Code belegten Dialer (multi_day_trend 0 Dialer! ·
   trip_segment_weather 4 · forecast_confidence 2 ·
   openmeteo_endpoint_routing 2 · metric_availability_probe 2 ·
   uv_air_quality 7 · story3 2 · go_api_setup 4 · snowgrid 3) +
   test_issue_338 (ac2 live, Rest zurück).
3. Die 9 Drift-Fixes (multi_day_trend 4, story3 5) minimal umstellen;
   ac3-Vakuum-Fix.
4. Abschluss: betroffene Dateien in Standard-Selektion unter Netz-Sperre
   ausführen → 0 failed; `-m live`-Collect zeigt die Dialer weiter.
Unverändert: snapshot_plausibility, geosphere_parsing,
segment_weather_metrics, segment_weather_cache (100% Dialer) ·
cli_wintersport, bug_338 (Subprozess-live) · die 6 verifizierten
Dialer-Dateien aus 2a/2b · compare_provider_routing (#1301).
```

## Expected Behavior

- **Input:** `uv run pytest` Standard-Selektion (netzfrei, in-process
  Netz-Sperre) für die 13 Kandidaten-Dateien + `test_issue_338`; separat
  `uv run pytest -m live --collect-only` über dieselben Dateien.
- **Output:** Standard-Lauf der betroffenen Dateien endet mit 0 failed / 0
  errors; die per Probe/Code belegten Dialer (50 NETBLOCK + 9
  live-abhängig + `test_issue_338::ac2`/`ac3`) sind aus der Standard-Selektion
  verschwunden, aber unter `-m live` weiterhin sammelbar.
- **Side effects:** 9 Dateien verlieren ihren Modul-Marker zugunsten
  test-/klassengenauer Marker; `test_issue_338_go_geosphere_counter.py`
  bekommt einen Marker-Override-Fix für den Vakuum-Test `test_ac3`; Wächter
  `test_pytest_collection_and_timeout_safety.py` um die 2c-Partition
  erweitert; Kontext-Doc als Status-Nachweis fortgeschrieben.

## Acceptance Criteria

- **AC-1:** Given die 76 per Netz-Sperre-Probe als grün+netzfrei belegten
  Tests (74 aus der Probe-Tabelle + ac4/call_log aus test_issue_338), When
  die Modul-live-Marker durch test-genaue Marker ersetzt sind, Then
  erscheinen diese Tests in der Standard-Selektion (`--collect-only`) und
  ein Standard-Ausführungslauf der betroffenen Dateien unter Netz-Sperre
  endet mit 0 failed / 0 errors.
  - Test: `pytest --collect-only` über die 10 betroffenen Dateien zeigt die
    76 Tests ohne `live`-Marker; anschließender Ausführungslauf derselben
    Dateien unter in-process Netz-Sperre liefert 0 failed / 0 errors.

- **AC-2:** Given die per NETBLOCK-Signatur bzw. Code-Beleg (fail-soft-Fetch)
  als Dialer/live-abhängig belegten Tests, When der Feinschnitt umgesetzt
  ist, Then tragen exakt diese Tests `@pytest.mark.live` (test-/klassengenau),
  sind unter `-m live` weiterhin sammelbar, und die 4 Voll-Dialer-Dateien
  (snapshot_plausibility, geosphere_parsing, segment_weather_metrics,
  segment_weather_cache) sowie cli_wintersport/bug_338 behalten ihren
  Modul-Marker unverändert.
  - Test: `pytest -m live --collect-only` zeigt genau die 59
    test-/klassengenau markierten Tests (50 NETBLOCK + 9 live-abhängig) plus
    `test_issue_338::ac2`/`ac3` sowie die unveränderten Modul-Marker-Dateien;
    Diff-Review bestätigt, dass die 4 Voll-Dialer-Dateien keine Marker-Zeile
    verändert haben.

- **AC-3:** Given die 9 Drift-roten Tests (multi_day_trend 4, e2e_story3 5),
  When sie minimal auf das aktuelle, per Beleg-Commit dokumentierte
  Soll-Format/Fixture-Modell umgestellt sind, Then sind sie im Standard-Lauf
  grün — ohne dass eine Verhaltens-Erwartung entfernt oder abgeschwächt
  wurde (nur Soll-Strings/Fixture-Mechanik nachgezogen).
  - Test: `uv run pytest tests/integration/test_multi_day_trend.py
    tests/e2e/test_e2e_story3_reports.py` netzfrei ausgeführt → 0 failed;
    Diff-Review zeigt ausschließlich Soll-String-/Fixture-Korrekturen, keine
    entfernten oder abgeschwächten Assertions.

- **AC-4:** Given der Vakuum-Test test_issue_338::test_ac3 (Subprozess
  deselektiert bisher alle Zieltests, Exit 5 (no tests collected) —
  Zieltests wurden deselektiert, Lauf verifizierte nichts), When er mit
  Marker-Override repariert ist, Then schlägt er nachweislich fehl, wenn ein
  Zieltest fehlschlägt (Negativ-Probe mit synthetisch rotem Zieltest), und
  bleibt selbst hinter dem live-Marker.
  - Test: Negativ-Probe — ein synthetisch rot gemachter Zieltest im
    Subprozess-Aufruf von `test_ac3` lässt `test_ac3` fehlschlagen (statt
    grün durchzulaufen); `test_ac3` selbst ist unter `-m live`, nicht in der
    Standard-Selektion, sammelbar.

- **AC-5:** Given der Kollektions-Wächter, When er um die 2c-Rückholungen
  erweitert ist, Then beweist er per Partitions-Mechanik (Standard +
  `-m live` == marker-neutraler Gesamt-Count) für jede teilgeschnittene
  Datei, dass kein Test verloren ging, und dass die zurückgeholten Dateien
  im Standard ≥ der erwarteten Testzahl zeigen.
  - Test: neue Testfunktionen in
    `test_pytest_collection_and_timeout_safety.py` — echte
    `pytest --collect-only`-Subprozesse je der 9 teilgeschnittenen Dateien +
    `test_issue_338`, Summe Standard + `-m live` gleicht dem
    marker-neutralen `--collect-only`-Gesamtcount (kein Mock, kein
    Dateiinhalt-Grep).

- **AC-6:** Given die Triage-Tabellen (Kontext-Doc + Spec), When die Scheibe
  schließt, Then ist jeder der 142 geprobten Tests + der 3
  Subprozess-Dateien-Tests genau einer Aktion zugeordnet (zurückgeholt /
  live-markiert / gefixt / unverändert-live) — kein Test verschwindet,
  keiner wird unbegründet zurückgeholt.
  - Test: Abgleich der finalen Datei-für-Datei-Zuordnung dieser Spec gegen
    `offline_rote_2c.json` + Kontext-Doc-Probe-Tabelle; jede Datei/jeder Test
    hat eine dokumentierte Aktion mit Begründung, keine Lücke.

## Known Limitations

- test_cli_wintersport/test_bug_338: Feinschnitt bewusst unterlassen
  (Subprozess-Live-Kopplung bzw. nicht lohnend) — bleiben Modul-live.
- test_compare_provider_routing: #1301-Territorium, unangetastet.
- Die 9 live-abhängigen Fail-soft-Tests bleiben Live-Schicht — kein Versuch,
  Fail-soft offline zu mocken (Test-Politik: kein Mock-Theater).
- LoC-Additions ~120-180; Limit-Riss → nur mit PO-Erlaubnis überschreiten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Test-Infrastruktur-Konvention, keine
  produktseitige Architektur — analog Scheibe 2a/2b)
- **Rationale:**
  1. Rückhol-Regel „nur Probe-grün unter Netz-Sperre" als Abnahme-Mechanik
     (Beweis Netzfreiheit + Funktion in einem Lauf). Verworfene Alternative:
     Code-Inspektion allein — hat in Scheibe 2b nachweislich geirrt (das
     734-Fehlurteil, ein per Inspektion als „lösbar" eingeschätzter Test
     erwies sich bei der Netz-Sperre-Probe als tatsächlicher Dialer). Die
     Probe ist damit der verbindliche Beweis, nicht die Einschätzung.
  2. Drift-Fixes statt Löschung für Story-Level-E2E-Tests (multi_day_trend,
     e2e_story3): Begründung im Kontext-Doc — diese Tests prüfen weiterhin
     gültiges Verhalten, nur die Soll-Strings/Fixtures sind veraltet. Das
     weicht bewusst vom 2b-K4-Löschmuster ab, das dort für
     issue-spezifische Design-Tests galt, deren Testobjekt selbst entfernt
     war (nicht der Fall hier — das geprüfte Verhalten existiert
     unverändert).

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1211, Sammelprojekt #1196,
  Scheibe 2c (Live-Feinschnitt), Abschluss nach Scheibe 2a (Commit
  `41eb5727`) und Scheibe 2b (`docs/specs/modules/rework_1211b_rot_triage.md`)
