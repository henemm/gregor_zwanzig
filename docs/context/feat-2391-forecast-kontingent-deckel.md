# Context: feat-2391-forecast-kontingent-deckel

**Issue:** #2391 (Scheibe S3 aus #2150, Epic #2138 Multi-User)
**Erstellt:** 2026-09-21

## Request Summary

Der Go-Endpunkt `GET /api/forecast` ruft Open-Meteo direkt auf und umgeht dabei das
Tageskontingent-Gate, das im Python-Core sitzt. Gesucht ist, dass Abrufe über diesen Pfad im
selben Kontingent landen wie alle anderen — mit der echten Nutzerkennung — und dass ein
einzelner Nutzer damit nicht die Kontingente der anderen aufbrauchen kann.

## Der Befund, gemessen am 2026-09-21

### Zwei ungegatete Forecast-Endpunkte, nicht einer

| Pfad | Gate? | Nutzerkennung? | Antwort-Cache? |
|---|---|---|---|
| Go `GET /api/forecast` (`internal/router/router.go:168`) | nein | nein | nein |
| Python `GET /forecast` (`api/routers/forecast.py:42`) | nein | nein | nein |

- Der Go-Weg: `handler/forecast.go:11` → `provider/openmeteo/provider.go:328` `FetchForecast`
  → `:53` `doRequest`. Der einzige Cache dort ist `cache.go:16` `AvailabilityCache` — er merkt
  sich, *welche Modelle* für eine Koordinate liefern (TTL 7 Tage), nicht die Vorhersage.
- Der Python-Weg: `api/routers/forecast.py:42` `get_forecast` baut sich eine frische
  `ForecastService(OpenMeteoProvider())` und ruft `get_forecast()` — ohne `user_id`, ohne
  `ForecastBudgetGate`.

**Folge für die Lösungswahl:** ein reiner Proxy Go → Python-Core löst nichts, weil das
Proxy-Ziel selbst ungegatet ist. Wer diesen Weg gehen will, muss den Python-Router zuerst ans
Gate hängen — inklusive Nutzerkennung, die der Router heute gar nicht entgegennimmt.

**Nicht von außen erreichbar** ist der Python-Router allerdings: `localhost:8000`
(`api/main.py:5`) plus gemeinsames Geheimnis seit #2142 (`api/main.py:148` `enforce_core_auth`,
fail-closed). Er ist also kein Umgehungsweg um einen Deckel auf der Go-Seite, sondern nur ein
zweiter Ort desselben Musters.

### Ein Aufruf kostet mehrere Kontingent-Einheiten — mit offener Obergrenze

`FetchForecast` löst aus: `doRequest` (Forecast) + `fetchUVData` (Air-Quality, `:348`) + bei
fehlenden Metriken `tryFallback` mit einem zweiten Modell (`:359`). **Jede** dieser Anfragen
läuft zusätzlich durch die Wiederholschleife in `doRequest` (`:55` `for attempt := 0; attempt <
p.cfg.Retries`): bei Netzwerkfehler oder HTTP 502/503/504 wird mit exponentieller Wartezeit
erneut gefeuert, und `logAPICall` verbucht **jeden Versuch** als echte Last (`:78`, Kommentar
"bildet die echte Last pro Retry-Versuch ab"). Ein einzelner `/api/forecast`-Aufruf kostet damit
im schlechten Fall `Retries × (1 Forecast + 1 UV + ggf. 1 Fallback)` — nicht 2–3. Wie viele
Einheiten eine Buchung zählen soll, ist eine offene Frage der Analyse.

### Es gibt bereits einen Go-seitigen Abrufzähler — mit gegenteiliger Entwurfsentscheidung

