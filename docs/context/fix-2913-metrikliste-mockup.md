# Context: fix-2913-metrikliste-mockup

## Request Summary
PO-Befund 12.11.2026 (Foto, „ziemliche Katastrophe“): Die Metrik-Liste im Reiter Wetter weicht grob vom Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` ab. Ziel: Metrik-Liste (Trip + Orte, Computer + Handy, DE/EN) nach Mockup. Abnahme per Ganzseitenbild Mockup ↔ Staging bei gleicher Breite, Zeile für Zeile; danach Bild an den PO. Befund-Kommentar: #2913, 12.11.2026.

## Abweichungen (Foto PO gegen Mockup 1280 px)
1. Mittlere Spalte (Ampel-Leiste + Erklärung) live ca. 1/4 statt ca. 1/2 der Kartenbreite. Die Leistenbeschriftungen überlappen, die Erklärung hat 8–10 Zeilen statt 3, die Zeilen sind 3–4× so hoch.
2. Zeilen ohne Ampel (display_only): „kein Alarm“ frei rechts, Ausrichtung uneinheitlich.
3. Untertitel fehlt: Mockup „°C · Tageshöchst · Tagestief“, „km/h · Mittelwind“, „mm · Summe“, „% · Vorbote, kein Alarm“, „m · Minimum“, „m · m über höchster Stelle“; live nur die Einheit.
4. „grün: …“ im Mockup grün und fett, live grau (`.wt-gruen` → `--g-ink-3`).
5. Aktive „Alarm ab“-Stufe live schwarz gefüllt, im Mockup hell mit farbigem Rahmen.
6. Sichtweite km statt m → eigenes Issue #2946.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | Grid der Zeile (Z. 98–105, 163–175), Untertitel (Z. 60–63), grün (Z. 145), Segment-Stil (Z. 155–162) |
| frontend/src/lib/components/organisms/wetter-tab/AmpelLeiste.svelte | Leiste und Beschriftungen |
| frontend/src/lib/components/atoms (Segmented, Btn) | Größe tap = 44 px, Ursache für breite Aktionsspalte (Verdacht) |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | Karte, Abschnitte, data-abschnitt="metriken" |
| docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html | Soll; `.mr` Z. 97: `32px minmax(130px,190px) minmax(160px,1fr) auto`, Handy Z. 180 |

## Existing Patterns
- Bausteine-Wächter (ADR-0112): nur Tokens, Seiten aus Bausteinen.
- Trip/Orte teilen dieselben Organismen (ADR-0097).

## Messung 12.11.2026 (Agent, Rohdaten im Sitzungs-Scratchpad `messung/`)
| Messgröße (Temperatur) | Mockup 1280 | Staging 1280 | Mockup 390 | Staging 390 |
|---|---|---|---|---|
| Karte | 1068 | 932 | 358 | 326 |
| Grid-Spalten | 32/190/332/418 | 44/180/202/422 | 40/1fr | 44/1fr |
| Zeilenhöhe | 112 | 168 | 257 | 316 |
| Erklärung | 3 Zeilen 12px | 6 Zeilen 12.5px | 4 | 4 |
| Segment-Höhe | 23 | 44 | | |
| „Grenzen ändern“ | 109×29 | 119×44 | | |
Zwischenbreiten Trip, Spalte 3 / Erklärzeilen: 1024 → Mockup 256/4, Staging **0/33**; 1100 → 332/3 vs **22/33**; 1440 → 332/3 vs 290/4.

### Ursachen (datei:zeile → Mockup-Wert)
1. `MetrikZeile.svelte:100` `minmax(0,1fr)` → Mockup Z.97 `minmax(160px,1fr)`; Mittelspalte fällt auf 0.
2. `WetterTabInhalt.svelte:298` Padding 28·40 zusätzlich zu `main` (24) + Seitenleiste 220 → Karte 932 statt 1068; mobil `:354` 16 px doppelt (Karte x=32 statt 16). Seitenleiste bleibt (App-Rahmen), Inhalt muss mit der Restbreite auskommen.
3. `MetrikZeile.svelte:163` Umbruch bei 899px → Mockup 760px, aber Seitenleiste beachten: Umbruch muss an der **verfügbaren** Breite hängen (Container-Query statt Viewport), sonst kippt 900–1250 px.
4. `MetrikZeile.svelte:100–101` Spalten 44/120–180/Gap 14 → 32/130–190/18.
5. Knöpfe 44 px hoch: `MetrikZeile.svelte:155–157` (Segment min 44), `:58`/`:87` `size="tap"` (`app.css:510`); Mockup Segment 23 px, `.btn.sm` 29 px. Lösung ohne Tapflächen-Verlust: vorhandenes Muster `data-tap="true"` (`app.css:513–521`, sichtbar klein, Trefferfläche 44).
6. Aktives Segment schwarz: `app.css:723–726` + `MetrikZeile.svelte:160–162` → Mockup Z.78 bg paper, Text accent-deep, Ring 1px rule.
7. Segment-Hülle `app.css:703–722` → Mockup Z.76–77 (bg card-alt, Rahmen rule-soft, Padding/Gap 2, 600/11.5px). Achtung: Atom `Segmented` wird auch anderswo genutzt → Variante statt globaler Änderung prüfen.
8. Erklärung/grün `MetrikZeile.svelte:139–147`, `:73` → Mockup Z.115–116 (12px, `.gr` grün `--a-green` 600, Punkt in der Span).
9. Untertitel `MetrikZeile.svelte:62` nur Einheit → Mockup Z.420 `[Einheit, Beschreibung].join(' · ')`; Beschreibungstexte DE/EN über Katalog.
10. Grenzzahlen `AmpelLeiste.svelte:57–63` → 14px Höhe, 10.5px, ink-3, Abstand 3.
11. Leiste `AmpelLeiste.svelte:75–89` Rahmen/Fugen → Mockup ohne Rahmen.
12. Schiefe Zeilen: Folge von 1+5; Prinzip „Leistenende je Zeile verschieden“ steckt auch im Mockup (kein Fehler).

### Werkzeuglücke Ganzseitenbild
Staging scrollt in `main.overflow-auto` innerhalb `h-screen` → Playwright `fullPage` liefert nur den sichtbaren Ausschnitt. Für die Abnahme braucht es eine Ganzseitenaufnahme (z. B. `h-screen`/overflow im Testskript aufheben oder Abschnitte stückeln). Gehört in diese Scheibe (Plan D).

## Risks & Considerations
- Tapfläche ≥ 44 px (AC-40-Design-Spec) darf nicht verloren gehen. Optisch kompakte Segmente mit wirksamer Tapfläche über `data-tap`, wie beim Warnungen-Schalter.
- Messung je Spalte läuft (Agent, Ergebnis folgt). Ursachen werden hier mit datei:zeile nachgetragen.
- Plan A–D (Abgleich-Werkzeug) zurückgestellt; D (Ganzseitenbild) ist Abnahme dieser Scheibe.

## Analysis

### Type
Bug (Abweichung Ist ↔ freigegebenes Mockup, Teil von Epic/Ticket #2913). Reine Oberflächen-Scheibe, kein Datenmodell, kein Backend.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | Grid nach Mockup `32px minmax(130px,190px) minmax(160px,1fr) auto`, Gap 18; Umbruch per Container-Query statt `@media 899px`; Untertitel `[Einheit, Hinweis].join(' · ')`; `.wt-gruen` → `--a-green`/600; Erklärung 12 px; Knöpfe `size="tap" data-tap="true"` (sichtbar klein, Trefferfläche 44); Segment-Overrides `min-height 44` entfernen |
| frontend/src/lib/components/organisms/wetter-tab/AmpelLeiste.svelte | MODIFY | Grenzzahlen 14 px Zeile, 10.5 px, ink-3, Abstand 3; Leiste ohne Rahmen/Fugen |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | Doppeltes Innen-Padding (Z. 298 Desktop, Z. 354 mobil) abbauen; Karte als `container-type: inline-size` (Bezug für Zeilen-Umbruch) |
| frontend/src/lib/components/ui/segmented/Segmented.svelte + app.css (Z. 703–726) | MODIFY | NEUE Variante (z. B. `variant="kompakt"`, data-Attribut) nach Mockup Z. 76–78: Hülle card-alt/rule-soft/Padding 2, aktives Segment paper + accent-deep + Ring rule, Höhe 23, Trefferfläche ≥ 44 per `::before` wie `data-tap`. **Keine globale Änderung**: Segmented wird von 17 Dateien genutzt (CompareTabs, MTabBar, HorizonChip, VersandTab …). |
| frontend/src/lib/i18n/messages/de + en | MODIFY | Neue Katalogschlüssel `wetter.hinweis.<metrik_id>` (Tageshöchst · Tagestief, vor der Etappe, Mittelwind, Spitze, Summe, Stufe, Minimum, Gipfel in Wolken, Maximum, m über höchster Stelle, zu wenig ist schlecht) + EN-Übersetzungen. „Vorbote, kein Alarm“ aus `is_precursor`, „nur Anzeige, keine Ampel“ aus `display_only` ableiten, nicht je Metrik doppeln. Metriken ohne Mockup-Hinweis: nur Einheit (Fallback, kein leerer Punkt). |
| frontend/src/lib/components/shared/wetter-tab/ampelModell.ts | MODIFY (klein, evtl.) | Hilfsfunktion `untertitel(id, eig)` → Katalogmodell, damit Komponente und Test dieselbe Logik nutzen |
| frontend/e2e/ (neue Abnahme-Spec) + Werkzeug Ganzseitenbild | CREATE | Ganzseitenaufnahme trotz `main.overflow-auto`/`h-screen` (im Testskript Höhe/Overflow aufheben), Mockup und Staging bei 1280 und 390 px, Trip + Orte, DE + EN |
| frontend/src/lib/components/organisms/wetter-tab/__tests__ (node --test) | CREATE/MODIFY | Untertitel-Logik, Katalogvollständigkeit DE/EN |

### Scope Assessment
- Files: ~8 (Code) + Test/Abnahme
- Estimated LoC: +220/−80 (davon ~60 Katalog, ~70 Abnahme-Spec)
- Risk Level: MEDIUM — nur Darstellung, aber Segmented ist geteilter Baustein (Variante zwingend) und die Tapfläche ≥ 44 px (AC-40 Design-Spec) darf nicht verloren gehen.

### Technical Approach (Empfehlung)
1. **Platz zuerst:** doppeltes Padding in WetterTabInhalt weg → Karte gewinnt ~136 px; Karte wird Container (`container-type: inline-size`, Muster existiert in `HubOverview.svelte:174`, `TripStageRow.svelte:127`).
2. **Zeilenraster wie Mockup** mit `minmax(160px,1fr)` für die Mitte; Umbruch auf zweizeiliges Handy-Layout per `@container (max-width: ~720px)` statt Viewport-Media-Query. Damit kippt 900–1250 px (Seitenleiste 220) nicht mehr auf 0-breite Mittelspalte.
3. **Kompakte Bedienelemente ohne Tapflächen-Verlust:** Knöpfe über vorhandenes `data-tap="true"`-Muster (app.css 513–521); Segment über neue Variante mit gleicher `::before`-Trefferfläche. Optik 23/29 px, Treffer 44 px.
4. **Typografie/Farbe:** Erklärung 12 px, „grün: …“ grün fett, Grenzzahlen nach Mockup, Leiste ohne Rahmen; nur Tokens (Bausteine-Wächter ADR-0112).
5. **Untertitel** über Katalog DE/EN, abgeleitet wo Eigenschaften es hergeben.
6. **Abnahme:** Ganzseitenbild Mockup ↔ Staging je Breite (1280, 1024, 390), Trip + Orte, Zeile für Zeile; zusätzlich Messwerte (Spaltenbreiten, Zeilenhöhe ≤ Mockup + Toleranz, Mittelspalte ≥ 160 px bei 1024) als automatische Zusicherung. Danach Bild an den PO (Memory: jede Scheibe endet mit Soll/Ist-Bild).
- Sichtweite km→m bleibt außerhalb (#2946).

### Gegen den Plan sprechende Befunde
- Container-Query-Schwelle: Mockup bricht bei Viewport 760 ohne Seitenleiste; die Kartenbreite dort ≈ 700. Exakte Schwelle in der Spec festlegen und an 1024/1100 messen (vorher 0/22 px Mittelspalte).
- Segment-Variante statt Umbau: mehr Code als globale Änderung, aber globale Änderung würde CompareTabs/MTabBar/HorizonChip mitverändern → nicht akzeptabel.
- Keine weiteren.

### Dependencies
- Segmented-Atom (Re-Export `atoms/Segmented` → `ui/segmented/Segmented.svelte`), Btn-Atom `size="tap"`.
- i18n-Katalog + Hardcode-Wächter (`hardcode_allowlist.json`), Bausteine-Wächter (nur Tokens).
- Trip und Orte nutzen dieselben Organismen (ADR-0097) → eine Änderung wirkt in beiden Kontexten.

### Open Questions
- keine Produktfrage offen (Mockup ist freigegebenes Soll).
