---
entity_id: feat_1256_s8c_hub_fidelity
type: feature
created: 2026-07-14
updated: 2026-07-14
status: draft
version: "1.0"
tags: [compare, ui-fidelity, design-handoff-4, issue-1256]
workflow: feat-1256-s8c-hub-fidelity
---

<!-- Issue #1256, Scheibe S8c (Restliste-Kommentar 2026-07-14, „Restliste = Vertrag").
     Umfasst genau R2 (Hub-Layout-Tab-Rahmen) + R3 (Hub-Fidelity-Bündel:
     SummaryCards-Copy, Orte-Tab-Rahmen, Breadcrumb, profileLabel, Mobile-Eyebrow,
     Mobile-Summary-Stack). Kanonische Quelle Desktop:
     `claude-code-handoff/current/jsx/screen-compare-detail.jsx` (im Repo).
     Kanonische Quelle Mobil: `screen-compare-detail-mobile.jsx` (Handoff-4,
     Scratchpad-Pfad im Kontext-Artefakt `docs/context/feat-1256-s8c-hub-fidelity.md`).
     Alle Ist-Referenzen in diesem Dokument wurden gegen HEAD 10e800af verifiziert
     (Datei:Zeile-Belege in jedem AC) — dritter Regressionsfall der Klasse
     „bereits vorhanden ohne Beleg behauptet" in S8b, hier bewusst vermieden. -->

# Issue #1256 — Scheibe S8c: Hub-Fidelity (Layout-Tab-Rahmen + Restliste-Bündel R3)

## Approval

- [x] Approved (PO-go 2026-07-15)

## Purpose

Der Orts-Vergleich-Detail-Hub (Desktop + Mobil) hat mehrere rein darstellende
Abweichungen vom Design-Handoff-4-Soll: dem Layout-Tab fehlt Überschrift/Hint/
Limit-Pillen/Card-Rahmen, mehrere SummaryCards zeigen rohe Preset-Felder statt
lesbarer Labels bzw. keine Sonderfälle (Draft, >3 Orte), der Orte-Tab hat keinen
Section-Rahmen, der Desktop-Breadcrumb hat einen App-weiten Extra-Krümel, und
die mobile Zusammenfassung ist ein starres 2×2-Grid statt der im Handoff
vorgesehenen klickbaren Chevron-Zeilen. S8c formalisiert genau diese 13
Abweichungen als Acceptance Criteria und behebt sie — ohne neue Schreibpfade,
ohne Änderung an `hubPutQueue` (S7).

## Source

- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte` (Layout-Tab,
  SummaryCard-Grid, Mobile-Monitoring-Stat, Orte-Tab-Panel)
- **File:** `frontend/src/routes/compare/[id]/+page.svelte` (Breadcrumb,
  Kontext-Unterzeile, Mobile-Header)
- **Identifier:** `<script>`-Block + Markup der o.g. Svelte-Komponenten (kein
  neues Modul, keine neue Route)

> **Schicht-Hinweis:** reine Frontend-/User-UI-Änderung (`frontend/src/...`,
> SvelteKit). Kein Go-API-, kein Python-Core-Anteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SectionH` (`frontend/src/lib/components/atoms/SectionH.svelte`) | atom | Geteilter Section-Header (eyebrow/title/`right`-Snippet); Hint wandert additiv ins `right`-Snippet — KEINE neue Prop, KEINE neue Komponente |
| `channelNamesLabel` (`subscriptionHelpers.ts:212`) | function | Kanal-Labels aus Preset-Konfiguration ableiten (bereits in Übersicht-Stat genutzt, CompareTabs.svelte:132) — für Layout-SummaryCard-Titel wiederverwenden |
| `presetProfileLabel` (`subscriptionHelpers.ts:134`) | function | Profil-Key → lesbares Label; bereits von CompareTile/HomeHero und der Mobile-Unterzeile in `+page.svelte:48/220` genutzt |
| `CompareLayoutRow` (`frontend/src/lib/components/molecules/CompareLayoutRow.svelte`) | molecule | Hat bereits eine `dense`-Prop (Z.17,20) für die mobile Kompaktdarstellung im Layout-Tab |
| `isMobileViewport` (CompareTabs.svelte, S8) | state | Bestehende Ein-Mount-Weiche (matchMedia 899px), steuert Desktop-/Mobil-Zweig in Übersicht und Layout-Tab |
| `handleValueChange(tabId)` (CompareTabs.svelte) | function | Bestehende Tab-Sprung-Funktion, von den SummaryCards genutzt — für die neuen Chevron-Zeilen (AC-7) wiederzuverwenden |
| `hubPutQueue` (S7) | mechanism | Schreibpfad-Serialisierung — bleibt unberührt, S8c fügt keine PUTs hinzu |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Layout-Tab-Rahmen (Desktop+Mobil), SummaryCard-Copy (Orte/Wertebereiche/Layout/Versand), Mobile-Status-Kurzform, Mobile-Chevron-Summary-Stack, Orte-Tab-Rahmen |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Breadcrumb auf 2 Krümel, Desktop-Unterzeile `profileLabel` statt roh, Mobile-Header-Eyebrow |
| `frontend/e2e/compare-hub-fidelity-s8c.spec.ts` | CREATE | Playwright-Staging-Wächter (Desktop 1280px + Mobil 390px) |
| `frontend/playwright.1256-s8c.staging.config.ts` | CREATE | Staging-Config nach Muster `playwright.1256-s8.staging.config.ts` |

