# Context: Vergleichs-Vorschau parallelisieren (#1765, Scheibe B1)

**Erstellt:** 2026-08-15 · **Workflow:** `fix-1765-compare-vorschau-parallel` · **Track:** Full Process

## Request Summary

Die Vergleichs-Vorschau (`POST /api/preview/compare/{preset_id}`) verarbeitet Orte seriell
(~25 s je Ort) und reißt bei 3+ Orten die 60-s-Grenze. Scheibe B1 parallelisiert die
Ortsverarbeitung nach dem Vorbild `stage_weather.py:173` und schließt damit **#1765**.
Der Trip-Pfad (#1839) folgt getrennt als B2.

## Verhältnis zum Bestandsdokument

`docs/context/fix-1765-1839-vorschau-laufzeit.md` ist die gemeinsame Ursachen- und
Messgrundlage beider Scheiben (U1–U4, Laufzeitmessungen, Risiken R1–R6, Variantenbewertung
V1/V2/V3). **Es bleibt gültig und wird hier nicht wiederholt.** Dieses Dokument trägt nur
das, was für B1 neu gemessen wurde — einschließlich **zweier Korrekturen** an den dort
notierten Annahmen.

### Korrektur 1: `_tf_instance` ist bereits abgesichert — fällt aus B1 raus

Die Gegenmaßnahmen-Tabelle des Bestandsdokuments (Zeile 417-426) führt „`_tf_instance`
doppelt geladen → Lock nach Vorbild `weather_cache.py`" als offene Aufgabe für Scheibe B.
**Das ist erledigt.** `src/utils/timezone.py:21-34` nutzt heute doppelt geprüftes Sperren
(`_tf_lock`), ausdrücklich nach dem Muster `weather_cache.py:294-305`; der Regressionstest
`tests/unit/test_timezone_singleton_threadsicher.py:72-124` erzwingt per `threading.Barrier`,
dass zwei gleichzeitige Erstzugriffe genau **eine** Instanz erzeugen. `_get_tf()` darf
unverändert aus dem Pool heraus aufgerufen werden.

### Korrektur 2: Der Reihenfolge-Nachweis existiert **nicht** am Wirkort

Dieselbe Tabelle verbucht „Reihenfolge kippt → `tests/unit/test_compare_location_order.py`
(Compare)" als vorhandene Absicherung. **Das trifft nicht zu.** Der Test baut
`ComparisonResult`-Objekte **von Hand** (`_result()`, Zeile 85-91) und prüft ausschließlich
die vier Renderer-Oberflächen (`test_compare_location_order.py:134,160,213`). Die Stelle, an
der eine Parallelisierung die Reihenfolge kippen würde — das Zusammenführen der
Ortsergebnisse —, liegt **davor** und ist ungeprüft. Es existiert **kein** Test, der nach
einem echten `ComparisonEngine.run()` mit mehreren Orten die Reihenfolge von
`ComparisonResult.locations` behauptet. Der Nachweis für B1 ist **neu zu bauen**, nicht
vorhanden.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/compare_preview_service.py:163` | **Änderungsort** — einziger `ComparisonEngine.run()`-Aufruf des Vorschaupfads, innerhalb `_prepare()` (129-178) |
| `src/services/comparison_engine.py:127` | Ortsschleife `for loc in locations` — **bleibt unangetastet** (Variante V3 „außen") |
| `src/services/comparison_engine.py:387-391` | Konstruktion des `ComparisonResult` **nach** der Schleife |
| `src/app/user.py:117-164` | `LocationResult` — rein ortsspezifisch, 25 Felder |
| `src/app/user.py:168-189` | `ComparisonResult` — 4 Felder + 2 Properties (Merge-Analyse unten) |
| `src/services/stage_weather.py:52-57, 164-183` | **Vorbild** — Wrapper `_fetch_one`, flache Liste, `[None] * len(flat)`, `future_to_idx` |
| `src/providers/call_log.py:41-53, 56-64` | **R1** — 11 Marker, `inspect.stack()[:25]` des ausführenden Threads |
| `src/services/official_alerts/warn_egress.py:55-57` | **ContextVar-Vorbild im Repo** — „ContextVar isoliert korrekt ueber Threads/Tasks" |
| `src/services/official_alerts/dpc.py:52,160-165` | **neues Risiko R7** — fixer nationaler Cache-Key (Italien), ungelockt |
| `src/services/official_alerts/vigilance.py:57-58,93-94` | **neues Risiko R7** — fixer Cache-Key `"national"` (Frankreich), ungelockt |
| `src/services/official_alerts/meteoalarm_budget.py:228-263` | Tageskontingent, `fcntl`-gesichert — begrenzt den Schaden aus R7 |
| `src/services/scheduler_dispatch_service.py:451` | zweite Call-Site (**Versand**) — Zuschnittfrage |
| `api/routers/compare.py:25-77` | dritte Call-Site (**Sofortvergleich**, öffentlich) — Zuschnittfrage |
| `internal/handler/preview_proxy.go:52` | Go-Timeout Vergleichs-Vorschau 60 s == nginx 60 s |

## Merge-Analyse: was beim Zusammenführen von N Teilergebnissen passiert

Der Vorschaudienst hat **keine eigene Ortsschleife** — er ruft `ComparisonEngine.run()`
**einmal** mit der vollen Liste auf (`compare_preview_service.py:163`). „Außen"
parallelisieren heißt deshalb: N Aufrufe `run(locations=[loc])` und N `ComparisonResult`
zu einem zusammenführen. Feld für Feld am Code geprüft:

| Feld | Merge-Verhalten | Begründung |
|---|---|---|
| `locations` | **positionstreu** zusammensetzen | einzige Stelle, an der die konfigurierte Reihenfolge lebt (`user.py:175`); Fertigstellungsreihenfolge ist bei ~25 s/Ort zufällig |
| `time_window` | trivial — bei allen N identisch | `run()`-Parameter (`comparison_engine.py:98`), nicht aus Orten abgeleitet |
| `target_date` | trivial — bei allen N identisch | `run()`-Parameter (`comparison_engine.py:100`) |
| `created_at` | **explizit einmal setzen**, vor dem Start der Parallel-Aufrufe | `field(default_factory=datetime.now)` (`user.py:171`) — heute ein Zeitstempel je Lauf, bei N Aufrufen N verschiedene. „Nimm den ersten" hinge an der Einreichungsreihenfolge. Verbraucht in `output/renderers/comparison.py:216` („Erstellt: …") |
| `winner` | **kein Merge-Code** | `@property` (`user.py:180-184`), live aus `self.locations`: erster fehlerfreier Ort in konfigurierter Reihenfolge — keine ortsübergreifende Bewertung |
| `valid_locations` | **kein Merge-Code** | `@property` (`user.py:186-189`), reiner Filter |

**Fazit:** Genau **zwei** Merge-Entscheidungen — Reihenfolge und `created_at`. Es gibt kein
gespeichertes Aggregat über alle Orte; die Score-Sortierung ist seit #1359 entfernt
(`comparison_engine.py:383-386`).

## Äquivalenz von `run(locations=[loc])` je Ort — am Code geprüft

- `run()` ist `@staticmethod`, `ComparisonEngine` hat **keine** Instanzattribute
  (`comparison_engine.py:97`). `settings` und `results` sind lokal je Aufruf (`:121-125`).
- **Fehler je Ort sind bereits gekapselt:** `comparison_engine.py:130-147` (Fetch) und
  `:369-381` (alles übrige) fangen intern ab und erzeugen `LocationResult(error=…)`.
  `run()` wirft für einen Ortsfehler **nie** nach außen ⇒ die Best-effort-Semantik ist gratis;
  ein Wrapper wie `stage_weather.py:52-57` schützt nur noch gegen Unerwartetes **vor** der
  Schleife (z. B. `Settings()`-Konstruktion).
- **Provider werden ohnehin je Ort neu gebaut und geschlossen** (`comparison_engine.py:414`
  über `get_provider()`, `providers/base.py:238`; `close()` bei `:425-426`) ⇒ keine
  Wiederverwendung geht verloren.
- Mehrkosten: `Settings()` wird N- statt einmal konstruiert (`:121-124`) — rein lesend.

## Existing Patterns

**Das Vorbild** (`src/services/stage_weather.py:170-183`) — vollständig zu übernehmen:

```python
flat = [(stage.id, seg) for stage in stages for seg in segments_by_stage[stage.id]]
fetched: list[Optional[SegmentWeatherData]] = [None] * len(flat)
if flat:
    with ThreadPoolExecutor(max_workers=min(len(flat), 8)) as executor:
        future_to_idx = {executor.submit(_fetch_one, …): idx for idx, … in enumerate(flat)}
        for future, idx in future_to_idx.items():
            fetched[idx] = future.result()
```

Vier Bestandteile: flache Liste vor dem Pool · Deckel `min(len, N)` · **indexierte
Vorbelegung** statt Append bei Fertigstellung · dünner Wrapper `_fetch_one`
(`stage_weather.py:52-57`) als Fehler-Grenze. Spezifiziert in
`docs/specs/modules/stage_weather_python_endpoint.md:57`.

**ContextVar-Vorbild** (`src/services/official_alerts/warn_egress.py:55-57`):
`contextvars.ContextVar(..., default=None)` mit Getter/Setter-Paar. Kommentar dort:
„ContextVar isoliert korrekt ueber Threads/Tasks."

⚠️ **`ThreadPoolExecutor` vererbt den contextvars-Kontext NICHT automatisch** (anders als
asyncio). Der Übergang muss explizit erfolgen — `contextvars.copy_context().run(...)` im
Worker oder Wert manuell durchreichen. Wer die ContextVar nur im Hauptthread setzt und im
Worker liest, bekommt still den Default zurück.

## Dependencies

**Upstream:** `ComparisonEngine.run` → `fetch_forecast_for_location` → `ForecastService` /
`OpenMeteoProvider` → `_enrich_thunder` (`dwd`/`dwd_eu`/`meteofrance`) · `BergfexScraper` ·
`get_official_alerts_with_status` · `ThunderWindowCache` · `call_log`.

**Downstream — `ComparisonEngine.run()` hat DREI unabhängige Produktiv-Aufrufstellen:**

| Call-Site | Weg | Grenze | von B1 erfasst? |
|---|---|---|---|
| `compare_preview_service.py:163` | Vorschau (der gemeldete Fall) | Go 60 s == nginx 60 s (`preview_proxy.go:52`) | **ja** |
| `scheduler_dispatch_service.py:451` | Versand (`POST /api/scheduler/compare-presets/{id}/send`, auch Cron-Loop `:145`) | nginx 60 s | offen — s. Zuschnittfrage |
| `api/routers/compare.py:71` | Sofortvergleich `GET /api/compare` (Rest der NiceGUI-Zeit, **öffentlich** über `router.go:156` erreichbar, bewusst nicht entfernt) | Go 60 s == nginx 60 s (`proxy.go:77`) | offen — s. Zuschnittfrage |

Alle drei durchlaufen dieselbe serielle Schleife `comparison_engine.py:127` und reißen bei
3+ Orten dieselbe Wand. **Geteilt ist heute nur `order_locations_by_ids()`**
(`compare_preview_service.py:242-254`, genutzt auch in `scheduler_dispatch_service.py:100-102,421`)
— die Call-Sites selbst sind unabhängig voneinander.

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/stage_weather_python_endpoint.md:57,126-129` | **Vorbild**; hält fest: kein neuer ADR nötig, ADR-0015 deckt es ab |
| `docs/specs/modules/compare_location_order.md` | Zusicherung: `ComparisonResult.locations` in Eingabereihenfolge, alle vier Oberflächen folgen ihr |
| `docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md:190-258` | Scheibe A, Abgrenzung zu B |
| `docs/specs/modules/compare_channel_preview_dispatch.md` | Vergleichs-Vorschau + Versand |
| `docs/specs/modules/fix_1329_forecast_cache_budget.md:399-407` | U4 (fehlender Cache) — **bewusst zurückgestellt, nicht Teil von B1** |

**ADR:** kein neues nötig. ADR-0015 (Python ist Owner der Wetter-Domäne) deckt die
Parallelisierung ab — derselbe Präzedenzfall wie beim Stage-Weather-Endpunkt. Ein eigenes
ADR zu Nebenläufigkeit existiert nicht (`docs/adr/README.md` ohne Treffer für
„async"/„Threadpool"/„Event-Loop"). **Aber:** griffe die Umsetzung **innerhalb**
`comparison_engine.py` ein (Variante V1, träfe Versand und Alarme mit), wäre das eine
Vorwegnahme aus #1539 und ADR-würdig. V3 „außen" braucht das nicht.

## Bestehende Verträge, die B1 nicht brechen darf

| Nachweis | Zusicherung |
|---|---|
| `tests/unit/test_preview_fehlerformen.py:97,117,130` | 404 / 422 / 503 des Vorschau-Endpunkts bleiben formgleich |
| `tests/unit/test_event_loop_bleibt_frei.py:147-221` | **Scheibe-A-Ratsche:** `/health` bleibt während einer laufenden Vergleichs-Vorschau erreichbar |
| `tests/unit/test_compare_location_order.py` | Renderer-Reihenfolge über alle vier Oberflächen |
| `docs/specs/modules/compare_location_order.md` | Ausgabereihenfolge = konfigurierte Preset-Reihenfolge |

🔴 **Ein Vertrag muss bewusst abgelöst werden:**
`tests/tdd/test_compare_preview_service.py:285-311` sichert zu, dass `ComparisonEngine.run`
**genau einmal** je `render_all_channels()` läuft (`calls.count == 1`), verankert als AC-7 im
Docstring `compare_preview_service.py:52-55`. Nach der Parallelisierung sind es N Aufrufe —
der Test wird rot. Die B1-Spec muss diesen Vertrag ausdrücklich ersetzen (Zusicherung neu
formulieren: *ein* Engine-Lauf **je Ort**, nicht *ein* Lauf je Ort**menge**), sonst blockiert
eine Bestandsratsche zu Recht. Weitere Tests derselben Datei (`:332,371,400`) prüfen die
Durchreichung von `time_window`/`forecast_hours` und müssen nach dem Umbau **je Ort**
weiterhin greifen — sie sind der Nachweis, dass die Parameter beim Aufteilen nicht verloren
gehen.

## Risks & Considerations

- **R1 (belegt) — `call_log` verliert die Quelle im Threadpool.**
  `resolve_call_source()` (`call_log.py:56-64`) liest `inspect.stack()[:25]` des
  **ausführenden** Threads; im Worker fehlen alle 11 Marker (`call_log.py:41-53`), das Journal
  bucht `"unbekannt"`. Kein Bestandstest prüft die Auflösung aus einem fremden Thread
  (geprüft: `test_bug_338_openmeteo_call_counter.py:152,175,199` rufen im Hauptthread auf).
  Belegt statt vermutet: Das Diagnose-Journal zeigt 7,4 % `unbekannt` mit einem Cluster beim
  bereits parallelisierten `stages-weather`. **Gegenmaßnahme:** ContextVar-Override **vor**
  der Stack-Inspektion, Marker als Rückfall — plus expliziter Kontext-Übergang in den Worker.
- **R3 — Reihenfolge.** Indexierte Vorbelegung; Nachweis **neu** (s. Korrektur 2). Der Test
  muss die Fertigstellungsreihenfolge künstlich gegen die Einreichungsreihenfolge drehen,
  sonst prüft er nichts.
- **R7 (neu) — Thundering Herd bei national geschlüsselten Warndiensten.**
  `dpc.py:52` (Italien) und `vigilance.py:57-58` (Frankreich) cachen mit **einem festen
  Schlüssel für alle Orte**, ungelockt nach „check-then-act" (`warn_egress.py:351,375,436…`).
  Solange die Orte seriell liefen, war der zweite Ort ein Cache-Treffer. Parallel sehen alle
  gleichzeitig einen Miss und lösen **redundante** Abrufe gegen denselben nationalen Endpunkt
  aus — gegen ein budgetiertes Tageskontingent (`meteoalarm_budget.py:228-263`, `fcntl`-fest,
  begrenzt den Schaden). Keine Datenkorruption, aber eine Lastspitze, die es vorher nicht gab.
  Betrifft FR-/IT-Orte, für den Karnischen Höhenweg (AT/DE) nicht. Dieselbe Lücke ist für den
  Kachel-Cache dokumentiert: `decision_matrix.md:246-254` nennt sie ausdrücklich als „bislang
  folgenlos, weil alle Aufrufer sequentiell liefen".
- **R2 — Höflichkeit gegenüber den Amtsdiensten.** Météo-France: **100 Anfragen/Minute auf
  ein gemeinsames Konto für alle Nutzer**, keine aktive Drosselung
  (`decision_matrix.md:231-254`). Parallelitätsgrad deshalb **unter** dem Vorbild ansetzen
  (Vorbild `min(len, 8)` → hier `min(len(locations), 4)`), als benannte Konstante mit Verweis.
- **R6 — Timeout-Leiter** (Go 60 s == nginx 60 s, kein Puffer) bleibt Sache von B2; bei 3–4
  Orten parallel liegt die Laufzeit bei ~26 s und damit deutlich unter der Wand.
- **Bereits erledigt, kein Risiko mehr:** `_tf_instance` (s. Korrektur 1) ·
  `ThunderWindowCache` (`thunder_window_cache.py:58-62`, Lock ausdrücklich für die
  Parallelisierung der Ortsschleife gebaut) · `WeatherCacheService`
  (`weather_cache.py:91`, Instanz-Lock) · `lru_cache` in `department_mapper.py:335`
  (intern gelockt) · `meteoalarm_budget.py` (`fcntl`) · Provider-Registry
  `providers/base.py:190` (idempotente Writes unter dem GIL).

## Gates, die bei den Änderungsdateien greifen

| Gate | greift? |
|---|---|
| `touched_tests_gate.py` | **ja** — `compare_preview_service.py` → `tests/unit/test_compare_channel_metrics_reach_the_renderer.py`, `test_compare_mail_blocks.py`; `call_log.py` → `test_diagnostics_path_resolution.py`, `test_radar_nowcast_cache_sharing.py` (Letzteres ein Fehltreffer: „call_log" ist dort nur eine lokale Variable) |
| `pendant_gate.py` | **nein** bei Änderungen an Bestandsdateien — nur bei **Neuanlagen** in den einseitigen Bereichen. Relevant nur, falls B1 eine neue compare-only-Datei anlegt |
| `renderer_mail_gate.py` | **nein** — keine der Änderungsdateien fällt unter `_MAIL_PATTERNS` |
| `architecture_guard.py` / `domain_pattern_guard.py` | laufen mit, schlagen aber nur bei neuen Wettermetrik-Berechnungen an — B1 führt keine ein |

## Analysis

### Type

Bug (#1765) — nutzersichtbares Fehlverhalten, Ursache gemessen, Behebung ist eine
Umstrukturierung ohne fachliche Verhaltensänderung.

### Zuschnitt-Entscheidung (Tech-Lead-Entscheid 2026-08-15, vom PO delegiert)

**Geteilter Baustein bauen, aber in diesem Schnitt nur die Vorschau umstellen.**
Zwei Schnitte, beide unter #1765; **erst der zweite schließt das Ticket.**

| | dieser Schnitt (B1) | Folgeschnitt (B1b) |
|---|---|---|
| Baustein `comparison_parallel.py` | **bauen**, an neutraler Stelle | benutzen |
| `call_log`-ContextVar | **bauen** | — |
| Call-Site A (Vorschau) | **umstellen** | — |
| Call-Site B (Versand) | — | umstellen + `top_ort`-Nachweis |
| Call-Site C (Sofortvergleich) | — | umstellen |
| Cron-Lastfrage (unten) | entfällt | dort zu entscheiden |
| schließt #1765 | nein | **ja** |

**Warum nicht alles in einem Schnitt** — obwohl der Ticketkommentar vom 2026-08-12 den Befund
ausdrücklich auf „jeder Weg, der die Ortsschleife synchron hinter nginx durchläuft" erweitert
(mit gemessenem 504 im Versand bei vier Orten) und die Mechanik in allen drei Fällen
nachweislich identisch ist: Die **Betriebsrisiken der drei Pfade sind es nicht.**

| | Vorschau (A) | Versand (B) |
|---|---|---|
| Auslöser | interaktiv, ein Mensch | Cron, unbeaufsichtigt |
| Gleichzeitigkeit | eine Sitzung | mehrere Nutzer (s.u.) |
| schreibt Zustand | nein | `letzter_versand`, Alarm-Anker, Snapshots |
| Fehlerfolge | Nutzer sieht Fehler, lädt neu | Briefing falsch/ausgefallen, unbemerkt |
| auf Staging prüfbar | direkt, in Sekunden | nur mit Aufwand |

Nebenläufigkeit wird nicht gleichzeitig in einen beaufsichtigten und einen unbeaufsichtigten
Pfad eingeführt — der unbeaufsichtigte bekommt sie, wenn der beaufsichtigte sie nachweislich
trägt. Der Baustein wird deshalb **sofort geteilt** angelegt (nicht in
`compare_preview_service.py`), damit B1b nur noch Call-Sites umhängt und nichts umbaut.

Zwei Nebenwirkungen stützen die Reihenfolge: (1) Das Cron-Lastrisiko entsteht ausschließlich
in B — es stellt sich in B1b, dann mit Betriebsdaten aus A statt mit einer Schätzung.
(2) Die `call_log`-Reparatur wirkt sofort **prozessweit**, nicht nur im Vergleich: der Mangel
ist mit 7,4 % `unbekannt` belegt und stammt aus dem bereits parallelen `stage_weather`-Pfad.

**Für B1b vorgemerkt — Cron-Überlagerung.** Der Cron-Endpunkt
`POST /api/scheduler/compare-presets-daily` (`api/routers/scheduler.py:186-201`) ist `def`
und läuft **heute schon** je `user_id` nebeneinander im Starlette-Threadpool. Kommt dort die
Ortsparallelität hinzu, addieren sich die gleichzeitigen Außenanfragen **über Nutzer hinweg**.
Für Météo-France (100 Anfragen/Minute, gemeinsames Konto, ungedrosselt) fängt die Deckelung
je Preset das nicht ab. Die tatsächliche Gleichzeitigkeit mehrerer FR-Presets am selben
Cron-Tick ist eine Betriebsfrage, aus dem Code **nicht** ablesbar — in B1b zu entscheiden,
nicht hier zu schätzen.

### Technischer Ansatz

**Neues Modul `src/services/comparison_parallel.py`** (nicht in `comparison_engine.py`, nicht
in `compare_preview_service.py`). Grund für die eigene Datei: Die Zusicherung
„`comparison_engine.py` unangetastet" wird so mechanisch prüfbar statt argumentativ, und der
Baustein liegt neutral genug, dass Versand und Sofortvergleich ohne Umweg andocken.

```python
def run_comparison_parallel(
    locations, time_window, target_date,
    forecast_hours=COMPARE_FORECAST_HOURS, profile=None,
    official_alerts_enabled=True, *, call_source=None,
) -> ComparisonResult
```

Ablauf nach dem Vorbild `stage_weather.py:170-183`:

1. `created_at = datetime.now()` **einmal**, vor dem Start der Futures.
2. `fetched: list[Optional[LocationResult]] = [None] * len(locations)`.
3. `ThreadPoolExecutor(max_workers=min(len(locations), MAX_PARALLEL_LOCATIONS))`,
   `future_to_idx`-Abbildung — **indexierte Rückgabe**, kein Append bei Fertigstellung.
4. Worker-Wrapper je Ort: setzt die `call_log`-Quelle im **eigenen** Thread, ruft
   `ComparisonEngine.run(locations=[loc], …)` mit den unveränderten Parametern auf und gibt
   `result.locations[0]` zurück. Fehler werden wie in `stage_weather.py:52-57` gekapselt.
5. `ComparisonResult(locations=fetched, time_window=…, target_date=…, created_at=created_at)`.

`MAX_PARALLEL_LOCATIONS = 4` als benannte Konstante mit Verweis auf
`decision_matrix.md:231-254` — **bewusst unter** dem Vorbild (`min(len, 8)`), weil das
Météo-France-Konto geteilt und ungedrosselt ist.

**🔴 Korrektur an der Strategie-Vorlage: ContextVar, nicht durchgereichter Parameter.**
Die Strategiebewertung schlug vor, die Quelle als Funktionsargument bis zu
`resolve_call_source()` durchzureichen, und hielt das für den billigeren Weg. Am Code
gegengeprüft: `resolve_call_source()` hat genau **zwei** Aufrufer —
`src/providers/openmeteo.py:558` (Thin-Wrapper der Provider-Instanz) und `call_log.py:84`
(modulintern). Der Aufruf liegt also **tief im Provider**, nicht im Wrapper. Ein Parameter
müsste durch `ComparisonEngine.run` → `fetch_forecast_for_location` → `get_provider` →
`OpenMeteoProvider` gereicht werden — genau den Bestandscode anfassen, den der Zuschnitt
„außen" unberührt lassen soll.

Die ContextVar ist deshalb hier die **kleinere** Änderung, und sie braucht **kein**
`copy_context()`: Der Worker setzt sie in seinem **eigenen** Thread, bevor er `run()` aufruft;
`resolve_call_source()` liest sie tief unten aus demselben Thread. Nötig ist ein
Context-Manager mit `reset(token)` — `ThreadPoolExecutor` verwendet Threads wieder, ein nicht
zurückgesetzter Wert würde in den nächsten Task lecken. Vorbild inklusive Setter/Getter-Paar:
`warn_egress.py:55-57,60-66`. Umfang: ContextVar + Override-Prüfung **vor** der
Stack-Inspektion + Context-Manager, die 11 Bestandsmarker bleiben Rückfall.

### Affected Files

| Datei | Änderung | Begründung |
|---|---|---|
| `src/services/comparison_parallel.py` | **CREATE** | geteilter Baustein: Executor, indexierte Rückgabe, `created_at`-Fixierung, Quellen-Override je Worker |
| `src/providers/call_log.py` | MODIFY | ContextVar + Context-Manager, Prüfung **vor** `inspect.stack()`; Marker bleiben Rückfall |
| `src/services/compare_preview_service.py:163` | MODIFY | Call-Site A → Baustein |
| `tests/tdd/test_compare_preview_service.py:285-311` | MODIFY | AC-7-Vertrag ablösen: ein Engine-Lauf **je Ort** statt einer je Ortsmenge |
| `tests/unit/test_comparison_parallel.py` | **CREATE** | Nachweise (a),(b),(d),(e) am Baustein |
| `tests/unit/test_call_source_ueber_threadgrenze.py` | **CREATE** | Nachweis (c) — Quellenauflösung im Worker-Thread |

`comparison_engine.py`: **unangetastet** — mechanisch prüfbar.
`scheduler_dispatch_service.py:451` und `api/routers/compare.py:71`: **nicht in diesem
Schnitt** (B1b) — sie behalten ihren heutigen `ComparisonEngine.run()`-Aufruf unverändert.

### Scope Assessment

| | Produktivcode | Test |
|---|---|---|
| Baustein `comparison_parallel.py` | ~40 LoC | |
| `call_log`-ContextVar + Context-Manager | ~15 LoC | |
| Call-Site A umstellen | ~10 LoC | |
| Nachweise (a),(b),(c),(d),(e) | | ~120–150 LoC |
| AC-7-Vertrag umbauen (Ersatz, kein Neubau) | | ~20–30 LoC |
| **Summe** | **~65 LoC** | **~140–180 LoC** |

**Gesamt ~205–245 LoC — unter dem 250er-Limit, ohne Override.** Der Nachweis (f)
(`top_ort` im Versandpfad) entfällt hier und gehört zu B1b.
Treiber ist auch so der **Nachweis**, nicht der Mechanismus.
Risk Level: **MEDIUM** (neue Nebenläufigkeit; Mechanik belegt äquivalent, Gegenmaßnahmen
bekannt, aber ausschließlich im interaktiven Pfad).

### Nachweise, die den Umbau bewachen müssen

| Nachweis | Fängt |
|---|---|
| (a) Ergebnisreihenfolge bei **künstlich gedrehter** Fertigstellungsreihenfolge | Reihenfolge kippt — der eigentliche Wirkort, heute ungeprüft (s. Korrektur 2) |
| (b) ein Ortsfehler reißt die anderen nicht mit | Best-effort-Semantik |
| (c) Quellenauflösung überlebt den Threadwechsel (≥2 Worker) | `call_log` wird blind — belegter Bestandsmangel |
| (d) `created_at` ist **ein** Zeitstempel für den ganzen Lauf | Zeitstempel hängt sonst am Zufall |
| (e) `time_window`/`forecast_hours` kommen bei **jedem** Ort an | Parameterverlust beim Aufteilen |
| ~~(f) `top_ort` im Versandpfad~~ | **B1b**, nicht dieser Schnitt — s. Risiko unten |

### Risiko für B1b: `top_ort` hängt am Merge

`scheduler_dispatch_service.py:460` liest `top_ort = result.locations[0].location.name` —
**nicht** `result.winner`. Der Wert geht in die API-Antwort und in
`save_compare_preset_status()`. Heute ist er durch die serielle Verarbeitung deterministisch;
nach dem Umbau hängt seine Korrektheit an der Merge-Reihenfolge. Das ist der Grund, warum die
Reihenfolge im Versandpfad **einen eigenen** Nachweis braucht und nicht in (a) aufgeht: in
der Vorschau ist die Reihenfolge Darstellung, im Versand ist sie ein Feldwert.
Das Verhalten selbst (erster konfigurierter Ort, nicht bester Score) wird **beibehalten** —
es ist Bestand seit #1359 und nicht Gegenstand dieses Tickets.

### Open Questions

Beide Zuschnittfragen wurden am 2026-08-15 vom PO an den Tech Lead delegiert und oben
entschieden (zwei Schnitte; Cron-Lastfrage nach B1b verlagert, weil sie dort erstmals
auftritt). Für diesen Schnitt bleibt **keine** offene Frage.

Für **B1b** vorzumerken:
- [ ] Cron-Überlagerung mehrerer Nutzer gegen das Météo-France-Kontingent — benannte Grenze
      oder eigenes Kontingent-Gate? Dann mit Betriebsdaten aus B1 zu entscheiden.
- [ ] `top_ort`-Nachweis im Versandpfad (Risiko oben).

## Nicht in diesem Workflow

- **U4** (fehlender Grundvorhersage-Cache im Vergleichspfad) — dokumentierte Zurückstellung
  aus `fix_1329_forecast_cache_budget.md:399-407`; hilft dem gemeldeten Kaltstart strukturell
  ohnehin nicht.
- **#1839 / Trip-Pfad** — Scheibe B2, eigener Workflow.
- **#1539** (Wurzel: sequenzielle Verarbeitung generell) — unberührt.
- **Timeout-Leiter** (R6) — B2, erst nach gemessener neuer Laufzeit.
