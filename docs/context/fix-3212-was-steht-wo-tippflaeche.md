# Context: fix-3212-was-steht-wo-tippflaeche

## Request Summary
Issue #3212: In der Karte „Was steht wo“ (Reiter Wetter, #3122 B3b) liegen Knöpfe unter 44 px Tippfläche; Wächter AC-40 (`frontend/e2e/s3a2794-teil3-design.spec.ts:103`, „Touch-Ziele < 44 px“) ist rot. Betroffen: (a) „Roh“ 32×22 und „Einfach“ 56×22, nur Desktop (`RohEinfachKnopf`); (b) `was-steht-wo-email-format-full|compact` (Segmented sm): Desktop 19 px, Mobil 36 px hoch. Soll: ≥44 px Tippfläche, Optik laut Mockup Fassung 4.

## Related Files
- `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:244-259` — Segmented `rolle="radio" size="sm"` mit testids `was-steht-wo-email-format(-full|-compact)`; kein `variant`.
- `frontend/src/lib/components/ui/segmented/Segmented.svelte` (atoms/Segmented.svelte ist Re-Export) — Prop `variant?: 'kompakt'` setzt `data-variant`.
- `frontend/src/app.css:754-757` (`data-size="sm"`: Padding 2px 8px, text-xs ⇒ 19 px), `:763-806` (Variante „kompakt“ = Mockup `.seg`, Trefferfläche per `::before` max(100%, --g-tap-min)), `:183-187` (`--g-tap-min: 44px`), `:519-531` (Btn `data-tap` mit `::before`).
- `frontend/src/lib/components/atoms/RohEinfachKnopf.svelte:23-80` — Knopf `.rek` (`min-height:0`, Pille Padding 3/6, 10.5 px mono); Tippfläche 44×44 nur in `@media (max-width: 899px), (pointer: coarse)` (Z. 73-80), auf Desktop keine ⇒ 32×22 / 56×22.
- `frontend/src/lib/components/molecules/EinstellTabelle.svelte:128` (Einsatz), `:283-300, :344-352` (Raster, Kurzwort, Mobil-Anordnung Haken/Knopf).
- `frontend/src/lib/components/atoms/Haken.svelte:71-78, 162-167` — Haken: Tippfläche 44 nur schmal/Touch bzw. ganzes `<label>` ≥ --g-tap-min bei Text-Variante.
- Verwandte Verwendungen von Segmented kompakt: `organisms/zustellung-tab/KanalTabelle.svelte:124`, `wetter-tab/MetrikZeile.svelte:87`.
- Wächter: `frontend/e2e/s3a2794-teil3-design.spec.ts:35-85` (`zuKleineZiele`), `:96-104` (`pruefeReiter`), `:107+` (AC-40 desktop/mobil); `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` (Bausteinregeln, verbietet rohe `<button>`/`<style>` außerhalb Atome; Segmented.svelte Z. 675 ausgenommen); `harte_farben_waechter` nicht betroffen (nur Token genutzt).
- Tests: `frontend/src/lib/components/atoms/__tests__/haken_roh_einfach.test.ts` (RohEinfachKnopf: Z. ~120 prüft Knopf-Markup/testid), `organisms/__tests__/was_steht_wo_karte.test.ts`, `lib/__tests__/elementliste_aktuell.test.ts`, `shared/__tests__/s3a2794_speicher_owner_waechter.test.ts`; E2E `frontend/e2e/was-steht-wo-karte.spec.ts`, `was-steht-wo.helpers.ts`.
- Mockup: `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` — `.mini` (Z. 233: 10.5 px mono, Padding 3px 6px, Rand 1px, Radius 3) für Roh/Einfach (Z. 631, 637); `.seg` (Z. 78-81: Padding 2, Gap 2, Buttons 4px 10px, 11.5 px/600, aktiv `--g-paper` mit Ring) für „E-Mail: Format“ (Z. 598, `seg('mailfmt',…)`).

## Existing Patterns
- Unsichtbare Tippfläche bei gleicher Optik: `position:relative` + `::before` zentriert, `width/height: max(100%, var(--g-tap-min))` (Btn `data-tap="true"`, Switch `tap`, Segmented `variant="kompakt"`). Der Wächter erkennt genau diese zwei Fälle (`data-tap="true"` und `[data-slot=segmented][data-variant=kompakt] [data-slot=segmented-item]`, Z. 53) und prüft dort per `elementFromPoint` das 44×44-Quadrat (Mitte + 4 Ecken, 1 px eingerückt); alle anderen Elemente: Bounding-Box ≥ 44×44. Eine `::before`-Vergrößerung ohne `data-tap` zählt also NICHT (Box bleibt 32×22).
- Mobil hat RohEinfachKnopf schon 44×44 per min-width/min-height (Reihe wächst dort nicht, Raster-Spalte = 44).
- Haken-Atom ist vom Native-Control-Check ausgenommen (#3190), Segmented-Zeilen im Reiter nutzen kompakt.

## Dependencies
Karte -> EinstellTabelle -> Haken, RohEinfachKnopf; Karte -> Segmented (ui). Änderungen an `app.css` (Segmented kompakt) und Atom RohEinfachKnopf wirken auf: KanalTabelle, MetrikZeile, Design-System-Seite `routes/_design-system/einstelltabelle/+page.svelte`.

## Existing Specs/ADRs
`docs/specs/modules/feat_3122_was_steht_wo.md` (Teil B Nr. 10-13, ACs Haken/Roh-Einfach, Tippfläche), ADR-0112 (Bausteine: nur Atome/Moleküle, keine eigenen `<style>`/rohen Buttons ausserhalb), ADR-0124; `docs/reference/design_system.md:300-305` (44-px-Regel, einzige Mausausnahme Vorlagen-Wähler), Charter §7.

## Risks
- Desktop-Zeilen der Tabelle sind kompakt (Haken-Kästchen nur schmal/Touch 44); `min-height:44` auch auf Desktop würde Zeilen aufblähen und vom Mockup abweichen ⇒ nicht den Mobil-Weg auf Desktop ausweiten.
- `::before` von „Roh“ (32 px breit) ragt 6 px seitlich in Nachbarn (Haken-Label, nächste Spalte); `elementFromPoint`-Prüfung an den Ecken (±21 px) muss das eigene Element treffen — Überdeckung durch spätere/positionierte Nachbarn live in Playwright prüfen (Desktop und Mobil).
- Segmented kompakt hat `overflow: visible`, `flex-wrap`; Mobil: Zeile „E-Mail: Format“ muss weiter umbrechen können (Ausführlich/Kompakt nebeneinander, Ecken-Treffer des zweiten Segments).
- Goldens: keine Golden-Datei unter `tests/golden/*` enthält `was-steht-wo`/`roh-einfach` (Treffer nur `data-size="sm"` in f6_versand_tab/f3_home_listen – dort unverändert, weil `size="sm"`-Regel nicht angefasst wird). Node-Tests mit Markup-Erwartung (haken_roh_einfach.test.ts Z.~120, was_steht_wo_karte.test.ts) prüfen ggf. neues Attribut `data-tap`/`variant`.
- Wächter nicht aufweichen: Ausnahme nur mit Begründung; hier nicht nötig, da beide Muster schon anerkannt (`data-tap` ist erkannt, kompakt ist erkannt).

## Analysis
### Type: Bug
### Root Cause
(a) `RohEinfachKnopf` setzt die Mindestgröße 44 nur unter `@media (max-width:899px),(pointer:coarse)`; auf Desktop ist das Element nur so groß wie die Pille (32×22/56×22), und `data-tap="true"` fehlt, sodass der Wächter die Bounding-Box misst. (b) Das Segment-Paar „E-Mail-Format“ nutzt `size="sm"` (Padding 2/8, 19 px; mobil 36 px durch globalen Knopfboden app.css:921-935), nicht die Mockup-Variante `.seg` = `variant="kompakt"` mit unsichtbarer 44er-Fläche.
### Affected Files (with changes)
1. `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` (~Z. 245): `size="sm"` ersetzen durch `variant="kompakt"` (wie KanalTabelle/MetrikZeile). Optik = Mockup `.seg`.
2. `frontend/src/lib/components/atoms/RohEinfachKnopf.svelte`: Knopf `data-tap="true"` + `position:relative` + `::before` (absolut, zentriert, `width/height: max(100%, var(--g-tap-min))`) für alle Breiten; die Mobil-Regel (min-width/min-height auf dem Knopf selbst) bleibt oder wird auf `::before` vereinheitlicht (dann Raster-Spalten unverändert 44). Pille unverändert (Mockup `.mini`).
3. Node-Tests: `haken_roh_einfach.test.ts` ergänzen (RED: Knopf trägt `data-tap="true"`; Karte rendert Segmented mit `data-variant="kompakt"`); E2E-Wächter AC-40 bleibt unverändert und wird grün (Gegenprobe: `data-tap` entfernen ⇒ rot).
4. Keine Änderung an Goldens, Wächterregeln oder Tokens erwartet. Spec `feat_3122_was_steht_wo.md`: ggf. ein AC-Satz „Tippfläche ≥ 44 px bei Mockup-Optik“.
### Scope Assessment
Klein: 2 Quelldateien (+1-2 Testdateien), < 40 LoC, kein Backend, frontend-only Deploy.
### Technical Approach
Vorhandenes Muster statt Neuem: Segmented `variant="kompakt"` (Token `--g-tap-min`, `::before`), Roh/Einfach analog Btn-`data-tap`. Gilt für Desktop und Mobil (mobil ersetzt kompakt den 36-px-Knopfboden, der Wächter prüft dort per Trefferpunkten; Kurzwort „Einf.“ und Raster bleiben). Danach AC-40 in Playwright desktop+mobil gegen Staging.
### Befunde gegen den Plan
- Ausweitung der Mobil-Lösung (min-height 44 am Knopf) auf Desktop wäre falsch: bläht Zeilen auf, weicht vom Mockup `.mini` ab.
- Ohne `data-tap` zählt `::before` im Wächter nicht (Bounding-Box-Messung) – Muster und Wächter müssen zusammen passen.
- Mobil-Segmente: 36 px kommt vom globalen Knopfboden, nicht von der Karte.
### Open Questions
Keine Produktfragen.
