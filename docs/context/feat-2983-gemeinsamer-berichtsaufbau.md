# Context: feat-2983-gemeinsamer-berichtsaufbau

## Request Summary
Issue #2983 (Folge von #1986, Paar 2 „Vorschau ↔ Versand doppelt verdrahtet"): Vorschau und Versand
bauen den Bericht heute an zwei Stellen zusammen (Trip und Ortsvergleich). Ziel: EIN gemeinsamer
Baustein für den Berichtsaufbau; Paritätstests danach überflüssig oder Regressionswächter.

Quelle des Zuschnitts: `docs/context/feature-1986-paritaets-bestandsaufnahme.md:43`,
`docs/specs/modules/paritaets_bestandsaufnahme.md`.

## Related Files

### Trip
| File | Relevance |
|------|-----------|
| `src/services/preview_service.py:139-327` | `_build_report`: Segmente, tz, Render-Optionen, Trend (eigener Thread), Haupt+Nacht-Abruf, Etappe/Stats, Gewitter-Ausblick, Wetterlage, `_render_email` → `TripReportFormatter().format_email` (Z.350-389) |
| `src/services/trip_report_scheduler.py:1566-2200` | `_briefing_bauen_und_senden`: dieselbe Kette (Segmente 1643, tz 1712, Render-Optionen 1726, Wetterlage 1827, Etappe/Stats 1835, Nacht 1843, Trend 1856, Gewitter 1874) plus versand-eigene Teile (Test-Fallback/Klemmen, Wind-Exposition, DWD-Vorwärmen, amtliche Warnungen, Ausfallschwelle, Ensemble, Vortag-Vergleich, Starkregen-Hinweis, Kontingent, Anker) |
| `src/services/trip_report_scheduler.py:2205` | `_build_trip_report_request` → DTO `TripReportRequest` |
| `src/services/notification_service.py:780-880` | `send_trip_report`: has_gap, undelivered, Starkregen-Text, `format_email(...)` mit mehr Parametern als die Vorschau (undelivered, exposed_sections, day_comparison, shortcode, stage_total, trip_url, has_gap) |
| `api/routers/preview.py` | HTTP-Einstieg der Trip-Vorschau (E-Mail/SMS/Telegram) |

### Ortsvergleich
| File | Relevance |
|------|-----------|
| `src/services/compare_preview_service.py:50-194` | `render_all_channels`/`_prepare`/`_render_email`: Profil, `run_comparison_parallel`, `resolve_compare_render_options`, Betreff, `render_compare_email/telegram/sms` |
| `src/services/scheduler_dispatch_service.py:~850-1100` | `send_one_compare_preset`: dieselbe Kette (Profil 935, Engine 948, Betreff 976, Optionen 979, `render_compare_email` 993, SMS 1072, Telegram 1080) plus undelivered, Kontingent, no_weather-Regeln, Anker |
| `src/output/renderers/comparison.py:537/917/1389` | Renderer E-Mail/Telegram/SMS (gemeinsam genutzt, nicht doppelt) |

### Paritätstests (bewachen das Paar heute)
`tests/tdd/test_preview_parity_without_outlook.py`, `tests/tdd/test_preview_render_options_parity.py`,
`tests/tdd/test_thunder_origin_preview.py` (thunder_night_addendum_parity), `tests/tdd/test_compare_preview_hourly_parity.py`,
`tests/tdd/test_compare_preview_service.py`, Isolation: `tests/test_preview_service_user_isolation.py`,
`tests/tdd/test_compare_preview_user_isolation.py`, Cache: `tests/unit/test_compare_preview_second_call_uses_cache.py`.

