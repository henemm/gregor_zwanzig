# Context: Issue #761 — ICON-D2 (~2 km) explizit für Zentraleuropa/Alpen

## Request Summary
Analog zu #734 (AROME-FR) eine **ICON-D2**-Quelle (DWD, ~2 km) explizit in die
koordinaten-basierte Nowcast-Kette einhängen — für wander-relevante Zentraleuropa-/
Alpen-Regionen, die heute auf den intransparenten Open-Meteo-`best_match` zurückfallen
(östliche Alpen, Dolomiten, Slowenien, Tschechien, östliche Schweiz — also alles, was
DE-RADOLAN, AT-INCA und die FR-AROME-Box NICHT abdecken).

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/radar_service.py` | Kette `_fetch_frames_with_fallback`, Bbox-Guards, geteilter `_fetch_openmeteo_15(lat,lon,models=)`, `format_now_text`-Label-Map — exakt das #734-Vorbild |
| `providers.brightsky.RadarFrame` | Gemeinsames Frame-Format (`timestamp`, `precip_mm_h`, `is_convective`) |
| `docs/specs/modules/radar_nowcast_france.md` | #734-Spec = strukturelles Vorbild für diese Spec |
| `tests/tdd/test_feature_734_arome_france_nowcast.py` | Test-Vorbild (mock-frei, reale API) |

## Existing Patterns (#734 etabliert)
- **Quellen-Kette:** `_within_<region>` Bbox-Guard + `_fetch_<model>` → `if frames: return frames, "<LABEL>"`. Fail-soft.
- **Geteilter Fetch:** `_fetch_openmeteo_15(lat, lon, models=None)` hängt `&models=<x>` an dieselbe Open-Meteo-`minutely_15`-URL. ICON-D2 = ein weiterer Aufruf mit `models="icon_d2"`.
- **Transparente Labels:** `format_now_text`-Map nennt das echte Modell.
- **Konvektion:** `weather_code` (WMO 95/96/99) → `is_convective` via `_is_convective_weathercode`.

## Verifizierte API-Fakten (echte Open-Meteo-Calls, 2026-06-11)
- **Modellname = `icon_d2`** (NICHT `icon_d2_15min` — das wirft „invalid MultiDomains"-Fehler).
- `models=icon_d2` liefert `minutely_15` mit `precipitation` UND `weather_code`. ✓
- **Domäne = rotiertes Gitter, NICHT rechteckig:** Innerhalb (Schweiz 46/7.5, Dolomiten 46.4/11.8, Tschechien 49.7/15, Slowenien 46.2/14.5) → echte Werte. Außerhalb des Gitters (Polen-Tatra 49.2/20, alle Rechteck-Ecken, Korsika, Schottland, Lappland) → **`precipitation: [None, None]`** (keine Interpolation!). Sehr weit weg (Atlantik) → API-`error`.

## ⚠️ Zentrale Design-Nuance (Unterschied zu #734)
Der geteilte Parser `_fetch_openmeteo_15` wandelt `None`→`0.0`. Bei AROME unkritisch (AROME-Domäne ≈ Rechteck, liefert in der ganzen #734-Bbox echte 0.0-Werte, kein None). Bei **ICON-D2** würde ein Punkt **innerhalb der Bbox aber außerhalb des rotierten Gitters** all-None→0.0→nicht-leere Frames erzeugen → fälschlich „ICON-D2" mit Schein-Nullen melden statt auf best_match durchzufallen.
**Lösung:** Beim expliziten Modell-Pfad (wenn `models` gesetzt) muss der Fetch `[]` liefern, wenn **alle** `precipitation`-Werte `None` sind (= Punkt außerhalb der Modell-Domäne). Der globale best_match-Pfad (`models=None`) behält das bisherige `None`→`0.0`-Verhalten. Damit ist der All-None-Guard — nicht die Bbox-Form — der eigentliche Korrektheits-Mechanismus; die Bbox grenzt nur grob ein, um sinnlose Calls für ferne Punkte zu sparen.

## Dependencies
- **Upstream:** `httpx`, Open-Meteo `/v1/forecast?models=icon_d2`.
- **Downstream:** `_show_now` (JETZT/### now), `trip_alert` (Radar-Alerts) — unverändert, konsumieren nur `NowcastResult`.

## Existing Specs
- `docs/specs/modules/radar_nowcast_france.md` (#734) — direktes Vorbild
- `docs/specs/modules/radar_nowcast.md` (#656) — Basis-Modul

## Risks & Considerations
- **Ketten-Reihenfolge:** RADOLAN(DE) → INCA(AT) → AROME-FR → **ICON-D2** → minutely_15. DE/AT treffen ihr Radar zuerst; AROME-FR (1,5 km, höher aufgelöst) hat Vorrang in der West-Überlappung (Schweiz-West/Benelux); ICON-D2 füllt östlich der AROME-Box (Dolomiten lon>10, Slowenien, Tschechien, Ost-Alpen).
- **All-None-Guard ist Pflicht** (siehe oben) — sonst stille Falsch-Labels.
- **Bbox:** konservatives Rechteck ~lat 44–58 N, lon 2–19 E; Gitter-Ecken fängt der None-Guard.
- **Backlog/niedrige Prio** — kleiner, additiver Schritt; ~70–110 LoC analog #734.
- Echtes Radar bleibt DE/AT; ICON-D2 ist (wie AROME) ein konvektionsauflösendes Modell, kein Radar-Pixel — in #734-Spec bereits ehrlich abgegrenzt.
