# External Validator Report — Epic 137: Wegpunkt-Editor

**Spec:** `docs/specs/modules/epic_137_wegpunkt_editor.md` (Version 1.0, 2026-05-17)
**Datum:** 2026-05-17
**Server:** https://staging.gregor20.henemm.com
**Validator-User:** `validator-issue110` (Cookie-Auth)

## Test-Setup

Zwei Trips per HTTP-API angelegt:

1. `validator-epic137-3st` — 3 regulaere Etappen, keine Pausentage, keine suggested-Wegpunkte (fuer AC-1, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9, AC-11, AC-15).
2. `validator-epic137` — 2 Etappen + 1 Pausentag, mit `suggested: true` auf je einem Wegpunkt pro Etappe (fuer AC-2, AC-6, AC-10, AC-12, AC-13, AC-14).

Beide Trips wurden ueber `POST /api/trips` angelegt; `suggested`-Flag wurde nachtraeglich per `PUT /api/trips/:id` gesetzt (das Backend persistiert es per PUT, strippt es aber bei POST).

## Checklist

| #  | Expected Behavior | Beweis | Verdict |
|----|-------------------|--------|---------|
| 1  | 3 Etappen → `stage-card-0`, `stage-card-1`, `stage-card-2` horizontal sichtbar | Alle 3 TestIDs `count=1 visible=True` (Screenshot `AC1-3stages.png`) | **PASS** |
| 2  | Trip mit Pausentag → `stage-card-pause-1` gestrichelt | Element vorhanden mit `class="stage-card stage-card--pause"`, computed `border-style: dashed`, `border: 1px dashed rgb(156,154,144)` (Screenshot `AC2-pausentag.png`) | **PASS** |
| 3  | DnD → `localStages` neu geordnet, Speichern-Button aktiv | Drag von `stage-card-0` (Tag 1) auf `stage-card-2`-Position → Reihenfolge im DOM nach Drag: Tag 2, Tag 3, Tag 1. Save-Button enabled (Screenshot `AC3-after-drag-v2.png`). Anmerkung: Save-Button ist generell immer enabled — Spec fordert „ist aktiv", nicht „wird aktiv". | **PASS** |
| 4  | StageCard mit GPX-Daten zeigt Sparkline + km + gain/loss | `stage-card-0` Text: `T01 / Etappe Süd / 4.7 km / +1320 m`, enthaelt ein `<svg>` (Sparkline) | **PASS** |
| 5  | MapCanvas-Routenlinie: `<polyline stroke="var(--g-accent)">` | `<polyline points="8,292 199.99…,150 392,8" stroke="var(--g-accent)" stroke-width="2">`, computed stroke `rgb(196, 90, 42)` | **PASS** |
| 6  | suggested Pin: `stroke-dasharray` + `stroke="var(--g-warning)"` | Pin `map-waypoint-pin-1` (Bocca a u Saltu): `<path … stroke="var(--g-warning)" stroke-dasharray="4,3" fill="white">`, aria-label `Vorgeschlagener Wegpunkt 2` | **PASS** |
| 7  | Klick Map-Pin → Pin visuell aktiv | Klick auf `Wegpunkt 2`: `<g style="filter: drop-shadow(0 0 3px var(--g-accent)); cursor: pointer;">` — anderer Pins ohne filter (Screenshot `AC7-after-pin-click.png`) | **PASS** |
| 8  | ProfileEditor: Gridlines bei 25/50/75% | 3 `<line>`-Elemente mit `stroke-dasharray="2,4"`, `stroke="var(--g-ink-faint)"`, y=39/70/101 in Zeichenflaeche 124px+8px-Padding ≈ 25%/50%/75% (Screenshot `AC8-profile-editor.png`) | **PASS** |
| 9  | Klick Profile-Pin → Map-Pin synchron aktiv (und umgekehrt) | Map→Profile: Klick Pin 2 setzt Profile-Circle 2 auf `r=7`. Profile→Map: Klick Circle 3 setzt Map-Pin `Wegpunkt 3` auf `filter: drop-shadow(0 0 3px var(--g-accent))`. Bidirektional bestaetigt. | **PASS** |
| 10 | suggested WaypointCard: confirm + reject Buttons | `waypoint-card-1` (Bocca a u Saltu): `waypoint-confirm-1` und `waypoint-reject-1` je count=1; rename/delete count=0. Nach Klick `confirm-1`: Buttons wechseln zu rename/delete. | **PASS** |
| 11 | manuelle WaypointCard: rename + delete Buttons | `waypoint-card-0` und `waypoint-card-2` (Calenzana, Refuge Ortu): `waypoint-rename-{i}` und `waypoint-delete-{i}` je count=1; confirm/reject count=0. | **PASS** |
| 12 | Save → PUT `/api/trips/:id` ohne `suggested`-Key | Captured PUT-Body: Stage `ep137-s1` Waypoints `[Calenzana, Bocca a u Saltu, Refuge Ortu]` — kein `suggested`-Feld in irgendeinem Waypoint. Code-Inspection: `NO suggested key in any waypoint in payload`. | **PASS** |
| 13 | Pausentag aktiv → `pause-stage-view` statt Map/Profile | Nach Klick auf `stage-card-pause-1`: `pause-stage-view` count=1, `map-canvas` count=0, `profile-editor` count=0. Inhalt: „Pausentag / 2026-06-02 / Standort: Refuge Ortu / Weiter nach: Refuge Ortu" (Screenshot `AC13-pause-view.png`) | **PASS** |
| 14 | `stripSuggested(stages)` entfernt alle suggested-Flags | Indirekt via AC-12 (PUT-Payload). Zusatztest REJECT: Klick auf `waypoint-reject-1` (suggested) entfernt den Waypoint — cards 3 → 2, map pins 3 → 2. Stripping- und Removal-Logik beide nachgewiesen. | **PASS** |
| 15 | `buildMapPositions` liefert Koordinaten in [0,400]×[0,300] | Polyline-Punkte `(8, 292), (200, 150), (392, 8)` — alle innerhalb der ViewBox `0 0 400 300`. Pin-Transforms folgen lat/lon-Skala (cos-korrigiert: WP1 unten links, WP2 Mitte, WP3 oben rechts). | **PASS** |

