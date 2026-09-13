---
entity_id: fix_2302_s2_dwd_zeitbudget
type: module
created: 2026-09-12
updated: 2026-09-12
status: draft
version: "1.0"
tags: [provider, zeitbudget, deadline, retry, httpx, tenacity, dwd, icon-d2, icon-eu]
---

# fix_2302_s2_dwd_zeitbudget

## Approval

- [x] Approved — PO-Freigabe 2026-09-12

## Purpose

`src/providers/dwd.py` (ICON-D2) und `src/providers/dwd_eu.py` (ICON-EU) prüfen ihr
Zeitbudget heute nur **zwischen** zwei `_request`-Aufrufen. Ein einzelner Abruf gegen eine
Gegenstelle, die die Verbindung annimmt und dann schweigt, kann die Retry-Kette rechnerisch
~390 s offenhalten, ohne dass die bestehende Zwischen-Aufruf-Prüfung das je bemerkt. Diese
Spec überträgt den in Scheibe A gebauten geteilten Baustein `src/providers/http.py` auf
beide Dateien und ersetzt den Test-Wächter, der heute **Abrufe** statt **verstrichener Zeit**
zählt (Befund D5).

Diese Spec beschreibt ausschließlich **Scheibe B** von #2302 (Epic #2257 Block 2). Scheibe A
(`src/providers/http.py`, `openmeteo.py`, `meteofrance.py`-Grundpfad) ist bereits umgesetzt
(`docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md`, Commit `c31a09a6`) und wird
hier nicht verändert. Scheibe C (`geosphere.py`, D2) folgt als eigener Workflow unter
demselben Issue.

## Source

- **File:** `src/providers/dwd.py`, `src/providers/dwd_eu.py`
- **Identifier:** `DwdDirectProvider._request`, `DwdDirectProvider._thunder_point`,
  `DwdDirectProvider.fetch_thunder_signals_named`, `DwdEuDirectProvider._request`,
  `DwdEuDirectProvider._thunder_point`, `DwdEuDirectProvider.fetch_thunder_signals_named`
  (Schicht: Python-Core, `src/providers/`)

## Estimated Scope

- **LoC:** ~180–220 Code plus Teständerungen (Schätzung aus der Analyse-Phase; bei
  Überschreitung ist `workflow.py set-field loc_limit_override 500` der dokumentierte Weg,
  nicht Scope-Schnitt)
- **Files:** 4
- **Effort:** medium

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/providers/dwd.py` | MODIFY | `_request(self, url, deadline_at=None)` bekommt den geteilten `@retry`-Zusatz (`stop_at_deadline`, `before=make_deadline_before_hook("_fetch_deadline_seconds")`) und den Kopf-Check `capped_timeout_or_raise`; neue Accessor-Methode `_fetch_deadline_seconds` liefert `FETCH_DEADLINE_SECONDS` (180 s, die WEITERE Hülle, auch als Hook-Vorgabewert für den Gewitterpfad); `_fetch_series` und `fetch_thunder_signals_named` reichen ihr jeweils schon lokal gebildetes `deadline_at` explizit durch; `_thunder_point` bekommt einen `deadline_at`-Parameter und reicht ihn an `_request` weiter |
| `src/providers/dwd_eu.py` | MODIFY | dieselbe Mechanik, ein Budget: Accessor liefert `THUNDER_FETCH_DEADLINE_SECONDS` (25 s); `_thunder_point` bekommt `deadline_at` und reicht ihn an `_request` weiter; `fetch_thunder_signals_named` reicht ihr lokal gebildetes `deadline_at` durch |
| `tests/tdd/test_provider_request_deadline.py` | MODIFY | neue Wanduhr-Wächter für `dwd.py` und `dwd_eu.py` ergänzt — der bestehende `_HangingServer` (`:105`) und die Normalfall-Gegenprobe (`:351`) werden geteilt, nicht kopiert |
| `tests/tdd/test_dwd_eu_thunder_time_budget.py` | MODIFY | `pytestmark = pytest.mark.live` (`:31`) entfernt; Docstring-Behauptung „ein Laufzeit-Test misst die Maschine, nicht die Zeitgrenze" (`:49-52`) korrigiert; der bestehende Zähl-Test bleibt inhaltlich unverändert erhalten |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/http.py` (`make_deadline_before_hook`, `stop_at_deadline`, `capped_timeout_or_raise`) | Modul (Scheibe A) | geteilter Zeitbudget-Baustein — wird angewandt, nicht verändert |
| `src/providers/meteofrance.py:426-476` | Vorbild | Anwendungsmuster (Accessor, Dekorator, Kopf-Check, Durchreichen) — Scheibe B überträgt es eins zu eins auf den Grundpfad und zusätzlich auf den Gewitterpfad |
| `tests/tdd/test_provider_request_deadline.py` (Scheibe A, 903 Z., ungemarkert) | Testdatei | Heimat der neuen Wächter; `_HangingServer` (`:105`) und Normalfall-Gegenprobe (`:351`) werden geteilt |
| `tests/tdd/test_dwd_eu_thunder_time_budget.py` | Testdatei | bestehender Zähl-Wächter, bleibt als eigenständige Zusicherung (Signal-Reihenfolge unter Budgetdruck) erhalten |
| `docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md` | Vorgänger-Spec | Formvorbild für AC-Sprache und Baustein-Vertrag — wird nicht editiert |

