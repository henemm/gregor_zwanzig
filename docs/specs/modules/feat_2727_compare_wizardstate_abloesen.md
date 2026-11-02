---
entity_id: feat_2727_compare_wizardstate_abloesen
type: module
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
tags: [frontend, compare, rueckbau, epic-2345, dod-1, adr-0097]
issue: "#2727"
epic: "#2345"
---

# compareWizardState ablösen (Epic #2345, DoD-1)

## Approval

- [ ] Approved

## Purpose

Das geteilte Zustandsmodul `CompareWizardState` (Klasse, Context-Schlüssel, Import über Komponentengrenzen) wird gelöscht. Hub und Anlegen des Ortsvergleichs halten ihren Zustand wie beim Trip (`TripTabs` / `TripNewEditor`). Für den Nutzer ändert sich nichts. Ein Wächter-Test verhindert die Rückkehr einer Klasse mit gleicher Rolle. Zusätzlich wird der zweite Teil von DoD-1 abgeschlossen: Abgleich der `context ===`-Zweige in `shared/` gegen die Soll-Liste aus #2276.

## Source

- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` (199 Zeilen, wird gelöscht)
- **Identifier:** `CompareWizardState` (Klasse), Context-Schlüssel `compare-wizard-state` und `compare-wizard-profile`
- **Schicht:** ausschließlich Frontend (SvelteKit). Keine Änderung an Go-API oder Python-Core.

Stand gemessen auf `origin/main` `60b932c94`. Die Analyse steht in `docs/context/feat-2727-compare-wizardstate.md` und ist die verbindliche Grundlage.

> **Trip/Ortsvergleich-Teilung (ADR-0097):** Es entsteht **kein** neues Compare-Zustandsmodul mit Trip-Pendant. Das Anlegen folgt dem Muster `TripNewEditor` (lokaler `$state`, ein POST). Der Hub behält einen komponentenlokalen Feldsatz (siehe „Ehrliche Restabweichung"). Der Produktivcode in `shared/` bleibt unberührt.
> **Mandantentrennung:** `user_id` kommt weiter aus dem Auth-Kontext, nie `"default"`. Die Datenwege ändern sich nicht; die Cross-User-Sperre wird mit zwei Nutzern erneut belegt (AC-19).
> **Kanäle:** Kein Briefing- oder Alarminhalt ändert sich. Der Payload für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) bleibt bitgleich (AC-8).

## Estimated Scope

- **LoC (produktiv):** ca. +250 / −400
- **Files:** ca. 8 produktiv, ca. 20–25 Tests, 1 Doku-Spec
- **Effort:** medium (Risiko MEDIUM: der Hub, 985 Zeilen, ist zentral)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare/compareEditorSave.ts` (`buildNewComparePresetPayload` :425, `buildComparePresetSavePayload` :121) | Upstream, unverändert | Payload-Bau |
| `compare/compareHubPersistenz.ts`, `shared/*VergleichSpeicherung.ts`, `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | Upstream, unverändert | einzige Schreiber (Leitplanke #102) |
| `compare/compareHubHydration.ts`, `*PropsAus.ts` (corridor, alarme, versand, wetterMetriken) | Upstream, nur Kommentare | Hydrierer und Adapter Zustand → Organismus-Props |
| `shared/anlegeLockEngine` | Upstream, unverändert | Freischaltung beim Anlegen |
| ADR-0097, `tests/tdd/test_pendant_gate.py` | Gate | Pendant-Sperre |
| Paritäts-E2E #2347 S4 (`hub-*.spec.ts`, `hub-anlegen-ablauf.spec.ts`) | Absicherung | Verhalten Hub/Anlegen |

## Implementation Details

Reihenfolge innerhalb dieser einen Spec und dieses einen Tickets (keine neuen Issues): **S1 Anlegen**, danach **S2 Hub**.

### S1 Anlegen

- `routes/compare/new/+page.svelte`: keine Instanz, kein `setContext` (weder `compare-wizard-state` noch das ungelesene `compare-wizard-profile`); reicht `data.vorlage` und `locations` als Props durch.
- `compare-new/CompareNewEditor.svelte`: Zustand als lokales `$state` nach dem Muster `TripNewEditor:91–140`. Startwerte aus `stateOverride` (existiert, :81–96) bzw. Vorlage. Speichern als lokale `async function` (`buildNewComparePresetPayload` + `api.post` + `goto`) statt `wiz.saveNewPreset()`. Die Prüfwerte `nameOk/orteOk/canContinue/orteContinueReady` bleiben im Editor (:161–200).
- `compare-new/compareNewVorlage.ts`: reine Funktion `preset, locations → Feldsatz` statt Mutation eines Zustandsobjekts. Das nur geschriebene, nie gelesene Feld `weekday` entfällt.
- `compare/steps/Step2Orte.svelte`: `pickedIds` als `$bindable`-Prop statt `getContext('compare-wizard-state')` (der Orte-Organismus ist Compare-eigen, kein Pendant-Verstoß).
- `shared/__tests__/infoboxSsr.ts`: `neuerWiz` und Context-Map entfallen; alles über `stateOverride` (zentraler Hebel für die abhängigen Tests).

### S2 Hub

- **Variante A (gewählt):** `CompareTabs.svelte` ersetzt `new CompareWizardState()` (:355) durch ein komponentenlokales `$state`-Feldobjekt. 39 Vorkommen werden mechanisch umbenannt; Hydrationsstellen (:368–536) und `*PropsAus`-Adapter (:777–823) bleiben unverändert.
- `compareWizardState.svelte.ts` wird gelöscht. Tote Felder entfallen mit ihr: `saveStatus`, `saveError`, `metricsManuallyEdited`, `weekday`.
- Wächter-Test (neu) nach Vorbild `compare_hub_bridge_restlos_entfernt.test.ts` (zweiteilige Begriffe, Positivkontrolle).
- `issue_683_wizard_remove.test.ts` wird umgedreht.
- Doku-Korrektur in `rework_2276_s6h_ac2_endbilanz.md` (Summenzeile).

### Variantenvergleich Hub (Begründung für A)

| | A (ein `$state`-Objekt im Hub) | A' (je Reiter ein Satz) | B (Props `$derived` aus `currentPreset`) |
|---|---|---|---|
| Hub-Änderung | 39 Vorkommen mechanisch | A + Aufteilung | Hydration, Schreibweg, Rollback neu |
| geteilte Felder Cooldown/Quiet (Versand ↔ Alarme) | konsistent | auseinanderlaufend | konsistent |
| sichtbarer Wert vor Server-Antwort | erhalten | erhalten | verloren |
| Rollback (`rollbackVersandSnapshot`/`rollbackAlarmSnapshot`) | erhalten | erhalten | ohne Ziel |
| `shared/` + Ratsche | unberührt | unberührt | müssen geändert werden |

B würde nur gehen, wenn die geteilten Reiter einen eigenen Bearbeitungsstand im Vergleich bekämen (Änderung in `shared/`, Ratschen-Eingriff). Das ist ein eigenes Vorhaben und widerspricht der Leitplanke „kein Verhalten ändern".

### Ehrliche Restabweichung (offen benannt, mit dieser Spec freizugeben)

Der Hub hält weiterhin einen komponentenlokalen Feldsatz als Zwischenstand. Es entfällt das **geteilte Zustandsmodul** (Klasse, Context-Schlüssel, Import über Komponentengrenzen), **nicht jeder Zwischenstand**. Die volle Trip-Gleichheit („Reiter halten ihren Bearbeitungsstand selbst, der Hub hält nur `currentPreset`") ist mit diesem Ticket **nicht** erreicht und bleibt ein Folgevorhaben. DoD-1 wird hier als „Zustandsmodul abgelöst" erfüllt, nicht als „Hub ohne Zwischenstand".

### Zweiter Teil DoD-1: `context ===` in `shared/`

Soll-Liste eingefroren in `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` (`EINGEFROREN_SOLL_ANZAHL = 47`). Befund: Ist = 47, identisch mit der Soll-Liste, kein Treffer außerhalb. Alle 15 HERKUNFT-Zweige (`rework_2276_s6h_ac2_endbilanz.md:146–162`) begründen sich mit anderen Persistenz-Endpoints, Katalog-Ladepfaden oder `maybeSchedule`, keiner mit dem Wizard-Zustand. Die drei Gates `p.context === 'vergleich' && !!p.zustand` (`versandVergleichSpeicherung.ts:244`, `wertebereicheVergleichSpeicherung.ts:209`, `weatherMetricsCompareSave.ts:561`) prüfen die aus Props gebaute `*ZustandsBruecke`, nicht die Klasse, und bleiben. **Ergebnis: Abgleich bestanden; es entfällt kein Zweig.** Nur die Summenzeile der Doku (:165: „14 / 46") ist falsch (richtig: 15 HERKUNFT, 47 gesamt; Tabellen 27/5/15 = 47) und wird korrigiert. Da die Ratsche nach `datei:zeile` geschlüsselt ist, bleibt der Produktivcode in `shared/` unberührt (Kommentarzeilen nur zeilenneutral, falls überhaupt: `CorridorEditor.svelte:58` und `CorridorEditorMobile.svelte:67` erwähnen den Schlüssel in einem Kommentar).

### Nebenbefund (Verhalten bleibt)

Schlägt der POST beim Anlegen fehl, landet die Meldung in `saveError`, das niemand liest; „Briefing aktivieren" tut dann für den Nutzer still nichts. Der Umbau behält das Verhalten bei. Eintrag im Sammel-Issue #1199, **keine Änderung in diesem Ticket**.

## Expected Behavior

- **Input:** unverändert (Nutzer legt Ortsvergleiche an und bearbeitet sie im Hub).
- **Output:** unverändert, Verhalten und gespeicherte Daten identisch zum Stand vor dem Umbau.
- **Side effects:** keine. Die Klasse, zwei Context-Schlüssel und vier tote Felder verschwinden.

## Acceptance Criteria

**Entfernen und Wächter**

- **AC-1:** Given der Stand nach dem Umbau / When im Quellcode (`frontend/src`) nach der Datei `compareWizardState.svelte.ts` und nach Importen darauf gesucht wird / Then existiert die Datei nicht mehr und keine Datei (Produktivcode, Test, Hilfsmodul wie `svelteTsModulHook.mjs`) importiert oder referenziert sie.
  - Test: Wächter-Test (a); geprüft über den echten Dateisystem-Zustand, nicht über Dateiinhalt einer einzelnen Datei.

- **AC-2:** Given der Wächter-Test / When der Context-Schlüssel `compare-wizard-state` oder `compare-wizard-profile` im Code unter `frontend/src` vorkommt / Then schlägt der Wächter fehl; reine Kommentarzeilen werden nicht gezählt.
  - Test: Wächter (b), zweiteilig zusammengesetzte Suchbegriffe, damit der Wächter sich nicht selbst findet.

- **AC-3:** Given der Wächter-Test / When unter `compare/` oder `compare-new/` eine `.ts`- oder `.svelte.ts`-Datei eine Klasse oder Factory mit `$state` exportiert / Then schlägt der Wächter fehl, auch wenn die Klasse anders heißt; reine Daten-Factories ohne `$state` bleiben erlaubt.
  - Test: Wächter (c) prüft die Rolle statt des Namens. Die Positivkontrolle legt eine künstliche Datei mit umbenannter Klasse samt `$state` in ein Temp-Verzeichnis an und beweist, dass der Wächter sie findet; eine Daten-Factory dort beweist, dass sie erlaubt bleibt.

- **AC-4:** Given der Wächter-Test / When unter `compare/` oder `compare-new/` irgendwo `setContext` oder `getContext` verwendet wird / Then schlägt der Wächter fehl.
  - Test: Wächter (d) mit Positivkontrolle (künstlicher Treffer wird gefunden). Der heutige Treffer `getContext` in `Step2Orte.svelte` ist durch AC-6 beseitigt.

**Anlegen unverändert (S1)**

- **AC-5:** Given ein Nutzer ruft `/compare/new` auf / When er Name, Region, Aktivitätsprofil und Orte einträgt und das Briefing aktiviert / Then wird genau **ein** `POST /api/compare/presets` abgeschickt, der Editor navigiert danach wie bisher (`goto`), und der Payload enthält alle eingegebenen Werte.
  - Test: Editor-Test mit echtem Request-Mitschnitt (Zähler der POSTs = 1), kein Mock der eigenen Annahme; Prüfung im Paritäts-E2E `hub-anlegen-ablauf.spec.ts` gegen Staging.

- **AC-6:** Given der Schritt „Orte" im Anlegen / When der Nutzer Orte auswählt oder abwählt (inkl. Smart-Import) / Then wirkt die Auswahl über die bindbare Prop `pickedIds` direkt im Editor-Zustand, ohne Context, und der Weiter-Knopf (`orteContinueReady`) reagiert wie bisher.
  - Test: Komponententest `Step2Orte` mit gebundenem `pickedIds`; E2E `issue-452-smart-import-step2.spec.ts` bleibt grün.

- **AC-7:** Given die Seite `/compare/new?from=<Vorlage>` / When sie geöffnet wird / Then sind Felder, Orte und Metriken **einmalig** beim Start aus der Vorlage vorbelegt (ohne `$effect`); eine spätere Änderung am Formular wird nicht von der Vorlage überschrieben, `weekday` wird weder gesetzt noch gesendet.
  - Test: `compareNewVorlage.test.ts` prüft den zurückgegebenen Feldsatz (reine Funktion `preset, locations → Feldsatz`); Wächter, dass `CompareNewEditor` die Vorlage nicht in einem `$effect` anwendet (AC-10 aus #2277 S2c bleibt gültig).

- **AC-8:** Given ein neu angelegter Ortsvergleich ohne Berührung des Versand-Reiters / When gespeichert wird / Then ist der gesendete Payload (Standardversand, Kanäle E-Mail, Telegram, SMS, Premium-SMS, Zeitplan, Alarm-Vorgaben, Wertebereiche) **identisch** zu dem vor dem Umbau und zum Trip-Standard.
  - Test: bestehende Tests `standardwerte_payload_paritaet_compare` und `anlegen_ohne_versand_beruehrung_postet_standardversand` laufen ohne Context-Stub und bleiben grün.

- **AC-9:** Given der Anlege-Editor / When der Nutzer die Reiter nacheinander öffnet / Then schalten Lock-Engine und Freischaltung (`anlegeLockEngine`) die Reiter wie bisher frei, und die Reiterkennungen entsprechen der Trip-Reiterleiste.
  - Test: `compare_new_lock_engine_wirkstelle`, `compare_anlege_freischaltung`, `anlege_reiter_kennungen_gleich`, `anlege_reiterleiste_trip_vergleich_paritaet` ohne Stub am Schlüssel `compare-wizard-state`, grün.

- **AC-10:** Given der Anlege-Editor in den Infobox- und Begriffs-Prüfständen (`infoboxSsr`) / When die Seite serverseitig gerendert wird / Then erscheinen Infoboxen und Begriffserklärungen nur beim Anlegen und an den vier Begriffen wie bisher, und der Helfer `neuerWiz` ist nicht mehr nötig (Zustand über `stateOverride`).
  - Test: `infobox_*`, `standardwerte_*`, `begriff_erklaerung_*` (inkl. `molecules/`) grün über den umgebauten zentralen Helfer.

**Hub unverändert (S2)**

- **AC-11:** Given ein Nutzer bearbeitet im Hub einen Reiter (Wertebereiche, Wetter-Metriken, Versand oder Alarme) / When er einen Wert ändert / Then wird wie bisher per Autosave gespeichert und der Speicher-Chip zeigt „speichert" → „gespeichert".
  - Test: Hub-Paritäts-E2E `hub-*.spec.ts` (#2347 S4) grün; Komponententest für den Speicherstatus ohne neue Mocks.

- **AC-12:** Given der Hub wurde mit einem Stand geöffnet und der Server hat inzwischen eine neuere Version / When gespeichert wird / Then erscheint wie bisher der 412-Konflikt und der Nutzer sieht den Konfliktzustand statt stiller Überschreibung.
  - Test: die vorhandenen 412-Tests des Hubs bleiben unverändert grün: `compare/__tests__/compare_kopf_412_nochmal_speichern.test.ts`, `compare_orte_status_412_nochmal_speichern.test.ts`, `hub_nochmal_speichern_ueber_reiterwechsel.test.ts`, `compare_konflikt_nutzlast_am_eintrag.test.ts`, `compare_retry_fehlerpfade_kein_verlust.test.ts`, `compare_retry_reiterwechsel_eingabe_bleibt.test.ts`, `compare_seitenaufbau_uebernimmt_etag.test.ts`; E2E `e2e/hub-wertebereiche-speichert-selbst.spec.ts`.

- **AC-13:** Given ein Speichern im Hub schlägt fehl / When die Server-Antwort ein Fehler ist / Then wird der sichtbare Wert über `rollbackVersandSnapshot` bzw. `rollbackAlarmSnapshot` auf den letzten gespeicherten Stand zurückgesetzt.
  - Test: Hub-Test mit echtem Fehlerantwort-Fixture, der den Rollback am sichtbaren Wert prüft (Variante A erhält das Rollback-Ziel).

- **AC-14:** Given Cooldown und Ruhezeiten (`alertCooldownMinutes`, `alertQuiet*`), die sowohl im Versand- als auch im Alarme-Reiter sichtbar sind / When der Nutzer den Wert in einem der beiden Reiter ändert / Then zeigt der andere Reiter denselben Wert, und der Wert wird nicht auseinanderlaufend gespeichert.
  - Test: neuer Test `hub_geteilte_felder_cooldown_quiet_konsistent.test.ts` (Änderung in Versand sichtbar in Alarme und umgekehrt). Dieser Test schlägt bei Variante A' (je Reiter ein Satz) fehl und beweist damit die Wahl von A.

- **AC-15:** Given ein Hub, dessen Preset-Daten erst nach dem ersten Rendern eintreffen (verzögerte Hydration) / When die Daten ankommen / Then füllen sich alle Reiter korrekt, ohne dass ein bereits vom Nutzer eingegebener Wert verloren geht oder ein Reiter leer bleibt.
  - Test: `compare_versand_hydration_unter_wetter_metriken` und `hub_reiter_gemeinsame_aufloesung` (heute mit Bezug auf die Klasse) laufen gegen das lokale Feldobjekt grün; ergänzt um einen Fall „Daten kommen spät".

- **AC-16:** Given der Hub nach dem Umbau / When die Adapter `corridorPropsAus`, `alarmePropsAus`, `versandPropsAus`, `wetterMetrikenPropsAus` die Reiter versorgen / Then verlangen sie nur ihre Ausschnitts-Typen (`*ZustandsQuelle`), nicht die Klasse, und die Wächter „Typ verschwunden" (`compare_wetter_metriken_wertprops`, `compare_versand_wertprops`, `compare_corridor_wertprops`, `compare_alarme_wertprops`) bleiben grün.
  - Test: genannte vier Tests grün (ggf. nur Kommentar-/Typnamen-Anpassung).

**Mandantentrennung**

- **AC-17:** Given zwei verschiedene Nutzer A und B mit je eigenen Ortsvergleichen / When Nutzer A einen Ortsvergleich anlegt oder im Hub bearbeitet und Nutzer B parallel dieselbe Seite öffnet / Then sieht B nie Daten von A, A kann keinen Ortsvergleich von B ändern (Cross-User-Sperre greift weiter), und die `user_id` stammt aus dem Auth-Kontext, nie `"default"`.
  - Test: bestehende Cross-User-Prüfungen der Compare-Endpoints und E2E mit zwei Nutzern gegen Staging; es wird geprüft, dass keine modulglobale Instanz Zustand zwischen Nutzern teilt (die Klasse war pro Seite instanziiert, der Umbau darf daran nichts ändern).

**Ratsche, Speicherwege, Pendant-Sperre**

- **AC-18:** Given der `context ===`-Abgleich in `shared/` / When die Ratsche `context_herkunft_zweige_eingefroren` läuft / Then bleibt die Anzahl bei **47** (27 / 5 / 15), die Zweige sind identisch zur eingefrorenen Soll-Liste, und der Produktivcode unter `shared/` (alle Nicht-Test-Dateien) ist im Umbau-Diff unverändert.
  - Test: `context_herkunft_zweige_eingefroren.test.ts` grün ohne Änderung der Soll-Liste; Diff-Prüfung im Validierungsschritt (`git diff --stat -- frontend/src/lib/components/shared` ohne Produktivdateien, ausgenommen `__tests__/`).

- **AC-19:** Given Datenerhalt-Leitplanke #102 / When ein Ortsvergleich gespeichert wird / Then schreiben weiterhin ausschließlich `compareHubPersistenz.ts`, die `*VergleichSpeicherung.ts`-Dateien und `weatherMetricsCompareSave.ts`; im neuen Code des Hubs und des Editors entsteht kein weiterer Schreibweg, und Bestandsfelder gehen nicht verloren (Read-Modify-Write mit Merge).
  - Test: bestehender Wächter `totcode_rueckbau_speicherweg.test.ts` (umgebaut ohne Klasse) bleibt grün; Round-Trip-Test: Preset mit nicht angefassten Feldern laden, einen Reiter ändern, gespeichertes Preset enthält die übrigen Felder unverändert.

- **AC-20:** Given ADR-0097 und die Pendant-Sperre / When der Umbau fertig ist / Then entsteht keine neue Compare-Komponente oder -Datei mit Trip-Pendant, und jede neue Datei unter `compare/` trägt, falls nötig, den Kopf `gz-eigenstaendig:`.
  - Test: `tests/tdd/test_pendant_gate.py` grün.

**Umgedrehte und umgebaute Tests, Doku**

- **AC-21:** Given der bisher gegenläufige Test `issue_683_wizard_remove.test.ts` / When er nach dem Umbau läuft / Then verlangt er, dass `compareWizardState.svelte.ts` **nicht** existiert und dass das Anlegen aus dem Editor selbst postet (kein `saveNewPreset` an einer Klasse).
  - Test: umgedrehter Test grün; vor dem Umbau rot nachgewiesen.

- **AC-22:** Given die Tests mit hartem Bezug auf die Klasse (`totcode_rueckbau_speicherweg`, `wizard_state_no_legacy_save`, `compare_wizard_save_new_preset_channels`, `compareNewVorlage`, `infoboxSsr`) / When sie nach dem Umbau laufen / Then bewahren sie ihre ursprüngliche Zusicherung (z. B. Kanäle im Anlege-Payload) am neuen Ort, statt gelöscht zu werden.
  - Test: jede umgebaute Testdatei bleibt in der Kern-Schicht grün; die Mutations-Gegenprobe des `implementation-validator` verfälscht jeweils die Wirkstelle (z. B. Kanal-Feld im Payload) und mindestens ein Test wird rot.

- **AC-23:** Given die Doku `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` / When die Summenzeile (:165) gelesen wird / Then lautet sie 15 HERKUNFT-Zweige und 47 insgesamt (Tabellen 27 / 5 / 15 = 47) statt 14 und 46, mit Hinweis auf den bestandenen Abgleich aus #2727.
  - Test: Doku-Compliance-Test (`# doc-compliance-test`), der die Summe der Tabellenzeilen mit der Summenzeile abgleicht, oder manuelle Diff-Prüfung im Validierungsschritt.

