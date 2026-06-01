# Antwort · Design-Request #503 — Wegpunkt-Editor: Wo gehört die Karte hin?

**Status:** beantwortet · 2026-06-01
**Bezug:** Issue #503 / #506 · ersetzt die offene Design-Frage aus
`docs/design-requests/issue_503_wegpunkt_editor_architektur.md`
**Mockup:** `Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html` (Sektion 00 Begründung,
01 Desktop 1440, 02 Mobile 390)

---

## TL;DR — Empfehlung: **Option B**

> Die Karte gehört in den **bestehenden Etappen-Tab**. Dieser wird zu
> **„Etappen & Wegpunkte"** umbenannt und nimmt den fertigen Editor als Inhalt auf.
> **`WaypointEditorPage` wird nicht als 6. Tab wiederbelebt — sein Inhalt wandert in
> `EditStagesPanelNew`, dann wird die Page gelöscht.**

Eine Karte. Eine Stelle. Kein Duplikat. Kein neuer Tab.

---

## Warum B (und nicht A oder C)

**`EditStagesPanelNew` und `WaypointEditorPage` sind zu ~90 % dieselbe Komponente:**
beide zeigen EtappenStrip + Höhenprofil + Wegpunktliste. Der einzige echte Unterschied
ist **die Karte** und die Sidebar-statt-Inline-Liste. Damit kollabiert die ganze
Architektur-Frage auf einen Satz: *Soll der Etappen-Tab eine Karte haben — ja.*

| Option | Bewertung | Begründung |
|---|---|---|
| **A** Karte weglassen | ❌ verworfen | Wirft das stärkste Setup-Werkzeug weg. Wegpunkte sind *Wetterscheiden* — inhärent räumlich. Das Höhenprofil zeigt *wann* (Distanz/Höhe), nie *wo* (Talkammer, Exposition, Grat). Außerdem landet eine fertige, spec-treue Komponente im Müll. |
| **B** Karte in „Etappen & Wegpunkte" | ✅ **Empfehlung** | Eine Stelle für Etappen- + Wegpunkt-Bearbeitung. Eliminiert das Duplikat. Deckt sich mit dem bestehenden Trip-Detail-Mockup, das den Tab schon **„Etappen & Wegpunkte"** nennt — die Design-Sprache behandelt beides längst als eine Fläche. |
| **C** eigener 6. Tab „Wegpunkte" | ❌ abgelehnt | Zwei Tabs mit demselben EtappenStrip + Höhenprofil = doppelte Navigation, doppelte Pflege, „in welchem Tab verschiebe ich einen Wegpunkt?". Genau die Drift, gegen die das Projekt arbeitet. |

### Zu Issue #296
#296 bleibt **im Kern gültig**: **keine Lat/Lon-Inputs**, Bearbeiten passiert visuell.
Der gebaute Editor hält das ein (Pins auf Karte + Klick im Profil, kein
Koordinaten-Formular). Revidiert wird **nur der eine Satz** „Karte ganz entfernen".
Die Karte kehrt als **Klick-/Ansichtsfläche** zurück, nicht als Eingabe-Widget.
→ #296 nicht reverten, sondern **präzisieren**: „Karte ja, Lat/Lon-Inputs nein."

---

## Antworten auf die 4 konkreten Fragen

**1. Architektur (A/B/C)?** → **B.** Karte in den Etappen-Tab, Editoren zusammenführen.

**2. Falls C (Tab-Name/Position)?** → entfällt. *(Hätte es C werden müssen: „Wegpunkte"
zwischen „Etappen" und „Wetter". Wird aber nicht empfohlen.)*

**3. Layout von `EditStagesPanelNew` mit Karte?** → **Gleich wie der frühere
Wegpunkt-Editor:** `grid-template-columns: 1fr 360px`.
- **Links (1fr):** Karte-Card (`Eyebrow „Karte · OpenTopoMap (OSM + SRTM)"` + Pill „Topo",
  100 % Breite × **440 px** Höhe) — darunter Höhenprofil-Card (synchron mit Karte,
  km/↑/↓-Stats rechts im Header).
- **Rechts (360px):** Wegpunkt-Sidebar-Card (Header `Wegpunkte` + „+ auf Route",
  Eine Zeile je Wegpunkt mit Aktionen Umbenennen/Verschieben/Löschen).
- **Pausentag-Etappe:** keine Karte/Wegpunkte → `PauseStageView` (Standort + Hinweis),
  identisch zum bestehenden Editor.

**4. Eigener EtappenStrip oder reicht die Tab-Navigation?** → **Eigener EtappenStrip,
zwingend.** Das sind zwei **verschiedene** Navigations-Achsen:
- **TripEditView-Tabs** wechseln den *Aspekt* (Route / Etappen & Wegpunkte / Wetter / Reports / Alarmregeln) — feste App-Struktur.
- **EtappenStrip** wechselt die *Etappe* (T01 / T02 / Pause / T03 …) innerhalb des Tabs — variable User-Daten, plus Drag-Sortieren + Pause-Insert.

Man kann Etappen nicht als Tabs abbilden (Anzahl variabel). EtappenStrip bleibt
**direkt unter der Tab-Leiste**, über dem Karte/Profil/Sidebar-Grid.

---

## Page-Chrome / Action-Ownership