## Implementation Details

### `src/providers/dwd.py` — der Dual-Fall

`dwd.py` hat **ein** `@retry`-dekoriertes `_request` (`:316-330`), das **zwei** Aufrufer mit
unterschiedlichem Budget bedient: den Grundpfad (`_fetch_series` → `FETCH_DEADLINE_SECONDS`,
180 s) und den Gewitterpfad (`fetch_thunder_signals_named` → `_thunder_point` →
`THUNDER_FETCH_DEADLINE_SECONDS`, 150 s). Ein `before`-Hook kann nur einen Vorgabewert haben,
darum reicht **jeder** Aufrufer sein bereits lokal vorhandenes `deadline_at` explizit durch:

- `_fetch_series` (`:332-350`) hat `deadline_at` bereits als Parameter — es wird zusätzlich an
  `_request(url, deadline_at=deadline_at)` (`:348`) durchgereicht statt nur für die eigene
  Zwischen-Aufruf-Prüfung (`:341`) genutzt zu werden.
- `fetch_thunder_signals_named` bildet `deadline_at` bereits lokal (`:450`). `_thunder_point`
  bekommt dafür einen neuen Parameter `deadline_at: Optional[float] = None` und reicht ihn bei
  seinem `_request`-Aufruf (`:371`) durch; beide Aufrufstellen von `_thunder_point`
  (`:471-473`, `:489-492`) übergeben das schon vorhandene `deadline_at` aus dem umgebenden
  Gültigkeitsbereich.
- Der `before`-Hook greift nur, wenn **keiner** der beiden Aufrufer `deadline_at` übergeben
  hat. Er muss dann die **weitere** Hülle liefern: Die neue Accessor-Methode
  `_fetch_deadline_seconds(self) -> float: return FETCH_DEADLINE_SECONDS` liefert **180 s**,
  nie 150 s — sonst würde ein vergessenes Durchreichen den Gewitterpfad heimlich verkürzen
  statt (im schlimmsten Fall) den Grundpfad heimlich zu verlängern.

### `src/providers/dwd_eu.py` — der einfache Fall

Strukturell deckungsgleich, aber nur **ein** Budget (`THUNDER_FETCH_DEADLINE_SECONDS`,
25 s) für den einzigen vorhandenen Pfad (die Datei implementiert nur das
Gewittersignal-Protokoll, kein `fetch_forecast`). Ein Accessor genügt:
`_fetch_deadline_seconds(self) -> float: return THUNDER_FETCH_DEADLINE_SECONDS`.
`_thunder_point` (`:321-365`) bekommt denselben neuen `deadline_at`-Parameter und reicht ihn
an `_request` (`:339`) weiter; `fetch_thunder_signals_named` (`:404`) reicht ihr lokal
gebildetes `deadline_at` durch.

### Fail-soft-Hülle — Zusicherung ist die Wanduhr, nicht der Ausnahmetyp

