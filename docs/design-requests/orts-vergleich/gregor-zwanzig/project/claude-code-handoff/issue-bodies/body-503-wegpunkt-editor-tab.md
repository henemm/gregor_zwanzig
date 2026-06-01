<!-- gregor-zwanzig-handoff: stable_id=wegpunkt-editor-tab-503 -->
## Kontext

Bezug: **Issue #503 / #506** · Design-Request `docs/design-requests/issue_503_wegpunkt_editor_architektur.md`.
Vollständige Design-Antwort (Mockup + Begründung): `docs/design-requests/issue_503_ANTWORT.md`.
Design-Mockup im Design-Repo: `Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html`
(Komponenten: `screen-trip-edit-tabs.jsx` als Tab-Host, `screen-waypoint-editor*.jsx` als Editor).

> **Dieses Issue existiert auf GitHub bereits ohne Marker.** Body durch diesen ersetzen
> (inkl. Stable-ID-Zeile 1), Titel beibehalten. #506 ist verwandt — Cross-Link kommentieren,
> nicht ungeprüft schließen.

## Die offene Frage (aus #503)

Der Wegpunkt-Editor wurde in #494 auf Tab-Design umgestellt. Tab „Etappen"
(`EditStagesPanelNew`) hat seit #296 **keine Karte** (nur Höhenprofil + Wegpunktliste).
Die fertige `WaypointEditorPage` (mit Karte) wird nicht mehr gerendert (toter Code).
Drei Wege standen zur Wahl: **A** Karte weglassen · **B** Karte in den Etappen-Tab ·
**C** eigener 6. Tab „Wegpunkte".

## Entscheidung · **Option B**

> Die Karte gehört in den **bestehenden Etappen-Tab**. Der Tab wird zu
> **„Etappen & Wegpunkte"** umbenannt und nimmt den vollständigen Editor (Karte +
> Höhenprofil + Wegpunkt-Sidebar) als Inhalt auf. **`WaypointEditorPage` wird nicht
> als 6. Tab wiederbelebt — ihr Inhalt wandert in `EditStagesPanelNew`, dann wird sie
> gelöscht.** Eine Karte. Eine Stelle. Kein Duplikat.

**Begründung:** `EditStagesPanelNew` und `WaypointEditorPage` sind zu ~90 % dieselbe
Komponente (beide: EtappenStrip + Höhenprofil + Wegpunktliste). Der einzige echte
Unterschied ist die **Karte**. Damit kollabiert die Architektur-Frage auf einen Satz:
*Soll der Etappen-Tab eine Karte haben — ja.* Option A wirft das stärkste Setup-Werkzeug
weg (Wegpunkte sind Wetterscheiden, inhärent räumlich; das Höhenprofil zeigt *wann*, nie
*wo*). Option C erzeugt zwei Tabs mit demselben EtappenStrip + Höhenprofil → doppelte
Navigation und Pflege. Das bestehende Trip-Detail-Mockup nennt den Tab ohnehin schon
**„Etappen & Wegpunkte"** — die Design-Sprache behandelt beides längst als eine Fläche.

### Zu #296
#296 bleibt **im Kern gültig**: **keine Lat/Lon-Inputs**, Bearbeiten passiert visuell
(Pins auf Karte + Klick im Profil). Revidiert wird **nur** der Satz „Karte ganz entfernen".
Die Karte kehrt als Klick-/Ansichtsfläche zurück, **nicht** als Koordinaten-Formular.
→ #296 nicht reverten, sondern präzisieren: „Karte ja, Lat/Lon-Inputs nein."

## PO-Korrektur · keine „Auto vs. manuell"-Unterscheidung

Auf PO-Entscheid (2026-06-01) entfällt die komplette Unterscheidung zwischen
„automatisch vorgeschlagenen" und „manuellen" Wegpunkten — in der **App** und im
**gesendeten Briefing**. Ein Wegpunkt ist ein Wegpunkt. Konkret:

