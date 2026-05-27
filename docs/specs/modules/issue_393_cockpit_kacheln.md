---
entity_id: issue_393_cockpit_kacheln
type: module
created: 2026-05-27
updated: 2026-05-27
status: approved
version: "1.0"
tags: [frontend, go-api, python, cockpit, home, briefing-log, alert-log, ssr, issue-393]
---

<!-- Issue #393 — Cockpit-Kacheln: Versandstatus + Alarm-Historie nachrüsten -->

# Issue #393 — Cockpit-Kacheln: Versandstatus + Alarm-Historie

## Approval

- [x] Approved

## Zweck

Die zwei Cockpit-Kacheln auf der Startseite ("Was geht heute raus" und "Alarme · letzte 24 h") zeigen derzeit statische Platzhalter. Dieses Modul rüstet beide Kacheln mit echten Daten nach: Python schreibt nach jedem erfolgreichen Briefing-Versand bzw. Alert-Versand einen Log-Eintrag in je eine JSON-Datei pro User (`briefing_log.json` / `alert_log.json`), Go liest diese Dateien read-only in einem neuen Endpoint `GET /api/cockpit/status`, und das SvelteKit-Frontend zeigt das Ergebnis fail-soft mit `AbortSignal.timeout(3000)` an. Der PO-Constraint "kein Live-Wetter im Cockpit" bleibt strikt erhalten: es werden keine Wetter-API-Calls auf der Startseite gemacht.

## Quelle / Source

**Python — neue Funktionen:**
- `src/services/trip_report_scheduler.py` — `_append_briefing_log(user_id, trip_id, kind, channels)`
- `src/services/trip_alert.py` — `_append_alert_log(user_id, trip_id, changes_count, severity)`

**Go — neuer Handler + Store-Methoden:**
- `internal/store/store.go` — `LoadBriefingLog(userID string)` + `LoadAlertLog(userID string)`
- `internal/handler/cockpit.go` — `CockpitStatusHandler(s Store)` für `GET /api/cockpit/status`
- `cmd/server/main.go` — Route-Registrierung

**Frontend:**
- `frontend/src/lib/types.ts` — neue Interfaces `CockpitStatus`, `BriefingLogEntry`, `AlertLogEntry`
- `frontend/src/routes/+page.server.ts` — cockpit-Fetch mit `AbortSignal.timeout(3000)`
- `frontend/src/routes/_home/cockpitHelpers.ts` — `plannedBriefings(rc, sentLog?)` erweitert
- `frontend/src/routes/+page.svelte` — Alert-Kachel: echte Daten / sauberer Leerzustand

**Tests:**
- `internal/handler/cockpit_test.go` — Go-Handler Unit-Tests (tmp-Verzeichnis, echte File-Reads)
- `tests/tdd/test_briefing_log.py` — Python-Tests für `_append_briefing_log()`
- `tests/tdd/test_alert_log.py` — Python-Tests für `_append_alert_log()`

