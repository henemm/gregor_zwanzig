---
entity_id: issue_1162_radar_dpc
type: feature
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, radar, italy, dpc, protezione-civile]
---

# Radar-DPC: Regen-Nowcast für Italien (Issue #1162)

## Approval

- [ ] Approved

## Purpose

Italienische Orte durchlaufen die Nowcast-Fallback-Kette (`_fetch_frames_with_fallback`) aktuell ohne eine landesspezifische Radar-Quelle — sie landen je nach Position auf dem AROME-FR-Modell-Downscaling (nur NW-Italien, deckt lon bis 10.0) oder direkt auf dem globalen `minutely_15`-Fallback. Diese Spec ergänzt Radar-DPC (Protezione Civile, nationales italienisches Wetterradar) als eigene, präzisere Quelle für ganz Italien — analog zum kürzlich gelieferten GeoSphere-INCA-Slice für Österreich (#1161). Reale Radar-Beobachtung (SRI-Produkt, mm/h) ersetzt dabei Modell-Downscaling überall dort, wo DPC verfügbar ist; Gewitter-/Hagel-Erkennung nutzt (wie bei INCA) einen Open-Meteo-Sidecar, da SRI kein natives Konvektionsfeld liefert. Native DPC-Gewitterprodukte (HRD/LTG) sind explizit ausgelagert nach Folge-Issue #1174.

## Source

- **File:** `src/providers/radar_dpc.py` (neu), `src/services/radar_service.py` (erweitert), `src/providers/base.py` (erweitert), `pyproject.toml` (erweitert)
- **Identifier:** `RadarDPCProvider`, `RadarNowcastService._within_dpc`, `RadarNowcastService._fetch_radar_dpc`, `register_provider("radar_dpc", RadarDPCProvider)`
- **Schicht:** Python-Backend (`src/providers/`, `src/services/`) — kein Go, kein Frontend. Reiner Nowcast-Pfad; `src/services/risk_engine.py` (CAPE-basierter mehrtägiger Pfad) ist nicht betroffen.

## Estimated Scope

- **LoC:** ~200–250 (Provider ~150–180 + Service-Integration ~30–40 + Registrierung ~5 + Tests separat)
- **Files:** 3 produktiv (`radar_dpc.py` neu, `radar_service.py` erweitert, `base.py` erweitert) + `pyproject.toml` + 1 Testdatei (`tests/tdd/test_issue_1162_radar_dpc.py`)
- **Effort:** high (neue, komplett unverifizierte externe API — 3-stufiger REST-Ablauf, `origin`-Header-Pflicht unklar, neue System-Dependency `rasterio` für GeoTIFF-Punktextraktion)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.geosphere.GeoSphereProvider._request` (Retry-Pattern) | internal Vorbild | `tenacity`-Retry (502/503/504 + Connect/Timeout, 5 Versuche, 2–60s exponential backoff) 1:1 auf `RadarDPCProvider` zu übertragen — Referenz `docs/specs/modules/api_retry.md` |
| `RadarNowcastService._fetch_openmeteo_15(lat, lon, models=None)` | internal helper (bereits produktiv) | Liefert global `best_match`-Frames inkl. `is_convective` (WMO 95/96/99) — wird als Sidecar für den Konvektions-Indikator wiederverwendet, identisches Muster zu `_fetch_geosphere_inca` |
| `providers.brightsky.RadarFrame` | model (unverändert) | Zieltyp für den DPC-Adapter (`timestamp`, `precip_mm_h`, `is_convective`) |
| `rasterio` (neu) | external library | GeoTIFF-Georeferenzierung + Punktextraktion (`dataset.index(lon, lat)` + `.read(1)[row, col]`) — Pillow kann laut Recherche keine GeoTIFF-Tags auflösen |
| `providers.base.register_provider` | internal factory | Registrierung `register_provider("radar_dpc", RadarDPCProvider)` analog `geosphere`/`brightsky` |
| `services.trip_alert.TripAlertService.check_radar_alerts`, `services.trip_command_processor.py` (`### now`) | downstream consumer | Konsumieren `RadarNowcastService.get_nowcast()` transparent über die Fallback-Kette und `source_label()` — kein Code-Änderungsbedarf erwartet |
| ADR-0018 (Nicht-Kaschieren-Invariante) | Architekturentscheidung | Verbietet stillen Fallback auf `convective_checked=True` bei Sidecar-Ausfall — identische Anwendung wie im INCA-Pfad |

## Implementation Details

### `RadarDPCProvider` (`src/providers/radar_dpc.py`, neu)

3-Schritt-REST-Ablauf gegen `https://radar-api.protezionecivile.it/`, mit Retry-Dekorator analog `GeoSphereProvider._request`:

```
1. GET  /findLastProductByType?type=SRI
   -> { "time": <ms-timestamp UTC des letzten verfügbaren SRI-Produkts> }

2. POST /downloadProduct
   Body: {"productType": "SRI", "productDate": <ms-timestamp aus Schritt 1>}
   -> { "bucket": ..., "key": ..., "url": <S3-URL>, "expiresSeconds": ... }

3. GET  <S3-URL aus Schritt 2>
   -> Roh-GeoTIFF-Bytes (Content-Type image/tiff)
```

- Jeder ausgehende Request trägt einen `origin`-Header (Wert laut Doku zwingend — **empirisch während der Implementierung zu verifizieren**, siehe Known Limitations; kein Blocker für die Spec-Freigabe, aber Pflicht-Verifikationsschritt vor Merge).
- Retry-Dekorator (`tenacity`, `stop_after_attempt(5)`, `wait_exponential(min=2, max=60)`, `retry_if_exception` auf 502/503/504 + `httpx.ConnectError`/`httpx.ReadTimeout`) auf Schritt 1 und 2 (Schritt 3 ist ein presigned S3-Download, kein Retry auf API-Statuscodes nötig, aber derselbe Connect/Timeout-Schutz).
- Punktextraktion: `rasterio.open(io.BytesIO(tif_bytes))` → `dataset.index(lon, lat)` liefert `(row, col)` im Pixel-Raster → `dataset.read(1)[row, col]` liefert den SRI-Rohwert (mm/h laut Produktbeschreibung; Einheiten-Umrechnungsfaktor ist während der Implementierung gegen reale Werte zu verifizieren, da die API-Doku keinen expliziten Skalierungsfaktor nennt).
- Methode `fetch_nowcast(lat, lon) -> list[RadarFrame]`: EIN GeoTIFF liefert EINEN Zeitstempel (den aus Schritt 1) und EINEN Wert an der Zielkoordinate — anders als INCA (Zeitreihe) liefert DPC pro Aufruf nur ein einziges `RadarFrame` (aktuellster verfügbarer SRI-Scan, 5-Minuten-Update). Das ist ein struktureller Unterschied zu `_fetch_geosphere_inca`, der bei `_derive_result` (Onset-Berechnung über ein Zeitfenster) zu berücksichtigen ist: mit nur einem Frame ist `onset_minutes` entweder `0` (falls `precip_mm_h >= _DRY_THRESHOLD_MM_H`) oder `None` (trocken) — keine Multi-Frame-Onset-Vorhersage wie bei INCA/AROME-FR.
- Fail-soft: jeder der drei Schritte kann scheitern (HTTP-Fehler, leere/unerwartete JSON-Struktur, `rasterio`-Decode-Fehler) → `except Exception -> []` auf Ebene des Providers oder des Service-Adapters (analog `_fetch_geosphere_inca`).
- Registrierung: `register_provider("radar_dpc", RadarDPCProvider)` in `src/providers/base.py::_load_providers()` (try/except ImportError-Block wie bei den bestehenden Einträgen).

**Reale API-Abweichungen (während der Implementierung empirisch festgestellt, gegenüber der ursprünglichen Doku-Annahme oben in Schritt 1–3 korrigiert):**
- `findLastProductByType`-Response ist `{"total": N, "lastProducts": [{"time": <ms>, ...}]}`, NICHT `{"time": ...}` direkt — Zeitstempel liegt unter `lastProducts[0].time`.
- Das GeoTIFF-CRS ist **projiziert** (Transverse Mercator, Zentrum ~12.5°E/42°N), **nicht** lon/lat. `dataset.index(lon, lat)` ohne Reprojektion wäre falsch — die Zielkoordinate muss vor dem Pixel-Sampling via `rasterio.warp.transform` von EPSG:4326 ins Dataset-CRS transformiert werden.
- Nodata-Wert ist `-9999` (in den Metadaten nicht als `ds.nodata` gesetzt) — Werte `< 0` werden als trocken (`0.0`) behandelt.
- Der `origin`-Header ist entgegen der Doku-Angabe empirisch **nicht** erforderlich (beide Endpoints antworten identisch mit/ohne Header) — die entsprechende Known-Limitation unten ist damit ausgeräumt.
- `rasterio` installiert sauber ohne System-GDAL-Paket (manylinux-Wheel mit gebündeltem GDAL) — die entsprechende Known-Limitation unten ist damit ausgeräumt.

### `radar_service.py` (erweitert)

- Neue Konstanten (grobe IT-BBox, empirisch zu verifizieren): `_DPC_LAT_MIN = 36.0`, `_DPC_LAT_MAX = 47.5`, `_DPC_LON_MIN = 6.5`, `_DPC_LON_MAX = 19.0`.
- `_within_dpc(lat, lon) -> bool`: reines Rechteck-Gate, analog `_within_inca`/`_within_arome_france`.
- `_fetch_radar_dpc(lat, lon) -> list`: ruft `RadarDPCProvider().fetch_nowcast(lat, lon)`, holt zusätzlich den Open-Meteo-Sidecar (`self._fetch_openmeteo_15(lat, lon)`) für `is_convective` — identisches Merge-Muster zu `_merge_convective` in `_fetch_geosphere_inca` (Toleranz ±5 Min), inkl. `self._convective_checked = False` bei Sidecar-Ausfall (ADR-0018). Try/except mit `except -> []` auf Gesamtebene (Provider-Fehler = Fallback zur nächsten Quelle).
- Einbau in `_fetch_frames_with_fallback` **vor** dem AROME-FR-Check:
  ```python
  if _within_dpc(lat, lon):
      frames = self._fetch_radar_dpc(lat, lon)
      if frames:
          return frames, "DPC"

  if _within_arome_france(lat, lon):
      ...
  ```
  Begründung (aus Analyse-Phase übernommen): reale Radar-Beobachtung schlägt Modell-Downscaling — analog dazu steht BrightSky (Radar) bereits vor INCA in derselben Kette.
- Neuer Eintrag in `_SOURCE_LABELS`: `"DPC": "Radar-DPC (Protezione Civile IT)"`.

### `pyproject.toml` (erweitert)

Neue Dependency `rasterio` im `[project].dependencies`-Block. Moderne manylinux-Wheels bündeln GDAL/PROJ (kein System-GDAL-Paket auf Ubuntu 24.04 erwartet nötig) — **muss vor/während der Implementierung empirisch bestätigt werden** (`uv add rasterio` im Worktree, echter `import rasterio` + Öffnen einer realen DPC-TIF-Datei).

## Expected Behavior

- **Input:** IT-Koordinaten innerhalb der DPC-BBox (z. B. Rom `41.9028, 12.4964` oder Mailand `45.4642, 9.1900`) für `get_nowcast()` bzw. den Alert-Tick.
- **Output:** Bei DPC-Erreichbarkeit liefert der Nowcast für italienische Orte eine reale Radar-Regenintensität (`source == "DPC"`) statt Modell-Downscaling; Gewitter/Hagel-Eskalation läuft über denselben Open-Meteo-Sidecar wie bei INCA. Bei DPC-Ausfall greift unverändert die bestehende Kette (AROME-FR/ICON-D2/`minutely_15`).
- **Side effects:** Drei zusätzliche HTTP-Calls (2× DPC-API + 1× S3-Download) plus ein Open-Meteo-Sidecar-Call pro DPC-Nowcast-Anfrage für IT-Koordinaten. Kein zusätzlicher State, kein neuer Alert-Typ — bestehende Alert-Throttle-Logik in `trip_alert.py` bleibt unverändert.

## Acceptance Criteria

- **AC-1:** Given eine reale IT-Koordinate innerhalb der DPC-BBox (z. B. Rom `41.9028, 12.4964`) / When `RadarDPCProvider().fetch_nowcast(lat, lon)` den vollen 3-Schritt-Ablauf gegen die echte API durchläuft / Then liefert er ein nicht-leeres `RadarFrame` mit einem Zeitstempel innerhalb der letzten ~15 Minuten (SRI-Update-Intervall 5 Min, Toleranz für API-Latenz) und einem plausiblen `precip_mm_h`-Wert (numerisch, `>= 0.0`, `< 500.0` als Plausibilitäts-Obergrenze gegen Decoding-Fehler).
  - Test: Echter HTTP-Call gegen `radar-api.protezionecivile.it` (kein Mock) mit fester IT-Koordinate; assert Frame vorhanden, Zeitstempel-Alter plausibel, `precip_mm_h` im plausiblen Bereich. Kein Dateiinhalt-Check.

- **AC-2:** Given eine IT-Koordinate innerhalb der DPC-BBox ohne injizierten `frame_source` (also über die echte Source-Chain) / When `RadarNowcastService().get_nowcast(lat, lon)` läuft / Then liefert das Ergebnis ein `NowcastResult` mit `source == "DPC"` (sofern DPC zum Testzeitpunkt erreichbar; Fail-Soft-Kette bleibt sonst unverändert aktiv und ein Fallback-`source`-Wert ist ebenfalls ein gültiges Testergebnis, sofern dokumentiert) — end-to-end echter Verhaltensnachweis, kein DI-Seam.
  - Test: Echter Aufruf ohne DI-Seam gegen die produktive Source-Chain (analog zu `test_ac4_inca_live_get_nowcast_has_convective_checked_field` in `test_issue_1161_inca_convective.py`); assert `NowcastResult.source in {"DPC", "AROME-FR", "ICON-D2", "minutely_15"}` mit klarer Präferenz-Assertion für `"DPC"` als Haupterwartung, Fallback-Werte werden geloggt/dokumentiert statt den Test hart scheitern zu lassen.

- **AC-3:** Given der DPC-3-Schritt-Ablauf schlägt fehl (z. B. durch eine absichtlich ungültige/nicht erreichbare Endpoint-Konfiguration im Testkontext, real ausgelöst, kein Mock der Exception) / When `_fetch_radar_dpc` bzw. `get_nowcast` für eine IT-Koordinate läuft / Then wird kein Absturz ausgelöst, die Methode liefert `[]` zurück, und die Fallback-Kette liefert stattdessen Frames aus der nächsten verfügbaren Quelle (AROME-FR/ICON-D2/`minutely_15`) mit entsprechendem `source`-Wert.
  - Test: Realer Fehlerpfad — z. B. echter HTTP-Call gegen eine bewusst ungültige DPC-Endpoint-URL/Timeout-Konfiguration (kein `Mock()`/`patch()`), der den Fail-Soft-Zweig real auslöst; assert `_fetch_radar_dpc` liefert `[]`, und `get_nowcast` für dieselbe Koordinate liefert ein `NowcastResult` mit einer der Fallback-Sources. Belegt echtes Verhalten, kein Dateiinhalt-Check.

- **AC-4:** Given ein DPC-Frame und ein Open-Meteo-Sidecar-Frame mit Timestamp innerhalb `T ± 5 Min` und `weather_code ∈ {95, 96, 99}` / When der interne Merge-Schritt in `_fetch_radar_dpc` läuft / Then trägt das zurückgegebene DPC-`RadarFrame` `is_convective=True`, während `precip_mm_h` weiterhin aus der DPC-SRI-Quelle stammt; scheitert der Sidecar-Call komplett, wird `NowcastResult.convective_checked == False` gesetzt und `format_now_text(result)` enthält den Hinweis „Gewitter-Check nicht verfügbar.".
  - Test: Zwei Teiltests analog `test_ac1_inca_merges_convective_flag_from_sidecar`/`test_ac3_inca_sidecar_failure_sets_convective_checked_false` aus `test_issue_1161_inca_convective.py` — echte (nicht gemockte) DPC- und Open-Meteo-`RadarFrame`-Objekte durch den Merge-Helper geschickt (Erfolgsfall), sowie ein real ausgelöster Sidecar-Fail-Pfad (Fehlerfall); assert `is_convective`/`convective_checked`/Text jeweils wie beschrieben. Kein Mock/patch/MagicMock.

- **AC-5 (Grenzfall BBox-Reihenfolge):** Given eine Koordinate knapp außerhalb der DPC-BBox (`lat/lon` außerhalb `_DPC_LAT_MIN/MAX`/`_DPC_LON_MIN/MAX`), aber innerhalb der bestehenden AROME-FR-BBox (z. B. eine Koordinate in Süd-Frankreich nahe der italienischen Grenze) / When `RadarNowcastService().get_nowcast(lat, lon)` läuft / Then wird `_within_dpc` korrekt `False` zurückgeben und die Fallback-Kette nutzt weiterhin AROME-FR (`source == "AROME-FR"`, sofern erreichbar) — Beweis, dass die neue DPC-Prüfung die bestehende AROME-FR-Abdeckung nicht verdrängt.
  - Test: Reiner Pure-Logic-Test von `_within_dpc(lat, lon)` mit einer Koordinate außerhalb der DPC-Box, kombiniert mit einem echten `get_nowcast`-Aufruf derselben Koordinate; assert `_within_dpc` liefert `False` UND `_within_arome_france` liefert `True` für dieselbe Koordinate UND `NowcastResult.source == "AROME-FR"` (sofern AROME-FR erreichbar). Kein Mock.

- **AC-6 (PO-Entscheidung, nachträglich während der Implementierung getroffen — Korsika → DPC):** Given Korsika liegt geografisch sowohl innerhalb der bestehenden AROME-FR-BBox als auch innerhalb der neuen DPC-BBox (Korsika lon ~9.0 liegt zwischen Sardinien lon ~8–9.5, ein Rechteck kann beide nicht trennen, ohne Sardinien auszuschließen) / When eine Korsika-Koordinate (z. B. `42.18, 9.0`) `RadarNowcastService().get_nowcast(lat, lon)` durchläuft / Then liefert das Ergebnis `source == "DPC"` (sofern DPC erreichbar), NICHT mehr `"AROME-FR"` — PO-Entscheidung 2026-07-09: reale Radar-Beobachtung schlägt Modell-Downscaling, auch für das GR20-Flaggschiff-Gebiet. `_within_arome_france(Korsika)` bleibt weiterhin `True` (unverändert), wird aber durch die vorgeschaltete DPC-Prüfung in der Fallback-Kette abgefangen, bevor AROME-FR geprüft wird.
  - Test: Bestehende Korsika-Assertions in `tests/tdd/test_feature_734_arome_france_nowcast.py` (`test_ac1_arome_france_real_fetch`, `test_ac2_chain_routing`) wurden von `source == "AROME-FR"` auf `source == "DPC"` aktualisiert — Regressionstest, kein Mock.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion (vorgeschlagen) | Testdatei |
|----|------------------------------|-----------|
| AC-1 | `test_ac1_dpc_provider_returns_real_frame_at_it_coordinate` | `tests/tdd/test_issue_1162_radar_dpc.py` |
| AC-2 | `test_ac2_dpc_live_get_nowcast_uses_dpc_source_for_it_coordinate` | `tests/tdd/test_issue_1162_radar_dpc.py` |
| AC-3 | `test_ac3_dpc_failure_falls_back_to_next_source` | `tests/tdd/test_issue_1162_radar_dpc.py` |
| AC-4 | `test_ac4_dpc_merges_convective_flag_from_sidecar`, `test_ac4_dpc_sidecar_failure_sets_convective_checked_false` | `tests/tdd/test_issue_1162_radar_dpc.py` |
| AC-5 | `test_ac5_dpc_bbox_boundary_defers_to_arome_fr` | `tests/tdd/test_issue_1162_radar_dpc.py` |
| AC-6 | `test_ac1_arome_france_real_fetch`, `test_ac2_chain_routing` (Korsika-Assertions aktualisiert) | `tests/tdd/test_feature_734_arome_france_nowcast.py` |

## Known Limitations

- ~~`origin`-Header-Pflicht unverifiziert~~ **AUSGERÄUMT:** empirisch bestätigt, dass beide Endpoints identisch mit/ohne `origin`-Header antworten — kein Blocker.
- **Reale Latenz des 3-stufigen API-Calls:** in den Live-Tests ~1–2s gemessen — unauffällig gegenüber der < 10s-Anforderung aus `radar_nowcast.md` AC-3. Keine Cache-Strategie in dieser Spec nötig; bei künftig beobachteter Verschlechterung (z. B. unter Last) ist eine Cache-Strategie (analog INCA) ein mögliches Folge-Issue.
- ~~`rasterio`-Systemabhängigkeit unverifiziert~~ **AUSGERÄUMT:** installiert sauber ohne System-GDAL-Paket auf Ubuntu 24.04 (manylinux-Wheel mit gebündeltem GDAL 3.12.1).
- **GeoTIFF-CRS ist projiziert, nicht lon/lat:** anders als in der ursprünglichen Implementation-Details-Annahme angenommen, erfordert die Punktextraktion eine Reprojektion (EPSG:4326 → Dataset-CRS via `rasterio.warp.transform`) vor dem Pixel-Sampling — siehe korrigierter Implementierungs-Abschnitt oben. Ohne diesen Schritt wäre der extrahierte Wert an der falschen Stelle im Raster.
- **Rate-Limits der DPC-API nicht dokumentiert:** Bei proaktiven Alerts (Scheduler-Tick über alle IT-Trips) könnte häufiges Polling gegen unbekannte Limits laufen. Eine Cache-Strategie (analog INCA, 300s/60s) ist eine mögliche Folge-Optimierung, aber nicht Pflicht-Scope dieser Spec.
- **Kein Multi-Frame-Onset:** Anders als INCA (Zeitreihe über mehrere 15-Min-Schritte) liefert ein DPC-SRI-Abruf nur den aktuellsten Scan (ein `RadarFrame`). `onset_minutes` ist im DPC-Pfad daher binär (`0` oder `None`), keine Vorhersage eines Regenbeginns in 20–60 Minuten wie bei den Multi-Frame-Quellen. Diese Einschränkung ist strukturell (SRI ist ein Beobachtungs-, kein Vorhersageprodukt) und nicht durch diese Spec auflösbar.
- **Kein natives Gewitter/Hagel-Signal aus DPC:** SRI liefert kein Konvektionsfeld; die Erkennung läuft über denselben Open-Meteo-Sidecar wie bei INCA und verschenkt damit den potenziellen DPC-Mehrwert aus `HRD` (Heavy Rain Detection) oder `LTG` (Blitzaktivität/LAMPINET). Das ist bewusst ausgelagert nach **Folge-Issue #1174** ("Radar-DPC: natives Gewitter/Hagel-Signal für Italien") und explizit nicht Teil dieser Spec.
- **BBox-Grenzen approximativ:** `_DPC_LAT_MIN/MAX`/`_DPC_LON_MIN/MAX` sind eine grobe Schätzung (lat 36.0–47.5, lon 6.5–19.0), nicht empirisch anhand der tatsächlichen DPC-Rasterabdeckung verifiziert. Eine Nachjustierung ist als separates Issue vorzunehmen, falls sich in der Praxis Lücken oder Fehlklassifikationen zeigen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Nicht-Kaschieren-Invariante bei Provider-/Quell-Ausfall)
- **Rationale:** ADR-0018 verbietet explizit stille Fallbacks, die einen Ausfall als „grün"/„geprüft" erscheinen lassen. Ein stiller `convective_checked=True` bei gescheitertem Open-Meteo-Sidecar-Call im DPC-Pfad wäre strukturell identisch zu dem in ADR-0018 beschriebenen Muster — analog zur bereits umgesetzten Anwendung im INCA-Pfad (#1161). Diese Spec wendet dieselbe Nicht-Kaschieren-Logik an: sichtbares additives Signal (`convective_checked`) statt Kaschieren. Kein neues ADR nötig — bestehendes ADR-0018 deckt das Muster inhaltlich ab; diese Spec ist eine Anwendung, keine neue Architekturentscheidung.

## Changelog

- 2026-07-09: Initial spec created (Issue #1162), Split-Entscheidung aus Analyse-Phase übernommen (natives DPC-Gewittersignal → #1174)
- 2026-07-09: Nach GREEN-Implementierung aktualisiert — 3 reale API-Abweichungen dokumentiert (Response-Struktur, CRS-Reprojektion, Nodata-Wert), 2 Known Limitations ausgeräumt (`origin`-Header nicht nötig, `rasterio` ohne System-GDAL), AC-6 ergänzt (PO-Entscheidung: Korsika → DPC statt AROME-FR, da geografisch nicht per Rechteck von Sardinien trennbar)
