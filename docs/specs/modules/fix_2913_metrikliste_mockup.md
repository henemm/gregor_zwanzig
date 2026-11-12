---
entity_id: fix_2913_metrikliste_mockup
type: bugfix
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
tags: [design-system, wetter-reiter, metrik-liste, segmented, container-query, adr-0112, epic-2791]
workflow: fix-2913-metrikliste-mockup
issue: 2913
---

# Einstellungen neu, Reiter Wetter: Metrik-Liste nach Mockup (Fix, Teil von #2913)

## Approval

- [ ] Approved

## Purpose

Die Metrik-Liste im Reiter Wetter (Trip und Orts-Briefing) weicht sichtbar vom freigegebenen Mockup Fassung 3 ab (PO-Befund 12.11.2026): Die Mittelspalte mit Ampel-Leiste und Erklärung ist bei normalen Fensterbreiten viel zu schmal (bei 1024 px sogar 0 px breit), die Zeilen sind 1,5- bis 4-mal so hoch, der Untertitel fehlt, „grün: …“ ist grau, die aktive „Alarm ab“-Stufe ist schwarz gefüllt, Knöpfe sind unnötig groß. Diese Scheibe bringt die Liste Zeile für Zeile auf das Mockup-Maß, ohne Tapflächen unter 44 px zu verlieren und ohne andere Nutzer des Segmented-Atoms zu verändern.

Grundlage: Analyse `docs/context/fix-2913-metrikliste-mockup.md` (maßgeblich, mit Messwerten), Soll `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (CSS `.mr` Z. ~70–200, Segmente Z. 76–78, Erklärung Z. 115–116, Handy-Layout Z. ~180, Untertitel-Logik Z. ~420). Vorgänger-Specs: `feat_2913_s3_bausteine.md`, `feat_2913_scheibe_c_wetter_rest.md`.

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/lib/components/organisms/wetter-tab/`, `frontend/src/lib/components/ui/segmented/`, `frontend/src/app.css`, `frontend/src/lib/i18n/messages/{de,en}/wetter.json`.
- **Identifier:** `MetrikZeile`, `AmpelLeiste`, `WetterTabInhalt`, Atom `Segmented` (neue Variante), Hilfsfunktion `untertitel()` in `shared/wetter-tab/ampelModell.ts`.
- **Nicht berührt:** Go-API, Python-Core, Speicherpfad, Alarm-Engine, Renderer, Logik-Module `ampelSchreiben.ts`, `wetterZustand.ts`.

> **Schicht-Hinweis:** Reine Frontend-Arbeit (SvelteKit, `frontend/src/...`). Keine Backend-Änderung.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, ADR-0097):** Die Änderungen liegen in den gemeinsamen Organismen (`WetterTabInhalt` mit `context="route"|"vergleich"`). Es entsteht keine Compare-eigene Komponente; Trip und Orte zeigen zwingend dasselbe Bild.
>
> **Mandantentrennung:** Nicht berührt. Es werden keine Nutzerdaten bewegt, kein Endpoint geändert; das Speichern der Grenzen bleibt unverändert. Die Zwei-Nutzer-Regel ist daher kein Prüfpunkt dieser Scheibe (Nicht-Ziel).
>
> **Kanäle:** Keine Änderung an Briefing- oder Alarm-Inhalt; E-Mail, Telegram, SMS, Premium-SMS sind nicht berührt (ADR-0095).

## Estimated Scope

- **LoC:** +220/−80 (davon ca. 60 Katalog, ca. 70 Abnahme-Spec)
- **Files:** 9 bis 11 (ca. 6 Produktivdateien, Rest Tests und Abnahme)
- **Effort:** medium, Risiko MEDIUM (nur Darstellung, aber Segmented ist geteilter Baustein und Tapflächen ≥ 44 px dürfen nicht verloren gehen)

## Scope

### In Scope

1. Zeilenraster der Metrik-Zeile nach Mockup, Umbruch per Container-Query an der Kartenbreite.
2. Doppeltes Innen-Padding in `WetterTabInhalt` abbauen; Karte wird Container.
3. Untertitel `[Einheit, Hinweis]` aus dem Katalog DE/EN.
4. Erklärtext 12 px, „grün: …“ in `--a-green` mit Gewicht 600.
5. Neue Segmented-Variante für „Alarm ab“ (kompakt, aktives Segment hell).
6. Kompakte Knöpfe über das vorhandene `data-tap`-Muster.
7. `AmpelLeiste`: Grenzzahlen und Leiste nach Mockup.
8. Einheitliche Ausrichtung der Zeilen ohne Ampel (display_only).
9. Abnahme-Werkzeug: Ganzseitenaufnahme und Messwert-Zusicherungen.

