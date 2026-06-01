# ANTI-PATTERNS

> Negativliste. Wenn ein Issue, ein PR, ein Mockup oder eine Implementierung gegen einen dieser Punkte verstößt, wird **stehengelassen, hinterfragt und korrigiert** — nicht durchgewinkt.
>
> Format: jedes Anti-Pattern hat einen Namen (greppbar), einen Erklärungs-Block, ein Beispiel **falsch** und ein Beispiel **richtig**. Claude Code kann dieses Dokument als Self-Review-Checklist nutzen.

---

## AP-001 · Native HTML-Controls in Forms

**Verboten:** native `<input type="checkbox">`, `<select>`, `<input type="date">`, `<input type="time">`, native Radio-Buttons.

**Warum:** Browser-Defaults überschreiben die Brand-Identität, das Verhalten ist plattform-uneinheitlich, Accessibility-Customization ist limitiert.

**Falsch:**
```svelte
<input type="checkbox" bind:checked={active} />
<select bind:value={template}>...</select>
```

**Richtig:**
```svelte
<Checkbox bind:checked={active} label="Trip aktiv" />
<Select bind:value={template} options={templates} />
```

---

## AP-002 · Lat/Lon-Eingabe-Felder

**Verboten:** numerische Eingabefelder für Latitude/Longitude im Wegpunkt-Editor oder Ort-Anlegen-Dialog.

**Warum:** Spec `ux_redesign_navigation.md §2`: Wegpunkte werden **visuell auf der Karte** gesetzt oder durch algorithmische Vorschläge ergänzt. Lat/Lon ist Implementierungs-Detail, nicht UI.

**Falsch:**
```svelte
<Input label="Latitude" bind:value={lat} />
<Input label="Longitude" bind:value={lng} />
```

**Richtig:**
```svelte
<MapEditor on:point-add={handlePoint} suggestions={algoSuggestions} />
<!-- Punkte als Marker auf Karte, klickbar -->
```

---

## AP-003 · Tabellen-Layout für Trip-/Ort-/Vergleichs-Listen

**Verboten:** `<table>` als primäre Struktur für `meine-trips`, `archiv`, `orts-vergleich` (Liste der Vergleiche, nicht die Matrix), `wetter-templates`.

**Warum:** Charter §3: Listen, in denen jedes Item ein Einstiegspunkt ist, werden als **Kachel-Grid** dargestellt. Tabellen sind nur für stündliche Daten (Wetter) und Hourly-Matrix.

**Falsch:**
```svelte
<table>
  <tr><th>Name</th><th>Datum</th><th>Etappen</th><th>Aktionen</th></tr>
  {#each trips as t}<tr>...</tr>{/each}
</table>
```

**Richtig:**
```svelte
<PageTileGrid>
  {#each trips as t}<Tile type="trip" {...t} />{/each}
</PageTileGrid>
```

---

## AP-004 · Mehrere Primäraktionen pro Screen

**Verboten:** Zwei oder mehr Buttons mit `variant="primary"` oder `variant="accent"` auf demselben Screen.

**Warum:** Charter §6: Genau eine Primäraktion. Sekundäres geht ins `<DropdownMenu>`.

**Falsch:**
```svelte
<Btn variant="accent">+ Neuer Trip</Btn>
<Btn variant="accent">Briefing senden</Btn>
<Btn variant="primary">Exportieren</Btn>
```

**Richtig:**
```svelte
<Btn variant="accent">+ Neuer Trip</Btn>
<DropdownMenu>
  <DropdownItem>Briefing senden</DropdownItem>
  <DropdownItem>Exportieren</DropdownItem>
</DropdownMenu>
```

---

## AP-005 · Icon-Soup auf Listen-Items

**Verboten:** Mehr als ein Icon-Button (≠ Kebab) pro Listen-Zeile.

**Warum:** Issue #05 + Charter §6. Die Liste ist eine Navigations-Oberfläche. Klick auf den Namen geht ins Detail; sekundäres in den Kebab.

**Falsch:**
```svelte
<TileRow>
  <Name />
  <IconBtn kind="alert" />
  <IconBtn kind="send" />
  <IconBtn kind="test" />
  <IconBtn kind="preview" />
  <IconBtn kind="edit" />
  <IconBtn kind="trash" />
</TileRow>
```

**Richtig:**
```svelte
<TileRow on:click={() => goto(`/trips/${t.id}`)}>
  <Name />
  <Status />
  <DropdownMenu trigger="kebab" />
</TileRow>
```

---

## AP-006 · Eigene Implementierung katalogisierter Komponenten

**Verboten:** Lokale Implementierungen von Komponenten, die im Katalog (`COMPONENTS.md`) existieren — auch wenn sie "nur ein bisschen anders" sind.

**Warum:** Drift ist die Hauptquelle für Inkonsistenz. Wenn der Katalog die Komponente nicht abdeckt: Katalog erweitern, dann nutzen.

