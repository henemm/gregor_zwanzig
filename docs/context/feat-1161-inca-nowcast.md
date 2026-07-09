# Context: feat-1161-inca-nowcast (Issue #1161)

## Request Summary
Issue #1161 (Kind-Issue von #1089, selbst Punkt 5 von Epic #1073) fordert: österreichische Orte sollen für die Gefahren-/Regen-/Gewitter-Bewertung den GeoSphere-**INCA**-Nowcast nutzen statt einer generischen Provider-Auswahl, mit Fail-Soft-Fallback.

## Zentraler Befund (verändert den Zuschnitt der Analyse-Phase!)

**Der AT→INCA-Regionalpfad existiert bereits produktiv** — implementiert in Issue #656 (`src/services/radar_service.py`), nicht erst neu zu bauen:

- `_within_inca(lat, lon)` prüft AT-Bounding-Box (`_INCA_LAT_MIN/MAX`, `_INCA_LON_MIN/MAX`).
- `_fetch_geosphere_inca()` ruft `GeoSphereProvider.fetch_nowcast()` auf → dediziertes GeoSphere-NOWCAST-Produkt (`/timeseries/forecast/nowcast-v1-15min-1km`, 15-Minuten-Auflösung, 1 km) — das ist tatsächlich das INCA-System, nicht generisch.
- Fail-Soft ist bereits vorhanden: bei Exception/leeren Daten fällt die Source-Chain automatisch weiter (AROME-FR → ICON-D2 → Open-Meteo `minutely_15`), kein Absturz.
- **AC-1 und AC-2 aus der Ursprungs-Formulierung (#1089/#1161) sind für den Regen-Anteil damit im Kern bereits erfüllt.**

**Echte offene Lücke: Gewitter/Hagel-Erkennung fehlt im INCA-Pfad — dokumentiert als bewusste Known Limitation.**

`docs/specs/modules/radar_convective_stage.md` (Issue #660, approved, Status "Implementation complete" für den globalen Pfad) hält explizit fest:

> „Konvektions-Indikator nur über Open-Meteo-`weather_code` (global). BrightSky/GeoSphere-Pfade kennzeichnen keine Konvektion (kein passendes Quellfeld) → in DE/AT-Abdeckung kann eine Gewitter-Lage unbemerkt bleiben, solange der Radar/INCA-Pfad greift. Bewusster Scope: globale Abdeckung der Zielgruppe zuerst."

Konkret: `RadarFrame.is_convective` wird im INCA-Pfad (`_fetch_geosphere_inca`) nie gesetzt (bleibt Default `False`), weil GeoSphere NOWCAST-Parameter (`t2m, ff, fx, rr, pt, rh2m`) kein Blitz-/Gewitter-Feld liefern. `pt` (precip type) kennt nur RAIN/SNOW/MIXED/FREEZING_RAIN — keinen Gewitter-Code. Ein AT-Ort, dessen Nowcast über INCA läuft, verliert dadurch die Eskalationsstufe „Starker Hagel/Gewitter" (die z. B. für Open-Meteo-Pfade über WMO-Code 95/96/99 funktioniert).

**Das ist vermutlich der eigentliche, noch offene Kern von #1161**, nicht der Aufbau eines neuen Providers.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | Nowcast-Source-Chain inkl. `_within_inca`, `_fetch_geosphere_inca`, `_derive_result` (is_convective-Aggregation) |
| `src/providers/geosphere.py` | `GeoSphereProvider.fetch_nowcast()` — INCA-Endpoint, `NOWCAST_PARAMS`, `_precip_type_from_code` |
| `src/providers/brightsky.py` | `RadarFrame`-Dataclass (`is_convective: bool = False`) |
| `src/services/trip_alert.py` | `check_radar_alerts` — konsumiert `NowcastResult.is_convective` für Alert-Kennzeichnung |
| `src/services/trip_command_processor.py` | Ad-hoc „/wetter jetzt"-Pfad, nutzt ebenfalls `RadarNowcastService.get_nowcast` |
| `src/services/risk_engine.py` | **Getrennter** multi-tägiger Gefahren-Pfad (CAPE/RiskType.THUNDERSTORM) — reiner Datenlayer, kennt keine Provider, konsumiert bereits aggregierte `SegmentWeatherData`. CAPE kommt aktuell ausschließlich aus Open-Meteo (`openmeteo.py`), GeoSphere NWP (`geosphere.py NWP_PARAMS`) liefert kein CAPE. |
| `docs/specs/modules/radar_nowcast.md` | Basis-Spec Issue #656 (4-Stufen-Intensität, Source-Chain) |
| `docs/specs/modules/radar_convective_stage.md` | Spec Issue #660 — Gewitter-Stufe, **enthält die o.g. Known Limitation** |
| `docs/reference/decision_matrix.md` | Provider-Auswahl für den **multi-tägigen** Forecast (MET/MOSMIX) — separates System, nicht der Nowcast-Pfad |

## Existing Patterns

- **Region→Provider via Bounding-Box-Gate-Kette** (`_within_radolan` → `_within_inca` → `_within_arome_france` → `_within_icon_d2` → generischer Fallback). Neue Regionen (z. B. spätere IT-Slice #1162) werden nach demselben Muster angehängt — Fail-Soft ist strukturell eingebaut (jede `_fetch_*`-Methode fängt Exceptions und liefert `[]`, Chain macht weiter).
- **Konvektions-Flag additiv**: `RadarFrame.is_convective` Default `False`, nur der Open-Meteo-Pfad setzt es aktiv. Jede Quelle, die das Flag NICHT setzen kann, bleibt bewusst konservativ (kein Fehlalarm), verliert aber Eskalationsfähigkeit.
- **DI-Seam für Tests**: `RadarNowcastService(frame_source=callable)` erlaubt Tests mit echten (nicht gemockten) `RadarFrame`-Objekten ohne Netzwerkaufruf — Pattern aus `test_feature_660_convective_stage.py` sollte für neue AC-Tests wiederverwendet werden.

## Dependencies

- **Upstream:** GeoSphere Data Hub API (`dataset.api.hub.geosphere.at`), auth-frei, bereits produktiv genutzt (Issue #1085 für Warnungen, #656/#770 für Nowcast).
- **Downstream:** `TripAlertService.check_radar_alerts` (proaktive Alerts), `trip_command_processor` (Ad-hoc-Anfragen). **Nicht** downstream: `risk_engine.py` (der mehrtägige Trip-Briefing-Risikopfad ist komplett getrennt und nutzt radar_service/INCA gar nicht).

## Existing Specs
- `docs/specs/modules/radar_nowcast.md` — Basis (Issue #656)
- `docs/specs/modules/radar_nowcast_inca_fix.md` — vorheriger INCA-Fix (Issue #770)
- `docs/specs/modules/radar_convective_stage.md` — Gewitter-Stufe, Known Limitation zu GeoSphere/INCA

## Risks & Considerations
- **Kein Duplikat-Risiko, aber Fehleinschätzungs-Risiko:** Ohne diesen Kontext hätte die Analyse-Phase versucht, einen kompletten neuen INCA-Provider zu bauen — der existiert schon. Scope korrekt auf „Gewitter-Lücke im INCA-Pfad schließen" eingrenzen.
- **Datenquelle für Gewitter-Indikator bei INCA unklar:** GeoSphere NOWCAST-Endpoint hat kein CAPE/Blitz-Feld. Optionen zu prüfen in `/20-analyse`: (a) GeoSphere hat evtl. einen separaten Blitz-/Gewitter-Layer (zu recherchieren), (b) Hybrid-Ansatz — INCA für Regen-Intensität, ergänzend Open-Meteo `weather_code` nur für das Konvektions-Flag abfragen (Zusatzcall), (c) AROME-NWP-CAPE (bereits in `geosphere.py` fetch_nwp_forecast erweiterbar) als Ergänzung, aber das ist stündliche Vorhersage, kein 15-Min-Nowcast — Granularitäts-Mismatch möglich.
- **Bewusste frühere Scope-Entscheidung respektieren:** Issue #660 hat die Lücke bewusst offengelassen („globale Abdeckung der Zielgruppe zuerst"). #1161 sollte im Analyse-Schritt klären, ob sich die Zielgruppen-Priorität seither geändert hat (GR20/Korsika war Fokus, jetzt AT/IT-Erweiterung lt. Epic #1073) — das rechtfertigt die Nachrüstung.
- **IT/Radar-DPC (#1162) ist komplett getrennt** — kein Radar-DPC-Code existiert im Repo. Keine Überschneidung mit #1161, aber gleiche Source-Chain-Architektur als Vorbild.

## Empfehlung für /20-analyse
Fokus der Analyse: Wie lässt sich `RadarFrame.is_convective` im `_fetch_geosphere_inca`-Pfad zuverlässig setzen, ohne die Datenqualität/Fail-Soft-Garantien zu verschlechtern? Nicht: neuen Provider bauen.

## Analysis

### Type
Feature (Nachrüstung einer bewusst dokumentierten Known Limitation, kein Bug).

### Zentraler Zusatzfund (Plan/Sonnet-Agent)
Die WMO-Code→`is_convective`-Mapping-Logik existiert bereits als **geteilter, produktiver Helper** `RadarNowcastService._fetch_openmeteo_15(lat, lon, models=None)` (`src/services/radar_service.py:253-299`), den AROME-FR und ICON-D2 bereits per `models=`-Parameter wiederverwenden — inkl. `_is_convective_weathercode()` (WMO 95/96/99) und eingebautem Fail-Soft. Damit ist keine neue Konvektions-Erkennungslogik nötig, nur Wiederverwendung.

### Verworfene Alternativen
- **AROME-NWP-CAPE (Option b):** verworfen — bräuchte unkalibrierten neuen CAPE-Schwellenwert und 1h/2500m→15min/1km-Downscale, widerspricht der Kernstärke von INCA (präzises Timing).
- **Externe Blitzortung (ALDIS/EUCLID):** verworfen — nicht auth-frei, neue Credential-Verwaltung, unklarer Zugang.

### Gewählter Ansatz (Sidecar-Reuse)
`_fetch_geosphere_inca()` ruft zusätzlich `self._fetch_openmeteo_15(lat, lon)` (global `best_match`, kein `models=`) auf und merged `is_convective` in die INCA-Frames per Timestamp-Match (Toleranz ±5 Min wegen leicht versetzter Raster zwischen INCA und Open-Meteo, kein exaktes `==`).

**Nicht-Kaschieren-Invariante (ADR-0018) — Pflichtbestandteil:** Ein stiller `is_convective=False`-Fallback bei Sidecar-Ausfall wäre ununterscheidbar von "geprüft, kein Gewitter" — sicherheitsrelevanter False Negative. Daher: `NowcastResult` bekommt additives Feld `convective_checked: bool` (Default `True` für alle bestehenden Pfade, die Konvektion inhärent prüfen; `False` nur wenn der INCA-Sidecar-Call scheitert). Reines `logger.warning` reicht laut ADR-0018 nicht aus (deckt nur Operator-Sichtbarkeit, nicht das Datensignal selbst).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/radar_service.py` | MODIFY | `_fetch_geosphere_inca` um Sidecar-Merge erweitern; `NowcastResult` um `convective_checked: bool = True` ergänzen; `_derive_result` propagiert das Feld |
| `tests/tdd/test_feature_770_inca_nowcast_fix.py` | MODIFY | Neue AC-Tests für INCA + Konvektion (Merge, Toleranz, Sidecar-Fail) |
| `tests/tdd/test_feature_660_convective_stage.py` | MODIFY | Neuer Fall "INCA + convective" ergänzend zum bestehenden Open-Meteo-Fall |
| `tests/tdd/test_feature_656_radar_nowcast.py` | MODIFY (ggf.) | Nur falls dort `is_convective=False` für INCA hart asserted wird |
| `docs/specs/modules/radar_convective_stage.md` | MODIFY | Known Limitation aktualisieren/schließen für GeoSphere/INCA-Teil |
| übrige 8 Testdateien (Alert/Onset/Tier/Acute-Override) | Regressionscheck | Reine Downstream-Konsumenten von `is_convective`, keine Änderung erwartet, nur mitlaufen lassen |

**Nicht betroffen:** `src/services/risk_engine.py` (getrennter, CAPE-basierter mehrtägiger Pfad), `src/providers/brightsky.py` (`RadarFrame.is_convective` existiert schon additiv, keine Änderung nötig), keine neue `NWP_PARAMS`-Erweiterung nötig.

### Scope Assessment
- Files: ~4-5 produktiv/Spec + 2-3 Testdateien
- Estimated LoC: ~120-180 (inkl. Tests)
- Risk Level: MEDIUM (sicherheitsrelevanter Pfad — Gewitter-Eskalation — aber additiv, kein bestehendes Verhalten verändert sich für Nicht-INCA-Pfade)

### Technical Approach
Sidecar-Reuse des bestehenden `_fetch_openmeteo_15`-Helpers (kein neuer Call-Typ, kein neuer Provider), ergänzt um sichtbares `convective_checked`-Signal statt stillem Fallback. Kleinster Blast Radius, konsistent mit additivem Pattern aus Issue #660.

### Dependencies
Keine Reihenfolge-Constraints zu anderen Providern (IT/#1162 unabhängig). Sinnvolle interne Schrittfolge: 1) `NowcastResult.convective_checked` additiv ergänzen → 2) `_fetch_geosphere_inca`-Sidecar-Merge mit Toleranz → 3) Tests 660/770 erweitern → 4) Downstream-Suite (Alert/Onset/Tier) als Regressionscheck.

### Open Questions
- [ ] Toleranzfenster für Timestamp-Match (±5 Min) — im Spec-Schritt als konkreter Wert festlegen und mit PO absichern, ob das ausreicht.
- [ ] Wie soll `convective_checked=False` downstream sichtbar werden (nur internes Feld vs. Alert-Text-Hinweis vs. Health-Signal analog ADR-0018 Punkt 3)? Für Spec-Phase klären.
