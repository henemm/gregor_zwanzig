# Context: feature-2277-s3-reiter-rueckbau

## Request Summary
Restscheiben von #2277: (AC-3) Reiterleisten von `/trips/new` und `/compare/new` ab dem Inhalts-Teil identisch in Beschriftung, Reihenfolge und Lock-Hinweisen; (AC-5) Alt-Bausteine `AlertRulesEditor`, `EditReportConfigSection`, `compareNewLogic` ohne produktiven Importeur. Bereits live: S1 (AlarmeTab), S2a (Wertebereiche), S2b (Mobile-Rahmen), S2c (`/compare/new?from=`).

Pfade relativ zu `frontend/`.

## Ist-Stand Reiter

| # | Trip (`TripNewEditor.svelte:71-79`) | Lock-Hinweis | Compare (`CompareNewEditor.svelte:96-103`) | Lock-Hinweis |
|---|---|---|---|---|
| 1 | Route | – | Vergleich | – |
| 2 | Etappen & GPX | erst Trip-Name + Startdatum | Orte | erst Vergleich benennen |
| 3 | Wegpunkte prüfen (optional) | erst alle GPX hochladen | – | – |
| 4 | Wetter-Metriken | erst alle GPX hochladen | Wetter-Metriken | erst mind. 2 Orte auswählen |
| 5 | Wertebereiche | erst Wetter-Metriken öffnen | Wertebereiche (id `idealwerte`) | erst Wetter-Metriken öffnen |
| 6 | **Briefing-Zeitplan** (id `zeitplan`) | erst Wertebereiche öffnen | **Alarme** | erst Wertebereiche öffnen |
| 7 | **Alerts** (id `alerts`) | erst Zeitplan öffnen | **Versand** | erst Alarme öffnen |

Hubs (Referenz): Trip-Hub `trip-detail/TripTabs.svelte:87-95` und Compare-Hub `compare/compareTabsResolve.ts:8-22` heißen beide „… Wertebereiche · Alarme · Versand · Vorschau“. Die Anlege-Seite des Trips ist also die einzige Abweichung.

Differenz Trip ↔ Compare: Reihenfolge der letzten beiden (Zeitplan→Alerts vs. Alarme→Versand) und Beschriftung („Briefing-Zeitplan“/„Alerts“ vs. „Versand“/„Alarme“).

## Lock-Engines
- `trip-new/tripNewLogic.ts` (244 Z., davon 88-244 Payload-Builder): Kette metriken → wertebereiche → zeitplan → alerts (`:27-43`); `canSave` verlangt `zeitplan` done; Fortschritt hartkodiert `['route','etappen','metriken','zeitplan']` „/4“ (`TripNewEditor.svelte:516,521,529,533`). Visited-Flags `wtVisited/wbVisited/ztVisited` (`:118-120`, gesetzt `:248-250`), Aufrufe `:163-167`.
- `compare-new/compareNewLogic.ts` (69 Z.): Progress-Objekt, Kette … → alarme → versand, `canActivate(versand)`, zählt alle 6 Reiter. Einziger Importeur `CompareNewEditor.svelte:31-38`; Tests `compareNewLogic.test.ts`, `compare_layout_tab_dissolution.test.ts:43`, `compareNewVorlage.test.ts:21`.
- Generalisierung möglich: sequentielle Kette `[id, Vorbedingung]` unter `shared/` (Pendant-Sperre greift für `shared/**` nicht). Kind-eigen: Eingangsbedingungen (Name+Datum+GPX vs. Name+2 Orte), optionaler Wegpunkte-Reiter beim Trip.

## Rückbau-Kandidaten (AC-5)

