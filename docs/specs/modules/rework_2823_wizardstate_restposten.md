---
entity_id: rework_2823_wizardstate_restposten
type: refactor
created: 2026-11-05
updated: 2026-11-05
status: draft
version: "1.0"
workflow: rework-2823-wizardstate-restposten
tags: [compare, e2e, kommentare, restposten]
issue: "#2823"
epic: "#2345"
vorgaenger: "#2727"
---

# Restposten #2727: Staging-Test Anlege-Naht und veraltete CompareWizardState-Kommentare

## Approval

- [ ] Approved

## Purpose

Der Staging-Test `compare-neu-kanal-anlegen.staging.spec.ts` ist der einzige Waechter der Anlege-Naht fuer `channel_active_metrics` auf `/compare/new`, klickt aber einen Versand-Weiter-Knopf, den es seit #1743 nicht mehr gibt (Timeout, am 2026-11-05 gegen Staging gemessen). Ausserdem nennen 12 Kommentare den seit #2727 geloeschten `CompareWizardState` noch als Zustandstraeger. Beides wird bereinigt, ohne Verhaltensaenderung und ohne die Zusicherung des Tests zu schwaechen.

## Source

- **File:** `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts`
- **Identifier:** `briefingAktivieren()` (:104-127) und Kopf-Kommentar (:5-31)

> Schicht: ausschliesslich Frontend (`frontend/e2e/`, `frontend/src/lib/components/`). Kein Go-/Python-Code.
> Trip/Compare-Teilung: keine neue Komponente, daher kein Pendant-Thema. Mandantentrennung: keine Nutzerdaten-Aenderung (der Test legt einen Vergleich des Staging-Testnutzers an und raeumt per `cleanupTracked` auf). Kanaele: Kommentar-/Testarbeit, der Test prueft SMS-Override sowie E-Mail/Telegram unberuehrt.

## Estimated Scope

- **LoC:** ca. +25/-25 (Kommentare zeilenneutral)
- **Files:** 13 (1 E2E-Test, 12 Kommentarstellen in 12 Dateien)
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts` | MODIFY | `briefingAktivieren()`: Klick auf `compare-editor-continue-versand` entfernen, Freischaltung "ab Alarme-Besuch" (JSDoc, Assert-Meldung). Kopf-Kommentar: `CompareNewEditor.svelte:394/:491` -> `:577/:671` (WetterMetrikenVersandPanel), `CompareWizardState.saveNewPreset:163 -> buildNewComparePresetPayload:341/414` -> `speichereNeuenVergleich` (CompareNewEditor.svelte:294, Kanal-Feld :327) -> `buildNewComparePresetPayload` (compareEditorSave.ts:443, `channel_active_metrics` :530). Schritt-(6)- und Redirect-Kommentar ("saveNewPreset -> goto") ebenso. Zeile 1 `// gz-eigenstaendig:` bleibt. |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` (:44) | MODIFY (Kommentar) | `CompareWizardState` -> lokaler `$state`-Feldsatz (`CompareFeldsatz`) |
| `frontend/src/lib/components/compare/versandPropsAus.ts` (:41) | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts` (:52) | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/corridorPropsAus.ts` (:35) | MODIFY (Kommentar) | dito |
| `frontend/src/lib/components/compare/compareHubHydration.ts` (:34) | MODIFY (Kommentar) | Mehrzeiler, zeilenneutral umbrechen |
| `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte` (:20) | MODIFY (Kommentar) | historischen Satz "statt `CompareWizardState`-Bindung" umformulieren |
| `frontend/src/lib/components/compare/compareEditorSave.test.ts` (:310) | MODIFY (Kommentar) | `CompareWizardState.saveNewPreset()` -> `speichereNeuenVergleich` (CompareNewEditor) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (:112) | MODIFY (Kommentar, Ratsche) | Ein-Zeilen-Ersatz |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte` (:39) | MODIFY (Kommentar, Ratsche) | Ein-Zeilen-Ersatz |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` (:61) | MODIFY (Kommentar, Ratsche) | Feldsatz statt Instanz, zeilenneutral |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` (:55) | MODIFY (Kommentar, Ratsche) | Mehrzeiler, zeilenneutral umbrechen |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` (:33) | MODIFY (Kommentar, Ratsche) | Ein-Zeilen-Ersatz |