`internal/provider/openmeteo/calllog.go:11-14` (Issue #338): jeder ausgehende Abruf des
Go-Providers, **Retry-Versuche eingeschlossen**, hängt eine JSONL-Zeile an
`<GZ_DATA_DIR>/diagnostics/openmeteo_calls_go.jsonl`. Der Kommentar nennt den Grund für die
getrennte Datei ausdrücklich: *"Eigene Datei (getrennt von Python), um
Cross-Language-Schreibkonflikte zu vermeiden."* Das ist reine Beobachtung, fail-soft, ohne jede
Drosselwirkung.

Für dieses Ticket ist das doppelt wichtig: die Zahlen für eine Buchung **liegen auf der
Go-Seite bereits vor**, und die Entscheidung "Go schreibt nicht in Python-Dateien" ist schon
einmal bewusst getroffen worden. Wer sie umkehren will, muss das begründen.

### Kein Rate-Limit je Konto

`internal/router/router.go:40` legt `AuthMiddleware` global — der Endpunkt ist angemeldeten
Nutzern vorbehalten, aber jeder darf unbegrenzt oft rufen.

### Eingegrenzt

`deps.WeatherProvider` hat genau **einen** Konsumenten (`router.go:168` →
`handler/forecast.go:11`). Der Scheduler und die Briefing-Pfade laufen nicht darüber.

## Bindende Vorentscheidung: ADR-0075 (vom 2026-09-21, aus #2387)

`docs/adr/0075-forecast-budget-fairness-je-nutzer.md` — für dieses Ticket **bindend**:

1. **Kein zweites Budget je Konto.** Ein Zähler je Nutzer mit je vollem `DAILY_BUDGET` ist
   ausdrücklich verworfen (N × Budget hebt den Kontoschutz auf). Der Nutzer-Topf ist ein reiner
   **Verteilungsschlüssel**. ⇒ Die Formulierung „Deckel je Konto" aus dem Issue-Titel ist als
   *eigenes* Kontingent zu verstehen **falsch** — richtig ist: der Go-Pfad muss durch dieselbe
   dreistufige Entscheidung laufen wie alles andere.
2. **Dreistufiges `allow(priority)`:** Stufe 0 (unter Schwelle: durchlassen) → Stufe 2 (≥ 100 %:
   harter Kontoschutz, steht **vor** Stufe 1) → Stufe 1 (über fairem Anteil `DAILY_BUDGET/N`:
   drosseln). `user_briefing` bleibt in allen Stufen ungedrosselt.
3. **Fail-open je Nutzer:** unlesbarer Topf oder Lock-Timeout gilt als „nicht überschritten",
   nie als Drosselungsgrund — sichtbar als `WARNING` des Gate-Loggers.
4. **`user_id` ist Pflichtparameter ohne Default**, `None` ist die geschriebene Entscheidung
   „unattributiert" und wird in Stufe 1 **gedrosselt, nie befreit**. Kein `"default"`-Rückfall
   (ADR-0003).
5. **Der Go-Status-Endpunkt bleibt auf Aggregate beschränkt** — `/api/scheduler/status` ist ohne
   Anmeldung erreichbar, Nutzerkennungen dürfen dort nie erscheinen. `forecastBudgetFile`
   deklariert `active_users` bewusst nicht; `forecast_budget_user_privacy_test.go` friert das ein.
6. **`DAILY_BUDGET`, `POLLING_THRESHOLD`, `BRIEFING_ONLY_THRESHOLD` bleiben wörtlich an ihrer
   Stelle** in `forecast_budget.py` — `TestForecastBudgetConstantsMatchPython`
   (`internal/scheduler/forecast_budget_health_test.go`) liest den Python-Quelltext zur Laufzeit
   und wird rot, sobald eine Konstante wandert.

**Ebenfalls aus ADR-0075, Abschnitt Konsequenzen:** drei Python-Pfade (`comparison_engine.py`,
`services/forecast.py`, `trip_forecast.py`) umgehen Cache **und** Gate bis heute vollständig —
derselbe Scope-Schnitt wie in `fix_1329_forecast_cache_budget.md`. `services/forecast.py` ist
genau der Pfad, den der Python-Router `/forecast` benutzt. Ob dieses Ticket den Schnitt
verschiebt, ist eine Scope-Frage für die Analyse.

## Risiken & Erwägungen

- **Schreibweg auf `active_users` ist sicherheitskritisch** (ADR-0075, Konsequenzen): fällt er
  aus, bleibt `N = 0`, der faire Anteil das ganze Tagesbudget, und Stufe 1 feuert nie. Ein
  zweiter Schreiber (Go) auf dieselbe Datei erhöht genau dieses Risiko. Eine Positivkontrolle
  auf den Schreibweg ist Pflicht, nicht Kür.
- **Zwei Prozesse auf einer Zählerdatei.** Python schreibt Read-Modify-Write unter `fcntl`
  (`services/file_lock.py`). Ein Go-seitiger Schreiber müsste dieselbe Sperrsemantik treffen —
  sonst gehen Buchungen verloren oder es entstehen Wartezeiten im HTTP-Pfad.
- **Datenschutz:** jede Lösung, die den Verbrauch je Nutzer nach außen sichtbar macht, kollidiert
  mit ADR-0075 Punkt 5.
- **Fail-open vs. fail-closed sauber trennen:** Zähler nicht lesbar ⇒ durchlassen; Zähler lesbar
  und über der Grenze ⇒ drosseln. Ein Deckel, der auch im zweiten Fall durchlässt, ist Zierrat.

## Offene Fragen für `/20-analyse`

1. **Wo entsteht die Buchung?** Drei Wege stehen im Raum, und die Wahl ist die ADR-pflichtige
   Entscheidung dieses Tickets:
   a) Go schreibt selbst in die Python-Zählerdatei — Präzedenz nur **lesend**
      (`forecast_budget_health.go`), und `calllog.go` hat die Trennung der Schreibwege
      ausdrücklich andersherum entschieden;
   b) der Go-Handler fragt den Python-Core vor dem Abruf (neuer interner Endpunkt hinter dem
      gemeinsamen Geheimnis), der Core bucht;
   c) der Go-Handler proxyt den ganzen Abruf auf den Python-Core, der dann gaten **und** die
      Kennung entgegennehmen müsste — heute tut der Router `/forecast` weder das eine noch das
      andere.
