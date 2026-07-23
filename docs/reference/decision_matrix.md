# Decision Matrix — Wetterdaten-Provider (Ist-Stand)

> Stand: 2026-07-21. Ersetzt das MET/MOSMIX-Auswahlmodell der MVP-Ära
> (historisch: ADR-0002, superseded). Quelle der Wahrheit für Details ist der
> Code — dieses Dokument beschreibt nur die Auswahllogik und wo sie liegt.

## Standard-Provider: Open-Meteo

Alle Produktionspfade (Briefings, Orts-Vergleich, Alerts, Vorschau) holen
Wetterdaten über `get_provider("openmeteo")` — Registry in
`src/providers/base.py` (`_load_providers()`).

## Fallback-Kette (in dieser Reihenfolge)

| Stufe | Was | Wo im Code | Referenz |
|---|---|---|---|
| 1 | **Intra-Modell-Fallback** innerhalb Open-Meteo: regionale Modelle → gröbere Modelle, ohne den Ausfall zu kaschieren | `src/providers/openmeteo.py` (`REGIONAL_MODELS`) | ADR-0018, #1115 |
| 2 | **Cross-Provider-Fallback** bei Open-Meteo-Totalausfall: Koordinate → regionale Direktanbindung (AT → `at_direct`/GeoSphere, DE → `de_direct`/ICON-D2-Open-Data-Direktprovider (DWD), FR → `fr_direct`/AROME-WCS-Direktprovider (Météo-France); Prüfreihenfolge AT→DE→FR, Alpenraum fällt bewusst an AT) | `src/providers/region_routing.py` | Epic #1127, #1141, #1143, #1144 |

## Weitere registrierte Provider

| Name | Zweck |
|---|---|
| `geosphere` | GeoSphere Austria (Direktanbindung, AT-Fallback-Basis) |
| `fr_direct` | Météo-France AROME-WCS (Direktanbindung, FR-Fallback, #1143) |
| `de_direct` | DWD ICON-D2 Open Data (GRIB2-Direktanbindung, DE-Fallback, #1144) |
| `brightsky` | DWD-Daten via BrightSky — genutzt im Radar-Pfad (`src/services/radar_service.py`) |
| `radar_dpc` | Radar-Nowcast Italien (DPC) |
| `fixture` | Offline-Testmodus: aktiv wenn `GZ_TEST_FIXTURE_DIR` gesetzt (#346) — bedient `openmeteo`-Anfragen aus versionierten Fixtures |

## Kontingent-Regeln (Open-Meteo)

Der Radar-Pfad dominiert den API-Verbrauch (#1329): geteilter Forecast-Cache +
Budget-/Prioritätssteuerung sind aktiv. Bei Änderungen an Abruf-Pfaden immer
den Kontingent-Effekt mitdenken; Verbrauchslog: `openmeteo_calls.jsonl`
(erfasst den Radar-Pfad NICHT).

## Historie

- MET Norway / MOSMIX (MVP-Auswahlmodell mit Distanz-/Höhen-Gate): entfernt,
  siehe ADR-0002 (superseded) und Git-Historie dieses Dokuments.
- Metrik-Mapping der Provider: steht im jeweiligen Provider-Modul
  (`src/providers/*.py`), nicht mehr in separater Prosa-Referenz.
