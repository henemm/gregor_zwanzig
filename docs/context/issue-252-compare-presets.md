# Context: Issue #252 — Compare Auto-Briefings: Preset speichern, Schedule, Sidepanel

## Request Summary

Compare-Presets (intern: `CompareSubscription`) sollen im Sidepanel des Compare-Screens verwaltet werden. Neu: `recipients`-Feld (per-Subscription E-Mail-Empfänger), `last_run`/`last_status` pro Subscription, eine `CompareSubscriptionsPanel`-Komponente und Sichtbarkeit im Scheduler-Status-Endpoint.

## Ist-Stand: Was bereits existiert

| Was | Datei | Status |
|-----|-------|--------|
| `CompareSubscription` Go-Struct | `internal/model/subscription.go` | vorhanden — **fehlt**: `Recipients`, `LastRun`, `LastStatus` |
| CRUD API Endpoints | `internal/handler/subscription.go` | vollständig (GET/POST/PUT/DELETE `/api/subscriptions`) |
| Persistenz | `internal/store/store.go` | `compare_subscriptions.json` pro User |
| Scheduler-Trigger (Python) | `api/routers/scheduler.py` | `_run_subscriptions_by_schedule()` läuft — **kein last_run-Rückschreib** |
| Compare-Engine | `internal/compare/engine.go` | fertig (Issue #250) |
| Compare-Email | aus Issue #253 | fertig — `run_comparison_for_subscription()` in Python |
| E-Mail-Versand | `api/routers/scheduler.py:_send_subscription()` | nutzt globale `Settings`-Email, **nicht** Subscription-`recipients` |
| Svelte-Dialog | `frontend/src/routes/compare/+page.svelte` L474ff | `showSaveAsSubDialog` → `SubscriptionForm` — **kein recipients-Feld** |
| Svelte `Subscription` Type | `frontend/src/lib/types.ts` L159 | **fehlt**: `recipients`, `last_run`, `last_status` |
| Subscriptions-Liste im Compare-Screen | `+page.svelte` L429ff | einfache Tabelle — kein dediziertes Panel |
| `PresetHeader` | `frontend/src/lib/components/compare/PresetHeader.svelte` | hat "Als Auto-Briefing speichern"-Button + disabled "Preset laden" |

## Lücken — was noch gebaut werden muss

### 1. Go-Modell: 3 neue Felder
```go
// internal/model/subscription.go
Recipients  []string   `json:"recipients,omitempty"`
LastRun     *time.Time `json:"last_run,omitempty"`
LastStatus  string     `json:"last_status,omitempty"` // "ok" | "error"
```
Additiv + `omitempty` → backward-compatible. Bestehende JSON-Files brechen nicht.

### 2. Validation-Update
`internal/handler/subscription.go:validateSubscription()` — neues Pflicht-Feld `recipients`: min. 1 gültige E-Mail-Adresse bei `send_email: true`.

### 3. Python: last_run/last_status rückschreiben
`api/routers/scheduler.py:_run_subscriptions_by_schedule()` — nach jedem Subscription-Run `PATCH /api/subscriptions/{id}` (oder direkt JSON-Write) mit aktuellem `last_run` + `last_status`.

Alternative: Go-Scheduler schreibt direkt (cleaner, aber aufwändiger). Empfehlung: Python-Side via bestehendem Go-API-Aufruf (HTTP PATCH).

### 4. Python: recipients nutzen
`api/routers/scheduler.py:_send_subscription()` — wenn `sub.recipients` gesetzt: E-Mail an diese Adressen senden statt an globale `settings`-Adresse.

### 5. Svelte TypeScript Interface erweitern
`frontend/src/lib/types.ts` — `Subscription` um `recipients?: string[]`, `last_run?: string`, `last_status?: string`.

### 6. SubscriptionForm: recipients-Feld
`frontend/src/lib/components/SubscriptionForm.svelte` — Empfänger-Eingabe (komma-getrennte E-Mails oder Tag-Input).

### 7. CompareSubscriptionsPanel (neu)
Neue Komponente: `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte`

Inhalt:
- Kopfzeile + "Aktuellen Vergleich speichern"-Button
- Liste: pro Preset → Name, Ort-Anzahl, Schedule-Label, Profil-Badge, Active-Dot (grün/grau)
- Letzte Ausführung: Zeitstempel + Top-Ort-Name + Status-Pill (ok=grün, error=rot)
- Leer-Zustand: "Noch keine Presets gespeichert"

Design-Referenz: Issue nennt `screen-compare.jsx::CompareSubscriptionsPanel` + `SubRow` — diese Klassen existieren nicht in der aktuellen SvelteKit-Codebase, sind nur konzeptionelle Referenz aus dem Issue.

### 8. Compare-Page: Sidepanel integrieren
`frontend/src/routes/compare/+page.svelte` — bestehende Subscriptions-Tabelle (L429ff) durch `CompareSubscriptionsPanel` ersetzen.

### 9. Scheduler Status: per-Subscription sichtbar
`internal/handler/scheduler_status.go` (oder äquivalent) — `/api/scheduler/status` soll pro aktiver Subscription einen Eintrag mit `next_run`, `last_run`, `last_status` zeigen.

**Achtung:** Aktuell zeigt der Status-Endpoint nur Job-Level (morning_subscriptions, evening_subscriptions). Per-Subscription-Status muss entweder aus dem Store gelesen oder im Go-Scheduler gecacht werden.

## Abhängigkeiten

| Upstream | Status |
|----------|--------|
| Issue #250 Compare-Engine | ✅ fertig |
| Issue #253 Compare-Email (`run_comparison_for_subscription`) | ✅ fertig |
| Issue #249 LocationsRail | ✅ fertig |
| Issue #251 Compare-Hauptbühne Frontend | ✅ fertig |

Keine Downstream-Abhängigkeiten bekannt.

## ActivityProfile-Namespace

System: `'wintersport'`, `'wandern'`, `'allgemein'`, `'summer_trekking'` (klein)  
Go-Enum: `WINTERSPORT`, `ALPINE_TOURING`, `SUMMER_TREKKING`, `ALLGEMEIN`  
Adapter `toCompareProfile()` in `frontend/src/lib/types.ts` — muss beim API-Call korrekt übergeben werden.

## Risiken

- **Datenverlust-Risiko**: `CompareSubscription`-Struct-Erweiterung ist additiv (omitempty). Bestehende JSON-Files bleiben kompatibel. ABER: UpdateSubscription-Handler macht aktuell vollständigen Replace — `LastRun`/`LastStatus` würden beim nächsten PUT überschrieben, wenn sie nicht mitgesendet werden. → Lösung: PATCH-Endpunkt für last_run/last_status (separater Handler), oder der Update-Handler merged statt replaces.
- **E-Mail-Versand**: `_send_subscription` sendet aktuell an globale `settings`-Adresse. Wenn `recipients` als Pflichtfeld eingeführt wird, bricht das für Subscriptions ohne `recipients` → Migration/Fallback nötig.
- **Scheduler-Status**: Der bestehende `Status()` in `scheduler.go` liest nur cron-Entries (next_run) + lastRuns-Map (last_run). Per-Subscription-Status muss aus dem Store kommen → erfordert Store-Zugriff im Handler.

## Verwandte Specs / Dateien

| Dokument | Relevanz |
|----------|----------|
| `docs/specs/modules/issue_250_compare_engine.md` | Compare-Engine Spec |
| `docs/specs/modules/issue_249_locations_rail.md` | LocationsRail |
| `internal/compare/types.go` | CompareRequest/CompareResult DTOs |
| `internal/scheduler/scheduler.go` | Scheduler-Architektur, recordRun, Status() |
| `cmd/server/main.go` | Route-Registrierung für neue Endpoints |