**Falsch:**
```svelte
<div style="background: #1a1a18; color: white; padding: 12px; ...">Toast</div>
<!-- eigener Toast statt <Toast> -->
```

**Richtig:**
```svelte
<Toast tone="success">Trip gespeichert.</Toast>
```

---

## AP-007 · Inline-Hex-Farben

**Verboten:** Hex-Codes in `style=`-Attributen oder CSS-Regeln außerhalb von `tokens.css`.

**Warum:** Charter §5. Farbe ist eine semantische Entscheidung, kein Hex-Wert.

**Falsch:**
```css
.warning-bg { background: #fef3c7; }
```
```svelte
<div style="color: #c45a2a;">Accent-Text</div>
```

**Richtig:**
```css
.warning-bg { background: rgba(192,138,26,0.06); border: 1px solid var(--g-warn); }
```
```svelte
<div style="color: var(--g-accent);">Accent-Text</div>
```

---

## AP-008 · Magic-Pixel-Spacing

**Verboten:** `padding`, `margin`, `gap`, `width`, `height` Werte, die nicht aus `--g-s-*` (Spacing) oder semantisch erklärt sind.

**Erlaubt:** Werte aus `--g-s-1` bis `--g-s-20`, plus semantische Werte (z. B. `width: 100%`, `height: 100vh`, `width: 1px` für Trennlinien, `44px` für Touch-Target).

**Falsch:**
```css
.card { padding: 17px 23px; gap: 9px; }
```

**Richtig:**
```css
.card { padding: var(--g-s-5) var(--g-s-6); gap: var(--g-s-2); }
```

---

## AP-009 · Emoji im Produkt-UI

**Verboten:** Emoji-Zeichen (`✓` `❌` `⚠️` `🟢` `🔴` `📍` `🗺` etc.) als Status-Icons oder dekorative Elemente.

**Warum:** Renderingsunterschiede zwischen OS, kein Token-Anschluss, ästhetisch instabil.

**Falsch:**
```svelte
<span>✓ Verbunden</span>
<span>⚠️ Warnung</span>
```

**Richtig:**
```svelte
<Dot tone="good" /> Verbunden
<Pill tone="warn">Warnung</Pill>
```

**Ausnahme:** Mathematische Zeichen `±`, `≤`, `≥`, `≈`, `Δ`, Pfeile `↑` `↓` `→` `←` für numerische / Richtungs-Information sind erlaubt.

---

## AP-010 · "Cockpit"-Style Startseite

**Verboten:** Dichte Dashboards mit ActiveTripCard + StageStrip + BriefingsTimeline + AlertFeed + Stats-Grids auf der Startseite.

**Warum:** Spec `ux_redesign_navigation.md §1` und Issue #03: Startseite ist **Kachel-Übersicht**, kein Live-Cockpit. Wer Live-Daten will, geht in Trip-Detail.

**Falsch:** Startseite mit 6 dichten Sektionen voller Mini-Charts.

**Richtig:** Kachel-Grid mit Trips und Vergleichen + Empty-State + Quick-Actions zum Anlegen.

---

## AP-011 · Eigene Page-Header

**Verboten:** Lokal gebaute Page-Header (Title + Eyebrow + Right-Slot) statt der `<PageHeader>`-Komponente aus dem Katalog.

**Warum:** Charter §10: Komponenten-Namen sind Verträge. Jeder Page-Header muss `<PageHeader>` heißen.

**Falsch:**
```svelte
<div class="my-page-header">
  <span class="eyebrow">TRIPS</span>
  <h1>Meine Trips</h1>
  <Btn>+ Neuer Trip</Btn>
</div>
```

**Richtig:**
```svelte
<PageHeader eyebrow="TRIPS" title="Meine Trips">
  <svelte:fragment slot="right">
    <Btn variant="accent">+ Neuer Trip</Btn>
  </svelte:fragment>
</PageHeader>
```

---

## AP-012 · Floating Action Button (FAB)

**Verboten:** Auch auf Mobile — kein schwebender Plus-Knopf unten rechts.

**Warum:** Charter §6. Primäraktion gehört in den Page-Header, auch auf Mobile (rechts neben Title als Icon-Button, falls Platz knapp).

---

## AP-013 · Standalone Wetter-Seite

**Verboten:** `/weather` als eigener Nav-Bereich oder Top-Level-Route mit eigenständigem Layout.

**Warum:** Charter §2 + Issue #309. Wetter ist immer ein Drill-Down aus Kontext (Etappe oder Ort).

**Falsch:**
```svelte
<!-- /routes/weather/+page.svelte als eigene Seite -->
<PageHeader title="Wetter" />
<HourlyTable />
```

**Richtig:**
```svelte
<!-- Slide-Panel als Sibling zu Trip-Detail / Compare -->
<TripDetail>
  <Etappe on:click={openWxDrillDown} />
</TripDetail>
<WxDrillDownPanel bind:open />
```

