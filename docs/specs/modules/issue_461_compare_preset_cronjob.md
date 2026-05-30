---
entity_id: issue_461_compare_preset_cronjob
type: module
created: 2026-05-30
updated: 2026-05-30
status: implemented
version: "1.0"
issue: 461
tags: [compare, preset, cronjob, scheduler, dispatch, heartbeat, python, go]
---

# Issue #461 — Orts-Vergleich: Compare-Preset Tagesversand Cronjob

## Approval

- [x] Approved (2026-05-30)

## Purpose

Implementiert den automatischen Tagesversand aller `schedule='daily'`-Compare-Presets um 06:00 Uhr: Der Go-Scheduler löst täglich einen Python-Endpoint aus, der über alle fälligen Presets iteriert, die Compare-Engine aufruft, die E-Mail rendert und via Resend versendet. Fehler einzelner Presets blockieren nicht den Gesamtlauf — nach vollständig fehlerfreiem Lauf wird ein BetterStack-Heartbeat gepingt, um den Betrieb extern nachweisbar zu überwachen.

## Source

**Geänderte Dateien (Go-Backend):**
- `internal/config/config.go` — +1 Feld `HeartbeatComparePresets string`
- `internal/scheduler/scheduler.go` — +1 Struct-Feld, +1 in `New()`, +1 jobDef `"0 6 * * *"`, +1 Methode `comparePresetsDaily()`

**Geänderte Dateien (Python-Backend):**
- `api/routers/scheduler.py` — +1 Endpoint `POST /api/scheduler/compare-presets-daily`, Hilfsfunktionen `_run_compare_presets_daily()`, `_save_preset_status()`, `_ping_heartbeat_compare_presets()`

**Neue Dateien (Tests):**
- `tests/tdd/test_issue_461_compare_preset_dispatch.py` — 3 Testklassen (~120 LoC)

