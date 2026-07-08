# Context: feat-1085-geosphere-warn

Issue #1085 — Alerts AT/IT Slice 1: GeoSphere-Warn-Quelle (Österreich). Epic #1073, baut auf Fundament #1033/#1034.

## Request Summary
Erste Nicht-Frankreich-Warnquelle: GeoSphere Warn API (AT) als neue `OfficialAlertSource` in der bestehenden Registry. Warnungen erscheinen additiv überall dort, wo `get_official_alerts_for_location` konsumiert wird (Orts-Vergleich + Trip-Briefings, seit #1087 gemeinsamer Renderer).

## Live-Verifikation der Quelle (2026-07-08, dieser Workflow)

- `GET https://warnungen.zamg.at/wsapp/api/getWarningsForCoords?lat={lat}&lon={lon}&lang=de` → HTTP 200, auth-frei, JSON GeoJSON-Feature. Probe Innsbruck (47.2692, 11.4041): **aktive Hitzewarnungen** (warntypid=6, warnstufeid=1, 10.–11.07.).
- Antwort-Struktur: `properties.location.properties.name` (= Gemeindename, z. B. "Innsbruck") + `properties.warnings[]`, je Warnung `properties`: `warntypid`, `warnstufeid`, `begin`/`end` (deutsches Format `TT.MM.JJJJ HH:MM`), `text`, `rawinfo.start`/`end` (**Unix-Epoch-Strings — robuster zu parsen als begin/end**).
- **Legende amtlich verifiziert** (OpenAPI `https://openapi.hub.geosphere.at/warnapi/v1/openapi.json`, Schemas `WarnType`/`WarnLevel`):
  - `WarnType`: 1=storm, 2=rain, 3=snow, 4=black ice, 5=thunderstorm, 6=heat, 7=cold (enum 1–7)
  - `WarnLevel`: **1=yellow, 2=orange, 3=red** (enum 1–3; Beispiel-Text "Gelbe Windwarnung" bei warnstufeid=1 bestätigt)
- Koordinaten außerhalb AT (Probe Paris): **HTTP 404** `{"type":"Error","msg":"Could not find municipal for coords."}` → covers()-Vorfilter verhindert den Call; fetch() muss 404 zusätzlich fail-soft schlucken.

## Level-Mapping (Kernentscheidung)
`OfficialAlert.level` ist Vigilance-Skala 1=grün…4=rot (models.py). GeoSphere 1=gelb/2=orange/3=rot → **level = warnstufeid + 1** (2/3/4). Damit greift das bestehende Renderer-Farbmapping (`alert/official_alerts.py`: ≤2 → G_SUCCESS, 3 → G_WARNING, ≥4 → G_DANGER) identisch zur Vigilance-Semantik.

## Hazard-Mapping (warntypid → hazard, label deutsch)
Bestehendes Vokabular: `wind_gust`, `thunderstorm`, `extreme_heat` (vigilance), `wildfire_risk` (meteo_forets), `access_ban` (massif_closure). Für AT: 1→`storm`/besser `wind_gust` („Sturm"), 2→`rain` („Starkregen"), 3→`snow` („Schneefall"), 4→`black_ice` („Glatteis"), 5→`thunderstorm` („Gewitter"), 6→`extreme_heat` („Hitze"), 7→`extreme_cold` („Kälte"). Wo ein Vigilance-hazard existiert, denselben Bezeichner verwenden (Konsistenz für nachgelagerte Filter); neue Typen bekommen neue Bezeichner. Renderer nutzt nur `label`+`level` → keine Renderer-Änderung nötig.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py` | Registry + `OfficialAlertSource`-Protocol (name/covers/fetch), fail-soft-Schleife |
| `src/services/official_alerts/models.py` | `OfficialAlert`-Dataclass (frozen) |
| `src/services/official_alerts/vigilance.py` | **Vorlage**: Cache mit Erfolgs-TTL 300s / Failure-TTL 60s, `_parse_iso`, warn-once bei fehlender ENV |
| `src/services/official_alerts/meteo_forets.py` | Vorlage pro-Regions-Cache |
| `src/services/official_alerts/__init__.py` | Registrierung (+Import, +register, +__all__) |
| `src/services/radar_service.py:33-36` | **AT-Bounding-Box existiert**: `_INCA_LAT_MIN/MAX=46.3/49.1`, `_INCA_LON_MIN/MAX=9.5/17.2` — importieren wie vigilance.py die AROME-FR-Box |
| `src/output/renderers/alert/official_alerts.py` | Gemeinsamer Badge-Renderer (#1087) — konsumiert nur label/level, **nicht anfassen** |
| NEU `src/services/official_alerts/geosphere_warn.py` | `GeoSphereWarnSource` |

## Existing Patterns
- Quelle = Klasse mit `name`-Property, `covers()` = reine BBox-Prüfung ohne Call, `fetch()` fail-soft `[]`.
- **Cache-Unterschied zu Vigilance:** Vigilance = EIN nationaler Call für alle Orte; GeoSphere-Endpoint ist **pro Koordinate** → Cache pro gerundetem (lat,lon)-Schlüssel (analog meteo_forets pro Region), Erfolgs-TTL 300s, Failure-TTL 60s (F001-Lehre: kein Call-pro-Ort-Sturm, hier: kein Call-pro-Wiederholung-Sturm).
- Keine ENV nötig (auth-frei) → kein Missing-Key-Zweig, aber 404/Timeout/kaputtes JSON fail-soft.
- Kreis-Import-Verbot: kein Import aus `services.comparison_engine`.

## Dependencies
- Upstream: `httpx`, `radar_service`-BBox-Konstanten, `official_alerts.models`.
- Downstream (unverändert, profitieren automatisch): `comparison_engine.py` (Compare), `trip_report_scheduler.py`/`app/trip.py` (Trip-Briefings, Toggle `official_alerts_enabled` #1040/#1087), Renderer via #1087.

## Existing Specs
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` (Registry-Fundament)
- `docs/specs/modules/issue_1035_vigilance_source.md` (Vorlage erste Quelle)
- `docs/specs/modules/epic_1073_trip_official_alerts.md` (Epic-Leitplanken)

## Risks & Considerations
- **Parallel-Arbeit #1110** baut die Compare-Mail um → E2E-Nachweis bevorzugt über **Trip-Briefing** mit AT-Ort (Warnungen dort seit #1087 stabil live); Compare deckt derselbe Registry-Pfad ab.
- Live-Testfenster: aktive Hitzewarnungen AT mind. bis 11.07. — „Badge sichtbar"-Beweis aktuell real möglich; Test darf aber nicht von Warnlage abhängen (warnungsfreier Ort ⇒ leere Liste ist auch korrekt).
- `begin`/`end` deutsch-lokal formatiert → `rawinfo`-Epochen bevorzugen (Zeitzonen-Falle).
- Endpoint ist wsapp (App-Backend) unter CC-BY — im OpenAPI-Hub dokumentiert (`warnapi/v1/getWarningsForCoords`), gleiche Struktur. Basis-URL ggf. `https://warnungen.zamg.at/wsapp/api` (verifiziert) beibehalten.
- KEINE Mocks (Projektregel): Tests rufen die echte API; Warnlage-unabhängige Assertions (Struktur, Mapping, fail-soft via ungültiger Koordinate).
