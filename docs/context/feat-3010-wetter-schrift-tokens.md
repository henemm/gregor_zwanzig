# Context: feat-3010-wetter-schrift-tokens

## Request Summary
Issue #3010 (Epic #2913, ADR-0112): Schriftgrößen in den Wetter-Organismen nicht mehr aus Abstands-Tokens (`font-size: var(--g-s-*)`), sondern aus Schrift-Tokens. Bild Mockup gegen Staging zeigt dieselben Schriftgrößen; ein Wächter-Test färbt einen Rückfall rot.

## Related Files
| Datei | Relevanz |
|---|---|
| frontend/src/app.css:151-159 | `--g-text-xs..5xl` = 11/13/15/17/20/24/32/44/60 px (nur in `:root`) |
| frontend/src/app.css:170-171 | `--g-s-3`=12px, `--g-s-4`=16px (Abstände) |
| frontend/src/app.css:183-214 | Maß-Tokens `--g-size-*` (10, 10.5, 11.5, 12.5, 13, 14, 18 px ...), KEIN 12px/16px |
| frontend/src/app.css:309 | `:root[data-theme="dark"]` überschreibt nur Farben; Schrift-/Maß-Tokens sind themenunabhängig |
| organisms/wetter-tab/MetrikZeile.svelte:126,145,163 | Fundstellen |
| organisms/wetter-tab/VorlageKarte.svelte:232 | Fundstelle |
| organisms/wetter-tab/GrenzenEditor.svelte:112,121,161 | Fundstellen |
| organisms/zustellung-tab/StilleStunden.svelte:131 | Fundstelle |
| molecules/EinstellTabelle.svelte:198 | Fundstelle |
| frontend/src/lib/__tests__/bausteine_waechter_regeln.ts (767 Z.) | Regeln; `tokenGruende()` Z.281, `AUSNAHMEN` Z.721 |
| frontend/src/lib/__tests__/bausteine_waechter.test.ts | Wächter-Tests (AC-3 Regel (b) Z.152-203) |
| docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html | Mockup-CSS |
| frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts + frontend/playwright.2913-metrikliste.staging.config.ts | Ganzseitenbild Wetter |

(Alle Komponentenpfade unter frontend/src/lib/components/.)

## Existing Patterns
- Wächter Regel (b) erkennt `var(--g-s-3)` als gültiges Token (ersetzt jedes `var(--g-*)` durch TOKEN). Eine Schrift-Größe aus Abstands-Token ist daher heute unsichtbar; keine Prüfung welches Token-Präfix.
- Neue Kleinstufen wurden bisher als `--g-size-*px` ergänzt (z. B. `--g-size-12-5px`, `-10-5px`, `-11-5px`, Kommentar "Kleinschrift") und für font-size genutzt (z. B. MetrikZeile `--g-size-14px`, `--g-size-12-5px`).
- design_system.md Z.154-162 listet nur die 9 `--g-text-*`; Z.183 `--g-s-*`. ADR-0112 Z.17: "Schrift ... über var(--g-*)" (keine Präfixregel für font-size).

## Dependencies
Alle Selektoren sind scoped in Svelte-`<style>`; Änderung wirkt nur auf Wetter-Reiter, Zustellung-Stille-Stunden, EinstellTabelle (verwendet laut Z.507 auch in Vorschauseite B3a). Staging/Prod laden app.css global.

## Existing Specs
docs/specs/modules/fix_2913_metrikliste_mockup.md, feat_2913_abgleich_ganzseite.md (Wetter-Mockup-Abgleich, Messwert-Zusicherungen).

## Risks
- 12px und 16px haben keine `--g-text-*`-Stufe; Umstellung auf 13 px (`--g-text-sm`) würde die Schrift sichtbar ändern (Ganzseitenbild, Zeilenhöhen/Umbruch in MetrikZeile, AC-4 Toleranz ≤124 px Zeilenhöhe in `.wt-why`).
- Mobil-Regel `font-size: 16px` (GrenzenEditor:161, StilleStunden:131) verhindert iOS-Zoom beim Fokus: darf NICHT unter 16 px fallen.
- EinstellTabelle:198 ist ein Baustein mit eigener Vorschau/Tests; Mockup-Entsprechung `.kx .kn small` = 12px.
- Wächter-AUSNAHMEN-Ratsche: Dateien in der Liste dürfen nur sinken; neue Regel darf keine Bestands-Zählung verschieben (siehe Wächter-Ansatz).