Beide `fetch_thunder_signals_named`-Methoden fangen intern jede Ausnahme ab
(`dwd.py:438/502`, `dwd_eu.py:393/415`) und liefern ein leeres oder unvollständiges Ergebnis
statt zu werfen — das ist ihr vorhandener „wirft NIE"-Vertrag (#1492 S2a), den diese Spec
nicht verändert. `_thunder_point` fängt zusätzlich selbst jede Ausnahme aus seinem eigenen
`_request`-Aufruf ab (`dwd.py:372/392`, `dwd_eu.py:340/359`) und liefert `None` zurück. Ein
`ProviderRequestError`, den `capped_timeout_or_raise` beim Überschreiten der Frist auslöst,
verlässt diesen Pfad also **nie** als propagierte Ausnahme — anders als beim direkten
`_request`-Aufruf des Grundpfads (Scheibe A `_ABBRUCH`-Muster). Die Tests für den
Gewitterpfad (AC-4, AC-5) prüfen deshalb ausschließlich **verstrichene Zeit** und dass das
Ergebnis den erwarteten fail-soft-Rückfall zeigt (`None`/leere Reihe) — nicht, welcher
Ausnahmetyp dabei intern auftritt. Die Grundpfad-Tests (AC-1, AC-2), die `_request` direkt
und ohne die fail-soft-Hülle aufrufen, übernehmen dagegen das tolerante `_ABBRUCH`-Muster aus
Scheibe A (`(ProviderRequestError, httpx.HTTPError)`, `test_provider_request_deadline.py:95`)
— dort ist der genaue Ausnahmetyp aus denselben Gründen wie in Scheibe A nicht Teil der
Spec-Zusicherung.

### Die dwd-Zusicherung braucht zwei unterscheidbare Budgets

Der gefährliche Fehler ist nicht „keine Frist", sondern „**stillschweigend die falsche**
Frist": Reicht die Gewitter-Aufrufstelle ihr `deadline_at` nicht durch, setzt der
`before`-Hook den Vorgabewert 180 s — der Gewitterpfad bekäme heimlich das weitere Budget der
Grundvorhersage. Ein Test, der `FETCH_DEADLINE_SECONDS` und `THUNDER_FETCH_DEADLINE_SECONDS`
auf denselben kleinen Wert patcht, bliebe dabei grün und würde diesen Fehler **nicht**
fangen. AC-4 patcht deshalb **deutlich verschiedene** Werte: `THUNDER_FETCH_DEADLINE_SECONDS`
klein (0,45 s), `FETCH_DEADLINE_SECONDS` deutlich größer (5 s). Fehlt das Durchreichen an der
Gewitter-Aufrufstelle, würde die tatsächlich verstrichene Zeit gegen die **größere** gepatchte
Grenze laufen (bis zu ~5 s statt der erwarteten <0,9 s) — genau das macht der geforderte
Mutations-Gegenprobe-Wächter sichtbar.

## Expected Behavior

- **Input:** Aufruf von `_request` (Grundpfad oder Gewitterpfad, `dwd.py` oder `dwd_eu.py`),
  mit oder ohne explizit übergebenes `deadline_at`.
- **Output:** Bei einer hängenden Gegenstelle bricht der Grundpfad spätestens bei erreichter
  Frist mit einer Ausnahme aus der Menge `(ProviderRequestError, httpx.HTTPError)` ab; der
  Gewitterpfad bricht innerhalb seiner eigenen (kleineren) Frist ab und liefert dabei — seinem
  bestehenden fail-soft-Vertrag folgend — `None`/eine unvollständige Reihe statt eine
  propagierte Ausnahme. Ein normal antwortender Server liefert in beiden Pfaden unverändert
  Daten.
- **Side effects:** Kein geteiltes `Retrying`-Objekt zwischen `DwdDirectProvider` und
  `DwdEuDirectProvider`. `TIMEOUT`, `FETCH_DEADLINE_SECONDS` und
  `THUNDER_FETCH_DEADLINE_SECONDS` bleiben Modul-Globals in den jeweiligen Dateien.

## Bewusst akzeptierte Verhaltensänderung

`capped_timeout_or_raise` deckelt den HTTP-Timeout eines Versuchs auf `min(base_timeout,
Restzeit)`. Am Ende einer langen Abruf-Schleife (z. B. spät in `_fetch_series`s
Stunden-Schleife oder spät in `_thunder_point`s Zeitschritt-Schleife) kann diese Restzeit
**unter** die heutigen festen 30 s (`TIMEOUT`) fallen. Ein einzelner Abruf, der heute in 25 s
durchkäme, kann nach diesem Fix mit nur noch 5 s Restzeit scheitern, obwohl der Server
grundsätzlich geantwortet hätte. Das ist die **gewollte** Wirkung des Zeitbudgets — aber die
einzige Stelle, an der heute erfolgreiche (nur langsame) Abrufe durch diese Änderung neu
kippen können. Diese Randbedingung ist absichtlich Teil der Spec, nicht nur des PR-Textes.

