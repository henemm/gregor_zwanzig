# Mobile Usability · Paket 1 — Trip-Detail-Tab „Etappen & Wegpunkte" (stages)

**Status:** Soll-Entwurf für PO-Abnahme · 2026-09-22 · **Mockup:** `docs/design-requests/mobile-usability-stages-soll.html`
**Bezug:** Mobile-Usability-Audit (WebKit, iPhone 13, 390×844) · #503 (Option B, verbindlich) · #585 (Editor live 1:1) · #1272 (Sortierung griff-only) · #963 (Map-First-Reorder) · ADR-0024 (geteilte SortableList)

---

## 1. Ausgangslage

Ist-Belege (lokale Audit-Artifacts, nicht im Repo versioniert):

- `frontend/test-results/mobile-usability/iphone13/trips_ma-alpen-x__stages.png` — stages-Tab, erster Viewport
- `frontend/test-results/mobile-usability/iphone13/trips_ma-alpen-x.png` — Übersicht-Tab zum Vergleich (gleicher Chrome)
- Befund-Zahlen aus dem Audit-Report: 15 überstehende Elemente im stages-Tab, 3 Clipps, horizontale Scrollbereiche, 15 Texte < 11 px.

| Befund | Messung (Audit) | Ursache im Code |
|---|---|---|
| Titel-Zeile `.trip-h1-row` ragt über | 319 px breit bei 278 px Sicht | `.trip-h1` hart 38 px (`TripHeader.svelte:223`), `.trip-h1-row` ohne `min-width: 0`, `flex-wrap: wrap` schiebt den Stift-Button in eine überstehende Zeile |
| Panel `.trip-detail-panel-stages` ragt über | 366 px bei 358 px Sicht | Inhalts-Container ohne `min-width: 0`-Kette; fixe 200-px-StageCards + Strip-Padding 14/40 |
| Etappen-Cards ragen über Container | Strip-Inhalt 916 px bei 278 px Sicht | `EtappenStrip.svelte` horizontal scrollbar, `StageCard.svelte` fix `width: 200px`, Strip-Padding `14px 40px` |
| Karte (`map-canvas`) auf 34 px Höhe gekappt (scrollHeight 2944!) | Clipp | `mobileEditorHeightPx`-JS-Berechnung (`EditStagesPanelNew.svelte:97-112`): gemessene Oberkante + BottomNav-Reservierung; Floor 200 px greift nicht, weil `available > 0` klein aber positiv ist — Leaflet rendert in die volle interne Höhe (2944 px), sichtbar bleiben 34 px |
| `profile-sheet-host` abgeschnitten | Clipp | Sheet-Höhen in Prozent-Snaps (`collapsed 56` / `peek 32%` / `half 55%` / `full 84%`, `ProfileSheetEmbedded.svelte:6`) relativ zum gekappten Editor-Container |
| `etappen-strip` horizontal scrollbar | 916 px Scrollbreite bei 278 px Sicht | Desktop-Strip 1:1 auf Mobile übernommen — 200-px-Karten × N Etappen + Pause-Gaps + „+ Etappe" |
| 15 Texte < 11 px | 9–10 px | `StageCard.svelte` 9-px-Labels, `EtappenStrip.svelte` 10-px-Eyebrow, `Stat size="sm"`-Labels 9 px (`TripHeader.svelte:182-188`), Map-Attribution 9 px |

Zwei strukturelle Beobachtungen aus dem Code, die über die Einzelbefunde hinausgehen:

1. **Zwei Etappen-Navigations-Achsen auf Mobile:** horizontaler `EtappenStrip` (Sortieren, Pause einfügen, aktivieren) UND `stage-switcher-pill` + `StageSelectSheet` (wechseln). Das #503-Soll-Bild mobil kannte den Strip noch nicht — es ersetzte ihn durch die StageSelectSheet. Der Ist-Code hat beide, beide überstehen.
2. **Die Kartenhöhe ist das teuerste Element der Seite:** JS-Messung mit Resize-/Orientation-Listenern, Safe-Area-Sonde, Cascade-Banner-Platzierungs-Effekt (drei gekoppelte `$effect`s, F001–F005-Kommentare) — alle nur deshalb, weil die Karte die „Restfläche" zwischen Chrome und BottomNav füllen soll. Der Clipp zeigt: Das Fundament wackelt.

