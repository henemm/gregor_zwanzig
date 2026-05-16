---
entity_id: issue_231_time_format
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, refactor, normalization]
issue: 231
---

<!-- Issue #231 — report_config Zeit-Format-Inkonsistenz HH:MM vs HH:MM:SS -->

# Issue #231 — Zeit-Format-Norm `HH:MM:SS` für `report_config`

## Approval

- [ ] Approved

## Zweck

`report_config.morning_time` und `report_config.evening_time` werden im
Frontend uneinheitlich formatiert: der Trip-Wizard und der Edit-Dialog
schreiben `'HH:MM'` (5 Zeichen), Defaults und Tests verwenden `'HH:MM:SS'`
(8 Zeichen). Python-Backend `time.fromisoformat()` akzeptiert beides, also
kein Funktionsbruch — aber Daten-Drift im Wire-Format, der bei zukünftiger
strikter Validierung bricht und schon jetzt Tests/Defaults von Schreib-Pfaden
auseinanderhält.

**Tech-Lead-Entscheidung:** Norm festlegen — **intern überall `HH:MM:SS`**
(Python/ISO-Konvention). HTML-`<input type='time'>` arbeitet zwingend mit
`HH:MM`; Konvertierung passiert genau an zwei Save-Grenzen.

Aufgedeckt im Refactoring-Sog von Issue #207 (strukturiertes Typing).

## Quelle / Source

- `frontend/src/lib/utils/time.ts` — neue Datei mit `toHHMMSS(time: string): string`-Helper + `node:test`-Test
- `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (Zeilen 348-349) — Save-Pfad konvertiert
- `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (Zeilen 124-125) — Save-Pfad konvertiert

## Acceptance Criteria

- **AC-1:** Given die neue Datei `frontend/src/lib/utils/time.ts` / When die Helper-Funktion `toHHMMSS('07:00')` aufgerufen wird / Then liefert sie `'07:00:00'`; bei `'07:00:00'` (bereits ISO-konform) liefert sie unverändert `'07:00:00'`; bei `''` oder `undefined` liefert sie den unveränderten Input (kein Crash, kein `:00`-Append auf leeren String)

- **AC-2:** Given `wizardState.svelte.ts::toTripPayload()` / When ein User im Wizard `morning.time='06:00'` und `evening.time='18:30'` setzt und Save klickt / Then enthält das gespeicherte `trip.report_config.morning_time === '06:00:00'` und `evening_time === '18:30:00'` (ISO-konform)

- **AC-3:** Given der Edit-Report-Config-Dialog (`EditReportConfigSection.svelte`) / When ein User einen bestehenden Trip mit `morning_time='07:00:00'` öffnet, die Zeit unverändert lässt, und speichert / Then bleibt `morning_time === '07:00:00'` (Roundtrip-stabil — `.slice(0,5)` beim Read + `toHHMMSS()` beim Write neutralisieren sich)

- **AC-4:** Given der Edit-Dialog / When der User die Zeit ändert via `<input type='time'>` oder Quick-Pick-Button / Then wird beim Save ebenfalls `'HH:MM:SS'` ins Backend geschrieben

- **AC-5:** Given `node:test` läuft auf `frontend/src/lib/utils/time.test.ts` / When die Tests für `toHHMMSS` ausgeführt werden / Then sind alle Cases grün: `'07:00'→'07:00:00'`, `'18:30'→'18:30:00'`, `'07:00:00'→'07:00:00'`, `''→''`, `'invalid'→'invalid'` (oder explizit beschriebener Fall — siehe §Erwartetes Verhalten unten)

- **AC-6:** Given svelte-check / When der Build läuft / Then ist die Error-Anzahl ≤ aktuelle Baseline (24) — keine neuen Type-Errors entstehen

## Erwartetes Verhalten

### `frontend/src/lib/utils/time.ts` (neu)

```typescript
/**
 * Konvertiert HH:MM auf HH:MM:SS (ISO-konform fuer Python time.fromisoformat).
 * Bereits ISO-konforme Strings (HH:MM:SS) bleiben unveraendert.
 * Leere/ungueltige Inputs werden unveraendert durchgereicht (defensive,
 * fuer Optional-Felder).
 *
 * Issue #231: report_config.morning_time / evening_time Norm.
 */
export function toHHMMSS(time: string | undefined): string | undefined {
  if (!time) return time;
  if (/^\d{2}:\d{2}$/.test(time)) return `${time}:00`;
  return time;  // bereits HH:MM:SS oder unbekanntes Format - durchreichen
}
```