- **AC-24:** Given das Gesamtergebnis / When die Kern-Schicht (`frontend-test`, `svelte-check`, `lint`, `go-test`, `test`) und danach auf Staging das Paritäts-E2E #2347 (kind-parametrisiert, `hub-*.spec.ts`, `hub-anlegen-ablauf.spec.ts`, `compare-neu-kanal-anlegen.staging.spec.ts`) laufen / Then sind alle grün, und das Verhalten des Anlegens und des Hubs ist für den Nutzer unverändert.
  - Test: 6 CI-Checks grün; `/e2e-verify` gegen Staging.

## Geplante Tests

**Neu:**

- `frontend/src/lib/components/compare/__tests__/compare_wizard_state_entfernt.test.ts` (Wächter a–d, AC-1 bis AC-4, mit Positivkontrollen)
- `frontend/src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts` (AC-14)
- Fall „späte Hydration" in `compare_versand_hydration_unter_wetter_metriken.test.ts` bzw. `hub_reiter_gemeinsame_aufloesung.test.ts` (AC-15)
- Anlege-Editor-Test „ein POST, Payload vollständig" (AC-5), Dateiname nach Verhalten, z. B. `compare_new_editor_postet_einmal.test.ts`
- Round-Trip-Datenerhalt-Test (AC-19)