2. **Welche Priorität** trägt ein interaktiver `/api/forecast`-Abruf im dreistufigen Modell?
   `polling` (ab 80 % gedrosselt) oder etwas Eigenes? `user_briefing` scheidet aus — das ist der
   Versandpfad, nicht die Ad-hoc-Abfrage.
3. **Eine Buchung oder 2–3?** Siehe oben.
4. **Scope — beantwortet, kein offener Punkt mehr:** der Python-Router `/forecast` bleibt außen
   vor. Er ist von außen nicht erreichbar: der Core lauscht auf `localhost:8000` (`api/main.py:5`)
   und weist seit #2142 jede Anfrage ohne gemeinsames Geheimnis ab (`api/main.py:148`
   `enforce_core_auth`, fail-closed mit 503, wenn gar kein Geheimnis gesetzt ist). Der Go-Router
   proxyt `/forecast` auch nicht (gemessen: keine solche Route). Ein Deckel auf dem Go-Pfad ist
   damit nicht in einem Sprung umgehbar.

## Bestehende Muster und Flächen (recherchiert, am Code gegengeprüft)

### Weitere bindende ADRs

| ADR | Kernaussage | Bedeutung hier |
|---|---|---|
| **ADR-0015** (Dual-Stack, teilweise abgelöst durch ADR-0062) | Regel 1: *„Neue Domain-/Wetter-/Rendering-Logik entsteht im Python-Core, nicht im Go-Backend. Go-Handler bleiben API-Klebstoff + Persistenz."* Die Zuständigkeitstabelle (`:31`) nennt **„Rate-Limiting"** aber ausdrücklich als Go-Aufgabe. | **Genau die Spannung dieses Tickets:** die Kontingent-Entscheidung ist Wetter-Domäne (Python), die Drosselung eines HTTP-Endpunkts ist API-Belang (Go). Die Analyse muss diese Grenze begründet ziehen. |
| **ADR-0062** | Go und Python teilen `GZ_CORE_SHARED_SECRET`, Go sendet `X-GZ-Core-Auth`, Python erzwingt es fail-closed auf jedem Endpunkt außer `/health`. | Go **kann** den Core fragen, statt nur Dateien zu lesen — der Kanal dafür existiert und ist abgesichert. |
| **ADR-0070** | Wartebudget je Nutzeraufruf im Go-Scheduler (Alarm 300 s, Briefing 600 s); Go wartet begrenzt, Python arbeitet unverändert zu Ende. | Nächstliegende Go-Präzedenz für „Grenze je Nutzer" — aber ein **Zeit**budget, kein Aufruf-Kontingent. Nicht eins zu eins übertragbar. |

### Anti-Präzedenz: `premium_sms_ratelimit.go`

Sieht nach dem passenden Muster aus, ist aber das Gegenteil: `internal/handler/premium_sms_ratelimit.go:3-8`
begründet ausdrücklich **global statt je Konto** — *„nicht je Konto (sonst koennte ein Angreifer
gezielt einzelne Konten aussperren)"*. Zähler im Arbeitsspeicher, kein Tagesreset, kein
HTTP-Status. Als Vorlage ungeeignet; als Mahnung nützlich: ein Deckel je Konto braucht eine
Begründung, warum Aussperren hier kein Angriffsziel ist (hier: der Deckel schützt ein
Kontingent, er bewacht kein Geheimnis).

### Wie Go die Zählerdatei heute liest

`internal/scheduler/forecast_budget_health.go:53-116` — `os.ReadFile`, **ohne Sperre**, fail-soft
bei kaputtem JSON. Die Begründung steht inline (`:68-74`): Python schreibt atomar
(`mkstemp` + `os.replace`), Go sieht nie eine Halbschrift. `forecastBudgetFile` (`:41-46`)
deklariert nur vier Felder; alles andere fällt beim Unmarshal weg — das ist der Mechanismus,
auf dem ADR-0075 Punkt 5 beruht.

**Lesen ist also gelöst. Schreiben ist die offene Frage** — dafür gibt es auf der Go-Seite
bisher keine Präzedenz, und `calllog.go` hat sie bewusst vermieden.

### Nutzerkennung im Handler

