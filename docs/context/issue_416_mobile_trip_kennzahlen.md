# Context: Issue #416 — Mobile Trip-Detail Kennzahlen-Kacheln

## Request Summary

Auf Mobile fehlen drei kompakte Kennzahlen-Kacheln direkt unterhalb des Status-Badges im Trip-Detail-Header. Diese geben dem Nutzer sofortigen Überblick ohne Navigation in Sub-Tabs.

## SOLL vs. IST

**SOLL** (claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/mobile-m-trip-detail.png):
- Drei nebeneinander stehende Tiles (label oben, Wert unten):
  - ETAPPE → "2/5" (aktuelle Etappe / Gesamtzahl)
  - BRIEFING → "06:00" (nächste Briefing-Zeit)
  - START IN → "3 Tg" (Tage bis Startdatum)
- Position: direkt nach Status-Badge, vor den Tabs

**IST** (claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/mobile-m-trip-detail.png):
- Kein Metric-Tile-Bereich vorhanden
- Nur: Breadcrumb → H1 → status-line (daysLabel + Badge) → meta-line → Buttons → Tabs

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Hauptdatei — hier werden die Tiles ergänzt |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()`, `todayStageIndex()` — aktuelle Etappe berechnen |
| `frontend/src/lib/utils/tripHero.ts` | `getDaysLabel()`, `sortedStageDates()` — Tage bis Start |
| `frontend/src/lib/utils/tripStats.ts` | `computeTripStats()` — `stages.length` |
| `frontend/src/lib/utils/rightColumn.ts` | `getReportSchedule()` — morning_time / evening_time |
| `frontend/src/lib/types.ts` | `Trip`, `ReportConfig` — Datenstruktur |
| `frontend/src/app.css` | `@custom-variant mobile { @media (max-width: 899px) }` — Breakpoint |
| `frontend/src/routes/trips/[id]/+page.svelte` | Verwendet TripHeader, übergibt `trip` + `now` |

## Bestehende Patterns

- **Mobile-Breakpoint:** `@media (max-width: 899px)` — konsistent im gesamten Projekt
- **TripHeader.svelte** hat bereits `now` als Prop (wird für daysLabel genutzt)
- **TripStats**: `computeTripStats(trip).stages` = Gesamtzahl Etappen
- **Aktive Etappe**: `todayStageIndex(trip, now)` (0-basiert, -1 wenn keine heute-Etappe)
- **Briefing-Zeit**: `getReportSchedule(trip)` → `.morning` (z.B. `"06:00:00"`) → `.slice(0,5)` → `"06:00"`; Priority: morning_enabled → morning, dann evening_enabled → evening
- **Tage bis Start**: aus `sortedStageDates()` (bereits in tripHero.ts) → diff zwischen heute und erstem Datum

## Data Logic pro Tile

### Tile 1: ETAPPE

| Status | Wert |
|--------|------|
| planned | `—/Y` (noch kein aktiver Tag) |
| active | `X/Y` (todayStageIndex + 1 / stages.length) |
| paused | `—/Y` |
| archived | `Y/Y` |

Y = `computeTripStats(trip).stages`

### Tile 2: BRIEFING

Priority: Wenn `morning_enabled` → morning_time (HH:MM). Wenn nicht, aber `evening_enabled` → evening_time (HH:MM). Wenn keins aktiv → `"—"`.

### Tile 3: START IN

| Status | Label | Wert |
|--------|-------|------|
| planned | START IN | "N Tg" (Tage bis erstem Stage-Datum) |
| active | TAG | "N" (todayStageIndex + 1, = welcher Tag) |
| paused | —  | "—" |
| archived | —  | "—" |

## Dependencies

- **Upstream:** `trip.stages`, `trip.report_config`, `trip.paused_at`, `trip.archived_at`
- **Downstream:** `TripHeader.spacing.test.ts` (testet Source-Markup via readFileSync — muss angepasst werden wenn neue Struktur H1-Bereich ändert; die Tiles sind NACH H1 → kein Konflikt)

## Existing Specs

- `docs/specs/modules/issue_302_trip_detail_page.md` — Trip-Detail Basis-Spec
- SOLL-Audit-Bericht: `docs/analysis/epic_404_phase3_soll_ist_vergleich.md`, Finding B-12

## Risks & Considerations

1. **Nur Mobile:** Tiles müssen auf Desktop (≥900px) verborgen sein — Action-Buttons sind dort schon sichtbar und der Platz ist für Navigation genutzt
2. **Keine neuen API-Calls:** Alle Daten kommen aus dem bereits geladenen `trip`-Objekt
3. **Lokalisierung:** Einheitlich Deutsch ("Tg", "Tag"); Zahlen mit führenden Nullen falls nötig; Briefing-Zeit ohne Sekunden
4. **Grenzfälle:** Trip ohne Etappen (stages=0), Trip ohne report_config, archivierter Trip
5. **Platzierung:** Tiles erscheinen NACH dem Status-Badge (status-line), VOR den Tabs — also noch innerhalb TripHeader
