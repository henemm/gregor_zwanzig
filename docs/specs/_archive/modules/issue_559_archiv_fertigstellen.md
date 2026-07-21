---
entity_id: issue_559_archiv_fertigstellen
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, archiv, go-api, wizard, briefing-history, template-copy, issue-559]
---

# Issue #559 — Archiv-Seite fertigstellen: Briefing-Verlauf, Vorlage kopieren, Was-passiert-ist

## Approval

- [ ] Approved

## Purpose

Die Archiv-Seite (`/archiv`) hat drei sichtbare aber inaktive Funktionen aus Issue #388: den Briefing-Verlauf-Button, den Vorlage-kopieren-Button und die „Was passiert ist"-Spalte zeigt überall `—`. Dieses Modul verdrahtet alle drei: ein neuer Go-Handler liefert die Briefing-Historie pro Tour, der Wizard-New-Flow akzeptiert einen `?from=`-Parameter um eine archivierte Tour als Vorlage zu laden, und die Spalte berechnet sich automatisch aus den bereits geladenen `archiveStats`-Counts.

> **Schicht-Hinweis:** AC-1 berührt Go-API (`internal/handler/`, `cmd/server/main.go`) und Frontend (`frontend/src/routes/archiv/`, `frontend/src/lib/components/briefing-history/`). AC-2 berührt ausschließlich Frontend (`frontend/src/routes/trips/new/`, `frontend/src/lib/components/trip-wizard/`). AC-3 ist rein Frontend (`frontend/src/routes/archiv/+page.svelte`). Python-Backend bleibt unverändert.

## Source

- **Neue Dateien:**
  - `internal/handler/briefing_history.go` — Go-Handler `BriefingHistoryHandler`
  - `internal/handler/briefing_history_test.go` — Go-Tests für den Handler
  - `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte` — Modal-Komponente
- **Geänderte Dateien:**
  - `cmd/server/main.go` — Route-Registrierung
  - `frontend/src/routes/archiv/+page.svelte` — History-Button-Wiring + „Was passiert ist"-Spalte
  - `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` — neue Methode `fromTemplate()`
  - `frontend/src/routes/trips/new/+page.server.ts` — `?from=`-Parameter auswerten
  - `frontend/src/routes/trips/new/+page.svelte` — Template anwenden beim Mount

## Estimated Scope