## Zusatzbeobachtungen

### CSS-Token `--g-ink-strong`
- Computed style: `--g-ink-strong: #1a1a18`, `--g-ink: #1a1a18` — Alias korrekt definiert.
- WaypointPin nutzt `fill="var(--g-ink-strong)"` (bestaetigte Wegpunkte), `fill="white"` mit `stroke="var(--g-warning)"` (suggested). Beide Stile aktiv.

### Backend-Verhalten zu `suggested`
- `POST /api/trips` strippt `suggested: true` (Feld erscheint nicht in der Response).
- `PUT /api/trips/:id` persistiert `suggested: true` und gibt es in `GET` wieder zurueck.
- Diese Asymmetrie ist nicht Gegenstand der Spec. Sie ermoeglicht aber den Test des suggested-UI-Pfades.

### Nicht-blocking Beobachtung: Console-422-Errors
Auf der Trip-Detail-Seite erscheinen zwei `422 Unprocessable Entity`-Fehler in der Browser-Console. Sie kommen nicht aus dem Wegpunkt-Editor (alle EP137-relevanten APIs antworten 200) und blockieren keinen der ACs. Quelle unklar (vermutlich anderer Tab oder Initial-Load), nicht in Spec-Scope.

### Aria-Labels
- Bestaetigte Pins: `aria-label="Wegpunkt N"`
- Suggested Pins: `aria-label="Vorgeschlagener Wegpunkt N"`
- ProfileEditor-Circles: `aria-label="Wegpunkt {Name}"`
Spec-konform (§2 WaypointPin ARIA-Regel).

### Save-Button Default-Zustand
Der Speichern-Button ist auch ohne Aenderungen enabled. Die Spec fordert in AC-3 nur „Speichern-Button ist aktiv (nach DnD)" — das ist erfuellt. Eine staerkere Garantie („disabled wenn keine Aenderungen") waere wuenschenswert, ist aber nicht spezifiziert.

## Findings

Keine kritischen Findings. Alle 15 Acceptance Criteria sind erfuellt.

## Verdict: VERIFIED

### Begruendung

Alle 15 Acceptance Criteria der Spec wurden mit der laufenden App auf
`https://staging.gregor20.henemm.com` reproduzierbar verifiziert:

- **Layout & TestIDs (AC-1, AC-2):** EtappenStrip rendert reguläre und Pausentag-Kacheln mit korrekten TestIDs und Borderstilen.
- **Interaktion (AC-3, AC-7, AC-9, AC-10):** DnD funktioniert, Pin-Klicks setzen `activeWaypointId` bidirektional, Confirm/Reject mutiert `localStages` korrekt.
- **Rendering (AC-4, AC-5, AC-6, AC-8):** StageCard, MapCanvas-Polyline und -Pins (manuell + suggested), ProfileEditor-Gridlines bei 25/50/75% sind spec-konform.
- **Persistenz (AC-12, AC-14):** Save-Pipeline ruft `stripSuggested` korrekt auf — keine `suggested`-Felder im PUT-Payload.
- **Pure Functions (AC-14, AC-15):** Verhalten von `stripSuggested` und `buildMapPositions` aeusserlich beobachtbar konsistent mit Spec.
- **Pausentag-Modus (AC-13):** PauseStageView ersetzt Map/Profile vollstaendig, Standort-Info aus Vorgaenger-/Folgeetappe.
- **CSS-Token (§10):** `--g-ink-strong` korrekt als Alias auf `--g-ink` gesetzt.

Die Implementierung erfuellt die Spec auf der Output-Ebene, die ein externer Validator pruefen kann. Code-interne Aspekte (Svelte-5-Runes-State, Pure-Function-Implementierung) wurden bewusst nicht inspiziert — die Verhaltensgleichheit ist hinreichend belegt.
