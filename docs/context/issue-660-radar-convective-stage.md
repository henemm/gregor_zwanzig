# Context: Issue #660 — Radar-Nowcast Gewitter/Hagel-Stufe via Konvektions-Indikator

## Request Summary
Folge zu #656: Eine 5. Intensitätsstufe „Starker Hagel/Gewitter" im Radar-Nowcast, die nicht aus der Regenrate (mm/h) ableitbar ist, sondern einen Konvektions-/Gewitter-Indikator der Datenquelle braucht. Heute kennt `intensity_to_text` nur 4 rate-basierte Stufen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | `intensity_to_text` (4 Stufen), `get_nowcast`, `_derive_result`, `format_now_text`, alle 3 Fetch-Pfade |
| `src/providers/brightsky.py` | `RadarFrame(timestamp, precip_mm_h)` — kein Typ-Feld; BrightSky `plain` liefert keinen Konvektions-Indikator |
| `src/providers/geosphere.py` | `fetch_nowcast` parst `pt` bereits → `PrecipType` (Codes 0–4: none/rain/snow/mixed/freezing_rain); **kein Gewitter-Code** |
| `src/app/models.py` | `PrecipType`-Enum (RAIN/SNOW/MIXED/FREEZING_RAIN); `ForecastDataPoint.precip_type` |
| `src/services/trip_alert.py` | `check_radar_alerts` (severity HIGH bereits), `radar_alert_due`, Versand E-Mail/Telegram |
| `docs/specs/modules/radar_nowcast.md` | Bestehende Spec inkl. „Known Limitations" → Gewitter-Stufe bewusst zurückgestellt |
| `tests/tdd/test_feature_656_radar_nowcast.py` | Mock-freie Test-Referenz für #656 |

## Existing Patterns
- **Fallback-Quellenkette** in `_fetch_frames_with_fallback`: BrightSky (DE) → GeoSphere INCA (AT) → Open-Meteo `minutely_15` (global). Open-Meteo ist der einzige Pfad, der GR20/Korsika abdeckt.
- **`RadarFrame`** trägt aktuell nur `precip_mm_h` — additive Erweiterung um ein Konvektions-Flag ist der saubere Hebel.
- **`intensity_to_text(mm_per_h)`** ist eine pure Funktion mit aufsteigenden Schwellen; eine optionale `is_convective`-Eskalation fügt sich nahtlos ein.
- **`_derive_result`** ermittelt `max_rate` über das Nowcast-Fenster → Konvektion analog als „irgendein Frame im Fenster konvektiv" aggregierbar.
- **Radar-Alert** schreibt bereits severity HIGH; Konvektion = höchste Priorität braucht nur eine Label-/Kennzeichnung.

## Verifizierte Quellen-Eignung (reale API-Checks heute)
- **Open-Meteo `minutely_15=precipitation,weather_code`** liefert an Korsika-Koordinate (42.15, 9.13) `weather_code` (WMO) mit. WMO-Codes **95 = Gewitter, 96 = Gewitter mit leichtem Hagel, 99 = Gewitter mit starkem Hagel**. → **Globaler Konvektions-Indikator, deckt die eigentliche Zielgruppe (GR20/Korsika), gleicher Endpunkt wie heute.**
- **GeoSphere INCA `pt`:** Codes 0–4 enthalten KEINEN Gewitter-/Hagel-Typ; Abdeckung nur Österreich (Zielgruppe GR20/Korsika fällt raus). → als Konvektions-Quelle ungeeignet bzw. nachrangig.
- **BrightSky `plain`:** kein Konvektions-Feld → bleibt 4-Stufen-Fallback (keine Falsch-Eskalation, AC-konform).

## Dependencies
- Upstream: Open-Meteo `minutely_15` (bereits genutzt), `RadarFrame`, `NowcastResult`.
- Downstream: `format_now_text` (Ad-hoc `### now`), `check_radar_alerts` (proaktiver Alert).

## Existing Specs
- `docs/specs/modules/radar_nowcast.md` (Issue #656) — wird um die Gewitter-Stufe erweitert (Known Limitation auflösen).

## Risks & Considerations
- **Additivität:** Default-Verhalten ohne Indikator muss bit-identisch bleiben (4-Stufen-Fallback) — `is_convective` defaultet auf `False`.
- **Keine Falsch-Eskalation:** Nur explizite WMO-Codes 95/96/99 (nicht z. B. „Regen") lösen die Stufe aus.
- **Mock-frei:** AC-Test gegen echte Open-Meteo-API; Gewitter-Lage ist wetterabhängig → für den deterministischen Stufen-Test reale WMO-Code-Beispielwerte durch den Service schicken (DI-Seam `frame_source`), für den End-to-End-Test echte API.
- **Eskalations-Priorität:** Konvektion schlägt rate-basierte Stufe (auch bei niedriger mm/h kann Gewitter herrschen).