## 2. Zielbild

Ein vertikal scrollender Tab-Inhalt ohne horizontale Scrollbereiche und ohne JS-Höhen-Messung:

```
[Tab-Leiste]                         ← Paket 2 (separater Soll)
[MapCard · Karte, feste Höhe]        ← max(240px, 40dvh), MapControl oben rechts
[ProfileSheetEmbedded · Snaps]       ← unter der Karte: collapsed/peek/half/full
[Etappen-Liste · vertikal, 4…N]      ← StageCardM, Drag-Griff, Pause, „+ Etappe"
```

Desktop bleibt unverändert (Strip + Grid 1fr/360px, #503-Layout).

## 3. Entscheidungen je Befund

### 3.1 Titel-Zeile (TripHeader, gilt seitenweit)

- `.trip-h1` auf Mobile: **38 px → `--g-text-xl` (20 px)** stufenlos per Media-Query (`max-width: 899px`), Tracking `--g-track-tight`. Begründung: einziger Skala-Sprung, der 38 px plausibel mobil skaliert (AP-017: nur `--g-text-*`-Token; Desktop bleibt `--g-text-3xl`-Nähe). `TOKENS.md §7` annotiert `--g-text-lg` (17 px) als „Mobile Page-Titles" — 20 px ist der Gegen-Vorschlag, weil der Trip-Name der Anker des Screens ist und lange Namen bei 17 px untergehen. **→ PO-Frage F1.**
- `.trip-h1-row`: `min-width: 0` + `flex-wrap: nowrap`, Titel `overflow: hidden; text-overflow: ellipsis` (einzeilig, kürzbar statt umbrechend-überstehend). Stift-Button fix 44×44 px rechts (`flex-shrink: 0`).
- `.header-left` hat bereits `min-width: 0` — die Kette bricht am `.trip-h1-row`, dort wird sie ergänzt.
- Stat-Labels (`ETAPPE`/`BRIEFING`/`START IN`): `<Stat size="sm">`-Label-Minimum auf **`--g-text-xs` (11 px)** heben (AP-017). Die 9-px-Labels kommen aus dem `size="sm"`-Zweig der Stat-Molecule.

### 3.2 Karten-Höhe / Map-Canvas-Clipp

- **JS-Restflächen-Berechnung ersatzlos streichen** (`mobileEditorHeightPx`, `MOBILE_EDITOR_MIN_HEIGHT_PX`, `BOTTOM_NAV_HEIGHT_PX`, `getSafeAreaPx`-Sonde, beide Measure-`$effect`s). Grund: der 34-px-Clipp ist der zweite schwere Fund dieser Datei nach F001/F004 — jede Messung der „Restfläche" koppelt Karte an Chrome-Höhe, Trip-Namen-Länge und Scrollposition. Das ist genau die Abhängigkeit, die der Adversary-Kommentar selbst als kippgefährdet beschreibt.
- Ersatz: **`.mobile-editor { height: max(240px, 40dvh) }`** — CSS-only, kein Listener, kein Floor-Problem (max() statt bedingtem Clamp), `dvh` folgt der Browser-Chrome dynamisch. Die BottomNav-Kollision entfällt, weil der Editor nicht mehr „bis zur Leiste" gezogen wird, sondern im normalen Scrollfluss steht (`.mobile-scroll-pad` bringt unten ohnehin `--g-nav-clearance` + 16 px).
- `MapCanvas` bekommt `fillHeight` weiterhin 100% der jetzt stabilen Elternhöhe; `invalidateSize()` nur noch auf Snap-Wechsel (vorhanden), nicht mehr auf Resize-Kaskaden.
- Nebeneffekt: der fixierte Cascade-Banner (`position: fixed` + Platzierungs-Effekt, Bug #1375/#1393) kann im Scrollfluss wieder ein normaler Inline-Strip über der Karte werden — der „verdeckt die Kartensteuerelemente"-Fall entsteht nur aus der Vollbild-Map-First-Anordnung. **→ PO-Frage F2** (Banner-Verhalten bei langem Chrome prüfen).

### 3.3 Profil-Sheet

- `ProfileSheetEmbedded` bleibt die Komponente, wechselt aber die Anker: **unter der Karte im Scrollfluss** statt absolut über der (gekappten) Restfläche. Snaps bleiben (`collapsed 56` / `peek 32%` / `half 55%` / `full 84%`), sind damit aber relativ zu einer stabilen Basis — der „abgeschnitten"-Clipp verschwindet mit 3.2.
- Peek ist der Default: Griff + Eyebrow „Wegpunkte · Etappe N" + Mini-Höhenprofil sichtbar, volle Wegpunktliste per Griff/Handle auf half/full. 1:1 mit #585-Live-Stand, nur der Anker wechselt.

### 3.4 Etappen-Darstellung: vertikale Liste statt horizontaler Strip

- **`<EtappenStrip>` wird auf Mobile durch eine vertikale `StageCardM`-Liste ersetzt** — Muster aus `docs/design/mobile/screen-trip-detail-mobile.jsx:192-234` (`DetailStages`), angepasst an die Editor-Anforderungen. Desktop-Strip unverändert.
- Die Liste übernimmt beide Achsen des heutigen Doppel-Systems: **aktivieren (Tap)** und **sortieren (Drag am Griff)** — damit entfallen `stage-switcher-pill` + `StageSelectSheet` auf Mobile ersatzlos (sie waren die #503-Behelfs-Lösung für den Strip; die Liste skaliert wie das Sheet auf 13+ Etappen, nur ohne Extra-Komponente).
- Karte bleibt zuerst sichtbar (Map-First bleibt als *Reihenfolge* bestehen, nicht als Vollbild-Rechtfertigung): Liste scrollt unter die Karte — die aktive Etappe ist auf der Karte kontextuell, die Liste ist der Einstieg.
- Begründung gegen den Strip: 916 px horizontale Scrollbreite bei 278 px Sicht ist nicht „Drag zum Sortieren", sondern Wischerei; vertikale Listen sind das Scroll-Muster der gesamten Mobile-Shell (AP-016 `gap`, keine Horizontalachsen außer explizit Daten-Matrizen).

### 3.5 Drag-Griff und Sortierung

- **Griff-only, kein Karten-Drag** (#1272 PO-Entscheid, ADR-0024): vertikale Liste nutzt die geteilte `SortableList`/`DragHandle`-Infrastruktur (gleicher Baustein wie Orte-Tab im Compare).
- **Griff im dichten Modus Pflicht** (#1272 offene Design-Frage, vom Code bereits so gebaut): `DragHandle` 44×44 px links in jeder `StageCardM`, sichtbar immer (nicht nur im Edit-Modus). Tastatur: Space/Enter → Sortiermodus, Pfeiltasten → verschieben (svelte-dnd-action-Bordmittel).
- Pfeile ▲/▼ kommen nicht zurück (#848).
- Pause einfügen wandert aus dem Hover-Gap (Strip-only) in den **„+ Etappe"-Kontext**: Ghost-Button „+ Etappe" (44 px) öffnet eine kleine Wahl „Etappe / Pausentag" — Öffnen-Frage F3, Alternativ-Vorschlag: Pausentag-Karte hat inline „Pausentag einfügen"-Aktion nach jeder Karte. Im Mockup ist Variante „Wahl am +"-Button dargestellt.

### 3.6 Mini-Texte (15 Texte < 11 px)

- Globale Regel dieses Pakets: **kein Text unter `--g-text-xs` (11 px)** im stages-Tab (AP-017). Konkret:
  - `StageCard`-Labels 9 px → 11 px bzw. in `StageCardM` mono 11 px (Code-Mono 11/13, Meta mono 11).
  - Strip-Eyebrow „ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN" (10 px) → ersetzt durch Listen-Header „4 ETAPPEN · ZIEHEN ZUM SORTIEREN" in `--g-text-xs`, Copy-Regel AP-014 („Drag" → „ziehen").
  - `Stat size="sm"`-Label 9 px → 11 px (3.1).
  - Karten-Attribution „© OpenStreetMap" bleibt die eine begründete Ausnahme (rechtlicher Hinweis, dekorativ, 9 px) — analog zum Ist.

## 4. Betroffene Komponenten (Katalog-Bezug)

| Komponente | Änderung | Katalog |
|---|---|---|
| `TripHeader.svelte` (Organism) | `.trip-h1` Mobile 20 px, `.trip-h1-row` min-width:0 nowrap, Stat-Label-Min 11 px | `<TripHeader>` §8; AP-011 |
| `EditStagesPanelNew.svelte` | `.mobile-editor` CSS-Höhe statt JS-Messung; Cascade-Banner inline; Media-Query-Zweig für vertikale Liste | Domain §9 (#503) |
| `EtappenStrip.svelte` / `StageCard.svelte` | Desktop unverändert; auf Mobile nicht mehr gerendert (durch Liste ersetzt) | `<EtappenStrip>` §9 v1.2 |
| **`StageCardM`** (neu, Molecule) | Vertikale Etappen-Karte: Griff 44 px, Code+Datum mono 11, Titel 13 (`--g-text-sm`), Stats mono 11, `StagePill`, Pause-Variante (dashed, kursiv) | Neuer Katalog-Eintrag nötig (§11 Erweiterungs-Prozess) — Muster: `DetailStages`/`StageCardM` in screen-trip-detail-mobile.jsx |
| `ProfileSheetEmbedded.svelte` | Anker unter Karte (Scrollfluss), Snaps unverändert | §9 v1.2 |
| `StageSelectSheet.svelte` | Mobile: entfällt (Liste ersetzt); Desktop: ungenutzt, ggf. spätere Entfernung (separat) | — |
| `MapCanvas.svelte` | `fillHeight` unverändert; kein Resize-Kaskaden-Handling nötig | `<MapEditor>`-Verwandtschaft §9 |
| `MapControl.svelte` | unverändert (44×44, neutral, oben) | AP-012-Ausnahme |
| `Stat.svelte` (Molecule) | `size="sm"`-Label 9 px → 11 px | `<Stat>` §4.5 |

AP-Konformität: AP-006 (keine lokalen Kopien — `StageCardM` kommt als Katalog-Komponente, Liste nutzt geteilte SortableList), AP-008/016 (Spacing via `--g-s-*`, `gap`), AP-012 (MapControl, kein FAB), AP-014 (Copy „ziehen statt drag"), AP-017 (Typo-Tokens, Min 11 px).

## 5. Nicht-Ziele

- Desktop-Darstellung (Strip + 1fr/360px-Grid) unverändert.
- `WaypointEditorPage`-Aufräumen (#503 Schritt 4) — längst erledigt.
- Aktionen „Pausieren/Archivieren/Test-Briefing" oberhalb des Headers (auf den Audit-Screens sichtbar) — gehören zur Danger-Zone der Seite, separates Paket.
- Leaflet/Tile-Caching.

## 6. Offene Fragen an PO

- **F1:** Trip-Titel Mobile: `--g-text-xl` (20 px, Vorschlag) oder `--g-text-lg` (17 px, TOKENS.md-Annotation „Mobile Page-Titles")? — Entscheidung gehört ggf. nach TOKENS.md zurück.
- **F2:** Cascade-Banner („Etappen lückenlos neu datieren?") im Scrollfluss über der Karte statt fixiert: OK, solange er direkt unter der Etappen-Datum-Zeile bleibt? (Betrifft die Bug-Kette #1375/#1389/#1393.)
- **F3:** Pause einfügen: als Wahl am „+ Etappe"-Button (Mockup-Variante) oder als Inline-Aktion zwischen zwei Etappen-Karten? Letztere braucht keinen Zwischendialog, kostet aber eine Zeile pro Lücke.
- **F4:** `StageSelectSheet` auf Mobile wirklich entfernen? (Liste ersetzt sie vollständig; auf Desktop wird sie aktuell nur vom Strip-Kontext mobil genutzt.)

## 7. Abnahmekriterien (Vorschlag)

- [ ] stages-Tab auf 390×844: kein horizontales Scrollen, kein Element > Viewport-Breite.
- [ ] `map-canvas`-Höhe = `max(240px, 40dvh)` ± Rendering-Toleranz, ohne JS-Messung; kein Clipp von `profile-sheet-host`.
- [ ] Vertikale Etappen-Liste: 4+ Etappen, Griff 44×44, Tastatur-Sortierung funktioniert, Pausentag darstellbar, „+ Etappe" erreichbar.
- [ ] Kein Text im Tab < 11 px (Attribution ausgenommen).
- [ ] Deep-Link `?tab=stages` rendert identisch ohne Mess-Flickern.
- [ ] Desktop-Pixelstand der #585-Fidelity unverändert.