> **Schicht-Hinweis:** Zweischichtige Änderung. Go-Scheduler (`internal/scheduler/`) löst den Dispatch-Endpunkt per HTTP aus. Die Versandlogik selbst (JSON-Lesen, Compare-Engine, Resend) liegt ausschließlich im Python-Backend (`api/routers/scheduler.py`). SvelteKit-Frontend bleibt unberührt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/config/config.go` — `Config`-Struct | intern (Go) | Aufnahme von `HeartbeatComparePresets` als neues ENV-Feld (`GZ_HEARTBEAT_COMPARE_PRESETS`) |
| `internal/scheduler/scheduler.go` — `morningSubscriptions()` | intern (Go) | Referenz-Muster für Heartbeat-Logik und `recordRun()`-Aufruf; `comparePresetsDaily()` folgt demselben Pattern |
| `internal/scheduler/scheduler.go` — `runForAllUsers()` | intern (Go) | Führt den Python-Endpoint pro User aus; `comparePresetsDaily()` nutzt dieselbe Methode |
| `api/routers/scheduler.py` — bestehende Router-Klasse | intern (Python) | Neuer Endpoint wird als Methode derselben Klasse ergänzt; nutzt bestehende `_ping_heartbeat()`-Infrastruktur |
| `api/routers/scheduler.py` — `_run_morning_subscriptions()` | intern (Python) | Referenz-Muster für Preset-Iteration, Fehlerbehandlung per-Item und Heartbeat-Ping-Logik |
| `app.loader` — `_parse_activity_profile()` | intern (Python) | Konvertiert Go-Uppercase-String (`"WINTERSPORT"`) in Python-Enum; gibt `None` bei unbekanntem Wert zurück (Engine fällt auf ALLGEMEIN-Fallback) |
| Compare-Engine (`src/services/compare_engine.py` o.ä.) | intern (Python) | Führt den eigentlichen Ortsvergleich aus; Input: Locations, `target_date`, `forecast_hours`, Aktivitätsprofil; Output: `CompareResult` mit `result.locations[0].location.name` als `top_ort` |
| Resend SMTP / E-Mail-Adapter | extern | Versand der Compare-E-Mail an `preset["empfaenger"]` |
| `data/users/{user_id}/compare_presets.json` | Datei (JSON-Array) | Direktes `[...]`-Array ohne Wrapper-Objekt — kein `{"subscriptions":[...]}` |
| BetterStack Heartbeat (`GZ_HEARTBEAT_COMPARE_PRESETS`) | extern | Ping nur bei `error_count == 0` nach vollständigem Lauf |
| `internal/scheduler/scheduler_test.go` | Test (Go) | Jobs-Count-Test 5→6 anpassen; neuer Test `TestComparePresetsDaily_TriggersHeartbeat` |

## Implementation Details

### §1 `internal/config/config.go` — Neues Heartbeat-Feld

Neues Feld additiv ergänzen (analog zu bestehenden Heartbeat-Feldern):

```go
HeartbeatComparePresets string `envconfig:"HEARTBEAT_COMPARE_PRESETS" default:""`
```

ENV-Variable bleibt leer → kein Heartbeat-Ping (fail-soft, analog zu bestehenden Feldern). Kein Pflichtfeld.

### §2 `internal/scheduler/scheduler.go` — Neuer Job

**Struct-Feld:**
```go
heartbeatComparePresets string
```

**In `New()`** — Feld aus Config befüllen:
```go
heartbeatComparePresets: cfg.HeartbeatComparePresets,
```

**jobDef hinzufügen** (6 Jobs total, Start()-Log entsprechend anpassen: "5→6 jobs"):
```go
{"0 6 * * *", s.comparePresetsDaily, "compare_presets_daily", "Compare Presets Daily (06:00)"},
```

**Neue Methode `comparePresetsDaily()`** — exakt analog zu `morningSubscriptions()`:
```go
func (s *Scheduler) comparePresetsDaily() {
    log.Println("[scheduler] Running compare presets daily...")
    s.recordRun("compare_presets_daily", func() error {
        return s.runForAllUsers("compare_presets_daily", "/api/scheduler/compare-presets-daily")
    })
    s.mu.RLock()
    lr := s.lastRuns["compare_presets_daily"]
    s.mu.RUnlock()
    if lr != nil && lr.Status == "ok" {
        s.pingHeartbeat("compare_presets_daily", s.heartbeatComparePresets)
    }
}
```

Heartbeat wird NUR gepingt wenn `lr.Status == "ok"` — entspricht der globalen Heartbeat-Readiness-Pflicht aus CLAUDE.md.

### §3 `api/routers/scheduler.py` — Python-Dispatch-Endpoint

**Neuer Endpoint** (analog zu bestehenden Scheduler-Endpoints; Router hat bereits `prefix="/api/scheduler"`):
```python
@router.post("/compare-presets-daily")
def trigger_compare_presets_daily(user_id: str = "default"):
    count = _run_compare_presets_daily(user_id)
    return {"status": "ok", "count": count}
