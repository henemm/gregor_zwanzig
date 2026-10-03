# Context: feat-2284-hub-kopf-paritaet

Issue #2284 · Epic #2345, Etappe P2 (nach #2277, vor #2287/#2288). Nachgemessen am 2026-10-02 auf `772cf8e0`.
FE steht für `frontend/src/lib/components`.

## Request Summary
Der Kopf des Trip-Hubs und des Vergleich-Hubs sowie der Reiter-Rahmen sollen gleich gebaut sein: ein Kopf-Baustein mit `kind` (Name, Region und Profil inline, Speicher-Chip an einer Stelle), keine Trip-Hüllen um die geteilten Reiter, explizites `context=` an jedem Mount und ein gemeinsamer `VTLaufzeit`-Baustein.

## Ist-Stand je Befund (Issue vom 09.09. → heute)

| # | Befund | Stand heute | Beleg |
|---|---|---|---|
| 1 | Trip: nur Name inline; Region nicht editierbar; Aktivität im Etappen-Reiter. Vergleich: Name, Region und Profil inline | **trifft zu** | `trip-detail/TripHeader.svelte:35-54,127-163` (Name), `:61,119-121` (Region nur in der Eyebrow-Zeile); `trip-detail/TripTabs.svelte:183-189,200-219` (Aktivität-Select, PUT `{activity}`); `routes/compare/[id]/+page.svelte:337-387` (Desktop), `:420-482` (Mobil), `:170-225` (Speichern je Feld) |
| 2 | SaveIndicator an verschiedenen Orten, `createSaveStatus` beim Vergleich ohne ID | **teilweise erledigt** (#2276): beide fixes Overlay, beide mit ID, gleicher `beforeNavigate`-Wächter. Offen ist nur der Montageort: Trip in TripHeader, Vergleich in CompareTabs | `TripHeader.svelte:194-196`; `compare/CompareTabs.svelte:728-732`; `ui/SaveIndicator.svelte:62`; `routes/trips/[id]/+page.svelte:43`; `routes/compare/[id]/+page.svelte:70` |
| 3 | Trip-Hüllen `AlarmeScheduleTab`/`BriefingScheduleTab`; zweiter Speichern-Knopf | **trifft zu** | `trip-detail/AlarmeScheduleTab.svelte` (70 Z.): berechnet nur Startwerte, `AlarmeTab context="route"` `:60`. `trip-detail/BriefingScheduleTab.svelte` (156 Z.): eigener `$effect`-Autosave + `weatherSaveGate` `:83-100`, Capture-Hooks `:123-128`, `VersandTab` `:130`, Knopf „Briefing-Zeitplan speichern" nur ohne `saveController` `:139-154` (Altlast). Der Vergleich mountet direkt: `CompareTabs.svelte:1054,1077` |
| 4 | `context=` fehlt an Mounts | **trifft zu**, kein Fehlverhalten, weil der Standardwert `'route'` ist | ohne `context`: `TripTabs.svelte:223` (`WeatherMetricsTab`), `:228` (`CorridorEditor`), `trip-new/TripNewEditor.svelte:900,1175` (`WeatherMetricsTab`). Alle übrigen Mounts tragen `context` (Liste in der Analyse) |
| 5 | metricsCatalog: Trip lädt serverseitig, Vergleich clientseitig | **trifft zu** | `routes/trips/[id]/+page.server.ts:17-22,36`; `shared/corridor-editor/compareMetricCatalogLoader.ts`, `CompareTabs.svelte:73,346,423-427` |
| 6 | `VTLaufzeitRoute` (73) und `VTLaufzeitVergleich` (141) | **trifft zu** | Route: nur lesend, Ende aus Etappen, „Etappen öffnen →". Vergleich: „Bis auf Weiteres"/„Bis Datum" editierbar. Gemountet in `shared/versand-tab/VersandTab.svelte:19-20,400,434` |

## Datenmodell
- **Trip.region** existiert in allen drei Schichten: Go `internal/model/trip.go:129` (`omitempty`), Python `src/app/trip.py:206` (roundtrip-erhalten, #805), Schreibweg `src/app/loader.py:1711-1712`, TS `frontend/src/lib/types.ts:346`. Gelesen wird es in TripHeader (Eyebrow), in der Trip-Liste `routes/trips/+page.svelte:417-418` und vermutlich im Home-Hero `routes/+page.svelte:202-207`. Geschrieben wird es heute nur beim Anlegen (`trip-new/tripNewLogic.ts:212-213`). Kein Python-Renderer liest es.
- **Vergleich-Region** liegt in `display_config.region` (`types.ts:661`), nicht top-level.
- **Profil ist NICHT dasselbe Feld:** Trip `activity: ActivityType` (trekking/skitour/hochtour/klettersteig/mtb/fahrrad_15/20/25, `types.ts:345`) und Vergleich `profil` (wintersport/wandern/allgemein/summer_trekking, `types.ts:127`, `ACTIVITY_PROFILE_OPTIONS` `:129`). Ein gemeinsamer Kopf braucht deshalb je `kind` eigene Optionen. Für die Analyse offen: Darf die Aktivität aus dem Etappen-Reiter in den Kopf wandern? Die Aktivität geht als `activityType` an `EditStagesSection` (`TripTabs.svelte:220`).
- **Speicherwege:** Trip-Name per `PUT /api/trips/{id} {name}` (`TripHeader.svelte:45`, `UpdateTripHandler` `internal/router/router.go:210`, Patch-DTO: fehlendes Feld = unverändert). Vergleich per `PUT /api/compare/presets/{id}` nur mit dem geänderten Feld (`router.go:251`, `UpdateComparePresetHandler`, Merge seit #2285). Ob ein Trip-PUT `{region}` sauber gemergt wird, prüft die Analyse am Go-Handler.

## Existing Patterns
- Inline-Bearbeitung im Kopf mit Stift-Schalter: `TripHeader.svelte` (Name) und Compare-Kopf (Name, Region, Profil), Spec `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md`.
- Speicher-Chip: `createSaveStatus({typ,id})` + `ui/SaveIndicator.svelte` als fixes Overlay, Specs `feat_880_autosave_overlay.md` und `feat_1273_s1_compare_hub_save_chip.md`.
- Geteilte Reiter-Organismen mit `context="route"|"vergleich"` unter `FE/shared/`; Trip-Speichern über `saveController` (seit #2276).
- `createMode`-Prop bei geteilten Organismen auf den Anlege-Seiten (#2277).

## Dependencies
- Upstream: `ui/SaveIndicator.svelte`, `stores/saveStatus`, `api.put`, Go `UpdateTripHandler`/`UpdateComparePresetHandler`, `shared/versand-tab/VersandTab.svelte`, `shared/alarme-tab/AlarmeTab.svelte`, `weatherSaveGate`.
- Downstream: `routes/trips/[id]/+page.svelte` (395 Z.), `routes/compare/[id]/+page.svelte` (516 Z.), `TripTabs.svelte` (394 Z.), `CompareTabs.svelte` (1.468 Z.), `TripNewEditor.svelte` (context-Mounts), Home-Hero und Trip-Liste (lesen `region`).

## Tests (Bestand)
- Unit: `trip-detail/TripHeader.issue699|mobile-metrics|spacing.test.ts`; `ui/__tests__/saveIndicatorConflictBranch.test.ts`; `stores/__tests__/saveStatus.test.ts`; `trip-detail/__tests__/weatherSaveGate.test.ts`; `shared/__tests__/versand_speicherung_nur_im_vergleich_hub.test.ts`, `alarme_save_single_writer.test.ts`, `alarme_tab_catalog_prop_structure.test.ts`; `shared/corridor-editor/corridorEditorMobile.test.ts:189-213` (einziger context-Mount-Check, nur für CorridorEditorMobile).
- Playwright: Trip-Kopf `issue-302-trip-detail-redesign`, `issue-724-trip-name-save-error`, `issue-714-trip-ui-polish`, `issue-616-trip-one-surface` (nur im CI-Stack fahrbar), `trip-header-btn-migration`. Speicher-Chip `issue-758-save-indicator`, `feat-880-autosave-overlay`, `save-status-indicator-honesty`. Compare-Kopf `compare-hub-name-region-profil` (+ staging.setup), `compare-hub-inline-edit`, `compare-hub-save-chip`, `compare-hub-fidelity-s8c`.
- Ein generischer Test „jeder Mount trägt `context=`" fehlt (AC-4 des Issues).

## Existing Specs
- `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`, `feat_1273_s2_compare_hub_name_region_profil.md`, `feat_880_autosave_overlay.md`, `versand_tab_route.md`, `versand_tab_vergleich.md`, `rework_2276_*`, `feat/fix_2277_*`.
- Archiv: `_archive/modules/issue_302_trip_detail_page.md` (TripHeader.svelte:3 verweist noch auf den alten Pfad), `issue_758_save_indicator.md`, `issue_215_sprint1_trip_detail_header.md`.
- Für den Trip-Hub-Kopf gibt es **keine aktive Spec**.

## Abgrenzung
- **#2278** (Aktionsmodell): Trip hat kein Kebab, sondern offene Knöpfe in der Breadcrumb-Leiste (`routes/trips/[id]/+page.svelte:284-333`). Löschen ist im Trip-Hub nicht erreichbar (`handleDeleteClick` `:173` ohne Aufrufer). Das Zielbild von #2284 nennt einen „Lifecycle-Kebab" im Kopf, das Aktionsmodell selbst gehört aber zu #2278. Den Schnitt legt die Analyse fest.
- **#2287** (Reiter-Kennungen) und **#2288** (Drag & Drop) folgen danach, nicht hier.
- `pendant_gate.py` überwacht nur **neue** Dateien in `compare/`, `compare-new/`, `trip-detail/`, `trip-new/`; `shared/` ist ausgenommen. Ein neuer `SubscriptionHeader` gehört nach `shared/`.

## Risks & Considerations
- **Parallele Sitzung #1433** (412-Konflikt, Datenverlust beim Editieren in zwei Tabs, Trip-Hub) arbeitet vermutlich in denselben Dateien (`routes/trips/[id]/+page.svelte`, Speicherweg, TripHeader). Vor der Umsetzung den Merge-Stand von #1433 prüfen bzw. über `SendMessage` abstimmen.
- **Datenerhalt:** Ein Region-Edit beim Trip darf nur `region` schreiben. Patch-DTO-Verhalten am Go-Handler belegen; mit zwei Nutzern testen (Mandantentrennung).
- **BriefingScheduleTab-Rückbau:** Eigener Autosave, `weatherSaveGate` und Capture-Hooks haben Gründe (Gesten-Erkennung gegen Autosave beim bloßen Öffnen). Beim Rückbau darf reines Öffnen weiter keinen PUT auslösen (vgl. #2277 S5 AC).
- **Profil ≠ Aktivität:** verschiedene Wertebereiche. „Gleiche Bedienung" heißt gleicher Ort und gleiche Geste, nicht gleiche Optionen.
- **Scope/LoC:** Ein Kopf-Baustein, der Rückbau zweier Hüllen, die VTLaufzeit-Zusammenführung und ein Mount-Wächter liegen deutlich über 250 LoC. Scheibenschnitt in der Analyse (Epic-Regel: themenweise abschließen, Scheiben im selben Ticket).
- Die Mail-Renderer sind nicht betroffen (Trip-Region liest kein Renderer), deshalb ist kein Mail-Validator im Umfang.

## Analysis

### Type
Feature (Parität Trip-Hub ↔ Vergleich-Hub, Epic #2345 Etappe P2). Kein Backend-Umbau.

### Zusätzliche Befunde der Analyse (2026-10-02)
- **Backend trägt schon:** `PUT /api/trips/{id}` ist ein Patch-DTO mit Pointer-Feldern (`internal/handler/trip.go:224-266`, Merge `:377-383`). `{region}` bzw. `{activity}` ändern nur dieses Feld; `""` überschreibt (= Region löschen). Keine Längenprüfung für `region` (Vergleich: Eingabe `maxlength=60` nur im Frontend). If-Match/412 vorhanden. Go-Tests: `internal/handler/trip_region_test.go` (Create, PreservedOnUpdate, UpdateReplacesWhenSent), `trip_etag_ifmatch_test.go`.
- **Befund 3 (zweiter Speichern-Knopf) ist im Verhalten schon erledigt:** `BriefingScheduleTab` wird nur in `TripTabs.svelte:233` gemountet, immer MIT `saveController` → der Knopf `:139-154` ist toter Code, der Versand-Reiter speichert heute schon automatisch. Offen ist nur der Rückbau der Hülle. Die Hülle trägt echte Logik: reportConfig-Klon, `$effect`-Autosave über `saveController.doSave`, `weatherSaveGate` (`catalogLoaded && userTouched`), capture-Hooks für Gesten. `AlarmeScheduleTab` trägt nur Ableitungen (`metricLevels`, `deriveActiveAlertMetricsForTrip`, `reconstructTripAlertChannels`).
- **Aktivität in den Kopf ist verhaltensneutral:** `EditStagesPanelNew.svelte:228-231` leitet die Ankunftszeiten nur per `$derived` ab (Anzeige). Kein `$effect` speichert nach einem Aktivitätswechsel die Etappen nach. Der Wechsel schreibt weiterhin nur `{activity}`.
- **Compare-Kopf:** Name/Region/Profil als Inline-Markup direkt in `routes/compare/[id]/+page.svelte`, Desktop (`:337-387`) und Mobil (`:420-482`) doppelt mit gleichen testids `compare-hub-{name,region}-edit-toggle|edit|save|save-error`. E2E: `compare-hub-name-region-profil.spec.ts`.
- **TripHeader** (325 Z.): Name-Edit `:123-163` (testids `trip-detail-h1`, `trip-name-edit-toggle|edit|save|save-error`), Eyebrow `:59-61`, SaveIndicator `:194-196`. Aktionsknöpfe liegen in `routes/trips/[id]/+page.svelte` (Breadcrumb) → #2278.
- **Mounts ohne `context=`** (vollständig, alle anderen tragen es): `TripTabs.svelte:223` (WeatherMetricsTab), `:228` (CorridorEditor), `TripNewEditor.svelte:900,1175` (WeatherMetricsTab).
- **VTLaufzeit:** `VTLaufzeitRoute` (Props `tripEnd`, `onOpenStages`; testid `briefings-laufzeit`; nur lesend) und `VTLaufzeitVergleich` (`value`, `onChange`; testids `briefings-laufzeit-vergleich`, `compare-versand-enddate-*`). Einzige Mounts `VersandTab.svelte:400/434`.
- **metricsCatalog:** Epic #2345 weist die Vereinheitlichung NICHT P7 zu (P7 = Datenmodell). Sie bleibt deshalb Teil von #2284 als eigene Scheibe — kein abgespaltener Rest.
- **Parallelarbeit:** PR #2486 (#1433, Trip-Konfliktschutz im Mehrreiter-Fall, Sitzung im Worktree `hashed-splashing-blanket`) ist OFFEN und ändert `TripHeader.svelte`, `TripTabs.svelte`, `routes/trips/[id]/+page.svelte`, `CompareTabs.svelte`. Abstimmung über `ListAgents` + `SendMessage`, nicht MQ.

### Scope-Schnitt
- **Drin (#2284 gesamt):** geteilter Kopf-Baustein (Name/Region/Profil bzw. Aktivität inline, Speicher-Chip an einer Stelle), Trip-Region editierbar, Aktivität aus dem Etappen-Reiter in den Kopf (Optionen je `kind` getrennt: Trip `activity`, Vergleich `profil`; „gleich" = gleicher Ort, gleiche Geste), Rückbau beider Trip-Hüllen, ein `VTLaufzeit` mit `context`, explizites `context=` an allen Mounts + Wächter, metricsCatalog-Ladeweg vereinheitlicht.
- **Raus:** Kebab/Lifecycle-Aktionen → #2278 (der Kopf bekommt nur einen leeren `actions`-Snippet-Slot als Andockpunkt). Reiter-Kennungen → #2287, Drag & Drop → #2288.

### Scheibenplan (je Scheibe ein eigener Workflow + eigene Spec auf #2284, Muster #2277)
Summe aller Scheiben ≈ 700 LoC Produktivcode — passt nicht in einen Workflow (Limit 250, Override max. 500). Daher:

| Scheibe | Inhalt | ACs (Ticket) | LoC prod (Schätzung) | Abhängigkeit |
|---|---|---|---|---|
| **S1 = dieser Workflow** | `shared/subscription-header/SubscriptionHeader.svelte` bauen; Compare-Kopf darauf umstellen (Doppelmarkup Desktop/Mobil entfällt, testids unverändert über `testidPrefix`). Speicher-Chip bleibt in S1 noch an seinem Ort. | Vorstufe zu AC-1/AC-2 | ~230 neu, ~−150 in `compare/[id]/+page.svelte` | keine — berührt keine Datei von #2486 |
| S2 | Trip-Kopf auf den Baustein: Region inline (neue testids `trip-region-*`), Aktivität in den Kopf (Select aus `TripTabs` entfernt), Speicher-Chip in beiden Hubs in den Baustein (raus aus TripHeader und `CompareTabs.svelte:728-732`). Region-Speichern über denselben Weg wie Name nach #2486 (If-Match). | AC-1, AC-2 | ~150 | **erst nach Merge #2486** |
| S3 | Hüllen-Rückbau: Logik in Trip-Helfer `trip-detail/tripBriefingState.svelte.ts`, `TripTabs` mountet `VersandTab`/`AlarmeTab` direkt; toter Knopf entfällt; ~11 Unit-Tests auf den Helfer umhängen (Aussage erhalten, nicht löschen). | AC-3 (umformuliert, s. u.) | ~200 brutto, netto negativ | **erst nach Merge #2486** |
| S4 | ein `VTLaufzeit.svelte` mit `context` (testids erhalten) | Zielbild | ~120 | keine |
| S5 | metricsCatalog: ein Ladeweg für beide Hubs | Befund 5 | offen, in S5-Analyse | nach S3 |
| S6 | 4 fehlende `context=` + Mount-Wächter | AC-4 | ~20 + Test | zuletzt |

### Affected Files (S1)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | CREATE | Kopf-Baustein, Props: `kind`, `name`, `region`, `profile`, `profileOptions`, `profileLabel`, `eyebrow`-Snippet, `regionMaxLength`, `testidPrefix`, `onSaveField(field, value)` (wirft bei Fehler), `actions`-Snippet (leer). Kein `api`-Import, kein `if kind ==` im Markup. |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Inline-Markup Desktop+Mobil durch Baustein ersetzen; Speicherfunktionen `:170-225` werden zu `onSaveField` |
| `frontend/src/lib/components/shared/__tests__/…` | CREATE | Unit-Tests für den Baustein (SSR-Harness, Muster vorhandener shared-Tests) |
| `frontend/e2e/compare-hub-name-region-profil.spec.ts` u. a. `compare-hub-*` | unverändert | müssen grün bleiben (Regression), `compare-hub-fidelity-s8c` ist das größte Layout-Risiko |

### Scope Assessment (S1)
- Files: 2 prod + Tests
- Estimated LoC: +~230 / −~150
- Risk Level: MEDIUM (Umbau einer häufig genutzten Fläche; Schutz durch bestehende E2E mit unveränderten testids)

### Technical Approach
Baustein nach `shared/` (vom `pendant_gate` ausgenommen). Unterschiede zwischen Trip und Vergleich liegen ausschließlich in Props (Optionen, Speicherfunktion, Präfix), nie im Markup. Ein Markup für Desktop und Mobil mit responsiver Klasse; weicht die Mobil-Anordnung stark ab, ein `{#snippet}` im selben Baustein, nie eine zweite Komponente. Die Seite liefert `onSaveField` → Read-Modify-Write und Merge-Verhalten bleiben auf Seiten-/Backend-Ebene wie heute (Vergleich: `PUT /api/compare/presets/{id}` nur mit dem geänderten Feld).

### Test-Hinweise für spätere Scheiben (festgehalten, damit nichts verloren geht)
- **AC-3 umformulieren** (Verhalten ist sichtbar schon erfüllt, ein RED-Test wäre sofort grün): „Trip-Versand-Reiter öffnen ohne Geste → kein PUT; Uhrzeit ändern → genau ein PUT über `saveController`." Bewacht den Hüllen-Rückbau. Bestehende Wächter: `weatherSaveGate.test.ts`, `versand_speicherung_nur_im_vergleich_hub.test.ts`, `alarme_save_single_writer.test.ts`. Der reportConfig-Klon darf nicht bei jedem Prop-Update neu initialisiert werden (Schreib-Echo).
- **AC-4-Wächter** nicht als String-grep (Dateiinhalt-Check ist als Verhaltensnachweis verboten), sondern strukturell per AST über die `.svelte`-Dateien — Muster `shared/__tests__/alarme_tab_catalog_prop_structure.test.ts`; mit Negativ-Fall.
- **S2 Datenerhalt:** Region ändern → Name, Etappen, report_config unverändert; zwei Nutzer (B kann A's Region nicht schreiben); `region: ""` löscht sauber; Home-Hero (`routes/+page.svelte:202`) und Trip-Liste (`routes/trips/+page.svelte:417`) blenden leere Region aus.

### Dependencies
- Upstream: `ui/SaveIndicator.svelte`, `stores/saveStatus`, `api.put`, Go `UpdateTripHandler`/`UpdateComparePresetHandler` (unverändert).
- Downstream S1: nur `routes/compare/[id]/+page.svelte`.
- PR #2486 blockt S2/S3, nicht S1.

### Open Questions
- Keine an den PO. Technische Entscheidungen oben getroffen (Aktivität in den Kopf: ja; Kebab → #2278; metricsCatalog als eigene Scheibe in #2284).
