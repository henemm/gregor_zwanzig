# External Validator Report

**Spec:** docs/specs/bugfix/snapshot_missing_coordinates.md
**Datum:** 2026-04-12T16:00:00+02:00
**Server:** https://gregor20.henemm.com
**Validator:** External (unabhaengig, post-fix)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Save: Snapshot-JSON enthaelt lat, lon, elevation_m pro Segment-Endpunkt | Save mit bekannten Koordinaten (47.2692, 11.4041, elev=574 / 47.2085, 11.461, elev=2246) → JSON enthaelt alle 6 Felder pro Segment mit exakten Werten | **PASS** |
| 2 | Load: Rekonstruierte Segmente haben echte Koordinaten | Load nach Save → start_point=(47.2692, 11.4041, 574), end_point=(47.2085, 11.461, 2246) — NICHT (0.0, 0.0, None) | **PASS** |
| 2b | Abwaertskompatibilitaet: Alte Snapshots laden ohne Fehler | gr221-mallorca.json (ohne Koordinaten-Felder, 2026-04-05) → laedt ohne Crash, Fallback auf (0.0, 0.0, None) | **PASS** |
| 3 | Alerts: API-Calls gehen an korrekte Koordinaten | Nach Save+Load: alle Segment-Koordinaten im Alpenbereich (47.2N, 11.4E), keine Dummy-Werte (0.0, 0.0) | **PASS** |
| 4 | Formatter: Kein Crash bei fehlender elevation_m | TripReportFormatter.format_email() mit altem Snapshot (elevation_m=None) → kein TypeError, Report wird generiert | **PASS** |

## Test-Methodik

Black-Box-Tests gegen die Service-Schnittstellen (keine Source-Code-Inspektion):

1. **Save-Test:** WeatherSnapshotService.save() mit 2 Segmenten mit bekannten Innsbruck-Koordinaten aufgerufen, dann JSON-Datei auf Vorhandensein der 6 Koordinaten-Felder geprueft
2. **Load-Test:** WeatherSnapshotService.load() auf das gespeicherte Snapshot, Koordinaten der rekonstruierten TripSegment-Objekte verifiziert
3. **Abwaertskompatibilitaet:** Load des alten gr221-mallorca.json (ohne Koordinaten-Felder) — kein Crash, Fallback funktioniert
4. **Alert-Pfad:** Koordinaten nach Load sind echt (47.2N, 11.4E), nicht (0.0, 0.0)
5. **Formatter:** format_email() mit altem Snapshot (alle elevation_m=None) — kein TypeError
6. **CLI Evening Report:** `--report evening` mit Innsbruck-Trip zeigt "(1000m)" und "(2246m)" korrekt an

## Findings

### Keine kritischen Findings

Alle 4 Expected Behaviors + Abwaertskompatibilitaet bestanden.

### Hinweis: Alte Snapshots behalten Dummy-Koordinaten (Known Limitation)

- **Severity:** LOW (dokumentiert)
- **Expected:** Spec dokumentiert: "Alte Snapshots behalten Dummy-Koordinaten bis zum naechsten Save"
- **Actual:** gr221-mallorca.json (2026-04-05) hat keine Koordinaten-Felder → Fallback (0.0, 0.0, None). Erst nach erneutem Save werden echte Koordinaten persistiert.
- **Evidence:** `svc.load("gr221-mallorca")` → `start_point=(0.0, 0.0), elevation_m=None`

### Hinweis: WebSocket-Verbindungsproblem auf Web-UI

- **Severity:** LOW (nicht bugfix-relevant)
- **Expected:** Web-UI funktioniert
- **Actual:** "Message too large for WebSocket transmission" auf https://gregor20.henemm.com
- **Evidence:** WebFetch der Startseite zeigt "Connection lost. Trying to reconnect..."

## Verdict: VERIFIED

### Begruendung

Alle 4 Expected Behaviors der Spec sind nachweislich erfuellt:

1. **Save** persistiert `start_lat`, `start_lon`, `start_elevation_m`, `end_lat`, `end_lon`, `end_elevation_m` pro Segment mit exakten Werten (Round-Trip-Test)
2. **Load** rekonstruiert echte Koordinaten — keine Dummy-Werte mehr
3. **Alert-Pfad** wuerde korrekte Alpen-Koordinaten nutzen (47.2N, 11.4E), nicht Golf von Guinea (0.0, 0.0)
4. **Formatter** crasht nicht bei `elevation_m=None` — alte Snapshots werden fehlerfrei formatiert

Abwaertskompatibilitaet funktioniert wie in der Spec als Known Limitation dokumentiert.
