# Adversary Dialog — feat-2347-s2-s4-paritaets-e2e
Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md
Datum: 2026-10-26 (Adversary-Lauf, Worktree 2346-s2)

## Checkliste
- [x] **Input:** CI-Lauf `e2e` gegen isolierten Stack; Unit-Lauf des Wächters (32 passed, `adversary-test-output.txt`); Staging-Lauf der Send-Dialog-Spec nur als `--list` (4 Fälle) belegt, NICHT ausgeführt.
- [x] **Output:** fünf Hub-Specs laufen per Schleife über `HUB_KINDS`; Fallzahlen per `--list`: HT 19, KB 20, KA 16, LM 20, SC 12, SD 4 (= Zuordnungstabelle). Basislauf der fünf Specs + 4 Etappen-Specs grün (109 passed, nur issue-758 AC-1/AC-4 rot, vorbestehend).
- [x] **Side effects:** Wegwerf-Daten `E2E-GZ-…` mit Aufräumen im `finally`. Abweichung vom Checklisten-Text: KA-5 nutzt den bestätigten Zweitnutzer (Fixture `testMitZustellbaremZiel`, Changelog der Spec) — Sende-Abruf wird per `page.route` abgefangen, kein echter Versand.
- [x] **AC-1:** PROVEN — Mutationen m01/m02 (Badge je kind, nur HT-6 des jeweiligen kind rot), m03 (Pfeiltasten, HT-4 beide kinds).
- [x] **AC-2:** PROVEN — m04 (PUT-Rumpf Trip, nur KB-4 route rot), m05 (fieldError Name, KB-7 + KB-10 beide kinds).
- [x] **AC-3:** PROVEN — m12/m13 (Region-Limit je kind, nur KA-3 des kind rot), m17/m18 (Orte-Anzahl, KA-8/KA-9), m19 (Kopf-Senden Trip, nur KA-5 route rot).
- [x] **AC-4:** PROVEN — m06 (Reihenfolge, LM-7 beide kinds), m07 (Ziel Bearbeiten Trip, nur LM-1 route rot), m08 (Pausieren des Vergleichs nur Anzeige, LM-3 und LM-4 vergleich rot).
- [x] **AC-5:** PROVEN per Basislauf grün + Fallzahl (LM-9/LM-10 vorhanden); keine eigene Mutation (Lücke, siehe Runde 2).
- [x] **AC-6:** TEILWEISE — m09 (Chip-Text, SC-4 beide kinds), m10/m11 (Rollback je kind, nur SC-4 des kind rot); ABER Produktfix-Schutzklauseln ungeprüft (F001), Kaskaden-Fall nicht abgedeckt (F002).
- [x] **AC-7:** AMBIGUOUS — nur `--list` (4 Fälle), kein Staging-Lauf im Artefaktordner (F005).
- [x] **AC-8:** PROVEN — Wächter 32 passed, `ALTLAST_MAX = 41` (tests/unit/test_e2e_compare_paritaet_waechter.py:85).
- [x] **AC-9:** PROVEN — 68 Zeilen `e2e/` in `.github/ci_e2e_specs.txt`, `E2E_MIN_SPECS: 68`, `E2E_MIN_EXECUTED_HAUPT: 451` (.github/workflows/ci.yml:285/286); Bindungstest grün.
- [x] **AC-10:** PROVEN (Stichprobe) — Fallzahlen je Datei = Spec; keine Abschwächung in den kind-Zweigen (Runde 1).
- [x] **AC-11:** PROVEN (Filter A/C) — kein `waitForTimeout`/`skip`/`__dirname`/`screenshot({path` in den fünf Specs; Filter B (3 Läufe) vom Implementierer, hier nicht wiederholt.
- [x] **AC-12:** TEILWEISE — 19 Mutationen, 16 gefangen, 3 NICHT gefangen (m14, m15, m16) ⇒ F001.
- [x] **AC-13:** PROVEN mit Vorbehalt F002 — Produktfix vorhanden und für den 1-Etappen-Fall wirksam.
- [x] **AC-14:** TEILWEISE — keine Datei-Verweise auf Nicht-Vorhandenes in Configs/Setups; wörtliche Treffer nur in Herkunfts-Kommentaren (F003); `--list` der Staging-Config zeigt vier Fälle; 758/880-Configs zeigen auf vorhandene Dateien.