`internal/middleware/auth.go:106-109` — `UserIDFromContext(ctx) string` liefert bei fehlender
Session den **leeren String**, nicht einen Fehler. Handler müssen selbst prüfen; das gelebte
Muster ist `internal/handler/premium_sms_link_code.go:33-40`:

```go
userID := middleware.UserIDFromContext(r.Context())
if userID == "" { http.Error(w, "unauthorized", http.StatusUnauthorized); return }
```

Das ist hier **Pflicht**, nicht Kür: ADR-0075 Punkt 4 verlangt eine echte Kennung; ein leerer
String würde in Python als ungültige Kennung einen `ValueError` auslösen (`forecast_budget.py`,
`VALID_USER_ID_RE`), im schlechteren Fall still auf ein fremdes Konto buchen.

### Der Endpunkt ist Altbestand

- Kein Aufruf aus `frontend/src/` — weder fest noch über einen API-Wrapper.
- `frontend/e2e/issue-294-home-kachel.spec.ts:116` prüft sogar **die Abwesenheit**:
  *„AC-7: kein /api/forecast- und kein /api/scheduler-API-Call"*.
- Einziger realer Nutzer: `scripts/refresh-openmeteo-fixtures.sh` (Regeneration von Testdaten).

**Damit entsteht eine vierte Lösungsoption für die Analyse:** den Endpunkt nicht drosseln,
sondern **zurückbauen oder auf den Fixture-/Entwicklungsfall beschränken**. Ein toter Endpunkt,
der ungezählt Kontingent verbrennen kann, ist möglicherweise gar nicht deckelnswert, sondern
überflüssig. Das ist zugleich die einzige Option, die den Schreibkonflikt zwischen den Sprachen
vollständig vermeidet — und die einzige, die die Frage aufwirft, ob `refresh-openmeteo-fixtures.sh`
einen anderen Weg bekommt.

### Testfläche

| Test | Was er bewacht |
|---|---|
| `internal/handler/forecast_test.go:16-102` | Nur Eingabevalidierung (400 bei fehlendem/ungültigem `lat`) und ein Live-Abruf gegen die echte API. **Keine** Auth-, Kontingent- oder Drossel-Prüfung. |
| `internal/scheduler/forecast_budget_health_test.go:256-286` | `TestForecastBudgetConstantsMatchPython` liest `forecast_budget.py` zur Laufzeit — wandert eine Konstante, wird der Test rot (ADR-0075 Punkt 6). |
| `internal/scheduler/forecast_budget_user_privacy_test.go:23-81` | Nutzerkennungen dürfen nicht über `/api/scheduler/status` nach außen (ADR-0075 Punkt 5). |
| `tests/unit/test_forecast_budget_gate.py` · `tests/unit/test_forecast_budget_fairness_je_nutzer.py` | Das dreistufige Modell und der faire Anteil auf der Python-Seite, inkl. Zwei-Nutzer-Szenario. |

**Lücke:** kein einziger Test bewacht heute, dass ein Abruf über `/api/forecast` gebucht wird —
genau deshalb konnte das Loch entstehen.

---

# Analysis (Phase 2, 2026-09-21)

## Type

**Bug** (Label `bug`, `priority:high`) — ein Schutzmechanismus, der laut ADR-0075 für alle
Abrufe gilt, greift auf einem Pfad nicht. Der Fix ist Verdrahtung, kein neues Feature.

## Vorab geklärt: das Gate ist nicht vakuum

Gegenprobe zur Frage, ob der globale Zähler überhaupt jemals hochzählt (sonst wäre das Ticket
ein anderes): `record_call()` hat drei echte Aufrufer im Produktivpfad —
`src/services/segment_weather.py:204` (Briefing/Etappen-Wetter),
`src/services/radar_service.py:905` (Radar/Nowcast),
`src/services/official_alerts/meteoalarm.py:740`. Die Buchung sitzt also in der
**Service-Schicht**, nicht im Provider — genau deshalb ist jeder Pfad, der den Provider direkt
anspricht (Go-Handler, `services/forecast.py`, `comparison_engine.py`, `trip_forecast.py`),
ungezählt. Das Loch ist strukturell, nicht ein vergessener Aufruf.

## Die vier Lösungswege — drei sind durch Messung erledigt

### (c) Proxy Go → Python-Core: **ausgeschlossen, Antwortformat bricht**

Go liefert `model.Timeseries` mit dem Feld `timezone` (`internal/model/forecast.go:92-96`);
Python liefert `NormalizedTimeseries` mit **nur** `meta` + `data` (`src/app/models.py:252-255`)
und entfernt in `_clean_dict` zusätzlich alle `None`-Werte
(`api/routers/forecast.py:24-38`). Die beiden Formate sind nicht austauschbar.

