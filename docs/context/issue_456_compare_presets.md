# Context: Issue #456 — Compare Auto-Briefings (Preset speichern, Schedule, Versand-Trigger)

## Request Summary
Nutzer soll einen laufenden Orts-Vergleich als Preset speichern und einen manuellen Versand-Trigger ausführen können. Das Sidepanel zeigt gespeicherte Presets mit letztem Versand-Zeitstempel und Top-Ort.

## Terminologie-Mapping

Issue #456 spricht von "ComparePreset" — das entspricht intern dem bestehenden `CompareSubscription`. Keine neue Entität nötig, nur Erweiterung.

## Was bereits existiert

| Komponente | Datei | Relevanz |
|-----------|-------|----------|
| Go-Modell | `internal/model/subscription.go` | `CompareSubscription` mit `ID`, `Name`, `Locations`, `Schedule`, `LastRun`, `LastStatus` |
| Go-CRUD | `internal/handler/subscription.go` | GET/POST/PUT/DELETE/PATCH `/api/subscriptions` |
| Go-Router | `cmd/server/main.go` | Alle Subscription-Routen registriert |
| Go-Store | `internal/store/store.go` | `LoadSubscriptions`, `SaveSubscription`, `DeleteSubscription` |
| Python-Modell | `src/app/user.py:116` | `CompareSubscription` dataclass |
| Python-Service | `src/services/compare_subscription.py` | `run_comparison_for_subscription()` |
| Python-Scheduler | `api/routers/scheduler.py` | `trigger_morning`, `trigger_evening`, `_run_subscriptions_by_schedule`, `_save_subscription` |
| Frontend-Type | `frontend/src/lib/types.ts` | `Subscription` interface mit `last_run`, `last_status` |
| Sidepanel | `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | Zeigt Subscription-Liste + AddReportCard |
| Card | `frontend/src/lib/components/compare/AutoReportCard.svelte` | Zeigt Name, Schedule, Locations, last_run |
| Hauptseite | `frontend/src/routes/compare/+page.svelte` | 3-Spalten-Layout, `handleSaveBriefing` → `/compare/new` |
| Scheduler-Cron | `internal/scheduler/scheduler.go:93` | `"0 7 * * *"` morning @ 07:00 Ortszeit |

## Was NEU ist für #456

| Feature | Fehlt wo |
|---------|---------|
| `top_ort_letzter_versand` Feld | Go-Modell + Python-Modell + Frontend-Type |
| `top_ort_letzter_versand` befüllen nach Lauf | `api/routers/scheduler.py::_save_subscription` |
| `top_ort_letzter_versand` im Sidepanel zeigen | `AutoReportCard.svelte` |
| Manueller Versand-Trigger `POST /api/subscriptions/{id}/send` | Go-Handler (neu) + Python-Endpoint (neu) + Route |
| Pre-fill Wizard mit aktuellem Compare-State | `frontend/src/routes/compare/+page.svelte::handleSaveBriefing` |

## API-Naming-Entscheidung

Issue nennt `/api/compare/presets` — empfohlen ist die **bestehende Benennung `/api/subscriptions`** zu behalten (konsistent mit Wizard, Editor, Scheduler) und nur den neuen Send-Endpoint hinzuzufügen:

```
POST /api/subscriptions/{id}/send   ← NEU
```

Kein Alias-Routing, keine Duplizierung.

## Abhängigkeiten

- Upstream: `internal/store/store.go` (Store), `src/services/compare_subscription.py` (Run-Logik)
- Downstream: `AutoReportCard.svelte`, `AutoReportsOverview.svelte`, Scheduler-Cron

## Existierende Patterns

- Read-Modify-Write in Go: `PatchSubscriptionRunStatusHandler` (liest, ändert nur bestimmte Felder, speichert) — gleicher Ansatz für Send-Handler
- Python-Save: `_save_subscription` in `scheduler.py` — liest JSON, patched `last_run`/`last_status` → hier `top_ort_letzter_versand` ergänzen
- Go→Python-Proxy: `handler.ProxyPostHandler` für einfache Trigger-Endpoints

## Risks & Considerations

- `top_ort_letzter_versand` ist optional (`omitempty`) — Bestandsdaten bleiben kompatibel
- Manual-Send-Handler muss Auth (User-ID) respektieren — wie alle anderen Subscription-Handler via `middleware.UserIDFromContext`
- Python-Endpoint für manuellen Versand: muss `user_id` als Query-Param entgegennehmen (wie bestehende Trigger-Endpoints) UND `subscription_id`
- `handleSaveBriefing` im Frontend: Wizard mit aktuellen Werten vorab befüllen ist optional für AC-1 (Wizard ist leer, Nutzer gibt Name ein) — die Simple-Version (`goto('/compare/new')`) erfüllt AC-1 bereits
