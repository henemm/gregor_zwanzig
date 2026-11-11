---
entity_id: feat_2913_s3_bausteine
type: module
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
tags: [design-system, bausteine, waechter, ampel, tokens, wetter-reiter, adr-0112, epic-2791]
workflow: feature-2913-bausteine
issue: 2913
---

# Einstellungen neu, Schritt 3: Bausteine aus dem Mockup (#2913)

## Approval

- [ ] Approved

## Purpose

Der Wetter-Reiter (aus #2794 Teil 3) liegt heute als lose Sammlung von neun Svelte-Dateien unter `shared/wetter-tab/` und verletzt den Bausteine-Wächter (ADR-0112): Der Test „echter Quellbaum grün“ (AC-7 in `bausteine_waechter.test.ts`) ist auf `main` rot, der CI-Job `frontend-test` blockiert damit jeden PR. Diese Spec löst das in zwei getrennt gelieferten Teilen: **Teil 1** macht `main` wieder grün, ohne dass sich auf dem Bildschirm etwas ändert; **Teil 2** baut die Bausteine nach dem angenommenen Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` aus (Ampel-Farbtokens, Atom-Erweiterungen, Skelett, Einstellungszeile, Chip-Leiste, Organismen aus Atomen) und macht `WetterTab` zur dünnen Seite. Trip und Orts-Briefing nutzen dieselben Bausteine (ADR-0097).

Grundlage: Analyse `docs/context/feature-2913-bausteine.md` (maßgeblich), ADR-0112, ADR-0097, ADR-0104 (zweisprachig), Wächter-Regeln `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`, Vorgänger-Spec `einstellungen_neu_neustart_adr_waechter_elementliste.md`.

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/app.css` (Tokens), `frontend/src/lib/components/shared/wetter-tab/*.svelte` (heutiger Ort der neun Dateien), `frontend/src/lib/components/{atoms,molecules,organisms}/`, `frontend/src/routes/_design-system/+page.svelte` (Showcase), Wächter `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`.
- **Identifier:** Komponenten `WetterTab`, `VorlageKarte`, `MetrikZeile`, `GrenzenEditor`, `WarnungenRadarKarte`, `AmpelLeiste`, `AlarmAbKopf`, `NichtImBriefing`, `AnpassenKarte` (verschoben), neu `Skelett`, `Einstellungszeile`; Wächter-Konstanten `SEITEN_SCOPE`, `BESTAND`, `AUSNAHMEN`; Tokens `--g-tap-min`, `--g-size-*`, `--g-ampel-*`.
- **Doku:** `docs/design-system/TOKENS.md`, `docs/design-system/COMPONENTS.md`.
- **Nicht berührt:** Go-API, Python-Core, Logik-Module `.ts` (`ampelModell.ts`, `ampelLeiste.ts`, `ampelSchreiben.ts`, `amtlicheWarnungen.ts`, `klon.ts`, `wetterTabLaden.ts`, `wetterTabSpeicherung.ts`, `wetterZustand.ts`), i18n-Kataloge `frontend/src/lib/i18n/messages/{de,en}/wetter.json`.

> **Schicht-Hinweis:** Reine Frontend-Arbeit (SvelteKit, `frontend/src/...`). Es gibt keine Backend-Änderung.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, ADR-0097):** Alle Bausteine dieser Spec liegen im Design-System (`atoms/`, `molecules/`, `organisms/`) und werden von Trip und Orts-Briefing gemeinsam genutzt (`context="route"|"vergleich"` wie bisher in `WetterTab`). Es entsteht keine Compare-eigene Komponente mit Trip-Pendant.
>
> **Mandantentrennung:** Es werden keine Nutzerdaten, Endpunkte oder Speicherwege geändert; der Speicherpfad (`wetterTabSpeicherung.ts`) bleibt unverändert. Ein Zwei-Nutzer-Test entfällt daher, die bestehenden Zwei-Nutzer-Tests des Wetter-Reiters (#2794) müssen grün bleiben.
>
> **Kanäle:** Keine Änderung an Briefing- oder Alarm-Inhalt; E-Mail, Telegram, SMS und Premium-SMS sind nicht berührt. Die Ampel-Logik bleibt unverändert.

## Estimated Scope

- **Teil 1:** ca. 16 bis 20 Dateien, ca. +250/−250 Zeilen geändert, zusätzlich ca. 1.370 verschobene Zeilen (Git-Verschiebung). Risiko LOW bis MEDIUM. Effort: medium.
- **Teil 2:** ca. 25 Dateien plus 8 Golden-Dateien, ca. +1.000/−300 Zeilen (davon ca. 450 Tests). Risiko MEDIUM (sichtbare Änderung im Wetter-Reiter, Dark-Kontrast, keine Logikänderung). Effort: medium bis high.
- **Gesamt:** LoC ca. +1.250/−550 (ohne verschobene Zeilen, davon ca. 450 Testzeilen in Teil 2), Files ca. 45 bis 55 einschließlich Goldens, Effort medium bis high, Risiko MEDIUM. Zwei PRs, Teil 2 setzt Teil 1 voraus.

## Scope

### In Scope

**Teil 1 (main wieder grün, pixelgleich, zuerst und als eigener PR):**
1. Neue reine Maß-Tokens in `frontend/src/app.css`: `--g-tap-min` (44px) und `--g-size-*` ausschließlich für Werte, die nicht im 4px-Raster von `--g-s-1..20` liegen (Light = Dark). Alle übrigen px-Werte werden auf vorhandene `--g-s-*`, `--g-text-*` und `--g-r-*` abgebildet, nie gerundet.
2. Die neun `.svelte`-Dateien `WetterTab`, `VorlageKarte`, `MetrikZeile`, `GrenzenEditor`, `WarnungenRadarKarte`, `AmpelLeiste`, `AlarmAbKopf`, `NichtImBriefing`, `AnpassenKarte` werden per `git mv` von `frontend/src/lib/components/shared/wetter-tab/` nach `frontend/src/lib/components/organisms/wetter-tab/` verschoben. Die `.ts`-Module bleiben in `shared/wetter-tab/`; Importe in den verschobenen Dateien werden angepasst.
3. Importeure (`trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-detail/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte`) und alle Tests mit Pfad-Strings auf `wetter-tab/*.svelte` werden nachgezogen (vollständig per `grep -rn "wetter-tab/.*\.svelte"` ermittelt, nach Rebase vor dem Merge wiederholt).
4. px-Werte werden in allen neun Dateien durch Tokens ersetzt, bis Regel b des Wächters 0 Verstöße meldet, ohne neuen Eintrag in `AUSNAHMEN`, `BESTAND` oder `audit:exempt`. Rohe Controls (`<button>`, `<input>`) bleiben in Teil 1 unverändert (in Bausteinen erlaubt), damit sich nichts sichtbar ändert.
5. Barrel `frontend/src/lib/components/organisms/index.ts` und Doku `TOKENS.md` (neuer Abschnitt Maß-Tokens), `COMPONENTS.md` (Organismen-Abschnitt).

**Teil 2 (Bausteine für Scheibe (a)/(b), eigener PR nach Teil 1):**
1. Ampel-Tokens (dazu Maß-Token `--g-size-3px` für die Ampel-Unterkante, K-4) `--g-ampel-gruen`, `--g-ampel-gelb`, `--g-ampel-orange`, `--g-ampel-rot` in `app.css` mit eigenem Dark-Block, nahe an den Mockup-Werten (`#15803d`, `#d69500`, `#d4530a`, `#a8104a`), aber so gewählt, dass jeder Wert als grafisches Element mindestens 3:1 Kontrast gegen den Karten-Hintergrund erreicht, in Light und in Dark (Design-Leitprinzip hoher Kontrast; Gelb wird dafür abgedunkelt). Farbe ist nie alleiniger Informationsträger.
2. Atom-Erweiterungen: `atoms/Input.svelte` mit Ampel-Unterkante (Variante je Ampelfarbe), `atoms/Segmented.svelte` mit Farbpunkt je Segment; neues Atom `atoms/Skelett.svelte` (Lade-Platzhalter, `.skel` im Mockup).
3. Moleküle: neu `molecules/Einstellungszeile.svelte` (generische Zeile `.lrow`) und `molecules/ChipLeiste.svelte` (`.more .chip`); `NichtImBriefing` wird daraus gebaut (siehe K-2).
4. Organismen nach Mockup ausgebaut, rohe Controls werden durch `Btn`/`Input`/`Segmented` ersetzt: `VorlageKarte`, `AlarmAbKopf`, `MetrikZeile` mit `AmpelLeiste`, `GrenzenEditor`.
5. `WetterTab` wird dünne Seite `shared/WetterTab.svelte` mit Eintrag in `SEITEN_SCOPE` in `bausteine_waechter_regeln.ts`, ohne `<style>`, nur Importe aus `atoms|molecules|organisms`; Zustand und API-Anbindung liegen im Organismus `organisms/wetter-tab/WetterTabInhalt.svelte` (siehe K-1).
6. Showcase `frontend/src/routes/_design-system/+page.svelte` zeigt die Ampel-Tokens und die neuen Atome; `TOKENS.md` und `COMPONENTS.md` nachgezogen.
7. Trip und Orte nutzen für alles dieselben Bausteine.

### Out of Scope

- Bausteine der Scheiben (c) bis (e) (Folge-Workflows von #2913): Kanal-Tabelle `table.kt`, Dringlichkeits-Tokens, „Test schicken ▾“, Aufklapper `details.adv`, `.olist`/`.budget`/Legende (Inhalt je Kanal), Inline-Bestätigung im Kebab, Unterstrich-Reiter, `HubKopf`, Etappen-/Orte-Liste.
- Keine Logikänderung an Ampel und Alarm (alle `.ts`-Module bleiben unverändert).
- Keine Änderung an den Texten in `wetter.json` DE/EN (bleibt Textquelle des Wetter-Reiters). Einzige Ausnahme: fehlt ein allgemeiner Ladetext für das Skelett-Atom, kommt ein neuer Schlüssel DE und EN in den Allgemein-Katalog (K-4).
- Keine Aufstockung von `BESTAND`, keine neuen `AUSNAHMEN`, kein `audit:exempt` als Abkürzung.
- Nicht aus dem Mockup übernommen: `.frame`, `.tag`, `.fb` (Mockup-Hilfen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md` | ADR | Regelwerk Bausteine/Tokens/Wächter |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`, `bausteine_waechter.test.ts`, `bausteine_waechter_wirkort.test.ts` | Test/Regeln | Regel a (Seiten), Regel b (Bausteine), Neue-Datei-Regel, BESTAND-Ratsche (Obergrenze 204), AUSNAHMEN-Ratsche |
| `frontend/src/app.css` | Tokens | `@theme`, `:root`, Dark-Block |
| `shared/wetter-tab/{ampelModell,ampelLeiste,ampelSchreiben,amtlicheWarnungen,klon,wetterTabLaden,wetterTabSpeicherung,wetterZustand}.ts` | Code | Logik, bleibt unverändert |
| `ui/*` Primitive | Code | Atome wrappen sie, Seiten importieren sie nie direkt |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | Spec | Verhalten des Wetter-Reiters, das erhalten bleiben muss |
| Teil 1 | Vorarbeit | Voraussetzung für Teil 2 |
| `docs/context/feature-2913-teil2.md` | Analyse | Grundlage des Umsetzungsplans Teil 2 |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0112, ADR-0097, ADR-0104 (umgesetzt, kein neues ADR)
- **ADR-0112** (Oberflächen nur aus Design-System-Bausteinen): wird umgesetzt, nicht geändert. Die Wetter-Reiter-Teile werden Organismen (Regel b, nur Tokens), `WetterTab` wird Seite in `SEITEN_SCOPE` (Regel a). Keine Ausnahme, keine Aufstockung von `BESTAND`.
- **ADR-0097** (Trip/Orte teilen Code): Jeder Baustein dieser Spec wird von Trip und Orts-Briefing gemeinsam genutzt.
- **ADR-0104** (zweisprachig): Texte bleiben im Katalog, unverändert.
- Neues ADR: keines. Rationale: Die Spec führt bestehende Entscheidungen aus; die vorübergehende Lage von `WetterTab` als Organismus (Teil 1) ist durch Regel b gedeckt und endet mit Teil 2 (AC-17).

## Affected Files

(Pfade ohne Präfix liegen unter `frontend/src/lib/components/`.)

| File | Teil | Change Type | Description |
|------|------|-------------|-------------|
| `frontend/src/app.css` | 1, 2 | MODIFY | Teil 1: `--g-tap-min`, `--g-size-*`; Teil 2: `--g-ampel-*` Light und Dark, Maß-Token `--g-size-3px`, Regeln für Input-Ampel, Segmented-Punkt, Skelett, `Btn` `tap` |
| `shared/wetter-tab/{WetterTab,VorlageKarte,MetrikZeile,GrenzenEditor,WarnungenRadarKarte,AmpelLeiste,AlarmAbKopf,NichtImBriefing,AnpassenKarte}.svelte` | 1 | MOVE nach `organisms/wetter-tab/` | `git mv`, Importe angepasst, px durch Tokens |
| `shared/wetter-tab/*.ts` (8 Module) | 1 | UNCHANGED | bleiben am Ort |
| `organisms/index.ts` | 1, 2 | MODIFY | Barrel; Teil 2: `WetterTabInhalt` statt `WetterTab` |
| `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-detail/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | 1, 2 | MODIFY | Importpfad; Teil 2: `$lib/components/shared/WetterTab.svelte` (K-1) |
| Pfad-Tests, u. a. `shared/__tests__/s3a2794_*.test.ts`, `trip-new/__tests__/f002*`, `fixloop3*`, `compare-new/__tests__/f001_f002*`, `compare/__tests__/fa3*` (vollständige Liste per grep) | 1 | MODIFY | Pfad-Strings nachziehen, nicht aufweichen |
| `atoms/Input.svelte`, `atoms/Segmented.svelte` | 2 | MODIFY | Ampel-Unterkante, Farbpunkt |
| `atoms/Skelett.svelte`, `atoms/index.ts` | 2 | CREATE/MODIFY | Skelett-Atom, Barrel |
| `molecules/Einstellungszeile.svelte`, `molecules/ChipLeiste.svelte`, `molecules/index.ts` | 2 | CREATE/MODIFY | generische Zeile, Chip-Leiste, Barrel |
| `organisms/wetter-tab/{VorlageKarte,AlarmAbKopf,MetrikZeile,AmpelLeiste,GrenzenEditor,NichtImBriefing,WarnungenRadarKarte}.svelte` | 2 | MODIFY | Ausbau nach Mockup, Controls durch Atome (`WarnungenRadarKarte` nur `Einstellungszeile`, Schalter bleibt) |
| `ui/input/input.svelte`, `ui/segmented/Segmented.svelte`, `ui/btn/*` | 2 | MODIFY | Primitive: `data-ampel`, Farbpunkt und Testid-Durchreichung, Größe `tap` (K-4, K-5) |
| `organisms/__tests__/wetter_tab_render_gleich.test.ts` samt Referenzkopien `organisms/__tests__/fixtures/wetter_tab_vor_2913/*.svelte.txt` | 2 | DELETE | durch Teil 2 bewusst überholt (K-8) |
| `tests/golden/f9_trip_flaechen/anlegen_*.{de,en}.html`, `tests/golden/f10_vergleich_flaechen/anlegen_weiter.{de,en}.html` | 2 | MODIFY | neu geschrieben, nur Markup/Hash (K-8) |
| `frontend/src/lib/i18n/messages/{de,en}/` Allgemein-Katalog | 2 | MODIFY (nur falls nötig) | Standard-Ladetext Skelett (K-4) |
| `organisms/wetter-tab/WetterTab.svelte` → `organisms/wetter-tab/WetterTabInhalt.svelte` | 2 | MOVE | Organismus mit Zustand, Laden, Speichern (K-1) |
| `shared/WetterTab.svelte` | 2 | CREATE | dünne Seite ohne `<style>`, in `SEITEN_SCOPE` (K-1) |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | 2 | MODIFY | `WetterTab` in `SEITEN_SCOPE` (keine Aufstockung von `BESTAND`/`AUSNAHMEN`) |
| `frontend/src/routes/_design-system/+page.svelte`, `showcase.test.ts` | 2 | MODIFY | Ampel-Tokens, neue Atome |
| `atoms/__tests__/`, `molecules/__tests__/`, `organisms/__tests__/`, `frontend/src/lib/__tests__/` (neue Tests, siehe Testplan) | 1, 2 | CREATE | `node --test` |
| `docs/design-system/TOKENS.md`, `docs/design-system/COMPONENTS.md` | 1, 2 | MODIFY | Doku |
| Teil 1, bereits geliefert: `DatumFeld`/`UhrzeitFeld`, `tests/golden/f9_trip_flaechen/anlegen_*.de.html`, `tests/golden/f10_vergleich_flaechen/anlegen_weiter.de.html`, `docs/context/einstellungen_neu/elementliste.json` | 1 | MODIFY | Nebenwirkungen laut Known Limitations |

## Implementation Details

**Teil 1, Reihenfolge:**
1. Pfad-Inventur: `grep -rn "wetter-tab/.*\.svelte" frontend/` (Quellen, Tests, Doku) als Liste sichern.
2. Tokens in `app.css` ergänzen. Für jeden px-Wert in den neun Dateien entscheiden: liegt er im 4px-Raster, wird er `--g-s-*`; Schrift `--g-text-*`; Radius `--g-r-*`; Touch-Ziel 44px `--g-tap-min`; Breiten wie 420/180/120/72/56px nur dort, wo sie nicht im Raster liegen, als `--g-size-*`. Es wird nie gerundet, weil die Darstellung pixelgleich bleiben muss.
3. `git mv` der neun Dateien, Importe in den Dateien und bei den vier Importeuren anpassen, Pfad-Tests nachziehen.
4. Wächter-Lauf: Regel b ohne Verstoß, Neue-Datei-Regel erfüllt (Dateien liegen unter `organisms/`), keine Änderung an `BESTAND`/`AUSNAHMEN`.
5. Barrel und Doku.

**Teil 2, Reihenfolge (Grobfassung; maßgeblich ist die Reihenfolge im Abschnitt „Umsetzungsplan Teil 2“):** Ampel-Tokens samt Kontrast-Test, Atome (Input, Segmented, Skelett), Molekül Einstellungszeile und Chip-Leiste, Organismen umbauen, `WetterTab` zur Seite, Showcase und Doku. Ampelfarben in `AmpelLeiste` kommen aus `--g-ampel-*` statt der heutigen Behelfs-Zuordnung (success, `--g-wx-sun`, accent, danger). Bedeutung und Reihenfolge der Ampelstufen bleiben (Logik in `ampelLeiste.ts` unverändert).

Hinweis: Wächter-Messwerte (Regel b: nur `--g-*`-Tokens, keine px/rem/em außer 0 und 1px-Rahmen; `@media`-Präludien neutralisiert; %, unitlose Zahlen und `fr` erlaubt) sind in der Analyse festgehalten und gelten unverändert.

## Umsetzungsplan Teil 2 / Klarstellungen (Workflow `feature-2913-teil2`)

Grundlage: Analyse `docs/context/feature-2913-teil2.md`. Die ACs AC-11 bis AC-23 bleiben inhaltlich unverändert; dieser Abschnitt legt fest, wie sie gegen den Stand nach Teil 1 (Wetter-Reiter unter `organisms/wetter-tab/`) erfüllt werden.

**K-1 Seiten-Ort (AC-17, AC-19):** Der Wächter verbietet Baustein-Dateien in `SEITEN_SCOPE`. Deshalb wird die heutige `organisms/wetter-tab/WetterTab.svelte` per `git mv` zu `organisms/wetter-tab/WetterTabInhalt.svelte` (Organismus mit Zustand, Laden, Speichern und `<style>` nach Regel b). Neu entsteht die Seite `frontend/src/lib/components/shared/WetterTab.svelte` (flach, wie `shared/VersandTab.svelte`): reine Durchreichung an `WetterTabInhalt` mit explizitem Prop `context` und den übrigen Props; kein `<style>`, keine rohen Controls, Komponenten-Import nur aus `$lib/components/organisms/…`. Sie wird in `SEITEN_SCOPE` eingetragen. `TripTabs`, `TripNewEditor`, `CompareTabs`, `CompareNewEditor` importieren `$lib/components/shared/WetterTab.svelte`. Die `.ts`-Module unter `shared/wetter-tab/` bleiben unverändert (AC-22); kein `.svelte.ts`-Controller.

**K-2 „Molekül NichtImBriefing“ (AC-15):** Das generische Molekül heißt `molecules/ChipLeiste.svelte` (Chips aus `Btn`). `NichtImBriefing` bleibt Organismus unter `organisms/wetter-tab/` und baut auf `ChipLeiste` auf; „Molekül“ in AC-15 ist für `NichtImBriefing` als Oberbegriff „Baustein“ zu lesen. Der Server-Render-Test aus AC-15 prüft `ChipLeiste` (in `molecules/__tests__/einstellungszeile_chips.test.ts`) und `NichtImBriefing` (ein Chip je nicht ausgewählter Metrik, in `organisms/__tests__/wetter_tab_bausteine.test.ts`). Zusätzlich neu: `molecules/Einstellungszeile.svelte` (Titel, optionaler Hinweis, Bereich für das Bedienelement). Beide im Barrel `molecules/index.ts`.

**K-3 Ampel-Tokens (AC-11):** Werte und WCAG-Kontrast gegen `--g-card` (Light `#ffffff`, Dark `#1d1d1a`):

| Token | Light | Dark | Mockup |
|---|---|---|---|
| `--g-ampel-gruen` | `#15803d` (5,0:1) | `#15803d` (3,4:1) | `#15803d` |
| `--g-ampel-gelb` | `#b98100` (3,4:1) | `#d69500` (6,6:1) | `#d69500` (Light nur 2,6:1) |
| `--g-ampel-orange` | `#d4530a` (4,2:1) | `#d4530a` (4,1:1) | `#d4530a` |
| `--g-ampel-rot` | `#a8104a` (7,4:1) | `#d43a76` (3,8:1) | `#a8104a` (Dark nur 2,3:1) |

„Nahe am Mockup“ heißt im Test: Farbton ±8°, Light-Helligkeit (HSL) ±8 Punkte, Dark-Helligkeit ≥ Mockup und höchstens +20 Punkte. Light-Werte stehen im ersten `:root`-Block, Dark-Werte im Block `:root[data-theme="dark"]`.

**K-4 Atome (AC-13, AC-14):** `atoms/Input.svelte` bekommt das Prop `ampel?: 'green' | 'yellow' | 'orange' | 'red'` (Schlüssel wie `ampelModell.ts`), gerendert als `data-ampel`; die 3px-Unterkante (Mockup) kommt per Regel in `app.css` aus `--g-ampel-*`; die Stärke liegt außerhalb des 4px-Rasters und wird als neuer Maß-Token `--g-size-3px` (Light = Dark) geführt. Ohne Prop ist das Markup unverändert. `ui/segmented/Segmented.svelte` bekommt je Option `farbe?` → Farbpunkt-Element mit `data-farbe`; die `items`-API von `atoms/Segmented.svelte` reicht künftig `testid`, `badge_testid` und `farbe` durch (heute werden Testids dort verworfen). Neues Atom `atoms/Skelett.svelte`: Maße nur aus Tokens, `role="status"`, `aria-busy="true"`, Beschriftung (`aria-label`) vom Aufrufer aus dem Katalog; ohne Aufrufer-Text verwendet das Atom einen Standardtext „wird geladen“ aus dem Katalog (vorhandener Schlüssel, falls keiner existiert neuer Schlüssel in DE und EN im Allgemein-Katalog, nicht in `wetter.json`), keine hartcodierten Texte; im Barrel `atoms/index.ts`.

**K-5 Touch-Ziele:** Die bestehende Design-Prüfung verlangt ≥44px für Knöpfe, Radios und Schalter im Wetter-Reiter. `Btn` bekommt deshalb eine Größe `tap` (Höhe `--g-tap-min`), bevor die Organismen ihre rohen Knöpfe durch `Btn` ersetzen.

**K-6 Organismen (AC-12, AC-16):** `VorlageKarte` (7 Knöpfe), `MetrikZeile` (2 Knöpfe, „Alarm ab“-Stufen als `Segmented` mit `farbe`), `GrenzenEditor` (Eingabe → `Input ampel=…`), `AlarmAbKopf` (als `Einstellungszeile`) ohne rohe Controls; `AmpelLeiste` nutzt `--g-ampel-*`. Jede Stufe ist zusätzlich ohne Farbe erkennbar: sichtbar durch Form und Lage (feste Reihenfolge grün → gelb → orange → rot von links nach rechts, sichtbare Trennfuge zwischen den Segmenten, darüber die Grenzwerte bzw. bei Gewitter die Stufenwörter als Text), für Hilfstechnik durch den Farbnamen aus dem Katalog (`wetter.farbe.*`) je Segment und `data-farbe`. `WarnungenRadarKarte` nutzt `Einstellungszeile`. In `WetterTabInhalt` werden Ladeanzeige (Skelett, Text „Lade Metriken …“ bleibt für Hilfstechnik) und der Erneut-laden-Knopf (`Btn`) aus Atomen gebaut.

**K-7 Erhaltene Prüf-Anker (AC-9, AC-23):** Testids und ARIA-Rollen bleiben: `wetter-zeile-*`, `wetter-ampel-leiste-*`, `wetter-tab-laden`, `wetter-tab-erneut-laden`, „Alarm ab“-Stufen mit `role=radio` und `aria-checked`, `aria-expanded` am Vorlagen-Picker, `wetter-warnungen-schalter`, `wetter-radar-schalter`, keine `select`-Elemente. Angepasst werden nur Struktur-Selektoren, keine Prüfung wird abgeschwächt.

**K-8 Goldens:** `organisms/__tests__/wetter_tab_render_gleich.test.ts` und seine Referenzkopien entfallen (Teil 1 hat sie ausdrücklich nur bis Teil 2 vorgesehen; Ersatz ist die Staging-Sichtprüfung AC-23). Die SSR-Goldens `tests/golden/f9_trip_flaechen/anlegen_{route,etappen,weiter}.{de,en}.html` und `tests/golden/f10_vergleich_flaechen/anlegen_weiter.{de,en}.html` werden neu geschrieben; der Diff darf nur Markup und Scoping-Hash betreffen, keine Texte (AC-21).

**Reihenfolge Teil 2:** (1) Tokens + Kontrast-Test → (2) Atome Input/Segmented/Skelett, `Btn` `tap`, Barrel → (3) Moleküle Einstellungszeile, ChipLeiste → (4) `git mv` zu `WetterTabInhalt`, Seite `shared/WetterTab.svelte`, Importeure, `SEITEN_SCOPE`, Pfad-Tests → (5) Organismen ohne rohe Controls, AmpelLeiste-Tokens → (6) Goldens → (7) Showcase und Doku (`COMPONENTS.md`, `TOKENS.md`) → (8) Wächter, `npm run check`, `/e2e-verify` (Trip und Orts-Briefing, Light und Dark, DE und EN).

**Betroffene Dateien zusätzlich zur Tabelle oben:** `ui/input/input.svelte`, `ui/segmented/Segmented.svelte`, `ui/btn/*`, `molecules/ChipLeiste.svelte`, `shared/WetterTab.svelte` (CREATE), `organisms/wetter-tab/WetterTabInhalt.svelte` (MOVE), `organisms/wetter-tab/WarnungenRadarKarte.svelte`, Pfad-Tests mit Konstante `WETTER_TAB` (trip-new, compare-new, shared/wetter-tab) sowie `organisms/__tests__/wetter_tab_ort.test.ts`, `wetter_tab_barrel.test.ts`, `shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts`, `s3a2794_teil3_keine_nativen_controls.test.ts`, die acht Golden-Dateien.

## Expected Behavior

- **Input:** Quellbaum von `main` mit rotem Wächter-Test (Teil 1); Wetter-Reiter in Trip und Orts-Briefing (Hub und Anlege-Kette).
- **Output:** Teil 1: Wächter-Test grün, Wetter-Reiter sieht und verhält sich wie zuvor. Teil 2: Wetter-Reiter folgt dem Mockup (Ampel-Unterkanten, Farbpunkte, Skelett beim Laden, Chip-Leiste „Nicht im Briefing“), `WetterTab` ist eine dünne Seite.
- **Side effects:** Keine Datenänderung, keine API-Änderung, keine Textänderung.

## Definition of Done

Fertig ist Teil 1, wenn der Bausteine-Wächter auf `main` grün ist, der CI-Job `frontend-test` wieder durchläuft und der Wetter-Reiter in Trip und Orts-Briefing pixelgleich zum Stand davor aussieht (AC-1 bis AC-10). Fertig ist Teil 2, wenn `WetterTab` als dünne Seite in `SEITEN_SCOPE` steht, die Bausteine für die Scheiben (a)/(b) im Design-System liegen, die Ampel-Tokens den Kontrastnachweis in Light und Dark bestehen und der Wetter-Reiter auf Staging für Trip und Orts-Briefing in DE und EN unverändert funktioniert (AC-11 bis AC-23).

## Acceptance Criteria

- **AC-1:** (Teil 1) Given der Quellbaum nach Teil 1 / When der Wächter-Test `bausteine_waechter.test.ts` AC-7 („echter Quellbaum grün“) läuft / Then ist er grün, und der CI-Job `frontend-test` ist für `main` und neue PRs wieder grün.

- **AC-2:** (Teil 1 und 2) Given der Diff von Teil 1 bzw. Teil 2 gegen `origin/main` / When `BESTAND` (Obergrenze 204), `AUSNAHMEN` und die Marker `audit:exempt` im Diff geprüft werden / Then enthält der Diff keinen neuen Eintrag in `BESTAND` oder `AUSNAHMEN` und kein neues `audit:exempt`.

- **AC-3:** (Teil 1) Given die neun Dateien `WetterTab`, `VorlageKarte`, `MetrikZeile`, `GrenzenEditor`, `WarnungenRadarKarte`, `AmpelLeiste`, `AlarmAbKopf`, `NichtImBriefing`, `AnpassenKarte` / When der Quellbaum nach Teil 1 geprüft wird / Then liegen die neun `.svelte`-Dateien unter `frontend/src/lib/components/organisms/wetter-tab/` (per `git mv`, Historie erhalten), die acht `.ts`-Module liegen weiterhin unter `frontend/src/lib/components/shared/wetter-tab/`, und unter `shared/wetter-tab/` liegt keine `.svelte`-Datei mehr.

- **AC-4:** (Teil 1) Given die neun verschobenen Dateien / When Regel b des Wächters (nur `--g-*`-Tokens, keine px/rem/em außer 0 und 1px-Rahmen, keine Hex-/rgb-/Farbnamen) auf sie angewendet wird / Then meldet sie 0 Verstöße, ohne dass die Dateien in `AUSNAHMEN` stehen oder `audit:exempt` tragen.

- **AC-5:** (Teil 1) Given die neuen Tokens `--g-tap-min` und `--g-size-*` in `app.css` / When ihre Definitionen gelesen werden / Then gibt es `--g-size-*` nur für Maße außerhalb des 4px-Rasters von `--g-s-1..20`, `--g-tap-min` ist 44px, und die Werte sind in Light und Dark identisch.

- **AC-6:** (Teil 1, Pixelgleichheit) Given eine Wetter-Reiter-Ansicht mit Trip- bzw. Vergleichsdaten vor und nach Teil 1 / When die berechneten Maße (Breite, Höhe, Padding, Margin, Gap, Schriftgröße) der Elemente beider Stände im Browser verglichen werden / Then sind sie für jedes Element der neun Komponenten identisch (kein gerundeter Wert, keine Verschiebung).

- **AC-7:** (Teil 1, Pixelgleichheit) Given dieselben Testdaten / When `WetterTab` vor und nach Teil 1 per Server-Render gerendert wird / Then ist das gerenderte Markup bis auf Dateipfad-bedingte Unterschiede (Komponenten-Pfade in Kommentaren oder Klassen-Hashes) gleich, und es gibt weder neue noch entfernte Elemente.

- **AC-8:** (Teil 1) Given die vier Importeure `TripTabs`, `CompareTabs`, `TripNewEditor`, `CompareNewEditor` und alle Tests mit Pfad-Strings / When ein `grep -rn "shared/wetter-tab/.*\.svelte" frontend/` ausgeführt wird (auch nach dem letzten Rebase vor dem Merge) / Then findet er keinen Treffer, und `npm run check` (svelte-check) meldet keinen Import-Fehler.

- **AC-9:** (Teil 1 und 2) Given die Wetter-Reiter von Trip und Orts-Briefing nach Teil 1 bzw. Teil 2 / When die Kerntests des Reiters (`s3a2794_*`, `trip-new/__tests__/f002*`, `fixloop3*`, `compare-new/__tests__/f001_f002*`, `compare/__tests__/fa3*` und die Tests unter `shared/wetter-tab/__tests__/`) laufen / Then sind sie grün, ohne dass Zusicherungen entfernt oder abgeschwächt wurden (nur Pfad-Strings oder, in Teil 2, Struktur-Selektoren dürfen angepasst werden).

- **AC-10:** (Teil 1) Given `organisms/index.ts` nach Teil 1 / When der Barrel gelesen wird / Then exportiert er die neun Organismen aus `wetter-tab/`, und `COMPONENTS.md` sowie `TOKENS.md` beschreiben die neuen Organismen und Maß-Tokens.

- **AC-11:** (Teil 2) Given die Tokens `--g-ampel-gruen`, `--g-ampel-gelb`, `--g-ampel-orange`, `--g-ampel-rot` in `app.css` / When ihre Kontrastverhältnisse gegen den Karten-Hintergrund (`--g-card` bzw. der in `Card.svelte` genutzte Hintergrund) in einem Test berechnet werden / Then sind alle vier Werte im Light-Modus und im Dark-Modus (eigener Dark-Block) mindestens 3:1, und jeder Wert liegt in Farbton und Helligkeit nahe an den Mockup-Werten `#15803d`, `#d69500`, `#d4530a`, `#a8104a` (Abweichung nur dort, wo WCAG-AA es verlangt).

- **AC-12:** (Teil 2) Given `AmpelLeiste` nach Teil 2 / When ihre Quelle und ihr gerendertes Markup geprüft werden / Then nutzt sie `--g-ampel-*` statt der Behelfs-Tokens (success, `--g-wx-sun`, accent, danger), und die Zuordnung der Stufen zu Farben entspricht unverändert der Logik in `ampelLeiste.ts`; zusätzlich ist jede Stufe auch ohne Farbe erkennbar (Text oder Form).

- **AC-13:** (Teil 2) Given `atoms/Input.svelte` mit der Ampel-Variante und `atoms/Segmented.svelte` mit Farbpunkt / When sie per Server-Render (`svelte/server`) mit je einer Ampelfarbe gerendert werden / Then trägt der Input die zur Farbe gehörende Unterkante (Klasse bzw. Token `--g-ampel-*`) und das Segment den Farbpunkt; ohne Variante ist das Markup gegenüber heute unverändert.

- **AC-14:** (Teil 2) Given das neue Atom `atoms/Skelett.svelte` / When es per Server-Render gerendert wird / Then entsteht ein Platzhalter-Element aus Tokens (keine rohen Maße), das für Hilfstechnik als „wird geladen“ gekennzeichnet ist, und es steht im Barrel `atoms/index.ts`.

- **AC-15:** (Teil 2) Given das Molekül `molecules/Einstellungszeile.svelte` und das Molekül `NichtImBriefing` als Chip-Leiste / When beide per Server-Render mit Beispieldaten gerendert werden / Then zeigt die Einstellungszeile Titel, optionalen Hinweis und einen Bereich für das Bedienelement, und `NichtImBriefing` zeigt je nicht ausgewählter Metrik einen Chip; beide sind aus `atoms`/`molecules` zusammengesetzt und haben keine rohen Controls.

- **AC-16:** (Teil 2) Given die Organismen `VorlageKarte`, `AlarmAbKopf`, `MetrikZeile` mit `AmpelLeiste` und `GrenzenEditor` nach Teil 2 / When ihre Quellen geprüft werden / Then enthalten sie kein rohes `<button>`, `<input>`, `<select>` oder `<textarea` mehr (nur `Btn`, `Input`, `Segmented`, `Switch` und weitere Atome), und Regel b bleibt bei 0 Verstößen.

- **AC-17:** (Teil 2) Given `WetterTab.svelte` nach Teil 2 / When der Wächter Regel a anwendet / Then steht `WetterTab` in `SEITEN_SCOPE`, enthält weder `<style>` noch `style=`/`style:`, keine Tailwind-Utilities und keine rohen Controls, und importiert Komponenten nur aus `atoms`, `molecules`, `organisms` (und freigegebenen Kompositionen).

- **AC-18:** (Teil 2) Given der echte Quellbaum nach Teil 2 / When `bausteine_waechter.test.ts` (AC-7), `bausteine_waechter_wirkort.test.ts` und `showcase.test.ts` laufen / Then sind alle grün, und es gibt keinen neuen Eintrag in `BESTAND` oder `AUSNAHMEN`.

- **AC-19:** (Teil 2, Trip und Vergleich teilen Bausteine) Given `TripTabs`/`TripNewEditor` und `CompareTabs`/`CompareNewEditor` / When ihre Importe geprüft werden / Then importieren beide Kontexte `WetterTab` und damit dieselben Atome, Moleküle und Organismen aus demselben Pfad; es gibt keine Compare-eigene Komponente für Vorlage, Alarm-ab, Metrik-Zeile, Ampel-Leiste, Grenzen-Editor oder „Nicht im Briefing“.

- **AC-20:** (Teil 2) Given der Showcase `/_design-system` / When die Seite gerendert wird / Then zeigt sie die vier Ampel-Tokens (Light und Dark) sowie Input mit Ampel-Unterkante, Segmented mit Farbpunkt und Skelett, und `showcase.test.ts` prüft, dass jedes neue Atom dort vorkommt.

- **AC-21:** (Teil 1 und 2, Zweisprachigkeit) Given die Texte des Wetter-Reiters in DE und EN / When `wetter.json` beider Sprachen vor und nach der Lieferung verglichen wird / Then sind sie unverändert, und der Wetter-Reiter rendert in beiden Sprachen dieselben Texte wie zuvor; es gibt keine neuen hartcodierten Nutzertexte in den Bausteinen (Beschriftungen kommen aus dem Katalog bzw. aus Props).

- **AC-22:** (Teil 2, keine Logikänderung) Given die acht `.ts`-Module unter `shared/wetter-tab/` / When der Diff von Teil 2 gegen `origin/main` geprüft wird / Then sind sie unverändert (außer unvermeidbaren Importpfaden), und die bestehenden Modell-Tests (Ampel-Zähler, Reihenfolge, Speicher-Payload, Warnungen) sind grün.

- **AC-23:** (Teil 2, Staging) Given Staging mit Teil 2 / When der Wetter-Reiter eines Trips und eines Orts-Briefings (Hub) in Light und Dark geöffnet und eine Grenze geändert, gespeichert und neu geladen wird / Then sehen beide Kontexte gleich aus, Ampelfarben und Unterkanten sind lesbar, das Skelett erscheint beim Laden, und der gespeicherte Wert bleibt erhalten.

## Test Plan

Alle Tests laufen mit `node --test` über `npm test -- <datei>` im Ordner `frontend/`, Ablage in `<schicht>/__tests__/`. Verhalten wird per Server-Render (`svelte/server`) geprüft; Mocks, die nur die eigene Annahme spiegeln, sind verboten, Dateiinhalt-Prüfungen nur mit `# doc-compliance-test`, wo es um Quellregeln geht (Wächter-Stil).

| Test | Ort | Deckt ab |
|------|-----|----------|
| Wächter AC-7 und Wirkort-Test (bestehend) | `frontend/src/lib/__tests__/bausteine_waechter.test.ts`, `bausteine_waechter_wirkort.test.ts` | AC-1, AC-2, AC-4, AC-17, AC-18 |
| Pfad-Test: keine `.svelte` unter `shared/wetter-tab/`, `.ts` dort vorhanden; Teil 1: Importeure zeigen auf `organisms/wetter-tab/`; ab Teil 2: alle vier Importeure zeigen auf `$lib/components/shared/WetterTab.svelte`, die Seite bindet `organisms/wetter-tab/WetterTabInhalt.svelte` ein (K-1) | `frontend/src/lib/components/organisms/__tests__/wetter_tab_ort.test.ts` | AC-3, AC-8, AC-19 |
| Token-Test: `--g-size-*` nur außerhalb 4px-Raster, `--g-tap-min`, Light = Dark | `frontend/src/lib/__tests__/tokens_masse.test.ts` | AC-5 |
| Pixelgleichheits-Test (nur Teil 1, entfällt mit Teil 2, siehe K-8): Server-Render der neun Komponenten gegen gesicherte Referenz vor der Verschiebung | `frontend/src/lib/components/organisms/__tests__/wetter_tab_render_gleich.test.ts` | AC-6, AC-7 |
| Ratsche: BESTAND/AUSNAHMEN/`audit:exempt` im Diff unverändert | `frontend/src/lib/__tests__/bausteine_waechter.test.ts` (bestehende Ratschen) | AC-2 |
| Kerntests Wetter-Reiter (bestehend, Pfade nachgezogen) | `shared/__tests__/s3a2794_*`, `trip-new/__tests__/`, `compare-new/__tests__/`, `compare/__tests__/`, `organisms/wetter-tab/__tests__` bzw. `shared/wetter-tab/__tests__/` | AC-9, AC-22 |
| Barrel/Doku | `frontend/src/lib/components/organisms/__tests__/wetter_tab_barrel.test.ts` (Barrel exportiert alle Wetter-Organismen, ab Teil 2 `WetterTabInhalt` statt `WetterTab`) | AC-10 |
| Ampel-Kontrast Light + Dark (Berechnung der WCAG-Luminanz aus den Werten in `app.css`, gegen Karten-Hintergrund beider Modi; Token-Quelle ist die Stylesheet-Datei selbst, daher markiert mit `# doc-compliance-test` wie die bestehenden Kontrasttests) | `frontend/src/lib/__tests__/ampel_tokens_kontrast.test.ts` | AC-11 |
| Atome: Input-Ampel, Segmented-Farbpunkt, Skelett per Server-Render | `frontend/src/lib/components/atoms/__tests__/ampel_atome.test.ts` | AC-13, AC-14 |
| Molekül Einstellungszeile, Chip-Leiste per Server-Render | `frontend/src/lib/components/molecules/__tests__/einstellungszeile_chips.test.ts` | AC-15 |
| Organismen ohne rohe Controls, AmpelLeiste nutzt `--g-ampel-*`, Stufe ohne Farbe erkennbar | `frontend/src/lib/components/organisms/__tests__/wetter_tab_bausteine.test.ts` | AC-12, AC-15 (NichtImBriefing), AC-16 |
| Trip und Vergleich importieren denselben Baustein | `frontend/src/lib/components/organisms/__tests__/wetter_tab_ort.test.ts` | AC-19 |
| Showcase zeigt Ampel-Tokens und neue Atome | `frontend/src/routes/_design-system/showcase.test.ts` | AC-20 |
| DE/EN-Katalog `wetter.json` unverändert, Reiter in beiden Sprachen mit denselben Texten (ein etwaiger neuer Skelett-Standardtext liegt im Allgemein-Katalog und ist im Reiter durch das `aria-label` des Aufrufers überdeckt, K-4) | `frontend/src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts` | AC-21 |
| `.ts`-Module unter `shared/wetter-tab/` im Diff gegen `origin/main` unverändert (Prüfschritt im Validierungs-Agenten per `git diff --stat origin/main -- frontend/src/lib/components/shared/wetter-tab/*.ts`, erwartet leer bis auf Importpfade) | Validierung Phase 6 | AC-22 |

**Staging-Sichtprüfung (Teil 2, AC-23):** Nach dem Push läuft `/e2e-verify` gegen `https://staging.gregor20.henemm.com`: Wetter-Reiter eines Trips und eines Orts-Briefings, Light und Dark, Grenze ändern, speichern, neu laden; Screenshots beider Kontexte werden nebeneinander verglichen. Für Teil 1 genügt die automatisierte Maß-Prüfung (AC-6) plus ein Stichproben-Blick auf denselben Reiter.

**Rote Phase:** Teil 1: AC-1 ist bereits rot auf `main` (Nachweis aus Nutzersicht: CI-Job `frontend-test`). Teil 2: Kontrast-, Atom-, Molekül- und Organismen-Tests werden vor der Implementierung rot geschrieben.

## Risks

- **Pfad-Tests nach Rebase:** Neu hinzugekommene Tests mit Pfad-Strings brechen erst nach dem Rebase; deshalb Pfad-Grep vor dem Merge wiederholen (AC-8).
- **Pixelgleichheit Teil 1:** Werte außerhalb des 4px-Rasters nur über neue Tokens, nie runden (AC-5, AC-6).
- **Ampelfarben (Teil 2):** Die Farbänderung ist sichtbar, folgt aber dem angenommenen Mockup und WCAG-AA; Gelb muss abgedunkelt werden (`#d69500` auf Weiß ca. 2,6:1). Dark-Werte müssen eigens nachgewiesen werden (AC-11).
- **Wächter-Ratschen:** Jeder Versuch, über `BESTAND`/`AUSNAHMEN`/`audit:exempt` abzukürzen, ist ein Verstoß (AC-2).
- **Vorübergehender Zustand:** `WetterTab` liegt nach Teil 1 als Organismus mit Zustand und API-Anbindung; das widerspricht dem Bild der dünnen Seite und wird erst mit AC-17 aufgelöst.
- **Offene PRs:** #2874 und #2846 berühren die neun Dateien nicht (geprüft); bei neuen PRs vor dem Merge erneut prüfen.

## Known Limitations

- Nach Teil 1 enthalten die neun Organismen weiterhin rohe `<button>`/`<input>`; das ist in Bausteinen regelkonform und wird bewusst erst in Teil 2 für die genannten vier Organismen ersetzt. `WarnungenRadarKarte` und `AnpassenKarte` behalten ihre rohen Controls, soweit Regel b sie erlaubt, bis ein Folge-Workflow sie umbaut.
- Dringlichkeits-Tokens, Kanal-Tabelle und die übrigen Scheibe-(c)–(e)-Bausteine fehlen noch; die Elementliste-Abgleich-Messung ist erst ab Scheibe (a) sinnvoll.
- `--g-wx-*` hat weiterhin keinen Dark-Wert; Teil 2 löst das nur für die Ampel-Nutzung in `AmpelLeiste`.
- Der Showcase nimmt Organismen weiter aus (bestehende Regel); er zeigt in Teil 2 Tokens und Atome.
- Teil 1, AC-6: Der Maßvergleich läuft deterministisch in `wetter_tab_render_gleich.test.ts` (gleicher Markup-Baum und gleiches CSS nach Token-Auflösung gegen die Referenz vor der Verschiebung; daraus folgen gleiche berechnete Maße). Ein eigener Playwright-Vorher/Nachher-Lauf in `frontend/e2e/` entfällt; die Sichtprüfung im Browser übernimmt `/e2e-verify` auf Staging.
- Teil 1: Die Historie der neun Dateien ist commitweise erhalten (Umbenennung `shared/` → `organisms/` im Implementierungs-Commit); im Gesamt-Diff ordnet Git sie den byte-gleichen Referenzkopien `*.svelte.txt` zu.
- Teil 1, Nebenwirkungen: `DatumFeld`/`UhrzeitFeld` nutzen `--g-s-6` statt `24px` (pixelgleich). Die Golden-Dateien `tests/golden/f9_trip_flaechen/anlegen_*.de.html` und `f10_vergleich_flaechen/anlegen_weiter.de.html` sind nur im Svelte-Scoping-Hash des Wetter-Reiters nachgezogen (Texte unverändert). `docs/context/einstellungen_neu/elementliste.json` ist mit `ermittleEn` gegen den aktuellen Katalog neu berechnet (vorher rot auf `main`, verwaister Schlüssel `wertebereiche.preset_dialog.standard`).

- Teil 2: `WarnungenRadarKarte` und `AnpassenKarte` behalten ihre rohen Schalter (`role=switch`). Das Atom `atoms/Switch.svelte` hat ein fest verdrahtetes `data-testid="switch"`, reicht weder Attribute noch `aria-checked` durch; ein Umbau bräche die Staging-Prüfanker `wetter-warnungen-schalter`/`wetter-radar-schalter`. AC-16 nennt beide Organismen nicht. Der Ausbau des Switch-Atoms folgt in einem eigenen Issue.
- Teil 2: Die Ampel-Werte weichen dort vom Mockup ab, wo WCAG-AA es verlangt: Gelb wird im Light-Modus abgedunkelt, Rot im Dark-Modus aufgehellt (siehe K-3).

## Changelog

- 2026-11-11: Initiale Spec (draft) für Workflow `feature-2913-bausteine`, Issue #2913.
- 2026-11-11: Abschnitt „Umsetzungsplan Teil 2 / Klarstellungen“ (K-1 bis K-8) und zwei Known Limitations für Workflow `feature-2913-teil2`; ACs unverändert.
