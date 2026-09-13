---
entity_id: fix_2302_s3_geosphere_zeitbudget
type: module
created: 2026-09-13
updated: 2026-09-13
status: draft
version: "1.0"
tags: [provider, zeitbudget, deadline, retry, httpx, tenacity, geosphere, snowgrid, nwp]
---

# fix_2302_s3_geosphere_zeitbudget

## Approval

- [x] Approved — PO-Freigabe 2026-09-13

## Purpose

`src/providers/geosphere.py` (AROME/NWP + SNOWGRID) prüft sein Zeitbudget heute gar nicht.
`_request` hat `stop_after_attempt(5)`, kein `before`-Hook, keinen Frist-Stop und ruft
`self._client.get(url)` **ohne** `timeout=` auf (Client-Default 30 s). Eine Gegenstelle, die
die Verbindung annimmt und dann schweigt, kann die Retry-Kette rechnerisch offenhalten, ohne
dass irgendetwas das je bemerkt. Diese Spec überträgt den in Scheibe A gebauten geteilten
Baustein `src/providers/http.py` auf `geosphere.py` — dieselbe Mechanik wie Scheibe B
(`dwd.py`/`dwd_eu.py`), diesmal als letzte der drei Wetterquellen.

Diese Spec beschreibt ausschließlich **Scheibe C** von #2302 (Epic #2257 Block 2). Scheibe A
(`src/providers/http.py`, Commit `c31a09a6`) und Scheibe B (`dwd.py`/`dwd_eu.py`, Commit
`83726174`) sind bereits umgesetzt und werden hier nicht verändert.

## Source

- **File:** `src/providers/geosphere.py`
- **Identifier:** `GeoSphereProvider._request`, `GeoSphereProvider.fetch_nwp_forecast`,
  `GeoSphereProvider.fetch_snowgrid`, `GeoSphereProvider.fetch_combined`
  (Schicht: Python-Core, `src/providers/`)

## Estimated Scope

- **LoC:** Produktiv ~+55–75; Tests Ziel ≤ ~300 (docstring-schwerer Stil wie Scheibe A/B — bei
  Überschreitung ist `workflow.py set-field loc_limit_override 500` der dokumentierte Weg,
  nicht Scope-Schnitt)
