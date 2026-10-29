# Context: feat-2347-s3d-paritaets-e2e

## Request Summary
#2347 (Epic #2345, P6) Scheibe S3d: der "compare-eigene Rest" der Paritäts-E2E-Umstellung. Ziel wie S1–S3c: jede Compare-Spec ist entweder kind-parametrisiert (Trip + Ortsvergleich, `HUB_KINDS`) oder trägt einen `gz-eigenstaendig:`-Kopf mit Begründung; ALTLAST schrumpft. Reine Testschicht, kein Produktcode.

## Stand (origin/main e2eefbdc0, S3c live 29.10.)
- Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`: `ALTLAST` = 29 (28 × Regel 1, 1 × Regel 2), `ALTLAST_MAX = 29` (Literal, muss == len(ALTLAST) sein), Prüfdatum 2027-01-24.
- Ratsche in `.github/workflows/ci.yml` Z. 285/286: `E2E_MIN_SPECS: 72`, `E2E_MIN_EXECUTED_HAUPT: 535`; Positivliste `.github/ci_e2e_specs.txt` (545 Zeilen).
- Vorbilder: `frontend/e2e/hub-*.spec.ts` (20 Dateien), jüngste Spec `docs/specs/modules/feat_2347_s3c_paritaets_e2e.md`, Muster `daywindow-shared-both-contexts`.

## S3d-Umfang laut S3c-Spec (Z. 43) + Issue
Radar, Stundenverlauf, Hourly-Order, 682-Mobile, `compare-hub-inline-edit`, `compare-editor-autosave`, **alle `.staging`-Specs inkl. `feat-1395-s4-conflict-retry.staging.spec.ts`** (+ `.setup.ts`; Trip-412-Retry, 31 Trip-Erwähnungen; S3c misst ihre Zusicherung zusätzlich im CI-Stack, ersetzt sie nicht).

## Betroffene Dateien (frontend/e2e)
| Datei | Zeilen | Fälle | In CI-Positivliste |
|---|---|---|---|
| compare-radar-toggle | 150 | 3 | ja (Z. 445) |
| compare-stundenverlauf-wertprops | 249 | 4 | ja (Z. 446) |
| compare-hourly-metric-order | 456 | 3 | nein |
| issue-682-compare-editor-mobile | 217 | 6 | ja (Z. 487) |
| compare-hub-inline-edit | 171 | 3 | ja (Z. 442; nur Orte-Teil übrig) |
| compare-editor-autosave | 479 | 10 | nein |
| compare-metric-order | 249 | 2 | nein (Nachbar zu Hourly-Order) |

`.staging`-Specs (nur Staging, nie CI): compare-active-metrics-format (365 Z.), compare-neu-kanal-anlegen (210), compare-outlook-metric-selection (652), compare-uebersicht-kanal-bedienung (101), compare-uebersicht-kanal-persistenz (136), fix-1350-compare-metric-select (289), fix-1350t3-compare-threshold-source (182), kanal-grenzen-ortsvergleich (207, Regel 2), feat-1395-s4-conflict-retry (215).

Übrige ALTLAST (S4-Kandidaten, nicht S3d): alarm-config, detail-edit-entry, edit-redirect, editor-fidelity-s8d, slice1, slice4, flow-navigation, hub-fidelity-s8c, layout-tab-dissolution, legacy-fields-survive-save, new-vorlage, feat-1461-s3b2b, issue-1080, issue-1093.

## Risiken / Hinweise
- `.staging`-Specs laufen nur gegen Staging (Basic-Auth, Admin- und Datenzugriffs-Fallen). Nach Zusammenführung in CI-fähige hub-Specs gilt: Zusicherung nicht abgeschwächt, Mutations-Gegenprobe je kind.
- Ratsche: `E2E_MIN_EXECUTED_HAUPT` per `npx playwright test --list` nachmessen, nie addieren; `E2E_MIN_SPECS` per `grep -c '^e2e/'`.
- Wächter-Regeln: kind-Schleife `HUB_KINDS` oder `gz-eigenstaendig:`-Kopf (≥ 15 Zeichen, in den ersten 30 Zeilen); Regel 2 gilt für Nicht-compare-Dateinamen mit `compare-detail-tab`.
- Registrierungsbremse 5/h/IP begrenzt lokale 3×-Läufe (AC-10 aus S3a blieb AMBIGUOUS).
- Umfang groß (~16 Dateien, ~4,5k Zeilen): LoC zählt nur produktive Spec-Dateien. Keine Abspaltung von Resten ohne PO-Entscheid (Epic-Regel).
- Parallelsessions: keine auf #2347 (sessions: #1442, #1814).

## Analysis

### Type
Feature (reine Testschicht, kein Produktcode)

### Verifizierte Befunde (Stichprobe am Code)
- ALTLAST 29 = 15 S3d-Kandidaten + 14 S4-Reste. Nach S3d bleiben 14 (S4-Liste siehe oben). `feat-1395-s4-conflict-retry.staging` steht NICHT in ALTLAST (Wächter greift nur bei "compare" im Dateinamen oder `compare-detail-tab` im Text).
- In der CI-Positivliste stehen nur radar-toggle, stundenverlauf-wertprops, hub-inline-edit, issue-682. Löschen von hourly, metric-order, autosave und der .staging-Specs berührt `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` nicht.
- **Falle:** `tests/tdd/test_compare_e2e_storagestate_migration.py:24` führt `compare-radar-toggle.spec.ts` in `MIGRATED_FILES` (read_text auf gelöschte Datei = rot; S3b löste das per Kommentar + Entfernen). Zusätzlich Einträge in `frontend/playwright.1273-s4c.staging.config.ts` (Z. 31 autosave, Z. 35 radar).
- Pendant-Lücken (Löschen würde Zusicherung abschwächen): radar-toggle "Default aus bei neuem Preset" und "bleibt bei fremdem Speichern" nicht in `hub-alarme-wertprops` AW-2; compare-editor-autosave AC-7 (Gesten-Gate, 0 PUTs ohne Geste) und AC-8 (Navigation ohne Datenverlust) in keiner hub-Spec.
- SMS 153/140 vs 160: kein Widerspruch, kind-abhängig (Vergleich 153, Trip 160, Alarm 140). `kanal-grenzen-ortsvergleich.staging` bekommt `gz-eigenstaendig:`-Kopf mit dieser Begründung.
- Die 9 .staging-Specs sind nicht zu einer Spec bündelbar (je eigenes Setup, Config, Login-Limit); sie laufen nie im CI-Stack, ihre Mutations-Gegenprobe ist dort nicht prüfbar.
- `OutputLayoutEditor.svelte` und `shared/dnd/SortableList.svelte` sind geteilte Bausteine: die Metrik-Reihenfolge per Drag (compare-metric-order, compare-hourly-metric-order) ist deshalb vermutlich NICHT Compare-eigen (Teilungs-Invariante). In /30 am Code prüfen, ob der Trip dieselbe Reihenfolge-Geste hat; wenn ja kind-parametrisieren statt Kopf, sonst Kopf mit konkreter Begründung.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/compare-radar-toggle.spec.ts | DELETE | nach neuem Fall AW-2b (Default aus, bleibt bei fremdem Speichern) |
| frontend/e2e/compare-stundenverlauf-wertprops.spec.ts | DELETE | Fälle je Altfall auf MS-2/MS-7 zuordnen |
| frontend/e2e/compare-editor-autosave.spec.ts | DELETE/KÜRZEN | Rest in hub-*-speichert-selbst; AC-7/AC-8 in neue Spec |
| frontend/e2e/hub-alarme-wertprops.spec.ts | MODIFY | AW-2b ergänzen |
| frontend/e2e/hub-editor-autosave-gesten-gate.spec.ts | CREATE | AC-7/AC-8 je kind (HUB_KINDS) |
| frontend/e2e/compare-hourly-metric-order*, compare-metric-order* | DELETE oder MODIFY | je nach Trip-Pendant (siehe oben) |
| frontend/e2e/issue-682-compare-editor-mobile.spec.ts, compare-hub-inline-edit.spec.ts | MODIFY | `gz-eigenstaendig:`-Kopf |
| 7 weitere .staging-Specs | MODIFY | Kopf mit Begründung (neu-kanal-anlegen, uebersicht-bedienung/-persistenz, fix-1350, fix-1350t3, kanal-grenzen-ortsvergleich; active-metrics-format/outlook-metric-selection nur mit Zuordnungstabelle löschbar) |
| feat-1395-s4-conflict-retry.staging.spec.ts + .setup.ts + playwright.feat-1395-s4.staging.config.ts | DELETE | 412-Retry durch VS-2/WS-4/MS-5/KS-1 im CI-Stack gedeckt |
| tests/unit/test_e2e_compare_paritaet_waechter.py | MODIFY | ALTLAST 29 → 14, ALTLAST_MAX 14 |
| tests/tdd/test_compare_e2e_storagestate_migration.py | MODIFY | radar aus MIGRATED_FILES |
| frontend/playwright.1273-s4c.staging.config.ts | MODIFY | Einträge entfernen |
| .github/ci_e2e_specs.txt, .github/workflows/ci.yml | MODIFY | Listenzeilen, E2E_MIN_SPECS (exakt), E2E_MIN_EXECUTED_HAUPT (per `playwright test --list` nachmessen) |

### Scope Assessment
- Files: ca. 25 (ca. 16 löschen/ändern, 2 neu, Ratsche, Wächter, tdd-Test, 1273-Config)
- Estimated LoC: ca. +300 / −1900 (nur Testcode)
- Risk Level: MEDIUM (Ratsche/Wächter hängen an der CI-Ampel; Zusicherung darf nirgends abgeschwächt werden)

### Technical Approach (Empfehlung: Variante B, ein Ticket, vier AC-Gruppen)
| Variante | ALTLAST nachher | gelöscht | neu | SPECS | HAUPT (grob) | Risiko |
|---|---|---|---|---|---|---|
| A nur Köpfe | 14 | 0 | 0 | 72 | 535 | niedrig, Doppelstruktur bleibt |
| B Mitte: Löschen radar/stundenverlauf/autosave + Gesten-Gate, Rest Köpfe | 14 | ca. 6 + Setup/Config | 2 | 71 | ca. 534 | mittel |
| C alle Staging-Specs zusammenführen/löschen | 14 | ca. 14 | 3–4 | 71–72 | 534–540 | hoch (Staging-Zusicherungen unprüfbar) |
- G1: neue/erweiterte hub-Specs (AW-2b, Gesten-Gate) RED→GREEN, dann Löschungen mit Ratschen-Zug, tdd-Test und 1273-Config im selben Commit.
- G2: Köpfe auf CI-gelisteten Specs (682, inline-edit).
- G3: Köpfe/Löschungen nicht gelisteter und staging-only Specs (inkl. feat-1395-s4).
- G4: Aufräumen (Setup, Configs, Kommentar-Verweise in ci_e2e_specs.txt/hub-Specs), ALTLAST + ALTLAST_MAX gemeinsam 29 → 14, Ratsche nachmessen.
- Keine Abspaltung als eigenes Ticket.

### Dependencies
- helpers.ts (HUB_KINDS, seedHub, openHub); Ratsche-Bindung `tests/unit/test_e2e_positivliste_ratschen_bindung.py`; Wächter; Registrierungsbremse 5/h/IP begrenzt lokale 3×-Läufe.

### Open Questions
- [ ] Hat der Trip eine Metrik-Reihenfolge per Drag (geteilter `OutputLayoutEditor`)? Entscheidung kind-Schleife vs. Kopf — am Code in /30 klären, keine PO-Frage.
- [x] Tiefe der Staging-only-Specs: Köpfe mit konkreter Begründung statt Zusammenführung (technische Entscheidung, keine PO-Frage).
- [ ] Zuordnungstabelle Alt→Neu inline in der Spec (Muster S3a–S3c); `docs/artifacts/.../zuordnung-alt-neu.md` aus S3a ist nicht im Repo.
