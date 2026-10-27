# Context: feat-2284-s2-trip-kopf

Issue #2284 · Scheibe S2 · Epic #2345, Etappe P2. Gemessen am 2026-10-03 auf `8432a3f0b` (main).
FE = `frontend/src/lib/components`. Zeilennummern aus dem heutigen Stand, **nicht** aus
`feat-2284-hub-kopf-paritaet.md` (dort gemessen auf `772cf8e0`, mehrere Bereiche haben sich verschoben).

## Request Summary
Der Trip-Hub-Kopf wird auf den in S1 gebauten geteilten Baustein `SubscriptionHeader` umgestellt:
Region wird inline editierbar (neue testids `trip-region-*`), die Aktivität wandert aus dem Etappen-Reiter
in den Kopf, und der Speicher-Chip (`SaveIndicator`) zieht in **beiden** Hubs in den Baustein (Trip: heute
in `TripHeader`, Vergleich: heute in `CompareTabs`). Nicht in S2: Rückbau `AlarmeScheduleTab`/`BriefingScheduleTab` (S3).

**Blocker aufgehoben:** PR #2486 (#1433, Trip-Konfliktschutz) ist am 2026-10-03 07:26 UTC gemergt. Im
selben Speicher-Bereich ist außerdem #2215 gelandet (`setUnsavedInput`, Commit `74ed601a9`, hält die
Anzeige auf `dirty`, solange ein vorgemerkter Save läuft — betrifft `WeatherMetricsTab`, `CorridorEditor`, Briefing).

## Related Files