- **Files:** 2
- **Effort:** medium

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/providers/geosphere.py` | MODIFY | `time`-Import + Import der Bausteine aus `providers.http` (`make_deadline_before_hook`, `stop_at_deadline`, `capped_timeout_or_raise`); neues Modul-Global `FETCH_DEADLINE_SECONDS = 180.0`; neue Accessor-Methode `_fetch_deadline_seconds`; `_request` bekommt `stop=stop_after_attempt(RETRY_ATTEMPTS) \| stop_at_deadline`, `before=make_deadline_before_hook("_fetch_deadline_seconds")`, ein neues keyword-only `deadline_at`-Argument, einen `capped_timeout_or_raise`-Kopf-Check und `timeout=request_timeout` am `self._client.get`-Aufruf; `fetch_nwp_forecast` und `fetch_snowgrid` nehmen ein optionales `deadline_at` entgegen und reichen es nur an `_request` durch (keine eigene Fristbildung); `fetch_combined` bildet die Frist **einmal** und reicht sie an beide (NWP + SNOWGRID) durch; `fetch_snowgrid` fängt zusätzlich `ProviderRequestError` und loggt `OUTCOME_UNAVAILABLE` statt die Ausnahme durchzulassen |
| `tests/tdd/test_provider_request_deadline.py` | MODIFY | neue GeoSphere-Wächter (Parallelstruktur zu den A/B-Wächtern) + ein Zwei-Pfad-Testserver, dessen Handler über den Datensatz-Teilstring in `self.path` unterscheidet (`nwp-v1-1h-2500m` vs. `snowgrid_cl-v2-1d-1km`) |
| `src/providers/http.py` | — | unverändert |

Kein drittes Modul im Scope — anders als Scheibe B (zwei Provider-Dateien) hat GeoSphere nur
eine Datei mit HTTP-Retry-Logik.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/http.py` (`make_deadline_before_hook`, `stop_at_deadline`, `capped_timeout_or_raise`) | Modul (Scheibe A) | geteilter Zeitbudget-Baustein — wird angewandt, nicht verändert |
| `src/providers/dwd.py:321-369` | Vorbild | Anwendungsmuster (Accessor, Dekorator-Zusatz, Kopf-Check, `deadline_at`-Durchreichen) — Scheibe C überträgt es strukturell, mit einer Erweiterung (SNOWGRID-Fail-soft-Fänger) |
| `tests/tdd/test_provider_request_deadline.py` (Scheiben A/B, ungemarkert, in der CI-Ampel) | Testdatei | Heimat der neuen Wächter; `_HangingServer` und Normalfall-Muster werden geteilt, nicht kopiert |
| `docs/specs/modules/fix_2302_s2_dwd_zeitbudget.md` | Vorgänger-Spec | Formvorbild für AC-Sprache und Baustein-Vertrag — wird nicht editiert |
| `docs/specs/modules/feat_1992_geosphere_health_amendment.md` (AC-3) | Vorbestehender Vertrag | SNOWGRID-Fehler lässt `fetch_combined` nie scheitern — diese Spec verschärft ihn um Frist-Fehler, hebt ihn nicht auf |
| `src/providers/regional_stubs.py:63-101` (`GeoSphereDirectProvider`) | Downstream | einziger Weg von GeoSphere in den Alarm-Pfad (`at_direct`); reicht `ProviderRequestError` unübersetzt durch |
| `src/providers/openmeteo.py:482` (`_enrich_snow`) | Downstream | ruft `fetch_snowgrid` direkt, fängt `except Exception: pass` — profitiert vom neuen `ProviderRequestError`-Fänger in `fetch_snowgrid` selbst |

## Implementation Details

### Der Konflikt D2 ↔ #1992 AC-3 — aufgelöst, kein neues ADR nötig

D2 (Entscheid aus `docs/context/fix-2302-provider-zeitbudget.md:692-703`) fordert: bei
Fristüberschreitung `ProviderRequestError`, kein stilles Leerergebnis. #1992 AC-3 fordert:
ein SNOWGRID-Fehler lässt `fetch_combined` nie scheitern. Beide gelten zugleich:

- **ADR-0018** (`docs/adr/0018-provider-fallback-ohne-kaschieren.md:11,22`) verbietet Ausweichen
  *ohne Sichtbarkeit*, nicht fail-soft an sich. D2s „kein stilles Leerergebnis" meint die
  **zurückgegebene Vorhersage** (Temperatur/Wind/Schnee-Grunddaten), nicht jeden internen Zweig.
- **NWP-Frist erschöpft** → `ProviderRequestError`/httpx-Fehler geht durch `fetch_nwp_forecast`,
  `fetch_combined`, `fetch_forecast` und `GeoSphereDirectProvider` (`regional_stubs.py:80-101`)
  ungefangen durch — nie ein leeres oder erfundenes Ergebnis.
- **SNOWGRID-Frist erschöpft** → bleibt fail-soft (#1992 AC-3, Wächter
  `test_snowgrid_enrichment_health.py:262` unberührt), aber **sichtbar**:
  `fetch_snowgrid` fängt künftig zusätzlich `ProviderRequestError` neben den bereits gefangenen
  httpx-Fehlertypen und loggt `log_enrichment_call(PATH_SNOWGRID, OUTCOME_UNAVAILABLE)` →
  `diagnostics/enrichment_calls.jsonl` → `/api/scheduler/status` `enrichment_health`.
  `fetch_combined` fängt einen durchschlagenden SNOWGRID-Fehler zusätzlich schon heute
  (`:622-631`, `except Exception`) und loggt ihn ebenfalls — diese Hülle bleibt bestehen und
  bekommt durch den `fetch_snowgrid`-eigenen Fänger eine zweite, granularere Journal-Zeile für
  den Direktaufruf-Pfad (`openmeteo._enrich_snow`).