Die globalen Aktionen **„Speichern"** und **„Vorschläge neu berechnen"** gehören
ab jetzt der **TripEditView-Page-Chrome** (Breadcrumb-Zeile rechts), **nicht** dem
Editor-Panel. `EditStagesPanelNew` rendert nur noch den Tab-Inhalt (EtappenStrip + Grid),
keine eigene Header-/Save-Leiste mehr. Im Mockup ist das so umgesetzt
(`embedded`-Modus liefert genau den Tab-Inhalt).

---

## Mobile (390 px)

Gleiches Prinzip, ein Tab:
- **TopAppBar** (`leftIcon back`, Eyebrow = Tripname · N Etappen, Title „Bearbeiten",
  rechts Kebab) → liefert TripEditView.
- **`MTab`** scrollbar: Route · **Etappen & Wegpunkte** (aktiv, Badge N) · Wetter · Reports · Alarme.
- **Tab-Inhalt:** Etappen-Switcher-Pill (öffnet `StageSelectSheet`) + editierbares
  Datum + **Karte fullscreen** + 3 FABs (Plus, Map, Search) + **Bottom-Sheet** mit
  Höhenprofil & Wegpunkten (Snaps peek 92 / half 320 / full 540).

Kein eigener Mobile-Screen — derselbe Tab-Inhalt unter derselben Tab-Leiste.

---

## Atomic-Design-Abbildung (für die Umsetzung)

Bestehende, kanonische Bausteine — **nichts neu erfinden:**

| Ebene | Baustein | Quelle |
|---|---|---|
| Organism | **StageWaypointEditor** (= heutiger `WaypointEditorPage`-Body) | wird Inhalt von `EditStagesPanelNew` |
| Molecule | EtappenStrip (Drag-Sort + Pause-Insert) | aus `WaypointEditorPage` heben |
| Molecule | MapCanvas (Leaflet OpenTopoMap, **keine Lat/Lon-Inputs**) | = Katalog `<MapEditor>` |
| Molecule | ProfileEditor (Höhenprofil, synchron mit Karte) | bestehend |
| Molecule | Wegpunkt-Sidebar / WaypointCard | bestehend |
| Molecule | `StageDateField` + `StageCascadeNotice` | `molecules/` (Single-Source, nicht duplizieren) |
| Template | TripEditView (Tabs + Page-Chrome + Save) | bestehend, nur Tab-Inhalt tauschen |

Das **„Etappen & Wegpunkte"**-Label muss in `COMPONENTS.md` / `SCREENS.json`
nachgezogen werden (Vertrag: Mockup-Name = Code-Name = Katalog-Name).

---

## Umsetzungs-Schritte (für Claude Code)

1. **`EditStagesPanelNew.svelte`**: MapCanvas (Leaflet OpenTopoMap, 100 % × 440 px)
   ergänzen; Layout auf `grid-template-columns: 1fr 360px` umstellen
   (links Karte + Höhenprofil, rechts Wegpunkt-Sidebar). EtappenStrip bleibt oben.
2. **Tab umbenennen** in `TripEditView.svelte`: „Etappen" → **„Etappen & Wegpunkte"**.
   Tab-Reihenfolge unverändert (Position 2).
3. **Save-Aktion** aus dem Panel in die TripEditView-Page-Chrome ziehen
   (falls noch im Panel).
4. **`WaypointEditorPage.svelte` löschen** (toter Code) — Inhalt ist nach
   `EditStagesPanelNew` gewandert. Routen/Imports darauf bereinigen.
5. **Issue #296** aktualisieren: Begründung auf „keine Lat/Lon-Inputs" präzisieren,
   den Satz „Karte ganz entfernen" zurücknehmen.
6. **Mobile**: `MTab`-Tab „Etappen & Wegpunkte" rendert den Karten-/Sheet-Editor als
   Tab-Inhalt (kein separater Screen/Route).
7. **Doku**: `COMPONENTS.md` + `SCREENS.json` auf das neue Tab-Label ziehen.

---

## Acceptance Criteria

- [ ] Tab 2 heißt „Etappen & Wegpunkte" (Desktop + Mobile).
- [ ] Tab-Inhalt zeigt EtappenStrip + Karte (440 px) + Höhenprofil + Wegpunkt-Sidebar (1fr / 360px).
- [ ] Keine Lat/Lon-Inputs; Wegpunkte werden per Karte/Profil-Klick bearbeitet.
- [ ] Pausentag-Etappe zeigt `PauseStageView` (keine Karte/Wegpunkte).
- [ ] „Speichern" + „Vorschläge neu berechnen" sitzen in der Page-Chrome, nicht im Panel.
- [ ] `WaypointEditorPage.svelte` existiert nicht mehr; keine toten Imports/Routen.
- [ ] Es gibt **keinen** separaten „Wegpunkte"-Tab.
- [ ] #296 ist aktualisiert (Karte erlaubt, Koordinaten-Inputs weiterhin verboten).

---

## Out of Scope (Folge-Issues)

- Echte Leaflet-Integration / Tile-Caching (eigenes Backend-Issue).
- Automatische Wegpunkt-Erzeugung aus der GPX (separat) — erzeugte und manuelle Wegpunkte sind in der UI gleichwertig, keine Unterscheidung.
- Drag-Reorder-Persistenz der Etappen (falls noch offen).
