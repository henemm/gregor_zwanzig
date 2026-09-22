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

> **Update 2026-09-22 (PO-Feedback):** Die Gestaltung von Karte und Höhenprofil ist
> als Entscheidungsvorlage mit zwei Varianten in §4 ausgearbeitet — **A** (Karte +
> Profil auf Mobile, konkret gestaltet) und **B** (beides entfällt auf Mobile).
> §2/§3 beschreiben die von beiden Varianten geteilte Basis (Titel, Liste,
> Typo-Regeln); Karten-/Profil-Entscheidungen aus §3.2/§3.3 gelten als Variante A.

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

## 4. Karte & Höhenprofil auf Mobile — Varianten A/B (PO-Entscheidungsvorlage)

PO-Feedback 2026-09-22: Die bisherige Lösung (Karte fixiert umankert + Profil-Sheet
im Scrollfluss) war eine Platzierung, keine Gestaltung. Beide Ausbaustufen werden
hier sauber gegenübergestellt. Mockup: Umschalter A/B oben im Frame
(`mobile-usability-stages-soll.html`).

### 4.1 Fundlage (Ist, zitiert)

| Fakt | Fundstelle | Konsequenz |
|---|---|---|
| Das **Gesamt-Höhenprofil existiert bereits im Übersichts-Tab** — klickbar, Etappen-Auswahl inklusive | `trip-detail/HubOverview.svelte:3` (import), `:63` (`<FullProfile … onSelectStage>`); `FullProfile.svelte:37` (`VB_WIDTH 1000`), `:200-204` (SVG 100 % × 200 px); Mobil sichtbar: `HubOverview.svelte:163-169` (Grid → 1 Spalte ≤ 899px) | Das Profil im stages-Tab ist auf Mobile eine **Doppelung** — die Info (Reihenfolge, Höhenverlauf, Etappen-Tap) ist bereits erreichbar. |
| Die **Karte existiert nur im stages-Tab** (sonst nirgends in trip-detail) | `MapCanvas.svelte` wird nur von `EditStagesPanelNew.svelte` importiert | Karte entfernen = auf Mobile **keine** Routen-Visualisierung mehr (außer Anlege-Wizard/Location-Kontexten). |
| Wegpunkt-Marker heute: **Standard-Leaflet-Pins, nicht nummeriert, keine definierte Touch-Fläche**; Popup „1. Name" | `MapCanvas.svelte:59-64` (`L.marker` + `bindPopup`) | Für Mobile sind nummerierte, ≥ 44 px tippbare Marker nötig — unabhängig von Variante A/B. |
| `EditorProfileSVG` ist fix **343×70** | `COMPONENTS.md §9` (v1.2); `docs/design-requests/screen-waypoint-editor-mobile.jsx:386-398` | Bei 390px Viewport, 16px Außenpadding, 16px Sheet-Padding bleiben **326 px** innen — 343 px overflowt/verkleinert. Sheet-Padding 12 px (`--g-s-3`) + SVG mit 1000er-viewBox (Muster `FullProfile`) lösen es. |
| Profil-Sheet-Snaps: `collapsed 56 / peek 32% / half 55% / full 84%` | `edit/ProfileSheetEmbedded.svelte:6` | Prozent-Snaps auf einen stabilen Anker beziehbar (Variante A). |

### 4.2 Variante A — Karte + Höhenprofil auf Mobile, konkret gestaltet

**Karte (`.mapcard`, feste Höhe `max(240px, 40dvh)`):**

- **Wegpunkt-Marker nummeriert:** weißer Kreis (24 px sichtbar) mit 2px Accent-Rand
  und Mono-Nummer (`--g-text-xs`), transparente **Hit-Fläche 44×44 px** drumherum
  (Charter §7). Muster identisch zum Karten-Mock des #503-Sollbilds
  (`screen-waypoint-editor-mobile.jsx:279-296`) — kein Neuerfinden.
- **Ausgewählter Wegpunkt:** Kreis 28px, Accent-Fill, Paper-Nummer (Muster
  `wp.selected` im selben Mock).
- **Tap auf Marker:** kompaktes **Popover** (Card, `--g-shadow-2`, Pfeil nach unten):
  „WP 3 · Talkammer", mono-Zeile „2440 m · ETA 11:05" + „Wegpunkt"-Aktionen
  (Umbenennen/Löschen als Ghost-`MBtn`s, 44px). Ersetzt das Leaflet-Standard-Popup
  (`MapCanvas.svelte:62`), das auf Touch unbrauchbar klein ist. Tap neben Popover
  schließt; zweiter Tap auf selben Marker ebenfalls.