| Baustein | Zeilen | Produktive Importeure | Status |
|---|---|---|---|
| `alert-rules-editor/AlertRulesEditor.svelte` | 100 | `organisms/index.ts:15` (Barrel), `edit/TripEditView.svelte:10,205` | TripEditView ist **tot** (kein Importeur; `/trips/[id]/edit` redirectet) → sofort löschbar |
| `alert-rules-editor/AlertRuleRow.svelte` | 327 | nur AlertRulesEditor | mit löschbar; `alertChannels.ts` ebenso |
| `alert-rules-editor/alertRuleDefaults.ts` | – | `alerts-tab/alertMetricTable.ts:16`, `alerts-tab/AlertMetricRow.svelte:7` (`DELTA_ONLY_METRICS`) | bleibt oder zieht vorher um |
| `ModeCard` | – | – | **bereits entfernt** (13af5db9, #1895) |
| `edit/EditReportConfigSection.svelte` | 574 | `TripNewEditor.svelte:17` (`:873`, `:1156`, nur Mail-Inhalt-Karte), `shared/WeatherMetricsTab.svelte:87,1982` (**Trip-Hub Mail-Inhalt-Karte im Reiter Wetter-Metriken**), `TripEditView` (tot), `briefings-tab/BriefingsTab.svelte:4,40` (BriefingsTab importiert in `TripTabs.svelte:14`, nie gerendert) | **nicht** ersatzlos löschbar: Mail-Inhalt-Karte (`data-testid="report-mail-content"`, ERCS `:458`) hat kein geteiltes Pendant; erst nach `shared/` extrahieren |
| `edit/reportConfigWrite.ts` | – | nur ERCS | verwaist mit ERCS |
| `compare-new/compareNewLogic.ts` | 69 | CompareNewEditor | nur ablösbar durch geteilte Lock-Engine |

Unberührt: `reportSlotAktiv.ts`, `shared/reportConfigDirty.ts` (mehrfach geteilt).

## Tests mit Bezug
- Pinnen Trip-Reiter: `trip-new/__tests__/trip_new_wertebereiche_reiter.test.ts:70-106`, `tripNewLogic.test.ts:69-94,324-332`, `trip_new_alarme_reiter.test.ts` (`activeTab:'alerts'`), `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein.test.ts:41`, `trip_new_versandkanaele_unabhaengig_von_metriken.test.ts:44` (`activeTab:'zeitplan'`).
- Testen Alt-Bausteine selbst (fallen mit): `alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts`, `alertChannels.test.ts`, `compareNewLogic.test.ts`, `edit/__tests__/sms_unbestaetigt_trip_editor.test.ts`, `report_config_uses_shared_schedule.test.ts`, `edit/issue_619_report_config_write.test.ts`, `edit/issue_693_email_config_cleanup.test.ts`.
- Anzupassen: `shared/__tests__/legacy_wizard_removed.test.ts:100` (erwartet Barrel-Export AlertRulesEditor).
- TripEditView-Tests: `edit/issue_503_etappen_waypoints.test.ts`, `issue_523_suggested_flag_cleanup.test.ts`, `routes/trips/bug_596.test.ts`, `deadTripOverviewComponentsRemoved.test.ts`, `tests/tdd/test_bug720_tripeditview_spread_fix.py`.
- Python-Doku-/Hygiene-Tests: `tests/tdd/test_issue_934_wizard_schedule.py`, `test_issue_753_746_hygiene.py`, `test_bundle_d_785_yesterday_toggle.py`, `test_issue_316_docs_cleanup.py`.
- Playwright: `e2e/issue-661-trip-new-mobile.spec.ts:186` ('Briefing-Zeitplan'), `gewitter-absolutregel-gesperrt.spec.ts:77-78,187` (/Zeitplan/, /Alerts/), `issue-776-metrics-toggle.spec.ts:30-60`, `versandzeit-stundenwahl.spec.ts:141`; veraltete AlertRulesEditor-Specs gegen `/trips/${id}/edit` (Redirect): `alert-rules-editor.spec.ts`, `issue-284-alert-rules-restyle.spec.ts`, `issue-687-alert-editor-soll-ist.spec.ts`, `issue-494-trip-edit-design.spec.ts`, `e2e/helpers.ts:343-354` (`fillStep4`).

## Existing Specs
`docs/specs/modules/`: `fix_2277_s1_alarme_tab_route.md`, `fix_2277_s2a_wertebereiche_trip_anlegen.md`, `fix_2277_s2b_mobile_rahmen_angleichung.md`, `feat_2277_s2c_compare_from_vorlage.md`, `feat_1301_f2a_compare_new_trip_pattern.md`, `feat_1301_f2b_editor_loeschung.md`, `fix_1738_trips_new_versand_tab.md`, `fix_1895_alarm_modus_rueckbau.md`, `fix_1895_s2_alarmkarte_rueckbau.md`, `feat_1481b_pendant_gate.md`.

## Risks & Considerations
- **Reihenfolge-Tausch beim Trip** (Alarme vor Versand) verändert `canSave` (hängt heute an `zeitplan`) und den Fortschritt „/4“ — Speichern darf nicht früher/später freigegeben werden als fachlich gewollt.
- Mail-Inhalt-Karte lebt im Trip-Hub im Reiter Wetter-Metriken; beim Extrahieren darf der Hub-Speicherweg (Read-Modify-Write) nicht brechen.
- Rückbau berührt viele Tests; gelöschte Tests dürfen keine noch gültige Zusicherung mitnehmen (Mutations-Gegenprobe).
- Umfang: sinnvoller Schnitt in Scheiben — (a) Reiter-Angleichung Trip, (b) toter Code (TripEditView, AlertRulesEditor/Row, BriefingsTab-Import, veraltete E2E), (c) Mail-Inhalt-Karte nach `shared/` + ERCS löschen, (d) geteilte Lock-Engine statt `compareNewLogic`.
- Pendant-Sperre: neue Dateien in `trip-new/`/`compare-new/` brauchen `gz-eigenstaendig`; `shared/` ist frei.

## Analysis

### Type
Feature (Angleichung + Rückbau), Teilscheibe S3 von #2277.

### Scheibenschnitt (Entscheidung)
| Scheibe | Inhalt | Ticket-AC | Risiko |
|---|---|---|---|
| **S3 (dieser Workflow)** | Trip-Reiter-Angleichung + Löschen des toten `AlertRulesEditor`-/`TripEditView`-Strangs | AC-3 vollständig, AC-5 **nur teilweise** (AlertRulesEditor) | niedrig–mittel |
| S4 (Folge-Workflow) | geteilte Lock-Engine unter `shared/`, `compareNewLogic.ts` löschen | AC-5 Teil 2 | mittel |
| S5 (Folge-Workflow) | Mail-Inhalt-Karte nach `shared/`, `EditReportConfigSection` + `reportConfigWrite.ts` + `BriefingsTab` löschen | AC-5 Teil 3 | hoch (Hub-Speicherweg, Read-Modify-Write, Mount-Kanonisierung `WeatherMetricsTab.svelte:106-108,1047-1056`) |

Begründung: S4 setzt die angeglichene Trip-Kette voraus (sonst Doppelumbau). S5 ist der einzige Eingriff in den Hub-Speicherweg und braucht eigene Staging-E2E auf Hub und `/trips/new`. **Issue #2277 bleibt nach S3 offen.**

LoC-Zählung (`edit_gate.py:425-465`): nur **Zusätze** zählen, Löschungen nicht; Produktiv-Limit 250, Tests separat 500. Rückbau ist damit LoC-frei.

### AC-3-Lesart (Tech-Lead-Entscheidung, Prüfung bei Spec-Freigabe)
Wörtlich „ab dem zweiten Reiter identisch" ist nicht erfüllbar (Reiter 2 ist kind-eigen: Etappen & GPX bzw. Orte; Trip hat zusätzlich den optionalen Wegpunkte-Reiter). Umsetzung: **Wetter-Metriken · Wertebereiche · Alarme · Versand** sind auf beiden Seiten identisch in Beschriftung, Reihenfolge und Lock-Hinweis; einzig der Lock-Hinweis von Wetter-Metriken bleibt kind-eigen, weil die Eingangsbedingung fachlich verschieden ist („erst alle GPX hochladen" vs. „erst mind. 2 Orte auswählen").

### Ziel-Reiterleiste Trip
Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken · Wertebereiche · **Alarme** („erst Wertebereiche öffnen") · **Versand** („erst Alarme öffnen").
- Tab-IDs umbenennen `zeitplan`→`versand`, `alerts`→`alarme` (= `CompareNewEditor.svelte:96-103`; Hub-IDs sind historisch anders: `TripTabs.svelte:88-96` nutzt `alerts`=Wertebereiche, `briefings`=Versand — nicht anfassen). IDs sind rein lokal (kein `?tab=`, kein Storage auf `/trips/new`).
- Lock-Kette `tripNewLogic.ts:27-61`: neues Visited-Flag für Alarme; Alarme frei nach Wertebereiche-Besuch, Versand frei nach Alarme-Besuch.
- `canSave` (`tripNewLogic.ts:73-75`) → `done.has('versand')` (wie `compareNewLogic.ts:66-68` `canActivate(versand)`).
- Fortschritt bleibt „/4" (Meilensteine route/etappen/metriken/versand), nur `'zeitplan'`→`'versand'` (`TripNewEditor.svelte:516-533`, `tripNewLogic.ts:79`). AC-3 betrifft die Reiterleiste, nicht den Balken.
- Fußzeilen-Hinweis „Zeitplan einrichten zum Speichern" (`TripNewEditor.svelte:935`) auf Versand umstellen.

### Nutzersichtbare Verhaltensänderung (eigene AC in der Spec!)
„Anlegen" setzt künftig den Besuch von **Alarme und Versand** voraus. Heute ist Alarme nach dem Zeitplan optional (man kann ohne Alarme-Besuch speichern). Entspricht dem Compare-Verhalten.

### Abgelöste freigegebene ACs (namentlich in der Spec als ersetzt führen)
- `fix_2277_s2a_wertebereiche_trip_anlegen.md` **AC-1** (Reiterfolge „…, Wertebereiche, Briefing-Zeitplan, Alerts"; Zeitplan nach Wertebereiche-Besuch) → wird durch neue Reiterfolge/Kette ersetzt.
- Kette `ztVisited → alerts` (`tripNewLogic.ts:59`) fällt.
- `fix_1738` und `fix_2277_s1` legen keine Reihenfolge fest; S1-AC-7 (AlertRulesEditor-Datei bleibt) wird durch die Löschung abgelöst.

### Affected Files
| File (rel. `frontend/`) | Change | Beschreibung |
|---|---|---|
| `src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Reiter-Defs/Labels/IDs, Visited-Setzen, Fortschritt, Fußzeilen-Hinweis |
| `src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Kette, canSave, Meilensteine |
| `src/lib/components/edit/TripEditView.svelte` | DELETE | tot (kein Importeur; `/trips/[id]/edit` redirectet 307) |
| `src/lib/components/organisms/alert-rules-editor/AlertRulesEditor.svelte`, `AlertRuleRow.svelte`, `alertChannels.ts` | DELETE | nur noch von TripEditView genutzt |
| `.../alert-rules-editor/alertRuleDefaults.ts` | MOVE | `DELTA_ONLY_METRICS` in **bestehende** Datei (`alerts-tab/alertMetricTable.ts`) oder `shared/` — keine neue Datei im kind-eigenen Ordner (Pendant-Sperre); Importe `alertMetricTable.ts:16`, `AlertMetricRow.svelte:7`, Test `alertRuleDefaults.test.ts` nachziehen |
| `src/lib/components/organisms/index.ts` | MODIFY | Barrel-Export `:15` entfernen |
| `trip-new/__tests__/*` (wertebereiche_reiter, tripNewLogic, alarme_reiter, zeitplan_tab…, versandkanaele…) | MODIFY | neue IDs/Kette |
| `shared/__tests__/legacy_wizard_removed.test.ts:100` | MODIFY | Barrel-Erwartung |
| Tests von gelöschten Bausteinen (`alertRegelNurAenderung`, `alertChannels`, `issue_503`, `issue_523`, `bug_596`, `deadTripOverviewComponentsRemoved`, `tests/tdd/test_bug720_tripeditview_spread_fix.py`) | DELETE | nicht in `ci_tdd_excludes.txt` ⇒ müssen in S3 mit fallen, sonst CI rot; vorher prüfen, ob eine noch gültige Zusicherung woanders abgedeckt ist |
| Python-Doku-/Hygiene-Tests (`test_issue_316_docs_cleanup.py`, `test_issue_934…`, `test_issue_753_746…`, `test_bundle_d_785…`) | CHECK/MODIFY | nur falls sie Pfade gelöschter Dateien erwarten |
| E2E: `issue-661-trip-new-mobile.spec.ts:186`, `gewitter-absolutregel-gesperrt.spec.ts:77-78,187`, `versandzeit-stundenwahl.spec.ts:141`, prüfen `issue-776-metrics-toggle.spec.ts:30-60` | MODIFY | Beschriftungen |
| E2E veraltet: `alert-rules-editor.spec.ts`, `issue-284…`, `issue-687…`, `issue-494…`, `fillStep4` (`e2e/helpers.ts:277-354`, unbenutzt) | DELETE | nicht in `ci_e2e_specs.txt` |
| neuer Test | CREATE | Paritätstest: Reiterleisten Trip ↔ Compare ab Wetter-Metriken identisch (Label, Reihenfolge, Lock-Hinweis) + Lock-Test Versand erst nach Alarme |

### Scope Assessment
- Produktiv: ~50–80 LoC Zusätze; Tests: ~120–200 Zusätze; Löschungen zahlreich (LoC-frei)
- Risk Level: **niedrig–mittel** — Kernlogik nur in Kette/canSave; Rückbau betrifft toten Code; Hauptrisiko: Test-Löschung nimmt gültige Zusicherung mit (Mutations-Gegenprobe Pflicht)

### Technical Approach
Erst Trip-Kette/Labels angleichen (Paritätstest grün), dann toten Strang löschen inkl. Tests/Barrel/E2E, `DELTA_ONLY_METRICS` umziehen. Staging: `/trips/new` Reiter durchklicken (Desktop + 390 px), Anlegen erst nach Versand möglich, Trip wird mit Alarmen/Wertebereichen persistiert.

### Dependencies
`tripNewLogic.ts` ← `TripNewEditor.svelte` (+ Tests). `alertRuleDefaults.ts` ← `alerts-tab/alertMetricTable.ts`, `AlertMetricRow.svelte`. Compare-Seite bleibt in S3 unverändert (Referenz).

### Open Questions
- keine PO-Fragen offen; AC-3-Lesart und Verhaltensänderung „Alarme vor Anlegen" werden bei der Spec-Freigabe sichtbar vorgelegt.


---

## #2277 S3 — Löschplan Alt-Tests (Übergabe RED → /50-implement)

Ergebnis der Abdeckungsprüfung (Phase 5, 2026-10-01): welche Zusicherung bewacht der jeweilige
Test, und lebt sie noch in einem produktiven Baustein? Grundregel der Spec: gelöschte Tests dürfen
keine noch gültige Zusicherung mitnehmen.

## Neue Signatur (in den RED-Tests festgelegt)

`unlockedTabs/doneTabs(name, startDate, etDone, wtVisited, wbVisited, alVisited, vsVisited)` —
Tab-IDs `alarme`/`versand` (statt `alerts`/`zeitplan`); `doneTabs` setzt `alarme` bei `alVisited`,
`versand` bei `vsVisited`; `canSave` ⇒ `done.has('versand')`; `progressCount` zählt
`route/etappen/metriken/versand`. Fußzeile: „Versand einrichten zum Speichern" (Muster Compare
„Versand einrichten zum Aktivieren"). Fortschritts-Arrays im Template (`TripNewEditor.svelte`
~Z.516/529) ebenfalls auf `versand` umstellen — SSR kann sie im Leerzustand nicht beobachten,
nur `tripNewLogic.progressCount` bewacht den Meilenstein.

## Ganz löschen (Zusicherung lebt nur im toten Baustein)

| Datei | Bewachte Zusicherung | Begründung |
|---|---|---|
| `frontend/src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts` | `newDefaultRule`/`expandRules` (Δ-Regel, `delta_window`-Durchreichung) | Kein lebender Code nutzt die Funktionen. |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | Kanäle pro Regel | Lebend gibt es nur Trip-Kanäle (`alert_channels`). |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Defaults + `DELTA_ONLY_METRICS` | `DELTA_ONLY_METRICS` jetzt bewacht in `alerts-tab/alertMetricTable.test.ts` (AC-6, neu). |
| `tests/tdd/test_bug720_tripeditview_spread_fix.py` | PUT von TripEditView ohne `{...trip}` | Nur toter Baustein; lebender Schutz in `alerts-tab/issue_850_alert_metrics_stale.test.ts`, `shared/__tests__/trip_speicherung_*`. |

## NUR TEILWEISE löschen (Rest bewacht lebenden Code!)

| Datei | Löschen | Behalten |
|---|---|---|
| `frontend/src/lib/components/edit/issue_503_etappen_waypoints.test.ts` | nur `describe('#503 Tab-Umbenennung')` (~Z.37–66, liest TripEditView) | Rest (EditStagesPanelNew, WaypointCard, WaypointPin) — lebend, sonst unbewacht |
| `frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts` | nur Test ~Z.101–106 (`TripEditView … stripSuggested`) | Rest (trip.go, types.ts, waypointEditor, Waypoint*-Bausteine) |
| `frontend/src/routes/trips/bug_596.test.ts` | nur AC-1 (Breadcrumb in TripEditView) | AC-2 („Meine Touren" nirgends) — einziger Wächter |

## Nicht löschen

- `frontend/src/lib/components/trip-detail/__tests__/deadTripOverviewComponentsRemoved.test.ts` — läuft weiter grün; nur Kommentar ~Z.113 anpassen.

## Weitere Nachzieh-Stellen

- `tests/tdd/test_issue_316_docs_cleanup.py` Z.43–44 (`NAMED_COMPONENTS` mit `AlertRulesEditor`/`AlertRuleRow`) + Z.79: wird `docs/reference/frontend_components.md` (Z.43, Abschnitt ~Z.680) bereinigt, Einträge aus der Liste nehmen (Kommentar wie bei ModeCard).
- Importe von `DELTA_ONLY_METRICS`: `alerts-tab/alertMetricTable.ts:16` (wird Definitionsort), `alerts-tab/AlertMetricRow.svelte:7`.
- Barrel `organisms/index.ts:15` und Kommentar Z.4.
- E2E löschen (laufen gegen Redirect, nicht in `ci_e2e_specs.txt`): `alert-rules-editor.spec.ts`, `issue-284-alert-rules-restyle.spec.ts`, `issue-687-alert-editor-soll-ist.spec.ts`, `issue-494-trip-edit-design.spec.ts`, `fillStep4` in `e2e/helpers.ts` (~Z.277–354; Z.346 referenziert `alert-rules-editor`).
- Reine Kommentare (optional): `utils/alertMetricCatalogIds.ts:36`, `alertMetricCatalogIds.test.ts:84`, `rightColumn.test.ts:9`, `EditStagesPanelNew.svelte:7`.
- Der AC-7-Import-Scan in `legacy_wizard_removed.test.ts` wird erst grün, wenn auch die Alt-Tests oben gelöscht/gekürzt sind.
