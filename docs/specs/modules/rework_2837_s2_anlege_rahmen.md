---
entity_id: rework_2837_s2_anlege_rahmen
type: feature
created: 2026-11-08
updated: 2026-11-08
status: draft
version: "1.0"
workflow: rework-2837-s2-anlege-rahmen
tags: [epic-2345, trip-compare-teilung, anlege-rahmen, shared, paritaet, frontend-only, dod-2]
---

# Scheibe S2: Anlege-Rahmen für Trip und Ortsvergleich als ein Baustein (Issue #2837, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Der Rahmen um die Anlege-Assistenten `/trips/new` und `/compare/new` ist heute zweimal verschieden gebaut. Der Trip hat oben nur einen Zurück-Knopf „Trips“ (fest im Code), einen Eyebrow „Neue Trip anlegen“ (grammatisch falsch), einen schwarzen „Trip speichern“-Knopf unten und einen selbstgebauten orangen „Weiter“-Knopf. Der Ortsvergleich hat oben einen Pfad ohne Link, „Abbrechen“ und „Briefing aktivieren“ in der Kopfleiste, ein Eyebrow „Neuer Orts-Vergleich“ und ein anderes „Weiter“. Das widerspricht der PO-Vorgabe „möglichst viel Code teilen“ (ADR-0097) und ist neben der Reiterleiste Desktop (#2845) die letzte offene Abnahme von Epic #2345 (DoD-2 Oberfläche).

Diese Spec legt **einen** geteilten Baustein `shared/anlege-rahmen/AnlegeRahmen.svelte` mit `context="route"|"vergleich"` an. Er trägt Navigation, Eyebrow, Titel, Fortschrittsanzeige und den Fuß mit Abbrechen, Standardwerten und Hauptaktion. Beide Editoren benutzen ihn. Fachlich Verschiedenes kommt über Props und Snippets herein (geschlossene Whitelist unten). Es ist die zweite und letzte Scheibe von #2837 (S1 Hub-Kopf: PR #2839 und S1b PR #2854, live). Die Vorbedingung #2792 S1c-4b ist gemergt und geschlossen. ADR-0110 `hub-kopf-und-anlege-rahmen-ein-baustein` gilt ausdrücklich auch für S2; es braucht kein zweites ADR.