### Out of Scope

- Login-Setup `GZ_VALIDATOR_*` (Setup/Config der Staging-Suiten, ca. 45 Setups mit gleichem Muster) wird NICHT umgebaut; Nebenbefund, Sammel-Issue #1199. Der Test laeuft mit dem Mapping im Ausfuehrbefehl unten.
- Mobil-Pfad (`.cm-mobile`): abgedeckt durch `kanal-je-wettergroesse-block.staging.spec.ts`.
- Nennungen von `CompareWizardState` in Testdateien unter `__tests__/` (u. a. die Waechter `compare_wizard_state_entfernt.test.ts`, `compare_wetter_metriken_wertprops.test.ts`, `compare_alarme_wertprops.test.ts`, `compare_versand_wertprops.test.ts`, `compare_corridor_wertprops.test.ts`, `issue_683_wizard_remove.test.ts`): zum Teil Waechter-Literale, bleiben unveraendert.
- Der verwaiste Doppel-Workflow `refactor-2727-compare-wizardstate` bleibt liegen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Staging `https://staging.gregor20.henemm.com` | environment | Lauf des Staging-Tests |
| Staging-`.env` (`/home/hem/gregor_zwanzig_staging/.env`, `GZ_AUTH_USER/PASS`) | config | Login, gemappt auf `GZ_VALIDATOR_*` |
| `/api/compare/presets` (POST/GET), `/api/locations` | API | Anlegen, Messung am gespeicherten Stand, Testorte |
| `compare-uebersicht-kanal.helpers.ts`, `helpers.ts` | test helper | Selektoren, Warteregel #1423, Cleanup |
| `kanal-je-wettergroesse-block.staging.spec.ts` (:256-268, `zumAlarmeReiter`) | vorbild | aktueller Klickweg |
| `compare_anlege_freischaltung.test.ts` | kerntest | belegt: Aktivieren ab Alarme-Besuch freigeschaltet (`BIS_ALARME`) |
| `context_herkunft_zweige_eingefroren.test.ts` (Ratsche 47), `compare_wizard_state_entfernt.test.ts` | waechter | muessen gruen und unveraendert bleiben |

## Implementation Details

1. **Staging-Test:** In `briefingAktivieren()` den Klick auf `compare-editor-continue-versand` streichen. Echter Weg ab Wetter-Metriken (dort steht der Test schon): `compare-editor-continue-wertebereiche` -> `compare-editor-continue-alarme` -> `compare-editor-activate`; Versand steckt im `WetterMetrikenVersandPanel` (Wetter-Metriken). Freischaltungs-Meldung des `toBeEnabled`-Asserts auf "nach dem Alarme-Besuch" umstellen. Schritt (6) (GET `/api/compare/presets/{id}`, `display_config.channel_active_metrics` mit SMS-Override, E-Mail/Telegram ohne Eintrag) und alle Zusicherungen der Schritte (1)-(5) bleiben wortgleich. Redirect-Regex `/compare/${id}$` bleibt (`goto('/compare/' + created.id)`).
2. **Kommentare:** je Fundstelle Ersatz innerhalb derselben Zeilen; Mehrzeiler neu umbrechen; Formulierung: "lokaler `$state`-Feldsatz (`CompareFeldsatz`, compareEditorSave.ts:568)". Keine Codezeile aendert sich.
3. **Ratsche:** Weil `context_herkunft_zweige_eingefroren.test.ts` nach `datei:zeile` schluesselt, ist Zeilenneutralitaet Pflicht.

Ausfuehrbefehl des Staging-Tests (als Skript ausfuehren, weil der Bash-Waechter `source` inline ablehnt; im Worktree Symlink `frontend/node_modules` -> `/home/hem/gregor_zwanzig/frontend/node_modules`):

