# Context: feat-2439-befehle-antwortzeit

## Request Summary
Rest von #2439 abschließen (Epic #2506): (a) den bereits gelieferten Push-Eingang (Webhook weckt Poll) in
Prod scharf schalten, (b) die Rechenzeit der Wetter-Befehle `HEUTE`/`MORGEN` (`TODAY`/`TOMORROW`) senken —
mit prüfbarer Zielgröße je Befehlsklasse (Vorschlag aus dem Issue: ohne Wetterabruf < 30 s, mit
Wetterabruf < 1 min).

## Teil (a) — Betriebs-Rest (kein Produktcode), Stand 18.10.
| Punkt | Stand |
|---|---|
| henemm-infra Nginx-Änderung versionieren | ✅ erledigt (`henemm-infra` a1c596d, PR #266) |
| SMS-Nachversuch 0/3/8 s mit echter SMS auf Staging neu messen (`test_ac1`, kein EOF) | offen — über zweite seven.io-Nummer selbst auslösbar |
| Prod-Hooks registrieren (seven.io + Stalwart, Eventname `message-ingest.ham`) | offen — Prod-`.env` hat alle 4 Variablen |
| `check-gregor20.sh`: `missed_total`-Check scharf | offen — kein Treffer `missed_total` in `henemm-infra/scripts/check-gregor20.sh`; vorbereitete Werkzeuge liegen NICHT unter `docs/artifacts/feat-2439-befehle-push-eingang/` (dort nur `prod-selftest.md` im Hauptcheckout) → aus Git-Historie des Branches `feat-2439-befehle-push-eingang*` bergen oder neu schreiben |
| Runbook `docs/runbooks/inbound-webhooks.md:55-58` | offen — nennt Eventname noch als „vor Registrierung verifizieren“; verifiziert ist `message-ingest.ham` (`store.ingest` existiert nicht) |

## Teil (b) — Aufrufpfad HEUTE/MORGEN
- Eingang: Telegram `api/routers/webhook.py:52` → `inbound_telegram_reader.py:347-363` (sendet erst „⏳ Wetter wird geladen“);
  E-Mail `inbound_email_reader.py:251`; Premium-SMS `inbound_sms_reader.py:355/372/403`.
  E-Mail/SMS laufen unter dem Poll-Lock (`api/routers/scheduler.py:211,242`) → ein langes HEUTE blockiert
  alle übrigen Befehle desselben Kanals.
- Dispatch: `trip_command_processor.py:1087-1106` → `_handle_query` (1449) → `heute`/`morgen` (1481-1488)
  → `_trigger_on_demand` (1576) → `TripReportSchedulerService.send_on_demand_report`
  (`trip_report_scheduler.py:1211`) → `_send_trip_report_outcome(on_demand=True)` (1295).
  **Derselbe Code wie der geplante Briefing-Versand.**
- Abrufe pro Befehl (alle seriell):
  (a) Zieltag-Segmente (1386, 1473; HEUTE ab-jetzt-gekappt 1428-1446),
  (b) Nachtwerte (1583),
  (c) Mehrtages-Ausblick (1593 → `_build_stage_trend` 2716-2754, bis 3 Etappen; Default nur evening/MORGEN, `report_config_resolver.py:145,157`),
  (d) Gewitter-Vorschau +1/+2 (1611 → 2935 → `_collect_future_stage_weather` 3196-3211, holt Folge-Etappen neu),
  (e) Ensemble je Etappe (1560/2754/3211, 15 s Timeout),
  (f) amtliche Warnungen, Starkregen-Nowcast (1642), Windexposition (1465).
  → HEUTE ≈ 3 Etappentage, MORGEN bis 4.
- GEWITTER/Glance/Timeline lesen Snapshot (`_fetch_and_save_snapshot` 914-958, Cache via `target_date`-Prüfung 925-931).
  JETZT → `_show_now` (1166) eigener kleiner Pfad. HELP/CODES/STATUS ohne Wetterabruf.

## Abruf je Segment
- `_fetch_weather` (`trip_report_scheduler.py:2386-2434`): serielle Schleife, Retry/Backoff.
- `OpenMeteoProvider.fetch_forecast` (`openmeteo.py:1035`) seriell: OM-Hauptabruf (1147, 30 s/60 s, 5 Retries),
  UV/Air-Quality (1216), Lückenfüller (1271-1306), SNOWGRID GeoSphere (1309 → `geosphere.py:391-434`, 7 Tage, ohne Cache),
  `enrich_thunder` (1317 → `thunder_enrichment.py:327-394`).
- Gewitter-Routing (`thunder_routing.py:73-77`): DE/Alpen → `de_direct` + `geosphere` CAPE/CIN.
  `de_direct` (`dwd.py:677-820`): 9 Größen × bis 24 h ≈ 216 GRIB-Downloads, 5 parallel je Zeitschritt, Budget 150 s (137).
  Nullpunkt hängt am ersten OM-Datenpunkt (ganzer Kalendertag, `openmeteo.py:1112-1114`) → auch 2-h-Segment holt bis 24 h.
- Caches: Segment-Rohdaten-Cache (`segment_weather.py:86-89,172`, TTL 600 s, `weather_cache.py:321`);
  DWD-Raster-LRU (`dwd.py:291-438`, kein TTL, Schlüssel URL → jeder neue Kalendertag kalt);
  Single-Flight (`segment_weather.py:194`).

## Existing Patterns
- `services/parallel_fetch.py` (`fetch_ordered`, #1539 S2, 8 Worker, Semaphore je Provider) — fertig, aber kein Produktivaufrufer.
- `services/stage_weather.py:180` holt Segmente bereits parallel (8 Threads) — nur UI-Etappenansicht.
- Messwerte: DWD kalt 10,3 s für 12-h-Fenster, warm 0,0 s (`docs/context/fix-2554-dwd-gewitterabruf-budget.md:8-11`);
  früher seriell ~52 s für 216 Abrufe (`dwd.py:134-136`).
- **Keine** Laufzeitmessung im Befehlspfad; nur Endpoint-Dauer der Scheduler-Jobs (`api/routers/scheduler.py:86-94`)
  und Rohzeitstempel (`providers/call_log.py:107-127`, `enrichment_health.py:58-86`).

## Dependencies
- Upstream: Open-Meteo, DWD (GRIB), GeoSphere (SNOWGRID, CAPE/CIN), Ensemble, Warn-Provider, Radar.
- Downstream (Risiko bei Änderung): `_send_trip_report_outcome`/`_fetch_weather`/`_build_stage_trend` →
  geplanter Briefing-Versand, Nachlieferung, Test-Versand (`api/routers/scheduler.py:309`), REPORT-Befehl
  (`trip_command_processor.py:2539`), Vorschau (`preview_service.py:193,260`).
  `fetch_segment_weather` + Cache → `trip_alert.py:2993`, `stage_weather.py:58`, `compare_location_weather_source.py:181`.
  `enrich_thunder`/`_RASTER_CACHE` → jeder OM-Abruf (Trip, Ortsvergleich, Alarm).

## Existing Specs
- `docs/specs/modules/feat_2439_befehle_push_eingang.md` (Teil a; Teil b dort Out of Scope, Z. 25/114, Verweis #2554)
- `docs/specs/modules/trip_command_processor.md`, `inbound_command_channels.md`
- `feat_2417_kurzform_englisch.md`, `feat_2417_befehle_e2e_echter_eingang.md`, `feat_2126_kanaltreue_adhoc_antwort.md`
- `fix_2554_dwd_gewitterabruf_budget.md`, `feat_1539_s1b_s2_abruf_baustein.md`; Kontext `feat-1539-parallele-abrufe.md`
- Tests: `test_trip_command_processor.py`, `test_issue_731_unified_commands.py`, `test_befehle_{telegram,email,premium_sms}_e2e.py`,
  `test_ab_jetzt_nur_bei_abruf.py`, `test_kanaltreue_adhoc_antwort.py`, `test_issue_612_report_on_demand.py`,
  `test_adhoc_abruf_am_telegram_draht.py`, `tests/e2e/test_push_eingang_befehle_staging.py`

## Hypothesen (Analyse muss sie MESSEN, nicht annehmen)
1. Kalter DWD-Gewitterabruf je neuem Kalendertag (≈10–20 s/Tag, 24 h auch bei kurzen Segmenten).
2. Serielle Segmentschleife mit 4–6 HTTP-Abrufen je Segment (OM, UV, Lückenfüller, SNOWGRID, CAPE), SNOWGRID/UV je Segment neu.
3. Ad-hoc-Antwort rechnet mehr als nötig (Nacht, Ausblick, Gewitter +1/+2, Ensemble).
4. Nebenkosten (`backfill_stage_distances` 2285, Retry-Backoff).
Offen: „~20 s je Etappe“ — Etappentag oder Segment? 4,5 min / 20 s ≈ 13 → eher Segmente.

## Risks & Considerations
- **Inhaltsparität:** Die Antwort auf HEUTE/MORGEN muss inhaltlich gleich bleiben (Kanal-Parität, Epic #2506); eine
  Kürzung des Umfangs (Ausblick, Gewitter +1/+2) ist eine Produktentscheidung, keine Optimierung.
- Parallelisierung im geteilten Briefing-Pfad trifft auch den geplanten Versand → Provider-Rate-Limits
  (Semaphore je Provider aus `parallel_fetch`), Reihenfolge der Segmente muss erhalten bleiben.
- Mail-Renderer-Gate: Änderungen am Briefing-Bau können Mail-Inhalt berühren → Modus-Matrix + `briefing_mail_validator.py`.
- Poll-Lock: lange Befehle blockieren den Kanal — Zielgröße muss auch den Lock-Effekt einschließen.
- Zielgröße muss auf Staging messbar sein (echter Eingang, nicht nur Kern-Test).

## Analysis

### Type
Feature (Teil a: Betriebs-Rest des Push-Eingangs; Teil b: Rechenzeit HEUTE/MORGEN senken + Zielgröße festlegen)

### Messbasis (18.10., gemessen — ersetzt den 4:38-min-Befund vom 27.09.)
Seit 27.09. gingen #2465 (DWD-Punkt-Fenster-Cache), #1539 (Single-flight), #2554 (DWD parallel) in main → alter Wert überholt.
Harness (versandfrei, Kanäle No-op, leeres `GZ_DATA_DIR`, synthetischer Trip Stubaier Alpen 4 Etappen/18–19 Segmente):
`<scratchpad>/bench.py` (+ `run.sh`, `ana.py`), nicht im Repo.

| Lauf | Gesamt | Kern |
|---|---|---|
| HEUTE kalt (2 Läufe) | 51,3 s / 35,2 s | 4 kalte DWD-Tagesfenster (Zieltag, Nacht, +1, +2), 415 GRIB, 249 MB, **nacheinander** |
| MORGEN kalt | 37,0 s | 2 kalte DWD-Fenster (280 GRIB); Zieltag 21,3 s, Ausblick `_build_stage_trend` 12,2 s |
| HEUTE / MORGEN warm | 1,8 s / 1,8 s | Rendern 0,9–1,1 s |
| **Staging, echter E-Mail-Eingang** (`staging_befehl_pruefen.py --szenario heute`) | **57,8 s** Rechnen (Journal 09:50:21→09:51:19), Gesamtlauf 69,6 s, PASS | 3 kalte DWD-Fenster 13/12/30 s, obwohl nur 1 Segment je Etappe |

HEUTE kalt (35 s) aufgeschlüsselt: Hauptsegmente 11,0 s (DWD-Kaltstart 6,1), Nacht 4,2 s (DWD 3,7), Gewitter +1/+2 17,7 s (DWD 7,1+2,8),
Ensemble 0,18, Warnungen 1,0, Nowcast 0,4, Wind/backfill je 0,04, Rendern 0,8.
Je Provider HEUTE kalt: DWD-GRIB 415 Abrufe/17–30 Thread-s · GeoSphere CAPE 18/4,6–8 s · SNOWGRID 18/2,6 s · OM 29/0,4 s · AQ 18/0,14 · Ensemble 3/0,1.
Keine Retries, nur 3/514 URLs doppelt. DWD-Fenster schwankt 6–30 s. Prod-Briefings 1.–6.10. (vor #2554): Morning 2:33–3:44, Evening 1:10–1:31.
Einschränkung: Korsika (`fr_direct`, Météo-France) nicht gemessen (Zugangsdaten im Harness nicht verfügbar).

Hypothesen: H1 kalter DWD je Kalendertag **bestätigt, größter Block** (56 % bzw. >30 Thread-s) · H2 serielle Segmentschleife halb (warm 0,55 s/Segment, ~21 %) ·
H3 Ad-hoc-Umfang: Nacht+Gewitter +1/+2 ≈ 60 % HEUTE, Ausblick 33 % MORGEN — **nur Anteil, keine Kürzung** · H4 Nebenkosten widerlegt.

### Fensterzuschnitt (Befund Plan-Agent)
DWD-URL kodiert Lauf + Abstand zur Gültigkeitsstunde (`dwd.py:231-242,629`), nicht den Fenster-Nullpunkt → Zieltag/+1/+2 sind disjunkte Dateimengen,
nur die Nacht überlappt (trifft schon heute den Cache, `dwd.py:635`). Kaltkosten sind fix (≈415 Dateien/Lauf, neuer Lauf alle 3 h) —
beschleunigen geht nur über **Überlappen der Wartezeiten**. Punkt-Fenster-Cache (`dwd.py:300-326`) 41×41 px, kein TTL, **max. 512 URLs** →
415 je Trip passt knapp; parallele Alarm-/Ortsvergleichsläufe können verdrängen (Risiko, im Spec prüfen ob Kapazität anzuheben ist).
Kein Single-flight beim Raster-Abruf (`dwd.py:635` prüft nur Cache) → doppelte Downloads bei Gleichzeitigkeit möglich.

### Poll-Lock / Kanäle (Befund Explore)
- Lock je Kanal (`api/routers/scheduler.py:31-53`; E-Mail :211, SMS :242), Befehl synchron im Lock (:213/:244).
- Zweiter Aufruf → sofort `{"status":"busy"}`; Go setzt den Weckruf wieder auf pending (`push_kick.go:151`, Auswertung `scheduler.go:1230`).
  → HELP während laufendem HEUTE wird nach Lock-Ende abgeholt (≈ HEUTE-Dauer + Kick-Abstand), Fallback Cron */5.
- Telegram: synchron im Webhook-Request, ohne Lock (`webhook.py:86-93`, `inbound_telegram_reader.py:156`).
- Go-Core-Client-Timeout 3000 s (`scheduler.go:297`), `closeConnTransport` (:264-273).
- **Keine Dauermessung im Befehlspfad.** Go `jobResult.DurationS` nur je Gesamtlauf (`scheduler.go:37-43,1037`); per-Nutzer-`last_run` ohne Dauer (:1371-1377).

### Teil a — Reste (Befund Explore)
- `missed_total`: Zähler `internal/scheduler/push_kick.go:54`, Inkrement :188, Ausgabe :211 (Push-Status-Map, Test `scheduler_kick_test.go:629-727`).
- Vorbereitete Werkzeuge für `check-gregor20.sh` **existieren nicht mehr** (weder Git-Historie aller Branches noch Worktrees) → neu schreiben.
  `check-gregor20.sh` hat noch keinen Check. **henemm-infra-Arbeitsbaum ist sofort live (Cron) → nur in Kopie entwickeln, infra zuerst.**
- Runbook `docs/runbooks/inbound-webhooks.md:55-58` + Z. 102 nennen den Stalwart-Eventnamen noch als „vor Registrierung verifizieren" → `message-ingest.ham` eintragen.
- `tests/e2e/test_push_eingang_befehle_staging.py::test_ac1_sms_last_run_sekunden_nach_webhook` (Z. 123) prüft push.last_received/received_total/last_run-Zeitnähe.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_command_processor.py | MODIFY | Dauer je Befehl messen (Dispatch ~1087-1106): Befehl, Kanal, Trip-ID, ms |
| src/services/trip_report_scheduler.py | MODIFY | Phasenzeiten im On-Demand/Briefing-Bau loggen; DWD-Tagesfenster (Zieltag/Nacht/+1/+2) **parallel vorwärmen** vor dem Hauptabruf (~1211/1295) |
| src/providers/dwd.py | MODIFY | Vorwärm-Einstieg (Fenster je Tag füllen), Abschluss-Log Dauer/Dateien/Cache-Treffer (~810), ggf. Cache-Kapazität 512 prüfen |
| src/services/parallel_fetch.py | MODIFY (nur S2, bedingt) | Segmentschleife parallel, falls S1 Ziel verfehlt |
| tests/test_befehl_antwortzeit*.py (Name nach Verhalten) | CREATE | Kern: Vorwärmen parallel (Gesamtzeit ≈ max statt Summe, mit aufgezeichneten/künstlich verzögerten Rastern), Inhalt bit-identisch, Dauer-Log vorhanden |
| tests/e2e/test_push_eingang_befehle_staging.py | MODIFY | Live: Zielgröße je Befehlsklasse aus Journal/Status messen |
| docs/runbooks/inbound-webhooks.md | MODIFY | Eventname `message-ingest.ham` |
| henemm-infra/scripts/check-gregor20.sh | MODIFY (anderes Repo) | `missed_total`-Check (Readiness, Ping nur bei Erfolg) |

### Scope Assessment
- Files: ~6 im Repo + 1 in henemm-infra
- Estimated LoC: S0 Beobachtbarkeit ~40, S1 Vorwärmen ~80-120, Tests ~100 → ~+220 produktiv/Test (Limit 250 knapp; S2 nur bei Bedarf → dann `loc_limit_override 500`)
- Risk Level: MEDIUM — geteilter Pfad mit geplantem Briefing-Versand, Alarm-Lauf und Ortsvergleich (DWD-Cache); Mail-Inhalt muss bit-identisch bleiben (Renderer-Gate); DWD-Last steigt kurzzeitig.

### Technical Approach (Empfehlung)
1. **Teil a (Betrieb, kein Produktcode)** als ACs in diesem Workflow (themenweise abschließen, nicht abspalten):
   SMS-Nachversuch auf Staging mit echter SMS neu messen (zweite seven.io-Nummer) → Prod-Hooks registrieren (seven.io + Stalwart `message-ingest.ham`)
   → `missed_total`-Check in `check-gregor20.sh` (in Kopie entwickeln, dann infra) → Runbook korrigieren.
2. **S0 Beobachtbarkeit zuerst:** Dauer je Befehl (Eingang→Übergabe an den Versand-Provider) + Phasenzeiten + DWD-Fensterzeit im Journal.
   Ohne sie ist keine Zielgröße auf Staging prüfbar.
3. **S1 DWD-Tagesfenster parallel vorwärmen** (Zieltag, Nacht, +1, +2; Pool 2–3 Tage gleichzeitig, `copy_context`), Ergebnis verwerfen,
   Hauptabruf trifft danach den Cache. Inhalt unverändert. Geschätzt HEUTE kalt 35–58 s → ~20–30 s.
   Einbau im geteilten `_send_trip_report_outcome` (nützt auch dem geplanten Briefing) vs. nur On-Demand → Tech-Entscheidung in der Spec
   (Empfehlung: geteilt, da inhaltsneutral; DWD-Last durch Pool begrenzt).
4. **S2 Segmentschleife parallel** (`parallel_fetch.fetch_ordered`) **nur**, wenn S1 auf Staging das Ziel verfehlt.
- Verworfen: Hintergrund-Vorwärmen rund um die Uhr (DWD-Dauerlast, 250+ LoC); eigener CAPE/SNOWGRID-Cache (durch S2 ersetzbar, ändert Cache-Semantik für Alarm/Ortsvergleich);
  Poll-Lock entkoppeln (Zustellreihenfolge/Kanaltreue, Gewinn 0 s Rechenzeit).
- **Keine Inhaltskürzung** (Nacht, Ausblick, Gewitter +1/+2, Ensemble bleiben). Weniger Stunden für +1/+2 wäre eine Datenänderung → nur als PO-Entscheidung, nicht Teil des Plans.

### Variantenvergleich (Schätzung auf gemessener Basis)
| Hebel | HEUTE kalt (35–51 s) | MORGEN kalt (37 s) | LoC | Risiko |
|---|---|---|---|---|
| 1 Fenster parallel vorwärmen | −15–25 s | −8–12 s | 80–120 | mittel (DWD-Bandbreite, ≤20 Verbindungen) |
| 1b Hintergrund-Vorwärmen | −25–35 s | ≈ | 250+ | hoch — verworfen |
| 2 Segmentschleife parallel | −5–10 s | −3–6 s | 60–90 | mittel (Rate-Limits, Retry-Block erhalten) |
| 3 CAPE/SNOWGRID-Cache | −3–7 s | −2–4 s | 80–100 | mittel — verworfen |
| 4 Lock entkoppeln | 0 s | 0 s | 150+ | hoch — verworfen |

### Befunde gegen den Plan
- Nicht gemessen, ob DWD bei mehr parallelen Verbindungen schneller wird (#2554 wählte 5er-Pool, weil mehr nichts brachte) → S1 kann an Bandbreite scheitern;
  vor der Spec-Zahl Probelauf 2 vs. 4 Fenster parallel im Harness.
- DWD-Fenster schwankt 6–30 s auch nach S1 → Zielgröße als Median über ≥5 Läufe + harte Obergrenze.
- `GZ_PARALLEL_FETCH_WORKERS=8` teilen sich alle Aufrufer; Aufruf aus Worker-Thread läuft inline seriell (Docstring `parallel_fetch.py`).
- 512-URL-LRU vs. 415 Dateien/Trip → Verdrängung durch parallele Alarm-/Ortsvergleichsläufe.
- Prod-Prozess läuft dauerhaft; der 15-min-Alarmzyklus hält evtl. das Zieltag-Fenster schon warm → Prod könnte schneller sein als Staging (nicht gemessen).

### Open Questions
- [ ] **Zielgröße/Messintervall** (Spec): gemessen ab Eingang beim Core (Webhook/Poll-Übernahme) bis Übergabe an den Versand-Provider; Satellit/Garmin-Laufzeit liegt außerhalb.
      Vorschlag Issue: ohne Wetterabruf < 30 s, mit Wetterabruf < 60 s (Median ≥5 Staging-Läufe kalt).
- [ ] **Lock-Kopplung:** HELP während laufendem HEUTE desselben Kanals wartet bis Lock-Ende (+Kick). AC muss „HELP während HEUTE" explizit messen
      (bei HEUTE < 30 s hält dann auch HELP < 60 s; reicht das, oder muss HELP auch dann < 30 s?).
- [ ] Vorwärmen nur On-Demand oder im geteilten Briefing-Pfad (Tech-Entscheidung, Empfehlung: geteilt).
- [ ] 512-URL-Cache-Kapazität anheben? (Speicher vs. Verdrängung — messen)