```

**Hilfsfunktion `_run_compare_presets_daily(user_id)`:**

1. Lade `data/users/{user_id}/compare_presets.json` als direktes JSON-Array `[...]` (KEIN Wrapper-Objekt)
2. Filtere: nur Presets mit `preset["schedule"] == "daily"`
3. Setze `error_count = 0`
4. Iteriere über gefilterte Presets:
   a. Lese `locations = preset["location_ids"]` — bei leer oder fehlend: `error_count += 1`, `log.warning(...)`, `continue`
   b. Konvertiere `preset["profil"]` via `_parse_activity_profile(preset.get("profil", "").lower())` → `activity_profile` (`.lower()` nötig: Go speichert Uppercase `"WINTERSPORT"`, Python-Enum erwartet Lowercase `"wintersport"`; None = Engine-Fallback ALLGEMEIN)
   c. Rufe Compare-Engine auf mit `target_date = date.today()`, `forecast_hours = 48`, `hour_from = preset["hour_from"]`, `hour_to = preset["hour_to"]`, `activity_profile`
   d. Bei Exception: `log.error(...)`, `error_count += 1`, `continue` (kein Abbruch des Gesamtlaufs)
   e. Bestimme `top_ort`: `result.locations[0].location.name` wenn `result.locations` nicht leer, sonst `None`
   f. Rendere E-Mail-Template mit Compare-Result
   g. Sende via Resend an alle `preset["empfaenger"]`
   h. Bei Sende-Exception: `log.error(...)`, `error_count += 1`, `continue`
   i. Rufe `_save_preset_status(user_id, preset["id"], top_ort)` auf
5. Rückgabe `error_count`

**Hilfsfunktion `_save_preset_status(user_id, preset_id, top_ort)`** — BUG-DATALOSS-GR221-konform:

1. Lese `data/users/{user_id}/compare_presets.json` als direktes Array
2. Finde Preset nach `p["id"] == preset_id`
3. Überschreibe NUR zwei Felder:
   - `preset["letzter_versand"] = datetime.utcnow().isoformat() + "Z"`
   - `preset["top_ort_letzter_versand"] = top_ort` (String oder `None`)
4. Alle anderen Felder bleiben erhalten (Read-Modify-Write — kein Full-Replace)
5. Schreibe Array zurück nach `compare_presets.json`

**Hilfsfunktion `_ping_heartbeat_compare_presets()`:**

Liest `GZ_HEARTBEAT_COMPARE_PRESETS` aus ENV. Wenn nicht leer: HTTP GET auf die URL (analog zu bestehenden Heartbeat-Pings). Wird NUR aufgerufen wenn `error_count == 0` — der Go-Scheduler übernimmt diesen Ping bereits über `pingHeartbeat()`, der Python-Endpoint muss ihn nicht doppelt feuern. Der Endpoint antwortet mit `{"status": "ok"}` unabhängig vom `error_count`, da Go den Job-Status über `recordRun()` trackt.

### §4 `tests/tdd/test_issue_461_compare_preset_dispatch.py` — Teststruktur

Drei Testklassen ohne Mocks (Projekt-Konvention: keine `Mock()`, `patch()`, `MagicMock`):

**Klasse 1 — `TestComparePresetsJsonFormat`:**
- Verifiziert, dass `compare_presets.json` als direktes Array gelesen wird (nicht als `{"subscriptions":[...]}`)
- Legt echte Testdatei an, liest via `_run_compare_presets_daily()`, prüft korrekte Filterung

**Klasse 2 — `TestComparePresetDispatchIsolation`:**
- Fehler bei einem Preset (z.B. leere `location_ids`) unterbricht nicht den Lauf der anderen
- Prüft `error_count` und Log-Ausgaben

**Klasse 3 — `TestPresetStatusSave`:**
- Nach Versand werden `letzter_versand` (ISO-datetime) und `top_ort_letzter_versand` korrekt in JSON gesetzt
- Alle anderen Preset-Felder bleiben erhalten (Roundtrip-Prüfung gegen Pre-State)

### §5 LoC-Budget

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/config/config.go` | +1 Feld | ~2 |
| `internal/scheduler/scheduler.go` | +1 Feld, +1 New()-Zeile, +1 jobDef, +1 Methode | ~22 |
| `internal/scheduler/scheduler_test.go` | jobs-count 5→6, neuer Test | ~40 |
| `api/routers/scheduler.py` | +1 Endpoint, +3 Hilfsfunktionen | ~115 |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py` | NEU — 3 Testklassen | ~120 |
| **Gesamt** | | **~299 LoC** |

LoC-Override vor Implementierungsstart setzen:
```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 350
```

## Expected Behavior

- **Input:** Täglicher Cron-Trigger um 06:00 vom Go-Scheduler via `POST /api/scheduler/compare-presets-daily`; User-ID kommt aus Auth-Kontext; `compare_presets.json` enthält das direkte JSON-Array der Presets des Users.
- **Output:**
  - HTTP 200 `{"status": "ok"}` vom Python-Endpoint (unabhängig von `error_count` auf Einzel-Preset-Ebene)
  - Compare-E-Mail an alle `preset["empfaenger"]` für jeden erfolgreich verarbeiteten `daily`-Preset
  - `letzter_versand` und `top_ort_letzter_versand` werden in `compare_presets.json` nach jedem erfolgreichen Versand aktualisiert
  - BetterStack-Heartbeat-Ping via Go-Scheduler, wenn `lr.Status == "ok"` (d.h. kein HTTP-Fehler auf Endpoint-Ebene)
- **Side effects:**
  - `data/users/{user_id}/compare_presets.json` wird nach jedem erfolgreichen Preset-Versand per Read-Modify-Write aktualisiert
  - Log-Einträge auf WARNING-Ebene für jeden fehlgeschlagenen Preset (`error_count += 1`, kein Abbruch)
  - Kein Heartbeat-Ping wenn ein Preset-Fehler auftrat (`error_count > 0` blockiert Ping auf Go-Seite)

## Acceptance Criteria

**AC-1:** Given mindestens ein Preset mit `schedule='daily'` in `compare_presets.json` eines Users / When der Scheduler `POST /api/scheduler/compare-presets-daily` um 06:00 Uhr auslöst / Then werden alle `daily`-Presets verarbeitet und je eine Compare-E-Mail an die konfigurierten Empfänger versendet
  - Test: (populated after /tdd-red)

**AC-2:** Given zwei `daily`-Presets, wobei das erste leere `location_ids` hat / When der Endpoint aufgerufen wird / Then wird das erste Preset mit `error_count += 1` übersprungen und das zweite Preset vollständig verarbeitet und versendet (kein Abbruch des Gesamtlaufs)
  - Test: (populated after /tdd-red)

**AC-3:** Given ein vollständig fehlerfreier Lauf über alle `daily`-Presets (`error_count == 0`) / When der Go-Scheduler den Python-Endpoint aufruft und `lr.Status == "ok"` ist / Then wird der BetterStack-Heartbeat unter `GZ_HEARTBEAT_COMPARE_PRESETS` genau einmal gepingt
  - Test: (populated after /tdd-red)

**AC-4:** Given ein erfolgreich versendetes Preset mit `id="cp-abc"` / When `_save_preset_status()` aufgerufen wird / Then enthält `compare_presets.json` für dieses Preset ein aktualisiertes `letzter_versand` im ISO-datetime-Format sowie `top_ort_letzter_versand` als String; alle anderen Felder des Presets sind byte-identisch zum Pre-State (BUG-DATALOSS-GR221-Schutz)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein `schedule='weekly'`-Support in #461:** Nur `schedule='daily'`-Presets werden verarbeitet. Weekly-Presets bleiben für einen späteren Issue reserviert.
- **`forecast_hours` fest auf 48:** ComparePreset hat kein eigenes `forecast_hours`-Feld; der Wert ist im Endpoint hartcodiert. Eine Konfigurierbarkeit pro Preset ist nicht vorgesehen.
- **Heartbeat auf Go-Ebene:** Der Python-Endpoint pingt den Heartbeat nicht selbst — das übernimmt der Go-Scheduler via `pingHeartbeat()`. Bei direktem Aufruf des Python-Endpoints (z.B. im Staging-Test) wird kein Heartbeat gefeuert.
- **Ortszeit-Cron fix auf 06:00 UTC:** Der Cron-Ausdruck `"0 6 * * *"` ist UTC-basiert. Bei Empfängern in anderen Zeitzonen kann der tatsächliche Versandzeitpunkt abweichen.
- **Kein Retry bei Versandfehlern:** Schlägt der Resend-Aufruf für ein Preset fehl, wird es für diesen Tag nicht erneut versucht. Ein Retry-Mechanismus ist nicht vorgesehen.

## Changelog

- 2026-05-30: Initial spec — Issue #461. Tagesversand aller `daily`-Compare-Presets via Go-Scheduler + Python-Endpoint; BetterStack-Heartbeat nur bei `error_count == 0`; Read-Modify-Write für `letzter_versand`/`top_ort_letzter_versand` (BUG-DATALOSS-GR221-konform); 4 AC im AC-N-Format.
