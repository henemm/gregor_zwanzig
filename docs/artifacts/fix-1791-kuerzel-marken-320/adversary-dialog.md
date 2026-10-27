# Adversary Dialog — fix-1791-kuerzel-marken-320
Spec: docs/specs/modules/fix_1791_kuerzel_marken_320px.md
Datum: 2026-10-18 11:29

## Checkliste
- [x] **Input:** Reihenfolge-Bereich in Trip-Editor oder Ortsvergleich-Fläche bei Fensterbreite
- [x] **Output:** Jede Ziehzeile zeigt oben Position, Griff, Name und beide Marken (volle Breite),
- [x] **Side effects:** keine; reines Layout.
- [x] **AC-1:** Given der Ortsvergleich-Editor bei 320×568 mit den Blöcken Stundenverlauf und Ausblick und den Zeilen wind, precipitation, thunder, gust, rain_probability, sunshine / When der Bereich „Reihenfolge" geladen und jede Zeile mittig ins Sichtfenster gescrollt wird / Then erfüllt in **allen** Zeilen **beider** Blöcke jede Marke die fünf Sichtbarkeits-Bedingungen aus #1719-S4 (Text nicht beschnitten `clientWidth ≥ scrollWidth`, innerhalb der Zeile, im Sichtfenster, von keinem Nachbarelement überdeckt, Text exakt). bei 320 px; heute rot (clientWidth 9 / scrollWidth 22–47), nach dem Fix grün. Live-Schicht; das ist der Bug-Nachweis aus Nutzersicht.
- [x] **AC-2:** Given der Trip-Editor bei 320×568 mit der Größe Gewitter in der Reihenfolge / When der Bereich „Reihenfolge" geladen wird / Then ist die Kurzform-Marke des Gewitters vollständig sichtbar (kein Überstand, `clientWidth ≥ scrollWidth`) und die Zeile erfüllt alle fünf Bedingungen. nach dem Fix grün.
- [x] **AC-3:** Given eine Ziehzeile bei 320 px, deren Größe den Roh/Einfach-Umschalter hat / When die Zeile angezeigt wird / Then liegen Umschalter und „Aus" in einer eigenen Zeile **unter** Name und Marken, überlagern keine Marke (`elementFromPoint` in der Mitte jeder Marke trifft die Marke) und sind weiterhin bedienbar (Klick auf „Einfach" schaltet den Modus, Klick auf „Aus" entfernt die Größe aus dem Kanal). vollständig unterhalb der des `.label-cell`, danach echter Klick auf Umschalter und „Aus".
- [x] **AC-4:** Given der Trip-Editor und der Ortsvergleich bei 375×667 / When der Bereich „Reihenfolge" geladen wird / Then gibt es unverändert keine Verletzung der fünf Bedingungen und keinen waagerechten Seitenscroll (`documentElement.scrollWidth ≤ innerWidth + 1`). (375, 390, 414, 600, 768, 899) — alle Breiten unter 900 px grün, nicht nur 320 px.
- [x] **AC-5:** Given eine Fensterbreite ab 900 px (Media-Query-Rand 901 px und Bruchzone 960/1024 px) / When die Ziehzeile gerendert wird / Then steht `.controls` weiterhin **rechts neben** dem Namen in derselben Rasterzeile, die Marken sind einzeilig, und bei Platzmangel kürzt der **Name**, nie eine Marke. Prüfung bei 901 px, dass `.controls` und `.label-cell` dieselbe vertikale Mitte teilen (Controls nicht unter dem Label). Gegenprobe siehe Abschnitt „Mutations-Gegenprobe".
- [x] **AC-6:** Given der Reihenfolge-Bereich bei einer Breite unter 900 px / When der Nutzer eine Zeile am Ziehgriff auf eine andere Position zieht / Then landet sie an der Zielposition, der Stand wird gespeichert und bleibt nach dem Neuladen erhalten; die Zeilen der Gruppe „Aus in diesem Kanal" bleiben unverändert aufgebaut (Name + „Ein"-Knopf in einer Zeile, ohne Griff und Position), der „Ein"-Knopf holt die Größe zurück. (z. B. 375 px); plus Prüfung der Aus-Zeile (kein `.drag-handle`, „Ein" im Sichtfenster und nicht von der Marke überlagert) bei 320 px.
- [x] **AC-7:** Given der Prüftest `kuerzel-marken-sichtbar.staging.spec.ts` / When er gegen Staging läuft / Then enthält die Auflösungsliste 320×568, die Zeile wird mittig gescrollt, die Überdeckungs-Prüfung gilt in allen Auflösungen (keine `mobileNavZone`- Abschaltung mehr), und die Zeilenzahl wird je `wm2-reihenfolge-row`-Block erwartet, sodass der Test bei zwei Blöcken nicht mit „12 statt 6" fehlschlägt. der #1719-S4-Spec); Nachweis der Reparatur: bei zurückgenommenem Fix (Mutation 1) ist er bei 320 px rot, bei angewandtem Fix grün — er misst also weder durch das Nav-Artefakt noch verfehlt er den echten Fehler.

