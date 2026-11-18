# Context: feat-3128-trip-gemeinsamer-berichtsaufbau

## Request Summary
Issue #3128 (abgespalten aus #2983): Trip-Briefing-Vorschau und Trip-Versand setzen den Bericht an zwei
Stellen zusammen. Ziel: EIN gemeinsamer Baustein nach dem Muster von `compare_briefing_aufbau.py` (#2983);
Vorschau = bauen, Versand = bauen + Seiteneffekte + senden. Versandinhalt bleibt byte-gleich.

Vorarbeit: `docs/context/feat-2983-gemeinsamer-berichtsaufbau.md` (Drift-Tabelle Trip, Variantenwahl V1).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/preview_service.py:133-388` | `_build_report` (Segmente, tz, Render-Optionen, Trend im eigenen Thread #1839, `_fetch_main_and_night`, Etappe/Stats, Gewitter, Wetterlage, `_render_email` → `TripReportFormatter().format_email`) |
| `src/services/preview_service.py:390-414` | `render_sms_preview` – einziger öffentlicher Einstieg (seit #1743 nur noch SMS-Vorschau) |
| `src/services/trip_report_scheduler.py:1566-2150` | `_briefing_bauen_und_senden`: Zieltag, Segmente + Test-Fallback (#768), Klemmen (#1325, #2417), tz, Render-Optionen, Wind-Exposition, DWD-Vorwärmen, Wetterabruf, Kontingent (`manuell_abgelehnt`, #2961), amtliche Warnungen, Ausfallschwelle (#1113), Ensemble, Wetterlage, Etappe/Stats, Nacht, Trend, Gewitter, Vortag, Starkregen, Request-Bau, Anker (#1629), Versand, Logs/Marker |
| `src/services/trip_report_scheduler.py:2205` | `_build_trip_report_request` → DTO `TripReportRequest` (Kanal-Flags, shortcode, stage_total, trip_url, Präfixe) |
| `src/services/notification_service.py:781-860` | `send_trip_report`: `has_gap` (compute_has_gap), `undelivered`, Starkregen-Text, `format_email(..., lang=self._lang)` |
| `src/services/compare_briefing_aufbau.py` | Vorbild (#2983): kleine Funktionen ohne Nebenwirkungen, kein Zirkelimport, Aufrufer lösen zur Laufzeit über das Modul auf |
| `src/services/segment_weather.py:548,577` | `night_weather_needed`, `fetch_night_weather` |
| `src/output/renderers/sms_trip.py:235,591` | SMS-Renderer nimmt `has_gap` → SMS-sichtbar |
| `api/routers/preview.py` | `GET /api/preview/{trip_id}/sms` |
| `scripts/premium_sms_preflight_check.py` | nutzt `PreviewService.render_sms_preview` |
| `tests/helpers/trip_vorschau_bericht.py` + ~20 Testdateien | rufen `_build_report` direkt (Signatur/Rückgabe-Tupel ist Test-Vertrag) |

## Existing Patterns
- #2983 Ortsvergleich: `compare_briefing_aufbau.py` mit Funktionen `compare_wetter_laden`, `compare_email_rendern`, `compare_kanaltexte_rendern`, `compare_briefing_bauen`; Spec `docs/specs/modules/compare_briefing_aufbau.md`; Golden-Tests in `tests/tdd/test_compare_briefing_aufbau.py`.
- Teilschritte sind auf Trip-Seite bereits geteilt (`_convert_trip_to_segments`, `_build_stage_trend`, `_build_thunder_forecast_from_trend_or_fetch`, `resolve_report_render_options`, `fetch_night_weather`); doppelt ist die Verdrahtung/Reihenfolge und der Render-Aufruf.
- Vorschau ohne Seiteneffekte über `scheduler.persist_backfill = False` (#2036).

## Drift (Ist-Stand, SMS-relevant = Vorschau-Ziel seit #1743)
| Punkt | Vorschau | Versand | SMS-sichtbar? |
|---|---|---|---|
| Nachtwetter | nur bei `night_weather_needed` | immer | ja (N/FN, Gewitter-Nachtzusatz), über has_gap |
| `has_gap` | nie (Default False) | `compute_has_gap` | ja (`sms_trip.py:534`) |
| Sprache | `TripReportFormatter()` ohne `lang` | `lang=self._lang` | **nein** (Analyse: `format_sms` hat kein `lang`, `_sms_kwargs` trip_report.py:463-476) |
| Klemme „ab jetzt" (#2417) | nein | nur on_demand/morning | Vorschau ist kein on_demand → kein Drift |
| Wind-Exposition, Vortag, Starkregen, Ensemble, undelivered, amtliche Warnungen | nein | ja | in Analyse prüfen (Ensemble = confidence, kein SMS-Token #2233) |
| Trend nebenläufig (#1839) | eigener Thread | seriell mit Phasenuhr | gewollter Unterschied |
| Demo-Provider (#483) | FixtureProvider | nie | gewollt |
| shortcode/stage_total/trip_url | fehlen | ja | in Analyse prüfen (SMS-Kopf?) |

## Dependencies
- Upstream: Scheduler-Methoden, `WeatherPatternService`, `TripReportFormatter`, `resolve_report_render_options`, `segment_weather`, `tz_for_coords`, `forecast_budget`.
- Downstream: `render_sms_preview` (API + Preflight-Skript), Scheduler-Versand (`_send_trip_report_outcome` ← `_send_trip_report`/`dispatch_orchestrator`, `send_on_demand_report`), Mail-Validator `briefing_mail_validator.py`, ~57 Testreferenzen auf `_build_report`.

## Existing Specs
- `docs/specs/modules/preview_service.md`, `trip_report_scheduler.md`, `fix_923b_wire_live_sms_preview.md`, `compare_briefing_aufbau.md` (Muster), `trip_report_formatter_v2.md`.

## Risks & Considerations
- **Kritischer Pfad:** jeder Trip-Versand läuft durch den Umbau → Golden-Tests (Mail + SMS + Telegram vorher = nachher) VOR dem Umbau, Renderer-Commit-Gate, `briefing_mail_validator.py` auf Staging.
- Versand hat Zwischenstopps (Kontingent nach Wetterabruf und vor Rendern, `no_weather`, Anker im try) → wie bei #2983 mehrere kleine Funktionen statt eines Rundum-Aufrufs; Phasenuhr (`uhr.wechsel`) muss weiter messen.
- `_last_converted_trip`-Tausch und Test-Fallback bleiben im Versand.
- Vorschau-Fehlercodes `vorschau_*` und Rückgabe-Tupel `(report, segment_weather, stage_name, trip_tz)` sind Testvertrag.
- Nachtwetter-Gate & has_gap (lang NICHT SMS-relevant, siehe Analysis): Vorschau muss dem Versand folgen (SMS-Vorschau misst die zugestellte SMS, #1743) → zusätzlicher Abruf in der Vorschau; Fixture-Provider im Demo-Modus mitgeben.
- Kein Zirkelimport (Baustein importiert weder `preview_service` noch Scheduler-Modul auf Modulebene).
- Multi-User: `user_id` vom Aufrufer, nie `"default"`; Test mit zwei Nutzern.

## Analysis

### Type
Feature (Refactor, Versandinhalt byte-gleich). SMS-sichtbare Drift der Vorschau ausgelagert nach **#3144** (Bug).

### Befunde
- SMS entsteht nur aus `_sms_kwargs` (`src/output/renderers/trip_report.py:463-476`: stage_name, report_type, thunder_forecast, disabled_specs, night_weather, has_gap, day_window, sms_alert_min_level, ampel) plus Segmentfeldern (`official_alerts`).
- SMS-sichtbare Drift: **amtliche Warnungen** (Vorschau lädt nie; `sms_trip.py:151-174,563-568`), **has_gap**, **Nachtwetter** (Gate), **Test-Fallback**. Nicht SMS-sichtbar: lang, Vortag, Starkregen, Ensemble, undelivered, shortcode, stage_total, trip_url, Präfixe (`_apply_prefixes` nur Mail/Telegram), Wind-Exposition (auch im Versand nicht in SMS).
- Versand hat Zwischenstopps: no_stage, Kontingent nach Wetterabruf (1757) und vor Request (1912), no_weather (1780-1805), Anker/Marker/Logs nach Versand.
- Gemeinsame Kandidaten: Segmentbau (persist-Flag), tz, render_options, Etappe/Name/Stats, `_fetch_weather`, Nacht, Trend, Gewitter, WeatherPattern, Render.
- Tests: 112 Treffer / 28 Dateien auf `_build_report`/`render_sms_preview`; Rückgabe-Tupel `(report, segment_weather, stage_name, trip_tz)` + Signatur sind Vertrag; `inspect.getsource`-Tests in `tests/tdd/test_bug_397_output_localtime.py`, `tests/tdd/test_issue_1004_ssot_callers.py` vorab prüfen.
- Golden: nur Trip-Mail (`tests/tdd/test_einstellung_gleich_mail_trip.py`, `tests/fixtures/einstellung_gleich_mail/trip_altbestand_golden.*`); **kein** Golden für Trip-SMS/Telegram-Versand → vor Umbau anlegen.
- Aufrufer Versand: `dispatch_orchestrator` (77, 98), `send_test_report_outcome` (briefings_send.py:74, trip_command_processor.py:2773), `send_on_demand_report` (trip_command_processor.py:1851). Vorschau: `api/routers/preview.py:52`, `scripts/premium_sms_preflight_check.py:70`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_briefing_aufbau.py` | CREATE | Baustein ohne Nebenwirkungen, kein Modul-Import von Scheduler/preview_service |
| `src/services/trip_report_scheduler.py` | MODIFY | `_briefing_bauen_und_senden` ruft Teilfunktionen an heutigen Stellen; Zwischenstopps, Phasenuhr, Anker, Marker bleiben im Scheduler |
| `src/services/preview_service.py` | MODIFY | `_build_report` = dünne Fassade auf Gesamtaufruf, Signatur/Tupel/`vorschau_*`-Fehlercodes unverändert, Trend parallel (#1839) bleibt |
| `src/services/notification_service.py` | MODIFY (minimal/evtl. keine) | Render-Aufruf ggf. über Baustein |
| `docs/specs/modules/trip_briefing_aufbau.md` | CREATE | Spec nach Muster `compare_briefing_aufbau.md` |
| `tests/tdd/test_trip_briefing_aufbau.py` | CREATE | Golden SMS (160 + Premium) + Telegram (Kurz/Lang) + Mail des Versands vor/nach, deterministische Fixtures, Sinks statt Mocks; Zirkelimport-Test im frischen Prozess; zwei Nutzer |

### Funktionsschnitt (Vorschlag)
- `trip_segmente_bauen(scheduler, trip, target, persist)` — Segmente (+ optional Test-Fallback bleibt im Versand).
- `trip_wetter_laden(...)` — Hauptabruf (Wind-Exposition/DWD-Vorwärmen nur Versand-Schalter).
- `trip_anreicherung_bauen(..., trend_parallel=False)` — Wetterlage, Etappe/Stats, Nacht, Trend, Gewitter.
- `trip_report_rendern(..., has_gap, lang, undelivered, vortag, starkregen)` — ein Render-Weg.
- `trip_briefing_bauen(...)` — Gesamtaufruf nur für die Vorschau.
Versand ruft Teile einzeln (Kontingent-Stopps, no_weather, Phasenuhr `uhr.wechsel` dazwischen). Vorschau-Verhalten bleibt in diesem Ticket UNVERÄNDERT (Drift → #3144).

### Scope Assessment
- Files: 4 Produktiv + Spec + 1-2 Testdateien
- Estimated LoC: Produktiv ca. +350/-400 (Verschiebung, zählt als „added"), Tests ca. +250
- LoC-Limit 250/Workflow (nur hinzugefügte Zeilen gegen HEAD) → `loc_limit_override 500` nötig; Commits in Etappen (Golden zuerst) halten das Delta je Schritt klein.
- Risk Level: **HIGH** (jeder Trip-Versand läuft durch den Umbau) — abgefangen durch Golden-Tests vor dem Umbau + `briefing_mail_validator.py` auf Staging.

### Technical Approach
Variante B2 (Plan-Bewertung):
| Variante | Inhalt | LoC grob | Durchläufe |
|---|---|---|---|
| A | nur Refactor, byte-gleich, Vorschau-Verhalten unverändert | ~450-600 + 150 Tests | 1 |
| B | A + Vorschau folgt Versand | A + ~100 Code + 150 Tests | 1, über Limit |
| **B2** | A jetzt (#3128), Drift-Angleichung als #3144 | Teil 1 ~600, Teil 2 ~250 | 2 |
Reihenfolge: (1) Golden SMS/Telegram/Mail gegen Ist-Stand, (2) Spec, (3) Baustein + Versand umverdrahten (Golden grün, Phasenuhr), (4) Vorschau-Fassade, (5) Staging mit `briefing_mail_validator.py`.

### Risiken
- Reihenfolge der Zwischenstopps/Phasenuhr verrutscht; Kontingent-Stopp muss vor Rendern bleiben.
- Zirkelimport (preview_service ↔ Scheduler): Baustein löst zur Laufzeit auf.
- `inspect.getsource`-Tests auf Fassadenquelltext.
- Multi-User: `user_id` durchreichen, nie `"default"`.

### Open Questions
- keine Produktfrage (Vorschau = zugestellte SMS ist mit #1743 entschieden; Drift-Behebung in #3144).