## Analysis
Type: Refactor / Design-System-Token (kein Verhaltens-Change, pixelgleich).

### 1. Fundstellen
| Fundstelle | Element | heute px | Mockup px (Selektor) | Ziel-Token |
|---|---|---|---|---|
| MetrikZeile:126 | `.wt-zeile [data-slot=btn][data-tap]` (kompakter Knopf) | 12 | 12 (`.btn.sm{...font-size:12px}`, Z.48) | `--g-text-2xs`... siehe Empfehlung: neu `--g-text-12`/`--g-size-12px` |
| MetrikZeile:145 | `.wt-name small`, `.wt-lbl` (Untertitel, Aktions-Label) | 12 | 12 (`.mr .nm small`, `.mr .act .lbl`, Z.102/110) | wie oben (12) |
| MetrikZeile:163 | `.wt-why` (Erklärtext) | 12 | 12 (`.why{font-size:12px}`, Z.117) | wie oben (12) |
| VorlageKarte:232 | `.wt-option small` (Menü-Option Untertext) | 12 | 11.5 (`.vmenu small{font-size:11.5px}`, Z.125) | Abweichung 0,5 px; Ziel 11.5 = `--g-size-11-5px` (existiert) oder 12 beibehalten (PO/Spec entscheiden) |
| GrenzenEditor:112 | `.wt-grp-name` (Gruppenname) | 12 | 10 (`.edit .grp > span`, Z.113, Caps-Mono) | Abweichung; Ziel 10 = `--g-size-10px` (existiert) falls Mockup-Treue gewollt, sonst 12 |
| GrenzenEditor:121 | `.wt-feld` (Feldlabel) | 12 | 10 (`.field label`, Z.89) | wie oben |
| GrenzenEditor:161 | `.wt-feld [data-slot=input]` <900px | 16 | Mockup hat keine Mobilregel (Input 14 / `.input.sm` 12); 16 = iOS-Zoom-Schutz | neu `--g-text-16`/`--g-size-16px` (bewusste Abweichung, begründen) |
| StilleStunden:131 | `.zt-minuten [data-slot=input]` mobil | 16 | dito | wie oben (16) |
| EinstellTabelle:198 | `.et-name small` | 12 | 12 (`.kx .kn small`, Z.216) | 12-Stufe |

### 2. Design-System
Vorhanden: nur 11/13/15/17 ... (`--g-text-*`, app.css:151-159, `:root` einmal, Dunkel überschreibt keine Größen, app.css:309 nur Farben). Maß-Tokens ohne 12 und 16 (`--g-size-12-5px`=12.5 ist NICHT 12). Es gibt also KEIN Token für 12 px und 16 px.
Empfehlung: Mockup nutzt 12 px für 6 der 8 Stellen (Kleinschrift Kaptionen/Knöpfe), 10/11.5 für Sonderfälle. Vorhandene Stufen reichen nicht pixelgleich (11 oder 13 wären Abweichung). Daher zwei neue Schrift-Stufen in app.css `:root` (+ Tabelle design_system.md Z.154ff.): `--g-text-2xs`-Muster passt nicht (xs=11 ist schon klein); Vorschlag: Zahlennamen entsprechend dem bestehenden `--g-size-12-5px`-Muster: `--g-text-12px` und `--g-text-16px` (Doku "Schrift-Zwischenstufen, Mockup .btn.sm/.why, iOS-Zoom-Schutz"). Hell/Dunkel: kein zweiter Eintrag nötig (Größen themenunabhängig; ein `:root`-Eintrag). Alternative (konservativ): Mockup-Treue 11.5/10 nutzen vorhandene `--g-size-*`, braucht aber dann Wächter-Regel, die `--g-size-*` für font-size zulässt. Entscheidung offen (siehe Open Questions).

