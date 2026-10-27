# Context: feat-2347-s2-s4-paritaets-e2e

## Request Summary
Scheiben S2–S4 von #2347 (Epic #2345, Etappe P6) in einem Workflow: die verbleibenden Compare-Playwright-Specs
zu kind-parametrisierten Hub-Specs (`for (const kind of HUB_KINDS)`) zusammenführen oder mit `gz-eigenstaendig:`
begründen, bis die ALTLAST-Liste des Paritäts-Wächters leer ist; Ratsche final. Reine Testschicht, kein Produktcode.

Vorgänger: S1 live (PR #2623, `9c7b41f94`), Spec `docs/specs/modules/feat_2347_s1_paritaets_e2e.md`
(Scheibenplan Z. 34-43, Befund-Korrekturen Z. 45-55), Kontext `docs/context/feat-2347-paritaets-e2e.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/helpers.ts` | `HubKind`, `HUB_KINDS`, `seedHub`, `openHub`, `hubApiPath` (aus S1) — Basis jeder neuen Spec |
| `frontend/e2e/hub-versand-autosave-chip.spec.ts`, `hub-cross-user-write-block.spec.ts` | S1-Vorbilder für kind-Schleife |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts:917-935` | ältere Schleife `['Trip','Vergleich']`; AC-11 Chip-Region-Teil wartet auf S2 |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | Wächter: Regeln Z. 100-133, `ALTLAST` Z. 39-89 (48), `ALTLAST_MAX=48` Z. 92; Ratschenregel: konform gewordener oder gelöschter Eintrag ⇒ rot, muss im selben PR raus |
| `.github/ci_e2e_specs.txt` | E2E-Ratsche, 64 Einträge (Z. 331-390, 397, 411, 421, 433); Compare-Einträge Z. 335-349, 374 |
| `.github/workflows/ci.yml:285-288,353-377,404` | `E2E_MIN_SPECS 64`, `E2E_MIN_EXECUTED_HAUPT 369`; Existenzprüfung je Datei; `.github/scripts/e2e_gate.py:66-70` |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py:27-48,82ff` | Gleichheit Listenlänge = `E2E_MIN_SPECS`; `MANDANTEN_SPECS` (`hub-cross-user-write-block`, `compare-editor-autosave-user-isolation`) |
| Staging-/RED-Configs: `frontend/playwright.*.staging.config.ts`, `frontend/e2e/playwright.*.staging.config.ts`, `frontend/e2e/playwright.1273-s{1,2,3}.red.config.ts`, `playwright.2284-s1.red.config.ts`, `frontend/playwright.1273-s4c.staging.config.ts:31-39` | nennen Compare-Specs namentlich — beim Umbenennen/Löschen mitziehen |
| `docs/reference/gates_und_ratschen.md` | Ratschen-/Wächter-Doku, Prüfdatum 2027-01-24 |

## Inventar ALTLAST (48 Dateien, Stand `9c7b41f94`)
T = Testfälle, W = `waitForTimeout`, R = Ratschen-Zeile.

**S2 — Hub-Kopf, Navigation, Chip, Liste**
| Compare-Datei | T | W | R | Trip-Pendant |
|---|---|---|---|---|
| compare-tab-bar | 5 | 0 | – | mobile-tab-bar (6/0/–) |
| compare-hub-name-region-profil | 7 | 1 | – | trip-hub-kopf-region-aktivitaet AC-1..8 (27/0/389), issue-724-trip-name-save-error (3/0/379) |
| compare-hub-kopf-einmal | 11 | 0 | – | trip-hub-kopf AC-6/8/18 |
| bug-626-compare-menu-actions | 7 | 12 | – | trips-list-aktionen (3/0/–) |
| compare-hub-save-chip | 4 | 1 | – | issue-758-save-indicator (7/0/–, AC-3/6 schon mit Vergleich), feat-880-autosave-overlay (7/2/–, AC-6/7 mit Vergleich) |
| compare-mobile-vervollstaendigung | 7 | 0 | – | mobile-tab-bar, issue-268 |
| compare-send-dialog-target.staging | 2 | 2 | – | trips-list-send (teilweise) |

**S3 — Speichert-selbst / Wertprops / Versand / Konflikt / Anlege-Mobil**
| Compare-Datei | T | W | R | Trip-Pendant |
|---|---|---|---|---|
| compare-alarme-speichert-selbst | 4 | 0 | 335 | issue-953 (teilweise) |
| compare-alarme-wertprops | 4 | 0 | 336 | speicherung-ueberlebt-neuladen AC-3 (teilweise) |
| compare-editor-autosave-user-isolation | 1 | 0 | 338 | hub-cross-user-write-block (teilweise); in `MANDANTEN_SPECS` |
| compare-editor-autosave | 11 | 7 | – | issue-758, hub-versand-autosave-chip |
| compare-editor-slice3 (AC-4..9) | 9 | 0 | 340 | Wertebereiche-Specs |
| compare-hub-briefing-times | 9 | 0 | – | versand-tab, issue-616 AC-3 |
| compare-hub-versand-inline | 7 | 0 | – | versand-tab, hub-versand-autosave-chip |
| compare-hub-inline-edit (Wertebereich-Teil) | 6 | 0 | 341 | speicherung-ueberlebt-neuladen |
| compare-konfliktschutz-zwei-kontexte | 5 | 0 | 342 | trip-hub-kopf AC-9, feat-1395-s4 (Staging) |
| compare-radar-toggle | 3 | 0 | 344 | keins |
| compare-stundenverlauf-wertprops | 4 | 0 | 345 | keins |
| compare-versand-speichert-selbst (Rest AC-4..11) | 5 | 0 | 346 | hub-versand-autosave-chip |
| compare-wertebereiche-speichert-selbst | 7 | 2 | 347 | speicherung-ueberlebt-neuladen, issue-953 |
| compare-wertebereiche-wertprops | 4 | 4 | 348 | enthält Trip-Fall AC-6 selbst |
| compare-wetter-metriken-speichert-selbst | 7 | 2 | 349 | weather-metrics-tab-autosave |
| compare-active-metrics-format.staging | 3 | 3 | – | weather-metrics-tab-autosave (teilweise) |
| compare-outlook-metric-selection.staging | 5 | 4 | – | trip-outlook-metric-selection.staging; 1× `skip` Z. 287 |
| feat-1461-s3b2b-compare-kanal-schwelle | 8 | 0 | – | prüft Trip schon mit (AC-16) |
| fix-1350-compare-metric-select.staging | 4 | 3 | – | weather-metrics-tab-autosave AC-1/3 |
| issue-682-compare-editor-mobile | 6 | 0 | 374 | issue-661-trip-new-mobile (11/1/373 — W in der Ratsche!) |
| versand-tab-vergleich (Regel 2) | 9 | 1 | – | versand-tab |

**S4 — ohne Trip-Pendant / compare-eigen (Kopf `gz-eigenstaendig:`)**
compare-detail-edit-entry (2/0/337), compare-edit-redirect (1/0/–), compare-editor-slice1 (5/0/339, `/compare/new`),
compare-editor-slice3 Rest (Orte AC-1..3, AC-10), compare-hub-fidelity-s8c (11/0/–), compare-hub-inline-edit Orte-Teil,
compare-legacy-fields-survive-save (2/0/343), compare-new-vorlage (3/0/–), compare-hourly-metric-order (3/1/–, laut Kopf rot),
compare-metric-order (2/0/–, laut Kopf rot), issue-1080-compare-new-url (3/0/–, Orte),
compare-uebersicht-kanal-bedienung.staging / -persistenz.staging, kanal-grenzen-ortsvergleich.staging (Regel 2, Compare-Mail/Kanal),
fix-1350t3-compare-threshold-source.staging (3/1/–).

**#2243-Leichen laut S1-Spec Z. 56-58 (nicht in der Ratsche)**
compare-alarm-config (2/1), compare-editor-slice4 (6/1), compare-editor-fidelity-s8d (11/0), compare-flow-navigation (16/1, Abschnitt „Editor-Layout-Tab" Z. 515ff tot),
compare-layout-tab-dissolution (6/0, AC-1 Z. 175-187 widerspricht sich ⇒ immer rot), issue-1093-compare-layout-crash (1/0),
compare-neu-kanal-anlegen.staging (1/0, klickt nicht mehr existentes `compare-editor-continue-versand` Z. 106 ⇒ echt tot).
Die meisten anderen „Abschaffungs"-Bezüge prüfen nur `toHaveCount(0)` — umgebogen, nicht tot.

## Existing Patterns
- kind-Schleife mit S1-Helfern; Testtitel tragen `kind` (Vorbild `hub-versand-autosave-chip.spec.ts`).
- Wächter-Konformität: `HUB_KINDS` im Text, Altmuster `['Trip','Vergleich']`, oder Kopf `gz-eigenstaendig:` (≥15 Zeichen Begründung, erste 30 Zeilen).
- Filter A: kein `waitForTimeout`/`skip` in Ratschen-Specs (auf Ereignisse warten: `waitForResponse`, `expect.poll`, `toHaveAttribute('data-state', …)`).
- Filter B: 3× grün im Zielverbund vor Aufnahme in die Ratsche.
- Chip: geteilter `SaveIndicator.svelte` (`save-indicator`, `data-state`, `.save-time`).
- Fremder Hub-PUT ⇒ exakt 404 (S1-Befund 3).

## Dependencies
- Upstream: S1-Helfer, CI-Stack (`.github/workflows/ci.yml` e2e-Job, ohne nginx), Seed über API.
- Downstream: Ratsche `ci_e2e_specs.txt` + `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT`, Bindungstest, Wächter, Staging-/RED-Configs mit Dateinamen, `MANDANTEN_SPECS`.

## Existing Specs
- `docs/specs/modules/feat_2347_s1_paritaets_e2e.md` — S1, Scheibenplan, Befund-Korrekturen, Abgrenzung #2243.

## Risks & Considerations
1. **Konflikt S4 ↔ #2243:** „Altlastliste auf leer" geht nicht, solange die 7 #2243-Leichen existieren; S1-Spec sagt „in #2347 nicht anfassen". #2243 ist offen, kein Branch/Commit, keine Session. Entscheidung in der Analyse nötig (Leichen in diesem Workflow mitlöschen vs. Reihenfolge) — inhaltlich gleiche Etappe des Epics #2345, Regel „Epics themenweise abschließen" spricht für Mitnahme der E2E-Leichen; Helfercode/55 Configs aus #2243 bleiben dort.
2. **Zusicherungsverlust beim Zusammenführen:** Jede Alt-Zusicherung braucht eine Ziel-Zeile in einer Mapping-Tabelle (wie S1 Z. 160ff); Mutations-Gegenprobe je zusammengeführtem Verhalten für beide kinds.
3. **Trip-Fälle neu:** Viele Compare-Zusicherungen haben kein Trip-Pendant (Radar, Stundenverlauf, Legacy-Felder, Konflikt-412) — für den Trip könnten sie ROT werden ⇒ echte Produktlücke statt Testarbeit. Dann: Befund, nicht Testabschwächung.
4. **Umfang:** ~48 Dateien, ~260 Testfälle. Laufzeit des CI-e2e-Jobs und `E2E_MIN_EXECUTED_HAUPT` je Etappe neu messen.
5. **Filter-A-Altverstöße** bereits in der Ratsche (wertebereiche-speichert-selbst 2, wertebereiche-wertprops 4, wetter-metriken-speichert-selbst 2, issue-661 1) — beim Umbau mitbereinigen.
6. **Staging-Specs** sind nicht im CI-Hauptlauf; Zusammenführung nur mit eigener Staging-Config verifizierbar.
7. **Config-Verweise** auf umbenannte Dateien (Staging/RED) mitziehen, sonst tote Configs.
8. **Parallelität:** `.github/ci_e2e_specs.txt` nicht parallel mit anderer Session bearbeiten.

## Analysis

### Type
Feature/Rework (reine Testschicht; Epic #2345, Etappe P6)

### Schnitt-Entscheidung (gemessen, ersetzt den Arbeitstitel „S2–S4")
- `workflow.py` kennt **keinen zweiten Durchlauf 4→8** im selben Workflow (Phasenautomat einmalig, Prod-Nachweis je SHA, `deploy-gregor-prod.sh` synct hart auf `origin/main` ⇒ ein gemergter, nicht ausgelieferter Zwischen-PR würde von parallelen Sitzungen ungeprüft mit ausgeliefert).
- Daher nach S1-Vorbild: **diese Spec/dieser Workflow = S2**, ein PR, volle Kette bis Selftest. S3a, S3b, S4 werden im Scheibenplan der Spec als Folge-Workflows **desselben Tickets #2347** geführt (kein Abspalten — Ticket/Epic bleiben, Issue bleibt offen bis S4).
- Vorgeschlagener Folgeschnitt: **S3a** Alarme/Wertebereiche/Wetter-Metriken/Wertprops (`*-speichert-selbst`, `*-wertprops`, `compare-editor-slice3` AC-4..9, `compare-hub-inline-edit` Wertebereich-Teil); **S3b** Versand-Trio, `versand-tab-vergleich`, Konflikt-412, Radar-Toggle, Stundenverlauf, `compare-editor-autosave`, `issue-682`↔`issue-661`, `.staging`-Specs, `feat-1461-s3b2b`, `fix-1350`; **S4** Gruppe (c) mit `gz-eigenstaendig:`, #2243-Leichen, ALTLAST leer, Ratsche final.
- `ci_e2e_specs.txt` ist Konfliktpunkt ⇒ Scheiben strikt sequentiell mergen.

### S2-Umfang (diese Spec)
| Alt (Compare) | Trip-Pendant | Befund (Stichprobe) | Ziel |
|---|---|---|---|
| `compare-tab-bar` (5 T, 155 Z.) | `mobile-tab-bar` (6 T, 116 Z.) | fast Spiegelbild: aria-selected, roving tabindex, Pfeiltasten, 44px, Badge, Deep-Link; testid-Präfix `${prefix}-detail-tab-*`; Reiter-IDs teils verschieden (Trip `etappen`, Vergleich `orte`) | neue `hub-tab-bar.spec.ts` (kind-Schleife), beide Alt-Dateien fallen |
| `compare-hub-name-region-profil` (7/1W) + `compare-hub-kopf-einmal` (11) | `trip-hub-kopf-region-aktivitaet` AC-1..8 (in Ratsche Z. 389), `issue-724-trip-name-save-error` (Ratsche Z. 379), `trip-hub-kopf` AC-6/8/18 | Kopf ist geteilt (`SubscriptionHeader`); Zusammenführung in kind-Schleife; AC-11-Chip-Region-Teil aus S1 hierher | `hub-kopf*.spec.ts` kind-parametrisiert; Ratschen-Zeilen umhängen |
| `bug-626-compare-menu-actions` (7 T, **12 W**) | `trips-list-aktionen` (3 T) | Aktionsmodell ist seit #2278 geteilt (`shared/subscriptionActions.ts:60-69`, kind-unabhängige Listen-/Hub-Aktionen) ⇒ Trip-Fälle für Bearbeiten/Setup fortsetzen/Senden/„genau 5 Aktionen" voraussichtlich ohne Produktlücke; Ziel-URLs je kind (`/compare/{id}/edit` vs. Trip-Pendant) in `HUB_SEL` | `hub-list-menu.spec.ts`; alle 12 `waitForTimeout` durch `expect`/`waitForResponse` ersetzen |
| `compare-hub-save-chip` (4/1W) | `issue-758-save-indicator` (7, AC-3/6 schon mit Vergleich), `feat-880-autosave-overlay` (7/2W, AC-6 hängt an Staging-Auth) | Chip geteilt (`SaveIndicator.svelte`), **Auslöser nicht**: Vergleich `?tab=orte` (`hub-orte-remove`)/`?tab=wertebereiche` (`corridor-editor-vergleich`), Trip über Etappen/`#versand` ⇒ kind-spezifische Trigger-Funktion, gemeinsame Chip-Assertions (idle/saving/Fehler, Zeitstempel, kein PUT bei unveränderter Eingabe) | `hub-save-chip.spec.ts` |
| `compare-mobile-vervollstaendigung` (7) | `mobile-tab-bar`, `issue-268` | Mobil-Hub geteilt | in `hub-tab-bar`/Mobil-Spec aufgehen lassen |
| `compare-send-dialog-target.staging` (2/2W) | `trips-list-send` (teilweise) | Staging-only, nicht im CI-Hauptlauf | kind-Schleife, bleibt Staging-Spec (nicht in Ratsche), Verifikation über eigene Staging-Config |

### Affected Files (S2)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/helpers.ts` | MODIFY | `HUB_SEL[kind]` (testid-Präfix, Reiter-IDs, Edit-URL), ggf. Seed-Optionen (Etappen/Orte) für Chip-Auslöser |
| `frontend/e2e/hub-tab-bar.spec.ts`, `hub-kopf*.spec.ts`, `hub-list-menu.spec.ts`, `hub-save-chip.spec.ts` | CREATE | kind-parametrisierte Specs |
| 7 Compare-Altdateien S2 + Trip-Pendants (`mobile-tab-bar`, `trips-list-aktionen`, Teile von `trip-hub-kopf-region-aktivitaet`, `issue-758-save-indicator`) | DELETE/MODIFY | nach vollständigem Mapping alt→neu |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | 7 ALTLAST-Einträge raus, `ALTLAST_MAX` 48→41 |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` (`E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) | MODIFY | neue Specs nach Filter B aufnehmen, Zahlen per `--list` messen |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | prüfen | Listenlänge = `E2E_MIN_SPECS` |
| Configs mit Dateinamen (`grep -rn <name> frontend .github tests`) | MODIFY | mitziehen |

### Scope Assessment
- Dateien: ~18; LoC Testcode ca. +700/-1100 (zählt nicht als produktive Spec-Datei); Produktcode: voraussichtlich 0
- Risk Level: MEDIUM (kein Produktverhalten geändert, aber Zusicherungsverlust beim Zusammenführen möglich)

### Technical Approach
Vor dem Schreiben je Altfall eine Zeile Mapping alt→neu (Spec-Tabelle wie S1). Neue Specs nach `hub-versand-autosave-chip.spec.ts` (Testtitel tragen `kind`, Seed per API, Cleanup). Alt-Dateien erst löschen, wenn alle Fälle gemappt sind und beide kinds 3× grün laufen. Mutations-Gegenprobe je zusammengeführtem Verhalten für **beide** kinds. Wird ein Trip-Fall rot: Produktlücke ⇒ im selben Ticket fixen (Regel „bekannte Abweichung im selben Ticket"), Produktdateien dann in die Spec, ggf. `loc_limit_override`; nie abschwächen.

### Risiken / Befunde für die Folge-Scheiben (nur hier festgehalten)
- `compare-hourly-metric-order` und `compare-metric-order` sind laut eigenem Kopf rot ⇒ kein reiner Kopf-Fall in S4, reparieren oder löschen.
- `compare-outlook-metric-selection.staging` hat ein `skip` (Z. 287) — Filter A.
- Filter-A-Altverstöße in der Ratsche: wertebereiche-speichert-selbst 2, wertebereiche-wertprops 4, wetter-metriken-speichert-selbst 2, issue-661 1 (S3a/S3b).
- Trip-Rot-Kandidaten S3b: Radar-Toggle, Stundenverlauf, Konflikt-412 (Trip-Pendant nur Staging), Legacy-Felder.
- **#2243-Leichen nicht pauschal tot:** `compare-detail-tab-${t.id}` dynamisch (`CompareTabs.svelte:159`), `compare-editor-tab-${t.id}`/`compare-editor-continue-{orte,wetter-metriken,wertebereiche,alarme}` live (`CompareNewEditor.svelte:403,460-491`). Belegt tot: `compare-editor-continue-versand` (fidelity-s8d, neu-kanal-anlegen.staging), `compare-editor-tab-layout`/`compare-detail-panel-layout` (layout-tab-dissolution, flow-navigation), `compare-step4-layout-preview`, `compare-layout-hourly-metric-*`. S4 löst die S1-Festlegung „#2243 nicht anfassen" per eigenem Abschnitt „Abweichung von S1" ab: je Datei Lauf + Grep, sonst kind-parametrisieren/begründen; #2243 danach kommentieren.
- Verweise auf #2243-Dateien: `tests/tdd/test_compare_e2e_storagestate_migration.py`, `tests/tdd/test_bug590_signal_removal_telegram_start.py`, `frontend/e2e/compare-uebersicht-kanal.helpers.ts`, `feat-1258-s4.staging.setup.ts`, `playwright.1093.*`, `playwright.1256-s2.staging.config.ts`, `playwright.1273-s4c.staging.config.ts`, `playwright.compare-layout-tab-dissolution.staging.config.ts`.
- CI-Laufzeit steigt durch Verdopplung je kind; `E2E_MIN_EXECUTED_HAUPT` je Scheibe messen.

### Open Questions
- keine für den PO (Schnitt und Produktlücken-Regel sind aus Projektregeln entschieden; Freigabe läuft über die deutschen ACs in `/30`)

## Übergabe /40 → /50 (S2, 2026-10-26)

**RED-Stand:** Sechs neue Specs (`hub-tab-bar`, `hub-save-chip`, `hub-kopf-bearbeiten`, `hub-kopf-aufbau`, `hub-list-menu`, `hub-send-dialog-target.staging` + `.setup.ts`) importieren `HUB_SEL` aus `./helpers` ⇒ `--list` bricht mit „does not provide an export named 'HUB_SEL'" ab (Beleg `docs/artifacts/feat-2347-s2-s4-paritaets-e2e/playwright-red-list.txt`). Wächter: `ALTLAST` 41, `ALTLAST_MAX = 41` ⇒ Echter-Baum-Test rot (7 Altdateien existieren noch). Ratsche: 5 hub-* aufgenommen, `issue-724` raus (68 Zeilen), `E2E_MIN_SPECS` noch 64 ⇒ Bindungstest rot (Beleg `test-red-output.txt`). Verbotsmuster (Filter A/C) in allen sechs neuen Dateien: 0. Altdateien NICHT gelöscht (gehört nach /50).

**Erwartete Fallzahlen (Gegenprobe mit Ersatz-`HUB_SEL` im Scratchpad):** HT 19 (HT-10 nur vergleich), SC 12, KB 20, KA 16 (KA-3 je kind×Viewport, KA-6..9 nur vergleich), LM 20, SD 4.

### `HUB_SEL`-Vertrag, den die Specs voraussetzen (in /50 in `helpers.ts` anlegen)
| Feld | route | vergleich |
|---|---|---|
| `kopf` | `trip` | `compare-hub` |
| `reiter` / `panel` | `trip-detail-tab` / `trip-detail-panel` | `compare-detail-tab` / `compare-detail-panel` |
| `reiterListe` | `trip-detail-tab-list` | `compare-detail-tab-list` |
| `punkteReiter` | `etappen` | `orte` |
| `profilFeld` / `profilWert` | `activity` / `skitour` | `profil` / `wandern` |
| `liste.url` | `/trips` | `/compare` (HT öffnet `${liste.url}/${id}?tab=…` direkt, NICHT über `openHub`) |
| `liste.zeile(id)` / `liste.menue` | `trip-row-<id>` / `trip-row-menu-btn` (Testids, `getByTestId`) | `compare-tile-<id>` / `compare-row-kebab` |
| `hubUrl(id)` | `/\/trips\/<id>(\?|$)/` | `/\/compare\/<id>(\?|$)/` |

Weil der Standard-Seed des Vergleichs `profil: 'wandern'` = `profilWert` trägt, seeden KB/SC mit abweichendem Startwert (`allgemein`/`trekking`) und prüfen Start ≠ Ziel; KA bleibt bei `wandern` (Unterzeile „Wandern · 2 Orte").

### Vom Edit-Gate in Phase 5 blockiert ⇒ in /50 anlegen
`frontend/playwright.hub-send-dialog-target.staging.config.ts` (Write auf Nicht-Testdatei in phase5 gesperrt). Inhalt:
```ts
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
// Staging-Validierung Issue #2347 S2 (vormals #1471, umbenannt aus
// playwright.compare-send-dialog-target.staging.config.ts). Analog playwright.staging.config.ts.
const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: 'e2e',
	timeout: 45_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	},
	projects: [
		{ name: 'setup', testMatch: /hub-send-dialog-target\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /hub-send-dialog-target\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: fileURLToPath(new URL('./e2e/playwright/.auth/staging-1471.json', import.meta.url)),
			},
		},
	],
});
```
Ebenfalls offen: `docs/reference/gates_und_ratschen.md` „S2: 41"; `E2E_MIN_SPECS` 64→68 und `E2E_MIN_EXECUTED_HAUPT` messen; alle Löschungen/Umbenennungen/Kommentar-Verweise laut Spec.

### Altbestand-Messung (Testplan 1) — `docs/artifacts/feat-2347-s2-s4-paritaets-e2e/altbestand-messung.md`
69 Altfälle, 13 rot. Für /50 entscheidend:
1. **Möglicher Produktfehler (AC-13):** `issue-758` AC-1 `:88`/AC-4 `:116` — Etappen-Datum ändern + blur löst im Trip **keinen** PUT aus, Kopf zeigt „Nicht gespeichert". SC-2/SC-4 (route) nutzen genau diesen Auslöser ⇒ werden voraussichtlich rot ⇒ Ursache eingrenzen, im selben Ticket fixen, Produktdateien in Spec nachtragen, nie abschwächen.
2. **Deckungslücke Befund 8 bestätigt:** `issue-682` deckt KEINE der drei AC-24-Zusicherungen (Toast-Text „erst Vergleich benennen", CTA bleibt nach Tipp sichtbar, kein Tab-Wechsel; `issue-682:118-119,124,130,173-174` prüfen nur Sichtbarkeit bzw. sind immer wahr). ⇒ in `issue-682` AC-2 ergänzen, BEVOR `compare-mobile-vervollstaendigung` gelöscht wird (`issue-682` steht in der Ratsche, Z. 374).
3. **Send-Sperre auf dem CI-Stack:** Konto `admin` hat keine Mail-Adresse ⇒ `send-confirm-yes` gesperrt („Im Konto ist keine E-Mail-Adresse hinterlegt") — trifft KA-5 (beide kinds). Vorbedingung im Spec herstellen (Profil-Mail setzen/abfangen), nicht abschwächen.
4. **Orte-Löschen 409 `location_in_use`** (`internal/handler/location.go:294-305`) — trifft KA-8, falls dort ein referenzierter Ort gelöscht wird.
5. Übrige Rote: `bug-626` AC-1/4/6/7 (keine Vergleiche auf leerem Stack, Eigen-Seed in LM löst das), `mobile-tab-bar` 3× 7-statt-5-Reiter, `compare-hub-save-chip` AC-2 `saving` zu kurz beobachtbar (SC-2 verzögert PUT 800 ms), `feat-880` AC-6 Staging-Auth.

### Weitere Befunde aus dem Schreiben
- **SD-Ziel nicht per Seed sperrbar:** E-Mail geht immer; „Senden" sperrt nur, wenn das KONTO keine/unbestätigte Adresse hat (`sendTargetLabel.ts`). SD prüft das als harte Vorbedingung via `GET /api/auth/profile`; alle Sende-Abrufe per `page.route` abgebrochen. Quota-Risiko Staging: pausierte Vergleiche zählen mit (`internal/handler/quota.go:159`).
- **Lösch-Dialog-Titel je kind verschieden:** Trip „Trip löschen" (`routes/trips/+page.svelte:260`), Vergleich „Vergleich löschen?" (`routes/compare/+page.svelte:324`) — in SD als kommentierter Textzweig; AC-13-Kandidat (prüfen, ob Angleichen nötig).
- **Archivieren Vergleich:** `PATCH /api/compare/presets/{id}/state {archived:true}` (`internal/router/router.go:285`, `internal/handler/compare_preset.go:504,550-555`); `/archiv` filtert `archived_at != null` (`routes/archiv/+page.server.ts:46`). LM-8 archiviert für beide kinds per API.
- **LM-Seed route:** Etappe mit heutigem Datum (sonst „geplant" statt „aktiv"); Entwurf = Etappe `date: ''`; pausiert = `PATCH /state {paused:true}`. Vergleich: pausiert `schedule: 'manual'`, Entwurf `location_ids: []`.
- **Risiken GREEN:** LM-10 nutzt `openHub` bei 390 px (unerprobt mobil); KA-5 route (Kopf aus dem Bild?), KB-5 route (bietet Wertebereiche-Pool einen Eintrag?); HT-3 nutzt echten Klick statt `dispatchEvent` (Alt `mobile-tab-bar:44`).
- **CI-Stack lokal:** zusätzlich zu den fünf Handgriffen `GZ_API_BASE=http://localhost:<go-port>` (sonst zeigen SvelteKit-Serverrouten via `start-preview.sh` auf 8091); Ports 8197/8107/4173 waren frei.

### Nachträge vor /50 (Gegenlesen)
- **KA-8 voraussichtlich rot, nicht „falls":** KA-8 legt einen eigenen Ort neben `e2e-loc-innsbruck` an und löscht ihn — ein vom Vergleich referenzierter Ort liefert 409 `location_in_use` (wie Altfall F007 `:466`). Frage für /50: Ist der Zustand „gespeicherte ID ohne aufgelösten Ort" über die API überhaupt noch herstellbar? Wenn nein: anderer Weg zur Vorbedingung oder dokumentierte Spec-Klärung (Changelog) — nie abschwächen.
- **KA-5 und SD brauchen gegensätzliche Kontozustände:** „Senden" sperrt auch bei **unbestätigter** Adresse (`sendTargetLabel.ts`) ⇒ KA-5 braucht eine bestätigte Konto-Adresse; das Profil wird vermutlich serverseitig (SvelteKit) geladen, `page.route` fängt das dann nicht. Ändert KA-5 das Admin-Konto im CI-Stack, im `finally` zurücksetzen (sonst Abfärben auf andere Ratschen-Specs). SD braucht das Gegenteil (Konto ohne zustellbares Ziel); das Staging-Validatorkonto hat sehr wahrscheinlich eine bestätigte Adresse ⇒ SD dort umgebungsbedingt rot. Lösung: Wegwerf-Nutzer `gregor-test+…` (Memory `reference_staging_briefing_mail_braucht_wegwerf_nutzer`). Die AC-7-Prämisse „Eigen-Seed ohne Ziel" ist per Objekt-Seed nicht erfüllbar ⇒ Spec-Abweichung in /50 dokumentieren (Changelog).
- **issue-758 / SC-2 route unbestätigt:** Erst von Hand reproduzieren (echter Fehler — „Nicht gespeichert" ohne Speicherweg — oder bedient der Alt-Test ein veraltetes Eingabeelement?), bevor Produktcode angefasst wird; ein AC-13-Fix vergrößert den Umfang (Spec `updated`/Changelog, ggf. `loc_limit_override`).
- **S1-Kollision:** `hub-versand-autosave-chip.spec.ts` definiert ein lokales `HUB_SEL` (andere Form) — beim Anlegen des Exports NICHT darauf umstellen; der S1-Kommentar `helpers.ts:592-594` („Selektor-Unterschiede stehen als HUB_SEL[kind] im jeweiligen Spec") mitziehen.

### AC-Zuordnung RED
AC-1..AC-7 ⇒ neue Specs (rot über `HUB_SEL`); AC-8 ⇒ Wächter rot; AC-9 ⇒ Bindungstest rot; AC-10, AC-11 (Filter B), AC-12, AC-13, AC-14 ⇒ Prozess-Prüfungen in /50 (Adversary) bzw. /60.
