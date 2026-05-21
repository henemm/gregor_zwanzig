# Gregor Zwanzig · Design Charter

> **Zweck dieses Dokuments.** Verbindliche Design-Entscheidungen.
> Eine Aussage pro Zeile, keine Alternativen, keine Optionen.
> Wenn ein Issue oder eine Implementierung dieser Charter widerspricht: die Charter gewinnt — oder das Dokument muss vorher geändert werden.
>
> Konsument dieser Datei ist **Claude Code** bei der Svelte-Implementierung.
> Konsument der referenzierten Mockups ist Claude Code zum Visuellen Abgleich.

---

## 0. Geltungsbereich

Diese Charter gilt für die Web-App `gregor.zwanzig` (SvelteKit-Frontend) und ihre Mobile-Web-Variante. Native Apps sind explizit nicht im Scope.

---

## 1. Identität

| Aspekt | Entscheidung |
|---|---|
| Produktname | `gregor.zwanzig` (lowercase, mit Punkt) |
| Wordmark-Variante | **B** — Mono-Schrift, `gregor` + Punkt (ink-4) + `zwanzig` (accent) |
| Caption unter Wordmark | `V0.20 · WETTER-BRIEFING` — Mono-Caps, Tracking 0.18 em |
| Bergmark-Glyph | **Verboten** im Sidebar-Kontext. Nur als optionales App-Icon (Favicon, OS-Icons) |
| Tonalität | nüchtern · präzise · alpin-modern · keine Werbesprache |

---

## 2. Navigation & Informationsarchitektur

| Aspekt | Entscheidung |
|---|---|
| Haupt-Nav-Bereiche | **Genau 4**: Startseite · Touren · Orts-Vergleich · Archiv |
| Nav-Reihenfolge | Diese Reihenfolge ist fixiert. Keine Umsortierung. |
| Konto-Einstellungen | Erreichbar **nur** über User-Badge unten in der Sidebar. **Nicht** in Haupt-Nav. |
| Kanal-Einstellungen | Innerhalb der Konto-Seite, keine eigene Nav-Position. |
| Wetter | **Keine eigene Seite.** Drill-Down inline aus Trip-Detail (Etappe) oder Compare (Ort) als Slide-Panel rechts (Desktop) / Bottom-Sheet (Mobile). |
| Mobile Nav | Bottom-Nav mit denselben 4 Bereichen. Drawer enthält Konto + Logout. |

---

## 3. Layout-Patterns

Drei kanonische Patterns. Jeder Screen muss in genau einem dieser Patterns sein.

| Pattern | Wann | Beispielscreens |
|---|---|---|
| **Kachel-Grid** | Listen, in denen jedes Item ein eigenständiger Einstiegspunkt ist | Startseite · Touren-Liste · Orts-Vergleich-Liste · Archiv · Wetter-Templates |
| **Master-Detail** | Sammlung mit Gruppen + auswählbarem Inhalt | Orts-Vergleich (Sidebar + Matrix) · Konto (Sektionen + Inhalt) |
| **Wizard** | Mehrstufiger Anlege-Prozess | Trip-Wizard (4 Schritte) |

**Tabellen-Layout ist die Ausnahme** und nur erlaubt für:
- Stündliche Wetterdaten (technische Dichte erforderlich)
- Hourly-Matrix in Compare (Vergleichszweck)
- System-Status-Tabellen in Konto

Für Touren, Vergleiche, Archiv, Templates: **Kachel-Grid, keine Tabelle**.

---

## 4. Komponenten-Disziplin

| Aspekt | Entscheidung |
|---|---|
| Quelle | `docs/design-system/COMPONENTS.md` ist der Single-Source-of-Truth-Katalog. |
| Naming | Komponenten-Name in Mockup = in Code = im Katalog. **Identisch.** |
| Erfinden verboten | Keine ad-hoc Buttons, Cards, Headers. Wenn etwas fehlt, wird es im Katalog ergänzt — nicht lokal gebaut. |
| Mobile-Pendant | Jede Desktop-Komponente, die auf Mobile gebraucht wird, hat ein im Katalog deklariertes Mobile-Pendant (oder ist responsiv mit explizit dokumentierten Breakpoints). |

---

## 5. Visuelle Sprache