**Umzubauen (Context-Stub entfernen bzw. harter Bruch):**

- Harte Brüche: `compare/__tests__/totcode_rueckbau_speicherweg.test.ts`, `wizard_state_no_legacy_save.test.ts`, `compare_wizard_save_new_preset_channels.test.ts`, `compare-new/__tests__/compareNewVorlage.test.ts`, `shared/__tests__/infoboxSsr.ts` samt allen Abhängigen (`infobox_*`, `standardwerte_*`, `begriff_erklaerung_*`, `anlegen_ohne_versand_beruehrung_postet_standardversand`, `standardwerte_payload_paritaet_compare`, `molecules/begriff_erklaerung_*`), `compare_versand_hydration_unter_wetter_metriken.test.ts`, `hub_reiter_gemeinsame_aufloesung.test.ts`, `shared/__tests__/svelteTsModulHook.mjs` (Verweis prüfen).
- Stub am Schlüssel `compare-wizard-state` entfernen: `anlege_reiter_kennungen_gleich`, `anlege_reiterleiste_trip_vergleich_paritaet`, `compare_new_lock_engine_wirkstelle`, `compare_anlege_freischaltung`, `corridor_editor_laedt_keine_compare_klebeschicht`, `infobox_nur_beim_anlegen`, `begriff_erklaerung_an_den_vier_begriffen`.
- Umdrehen: `compare/__tests__/issue_683_wizard_remove.test.ts` (verlangte Datei :163 und `saveNewPreset` :215).
- E2E (nur beobachten, ggf. Selektoren): `e2e/issue-452-smart-import-step2.spec.ts`, `compare-neu-kanal-anlegen.staging.spec.ts`, `hub-anlegen-ablauf.spec.ts`, `hub-*.spec.ts`.
- Python-Gate: `tests/tdd/test_pendant_gate.py` (nur laufen lassen).