### Estimated Changes

- Files: 4 (2 modify, 2 create)
- LoC: ~+230/-25 (Quell-Code ~+150/-25 auf beide Svelte-Dateien, Test+Config
  ~+80) — **knapp am 250-LoC-Limit, ggf. Override nötig** (PO-Freigabe
  erforderlich, siehe CLAUDE.md „Kein LoC-Override ohne Permission").
- Effort: medium

## Implementation Details

Section-Rahmen für Layout-Tab und Orte-Tab werden über den bereits vorhandenen
`SectionH`-Atom gebaut: der mono-Hint kommt additiv in dessen `right`-Snippet
(kein neuer Prop, `SectionH.svelte` selbst bleibt unverändert — Trip/Compare-
Sharing-Invariante). Die 3 Limit-Pillen (Desktop) bzw. kompakteren Pillen
(Mobil) sind statische, lokale Arrays analog dem JSX-Vorbild
(`screen-compare-detail.jsx:247`, `screen-compare-detail-mobile.jsx:150`) —
keine neue Datenquelle. Die Layout-Zeilen selbst (`CompareLayoutRow`) bleiben
funktional unverändert, nur der Rahmen darum ändert sich (Card Desktop,
kein Card + `dense`-Prop Mobil).

Für die SummaryCards werden bestehende, bereits im Modul vorhandene Ableitungen
wiederverwendet: `channelsLabel` (= `channelNamesLabel(preset)`, bereits Z.132)
für den Layout-Karten-Titel (mit Fallback `'Keine Kanäle'` statt dem
Übersicht-Stat-Fallback `'—'`, da JSX:169 explizit „Keine Kanäle" fordert),
`presetProfileLabel(preset.profil)` für den Wertebereiche-Karten-Titel (mit
Fallback auf den rohen `preset.profil`-Wert, falls das Mapping leer zurückgibt
— kein leerer Titel), sowie der bestehende `status`/`isDraft`-Zustand für die
Versand-Karten-Sonderfälle. Orte-Karte bekommt einen zusätzlichen bedingten
Suffix-String nach dem bestehenden `.slice(0, 3)`-Join.

Der mobile Summary-Stack (AC-7) ersetzt das 2×2-Grid im `isMobileViewport`-Zweig
durch 4 gestapelte, klickbare Zeilen (Eyebrow-Zeile klein-mono, Titel, Desc,
Chevron-Icon rechts) — als lokale Inline-Struktur oder kleine lokale Helper-
Funktion innerhalb `CompareTabs.svelte` (kein neues geteiltes Molecule, siehe
„Trip/Compare-Sharing-Begründung" unten). Jede Zeile ruft beim Klick
`handleValueChange(tabId)` auf, exakt wie die bestehenden SummaryCard-„Bearbeiten
→"-Buttons.

Breadcrumb-Änderung und `profileLabel`-Fix in `+page.svelte` sind reine
Markup-Anpassungen ohne neue Ableitung (`profileLabel` existiert bereits als
`$derived` in Zeile 48, wird nur in der Desktop-Unterzeile noch nicht
konsumiert).

## Expected Behavior

- **Input:** Bestehende Preset-Daten (Orte, Profil, Kanäle, Status draft/active/
  paused) wie bisher über `data.preset`/`preset`-Props.
- **Output:** Identische Daten, aber mit den in den Acceptance Criteria
  beschriebenen Rahmen/Labels/Sonderfällen gerendert — auf beiden Viewports
  (Desktop ≥900px, Mobil <900px via bestehendem `isMobileViewport`).
- **Side effects:** keine. Keine neuen Fetches, keine neuen PUT-Aufrufe, keine
  Änderung an `hubPutQueue` oder anderen S7-Schreibpfaden.

## Acceptance Criteria

- **AC-1:** Given den Hub-Layout-Tab eines Presets auf Desktop (≥900px) / When
  der Tab geöffnet wird / Then zeigt er den Section-Header „Übersicht pro
  Kanal" mit mono-Hint rechts „Metrik-Zeilen · Orte sind die Spalten — der
  Renderer kappt je Kanal", darunter 3 Mono-Limit-Pillen (`Email · alle
  Spalten` / `Telegram · max 8` / `SMS · flach · 0`) und einen Card-Wrapper
  (Padding 20, Spalten-Layout, Gap 16) um die bestehenden `CompareLayoutRow`s
  (Soll: `screen-compare-detail.jsx:245-266` + `:416-426`; Ist ohne Rahmen:
  `CompareTabs.svelte:847-853`).
  - Test: Playwright Desktop-Viewport — Section-Header-Text, Hint-Text und
    3 Pillen-Texte sichtbar; `CompareLayoutRow`-Zeilen bleiben innerhalb eines
    Card-Containers.

- **AC-2:** Given den Hub-Layout-Tab desselben Presets auf einem mobilen
  Viewport (<900px) / When der Tab geöffnet wird / Then zeigt er stattdessen
  den Header „Spalten pro Kanal" mit Hint „Renderer kappt je Kanal", kompaktere
  Pillen (SMS-Pille nur `SMS · flach`, ohne „· 0"), die `CompareLayoutRow`s mit
  `dense`-Prop (Prop existiert bereits: `CompareLayoutRow.svelte:17,20`), und
  KEINEN Card-Rahmen um die Zeilen (Soll:
  `screen-compare-detail-mobile.jsx:148-166`).
  - Test: Playwright Mobil-Viewport (390px) — Header/Hint-Text, kompakte
    Pillen-Texte, keine Card-Umrandung um die Layout-Zeilen.

- **AC-3:** Given ein Preset mit mehr als 3 verglichenen Orten / When der
  Übersicht-Tab (Desktop und Mobil) gerendert wird / Then zeigt die
  Orte-SummaryCard hinter den ersten 3 Ortsnamen den Suffix „ +N weitere" mit
  der korrekten Restanzahl N (Soll: JSX:159; Ist ohne Suffix:
  `CompareTabs.svelte:733`).
  - Test: Playwright — Preset mit 4 Test-Orten anlegen, Suffix-Text „+1
    weitere" auf der Orte-Karte prüfen.

- **AC-4:** Given ein Preset mit mindestens einem konfigurierten Kanal / When
  der Übersicht-Tab gerendert wird / Then zeigt die Layout-SummaryCard als
  Titel die konfigurierten Kanäle als lesbare Labels (via bestehendem
  `channelNamesLabel(preset)`, `CompareTabs.svelte:132`) bzw. „Keine Kanäle"
  wenn kein Kanal konfiguriert ist, und die Copy endet mit „ — Reihenfolge nach
  Priorität." (Soll: JSX:169-171; Ist harte Liste `channels.join(' · ')` +
  Copy ohne Suffix: `CompareTabs.svelte:750-751`).
  - Test: Playwright — Test-Preset mit Email+Telegram, Karten-Titel zeigt
    „Email · Telegram" (nicht die rohen Keys); zweiter Test mit 0 Kanälen zeigt
    „Keine Kanäle"; Copy-Text endet mit „Reihenfolge nach Priorität."

- **AC-5:** Given ein Preset im Status `draft` / When der Übersicht-Tab
  gerendert wird / Then zeigt die Versand-SummaryCard den Titel „Noch nicht
  geplant" und die Copy „Briefing-Uhrzeiten im Tab Versand festlegen." — bei
  jedem anderen Status bleibt die Karte unverändert wie bisher (Soll:
  JSX:175-177; Ist statisch ohne Draft-Fall: `CompareTabs.svelte:759-760` +
  `versandSummaryText` Z.126-128).
  - Test: Playwright — Draft-Test-Preset zeigt „Noch nicht geplant" +
    Festlegen-Copy; aktives Test-Preset zeigt weiterhin Uhrzeiten/„nächster
    Versand"-Copy wie vor der Änderung.

- **AC-6:** Given ein Preset mit gesetztem `profil`-Feld / When der
  Übersicht-Tab gerendert wird / Then zeigt die Wertebereiche-SummaryCard als
  Titel das lesbare Profil-Label via `presetProfileLabel(preset.profil)`
  (`subscriptionHelpers.ts:134`) statt des rohen `preset.profil`-Werts (Soll:
  JSX:163; Ist roh: `CompareTabs.svelte:741`) — ist das Mapping-Ergebnis leer
  (unbekanntes Profil), bleibt der rohe Wert als Fallback stehen statt eines
  leeren Titels.
  - Test: Playwright — Test-Preset mit `profil: 'wandern'` zeigt Karten-Titel
    „Wandern" (nicht „wandern").

- **AC-7:** Given einen mobilen Viewport (<900px) auf dem Übersicht-Tab / When
  der Tab gerendert wird / Then erscheint die Zusammenfassung als EINE Card mit
  4 gestapelten Chevron-Zeilen (Eyebrow klein-mono / Titel / Beschreibung,
  Chevron rechts, ganze Zeile klickbar → springt in den jeweiligen Tab) statt
  des 2×2-Grids: Orte (erste 2 Namen + „+N"), Wertebereiche (Profil-Label,
  „M Metriken · Markierung, kein Score"), Layout (Kanal-Labels bzw. „Keine
  Kanäle", Beschreibung „Übersicht pro Kanal"), Versand (Draft: „Nicht
  geplant"/„Aktivierung offen", sonst Zeiten-Label/„Briefings <Zeiten>") (Soll:
  `screen-compare-detail-mobile.jsx:87-93` + `:276-293`; Eyebrow-Label
  „Wertebereiche" statt CDM-Vorlage „Idealwerte" — bewusster App-Rename aus
  Scheibe #1231-S6, wird NICHT auf „Idealwerte" zurückgesetzt). Desktop behält
  unverändert das bestehende 2×2-Grid.
  - Test: Playwright Mobil-Viewport — 4 Zeilen mit den genannten
    Eyebrow/Titel/Desc-Texten sichtbar (kein 2×2-Grid-Layout mehr); Klick auf
    die „Orte"-Zeile navigiert sichtbar in den Orte-Tab (aktiver Tab wechselt).

- **AC-8:** Given einen mobilen Viewport auf dem Übersicht-Tab / When der
  Monitoring-Status-Stat gerendert wird / Then zeigt er die Kurzform „Läuft
  autom." / „Entwurf" / „Pausiert" (Soll: `screen-compare-detail-mobile.jsx:81`;
  Ist Langform „Läuft automatisch"/„Entwurf · nicht aktiv"/„Pausiert":
  `CompareTabs.svelte:649-653`). Desktop behält die bestehende Langform
  unverändert.
  - Test: Playwright Mobil-Viewport — Status-Stat-Text ist exakt „Läuft
    autom." (aktives Test-Preset) bzw. „Entwurf" (Draft-Test-Preset).

- **AC-9:** Given den Orte-Tab (Desktop und Mobil) / When der Tab geöffnet wird
  / Then zeigt er einen Section-Header „Verglichene Orte" mit Hint (Desktop:
  „Reihenfolge = Spalten im Briefing · ziehen zum Sortieren", Mobil: „ziehen
  zum Sortieren") sowie einen Card-Container um die Ortsliste UND den „Ort
  hinzufügen"-Footer (Soll: JSX:197-216, CDM:110; Ist rahmenlos:
  `CompareTabs.svelte:775-825`) — Drag-Sortierung, Entfernen-Buttons und das
  Add-Panel funktionieren innerhalb des neuen Rahmens unverändert wie zuvor.
  - Test: Playwright — Section-Header/Hint-Text sichtbar; bestehender
    Drag-Sortier-Testpfad (Muster `compare-flow-navigation.spec.ts`) bleibt
    grün; Ort entfernen + „Ort hinzufügen" funktionieren unverändert innerhalb
    des neuen Card-Rahmens.

- **AC-10:** Given die Desktop-Ansicht des Hubs (≥900px) / When die Seite
  gerendert wird / Then zeigt der Breadcrumb genau ZWEI Krümel „Orts-Vergleiche
  / Hub" — der bisherige Extra-Krümel „WORKSPACE · " entfällt (Soll: JSX:66-70;
  Ist drei Krümel: `+page.svelte:144-150`). Die Änderung betrifft
  ausschließlich die Compare-Hub-Seite, keine App-weite Breadcrumb-Änderung.
  - Test: Playwright Desktop-Viewport — Breadcrumb-Container enthält genau 2
    sichtbare Text-Segmente, „WORKSPACE" ist nicht mehr vorhanden.

- **AC-11:** Given die Desktop-Ansicht des Hubs / When die Kontext-Unterzeile
  unter dem Titel gerendert wird / Then zeigt sie das Profil-Label via
  `presetProfileLabel` statt des rohen `preset.profil`-Werts, mit derselben
  Leerfeld-Absicherung wie die bereits existierende Mobile-Unterzeile
  (`+page.svelte:219-221`, kein führendes/doppeltes „ · " bei leerem Profil)
  (Soll: JSX:78-80; Ist roh: `+page.svelte:158-160`).
  - Test: Playwright Desktop-Viewport — Unterzeile zeigt „Wandern" statt
    „wandern" für ein Test-Preset mit `profil: 'wandern'`.

- **AC-12:** Given die mobile Ansicht des Hubs (<900px) / When der Mobile-Header
  gerendert wird / Then zeigt er eine Eyebrow-Zeile „Orts-Vergleich · Hub" über
  dem Preset-Namen (Soll: `screen-compare-detail-mobile.jsx:51`; Ist ohne
  Eyebrow: `+page.svelte:183-222`).
  - Test: Playwright Mobil-Viewport — Text „Orts-Vergleich · Hub" ist im
    Mobile-Header-Bereich sichtbar.

- **AC-13:** Given alle neuen Section-Rahmen aus AC-1, AC-2 und AC-9 / When sie
  implementiert werden / Then nutzen sie ausschließlich den bestehenden,
  geteilten `SectionH`-Atom (Hint über dessen vorhandenes `right`-Snippet,
  `SectionH.svelte:12-26`) — es entsteht KEINE neue Compare-eigene
  Header-Komponente, `SectionH` selbst bleibt unverändert (keine neue Prop),
  der Trip-Hub (`HubOverview`, `TripTabs`) bleibt byte-identisch zum Stand vor
  S8c, und es werden keine PUT-/Fetch-Pfade verändert.
  - Test: Source-Wächter — `git diff` auf `HubOverview.svelte`/`TripTabs.svelte`
    ist leer; `SectionH.svelte` ist unverändert (keine neue Prop im Interface);
    keine neuen `fetch(`/PUT-Aufrufe in den geänderten Dateien.

## Known Limitations

- **(a) Layout-Panel-Kanalliste bleibt hart:** Das Layout-Panel iteriert
  weiterhin über die harte Kanal-Liste `['email','telegram','sms']`
  (`CompareTabs.svelte:470,849`), obwohl JSX:259 nur konfigurierte Kanäle
  zeigt (mit Email-Fallback). Dies ist NICHT Teil der Restliste R2 und bleibt
  bewusst außerhalb des S8c-Scopes — Entscheidung fällt beim
  Null-Lücken-Abschluss-Audit von #1256.
- **(b) Mobile-Orte-Stack, Mobile-Listen-Chrome, Editor-CTAs:** gehören zu
  R4/Scheibe S8d, nicht S8c.
- **(c) Kanal-Verbindungsstatus** (Dot/„verifiziert"/„nicht verbunden" im
  Versand-Tab) = R5, wartet auf separate fachliche Klärung.
- **(d) Mobile-Pencil-Icon → `/edit`-Link im Mobile-Header** (`+page.svelte:198`)
  hängt an S9/KL-1, wird in S8c nicht angefasst.
- **(e) CDM zeigt Mobile-Stats ohne `Dot`-Icon**, der Ist-Zustand behält die
  `Dot`-Icons bei mobilen Stats (z.B. Kanäle-Stat) — dies ist keine in der
  Restliste gelistete Lücke und bleibt unverändert.

## Trip/Compare-Sharing-Begründung

Die Chevron-Zeilen-Zusammenfassung (AC-7) ist als Compare-eigenes Element
zulässig: der Trip-Hub (`HubOverview`) hat keinen mobilen Summary-Stack dieser
Art, es existiert also kein Trip-Pendant, zu dem hier dupliziert würde. Das
Soll ist explizit Compare-spezifisches JSX (`screen-compare-detail-mobile.jsx`,
kein `screen-trip-detail-mobile.jsx`-Äquivalent für diesen Block). Alle
übrigen Bausteine dieser Spec (Section-Header via `SectionH`, Card-Atom,
`CompareLayoutRow.dense`) sind bereits geteilte Bausteine und werden nur
konsumiert, nicht neu gebaut.

## Test Plan

### Automated Tests (TDD RED)

- [ ] AC-1/AC-2: Layout-Tab-Rahmen fehlt (Header/Hint/Pillen/Card) auf beiden
  Viewports — RED, weil `CompareTabs.svelte:847-853` aktuell nur das nackte
  `{#each}` rendert.
- [ ] AC-3: Orte-Karte ohne „+N weitere"-Suffix bei >3 Orten — RED.
- [ ] AC-4: Layout-Karten-Titel zeigt rohe Kanal-Keys statt Labels/„Keine
  Kanäle" — RED.
- [ ] AC-5: Versand-Karte ohne Draft-Sonderfall — RED.
- [ ] AC-6: Wertebereiche-Karten-Titel zeigt rohen `profil`-Wert — RED.
- [ ] AC-7: Mobiles 2×2-Grid statt Chevron-Stack — RED.
- [ ] AC-8: Mobile Status-Stat zeigt Langform statt Kurzform — RED.
- [ ] AC-9: Orte-Tab ohne Section-Rahmen — RED.
- [ ] AC-10: Breadcrumb hat 3 statt 2 Krümel — RED.
- [ ] AC-11: Desktop-Unterzeile zeigt rohes `profil` — RED.
- [ ] AC-12: Mobile-Header ohne Eyebrow — RED.
- [ ] AC-13: Source-Wächter auf Trip-Hub-Byte-Identität + `SectionH`-Interface
  — GREEN von Anfang an (Regressionsschutz, kein Bugfix-Nachweis nötig).

Neue Datei `frontend/e2e/compare-hub-fidelity-s8c.spec.ts` (Playwright,
Staging, verhaltensbenannt nach Namensregel — NICHT `test_issue_1256...`),
Muster: `compare-mobile-vervollstaendigung.spec.ts` (echte Klickpfade statt
`goto()` wo ein Klick gefordert ist, `:visible`-Disambiguierung bei
Desktop+Mobil-Doppel-DOM, eindeutige Testdaten-Namen mit `Date.now()`-Suffix,
`afterEach`-Cleanup). Eigene Staging-Config
`frontend/playwright.1256-s8c.staging.config.ts` nach Muster
`playwright.1256-s8.staging.config.ts`. Ausführung ausschließlich gegen
Staging nach Push+Auto-Deploy — KEINE Mocks, keine lokalen Fixtures für die
E2E-Schicht.

Kern-Schicht (deterministisch, ohne Netz): AC-13 als Source-Wächter (Vitest
oder einfacher Node-Diff-Check) auf `HubOverview.svelte`/`TripTabs.svelte`
Byte-Identität und `SectionH.svelte`-Interface — läuft bei jedem `pytest`/
`vitest`-Durchlauf ohne Staging.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein darstellende Fidelity-Korrektur bestehender Komponenten
  (Markup/Copy/Labels), keine neue Architektur, kein neuer Schreibpfad, keine
  neue Abhängigkeit. Nutzt ausschließlich bereits vorhandene geteilte Bausteine
  (`SectionH`, `Card`, `channelNamesLabel`, `presetProfileLabel`,
  `CompareLayoutRow.dense`).

## Changelog

- 2026-07-14: Initial spec created
