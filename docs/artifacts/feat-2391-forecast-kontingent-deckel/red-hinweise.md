# RED-Hinweise — Issue #2391 (Scheibe S3 von #2150, Epic #2138)

Spec: `docs/specs/modules/forecast_go_pfad_kontingent.md` (AC-1 bis AC-9)
Phase: `phase5_tdd_red`, erstellt 2026-09-21

Testdateien:

| Datei | Zeilen | Commit |
|---|---|---|
| `tests/tdd/test_internal_forecast_budget_reserve.py` | 490 | `973574a3` |
| `internal/handler/forecast_test.go` | 492 (vorher 102) | `3adbb327` |

Artefakte: `test-red-python.txt` (Exit 1, 7 von 7 rot, `404`), `test-red-go.txt`
(Exit 1, `build failed`, Aritätsfehler an 9 Stellen).

---

## 1. Abweichungen von Spec und Briefing

### 1. AC-1 liegt Python-seitig statt als Go-Test

Die `- Test:`-Zeile von AC-1 beschreibt einen Go-Test gegen einen echten
Python-Core mit `tmp_path`-Zählerdatei. Aus `go test` heraus ist das nicht
erreichbar. Die **AC selbst** ist unverändert prüfbar und liegt in
`tests/tdd/test_internal_forecast_budget_reserve.py::test_erlaubte_reservierung_bucht_zwei_einheiten_auf_die_echte_user_id`:
Zählerstand der Nutzer-Zählerdatei vor und nach einer erlaubten `reserve`,
Differenz 2. Die Spec bleibt wortgleich, nur die Realisierung wandert. Die
Go-Seite deckt die Verdrahtung über AC-2 (429/200) und AC-4 (Ankunft) ab.

### 2. `DAILY_BUDGET` wird für AC-3/AC-4/AC-8 per `monkeypatch` auf 20 gesetzt

Fixture `kleiner_deckel`, `tests/tdd/test_internal_forecast_budget_reserve.py:152`.

**Warum:** Mit dem Produktivwert 9000 bräuchte das Arrangement über 3600
`reserve`-Aufrufe (je fünf fcntl-Lock-Zyklen) — Minuten Laufzeit in der
Kern-Schicht. Die naheliegende Alternative, `active_users` mit vielen Kennungen
vorzuschreiben, um den fairen Anteil zu drücken, fällt aus: genau dieses Feld
ist der Prüfling des Schreibwegs (#2387-Falle). Der Monkeypatch auf die
Klassenkonstante lässt dagegen **jedes** geschriebene Feld vom Produkt kommen.

**ADR-0075 Punkt 6 bleibt unberührt:** `TestForecastBudgetConstantsMatchPython`
(`internal/scheduler/forecast_budget_health_test.go:256`) liest den
Python-**Quelltext**, nicht den Laufzeitwert.

**AC-1 und AC-9 laufen bewusst gegen die ECHTE Konstante** — die gebuchte Menge
(2 Einheiten, 1 Cache-Miss) muss unter Produktivbedingungen belegt sein, nicht
nur unter einem Testdeckel.

Arithmetik des Arrangements (`_baue_stufe_1_lage`, `:187`): acht Reservierungen
von A (global 16, A 16), dann eine von B (global 18 = 90 %, B 2,
`active_users = {A, B}`). Fairer Anteil bei N=2 ist 10 — A liegt mit 16 darüber,
B mit 2 darunter, der globale Anteil liegt mitten im Band
(0,80 <= 0,90 < 0,95), nicht auf der Schwelle.

### 3. `_pruefe_arrangement()` als Positivkontrolle auf den Schreibweg

`tests/tdd/test_internal_forecast_budget_reserve.py:202`. Liest `calls` (global
und je Nutzer) sowie `active_users` aus den real vom Produkt geschriebenen
Dateien zurück, **bevor** die eigentliche Handlung läuft. Doppelter Zweck:

- geforderte Positivkontrolle auf den `active_users`-Schreibweg (ADR-0075,
  Konsequenzen): fällt er aus, bleibt N = 0, der faire Anteil das ganze
  Tagesbudget, Stufe 1 feuert nie — die Drossel-Tests wären grün, ohne etwas zu
  bewachen;
- verhindert, dass ein still abgelehnter Arrangement-Aufruf in ein plausibel
  aussehendes, aber falsches Urteil läuft.

Zusätzlich sichert `_erlaube()` (`:169`) jeden Arrangement-Aufruf einzeln als
`allowed: true` ab.

### 4. `test_reserve_ohne_user_id_wird_abgewiesen` (422) liegt außerhalb der 9 ACs

`tests/tdd/test_internal_forecast_budget_reserve.py:469`. Abgeleitet aus dem
Spec-Abschnitt „Implementation Details" (`user_id` als Pflicht-Query-Parameter,
Muster `api/routers/internal.py:29`) und ADR-0075 Punkt 4 / ADR-0003 (kein
`"default"`-Rückfall). **Bewusste Zugabe, keine erfundene AC** — der Adversary
soll sie nicht als AC-Erfindung lesen.

