# Context: feature-2913-bausteine (#2913 Schritt 3)

## Request Summary
Das angenommene Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (Einstellungs-Hub Trip/Orte, Reiter Wetter, Zustellung, Etappen/Orte) in Atome/Moleküle/Organismen zerlegen; vorhandene Bausteine nutzen, fehlende einmal im Design-System bauen (Trip und Orte teilen sie, ADR-0097), nach ADR-0112 (nur Tokens, Wächter blockt beim Merge). Seiten-Scheiben (a)–(e) sind Schritt 4 (Folge-Workflows).

## Akuter Befund: Bausteine-Wächter auf main rot
`frontend/src/lib/__tests__/bausteine_waechter.test.ts` AC-7 („echter Quellbaum grün") scheitert auf `e89f12fff`: die 9 Dateien `frontend/src/lib/components/shared/wetter-tab/*.svelte` (aus PR #2920, #2794 Teil 3, parallel zu #2918 gemergt) stehen weder in `SEITEN_SCOPE` noch in `BESTAND` (Neue-Datei-Regel). Sie enthalten je ein `<style>` und zusammen 13 rohe `<button>`. Folge: CI-Job `frontend-test` rot für main und jeden PR. Diese Dateien sind genau die Kandidaten für die neuen Bausteine (Metrik-Zeile, Ampel-Leiste, Grenzen-Editor, Alarm-ab-Kopf, Vorlage-Karte, Nicht im Briefing, Warnungen/Radar) → Auflösung gehört in diesen Workflow, als erster Schritt.

## Mockup-Elemente → Baustein (Inventur)
| Mockup-Element (CSS) | Vorhandener Baustein | Lücke |
|---|---|---|
| Kopf `.crumbs/.eyebrow/h1+.pill/.meta` | PageHeader + Pill | heute `shared/hub-kopf/HubKopf.svelte` (kein Baustein) |
| Kebab ⋮ mit Inline-`.confirm` | SubscriptionKebab, ConfirmDialog | Inline-Bestätigung fehlt |
| „Test schicken ▾" (`.btn.sm.accent`+`.menu`, gesperrte Zeilen `.dis`, Segmented-Kopf Morgen/Abend, `.toast`) | SendConfirmDialog (teilweise) | **fehlt** |
| Reiterleiste `.tab` + `.badge` | Segmented `rolle="tabs"` | Unterstrich-Reiter-Stil fehlt |
| `.sectionh` | SectionH | – |
| `.card` / `.switch` / Feld / Uhrzeit / Datum / `.dot` | Card / Switch / Field / UhrzeitFeld / DatumFeld / Dot | – |
| Segmented mit Farbpunkt `.seg .d` („Alarm ab") | Segmented | Farbpunkt-Variante fehlt |
| `.input.sm` mit Ampel-Unterkante `.lr/.lo/.ly` | Input | Ampel-Variante fehlt |
| `.warnbox.bad/.info` | Infobox / AlertRow | Varianten prüfen |
| Vorlage-Karte (`.vorlage .picker .vmenu .vg`, Dialog Speichern) | – (PresetRail passt nicht) | **fehlt** (heute `shared/wetter-tab/VorlageKarte.svelte`) |
| „Alarm ab für alle" (`.lrow` card-alt + Segmented Nie/Gelb/Orange/Rot) | – | **fehlt** (heute `AlarmAbKopf.svelte`) |
| Metrik-Gruppe `.mgroup .gh` + Metrik-Zeile `.mr` (rm, nm, `.bandwrap .ticks .band .why`, `.act`) mit Varianten beidseitig/oben/unten/ordinal Gewitter/nur Anzeige/Vorbote/UV nie | – | **fehlt** (heute `MetrikZeile`, `AmpelLeiste`+`ampelLeiste.ts`) |
| Grenzen-Editor `.edit .grp` | – | **fehlt** (heute `GrenzenEditor.svelte`) |
| „Nicht im Briefing" `.more .chip` | MetricOffShelf (ähnlich) | Chip-Leiste fehlt (heute `NichtImBriefing.svelte`) |
| Generische Einstellungszeile `.lrow` | ChannelRow/DetailRow nahe | **fehlt** |
| Aufklapper `details.adv` | – | **fehlt** |
| Inhalt je Kanal `.olist .oi` (Griff, Name, Roh/Einfach, Beispiel, Schalter; `.off/.fixed/.locked`), `.budget`, `.legend .kz` | – (Logik `weather-metrics-tab/kuerzelLegende.ts`, `channelMetricLayouts.ts`) | **fehlt** |
| Lade-Skelett `.skel` | – | **fehlt** |
| Kanal-Tabelle `table.kt` (Status-Punkt, Briefing-/Alarm-Schalter, „gesperrt", Dringlichkeit gering/mittel/hoch, Premium-SMS) | ChannelRow/ChannelChip als Teile | **fehlt** |
| Etappen-/Orte-Liste | StagePill/CompareLocationRow nicht 1:1 | über generische Zeile |
| Nicht übernehmen: `.frame`, `.tag`, `.fb` | – | Mockup-Hilfen |

## Related Files
| File | Relevance |
|---|---|
| `docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md` | Regeln; Z.32 nennt nötige Bausteine (`--g-ampel-*` mit Dark-Block, Metrik-Zeile, Vorlage-Karte, Kanal-Tabelle) |
| `frontend/src/lib/__tests__/bausteine_waechter.test.ts`, `bausteine_waechter_regeln.ts`, `bausteine_waechter_wirkort.test.ts` | Wächter: SEITEN_SCOPE (Z.504, leer), FREIGEGEBENE_KOMPOSITIONEN (Z.507), BESTAND (Z.510ff., Obergrenze 204, Z.718), AUSNAHMEN-Ratsche (Z.721–762) |
| `frontend/src/app.css` | Tokens (`@theme` Z.66, `:root` Z.97, Dark Z.267); keine `--g-ampel-*`, keine Dringlichkeits-Tokens |
| `docs/design-system/TOKENS.md`, `COMPONENTS.md`, `ANTI-PATTERNS.md` | Design-System-Doku |
| `frontend/src/lib/components/{atoms,molecules,organisms}/` + `index.ts` | Ziel-Ordner, Barrel |
| `frontend/src/lib/components/shared/wetter-tab/*` | heutiger Wetter-Reiter (#2794), wird in Bausteine überführt |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | Übergangsreiter (alte Bausteine: WeatherV2Grundauswahl, WeatherV2PresetBar, VTBriefingChannels, AlarmeTab …) – Schritt 4 (d) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` Z.214/216, `compare/CompareTabs.svelte` Z.799ff. | Einbindung Trip/Vergleich |
| `frontend/src/routes/_design-system/+page.svelte` + `showcase.test.ts` | Showcase (Organisms bisher ausgenommen) |
| `claude-code-handoff/current/jsx/` | Handoff-Referenz atoms/molecules/organisms.jsx, tokens.css |
| `docs/context/einstellungen_neu/elementliste.json`, `scripts/elementliste_abgleich.ts`, `frontend/e2e/elementliste_abgleich_logik.ts` | Elementliste (4148, Abgleich gegen Staging) |

## Existing Patterns
- Bausteine sind dünne Svelte-5-Komponenten; Atome wrappen teils `ui/*` (Seiten dürfen `ui/` nicht direkt importieren).
- Tests: `node --test` mit Loader (`npm test -- <datei>`), Ablage `<schicht>/__tests__/*.test.ts`; Verhalten per Server-Render `svelte/server` (z. B. `molecules/__tests__/send_confirm_dialog.test.ts`).
- Ampel-Farben heute behelfsweise success/`--g-wx-sun`/accent/danger (`AmpelLeiste.svelte` Z.19–22); Mockup nutzt `#15803d/#d69500/#d4530a/#a8104a`.

## Dependencies
- Upstream: Tokens `app.css`, `ui/*` Primitive, `ampelLeiste.ts`, `kuerzelLegende.ts`, i18n-Katalog (ADR-0104).
- Downstream: WetterTab/ZustellungTab (Trip + Vergleich, Anlege-Ketten `TripNewEditor`, `CompareNewEditor`), Elementliste-Abgleich, Wächter.

## Existing Specs
- `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` (Z.30: Bausteine inkl. `--g-ampel-*` = dieser Folge-Workflow)
- `feat_2794_s3a_reiter_wetter.md`, `feat_2794_s3a_teil2_leiste.md`, `feat_2794_s3a_teil3_wetter.md`, `feat_2792_s1_profil_ampel.md`, `ampel_schwellen_katalog.md`
- `rework_2881_design_system_bereinigung.md`, `design_system_drift_fixes.md`

## Risks & Considerations
- main ist rot (Wächter) → blockt alle PRs; zuerst lösen (wetter-tab-Teile als Bausteine anlegen bzw. WetterTab in SEITEN_SCOPE).
- Umfang: ~15 fehlende Bausteine; in Scheiben schneiden (Issue: senkrechte Scheiben, je auf Staging sichtbar). Dieser Workflow: Tokens + Bausteine für Scheibe (a)/(b) und Auflösung des roten Wächters; weitere Bausteine mit den jeweiligen Scheiben.
- Neue Farben (Ampel, Dringlichkeit) brauchen Dark-Mode-Werte und WCAG-AA-Kontrast (Design-Leitprinzip).
- Keine Verhaltensänderung am Wetter-Reiter (Ampel-/Alarm-Logik geprüft in #2794); nur Aufbau aus Bausteinen.
- Trip/Orte teilen jeden Baustein (ADR-0097, Gate #1170).

## Analysis

### Type
Feature (Schritt 3 von #2913), mit akutem Vorab-Fix: Bausteine-Wächter auf main rot (blockt `frontend-test` für alle PRs).

### Wächter-Fakten (gemessen, `bausteine_waechter_regeln.ts`)
- Neue-Datei-Regel: Dateisystem-Lauf; jede `.svelte` unter `routes/` oder `lib/components/` außerhalb `atoms|molecules|organisms` muss in SEITEN_SCOPE (Regel a) oder BESTAND stehen. BESTAND voll (204 = Obergrenze), Aufstocken verboten (Ratsche). `audit:exempt` hilft nicht gegen die Neue-Datei-Regel.
- Regel a (Seiten): kein `<style>`, kein `style=`/`style:`, keine Tailwind-Utilities, keine rohen button/input/select/textarea/table, nur Komponenten-Importe aus atoms|molecules|organisms (+FREIGEGEBENE_KOMPOSITIONEN).
- Regel b (Bausteine): nur `--g-*`-Tokens; Hex/rgb/Farbnamen/fremde var()/px/rem/em verboten (außer 0 und 1px-Rahmen). `@media`-Präludien neutralisiert (899px-Breakpoint erlaubt), %, unitlose Zahlen, fr erlaubt. Rohe Controls in Bausteinen erlaubt. Neue Baustein-Datei startet in AUSNAHMEN bei 0.
- Showcase erzwingt keine neuen Bausteine; Organisms ausgeschlossen.

### Bestand wetter-tab (17 Dateien)
9 `.svelte` (WetterTab 371, VorlageKarte 256, MetrikZeile 176, GrenzenEditor 159, WarnungenRadarKarte 119, AmpelLeiste 83, AlarmAbKopf 69, NichtImBriefing 69, AnpassenKarte 64 Z.): Farben schon nur `var(--g-*)`, aber ca. 190 px-Werte (44px Touch-Ziel, 420/180/120/72/56px Breiten, Abstände), 9 rohe `<button>`, 1 rohes `<input>`, alle mit `$t`-Katalog. 8 `.ts`-Logikmodule (vom Wächter nicht erfasst) bleiben an Ort und Stelle. Importeure: TripTabs, CompareTabs, TripNewEditor, CompareNewEditor; `SavePresetDialog.svelte` und `weatherMetricsSavePayload.ts` importieren `.ts` aus wetter-tab.
Offene PRs #2874/#2846 berühren keine dieser Dateien (geprüft).

### Tokens heute
Spacing `--g-s-1..20` (4px-Raster: 4,8,12,16,20,24,32,40,48,64,80), Text `--g-text-*`, Radien. Fehlen: Touch-Ziel (44px), Ampel (`--g-ampel-*`, ADR-0112 Z.32), Dringlichkeit, Breiten (420/180/120/72/56). AmpelLeiste mappt heute success/`--g-wx-sun`/accent/danger; `--g-wx-*` ohne Dark-Wert.

### Variantenvergleich (Weg zu grünem main)
| | V1: 8 Teile → Bausteine, WetterTab → SEITEN_SCOPE | V2: alle 9 → `organisms/wetter-tab/` | V3: BESTAND/exempt |
|---|---|---|---|
| verschobene .svelte | 9 | 9 | 0 |
| px→Token-Bereinigung | 8 Dateien | 9 Dateien | – |
| zusätzlich | WetterTab ohne `<style>`, Layout-/Skelett-/Fehler-Bausteine nötig | nur Tokens | – |
| gebrochene Pfad-Tests | ca. 5–8 | ca. 5–8 | 0 |
| sichtbare Änderung | ja (Umbau Wurzel) | nein | nein |
| zulässig | ja | ja (Regel b) | **nein** (Ratsche/Abkürzung) |

### Technical Approach (Entscheidung Tech Lead)
Zwei Teile in diesem Workflow, je eigener PR:

**Teil 1 — main grün, ohne sichtbare Änderung (zuerst, kleinster PR):**
1. Neue Tokens in `app.css` (reine Maße, Light = Dark): `--g-tap-min: 44px` und Breiten-Tokens (`--g-size-*`) nur für Werte außerhalb des 4px-Spacing-Rasters; alles andere auf `--g-s-*`/`--g-text-*`/`--g-r-*` abbilden. Pixelgleich, keine Farbänderung. Doku TOKENS.md §14.
2. Die 9 `.svelte` per Verschieben (Git-Historie erhalten) nach `frontend/src/lib/components/organisms/wetter-tab/`; `.ts`-Module bleiben in `shared/wetter-tab/` (Importe in den verschobenen Dateien anpassen). Importeure (4) und Pfad-Tests (per grep `wetter-tab/.*\.svelte` vollständig ermitteln, nach Rebase vor Merge wiederholen) nachziehen.
3. px → Tokens in allen 9 Dateien bis Regel b mit 0 Verstößen (keine AUSNAHMEN-Einträge, kein `audit:exempt`). Rohe Controls bleiben in Teil 1 (in Bausteinen erlaubt), damit sich nichts sichtbar ändert.
4. Barrel `organisms/index.ts`; COMPONENTS.md §8.
Bewusstes Zugeständnis: WetterTab (Zustand/API) liegt vorübergehend als Organismus; Teil 2 macht ihn zur dünnen Seite (SEITEN_SCOPE).

**Teil 2 — Bausteine für Scheibe (a)/(b):**
- Ampel-Tokens `--g-ampel-gruen/-gelb/-orange/-rot` mit Dark-Block, nahe Mockup (#15803d/#d69500/#d4530a/#a8104a), aber WCAG-AA für grafische Elemente (≥3:1 gegen Karte, Light und Dark; #d69500 auf Weiß ≈2,6:1 → abdunkeln). Design-Leitprinzip (hoher Kontrast, PO-bestätigt) entscheidet; Farbe nie alleiniger Träger. AmpelLeiste nutzt sie; Showcase zeigt sie.
- Atom-Erweiterungen: Input mit Ampel-Unterkante, Segmented mit Farbpunkt; neues Atom Skelett (`.skel`).
- Molecules: Einstellungszeile (`.lrow`), NichtImBriefing als Chip-Leiste.
- Organisms nach Mockup ausgebaut, rohe Controls → Btn/Input/Segmented: VorlageKarte, AlarmAbKopf, MetrikZeile+AmpelLeiste, GrenzenEditor.
- WetterTab wird dünne Seite in SEITEN_SCOPE (kein `<style>`, nur Baustein-Importe).
- Trip und Orte nutzen dieselben Bausteine (ADR-0097).

**Spätere Scheiben (nicht dieser Workflow):** Kanal-Tabelle + Dringlichkeits-Tokens (d), „Test schicken ▾" (e), Aufklapper `details.adv`, Inhalt je Kanal `.olist`/`.budget`/Legende (d), Inline-Bestätigung im Kebab, Unterstrich-Reiter, HubKopf, Etappen/Orte-Liste.

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| frontend/src/app.css | MODIFY | `--g-tap-min`, `--g-size-*` (Teil 1); `--g-ampel-*` Light/Dark (Teil 2) |
| frontend/src/lib/components/shared/wetter-tab/*.svelte (9) | MOVE → organisms/wetter-tab/ | px→Tokens; Teil 2 Ausbau |
| frontend/src/lib/components/organisms/index.ts | MODIFY | Barrel |
| TripTabs, CompareTabs, TripNewEditor, CompareNewEditor (.svelte) | MODIFY | Importpfad |
| shared/__tests__/s3a2794_*, trip-new/__tests__/f002…, fixloop3…, compare-new/__tests__/f001_f002…, compare/__tests__/fa3… u. a. | MODIFY | Pfad-Strings |
| atoms/Input.svelte, atoms/Segmented.svelte, atoms/Skelett.svelte | MODIFY/CREATE | Teil 2 |
| molecules/Einstellungszeile.svelte | CREATE | Teil 2 |
| frontend/src/lib/__tests__/bausteine_waechter_regeln.ts | MODIFY | Teil 2: WetterTab in SEITEN_SCOPE |
| routes/_design-system/+page.svelte | MODIFY | Ampel-Tokens/neue Atome zeigen |
| docs/design-system/TOKENS.md, COMPONENTS.md | MODIFY | Doku |

### Scope Assessment
- Teil 1: ~16–20 Dateien, ca. +250/−250 geändert (plus ~1.370 Z. verschoben), Risiko LOW–MEDIUM.
- Teil 2: ~12–15 Dateien, ca. +600/−300, Risiko MEDIUM (sichtbare Änderung Wetter-Reiter, Dark-Kontrast; keine Logikänderung).
- Gesamt: MEDIUM.

### Dependencies
Teil 2 setzt Teil 1 voraus. Logik-`.ts` (ampelModell, ampelLeiste, wetterZustand …) unverändert. i18n `messages/{de,en}/wetter.json` bleibt Textquelle. Elementliste-Abgleich misst erst ab Scheibe (a) sinnvoll.

### Risiken / Befunde gegen den Plan
- Nach Rebase neu hinzugekommene Pfad-Tests → grep vor Merge wiederholen.
- Pixelgleichheit Teil 1: Werte außerhalb des Rasters nur über neue Tokens, nicht runden.
- Ampel-Farbänderung (Teil 2) ist sichtbar, folgt aber dem angenommenen Mockup und WCAG-AA.
- WetterTab vorübergehend als Organismus widerspricht dem Geist „dünne Seite“ — begrenzt auf Teil 1; Auflösung ist AC von Teil 2.

### Open Questions
- Keine Produktfrage offen (Farbwerte: Design-Leitprinzip; Schnitt: Tech-Lead-Entscheidung).

## RED-Stand (Phase 5, 2026-11-11) — nur Teil 1

RED-Tests decken **nur Teil 1** ab (eigener PR zuerst; Teil-2-Tests würden den Teil-1-PR rot machen und werden vor der Teil-2-Implementierung rot geschrieben).

| Test | ACs |
|---|---|
| `frontend/src/lib/components/organisms/__tests__/wetter_tab_ort.test.ts` | AC-2 (Teil 1), AC-3, AC-4, AC-8, AC-19 (Importpfad) |
| `frontend/src/lib/__tests__/tokens_masse.test.ts` | AC-5 |
| `frontend/src/lib/components/organisms/__tests__/wetter_tab_render_gleich.test.ts` + `fixtures/wetter_tab_vor_2913/*.svelte.txt` | AC-6, AC-7 |
| `frontend/src/lib/components/organisms/__tests__/wetter_tab_barrel.test.ts` | AC-10 |
| bestehend `bausteine_waechter.test.ts` AC-7 | AC-1 |

**Messweise AC-6/AC-7 (Abweichung vom Testplan, technisch begründet):** Statt Playwright-Maßmessung vergleicht `wetter_tab_render_gleich` das vom Svelte-Compiler erzeugte CSS (nach Auflösung aller `var(--g-*)` mit den hellen Werten aus `app.css`, rem×16) und den Markup-Baum (Svelte-Parser) mit dem Referenzstand von `main` e89f12fff. Gleiches CSS + gleicher Baum ist die Ursache gleicher berechneter Maße; deterministisch, ohne Server. Folge für die Umsetzung: Tokens müssen den Originalwert **exakt** treffen (direkte Zuordnung, kein `calc()`-Umweg, der sich anders ausschreibt); Werte ohne passendes Token → `--g-size-*` (px oder em), nie runden. Der Test samt Fixture-Ordner wird mit Teil 2 entfernt.

**Hinweise für /50-implement:** Bestehende Kerntests mit Pfaden (`shared/__tests__/s3a2794_teil3_*`, `shared/wetter-tab/__tests__/*`, Hub-/Editor-Tests) nachziehen, Zusicherungen nicht abschwächen (AC-9). `TripNewEditor` liegt unter `trip-new/` (nicht `trip-detail/`).
