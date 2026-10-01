---
entity_id: feat_2277_s3_reiter_angleichung_rueckbau
type: feature
created: 2026-10-01
updated: 2026-10-01
status: draft
version: "1.0"
tags: [trip-new, compare-new, reiter, lock-kette, rueckbau, alert-rules-editor, parity]
---

# Reiterleisten-Angleichung Trip ↔ Ortsvergleich und Rückbau des toten Alarm-Strangs (Issue #2277 Scheibe S3)

## Approval

- [ ] Approved

## Purpose

Scheibe **S3** von #2277 (Anlege-Strecke-Konvergenz, Epic #2345) macht zwei Dinge.

1. **Reiter-Angleichung (Ticket-AC-3):** Die Anlege-Seite `/trips/new` bekommt dieselben letzten
   vier Reiter wie `/compare/new`: **Wetter-Metriken · Wertebereiche · Alarme · Versand**, in dieser
   Reihenfolge, mit denselben Beschriftungen und denselben Lock-Hinweisen. Heute heißen die letzten
   beiden Reiter beim Trip „Briefing-Zeitplan" und „Alerts" und stehen in anderer Reihenfolge. Die
   Anlege-Seite des Trips ist die einzige Abweichung; beide Hubs (Trip und Ortsvergleich) heißen
   bereits „… Wertebereiche · Alarme · Versand · Vorschau".
2. **Rückbau (Ticket-AC-5, Teil 1):** Der tote Strang um `AlertRulesEditor` (`TripEditView`,
   `AlertRulesEditor`, `AlertRuleRow`, `alertChannels`) wird gelöscht. Der Strang hat keinen
   produktiven Einstieg mehr — `/trips/[id]/edit` leitet nur noch um.

**Nutzersichtbare Verhaltensänderung:** „Anlegen" beim Trip setzt künftig den Besuch der Reiter
**Alarme und Versand** voraus (wie beim Ortsvergleich). Bisher genügte der Besuch des Zeitplans; der
Alerts-Reiter war freiwillig.

## Source