**Test-Politik:** kein Mock-Theater. Es werden keine `Mock()`/`patch()`, die nur die eigene Annahme spiegeln, eingeführt; Request-Mitschnitte und echte Komponenten-Renderings statt Dateiinhalt-Checks. Die Wächter-Tests sind strukturelle Wächter über echten Dateisystem-Zustand mit Positivkontrolle (Muster `compare_hub_bridge_restlos_entfernt.test.ts`), kein Ersatz für Verhaltensnachweise (AC-5 bis AC-17). Frontend-Tests laufen über `node --test`. Mutationen nur per String-Ersetzung mit externer Sicherungskopie.

## Definition of Done

- [ ] `compareWizardState.svelte.ts` gelöscht, kein produktiver Importeur, Wächter (AC-1–AC-4) grün inkl. Positivkontrollen
- [ ] Alle Verhaltens-ACs (AC-5–AC-17) durch Tests belegt, Kern-Schicht 100 % grün
- [ ] `context ===`-Ratsche unverändert 47, `shared/`-Produktivcode unberührt (AC-18)
- [ ] Doku-Summenzeile in `rework_2276_s6h_ac2_endbilanz.md` auf 15/47 korrigiert (AC-23)
- [ ] PR mit allen 6 CI-Checks grün gemergt, Staging-E2E inkl. Paritäts-E2E #2347 grün, Prod-Selftest Exit 0 (AC-24)

