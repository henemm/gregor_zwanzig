---
entity_id: fix_2554_dwd_gewitterabruf_budget
type: module
created: 2026-10-13
updated: 2026-10-13
status: implemented
version: "1.0"
workflow: fix-2554-dwd-gewitterabruf-budget
tags: [provider, dwd, icon-d2, gewitter, zeitbudget, parallel, timeout, health-journal]
---

# fix_2554_dwd_gewitterabruf_budget

## Approval

- [ ] Approved

## Purpose

Der DWD-Gewitterabruf (`DwdDirectProvider.fetch_thunder_signals_named`) lädt für 9
Gewittergrößen und bis zu 12 Zeitpunkte rund 108 Dateien strikt nacheinander. Bei
langsamem DWD (Störung 12.10.2026, 151–170 s je Abruf) ist das 150-s-Budget nach 1–2
Zeitpunkten aufgebraucht, Berichte werden ~150 s langsamer, und das Budget-Ende war
nirgends sichtbar außer als Log-Zeile. Diese Spec macht den Abruf robust gegen eine
langsame Gegenstelle: Downloads je Zeitpunkt laufen parallel, Gewitter-Downloads
bekommen einen eigenen strengeren Timeout, und eine Budget-Erschöpfung erscheint im
Health-Journal (#2218). Das Budget selbst (150 s) bleibt unverändert.

Ursache der Störung vom 12.10. war DWD-seitig und zeitweilig (Messung 12.10. ~19:45 UTC:
alle Downloads wieder 0,02–0,06 s, 12/12 Zeitpunkte in 10,3 s) und ist nicht mehr
reproduzierbar. Behoben wird die strukturelle Schwäche, nicht die Störung selbst.
Refs #1405.

## Source

- **File:** `src/providers/dwd.py`, `src/providers/enrichment_health.py`
- **Identifier:** `DwdDirectProvider._thunder_point`,
  `DwdDirectProvider.fetch_thunder_signals_named`, neue Methode
  `DwdDirectProvider._thunder_request`, neue Konstanten `THUNDER_REQUEST_TIMEOUT`,
  `THUNDER_RETRY_ATTEMPTS`, `THUNDER_PARALLEL_DOWNLOADS`, neue Pfadkonstante
  `PATH_THUNDER_BUDGET` (Schicht: Python-Core, `src/providers/`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/http.py` (`make_deadline_before_hook`, `stop_at_deadline`, `capped_timeout_or_raise`) | Modul | geteilter Zeitbudget-Baustein (#2302) — wird für den neuen Gewitter-Abrufweg wiederverwendet, nicht verändert |
| `src/providers/dwd.py` `_PointWindowCache` / `_RASTER_CACHE` (#2465) | Klasse | ist bereits durch `threading.Lock` thread-sicher (`find`/`put`); wird nicht verändert |
| `src/providers/enrichment_health.py` (`log_enrichment_call`) | Modul | Health-Journal #2218; fail-soft Schreibweg, Go-Aggregator gruppiert generisch nach `path` (#1992 AC-8) |
| `src/providers/thunder_enrichment.py` | Aufrufer | bleibt unverändert; Vertrag „Provider wirft `ThunderSourceUnavailableError` nur bei Totalausfall" bleibt |
| `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md` | Vorgänger-Spec | AC-7 (Ausfallreihenfolge, Lauf-Rückfall), Größenreihenfolge `THUNDER_PARAMS` — bleibt erhalten |
| `docs/specs/modules/fix_2302_s2_dwd_zeitbudget.md` | Vorgänger-Spec | festes, nicht rollendes Budget; `_request`-Grundpfad unverändert |
| `httpx.Client`, `concurrent.futures.ThreadPoolExecutor` | Bibliothek | `httpx.Client` ist thread-sicher; Pool der parallelen Downloads |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/dwd.py` | MODIFY | neue Konstanten; neuer Abrufweg `_thunder_request` (eigener Timeout, eigene Versuchszahl); `_thunder_point` nutzt ihn; Zähler im `zustand` hinter einem Lock; Schleife in `fetch_thunder_signals_named` je Zeitpunkt parallel mit Lauf-Bestätigung vor dem Fan-out; Journalzeile bei Budget-Ende |
| `src/providers/enrichment_health.py` | MODIFY | neue Pfadkonstante `PATH_THUNDER_BUDGET = "thunder_budget"` (kein Go-Code nötig) |
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` | CREATE | Kern-Tests gegen echten lokalen HTTP-Server mit Verzögerung (kein Mock-Theater) |

### Estimated Changes

- Files: 3
- LoC: +110 / -20 Produktivcode (Tests zusätzlich ~250)

## Implementation Details

**A. Parallele Downloads je Zeitpunkt.** `fetch_thunder_signals_named` behält die
äußere Schleife über die Zeitpunkte (`offsets`) und die Reihenfolge „je Zeitpunkt alle
Größen in `THUNDER_PARAMS`-Reihenfolge" (#1531 AC-7). Innerhalb eines Zeitpunkts werden
die Größen nicht mehr nacheinander, sondern über einen kleinen `ThreadPoolExecutor`
(`THUNDER_PARALLEL_DOWNLOADS = 5` Verbindungen) abgerufen. Ein Pool wird je Abruf
gebildet und am Ende geschlossen. Kein Fan-out über mehrere Zeitpunkte hinweg: das würde
die Ausfallreihenfolge brechen (hintere Zeitpunkte würden vor vorderen Größen laden).

- **Reihenfolge:** Die Aufgaben werden in `THUNDER_PARAMS`-Reihenfolge eingereicht (der
  Pool nimmt sie in dieser Reihenfolge an); die Ergebnisse werden danach über die
  Größe (nicht über die Fertigstellungsreihenfolge) in `roh_je_param[param][offset]`
  einsortiert. Das Budget wird in jeder Aufgabe vor dem Download geprüft
  (`_thunder_budget_erschoepft`, wie bisher vor jedem Einzel-Call). Weil spätere
  Aufgaben nie vor früheren starten, kann bei Budget-Ende keine hintere Größe geladen
  worden sein, wenn eine vordere wegen Budget übersprungen wurde. Meldet ein Zeitpunkt
  Budget-Ende, wird kein weiterer Zeitpunkt begonnen. In-flight-Downloads enden spätestens
  an der Frist, weil `capped_timeout_or_raise` den Versuchs-Timeout auf die Restzeit
  deckelt.
- **Entscheidung Lauf-Rückfall (404): Bestätigung vor Fan-out.** Der Rückfall auf einen
  älteren Lauf darf nur geschehen, solange noch kein Lauf durch eine Antwort bestätigt
  ist (`zustand["bestaetigt"]`, #1531 AC-7/#1457 AC-2). Racen mehrere Threads gegen
  einen noch unbestätigten Lauf, könnten zwei Threads `zustand["index"]` doppelt erhöhen
  (Lauf übersprungen) oder eine Reihe auf verschiedene Läufe verteilen. Deshalb gilt:
  Solange `bestaetigt` False ist, werden die Größen des Zeitpunkts wie bisher
  **nacheinander** abgerufen, bis die erste Antwort (oder ein Cache-Treffer) den Lauf
  bestätigt; erst die übrigen Größen dieses Zeitpunkts und alle folgenden laufen
  parallel. Nach der Bestätigung wird `zustand["index"]` nie wieder verändert (der
  404-Zweig ist über `not zustand["bestaetigt"]` gesperrt), womit der Lauf-Rückfall
  unter Parallelität nicht kippen kann. Verworfen: ein Lock um den ganzen Rückfall-Zweig
  (hielte Downloads während des Lock-Besitzes an und bliebe trotzdem von der Reihenfolge
  abhängig, welcher Thread zuerst 404 sieht).
- **Zähler:** `zustand["versucht"]` und `zustand["fehlgeschlagen"]` werden vom
  Haupt- und von Worker-Threads mit `+= 1` verändert, das ist nicht atomar. Sie werden
  hinter einem `threading.Lock` erhöht (kleiner Helfer, der Lock lebt neben dem Dict je
  Abruf). Die Totalausfall-Prüfung (`versucht > 0 and fehlgeschlagen == versucht` →
  `ThunderSourceUnavailableError`) bleibt unverändert und läuft nach dem Pool.
- **`_RASTER_CACHE`:** unverändert, ist durch seinen eigenen Lock thread-sicher. Zwei
  Threads, die dieselbe URL gleichzeitig laden, legen den Ausschnitt nicht doppelt ab
  (bestehender Schutz in `put`). Cache-Treffer (#2465) laufen im Worker ohne Download.
- **Anker-Abruf** für kumuliertes `grau_gsp` bleibt ein einzelner, vorgezogener,
  sequentieller Abruf vor den Zeitpunkten (kann den Lauf bestätigen).
- **Speicher:** höchstens 5 gleichzeitig entpackte Raster; das Fenster (41×41) wird
  sofort extrahiert, das große Raster danach freigegeben (bestehendes Verhalten von
  `_decode_window`).

**B. Eigener Timeout und weniger Retries nur für Gewitter.** Neue Konstanten
`THUNDER_REQUEST_TIMEOUT = 10.0` und `THUNDER_RETRY_ATTEMPTS = 2`. Neue Methode
`_thunder_request(url, deadline_at)` mit eigenem `@retry` (gleiche Bausteine:
`stop_after_attempt(THUNDER_RETRY_ATTEMPTS) | stop_at_deadline`,
`make_deadline_before_hook("_fetch_deadline_seconds")`, Backoff wie bisher), eigenem
Kopf-Check mit `base_timeout=THUNDER_REQUEST_TIMEOUT`. `_thunder_request` wiederholt
nur bei 500/502/503/504 und `httpx.ConnectError`, **nicht** bei `ReadTimeout`: ein
Server, der 10 s geschwiegen hat, erholt sich innerhalb des Abrufs selten, und ein
zweiter Versuch würde den Hänger verdoppeln. Ein hängender Einzelabruf kostet damit
höchstens `THUNDER_REQUEST_TIMEOUT`. `_thunder_point` ruft `_thunder_request` statt
`_request`. `_request`, `_fetch_series`, `TIMEOUT = 30`, `RETRY_ATTEMPTS = 5` und
`FETCH_DEADLINE_SECONDS` (Grundvorhersage) bleiben unverändert.

**C. Budget-Erschöpfung im Health-Journal.** Das Journal (`log_enrichment_call`, #2218)
wird in `thunder_enrichment.py` bisher nur vom Aufrufer geschrieben, der aus dem
Provider-Ergebnis nicht erkennt, ob das Budget ausgeschöpft war. Kleinster Weg: der
Provider selbst schreibt am Ende von `fetch_thunder_signals_named` **eine** Zeile je
Abruf mit eigenem Pfad `thunder_budget` (`PATH_THUNDER_BUDGET`): Outcome `fallback`
(= „degradiert, aber bedient") mit `detail="icon_d2_budget_erschoepft"`, wenn das Budget
erschöpft war; Outcome `ok`, wenn der Abruf ohne Budget-Ende durchlief. Der Go-
Aggregator gruppiert generisch nach `path` (#1992 AC-8), ein neuer Wert braucht keine
Go-Änderung; ein eigener Pfad vermeidet, dass das Budget-Ende von der `ok`-Zeile des
Aufrufers (`thunder`) überdeckt wird. `log_enrichment_call` ist selbst fail-soft; der
Aufruf steht innerhalb der „wirft nie"-Hülle.

**Nicht geändert:** `THUNDER_FETCH_DEADLINE_SECONDS = 150.0` (PO-Entscheid 2026-08-08),
`dwd_eu.py`, Mail-Renderer, `thunder_enrichment.py`. Das Budget bleibt fest und wird
einmal je Abruf gebildet (Lehre #1448). Der Vertrag „best effort, wirft nie" bleibt
(einzige Ausnahme wie bisher: `ThunderSourceUnavailableError` bei Totalausfall,
#1492 S2a).

## Expected Behavior

- **Input:** `fetch_thunder_signals_named(location, start, end)` gegen ICON-D2-Open-Data,
  unverändert.
- **Output:** gleiche Struktur und gleiche Werte wie bisher; bei langsamer Gegenstelle
  kommen deutlich mehr Zeitpunkte je Größe an.
- **Side effects:** eine zusätzliche Journalzeile (`path=thunder_budget`) je Abruf; bis
  zu 5 parallele Verbindungen zu `opendata.dwd.de`.

## Test Plan

Kern-Schicht (deterministisch, kein Internet): neue Datei
`tests/tdd/test_dwd_thunder_parallel_fetch.py`, benannt nach Verhalten. Sie nutzt einen
echten lokalen `ThreadingHTTPServer` (Muster `test_dwd_thunder_signal_fetch.py`
`_GewitterServer`, aufgezeichnete Rasterdaten als Fixture), der je Anfrage eine
einstellbare Verzögerung, einen 404 für einzelne Läufe/URLs oder einen Hänger liefern
kann. Der Server zählt Anfragen je URL mit. Kein `Mock()`/`patch()` des Providers;
erlaubt ist nur `monkeypatch` der Modulkonstanten (`THUNDER_FETCH_DEADLINE_SECONDS`,
`THUNDER_REQUEST_TIMEOUT`, Basis-URL). Jeder Test setzt `@pytest.mark.timeout(N)`
oberhalb der erwarteten Laufzeit. Die Journal-Tests lesen die JSONL-Datei über die
Test-Isolation der Datenwurzel (`get_data_root`, Falle #1633).

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-1): GIVEN lokaler Server mit 0,2 s Verzögerung je Datei und Budget
  auf 8 s gepatcht WHEN der Abruf für 12 Zeitpunkte läuft THEN liegen je Größe
  mindestens 10 Zeitpunkte vor (sequentiell wären es höchstens ~4).
- [ ] Test 2 (AC-2): GIVEN Server, der erst nach der Budgetgrenze zu langsam wird (Budget
  klein gepatcht) WHEN der Abruf abbricht THEN fehlen nur hintere Zeitpunkte, und je
  fehlendem Zeitpunkt fehlen nur hintere Größen (nie fehlt eine vordere Größe bei
  vorhandener hinterer).
- [ ] Test 3 (AC-3): GIVEN ein Server hängt bei genau einer URL (schläft länger als der
  Timeout), `THUNDER_REQUEST_TIMEOUT` auf 0,5 s gepatcht WHEN der Abruf läuft THEN
  dauert der Gesamtabruf höchstens Timeout plus Rand, die URL wurde genau einmal
  angefragt, die Zelle bleibt `None`, alle anderen sind gefüllt.
- [ ] Test 4 (AC-4): GIVEN der jüngste Lauf liefert 404 für alle URLs, ein älterer
  existiert, UND einzelne spätere Stunde 404 im bestätigten Lauf WHEN der Abruf
  parallel läuft THEN stammen alle Werte aus dem älteren Lauf, die einzelne Stunde bleibt
  `None`, und der Server sah keine Anfrage dieser URL gegen einen noch älteren Lauf.
- [ ] Test 5 (AC-5): GIVEN normaler Server ohne Verzögerung WHEN der Abruf läuft THEN sind
  Werte und Reihenfolge der Zeitpunkte je Größe identisch zu einem aufgezeichneten
  Sollstand, inklusive differenziertem `grau_gsp` mit Anker.
- [ ] Test 6 (AC-6): GIVEN Budget klein gepatcht, Server langsam WHEN der Abruf
  abbricht THEN steht im Journal eine Zeile `path=thunder_budget`, `outcome=fallback`;
  bei vollständigem Lauf eine Zeile mit `outcome=ok`.
- [ ] Test 7 (AC-7): GIVEN der Abruf lief einmal WHEN derselbe Punkt/dasselbe Fenster
  erneut abgerufen wird THEN sieht der Server keine neue Anfrage.
- [ ] Test 8 (AC-8): GIVEN Server liefert 500er, Verbindungsabbruch, Müll-Bytes bzw.
  Journal-Schreibfehler WHEN der Abruf läuft THEN wirft er nicht (außer bei Totalausfall
  den bestehenden `ThunderSourceUnavailableError`), und der Pool hinterlässt keinen
  hängenden Thread.

Bestehende Tests bleiben unverändert grün: `tests/tdd/test_dwd_thunder_signal_fetch.py`,
`test_dwd_thunder_new_signals_fetch.py`, `test_dwd_eu_thunder_time_budget.py`,
`test_provider_request_deadline.py`, `tests/unit/test_dwd_thunder_raster_cache.py`.
Der Befund „vorbestehend rot" von `test_dwd_thunder_signal_fetch.py::test_ac3_…` (siehe
#2302 S2) wird weder verändert noch verschlimmert. Live-Schicht: Nachweis gegen Staging
(`/e2e-verify`) nur als Regressionslauf; die Störung ist nicht nachstellbar.

### Mutations-Gegenproben (PFLICHT)

Jede Verfälschung per String-Ersetzung mit externer Sicherungskopie, nie `git checkout`:

| Verfälschung | Muss rot werden |
|---|---|
| Einsortieren über Fertigstellungsreihenfolge statt über die Größe (z. B. Ergebnisliste statt Zuordnung nach `param`) | Test 5 (Werte vertauscht) und Test 2 |
| Pool wieder auf 1 Worker (`THUNDER_PARALLEL_DOWNLOADS = 1`) | Test 1 |
| `THUNDER_REQUEST_TIMEOUT` zurück auf 30 s (bzw. `_thunder_point` ruft wieder `_request`) | Test 3 |
| `ReadTimeout` im Gewitterweg wieder wiederholt | Test 3 (URL zweimal angefragt) |
| Lauf-Bestätigung vor Fan-out entfernt (sofort alles parallel) | Test 4 |
| Lock um die Zähler entfernt | Test 8 (Zählerstand `versucht`/`fehlgeschlagen` stimmt nicht; ggf. mit `sys.setswitchinterval`-Verschärfung im Test) |
| Budget-Prüfung in der Worker-Aufgabe entfernt | Test 2 |
| Journalzeile entfernt oder auf falschen Pfad geschrieben | Test 6 |
| Cache-Prüfung in `_thunder_point` entfernt | Test 7 |
| Anker (`vorwert`) für `grau_gsp` ignoriert | Test 5 |
| Journal-Fehler nicht abgefangen (Schreibfehler bricht den Abruf) | Test 8 |

Leitfrage je Probe: Ist die Zusicherung dort geprüft, wo sie WIRKT (am Ergebnis bzw. an den
Server-Zählern), nicht nur dort, wo der Code steht?

## Acceptance Criteria

**AC-1:** Given ein langsamer DWD-Server (lokaler HTTP-Testserver mit festem Verzug je Datei, Budget auf eine kurze Wanduhrzeit gepatcht) / When der Gewitterabruf für 12 Zeitpunkte und 9 Größen läuft / Then kommen innerhalb des Budgets deutlich mehr Zeitpunkte je Größe an, als ein sequentieller Abruf in derselben Zeit schaffen würde (mindestens das Doppelte).

**AC-2:** Given das Budget läuft während des Abrufs ab / When der Abruf abbricht / Then bleiben die vorderen Größen (`lpi`, `grau_gsp`, `cin_ml`, …) und die vorderen Zeitpunkte erhalten, und es fehlen nur hintere Zeitpunkte bzw. je Zeitpunkt nur hintere Größen; nie fehlt eine vordere Größe, wenn eine hintere desselben Zeitpunkts geladen wurde.

**AC-3:** Given ein einzelner Download hängt (Server antwortet nicht) / When der Abruf läuft / Then kostet dieser Download höchstens `THUNDER_REQUEST_TIMEOUT` (10 s) und wird bei einem Timeout nicht wiederholt, die betroffene Zelle bleibt leer (`None`, nie 0), alle anderen Zellen kommen an, und der Abruf dauert insgesamt nicht länger als dieser Timeout plus Rand.

**AC-4:** Given der jüngste Modelllauf ist noch nicht verfügbar (404), ein älterer ist es / When der Abruf mit parallelen Downloads läuft / Then kommen alle Werte konsistent aus einem einzigen Lauf (dem ersten bestätigten), und eine später einzeln fehlende Stunde (404) bleibt leer, ohne die Reihe auf einen anderen Lauf zu verschieben.

**AC-5:** Given ein normal schneller DWD-Server / When der Abruf läuft / Then sind Werte, Größenreihenfolge und Zeitpunktreihenfolge identisch zum Ergebnis vor der Änderung, einschließlich des aus dem kumulierten Signal `grau_gsp` abgeleiteten Stundenwerts mit seinem Anker-Abruf.

**AC-6:** Given das Gewitter-Budget (150 s im Betrieb) wird erschöpft / When der Abruf endet / Then steht im Health-Journal genau eine Zeile mit Pfad `thunder_budget` und Ausgang `fallback` (Detail `icon_d2_budget_erschoepft`); läuft der Abruf ohne Budget-Ende durch, steht dort Ausgang `ok`.

**AC-7:** Given ein Punkt-Fenster liegt bereits im Cache (#2465) / When derselbe Punkt erneut abgerufen wird / Then löst das keinen Download aus und liefert dieselben Werte.

**AC-8:** Given Serverfehler, Verbindungsabbrüche, unlesbare Antworten oder ein nicht schreibbares Journal / When der Abruf läuft / Then wirft er nie nach außen (einzige Ausnahme wie bisher: `ThunderSourceUnavailableError` bei Totalausfall), das Budget bleibt fest bei 150 s, und nach dem Abruf läuft kein Download-Thread weiter.


## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Technische Härtung innerhalb des bestehenden Gewitter-Abrufwegs (Parallelität, Timeout, Journalzeile). Keine Änderung an Kanälen, Providerwahl, Datenmodell, Auth oder Budgetgröße; PO-Entscheid 150 s (2026-08-08) und ADR-0018 (degradierte Pfade sichtbar machen) werden eingehalten bzw. umgesetzt.

## Changelog

- 2026-10-13: Initial spec created (Refs #2554, #1405)
