# Context: fix-1447-alarm-timeout

Issue: #1447 (Ursprung: henemm-infra#147, dort geschlossen)

## Request Summary

Der Scheduler-Job „Alert Checks (every 15 min)" scheitert sporadisch für Nutzer `henning`
mit `context deadline exceeded` — genau 120 Sekunden nach Job-Start. Ein Alarm-Zyklus
fällt damit aus, eine Wetterwarnung kann sich um bis zu 15 Minuten verzögern.

## Belegte Faktenlage (Live-Logs, 2026-08-01 erhoben)

| Fakt | Beleg |
|---|---|
| 3 Vorfälle seit 20.07.: 30.07. 13:02, 31.07. 14:17, 31.07. 14:47 | `journalctl -u gregor-api`, alle mit `context deadline exceeded` |
| Immer derselbe Nutzer (`henning`), immer derselbe Job (`alert_checks`) | ebd. |
| **Normalfall ist unter 1 Sekunde** | Go-Log: `alert-checks?user_id=henning → 200` fast immer in derselben Sekunde |
| Ausreißer existieren: 27 s (31.07. 15:45), 49 s (31.07. 15:00) | ebd. |
| Beim Vorfall taucht der henning-Lauf im Python-Log **gar nicht** auf — auch nicht verspätet | `journalctl -u gregor-python`, Fenster 14:15–15:05 |
| Der Folge-Nutzer `steffi` kam 2 Minuten zu spät dran | Python-Log 31.07. 14:17:00 |

