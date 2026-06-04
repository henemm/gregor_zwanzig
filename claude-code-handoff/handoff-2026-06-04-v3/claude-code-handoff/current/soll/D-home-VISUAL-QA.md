# Visual-QA — #579 Home · Pass/Fail-Checkliste für den fresh-eyes-inspector

**Zweck:** Die inhaltliche Struktur stimmt — die **gestalterische Ausführung** der deployten Home ist schlampig.
Diese Liste macht „schlampig" **messbar**. Jeder Punkt ist ein FAIL-Kriterium im SOLL-IST-Gate (#575).
**SOLL = `current/jsx/screen-home.jsx`** (gerendert via `_soll-render.html?s=home`).

> Regel: Es wird **nicht interpretiert**. Wenn IST ≠ JSX in einem dieser Punkte → FAIL, zurück in den Build.

---

## 🔴 Blocker (FAIL = kein Merge)

| # | Atom/Component | FAIL-Symptom (IST, schlampig) | PASS-Kriterium (SOLL/JSX) |
|---|---|---|---|
| V1 | **Status-Grid (Page)** | Hero-Karte auf Höhe der rechten Spalte gestreckt → großes leeres Loch unter dem Inhalt. | `align-items: start`. Hero so hoch wie sein Inhalt; der Raum **unter** dem Hero (linke Spalte) wird von den **Schnellaktionen** gefüllt (siehe V13) — **kein** stretch, **kein** Loch. |
| V2 | **`HomeHeroTrip` (Organism)** | Fortschrittsbalken **über** dem Titel, an der Pille klebend; „Trip öffnen" lose im Body. | Reihenfolge: Pills → Titel → Route-Untertitel → **Balken mit Label „Tag x / y" + Datumsrange** → **Footer-Leiste** (`card-alt`) mit Kanal-Dots links + „Trip öffnen →" rechts. |
| V3 | **`HomeHeroTrip` — Kanäle** | „● Email" hängt orphaned im leeren Body, ohne Label/Kontext. | Kanäle sitzen in der Footer-Leiste hinter `Eyebrow` „Kanäle", als Dot-Reihe. Nie frei im Body. |
| V4 | **`QuickAction` (Molecule)** | ASCII-Glyphs `→ ## >> [ ]` — keine visuelle Familie, Platzhalter-Optik. | Inline-SVG-Line-Icons (`route/metrics/clock/eye`), eine Strichstärke, im gerundeten Glyph-Tile. |
| V5 | **„Außerdem beobachtet" (Organism)** | 3 lose Zeilen über volle Breite, riesige Leere in der Mitte, kein Wrapper/Header. | **Eine** `Card` mit `Eyebrow` + Titel + „Alle Vergleiche →"; darin kompakte `CompareStatusRow`-Zeilen. |
| V6 | **`CompareStatusRow` — Konsistenz** | „Heimat" zeigt Email-Pille, andere Zeilen nicht → ragged. | Alle Zeilen gleicher Aufbau; Empfänger-Pille nur wenn gesetzt, **konsistent platziert** (gleiche Spalte). |
| V7 | **Archiv-Sektion (Page)** | Riesen-Karte mit ~80 px Padding umschließt **eine** Mini-Kachel. | `SectionH` (Eyebrow + Titel + Kicker + „Alle anzeigen"-`Btn`) + **4-Spalten-Grid** Archiv-Karten, **ohne** Mega-Wrapper. |
| V13 | **Schnellaktionen (Page-Layout)** | Volle Breitenzeile unterhalb des Cockpits, vom aktiven Trip abgekoppelt. | **Vertikal gestapelt in der linken Hero-Spalte**, direkt unter dem Hero (kompakter Header „Schnell eingreifen / Schnellaktionen", **kein** langer Kicker). Letzte Aktion = Test-Versand (`glyph="send"`, „Test-Briefing/Test-Vergleich schicken"). |

---

## 🟡 Craft (FAIL = nacharbeiten vor Abnahme)

| # | Atom/Component | FAIL-Symptom | PASS-Kriterium |
|---|---|---|---|
| V8 | **`Pill` (Live)** | Zu fette Vollton-Lozenge, Dot küsst „Live", Button-Optik. | Schlankes Status-Tag: geringeres Vertikal-Padding, Dot mit Gap zum Text, Tag-Höhe ≈ Caption. |
| V9 | **`PageHeader` — Topbar** | Langer grauer Beschreibungs-Absatz über volle Breite; schwer. | Eyebrow + Titel (18 px) knapp; Sub kurz/optional, nicht volle Breite. |
| V10 | **`PageHeader` — Aktionen** | „+ Neuer Trip" laut schwarz/primary, „Neuer Vergleich" nackter Link → kein Paar. | Genau **zwei** Buttons — „Neuer Trip" + „Neuer Vergleich", **beide ghost** mit `+`-Icon. **Kein** schwarzer Primary, **keine** kontextlose „Test an mich"-Aktion (die wandert als Schnellaktion in die Hero-Spalte, V13). |
| V11 | **`SectionH` / Eyebrow-Rhythmus** | Sektionsabstände springen; Eyebrow-zu-Inhalt-Gaps uneinheitlich. | Einheitlicher Sektions-Vertikal-Rhythmus (Spacing-Token); gleicher Eyebrow→Inhalt-Gap überall. |
| V12 | **Spaltenbreiten / Alignment** | Hero-Grid rechts fluchtet nicht mit den Zeilen darunter. | Alle Sektionen teilen denselben Content-Container; linke **und** rechte Kante fluchten durchgehend. |

---

## Prüf-Methode (inspector)

1. SOLL rendern: `_soll-render.html?s=home` (+ `home-compare`, `home-planning`).
2. IST: Playwright-Screenshot der gebauten Route bei 1440 Breite.
3. Punkt für Punkt V1–V13 abhaken. **Ein** Blocker offen → FAIL.
4. Besonders auf **Leerflächen** achten (V1, V5, V7): tote Fläche = das auffälligste Schlampigkeits-Signal.

> Diese Defekte sind in der JSX bereits gelöst. „Schlampig" entsteht nur, wenn vom JSX abgewichen wird — das Gate muss genau das fangen.
