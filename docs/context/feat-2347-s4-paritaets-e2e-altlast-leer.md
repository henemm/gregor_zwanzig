# Context: feat-2347-s4-paritaets-e2e-altlast-leer

## Request Summary
Epic #2347 (Paritäts-E2E), Slice S4: Die Altlast-Liste `ALTLAST` im Paritäts-Wächter (14 Compare-Specs ohne Trip-Pendant) auf leer bringen. Je Datei: (a) in kind-parametrisierten `hub-*`-Spec zusammenführen, (b) löschen, wenn tot, (c) `gz-eigenstaendig:`-Kopf (nur Orte-Tab, transponierte Übersicht, Compare-Mail). Dazu die #2243-Leiche `trip-edit.spec.ts`. Reine Testschicht, kein Produktcode erwartet.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | `ALTLAST` (Z. 50-66), `ALTLAST_MAX = 14` (Z. 71, muss gleich `len(ALTLAST)` sein), Kommentarblock Z. 38-49; `test_echter_baum_ist_nicht_leer` fordert mind. 10 compare-Dateien (Risiko nach Löschungen) |
| `.github/ci_e2e_specs.txt` | Ratsche; nur 3 der 14 stehen drin: compare-detail-edit-entry, compare-editor-slice1, compare-legacy-fields-survive-save |
| `.github/workflows/ci.yml:285-286` | `E2E_MIN_SPECS: 73`, `E2E_MIN_EXECUTED_HAUPT: 549` (Handpflege, neu messen) |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | fordert Gleichheit MIN_SPECS = Zeilenzahl der Liste |
| `.github/scripts/e2e_gate.py` (Z. 404) | Gate-Logik |
| `docs/reference/gates_und_ratschen.md:232` | nennt noch 64/369, veraltet |
| `docs/specs/modules/feat_2347_s1..s3d_paritaets_e2e.md` | Vorgänger-Specs (Muster für S4-Spec) |
| `frontend/e2e/hub-*.spec.ts` | Ziel-Specs mit `HUB_KINDS` |
| `frontend/e2e/trip-edit.spec.ts` | #2243-Leiche: 11 Tests, Wizard-Selektoren, nicht in Ratsche, `/trips/[id]/edit` leitet laut Unit-Test um |
| `playwright.1256-s2/s8c/s8d/1461-s3b2b.staging.config.ts`, `compare-edit-redirect.staging.setup.ts`, `compare-layout-tab-dissolution.staging.setup.ts` | hängen an einzelnen Altlast-Specs, bei Löschung mitnehmen (Existenz noch zu prüfen) |

