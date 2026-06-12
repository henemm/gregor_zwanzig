# Spec: GeoSphere-Nowcast — 0.0 ist ein echter Wert, kein None

- **Issue:** #777
- **Type:** Bug
- **Created:** 2026-06-12
- **Scope:** backend-only (`src/providers/geosphere.py`)
- **Status:** draft

## Problem

`GeoSphereProvider._parse_nowcast_response` transformiert API-Rohwerte mit dem Muster
`round(x, 1) if x else None`. Der Truthiness-Check `if x` ist bei `x == 0.0` falsch
(`0.0` ist in Python falsy) → der exakte Wert `0.0` wird als `None` gespeichert. Damit ist
ein **physikalisch echter** Messwert (trocken = 0.0 mm, windstill = 0.0 km/h) nicht mehr von
„kein Datenpunkt" (`None`) unterscheidbar.

Betroffene Zeilen (alle in `_parse_nowcast_response`):
- `geosphere.py:628` — `precip_1h_mm=round(precip, 1) if precip else None` (Niederschlag)
- `geosphere.py:620` — `wind_kmh = round(wind * 3.6, 1) if wind else None` (Wind)
- `geosphere.py:621` — `gust_kmh = round(gust * 3.6, 1) if gust else None` (Böe)

Konsequenz: Konsumenten, die `None` als „keine Daten" verwerfen
(`weather_metrics.py:787`, `comparison_engine.py:376`, `trip_report_scheduler.py:1090-1094`,
`aggregation.py`), lassen trockene/windstille Intervalle still aus Summen, Mittelwerten und
Zählungen herausfallen → verzerrte Aggregation.

## Lösung

Truthiness-Check `if x` durch expliziten `if x is not None` ersetzen — für Niederschlag,
Wind und Böe. Echte `None`-Werte (fehlender Datenpunkt, Index out of range) bleiben weiter
`None`; nur der Wert `0.0` wird jetzt korrekt als `0.0` durchgereicht.

## Acceptance Criteria

**AC-1:** Given ein GeoSphere-NOWCAST-Response mit `rr`-Wert `0.0` (trockenes Intervall),
When `_parse_nowcast_response` ihn parst, Then ist `precip_1h_mm` des entsprechenden
`ForecastDataPoint` exakt `0.0` (Typ float) und **nicht** `None`.

**AC-2:** Given ein GeoSphere-NOWCAST-Response mit `ff`-Wert `0.0` (windstill) und `fx`-Wert
`0.0` (keine Böe), When `_parse_nowcast_response` ihn parst, Then sind `wind10m_kmh` und
`gust_kmh` des entsprechenden `ForecastDataPoint` exakt `0.0` und **nicht** `None`.

**AC-3:** Given ein GeoSphere-NOWCAST-Response, bei dem ein Parameter-Array kürzer als die
Zeitstempel-Liste ist (echter fehlender Datenpunkt, Index out of range), When
`_parse_nowcast_response` ihn parst, Then bleibt das betroffene Feld `None` (echte Datenlücke
wird **nicht** zu 0.0 verfälscht) — die Unterscheidung None vs. 0.0 funktioniert in beide
Richtungen.

**AC-4:** Given ein NOWCAST-Response mit gemischten Nicht-Null-Werten (z.B. `rr=1.2`,
`ff=3.5`), When `_parse_nowcast_response` ihn parst, Then bleiben die transformierten Werte
unverändert korrekt (`precip_1h_mm=1.2`, `wind10m_kmh=round(3.5*3.6,1)=12.6`) — der Fix ändert
ausschließlich das Verhalten bei exakt `0.0`, keine Regression bei bestehenden Werten.

## Out of Scope

- `cli.py:123` (`if dp.wind10m_kmh`) — analoger Falsy-Bug, aber im **Anzeige-Konsumenten**,
  nicht im Parser. Separater Nebenbefund, ggf. eigenes Folge-Issue.
- `_parse_snowgrid_response` (`geosphere.py:577`, `snow_depth_m`) — anderer Pfad, nicht Teil
  des Issue-Scopes (#777 nennt explizit nur `_parse_nowcast_response`).

## Test-Strategie (mock-frei)

Der Parser ist eine reine Transformation eines API-Response-Dicts. Ein real-geformter
NOWCAST-Response (Struktur exakt wie GeoSphere liefert: `timestamps`, `features[0].properties.
parameters.{t2m,ff,fx,rr,...}.data`) wird durch den **echten** `_parse_nowcast_response`
geschickt — kein Mock, keine gepatchte Methode, nur echte Parser-Logik auf echt-geformten
Daten. Vor dem Fix liefert der Parser `None` für `0.0` (rot), nach dem Fix `0.0` (grün).
