# Context: #1144 — DWD-Direktprovider für Deutschland (Slice DE von Epic #1127)

## Analysis

### Type
Feature (Slice DE aus Epic #1127, Cross-Provider-Fallback zweite Stufe). Abhängigkeiten Slice 0 (#1141) und Slice FR (#1143) geschlossen; #1143 (`MeteoFranceDirectProvider`) dient als 1:1-Strukturvorlage (Registry-Umbau, Adapter-Aufbau, Test-Muster).

### Weichenstellung: Quellenentscheidung MOSMIX vs. ICON-D2 vs. BrightSky/weather

**Empfehlung: ICON-D2 Open Data (Gitterdaten, `opendata.dwd.de`).**

Drei Kandidaten wurden geprüft, weil DWD (anders als Open-Meteo/GeoSphere) kein einfaches JSON-API für Vorhersagen anbietet:

| Quelle | Format | Parser-Aufwand | Räumliche Genauigkeit für beliebige Koordinaten | Infrastruktur | Auth/Kosten |
|---|---|---|---|---|---|
| **ICON-D2 Open Data** | GRIB2 (`.bz2`), 1 File/Parameter/Zeitschritt | rasterio/GDAL bereits vorhanden (#1143) + `bz2`-Stdlib zum Entpacken — keine neue Dependency; Niederschlag ist **seit Laufbeginn kumuliert** → Differenzbildung zwischen Zeitschritten nötig (empirisch zu verifizieren, s. u.) | **Echtes 2,2-km-Gitter**, trifft jeden Punkt (Gipfel, Tal, Grat) | DWD direkt (opendata.dwd.de) | anonym, kein Key, keine dokumentierten Limits |
| MOSMIX | KMZ/XML, Stationsdaten | Zusätzliches KML/XML-Parsing nötig (kein GRIB, neue Parser-Fläche) | Nur Stationspunkte (~einige hundert in DE), **kein Flächenraster** — abseits von Stationen (Gipfel/Tal) potenziell großer Distanz-/Höhenfehler | DWD direkt | anonym, kein Key |
| BrightSky `/weather` | fertiges JSON (wraps MOSMIX) | **Keiner** — reines HTTP+JSON, kein GRIB/KML | Wie MOSMIX: nächste Station im Umkreis bis 50 km (`max_dist`-Parameter), **kein Punktraster** | **Drittanbieter-Spiegel** (`api.brightsky.dev`), nicht DWD selbst | anonym, kein Key |

**Begründung:**

1. **ADR-0002 hat die Stationsdaten-Genauigkeitsfrage für dieses Produkt bereits entschieden.** MOSMIX wurde 2025-08-28 als Standardquelle verworfen, weil es an beliebigen GPX-Wegpunkten (Grat, Tal, küstennah) "oft weit von der nächsten Station entfernt" und damit "systematisch unzuverlässig" ist — exakt das Nutzungsmuster dieses Produkts (Weitwanderer, GR20-artige Routen abseits von Ortschaften). Diese Begründung gilt unverändert für MOSMIX **und** für BrightSky `/weather` (das intern nur MOSMIX umverpackt, mit `max_dist`-Default 50 km statt einer Gate-Logik). Eine erneute Grundsatzdiskussion ist nicht nötig — die Entscheidung steht bereits im Repo.
2. **Konsistenz mit AT/FR.** Beide bereits implementierten Direktprovider (GeoSphere-AROME für AT, Météo-France-AROME-WCS für FR) sind **Gitter**-Modelle mit echter Flächenabdeckung. ICON-D2 setzt dieses Muster für DE fort; MOSMIX/BrightSky würden eine dritte, inkonsistente Genauigkeitscharakteristik in dieselbe Fallback-Registry einführen (ein Fallback, der für zwei Länder gitterbasiert und für eines stationsbasiert ist).
3. **Echte Infrastruktur-Unabhängigkeit.** Epic #1127 ist explizit als "Original-Dienste direkt" gerahmt — BrightSky ist ein Drittanbieter-Spiegel, der selbst unabhängig von DWD ausfallen kann (eigene Infrastruktur, eigenes Ausfallrisiko, außerhalb dieses Projekts). Das Projekt akzeptiert diesen Trade-off bereits für den Radar-Pfad (`brightsky.py`, RADOLAN) — dort gibt es keine bessere Alternative. Für den Forecast-Pfad **gibt es** mit ICON-D2 eine echte DWD-eigene Quelle, der Kompromiss ist hier nicht nötig.
4. **Kein neuer Dependency-Bedarf.** GRIB2-Parsing ist seit #1143 gelöst (rasterio/GDAL), `bz2`-Entpacken ist Python-Stdlib. Der Mehraufwand von ICON-D2 gegenüber BrightSky ist Requestvolumen und eine neue Precip-Semantik-Prüfung, keine neue Technologie.

**Bewusst in Kauf genommener Nachteil:** ICON-D2 liefert **1 Datei pro Parameter pro Zeitschritt** (kein Multi-Zeitschritt-Bundle) — bei vollem 48h-Horizont und 3 Parametern (T2M, U10M/V10M als 2, Precip) bis zu ~144 HTTP-Downloads+bz2-Entpackungen pro Fetch. Das ist mehr als die 96 Calls, die schon bei AROME-FR (#1143) ein eigenes Zeitbudget (`FETCH_DEADLINE_SECONDS`) nötig machten. **Scoping-Konsequenz:** Horizont im MVP auf 24h begrenzen (analog AROME-FR-Vorgeschichte, dort startete #1143 bei 6h), macht ~4 Parameter × 24 ≈ 96 Calls — im selben Rahmen wie das bereits akzeptierte FR-Muster. PO kann Horizont später erweitern (wie bei FR von 6h auf 24h nach Freigabe).

**Offener empirischer Punkt für den `/20-analyse`-Spike (nicht in dieser Planung final verifiziert):** `tot_prec` ist laut DWD-Doku seit Laufbeginn **kumuliert** (nicht 1h-Rate wie ursprünglich für AROME angenommen, aber auch nicht identisch mit AROMEs tatsächlichem Verhalten — dort erwies sich die Doku-Annahme in Runde 1 als falsch, F003). Die Differenzbildung zwischen zwei aufeinanderfolgenden Zeitschritten muss **gegen echte, aufgezeichnete ICON-D2-Antworten mit einem Nicht-Null-Niederschlagswert verifiziert werden**, bevor die Formel in der Spec fixiert wird — dieselbe Lehre wie F003 aus #1143 (dort maskierte ein 0,0-Fixture den Fehler).

### Affected Files (geplant, analog #1143-Struktur)

| File | Change | Description |
|------|--------|--------------|
| `src/providers/dwd.py` | CREATE | Neue Klasse `DwdDirectProvider` (Registry-Key `de_direct`). Vorlage: `src/providers/meteofrance.py` (bz2-Entpacken statt direktem GRIB2, `_read_point_value` via rasterio wiederverwendbares Muster, httpx→`ProviderRequestError`-Übersetzung, Retry-Pattern aus `geosphere.py`) |
| `src/providers/regional_stubs.py` | MODIFY | `make_de_direct = partial(RegionalStubProvider, "de_direct")` (Zeile 102) entfernt; Modul-Docstring (Zeile 18: "Der verbleibende reale Provider landet in #1144") wird obsolet — nach diesem Slice bleibt kein offener Regions-Stub mehr |
| `src/providers/base.py` | MODIFY | `_load_providers()` (Zeile 183-186): Import `from providers.dwd import DwdDirectProvider` ergänzt, `register_provider("de_direct", make_de_direct)` → `register_provider("de_direct", DwdDirectProvider)` |
| `src/app/models.py` | MODIFY | `Provider`-Enum um `DWD = "DWD"` erweitert (analog `METEOFRANCE`, Zeile 31) |
| `src/providers/region_routing.py` | KEINE (voraussichtlich) | DE-Box (46,3–55,1/5,8–15,1... aktuell `47.2, 55.1, 5.8, 15.1`) — ICON-D2-Domäne (43,2–58,1°N/−3,9–20,3°E lt. Recherche) umschließt die Box vollständig; **wie bei AT (#1142) empirisch mit echten Grenzwert-Calls zu bestätigen**, bevor die Zeile final als "keine Änderung" gilt |
| `docs/reference/decision_matrix.md` | MODIFY | `de_direct`-Zeile von "Stub" auf "ICON-D2-Open-Data-Direktprovider (DWD)" fortgeschrieben |

**Schicht-Hinweis:** Alle Änderungen in Python-Core (`src/providers/`, `src/app/models.py`). Keine Go-API-Änderung, kein Frontend-Bezug.

### Datenmodell (verifiziert, unverändert wiederverwendbar)
`NormalizedTimeseries(meta, data)` (`models.py:161`), `ForecastDataPoint` (`models.py:93`) mit `t2m_c`/`wind10m_kmh`/`precip_1h_mm`. `__post_init__` (`models.py:145-156`) normalisiert **jeden** aware-Zeitstempel automatisch auf naive UTC — das ist der strukturelle Fix aus #1345 (Ernstfall: GeoSphere-tz-Crash), der **generisch für alle Provider inkl. eines neuen DE-Providers** gilt. Kein providerspezifischer tz-Code nötig, sofern `ForecastDataPoint` korrekt befüllt wird.

### Fallback-Seam (verifiziert, KEINE Änderung nötig)
`openmeteo.py:922-945` — bereits vollständig für alle drei Regionen verdrahtet (F001-Fix aus #1142 deckt `ProviderNotImplementedError`/`ProviderRequestError`/`ProviderNotFoundError` ab). Der Seam ruft `get_provider(direct_name).fetch_forecast(...)`, setzt `fallback_reason="cross_provider_total_outage"` und `fallback_model=direct_name`. Für DE ändert sich hier nichts — nur die Registry-Umhängung in `base.py` bewirkt den Wechsel vom Stub zum echten Provider.

### Nicht-Kaschieren-Invariante (ADR-0018, verbindlich)
4xx bleibt sichtbar (kein Retry, kein weiteres Ausweichen); 5xx/Timeout nach Retry-Ausschöpfung bleibt sichtbar (`has_error`). Gilt unverändert für `DwdDirectProvider`.

### Scope Assessment
- **Files:** 1 CREATE (`dwd.py`) + 3 MODIFY (`regional_stubs.py`, `base.py`, `models.py`) + `docs/reference/decision_matrix.md` (zählt nicht zum LoC-Limit) + 1 Testdatei mit ICON-D2-GRIB2-Fixtures + ggf. `region_routing.py` falls die Coverage-Prüfung eine Box-Anpassung ergibt
- **LoC:** geschätzt 180–250 Produktions-LoC (nahe/am 250-LoC-Limit, wie #1143) — Haupttreiber ist der bz2-Entpack- + Multi-File-Abruf- + Differenzbildungs-Code
- **Effort:** medium-high — GRIB2-Lesen ist gelöst (#1143-Vorlage), aber bz2-Entpacken, Precip-Differenzbildung und das höhere Requestvolumen (bis zu ~96 Calls im 24h-MVP-Horizont) sind neu und brauchen ein Zeitbudget-Pattern analog `FETCH_DEADLINE_SECONDS`
- **Risk:** MEDIUM — größtes Risiko ist die Precip-Semantik (empirisch zu verifizieren, s. o.), zweitgrößtes das Requestvolumen/Backend-Robustheit von `opendata.dwd.de` (bislang nicht production-getestet in diesem Projekt)

### Test-Strategie (mock-frei, analog #1143)
- Coverage-Routing (AC-2/AC-5-Äquivalent): rein deterministisch, kein HTTP
- 4xx/5xx-Verhalten: lokaler `ThreadingHTTPServer`, `monkeypatch.setattr("providers.dwd.BASE_URL", ...)` — Vorlage `tests/tdd/test_meteofrance_direct_fallback.py`
- **AC-1 (valide Normalisierung):** aufgezeichnetes ICON-D2-GRIB2-Fixture (`.bz2` entpackt oder Roh-`.bz2`, je nach Implementierung), lokal ausgeliefert, mit Plausibilitäts-Bounds (analog F001 aus #1143: nie nur `is not None`, sondern physikalische Bounds pro Feld — verhindert Cross-Parameter-Mixup)
- **Precip-Regressionstest (analog F003 aus #1143, PFLICHT):** echt aufgezeichnetes Nicht-Null-Niederschlags-Fixture, da ein 0,0-Fixture die Differenzbildungs-/Skalierungslogik nicht prüfen würde
- **E2E-Totalausfall-Test (PFLICHT, aus #1345-Lehre, "Abnahme-Vorlage für #1143/#1144"):** Open-Meteo-503-Fixture (alle Modelle) → `DwdDirectProvider`-Fixture (aufgezeichnet) → vollständiges `NormalizedTimeseries` durch den Seam — nicht nur der Fehlerpfad (wie `test_seam_falls_back_past_meteofrance_5xx_to_openmeteo_error` bei FR), sondern auch der **Erfolgspfad** durch den Seam, der bislang für keine Region als dediziertes Test explizit abgedeckt ist. Das ist der Nachweis, dass das Briefing im Ernstfall tatsächlich vollständig rendert (nicht nur, dass die Fehlerbehandlung sauber ist).
- **F001-Testauftrag aus Issue-Kommentar:** Direktanbieter-5xx am Einhängepunkt → Segment bleibt `has_error`, kein Crash — bereits durch den Seam-Test in obiger Form abgedeckt (Fehlerpfad-Variante).

## ACs-Entwurf (DRAFT, wird final in `/30-write-spec` mit PO-Freigabe festgezurrt)

- **AC-1:** Given eine Koordinate innerhalb der DWD/ICON-D2-Coverage (empirisch verifizierte Router-Box), When `DwdDirectProvider.fetch_forecast` aufgerufen wird, Then liefert die Antwort ein valides `NormalizedTimeseries` mit befüllten Basis-Feldern (`t2m_c`, `wind10m_kmh`, `precip_1h_mm`) für mindestens einen Datenpunkt, mit physikalisch plausiblen Werten (Bounds-Test, kein Cross-Parameter-Mixup).
- **AC-2:** Given eine Koordinate liegt außerhalb der DE-Router-Box, When `direct_provider_for(lat, lon)` aufgerufen wird, Then wird `"de_direct"` NICHT zurückgegeben.
- **AC-3:** Given DWD/`opendata.dwd.de` antwortet mit einem 4xx, When der Aufruf erfolgt, Then wird die `ProviderRequestError` sichtbar durchgereicht (kein Retry, kein drittes Ausweichen, ADR-0018).
- **AC-4:** Given DWD antwortet durchgehend mit 5xx/Timeout (nach Ausschöpfung der Retries), When das Segment verarbeitet wird, Then propagiert `DwdDirectProvider.fetch_forecast` eine `ProviderRequestError` (kein Crash), und der Seam fängt sie unverändert (Segment bleibt `has_error`).
- **AC-5 (Niederschlag-Differenzbildung, empirisch zu verifizieren):** Given ICON-D2 liefert `tot_prec` als seit Laufbeginn kumulierten Wert, When die Normalisierung läuft, Then wird `precip_1h_mm` korrekt als Differenz zweier aufeinanderfolgender Zeitschritte berechnet — verifiziert an einem echten Nicht-Null-Fixture (nicht nur an einem 0,0-Fixture, F003-Lehre).
- **AC-6 (Wind-Korrektheit):** Given ICON-D2 liefert U/V-Windkomponenten in m/s, When die Normalisierung läuft, Then entspricht `wind10m_kmh` `sqrt(u²+v²)*3.6`, gerundet auf 1 Nachkommastelle (identische Formel zu `geosphere._vector_to_speed_kmh`/`meteofrance._vector_to_speed_kmh`).
- **AC-7 (E2E-Totalausfall-Rendering, aus #1345-Lehre, NEU gegenüber Issue-Entwurf):** Given Open-Meteo hat für eine DE-Koordinate einen kompletten Totalausfall (alle Modelle 5xx/Timeout), When das Briefing für dieses Segment gerendert wird, Then wird ein vollständiges Segment aus `DwdDirectProvider`-Daten gerendert (nicht nur eine erfolgreiche `fetch_forecast`-Rückgabe isoliert getestet) — Test analog dem für #1345 vorgeschlagenen E2E-Muster (503-Fixture → Direktprovider-Fixture → Briefing rendert vollständig).
- **AC-8 (F001-Testauftrag aus Issue-Kommentar):** Given `DwdDirectProvider` wirft `ProviderRequestError` (5xx/Timeout) am Cross-Provider-Einhängepunkt, When der Seam in `openmeteo.py` das fängt, Then bleibt das Segment sichtbar `has_error` markiert (kein Crash mit einer neuen, unbehandelten Exception) — deckungsgleich mit AC-4, hier als expliziter End-to-End-Nachweis durch den Seam (nicht nur isolierter Provider-Unit-Test).

## Open Questions (an PO)

1. **Die eine zu bestätigende Richtungsentscheidung:** ICON-D2 Open Data statt MOSMIX/BrightSky als DE-Direktquelle (Begründung s. o. — konsistent mit ADR-0002 und dem AT/FR-Gittermuster).
2. **Horizont-Scoping:** MVP mit 24h-Vorhersagehorizont starten (wie ursprünglich bei AROME-FR), später erweiterbar? Reduziert Requestvolumen und LoC im ersten Schritt.
3. **Coverage-Box:** DE-Router-Box wird im Implementierungsschritt empirisch gegen echte ICON-D2-Grenzwert-Calls verifiziert (wie bei AT) — keine Vorab-Annahme in der Spec fixieren.

## Scope Assessment (Zusammenfassung)
- Files: ~1 CREATE + 3-4 MODIFY (analog #1143)
- LoC: ~180–250, nahe am Workflow-Limit. **Kein Override eigenmächtig vorwegnehmen:** sollte der Parser das Limit reißen, ist eine Scheibung (Parser-MVP, z. B. T2M+Wind zuerst und Precip als Folge-Slice, oder reduzierter Horizont) der richtige Weg — Entscheidung liegt beim PO in `/30-write-spec`, nicht vorab hier
- Risk: MEDIUM (Precip-Semantik empirisch offen, Requestvolumen-Backend-Robustheit ungetestet)