## Dialog

### Runde 1
**Adversary:** Geprueft wurde der uncommittete Diff (nur Komponente, 17+/3-).
- (a) Kern-Strukturtests (`node --test`, Kommando aus frontend/package.json): weather_metric_kuerzel_marken, weather_metric_name_forms_visible, metricKuerzelLegende -> 43 pass / 0 fail.
- (b) CSS-Logik: Alle Aenderungen liegen innerhalb `@media (max-width: 899px)`; ausserhalb kein Zeichen geaendert (git diff). Spezifitaet: `.row:not(.aus-row)` trifft die Aus-Zeile gar nicht; Mobil-`.controls` (spaeter, gleiche Spezifitaet) gewinnt gegen Basis-`.controls`. Markup-Reihenfolge pos, DragHandle, label-cell, controls (WeatherV2Reihenfolge.svelte:119-156) => pos Sp.1, Griff Sp.2, label-cell explizit Sp.3 (alle Zeile 1), controls explizit Zeile 2 ueber alle Spalten. Korrekt.
- (c) Geometrie: Kein Staging-Stand mit Fix, Vite-Proxy zeigt auf Staging, also NICHT die echte Seite messbar. Stattdessen statisches Mess-Geruest (docs/artifacts/fix-1791-kuerzel-marken-320/geometry-harness.mjs): echter style-Block der Komponente + nachgebautes Zeilenmarkup in Chromium. 320 px: label-cell x 80..304 (224 px statt 11 px), Marken clientWidth==scrollWidth (67/67, 118/118), controls y 55..81 vollstaendig unter label-cell (y 12..45), Aus-Zeile einzeilig (Label 16..257, "Ein" 267..304), docW 320. 375/899: gleiche Form, kein Seitenscroll. 900/901/1024: controls rechts neben label (x 744..884 neben 80..734). Einschraenkung: Nachbau, nicht die echte Svelte-Seite; echte Bedingung 4 (elementFromPoint), Nav-Scroll und Klickbarkeit sind NOT_MEASURABLE bis Staging.
**Implementierer:** nicht beteiligt (Kontextisolation).

### Runde 2 (Mutations-Gegenprobe, String-Ersetzung, externe Sicherungskopie, Rueckspiel per diff identisch)
**Adversary:**
- M2: `@media (max-width: 899px)` -> `5000px`. Harness: bei 901 und 1024 px liegt controls UNTER dem Label (y 39..65 vs 12..29) => Mutation wirksam. Kern-Tests 43 pass / 0 fail => KEIN Kern-Test faengt sie. Faengt nur der Staging-Playwright-Test "AC-5: bei 901px steht .controls neben dem Label" (kuerzel-marken-sichtbar.staging.spec.ts:765) bzw. AC-12; beide laufen nicht in der CI-Ampel.
- M3: `.row:not(.aus-row)` -> `.row`. Harness 320 px: Aus-Zeile zerlegt (Label x 214..304 statt 16..257, "Ein" in Zeile 2, y 130..154). Kern-Tests 43/43 gruen. Im Staging-Spec gibt es KEINEN Aus-Zeilen-Test (kein wm2-aus-row-Treffer; AC-14 laeuft bei 1440 px, Z.689) => diese Mutation faengt NIRGENDS ein Test.
- Rueckspiel je Mutation per diff gegen Sicherungskopie identisch (IDENT2, IDENT3); git diff --stat danach wieder 17+/3-.
- M1/M4 nicht gefahren (M1 braucht Staging-Playwright; Rot-Beleg liegt in test-red-output.txt).
**Implementierer:** nicht beteiligt.