- **Frontend:**
  `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (MODIFY),
  `frontend/src/lib/components/trip-new/tripNewLogic.ts` (MODIFY),
  `frontend/src/lib/components/organisms/index.ts` (MODIFY),
  `frontend/src/lib/components/organisms/alerts-tab/alertMetricTable.ts` (MODIFY, nimmt `DELTA_ONLY_METRICS` auf),
  `frontend/src/lib/components/organisms/alerts-tab/AlertMetricRow.svelte` (MODIFY, Import),
  `frontend/src/lib/components/edit/TripEditView.svelte` (DELETE),
  `frontend/src/lib/components/organisms/alert-rules-editor/` (DELETE: `AlertRulesEditor.svelte`,
  `AlertRuleRow.svelte`, `alertChannels.ts`, `alertRuleDefaults.ts` nach Umzug)
- **Identifier:** Tab-IDs `versand` und `alarme` in `TripNewEditor.svelte`; Kette und `canSave` in
  `tripNewLogic.ts`; `DELTA_ONLY_METRICS`.

> **Schicht-Hinweis:** ausschließlich **Frontend**. Kein Go-API-, kein Python-Core-Code, kein
> Schema-Eingriff. Der Trip-Anlege-Payload (Wertebereiche, Alarme, Versand) bleibt unverändert;
> der Speicherweg (Read-Modify-Write) wird nicht berührt.

## Entscheidungen

1. **AC-3-Lesart (Tech-Lead-Entscheidung, bei Freigabe sichtbar):** Wörtlich „ab dem zweiten Reiter
   identisch" ist nicht erfüllbar — Reiter 2 ist kind-eigen („Etappen & GPX" beim Trip, „Orte" beim
   Ortsvergleich), und der Trip hat zusätzlich den optionalen Reiter „Wegpunkte prüfen". Umgesetzt wird:
   **Wetter-Metriken · Wertebereiche · Alarme · Versand** sind auf beiden Seiten in Beschriftung,
   Reihenfolge und Lock-Hinweis identisch. **Einzige Ausnahme, begründet:** Der Lock-Hinweis von
   „Wetter-Metriken" bleibt kind-eigen, weil die Eingangsbedingung fachlich verschieden ist
   („erst alle GPX hochladen" beim Trip, „erst mind. 2 Orte auswählen" beim Ortsvergleich).
2. **Ziel-Reiterleiste Trip:** Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken ·
   Wertebereiche · Alarme (Lock-Hinweis „erst Wertebereiche öffnen") · Versand (Lock-Hinweis
   „erst Alarme öffnen").
3. **Tab-IDs auf `/trips/new`:** `zeitplan` wird `versand`, `alerts` wird `alarme` (gleich wie in
   `CompareNewEditor.svelte`). Die IDs sind rein lokal (kein `?tab=`, kein Storage). **Die Hub-IDs in
   `trip-detail/TripTabs.svelte` (`alerts` = Wertebereiche, `briefings` = Versand) werden NICHT angefasst.**
4. **Neue Verhaltensänderung bewusst:** „Anlegen" aktiv erst nach Besuch von **Versand**; der Versand
   ist erst nach dem Besuch von **Alarme** erreichbar, also setzt „Anlegen" beide Besuche voraus.
   Entspricht `compareNewLogic.canActivate('versand')` beim Ortsvergleich.
5. **Fortschrittsanzeige bleibt „/4"** mit den Meilensteinen Route · Etappen · Metriken · **Versand**
   (statt Zeitplan). AC-3 betrifft die Reiterleiste, nicht den Balken.
6. **Fußzeilen-Hinweis** „Zeitplan einrichten zum Speichern" wird auf den Versand umgestellt.
7. **`DELTA_ONLY_METRICS`** wandert in eine **bestehende** Datei (`alerts-tab/alertMetricTable.ts`),
   nicht in eine neue Datei im kind-eigenen Ordner (Pendant-Sperre). Verhalten des Alarm-Reiters
   bleibt unverändert.
8. **Compare-Seite bleibt unverändert** und dient als Referenz des Paritätstests.

## Nicht im Umfang

- **S4:** geteilte Lock-Engine unter `shared/` und Löschung von `compare-new/compareNewLogic.ts`
  (Ticket-AC-5, Teil 2). In S3 bleibt `compareNewLogic.ts` unverändert.
- **S5:** Mail-Inhalt-Karte nach `shared/`, Löschung von `edit/EditReportConfigSection.svelte`,
  `edit/reportConfigWrite.ts` und `briefings-tab/BriefingsTab.svelte` (Ticket-AC-5, Teil 3). Die
  Mail-Inhalt-Karte lebt im Trip-Hub im Reiter Wetter-Metriken und in `TripNewEditor`; sie bleibt in S3
  unangetastet.
- Hub-Reiter (`TripTabs.svelte`, `compareTabsResolve.ts`) und deren IDs.
- Go-API, Python-Core, Datenmodell, Mail-Renderer.
- **Issue #2277 bleibt nach S3 offen** — erst nach S4 und S5 ist AC-5 vollständig erfüllt.

## Abgelöste freigegebene ACs

Folgende bereits freigegebene Zusicherungen werden durch diese Spec **namentlich ersetzt**:

| Spec | AC | Ersetzt durch |
|------|----|---------------|
| `fix_2277_s2a_wertebereiche_trip_anlegen.md` | **AC-1** (Reiterfolge „…, Wertebereiche, Briefing-Zeitplan, Alerts"; Zeitplan frei nach Besuch Wertebereiche) | **AC-1, AC-3 und AC-4 dieser Spec** (neue Reiterfolge und Kette Wertebereiche → Alarme → Versand). Die Kette `ztVisited → alerts` fällt. |
| `fix_2277_s1_alarme_tab_route.md` | **AC-7** (Datei `AlertRulesEditor.svelte` bleibt bestehen) | **AC-7 dieser Spec** (Datei wird gelöscht). |

Alle übrigen ACs von `fix_2277_s2a_wertebereiche_trip_anlegen.md` (z. B. Wertebereiche beim Anlegen
sichtbar und persistiert) und von `fix_2277_s1_alarme_tab_route.md` bleiben gültig. `fix_1738` und
S1 legen keine Reihenfolge der Reiter fest und sind nicht betroffen.

## Affected Files

Pfade relativ zu `frontend/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Reiter-Definitionen (Labels, IDs `versand`/`alarme`, Lock-Hinweise, Reihenfolge), Visited-Setzen für Alarme, Fortschritt „/4" mit Meilenstein `versand`, Fußzeilen-Hinweis. |
| `src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Lock-Kette `… wertebereiche → alarme → versand`, neues Visited-Flag für Alarme, `canSave` ⇒ `done.has('versand')`, Meilensteine. |
| `src/lib/components/edit/TripEditView.svelte` | DELETE | Tot: kein Importeur, `/trips/[id]/edit` leitet um (307). |
| `src/lib/components/organisms/alert-rules-editor/AlertRulesEditor.svelte`, `AlertRuleRow.svelte`, `alertChannels.ts` | DELETE | Nur noch von `TripEditView` genutzt. |
| `src/lib/components/organisms/alert-rules-editor/alertRuleDefaults.ts` | MOVE/DELETE | `DELTA_ONLY_METRICS` zieht in `alerts-tab/alertMetricTable.ts`; Importe in `alertMetricTable.ts` und `AlertMetricRow.svelte` und der Test `alertRuleDefaults.test.ts` werden nachgezogen. |
| `src/lib/components/organisms/index.ts` | MODIFY | Barrel-Export von `AlertRulesEditor` (Zeile 15) entfernen. |
| `src/lib/components/trip-new/__tests__/` (`trip_new_wertebereiche_reiter`, `tripNewLogic`, `trip_new_alarme_reiter`, `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`, `trip_new_versandkanaele_unabhaengig_von_metriken`) | MODIFY | Neue IDs und neue Kette. |
| `src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts` (Zeile ~100) | MODIFY | Erwartet bisher den Barrel-Export `AlertRulesEditor`; neu: Export und Datei existieren nicht mehr. |
| Tests der gelöschten Bausteine: `alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts`, `alertChannels.test.ts`, `edit/__tests__/issue_503_etappen_waypoints.test.ts`, `issue_523_suggested_flag_cleanup.test.ts`, `routes/trips/bug_596.test.ts`, `deadTripOverviewComponentsRemoved.test.ts`, `tests/tdd/test_bug720_tripeditview_spread_fix.py` | DELETE | Nicht in `ci_tdd_excludes.txt`, müssten sonst CI rot machen. Vorher je Datei prüfen, ob eine noch gültige Zusicherung anderswo abgedeckt ist (siehe Tests). |
| Python-Doku-/Hygiene-Tests `tests/tdd/test_issue_316_docs_cleanup.py`, `test_issue_934_wizard_schedule.py`, `test_issue_753_746_hygiene.py`, `test_bundle_d_785_yesterday_toggle.py` | CHECK/MODIFY | Nur anpassen, falls sie Pfade gelöschter Dateien erwarten. |
| `e2e/issue-661-trip-new-mobile.spec.ts` (Zeile ~186), `e2e/gewitter-absolutregel-gesperrt.spec.ts` (Zeilen ~77-78, ~187), `e2e/versandzeit-stundenwahl.spec.ts` (Zeile ~141) | MODIFY | Beschriftungen „Briefing-Zeitplan"/„Zeitplan"/„Alerts" ⇒ „Versand"/„Alarme". `e2e/issue-776-metrics-toggle.spec.ts` (Zeilen ~30-60) prüfen. |
| `e2e/alert-rules-editor.spec.ts`, `e2e/issue-284-alert-rules-restyle.spec.ts`, `e2e/issue-687-alert-editor-soll-ist.spec.ts`, `e2e/issue-494-trip-edit-design.spec.ts`, `fillStep4` in `e2e/helpers.ts` (Zeilen ~277-354, unbenutzt) | DELETE | Veraltet (laufen gegen den Redirect `/trips/${id}/edit`), nicht in `ci_e2e_specs.txt`. |
| `src/lib/components/trip-new/__tests__/` bzw. `shared/__tests__/` neuer Paritäts- und Lock-Test | CREATE | Siehe „Tests". |

## Estimated Scope

- **LoC (produktiv):** ca. +50 bis +80 Zusätze (Löschungen zählen nicht); Tests ca. +120 bis +200 Zusätze.
  Unter dem 250-LoC-Limit.
- **Files:** 5 produktiv geändert, ca. 9 produktiv gelöscht, Tests zahlreich angepasst oder gelöscht.
- **Effort:** medium.
- **Risk Level: NIEDRIG–MITTEL** — Kernlogik nur in Kette und `canSave`; Rückbau betrifft toten Code.
  Hauptrisiko: eine Test-Löschung nimmt eine noch gültige Zusicherung mit.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tripNewLogic.ts` | module | Lock-Kette, `canSave`, Meilensteine; Aufrufer `TripNewEditor.svelte`. |
