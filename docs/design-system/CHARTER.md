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
| Haupt-Nav-Bereiche | Wie die heutige Seitenleiste (ADR-0111 Punkt 6): Startseite · Meine Trips · Orts-Vergleich · Archiv, darunter Hilfe; Admin nur für Admin-Konten. Produktbegriff ist **Trip**, nie „Tour" (Glossar, ADR-0104). |
| Nav-Reihenfolge | Diese Reihenfolge ist fixiert. Keine Umsortierung. |
| Konto-Einstellungen | Erreichbar **nur** über das User-Badge: unten in der Sidebar (Desktop) bzw. als **Konto-Kreis** neben der Mobile-Nav. **Nicht** in Haupt-Nav. |
| Kanal-Einstellungen | Innerhalb der Konto-Seite, keine eigene Nav-Position. |
| Wetter | **Keine eigene Seite.** Drill-Down inline aus Trip-Detail (Etappe) oder Compare (Ort) als Slide-Panel rechts (Desktop) / Bottom-Sheet (Mobile). |
| Mobile Nav | Schwebende Bottom-Nav (Glas) mit den 4 Hauptbereichen (Übersicht · Trips · Vergleich · Archiv) plus User-Badge als **Konto-Kreis** rechts daneben. Der Konto-Kreis öffnet das **Konto-Sheet**: Kanäle & Empfänger · Einstellungen · System-Status · Dunkles Design · Datenexport · Abmelden (Benachrichtigungen erst mit echtem Posteingang, #1701). **Kein Top-Balken**, kein Hamburger-Drawer (Mobile-Shell S2, PO 2026-09-19). |

---

## 3. Layout-Patterns

Drei kanonische Patterns. Jeder Screen muss in genau einem dieser Patterns sein.

| Pattern | Wann | Beispielscreens |
|---|---|---|
| **Kachel-Grid** | Listen, in denen jedes Item ein eigenständiger Einstiegspunkt ist | Startseite · Wetter-Templates |
| **Tabelle (`ListTable`)** | Trip-Liste und Vergleichsliste (ADR-0111 Punkt 2); am Handy Karten-Zeilen | Trip-Liste · Orts-Vergleich-Liste |
| **Master-Detail** | Sammlung mit Gruppen + auswählbarem Inhalt | Orts-Vergleich (Sidebar + Matrix) · Konto (Sektionen + Inhalt) |
| **Anlegen** | Mehrstufiger Anlege-Prozess im geteilten Anlege-Rahmen (ADR-0110), Schritte über `AnlegeReiter` (ADR-0111 Punkt 3) | Trip anlegen · Vergleich anlegen |

**Tabellen-Layout ist die Ausnahme** und nur erlaubt für:
- Stündliche Wetterdaten (technische Dichte erforderlich)
- Hourly-Matrix in Compare (Vergleichszweck)
- System-Status-Tabellen in Konto

Trip-Liste und Vergleichsliste sind **Tabellen** (`ListTable`, gleich gebaut); die frühere Kachel-Pflicht ist für diese beiden Listen durch ADR-0111 Punkt 2 abgelöst. Neue Listen folgen ihrer Schwesterliste, keine dritte Form.

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
| Hauptaktion | **Ink** (`Btn primary`, ADR-0110) — auch „+ Neuer Trip"/„+ Neuer Vergleich" auf Listen und Startseite (ADR-0111). |
| Accent | `--g-accent` (burnt orange `#c45a2a`). **Sparsam** — Weiter/Aktiv-Zustand, Unterstrich des aktiven Reiters, Fortschritt, ein Hervorhebungs-Element pro Screen. Als Fläche unter Text oder als Textfarbe nur `--g-accent-deep` (WCAG-AA, #2879). |
| Spacing | Ausschließlich `--g-s-*` Tokens. Keine freien Pixel-Werte. |
| Radien | Ausschließlich `--g-r-*` Tokens. Default `--g-r-3` (6 px) für Cards. |
| Schatten | Ausschließlich `--g-shadow-*` Tokens. Dezent — kein Material-Design-Lifting. |
| Farben | Ausschließlich `--g-*` Tokens. Keine Inline-Hex. |
| Topo-Pattern | Nur auf Auth-Screens und Empty-States, nicht überall. |
| Emoji | **Verboten** im Produkt-UI. Auch keine Zustands-Symbole „✓"/„⊘" — stattdessen `<Dot>` mit Text (erledigt `--g-good`, gesperrt `--g-ink-4` + `aria-disabled`, ADR-0111 Punkt 7) oder semantische Pills. |
| Iconographie | Nur die im Katalog deklarierten Line-Icons. **Keine** zusätzlichen SVGs ad-hoc. |

---

## 6. Interaktions-Regeln

| Aspekt | Entscheidung |
|---|---|
| Primäraktion pro Screen | **Genau eine.** Visuell prominent. Position: rechts neben Page-Header. |
| Sekundäraktionen | Aus dem `<DropdownMenu>` (Kebab `⋯`). |
| Floating Action Button (FAB) | **Verboten** — der Primäraktions-FAB (Akzent-Farbe, unten rechts). Ausnahme: `<MapControl>` auf Vollbild-Karten (neutral, oben, gleichgewichtig — siehe AP-012). |
| Listen-Items | Klick auf den Namen öffnet Detail. **Keine** Icon-Soup auf jeder Zeile. |
| Inline-Edit | Bevorzugt vor Modal-Dialog. Modal nur, wenn der Edit-Prozess mehrstufig oder destruktiv ist. |
| Bestätigung destruktiver Aktionen | Inline-Confirm oder Modal mit explizitem rotem Button-Label ("Konto löschen") — kein "OK"/"Bestätigen". |
| Toast-Position Desktop | Bottom-Right, 24 px Inset. |
| Toast-Position Mobile | Bottom über BottomNav (88 px Inset). |

---

## 7. Daten & Eingabe

Die Regeln gelten unverändert; ADR-0111 (Audit 2026-11-09) setzt sie auf den Trip- und Vergleichsseiten durch (native Felder → Bausteine, Tippflächen ≥ 44 px, `.mono`/`.tnum` nach TOKENS.md §12).

| Aspekt | Entscheidung |
|---|---|
| Lat/Lon-Eingabe | **Verboten** im UI. Wegpunkte werden ausschließlich visuell auf Karte oder durch Algorithmus-Vorschlag gesetzt. |
| Native HTML Controls | **Verboten** (`<input type="checkbox">`, `<select>`, `<input type="date">`). Stattdessen die Brand-Bausteine aus dem Katalog. |
| Mobile-Input-Bodysize | Mindestens 16 px (verhindert iOS Auto-Zoom). |
| Touch-Targets | Mindestens 44 × 44 px bei Fingerbedienung (`@media (pointer: coarse)`). Bei Mausbedienung darf der Vorlagen-Wähler im Wetter-Reiter die Mockup-Höhe (ca. 38 px) haben (PO 14.11.2026, #3003). |
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
| v1.1 | 2026-11-09 | ADR-0111 (#2881): §2 Navigation wie die Seitenleiste, „Trip" statt „Tour"; §3 Trip-/Vergleichsliste als Tabelle, Anlegen statt Wizard; §5 Hauptaktion Ink, Accent unter Text `--g-accent-deep`, `Dot` statt ✓/⊘; §7 Verweis auf ADR-0111. |
