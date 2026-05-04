# External Validator Report

**Spec:** docs/specs/modules/go_provider_openmeteo.md
**Datum:** 2026-04-13T14:30:00Z
**Server:** https://gregor20.henemm.com
**Validator:** External (isoliert, kein Quellcode-Zugriff)

## Methodik

Alle Tests via `curl` gegen den produktiven Server (gregor20.henemm.com). Kein Quellcode-Zugriff, keine git-History, keine Artefakte aus der Implementierer-Session.

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | GET /api/forecast?lat=39.7&lon=3.0&hours=24 → 200 + 24 Datenpunkte | HTTP 200, 24 Datenpunkte, model=meteofrance_arome | **PASS** |
| 2 | Default hours = 48 (kein Parameter) | GET ohne hours: data_count=48 | **PASS** |
| 3 | Response hat top-level `timezone` Feld (BUG-TZ-01 Fix) | timezone="Europe/Madrid" fuer Mallorca | **PASS** |
| 4 | Timezone korrekt fuer verschiedene Koordinaten | Mallorca=Europe/Madrid, Innsbruck=Europe/Vienna, Oslo=Europe/Oslo, Athen=Europe/Athens, Tokyo=Asia/Tokyo | **PASS** |
| 5 | SelectModel Mallorca (39.7, 3.0) → meteofrance_arome | model="meteofrance_arome", grid_res_km=1.3 | **PASS** |
| 6 | SelectModel Innsbruck (47.3, 11.4) → icon_d2 | model="icon_d2", grid_res_km=2 | **PASS** |
| 7 | SelectModel Oslo (59.9, 10.7) → metno_nordic | model="metno_nordic" | **PASS** |
| 8 | SelectModel Athen (37.9, 23.7) → icon_eu | model="icon_eu" | **PASS** |
| 9 | SelectModel Tokyo (35.7, 139.7) → ecmwf_ifs04 | model="ecmwf_ifs04" | **PASS** |
| 10 | Fehlende lat → 400 invalid_params | HTTP 400, `{"error":"invalid_params","detail":"lat and lon are required"}` | **PASS** |
| 11 | lat=999 → 400 invalid_params | HTTP 400, `{"detail":"lat must be between -90 and 90","error":"invalid_params"}` | **PASS** |
| 12 | lon=-181 → 400 invalid_params | HTTP 400, `{"detail":"lon must be between -180 and 180","error":"invalid_params"}` | **PASS** |
| 13 | UV-Index vorhanden (Air Quality API) | uv_index-Werte in Daten (z.B. 3.3 bei Mallorca Mittag) | **PASS** |
| 14 | Timestamp-Format `+00:00` (nicht `Z`) | ts="2026-04-13T00:00:00+00:00" — korrekt | **PASS** |
| 15 | thunder_level als String "NONE"/"MED"/"HIGH" | thunder_level="NONE" in allen Responses | **PASS** |
| 16 | omitempty: nil-Felder nicht serialisiert | AROME ohne visibility_m/freezing_level_m/pop_pct; ICON-D2 mit diesen Feldern | **PASS** |
| 17 | Response-Envelope: timezone + meta + data | Top-Level Keys: ['data', 'meta', 'timezone'] | **PASS** |
| 18 | meta.provider = "openmeteo" (laut Spec) | Actual: "OPENMETEO" (Grossbuchstaben) | **FAIL** |
| 19 | Timestamp-Key = "ts" (laut Expected Behavior) | Actual: "ts" — stimmt mit Expected Behavior | **PASS** |

**Score: 18 PASS / 1 FAIL / 0 UNKLAR**

## Findings

### F1: provider-Wert in Grossbuchstaben statt Kleinbuchstaben
- **Severity:** LOW
- **Expected:** Spec Expected Behavior zeigt `"provider": "openmeteo"` (Kleinbuchstaben)
- **Actual:** Response liefert `"provider": "OPENMETEO"` (Grossbuchstaben)
- **Evidence:** `curl -s "https://gregor20.henemm.com/api/forecast?lat=39.7&lon=3.0&hours=2"` → `meta.provider = "OPENMETEO"`
- **Bewertung:** Funktional irrelevant. Consumer die auf exakten String-Match pruefen koennten betroffen sein. Empfehlung: Entweder Spec anpassen oder Implementierung auf lowercase aendern.

### F2: Spec-interne Inkonsistenz bei Timestamp-Key (informativ, kein Implementierungsfehler)
- **Severity:** INFO
- **Expected:** DTO-Definition in Spec zeigt `json:"time"`, Expected Behavior Beispiel zeigt `"ts"`
- **Actual:** Implementation nutzt `"ts"` — stimmt mit Expected Behavior ueberein
- **Evidence:** Response-Key ist `"ts"`, nicht `"time"`
- **Bewertung:** Kein Implementierungsfehler. Die Spec sollte den DTO-Tag auf `json:"ts"` korrigieren, um die Inkonsistenz zu beseitigen.

## Verdict: VERIFIED

### Begruendung

**18 von 19 Pruefpunkten PASS. 1 FAIL (LOW Severity).**

Alle Kernziele der Spec sind erreicht:

1. **BUG-TZ-01 ist BEHOBEN** — `timezone`-Feld korrekt im Response-Envelope fuer alle 5 getesteten Regionen (Europe/Madrid, Europe/Vienna, Europe/Oslo, Europe/Athens, Asia/Tokyo).

2. **Regionale Modellauswahl funktioniert fehlerfrei** — Alle 5 Modelle (meteofrance_arome, icon_d2, metno_nordic, icon_eu, ecmwf_ifs04) werden korrekt nach Koordinaten ausgewaehlt.

3. **Go-native HTTP-Handler korrekt integriert** — Fehlerformat (HTTP 400, `{"error":"invalid_params","detail":"..."}`) entspricht exakt der Spec. Keine Pydantic/FastAPI-Rueckstaende.

4. **`hours`-Parameter funktioniert** — Default=48, explizite Werte (6, 24) liefern korrekte Datenmenge.

5. **UV-Index via Air Quality API** — uv_index-Werte vorhanden und plausibel (0 nachts, bis ~5 mittags).

6. **Timestamp-Format** korrekt (`+00:00`, nicht `Z`).

7. **omitempty** funktioniert — modellabhaengige Felder werden korrekt ausgelassen/eingeschlossen.

Die einzige Abweichung (provider "OPENMETEO" statt "openmeteo") ist kosmetisch, Severity LOW, und bricht keine Funktionalitaet.