### Nicht-Ziele

- **Sichtweite km statt m:** eigenes Issue #2946, hier nicht angefasst.
- **Zwei-Nutzer-Test:** nicht anwendbar (keine datenbewegenden Endpoints).
- **Dark Mode:** nur „nicht kaputt“ (keine neuen Hardcode-Farben, Tokens tragen beide Themes); keine eigene Dark-Abnahme gegen das Mockup.
- **Globale Änderung des Segmented-Atoms:** ausgeschlossen. CompareTabs, MTabBar, HorizonChip, VersandTab u. a. (17 Nutzer) bleiben optisch und im Verhalten unverändert.
- Keine Änderung an Metrik-Auswahl, Ampel-Logik, Speichern, Backend.
- Plan A–C eines allgemeinen Abgleich-Werkzeugs bleiben zurückgestellt; nur die Ganzseitenaufnahme (Plan D) gehört hierher.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md` | ADR | Nur Tokens und Bausteine; Bausteine-Wächter muss grün bleiben |
| `docs/adr/0097-trip-ortsvergleich-code-teilung.md` | ADR | Trip und Orte teilen den Code |
| `docs/adr/0104-zweisprachigkeit-de-en.md` | ADR | Neue Nutzertexte nur über den Katalog, DE und EN |
| `ui/segmented/Segmented.svelte` (Re-Export `atoms/Segmented`) | Atom | Neue Variante `kompakt` |
| `atoms/Btn` mit `size="tap"` und `data-tap="true"` (`app.css` ca. Z. 510–521) | Atom/CSS | Optisch kleiner Knopf, Trefferfläche 44 px |
| `shared/wetter-tab/ampelModell.ts` | Code | Untertitel-Logik, von Komponente und Test gemeinsam genutzt |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json`, `hardcode_allowlist.json` | i18n/Wächter | Katalog, Hardcode-Wächter |
| Container-Query-Muster `HubOverview.svelte:174`, `TripStageRow.svelte:127` | Code | Vorbild für `container-type: inline-size` |
| `docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md` | Spec | Vorgänger (Karten und Abschnitte im Wetter-Reiter) |

## Implementation Details

**1. Zeilenraster (`MetrikZeile.svelte`).** Desktop-Raster `32px minmax(130px,190px) minmax(160px,1fr) auto`, `column-gap: 18px` (bisher 44/120–180/`minmax(0,1fr)`/Gap 14). Die Mittelspalte hat damit eine harte Untergrenze von 160 px und kann nicht mehr auf 0 fallen.

**2. Umbruch per Container-Query.** Die Karte in `WetterTabInhalt` erhält `container-type: inline-size`. Der Umbruch ins Handy-Layout läuft über `@container (max-width: 700px)` statt `@media (max-width: 899px)`. Begründung der Schwelle: Das Mockup bricht bei 760 px Viewport (ohne Seitenleiste); dort ist die Kartenbreite ca. 700 px. Die Schwelle hängt an der verfügbaren Breite, damit der Bereich 900–1250 px Viewport (mit 220 px Seitenleiste) nicht mehr auf eine 0-breite Mittelspalte kippt. Rechnung bei Viewport 1024 mit Seitenleiste: Karte ca. 750 px, also Desktop-Layout; Mindestbedarf des Rasters 32+130+160+ca. 120+3·18 ≈ 500 px, passt. Handy-Layout bei 390 px zweizeilig wie Mockup Z. ~180 (Spalten `40px 1fr`, Ampel-Leiste und Erklärung in zweiter Zeile).

**3. Padding (`WetterTabInhalt.svelte`).** Das zusätzliche Innen-Padding (Desktop 28/40 px, mobil 16 px) zusätzlich zu `main` (24 px) entfällt; die Karte nutzt die Restbreite (Soll bei 1280: Karte ca. 1068 px statt 932 px; mobil: Karte beginnt bei x = 16 px statt 32 px). Die Seitenleiste bleibt als App-Rahmen.