- **Folge für die Tests:** Die Serien-Zusicherung für `fetch_combined` ist eine
  **Wanduhr-Obergrenze** plus Journal-Eintrag, keine Ausnahme (AC-3).

### D2 in sich widersprüchlich beim Wolken-Abruf — aufgelöst

`_fetch_openmeteo_clouds` (`:508`) bleibt **unberührt**: ein einzelner Versuch, kein Retry,
fest 10 s, fail-soft (`except Exception: return {}`). Der einzige Alarm-Pfad-Zugang
(`GeoSphereDirectProvider.fetch_combined`, `regional_stubs.py:88-95`) ruft ohnehin
`include_cloud_layers=False`. Eine gemeinsame Frist dort brächte keinen zusätzlichen Schutz,
nur Code- und Test-LoC. Damit gilt für `fetch_combined` mit Wolken-Anreicherung eine
**Obergrenze von ungefähr Frist + 10 s** — als ausdrückliche Grenze unten festgehalten.

### `_request` — die Kernänderung

```
@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS) | stop_at_deadline,
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=retry_if_exception(_is_retryable_error),
    before=make_deadline_before_hook("_fetch_deadline_seconds"),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _request(self, endpoint, lat, lon, parameters, start=None, end=None,
             *, deadline_at: Optional[float] = None) -> Dict[str, Any]:
```

`deadline_at` wird **keyword-only** (`*`), strenger als das Vorbild in `dwd.py:342` — dort
genügt eine einfache Optional-Position, weil `_request` dort nur `url` als weiteres Argument
hat. `geosphere._request` hat sechs bestehende positionale Parameter; ohne `*` könnte ein
künftiger Aufruf `deadline_at` versehentlich positional an `end` vorbeischieben, ohne dass der
`before`-Hook (der ausschließlich `retry_state.kwargs.get("deadline_at")` liest,
`providers/http.py:51`) es je sehen würde. Kopf-Check und `get`-Aufruf analog `dwd.py:358-365`:
`capped_timeout_or_raise(provider_name=self.name, base_timeout=TIMEOUT, deadline_at=deadline_at,
budget_label="FETCH_DEADLINE_SECONDS", budget_seconds=FETCH_DEADLINE_SECONDS)`, danach
`self._client.get(url, timeout=request_timeout)` statt bisher `self._client.get(url)`.