---

## AP-014 · Inkonsistente Copy

**Verboten:** Verwendung von Tabu-Wörtern aus `COPY.md §9`.

**Häufige Sünder:** "Tour" statt "Trip", "Account" statt "Konto", "Notification" statt "Briefing", "Editieren" statt "Bearbeiten", "Erstellen" statt "Anlegen".

**Vorgehen:** Vor jedem Commit `grep -wi` für die Tabu-Begriffe laufen lassen.

---

## AP-015 · Speaker-Notes-Stil-Texte im UI

**Verboten:** Lange erklärende Paragraphen in Help-Tooltips, Empty-States, Modal-Body, die wie "Speaker-Notes" wirken.

**Warum:** Charter §1: nüchtern, keine Werbesprache. Wenn der User es lesen soll, sage es in einem Satz. Wenn mehr Erklärung nötig ist, gehört es in Dokumentation, nicht ins UI.

**Faustregel:** Helper-Text max. 2 Zeilen. Empty-State-Body max. 1 Satz.

---

## AP-016 · Padding/Margin auf Container, der `display: flex/grid` mit `gap` nicht nutzt

**Verboten:** Per-Element-Margins (`margin-bottom: 12px` auf jedem Child) für Listen-Layouts.

**Warum:** `gap` ist explizit und überlebt DOM-Edits.

**Falsch:**
```css
.list > .item { margin-bottom: 12px; }
```

**Richtig:**
```css
.list { display: flex; flex-direction: column; gap: var(--g-s-3); }
```

---

## AP-017 · Drift in der Schrift-Skala

**Verboten:** `font-size`-Werte, die nicht aus `--g-text-*` Tokens kommen.

**Erlaubt:** `--g-text-xs` (11), `--g-text-sm` (13), `--g-text-md` (15), `--g-text-lg` (17), `--g-text-xl` (20), `--g-text-2xl` (24), `--g-text-3xl` (32), `--g-text-4xl` (44), `--g-text-5xl` (60).

**Mobile-Minimum für Body-Input:** 16 px (verhindert iOS Auto-Zoom). Falls als Token nötig: `--g-text-base-mobile`.

---

## AP-018 · CSS-Animationen mit Bounce/Elastic

**Verboten:** `cubic-bezier(.34,1.56,.64,1)` und ähnliche Spring-Easings für UI-Übergänge.

**Erlaubt:** `ease`, `ease-out`, `linear`, `cubic-bezier(.4,0,.2,1)` (Material standard). Dauer 120–240 ms für UI-State-Changes.

**Warum:** Charter §5: nüchtern, kein verspielter Material-Lift.

---

## AP-019 · Lange Modal-Cascades

**Verboten:** Modal-Dialog, der ein weiteres Modal öffnet, das ein drittes Modal öffnet.

**Warum:** UX-Sackgasse. Wenn ein Prozess mehr als 1 Modal braucht: Wizard oder eigene Seite.

---

## AP-020 · Status-Pills ohne Tonalität

**Verboten:** Generische graue Pills für unterschiedliche Status. Jeder Status MUSS eine semantische Tonalität haben.

**Falsch:**
```svelte
<Pill>Aktiv</Pill>
<Pill>Pausiert</Pill>
<Pill>Fehler</Pill>
```

**Richtig:**
```svelte
<Pill tone="good">Aktiv</Pill>
<Pill tone="warn">Pausiert</Pill>
<Pill tone="bad">Fehler</Pill>
```

---

## Selbst-Audit-Befehle (für Claude Code)

```bash
# AP-001 — native checkboxes/selects
grep -rn 'type="checkbox"' frontend/src/
grep -rn '<select' frontend/src/

# AP-002 — Lat/Lon-Felder
grep -rn -E 'label="(Latitude|Longitude|Lat|Lon|Lng)"' frontend/src/

# AP-007 — Inline-Hex
grep -rn -E '#[0-9a-fA-F]{3,6}' frontend/src/ \
  | grep -v 'tokens.css' | grep -v '\.md:'

# AP-008 — Magic-Pixel
grep -rnE '(padding|margin|gap):\s*[0-9]+px' frontend/src/

# AP-009 — Emojis
grep -rnP '[\x{1F300}-\x{1F9FF}]|✓|✗|⚠|🟢|🔴|📍|🗺' frontend/src/

# AP-014 — Tabu-Wörter
grep -rwni -E 'Tour|Touren|Account|Notification|Editieren|Erstellen|Cockpit' \
  frontend/src/ | grep -v '\.svelte-kit/'
```

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initiale Negativliste — Runde 1 |
| v1.1 | 2026-05-26 | Kanonisches Vokabular umgedreht: `Trip` ist jetzt User-facing, `Tour`/`Touren` sind tabu. AP-014-Beispiele entsprechend angepasst. |
