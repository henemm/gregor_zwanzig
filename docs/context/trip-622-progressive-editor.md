# Context: Neue Tour anlegen — Progressive Tab Editor (#622) + Waypoint-Editor-Closeout (#585)

## Request Summary
Session "#622 + #585": (1) `/trips/new` vom alten 5-Schritt-Wizard auf einen **Progressive Tab Editor**
umbauen, der dieselben Tab-Komponenten wie der Trip-Bearbeiten-Flow wiederverwendet (Issue #622);
(2) den bereits implementierten, aber noch offenen Waypoint-Editor (#585) über das Design-Diff-Gate
abschließen.

## Stand der beiden Issues

### #585 — Waypoint-Editor 1:1 (CODE FERTIG, Issue offen)
- Commits `97b8746a` (feat) + `485a9b67` (Staging-Fixes F001/F002/F003) sind **auf origin/main** (= live/deploybar).
- Geänderte Dateien: `EtappenStrip.svelte`, `StageCard.svelte`, `WaypointCard.svelte`,
  `EditStagesPanelNew.svelte`, `TripEditView.svelte`, `frontend/src/lib/types.ts` (+ Spec).
- 26 Tests grün. Issue trägt Label `design-compliance` → `pre_issue_close_design_gate.py` **blockiert
  den Close**, solange kein `docs/artifacts/<workflow>/design-diff-J-waypoint-editor-etappen-tab.json`
  mit `"passed": true` existiert. Dieses Artefakt fehlt aktuell.
- Offene Frage: ursprünglicher Reopen-Trigger war 51,5 % Pixel-Diff (vor der Rework). Nach Rework neu
  messen — könnte PASS sein oder dokumentierte SOLL-/Daten-Divergenz (bekanntes Muster, siehe Memory
  `feedback_design_fidelity_1to1.md` / `feedback_no_threshold_manipulation.md`).

### #622 — Progressive Tab Editor (Slice 1 ✅ LIVE, Slice 2 ✅ LIVE, Slice 3 ✅ LIVE)

#### Slice 1 (2026-06-07, Commit 11edbfe7)
- Spec: `docs/specs/modules/issue_622_trip_new_progressive_editor.md` (9 ACs, PO-freigegeben 2026-06-06).
- **✅ LIVE:** Shell + Route-Tab + Etappen-Tab (Create-Modus) + Wetter/Zeitplan/Alerts-Reuse + Speichern (POST). ACs 1–4, 6–8 implementiert.
- Blocker #587/#616/#617 waren live.

#### Slice 2 (2026-06-08, Issue #658)
- Spec: `docs/specs/modules/issue_658_trip_new_wegpunkte_tab.md` (8 ACs, PO-freigegeben 2026-06-07).
- **✅ LIVE (2026-06-08):** Optionaler Wegpunkte-Tab mit eingebettetem `EditStagesPanelNew` (embedded, kein PUT) + Persistenz der bearbeiteten Wegpunkte in `buildCreateTripPayload`.
- Schließt AC-5 von #622 + behöbe stille Datenlücke (Wegpunkte wurden vorher verworfen).

#### Slice 3 (2026-06-08, Issue #661)
- Spec: `docs/specs/modules/issue_661_trip_new_mobile.md` (9 ACs, PO-freigegeben 2026-06-08).
- **✅ LIVE (2026-06-08):** Mobile-Parität für `/trips/new` (≤899px, CSS-only responsive).
  App-Leiste statt Breadcrumb, gestapelte Route-Eingabe mit Floating-CTA, Etappen als vertikale Karten
  mit Bottom-Sheet-Namenseingabe, scrollbare TabBar, Lock-Tab→Toast (statt Flash).
- Schließt AC-9 (Mobile) von #622. **#622-Paket komplett: alle 9 ACs abgeschlossen.**

#### Design-Quellen
1:1-Quellen im Repo: `docs/design-requests/trip-anlegen-2026-06-06/`
  (`Gregor 20 - Trip anlegen.html`, `screen-trip-new-v2{,-mobile}.jsx`).

## Reuse-Landkarte (#622)
| Komponente | Pfad | Status |
|---|---|---|
| Etappen & GPX | `edit/EditStagesPanelNew.svelte` | ✅ reuse (GPX-pro-Etappe + Datums-Automatik existiert) |
| Wetter | `trip-detail/WeatherMetricsTab.svelte` | ⚠️ braucht `onChannelsChange`-Output |
| Zeitplan | `edit/EditReportConfigSection.svelte` | ✅ akzeptiert `weatherChannels`-Prop (#617) |
| Alerts | `alert-rules-editor/AlertRulesEditor.svelte` | ✅ reuse |
| Waypoint-Subkomponenten | `trip-detail/waypoints/*` | ✅ reuse, brauchen `embedded`-Einbettung |
| **Shell + Lock-State** | — | ❌ **NEU zu bauen** |
| **Route-Tab (create)** | — | ❌ **NEU** (Name/Region/Startdatum) |

## Backend
- `POST /api/trips` (Neu) + `PUT /api/trips/{id}` existieren.
- `POST /api/gpx/parse?stage_date=&start_hour=` parst GPX **pro Etappe** → `stage.Waypoints`.
- Go-`Stage` hat **kein** rohes GPX-Feld (nur `Waypoints`) — die Spec-Sorge „Backend GPX pro Etappe"
  ist **entschärft**: GPX wird heute schon pro Etappe geparst, abgeleitete Waypoints persistiert.
  → Voraussichtlich **kein Backend-Schema-Change** nötig.

## Risiken & Considerations
- **Scope/LoC:** #622 ist groß (Shell + Lock-State + Route-Tab + Kanal-Binding + 9 ACs inkl. Mobile).
  Wahrscheinlich > 250 LoC → LoC-Override (PO-Permission Pflicht, Memory `feedback_no_loc_override...`)
  oder Mobile (AC-9) als Folge-Slice.
- **Breaking-change:** alter Wizard (`TripWizardShell`) wird deprecated/entfernt — kein paralleler Pfad.
- **#585-Gate:** evtl. SOLL-Divergenz → kein Threshold-Manipulieren, nur dokumentierter Override.

## Existing Specs
- `docs/specs/modules/issue_622_trip_new_progressive_editor.md`
- `docs/specs/modules/issue_585_waypoint_editor_design.md`
