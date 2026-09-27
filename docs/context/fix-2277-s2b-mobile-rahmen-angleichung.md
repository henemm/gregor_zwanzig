# Context: fix-2277-s2b-mobile-rahmen-angleichung

## Request Summary

Issue #2277, Scheibe S2b (aus dem Schnitt-Vorschlag von S2): Die Anlege-Seiten `/trips/new`
und `/compare/new` sollen im mobilen Rahmen (Kopfleiste, Zurück-Aktion, Tabbar-Sichtbarkeit,
Tab-Streifen-Scrollhinweis) und in Reiter-Beschriftung/-Reihenfolge/-Lock-Hinweisen
angeglichen werden (AC-3, AC-6, AC-7 aus dem Issue). Kein Datenmodell-Risiko — reines
Layout/Markup. S1 (AlarmeTab) und S2a (Wertebereiche-Reiter) sind bereits live.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (1257 Zeilen) | Mobile App-Leiste (`:502-526`) — eigener 44×44-Icon-Zurück-Button **ohne `aria-label`** (`:504-509`), kein `PageHeader`, kein `EditorStickyFooter` (0 Treffer für beide im ganzen File). Mobile Tab-Bar (`:586-611`) **ohne Fade-Maske**. `TAB_DEFS` (`:70-78`): `route, etappen, wegpunkte, metriken, wertebereiche, zeitplan, alerts` — 7 Einträge. Tab `zeitplan` mountet `VersandTab` (`:880-892`, `:1154-1159`), Tab `alerts` mountet `AlarmeTab` (`:926-936`, `:1183-1189`) — **in dieser Reihenfolge: erst VersandTab, dann AlarmeTab**. `makeCancelHandler()` (`:466-468`) setzt `intentionalCancel = true` und ruft `goto('/trips')` — das ist an `beforeNavigate` (`:450-457`) gekoppelt, das bei fehlendem `intentionalCancel`-Flag stattdessen einen Autosave auslöst. |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (578 Zeilen) | Nutzt bereits `PageHeader` (`$lib/components/atoms`, Import `:60`, Mount `:420` mit `back={{ href: '/compare', label: 'Vergleiche' }}`) und `EditorStickyFooter` (`$lib/components/shared/EditorStickyFooter.svelte`, Import `:59`, Mount `:501-516`). Mobile Tab-Bar (`:434`) trägt bereits `mask-image`/`-webkit-mask-image` (Fade an beiden Rändern, 16px). `TAB_DEFS` (`:96-103`): `vergleich, orte, metriken, idealwerte, alarme, versand` — 6 Einträge. Tab `alarme` mountet `AlarmeTab`, Tab `versand` mountet `VersandTab` — **umgekehrte Reihenfolge zu Trip** (dort: erst Versand/Zeitplan, dann Alarme/Alerts). Kein `beforeNavigate`/`intentionalCancel`-Muster vorhanden (0 Treffer) — Compare kennt diese Autosave-beim-Verlassen-Logik gar nicht. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` (244 Zeilen) | Lock-Kette der Trip-Tabs (Freischaltung/`done`-Zustand); für AC-3 relevant nur, falls Reihenfolge/Label-Änderungen die Kette berühren. |
| `frontend/src/lib/components/compare-new/compareNewLogic.ts` (69 Zeilen) | Lock-Kette Compare, strukturell gespiegelt aus `tripNewLogic.ts`. |
| `frontend/src/lib/components/atoms/PageHeader.svelte` | Geteiltes Atom: `eyebrow`/`title`/`sub`/`right`-Slot/`back`-Prop (`{href, label}`)/`compact`. Rendert bei `back` ein `<BackLink>`. **Kein Callback-Hook** — `back` ist reine Href-Navigation, kein `onclick`-Override möglich (Risiko, siehe unten). |
| `frontend/src/lib/components/atoms/BackLink.svelte` | Geteiltes Atom: `<a href>` mit `aria-label` (Default `Zurück: ${label}`, per `ariaLabel`-Prop überschreibbar). Reine Navigation, kein Klick-Interception-Mechanismus. |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | Bereits als **geteilter Baustein für Trip UND Vergleich** kommentiert (`:1-6`), aber nur von Compare gemountet — Trip nutzt eigene Inline-Buttons in der Desktop-Breadcrumb-Leiste (`:489-497`) und der Mobile-App-Leiste (`:520-525`) statt des Footers. |
| `frontend/src/routes/+layout.svelte` | `:212` `isWizard = page.url.pathname.startsWith('/trips/new')` — gilt **nur** für `/trips/new`. `:271` `{#if !isWizard}` blendet `BottomNav` (mobile Tab-Leiste der App) aus. Für `/compare/new` bleibt `BottomNav` sichtbar (AC-6 unerfüllt). `:217-227` zwei weitere `$derived`, die `istAnlegeSeite` bereits **für beide** Routen prüfen (`/trips/new` UND `/compare/new`, `:220-222`) — dieses Muster existiert also schon als Vorbild für eine beidseitige Bedingung. |
| `.claude/hooks/pendant_gate.py` | `trip-new/` und `compare-new/` sind einseitige Bereiche (Pendant-Sperre greift bei neuen Dateien ohne `gz-eigenstaendig:`-Begründung); `shared/` und `atoms/` sind ausgenommen. Eine neue gemeinsame Komponente (z. B. ein Mobile-Header-Baustein) gehört nach `shared/` oder `atoms/`. |
| `.github/ci_e2e_specs.txt:320` | Nur `e2e/issue-661-trip-new-mobile.spec.ts` registriert; kein Eintrag für `compare-new`. Neue/geänderte E2E-Specs zu `/compare/new` müssten ggf. aufgenommen werden. |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | Zählt nur `context ===`/`context !==` in `shared/`. Reine Layout-/Header-Änderungen ohne neue `context`-Verzweigung berühren diese Ratsche voraussichtlich **nicht** (anders als S2a bei `CorridorEditor`). |

## Existing Patterns

- **Zwei Editoren, ein Rahmen-Muster, zweimal implementiert**: Beide nutzen Progressive Tabs
  mit `TAB_DEFS`, Desktop/Mobile-XOR-Mount über `isMobileViewport`/CSS-Klassen. Compare hat
  den Rahmen bereits auf die geteilten Atome (`PageHeader`, `BackLink`, `EditorStickyFooter`)
  umgestellt, Trip nicht — die Angleichungsrichtung ist **Compare-Muster auf Trip übertragen**,
  nicht umgekehrt.
- **`istAnlegeSeite`-Muster in `+layout.svelte`** zeigt bereits, wie eine Bedingung für
  „beide Anlege-Routen" aussieht (`pathname === '/trips/new' || pathname === '/compare/new'`)
  — Vorlage für die Erweiterung von `isWizard`.
- **Fade-Maske** ist ein reines CSS-Attribut (`mask-image`/`-webkit-mask-image`), in Compare
  bereits fertig formuliert (`CompareNewEditor.svelte:434`) — für Trip 1:1 übertragbar.

## Dependencies (Upstream/Downstream)

- **Upstream:** S1 (#2426, live) und S2a (#2442, live) — beide bereits im Trip-Editor verankert,
  keine Berührung durch S2b.
- **Downstream:** keine bekannten Abhängigkeiten anderer Tickets auf den Rahmen-Zustand von
  `/trips/new`/`/compare/new`.
- **Geschwister:** S2c (`?from=`-Vorlage für Compare, AC-4) — unabhängige Dateien, kein
  Datenfluss zwischen S2b und S2c.

## Existing Specs

- `docs/specs/modules/fix_2277_s1_alarme_tab_route.md` — S1-Spec, Formvorlage.
- `docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md` — S2a-Spec, zeigt das
  `createMode`-Spec-Format für denselben Editor.
- **Keine** existierende Spec für S2b — `/30-write-spec` folgt nach `/20-analyse`.
- `docs/analysis/mobile-audit-2026-09-19.md` (Befund P2-1/P4-3, Ticket T4) — Ursprung der
  AC-6/AC-7-Nachträge.

## Risks & Considerations

1. **`makeCancelHandler`/`intentionalCancel`/`beforeNavigate`-Kopplung ist Trip-spezifisch und
   inkompatibel mit `PageHeader`s reinem `back={href}`-Navigationsmuster.** Ein naiver Ersatz
   des Icon-Buttons durch `<PageHeader back={{href:'/trips', label:'Trips'}}>` würde die
   Intentional-Cancel-Markierung überspringen — `beforeNavigate` würde dann bei jedem
   Zurück-Klick einen Autosave auslösen statt eines reinen Abbruchs. Compare kennt dieses
   Verhalten nicht (kein `beforeNavigate` dort). Die Spec muss entweder `PageHeader`/`BackLink`
   um einen Klick-Interception-Mechanismus erweitern (z. B. optionaler `onclick`-Callback vor
   der Navigation) oder für Trip einen eigenen Wrapper um `BackLink` legen, der `intentionalCancel`
   setzt, bevor navigiert wird.
2. **Reihenfolge der letzten beiden geteilten Reiter ist zwischen Trip und Compare vertauscht**:
   Trip = `..., wertebereiche, zeitplan(→VersandTab), alerts(→AlarmeTab)`; Compare =
   `..., idealwerte, alarme(→AlarmeTab), versand(→VersandTab)`. AC-3 verlangt identische
   Reihenfolge/Beschriftung „ab dem zweiten Reiter" — das trifft auf die kind-eigenen ersten
   Reiter (Trip hat drei: Route/Etappen/Wegpunkte; Compare hat zwei: Vergleich/Orte) so nicht
   wörtlich zu, wie CLAUDE.md es selbst festhält („Kind-eigen bleiben nur der erste Reiter
   (Route+Etappen+Wegpunkte vs. Vergleich+Orte)" — Plural bei Trip). **Tech-Lead-Klärung nötig
   in der Analyse-Phase:** (a) ab welchem Reiter „identisch" gilt (ab dem ersten GEMEINSAMEN
   Reiter, nicht ab Index 2), und (b) ob die VersandTab/AlarmeTab-Reihenfolge angeglichen wird
   (welche Richtung: Trip auf Compare oder umgekehrt) oder ob nur Label/Lock-Hint-Text
   vereinheitlicht werden, ohne die Reihenfolge anzufassen (Label „Alerts" vs. „Alarme" ist im
   Übrigen selbst schon uneinheitlich).
3. **`EditorStickyFooter` ist laut eigenem Kommentar für beide Editoren gedacht**, wird aber nur
   von Compare gemountet. Trips Primäraktion sitzt aktuell an zwei Stellen (Desktop-Breadcrumb
   `:493-497`, Mobile-App-Leiste `:520-525`) statt in einem Sticky-Footer — eine Angleichung
   verschiebt strukturell mehr als nur den Header.
4. **`+layout.svelte:212` `isWizard`-Erweiterung auf `/compare/new` wirkt global**: Sie blendet
   `BottomNav` auch für Compare aus. Zu prüfen (Analyse-Phase), ob das für alle
   Compare-Anlege-Zustände gewünscht ist oder ob es Sonderfälle gibt (z. B. `?from=`-Vorlage,
   Fehlerzustände) — aktuelle Instanz von `istAnlegeSeite` (`:220-222`) behandelt bereits beide
   Routen gleich und liefert dafür ein Vorbild.
5. **Pendant-Sperre**: Eine neue gemeinsame Komponente (z. B. für den Mobile-Header) muss nach
   `shared/` oder `atoms/`, nicht nach `trip-new/`/`compare-new/`, sonst blockt `pendant_gate.py`
   ohne `gz-eigenstaendig:`-Begründung.
6. **Kein Backend-/Datenmodell-Eingriff** — reines Frontend-Layout. Kein Cross-User-Risiko, kein
   Read-Modify-Write-Bezug.
7. **LoC-Limit 250**: Header/Footer-Umstellung + Tab-Label/Reihenfolge-Angleichung +
   `+layout.svelte`-Erweiterung + Tests wirken machbar innerhalb des Limits, sofern die
   Reihenfolge-Frage (Punkt 2) NICHT zusätzlich eine Umstrukturierung der Mount-Reihenfolge in
   `TripNewEditor.svelte` (Doppel-Mount Desktop+Mobile je Tab) erzwingt — das würde den Umfang
   erhöhen und wäre ggf. eine eigene Unter-Scheibe wert.

## Analysis

### Type

Feature (Rework/Angleichung bestehender Anlege-Editoren, kein Bugfix).

### Tech-Lead-Entscheidungen (Auflösung der 4 offenen Punkte aus „Risks & Considerations")

1. **Zurück-Button-Konflikt (AC-6):** `BackLink`/`PageHeader` bekommen ein optionales
   `onclick`-Prop. Ist es gesetzt, rendert `BackLink` ein `<button>` statt `<a href>` und ruft
   den Callback direkt auf — der Router wird gar nicht involviert, `beforeNavigate` triggert
   also unabhängig davon korrekt. Trip übergibt seine bestehende `onCancel`-Konstante
   (`TripNewEditor.svelte:471`, bereits vorhanden — `makeCancelHandler()` an sich muss nicht neu
   geschrieben werden). Compare bleibt bei reinem `href` (kein Verhaltenswechsel dort, kein
   Regressionsrisiko). Das ist die geteilte, robuste Lösung im Sinne der Code-Teilungs-Vorgabe.
2. **Reiter-Reihenfolge (AC-3) — Scope-Schnitt:** AC-3 wird **aus S2b herausgeschnitten**.
   Begründung: „ab dem zweiten Reiter identisch" ist wörtlich nicht anwendbar (Trip hat drei
   eigene Reiter, Compare zwei) und braucht vor der Umsetzung eine Klärung der Lesart (vermutlich
   „ab dem ersten GEMEINSAMEN Reiter"). Die volle Umsetzung ist zudem kein Layout-Thema mehr,
   sondern ein Logik-Umbau in `TripNewEditor.svelte` (TAB_DEFS-Reihenfolge tauschen, Labels
   „Alerts"→„Alarme" angleichen, Lock-Hint-Kette neu verketten, Save-Gating-Text ändern) mit
   eigenem LoC- und Testbedarf. S2b bleibt damit auf **AC-6 + AC-7** (mobiler Rahmen) begrenzt;
   AC-3 wird als Folge-Scheibe unter #2277 zurückgestellt (Arbeitstitel S2b-2 oder S3 — Issue
   bleibt offen, kein neues Ticket nötig, analog zum bisherigen S1/S2a-Vorgehen).
3. **EditorStickyFooter:** Trip übernimmt dieselbe Aufteilung wie Compare — `PageHeader` trägt
   nur Zurück+Titel, die Primäraktion wandert in den bereits als „für beide Editoren gedacht"
   kommentierten `EditorStickyFooter`. Das ersetzt die Desktop-Breadcrumb-Buttons (:493-497) und
   die Mobile-Appbar-Save-Taste (:520-525) durch den geteilten Baustein — erfüllt AC-6 wörtlich
   („eine Kopfleiste aus einem Baustein") und vermeidet doppelte Pflege von Save-Logik/Text.
4. **isWizard/BottomNav (AC-6):** `isWizard` in `+layout.svelte:212` wird durch das bereits
   existierende `istAnlegeSeite`-Derived (:220-222, prüft schon beide Routen) ersetzt statt ein
   zweites paralleles Flag zu pflegen. `?from=` (Compare-Vorlage, S2c) ist ein Query-Parameter
   und berührt den Pathname-Check nicht — kein Konflikt mit der Schwester-Scheibe. Zusätzlich:
   `EditorStickyFooter` bekommt/behält ein `navClearance`-Verhalten, damit beim Ausblenden der
   BottomNav kein reservierter Leerraum unten stehen bleibt (Compare-Fall).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/atoms/BackLink.svelte` | MODIFY | Optionales `onclick`-Prop; bei Vorhandensein `<button>` statt `<a href>`, kein Router-Trigger |
| `frontend/src/lib/components/atoms/PageHeader.svelte` | MODIFY | `onclick`-Prop zu `back`-Objekt durchreichen |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Desktop-Breadcrumb + Mobile-Appbar durch `PageHeader`+`EditorStickyFooter` ersetzen, `onCancel` an `BackLink.onclick`, Tab-Streifen-Fade-Maske ergänzen; Testids `tn-mobile-appbar`/`tn-mobile-save`/`tn-desktop-breadcrumb`/`tn-mobile-tabbar` 1:1 erhalten |
| `frontend/src/routes/+layout.svelte` | MODIFY | `isWizard` durch `istAnlegeSeite` ersetzen (beide Anlege-Routen) |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | MODIFY (ggf.) | `navClearance`-Verhalten für Compare absichern, falls nicht bereits vorhanden |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY (klein) | Ggf. `navClearance`-Prop setzen; sonst nur Referenz/keine funktionale Änderung |
| `frontend/e2e/issue-661-trip-new-mobile.spec.ts` | MODIFY | Testids/Selektoren an neues Markup anpassen, zusätzliche Assertion „kein Autosave-Request beim Zurück-Tap" |

### Scope Assessment

- Files: 6-7 (davon 2 nur klein berührt)
- Estimated LoC: ca. +100/-120 bis +160/-160 (Ersatz von Inline-Markup durch Baustein-Aufrufe,
  netto eher Reduktion in `TripNewEditor.svelte`)
- Risk Level: MEDIUM — nicht wegen Komplexität, sondern wegen der Autosave-Kopplung
  (`beforeNavigate`/`intentionalCancel`) und der Testid-Abhängigkeit von `issue-661-trip-new-mobile.spec.ts`;
  beides ist durch den gewählten Ansatz (Button statt Router-Navigation, Testids erhalten)
  strukturell entschärft, nicht nur getestet
- LoC-Limit 250 reicht voraussichtlich ohne Override, solange AC-3 draußen bleibt (siehe
  Tech-Lead-Entscheidung 2)

### Technical Approach

Siehe „Tech-Lead-Entscheidungen" oben. Reihenfolge der Umsetzung: (1) `BackLink`/`PageHeader`
um `onclick`-Prop erweitern (Fundament, regressionsfrei für Compare) → (2) Trip-Appbar auf
`PageHeader`+`onCancel` umstellen, Testids erhalten → (3) im selben Zug Trip-Save/Cancel auf
`EditorStickyFooter` umstellen → (4) Fade-Maske in Trips Tab-Streifen ergänzen → (5) `isWizard`
durch `istAnlegeSeite` ersetzen, `navClearance` in Compare prüfen → (6) E2E-661 anpassen und um
Autosave-Regressions-Assertion erweitern.

Vor Schritt (2): `grep -rn "tn-mobile-\|cm-mobile-" frontend/e2e frontend/src` fahren, um alle
Testid-Abhängigkeiten vollständig zu erfassen, bevor Markup ersetzt wird.

### Dependencies

Upstream: S1 (#2426) und S2a (#2442) live, keine Berührung. Downstream: keine. Geschwister:
S2c (`?from=`-Vorlage, AC-4) unabhängig — Query-Parameter, keine Pathname-Kollision mit der
`isWizard`/`istAnlegeSeite`-Änderung dieser Scheibe.

### Open Questions

- [x] Zurück-Button-Konflikt mit `beforeNavigate` — gelöst durch `onclick`-Button statt Href-Navigation
- [x] AC-3-Reiter-Reihenfolge — aus S2b herausgeschnitten, eigene Folge-Scheibe unter #2277
- [x] `EditorStickyFooter`-Umfang — Trip übernimmt volle Umstellung (Header + Footer)
- [x] `isWizard`/BottomNav — Wiederverwendung von `istAnlegeSeite`, kein Sonderfall durch S2c