## Ausdrückliche Grenzen

- **Tröpfel-Fall (D6) bleibt ungedeckt.** Eine einzelne, beliebig lang hingezogene Antwort
  (Byte für Byte, jedes einzeln innerhalb des httpx-Timeouts) wird vom geteilten Baustein
  **nicht** erkannt — httpx hat dafür keinen Parameter, im Haus existiert kein Vorbild, das
  das schließt. Das ist ein eigenes Ticket, kein Teil von Scheibe B. Verschweigen scheidet
  aus.
- **K3 — Lauf-Rückfall in der `while True`-Schleife.** Das Durchreichen von `deadline_at` an
  `_thunder_point` (`dwd.py:352`, `dwd_eu.py:321`) und von dort an `_request` ist **Teil**
  dieser Spec (AC-4/AC-5) — kein Vorbehalt mehr. Offen bleibt nur eine engere Restfrage für
  die TDD-RED-Phase: Ob dieses einfache Parameter-Durchreichen den Multiplikator auch dann
  vollständig schließt, wenn `_thunder_point` bei wiederholten 404-Kandidatenwechseln
  **mehrfach** `_request` mit derselben absoluten `deadline_at` aufruft, oder ob dafür eine
  zusätzliche Prüfung zwischen den Kandidatenwechseln nötig ist. Gelingt das Schließen nicht
  trivial über das reine Durchreichen, wird der Rest in der TDD-RED-Phase ausdrücklich als
  offener Punkt benannt, nicht stillschweigend weggelassen.
- **Nie beobachtet.** Der Nachweis ist Konstruktion gegen `_HangingServer`; es gibt keinen
  Live-Vorfall zu reproduzieren.
