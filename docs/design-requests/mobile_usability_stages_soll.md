# Mobile Usability · Paket 1 — Trip-Detail-Tab „Etappen & Wegpunkte" (stages)

**Status:** **PO-Entscheide vollständig (F1–F7), bereit für Spec** · 2026-09-22 · **Mockup:** `docs/design-requests/mobile-usability-stages-soll.html` (zeigt Zustand B)
**Bezug:** Mobile-Usability-Audit (WebKit, iPhone 13, 390×844) · #503 (Option B, verbindlich; Mobile-Präzisierung §4.4) · #585 (Editor live 1:1) · #1272 (Sortierung griff-only) · #963 (Map-First-Reorder — Mobile-Zweig entfällt mit F5) · ADR-0024 (geteilte SortableList) · Leitplanke 1 (mobile_shell_ohne_topbar.md §2a)

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

> **PO-Entscheid 2026-09-22 (F5, verbindlich):** Karte und Höhenprofil entfallen auf
> Mobile komplett. Begründung PO, wörtlich: *„Beides spielt unterwegs keine Rolle und
> niemand will das unterwegs auf dem Smartphone editieren."* Details und Konsequenzen
> in §4; die früheren Varianten A/B+ sind verworfen. §3 beschreibt die geteilte Basis
> (Titel, Liste, Typo-Regeln); Abschnitte 3.2/3.3 gelten damit als obsolet.

Ein vertikal scrollender Tab-Inhalt ohne horizontale Scrollbereiche, ohne Karte,
ohne Höhenprofil, ohne JS-Höhen-Messung:

```
[Tab-Leiste]                         ← Paket 2 (separater Soll)
[Desktop-Hinweis · neutral, statisch] ← „Karte & Höhenprofil sind am Desktop verfügbar"
[Etappen-Liste · vertikal, 4…N]      ← StageCardM, Drag-Griff, aufklappbare Wegpunkt-Zeilen
```