> **Schicht-Hinweis:** Python-Backend (`src/services/`) schreibt, Go-API (`internal/`) liest. Das SvelteKit-Frontend (`frontend/src/routes/`) konsumiert den Go-Endpoint. Kein Cross-Layer-Write: Python hat keinen direkten Go-API-Aufruf, Go hat keinen direkten Python-Aufruf.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_report_scheduler.py` | Python-Service | Ruft `_append_briefing_log()` nach erfolgreichem `_send_trip_report()` auf |
| `src/services/trip_alert.py` | Python-Service | Ruft `_append_alert_log()` nach erfolgreichem `check_and_send_alerts()` auf |
| `data/users/{uid}/briefing_log.json` | Persistenz-Datei | Log-Datei pro User für Briefing-Versand-Ereignisse; wird von Python geschrieben, von Go gelesen |
| `data/users/{uid}/alert_log.json` | Persistenz-Datei | Log-Datei pro User für Alert-Versand-Ereignisse; 48h-Retention, Python bereinigt beim Schreiben |
| `internal/store/store.go` | Go-Store | Stellt `LoadBriefingLog()` + `LoadAlertLog()` bereit (fail-soft bei fehlendem File) |
| `internal/handler/cockpit.go` | Go-Handler | Aggregiert Briefing- und Alert-Logs für den authenticated User, filtert auf 24h |
| `cmd/server/main.go` | Go-Einstieg | Registriert `GET /api/cockpit/status` mit dem neuen Handler |
| `frontend/src/lib/types.ts` | TypeScript | Typdefinitionen `CockpitStatus`, `BriefingLogEntry`, `AlertLogEntry` |
| `frontend/src/routes/+page.server.ts` | SvelteKit SSR | Fetcht `/api/cockpit/status` parallel zu trips/subscriptions mit 3000ms Timeout |
| `frontend/src/routes/_home/cockpitHelpers.ts` | Frontend-Helper | `plannedBriefings(rc, sentLog?)` — bisher ohne sentLog, jetzt optional mit Sent-Status |
| `frontend/src/routes/+page.svelte` | SvelteKit-Seite | Konsumiert `cockpitStatus`, rendert Alert-Kachel mit echten Daten oder Leerzustand |
| `AbortSignal.timeout()` | Node.js 18+ Built-in | Bricht SSR-Fetch nach N ms ab — kein Polyfill nötig |

## Implementation Details

### 1. Python: `_append_briefing_log()` in `trip_report_scheduler.py`

Die Funktion liest die bestehende `briefing_log.json` (falls vorhanden), hängt einen neuen Eintrag an und schreibt atomar zurück. Kein Bereinigen — das Frontend filtert auf "heute".

```python
def _append_briefing_log(user_id: str, trip_id: str, kind: str, channels: list[str]) -> None:
    path = Path(f"data/users/{user_id}/briefing_log.json")
    data = json.loads(path.read_text()) if path.exists() else {"entries": []}
    data["entries"].append({
        "trip_id": trip_id,
        "kind": kind,                             # "morning" | "evening"
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "channels": channels
    })
    path.write_text(json.dumps(data, indent=2))
```

Aufruf in `_send_trip_report()` nach `logger.info("Report sent …")`, d.h. nur wenn kein Exception geworfen wurde.

### 2. Python: `_append_alert_log()` in `trip_alert.py`

Analog zu Briefing-Log, aber mit 48h-Retention: beim Schreiben werden Einträge älter als 48 Stunden entfernt.

```python
def _append_alert_log(user_id: str, trip_id: str, changes_count: int, severity: str) -> None:
    path = Path(f"data/users/{user_id}/alert_log.json")
    data = json.loads(path.read_text()) if path.exists() else {"entries": []}
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=48)
    data["entries"] = [
        e for e in data["entries"]
        if datetime.fromisoformat(e["sent_at"]) > cutoff
    ]
    data["entries"].append({
        "trip_id": trip_id,
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "changes_count": changes_count,
        "severity": severity                      # "LOW" | "MODERATE" | "HIGH"
    })
    path.write_text(json.dumps(data, indent=2))
```

Aufruf in `check_and_send_alerts()` nach erfolgreichem Versand.

### 3. Go: `LoadBriefingLog()` + `LoadAlertLog()` in `store.go`

Beide Methoden lesen die JSON-Datei des jeweiligen Users und deserialisieren in Go-Structs. Bei fehlendem File (noch kein Briefing / kein Alert): leeres Struct zurückgeben, kein Error.

```go
type BriefingLogEntry struct {
    TripID   string   `json:"trip_id"`
    Kind     string   `json:"kind"`
    SentAt   string   `json:"sent_at"`
    Channels []string `json:"channels"`
}

type BriefingLog struct {
    Entries []BriefingLogEntry `json:"entries"`
}