Neue Accessor-Methode: `_fetch_deadline_seconds(self) -> float: return FETCH_DEADLINE_SECONDS`
— GeoSphere hat, anders als `dwd.py`, nur **ein** Budget (kein separater Gewitterpfad über
`_request`; `fetch_thunder_signals_named` läuft laut eigenem Docstring „BEWUSST ohne
`self._request()` (kein `@retry`)", `:412`, unberührt von dieser Spec), darum genügt ein
einziger Accessor ohne Dual-Fall-Unterscheidung.

### Durchreichen

- `fetch_nwp_forecast` (`:329-349`) nimmt ein optionales keyword-only `deadline_at` entgegen
  und reicht es **nur durch** an `_request(..., deadline_at=deadline_at)` (analog `_fetch_series`
  in `dwd.py`). Sie bildet **keine** eigene Frist — kommt `None` an, bildet der `before`-Hook
  die Standardfrist; eine lokal gebildete Frist würde die Serienfrist aus `fetch_combined`
  aushebeln (AC-3).
- `fetch_snowgrid` (`:351-382`) nimmt `deadline_at` ebenso optional entgegen und reicht es nur durch;
  zusätzlich fängt der bestehende `except`-Block künftig auch `ProviderRequestError` (neben
  `httpx.HTTPStatusError`, `httpx.TimeoutException`, `httpx.RequestError`) und loggt
  `OUTCOME_UNAVAILABLE` statt die Ausnahme durchzulassen.
- `fetch_combined` (`:588-660`) bildet die Frist **einmal** vor dem NWP-Aufruf und reicht
  dasselbe `deadline_at` an `fetch_nwp_forecast` **und** — sofern `include_snow` und `ts.data`
  nicht leer sind — an `fetch_snowgrid` durch. Fehlt das Durchreichen an einer der beiden
  Stellen, bekäme der jeweilige Aufruf über den `before`-Hook automatisch ein frisches
  180-s-Fenster statt der verbleibenden Serienfrist (Mutations-Ziel, siehe Test Plan).
- `fetch_nowcast` (`:477-506`) ruft bereits `self._request(ENDPOINTS["nowcast"], ...)`
  (`:499`) **ohne** `deadline_at` — sie bekommt dadurch automatisch, ohne Aufrufstellen-
  Änderung, ein frisches 180-s-Fenster über den `before`-Hook-Vorgabewert. Das ist beabsichtigt
  (derselbe Mechanismus wie bei jedem unbenannten Einzelaufruf) und wird unten unter „Was sich
  für Nutzer ändert" bzw. Grenzen benannt, nicht stillschweigend übergangen.
- `fetch_thunder_signals_named` (`:398`) und `_fetch_openmeteo_clouds` (`:508`) bleiben beide
  unberührt — sie laufen nicht über `_request`.

### Ohne übergebenes `deadline_at`

Analog Scheibe A/B: der `before`-Hook löst `_fetch_deadline_seconds` erst **zur Aufrufzeit**
auf (`providers/http.py:36-39`, Namensauflösung statt Werteinfrieren), damit ein
`monkeypatch` von `FETCH_DEADLINE_SECONDS` im Test wirkt. Default im Code bleibt 180,0 s.

## Expected Behavior

- **Input:** Aufruf von `_request` (direkt oder über `fetch_nwp_forecast`/`fetch_snowgrid`/
  `fetch_combined`/`fetch_nowcast`), mit oder ohne explizit übergebenes `deadline_at`.
- **Output:** Bei einer hängenden Gegenstelle bricht der NWP-Pfad spätestens bei erreichter
  Frist mit einer Ausnahme aus `(ProviderRequestError, httpx.HTTPError)` ab — nie ein leeres
  oder erfundenes Vorhersage-Ergebnis. Der SNOWGRID-Pfad bricht innerhalb derselben (bei
  `fetch_combined`: gemeinsamen) Frist ab und liefert dabei seinem bestehenden
  fail-soft-Vertrag folgend `(None, None)` zurück, sichtbar geloggt als
  `enrichment_health`-Journal-Eintrag. Ein normal antwortender Server liefert unverändert
  Daten.
- **Side effects:** `fetch_nowcast` bekommt ab jetzt ebenfalls einen (bisher nicht
  vorhandenen) 180-s-Deckel, ohne dass eine Aufrufstelle geändert wurde. `TIMEOUT` und
  `FETCH_DEADLINE_SECONDS` bleiben Modul-Globals in `geosphere.py`; `_fetch_openmeteo_clouds`
  bleibt bei ihrem eigenen festen 10-s-Timeout.

## Was sich für Nutzer ändert

GeoSphere ist der österreichische Wetterdienst. Wir nutzen ihn als Ausweichquelle, wenn
Open-Meteo für einen Ort in Österreich komplett ausfällt (darüber hängt er am Alarm-Pfad),
außerdem für Schneehöhen (SNOWGRID) und den INCA-Nowcast. Als letzte der Wetterquellen hatte
er **gar kein** Zeitbudget: Eine Gegenstelle, die die Verbindung annimmt und dann schweigt,
konnte einen einzelnen Abruf samt Wiederholversuchen rechnerisch rund 390 Sekunden
offenhalten. Nach diesem Fix gilt wie bei Open-Meteo, Météo-France und DWD eine feste
Obergrenze von 180 Sekunden je Abruf-Kette, Wartepausen eingerechnet.

- **Normalfall** (Gegenstelle antwortet wie gewohnt): keine Änderung.
- **Hauptvorhersage überschreitet die Frist:** Der Abruf scheitert mit einem Fehler — es wird
  nie eine leere oder unvollständige Vorhersage ausgegeben (ADR-0018).
- **Nur die Schneehöhen-Anreicherung überschreitet die Frist:** Die Vorhersage kommt ohne
  Schneehöhe (so wie heute schon bei jedem anderen SNOWGRID-Ausfall), und der Ausfall wird im
  Betriebsstatus (`/api/scheduler/status`) mitgezählt. Neu sichtbar wird er dabei auch dort,
  wo Open-Meteo die Schneehöhe bei GeoSphere nachfragt — dieser Weg hat einen solchen Abbruch
  bisher stumm geschluckt.

## Grenzen / Known Limitations

- **at_direct bekommt ein frisches Fenster.** Die `at_direct`-Weiche (`regional_stubs.py`)
  erreicht GeoSphere erst nach der Open-Meteo-Kandidatenschleife und reicht deren Restfrist
  nicht durch — GeoSphere bekommt dort ein **frisches** 180-s-Fenster über den `before`-Hook-
  Vorgabewert. Gegen `ALERT_RUN_DEADLINE_SECONDS = 90` schützt ein 180-s-Budget ohnehin nicht
  (gilt genauso für dwd/meteofrance, ist kein neues Problem dieser Scheibe).
- **Wolken-Abruf außerhalb der gemeinsamen Frist.** `_fetch_openmeteo_clouds` bleibt bei ihrem
  eigenen festen 10-s-Timeout, unabhängig von `FETCH_DEADLINE_SECONDS`. Obergrenze für
  `fetch_combined` mit `include_cloud_layers=True` damit ≈ Frist + 10 s.
- **Tröpfel-Fall (D6) bleibt ungedeckt.** Eine einzelne, beliebig lang hingezogene Antwort
  (Byte für Byte, jedes einzeln innerhalb des httpx-Timeouts) wird vom geteilten Baustein
  nicht erkannt — httpx hat dafür keinen Parameter. Eigenes Ticket, kein Teil dieser Scheibe.
- **`GeoSphereDirectProvider` meldet `provider="geosphere"`.** Ein Frist-Fehler auf dem
  `at_direct`-Pfad trägt weiterhin die Provider-Kennung `"geosphere"` statt `"at_direct"`
  (vorbestehendes Verhalten, nicht Gegenstand dieser Scheibe).
- **`fetch_nowcast` bekommt erstmals einen Deckel**, ohne dass eine Aufrufstelle geändert
  wurde — bewusste Nebenwirkung des `before`-Hook-Vorgabewerts, nicht durch eine AC
  abgedeckt.
- **Nie beobachtet.** Der Nachweis ist Konstruktion gegen `_HangingServer`; es gibt keinen
  Live-Vorfall zu reproduzieren.

## Test Plan

Given/When/Then der einzelnen Zusicherungen steht ausschließlich in `## Acceptance Criteria`
unten — dieser Abschnitt hält die Rahmenbedingungen fest, die für alle ACs gelten.

### Heimat und Teilung

Alle neuen Wanduhr-Wächter gehören in `tests/tdd/test_provider_request_deadline.py`
(Scheiben A/B, ungemarkert, in der CI-Ampel). `_HangingServer` und die Normalfall-Gegenprobe
werden von dort **geteilt, nicht kopiert**.

### Zwei-Pfad-Testserver für die Serienfrist (AC-3)

Ein `ThreadingHTTPServer`, dessen Handler über den **Datensatz-Teilstring in `self.path`**
unterscheidet: enthält der Pfad `"nwp-v1-1h-2500m"` (`ENDPOINTS["nwp"]`), antwortet er nach
0,6 s mit einem minimalen GeoJSON-Rumpf (`timestamps` + mindestens ein Eintrag unter
`features[0].properties.parameters.t2m.data`, damit `_parse_nwp_response` ein nicht-leeres
`ts.data` liefert — **das ist Voraussetzung dafür, dass `fetch_combined` den SNOWGRID-Abruf
überhaupt versucht**, `geosphere.py:621` prüft `if include_snow and ts.data`); enthält der
Pfad `"snowgrid_cl-v2-1d-1km"` (`ENDPOINTS["snowgrid"]`), hängt er. `geosphere.BASE_URL` wird
per `monkeypatch` auf die lokale Server-Adresse gesetzt. Aufruf mit
`include_cloud_layers=False` (wie der einzige Alarm-Pfad-Aufrufer, `regional_stubs.py:88-95`)
— sonst würde der reale `_fetch_openmeteo_clouds`-Abruf (fester 10-s-Timeout, echtes Netz) in
das gemessene Fenster hineinfallen und die Schwelle verfälschen bzw. den Wächter
netzabhängig machen. Die AC-3-Assertion prüft **drei** Dinge zusammen, nicht nur die Wanduhr:
`ts.data` ist nicht leer (Beleg, dass der NWP-Abruf wirklich gelang), die Datenpunkte tragen
`snow_depth_cm is None` (Beleg, dass SNOWGRID wirklich abgebrochen ist, nicht übersprungen
wurde), und das Journal enthält einen `snowgrid`/`unavailable`-Eintrag.

### Wartepausen-Deckel (AC-2)

Wie in Scheibe A/B: `TIMEOUT` klein gepatcht (0,5), **explizit**
`monkeypatch.setattr(GeoSphereProvider._request.retry, "wait", wait_fixed(1.0))` gesetzt
(F-ADV1-Klasse: eine gemeinsame Rüst-Helferfunktion darf `wait` nie unbemerkt neutralisieren).
`.retry` ist ein einziges, an der unbound Methode hängendes `Retrying`-Objekt — derselbe
Patch-Pfad, den `test_issue_1142_geosphere_direct_fallback.py:218` bereits für `retry.wait`
verwendet; der Patch wird **pro Test** zurückgesetzt (`monkeypatch`-Fixture-Scope), nie global.

### Timeout-Absicherung je Hänger-Test

`pyproject.toml:69` setzt global `timeout = 30`. Jeder Test gegen `_HangingServer` trägt
zusätzlich ein eigenes `@pytest.mark.timeout(N)` mit `N` oberhalb der erwarteten
Fehlschlag-Laufzeit.

### Regressions-Grundlinie

Vor der ersten Code-Änderung wird ein Lauf der in AC-8 genannten Testdateien als Grundlinie
gemessen (Anzahl passed/failed, Namen etwaiger vorbestehender Fehlschläge). Dieselbe Bilanz
muss nach GREEN unverändert bestehen — die genaue Zahl wird erst im TDD-RED-Lauf festgestellt,
nicht hier vorweggenommen.

### Mutations-Gegenprobe (PFLICHT)

Entfernt man das Durchreichen von `deadline_at` an der SNOWGRID-Aufrufstelle in
`fetch_combined`, MUSS der AC-3-Wächter rot werden — die verstrichene Zeit läuft dann gegen
den `before`-Hook-Vorgabewert (180 s bzw. den gepatchten `FETCH_DEADLINE_SECONDS`-Wert) statt
gegen die enge Serienfrist (erwartete Größenordnung laut Analyse: korrekt ≈ 1,0–1,1 s, Mutation
„`deadline_at` nicht an SNOWGRID" ≈ 1,6 s, Mutation „`stop_at_deadline` entfernen" ≈ 3 s). Im
Docstring des Tests explizit benennen, welche Mutation gefangen werden soll.

## Acceptance Criteria

- **AC-1:** Given `_request` wird direkt gegen einen `_HangingServer` aufgerufen, `FETCH_DEADLINE_SECONDS` ist per Monkeypatch auf 0,45 Sekunden gesetzt und `TIMEOUT` bleibt bei 5,0 Sekunden (über der Frist) / When `_request(endpoint, lat, lon, parameters)` ohne explizites `deadline_at` läuft / Then bricht der Aufruf mit einer Ausnahme aus `(ProviderRequestError, httpx.HTTPError)` ab, und die tatsächlich verstrichene Wanduhrzeit liegt unter 0,9 Sekunden.
  - Test: Neuer Wächter in `tests/tdd/test_provider_request_deadline.py`, analog Scheiben-A/B-AC-1, mit `time.monotonic()` gemessen, ausdrücklich keine Aufrufzählung. `@pytest.mark.timeout(N)` gesetzt.

- **AC-2:** Given `TIMEOUT` ist per Monkeypatch auf 0,5 Sekunden gesetzt, `FETCH_DEADLINE_SECONDS` auf 0,45 Sekunden, und `GeoSphereProvider._request.retry.wait` ist explizit auf `wait_fixed(1.0)` gepatcht / When `_request` gegen `_HangingServer` läuft / Then liegt die verstrichene Zeit zwischen 0,2 und unter 0,9 Sekunden — die Wartepause selbst wird von der Frist gedeckelt, nicht nur die HTTP-Versuche.
  - Test: Mutations-relevanter Wächter (F-ADV1-Klasse); Patch **im Test selbst**, nicht in einer geteilten Rüst-Funktion. `@pytest.mark.timeout(N)` gesetzt.

- **AC-3:** Given `fetch_combined(lat, lon, include_cloud_layers=False)` läuft gegen einen Zwei-Pfad-Server, dessen NWP-Endpunkt nach 0,6 Sekunden mit gültigem, nicht-leerem GeoJSON antwortet und dessen SNOWGRID-Endpunkt hängt, `FETCH_DEADLINE_SECONDS` ist auf 1,0 Sekunden gepatcht, `TIMEOUT` auf 10,0, die Wartepause ist wie in AC-2 explizit gesetzt / When der Aufruf durchläuft / Then liegt die gesamte Wanduhrzeit unter 1,35 Sekunden, `ts.data` ist nicht leer, alle Datenpunkte tragen `snow_depth_cm is None`, und das `enrichment_health`-Journal enthält einen Eintrag mit Pfad `snowgrid` und Ausgang `unavailable`.
  - Test: Zwei-Pfad-`ThreadingHTTPServer`, Unterscheidung über den Datensatz-Teilstring in `self.path`. `geosphere.BASE_URL` per Monkeypatch umgeleitet. Journal-Prüfung über die Test-Datenwurzel-Isolation, keine echte Datenwurzel. Mutations-Gegenprobe siehe Test-Plan-Abschnitt. `@pytest.mark.timeout(N)` gesetzt.

- **AC-4:** Given `FETCH_DEADLINE_SECONDS` ist auf 0,45 Sekunden gepatcht und der lokale Server für den NWP-Endpunkt ist ein `_HangingServer` (keine Möglichkeit, je eine Antwort zu bekommen) / When `fetch_combined` aufgerufen wird — derselbe Pfad, den `at_direct` nutzt (`regional_stubs.py:88-95`) — / Then wirft der Aufruf eine Ausnahme aus `(ProviderRequestError, httpx.HTTPError)`, liefert kein leeres oder unvollständiges `NormalizedTimeseries`-Ergebnis, und die verstrichene Wanduhrzeit liegt unter 0,9 Sekunden.
  - Test: Neuer Wächter, belegt die D2-Seite des aufgelösten Konflikts (NWP-Frist-Fehler geht durch, wird nie stillschweigend zu einem leeren Ergebnis). Ausdrücklich `fetch_combined`, nicht `fetch_forecast` — Letztere übersetzt jeden httpx-Fehler auf `ProviderRequestError` (`:269-274`) und würde den Ausnahmetyp allein nicht mehr zeigen, über welchen Pfad die Frist erschöpft wurde. `@pytest.mark.timeout(N)` gesetzt.

- **AC-5:** Given ein normal antwortender lokaler GeoJSON-Server (kein Hang), Standardfrist unverändert / When `fetch_nwp_forecast` bzw. `_request` aufgerufen wird / Then liefert er unverändert Daten, bricht nicht vorzeitig ab, und die verstrichene Zeit bleibt unter 2,0 Sekunden.
  - Test: Normalfall-Gegenprobe (Muster aus Scheibe A/B, geteilt). Pflichtbestandteil: ohne diese AC wäre ein Fix, der alles sofort abbricht, ebenfalls grün.

- **AC-6:** Given `_request` wird ohne den Parameter `deadline_at` aufgerufen, `FETCH_DEADLINE_SECONDS` ist zur Laufzeit per Monkeypatch auf einen sehr kleinen Wert gesetzt / When der geteilte `before`-Hook feuert / Then setzt er die Frist selbst aus `_fetch_deadline_seconds()`, und der gepatchte Wert wirkt sofort — auch ohne dass `_request` neu dekoriert oder das Modul neu geladen wird. Zusätzlich gilt im unveränderten Modul ohne Patch: `geosphere.FETCH_DEADLINE_SECONDS == 180.0`.
  - Test: Gegen `_HangingServer`, `_request` ohne `deadline_at`-Argument, Vorgabewert-Nachweis analog Scheiben-A/B-AC-5/AC-7, plus eine reine Wertprüfung der unveränderten Modul-Konstante.

- **AC-7:** Given `fetch_snowgrid` wird direkt aufgerufen (der Pfad, den `openmeteo._enrich_snow` nutzt), `FETCH_DEADLINE_SECONDS` ist auf 0,45 Sekunden gepatcht und der SNOWGRID-Endpunkt hängt / When der Aufruf durchläuft / Then liefert `fetch_snowgrid` `(None, None)` zurück, ohne eine Ausnahme zu werfen, und das `enrichment_health`-Journal enthält einen Eintrag mit Pfad `snowgrid` und Ausgang `unavailable`.
  - Test: Neuer Wächter, belegt den zusätzlichen `ProviderRequestError`-Fänger in `fetch_snowgrid` — ohne ihn würde der Direktaufruf-Pfad (`_enrich_snow`) einen Frist-Fehler stumm über `except Exception: pass` verschlucken, aber ohne Journal-Eintrag.

- **AC-8:** Given eine vor der ersten Code-Änderung gemessene Regressions-Grundlinie aus `tests/tdd/test_snowgrid_enrichment_health.py`, `tests/tdd/test_issue_1142_geosphere_direct_fallback.py`, `tests/test_geosphere.py`, `tests/tdd/test_wegpunkt_hoehe_im_request.py` und den bestehenden Tests in `tests/tdd/test_provider_request_deadline.py` / When dieselben Dateien nach GREEN erneut laufen (ungemarkerte Tests mit `-m ''`, Live-Tests mit echtem Netz ausgenommen) / Then bleibt die Bilanz (Anzahl passed/failed, Namen etwaiger vorbestehender Fehlschläge) gegenüber der Grundlinie unverändert.
  - Test: Vollständiger Lauf der genannten Dateien vor und nach der Implementierung, Ergebnis im QA-Artefakt gegen die vorher gemessene Grundlinie verglichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieselbe Einordnung wie Scheibe A/B. ADR-0038 weist die Klasse „einzelne in
  sich unbegrenzt blockierende Schritte" (#1448) zu und deckt sie selbst nicht ab; #2302 ist
  die dort ausgenommene Klasse. ADR-0047 Entscheidung 6 bleibt unberührt — keine
  Restzeit-Weitergabe zwischen Provider-Quellen; `at_direct` bekommt bewusst ein frisches
  Fenster (siehe Grenzen). ADR-0018 (Fallback ohne Kaschieren) verlangt, dass ein Fristabbruch
  als solcher erkennbar bleibt: am NWP-Pfad bleibt `ProviderRequestError`/`httpx.HTTPError` der
  Abbruchmechanismus (nie ein stilles Leerergebnis), am SNOWGRID-Pfad bleibt der bestehende,
  durch #1992 AC-3 geforderte fail-soft-Vertrag in Kraft — verschärft um einen sichtbaren
  Journal-Eintrag statt eines stummen Verschluckens.

## Changelog

- 2026-09-13: Initial spec created (Scheibe C von #2302)
- 2026-09-13: Implementiert (Scheibe C), Adversary VERIFIED
