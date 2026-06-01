# Mobile-Patterns · Gregor Zwanzig

Verbindliche Pattern-Entscheidungen für die Mobile-Erweiterung. Abgeleitet aus
iOS HIG / Material Guidelines und der bestehenden Desktop-Sprache von Gregor 20.

---

## §A · Mapping Mobile-Screen ↔ Desktop-Screen

| Mobile (JSX-Datei)                       | Desktop-Pendant                  | Pattern-Hauptentscheidung                            |
|------------------------------------------|----------------------------------|------------------------------------------------------|
| `screen-login-mobile.jsx`                | — (Desktop: kein Login)          | Vollbild · Magic-Link primär, Passkey sekundär       |
| `screen-design-system-mobile.jsx`        | `screen-design-system.jsx`       | Single-Column Token-Reference                        |
| `screen-home-mobile.jsx`                 | `screen-home.jsx`                | Vertikaler Card-Stack mit Hero                       |
| `screen-trips-mobile.jsx`                | `screen-trips.jsx`               | **Card-Stack** statt Tabelle, Aktionen in Sheet      |
| `screen-trip-detail-mobile.jsx`          | `screen-trip-detail.jsx`         | Hero + horizontal scrollbarer Tab-Streifen (Pill)    |
| `screen-trip-wizard-mobile.jsx`          | `screen-trip-wizard.jsx`         | **4 Vollbild-Schritte**, sticky Action-Bar           |
| `screen-waypoint-editor-mobile.jsx`      | `screen-waypoint-editor.jsx`     | **Karte vollbild + 3-Snap-Bottom-Sheet**             |
| `screen-metrics-editor-mobile.jsx`       | `screen-metrics-editor.jsx`      | Preset-Picker H-Scroll + 5 Kategorie-Accordions + Kanal-Vorschau (Issue #496) |
| `screen-alert-config-mobile.jsx`         | `screen-alert-config.jsx`        | Modus-Cards + Metrik-Liste mit Inline-Threshold-Editor |
| `screen-compare-list-mobile.jsx`         | `screen-compare-list.jsx`        | **Kachel-Stack** (Charter §3 v1.1) — Tap → Detail   |
| `screen-compare-detail-mobile.jsx`       | `screen-compare-detail.jsx`      | Setup + Monitoring-Grid + Aktionen-Sheet            |
| `screen-location-new-mobile.jsx`         | `screen-location-new.jsx`        | 3-Step-Modal-Flow                                    |
| `screen-output-preview-mobile.jsx`       | `screen-output-preview.jsx`      | Segmented Control: Email · SMS · Signal              |
| `screen-patterns-mobile.jsx`             | —                                | Cross-Cutting: Shell · Modal · Sheet · Toast · States |

---

## §B · Breakpoint-Logik

```
≤ 599 px        → Mobile-Layout (alle Mobile-Screens dieses Bundles)
                  Primärziel: 375 px. Sekundärziel: 414 px.

600 – 899 px    → Mobile-Wide / kleine Tablets
                  Layout = Mobile, aber Card-Reihen dürfen 2-spaltig werden
                  (Übersicht: Briefings + Alerts side-by-side; Compare: Banner
                   neben Preset-Header). Bottom-Nav bleibt.

≥ 900 px        → Desktop (bestehendes Layout, unverändert).
```

Implementierung in `app.css` (Empfehlung):

```css
/* Mobile-first base. */
.gz-layout       { display: flex; flex-direction: column; }
.gz-screen-pad   { padding: var(--g-s-4); }
.gz-hide-mobile  { display: none; }
.gz-show-mobile  { display: block; }

@media (min-width: 600px) {
  .gz-cards-grid { grid-template-columns: 1fr 1fr; }
}

@media (min-width: 900px) {
  .gz-layout      { flex-direction: row; }   /* Sidebar einblenden */
  .gz-screen-pad  { padding: var(--g-s-10); }
  .gz-hide-mobile { display: revert; }
  .gz-show-mobile { display: none; }         /* BottomNav, TopAppBar weg */
}
```

`window.innerWidth`-Reads im Skript vermeiden — alles über CSS-Queries.

---

## §C · Navigation (Hybrid)

**Entscheidung:** Bottom-Nav für 4 Top-Destinationen + Drawer für Konfiguration.

### Bottom-Nav (`<BottomNav>`)
- 4 Items, Höhe 64 px, Safe-Area-Bottom additiv.
- Items: `Übersicht · Trips · Vergleich · Archiv`.
- Aktiv-Indikator: 2 px Accent-Strich oben (gleicher Token wie Desktop-Sidebar-LeftBorder).
- Badge-Counter im Mono-Font, 14 px Pille, Akzent-Hintergrund.
- Touch-Höhe pro Item: gesamte Nav-Höhe minus Padding = 56 px effektiv.

### Top-App-Bar (`<TopAppBar>`)
- 56 px hoch, 1 px Hairline `--g-rule-soft` unten (nur wenn gescrollt).
- Links: Hamburger / Back / Close (44 × 44 IconBtn).
- Mitte: Eyebrow (Mono, 9 px, Caps) + Title (15–17 px, semibold).
- Rechts: 1–2 IconBtns (Bell/Plus/Share/More), je 44 × 44.

### Drawer (`<Drawer>`)
- 296 px breit, slide-in von links.
- Inhalt: Logo · Workspace-Items · Konfiguration · User-Footer.
- Schließt durch: Backdrop-Tap, Close-Button, Swipe-Left, ESC.
- Safe-Area-Top und -Bottom respektieren.

### Wann welche Variante
| Screen-Typ                              | TopBar | BottomNav |
|-----------------------------------------|--------|-----------|
| Standard-Workspace (Home/Trips/etc.)    | ✓ menu | ✓         |
| Trip-Detail                             | ✓ back | ✓         |
| Wizard (4 Schritte)                     | ✓ back | **aus**   |
| POI-Import (Smart-Import-Flow)          | ✓ close| **aus**   |
| Waypoint-Editor                         | ✓ back | **aus**   |
| Metriken / Alerts (modal-artig)         | ✓ back | **aus**   |
| Output-Vorschau                         | ✓ back | **aus**   |
| Login                                   | **aus**| **aus**   |
| Patterns: Drawer offen / Sheet offen / Toast / States | wie zugrundeliegender Screen | — |

---

## §D · Listen / Tabellen

**Entscheidung:** Card-Stack für Master-Listen · H-Scroll für dichte Matrizen.

### Card-Stack
Verwendet für: Trip-Liste, Etappen-Liste, Wegpunkt-Liste, Locations-Liste,
Metrik-Items im Accordion.

Anatomie:
- Padding 14 px (sm) bis 16 px.
- Status-Dot links (7–9 px) für aktiven/Status-Indikator.
- Hauptinfo + Mono-Subline.
- Aktionen rechts: entweder Inline (max. 3 Buttons), sonst `IconBtn kind="more"` → Sheet.
- Aktiver/selected Eintrag: 3 px Accent-Left-Border, Tint-Background `--g-accent-tint`.

### H-Scroll mit sticky 1. Spalte
Verwendet für: Stunden-Verlauf Top-3, Wetter-Metriken-Tabelle. (Die frühere Compare-Konsum-Matrix ist entfallen — Charter §3 v1.1: Compare ist Liste → Detail, kein Briefing-Reader.)

Implementierung:
- `display: inline-flex` Container in `overflow-x: auto`-Wrapper.
- `position: sticky; left: 0; z-index: 2;` auf erster Spalte.
- `WebkitOverflowScrolling: touch` + `scrollbar-width: none`.
- Spaltenbreite 88–110 px, ergibt 2-3 sichtbar bei 375 px.
- Best-Wert pro Zeile farbig hinterlegt (`rgba(61,107,58,0.08)`).
- Touch-Affordance: Hinweis-Mono "→ scrollen" über der Tabelle.

---

## §E · Wizard (4 Schritte)

**Entscheidung:** Jeder Schritt = eigener Vollbild-Screen.

Anatomie pro Schritt:
1. **Sticky Top** (TopAppBar): Eyebrow `Schritt N von 4 · Neuer Trip`, Title des aktuellen Schritts, Back-Icon links, Abbrechen-Text rechts.
2. **Step-Indicator** unter TopBar: 4-Segment-Bar, gefüllt bis aktueller Schritt, je 3 px hoch.
3. **Scrollbarer Content**: vertikal, Card-Stack.
4. **Sticky Bottom-Action-Bar**: `← Zurück` (Ghost) + `Weiter · {nächster Title} →` (Primary). Auf Schritt 4 wird Primary zu `Trip anlegen` (Accent).

**Bottom-Nav während Wizard**: ausgeblendet. Wizard ist linearer Flow; Vermischung mit Workspace-Nav führt zu Datenverlust-Risiko.

**Schritt-spezifische Anpassungen vs. Desktop**:
- *Schritt 1 (Profil)*: 2-spaltiges Desktop-Layout → vertikale Cards.
- *Schritt 2 (GPX)*: Drop-Zone full-width, Vorlagen-Card als Accordion unten kollabiert.
- *Schritt 3 (Wegpunkte)*: Etappenliste links wird zu **Pill-Scroller oben**; Vorschläge darunter full-width.
- *Schritt 4 (Briefings)*: 2 Spalten → sequentiell, Threshold-Liste kompakt.

---

## §F · Modal vs. Bottom-Sheet

| Use-Case                                | Pattern        | Begründung                                 |
|-----------------------------------------|----------------|---------------------------------------------|
| Wizard (Trip-Anlage)                    | **Modal-Flow** | Linear, mehrere Schritte, eigene Route      |
| POI-Import (Smart-Import)               | Modal-Flow     | Auch linear (Quelle → URL → Vorschlag)      |
| Bestätigung "Trip löschen"              | Modal          | Destruktiv, blockt User-Flow                |
| Email-Vorschau (Detail-Ansicht)         | Modal          | Eigenständige Lesefläche                    |
| **Wizard-Abbruch**                      | **Bottom-Sheet** | 3-Optionen-Fork (Entwurf / Verwerfen / Weiter) |
| Aktionen-Menü ("•••")                   | Bottom-Sheet   | Kontextuelle Wahl, nicht-blockend          |
| Locations auswählen (Compare)           | Bottom-Sheet   | Multi-Select + Suche                         |
| Etappen-Auswahl (Wegpunkt-Editor)       | Bottom-Sheet   | Skaliert für 13+ Etappen                    |
| Wegpunkt-Edit (Vorschlag)               | Sheet (peek/half/full) | Bleibt Karte sichtbar              |
| Filter / Sort                           | Bottom-Sheet   | Quick-Edit                                  |
| Push-Permission Pre-Prompt              | **Vollbild-Screen** | Einmaliger Moment, Hero-IconBüne nötig |

### Sheet-Snap-Points
`peek` (32 % bzw. fix 92 px), `half` (55 %), `full` (84–90 %). Drag-Handle 36 × 4 px,
Backdrop `rgba(26,26,24,0.42)`. Dismiss: Backdrop-Tap, Drag-Down, Close-Button.

### Wizard-Abbruch (verbindlich)
Wann immer ein mehrstufiger Flow (Wizard, POI-Import, Login mit OTP) durch Close
verlassen wird **und der User schon Daten eingegeben hat**, muss ein Bottom-Sheet
mit drei Optionen erscheinen:

1. **Als Entwurf speichern** (Accent) — landet in Trips-Liste mit `status: draft`.
2. **Weiter editieren** (Ghost) — Sheet schließt, Flow läuft weiter.
3. **Verwerfen** (Ghost-Bad) — destruktiv, mit Bad-Akzent.

Hat der User noch nichts eingegeben → direkter Close ohne Sheet.

### Push-Permission Pre-Prompt (verbindlich)
Niemals direkt das native System-Permission-Dialog ohne Vorlauf zeigen — es kann
nur einmal pro App-Installation aufgerufen werden. Stattdessen Pre-Prompt
(`PatternPushPermission`):

- **Wann zeigen**: einmalig nach erstem `Alert-Konfig speichern`. Fallback: nach
  erstem Trip-Anlegen, wenn noch kein Alert konfiguriert.
- **Wenn User „Aktivieren" tappt**: native Permission-Dialog triggern.
- **Wenn User „Später" tappt**: Pre-Prompt-Counter erhöhen; in 7 Tagen oder bei
  nächster Alert-Auslösung erneut zeigen. Nach 3× ignoriert → in Settings
  verfügbar machen, aber nicht mehr proaktiv aufschlagen.
- **Wenn User schon einmal in System-Dialog „Nein" gewählt hat**: Pre-Prompt
  zeigen, aber der „Aktivieren"-Button öffnet die OS-Settings (Deep-Link), nicht
  den System-Dialog (der ist verbrannt).

---

## §G · Progressive Disclosure

| Wo                          | Wie                                                              |
|-----------------------------|------------------------------------------------------------------|
| Trip-Detail Tabs            | 6 Tabs in horizontal scrollbarem Pill-Strip (MTab)              |
| Etappen-Card                | Eckdaten initial sichtbar, Summary nur in Detail-Sheet           |
| Metriken-Editor             | 5 Kategorie-Accordions, default Temp + Wind offen                |
| Compare-Detail              | Setup-Cards (Orte/Idealwerte/Layout/Versand) + Vorschau-Prüfung; kein Tages-Briefing |
| Output-Preview              | 3-Kanal Segmented Control (Email · SMS · Signal)                 |
| Drawer                      | Settings/Channels nur dort, nicht in Bottom-Nav                  |

---

## §H · Touch & Type · Mindestmaße

| Kategorie                       | Mobile-Wert | Token                                  |
|---------------------------------|-------------|-----------------------------------------|
| Minimum Touch-Target            | 44 × 44 px  | iconBtn / Switch-Hit-Area               |
| Standard Button (`MBtn lg`)     | 48 px hoch  | Card-CTAs, Sticky-Action-Bar            |
| Focus-CTA (`MBtn xl`)           | 56 px hoch  | Login, primäre Anlage-Aktionen          |
| Input-Höhe (`MInput`)           | 48 px       | minHeight                               |
| Input-Font-Size                 | **16 px**   | `MInput` hartcodiert (iOS-Anti-Zoom)    |
| Bottom-Nav Item                 | 64 px hoch  | + env(safe-area-inset-bottom)           |
| Top-App-Bar                     | 56 px hoch  | TOPBAR_H Konstante                      |
| Sticky Action-Bar (Wizard etc.) | 56–72 px    | + env(safe-area-inset-bottom)           |

---

## §I · Safe-Areas

- `padding-top: env(safe-area-inset-top)` auf App-Shell-Root.
- `padding-bottom: env(safe-area-inset-bottom)` auf jeder Sticky-Bottom-Komponente
  (BottomNav, Wizard-Actions, Toast).
- In den JSX-Mockups als Konstanten `SAFE_TOP = 44` / `SAFE_BOTTOM = 34` enthalten —
  in Production durch echte `env()`-Werte ersetzen.

---

## §J · Verbindliche Komponenten-Namen

Damit Hand-off + Production konsistent bleiben:

**Übernommen aus Desktop (unverändert):**
`Card · Pill · Eyebrow · Dot · WIcon · ElevSparkline · Logo · TopoBg`

**Neu für Mobile (`mobile-shell.jsx`):**
`MobileShell · PhoneFrame · TopAppBar · BottomNav · Drawer · Sheet · Toast ·
IconBtn · MIcon · MInput · MField · MBtn · MSwitch · MTab · ScreenScroll`

**Mobile-Screen-Komponenten** tragen das Suffix `Mobile`
(`ScreenHomeMobile`, `ScreenTripsMobile`, …) — 1:1-Mapping zu Desktop.

---

## §K · Was NICHT verändert wurde

- Tokens (`tokens.css`)
- Farbpalette / Akzent-Logik
- Schriftfamilien
- Status-/Risk-Semantik (good/warn/bad)
- Icon-Set (gleiche SVG-Strokes, gleicher Stil)
- Brand-Logo

Wenn ein Mobile-Screen ein Symbol zeigt, das im Desktop noch nicht existiert (z. B.
`MIcon kind="drag"` oder Bottom-Sheet-Drag-Handle), folgt es derselben Stroke-Sprache
(1.7 px, round, monochrom, `currentColor`).
