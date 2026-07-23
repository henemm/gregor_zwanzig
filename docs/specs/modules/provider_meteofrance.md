---
entity_id: provider_meteofrance
type: module
created: 2026-07-22
updated: 2026-07-23
status: draft
version: "1.0"
tags: [providers, meteofrance, arome, openmeteo, reliability, fallback, routing, briefing]
workflow: 1143-meteofrance-fr-fallback
---

# Cross-Provider-Fallback — echter Météo-France-AROME-Direktprovider für FR (#1143, Slice 2/4 von Epic #1127)

## Approval

- [x] Approved (PO „freigabe" 2026-07-22)

## Purpose

Der in #1141 verdrahtete Stub `fr_direct` (wirft immer `ProviderNotImplementedError`) wird durch einen **echten** Météo-France-Provider ersetzt, damit der Cross-Provider-Fallback im Total-Ausfall-Fall für Koordinaten in Frankreich (inkl. Korsika/GR20) tatsächlich Wetterdaten liefert statt weiterhin den Original-Fehler durchzureichen. Der neue Provider ruft die öffentliche Météo-France-WCS-API für das AROME-HIGHRES-Modell (0,01° Auflösung Frankreich) direkt auf, liest die GRIB2-Rohdaten mit dem bereits vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue Dependency) und normalisiert sie auf `t2m_c`/`wind10m_kmh`/`precip_1h_mm`. Zusätzlich wird die FR-Router-Box in `region_routing.py` nach Osten erweitert, damit Korsika (GR20-Kernrouten) beim Totalausfall überhaupt auf `fr_direct` geroutet wird (PO-Entscheidung 2026-07-22).

## Source

- **File:** `src/providers/meteofrance.py` (Python-Core / Domain-Backend) — CREATE. Neue Klasse `MeteoFranceDirectProvider`, Vorlage `src/providers/geosphere.py` (`_vector_to_speed_kmh`, `_request`-Retry-Muster, httpx→`ProviderRequestError`-Übersetzung) und `GeoSphereDirectProvider` (`src/providers/regional_stubs.py:58-96`, Adapter-Struktur).
- **File:** `src/providers/regional_stubs.py:101` — `make_fr_direct` (`partial(RegionalStubProvider, "fr_direct")`) wird entfernt; Registry-Key `fr_direct` zeigt stattdessen auf `MeteoFranceDirectProvider` aus `meteofrance.py`.
- **File:** `src/providers/base.py:183-191` — `_load_providers()`: `register_provider("fr_direct", make_fr_direct)` wird auf `register_provider("fr_direct", MeteoFranceDirectProvider)` umgestellt (Import aus `providers.meteofrance` statt `providers.regional_stubs`); `de_direct` bleibt unverändert Stub.
- **File:** `src/app/models.py:22-30` — `Provider`-Enum um `METEOFRANCE = "METEOFRANCE"` erweitert, für `ForecastMeta.provider` im neuen Provider.
- **File:** `src/providers/region_routing.py:36` — FR-Box `_RegionBounds("FR", 41.3, 51.1, -5.2, 8.3, "fr_direct")` wird nach Osten auf `max_lon=9.7` erweitert (Korsika/GR20-Abdeckung, PO-Entscheidung 2026-07-22), Rest der Box unverändert.
- **File:** `docs/reference/decision_matrix.md` — `fr_direct`-Zeile von „Stub" auf „AROME-WCS-Direktprovider (Météo-France)" fortgeschrieben.

> **Schicht-Hinweis:** Alle Änderungen liegen in Python-Core (`src/providers/`, `src/app/models.py`). Keine Go-API-Änderung, kein Frontend-Bezug.

## Estimated Scope

- **LoC:** ~150–250 Produktions-LoC (neuer Provider ist der Löwenanteil; Registry/Enum/Box-Änderungen sind Ein- bis Wenig-Zeiler) — nahe am 250-LoC-Workflow-Limit, ggf. Override nötig.
- **Files:** 1 CREATE (`meteofrance.py`) + 4 MODIFY (`regional_stubs.py`, `base.py`, `models.py`, `region_routing.py`) + `docs/reference/decision_matrix.md` (zählt nicht zum LoC-Limit) + 1 Testdatei mit AROME-GRIB2-Fixtures.
- **Effort:** medium-high (GRIB2-Parsing via rasterio ist neu im Projekt, WCS-Abrufstrategie muss Call-Anzahl niedrig halten, Backend ist bekanntermaßen flaky).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GeoSphereProvider._request` / `_is_retryable_error` (geosphere.py:59-65, 245-279) | function | Vorlage für tenacity-Retry (502/503/504 + Connection-Errors, 5 Versuche, 2-60s Backoff) und httpx→`ProviderRequestError`-Übersetzung im neuen Provider |
| `_vector_to_speed_kmh` (geosphere.py:106-109) | function | Muster für U/V-Wind-Vektor → km/h (Betrag * 3,6); wird für AROME-U/V-Komponenten äquivalent implementiert |
| `direct_provider_for` (region_routing.py:40-46) | function | Gate für `fr_direct` — Box-Erweiterung (max_lon 8,3 → 9,7) ist Teil dieses Slices, damit Korsika/GR20 überhaupt geroutet wird |
| `ProviderRequestError`/`ProviderNotFoundError`/`ProviderNotImplementedError` (base.py:70-107) | class | Müssen vom neuen Provider korrekt geworfen werden (httpx-Fehler → `ProviderRequestError` mit `status_code`); Seam in `openmeteo.py` fängt bereits alle drei (F001-Fix aus #1142) |
| `get_provider`/`register_provider` (base.py:114-159, 183-191) | function | Bestehende Registry; Umhängen des `fr_direct`-Eintrags von Stub auf echten Provider |
| `NormalizedTimeseries`/`ForecastMeta`/`ForecastDataPoint`/`Provider`-Enum (models.py:22-30, 74-163) | dataclass | Zielformat; `__post_init__` erzwingt naive-UTC-Zeitstempel — Pflicht bei jedem neuen Provider |
| `rasterio`/GDAL 3.12.1 GRIB-Treiber | library | Bereits im Projekt vorhanden (verifiziert im Feasibility-Spike, `'GRIB' in rasterio.Env().drivers()` → True); liest die GRIB2-Antworten der WCS-API bandweise |
| `GZ_METEOFRANCE_APIKEY` (bereits genutzt in `vigilance.py:88`, `meteo_forets.py`) | env var | Gleicher API-Key wie Vigilance/Forêts, hier als `apikey`-Header gegen die WCS-AROME-Domäne (Feasibility-Spike bestätigt: Zugriff auf AROME HIGHRES freigeschaltet) |
| `docs/specs/_archive/modules/issue_1142_geosphere_direct_fallback.md` | spec | Vorgänger-Slice (AT) — 1:1-Strukturvorlage für Adapter/Seam/Test-Aufbau |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | ADR | Nicht-Kaschieren-Invariante: 4xx bleibt sichtbar, 5xx/Timeout nach Retry bleibt sichtbar — für diesen Provider verbindlich |

## Implementation Details

**1. `src/providers/meteofrance.py` (CREATE, ~150-200 LoC)**

Neue Klasse `MeteoFranceDirectProvider`, implementiert das `WeatherProvider`-Protocol (`name`-Property, `fetch_forecast`). Aufbau analog `GeoSphereProvider`:

- **Konfiguration:** `BASE_URL = "https://public-api.meteofrance.fr/public/arome/1.0/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/"`, Auth per `apikey`-Header (`GZ_METEOFRANCE_APIKEY`, gleicher Key wie `vigilance.py`/`meteo_forets.py`), `httpx.Client(timeout=TIMEOUT)`.
- **Retry:** tenacity `@retry` mit `stop_after_attempt(5)`, `wait_exponential(min=2, max=60)`, `retry_if_exception(_is_retryable_error)` (502/503/504 + `ConnectError`/`ReadTimeout`) — 1:1 Muster aus `geosphere.py:238-279`. `_request` fängt `httpx.HTTPStatusError`/`httpx.RequestError` NICHT selbst; die Übersetzung zu `ProviderRequestError` erfolgt in `fetch_forecast` (wie bei `GeoSphereProvider.fetch_forecast`, geosphere.py:213-226), damit der Retry-Mechanismus auf der rohen httpx-Exception arbeitet.
- **Abrufstrategie (empirisch korrigiert, s. Known Limitations):** Die Live-WCS-API akzeptiert `subset=time(...)` NUR als einzelnen Zeitwert pro `GetCoverage`-Call ("Slicing on time is mandatory: only a 2D coverage can be downloaded") — ein Multi-Zeitschritt-Request in einem Call ist technisch nicht möglich, anders als ursprünglich angenommen. Der Provider ruft daher für jeden der vier Parameter (`TEMPERATURE` mit `height=2`-Subset, `U_COMPONENT_OF_WIND`, `V_COMPONENT_OF_WIND`, `TOTAL_PRECIPITATION`) je Zeitschritt einen eigenen `GetCoverage`-Request ab, begrenzt auf `FORECAST_HOURS` (24h-Horizont, PO-Entscheidung 2026-07-23 — Nachfolger von zuvor 6h): 4 Parameter × 24 Zeitschritte = 96 Calls pro Fetch, ausschließlich im Total-Ausfall-Fallback-Pfad (kein Dauerbetrieb).
- **GRIB2-Parsing:** `rasterio.open()` auf die Response-Bytes (via `MemoryFile` oder Temp-Datei), pro Band (= Zeitschritt) `dataset.read(band_index)` an der Zielkoordinate (Pixel-Lookup über `dataset.index(lon, lat)`), Zeitstempel je Band aus den GRIB-Metadaten (`dataset.tags(band_index)`, GRIB-Standard-Tag `GRIB_VALID_TIME` o.ä.).
- **Normalisierung:**
  - `t2m_c`: direkt aus TEMPERATURE-Band (AROME liefert bereits °C oder K — im Implementierungsschritt anhand echter Response verifizieren und ggf. K→°C konvertieren, analog zum bestätigten Pattern bei anderen Providern).
  - `wind10m_kmh`: `_vector_to_speed_kmh(u, v)` — äquivalente Funktion zu `geosphere.py:106-109`, `sqrt(u²+v²) * 3.6`, gerundet auf 1 Nachkommastelle.
  - `precip_1h_mm`: **Korrigiert 2026-07-23 nach empirischer Messung (Adversary #1143 F003, Runde 2 — löst die Runde-1-Analyse ab):** TOTAL_PRECIPITATION über die `_PT1H`-Coverage ist eine 1h-Akkumulation (GRIB-PDS `typeOfStatisticalProcessing=1`, `lengthOfTimeRange=1h`) — der Rohwert IST bereits die 1h-Regenmenge in kg/m² (= mm), **keine** Rate. Das GDAL-Tag `GRIB_UNIT=[kg/(m^2*s)]` ist ein generisches Fehletikett und darf nicht wörtlich genommen werden. Beweis: Alpenzelle 44,04N/7,84E, 2026-07-23T15:00Z, Rohwert `5,178` — `×3600` ergäbe `18641,6` mm/h (physikalisch unmöglich), Direktwert `5,178` mm/h (plausibel). Umrechnung: `precip_1h_mm = max(0, round(rate, 1))` — **kein** `×3600`, keine Differenzbildung.
  - `symbol`/`wmo_code`: bleiben `None` (PO-Entscheidung 2026-07-22, minimal — konsistent mit `GeoSphereProvider`/`OpenMeteoProvider`).
- **Meta:** `ForecastMeta(provider=Provider.METEOFRANCE, model="AROME-HIGHRES", grid_res_km=1.3, interp="grid_point")`.
- **Fehlerbehandlung:** `fetch_forecast` fängt `httpx.HTTPStatusError`/`httpx.RequestError` aus den drei `_request`-Aufrufen und übersetzt zu `ProviderRequestError(self.name, ..., status_code=...)` — 1:1 Muster `geosphere.py:221-226`. Ein 4xx (z. B. `outside of dataset bounds`) propagiert unverändert als `ProviderRequestError` mit `status_code` im 4xx-Bereich (kein Retry, kein weiteres Ausweichen — ADR-0018).

**2. `src/providers/regional_stubs.py` (MODIFY, ~5 LoC)**

`make_fr_direct = partial(RegionalStubProvider, "fr_direct")` (Zeile 101) wird entfernt. Modul-Docstring (Zeile 15-16) wird auf „#1144 (DWD DE)" als einzig verbleibenden offenen Folge-Slice reduziert.

**3. `src/providers/base.py` (MODIFY, ~5 LoC)**

`_load_providers()` (Zeile 183-191): Import `from providers.meteofrance import MeteoFranceDirectProvider` ergänzt, `register_provider("fr_direct", make_fr_direct)` wird zu `register_provider("fr_direct", MeteoFranceDirectProvider)`. `de_direct` bleibt unverändert bei `RegionalStubProvider`.

**4. `src/app/models.py` (MODIFY, 1 LoC)**

`Provider`-Enum (Zeile 22-30) um `METEOFRANCE = "METEOFRANCE"` erweitert.

**5. `src/providers/region_routing.py` (MODIFY, 1 LoC)**

FR-Zeile (36): `_RegionBounds("FR", 41.3, 51.1, -5.2, 8.3, "fr_direct")` → `_RegionBounds("FR", 41.3, 51.1, -5.2, 9.7, "fr_direct")`. `max_lon` von 8,3 auf 9,7 erhöht, damit Korsika/GR20 (≈41,3-43,0N / 8,5-9,6E) innerhalb der Box liegt. Rest der Box (min_lat/max_lat/min_lon), sowie AT/DE-Zeilen unverändert.

## Expected Behavior

- **Input:** Briefing-/Vergleichs-Wetterabruf via `fetch_forecast`; Open-Meteo hat bereits alle abdeckenden Modelle inkl. globalem ECMWF mit 5xx/Timeout ausgeschöpft (Total-Ausfall, #1141-Pfad); Koordinate liegt in Frankreich (inkl. Korsika, nach der Box-Erweiterung).
- **Output:** Bei Koordinate innerhalb der erweiterten FR-Router-Box (41,3-51,1N / -5,2-9,7E) und innerhalb der tatsächlichen AROME-Domäne: `NormalizedTimeseries` von Météo-France mit `meta.fallback_reason="cross_provider_total_outage"` und `meta.fallback_model="fr_direct"`, Datenpunkte mit befüllten `t2m_c`/`wind10m_kmh`/`precip_1h_mm`. Bei Koordinate außerhalb der Router-Box: Router liefert `None` für `fr_direct`, `fr_direct` wird gar nicht erst kontaktiert. Bei Météo-France-4xx (z. B. außerhalb der WCS-Domäne innerhalb der Router-Box): `ProviderRequestError` sichtbar durchgereicht, kein drittes Ausweichen. Bei Météo-France-5xx/Timeout nach Ausschöpfung des Retries: `ProviderRequestError` propagiert zum Seam, Segment bleibt `has_error`.
- **Side effects:** Kein zusätzlicher Open-Meteo-Call im Fallback-Pfad (Provider ist eigenständig, keine versteckte Abhängigkeit wie bei GeoSphere-Wolken). Bestehende `de_direct`/`at_direct`-Provider und alle anderen Konsumenten von `region_routing.direct_provider_for` bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given eine Koordinate innerhalb der erweiterten FR-Router-Box und innerhalb der tatsächlichen Météo-France-AROME-Coverage (z. B. Paris), When `MeteoFranceDirectProvider.fetch_forecast` aufgerufen wird, Then liefert die Antwort ein valides `NormalizedTimeseries` mit befüllten Basis-Feldern (`t2m_c`, `wind10m_kmh`, `precip_1h_mm`) für mindestens einen Datenpunkt.
  - Test: Aufgezeichnetes AROME-WCS-GRIB2-Response-Fixture (einmalig echt abgerufen, versioniert unter `tests/fixtures/`) wird über einen lokalen `ThreadingHTTPServer` ausgeliefert; `MeteoFranceDirectProvider` gegen diesen Server konfiguriert; Assertion auf nicht-leere `NormalizedTimeseries.data` mit gesetzten `t2m_c`/`wind10m_kmh`/`precip_1h_mm`.

- **AC-2:** Given eine Koordinate liegt außerhalb der (erweiterten) FR-Router-Box, When `direct_provider_for(lat, lon)` aufgerufen wird, Then wird `"fr_direct"` NICHT zurückgegeben (kein Fehlversuch gegen eine offensichtlich falsche Region).
  - Test: Rein deterministischer Aufruf von `direct_provider_for` mit einer Koordinate außerhalb aller drei Boxen (z. B. Berlin-Ost, deutlich außerhalb FR); Assertion `result != "fr_direct"`. Kein HTTP nötig.

- **AC-3:** Given Météo-France antwortet mit einem 4xx (Inhaltsfehler, z. B. Koordinate außerhalb der WCS-Domäne), When der Aufruf erfolgt, Then wird die daraus resultierende `ProviderRequestError` sichtbar durchgereicht (kein drittes, verdecktes Ausweichen, ADR-0018).
  - Test: Lokaler `ThreadingHTTPServer` liefert für den WCS-Endpoint einen 4xx-Statuscode (z. B. 400 mit „outside of dataset bounds"-Body, analog zur echten AROME-Fehlermeldung aus dem Feasibility-Spike); `monkeypatch.setattr("providers.meteofrance.BASE_URL", <lokale URL>)`; Assertion, dass `fetch_forecast` eine `ProviderRequestError` mit `status_code` im 4xx-Bereich wirft und KEIN Retry-Loop läuft (Request-Zähler am Test-Server == 1).

- **AC-4:** Given Météo-France antwortet durchgehend mit 5xx/Timeout (nach Ausschöpfung der 5 Retry-Versuche), When das Segment verarbeitet wird, Then propagiert `MeteoFranceDirectProvider.fetch_forecast` eine `ProviderRequestError` (kein Crash mit einer rohen httpx-Exception oder einer anderen unbehandelten Exception), und der Seam in `openmeteo.py` fängt sie unverändert (Segment bleibt `has_error`).
  - Test: Lokaler `ThreadingHTTPServer` liefert durchgehend 503 für den WCS-Endpoint; `monkeypatch.setattr("providers.meteofrance.BASE_URL", <lokale URL>)`; Assertion auf `ProviderRequestError` nach genau 5 Anfragen (Retry-Zähler am Test-Server == 5) sowie auf den End-to-End-Pfad über den Open-Meteo-Seam (analog `test_seam_catches_provider_request_and_not_found_error` aus #1142).

- **AC-5 (Korsika-Regression):** Given eine Koordinate auf einer GR20/Korsika-Kernroute (z. B. 42,0N/9,0E), When `direct_provider_for(lat, lon)` aufgerufen wird, Then wird `"fr_direct"` zurückgegeben (Box-Erweiterung auf `max_lon=9,7` greift; vor diesem Slice hätte die Koordinate außerhalb aller drei Regionen gelegen und `None` erhalten).
  - Test: Rein deterministischer Aufruf von `direct_provider_for(42.0, 9.0)`; Assertion `result == "fr_direct"`. Zusätzlicher Test mit einer Koordinate knapp außerhalb der alten Box, aber innerhalb der neuen (z. B. 42,0N/9,0E liegt bereits im alten Bereich min_lon=-5.2 — konkret muss der Testfall eine Koordinate mit Längengrad zwischen 8,3 und 9,7 wählen, z. B. 42,3N/9,3E, um die Erweiterung isoliert nachzuweisen).

- **AC-6 (Wind-Korrektheit, Detailkriterium zu AC-1):** Given AROME liefert U/V-Windkomponenten in m/s, When die Normalisierung läuft, Then entspricht `wind10m_kmh` dem Vektorbetrag `sqrt(u²+v²) * 3.6`, gerundet auf 1 Nachkommastelle (identische Formel zu `geosphere._vector_to_speed_kmh`).
  - Test: Unit-Test mit bekannten U/V-Werten (z. B. u=10, v=0 → 36.0 km/h) gegen die neue Hilfsfunktion in `meteofrance.py`, ohne HTTP.

- **AC-7 (Niederschlag-Umrechnung, Detailkriterium zu AC-1, korrigiert 2026-07-23, Runde 2):** Given AROME liefert TOTAL_PRECIPITATION über die `_PT1H`-Coverage als 1h-Akkumulation (GRIB-PDS `typeOfStatisticalProcessing=1`, `lengthOfTimeRange=1h` — Rohwert = mm, **keine** Rate; das GDAL-Tag `kg/(m²·s)` ist ein Fehletikett; empirisch verifiziert gegen die Live-API, Adversary #1143 F003 Runde 2), When die Normalisierung läuft, Then entspricht `precip_1h_mm` je Zeitschritt `max(0, round(rohwert, 1))` — **kein** `×3600`, keine Differenzbildung —, mit Untergrenze 0 (keine negativen Werte durch Rundungsartefakte).
  - Test: Abgedeckt durch AC-1 (`test_fetch_forecast_parses_recorded_arome_grib2_fixture`, Plausibilitäts-Bounds `0 <= precip_1h_mm <= 100`) UND durch einen dedizierten Regressionstest `test_fetch_forecast_uses_recorded_nonzero_precip_fixture_without_rate_conversion` gegen ein echt aufgezeichnetes NICHT-NULL-Precip-Fixture (Alpenzelle 44,04N/7,84E, Rohwert 5,178) — das ursprüngliche AC-1-Fixture (Paris) war durchgehend `0,0`, wodurch der `×3600`-Fehler in Runde 1 unsichtbar blieb.

## Known Limitations

- Nur `fr_direct` wird in diesem Slice an einen echten Provider angebunden — `de_direct` bleibt unveränderter Stub (`ProviderNotImplementedError`) bis #1144.
- **Keine explizite Coverage-Prüfung innerhalb des Providers:** Die Router-Box (erweitert auf max_lon=9,7) ist eine grobe Länder-/Alpenraum-Näherung, keine exakte AROME-Domänengrenze. Sollte eine Koordinate innerhalb der Router-Box, aber außerhalb der tatsächlichen AROME-WCS-Domäne liegen, liefert Météo-France einen 4xx (`outside of dataset bounds`), der über AC-3 sauber als `ProviderRequestError` durchgereicht wird — kein Crash, aber auch kein präventives Skippen (analog zur AT-Erkenntnis aus #1142, hier aber NICHT empirisch für die gesamte Box verifiziert, da die AROME-FR-Domäne laut Feasibility-Spike deutlich über die Router-Box hinausreicht: long −12…16, lat 37,5…55,4).
- Der `enrich_ensemble`-Parameter wird vom neuen Provider ignoriert (keine Ensemble-API bei Météo-France AROME vorhanden im Rahmen dieses Slices) — analog zu `GeoSphereProvider`.
- ARPEGE (globales Météo-France-Modell) ist mit dem vorhandenen API-Key gesperrt (403, Feasibility-Spike) und wird nicht genutzt — nur AROME HIGHRES France.
- `symbol`/`wmo_code` bleiben `None` (PO-Entscheidung 2026-07-22) — kein Wettercode/Symbol aus AROME abgeleitet, konsistent mit GeoSphere/Open-Meteo.
- Kein neues Alarmsignal für „Météo-France-Direktfallback wurde benutzt" — Sichtbarkeit läuft weiterhin über `meta.fallback_reason`/`fallback_model` (#1141) und `provider_error_streak` (Go, unverändert).
- Die exakte WCS-GetCoverage-Request-Syntax (Subset-Parameter-Namen, ob U/V in einem gemeinsamen Coverage-Request kombinierbar sind, exakte GRIB-Band-Zeitstempel-Extraktion) ist im Implementierungsschritt gegen die echte API zu verifizieren — der Feasibility-Spike bestätigte Zugang und Format (GetCapabilities/DescribeCoverage HTTP 200, GRIB2 lesbar), nicht jede Detail-Syntax der GetCoverage-Aufrufe.
- **WCS-Einzelzeitschritt-Beschränkung (empirisch verifiziert 2026-07-22):** `subset=time(...)` akzeptiert nur einen einzelnen Zeitwert je `GetCoverage`-Call — die in der Implementation-Details-Sektion ursprünglich angenommenen „~3 Calls" (ein Call je Parameter über die volle Zeitachse) sind technisch nicht möglich. Der Provider ruft daher je Parameter UND Zeitschritt einzeln ab. Vorhersagehorizont `FORECAST_HOURS` wurde 2026-07-23 per PO-Entscheidung von 6h auf 24h erweitert: 4 Parameter × 24 Zeitschritte = 96 Calls pro Fetch (zuvor 4 × 6 = 24 Calls bei 6h) — weiterhin ausschließlich im Total-Ausfall-Fallback-Pfad (#1141), kein Dauerbetrieb, kein Skalierungsrisiko für Open-Meteo-Kontingent.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0018 bleibt gültig und verbindlich, wird durch dieses Slice nicht verändert)
- **Rationale:** Reine additive Erweiterung des in #1141/#1142 etablierten Registry-/Fallback-Musters — ein Stub wird durch einen echten Provider ersetzt, keine neue Cross-Cutting-Entscheidung, kein neuer Layer. Die Nicht-Kaschieren-Invariante (ADR-0018) wird unverändert angewendet: 4xx bleibt sichtbar (AC-3), 5xx/Timeout nach Retry bleibt sichtbar (AC-4). Die Coverage-Box-Erweiterung (Korsika) ist eine lokale Parameteränderung in einer bestehenden Datenstruktur, kein neues Entscheidungsfeld — rechtfertigt kein eigenes ADR.

## Out of Scope (Folge-Issues)

- **#1144** — echter DWD-Direktprovider für Deutschland (`de_direct`).
- Coverage-Bounds-Vereinheitlichung zwischen `radar_service._AROME_FR_*`, `openmeteo.REGIONAL_MODELS["meteofrance_arome"]` und `region_routing._REGIONS` (Epic-#1127-Risiko 3) — nicht Teil dieses Slices, die Router-Box bleibt eine eigenständige, bewusst grobe Länder-Näherung.
- Bonus-Metriken aus AROME (CAPE, Wolken, Blitzdichte) — im Feasibility-Spike identifiziert, aber nicht Teil dieses minimalen Slices (PO-Entscheidung 2026-07-22: nur t2m_c/wind10m_kmh/precip_1h_mm).

## Changelog

- 2026-07-22: Initial spec created
- 2026-07-23: Vorhersagehorizont `FORECAST_HOURS` von 6h auf 24h erweitert (PO-Entscheidung); Abrufstrategie- und Known-Limitations-Abschnitt auf die tatsächliche WCS-Einzelzeitschritt-Beschränkung (96 statt 24 Calls) fortgeschrieben.
- 2026-07-23: Adversary #1143 Runde 1 (BROKEN → Fix-Schleife): AC-7 korrigiert — TOTAL_PRECIPITATION ist empirisch belegt eine Rate je 1h-Fenster (kg/(m²·s)), keine kumulierte Reihe; `_precip_1h_from_cumulative` (toter Code) entfernt. `RETRY_STATUS_CODES` um 500 ergänzt (reales Live-Symptom). Neues Gesamt-Zeitbudget `FETCH_DEADLINE_SECONDS` für `fetch_forecast` ergänzt (verhindert unbegrenzte Laufzeit über bis zu 96 sequentielle Calls). AC-1-Test liefert jetzt pfad-abhängig vier echte Fixtures (Temp/U/V/Precip) statt einer einzigen Temperatur-Antwort für alle Parameter, plus Plausibilitäts-Bounds.
- 2026-07-23: Adversary #1143 Runde 2 (F003, Nachbesserung der Runde-1-Analyse): die Rate-Deutung (`×3600`) war FALSCH — der TOTAL_PRECIPITATION-Rohwert ist laut GRIB-PDS (`typeOfStatisticalProcessing=1`, Accumulation, `lengthOfTimeRange=1h`) bereits die 1h-Regenmenge in mm; das GDAL-Tag `kg/(m²·s)` ist ein generisches Fehletikett. Beweis: Alpenzelle 44,04N/7,84E, 2026-07-23T15:00Z, Rohwert 5,178 → `×3600`=18641,6 mm/h (physikalisch unmöglich) vs. Direktwert 5,178 mm/h (plausibel). `precip_mm = round(rohwert, 1)` statt `round(rohwert * 3600, 1)`. AC-7 entsprechend korrigiert. Neuer Regressionstest gegen ein echt aufgezeichnetes NICHT-NULL-Precip-Fixture (`tests/fixtures/meteofrance/arome_alps_precip_nonzero_20260723.grib2`) — das ursprüngliche AC-1-Fixture (Paris) war `0,0` und hätte den Fehler nicht sichtbar gemacht.
