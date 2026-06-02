# Context: Issue #511 — Weekly-Presets: Go-Scheduler missing weekly job

## Request Summary
Der Go-Scheduler kennt nur einen `compare_presets_daily`-Job (täglich 06:00),
der ausschließlich `schedule='daily'`-Presets verarbeitet. Presets mit `schedule='weekly'`
werden stillschweigend übersprungen und werden niemals versandt.

## Problem-Tiefe

**Fehlende Teile (heute):**
1. `ComparePreset`-Modell (Go + TypeScript) hat **kein `weekday`-Feld** — User kann nicht konfigurieren, welcher Wochentag gesendet wird
2. `SavePresetDialog.svelte` hat **keinen Weekday-Picker** für `schedule='weekly'`
3. `_run_compare_presets_daily` filtert hart auf `schedule='daily'` — weekly wird nie ausgeführt
4. Bestehender Test (`test_issue_461`, Zeile 215) dokumentiert das explizit als OK-Verhalten

## Related Files

| File | Relevanz |
|------|----------|
| `internal/model/compare_preset.go` | Go-Modell — kein `weekday`-Feld (muss ergänzt werden) |
| `internal/handler/compare_preset.go` | CRUD-Handler — `validateComparePreset()` (weekday-Validierung ergänzen) |
| `api/routers/scheduler.py:234` | `_run_compare_presets_daily()` — filtert nur `schedule='daily'` |
| `api/routers/scheduler.py:63` | POST `/api/scheduler/compare-presets-daily` — triggert die Python-Funktion |
| `internal/scheduler/scheduler.go:94` | Go-Cron-Job `{"0 6 * * *", s.comparePresetsDaily, ...}` |
| `internal/scheduler/scheduler.go:160` | `comparePresetsDaily()` — ruft Python-Endpoint für alle User auf |
| `frontend/src/lib/types.ts:447` | TypeScript `ComparePreset`-Interface — kein `weekday`-Feld |
| `frontend/src/lib/components/compare/SavePresetDialog.svelte` | UI — hat `schedule='weekly'` aber keinen Weekday-Picker |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:215` | Test, der weekly-Skip dokumentiert (muss angepasst werden) |

## Existing Patterns

- **Subscription** hat `weekday: int` (0=Monday..6=Sunday), Default 4 (Freitag)
  → Gleiche Konvention für ComparePreset verwenden
- `internal/model/subscription.go:14`: `Weekday int json:"weekday"`
- `internal/store/store.go:259`: Migrations-Pattern (Default 4 setzen beim Laden)
- `internal/handler/subscription.go:81`: `if sub.Weekday < 0 || sub.Weekday > 6` — Validierung

## Fix-Option (Issue-Empfehlung: Option 2 — Daily-Job erweitern)

Statt separatem wöchentlichem Cron-Job den bestehenden `compare_presets_daily` (täglich 06:00)
erweitern, sodass er zusätzlich weekly-Presets verarbeitet, wenn `today.weekday() == preset.weekday`.

**Vorteile:** Ein Endpoint, ein Job, ein Heartbeat, minimale Infrastruktur-Änderung.

## Scope-Analyse

Alle 4 Schichten müssen angepasst werden:

1. **Go-Modell** — `weekday int` ergänzen (Default 4=Freitag beim Laden alter Presets)
2. **Go-Validation** — weekday 0–6 prüfen wenn schedule='weekly'
3. **Python** — `_run_compare_presets_daily` auch weekly-Presets prüfen (today.weekday()==preset.weekday)
4. **TypeScript** — `weekday?: number` in `ComparePreset`-Interface
5. **Frontend** — Weekday-Picker in `SavePresetDialog.svelte` bei schedule='weekly'
6. **Tests** — bestehender weekly-skip-Test umschreiben; neue Tests für weekday-Matching

## Dependencies

- Upstream: `ComparePreset`-Persistenz in `data/users/{id}/compare_presets.json`
- Downstream: `comparePresetsDaily()` → Python-Endpoint → E-Mail-Versand

## Risks & Considerations

- **Bestandsdaten:** Existierende presets.json ohne `weekday`-Feld müssen einen Fallback-Wert bekommen
  (Default 4=Freitag, konsistent mit Subscription-Migration in `store.go:259`)
- **BUG-DATALOSS-GR221:** Read-Modify-Write-Pattern bei `_save_preset_status` bereits vorhanden — beibehalten
- **Kein User hat aktuell weekly-Presets** (Migration #509 erzeugt nur daily/manual) — sicher zu deployen
- **Heartbeat:** Bleibt unverändert — weekly-Versand läuft über denselben `compare_presets_daily`-Job
- **Test-Anpassung:** `test_issue_461:215` dokumentiert weekly-Skip als korrektes Verhalten → muss zu `test_weekly_preset_skipped_on_wrong_weekday` refactored werden
