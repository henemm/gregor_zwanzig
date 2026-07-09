---
entity_id: radar_nowcast_italy_arpae_fallback
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, italy, europe, arpae, fallback]
---

# Nowcast: ARPAE-ICON-2I-Modell-Rückfall unter Radar-DPC für Italien (Issue #1186)

## Approval

- [ ] Approved

## Purpose

Fällt der italienische Radar-DPC-Nowcast (#1162, live) aus (leere Antwort/Fehler),
springt die Quellen-Kette heute direkt auf AROME-FR/ICON-D2 (nur für Rand-
Koordinaten treffend) bzw. den globalen `minutely_15`-Fallback — für Mittel-/
Süditalien (Rom, Neapel, Sizilien) ohne jede regionale Zwischenstufe. Diese Spec
hängt **ARPAE ICON-2I** (Open-Meteo, 2 km, deckt ganz Italien inkl. Süden/Inseln
ab) als Modell-Rückfall **direkt unter Radar-DPC** ein: Radar-DPC → ARPAE-2I →
(AROME-FR/ICON-D2 für Randzonen) → generisch. Vervollständigt die vom PO
gewünschte Zwei-Ebenen-Absicherung (echtes Radar primär, regionales Modell als
Netz) — analog zur AT-Absicherung (INCA + Konvektions-Sidecar).

## Source

- **File:** `src/services/radar_service.py` (erweitert)
- **Identifier:** `RadarNowcastService._fetch_frames_with_fallback` (DPC-Block),
  neue `_fetch_italy_arpae`, `_SOURCE_LABELS`.
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~40–50 (Fetch-Methode + zweiter Schritt im DPC-Block + Label) + Tests
- **Files:** 1 produktiv (`radar_service.py`), 1 bestehender Test MODIFY
  (`test_issue_1162_radar_dpc.py`, 1 Assertion erweitert), 1 Testdatei CREATE
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.RadarNowcastService` | service | Quellen-Kette, DPC-Block wird um ARPAE-Schritt erweitert (bestehend) |
| `providers.brightsky.RadarFrame` | dataclass | Gemeinsames Frame-Format (bestehend) |
| Open-Meteo `/v1/forecast?models=italia_meteo_arpae_icon_2i` | provider | ARPAE ICON-2I Punkt-JSON mit `minutely_15=precipitation,weather_code` (kein API-Key) |
| `RadarNowcastService._fetch_openmeteo_15` | helper | Geteilter Open-Meteo-Fetch/Parse (bestehend, identisch zu AROME-FR/ICON-D2) |
| `_within_dpc` | helper | Bestehende Box (36.0–47.5 N, 6.5–19.0 E, deckt ganz Italien inkl. Korsika ab) — **wird wiederverwendet, keine neue Box** |

## Implementation Details

### Quellen-Kette (DPC-Block erweitert)
```
if _within_dpc(lat, lon):                      # IT — Radar-DPC-Domäne
    frames = self._fetch_radar_dpc(lat, lon)
    if frames:
        return frames, "DPC"
    frames = self._fetch_italy_arpae(lat, lon)  # NEU — Modell-Rückfall
    if frames:
        return frames, "ARPAE-2I"

if _within_arome_france(lat, lon):              # unverändert
    ...
```
**Bewusst kein neuer `_within_italy`-Guard:** Die bestehende `_within_dpc`-Box
(36.0–47.5 N, 6.5–19.0 E) deckt bereits ganz Italien inkl. Korsika ab — deckungsgleich
mit dem, was eine neue Italien-Box abdecken würde. Ein zweiter, praktisch
identischer Bounding-Box-Block wäre Redundanz ohne Nutzen. Der ARPAE-Schritt
greift **ausschließlich** dort, wo DPC bereits zuständig war und leer/fehlerhaft
antwortete — reiner Rückfall, keine neue Region.

### ARPAE-ICON-2I Fetch (`_fetch_italy_arpae`)
```python
def _fetch_italy_arpae(self, lat: float, lon: float) -> list:
    """Fetch ARPAE ICON-2I (2 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
    return self._fetch_openmeteo_15(lat, lon, models="italia_meteo_arpae_icon_2i")
```
- Identisches Parsing zu AROME-FR/ICON-D2: `precipitation` (mm/15 min) → mm/h
  (×4), `weather_code` → `is_convective` → `RadarFrame`. ARPAE führt
  `weather_code` mit (live verifiziert) → **kein** Konvektions-Sidecar nötig
  (anders als DPC/INCA, die kein eigenes Gewitter-Feld haben).
- Bei HTTP-/Netz-Fehler oder Leerantwort: `[]` → Kette fällt weiter auf
  AROME-FR/ICON-D2/generisch zurück (fail-soft, unverändertes Verhalten für
  Randzonen und Nicht-IT-Koordinaten).

### Quellen-Transparenz (`_SOURCE_LABELS`)
- Neuer Eintrag: `"ARPAE-2I"` → **"ARPAE ICON-2I (2 km, Italien)"**.
- Alle Konsumenten lesen `source` ausschließlich über `source_label()` — kein
  weiterer Code-Fix nötig (bestätigt bei #1161/#1162).

### Bestandsschutz — Test-Anpassung (kein neuer Bug, erwartetes Verhalten)
`tests/tdd/test_issue_1162_radar_dpc.py::test_ac3_dpc_failure_falls_back_to_next_source`
bricht DPC für Rom real (`radar_dpc.BASE_URL` auf ungültiges Schema) und erwartet
aktuell `result.source in ("AROME-FR", "ICON-D2", "minutely_15")`. Rom liegt in
keiner dieser drei Boxen — nach dieser Änderung landet der Fallback korrekt bei
`"ARPAE-2I"`. Die Assertion wird um `"ARPAE-2I"` erweitert. Das ist die
beabsichtigte Verhaltensverbesserung dieses Issues, keine Regression.

## Expected Behavior

- **Input:** Koordinaten (aus heutiger Etappe) bzw. `### now`/`JETZT` Inbound;
  Scheduler-Tick bei Alerts.
- **Output:** Bei DPC-Verfügbarkeit unverändert `source=="DPC"`. Bei DPC-Ausfall
  für eine IT-Koordinate: `source=="ARPAE-2I"` statt direktem Sprung zu
  AROME-FR/ICON-D2/generisch.
- **Side effects:** Keine (reiner Lese-/Fetch-Pfad).

## Acceptance Criteria

- **AC-1:** Given Radar-DPC liefert für eine Süd-IT-Koordinate (Rom 41.90/12.50
  oder Palermo 38.12/13.36) real keine Frames (DPC-Fetch-Methode durch eine
  `[]`-liefernde Instanzmethode ersetzt — DI ohne Mock, Muster #1161/#1162) /
  When `RadarNowcastService.get_nowcast(lat, lon)` aufgerufen wird / Then ist
  `result.source == "ARPAE-2I"` und `result.frames` enthält ≥1 reale Frame mit
  numerischer Niederschlagsrate (mm/h ≥ 0) — der Rückfall landet beim
  italienischen Modell, nicht direkt beim globalen `minutely_15`-Fallback.
  - Test: `_fetch_radar_dpc` durch `[]`-liefernde Methode ersetzt, echter HTTP-Call
    für den ARPAE-Schritt. Kein Mock.

- **AC-2:** Given Radar-DPC ist verfügbar und liefert reale Frames für eine
  IT-Koordinate / When `get_nowcast` aufgerufen wird / Then bleibt
  `result.source == "DPC"` — Radar behält Vorrang vor dem Modell-Rückfall, keine
  Regression an #1162.
  - Test: Echter Live-Call gegen Rom ohne DI; assert `source == "DPC"` (Muster
    `test_ac2_dpc_live_get_nowcast_uses_dpc_source_for_it_coordinate` aus #1162).

- **AC-3:** Given sowohl Radar-DPC als auch ARPAE-2I liefern leer/Fehler (beide
  Fetch-Methoden durch `[]`-liefernde Instanzmethoden ersetzt) / When
  `get_nowcast` für eine Koordinate außerhalb AROME-FR/ICON-D2 (Rom) aufgerufen
  wird / Then fällt die Kette fail-soft auf `source == "minutely_15"` zurück,
  ohne Absturz.
  - Test: Beide `_fetch_radar_dpc` und `_fetch_italy_arpae` durch `[]`-liefernde
    Methoden ersetzt (DI ohne Mock); assert `source == "minutely_15"`, kein Raise.

- **AC-4:** Given ein `NowcastResult` mit `source == "ARPAE-2I"` / When
  `source_label(result.source)` es abbildet / Then enthält das Label "ARPAE" und
  "Italien" — transparente Quellenangabe, kein generisches Label.
  - Test: Pure-Function-Test, `RadarNowcastService().source_label("ARPAE-2I")`
    enthält beide Teilstrings. Deterministisch, kein Netz.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_dpc_failure_falls_back_to_arpae_italy` |
| AC-2 | `test_ac2_dpc_available_keeps_dpc_priority_over_arpae` |
| AC-3 | `test_ac3_dpc_and_arpae_both_fail_falls_back_to_minutely15` |
| AC-4 | `test_ac4_source_label_transparent_arpae_italy` |

Zusätzlich: Erweiterung von
`tests/tdd/test_issue_1162_radar_dpc.py::test_ac3_dpc_failure_falls_back_to_next_source`
um `"ARPAE-2I"` in der erlaubten Ergebnismenge (Bestandsschutz, s.o.).

Neue Testdatei: `tests/tdd/test_feature_1186_arpae_it_fallback.py` (mock-frei).

## Known Limitations

- **15-Minuten-Werte für Italien sind interpoliert, kein echtes Minuten-Radar:**
  Open-Meteo liefert natives 15-Min-Raster nur für HRRR/ICON-D2/AROME. Für
  `italia_meteo_arpae_icon_2i` werden `minutely_15`-Werte aus Stundenwerten
  interpoliert. Als Rückfall unter dem echten DPC-Radar ist das ein
  proportionaler Abstrich — primäre Quelle bleibt das Radar.
- **Kein eigener Konvektions-Sidecar für ARPAE:** ARPAE führt `weather_code`
  bereits mit (wie AROME-FR/ICON-D2), daher kein Sidecar-Merge nötig — anders
  als bei DPC/INCA.
- **Gemeinsame Box statt eigener Italien-Box:** Der ARPAE-Rückfall greift exakt
  in der bestehenden `_within_dpc`-Domäne. Sollte diese Box künftig geschärft
  werden, wandert der ARPAE-Rückfall automatisch mit — bewusst gekoppelt, kein
  eigenständiges Abdeckungsgebiet.

## Changelog

- 2026-07-09: Initial spec created (Issue #1186) — ARPAE ICON-2I als
  Modell-Rückfall innerhalb der bestehenden DPC-Box, nach #1162 (live).
