# Decision Matrix — Forecast Source Selection

## Regeln (Gate)
1) Standard: **MET Norway (Locationforecast)**
2) Ausnahme: **MOSMIX**, nur wenn alle erfüllt:
   - Distanz ≤ 25 km
   - |ΔH| ≤ 150 m
   - Land/See-Flag: **gleich**
3) Sonst: MET
4) Fallback (nicht MVP): entfällt

## Confidence (nur zur *gewählten* Quelle)
- Start: 100
- Distanz > 10 km: −1 / 5 km (max −20)
- |ΔH| > 100 m: −1 / 50 m (max −20)
- *Gebirge*: −20 (Heuristik; s. unten)
- Ergebnisband: **HIGH** (75–100), **MED** (50–74), **LOW** (< 50)

## Debug (Beispiel)
```
source.decision: MOSMIX rejected (dist=20.0km, delta_h=220m, land_sea_match=false)
source.chosen: MET
source.confidence: MED (62)
source.coords: 54.29N,10.90E
source.meta: run=2025-08-28T19:12Z, model=ECMWF
```

## Datenquellen (Minimal)
- **MOSMIX Stationskatalog** (IDs, Lat/Lon, Höhe)
- **DEM** (SRTM/EU-DEM) für Höhen + ΔH
- **Land/See-Maske** (Natural Earth / ESA CCI)
- **Zeiten** UTC; Run-ID z. B. `2025-08-28T19:12Z`

## „Gebirge“-Heuristik
APIs liefern **keine** generische „Gebirge“-Flag. Minimalheuristik:
- `is_mountain = (elev ≥ 1200 m) OR (Relief_5km ≥ 400 m)`  → konfigurierbar
