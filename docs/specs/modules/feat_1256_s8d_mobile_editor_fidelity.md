---
entity_id: feat_1256_s8d_mobile_editor_fidelity
type: feature
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [compare, ui-fidelity, design-handoff-4, issue-1256, mobile]
workflow: feat-1256-s8d-mobile-editor-fidelity
---

<!-- Issue #1256, Scheibe S8d (Restliste-Kommentar 2026-07-14, „Restliste = Vertrag").
     Umfasst genau R4 (Mobile-Vervollständigung: Liste + Editor-Orte-Tab +
     kontextuelle CTAs + Profil-Häkchen + TopAppBar-Detail) plus C1
     (Desktop-Editor-create Weiter-CTA-Füße Orte/Wertebereiche/Layout).
     Kanonische Soll-Quellen: `screen-compare-list-mobile.jsx`,
     `screen-compare-editor-mobile.jsx` (Handoff-4, Scratchpad-Pfad im
     Kontext-Artefakt `docs/context/feat-1256-s8d-mobile-editor-fidelity.md`)
     sowie `claude-code-handoff/current/jsx/screen-compare-editor.jsx`
     (Desktop, im Repo). Vorgänger-Scheibe S8c (Hub-Fidelity) verweist in
     ihren Known Limitations (b) explizit hierher. Alle Ist-Referenzen wurden
     gegen den Worktree-Stand vom 2026-07-15 verifiziert (Datei:Zeile-Belege
     in jedem AC). -->

# Issue #1256 — Scheibe S8d: Mobile-Editor-Fidelity (Restliste-Bündel R4 + C1)

## Approval

- [ ] Approved

## Purpose

Die mobile Orts-Vergleich-Liste reflowt heute lediglich den Desktop-Kopf
(32px-Titel, langer Intro-Text, immer sichtbares Suchfeld) statt des im
Design-Handoff-4 vorgesehenen kompakten Mobile-Kopfs. Der mobile Editor
mountet im Orte-Tab unverändert das Desktop-Grid (Smart-Import + Inline-
Bibliothek) statt eines echten Mobile-Stacks, die Floating-CTA ist ein
generisches „Weiter →" ohne Kontext-Label oder Disabled-Feedback, die
Profil-Auswahl hat kein Auswahl-Häkchen, die Metrik-Unterzeile ist
ungekürzt, und die TopAppBar zeigt im Create-Modus einen ausgegrauten statt
eines ausgeblendeten „Aktivieren"-Buttons vor Bereitschaft. Der
Desktop-Editor hat im Create-Modus außerdem nur auf dem Vergleich-Tab einen
Weiter-CTA-Fuß — Orte, Wertebereiche und Layout fehlen. S8d formalisiert
diese Abweichungen als Acceptance Criteria und behebt sie — ohne neue
Schreibpfade, ohne Änderung an den geteilten Organismen
(CorridorEditor/CorridorEditorMobile/LayoutTab/VersandTab/TripTabs).

## Source