**4. Untertitel.** `untertitel(id, eig)` in `ampelModell.ts` liefert `[Einheit, Hinweis].filter(Boolean).join(' · ')`. Hinweis je Metrik aus Katalogschlüssel `wetter.hinweis.<metrik_id>` (DE und EN): Tageshöchst · Tagestief, vor der Etappe, Mittelwind, Spitze, Summe, Stufe, Minimum, Gipfel in Wolken, Maximum, m über höchster Stelle, zu wenig ist schlecht (genaue Zuordnung wie Mockup Z. ~420). „Vorbote, kein Alarm“ wird aus `is_precursor`, „nur Anzeige, keine Ampel“ aus `display_only` abgeleitet (eigene Katalogschlüssel, nicht je Metrik doppelt). Fallback ohne Hinweis: nur die Einheit, ohne Trennpunkt am Ende.

**5. Erklärung und „grün“.** Erklärtext 12 px (bisher 12,5), „grün: …“ in `--a-green` mit `font-weight: 600` (bisher `--g-ink-3`), der Punkt liegt in der Span (Mockup Z. 115–116).

**6. Segmented-Variante.** Neue Variante (`variant="kompakt"`, Ausgabe als data-Attribut, CSS in `app.css` nur unter diesem Selektor): Hülle `card-alt`, Rahmen `rule-soft`, Padding/Gap 2 px, 600/11,5 px; sichtbare Höhe ca. 23 px; aktives Segment `paper`, Text `accent-deep`, Ring 1 px `rule`; keine schwarze Füllung. Wirksame Trefferfläche ≥ 44×44 px über `::before` wie beim `data-tap`-Muster. Die Mindesthöhen 44 px in `MetrikZeile` (Z. 155–162) entfallen. Standard-Segmented (ohne Variante) bleibt bytegleich im Verhalten und optisch unverändert.

**7. Knöpfe.** „Grenzen ändern“ und die weiteren Zeilen-Knöpfe: `size="tap"` plus `data-tap="true"` (sichtbar ca. 29 px hoch, wie `.btn.sm` im Mockup; Trefferfläche 44 px). Die breite Aktionsspalte (bisher 119×44) schrumpft damit auf Mockup-Maß (109×29).

**8. AmpelLeiste.** Grenzzahlen: Zeilenhöhe 14 px, 10,5 px, Farbe `ink-3`, Abstand 3 px. Leiste ohne Rahmen und ohne Fugen zwischen den Zonen. Beschriftungen dürfen sich nicht überlappen (die Mindestbreite 160 px der Mittelspalte gewährleistet dies; Test misst).

**9. Zeilen ohne Ampel (display_only).** Die Hinweisangabe „kein Alarm“ steht im selben Raster-Feld wie bei Zeilen mit Ampel und beginnt am linken Rand der Mittelspalte; die Aktionsspalte bleibt rechts ausgerichtet. Das Prinzip „Leistenende je Zeile verschieden“ (Mockup) bleibt unverändert und ist kein Fehler.

**10. Tokens.** Ausschließlich Design-Tokens (`--a-green`, `--g-ink-3`/`ink-3`, `paper`, `card-alt`, `rule`, `rule-soft`, `accent-deep`); keine Hex-Werte, keine rohen Controls (Bausteine-Wächter ADR-0112 und Hardcode-Wächter bleiben grün, keine Aufstockung von `BESTAND`/`AUSNAHMEN`).

**11. Abnahme-Werkzeug.** Neue Playwright-Spec in `frontend/e2e/` mit Helfer für die Ganzseitenaufnahme: Das Skript hebt `h-screen` und `main.overflow-auto` zur Aufnahmezeit auf (Höhe auto, overflow visible), sodass `fullPage` die ganze Liste liefert. Aufnahmen von Mockup und Staging bei 1280, 1024 und 390 px, Trip und Orte, DE und EN. Gemessene Werte (Spaltenbreiten, Zeilenhöhe, Zeilenzahl der Erklärung, Segmenthöhe, Knopfgröße, Trefferfläche) werden als automatische Zusicherung geprüft. Danach Bildvergleich Mockup gegen Staging durch den Agenten `mockup-bildpruefer`, Ergebnis-Bild an den PO (Soll/Ist, Zeile für Zeile).

## Expected Behavior

