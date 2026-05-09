# Context: Epic #134 — Startseite: Trip-Cockpit

## Request Summary

Die Startseite (`/`) wird von einer einfachen Kachel-Liste zu einem vollwertigen Trip-Cockpit umgebaut. Kernprinzip: der aktive Trip steht im Fokus, Briefing-Status und Alerts sind auf einen Blick sichtbar. Basis ist das in Epic #133 gebaute Design-System.

## Child-Issues

| Issue | Titel | Inhalt |
|-------|-------|--------|
| #147 | Topbar | Datum, Begrüßung, CTAs (Test-Briefing senden, Neuer Trip) |
| #148 | Hero — Aktiver Trip Card | Status-Pill ('Live · Tag X von Y'), Etappen-Stats, ElevSparkline, Wetter-Zeile |
| #149 | Stage-Pill + Etappen-Strip | `StagePill`-Komponente (Code, Risiko-Bar, aktiv/muted) + horizontaler Strip |
| #150 | Briefings-Timeline | Card 'Was geht raus' — ReportRow pro Job (Zeit, Art, Kanäle, Status) |
| #151 | Alert-Feed | Card 'Alerts letzte 24h' — AlertRow (Icon, Zeitstempel, Nachricht) |
| #152 | Morgen-Vorschau + Archiv-Grid | Nächste Etappe (Sparkline + Summary) + 4 Archiv-Kacheln |

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/routes/+page.svelte` | **Hauptdatei** — wird vollständig umgebaut |
| `frontend/src/routes/+page.server.ts` | Server-Loader — lädt Trip+Subscription, muss um Scheduler-Status erweitert werden |
| `frontend/src/lib/types.ts` | Typen (Trip, Stage, Waypoint) — evtl. neue Typen für SchedulerStatus |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Design-System Pill — basis für StagePill |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Elevation-Sparkline — direkt verwendbar in Hero + Morgen-Vorschau |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Topo-Hintergrund — gut für Hero-Card |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | GCard — für alle Cockpit-Sektionen |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Eyebrow-Label — für Sektion-Header |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Btn — für Topbar-CTAs |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Dot — für Status-Indikatoren |
| `frontend/src/app.css` | CSS-Tokens (`--g-*`) — Farb-/Radius-/Shadow-Tokens |
| `internal/model/trip.go` | Trip/Stage/Waypoint-Datenmodell (Go) |
| `internal/scheduler/scheduler.go` | Scheduler-Status-Struktur |
| `cmd/server/main.go` | Alle API-Routen |

## Existing Patterns

- **Server-Loader:** `+page.server.ts` nutzt `fetch` direkt gegen `http://localhost:8090/api/*` mit Session-Cookie-Forwarding — dasselbe Pattern für `/api/scheduler/status` anwenden
- **Design-System:** Alle Atoms nutzen `data-slot` + `data-variant`/`data-tone`-Attribute, Styles in `app.css @layer components`
- **Svelte 5 Runes:** `$props()`, `$state()`, `$derived()` — kein `let … = export` mehr
- **Icon-Import:** `import FooIcon from '@lucide/svelte/icons/foo'`

## Kritische Befunde: Fehlende API-Daten (bestehend aus Phase 1)

### 1. Aktiver Trip — keine server-seitige Logik vorhanden
Die API liefert alle Trips flat ohne "aktiv"-Flag. Der aktive Trip muss client-seitig bestimmt werden: Etappe, deren `date` dem heutigen Datum entspricht. Kein Go-API-Change nötig — reine Frontend-Logik.

**Formel:**
```ts
const today = new Date().toISOString().slice(0, 10); // 'YYYY-MM-DD'
const activeTrip = trips.find(t => t.stages.some(s => s.date === today));
const todayStage = activeTrip?.stages.find(s => s.date === today);
const dayIndex = activeTrip?.stages.findIndex(s => s.date === today); // "Tag X von Y"
```

### 2. Alert-Feed — kein Endpunkt vorhanden
`/api/scheduler/alert-checks` ist nur ein POST-Trigger (kein GET für History). Es gibt **keinen** Alert-History-Endpunkt. Alert-Feed (#151) muss mit Platzhalter ("Keine Alerts in den letzten 24h") oder aus dem Scheduler-Status abgeleitet werden.

**Optionen:**
- A) Mock: statischer Leer-State "Keine Alerts" — kein Backend-Aufwand
- B) Neuer Go-Endpunkt `/api/alerts` mit in-memory Ring-Buffer — Aufwand ~1h Go
- Empfehlung: Option A für MVP, Option B als separates Issue

### 3. Briefings-Timeline — Scheduler-Status vorhanden, aber kein Versand-Log
`/api/scheduler/status` liefert `next_run`, `last_run.time`, `last_run.status` pro Job. Das zeigt wann zuletzt gelaufen und ob erfolgreich — aber nicht "Briefing wurde an User X gesendet".

**Plan:** Scheduler-Status-Daten für die Timeline nutzen (nächste geplante Läufe + letzter Status), ohne neue Backend-Logik.

### 4. ElevSparkline-Daten
`Waypoint.elevation_m` ist `number` in `types.ts` und `int` in `model/trip.go`. ElevSparkline erwartet `number[]`. Mapping: `stage.waypoints.map(w => w.elevation_m)`.

