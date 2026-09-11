# Context: fix-2302-provider-zeitbudget

> Issue **#2302** · Epic #2257 Block 2 (Fallback-Härtung) · Track **Full Process**
> Vorgänger-Recherche: `docs/context/fix-2121-gewitter-zeitbudget.md`
> **Alle Zeilennummern in diesem Dokument sind am 11.09.2026 frisch aus dem Code
> hergeleitet** — die Angaben im Ticket und in #1539 waren teilweise gewandert.

## Request Summary

Vier der fünf Wetterquellen prüfen ihr Zeitbudget nur **zwischen** zwei `_request`-Aufrufen,
nie **innerhalb** eines Aufrufs. Das Gegenmittel existiert bereits in
`src/providers/openmeteo.py` (gebaut unter #1448 S3), ist aber kopiert statt geteilt.

### 🔴 Präzise Fassung des Mechanismus — die lockere Formulierung führt in die Irre

**Eine einzelne HTTP-Anfrage hängt NICHT unbegrenzt.** Alle fünf Provider bauen
`httpx.Client(timeout=TIMEOUT)` mit `TIMEOUT = 30.0` als **Skalar** (`dwd.py:59`,
`dwd_eu.py:78`, `meteofrance.py:78`, `geosphere.py:50`, `openmeteo.py:62`). Ein Skalar setzt
bei httpx `connect`/`read`/`write`/`pool` **gleich** — die Read-Phase bricht nach 30 s mit
`httpx.ReadTimeout` ab. Die Ticket-Bemerkung, es fehle `httpx.Timeout(connect=…, read=…)`,
benennt daher **keinen** Defekt: der Skalar setzt `read` bereits.

**Der Befund ist die ungebremste Summe der Retry-Kette**, nicht ein endloser Einzelabruf:
`ReadTimeout` ist in allen vier `_is_retryable_error` wiederholbar (z. B. `dwd.py:139`), der
Dekorator feuert 5 Versuche mit 2–60 s Backoff (`dwd.py:316-322`) — und **erst danach** kommt
die Budgetprüfung wieder dran. Die Zusicherung muss also die **Kette** deckeln, nicht den
einzelnen Versuch.

### 🔴 Der eine wirklich unbegrenzte Fall — und er wird vom Vorbild NICHT gedeckt

Das httpx-Timeout begrenzt die Wartezeit **auf das nächste Stück Daten**, nicht die
Gesamtdauer der Antwort. Jedes eintreffende Byte stellt die Uhr zurück. Eine Gegenstelle,
die langsam tröpfelt, läuft damit **unbegrenzt**.

**Selbst gemessen** (lokaler Server, ein Byte alle 0,3 s, Skalar-Timeout 0,5 s):

```
ERFOLG nach 6.08s (Skalar-Timeout 0.5s, Body=20B)
=> Faktor 12.2x ueber dem Timeout — Skalar deckelt die GESAMTDAUER NICHT.
```

Der Abruf galt als **Erfolg**, kein Timeout. Wichtig: Das Muster aus `openmeteo.py` hilft
dagegen **ebenfalls nicht** — `min(TIMEOUT, restzeit)` (`:673`) ist wieder nur ein Skalar
derselben Art, und `_stop_at_request_deadline` greift ausschließlich **zwischen** zwei
Versuchen.

**Folge für die Spec:** Der Fix deckelt die **Wiederholungskette** verlässlich. Er deckelt
**nicht** eine einzelne, beliebig lang hingezogene Antwort. Das gehört als ausdrückliche
Grenze in die Spec — sonst steht eine Zusicherung im Haus, die nicht hält. Ob der
Tröpfel-Fall mitgenommen wird, ist eine eigene Entscheidung (**D6**); er braucht ein
anderes Mittel als das kopierte Muster.

## Drei Korrekturen am Ticket — vor der Analyse zu klären

Das Ticket ist in der Sache richtig, aber drei seiner Angaben halten der Nachmessung nicht
stand. Sie verschieben den Zuschnitt.

### K1 — Die 120-Sekunden-Begründung ist überholt

Das Ticket stützt die Dringlichkeit darauf, dass `ALERT_RUN_DEADLINE_SECONDS = 90.0`
bewusst „spürbar unter" den 120 s des Go-Schedulers liege. **Der Cron-Scheduler wartet
heute 3000 s** (`internal/scheduler/scheduler.go:161`), geändert unter **#1912**, weil
120 s reguläre Versandläufe abschnitten (längster gemessener Einzelversand 319 s).
ADR-0038 zitiert noch `scheduler.go:82` mit 120 s; der Kommentar in `trip_alert.py:61-65`
ebenfalls. Beide Stellen sind veraltet.

**Der manuelle Anstoß aus dem Frontend hat weiterhin 120 s**
(`internal/handler/proxy.go:112`, geroutet über `internal/router/router.go:221`).

**Folge:** Der Schaden liegt nicht mehr beim wartenden Scheduler, sondern am
**15-Minuten-Takt** (`scheduler.go:192`). Überlappt ein Lauf seinen Vorgänger, wird der
Folgetick per `TryLock` übersprungen (`scheduler.go:127-132`, `:532-539`) — die
Alarmprüfung findet in dem Zyklus nicht statt. Das ist die Schadensform, die die Spec
adressieren muss.

**🔴 Und die Änderung senkt die Dringlichkeit nicht, sie erhöht sie.** Die alten 120 s
wirkten als **unfreiwilliger Notausgang**: Ein interner Stall wurde von außen nach rund
zwei Minuten abgeschnitten, ob man wollte oder nicht. Mit 3000 s fehlt dieser Notausgang.
Ein Stall von bis zu ~390 s je Abruf — bei DWD/ICON-EU mit Lauf-Rückfall bis zu ~3 × 390 s
≈ 1170 s, also fast 20 Minuten (K3) — läuft jetzt **ohne jedes äußere Eingreifen** durch.
Bei einem 15-Minuten-Takt heißt das: **potenziell mehr als ein** übersprungener Tick, nicht
nur der Folgetick. Das gehört in die Begründung, nicht in eine Fußnote.

### K2 — Météo-France ist auf dem Gewitter-Pfad bereits geschützt

Das Ticket führt `meteofrance.py` pauschal als ungeschützt. Tatsächlich gibt es dort
**zwei** Pfade, und nur einer ist offen:

| Pfad | Call-Site | `timeout=` | Retry | Wirksamer Deckel |
|---|---|---|---|---|
| `fetch_forecast` → `_fetch_series` (`:508`) → `_request` (`:428`) → `_request_once` | `:434` | **nein** | **ja** | 30 s **je Versuch** |
| `fetch_thunder_signals_multi` → `_request_once` **direkt** | `:644-648` | **ja, `timeout=restzeit`** | nein | `min(30, restzeit)` |

Das 45-s-Gewitterbudget hält also bereits innerhalb eines Abrufs — es ist die **einzige**
Restzeit-Weitergabe in allen vier Dateien. Offen ist dort nur das 180-s-Budget der
Grundvorhersage.

### K3 — Der Ernstfall ist größer als 390 s

Das Ticket rechnet `5 × 30 s + 4 × bis 60 s ≈ 390 s` je Abruf. Dazu kommt ein vom Ticket
nicht genannter Multiplikator: **Alle drei Gewitter-Pfade haben einen `while True`-Rückfall
über bis zu drei Modell-Lauf-Kandidaten, ohne Budgetprüfung dazwischen** —
`dwd.py:364-391`, `dwd_eu.py:333-358`, `meteofrance.py:641`. Bei DWD und ICON-EU feuert
jeder Kandidat einen vollen **geretryten** `_request`; der Ernstfall je Signalabruf liegt
dort bei rund **drei mal 390 s**. (Bei Météo-France nicht, s. K2.)

## IST-Stand der vier Quellen

| Datei | Budget | Prüfstelle | Timeout am Abruf | Retry-Deckel |
|---|---|---|---|---|
| `dwd.py` | Grund `180.0` (`:69`) · Gewitter `150.0` (`:119`) | `:341` zwischen Offsets · `:468`/`:486` je (Offset × Signal) · **nicht** im Lauf-Rückfall `:364-391` | **keiner** (`:326`) → 30 s aus dem Client | 5 ×, 2–60 s, `{500,502,503,504}` — **auch im Gewitterpfad** |
| `dwd_eu.py` | — · Gewitter `25.0` (`:134`) | `:408` zwischen Offsets je Signal · **nicht** im Lauf-Rückfall `:333-358` | **keiner** (`:315`) → 30 s | 5 ×, 2–60 s, `{500,502,503,504}` — **auch im Gewitterpfad** |
| `meteofrance.py` | Grund `180.0` (`:93`) · Gewitter `45.0` (`:114`) | `:501` zwischen Offsets · `:632` je (Gruppe × Offset), **unter** dem Cache-Zugriff `:628` · `:680` zwischen Lauf-Kandidaten | Grund **keiner** (`:434`) → 30 s · Gewitter **`timeout=restzeit`** (`:647`) | 5 ×, 2–60 s, `{500,502,503,504}` — Gewitterpfad **ohne** Retry |
| `geosphere.py` | **keines** | **keine** | `:320` **keiner** → 30 s · `:429` fest `3.0` · `:546` fest `10.0` | 5 ×, 2–60 s, **`{502,503,504}` — ohne 500**; `:429`/`:546` ohne Retry |

Alle vier bauen den Client mit einem **Skalar**-Timeout: `dwd.py:310`, `dwd_eu.py:299`,
`meteofrance.py:412-415`, `geosphere.py:223`. Das ist für sich **kein** Defekt (s. Request
Summary) — der Skalar setzt `read` mit.

### Der sechste HTTP-Pfad im Alarm-Lauf — vollständigkeitshalber

Die Rede von „vier von fünf Quellen" verschweigt einen weiteren Alarm-relevanten
Aufrufpfad: **`src/services/radar_service.py:849`** baut `httpx.Client(timeout=HTTPX_TIMEOUT)`
mit `HTTPX_TIMEOUT = 8.0` (`:143`). Aufgerufen im **selben** Alarm-Lauf über
`trip_alert.py:1460-1465` (`_get_radar_service`) und `trip_alert.py:1587`
(`check_radar_alerts`); Regen-/Radar-Alarme sind eine reguläre Alarmart.

**Bewertung: unkritisch — aber geprüft, nicht übergangen.** Das Modul hat **keinen**
`@retry`-Dekorator (gezielter Grep: keine Treffer). Die Problemklasse „Retry-Kette summiert
sich" existiert dort also nicht; ein Einzelabruf bleibt durch den 8-s-Skalar gedeckelt.
Der Tröpfel-Fall (D6) gilt allerdings auch hier.
**Zu entscheiden:** Soll der Baustein so gebaut sein, dass ein künftiger Retry in
`radar_service.py` nicht dieselbe Lücke aufreißt?

Ebenfalls geprüft und **zurecht draußen**: `brightsky.py` (`TIMEOUT = 8.0`) ist zwar in
`base.py:296-297` registriert, wird aber nur von `validator_render_service.py` benutzt,
nicht von `region_routing.py` oder dem Alarm-Pfad.

**Ungeklärt, nicht entlastet:** `services/official_alerts/meteoalarm_feed.py:55`
(`TIMEOUT = 15.0`, Aufruf `:209`) — der Weg bis in den Alarm-Lauf ließ sich nicht
zurückverfolgen, er ist in `trip_alert.py` nicht referenziert. In `/30-write-spec` zu
klären oder ausdrücklich als außerhalb zu erklären.

### `geosphere.py` ist der Ausreißer

- Kein `deadline_at`, kein `time.monotonic()`, **kein `import time`** in der ganzen Datei.
- `fetch_combined` (`:588`) feuert bis zu drei Abrufe nacheinander (NWP `:618`, SNOWGRID
  `:623`, Open-Meteo-Wolken `:641`) ohne gemeinsame Frist.
- **Hängt am Alarm-Pfad:** `region_routing.py:34` bildet die Region AT (46,3–49,1 N,
  9,5–17,2 O) auf `at_direct` ab → `GeoSphereDirectProvider` (`regional_stubs.py:63-70`)
  → `fetch_combined` (`regional_stubs.py:88-95`). Das kann die 90 s aus `trip_alert.py:66`
  allein überziehen.
- Zweiter Weg, auch außerhalb Österreichs: Snowgrid-Anreicherung `openmeteo.py:505-507`
  → `geosphere.py:373`, ein Abruf über dasselbe ungedeckelte `_request`.
- Dritter Weg unkritisch: `thunder_routing.py:75` (DE_ALPEN) — ein Abruf, fest auf 3 s,
  ohne Retry.
- **Einschränkung:** Struktur-Befund aus dem Routing, kein durchgespielter Alarm-Lauf.
  Der Weg von `trip_alert` bis `region_routing` ist nicht bis in den Aufrufer verfolgt.

## Das Referenzmuster — `openmeteo.py` (#1448 S3)

Zwei getrennte Wirkungen, beide nötig:

| Zeile | Wirkung |
|---|---|
| `:673` `request_timeout = TIMEOUT if restzeit is None else min(TIMEOUT, restzeit)`, übergeben an `:677` | ein **laufender** Versuch kann die Frist nicht um bis zu 30 s überziehen |
| `:667-672` `restzeit <= 0` → sofort `ProviderRequestError` | ein **neuer** Versuch beginnt nach Fristablauf gar nicht erst |
| `:621` `stop=stop_after_attempt(RETRY_ATTEMPTS) \| _stop_at_request_deadline` (`:304-313`) | Versuchszahl **und** verstrichene Zeit begrenzen gemeinsam; greift die Stop-Bedingung, wird die Wartepause nicht mehr abgeschlafen |
| `:624` `before=_resolve_request_deadline` (`:286-301`) | fehlt `deadline_at`, setzt der Hook sie selbst — **die Zusicherung hängt nicht daran, dass eine Aufrufstelle den Parameter durchreicht** |

**Der `if … is None`-Wächter ist der Kern:** `before` feuert vor *jedem* Versuch. Ohne den
Wächter wäre die Ersatzfrist **rollend** — jeder Versuch bekäme wieder volle 60 s, die
Obergrenze wäre wirkungslos. Mechanisch trägt es, weil `retry_state.kwargs` dieselbe
dict-Instanz ist, die tenacity in `fn(*args, **kwargs)` entpackt.

**Für den Zuschnitt entscheidend:** Weil der `before`-Hook die Frist notfalls selbst setzt,
ließe sich die Zusicherung **allein am Dekorator** herstellen — ohne jeden der Dutzenden
Aufrufpfade in vier Dateien anzufassen.

### Was `openmeteo.py` NICHT löst — Grenze der Vorlage

Die Vorlage deckt die Begrenzung **eines einzelnen `_request`** ab. Genau das ist die Sache
von #2302. Sie deckt **keine Gesamtgrenze über die Anreicherungskette** ab:

- `:1010` bildet `deadline_at` **nur für die Kandidatenschleife** (`:1064-1104`).
- `:1147` `_fetch_uv_data`, `:1169` `_fetch_ensemble_spread`, `:1239` `_enrich_snow`,
  `:1247` `_enrich_thunder` laufen **alle nach Ablauf dieser Frist, keine unter ihr**.
- `:1110/:1116` ruft bei Totalausfall den Direktprovider — **ohne** `deadline_at`.

Das ist ADR-0038-/#1539-Gebiet und gehört **ausdrücklich nicht** in diesen Fix. Die Spec
muss die Zusicherung entsprechend eng formulieren, sonst zitiert sie eine Garantie, die
es so nicht gibt.

### 🔴 Die Falle beim Portieren — die Vorlage hat selbst eine Lücke

| Pfad | Zeile | `stop=` |
|---|---|---|
| erster Kandidat | `:1077-1079` → Dekorator `:621` | `stop_after_attempt(…) \| _stop_at_request_deadline` |
| Folge-Kandidaten | `:1084-1087` | `stop_after_attempt(FALLBACK_RETRY_ATTEMPTS)` — **zeitbasierte Bedingung ist weg** |

`retry_with(stop=…)` **ersetzt** den `stop`-Parameter, es ergänzt ihn nicht
(`tenacity/__init__.py:262-275`, `stop=_first_set(stop, self.stop)`). Der `before`-Hook
überlebt, die Stop-Seite nicht.

**Heute folgenlos:** `FALLBACK_RETRY_ATTEMPTS = 1` (`:107`) mit `wait=wait_none()`
(`:1086`) lässt gar keine Wiederholkette entstehen; die Frist wirkt dort allein über
`:667-672` und `:673`.

**Beim Portieren real:** Setzt jemand bei einer der vier anderen Quellen den
Fallback-Zähler > 1 **und** eine echte Wartefunktion, überzieht die Kette die Frist um
**eine volle Wartepause**, im Extremfall `RETRY_WAIT_MAX = 60 s` (`:112`) — tenacity prüft
nur noch die Versuchszahl, schläft die Pause ab, erst der Kopf-Check des *nächsten*
Versuchs bricht ab. Danach ist Schluss (der bei `:668` geworfene `ProviderRequestError`
trägt weder `status_code` noch `__cause__`, `_is_retryable_error` liefert `False`).
Es passiert **still**: `test_stop_condition_limits_retry_backoff_within_deadline` (`:673`)
misst ausschließlich den Pfad des ersten Kandidaten.

### Wo die Frist lebt — und warum das so gebaut ist

Weder Instanz-Attribut noch ContextVar noch Thread-Local: ausschließlich in
`retry_state.kwargs["deadline_at"]`, im `RetryCallState`, den tenacity **je Aufruf frisch**
anlegt (`tenacity/__init__.py:475`).

- **Per-Call sicher** — parallele `_request`-Aufrufe teilen die Frist nicht.
- **tenacity-Iterationszustand** liegt in `threading.local()` (`tenacity/__init__.py:240`).
- **🔴 Das Konfigurationsobjekt ist geteilt:** `OpenMeteoProvider._request.retry` ist ein
  prozessweit **einziges** `Retrying`-Objekt, und Tests patchen genau dieses
  (`test_send_slot_and_fetch_deadline.py:410-411`, `:594-595`, `:642-643`, `:710-711`).
  **Genau deshalb** liest der Mechanismus die Frist aus `kwargs`, statt je Aufruf ein
  `retry_with(stop=…)` zu bauen — so bleibt die geteilte Konfiguration unangetastet.
  Ein geteilter Baustein muss diese Eigenschaft erhalten.

## Fristen-Kette von außen nach innen

| Ebene | Wert | Prüfgranularität | Beleg |
|---|---|---|---|
| Cron-Scheduler → Python-Core | **3000 s** | je Aufruf | `scheduler.go:161` |
| Manueller Anstoß (Frontend) | **120 s** | je Aufruf | `proxy.go:112` |
| Takt / Überlappung | **15 min**, Folgetick wird verworfen | je Tick | `scheduler.go:192`, `:127-132` |
| Alarm-Lauf | **90 s** | **nur zwischen zwei Trips** | `trip_alert.py:66`, gesetzt `:863`, geprüft `:867` |
| Provider-Budget | 25–180 s | zwischen Offsets/Signalen | s. IST-Tabelle |
| Einzelabruf | 30 s **je Versuch** | — | Client-Skalar |

**Die Fristen sind nicht gestaffelt, sie stehen nebeneinander.** Jedes Provider-Budget wird
**je Abruf neu** gebildet, nie einmal je Durchgang: `openmeteo.py:1010`,
`meteofrance.py:734`/`:612`, `dwd.py:541`/`:450`, `dwd_eu.py:404`. Ein Trip mit acht
Etappen bekommt achtmal ein frisches 60-s-Budget, keines davon weiß von den 90 s.

Hängt **ein** Trip, erreicht die Schleife die Prüfung in `trip_alert.py:867` nie — der
Durchgang läuft unbegrenzt weiter. Bei Erreichen der Frist: `hit_deadline = True`, `break`
(`:868-869`), Rest zählt als `skipped`, Router übersetzt nach `status: "partial"` +
`reason: "deadline"` (`api/routers/scheduler.py:74-82`), Go bucht `partialRunError`
(`scheduler.go:653-658`).

**Der Alarm-Pfad ist seriell, die anderen nicht.** `check_all_trips` läuft seriell über
Trips, `_fetch_fresh_weather` seriell über Segmente (`trip_alert.py:2444`); Go durchläuft
Nutzer seriell (`scheduler.go:265`). Parallel sind nur: Ortsvergleich
(`comparison_parallel.py:118-120`, `MAX_PARALLEL_LOCATIONS = 4` bei `:42`) und
Briefing/Vorschau (`stage_weather.py:174`, bis zu 8). Kein `asyncio.gather`, keine
`threading.Thread` im Abrufpfad.

**Übersprungene Ticks sind gezählt und sichtbar** — brauchbar als Beobachtungsgröße:
`jobOverlapState.SkippedSinceLastRun` mit JSON-Tag `skipped_since_last_run`
(`scheduler.go:39-48`, Feld `:46`), hochgezählt beim `TryLock`-Fehlschlag (`:558-568`),
zurückgesetzt erst bei einem **tatsächlich ausgeführten** Lauf (`:579-580`), ausgegeben
über `overlapField(jobID)` (`:750-762`, `nil` bei Ruhe) in `Status()`.

### 🔴 Die Budgets addieren sich, statt sich zu begrenzen (Bestandszustand)

Drei Ebenen Fallback, nur die erste führt ein Budget mit:

1. **Modell-Fallback in Open-Meteo** (`openmeteo.py:1064-1101`, #1115) — **gemeinsames**
   Budget, `deadline_at` aus `:1010` an alle Kandidaten durchgereicht.
2. **Cross-Provider bei Totalausfall** (`openmeteo.py:1108-1132`) — `:1116` übergibt
   **kein** `deadline_at`; die Signaturen der Ersatzprovider (`meteofrance.py:719`,
   `dwd.py:528`, `geosphere.py:230`) kennen keinen solchen Parameter. Jeder bildet eine
   neue volle Frist (`meteofrance.py:734`, `dwd.py:541`, je 180 s); GeoSphere **gar keine**.
3. **Vertretung der Gewitterquelle** (`thunder_enrichment.py:482`, `:509`, `:534`) —
   **eigenes volles Budget, ausdrücklich dokumentiert** (`thunder_enrichment.py:500-502`:
   „mit ihrem eigenen vollen Zeitbudget, keine Restzeit-Weitergabe").

Summiert je Segment möglich: 60 s + 180 s + 45/150 s + Vertretung. `meteofrance.py:105-113`
benennt das **selbst im Quelltext** als Bestandszustand, der das 90-s-Alarmbudget sprengt.

**Das ist NICHT Gegenstand dieses Fixes** — ADR-0047 Entscheidung 6 hat es so entschieden.
Hier nur als bekannte Grenze vermerkt, damit die Spec keine Wirkung verspricht, die sie
nicht hat.

## 🔴 Der Test-Rahmenbefund — die vorhandenen Wächter laufen im Normallauf nicht

`pyproject.toml:65` setzt `addopts = "-q -m 'not email and not live and not staging'"`.
Jede Datei, die heute ein Provider-Zeitbudget bewacht, trägt `pytestmark =
pytest.mark.live`, **obwohl keine davon echtes Netz braucht** — alle arbeiten gegen lokale
`ThreadingHTTPServer`/`socket`-Server auf `127.0.0.1`:

| Datei | Marker |
|---|---|
| `test_dwd_thunder_signal_fetch.py:117` | `live` |
| `test_dwd_thunder_new_signals_fetch.py:101` | `live` |
| `test_dwd_eu_thunder_time_budget.py:31` | `live` |
| `test_send_slot_and_fetch_deadline.py:91` | `live` |
| `test_thunder_budget_and_failsoft.py:50` | `live` |
| `test_alert_run_deadline.py` | **keiner** — läuft mit |

**Selbst nachgemessen (nicht vom Agenten übernommen):**

```
uv run pytest --collect-only test_dwd_eu_thunder_time_budget.py test_thunder_budget_and_failsoft.py
→ no tests collected (6 deselected) in 0.51s   [exit=5]
```

### Der Marker ist Absicht, nicht Versehen

`test_dwd_thunder_new_signals_fetch.py:73-76` hält den Grund im Docstring fest:

> „Kein echtes Netz -- trotzdem `pytestmark = pytest.mark.live` (identisches Vorbild:
> diese Provider-Tests laufen NICHT im Commit-Gate, sondern nur explizit via
> `pytest -m live`, CI-Vermessung #1196)."

`live` wird hier also als „vom Commit-Gate ausgenommen" benutzt, nicht in der Bedeutung
seiner eigenen Definition (`pyproject.toml:76`: „Tests that hit the real external weather
API"). Das ist eine **bewusste, dokumentierte Abwägung mit Aktenzeichen #1196** — kein
falsch gesetzter Marker. Der Befund bleibt trotzdem stehen: Die Wirkung ist, dass diese
Zusicherungen weder lokal noch in der CI laufen.

Die CI könnte sie ausführen: `.github/workflows/ci.yml:56-63` ruft `uv run pytest` ohne
`-m`-Override, und die Egress-Sperre erlaubt `127.0.0.1` ausdrücklich (`ci.yml:59-60`:
`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`). Sie werden
allein durch den Marker verworfen.

**Folge für die Spec:** Ein neuer Wächter, nach dem Muster der Nachbardateien gebaut, wäre
ab Tag eins unsichtbar. `tests/tdd/test_alert_run_deadline.py` ist die Vorlage.
Zu beachten ist dabei der globale `timeout = 30` (`pyproject.toml:69`) — ein Test, der
einen hängenden Server misst, braucht ein deklariertes `@pytest.mark.timeout(N)`.

### Was die bestehenden Wächter messen

`tests/tdd/test_dwd_eu_thunder_time_budget.py` (Marker `live`, Z. 31):

- `test_ac4_erschoepftes_gewitterbudget_bricht_nur_die_anreicherung_ab` (Z. 45) zählt
  **Abrufe**, nicht Zeit — als **Vergleich zweier Läufe** (Budget 60,0 gegen schnellen
  Server, dann 0,4 gegen `verzoegerung_s=0.15`). Assertions Z. 78-99: `ohne_zeitdruck > 8`
  (Positivkontrolle), `abrufe >= 1`, `abrufe < ohne_zeitdruck`, `abrufe <= 8`.
  Das Vergleichsbein stammt aus Adversary-Befund F003 — eine feste Schwelle allein wäre
  auch bei abgeschalteter Zeitgrenze grün geblieben.
- Der Verzicht auf eine Wanduhr-Assertion ist dort **ausdrücklich begründet**: „ein
  Laufzeit-Test misst die Maschine, nicht die Zeitgrenze". Diese Begründung ist beim
  Formulieren der neuen ACs zu entkräften oder zu übernehmen — nicht zu übergehen.
- Ein 390 s hängender Abruf lässt beide Tests grün.

Weitere: `test_dwd_thunder_signal_fetch.py:625` (feste Schwelle, **ohne** Vergleichslauf —
Asymmetrie zur F003-gehärteten Schwesterdatei), `test_dwd_thunder_new_signals_fetch.py:470`
(Reihenfolge unter Budgetdruck), `test_thunder_budget_and_failsoft.py:133` (**echte
Wanduhr**: `dauer < (_ANTWORTZEIT_S + _ZEITGRENZE_S)/2`, Z. 172),
`test_send_slot_and_fetch_deadline.py` (vier Wanduhr-Assertions gegen `_HangingServer`).

### Bausteine für den Nachweis (kein Mock-Theater nötig)

**`_HangingServer` — der richtige Baustein, und er existiert bereits für httpx.**
Original `tests/tdd/test_mail_send_deadline.py:63-116`, **httpx-Kopie
`tests/tdd/test_send_slot_and_fetch_deadline.py:140-188`** (Docstring Z. 143-146 verweist
aufs Original: „httpx blockiert dadurch beim Warten auf die HTTP-Antwort (Read-Phase)").
**Übernehmen, nicht nachbauen.**

- Roher TCP-Server, spricht kein Protokoll. `__init__(self)` ohne Parameter macht alles:
  `bind(("127.0.0.1", 0))`, `listen(8)`, Accept-Loop als Daemon-Thread (Z. 75-84).
  Instanziieren *ist* Starten.
- Nach außen: `.host`/`.port` (Z. 79), `.connection_count` (Z. 80, 95), `.close()`
  (Z. 98-109), Contextmanager `__enter__`/`__exit__` (Z. 111-116).
- Angenommene Verbindungen werden **nie bedient** — das erzeugt den Hang.
- **Achtung:** Der httpx-Kopie **fehlt `connection_count`**. Wer Verbindungsversuche zählen
  will, nimmt die Mail-Variante als Quelle.
- Nutzung immer als `with`-Block, jeder Test mit eigenem `@pytest.mark.timeout(10|12)`.
- Verwandt: `_ImmediateTempFailServer` (Z. 119-168) — antwortet sofort `421` und schließt,
  für wiederholte Fehlschläge **ohne** Hang.

**`eu_server(...)` reicht für den Hänger-Nachweis NICHT.** Korrigierte Fundstelle:
`tests/tdd/_dwd_eu_fixtures.py:223-251` (Z. 54-72 ist der Import-Block).

```python
@contextmanager
def eu_server(monkeypatch, *, inhalt=None, status_je_lauf=None,
              fehlende_zeitschritte=None, verzoegerung_s=0.0, fixtures=None)
```

`verzoegerung_s` ist ein **`time.sleep` VOR der Antwort** (Z. 172-173, Kopf von `do_GET`),
**kein Schweigen**. Für „nimmt an und antwortet nie" braucht es den `_HangingServer`.
Nützlich bleibt der `eu_server` für Abruf-Zählung: `.abrufe` und `.abrufe_mit_param`,
beide unter `threading.Lock` (Z. 164-166, 183-185); patcht `dwd_eu.BASE_URL` auf sich
selbst (Z. 245).

**Vorlage für die Wanduhr-Form:** `tests/tdd/test_send_slot_and_fetch_deadline.py` hat
**sechs** Wanduhr-Assertions gegen `_HangingServer`, alle mit `monkeypatch.setattr(...,
"FETCH_DEADLINE_SECONDS", …, raising=False)`. Besonders einschlägig:

| Test | Setzt | Assertion |
|---|---|---|
| `test_fetch_forecast_raises_provider_request_error_after_deadline` (Z. 385) | `FETCH_DEADLINE_SECONDS=0.4`, `TIMEOUT=0.2`, `wait_none()` | `elapsed < 0.9` (Z. 426) in `pytest.raises(ProviderRequestError)` |
| `test_single_hanging_request_aborts_within_deadline_without_candidate_switch` (Z. 554) | `0.3` (Z. 597) | `elapsed < 0.65` (Z. 609) |
| `test_request_explicit_deadline_at_overrides_default_fetch_deadline` (Z. 618) | Konstante `2.0`, **plus** `deadline_at = monotonic() + 0.15` (Z. 647) | `elapsed < 0.5` (Z. 659) — beweist, dass die übergebene Restzeit die Modulkonstante übersticht |
| `test_normal_case_unaffected_by_new_deadlines` (Z. 439) | — | `elapsed < 2.0` (Z. 483) — **Gegenprobe Normalfall** |

Die Gegenprobe ist Pflichtbestandteil: Ohne sie wäre ein Fix, der einfach alles sofort
abbricht, ebenfalls grün.

**Nicht taugliche Vorbilder:** `test_meteofrance_direct_fallback.py:481` setzt
`FETCH_DEADLINE_SECONDS=0.12` gegen einen `time.sleep(0.05)`-Server, assertet aber **nur**
`pytest.raises(ProviderRequestError)` — misst „wirft überhaupt", nicht „wirft rechtzeitig".

**Kategorie „nur `timeout=` durchgereicht" ist ein gemessener Null-Befund:** Ein gezielter
Grep über `tests/` nach Assertions auf `timeout`-Argumenten findet **keinen** Fall, in dem
ein Provider-Timeout per Argument-Inspektion an einem Mock nachgewiesen wird. Diese
Testform hat im Repo keine Tradition — und soll auch keine bekommen.

## Bindende Vorentscheidungen

| Quelle | Was sie festlegt | Folge für #2302 |
|---|---|---|
| **ADR-0047, Entscheidung 6** (PO, 06.08.2026) | Die Ersatzquelle bekommt ihr **volles eigenes** Budget, ausdrücklich **keine** Restzeit der Primärquelle; bis zu 115 s Zusatzlatenz bewusst akzeptiert | Der Fix wirkt **innerhalb** eines Budgets. Eine Restzeit-Weitergabe **zwischen** Quellen wäre eine stille ADR-Umkehr — verboten ohne neues ADR. |
| **ADR-0038** | s. Zitat unten — nimmt „einzelne in sich unbegrenzt blockierende Schritte" ausdrücklich aus (Verweis #1448) | #2302 ist genau die dort ausgenommene Klasse. ADR-0038 enthält zusätzlich die überholte 120-s-Angabe (K1). |
| **ADR-0018** | Fallback ohne Kaschieren: 4xx nicht ausweichen, jedes Ausweichen markieren | Ein Fristabbruch muss als solcher erkennbar bleiben, nicht als leeres Ergebnis durchgehen. |
| **#1539** (offen) | sequenzielle Verarbeitung als Skalierungsgrenze; PO: Dauer eines Briefing-Laufs unkritisch, Architektur muss skalieren | **Gleiche Schadensform, verschiedene Ursache.** Der übersprungene 15-Minuten-Tick ist bei beiden der Schaden; #2302 = **ein** hängender Abruf, #1539 = die **Summe** vieler Orte. #2302 beseitigt den Schaden also **nicht** — er bleibt bei lebendem #1539 bestehen. |

**ADR-0038 wörtlich** (`docs/adr/0038-zeitgrenze-je-nutzerlauf-unter-aufrufer-wartezeit.md:91-94`):

> „Diese Entscheidung begrenzt ausdrücklich nur die **Summe** der Arbeit eines Laufs, nicht
> einzelne in sich unbegrenzt blockierende Schritte (SMTP ohne Timeout, ungedeckelte
> Warteschleifen, Dateisperren ohne Timeout) — diese Klasse ist gesondert zu behandeln
> (Issue #1448) und wird durch dieses ADR nicht abgedeckt."
| **#1993** (offen, low) | Sichtbarkeit der Drosselung (429) | Benachbart: dort Sichtbarkeit, hier Dauer. Kein Konflikt. |

## Offene Designfragen für `/20-analyse`

**D1 — Geteilter Baustein oder vier Kopien? (die Leitfrage)**

Vorentschieden ist bereits der **Ort**: eine **neue Datei `src/providers/http.py`**, nicht
`base.py`. Begründung: `base.py` trägt Registry und alle Fehlerklassen und importiert
bewusst **weder `httpx` noch `tenacity`** (`base.py:7-16`); sämtliche Provider-Importe
stehen dort lokal in Funktionen (`:281 ff.`), damit ein defekter Provider nur seinen
eigenen Block reißt. Ein HTTP-Baustein in `base.py` zöge `httpx`/`tenacity` in genau das
Modul, das jeder Provider importiert.

Teilbarkeit der Bausteine:

| Baustein | Zeilen (openmeteo) | Einordnung |
|---|---|---|
| `_stop_at_request_deadline` | `:304-313` | **teilbar, wörtlich** — greift nur auf `retry_state.kwargs` zu, kein Modul-Global |
| `_resolve_request_deadline` | `:286-301` | teilbar, **aber** liest `FETCH_DEADLINE_SECONDS` als Modul-Global → Dauer muss parametrisiert werden |
| Kopf-Check + Deckelung (`restzeit`, `min(TIMEOUT, restzeit)`) | `:666-673` | teilbar als Hilfsfunktion; providerspezifisch nur `TIMEOUT`, Providername (`:668`) und Konstantenname im Fehlertext (`:670`) |
| `RETRY_ATTEMPTS` / `RETRY_WAIT_MIN` / `RETRY_WAIT_MAX` | `:110-112` | teilbar — in allen fünf **identisch** (5 / 2 / 60) |
| `_is_retryable_error` | `:272-283` | teilbar **nur nach Angleichung** — Signatur `Exception` statt `BaseException` (dwd `:134`, dwd_eu `:154`, meteofrance `:213`, geosphere `:59`); nur openmeteo hat den `__cause__`-Zweig (`:277-282`) |
| `RETRY_STATUS_CODES` | `:113` | **braucht eine Entscheidung** — divergiert: `{502,503,504}` (openmeteo `:113`, geosphere `:56`) gegen `{500,502,503,504}` (dwd `:64`, dwd_eu `:83`, meteofrance `:86`) |

Nicht teilbar (openmeteo-spezifisch): `REGIONAL_MODELS` (`:118 ff.`), `_candidate_models`
und Endpunkt-Dedup (`:1064-1067`), `FALLBACK_RETRY_ATTEMPTS` (`:107`), Kandidatenschleife
(`:1064-1104`), `_punkt_params` (`:1012-1039`), Cross-Provider-Weiche (`:1105-1133`),
`_log_api_call` (`:615-618`).

Offen bleibt: **Wird `openmeteo.py` auf den Baustein migriert?** Wenn nein, stehen danach
fünf Varianten statt vier — schlechter als heute. Wenn ja, fasst der Fix ausgerechnet die
heute korrekte Quelle im Alarm-Pfad an. Und: **Wie kommt die providereigene Fristdauer
(25/45/60/150/180 s) an einen geteilten Dekorator**, ohne das prozessweit geteilte
`Retrying`-Objekt anzufassen, das die Tests patchen?

#### 🔴 Die harte Randbedingung: der Wert muss LAUFZEIT-spät aufgelöst werden

Der `@retry`-Dekorator wird zur **Import-Zeit** ausgewertet (`openmeteo.py:620-626`). Alle
fünf einschlägigen Tests patchen das Modul-Global zur **Laufzeit** (`:409`, `:413`, `:597`,
`:645`, `:709`).

**Eine Closure über den Wert** (`_make_hook(60.0)` beim Dekorieren) **fröre ihn ein** — die
Patches liefen ins Leere, die Tests würden grün, ohne noch etwas zu bewachen. Das ist das
Ausschlusskriterium, an dem die naheliegendste Bauform scheitert, und es ist genau die
Falle „Test misst die Zusicherung nicht mehr".

Zwei tragfähige Wege, an den providereigenen Wert zu kommen — beide über `retry_state`:

- `retry_state.args[0]` **ist der Provider selbst** (`_request` ist eine gebundene Methode,
  `self` steht im Positionsargument; im `retry_with`-Pfad explizit sichtbar,
  `openmeteo.py:1087`). Ein geteilter Hook könnte
  `getattr(retry_state.args[0], "FETCH_DEADLINE_SECONDS")` lesen: **eine** Funktion für alle
  fünf Dekoratoren, Wert je Provider, Auflösung zur Laufzeit.
- (zweiter Weg vom Agenten angerissen, in `/20-analyse` auszuarbeiten)

**Zusatzkomplikation:** Es ist nicht „ein Wert je Provider", sondern teilweise **zwei
Fristen im selben Modul** — `FETCH_DEADLINE_SECONDS` (dwd `:69` 180,0 · meteofrance `:93`
180,0 · openmeteo `:74` 60,0) gegen `THUNDER_FETCH_DEADLINE_SECONDS` (dwd `:119` 150,0 ·
meteofrance `:114` 45,0 · dwd_eu `:134` 25,0). Ein Unterscheidungsmerkmal auf **Modulebene
reicht nicht**.

#### Was die Vorlagen-Spec verbindlich macht

`docs/specs/modules/fix_1448_s3_telegram_openmeteo.md` (477 Zeilen, Status `draft`,
Approval-Kästchen **ungehakt**):

- Verbindlich ist ausdrücklich nur das **Ergebnis** — Versuchszahl *und* verstrichene Zeit
  beide durch die Restzeit begrenzt —, **nicht die Bauform** (`:190-199`). Wir sind in der
  Wahl des geteilten Bausteins also frei.
- Die Team-Lead-Präzisierung nach der RED-Phase (`:157-176`) verwirft den ursprünglichen
  `deadline_at=None`-Default mit der Begründung: **„eine Absicherung, die man vergessen
  kann einzuschalten, ist im Ernstfall keine."** Der `before`-Hook-Ersatzweg ist damit eine
  **geforderte Eigenschaft**, kein Nebenprodukt — und muss im geteilten Baustein erhalten
  bleiben.
- Die Spec notiert selbst als Nebenbefund, dass `dwd.py` dieselbe Lücke noch hat
  (`:436-440`), und dass die Provider-**Kette** als Ganzes weiterhin kein Budget hat
  (`:428-435`). #2302 ist die Einlösung des ersten Punktes, nicht des zweiten.

#### Schwachstelle der Vorlagen-Tests, die wir nicht erben sollten

Fünf von acht Tests dort messen die Wanduhr. Aber: **Beide AC-6-Tests neutralisieren die
Wartepausen per `wait_none()`** (`:594-595`, `:642-643`) — und schalten damit genau den
Faktor aus, den die Zeitgrenze begrenzen soll. Nur `test_stop_condition_limits_retry_backoff_within_deadline`
(`:673-729`) lässt sie spürbar stehen (`wait_fixed(1.5)`, `:711`).

**Folge für unsere ACs:** Mindestens eine Zusicherung muss den Retry-Backoff **stehen
lassen**, sonst misst sie den Abruf-Timeout und übersieht die Wartepausen — und die machen
in der 390-Sekunden-Rechnung des Tickets den größeren Anteil aus (4 × bis 60 s gegen
5 × 30 s).

**D2 — Bekommt `geosphere.py` ein Budget?**
Dort eines *einzuführen* ist neues Verhalten, nicht Härtung: Es kann Abrufe abbrechen, die
heute langsam, aber erfolgreich durchlaufen — nutzersichtbar als fehlende Wetterdaten.
Entweder mit AC aufnehmen, die sagt, was beim Erreichen passiert (ADR-0018: markiert, nicht
still), oder ausdrücklich vertagen. Die stille Mitte ist das Risiko.
Gewicht: Geosphere ist die **einzige** Quelle ganz ohne Budget und hängt über `at_direct`
am Alarm-Pfad.

**D3 — Der Lauf-Rückfall (K3) fällt aus D1 heraus, ist keine eigene Frage.**
Wird die Frist **durchgereicht** (ein `deadline_at` je Gewitterabruf, wie `:1010` es für
die Kandidatenschleife tut), sind die drei Lauf-Kandidaten automatisch mitgedeckelt.
Wird sie **je `_request` neu hergeleitet** (der `before`-Hook-Ersatzweg), bekommt jeder
Kandidat frische volle Zeit und K3 bleibt offen. Als **Konsequenz von D1** formulieren,
nicht als dritte Option — sonst wird es zweimal und womöglich gegenläufig entschieden.

**D4 — `live`-Marker: entschieden, kein Diskussionspunkt mehr.**
- Der **neue** Wächter trägt **keinen** dieser Marker. Vorlage `test_alert_run_deadline.py`.
  Das ist eine **AC**, kein Nebensatz.
- Wird bei D5 entschieden, `test_dwd_eu_thunder_time_budget.py` **in place zu verschärfen**,
  muss dort der `live`-Marker (Z. 31) **mit entfernt** werden — sonst ist die verschärfte
  Zusicherung genauso unsichtbar wie die alte. Kein Scope-Zuwachs, sondern die Wirksamkeit
  des eigenen Fixes.
- Die **übrige** Marker-Setzung gehört **nicht** in diesen Fix → Test-/Gate-Befund nach
  **#1196**, mit der Messung oben als Beleg.

**D5 — Zusicherungsform der ACs.**
Die neue Zusicherung muss **Obergrenze der tatsächlich verstrichenen Wanduhrzeit** gegen
einen echt hängenden lokalen Server sein — nicht Aufrufzahl, und **nicht** „`timeout=`
wurde durchgereicht" (FORM statt WERT: bewacht den Draht, nicht die Wirkung).
Pflichtbestandteil ist die **Gegenprobe Normalfall** (Muster
`test_send_slot_and_fetch_deadline.py:439`), sonst wäre ein Fix, der alles sofort abbricht,
ebenfalls grün.

Zu entscheiden: bestehenden Zähl-Test **verschärfen oder ersetzen** — nicht daneben stehen
lassen. Dabei ist die dortige Begründung zu entkräften oder zu übernehmen, nicht zu
übergehen: „ein Laufzeit-Test misst die Maschine, nicht die Zeitgrenze". Gegenargument aus
dem Bestand: `test_send_slot_and_fetch_deadline.py` und `test_thunder_budget_and_failsoft.py`
messen sehr wohl Wanduhrzeit, mit großzügigem Sicherheitsabstand
(`dauer < (_ANTWORTZEIT_S + _ZEITGRENZE_S)/2`).

**D6 — Wird der Tröpfel-Fall mitgenommen?**
Die einzige wirklich unbegrenzte Lücke (s. Request Summary, selbst gemessen: Faktor 12,2)
wird vom kopierten Muster **nicht** geschlossen. Sie bräuchte eine Obergrenze auf die
**Gesamtdauer** einer Antwort — httpx bietet dafür keinen eingebauten Parameter, es wäre
ein eigenes Mittel (z. B. Streaming mit Fristprüfung je Chunk, oder ein Wachhund-Thread).
Drei Wege: (a) mitnehmen, (b) ausdrücklich als Grenze in die Spec schreiben und
vertagen (eigenes Ticket), (c) verschweigen — **(c) scheidet aus**.
Gegen (a) spricht, dass es den Fix verdoppelt und eine Bauform braucht, für die es im Haus
kein Vorbild gibt. Für (b) spricht, dass echte Wetterdienste eher schweigen als tröpfeln.

**D7 — Deckt der Baustein auch künftige Nutzer?**
`radar_service.py` hat heute keinen Retry und ist deshalb unkritisch. Soll der Baustein so
geschnitten sein, dass ein dort später ergänzter Retry die Lücke nicht erneut öffnet?

## Risks & Considerations

- **Nie beobachtet.** Braucht eine Gegenstelle, die annimmt und schweigt. Der einzige real
  aufgetretene Fehler (401 bei Météo-France) kann es **nachweislich nicht** auslösen: 401
  steht in keinem `_is_retryable_error` und kommt sofort zurück. Ein Versuch, die
  Produktionsprotokolle gegenzulesen, ergab keine Treffer — aber die Leserechte des Laufs
  sind **nicht abgesichert**, die Messung zählt nicht als Beleg.
- **Zu scharfe Grenzen schneiden echte Daten weg.** Gewitter ist eine Alarm-Eingangsgröße;
  ein zu knappes Budget erzeugt stille Lücken statt langer Läufe.
- **LoC-Limit.** Vier Provider plus möglicher geteilter Baustein — 250 Zeilen reichen
  voraussichtlich nicht. Override erst setzen, wenn das Limit real blockt.
- **`e2e_scope`.** Reiner Python-Backend-Change, kein Frontend — per `set-field` richten,
  er bleibt sonst auf dem Spec-Commit-Wert.
- **Die Nachweis-Tests binden echte lokale Sockets.** Literal benennen, nie unter
  `--disable-socket` ohne `--allow-hosts=127.0.0.1` laufen lassen.