- **Keine** orange gestrichelten Pins / getönten Markierungen — alle Wegpunkte sehen gleich aus (solider Pin).
- **Kein** „· Vorschlag"-Badge in Liste/Profil.
- **Kein** „Bestätigen/Verwerfen"-Sonderweg. Jeder Wegpunkt hat dieselben Aktionen: **Umbenennen · Verschieben · Löschen**.
- **Kein** Hinweis-Footer („orange gestrichelt … Bestätigen …") — ersatzlos entfernt.
- **Kein** Marker im Briefing-Text (früher `(KI)`/`(auto)` hinter einem Wegpunkt) — ersatzlos entfernt.
- Das Daten-Flag `waypoint.ai` (bzw. äquivalent) wird **entfernt**; keine UI liest es mehr.
- Sprachregel projektweit: **kein „KI"** in der UI. Backend-seitige Erzeugung heißt sachlich
  „aus der GPX erzeugt / vorgeschlagen", nie „KI".

## Files

- `EditStagesPanelNew.svelte` — bekommt MapCanvas (Leaflet OpenTopoMap) + Grid `1fr / 360px`.
- `TripEditView.svelte` — Tab-Label „Etappen" → „Etappen & Wegpunkte"; Speichern/„Vorschläge neu berechnen" in die Page-Chrome.
- `WaypointEditorPage.svelte` — **löschen** (toter Code; Inhalt wandert in `EditStagesPanelNew`). Routen/Imports bereinigen.
- Mobile-Pendant des Etappen-Editors — Karte fullscreen + Bottom-Sheet als Tab-Inhalt unter der Tab-Leiste (`MTab`).
- Briefing-Renderer (Email/Signal/Telegram/SMS) — `(KI)`/`(auto)`-Marker hinter Wegpunkten entfernen.

## Layout · Desktop (Tab „Etappen & Wegpunkte")

Page-Chrome (TripEditView): Breadcrumb + Hero + Tab-Leiste. Speichern + „Vorschläge neu
berechnen" sitzen **rechts in der Breadcrumb-Zeile** (gehören dem Tab-Host, nicht dem Panel).

Tab-Inhalt:
1. **EtappenStrip** (volle Breite, direkt unter der Tab-Leiste) — Etappen-Auswahl,
   Drag-Sortieren, Pause-Insert. **Bleibt zwingend** — eigene Navigations-Achse (Etappe ≠ Tab).
2. **Grid `grid-template-columns: 1fr 360px`:**
   - **Links (1fr):** Karte-Card (Eyebrow „Karte · OpenTopoMap (OSM + SRTM)" + Pill „Topo",
     100 % Breite × **440 px** Höhe) — darunter Höhenprofil-Card (synchron mit Karte,
     km/↑/↓-Stats rechts im Header).
   - **Rechts (360px):** Wegpunkt-Sidebar-Card. Header „Wegpunkte · N insgesamt" + „+ auf Route".
     Eine Zeile je Wegpunkt; der aktive Eintrag klappt Aktionen **Umbenennen / Verschieben / Löschen** aus.
3. **Pausentag-Etappe:** keine Karte/Wegpunkte → `PauseStageView` (Standort + Hinweis), unverändert.

## Layout · Mobile (390 px)

Gleiches Prinzip, ein Tab — kein eigener Screen:
- **TopAppBar** (leftIcon back, Eyebrow = Tripname · N Etappen, Title „Bearbeiten", rechts Kebab) — von TripEditView.
- **`MTab`** scrollbar: Route · **Etappen & Wegpunkte** (aktiv, Badge N) · Wetter · Reports · Alarme.
- **Tab-Inhalt:** Etappen-Switcher-Pill (öffnet Etappen-Auswahl-Sheet) + editierbares Datum
  (`StageDateField`, siehe #18) + **Karte fullscreen** + 3 FABs (Plus, Karte, Suche) +
  **Bottom-Sheet** mit Höhenprofil & Wegpunkten (Snaps peek 92 / half 320 / full 540).

## Tab-Label & Position

- Label: **„Etappen & Wegpunkte"** (Desktop + Mobile).
- Position: **unverändert Position 2** (Route · **Etappen & Wegpunkte** · Wetter · Reports · Alarmregeln). Kein neuer Tab.

## Atomic-Design-Abbildung

| Ebene | Baustein | Quelle |
|---|---|---|
| Organism | StageWaypointEditor (= heutiger `WaypointEditorPage`-Body) | wird Inhalt von `EditStagesPanelNew` |
| Molecule | EtappenStrip (Drag-Sort + Pause-Insert) | aus `WaypointEditorPage` heben |
| Molecule | MapCanvas (Leaflet OpenTopoMap, **keine Lat/Lon-Inputs**) | = Katalog `<MapEditor>` |
| Molecule | ProfileEditor (Höhenprofil, synchron mit Karte) | bestehend |
| Molecule | WaypointCard / Wegpunkt-Sidebar (einheitliche Aktionen) | bestehend, Auto/Manuell-Zweig entfernt |
| Molecule | `StageDateField` + `StageCascadeNotice` | `molecules/` (Single-Source, siehe #18) |
| Template | TripEditView (Tabs + Page-Chrome + Save) | bestehend, nur Tab-Inhalt tauschen |

Das neue Label **„Etappen & Wegpunkte"** in `docs/design-system/COMPONENTS.md` und
`SCREENS.json` nachziehen (Vertrag: Mockup-Name = Code-Name = Katalog-Name).

## Umsetzungs-Schritte

1. `EditStagesPanelNew.svelte`: MapCanvas (Leaflet OpenTopoMap, 100 % × 440 px) ergänzen;
   Layout auf `grid-template-columns: 1fr 360px` (links Karte + Höhenprofil, rechts Wegpunkt-Sidebar).
   EtappenStrip bleibt oben.
2. `TripEditView.svelte`: Tab „Etappen" → „Etappen & Wegpunkte" (Position 2 unverändert).
3. Speichern + „Vorschläge neu berechnen" aus dem Panel in die Page-Chrome ziehen.
4. **`WaypointEditorPage.svelte` löschen**, Routen/Imports bereinigen.
5. Auto/Manuell-Unterscheidung entfernen: dashed Pins, Tint, „· Vorschlag"-Badge,
   „Bestätigen/Verwerfen", Hinweis-Footer, Briefing-Marker, `waypoint.ai`-Flag.
6. Mobile: Tab-Inhalt = Karten-/Sheet-Editor (kein separater Screen/Route).
7. `COMPONENTS.md` + `SCREENS.json` auf das neue Tab-Label + die einheitlichen Wegpunkt-Aktionen ziehen.
8. #296 aktualisieren (Karte erlaubt, Lat/Lon-Inputs weiterhin verboten).

## Constraints

- **C1** Tab 2 heißt „Etappen & Wegpunkte" (Desktop + Mobile); es gibt **keinen** separaten „Wegpunkte"-Tab.
- **C2** Tab-Inhalt: EtappenStrip + Karte (440 px) + Höhenprofil + Wegpunkt-Sidebar (`1fr / 360px`).
- **C3** Keine Lat/Lon-Inputs; Wegpunkte werden per Karte/Profil-Klick bearbeitet.
- **C4** Alle Wegpunkte sind visuell + interaktiv gleichwertig (keine Auto/Manuell-Unterscheidung).
- **C5** Wegpunkt-Aktionen einheitlich: Umbenennen / Verschieben / Löschen.
- **C6** Speichern + „Vorschläge neu berechnen" in der Page-Chrome, nicht im Panel.
- **C7** Pausentag-Etappe zeigt `PauseStageView` (keine Karte/Wegpunkte).
- **C8** Kein „KI" und kein Auto/Manuell-Marker in UI **und** gesendetem Briefing.

## Acceptance criteria

- [ ] Tab 2 heißt „Etappen & Wegpunkte" (Desktop + Mobile), Position unverändert.
- [ ] Tab-Inhalt zeigt EtappenStrip + Karte (440 px) + Höhenprofil + Wegpunkt-Sidebar (`1fr / 360px`).
- [ ] Keine Lat/Lon-Inputs; Bearbeiten per Karte/Profil-Klick.
- [ ] Alle Wegpunkte identisch dargestellt (kein dashed/Tint/Badge); Aktionen = Umbenennen/Verschieben/Löschen.
- [ ] Kein Hinweis-Footer; kein `(KI)`/`(auto)`-Marker im Briefing; `waypoint.ai`-Flag entfernt.
- [ ] Pausentag-Etappe zeigt `PauseStageView`.
- [ ] Speichern + „Vorschläge neu berechnen" in der Page-Chrome.
- [ ] `WaypointEditorPage.svelte` existiert nicht mehr; keine toten Imports/Routen.
- [ ] #296 aktualisiert (Karte erlaubt, Koordinaten-Inputs verboten).
- [ ] Bestehende Playwright `data-testid`s erhalten.

## Edge cases

| Fall | Verhalten |
|---|---|
| Etappe ohne Wegpunkte | Karte zeigt nur Route/leeren Zustand, Sidebar „0 insgesamt" + „+ auf Route". |
| Pausentag-Etappe | Kein Karten-/Wegpunkt-Block → `PauseStageView`. |
| Sehr viele Etappen (13+) | EtappenStrip horizontal scrollbar (Desktop) / Switcher-Sheet (Mobile). |
| SMS-Briefing | Wegpunkte ohne Marker, flach, ≤ 140 Zeichen (Output-Layout-System #14). |

## Out of scope (Folge-Issues)

- Echte Leaflet-Integration / Tile-Caching (eigenes Backend-Issue).
- Automatische Wegpunkt-Erzeugung aus der GPX (separat) — erzeugte und manuelle Wegpunkte sind in der UI gleichwertig, keine Unterscheidung.
- Drag-Reorder-Persistenz der Etappen (falls noch offen).

## 📎 Screenshots

**Soll · Desktop — Tab „Etappen & Wegpunkte" mit Karte + Höhenprofil + Wegpunkt-Sidebar**

![soll-issue503-desktop-etappen-tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue503-desktop-etappen-tab.png)

**Soll · Mobile — derselbe Tab: Karte fullscreen + Bottom-Sheet, kein eigener Screen**

![soll-issue503-mobile-etappen-tab](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue503-mobile-etappen-tab.png)
