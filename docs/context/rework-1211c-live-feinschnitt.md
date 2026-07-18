# Context: rework-1211c-live-feinschnitt

## Request Summary
Scheibe 2c von #1211 (Abschluss): Die alt-bestandenen modul-weiten `live`-Marker feinschneiden — beweisbar netzfreie UND grüne Tests zurück in die Standard-Selektion; danach ist jeder verbleibende live/email/staging-Marker semantisch echt (nur echte Anrufer bzw. Umgebungs-Abhängige).

## Messmethode (2026-07-18)
Netz-Sperre-Probe (in-process socket.connect-Patch, localhost erlaubt, `-o addopts=` zur Marker-Neutralisierung) über 13 subprozess-freie Kandidaten-Dateien. Ergebnis-Rohdaten: docs/artifacts/rework-1211c-live-feinschnitt/probe2c.xml + offline_rote_2c.json. 3 Dateien mit subprocess-Aufrufen (test_cli_wintersport, test_bug_338_openmeteo_call_counter, test_issue_338_go_geosphere_counter) NICHT ausgeführt (Subprozess dialt an Sperre vorbei) → Code-Inspektion.

## Probe-Ergebnis (142 Tests): 74 grün · 50 NETBLOCK (echte Dialer) · 18 offline-rot

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