| `CompareNewEditor.svelte` (Zeilen ~96-103) | component | Referenz der Reiter-Definition (unverändert). |
| `compareNewLogic.ts` | module | Referenz-Lock-Kette (`canActivate('versand')`); unverändert, fällt erst in S4. |
| `alerts-tab/alertMetricTable.ts`, `AlertMetricRow.svelte` | modules | Bisherige Importeure von `DELTA_ONLY_METRICS` aus `alertRuleDefaults.ts`. |
| `trip-detail/TripTabs.svelte` | component | Hub; Reiter-IDs bleiben unberührt. |
| `routes/trips/[id]/edit` | route | Redirect bleibt bestehen (keine tote Route). |
| `fix_2277_s2a_wertebereiche_trip_anlegen.md`, `fix_2277_s1_alarme_tab_route.md` | specs | Teilweise abgelöst (siehe oben). |
| `feat_1481b_pendant_gate.md` | spec | Pendant-Sperre: keine neue Datei in `trip-new/`/`compare-new/` ohne `gz-eigenstaendig`; neuer Test liegt in `shared/__tests__/`. |

## Implementation Details

1. **Reihenfolge der Arbeit:** zuerst Trip-Kette und Labels angleichen (Paritätstest grün), danach den
   toten Strang samt Tests, Barrel und E2E löschen und `DELTA_ONLY_METRICS` umziehen.
