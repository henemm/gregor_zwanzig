# Context: rework-2823-wizardstate-restposten

## Request Summary
Restposten aus #2727 (Epic #2345, PR #2775, live seit Prod 8b56b3d). #2727 selbst ist **geschlossen und erledigt**. Nachgemessen am 2026-11-05 auf `2941d6c0b`: `compare_wizard_state_entfernt.test.ts` + `context_herkunft_zweige_eingefroren.test.ts` 50/50 grün, Ratsche 47. Die Sitzung war versehentlich als Doppel-Workflow `refactor-2727-compare-wizardstate` gestartet. PO-Entscheidung 2026-11-05: die Restposten hier erledigen → Issue #2823.

Zwei Restposten:
1. **Veralteter Staging-Test** `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts` (#1703 S8, „EINZIGER Wächter der ANLEGE-Naht“ für `channel_active_metrics` per Kanal-Reiter auf `/compare/new`). `briefingAktivieren()` (:104–128) klickt `compare-editor-continue-versand`, den es seit #1743 nicht mehr gibt (Versand liegt unter Wetter-Metriken). Schon vor #2775 kaputt, nicht in CI.
2. **Irreführende Kommentare**, die den gelöschten `CompareWizardState` noch als Zustandsträger nennen (11 Produktivdateien).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts` | 211 Z. Zu reparieren: `briefingAktivieren()` und Kopf-Kommentar (:11–12 nennt `CompareWizardState.saveNewPreset:163`, `CompareNewEditor.svelte:394/:491` — Zeilen veraltet) |
| `frontend/e2e/playwright.compare-uebersicht-kanal.staging.config.ts` | Config, die die Datei laufen lässt (testDir `.`); liest `GZ_VALIDATOR_USER ?? E2E_USER` |
| `frontend/e2e/compare-uebersicht-kanal.staging.setup.ts` | Setup: `httpCredentials` aus `GZ_VALIDATOR_USER/PASS` (:23), App-Login aus `GZ_AUTH_USER/PASS` (:26). Staging hat keine Basic-Auth mehr; beim #2775-Lauf manuell gemappt |
| `frontend/e2e/compare-uebersicht-kanal.helpers.ts` | Selektoren/Warteregel #1423 für die Kanal-Reiter |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Heutiger Klickweg Desktop: `compare-editor-continue-orte` (:559) → `-wetter-metriken` (:569) → `-wertebereiche` (:581) → `-alarme` (:591) → `compare-editor-activate` (:467). Kein Versand-Reiter mehr; Versand steckt im `WetterMetrikenVersandPanel` (:577) |
| `frontend/e2e/kanal-je-wettergroesse-block.staging.spec.ts:256–268` | Vorbild für den aktuellen Klickweg (`zumAlarmeReiter`, verweist ausdrücklich auf „Muster compare-neu-kanal-anlegen“) |
| `frontend/e2e/helpers.ts:867–882` | `ANLEGE_SEL` mit Selektoren für `.cm-desktop`-Weiter-Knöpfe und `cm-mobile-activate` |
| `frontend/src/lib/components/compare-new/__tests__/compare_anlege_freischaltung.test.ts` | Kerntest: Aktivieren ab Alarme-Besuch freigeschaltet (`BIS_ALARME`), 5 Fortschritts-Segmente |
| Kommentar-Dateien `compare/`: `alarmePropsAus.ts:44`, `versandPropsAus.ts:41`, `wetterMetrikenPropsAus.ts:52`, `corridorPropsAus.ts:35`, `compareHubHydration.ts:34`, `CompareHourlyLayoutControls.svelte:20` | Nennen `CompareWizardState` |
| Kommentar-Dateien `shared/`: `alarmeVergleichSpeicherung.ts:61`, `versandVergleichSpeicherung.ts:55`, `WeatherMetricsTab.svelte:112`, `OutlookLayoutControls.svelte:39`, `corridor-editor/wertebereicheVergleichSpeicherung.ts:33` | Nennen `CompareWizardState`; unter Ratschen-Schutz (siehe Risiken) |
| `frontend/src/lib/components/compare/__tests__/compare_wizard_state_entfernt.test.ts` | Wächter #2727; zählt nur Code-Zeilen, Kommentare nicht — muss grün bleiben |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | Ratsche 47, geschlüsselt nach `datei:zeile` |

## Existing Patterns
- Weiter-Kette auf `/compare/new` Desktop wie in `kanal-je-wettergroesse-block.staging.spec.ts` (drei Klicks bis Alarme, dann Aktivieren).
- Messung am gespeicherten Stand (`GET /api/compare/presets/{id}`), nicht an der Oberfläche — Grundsatz der Datei, bleibt.
- Mutations-Gegenprobe bei E2E: die Zusicherung muss dort geprüft werden, wo sie wirkt (der POST-Payload `display_config.channel_active_metrics`).

## Dependencies
- Upstream: Staging (`https://staging.gregor20.henemm.com`), Staging-Login (`GZ_AUTH_*` aus Staging-`.env`), `/api/compare/presets` POST/GET, `/api/locations` (Testorte).
- Downstream: keine. Kommentare haben keine Laufzeitwirkung; der Staging-Test läuft nur manuell in `/e2e-verify`.

## Existing Specs
- `docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md` — Kanal-Reiter (Anlege-Seite kommt dort nicht vor, Lücke laut Testkopf)
- `docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md` — Ablösung, AC-18 (shared/ Produktivcode unberührt, Ratsche 47)
- `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` — Soll-Liste der `context ===`-Zweige

## Risks & Considerations
- **Ratsche nach `datei:zeile`:** Kommentar-Änderungen in `shared/` müssen zeilenneutral sein (gleiche Zeilenzahl), sonst verschieben sich die eingefrorenen Schlüssel. Sicherer Weg: Ein-Zeilen-Ersatz in der Kommentarzeile selbst.
- **Renderer-/Pendant-Gates** können Edits an `shared/`-Dateien prüfen; reine Kommentar-Edits — trotzdem Commit-Wächter beachten (`reference_commit_im_worktree_drei_waechter...`).
- **Test-Aussage nicht verwässern:** Beim Reparieren darf der Test nicht still schwächer werden (z. B. Aktivieren-Klick ohne Prüfung des gespeicherten Kanal-Overrides). Er muss vorher rot (heute: Timeout am fehlenden Knopf) und nachher grün sein, und eine Verfälschung des Payloads muss ihn rot machen.
- **Login-Variablen:** Setup/Config verlangen `GZ_VALIDATOR_*`, die es für Staging nicht mehr gibt. Ohne Anpassung läuft der Test nur mit manuellem Mapping. Gleiches Muster in ~100 weiteren Staging-Setups → **nicht** hier flächig umbauen (eigener Befund, ggf. #1199); für diese Config nur so weit, dass sie ohne Handgriff läuft, falls nötig.
- **Mobil-Pfad:** Test fährt nur Desktop; `.cm-mobile` ist durch `kanal-je-wettergroesse-block` abgedeckt — kein Scope.
- **Abgrenzung:** keine Verhaltensänderung, kein Produktivcode außer Kommentaren. Scope = frontend/e2e + Kommentare → `e2e_scope` beachten (Memory: kippt im Worktree auf docs-only).
- **Verwaister Doppel-Workflow** `refactor-2727-compare-wizardstate` (phase1) bleibt liegen; kein Verhalten davon abhängig.

## Analysis

### Type
Rework (Restposten, keine Verhaltensänderung). Kein Produktfehler: ein veralteter Test und veraltete Kommentare.

### RED-Punkt gemessen (2026-11-05, Staging, Stand `2941d6c0b`)
Lauf `compare-neu-kanal-anlegen.staging.spec.ts` gegen Staging: Setup grün, Schritte (1)–(4) grün (Kanal-Reiter da, Umschalten, SMS-Abwahl, E-Mail unberührt). Abbruch **genau** in `briefingAktivieren()` :107 — Timeout 120 s, `waiting for getByTestId('compare-editor-continue-versand')`. Nur der Klickweg am Ende ist kaputt; Umfang bestätigt.

Ausführbefehl (Login-Mapping; Zugang aus der **Staging**-`.env`, nicht der Projekt-`.env`):
```bash
set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
export GZ_VALIDATOR_USER="$GZ_AUTH_USER" GZ_VALIDATOR_PASS="$GZ_AUTH_PASS"
cd frontend && npx playwright test --config e2e/playwright.compare-uebersicht-kanal.staging.config.ts e2e/compare-neu-kanal-anlegen.staging.spec.ts --reporter=line
```
Im Worktree braucht `frontend/node_modules` einen Symlink auf `/home/hem/gregor_zwanzig/frontend/node_modules` (gitignored, angelegt). Bash-Wächter der Worktree-Sitzung lehnt `source` inline ab → als Skript ausführen.

### Befunde, die gegen den Wortlaut des Issues sprechen
- Das Issue nennt den Klickweg „Wetter-Metriken → Versand". **Einen Versand-Schritt gibt es nicht mehr** (Versand liegt im `WetterMetrikenVersandPanel` in Wetter-Metriken). Echter Weg ab Wetter-Metriken (dort steht der Test schon): `compare-editor-continue-wertebereiche` → `compare-editor-continue-alarme` → `compare-editor-activate`. Freischaltung ab Alarme-Besuch (`BIS_ALARME`, Kerntest `compare_anlege_freischaltung.test.ts`). Vorbild: `kanal-je-wettergroesse-block.staging.spec.ts` `zumAlarmeReiter` (:256–268). Die ACs nennen den echten Weg.
- Das Issue nennt 11 Kommentar-Dateien; der grep findet **12 Treffer**. Der zwölfte ist `compare/compareEditorSave.test.ts:310` (Testdatei, gleiche Art veralteter Kommentar). **Entscheidung: gehört dazu** (gleicher Fix, keine Ratsche betroffen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts` | MODIFY | `briefingAktivieren()`: Versand-Klick raus, Freischaltung „nach dem Alarme-Besuch"; JSDoc und Assert-Meldung anpassen. Kopf :9 `CompareNewEditor.svelte:394/:491` → `:577/:671` (WetterMetrikenVersandPanel); Kopf :12–13 `CompareWizardState.saveNewPreset:163 -> buildNewComparePresetPayload:341/414` → `speichereNeuenVergleich` (CompareNewEditor ~:294, Kanal-Feld :327) → `buildNewComparePresetPayload` (compareEditorSave.ts:443, `channel_active_metrics` :530). Schritt-(6)-Kommentar und Redirect-Kommentar („saveNewPreset -> goto") ebenso. Zeile 1 `// gz-eigenstaendig:` bleibt. Redirect-Regex `/compare/${id}$` passt weiter (`goto('/compare/' + created.id)`, :338). |
| `frontend/src/lib/components/compare/alarmePropsAus.ts:44` | MODIFY (Kommentar) | `CompareWizardState` → lokaler `$state`-Feldsatz (`CompareFeldsatz`) |
| `frontend/src/lib/components/compare/versandPropsAus.ts:41` | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts:52` | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/corridorPropsAus.ts:35` | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/compareHubHydration.ts:34` | MODIFY (Kommentar) | Mehrzeiler mit Bindestrich-Fortsetzung; zeilenneutral umbrechen |
| `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte:20` | MODIFY (Kommentar) | historischer Satz „statt `CompareWizardState`-Bindung" umformulieren |
| `frontend/src/lib/components/compare/compareEditorSave.test.ts:310` | MODIFY (Kommentar) | `CompareWizardState.saveNewPreset()` → `speichereNeuenVergleich` (CompareNewEditor); `:394/491` → `:577/:671` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:112` | MODIFY (Kommentar, Ratsche!) | Ein-Zeilen-Ersatz |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte:39` | MODIFY (Kommentar, Ratsche!) | Ein-Zeilen-Ersatz |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:61` | MODIFY (Kommentar, Ratsche!) | Feldsatz statt Instanz; zeilenneutral |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:55` | MODIFY (Kommentar, Ratsche!) | Mehrzeiler, zeilenneutral umbrechen |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:33` | MODIFY (Kommentar, Ratsche!) | Ein-Zeilen-Ersatz |

Heutiger Zustandsträger (Formulierungsvorlage): komponentenlokales `$state<CompareFeldsatz>`-Feldobjekt, im Hub in `CompareTabs.svelte`, beim Anlegen `wiz` in `CompareNewEditor.svelte`; Typ `CompareFeldsatz` in `compare/compareEditorSave.ts:568` (Spec #2727 Variante A).

### Prüfbare Zielzustände
- `grep -rn CompareWizardState frontend/src` liefert **außerhalb** des Wächters `compare/__tests__/compare_wizard_state_entfernt.test.ts` **0 Treffer**.
- Jede geänderte Kommentar-Datei hat dieselbe Zeilenzahl wie vorher (`git diff --numstat`: added == deleted je Datei), überall, nicht nur in `shared/`.
- `context_herkunft_zweige_eingefroren.test.ts` (Ratsche 47) und `compare_wizard_state_entfernt.test.ts` grün und unverändert.
- Staging-Test: vorher rot (Timeout am Versand-Knopf, belegt oben), nachher grün gegen Staging.
- Mutations-Gegenprobe (Adversary): Mutationspunkte sind das Kanal-Feld im `buildNewComparePresetPayload({...})`-Aufruf (`CompareNewEditor.svelte:327`) und `channel_active_metrics` in `compareEditorSave.ts:530`. Die Mutation wirkt nur im laufenden Frontend; Nachweis über lokalen Dev-Server mit Mutation, dessen Vite-Proxy auf Staging zeigt (Memory `reference_lokaler_e2e_stack_zwei_fallen_proxy_zeigt_auf_staging`), Test mit `GZ_SVELTE_BASE` auf den lokalen Server → Schritt (6) muss rot werden. In der Spec festlegen.

### Scope Assessment
- Files: 13 (1 E2E-Test, 12 Kommentarstellen)
- Estimated LoC: ca. +25/-25 (Kommentare zeilenneutral)
- Risk Level: LOW — keine Laufzeitwirkung; einziges Risiko ist die zeilengeschlüsselte Ratsche (durch Zeilenneutralität abgefangen)

### Technical Approach
1. Staging-Test: in `briefingAktivieren()` den `continue-versand`-Klick streichen, Doku/Meldung auf „Alarme-Besuch" umstellen, Zeilenverweise im Kopf aktualisieren. Keine Zusicherung schwächen: Schritt (6) (gespeicherter Stand via GET) und die Null-Prüfung für E-Mail/Telegram bleiben wörtlich.
2. Kommentare: je Fundstelle Ersatz innerhalb derselben Zeilen (Mehrzeiler neu umbrechen).
3. Login-Setup **nicht** umbauen (45 Setups mit gleichem `GZ_VALIDATOR_*`-Muster → Nebenbefund #1199); Ausführbefehl mit Mapping steht oben und kommt in die Spec.

### Dependencies
Staging erreichbar, Staging-`.env`; `/api/compare/presets` POST/GET, `/api/locations`. Keine Downstream-Abhängigkeit.

### Deploy-Hinweis
Frontend-only ohne Laufzeitwirkung (Kommentare + E2E-Datei). `e2e_scope` kippt im Worktree gern auf docs-only (Memory) — beim Deploy bewusst prüfen.

### Open Questions
- keine (Nebenbefund Login-Muster der 45 Setups → #1199)