**Wichtigste Ableitung:** Der Sprung von unter 1 Sekunde auf über 120 Sekunden ist kein
langsames Anwachsen der Arbeitsmenge. Die Erklärung des Issues („henning hat 9 Briefings,
also die größte Angriffsfläche") greift zu kurz — 9 Briefings, die normalerweise in unter
einer Sekunde durchlaufen, machen im Regelfall **gar keine** Netzabrufe. Der Ausreißer ist
ein Lauf, in dem echte Abrufe stattfinden.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/scheduler/scheduler.go:82` | `http.Client{Timeout: 120s}` — geteilt von **allen** HTTP-Jobs |
| `internal/scheduler/scheduler.go:148-183` | `runForAllUsers` — sequenziell, continue-on-error, gibt `firstErr` zurück |
| `internal/scheduler/scheduler.go:342-359` | `recordRun` — Status ist binär `ok`/`error`, **kein** `partial` |
| `internal/scheduler/scheduler.go:79` | `cron.New(...)` **ohne** `WithChain(SkipIfStillRunning)` |
| `api/routers/scheduler.py:45-52` | `/alert-checks`, synchron, läuft im Threadpool |
| `src/services/trip_alert.py:275-362` | `check_all_trips` — sequenziell, **kein Zeitbudget** |
| `src/services/trip_alert.py:344`, `:903-972` | `check_official_alert_triggers` — läuft **vor** allen Drosseln |
| `src/services/trip_alert.py:803-858` | `_fetch_fresh_weather` — Schleife über alle Segmente, kein Budget |
| `src/providers/openmeteo.py:61,96-103,787-1052` | 30 s × 5 Versuche + Backoff, **keine** `FETCH_DEADLINE` |
| `src/providers/meteofrance.py:85,199-205,226` | **Vorbild:** `FETCH_DEADLINE_SECONDS = 180.0` |
| `src/providers/dwd.py:69,184-190,208` | dito, aus meteofrance übernommen |
| `src/services/official_alerts/meteoalarm.py:133,786-800,1042` | `_PAGE_FETCH_BUDGET_SECONDS = 20.0` **je Aufruf je Land** |
| `src/services/weather_cache.py:294-305` | Cache-TTL **600 s** bei Scheduler-Takt **900 s** |
| `src/services/trip_report_scheduler.py:50-51,1135-1137` | **Vorbild:** `FETCH_RETRY_ATTEMPTS = 2` + `fail_fast` im Briefing-Pfad |

## Existing Patterns

1. **Gesamt-Zeitbudget je Abruf-Einheit** (`FETCH_DEADLINE_SECONDS`, monotone Uhr, Prüfung
   vor jedem Einzel-Request, sichtbarer `ProviderRequestError` statt stillem Teilergebnis).
   Eingeführt als Adversary-Befund F004 in #1143. Testmuster:
   `tests/tdd/test_meteofrance_direct_fallback.py:476-517` — echter langsamer HTTP-Server,
   Deadline per `monkeypatch` auf 0,12 s geschrumpft.
2. **Gekappte Wiederholung im wiederkehrenden Job** — der Briefing-Pfad hat das bereits
   (`FETCH_RETRY_ATTEMPTS = 2`, `fail_fast`). Der Alarm-Pfad hat es nicht.
3. **Nebenläufige Segment-Abrufe** — `stage_weather.py:157` (`ThreadPoolExecutor`, ≤8).
   Nur im Briefing-Pfad, nicht im Alarm-Pfad.
4. **Hartkodierte Timeouts** sind repoweit das gültige Muster (`internal/egress/guard.go:60`).

## Dependencies

**Upstream (was der Alarm-Pfad benutzt):**
- `SegmentWeatherService` → `openmeteo` → Modell-Fallback (#1115) → Cross-Provider (#1141)
  → `dwd` / `meteofrance` / `geosphere` (je bis zu 96 Einzel-Calls, eigene 180-s-Deadline)
- 6 amtliche Warn-Quellen (Vigilance, MeteoForets, MassifClosure, GeoSphereWarn,
  MeteoAlarm, DPC)

**Downstream (was dieselbe Kette mitbenutzt und von einer Änderung mitbetroffen wäre):**
- `/compare-alert-checks` — identischer SegmentWeatherService/openmeteo-Pfad
- `/trip-reports` — derselbe Pfad, aber mit eigener Retry-Kappung
- `/compare-official-alert-checks` — derselbe Warn-Pfad
- Telegram-Versandtakt: `docs/specs/modules/telegram_send_pacing.md:64,95,210,258` rechnet
  ausdrücklich gegen die 120 s. Eine **Verkleinerung** des Go-Timeouts macht die dortige
  Reserve ungültig.

## Existing Specs

| Dokument | Status | Kernaussage |
|---|---|---|
| `docs/specs/modules/api_retry.md` | draft, nicht approved | 5 Versuche / 2–60 s Backoff / {502,503,504}. Referenz-Pattern, von allen Providern kopiert. |
| `docs/specs/_archive/modules/go_scheduler.md` | superseded | 120 s „großzügig bemessen, typisch 5–30 s". Retry für Jobs ausdrücklich Out of Scope. |
| `docs/specs/_archive/modules/issue_1155_openmeteo_retry_tuning.md` | approved | **Darf nicht zurückgedreht werden:** Primär-Kandidat behält volle 5 Versuche; Folge-Kandidaten genau 1 Versuch ohne Backoff. |
| `docs/specs/_archive/modules/issue_1128_openmeteo_retry_fix.md` | implementiert | Retry-Prädikat erkennt `__cause__`. |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | akzeptiert | Ausweichen ja, Kaschieren nein: jedes Ausweichen wird markiert und erzeugt ein wachsendes Health-Signal. |

**Es gibt kein ADR zu Wartezeiten/Wiederholungen/Scheduler-Timeouts.** Beide Retry-Specs
haben das geprüft und dokumentiert. Eine Grundsatzentscheidung hier braucht daher ein neues ADR.

## Risks & Considerations

1. **Die 120 s gelten pro Nutzer-Aufruf, nicht pro Job.** Bei N Nutzern kann `alert_checks`
   bis zu N × 120 s dauern.
2. **Kein Überlappungsschutz.** `cron.New()` läuft ohne `SkipIfStillRunning`. Der Vorschlag
   des Issues, den Go-Timeout auf 300 s anzuheben, vergrößert diese Lücke direkt: schon ~3
   langsame Nutzer reißen dann den 15-Minuten-Takt, und zwei Läufe schreiben gleichzeitig
   `lastRuns`.
3. **Kein Teilerfolg-Status.** Ein gescheiterter Nutzer macht den ganzen Job `error`, mit der
   Fehlermeldung nur des ersten Fehlers.
4. **Die Alert-Jobs haben keinen Heartbeat.** Ihr einziges Signal ist `lastRuns` in
   `/api/scheduler/status`.
5. **Wiederholungs-Zahlen zu senken ist nicht frei.** Fest eingetragene Erwartungen in
   `tests/tdd/test_meteofrance_direct_fallback.py:364` und `tests/tdd/test_dwd_direct_fallback.py:443`
   (`request_count == 5`) sowie die #1155-ACs.
6. **Offen und ungeklärt:** Läuft der abgebrochene Python-Lauf im Hintergrund zu Ende und
   verschickt die Alarme trotzdem? Der Endpunkt ist synchron im Threadpool, der
   Client-Abbruch beendet ihn vermutlich nicht — bewiesen ist das nicht. Das entscheidet,
   ob überhaupt ein Alarm verloren geht oder nur die Statusmeldung falsch ist.
7. **`pytest-timeout` steht global auf 30 s** (`pyproject.toml:63`). Jeder neue
   Zeitbudget-Test braucht ein geschrumpftes Budget per `monkeypatch`, kein echtes Warten.

## Analyse-Ergebnis (Phase 2)

### Die Diagnose des Issues ist nicht belegt — und spricht gegen sich selbst

Das Issue nennt als Ursache den Wiederhol-Zyklus von Open-Meteo (5 × 30 s + Backoff = ~180 s).
Die Messdaten stützen das nicht:

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| Open-Meteo-Abrufe im Vorfallsfenster | **null** | `data/diagnostics/openmeteo_calls.jsonl`, 31.07. 12:14–12:22 UTC |
| Werden Fehlversuche protokolliert? | **ja, jeder** | `src/providers/openmeteo.py:551` schreibt im `except httpx.RequestError`-Zweig. 5 Versuche ⇒ 5 Zeilen |
| Warn-Dienst-Abrufe im Vorfallsfenster | 43, **alle in der ersten Sekunde**, `cache_hit: true` | `warn_service_calls.jsonl`, Ticks 12:15/12:30/12:45 identisch |
| Tages-Kontingent | 592 von 9000 (6,6 %) | `data/diagnostics/forecast_budget.json` |
| Log-Ausgabe in allen drei Vorfallsfenstern | **null Zeilen** | `journalctl -u gregor-python`, alle 3 Fenster |
| Zustandsdateien während der Vorfälle geschrieben | **keine** | `alert_log.json`, `throttle_state.json`, `alert_state/` |

**Gegenprobe, die den Punkt entscheidet:** Am 31.07. um 14:30 hat Open-Meteo tatsächlich reihenweise
`503` geliefert — der Systemjournal ist voll davon. **Dieser Lauf war in unter einer Sekunde fertig.**
Die drei Hänger dagegen waren vollkommen still. Ein Wiederhol-Sturm sieht anders aus.

### Was der hängende Lauf war, lässt sich aus Produktionsdaten nicht entscheiden

Der Lauf hat keine Spur hinterlassen: keine Abrufe, keine Logzeile, keine geschriebene Datei.
Grund ist ein Beobachtbarkeitsloch: Der Root-Logger ist nirgends konfiguriert
(`api/main.py:18`, kein `basicConfig`/`dictConfig` im ganzen Repo). Uvicorn konfiguriert nur
seine eigenen Logger. Damit werden **alle `logger.info(...)` aus `src/` verworfen** — genau die
Zeilen, die einen Versand-Backoff oder ein Drossel-Warten belegen würden
(`trip_alert.py:220`, `telegram.py:245`). `warning`/`error` landen über `logging.lastResort`
auf stderr, ohne Zeitstempel und ohne Modulnamen.

### Was stattdessen belegt ist: der Pfad hat keine einzige harte Zeitgrenze

Es gibt im gesamten Alarm-Pfad **keinen** Punkt, an dem die Zeit gedeckelt wird — und
mindestens drei Stellen, die unbegrenzt blockieren können:

| # | Unbegrenzter Blockierer | Datei:Zeile | Grenze |
|---|---|---|---|
| B1 | `smtplib.SMTP(host, port)` **ohne `timeout=`** | `src/output/channels/email.py:433` | **keine** — `connect`/`starttls`/`login`/`sendmail` können beliebig lange hängen. Dazu 50 s garantierter Retry-Schlaf (`:624-625,668,713`) und ein ebenso ungeschützter Ersatzweg |
| B2 | Telegram-Drosselbremse `_reserve_send_slot`, `while True` ohne Versuchsobergrenze | `src/output/channels/telegram.py:210-250` | je Runde bis 60 s, beliebig viele Runden |
| B3 | `fcntl.flock(LOCK_EX)` ohne `LOCK_NB`/Timeout, auf einer **globalen, nicht nutzergetrennten** Datei, genommen **je Segment** | `src/services/forecast_budget.py:178` (auch `throttle_store.py:115`, `meteoalarm_budget.py:231`) | **keine** |
| B4 | `check_all_trips()` selbst | `src/services/trip_alert.py:275-362` | **kein Gesamtbudget** |
| B5 | `openmeteo.fetch_forecast()` | `src/providers/openmeteo.py:787-1052` | **kein `FETCH_DEADLINE`** — anders als `dwd.py:69` und `meteofrance.py:85` |

Die einzige Grenze im ganzen System sind die 120 s des Go-Clients — und die kappen nur die
HTTP-Verbindung. Der Python-Thread läuft danach weiter (synchroner Endpunkt im Threadpool,
`api/routers/scheduler.py:46`, uvicorn ohne `--workers`/`--limit-concurrency`).

### Bewertung der Vorschläge aus dem Issue

| Vorschlag | Bewertung |
|---|---|
| 1. Wiederhol-Verhalten im Alarm-Pfad begrenzen | **Zielt daneben.** Der Wiederhol-Zyklus war nachweislich nicht beteiligt. Zusätzlich ist die Zahl durch #1155 (approved) und fest eingetragene Test-Erwartungen gebunden. |
| 2. Go-Wartezeit auf 300 s anheben | **Verschlimmert.** Es gibt keinen Überlappungsschutz (`cron.New()` ohne `SkipIfStillRunning`, `scheduler.go:79`), und die 120 s sind **pro Nutzer**. Bei 300 s reißen schon drei langsame Nutzer den 15-Minuten-Takt, und zwei Läufe schreiben gleichzeitig `lastRuns`. |
| 3. Teilerfolg melden statt „Job gescheitert" | **Richtig, aber nachrangig.** `recordRun` kennt nur `ok`/`error` (`scheduler.go:342-359`). |

### Empfohlene Stoßrichtung

Nicht die vermutete Einzelursache reparieren, sondern die **Klasse** schließen — die
Ursache ist heute grundsätzlich nicht feststellbar, und der nächste Vorfall wäre es wieder:

1. **Harte Obergrenze je Nutzer-Lauf** in `check_all_trips()`, deutlich unter den 120 s des
   Go-Clients, nach dem Vorbild `FETCH_DEADLINE_SECONDS` (monotone Uhr, Prüfung vor jeder
   Tour, sichtbarer Fehler statt stillem Teilergebnis).
2. **Timeouts auf die unbegrenzten Blockierer** B1–B3.
3. **Laufzeit je Nutzer und Job messen und melden**, damit der nächste Vorfall belegbar ist.
4. **Überlappungsschutz in Go** (`SkipIfStillRunning`) — anstelle einer Timeout-Anhebung.

### Offen geblieben

- Läuft der abgebrochene Python-Lauf im Hintergrund zu Ende? Der synchrone Endpunkt im
  Threadpool spricht dafür; die fehlenden Zustandsschreibvorgänge sprechen dagegen.
  **Nicht entscheidbar ohne die Messung aus Punkt 3.**
- 2 der 3 Vorfälle waren der **erste 15-Minuten-Tick nach einem Dienst-Neustart**
  (30.07. Neustart 12:56 → Tick 13:00; 31.07. Neustart 14:38 → Tick 14:45). Der dritte
  (31.07. 14:15) nicht. Ein Kaltstart-Effekt ist damit möglich, aber nicht belegt.