2. `tripNewLogic.ts`: Kette `route → etappen → (wegpunkte) → metriken → wertebereiche → alarme → versand`;
   neues Visited-Flag für Alarme (analog zu den bestehenden `wtVisited`/`wbVisited`); Alarme frei nach
   Besuch von Wertebereiche, Versand frei nach Besuch von Alarme; `canSave` ⇒ `done.has('versand')`;
   Fortschritt-Meilensteine `['route','etappen','metriken','versand']`.
3. `TripNewEditor.svelte`: Reiter-Definitionen auf Beschriftung „Alarme"/„Versand" und IDs
   `alarme`/`versand` umstellen; Besuch des Alarme-Reiters im selben Muster wie die anderen Reiter
   erfassen; Fortschrittsaufrufe (`'zeitplan'` ⇒ `'versand'`); Fußzeilen-Hinweis auf Versand.
4. Der Inhalt der Reiter (Versand-Baustein, `AlarmeTab`) bleibt unverändert — nur Beschriftung, ID,
   Reihenfolge und Freischaltung ändern sich.
5. Rückbau: Dateien löschen, Barrel-Export entfernen, `DELTA_ONLY_METRICS` verschieben, Importe
   nachziehen; anschließend `grep` auf die gelöschten Dateinamen in `src/`, `e2e/`, `tests/` darf keinen
   Importeur mehr finden.