- **LoC:** ~290 (Override auf 350 nötig)
- **Files:** 8 (3 neu, 5 geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/store.go` → `LoadBriefingLog()` | Go Store (vorhanden, read-only) | Liefert alle `BriefingLogEntry{TripID, Kind, SentAt, Channels}` für den eingeloggten User; Handler filtert auf `trip_id` |
| `internal/handler/auth.go` → `getUserID()` | Go Helper (vorhanden, read-only) | Session-User-ID aus Request-Cookie auslesen; etabliertes Pattern in allen Handlers |
| `cmd/server/main.go` | Go Router (vorhanden, geändert) | Registriert `GET /api/trips/{id}/briefing-history` analog zu bestehenden Trip-Routen |
| `internal/handler/trip_test.go` | Go Test (vorhanden, read-only) | Referenz-Pattern für `chi.NewRouter()`-Wrapping in Handler-Tests |
| `frontend/src/routes/archiv/+page.server.ts` | SvelteKit Loader (vorhanden, read-only) | Liefert `archiveStats.briefings[trip.id]` + `archiveStats.alerts[trip.id]` — bereits geladen, kein Änderungsbedarf für AC-3 |
| `frontend/src/routes/archiv/+page.svelte` | SvelteKit Page (vorhanden, geändert) | History-Button in `ArchiveRow` verdrahten (AC-1); „Was passiert ist"-Spalte befüllen (AC-3) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` → `WizardState` | SvelteKit Klasse (vorhanden, geändert) | Neue Methode `fromTemplate(trip: Trip)` kopiert Konfigurations-Felder selektiv |
| `frontend/src/routes/trips/new/+page.server.ts` | SvelteKit Loader (vorhanden, geändert) | Liest `?from=` Query-Param, ruft `GET /api/trips/{id}` auf, übergibt `templateTrip` an Page |
| `frontend/src/routes/trips/new/+page.svelte` | SvelteKit Page (vorhanden, geändert) | Ruft `state.fromTemplate(data.templateTrip)` auf wenn `data.templateTrip` vorhanden |
| `frontend/src/lib/types.ts` → `Trip` | TypeScript-Typ (vorhanden, read-only) | Typisierung für `templateTrip` und `BriefingHistoryEntry`-Response |
| `contrast-audit.test.ts` | Test-Suite (vorhanden, read-only) | Muss nach Änderungen grün bleiben — kein Hex-Literal als Farbwert in Svelte-Dateien |

## Implementation Details

### 1. Go-Handler `BriefingHistoryHandler` (neu)

Datei: `internal/handler/briefing_history.go`

```go
func BriefingHistoryHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        uid, err := getUserID(r)
        if err != nil {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        tripID := chi.URLParam(r, "id")
        entries, err := s.WithUser(uid).LoadBriefingLog()
        if err != nil {
            http.Error(w, "internal error", http.StatusInternalServerError)
            return
        }
        type responseEntry struct {
            SentAt   time.Time `json:"sent_at"`
            Kind     string    `json:"kind"`
            Channels []string  `json:"channels"`
        }
        result := []responseEntry{}
        for _, e := range entries {
            if e.TripID == tripID {
                result = append(result, responseEntry{
                    SentAt:   e.SentAt,
                    Kind:     e.Kind,
                    Channels: e.Channels,
                })
            }
        }
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(result)
    }
}
```

- Liefert bei leerem Log `[]` (leeres JSON-Array), nie `null`
- `tripID`-Vergleich ist String-Gleichheit (UUIDs)
- Kein Subject-Feld — `BriefingLogEntry` speichert keinen Betreff

### 2. Route-Registrierung in `cmd/server/main.go`

```go
r.Get("/api/trips/{id}/briefing-history", handler.BriefingHistoryHandler(s))
```

Einfügen nach der bestehenden `r.Get("/api/trips/{id}", ...)` Zeile.

### 3. Go-Tests `briefing_history_test.go`

Pattern analog zu `trip_test.go`:

```go
router := chi.NewRouter()
router.Get("/api/trips/{id}/briefing-history", handler.BriefingHistoryHandler(store))
req := httptest.NewRequest("GET", "/api/trips/trip-123/briefing-history", nil)
// Session-Cookie setzen
rec := httptest.NewRecorder()
router.ServeHTTP(rec, req)
```

Testfälle:
- Unauthentifizierter Request → 401
- Authentifizierter Request, Trip hat Briefing-Log-Einträge → 200, JSON-Array mit korrekten Feldern
- Authentifizierter Request, andere Trip-ID → 200, leeres Array `[]`
- Store-Fehler → 500

### 4. Frontend-Komponente `BriefingHistoryDialog.svelte` (neu)

Datei: `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte`

Props: `tripId: string`, `tripName: string`, `open: boolean`, `onclose: () => void`

- Beim Öffnen (`open === true`): `GET /api/trips/{tripId}/briefing-history` via `fetch()`
- Loading-State anzeigen während Fetch läuft
- Ergebnis als chronologische Liste: Datum (`SentAt` formatiert als `DD.MM.YYYY HH:mm`), Kind (`morning` → „Morgen-Briefing", `evening` → „Abend-Briefing"), Channels als kommaseparierte Liste
- Leer-State: „Für diese Tour wurden noch keine Briefings versendet."
- Schließen via `onclose`-Callback oder Klick auf Hintergrund
- Alle Farben via `--g-*` CSS-Tokens, kein Hex-Literal

### 5. Archiv-Page-Änderungen: History-Button verdrahten (AC-1)

In `frontend/src/routes/archiv/+page.svelte`:

```svelte
<script>
  import BriefingHistoryDialog from '$lib/components/briefing-history/BriefingHistoryDialog.svelte';
  let historyTripId = $state<string | null>(null);
  let historyTripName = $state('');
</script>

<!-- Im ArchiveRow History-Button: -->
<Btn variant="quiet" size="icon-sm"
  onclick={() => { historyTripId = trip.id; historyTripName = trip.name; }}>
  <HistoryIcon />
</Btn>

<!-- Dialog am Ende der Page: -->
<BriefingHistoryDialog
  tripId={historyTripId ?? ''}
  tripName={historyTripName}
  open={historyTripId !== null}
  onclose={() => historyTripId = null}
/>
```

### 6. Archiv-Page-Änderungen: „Was passiert ist"-Spalte (AC-3)

In `frontend/src/routes/archiv/+page.svelte`, in der `ArchiveRow`-Spalte 5 (aktuell `—`):

```svelte
{@const briefingCount = archiveStats?.briefings?.[trip.id] ?? 0}
{@const alertCount = archiveStats?.alerts?.[trip.id] ?? 0}
{#if briefingCount === 0 && alertCount === 0}
  —
{:else if alertCount === 0}
  {briefingCount} Briefings
{:else}
  {briefingCount} Briefings · {alertCount} Alerts
{/if}
```

Kein Backend-Änderungsbedarf — `archiveStats` ist bereits im Page-Load vorhanden.

### 7. `WizardState.fromTemplate()` (AC-2)

In `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`, neue Methode an der `WizardState`-Klasse:

```ts
fromTemplate(trip: Trip): void {
    // Stages: Namen und Anzahl kopieren, keine Waypoints, keine Daten
    this.stages = (trip.stages ?? []).map(s => ({
        name: s.name,
        waypoints: [],
        startDate: null,
        endDate: null
    }));
    // Konfiguration übernehmen
    this.activity = trip.activity ?? null;
    this.alertRules = structuredClone(trip.alertRules ?? []);
    this.weatherMetrics = structuredClone(trip.weatherMetrics ?? []);
    this.channelLayouts = structuredClone(trip.channelLayouts ?? {});
    // Briefing-Zeiten: konservative Defaults (morning + evening aktiv)
    // archived trip's report_config.enabled unterscheidet nicht zuverlässig per report
    this.reportConfig = {
        morning: { enabled: true, hour: 6 },
        evening: { enabled: true, hour: 18 }
    };
    // NICHT kopiert: name, startDate, endDate, archived_at, id
}
```

Kommentar zu `reportConfig`: Das archivierte Trips `report_config.enabled` ist ein globaler Boolean, der nicht sicher auf morning/evening aufschlüsselbar ist. Konservative Defaults (beide aktiv) sind sicherer als inaktive Defaults.

### 8. `+page.server.ts` für `/trips/new` (AC-2)

```ts
export const load: PageServerLoad = async ({ url, cookies }) => {
    const fromId = url.searchParams.get('from');
    if (!fromId) return {};

    const session = cookies.get('gz_session');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (session) headers['Cookie'] = `gz_session=${session}`;

    const res = await fetch(`${API()}/api/trips/${fromId}`, {
        headers,
        signal: AbortSignal.timeout(5000)
    }).catch(() => null);

    const templateTrip: Trip | null = res?.ok ? await res.json() : null;
    return { templateTrip };
};
```

Fail-soft: bei Fehler oder fehlendem `?from=` ist `templateTrip` nicht gesetzt — Wizard startet leer.

### 9. `/trips/new/+page.svelte` Template anwenden (AC-2)

```svelte
<script>
  import { onMount } from 'svelte';
  let { data } = $props();
  // ...existing WizardState init...

  onMount(() => {
    if (data.templateTrip) {
      state.fromTemplate(data.templateTrip);
    }
  });
</script>
```

Visueller Hinweis im Wizard-Header wenn Template aktiv:
```svelte
{#if data.templateTrip}
  <p class="template-hint">Vorlage: {data.templateTrip.name}</p>
{/if}
```
Stilisierung: `--g-ink-3`, kleiner Font, kein prominentes Banner.

### 10. LoC-Budget

| Datei | Delta LoC | Zählt |
|-------|-----------|-------|
| `internal/handler/briefing_history.go` | ~35 (neu) | ja |
| `internal/handler/briefing_history_test.go` | ~70 (neu) | ja |
| `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte` | ~80 (neu) | ja |
| `cmd/server/main.go` | +1 | ja |
| `frontend/src/routes/archiv/+page.svelte` | ~30 | ja |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | ~25 | ja |
| `frontend/src/routes/trips/new/+page.server.ts` | ~15 | ja |
| `frontend/src/routes/trips/new/+page.svelte` | ~10 | ja |
| **Gesamt** | **~266** | **Override 350 nötig** |

## Expected Behavior

- **Input (AC-1):** Nutzer klickt History-Button in einer Archiv-Zeile → Modal öffnet sich, zeigt Briefing-Verlauf der Tour
- **Input (AC-2):** Nutzer klickt Vorlage-kopieren-Button → Browser navigiert zu `/trips/new?from={tripId}` → Wizard startet mit kopierten Konfigurationsfeldern
- **Input (AC-3):** Seite lädt → „Was passiert ist"-Spalte zeigt `"12 Briefings · 3 Alerts"` oder `"12 Briefings"` oder `—`
- **Output (AC-1):** JSON-Array `[{sent_at, kind, channels}]` vom neuen Endpoint; Modal rendert chronologische Liste
- **Output (AC-2):** Wizard-Formular vorausgefüllt mit Stages (nur Name, keine Waypoints/Daten), Activity, AlertRules, WeatherMetrics, ChannelLayouts; Name-Feld leer
- **Output (AC-3):** Textueller Auto-Summary aus bereits geladenen `archiveStats`-Counts
- **Side effects:**
  - AC-1: neuer GET-Endpoint im Go-API-Server registriert
  - AC-2: `+page.server.ts` für `/trips/new` macht ggf. einen zusätzlichen API-Call wenn `?from=` gesetzt
  - AC-3: keine

## Acceptance Criteria

- **AC-1:** Given eine archivierte Tour mit mindestens einem Briefing-Log-Eintrag / When der Nutzer auf den History-Button in der Archiv-Zeile klickt / Then öffnet sich `BriefingHistoryDialog` und zeigt eine Liste mit Datum, Briefing-Typ und Kanal(en) für jeden Eintrag; die Liste ist chronologisch absteigend sortiert; kein JS-Fehler

- **AC-2:** Given eine archivierte Tour mit Konfigurationsfeldern (activity, alertRules, weatherMetrics) / When der Nutzer auf den Vorlage-kopieren-Button klickt und der Wizard-New-Flow unter `/trips/new?from={tripId}` geladen wird / Then sind Stages (nur Namen, keine Waypoints/Daten), Activity, AlertRules, WeatherMetrics und ChannelLayouts im Wizard vorausgefüllt; Name-Feld ist leer; ein Hinweistext zeigt den Vorlagen-Namen an; startDate und endDate sind nicht gesetzt

- **AC-3:** Given die Archiv-Seite mit mindestens einer archivierten Tour, für die `archiveStats.briefings[trip.id] > 0` gilt / When die Seite geladen ist / Then zeigt die „Was passiert ist"-Spalte `"{n} Briefings · {m} Alerts"` wenn Alerts > 0, `"{n} Briefings"` wenn Alerts = 0, oder `—` wenn beide = 0; kein zusätzlicher API-Call für diese Spalte

- **AC-4:** Given ein unauthentifizierter Request an `GET /api/trips/{id}/briefing-history` / When der Handler aufgerufen wird / Then antwortet der Endpoint mit HTTP 401; kein Datenleck

- **AC-5:** Given eine Tour-ID, für die keine Briefing-Log-Einträge vorhanden sind / When `GET /api/trips/{id}/briefing-history` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200 und einem leeren JSON-Array `[]`; `BriefingHistoryDialog` zeigt den Leer-State-Text „Für diese Tour wurden noch keine Briefings versendet."

- **AC-6:** Given die Svelte-Dateien `BriefingHistoryDialog.svelte` und die geänderten Page-Komponenten / When `contrast-audit.test.ts` ausgeführt wird / Then sind alle Tests grün; kein Hex-Farbliteral in Svelte-Ausgabe, ausschließlich `--g-*` CSS-Tokens

## Known Limitations

- **Kein Subject/Betreff im Briefing-Log:** `BriefingLogEntry` speichert keinen Betreff. Die History-Ansicht zeigt nur Datum, Kind (morning/evening) und Channels — kein Betreff-Preview wie ggf. im Issue vorgestellt.
- **Wizard-Vorlage ohne Waypoints:** Etappen werden nur mit Name kopiert; Waypoints, Koordinaten und Daten werden explizit geleert. Dies ist das korrekte Verhalten (alte Daten würden in neuen Trip-Kontext passen nicht).
- **reportConfig konservative Defaults:** Da `report_config.enabled` im archivierten Trip kein per-report-Feld ist, werden im Template immer morning + evening aktiviert. Nutzer kann dies im Wizard anpassen.
- **Treffer-Spalte bleibt `—`:** Forecast-Accuracy hat kein Backend-Feld und ist außerhalb dieses Issues.

## Out of Scope

- Löschen archivierter Touren (dritter Aktions-Button — eigenes Issue)
- Sortierung „Genauigkeit" in der Archiv-Tabelle (kein Backend-Feld — aus Issue #388)
- Mobile-optimierte Ansicht der Briefing-History (Folge-Issue)
- Freitext-Feld für „Was passiert ist" (würde neues DB-Schema erfordern)
- Änderungen am Python-Backend oder `src/`-Verzeichnis

## Changelog

- 2026-06-02: Initial spec erstellt. Drei Archiv-Features: neuer Go-Handler für Briefing-Verlauf, Wizard-Template-Kopie via `?from=`-Param, Auto-Summary „Was passiert ist" aus bestehenden archiveStats-Counts. LoC-Override 350 dokumentiert.