Entscheidend ist, wer daran hängt: `scripts/refresh-openmeteo-fixtures.sh:30` schreibt die
Antwort von `/api/forecast` **wörtlich** in `fixtures/openmeteo/<ort>.json`, und
`internal/provider/fixture/provider.go:43` liest genau diese Dateien als Go-`Timeseries`. Ein
Proxy zerstört damit still die Fixture-Erzeugung und, beim nächsten Refresh, den
Offline-Testmodus. Mitreparieren hieße: Fixture-Format, Fixture-Provider und Refresh-Script in
derselben Scheibe — das sprengt das LoC-Limit.

Zusatzgrund: der Proxy-Zielpfad (`services/forecast.py`) ist selbst ungegatet, der Fix müsste
also ohnehin auf beiden Seiten landen.

### (a) Go schreibt selbst in die Zählerdatei: **ausgeschlossen, drei Entscheidungen dagegen**

- **ADR-0015 Regel 1** — Domänenlogik entsteht im Python-Core, Go bleibt API-Klebstoff.
- **ADR-0075 Punkt 2** — `allow(priority)` ist *die* dreistufige Entscheidungsprozedur. Ein
  Go-Nachbau wäre ein zweites Exemplar derselben Regel, das auseinanderlaufen kann; Punkt 6
  friert die Konstanten ausdrücklich an ihrem Python-Ort ein.