```bash
set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
export GZ_VALIDATOR_USER="$GZ_AUTH_USER" GZ_VALIDATOR_PASS="$GZ_AUTH_PASS"
cd frontend && npx playwright test --config e2e/playwright.compare-uebersicht-kanal.staging.config.ts e2e/compare-neu-kanal-anlegen.staging.spec.ts --reporter=line
```

Mutations-Gegenprobe (Adversary, per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`): Das Kanal-Feld in `CompareNewEditor.svelte:327` (`channelActiveMetricKeys: { ...wiz.channelActiveMetricKeys }` -> `{}`) bzw. `channel_active_metrics` in `compareEditorSave.ts:530` wird verfaelscht. Die Mutation wirkt nur im laufenden Frontend; Nachweis ueber lokalen Dev-Server mit Mutation, dessen Vite-Proxy auf Staging zeigt, und den Test mit `GZ_SVELTE_BASE` auf diesen Server. Erwartung: Schritt (6) wird rot. Danach Mutation vollstaendig zurueckspielen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] RED (bereits gemessen 2026-11-05, Stand `2941d6c0b`): Staging-Test bricht in `briefingAktivieren()` :107 mit Timeout 120 s ab (`waiting for getByTestId('compare-editor-continue-versand')`); Schritte (1)-(4) vorher gruen.
- [ ] GREEN: derselbe Staging-Test nach der Reparatur gegen Staging gruen.
- [ ] Mutations-Gegenprobe wie oben: Test rot bei verfaelschtem Payload-Kanalfeld, gruen nach Rueckspielen.
- [ ] `grep -rn CompareWizardState frontend/src --include='*' --exclude-dir=__tests__` liefert 0 Treffer.
- [ ] `git diff --numstat`: je Kommentar-Datei added == deleted.
- [ ] Kern-Schicht: `node --test` fuer `context_herkunft_zweige_eingefroren.test.ts`, `compare_wizard_state_entfernt.test.ts`, `compare_anlege_freischaltung.test.ts`, `compareEditorSave.test.ts` gruen; zuerst die ersten beiden unveraendert.

## Expected Behavior

- **Input:** unverändert — Nutzer legt auf `/compare/new` einen Ortsvergleich an und wählt per Kanal-Reiter eine SMS-eigene Metrik-Auswahl.
- **Output:** unverändert — gespeicherter Vergleich trägt `display_config.channel_active_metrics` mit SMS-Override, E-Mail/Telegram ohne Eintrag.
- **Side effects:** keine. Änderung betrifft nur den Klickweg des Staging-Tests und Kommentartext; keine Laufzeitwirkung.

## Acceptance Criteria

- **AC-1:** Given der Staging-Test `compare-neu-kanal-anlegen.staging.spec.ts` ist vor der Reparatur rot (Timeout am Knopf `compare-editor-continue-versand`, :107) / When er nach der Reparatur mit dem Ausfuehrbefehl gegen Staging laeuft / Then er ist gruen und faehrt den echten Klickweg Wetter-Metriken -> `compare-editor-continue-wertebereiche` -> `compare-editor-continue-alarme` -> `compare-editor-activate`, ohne `compare-editor-continue-versand` zu nennen.
  - Test: Nutzer legt auf `/compare/new` (Desktop) einen Vergleich mit zwei Orten an, schaltet im SMS-Reiter eine Metrik ab und aktiviert das Briefing; Weiterleitung auf `/compare/{id}`.

- **AC-2:** Given der reparierte Test / When Schritt (6) den gespeicherten Vergleich per GET `/api/compare/presets/{id}` liest / Then `display_config.channel_active_metrics` enthaelt den SMS-Override der abgewaehlten Metrik, und E-Mail und Telegram haben keinen Eintrag, wortgleich zur Zusicherung vor der Reparatur (keine Schwaechung).
  - Test: Messung am gespeicherten Server-Stand, nicht an der Oberflaeche; Diff des Tests zeigt Aenderungen nur in `briefingAktivieren()` und Kommentaren.

- **AC-3:** Given das Kanal-Feld im POST-Payload ist per Mutation verfaelscht (`channelActiveMetricKeys` in `CompareNewEditor.svelte:327` leer bzw. `channel_active_metrics` in `compareEditorSave.ts:530` entfernt) und das Frontend laeuft lokal mit Vite-Proxy auf Staging / When der Test mit `GZ_SVELTE_BASE` auf den lokalen Server laeuft / Then Schritt (6) schlaegt fehl (Test rot), und nach Rueckspielen der Mutation ist er wieder gruen.
  - Test: Adversary-Lauf, Mutation per String-Ersetzung mit externer Sicherungskopie; Ergebnis rot/gruen im Bericht.

- **AC-4:** Given die 12 veralteten Kommentar-Fundstellen / When `grep -rn CompareWizardState frontend/src` ausserhalb der Verzeichnisse `__tests__/` laeuft / Then es liefert 0 Treffer (inkl. `compare/compareEditorSave.test.ts:310`); der Wortlaut in den Kommentaren nennt stattdessen den lokalen `$state`-Feldsatz (`CompareFeldsatz`) bzw. `speichereNeuenVergleich`.
  - Test: grep-Nachweis ist hier Doku-Pruefung der Kommentarbereinigung (# doc-compliance-test); Laufzeitverhalten wird durch AC-5 und AC-6 bewiesen.

- **AC-5:** Given jede der 12 geaenderten Kommentar-Dateien / When `git diff --numstat` gegen `origin/main` laeuft / Then added == deleted je Datei, und `context_herkunft_zweige_eingefroren.test.ts` (Ratsche 47) sowie `compare_wizard_state_entfernt.test.ts` sind unveraendert und gruen.
  - Test: `node --test` beider Dateien; Ratsche bleibt bei 47 eingefrorenen Schluesseln.

- **AC-6:** Given der Stand nach dem Merge / When die Kern-Schicht (`compare_anlege_freischaltung.test.ts`, `compareEditorSave.test.ts`) laeuft und der Diff gelesen wird / Then alle Tests sind gruen und der Diff enthaelt ausser Kommentaren und der E2E-Datei keine Produktivcode-Aenderung (keine Verhaltensaenderung).
  - Test: Der Anlege-Weg erzeugt weiterhin genau einen POST mit unveraendertem Payload; Kommentar-Diff enthaelt nur Zeilen, die mit `//`, `*` oder `/**` beginnen.

- **AC-7:** Given der Kopf-Kommentar des Staging-Tests / When er gelesen wird / Then alle Zeilenverweise stimmen mit dem Code ueberein (`CompareNewEditor.svelte:577/:671`, `speichereNeuenVergleich` :294, Kanal-Feld :327, `buildNewComparePresetPayload` compareEditorSave.ts:443, `channel_active_metrics` :530) und kein Verweis auf `CompareWizardState` oder `saveNewPreset` bleibt.
  - Test: Zeilenverweise werden vor dem Commit gegen die Dateien gegengelesen (# doc-compliance-test).

## Known Limitations

- Der Staging-Test ist nicht in CI und laeuft nur manuell in `/e2e-verify`; die Login-Variablen `GZ_VALIDATOR_*` muessen per Mapping gesetzt werden (Nebenbefund #1199).
- Zeilenverweise im Kopf-Kommentar koennen bei kuenftigen Aenderungen der Quelldateien wieder veralten; die Verweise nennen deshalb auch den Funktionsnamen.
- Deploy-Hinweis: Frontend-only ohne Laufzeitwirkung (Kommentare + E2E-Datei). `e2e_scope` kippt im Worktree gern auf docs-only; beim Deploy bewusst pruefen und den Nachweis `.claude/e2e_verified/<sha>.json` regulaer erzeugen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Restposten-Bereinigung (Test-Klickweg und Kommentare) ohne Entscheidungsflaeche; die Ablaesung von `CompareWizardState` ist bereits in Spec `feat_2727_compare_wizardstate_abloesen.md` entschieden.

## Changelog

- 2026-11-05: Initial spec created (Issue #2823, Restposten aus #2727)
