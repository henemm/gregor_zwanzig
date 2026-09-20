---
entity_id: radar_nowcast_france
type: module
created: 2026-06-11
updated: 2026-09-20
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, radar, france, europe]
---

# Nowcast: Explizites AROME-HD-Routing für Frankreich (Issue #734)

## Approval

- [x] Approved

## Purpose

Hängt **Météo-France AROME-HD** (1,5 km, 15-Minuten-Schritte) als explizite regionale
Hochauflösungs-Quelle in die koordinaten-basierte Nowcast-Quellen-Kette des
`RadarNowcastService` ein. Schließt die in `radar_nowcast.md` dokumentierte Lücke, dass
Koordinaten außerhalb DE (RADOLAN) und AT (INCA) bislang auf Open-Meteos `best_match`
zurückfielen — der **nachweislich kein** regionales Hochauflösungs-Modell garantiert
(verifiziert: `minutely_15` liefert auch mitten im Atlantik/in der Sahara Werte → außerhalb
der Modell-Abdeckung interpoliert best_match global herab). Für die AROME-HD-Domäne
(Frankreich inkl. Korsika, FR-Alpen, Pyrenäen, Benelux, NW-Italien) wird das Modell ab jetzt
**explizit** angesteuert.

## Source

- **File:** `src/services/radar_service.py` (erweitert)
- **Identifier:** `RadarNowcastService._fetch_frames_with_fallback`, neue `_fetch_arome_france_hd`,
  neue Bbox-Helper `_within_arome_france`, `format_now_text` (Quellen-Label).
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~70–110 (Bbox-Konstanten + Guard + Fetch-Methode + Ketten-Einhängung + Label) + mock-freie Tests
- **Files:** 1 produktiv + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.RadarNowcastService` | service | Quellen-Kette, in die AROME-FR eingehängt wird (bestehend) |
| `providers.brightsky.RadarFrame` | dataclass | Gemeinsames Frame-Format (`timestamp`, `precip_mm_h`, `is_convective`) |
| Open-Meteo `/v1/forecast?models=arome_france_hd` | provider | AROME-HD Punkt-JSON mit `minutely_15=precipitation,weather_code` (kein API-Key) |
| `RadarNowcastService._is_convective_weathercode` | helper | WMO 95/96/99 → Konvektion (bestehend, wird für AROME-Pfad genutzt) |

## Implementation Details

### Quellen-Kette (erweitert)
```
def _fetch_frames_with_fallback(lat, lon):
    if _within_radolan(lat, lon):                # DE  — echtes Radar
        frames = brightsky;  if frames: return frames, "radar"
    if _within_inca(lat, lon):                   # AT  — INCA-Nowcast
        frames = inca;       if frames: return frames, "INCA"
    if _within_arome_france(lat, lon):           # NEU — AROME-HD explizit
        frames = arome;      if frames: return frames, "AROME-FR"
    frames = openmeteo_minutely15(lat, lon)      # global best_match (Fallback)
    return frames, "minutely_15"
