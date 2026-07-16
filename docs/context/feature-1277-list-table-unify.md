# Context: Listen-Übersichten vereinheitlichen (#1277)

## Request Summary
`/trips` und `/compare` sollen auf dem Desktop dieselbe Tabellen-Darstellung
teilen (geteiltes `ListTable`-Organism) statt divergierender Layouts
(Trips = Tabelle, Compare = Kachel-Grid). PO-Entscheid 2026-07-16, ersetzt die
frühere Charter-§3-Vorgabe (Kachel-Grid) für die Desktop-Übersicht. Mobile
bleibt unverändert (Karten-Stapel für beide).

## Herkunft
- #1274 (Konsistenzfrage) → geschlossen, Befund: Divergenz war Design-Charter-
  Drift, kein fachlicher Unterschied.
- #1277 (dieses Issue) trägt die fertige Spec (`body-30`) inkl. AC-Liste,
  SOLL-Bildern und der kanonischen JSX-Referenz aus dem Claude-Design-Projekt.
- Cross-Links: #486 (Trips-Zeilenverhalten, Kebab-Menü — bleibt gültig, wird
  jetzt geteilt), #485 (Compare Kachel-Grid, Charter §3 v1.1 — wird für
  Desktop durch die Tabelle ersetzt).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` | Desktop-Bereich (`class="hidden desktop:block"`, Zeilen ~438-475) enthält die Grid-Tabelle inline — wird durch `ListTable`-Aufruf ersetzt. Mobile Card-Stack (Zeilen ~405-437) bleibt unverändert. |
| `frontend/src/routes/compare/+page.svelte` | Desktop-Bereich (Zeilen ~64-116) nutzt `CompareGrid` — wird durch `ListTable`-Aufruf ersetzt. Mobiler Kachel-Stack (Zeilen ~118-148) bleibt unverändert. |
| `frontend/src/lib/components/compare/CompareGrid.svelte` | Aktuelles Kachel-Grid für Compare-Desktop — entfällt für Desktop, kein Ersatz auf Mobile nötig (Mobile nutzt `CompareTile` direkt, nicht `CompareGrid`). Prüfen ob `CompareGrid` danach noch anderswo referenziert wird, sonst löschen. |
| `frontend/src/lib/components/compare/CompareTile.svelte` | Bleibt — trägt weiterhin Mobile-Kachelliste + Home-Kachel. NICHT anfassen. |
| `frontend/src/lib/components/compare/subscriptionHelpers.js` | `deriveStatusFromPreset`, `presetLocationsLabel`, `presetProfileLabel`, `presetTileScheduleLabel`, `relativeLastSent`, `presetChannels` — liefern die Spaltendaten für die Compare-`ListTable`-Columns. Wiederverwenden, nicht duplizieren. |
| `frontend/src/lib/components/compare/CompareKebab.svelte` | Bestehendes Overflow-Menü-Muster für Compare-Aktionen — als Vorlage/Wiederverwendung für `ListActionsMenu` prüfen statt Fork. |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus`, `tripStatus` — liefern Status für Trip-Spalten. |
| `frontend/src/lib/components/organisms/` | Bestehender Organism-Ordner (`index.ts` + mehrere `.svelte`) — kanonischer Zielort für ein neues `ListTable.svelte`. |
| `frontend/src/lib/components/atoms/{Card,Stat,Dot,Btn,Eyebrow}.svelte` | Bereits verwendete Atoms auf beiden Seiten — `ListTable` baut darauf auf, kein neues Atom nötig. |
| `frontend/src/routes/trips/issue_402.test.ts`, `issue_477_486.test.ts`, `bug_596.test.ts` | Bestehende Trips-Tests — `data-testid`/Selektoren müssen laut AC erhalten bleiben, wo vorhanden (`trip-card-*` bleibt mobil unverändert; Desktop-Selektoren ggf. neu über `ListTable`). |
| `frontend/src/routes/compare/__tests__/*.test.ts`, `frontend/src/lib/components/compare/__tests__/compare_list_*.test.ts` | Bestehende Compare-Tests, u. a. `compare_list_dead_components_removed.test.ts` (prüft schon auf entfernte Inline-Kacheln — Präzedenzfall für „keine tote Komponente liegen lassen"), `compare_list_kebab_actions.test.ts` (Overflow-Menü-Verhalten). |

## Kanonische Design-Referenz (aus Claude-Design-Projekt synchronisiert)

- `claude-code-handoff/issue-bodies/body-30-uebersicht-listen-tabelle.md` — verbindliche Spec inkl. AC-Liste, `ListTable`-API, Spalten-Definition pro Screen.
- SOLL-Bilder (bereits nach `.github/issue-assets/` gepusht, in #1277 eingebettet): `soll-uebersicht-listen-tabelle-trips.png`, `soll-uebersicht-listen-tabelle-compare.png`.
- JSX-Referenz **im Claude-Design-Projekt** (DesignSync, projectId `019dfcf4-1e69-73f2-b094-c19e157014a2`) aktuell — lokale Snapshots (`claude-code-handoff/current/jsx/{screen-trips,screen-compare-list,organisms}.jsx`) sind noch NICHT synchronisiert (JSX-Dateien sind Edit-Gate-geschützt, Sync erfolgt in der Implementierungsphase). Bei Bedarf per `DesignSync.get_file` erneut abrufen — Diff gegen lokale Version ist rein additiv (ListTable/ListTableRow/ListActionsMenu/ListNameCell, 159 neue Zeilen in `organisms.jsx`).

## Existing Patterns

- **`context`-Prop-Muster** (Trip/Compare-Teilung, CLAUDE.md-Pflicht): `shared/versand-tab.jsx`, `shared/layout-tab.jsx`, `shared/corridor-editor` nutzen bereits `context="route"|"vergleich"` für geteilte Organismen mit screen-spezifischen Daten. `ListTable` folgt demselben Prinzip, aber generischer: Fachlogik komplett über `columns`/`rowActions`-Props injiziert, kein `context`-Enum nötig.
- **Overflow-Menü statt Icon-Geschwader**: bereits etabliert bei Compare (`CompareKebab`) und im JSX-Vorbild für Trips (#486) — `ListActionsMenu` verallgemeinert dieses Muster.
- **Ganze Zeile klickbar → Detail**: bereits für die aktuelle Trips-Tabelle implementiert (`onclick={() => goto(...)}` auf der Zeile) — Muster wird für Compare übernommen (aktuell nur Kachel-Klick).

## Dependencies
- Upstream: `ComparePreset`/`Trip`-Typen (`$lib/types.js`), Status-Ableitung (`tripStatus.ts`, `subscriptionHelpers.js`).
- Downstream: Playwright-/Vitest-Tests (s.o.), ggf. `data-testid`-Konsumenten in E2E-Suiten außerhalb der gelisteten Dateien (Grep vor Implementierung empfohlen).

## Existing Specs
- Kein `docs/specs/modules/`-Eintrag für die Listen-Übersichten selbst gefunden — wird in Phase 3 (`/30-write-spec`) neu angelegt.

## Risks & Considerations
- **Test-Bruch**: Mehrere bestehende Tests prüfen aktuell explizit Tabellen-Markup bei Trips (`grid-template-columns`) bzw. Kachel-Markup bei Compare (`compare-tile-*`, `CompareGrid`) — beim Umbau müssen betroffene Tests aktualisiert (nicht nur grün gebogen) werden, siehe Test-Politik (Kern-Schicht 100% grün, veraltete Tests löschen statt liegenlassen).
- **CompareGrid Verwaisung**: nach Umbau ggf. ungenutzt — vor Löschen prüfen, ob noch andere Konsumenten existieren (z. B. Home-Kachel-Vorschau).
- **Konsistenz-Anspruch aus CLAUDE.md** ("Trip/Ortsvergleich-Code-Teilung"): `ListTable` MUSS die einzige Tabellen-Implementierung sein — kein Fork je Screen (deckt sich mit AC aus body-30).
- **Mobile darf nicht angefasst werden** — beide AC-Listen und CLAUDE.md-Prinzip sind hier deckungsgleich; Playwright-Mobile-Suiten (`compare_list_mobile_chrome.test.ts`) sind ein harter Regressions-Fang.