## Dialog

### Runde 1
**Adversary:** Basislauf gruen (109 passed, 2 rot = issue-758 AC-1/AC-4). Mutationen m01-m13 an der Stelle, die der Nutzer erreicht (Produktkomponenten, nicht HUB_SEL): Badge-Zaehler je kind (m01 nur HT-6 route, m02 nur HT-6 vergleich), Pfeiltasten (m03 HT-4 beide), PUT-Rumpf Trip (m04 nur KB-4 route), fieldError Name (m05 KB-7/KB-10 beide), Aktionsreihenfolge (m06 LM-7 beide), Ziel Bearbeiten Trip (m07 nur LM-1 route), Pausieren des Vergleichs nur Anzeige (m08 LM-3/LM-4 vergleich), Chip-Text (m09 SC-4 beide), Rollback Etappen entfernt (m10 nur SC-4 route), Rollback Orte entfernt (m11 nur SC-4 vergleich), Regionslimit je kind (m12 nur KA-3 route, m13 nur KA-3 vergleich). Alle gefangen, kind-spezifisch.
**Implementierer (laut Spec-Changelog v1.1 und altbestand-messung.md, nicht neu befragt):** Produktfix AC-13 in EditStagesPanelNew.svelte (Rollback nach PUT-500, nicht bei 412 und nicht beim Wiederholen); KA-5 ueber Zweitnutzer-Fixture, KA-8 mit Geister-ID; issue-758 AC-1/AC-4 vorbestehend rot; compare-hub-inline-edit AC-14/15 Fremd-Flake.

### Runde 2
**Adversary:** m14 (412-Klausel entfernt), m15 (Wiederholen-Klausel entfernt), m16/m20/m21 (merkeServerStand in Autosave, Kaskade, manuellem Speichern entfernt): KEIN Test rot (74 bzw. 59 passed, inkl. issue-498, mobile-stage-date-edit, speicherung-ueberlebt-neuladen, compare-konfliktschutz-zwei-kontexte) ⇒ F001. Weitere gefangene Mutationen: m17/m18 (Orte-Anzahl, KA-8/KA-9), m19 (Kopf-Senden Trip, nur KA-5 route), m22 (Reiteranzahl, HT-2/4/5/7 beide kinds), m23 (Hub-Blatt pausiert ohne Archivieren, LM-10 beide kinds; subscriptionActions ignoriert kind absichtlich, daher nicht kind-spezifisch mutierbar). compare-hub-inline-edit: 9/9 (repeat-each=8 auf AC-14/15) und 97/97 (repeat-each=16 Gesamtdatei) gruen; kein Compare-Code beruehrt, bug-626 stand nicht in der Ratsche, die neuen Specs sortieren nach der Datei ⇒ S2 verursacht den Flake nicht. issue-758 AC-1/AC-4: veralteter Test (issue-498:100-102 dokumentiert: Kaskaden-Rueckfrage haelt den Speichervorgang zurueck), nicht in der Ratsche, vor S2 rot. Rueckstaende im Stack nach den Laeufen: nur issue-758-Reste und Reste meiner eigenen gescheiterten Mutationslaeufe (m08).
**Implementierer:** keine Antwort eingeholt (Kontextisolation); F001-F005 gehen an den Orchestrator.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Alle Testdaten sind selbst angelegte Wegwerf-Objekte (`seedHub`, `E2E-GZ-…`); Zweitnutzer nur in KA-5 (Fixture `testMitZustellbaremZiel`, bestaetigt ueber den Staging-Testweg des CI-Stacks); der Staging-Lauf der Send-Dialog-Spec wurde nicht ausgefuehrt.

## Findings