```
Reihenfolge ist bewusst: DE/AT-Koordinaten treffen ihr dediziertes Radar zuerst; AROME-FR wird
nur erreicht, wenn die spezialisierteren Radar-Quellen nicht greifen (leere Antwort) oder die
Koordinate außerhalb DE/AT liegt. Jeder Schritt ist fail-soft (Exception/Leerantwort → nächste Quelle).

### AROME-HD Bounding Box (`_within_arome_france`)
- Deckt die AROME-HD-Domäne ab: ~`41.0–51.5 N`, `-5.5–10.0 E`.
- Enthält: Festland-Frankreich, **Korsika** (~41.3–43.1 N / 8.5–9.6 E), französische Alpen,
  Pyrenäen, Benelux, NW-Italien. Überlappungen mit der RADOLAN-/INCA-Box sind unkritisch, da
  diese in der Kette **vorher** geprüft werden.

### AROME-HD Fetch (`_fetch_arome_france_hd`)
- Open-Meteo `/v1/forecast?latitude=..&longitude=..&models=arome_france_hd`
  `&minutely_15=precipitation,weather_code&timezone=UTC&forecast_minutely_15=96`.
- Parsing identisch zum bestehenden `minutely_15`-Pfad: `precipitation` (mm/15 min) → mm/h (×4),
  `weather_code` → `is_convective` via `_is_convective_weathercode` → `RadarFrame`.
- Bei HTTP-/Netz-Fehler oder Leerantwort: `[]` zurück → Kette fällt auf globalen best_match zurück.

### Quellen-Transparenz (`format_now_text`)
- `source`-Label-Map ergänzt: `"AROME-FR"` → **"Météo-France AROME (1,5 km)"**.
- `"minutely_15"` wird ehrlich umbenannt zu **"Open-Meteo (global)"** (statt "Open-Meteo 15-min"),
  damit der Nutzer die tatsächliche Datenherkunft/-güte sieht.

## Expected Behavior

- **Input:** Koordinaten (aus heutiger Etappe) bzw. `### now`/`JETZT` Inbound; Scheduler-Tick bei Alerts.
- **Output:** Nowcast-Text bzw. Alert — bei AROME-FR-Abdeckung mit explizit hochauflösenden Daten
  und transparentem Modell-Label.
- **Side effects:** Keine (reiner Lese-/Fetch-Pfad); Alert-Pfad-Seiteneffekte unverändert aus `radar_nowcast.md`.

## Acceptance Criteria

- **AC-1:** Given eine reale Koordinate innerhalb der AROME-HD-Domäne (z.B. Korsika ~42.18 N / 9.0 E) und außerhalb der DE/AT-Radar-Boxen / When `RadarNowcastService.get_nowcast(lat, lon)` aufgerufen wird / Then ist `result.source == "AROME-FR"` und `result.frames` enthält ≥1 reale Frame mit numerischer Niederschlagsrate (mm/h ≥ 0) — also explizit AROME, **nicht** der globale `minutely_15`-Fallback.
  - Test: Echter HTTP-Call (`_fetch_arome_france_hd` bzw. `get_nowcast`) gegen Open-Meteo `models=arome_france_hd` mit fester Korsika-Koordinate; assert `source=="AROME-FR"`, ≥1 Frame, Raten numerisch ≥ 0. Kein Mock.

- **AC-2:** Given die Bbox-Logik der Quellen-Kette / When Koordinaten verschiedener Regionen klassifiziert werden / Then liegt Korsika/Paris/Pyrenäen in der AROME-FR-Box, eine deutsche Koordinate (Berlin) wird zuvor von der RADOLAN-Box abgefangen (Routing-Reihenfolge), und eine Koordinate außerhalb Europas (Nord-Atlantik) liegt in keiner expliziten Box und fällt auf `minutely_15` zurück.
  - Test: Deterministischer Test auf `_within_arome_france` (Korsika/Paris/Pyrenäen=True, Atlantik=False) + Ketten-Routing-Test, der für Berlin `source=="radar"` (RADOLAN-Vorrang) und für Atlantik `source=="minutely_15"` belegt. Kein Netz für die Bbox-Asserts, kein Dateiinhalt-Check.

- **AC-3:** Given ein `NowcastResult` mit `source == "AROME-FR"` bzw. `source == "minutely_15"` / When `format_now_text(result)` es rendert / Then nennt der Text bei AROME-FR transparent die echte Quelle (enthält "AROME" und "Météo-France") und beim globalen Fallback ein ehrliches globales Label ("Open-Meteo (global)") — nie das irreführende generische "15-min" für AROME-Daten.
  - Test: Pure-Function-Test mit konstruierten `NowcastResult`-Objekten beider Quellen → erwartete Label-Strings im Ausgabetext. Deterministisch, kein Netz.

