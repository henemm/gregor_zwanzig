# Context: rework-2837-hub-kopf-anlege-rahmen

Issue #2837, Teil von Epic #2345, letzte offene Abnahme **DoD-2 Oberfläche**. Stand `4f3309cd4`, 2026-11-06.

## Request Summary
Hub-Kopf (`/trips/[id]` vs. `/compare/[id]`) und Anlege-Rahmen (`/trips/new` vs. `/compare/new`) sollen bei Trip und Ortsvergleich **ein** Baustein mit `context` sein. Gleich werden: Lage/Farbe „Senden“, Breadcrumb, Status-Anzeige, Region, Kebab-Symbol, Reiter-Zähler, Lage der Speicher-Aktionen, Weiter-Knopf, Titel-Label. Nur fachlich Verschiedenes darf abweichen. Abschluss: Screenshot-Paar je Fläche (Desktop 1440 / Mobil 390) als Fresh-Eyes-Nachweis im Epic.

**Nicht im Scope:** Aktivitätsprofil-Auswahl beim Anlegen (läuft in #2792, parallele Sitzung `feat-2792-s1c4b-umschalten`, Phase 6). Randbefunde (Badge „ALLE KANÄLE“ abgeschnitten, Begriffe Wertebereiche/Ideal-Werte, Testdaten „Validator-1025 Compare“) gehören nicht hierher.

Pfade relativ zu `frontend/src/`.

## Hub-Kopf: Ist-Stand

### Geteilt schon heute
`lib/components/shared/subscription-header/SubscriptionHeader.svelte` (178 Z.)
- Props :21-42: `kind`, `name`, `region`, `profile`, `profileOptions`, `profileLabel`, `regionMaxLength`, `testidPrefix`, `titleTestid`, `titleSize: 30|38`, `saveController`, `onSaveField`.
- Snippets :37-41: `eyebrow`, `namePrefix`, `badges`, `actions`, `meta`. Ein Markup ohne `kind`-Zweig (`data-kind` :116).
- `<h1>` :123, `badges` :126 + `actions` :127 in der Titelzeile (**beide Seiten übergeben `actions` nicht**). Region `{region || '—'}` :135 (gilt für beide). `meta` :140, Profil :145-171, SaveIndicator :176-178.

### Trip (drei Schichten)
- `routes/trips/[id]/+page.svelte` Leiste `trip-detail-breadcrumb-bar` :311-357: mobil `BackLink` :314; Breadcrumb „Trips / {shortcode ?? name}“ :315-319; **Senden** `Btn variant="accent" size="sm" data-testid="subscription-hub-send"` :322-330 (gesperrt draft/archived); Kebab mobil eigener Button mit `EllipsisVerticalIcon` :331-342, Desktop `SubscriptionKebab` :343-348; Meldungen :349-357; CSS :425-467. Danach `<TripHeader>` :359, `<TripTabs badges={{}}>` :361.
- `lib/components/trip-detail/TripHeader.svelte`: Hülle `<header class="trip-header">` :121; `SubscriptionHeader kind="trip" titleSize={38} titleTestid="trip-detail-h1"` :124-143; eyebrow = Datum :137-139, namePrefix = Shortcode :140-142; **Status in eigener Zeile außerhalb** :145-150 (`daysLabel` + `TripStatusBadge`); Meta km/Hm :152-155; Kennzahl-Kacheln mobil :160-170; totes CSS `.header-actions`/`.briefing-msg` :217-226.
- `TripStatusBadge.svelte:16-23,39` (`Pill tone` active→accent, testid `trip-detail-status-badge`).

### Vergleich
`routes/compare/[id]/+page.svelte`
- Breadcrumb nur Desktop :359-363 `ORTS-VERGLEICHE` (Link) / „Hub“ (`vergleich.hub.krumel`, `i18n/messages/de/vergleich.json:36`); mobil `BackLink` „Vergleiche“ :364.
- `SubscriptionHeader kind="vergleich" testidPrefix="compare-hub"` :367-397 (Titel 30 px); eyebrow nur mobil „Orts-Vergleich · Hub“ :379-382 (`vergleich.json:37`); **Status als Badge** `CompareStatusPill` + Laufzeit :383-388; meta = Orte-Anzahl :389-396.
- Aktionsspalte neben dem Baustein :401-424: draft → „Setup abschließen“ `Btn primary` :402-403; sonst **Senden** `Btn variant="primary"` (schwarz) :406-408; Desktop `SubscriptionKebab` :410-412; mobil Button `MoreHorizontalIcon` :413-423.
- `CompareStatusPill.svelte:25-40`.

### Reiter-Zähler
Beide nutzen `lib/components/mobile/MTabBar.svelte`. Trip `TripTabs.svelte:185-190` ohne `size` → Badge `--g-accent` gefüllt (`MTabBar.svelte:134-143`); Vergleich `compare/CompareTabs.svelte:678-684` mit `size="sm"` → neutral `--g-paper-deep`/`--g-ink-3` (:161-167); mobil :210-220. Badge-Werte Trip `TripTabs.svelte:60-66,93`, Vergleich nur Orte `CompareTabs.svelte:151-158`.

### Senden-Farbe
`app.css`: `--g-accent #c45a2a` :99, `--g-ink #1a1a18` :101; `Btn accent` :364-371, `primary` :355-362, `quiet` :421-428, `link` :409-419. `Btn` = `lib/components/ui/btn/Btn.svelte`.

## Anlegen: Ist-Stand
Routen sind Hüllen: `routes/trips/new/+page.svelte:9`, `routes/compare/new/+page.svelte:26`.

### `lib/components/trip-new/TripNewEditor.svelte` (1320 Z.)
- Desktop-Nav :556-558 `PageHeader back={{href:'/trips',label:'Trips',onclick:onCancel}} compact` (testid `tn-desktop-breadcrumb`) — nur Zurück-Link, Label hart kodiert. Mobil :561-568.
- Label :572 `trip.anlegen.titel` = „Neue Trip anlegen“ (`trip.json:231`; `neuer_trip` = „Neue Trip“ :230 — beide grammatisch falsch). h1 :573-575, Fortschritt :577-586.
- Weiter :727-740 roher `<button data-testid="trip-new-continue-etappen">`, Inline `--g-accent` (`trip.anlegen.etappen_anlegen` `trip.json:250`). Weitere Weiter-Füße :939, :953 (`Btn accent`).
- Speicherleiste Desktop **unten** :985-998 `EditorStickyFooter context="route"` (`tn-desktop-footer`): Hinweis, `StandardwerteSpeichernKnopf` (`trip-new-standardwerte-btn`), roher `<button data-testid="trip-new-save-btn">` Inline `--g-ink` („Trip speichern“, `trip.json:276`). Kein Abbrechen-Knopf (Abbruch über Zurück-Link `onCancel`).
- Mobil-Footer :1234-1273 (`tn-mobile-footer`, `MBtn`).

### `lib/components/compare-new/CompareNewEditor.svelte` (766 Z.)
- Desktop-Kopfleiste **oben** :454-475: Breadcrumb-Text (unverlinkt) „Orts-Vergleiche / Neuer Vergleich“ :455-459; rechts Hinweis + `StandardwerteSpeichernKnopf` (`compare-editor-standardwerte`) :461-464; Abbrechen `Btn ghost sm href="/compare"` :465; „Briefing aktivieren“ `Btn primary` (`compare-editor-activate`, gesperrt `quiet`) :466-473.
- Label :479 `home.planung.neuer_orts_vergleich` (`home.json:51`). h1 :480.
- Weiter :559 `Btn data-testid="compare-editor-continue-orte" variant={canContinue?'accent':'quiet'}` (gesperrt wirkt wie Textlink; `vergleich.neu.orte_hinzufuegen` `vergleich.json:124`). Weitere Füße :569, :581, :590.
- Mobil: PageHeader :607, `EditorStickyFooter context="vergleich" testid="cm-mobile-cta"` :686-704.

### Schon geteilt (`lib/components/shared/`)
- `EditorStickyFooter.svelte` (Props `context`, `testid`, `navClearance`, `children` :10-18; `context` nur Datenmarke). Nutzer: TripNewEditor :985, :1234; CompareNewEditor :686 (nur mobil).
- `StandardwerteSpeichernKnopf.svelte` (beide).
- `anlegeLockEngine.ts` (`tailUnlocked`, `tailDone`, `canFinish`, `canFinishMitStandardwerten`, `progressCount` :32-70).
- `wizardHelpers.ts` (Datum/Id, kein UI). `subscriptionTabs.ts:88` `anlegeKette(kind)`.
- Atom `atoms/PageHeader.svelte` (Props `back`, `eyebrow`, `title`, `right`, `compact` :8-23).

## Existing Patterns
- Vorbild „ein Baustein mit `context`“: `shared/hub-uebersicht/HubUebersicht.svelte` (Spec `feat_2682_hub_uebersicht_geteilt.md`), Tab-Organismen in `shared/` (Versand, Layout, Wertebereiche, Alarme).
- `SubscriptionHeader` ist bereits kontextneutral (ein Markup, Snippets). Der Weg liegt nahe: Seiten-Chrome (Breadcrumb, Senden, Kebab, Status) in den geteilten Baustein bzw. einen neuen geteilten Hub-Kopf-Rahmen heben; fachlich Verschiedenes (Datum/Shortcode/km beim Trip, Orte-Anzahl beim Vergleich, „Tag x von y“) über Snippets.
- Anlegen: Kopf (Breadcrumb + Label + h1 + Fortschritt) und Speicherleiste als geteilter Rahmen unter `shared/`; Inhalte der Schritte bleiben in den Editoren.

## Dependencies
- Upstream: `SubscriptionHeader`, `SubscriptionKebab`, `MTabBar`, `Btn`/`MBtn`, `PageHeader`, `BackLink`, `EditorStickyFooter`, `StandardwerteSpeichernKnopf`, `anlegeLockEngine`, i18n-Katalog (`trip.json`, `vergleich.json`, `home.json`).
- Downstream: beide Hub-Seiten, beide Anlege-Editoren, E2E-Selektoren `frontend/e2e/helpers.ts` (`HUB_KINDS` :609, `HUB_SEL` :617, `ANLEGE_SEL` :763-885).

## Bestehende Tests (werden berührt)
Unit (`node --test`):
- `shared/__tests__/subscription_header_kontextneutral.test.ts`, `subscription_header_einmal_gerendert.test.ts` (genau ein `<header class="trip-header">` :229), `subscription_header_bedienlogik.test.ts`, `aktionsmodell_seiten_bindung.test.ts` (Senden öffnet nur Dialog :107-118; Draft-Bedingung Vergleich :266-267).
- `routes/compare/__tests__/bug_589_breadcrumb_links.test.ts` (ORTS-VERGLEICHE Link, „Hub“ kein Link).
- `trip-detail/TripHeader.issue699.test.ts` (keine zweite Breadcrumb im TripHeader), `TripHeader.spacing`, `TripHeader.mobile-metrics`.
- `trip-new/__tests__/trip_new_mobile_rahmen_angleichung.test.ts` (ein back-link in `tn-desktop-breadcrumb`, Save-Btn im route-Footer), `compare-new/__tests__/compare_new_footer_nav_clearance.test.ts`, `shared/__tests__/standardwerte_knopf_geteilt.test.ts` (:98-102 „Trip speichern“), `trip_new_reiterleiste_besuchs_flags.test.ts`, `compare_anlege_freischaltung.test.ts`, `trip_anlegen_sprache.test.ts` (:55 „Neue Trip anlegen“), `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`.

E2E (`frontend/e2e/`): `hub-anlegen-ablauf.spec.ts` (AN-1..15, Weiter-Labels :138/:144), `hub-kopf-aufbau.spec.ts` (KA-7 :502/:514, KA-10 :442, Senden :346/:407), `hub-kopf-bearbeiten.spec.ts`, **`hub-tab-bar.spec.ts` HT-8 :202-223 erzwingt unterschiedliche Badge-Optik je Art** (muss umgedreht werden), `issue-661-trip-new-mobile`, `standardwerte-und-hilfe`, `compare-editor-fidelity-s8d`, `trip-header-btn-migration`, `issue-302-trip-detail-redesign`, `issue-336-status-dedup`, `issue-616-trip-one-surface`, `trip-detail-actions`.

## Existing Specs / ADRs
- `docs/specs/modules/feat_2284_s1_subscription_header.md` — **Entscheidung 6 (:94) „Seiten-Chrome bleibt in der Seite“** (Breadcrumb, BackLink, Senden, Kebab); Out of Scope :238-250. → Diese Entscheidung wird durch #2837 aufgehoben/erweitert; muss in der neuen Spec ausdrücklich benannt werden.
- `feat_2284_s2_trip_kopf.md` — Entscheidungen 7/8 :116-119 („TripHeader bleibt Hülle“, Status/Meta außerhalb des Bausteins) → ebenfalls betroffen.
- `feat_2347_s2_paritaets_e2e.md`, `feat_2347_s4_paritaets_e2e.md`, `feat_1301_f2a_compare_new_trip_pattern.md`, `fix_2277_s2b_mobile_rahmen_angleichung.md`, `feat_2277_s4_anlege_lockengine.md`, `feat_2727_compare_wizardstate_abloesen.md`, `feat_2682_hub_uebersicht_geteilt.md`, `mobile_tab_leisten_mtabbar.md`, `feat_1481b_pendant_gate.md`, `feat_2792_s1_profil_ampel.md`.
- ADR-0097 (Trip/Ortsvergleich-Code-Teilung), ADR-0032 (Wizard-Abschaffung), ADR-0109/0107 (vorgeschlagen).

## Gates
- Pendant-Sperre `.claude/hooks/pendant_gate.py` (Doku `docs/reference/gates_und_ratschen.md:107-160`): neue Dateien unter `components/{compare,compare-new,trip-detail,trip-new}/**` oder `Compare*`/`Trip*`-Namen mit Gegenstück blockieren den Commit → neue Bausteine gehören nach `shared/**`. `BEKANNTE_PAARE` :74 darf nur schrumpfen.
- E2E-Paritäts-Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`: `*compare*.spec.ts` braucht `HUB_KINDS`-Schleife.
- Pflicht-Regel: Zwei-Nutzer-Test nur für datenbewegende Endpoints — hier reine Oberfläche, kein neuer Endpoint.

## Risks & Considerations
1. **Konflikt mit #2792** (paralleler Umbau der Profil-Auswahl in denselben Editoren TripNewEditor/CompareNewEditor) → Merge-Konflikte; Profil-Bereich nicht anfassen, Rebase vor Phase 6.
2. **Welche Variante gewinnt** (orange vs. schwarz Senden, Speicherleiste oben vs. unten, Badge vs. eigene Statuszeile, Zähler orange vs. grau, Kebab vertikal vs. horizontal, Abbrechen ja/nein) ist eine Produktentscheidung → in der Analyse mit Begründung aus Gregors eigener Ordnung (Design-System, bestehende Muster, Kontrastprinzip) empfehlen und in der Spec zur Freigabe vorlegen.
3. Bestehende Spec-Entscheidungen (#2284 S1 Entscheidung 6, S2 Entscheidung 7/8) werden abgelöst → in der Spec ausdrücklich nennen; prüfen, ob ein ADR nötig ist (Editor-Rahmen ist Entscheidungsfläche).
4. Viele Tests verankern die jetzige Divergenz (HT-8, `bug_589`, `TripHeader.issue699`, `trip_anlegen_sprache`, `ANLEGE_SEL.abbrechen`) → bewusst umdrehen, nicht löschen.
5. Fachlich Verschiedenes bleibt: Datum/Shortcode/km/Hm/„Tag x von y“ (Trip), Orte-Anzahl (Vergleich), „Setup abschließen“ bei Vergleich-draft (prüfen, ob Trip-draft ein Pendant braucht), Abschluss-Label „Trip speichern“ vs. „Briefing aktivieren“.
6. Rohe `<button>` mit Inline-Farben im TripNewEditor (:737, :994) → auf `Btn`-Varianten umstellen.
7. Mobil und Desktop getrennt prüfen (1440/390); Kontrast WCAG-AA.

## Analysis

### Type
Rework (Feature-Charakter: Oberflächen-Vereinheitlichung, kein Fehlverhalten). Abschluss von Epic #2345 DoD-2.

### Gemessene Grundlagen (Analyse 2026-11-06)
- `Btn primary` (schwarz, `--g-ink`) 33× im Produkt, `accent` (orange) 13×. Hauptaktionen/Speichern sind fast überall `primary` (Listen-„Neuer Trip" `routes/+page.svelte:724`, WeatherMetricsTab, EditStagesPanel, LocationForm); `accent` sitzt bei Weiter-/Onboarding-CTAs.
- Kontrast nachgerechnet: Weiß auf `#c45a2a` = **4,34:1** (unter WCAG-AA 4,5:1 für kleinen Text); Ink auf Paper ≈ 15:1; neutrales Badge `ink-3 #6b675c` auf `paper-deep #ecead9` ≈ 4,7:1 (besteht).
- Spannung im Design-System: `design_system.md:64` nennt `--g-accent` „Primär-Akzent (CTA …)", `:22` stellt Lesbarkeit/Kontrast über Ästhetik (PO-bestätigt). Spec muss die Abwägung ausdrücklich begründen.
- Kebab: `molecules/SubscriptionKebab.svelte:6,43` und `SubscriptionCard.svelte:227` nutzen `EllipsisVerticalIcon`; einzig Compare mobil (`compare/[id]/+page.svelte:421`) nutzt `MoreHorizontalIcon`.
- Speicherleisten: `EditorStickyFooter` (unten, sticky) ist schon bei 3 von 4 Anlege-Flächen im Einsatz (Trip Desktop+Mobil, Compare Mobil); nur Compare Desktop sitzt oben.
- Region-Platzhalter `{region || '—'}` liegt bereits im geteilten `SubscriptionHeader:135` → kein Code nötig, nur im Screenshot-Paar prüfen.

### Divergenzpunkte und Empfehlung (zur Freigabe in der Spec vorlegen)
| Punkt | Trip-Ist | Vergleich-Ist | Empfehlung | Begründung |
|---|---|---|---|---|
| Senden-Farbe | `accent` orange | `primary` schwarz | **`primary` (schwarz) für beide** | Kontrast AA (4,34 vs. 15:1), Mehrheitsmuster für Hauptaktionen; Orange bleibt „Weiter"/Aktiv-Zustand |
| Senden-Lage | Kopfleiste oben rechts neben Kebab | Aktionsspalte neben Titel | **Kopfleiste (Breadcrumb · Senden · Kebab) für beide**, mobil 44 px Touch-Höhe | Eine Leiste, unabhängig vom Titel-Umbruch |
| Breadcrumb Hub | „Trips / {shortcode ?? name}", Elternteil verlinkt | nur Desktop „ORTS-VERGLEICHE / Hub" | **„Trips / {shortcode ?? name}" bzw. „Orts-Vergleiche / {name}"**, Elternteil verlinkt; mobil beide `BackLink` | „Hub" trägt keine Orientierung; `bug_589` (Link + Nicht-Link) bleibt inhaltlich gültig |
| Status | eigene Zeile unter dem Kopf (`daysLabel` + `TripStatusBadge`) | Badge in der Titelzeile + Laufzeit | **Badge in der Titelzeile (`badges`-Snippet) für beide**; „Tag x von y"/Laufzeit als fachlicher Zusatz daneben | Slot existiert schon; eine Zeile weniger. Mobil 390 px auf Umbruch prüfen; `issue-336-status-dedup` bewacht die heutige Zeile |
| Region | `—` | `—` | schon gleich | — |
| Kebab mobil | vertikal | horizontal | **vertikal**, Mobil-Button in `SubscriptionKebab` heben | Alle übrigen Flächen vertikal |
| Reiter-Zähler | orange gefüllt | grau neutral (`size="sm"`) | **neutral für beide** als eigene `MTabBar`-Badge-Variante (nicht über `size`) | Orange-Badge 12 px fällt AA durch; Orange bleibt Aktiv-Unterstrich. HT-8 umdrehen |
| Speicherleiste Anlegen | Desktop unten sticky | Desktop oben | **unten sticky (`EditorStickyFooter`) für beide** | 3 von 4 Flächen; Hauptknopf bleibt sichtbar |
| Abbrechen | nein (nur Zurück-Link `onCancel`) | ja `Btn ghost` | **ja für beide**, `ghost` links vom Hauptknopf in der Leiste | Ein Muster; `onCancel`-Wächter bleibt |
| Breadcrumb Anlegen | nur Zurück-Link „Trips" (hart kodiert) | „Orts-Vergleiche / Neuer Vergleich" unverlinkt | **„Trips / Neuer Trip" bzw. „Orts-Vergleiche / Neuer Vergleich"**, Elternteil verlinkt (mit `onCancel`-Wächter), Texte aus i18n | Spiegelt den Hub-Kopf |
| Weiter-Knopf | roher `<button>` Inline-Orange | `Btn accent`, gesperrt `quiet` (wirkt wie Textlink) | **`Btn variant="accent"` mit sichtbarem `disabled`-Zustand** für beide | Ein Zustand, kein Textlink; Inline-Farbe weg |
| Label | „Neue Trip anlegen" (falsch) | „Neuer Orts-Vergleich" | **„Neuer Trip" / „Neuer Orts-Vergleich"** aus einem Schlüsselpaar | Grammatik; `trip_anlegen_sprache.test.ts:55` umstellen |

Fachlich verschieden und bleibt: Datum, Shortcode, km/Hm, „Tag x von y" (Trip), Orte-Anzahl (Vergleich), Draft-Logik (Trip-Senden gesperrt / Vergleich „Setup abschließen"), Abschluss-Label („Trip speichern" / „Briefing aktivieren"), Schritt-Inhalte, Profil-Bereich (#2792).

### Affected Files (with changes)
| File (unter `frontend/src/`) | Change | Description |
|---|---|---|
| `lib/components/shared/hub-kopf/HubKopf.svelte` | CREATE | Leiste (Breadcrumb, Senden `primary`, Kebab, Meldungen) + `SubscriptionHeader`; Props `context`, `parent`, `crumb`, `sendDisabled`, `onSend`, Kebab-Daten, `testidPrefix`; Snippets `status`, `eyebrow`, `namePrefix`, `meta` |
| `lib/components/molecules/SubscriptionKebab.svelte` | MODIFY | Mobil-Button (vertikal) übernehmen |
| `lib/components/mobile/MTabBar.svelte` | MODIFY | neutrale Badge-Variante als Standard |
| `routes/trips/[id]/+page.svelte` | MODIFY | Leiste :311-357 → `HubKopf` |
| `routes/compare/[id]/+page.svelte` | MODIFY | Breadcrumb/Aktionsspalte :359-424 → `HubKopf` |
| `lib/components/trip-detail/TripHeader.svelte` | MODIFY | `status-line` raus (→ `badges`), totes CSS raus, Hülle/Meta/Mobil-Kacheln bleiben |
| `lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | MODIFY | Badge-Variante vereinheitlichen |
| `lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | CREATE | Kopf (Breadcrumb, Label, h1, Fortschritt) + `EditorStickyFooter` (auch Desktop) mit Abbrechen/Hinweis/Standardwerte/Abschluss; Snippets `children`, `leiste`, `abschluss` |
| `lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Kopf/Fuß → `AnlegeRahmen`; rohe Buttons → `Btn` |
| `lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Kopfleiste oben → `AnlegeRahmen`; Weiter gesperrt → `disabled` |
| `lib/i18n/messages/{de,en}/trip.json`, `vergleich.json` | MODIFY | Label/Breadcrumb-Schlüssel |
| `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` | CREATE | löst #2284 S1 Entscheidung 6 und S2 Entscheidungen 7/8 ab, schreibt ADR-0097 fort |
| Unit-Tests (siehe „Bestehende Tests") | MODIFY | Divergenz-Zusicherungen umdrehen, nicht löschen |
| E2E `hub-tab-bar` HT-8, `hub-kopf-aufbau` KA-7/KA-10/Senden, `hub-anlegen-ablauf` Weiter-Labels, `helpers.ts` `ANLEGE_SEL`/`HUB_SEL` | MODIFY | auf Gleichheit umstellen, `HUB_KINDS`-Schleifen |

### Scope Assessment
- Zwei Slices empfohlen:
  - **Slice A Hub-Kopf** (+ ADR, Reiter-Zähler, Kebab): ~8 Dateien, netto ≈ +350 LoC inkl. Tests. Konfliktfrei zu #2792.
  - **Slice B Anlege-Rahmen**: ~6 Dateien, netto ≈ +400 LoC inkl. Tests. Berührt dieselben Editoren wie #2792 → nach dessen Merge rebasen.
- Risk Level: **MEDIUM** (rein Oberfläche, kein Datenpfad/Endpoint; aber viele E2E-/Unit-Zusicherungen und Parallelarbeit #2792).

### Technical Approach
Vorbild `shared/hub-uebersicht/HubUebersicht.svelte`: ein Markup, `context` nur als Datenmarke/Textwahl, Fachliches über Snippets. Neue Dateien ausschließlich unter `shared/` (Pendant-Gate). Testids stabil halten, wo möglich (`subscription-hub-send`, `trip-new-save-btn`, `tn-desktop-footer`); neue gemeinsame testids per `testidPrefix`. Abschluss je Slice: Screenshot-Paar Desktop 1440 / Mobil 390 als Fresh-Eyes-Nachweis im Epic.

### Dependencies
Upstream `SubscriptionHeader`, `SubscriptionKebab`, `MTabBar`, `Btn`/`MBtn`, `BackLink`, `EditorStickyFooter`, `StandardwerteSpeichernKnopf`, `anlegeLockEngine`, i18n-Katalog. Downstream beide Hub-Seiten, beide Anlege-Editoren, `frontend/e2e/helpers.ts`. Parallel: #2792 (TripNewEditor/CompareNewEditor, Profil-Bereich nicht anfassen).

### Risks
1. #2792-Konflikt in Slice B → Slice A zuerst, B nach Rebase.
2. Senden schwarz widerspricht dem Wortlaut `design_system.md:64` („CTA = Akzent") → Begründung über Kontrastprinzip :22 in Spec und ADR; `design_system.md` nachziehen (Accent = Weiter/Aktiv, Hauptaktion = Ink).
3. Status-Badge in der Titelzeile kann mobil bei langen Namen umbrechen → 390-px-Screenshot.
4. Divergenz-verankernde Tests (HT-8, `bug_589`, `TripHeader.issue699`, `issue-336-status-dedup`, `trip_anlegen_sprache`, `ANLEGE_SEL.abbrechen`) bewusst umdrehen.
5. Draft-Trip-Pendant zu „Setup abschließen" ist Produktfrage außerhalb dieser Angleichung (nicht in Scope).

### Open Questions
- [ ] Produktentscheidungen der Tabelle oben (insb. Senden schwarz statt orange, Status als Badge, Abbrechen auch beim Trip) werden in der Spec mit Begründung zur Freigabe vorgelegt — keine Vorab-Rückfrage nötig.

## RED-Übergabe an /50-implement (2026-11-06)

RED-Stand: 82/396 Unit-Tests rot (fachlich bzw. HubKopf fehlt), 7 Doku-Tests rot (`tests/unit/test_hub_kopf_doku_2837.py`), E2E `hub-kopf-paritaet-compare-trip.spec.ts` geschrieben, nicht ausgeführt (in `.github/ci_e2e_specs.txt`, `E2E_MIN_SPECS` 73→74 ⇒ `e2e`-Job rot bis GREEN). Beleg: `docs/artifacts/rework-2837-hub-kopf-anlege-rahmen/test-red-output.txt`.

**Tech-Lead-Entscheidung Testid-Konflikt:** Spec-Entscheidung 10 gilt, `trip-detail-breadcrumb-bar` bleibt stabil. Umsetzung nach dem Vorbild `titleTestid` im `SubscriptionHeader`: `HubKopf` bekommt einen optionalen Prop (z. B. `leisteTestid`), gerendert als **inneres** Element um den Leisten-Inhalt; die Trip-Seite übergibt `trip-detail-breadcrumb-bar`. Die Leiste selbst trägt `hub-kopf-leiste` für beide Arten. Kein Umbenennen der ca. 8 E2E-Specs (`trip-detail-actions` AC-10/11, `issue-592-593`, `send-in-flight-guard`, `issue-767-768`, `pwa-offline-ansicht-mit-stand`, `trip-detail-overview-left`, `trip-hub-kopf-region-aktivitaet` AC-13).

**Von RED festgelegte Schnittstelle:** HubKopf-Props zusätzlich `actions`, `onSelect`, `mobil`, `onSheetOpen`, `onSetup`; `SubscriptionKebab` neu `mobil`, `onSheetOpen` (mobil eigener 44×44-Knopf, vertikal). Feste testids `hub-kopf-leiste`, `hub-kopf-breadcrumb`, `hub-kopf-status`; `data-kind` = `context`. Kein `{#if}` nach `context` im Template. `e2e/helpers.ts` nur neue Exporte `HUB_KOPF_SEL`, `TOKEN_RGB`, `kontrastVerhaeltnis`.

**Freigegeben unter ADR-0110 (bewusst):** Goldens f9 `hub_seite`/`kopf_status` und f10 `hub_seite` werden in GREEN neu erzeugt; F10_ANKER `vergleich.hub.krumel`/`vergleich.hub.eyebrow` und `deutsch_unveraendert.test.ts` (NEU_IN_F10) nachziehen. **Falle:** die Prüfstände f9/f10 ersetzen Zustandszeilen der Seiten wörtlich (`let mobil = $state(false);`, `isSending`, `sendStatus`, `errorMsg`, `sendMsg`, `pauseError`). Diese Zeilen nicht verschieben oder umformulieren, sonst bricht der Import und alle Seiten-Tests werden aus falschem Grund rot.

**Ehrlich vermerkt:** `issue_582` AC-4c bleibt Quelltext-Grep (wie vorher, nur umgehängt); Messaufbau-Zeile in `vergleich_hub_sprache` ist nicht mehr breadcrumb-spezifisch. E2E-Annahmen: HP-13 Sprache per `PUT /api/auth/profile {language}`, HP-3 Entwürfe (`location_ids: []`, Trip-Etappe ohne Datum), HP-7 Aktionsblatt über `role=dialog` + `subscription-action-*`.
