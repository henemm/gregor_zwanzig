# SOLL-Coverage — Epic #575 (1:1-Frontend-Reimplementierung)

> **HISTORISCH seit ADR-0111 Punkt 5 (2026-11-09, #2881).** Die Soll-Bilder in diesem Ordner und die
> JSX-Vorlagen bilden den Stand von Epic #575 (Juni 2026) ab (u. a. entfernter Signal-Kanal, alter
> Schritt-Wizard, „Meine Touren"). Sie sind **nicht mehr bindend**. Maßstab sind
> `docs/reference/design_system.md`, das Mockup Fassung 3
> (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`) und die Playwright-Paritäts- und
> Kontrasttests. `design_fidelity_diff.py` und das Design-Gate `pre_issue_close_design_gate.py` sind
> außer Dienst. Der Text unten bleibt als Archiv unverändert.

**Stand:** 2026-06-04 · **Quelle der Wahrheit:** `current/jsx/` (JSX = bindend) + `current/soll/` (Screenshot = visuell bindend).
**Render-Host für JSX:** `../../_soll-render.html?s=<key>` (Projekt-Root) bzw. die Artboards in `../../Gregor 20 - Desktop.html`.

> **Prozess pro Screen (aus Epic #575):** `current/jsx/screen-X.jsx` + `atoms.jsx` + `tokens.css` lesen → 1:1 nach Svelte → Playwright-Screenshot → `fresh-eyes-inspector` SOLL-IST → PASS. **Keine Interpretation, keine eigenen Design-Entscheidungen.**

---

## Phase 1 — Fundament (sequenziell)

| Issue | JSX-Quelle (`current/jsx/`) | Anmerkung |
|---|---|---|
| **#576 [A]** Tokens | `tokens.css` | Bereits wertgleich in `frontend/src/app.css` (geprüft 2026-06-03). Diff nur `--g-paper-deep`. Sync = `:root` + `.dark` abgleichen. |
| **#577 [B]** Atoms | `atoms.jsx` | Inkl. `brand-kit.jsx` (Grundgesetz). **Achtung Glyphs** → siehe ⚠️ unten. |
| **#578 [C]** Molecules + Organisms | `molecules.jsx`, `organisms.jsx`, `sidebar.jsx` | `QuickAction`, `BriefingTimelineRow`, `CompareStatusRow`, `SetupResumeCard` etc. |

---

## Phase 2 — Screens (parallel nach A+B+C)

| Issue | JSX-Quelle (`current/jsx/`) | SOLL-Bild (`current/soll/`) | Status |
|---|---|---|---|
| **#579 [D]** Home | `screen-home.jsx` (Trip + `mode="compare"`), `screen-home-planning.jsx` | `D-home-trip.png`, `D-home-compare.png`, `D-home-planning.png` | ✅ |
| **#580 [E]** Trips-Liste | `screen-trips.jsx` | `E-trips-list-variant.png` | 🟡 nur Variante — voll-SOLL empfohlen |
| **#581 [F]** Trip-Detail | `screen-trip-detail.jsx`, `screen-trip-edit-tabs.jsx` | `F-trip-detail-*.png` (5) | ✅ |
| **#582 [G]** Compare | `screen-compare-detail.jsx`, `screen-compare-list.jsx`, `screen-compare-wizard.jsx` | `G-compare-*.png` (7) | ✅ |
| **#583 [H]** Archiv | `screen-archive.jsx` | `H-archive.png` | ✅ |
| **#584 [I]** Wizard | `screen-trip-wizard.jsx` | `I-wizard-step1..5-*.png` (5) | ✅ |
| **#585 [J]** Waypoint-Editor | `screen-waypoint-editor.jsx` | `J-waypoint-editor-etappen-tab.png` | ✅ |
| **#586 [K]** Alert-Config | `screen-alert-config.jsx` | `K-alert-config-list.png` | 🟡 nur Liste — Editor-State fehlt |
| **#587 [L]** Metrics-Editor | `screen-metrics-editor.jsx` (+ `screen-channel-preview-redesign.jsx`, `screen-output-preview.jsx`) | `L-metrics-editor-*.png` (4) | ✅ |
| **#588 [M]** Location-New | `screen-location-new.jsx` | `M-location-new.png` | ✅ |

---

## ⚠️ Was die JSX-Vorlage NICHT abbildet — explizit in die Issues schreiben

Diese Punkte kann ein 1:1-JSX→Svelte-Übersetzer nicht aus dem Markup ableiten. Sie gehören als **Acceptance Criteria** in die jeweiligen Issues, sonst reproduziert der Rebuild dieselben Fehler:

1. **#577/#578 · `QuickAction` braucht echte Icons, keine ASCII-Glyphs.** Die aktuelle Impl (`#573`) rendert `->`, `##`, `>>`, `[]`. Die JSX-Vorlage (`QuickActionGlyph` in `molecules.jsx`) definiert **Inline-SVG-Line-Icons** (`route/metrics/clock/eye`). Beim Port die SVG-`<path>`-Daten **verbatim** übernehmen — Inline-SVG ist SSR-sicher und dep-frei, der „kein-Lucide"-Einwand greift nicht.

2. **#579 · Home: zwei Daten-Bugs, die im JSX schon korrekt sind, aber an der Daten-Verdrahtung hängen:**
   - **Briefing-Zeit ohne Sekunden.** JSX zeigt `06:00`. Beim Verdrahten `report_config.morning_time/evening_time` (DB = `HH:MM:SS`) auf `HH:MM` trimmen (`cockpitHelpers.ts`). Sonst erscheint `06:00:00`.
   - **Keine doppelten Archiv-Trips.** „Außerdem laufende" Trip-Liste muss `status === 'fertig'` ausschließen, sonst erscheint ein abgeschlossener Trip (z. B. „GR221 Mallorca") gleichzeitig als lose Kachel **und** im Archiv-Grid.

3. **#579 · Home-Vollständigkeit (Regressionsschutz).** Die kanonische JSX-Home ist die **reiche** Version: Topbar mit `Neuer Trip` + `Neuer Vergleich` (beide ghost), Hero mit 2 Pills + Route-Untertitel + Fortschritt **unter** dem Titel + Kanal-Footer-Leiste, Outbox „Versand · heute" + „Alle Kanäle ok"-Pille, Alerts mit „Schwellen →"-Link. Die deployte Version hatte vieles davon entfernt (folgte dem von #575 überschriebenen #568). **PASS-Kriterium: 1:1 zur JSX, nichts weglassen.**

4. **#579 · Schnellaktionen in der linken Hero-Spalte (PO 2026-06-04).** Die Schnellaktionen stehen **nicht** als volle Breitenzeile unter dem Cockpit, sondern **vertikal gestapelt direkt unter dem Hero** in der linken Spalte — dadurch füllen sie den Raum neben Outbox/Alerts und sind klar dem aktiven Trip/Vergleich zugeordnet. Letzte Aktion ist der **kontextbezogene Test-Versand** (`glyph="send"`, „Test-Briefing schicken" bzw. „Test-Vergleich schicken", Sub „→ An deine eigenen Kanäle"). Die frühere kontextlose Topbar-Aktion „Test an mich" wurde **entfernt** und durch diese ersetzt.

5. **#587 [L] · Email-Bausteine liegen in `screen-output-preview.jsx`, NICHT in Atoms/Molecules.** Die Komponenten `EmailEyebrow`, `EmailTag`, `EmailStat`, `EmailSegmentBlock`, `EmailDataTable` (und `EmailHourList`) sind **lokale Helfer-Funktionen am Dateiende von `current/jsx/screen-output-preview.jsx`** (ab ca. Zeile 219), absichtlich NICHT in `atoms.jsx`/`molecules.jsx` — es sind reine Email-Renderer-Bausteine, kein App-UI. Wer sie sucht oder portiert, liest `screen-output-preview.jsx`. Eine Meldung „atoms.jsx/molecules.jsx fehlen, weil EmailEyebrow nicht drin" ist ein **Fehlbefund** (falsche Datei). **Hinweis Mobile-Renderer:** `screen-output-preview.jsx` und die Mobile-Screens brauchen `mobile-shell.jsx` (`PhoneFrame`, `MBtn`, `MField` …) — seit 2026-06-21 in `current/jsx/` enthalten.

---

## SOLL-PNGs neu erzeugen (Home / Archiv)

Die Home- und Archiv-SOLL-Bilder werden aus der JSX gerendert (nicht aus der deployten App):
`_soll-render.html?s=home | home-compare | home-planning | archive` im Projekt-Root öffnen.
Nach **jeder** Änderung an `screen-home.jsx` / `screen-archive.jsx` neu rendern und die PNGs in
`current/soll/` ersetzen, damit das SOLL-IST-Gate gegen den aktuellen Stand prüft.

---

## Sync-Disziplin (CLAUDE.md)

`current/jsx/` und `current/soll/` sind **Schnappschüsse** der kanonischen Wurzel-Dateien (echte Symlinks sind in dieser Umgebung nicht möglich). **Bei jeder Änderung an einer Wurzel-`screen-*.jsx` / `atoms.jsx` / `tokens.css` den Schnappschuss hier mitziehen** — sonst übersetzt Claude Code gegen einen veralteten Stand.
