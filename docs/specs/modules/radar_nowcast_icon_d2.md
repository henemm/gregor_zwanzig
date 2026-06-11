---
entity_id: radar_nowcast_icon_d2
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, icon-d2, central-europe, alps]
---

# Nowcast: Explizites ICON-D2-Routing für Zentraleuropa/Alpen (Issue #761)

## Approval

- [x] Approved

## Purpose

Hängt **DWD ICON-D2** (~2 km, 15-min) als explizite regionale Hochauflösungs-Quelle in die
koordinaten-basierte Nowcast-Quellen-Kette des `RadarNowcastService` ein — direkt analog zu
#734 (AROME-FR). Schließt die Lücke für wander-relevante Zentraleuropa-/Alpen-Regionen östlich
der AROME-Frankreich-Box und außerhalb von DE-RADOLAN / AT-INCA (östliche Alpen, Dolomiten,
Slowenien, Tschechien, östliche Schweiz), die heute auf Open-Meteos intransparenten `best_match`
zurückfallen, der nachweislich kein regionales Hochauflösungs-Modell garantiert.

## Source

- **File:** `src/services/radar_service.py` (erweitert)
- **Identifier:** `RadarNowcastService._fetch_frames_with_fallback`, neue `_fetch_icon_d2`,
  neue Bbox-Helper `_within_icon_d2`, erweiterter `_fetch_openmeteo_15` (All-None-Guard für
  expliziten Modell-Pfad), `format_now_text` (Quellen-Label).
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~70–110 (Bbox-Konstanten + Guard + Fetch + All-None-Guard + Ketten-Einhängung + Label) + mock-freie Tests
- **Files:** 1 produktiv + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.RadarNowcastService` | service | Quellen-Kette + geteilter `_fetch_openmeteo_15` (#734) |
| `providers.brightsky.RadarFrame` | dataclass | Gemeinsames Frame-Format |
| Open-Meteo `/v1/forecast?models=icon_d2` | provider | ICON-D2 Punkt-JSON, `minutely_15=precipitation,weather_code` (kein API-Key) |
| `RadarNowcastService._is_convective_weathercode` | helper | WMO 95/96/99 → Konvektion (bestehend) |
| `docs/specs/modules/radar_nowcast_france.md` | spec | Strukturelles Vorbild (#734) |

## Implementation Details

### Quellen-Kette (erweitert)
```
def _fetch_frames_with_fallback(lat, lon):
    if _within_radolan(lat, lon):          # DE  — echtes Radar
        frames = brightsky;  if frames: return frames, "radar"
    if _within_inca(lat, lon):             # AT  — INCA
        frames = inca;       if frames: return frames, "INCA"
    if _within_arome_france(lat, lon):     # FR  — AROME-HD (1,5 km)
        frames = arome;      if frames: return frames, "AROME-FR"
    if _within_icon_d2(lat, lon):          # NEU — ICON-D2 (~2 km)
        frames = icon_d2;    if frames: return frames, "ICON-D2"
    frames = openmeteo_minutely15(lat, lon)  # global best_match (Fallback)
    return frames, "minutely_15"
```
ICON-D2 wird NACH AROME-FR geprüft: in der West-Überlappung (Schweiz-West/Benelux) hat das
höher aufgelöste AROME-HD (1,5 km) Vorrang; ICON-D2 füllt östlich der AROME-Box (Dolomiten
lon > 10, Slowenien, Tschechien, Ost-Alpen). DE/AT treffen ihr Radar weiterhin zuerst.

### ICON-D2 Bounding Box (`_within_icon_d2`)
- Konservatives Rechteck ~`44.0–58.0 N`, `2.0–19.0 E` (grobe Eingrenzung, spart sinnlose
  Calls für ferne Punkte). Die **exakte** Domänen-Treue leistet der All-None-Guard (s.u.),
  da das ICON-D2-Gitter rotiert/nicht-rechteckig ist.

### ICON-D2 Fetch (`_fetch_icon_d2`)
- Open-Meteo `/v1/forecast?latitude=..&longitude=..&models=icon_d2`
  `&minutely_15=precipitation,weather_code&timezone=UTC&forecast_minutely_15=96`.
- Delegiert an den geteilten `_fetch_openmeteo_15(lat, lon, models="icon_d2")`.
- Parsing wie AROME: precipitation (mm/15 min) → mm/h (×4), `weather_code` → `is_convective`.

### All-None-Guard (`_fetch_openmeteo_15`, nur expliziter Modell-Pfad)
- **Verifiziert:** Außerhalb der ICON-D2-Domäne liefert Open-Meteo `precipitation: [None, …]`
  (keine Interpolation). Der bestehende Parser wandelt `None`→`0.0` → nicht-leere Frames →
  fälschlich „ICON-D2" mit Schein-Nullen statt Fallthrough.
- **Regel:** Wenn `models` gesetzt ist UND **alle** `precipitation`-Werte `None` sind →
  `return []` (Punkt außerhalb der Modell-Domäne → Kette fällt auf best_match zurück).
- Der globale Pfad (`models=None`) behält unverändert das `None`→`0.0`-Verhalten (best_match
  interpoliert für Land-Koordinaten, liefert nie all-None) — keine Regression für #734/#656.

### Quellen-Transparenz (`format_now_text`)
- Label-Map ergänzt: `"ICON-D2"` → **"DWD ICON-D2 (2 km)"**.

## Expected Behavior

- **Input:** Koordinaten (heutige Etappe) bzw. `### now`/`JETZT`; Scheduler-Tick bei Alerts.
- **Output:** Nowcast-Text/Alert — bei ICON-D2-Abdeckung mit explizit hochauflösenden Daten
  und transparentem Modell-Label.