## Die 14 Altlast-Specs (Vermessung, teils nur aus Kopfzeilen — in Analyse verifizieren)
| Spec | Zeilen/Tests | Ratsche | Fläche | Erstempfehlung |
|---|---|---|---|---|
| compare-alarm-config | 125/4 | nein | /compare/[id] Alarme | a (hub-alarme-*) oder b |
| compare-detail-edit-entry | 141/5 | JA | /compare/[id] Mobil, Draft | a, sonst c |
| compare-edit-redirect | 98/2 | nein | /compare/[id]/edit → Detail | a oder b (Trip hat nur Unit-Test) |
| compare-editor-fidelity-s8d | 507/27 | nein | /compare/new Desktop/Mobil | b/a, erst Tote prüfen |
| compare-editor-slice1 | 88/7 | JA | /compare/new Gerüst | c oder b |
| compare-editor-slice4 | 275/8 | nein | /compare/new Aktivieren-Gate, Create-POST | c oder a |
| compare-flow-navigation | 821/31 | nein | Liste, new, Detail | a teils b, größter Brocken |
| compare-hub-fidelity-s8c | 328/30 | nein | /compare/[id] Rahmen | a oder b (Layout-Tab abgeschafft #1360) |
| compare-layout-tab-dissolution | 426/9 | nein | Wetter-Metriken | a/b, 2 Fälle schon rot (AC-2, AC-6) |
| compare-legacy-fields-survive-save | 136/3 | JA | hour_from/hour_to/forecast_hours | c |
| compare-new-vorlage | 148/4 | nein | /compare/new?from= | a falls /trips/new?from= existiert, sonst c |
| feat-1461-s3b2b-compare-kanal-schwelle | 596/10 | nein | Alarme/Etappen, hat Trip-Teile | a |
| issue-1080-compare-new-url | 169/5 | nein | Smart-Import Orte | c oder b |
| issue-1093-compare-layout-crash | 71/1 | nein | Layout-Crash, Fläche tot (belegt: `step4-loading` fehlt in src) | b |

## Existing Patterns
- Paritäts-Wächter im Ratschenmodus: `ALTLAST` darf nur schrumpfen, `ALTLAST_MAX` literal und gleich `len(ALTLAST)` (S3a F001).
- Zusammenführen: Altfälle 1:1 in `hub-*`-Spec mit `HUB_KINDS`, nichts abschwächen; Mutations-Gegenprobe je kind (S3a-S3d).
- Eigenständigkeit: `gz-eigenstaendig:`-Kopf in den ersten 30 Zeilen, Begründung mind. 15 Zeichen.
- Ratsche: Spec-Anzahl und ausgeführte Fälle neu messen (`playwright test --list`).

## Dependencies
- Upstream: Playwright-Config, CI-Positivliste, Fixtures (Test-Trip/Test-Vergleich).
- Downstream: CI-Job `e2e`, Wächter-Test, `docs/reference/gates_und_ratschen.md`.

## Existing Specs
- `docs/specs/modules/feat_2347_s3d_paritaets_e2e.md` (jüngste Vorlage)

## Risks & Considerations
- 7 Tests auf Staging vorbestehend rot (compare-outlook AC-1/AC-8, compare-layout-tab-dissolution AC-1/2/6, layout-tab-vergleich AC-7/AC-11); gehören zu S4 bzw. #1196.
- `test_echter_baum_ist_nicht_leer` (mind. 10 compare-Dateien) kann nach Streichungen reißen; Schwelle anpassen.
- Tot-Einschätzungen beruhen auf Kopfzeilen, nicht auf Läufen: vor Löschung je Datei Fläche und Abdeckung belegen (nichts still abschwächen).
- Nicht-compare-benannte Specs (issue-682-compare-editor-mobile, fix-1350-*) sind ungeprüft gegen Regel 2.
- `e2e`-CI-Lauf dauert ~17 min; lokal Registrierungsbremse (siehe S3a AC-10).
- S4 darf kein Produktcode sein; stößt ein Trip-Pendant rot auf, gilt AC-13-Regel (Produktfix im Slice).

## Analysis

### Type
Feature (reine Testschicht, kein Produktcode; AC-13-Regel: rotes Trip-Pendant ⇒ Produktfix im Slice).

### Quellen
3 Read-only-Analyse-Agenten (Gruppe A/B/C, 2026-10-30), per grep/ls, nicht durch Läufe belegt. "Fläche tot" und "Abdeckung anderswo" sind vor jeder Löschung je Fall nachzuprüfen (Testnamen in Ziel-Specs lesen).

### Klassifikation (Empfehlung)
| Spec | Empfehlung | Anmerkung |
|---|---|---|
| issue-1093-compare-layout-crash | b löschen | Fläche tot (`Step4Layout`/`LayoutPreview` 0 Treffer in .svelte); Config+Setup mit; `issue-1093-unit.spec.ts` (ci_e2e_specs.txt:504) separat entscheiden |
| compare-layout-tab-dissolution | b löschen; AC-3 (?tab=layout) vorher nach `hub-reiter-alt-kennungen-umleitung` | Layout-Tab tot, 2 Fälle schon rot; Config+Setup mit |
| trip-edit (#2243-Leiche) | b löschen | `/edit` leitet um (Unit-Test); Hub-Abdeckung hub-tab-bar / hub-*-speichert-selbst |
| compare-edit-redirect | a: 1 Fall `/${kind}/{id}/edit` in `hub-reiter-alt-kennungen-umleitung` | Setup mit |
| compare-alarm-config | b | durch hub-alarme-wertprops AW-4 + hub-alarme-speichert-selbst gedeckt (Stichprobe); testMatch in playwright.1273-s4c anpassen |
| compare-detail-edit-entry | b | hub-list-menu LM-1/LM-5; ci_e2e_specs.txt:468 mit raus |
| compare-legacy-fields-survive-save | a nach `hub-kopf-bearbeiten` (Roundtrip hour_from/hour_to/forecast_hours) | ci_e2e_specs.txt:472 Eintrag-Tausch; Kernschutz, nicht ersatzlos |
| compare-hub-fidelity-s8c | gemischt: a (mobiler Chevron-Stack, Status-Kurzform, Versand-Karte) → hub-tab-bar/hub-versand-*; Rest b; Orte-Texte c | Config+Setup mit |
| feat-1461-s3b2b | gemischt: a (Kanal-Schwelle je kind → hub-alarme-speichert-selbst; Anlege-Fälle → Anlege-Spec), Rest b | AS-1 vorher gegen AC-15 lesen; Config+Setup mit |
| compare-new-vorlage | a: kind-parametrisierter Anlege-Spec (`/trips/new?from=` existiert, #559, ohne „(Kopie)“-Suffix ⇒ Fall je kind anpassen) | AC-6 Cross-User, AC-11 Mobil |
| compare-editor-slice1 / slice4 / fidelity-s8d / flow-navigation (Create-Teile) | a: `/compare/new` ist laut CLAUDE.md Trip-Muster (`TripNewEditor`) ⇒ kind-parametrisierter `hub-anlegen-*`-Spec | Agent behauptet „Trip-Anlegen hat Wizard“ – gegen `/trips/new` prüfen. Tote Teile (Layout-Tab, channel_layouts, compare-step4-layout-preview) b. Fälle ohne Abdeckung nicht still löschen |
| issue-1080-compare-new-url | c (`gz-eigenstaendig:`, Orte-Tab) | Step2Orte lebt |
| flow-navigation (17 Fälle, nicht 31) | Klickpfade/Kebab b (LM-1/9/10/8); Breadcrumb-Klick, „Bearbeiten →“ a; Orte-Fidelity c | Config playwright.1256-s2 |

### Affected Files
| File | Change |
|---|---|
| frontend/e2e: 14 Altlast-Specs + trip-edit | DELETE bzw. Fälle MERGE |
| hub-alarme-speichert-selbst, hub-tab-bar, hub-kopf-bearbeiten/-aufbau, hub-versand-*, hub-reiter-alt-kennungen-umleitung | MODIFY (kind-Fälle) |
| hub-anlegen-*.spec.ts | CREATE (HUB_KINDS) |
| 6 playwright-Configs + Setups (1256-s8c, 1256-s8d, 1461-s3b2b, 1080, 1093, layout-tab-dissolution) | DELETE; 1273-s4c testMatch anpassen |
| tests/unit/test_e2e_compare_paritaet_waechter.py | ALTLAST leeren, ALTLAST_MAX = len im selben Zug; Schwelle in test_echter_baum_ist_nicht_leer (≥10) anpassen |
| .github/ci_e2e_specs.txt, ci.yml:285-286 (73 / 549), test_e2e_positivliste_ratschen_bindung.py | per `playwright test --list` neu messen; Einträge 468/469/472/504, Kommentare 130/166/191/192 bereinigen |
| docs/reference/gates_und_ratschen.md:232 | veraltete Zahlen |
| Spec-Namen-Referenzen: test_compare_e2e_storagestate_migration.py, test_bug590_signal_removal_telegram_start.py, test_compare_alert_channel_threshold.py, e2e_frontend_browser_gate.py, feat_1558_frontend_browser_gate.md, operations_playbook.md | prüfen/nachziehen |

### Scope Assessment
- Files: ca. 15 DELETE, ca. 8 MODIFY, 1–2 CREATE, 6 Configs+Setups DELETE, 4–5 Ratschen-/Doku-Dateien
- LoC: netto stark negativ (ca. −4000), +400–600 neu
- Risk: MEDIUM — stilles Abschwächen möglich, Ratschen-Zahlen müssen exakt stimmen, CI-e2e ~17 min
- Empfehlung: Schnitt in S4a (Löschungen b + c-Köpfe + Wächter/Ratschen), S4b (Anlege-Spec), S4c (Merges in hub-*), da ein Slice das LoC-Limit sprengt.

### Technical Approach
Je Datei: Fall lesen → Ziel-Fall in kind-parametrisiertem Spec belegen (Name+Zeile) → Mutations-Gegenprobe je kind → erst dann Altdatei löschen. ALTLAST und ALTLAST_MAX im selben Commit schrumpfen. Ratsche am Ende messen.

### Dependencies
Fixtures Test-Trip/Test-Vergleich; CI-Job `e2e`; Wächter-Test.

### Open Questions
- [ ] Ein Slice oder Schnitt S4a/b/c (technisch, wird in der Spec entschieden)
- [ ] `/trips/new` vs. `/compare/new`: gleiche Selektoren? (entscheidet Parametrisierbarkeit des Anlege-Specs)
- [ ] `issue-1093-unit.spec.ts` löschen (toter `layoutPreviewRows.ts`)?
- [ ] 7 vorbestehend rote Staging-Tests (compare-outlook AC-1/8, layout-tab-dissolution, layout-tab-vergleich AC-7/11) gehören zu S4 bzw. #1196
