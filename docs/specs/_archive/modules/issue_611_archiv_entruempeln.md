---
entity_id: issue_611_archiv_entruempeln
type: module
created: 2026-06-05
updated: 2026-06-05
status: draft
version: "1.0"
tags: [archive, design-compliance, compare, trip]
---

# Issue #611 — Archiv entrümpeln (reines Archiv für Trips + Vergleiche)

## Approval

- [x] Approved — PO (Henning) 2026-06-05

## Purpose

Die Archiv-Seite wird auf das kanonische Mockup `screen-archive.jsx` zurückgebaut:
ein reines Archiv für **Trips und Orts-Vergleiche** mit genau zwei Aktionen pro
Eintrag (Wieder aktivieren, Löschen). Die nie spezifizierte Forecast-Analytik
(Genauigkeit, AccuracyBar, „Was passiert ist", Summen-Statistik) wird vollständig
entfernt — Oberfläche **und** Datenfelder.

## Source

- **Frontend:** `frontend/src/routes/archiv/+page.svelte`, `+page.server.ts`, `archiveHelpers.ts`
- **Frontend-Typ:** `frontend/src/lib/types.ts` (Trip)
- **Compare-Einstieg:** `frontend/src/routes/compare/+page.svelte` (+ Tile/Grid)
- **Go-API:** `internal/model/trip.go`, `internal/model/compare_preset.go`,
  `internal/handler/compare_preset.go`, `cmd/server/main.go`, `internal/store/store.go`
- **Kanonisches Soll:** `claude-code-handoff/current/jsx/screen-archive.jsx`,
  `claude-code-handoff/current/soll/H-archive.png`

## Estimated Scope

- **LoC:** ~280–340 produktiv (Frontend-Rewrite + Compare-Archivzustand + Feld-Cleanup) — über 250-Softlimit (PO-bestätigt als ein zusammenhängender Schritt am 2026-06-05)
- **Files:** ~9
- **Effort:** high

## Dependencies

- `gz_session`-Cookie, `GZ_API_BASE` (SSR-Fetch)
- Vorhandene Trip-Endpoints: `PATCH /api/trips/{id}/state` (archive/reaktivieren),
  `DELETE /api/trips/{id}`
- Vorhandene Compare-Endpoints: `GET /api/compare/presets`, `DELETE /api/compare/presets/{id}`
- Design-Fidelity-Gate (#603): Pixel-Diff gegen `H-archive.png`

## Datenmodell

Ein archivierter Eintrag wird im Frontend als vereinheitlichter Typ dargestellt:

```ts
type ArchiveEntry = {
  id: string;
  type: 'trip' | 'compare';
  name: string;
  detail: string;   // "13 Etappen" | "6 Orte"
  archived: string; // ISO-Datum, Anzeige YYYY-MM-DD
};
```

Backend additiv: `ComparePreset.ArchivedAt *time.Time` (`json:"archived_at,omitempty"`).
Entfernt: `Trip.AccuracyPct/Headline/BriefingsCount/AlertsCount` (#583-Felder, ungenutzt).

## Acceptance Criteria

**AC-1:** Given die Archiv-Seite ist geladen, When der Nutzer die Seite betrachtet,
Then erscheint **keine** Genauigkeits-, Forecast- oder Briefing-Statistik — weder
eine Summen-Leiste oben noch eine Spalte „Treffer"/AccuracyBar noch eine Spalte
„Was passiert ist" pro Zeile.

**AC-2:** Given archivierte Trips und archivierte Vergleiche existieren, When die
Archiv-Liste rendert, Then enthält sie **beide** Typen, jede Zeile trägt ein
sichtbares Typ-Kennzeichen (Pill, mono, uppercase) — „Trip" neutral, „Vergleich"
in abgesetztem Grün (#3d6b3a).

**AC-3:** Given die Filter-Leiste „Alle · Trips · Vergleiche", When der Nutzer einen
Filter wählt, Then zeigt die Liste nur Einträge dieses Typs und jede Pill trägt
einen korrekten Count-Badge; die Namenssuche filtert zusätzlich case-insensitiv
über den Namen.

**AC-4:** Given die Tabellen-Kopfzeile, When sie rendert, Then hat sie genau die
Spalten „Name" (inkl. Typ-Tag) · „Umfang" · „Archiviert" · „Aktionen" im Grid
`2fr 1fr 1fr auto`, ohne weitere Datenspalten.

**AC-5:** Given eine Archiv-Zeile eines Trips, When der Nutzer „Wieder aktivieren"
klickt, Then ruft die Seite `PATCH /api/trips/{id}/state` mit `{archived:false}`
auf, der Trip verschwindet aus dem Archiv und erscheint wieder unter „Meine Trips".

**AC-6:** Given eine Archiv-Zeile eines Vergleichs, When der Nutzer „Wieder
aktivieren" klickt, Then wird `archived_at` des Vergleichs serverseitig auf null
gesetzt, der Vergleich verschwindet aus dem Archiv und erscheint wieder unter
„Orts-Vergleiche".

**AC-7:** Given eine beliebige Archiv-Zeile, When der Nutzer „Löschen" klickt und
den Bestätigungsdialog bestätigt, Then wird der Eintrag endgültig entfernt
(`DELETE /api/trips/{id}` bzw. `DELETE /api/compare/presets/{id}`) und verschwindet
aus der Liste; bei Abbruch bleibt er erhalten.

**AC-8:** Given die Vergleichs-Seite mit einem aktiven Vergleich, When der Nutzer
dort „Archivieren" wählt, Then setzt der Server `archived_at` des Vergleichs und der
Vergleich wandert aus „Orts-Vergleiche" ins Archiv (Einstiegspunkt, damit Vergleiche
das Archiv überhaupt erreichen).

**AC-9:** Given das Trip-Modell und der Frontend-Trip-Typ, When der Code nach dem
Umbau gebaut wird, Then existieren die Felder `accuracy_pct`, `headline`,
`briefings_count`, `alerts_count` nicht mehr (Backend-Struct, JSON-Serialisierung,
TypeScript-Typ, Seed-Skript) und kein Code referenziert sie.

**AC-10:** Given die Archiv-Liste ist leer oder die Suche liefert keinen Treffer,
When die Seite rendert, Then zeigt sie den Leerzustand „Keine archivierten Einträge"
bzw. „Keine archivierten Einträge für »…« gefunden."; der Footer zeigt „N von M
Einträgen · Trips auto-archiviert nach Trip-Ende".

## Edge Cases

| Fall | Verhalten |
|---|---|
| Archiv leer | „Keine archivierten Einträge" |
| Suche ohne Treffer | „Keine archivierten Einträge für »…« gefunden." |
| Vergleich ohne Enddatum | `archived` = Datum der manuellen Archivierung (`archived_at`) |
| Reaktivierter Trip mit Datum in Vergangenheit | landet in „Meine Trips" (Status geplant/aktiv), Datums-Logik wie Editor |
| Löschen abgebrochen | Eintrag bleibt erhalten, kein API-Call |

## Out of Scope

- Keine neue Analytik in irgendeiner Form.
- Keine Migration historischer Briefing-Logs (`/api/archive/stats` bleibt als
  Endpoint bestehen, wird aber vom Archiv nicht mehr genutzt).

## Test-Strategie (keine Mocks)

- **Frontend-E2E (Playwright gegen Staging, eingeloggt):** Archiv-Seite öffnen,
  beide Typen + Tags prüfen, Filter+Counts klicken, Suche, Reaktivieren eines Trips
  und eines Vergleichs (Verschwinden + Wiedererscheinen am Zielort), Löschen mit
  Confirm. Pixel-Diff gegen `H-archive.png` (#603-Gate).
- **Backend (echter HTTP-Call gegen lokale/Staging-API):** Compare-State-PATCH setzt
  `archived_at`; DELETE entfernt; Roundtrip-Test ComparePreset mit/ohne `archived_at`.
- **Schema-Roundtrip:** Bestands-`compare_presets.json` ohne `archived_at` lädt
  weiterhin fehlerfrei (additives Feld).
