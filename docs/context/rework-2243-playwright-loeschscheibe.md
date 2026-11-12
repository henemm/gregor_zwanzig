# Context: rework-2243-playwright-loeschscheibe

## Request Summary
Issue #2243 (aus Sammelprojekt #1196): Playwright-Bestand ausmisten — Specs gegen abgeschaffte
Oberflächen (Layout-Reiter #1360, 5-Schritt-Wizard #622, alte Editor-Tabs) löschen, toten
Helfercode entfernen, worktree-blinde/ESM-kaputte Specs beheben oder löschen, Config-Wildwuchs
reduzieren. Löschen nach Test-Politik (veraltetes Verhalten wird gelöscht, nicht repariert).

## Ist-Stand am origin/main 9c1ca4965 (2026-11-12) gegen die Issue-Liste

Bereits verschwunden (kein Handlungsbedarf): `compare-editor-slice4`, `versand-tab-vergleich`,
`issue-1093-compare-layout-crash`, `trip-edit`, `compare-alarm-config`, `compare-editor-autosave`.
`fillStep4` aus `helpers.ts` ebenfalls weg.

Noch vorhanden:

| Datei | Zeilen | Positivliste | Verweise von außen |
|---|---|---|---|
| e2e/layout-tab-vergleich.spec.ts | 153 | nein | playwright.1273-s4c.staging.config.ts, tests/tdd/test_compare_e2e_storagestate_migration.py |
| e2e/compare-editor-slice3.spec.ts | 292 | **ja** (Z. 499) | hub-versand-aufbau.spec.ts (Kommentar?), tests/unit/test_e2e_compare_paritaet_waechter.py, tests/refactor/test_dead_code_scheibe3.py |
| e2e/compare-editor-fidelity-s8d.spec.ts | 256 | nein (Staging-only) | playwright.1256-s8d.staging.config.ts, hub-liste-seitenrahmen/hub-anlegen-ablauf (Herkunftskommentare), compare_list_mobile_chrome.test.ts, Paritätswächter |
| e2e/compare-flow-navigation.spec.ts | 151 | nein | playwright.1256-s2.staging.config.ts, mehrere hub-*.spec.ts (Herkunftskommentare), step2_orte_library_grouping.test.ts, Paritätswächter |
| e2e/issue-264-stage-sort.spec.ts | 117 | nein | — (importiert fillStep1) |
| e2e/issue-296-profile-editor.spec.ts | 256 | nein | — |
| e2e/issue-675-stage-start-time.spec.ts | 116 | nein | playwright.675.config.ts |
| e2e/orts-vergleich-c4.spec.ts | 87 | nein | — |
| e2e/issue-592-593-trips-navigation.spec.ts | 118 | nein | — (readFileSync auf Hauptrepo-Pfad Z. 45/51) |
| e2e/feat-880-autosave-overlay.spec.ts | 262 | nein | playwright.880.staging.config.ts |

Testid `compare-editor-tab-layout` existiert im Quellcode nicht mehr; im e2e-Bestand nur noch in
`hub-anlegen-ablauf.spec.ts` (vermutlich Abwesenheits-Zusicherung — prüfen).

Weitere Altlast-Treffer (`edit-tabs`/`wizard-next`/„Etappen speichern"), über die Issue-Liste
hinaus: `epic-138-metriken-editor` (nur describe.skip), `issue-758-save-indicator`,
`issue-498-stage-date-autosave`, `trip-detail-region`, `trips.spec.ts`, `helpers.ts` — in der
Analyse je Datei klären, ob Altlast oder Abwesenheits-Zusicherung.

### Toter Helfercode
`frontend/e2e/helpers.ts`: `fillStep1` (Z. 343, einziger Nutzer issue-264), `fillStep2` (Z. 367),
`fillStep3` (Z. 395) ohne Aufrufer. Fällt issue-264, ist `fillStep1` ebenfalls tot.

### Fest verdrahtete Hauptrepo-Pfade (Code, nicht Kommentar)
`issue-592-593-trips-navigation` (Z. 45/51), `list-routes-btn-migration` (Z. 26),
`forms-dialogs-btn-migration` (Z. 31), `trip-header-btn-migration` (Z. 49),
`admin-nutzerverwaltung.staging.setup` (Z. 20, staging_admin.env — legitim: Credential-Ort),
`fix-2213-bauliche-aenderung.staging.setup` (Z. 12, Staging-.env — legitim).
Darüber hinaus viele Treffer nur in Kommentaren. Python hat `test_repo_path_hardcoding_ratchet.py`,
TypeScript keinen Wächter.

### `__dirname` in ESM
Rund 50 Dateien (überwiegend `*.staging.setup.ts` und `playwright.*.staging.config.ts`). Playwright
transpiliert Configs/Setups selbst (eigener Loader) — dort kann `__dirname` funktionieren; nur echte
Specs wie `issue-322-wicon-komponente.spec.ts` fallen sicher. In der Analyse mit einem
Probe-Lauf (`--list`) je Kategorie belegen statt vermuten.

### Configs
63 getrackte `playwright*.config.ts` (37 unter `frontend/`, 26 unter `frontend/e2e/`).
Dauerhaft genutzt: `playwright.config.ts` (CI-Haupt-/PWA-/Ratelimit-Lauf), `playwright.staging.config.ts`,
`playwright.703.config.ts` (Ratelimit-Lauf? prüfen), `playwright.mobile-usability*`/`mobile-ux.local`
(#2601), `playwright.elementliste.*` (ADR-0112 Bildprüfung). Der Rest sind Scheiben-Configs.
Verweise aus Skripten/Hooks/Doku (`.claude/hooks`, `scripts/`, `docs/`) vor dem Löschen je Config prüfen.

## Existing Patterns
- Positivliste `.github/ci_e2e_specs.txt` + Filter in `ci.yml` (~Z. 334). Ratsche:
  `E2E_MIN_SPECS: 80` (EXAKT = Zeilenzahl `^e2e/`), `E2E_MIN_EXECUTED_HAUPT: 709` (Fallzahl,
  45 unter Messwert). Bindung bewacht `tests/unit/test_e2e_positivliste_ratschen_bindung.py`.
  Frühere Löschscheiben (PR #2495, #2347 S3a/S4) haben beide Zahlen abgesenkt und per
  `npx playwright test --list` direkt nachgemessen — das ist das etablierte Vorgehen.
- Paritätswächter `tests/unit/test_e2e_compare_paritaet_waechter.py` und
  `tests/refactor/test_dead_code_scheibe3.py` nennen slice3/s8d/flow-navigation namentlich —
  beim Löschen mitziehen.
- `tests/tdd/test_compare_e2e_storagestate_migration.py` verweist auf layout-tab-vergleich.

## Dependencies
- Upstream: Playwright-Runner, `helpers.ts`, Staging-Setups.
- Downstream: CI-Job `e2e`, Positivliste/Ratsche, Python-Wächtertests, Staging-Configs
  einzelner Scheiben, ggf. Doku (`docs/reference/gates_und_ratschen.md`, Specs).

## Existing Specs
- `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` (Positivliste/Ampel)
- `docs/specs/modules/fix_1771_s3_e2e_listen_wachstum.md`
- `docs/specs/modules/fix_1196_s1_testnetz_entrauschen.md` (Sammelprojekt)
- `docs/specs/modules/feat_2347_s4_paritaets_e2e.md` (Muster einer Löschscheibe)

## Risks & Considerations
- Ratsche: Entfernen von `compare-editor-slice3` senkt Dateizahl (80→79) und Fallzahl; beides exakt
  nachmessen, sonst `e2e` rot.
- Löschen darf keine noch einzigartige Zusicherung vernichten: je Datei prüfen, ob die Aussage
  in einer hub-*-Spec weiterlebt (#2347 hat vieles übernommen).
- Config-Konsolidierung (Teil E) ist der größte und riskanteste Teil (Staging-Setups mit eigener
  storageState-Logik); ggf. auf „verwaiste Configs löschen" beschränken und Restkonsolidierung
  begründet abgrenzen.
- Nur Test-/Config-Dateien betroffen; Produktcode unverändert → kein Staging-Deploy-Effekt auf
  Nutzer, aber CI-`e2e` muss grün bleiben.
- Nachtfenster 22:00–02:30 UTC: `test`-Job strukturell rot (Memory).

## Analysis

### Type
Rework (Test-Bestand aufräumen) — kein Produktcode betroffen.

### Kernbefund
Die Issue-Liste ist teilweise überholt: `layout-tab-vergleich`, `compare-editor-slice3`,
`compare-editor-fidelity-s8d`, `compare-flow-navigation`, `feat-880-autosave-overlay` laufen gegen
den aktuellen Stand (umgeschrieben in #2794 S3a/#2837/#2880, `gz-eigenstaendig:`-Köpfe, dynamische
Testids über `AnlegeReiter`/`LTChannelPicker`). Löschen würde einzigartige Zusicherungen vernichten
(slice3: Create-POST mit 5 Slot-Feldern + `official_warnings`, in hub-anlegen-ablauf grep = 0;
s8d: Orte-Fälle mobil). → BEHALTEN. Positivliste bleibt unverändert ⇒ `E2E_MIN_SPECS` 80 und
`E2E_MIN_EXECUTED_HAUPT` 709 bleiben.

### Urteil je Datei
| Datei | Urteil | Grund |
|---|---|---|
| e2e/issue-264-stage-sort.spec.ts | DELETE | trip-wizard-* weg (5-Schritt-Wizard #622); Zusicherung naturalSort → Ersatz-Unit-Test |
| e2e/issue-296-profile-editor.spec.ts | DELETE | EDIT_URL nur Redirect, waypoint-confirm/reject, wp-lat/lon/ele weg; Rest lebt in issue-407, waypoints-editor, etappen-bauliche-aenderung-speichert, issue-675 |
| e2e/orts-vergleich-c4.spec.ts | DELETE | group-header weg, Tests 1/2 vakuös, Test 3 sucht abgeschaffte Fläche; API-Fall in Go-Tests |
| e2e/trip-detail-region.spec.ts | DELETE | trip-hero-*, trip-wizard-step1-*, wizard-*-btn weg; lebt in hub-kopf-aufbau, trip-hub-kopf-region-aktivitaet, hub-anlegen-ablauf AN-6 |
| e2e/topo-heroes.spec.ts | DELETE | cockpit-topbar, trip-hero, trip-wizard-* weg |
| e2e/list-routes-btn-migration.spec.ts | DELETE | reiner Quelltext-Grep mit Hauptrepo-Pfad auf nicht mehr existierende Dateien; ui/button physisch weg |
| e2e/issue-322-wicon-komponente.spec.ts | DELETE | AC-5 `__dirname` in ESM (ReferenceError, Z. 14), AC-4 vakuös; lief nie |
| e2e/issue-675-stage-start-time.spec.ts | MODIFY | AC-3/AC-4 klicken „Etappen speichern" (bei Auto-Save nie gerendert) → Fälle löschen; AC-1/2/5/7 bleiben |
| e2e/issue-592-593-trips-navigation.spec.ts | MODIFY | AC-1 (a.trip-link weg), AC-1b/AC-2 (readFileSync Hauptrepo) löschen; AC-3/4/13 bleiben |
| e2e/epic-138-metriken-editor.spec.ts | MODIFY | zwei describe.skip-Blöcke (AC-8 ab Z. 302, AC-9 ab Z. 375) mit toten Testids löschen |
| e2e/trip-header-btn-migration.spec.ts | MODIFY | Quelltext-Fall AC-1 mit Hauptrepo-Pfad (Z. 49) löschen, DOM-Fälle bleiben |
| e2e/forms-dialogs-btn-migration.spec.ts | MODIFY | Quelltext-Schleife AC-1 mit Hauptrepo-Pfad (Z. 31) löschen, DOM-Fälle bleiben |
| e2e/helpers.ts | MODIFY | fillStep1/2/3 + Step1/2/3Input (ca. Z. 326-436) löschen, nach issue-264 |
| e2e/compare-editor-slice3.spec.ts | MODIFY (Kopf) | Kopfkommentar „fällt mit #2243 ersatzlos" ist falsch → „bleibt eigenständig (Create-POST)" |
| frontend/playwright.fix-923b.staging.config.ts + e2e/fix-923b-wire-live-sms-preview.staging.setup.ts | DELETE | testMatch-Spec existiert nicht, keine Verweise |
| frontend/playwright.1272.staging.config.ts | DELETE | testMatch `sortable-list-shared.spec.ts` existiert nicht |
| .github/ci_e2e_specs.txt (Kopf Z. 8-17) | MODIFY | Ausschluss-Kommentare zu list-routes-btn-migration/issue-322 kürzen (nur Kommentar) |
| Unit-Test für naturalSort (neben naturalSort-Quelle) | CREATE | Ersatz für issue-264-Zusicherung (KHW_03/01/00a-Namen); Runner ist `node --test`, kein Vitest |
| tests/unit/test_ts_repo_path_hardcoding.py | CREATE | TS-Pendant zu tests/tdd/test_repo_path_hardcoding_ratchet.py: scannt frontend/e2e/**/*.ts nach Hauptrepo-Pfad, Kommentare ignoriert, Ausnahme `// gz-main-path: <Grund>` (admin-nutzerverwaltung.staging.setup Z. 20, fix-2213-bauliche-aenderung.staging.setup Z. 12) |

BEHALTEN ohne Änderung: layout-tab-vergleich, compare-editor-fidelity-s8d, compare-flow-navigation,
feat-880-autosave-overlay, issue-758-save-indicator, issue-498-stage-date-autosave, trips.spec.ts
(Fehlalarme waren dynamische Testids bzw. Abwesenheits-Zusicherungen).

### Mitzieh-Stellen
- Python-Wächter (paritaet_waechter, dead_code_scheibe3, storagestate_migration, positivliste_ratschen_bindung): keine Änderung, da keine dort genannte Datei fällt.
- ci.yml Ratschen: unverändert; trotzdem `npx playwright test --list` vor/nach dokumentieren.
- `.claude/`, `scripts/`: keine Verweise auf Löschkandidaten.
- docs/: nur historische Spec-/Kontext-Erwähnungen, nicht anfassen.

### Scope Assessment
- Dateien: ~10 gelöscht, ~8 geändert, 2 neu
- LoC: ca. -1000 / +80
- Risk Level: LOW (nur Test-/Config-Dateien, Positivliste und Ratschen unberührt)

### Technical Approach
Reihenfolge: (1) Specs löschen/kürzen, (2) helpers.ts-Helfer entfernen, (3) naturalSort-Unit-Test,
(4) verwaiste Configs + Setup löschen, Positivlisten-Kopf nachziehen, (5) TS-Pfadwächter (rot gegen
Synthetikfall, grün nach Schritt 1), (6) `npx playwright test --list`, betroffene Python-Testdateien
benannt ausführen, Frontend-Unit-Tests.

### Abgrenzung (eigene Folgetickets)
- Config-Konsolidierung auf ein lokales + ein Staging-Config (Issue-Ziel E): jede Scheiben-Config hat
  eigenes Setup/storageState; Zusammenlegen ändert Staging-Auth-Verhalten → eigenes Ticket.
- Configs ohne externen Verweis, aber mit existierenden Specs (1895, 2213, 774, bundle-i,
  feat-1395-s3, fix-1047, fix-1350, fix-1350t3, fix-1393): nicht verwaist → Konsolidierungs-Ticket.
- Nachlese-Kandidaten mit nur Testid-Evidenz: issue-943-activity-edit, trip-detail-overview-left,
  waypoints-editor (confirm/reject), issue-407-waypoint-editor-screen (12 Skips),
  orts-gruppen-c2, orts-vergleich-c1 → Folgeticket mit Fallprüfung.
- feat-880 AC-6 liest staging-880.json nur aus Staging-Config → im Folgeticket mitprüfen.

### Open Questions
- keine Produktfrage; alles Tech-Lead-Entscheidung nach Test-Politik.