6. Keine Änderung an `buildTripPayload`-Teilen von `tripNewLogic.ts` (Zeilen ~88-244).

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new`.
- **Output:** Die Reiterleiste lautet Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken ·
  Wertebereiche · Alarme · Versand. Alarme wird nach dem Besuch von Wertebereiche frei, Versand nach dem
  Besuch von Alarme. „Anlegen" wird erst nach dem Besuch von Versand aktiv. Danach legt Speichern den
  Trip samt Wertebereichen und Alarmen an.
- **Side effects:** Keine Backend-Änderung. Nutzer, die bisher ohne Alarme-Besuch speichern konnten,
  müssen den Reiter Alarme einmal öffnen (gewollte Angleichung an den Ortsvergleich).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet `/trips/new` / When er die Reiterleiste betrachtet / Then lauten
  die Reiter in dieser Reihenfolge Route · Etappen & GPX · Wegpunkte prüfen · Wetter-Metriken ·
  Wertebereiche · Alarme · Versand, und die Beschriftungen „Briefing-Zeitplan" und „Alerts" kommen
  nicht mehr vor.
  - Test: Kern — Paritäts-/Reiterlisten-Test auf der echten Reiter-Definition; Staging-E2E liest die
    Reiterleiste.
  - Mutations-Gegenprobe: eine Beschriftung oder die Reihenfolge von Alarme und Versand vertauschen
    ⇒ der Test wird rot.

- **AC-2:** Given ein Nutzer auf `/trips/new`, der die Reiter Alarme und Versand noch nicht freigeschaltet
  hat / When er deren Lock-Hinweise liest / Then lautet der Hinweis bei Alarme „erst Wertebereiche
  öffnen" und bei Versand „erst Alarme öffnen".
  - Test: Kern — Lock-Test auf Kette und Hinweistexte; Staging-E2E prüft die gesperrten Reiter.
  - Mutations-Gegenprobe: Versand an Wertebereiche statt an Alarme koppeln ⇒ rot.

- **AC-3:** Given die Reiterleisten von `/trips/new` und `/compare/new` / When man jeweils die Reiter ab
  Wetter-Metriken vergleicht / Then stimmen Wetter-Metriken, Wertebereiche, Alarme und Versand in
  Beschriftung, Reihenfolge und Lock-Hinweis überein; ausgenommen ist allein der Lock-Hinweis von
  Wetter-Metriken, der kind-eigen bleibt („erst alle GPX hochladen" beim Trip, „erst mind. 2 Orte
  auswählen" beim Ortsvergleich).
  - Test: Kern — neuer Paritätstest vergleicht die Reiter-Definitionen beider Editoren ab Wetter-Metriken
    (Label, Reihenfolge, Hinweis); die Wetter-Metriken-Ausnahme ist im Test namentlich begründet.
  - Mutations-Gegenprobe: Beschriftung „Alarme" nur im Trip auf „Alerts" ändern ⇒ Paritätstest rot;
    Lock-Hinweis „Versand" nur im Compare ändern ⇒ rot.

- **AC-4:** Given ein Nutzer auf `/trips/new`, der alle Pflichtangaben gemacht hat und Wertebereiche
  besucht, aber den Reiter Alarme noch nicht geöffnet hat / When er den Anlegen-Button ansieht / Then ist
  „Anlegen" deaktiviert und der Versand-Reiter gesperrt; erst nach dem Besuch von Alarme und danach von
  Versand wird „Anlegen" aktiv. Der Fußzeilen-Hinweis fordert entsprechend den Versand statt des
  Zeitplans, und die Fortschrittsanzeige bleibt „/4" mit dem Meilenstein Versand.
  - Test: Kern — Lock-Test auf `tripNewLogic` (`canSave` nur mit `versand`, Versand nur nach
    Alarme); Staging-E2E klickt die Kette durch.
  - Mutations-Gegenprobe: `canSave` wieder an Wertebereiche oder Alarme koppeln ⇒ rot; Fortschritt auf
    „/5" ändern ⇒ rot.

- **AC-5:** Given ein Trip wird über `/trips/new` vollständig durchgeklickt (inklusive Wertebereiche,
  Alarme und Versand) und angelegt / When er danach im Hub geöffnet wird / Then sind die eingestellten
  Wertebereiche, Alarm-Einstellungen und Versand-Kanäle persistiert, und der Anlege-Payload unterscheidet
  sich nicht von dem vor dieser Scheibe.
  - Test: Kern — bestehende Payload-Tests von `tripNewLogic` bleiben grün und unverändert in ihrer
    Aussage; Staging-E2E legt einen Test-Trip an, öffnet den Hub und liest die Werte (Persistenz).
  - Mutations-Gegenprobe: im Payload-Aufbau die Alarm- oder Wertebereiche-Zuweisung auslassen ⇒ ein
    Test wird rot.

- **AC-6:** Given der Alarm-Reiter (`AlarmeTab`) im Anlege-Editor / When ein Nutzer eine Alarm-Regel
  einstellt, die nur bei Änderung auslöst (Delta-Metrik) / Then verhält sich der Reiter unverändert
  gegenüber vor dieser Scheibe, und `DELTA_ONLY_METRICS` ist in der bestehenden Datei
  `alerts-tab/alertMetricTable.ts` definiert, nicht in einer neuen Datei der kind-eigenen Ordner.
  - Test: Kern — bestehender `alertRuleDefaults`-Test zeigt auf den neuen Ort und bleibt inhaltlich
    gleich; Alarm-Tab-Tests bleiben grün.
  - Mutations-Gegenprobe: eine Metrik aus `DELTA_ONLY_METRICS` entfernen ⇒ der Test wird rot.

- **AC-7:** Given der Quellbaum nach dem Rückbau / When man nach den Dateien sucht / Then existieren
  `edit/TripEditView.svelte`, `alert-rules-editor/AlertRulesEditor.svelte`, `AlertRuleRow.svelte` und
  `alertChannels.ts` nicht mehr, kein Quell- oder Testcode importiert sie, und der Barrel-Export von
  `AlertRulesEditor` in `organisms/index.ts` ist entfernt. (Ersetzt `fix_2277_s1_alarme_tab_route`
  AC-7.)
  - Test: Kern — angepasster `legacy_wizard_removed.test.ts` prüft Nichtexistenz und fehlenden Export;
    ein Import-Scan über `src/` findet keine Referenz.
  - Mutations-Gegenprobe: den Barrel-Export wieder einfügen oder eine der Dateien zurücklegen ⇒ der Test
    wird rot.

- **AC-8:** Given ein Nutzer ruft `/trips/<id>/edit` auf / When die Seite lädt / Then wird er wie bisher
  umgeleitet (HTTP 307 auf die Trip-Detailseite) und sieht keine Fehlerseite.
  - Test: Staging-E2E bzw. bestehender Routen-Test prüft den Redirect; der Redirect-Pfad hat keinen
    Import auf gelöschte Dateien.
  - Mutations-Gegenprobe: Redirect aus der Route entfernen ⇒ der Test wird rot.

- **AC-9:** Given die Compare-Anlegeseite `/compare/new` / When sie nach dieser Scheibe geöffnet und
  durchgeklickt wird / Then sind Reiter, Lock-Hinweise und Verhalten unverändert gegenüber vor der
  Scheibe (Referenz der Parität).
  - Test: Kern — bestehende `compareNewLogic`- und Compare-Editor-Tests bleiben unverändert grün;
    Staging-E2E durchläuft `/compare/new`.
  - Mutations-Gegenprobe: die Compare-Reiter-Definition ändern ⇒ Paritätstest und Compare-Tests werden rot.

- **AC-10:** Given ein Nutzer öffnet `/trips/new` in 390 px Breite / When er die Reiterleiste bedient
  / Then funktioniert sie wie bisher (horizontal bedienbar, aktiver Reiter sichtbar, gesperrte Reiter
  nicht anwählbar, kein horizontales Seiten-Scrollen), und die neuen Beschriftungen „Alarme" und
  „Versand" sind lesbar.
  - Test: Staging-E2E bei 390 px (Anpassung von `issue-661-trip-new-mobile.spec.ts`).
  - Mutations-Gegenprobe: die Beschriftung im Mobile-Spec nicht anpassen ⇒ der Spec wird rot, damit ist
    die Bewachung nachgewiesen.

## Tests

**Neu:**
- **Paritätstest** (`shared/__tests__/`, `node --test`): liest die echten Reiter-Definitionen von
  `TripNewEditor` und `CompareNewEditor` und prüft ab Wetter-Metriken Label, Reihenfolge und Lock-Hinweis
  (AC-1, AC-2, AC-3). Keine Mocks der Prüflinge. Die Wetter-Metriken-Ausnahme steht im Test mit Begründung.
- **Lock-Test** (`trip-new/__tests__/` bzw. Erweiterung `tripNewLogic.test.ts`): Alarme frei nach
  Wertebereiche, Versand frei nach Alarme, `canSave` nur mit `versand`, Meilensteine „/4" (AC-2, AC-4).

**Anzupassen (neue IDs und Kette):** `trip_new_wertebereiche_reiter.test.ts`, `tripNewLogic.test.ts`,
`trip_new_alarme_reiter.test.ts` (`activeTab: 'alerts'` ⇒ `'alarme'`),
`trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein.test.ts` und
`trip_new_versandkanaele_unabhaengig_von_metriken.test.ts` (`activeTab: 'zeitplan'` ⇒ `'versand'`),
`legacy_wizard_removed.test.ts`.

**Zu löschen (Tests der gelöschten Bausteine):** siehe Affected Files. **Mutations-Gegenprobe vor jeder
Löschung (Pflicht):** Für jede zu löschende Testdatei wird geprüft, welche Zusicherung sie bewacht
(z. B. `issue_503_etappen_waypoints`: Etappen-/Wegpunkt-Verhalten; `issue_523_suggested_flag_cleanup`:
Aufräumen des `suggested`-Flags; `alertRegelNurAenderung`: Delta-Metrik-Regel). Lebt die Zusicherung nur
im gelöschten Baustein, darf der Test fallen. Wird sie von einem noch produktiven Baustein
(`TripNewEditor`, `AlarmeTab`, Hub) ebenfalls ausgeübt, muss sie dort bereits bewacht sein oder wird in
einen verbleibenden Test übernommen — gelöschte Tests dürfen keine noch gültige Zusicherung mitnehmen.
Der Adversary belegt das per String-Mutation am produktiven Baustein mit externer Sicherungskopie (nie
`git checkout/stash/reset`).

**Playwright (Staging):** angepasst `issue-661-trip-new-mobile.spec.ts`,
`gewitter-absolutregel-gesperrt.spec.ts`, `versandzeit-stundenwahl.spec.ts`, geprüft
`issue-776-metrics-toggle.spec.ts`; gelöscht die veralteten AlertRulesEditor-Specs und `fillStep4`.

## Staging-Verifikation

Nach Merge und Staging-Auto-Deploy (`https://staging.gregor20.henemm.com`), mit Test-Nutzer (kein
Sammel-Versand):