func (s *Store) LoadBriefingLog(userID string) (BriefingLog, error) {
    path := filepath.Join(s.dataDir, "users", userID, "briefing_log.json")
    if _, err := os.Stat(path); os.IsNotExist(err) {
        return BriefingLog{}, nil   // fail-soft
    }
    // … json.Unmarshal …
}
```

`LoadAlertLog()` analog mit `AlertLog` + `AlertLogEntry` (trip_id, sent_at, changes_count, severity).

### 4. Go: `CockpitStatusHandler` in `internal/handler/cockpit.go`

Handler liest User-ID aus dem JWT-Context (identisches Muster wie bestehende Handler), lädt beide Logs, filtert auf 24h (für Briefings: filtert auf "heute" Ortszeit UTC), gibt JSON zurück.

```go
func CockpitStatusHandler(s store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        userID := auth.UserIDFromContext(r.Context())
        briefingLog, _ := s.LoadBriefingLog(userID)   // Fehler → leeres Log
        alertLog, _ := s.LoadAlertLog(userID)

        cutoff24h := time.Now().UTC().Add(-24 * time.Hour)
        todayDate := time.Now().UTC().Format("2006-01-02")

        // Briefings: nur heutige Einträge (sent_at beginnt mit todayDate)
        var briefings []BriefingLogEntry
        for _, e := range briefingLog.Entries {
            if strings.HasPrefix(e.SentAt, todayDate) {
                briefings = append(briefings, e)
            }
        }

        // Alerts: nur Einträge der letzten 24h
        var alerts []AlertLogEntry
        for _, e := range alertLog.Entries {
            t, err := time.Parse(time.RFC3339, e.SentAt)
            if err == nil && t.After(cutoff24h) {
                alerts = append(alerts, e)
            }
        }

        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]any{
            "briefings": briefings,
            "alerts":    alerts,
        })
    }
}
```

### 5. Go: Route-Registrierung in `cmd/server/main.go`

```go
r.Get("/api/cockpit/status", handler.CockpitStatusHandler(store))
```

Hinter dem bestehenden JWT-Middleware-Block, analog zu anderen `/api/`-Routen.

### 6. TypeScript-Typen in `frontend/src/lib/types.ts`

```ts
export interface BriefingLogEntry {
    trip_id: string;
    kind: 'morning' | 'evening';
    sent_at: string;      // ISO 8601
    channels: string[];
}

export interface AlertLogEntry {
    trip_id: string;
    sent_at: string;      // ISO 8601
    changes_count: number;
    severity: 'LOW' | 'MODERATE' | 'HIGH';
}

export interface CockpitStatus {
    briefings: BriefingLogEntry[];
    alerts: AlertLogEntry[];
}
```

### 7. SSR-Fetch in `+page.server.ts`

Parallel zu den bestehenden trips/subscriptions-Fetches, fail-soft mit `null`:

```ts
const cockpitRes = await fetch(`${API()}/api/cockpit/status`, {
    headers,
    signal: AbortSignal.timeout(3000)
}).catch(() => null);

const cockpitStatus: CockpitStatus | null = cockpitRes?.ok
    ? await cockpitRes.json().catch(() => null)
    : null;