**Nicht im Scope:** Profil-Auswahl beim Anlegen (#2792), Reiterleiste Desktop (#2845), Inhalte der einzelnen Schritte (Etappen-Tab, Orte-Tab), Angleichung der beiden Lock-Engines (`tripNewLogic.ts` gegen `anlegeLockEngine.ts`, DoD-1-Thema), Verhaltensänderungen am Speichern oder Autosave.

## Entscheidungen zur Freigabe

„Vorher“ ist, was der Nutzer heute sieht, „Nachher“ nach dem Umbau. Wo nur Trip oder nur Ortsvergleich betroffen ist, steht es dabei; sonst gilt es für beide.

| Nr. | Thema | Vorher (Trip / Vergleich) | Nachher (beide) | Warum |
|---|---|---|---|---|
| 1 | **Navigation Computer** | Nur Zurück „Trips“ (fest im Code) / Pfad „Orts-Vergleiche / Neuer Vergleich“ ohne Link | Pfad „Trips / Neuer Trip“ bzw. „Orts-Vergleiche / Neuer Vergleich“, der vordere Teil ist ein Link zur Liste (Text aus dem Katalog), der hintere kein Link. Beim Trip ruft der Link Abbrechen auf (kein Speichern), die Adresse bleibt als `href` erhalten | Gleicher Aufbau wie der Hub-Kopf aus S1 |
| 2 | **Navigation Handy** | Zurück-Knopf „Trips“ / Link „Vergleiche“ auf `/compare` | Zurück-Pfeil mit Elternteil aus dem Katalog; beim Trip löst er Abbrechen aus (kein Speichern), beim Vergleich führt er auf `/compare` | Gleiche Lage, gleiche Beschriftungsquelle |
| 3 | **Eyebrow** | „Neue Trip anlegen“ (falsch), Handy „Neue Trip“ / „Neuer Orts-Vergleich“, Handy „Neuer Vergleich“ | „Neuer Trip“ / „Neuer Vergleich“ (en: „New trip“ / „New comparison“), auf Computer und Handy derselbe Text | Sprachfehler beheben, Computer = Handy |
| 4 | **Abbrechen** | Kein Knopf (nur Zurück) / `Btn ghost` oben rechts | `Btn ghost` klein, **unten links** im Fuß, bei beiden. Trip verwirft ohne Speichern, Vergleich führt auf `/compare` | Eine Stelle für „raus ohne Folgen“ |
| 5 | **Hauptaktion Computer** | Trip: unten, selbstgebauter schwarzer Knopf / Vergleich: oben in der Kopfleiste | **Unten rechts im Fuß**, `Btn primary` (Ink, schwarz), gesperrt (sichtbar abgeblendet), solange der Abschluss nicht möglich ist | Hauptaktion = Ink (design_system.md:64), Speicherleiste unten für beide |
| 6 | **Standardwerte** | Im Fuß / in der Kopfleiste | Bei beiden im Fuß neben der Hauptaktion (geteilter `StandardwerteSpeichernKnopf`) | Eine Stelle |
| 7 | **Weiter** | Trip: selbstgebauter Knopf mit Inline-Farbe und Deckkraft / Vergleich: `Btn` mit zusätzlicher Inline-Deckkraft | `Btn accent` (orange); gesperrt allein über das globale `disabled`-Aussehen (`app.css:442-446`), keine Inline-Deckkraft; Hinweistext daneben bleibt | Orange = Weiter (design_system.md:64) |
| 8 | **Abschluss-Text** | Trip „Trip speichern“ (Handy „Speichern“) / „Briefing aktivieren“ | Je Art verschieden (Whitelist); beim Trip auf Computer **und** Handy „Trip speichern“ | Vergleich aktiviert beim Abschluss, Trip speichert; nur die Trip-interne Abweichung wird behoben |
| 9 | **Autosave beim Verlassen** | Trip speichert beim Wegnavigieren, sobald bereit, außer bei Zurück/Abbrechen / Vergleich nie | **Unverändert** (Whitelist) | Vergleich legt nur beim einzigen „Briefing aktivieren“ an; Autosave würde Karteileichen erzeugen (#1301 F2a). Angleichen wäre ein Verhaltens-Ticket |
| 10 | **Fuß Handy** | `EditorStickyFooter` | Unverändert (gleiche Abstände, `navClearance` wie heute) | Nicht Teil der Abweichung |

## Whitelist: fachlich verschieden, darf abweichen (geschlossene Liste)

1. Inhalte der Schritte (Etappen-Tab beim Trip, Orte-Tab beim Vergleich) und die Profil-Auswahl (#2792).
2. Abschluss-Text („Trip speichern“ gegen „Briefing aktivieren“) samt gekoppeltem Hinweis („Alarme einrichten zum Speichern“ gegen `vergleich.neu.alarme_zum_aktivieren`).
3. Autosave-Semantik beim Verlassen (Trip ja, Vergleich nein) und damit die Bedeutung von Abbrechen (Trip: verwerfen statt Autosave; Vergleich: Seite verlassen, es existiert kein Entwurf).
4. Die zwei Lock-Engines (Konvergenz ist DoD-1).
5. Datenmarke `data-kind`, Testid-Präfix und die Texte des Katalogs je `context`.

Alles andere ist ein Markup. Titel (h1: Name oder „Kein Name“) und Fortschrittsanzeige (5 Segmente) sind schon heute gleich und bleiben im Rahmen.

## Source

- **Neu (Pfade relativ zu `frontend/src/lib/components/`):** `shared/anlege-rahmen/AnlegeRahmen.svelte`; Unit-Test unter `shared/anlege-rahmen/__tests__/`. **Neue Dateien ausschließlich unter `shared/`** (Pendant-Gate `.claude/hooks/pendant_gate.py`, `BEKANNTE_PAARE` darf nur schrumpfen).
- **Geändert:**
  - `trip-new/TripNewEditor.svelte` (Kopf `:556-587` und Fuß `:985-998` in den Rahmen; `beforeNavigate` `:504-512` und `onCancel` `:522` bleiben im Editor; roher Weiter-Button `:733-738` und roher Speichern-Button `:992-996` werden `Btn`; Mobil-Speichern `:1242` von `aktionen.speichern` auf `trip.anlegen.speichern`).
  - `compare-new/CompareNewEditor.svelte` (Kopfleiste `:454-473` raus; Abbrechen, Standardwerte und „Briefing aktivieren“ in den Rahmen-Fuß; Inline-Deckkraft an Weiter `:569/581/590` entfernen; Kommentar `:477` „7 Segmente“ auf 5 korrigieren).
  - `shared/EditorStickyFooter.svelte` (40 Zeilen; nur falls nötig: links/rechts-Aufteilung).
  - i18n `lib/i18n/messages/{de,en}/trip.json` und `vergleich.json` (Eyebrow-Texte je Art, „Neue Trip“ wird „Neuer Trip“, Elternteil-Texte; tote Schlüssel `trip.anlegen.titel`, `home.planung.neuer_orts_vergleich` nur entfernen, wenn grep keine weitere Nutzung zeigt).
  - Doku: `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` (kurzer Nachtrag „S2 umgesetzt“), `docs/reference/design_system.md` (Anlege-Rahmen-Zeile, falls dort geführt).
- **Nicht anfassen:** `shared/hub-kopf/HubKopf.svelte` (zieht SubscriptionHeader, Kebab und Senden mit und hat keinen `onclick`-Pfad; eine Anlege-Variante dort wäre eine Kontext-Verzweigung gegen ADR-0110 Pkt. 1; nur das Muster wird übernommen), `tripNewLogic.ts`, `shared/anlegeLockEngine.ts`.
- **Unverändert wiederverwendet:** `atoms/PageHeader`, `atoms/BackLink` (`back: {href,label,onclick?}`), `ui/btn/Btn.svelte`, `shared/StandardwerteSpeichernKnopf.svelte`.

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein neuer Endpunkt.
> **Trip/Ortsvergleich-Teilung:** Kern dieser Spec. Baustein unter `shared/anlege-rahmen/`, Parameter `context="route"|"vergleich"` (Vorbild `shared/hub-kopf/HubKopf.svelte`). Es entsteht keine Komponente mit Pendant unter `trip-new/` oder `compare-new/`; die Pendant-Sperre löst nicht aus.
> **Mandantentrennung:** reine Oberfläche, kein neuer datenbewegender Endpunkt. Speichern (`POST /api/compare/presets`, Trip-Speichern) und Autosave laufen unverändert über den Editor mit der echten `user_id` aus dem Auth-Kontext. Der Rahmen ruft keine API selbst; ein Zwei-Nutzer-Test des Rahmens entfällt, die bestehenden Anlege-E2E laufen unverändert.
> **Kanäle:** nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/EditorStickyFooter.svelte` | component | Fuß unten (Desktop und Handy), Props `context`, `testid`, `navClearance` |
| `shared/StandardwerteSpeichernKnopf.svelte` | component | „Mit Standardwerten speichern“, bleibt geteilt |
| `shared/anlegeLockEngine.ts`, `trip-new/tripNewLogic.ts` | module | Freischaltung der Schritte; werden nicht verändert |
| `atoms/PageHeader.svelte`, `atoms/BackLink.svelte` | component | Navigation Handy |
| `ui/btn/Btn.svelte` | component | Abbrechen (`ghost`), Hauptaktion (`primary`), Weiter (`accent`) |
| `lib/i18n` Katalog (`trip.json`, `vergleich.json`, `listen.json`) | module | Texte de und en (ADR-0104) |
| `frontend/e2e/helpers.ts` (`ANLEGE_SEL`) | test helper | gemeinsame Selektoren je Art |
| `routes/trips/new/+page.server.ts`, `routes/compare/new/+page.server.ts` | route | `?from=`-Vorlage |

## Scope (Estimated Scope)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | CREATE | Ein Baustein mit `context`, Kopf, Eyebrow, Titel, Fortschritt-Slot, Inhalt-Slot, Desktop-Fuß |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Kopf und Fuß in den Rahmen, rohe Buttons zu `Btn`, Mobil-Speichertext |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Kopfleiste raus, Fuß unten, Inline-Deckkraft raus |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | MODIFY (nur falls nötig) | links/rechts-Slots |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json`, `vergleich.json` | MODIFY | Eyebrow- und Elternteil-Texte |
| `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` | MODIFY | Nachtrag S2 |
| `frontend/e2e/helpers.ts` | MODIFY | `ANLEGE_SEL` nur dort, wo Lage wandert |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` | CREATE | kind-parametrisiertes Paritäts-E2E |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` | CREATE | Unit-Test beider `context` |
| umzudrehende Unit-/E2E-Tests | MODIFY | siehe Test Plan |

### Estimated Changes

- **Produktdateien:** 5 bis 6 (1 neu: AnlegeRahmen; 2 Editoren; i18n de/en als je eine Datei zählend; `EditorStickyFooter` nur bei Bedarf), dazu ca. 15 Test-/E2E-Dateien und 2 Doku-Dateien.
- **LoC Produktcode (ohne Tests, Docs, i18n), ehrlich geschätzt:** AnlegeRahmen ca. +150; TripNewEditor ca. +40/-80 (Kopf, Fuß, rohe Buttons); CompareNewEditor ca. +40/-70 (Kopfleiste, Inline-Deckkraft); EditorStickyFooter ca. +10/-0. Brutto ca. +250/-150, geänderte Zeilen insgesamt ca. 400, netto ca. +100.
- **`loc_limit_override 450`** (wie S1): Ein Baustein ersetzt zwei gewachsene Rahmen, der Umbau besteht überwiegend aus Verschieben vorhandener Zeilen; ein weiteres Abspalten ließe den Rahmen halbiert zurück, die Parität käme erst später, und S2 ist der Abschluss des Epics. Tests liegen zusätzlich außerhalb der Zählung.
- **Effort:** medium-high. **Risiko:** MEDIUM (zwei zentrale Editoren, viele Tests verankern die Divergenz; Speichern, Autosave und Lock-Engine bleiben unverändert).

## Implementation Details

Reihenfolge, damit jeder Zwischenstand grün bleibt:

1. **Früher Machbarkeitsnachweis (größtes technisches Risiko):** Der Vergleich hat heute keinen Desktop-Fuß; seine Hülle ist `TopoBg` (`CompareNewEditor.svelte:452`) mit `overflow-x:auto`-Leiste (`:496`). Ein klebender Fuß greift nur ohne eigenen Scroll-Container. Vor dem Umbau mit Screenshot bei 1440 px prüfen, dass der Fuß am unteren Fensterrand sichtbar bleibt; falls nötig, Hülle bzw. `overflow` so anpassen, dass nur der Fortschritt-/Leistenstreifen scrollt.
2. **`AnlegeRahmen`** anlegen: Props `context`, `onCancel?` (Trip), `cancelHref` (Vergleich und `href`-Rückfall), `abschlussLabel`, `canFinish`, `onFinish`, `hinweis` (Snippet, Alarm-Hinweis), `standardwerte` (Snippet, bindet den geteilten Knopf ein), `testidPrefix`, `navClearance`; Snippets `fortschritt`, `children`. Kein `context`-Zweig im Aufbau; `context` wählt nur Textschlüssel, Elternteil-Link, `data-kind` und Testid-Präfix. Desktop: Breadcrumb (Elternteil als Link, bei Trip mit `onclick={onCancel}` und `href`), Eyebrow, h1, Fortschritt, Inhalt, Fuß über `EditorStickyFooter` (Abbrechen links; Standardwerte, Hinweis und Hauptaktion rechts). Handy: `PageHeader back`, Fuß bleibt der bestehende Mobil-Fuß der Editoren.
3. **Trip-Editor** umstellen: `beforeNavigate` und `intentionalCancel` bleiben im Editor und wirken unverändert; roher Weiter-Button zu `Btn accent` (Gesperrt-Zustand nur über `disabled`), roher Speichern-Button zu `Btn primary` in den Rahmen-Fuß; Mobil-Text `trip.anlegen.speichern`.
4. **Vergleich-Editor** umstellen: Kopfleiste raus; Abbrechen, Standardwerte und „Briefing aktivieren“ (`compare-editor-activate`, `Btn primary`) in den Rahmen-Fuß; Inline-`opacity` an Weiter entfernen; Kommentar `:477` berichtigen.
5. **i18n** de und en; Katalogtests (`keine_hartkodierten_nutzertexte.test.ts`) grün. Das hart kodierte „Trips“ (`TripNewEditor.svelte:557`) entfällt.
6. **Tests umdrehen** (siehe Test Plan), **ADR-Nachtrag und Doku**.

**i18n-Regeln (ADR-0104):** neue und verschobene Texte nur über den Katalog, de **und** en. Protokoll-Token werden nie übersetzt.

## Expected Behavior

- **Input:** `context`, Namen und Zustand des Editors (Name, bereit zum Abschluss, Standardwerte erlaubt), Callbacks `onCancel`, `onFinish`.
- **Output:** gleicher Rahmen für beide Arten; sichtbarer Unterschied nur in der Whitelist.
- **Side effects:** keine im Rahmen. Speichern, Autosave und Anlegen bleiben im jeweiligen Editor und ändern sich nicht.

## Test Plan

Test-Politik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis (Ausnahme `# doc-compliance-test`). Frontend-Unit-Tests laufen über `node --test`, **nicht** Vitest. Jede Zusicherung wird dort geprüft, wo sie wirkt: Lage, Farbe und Gesperrt-Zustand im E2E aus Nutzersicht, Aufbau und Textwahl je `context` im Unit-Test des Rahmens.

### Divergenz-verankernde Tests: umdrehen, nicht löschen

| Test | Heute erzwungen | Neue Zusicherung |
|---|---|---|
| Unit `trip_new_mobile_rahmen_angleichung.test.ts` (:89-122, :124-170, :219-265) | Zurück als Button ohne `href`; Save-Positionen; Strukturwächter und Aria | Zurück mit Katalog-Elternteil (Trip: `onCancel`, `href` bleibt); Save-Positionen im Rahmen-Fuß; Aria-Wächter folgt dem Rahmen |
| Unit `trip_anlegen_sprache.test.ts` (:55, :57, :157) | „Neue Trip anlegen“ | „Neuer Trip“ / „New trip“ |
| Unit `standardwerte_knopf_geteilt.test.ts` (:116-141) | Compare-Platzierung in der Kopfzeile | Platzierung im Fuß neben der Hauptaktion, bei beiden Arten |
| Unit `compare_anlege_freischaltung.test.ts` (:308) | Desktop „Briefing aktivieren“ in der Kopfleiste | Desktop „Briefing aktivieren“ im Fuß, gleiche Freischaltung |
| Unit `compare_new_footer_nav_clearance.test.ts` | Abstand des Mobil-Fußes | **muss unverändert greifen** |
| Unit `trip_new_reiterleiste_besuchs_flags.test.ts`, `anlege_reiterleiste_trip_vergleich_paritaet.test.ts`, `compare_new_editor_mobil_orte_schritt.test.ts`, `compare_new_lock_engine_wirkstelle.test.ts` | Pfade und Selektoren der alten Rahmen | Pfade folgen dem Rahmen; Zusicherungen zur Lock-Engine bleiben wörtlich |
| E2E `hub-anlegen-ablauf.spec.ts` (`CTA_KETTE` :135-151, AN-8 :463, AN-15 :518-547, AN-14 :651-697) | Abbrechen und CTA-Kette je Art in alter Lage | Abbrechen unten links, Hauptaktion unten rechts, Weiter als `Btn accent`; Zeilen bleiben, Lage dreht |
| E2E `helpers.ts` `ANLEGE_SEL` (:879-884 route, :915-920 vergleich) | je Art eigene Lage | einzige Stelle, an der Selektoren umgestellt werden; testids bleiben |
| E2E `issue-661-trip-new-mobile.spec.ts` (:46-59, :212-222; veralteter Kommentar :11) | Zurück ohne Autosave; `tn-mobile-save` in App-Leiste | Zurück ohne Autosave bleibt wörtlich; Kommentar berichtigt |
| E2E `standardwerte-und-hilfe.spec.ts` (:185, :203-240) | Standardwerte in der Kopfzeile des Vergleichs | im Fuß |
| E2E `compare-editor-fidelity-s8d.spec.ts` (:210-246) | Desktop-CTA-Fuß | neuer Fuß |

Per testid-Treffer zusätzlich zu prüfen (Umhängung im Commit benannt, nichts gelockert): `compare-editor-slice3`, `compare-flow-navigation`, `compare-neu-kanal-anlegen.staging`, `compare-hourly-metric-order`, `langlaeufer-zeitbudget-wirkort`, `issue-932-activity-type-route-tab`, `bug-708-stage-delete-confirm`, `issue-1080-compare-new-url`, `issue-682-compare-editor-mobile`.

### Neu (TDD RED, aus Nutzersicht)

- [ ] Unit `shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` (beide `context`): ein Markup, Elternteil-Text und Eyebrow aus dem Katalog je `context`, `data-kind` gesetzt, Abbrechen links und Hauptaktion rechts im Fuß, Hauptaktion gesperrt ohne `canFinish`, kein `context`-Zweig im Aufbau.
- [ ] E2E `frontend/e2e/anlege-rahmen-paritaet.spec.ts`: Schleife über beide Arten, bei 1440 und 390 px, de und en: Lage Breadcrumb, Eyebrow, Abbrechen, Hauptaktion, Weiter; Hauptaktion schwarz, Weiter orange; Gesperrt-Zustand; Trip-Abbrechen ohne Autosave; Vergleich ohne Draft; Sticky-Fuß sichtbar. Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`: Datei trägt die Art-Schleife.
- [ ] Mutationen (Pflicht, per String-Ersetzung mit externer Sicherung): Hauptaktion im Trip wieder auf `accent` ⇒ rot; Abbrechen wieder oben ⇒ rot; Inline-Deckkraft am Weiter wieder gesetzt ⇒ rot; Eyebrow „Neue Trip“ ⇒ rot; Trip-Zurück ruft Autosave auf ⇒ rot; Fuß im Vergleich wieder entfernt ⇒ rot. Eine Verfälschung, die kein Test fängt, ist ein Finding.

## Acceptance Criteria

- **AC-1:** Given der Nutzer öffnet `/trips/new` und `/compare/new` auf dem Computer (1440 px) / When die Seite geladen ist / Then zeigt der Pfad oben „Trips / Neuer Trip“ bzw. „Orts-Vergleiche / Neuer Vergleich“, der vordere Teil ist ein Link zur Liste, der hintere kein Link, und beim Vergleich steht kein separater „Abbrechen“-Knopf mehr in der Kopfleiste.
  - Test: E2E-Schleife über beide Arten bei 1440 px: Text und Link-Eigenschaft der Krümel, Position oben links; kein Abbrechen-Knopf im Kopfbereich.
- **AC-2:** Given der Nutzer ist im Trip-Assistenten mit einer Eingabe auf dem Computer / When er den vorderen Teil des Pfades („Trips“) anklickt / Then verlässt er den Assistenten ohne Speichern und landet auf `/trips`, und es entsteht kein neuer Trip.
  - Test: E2E: Name eingeben, Pfad-Link klicken, `/trips` erreicht, kein neuer Trip in der Liste (kein Autosave-Request); Quelle des Texts ist der Katalog (kein hart kodiertes „Trips“).
- **AC-3:** Given der Nutzer öffnet beide Assistenten auf dem Handy (390 px) / When er den Kopf betrachtet / Then steht links ein Zurück-Pfeil mit dem Elternteil-Namen aus dem Katalog („Trips“ bzw. „Orts-Vergleiche“), und ein Tippen führt beim Trip ohne Speichern auf `/trips`, beim Vergleich auf `/compare`.
  - Test: E2E-Schleife bei 390 px: Lage und Beschriftung des Zurück-Elements; Klick führt auf die jeweilige Liste; Trip: kein Speichern-Request.
- **AC-4:** Given beide Assistenten in Deutsch und in Englisch auf Computer und Handy / When der Nutzer das Eyebrow-Label über dem Titel liest / Then steht dort „Neuer Trip“ / „Neuer Vergleich“ (en: „New trip“ / „New comparison“), auf dem Computer und auf dem Handy derselbe Text, und niemals „Neue Trip“.
  - Test: E2E-Schleife (Art x Breite x Sprache): Eyebrow-Text gleich für Computer und Handy; Unit `trip_anlegen_sprache` umgedreht.
- **AC-5:** Given beide Assistenten auf dem Computer / When der Nutzer den unteren Fuß betrachtet / Then steht „Abbrechen“ (`Btn ghost`) bei beiden unten links, und es gibt in der Kopfleiste keinen Abbrechen-Knopf.
  - Test: E2E-Schleife bei 1440 px: Position von Abbrechen links im Fuß (gleiche Zeile wie die Hauptaktion, links von ihr); Kopfbereich ohne Abbrechen.
- **AC-6:** Given der Nutzer hat im Trip-Assistenten Eingaben gemacht / When er „Abbrechen“ oder Zurück wählt / Then wird nichts gespeichert und er landet auf `/trips`; wählt er dagegen eine andere Navigation (z. B. Menü) und der Trip ist bereit, bleibt das Autosave-Verhalten wie heute unverändert.
  - Test: E2E: Abbrechen und Zurück erzeugen keinen Trip; Wegnavigieren über das Menü bei bereitem Trip speichert wie bisher (bestehender Test `issue-661-trip-new-mobile` Zurück ohne Autosave bleibt wörtlich grün).
- **AC-7:** Given der Nutzer ist im Vergleichs-Assistenten mit Eingaben / When er „Abbrechen“ wählt oder die Seite verlässt / Then landet er bei Abbrechen auf `/compare`, es wird kein Vergleich und kein Entwurf angelegt, und angelegt wird nur beim Klick auf „Briefing aktivieren“.
  - Test: E2E: nach Abbrechen und nach Wegnavigieren kein neuer Vergleich in der Liste (kein `POST /api/compare/presets`); nur „Briefing aktivieren“ löst den Request aus.
- **AC-8:** Given beide Assistenten auf dem Computer im letzten Schritt / When der Nutzer den Fuß betrachtet / Then steht die Hauptaktion unten rechts, schwarz (Ink) mit weißer Schrift, beim Trip „Trip speichern“ und beim Vergleich „Briefing aktivieren“, und beim Vergleich sitzt „Briefing aktivieren“ nicht mehr oben in der Kopfleiste.
  - Test: E2E-Schleife bei 1440 px: Position unten rechts im Fuß, berechnete Hintergrundfarbe `--g-ink`; `compare-editor-activate` liegt im neuen Fuß `cm-desktop-footer`.
- **AC-9:** Given ein Assistent, bei dem der Abschluss noch nicht möglich ist / When der Nutzer die Hauptaktion betrachtet / Then ist sie sichtbar abgeblendet und nicht anklickbar, und sie wird anklickbar, sobald der Abschluss möglich ist.
  - Test: E2E-Schleife: `disabled` und reduzierte Deckkraft im Ausgangszustand, nach Erfüllen der Bedingungen aktiv; Klick im gesperrten Zustand löst keinen Request aus.
- **AC-10:** Given beide Assistenten auf dem Computer / When der Nutzer den Fuß betrachtet / Then steht „Mit Standardwerten speichern“ bei beiden im Fuß neben der Hauptaktion (nicht in der Kopfzeile), zusammen mit dem Hinweistext zum Abschluss.
  - Test: E2E-Schleife bei 1440 px: Standardwerte-Knopf im Fuß; Kopfbereich ohne Standardwerte-Knopf; Unit `standardwerte_knopf_geteilt` umgedreht.
- **AC-11:** Given beide Assistenten in einem Zwischenschritt / When der Nutzer „Weiter“ betrachtet / Then ist „Weiter“ bei beiden ein orangefarbener Knopf (`Btn accent`), der im gesperrten Zustand allein durch das gemeinsame Abgeblendet-Aussehen erkennbar ist (keine zusätzliche Inline-Deckkraft), mit Hinweistext daneben.
  - Test: E2E-Schleife (Computer und Handy): Hintergrund `--g-accent`; gesperrt gemessen über `disabled`; Unit: Quelltext des Weiter-Knopfs ohne Inline-`opacity` oder Inline-Farbe (als Strukturwächter, nicht als alleiniger Verhaltensnachweis).
- **AC-12:** Given der Trip-Assistent auf Computer und Handy / When der Nutzer den Abschluss betrachtet / Then heißt die Hauptaktion auf beiden „Trip speichern“ (nicht mehr „Speichern“ auf dem Handy), und im Vergleich bleibt „Briefing aktivieren“ auf beiden.
  - Test: E2E bei 1440 und 390 px: Beschriftung der Hauptaktion; Unit: Mobil-Text kommt aus `trip.anlegen.speichern`.
- **AC-13:** Given beide Assistenten auf dem Handy (390 px) / When der Nutzer die Fußleiste betrachtet / Then sitzt sie unverändert über der Navigation mit demselben Abstand wie heute (`navClearance`), und nichts ist verdeckt.
  - Test: Unit `compare_new_footer_nav_clearance.test.ts` unverändert grün; E2E bei 390 px: Fuß vollständig sichtbar, nicht von der unteren Navigation überdeckt.
- **AC-14:** Given der Rahmen im Quelltext / When beide Editoren gerendert werden / Then entsteht der Aufbau aus **einem** Markup (`AnlegeRahmen`), `context` wählt nur Textschlüssel, Elternteil-Link, Datenmarke und Testid-Präfix, und es gibt keine Komponente mit Pendant in `trip-new/` oder `compare-new/`.
  - Test: Unit-Test `anlege_rahmen.test.ts` rendert beide `context` und vergleicht den Aufbau (gleiche Struktur, nur Texte und `data-kind` verschieden); Pendant-Gate `.claude/hooks/pendant_gate.py` löst nicht aus.
- **AC-15:** Given neue und verschobene Nutzertexte (Elternteil, Eyebrow, Abbrechen, Abschluss-Texte) / When die Oberfläche auf Deutsch und Englisch gerendert wird / Then erscheinen alle Texte über den Katalog in beiden Sprachen, und es bleibt kein hart kodierter Nutzertext.
  - Test: E2E in de und en; `keine_hartkodierten_nutzertexte.test.ts` grün (das hart kodierte „Trips“ ist entfernt).
- **AC-16:** Given bestehende Tests und Automatisierungen / When der Umbau fertig ist / Then bestehen die Selektoren `trip-new-save-btn`, `tn-desktop-footer`, `compare-editor-activate`, `compare-editor-standardwerte`, `trip-new-continue-etappen`, `compare-editor-continue-orte` weiter, und neu ist nur der Fuß-Wrapper `cm-desktop-footer` analog `tn-desktop-footer`.
  - Test: E2E sucht alle genannten testids und findet je genau eines; `ANLEGE_SEL` ist die einzige umgestellte Stelle.
- **AC-17:** Given der Nutzer startet einen Assistenten mit einer Vorlage (`?from=`) / When er `/trips/new?from=…` bzw. `/compare/new?from=…` öffnet / Then sind die Felder wie vor dem Umbau vorbelegt, und der Rahmen sieht aus wie ohne Vorlage.
  - Test: E2E für beide Arten: Vorlage laden, vorbelegte Werte vorhanden, Rahmen-Elemente (Breadcrumb, Fuß) vorhanden.
- **AC-18:** Given der Vergleichs-Assistent (Hülle mit `TopoBg` und waagerecht scrollender Leiste) auf dem Computer / When der Nutzer bei langem Inhalt scrollt oder das Fenster klein ist / Then bleibt der Fuß mit Abbrechen und Hauptaktion am unteren Fensterrand sichtbar und erreichbar.
  - Test: E2E bei 1440 px mit langem Inhalt und bei niedrigem Fenster (z. B. 1440x700): Fuß vollständig im Viewport, Hauptaktion anklickbar; Screenshot als Beleg.
- **AC-19:** Given die Umsetzung / When die Testsuite läuft / Then sind alle divergenz-verankernden Tests aus dem Test Plan umgedreht und nicht gelöscht, die neuen Tests (Unit-Test des Rahmens, E2E `anlege-rahmen-paritaet.spec.ts`) sind grün, und die Pflicht-Mutationen werden von mindestens einem Test gefangen.
  - Test: `node --test` auf den benannten Unit-Dateien und Playwright auf den benannten E2E-Dateien; Adversary-Verdict VERIFIED mit Mutationsprotokoll.
- **AC-20:** Given die Doku / When sie nach der Lieferung geprüft wird / Then enthält ADR-0110 den Nachtrag „S2 umgesetzt“ (kein neues ADR), und die Whitelist dieser Spec ist die einzige Liste erlaubter Abweichungen.
  - Test: `tests/test_adr_index_drift.py` grün; Doku-Prüfung in /60 (`# doc-compliance-test` für den Nachtrag).
- **AC-21:** Given (Abschluss) S2 ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Anlege-Rahmen Computer 1440 px und Handy 390 px (Trip gegen Vergleich) vergleicht / Then findet er keinen Unterschied außer der Whitelist (Schritt-Inhalte, Abschluss-Text mit Hinweis, Profil-Auswahl), und das Paar liegt als Kommentar im Epic #2345.
  - Test: `fresh-eyes-inspector` ohne Bug-Kontext auf vier Screenshots (2 Breiten x 2 Arten); Ergebnis und Bilder als Kommentar im Epic #2345 abgelegt. Danach bleibt im Epic nur #2845 offen; Issue #2837 wird nach grünem Selftest geschlossen.

## Definition of Done

- AC-1 bis AC-21 sind erfüllt, jedes AC hat einen grünen Test aus dem Test Plan; keine Zusicherung wurde gelockert, keine divergenz-verankernde Datei gelöscht.
- Pflicht-Mutationen werden gefangen (Adversary-Verdict VERIFIED).
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.
- Fresh-Eyes-Screenshot-Paar (1440/390, Trip gegen Vergleich) liegt als Kommentar im Epic #2345.
- Issue #2837 wird erst nach Selftest-Exit 0 geschlossen.

## Known Limitations

- Autosave beim Verlassen bleibt je Art verschieden (Whitelist). Mögliches Folge-Thema außerhalb von S2: Rückfrage statt Autosave beim Verlassen des Trips.
- Die zwei Lock-Engines bleiben getrennt (DoD-1).
- Profil-Auswahl (#2792) und Reiterleiste Desktop (#2845) sind nicht Teil dieser Scheibe.
- Etappen-Tab-Buttons (`TripNewEditor.svelte:850-910`, rohe Buttons ohne testid) sind Schritt-Inhalt; sie werden geprüft, aber nur angefasst, wenn der Umbau es erzwingt.
- Handy-Eyebrow (AC-4): Sobald ein Name eingegeben ist, zeigt das Handy über dem Reiter-Titel den Namen statt „Neuer Trip“/„Neuer Vergleich“ (Bestandsverhalten, bei beiden Arten gleich). Auf dem Handy ist das die einzige Stelle, an der der Name beim Anlegen sichtbar ist; AC-4 gilt für den Zustand ohne Namen (geprüft in E2E AR-4). Festgestellt in /60-validate.
- Nebenbefund: PR #2846 (S1-Erstversuch `HubStatusBadge`, durch #2854 überholt) ist ohne Merge zu schließen; nicht Teil dieser Lieferung.

## Risiken

1. **Sticky-Fuß im Vergleich** (`TopoBg`, `overflow-x:auto`): größtes technisches Risiko, deshalb früher Machbarkeitsnachweis (Implementation Details Schritt 1) und AC-18.
2. **Verhaltensunterschied Autosave:** Der Rahmen darf Abbrechen nicht vereinheitlichen; AC-6 und AC-7 sichern beide Semantiken ab. Der Trip-Pfad-Link muss `onCancel` vor der Navigation aufrufen, sonst greift `beforeNavigate` mit Autosave.
3. **Viele Tests verankern die Divergenz** (Test Plan); vergessene Treffer zeigen sich als roter `frontend-test`/`e2e`-Check. Alle per testid-Suche vorab zuordnen.
4. **Kontrast:** Hauptaktion Ink auf Papier ca. 15:1, Weiß auf Accent nur 4,34:1 (siehe S1); deshalb bleibt Accent bei „Weiter“ mit großem Knopf-Text und bei Aktiv-Zuständen, die Hauptaktion ist Ink (design_system.md:64).
5. **Scope:** über 250 Zeilen, daher `loc_limit_override 450`; kein weiteres Abspalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0110 `hub-kopf-und-anlege-rahmen-ein-baustein` gilt auch für S2; kein neues ADR, nur Nachtrag „S2 umgesetzt“.
- **Rationale:** Der Rahmen bleibt ein Baustein mit `context` (Pkt. 1 und 7 des ADR). `HubKopf` wird bewusst nicht erweitert, damit der Hub-Kopf nicht um Anlege-Verzweigungen wächst. Autosave-Semantik und Abschluss-Text bleiben fachlich verschieden und stehen in der Whitelist; wer das ändern will, braucht ein eigenes Verhaltens-Ticket.

## Changelog

- 2026-11-08: Initial spec created (Issue #2837, Epic #2345, Scheibe S2 Anlege-Rahmen)