### `wizardState.svelte.ts` (Save-Pfad, Zeilen 348-349)

```typescript
import { toHHMMSS } from '$lib/utils/time';
// ...
const rc: ReportConfig = {
  // ...
  morning_time: toHHMMSS(b.reports.morning.time),
  evening_time: toHHMMSS(b.reports.evening.time),
  // ...
};
```

### `EditReportConfigSection.svelte` (Save-Pfad, Zeilen 124-125)

```typescript
import { toHHMMSS } from '$lib/utils/time';
// ...
reportConfig = {
  ...originalReportConfig,
  enabled: morning_enabled || evening_enabled,
  morning_enabled,
  evening_enabled,
  morning_time: toHHMMSS(morning_time),
  evening_time: toHHMMSS(evening_time),
  // ...
};
```

### `frontend/src/lib/utils/time.test.ts` (neu)

```typescript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toHHMMSS } from './time.ts';

test('AC-1.1: toHHMMSS — HH:MM -> HH:MM:SS', () => {
  assert.equal(toHHMMSS('07:00'), '07:00:00');
  assert.equal(toHHMMSS('18:30'), '18:30:00');
});

test('AC-1.2: toHHMMSS — bereits HH:MM:SS bleibt unveraendert', () => {
  assert.equal(toHHMMSS('07:00:00'), '07:00:00');
});

test('AC-1.3: toHHMMSS — leerer String wird durchgereicht', () => {
  assert.equal(toHHMMSS(''), '');
});

test('AC-1.4: toHHMMSS — undefined wird durchgereicht', () => {
  assert.equal(toHHMMSS(undefined), undefined);
});

test('AC-1.5: toHHMMSS — unbekanntes Format wird durchgereicht (kein Crash)', () => {
  assert.equal(toHHMMSS('invalid'), 'invalid');
});
```

Ausführung: `cd frontend && node --experimental-strip-types --test src/lib/utils/time.test.ts`

## Out-of-Scope

- **Reader-Konsolidierung:** `parseHHMM` in `tripHero.ts` bleibt unverändert
  (tolerant gegen beide Formate). Verschieben nach `time.ts` wäre sauberer,
  aber separater Issue.
- **Backend-Validierung verschärfen:** Python akzeptiert weiterhin beide Formate;
  strikteres `fromisoformat`-Re-Validate beim API-Receive ist eigener Issue.
- **`<input type='time'>` durch eigenes Custom-Input mit Sekunden-Anzeige
  ersetzen** — User soll weiter HH:MM eintippen, das ist HTML-Standard und
  Wandersport-User-freundlich.

## Tests / Verifikation

- **Unit:** Neue `time.test.ts` (siehe AC-5).
- **TypeScript:** svelte-check, Baseline 24 Errors.
- **Staging-Manual-Probe:**
  1. Neuen Trip via Wizard mit `06:00`/`18:00` als Briefing-Zeiten anlegen → Save.
  2. Über API (`GET /api/trips/{id}`) oder Edit-Dialog laden → `morning_time === '06:00:00'`.
  3. Edit-Dialog: Zeit unverändert lassen, Save → Wert bleibt `'06:00:00'`.

## Risiken & Migration

- **Risiko sehr gering:** Reader sind robust; Python-Backend akzeptiert beide
  Formate weiterhin.
- **Wire-Format wird konsistent:** Neue Trips/Edits schreiben jetzt einheitlich
  `HH:MM:SS`. Bestandsdaten mit `HH:MM` werden beim nächsten Edit automatisch
  in `HH:MM:SS` migriert (Edit-Roundtrip).
- **Keine Daten-Migration nötig:** Lazy Migration über Edit-Roundtrip; falls
  gewünscht kann Backend-Side `morning_time = morning_time.padEnd(8, ':00')`
  bei Read normalisieren — Out-of-Scope.
- **Helper-Funktion ist defensiv:** Leere/ungültige Strings werden unverändert
  durchgereicht, kein Crash bei Off-Spec-Input.