- **Marker ↔ Liste synchron:** Auswahl im Sheet (Variante A.2) hebt den Marker hervor
  und umgekehrt (heute schon via `activeWaypointId`, `MapCanvas.svelte:9`).
- **MapControl** bleibt der einzige Karten-Overlay-Cluster (AP-012-Ausnahme):
  44×44, neutral, oben rechts. „Wegpunkt hinzufügen" bleibt editierend — auf dem
  Thumbnail bedeutet Tap auf Karte: Marker-Vorschlag setzen (heutiges
  `onMapClick`-Verhalten).
- **stage-switcher-pill / StageSelectSheet bleiben entfernt** (bisheriger Kern-Entwurf):
  Die Etappen-Auswahl übernimmt die vertikale Liste; die Karte zeigt immer die
  *aktive* Etappe. Marker sind Wegpunkt-Marker, keine Etappen-Marker — zwei
  nummerierte Systeme (Etappen 1–4 vs. Wegpunkte 1–5) auf einer 240px-Karte wären
  nicht unterscheidbar (F6).

**Höhenprofil (`ProfileSheetEmbedded`, Anker im Scrollfluss unter der Karte):**

- **Sheet statt Section/Akkordeon** — Entscheidung mit Begründung: Die
  Sheet-Convention der Mobile-Shell (`docs/design/mobile/README.md`, §Sheet-vs-Modal:
  BottomSheet für kontextuelle Aktionen / Quick-Edit) trifft zu: Profil +
  Wegpunktliste ist Quick-Edit. Ein Akkordeon als eigene Sektion wäre simpler, hielte
  die Wegpunktliste aber dauerhaft im Layout (größerer Scroll-Penny) und bräche die
  etablierte Griff-Sprache (Drag-Handle, Snaps), die #585 live 1:1 etabliert hat.
  Peek hält den Höhenverlauf permanent sichtbar — der wichtigste Informationsgehalt
  für 88 px.
- **Peek konkret: 88px** (Handle 20 + Kopfzeile 44 + 24px Profil-Beginn) — ersetzt
  das heutige prozentbasierte `peek 32%`, das bei kleinen Editor-Höhen kollabiert.
  Snaps: `peek 88 / half 320 / full 84%` (Deckel, wie `<Sheet snap="auto">`).
- **Wegpunkt-Dots im Profil:** nummerierte Dots (12px sichtbar, 44px Hit-Fläche via
  transparentem SVG-Kreis) an den Distanzpositionen; aktiver Dot Accent-Fill, Rest
  weiß/Accent-Rand (Muster `EditorProfileSVG`, um Nummern ergänzt). Tap auf Dot →
  Auswahl + Synchronisation mit Marker (Karte) und Wegpunktliste (Sheet).
- **Breite:** Sheet-Padding `var(--g-s-3)` (12px), `EditorProfileSVG` auf
  1000er-viewBox mit `width: 100%` umbauen (Muster `FullProfile.svelte:37`) —
  ersatzlos skalierbar, kein Fixwert mehr.

**Liste:** unverändert aus dem Kern-Entwurf (§3.4–3.6) — Karte und Sheet sitzen
oberhalb der vertikalen StageCardM-Liste.

### 4.3 Variante B — Karte + Profil entfallen auf Mobile

**Aufbau:** stages-Tab mobil = vertikale StageCardM-Liste als einzige Darstellung,
ergänzt um:

- **Wegpunkt-Zeilen pro Etappe:** StageCardM tappt auf und zeigt die Wegpunkte als
  Zeilen (Name, Höhe, ETA mono), synchron mit der heutigen Sheet-Liste (Muster
  `screen-waypoint-editor-mobile.jsx:356-379`). Chevron rechts als Zustands-Indikator.
- **Hinweis-Banner** (Card, 3px Accent-Left-Border, oberhalb der Liste):
  „Karte & Höhenprofil sind am Desktop verfügbar — Wegpunkte setzen und verschieben
  ist dort am besten machbar." (AP-015: ein Satz.) Kein „Im Editor öffnen"-Button:
  #616 hat die separate Bearbeiten-Route entfernt — der stages-Tab *ist* der Editor,
  der Button wäre zirkulär (der vorhandene „Im Editor öffnen →"-Sprung im
  Übersichts-Tab, `HubOverview.svelte:58`, landet genau hier).
- **Profil-Ersatz:** Das Gesamt-Profil bleibt mobil im **Übersichts-Tab**
  (`FullProfile`) erreichbar — Variante B verliert also kein Profil, sondern nur die
  Doppelung. Verlust allein: kein *Etappen-Profil mit Wegpunkt-Dots* mobil.