### 3. Wächter
Muster: Regel (b) in `tokenGruende(eigenschaft, wertRoh)` (bausteine_waechter_regeln.ts:281) liefert Gründe-Strings; Zähler `zaehleTokenVerstoesse` -> Ratsche AUSNAHMEN. Neue Regel: in `tokenGruende` bei `eigenschaft === 'font-size'` und Wert enthält `var(--g-s-` oder `var(--g-space` -> Grund `Schriftgröße aus Abstands-Token (--g-s-*), nur --g-text-*`. Geltungsbereich: alle Baustein-Ordner (atoms/molecules/organisms), nicht nur Wetter. Empfehlung: ALLE, weil Regel (b) schon alle Bausteine prüft; Bestand ist laut grep nur die 9 Fundstellen (alle in Bausteinen). Sie zählen dann in AUSNAHMEN zusätzlich: nach Umstellung auf 0 neu erhoben (`istStand`-Helfer Z.486) bzw. Einträge für MetrikZeile/VorlageKarte/GrenzenEditor/StilleStunden/EinstellTabelle prüfen und senken. Besser eigener Fehlertext statt Zähler (hart, nicht ratschenfähig, Bestand 0 erzwingen). Tests in bausteine_waechter.test.ts nach AC-3-Muster (rot: `font-size: var(--g-s-3)`; grün: `var(--g-text-sm)`), plus Quellbaum-Test AC-7 bleibt grün.

### 4. Rohe/off-scale Werte in Wetter-Organismen
`grep font-size: <zahl>px` in organisms/wetter-tab, zustellung-tab, EinstellTabelle: keine rohen px. Off-Skala nur über `--g-size-*`: MetrikZeile `--g-size-14px` (.wt-name b), `--g-size-12-5px` (.wt-nur), `--g-size-18px` (.wt-rm); GrenzenEditor `--g-size-14px` (Input), `--g-size-12-5px` (.wt-hint). `--g-text-sm` bereits in `.wt-fehler`.

### 5. Ganzseitenbild
`cd frontend && npx playwright test --config playwright.2913-metrikliste.staging.config.ts` (Spec e2e/fix2913-metrikliste-mockup.staging.spec.ts; Aufnahmen Mockup+Staging 1280/1024/390, Trip+Orte, DE+EN, nach `$BILD_DIR`); anschließend Agent `mockup-bildpruefer` über die Bildpaare. Nur gegen Staging nach Push, nicht in CI.

### Affected Files
- MODIFY: frontend/src/app.css (neue Stufen), docs/reference/design_system.md (Tabelle), 5 Komponenten (siehe oben), bausteine_waechter_regeln.ts, bausteine_waechter.test.ts, ggf. AUSNAHMEN.
- CREATE: keine (ggf. Spec docs/specs/modules/feat_3010_wetter_schrift_tokens.md).

### Scope
~8 Dateien, <100 LoC; kein Verhalten.

### Technical Approach
1. 12px/16px-Stufen anlegen (app.css, Doku). 2. 9 Fundstellen umstellen (pixelgleich zu heute, um Layout/AC-4-Zeilenhöhe nicht zu brechen; Mockup-Abweichungen 11.5/10 getrennt entscheiden). 3. Wächterregel + Tests (rot vor Umstellung). 4. Staging-Bildabgleich.

### Open Questions
- Pixelgleich zu heute (12) oder Mockup-treu (VorlageKarte 11.5, GrenzenEditor-Labels 10)? Empfehlung: pixelgleich zu heute, Abweichungen als eigenes Issue.
- Benennung: `--g-text-12px`/`--g-text-16px` (Maßmuster) vs. Rangnamen; Empfehlung Zahlennamen.

### Entscheidung Tech Lead (19.11.2026)
Pixelgleich zu heute umstellen: neue Stufen `--g-text-12px` (12 px) und `--g-text-16px` (16 px) in `:root` (Dunkel-Theme überschreibt nur Farben). Die vorhandenen Mockup-Abweichungen (VorlageKarte 11,5 px, GrenzenEditor-Beschriftungen 10 px) bleiben unverändert — reine Token-Umstellung ohne sichtbare Änderung; 10 px widerspräche zudem dem Leitprinzip Lesbarkeit (design_system.md). 16 px der mobilen Eingabefelder bleibt (Zoom-Schutz). Wächter-Regel gilt für alle Baustein-Ordner, damit auch StilleStunden und EinstellTabelle umgestellt werden.
