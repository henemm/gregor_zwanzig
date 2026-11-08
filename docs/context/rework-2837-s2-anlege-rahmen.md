# Context: rework-2837-s2-anlege-rahmen

## Request Summary
Issue #2837, Scheibe **S2** (Epic #2345, DoD-2): Der Anlege-Rahmen von `/trips/new` und `/compare/new` wird **ein** Baustein mit `context`. Gleich werden: Navigation oben (Breadcrumb/Zurück), Eyebrow-Label, Lage der Speicher-Aktionen, Abbrechen, Weiter-Knopf (Typ, Farbe, Gesperrt-Zustand). Nur fachlich Verschiedenes darf abweichen. Abschluss: Fresh-Eyes-Screenshot-Paar (1440/390 px) im Epic. Danach bleibt im Epic nur #2845 (Reiterleiste Desktop).

**Vorbedingung erfüllt:** #2792 S1c-4b ist gemergt (`463f5c386`, Doku `0d958e181`), #2792 geschlossen. Rebase-Konflikt mit dem Profil-Umbau entfällt damit.

**Nicht im Scope:** Profil-Auswahl beim Anlegen (Chips vs. Karten, #2792), Reiterleiste Desktop (#2845), Inhalte der einzelnen Schritte (Etappen-Tab, Orte-Tab).

**Vorlauf:** S1 (PR #2839) und S1b (PR #2854, live `17a2321`) haben den Hub-Kopf geliefert. ADR-0110 `hub-kopf-und-anlege-rahmen-ein-baustein` gilt laut S1-Spec ausdrücklich **auch für S2** (kein zweites ADR nötig; ggf. Nachtrag). Vorgemerkte Entscheidungen (S1-Spec :201): Hauptaktion schwarz (Ink), Weiter orange (Accent) mit sichtbarem Gesperrt-Zustand, Speicherleiste unten für beide.

## Ist-Stand (gemessen 2026-11-08 auf `17a2321`)

| Element | Trip (`trip-new/TripNewEditor.svelte`, 1320 Z.) | Vergleich (`compare-new/CompareNewEditor.svelte`, 766 Z.) |
|---|---|---|
| Navigation Desktop | `:556-557` `PageHeader back` „Trips“ hart kodiert, `onclick: onCancel`, testid `tn-desktop-breadcrumb`, kein Breadcrumb-Text | `:454-460` Breadcrumb „Orts-Vergleiche / Neuer Vergleich“ **unverlinkt**, kein Zurück |
| Navigation Mobil | `:561-568` `PageHeader back` i18n „Trips“, `onCancel`, `tn-mobile-appbar` | `:606-608` `PageHeader back href=/compare` „Vergleiche“, `cm-mobile-head` |
| Abbrechen | kein Knopf; Zurück = `onCancel` (`:522`, setzt `intentionalCancel`, `goto('/trips')`) | `:465` `Btn ghost sm href="/compare"` „Abbrechen“, reiner Link |
| **Autosave beim Verlassen** | `beforeNavigate` `:505-512` **speichert automatisch**, wenn bereit (außer bei `onCancel`) | **kein** `beforeNavigate` |
| Eyebrow Desktop | `:572` `trip.anlegen.titel` „Neue Trip anlegen“ (de `trip.json:231`, falsch), en „Create new trip“ | `:479` `home.planung.neuer_orts_vergleich` „Neuer Orts-Vergleich“ |
| Eyebrow Mobil | Name oder `trip.anlegen.neuer_trip` „Neue Trip“ (`trip.json:230`, falsch) | Name oder „Neuer Vergleich“ (`vergleich.json:105`) |
| h1 | `:573-575` Name oder `trip.anlegen.kein_name` | `:480-481` gleich |
| Fortschritt | `:577-587` `trip-new-progress`, 5 Segmente (`tripNewLogic.ts:101`) | `:483-490` `compare-editor-progress`, 5 Segmente (`anlegeKette('vergleich')`) |
| Weiter erster Schritt | `:733-738` **roher `<button>`** `trip-new-continue-etappen`, Inline-Style accent / `--g-ink-4` + opacity .45 | `:559` `Btn` `compare-editor-continue-orte`, accent / quiet+disabled (ohne opacity) |
| Weiter Folgeschritte | `:939`, `:953` `Btn accent`; Etappen-Tab `:850-910` rohe Buttons ohne testid | `:569` (zusätzlich `style=opacity .45`), `:581`, `:590` `Btn accent` |
| Speichern Desktop | **unten** `:985-998` `EditorStickyFooter context="route" testid="tn-desktop-footer"`, roher `<button>` `trip-new-save-btn` Inline `--g-ink`, „Trip speichern“ | **oben** in der Kopfleiste `:466-473` `Btn` `compare-editor-activate` „Briefing aktivieren“ (primary/quiet, opacity .4) |
| Standardwerte | `:990` `trip-new-standardwerte-btn` (Footer), Hinweis „Alarme einrichten zum Speichern“ `:989` | `:463` `compare-editor-standardwerte` (Kopfleiste), Hinweis `vergleich.neu.alarme_zum_aktivieren` |
| Mobil Fuß | `:1234-1273` `EditorStickyFooter` `tn-mobile-footer`, `tn-mobile-save` „Speichern“ (`aktionen.speichern`), `tn-mobile-route-cta` | `:686-704` `EditorStickyFooter` `cm-mobile-cta`, `cm-mobile-activate` „Briefing aktivieren“ |
| Lock-Engine | eigene `tripNewLogic.ts` (`unlockedTabs`, `doneTabs`) + nur `canFinishMitStandardwerten` | `shared/anlegeLockEngine.ts` voll |

Veraltet im Code: Kommentar `CompareNewEditor.svelte:477` („7 Segmente“, sind 5); `e2e/issue-661-trip-new-mobile.spec.ts:11` (`tn-mobile-save` in App-Leiste).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Kopf/Fuß → gemeinsamer Rahmen; rohe Buttons → `Btn` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Kopfleiste oben → Rahmen, Speichern nach unten |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` (40 Z.) | Props `context`, `testid`, `navClearance`, `children`; schon bei 3 von 4 Flächen im Einsatz |
| `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte` | geteilt, bleibt |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | geteilt; Trip nutzt nur Teil (Konvergenz außerhalb des Scopes) |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | **Vorbild** aus S1: Breadcrumb `<a href=parent.href> / crumb` (`hub-kopf-breadcrumb`), Mobil `BackLink`; **kein `onclick`-Pfad** |
| `frontend/src/lib/components/atoms/PageHeader.svelte`, `atoms/BackLink.svelte` | `back: {href,label,onclick?}`; mit `onclick` wird BackLink zum Button |
| `frontend/src/routes/trips/new/+page.svelte:9`, `routes/compare/new/+page.svelte:17` | reine Hüllen, alle Chrome liegt im Editor |
| i18n `trip.json:230-276`, `vergleich.json:105-124`, `home.json:51`, `listen.json:5/9`, `bausteine.json:22` (de/en) | Labels |
| `frontend/e2e/helpers.ts` `ANLEGE_SEL` ab `:811` | gemeinsame E2E-Selektoren je Art |

## Existing Patterns
- **S1-Muster `shared/hub-kopf/HubKopf.svelte`** bzw. `shared/hub-uebersicht/HubUebersicht.svelte`: ein Markup, `context` nur Datenmarke/Textwahl, Fachliches über Snippets, testids über `testidPrefix`. Neue Dateien nur unter `shared/` (Pendant-Gate `.claude/hooks/pendant_gate.py`, `BEKANNTE_PAARE` darf nur schrumpfen).
- `EditorStickyFooter` unten ist bereits Standard für Trip Desktop/Mobil und Compare Mobil.
- `design_system.md:64` (S1 nachgezogen): Hauptaktion = Ink, Accent = Weiter/Aktiv.
- Paritäts-E2E kind-parametrisiert über `HUB_KINDS`-Schleifen (#2347, S1 `hub-kopf-paritaet-compare-trip.spec.ts`).

## Dependencies
- Upstream: `EditorStickyFooter`, `StandardwerteSpeichernKnopf`, `anlegeLockEngine`, `tripNewLogic`, `Btn`/`MBtn`, `PageHeader`/`BackLink`, ggf. `HubKopf`-Breadcrumb-Teil, i18n-Katalog.
- Downstream: beide Anlege-Routen, `?from=`-Vorlage (beide `+page.server.ts`), E2E-Helfer `ANLEGE_SEL`, Paritäts-Suiten.

## Existing Specs
- `docs/specs/modules/rework_2837_s1_hub_kopf.md` (S2-Ausblick `:24-29`, `:201`; ADR-0110 gilt für S2 `:90`)
- `docs/specs/modules/rework_2837_s1b_status_profil.md`
- `docs/context/rework-2837-hub-kopf-anlege-rahmen.md` (Zielbild-Tabelle `:109-126`, Dateiplan `:140-146`, Slice B ≈6 Dateien / +400 LoC inkl. Tests)
- `feat_1301_f2a_compare_new_trip_pattern.md`, `fix_2277_s2b_mobile_rahmen_angleichung.md`, `feat_2277_s4_anlege_lockengine.md`, `feat_2347_s4_paritaets_e2e.md`
- `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md`

## Tests, die die Divergenz festschreiben (bewusst umdrehen, nicht löschen)
- Unit: `trip_new_mobile_rahmen_angleichung.test.ts` (:89-122 Zurück als Button ohne href, :124-170 Save-Positionen, :219-265 Strukturwächter/aria), `trip_anlegen_sprache.test.ts` (:55 „Neue Trip anlegen“, :57, :157), `standardwerte_knopf_geteilt.test.ts` (:116-141 Compare-Platzierung **in der Kopfzeile**), `compare_anlege_freischaltung.test.ts` (:308 Desktop „Briefing aktivieren“), `compare_new_footer_nav_clearance.test.ts`.
- E2E: `hub-anlegen-ablauf.spec.ts` (`CTA_KETTE` :135-151, AN-8 Abbrechen :463, AN-15 :518-547, AN-14 :651-697), `helpers.ts` `ANLEGE_SEL` (:879-884 route, :915-920 vergleich), `issue-661-trip-new-mobile.spec.ts` (:46-59, :212-222 Zurück ohne Autosave), `standardwerte-und-hilfe.spec.ts` (:185, :203-240), `compare-editor-fidelity-s8d.spec.ts` (:210-246 Desktop-CTA-Fuß).

## Risks & Considerations
1. **Verhaltensunterschied, nicht nur Optik: Autosave beim Verlassen.** Trip speichert bei jeder Navigation außer Zurück/Abbrechen automatisch (`beforeNavigate`), der Vergleich nie. Ein gemeinsamer Rahmen mit „Abbrechen“ muss festlegen, was Abbrechen und Wegnavigieren je Art bedeuten. In der Analyse klären, ob das fachlich (Trip hat Etappen-Aufwand) oder Drift ist; im Zweifel nicht im Rahmen-Ticket angleichen, sondern Abbrechen-Semantik je Art beibehalten und nur Lage/Optik vereinheitlichen.
2. **`HubKopf` kennt kein `onclick`/`onCancel`.** Der Trip-Zurück muss ohne Autosave navigieren → entweder Breadcrumb-Teil mit `onclick` erweitern oder eigenen Rahmen-Kopf bauen (S1-Hub darf nicht brechen).
3. **Abschluss-Beschriftung:** „Trip speichern“/„Speichern“ vs. „Briefing aktivieren“ — fachlich verschieden? (Vergleich aktiviert beim Abschluss; Trip speichert). Analyse muss entscheiden, ob Text gleich wird oder nur Lage/Farbe.
4. **Scope-Deckel 250 LoC**: S1 brauchte `loc_limit_override 450`. Hier ~6 Produktdateien; viele umzudrehende Tests. Ehrlich schätzen, ggf. Override begründen, nicht weiter abspalten (Epic-Abschluss).
5. **Pendant-Gate:** neuer Baustein nur unter `shared/` (z. B. `shared/anlege-rahmen/`).
6. **Rohe Buttons mit Inline-Farben** im Trip (`:733-738`, `:992-996`, Etappen-Tab `:850-910`) → `Btn`-Varianten; Etappen-Tab-Buttons sind Schritt-Inhalt, nur prüfen, nicht zwingend anfassen.
7. **Testids stabil halten**, wo möglich (`trip-new-save-btn`, `tn-desktop-footer`, `compare-editor-activate`), sonst `ANLEGE_SEL` als einzige Stelle umstellen.
8. **Zwei Lock-Engines** (Trip `tripNewLogic`, Vergleich `anlegeLockEngine`): Konvergenz wäre DoD-1-Thema, nicht DoD-2 — ausdrücklich nicht in S2 vermischen.
9. i18n: neue Texte nur über den Katalog, de **und** en (ADR-0104); `keine_hartkodierten_nutzertexte.test.ts` fängt das hart kodierte „Trips“ (`:557`).
10. Nebenbefund: PR **#2846** (S1-Erstversuch `HubStatusBadge`) ist offen, aber durch PR #2854 (`StatusSchild`, live) überholt und nicht in `main`. Schließen ohne Merge (Auto-Modus-Klassifikator hat das Schließen in dieser Sitzung blockiert).

## Analysis

### Type
Feature (Rework, DoD-2 Oberfläche Epic #2345)

### Befunde (Plan-Agent, im Code gegengeprüft auf `938045c5d`)
- **Autosave je Art fachlich begründet, bleibt:** Trip `beforeNavigate` (`TripNewEditor.svelte:504-512`) speichert beim Wegnavigieren, sobald `ready`; Vergleich legt nur per einzigem `POST /api/compare/presets` (`CompareNewEditor.svelte:337`) bei „Briefing aktivieren" an, kein Draft, kein `beforeNavigate`. Autosave im Vergleich würde Karteileichen erzeugen (#1301 F2a). Angleichen wäre ein Verhaltens-Ticket → Whitelist-Eintrag „bewusst verschieden".
- **Abschluss-Text je Art (Whitelist):** Trip „Trip speichern", Vergleich „Briefing aktivieren" (Hinweis `vergleich.neu.alarme_zum_aktivieren` daran gekoppelt). Drift innerhalb Trip: Desktop `trip.anlegen.speichern` (`:995`) vs. Mobil `aktionen.speichern` (`:1242`) → Mobil auf `trip.anlegen.speichern`.
- **HubKopf NICHT erweitern:** zieht SubscriptionHeader/Kebab/Senden mit, kein `onclick`-Pfad; Anlege-Modus dort = Kontext-Verzweigung gegen ADR-0110 Pkt. 1. Nur das Muster übernehmen.
- **Größtes technisches Risiko:** Vergleich hat heute keinen Desktop-Fuß; Hülle ist `TopoBg` (`:452`) mit `overflow-x:auto`-Leiste (`:496`). Sticky-Fuß greift nur ohne eigenen Scroll-Container → früh per Screenshot prüfen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | CREATE | Ein Baustein `context="route"\|"vergleich"`: Kopf (Desktop Breadcrumb `Elternteil-Link / Neuer …`, Mobil `PageHeader back`), Eyebrow, h1, Fortschritt-Slot, Inhalt-Slot, Desktop-Fuß (Abbrechen links, Standardwerte + Hauptaktion rechts) über `EditorStickyFooter`. Props u. a. `onCancel?`, `abschlussLabel`, `canFinish`, testid-Präfix |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Kopf/Fuß in den Rahmen; `beforeNavigate` bleibt im Editor; roher Weiter-Button `:733-738` und Save-Button → `Btn accent` / `Btn primary`; Mobil-Save-Text vereinheitlicht |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Kopfleiste oben (`:454-473`) raus; Abbrechen/Standardwerte/„Briefing aktivieren" in den Rahmen-Fuß unten; Inline-`opacity` an Weiter (`:569/581/590`) entfernen; Kommentar `:477` („7 Segmente") korrigieren |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | MODIFY (klein, nur falls nötig) | ggf. Slot-Aufteilung links/rechts |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json` (+ ggf. `vergleich.json`, `home.json`) | MODIFY | „Neue Trip"→„Neuer Trip"; Eyebrow-Schlüssel je Art `trip.anlegen.neuer_trip` / `vergleich.neu.neuer_vergleich`; tote Schlüssel (`trip.anlegen.titel`, `home.planung.neuer_orts_vergleich`) nur entfernen, wenn grep keine weitere Nutzung zeigt |
| `frontend/e2e/helpers.ts` (`ANLEGE_SEL` ab `:811`) | MODIFY | nur Selektoren, wo Lage wandert; testids bleiben stabil |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` | CREATE | kind-parametrisiert (Muster `hub-kopf-paritaet-compare-trip.spec.ts`): Lage Breadcrumb/Eyebrow/Abbrechen/Hauptaktion/Weiter, 1440/390 px, de/en |
| `shared/anlege-rahmen/__tests__/…` | CREATE | Unit-Test des Rahmens (beide `context`) |
| Umzudrehen (nicht löschen), Unit | MODIFY | `trip_new_mobile_rahmen_angleichung.test.ts`, `trip_new_reiterleiste_besuchs_flags.test.ts`, `standardwerte_knopf_geteilt.test.ts` (`:116-141` Kopfzeile → Fuß), `anlege_reiterleiste_trip_vergleich_paritaet.test.ts`, `compare_new_editor_mobil_orte_schritt.test.ts`, `compare_new_lock_engine_wirkstelle.test.ts`, `compare_anlege_freischaltung.test.ts` (`:308`), `trip_anlegen_sprache.test.ts` (`:55/57/157`), `compare_new_footer_nav_clearance.test.ts` (muss unverändert greifen) |
| Umzudrehen, E2E | MODIFY | `hub-anlegen-ablauf.spec.ts`, `issue-661-trip-new-mobile.spec.ts` (inkl. veralteter Kommentar `:11`), `standardwerte-und-hilfe.spec.ts`, `compare-editor-fidelity-s8d.spec.ts`; per testid-Treffer prüfen: `compare-editor-slice3`, `compare-flow-navigation`, `compare-neu-kanal-anlegen.staging`, `compare-hourly-metric-order`, `langlaeufer-zeitbudget-wirkort`, `issue-932-activity-type-route-tab`, `bug-708-stage-delete-confirm`, `issue-1080-compare-new-url`, `issue-682-compare-editor-mobile` |

### Scope Assessment
- Produktdateien: 5–6 (1 neu)
- Estimated LoC Produkt: ca. +250/−150 (inkl. Löschungen 350–450) → **über Deckel 250; `loc_limit_override 450` begründet wie S1** (ein Baustein ersetzt zwei Rahmen, Epic-Abschluss, keine weitere Abspaltung). Tests zusätzlich.
- Risk Level: **MEDIUM** — zwei zentrale Editoren, viele divergenz-verankernde Tests; Verhalten (Speichern, Autosave, Lock-Engine) wird nicht geändert.

### Technical Approach
Neuer Baustein `shared/anlege-rahmen/AnlegeRahmen.svelte`, ein Markup, `context` wählt nur Texte/Datenmarke (ADR-0110 Pkt. 1 + 7, kein neues ADR). Fachliches über Props/Snippets.

Vorgeschlagene Entscheidungstabelle für die Spec:

| Element | Vorher (Trip / Vergleich) | Nachher (beide) |
|---|---|---|
| Navigation Desktop | nur Zurück „Trips“ (hart kodiert) / Breadcrumb ohne Link | Breadcrumb „Trips / Neuer Trip“ bzw. „Orts-Vergleiche / Neuer Vergleich“, Elternteil Link aus Katalog; beim Trip ruft er `onCancel` (kein Autosave), `href` bleibt |
| Navigation Mobil | Zurück-Knopf / Link `/compare` „Vergleiche“ | `PageHeader back` mit Katalog-Elternteil; Trip `onCancel` |
| Eyebrow | „Neue Trip anlegen“ (falsch) / „Neuer Orts-Vergleich“ | „Neuer Trip“ / „Neuer Vergleich“ (en „New trip“ / „New comparison“), Desktop = Mobil |
| Abbrechen | fehlt / `Btn ghost` oben rechts | `Btn ghost sm` unten links im Fuß, beide; Trip verwirft ohne Autosave, Vergleich → `/compare` |
| Speichern/Aktivieren Desktop | unten, roher Button / oben, `Btn` | **unten rechts im Fuß**, `Btn primary` (Ink), gesperrt solange nicht bereit |
| Standardwerte | Fuß / Kopfleiste | beide im Fuß neben der Hauptaktion |
| Weiter | roher Button + Inline-Opacity / `Btn` + Inline-Opacity | `Btn accent`, gesperrt über globales `disabled` (`app.css:442-446`), Hinweistext daneben |
| Abschluss-Text | „Trip speichern“ (Mobil „Speichern“) / „Briefing aktivieren“ | je Art (Whitelist); Trip Desktop = Mobil „Trip speichern“ |
| Autosave beim Verlassen | ja / nein | unverändert (Whitelist, fachlich) |
| Mobil-Fuß | `EditorStickyFooter` | unverändert (`navClearance` wie heute) |

Whitelist „darf abweichen": Inhalte der Schritte (Etappen- vs. Orte-Tab), Profil-Auswahl (#2792), Abschluss-Text + Alarm-Hinweis, Autosave-Semantik, Lock-Engine (DoD-1).

Testid-Politik: bestehende testids bleiben (z. B. `compare-editor-activate` wandert nach unten, heißt gleich); neuer Wrapper `cm-desktop-footer` analog `tn-desktop-footer`.

### Dependencies
- Upstream: `EditorStickyFooter`, `StandardwerteSpeichernKnopf`, `Btn`/`MBtn`, `PageHeader`/`BackLink`, i18n-Katalog. Nicht anfassen: `tripNewLogic.ts`, `anlegeLockEngine.ts`, `HubKopf.svelte`.
- Downstream: beide Anlege-Routen inkl. `?from=`-Vorlage (nach Umbau einmal prüfen), `ANLEGE_SEL`, Paritäts-Suiten.

### Open Questions
- [x] Autosave angleichen? → Nein, fachlich verschieden, Whitelist (technisch entschieden).
- [x] Abschluss-Text gleich? → Nein, je Art; nur Trip-intern vereinheitlicht.
- [x] HubKopf erweitern? → Nein, eigener Rahmen-Baustein unter `shared/`.
- Keine offene Produktfrage. Mögliches Folge-Thema außerhalb S2: Rückfrage statt Autosave beim Verlassen des Trips.
- Nebenbefund: PR #2846 (überholt durch #2854) ohne Merge schließen.