## Existing Patterns
- Geteilte Bausteine statt Kopien: `resolve_report_render_options` / `resolve_compare_render_options` (#1208/#1209), `fetch_night_weather` + `night_weather_needed`, `COMPARE_FORECAST_HOURS` (#1305), Alarm-Vorschau über geteilten Kanaltext-Baustein (#2986, direkt davor geliefert).
- Vorschau nutzt bereits Scheduler-Methoden (`_convert_trip_to_segments`, `_build_stage_trend`, `_build_thunder_forecast_from_trend_or_fetch`) mit `persist_backfill=False` – die Teilschritte sind geteilt, die **Reihenfolge/Verdrahtung** ist doppelt.
- Kommentar-Appelle „identisch zum Versand (Zeile X)" in `preview_service.py` sind Zeichen der Doppelung.

## Dependencies
- Upstream: Scheduler-Methoden, `WeatherPatternService`, `TripReportFormatter`, `run_comparison_parallel`, Render-Optionen-Resolver, `tz_for_coords`.
- Downstream: Trip-Vorschau-Endpunkte (E-Mail/SMS/Telegram), Compare-Paritätstests (`render_all_channels`), Scheduler-Versand Trip und Ortsvergleich, Mail-Validatoren (`briefing_mail_validator.py`, `email_spec_validator.py`), ~128 Tests referenzieren `_build_report`/`format_email`/`render_all_channels`.

## Existing Specs
- `docs/specs/modules/paritaets_bestandsaufnahme.md` (Herkunft)
- `docs/specs/modules/report_config_resolver_slice_b.md` (Render-Optionen-Baustein)
- `docs/specs/modules/fix_1486_outlook_silent_exit.md`, `compare_forecast_horizon.md`, `i18n_p9b_scheduler_orchestrierung_2672.md`

## Risks & Considerations
- **Kritischer Pfad:** Versand jedes Trip-Briefings und Ortsvergleichs läuft durch den umzubauenden Code. Verhaltensgleichheit (Mail-Inhalt, Kanäle, Anker, Marker, Ausfall-Regeln) ist Pflicht → Renderer-Commit-Gate + Validatoren.
- Echte, gewollte Unterschiede Vorschau ↔ Versand müssen als Parameter des Bausteins bleiben: kein Persistieren (`persist_backfill=False`), Demo-Provider (#483), has_gap=False (#1331), Trend parallel im Thread (#1839, Vorschau-Latenz), kein Test-Fallback/Klemmen, keine Anker/Marker/Snapshot-Schreibung, keine undelivered-Vorfälle; Vorschau ohne Wind-Exposition/Vortag/Starkregen? → in Analyse prüfen, ob das gewollt oder Drift ist (wahrscheinlich Drift = Vorschau zeigt weniger als Versand).
- Mandantentrennung: echte `user_id` durchreichen, nie `default` (Isolationstests beidseitig).
- Fehlercodes der Vorschau (`vorschau_etappe_fehlt`, `vorschau_zu_wenige_wegpunkte`, `vorschau_wetter_fehlt`) vs. Versand-Rückgaben (`no_stage`, `no_weather`) müssen erhalten bleiben.
- Phasenuhr (`uhr.wechsel`) und Kontingent-Abbruch (`manuell_abgelehnt`) gibt es nur im Versand.
- Größe: zwei getrennte Zusammenführungen (Trip, Ortsvergleich). Analyse soll entscheiden, ob in einem Durchlauf oder als Epic mit zwei Kind-Issues (PO-Regel: Epic mit eigenen Issues, nie Teilaufgaben-Issue).
- Trip/Ortsvergleich-Code-Teilung (CLAUDE.md): beide Seiten nach demselben Muster bauen.

## Investigation (Phase 2, 3× Explore)

### Drift Trip (Vorschau `preview_service._build_report` vs. Versand `_briefing_bauen_und_senden` + `send_trip_report`)
| Schritt | Status |
|---|---|
| Segmente | Versand klemmt auf heute/jetzt (tsr:1694-1718), Vorschau nicht |
| TZ, Render-Optionen, Wetterlage, Etappe/Stats, Trend, Gewitter | gleich |
| Wind-Exposition `exposed_sections` (tsr:1731-1742) | nur Versand → Drift |
| DWD-Vorwärmen (1746) | nur Versand (Performance, kein Inhalt) |
| Totalausfall/Teilausfall-Hinweis (1780-1814) | nur Versand |
| Amtliche Warnungen `official_queries` (1768) | nur Versand, Verwendung im DTO prüfen |
| Ensemble `_enrich_ensemble_for_trip` (1817) | nur Versand → Drift (nur Verlässlichkeits-Hinweis im Mailtext, #710) |
| Nachtwetter | Vorschau nur bei `night_weather_needed`, Versand immer bei Segmenten → abweichend |
| Vortag `day_comparison` (1886-1897) | nur Versand → Drift |
| Starkregen (1906, Text notification_service:812-834) | nur Versand; feat_1439 sagt „nur planmäßiges Briefing" (implizit, keine Vorschau-Festlegung) |
| format_email-Parameter nur im Versand | undelivered, exposed_sections, day_comparison, shortcode, stage_total, trip_url, has_gap, starkregen_hint_text, lang |
| Sprache | Vorschau `TripReportFormatter()` ohne `lang` → Drift für EN-Nutzer prüfen |
| Präfixe, Anker/Gedächtnis, Kanal-Flags, Kontingent, Phasenuhr | nur Versand (Seiteneffekte, gewollt) |

### Drift Ortsvergleich (`compare_preview_service` vs. `send_one_compare_preset`)
| Schritt | Status |
|---|---|
| Profil, Engine-Parameter, Betreff, E-Mail-Optionen, SMS, Telegram-Langform | gleich |
| Zieltag | Vorschau `_resolve_target_date`, Versand `first_resolvable_tz`+`local_dt` → Zeitbasis prüfen |
| `undelivered` in E-Mail | nur Versand → Drift |
| Telegram-Stil `kurzform` (sds:1077) | Vorschau zeigt immer Langform → Drift (sichtbarer Fehler) |
| Alle-Orte-ohne-Wetter → `no_weather`, Kontingent, Nachhol-Hinweis, Anker | nur Versand |

### Specs/ADRs
- Keine Spec legt fest, dass die Trip-Briefing-Vorschau Wind-Exposition, Vortag, Starkregen oder amtliche Warnungen NICHT zeigen soll. `wind_exposition_*` und `feat_1439` beschreiben nur den Versand (implizit).
- Gewollte Unterschiede belegt: Demo-Provider (#483, fix_2581), Trend nebenläufig (fix_1839 Ae3), keine Seiteneffekte (preview_service.md). Gleichheit verlangt: ADR-0025 (Gewitter), ADR-0119 (Layout-Resolver), alert_channel_texts (byte-gleich Compare-Alarm).
- `paritaets_bestandsaufnahme.md` enthält „NEU-2" nicht wörtlich; Quelle ist Implementation Details §3.

### Abhängigkeiten
- Einstiege: `api/routers/preview.py` → `PreviewService.render_sms_preview`/`_build_report`; `scripts/premium_sms_preflight_check.py` importiert PreviewService. `_briefing_bauen_und_senden` ← `_send_trip_report_outcome` ← `_send_trip_report`/`dispatch_orchestrator`. `send_one_compare_preset` ← sds:197/436/1243, `send_compare_preset` ← `briefings_send.py`, `trip_command_processor.py`.
- `ComparePreviewService.render_all_channels` hat keinen produktiven Aufrufer außer Tests (dokumentierte Ausnahme, Kommentar Z.15) — Compare-Vorschau im UI läuft über anderen Pfad, prüfen.
- Tests: `_build_report` 21 Dateien, `_render_email` 31, `render_all_channels` 21, `send_one_compare_preset` 72 (oft monkeypatcht, z. B. test_2795, test_compare_send_lock). `tests/tdd/test_profil_ampel_kette.py:926-932` zählt Namensvorkommen im Quelltext → Signaturen/Namen behalten.
- Zirkulärer Import: compare_preview_service ↔ scheduler_dispatch_service (`order_locations_by_ids`, `build_compare_preset_subject`).

### Verifizierter Schlüsselbefund (Orchestrator)
Seit #1743 (PO-Entscheid 22.10.2026) gibt es die Briefing-Vorschau je Kanal im Produkt nicht mehr. Übrig: `GET /api/preview/{trip_id}/sms` (`render_sms_preview` → `_build_report` → `report.sms_text`), genutzt von Staging-Specs und `scripts/premium_sms_preflight_check.py`. `POST /api/preview/compare/{id}` ist entfernt (router.go:334, api.ts:303); `ComparePreviewService.render_all_channels` hat keinen produktiven Aufrufer mehr (nur Tests), `_load_preset` wird von `compare_alert_preview_service` genutzt.

## Analysis

### Type
Feature (Refactoring mit Drift-Beseitigung; kein sichtbares Produktverhalten außer SMS-Vorschau = zugestellte SMS)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_briefing_aufbau.py` | CREATE | Baustein `briefing_bauen(scheduler, trip, target, report_type, now_utc, *, modus, provider, …)` → Ergebnisobjekt mit allen Formatter-/Request-Eingaben, ohne Seiteneffekte |
| `src/services/compare_briefing_aufbau.py` | CREATE | Baustein `compare_briefing_bauen(…)`: Profil, `run_comparison_parallel`, Render-Optionen, Betreff, E-Mail/SMS/Telegram inkl. Telegram-Stil `kurzform`; ohne Importe der beiden Dienste (Zirkelimport auflösen) |
| `src/services/trip_report_scheduler.py` | MODIFY | `_briefing_bauen_und_senden` ruft Baustein; Uhr, Kontingent (`manuell_abgelehnt`), Anker/Gedächtnis, Kanal-Flags, `no_stage`/`no_weather` bleiben im Versand, Reihenfolge erhalten |
| `src/services/preview_service.py` | MODIFY | `_build_report` ruft Baustein (modus=vorschau), Fehlercodes `vorschau_*` bleiben, Trend-Thread #1839 bleibt |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset` ruft Compare-Baustein; undelivered, Kontingent, no_weather, Nachhol-Hinweis, Anker bleiben |
| `src/services/compare_preview_service.py` | MODIFY | `render_all_channels` = dünne Hülle über Compare-Baustein; `_load_preset` bleibt (Alarm-Vorschau) |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY (nur falls nötig) | Namenszähler 926-932; bevorzugt Aufrufe von `template_id_for` in den bisherigen Funktionen belassen |
| Paritätstests (`test_preview_parity_without_outlook`, `test_preview_render_options_parity`, `test_preview_thunder_matches_sent`, `test_compare_preview_service`, `test_compare_preview_hourly_parity`) | MODIFY | werden Regressionswächter „Vorschau und Versand gehen durch denselben Baustein" |
| neue Tests | CREATE | Golden/Characterization: Trip-Mail, Trip-SMS, Compare-Mail/SMS/Telegram vorher = nachher; SMS-Vorschau = Versand-SMS; Telegram-Kurzform in Compare-Vorschau; zwei Nutzer |

### Scope Assessment
- Quelldateien: 6 (2 neu), Tests ca. 8–12 Dateien
- Estimated LoC: ca. +350/−550 (netto −100 bis −250), Schätzung
- Risk Level: HIGH (jeder Trip- und Ortsvergleich-Versand läuft durch den Umbau) → Absicherung über Golden-Tests vor dem Umbau, Renderer-Commit-Gate, `briefing_mail_validator.py`, `email_spec_validator.py` auf Staging

### Technical Approach (Entscheidung Tech Lead)
Variantenvergleich (Plan/Sonnet): V1 Baustein für beide und Vorschau ruft ihn; V2 wie V1, Compare-Vorschau als dünne Hülle; V3 Compare-Vorschau löschen. Gewählt: **V1 für Trip, V2 für Ortsvergleich, in EINEM Durchlauf** (kleine verwandte Teile, gleiches Muster Trip/Vergleich; Epic nur, falls die LoC-Grenze des Workflows reißt).

Grundsatz: Der Baustein ist die einzige Stelle, die den Berichtsinhalt zusammensetzt; Versand = bauen + Seiteneffekte + senden, Vorschau = bauen.

Bewusste Unterschiede als Parameter (dokumentiert, keine Drift):
- Provider (Demo #483/fix_2581), keine Persistenz (`persist_backfill=False`), Trend-Thread in der Vorschau (#1839), Zieltag-Klemme nur im Versand, `has_gap` (#1331) nur im Versand, Fehlerabbildung je Seite (`vorschau_*` vs `no_stage`/`no_weather`).
- Seiteneffekte bleiben komplett außerhalb des Bausteins: Phasenuhr, Kontingent, Anker/Melde-Gedächtnis, undelivered-Vorfälle, Präfixe, Kanal-Flags.
- Mail-only-Anreicherungen (Wind-Exposition, Vortag, Starkregen-Text, Ensemble-Verlässlichkeit, undelivered-Block) sind Baustein-Schritte mit Schalter; in der Vorschau aus, weil seit #1743 keine Mail-Vorschau mehr existiert und sie die SMS-Zeile nicht beeinflussen (`trip_report.py:485`, `sms_trip.py:584`) — spart Abrufe/Latenz der SMS-Vorschau.

Drift, die angeglichen wird (Vorschau folgt dem Versand):
- **Nachtwetter-Gate** (Vorschau nur bei `night_weather_needed`, Versand immer): SMS-sichtbar; die SMS-Vorschau dient laut #1743 dazu, die zugestellte SMS zu messen ⇒ Vorschau muss dem Versand folgen (Fehlerbehebung, keine Produktentscheidung). Vorher prüfen, welche Seite fachlich richtig ist; Ziel: beide identisch.
- **Sprache** (`lang`) über denselben Baustein.
- **Telegram-Kurzform** im Ortsvergleich: Hülle folgt `effective_compare_telegram_style`.

Reihenfolge: 1. Golden-Tests Ist-Stand (Versand-Mail Trip, Versand-SMS, Compare alle Kanäle) → 2. Ortsvergleich-Baustein (kleiner) → 3. Trip-Baustein, erst Versand (Golden grün), dann Vorschau → 4. Paritätstests zu Wächtern → 5. Gates/Validatoren.

### Dependencies
Siehe Abschnitt Investigation/Abhängigkeiten. Einstiegsnamen und Signaturen (`_build_report`, `_render_email`, `render_all_channels`, `send_one_compare_preset`, `_briefing_bauen_und_senden`) bleiben erhalten (72 Testdateien monkeypatchen `send_one_compare_preset`).

### Open Questions
- [x] Mail-Drift angleichen? → Nein, als Modus-Schalter dokumentiert (keine Mail-Vorschau mehr seit #1743). Tech-Lead-Entscheidung.
- [x] Nachtwetter-Gate → Vorschau folgt Versand (SMS-Vorschau muss zugestellte SMS abbilden). Tech-Lead-Entscheidung.
- [ ] LoC-Grenze des Workflows in Phase 3 prüfen; bei Überschreitung Epic mit zwei Kind-Issues (Trip / Ortsvergleich).