- **Input:** Reiter Wetter eines Trips oder Orts-Briefings, beliebige Fensterbreite 390–1440 px, Sprache DE oder EN.
- **Output:** Metrik-Liste im Mockup-Maß: breite Mittelspalte, niedrige Zeilen, Untertitel mit Hinweis, grüne „grün: …“-Angabe, helle aktive „Alarm ab“-Stufe, kompakte Knöpfe mit voller Trefferfläche.
- **Side effects:** Keine. Weder Speicherwerte noch Briefing-Inhalte ändern sich.

## Test Plan

### Automatisierte Tests (TDD RED), Kern-Schicht `node --test`, ohne Mock-Theater

- [ ] `untertitel()`: GIVEN Temperatur DE WHEN Untertitel gebildet THEN „°C · Tageshöchst · Tagestief“; GIVEN Metrik ohne Hinweis THEN nur die Einheit ohne endenden Punkt; GIVEN `is_precursor` THEN enthält „Vorbote, kein Alarm“; GIVEN `display_only` THEN enthält „nur Anzeige, keine Ampel“ (jeweils DE und EN).
- [ ] Katalogvollständigkeit: jeder Schlüssel `wetter.hinweis.*` und die beiden abgeleiteten Hinweise existieren in DE und EN, ohne leere Werte.
- [ ] Stil-Regeln gegen die echten CSS-Quellen als `# doc-compliance-test`: Raster-Wert `32px minmax(130px,190px) minmax(160px,1fr) auto`, Container-Query statt Viewport-Media-Query, Variante `kompakt` nur unter eigenem Selektor, `.wt-gruen` nutzt `--a-green`.
- [ ] Bausteine-Wächter und Hardcode-Wächter laufen grün (bestehende Testdateien).
- [ ] Bestehende Segmented-Nutzer-Tests (CompareTabs, MTabBar, HorizonChip, VersandTab) bleiben grün.

### Staging-Playwright (Live-E2E-Schicht, in `/e2e-verify`)

- [ ] Messwerte je Breite 1024, 1100, 1280, 1440 (mit Seitenleiste), Trip und Orte (siehe AC-1 bis AC-4, AC-7 bis AC-10).
- [ ] Ganzseitenaufnahmen Mockup und Staging, 1280/1024/390, Trip+Orte, DE+EN; Bildvergleich durch `mockup-bildpruefer`.

## Definition of Done

Fertig ist die Scheibe, wenn die Metrik-Liste im Reiter Wetter von Trip und Orts-Briefing auf Staging bei 1024, 1100, 1280, 1440 und 390 px in DE und EN dem Mockup entspricht: Mittelspalte ≥ 160 px, Zeilenhöhe und Erklärung in den Grenzen von AC-4, Untertitel aus dem Katalog, „grün: …“ grün und fett, aktive „Alarm ab“-Stufe hell mit Ring, kompakte Bedienelemente mit wirksamer Trefferfläche ≥ 44 px, andere Segmented-Nutzer unverändert, Bausteine- und Hardcode-Wächter grün (AC-1 bis AC-13). Die Ganzseitenaufnahmen Mockup ↔ Staging liegen vor, der `mockup-bildpruefer` meldet nach höchstens zwei Runden keine offene Abweichung, und der PO hat das Soll/Ist-Bild erhalten. Sichtweite km→m bleibt in #2946.

## Acceptance Criteria

- **AC-1:** Given der Reiter Wetter eines Trips oder Orts-Briefings ist bei Viewport 1024, 1100, 1280 oder 1440 px (mit Seitenleiste) geöffnet / When die Zeile „Temperatur“ gemessen wird / Then ist die Mittelspalte (Ampel-Leiste plus Erklärung) mindestens 160 px breit, das Raster ist `32px minmax(130px,190px) minmax(160px,1fr) auto` mit 18 px Abstand, und Trip und Orte liefern dieselben Werte.
  - Test: Staging-Playwright misst die berechneten Spaltenbreiten (`getComputedStyle` auf `grid-template-columns`) in beiden Kontexten und allen vier Breiten; vorher 0 px bei 1024 und 22 px bei 1100.

- **AC-2:** Given die Karte der Metrik-Liste ist Container (`container-type: inline-size`) / When die Kartenbreite 700 px oder weniger beträgt / Then wechselt die Zeile ins zweizeilige Handy-Layout, bei größerer Kartenbreite bleibt das Desktop-Layout; der Wechsel hängt an der Kartenbreite, nicht an der Viewportbreite, und bei Viewport 390 px ist die Zeile zweizeilig wie im Mockup.
  - Test: Playwright prüft bei Viewport 1024 (Karte ca. 750 px) Desktop-Layout, bei 390 px das Handy-Layout (Spalten `40px 1fr`) und per Containerbreiten-Variation (Seitenleiste ein/aus) den Wechsel an der 700-px-Schwelle.

