---
entity_id: rework_2243_playwright_loeschscheibe
type: feature
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
workflow: rework-2243-playwright-loeschscheibe
tags: [testing, e2e, playwright, aufraeumen, loeschscheibe]
---

# Playwright-Löschscheibe: tote Specs, toter Helfercode, verwaiste Configs (#2243)

## Approval

- [ ] Approved

## Purpose

Der Playwright-Bestand enthält Specs gegen abgeschaffte Oberflächen (5-Schritt-Wizard #622, alte Editor-Tabs, Auto-Save-Umbau #758), Quelltext-Greps mit fest verdrahtetem Hauptrepo-Pfad und Configs ohne Spec. Diese Scheibe löscht oder kürzt sie nach Test-Politik (veraltetes Verhalten wird gelöscht, nicht repariert), entfernt toten Helfercode und führt einen TypeScript-Wächter gegen fest verdrahtete Hauptrepo-Pfade ein. Produktcode bleibt unverändert.

## Source

- **Files (DELETE):**
  - `frontend/e2e/issue-264-stage-sort.spec.ts`, `frontend/e2e/issue-296-profile-editor.spec.ts`, `frontend/e2e/orts-vergleich-c4.spec.ts`, `frontend/e2e/trip-detail-region.spec.ts`, `frontend/e2e/topo-heroes.spec.ts`, `frontend/e2e/list-routes-btn-migration.spec.ts`, `frontend/e2e/issue-322-wicon-komponente.spec.ts`
  - `frontend/playwright.fix-923b.staging.config.ts`, `frontend/e2e/fix-923b-wire-live-sms-preview.staging.setup.ts`, `frontend/playwright.1272.staging.config.ts`
- **Files (MODIFY):**
  - `frontend/e2e/issue-675-stage-start-time.spec.ts` (AC-3/AC-4 raus), `frontend/e2e/issue-592-593-trips-navigation.spec.ts` (AC-1, AC-1b, AC-2 raus), `frontend/e2e/epic-138-metriken-editor.spec.ts` (zwei `describe.skip`-Blöcke raus), `frontend/e2e/trip-header-btn-migration.spec.ts` (Quelltext-Fall AC-1 raus), `frontend/e2e/forms-dialogs-btn-migration.spec.ts` (Quelltext-Schleife AC-1 raus)
  - `frontend/e2e/helpers.ts` (`fillStep1/2/3` samt `Step1/2/3Input`)
  - `frontend/e2e/compare-editor-slice3.spec.ts` (nur Kopfkommentar)
  - `.github/ci_e2e_specs.txt` (nur Kopfkommentar, Zeilen 8-17)
- **Files (CREATE):**
  - `frontend/src/lib/utils/naturalSort.test.ts` (Runner `node --test`, kein Vitest)
  - `tests/unit/test_ts_repo_path_hardcoding.py`
- **Identifier:** `naturalSort`/`naturalSortKey` (`frontend/src/lib/utils/naturalSort.ts`, unverändert); Wächterfunktion `scan_ts_for_hardcoded_repo_paths` in der neuen Python-Testdatei

> **Schicht-Hinweis:** Ausschließlich Test-, Config- und CI-Kommentar-Dateien (`frontend/e2e/`, `frontend/playwright.*.config.ts`, `frontend/src/lib/utils/*.test.ts`, `tests/unit/`, `.github/`). Kein Frontend-, Go-API- oder Python-Core-Produktcode wird geändert. Trip/Ortsvergleich-Teilung, Mandantentrennung und Kanäle sind nicht berührt.

## Estimated Scope

- **LoC:** ca. -1000 / +80 (Löschungen zählen kaum; neu sind Unit-Test und Wächter)
- **Files:** ca. 10 gelöscht, ca. 8 geändert, 2 neu
- **Effort:** low-medium, Risiko LOW

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.github/ci_e2e_specs.txt` | Positivliste | bleibt inhaltlich unverändert (keine gelöschte Spec steht drin) |
| `.github/workflows/ci.yml` (`E2E_MIN_SPECS: 80`, `E2E_MIN_EXECUTED_HAUPT: 709`) | Ratschen | bleiben unverändert |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | Wächter | bindet Ratschenzahlen an Positivliste, muss grün bleiben |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | Vorbild | Python-Pendant, Bauform des neuen Wächters |
| `tests/unit/test_e2e_compare_paritaet_waechter.py`, `tests/refactor/test_dead_code_scheibe3.py`, `tests/tdd/test_compare_e2e_storagestate_migration.py` | Wächter | nennen behaltene Dateien namentlich, bleiben unverändert grün |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/issue-264-stage-sort.spec.ts`, `issue-296-profile-editor.spec.ts`, `orts-vergleich-c4.spec.ts`, `trip-detail-region.spec.ts`, `topo-heroes.spec.ts`, `list-routes-btn-migration.spec.ts`, `issue-322-wicon-komponente.spec.ts` | DELETE | Specs gegen abgeschaffte Oberflächen bzw. worktree-blinde Quelltext-Greps (AC-1) |
| `frontend/playwright.fix-923b.staging.config.ts`, `frontend/e2e/fix-923b-wire-live-sms-preview.staging.setup.ts`, `frontend/playwright.1272.staging.config.ts` | DELETE | verwaiste Config/Setup ohne existierende Spec (AC-2) |
| `frontend/e2e/issue-675-stage-start-time.spec.ts`, `issue-592-593-trips-navigation.spec.ts`, `epic-138-metriken-editor.spec.ts`, `trip-header-btn-migration.spec.ts`, `forms-dialogs-btn-migration.spec.ts` | MODIFY | tote Fälle raus, Rest unverändert (AC-3) |
| `frontend/e2e/helpers.ts` | MODIFY | `fillStep1/2/3`, `Step1/2/3Input` raus (AC-4) |
| `frontend/src/lib/utils/naturalSort.test.ts` | CREATE | Ersatz-Zusicherung für issue-264 (AC-5) |
| `tests/unit/test_ts_repo_path_hardcoding.py` | CREATE | TS-Pfadwächter (AC-6) |
| `frontend/e2e/admin-nutzerverwaltung.staging.setup.ts`, `frontend/e2e/fix-2213-bauliche-aenderung.staging.setup.ts` | MODIFY | Ausnahme-Marker `// gz-main-path: <Grund>` (AC-6) |
| `.github/ci_e2e_specs.txt` | MODIFY | nur Kopfkommentar (AC-7) |
| `frontend/e2e/compare-editor-slice3.spec.ts` | MODIFY | nur Kopfkommentar (AC-8) |

## Implementation Details

Reihenfolge:

1. Specs löschen bzw. kürzen laut Urteilstabelle (je Datei eine Zeile im PR mit Grund).
2. `helpers.ts`: `fillStep1/2/3` und `Step1/2/3Input` entfernen (nach Wegfall von issue-264 ohne Aufrufer).
3. `naturalSort.test.ts` anlegen: sichert zu, dass die KHW-Etappennamen `KHW_03`, `KHW_01`, `KHW_00a` nach `naturalSort` als `KHW_00a`, `KHW_01`, `KHW_03` geordnet werden, auch wenn die Dateinamen (Datum-Präfix) eine andere Reihenfolge ergäben; ferner `KHW_10` nach `KHW_2`. Echte Funktion, keine Mocks.
4. Verwaiste Configs/Setup löschen (testMatch zeigt auf nicht existierende Spec, keine Verweise); Kopfkommentar der Positivliste kürzen.
5. `tests/unit/test_ts_repo_path_hardcoding.py`: scannt `frontend/e2e/**/*.ts` nach dem Hauptrepo-Pfad `/home/hem/gregor_zwanzig` im Code (Zeilen- und Blockkommentare sowie JSDoc ignoriert). Ausnahme `// gz-main-path: <Grund>` (Grund mind. sinnvoll lang) auf der Zeile des Fundes oder der Zeile davor. Legitime Ausnahmen: `admin-nutzerverwaltung.staging.setup.ts` (Credential-Ort `staging_admin.env`) und `fix-2213-bauliche-aenderung.staging.setup.ts` (Staging-`.env`). Der Wächter wird gegen einen Synthetikfall (temporäres Verzeichnis mit Beispieldatei) rot nachgewiesen und läuft auf dem echten Bestand grün.
6. Kopfkommentar `compare-editor-slice3.spec.ts` (Zeile 10): statt „fällt mit #2243 ersatzlos" nun „bleibt eigenständig (Create-POST mit 5 Slot-Feldern und `official_warnings`, in hub-anlegen-ablauf nicht abgedeckt)".
7. Nachmessung: `npx playwright test --list` vor und nach der Scheibe; betroffene Python-Tests benannt, Frontend-Unit-Tests ausführen.

## Expected Behavior

- **Input:** Repo-Stand `origin/main` 9c1ca4965.
- **Output:** schlankerer Playwright-Bestand ohne Specs gegen abgeschaffte Oberflächen, ohne worktree-blinde Quelltext-Greps, ohne toten Helfercode; neuer Wächter verhindert Rückkehr fest verdrahteter Hauptrepo-Pfade in TypeScript.
- **Side effects:** keine für Nutzer; CI-Job `e2e` unverändert (Positivliste und Ratschen berührt nichts Gelöschtes).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN die sieben Löschkandidaten und drei verwaisten Configs WHEN ein Python-Existenz-/Verweistest läuft THEN existiert keine davon und keine ausführbare Datei verweist auf sie (AC-1, AC-2).
- [ ] Test 2: GIVEN die fünf gekürzten Specs WHEN `npx playwright test --list` läuft THEN fehlen die toten Fälle, die verbleibenden Fälle sind gelistet, kein Import-/Syntaxfehler (AC-3, AC-4).
- [ ] Test 3: GIVEN `naturalSort` WHEN `naturalSort.test.ts` mit `node --test` läuft THEN KHW_00a < KHW_01 < KHW_03 und KHW_2 < KHW_10; gegen lexikografische Verfälschung rot (AC-5).
- [ ] Test 4: GIVEN eine synthetische TS-Datei mit Hauptrepo-Pfad im Code in `tmp_path` WHEN der Wächter läuft THEN schlägt er an; Kommentar-Fund und markierte Ausnahme schlagen nicht an; echter Bestand grün (AC-6).
- [ ] Test 5: GIVEN Positivliste und Ratschen WHEN `test_e2e_positivliste_ratschen_bindung.py` läuft THEN grün mit 80/709 (AC-7).
- [ ] Test 6: GIVEN die behaltenen Specs WHEN Paritäts-, Dead-Code- und storageState-Wächter laufen THEN grün, Slice3-Kopf korrigiert (AC-8, AC-9).

## Acceptance Criteria

- **AC-1:** Given die sieben Specs issue-264, issue-296, orts-vergleich-c4, trip-detail-region, topo-heroes, list-routes-btn-migration und issue-322 testen abgeschaffte Oberflächen oder sind reine Quelltext-Greps / When die Scheibe umgesetzt ist / Then keine dieser Dateien existiert mehr unter `frontend/e2e/`, und keine ausführbare Datei im Repo (`.ts`, `.mjs`, `.py`, `.sh`, `.yml`, `.json`, außer Doku, Specs und Kontextdateien unter `docs/`) verweist auf ihren Namen.

- **AC-2:** Given die Config `playwright.fix-923b.staging.config.ts` samt Setup `fix-923b-wire-live-sms-preview.staging.setup.ts` sowie `playwright.1272.staging.config.ts` verweisen auf nicht existierende Specs / When die Scheibe umgesetzt ist / Then alle drei Dateien existieren nicht mehr, und keine ausführbare Datei verweist auf sie; jede weitere `playwright*.config.ts` bleibt unberührt.

- **AC-3:** Given issue-675, issue-592-593, epic-138-metriken-editor, trip-header-btn-migration und forms-dialogs-btn-migration enthalten tote Fälle (Klick auf „Etappen speichern", `a.trip-link`, Quelltext-Lesen über Hauptrepo-Pfad, zwei `describe.skip`-Blöcke) / When die Scheibe umgesetzt ist / Then enthalten die Dateien diese Fälle nicht mehr, die verbleibenden Fälle (issue-675 AC-1/2/5/7, issue-592-593 AC-3/4/13, DOM-Fälle der beiden btn-migration-Specs, übrige Fälle von epic-138) sind unverändert vorhanden und werden von `npx playwright test --list` aufgelistet.

- **AC-4:** Given `helpers.ts` enthielt `fillStep1`, `fillStep2`, `fillStep3` und die Typen `Step1Input`, `Step2Input`, `Step3Input` ohne verbliebenen Aufrufer / When die Scheibe umgesetzt ist / Then kommen diese Namen nirgends mehr unter `frontend/` vor, und `npx playwright test --list` im Verzeichnis `frontend` läuft ohne Import- oder Syntaxfehler durch.

- **AC-5:** Given issue-264 sicherte zu, dass Etappen nach Etappenname statt nach Dateiname geordnet werden (KHW_00a vor KHW_01 vor KHW_03, obwohl das Datum-Präfix KHW_03 nach vorn zieht) / When `naturalSort.test.ts` mit `node --test` läuft / Then ist der Test grün; wird `naturalSort` testweise so verfälscht, dass es lexikografisch statt natürlich sortiert (z. B. `KHW_10` vor `KHW_2`), wird derselbe Test rot (Mutations-Gegenprobe, Verfälschung per String-Ersetzung mit externer Sicherungskopie).

- **AC-6:** Given TypeScript hatte keinen Wächter gegen fest verdrahtete Hauptrepo-Pfade / When `tests/unit/test_ts_repo_path_hardcoding.py` auf `frontend/e2e/**/*.ts` läuft / Then meldet er keinen Fund im echten Bestand (die zwei Credential-Stellen tragen `// gz-main-path: <Grund>`), Kommentarzeilen mit dem Pfad zählen nicht, und gegen eine synthetische TS-Datei mit `readFileSync('/home/hem/gregor_zwanzig/...')` im Code ohne Ausnahme-Marker schlägt der Wächter an (rot belegbar, ohne Mocks, mit echter Datei in `tmp_path`).

- **AC-7:** Given die Ratschen `E2E_MIN_SPECS=80` und `E2E_MIN_EXECUTED_HAUPT=709` sowie die Positivliste `.github/ci_e2e_specs.txt` / When die Scheibe umgesetzt ist / Then bleiben beide Zahlen in `ci.yml` unverändert, die Positivliste hat weiterhin 80 `e2e/`-Zeilen (nur der Kopfkommentar Zeilen 8-17 ist gekürzt), jede dort genannte Spec existiert, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` ist grün und der CI-Job `e2e` ist nach dem Merge grün.

- **AC-8:** Given der Kopfkommentar von `compare-editor-slice3.spec.ts` behauptete, die Datei falle mit #2243 ersatzlos / When die Scheibe umgesetzt ist / Then steht dort, dass die Datei eigenständig bleibt (Create-POST), der Satz „fällt mit #2243 ersatzlos" kommt nicht mehr vor, und kein Testfall der Datei ist verändert.

- **AC-9:** Given die bewusst behaltenen Specs layout-tab-vergleich, compare-editor-slice3, compare-editor-fidelity-s8d, compare-flow-navigation, feat-880-autosave-overlay, issue-758-save-indicator, issue-498-stage-date-autosave und trips / When die Scheibe umgesetzt ist / Then existieren alle unverändert (slice3 nur im Kopfkommentar), und die Wächter `test_e2e_compare_paritaet_waechter.py`, `test_dead_code_scheibe3.py` und `test_compare_e2e_storagestate_migration.py` sind grün.

## Definition of Done

- [ ] AC-1 bis AC-9 per Test belegt, AC-5 und AC-6 zusätzlich per Mutations-Gegenprobe
- [ ] `npx playwright test --list` vor und nach der Scheibe dokumentiert, keine Lade-Fehler
- [ ] Positivliste 80 Einträge, Ratschen 80/709 unverändert, Bindungstest grün
- [ ] Je gelöschter Datei eine Zeile mit Grund im PR
- [ ] Folgeticket für Config-Konsolidierung, Nachlese-Kandidaten, feat-880 AC-6 und `__dirname`-Probelauf angelegt
- [ ] CI-Ampel (6 Checks) grün, kein Produktcode geändert

## Known Limitations

- Bewusste Abweichung vom Ticket, Teil A: Die Layout-Reiter-Specs (layout-tab-vergleich, slice3, fidelity-s8d, compare-flow-navigation) werden **nicht** gelöscht. Die Ticketannahme (sie fahren `compare-editor-tab-layout` an) ist überholt: sie wurden in #2794 S3a/#2837/#2880 umgeschrieben und laufen gegen den aktuellen Stand. Löschen würde einzigartige Zusicherungen vernichten (slice3: Create-POST mit 5 Slot-Feldern + `official_warnings`, in hub-anlegen-ablauf nicht vorhanden; s8d: Orte-Fälle mobil). Die Testid `compare-editor-tab-layout` ist im Quellcode nicht mehr vorhanden; Abwesenheits-Zusicherungen bleiben.
- Bewusste Abweichung vom Ticket, Teil E: Es werden nur **verwaiste** Configs (testMatch ohne existierende Spec, ohne Verweis) gelöscht, keine Konsolidierung auf ein lokales und ein Staging-Config.
- Out of Scope, Begründung: Config-Konsolidierung ändert das Staging-Auth-Verhalten (jede Scheiben-Config hat eigenes Setup und storageState) und braucht ein eigenes Ticket. Configs mit existierenden Specs (1895, 2213, 774, bundle-i, feat-1395-s3, fix-1047, fix-1350, fix-1350t3, fix-1393) sind nicht verwaist.
- Out of Scope: Nachlese-Kandidaten mit nur Testid-Evidenz (issue-943-activity-edit, trip-detail-overview-left, waypoints-editor confirm/reject, issue-407-waypoint-editor-screen mit 12 Skips, orts-gruppen-c2, orts-vergleich-c1) brauchen eine Fallprüfung je Datei; Folgeticket.
- Out of Scope: `feat-880-autosave-overlay` AC-6 (liest `staging-880.json` nur aus der Staging-Config) wird im Folgeticket mitgeprüft.
- Out of Scope: `__dirname`-in-ESM-Fälle in Configs/Setups: Playwright lädt diese über eigenen Transpiler; nur `issue-322` (Spec) fällt sicher und wird gelöscht. Weitere Fälle erst nach Probe-Lauf im Folgeticket.
- Bereits erledigt, kein Handlungsbedarf: `compare-editor-slice4`, `versand-tab-vergleich`, `issue-1093-compare-layout-crash`, `trip-edit`, `compare-alarm-config`, `compare-editor-autosave`, `fillStep4`.
- Das Nachtfenster 22:00-02:30 UTC macht den CI-Job `test` strukturell rot; Merge außerhalb dieses Fensters.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Umsetzung der bestehenden Test-Politik (veraltetes Verhalten wird gelöscht). Der neue Wächter folgt dem Muster des Python-Pendants `test_repo_path_hardcoding_ratchet.py` (#1409). Regel-Budget: neue Pflicht-Regel mit Prüfdatum 2027-02-10 (+90 Tage), danach Weiterführung oder Streichung.

## Changelog

- 2026-11-12: Erstfassung (Entwurf) aus Analyse in `docs/context/rework-2243-playwright-loeschscheibe.md`.
