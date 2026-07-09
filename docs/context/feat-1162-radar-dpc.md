# Context: feat-1162-radar-dpc

## Request Summary
Für italienische Orte soll `RadarNowcastService` (Gefahren-/Regen-/Gewitter-Nowcast) statt der generischen Open-Meteo-Fallback-Kette das nationale italienische Radar-DPC (Protezione Civile) als regionsspezifische Quelle nutzen — analog zum kürzlich gelieferten GeoSphere-INCA-Slice für Österreich (#1161). Fail-soft-Pflicht: fehlt/schlägt DPC fehl, muss die bestehende Kette (AROME-FR/ICON-D2/minutely_15) unverändert greifen.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | Zentrale Fallback-Kette (`_fetch_frames_with_fallback`); hier muss ein neuer BBox-Zweig `_within_dpc(lat, lon)` + `_fetch_radar_dpc(lat, lon)` ergänzt werden, Source-Label `"DPC"` in `_SOURCE_LABELS`. Reihenfolge/Position relativ zu AROME-FR (deckt bereits NW-Italien bis lon 10.0) ist eine Analyse-Entscheidung. |
| `src/providers/geosphere.py` | Direktes Vorbild für einen neuen `src/providers/radar_dpc.py`: eigene Provider-Klasse mit `_request`-Methode, `httpx`-Client, `tenacity`-Retry (502/503/504 + Connect/Timeout, Referenz api_retry.md), fail-soft `except -> None/[]`. |
| `src/services/radar_service.py::_fetch_geosphere_inca` | Konkretes Adapter-Pattern: Provider-Call → Umrechnung in `RadarFrame`-Liste (mm/Intervall → mm/h), Convective-Sidecar-Merge via `_merge_convective`, `_convective_checked`-Flag bei Sidecar-Ausfall (ADR-0018: Fehler nie stillschweigend als "kein Gewitter" umdeuten). |
| `src/providers/brightsky.py` | Definiert `RadarFrame`-Dataclass (`timestamp`, `precip_mm_h`, `is_convective`) — Zieltyp für den DPC-Adapter. |
| `docs/specs/modules/radar_nowcast.md` | Genehmigte Basis-Spec (Issue #656) inkl. AC-Format/Test-Mapping-Konvention; hier muss ein neuer Abschnitt/Changelog-Eintrag für DPC ergänzt werden (analog zu den bestehenden INCA/AROME-FR/ICON-D2-Erweiterungen). |
| `src/providers/region_routing.py`, `src/providers/regional_stubs.py` | **Anderes** Subsystem (Cross-Provider-Fallback #1141 für den Gesamt-Forecast bei Open-Meteo-Totalausfall) — nicht verwechseln mit der Nowcast-Provider-Auswahl in `radar_service.py`. Kein direkter Bezug, nur als Namens-Kollisions-Warnung relevant (`at_direct`/`de_direct`/`fr_direct` sind NICHT dasselbe wie Nowcast-Sources). |
| `src/services/trip_alert.py`, `src/services/radar_alert_service.py` | Konsumenten von `RadarNowcastService.get_nowcast()` für proaktive Alerts — profitieren automatisch, kein Code-Änderungsbedarf erwartet (Source-Label wird über `source_label()` generisch aufgelöst). |
| `tests/tdd/test_issue_1161_inca_convective.py`, `docs/specs/modules/*inca*` (Workflow #1161, git-Commit adba42e5) | Frisch gelieferte Schwester-Implementierung — als 1:1-Testmuster für Struktur/AC-Format/Adversary-Ablauf heranziehen. |

## Existing Patterns

- **BBox-Gate + Provider-Fetch + Fail-Soft:** jede Quelle folgt demselben Dreischritt: `_within_X(lat,lon)` (reines Rechteck-Gate) → `_fetch_X(lat,lon)` (try/except, loggt Warnung, gibt `[]` zurück bei Fehler) → Fallback zur nächsten Quelle in der Kette.
- **Konvektions-Erkennung uneinheitlich pro Quelle:** RADOLAN/INCA haben kein natives Gewitter-Feld (INCA nutzt Open-Meteo-Sidecar für `is_convective`), AROME-FR/ICON-D2 nutzen WMO-`weather_code` direkt aus derselben Open-Meteo-Response. DPC hat potenziell **eigene** Gewitter-/Hagel-nahe Produkte (siehe Risiken), was einen dritten Erkennungspfad bedeuten könnte.
- **Source-Label-Dict** (`_SOURCE_LABELS`) ist die einzige Stelle, an der ein neuer Source-Key ein menschenlesbares Label braucht — sonst Fallback auf Rohschlüssel (forward-kompatibel, aber unschön für E-Mail/Alert-Texte).
- **Retry-Konvention:** `docs/specs/modules/api_retry.md` (5 Versuche, 2–60s, exponential backoff) gilt für alle Provider-Requests, siehe `geosphere.py::_request`.

## Dependencies

- **Upstream:** `httpx` (vorhanden), `tenacity` (vorhanden), `pillow` (vorhanden — reicht für einfache PNG/JPEG, **nicht** für GeoTIFF-Georeferenzierung). Aktuell **keine** Geo-Raster-Bibliothek (`rasterio`/GDAL/`numpy`/`tifffile`) im Projekt (`pyproject.toml` geprüft).
- **Downstream:** `RadarNowcastService.get_nowcast()` wird konsumiert von `trip_command_processor.py` (`### now`-Befehl), `trip_alert.py`/`radar_alert_service.py` (proaktive Alerts), `format_now_text()` (E-Mail/SMS/Telegram-Text). Kein Code-Änderungsbedarf dort erwartet, da die Fallback-Kette transparent erweitert wird.

## Existing Specs

- `docs/specs/modules/radar_nowcast.md` — Basis-Spec (Issue #656), muss um DPC-Abschnitt erweitert werden.
- Analoge Erweiterungs-Specs als Vorlage: `radar_nowcast_france.md` (AROME-FR), `radar_nowcast_icon_d2.md`, `radar_nowcast_inca_fix.md`.
- Kein `docs/reference/decision_matrix.md`-Eintrag für Italien/DPC vorhanden — diese Matrix betrifft nur die MET/MOSMIX-Forecast-Quellenwahl, nicht Nowcast; vermutlich kein Update nötig.

## Recherche: Radar-DPC API (extern, Stand 2026-07-09)

- **Basis-URL:** `https://radar-api.protezionecivile.it/`
- **Ablauf (2 Schritte, KEIN WebSocket nötig — REST reicht):**
  1. `GET /findLastProductByType?type=<PRODUCT>` → JSON mit letztem verfügbaren Zeitstempel (`time` in ms UTC).
  2. `POST /downloadProduct` mit Body `{"productType": "...", "productDate": <ms-timestamp>}` → JSON mit S3-Metadaten (`bucket`, `key`, `url`, `expiresSeconds`) für eine **TIF-Datei** (Rohdaten-Rasterbild).
- **Auth:** kein API-Key, aber `origin`-Header zwingend erforderlich (sonst vermutlich Reject — noch nicht empirisch verifiziert).
- **Relevante Produkte:** `SRI` (Surface Rainfall Intensity, mm/h, 5-Min-Update — direktes Äquivalent zu unserem `precip_mm_h`), `VMI` (Vertical Maximum Intensity, dBZ-Reflektivität, 5-Min), `HRD` (Heavy Rain Detection, Shapefile mit Schwere-Index — potenziell Gewitter-Indikator), `LTG` (Blitzaktivität/LAMPINET, 10-Min — potenziell Gewitter-Indikator), `SRT1/CUM3/6/12/24` (Niederschlagssummen).
- **Geografische Abdeckung:** national fix ("area spaziale è fissa"), kein dokumentiertes Bounding-Box-Detail für einzelne Produkte gefunden — muss empirisch verifiziert werden (vermutlich ganz Italien inkl. Alpenrand, potenziell mit Überlappung zur bestehenden AROME-FR-BBox in NW-Italien).
- **Rate-Limits:** nicht dokumentiert.

Quellen: [REST API — radar-dpc-docs](https://dpc-radar.readthedocs.io/it/latest/api.html), [Piattaforma-Beschreibung](https://dpc-radar.readthedocs.io/it/latest/platform.html)

## Risks & Considerations

1. **Kein Punkt-Query, sondern Rasterbild (Kern-Risiko):** anders als GeoSphere INCA (das eine fertige Zeitreihe für lat/lon liefert) liefert Radar-DPC ein flächendeckendes GeoTIFF. Um daraus einen Wert an einer konkreten Koordinate zu extrahieren, braucht es Georeferenzierung (Pixel↔Koordinaten-Transformation) — typischerweise via `rasterio`/GDAL, was aktuell **keine** Projekt-Dependency ist. Das ist der zentrale Analyse-Punkt: entweder (a) neue Geo-Raster-Dependency einführen, (b) TIF-Header manuell parsen (GeoTIFF-Tags enthalten Transform-Matrix, aufwändig aber machbar ohne GDAL), oder (c) prüfen ob ein alternativer, punktbasierter Zugang existiert (z. B. über eine andere DPC-Schnittstelle), was noch nicht gefunden wurde.
2. **Kein natives Gewitter/Hagel-Feld für `is_convective`:** ähnlich wie bei INCA fehlt SRI ein direktes Konvektions-Flag. `HRD` (Schwere-Index) oder `LTG` (Blitzdichte) könnten das leisten, brauchen aber eigene Abfrage/Parsing-Logik — ODER es wird wie bei INCA ein Open-Meteo-Sidecar für `is_convective` wiederverwendet (einfacherer, konsistenter Pfad, aber verschenkt den DPC-Mehrwert, den Issue #1162 im Titel explizit nennt: "erkennt Gewitter/Hagel für Österreich" war der #1161-Claim — hier müsste DPC dasselbe für Italien leisten, nicht nur Regen).
3. **BBox-Überlappung mit AROME-FR:** `_AROME_FR_LON_MIN/MAX = -5.5..10.0`, `_AROME_FR_LAT_MIN/MAX = 41.0..51.5` deckt bereits NW-Italien ab. Reihenfolge in `_fetch_frames_with_fallback` muss geklärt werden: DPC vor oder nach AROME-FR prüfen? (Nationale, radar-basierte DPC-Daten sind vermutlich präziser als das AROME-FR-Modell-Downscaling — spricht für DPC-Vorrang innerhalb Italiens.)
4. **`origin`-Header-Pflicht unverifiziert:** muss in der Analyse-Phase gegen die echte API getestet werden (kein Mock erlaubt laut Projekt-Policy) — ggf. reicht ein synthetischer `Origin`-Header, ggf. ist eine Whitelist-Domain nötig, was den auth-freien Zugang faktisch einschränken würde.
5. **S3-Presigned-URL-Zwischenschritt:** `downloadProduct` liefert nicht direkt die Datei, sondern eine S3-URL mit `expiresSeconds` — ein dritter HTTP-Call ist nötig, was Latenz addiert (Nowcast-Alert-Pfad hat Zeitdruck, siehe AC-3 der Basis-Spec: < 10s Antwortzeit für `### now`).
6. **Rate-Limits unbekannt:** bei proaktiven Alerts (Scheduler-Tick über alle IT-Trips) könnte häufiges Polling gegen unbekannte Limits laufen — Analyse sollte Cache-Strategie (analog INCA 300s/60s laut Memory) mitdenken.

## Nächster Schritt
`/20-analyse` — insbesondere Klärung des GeoTIFF-Punktabfrage-Ansatzes (Dependency-Entscheidung) und der Konvektions-Erkennungsstrategie, bevor die Spec geschrieben wird.

---

## Analysis

### Type
Feature (neue regionsspezifische Nowcast-Quelle, analog #1161).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/radar_dpc.py` | CREATE | Neuer Provider (~150–200 LoC): 3-Schritt-REST-Call (`findLastProductByType` → `downloadProduct` → S3-URL), Retry via `tenacity` (Vorbild `geosphere.py`), GeoTIFF-Download + Punkt-Extraktion via `rasterio`, Rückgabe als `RadarFrame`-Liste. |
| `src/providers/base.py` | MODIFY | `register_provider("radar_dpc", RadarDPCProvider)` ergänzen. |
| `src/services/radar_service.py` | MODIFY (~30–40 LoC) | Neue IT-BBox-Konstanten, `_within_dpc()`, `_fetch_radar_dpc()` in `_fetch_frames_with_fallback` (Position **vor** AROME-FR), neuer Eintrag `"DPC"` in `_SOURCE_LABELS`. |
| `pyproject.toml` | MODIFY | Neue Dependency `rasterio` (bündelt GDAL/PROJ als manylinux-Wheel, kein System-GDAL nötig — empirisch zu verifizieren). |
| `docs/specs/modules/issue_1162_dpc_convective.md` (oder vergleichbarer Name) | CREATE | Neue Spec, 1:1-Vorlage `issue_1161_inca_convective.md` (Abschnittsstruktur, AC-Format Given/When/Then, ADR-0018-Bezug). |
| `docs/reference/decision_matrix.md` | MODIFY (optional) | Neue Sektion "Regionale Nowcast-Provider-Dispatch" — aktuell nur MET/MOSMIX-Forecast-Auswahl dokumentiert, Radar-Fallback-Kette fehlt dort komplett (auch für INCA/AROME/ICON-D2 rückwirkend nicht dokumentiert — kein Scope-Zwang für #1162, aber Erwähnung wert). |
| `tests/tdd/test_issue_1162_radar_dpc.py` | CREATE | TDD RED, 1:1-Struktur zu `test_issue_1161_inca_convective.py`: 4 AC-Tests, echte HTTP-Calls (kein Mock), reale IT-Koordinate (z.B. Mailand 45.4642/9.1900). |

**Nicht betroffen:** `region_routing.py`/`regional_stubs.py` (anderes Subsystem, Cross-Provider-Fallback #1141), `trip_alert.py`/`radar_alert_service.py`/`trip_command_processor.py` (Konsumenten, profitieren transparent über `source_label()`).

### Scope Assessment
- Files: 5 modify/create + 1 optionale Doku-Datei
- Estimated LoC: ~350–450 (Provider + Service-Integration + Tests) — **über dem 250-LoC-Default-Limit**
- Risk Level: **HIGH** (neue externe API komplett unverifiziert: `origin`-Header-Pflicht, Latenz des 3-stufigen Calls gegen <10s-AC aus der Basis-Spec, unbekannte Rate-Limits; neue System-Dependency `rasterio`)

### Technical Approach

1. **GeoTIFF-Punktextraktion:** `rasterio` (moderne manylinux-Wheels bündeln GDAL/PROJ, kein System-Paket-Install erwartet nötig — **vor Spec-Freigabe empirisch bestätigen**: `uv add rasterio` im Worktree, echten Read + Punkt-Sample gegen eine reale DPC-TIF-Datei). Pillow scheidet aus (bestätigt: keine GeoTIFF-Tag-Unterstützung).
2. **Konvektions-Erkennung (Gewitter/Hagel):** MVP nutzt den bestehenden Open-Meteo-Sidecar (identisches Pattern zu INCA/#1161, `convective_checked=False`-Fail-Soft nach ADR-0018 bei Sidecar-Ausfall). Native DPC-Produkte (HRD/LTG) sind ein separater Fast-Follow — würden Scope und unverifizierte API-Fläche in diesem Workflow zusätzlich sprengen.
3. **BBox-Reihenfolge:** IT-spezifische BBox (grob lat 36–47.5, lon 6.5–19, empirisch zu verifizieren) wird **vor** AROME-FR geprüft — reale Radar-Beobachtung schlägt Modell-Downscaling, analog dazu steht BrightSky (Radar) bereits vor INCA in der bestehenden Kette.
4. **Implementierungsreihenfolge:** (a) Provider-Adapter isoliert gegen die echte API bauen und die drei Kern-Unbekannten klären (`origin`-Header, reale Latenz, `rasterio`-Extraktion), bevor `radar_service.py` angefasst wird; (b) BBox-Integration in die Fallback-Kette; (c) Spec + Tests nach INCA-Vorlage.
5. **Spec-Vorlage:** `docs/specs/modules/issue_1161_inca_convective.md` 1:1 als Struktur-Vorbild (Approval/Purpose/Source/Scope/Dependencies/Implementation Details/Expected Behavior/Acceptance Criteria im Given-When-Then-Format/AC-Test-Mapping/Known Limitations/ADR-Bezug/Changelog).

### Dependencies
- **Upstream (neu):** `rasterio` (GeoTIFF-Punktextraktion) — einzige neue Dependency.
- **Upstream (bestehend):** `httpx`, `tenacity` (Retry-Pattern aus `geosphere.py`), Provider-Registry (`src/providers/base.py::register_provider`).
- **Downstream:** `RadarNowcastService.get_nowcast()` konsumiert von `trip_command_processor.py:1091` (`### now`-Befehl) und `trip_alert.py:762` (proaktive Alerts) — kein Änderungsbedarf, Integration ist transparent über die Fallback-Kette.
- **Relevantes ADR:** ADR-0018 (Provider-Fallback darf Sidecar-/Check-Ausfälle nie stillschweigend als "geprüft, alles ok" kaschieren) — direkt anwendbar auf den Konvektions-Sidecar-Fail-Pfad.

### Open Questions
- [x] LoC-Schätzung (~350–450) überschreitet das 250-LoC-Default-Limit — **PO-Entscheidung 2026-07-09: Split.** Dieser Workflow (`feat-1162-radar-dpc`) liefert NUR den Kern: Radar-DPC als Regen-Nowcast-Quelle für Italien (Provider + BBox-Integration + Open-Meteo-Sidecar für `is_convective`, identisches Muster zu INCA/#1161). Native Gewitter/Hagel-Erkennung via DPC-eigene Produkte (HRD/LTG) ausgelagert nach **Folge-Issue #1174**.
- [ ] `rasterio`-Install ohne System-GDAL-Paket auf Ubuntu 24.04 — muss vor Spec-Freigabe empirisch im Worktree bestätigt werden.
- [ ] `origin`-Header-Pflicht der DPC-API — muss gegen die echte API verifiziert werden (welcher Wert wird akzeptiert?).
- [ ] Reale Latenz des 3-stufigen API-Calls (findLastProductByType → downloadProduct → S3-Download → GeoTIFF-Decode) gegen die <10s-AC-3-Anforderung aus der Basis-Spec (`radar_nowcast.md`) für den `### now`-Befehl.
- [ ] Exakte IT-BBox-Grenzen (grobe Schätzung vorhanden, nicht verifiziert).

### Scope dieses Workflows (nach Split-Entscheidung)
**In Scope:** Radar-DPC-Provider (SRI-Produkt, mm/h), BBox-Integration vor AROME-FR, `is_convective` via bestehenden Open-Meteo-Sidecar (ADR-0018-konform), Spec + Tests nach INCA-Vorlage.
**Explizit NICHT in Scope (→ #1174):** natives DPC-Gewitter/Hagel-Signal (HRD/LTG).