## Known Limitations

- **Ehrliche Restabweichung (Hub):** Der Hub behält einen komponentenlokalen Feldsatz als Zwischenstand; volle Trip-Gleichheit (Reiter halten ihren Bearbeitungsstand selbst, Hub nur `currentPreset`) ist **nicht** Teil dieses Tickets und ein Folgevorhaben (erfordert Änderungen in `shared/` samt Ratschen-Eingriff).
- **Nebenbefund:** Fehler beim Anlegen-POST werden in `saveError` geschrieben, das niemand liest; das Verhalten bleibt, Verweis auf Sammel-Issue #1199.
- Die 15 HERKUNFT-Zweige in `shared/` bleiben bewusst bestehen (geduldet, nicht fachlich).
- Zeilenverschiebungen in `shared/`-Dateien würden die nach `datei:zeile` geschlüsselte Ratsche rot machen; deshalb bleibt `shared/`-Produktivcode unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; stützt sich auf ADR-0097 (Trip/Ortsvergleich-Code-Teilung) und ADR-0032 (Wizard-Abschaffung, progressive Editoren).
- **Rationale:** Reiner Rückbau ohne neue Entscheidungsfläche. Die Wahl „Variante A" für den Hub ist eine Umsetzungsentscheidung innerhalb der Leitplanke „kein Verhalten ändern"; die Restabweichung wird offen in der Spec benannt, ein ADR ist nicht nötig, weil keine bestehende Entscheidung zurückgenommen wird.

## Changelog

- 2026-11-01: Initial spec created (Issue #2727, Epic #2345 DoD-1)