- **File:** `frontend/src/routes/compare/+page.svelte` (Mobile-Kopf,
  Suchfeld, Stats, Content-Padding)
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte`
  (mobiler CTA, TopAppBar-Detail, Profil-Liste, mobiler Orte-Tab-Mount,
  Desktop-Editor-CTA-Füße Orte/Idealwerte/Layout)
- **File:** `frontend/src/lib/components/compare/steps/Step2Orte.svelte`
  (mobiler Stack als `dense`-Variante des Orte-Tabs)
- **File:** `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` +
  `frontend/src/routes/+layout.svelte` (Design-Kopfleiste: additiver
  `title`-/Back-/Aktions-Support nach `mobile-shell.jsx:87-114`, pro Seite
  befüllbar — PO-Regel 2026-07-15: Design-Komponenten verwenden, nicht
  nachbauen)
- **Identifier:** `<script>`-Block + Markup der o.g. Svelte-Komponenten
  (kein neues Modul außer einem kleinen Befüllungs-Store, keine neue Route)

> **Schicht-Hinweis:** reine Frontend-/User-UI-Änderung (`frontend/src/...`,
> SvelteKit). Kein Go-API-, kein Python-Core-Anteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `unlockedTabs`/`doneTabs` (`compareEditorLogic.ts:22,32`) | function | Lock-/Done-Sets — Quelle für alle CTA-Disabled-Bedingungen (Desktop wie Mobil), unverändert |
| `TAB_ORDER` (`compareEditorLogic.ts:8`) | constant | Tab-Reihenfolge für `handleMobileNext()` und die neuen Desktop-CTA-Sprünge |
| `groupLocations()` (`locationHelpers.ts`) | function | Bibliotheks-Gruppierung — von Step2Orte UND dem mobilen Sheet in CompareEditor bereits genutzt, für die `dense`-Variante wiederverwendet, nicht dupliziert |
| `dense`-Prop-Muster (`LayoutTab.svelte:22,33`, `layout-tab.dense`-CSS Z.66) | pattern | Bestehendes Kompakt-Variant-Muster für geteilte Tab-Organismen — Vorlage für die neue `dense`-Prop auf Step2Orte |
| `profileMetricsLabel()` (`CompareEditor.svelte:249-252`) | function | Profil→Metriken-Label — Desktop bleibt ungekürzt (Vorlage-Z.180), mobil braucht eine 4-Einträge-gekürzte Variante zusätzlich zur bestehenden Funktion (keine Änderung an der bestehenden Funktion selbst, da Desktop sie unverändert nutzt) |
| `isMobileViewport` (CompareEditor.svelte:79-83) | state | Bestehende Ein-Mount-Weiche (matchMedia 899px) — steuert bereits `CorridorEditor`/`CorridorEditorMobile` und wird für die Step2Orte-`dense`-Weiche wiederverwendet |
| `MBtn`, `Btn`, `Sheet` (Atoms/Molecules) | component | Bereits im Editor genutzte Bausteine — keine neue Komponente |
| `TopAppBar` (`ui/sidebar/TopAppBar.svelte`, kanonisch per #373 aus `mobile-shell.jsx` konsolidiert) | component | Die Design-Kopfleiste. Hat bereits `eyebrow`/`leftIcon`/`right`/`dense`/`scrolled`-Props, wird vom Layout aber nie parametrisiert; `title` (mobile-shell.jsx:87,105-109) fehlt noch und wird ADDITIV ergänzt (#373-Methode: Default = bisheriges Wordmark-Verhalten, keine andere Seite ändert sich) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | MODIFY | Additiver `title`-Prop (mobile-shell.jsx:105-109) + Back-Variante für `leftIcon` + Verhalten „seiten-eigene rechte Aktion ersetzt die Default-Bell/Plus-Gruppe"; Default (ohne Befüllung) = exakt heutiges Erscheinungsbild auf allen Seiten |
| `frontend/src/routes/+layout.svelte` + kleines Befüllungs-Modul (CREATE, z.B. `$lib/stores/topAppBar`) | MODIFY/CREATE | Seiten können title/eyebrow/leftIcon/rechte Aktion der globalen Design-Kopfleiste setzen (Reset bei Navigation); Mechanismus wiederverwendbar für Trip-Seiten (Konvergenz #1230) |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | Mobil: befüllt die Design-Kopfleiste (title „Orts-Vergleiche", eyebrow „Workspace · N", rechts Plus→`/compare/new`); Desktop-Kopf nur noch ≥900px; kurzer mobiler Intro, Suchfeld mobil entfernt (Desktop bleibt), Stats mobil `size="sm"`, mobiles Content-Padding |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Nachgebaute `cm-mobile-appbar` ENTFÄLLT — der mobile Editor befüllt die globale Design-Kopfleiste (title=Tab-Titel, eyebrow=Name/„Neuer Vergleich", leftIcon=back→`/compare`, rechts Speichern bzw. „…"/„Aktivieren"); mobiler Floating-CTA kontextuell (Label + Disabled-Feedback je Tab, kein CTA auf Versand), mobile Profil-Liste mit Häkchen + gekürzter Metrik-Zeile, mobiler Orte-Tab mountet Step2Orte mit `dense`, Desktop-Editor-CTA-Füße für Orte/Idealwerte/Layout im `.cm-desktop`-Zweig |
| `frontend/e2e/issue-682-compare-editor-mobile.spec.ts` | MODIFY | Selektoren `cm-mobile-appbar`/`cm-mobile-save`/`cm-mobile-activate` auf die Design-Kopfleiste migrieren (`top-app-bar`-basierte testids); übrige Selektoren unverändert. (`compare-mobile-vervollstaendigung.spec.ts` referenziert nur das unveränderte `cm-mobile-cta` — Prüfung ergab: keine Migration nötig; Korrektur der ursprünglichen Scope-Annahme, Adversary-F002) |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | MODIFY | Neue `dense`-Prop: mobiler 1-spaltiger Stack (Kopfzeile „Im Vergleich · N" + Badge, nummerierte Karten mit ✕, dashed „Bibliothek"-Button öffnet weiterhin das bestehende `mobileLibraryOpen`-Sheet aus CompareEditor) statt Desktop-2-Spalten-Grid (Smart-Import + Inline-Bibliothek) |
| `frontend/e2e/compare-editor-fidelity-s8d.spec.ts` | CREATE | Playwright-Staging-Wächter (Desktop 1280px + Mobil 390px) |
| `frontend/playwright.1256-s8d.staging.config.ts` | CREATE | Staging-Config nach Muster `playwright.1256-s8c.staging.config.ts` |

### Estimated Changes

- Files: 9 (6 modify, 3 create)
- LoC: ~+470/-140 (Quell-Code: `TopAppBar.svelte` ~+45, Befüllungs-Modul
  ~+40, `+layout.svelte` ~+15, `+page.svelte` ~+45/-15, `CompareEditor.svelte`
  ~+180/-90 [CTA-Blöcke, Profil-Häkchen, gekürzte Metrik-Zeile,
  `dense`-Übergabe; nachgebaute `cm-mobile-appbar` entfällt],
  `Step2Orte.svelte` ~+110/-15; Suiten-Migration ~+35; neue Test+Config
  ~+160) — deutlich über dem 250-LoC-Budget.
  **PO-Entscheid 2026-07-15 (AskUserQuestion): eine Scheibe (A+B+C),
  `loc_limit_override 500` genehmigt und im Workflow-State gesetzt.**
  Reißt die Umsetzung die 500, wird der PO gefragt — kein eigenmächtiges
  Anheben.
- Effort: high

## Implementation Details

**Kopfleiste (PO-Regel 2026-07-15 — Design-Komponenten verwenden, nichts
nachbauen):** Die kanonische Design-Kopfleiste `ui/sidebar/TopAppBar.svelte`
(per #373 aus `mobile-shell.jsx` konsolidiert, eyebrow/leftIcon/right/dense/
scrolled bereits vorhanden) bekommt additiv den noch fehlenden `title`-Prop
(mobile-shell.jsx:105-109), eine Back-Variante des linken Icons und die
Regel „seiten-eigene rechte Aktion ersetzt Default-Bell/Plus". Ein kleines
Befüllungs-Modul (Store/Context, Reset bei Navigation) lässt Seiten diese
Props setzen; `+layout.svelte` reicht sie an die EINE globale Instanz
durch. Ohne Befüllung rendert die Leiste exakt wie heute (Wordmark +
Bell + Plus→/trips/new) — keine fremde Seite ändert sich. KEIN in-page
nachgebauter Kopf; die bestehende nachgebaute `cm-mobile-appbar` im
CompareEditor (Z.1122-1156) wird durch die Befüllung derselben globalen
Komponente ERSETZT (behebt nebenbei die heutige Doppel-Leiste: Wordmark-Bar
+ Editor-Bar übereinander, die das JSX-Soll nicht kennt).

**A (Liste):** `compare/+page.svelte` befüllt mobil die Design-Kopfleiste
(title „Orts-Vergleiche", eyebrow „Workspace · N", rechts Plus→
`/compare/new`). Für Intro, Suchfeld, Stats und Content-Padding erhält die
Datei `desktop:hidden`/`hidden desktop:block`-Zweige — dieselbe
Weichen-Technik, die sie bereits für Kachel-Stack (Z.71-83) vs. Desktop-Grid
(Z.86-94) nutzt. Das Suchfeld wird im mobilen Zweig ersatzlos weggelassen
(Handoff-5-P3), im Desktop-Zweig unverändert beibehalten.

**B (mobiler Editor):** Step2Orte bekommt eine `dense?: boolean = false`-Prop
nach dem etablierten Muster von `LayoutTab.svelte` — EIN Code, kein zweiter
Orte-Stack im `.cm-mobile`-Zweig von CompareEditor (Designentscheidung 2 aus
dem Kontext-Dokument). Bei `dense` wird kein Smart-Import-Panel und keine
Inline-Bibliothek gerendert, nur die Picked-Liste + der bestehende
„Bibliothek wählen"-Button, der weiterhin das bereits vorhandene
`mobileLibraryOpen`-Sheet in `CompareEditor.svelte` öffnet (Sheet selbst
unverändert). Die Floating-CTA (`cm-mobile-cta`, Z.1269-1277) wird von einem
statischen Label auf eine pro-Tab abgeleitete Funktion umgestellt, die
dieselben `unlockedTabs`/`doneTabs`-Bedingungen liest wie
`compareEditorLogic.ts` bereits für die Tab-Freischaltung nutzt — keine neue
Datenquelle. Auf dem Versand-Tab wird der `cm-mobile-cta`-Wrapper nicht
gerendert (Aktivieren sitzt ausschließlich in der App-Bar, s. AC-15 und
Known Limitations (b)).

**C (Desktop-Editor create):** Die drei neuen CTA-Füße für Orte, Idealwerte
und Layout leben als zusätzliche Markup-Blöcke im `.cm-desktop`-Zweig von
`CompareEditor.svelte`, direkt nach dem jeweiligen `{:else if activeTab === …}`-
Mount-Punkt (Z.1075 Orte, Z.1076-1084 Idealwerte, Z.1085-1086 Layout) — als
Wrapper UM `Step2Orte`/`CorridorEditor`/`ltLayoutSection()`, niemals in den
Organismen selbst (C0-Invariante, Designentscheidung 3). Muster identisch zum
bereits bestehenden Vergleich-Tab-CTA (Z.1045-1071,
`compare-editor-continue-orte`), jeweils `{#if !isEdit}`-gegated.

## Expected Behavior

- **Input:** Bestehende Wizard-/Preset-Daten (`wiz.name`, `wiz.pickedIds`,
  `wiz.activityProfile` etc.) wie bisher über den Compare-Wizard-State.
- **Output:** Identische Daten, aber mit den in den Acceptance Criteria
  beschriebenen Layouts/Labels/Disabled-Zuständen gerendert — auf beiden
  Viewports (Desktop ≥900px, Mobil <900px via bestehendem
  `isMobileViewport`/`desktop:hidden`).
- **Side effects:** keine. Keine neuen Fetches, keine neuen PUT-Aufrufe,
  keine Änderung an `hubPutQueue` oder anderen Schreibpfaden. Keine
  Änderung an `CorridorEditor`, `CorridorEditorMobile`, `LayoutTab`,
  `VersandTab` oder `TripTabs`.

## Acceptance Criteria

### Gruppe A — Mobile-Liste (`compare/+page.svelte`)

- **AC-1:** Given die Orts-Vergleich-Liste auf einem mobilen Viewport
  (<900px) / When die Seite geladen wird / Then zeigt die obere App-Leiste
  der Seite den Titel „Orts-Vergleiche" mit Eyebrow-Zeile „Workspace · N"
  (N = Anzahl Vergleiche) und rechts ein Plus-Tap-Ziel (mindestens 44×44px),
  das einen neuen VERGLEICH anlegt — statt des heutigen Zustands
  (App-Leiste mit Schriftzug + Plus, das „Neuer Trip" öffnet, und darunter
  der reflowte Desktop-Kopf mit 32px-Titel + langem Fließtext) (Soll: JSX-M
  Z.22 `MobileShell title/eyebrow/right`; Ist: `+layout.svelte:70` ohne
  Befüllung + `+page.svelte:35-47` ohne mobile Weiche). Auf allen anderen
  Seiten (z.B. `/trips`) und am Desktop (≥900px) bleibt alles unverändert.
  - Test: Playwright Mobil-Viewport (390px) — App-Leiste zeigt Titel-Text
    „Orts-Vergleiche" und Eyebrow mit „Workspace ·"; Tap auf das Plus-Ziel
    navigiert nach `/compare/new`; auf `/trips` (mobil) zeigt die App-Leiste
    weiterhin den Schriftzug wie bisher; Desktop-Viewport auf `/compare`
    zeigt weiterhin den bisherigen 32px-Titel unverändert.

- **AC-2:** Given den mobilen Kopf aus AC-1 / When er gerendert wird / Then
  zeigt er den kurzen Intro-Text „Stehende Monitore: dieselben Orte im
  Blick. Briefings wie beim Trip — morgens für heute, abends für morgen.
  Ohne Ranking — läuft, bis du stoppst." statt des langen Desktop-Fließtexts
  (Soll: JSX-M Z.27-30; Ist: der lange Desktop-Text wird aktuell 1:1
  mobil mit reflowt, `+page.svelte:39-44`).
  - Test: Playwright Mobil-Viewport — der kurze Intro-Satz ist sichtbar,
    der lange Desktop-Satz („Morgen-Briefing für heute, Abend-Briefing für
    morgen, zur gewählten Uhrzeit…") ist NICHT sichtbar.

- **AC-3:** Given die Liste auf einem mobilen Viewport / When sie gerendert
  wird / Then ist KEIN Suchfeld sichtbar (Handoff-5-P3, ersatzlose
  Entfernung mobil) — auf einem Desktop-Viewport (≥900px) bleibt das
  Suchfeld unverändert vorhanden und funktioniert wie bisher (Ist ohne
  Viewport-Weiche: `+page.svelte:50-61`, Kommentar „Suche immer sichtbar
  (Issue #582)" ist durch Handoff-5-P3 für Mobil überstimmt).
  - Test: Playwright Mobil-Viewport — Such-Input ist nicht vorhanden/nicht
    sichtbar; Playwright Desktop-Viewport — Such-Input ist sichtbar und
    filtert die Liste beim Tippen wie vor der Änderung.

- **AC-4:** Given die Liste auf einem mobilen Viewport / When die
  Stats-Zeile (Aktiv/Pausiert/Drafts) gerendert wird / Then erscheint sie in
  der kompakten `size="sm"`-Darstellung (Soll: JSX-M Z.42-44; Ist ohne
  Größenvariante: `+page.svelte:65-67`). Die Desktop-Ansicht behält die
  bisherige Standardgröße unverändert.
  - Test: Playwright Mobil-Viewport — Stats-Werte sichtbar, kompaktere
    Darstellung (kleinere Schriftgröße/Höhe als Desktop-Viewport im
    Vergleichs-Snapshot).

- **AC-5:** Given die Liste auf einem mobilen Viewport / When der
  Kachel-Stack gerendert wird / Then ist das umgebende Content-Padding
  kompakt (Soll: JSX-M Z.24 „12px 16px 24px") statt des für Desktop
  gedachten `32px 40px 60px` (Ist: `+page.svelte:34`, gilt aktuell für
  beide Viewports identisch) — es entsteht dabei kein doppeltes
  horizontales Padding durch das umgebende Layout (`+layout.svelte`
  `px-4`-Klasse auf `<main>`, bekannte Falle aus Scheibe S8).
  - Test: Playwright Mobil-Viewport — gemessener linker/rechter Abstand des
    ersten Kachel-Elements zum Viewport-Rand liegt im erwarteten kompakten
    Bereich (kein doppeltes Padding, kein Overflow).

### Gruppe B — Mobiler Editor (`.cm-mobile`-Zweig + Step2Orte)

- **AC-6:** Given den Orte-Tab des mobilen Editors (`/compare/new`, Name
  gesetzt) / When der Tab geöffnet wird / Then zeigt er einen 1-spaltigen
  Stack: Kopfzeile „Im Vergleich · N" mit Status-Badge („min. 2" bei <2
  Orten, „viel — Empf. 3–5" bei >5 Orten, sonst „passt"), darunter
  nummerierte Orts-Karten mit Entfernen-Button (✕) je Ort, und darunter ein
  gestrichelter „Ort aus Bibliothek wählen"-Button, der das bestehende
  Bibliotheks-Sheet öffnet (Soll: JSX-M Z.226-266; Ist: Desktop-2-Spalten-
  Grid wird unverändert mobil gemountet, `CompareEditor.svelte:1235` +
  `Step2Orte.svelte:193-357`).
  - Test: Playwright Mobil-Viewport — Kopfzeile-Text „Im Vergleich ·"
    sichtbar, Badge-Text je nach Testdaten-Anzahl korrekt, nummerierte
    Karten (1, 2, …) sichtbar, Klick auf ✕ entfernt einen Ort aus der
    Liste, Klick auf den gestrichelten Button öffnet das Bibliotheks-Sheet
    (bestehender Testpfad aus `issue-682-compare-editor-mobile.spec.ts`
    bleibt grün).

- **AC-7:** Given denselben mobilen Orte-Tab / When er gerendert wird /
  Then enthält er WEDER das Smart-Import-Panel (URL/Koordinaten-Eingabe)
  NOCH die dreispaltige Inline-Bibliothek — beide sind auf Desktop
  unverändert vorhanden (Soll: JSX-M hat keine dieser Elemente im mobilen
  Orte-Tab; Ist: `Step2Orte.svelte:196-274` [Smart-Import] und
  `:319-356` [Inline-Bibliothek] werden aktuell auch mobil mitgerendert).
  - Test: Playwright Mobil-Viewport — Smart-Import-Input
    (`compare-step2-smart-import-input`) und Inline-Bibliotheks-Grid
    (`compare-step2-library`) sind nicht sichtbar; Playwright
    Desktop-Viewport — beide bleiben unverändert sichtbar und funktional.

- **AC-8:** Given den Vergleich-Tab des mobilen Editors im Create-Modus /
  When die Floating-CTA gerendert wird / Then zeigt sie „Orte hinzufügen →"
  (aktiv, primary) sobald ein Name eingetragen ist, sonst „Name eingeben"
  (deaktiviert: kein Klick-Effekt, reduzierte Deckkraft) (Soll: JSX-M
  Z.200-207; Ist: generisches „Weiter →", immer primary, kein
  Disabled-Feedback: `CompareEditor.svelte:1269-1277`).
  - Test: Playwright Mobil-Viewport — mit leerem Namen zeigt die CTA „Name
    eingeben" und ein Klick verändert den aktiven Tab nicht; nach Eingabe
    eines Namens zeigt die CTA „Orte hinzufügen →" und ein Klick wechselt
    sichtbar in den Orte-Tab.

- **AC-9:** Given den Orte-Tab des mobilen Editors im Create-Modus / When
  die Floating-CTA gerendert wird / Then zeigt sie „Idealwerte festlegen →"
  (aktiv) sobald mindestens 2 Orte gewählt sind, sonst „noch N Ort(e) nötig"
  mit der korrekten Restanzahl N (deaktiviert) (Soll: JSX-M Z.269-277; Ist
  generisch s. AC-8).
  - Test: Playwright Mobil-Viewport — mit 1 gewähltem Ort zeigt die CTA
    „noch 1 Ort nötig" und ist nicht klickbar; nach Hinzufügen eines
    zweiten Orts zeigt sie „Idealwerte festlegen →" und ein Klick wechselt
    sichtbar in den Wertebereiche-Tab.

- **AC-10:** Given den Wertebereiche-Tab des mobilen Editors im
  Create-Modus / When die Floating-CTA gerendert wird / Then zeigt sie
  „Layout einrichten →" (immer aktiv, da der Tab erst nach Erreichen der
  2-Orte-Bedingung erreichbar ist) statt des generischen „Weiter →" (Soll:
  JSX-M Z.323-327; Ist generisch s. AC-8).
  - Test: Playwright Mobil-Viewport — auf dem Wertebereiche-Tab zeigt die
    CTA „Layout einrichten →"; Klick wechselt sichtbar in den Layout-Tab.

- **AC-11:** Given den Layout-Tab des mobilen Editors im Create-Modus / When
  die Floating-CTA gerendert wird / Then zeigt sie „Versand einrichten →"
  statt des generischen „Weiter →" (Soll: JSX-M Z.337-341; Ist generisch
  s. AC-8).
  - Test: Playwright Mobil-Viewport — auf dem Layout-Tab zeigt die CTA
    „Versand einrichten →"; Klick wechselt sichtbar in den Versand-Tab.

- **AC-12 (PO-Entscheidungspunkt, s. Known Limitations (b)):** Given den
  Versand-Tab des mobilen Editors im Create-Modus / When der Tab geöffnet
  wird / Then ist KEIN Boden-Floating-CTA sichtbar — „Aktivieren" ist
  ausschließlich über den App-Bar-Button (AC-15) sowie die
  Aktivierungs-Karte innerhalb des Versand-Tabs erreichbar (Soll: JSX-M hat
  in `CEM_VersandTab` keinen Floating-CTA-Block; Ist zeigt aktuell dieselbe
  Floating-CTA mit Label „Aktivieren": `CompareEditor.svelte:1274`). Dies
  ist eine Verhaltensänderung gegenüber dem bisherigen S8-AC-24
  („floating CTA unverändert sichtbar auf allen Tabs") — Freigabe explizit
  Teil des Spec-go.
  - Test: Playwright Mobil-Viewport — auf dem Versand-Tab ist
    `[data-testid="cm-mobile-cta"]` nicht vorhanden/nicht sichtbar; die
    bestehenden Tests auf anderen Tabs (`compare-mobile-vervollstaendigung.
    spec.ts` AC-24, `issue-682-compare-editor-mobile.spec.ts` AC-4a) bleiben
    unverändert grün, da sie den Vergleich-Tab prüfen.

- **AC-13:** Given die Profil-Auswahl im mobilen Vergleich-Tab / When ein
  Profil ausgewählt ist / Then zeigt die zugehörige Karte ein
  Accent-farbenes Auswahl-Häkchen (Kreis mit Check-Symbol) rechts in der
  Karte (Soll: JSX-M Z.190-194; Ist ohne Häkchen:
  `CompareEditor.svelte:1219-1233`).
  - Test: Playwright Mobil-Viewport — nach Auswahl eines
    Aktivitätsprofils ist ein Check-Icon/Häkchen-Element innerhalb der
    ausgewählten Profil-Karte sichtbar, bei den nicht gewählten Karten
    nicht.

- **AC-14:** Given dieselbe Profil-Auswahl / When die Metrik-Unterzeile
  einer Profil-Karte gerendert wird / Then zeigt sie höchstens 4
  Metrik-Labels, gefolgt von „…" falls das Profil mehr als 4 Metriken hat
  (Soll: JSX-M Z.186-188 `slice(0, 4).join(" · ")` + `" …"`; Ist ungekürzt:
  `CompareEditor.svelte:1228`, nutzt `profileMetricsLabel()` ohne Kürzung).
  Die Desktop-Ansicht bleibt unverändert ungekürzt (JSX Z.180).
  - Test: Playwright Mobil-Viewport — für ein Testprofil mit >4 Metriken
    endet die Unterzeile sichtbar mit „…" und enthält höchstens 4
    Metrik-Namen getrennt durch „ · "; Desktop-Viewport zeigt weiterhin
    alle Metriken des Profils.

- **AC-15:** Given den mobilen Editor (`/compare/new` bzw.
  `/compare/{id}/edit`) / When die Seite gerendert wird / Then gibt es
  GENAU EINE obere App-Leiste (nicht wie heute zwei übereinander:
  Schriftzug-Leiste + Editor-Kopfzeile), und sie zeigt: links ein
  Zurück-Tap-Ziel nach `/compare`, als Titel den aktiven Tab-Namen, als
  Eyebrow den Vergleichs-Namen (bzw. „Neuer Vergleich"), rechts im
  Create-Modus „…" solange der Versand-Tab noch nicht besucht wurde und
  „Aktivieren" danach, im Edit-Modus „Speichern" (Soll: JSX-M Z.419-448
  `TopAppBar title/eyebrow/leftIcon="back"/right`; Ist: nachgebaute zweite
  Leiste `CompareEditor.svelte:1122-1156`, rechter Button immer
  „Aktivieren", nur farblich ausgegraut).
  - Test: Playwright Mobil-Viewport — auf `/compare/new` existiert genau
    eine sichtbare App-Leiste; sie zeigt direkt nach dem Laden rechts „…";
    nach Durchklicken bis zum Versand-Tab zeigt sie „Aktivieren"; Tap auf
    das Zurück-Ziel navigiert nach `/compare`; der Titel wechselt beim
    Tab-Wechsel sichtbar mit (z.B. „Vergleich" → „Orte").

### Gruppe C — Desktop-Editor create (`CompareEditor.svelte`, `.cm-desktop`)

- **AC-16:** Given den Orte-Tab des Desktop-Editors im Create-Modus (<2
  Orte gewählt) / When der Tab-Fuß gerendert wird / Then zeigt er den
  Hinweis „⊘ min. 2 Orte auswählen" neben einem deaktivierten
  „Idealwerte festlegen →"-Button; ab 2 gewählten Orten ist der Hinweis weg
  und der Button aktiv (Soll: JSX Z.298-307; Ist: kein Tab-Fuß auf dem
  Orte-Tab vorhanden, `CompareEditor.svelte:1075`).
  - Test: Playwright Desktop-Viewport — mit 1 gewähltem Ort ist der
    ⊘-Hinweis sichtbar und der Button nicht klickbar; nach Hinzufügen eines
    zweiten Orts verschwindet der Hinweis, Klick auf den Button wechselt
    sichtbar in den Wertebereiche-Tab.

- **AC-17:** Given den Wertebereiche-Tab des Desktop-Editors im
  Create-Modus / When der Tab-Fuß gerendert wird / Then zeigt er einen
  „Layout einrichten →"-Button (Soll: JSX Z.322-328; Ist: kein Tab-Fuß
  vorhanden, `CompareEditor.svelte:1076-1084`).
  - Test: Playwright Desktop-Viewport — auf dem Wertebereiche-Tab ist der
    Button „Layout einrichten →" sichtbar; Klick wechselt sichtbar in den
    Layout-Tab.

- **AC-18:** Given den Layout-Tab des Desktop-Editors im Create-Modus /
  When der Tab-Fuß gerendert wird / Then zeigt er einen
  „Versand einrichten →"-Button (Soll: JSX Z.338-344; Ist: kein Tab-Fuß
  vorhanden, `CompareEditor.svelte:1085-1086`).
  - Test: Playwright Desktop-Viewport — auf dem Layout-Tab ist der Button
    „Versand einrichten →" sichtbar; Klick wechselt sichtbar in den
    Versand-Tab.

- **AC-19:** Given einen bestehenden Vergleich im Bearbeiten-Modus
  (`/compare/{id}/edit`, Desktop) / When die Tabs Orte, Wertebereiche oder
  Layout geöffnet werden / Then ist KEINER der in AC-16/AC-17/AC-18 neu
  eingeführten Tab-Füße sichtbar — identisch zum bereits bestehenden
  Verhalten des Vergleich-Tab-CTA, der ebenfalls nur im Create-Modus
  erscheint (`compare-editor-continue-orte`, `{#if !isEdit}`,
  `CompareEditor.svelte:1059`).
  - Test: Playwright Desktop-Viewport, Edit-Modus — auf allen vier Tabs
    (Vergleich/Orte/Wertebereiche/Layout) ist kein „→"-Weiter-CTA-Fuß
    sichtbar.

### Invariante

- **AC-20:** Given alle Änderungen aus S8d / When sie implementiert sind /
  Then bleiben `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`,
  `LayoutTab.svelte`, `VersandTab.svelte` und `TripTabs.svelte`
  byte-identisch zum Stand vor S8d (die neuen CTA-Wrapper liegen
  ausschließlich in `CompareEditor.svelte` UM diese Organismen, s. C0-
  Invariante). Die `data-testid`-Werte `cm-mobile-cta`,
  `compare-step2-mobile-library-btn` sowie `cm-mobile-tab-{id}` bleiben im
  DOM erhalten; die testids der entfallenden nachgebauten Editor-Kopfzeile
  (`cm-mobile-appbar`, `cm-mobile-save`, `cm-mobile-activate`) werden durch
  Pendants an der geteilten Design-Kopfleiste ersetzt, und die beiden
  bestehenden Wächter-Suiten (`compare-mobile-vervollstaendigung.spec.ts`,
  `issue-682-compare-editor-mobile.spec.ts`) werden in DERSELBEN Scheibe
  darauf migriert und laufen grün.
  - Test: Source-Wächter — `git diff` auf die fünf genannten Organismus-
    Dateien ist leer; Grep auf `cm-mobile-cta`, `cm-mobile-tab-`,
    `compare-step2-mobile-library-btn` in `CompareEditor.svelte`/
    `Step2Orte.svelte` findet weiterhin alle Treffer; beide migrierten
    Suiten laufen grün gegen Staging (gleicher Lauf wie die neue
    S8d-Suite).

## Known Limitations

- **(a) Kopfleiste = die vorhandene Design-Komponente, per Befüllung:**
  Liste und Editor verwenden die EINE globale `TopAppBar` (kanonische
  Design-Komponente aus #373/`mobile-shell.jsx`) und befüllen sie pro Seite
  mit title/eyebrow/leftIcon/rechter Aktion — fehlende Fähigkeiten werden
  der Komponente ADDITIV ergänzt (PO-Regel 2026-07-15: Design-Elemente
  verwenden und anpassen, nichts nachbauen). Das `MobileShell`-TEMPLATE
  wird nicht pro Seite gemountet, weil das Layout TopAppBar + BottomNav
  bereits global mountet — es werden also die Design-ELEMENTE verwendet,
  nur ihre Montage folgt der bestehenden Layout-Architektur. Auf nicht
  befüllten Seiten zeigt die Leiste unverändert den Wordmark-Default.
- **(b) Mobiler Versand-Tab verliert den Boden-CTA im Create-Modus:** s.
  AC-12 — dies weicht vom bisherigen S8-AC-24 ab. **PO-Entscheid 2026-07-15
  (AskUserQuestion): AC-12 wie spezifiziert freigegeben** — der untere Knopf
  entfällt, Aktivieren nur über App-Bar + Aktivierungs-Karte (1:1 JSX).
- **(c) `handleMobileNext()` (`CompareEditor.svelte:438-445`) bleibt
  strukturell erhalten** (Tab-Sprung + `handleActivate()` auf Versand) —
  S8d ändert nur Label/Disabled-Darstellung, nicht die Sprunglogik selbst.

## Out of Scope

- **R5 (Kanal-Verbindungsstatus)** im Versand-Tab (Dot/„verifiziert"/„nicht
  verbunden") — wartet auf separate fachliche Klärung, nicht Teil von S8d.
- **S9 /edit-Redirect** (Mobile-Pencil-Icon → `/edit`-Link im Mobile-Header
  der Hub-Seite, KL-1 aus S8c) — wird in S8d nicht angefasst.
- **Alarme-Tab** (#1258) — bleibt unangetastet; die CTA-Kette im Create-
  Modus bleibt vergleich→orte→idealwerte→layout→versand, Alarme bleibt im
  Create-Modus weiterhin gesperrt (Bestand, `CompareEditor.svelte:1177`).
- **Desktop-Suchfeld auf `/compare`** bleibt unverändert bestehen (AC-3
  betrifft ausschließlich die mobile Ansicht).
- **Geteilte Organismen** (`CorridorEditor`, `CorridorEditorMobile`,
  `LayoutTab`, `VersandTab`, `TripTabs`) = 0 Zeilen Diff — s. AC-20. Alle
  neuen CTAs leben ausschließlich im `CompareEditor`-Rahmen.

## Trip/Compare-Sharing-Begründung

Die neue `dense`-Prop auf `Step2Orte.svelte` (AC-6/AC-7) folgt exakt dem
bereits etablierten Muster von `LayoutTab.svelte` (`dense`-Prop,
`layout-tab.dense`-CSS) — kein neues Konzept, sondern Konsolidierung auf
einen bestehenden Baustil. Der Orte-Tab selbst ist eine erlaubte
Compare-Eigenheit (kein Trip-Pendant, s. CLAUDE.md „Trip/Ortsvergleich-
Code-Teilung"), daher ist eine Compare-eigene `dense`-Variante hier
zulässig und dupliziert nichts. Die vier neuen Floating-/Fuß-CTAs (Gruppe B
und C) sind ausschließlich Wrapper-Markup im geteilten Editor-Rahmen
(`CompareEditor.svelte`), nicht in den geteilten Organismen selbst — die
Lock-Engine (`unlockedTabs`/`doneTabs`) bleibt die einzige Quelle für
Freischaltungs-/Bereitschafts-Zustände, identisch zum Trip-Editor-Muster.
`TripTabs.svelte` bleibt dadurch byte-identisch (AC-20).

## Test Plan

### Automated Tests (TDD RED)

- [ ] AC-1 bis AC-5: Mobile-Kopf/Suchfeld/Stats/Padding fehlen — RED, da
  `+page.svelte` aktuell keine Viewport-Weiche für diese Blöcke hat.
- [ ] AC-6/AC-7: mobiler Orte-Tab mountet unverändert das Desktop-Grid —
  RED, da `Step2Orte.svelte` keine `dense`-Prop kennt.
- [ ] AC-8 bis AC-12: Floating-CTA zeigt generisches „Weiter →"/„Aktivieren"
  ohne Kontext-Label oder Disabled-Feedback, Versand-Tab zeigt weiterhin
  einen Boden-CTA — RED.
- [ ] AC-13/AC-14: Profil-Liste ohne Häkchen, Metrik-Zeile ungekürzt — RED.
- [ ] AC-15: App-Bar zeigt immer „Aktivieren" (nur ausgegraut) statt „…" —
  RED.
- [ ] AC-16 bis AC-18: Desktop-Editor hat auf Orte/Wertebereiche/Layout
  keinen Tab-Fuß-CTA — RED.
- [ ] AC-19: GREEN von Anfang an (Edit-Modus zeigt bereits heute keine
  Create-CTAs — Regressionsschutz für die neuen CTAs).
- [ ] AC-20: GREEN von Anfang an (Source-Wächter/Regressionsschutz, kein
  Bugfix-Nachweis nötig).

Neue Datei `frontend/e2e/compare-editor-fidelity-s8d.spec.ts` (Playwright,
Staging, verhaltensbenannt nach Namensregel — NICHT `test_issue_1256...`),
Muster: `compare-mobile-vervollstaendigung.spec.ts` /
`issue-682-compare-editor-mobile.spec.ts` (echte Klickpfade statt `goto()`
wo ein Klick gefordert ist, `:visible`-Disambiguierung bei Desktop+Mobil-
Doppel-DOM, eindeutige Testdaten-Namen mit `Date.now()`-Suffix,
`afterEach`-Cleanup). Eigene Staging-Config
`frontend/playwright.1256-s8d.staging.config.ts` nach Muster
`playwright.1256-s8c.staging.config.ts`. Ausführung ausschließlich gegen
Staging nach Push+Auto-Deploy — KEINE Mocks, keine lokalen Fixtures für die
E2E-Schicht.

Kern-Schicht (deterministisch, ohne Netz): AC-20 als Source-Wächter
(einfacher Node-Diff-Check oder Vitest) auf Byte-Identität der fünf
Organismus-Dateien und Presenz der genannten `data-testid`-Strings — läuft
bei jedem `vitest`-Durchlauf ohne Staging.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein darstellende Fidelity-Korrektur bestehender
  Komponenten (Markup/Copy/Labels/Disabled-Zustände), keine neue
  Architektur, kein neuer Schreibpfad, keine neue Abhängigkeit. Die einzige
  neue strukturelle Ergänzung ist eine `dense`-Prop auf `Step2Orte.svelte`
  nach bereits etabliertem Muster (`LayoutTab.svelte`).

## Changelog

- 2026-07-15: Initial spec created
- 2026-07-15: PO-Entscheide eingetragen (AskUserQuestion): AC-12 wie
  spezifiziert (Boden-CTA entfällt), eine Scheibe mit LoC-Override 500
- 2026-07-15: Umbau nach PO-Grundsatzregel „nichts nachbauen — Claude-
  Design-Komponenten verwenden, ggf. anpassen": In-Page-Listen-Kopf und
  nachgebaute `cm-mobile-appbar` gestrichen; stattdessen globale
  `TopAppBar` (Design-Komponente, #373) additiv erweitert (title/back/
  rechte Aktion) und pro Seite befüllbar; AC-1/AC-15/AC-20, Scope,
  Implementation Details, Known Limitation (a) entsprechend geändert
- 2026-07-15: Fakten-Korrektur Scope-Tabelle nach Adversary-F002:
  `compare-mobile-vervollstaendigung.spec.ts` brauchte keine Migration
  (referenziert nur unverändertes `cm-mobile-cta`); F001-Remediation:
  AC-15-E2E-Test um Rück-Navigations-Assertion (Leiste zeigt wieder
  Listen-Zustand) ergänzt
