# Context: feat-2347-paritaets-e2e

## Request Summary
Issue #2347 (Epic #2345, Etappe P6 „Ratsche"): Hub-, Anlege- und Listen-Verhalten soll per Playwright für Trip **und** Ortsvergleich mit **einem** Spec je Verhalten belegt sein (Schleife über `kind`). Compare-only bleiben nur Orte-Tab, transponierte Übersicht und Compare-Mail; jede andere Compare-Datei braucht eine `gz-eigenstaendig:`-Begründung. Die Ratsche `.github/ci_e2e_specs.txt` soll die parametrisierten Specs und keine Bestandsleichen enthalten.

Gemessen auf `9264af55f` (2026-10-26). Voraussetzungen #2276/#2277 sind erledigt.

## Befund-Korrekturen gegenüber dem Issue-Text
- **Vorbild:** `daywindow-shared-both-contexts.spec.ts` hat **keine** `kind`-Schleife (zwei handgeschriebene Fälle), verletzt Filter A (`waitForTimeout(1_500)` :140) und steht nicht in der Ratsche. **Echtes Vorbild:** `trip-hub-kopf-region-aktivitaet.spec.ts:917-935` — `for (const hub of ['Trip','Vergleich'])` mit `seedTrip`/`openTripHub` bzw. `seedPreset`/`openCompareHub`, steht in der Ratsche.
- **Versand ist kein eigener Reiter mehr** (#1743): Abschnitt `#versand` im Reiter Wetter-Metriken (`?tab=wetter-metriken#versand`, testids `versand-abschnitt`, `report-morning-time`).
- **API-Pfade:** `/api/trips/<id>` und `/api/compare/presets/<id>` (kein `/api/briefings` für PUT). Fremder Trip: `UpdateTripHandler` (`internal/handler/trip.go:358-369`) → **404** vor ETag-Prüfung — gleich wie Compare.
- **Save-Chip ist bereits geteilt:** `lib/components/ui/SaveIndicator.svelte` (`data-testid="save-indicator"`, `data-state`, `.save-time` HH:MM), nur in `shared/subscription-header/SubscriptionHeader.svelte`; eingebunden in `trip-detail/TripHeader.svelte:109` und `routes/compare/[id]/+page.svelte:352`, beide mit `createSaveStatus`.
- **AC-1 ist zur Hälfte da, aber getrennt:** Trip `trip-hub-kopf-region-aktivitaet.spec.ts:974` (AC-11), Vergleich `compare-versand-speichert-selbst.spec.ts` (AC-1).
- **AC-2-Lücke real:** keine Trip-E2E zur Cross-User-Schreibsperre.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/compare-cross-user-write-block.spec.ts` (R) | Nur API: B PUTet auf A's Preset → 404, Name unverändert. Zu parametrisieren (AC-2) |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` (R) | Orte-Geste, an Vergleich gebunden; Mandanten-Spec |
| `frontend/e2e/compare-editor-autosave.spec.ts` | 11 Fälle, 7× `waitForTimeout`, nicht in Ratsche; Autosave Orte/Wetter-Metriken/Wertebereiche, Gesten-Gate, F001-Re-Arm |
| `frontend/e2e/compare-hub-save-chip.spec.ts` | 4 Fälle (idle, saving→idle + Reload, Fokus/Blur 0 PUT, 500 → Fehler + Rollback); 1× `waitForTimeout`; nicht in Ratsche |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts` (R) | Vergleichs-Hälfte von AC-1 |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` (R) | Vorbild-Schleife + Trip-Hälfte von AC-1 |
| `frontend/e2e/helpers.ts` | `registriereBestaetigtenZweitnutzer`, `createTestTrip`/`createTestComparePreset`/`createTestLocation`, `cleanupTracked`; `fillStep1/2/3` tot (#2243 C) |
| `frontend/e2e/global.setup.ts` | storageState `playwright/.auth/admin.json`, Orte `e2e-loc-*`, Trip `e2e-cockpit-test` |
| `frontend/e2e/trip-edit.spec.ts` | Bestandsleiche (alter Wizard, testids existieren nicht mehr), nicht in Ratsche; in #2243 Liste B |
| `.github/ci_e2e_specs.txt` | Ratsche (Kopf Z. 63-69: Login-Kontingent) |
| `.github/workflows/ci.yml` Job `e2e` (~Z. 188ff, Kommentar Z. 285) | Existenzprüfung je Eintrag, `E2E_MIN_SPECS` (63), `E2E_MIN_EXECUTED_HAUPT: 367` exakt via `.github/scripts/e2e_gate.py` |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | `E2E_MIN_SPECS` == Listenlänge exakt; `MANDANTEN_SPECS` hält beide Compare-Mandanten-Dateinamen fest |
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | Tab-testids `trip-detail-tab-<id>` / `compare-detail-tab-<id>` |
| `.claude/hooks/pendant_gate.py` | Erfasst **keine** E2E-Specs (`_bereich()` → None für `.spec.ts`) |

## Einordnung der 47 `*compare*.spec.ts` (R = in Ratsche, 17)
- **(a) darf bleiben:** `compare-hub-inline-edit` R (Orte; eingebetteter CorridorEditor-Teil ist b), `compare-uebersicht-kanal-bedienung.staging`, `compare-uebersicht-kanal-persistenz.staging`, `compare-metric-order`, `compare-hourly-metric-order` (beide laut Ratschen-Kopf rot), `issue-1080-compare-new-url`.
- **(b) Trip-Pendant vorhanden → zusammenführbar:** `compare-editor-autosave`, `compare-hub-save-chip`, `compare-versand-speichert-selbst` R, `compare-hub-versand-inline`, `compare-hub-briefing-times`, `compare-alarme-speichert-selbst` R, `compare-alarme-wertprops` R, `compare-radar-toggle` R (Radar ohne Trip-Spec), `compare-wertebereiche-speichert-selbst` R, `compare-wertebereiche-wertprops` R, `compare-wetter-metriken-speichert-selbst` R, `compare-stundenverlauf-wertprops` R, `compare-active-metrics-format.staging`, `compare-outlook-metric-selection.staging`, `compare-konfliktschutz-zwei-kontexte` R, `compare-hub-kopf-einmal`, `compare-hub-name-region-profil`, `compare-tab-bar`, `bug-626-compare-menu-actions`, `compare-send-dialog-target.staging`, `feat-1461-s3b2b-compare-kanal-schwelle` (prüft beide), `compare-cross-user-write-block` R, `compare-editor-autosave-user-isolation` R (die letzten zwei ohne Trip-Pendant = AC-2-Lücke).
- **(c) ohne Pendant:** `compare-detail-edit-entry` R, `compare-edit-redirect`, `compare-new-vorlage`, `compare-editor-slice1` R, `issue-682-compare-editor-mobile` R (Pendant `issue-661-trip-new-mobile` R), `compare-hub-fidelity-s8c`, `compare-mobile-vervollstaendigung`, `compare-legacy-fields-survive-save` R, `fix-1350-compare-metric-select.staging`, `fix-1350t3-compare-threshold-source.staging`.
- **(d) tot/veraltet:** `compare-editor-slice4`, `compare-editor-fidelity-s8d`, `compare-flow-navigation`, `issue-1093-compare-layout-crash`, `compare-layout-tab-dissolution`, `compare-alarm-config`, `compare-neu-kanal-anlegen.staging`, ggf. `compare-editor-slice3` R — größtenteils auf der #2243-Liste.

## Existing Patterns
- Schleife über Hubs: `trip-hub-kopf-region-aktivitaet.spec.ts:917-935`.
- Zweitnutzer: `registriereBestaetigtenZweitnutzer` + `browser.newContext({storageState: undefined})`.
- Aufräumen: `cleanupTracked` (preset → trip → location) bzw. try/finally.
- Ratschen-Verkleinerung hat Präzedenzfall: PR #2495 (`E2E_MIN_SPECS` 60→58, `E2E_MIN_EXECUTED` neu gemessen).

## Dependencies
- Upstream: CI-Stack `frontend/e2e/ci-stack.sh`, Go-Handler `trip.go`/Compare-Preset-Handler (404 für fremde Objekte), `SaveIndicator`/`SubscriptionHeader`.
- Downstream: CI-Job `e2e` (Existenzprüfung, Min-Specs, exakte Ausführungszahl), `test_e2e_positivliste_ratschen_bindung.py` (feste Dateinamen der Mandanten-Specs).

## Existing Specs
- #2276: `docs/specs/modules/rework_2276_s1…s6h_*.md`
- #2277: `docs/specs/modules/fix_2277_*.md`, `feat_2277_*.md`
- #2346: `docs/specs/modules/feat_2346_cockpit_paritaet.md`
- Save-Chip/Autosave: `feat_1273_s1_compare_hub_save_chip.md`, `issue_1261_compare_edit_autosave.md`, `epic_1273_s4a_test_migration.md`
- #2347 selbst: noch keine Spec.

## Risks & Considerations
- **Überschneidung mit #2243 (Löschscheibe, OPEN, kein Commit):** Gruppe (d) und `trip-edit.spec.ts` gehören dorthin. Abgrenzung oder Übernahme muss die Analyse entscheiden — nicht doppelt arbeiten.
- **Umfang:** AC-3 (alle 47 Compare-Specs auf (a) reduzieren) ist groß; LoC-Limit gilt für Testdateien nicht als „produktiv", aber Review-/CI-Aufwand ist hoch → Scheibung prüfen (Epic-Regel: themenweise abschließen, nicht abspalten).
- **Ratschen-Kopplung:** Umbenennen/Zusammenlegen der Mandanten-Specs bricht `test_e2e_positivliste_ratschen_bindung.py`; `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` müssen exakt nachgezogen und neu gemessen werden.
- **Filter A:** zusammengeführte Specs dürfen kein `waitForTimeout`/`skip` enthalten — Teile von `compare-editor-autosave`/`compare-hub-save-chip` müssen dafür umgebaut werden; Filter B verlangt 3× grün im Zielverbund.
- **Login-Kontingent:** jeder neue Zweitnutzer-Fall verbraucht Login (30/h) und Registrierung (5/h je IP).
- **Regressionsnetz nicht verlieren:** beim Zusammenführen dürfen Zusicherungen der Compare-Specs (Gesten-Gate, F001-Re-Arm, 500-Rollback) nicht stillschweigend verschwinden — Zuordnungstabelle alt→neu nötig.
- **`gz-eigenstaendig:` in E2E wird von keinem Gate erzwungen** (pendant_gate ignoriert `frontend/e2e/`) — AC-3 braucht einen eigenen Wächter-Test oder bleibt Konvention.

## Analysis

### Type
Feature (type:rework, reine Testschicht: `frontend/e2e/`, Ratsche, Unit-Wächter, Gate-Doku). Kein Produktcode.

### Abgrenzung zu #2243 (entschieden)
- **In der Ratsche gelistete** Leichen/Mischdateien fallen unter AC-4 von #2347 — konkret `compare-editor-slice3` (R).
- **Nicht gelistete** Leichen (`trip-edit`, `slice4`, `fidelity-s8d`, `flow-navigation`, `issue-1093`, `layout-tab-vergleich`, `compare-alarm-config`, …) bleiben bei #2243 und werden hier NICHT angefasst.
- `compare-editor-slice3` ist **keine** Leiche (verifiziert): AC-1..3 = Orte-Tab (bleibt Compare-only), AC-4..9 = CorridorEditor (Gruppe b → in Wertebereiche-Spec aufgehen bzw. neuer kind-Fall), AC-10 (Wizard-Konfig an Server) gegen `compare-editor-slice1`/`compare-new-vorlage` abgleichen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/helpers.ts` | MODIFY | `HubKind`, `HUB_KINDS`, `seedHub(kind)`, `openHub(kind,id,{tab,hash})`, `hubApiPath(kind,id)` — dünn, keine Assertions; Selektor-Unterschiede bleiben als `HUB_SEL[kind]` im Spec |
| `frontend/e2e/compare-cross-user-write-block.spec.ts` | DELETE→CREATE `hub-cross-user-write-block.spec.ts` | AC-2: ein Zweitnutzer (beforeAll), Schleife über beide kinds, Status 404 + Objekt unverändert |
| AC-1-Spec (neu, z. B. `hub-versand-autosave-chip.spec.ts`) | CREATE | Versand-Uhrzeit → Autosave + Chip „Gespeichert HH:MM" je kind; ersetzt Trip-AC-11 aus `trip-hub-kopf-region-aktivitaet` und Vergleichs-AC-1 aus `compare-versand-speichert-selbst` |
| `trip-hub-kopf-region-aktivitaet.spec.ts`, `mobile-tab-bar`, `trips-list-aktionen`, `issue-758-save-indicator`, `feat-880-autosave-overlay`, `versand-tab`, `weather-metrics-tab-autosave`, `speicherung-ueberlebt-neuladen` | MODIFY | Zielorte für Zusammenführung der Gruppe (b) (Schleife über kind) |
| Gruppe-(b)-Compare-Specs (≈20, Liste im Kontext oben) | DELETE (nach Übernahme) | je Datei Zuordnungstabelle „alte Zusicherung → neuer Fall" |
| `issue-682-compare-editor-mobile` ↔ `issue-661-trip-new-mobile` | MERGE | Pendant existiert → Gruppe b, nicht c |
| Gruppe-(c)-Dateien (`compare-detail-edit-entry`, `compare-edit-redirect`, `compare-new-vorlage`, `compare-editor-slice1`, `compare-legacy-fields-survive-save`, gelistete Teile) | MODIFY | `gz-eigenstaendig:`-Kopf **nur nach Beleg**, dass kein Trip-Pendant existiert (`compare-detail-edit-entry`/`compare-edit-redirect` erst gegen `hub-reiter-alt-kennungen-umleitung` prüfen) |
| `compare-editor-autosave-user-isolation.spec.ts` | MODIFY | Orte-Geste = erlaubte Compare-Eigenheit → Name bleibt, Kopf `gz-eigenstaendig: Orte-Tab` (vermeidet Bruch von `MANDANTEN_SPECS`/testMatch) |
| `.github/ci_e2e_specs.txt` | MODIFY | neue Specs rein, zusammengeführte raus |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` (== Listenlänge), `E2E_MIN_EXECUTED_HAUPT` **gemessen** je Scheibe |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | MODIFY | `MANDANTEN_SPECS`: `compare-cross-user-write-block` → `hub-cross-user-write-block` |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | MODIFY | nennt `compare-radar-toggle`/`versand-tab-vergleich` — mitziehen, wenn diese fallen |
| `frontend/playwright.*.staging.config.ts` / `e2e/playwright.*.red.config.ts` mit testMatch auf alte Namen | MODIFY/DELETE | 1273-s4c, 1256-s7, 1229-hub, 1273-s1/-s2, 2284-s1 — je Scheibe `grep -rn <altname>` über `.github tests frontend docs` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` (Name vorläufig) | CREATE | AC-3-Wächter: (1) `frontend/e2e/*compare*.spec.ts` nur mit erlaubtem Thema oder `gz-eigenstaendig:`-Kopf; (2) Specs, die `/compare/` bzw. `compare-detail-tab` ansteuern, brauchen kind-Schleife oder Kopf (schließt Umgehung per Dateiname). Start als Ratsche mit schrumpfender Altlastliste |
| `docs/reference/gates_und_ratschen.md` | MODIFY | neuer Wächter + Prüfdatum **2027-01-24** (+90 Tage, Regel-Budget) |

### Scope Assessment
- Gesamt: ~40 Dateien berührt, Testcode netto eher negativ (Redundanz Versand ×3, Radar ×3 fällt). Produktcode: 0.
- Risk Level: **MEDIUM** — kein Nutzerverhalten betroffen, aber Gefahr, Regressionsnetze stillschweigend zu verlieren, und enge CI-Ratschen-Kopplung.

### Scheibenschnitt (alles innerhalb #2347, kein Abspalten)
- **S1 (diese Spec):** Helfer + AC-1 + AC-2 + AC-3-Wächter (Ratschenmodus, Altlastliste) + Prüfdatum. Umbenennung `compare-cross-user-write-block` → `hub-cross-user-write-block` samt `MANDANTEN_SPECS`/testMatch/Ratsche.
- **S2:** Hub-Kopf & Navigation: `compare-tab-bar`↔`mobile-tab-bar`; `compare-hub-name-region-profil`+`compare-hub-kopf-einmal`↔`trip-hub-kopf-region-aktivitaet`/`issue-724`; `bug-626-compare-menu-actions`↔`trips-list-aktionen` (12× waitForTimeout ersetzen); `compare-hub-save-chip`↔`issue-758`/`feat-880`.
- **S3 (ggf. S3a Alarme/Radar · S3b Wertebereiche/Wetter-Metriken/Versand/Editor-Autosave):** `*-speichert-selbst`, `*-wertprops`, Versand-Trio, `compare-radar-toggle`, `compare-konfliktschutz-zwei-kontexte`, `compare-editor-autosave` (7× W), `issue-682`↔`issue-661`, slice3 AC-4..9.
- **S4:** Gruppe (c) belegen + `gz-eigenstaendig:`, slice3-Rest (Orte-Tab/AC-10), Altlastliste des Wächters auf leer, Ratsche final.
- Je Scheibe: `E2E_MIN_EXECUTED_HAUPT` messen, Filter A (kein waitForTimeout/skip) + Filter B (3× grün im Zielverbund).

### Technical Approach
Vorbild `trip-hub-kopf-region-aktivitaet.spec.ts:917-935`: `for (const kind of HUB_KINDS) test(\`AC-x (${kind}): …\`)`. Gemeinsamer Seed/Öffnen/API-Pfad im Helfer, unterschiedliche Kopf-Testids als `HUB_SEL[kind]` im Spec (ehrlicher als Voll-Abstraktion). Compare-Zusätze nur in `if (kind === 'vergleich')`, wenn fachlich nötig. Wartebedingungen über `waitForResponse`/`expect.poll`, nie `waitForTimeout`.

**Pflichtinhalte der Spec:** Zuordnungstabelle alt → neu je entfallender Datei (insb. Gesten-Gate, F001-Re-Arm, 500-Rollback, 412-Retry); diese vier je einmal per Mutations-Gegenprobe rot zeigen.

### Design-Vorgaben
- AC-2: **genau eine** Registrierung je Lauf (Kontingent 5/h je IP) — Zweitnutzer in `beforeAll`, beide kinds damit. Status beider Hubs ist 404 (`UpdateTripHandler` prüft Besitz vor ETag) → Spec behauptet 404, nicht „403/404".
- AC-1: Versand ist Abschnitt `#versand` im Reiter Wetter-Metriken (`?tab=wetter-metriken#versand`), Chip = geteilter `SaveIndicator` (`data-testid="save-indicator"`, `.save-time`).
- `E2E_MIN_SPECS` darf beim Zusammenlegen sinken (Präzedenz PR #2495), muss in Spec/PR begründet werden.

### Dependencies
- #2276/#2277 erledigt (Voraussetzung erfüllt). `origin/main` am 2026-10-26 geprüft: keine #2347-Commits.
- Nicht parallel mit #2243 an `ci_e2e_specs.txt` arbeiten (Merge-Konflikt).

### Open Questions
- keine PO-Fragen (alles technisch; Abgrenzung #2243 und Scheibenschnitt entschieden).
- Technisch in S3/S4 zu messen: deckt `hub-reiter-alt-kennungen-umleitung` `compare-edit-redirect`/`compare-detail-edit-entry` ab? Ist slice3 AC-10 schon in slice1/new-vorlage belegt?

## Übergabe RED → GREEN (/40, 2026-10-26)

**RED-Stand:** `tests/unit/test_e2e_compare_paritaet_waechter.py` (Funktion `pruefe_compare_specs` vollständig, `ALTLAST` bewusst LEER ⇒ Echter-Baum-Test rot, listet ~49 Verstöße), `MANDANTEN_SPECS` auf `e2e/hub-cross-user-write-block.spec.ts` umgestellt (rot, bis die Datei auf der Positivliste steht), `frontend/e2e/hub-versand-autosave-chip.spec.ts` + `hub-cross-user-write-block.spec.ts` (rot bei der Sammlung: `helpers.ts` exportiert `HUB_KINDS` nicht).

**Für /50 (Developer):**
- `helpers.ts`: `HubKind`, `HUB_KINDS`, `SeededHub`, `seedHub`, `openHub`, `hubApiPath` laut Spec. `seedHub('route')` braucht Etappen mit Wegpunkten und `report_config: {enabled, morning_enabled: true, morning_time: '06:00:00', …}` (Vorbild `seedBody` in `trip-hub-kopf-region-aktivitaet.spec.ts:80`); `seedHub('vergleich')` mit Seed-Orten `e2e-loc-innsbruck`/`e2e-loc-stubai`, `morning_enabled: true`, `morning_time: '06:00:00'` (Vorbild `legeVergleichAn` in `compare-versand-speichert-selbst.spec.ts:53`). Präfix `E2E-GZ-`. `aufraeumen()` löscht per DELETE.
- `openHub('vergleich')`: nach `goto` muss der Reiter `compare-detail-tab-wetter-metriken:visible` geklickt werden (doppelte Knoten, Muster `oeffneVersand` Z. 112) — **ohne** `networkidle`, nur auf Sichtbarkeit warten.
- AC-1-Spec prüft `toHaveValue('06:00')`/`'08:00'` am Select — falls die Option-Werte `HH:MM:SS` sind, die Spec-Erwartung angleichen (nicht den Produktcode).
- „Genau ein PUT" ohne Schlaf: `page.reload()` ist die Schranke (bereits so geschrieben). Die Mutation „doppelter Handler" muss im GREEN tatsächlich rot werden — sonst Finding.
- AC-2 läuft seriell: unter Mutation wird der Folgefall **übersprungen**, nicht grün. Mutationen je kind einzeln mit `--grep "AC-2 \(route\)"` bzw. `"AC-2 \(vergleich\)"` fahren; jede Ausführung kostet eine Registrierung (5/h je IP) — Mutationsläufe einplanen.
- `ALTLAST` erst am **Endstand** messen (nach Löschen von `compare-cross-user-write-block.spec.ts`), `ALTLAST_MAX = len(ALTLAST)` bleibt so.
- Rest laut Spec „Berührte Dateien": alte Cross-User-Spec löschen, AC-1 aus `compare-versand-speichert-selbst` (6 → 5 Fälle, `waitForTimeout` weg), Versand-Anhang aus Trip-AC-11 (Titel anpassen), Positivliste, `ci.yml` (`E2E_MIN_SPECS` 64, `E2E_MIN_EXECUTED_HAUPT` per `--list` messen), Passkey-Kommentar, `gates_und_ratschen.md` (Prüfdatum 2027-01-24).