## Scheduler-Status-Struktur (Go)

```json
{
  "running": true,
  "timezone": "Europe/Berlin",
  "jobs": [
    {
      "id": "morning",
      "name": "Morning Reports",
      "next_run": "2026-05-10T07:00:00+02:00",
      "last_run": {
        "time": "2026-05-09T07:00:02+02:00",
        "status": "ok",
        "error": ""
      }
    }
  ]
}
```

## User-Story-Mapping (neu aus US-Spec)

Die Startseite ist der einzige Ort, der alle drei User Stories gleichzeitig sichtbar macht:

| Cockpit-Bereich | User Story | Was wird sichtbar |
|----------------|-----------|-------------------|
| Hero: Aktiver Trip (#148) + ElevSparkline | **US-1** (Workspace) | "Das System kennt meinen genauen Standort heute" |
| Etappen-Strip (#149) | **US-1** (Workspace) | Mein ganzer Reiseweg, die aktive Etappe hervorgehoben |
| Briefings-Timeline (#150) | **US-3** (Autarkes System) | "Das geht automatisch raus — zur richtigen Zeit" |
| Alert-Feed (#151) | **US-3** (Wachhund) | "Der Wachhund hat angeschlagen / alles ruhig" |
| Wetter-Zeile im Hero | **US-2** (Metriken) | Kompakte Zusammenfassung der konfigurierten Kern-Metriken |
| Test-Briefing CTA (Topbar #147) | **US-3** (Autarkes System) | Manueller Trigger: "Sende Briefing jetzt" |

## Kritische Befunde: Fehlende API-Daten

### 5. Trip-Status — kein Status-Feld im Datenmodell
`model/trip.go` hat **kein** `status`-Feld (Geplant / Aktiv / Pausiert / Archiviert). Das Archiv-Grid (#152) braucht "abgeschlossene" Trips, der Hero braucht "aktive" Trips.

**Inferenz-Logik (rein frontend-seitig, kein Backend-Aufwand):**
```ts
type TripStatus = 'active' | 'upcoming' | 'archived';

function getTripStatus(trip: Trip): TripStatus {
  const today = new Date().toISOString().slice(0, 10);
  const dates = trip.stages.map(s => s.date).filter(Boolean).sort();
  if (dates.length === 0) return 'upcoming';
  if (dates[dates.length - 1] < today) return 'archived';
  if (dates[0] <= today) return 'active';
  return 'upcoming';
}
```

**Für das Archiv-Grid:** `trips.filter(t => getTripStatus(t) === 'archived').slice(0, 4)`

### 6. Wetter-Summary-Zeile im Hero — benötigt Forecast-Call
Die Hero-Card soll eine "Wettereinzeile" zeigen (z.B. "☀️ 18° · Wind 25 km/h · Kein Regen"). Das erfordert einen Forecast-Call für den ersten Wegpunkt der heutigen Etappe.

**Endpunkt:** `GET /api/forecast?lat=...&lon=...` (liefert `ForecastResponse`)

**Entscheidung für MVP:** Wetter-Zeile im Server-Loader nur dann laden, wenn ein aktiver Trip existiert und dessen heutige Etappe mindestens einen Waypoint hat. Sonst Leer-State "Keine Wetterdaten".

**Zusätzlicher fetch in `+page.server.ts`:**
```ts
// Nur wenn aktiver Trip + heutige Etappe + Waypoint vorhanden
if (firstWaypoint) {
  const fRes = await fetch(`${API()}/api/forecast?lat=${firstWaypoint.lat}&lon=${firstWaypoint.lon}`, { headers });
  forecast = fRes?.ok ? await fRes.json() : null;
}
```

### 7. Test-Briefing-Button — POST-Endpunkt
Topbar-CTA "Test-Briefing senden" triggert `POST /api/scheduler/trip-reports`. Dieser Endpunkt ist bereits vorhanden (kein Backend-Aufwand). Der Button im Frontend muss einen `fetch`-POST auslösen und Feedback zeigen (Toast/Spinner).

## Dependencies

- **Upstream:** Go API (`/api/trips`, `/api/scheduler/status`, `/api/forecast`) → `+page.server.ts` → `+page.svelte`
- **Downstream:** Keine anderen Seiten hängen an `+page.svelte`
- **Design-System-Voraussetzung:** Epic #133 (Lauf A + B) muss deployed sein — ✅ bereits committed

## Risks & Considerations

- **Safari:** Alle `on_click`-Handler müssen Factory-Pattern nutzen (`make_*` → `do_*`) — CLAUDE.md-Pflicht
- **Alert-Feed ohne Backend:** Entweder Platzhalter oder separates Issue für Alert-History-Endpunkt
- **Performance:** Server-Loader macht bereits 2 fetches (trips + subscriptions), `/api/scheduler/status` kommt als 3. hinzu — noch akzeptabel (parallel mit `Promise.all`)
- **Leer-State:** Wenn kein aktiver Trip vorhanden (kein heutiges Datum) → Hero zeigt nächsten Trip oder generischen Willkommens-State
- **Kein "aktiv"-Flag:** Wenn mehrere Trips an demselben Tag Etappen haben → erster Match gewinnt (edge case, ignorierbar für MVP)