- **`internal/provider/openmeteo/calllog.go:11-14`** — die Trennung der Schreibwege zwischen
  den Sprachen ist bereits bewusst *andersherum* entschieden ("eigene Datei, um
  Cross-Language-Schreibkonflikte zu vermeiden"). Go müsste zusätzlich die `fcntl`-Semantik aus
  `services/file_lock.py` nachbauen — im HTTP-Pfad, mit Sperrwartezeit.
- Risikoverstärkung: ein zweiter Schreiber auf `active_users` ist genau der Weg, über den
  laut ADR-0075 (Konsequenzen) `N = 0` und damit ein wirkungsloses Stufe-1 entsteht.

### (d) Endpunkt zurückbauen: **abgelehnt, ausdrücklich und mit Begründung**

Der Gedanke ist naheliegend (kein Aufruf aus `frontend/src/`, gemessen), aber:

- `docs/specs/modules/sveltekit_weather_table.md:61,85` ist eine **aktive**, nicht archivierte
  Spec, die den Endpunkt als Client-Weg vorsieht. Ein Rückbau widerspricht einer geltenden Spec
  und wäre selbst freigabepflichtig.
- Der Fixture-Weg hängt am exakten Go-Antwortformat (siehe oben) — Rückbau verlangt einen
  Ersatzweg für `refresh-openmeteo-fixtures.sh` in derselben Scheibe.
- Ein Rückbau löst die im Ticket verlangte **Buchung** nicht, er entfernt nur einen Verbraucher.

Der Nebenbefund „kein Produktiv-Aufrufer" ist als Zeile für #1199 vorgesehen, nicht als
Handlung dieses Tickets.

### (b) Go fragt den Core vor dem Abruf: **Empfehlung**

Der einzige Weg, der den Go-Pfad durch **dieselbe** `allow(priority)`-Entscheidung schickt,
ohne Antwortformat, Schreibwege oder Konstanten zu bewegen:

- Ein Schreiber auf der Zählerdatei bleibt Python (unter `fcntl`) — `calllog.go`-Entscheidung
  und ADR-0075 Konsequenzen unberührt.
- Der Kanal existiert und ist abgesichert: `internal/coreauth/transport.go:27`
  (`X-GZ-Core-Auth`, ADR-0062), `api/main.py:148` erzwingt ihn fail-closed.
- Das Muster für die Nutzerkennung existiert samt Spoofing-Schutz:
  `internal/handler/proxy.go:151-163` `appendUserID` (entfernt eine vom Client mitgeschickte
  `user_id` und setzt die authentifizierte). `api/routers/internal.py:29` zeigt die
  Gegenseite (`user_id: str = Query(...)`).
- `/api/_internal/*` ist der etablierte Ort für core-interne Endpunkte
  (`internal/router/router.go:198-204`).
- ADR-0015 nennt „Rate-Limiting" als Go-Aufgabe, ADR-0075 die Kontingent-Entscheidung als
  Python-Domäne. (b) zieht die Grenze genau dort: **Go entscheidet über die HTTP-Antwort
  (429), Python entscheidet über das Kontingent.**

## Die drei offenen Fragen aus Phase 1 — entschieden

### 1. Wo entsteht die Buchung? → Weg (b), ein Roundtrip („reserve")

Neuer interner Endpunkt im Python-Core, der **prüfen und buchen in einem Aufruf** erledigt:

```
POST /api/_internal/forecast-budget/reserve?user_id=<auth>&priority=polling&units=2
  → 200 {"allowed": true}   (gebucht)
  → 200 {"allowed": false, "retry_after_s": <bis UTC-Mitternacht>}   (nicht gebucht)
```

**Warum ein Aufruf statt „allow vorher, record mit echter Zahl nachher":** die echte Zahl
kennt Go erst nach dem Abruf, und sie ist am Handler nicht abgreifbar —
`provider.WeatherProvider.FetchForecast` gibt keine Call-Anzahl zurück, und die
request-genaue Attribution über Context-Durchreichung ist in
`docs/specs/_archive/modules/issue_338_go_geosphere_counter.md:167` ausdrücklich als
Folge-Arbeit ausgewiesen. Eine Nachbuchung erzwänge also eine Änderung der Provider-Schnittstelle
— deutlich mehr Fläche als der Gewinn. Zweiter Vorteil der Vorbuchung: sie ist atomar. Fällt der
Go-Prozess zwischen Abruf und Nachbuchung aus, wäre der Abruf ungezählt — genau das Loch, das
dieses Ticket schließt.

### 2. Priorität → `polling`

Keine neue Priorität und keine neue Konstante: `TestForecastBudgetConstantsMatchPython`
(`internal/scheduler/forecast_budget_health_test.go:256-286`) spiegelt die Python-Konstanten
und ist nach ADR-0075 Punkt 6 eingefrorener Boden. Sachlich passt `polling` genau: ein
interaktiver Ad-hoc-Abruf ist der Fall, für den die 80-%-Schwelle gebaut wurde.
`user_briefing` scheidet aus (Versandpfad, nie gedrosselt), `alert_check` ebenso.

### 3. Eine Buchung oder mehrere? → **2 Einheiten**, mit dokumentierter Näherung

Gemessen an `internal/provider/openmeteo/provider.go:328-360`: `doRequest` (Forecast) und
`fetchUVData` (`:348`) laufen **unbedingt**, `tryFallback` (`:359`) nur bei fehlenden Metriken,
und jede dieser Anfragen kann die Wiederholschleife durchlaufen (`:55`). 2 ist damit die
garantierte Untergrenze des Regelfalls — ehrlicher als 1 und nicht spekulativ wie ein
Aufschlag für Retries. Die Unterbuchung im Fehlerfall wird in der Spec als bewusste Grenze
benannt; die echten Zahlen bleiben über `calllog.go` nachmessbar.

Zusätzlich bucht der Endpunkt `record_cache_miss()` einmal je Anfrage — auf dem Go-Pfad gibt es
keinen Antwort-Cache, jeder Abruf ist faktisch ein Miss. Ohne das lügt die Cache-Hit-Quote in
`/api/scheduler/status` nach oben.

## Verhalten an der Grenze (AC-Fläche 3)

| Lage | Antwort | Begründung |
|---|---|---|
| Keine Session (`UserIDFromContext == ""`) | `401` | Muster `internal/handler/premium_sms_link_code.go:33-40`. Pflicht: ADR-0075 Punkt 4 verlangt eine echte Kennung; ein leerer String würde im Gate-Konstruktor `ValueError` auslösen. Kein `"default"`-Rückfall (ADR-0003). |
| Core nicht erreichbar / Timeout / Nicht-200 | **durchlassen** (fail-open) + `WARNING`-Log | ADR-0075 Punkt 3: ein kaputter Zähler darf nie einen Abruf blockieren. |
| Core antwortet `allowed: false` | `429` + `Retry-After` | fail-closed. Ein Deckel, der auch hier durchlässt, ist Zierrat. |
| In keinem Fall | stilles Leerergebnis | — |

`Retry-After` = Sekunden bis zum nächsten UTC-Mitternacht; der Zähler wird an der UTC-Tagesgrenze
zurückgesetzt (`ForecastBudgetGate._today_utc`), jeder kürzere Wert wäre eine Lüge.

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `internal/handler/forecast.go` | MODIFY | Auth-Prüfung (401 ohne Session), `reserve`-Anfrage an den Core vor dem Abruf, 429 + `Retry-After` bei Ablehnung, fail-open bei unerreichbarem Core |
| `internal/router/router.go` | MODIFY | `ForecastHandler` bekommt `deps.Config.PythonCoreURL` (eine Zeile) |
| `api/routers/internal.py` | MODIFY | Neuer Endpunkt `POST /api/_internal/forecast-budget/reserve` — `ForecastBudgetGate(user_id)` → `allow(priority)` → bei `True`: `record_cache_miss()` + `record_call()` × units |
| `internal/handler/forecast_test.go` | MODIFY | Zwei-Nutzer-Test, Ankunfts-Test für `user_id`/`priority`/`units` am Core, fail-open-Test, 401-Test |
| `tests/tdd/test_internal_forecast_budget_reserve.py` | CREATE | Buchungsweg gegen echte Zählerdatei (tmp `data_root`): Nutzer A über fairem Anteil → `allowed: false`, Nutzer B → `allowed: true` |
| `docs/adr/0076-*.md` | CREATE | Grenzziehung Go↔Python für Kontingent-Entscheidungen (s. u.) |
| `docs/specs/modules/forecast_go_pfad_kontingent.md` | CREATE | Spec mit ACs (Phase 3) |
| `docs/adr/README.md` | MODIFY | Index-Eintrag (erzwingt `tests/test_adr_index_drift.py`) |

## Scope Assessment

- Produktive Dateien: 3 (+2 Doku, +2 Test)
- Geschätzte LoC produktiv: **~100** (Go-Handler ~55, Router 1, Python-Endpunkt ~35) — unter dem
  Limit von 250, kein Override nötig
- Risiko: **MITTEL**

Risikobegründung: kein Persistenz-Schema-Wechsel, kein Antwortformat-Wechsel, keine Konstante
wandert. Neu ist ein RPC im HTTP-Pfad (Latenz eines lokalen Aufrufs, plus Sperrwartezeit des
Python-Schreibers) und ein zweiter Buchungsweg auf denselben Zähler — dieser aber **im selben
Prozess** wie der bestehende, also unter derselben `fcntl`-Sperre.

## ADR-Pflicht

Ja. Die Entscheidung berührt eine Entscheidungsfläche (Architekturgrenze Go↔Python) und löst
die Spannung, die Phase 1 benannt hat: ADR-0015 nennt Rate-Limiting als Go-Aufgabe, ADR-0075
die Kontingent-Logik als Python-Domäne. **ADR-0076** schreibt fest: die Kontingent-*Entscheidung*
bleibt ausschließlich in `ForecastBudgetGate` (Python, ein Schreiber, `fcntl`); Go fragt sie über
`/api/_internal/*` hinter `X-GZ-Core-Auth` ab und übersetzt sie in einen HTTP-Status. Kein
Go-seitiger Schreiber auf `forecast_budget.json`, kein Nachbau von `allow()` in Go. Ergänzt
ADR-0075, löst es nicht ab.

## Test-Zuschnitt und die Fallen darin

**Der Zwei-Nutzer-Test liegt auf beiden Seiten, und das muss sichtbar bleiben:**

- Go (`httptest`-Core-Stub): beweist, dass der Handler die Entscheidung *durchverdrahtet* —
  Nutzer A erhält `429`, Nutzer B `200`. Kein Mock-Theater (echter HTTP-Server), aber allein
  beweist er nichts über das Kontingent.
- Python (neuer Test gegen echte Zählerdatei in `tmp_path`): beweist die Buchung und den fairen
  Anteil. Die Python-Hälfte des dreistufigen Modells ist bereits durch
  `tests/unit/test_forecast_budget_fairness_je_nutzer.py` abgedeckt.

**Fallen, die im RED-Entwurf berücksichtigt sein müssen:**

1. **`allow()` lässt unbekannte Prioritäten immer durch** (`forecast_budget.py:133-134`,
   fail-open). Schickt Go einen Tippfehler, einen leeren oder gar keinen `priority`-Wert, wird
   **nie** gedrosselt — und ein Go-Test, der nur die *Antwort* eines Stubs prüft, bleibt grün,
   ebenso jeder bestehende Python-Gate-Test. Mindestens ein Test muss zusichern, dass
   `priority=polling`, die echte `user_id` und `units` **am Core ankommen** (Stub liest die
   Query und prüft die Werte), nicht nur dass der Handler ein vorgegebenes Urteil befolgt.
   (Muster: `reference_fixture_legt_das_feld_selbst…`, `reference_mutation_im_falschen_kontext…`)
2. **Positivkontrolle auf den Schreibweg** ist Pflicht (ADR-0075, Konsequenzen): ein Test muss
   das Produkt den Zähler *selbst* schreiben lassen und danach `calls` **und** `active_users`
   in der Datei nachlesen. Eine Fixture, die die Felder selbst anlegt, macht die Zusicherung
   vakuum-grün.
3. **Fail-open muss geprüft sein** — unerreichbarer Core ⇒ `200` mit Vorhersage. Ohne diesen
   Test öffnet sich das Loch still wieder, sobald der Core steht.
4. **Bestandstest nicht brechen:** `internal/handler/forecast_test.go:16-102` prüft heute
   Eingabevalidierung ohne Auth-Kontext. Mit der neuen 401-Prüfung laufen diese Fälle in 401
   statt 400 — die Reihenfolge (Auth vor Parametervalidierung, oder umgekehrt) ist eine
   AC-Frage für Phase 3, nicht eine stille Anpassung des Alttests.

## Dependencies

- `ADR-0075` (bindend, alle 6 Punkte), `ADR-0015` Regel 1 + Zuständigkeitstabelle, `ADR-0062`
  (`GZ_CORE_SHARED_SECRET`/`X-GZ-Core-Auth`), `ADR-0003` (Mandantentrennung)
- Bestehende Bausteine, die wiederverwendet werden: `appendUserID`
  (`internal/handler/proxy.go:151`), `internal/coreauth/transport.go`,
  `api/routers/internal.py` als Ablageort, `middleware.UserIDFromContext`
- Kein Frontend- und kein Schema-Bezug — `e2e_scope` dieser Scheibe ist **full-stack (Go +
  Python), kein Frontend**

## Open Questions

Keine für den PO. Alle drei technischen Fragen aus Phase 1 sind oben entschieden und begründet.
Für Phase 3 offen und dort als AC zu formulieren:

- [ ] Reihenfolge im Handler: Auth-Prüfung (401) vor oder nach der Parametervalidierung (400)?
- [ ] Antwortkörper des 429 — Fehlerobjekt im Stil der bestehenden `{"error": …, "detail": …}`?

## Nebenbefunde (nicht dieses Ticket)

- `/api/forecast` hat keinen Produktiv-Aufrufer aus `frontend/src/`; einziger echter Nutzer ist
  `scripts/refresh-openmeteo-fixtures.sh`. → Zeile für #1199 (Nutzen des Endpunkts prüfen),
  nicht Gegenstand dieses Fixes.
- Der Python-Router `GET /forecast` (`api/routers/forecast.py:42`) bleibt ungegatet — von außen
  nicht erreichbar (localhost + `enforce_core_auth` fail-closed), also kein Umgehungsweg.
  Derselbe Scope-Schnitt wie in `fix_1329_forecast_cache_budget.md:414-419`
  (`comparison_engine.py`, `services/forecast.py`, `trip_forecast.py`).

## Nachtrag aus der Gegenlese — gehört zu „Open Questions" (Phase-3-AC-Arbeit)

Zwei Punkte, die die Liste oben ergänzen. Beide sind keine Analyse-Lücken, sondern
AC-Entscheidungen, die in Phase 3 hingeschrieben werden müssen — sonst findet sie der Adversary:

- [ ] **Abgelehnte `reserve` darf NICHT buchen — und das braucht eine eigene AC.** Heute stehen
  `allow()` und `record_call()` im Bestand als zwei getrennte Anweisungen nebeneinander
  (`segment_weather.py:203-204`); der neue Endpunkt verschmilzt sie hinter *einem* HTTP-Aufruf.
  Ein falscher Zweig ist von außen unsichtbar: ein `reserve`, das trotz Ablehnung bucht, liefert
  weiterhin `allowed: false`, und sowohl der Go-Test als auch ein Python-Test, der nur das
  Urteil prüft, bleiben grün. Die AC muss den Zählerstand **vor und nach** einer abgelehnten
  Anfrage auf derselben Datei vergleichen und Gleichheit zusichern.
- [ ] **`units` gehört nicht auf die Leitung.** Als Query-Parameter nimmt der Core jede Zahl an,
  die der Aufrufer schickt — zwischen vertrauenswürdigen Prozessen unkritisch, aber es lässt
  Handler und Gate auseinanderdriften. Empfehlung für Phase 3: `units` wird eine Konstante im
  Python-Endpunkt und verschwindet aus der Schnittstelle; alternativ begrenzt der Core den Wert.
- **Klarstellung zur Tabelle oben:** `record_call()` × 2 ist bewusst eine Wiederholung, kein
  Kopierfehler. `record_call()` trägt zusätzlich in `active_users` ein
  (`forecast_budget.py:145-149`), das aber mengengeprüft und damit idempotent — zweimaliger
  Aufruf erhöht nur `calls`. Die Spec muss diese Absicht benennen.

## Prozessnotiz zu Phase 2

Die in `/20-analyse` vorgesehenen drei Explore-Agenten (betroffene Dateien · bestehende Specs ·
Abhängigkeiten) wurden **nicht erneut** gestartet: ihre Ergebnisse liegen vollständig im
Abschnitt „Bestehende Muster und Flächen" aus Phase 1 (`/10-context`), mit Datei:Zeile-Belegen.
Ein erneuter Fan-out hätte denselben Inhalt in den Hauptkontext gezogen, ohne neuen Befund.
Die strategische Bewertung (Lösungswahl, Risiko, Scope) wurde im Hauptkontext erarbeitet und
durch eine unabhängige Gegenlese geprüft; die messbaren Grundlagen dafür — Antwortformate,
`record_call()`-Aufrufer, `appendUserID`-Muster, `FetchForecast`-Zweige — sind oben jeweils mit
Fundstelle zitiert und damit ohne diesen Gesprächsverlauf nachvollziehbar.
