# Context: feat-2347-s3c-paritaets-e2e

## Request Summary
#2347 Scheibe S3c (Epic #2345, Etappe P6): Die Zwei-Kontexte-Konfliktspec `compare-konfliktschutz-zwei-kontexte.spec.ts` (nur Ortsvergleich, 394 Zeilen, ALTLAST) wird eine geteilte `hub-*`-Spec, die dieselbe Zusicherung per `for (const kind of HUB_KINDS)` für Trip UND Ortsvergleich prüft. Das Trip-Pendant ist erstmals gemessen (bisher nur `feat-1395-s4-conflict-retry.staging.spec.ts`, ein einzelner Fall gegen Staging).

## Related Files
| File | Relevanz |
|------|----------|
| `frontend/e2e/compare-konfliktschutz-zwei-kontexte.spec.ts` | Quelle: Test 9 (Alarme/Wertebereiche/Versand/Wetter-Metriken je Reiter + Orte), Test 10 (#2381 selber Tab), Test 11a (Pausieren im Hub), 11b (Pausieren auf Listenseite) |
| `frontend/e2e/hub-versand-speichert-selbst.spec.ts` | Muster: kind-Schleife, VS-2 = 412 → „Nochmal speichern" je kind, `zaehlePuts`, `seedHub`, `HUB_SEL` |
| `frontend/e2e/helpers.ts:590-720` | `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath` |
| `frontend/e2e/feat-1395-s4-conflict-retry.staging.spec.ts` (+ `.setup.ts`) | Trip-412-Retry nur gegen Staging, 1 Fall; Zuordnung zu S3c oder S3d (`.staging`) klären |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | ALTLAST 30 → ALTLAST_MAX literal; Eintrag streichen + Max senken im selben Zug |
| `.github/ci_e2e_specs.txt` (Z. ~293 Aufnahme, Z. 420 Eintrag) | Ratsche; Spec umbenennen/ersetzen, `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` neu messen |
| `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` | Ursprungs-Spec (#2375/#2381), ACs der Altspec |
| `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md` | Trip-Pendant im Produkt (#1433), `meldeKonflikt`, Teilfeld-Nutzlasten |
| `docs/specs/modules/feat_2347_s3b_paritaets_e2e.md` | Format-/Zuordnungsvorlage für die S3c-Spec |

## Existing Patterns
- Geteilte Spec: `for (const kind of HUB_KINDS)`, kind-Kontraste in einer Tabelle, Zweige je mit Begründung; kein Zweig wird übersprungen (WW-4).
- Zweiter Kontext = neuer Browser-Kontext mit DEMSELBEN `storageState` (kein zweiter Login, 429-Bremse).
- Warten nur `expect.poll`/`toHaveAttribute`; keine festen Wartezeiten (Filter A der CI-Positivliste).
- Wächter-Ratsche: ALTLAST darf nur schrumpfen, `ALTLAST_MAX` ist Literal; Mutations-Gegenprobe je kind Pflicht.

## Kind-Kontraste (am Code gemessen)
- **Pausieren:** Trip schreibt `setPaused('trip', id, paused)` = `PATCH /api/trips/{id}/state` (kein If-Match → kein 412 beim Pausieren; Trip-Seite flusht zuvor `tripSaveCtl`). Vergleich: PUT `{schedule, previous_schedule}` mit If-Match → 412 → „Nochmal speichern". Test 11a muss je kind seine EIGENE Zusicherung prüfen (Trip: Name von A bleibt, `paused` true, kein Datenverlust; Vergleich: unverändert).
- **Reiter-Kennungen:** `trip-detail-tab-*` vs. `compare-detail-tab-*` (über `HUB_SEL`). Trip-Reiter-Änderungen schreiben `{report_config…}` per PUT `/api/trips/{id}`; Vergleich Teilfelder per PUT `/api/compare/presets/{id}`.
- **Compare-eigen (gz-eigenstaendig:)**: Test 9 (Orte) – Orte-Tab ist eine der drei erlaubten Compare-Eigenheiten (Trip-Pendant „Etappen" hat andere Gesten); Test 11b (Listenseite `/compare`, roher fetch) – ggf. Trip-Pendant `/trips`-Listenmenü prüfen.
- **Offen für /20-analyse:** Trip-Hub-Reiter für Test 9 (Alarme, Wertebereiche, Versand, Wetter-Metriken je Trip-Selektor), Namens-Edit im Trip-Kopf (`HUB_SEL.kopf` = `trip`), Trip-Pendant zu „Orte entfernen" (Etappe?), Trip-Seed hat nur 1 Etappe.

## Dependencies
- Upstream: `saveStatusStore.svelte.ts` (`retryConflict`, Konflikt-Sperre), `etagRegistry.ts` (`markiereKonflikt`), `api.ts` (If-Match, 412), `shared/pickEigenfelder.ts`, `tripSpeicherung.ts`, `CompareTabs.svelte`.
- Downstream: CI-Ratsche (`e2e`-Job), Paritäts-Wächter, Folgescheiben S3d/S4.

## Risiken
- Trip-Fälle könnten rot werden (Produktlücke, AC-13: im selben Ticket beheben, Muster S2).
- Konflikt-Schutz zeigt nur in Zwei-Kontexte-Tests Wirkung (Lehre #2381: 200 OK mit veraltetem Körper); Mutations-Gegenprobe an der Stelle, an der die Zusicherung wirkt (Teilfeld-Nutzlast, If-Match), nicht nur am Test.
- `ci_e2e_specs.txt` ist Konfliktpunkt: Scheiben strikt nacheinander; Basis hinter `origin/main` prüfen (#2266 ist neu auf main).
- Basis-Branch `worktree-s3a-2347` steht auf `c3c7fcc72`, `origin/main` hat 1 neuen Merge (#2631) → vor Commit rebasen/ff.
- Lokal Registrierungsbremse bei Zweitnutzer-Fixtures; Läufe im CI-Stack (3× grün erst im CI-Hauptlauf).
- `feat-1395-s4` ist `.staging` und gehört laut S3b-Spec zu S3d – nicht still in S3c ziehen.

## Existing Specs
- `docs/specs/modules/feat_2347_s1…s3b_paritaets_e2e.md`, `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md`, `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md`

## Analysis

### Type
Feature (reine Testinfrastruktur, kein Produktcode geplant; Produktfix nur falls ein Trip-Fall rot wird, AC-13).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` | CREATE | Geteilte Spec, `for (const kind of HUB_KINDS)`: Test 9 je Reiter (Alarme, Wertebereiche, Versand, Wetter-Metriken), Test 10 (#2381), Test 11a (Pausieren im Hub), Test 11b (Listen-Kebab) |
| `frontend/e2e/compare-konfliktschutz-zwei-kontexte.spec.ts` | MODIFY/DELETE | Alle kind-neutralen Teile raus; verbleibt nur Test 9 (Orte) mit `gz-eigenstaendig:`-Kopf (oder in eigene Datei) |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | ALTLAST 30 → 29 oder 30 (je nachdem ob die Orte-Datei bleibt), `ALTLAST_MAX` im selben Zug |
| `.github/ci_e2e_specs.txt` | MODIFY | Neue Spec aufnehmen, Alt-Eintrag ersetzen, `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` neu messen |
| `docs/specs/modules/feat_2347_s3c_paritaets_e2e.md` | CREATE | Spec mit Kind-Kontrast-Tabelle |

### Scope Assessment
- Files: 5 (+1 Spec). Estimated LoC: +~450 / −~330 (Test-Code). Risk: MEDIUM
  (Trip-Fälle erstmals gemessen; Zweit-Kontext-Aufbau; Ratsche als Konfliktpunkt).

### Technical Approach
- Muster `hub-versand-speichert-selbst.spec.ts` (VS-2: 412 → „Nochmal speichern" je kind) + `seedHub`/`openHub`/`HUB_SEL`/`hubApiPath`. Zweiter Kontext = neuer Browser-Kontext mit demselben `storageState`.
- **Kind-Kontraste (am Code gemessen):**
  - Reiter-Schreibweg: Trip PUT `/api/trips/{id}` mit Teilfeld `{report_config…}` / Alarme / display_config (`tripSpeicherung.ts`); Vergleich PUT `/api/compare/presets/{id}` mit Teilfeldern (`*VergleichSpeicherung.ts`). Die „Änderung von B fehlt auf dem Server"-Prüfung ist daher je kind eine eigene Feld-Zuordnung (Tabelle in der Spec), nicht derselbe Feldname.
  - Reiter-Selektoren: Alarme `alarme-tab` geteilt; Wertebereiche `corridor-editor-{context}` (route/vergleich); Wetter-Metriken `weather-metrics-tab-{context}`; Versand-Zeit `report-morning-time` — Trip-Selektoren aus den bestehenden `hub-*-speichert-selbst`-Specs übernehmen (dort bereits je kind belegt).
  - Pausieren: Trip = `tripSaveCtl.flush()` dann `PATCH /api/trips/{id}/state` OHNE If-Match ⇒ kein 412. Test 11a ist daher je kind verschieden: Vergleich 412 → Retry (`{schedule, previous_schedule}`); Trip prüft stattdessen „Name von A bleibt, `paused` true, kein Datenverlust" (eigene Zusicherung, kein Skip).
  - Test 11b: Trip-Pendant `/trips`-Listenmenü existiert (`togglePause` → `setPaused('trip', …)`); Vergleichs-Listenpfad nutzt laut Altspec rohen PUT. Beide in der Spec je kind benennen; Zusicherung „Name von A bleibt" gilt für beide.
  - Test 9 (Orte): Compare-eigen (Orte-Tab) → `gz-eigenstaendig:`; Trip-Pendant „Etappen" hat andere Gesten und ist kein Konfliktschutz-Teilfeld des Vergleichs → keine Parität erzwingen, Begründung in der Spec.
- Namens-Edit in A: `HUB_SEL.kopf` (`name-edit-toggle`, siehe `hub-kopf-bearbeiten.spec.ts`) gilt für beide kinds; Kopf-PUT trägt je kind nur `{name}` (KB-4) — Test 10 (#2381) je kind.
- Mutations-Gegenprobe je kind (Pflicht): Teilfeld-Nutzlast verfälschen (Vollobjekt statt Teilfeld) und If-Match weglassen; je Mutation muss genau der kind-Fall rot werden.

### Dependencies
- Upstream: `saveStatusStore.svelte.ts` (`retryConflict`), `etagRegistry.ts`, `api.ts` (If-Match/412), `tripSpeicherung.ts`, `*VergleichSpeicherung.ts`, `CompareTabs.svelte`.
- Downstream: CI-Ratsche (`e2e`), Paritäts-Wächter, S3d/S4.

### Open Questions
- [ ] Trip-Fall rot (z. B. Trip-Reiter ohne 412-Weg)? → AC-13: im selben Ticket beheben (erst Messung).
- [ ] `feat-1395-s4-conflict-retry.staging.spec.ts` bleibt bei S3d (laut S3b-Spec) — nicht in S3c ziehen.
- [ ] Verbleibende Orte-Datei: umbenennen (`compare-orte-konfliktschutz…`) mit `gz-eigenstaendig:`, ALTLAST dann −1 durch Ersatz.
- [ ] Basis hinter `origin/main` (#2631): vor Commit `git merge --ff-only origin/main`.
