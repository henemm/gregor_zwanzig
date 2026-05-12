# Context: Issue #154 — Trip-Übersicht: Hero + Stats

## Request Summary

Drittes Sub-Issue von Epic #135. In den **Tab „Übersicht"** (heute Placeholder mit „Inhalt folgt mit Issue #154 (Hero)") kommt der Trip-Hero — die zentrale Bühne mit:

1. **H1 Trip-Name** (groß, prominent)
2. **Region** (z.B. „Mallorca", „Korsika") — siehe Risk §1
3. **Zeitraum** (Start–Ende, z.B. „11. Mai – 14. Mai 2026")
4. **3 Stat-Kacheln:**
   - **Aktive Etappe** (z.B. „Tag 2/5 — Vizzavona → Capannelle" oder „Trip startet in 3 Tagen")
   - **Nächstes Briefing** (z.B. „Heute Abend, 18:00")
   - **Tage bis Start** (z.B. „in 12 Tagen", „läuft seit Tag 2", „beendet vor 3 Tagen")

Der Hero ersetzt den Placeholder im „Übersicht"-Tab — sitzt **im Tab-Panel**, nicht über dem Tab-Header.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | **EDIT.** Placeholder `Inhalt folgt mit Issue #154 …` im Overview-Panel ersetzen durch `<TripHero {trip} />` |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | **NEU.** Hero-Komponente |
| `frontend/src/lib/components/trip-detail/index.ts` | **EDIT.** Barrel-Export `TripHero` |
| `frontend/src/lib/utils/tripHero.ts` | **NEU.** Pure-Functions: `getActiveStage`, `getNextBriefing`, `daysUntilStart`, `formatDateRange`, `getRegion` |
| `frontend/src/lib/utils/tripHero.test.ts` | **NEU.** Vitest-/node-test-runner Unit-Tests |
| `frontend/src/routes/trips/[id]/+page.svelte` | **EDIT (klein).** trip an TripTabs durchreichen (Tabs braucht trip für Hero) |
| `frontend/e2e/trip-detail-hero.spec.ts` | **NEU.** Playwright-Tests |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | **REFERENZ.** Stil-Vorbild für Hero (h1 + Pill + Eyebrow + ElevSparkline). Macht sehr ähnliche Anzeige im Cockpit. |
| `frontend/src/lib/components/ui/g-card/`, `ui/eyebrow/`, `ui/pill/` | Bausteine für Stat-Kacheln |
| `frontend/src/routes/+page.svelte` (Z. 25-32) | **REFERENZ.** Cockpit-Logik für `activeTrip`, `todayStage`, `dayIndex` — wiederverwendbares Pattern |

## Existing Patterns

- **Stat-Kacheln im Cockpit (BriefingsTimeline.svelte):** GCard mit Eyebrow + Dot + Wert. Analog für Hero-Stats.
- **Aktive Stage Berechnung (Cockpit):** `activeTrip?.stages.findIndex(s => s.date === today)` — direkt übernehmbar.
- **Date-Formatting (BriefingsTimeline.svelte:39-47):** `Date.toLocaleString('de-AT', { timeZone: 'Europe/Vienna', ... })` — Pattern für Zeit-Anzeige.
- **`timeAgo`/relative-time helper (BriefingsTimeline.svelte:28-37):** „vor 12 Min", „vor 3 Tagen" — fast 1:1 wiederverwendbar für „läuft seit Tag 2" oder „in 3 Tagen".
- **Tech-Lead-Pattern aus Step 2:** Pure-Function in `lib/utils/` + thin Svelte-Wrapper. Wiederverwenden.

## Dependencies

- **Upstream:** Trip-Objekt mit `name`, `stages` (mit Datum), `report_config.morning_time`/`evening_time` (für Briefings).
- **Downstream:** Step 4 (Höhenprofil-SVG, Issue #156) und Step 5 (Stage-Row-Liste, Issue #157) docken **im selben Übersicht-Panel** unter dem Hero an.

## Existing Specs

- `docs/specs/modules/epic_135_step1_tab_navigation.md` — Tab-Skelett (Vorgänger). Overview-Tab erwartet Hero-Inhalt.
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` — direkter Vorgänger (Header). Hero kommt darunter, im Tab-Panel.
- **Keine Master-Spec** für Epic #135. Konsistent zu Step 1 + 2: nur Sub-Spec.

## Risks & Considerations

### 1. Region — woher? (Tech-Lead-Empfehlung)

Trip-Modell hat **kein Region-Feld**. Vier Wege:

| Weg | Aufwand | Vorteil | Nachteil |
|---|---|---|---|
| Neues `region`-Feld am Trip-Modell + Wizard-Erweiterung | ~30 LoC + Wizard-Edit | Sauber, vom User gepflegt | Erweitert Scope auf Wizard |
| Aus `avalanche_regions[0]` ableiten (z.B. „AT-07-15") | ~5 LoC | Sofort verfügbar | Kryptisch, nur für Wintersport |
| Region-Reverse-Geocoding aus Stage-Koordinaten | ~50 LoC + externes API | Automatisch | Latenz, API-Key, Komplexität |
| **Region weglassen für #154**, separates Folge-Issue | 0 LoC | Sauberer Cut | Hero ist optisch unvollständig |

**Tech-Lead-Empfehlung: 4.** Region weglassen, Hero zeigt nur Name + Zeitraum + Stats. Region als eigenes Sub-Issue im Epic #135 anlegen. Begründung: alle 3 anderen Wege sprengen den Scope oder produzieren Halbgares. Issue-Body verlangt zwar Region — aber ein Hero ohne Region ist immer noch nützlich, mit kryptischen avalanche-Codes nicht.

### 2. „Aktive Etappe" — Vier Zustände

Je nach Trip-Status muss die Kachel eine sinnvolle Information zeigen:

| Trip-Status | Kachel-Text |
|---|---|
| `planned` (Start in Zukunft) | „Trip startet in X Tagen" |
| `active` (heute = Stage X) | „Tag X/Y · <Stage-Name>" |
| `paused` | „Pausiert — Tag X war zuletzt aktiv" oder schlicht „Pausiert" |
| `archived` | „Beendet — vor X Tagen" |

Pure-Function `getActiveStageDisplay(trip, now)` → String. Nutzt bestehende `deriveTripStatus` aus #153.

### 3. „Nächstes Briefing" — woher?

Trip hat `report_config.morning_time` (z.B. „07:00:00") und `evening_time` (z.B. „18:00:00") + `enabled`-Flag. Logik:

- Wenn `enabled === false` → „Briefings deaktiviert"
- Sonst: Bestimme nächsten Zeitpunkt (morning_time heute > now → heute morning; sonst evening heute > now → heute evening; sonst morgen morning)
- Anzeige als Tageszeit, kombiniert mit relativer Angabe („heute, 18:00", „morgen, 07:00")

Pure-Function `getNextBriefing(trip, now)` → `{ when: Date, label: string }`.

### 4. „Tage bis Start" — was tun bei laufendem Trip?

Pragmatisch: Label-Wechsel je nach Phase:
- `now < first stage` → „in X Tagen" (positiv)
- `now innerhalb` → „läuft seit Tag X" (Trip-Status active)
- `now > last stage` → „beendet vor X Tagen"
- `archived` → „seit X Tagen archiviert"

Pure-Function `getDaysLabel(trip, now)` → String.

### 5. Reaktivität nach Status-Wechsel

Wenn der User in #153 auf „Pausieren" klickt, ändert sich `trip.paused_at` reaktiv. Der Hero muss diese Änderung mit-rendern (Stat-Kachel „Aktive Etappe" wechselt zu „Pausiert"). Trip ist bereits in `$state` in `+page.svelte` aus #153 → Svelte 5 macht das automatisch.

### 6. LoC-Budget

Schätzung:
- `tripHero.ts` Pure-Functions: ~80 LoC (5 Funktionen + Hilfsfunktionen)
- `tripHero.test.ts` Unit-Tests: ~120 LoC (mind. 15 Tests für 4 Trip-Phasen × 3 Stat-Kacheln)
- `TripHero.svelte` Komponente: ~80 LoC (4 Bereiche: H1, Zeitraum, 3 Stat-Kacheln)
- `TripTabs.svelte` Edit: +5 LoC (Hero im Overview-Tab einbauen, Placeholder weg)
- `+page.svelte` Edit: +2 LoC (trip an TripTabs durchreichen)
- `index.ts` Edit: +1 LoC (Barrel)
- `e2e/trip-detail-hero.spec.ts`: ~80 LoC (8-10 E2E-Tests für ACs)
- **Summe: ~370 LoC** → Override auf 400 nötig (analog zu #153).

### 7. Tab-Mit-Trip-Prop — Cleaner Schnittstellen-Aufdrösel

Bisher: `TripTabs` kennt `trip` nicht. Mit Hero im Overview-Tab muss TripTabs entweder:
- (a) `trip`-Prop bekommen und an Hero durchreichen, ODER
- (b) Hero als Slot/Snippet im Parent gerendert werden, TripTabs bleibt trip-frei.

**Tech-Lead-Empfehlung: (a).** TripTabs hat schon `badges`-Prop für Tab-spezifische Daten. `trip` ist die Quelle für mehrere Tab-Inhalte (#156 Höhenprofil im Overview, #158 Wetter-Metriken im Weather-Tab, #189 Vorschau im Preview-Tab). Trip-Prop einmal durchgereicht spart später viele Snippet-Konstruktionen. Single-Source-Pattern.

### 8. Cockpit-Code-Duplikat? (analog zu #153)

`+page.svelte:25-37` macht ähnliche Cockpit-Berechnungen (`activeTrip`, `todayStage`, `dayIndex`). Versuchung: gemeinsame Util-Funktion teilen.

**Tech-Lead-Empfehlung: NICHT konsolidieren.** Cockpit-Logik ist über mehrere Trips (`(data.trips as Trip[]).find(...)`), Trip-Hero ist über genau einen Trip. Semantik unterschiedlich, würde Util-Funktionen-Signatur vermurksen. Eigenständige Pure-Functions im `lib/utils/tripHero.ts`, Cockpit-Refactor als separates Tech-Debt-Ticket (Konsolidierung von `getTripStatus` + Stage-Date-Berechnungen).

### 9. Acceptance Criteria — Vorschau

Mindestens 15 ACs:
- AC-1..AC-3: Hero rendert H1, Zeitraum, 3 Stat-Kacheln in fester Reihenfolge.
- AC-4..AC-7: `getActiveStageDisplay` für alle 4 Trip-Status liefert korrekten String.
- AC-8..AC-10: `getNextBriefing` korrekt für „vor morning", „zwischen morning & evening", „nach evening".
- AC-11..AC-13: `getDaysLabel` korrekt für planned/active/archived.
- AC-14: Hero re-rendert reaktiv nach `trip.paused_at`-Setzen (ohne Reload).
- AC-15: Tab-Navigation aus Step 1 + Header aus Step 2 bleiben unberührt sichtbar.

## Open Items für Phase 2 / Phase 3

- **User-Frage:** Region weglassen (Empfehlung) — oder lieber „avalanche_regions[0] anzeigen falls vorhanden"?
- **Format-Frage:** Zeitraum als `11.–14. Mai 2026` (deutsche Konvention) oder `11. Mai 2026 – 14. Mai 2026`?
- **TestID-Inventar:** in Phase 3 (Spec) auflisten.
