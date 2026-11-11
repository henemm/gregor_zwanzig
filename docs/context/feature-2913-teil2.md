# Context: feature-2913-teil2 (#2913, Teil 2 — Bausteine aus dem Mockup)

## Request Summary
Teil 2 der freigegebenen Spec `docs/specs/modules/feat_2913_s3_bausteine.md` (AC-11 bis AC-23): Ampel-Tokens, Atom-Erweiterungen (Input-Unterkante, Segmented-Farbpunkt, Skelett), Molekül Einstellungszeile und Chip-Leiste, Organismen ohne rohe Controls, `WetterTab` als dünne Seite in `SEITEN_SCOPE`. Teil 1 ist live (972b95e, PR #2929); vorausgehende Analyse: `docs/context/feature-2913-bausteine.md`.

## Related Files (Stand nach Teil 1)
(Pfade unter `frontend/src/`)

| File | Relevance |
|------|-----------|
| `lib/components/atoms/Input.svelte` | reicht nur an `ui/input/input.svelte` weiter (Props `size`, `error`); keine Ampel-Variante |
| `lib/components/atoms/Segmented.svelte` | wrappt `ui/segmented/Segmented.svelte`; neue API `items/value/onChange/size`, alte `options/selected/onselect`; Option `{value,label,badge?,testid?,badge_testid?}`; **bei `items`-API werden `testid`/`badge_testid` auf undefined gesetzt (Z.37)**; kein Farbpunkt |
| `lib/components/atoms/index.ts` | Switch, SectionH, AvatarStack, KV, Eyebrow, Pill, Card, Btn, Input, Dot, WIcon, ElevSparkline, TopoBg, Segmented, PageHeader, BackLink, Stat — **kein Skelett** im ganzen `src` |
| `lib/components/molecules/index.ts` | Field, DetailRow, StagePill, ChannelRow, ChannelChip, ThresholdRow, HorizonChips u. a.; **keine generische Einstellungszeile / kein generischer Chip** (ChannelChip ist kanal-spezifisch) |
| `lib/components/organisms/wetter-tab/*.svelte` | alle neun mit `<style>`; rohe `<button>`: VorlageKarte 7, MetrikZeile 2, AnpassenKarte 1, NichtImBriefing 1, WarnungenRadarKarte 1, WetterTab 1; rohes `<input>`: GrenzenEditor 1; kein select/textarea |
| `organisms/wetter-tab/AmpelLeiste.svelte` Z.19-22 | Behelfsfarben `green: --g-success`, `yellow: --g-wx-sun`, `orange: --g-accent`, `red: --g-danger` |
| `organisms/wetter-tab/WetterTab.svelte` (371 Z.) | Script bis Z.214 (7 `$state`, `onMount` lädt `ladeWetterDaten` + `VERGLEICHS_KATALOG[context]()`, Speicherer aus `wetterTabSpeicherung.ts`), `<style>` ab Z.288, 9× `class=`, Kind-Komponenten als `./`-Geschwister, Imports aus `shared/corridor-editor/compareMetricCatalogLoader.ts`, `shared/weather-metrics-tab/compareMetricSelection.ts`, `shared/wetter-tab/*.ts` |
| `lib/__tests__/bausteine_waechter_regeln.ts` | `SEITEN_SCOPE` leer (Z.504, Opt-in), `FREIGEGEBENE_KOMPOSITIONEN` leer; Regel a: kein `<style>`/`style=`/`style:`/Tailwind, keine rohen button/input/select/textarea/table, Komponenten-Importe nur aus `$lib/components/{atoms,molecules,organisms}`; **Baustein-Dateien dürfen nicht in `SEITEN_SCOPE` (Z.466)** ⇒ WetterTab muss für Regel a aus `organisms/` heraus an einen Seiten-Ort; `BESTAND_OBERGRENZE = 204` (Z.718) |
| `app.css` | Light `:root` ~Z.95-250 (`--g-card #ffffff` Z.233, `--g-success #3d6b3a`, `--g-danger #a83232`, `--g-wx-sun #e8a820`, `--g-accent #c45a2a`); Dark `:root[data-theme="dark"]` ab Z.293 (`--g-card #1d1d1a`); kein `--g-ampel-*` |
| `routes/_design-system/+page.svelte`, `showcase.test.ts` | Test prüft nur Import-Regex, Sektionsnamen und Stichproben (Switch, Btn, Pill, Stat, AlertRow, ChannelRow) — AC-20 verlangt Ausbau auf „jedes neue Atom“ |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Ampel `--a-green #15803d / --a-yellow #d69500 / --a-orange #d4530a / --a-red #a8104a` (Z.15); `.skel` Z.201 (14px, r 4px, `--g-rule-soft`); `.lrow` Z.140-145; `.more`/`.chip` Z.135-136; Input-Unterkante `.lr/.lo/.ly` 3px (Z.112); Segmented-Punkt `.seg .d` 8px rund (Z.79, Markup Z.356) |

## Existing Patterns
- Atome sind dünne Wrapper um `ui/*`-Primitive; Seiten importieren nie `ui/` direkt.
- Kontrast-Tests: kein gemeinsamer Helfer, je Test lokale `kontrast()`/`luminanz()` (`lib/__tests__/dark_palette_kontrast.test.ts:76/83`, `pill_toene_kontrast.test.ts`, `danger_flaeche_kontrast.test.ts` u. a.) — Vorbild für AC-11.
- Tests laufen über `node --test` (kein Vitest).
- Trip/Vergleich: ein `WetterTab` mit `context="route"|"vergleich"`, Importeure TripTabs, CompareTabs, TripNewEditor, CompareNewEditor.

## Dependencies
- Upstream: `shared/wetter-tab/*.ts` (Logik, unverändert, AC-22), `ui/input`, `ui/segmented`, i18n `wetter.json` DE/EN (unverändert, AC-21).
- Downstream: TripTabs, CompareTabs, TripNewEditor, CompareNewEditor; Staging-Suite `playwright.2794-s3a3.staging.config.ts` (55 Tests, Teil 1 grün).

## Existing Specs
- `docs/specs/modules/feat_2913_s3_bausteine.md` — freigegeben, Teil 2 = AC-11..AC-23
- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` — Verhalten des Wetter-Reiters
- ADR-0112, ADR-0097, ADR-0104

## Risks & Considerations
- **Seiten-Ort von WetterTab:** Regel verbietet Baustein-Dateien in `SEITEN_SCOPE` (Z.466). AC-17 verlangt WetterTab in `SEITEN_SCOPE` ⇒ Teil 2 muss WetterTab aus `organisms/` an einen Nicht-Baustein-Ort verschieben (z. B. zurück unter `shared/` oder eigene Seiten-Komposition) — in `/20-analyse` klären; Importeure und Pfad-Tests (`s3a2794_teil3_keine_nativen_controls.test.ts` erwartet Bausteine unter `organisms/wetter-tab/`) mitziehen.
- **Testids bei Segmented:** E2E-Suite nutzt `getByTestId(WT.alarmAbStufe(id,'red'))` mit `aria-checked`. Die `items`-API von `atoms/Segmented` verwirft `testid` ⇒ Atom so erweitern, dass Testids je Segment erhalten bleiben (sonst bricht die Staging-Suite).
- **Weitere E2E-Selektoren:** `[data-testid^="wetter-zeile-"]`, `aria-checked` auf Schaltern (`role=switch`), `getByRole('radio', {name:/^(Roh|Einfach)$/})` = 0, `karte.locator('select')` = 0, `NATIV`-Liste in design.spec — Testids und ARIA-Rollen müssen beim Umbau auf Atome erhalten bleiben (AC-9 erlaubt nur Anpassung von Struktur-Selektoren, keine Abschwächung).
- **Dark-Kontrast Gelb:** Mockup-Gelb `#d69500` auf Weiß liegt knapp unter 3:1 ⇒ abdunkeln; Dark-Block braucht eigene, hellere Werte gegen `#1d1d1a`.
- **WetterTab-Logik:** 7 `$state`, Laden und Speichern im Script — beim Ausdünnen in `.ts`-Module/Organismen auslagern, ohne die `.ts`-Logikmodule zu ändern (AC-22 erlaubt nur Importpfade).
- **Showcase-Test** muss auf „jedes neue Atom kommt vor“ ausgebaut werden (AC-20).
- Sichtbare Änderung ⇒ Staging-Verifikation in Light und Dark für Trip und Orts-Briefing (AC-23), DE und EN.

## Analysis

### Type
Feature (Teil 2 der freigegebenen Spec `feat_2913_s3_bausteine.md`, AC-11..AC-23). Spec ist bereits freigegeben; `/30-write-spec` ergänzt nur einen Abschnitt „Umsetzungsplan Teil 2 / Klarstellungen“, ohne ACs inhaltlich zu ändern.

### Kernentscheidungen (Tech Lead)
1. **Seiten-Ort:** `SEITEN_SCOPE` ist eine exakte Dateiliste; Baustein-Dateien dürfen nicht hinein. Regel a wertet jeden Import unter `lib/components/` außerhalb atoms/molecules/organisms als Verstoß (auch `.ts` und `import type`). ⇒ Neue Seite `lib/components/shared/WetterTab.svelte` (flach, Konvention wie `shared/VersandTab.svelte`, `shared/AlarmeTab.svelte`) als reine Durchreichung: `import WetterTabInhalt from '$lib/components/organisms/wetter-tab/WetterTabInhalt.svelte'`, `let { context, ...rest }: ComponentProps<typeof WetterTabInhalt> = $props()` (`context` explizit, wegen `propNamen`-Prüfung in `s3a2794_teil3_wettertab_mount.test.ts`). Nicht `shared/wetter-tab/` (widerspricht AC-3/AC-8).
2. **Zustand/CSS:** heutige `organisms/wetter-tab/WetterTab.svelte` per `git mv` → `WetterTabInhalt.svelte` (7 `$state`, `onMount`, Laden/Speichern, `<style>` nach Regel b). `shared/wetter-tab/*.ts` unverändert (AC-22). Kein `.svelte.ts`-Controller (bräuchte Missbrauch von `FREIGEGEBENE_KOMPOSITIONEN`).
3. **AC-15 Wortlaut „Molekül NichtImBriefing“:** generisches Molekül heißt `molecules/ChipLeiste.svelte`; `NichtImBriefing` bleibt Organismus unter `organisms/wetter-tab/` und baut auf `ChipLeiste` auf (sonst Bruch mit AC-3, Barrel-Test). In der Spec als Klarstellung festhalten.
4. **Ampel-Tokens (AC-11), WCAG gegen Karte:**

| Token | Light (vs #ffffff) | Dark (vs #1d1d1a) | Mockup |
|---|---|---|---|
| `--g-ampel-gruen` | `#15803d` (5,02) | `#15803d` (3,37) | `#15803d` |
| `--g-ampel-gelb` | `#b98100` (3,39) | `#d69500` (6,56) | `#d69500` (hell nur 2,57) |
| `--g-ampel-orange` | `#d4530a` (4,17) | `#d4530a` (4,06) | `#d4530a` |
| `--g-ampel-rot` | `#a8104a` (7,40) | `#d43a76` (3,75) | `#a8104a` (dunkel nur 2,28) |

   Test-Toleranz „nahe am Mockup“: Hue ±8°, Light-Helligkeit ±8 HSL-Punkte, Dark-Helligkeit ≥ Mockup und ≤ +20. Light-Werte im ersten `:root` (Kontrasttests lesen ersten Treffer), Dark im `:root[data-theme="dark"]`-Block.
5. **Atome:** `Input` Prop `ampel?: 'green'|'yellow'|'orange'|'red'` → `data-ampel` (englische Schlüssel wie `ampelModell.ts`), 3px-Unterkante per CSS in `app.css`; ohne Prop Markup unverändert. `ui/segmented/Segmented.svelte`: Option `farbe?` → `<i data-slot="segmented-punkt" data-farbe>`; `items`-API reicht künftig `testid`/`badge_testid`/`farbe` durch (heute Z.37 verworfen). Neues Atom `atoms/Skelett.svelte` (`role="status" aria-busy="true"`, `aria-label` vom Aufrufer, keine Eigentexte), im Barrel.
6. **Touch-Ziele:** `s3a2794-teil3-design.spec.ts` verlangt ≥44px für Buttons/Radios/Switches; `Btn` ist 24–36px, `::after` zählt nicht in `getBoundingClientRect`. ⇒ neue `Btn`-Größe `tap` (44px) in `ui/btn` + `app.css`, vor dem Organismen-Umbau.
7. **Known Limitations:** `WarnungenRadarKarte` und `AnpassenKarte` behalten ihre rohen `role=switch`/Toggle-Buttons — `atoms/Switch.svelte` ist `<span>` mit fest verdrahtetem `data-testid="switch"`, ohne restProps/`aria-checked` ⇒ E2E `wetter-warnungen-schalter`/`wetter-radar-schalter` bräche. AC-16 nennt beide Organismen nicht. Folge-Issue für Switch-Atom anlegen.
8. **Goldens:** `organisms/__tests__/wetter_tab_render_gleich.test.ts` + `fixtures/wetter_tab_vor_2913/` löschen (Testkopf sieht das für Teil 2 vor; Ersatz AC-23 Staging-Sichtvergleich). SSR-Goldens `tests/golden/f9_trip_flaechen/anlegen_{route,etappen,weiter}.{de,en}.html`, `f10_vergleich_flaechen/anlegen_weiter.{de,en}.html` neu schreiben (`GZ_GOLDEN_SCHREIBEN=de|en`), Diff prüfen: nur Markup/Hash, Texte gleich (AC-21).

### Affected Files (Pfade unter `frontend/src/lib/components/` sofern nicht anders)
| File | Change | Description |
|---|---|---|
| `frontend/src/app.css` | MODIFY | `--g-ampel-*` Light+Dark; Regeln Input-Ampel, Segmented-Punkt, Skelett, Btn `tap` |
| `atoms/Input.svelte`, `ui/input/input.svelte` | MODIFY | Prop `ampel` → `data-ampel` |
| `ui/segmented/Segmented.svelte`, `atoms/Segmented.svelte` | MODIFY | `farbe`, Testids bei `items`-API durchreichen |
| `ui/btn/*` | MODIFY | Größe `tap` |
| `atoms/Skelett.svelte`, `atoms/index.ts` | CREATE/MODIFY | Skelett-Atom + Barrel |
| `molecules/Einstellungszeile.svelte`, `molecules/ChipLeiste.svelte`, `molecules/index.ts` | CREATE/MODIFY | Titel/Hinweis/Slot; Chips aus `Btn` |
| `organisms/wetter-tab/WetterTab.svelte` → `WetterTabInhalt.svelte` | MOVE | Zustand, Laden, CSS; Skelett-Atom, Fehler-Knopf als `Btn` |
| `shared/WetterTab.svelte` | CREATE | dünne Seite, in `SEITEN_SCOPE` |
| `organisms/wetter-tab/AmpelLeiste.svelte` | MODIFY | `var(--g-ampel-*)`; Stufe ohne Farbe erkennbar (`role="img"` + `aria-label`/`data-farbe`) |
| `organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | 7 rohe Buttons → `Btn` (aria-expanded/haspopup/testid über restProps) |
| `organisms/wetter-tab/MetrikZeile.svelte` | MODIFY | 2 Buttons → `Btn`; Alarm-ab-Stufen mit `farbe` |
| `organisms/wetter-tab/GrenzenEditor.svelte` | MODIFY | rohes input → `Input ampel={f}` (testid überschreibt Default) |
| `organisms/wetter-tab/AlarmAbKopf.svelte` | MODIFY | Zeile als `Einstellungszeile` |
| `organisms/wetter-tab/NichtImBriefing.svelte` | MODIFY | baut auf `ChipLeiste` |
| `organisms/wetter-tab/WarnungenRadarKarte.svelte` | MODIFY | `Einstellungszeile`; Schalter bleibt roh (KL) |
| `organisms/index.ts` | MODIFY | `WetterTabInhalt` exportieren |
| `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | MODIFY | Import `$lib/components/shared/WetterTab.svelte` |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | `SEITEN_SCOPE` += `lib/components/shared/WetterTab.svelte`; kein BESTAND/AUSNAHMEN |
| 6 Tests mit Konstante `WETTER_TAB` (trip-new f002, fixloop3_c3; compare-new f001_f002; shared/wetter-tab fixloop3_c2, fixloop4, f005) | MODIFY | Pfad → `WetterTabInhalt.svelte` |
| `organisms/__tests__/wetter_tab_ort.test.ts`, `wetter_tab_barrel.test.ts`, `shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts`, `s3a2794_teil3_keine_nativen_controls.test.ts` | MODIFY | Pfade/Listen nachziehen (AC-9) |
| `organisms/__tests__/wetter_tab_render_gleich.test.ts` + fixtures | DELETE | durch Teil 2 bewusst überholt |
| `tests/golden/f9_*`, `f10_*` (8 Dateien) | MODIFY | neu schreiben, Textgleichheit prüfen |
| `frontend/src/routes/_design-system/+page.svelte`, `showcase.test.ts` | MODIFY | Ampel-Swatches L/D, Input-Ampel, Segmented-Punkt, Skelett; Assert je neues Atom |
| neue Tests: `ampel_tokens_kontrast`, `atoms/__tests__/ampel_atome`, `molecules/__tests__/einstellungszeile_chips`, `organisms/__tests__/wetter_tab_bausteine`, `organisms/__tests__/wetter_tab_i18n` | CREATE | gemäß Spec-Testtabelle |
| `docs/design-system/COMPONENTS.md`, `TOKENS.md` | MODIFY | Doku |

### Scope Assessment
- Files: ~25 (+8 Goldens)
- Estimated LoC: ca. +1000/-300 (≈450 Tests, 250 Organismen, 150 Atome/Moleküle, 40 CSS, 60 Pfade)
- Risk Level: MEDIUM — sichtbare Änderung im Wetter-Reiter beider Kontexte, viele E2E-Selektoren müssen erhalten bleiben; Logik unverändert.

### Reihenfolge
1 Tokens + Kontrast-Test → 2 Atome (Input, Segmented, Skelett, Btn `tap`) + Barrel → 3 Moleküle → 4 `git mv` + Seite + Importeure + `SEITEN_SCOPE` + Pfad-Tests → 5 Organismen ohne rohe Controls, AmpelLeiste-Tokens → 6 `render_gleich` löschen, SSR-Goldens neu → 7 Showcase + Doku → 8 Wächter, `npm run check`, `/e2e-verify` (Light/Dark, Trip + Orts-Briefing, DE/EN).

### E2E-Selektoren, die erhalten bleiben müssen
`wetter-zeile-*`, `wetter-ampel-leiste-*`, `wetter-tab-laden` (Text „Lade Metriken …“), `wetter-tab-erneut-laden`, `WT.alarmAbStufe(id, farbe)` mit `aria-checked`/`role=radio`, `aria-expanded` am Vorlagen-Picker, `wetter-warnungen-schalter`, `wetter-radar-schalter`, `locator('select')`=0, `NATIV`-Liste, Touch-Ziele ≥44px.

### Open Questions
- keine Produktfrage offen (Spec freigegeben; Farbwerte folgen Mockup + WCAG-AA wie in Spec festgelegt).
