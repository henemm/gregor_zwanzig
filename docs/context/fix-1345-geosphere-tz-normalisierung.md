# Context: fix-1345-geosphere-tz-normalisierung

Issue: #1345 — AT-Cross-Provider-Fallback im Ernstfall wirkungslos: GeoSphere-Zeitstempel (aware) crashen die Briefing-Pipeline (naive)

## Analysis

### Type
Bug (priority:critical) — Analyse aus Vorsession, vollständig in Issue-Kommentaren dokumentiert und PO-bestätigt (2026-07-22). Code-Referenzen am 2026-07-22 gegen origin/main (27756aa7) re-verifiziert.

### Root Cause (verifiziert)
1. open-meteo-Totalausfall (503) → Weiche `openmeteo.py:926-930` (`direct_provider_for`) greift korrekt → `GeoSphereDirectProvider`.
2. GeoSphere liefert **timezone-aware** Zeitstempel (`src/providers/geosphere.py:518,625` — `fromisoformat(...replace("Z","+00:00"))`), Pipeline-Konvention ist **naive UTC**. Die Hausnorm wird nirgends erzwungen: `ForecastDataPoint.ts` ist nur als `datetime` typisiert (`src/app/models.py:94`), Pythons datetime unterscheidet naive/aware nicht.
3. Segment-Fensterung (`src/services/segment_weather.py:76 fetch_segment_weather`) vergleicht naive mit aware → `TypeError: can't compare offset-naive and offset-aware datetimes`.
4. `_is_transient_fetch_error(TypeError)` → False (`src/services/trip_report_scheduler.py:66-75`) → kein Retry → „All-failed weather data" → Briefing „Wetterdaten nicht verfügbar".

### Nebenfunde
- `src/providers/geosphere.py:397-400`: Cloud-Layer-Zeiten hartkodiert UTC+1 — im Sommer (AT=UTC+2) 1h daneben. Bei tz-Normalisierung mitziehen.
- Segment 4 im Vorfall: „Cannot compute metrics from empty timeseries" (GeoSphere lieferte leere Reihe) — separat zu prüfen.

### Lösungsrichtung (PO-bestätigt, Issue-Kommentar 2026-07-22)
Fix gehört in die **Normalisierungsschicht**, nicht (nur) in den Adapter: `ForecastDataPoint.__post_init__` (`src/app/models.py:144`, existiert bereits für wind_dir-Alias) normalisiert jede aware-Zeit nach UTC und streift tzinfo ab („normalize at the boundary"). Damit sind alle heutigen und künftigen Provider (#1143 FR, #1144 DE) strukturell abgesichert.

### Affected Files (geplant)
| File | Change | Description |
|------|--------|-------------|
| src/app/models.py | MODIFY | `__post_init__`: aware→UTC-naive Normalisierung für `ts` |
| src/providers/geosphere.py | MODIFY | Cloud-Layer UTC+1-Hartkodierung durch echte Zeitzonen-Konvertierung ersetzen |
| tests/ (Kern) | CREATE | Guard-Test aware→naive; E2E-Fallback-Test 503-Fixture + aufgezeichnete GeoSphere-Antwort → Briefing rendert |

### Scope Assessment
- Files: ~4 · Estimated LoC: +80/-10 · Risk: MEDIUM (zentrale Datenklasse, alle Provider betroffen — genau deshalb Guard-Tests)

### Technical Approach
1. Tz-Vertrag explizit: `ForecastDataPoint.__post_init__` normalisiert `ts` (aware → `astimezone(utc)` → `replace(tzinfo=None)`).
2. GeoSphere Cloud-Layer: naive Vienna-Zeiten korrekt über `ZoneInfo("Europe/Vienna")` nach UTC.
3. E2E-Fallback-Test (deterministischer Kern): Open-Meteo-503-Fixture → GeoSphere-Fixture (aufgezeichnet) → Briefing vollständig gerendert. Abnahme-Vorlage für #1143/#1144.
4. Retry-Erwartung (Issue Punkt 2): Nach tz-Fix existiert der TypeError nicht mehr; 503-Retry-Pfad (`trip_report_scheduler.py:1172`) per Regressionstest 503→200 absichern.

### Open Questions
— keine (PO-Richtung liegt wörtlich im Issue)