- **Code:** Desktop-Zweig von `EditStagesPanelNew` (Strip + Grid + MapCanvas 440px +
  ProfileEditor) bleibt unverändert; der Mobile-Zweig wird schlanker (kein
  `mobile-editor`, kein Sheet, kein MapCanvas-Import mobil). `mobileEditorHeightPx`
  und die F001–F005-Effekte entfallen vollständig statt nur umgangen zu werden.

**Widerspruchs-Analyse:**

| Prüfung | Befund |
|---|---|
| **#503-ANTWORT (Option B verbindlich, 2026-06):** „Die Karte gehört in den bestehenden Etappen-Tab … Wirft das stärkste Setup-Werkzeug weg" (Ablehnung von Option A „Karte weglassen") | Die Entscheidung zielte auf **Architektur-Ebene** (kein 6. Tab, kein Duplikat-Editor, Karte nicht aus der App entfernen) — damals gab es noch kein Mobile-Shell-Pflichtenheft. Charter §4: jede Desktop-Komponente braucht ein „deklariertes Mobile-Pendant **oder** ist responsiv mit explizit dokumentierten Breakpoints" — „entfällt auf Mobile, Info bleibt via Übersichts-Tab" ist eine dokumentierbare Ausprägung, aber sie **widerspricht dem Wortlaut von #503** („Karte gehört in den Etappen-Tab"). Konflikt ist real, aber lösbar: #503 um einen Satz präzisieren („Karte ja — Mobile-Ausprägung nach §4 des Usability-Solls"). **PO-Entscheid nötig (F5).** |
| **Leitplanke 1 (PO 2026-09-19, `mobile_shell_ohne_topbar.md` §2a):** „PWA auf iPhone dient dem schnellen Zugriff … Anlegen und Editieren sind Desktop-Fälle." | Stützt B klar: Der stages-Tab ist primär **Editor** (Etappen sortieren, Wegpunkte setzen/verschieben). Leitplanke 1 sagt ausdrücklich, dass schwere Eingabe am Desktop stattfindet. Der auf Mobile verbleibende Nutzen (Reihenfolge, Daten, Risiko, Wegpunkt-Kontrolle) ist vollständig listenfähig. |
| **Doppelungsfund:** Profil existiert bereits im Übersichts-Tab (`HubOverview.svelte:63`); Karte nur im stages-Tab | B entfernt nur die Profil-Doppelung und die Karte. Gegenprobe „Übersicht hat schon eine Karte" ist **nicht** erfüllt — dort gibt es nur `FullProfile`, keine Karte (`HubOverview.svelte` importiert kein MapCanvas). |
| **Touch-Editing-Realismus:** Wegpunkt per `onMapClick` auf der Route setzen (`MapCanvas.svelte:77-81`), verschieben per Marker — auf 390px/Finger | Leaflet-Controls sind touch-fähig, aber präzises Setzen/Verschieben von Wetterscheiden auf einer Topokarte mit dem Finger ist realistisch eingeschränkt; Fehltipp-Kosten hoch (unbenannter WP in falscher Kammer). Anschaubarkeit ist gegeben, Bearbeitbarkeit marginal. |
| **Wetter-Briefing-Nutzen:** Wegpunkte sind Wetterscheiden (#503) — räumliche Lage ist Setup-Wissen | Unterwegs zählen Reihenfolge, Höhe, Risiko — alles in Liste + Übersichts-Profil. Routen-Navigation ist nicht Produkt-Scope. |

**Trade-offs B:** − Karten-Orientierung unterwegs (schwach, s. o.); − Etappen-Profil mit
WP-Dots mobil; + kein Leaflet auf Mobile (Ladezeit, Tile-Daten, Offline-Sackgassen),
+ kein Sheet/Kein Mess-JS, + ein Scroll-Muster, + klare Leitplanke-1-Linie.

### 4.4 Empfehlung: **Variante B+ (B mit read-only-Karten-Thumbnail)**

Reines B verwirft die Karte komplett und stellt den #503-Wortlaut auf die Probe,
volles A kostet Sheet + Popover + Marker-Sync + Leaflet-Mobilpflege für einen
Editor-Kontext, den Leitplanke 1 als Desktop-Fall deklariert. Der saubere Mittelweg:

- **Karte bleibt als read-only Thumbnail** im stages-Tab: `max(160px, 24dvh)`,
  keine MapControl-Edit-Werkzeuge, nummerierte tippbare Marker mit Popover
  (Name/Höhe/ETA — Gestaltung wie A.1, nur ohne Edit-Aktionen). Erhält die
  #503-Linie „Karte im Etappen-Tab", kostet aber kein Editing-Interaktionsdesign.
- **Profil-Sheet entfällt** im stages-Tab — das Übersichts-`FullProfile` übernimmt
  (Doppelung gestrichen, Wegpunkt-Dots sind der einzige echte Informationsverlust).
- **Liste übernimmt** wie in B die Wegpunkt-Zeilen (Aufklapp-Chevron).
- Editing-Hinweis-Banner wie B.

Begründung in einem Satz: Das Profil ist mobil bereits vorhanden (Übersicht), die
Karte nur hier — also Karte klein+read-only behalten, Profil-Doppelung streichen,
Editieren an den Desktop verweisen (Leitplanke 1). Falls PO Karten-Nutzung mobil für
marginal hält, ist reines B die konsequentere Variante desselben Arguments — die
Vorlage dafür steht mit 4.3.

### 4.5 Neue PO-Fragen (eingearbeitet in §7)

- **F5:** Variante A, B oder B+? (Mit F6/F7 als Nachfragen.)
- **F6:** Bei A/B+: Nummernsystem — Wegpunkte nummeriert, Etappen unnummeriert
  (Vorschlag), oder beide (verwirrt auf kleiner Karte)?
- **F7:** Bei B/B+: Wegpunkt-Zeilen direkt in der StageCardM aufklappbar (Vorschlag)
  oder eigener „Wegpunkte"-Unterblock unter der Liste?

## 5. Betroffene Komponenten (Katalog-Bezug)

| Komponente | Änderung | Katalog |
|---|---|---|
| `TripHeader.svelte` (Organism) | `.trip-h1` Mobile 20 px, `.trip-h1-row` min-width:0 nowrap, Stat-Label-Min 11 px | `<TripHeader>` §8; AP-011 |
| `EditStagesPanelNew.svelte` | `.mobile-editor` CSS-Höhe statt JS-Messung; Cascade-Banner inline; Media-Query-Zweig für vertikale Liste | Domain §9 (#503) |
| `EtappenStrip.svelte` / `StageCard.svelte` | Desktop unverändert; auf Mobile nicht mehr gerendert (durch Liste ersetzt) | `<EtappenStrip>` §9 v1.2 |
| **`StageCardM`** (neu, Molecule) | Vertikale Etappen-Karte: Griff 44 px, Code+Datum mono 11, Titel 13 (`--g-text-sm`), Stats mono 11, `StagePill`, Pause-Variante (dashed, kursiv) | Neuer Katalog-Eintrag nötig (§11 Erweiterungs-Prozess) — Muster: `DetailStages`/`StageCardM` in screen-trip-detail-mobile.jsx |
| `ProfileSheetEmbedded.svelte` | Variante A: Anker unter Karte, Peek 88px statt 32%, Padding 12, SVG 100%-breit. Variante B/B+: entfällt auf Mobile (unverändert auf Desktop) | §9 v1.2 |
| `EditorProfileSVG` | 1000er-viewBox + `width:100%` statt fix 343×70 (Variante A); nummerierte Wegpunkt-Dots mit 44px Hit-Fläche | §9 v1.2 |
| `StageCardM` | Variante B/B+: zusätzlich aufklappbare Wegpunkt-Zeilen (Chevron) | s. o. |
| `StageSelectSheet.svelte` | Mobile: entfällt (Liste ersetzt); Desktop: ungenutzt, ggf. spätere Entfernung (separat) | — |
| `MapCanvas.svelte` | Variante A/B+: nummerierte 44px-Marker + Popover statt Standard-Pin/Popup; B: unverändert (nur Desktop) | `<MapEditor>`-Verwandtschaft §9 |
| `MapControl.svelte` | unverändert (44×44, neutral, oben) | AP-012-Ausnahme |
| `Stat.svelte` (Molecule) | `size="sm"`-Label 9 px → 11 px | `<Stat>` §4.5 |

AP-Konformität: AP-006 (keine lokalen Kopien — `StageCardM` kommt als Katalog-Komponente, Liste nutzt geteilte SortableList), AP-008/016 (Spacing via `--g-s-*`, `gap`), AP-012 (MapControl, kein FAB), AP-014 (Copy „ziehen statt drag"), AP-017 (Typo-Tokens, Min 11 px).

## 6. Nicht-Ziele

- Desktop-Darstellung (Strip + 1fr/360px-Grid) unverändert — gilt für Variante A, B und B+.
- `WaypointEditorPage`-Aufräumen (#503 Schritt 4) — längst erledigt.
- Aktionen „Pausieren/Archivieren/Test-Briefing" oberhalb des Headers (auf den Audit-Screens sichtbar) — gehören zur Danger-Zone der Seite, separates Paket.
- Leaflet/Tile-Caching.
- Änderung am Übersichts-Tab (`HubOverview`/`FullProfile`) — er bleibt in allen Varianten der Ort des Gesamt-Profils.

## 7. Offene Fragen an PO

- **F1:** Trip-Titel Mobile: `--g-text-xl` (20 px, Vorschlag) oder `--g-text-lg` (17 px, TOKENS.md-Annotation „Mobile Page-Titles")? — Entscheidung gehört ggf. nach TOKENS.md zurück.
- **F2:** Cascade-Banner („Etappen lückenlos neu datieren?") im Scrollfluss über der Karte statt fixiert: OK, solange er direkt unter der Etappen-Datum-Zeile bleibt? (Betrifft die Bug-Kette #1375/#1389/#1393.) — Bei Variante B/B+ (keine Vollbild-Karte) verliert die Frage ihren Fixierungs-Zwang; dann gilt: inline direkt unter dem Datum, aus dem der Wurf kam.
- **F3:** Pause einfügen: als Wahl am „+ Etappe"-Button (Mockup-Variante) oder als Inline-Aktion zwischen zwei Etappen-Karten? Letztere braucht keinen Zwischendialog, kostet aber eine Zeile pro Lücke.
- **F4:** `StageSelectSheet` auf Mobile wirklich entfernen? (Liste ersetzt sie vollständig; auf Desktop wird sie aktuell nur vom Strip-Kontext mobil genutzt.)
- **F5:** **Varianten-Entscheid Karte/Profil (§4): A, B oder B+ (Empfehlung)?** Bei B/B+: #503-ANTWORT um einen Satz präzisieren („Karte ja — Mobile-Ausprägung nach §4")?
- **F6:** Nummernsystem auf Karte/Profil: Wegpunkte nummeriert, Etappen unnummeriert (Vorschlag — vermeidet 1–4 vs. 1–5-Verwechslung auf kleiner Fläche) oder beide nummeriert?
- **F7:** Bei B/B+: Wegpunkt-Zeilen direkt in der StageCardM aufklappbar (Vorschlag, Mockup) oder separater „Wegpunkte"-Block?

## 8. Abnahmekriterien (Vorschlag)

Basis (alle Varianten):

- [ ] stages-Tab auf 390×844: kein horizontales Scrollen, kein Element > Viewport-Breite.
- [ ] Vertikale Etappen-Liste: 4+ Etappen, Griff 44×44, Tastatur-Sortierung funktioniert, Pausentag darstellbar, „+ Etappe" erreichbar.
- [ ] Kein Text im Tab < 11 px (Attribution ausgenommen).
- [ ] Deep-Link `?tab=stages` rendert identisch ohne Mess-Flickern.
- [ ] Desktop-Pixelstand der #585-Fidelity unverändert.

Variante A (zusätzlich):

- [ ] `map-canvas`-Höhe = `max(240px, 40dvh)` ± Rendering-Toleranz, ohne JS-Messung; kein Clipp von `profile-sheet-host`.
- [ ] Wegpunkt-Marker: nummeriert, 44×44 Hit-Fläche, aktiver Marker hervorgehoben; Tap öffnet Popover (Name, Höhe, ETA); Auswahl synchron mit Profil-Dots und Sheet-Liste.
- [ ] Profil-Sheet: Peek 88px, Griff auf half/full, Wegpunkt-Dots tippbar (44px), EditorProfileSVG skaliert auf volle Innenbreite (kein Fixwert).

Variante B/B+ (zusätzlich):

- [ ] (B+) Karten-Thumbnail read-only: `max(160px, 24dvh)`, keine Edit-Werkzeuge, Marker+Popover wie A, aber ohne Edit-Aktionen.
- [ ] (B/B+) Hinweis-Banner mit Desktop-Verweis (ein Satz, AP-015); kein zirkulärer „Im Editor öffnen"-Button.
- [ ] (B/B+) StageCardM klappt Wegpunkt-Zeilen auf (Name, Höhe, ETA), Chevron-Zustand sichtbar.
- [ ] (B/B+) Auf Mobile kein Leaflet-Import im stages-Tab (Ladecheck); Profil weiterhin im Übersichts-Tab erreichbar.