### 5. RED-Contract für die Python-Hälfte von AC-4: kein `Literal`-Typ

`tests/tdd/test_internal_forecast_budget_reserve.py:416`. Die
`alert_check`-Assertion setzt voraus, dass der Endpunkt beliebige
Prioritätswerte entgegennimmt (kein `Literal["polling"]` in der Signatur). Nur
weil die beiden Antworten auseinandergehen, ist bewiesen, dass der Wert aus der
Query bis ins Gate durchgereicht wird — eine fest verdrahtete Priorität ergäbe
zwei gleiche Antworten. Baut die Implementierung einen `Literal`, wird dieser
Test rot, ohne dass fachlich etwas kaputt ist.

### 6. Vierter Bestandsfall ergänzt: `TestForecastHandler_InvalidHours_Returns400`

Die Spec nennt unter AC-7 drei Bestandsfälle („fehlendes `lat`, ungültiges
`lat`, ungültiges `hours`"); im Code gab es den `hours`-Fall nicht. Er ist jetzt
da, mit gültigem Auth-Kontext und 400-Erwartung wie die anderen. Alle vier
Bestandsfälle behalten ihre **400**-Erwartung unverändert (Spec AC-7, Zusatz) —
kein stilles Umschreiben auf 401.

### 7. `units` — keine Assertion, die den Parameter erwartet

Stattdessen prüft `internal/handler/forecast_test.go:363`, dass am Core **genau**
`user_id` und `priority` ankommen. Das ist die Spec-Zusicherung „Auf der Leitung
reisen NUR `user_id` und `priority`", nicht ihr Gegenteil. Die Zahl der
gebuchten Einheiten ist eine Konstante im Python-Endpunkt.

### 8. `coreStub` mit Mutex

`internal/handler/forecast_test.go:73-79`. Der httptest-Handler läuft in einer
eigenen Goroutine, die Zusicherungen lesen aus der Test-Goroutine. CI fährt
`go test ./...` ohne `-race` (`.github/workflows/ci.yml:74`); die Sperre
verhindert, dass die Datei in GREEN aus einem sachfremden Grund umfällt, falls
jemand `-race` ergänzt.

---

## 2. Einschränkungen des RED-Laufs

- **Die Go-Hälfte ist nie ausgeführt worden.** Der Compile-Fehler (fehlende
  Core-Basis-URL in der Signatur) verhindert jede Ausführung. Belegt ist per
  `go vet` ausschließlich **Typkorrektheit** — vet meldet nur die Aritätsfehler,
  nichts sonst. Jede Zusicherung in AC-2, AC-4, AC-5, AC-6 und AC-7 ist
  **unerprobt** und zeigt sich erst im ersten GREEN-Lauf. „9 Testfälle
  geschrieben" heißt hier nicht „9 Testfälle bewiesen".
- **Das Go-Artefakt ist nicht als „viele Tests kaputt" zu lesen.** Der
  Compile-Fehler legt das gesamte Paket `internal/handler` lahm, also auch alle
  Bestandstests, die mit dieser Änderung nichts zu tun haben.
- **AC-5, dritte Variante (Timeout) fehlt bewusst.** Unerreichbarer Core und
  Status ≠ 200 sind realisiert
  (`TestForecastHandler_CoreUnerreichbar_FailOpen200`,
  `TestForecastHandler_CoreAntwortetNicht200_FailOpen200`). Ein echter
  Timeout-Test pinnt eine Zeitgrenze, die die Spec nicht festlegt, und wäre
  langsam oder flaky.
- **Zwei Commits statt einem.** Der erste Commit hat die mit-gestagte Go-Datei
  still fallen lassen (`1 file changed`); Ursache unbekannt. Sie liegt in
  `3adbb327`. `git diff HEAD --stat` ist leer — Arbeitsbaum und `HEAD` sind
  deckungsgleich, die Artefakte belegen den committeten Stand.
- **Rebase war nötig:** `git fetch origin && git rebase --autostash origin/main`
  (Gate: „Branch ist 10 Commit(s) hinter origin/main"). Beide Dateien sind
  danach byte-identisch mit den Scratchpad-Kopien.

---

## 3. Für den Adversary: Stellen, an denen die Zusicherung möglicherweise nicht dort geprüft wird, wo sie WIRKT

Nach Gewicht sortiert. Je Punkt: Fundstelle und die Mutation, die rot werden
müsste.

### (a) Der WARNING-Nachweis für AC-5 hängt an einer Log-Konvention

`internal/handler/forecast_test.go:406` und `:412`.

Geprüft wird `strings.Contains(ausgabe, "WARN")` plus „`budget` oder `reserve`
kommt vor". Das ist eine Log-String-Prüfung, also genau das Muster, das schon
einmal per zufälliger Substring-Überlappung falsche Abdeckung vorgetäuscht hat
(#2152). Hier erfasst der Puffer zwar nur diesen einen Handler-Aufruf, aber die
Zusicherung „der Fehler wurde als Warnung sichtbar" hängt an einer Konvention
(`WARN`), nicht an einer Struktur. Ein Implementierer, der
`log.Printf("[forecast] reserve fehlgeschlagen: %v")` **ohne** `WARN` schreibt,
wird rot, obwohl er fachlich richtig liegt — und umgekehrt genügt ein beliebiges
`WARN`-Wort.

**Mutation, die rot werden muss:** die Warnung im Fail-open-Zweig ersatzlos
weglassen, sonst alles gleich lassen. Wird kein Test rot, ist AC-5 nur halb
bewacht.

### (b) Die Gleichheits-Zusicherung von AC-8 kennt nur eine handgeschriebene Feldliste

`tests/tdd/test_internal_forecast_budget_reserve.py:374`, Helfer `_zaehlerstand()`
bei `:116`.

Abgedeckt sind `calls` (global + beide Nutzertöpfe), `cache_misses` und
`active_users`. **Nicht** abgedeckt: `cache_hits` und jedes Feld, das die
Implementierung neu einführt. Ein abgelehnter Zweig, der irgendetwas anderes
schreibt, bliebe unentdeckt. Der Vergleich ist absichtlich ein Dict-Vergleich
und kein Feld-für-Feld-Check, aber die Feldliste stammt von mir, nicht aus der
Datei.

**Mutationen, die rot werden müssen:** (1) im abgelehnten Zweig zusätzlich
`record_cache_miss()` aufrufen; (2) im abgelehnten Zweig `record_call()` einmal
aufrufen. **Mutation, die vermutlich NICHT gefangen wird:** im abgelehnten Zweig
`record_cache_hit()` aufrufen — `cache_hits` steht nicht in `_zaehlerstand()`.
Wenn das dem Adversary wichtig ist, gehört das Feld in die Liste.

### (c) Die Naht „Go sendet polling → Core verwendet polling" ist unerprobt

`tests/tdd/test_internal_forecast_budget_reserve.py:416` (Core verwendet die
Priorität aus der Query) und `internal/handler/forecast_test.go:355` (Go sendet
`priority=polling`).

Die Python-Seite beweist, dass der Endpunkt die Priorität aus der Query liest;
sie beweist **nicht**, dass Go `polling` sendet. Diese Hälfte trägt allein der
Go-Test — und der ist wegen des Compile-Fehlers nie gelaufen. Hintergrund:
`allow()` lässt unbekannte Prioritäten fail-open immer durch
(`src/services/forecast_budget.py:133-134`), ein Tippfehler in `priority` wäre
also von außen unsichtbar.

**Mutation, die rot werden muss:** im Go-Handler `priority=polling` in
`priority=pollling` (Tippfehler) ändern. Bleibt der Go-Test grün, ist AC-4 auf
der Go-Seite wirkungslos.

### (d) `retry_after_s` wird nur auf Plausibilität geprüft, nicht auf UTC-Mitternacht

`tests/tdd/test_internal_forecast_budget_reserve.py:328` (Python) und
`internal/handler/forecast_test.go:293` (`Retry-After`-Header, Go).

Geprüft wird nur `0 < s <= 86400` und Ganzzahligkeit. Ob der Wert tatsächlich
auf das nächste UTC-Mitternacht zeigt (und nicht z. B. eine feste Stunde ist),
prüft kein Test. Eine strengere Prüfung hätte eine injizierbare Uhr am Endpunkt
gebraucht, die die Spec nicht vorsieht.

**Mutation, die vermutlich NICHT gefangen wird:** `retry_after_s = 3600` hart
verdrahten. Kein Test wird rot. Die Spec sagt aber ausdrücklich, jeder kürzere
Wert als die Zeit bis zur UTC-Tagesgrenze wäre eine Lüge — hier klafft eine
bewusst offen gelassene Lücke.

### (e) Der Provider-Aufrufzähler misst eine Stufe früher als die Wirkstelle

`internal/handler/forecast_test.go:307` (429 darf nicht abrufen) und `:396`
(fail-open muss abrufen), Typ `zaehlenderProvider` bei `:56`.

Der Zähler zählt `FetchForecast`-Aufrufe **am Handler**, nicht tatsächliche
HTTP-Abrufe bei Open-Meteo. Dass ein 429 „kein Kontingent verbrennt", ist also
eine Stufe früher gemessen, als die Wirkung entsteht. Für diese Scheibe ist das
die richtige Schnittstelle (der Handler kennt nur `FetchForecast`), aber es ist
nicht die Wirkstelle. Ein `FetchForecast`-Aufruf kostet laut Analyse im
schlechten Fall `Retries × (1 Forecast + 1 UV + ggf. 1 Fallback)` Einheiten —
davon sieht der Test nichts.

**Mutation, die rot werden muss:** im 429-Zweig `return` weglassen, sodass der
Abruf trotzdem läuft.

### (f) `_aktive_nutzer() == set()` im 422-Test ist strukturell schwach

`tests/tdd/test_internal_forecast_budget_reserve.py:487`.

Bei einem 422 aus der FastAPI-Validierung läuft ohnehin kein Endpunkt-Code. Die
Zusicherung würde erst dann etwas fangen, wenn jemand `user_id` optional macht
**und** mit einem Ersatzwert bucht. Bewusst stehen gelassen, aber keine echte
Positivkontrolle.

**Mutation, die rot werden muss:** `user_id: str = Query("default")` — dann
liefert der Endpunkt 200 statt 422 und trägt `"default"` in `active_users` ein.

### Am robustesten

`_pruefe_arrangement()` (`tests/tdd/test_internal_forecast_budget_reserve.py:202`)
und die Zwei-Nutzer-Gegenlesung in
`test_user_id_aus_der_query_bestimmt_den_getroffenen_topf` (`:428`): dort liest
der Test ausschließlich aus Dateien, die das Produkt selbst geschrieben hat, und
prüft beide Richtungen (abgelehnter Topf unverändert, erlaubter Topf +2).
