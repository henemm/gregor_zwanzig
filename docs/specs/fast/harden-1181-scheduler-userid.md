# Mini-Spec: Scheduler-Trigger-Endpoints — `user_id`-Default „default" härten (#1181)

## Kontext
Vier interne Scheduler-Trigger-Endpoints in `api/routers/scheduler.py` erben einen
stillen Default `user_id: str = "default"`. Wird der Endpoint ohne `user_id` aufgerufen,
verarbeitet er kommentarlos die Daten des `default`-Nutzers — ein latentes
Cross-User-Datenleck (CLAUDE.md: „niemals auf `default` zurückfallen"). Aktuell kein
aktiver Angriffsvektor (Go-Cron übergibt immer eine echte `user_id`, Endpoints intern
auf localhost:8000, Go-Auth-Gate blockt 401). Rein defensive Härtung.

## Was ändert sich
- In `api/routers/scheduler.py` wird `user_id` bei diesen **vier** Endpoints von
  `user_id: str = "default"` zu `user_id: str = Query(...)` (Pflicht-Query-Parameter):
  - `POST /api/scheduler/trip-reports` (`trigger_trip_reports`)
  - `POST /api/scheduler/alert-checks` (`trigger_alert_checks`)
  - `POST /api/scheduler/compare-alert-checks` (`trigger_compare_alert_checks`)
  - `POST /api/scheduler/compare-presets-daily` (`trigger_compare_presets_daily`)
- Fehlt `user_id`, antwortet FastAPI mit **HTTP 422** statt still den `default`-Nutzer zu verarbeiten.
- Muster ist identisch zu bereits vorhandenem `trigger_compare_official_alert_checks`
  (`user_id: str = Query(...)`) in derselben Datei. `Query` ist bereits importiert.

## Was darf sich nicht ändern
- Alle vier Endpoints funktionieren unverändert, **wenn** `?user_id=<uid>` übergeben wird
  (Go-Scheduler `triggerEndpointForUser` tut das immer → kein realer Aufruf bricht).
- Response-Format (`{"status": ..., "count": ...}`) bleibt gleich.
- `hour`-Parameter bei `trip-reports` und `compare-presets-daily` bleibt optional (`None`).
- Nicht angefasst: `radar-alert-checks`, `compare-radar-alert-checks`,
  `compare-official-alert-checks` (bereits Pflicht) sowie die **manuellen** Endpoints
  `send-test-trip-report` / `manual-send-compare-preset` (Dev-/Test-Werkzeuge, außerhalb Scope).

## Manuelle Test-Schritte (gegen laufende Python-API, Port 8000/8001)
1. `POST /api/scheduler/alert-checks` **ohne** `user_id` → erwartet **422** (vorher: 200 mit `default`-Lauf).
2. `POST /api/scheduler/alert-checks?user_id=<echte-uid>` → erwartet **200** `{"status":"ok","count":N}`.
3. Gleiche Gegenprobe für `trip-reports`, `compare-alert-checks`, `compare-presets-daily`.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: `POST /api/scheduler/alert-checks` ohne `user_id` → 422 (Kern-Schicht, FastAPI `TestClient`).
- [ ] Test: alle vier Endpoints ohne `user_id` → 422 (parametrisiert).
- [ ] Test: `alert-checks?user_id=default` → 200 (Pflicht-Param akzeptiert übergebenen Wert weiterhin).