- F001 HIGH, spec_violation (AC-12/AC-13), evidence frontend/src/lib/components/edit/EditStagesPanelNew.svelte:163 (412-/Wiederholen-Klausel) und :122/:172/:414 (merkeServerStand): m14, m15, m16, m20, m21 liessen alle Tests gruen. Remediation: Tests fuer (a) 412 dann Nochmal speichern behaelt und persistiert die Eingabe, (b) erster Save ok, zweiter 500 setzt auf den ERSTEN Stand zurueck, (c) Kaskade-Erfolg gefolgt von Fehler; oder die Logik in ein svelte-freies Modul wie *VergleichSpeicherung.ts ziehen und per node:test sichern.
- F002 MEDIUM (AMBIGUOUS), evidence EditStagesPanelNew.svelte:440-457 (Kaskaden-Fehlerzweig: deferSave plus setError, kein Rollback) und frontend/e2e/hub-save-chip.spec.ts:206 (SC-4 route mit Ein-Etappen-Seed aus helpers.ts): bei einem Trip mit Folge-Etappen bleibt der Versuchswert nach PUT-500 stehen (gewollt laut #1393 R4, issue-498 AC-32), beim Vergleich und beim Trip ohne Folge-Etappen wird zurueckgesetzt. Nicht empirisch geprobt (Probe-Schreiben vom Werkzeug-Wächter verhindert). Entscheidung noetig, ob AC-6 hier Paritaet verlangt.
- F003 LOW, evidence frontend/e2e/hub-list-menu.spec.ts:8, hub-tab-bar.spec.ts:7, hub-save-chip.spec.ts:9, hub-kopf-aufbau.spec.ts:8, hub-kopf-bearbeiten.spec.ts:9, hub-send-dialog-target.staging.spec.ts:6, frontend/playwright.hub-send-dialog-target.staging.config.ts:4: Herkunfts-Kommentare nennen die geloeschten Dateien; AC-14 wörtlich (kein Treffer) verfehlt. In #1199 buchen oder AC praezisieren.
- F004 LOW, evidence frontend/e2e/hub-send-dialog-target.staging.spec.ts:21: Kommentar mit Hauptrepo-Pfad (Datei nicht in der Ratsche, Filter C greift nicht). #1199.
- F005 MEDIUM (AMBIGUOUS), AC-7: Staging-Lauf der Send-Dialog-Spec nicht belegt (nur --list mit 4 Faellen); kein Artefakt. Lauf nachholen.
- F006 LOW: Checkliste/Side-effects-Zeile der Spec nennt „kein Zweitnutzer", KA-5 nutzt einen (im Changelog dokumentiert). Checklistentext angleichen. Zusatz: die Fixture registriert je Worker einen Nutzer (Limit 5/h je IP); bei retries: 0 ohne Wirkung, bei vielen lokalen Wiederholungslaeufen moeglicher Stoerfaktor.
- F007 LOW (kein S2-Befund): issue-758 AC-1/AC-4 veraltet, nicht in der Ratsche, in #1196 buchen.


### Runde 3 (Fix-Loop 1)
**Adversary:** Neues Modul frontend/src/lib/components/shared/etappenSpeicherstand.ts, verdrahtet in EditStagesPanelNew.svelte (autoSaveClient im Auto-Save :159, direktClient in save() :120 und Kaskade :394). Node-Test etappen_rollback_auf_bestaetigten_stand.test.ts: 6/6, laeuft am echten Komponenten-Skript. Eigene Wiederholung per sed gegen Sicherungskopie (cmp danach IDENT): 412-Klausel entfernt ⇒ Test (a)+(b) rot; Wiederholen-Klausel entfernt ⇒ (b) rot; merke im PUT-Erfolg entfernt (deckt Auto-Save, Kaskade, manuell zugleich, da alle ueber direktPut) ⇒ (c),(d),(d) rot; Auto-Save-Client in der Komponente durch api ersetzt ⇒ (c),(d),(d) rot. Damit sind m14, m15, m16, m20, m21 gefangen (F001 geschlossen). Verdrahtungs-Mutationen: Kaskade nutzt autoSaveClient (Rollback) ⇒ Node-Test NICHT rot, aber E2E issue-498 AC-11/12/14/15/32/35 rot (6 Faelle, nach Neubau) ⇒ gefangen. save() (manuelles Speichern) nutzt autoSaveClient ⇒ weder Node-Test noch E2E rot ⇒ F008 LOW. Node-Kern um EditStagesPanelNew: 229/229 (12 benannte Dateien). Teilungsregel: Compare-Pendant ist CompareTabs.persistPickedIds (inline, Orte-Reiter, compare-eigen); *VergleichSpeicherung.ts betrifft Alarme/Versand/Wertebereiche, nicht Punkte-Listen ⇒ kein teilbares Pendant uebersehen, Muster aber gespiegelt. SD-Setup: Wegwerf-Nutzer, Kennwortdatei mode 0600 in gitignorierter e2e/playwright/.auth, Konto-Loeschung in afterAll; ABER schlaegt das Setup NACH der Registrierung fehl (Token/Bestaetigung/Login), laeuft die abhaengige Spec samt afterAll nie ⇒ Konto + Datei bleiben (F009 LOW/MEDIUM, nur Staging-Handlauf). AC-14: Treffer nur noch in .github/ci_e2e_specs.txt:126-127 und 335-339 (historische Kommentare, nennen die geloeschten Namen); Filter A/C in den hub-Specs und im SD-Setup sauber.
**Implementierer:** keine Antwort eingeholt.

### Runde 4
**Adversary:** F002 laut Orchestrator bewusstes Verhalten (nur Changelog). Keine weiteren Funde.

## Findings (Stand Runde 3)
- F001 geschlossen. F002 vom Orchestrator als gewollt entschieden. F003/F004 behoben bis auf historische Kommentare in .github/ci_e2e_specs.txt (LOW). F005 vom Implementierer belegt (Staging 5/5, test-green-output.txt, nicht von mir wiederholt).
- F008 LOW: EditStagesPanelNew.svelte:120 (save()) — Wechsel auf autoSaveClient faellt nirgends auf. Remediation: ein Node-Fall (manueller Fehler ohne Rueckfall) oder bewusst belassen.
- F009 LOW: hub-send-dialog-target.staging.setup.ts — Aufraeumen des Wegwerf-Kontos nur ueber afterAll der Spec; bei Setup-Abbruch nach der Registrierung Leck. Remediation: try/catch im Setup, das bei Fehler das Konto loescht.

## Bestätigungen (Code references)

- Confirmation: Rollback auf zuletzt bestätigten Stand, 412/Wiederholen ausgenommen; per Mutation belegt
  Code reference: frontend/src/lib/components/shared/etappenSpeicherstand.ts:56
- Confirmation: Test misst am echten Komponenten-Skript, 6/6, Mutationen rot
  Code reference: frontend/src/lib/components/trip-detail/__tests__/etappen_rollback_auf_bestaetigten_stand.test.ts:78
- Confirmation: autoSaveClient im Auto-Save, direktClient in save() und Kaskade; Kaskaden-Verdrahtung durch E2E bewacht, save() unbewacht (F008)
  Code reference: frontend/src/lib/components/edit/EditStagesPanelNew.svelte:159
- Confirmation: HUB_SEL/HubKind-Konstanten ohne Assertions, von allen fünf Specs genutzt; Hilfs-waitForTimeout nur im alten Drag-Helfer
  Code reference: frontend/e2e/helpers.ts:600
- Confirmation: HT-Fälle (19) per Schleife über HUB_KINDS, Mutationen m01/m02/m03/m22 rot
  Code reference: frontend/e2e/hub-tab-bar.spec.ts:71
- Confirmation: KB-Fälle (20), Mutationen m04/m05 rot
  Code reference: frontend/e2e/hub-kopf-bearbeiten.spec.ts:189
- Confirmation: KA-Fälle (16), kind-Zweige begründet, Mutationen m12/m13/m17/m18/m19 rot
  Code reference: frontend/e2e/hub-kopf-aufbau.spec.ts:197
- Confirmation: LM-Fälle (20), Mutationen m06/m07/m08/m23 rot
  Code reference: frontend/e2e/hub-list-menu.spec.ts:259
- Confirmation: SC-Fälle (12), Mutationen m09/m10/m11 rot
  Code reference: frontend/e2e/hub-save-chip.spec.ts:206
- Confirmation: SD-Fälle (4) per --list, Staging-Lauf vom Implementierer belegt
  Code reference: frontend/e2e/hub-send-dialog-target.staging.spec.ts:130
- Confirmation: Wegwerf-Nutzer, Kennwortdatei 0600, Leck bei Setup-Abbruch nach Registrierung (F009)
  Code reference: frontend/e2e/hub-send-dialog-target.staging.setup.ts:40
- Confirmation: Config listet vier Fälle, Dateinamen vorhanden
  Code reference: frontend/playwright.hub-send-dialog-target.staging.config.ts:17
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/playwright.1256-s8c.staging.config.ts:5
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/feat-1256-s8c.staging.setup.ts:5
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/playwright.1273-s3.red.config.ts:7
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts:8
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.setup.ts:6
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/issue-953.staging.setup.ts:4
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/compare-edit-redirect.spec.ts:15
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/compare-edit-redirect.staging.setup.ts:6
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/compare-editor-fidelity-s8d.spec.ts:19
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/compare-hub-fidelity-s8c.spec.ts:11
- Confirmation: nur Kommentare, kein Verweis auf gelöschte Datei
  Code reference: frontend/e2e/hub-reiter-alt-kennungen-umleitung.spec.ts:66
- Confirmation: AC-24-Deckung (Toast-Text, kein Reiterwechsel, CTA) in AC-2 übernommen, strenger als zuvor
  Code reference: frontend/e2e/issue-682-compare-editor-mobile.spec.ts:121
- Confirmation: AC-11-Fälle entfernt, Deckung in hub-save-chip SC-5/SC-6
  Code reference: frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts:966
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/src/lib/components/shared/__tests__/subscription_header_bedienlogik.test.ts:10
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/src/lib/components/shared/__tests__/subscription_header_einmal_gerendert.test.ts:10
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/src/lib/components/shared/__tests__/subscription_header_kontextneutral.test.ts:15
- Confirmation: nur Kommentar, kein Verweis auf gelöschte Datei
  Code reference: frontend/src/routes/trips/__tests__/trip_list_pause.test.ts:11
- Confirmation: 68 Listenzeilen, hub-Specs enthalten, issue-724 entfernt; Kommentarverweise historisch
  Code reference: .github/ci_e2e_specs.txt:381
- Confirmation: E2E_MIN_SPECS 68 und E2E_MIN_EXECUTED_HAUPT 451, Bindungstest grün
  Code reference: .github/workflows/ci.yml:285
- Confirmation: ALTLAST_MAX 41, Wächter 32 passed
  Code reference: tests/unit/test_e2e_compare_paritaet_waechter.py:85

## Verdict
**VERIFIED**

(mit LOW-Anmerkungen F008, F009) — F001 behoben und per eigener Mutation bewiesen; keine HIGH/CRITICAL offen.

## Geprüfte Dateien

- sha256:36fd6f97d8f7aa4eee5111b8db864baebf4f30b04a2f9e8bfd03d79e8becdc1c  .github/ci_e2e_specs.txt
- sha256:efbda566829aaf1406b8d3d9209c1c7234ed40e3db7d9aa40362d4cfd5009f6e  .github/workflows/ci.yml
- sha256:b5ad1c452e69418c2d2586af9e397c52d27911fe965123f61c587f7e3872b25c  frontend/e2e/compare-edit-redirect.spec.ts
- sha256:7c4525e53bc3b48903b7892c661692a3c474833393f1c32343fe1c09e9f59e63  frontend/e2e/compare-edit-redirect.staging.setup.ts
- sha256:7058d2b38a6b0d6ce0ba6ecffe2fc1e47915e8bb3bbb167dc0affeb8c3c7e123  frontend/e2e/compare-editor-fidelity-s8d.spec.ts
- sha256:a0a28a91b0889957df5915578a15c9e1c63c10cc9423899e194859567742f38a  frontend/e2e/compare-hub-fidelity-s8c.spec.ts
- sha256:fa13c1c7c9b1f988e326483acd04ee035f00d3a3ee282bb39e2c4bd102d7d0ef  frontend/e2e/feat-1256-s8c.staging.setup.ts
- sha256:92ba306250155255f426c61fa95ce7e59d4fd5bdbb25e9dfff03e07325538601  frontend/e2e/helpers.ts
- sha256:99371e19fc73260ca61b50208b667b42e720e1ccbbf0d768847ecfa31f2fc8e8  frontend/e2e/hub-kopf-aufbau.spec.ts
- sha256:14319799a4dca313d314ce599c22f40d96f68d5a5458a57147be4709899f4f38  frontend/e2e/hub-kopf-bearbeiten.spec.ts
- sha256:d164e87979a8ddb041a60044d12886e1baf17afd2157bfa5a8f5641b53eb0f0d  frontend/e2e/hub-list-menu.spec.ts
- sha256:089046f302f41eb4cf7d27608e2ade0bfedb5687a6f7b4d36a793976197f8036  frontend/e2e/hub-reiter-alt-kennungen-umleitung.spec.ts
- sha256:66377cd055624b16f50b3dcc69788dd6b5826495d45f711860ff0fccbcb89579  frontend/e2e/hub-save-chip.spec.ts
- sha256:620295927c68318a014c1b8188f217217d07567dbb392aa64c84861be5bebfb4  frontend/e2e/hub-send-dialog-target.staging.setup.ts
- sha256:498b68a1d4d3f0e8270b30f7673822f5f7fbb5a164f8b8e59e0da629207bd8d0  frontend/e2e/hub-send-dialog-target.staging.spec.ts
- sha256:184377920eac92fcde4eef23c6c8246d9e4bf130f9277f5485392acb938176ef  frontend/e2e/hub-tab-bar.spec.ts
- sha256:c1d339fd5af9e8204a82a06cc1a92e68bb379387105466eac9008a3a4eda045d  frontend/e2e/issue-682-compare-editor-mobile.spec.ts
- sha256:ee5db6cc45a1d8e47b62ac8823bc964d7e75722c21cca5dd01bd38fc7652bdad  frontend/e2e/issue-953.staging.setup.ts
- sha256:cd14035b810c0d245f60bc1b7fcdbdc9b7862d6942d07ec7e35c2709f3261eec  frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.setup.ts
- sha256:b3f805ed03fc0bc94ccdab3ff1d98aefbd84696ce1d2f0ae95ecba1e8ca77e61  frontend/e2e/playwright.1273-s3.red.config.ts
- sha256:481b0ad57191bc445dd340194c3eb40e87513d985049e4fa2aeacf7b3b2ee3e4  frontend/e2e/playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts
- sha256:a9260e2a680013a55739828b4cfa818a96e4263f7b586a85720f81cc71019bf0  frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts
- sha256:b01137896c05aac10d788542cc86e521a373997e3673ac2455b20eec9a08090f  frontend/playwright.1256-s8c.staging.config.ts
- sha256:84af70d7cde913d0316abedcba9266825ab2d69b623a730af8b1f3cb5d306c27  frontend/playwright.hub-send-dialog-target.staging.config.ts
- sha256:9324d29ad018a8aa5ca29ba94d1a20127c1065ac751e6baef69817fa36e918d0  frontend/src/lib/components/edit/EditStagesPanelNew.svelte
- sha256:d695e90c05cdd752d3ab05232de4537f8d83fb5bd51886373d724f9fada2a811  frontend/src/lib/components/shared/__tests__/subscription_header_bedienlogik.test.ts
- sha256:5a89c27a7075d8f1a4a25f75009f699df10dff7c0f6ed0f2e25322c74074473d  frontend/src/lib/components/shared/__tests__/subscription_header_einmal_gerendert.test.ts
- sha256:8ae8ac5fd913e751e36f2f036a9a63a79d147d95c07001dc4a677ea46cbd96b9  frontend/src/lib/components/shared/__tests__/subscription_header_kontextneutral.test.ts
- sha256:102f89d1805d81d3b6563c055391148cc4f57ac2ab40dc29cc624c1f62b34aa3  frontend/src/lib/components/shared/etappenSpeicherstand.ts
- sha256:fbede9c0935a9cc4c16a0d3b4ce2fef019e744e733b03be8f73a07adf56c697f  frontend/src/lib/components/trip-detail/__tests__/etappen_rollback_auf_bestaetigten_stand.test.ts
- sha256:51ab0fba538cc8cb48de8d14ac4f546773c712f93a3ad0acf9c83254a7282431  frontend/src/routes/trips/__tests__/trip_list_pause.test.ts
- sha256:477ad6c4bb075c795e3263fb4b844e838228d3c4633b483cd8dc3cf05595ae73  tests/unit/test_e2e_compare_paritaet_waechter.py

## Prüfbasis

- base: 801df24120a89b900ddcded322085c9bf850783f
- blob:79c83b89092d7f9a7d9f2e18bd82c74004f46118  .github/ci_e2e_specs.txt
- blob:4f4aa35e5b16db39923928f47472e8966ead21a0  .github/workflows/ci.yml
- blob:1573eb53d74bfb8920fe243dac7b2db2e81a93a4  frontend/e2e/compare-edit-redirect.spec.ts
- blob:f43048bb53e20b36c3a404cdd83651c2ae16609a  frontend/e2e/compare-edit-redirect.staging.setup.ts
- blob:f56527d0c76a8c8af268476281047d1901c428c6  frontend/e2e/compare-editor-fidelity-s8d.spec.ts
- blob:08e7942b57fd5e38e18c38d453c445e4ccdb6bdc  frontend/e2e/compare-hub-fidelity-s8c.spec.ts
- blob:30d2be5dbcd84583d4f4d636fc4e6e021a4eeea6  frontend/e2e/feat-1256-s8c.staging.setup.ts
- blob:6209532eb45ce6cb69280a524ade5576d391e6c1  frontend/e2e/helpers.ts
- blob:a7877a0b733cf1fedf8468e2eae73a23df1de8c3  frontend/e2e/hub-kopf-aufbau.spec.ts
- blob:a3e908584ba9da5b8022dca7778e1b43daaaa485  frontend/e2e/hub-kopf-bearbeiten.spec.ts
- blob:d8137ddcda169cadcb3aab6c6ec291c6f1f036ea  frontend/e2e/hub-list-menu.spec.ts
- blob:0a521eeb8ed2b1669e4b1e3995c63202e14518e4  frontend/e2e/hub-reiter-alt-kennungen-umleitung.spec.ts
- blob:388b4b25b4355d6150b963a23528e38089a75ce5  frontend/e2e/hub-save-chip.spec.ts
- blob:d206bf5ad60f0d9d66b5732ec7c6cb1a3f42989c  frontend/e2e/hub-send-dialog-target.staging.setup.ts
- blob:2afd0106f90597fb09e166337d37b91f3732c3bc  frontend/e2e/hub-send-dialog-target.staging.spec.ts
- blob:3ec7213934e51126cb55b6a886a27fece678ce57  frontend/e2e/hub-tab-bar.spec.ts
- blob:a23be5791a24c1bce8cbc7c76b340945629b13df  frontend/e2e/issue-682-compare-editor-mobile.spec.ts
- blob:c4ea2c2de04e0cca89946b7b9fbe052901075bb2  frontend/e2e/issue-953.staging.setup.ts
- blob:33948ec6f6ceece8ebbf7c4a46ea863d8ba13b6f  frontend/e2e/metrik-grundauswahl-schneidet-kanal.staging.setup.ts
- blob:4f6b2f48bb04f2bc20cab8a086c191b48e0d2daf  frontend/e2e/playwright.1273-s3.red.config.ts
- blob:eedbf3744efcde861d17fff5d6b331e718f1993a  frontend/e2e/playwright.metrik-grundauswahl-schneidet-kanal.staging.config.ts
- blob:74c06da8b2ed7fd031aec00ccbd29e44a5154489  frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts
- blob:2d2c34eaa66d05bf0c51db98d86cb68f70f47c0f  frontend/playwright.1256-s8c.staging.config.ts
- blob:3ac576e3c588559f19d108f612d06ed90433fa7a  frontend/playwright.hub-send-dialog-target.staging.config.ts
- blob:64f50b12bb89d27aa6d81515485ec5b8b384fa3e  frontend/src/lib/components/edit/EditStagesPanelNew.svelte
- blob:7706752bdd13e5c91ee741bfd5883498cab7faa5  frontend/src/lib/components/shared/__tests__/subscription_header_bedienlogik.test.ts
- blob:fe45273456aed57bfe162c3b82ed07952ec7bca0  frontend/src/lib/components/shared/__tests__/subscription_header_einmal_gerendert.test.ts
- blob:b878b8d1d5fc22681c17b93bd197bbae074f62d4  frontend/src/lib/components/shared/__tests__/subscription_header_kontextneutral.test.ts
- blob:fe4dfe5212f5427a9a13c349c5ded10fe170c248  frontend/src/lib/components/shared/etappenSpeicherstand.ts
- blob:c1e4eb48d4728ca6814f3d8edef8ff558b48d07b  frontend/src/lib/components/trip-detail/__tests__/etappen_rollback_auf_bestaetigten_stand.test.ts
- blob:b27981fc0856af2f6e8b274c4a838b5655bfbf61  frontend/src/routes/trips/__tests__/trip_list_pause.test.ts
- blob:5e7c6c490e745d8fa291e06c8f0cb74ec4cca3a4  tests/unit/test_e2e_compare_paritaet_waechter.py