- **Side effects:** Keine (reiner Lese-/Fetch-Pfad).

## Acceptance Criteria

- **AC-1:** Given eine reale Koordinate innerhalb der ICON-D2-Domäne und außerhalb der DE/AT/FR-Boxen (z.B. Dolomiten ~46.4 N / 11.8 E) / When `RadarNowcastService.get_nowcast(lat, lon)` aufgerufen wird / Then ist `result.source == "ICON-D2"` und `result.frames` enthält ≥1 reale Frame mit numerischer Niederschlagsrate (mm/h ≥ 0) — explizit ICON-D2, nicht der globale `minutely_15`-Fallback.
  - Test: Echter HTTP-Call gegen Open-Meteo `models=icon_d2` mit fester Dolomiten-Koordinate; assert `source=="ICON-D2"`, ≥1 Frame, Raten numerisch ≥ 0. Kein Mock.

- **AC-2:** Given die Bbox- und Ketten-Logik / When Koordinaten verschiedener Regionen geroutet werden / Then liegt eine Zentraleuropa-Koordinate außerhalb DE/AT/FR (Dolomiten/Slowenien) in der ICON-D2-Box; Berlin wird zuvor von RADOLAN abgefangen (`source=="radar"`); eine West-Überlappungs-Koordinate in der AROME-Box (z.B. Schweiz-West) wird von AROME-FR vor ICON-D2 bedient (`source=="AROME-FR"`); der Nord-Atlantik liegt in keiner Box und fällt auf `minutely_15` zurück.
  - Test: Deterministischer Test auf `_within_icon_d2` + echte Ketten-Calls für Berlin (`radar`), Schweiz-West (`AROME-FR`), Atlantik (`minutely_15`). Mock-frei.

- **AC-3:** Given eine reale Koordinate INNERHALB der ICON-D2-Bbox, aber AUSSERHALB des rotierten ICON-D2-Gitters (z.B. Polen-Tatra ~49.2 N / 20.0 E, das all-None liefert) / When `_fetch_icon_d2` bzw. `get_nowcast` aufgerufen wird / Then liefert der ICON-D2-Fetch `[]` (All-None-Guard) und die Kette fällt sauber auf `minutely_15` zurück — KEIN fälschliches `source=="ICON-D2"` mit Schein-Null-Frames.
  - Test: Echter HTTP-Call gegen eine all-None-Koordinate; assert `_fetch_icon_d2(...) == []` UND `get_nowcast(...).source == "minutely_15"`. Mock-frei (Open-Meteo liefert real all-None außerhalb der Domäne).

- **AC-4:** Given ein `NowcastResult` mit `source == "ICON-D2"` / When `format_now_text(result)` rendert / Then nennt der Text transparent die echte Quelle ("DWD ICON-D2"); ein konvektiver ICON-D2-`weather_code` (95/96/99) treibt `is_convective` → `intensity_to_text` = "Starker Hagel/Gewitter".
  - Test: (a) Pure-Function-Test: `format_now_text` mit `NowcastResult(source="ICON-D2")` enthält "DWD ICON-D2". (b) Deterministischer Test: reale `RadarFrame`-Objekte mit konvektivem Code → `is_convective`+Intensität korrekt. Kein Mock.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_icon_d2_real_fetch_returns_icon_d2_source` |
| AC-2 | `test_ac2_within_icon_d2_bbox`, `test_ac2_chain_routing_precedence` |
| AC-3 | `test_ac3_icon_d2_all_none_falls_through_to_global` |
| AC-4 | `test_ac4_format_now_text_icon_d2_label`, `test_ac4_icon_d2_convective_drives_intensity` |

Testdatei: `tests/tdd/test_feature_761_icon_d2_nowcast.py` (mock-frei).

## Known Limitations

- **Echtes Radar nur DE/AT:** ICON-D2 ist (wie AROME) ein konvektionsauflösendes Modell-Nowcast,
  kein Radar-Reflektivitäts-Pixel — für „regnet's in ~20 Min?" praxistauglich. Echtes Radar
  jenseits DE/AT bleibt mangels sauberer freier Punkt-API offen (siehe #734 Known Limitations).
- **Rotiertes Gitter:** Die rechteckige Bbox ist nur eine grobe Eingrenzung; die exakte
  Domänen-Treue kommt vom All-None-Guard. Punkte innerhalb der Bbox aber außerhalb des Gitters
  fallen korrekt auf best_match zurück.
- **West-Überlappung:** In der AROME-Box (Schweiz-West/Benelux) gewinnt AROME-HD (höhere
  Auflösung) durch die Ketten-Reihenfolge — ICON-D2 deckt nur den Rest.
- **best_match-Fallback intransparent:** Außerhalb aller expliziten Boxen unverändert wie #734.
- **Keine echte Blitz-Quelle:** Blitzortung kommerziell verboten; Gewitter bleibt Modell-
  Klassifikation (WMO-`weather_code`), hier aus ICON-D2.

## Changelog

- 2026-06-11: Initial spec created (Issue #761) — ICON-D2 explizit für Zentraleuropa/Alpen; baut auf #734-Mechanik auf, All-None-Guard für rotiertes Gitter
