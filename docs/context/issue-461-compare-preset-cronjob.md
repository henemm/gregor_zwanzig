# Context: Issue #461 — Compare-Preset Tagesversand Cronjob

## Request Summary

Täglicher automatischer Versand aller ComparePresets mit `schedule='daily'` um 06:00 Ortszeit.
Der Go-Scheduler löst einen Python-Endpoint aus, der die Presets lädt, die Compare-Engine
aufruft, eine HTML-E-Mail rendert und an alle `empfaenger` schickt.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go` | Hier wird der neue Cron-Job `"0 6 * * *"` registriert |
| `internal/config/config.go` | +1 Feld `HeartbeatComparePresets string` (ENV `GZ_HEARTBEAT_COMPARE_PRESETS`) |
| `internal/model/compare_preset.go` | Datenmodell: ID, LocationIDs, Schedule, Profil, HourFrom/To, Empfaenger, LetzterVersand, TopOrtLetzterVersand |
| `internal/store/store.go` | `LoadComparePresets()` / `SaveComparePresets()` — bereits vorhanden |
| `internal/handler/compare_preset.go` | `/send`-Stub ist hier — bleibt Stub (echte Logik im Scheduler) |
| `api/routers/scheduler.py` | +1 Endpoint `POST /api/scheduler/compare-presets-daily` + Hilfsfunktionen |
| `src/output/renderers/email/compare_html.py` | `render_compare_html()` — bereits vorhanden, Referenz aus #460 |
| `src/services/compare_subscription.py` | Muster: `run_comparison_for_subscription()` — analog für Presets |
| `src/services/comparison_engine.py` | `ComparisonEngine.run()` — wird direkt aufgerufen |
| `src/app/loader.py` | `load_all_locations(user_id)` — liefert SavedLocations, nach IDs filtern |
| `src/outputs/email.py` | `EmailOutput.send()` — bereits vorhanden |

## Existing Patterns

### Subscription-System (Alt-Modell, Vorbild)
Die bestehenden `CompareSubscription`-Objekte (Python-seitig in `compare_subscriptions.json`)
werden per `_run_subscriptions_by_schedule()` in `api/routers/scheduler.py` verarbeitet.
Das Muster ist:
1. Alle Subscriptions laden → nach Schedule filtern
2. `run_comparison_for_subscription(sub, all_locations)` → `(subject, html_body, text_body)`
3. `_send_subscription(sub, subject, html_body, text_body, settings)` → SMTP
4. `last_run` / `last_status` zurückschreiben (Read-Modify-Write)
5. Heartbeat nur bei `success_count > 0`

### Unterschiede ComparePreset vs. CompareSubscription

| Aspekt | CompareSubscription (alt) | ComparePreset (neu, #461) |
|--------|--------------------------|--------------------------|
| Modell | Python (`app.user.CompareSubscription`) | Go JSON (`compare_presets.json`) |
| Locations | Eingebettete Namen/IDs | Nur IDs → aus SavedLocations laden |
| Empfänger | `sub.recipients` | `preset.empfaenger` |
| Profil | `sub.activity_profile` | `preset.profil` (string, z.B. `"WINTERSPORT"`) |
| Zeitfenster | `time_window_start/end` | `hour_from` / `hour_to` |
| Status-Feld | `last_run` / `last_status` | `letzter_versand` / `top_ort_letzter_versand` |
| Enabled-Flag | `sub.enabled` | kein Flag — alle `daily`-Presets werden versendet |
| Persistenz | `compare_subscriptions.json` (Python-Format) | `compare_presets.json` (Go-Format, direkt JSON) |

### Go-Scheduler Muster (scheduler.go)
- Job wird in `New()` als `jobDef`-Eintrag registriert
- `runForAllUsers("compare_presets_daily", "/api/scheduler/compare-presets-daily")` iteriert über alle User
- `recordRun()` schreibt `lastRuns[jobID]`
- Heartbeat: `pingHeartbeat("compare_presets_daily", s.heartbeatComparePresets)` nur bei `status == "ok"`

### Heartbeat-Pflicht
- Neues Config-Feld: `HeartbeatComparePresets string` in `config.go` (ENV: `GZ_HEARTBEAT_COMPARE_PRESETS`)
- Neues Scheduler-Feld: `heartbeatComparePresets string` in `scheduler.go`
- Ping NUR wenn `ERRORS == 0` (Readiness, nicht Liveness — globale Heartbeat-Regel)

## Dependencies

- **Upstream (muss fertig sein):**
  - #458: `ComparePreset` CRUD-Backend — ✅ implementiert (store, handler, model vorhanden)
  - #460: `render_compare_html()` mit Begründungs-Tags + Header — ✅ implementiert
- **Downstream (abhängig von diesem Issue):**
  - Frontend-Anzeige des letzten Versands (kein eigenes Issue bisher)

## Existing Specs

- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Modell
- `docs/specs/modules/go_scheduler.md` — Scheduler-Patterns
- `docs/specs/modules/issue_253_compare_email.md` — HTML-Renderer

## Scope der Änderungen

### Go (gregor-api)
1. `internal/config/config.go` — +1 ENV-Feld `HeartbeatComparePresets` (~2 LoC)
2. `internal/scheduler/scheduler.go` — +1 Struct-Feld, +1 in New(), +1 jobDef-Eintrag, +1 Methode (~22 LoC)
3. `internal/scheduler/scheduler_test.go` — jobs-count von 5 auf 6 + neuer Heartbeat-Test (~40 LoC)

### Python (gregor-python)
4. `api/routers/scheduler.py` — +1 Endpoint, `_run_compare_presets_daily()`, `_save_preset_status()`, `_ping_heartbeat_compare_presets()` (~115 LoC)
5. Kein neuer Service nötig — Logik passt in den Router (analog zu `_run_subscriptions_by_schedule`)

### Tests
6. `tests/tdd/test_issue_461_compare_preset_dispatch.py`
   - `TestSavePresetStatus`: Read-Modify-Write mit tmp_path, prüft korrekte Felder + Erhalt anderer Felder
   - `TestComparePresetsFilterLogic`: nur `schedule="daily"` wird verarbeitet
   - `TestComparePresetsDailyEndpoint`: FastAPI TestClient, leere Preset-Liste → count=0
   (~120 LoC)

**Gesamtschätzung: ~300 LoC** (davon ~175 LoC Produktionscode, ~120 LoC Tests)
→ LoC-Limit-Override auf 350 nötig vor Implementierung.

## Kritische Implementation-Details (aus Analyse)

- **JSON-Format**: `compare_presets.json` ist direktes `[...]` Array — KEIN `{"subscriptions":[...]}` Wrapper (anders als compare_subscriptions.json!)
- **Profil**: `_parse_activity_profile(preset.get("profil","").lower())` — nutzt bestehende Funktion aus loader.py
- **top_ort**: `result.locations[0].location.name` (nicht `result.winner`, der errors filtert)
- **forecast_hours**: Fixer Wert 48 (ComparePreset hat kein konfigurierbares Feld)
- **Start()-Log**: von "5 jobs" auf "6 jobs" aktualisieren
- **ENV für Heartbeat in .env**: `GZ_HEARTBEAT_COMPARE_PRESETS=` (leer bis BetterStack angelegt)

## Risks & Considerations

1. **Location-Lookup:** `load_all_locations()` gibt alle User-Locations zurück. Preset hat nur IDs.
   Filter: `[loc for loc in all_locations if loc.id in set(preset.location_ids)]`
   → Fehlende IDs: warnen, weitermachen (kein Absturz)

2. **Profil-Konvertierung:** `preset["profil"]` ist ein Uppercase-Go-String (`"WINTERSPORT"`), Python-Enum hat Lowercase-Werte (`"wintersport"`). Konvertierung: `_parse_activity_profile(preset.get("profil","").lower())` aus `app.loader` — gibt `None` zurück bei unbekanntem Wert (z.B. `"ALPINE_TOURING"` → `None` → ALLGEMEIN-Fallback in Engine). NICHT `ActivityProfile(value)` direkt aufrufen (keine Exception-Sicherheit).

3. **target_date für Tagesversand:** 06:00 → Forecast für HEUTE (gleich wie DAILY_MORNING-Subscriptions)

4. **Read-Modify-Write compare_presets.json:**
   - Format ist direkt JSON-Array (kein `{"subscriptions": [...]}` Wrapper wie bei compare_subscriptions)
   - Nur `letzter_versand` und `top_ort_letzter_versand` überschreiben
   - Top-Ort = `result.locations[0].location.name` wenn `result.locations` nicht leer

5. **BetterStack Heartbeat:** Neuen Heartbeat in BetterStack anlegen, Token in `.env` eintragen.
   Periode: 86400s (täglich), Grace: 7200s (2h Toleranz).

6. **Fehlerresilienz:** Exception pro Preset gefangen — Fehler werden geloggt, nächstes Preset läuft.
   Heartbeat nur bei `error_count == 0` am Ende des gesamten Laufs.