**Nicht-Kandidaten (bleiben unverändert live, verifizierte Dialer):** test_account_page(+_extend), test_change_password, test_register_page, test_feature_770, test_stage_reorder, test_compare_provider_routing (#1301-Territorium), test_bug_338/test_issue_338 (je nach Teil-2-Inspektion).

## Rückhol-Regel (Kern-Prinzip der Scheibe)
NUR Tests, die unter der Netz-Sperre GRÜN waren, kommen zurück (Beweis Netzfreiheit + Funktion in einem). Umsetzung: modul-weiten `pytestmark`-live entfernen, stattdessen `@pytest.mark.live` test-/klassengenau auf die NETBLOCK-Dialer; offline-rote werden nach 2b-Mechanik behandelt (nie unmarkiert-rot zurück in den Kern).

## Risks & Considerations
- Ein zurückgeholter roter Test blockiert das Commit-Gate aller Sessions → Rückholung strikt nur Probe-grüne; Abschlussbeweis per erneuter Standard-Lauf-Messung der betroffenen Dateien.
- Parallel-Sessions (#1301 B4/C1 gepusht): vor Commit fetch+ff; test_compare_provider_routing nicht anfassen.
- e2e_story3: „e2e"-Pfad, prüfen ob tests/e2e/ überhaupt in Standard-Selektion collected wird (testpaths=tests → ja).
- Wächter-Erweiterung nach 2a/2b-Muster (Partitionsbeweis je teilgeschnittener Datei).

## Analysis
Detail-Triage der 18 offline-roten + 3 Subprozess-Dateien: läuft (Sonnet-Agent), Ergebnis wird hier ergänzt.

## Analysis (Detail-Triage, Sonnet-Agent, alle mit file:line + Beleg-Commit)

### Die 18 offline-Roten — Urteile
**LIVE-ABHÄNGIG → test-genau live-markieren (9):** metric_availability_probe beide (fail-soft probe_model_availability openmeteo.py:307-327) · uv_air_quality beide (fail-soft _fetch_uv_data :680-685) · story3 test_fetch_real_weather (SegmentWeatherSummary mit None-Feldern bei ProviderRequestError) · go_api_setup alle 4 (KEIN Server nötig — TestClient in-process; 502 = dokumentierte Fail-soft-Antwort des echten OpenMeteoProvider-Calls forecast.py:39-60).
**Format-/Fixture-Drift → minimal fixen (9, Verhalten weiterhin gültig, nur Soll-Strings/Fixtures stale):** multi_day_trend 4 (2× altes 2-Zeilen-Layout → #911-Tabellenformat, Commits 9f14fd39/2205639e; 2× `"Etappen" not in` strukturell unhaltbar durch #1241-Footer-Label → spezifischerer String) · story3 5 (segment_time_windows: Fixture nutzt entmachtetes Waypoint.time_window, #1004/cb39d05c; html/plain: „Summary"/„SEGMENTS" → „Metriken-Überblick", #790/#795; sms 2×: Legacy „E1:" → v2.0-Token, sms_trip.py-Docstring). Tech-Lead-Begründung fürs Fixen statt Löschen: Story-Level-E2E-Tests mit weiterhin gültiger Verhaltens-Erwartung — nur Soll-Strings driften (anders als die gelöschten issue-spezifischen Design-Tests aus 2b-K4).

### Subprozess-Dateien (Code-Inspektion)
- **test_cli_wintersport:** bleibt Modul-live — `--dry-run` verhindert NUR Versand, nicht den echten Provider-Fetch (cli.py:160-185); Subprozess erbt Env ohne Fixture-Pfad.
- **test_bug_338:** bleibt Modul-live (ac1-ac3 rufen Provider real; ac4 wäre offline-fähig, Feinschnitt nicht lohnend).
- **test_issue_338:** ac2 bleibt live; ac4 + call_log-Test offline → zurückholbar (2 Tests zusätzlich zu den 74). **ECHTER BEFUND: ac3 ist ein Vakuum-Test** — Subprozess `uv run pytest <datei> -q` OHNE Marker-Override → addopts deselektiert alle 6 Zieltests → Exit 5 (no tests collected) — Lauf verifizierte nichts (empirisch korrigiert, Adversary F002/F004). Fix in dieser Scheibe (Testfehler-Mechanik): `-o addopts=`-Override ergänzen.

### Umsetzungsplan
1. RED: Wächter um `_C2_RETURNED_FILES`-Partition erweitern (zurückgeholte Dateien müssen im Standard ≥N Tests zeigen, Dialer-Rest unter -m live; schlägt fehl solange Modul-Marker stehen).
2. 9 teilbare Dateien: Modul-`pytestmark`-live entfernen; `@pytest.mark.live` auf die per Probe/Code belegten Dialer (multi_day_trend 0 Dialer! · trip_segment_weather 4 · forecast_confidence 2 · openmeteo_endpoint_routing 2 · metric_availability_probe 2 · uv_air_quality 7 · story3 2 · go_api_setup 4 · snowgrid 3) + test_issue_338 (ac2 live, Rest zurück).
3. Die 9 Drift-Fixes (multi_day_trend 4, story3 5) minimal umstellen; ac3-Vakuum-Fix.
4. Abschluss: betroffene Dateien in Standard-Selektion unter Netz-Sperre ausführen → 0 failed; `-m live`-Collect zeigt die Dialer weiter.
**Unverändert:** snapshot_plausibility, geosphere_parsing, segment_weather_metrics, segment_weather_cache (100% Dialer) · cli_wintersport, bug_338 (Subprozess-live) · die 6 verifizierten Dialer-Dateien aus 2a/2b · compare_provider_routing (#1301).

### Scope Assessment
~12 Test-Dateien MODIFY + Wächter · Additions ~120-180 LoC · Risk MEDIUM (Rückholung nur Probe-grüner, Abschlussmessung als Hard-Beweis).

## Wächter-Wert-Korrekturen (Orchestrierer-Freigaben)

Zwei `min_standard`-Werte im Wächter (`_C2_SPLIT_FILES`,
tests/tdd/test_pytest_collection_and_timeout_safety.py) wurden nach der
initialen Umsetzung nach unten korrigiert. Beide Korrekturen sind vom
Orchestrierer im Adversary-Fix-Loop geprüft, begründet und freigegeben —
keine eigenmächtige Schwellen-Senkung durch den Developer-Agent:

- **test_e2e_story3_reports.py: 14 → 13.** `test_scheduler_send_reports`
  dialt nachweislich real (Live-Log-Beweis, fail-soft schluckt den
  Netzfehler intern und liefert trotzdem grün zurück) — der Test bleibt
  daher `email`+`live`, nicht Teil der Standard-Selektion.
- **test_metric_availability_probe.py: 7 → 5.** Adversary-Befund F001
  (Fix-Loop 1, 2026-07-18): `test_each_model_has_available_and_unavailable`
  und `test_cache_file_written_after_probe` riefen
  `probe_model_availability()` ungemockt auf — unter echter Netz-Sperre
  Timeout (tenacity-Retries) statt 0 failed/0 errors, offline strukturell
  vakuum (leeres `models`-Dict → 0 Iterationen, „grün" ohne jeden Beweis).
  Beide zusätzlich `@pytest.mark.live` markiert; `min_standard` entsprechend
  von 7 auf 5 korrigiert.

Der inhaltliche Maßstab bleibt in beiden Fällen unverändert: **nur belegte
Dialer/Vakuum-Tests bleiben draußen** — jede Korrektur ist durch einen
konkreten Beleg (Live-Log bzw. Adversary-Reproduktion) gedeckt, nicht durch
bloßes Absenken einer unbequemen Schwelle.