Desktop bleibt unverändert (Strip + Karte 440px + Profil + Grid 1fr/360px, #503-Layout).

## 3. Entscheidungen je Befund

### 3.1 Titel-Zeile (TripHeader, gilt seitenweit)

- `.trip-h1` auf Mobile: **38 px → `--g-text-xl` (20 px)** stufenlos per Media-Query (`max-width: 899px`), Tracking `--g-track-tight`. Begründung: einziger Skala-Sprung, der 38 px plausibel mobil skaliert (AP-017: nur `--g-text-*`-Token; Desktop bleibt `--g-text-3xl`-Nähe). `TOKENS.md §7` annotiert `--g-text-lg` (17 px) als „Mobile Page-Titles" — 20 px ist der Gegen-Vorschlag, weil der Trip-Name der Anker des Screens ist und lange Namen bei 17 px untergehen. **→ PO-Frage F1.**
- `.trip-h1-row`: `min-width: 0` + `flex-wrap: nowrap`, Titel `overflow: hidden; text-overflow: ellipsis` (einzeilig, kürzbar statt umbrechend-überstehend). Stift-Button fix 44×44 px rechts (`flex-shrink: 0`).
- `.header-left` hat bereits `min-width: 0` — die Kette bricht am `.trip-h1-row`, dort wird sie ergänzt.
- Stat-Labels (`ETAPPE`/`BRIEFING`/`START IN`): `<Stat size="sm">`-Label-Minimum auf **`--g-text-xs` (11 px)** heben (AP-017). Die 9-px-Labels kommen aus dem `size="sm"`-Zweig der Stat-Molecule.

### 3.2 Karten-Höhe / Map-Canvas-Clipp — ~~max(240px, 40dvh)~~ entfällt

> **Obsolet durch PO-Entscheid F5 (2026-09-22):** Auf Mobile gibt es keine Karte
> mehr — die Höhenfrage erledigt sich. Der komplette `.mobile-editor`-Zweig
> (Karten-Container, `mobileEditorHeightPx`, `BOTTOM_NAV_HEIGHT_PX`,
> `getSafeAreaPx`-Sonde, beide Measure-`$effect`s, Fixierungs-Logik des
> Cascade-Banners) wird auf Mobile nicht mehr gerendert und kann dort entfernt
> werden. Der 34-px-Clipp und die F001–F005-Kette sterben mit dem Zweig. Der
> Desktop-Zweig (`MapCanvas` 440px) bleibt unverändert.

### 3.3 Profil-Sheet — entfällt

> **Obsolet durch PO-Entscheid F5 (2026-09-22):** `ProfileSheetEmbedded` wird auf
> Mobile nicht mehr gerendert. Das Gesamt-Höhenprofil bleibt mobil im
> Übersichts-Tab erreichbar (`HubOverview` → `FullProfile`, §4.1) — das war die
> ohnehin identische Information. `EditorProfileSVG` bleibt unverändert (nur
> Desktop). Wegpunkt-Details wandern in die aufklappbaren Zeilen der
> `StageCardM` (§4.2, F7-Arbeitsstand).

### 3.4 Etappen-Darstellung: vertikale Liste statt horizontaler Strip

- **`<EtappenStrip>` wird auf Mobile durch eine vertikale `StageCardM`-Liste ersetzt** — Muster aus `docs/design/mobile/screen-trip-detail-mobile.jsx:192-234` (`DetailStages`), angepasst an die Editor-Anforderungen. Desktop-Strip unverändert.
- Die Liste übernimmt beide Achsen des heutigen Doppel-Systems: **aktivieren (Tap)** und **sortieren (Drag am Griff)** — damit entfallen `stage-switcher-pill` + `StageSelectSheet` auf Mobile ersatzlos (sie waren die #503-Behelfs-Lösung für den Strip; die Liste skaliert wie das Sheet auf 13+ Etappen, nur ohne Extra-Komponente).
- Die Liste ist auf Mobile die **einzige** Etappen-Darstellung: aktivieren (Tap),
  sortieren (Drag am Griff) und — neu — Wegpunkte anzeigen (aufklappbare Zeilen,
  §4.2). Die Karte als Kontextfläche entfällt mit F5; `stage-switcher-pill` +
  `StageSelectSheet` entfallen auf Mobile ersatzlos (die Liste skaliert auf 13+
  Etappen).
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
  - ~~Karten-Attribution~~ entfällt auf Mobile mit der Karte (F5); auf Desktop bleibt sie die begründete Ausnahme (rechtlicher Hinweis, dekorativ, 9 px).

## 4. Karte & Höhenprofil auf Mobile — Entscheid B (beschlossen)

> **Status: PO-ENTSCHEID, 2026-09-22 (Frage F5).** Karte und Höhenprofil entfallen
> auf Mobile komplett. Begründung PO, wörtlich: *„Beides spielt unterwegs keine
> Rolle und niemand will das unterwegs auf dem Smartphone editieren."*
> Desktop (≥ 900px) bleibt beim #503-Layout: EtappenStrip + Karte 440px +
> Höhenprofil + Wegpunkt-Sidebar (Grid 1fr/360px).

### 4.1 Fundlage (Ist, zitiert — Begründungsbasis für die Entscheid)

| Fakt | Fundstelle | Konsequenz |
|---|---|---|
| Das **Gesamt-Höhenprofil existiert bereits im Übersichts-Tab** — klickbar, Etappen-Auswahl inklusive | `trip-detail/HubOverview.svelte:3` (import), `:63` (`<FullProfile … onSelectStage>`); `FullProfile.svelte:37` (`VB_WIDTH 1000`), `:200-204` (SVG 100 % × 200 px); Mobil sichtbar: `HubOverview.svelte:163-169` (Grid → 1 Spalte ≤ 899px) | Das Profil im stages-Tab ist auf Mobile eine **Doppelung** — mit B streichen wir sie, ohne Informationsverlust. |
| Die **Karte existiert nur im stages-Tab** (sonst nirgends in trip-detail) | `MapCanvas.svelte` wird nur von `EditStagesPanelNew.svelte` importiert | B entfernt die einzige Routen-Visualisierung auf Mobile — vom PO gewichtet gegen „unterwegs keine Rolle". |
| Wegpunkt-Marker heute: **Standard-Leaflet-Pins, nicht nummeriert, keine definierte Touch-Fläche**; Popup „1. Name" | `MapCanvas.svelte:59-64` | Bestätigt den Touch-Editing-Befund: selbst die Ist-Karte ist mobil nicht editier-gestaltet. |
| `EditorProfileSVG` ist fix **343×70**, Sheet-Padding 16 px → innen 326 px bei 390px Viewport | `COMPONENTS.md §9`; `screen-waypoint-editor-mobile.jsx:386-398` | Wird mit B irrelevant (Komponente bleibt nur Desktop). |
| Mobile-Shell-Leitplanke 1 (PO 2026-09-19): „Anlegen und Editieren sind Desktop-Fälle" | `mobile_shell_ohne_topbar.md` §2a | Stützt B: Der stages-Tab ist primär Editor; der mobil verbleibende Nutzen (Reihenfolge, Daten, Risiko, Wegpunkt-Kontrolle) ist listenfähig. |

### 4.2 Beschlossenes Soll (Variante B)

Mobiler stages-Tab = **vertikale StageCardM-Liste als einzige Darstellung**, ergänzt um:

- **Desktop-Hinweis-Banner** oberhalb der Liste: „Karte & Höhenprofil sind am
  Desktop verfügbar." — **neutral und statisch**, bewusst **nicht** akzentuiert und
  nicht wegklappbar. Begründung: Es ist eine reine Info, kein Call-to-Action — ein
  Accent-Left-Border (bisher im B-Entwurf) signalisiert Aufmerksamkeit/Aktion, die
  es nicht gibt (Charter §6: Accent sparsam; AP-015: nüchtern, ein Satz). Ein
  wegklappbarer Zustand wäre Persistenz-Overhead für einen einzeiligen Hinweis.
  Umsetzung: `<Card>` mit `--g-card-alt`-Hintergrund, `--g-rule`-Rand, Info-Icon
  (`--g-ink-3`), Copy in `--g-text-sm`. Kein „Im Editor öffnen"-Button: #616 hat die
  separate Bearbeiten-Route entfernt — der stages-Tab *ist* der Editor, der Button
  wäre zirkulär (der „Im Editor öffnen →"-Sprung im Übersichts-Tab,
  `HubOverview.svelte:58`, landet genau hier).
- **Aufklappbare Wegpunkt-Zeilen in der StageCardM** (Arbeitsstand, siehe F7):
  Tap auf eine Etappen-Karte klappt die Wegpunkte als Zeilen auf (Nummern-Kreis,
  Name, Höhe, ETA in mono `--g-text-xs`), Chevron als Zustands-Indikator; Muster
  der heutigen Sheet-Liste (`screen-waypoint-editor-mobile.jsx:356-379`). Pause-Karten
  haben keine Wegpunkt-Zeilen.
- **Kein** `.mobile-editor`, **kein** `ProfileSheetEmbedded`, **kein** MapCanvas-Import
  mobil: Der Mobile-Zweig von `EditStagesPanelNew` rendert nur noch Listen-Header +
  Liste. `mobileEditorHeightPx`, Safe-Area-Sonde, Fixierungs-Effekte (F001–F005)
  entfallen vollständig — nicht nur umgangen.
- **Code-Konsequenz positiv:** Der Desktop-Zweig (Strip + Grid + MapCanvas 440px +
  `ProfileEditor`) bleibt unverändert; die Mobile/Desktop-Weiche wird simpler statt
  komplexer (heute zwei vollständige Render-Zweige).

### 4.3 Verworfene Alternativen (Archiv, Nachvollziehbarkeit)

- **Variante A (Karte 240px + Profil-Sheet, beides konkret gestaltet):** verworfen.
  Hätte Sheet + Popover + Marker-Synchronisation + Leaflet-Mobilpflege (Ladezeit,
  Tile-Daten, Offline) für einen Editor-Kontext gekostet, den der PO ausdrücklich
  als Desktop-Fall sieht. Die ausgearbeitete Gestaltung (nummerierte 44px-Marker,
  Popover, Peek-88-Sheet, Nummern-Dots) bleibt im Git-Verlauf des Mockups/Docs
  referenzierbar, falls die Entscheidung je revidiert wird.
- **Variante B+ (read-only-Karten-Thumbnail 160px, Profil weg):** verworfen. Der PO
  hat „unterwegs keine Rolle" auf beides bezogen — auch die reine Karten-Ansicht.
  B+ hätte den #503-Wortlaut entschärft, aber genau den Zustand geschaffen, den die
  Begründung ausschließt: ein Karten-Element, das niemand unterwegs braucht.

### 4.4 #503-Präzisierung (Vorschlag, wird mit der Implementierungs-Spec eingereicht)

Die verbindliche #503-ANTWORT sagt: „Die Karte gehört in den bestehenden
Etappen-Tab" (Option B, Architektur-Ebene, 2026-06). Für die Mobile-Ausprägung
schlagen wir folgende Ergänzung vor, die mit der Implementierungs-Spec des
Usability-Fix-Pakets als Änderung an `docs/design-requests/issue_503_ANTWORT.md`
eingereicht wird:

> *„**Mobile-Präzisierung (PO 2026-09-22):** Die Verbindlichkeit gilt für Desktop /
> Editor-Viewport (≥ 900 px). Auf Mobile (< 900 px) entfallen Karte und
> Höhenprofil im Etappen-Tab ersatzlos; stattdessen zeigt der Tab die vertikale
> Etappenliste mit aufklappbaren Wegpunkt-Zeilen und einem neutralen Hinweis
> „Karte & Höhenprofil sind am Desktop verfügbar". Das Gesamt-Höhenprofil bleibt
> mobil im Übersichts-Tab (`FullProfile`). Desktop bleibt 1:1 beim #503-Layout."*

Charter-Basis: §4 erlaubt explizit dokumentierte Mobile-Ausprägungen („Mobile-Pendant
**oder** responsiv mit explizit dokumentierten Breakpoints"); „entfällt auf Mobile,
Info via Übersichts-Tab" ist eine dokumentierbare Ausprägung.

## 5. Betroffene Komponenten (Katalog-Bezug)

| Komponente | Änderung | Katalog |
|---|---|---|
| `TripHeader.svelte` (Organism) | `.trip-h1` Mobile 20 px, `.trip-h1-row` min-width:0 nowrap, Stat-Label-Min 11 px | `<TripHeader>` §8; AP-011 |
| `EditStagesPanelNew.svelte` | Mobile-Zweig rendert nur noch Listen-Header + vertikale Liste (kein `.mobile-editor`, kein Sheet, kein MapCanvas); `mobileEditorHeightPx`/Mess-Effekte entfallen. Cascade-Banner mobil inline statt fixiert. Desktop unverändert | Domain §9 (#503) |
| `EtappenStrip.svelte` / `StageCard.svelte` | Desktop unverändert; auf Mobile nicht mehr gerendert (durch Liste ersetzt) | `<EtappenStrip>` §9 v1.2 |
| **`StageCardM`** (neu, Molecule) | Vertikale Etappen-Karte: Griff 44 px, Code+Datum mono 11, Titel 13 (`--g-text-sm`), Stats mono 11, `StagePill`, Pause-Variante (dashed, kursiv), **aufklappbare Wegpunkt-Zeilen** (F7-Arbeitsstand) | Neuer Katalog-Eintrag nötig (§11 Erweiterungs-Prozess) — Muster: `DetailStages`/`StageCardM` in screen-trip-detail-mobile.jsx |
| `ProfileSheetEmbedded.svelte` | Entfällt auf Mobile (wird nicht mehr gerendert); Desktop unverändert | §9 v1.2 |
| `EditorProfileSVG` | Unverändert (nur Desktop relevant) | §9 v1.2 |
| `StageSelectSheet.svelte` | Entfällt auf Mobile (durch Entscheid B/F4 mitentschieden); Desktop ggf. spätere Entfernung (separat) | — |
| `MapCanvas.svelte` | Unverändert (nur Desktop; kein mobiler Import mehr) | `<MapEditor>`-Verwandtschaft §9 |
| `MapControl.svelte` | Unverändert (Desktop/Karte); auf Mobile nicht mehr gerendert | AP-012-Ausnahme |
| `Stat.svelte` (Molecule) | `size="sm"`-Label 9 px → 11 px | `<Stat>` §4.5 |

AP-Konformität: AP-006 (keine lokalen Kopien — `StageCardM` kommt als Katalog-Komponente, Liste nutzt geteilte SortableList), AP-008/016 (Spacing via `--g-s-*`, `gap`), AP-012 (MapControl, kein FAB), AP-014 (Copy „ziehen statt drag"), AP-015 (Desktop-Hinweis: ein Satz, nüchtern), AP-017 (Typo-Tokens, Min 11 px). Der Desktop-Hinweis-Banner ist bewusst **nicht** akzentuiert (Charter §6: Accent = Primäraktion/Hervorhebung, keine reine Info).

## 6. Nicht-Ziele

- Desktop-Darstellung (Strip + Karte 440px + Profil + 1fr/360px-Grid) unverändert.
- `WaypointEditorPage`-Aufräumen (#503 Schritt 4) — längst erledigt.
- Aktionen „Pausieren/Archivieren/Test-Briefing" oberhalb des Headers (auf den Audit-Screens sichtbar) — gehören zur Danger-Zone der Seite, separates Paket.
- Leaflet/Tile-Caching.
- Änderung am Übersichts-Tab (`HubOverview`/`FullProfile`) — er bleibt der Ort des Gesamt-Profils; mit B gibt es im stages-Tab mobil keine Karten-/Profil-Reste (auch kein Thumbnail).

## 7. PO-Entscheide — ALLE ENTSCHIEDEN (2026-09-22)

- **F1 (ENTSCHIEDEN):** Trip-Titel Mobile = **`--g-text-xl` (20 px)** mit `min-width:0` + Ellipsis (Vorschlag angenommen). TOKENS.md-Annotation „Mobile Page-Titles → `--g-text-lg`" wird bei Gelegenheit präzisiert.
- **F2 (ENTSCHIEDEN):** Cascade-Banner mobil **inline über der betroffenen Etappen-Karte** (Vorschlag angenommen) — kein `position:fixed`, keine Platzierungs-Effekte; die #1375-Logik entfällt mobil.
- **F3 (ENTSCHIEDEN):** Pause einfügen = **Wahl am „+ Etappe"-Button** (Mockup-Variante angenommen): Ghost-Button öffnet kleine Wahl „Etappe / Pausentag".
- **F4 (ENTSCHIEDEN):** `StageSelectSheet` entfällt auf Mobile (Liste ist die einzige Etappen-Auswahl). Desktop-Entfernung separat.
- **F5 (ENTSCHIEDEN):** **Variante B** — Karte und Höhenprofil entfallen auf Mobile komplett. Begründung PO, wörtlich: *„Beides spielt unterwegs keine Rolle und niemand will das unterwegs auf dem Smartphone editieren."* — Varianten A und B+ verworfen (§4.3); #503-Präzisierung als Vorschlag in §4.4.
- **F6 (ENTSCHIEDEN):** Nummern-Kreise in den Wegpunkt-Zeilen bleiben **nummeriert je Etappe (1…N)** (Default angenommen); keine Etappen-Nummerierung nötig (Karte entfällt).
- **F7 (ENTSCHIEDEN):** Wegpunkt-Zeilen **direkt in der StageCardM aufklappbar** (Vorschlag/Mockup angenommen), Chevron als Zustands-Indikator; kein separater „Wegpunkte"-Block.

## 8. Abnahmekriterien (Vorschlag, Stand Entscheid F5 / Variante B)

Basis:

- [ ] stages-Tab auf 390×844: kein horizontales Scrollen, kein Element > Viewport-Breite.
- [ ] Kein Karten-, Profil-, Sheet- oder MapControl-Element im mobilen stages-Tab; kein Leaflet-Import mobil (Ladecheck).
- [ ] Desktop-Hinweis oberhalb der Liste: **neutral** (`--g-card-alt`, `--g-rule`-Rand, Info-Icon `--g-ink-3`), **statisch** (nicht wegklappbar, kein Accent), Copy ein Satz.
- [ ] Vertikale Etappen-Liste: 4+ Etappen, Griff 44×44, Tastatur-Sortierung funktioniert, Pausentag darstellbar, „+ Etappe" erreichbar.
- [ ] Wegpunkt-Zeilen: aufklappbar pro Etappe (Nummer, Name, Höhe, ETA), Chevron-Zustand sichtbar, Pause-Karten ohne Zeilen.
- [ ] Cascade-Banner mobil inline über der betroffenen Etappen-Karte (kein `position:fixed`, keine Platzierungs-Effekte).
- [ ] Kein Text im Tab < 11 px.
- [ ] Deep-Link `?tab=stages` rendert identisch, ohne Mess-Flickern.
- [ ] Desktop-Pixelstand der #585-Fidelity unverändert (Strip, Karte 440px, Profil, Grid).
- [ ] Gesamt-Höhenprofil im Übersichts-Tab mobil weiterhin erreichbar und unverändert.