- **AC-3:** Given der Reiter Wetter ist offen / When die Karte gemessen wird / Then ist das doppelte Innen-Padding abgebaut: bei Viewport 1280 füllt die Karte die Inhaltsbreite von `main` (Abweichung ≤ 2 px, rechnerisch 1280 − 220 Seitenleiste − 2·24 = 1012 px, mindestens 1000 px; vorher 932; das Mockup-Maß 1068 gilt ohne Seitenleiste), bei 390 px beginnt sie bei x = 16 px (vorher 32).
  - Test: Playwright misst `getBoundingClientRect()` der Karte und die Inhaltsbreite von `main` bei 1280 und 390 px, Trip und Orte.

- **AC-4:** Given Viewport 1280 / When die Zeile „Temperatur“ gemessen wird / Then ist sie höchstens 124 px hoch (Mockup 112 px, Toleranz 12 px, vorher 168), die Erklärung hat höchstens 4 Zeilen bei 12 px Schriftgröße (vorher 6 Zeilen bei 12,5 px).
  - Test: Playwright misst Zeilenhöhe, `font-size` und Zeilenzahl (Höhe / `line-height`) der Erklärung.

- **AC-5:** Given die Sprache ist DE oder EN / When die Metrik-Liste angezeigt wird / Then zeigt jeder Untertitel `Einheit · Hinweis` (z. B. „°C · Tageshöchst · Tagestief“, „km/h · Mittelwind“, „mm · Summe“, „% · Vorbote, kein Alarm“, Sichtweite „km · Minimum“ bis #2946), Vorbote-Metriken zeigen „Vorbote, kein Alarm“ aus `is_precursor`, Zeilen ohne Ampel „nur Anzeige, keine Ampel“ aus `display_only`, und Metriken ohne Hinweis zeigen nur die Einheit ohne endenden Trennpunkt.
  - Test: Kern-Test der Funktion `untertitel()` und Katalogvollständigkeit DE/EN; Playwright liest die Untertitel im DOM in beiden Sprachen.

- **AC-6:** Given eine Metrik mit „grün: …“-Angabe / When die Zeile dargestellt wird / Then hat die Angabe die Farbe des Tokens `--a-green` und Schriftgewicht 600 (vorher grau).
  - Test: Playwright vergleicht `color` und `font-weight` der „grün“-Span mit der aufgelösten Farbe von `--a-green`.

- **AC-7:** Given die Zeile hat die Auswahl „Alarm ab“ / When sie dargestellt wird / Then verwendet sie eine neue Variante `kompakt` des Segmented-Atoms mit sichtbarer Höhe von 23 px (Toleranz ±2 px), das aktive Segment ist hell (`paper`) mit Text `accent-deep` und Ring statt schwarzer Füllung; alle anderen Segmented-Nutzer (CompareTabs, MTabBar, HorizonChip, VersandTab) sehen unverändert aus.
  - Test: Playwright misst Höhe und Hintergrundfarbe des aktiven Segments in der Metrik-Zeile; Gegenprobe: aktives Segment in CompareTabs und VersandTab bleibt dunkel gefüllt wie vorher; bestehende Segmented-Tests bleiben grün.

- **AC-8:** Given die Zeile enthält Knöpfe wie „Grenzen ändern“ / When sie gemessen werden / Then ist der sichtbare Knopf ca. 29 px hoch (Mockup 109×29, vorher 119×44), und die wirksame Trefferfläche aller Bedienelemente der Zeile (Knöpfe und Segmente) bleibt mindestens 44×44 px.
  - Test: Playwright misst Sichtfläche und per `elementFromPoint` an den Rändern einer 44×44-Fläche um den Mittelpunkt die Trefferfläche.

- **AC-9:** Given die Ampel-Leiste einer Zeile / When sie gemessen wird / Then haben die Grenzzahlen 10,5 px Schriftgröße in `ink-3` bei 14 px Zeilenhöhe und 3 px Abstand, die Leiste hat weder Rahmen noch Fugen, und die Beschriftungen überlappen sich bei 1024 und 1280 px nicht.
  - Test: Playwright prüft `font-size`, `color`, Rahmen-/Fugenbreite und dass sich die Bounding-Boxen benachbarter Grenzzahlen nicht schneiden.

- **AC-10:** Given Zeilen ohne Ampel (`display_only`) / When sie neben Zeilen mit Ampel stehen / Then beginnt „kein Alarm“ bei allen diesen Zeilen am selben linken Rand der Mittelspalte und die Aktionsspalte endet bei allen Zeilen am selben rechten Rand.
  - Test: Playwright vergleicht `left` der Hinweise aller display_only-Zeilen (Abweichung ≤ 1 px).

- **AC-11:** Given die Änderung ist umgesetzt / When Bausteine-Wächter (ADR-0112) und Hardcode-Wächter laufen / Then sind beide grün ohne neue Ausnahmen, die Änderungen nutzen nur Tokens, und Trip und Orte nutzen denselben Code ohne Compare-eigene Komponente.
  - Test: bestehende Wächter-Testdateien per `node --test`; Playwright vergleicht Messwerte Trip und Orte (identisch).

- **AC-12:** Given Mockup und Staging / When die Abnahme läuft / Then entstehen Ganzseitenaufnahmen (trotz `main.overflow-auto` und `h-screen` die ganze Liste) bei 1280, 1024 und 390 px für Trip und Orte in DE und EN, die gemessenen Werte aus AC-1 bis AC-10 sind als automatische Zusicherung grün, und der Agent `mockup-bildpruefer` hat Mockup gegen Staging Zeile für Zeile verglichen; das Soll/Ist-Bild geht an den PO.
  - Test: Aufnahme-Spec liefert pro Kombination eine Bilddatei mit Höhe größer als Viewport-Höhe; Messzusicherungen laufen in `/e2e-verify`.

- **AC-13:** Given die Sichtweite wird in km statt m angezeigt und Dark Mode ist aktiv / When die Metrik-Liste geöffnet wird / Then bleibt die km-Anzeige unverändert (Nicht-Ziel, #2946) und die Liste ist im Dark Mode lesbar und nicht kaputt (keine unlesbaren Texte, keine abgeschnittenen Elemente).
  - Test: Playwright öffnet die Liste im Dark Mode und prüft, dass Text- und Hintergrundfarbe der Zeilen nicht identisch sind und kein Element über den Kartenrand hinausragt.

## Known Limitations / Risiken

- **Segmented geteilt (17 Nutzer):** Deshalb Variante statt globaler Änderung; Risiko, dass Variantenstil in Standard-Nutzer „durchsickert“, wird durch Selektor-Begrenzung und AC-7-Gegenprobe abgesichert.
- **Tapfläche:** Kompakte Optik darf die 44-px-Trefferfläche nicht senken (AC-40 in `docs/specs/modules/feat_2794_s3a_teil3_wetter.md`); abgesichert durch AC-8.
- **Container-Query-Schwelle 700 px:** aus dem Mockup abgeleitet; bei Abweichung an 1024/1100 wird die Schwelle in der Umsetzung anhand der Messung nachjustiert und hier im Changelog vermerkt.
- **Ganzseitenaufnahme:** Aufheben von `h-screen`/overflow nur im Testskript, nie in Produktivcode.
- **Hinweis-Zuordnung:** Metriken ohne Mockup-Hinweis zeigen nur die Einheit (bewusst).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Umsetzung bestehender Entscheidungen ADR-0097, ADR-0104, ADR-0112)
- **Rationale:** Reine Angleichung an das freigegebene Mockup; die Segmented-Variante ist eine Erweiterung des Bausteins, keine neue Grundsatzentscheidung.

## Changelog

- 2026-11-12: Initial spec created (Fix nach PO-Befund 12.11.2026, Teil von #2913)
- 2026-11-12 (Phase 6): AC-3-Schwelle rechnerisch korrigiert. „≥ 1060 px" stammte aus dem Mockup ohne Seitenleiste; mit der Seitenleiste (App-Rahmen, bleibt laut Impl. Detail 3) ist das Maximum 1012 px. Zweck unverändert (doppeltes Padding weg), neue Zusicherung: Karte = Inhaltsbreite von `main` ±2 px. AC-5-Beispiel Sichtweite lautet bis #2946 „km · Minimum" (Einheit kommt aus `/api/metrics`, km→m ist Nicht-Ziel).
