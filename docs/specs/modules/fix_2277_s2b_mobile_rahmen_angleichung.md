---
entity_id: fix_2277_s2b_mobile_rahmen_angleichung
type: bugfix
created: 2026-09-27
updated: 2026-09-27
status: draft
version: "1.1"
tags: [trip-new, compare-new, mobile-shell, page-header, editor-sticky-footer, shared-component]
---

# `/trips/new` und `/compare/new` — Kopfleiste/Zurück/BottomNav angleichen (Issue #2277 Scheibe S2b)

## Approval

- [ ] Approved

## Purpose

Scheibe **S2b** von #2277 (Anlege-Strecke-Konvergenz, Epic #2345) gleicht den mobilen
Rahmen der beiden Anlege-Editoren an: `/trips/new` übernimmt für Kopfleiste und
Speicher-Aktion die geteilten Bausteine `PageHeader`/`BackLink`/`EditorStickyFooter`,
die `/compare/new` bereits nutzt, und `/compare/new` blendet — wie `/trips/new` es
bereits tut — die App-weite `BottomNav` aus. Trip hat aktuell **keinen** `PageHeader`-
Mount; die Zurück-Aktion (Desktop „Abbrechen"-Button, Mobile Icon-Button) und die
Speichern-Aktion sitzen als Inline-Markup in zwei getrennten Blöcken
(`TripNewEditor.svelte:479-499` Desktop, `:502-526` Mobile). `BackLink`/`PageHeader`
kennen bisher **nur** Href-Navigation — Trips Zurück-Aktion ist aber an
`intentionalCancel`/`beforeNavigate` gekoppelt (Autosave-Vermeidung beim bewussten
Abbruch) und darf deshalb nicht auf reine `<a href>`-Navigation umgestellt werden.
`BackLink`/`PageHeader` bekommen dafür ein optionales `onclick`-Prop, das die
Navigation durch einen direkten Callback-Aufruf ersetzt — ohne den Router zu
involvieren. `/compare/new` bleibt bei reinem `href` (kein Verhaltenswechsel dort).

## Source

- **File (Frontend):**
  `frontend/src/lib/components/atoms/BackLink.svelte`,
  `frontend/src/lib/components/atoms/PageHeader.svelte`,
  `frontend/src/lib/components/trip-new/TripNewEditor.svelte`,
  `frontend/src/routes/+layout.svelte`,
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (kleine Änderung),
  `frontend/src/lib/components/atoms/__tests__/back_link_page_header_onclick_button.test.ts`
  (neu), `frontend/src/lib/components/trip-new/__tests__/trip_new_mobile_rahmen_angleichung.test.ts`
  (neu, SSR-Render über `tripNewSsr.ts`), `frontend/src/routes/__tests__/layout_istanlegeseite_bottomnav.test.ts`
  (neu, SSR-Render über `layout-ssr-hooks.mjs`),
  `frontend/src/lib/components/compare-new/__tests__/compare_new_footer_nav_clearance.test.ts`
  (neu, Source-Inspection — Vorbild `compareNewResponsiveSwitch.test.ts`),
  `frontend/e2e/issue-661-trip-new-mobile.spec.ts` (erweitert)
- **Identifier:** `BackLink` (neuer Prop `onclick?: () => void`), `PageHeader`
  (`back`-Objekt bekommt `onclick?: () => void`), Mount-Ersatz Desktop
  `TripNewEditor.svelte:479-499` und Mobile `:502-526`, `+layout.svelte:212`
  (`isWizard` → `istAnlegeSeite`, bereits vorhanden `:220-222`),
  `CompareNewEditor.svelte:501` (`EditorStickyFooter`-Mount, neuer Prop
  `navClearance={false}`).

> **Schicht-Hinweis:** ausschließlich **Frontend**
> (`frontend/src/lib/components/`, `frontend/src/routes/`). Kein Go-API-Change,
> kein Python-Core-Code betroffen — reines Layout/Markup, kein Datenmodell-Bezug.

## Nicht in dieser Scheibe

- **AC-3 (Reiter-Reihenfolge/-Beschriftung „ab dem zweiten Reiter") ist explizit
  aus S2b herausgeschnitten** (Tech-Lead-Entscheidung, `docs/context/fix-2277-s2b-mobile-rahmen-angleichung.md`
  „Analysis" Punkt 2). Begründung: „ab dem zweiten Reiter identisch" ist wörtlich
  nicht anwendbar (Trip hat drei eigene Reiter — Route/Etappen/Wegpunkte —, Compare
  zwei — Vergleich/Orte) und bräuchte vor der Umsetzung eine Lesart-Klärung
  (vermutlich „ab dem ersten GEMEINSAMEN Reiter"). Die volle Umsetzung ist zudem kein
  Layout-Thema mehr, sondern ein Logik-Umbau in `TripNewEditor.svelte` (`TAB_DEFS`-
  Reihenfolge tauschen, Labels „Alerts"→„Alarme" angleichen, Lock-Hint-Kette neu
  verketten) mit eigenem LoC-/Testbedarf. Wird als Folge-Scheibe unter #2277
  zurückgestellt — Issue bleibt offen, kein neues Ticket nötig.
- **`TAB_DEFS`, Reiter-Reihenfolge, Labels, Lock-Hints, `unlockedTabs()`/`doneTabs()`
  in `tripNewLogic.ts`/`compareNewLogic.ts` werden NICHT verändert.** Nur der
  Rahmen (Kopfleiste, Zurück-Aktion, Speicher-Aktion, BottomNav-Sichtbarkeit,
  Tab-Streifen-Fade-Maske) wird angeglichen.
- **`CorridorEditor`/`AlarmeTab`/`WeatherMetricsTab`-Mounts (S1/S2a, #2426/#2442,
  bereits live) werden nicht angefasst.** Diese Scheibe berührt ausschließlich die
  Kopf-/Fußleisten-Bausteine und `+layout.svelte`. *(Nachtrag v1.2: Ausnahme —
  `EditStagesPanelNew.svelte` (`bottomReservePx`) und `app.css`
  (`mobile-scroll-pad--ohne-nav`), siehe „Affected Files"; beide rein additiv und
  default-transparent, in der Umsetzung als Folge von AC-4/AC-6 nötig geworden.)*
- **`?from=`-Vorlage (`/trips/new?from=`, `/compare/new?from=`) — Scheibe S2c.**
  Ein Query-Parameter berührt den Pathname-Check von `istAnlegeSeite` nicht — kein
  Konflikt mit dieser Scheibe.
- **`CompareNewEditor.svelte`s Desktop-Breadcrumb (`:264-284`, inline „Abbrechen"/
  „Briefing aktivieren") wird NICHT auf `PageHeader`/`EditorStickyFooter`
  umgestellt.** Compare nutzt diese Bausteine bislang nur im Mobile-Zweig
  (`:419-421` `PageHeader`, `:501-516` `EditorStickyFooter`); eine Desktop-
  Angleichung für Compare ist nicht Gegenstand von AC-6/AC-7 (die sich laut
  Request Summary auf den **mobilen** Rahmen beziehen) und bliebe eine eigene,
  spätere Entscheidung.
- **`CorridorEditorMobile.svelte` und die drei `context="vergleich"`-Mounts von
  `AlarmeTab`/`WeatherMetricsTab`/`CorridorEditor` in `CompareNewEditor.svelte`
  werden nicht verändert** — nur der `EditorStickyFooter`-Mount (`navClearance`-
  Prop) und `+layout.svelte` betreffen Compare in dieser Scheibe.
- **`EditorStickyFooter.svelte` selbst wird NICHT verändert.** Der Prop
  `navClearance` (Default `true`) existiert bereits (`:14,18`,
  `class:has-nav={navClearance}` `:21`, CSS-Regel `:35-39`) — diese Scheibe nutzt
  ihn nur an zwei neuen/geänderten Mount-Stellen, ändert aber nichts an der
  Komponente selbst (Abweichung von der ursprünglichen Analyse-Vermutung
  „`EditorStickyFooter` bekommt/behält ein `navClearance`-Verhalten" — Verifikation
  ergab: es existiert bereits vollständig).

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/atoms/BackLink.svelte` | MODIFY | Neuer optionaler Prop `onclick?: () => void` (Destrukturierung `:13`). Template (`:16-24`) bekommt eine Fallunterscheidung: ist `onclick` gesetzt, rendert ein `<button type="button" data-testid="back-link" class="mono back-link" aria-label={...} onclick={onclick}>` (identisches Innenleben: Chevron-SVG + Label) statt des bisherigen `<a href data-testid="back-link" ...>`; ohne `onclick` bleibt das bestehende `<a href>`-Markup unverändert (Default-Verhalten für Compare bitgleich). Kein Router-Kontakt im `onclick`-Zweig — der Callback wird direkt aufgerufen, keine `goto()`-Injektion in `BackLink` selbst. |
| `frontend/src/lib/components/atoms/PageHeader.svelte` | MODIFY | `Props.back` (`:17`) bekommt ein optionales drittes Feld: `back?: { href: string; label: string; onclick?: () => void }`. Der `<BackLink>`-Mount (`:37`) reicht `onclick={back.onclick}` durch. Ohne `onclick` im `back`-Objekt bleibt `BackLink` im Href-Modus (Compare-Mount `CompareNewEditor.svelte:420` bleibt unverändert und unbetroffen, weil dort kein `onclick`-Feld übergeben wird). |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Desktop-Breadcrumb (`:479-499`, `data-testid="tn-desktop-breadcrumb"`) und Mobile-App-Leiste (`:502-526`, `data-testid="tn-mobile-appbar"`) werden JEWEILS durch einen `<PageHeader back={{ href: '/trips', label: 'Trips', onclick: onCancel }} .../>`-Mount ersetzt — testid-Attribut bleibt auf dem jeweiligen `.tn-desktop`/`.tn-mobile`-Wrapper-`<div>` erhalten (1:1, nicht auf `PageHeader` selbst). Die bisherigen Aktions-Buttons dieser beiden Blöcke (Desktop „Abbrechen"+„Trip speichern" `:489-497`, Mobile „Speichern" `:520-525`) wandern in **zwei neue** `<EditorStickyFooter context="route" navClearance={false} testid="...">`-Mounts (einer je `.tn-desktop`/`.tn-mobile`-Zweig, analog zum bestehenden CSS-Umschaltmuster der Datei) — Desktop behält `data-testid="trip-new-save-btn"` auf dem Speichern-Button, Mobile behält `data-testid="tn-mobile-save"`. `onCancel`/`onSave` (`:470-471`, unverändert) werden an die neuen Mounts durchgereicht, `makeCancelHandler()` (`:466-468`) bleibt unverändert (kein neuer Delta-Code). Mobile Tab-Bar (`:586`, `data-testid="tn-mobile-tabbar"`) bekommt zusätzlich `mask-image`/`-webkit-mask-image` (16px Fade beidseitig, wörtlich identisch zu `CompareNewEditor.svelte:434`). |
| `frontend/src/routes/+layout.svelte` | MODIFY | `isWizard` (`:212`, `$derived(page.url.pathname.startsWith('/trips/new'))`) wird durch das bereits vorhandene `istAnlegeSeite`-Derived (`:220-222`, prüft `/trips/new` UND `/compare/new`) ersetzt; alle drei Verwendungsstellen von `isWizard` (`:271` `{#if !isWizard}` vor `BottomNav`) zeigen danach auf `istAnlegeSeite`. Keine neue Variable, keine doppelte Pflege zweier paralleler Flags. |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY (klein) | `EditorStickyFooter`-Mount (`:501`, `context="vergleich" testid="cm-mobile-cta"`) bekommt zusätzlich `navClearance={false}` — die Komponente reserviert danach keinen Leerraum mehr für eine (nun überall ausgeblendete) `BottomNav` auf `/compare/new`. Einzige Änderung an dieser Datei in S2b. |
| `frontend/src/app.css` | MODIFY (Nachtrag v1.2) | Neue Regel `.mobile-scroll-pad.mobile-scroll-pad--ohne-nav` (nur `max-width: 899px`): `padding-bottom: env(safe-area-inset-bottom)` statt Reservierung für die auf Anlege-Seiten ausgeblendete `BottomNav`. Wird von `+layout.svelte` per `class:mobile-scroll-pad--ohne-nav={istAnlegeSeite}` gesetzt. Folge von AC-6 (kein Leerraum mehr unter dem Speichern-Footer). |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY (Nachtrag v1.2) | Neuer optionaler Prop `bottomReservePx?: number` (Fallback `BOTTOM_NAV_HEIGHT_PX = 70`, alle anderen Aufrufer bitgleich). `TripNewEditor.svelte` reicht die per `ResizeObserver` gemessene Höhe des mobilen Speichern-Footers durch, damit die Wegpunkte-Karte samt Attribution über dem Footer endet (Folge von AC-4). Berührt nur die Höhenberechnung, keine Editor-Logik. |
| `frontend/src/lib/components/atoms/__tests__/back_link_page_header_onclick_button.test.ts` *(neu)* | CREATE | Echtes SSR-Rendering (`svelte/server`) von `BackLink.svelte` und `PageHeader.svelte` direkt (kein Umweg über `TripNewEditor`) — beweist die Grundbaustein-Regel isoliert vom Trip-Kontext. |
| `frontend/src/lib/components/trip-new/__tests__/trip_new_mobile_rahmen_angleichung.test.ts` *(neu)* | CREATE | Echtes SSR-Rendering über die bestehende Harness `tripNewSsr.ts` (Issue #1738) — Testid-Erhalt, Button-statt-Anchor-Struktur in beiden Viewport-Zweigen, Fade-Maske auf `tn-mobile-tabbar`. |
| `frontend/src/routes/__tests__/layout_istanlegeseite_bottomnav.test.ts` *(neu)* | CREATE | Echtes SSR-Rendering von `+layout.svelte` über die bestehende Harness `layout-ssr-hooks.mjs` (Issue #2268, Vorbild `app_footer_je_route.test.ts`) — BottomNav-Sichtbarkeit je Route. |
| `frontend/src/lib/components/compare-new/__tests__/compare_new_footer_nav_clearance.test.ts` *(neu)* | CREATE | Source-Inspection (`readFileSync`) auf `CompareNewEditor.svelte` — Vorbild `compareNewResponsiveSwitch.test.ts`, das für dieselbe Datei mangels SSR-Harness (kein Stub für den `compare-wizard-state`-Context) bereits denselben Ansatz nutzt. Zulässig hier, weil es eine reine Konfigurations-/Prop-Anwesenheitszusicherung ist (`navClearance={false}` auf dem konkreten Mount), kein Verhaltensnachweis, der SSR bräuchte. |
| `frontend/e2e/issue-661-trip-new-mobile.spec.ts` | MODIFY | Neue Testfälle: (a) Zurück-Tap auf Mobile navigiert zu `/trips`, OHNE dass zuvor ein `PUT /api/trips/__new__`-Request (Autosave) beobachtet wird (Netzwerk-Interception); (b) Testid-Erhalt an den (nun anders positionierten) Speichern-Buttons bleibt über bestehende `AC-1`/`AC-8`-Tests hinweg grün (keine Änderung an diesen Tests nötig, da sie testid-basiert und positionsunabhängig lokalisieren). |

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. +70 / −75 — deutlich unter dem 250-LoC-Limit.
  Die ursprüngliche Analyse-Schätzung (+100/−120 bis +160/−160) ging von einer
  größeren Markup-Verschiebung aus; die Verifikation der tatsächlichen Dateien
  (insbesondere `EditorStickyFooter.svelte`, das `navClearance` bereits fertig
  mitbringt) reduziert den Umfang. `workflow.py status` ist vor jeder
  Override-Ankündigung in `/50` die maßgebliche Quelle, nicht diese Schätzung.
- **Files:** 5 produktiv (`BackLink.svelte`, `PageHeader.svelte`,
  `TripNewEditor.svelte`, `+layout.svelte`, `CompareNewEditor.svelte` — Letzteres
  nur 1 Zeile), 5 Testdateien (4 neu, 1 erweitert E2E) — Testdateien zählen nicht
  gegen das LoC-Limit.
- **Effort:** medium.
- **Risk Level: MEDIUM.** Nicht wegen Komplexität, sondern wegen der
  Autosave-Kopplung (`beforeNavigate`/`intentionalCancel`, s. Purpose) und der
  Testid-Abhängigkeit von `issue-661-trip-new-mobile.spec.ts`. Beides ist durch
  den gewählten Ansatz (Button-Callback statt Href-Navigation, Testids 1:1
  erhalten) strukturell entschärft, nicht nur getestet. `BackLink`/`PageHeader`
  sind geteilte Atome mit weiteren Aufrufern (u.a. Compare, ggf. andere Seiten) —
  der neue Prop ist additiv und default-transparent (Default `undefined`, altes
  Href-Verhalten bleibt Standard).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareNewEditor.svelte:420` (`PageHeader back={{href,label}}`, ohne `onclick`) | component | Lebender Präzedenzfall für den unveränderten Href-Modus — Regressionsanker, an dem der neue optionale Prop nichts ändern darf. |
| `EditorStickyFooter.svelte` (`navClearance`-Prop, bereits vorhanden) | component | Wiederverwendet ohne Änderung — sowohl für die zwei neuen Trip-Mounts als auch für die `navClearance={false}`-Ergänzung am bestehenden Compare-Mount. |
| `+layout.svelte:220-222` (`istAnlegeSeite`) | derived | Bereits bestehendes Muster „beide Anlege-Routen" (Issue #2316 AC-8) — Vorlage für die Erweiterung von `isWizard`, keine neue Bedingung nötig. |
| `TripNewEditor.svelte:449-471` (`beforeNavigate`, `intentionalCancel`, `makeCancelHandler`) | logic | Unverändert wiederverwendet — der neue `PageHeader`-Mount reicht lediglich die bestehende `onCancel`-Konstante als `back.onclick` durch, keine neue Abbruch-Logik. |
| `frontend/src/lib/components/trip-new/__tests__/tripNewSsr.ts` (`renderTripNew`, `countTestid`, `outerHtml`, `bereichVon`) | Prüfstand | Bereits vorhandene SSR-Render-Harness (Issue #1738), wiederverwendet für alle Trip-ACs — keine neue Infrastruktur. |
| `frontend/src/routes/__tests__/layout-ssr-hooks.mjs` + Registrierungsmuster aus `app_footer_je_route.test.ts` | Prüfstand | Bereits vorhandene SSR-Render-Harness für `+layout.svelte` (Issue #2268) — wiederverwendet für die BottomNav-AC, keine neue Infrastruktur. |
| `frontend/src/lib/components/compare-new/__tests__/compareNewResponsiveSwitch.test.ts` | Vorbild | Belegt, dass Source-Inspection für `CompareNewEditor.svelte` bereits der etablierte, akzeptierte Prüfweg ist (kein `compare-wizard-state`-Context-Stub vorhanden) — dieselbe Technik für die `navClearance`-AC. |
| `docs/specs/modules/fix_2277_s1_alarme_tab_route.md`, `fix_2277_s2a_wertebereiche_trip_anlegen.md` | spec | Formvorbild dieser Spec (Detailtiefe, Wirkort-je-Zusicherung, Mutations-Gegenproben). |

## Implementation Details

### Design-Entscheidungen

1. **`onclick` schaltet `BackLink` auf einen `<button>`, nie beide Pfade
   gleichzeitig.** Ein `<a href>` mit zusätzlichem `onclick`, das `preventDefault()`
   aufruft, wäre ein zweiter, fehleranfälliger Mechanismus (Tastatur-/Screenreader-
   Aktivierung eines Links löst z.T. andere Events aus als ein Button). Die Spec
   verlangt stattdessen eine echte Fallunterscheidung im Template: `onclick`
   gesetzt ⇒ `<button>`, sonst `<a href>`. Damit gibt es strukturell **keinen**
   Href/Navigations-Pfad, wenn `onclick` aktiv ist — die Regression aus Risk #1
   der Analyse („naiver Ersatz überspringt `intentionalCancel`") ist dadurch nicht
   nur vermieden, sondern durch Abwesenheit des `href`-Attributs im gerenderten
   Markup nachweisbar.
2. **`TripNewEditor.svelte` übergibt weiterhin dieselbe `onCancel`-Konstante
   (`:471`), keine neue Wrapper-Funktion.** `makeCancelHandler()` setzt bereits
   `intentionalCancel = true` VOR `goto('/trips')` — das ist exakt das Verhalten,
   das `beforeNavigate` (`:450-457`) braucht, um den Autosave-Zweig zu
   überspringen. Der einzige Unterschied zu heute: der Aufruf-Ort wandert vom
   Inline-`<button onclick={makeCancelHandler()}>` (Mobile, `:504`) bzw.
   `<button onclick={onCancel}>` (Desktop, `:489`) in den `back.onclick`-Slot von
   `PageHeader`. Kein Verhaltensunterschied, nur ein anderer struktureller Ort.
3. **Save-Aktion wandert für BEIDE Viewports (Desktop UND Mobile) in je einen
   `EditorStickyFooter`-Mount, nicht nur mobil.** Das geht über die im Request
   Summary genannte „mobiler Rahmen"-Formulierung hinaus, folgt aber wörtlich der
   gebundenen Tech-Lead-Entscheidung 3 aus der Analyse-Phase
   (`docs/context/fix-2277-s2b-mobile-rahmen-angleichung.md`): „Das ersetzt die
   Desktop-Breadcrumb-Buttons (:493-497) und die Mobile-Appbar-Save-Taste
   (:520-525) durch den geteilten Baustein". Begründung: `onSave`/`onCancel` sind
   für beide Viewports identisch — ein Aufteilen (Desktop bleibt Inline-Button,
   nur Mobile nutzt `EditorStickyFooter`) würde dieselbe Save-Logik/-Beschriftung
   an zwei Stellen unterschiedlich pflegen, genau das, was CLAUDE.md
   „Trip/Ortsvergleich-Code-Teilung" vermeiden will. `EditorStickyFooter`s
   `position: sticky; bottom: 0`-Verhalten (`:27-28`) funktioniert unabhängig vom
   Viewport; die `@media (max-width: 899px)`-Regel (`:35-39`) betrifft nur das
   zusätzliche Bottom-Padding bei `has-nav`, nicht die Sticky-Sichtbarkeit selbst.
4. **`navClearance={false}` auf BEIDEN Trip-Footern UND dem geänderten
   Compare-Footer.** `BottomNav` ist auf `/trips/new` bereits heute (unverändert
   durch diese Scheibe) und auf `/compare/new` NEU (Design-Entscheidung 5)
   ausgeblendet — in keinem der drei Fälle muss der jeweilige
   `EditorStickyFooter` Platz für eine tatsächlich unsichtbare `BottomNav`
   reservieren. `navClearance`s Default (`true`) bleibt für andere, künftige
   Mounts außerhalb von Anlege-Seiten unverändert nützlich (z.B. ein Sticky-Footer
   auf einer Seite MIT sichtbarer `BottomNav`) — kein Eingriff in die Komponente
   nötig, nur an den Aufrufstellen.
5. **`isWizard` wird ERSETZT, nicht um `istAnlegeSeite` ergänzt.** Zwei parallele
   Flags mit überlappender, aber nicht identischer Bedeutung (`isWizard` nur
   `/trips/new`, `istAnlegeSeite` beide Routen) wären eine Fehlerquelle bei jeder
   künftigen dritten Anlege-Route. `istAnlegeSeite` (`:220-222`) deckt den
   bisherigen `isWizard`-Anwendungsfall (`:271`) vollständig ab — Ersetzen statt
   Duplizieren.

### Wirkort je Zusicherung

- **`BackLink`/`PageHeader` rendern bei gesetztem `onclick` einen `<button>` ohne
  `href` (AC-1/AC-2)** → **Kern, echtes SSR-Rendering** der beiden Atome direkt
  (kein Umweg über einen Editor). Reine Struktur-Behauptung — SSR serialisiert
  `onclick={fn}` nicht als HTML-Attribut, daher kann dieser Test NICHT beweisen,
  dass der übergebene Callback bei einem echten Klick feuert (das ist E2E-
  Aufgabe, s.u.), wohl aber, dass **kein** `href`-Navigationspfad existiert, wenn
  `onclick` gesetzt ist, und dass der Href-Pfad ohne `onclick` unverändert bleibt
  (Compare-Regressionsschutz, ohne Compare selbst zu rendern).
- **Trip Mobile-Appbar + Desktop-Breadcrumb nutzen den neuen Button-Pfad,
  Testids bleiben erhalten (AC-3/AC-4/AC-9)** → **Kern, echtes SSR-Rendering**
  über `tripNewSsr.ts`. `bereichVon()` klassifiziert die beiden `back-link`-
  Fundstellen nach Desktop/Mobil-Baum, `countTestid()` beweist Ein-Instanz je
  Testid.
- **Zurück-Tap navigiert ohne vorherigen Autosave (AC-5)** → **Live-E2E**
  (`issue-661-trip-new-mobile.spec.ts`), weil SSR keine Klick-Events ausführen
  kann. Netzwerk-Interception beweist die Abwesenheit eines
  `PUT /api/trips/__new__`-Requests vor der Navigation zu `/trips`.
- **BottomNav auf `/compare/new` jetzt ebenfalls ausgeblendet, `/trips/new`
  unverändert, andere Routen unverändert sichtbar (AC-6)** → **Kern, echtes
  SSR-Rendering** von `+layout.svelte` über `layout-ssr-hooks.mjs` (Vorbild
  `app_footer_je_route.test.ts`), Regex `/bottom-?nav/i` auf Abwesenheit/
  Anwesenheit geprüft.
- **Kein reservierter Leerraum im Compare-Footer (AC-7)** → **Kern,
  Source-Inspection** auf `CompareNewEditor.svelte` (kein SSR-Harness verfügbar,
  s. Affected Files) — reine Konfigurations-Anwesenheitszusicherung.
- **Fade-Maske auf `tn-mobile-tabbar` (AC-8)** → **Kern, echtes SSR-Rendering**
  über `tripNewSsr.ts`, `outerHtml(html, 'tn-mobile-tabbar')` + Regex auf
  `mask-image`/`-webkit-mask-image` mit denselben Werten wie
  `CompareNewEditor.svelte:434`.
- **Vorlese-Text (`aria-label`) am Zurück-Pfeil in `/trips/new` (AC-10)** →
  **Kern, echtes SSR-Rendering** über `tripNewSsr.ts`, derselbe Prüfstand wie
  AC-3/AC-8. Der bisherige Icon-Button trug KEIN `aria-label`
  (Mobile-Audit-Nachtrag 19.09. zu #2277) — mit dem Ersatz durch `BackLink`
  bringt der Baustein seinen Default `` `Zurück: ${label}` `` (`BackLink.svelte:20`)
  automatisch mit; diese AC weist den resultierenden, konkreten Text
  `aria-label="Zurück: Trips"` in BEIDEN Viewport-Zweigen explizit nach, statt
  es als Nebeneffekt von AC-3 unbewiesen zu lassen.

## Expected Behavior

- **Input:** Ein Nutzer öffnet `/trips/new` oder `/compare/new` auf einem
  schmalen Viewport (≤899px) und tippt auf den Zurück-Pfeil in der Kopfleiste.
- **Output:** Trip navigiert wie bisher zu `/trips`, ohne dass zuvor ein
  Autosave-Request ausgelöst wird (`intentionalCancel` greift weiterhin). Beide
  Editoren zeigen dieselbe Kopfleisten-Bauart (`PageHeader`) und dieselbe
  Speicher-Fußleiste (`EditorStickyFooter`). Die App-weite `BottomNav` ist auf
  beiden Anlege-Seiten unsichtbar, ohne dass am unteren Bildschirmrand
  reservierter Leerraum stehen bleibt. Die mobile Tab-Leiste beider Editoren
  zeigt an beiden Rändern denselben Scroll-Hinweis (Fade-Maske).
- **Side effects:** Keine zusätzlichen Netzwerkzugriffe. Kein Verhalten ändert
  sich für Desktop-Nutzer von `/compare/new` (dessen Breadcrumb bleibt
  unangetastet) oder für Nutzer außerhalb der beiden Anlege-Seiten (`isWizard`→
  `istAnlegeSeite` deckt exakt denselben BottomNav-Anwendungsfall ab, keine
  dritte Route betroffen).

## Acceptance Criteria

- **AC-1:** Given `BackLink.svelte` rendert heute ausschließlich ein `<a href>`
  (`:16-24`), unabhängig davon, ob ein Klick-Callback benötigt wird / When ein
  neuer optionaler Prop `onclick?: () => void` gesetzt wird / Then rendert
  `BackLink` (SSR, `svelte/server`) mit `{ href: '/trips', label: 'Trips',
  onclick: () => {} }` ein `<button type="button" data-testid="back-link">`
  OHNE `href`-Attribut, UND mit denselben Props aber OHNE `onclick` weiterhin ein
  `<a href="/trips" data-testid="back-link">`.
  - Test: Kern — `back_link_page_header_onclick_button.test.ts`, direktes
    SSR-Rendering von `BackLink.svelte` in beiden Varianten.
  - Mutations-Gegenprobe: die Fallunterscheidung entfernen und immer `<a href>`
    rendern (auch bei gesetztem `onclick`) ⇒ das gerenderte Element trägt ein
    `href`-Attribut, obwohl `onclick` gesetzt ist ⇒ Test wird rot.

- **AC-2:** Given `PageHeader.svelte`s `back`-Prop kennt heute nur `{href,
  label}` (`:17`) und reicht kein `onclick` an `BackLink` durch (`:37`) / When
  `back` um ein optionales `onclick?: () => void` erweitert und an `BackLink`
  durchgereicht wird / Then rendert `PageHeader` mit
  `back={{href:'/x',label:'X',onclick:fn}}` denselben `<button>`-Pfad wie AC-1,
  UND `PageHeader` mit `back={{href:'/compare',label:'Vergleiche'}}` (ohne
  `onclick`, exakter Compare-Mount-Wortlaut `CompareNewEditor.svelte:420`)
  rendert unverändert ein `<a href="/compare">`.
  - Test: Kern — `back_link_page_header_onclick_button.test.ts`, direktes
    SSR-Rendering von `PageHeader.svelte` in beiden Varianten (zweite Variante
    ist die Regressionsprobe für Compare, ohne Compare selbst zu rendern).
  - Mutations-Gegenprobe: `onclick={back.onclick}` beim `<BackLink>`-Mount in
    `PageHeader.svelte` weglassen ⇒ auch mit gesetztem `back.onclick` bleibt das
    Ergebnis ein `<a href>` ⇒ Test wird rot.

- **AC-3:** Given `/trips/new` zeigt heute in `data-testid="tn-mobile-appbar"`
  einen Inline-Icon-Button `onclick={makeCancelHandler()}` OHNE `PageHeader`
  (`:504-509`) und in `data-testid="tn-desktop-breadcrumb"` einen Inline-Button
  „Abbrechen" `onclick={onCancel}` (`:489-492`) / When beide Blöcke durch einen
  `<PageHeader back={{href:'/trips',label:'Trips',onclick:onCancel}} .../>`-Mount
  ersetzt werden (Wrapper-`data-testid` unverändert) / Then liefert
  `renderTripNew({activeTab:'route', isMobileViewport:false})` GENAU EIN
  `<button ... data-testid="back-link">` (kein `<a ... data-testid="back-link">`)
  innerhalb von `outerHtml(html, 'tn-desktop-breadcrumb')`, UND
  `renderTripNew({activeTab:'route', isMobileViewport:true})` GENAU EIN
  `<button ... data-testid="back-link">` innerhalb von
  `outerHtml(html, 'tn-mobile-appbar')`.
  - Test: Kern — `trip_new_mobile_rahmen_angleichung.test.ts`, `renderTripNew()`
    + `outerHtml()` + `bereichVon()` (alle aus `tripNewSsr.ts`).
  - Mutations-Gegenprobe: im Trip-Mount `back={{href:'/trips',label:'Trips'}}`
    (ohne `onclick`) übergeben ⇒ beide Fundstellen rendern wieder `<a href>`
    statt `<button>` ⇒ Test wird rot (genau die Regression aus Analyse-Risk #1).

- **AC-4:** Given die Speichern-/Abbrechen-Aktionen sitzen heute als Inline-
  Buttons INNERHALB von `tn-desktop-breadcrumb` (`:493-497`,
  `data-testid="trip-new-save-btn"`) bzw. `tn-mobile-appbar` (`:520-525`,
  `data-testid="tn-mobile-save"`) / When beide Aktionen in je einen neuen
  `<EditorStickyFooter context="route" navClearance={false}>`-Mount wandern (ein
  Mount je `.tn-desktop`/`.tn-mobile`-Zweig) / Then liefert
  `countTestid(renderTripNew({activeTab:'route', isMobileViewport:false}),
  'trip-new-save-btn')` GENAU 1 UND `countTestid(...,
  'tn-mobile-appbar')` weiterhin GENAU 1 (der Wrapper bleibt bestehen, auch ohne
  die Save-Taste darin), UND
  `countTestid(renderTripNew({activeTab:'route', isMobileViewport:true}),
  'tn-mobile-save')` GENAU 1.
  - Test: Kern — `trip_new_mobile_rahmen_angleichung.test.ts`, `countTestid()`.
  - Mutations-Gegenprobe: `data-testid="tn-mobile-save"` beim Verschieben in den
    neuen `EditorStickyFooter`-Mount versehentlich weglassen ⇒
    `countTestid(...,'tn-mobile-save')` liefert `0` statt `1` ⇒ Test wird rot
    (fängt genau die Regression, die `issue-661-trip-new-mobile.spec.ts` AC-1
    sonst erst im E2E-Lauf fände).

- **AC-5:** Given `beforeNavigate` (`TripNewEditor.svelte:450-457`) triggert
  heute einen Autosave-PUT (`buildAndSave()`), sobald `!intentionalCancel` beim
  Verlassen der Seite ist / When ein Nutzer auf Mobile (≤899px) den
  Zurück-Button in der neuen `PageHeader`-Kopfleiste antippt / Then navigiert
  der Browser zu `/trips`, UND es wird zu keinem Zeitpunkt vor Abschluss dieser
  Navigation ein `PUT`-Request auf `/api/trips/__new__` beobachtet.
  - Test: Live-E2E — `issue-661-trip-new-mobile.spec.ts`, neuer Testfall:
    `page.on('request', ...)`-Interception ab `page.goto('/trips/new')` bis
    nach dem Klick auf den Zurück-Button in `tn-mobile-appbar`, Assertion auf
    die Abwesenheit eines `PUT`-Requests mit `/api/trips/__new__` im Pfad,
    gefolgt von `expect(page).toHaveURL(/\/trips$/)`.
  - Mutations-Gegenprobe: `back={{href:'/trips',label:'Trips'}}` (ohne
    `onclick`) im Trip-Mount ⇒ Klick navigiert per `<a href>` SOFORT, OHNE
    vorher `intentionalCancel = true` zu setzen ⇒ `beforeNavigate` triggert
    einen Autosave-`PUT` ⇒ Test wird rot (Netzwerk-Request beobachtet, wo keiner
    erwartet ist).

- **AC-6:** Given `+layout.svelte:212` blendet `BottomNav` heute NUR für
  `/trips/new` aus (`isWizard`, `:271` `{#if !isWizard}`) — auf `/compare/new`
  bleibt sie sichtbar / When `isWizard` durch das bereits vorhandene
  `istAnlegeSeite`-Derived (`:220-222`, deckt beide Routen ab) ersetzt wird /
  Then rendert das Layout für `/compare/new` KEINE `BottomNav` mehr
  (`!/bottom-?nav/i.test(html)`), für `/trips/new` weiterhin KEINE (unverändert),
  und für `/trips` (Kontrollroute) weiterhin EINE (`/bottom-?nav/i.test(html)`).
  - Test: Kern — `layout_istanlegeseite_bottomnav.test.ts`, echtes
    SSR-Rendering über `layout-ssr-hooks.mjs` (Vorbild
    `app_footer_je_route.test.ts` AC-4/AC-5), drei Pfade geprüft.
  - Mutations-Gegenprobe: `isWizard` unverändert lassen (kein Ersatz) ⇒
    `/compare/new` zeigt weiterhin eine `BottomNav` ⇒ Test wird rot.

- **AC-7:** Given `CompareNewEditor.svelte:501`s `EditorStickyFooter`-Mount
  setzt heute kein `navClearance` (Default `true` reserviert Bottom-Padding für
  eine sichtbare `BottomNav`, `EditorStickyFooter.svelte:35-39`) — nach AC-6 ist
  die `BottomNav` auf `/compare/new` aber nie mehr sichtbar / When
  `navClearance={false}` am Mount ergänzt wird / Then enthält
  `CompareNewEditor.svelte` an der `EditorStickyFooter`-Mount-Zeile das Attribut
  `navClearance={false}`.
  - Test: Kern — `compare_new_footer_nav_clearance.test.ts`, Source-Inspection
    (Vorbild `compareNewResponsiveSwitch.test.ts`, da kein SSR-Harness für
    `CompareNewEditor.svelte` existiert — fehlender Context-Stub für
    `compare-wizard-state`).
  - Mutations-Gegenprobe: `navClearance={false}` wieder entfernen ⇒ Test wird
    rot (Attribut fehlt am Mount).

- **AC-8:** Given `CompareNewEditor.svelte:434`s mobile Tab-Leiste trägt bereits
  eine Fade-Maske (`mask-image`/`-webkit-mask-image`, 16px beidseitig), Trips
  `tn-mobile-tabbar` (`TripNewEditor.svelte:586`) aber nicht / When dieselbe
  `mask-image`/`-webkit-mask-image`-Deklaration wörtlich auf `tn-mobile-tabbar`
  übertragen wird / Then enthält
  `outerHtml(renderTripNew({activeTab:'route', isMobileViewport:true}),
  'tn-mobile-tabbar')` sowohl `mask-image: linear-gradient(to right,
  transparent, black 16px, black calc(100% - 16px), transparent)` als auch die
  `-webkit-`-Variante.
  - Test: Kern — `trip_new_mobile_rahmen_angleichung.test.ts`, `outerHtml()` +
    Regex auf beide Deklarationen.
  - Mutations-Gegenprobe: nur die `-webkit-`-Variante ergänzen, die
    Standard-Deklaration weglassen ⇒ Test wird rot (fehlende
    `mask-image`-Deklaration).

- **AC-9 (Ein-Instanz-/Testid-Erhalt, Strukturwächter):** Given die vier
  bestehenden Testids `tn-mobile-appbar`, `tn-mobile-save`,
  `tn-desktop-breadcrumb`, `tn-mobile-tabbar` sind vertragliche Selektoren von
  `issue-661-trip-new-mobile.spec.ts` / When der Rahmen-Umbau (AC-3/AC-4/AC-8)
  abgeschlossen ist / Then liefert `countTestid()` für JEDES der vier Testids in
  `renderTripNew({activeTab:'route', isMobileViewport:false})` UND
  `renderTripNew({activeTab:'route', isMobileViewport:true})` in Summe über
  beide Aufrufe GENAU 1 pro Testid (kein Testid verdoppelt sich, keins
  verschwindet).
  - Test: Kern — `trip_new_mobile_rahmen_angleichung.test.ts`, Schleife über
    die vier Testids mit `countTestid()` (Muster `trip_new_alarme_reiter.test.ts`
    AC-6/`trip_new_wertebereiche_reiter.test.ts` AC-5).
  - Mutations-Gegenprobe: `data-testid="tn-desktop-breadcrumb"` beim Ersetzen
    des Blocks versehentlich auf den neuen `PageHeader`-Mount selbst verschieben
    statt auf dem `.tn-desktop`-Wrapper zu belassen ⇒ sobald `PageHeader`
    bedingt weniger Markup umschließt als der alte Wrapper, kann das Testid an
    einer anderen Verschachtelungstiefe landen als von `bereichVon()`/
    nachgelagerten E2E-Selektoren erwartet — der Test fängt zumindest die
    Verdopplung/Abwesenheit, die eine falsch platzierte testid-Zuweisung häufig
    begleitet.

- **AC-10:** Given der heutige Icon-Button in `tn-mobile-appbar`
  (`TripNewEditor.svelte:504-509`) trägt KEIN `aria-label` (Mobile-Audit-Nachtrag
  19.09. zu #2277 — Vorlesetext für Screenreader fehlt), und `BackLink.svelte`s
  Default-`aria-label` ist `` `Zurück: ${label}` `` (`:20`, greift, solange kein
  eigenes `ariaLabel`-Prop übergeben wird) / When der Icon-Button durch den
  gemeinsamen `PageHeader`-Mount mit `back={{href:'/trips', label:'Trips',
  onclick:onCancel}}` ersetzt wird (AC-3) / Then enthält
  `outerHtml(renderTripNew({activeTab:'route', isMobileViewport:true}),
  'tn-mobile-appbar')` das Attribut `aria-label="Zurück: Trips"` GENAU EINMAL,
  UND `outerHtml(renderTripNew({activeTab:'route', isMobileViewport:false}),
  'tn-desktop-breadcrumb')` ebenfalls `aria-label="Zurück: Trips"` GENAU EINMAL.
  - Test: Kern — `trip_new_mobile_rahmen_angleichung.test.ts`, `outerHtml()` +
    Regex auf `aria-label="Zurück: Trips"`, beide Viewport-Renders (Muster wie
    AC-3/AC-8, derselbe Prüfstand).
  - Mutations-Gegenprobe: `label: 'Trips'` beim `back`-Objekt in
    `TripNewEditor.svelte` weglassen (bzw. auf `label: ''` verfälschen) ⇒ der
    resultierende Vorlesetext wird `aria-label="Zurück: "` (bzw. `"Zurück:
    undefined"`) statt `"Zurück: Trips"` ⇒ Test wird rot.

## Known Limitations

- **Kein Live-E2E-Nachweis für den Desktop-Klickpfad in dieser Scheibe.** AC-5
  prüft die Autosave-Vermeidung nur auf Mobile (≤899px), weil
  `issue-661-trip-new-mobile.spec.ts` ausschließlich Mobile-Szenarien enthält.
  Der Desktop-„Zurück"-Klick nutzt denselben `PageHeader`-Mechanismus
  (identischer `back.onclick`), ist aber nur über den manuellen Staging-
  Klick-Durchlauf bei `/70-deploy` abgedeckt (Pflicht bei jeder UI-Änderung,
  `docs/reference/operations_playbook.md`).
- **`CompareNewEditor.svelte`s Desktop-Breadcrumb bleibt strukturell
  abweichend von Trip** (eigenes Inline-Markup statt `PageHeader`/
  `EditorStickyFooter`) — bewusst außerhalb dieser Scheibe (s. „Nicht in dieser
  Scheibe"). Die Trip/Compare-Konvergenz ist nach S2b auf Mobile vollständig,
  auf Desktop nur für Trip (Kopf-/Fußleiste) hergestellt.
- **AC-3 des Gesamt-Epics (Reiter-Reihenfolge) bleibt offen**, s. „Nicht in
  dieser Scheibe" — eigene Folge-Scheibe unter #2277.
- **`compare_new_footer_nav_clearance.test.ts` ist eine reine
  Konfigurations-Anwesenheitsprüfung, kein Verhaltensnachweis.** Ob
  `navClearance={false}` tatsächlich das erwartete CSS-Verhalten (keine
  `has-nav`-Klasse, kein reserviertes Bottom-Padding) erzeugt, ist bereits durch
  `EditorStickyFooter.svelte`s bestehende, unveränderte Implementierung
  (`class:has-nav={navClearance}`) belegt — diese Scheibe fügt dafür keinen
  neuen Komponententest hinzu, weil `EditorStickyFooter.svelte` selbst nicht
  geändert wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Der optionale `onclick`-Callback auf `BackLink`/`PageHeader`
  folgt demselben additiven, default-transparenten Erweiterungsmuster, das S1/
  S2a bereits für `createMode`-Props auf Domänen-Organismen etabliert haben
  (`docs/specs/modules/fix_2277_s1_alarme_tab_route.md`,
  `fix_2277_s2a_wertebereiche_trip_anlegen.md`) — hier auf zwei UI-Atome
  angewendet, kein neuer Architekturentscheid. Der Ersatz von `isWizard` durch
  `istAnlegeSeite` ist eine reine Konsolidierung zweier überlappender Flags auf
  ein bereits bestehendes, unter Issue #2316 (AC-8) eingeführtes Derived — ebenfalls
  keine neue Architekturentscheidung.

## Changelog

- 2026-09-27: Initial spec created (Scheibe S2b von #2277, Epic #2345).
- 2026-09-27 (v1.1, Nachtrag PO): explizites AC-10 für den Vorlese-Text
  (`aria-label`) am Zurück-Pfeil in `/trips/new` ergänzt — bisher nur strukturell
  über AC-3 miterledigt, jetzt einzeln mit konkretem, verifiziertem Text
  (`"Zurück: Trips"`, `BackLink.svelte:20`-Default) nachgewiesen. „Wirkort je
  Zusicherung" um den entsprechenden Eintrag ergänzt.
- 2026-09-28 (v1.2, Validierungs-Nachtrag, Adversary-Finding G003): `app.css` und
  `EditStagesPanelNew.svelte` in „Affected Files" nachgetragen (Implementierungs-
  Realität, keine neuen ACs). Beide Änderungen sind durch die E2E-Fälle
  „S2b AC-4 (mobil)" in `issue-661-trip-new-mobile.spec.ts` gedeckt.