return { trips, subscriptions, cockpitStatus };
```

Kein Wetter-Endpoint wird aufgerufen — PO-Constraint ist erfüllt.

### 8. `cockpitHelpers.ts` — `plannedBriefings()` erweitern

Die bestehende Funktion berechnet geplante Briefings aus `report_config`. Sie erhält einen optionalen zweiten Parameter `sentLog?: BriefingLogEntry[]`. Für jeden geplanten Briefing-Eintrag prüft sie, ob ein passender `sent`-Eintrag im Log existiert (gleicher `trip_id` + `kind` + heutiges Datum).

```ts
export function plannedBriefings(
    rc: ReportConfig,
    sentLog?: BriefingLogEntry[]
): Array<{ kind: string; label: string; status: 'sent' | 'planned' }> {
    const todayPrefix = new Date().toISOString().slice(0, 10);
    return [...].map(entry => ({
        ...entry,
        status: sentLog?.some(
            s => s.kind === entry.kind &&
                 s.trip_id === rc.trip_id &&
                 s.sent_at.startsWith(todayPrefix)
        ) ? 'sent' : 'planned'
    }));
}
```

### 9. `+page.svelte` — Alert-Kachel

```svelte
{#if cockpitStatus?.alerts?.length}
    {#each cockpitStatus.alerts as alert}
        <AlertRow {alert} />
    {/each}
{:else}
    <p class="empty-state">Keine Alarme in den letzten 24 Stunden</p>
{/if}
```

Die "Was geht raus"-Kachel erhält `cockpitStatus?.briefings` als `sentLog`-Argument an `plannedBriefings()`.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/services/trip_report_scheduler.py` | ~25 | ja |
| `src/services/trip_alert.py` | ~25 | ja |
| `internal/store/store.go` | ~60 | ja |
| `internal/handler/cockpit.go` | ~70 | ja |
| `cmd/server/main.go` | ~2 | ja |
| `frontend/src/lib/types.ts` | ~20 | ja |
| `frontend/src/routes/+page.server.ts` | ~10 | ja |
| `frontend/src/routes/_home/cockpitHelpers.ts` | ~20 | ja |
| `frontend/src/routes/+page.svelte` | ~15 | ja |
| `internal/handler/cockpit_test.go` | ~80 | ja |
| `tests/tdd/test_briefing_log.py` | ~40 | ja |
| `tests/tdd/test_alert_log.py` | ~40 | ja |
| **Gesamt (zählend)** | **~407** | **→ loc_limit_override 500** |

## Expected Behavior

- **Input:** Erfolgreicher Briefing- oder Alert-Versand durch Python-Services; `GET /api/cockpit/status` vom authentifizierten User; Startseiten-Load
- **Output:**
  - `briefing_log.json` / `alert_log.json` werden nach jedem erfolgreichen Versand aktualisiert
  - `GET /api/cockpit/status` gibt `{ briefings: [...], alerts: [...] }` zurück — leere Arrays wenn keine Logs vorhanden
  - "Was geht raus"-Kachel zeigt grünen Dot + "gesendet" für versendete Briefings, grauen Dot + "geplant" für ausstehende
  - "Alarme · letzte 24 h"-Kachel zeigt echte Alert-Zeilen oder sauberen Leerzustand
- **Side effects:**
  - `alert_log.json`: Python bereinigt beim Schreiben Einträge älter als 48h
  - Bei Timeout (>3000ms) oder Fehler des cockpit-Endpoints: `cockpitStatus = null`, beide Kacheln fallen auf Leerzustand zurück — Seite lädt trotzdem
  - Kein Einfluss auf bestehende trips/subscriptions-Fetches

## Acceptance Criteria

- **AC-1:** Given Python Scheduler versendet erfolgreich ein Morning-Briefing für Trip T / When `_send_trip_report()` erfolgreich abschließt / Then wird ein Eintrag `{ trip_id: T, kind: 'morning', sent_at: <ISO-UTC>, channels: [...] }` in `data/users/{uid}/briefing_log.json` angehängt
  - Test: (populated after /tdd-red)

- **AC-2:** Given Python Alert-Service sendet erfolgreich einen Alert für Trip T / When `check_and_send_alerts()` erfolgreich abschließt / Then wird ein Eintrag `{ trip_id: T, sent_at: <ISO-UTC>, changes_count: N, severity: S }` in `data/users/{uid}/alert_log.json` angehängt
  - Test: (populated after /tdd-red)

- **AC-3:** Given `GET /api/cockpit/status` wird aufgerufen / When `briefing_log.json` nicht existiert / Then gibt der Endpoint `{ briefings: [], alerts: [] }` zurück (kein 500-Error)
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Hero-Tour hat heute Morgen ein Briefing versendet (Eintrag in `briefing_log.json` mit `kind='morning'` und `sent_at` = heute) / When die Startseite lädt / Then zeigt die "Was geht raus"-Kachel den Morgen-Row mit grünem Dot und Text "gesendet"
  - Test: (populated after /tdd-red)

- **AC-5:** Given kein Briefing wurde heute versendet (Log-File leer oder kein heutiger Eintrag) / When die Startseite lädt / Then zeigt die "Was geht raus"-Kachel alle konfigurierten Briefings mit grauem Dot und Text "geplant"
  - Test: (populated after /tdd-red)

- **AC-6:** Given mindestens ein Alert-Event in `alert_log.json` in den letzten 24 h für die Hero-Tour / When die Startseite lädt / Then zeigt die "Alarme · letzte 24 h"-Kachel die Event-Zeilen statt des Leer-Zustands
  - Test: (populated after /tdd-red)

- **AC-7:** Given kein Alert-Event in den letzten 24 h für die Hero-Tour / When die Startseite lädt / Then zeigt die "Alarme · letzte 24 h"-Kachel den sauberen Leer-Zustand (Text: "Keine Alarme in den letzten 24 Stunden")
  - Test: (populated after /tdd-red)

- **AC-8:** Given der `/api/cockpit/status`-Endpoint antwortet langsam oder gar nicht / When der SSR-Loader nach 3000ms kein Response erhält / Then wird `cockpitStatus: null` zurückgegeben, Seite lädt trotzdem (sauberer Leer-Zustand in beiden Kacheln)
  - Test: (populated after /tdd-red)

- **AC-9:** Given Python schreibt `alert_log.json` / When Einträge älter als 48 Stunden existieren / Then werden diese beim nächsten Write-Vorgang bereinigt (Retention-Policy)
  - Test: (populated after /tdd-red)

- **AC-10:** Given die Startseite lädt / When der SSR-Loader in `+page.server.ts` ausgeführt wird / Then darf kein Wetter-Endpoint aufgerufen werden (kein Call an `/api/trips/.../stages/weather` oder Open-Meteo)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Concurrent-Write-Schutz zwischen Python-Prozessen:** Bei gleichzeitigem Morgen- und Abend-Briefing (theoretisch möglich bei langer Laufzeit) könnte ein Schreibvorgang den anderen überschreiben. Da Python-Briefings serialisiert im Scheduler laufen und die Logs klein sind, ist das Risiko praktisch null; bei Bedarf kann `filelock` ergänzt werden.
- **Timezone-Filterung für "heute":** Der Go-Handler filtert Briefings auf UTC-Datum. Ein User in UTC+2 der um 23:30 Ortszeit ein Briefing erhält, sieht es am nächsten UTC-Tag nicht mehr in "Was geht heute raus". Für die aktuelle Zielgruppe (GR20-Wanderer in CEST) ist dieser Rand-Case akzeptabel.
- **alert_log.json nicht bereinigt bei Go-Reads:** Go liest die gesamte Datei ohne Filtering der Retention. Das Bereinigen obliegt Python beim nächsten Schreib-Vorgang. Bei langer Pause ohne Alerts kann die Datei veraltete Einträge enthalten — der Go-Handler filtert diese korrekt auf 24h heraus.

## Out of Scope

- Persistenz der Logs in der Go-Datenbank (SQLite) — JSON-Files analog `alert_throttle.json` sind für diesen Use Case ausreichend
- Pagination oder Archiv der Briefing-History über mehrere Tage
- Retry-Logik im SSR-Loader bei cockpit-Fetch-Fehler
- Push-Notifications oder Echtzeit-Updates der Cockpit-Kacheln
- Anpassung bestehender Alert-Kachel-UI-Komponenten (nur Daten-Anbindung, keine Redesigns)

## Changelog

- 2026-05-27: Initial spec erstellt. Python schreibt `briefing_log.json` + `alert_log.json` nach erfolgreichen Versand-Events; Go liest via neuem `GET /api/cockpit/status`-Endpoint; SvelteKit-Frontend bindet beide Kacheln mit fail-soft `AbortSignal.timeout(3000)` an. PO-Constraint "kein Live-Wetter im Cockpit" bleibt erhalten. loc_limit_override auf 500 gesetzt (~407 LoC geschätzt).