1. **Desktop:** `/trips/new` durchklicken — Reiterleiste und Lock-Hinweise nach AC-1/AC-2; Anlegen
   bleibt gesperrt bis Alarme und Versand besucht sind (AC-4).
2. **Persistenz:** Test-Trip mit geänderten Wertebereichen und einer Alarm-Einstellung anlegen, im Hub
   öffnen, Werte prüfen (AC-5).
3. **Mobil 390 px:** Reiterleiste wie in AC-10.
4. **Vergleich:** `/compare/new` durchklicken, Parität zu AC-3 sichtbar prüfen (AC-9).
5. **Redirect:** `/trips/<id>/edit` leitet um (AC-8).
6. Staging-Basic-Auth und Login-Zugangsdaten aus `/home/hem/gregor_zwanzig_staging/.env`; ist ein Teil nicht
   messbar, wird er als `NOT_MEASURABLE_ON_STAGING` geführt, nicht als PASS.

Reine Frontend-Änderung; Mail-Validatoren entfallen (kein Mail-Inhalts-Eingriff).

## Known Limitations

- AC-5 aus #2277 ist nach S3 nur teilweise erfüllt: `compareNewLogic.ts` (S4) und
  `EditReportConfigSection.svelte`/`reportConfigWrite.ts`/`BriefingsTab` (S5) bestehen weiter. Issue #2277 bleibt offen.
- Die Lock-Ketten von Trip und Vergleich sind nach S3 inhaltlich gleich, aber noch zwei getrennte Implementierungen
  (`tripNewLogic.ts`, `compareNewLogic.ts`); die Zusammenführung folgt in S4.
- Der Lock-Hinweis von „Wetter-Metriken" bleibt kind-eigen („erst alle GPX hochladen" bzw. „erst mind. 2 Orte
  auswählen"), weil die Eingangsbedingung fachlich verschieden ist.
- Die Tab-IDs im Trip-Hub (`TripTabs.svelte`) bleiben historisch abweichend; nur die Beschriftungen sind dort bereits gleich.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (umgesetzt wird ADR-0032, progressive Tab-Editoren)
- **Rationale:** S3 gleicht eine bestehende Reiterleiste an das schon geltende Vergleichs- und Hub-Muster an und
  baut toten Code zurück. Keine Entscheidungsfläche wird neu entschieden oder umgekehrt.

## Changelog

- 2026-10-01: Initial spec created (#2277 S3: Reiter-Angleichung `/trips/new` + Rückbau AlertRulesEditor/TripEditView)
