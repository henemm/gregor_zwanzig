---
entity_id: issue_252_compare_presets
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
issue: 252
tags: [compare, subscriptions, scheduler, frontend, svelte, python, go, email, recipients]
---

# Issue #252 — Compare Presets: recipients, last_run/last_status, CompareSubscriptionsPanel

## Approval

- [ ] Approved

## Purpose

Erweitert das bestehende `CompareSubscription`-System um drei neue Felder (`recipients`, `last_run`, `last_status`) und eine neue Frontend-Komponente `CompareSubscriptionsPanel`, die den aktuellen Laufstatus jedes Presets im Compare-Screen anzeigt. Die Erweiterung schließt den Auto-Briefings-Regelkreis: Scheduler schreibt nach jedem Lauf Laufzeit und Status zurück in die Subscription-JSON, das Frontend liest diese Felder und zeigt sie im Sidepanel an — ohne bestehende Datenstrukturen oder API-Contracts zu brechen.

## Source

- **EDIT:** `internal/model/subscription.go` — `CompareSubscription`-Struct um 3 Felder erweitern
- **EDIT:** `internal/handler/subscription.go` — Validierung + neuer `PatchSubscriptionRunStatusHandler`
- **EDIT:** `cmd/server/main.go` — Route `PATCH /api/subscriptions/{id}/run-status` registrieren
- **EDIT:** `internal/middleware/auth.go` — PATCH-Route zur Auth-Whitelist hinzufügen
- **EDIT:** `internal/scheduler/scheduler.go` — `Status()`-Response um per-Subscription last_run/last_status erweitern
- **EDIT:** `src/app/user.py` — `CompareSubscription`-Dataclass um 3 Felder erweitern
- **EDIT:** `src/app/loader.py` — `load_compare_subscriptions()` liest 3 neue Felder
- **EDIT:** `src/outputs/email.py` — `EmailOutput.send()` erhält optionalen `to`-Parameter
- **EDIT:** `api/routers/scheduler.py` — Scheduler schreibt `last_run`/`last_status` nach Lauf direkt in JSON; `_send_subscription()` nutzt `sub.recipients`
- **EDIT:** `frontend/src/lib/types.ts` — `Subscription`-Interface um `recipients?`, `last_run?`, `last_status?` erweitern
- **EDIT:** `frontend/src/lib/components/SubscriptionForm.svelte` — `recipients`-Eingabefeld + Validierung
- **NEU:** `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` — Preset-Liste mit Active-Dot, LastRun-Zeitstempel, Status-Pill
- **EDIT:** `frontend/src/routes/compare/+page.svelte` — bestehende Subscriptions-Tabelle durch `CompareSubscriptionsPanel` ersetzen

