---
entity_id: mobile_stages_tab_listen_only
type: feature
created: 2026-09-23
updated: 2026-10-03
status: implemented
version: "1.0"
tags: [mobile, usability, frontend, trip-detail, stages, atomic-design]
---

<!-- Mobile-Usability-Audit (WebKit iPhone 13, 390×844): Fix-Paket 1.
     Verbindlicher Soll: docs/design-requests/mobile_usability_stages_soll.md
     (ALLE PO-Entscheide F1–F7 vom 2026-09-22, Status „bereit für Spec").
     Mockup: docs/design-requests/mobile-usability-stages-soll.html
     Audit-Belege: frontend/test-results/mobile-usability/report-iphone13.json
     (+ report-iphone13.md, Screenshots unter .../iphone13/).
     PO-Kernentscheid F5 (wörtlich): „Beides spielt unterwegs keine Rolle und
     niemand will das unterwegs auf dem Smartphone editieren." → Variante B:
     Karte + Höhenprofil entfallen auf Mobile ersatzlos. -->

# Mobile Usability Paket 1 — Etappen-Tab auf Mobile: Listen-only ohne Karte/Profil

## Approval

- [x] Approved (PO „approved", 2026-09-25; Design-Entscheide F1–F7 vom 2026-09-22)

## Purpose

Der Trip-Detail-Tab „Etappen & Wegpunkte" ist auf Mobile der schlechteste Screen
des Audits: 15 überstehende Elemente, 3 Clipps (Karte auf 34 px Höhe gekappt bei
scrollHeight 2944, Profil-Sheet abgeschnitten), horizontal scrollbarer
EtappenStrip (916 px Scrollbreite bei 278 px Sicht) und 15 Texte unter 11 px.
Die Spec ersetzt den mobilen Tab-Inhalt komplett: eine vertikale, sortierbare
Etappenliste (`StageCardM`) als einzige Darstellung — ohne Karte, ohne
Höhenprofil, ohne Sheet, ohne JS-Höhenmessung. Desktop (≥ 900 px) bleibt
1:1 beim #503/#585-Stand.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
  (mobiler Zweig: `.mobile-editor` + `mobileEditorHeightPx` + Mess-Effekte
  entfernen; Liste + Banner mounten)
- **File:** `frontend/src/lib/components/mobile/StageCardM.svelte` (NEU,
  Katalog-Komponente; Muster `docs/design/mobile/screen-trip-detail-mobile.jsx:192-234`)
- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
  (`.trip-h1` Mobile `--g-text-xl`, `.trip-h1-row` `min-width:0`/nowrap/Ellipsis)
- **File:** `frontend/src/lib/components/molecules/Stat.svelte`
  (`size="sm"`-Label-Minimum 11 px)
- **File:** `docs/design-system/COMPONENTS.md` (Katalog: `StageCardM` §4.5
  eintragen, §11-Erweiterungsprozess)

> **Schicht-Hinweis:** reine Frontend-/User-UI-Änderung (`frontend/src/...`,
> SvelteKit). Kein Go-API-, kein Python-Core-Anteil.

## Affected Files

| Datei | Änderung | Iteration |
|---|---|---|
| `frontend/src/lib/components/mobile/StageCardM.svelte` | NEU: vertikale Etappen-Karte (Griff 44px, Code/Datum mono 11px, Titel `--g-text-sm`, Stats mono 11px, `StagePill`, Pause-Variante, aufklappbare Wegpunkt-Zeilen F7) | 1 (Basis), 2 (Wegpunkt-Zeilen) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Mobile-Zweig: `.mobile-editor`/`ProfileSheetEmbedded`/`MapCanvas`/`StageSelectSheet` nicht mehr rendern; stattdessen Desktop-Hinweis-Banner + `StageCardM`-Liste (SortableList/DragHandle, geteilt ADR-0024); Cascade-Banner mobil inline (F2); Mess-`$effect`s und Konstanten entfernen | 1 (Layout+Banner), 2 (Aufräumen) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | `.trip-h1` 38px → `--g-text-xl` (20px) ≤899px; `.trip-h1-row` `min-width:0` + nowrap + Ellipsis; Stift 44px | 1 |
| `frontend/src/lib/components/molecules/Stat.svelte` | `size="sm"`-Label 9px → 11px (`--g-text-xs`) | 1 |
| `docs/design-system/COMPONENTS.md` | `StageCardM` als Molecule eintragen (§11-Prozess) | 1 |
| `frontend/src/lib/components/edit/StageSelectSheet.svelte` | Mobil-Entfernung verifizieren (kein mobiler Mount mehr); Datei selbst evtl. unverändert | 2 |

## Estimated Scope

- **LoC:** Iteration 1 ~200 · Iteration 2 ~150 (gesamt ~350)
- **Files:** 5–6
- **Effort:** medium

> **Scope-Guard:** `max_loc_delta: 250` pro Iteration. Aus diesem Grund sind
> die Wegpunkt-Zeilen (F7) und das Aufräumen (StageSelectSheet-Mobil-Pfade,
> Cascade-Inline) in Iteration 2 ausgelagert. Nicht beides in einem Commit.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SortableList` / `DragHandle` (`frontend/src/lib/components/shared/dnd/`) | component | Geteilte Sortier-Infrastruktur (ADR-0024, #1272 griff-only) — `StageCardM`-Liste nutzt sie, nichts Neues bauen |
| `computeArrivalTimes` / `activityToSpeed` (`frontend/src/lib/utils/naismith.ts`) | function | ETA-Berechnung für Wegpunkt-Zeilen (F7), bestehende Nutzung im Panel |
| `isPauseStage` (`frontend/src/lib/components/shared/wizardHelpers.ts`) | function | Pause-Erkennung für Karten-Variante (bereits genutzt) |
| `Eyebrow`, `Pill`, `Btn` (`$lib/components/atoms`) | component | Listen-Header, Risk-Pills, „+ Etappe"-Wahl (F3: Etappe/Pausentag) |
| `TripTabs.svelte` (mobiler Tab-Band-Zweig) | component | Paket 2 (`mobile_tab_leisten_mtabar`) — unabhängig, aber gleicher Screen |
| Design-Doc `docs/design-requests/mobile_usability_stages_soll.md` | doc | Verbindlicher Soll inkl. aller PO-Entscheide F1–F7 |

## Implementation Details

```
[Mobile-Zweig EditStagesPanelNew, Iteration 1]
if (viewport <= 899px):
  <DesktopHintBanner />            <!-- neutral: --g-card-alt, --g-rule, Info-Icon, statisch -->
  <ListenHeader eyebrow="N ETAPPEN · ZIEHEN ZUM SORTIEREN" + "+ Etappe"-MBtn ghost />
  <SortableList items={stages} zoneClass="stage-cardm-list">
    <StageCardM stage active={…} expanded={…} />   <!-- pro Etappe -->
  </SortableList>
else:
  [bisheriger Desktop-Zweig unverändert: EtappenStrip + MapCanvas 440px + ProfileEditor + Grid 1fr/360px]

[Entfernt auf Mobile]
.mobile-editor, mobileEditorHeightPx, MOBILE_EDITOR_MIN_HEIGHT_PX,
BOTTOM_NAV_HEIGHT_PX, getSafeAreaPx()-Sonde, beide Measure-$effect:s,
cascade-Platzierungs-Effekt (F2: Banner inline), ProfileSheetEmbedded,
StageSelectSheet, MapCanvas (kein dynamischer Import mehr im mobilen Pfad)
```

- **Desktop-Hinweis (F5, entschieden):** Copy „Karte & Höhenprofil sind am
  Desktop verfügbar. Das Gesamt-Höhenprofil bleibt im Übersichts-Tab."
  **Neutral und statisch** — `--g-card-alt`-Hintergrund, `--g-rule`-Rand,
  Info-Icon in `--g-ink-3`, kein Accent, nicht wegklappbar (Begründung:
  reine Info ohne CTA; Charter §6, AP-015).
- **StageCardM:** Katalog-Namen `StageCardM`; 44px-DragHandle links (griff-only,
  #1272); Tap auf den Karten-Body klappt Wegpunkt-Zeilen auf/zu (F7,
  Iteration 2: Nummern-Kreis mono, Name, „{Höhe} m · ETA {Zeit}", Chevron).
- **Titel (F1):** `.trip-h1 { font-size: var(--g-text-xl) }` in
  `@media (max-width: 899px)`; `.trip-h1-row { min-width: 0; flex-wrap: nowrap }`,
  Titel einzeilig mit Ellipsis, Stift-Button 44px `flex-shrink: 0`.
- **Typo-Regel (AP-017):** kein Text im mobilen Tab unter 11px
  (`Stat size="sm"`-Label, StageCardM-Labels, Listen-Header `--g-text-xs`).

## Expected Behavior

- **Input:** Trip mit N Etappen (inkl. Pausentagen) und Wegpunkten, mobiler
  Viewport (< 900px), Deep-Link `?tab=stages`.
- **Output:** Vertikal scrollbarer Tab ohne horizontale Scrollbereiche; Liste
  sortierbar per Griff (Touch + Tastatur); Wegpunkte je Etappe aufklappbar.
- **Side effects:** Speichern (Drag-Reihenfolge, Kaskaden-Antwort) läuft über
  den bestehenden `saveController` unverändert; kein neuer Schreibpfad.

## Acceptance Criteria

- **AC-1:** Given der stages-Tab auf einem mobilen Viewport (< 900px, z.B.
  390×844) / When die Seite geladen wird / Then enthält der Tab-Inhalt kein
  Karten-, Profil-, Sheet- oder MapControl-Element (kein
  `data-testid="map-canvas"`, kein `profile-sheet-host` im DOM) und kein
  Leaflet-Import läuft (Netzwerk-/Bundle-Check).
  - Test: Playwright Mobil-Viewport — DOM-Queries auf `map-canvas` und
    `profile-sheet-host` sind leer; kein Tile-Request zu opentopomap.org.

- **AC-2:** Given derselbe Tab / When er gerendert wird / Then existiert
  oberhalb der Liste ein neutraler Hinweis („Karte & Höhenprofil sind am
  Desktop verfügbar…") ohne Accent-Rahmen, ohne Schließen-Aktion.
  - Test: Playwright — Banner-Text sichtbar; Banner hat kein
    Accent-Element (kein 3px-Akzent-Border, kein Schließen-Button).

- **AC-3:** Given eine Tour mit ≥ 4 Etappen inkl. einem Pausentag / When der
  Nutzer die Liste betrachtet / Then sieht er vertikale Karten mit Drag-Griff,
  Risk-Pill, Distanz/Höhen/WP-Angaben und eine abgesetzte Pause-Karte —
  horizontal ist nichts scrollbar (ScrollWidth = ClientWidth je Zeile).
  - Test: Playwright — Griff je Karte ≥ 44×44px (BoundingBox); Pausentag-Karte
    unterscheidbar (dashed); kein Element ragt über die Viewport-Breite
    (Audit-Check aus report-iphone13.json wiederholt sich nicht).

- **AC-4:** Given die Liste / When der Nutzer am Griff zieht (oder per
  Tastatur: Space/Enter, dann Pfeiltasten) / Then ändert sich die Etappen-
  reihenfolge und wird über den bestehenden saveController persistiert.
  - Test: Playwright DragHandle-Tap + Tastaturpfad; Reihenfolge nach Reload
    stabil; keine ▲/▼-Pfeile vorhanden (#848).

- **AC-5:** Given eine Etappe mit Wegpunkten / When der Nutzer die Etappen-
  Karte antippt / Then klappen die Wegpunkt-Zeilen auf (Nummer, Name, Höhe,
  ETA) und das Chevron dreht; zweiter Tap klappt zu. (Iteration 2)
  - Test: Playwright — `wp-rows` wechselt sichtbar; Zeilen zeigen Höhe/ETA;
    Pause-Karten haben keine Zeilen.

- **AC-6:** Given ein langer Tourname / When die Seite mobil rendert / Then
  steht der Titel einzeilig in 20px mit Ellipsis (keine Überstehung, kein
  Umbruch) und alle Labels im Tab sind ≥ 11px.
  - Test: Playwright — `.trip-h1` computed font-size 20px;
    `scrollWidth <= clientWidth` für `.trip-h1-row`; kein Text-Node im Tab
    mit font-size < 11px (Audit-Befund „15 Texte < 11px" geschlossen).

- **AC-7:** Given ein Deep-Link `/trips/<id>?tab=stages` / When die Seite
  geladen wird / Then rendert der Tab ohne Mess-Flickern und ohne
  nachträgliche Höhen-Sprünge (kein Resize-Kaskaden-Layout).
  - Test: Playwright — stabiler Screenshot vor/nach 1s; keine
    Layout-Shifts > 1px im Tab-Inhalt.

- **AC-8:** Given ein Datum einer Etappe wird geändert (Kaskaden-Rückfrage) /
  When die Rückfrage erscheint / Then steht sie mobil inline direkt über der
  betroffenen Etappen-Karte — nicht `position:fixed`, nicht über der BottomNav.
  (Iteration 2, F2)
  - Test: Playwright — Banner-Position innerhalb des Listen-Containers;
    kein `position:fixed` im computed style.

- **AC-9:** Given Desktop-Viewport (≥ 900px) / When derselbe Trip geöffnet
  wird / Then ist der Tab unverändert: EtappenStrip, Karte 440px, Profil,
  Wegpunkt-Sidebar — Pixelstand der #585-Fidelity.
  - Test: Playwright Desktop-Viewport — Screenshot-Diff gegen den
    Fidelity-Baseline-Stand ohne Abweichung im Editor-Bereich.

- **AC-10:** Given der Übersichts-Tab auf Mobile / When er geöffnet wird /
  Then bleibt das Gesamt-Höhenprofil (`FullProfile`) unverändert erreichbar.
  - Test: Playwright — Profil-SVG im Übersichts-Tab sichtbar und tippbar.

## Known Limitations

- Auf Mobile gibt es keine Routen-Visualisierung mehr (PO-Entscheid F5);
  Wegpunkte können mobil nur betrachtet, nicht auf Karte gesetzt/verschoben
  werden (Desktop-Hinweis weist darauf hin).
- Kein Etappen-Profil mit Wegpunkt-Dots auf Mobile (Gesamt-Profil im
  Übersichts-Tab bleibt).
- `StageSelectSheet` bleibt vorerst als Datei bestehen (Desktop-Nutzung
  prüfen und separat entfernen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (verbindliche Design-Entscheid, Dokumentation im
  Design-Request)
- **Rationale:** PO-Entscheid F5 vom 2026-09-22 (Variante B), wörtlich:
  *„Beides spielt unterwegs keine Rolle und niemand will das unterwegs auf
  dem Smartphone editieren."* Die verbindliche #503-Entscheidung („Karte
  gehört in den Etappen-Tab", 2026-06) gilt unverändert für Desktop/Editor
  (≥ 900px); als Mobile-Präzisierung (Vorschlag, mit dieser Spec an
  `docs/design-requests/issue_503_ANTWORT.md` einzureichen): *„Auf Mobile
  (< 900px) entfallen Karte und Höhenprofil im Etappen-Tab ersatzlos;
  stattdessen zeigt der Tab die vertikale Etappenliste mit aufklappbaren
  Wegpunkt-Zeilen und einem neutralen Hinweis. Das Gesamt-Höhenprofil bleibt
  mobil im Übersichts-Tab. Desktop bleibt 1:1 beim #503-Layout."* —
  Charter-Basis §4 (dokumentierte Mobile-Ausprägung). Soll-Referenz:
  `docs/design-requests/mobile_usability_stages_soll.md` (F1–F7 entschieden),
  Mockup `docs/design-requests/mobile-usability-stages-soll.html`.

## Changelog

- 2026-09-23: Initial spec created (nach Design-Doc-Stand „PO-Entscheide
  vollständig, bereit für Spec")
- 2026-10-03: Umsetzung abgeschlossen und validiert. Iteration 1 (d05f7cbc):
  StageCardM-Baustein + Katalog v1.4, Listen-only-Mobile-Zweig, Desktop-Hinweis,
  Titel-Fix F1, Stat-Label 11px — Audit stages-Tab 15/2/15 → 4/1/0. Iteration 2
  (46137b8b): Wegpunkt-Zeilen aufklappbar (F7), Pause-Wahl am „+ Etappe" (F3),
  Cascade-Banner inline (F2), mobile JS-Höhenmessung + .mobile-editor entfernt,
  SortableList onDndReorderEnd + ADR-0024-Changelog. Cleanup (e2d2c41b):
  verwaiste Komponenten MapControl/ProfileSheetEmbedded/StageSelectSheet/
  EditorProfileSVG entfernt, Katalog v1.6. Validierung: E2E 8/8 +
  mobile-tab-bar 11/11 + stages/tabs 18/18, Unit 3134/0; Desktop-Pfade
  zeichen-identisch (AC-9 in jeder Iteration geprüft).