- **AC-4:** Given AROME-`minutely_15`-Daten, die einen konvektiven WMO-Code (95/96/99) für einen nassen Frame im Nowcast-Fenster führen / When `RadarNowcastService` daraus ein Ergebnis ableitet / Then ist `result.is_convective == True` und `intensity_to_text` liefert "Starker Hagel/Gewitter" — d.h. der hochauflösende AROME-`weather_code` speist das Gewitter-Signal (kein separater Blitz-Feed nötig).
  - Test: Deterministischer Test, der reale `RadarFrame`-Objekte (konstruiert aus AROME-Feldwerten inkl. `is_convective=True`, kein `Mock`) durch `_derive_result`/`intensity_to_text` führt → `is_convective` propagiert, Intensitäts-String korrekt. Ergänzend ein echter Fetch gegen die AROME-Koordinate, der die Parse-Struktur (`weather_code` vorhanden) belegt.

> Nachtrag 2026-09-15 (#2205, ADR-0069): Konvektiver Frame ohne Hagel (Wettercode 95) trägt jetzt das Label „Gewitter" (`INTENSITY_CONVECTIVE_NO_HAIL`); „Starker Hagel/Gewitter" nur noch bei Wettercode 96/99 (`RadarFrame.hail`).

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_arome_france_real_fetch_returns_arome_source` |
| AC-2 | `test_ac2_within_arome_france_bbox`, `test_ac2_chain_routing_berlin_radar_atlantic_global` |
| AC-3 | `test_ac3_format_now_text_transparent_source_labels` |
| AC-4 | `test_ac4_arome_convective_weathercode_drives_intensity`, `test_ac4_arome_real_fetch_has_weather_code` |

Testdatei: `tests/tdd/test_feature_734_arome_france_nowcast.py` (mock-frei).

## Known Limitations

- **Echtes Radar nur DE/AT:** Außerhalb der RADOLAN-/INCA-Domäne gibt es keine saubere freie
  Punkt-API für rohes Radar-Reflektivitäts-Mosaik (RainViewer = nur PNG-Kacheln, Météo-France-Radar
  = GRIB/WMS). AROME-HD ist ein konvektionsauflösendes Modell-Nowcast — für „regnet's in ~20 Min?"
  praxistauglich, aber kein Radar-Pixel.
- **Keine echte Blitz-Quelle:** Blitzortung.org verbietet kommerzielle Nutzung ausdrücklich → für
  dieses Produkt nicht nutzbar. Es existiert keine saubere freie Echtzeit-Einschlag-Quelle. Gewitter
  bleibt eine Modell-Klassifikation (WMO-`weather_code`), über Frankreich jetzt aus AROME-HD.
- **Nur Frankreich-Box in diesem Issue:** Weitere europäische Hochauflösungs-Modelle (ICON-D2 für
  Zentraleuropa/Alpen) sind ausgegliedert in **Issue #761** (Backlog). Regionen ohne explizite Box
  fallen weiterhin auf Open-Meteo best_match zurück — bewusst akzeptierte regionale Abdeckungs-Unterschiede.
- **best_match-Fallback intransparent:** Außerhalb der expliziten Boxen kann best_match je nach Ort
  ein regionales Modell ODER eine globale Interpolation liefern; das Label "Open-Meteo (global)" macht
  diese Unsicherheit ehrlich, garantiert aber keine bestimmte Auflösung.
- **Latenz/Verfügbarkeit:** Hängt von Open-Meteo ab; Timeout/Leerantwort → Fallback auf best_match.

## Changelog

- 2026-06-11: Initial spec created (Issue #734) — AROME-HD explizit für Frankreich-Box; ICON-D2 ausgegliedert nach #761
- 2026-09-20: Die seit 2026-06-11 behauptete Korsika-Zuordnung zu AROME-FR wird mit Issue #1761 erstmals real eingelöst — bis dahin griff die (größere) Italien-Radar-Box vor der Frankreich-Box, sodass Korsika faktisch nie über AROME-FR lief. Neu ist eine eigene, vorgeschaltete Korsika-Box (`_within_corsica`) plus ARPAE-ICON-2I-Sidecar für `is_convective`/`hail`, weil AROME-FR an Korsika-Koordinaten strukturell keinen `weather_code` liefert (das sah die ursprüngliche AC-1-Fassung noch nicht vor). Siehe `docs/specs/modules/fix_1761_korsika_arome_sidecar.md`.
