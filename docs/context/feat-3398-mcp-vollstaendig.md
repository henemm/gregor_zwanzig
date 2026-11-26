# Context: feat-3398-mcp-vollstaendig

## Request Summary
PO-Vorgabe 2026-11-26 (#3398): „bitte kein Stückwerk. Gregor soll vollständig über den MCP verfügbar sein, mit allen Metriken.“ Der MCP-Konnektor „Gregor Wetter“ (#3281, ADR-0128) soll alle wählbaren Katalog-Metriken liefern und zusätzlich den Regen-/Gewitter-Nowcast (Radar), wie Briefings und Alarme ihn nutzen.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/mcp_wetter.py:33-37` | `_ROHFELDER`: die Whitelist der ausgegebenen Felder (11 + `sonnenminuten`); hier muss erweitert werden |
| `api/routers/mcp_wetter.py:41-51` | `_einheiten()`: Einheit aus Katalog (`dp_field` → `unit`), Sonderfälle `wmo_code`, `sonnenminuten` |
| `api/routers/mcp_wetter.py:113-118` | Abruf `get_provider("openmeteo").fetch_forecast(..., enrich_ensemble=False, enrich_snow=False)`; kein Cache, kein Budget-Gate |
| `src/app/metric_catalog.py:141-786` | 32 Definitionen, 29 wählbar (`get_all_metrics()` 1406-1414); nicht wählbar: `temperature_cold`, `confidence` (#710), `cape` (#1585) |
| `src/app/models.py:135,152` | `ForecastDataPoint.wind_chill_c`, `confidence_pct` |
| `src/providers/openmeteo.py:1237,1309-1341` | Ensemble per `enrich_ensemble`; `_abschliessen`: `_enrich_snow` (per `enrich_snow`), `_enrich_thunder`, Bewölkung |
| `src/providers/thunder_enrichment.py:208-276` | Radar-Override ±90 min hebt `thunder_level` auf MED |
| `src/services/radar_service.py:657` | `RadarNowcastService().get_nowcast(lat, lon, elevation_m, priority, user_id, deadline_at) -> NowcastResult` (Dataclass 215-310) |
| `src/services/radar_cache.py:38,127` | Frame-Cache TTL 240 s, prozessweit |
| `src/services/segment_weather.py:96` | `SegmentWeatherService.fetch_segment_weather` (Cache + Budget-Gate); Compare nutzt synthetisches 1-Punkt-Segment (`comparison_engine.py:67-111`) |
| `internal/mcp/werkzeuge.go:39-48,182-207` | Werkzeug-Schema (ort, lat, lon, von, bis); `wetter()` reicht JSON durch (keine Whitelist) |
| `internal/handler/mcp_wetter.go:61-64` | `MCPWetterAnfrage{Lat,Lon,Von,Bis}` |
| `internal/i18n/messages/{de,en}/mcp.json` | Werkzeugbeschreibung `mcp.werkzeug.wetter` zählt Felder auf → muss nachgezogen werden |
| `tests/tdd/test_mcp_wetter_core_endpunkt.py` | Endpunkt-Tests; prüft Top-Level-Keys exakt, Einheiten je Stundenfeld, `confidence_pct` fehlt |
| `internal/mcp/testdata/core_*.json`, `internal/router/mcp_welt_test.go:80` | Go-Fixtures des Core-Antwortformats |

## Existing Patterns
- Felder werden per Katalog-`dp_field` benannt, Einheit aus Katalog (unübersetzt, ADR-0104).
- Abgeleitete Werte (Sonnenminuten) werden in Python aus der einen Umrechnung des Bestands erzeugt (ADR-0127), nie in Go.
- Nowcast-Verbraucher (`trip_alert.py:2340`, `trip_report_scheduler.py:2388`, `compare_radar_alert.py`) rufen `get_nowcast` mit `priority` und `user_id`.

## Dependencies
- Upstream: Open-Meteo-Provider (+ Thunder-/Snow-Enrichment, Ensemble), RadarNowcastService (Quellkette RADOLAN → INCA → AROME-Korsika → ARPAE → AROME-HD → ICON-D2 → Open-Meteo minutely_15; Horizont 180 min; 15-min-Raster bzw. 5-min-Frames).
- Downstream: Go-MCP-Werkzeug `wetter` (Durchreichung), Claude-App.

## Existing Specs
- `docs/specs/modules/mcp_wetter_konnektor.md`: Feldliste Zeile 68 (explizit), `felder?` Zeile 87 (nicht implementiert), Known Limitation Zeile 175 „Kein Regenradar und kein Nowcast“ → wird durch diese Änderung aufgehoben (Spec-Update, Changelog).
- ADR-0128: nur Orts-/Wetterdaten; Nowcast ist Wetterdatum → kein neues ADR nötig, aber Nachtrag/Verweis im Spec.

## Risks & Considerations
- **Vollständigkeit vs. Datenmenge:** 7 Tage × 24 h × ~25 Felder → große Antwort für Claude; ggf. Feldauswahl (`felder`) sinnvoll — aber „kein Stückwerk“: Standard = alles.
- **Gleiche Werte wie im Briefing:** MCP nutzt `enrich_snow=False` (keine SNOWGRID-Füllung für Schneehöhe/Neuschnee/Schneefallgrenze) und Open-Meteo-only; geosphere-only Felder (`precip_type`, `snow_depth`, `fresh_snow`, `snowfall_limit`) brauchen den Briefing-Pfad. Wahrscheinlich `enrich_snow=True`.
- **Ensemble/Confidence:** `confidence_pct` bleibt ausgeschlossen (#710, `tests/tdd/test_issue_715_confidence_not_selectable.py`); `enrich_ensemble` daher nicht nötig.
- **CAPE:** nicht wählbar (#1585) → nicht ausgeben (Katalog-Regel „wählbar“ als Maßstab).
- **Abgeleitete Fenstermetriken** (`*_night`, `*_day_low/high`, `temperature_cold`) teilen `dp_field` → stündlich kein Extrafeld nötig; Tagesaggregate optional.
- **Nowcast-Kosten:** Radar-Abruf je MCP-Aufruf; Budget-Gate per `priority`, Cache 240 s; Mengenbremse/Kontingent in Go deckt Aufrufzahl. Nur sinnvoll, wenn Zeitraum die nächsten 3 h berührt.
- **Nowcast außerhalb Radarabdeckung:** Fallback Open-Meteo minutely_15 → Quelle muss in der Antwort stehen (`source`).
- Go-Fixtures und Werkzeugbeschreibung (de/en) müssen mitziehen.

## Analysis

### Type
Feature (Erweiterung des MCP-Konnektors #3281, ADR-0128)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/mcp_wetter.py` | MODIFY | Feldmenge aus Katalog ableiten (`get_all_metrics()` → `dp_field`, dedupliziert, ohne `dni_wm2`; plus `wmo_code`, `sonnenminuten`); `enrich_snow=True`; optionaler Parameter `felder` |
| `api/routers/mcp_nowcast.py` | CREATE | `GET /api/_internal/mcp/nowcast?lat&lon` → `RadarNowcastService().get_nowcast(..., priority="user_briefing", user_id=None)`; Zusammenfassung + Frame-Reihe (Ortszeit, mm/h, konvektiv, Hagel), Quelle, Reichweite, Flags |
| `api/main.py` | MODIFY | Router registrieren |
| `tests/tdd/test_mcp_wetter_core_endpunkt.py` | MODIFY | Feldmenge == wählbare Katalogfelder; `felder`-Auswahl; Schnee im SNOWGRID-Gebiet |
| `tests/tdd/test_mcp_nowcast_core_endpunkt.py` | CREATE | Nowcast mit Offline-Fixtures (`GZ_TEST_FIXTURE_DIR`), kein Mock |
| `internal/mcp/werkzeuge.go` | MODIFY | Werkzeug `regen_nowcast` (Schema ort/lat/lon), `felder` am Werkzeug `wetter` |
| `internal/handler/mcp_wetter.go` (oder neue `mcp_nowcast.go`) | MODIFY/CREATE | Abruf analog `MCPWetterAbrufen` inkl. Mengenbremse/Kontingent |
| `internal/i18n/messages/{de,en}/mcp.json` | MODIFY | Beschreibungen `wetter` (Feldliste), `regen_nowcast`, `mcp.feld.felder`, Intensitätstexte, Hinweis „nicht verfügbar/trocken“ |
| `internal/mcp/testdata/core_*.json`, Go-Tests | MODIFY/CREATE | neues Antwortformat, Nowcast-Fixture |
| `docs/specs/modules/mcp_wetter_konnektor.md` | MODIFY | Feldliste, `felder`, Nowcast-Werkzeug, Known Limitation „kein Nowcast“ aufheben, Changelog |

### Scope Assessment
- Files: ~12, in drei Lieferscheiben (je eigener PR, ein Workflow)
- Estimated LoC: S1 ~150 (Felder + Schnee + `felder` Python), S2 ~250 (Nowcast Python), S3 ~250 (Go: Werkzeug `regen_nowcast`, `felder`, i18n, Fixtures); Tests zusätzlich
- Risk Level: MEDIUM (externe Schnittstelle, Radar-Abrufe; keine Nutzerdaten, keine Auth-Änderung)

### Technical Approach
1. **Felder aus dem Katalog** statt Handliste: neue wählbare Metriken erscheinen automatisch. Ausgeschlossen bleiben nicht wählbare (`confidence_pct` #710, `cape_jkg` #1585). `dni_wm2` nur als `sonnenminuten` (ADR-0127, eine Umrechnung). Leere Katalogeinheit (`thunder_level`, `precip_type`, `uv_index`) → `""`. Enums als `.value`.
2. **`enrich_snow=True`** wie Compare-Briefing: Schneehöhe/Neuschnee aus SNOWGRID nur im Abdeckungsgebiet (Alpenraum); außerhalb fehlen die Felder — auch im Briefing (dokumentieren). `precip_type` wird nur von GeoSphere gefüllt (`geosphere.py:888`, `openmeteo.py:1022` = None) → im Open-Meteo-Pfad leer, wie im Briefing. Ensemble bleibt aus (nur für `confidence_pct`).
3. **`felder`-Parameter** (in Spec #3281 Zeile 87 bereits vorgesehen, nie gebaut): Standard = alle; Auswahl verkleinert lange Zeiträume (7 Tage × alle Felder ≈ 50 KB). Unbekannte Feldnamen → Eingabefehler mit Katalogtext.
4. **Eigenes Werkzeug `regen_nowcast`** (Horizont 180 min ≠ 7 Tage; kein Radarabruf bei jedem `wetter`-Aufruf). Ausgabe: `beginn_min`/`ende_min` (onset/event_end), `laeuft_bereits`, `intensitaet` als stabiler Token (`leicht|maessig|stark|...` aus `_INTENSITY_*`) + übersetzter Text, `konvektiv`, `hagel` (aus Frames), `max_mm_h_erste_stunde`, `summe_erste_stunde_mm`, `quelle`, `reichweite_min`, `ueber_horizont_hinaus`, `gedrosselt`, `nicht_verfuegbar`, Frame-Reihe `[{zeit, mm_h, konvektiv, hagel}]`. Außerhalb Radarabdeckung: Quelle `minutely_15` (Open-Meteo), ehrlich ausgewiesen. Feldnamen-Wortlaut wird in der Spec festgelegt. `priority="user_briefing"` (Go bucht Kontingent schon, keine Doppelbuchung).
5. Go bleibt Durchreichung; Mengenbremse/Kontingent gilt für beide Werkzeuge.

### Dependencies
- `RadarNowcastService` (Cache 240 s, Single-Flight, Budget-Gate), Offline-Fixtures für Tests.
- Reihenfolge: Spec (alle Scheiben) → S1 → S2 → S3 (S3 hängt am Format aus S2).

### Open Questions
- keine PO-Fragen: Umfang ist vom PO vorgegeben („alles“); Schnee-/Niederschlagsart-Lücken entsprechen dem Briefing-Stand und werden in der Spec benannt.
