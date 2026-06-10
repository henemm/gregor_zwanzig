---
entity_id: issue_727_trips_null_safety
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trips, null-safety, ssr, bugfix]
---

# Issue #727 — Trips-Seite: Null-Safety für stages-Feld

## Approval

- [ ] Approved

## Purpose

Behebt einen SSR-500-Absturz auf `/trips`, der auftritt wenn mindestens ein Trip in der Datenbank `stages: null` hat. Der TypeScript-Typ deklariert `stages: Stage[]` (kein null), die Go-API liefert aber `null` wenn beim Trip-Anlegen kein `stages`-Feld übergeben wurde. Zwei Stellen in `+page.svelte` greifen ohne Null-Guard auf `stages` zu — das macht die gesamte Trips-Übersicht für alle Nutzer unbenutzbar sobald ein solcher Trip existiert.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte`
- **Identifier:** `dateRange()` (Z. 224–225), Desktop-Karte Etappen-Zähler (Z. 423)

## Estimated Scope

- **LoC:** ~3 (zwei gezielte optional-chaining-Ergänzungen)
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/trips/+page.svelte` | Modify | Null-Guards an den zwei crashenden Stellen einfügen |
| Go-API `GET /api/trips` | Read-only | Liefert `stages: null` für Trips ohne Etappen — bleibt unverändert |

## Implementation Details

### Fix 1 — `dateRange()` (Z. 224–225)

Aktuelle fehlerhafte Implementierung:

```svelte
if (!trip.stages.length)        // Z. 224 — ReferenceError bei null
  trip.stages.map((s) => s.date).sort()  // Z. 225 — dito
```

Korrigierte Implementierung mit optional chaining:

```svelte
if (!trip.stages?.length)
  trip.stages?.map((s) => s.date).sort()
```

Verhalten bei `stages === null`: `trip.stages?.length` ergibt `undefined`, der `!undefined`-Guard ist `true` → Funktion gibt früh `'-'` zurück (identisches Verhalten zu einem Trip mit leeren stages).

### Fix 2 — Desktop-Karte Etappen-Zähler (Z. 423)

Aktuelle fehlerhafte Implementierung:

```svelte
{trip.stages.length} Etappen
```

Korrigierte Implementierung:

```svelte
{trip.stages?.length ?? 0} Etappen
```

Verhalten bei `stages === null`: zeigt `0 Etappen` (analog zu Z. 471, die bereits null-safe ist).

### Nicht anfassen

Z. 471 (`{trip.stages?.length ?? 0}`) ist bereits korrekt — kein Fix nötig.

## Expected Behavior

- **Input:** Trip-Objekt aus der API mit `stages: null`
- **Output:** `dateRange()` gibt `'-'` zurück; Desktop-Karte zeigt `0 Etappen`
- **Side effects:** keine — andere Trips (mit echten Etappen oder leerem Array) sind von optional chaining nicht betroffen

## Acceptance Criteria

**AC-1:** Given ein Nutzer hat mindestens einen Trip mit `stages: null` in der Datenbank / When der Nutzer `/trips` aufruft / Then lädt die Seite ohne HTTP-500-Fehler und zeigt alle Trips in der Listenansicht an.

**AC-2:** Given ein Trip mit `stages: null` existiert / When `dateRange()` für diesen Trip aufgerufen wird / Then gibt die Funktion `'-'` zurück (kein Crash, kein leerer String, kein undefined).

**AC-3:** Given ein Trip mit `stages: null` existiert / When die Desktop-Karten-Ansicht (`/trips`) gerendert wird / Then zeigt die Karte dieses Trips `0 Etappen` an statt abzustürzen.

**AC-4:** Given Trips mit echten Etappen existieren / When `/trips` geladen wird / Then werden Datum-Range und Etappen-Anzahl dieser Trips weiterhin korrekt angezeigt (keine Regression).

## Known Limitations

- Die Ursache (API liefert `null` statt `[]`) liegt im Go-Backend und wird hier nicht behoben. Ein separates Issue sollte prüfen, ob die API konsistent `[]` zurückgeben soll um zukünftige Null-Bugs zu verhindern.
- Die TypeScript-Typ-Deklaration `stages: Stage[]` entspricht nicht der API-Realität (`Stage[] | null`). Eine Typ-Korrektur wäre ein separater Schritt.

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-10 | Initial spec — Bug-Fix für SSR-500 bei stages:null |
