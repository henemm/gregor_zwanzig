---
entity_id: system_status_redesign
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, ui, f75]
---

# F75 — System-Status Seite: Inhalt fuer normale User ueberarbeiten

## Approval

- [ ] Approved

## Purpose

Wandelt die System-Status-Seite (`/settings`) von einer technischen Monitoring-Ansicht in ein user-freundliches "Mein Service"-Dashboard um. Statt interner Job-Namen, Backend-Config-Parameter und Go/Python-Health-Splits sieht der User: wann sein naechster Report kommt, wie viele Trips/Abos/Locations er hat, welche Benachrichtigungskanaele aktiv sind, welches Wetter-Modell pro Location genutzt wird, und ob der Service laeuft.

## Source

- **File:** `frontend/src/routes/settings/+page.svelte` **(REWRITE, ~200 LoC)**
- **File:** `frontend/src/routes/settings/+page.server.ts` **(EDIT, ~30 LoC)**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/api/scheduler/status` | Go endpoint | Job-Zeiten und Last-Run-Status (public, keine Auth) |
| `/api/health` | Go endpoint | System ok/degraded + Version (public, keine Auth) |
| `/api/auth/profile` | Go endpoint | E-Mail, Signal, Telegram des Users (auth required) |
| `/api/trips` | Go endpoint | Trip-Array fuer Count (auth required) |
| `/api/subscriptions` | Go endpoint | Abo-Array fuer Count (auth required) |
| `/api/locations` | Go endpoint | Location-Array mit lat/lon fuer Modell-Zuordnung (auth required) |

## Implementation Details

### Sektion 1: "Deine Reports"

**Card mit Titel "Deine Reports"** — zeigt wann die naechsten Reports verschickt werden.

Datenquelle: `/api/scheduler/status` → `jobs`-Array, gefiltert auf user-relevante Jobs.

**Job-Mapping (technisch → user-freundlich):**

| Job-ID | Anzeige-Name | Anzeige |
|--------|-------------|---------|
| `morning_subscriptions` | Morgen-Report | Naechster: Datum/Uhrzeit |
| `evening_subscriptions` | Abend-Report | Naechster: Datum/Uhrzeit |
| `trip_reports_hourly` | Trip-Checks | Stuendlich, zuletzt: relatives Zeitformat |
| `alert_checks` | **ausblenden** | — |
| `inbound_command_poll` | **ausblenden** | — |

**Zeitformat:** `next_run` als "morgen um 07:00" oder "18.04. um 18:00" (de-AT locale).

**Last-Run-Anzeige:** Relatives Format "vor X Minuten" / "vor X Stunden" fuer `last_run.time`. Bei `status === 'error'`: Warn-Badge mit Fehlermeldung.

**Fallback:** "Scheduler nicht erreichbar" wenn Daten null.

### Sektion 2: "Dein Account"

**Card mit Titel "Dein Account"** — Kurzuebersicht ueber aktive Daten und Kanaele.

**Zaehler mit Links:**

| Zeile | Datenquelle | Anzeige |
|-------|-------------|---------|
| Aktive Trips | `trips.length` | Zahl + Link zu `/trips` |
| Aktive Abos | `subscriptions.filter(s => s.enabled).length` | Zahl + Link zu `/subscriptions` |
| Locations | `locations.length` | Zahl + Link zu `/locations` |

**Benachrichtigungs-Kanaele:**

Aus `/api/auth/profile` die konfigurierten Kanaele anzeigen:
- E-Mail: `profile.mail_to` (falls gesetzt)
- Signal: `profile.signal_phone` (falls gesetzt)
- Telegram: `profile.telegram_chat_id` (falls gesetzt)
- Falls kein Kanal konfiguriert: Hinweis "Keine Benachrichtigungen konfiguriert" + Link zu `/account`

**Wetter-Modelle pro Location:**

Fuer jede Location aus dem `locations`-Array das genutzte Modell bestimmen:

```typescript
function getProvider(lat: number, lon: number): string {
  return (lat >= 45 && lat <= 50 && lon >= 8 && lon <= 18)
    ? 'GeoSphere (Alpen)'
    : 'OpenMeteo';
}
```

Anzeige als kompakte Liste: "Innsbruck → GeoSphere (Alpen)" / "Mallorca → OpenMeteo".

Falls keine Locations: "Noch keine Locations angelegt" + Link zu `/locations`.

### Sektion 3: "Verfuegbarkeit"

**Card mit Titel "Verfuegbarkeit"** — vereinfachter System-Status.

**Eine Ampel** statt Go/Python-Aufschluesselung:

| `health.status` | Anzeige |
|-----------------|---------|
| `ok` | Gruener Punkt + "System laeuft" |
| `degraded` | Gelber Punkt + "Eingeschraenkt" |
| Endpoint nicht erreichbar | Roter Punkt + "Nicht erreichbar" |

**Version:** Dezent unter der Ampel: "v0.1.0" in `text-muted-foreground`.

### Was entfaellt

| Bisheriger Inhalt | Grund |
|-------------------|-------|
| Konfigurations-Tabelle (Provider, Lat/Lon, Debug-Level, Kanal) | Reine Interna, User hat nichts davon |
| Go/Python Health-Split | Ops-Detail, nicht user-relevant |
| Job-Tabelle mit technischen Namen | Ersetzt durch user-freundliche Report-Zeiten |
| `/api/config` Fetch | Nicht mehr benoetigt |

### page.server.ts Aenderungen

**Entfaellt:** `/api/config` Fetch

**Neu:** 3 zusaetzliche Fetches (parallel via `Promise.all`):

```typescript
const [schedRes, healthRes, profileRes, tripsRes, subsRes, locsRes] = await Promise.all([
  fetch(`${API()}/api/scheduler/status`, { headers }).catch(() => null),
  fetch(`${API()}/api/health`, { headers }).catch(() => null),
  fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null),
  fetch(`${API()}/api/trips`, { headers }).catch(() => null),
  fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null),
  fetch(`${API()}/api/locations`, { headers }).catch(() => null),
]);
```

Return-Shape:

```typescript
{
  scheduler: SchedulerStatus | null,
  health: HealthResponse | null,
  profile: ProfileResponse | null,
  trips: Trip[],
  subscriptions: Subscription[],
  locations: Location[]
}
```

### UI-Komponenten

Benutzt bestehende Komponenten — keine neuen noetig:
- `Card` (Root, Header, Title, Description, Content)
- `Badge` (fuer Status-Anzeigen und Kanal-Tags)
- Svelte `{#if}` / `{#each}` fuer bedingte Anzeige
- `<a>` Links zu anderen Seiten

**Kein Table-Einsatz** in den neuen Sektionen — stattdessen kompaktere Layouts mit `flex`/`grid` und Description-Lists fuer bessere Lesbarkeit.

## Expected Behavior

- **Input:** Authentifizierter User oeffnet `/settings`
- **Output:** Dashboard mit 3 Sektionen: Reports, Account, Verfuegbarkeit
- **Side effects:** Keine — rein lesend, keine Mutations-Endpoints

### Fehlerfaelle

| Szenario | Verhalten |
|----------|-----------|
| Scheduler nicht erreichbar | "Report-Zeitplan nicht verfuegbar" |
| Profile nicht ladbar | Kanal-Sektion ausblenden |
| Trips/Subs/Locations nicht ladbar | Zaehler zeigt 0 |
| Health nicht erreichbar | Rote Ampel "Nicht erreichbar" |

## Known Limitations

- **Provider-Zuordnung ist Frontend-Logik:** Die GeoSphere-Bounds (45-50°N, 8-18°E) sind im Frontend dupliziert. Bei Aenderung der Backend-Logik muss das Frontend angepasst werden. Akzeptabel da sich diese Bounds selten aendern.
- **Keine Echtzeit-Updates:** Daten werden beim Seitenaufruf geladen (SSR), kein Polling/WebSocket.
- **Scheduler-Jobs nur OpenMeteo:** Im Scheduler wird generell OpenMeteo genutzt (siehe Bugfix-Spec `scheduler_provider_selection.md`). Die Provider-Anzeige pro Location zeigt das theoretisch genutzte Modell fuer Compare/Subscriptions, nicht fuer Trip-Reports.

## Changelog

- 2026-04-18: Initial spec created
