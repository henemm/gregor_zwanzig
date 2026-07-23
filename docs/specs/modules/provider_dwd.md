---
entity_id: provider_dwd
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [providers, dwd, icon-d2, openmeteo, reliability, fallback, routing, briefing]
workflow: feature-1144-dwd-de
---

# Cross-Provider-Fallback — echter DWD-ICON-D2-Direktprovider für DE (#1144, Slice 3/4 von Epic #1127)

## Approval

- [x] Approved (PO „go" 2026-07-23)

## Purpose

Der in #1141 verdrahtete Stub `de_direct` (wirft immer `ProviderNotImplementedError`) wird durch einen **echten** DWD-Provider ersetzt, damit der Cross-Provider-Fallback im Total-Ausfall-Fall für Koordinaten in Deutschland tatsächlich Wetterdaten liefert statt weiterhin den Original-Fehler durchzureichen. Der neue Provider ruft die öffentliche ICON-D2-Open-Data-API (`opendata.dwd.de`, 2,2-km-Gitter) direkt ab, liest die GRIB2-Rohdaten mit dem bereits vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue Dependency, #1143) nach Entpacken des `.bz2`-Containers (Python-Stdlib `bz2`), und normalisiert sie auf `t2m_c`/`wind10m_kmh`/`precip_1h_mm`. Mit diesem Slice ist nach #1141/#1142/#1143 kein Regions-Stub in `regional_stubs.py` mehr offen — alle drei Regionen (AT/FR/DE) haben einen echten Direktprovider.

## Source

- **File:** `src/providers/dwd.py` (Python-Core / Domain-Backend) — CREATE. Neue Klasse `DwdDirectProvider`, Vorlage `src/providers/meteofrance.py` (Retry-Muster, httpx→`ProviderRequestError`-Übersetzung, `_vector_to_speed_kmh`, `_read_point_value`-Pixel-Lookup via rasterio, `FETCH_DEADLINE_SECONDS`-Zeitbudget), zusätzlich `bz2.decompress()` vor `rasterio.open()` (ICON-D2-Dateien liegen als `.grib2.bz2` vor, MeteoFrance-WCS lieferte unkomprimiertes GRIB2 direkt).
- **File:** `src/providers/regional_stubs.py:102` — `make_de_direct` (`partial(RegionalStubProvider, "de_direct")`) wird entfernt; Registry-Key `de_direct` zeigt stattdessen auf `DwdDirectProvider` aus `dwd.py`. Modul-Docstring (Zeile 18: „Der verbleibende reale Provider landet in #1144") wird obsolet — nach diesem Slice bleibt kein offener Regions-Stub mehr, entsprechend fortgeschrieben.
- **File:** `src/providers/base.py:183-188` — `_load_providers()`: `register_provider("de_direct", make_de_direct)` wird auf `register_provider("de_direct", DwdDirectProvider)` umgestellt (Import aus `providers.dwd` statt `providers.regional_stubs`); `at_direct`/`fr_direct` bleiben unverändert.
- **File:** `src/app/models.py:22-31` — `Provider`-Enum um `DWD = "DWD"` erweitert (analog `METEOFRANCE`), für `ForecastMeta.provider` im neuen Provider.
- **File:** `src/providers/region_routing.py:35` — DE-Box (`46.3–55.1/5.8–15.1`... aktuell `_RegionBounds("DE", 47.2, 55.1, 5.8, 15.1, "de_direct")`) voraussichtlich unverändert — empirisch gegen die ICON-D2-Domäne zu bestätigen (s. Known Limitations), keine Vorab-Fixierung.
- **File:** `docs/reference/decision_matrix.md` — `de_direct`-Zeile von „Stub" auf „ICON-D2-Open-Data-Direktprovider (DWD)" fortgeschrieben.

> **Schicht-Hinweis:** Alle Änderungen liegen in Python-Core (`src/providers/`, `src/app/models.py`). Keine Go-API-Änderung, kein Frontend-Bezug.

## Estimated Scope

- **LoC:** ~180–250 Produktions-LoC (neuer Provider ist der Löwenanteil; Registry/Enum-Änderungen sind Ein- bis Wenig-Zeiler) — nahe/am 250-LoC-Workflow-Limit. Haupttreiber gegenüber #1143 ist zusätzlich der `bz2`-Entpack-Schritt und die Precip-Differenzbildung (zwei Zeitschritte statt Einzelwert). **Kein Override wird hier vorweggenommen:** sollte der Parser das Limit reißen, ist eine Scheibung (Parser-MVP T2M+Wind zuerst, Precip als Folge-Slice, oder reduzierter Horizont) der richtige Weg — Entscheidung liegt beim PO im Implementierungsschritt, nicht in dieser Spec.
- **Files:** 1 CREATE (`dwd.py`) + 3 MODIFY (`regional_stubs.py`, `base.py`, `models.py`) + ggf. `region_routing.py` falls die Coverage-Prüfung eine Box-Anpassung ergibt + `docs/reference/decision_matrix.md` (zählt nicht zum LoC-Limit) + 1 Testdatei mit ICON-D2-GRIB2-Fixtures.
- **Effort:** medium-high (GRIB2-Parsing via rasterio ist gelöst, #1143-Vorlage; `bz2`-Entpacken, Precip-Differenzbildung über zwei Zeitschritte und höheres Requestvolumen auf einem bislang in diesem Projekt nicht produktionsgetesteten Backend sind neu).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MeteoFranceDirectProvider._request` / `_is_retryable_error` (meteofrance.py:98-104, 163-185) | function | Vorlage für tenacity-Retry (500/502/503/504 + Connection-Errors, 5 Versuche, 2-60s Backoff) und httpx→`ProviderRequestError`-Übersetzung im neuen Provider |
| `_vector_to_speed_kmh` (meteofrance.py:107-111) | function | Muster für U/V-Wind-Vektor → km/h (Betrag * 3,6, gerundet auf 1 Nachkommastelle); für ICON-D2-U/V-Komponenten identisch übernommen |
| `_read_point_value` (meteofrance.py:128-138) | function | Muster für rasterio-Pixel-Lookup an (lat, lon) aus GRIB2-Rohbytes via `MemoryFile`; wird im neuen Provider um den vorgeschalteten `bz2.decompress()`-Schritt ergänzt |
| `FETCH_DEADLINE_SECONDS`-Zeitbudget-Pattern (meteofrance.py:80-85, 194-206) | pattern | Gesamt-Zeitbudget für `fetch_forecast` bei bis zu ~96 sequentiellen Calls x Retries — identisches Muster für ICON-D2 nötig |
| `direct_provider_for` (region_routing.py:35, 40-46) | function | Gate für `de_direct` — DE-Box bleibt voraussichtlich unverändert (empirisch zu bestätigen, s. Known Limitations) |
| `ProviderRequestError`/`ProviderNotFoundError`/`ProviderNotImplementedError` (base.py:70-107) | class | Müssen vom neuen Provider korrekt geworfen werden (httpx-Fehler → `ProviderRequestError` mit `status_code`); Seam in `openmeteo.py` fängt bereits alle drei (F001-Fix aus #1142) |
| `get_provider`/`register_provider` (base.py:114-159, 183-188) | function | Bestehende Registry; Umhängen des `de_direct`-Eintrags von Stub auf echten Provider |
| `NormalizedTimeseries`/`ForecastMeta`/`ForecastDataPoint`/`Provider`-Enum (models.py:22-31, 74-163) | dataclass | Zielformat; `__post_init__` erzwingt naive-UTC-Zeitstempel — Pflicht bei jedem neuen Provider, KEIN providerspezifischer tz-Code nötig (#1345-Fix, generisch) |
| `rasterio`/GDAL 3.12.1 GRIB-Treiber | library | Bereits im Projekt vorhanden seit #1143; liest die entpackten GRIB2-Antworten bandweise |
| `bz2` (Python-Stdlib) | library | ICON-D2-Dateien liegen als `.grib2.bz2` vor — Entpacken vor `rasterio.open()`, keine neue Dependency |
| `docs/specs/modules/provider_meteofrance.md` | spec | Vorgänger-Slice (FR) — 1:1-Strukturvorlage für Adapter/Seam/Test-Aufbau, inkl. F001/F003/F004-Lehren aus Adversary-Runden |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | ADR | Nicht-Kaschieren-Invariante: 4xx bleibt sichtbar, 5xx/Timeout nach Retry bleibt sichtbar — für diesen Provider verbindlich |

## Implementation Details

**1. `src/providers/dwd.py` (CREATE, ~180-230 LoC)**

Neue Klasse `DwdDirectProvider`, implementiert das `WeatherProvider`-Protocol (`name`-Property, `fetch_forecast`). Aufbau analog `MeteoFranceDirectProvider`:

- **Konfiguration:** `BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-d2/grib/"`, kein API-Key (anonymer Zugriff), `httpx.Client(timeout=TIMEOUT)`.
- **URL-Struktur:** `<BASE_URL><HH>/<param>/icon-d2_germany_regular-lat-lon_single-level_<YYYYMMDDHH>_<TTT>_2d_<param>.grib2.bz2` — Läufe alle 3h (00/03/06/…/21 UTC), Parameter-Ordner `t_2m`, `u_10m`, `v_10m`, `tot_prec`. Anders als bei AROME-WCS (ein Call kann Zeit- und Ortsfenster gleichzeitig subsetten) liefert ICON-D2 Open Data **1 Datei pro Parameter pro Zeitschritt** — es gibt keinen serverseitigen Punkt-Query, die volle Rasterdatei muss pro Zeitschritt geladen werden.
- **Retry:** tenacity `@retry` mit `stop_after_attempt(5)`, `wait_exponential(min=2, max=60)`, `retry_if_exception(_is_retryable_error)` (500/502/503/504 + `ConnectError`/`ReadTimeout`) — 1:1 Muster aus `meteofrance.py:98-104, 156-185`. `_request` fängt `httpx.HTTPStatusError`/`httpx.RequestError` NICHT selbst; die Übersetzung zu `ProviderRequestError` erfolgt in `fetch_forecast` (wie bei `MeteoFranceDirectProvider.fetch_forecast`, meteofrance.py:228-239), damit der Retry-Mechanismus auf der rohen httpx-Exception arbeitet.
- **Abrufstrategie:** Für jeden der vier Parameter (`t_2m`, `u_10m`, `v_10m`, `tot_prec`) je Zeitschritt ein eigener HTTP-GET-Request, begrenzt auf `FORECAST_HOURS` (24h-Horizont, PO-Tech-Lead-Entscheidung 2026-07-23, analog dem FR-MVP-Vorbild): 4 Parameter × 24 Zeitschritte = ~96 Calls pro Fetch, ausschließlich im Total-Ausfall-Fallback-Pfad (kein Dauerbetrieb). Gesamt-Zeitbudget `FETCH_DEADLINE_SECONDS` analog `meteofrance.py:80-85` — verhindert unbegrenzte Laufzeit über die vielen sequentiellen Calls x Retries.
- **Entpacken + GRIB2-Parsing:** `bz2.decompress(response.content)` auf die Rohbytes der `.grib2.bz2`-Antwort, danach `rasterio.open()` via `MemoryFile` (Muster `_read_point_value`, meteofrance.py:128-138) — Pixel-Lookup an der Zielkoordinate über `dataset.index(lon, lat)`, Zeitstempel je Datei aus dem `<TTT>`-Offset im Dateinamen (nicht aus GRIB-Metadaten wie bei AROME, da hier eine Datei = ein Zeitschritt statt eines Multi-Band-Coverage).
- **Normalisierung:**
  - `t2m_c`: **Empirisch in der RED-Phase 2026-07-23 an echtem Fixture korrigiert:** GDAL taggt ICON-D2 `t_2m` bereits mit `GRIB_UNIT=[C]` ("Temperature [C]") — der Rohwert IST **bereits °C**, KEINE Kelvin-Umrechnung. Beweis: München Lauf 2026-07-22T21Z +1h, Rohwert `18.11` — als `kelvin-273.15` wäre das −255°C (unmöglich), als direkter °C-Wert plausibel (Sommerabend). Also `t2m_c = round(rohwert, 1)`, **kein** `−273.15`. GRIB-PDS-Einheit im Impl-Schritt gegenprüfen (nicht dem GDAL-Tag allein trauen), aber die Messung ist eindeutig; AC-1-Bounds (−40…50) fangen einen Fehlgriff sofort.
  - `wind10m_kmh`: `_vector_to_speed_kmh(u, v)` — 1:1 übernommen aus `meteofrance.py:107-111`, U/V in m/s, `sqrt(u²+v²) * 3.6`, gerundet auf 1 Nachkommastelle.
  - `precip_1h_mm`: **Kritischer Unterschied zu AROME-FR (#1143) — NICHT dieselbe Formel.** `tot_prec` bei ICON-D2 ist **seit Laufbeginn kumuliert** (nicht 1h-Fenster wie AROMEs `_PT1H`-Coverage). Die 1h-Regenmenge ist die **Differenz zweier aufeinanderfolgender Zeitschritte**: `precip_1h_mm[t] = max(0, round(tot_prec[t] - tot_prec[t-1], 1))`, mit `precip_1h_mm[t=1] = max(0, round(tot_prec[t=1] - 0, 1))` (Laufbeginn = 0). **F003-Lehre aus #1143 verbindlich angewendet:** diese Formel ist wie bei AROME zunächst eine Doku-Ableitung, KEINE bestätigte Live-Messung — analog zu AROME (wo die Doku-Annahme in Runde 1 falsch war) MUSS die tatsächliche Semantik (kumuliert vs. Rate, Einheit) im Implementierungsschritt gegen einen echten Nicht-Null-Datenpunkt verifiziert werden, bevor die Formel final gilt. NIE dem GDAL-`GRIB_UNIT`-Tag allein trauen — `typeOfStatisticalProcessing` aus den GRIB-PDS-Metadaten lesen (identisches Verfahren wie bei der AROME-Korrektur, meteofrance.py-Docstring Zeile 21-37).
  - `symbol`/`wmo_code`: bleiben `None` (konsistent mit `GeoSphereProvider`/`MeteoFranceDirectProvider`/`OpenMeteoProvider`).
- **Meta:** `ForecastMeta(provider=Provider.DWD, model="ICON-D2", grid_res_km=2.2, interp="grid_point")`.
- **Fehlerbehandlung:** `fetch_forecast` fängt `httpx.HTTPStatusError`/`httpx.RequestError` aus den vier `_fetch_series`-Aufrufen und übersetzt zu `ProviderRequestError(self.name, ..., status_code=...)` — 1:1 Muster `meteofrance.py:233-239`. Ein 4xx (z. B. Zeitschritt noch nicht veröffentlicht, Lauf-Timing-Mismatch) propagiert unverändert als `ProviderRequestError` mit `status_code` im 4xx-Bereich (kein Retry, kein weiteres Ausweichen — ADR-0018).

**2. `src/providers/regional_stubs.py` (MODIFY, ~5 LoC)**

`make_de_direct = partial(RegionalStubProvider, "de_direct")` (Zeile 102) wird entfernt. Modul-Docstring (Zeile 18: „Der verbleibende reale Provider landet in #1144") wird gestrichen bzw. auf „Nach #1144 ist kein Regions-Stub mehr offen" umgeschrieben — `RegionalStubProvider` selbst bleibt als generische Klasse im Modul (kein anderer Aufrufer betroffen).

**3. `src/providers/base.py` (MODIFY, ~5 LoC)**

`_load_providers()` (Zeile 183-188): Import `from providers.dwd import DwdDirectProvider` ergänzt, `register_provider("de_direct", make_de_direct)` wird zu `register_provider("de_direct", DwdDirectProvider)`. `at_direct`/`fr_direct` bleiben unverändert.

**4. `src/app/models.py` (MODIFY, 1 LoC)**

`Provider`-Enum (Zeile 22-31) um `DWD = "DWD"` erweitert.

**5. `src/providers/region_routing.py` (MODIFY, voraussichtlich KEINE Änderung)**

DE-Zeile (35): `_RegionBounds("DE", 47.2, 55.1, 5.8, 15.1, "de_direct")` — die ICON-D2-Domäne (43,2–58,1°N / −3,9–20,3°E lt. Recherche) umschließt die Box vollständig. Wie bei AT (#1142) empirisch mit echten Grenzwert-Calls zu bestätigen, bevor die Zeile final als „keine Änderung" gilt (s. Known Limitations) — keine Vorab-Fixierung in dieser Spec.

## Expected Behavior

- **Input:** Briefing-/Vergleichs-Wetterabruf via `fetch_forecast`; Open-Meteo hat bereits alle abdeckenden Modelle inkl. globalem ECMWF mit 5xx/Timeout ausgeschöpft (Total-Ausfall, #1141-Pfad); Koordinate liegt in Deutschland.
- **Output:** Bei Koordinate innerhalb der DE-Router-Box (47,2-55,1N / 5,8-15,1E) und innerhalb der tatsächlichen ICON-D2-Domäne: `NormalizedTimeseries` von DWD mit `meta.fallback_reason="cross_provider_total_outage"` und `meta.fallback_model="de_direct"`, Datenpunkte mit befüllten `t2m_c`/`wind10m_kmh`/`precip_1h_mm`. Bei Koordinate außerhalb der Router-Box: Router liefert `None` für `de_direct`, `de_direct` wird gar nicht erst kontaktiert. Bei DWD-4xx (z. B. Zeitschritt noch nicht veröffentlicht): `ProviderRequestError` sichtbar durchgereicht, kein drittes Ausweichen. Bei DWD-5xx/Timeout nach Ausschöpfung des Retries: `ProviderRequestError` propagiert zum Seam, Segment bleibt `has_error`.
- **Side effects:** Kein zusätzlicher Open-Meteo-Call im Fallback-Pfad (Provider ist eigenständig). Bestehende `at_direct`/`fr_direct`-Provider und alle anderen Konsumenten von `region_routing.direct_provider_for` bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given eine Koordinate innerhalb der DE-Router-Box und innerhalb der tatsächlichen ICON-D2-Domäne (z. B. München), When `DwdDirectProvider.fetch_forecast` aufgerufen wird, Then liefert die Antwort ein valides `NormalizedTimeseries` mit befüllten Basis-Feldern (`t2m_c`, `wind10m_kmh`, `precip_1h_mm`) für mindestens einen Datenpunkt, mit physikalisch plausiblen Werten (Bounds-Test, kein Cross-Parameter-Mixup — analog F001 aus #1143).
  - Test: Aufgezeichnete ICON-D2-GRIB2-`.bz2`-Response-Fixtures (einmalig echt abgerufen, versioniert unter `tests/fixtures/dwd/`, je ein Fixture für `t_2m`/`u_10m`/`v_10m`/`tot_prec`) werden über einen lokalen `ThreadingHTTPServer` ausgeliefert; `DwdDirectProvider` gegen diesen Server konfiguriert (`monkeypatch.setattr("providers.dwd.BASE_URL", ...)`); Assertion auf nicht-leere `NormalizedTimeseries.data` mit gesetzten `t2m_c`/`wind10m_kmh`/`precip_1h_mm` und Plausibilitäts-Bounds (z. B. `-40 <= t2m_c <= 50`, `0 <= wind10m_kmh <= 250`, `0 <= precip_1h_mm <= 100`).

- **AC-2:** Given eine Koordinate liegt außerhalb der DE-Router-Box, When `direct_provider_for(lat, lon)` aufgerufen wird, Then wird `"de_direct"` NICHT zurückgegeben (kein Fehlversuch gegen eine offensichtlich falsche Region).
  - Test: Rein deterministischer Aufruf von `direct_provider_for` mit einer Koordinate außerhalb aller drei Boxen; Assertion `result != "de_direct"`. Kein HTTP nötig.

- **AC-3:** Given DWD/`opendata.dwd.de` antwortet mit einem 4xx (z. B. Zeitschritt-Datei noch nicht veröffentlicht, 404), When der Aufruf erfolgt, Then wird die daraus resultierende `ProviderRequestError` sichtbar durchgereicht (kein Retry, kein drittes Ausweichen, ADR-0018).
  - Test: Lokaler `ThreadingHTTPServer` liefert für den ICON-D2-Endpoint einen 404; `monkeypatch.setattr("providers.dwd.BASE_URL", <lokale URL>)`; Assertion, dass `fetch_forecast` eine `ProviderRequestError` mit `status_code` im 4xx-Bereich wirft und KEIN Retry-Loop läuft (Request-Zähler am Test-Server == 1).

- **AC-4:** Given DWD antwortet durchgehend mit 5xx/Timeout (nach Ausschöpfung der 5 Retry-Versuche), When das Segment verarbeitet wird, Then propagiert `DwdDirectProvider.fetch_forecast` eine `ProviderRequestError` (kein Crash mit einer rohen httpx-Exception oder einer anderen unbehandelten Exception), und der Seam in `openmeteo.py` fängt sie unverändert (Segment bleibt `has_error`).
  - Test: Lokaler `ThreadingHTTPServer` liefert durchgehend 503 für den ICON-D2-Endpoint; `monkeypatch.setattr("providers.dwd.BASE_URL", <lokale URL>)`; Assertion auf `ProviderRequestError` nach genau 5 Anfragen (Retry-Zähler am Test-Server == 5) sowie auf den End-to-End-Pfad über den Open-Meteo-Seam (analog `test_seam_catches_provider_request_and_not_found_error` aus #1142/#1143).

- **AC-5 (Niederschlag-Differenzbildung, empirisch zu verifizieren, F003-Pflicht):** Given ICON-D2 liefert `tot_prec` als seit Laufbeginn kumulierten Wert, When die Normalisierung über zwei aufeinanderfolgende Zeitschritte läuft, Then wird `precip_1h_mm` korrekt als Differenz `max(0, round(tot_prec[t] - tot_prec[t-1], 1))` berechnet.
  - Test: **PFLICHT-Regressionstest gegen ein echt aufgezeichnetes NICHT-NULL-Precip-Fixture-Paar** (zwei aufeinanderfolgende ICON-D2-`tot_prec`-Zeitschritte für dieselbe Koordinate, mit unterschiedlichen kumulierten Werten — analog `test_fetch_forecast_uses_recorded_nonzero_precip_fixture_without_rate_conversion` aus #1143). Ein 0,0-Fixture-Paar würde die Differenzbildung nicht prüfen (F003-Lehre) und ist als alleiniger Nachweis NICHT ausreichend. Zusätzlich: Randfall erster Zeitschritt (`precip_1h_mm[t=1] = tot_prec[t=1]`, da Laufbeginn implizit 0) als eigener Assertion-Fall.

- **AC-6 (Wind-Korrektheit):** Given ICON-D2 liefert U/V-Windkomponenten in m/s, When die Normalisierung läuft, Then entspricht `wind10m_kmh` `sqrt(u²+v²)*3.6`, gerundet auf 1 Nachkommastelle (identische Formel zu `geosphere._vector_to_speed_kmh`/`meteofrance._vector_to_speed_kmh`).
  - Test: Unit-Test mit bekannten U/V-Werten (z. B. u=10, v=0 → 36.0 km/h) gegen die neue Hilfsfunktion in `dwd.py`, ohne HTTP.

- **AC-7 (E2E-Totalausfall-Rendering, aus #1345-Lehre, verbindliche Abnahme-Vorlage):** Given Open-Meteo hat für eine DE-Koordinate einen kompletten Totalausfall (alle Modelle 5xx/Timeout), When das Briefing für dieses Segment gerendert wird, Then wird ein vollständiges Segment aus `DwdDirectProvider`-Daten gerendert (Erfolgspfad, nicht nur eine isolierte `fetch_forecast`-Rückgabe).
  - Test: Open-Meteo-503-Fixture (alle Modelle) über den bestehenden Test-Server → `DwdDirectProvider`-Fixture (aufgezeichnet, wie AC-1) durch den Seam in `openmeteo.py` → Assertion auf vollständiges `NormalizedTimeseries`/gerendertes Segment mit `fallback_reason="cross_provider_total_outage"`, `fallback_model="de_direct"`, befüllten Basis-Feldern. Das ist der Nachweis, dass das Briefing im Ernstfall tatsächlich vollständig rendert — nicht nur, dass die Fehlerbehandlung sauber ist.

- **AC-8 (F001-Testauftrag aus Issue-Kommentar):** Given `DwdDirectProvider` wirft `ProviderRequestError` (5xx/Timeout) am Cross-Provider-Einhängepunkt in `openmeteo.py`, When der Seam das fängt, Then bleibt das Segment sichtbar `has_error` markiert (kein Crash mit einer neuen, unbehandelten Exception) — deckungsgleich mit AC-4, hier als expliziter End-to-End-Nachweis durch den Seam (nicht nur isolierter Provider-Unit-Test).
  - Test: Wie AC-4, aber Assertion zusätzlich auf den vollständigen Seam-Durchlauf (`openmeteo.py`-Fetch-Pfad statt isoliertem `DwdDirectProvider()`-Aufruf), analog dem für #1345 vorgeschlagenen E2E-Fehlerpfad-Muster.

## Known Limitations

- Nur `de_direct` wird in diesem Slice an einen echten Provider angebunden. Mit Abschluss dieses Slices ist `regional_stubs.RegionalStubProvider` in keinem der drei Regions-Registry-Einträge mehr aktiv (AT/FR/DE haben alle einen echten Direktprovider) — die Klasse bleibt als generischer Baustein im Modul, wird aber von `_load_providers()` nirgends mehr instanziiert.
- **Keine explizite Coverage-Prüfung innerhalb des Providers:** Die DE-Router-Box ist eine grobe Länder-Näherung, keine exakte ICON-D2-Domänengrenze. **Empirisch in der Adversary-Phase korrigiert (F001):** ICON-D2 liefert eine volle rechteckige Rasterdatei (200 OK), ~16,7 % der Pixel sind Nodata (`dataset.nodata == 9999.0`). Eine Koordinate innerhalb der Router-Box, aber außerhalb der tatsächlichen Modell-Domäne, träfe also einen **Sentinel-Wert 9999.0** — KEIN 4xx. `_read_point_value` (`dwd.py:115-128`) prüft diesen Sentinel derzeit NICHT, d. h. der Garbage-Wert flösse unvalidiert ins Ergebnis (die Bounds-Prüfung lebt nur im Test). **Heute nicht auslösbar:** 40×40-Dichte-Scan der DE-Box → 0/1600 Nodata-Treffer, die Box liegt vollständig in der gültigen Domäne. Latenter Pfad bei künftiger Box-Erweiterung → Sammel-Eintrag #1199 (Nodata-Guard in `_read_point_value`). **Die DE-Box-Unveränderlichkeit ist eine begründete, dicht gescannte Erwartung, keine formale Domänengrenz-Verifikation** — bei künftiger Box-Änderung neu zu prüfen.
- **Precip-Semantik empirisch offen (größtes Risiko dieses Slices):** Die Differenzbildungs-Formel (AC-5) beruht auf DWD-Dokumentation, nicht auf einer bereits durchgeführten Live-Messung — bei AROME-FR (#1143) erwies sich die analoge Doku-Annahme in Adversary-Runde 1 als falsch (F003) und musste in Runde 2 korrigiert werden. Dieselbe Korrekturschleife ist für ICON-D2 einzuplanen; die Formel in dieser Spec ist der Startpunkt, nicht die verifizierte Endfassung.
- Der `enrich_ensemble`-Parameter wird vom neuen Provider ignoriert (keine Ensemble-API bei ICON-D2 im Rahmen dieses Slices) — analog zu `GeoSphereProvider`/`MeteoFranceDirectProvider`.
- `symbol`/`wmo_code` bleiben `None` — kein Wettercode/Symbol aus ICON-D2 abgeleitet, konsistent mit GeoSphere/Météo-France/Open-Meteo.
- Kein neues Alarmsignal für „DWD-Direktfallback wurde benutzt" — Sichtbarkeit läuft weiterhin über `meta.fallback_reason`/`fallback_model` (#1141) und `provider_error_streak` (Go, unverändert).
- **Requestvolumen/Backend-Robustheit von `opendata.dwd.de` ist in diesem Projekt bislang nicht produktionsgetestet** (anders als Météo-France/GeoSphere, die bereits vor #1142/#1143 in anderen Kontexten genutzt wurden — z. B. `vigilance.py`, `meteo_forets.py`). Bis zu ~96 sequentielle Requests pro Fetch sind ein neues Belastungsmuster für diese Quelle.
- 24h-Horizont ist bewusstes MVP-Scoping (PO-Tech-Lead-Entscheidung 2026-07-23, analog dem ursprünglichen FR-Startwert von 6h vor Erweiterung auf 24h) — spätere Erweiterung ist ein Folge-Slice, keine offene Frage in diesem Slice.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0018 bleibt gültig und verbindlich, wird durch dieses Slice nicht verändert)
- **Rationale:** Reine additive Erweiterung des in #1141/#1142/#1143 etablierten Registry-/Fallback-Musters — ein Stub wird durch einen echten Provider ersetzt, keine neue Cross-Cutting-Entscheidung, kein neuer Layer. Die Nicht-Kaschieren-Invariante (ADR-0018) wird unverändert angewendet: 4xx bleibt sichtbar (AC-3), 5xx/Timeout nach Retry bleibt sichtbar (AC-4). Die Quellenwahl ICON-D2 statt MOSMIX/BrightSky ist eine Konkretisierung der bereits in ADR-0002 getroffenen Stationsdaten-Genauigkeitsentscheidung (MOSMIX für dieses Produkt ungeeignet), kein neues Entscheidungsfeld — rechtfertigt kein eigenes ADR.

## Out of Scope (Folge-Issues)

- Coverage-Bounds-Vereinheitlichung zwischen `radar_service`, `openmeteo.REGIONAL_MODELS` und `region_routing._REGIONS` (Epic-#1127-Risiko 3) — nicht Teil dieses Slices, die Router-Box bleibt eine eigenständige, bewusst grobe Länder-Näherung.
- Bonus-Metriken aus ICON-D2 (CAPE, Wolken, Blitzdichte, Böen) — nicht Teil dieses minimalen Slices (analog PO-Entscheidung 2026-07-22 bei AROME-FR: nur t2m_c/wind10m_kmh/precip_1h_mm).
- Horizont-Erweiterung über 24h hinaus (analog der FR-Erweiterung von 6h auf 24h nach Freigabe) — spätere PO-Entscheidung, nicht Teil dieses Slices.
- Mit diesem Slice ist Epic #1127 (Cross-Provider-Fallback, alle drei Regionen AT/FR/DE) inhaltlich abgeschlossen — verbleibende Epic-Risiken (Coverage-Bounds-Vereinheitlichung, s. o.) sind eigene Folgearbeit, kein neuer Regions-Slice.

## Changelog

- 2026-07-23: Initial spec created
- 2026-07-23: Spec-Validator VALID; PO-Freigabe („go") der 8 ACs erteilt
- 2026-07-23: RED-Phase — 8 Tests (`tests/tdd/test_dwd_direct_fallback.py`), 7 rot (ModuleNotFoundError `providers.dwd`) / 1 grün (AC-2-Router-Wächter). Echte ICON-D2-Fixtures aufgezeichnet (`tests/fixtures/dwd/`), inkl. Nicht-Null-Precip-Paar (Ostseeküste 53.70/14.94, kumuliert +3h=3.14 → +4h=15.49, Differenz 12.35 mm). **Empirische Korrektur:** `t_2m` ist bereits °C (GDAL-Tag `[C]`), keine Kelvin-Umrechnung — `t2m_c`-Formel oben entsprechend geändert. `tot_prec`-Kumulation durch wachsende `lengthOfTimeRange` (0/60/120 min) gestützt.