> **Schicht-Zuordnung:** Go-API (`internal/`), Python-Backend (`src/app/`, `src/outputs/`, `api/routers/`), SvelteKit-Frontend (`frontend/src/`). Python schreibt `last_run`/`last_status` direkt in JSON (kein HTTP-PATCH), weil der Go-API-Endpoint Cookie-Auth erfordert, die der Scheduler nicht besitzt. Der PATCH-Endpoint ist additiv für zukünftige Go-native Nutzung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareSubscription` (`internal/model/subscription.go`) | intern | Basis-Struct; wird additiv um `Recipients []string`, `LastRun *time.Time`, `LastStatus string` erweitert |
| `store.LoadSubscriptions` / `store.SaveSubscription` (`internal/store/store.go`) | intern | Lesen/Schreiben der Subscription-JSON; SaveSubscription muss die neuen Felder mit `omitempty` persistieren |
| `run_comparison_for_subscription()` (`api/routers/scheduler.py`) | intern | Bestehende Python-Funktion, die die Compare-Engine aufruft und das Mail-Ergebnis aufbaut; Issue #253 |
| `EmailOutput.send()` (`src/outputs/email.py`) | intern | Versendet die Compare-Mail; erhält neuen optionalen `to`-Parameter für per-Subscription-Empfänger |
| `load_compare_subscriptions()` (`src/app/loader.py`) | intern | Deserialize der Subscription-JSONs; muss 3 neue Felder einlesen |
| `POST /api/compare/run` (`internal/handler/compare_run.go`) | intern | Compare-Engine-Endpoint; Issue #250, bereits implementiert |
| `CompareSubscriptionsPanel`-Pattern (`frontend/src/lib/components/compare/`) | intern | Sidepanel-Muster aus Issue #249 (LocationsRail) als UI-Referenz |
| Auth-Middleware / `WithUser()` (`internal/middleware/auth.go`) | intern | Cookie-Auth-Whitelist muss PATCH-Route ausnehmen, damit Scheduler-seitige Go-Komponenten künftig diesen Endpoint nutzen können |
| `Subscription`-Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typen; Erweiterung um optionale Felder ist backward-compatible |

## Implementation Details

### §1 `internal/model/subscription.go` — 3 neue Felder

```go
type CompareSubscription struct {
    // ... bestehende Felder unverändert ...
    Recipients []string   `json:"recipients,omitempty"`  // per-Subscription Empfänger; leer → settings.mail_to
    LastRun    *time.Time `json:"last_run,omitempty"`    // Zeitpunkt des letzten Scheduler-Laufs
    LastStatus string     `json:"last_status,omitempty"` // "ok" | "error" | leer wenn noch nie gelaufen
}
```

Alle drei Felder mit `omitempty` — bestehende JSONs ohne diese Felder bleiben valide und werden fehlerfrei deserialisiert (Null-Werte).

### §2 `internal/handler/subscription.go` — Validierung + neuer Handler

**Erweiterte Validierung bei Create/Update:**
- Wenn `send_email: true` und `recipients` nicht leer: jede Adresse muss `strings.Contains("@")` erfüllen; sonst HTTP 400.
- Wenn `send_email: true` und `recipients` leer: kein Fehler — Default-Empfänger aus Settings wird zur Laufzeit im Python-Scheduler angewendet.

**Neuer Handler `PatchSubscriptionRunStatusHandler`:**

```go
// PATCH /api/subscriptions/{id}/run-status
// Body: { "last_run": "2026-05-20T14:00:00Z", "last_status": "ok" }
// Liest existierende Subscription, überschreibt nur LastRun + LastStatus (Read-Modify-Write).
// Antwortet 200 mit aktualisiertem Subscription-JSON.
```

Read-Modify-Write-Pflicht: `store.LoadSubscription()` → Felder setzen → `store.SaveSubscription()`. Kein Überschreiben anderer Felder.

### §3 `cmd/server/main.go` — Route registrieren

```go
r.Patch("/api/subscriptions/{id}/run-status", handler.PatchSubscriptionRunStatusHandler(store))
```

Einzige Änderung in dieser Datei.

### §4 `internal/middleware/auth.go` — Auth-Whitelist

PATCH-Route `/api/subscriptions/{id}/run-status` zur bestehenden Auth-Whitelist hinzufügen (Muster identisch zu `/api/health`). Ermöglicht zukünftig lokalen Go-Scheduler-Aufruf ohne Cookie.

### §5 `internal/scheduler/scheduler.go` — Status()-Erweiterung

`GET /api/scheduler/status`-Response erhält ein neues optionales Feld `compare_subscriptions`:

```json
{
  "jobs": { ... },
  "compare_subscriptions": [
    {
      "id": "sub-abc",
      "name": "Zillertal vs. Stubai",
      "enabled": true,
      "last_run": "2026-05-20T06:00:00Z",
      "last_status": "ok"
    }
  ]
}
```

Implementierung: `store.LoadSubscriptions(userID)` aufrufen, über die Liste iterieren, nur `id`, `name`, `enabled`, `last_run`, `last_status` in die Response mappen. Kein Fehler wenn Store leer ist — leeres Array zurückgeben.

### §6 `src/app/user.py` — CompareSubscription Dataclass

```python
@dataclass
class CompareSubscription:
    # ... bestehende Felder ...
    recipients: list[str] = field(default_factory=list)
    last_run: str | None = None    # ISO-8601-String; None wenn noch nie gelaufen
    last_status: str | None = None  # "ok" | "error" | None
```

### §7 `src/app/loader.py` — load_compare_subscriptions()

Bei Deserialisierung die drei neuen Felder mit `.get("recipients", [])`, `.get("last_run")`, `.get("last_status")` einlesen. Keine Migration nötig — fehlende Felder ergeben Default-Werte.

### §8 `src/outputs/email.py` — EmailOutput.send()

```python
def send(self, subject: str, body: str, to: list[str] | None = None) -> None:
    recipients = to if to else [self.settings.mail_to]
    # bestehender SMTP-Send-Pfad mit `recipients`