| File | Relevance |
|------|-----------|
| `FE/shared/subscription-header/SubscriptionHeader.svelte` (140 Z.) | Der Baustein aus S1. Props `:18-32` (`kind`, `name`, `region`, `profile`, `profileOptions`, `profileLabel`, `regionMaxLength`=60, `testidPrefix`, `onSaveField(field,value,schliessen)`, Snippets `eyebrow/badges/meta/actions`). `save()` mit drei Ausgängen `:64-77`. `<h1>` **ohne testid** und nur `{name}` `:100`. Name-Eingabe **ersetzt** die `<h1>` im Bearbeitungsmodus `:96-102`. Region-Anzeige `{region ?? '—'}` `:112`. `meta`-Snippet rendert **innerhalb der Region-Zeile** `:107-118`. Profil als Kachelreihe (Buttons) `:120-138`, testids `${p}-profil-option-${value}`. Kein `SaveIndicator`-Slot/-Prop. |
| `FE/shared/__tests__/subscription_header_{kontextneutral,einmal_gerendert,bedienlogik}.test.ts` | S1-Bausteintests; `kontextneutral` rendert schon einen Trip-Prop-Satz (`testidPrefix:'trip'`, Optionen `trekking/skitour`, erwartet `trip-name-edit-toggle`, `trip-region-edit-toggle`, `trip-profil-option-*` — `:84-91`, `:155-160`). `bedienlogik` prüft `aria-label="Region bearbeiten"` `:96`. |
| `FE/trip-detail/TripHeader.svelte` (331 Z.) | Heutiger Trip-Kopf. Name-Edit-State `:36-39`, `makeNameSaveHandler` `:41-60` (`baueTripSpeicherung(api, trip.id, {name}, …, 'kopf')` + `speichereOderMeldeKonflikt`), Eyebrow `REGION · DATUM` `:67,125-127`, `<h1 data-testid="trip-detail-h1">` mit Shortcode-Präfix `:130-132`, Stift `trip-name-edit-toggle` (aria `Trip-Name bearbeiten`) `:133-143`, Edit-Zeile **unter** der weiter sichtbaren `<h1>` `:146-169` (testids `trip-name-edit`, `trip-name-save`, `trip-name-save-error`), Status-Zeile `trip-detail-status-supplement` + `TripStatusBadge` `:171-176`, Meta `trip-detail-meta` (km/Hm) `:178-181`, Mobil-Kacheln `trip-header-mobile-metrics` `:186-196` (CSS `:321-330`), **SaveIndicator `:198-202`**. Außen `<header class="trip-header">` `:122`. |
| `FE/trip-detail/TripTabs.svelte` (399 Z.) | `activityType = $state(trip?.activity)` **nur beim Mount** `:62`. `handleActivityChange` `:184-194` (`baueTripSpeicherung(…, {activity: val \|\| undefined}, onTripUpdate, 'aktivitaet')`). Select-Zeile „AKTIVITÄT" `:206-224` (`data-testid="edit-activity-dropdown"`, 8 Optionen). `EditStagesSection … activityType={activityType}` `:225`. |
| `frontend/src/routes/trips/[id]/+page.svelte` (450 Z.) | `trip = $state(data.trip)` `:27`; `tripSaveCtl = createSaveStatus({typ:'trip', id})` `:50`; `registriereUebernahme` (`'geholt'` ⇒ nur `trip` setzen) `:77-83`; `registriereAbgelehnt` (`trip = wendeNutzlastAn(...)`) `:89-91`; `handleTripUpdate` `:281-283`; Breadcrumb-Leiste mit Aktionsknöpfen `:333-389` (→ #2278); `<TripHeader … saveController={tripSaveCtl}/>` `:390` (außerhalb `{#key}`); `{#key uebernommeneFassung}<TripTabs …/>` `:391-400`. Alles in `<main>` `:331`. |
| `frontend/src/routes/trips/[id]/+page.server.ts` (37 Z.) | Lädt Trip + `metricsCatalog` parallel, liefert `etag` `:17-36`. Für S2 unverändert. |
| `frontend/src/routes/compare/[id]/+page.svelte` (406 Z.) | Referenzmuster S1: `KOPF_RUMPF` / `KOPF_SCHLUESSEL` (`kopf-name/kopf-region/kopf-profil`) `:186-191`, `onSaveField` mit `baueSpeicherung` + `imWiederholen`-Guard `:192-202`, Mount `<SubscriptionHeader kind="vergleich" …>` `:314-343`. Kopf liegt **außerhalb** von `{#key uebernommeneFassung}` (`:381-390`). |
| `FE/compare/CompareTabs.svelte` (1490 Z.) | `import SaveIndicator` `:25`; **Chip-Mount `:750-754`** (Kommentar verweist noch auf „TripHeader.svelte:194-195"). Liegt unter `CompareDetail` (`CompareDetail.svelte:33`) ⇒ innerhalb von `{#key uebernommeneFassung}` der Seite. `CompareTabs`/`CompareDetail` werden **nur** im Vergleich-Hub gemountet (`routes/compare/[id]/+page.svelte:382`). |
| `FE/ui/SaveIndicator.svelte` (155 Z.) | Prop nur `controller` `:7-10`; `data-testid="save-indicator"`, `data-state` `:20-28`; Zustände idle/dirty/saving/conflict(„Nochmal speichern" `:41-46`)/error. `position: fixed` unten rechts, `z-index: 62` `:61-65`, mobil über BottomNav `:81-85`; Dimming per CSS-Animation (kein lokaler JS-Zustand). Mount-Ort ist daher optisch frei, solange kein Vorfahr `transform`/`filter` trägt. |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `createSaveStatus(kennung)` `:466`; `imWiederholen` `:87`; `registriereAbgelehnt` `:98`; `registriereUebernahme` `:106`. |
| `FE/shared/tripSpeicherung.ts` | `baueSpeicherung(client, pfad, body, nachErfolg, schluessel)` `:46-63`; `baueTripSpeicherung` (Pfad `/api/trips/{id}`) `:65-73`; `speichereOderMeldeKonflikt` (412 ⇒ `meldeKonflikt`, sonst wirft) `:87-101`. |
| `FE/shared/OfflineSperre.svelte` | Sperrt offline **jedes** `main button/input/select/textarea` am DOM `:41-47` (Ausnahme `[role=tab]`, `[data-offline-erlaubt]`). Neue Kopf-Bedienelemente sind automatisch gesperrt, solange sie in `<main>` liegen. |
| `FE/edit/EditStagesPanelNew.svelte` | Mobil-Editor-Höhe aus der gemessenen Oberkante (Breadcrumb/TripHeader/Tab-Leiste) `:59-85` — ein höherer Kopf verkleinert die Karte mobil. |
| `frontend/src/lib/types.ts` | `ActivityType` (8 Werte) `:28-30`; `Trip.activity?`, `Trip.region?` `:345-346`; Vergleich `ActivityProfile`/`ACTIVITY_PROFILE_OPTIONS` `:127-134`. Für Trip-Aktivität gibt es **keine** Options-Konstante. |
| `internal/handler/trip.go` | Patch-DTO `tripUpdateRequest` `:243-286` — **`Region *string` `:260` und `Activity *string` `:261` sind enthalten** (beide `omitempty`). Merge `:397-403` (nur bei non-nil). `UpdateTripHandler` `:288` mit `s.WithUser(middleware.UserIDFromContext(...))` `:290`. Keine Längen-/Wertprüfung für `region` oder `activity`. |
| `internal/model/trip.go` | `Activity string` `:128`, `Region string` `:129` (beide `omitempty`). |
| `src/app/loader.py:1711-1712` | Python schreibt `region` nur, wenn gesetzt (leer ⇒ Schlüssel fehlt). Kein Renderer liest Trip-Region ⇒ kein Mail-Validator im Umfang. |
| Leser von `trip.region` | Home-Hero `routes/+page.svelte:202-207`, Trip-Liste `routes/trips/+page.svelte:417-418` (beide `{#if …}` ⇒ leere Region ausgeblendet). |

## Existing Patterns
- **S1-Muster Vergleich** (`routes/compare/[id]/+page.svelte:186-202`): Seite liefert `onSaveField(field, value, schliessen)`, sendet **nur** das eigene Feld, Konflikt-Schlüssel je Feld, drei Ausgänge (gespeichert ⇒ `schliessen()`; 412 ⇒ Promise erfüllt ohne `schliessen`; Fehler ⇒ wirft).
- **Trip-Speicherweg heute:** `baueTripSpeicherung` + `speichereOderMeldeKonflikt(…, saveController)` sowohl für Name (`TripHeader.svelte:48-53`, Schlüssel `'kopf'`) als auch Aktivität (`TripTabs.svelte:190-193`, Schlüssel `'aktivitaet'`). Nach Erfolg `onTripUpdate(updated)` ⇒ `trip = updated` auf der Seite.
- **Trip-Retry-Übernahme:** Phase `'geholt'` setzt nur `trip`, kein Neuaufbau; Neuaufbau der Reiter erst bei `'wiederholt'` über `{#key uebernommeneFassung}` (`+page.svelte:71-83`). Der Kopf liegt außerhalb des `{#key}` und wird nie neu aufgebaut.
- **Ein `SaveIndicator` je Seite**, `position: fixed` (Specs `feat_880_autosave_overlay.md` AC-1/AC-7: genau ein `save-indicator` im DOM).
- **Trip/Vergleich-Teilung als Gate:** keine `if kind ===`-Verzweigung im Markup (S1 Entscheidung 4, AC-6); Unterschiede nur über Props/Snippets.

## Dependencies
- **Upstream:** `SubscriptionHeader.svelte` (S1), `ui/SaveIndicator.svelte`, `saveStatusStore`, `tripSpeicherung.ts` (`baueTripSpeicherung`, `speichereOderMeldeKonflikt`), `etagRegistry` (If-Match automatisch über `api.put`), Go `UpdateTripHandler` (unverändert; trägt `region`/`activity` bereits).
- **Downstream:** `routes/trips/[id]/+page.svelte`, `TripHeader.svelte` (Umbau oder Rückbau), `TripTabs.svelte` (Select raus, `activityType` reaktiv), `CompareTabs.svelte` (Chip raus), `routes/compare/[id]/+page.svelte` (Chip über den Baustein), `EditStagesSection`/`EditStagesPanelNew` (Ankunftszeiten hängen an `activityType`), Home-Hero + Trip-Liste (lesen `region`), #1433-Test-Harness (s. u.).
- **Nachfolgend:** S3 (Hüllen-Rückbau) berührt `TripTabs.svelte` erneut; #2278 (Aktionsmodell) dockt am `actions`-Slot an.

## Existing Specs
- `docs/specs/modules/feat_2284_s1_subscription_header.md` — Baustein-Vertrag (Entscheidungen 1-8, insb. 3 = `onSaveField`/`schliessen`, 4 = kein `kind`-Zweig, 5 = ein Markup, 8 = Chip-Umzug nach S2); Out-of-Scope listet S2.
- `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md` — Verhaltens-ACs des Vergleich-Kopfs (AC-1…AC-7: sofort sichtbar, persistiert, Teil-Edit ohne Datenverlust, Cross-Tab, Mobil-Parität, Fehlerfall). Vorlage für die Trip-ACs.
- `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md` (#1433) — AC-10 (412 bei Name/Aktivität ⇒ „Nochmal speichern"), AC-15 (Nutzlast nur Eigenfeld `name`/`activity`), AC-18 (If-Match bleibt nach 412). Gilt für den neuen Weg weiter; `region` kommt als Eigenfeld hinzu.
- `docs/specs/modules/feat_880_autosave_overlay.md` — Chip fix unten rechts, genau einer im DOM (AC-1, AC-7).
- `docs/context/feat-2284-hub-kopf-paritaet.md` — Analyse + Scheibenplan (S2 ≈ 150 LoC prod, AC-1/AC-2 des Issues), Test-Hinweis „S2 Datenerhalt" (`:110`).
- Für den Trip-Hub-Kopf selbst gibt es keine aktive Spec (Archiv: `_archive/modules/issue_302_trip_detail_page.md`).

## Bestehende Tests & testids (die der Umbau berührt)

**CI-Ratsche (`.github/ci_e2e_specs.txt`) — harte Wächter**
| Spec | Greift auf | Risiko bei Umbau |
|---|---|---|
| `e2e/issue-724-trip-name-save-error.spec.ts` | `trip-detail-h1` (sichtbar vor dem Edit `:52,83,111`), `trip-name-edit-toggle/-edit/-save/-save-error`, nach Erfolg `trip-detail-h1` enthält neuen Namen `:91` | `SubscriptionHeader`-`<h1>` hat **keine** testid ⇒ rot, solange `trip-detail-h1` nicht erhalten bleibt. Name-testids passen bei `testidPrefix="trip"` exakt. |
| `e2e/issue-714-trip-ui-polish.spec.ts` | `trip-detail-h1` sichtbar, `trip-name-edit` versteckt `:111-113`; Edit → Save → Feld versteckt `:132-138` | wie oben |
| `e2e/issue-616-trip-one-surface.spec.ts` | Namens-Edit `:156-160`; `save-indicator` `data-state="idle"` nach Versand-Änderung `:131` | Chip muss weiter genau einmal und am selben Controller hängen |
| `e2e/issue-336-status-dedup.spec.ts` | `trip-detail-status-supplement` `:33,66`, `trip-detail-meta` `:73`, Locator `header.trip-header` `:53,112` | Bricht, wenn `<header class="trip-header">` oder Status-/Meta-Zeile wegfallen |
| `e2e/compare-hub-name-region-profil.spec.ts`, `compare-hub-save-chip.spec.ts`, `compare-hub-fidelity-s8c.spec.ts`, `compare-hub-inline-edit.spec.ts` | Vergleich-Kopf + Chip | Chip-Umzug in den Baustein darf Verhalten/Anzahl nicht ändern |

**Nur live/Staging (nicht in der Ratsche)**
- `e2e/feat-880-autosave-overlay.spec.ts`: `save-indicator` `toHaveCount(1)` und `position: fixed` auf Trip (`:86-91`) **und** Vergleich (`:205-208`) — Doppel-Mount während des Umzugs fällt hier auf.
- `e2e/issue-758-save-indicator.spec.ts`, `e2e/save-status-indicator-honesty.spec.ts`: Chip-Zustände über `data-state`.
- `e2e/pwa-offline-sperre-und-mandant.spec.ts:216-222`: erwartet `edit-activity-dropdown` **im Etappen-Reiter** sichtbar und offline `disabled`; `:410-416` `selectOption('skitour')` dort. Zieht die Aktivität in den Kopf, muss die Spec auf den neuen Ort zeigen (Aussage „offline gesperrt" erhalten).
- `e2e/feat-1461-s3b2b-compare-kanal-schwelle.spec.ts:385-391`: öffnet `?tab=stages`, nutzt `edit-activity-dropdown` als PUT-Auslöser.
- `e2e/compare-hub-kopf-einmal.spec.ts` (S1): jede Kopf-testid genau einmal — gilt künftig auch für die Trip-Seite als Muster.

**Tot**
- `e2e/issue-943-activity-edit.spec.ts` zielt auf `/trips/<id>/edit` + `trip-edit-view` (`:29-37`); die Route leitet um (`routes/trips/[id]/edit/+page.svelte:1`). `edit/issue_943_activity_edit.test.ts` prüft nur Existenz/Inhalt der E2E-Datei (`:27-42`) — vom Umbau unberührt.

**Kern-Unit-Tests**
- `FE/trip-detail/__tests__/tripMehrreiterPruefstand.ts` greift in **Komponenten-Interna**: `kopfReiter` baut `TripHeader.svelte` und ruft `inst.u.editName` + `inst.u.makeNameSaveHandler()` `:425-438`; `aktivitaetReiter` baut `TripTabs.svelte` und ruft `inst.u.handleActivityChange` `:440-460` (Pfade `DATEI.kopf/tabs` `:43-44`). Benutzt von `trip_kopf_aktivitaet_melden_konflikt.test.ts` (`:50,62,77,89,96,111`), `trip_reiter_roundtrip_jedes_feld.test.ts` (`:312,319`), `trip_reiter_nutzlast_nur_eigene_felder.test.ts` (`:225,232`), `trip_konflikt_schreibt_seitenstand_fort.test.ts`. Entfallen diese Funktionen, werden die Tests rot. **Präzedenz S1** (Commit `db1576d33`): die #1433-Kopf-Tests des Vergleichs wurden auf `onSaveField` umgehängt, Zusicherungen unverändert. `tripSeite` (`:486-538`) baut bereits das Skript von `routes/trips/[id]/+page.svelte` — ein seitenseitiges `onSaveField` wäre über `inst.u.onSaveField` erreichbar.
- `FE/trip-detail/TripHeader.issue699.test.ts`, `TripHeader.spacing.test.ts`, `TripHeader.mobile-metrics.test.ts`: `readFileSync`-Quelltextprüfungen auf `TripHeader.svelte` (Eyebrow `eyebrowText`/`dateRange`, `meta-line`, Mobil-Kacheln, Importe). Brechen bei Umbau/Verschiebung der Quelltextstellen; nach Projektregel sind Dateiinhalt-Checks kein Verhaltensnachweis.
- `FE/ui/__tests__/saveIndicatorConflictBranch.test.ts`, `stores/__tests__/saveStatus.test.ts`: Chip/Controller selbst — vom Umzug nicht berührt.
- Go: `internal/handler/trip_region_test.go` (`CreateAndRead`, `PreservedOnUpdate`, `UpdateReplacesWhenSent` `:21,68,113`), `trip_etag_ifmatch_test.go` inkl. `TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers` `:236`, `entity_traversal_test.go:460` (zwei echte Nutzer). Ein Fall „Nutzer B sendet minimalen Kopf-Rumpf `{region}` gegen A's Trip-ID ⇒ A's Datei byte-gleich" fehlt (Analogon zu S1 AC-11).

**Neue testids aus dem Baustein bei `testidPrefix="trip"`:** `trip-name-edit-toggle|edit|save|save-error` (identisch zu heute), `trip-region-edit-toggle|edit|save|save-error` (neu), `trip-profil-option-<activity>` und `trip-profil-save-error` (neu; Präfix „profil" ist im Baustein fest verdrahtet `:90,125`).

## Risks & Considerations
- **Reaktivität Aktivität → Etappen (Fakt):** `TripTabs` hält `activityType` als Mount-`$state` (`:62`). Ändert künftig der Kopf `trip.activity`, bekommt `EditStagesSection` (`:225`) den neuen Wert nicht — die Ankunftszeiten (Naismith, `EditStagesPanelNew` `$derived`) blieben veraltet, bis der Reiter neu gemountet wird. `TripTabs` muss `trip.activity` reaktiv durchreichen.
- **Datenerhalt / Teil-Edit:** Kopf-PUTs dürfen nur `{name}`, `{region}` bzw. `{activity}` senden (Go merged nur non-nil, `trip.go:397-403`). Kein Spread des Seiten-`trip`. Mit zwei Nutzern testen (Mandantentrennung, CLAUDE.md-Pflicht).
- **Region leeren:** Baustein zeigt `region ?? '—'` (`:112`) — ein gespeicherter Leerstring `""` erscheint als leere Zeile, nicht als „—". Go `omitempty` + Python `if trip.region` ⇒ Leerstring = Feld fehlt; Home-Hero/Trip-Liste blenden aus. Gilt auch für den Vergleich.
- **Activity leeren nicht möglich:** heute `activity: val || undefined` ⇒ Schlüssel fällt aus dem JSON, Server lässt den Wert stehen. Mit Kacheln gibt es ohnehin keine „leer"-Option; Trips ohne `activity` zeigen dann keine Kachel als gewählt.
- **Chip-Umzug ohne Doppel-Mount:** `CompareTabs.svelte:750-754` und `TripHeader.svelte:198-202` müssen im selben Schritt entfallen, in dem der Baustein den Chip rendert (feat-880 `toHaveCount(1)`). Beim Vergleich wandert der Chip damit aus dem `{#key uebernommeneFassung}`-Bereich heraus (kein Remount mehr beim Neuaufbau) — verhaltensneutral, da `SaveIndicator` keinen lokalen JS-Zustand hat; prüfen, dass kein Vorfahr des Kopfs `transform`/`filter` setzt (sonst bricht `position: fixed`).
- **Mobil-Höhe:** 8 Aktivitäts-Kacheln + Region-Zeile machen den Trip-Kopf mobil deutlich höher; `EditStagesPanelNew` berechnet die Kartenhöhe aus der Oberkante (`:59-85`) ⇒ weniger Kartenfläche im Etappen-Reiter auf 375 px.
- **#1433-Harness:** vier Kern-Testdateien hängen an `makeNameSaveHandler`/`handleActivityChange`/`editName` — umhängen, Aussagen erhalten (nicht löschen), sonst `test`-Job rot.
- **`trip-detail-h1` und `header.trip-header`** sind CI-Wächter (724, 714, 336). Ein reiner Austausch von `TripHeader` gegen den Baustein ohne diese Anker bricht die Ratsche.
- **Offline-Sperre:** greift automatisch für neue Knöpfe in `<main>`; pwa-offline-Spec muss auf den neuen Ort der Aktivität umgestellt werden.
- **LoC:** S2-Schätzung ~150 prod; Harness-/E2E-Umstellungen zählen nicht. Mit TripHeader-Umbau + TripTabs + CompareTabs + Baustein-Erweiterung (Chip) realistisch nahe am Limit 250 — vorab `workflow.py status` prüfen.
- **Parallelarbeit:** S3 fasst `TripTabs.svelte` ebenfalls an — nicht parallel starten.

## Offene Fragen für die Analyse
1. **`trip-detail-h1`:** Baustein-`<h1>` bekommt eine testid (generisch `${p}-…` oder optionaler Prop) — oder die CI-Specs 724/714/302 werden umgestellt? (Specs ohne PO-Freigabe zu ändern ist heikel; S1 durfte nur einen Selektor eingrenzen.)
2. **Shortcode-Präfix in der `<h1>`** (`TripHeader.svelte:131`, Mono/Akzent): über `name`-Prop nicht abbildbar ⇒ eigener Snippet-Slot (z. B. `namePrefix`) oder Entfall?
3. **Verhalten im Edit-Modus:** Trip zeigt die `<h1>` heute weiter **über** dem Eingabefeld; der Baustein ersetzt sie. Akzeptiert (Parität) — Specs 714/724 prüfen `trip-detail-h1` nur vor dem Öffnen bzw. nach Erfolg?
4. **Eyebrow `REGION · DATUM`:** mit inline Region-Zeile doppelt. Eyebrow nur noch Datum? (`TripHeader.issue699.test.ts` prüft die Region in der Eyebrow per Quelltext.)
5. **Aktivität als 8 Kacheln vs. Select:** Baustein kann nur Kacheln. Kachelreihe übernehmen (Parität, Höhe mobil) oder Baustein um eine Darstellungsvariante erweitern (dann über Prop, nie über `kind`)?
6. **Options-Liste/Labels:** keine geteilte Konstante; Labels weichen ab („Trekking" in `TripTabs.svelte:215` vs. „Alpen-Trekking" in `TripNewEditor.svelte:661,993`). Neue Konstante `ACTIVITY_TYPE_OPTIONS` in `types.ts` (Muster `ACTIVITY_PROFILE_OPTIONS`) und welche Labels?
7. **`TripHeader` als Hülle behalten?** Ja ⇒ `header.trip-header`, Status-Zeile, Meta-Zeile, Mobil-Kacheln bleiben (336 grün); `TripHeader` mountet den Baustein. Nein ⇒ alles in die Seite bzw. in Snippets.
8. **Platz für Status-Badge, Tage-Label, km/Hm:** `badges`-Snippet (neben dem Namen) und `meta`-Snippet (rendert **in** der Region-Zeile und verschwindet beim Region-Edit) — passt das für `trip-detail-status-supplement` und `trip-detail-meta`, oder bleiben sie außerhalb des Bausteins?
9. **Konflikt-Schlüssel:** Trip heute `'kopf'` (Name) und `'aktivitaet'`, Vergleich `kopf-name|kopf-region|kopf-profil`. Auf das Vergleich-Schema vereinheitlichen? (Wirkt auf die Dedup-Liste von „Nochmal speichern" und auf die #1433-Tests.)
10. **`imWiederholen`-Guard beim Trip:** nötig? Trip-Reiter bauen sich nur über `uebernommeneFassung` neu auf, `trip = updated` während des Retrys baut nichts neu auf — vermutlich ohne Guard korrekt, aber zu belegen.
11. **`regionMaxLength` für Trip:** Backend prüft keine Länge; Vergleich nutzt 60. Gleicher Wert?
12. **Chip-API am Baustein:** neuer Prop `saveController` (Baustein rendert `SaveIndicator`) — Baustein bliebe ohne `api`-Import, bekommt aber eine Store-Abhängigkeit. Oder Snippet `chip`? Der Vergleich müsste `hubSaveCtl` dann zusätzlich an den Kopf geben.

## Analysis

### Type
Feature (Scheibe S2 von #2284, Epic #2345 Etappe P2)

### Entscheidungen zu den 12 offenen Fragen
1. **`trip-detail-h1`:** Baustein bekommt optionalen Prop `titleTestid` (Trip: `'trip-detail-h1'`, Vergleich: leer). Prop, kein `kind`-Zweig. CI-Specs 724/714/336/616 bleiben unverändert — 724/714 lesen die `<h1>` nur vor dem Öffnen (724:52/83/111, 714:111) und nach Erfolg (724:91). `issue-302` (nicht in der Ratsche) prüft nur die testid (`:33-35`).
2. **Shortcode-Präfix:** neues optionales Snippet `namePrefix`, im Baustein innerhalb der `<h1>`. Entfall wäre Funktionsänderung ohne Not.
3. **Edit-Modus:** Parität zum Vergleich — die Eingabe ersetzt die `<h1>`. Keine Specänderung nötig (s. 1).
4. **Eyebrow:** nur noch Datumsbereich (`eyebrow`-Snippet); Region steht inline in der Region-Zeile. Kein Ratschen-Spec prüft die Region in der Eyebrow (gemessen: Grep `frontend/e2e`). `TripHeader.issue699.test.ts` (Quelltextprüfung) wird auf Verhalten umgestellt.
5. **Aktivität:** Kachelreihe des Bausteins, keine neue Darstellungsvariante (S1-Entscheidung 5). Mobil wird der Kopf höher ⇒ prüfbare AC zur Kartenhöhe 375×667 (s. Risiken).
6. **Options-Konstante:** `ACTIVITY_TYPE_OPTIONS` in `types.ts` (Muster `ACTIVITY_PROFILE_OPTIONS`), Labels aus `TripTabs.svelte:215-222` (Ist-Stand im Etappen-Reiter). `TripNewEditor`-Labels bleiben unberührt (kein S2-Thema).
7. **`TripHeader` bleibt Hülle:** `<header class="trip-header">`, Status-Zeile `trip-detail-status-supplement`, Meta `trip-detail-meta`, Mobil-Kacheln bleiben (Spec 336); die Hülle mountet den Baustein.
8. **Status/Meta außerhalb des Bausteins** — das `meta`-Snippet rendert in der Region-Zeile und verschwindet beim Region-Edit (`SubscriptionHeader.svelte:107-118`). `badges`/`meta` bleiben beim Trip leer.
9. **Konflikt-Schlüssel:** angleichen an `kopf-name`/`kopf-region`/`kopf-profil`. Gemessen: `'kopf'`/`'aktivitaet'` kommen in `frontend/src` nur an den zwei Save-Aufrufen vor (`TripHeader.svelte:51`, `TripTabs.svelte:191`), kein Test und keine Dedup-Logik liest sie ⇒ Umbenennung ohne Nebenwirkung, Gewinn: ein Schema für beide Hubs.
10. **`imWiederholen`-Guard: nein.** Der Vergleich braucht ihn, weil eine neue `preset`-Referenz `CompareTabs` neu aufbaut (Kommentar `compare/[id]/+page.svelte:195-197`, F101). Beim Trip baut `trip = updated` nichts neu auf (Neuaufbau nur über `{#key uebernommeneFassung}`, Kopf liegt außerhalb), und der heutige Trip-Namensweg (`TripHeader.svelte:47-50`) läuft seit #1433 ebenfalls ohne Guard. Status quo bleibt; ein Test belegt „Retry läuft, `trip` wird ersetzt, Reiter nicht neu aufgebaut".
11. **`regionMaxLength`:** 60 wie beim Vergleich.
12. **Chip-API:** neuer Prop `saveController?` am Baustein, der Baustein rendert `<SaveIndicator>` selbst (kein `api`-Import). Vergleich übergibt `hubSaveCtl`, Trip `tripSaveCtl`. Entfernen aus `CompareTabs.svelte:750-754` (+Import `:25`) und `TripHeader.svelte:198-202` im **selben** Schritt (feat-880 `toHaveCount(1)`).

**Region leeren:** `save()` im Baustein (`:65-77`) weist leere Werte nicht ab ⇒ `{region: ""}` wird gesendet, Go setzt `""` (Pointer non-nil), `omitempty` lässt den Schlüssel fallen. Anzeige „—" über Normalisierung **am Trip-Mount** (`region={trip.region || undefined}`); der Baustein behält `??` ⇒ Vergleich-Verhalten unverändert (S1 AC-12).

**Mandantentrennung:** `UpdateTripHandler` (`internal/handler/trip.go:290,314-326`) lädt über `s.WithUser(...)` und antwortet bei fremder ID 404 ohne Schreiben (kein Upsert). Fehlender Test: Nutzer B sendet `{region}` gegen A's Trip-ID ⇒ 404, A's Datei byte-gleich (neu in `trip_region_test.go`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Props `titleTestid`, `saveController`, Snippet `namePrefix`; rendert `SaveIndicator` |
| `frontend/src/lib/types.ts` | MODIFY | `ACTIVITY_TYPE_OPTIONS` |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | Baustein-Mount, `onSaveField` (nur Eigenfeld, Schlüssel `kopf-*`), Namens-Markup + Chip raus; Eyebrow nur Datum |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Aktivitäts-Select + `handleActivityChange` raus; `activityType = $derived(trip?.activity)` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Chip-Mount + Import raus |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | `saveController={hubSaveCtl}` am Baustein |
| `frontend/src/lib/components/trip-detail/__tests__/tripMehrreiterPruefstand.ts` + 4 #1433-Tests | MODIFY | `kopfReiter`/`aktivitaetReiter` auf `onSaveField` umhängen, Aussagen erhalten |
| `TripHeader.issue699/spacing/mobile-metrics.test.ts` | MODIFY | Quelltextprüfungen an neue Struktur anpassen bzw. durch Verhaltensprüfung ersetzen |
| `frontend/src/lib/components/shared/__tests__/subscription_header_*.test.ts` | MODIFY | neue Props (testid, Chip genau einmal, `namePrefix`) |
| `frontend/e2e/pwa-offline-sperre-und-mandant.spec.ts` (`:216-222`, `:410-416`) | MODIFY | Ziel `trip-profil-option-*`, Aussage „offline gesperrt" bleibt |
| `frontend/e2e/feat-1461-s3b2b-compare-kanal-schwelle.spec.ts` (`:385-391`) | MODIFY | PUT-Auslöser `trip-profil-option-*` statt Dropdown |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` | CREATE | Region/Aktivität/Datenerhalt/Konflikt/Mobil/Chip genau einmal (Trip + Vergleich) |
| `internal/handler/trip_region_test.go` | MODIFY | Zwei-Nutzer-Fall `{region}` |
| `edit/issue_943_activity_edit.test.ts`, `e2e/issue-943-*` | unverändert | tot, prüft nur Existenz der E2E-Datei |

Chip-Locatoren in `frontend/e2e` (epic-138, issue-498, versand-tab-vergleich, compare-*, save-status-indicator-honesty, issue-1158) greifen alle seitenweit über `getByTestId('save-indicator')` — keiner ist an einen Eltern-Container gebunden ⇒ vom Umzug unberührt. `issue-1158-mobile-sheet-collapse.spec.ts:142-145` misst die Position (bleibt `fixed`).

### Scope Assessment
- Produktive Dateien: 6
- Estimated LoC: ca. 190-220 brutto (Baustein +25, types +12, TripHeader ±100, TripTabs −35, CompareTabs −6, Vergleich-Seite +2) ⇒ unter 250, keine Teilung
- Risk Level: MEDIUM (zentrale Kopf-Komponente beider Hubs, Speicherweg mit Konfliktschutz)

### Technical Approach
1. Baustein erweitern (`titleTestid`, `saveController`, `namePrefix`) + `ACTIVITY_TYPE_OPTIONS`.
2. Chip-Umzug Vergleich (CompareTabs raus, Baustein-Prop rein) und Trip (TripHeader-Chip raus) im selben Commit.
3. `TripHeader` mountet den Baustein mit `onSaveField(field, value, schliessen)` nach S1-Muster: Rumpf nur `{name}`/`{region}`/`{activity}`, `baueTripSpeicherung` + `speichereOderMeldeKonflikt(…, saveController)`, nach Erfolg `onTripUpdate(u)` + `schliessen()`.
4. `TripTabs`: Select raus, `activityType` per `$derived` (sonst veraltete Ankunftszeiten — Risiko 1).
5. #1433-Harness umhängen; neue Tests (Go zwei Nutzer, E2E).

### Risiken
1. **Reaktivität `activityType`** (`TripTabs.svelte:62` Mount-`$state`) ⇒ `$derived`; Test „Kopf wählt skitour ⇒ Ankunftszeiten ändern sich ohne Remount".
2. **Doppel-Mount Chip** ⇒ ein Commit; feat-880 + neuer Test `toHaveCount(1)` je Hub.
3. **`position: fixed`:** kein Vorfahr mit `transform`/`filter` gefunden (`<main style="position:relative;overflow:hidden">` beschneidet `fixed` nicht); per `getComputedStyle` belegen.
4. **Mobil-Höhe:** 8 Kacheln umbrechen auf 375 px mehrzeilig, Kopf wächst sichtbar, `EditStagesPanelNew` (`:59-85`) verkleinert die Karte. AC mit prüfbarer Schwelle (Kartenhöhe bei 375×667) und die Höhenänderung im AC-Text benennen, damit der PO sie bei der Freigabe sieht.
5. **Wächter 336/724/714/616:** `header.trip-header`, Status-/Meta-Zeile, `trip-detail-h1` bleiben erhalten.
6. **Offline-Sperre** greift automatisch (`<main>`).
7. **Parallelarbeit:** S3 fasst `TripTabs.svelte` ebenfalls an — nicht parallel.

### AC-Entwurf (für /30-write-spec)
Name inline (trip-detail-h1 nach Reload) · Region inline setzen/leeren („—", Home-Hero/Liste blenden aus) · Aktivität als Kachel im Kopf, kein Dropdown mehr im Etappen-Reiter · Etappen-Ankunftszeiten reagieren ohne Reload · Datenerhalt (PUT nur Eigenfeld, übrige Felder per GET unverändert) · Zwei-Nutzer-Test Go (404, Datei byte-gleich) · Fehlerfall 500 je Feld · Konflikt 412 „Nochmal speichern" je Feld · genau ein Chip, fixed, beide Hubs · Mobil 375 px mit Kartenhöhen-Schwelle · offline gesperrt · Regression: Ratschen-Specs 724/714/616/336 + compare-hub-* unverändert grün.

### Open Questions
- Keine an den PO. Alle technischen Entscheidungen oben getroffen.