| Aspekt | Entscheidung |
|---|---|
| Type-Pairing | `Inter Tight` (Sans) + `JetBrains Mono` (Mono). **Keine** weiteren Fonts. |
| Mono-Verwendung | Zahlen, technische Labels, Eyebrows, Captions, Status-Pills. **Nicht** für Fließtext. |
| Accent | `--g-accent` (burnt orange `#c45a2a`). **Sparsam** — Primäraktion, aktiver Nav-Item, ein Hervorhebungs-Element pro Screen. |
| Spacing | Ausschließlich `--g-s-*` Tokens. Keine freien Pixel-Werte. |
| Radien | Ausschließlich `--g-r-*` Tokens. Default `--g-r-3` (6 px) für Cards. |
| Schatten | Ausschließlich `--g-shadow-*` Tokens. Dezent — kein Material-Design-Lifting. |
| Farben | Ausschließlich `--g-*` Tokens. Keine Inline-Hex. |
| Topo-Pattern | Nur auf Auth-Screens und Empty-States, nicht überall. |
| Emoji | **Verboten** im Produkt-UI. Auch keine "✓" Status-Symbole — stattdessen `<Dot>` oder semantische Pills. |
| Iconographie | Nur die im Katalog deklarierten Line-Icons. **Keine** zusätzlichen SVGs ad-hoc. |

---

## 6. Interaktions-Regeln

| Aspekt | Entscheidung |
|---|---|
| Primäraktion pro Screen | **Genau eine.** Visuell prominent. Position: rechts neben Page-Header. |
| Sekundäraktionen | Aus dem `<DropdownMenu>` (Kebab `⋯`). |
| Floating Action Button (FAB) | **Verboten.** Auch auf Mobile. |
| Listen-Items | Klick auf den Namen öffnet Detail. **Keine** Icon-Soup auf jeder Zeile. |
| Inline-Edit | Bevorzugt vor Modal-Dialog. Modal nur, wenn der Edit-Prozess mehrstufig oder destruktiv ist. |
| Bestätigung destruktiver Aktionen | Inline-Confirm oder Modal mit explizitem rotem Button-Label ("Konto löschen") — kein "OK"/"Bestätigen". |
| Toast-Position Desktop | Bottom-Right, 24 px Inset. |
| Toast-Position Mobile | Bottom über BottomNav (88 px Inset). |

---

## 7. Daten & Eingabe

| Aspekt | Entscheidung |
|---|---|
| Lat/Lon-Eingabe | **Verboten** im UI. Wegpunkte werden ausschließlich visuell auf Karte oder durch Algorithmus-Vorschlag gesetzt. |
| Native HTML Controls | **Verboten** (`<input type="checkbox">`, `<select>`, `<input type="date">`). Stattdessen die Brand-Bausteine aus dem Katalog. |
| Mobile-Input-Bodysize | Mindestens 16 px (verhindert iOS Auto-Zoom). |
| Touch-Targets | Mindestens 44 × 44 px. |
| Numerische Felder | Mono-Schrift, `tabular-nums`. |
| Datums-Format | `DD. MMM YYYY` für Display, ISO für Daten. |

---

## 8. Responsives Verhalten

| Aspekt | Entscheidung |
|---|---|
| Desktop-Default | 1440 px Design-Breite |
| Desktop-Wide | 1680 px für Compare (Matrix + Sidebar + Drill-Down-Panel) |
| Mobile-Default | 375 px Design-Breite |
| Breakpoints | Mobile: < 640. Tablet: 640–1024 (= Mobile-Pattern, mehr Padding). Desktop: > 1024. |
| Mobile-First-Code | Code wird Mobile-First geschrieben, Desktop-Layout per `@media (min-width: …)`. |

---

## 9. Copy & Sprache

| Aspekt | Entscheidung |
|---|---|
| Sprache | Deutsch. Englisch nur in technischen Code-Identifiern. |
| Tonalität | "Du", nicht "Sie". |
| Anglizismen | Vermeiden. Konkrete Tabu-Liste in `COPY.md`. |
| Fachbegriffe | Eingedeutscht, wo etabliert (Wegpunkt, Etappe, Briefing). |

---

## 10. Mockup-Disziplin

`Soll-Mockups.html` ist die **Proof-Layer** des Systems — kein Spielplatz. Regeln:

- Jeder Screen in einem `DCArtboard`.
- Komponenten-Namen im Mockup-Code = Komponenten-Namen in `COMPONENTS.md`.
- Wenn ein Mockup eine neue Komponente braucht, **erst** den Katalog erweitern, **dann** mocken.
- Mockup ist veraltet, wenn Charter / COMPONENTS / COPY sich ändern → in derselben Iteration nachziehen.

---

## 11. Änderungs-Prozess

Diese Charter wird **nicht** durch implizite Drift geändert. Wer die Charter ändert:

1. Editiert das Dokument.
2. Markiert die Änderung mit Datum + Begründung.
3. Aktualisiert davon abhängige Mockups + Code in derselben Änderungs-Welle.

Implementierungen, die dieser Charter widersprechen, sind als Bug behandelt.

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initiale Charter — Runde 1 |
