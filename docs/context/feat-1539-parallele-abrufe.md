# Context: feat-1539-parallele-abrufe

## Request Summary
Issue #1539 (Epic #2138): Wetterabrufe je Ort/Etappe laufen seriell; mit wachsender Nutzerzahl
überschreiten Alarm-Läufe ihr Zeitfenster, Ticks fallen aus. PO-Einordnung 2026-08-06: Dauer eines
Einzellaufs unkritisch — entscheidend ist, dass die Architektur skaliert.

Repo-Stand der Erhebung: `1554587be`.

## Korrekturen gegen den Ticket-Text (nachgemessen)
- Radar-Jobs laufen im **5-Minuten-Takt** (`3-58/5`, `internal/scheduler/scheduler.go:279,282`), nicht 15 Min.
  Im 15-Min-Takt: alert, compare-alert, compare-official, data_write_selftest; dazu stündlich briefing_dispatch.
- DWD-Gewitter-Zeitgrenze heute **150 s** (`dwd.py:130`, #1531), Météo-France 45 s, ICON-EU 25 s, Geosphere 3 s/Anfrage.
- `ALERT_RUN_DEADLINE` **180 s** (`trip_alert.py:71`), Radar-Laufgrenze 45 s (`:76`).
- Messung Produktion 2026-08-15 (Kommentar #1539): **heute fallen keine Ticks aus** — es geht um Skalierung,
  nicht um einen akuten Ausfall. Wiedervorlage-Regel: vor jeder Aussage „nicht dringend" neu messen.
- `segment_weather.py:~195` ist der Einzelabruf, keine Schleife; die Schleifen sitzen in den Aufrufern.

## Wo seriell gearbeitet wird
**Go** — `runForAllUsers` (`scheduler.go:318`) iteriert Nutzer seriell (`:355`), rotiert (`rotateUsers:423`).
#2149 B: Wartebudget je Nutzeraufruf (`callUserWithBudget:482`); bei Ablauf läuft der Aufruf in einer
Goroutine weiter, Schleife geht weiter (`:511-513`). Nutzer mit laufendem Vorlauf wird übersprungen (`:458`).
Budgets (`:241-248`): Alarm warten 300 / Lauf 720 / Deckel 1800 s; Briefing 600/1440; Radar 240/270/600.
Go-HTTP-Client 3000 s (`:226`). Regel ADR-0038: Python-Grenze + längster Einzelschritt ≤ Go-Wartebudget.

**Python** (`api/routers/scheduler.py`):

| Go-Job | Endpoint | Schleifen (alle seriell) |
|---|---|---|
| alert_checks | `/alert-checks` :61 | Trips `trip_alert.py:1066`; Etappen `_fetch_fresh_weather:2840`; amtl. Warnungen `:3028` |
| radar_alert_checks | `/radar-alert-checks` :115 | Trips `:1922`; Zonenpunkte `:2173` |
| compare_alert_checks | `/compare-alert-checks` :88 | Presets `compare_alert.py:197`; Orte `:533` |
| compare_radar_alert_checks | :123 | Presets `compare_radar_alert.py:164`; Orte `:538` |
| compare_official_alert_checks | :133 | Presets `compare_official_alert.py:106`; Orte `_detect:395` |
| trip_reports_hourly | `/trip-reports` | Trips `trip_report_scheduler.py:604`; Etappen `_fetch_weather:2361` (`fail_fast` :2360) |

compare_alert und compare_official haben **keine** Lauf-Zeitgrenze.

## Bestehende Parallelität (Muster zum Wiederverwenden)
- `src/services/comparison_parallel.py:118` — ThreadPoolExecutor, `MAX_PARALLEL_LOCATIONS = 4` (`:42`,
  wegen geteiltem Météo-France-Konto); setzt `call_source` im Worker explizit (`:73`, ContextVar wird
  nicht vererbt). Genutzt von Vorschau (`compare_preview_service.py:170`, #1765 B1), Versand
  (`scheduler_dispatch_service.py:527`) und Sofortvergleich (`api/routers/compare.py:80`, #1765 B1b).
- `src/services/stage_weather.py:180` — Pool `min(len, 8)`, #1212, nur interner Etappen-Endpoint.
- **Kein Alarmpfad und nicht der Trip-Briefing-Pfad sind parallelisiert.**
- Wichtig: Die Scheduler-Endpoints sind `def`-Handler → laufen bereits heute im anyio-Threadpool
  nebenläufig (ein uvicorn-Prozess, kein CapacityLimiter). Die Races unten existieren **schon jetzt**.

## Thread-Sicherheit geteilter Zustände
| Zustand | Datei | Stand |
|---|---|---|
| Wetter-Cache | `weather_cache.py` | In-Memory, Lock, TTL 600 s; **kein Request-Dedupe** (`segment_weather.py:152/237`) |
| Gewitterfenster-Cache | `providers/thunder_window_cache.py` | In-Memory, Lock, kein Dedupe |
| Radar-Cache | `radar_cache.py` | In-Memory, Lock, TTL 240 s |
| ForecastBudgetGate | `forecast_budget.py` | fcntl + `os.replace`; `allow()`/`record_call()` nicht atomar (Überschießen); fail-open bei Lock-Timeout 2 s (`file_lock.py:28`) ⇒ Aufrufe ungezählt |
| MeteoAlarm-Budget | `official_alerts/meteoalarm_budget.py` | gleiches Muster, Tagesbudget 100 |
| Warn-Feed-Caches | `official_alerts/warn_egress.cached_fetch:389` | Modul-dict ohne Lock/Dedupe ⇒ Thundering Herd (**C4-64**, dpc 4,6-MB-ZIP) |
| Modell-Verfügbarkeit | `providers/openmeteo.py:357-360` | `write_text` ohne `os.replace` (**C4-63**); abgelaufen ⇒ jeder Fetch startet Auto-Probe (`:1239-1243`) |
| Alarm-Log | `alert_log._append:536-548` | RMW **ohne Lock** ⇒ Eintragsverlust schon heute möglich |
| Alarm-/Snapshot-Zustand | `alert_state.py:77`, `weather_snapshot.py`, `compare_weather_snapshot.py` | `write_text` ohne Lock/`os.replace` |
| Throttle/Check-State | `throttle_store.py`, `alert_check_state.py` | fcntl + `os.replace` — in Ordnung |

## Beobachtbarkeit
- `skipped_since_last_run`/`last_skipped_at` (`scheduler.go:48`, `recordRun:887`, `overlapField:1101`).
- `last_run` ohne Dauer (`jobResult :35`). Je-Nutzer-Zähler `usersField:1122`.
- Python liefert `duration_s` für Trip-Alarm/Radar (`scheduler.py:80,107`), Go wertet es nicht aus;
  Compare-Pfade liefern keine Dauer.

## Existing Specs / ADRs
ADR-0075 (Tagestopf), 0038 (Zeitgrenze Nutzerlauf), 0070 (Wartegrenze), 0082 (Radar-Takt), 0031, 0083, 0036
(Nebenläufigkeitsschutz), 0076, 0018, 0047/0057, 0003.
Specs: `fix_1765_b1_compare_vorschau_parallel.md`, `fix_1765_b1b_versand_sofortvergleich_parallel.md`,
`fix_1447_s1_alarm_lauf_zeitgrenze.md`, `fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md`,
`fix_2149_scheduler_budget_teilb.md`, `fix_2261_a2s1_alarmlauf_reihenfolge.md`, `feat_2261_a2s2_radar_takt.md`,
`fix_1329_forecast_cache_budget.md`, `forecast_budget_je_nutzer.md`, `fix_1448_s2_dateisperren.md`.

## Tests (Bestand)
Parallel: `tests/unit/test_comparison_parallel.py`, `test_compare_versand_parallel.py`, `test_sofortvergleich_parallel.py`.
Zeitgrenze/Fairness: `tests/tdd/test_alert_run_deadline.py`, `test_alert_run_fairness.py`, `test_radar_alarmlauf_*`.
Budget/Cache: `tests/unit/test_forecast_budget_gate.py`, `test_forecast_cache_sharing.py`, `test_thunder_shared_window_cache.py`.
Go: `job_overlap_test.go`, `user_call_wait_budget_test.go`, `run_budget_rotation_test.go`, `multi_user_test.go`.
Kein Test prüft Thread-Konkurrenz auf `alert_log`, `alert_state`, `warn_egress`, Verfügbarkeits-Cache.

## Offene verwandte Nebenbefunde
C4-63, C4-64 (an #1539), C4-61/#2234 (Compare-Pfad ohne Forecast-Cache), C4-62 (Thread-Ausnahmen in pytest nur Warnung).

## Risks & Considerations
1. **Kontingent:** nicht-atomares Prüfen/Zählen + fail-open ⇒ mehr Threads = Überschießen und ungezählte Aufrufe;
   ohne Dedupe Doppelabrufe derselben Kachel.
2. **Amtsdienste:** MeteoAlarm-Drossel (~4 s/Anfrage) wirkt nur je Aufruf, nicht threadübergreifend;
   Météo-France-Konto geteilt; dpc/vigilance-Herde (C4-64). Vor Parallelisierung Lock+Dedupe in `cached_fetch`.
3. **ContextVars** (`call_source`, `_fetch_failure_sink`, `_capture_id_sink`) gehen in Workern verloren ⇒
   `contextvars.copy_context().run` nötig, sonst stille Signalverluste.
4. **Reihenfolge-Abhängigkeiten:** Zeitgrenze vor jeder Einheit, `skipped_ids`, Rotation (#2261 A-2 S1),
   `fail_fast` im Briefing, `RadarDeadlineExceeded`-Abbruch setzen serielles Arbeiten voraus.
5. **Seiteneffekte in der Schleife:** Trip-Alarm versendet + schreibt Zustand innerhalb der Trip-Schleife
   (`trip_alert.py:1136-1170`). Compare-Pfade trennen Erkennen/Versenden ⇒ dort nur Erkennung parallelisierbar.
6. **Wo der Engpass wirklich sitzt:** Go-Nutzerschleife je Job (Laufbudget 720/270 s) ist der Skalierungsdeckel,
   nicht allein die Python-Ortsschleife. Alternative/Ergänzung: begrenzter Fan-out über Nutzer in Go —
   belastet den Python-Threadpool (~40) und alle Races oben.

## Messung Produktion 2026-10-07 (Phase 2)
- `/api/scheduler/status`: kein `overlap`-Block in irgendeinem Job, 3 Nutzer, alle `last_run` ok.
- **Aber der Go-Überlaufzähler ist blind für den eigentlichen Schaden:** Python bricht den Alarmlauf
  intern an der Zeitobergrenze ab und lässt Trips ungeprüft. `journalctl -u gregor-python`, 7 Tage:
  **29× „Zeitobergrenze … überschritten" für `user_id=henning` — jedes Mal checked=2 skipped=2**
  (27× noch mit alter 90-s-Grenze, 1× 180 s, 1× Radar 45 s; skipped_ids `74de939c`, `gr221-mallorca`).
  Häufung morgens 04:30–10:30 Serverzeit CEST (01.–06.10.). Ein Nutzer mit 4 Trips reißt die Grenze bereits.
- Trip-Alarm-Laufdauern (Log „Lauf beendet nach Xs", n=2012): p50 0,01 s · p90 13,8 s · p95 37 s ·
  p99 104 s · max 215 s. Andere Jobs loggen keine Dauer (Radar liefert `duration_s` nur in der Response,
  Compare-Pfade und `/trip-reports` gar nicht) ⇒ Beobachtbarkeitslücke.
- Aufschlüsselung Lauf 03.10. 06:00–06:02 (henning, 144 s): Etappen strikt nacheinander, je Etappe
  12–50 s (Open-Meteo 503-Retries 2+2+4 s, `de_direct`-Gewitter, Geosphere-ReadTimeout+Retry, und
  10–30 s unprotokollierte Lücke zwischen „geosphere gefüllt" und nächster Etappe). 6 Etappen ⇒ ~2,5 min
  für EINEN Trip.
- Folge für die Einordnung: Die Aussage „heute fallen keine Ticks aus" (Kommentar 2026-08-15) gilt nur
  für den Go-Zähler. Auf Trip-Ebene entsteht schon heute Schaden (Prüfung einzelner Trips fällt aus;
  Rotation #2261 A-2 S1 verteilt ihn nur).
- Dauer je Etappe hängt am langsamsten Quellabruf; Parallelisierung der Etappen-Schleife
  (`trip_alert._fetch_fresh_weather:2840`) ist der direkteste Hebel.

## Code-Erhebung (Phase 2)
- ContextVars: nur 3 — `warn_egress.py:57 _fetch_failure_sink`, `:120 _capture_id_sink`,
  `call_log.py:66 _call_source_override`. Worker müssen sie per `contextvars.copy_context().run` erben.
- `comparison_parallel.py` ist an `ComparisonEngine`/Orte gekoppelt, nicht generisch (Pool :118, Grenze 4 :42,
  Reihenfolge per Index :115-132, Teilausfall → `LocationResult(error)` :151-158).
- Trennbarkeit Abruf/Auswertung: trip_alert-Etappen ja (keine Writes in der Schleife :2840-2872);
  compare_radar ja (Deadline-Exception muss erhalten bleiben); trip_report `_fetch_weather` bedingt
  (`fail_fast`/Retry gekoppelt); compare_alert und compare_official speichern Zustand IN der Schleife
  ⇒ dort nur der Abruf vorziehbar.

### Nachmessung nach Grenzanhebung (Advisor-Prüfung)
- `ALERT_RUN_DEADLINE_SECONDS` 90→180 per `972372d23` (2026-10-04, #2261 A-2 S1); auf Prod noch
  bis 05.10. 04:32 mit 90 s geloggt, ab 06.10. mit 180 s. **Rate: vorher ~5 Abbrüche/Tag, seitdem in
  ~1,5 Tagen 1× Trip-Alarm (06.10. 09:03, 180 s) + 1× Radar (06.10. 09:34, 45 s).** Schaden gedämpft,
  nicht beseitigt — und das bei EINEM Nutzer mit 4 Trips. Nicht als „29/Woche" verkaufen.
- Die 10–30-s-Lücke je Etappe ist **Geosphere: ReadTimeout nach 30 s + Retry 2 s** (ungefiltertes
  Fenster 03.10. 06:00:42–06:01:33). Reines Warten auf externe Dienste ⇒ Abruf-Parallelisierung wirkt;
  Dedupe allein hilft nicht (je Etappe eigener Punkt, auch wenn 2–4 km nah).
- Open-Meteo lieferte 503 „overloaded" ⇒ Fan-out braucht eine Nebenläufigkeitsgrenze je Provider,
  sonst vervielfachen sich Retries.
- `checked`/`skipped` (`trip_alert.py:1066-1075`): `skipped` = nicht erreicht, unabhängig davon, ob der
  Trip aktiv ist. Ob `74de939c`/`gr221-mallorca` im Datumsfenster liegen, ist von `hem` aus nicht lesbar
  (Prod-Daten nicht unter `data/users/`). Offen, aber nicht entscheidungsrelevant: Der Mechanismus
  trifft aktive wie inaktive Trips gleich.
- **Beobachtbarkeitslücke (Pflicht-Scope):** Go-Status meldet `alert_checks.users.partial: 0` und keinen
  `overlap`, obwohl Python Trips ungeprüft lässt. Das im Ticket genannte Wirkmaß
  `skipped_since_last_run` misst den Schaden nicht.

## Analysis

### Type
Feature (Skalierungs-Architektur) mit nachgewiesenem Schaden schon heute: Trip-Alarmläufe brechen an der
Zeitgrenze ab und lassen Trips ungeprüft, und die Überwachung zeigt dabei Grün.

### Technical Approach (Empfehlung Tech Lead)
Variante „Kombination", in fester Reihenfolge: **erst messbar machen, dann Schreibzugriffe absichern,
dann EIN gemeinsamer, begrenzter Abruf-Baustein, dann die Schleifen parallel umstellen.**
- **Ein** prozessweiter Abruf-Baustein `src/services/parallel_fetch.py`, z. B. `fetch_ordered(items, fn,
  *, provider_gate, deadline_at)`:
  - eigener, modulweiter Executor (~8 Worker, nicht der anyio-Pool)
  - Semaphore je Provider: Open-Meteo ~3, Météo-France 4, MeteoAlarm 1; die Zahlen in Phase 3 aus der Messung festlegen
  - `contextvars.copy_context().run` für alle 3 ContextVars
  - Ergebnisse in Index-Reihenfolge
  - Teilausfall je Element als Fehlerobjekt
  - Zeitgrenze: nicht gestartete Aufgaben fallen weg; ADR-0038 bleibt erhalten
  - Single-flight je Cache-Schlüssel in `segment_weather.py:152/237`
- Parallel laufen nur **Abrufe innerhalb eines Trips oder Vergleichs** (Etappen, Zonenpunkte, Orte). Trips
  und Nutzer bleiben seriell. So bleiben Reihenfolge und Rotation (#2261 A-2 S1), `skipped_ids`, Versand
  und State-Write unverändert.
- Fan-out über Nutzer in Go (S7) nur mit Messauslöser: `not_reached_budget` aus S0 > 0 im Echtbetrieb.
  Der heutige Schaden liegt innerhalb eines Nutzers, und Go-Fan-out würde nur die Last auf Python und
  die Races vervielfachen.
- Ein 503 bei Open-Meteo darf nicht vervielfacht werden. Retries laufen deshalb unter der
  Provider-Semaphore, dazu kommt eine kurze Sperre je Provider nach Überlast; Detail in Phase 3.

### Scheiben (alle innerhalb #1539, keine Abspaltung)
| Scheibe | Inhalt | LoC ~ |
|---|---|---|
| **S0 Beobachtbarkeit** | Go `triggerResponseBody` (`scheduler.go:948`) übernimmt `reason/skipped/skipped_ids/duration_s`; `jobResult` (`:35`) bekommt die Dauer aus der Go-Wanduhr für ALLE Jobs; kumulativ `deadline_aborts_total` + `last_deadline_at` neben `usersField` (`:1122`). Python: `duration_s` + `status: partial` für compare-alert, compare-official, compare-radar, trip-reports (`api/routers/scheduler.py:55-140`), Logzeile „Lauf beendet nach Xs" in allen Pfaden, Dauer je Trip/Etappe | ~150 |
| **S1a Atomare Schreiber** | `alert_log._append` (`:536-548`) mit Lock + `os.replace`; gemeinsamer `atomic_write_json` für `alert_state.py:77`, `weather_snapshot.py`, `compare_weather_snapshot.py`; C4-63 `openmeteo.py:357-360` + Lock um die Auto-Probe `:1239-1243` | ~120 |
| **S1b Cache & Budget** | C4-64 `warn_egress.cached_fetch:389` mit Lock + Single-flight; `ForecastBudgetGate.reserve()` atomar (`forecast_budget.py:100/141`); Zähler für ungezählte Aufrufe bei fail-open; `meteoalarm_budget.py` analog | ~130 |
| **S2 Baustein** | `parallel_fetch.py` (s. o.) + Single-flight im Wetter-Cache | ~160 |
| **S3 Trip-Alarm-Etappen** | `trip_alert._fetch_fresh_weather:2840-2872` über den Baustein; Auswertung bleibt seriell; **größter Nutzen** | ~90 |
| **S4 Radar** | Zonenpunkte `trip_alert.py:2173`, `compare_radar_alert.py:538`; `RadarDeadlineExceeded` aus dem Worker im Hauptthread neu werfen | ~100 |
| **S5 Trip-Briefing** | `trip_report_scheduler._fetch_weather:2361`; Kopplung mit `fail_fast` (`:2360`) wird in Phase 3 entschieden | offen |
| **S6 Compare-Alarm/Amtlich** | `compare_alert.py:533`, `compare_official_alert.py:395`; nur Abruf vorziehen, da Zustand IN der Schleife geschrieben wird; dabei Laufgrenze ergänzen (heute keine) | offen |
| **S7 Go-Nutzer-Fan-out** | nur mit Messauslöser (s. o.), begrenzt 2–3, nur Alarm-Jobs | — |

Lieferung in mehreren Workflows à ≤250 LoC, z. B. S0+S1a → S1b+S2 → S3+S4 → S5/S6.
**Der erste Workflow (dieser) = S0 + S1a.**
Begründung: S0 liefert die Vorher-Messung und schließt die Überwachungslücke. S1a ist Vorbedingung,
weil heute schon parallel laufende `def`-Handler Einträge verlieren können. Beide sind risikoarm und
ändern das Abrufverhalten nicht.

### Affected Files (Workflow 1: S0 + S1a)
| File | Change | Description |
|---|---|---|
| `internal/scheduler/scheduler.go` | MODIFY | Antwortkörper, Dauer je Job, kumulative Abbruch-Zähler im Status |
| `internal/scheduler/*_test.go` | CREATE/MODIFY | Status zeigt Abbruch + Dauer |
| `api/routers/scheduler.py` | MODIFY | `duration_s`/`partial` für alle Alarm-/Report-Routen |
| `src/services/compare_alert.py`, `compare_official_alert.py`, `trip_report_scheduler.py` | MODIFY | Laufdauer messen/loggen |
| `src/services/trip_alert.py` | MODIFY | Dauer je Trip/Etappe loggen |
| `src/services/alert_log.py` | MODIFY | RMW unter Lock + atomar |
| `src/services/alert_state.py`, `weather_snapshot.py`, `compare_weather_snapshot.py` | MODIFY | atomarer Schreibhelfer |
| `src/providers/openmeteo.py` | MODIFY | C4-63 atomar + Probe-Lock |
| `tests/…` (nach Verhalten benannt) | CREATE | Barrier-Konkurrenztests, Status-Sichtbarkeit, zwei Nutzer |

### Scope Assessment
- Gesamt #1539: ~750 LoC über 3–4 Workflows. Workflow 1: ~270 LoC ⇒ `loc_limit_override` voraussichtlich nötig.
- Risiko: **MITTEL** — zentrale Alarmpfade; S0/S1a ändern aber kein Abrufverhalten. Das eigentliche
  Risiko (Nebenläufigkeit) liegt in S2–S4.

### Risiken (für spätere Scheiben)
#2261-Rotation (gelöst: nie Trips parallel) · `fail_fast` · `RadarDeadlineExceeded` darf nicht verschluckt
werden · Seiteneffekte in der compare_official-Schleife · Multi-User-Isolation (Test mit zwei Nutzern) ·
C4-62: Thread-Ausnahmen werden in neuen Tests zum Fehler (`filterwarnings`) · Spitzenlast Open-Meteo
(Tageszahl der Calls darf nicht steigen).

### Wirkungsnachweis
- Vorher (07.10.): siehe Messung oben.
- Nachher: `deadline_aborts_total` und `duration_s` je Job im Status; 7 Tage Prod
  `grep -c Zeitobergrenze` → ~0; p95/p99 der Laufdauer.
- Schutzgrößen, die nicht schlechter werden dürfen: Open-Meteo-503/Tag, Calls/Tag, `cache_hits`,
  ungezählte Calls, MeteoAlarm-Tagesbudget.
- `skipped_since_last_run` misst nur Überlappung, ist also kein Wirkmaß.

### Open Questions (technisch, klärt Phase 3 selbst — keine PO-Frage)
- [ ] Warum zeigt der Go-Status `partial: 0`? Schnappschuss wird vom nächsten Lauf überschrieben, oder `aggregateLocked`? Ursache im Code belegen.
- [ ] Rundet der Wetter-Cache-Schlüssel so, dass 2–4 km entfernte Etappen eine Kachel teilen?
- [ ] Wie hoch werden die Provider-Semaphoren gesetzt? Per Messung bestimmen (S2).
- [ ] Wie verhält sich `fail_fast` im Briefing (S5)?

## RED-Übergabe an /50-implement (2026-10-08)

RED-Tests (alle rot gegen den Stand vor GREEN; Artefakte lokal unter `docs/artifacts/feat-1539-parallele-abrufe/`, gitignored):

- **Go AC-1–5:** `internal/scheduler/deadline_abort_visibility_test.go` — bleibt bis GREEN **ungetrackt** (touched_tests_gate). Liest den Status als `map[string]any`. Go-Binär: `/usr/local/go/bin/go` (nicht im PATH). AC-3 nutzt Fake-Server 800 ms / Wartebudget 50 ms, erwartet `duration_s < 0.4`, Einsammeln über `harvestLateResult` darf nicht doppelt zählen.
- **Python AC-6/7:** `tests/tdd/test_scheduler_run_duration_reporting.py`, `tests/tdd/test_trip_alert_duration_logging.py`. Laufen mit `--disable-socket --allow-unix-socket` (wie CI, TestClient braucht Unix-Socketpair).
  - `checked` bei `/compare-alert-checks` und `/compare-official-alert-checks` = Anzahl geprüfter Presets des Nutzers (Test erwartet 1 bei einem Preset).
  - Je Route **genau eine** Zeile „Lauf beendet nach … user_id=…“ — nicht in Router UND Service loggen.
  - Trip-Dauerzeile: Trip-Name + `\d+(\.\d+)?\s*s`, genau eine je Trip; Etappenzeile: `Etappe <segment_id>` + Dauer in s, genau eine je Etappe. Zeilen mit „Lauf beendet nach“ zählen nicht als Dauerzeile.
  - **Bestandstest anpassen:** `tests/test_dispatch_status_delivery.py` vergleicht die Antwort per `==` mit genau drei Feldern (`{"status","count","failed"}`) — wird mit zusätzlichem `duration_s` rot; auf Teilmengen-Vergleich umstellen.
- **Python AC-8–11:** `tests/tdd/test_alert_log_concurrent_append.py`, `test_state_writers_atomic.py`, `test_openmeteo_availability_probe_single.py`, `test_alert_log_lock_timeout_is_loud.py`.
  - AC-9 erzeugt den Fehler mitten im Schreiben über `RLIMIT_FSIZE` (16384 B) im Kindprozess, weil alle Schreiber heute `json.dumps` vor dem Öffnen aufrufen.
  - AC-10 ersetzt `OpenMeteoProvider._request` (HTTP-Grenze) durch zählende Funktion, zählt am Endpoint `/v1/ecmwf`; `_enrich_thunder` ist No-op.
  - **AC-11 erwartet diese Namen:** Modulkonstante `services.alert_log.ALERT_LOG_LOCK_TIMEOUT_SECONDS` (Wartefrist, Standard 30 s, Test setzt 0,3 s) und int-Prozesszähler `services.alert_log.alert_log_lost_entries`. ERROR-Log über Logger `services.alert_log` mit vollständigem Eintrag als JSON (inkl. `sent_at`).
- **Monitor AC-12:** Probe `docs/artifacts/feat-1539-parallele-abrufe/ac12/ac12_probe.sh <kopie>` (README im Kopf, Fixtures in `ac12/fixtures/`). Nie gegen das Live-Skript (Probe verweigert). Fälle a (Zuwachs) und d (Neustart mit total>0 ⇒ WARN mit Zuwachs ab Basis 0) sind rot, b/c grün.
  - Achtung: Abschnitt 2 von `check-gregor20.sh` überschreibt die Zustandsdatei bei jedem Lauf mit nur den fehlerhaften Jobs — der deadline-Basiswert muss diesen Rückschreib-Schritt überleben, sonst warnt der Monitor alle 5 Min. Die Probe läuft jeden Fall zweimal und bewertet den zweiten Lauf.
  - Schwäche der Probe (für den Adversary): eine Zeile „(1 -> 3)“ besteht Fall d zufällig über die „1“.