```

Bestehende Aufrufe ohne `to`-Parameter bleiben unverändert — `settings.mail_to` als Default.

### §9 `api/routers/scheduler.py` — Status-Rückschreiben nach Lauf

Nach jedem `_run_subscription()` Aufruf:

```python
sub.last_run = datetime.utcnow().isoformat() + "Z"
sub.last_status = "ok"  # oder "error" bei Exception
_save_subscription(user_id, sub)  # schreibt direkt in data/users/{user_id}/compare_subscriptions.json
```

`_save_subscription()`: Lädt die JSON-Datei, findet den Eintrag via `id`, überschreibt `last_run` + `last_status`, schreibt zurück (Read-Modify-Write). Kein HTTP-Call an Go-API.

`_send_subscription()`: Wenn `sub.recipients` nicht leer, `email_output.send(..., to=sub.recipients)` aufrufen. Sonst `email_output.send(...)` ohne `to` (Default greift).

### §10 `frontend/src/lib/types.ts` — Interface-Erweiterung

```typescript
interface Subscription {
  // ... bestehende Felder ...
  recipients?: string[];
  last_run?: string;    // ISO-8601
  last_status?: string; // "ok" | "error" | undefined
}
```

### §11 `frontend/src/lib/components/SubscriptionForm.svelte` — recipients-Feld

Neues Textfeld "Empfänger (E-Mail)" unterhalb von `send_email`-Toggle. Komma-getrennte Eingabe; clientseitige Validierung: jedes Token muss `@` enthalten. Leer lassen = Default-Empfänger aus Server-Settings. Fehlertext nur bei ungültiger E-Mail-Adresse, nicht bei leerem Feld.

### §12 `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` — NEUE Komponente

Layout (pro Preset-Zeile):
- **Active-Dot:** Grün wenn `enabled: true`, Grau wenn `enabled: false`
- **Name:** Subscription-Name (fett)
- **Schedule-Info:** z.B. "täglich 06:00" (aus `schedule`-Feld)
- **LastRun:** ISO-Timestamp → `"Zuletzt: 20.05.2026, 06:00"` (lokale Zeitformatierung via `Intl.DateTimeFormat`); leer wenn `last_run` undefined
- **Status-Pill:** Grüne Pill "ok" wenn `last_status === "ok"`, rote Pill "Fehler" wenn `"error"`, kein Pill wenn undefined
- **Edit-Button:** Öffnet bestehenden Subscription-Bearbeitungs-Flow

Props: `subscriptions: Subscription[]`. Lädt keine eigenen Daten — Daten kommen von `+page.svelte`.

### §13 `frontend/src/routes/compare/+page.svelte` — Panel-Einbau

Bestehende Subscriptions-Tabelle (`<SubscriptionsTable>` oder äquivalentes Element) durch `<CompareSubscriptionsPanel subscriptions={$subscriptions} />` ersetzen. `$subscriptions`-Store bleibt wie bisher befüllt — nur die Darstellungskomponente wechselt.

### §14 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|---------|-----|
| `internal/model/subscription.go` | +3 Felder | ~8 |
| `internal/handler/subscription.go` | Validierung + neuer Handler | ~40 |
| `cmd/server/main.go` | +1 Route | ~2 |
| `internal/middleware/auth.go` | +1 Whitelist-Eintrag | ~3 |
| `internal/scheduler/scheduler.go` | Status()-Erweiterung | ~25 |
| `src/app/user.py` | +3 Felder | ~6 |
| `src/app/loader.py` | +3 .get()-Calls | ~6 |
| `src/outputs/email.py` | optionaler `to`-Parameter | ~8 |
| `api/routers/scheduler.py` | Status-Rückschreiben + recipients | ~30 |
| `frontend/src/lib/types.ts` | +3 optionale Felder | ~5 |
| `frontend/src/lib/components/SubscriptionForm.svelte` | recipients-Eingabe + Validierung | ~25 |
| `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` | NEUE Komponente | ~80 |
| `frontend/src/routes/compare/+page.svelte` | Panel-Austausch | ~5 |
| **Summe** | | **~243 LoC** |

LoC-Limit-Override auf 250 setzen vor Implementierungsstart: `workflow.py set-field loc_limit_override 250`

## Expected Behavior

- **Input:** Bestehende `CompareSubscription`-JSONs ohne neue Felder (Null-Default), neue Subscriptions mit optionalem `recipients`-Array, Scheduler-Laufkontext.
- **Output:**
  - Scheduler sendet Compare-Mail an `sub.recipients` wenn befüllt, sonst an `settings.mail_to`.
  - Nach jedem Scheduler-Lauf enthält die Subscription-JSON `last_run` (ISO-8601) und `last_status` (`"ok"` / `"error"`).
  - `GET /api/scheduler/status` enthält ein `compare_subscriptions`-Array mit `last_run`/`last_status` pro aktivem Preset.
  - `CompareSubscriptionsPanel` zeigt Active-Dot, LastRun-Zeitstempel und Status-Pill pro Preset.
- **Side effects:**
  - Direktes Schreiben in `data/users/{user_id}/compare_subscriptions.json` durch Python-Scheduler (kein HTTP-Call).
  - Bestehende Subscriptions ohne `recipients`-Feld werden unverändert weiter mit `settings.mail_to` bedient.
  - Bestehende `CompareSubscription`-JSONs ohne neue Felder bleiben fehlerfrei ladbar — keine Migration erforderlich.
  - Kein bestehender API-Endpoint wird entfernt oder breaking-geändert.

## Acceptance Criteria

**AC-1:** Given ein gespeicherter aktiver Preset (`enabled: true`) mit `schedule: "daily_morning"` / When der Scheduler feuert / Then wird `run_comparison_for_subscription()` aufgerufen, eine Mail an `sub.recipients` (falls gesetzt) bzw. `settings.mail_to` versendet, und `last_run` + `last_status: "ok"` werden in die Subscription-JSON zurückgeschrieben.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein Preset mit `enabled: false` / When der Scheduler `_run_subscriptions_by_schedule()` aufruft / Then wird dieser Preset ohne Mail-Versand und ohne Status-Aktualisierung übersprungen.
  - Test: (populated after /tdd-red)

**AC-3:** Given der letzte Versand war erfolgreich (`last_status: "ok"`, `last_run` gesetzt) / When `CompareSubscriptionsPanel` die Subscription-Liste rendert / Then zeigt die Preset-Zeile den formatierten `last_run`-Zeitstempel und eine grüne Status-Pill mit Text "ok".
  - Test: (populated after /tdd-red)

**AC-4:** Given `GET /api/scheduler/status` wird aufgerufen / Then enthält die Response ein `compare_subscriptions`-Array, in dem jeder aktive Preset mit `id`, `name`, `last_run` und `last_status` aufgeführt ist; Presets ohne bisherigen Lauf haben `last_run: null` und fehlendes `last_status`.
  - Test: (populated after /tdd-red)

**AC-5:** Given ein Preset mit `recipients: ["a@example.com"]` / When der Scheduler feuert / Then wird `EmailOutput.send()` mit `to=["a@example.com"]` aufgerufen und die Mail geht an diese Adresse, nicht an `settings.mail_to`.
  - Test: (populated after /tdd-red)

**AC-6:** Given eine bestehende Subscription-JSON ohne `recipients`-, `last_run`- und `last_status`-Felder / When `load_compare_subscriptions()` diese Datei einliest / Then werden alle drei Felder mit ihren Default-Werten (`[]`, `None`, `None`) befüllt ohne Fehler oder Exception.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein HTTP-PATCH durch Python-Scheduler:** Python schreibt `last_run`/`last_status` direkt in die JSON-Datei, weil der Go-API-Endpoint Cookie-Auth erfordert. Der `PATCH /api/subscriptions/{id}/run-status`-Endpoint ist für zukünftige Go-native Nutzung vorgesehen, wird in diesem Issue aber noch nicht durch den Scheduler aufgerufen.
- **Kein Retry-Mechanismus:** Wenn `_send_subscription()` fehlschlägt (z.B. SMTP-Fehler), wird `last_status: "error"` gesetzt, aber kein Retry eingeplant. Der nächste reguläre Scheduler-Lauf überschreibt den Status.
- **recipients-Validierung nur clientseitig im Frontend:** Der Go-Handler validiert E-Mail-Adressen nur auf `@`-Enthaltensein, keine vollständige RFC-5322-Validierung. Ungültige Adressen führen zu SMTP-Fehlern zur Laufzeit.
- **Status nur "ok"/"error":** Kein Differenzieren zwischen "Compare-Engine-Fehler" und "Mail-Versand-Fehler" in `last_status`. Beide Fehlerfälle landen als `"error"`.
- **In-Memory-Status im Go-Scheduler:** Die `Status()`-Funktion liest Subscriptions aus dem Dateisystem bei jedem Aufruf — kein In-Memory-Caching. Bei sehr vielen Subscriptions (>100) könnte das zu Latenz führen; im aktuellen Nutzungsrahmen unkritisch.

## Changelog

- 2026-05-20: Initial spec — Issue #252. CompareSubscription +3 Felder (recipients, last_run, last_status), PatchSubscriptionRunStatusHandler, CompareSubscriptionsPanel, Python-Scheduler schreibt Status direkt in JSON. ~243 LoC, LoC-Override auf 250 erforderlich.