- **`tests/tdd/test_dwd_thunder_signal_fetch.py` ist nicht Gegenstand dieser Scheibe.** Der
  Test `test_ac3_dauerhafter_serverfehler_liefert_leeres_ergebnis_statt_ausnahme` ist
  vorbestehend rot (Messung M4) — Commit `5a8b6014` (#1492 S2a) hat das dort erwartete
  Verhalten bewusst abgelöst. Die Datei bleibt `live`-gemarkert; ein Entmarkern würde die
  CI-Ampel rot färben. Nebenbefund gehört in #1199, nicht in diese Scheibe.

## Known Limitations

- Siehe „Ausdrückliche Grenzen" oben — Tröpfel-Fall, K3-Restfrage, fehlender Live-Nachweis,
  `test_dwd_thunder_signal_fetch.py` unverändert vorbestehend rot.
- Cross-Provider-Totalausfall und Gewitter-Vertretung behalten laut ADR-0047 Entscheidung 6
  ihr eigenes volles Budget je Quelle — diese Spec überträgt keine Restzeit zwischen
  Provider-Quellen.

## Test Plan

Given/When/Then der einzelnen Zusicherungen steht ausschließlich in `## Acceptance Criteria`
unten — dieser Abschnitt wiederholt es nicht, sondern hält die Rahmenbedingungen fest, die
für **alle** ACs gelten.

### Heimat und Teilung

Alle neuen Wanduhr-Wächter (AC-1 bis AC-8) gehören in
`tests/tdd/test_provider_request_deadline.py` (aus Scheibe A, 903 Zeilen, **ungemarkert**, in
der CI-Ampel). `_HangingServer` (`:105`) und die Normalfall-Gegenprobe
(`test_normalfall_liefert_unveraendert_daten`, `:351`) werden von dort **geteilt, nicht
kopiert**.

**Dokumentierte Abweichung von D5:** D5 (Kontext-Dokument `:79-94`) verlangte den
Wanduhr-Test „in **derselben** Datei" wie der bestehende Zähl-Test, mit einer **Kopie** des
`_HangingServer`. D5 wurde formuliert, **bevor** Scheibe A
`tests/tdd/test_provider_request_deadline.py` geschaffen hat. Wir folgen D5s **Absicht**
(Wanduhr-Nachweis statt Aufrufzahl-Nachweis), nicht seinem Wortlaut: die neuen Wächter
gehören in die Scheibe-A-Datei, das teilt den `_HangingServer`-Baustein statt ihn ein zweites
Mal zu kopieren. Das Entmarkern von `test_dwd_eu_thunder_time_budget.py` (AC-9) bleibt davon
unberührt — es ist eine eigenständige Zusicherung, die einen bereits vorhandenen Wächter im
Normallauf sichtbar macht, keine Wanduhr-Frage.

### Schwellen

Aus Scheibe A **übernommen, nicht verschärft**: `elapsed < 0.9` Sekunden bei einer auf 0,45 s
gepatchten Frist; Normalfall-Gegenprobe `elapsed < 2.0` Sekunden. Diese Verhältnisse haben
CI-Läufe bereits überstanden — eine knappere Schwelle wäre eine Zeitbombe, die erst in
fremden PRs rot wird, nicht hier.

### Timeout-Absicherung je Hänger-Test

`pyproject.toml:69` setzt global `timeout = 30`. Jeder Test gegen `_HangingServer` trägt
zusätzlich ein eigenes `@pytest.mark.timeout(N)` mit `N` oberhalb der erwarteten
Fehlschlag-Laufzeit — ein Timeout-Kill statt einer lesbaren Assertion wäre ein schlechteres
Artefakt bei einer Regression.

### Regressions-Grundlinie (Messung M3)

Vor der ersten Code-Änderung gemessen: die sechs in M3 benannten Testdateien liefen mit
`-m ''` bei 43 passed / 1 vorbestehend failed
(`test_dwd_thunder_signal_fetch.py::test_ac3_dauerhafter_serverfehler_liefert_leeres_ergebnis_statt_ausnahme`,
M4). Dieses Ergebnis muss nach GREEN unverändert bleiben (AC-10).

### Wechselwirkung mit dem bestehenden Zähl-Test (AC-9)

`test_dwd_eu_thunder_time_budget.py` patcht `THUNDER_FETCH_DEADLINE_SECONDS` auf 0,4 s bei
0,15 s Verzögerung je Abruf (`:63-73`). Nach diesem Fix deckelt `capped_timeout_or_raise`
dort zusätzlich den Einzel-Timeout jedes Abrufs. Ob die bestehenden Assertionen
(`abrufe >= 1`, `abrufe < ohne_zeitdruck`, `abrufe <= _ABRUF_SCHWELLE`) dadurch unverändert
grün bleiben, ist plausibel (die Fixture zählt serverseitig, unabhängig vom Client-Timeout),
wird aber **im TDD-RED-Lauf gemessen, nicht vorab behauptet**. Bricht die Wechselwirkung den
Test, ist das ein Finding für die Implementierungsphase, kein stiller Spec-Widerspruch.

### Mutations-Gegenprobe (PFLICHT)

Entfernt man das Durchreichen von `deadline_at` an der Gewitter-Aufrufstelle in `dwd.py`
(`_thunder_point` → `_request`, konkret die Argumente bei `:471-473`/`:489-492` bzw. den neuen
Parameter an `_thunder_point` selbst), MUSS der AC-4-Wächter rot werden — die verstrichene
Zeit läuft dann gegen den `before`-Hook-Vorgabewert (180 s bzw. den gepatchten
`FETCH_DEADLINE_SECONDS`-Wert), nicht gegen die enge Gewitter-Frist.

## Acceptance Criteria

- **AC-1:** Given der ICON-D2-Grundpfad ruft `_request` direkt gegen `_HangingServer` mit auf 0,45 s gepatchtem `FETCH_DEADLINE_SECONDS` / When `_request(url, deadline_at=...)` aufgerufen wird / Then bricht der Aufruf mit einer Ausnahme aus `(ProviderRequestError, httpx.HTTPError)` ab, und die tatsächlich verstrichene Wanduhrzeit liegt unter 0,9 Sekunden.
  - Test: Neuer Wächter in `tests/tdd/test_provider_request_deadline.py`, analog Scheibe A AC-1, mit `time.monotonic()` gemessen; ausdrücklich **keine** Aufrufzählung. `@pytest.mark.timeout(N)` gesetzt.

- **AC-2:** Given der ICON-EU-Pfad ruft `_request` direkt gegen `_HangingServer` mit auf 0,45 s gepatchtem `THUNDER_FETCH_DEADLINE_SECONDS` (ihrem einzigen Budget) / When `_request(url, deadline_at=...)` aufgerufen wird / Then bricht der Aufruf mit `(ProviderRequestError, httpx.HTTPError)` ab, und die verstrichene Zeit liegt unter 0,9 Sekunden.
  - Test: Analog AC-1, gegen `DwdEuDirectProvider`. `@pytest.mark.timeout(N)` gesetzt.

- **AC-3:** Given ein normal antwortender lokaler Server (kein Hang) / When `_request` für beide Dateien (`dwd.py` und `dwd_eu.py`) aufgerufen wird / Then liefert er unverändert Daten, bricht nicht vorzeitig ab, und die verstrichene Zeit bleibt unter 2,0 Sekunden.
  - Test: Muster `test_provider_request_deadline.py:351` (Normalfall-Gegenprobe), übertragen auf beide Provider. Pflichtbestandteil: ohne diese AC wäre ein Fix, der alles sofort abbricht, ebenfalls grün.

- **AC-4:** Given `THUNDER_FETCH_DEADLINE_SECONDS` ist auf 0,45 s gepatcht und `FETCH_DEADLINE_SECONDS` deutlich größer auf 5 s / When `fetch_thunder_signals_named` gegen `_HangingServer` aufgerufen wird / Then hält die tatsächlich verstrichene Zeit die GEWITTER-Frist ein (bleibt unter 0,9 Sekunden, nicht unter der größeren Grundpfad-Grenze), und der Aufruf endet mit dem bestehenden `ThunderSourceUnavailableError`-Vertrag aus #1492 S2a — **nicht** mit einem durchschlagenden `ProviderRequestError`.

  **Sachliche Korrektur dieser AC nach der Freigabe (2026-09-12, TDD-RED):** Die freigegebene Fassung verlangte „fail-soft `None`/unvollständige Reihe **statt** eine propagierte Ausnahme". Das ist für `dwd.py` faktisch falsch: `src/providers/dwd.py:510-511` wirft `ThunderSourceUnavailableError`, sobald `versucht > 0 and fehlgeschlagen == versucht` — gegen eine hängende Gegenstelle also immer, und das **absichtlich** (Kommentar `:504-507`, #1492 S2a: der Typ soll zum Aufrufer durchschlagen und wird bewusst NACH dem generischen `except Exception` geworfen). Selbst am Code nachgeprüft. Der Wächter fängt deshalb genau diesen Vertrag; das ist zugleich die Positivkontrolle, dass überhaupt ein echter Versuch hinausging. **AC-5 (`dwd_eu.py`) bleibt unverändert** — dort existiert dieser Wurf nicht (`grep` über beide Dateien: einzige Fundstelle ist `dwd.py:511`).
  - Test: Neuer Wächter in `test_provider_request_deadline.py`. Zusicherung ist ausschließlich die Wanduhr plus der fail-soft-Rückgabewert — **nicht** ein Ausnahmetyp, weil `_thunder_point` jede Ausnahme aus `_request` selbst abfängt (`dwd.py:372/392`). Mutations-Gegenprobe siehe Test-Plan-Abschnitt oben: Entfernt man das Durchreichen von `deadline_at` an der Gewitter-Aufrufstelle, überschreitet die verstrichene Zeit die 0,9-Sekunden-Grenze deutlich, bleibt aber unter der 5-Sekunden-Grenze — der Wächter muss dabei rot werden. `@pytest.mark.timeout(N)` gesetzt.

- **AC-5:** Given `THUNDER_FETCH_DEADLINE_SECONDS` (ICON-EUs einziges Budget) ist auf 0,45 s gepatcht / When `fetch_thunder_signals_named` gegen `_HangingServer` aufgerufen wird / Then hält die verstrichene Zeit diese Frist ein (unter 0,9 Sekunden) und liefert fail-soft eine unvollständige Reihe statt eine propagierte Ausnahme.
  - Test: Analog AC-4, ohne den Dual-Budget-Kontrast (nur ein Budget vorhanden). Zusicherung bleibt: Durchreichen von `deadline_at` über `_thunder_point` an `_request` funktioniert auch am einfachen Fall. `@pytest.mark.timeout(N)` gesetzt.

- **AC-6:** Given `_request` wird ohne den Parameter `deadline_at` aufgerufen / When der geteilte `before`-Hook feuert / Then setzt er die Frist selbst aus der providereigenen `_fetch_deadline_seconds()`-Methode — für `DwdDirectProvider` muss dieser Vorgabewert 180 s (`FETCH_DEADLINE_SECONDS`) sein, nie 150 s, sonst würde ein vergessenes Durchreichen den Gewitterpfad heimlich verkürzen.
  - Test: Gegen `_HangingServer`, `_request` ohne `deadline_at`-Argument aufgerufen, für beide Dateien — jeweils `elapsed <` der jeweils passenden Obergrenze aus AC-1/AC-2. Für `dwd.py` zusätzlich: der resultierende Vorgabewert entspricht nachweislich `FETCH_DEADLINE_SECONDS`, nicht `THUNDER_FETCH_DEADLINE_SECONDS`.

- **AC-7:** Given das Modul-Global `FETCH_DEADLINE_SECONDS` bzw. `THUNDER_FETCH_DEADLINE_SECONDS` wird zur Laufzeit per `monkeypatch` gesetzt / When `_request` aufgerufen wird / Then gilt der gepatchte Wert.
  - Test: Für beide Provider je ein Test, der die Konstante patcht und prüft, dass die Frist entsprechend reagiert (sehr kleiner Wert → sofortiger Abbruch trotz erreichbarem Server), analog Scheibe A AC-5.

- **AC-8:** Given der geteilte Baustein ist in `DwdDirectProvider` und `DwdEuDirectProvider` verdrahtet / When die Retry-Konfiguration des einen Providers verändert wird (z. B. `wait` gepatcht) / Then bleibt das Verhalten des anderen Providers unverändert — es existiert kein geteiltes `Retrying`-Objekt.
  - Test: Verhaltensbasiert (Laufzeit/Retry-Anzahl des unveränderten Providers bleibt gleich) plus die strukturelle Invariante `DwdDirectProvider._request.retry is not DwdEuDirectProvider._request.retry`, analog Scheibe A AC-6.

- **AC-9:** Given `tests/tdd/test_dwd_eu_thunder_time_budget.py` trägt nach dieser Änderung keinen `live`/`email`/`staging`-Marker mehr, und die Docstring-Behauptung „ein Laufzeit-Test misst die Maschine, nicht die Zeitgrenze" ist korrigiert / When ein normaler `uv run pytest --collect-only tests/tdd/test_dwd_eu_thunder_time_budget.py`-Lauf läuft / Then sammelt er beide vorhandenen Tests (`N > 0`), und beide laufen im Normallauf grün — der Zähl-Test bleibt erhalten und wird nicht gelöscht.
  - Test: `--collect-only`-Beleg im QA-Artefakt (Anzahl > 0), plus ein normaler Testlauf der Datei ohne `-m`-Override.

- **AC-10:** Given die in Messung M3 festgehaltene Regressions-Grundlinie (sechs benannte Testdateien, 43 passed / 1 vorbestehend failed) / When dieselben Dateien nach GREEN erneut laufen / Then bleibt das Ergebnis unverändert — der eine vorbestehende Fehlschlag (`test_dwd_thunder_signal_fetch.py::test_ac3_dauerhafter_serverfehler_liefert_leeres_ergebnis_statt_ausnahme`, M4) bleibt der einzige.
  - Test: Vollständiger Lauf der sechs Dateien nach Abschluss der Implementierung, Ergebnis im QA-Artefakt gegen die M3-Baseline verglichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieselbe Einordnung wie Scheibe A. ADR-0038 weist die Klasse „einzelne in
  sich unbegrenzt blockierende Schritte" #1448 zu und deckt sie selbst nicht ab; #2302 ist die
  dort ausgenommene Klasse. ADR-0047 Entscheidung 6 bleibt unberührt — keine Restzeit-Weitergabe
  zwischen Provider-Quellen. ADR-0018 (Fallback ohne Kaschieren) verlangt, dass ein
  Fristabbruch als solcher erkennbar bleibt; am Grundpfad bleibt dafür
  `ProviderRequestError`/`httpx.HTTPError` der Abbruchmechanismus, am Gewitterpfad bleibt der
  bereits bestehende, unveränderte fail-soft-Vertrag (`None`/unvollständige Reihe) in Kraft.

## Changelog

- 2026-09-12: Initial spec created (Scheibe B von #2302)
