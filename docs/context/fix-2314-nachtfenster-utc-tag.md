# Context: fix-2314-nachtfenster-utc-tag

## Request Summary
Zweiter Durchgang zu #2314. Der erste Fix (PR #2329, `tests/helpers/ortstag.py`) hat das Teilfenster
22:00–24:00 UTC geheilt. Der AC-9-Nachtlauf am 15.09. um 00:20 UTC (Run `34912773403`, Job `test`
`104203730792`, `main` @ `4188195a`) war trotzdem rot: **60 failed**, Schnittmenge mit den alten 144 = 0.
Ziel: `test` ist im gesamten Nachtfenster grün, und **beide** Teilfenster sind lokal nachstellbar.

## Zwei Teilfenster, zwei Mechanismen
Prozesszone in Tests: `America/St_Johns` (Root-`conftest.py:23`, #1402, Sommer UTC−2:30).
Trip-Koordinaten überwiegend Europa (UTC+2).

| Fenster (UTC) | Prozesstag (`date.today()`) | UTC-Tag | Ortstag Europa | Stand |
|---|---|---|---|---|
| 22:00–24:00 | heute | heute | **morgen** | PR #2329 behoben |
| 00:00–02:30 | **gestern** | heute | heute | **60 rot, dieser Workflow** |
| 02:30–22:00 | heute | heute | heute | grün |

## Warum der erste Durchgang das Fenster 00:00–02:30 nicht sah (Messwerkzeug-Lücke)
Der Uhr-Schalter `GZ_TEST_WALL_CLOCK_UTC` (`tests/conftest.py` Session-Fixture `_gestellte_wanduhr`,
Anker aus `tests/helpers/wanduhr.py`) ruft `freeze_time(anker, tick=True)` **ohne `tz_offset`**.
freezegun 1.5.5: `FakeDate.today() = _date_to_freeze() + _tz_offset()` → mit Offset 0 liefert
`date.today()` den **UTC-Tag**, nicht den Tag der Prozesszone. Die reale Situation „Prozesstag ≠ UTC-Tag"
ist mit dem Schalter damit **strukturell nicht herstellbar**. `fake_localtime` dagegen verschiebt um
`time.timezone` (Prozesszone) → innerhalb eines gestellten Laufs sind `date.today()` und
`time.localtime()` untereinander inkonsistent.
In der CI-Historie (400 Läufe seit 18.08.) lag kein einziger Lauf im Fenster 00:00–03:00 UTC.

## Die 60 Fehlschläge (Übersicht: Scratchpad `nacht_failures.txt`)
| Datei | rot | Symptom (Kurzform) |
|---|---|---|
| tests/tdd/test_strecke_km_argument.py | 9 | ValueError aus Fixture-Helfer „Ortsminute 30 … VERGANGENHEIT nicht darstellbar" |
| tests/tdd/test_starkregen_kurzfristhinweis.py | 8 | „Voraussetzung: es wurde keine Briefing-Mail gebaut" |
| tests/tdd/test_official_alert_cooldown_entkopplung.py | 7 | amtlicher Alarm nicht erkannt (`0 == 1`) |
| tests/tdd/test_nowcast_briefing_overtake.py | 6 | Sperre greift nicht (count=1 statt 0) |
| tests/tdd/test_briefing_anchor_survives_dispatch_failure.py | 6 | datierter Snapshot/Anker fehlt, „Tour muss heute Abschnitte haben" |
| tests/unit/test_forecast_budget_gate.py | 4 | Budget-Drossel greift nicht (Zählerdatei mit `date.today()`, Produkt liest UTC-Tag `forecast_budget.py:123`) |
| tests/tdd/test_ausblick_schleife_bewahrt_alle_nachgeruesteten_kilometrierungen.py | 2 | `no_weather` / Ausblick unvollständig |
| tests/tdd/test_compare_outlook_day_boundary.py | 2 | Stundentabelle zeigt falschen Kalendertag |
| tests/tdd/test_issue_883_acute_danger_override.py | 2 | Alarm-Unterdrückung falsch |
| tests/tdd/test_radar_nowcast_health_journal.py | 2 | Drosselung löst HTTP aus |
| tests/tdd/test_thunder_next_day_reference_by_report_type.py | 2 | „morning-Zieltag muss heute sein" |
| tests/unit/test_meteoalarm_budget_gate.py | 2 | Budget-Zähler 0 statt 50 |
| tests/tdd/test_alarm_szenario_laufendes_ereignis.py | 1 | keine Briefing-Mail gebaut |
| tests/tdd/test_alert_etappen_praefix_kurzform.py | 1 | Radar-Alarm 0 statt 1 |
| tests/tdd/test_compare_outlook.py | 1 | `hourly_data` leer |
| tests/tdd/test_issue_818_radar_briefing_integration.py | 1 | Grund `delivery_failed` statt `event_duplicate` |
| tests/tdd/test_stage_weather_endpoint.py | 1 | fail-soft liefert None |
| tests/unit/test_comparison_engine_no_circular_import.py | 1 | CLOUD_LOW_AVG engine=None (frischer Interpreter!) |
| tests/unit/test_radar_budget_and_priority.py | 1 | Drosselung löst HTTP aus |
| tests/unit/test_radar_upstream_failure.py | 1 | Drosselung löst HTTP aus |

Dieselben Tests sind im Tagfenster grün (Push-Lauf `34882372601`, 18:41 UTC, gleicher Commit).

## Analysis

### Type
Bug (Test-Infrastruktur). **Produkt in allen 60 Fällen korrekt** — drei unabhängige Analyse-Agenten; `date.today()` in den verdächtigten Produktdateien steht ausschließlich in Kommentaren/Docstrings. Einziger echter Produkt-Nebenbefund: `src/providers/openmeteo.py:325,349` (`date.today()` für Availability-Cache-TTL) und `:1031` (naives `datetime.now()` in totem Zweig) — nicht Ursache, Prod läuft `Etc/UTC` → Sammel-Issue #1199.

### Vier Fehlerfamilien
| Familie | Tests | Mechanismus | Stellen | Richtiger Tag |
|---|---|---|---|---|
| A Zählerdatei | 10 | Test schreibt Budget-Zähler mit Prozesstag, Produkt liest UTC-Tag (`_today_utc`) → Zähler gilt als „gestern", wird 0 | fünf kopierte `_write_budget`: `tests/unit/test_forecast_budget_gate.py:122`, `tests/unit/test_meteoalarm_budget_gate.py:28`, `tests/unit/test_radar_budget_and_priority.py:103`, `tests/unit/test_radar_upstream_failure.py:119`, `tests/tdd/test_radar_nowcast_health_journal.py:172` | UTC-Tag |
| B Etappe/Snapshot/Marker | ≈33 | Etappe, Wetter-Snapshot oder Zeitanker mit Prozesstag, Produkt sucht Ortstag (`trip_local_today`; ohne Wegpunkte UTC) | `_active_trip()` `test_starkregen_kurzfristhinweis.py:95` (auch von `test_alarm_szenario_laufendes_ereignis.py:924`); `_write_snapshot()` `test_nowcast_briefing_overtake.py:406`, `test_issue_883_acute_danger_override.py:165`; `schnappschuss_speichern()` `tests/helpers/official_alert_gate_fixtures.py:190`; `_make_active_trip()` `test_issue_818_radar_briefing_integration.py:100`; `frozen_active_window()` `tests/helpers/nowcast_gate_fixtures.py:471`; ~11 Stellen in `test_briefing_anchor_survives_dispatch_failure.py`; `test_thunder_next_day_reference_by_report_type.py:79,103` | Ortstag der Trip-Koordinaten (Island = UTC+0) bzw. UTC-Rückfall |
| C FixtureProvider | 7 | Offline-`FixtureProvider` (`src/providers/fixture.py:110`) verankert Daten am UTC-Tag; Test filtert auf Prozesstag → leer | `test_compare_outlook_day_boundary.py:86,123`, `test_compare_outlook.py:111`, `test_ausblick_schleife_…py:138,179`, `test_stage_weather_endpoint.py:95/161`, `tests/unit/test_comparison_engine_no_circular_import.py:72` (Subprozess erbt `TZ`) | UTC-Tag |
| D Uhrzeit-Grenze | 9 | **Kein Tagesfehler.** `tests/helpers/strecke_fixtures.py:38,97` (LAT/LON 0,0) verlangt Versätze −120/−30 Min im selben Ortstag; `tests/helpers/arrival_window_fixtures.py:170-182` wirft ValueError, wenn Ortszeit kurz nach Mitternacht | `tests/tdd/test_strecke_km_argument.py` | — (Uhr im Test pinnen) |

### Messungen (reproduzierbar, Scratchpad-Protokolle)
1. **freezegun ist für diesen Fall blind:** `freeze_time` ohne Zonenbehandlung → `date.today()` = UTC-Tag; `tz_offset` verschiebt auch `datetime.now(timezone.utc)` (gemessen 00:20 → 21:50) → unbrauchbar; `fake_localtime` ignoriert Sommerzeit.
2. **Zonen-Knopf statt Uhr-Patch (Advisor-Hinweis, gemessen):** Prozesszone `Pacific/Marquesas` (UTC−9:30, Halbstunden-Versatz wie St_Johns, keine Sommerzeit) um 06:39 UTC, **ohne** freezegun, alle 20 Dateien in einem Lauf: **51 von 51** Tagesfehlern der CI-Menge reproduziert — inkl. Subprozess-Test. Die 9 von Familie D fehlen erwartungsgemäß (brauchen UTC-Uhrzeit nahe Mitternacht, nicht falschen Tag).
3. **60 ist eine Untergrenze:** derselbe Lauf zeigt 7 weitere rote Tests (`test_issue_818_radar_briefing_integration.py` 6, `test_radar_upstream_failure.py::test_both_alarm_paths_receive_data_unavailable_flag`) — gleicher Helfer `_make_active_trip()`/Prozesstag, im CI-Moment 00:20 nur zufällig nicht getroffen.
4. Messartefakt vermieden: lokale Läufe brauchen die CI-Flags `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`; ohne `--allow-hosts` entstehen 25 Schein-Fehler.
5. **Vollmessung gesamte Suite** unter `Pacific/Marquesas` mit CI-Flags und CI-Excludes (15.09. ~06:45 UTC): 12027 passed, **62 rot** = 58 Tagesfehler (51 aus CI + 7 aus Messung 3) + 4 lokale Umgebungsartefakte: `tests/test_public_host_links.py` (3, auch in Standardzone rot — lokal gesetztes `GZ_PUBLIC_HOST`) und `tests/tdd/test_issue_1014_live_optin.py` (1, allein grün — bekannter Reihenfolge-Altbefund #1196). Keine weitere Datei betroffen.
   **Wahrer Umfang: 67 Tests in 20 Dateien** (58 Tagesfehler Familien A–C + 9 Uhrzeit-Grenze Familie D).

### Technical Approach (Empfehlung)
1. **Messwerkzeug additiv:** Root-`conftest.py:23` bekommt einen Env-Knopf für die Prozesszone (Default `America/St_Johns` unverändert). Kein Eingriff in freezegun-Interna, `_gestellte_wanduhr`/#2096 bleibt unberührt. „Prozesstag ≠ UTC-Tag" ist damit zu jeder Tageszeit herstellbar, auch Winterzeit-unabhängig.
2. **Fixtures je Familie:** A/C → UTC-Tag über neuen Helfer `utc_tag()` neben `ortstag()` in `tests/helpers/ortstag.py`; B → `ortstag(lat, lon)` mit den Koordinaten des gebauten Trips, auch in Nebenpfaden (Snapshot, Marker, Zeitanker); D → Uhr im Test auf eine unkritische UTC-Zeit pinnen (Koordinaten 0,0 bleiben).
3. **Wanduhr-Ratsche #1667** so erweitern, dass sie `utc_tag()` wie `ortstag()` erkennt (kein neues Gate).
4. **Nachweis ohne Warten auf die Nacht:** gesamte Suite unter „Gestern-Zone" grün + Familie D bei gepinnter Uhr 00:20 UTC grün + Kontrolllauf Standardzone grün. Echter CI-Nachtlauf wird als Bestätigung im Issue gebucht, nicht als Pflicht-AC mit Wanduhr-Abhängigkeit.

### Scope Assessment
- Dateien: ≈20 Testdateien + 3–4 Helfer + Root-`conftest.py` + Ratsche; weitere aus der Vollmessung
- LoC: voraussichtlich >250 → `loc_limit_override` nötig
- Risiko: MEDIUM (nur `tests/`, aber Merge-Tor aller Sitzungen)

## Related Files
| File | Relevance |
|------|-----------|
| `conftest.py` (Root) | setzt Prozesszone `America/St_Johns` auf Modulebene |
| `tests/conftest.py` (`_gestellte_wanduhr`, ~Z. 580–630) | Uhr-Schalter, `freeze_time` ohne `tz_offset` — Messlücke |
| `tests/helpers/wanduhr.py` | Anker-Umrechnung des Schalters (eine Stelle, #2096) |
| `tests/tdd/test_gestellte_wanduhr_schalter.py` | Selbsttest des Schalters |
| `tests/helpers/ortstag.py` | Helfer aus Durchgang 1 (Ortstag aus Koordinaten) |
| Wanduhr-Ratsche #1667 | erkennt `ortstag(...)` ohne gepinnte Uhr; muss ggf. neue Helfer kennen |
| `src/services/forecast_budget.py:123`, `src/services/official_alerts/meteoalarm_budget.py` | UTC-getaktete Tageszähler (Produkt korrekt) |
| Produkt-Stellen mit `date.today()`: `alert_briefing_anchor.py`, `dispatch_orchestrator.py`, `trip_report_scheduler.py`, `scheduler_dispatch_service.py`, `notification_service.py`, `preview_service.py`, `trip_command_processor.py`, `compare_slot_scheduler.py`, `compare_location_weather_source.py`, `providers/openmeteo.py`, `output/renderers/email/compare_html.py` | **offen: echte Produktfehler im Fenster denkbar** (Server-Zone ≠ UTC ≠ Ortszone), nicht nur Fixture-Fehler |
| `docs/reference/critical_lessons.md` | Regel + Messgrenze aus Durchgang 1 |

## Existing Patterns
- Durchgang 1: Fixtures datieren über `ortstag(lat, lon)`, Delegation an produktives `tz_for_coords`, keine eigene Zonenarithmetik.
- Produkt: Ortstag über `trip_day.trip_local_today` (ADR-0044); globale Tageszähler auf UTC-Tag (`_today_utc`).
- `tests/tdd/test_compare_local_time_basis.py` stellt eigene TZ und stellt sie wieder her.

## Dependencies
- Upstream: freezegun 1.5.5 (`tz_offset`-Semantik), `utils.timezone.tz_for_coords`, Prozesszone aus Root-`conftest.py`.
- Downstream: CI-Job `test` (Merge-Tor aller Sitzungen), Nachweis-Läufe mit `GZ_TEST_WALL_CLOCK_UTC`.

## Existing Specs
- Spec aus Durchgang 1 (`fix-2314-ci-zeitzonen-riss`, archiviert) — AC-9 dort verlangt echten Nachtlauf.
- #2096 (Uhr-Schalter), #1402 (Prozesszone St_Johns), #1667 (Wanduhr-Ratsche), ADR-0044 (Ortstag).

## Risks & Considerations
- **Fixture-Fehler vs. Produktfehler unterscheiden:** Wo das Produkt `date.today()` nutzt, wäre das Umdatieren der Fixture ein Verdecken. Pro Datei klären, welcher Tag fachlich richtig ist (Ortstag / UTC-Tag / Prozesstag).
- **Messwerkzeug zuerst:** Ohne Schalter, der „Prozesstag ≠ UTC-Tag" herstellt, ist jeder Fix wieder nur im echten Nachtlauf prüfbar. `tz_offset` ist in freezegun ein fester Wert — Sommer/Winterzeit St_Johns beachten; Wirkung auf `datetime.now()` (naiv) und `time.localtime()` prüfen.
- Die Schalter-Änderung könnte bisher grüne Nachweis-Läufe anderer Uhrzeiten rot färben (dann: weitere, bislang verdeckte Fehler).
- `test_comparison_engine_no_circular_import.py` startet einen frischen Interpreter — dort wirkt ein Session-freezegun nicht; Messbarkeit gesondert klären.
- 22:00–24:00 UTC ist nach PR #2329 ebenfalls noch nicht per echtem CI-Lauf belegt.
- Scope: nur `tests/`, sofern die Analyse keinen Produktfehler findet; sonst Produktänderung ausdrücklich in die Spec.