## Nachtrag nach dem Verdict (Orchestrator)

F001 im selben Ticket behoben: Der Staging-Spec bekam den Aus-Zeilen-Test bei 320 px und den Ziehtest bei 375 px (nur `--list`-geprueft, 10 Tests, nicht ausgefuehrt).
Code reference: frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts:1
PO-Freigabe der Restunsicherheit (echte 320-px-Messung nach Staging-Deploy) mit `ok ambiguous`.

## Findings

Finding F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:486
  Description: `.row:not(.aus-row)` (Z.486/489/492) ist der einzige Schutz der Aus-Zeile. Ohne `:not(.aus-row)` zerlegt sich die Aus-Zeile bei 320 px (gemessen), und KEIN Test wird rot (Kern 43/43; Staging-Spec ohne Aus-Zeilen-Test).
  Spec requirement: AC-6 / Test-Plan Test 5 - Aus-Zeile bei 320 px (kein .drag-handle, "Ein" im Sichtfenster, nicht ueberlagert), Ziehen bei < 900 px.
  Conflict: Der geforderte Test fehlt in kuerzel-marken-sichtbar.staging.spec.ts (AC-14 nur bei 1440 px). Mutation 3 bleibt unentdeckt.
  Remediation: Staging-Spec um AC-6-Test erweitern (320 px: wm2-aus-row ohne .drag-handle, Label und "Ein" in einer Zeile, "Ein" klickbar; Ziehen bei 375 px).

Finding F002
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:483
  Description: Rueckfallschutz der Zweizeilen-Struktur und gegen M2 liegt nur in Playwright-Specs ausserhalb der CI-Ampel (#1771); Kern-Tests sind gegen M2 und M3 blind.
  Spec requirement: Known Limitations der Spec.
  Conflict: Bekannte, dokumentierte Luecke, keine neue Abweichung.
  Remediation: Sammel-Eintrag #1199 / #1771.

## Confirmations
- AC-1/AC-2/AC-4: WeatherV2Reihenfolge.svelte:486-496 - Textspalte 224 px statt 11 px, Marken unbeschnitten (Harness). Staging-Messung NOT_MEASURABLE (Fix nicht deployt). CONFIRMED im Nachbau.
- AC-3: :492-495 - controls unter label-cell (y 55 > 45); Klickbarkeit NOT_MEASURABLE lokal.
- AC-5: Aenderungen nur in der Media-Query; 900/901/1024 px im Harness einzeilig. CONFIRMED.
- AC-6: Aus-Zeile 320 px einzeilig im Harness; Test dafuer fehlt (F001). Teilweise.
- AC-7: Prueftest nicht Gegenstand dieses Diffs (e2e/ ohne uncommittete Aenderung; Z.55 320 px, Z.201 mittiges Scrollen, Z.765 AC-5-Test vorhanden). Nicht weiter geprueft.

## Herkunft der Vorbedingungen

Vorbedingungen (Spec, Staging-Messbefund) aus der Spec uebernommen; Geometrie selbst gemessen (Harness).

## Verdict

**AMBIGUOUS** - Fix-Logik und Geometrie im Nachbau korrekt, Kern 43/43 gruen; echte 320-px-Messung auf Staging steht aus (NOT_MEASURABLE). F001 behoben (Aus-Zeilen-Test ergaenzt), F002 Sammel-Eintrag. PO hat die Restunsicherheit mit `ok ambiguous` freigegeben.

## Geprüfte Dateien

- sha256:f2b7bcc6be882378e7dcde8aafdbe3c06f8cd98be837615dd23fb9c69a22af09  frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts
- sha256:5aa614ae7d7bef4e70882748700a1d7eaf47dd4d1484a9c78c4cfc5c44e9d5ea  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte

## Prüfbasis

- base: eaf35b5e953a5188949c7b1aa1dcd2ee4c852928
- blob:0800575cbb4babaa7fe93973dd68b15af7381383  frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts
- blob:3717c0b933fbec8c23f3e9fa32258fc8f3b78954  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte
