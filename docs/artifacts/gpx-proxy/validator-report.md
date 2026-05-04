# External Validator Report

**Spec:** docs/specs/modules/gpx_proxy.md (v1.0, updated 2026-04-14)
**Datum:** 2026-04-14T06:55:00Z
**Server:** https://gregor20.henemm.com
**Validator:** External Validator (unabhaengig, kein Zugriff auf src/)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | POST /api/gpx/parse mit GPX-Datei → JSON mit name, date, waypoints[] | HTTP 200: `{"name":"Tag 1: von Valldemossa nach Deià","date":"2026-01-17","waypoints":[{"id":"G1","name":"Start","lat":39.710564,...},{"id":"G2",...},{"id":"G3",...},{"id":"G4",...}]}` | **PASS** |
| 2 | Query-Params stage_date + start_hour werden weitergeleitet | `stage_date=2026-01-17&start_hour=8` → date="2026-01-17", time_window startet 08:00; `stage_date=2026-01-18&start_hour=7` → date="2026-01-18", time_window startet 07:00 | **PASS** |
| 3 | Waypoints enthalten id, name, lat, lon, elevation_m, time_window | JSON-Schema-Check: alle 6 Felder vorhanden, keine Extra-Felder, keine fehlenden Felder | **PASS** |
| 4 | Ohne optionale Params: Defaults greifen (date=heute, start_hour=8) | Ohne Params: date="2026-04-14" (heute), time_window startet 08:00 | **PASS** |
| 5 | Kein file-Field → 422 mit FastAPI Validation | HTTP 422: `{"detail":[{"type":"missing","loc":["body","file"],"msg":"Field required","input":null}]}` | **PASS** |
| 6 | Leere GPX-Datei → 400 mit "no_file_content" | HTTP 400: `{"detail":"no_file_content"}` | **PASS** |
| 7 | Ungueltige GPX → 400 mit "Ungueltiges GPX-Format: ..." | HTTP 400: `{"detail":"Ungueltiges GPX-Format: Error parsing XML: syntax error: line 1, column 0"}` | **PASS** |
| 8 | Python nicht erreichbar → 503 mit core_unavailable | Nicht testbar ohne Prod-Downtime | **UNKLAR** |
| 9 | Invalid start_hour (>23) → 422 Validation | HTTP 422: `{"detail":[{"type":"less_than_equal","loc":["query","start_hour"],...,"ctx":{"le":23}}]}` | **PASS** |
| 10 | Invalid stage_date Format → 422 Validation | HTTP 422: `{"detail":[{"type":"date_from_datetime_parsing","loc":["query","stage_date"],...}]}` | **PASS** |
| 11 | Zweite GPX-Datei liefert andere korrekte Daten | Tag 2 (Deia→Soller): 3 Waypoints, name/date/waypoints korrekt | **PASS** |
| 12 | GET /api/gpx/parse → 405 Method Not Allowed | HTTP 405 | **PASS** |

## Findings

### Finding 1: 503-Fehlerfall nicht verifizierbar
- **Severity:** LOW
- **Expected:** Python-Backend nicht erreichbar → 503 mit `{"error":"core_unavailable"}`
- **Actual:** Nicht getestet — Python-Backend-Stop auf Prod waere destruktiv
- **Evidence:** Kein Test moeglich ohne Seiteneffekt auf Produktion

## Verdict: VERIFIED

### Begruendung

**11 von 12 Testpunkten: PASS.** Der einzige UNKLAR-Punkt (503 bei Python-Ausfall) ist ein destruktiver Test, der die Produktionsumgebung beeintraechtigen wuerde — kein realistischer Validierungstest.

Alle testbaren Expected Behaviors aus der Spec sind erfuellt:

1. **Happy Path:** GPX-Upload liefert korrektes JSON (name, date, waypoints mit allen 6 Feldern)
2. **Query-Params:** stage_date und start_hour werden korrekt durchgereicht; Defaults funktionieren
3. **Error Cases (4/4 testbar):** 422 bei fehlendem File und ungueltige Params, 400 bei leerem/invalidem GPX
4. **Response-Format:** Exakt wie in der Spec definiert — keine Extra-Felder, keine fehlenden Felder
5. **HTTP Methods:** Nur POST erlaubt

**Hinweis:** Die Spec wurde seit dem vorherigen AMBIGUOUS-Report aktualisiert (Changelog: "Error Cases an FastAPI-Standardverhalten angepasst"). Die aktuelle Implementation stimmt mit der aktuellen Spec ueberein.
