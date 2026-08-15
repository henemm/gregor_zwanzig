# Context: Vorschau-Laufzeit (#1765 + #1839)

**Workflow:** `fix-1765-1839-vorschau-laufzeit` · **Typ:** feature (Full Process) · **Erstellt:** 2026-08-15

## Request Summary

Die Vergleichs-Vorschau (#1765) lädt bei 3+ Orten nie, die Trip-Vorschau (#1839) bricht beim
ersten (kalten) Aufruf nach 30 s mit 502 ab. PO-Vorgabe: **Ursache angehen, nicht Timeouts
hochsetzen.** Die gemeinsame Wurzel #1539 (sequenzielle Orts-/Etappenverarbeitung) ist
laut PO-Messung vom 2026-08-15 **nicht akut** (keine übersprungenen Scheduler-Ticks) und
bleibt als Architektur-Ticket offen; die Vorschau-Tickets werden über eine Parallelisierung
**des Vorschau-Pfads** angegangen — echter Teilschritt, ohne #1539s `[triage:po]`-Entscheidung
vorwegzunehmen.

## Drei trennbare Ursachen (gemessen am Code, nicht aus den Ticketkörpern übernommen)

### U1 — Die Vorschau blockiert den einzigen Python-Prozess

`api/routers/preview.py` deklariert alle vier Handler `async def` (Zeilen 30, 56, 86, 129),
enthält aber **kein einziges `await`** (verifiziert per `grep -n "await\|async def"`). Die
darunterliegenden Wetterabrufe sind synchrone `httpx.Client`-Aufrufe. Ein `async def`-Handler
läuft bei Starlette **direkt im Event-Loop-Thread** — nicht im Threadpool, den `def`-Handler
bekommen. Uvicorn läuft ohne `--workers` (ein Prozess, ein Loop).

Folge: Während einer Vorschau ist der gesamte Python-Core taub. Der Go-Health-Handler gibt
Python 2 s (`internal/handler/proxy.go:19`) → `python_core: unavailable`, `status: degraded`.
**Das erklärt den unnötigen Neustart von `gregor-python-staging` am 2026-08-12 vollständig**
(#1765, Kommentar 1) und macht `/api/health` als Ausfallsignal unbrauchbar.

#### U1 ist eine Klasse von 13 Handlern, nicht ein Vorschau-Sonderfall

Ausgezählt über den gesamten `api/`-Baum (AST, Dekorator `router.*`/`app.*`):

| | Anzahl |
|---|---|
| Route-Handler `def` (laufen im Starlette-Threadpool — **richtig**) | **22** |
| Route-Handler `async def` (laufen im Event-Loop) | **14** |
| davon **ohne jedes `await`** ⇒ blockieren den Loop grundlos | **13** |

Der Hausstil ist also bereits `def`; die 13 `async def`-Handler ohne `await` sind die Abweichung.
Einziger berechtigter `async def`: `api/routers/gpx.py:23 parse_gpx` (Datei-Upload, nutzt `await`).

**Zweifach gemessen, gleiches Ergebnis** — einmal statisch per AST über `api/**/*.py`, einmal
zur Laufzeit an der fertig gebauten App (`app.routes` → `inspect.iscoroutinefunction`).
Die Laufzeit-Zählung war nötig, weil eine reine AST-Zählung Dekorator-Formen übersehen kann
(anders benannte Router-Variablen, `add_api_route`). Beide Wege nennen **dieselben 13 Handler**.

#### Die Mechanik ist experimentell belegt, nicht nur hergeleitet

Wegwerf-Experiment (zwei identische Mini-Apps, uvicorn im Thread, ohne Netz):

| Aufbau | `/health` **während** laufender Arbeit |
|---|---|
| `async def` + blockierende Arbeit (heutiger Zustand) | **Timeout nach 2,02 s** |
| `def` + identische blockierende Arbeit (Vorschlag) | **HTTP 200 nach 0,03 s** |

Die 2,02 s sind genau die Grenze, die der Go-Health-Handler setzt
(`internal/handler/proxy.go:19`). Damit ist die Wirkkette
`async def ohne await` → Loop blockiert → `/health` stumm → `degraded` **geschlossen belegt**.
Derselbe Aufbau ist zugleich der Bauplan für den U1-Test: deterministisch, netzfrei, ~7 s Laufzeit.

Die 13 blockierenden Handler:

| Datei:Zeile | Handler | Anmerkung |
|---|---|---|
| `api/routers/preview.py:30,56,86,129` | `preview_email`, `preview_sms`, `preview_compare`, `preview_telegram` | **gemeldetes Symptom** (#1765/#1839) |
| `api/routers/internal.py:56` | `stages_weather` | Cockpit-Etappenwetter — nutzt **innen** einen `ThreadPoolExecutor` und blockiert dann den Loop beim Warten auf die Ergebnisse |
| `api/routers/internal.py:30` | `loaded_trip` | |
| `api/routers/validator.py:167,181,244,272,317,339` | u.a. `alert_preview`, `compare_email_preview` | Validator-Pfad |
| `api/routers/notify.py:19` | `test_notify` | |

⇒ Würde Scheibe A nur die vier Vorschau-Handler umstellen, bliebe der Core weiterhin durch
das Cockpit-Etappenwetter und die Validator-Endpunkte taub. Die Reparatur ist mechanisch
(das Wort `async` entfällt, es gibt kein `await`, das brechen könnte) — der Umfang der
Klasse ist daher eher ein Argument dafür, sie **ganz** zu erledigen, als für eine Teilmenge.

### U2 — Die Vorschau erbt die Wiederhol-Politik des Versands

`preview_service.py:173` ruft `scheduler._fetch_weather(segments, provider=provider)`. Dort:
`fail_fast` ist eine **lokale Variable**, hart auf `False`, kein Parameter
(`trip_report_scheduler.py:1953`) → 3 Versuche je Segment mit `time.sleep`
(`FETCH_RETRY_ATTEMPTS = 2`, `FETCH_RETRY_BACKOFF_SECONDS = 1`, Zeilen 73–74).
Darunter die Provider mit `RETRY_ATTEMPTS = 5` und `wait_exponential(min=2, max=60)`.
Für einen Nutzer, der auf einen Reiter starrt, ist das falsch dimensioniert — die Werte
stammen aus dem asynchronen Versandpfad, wo Wartezeit unkritisch ist (PO-Einordnung in #1539).

### U3 — Serielle Orts- bzw. Segmentschleife

- Vergleich: `src/services/comparison_engine.py:127` `for loc in locations:` — je Ort bis zu
  drei Netzabrufe (Forecast inkl. Gewitter-Anreicherung; optional Bergfex-Schnee; optional
  amtliche Warnungen via `get_official_alerts_with_status`, Zeile 323).
- Trip: `src/services/trip_report_scheduler.py:1954` `for segment in segments:` in
  `_fetch_weather` (ab Zeile 1917). `segment_weather.py` selbst hat **keine** Ortsschleife —
  es verarbeitet genau ein Segment je Aufruf (Netzabruf bei Zeile 195).

### U4 — Der Vergleichspfad hat keinen Grundvorhersage-Cache (bekannt, zurückgestellt, **nicht** Teil dieses Workflows)

Nachgeprüft, weil die Strategiebewertung eine Cache-Aufwärmung erwog:
`get_shared_weather_cache()` / `WeatherCacheService` wird **ausschließlich** von
`src/services/segment_weather.py:67` (Trip-Pfad) und zwei Renderern genutzt.
Der Vergleichspfad (`comparison_engine.py:130` → `fetch_forecast_for_location` →
`ForecastService.get_forecast`) konsultiert **keinen** Cache — `src/services/forecast.py`
enthält kein einziges Vorkommen von „cache".

Konsequenz für die Einordnung von #1765: Die Trip-Vorschau ist nur **kalt** langsam
(#1839: >50 s kalt, 0,65 s warm — der Cache greift). Die Vergleichs-Vorschau ist
**immer** kalt; „lädt nie" ist dort kein Erstaufruf-Problem, sondern der Dauerzustand.
**Diese Ursache wird in diesem Workflow NICHT angegangen.** Drei Gründe, in dieser Reihenfolge:

1. **Sie erklärt den gemeldeten Fehler nicht.** #1765 und #1839 beschreiben beide den
   **ersten**, kalten Aufruf. Ein Cache wirkt strukturell erst ab dem zweiten.
2. **Sie ist eine dokumentierte, bewusste Zurückstellung**, kein Versäumnis:
   `docs/specs/modules/fix_1329_forecast_cache_budget.md:399-407` benennt sie wörtlich als
   „bewusster Scope-Schnitt" und „Folge-Optimierungs-Ticket, kein Korrektheitsproblem".
   Dieselbe Stelle (Zeilen 414-419) nennt `forecast.py` und `trip_forecast.py` als gleich
   gelagerte Fälle. **Das angekündigte Folge-Ticket existiert bis heute nicht** (per
   `gh issue list` gesucht) — gehört als Zeile ins Sammel-Issue #1199, nicht in diesen Workflow.
3. **Der Nutzen wäre für den realistischen Anwendungsfall klein.** `ThunderWindowCache`
   greift **regionsabhängig** (`src/providers/thunder_routing.py:33,47-49`): nur bei Routing
   nach `FR` (Météo-France, `meteofrance.py:613`). Für `DE_ALPEN` — laut Kommentar in
   `thunder_routing.py:33` ausdrücklich Deutschland, Alpenraum **und Österreich**, also der
   Karnische Höhenweg — läuft die Anreicherung über `dwd.py`, und dort gibt es **keinen
   Cache**. Der teuerste Einzelabruf (DWD-Gewitter, Budget 150 s) ist damit bei jedem Aufruf
   voll exponiert, kalt wie warm.

Was beim zweiten Aufruf innerhalb von 600 s tatsächlich entfällt, je Abrufgruppe:

| Abrufgruppe je Ort | gecacht? | Fundstelle |
|---|---|---|
| Grundvorhersage (`ForecastService.get_forecast`) | **nein** | `comparison_engine.py:412-423`, `src/services/forecast.py` (0 Treffer „cache") |
| Gewitter-Anreicherung | **nur bei FR-Routing** | `thunder_routing.py:47-49`; `meteofrance.py:613` (Cache) vs. `dwd.py`/`dwd_eu.py` (keiner) |
| Bergfex-Schnee (optional) | **nein** | `comparison_engine.py:432-441` |
| Amtliche Warnungen (optional) | **ja**, 1800 s | `official_alerts/warn_egress.py:38-39`, `geosphere_warn.py:37,53` |

Nebenbei belegt: Ein Adapter, der Vergleichsorte in den geteilten Cache einhängt, existiert
bereits für die Alarm-Prüfung (`src/services/compare_location_weather_source.py:145-156`) —
ein späteres U4-Ticket hätte also einen Präzedenzfall, aber der Adapter liefert nur den
schmalen Alarm-Ausschnitt (ein Tagesfenster, kein 96-h-Ausblick).

## Related Files

| Datei | Relevanz |
|---|---|
| `api/routers/preview.py` | **U1** — die vier `async def`-Handler ohne `await` |
| `src/services/preview_service.py:173` | **U2** — Einstieg Trip-Vorschau, ruft `_fetch_weather` |
| `src/services/compare_preview_service.py:163` | Einstieg Vergleichs-Vorschau, ruft `ComparisonEngine.run` |
| `src/services/comparison_engine.py:127` | **U3** — Ortsschleife Vergleich |
| `src/services/trip_report_scheduler.py:1917-1975` | **U2+U3** — `_fetch_weather`, Segmentschleife, Retry-Politik |
| `src/services/segment_weather.py:195` | Netzabruf je Segment (Ein-Segment-Funktion) |
| `src/services/stage_weather.py:173` | **Vorbild** — `ThreadPoolExecutor(max_workers=min(len(flat), 8))` über denselben Aufruf |
| `src/providers/call_log.py:41-64` | **Risiko R1** — Quellenzuordnung über `inspect.stack()` |
| `src/providers/thunder_enrichment.py:182` | Gewitter-Anreicherung je Ort |
| `src/providers/dwd.py:119` / `meteofrance.py:114` / `dwd_eu.py` | Gewitter-Zeitbudgets 150 s / 45 s / 25 s |
| `src/providers/thunder_window_cache.py:26,58,153` | Prozess-Singleton, `threading.Lock`, ausdrücklich für Parallelisierung gebaut |
| `src/services/weather_cache.py:91,294` | Prozess-Singleton, `threading.Lock` |
| `src/services/forecast_budget.py:175-215` | `fcntl.flock`, fail-open; `user_briefing` wird nie gedrosselt |
| `internal/handler/preview_proxy.go:52,81` | Go-Timeouts 60 s (Vergleich) / 30 s (Trip) |
| `internal/handler/proxy.go:19` | Health-Timeout 2 s → erklärt `degraded` |

## Existing Patterns

- **Parallelisierung ist im Repo bereits gelebt und spezifiziert:** `stage_weather.py:173`
  nutzt `ThreadPoolExecutor` über `SegmentWeatherService.fetch_segment_weather()` mit
  Best-effort je Segment (`_fetch_one`, Zeilen 52–57). Die Spec
  `docs/specs/modules/stage_weather_python_endpoint.md:57` bezeichnet den Aufruf ausdrücklich
  als „**parallel** via `ThreadPoolExecutor` (flach über alle (Stage,Segment)-Paare; I/O-bound,
  threadsicher)". Dort war **kein neuer ADR nötig** (Zeile 128: ADR-0015 deckt es ab).
- **Thread-Sicherheit wurde vorbereitet:** `thunder_window_cache.py:58-62` begründet den Lock
  wörtlich damit, dass „die Orts-Schleife des Ortsvergleichs parallelisiert werden kann".

## Dependencies

**Upstream (was der Vorschau-Pfad nutzt):** `ForecastService`/`OpenMeteoProvider` →
`_enrich_thunder` → `dwd`/`dwd_eu`/`meteofrance`; `BergfexScraper`;
`get_official_alerts_with_status`; `ThunderWindowCache`, `WeatherCacheService`,
`ForecastBudgetGate`, `call_log`.

**Downstream (wer die zu ändernden Stellen sonst noch nutzt) — das ist der Blast Radius:**

`_fetch_weather` (6 Produktiv-Aufrufer):
`preview_service.py:173` (Vorschau) · `trip_command_processor.py:306` (Inbound-Befehle) ·
`trip_report_scheduler.py:694`, `:1286`, `:2254`, `:2689` (**Versand + Alarme**)

`ComparisonEngine.run` (3 Produktiv-Aufrufer):
`compare_preview_service.py:163` (Vorschau) · `scheduler_dispatch_service.py:451`
(**Versand**) · `api/routers/compare.py:71` (Vergleichsansicht im Frontend)

⇒ Eine Änderung **innerhalb** dieser beiden Funktionen trifft Briefings und Alarme mit.
Der Zuschnitt muss klären, ob die Nebenläufigkeit dort eingebaut oder auf den Vorschau-Pfad
begrenzt wird (z.B. opt-in-Parameter mit Default = heutiges Verhalten).

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/stage_weather_python_endpoint.md` | **Vorbild** für die Parallelisierung (Zeilen 57, 122–124, 126–129) |
| `docs/specs/modules/epic_140_output_vorschau.md` | Ursprungsspec der Vorschau-Endpunkte |
| `docs/specs/modules/compare_channel_preview_dispatch.md` | Vergleichs-Vorschau + Versand |
| `docs/specs/modules/fix_1329_forecast_cache_budget.md` | `ForecastBudgetGate` |
| `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md` | Herkunft des 150-s-Gewitterbudgets |
| `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md` | `skipped_since_last_run` — Wirkungsnachweis für #1539 |
| ADR-0015 | Python ist Owner der Wetter-Domäne (deckt die Parallelisierung ab) |

## Risks & Considerations

- **R1 (still, hoch) — Die Diagnose-Zuordnung bricht unter Threads.**
  `call_log.resolve_call_source()` (`src/providers/call_log.py:57-64`) leitet die Quelle aus
  `inspect.stack()[:25]` **des aufrufenden Threads** ab. In einem `ThreadPoolExecutor` beginnt
  der Stack beim Worker — alle Marker (`render_email_preview`, `_fetch_weather`, `compare`, …)
  verschwinden, jeder Abruf landet als `"unbekannt"` im Journal (#338). **Kein bestehender Test
  fängt das** (die Tests rufen im Hauptthread auf). Verdacht: Der Cockpit-Pfad über
  `stage_weather.py` protokolliert deshalb **heute schon** „unbekannt" — vor der Umsetzung am
  Journal nachmessen; trifft es zu, ist es ein belegter Vorfall statt einer Theorie.
- **R2 — Höflichkeit gegenüber den Amtsdiensten.** DWD/Météo-France vertragen keinen
  unbegrenzten Parallelabruf. Obergrenze setzen (Vorbild: `min(len(flat), 8)`).
  `ForecastBudgetGate` hilft hier nicht: `user_briefing` wird nie gedrosselt
  (`forecast_budget.py:64-65`).
- **R3 — Reihenfolge-Stabilität.** Die Ortsreihenfolge im Vergleich ist fachlich festgelegt
  (`docs/specs/modules/compare_location_order.md`, `tests/unit/test_compare_location_order.py`).
  Parallele Abarbeitung darf die Ausgabereihenfolge nicht verändern.
- **R4 — Fehlerverhalten je Ort.** Heute bricht ein Ortsfehler die Schleife nicht
  (`try/except` je Ort). Best-effort-Semantik muss erhalten bleiben; `future.result()`
  wirft sonst den ersten Fehler nach außen.
- **R5 — Kein Test deckt Laufzeit oder Nebenläufigkeit ab.** Weder für `preview_proxy.go`
  (30 s/60 s) noch für die Ortsschleife existieren Timeout- oder Lastszenarien. Der
  Wirkungsnachweis muss neu gebaut werden — **am Wirkort**: dass `/health` **während** einer
  laufenden Vorschau antwortet, ist die eigentliche Zusicherung von U1.
- **R6 — Timeout-Leiter ist widersprüchlich** (Nebenbefund, keine Lösung):
  Vergleichs-Vorschau Go 60 s == nginx 60 s (kein Puffer, Wettlauf); Trip-Vorschau Go 30 s,
  obwohl nginx 60 s zuließe; der **Versand** desselben Rechenwegs darf 120 s
  (`compare_preset.go:676`) bzw. 300 s (`proxy.go:277`). nginx setzt für gregor20 **kein**
  `proxy_read_timeout` → Default 60 s (geprüft in `/etc/nginx/sites-available/gregor20.henemm.com`).

## Korrekturen an den Ticketkörpern (am Code gemessen)

- **#1539 nennt für `de_direct` 90 s.** Heute steht dort **150 s**
  (`dwd.py:119 THUNDER_FETCH_DEADLINE_SECONDS = 150.0`, PO-Entscheid 2026-08-08 via #1531).
  Der Worst Case je Ort ist seit dem Ticket **größer** geworden.
- **#1765 nennt „~21 s pro Ort"** (gemessen 2026-08-12). Wegen der Budgetanhebung aus #1531
  ist dieser Wert vor der Umsetzung **neu zu messen**, nicht zu übernehmen.
- **#1765 vermutet den Single-Worker als Nebenaspekt** („prüfen, ob der Python-Core mehr als
  einen Worker verträgt"). Gemessen ist der Grund präziser: nicht die Worker-Zahl, sondern
  `async def` **ohne** `await` bei synchroner Arbeit. Ein `def`-Handler behebt es ohne
  zusätzliche Prozesse.

## Messungen am laufenden Staging-Dienst (2026-08-15)

Fixtures: 3-Orte-Preset `cp-21e198c1b74020dd` (Innsbruck/Stubai/Zillertal — alle in `DE_ALPEN`),
2-Orte-Preset temporär angelegt und danach gelöscht, Trip `e2e-1680-s5b-preview`.
Rohdaten im Session-Scratchpad (`m1_health_log.txt`, `openmeteo_tail2000.jsonl`).

| # | Messung | Ergebnis |
|---|---|---|
| M1 | `/health` während einer Vergleichs-Vorschau (3 Orte) | **74,5 s von 75,76 s nicht binnen 2 s erreichbar** — 25 Timeouts in Folge, erst der Poll nach Abschluss kam mit 200/0,30 s durch |
| M2 | Vergleich, kalt / warm (3 Orte) | 75,76 s / **75,66 s** |
| M2 | Vergleich, kalt / warm (2 Orte) | 50,14 s / **49,85 s** |
| M2 | daraus Sekunden je Ort | **25,1–25,6 s** (Grenzkosten des 3. Ortes: 25,62 s) |
| M3 | Trip kalt / warm | **121,14 s** / 0,69 s; ein dritter Aufruf Minuten später wieder 78,64 s |
| M4 | Vergleich über nginx | **504 nach 60,02 s** |
| M4 | Trip über nginx | **502 nach 30,02 s** |
| M5 | Diagnose-Journal, letzte 2000 Zeilen | **7,4 % (148) `source: "unbekannt"`** |

### Was die Messungen entscheiden

- **(a) „~21 s pro Ort" ist widerlegt** — gemessen 25,1–25,6 s, rund 20 % höher. Passt zur
  Anhebung des DWD-Gewitterbudgets von 90 s auf 150 s (#1531, 2026-08-08).
- **(b) „>50 s kalt / 0,65 s warm"** — warm trifft (0,69 s), kalt ist mit **121 s** mehr als
  doppelt so hoch wie das Ticket nahelegt.
- **(c) „eine einzelne Vorschau kippt `/api/health`" ist bestätigt** — und stärker als
  „kippt": der Dienst war praktisch die **gesamte** Aufrufdauer stumm.
- **U4 unabhängig bestätigt:** Beim Vergleich sind kalt und warm **identisch** (75,76/75,66 s;
  50,14/49,85 s). Es gibt dort keinen wirksamen Cache — auch `ThunderWindowCache` nicht, weil
  die drei Testorte nach `DE_ALPEN` routen und damit über `dwd.py` laufen, das keinen Cache
  hat. Die Regionsanalyse hat das vorhergesagt, die Messung bestätigt es.
- **Die `call_log`-Falle ist belegt, nicht mehr theoretisch:** Ein `unbekannt`-Cluster
  (2026-08-12T04:45:22–31 UTC) fällt zeitlich exakt mit einem
  `GET /api/_internal/trips/…/stages-weather` zusammen — dem Endpunkt, der bereits heute einen
  `ThreadPoolExecutor` nutzt. **Einschränkung des Messenden:** Ein zweites Cluster korreliert
  stattdessen mit `/api/_validator/sms-fidelity-preview`; dort ist die Ursache eine fehlende
  Marker-Abdeckung, keine Threading-Folge. `unbekannt` ist also nicht ausschließlich
  Threading-bedingt.

### Nachmessung N1/N2 — was die Trip-Vorschau wirklich tut (störungsfreies Fenster)

Gemessen im Fenster 12:57:49–12:59:50 UTC, in dem laut `journalctl` **kein** fremder Request
lief, und **vor** dem Staging-Neustart um 13:00:22 UTC.

**N1 — 7 Segmentabrufe, nicht 3:**

| # | Segment | Tag | Dauer |
|---|---|---|---|
| 1 | Start | heute | 12,27 s |
| 2 | Ziel | heute | 12,12 s |
| 3 | Nachtwetter (Segment 999) | heute | 24,60 s |
| 4 | Start | +1 Tag | 25,38 s |
| 5 | Ziel | +1 Tag | 25,90 s |
| 6 | Start | +2 Tage | 10,06 s |
| 7 | Ziel | +2 Tage | 10,13 s |

Summe **120,46 s** von 121,14 s Gesamtdauer (Rest: abschließender ECMWF-Z500-Abruf für das
Stabilitäts-Label plus Rendering). Mittel ~17,3 s, Spanne 10,1–25,9 s.

Warum 7: Der Trip hat 3 Etappen à 2 Wegpunkte. Die Vorschau holt dieselben 2 Wegpunkte
zusätzlich für **+1 und +2 Tage** (Gewitter-Vorhersage / Mehrtages-Trend) — 2 × 3 = 6 — plus
**1 × Nachtwetter** = 7. **Kostentreiber ist nicht der HTTP-Abruf** (Antwort in < 50 ms),
sondern die DWD-Gewitter-Anreicherung je Segment.

**Konsequenz — die Sorge „Parallelisierung reicht nicht" ist widerlegt.** Parallelisiert
läge die Gesamtzeit bei etwa dem langsamsten Einzelsegment, also **~26 s** — unter der
30-s-Grenze des Go-Weiterleiters. **Aber die Reserve ist dünn** (~87 % des Budgets), was die
Korrektur der Timeout-Leiter in Scheibe B als **Sicherheitsabstand** rechtfertigt, nicht als
Ersatz für die Beschleunigung.

**Offene Designfrage für Scheibe B** (vom Messenden ausdrücklich als nicht durch Messung
beantwortbar markiert): Die 7 Abrufe verteilen sich über **mindestens drei getrennte Schritte**
im Vorschau-Code (Hauptabruf heute, Gewitter-Vorhersage +1/+2 Tage, Nachtwetter). Ob sie in
**einen** gemeinsamen Parallel-Pool passen oder mehrere Stellen umgebaut werden müssen, ist
dort zu klären.

**N2 — null Wiederholversuche.** Kein Treffer für „Weather fetch failed for segment … after
N attempt(s)", keine Tenacity-Meldungen, jedes Segment genau einmal protokolliert, alle
Abrufe `status:200, error:null` beim ersten Versuch.

⇒ **U2 ist latenzseitig wirkungslos, solange die Wetterdienste gesund sind.** Die 121 s sind
echte, einmalige Arbeit. Der Wert von U2 liegt woanders und ist entsprechend zu begründen:
(a) es schafft die **vorschau-eigene Abruf-Nahtstelle**, ohne die Scheibe B nicht
parallelisieren kann, ohne `_fetch_weather` (6 Aufrufer, 4 im Versand-/Alarmpfad) anzufassen;
(b) bei einer **echten** Provider-Störung verdreifacht sich heute die Wartezeit der
interaktiven Vorschau samt `sleep` — realer Fall, in dieser Messung nur nicht eingetreten.
Einschränkung des Messenden: eine Momentaufnahme bei fehlerfreiem Provider kann Retries im
Störungsfall nicht ausschließen, nur ihr Ausbleiben im Normalbetrieb belegen.

**Nicht verwertbare Gegenprobe, ausdrücklich so gemeldet:** Ein zweiter Trip (`277aa63f`)
antwortete in 0,15 s — aber nur, weil sein Datum außerhalb des DWD-Vorhersagehorizonts liegt
und alle 6 Anfragen sofort mit HTTP 400 zurückkamen. Kein echter Abruf, kein Beleg.

### Störung, die bei jeder Wiederholung mitzudenken ist

Zwei **getrennte** Störquellen, beide vor jeder Wiederholungsmessung zu prüfen:

1. **Staging-Neustart leert den Cache.** Der 78,64-s-Ausreißer beim dritten Trip-Aufruf ist
   belegt erklärt: `gregor-python-staging.service` wurde um 13:00:22 UTC neu gestartet
   (Staging-Auto-Deploy, PID-Wechsel im `journalctl` nachgewiesen). Das verwirft den
   prozessweiten In-Memory-Cache vollständig — nach jedem Auto-Deploy ist der erste Aufruf
   wieder kalt. Die zunächst genannte Vermutung „vermutlich Fremdlast" wurde vom Messenden
   selbst **zurückgezogen und durch diesen Beleg ersetzt**.
2. **Parallele Fremdnutzung** besteht unabhängig davon (ein fremdes Compare-Preset entstand
   während der Messung im selben Nutzer). Weil der Python-Core ein Single-Worker ist,
   verfälscht jeder fremde Vorschau-Aufruf die Zeitmessung nach oben. Als **Beobachtung**
   gemeldet, nicht als Erklärung für einen bestimmten Messwert.

## Analysis

### Type
**Bug** (beide Tickets `bug`, `priority:medium`, nutzersichtbares Fehlverhalten).

### Technischer Ansatz

**U1 — Entblockung (Scheibe A).** Die 13 `async def`-Handler ohne `await` werden zu `def`.
Damit führt Starlette sie im Threadpool aus, der Event-Loop bleibt frei. Kein `await` ist
vorhanden, das brechen könnte; `gpx.py:22 parse_gpx` bleibt `async def` (nutzt `await`).
Der Threadpool ist nirgends konfiguriert → anyio-Default (40 Threads); genügt.

**U2 — Vorschau-eigene Abrufpolitik (Scheibe A).** Statt `scheduler._fetch_weather()` mit
seiner Versand-Retry-Leiter bekommt die Trip-Vorschau eine eigene, schlanke Abruffunktion in
`preview_service.py`, die `fetch_segment_weather()` je Segment ohne Wiederhol-Schleife
aufruft. Grund: Wartezeit ist im Versand unkritisch (PO-Einordnung #1539), in einer
interaktiven Vorschau nicht.

**U3 — Parallelisierung (Scheibe B), Variante V3 „außen".** Bewertet wurden drei Varianten:

| | Ansatz | Bewertung |
|---|---|---|
| V1 | `ThreadPoolExecutor` **in** `_fetch_weather` / `ComparisonEngine.run` | verworfen — ändert Versand und Alarme sofort mit (9 Aufrufer) und nimmt die `[triage:po]`-Entscheidung aus #1539 vorweg |
| V2 | Opt-in-Parameter, Default = heute | verworfen — baut einen toten Zweig in versandkritischen Code, den heute kein Aufrufer nutzt |
| **V3** | Parallelisierung **außen**, nur im Vorschau-Pfad | **empfohlen** |

Für den Trip ist V3 geradeaus (Parallelisierung um die in A neu entstandene Abruffunktion).
Für den Vergleich wird `comparison_engine.py` **nicht angefasst**; stattdessen ruft
`compare_preview_service.py` `ComparisonEngine.run(locations=[loc], …)` je Ort parallel auf
und fügt die Ergebnisse indexiert zusammen.

**Die Äquivalenz dieses Aufsplittens wurde nachgeprüft, nicht angenommen:**
`time_window`, `target_date`, `forecast_hours`, `profile` und `official_alerts_enabled` sind
**Parameter** von `run()` (`comparison_engine.py:98-105`), werden also nicht aus der
Ortsmenge abgeleitet. Nach der Schleife findet nichts Ortsübergreifendes mehr statt — seit
#1359 Scheibe 2 gibt es keine Score-Sortierung, `results` behält die Eingabereihenfolge
(`comparison_engine.py:383-390`). Der Provider wird in `fetch_forecast_for_location` **je Ort**
neu gebaut und geschlossen, es existiert also gar keine ortsübergreifende Dedup, die verloren
gehen könnte. Als Nebengewinn erbt die Variante die vorhandene Fehlerbehandlung: `run()` fängt
Ortsfehler bereits intern ab (`comparison_engine.py:369-381`) und wirft bei einem einzigen Ort
nie nach außen — Best-effort bleibt ohne Zutun erhalten.

### Affected Files

| Datei | Änderung | Scheibe | Beschreibung |
|---|---|---|---|
| `api/routers/preview.py` | MODIFY | A | 4× `async def` → `def` |
| `api/routers/internal.py` | MODIFY | A | 2× `async def` → `def` |
| `api/routers/validator.py` | MODIFY | A | 6× `async def` → `def` |
| `api/routers/notify.py` | MODIFY | A | 1× `async def` → `def` |
| `src/services/preview_service.py` | MODIFY | A+B | eigene Abruffunktion (A), Parallelisierung (B) |
| `tests/unit/…` (neu) | CREATE | A | U1-Test am Wirkort + Ratschen-Test |
| `src/services/compare_preview_service.py` | MODIFY | B | `run()` je Ort parallel, indexierte Zusammenführung |
| `src/providers/call_log.py` | MODIFY | B | `ContextVar`-Override vor der Stack-Inspektion |
| `src/utils/timezone.py` | MODIFY | B | Lock um `_tf_instance` |
| `tests/unit/…` (neu) | CREATE | B | Reihenfolge, Best-effort, `call_log` unter Threads |

### Scope Assessment

- Dateien: ~10 (A: 6, B: 5, teils überlappend)
- Produktivcode geschätzt: **A ~30–40 LoC, B ~60–80 LoC** — zusammen unter dem 250er-Limit,
  aber knapp genug, dass der Zähler vor Beginn von B geprüft gehört
- Risk Level: **A = LOW** (mechanisch, kein `await` vorhanden), **B = MEDIUM**
  (Nebenläufigkeit, aber mit Präzedenzfall und thread-sicher vorbereiteten Caches)

### Beschlossene Gegenmaßnahmen für Scheibe B

| Risiko | Gegenmaßnahme | Nachweis |
|---|---|---|
| Reihenfolge kippt | indexierte Vorbelegung (`[None] * len(items)`) statt Append bei Fertigstellung, wie `stage_weather.py:171` | `tests/unit/test_compare_location_order.py` (Compare); für Trip fehlt ein Äquivalent → neu |
| Fehler eines Orts reißt alle mit | Compare: gratis über `run()`-je-Ort; Trip: Wrapper wie `stage_weather.py:52-57` | neuer Kern-Test |
| `call_log` verliert die Quelle | `ContextVar`-Override in `resolve_call_source()` vor der Stack-Inspektion; die 11 Bestandsmarker bleiben als Rückfall | neuer Kern-Test mit 2 Workern |
| `_tf_instance` doppelt geladen | Lock nach Vorbild `weather_cache.py` | Test mit 2 Threads + Aufrufzähler |
| Météo-France-Kontingent | Parallelitätsgrad **niedriger als das Vorbild**: Vergleich `min(len(locations), 4)`, Trip `min(len(segments), 8)`, als benannte Konstante mit Verweis auf `decision_matrix.md` | Code-Review (nicht kern-testbar) |
| Cache-Stampede bei gleichzeitigem Miss | **keine** — bewusst nur benannt (bereits dokumentierte offene Lücke) | — |

Grundlage der Kontingent-Grenze: `docs/reference/decision_matrix.md:229-247` — Météo-France
erlaubt **100 Anfragen/Minute auf ein gemeinsames Konto für alle Nutzer**, ohne aktive
Drosselung (die Lücke ist dort selbst dokumentiert).

### Open Questions

- [ ] Bestätigt die Live-Messung, dass `/api/health` während einer echten Vorschau kippt?
      (Die Mechanik ist netzfrei bewiesen; offen ist nur die Bestätigung am Dienst.)
- [ ] Füllt der bestehende `stage_weather`-Threadpool das Diagnose-Journal heute schon mit
      `source: "unbekannt"`? Falls ja, ist die `call_log`-Reparatur ein belegter Fang statt
      einer Vorsichtsmaßnahme.
- [ ] Liefert `SegmentWeatherService.fetch_segment_weather()` bei einem 96-h-Fenster
      dieselbe Datenform wie der heutige direkte `get_forecast(hours_ahead=96)`? **Nur
      relevant, falls U4 je angegangen wird** — für diesen Workflow nicht zu klären.

## Zuschnitt (Intake-Empfehlung, PO-Freigabe 2026-08-15 „go")

- **Scheibe A:** U1 + U2 — Vorschau blockiert den Prozess nicht mehr, eigene kurze
  Wiederhol-/Zeitpolitik für den interaktiven Pfad. Kein Nebenläufigkeitsrisiko im Versandpfad.
- **Scheibe B:** U3 — Parallelisierung nach dem Muster aus `stage_weather.py:173`; echter
  Teilschritt Richtung #1539. R6 nur nachziehen, falls die dann gemessene Laufzeit es verlangt.
