---
entity_id: fix_2047_s2_ci_prod_gate
type: bugfix
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "2.0"
workflow: fix-2047-s2-prod-gate
tags: [ci, deploy, prod-gate, adr-0006, idempotenz, selbsttest]
---

# #2047 Scheibe 2b — CI-Auslieferung absichern: Idempotenz, Selbsttest, Serialisierung

## Approval

- [ ] Approved

## Purpose

Die CI liefert seit PR #2516 nach Produktion aus, sobald ein echter `/e2e-verify`-Nachweis für den
Stand vorliegt. Diese Ergänzung sichert diesen Weg ab: Wird derselbe Stand von CI und Session
ausgeliefert, startet er die Dienste nicht doppelt neu; zwei CI-Läufe laufen nie gleichzeitig; nach
jeder CI-Auslieferung läuft der Post-Deploy-Selbsttest; und die Telegram-Meldung unterscheidet
sauber „ausgeliefert", „bereits ausgeliefert" und „fehlgeschlagen".

## Kontext

- Die ursprüngliche Fassung dieser Spec (CI wartet bis zu 60 Minuten per `ci_wait_for_verdict.sh`
  auf den Nachweis) wurde durch PR #2516 überholt: Dort ist die CI bereits reiner Leser, `deploy.needs`
  umfasst alle 6 Ampel-Jobs, es gibt keinen Verdict-Schreiber und kein `git reset --hard` mehr, und
  `scripts/ci_prod_gate.sh` prüft einmalig (Step `gate`, Output `open=true|false`). Die Doku
  (CLAUDE.md, `/70-deploy`, Playbook, Gate-Referenz) wurde dort nachgezogen.
- PO-Entscheid 2026-10-06 „Auf Hauptstand aufbauen": Das Warte-Skript entfällt ersatzlos; diese Spec
  enthält nur noch das Delta zu #2516.
- Offene Lücken nach #2516: (a) bei `open` liefern CI und Session (`/70-deploy`) beide aus, was die
  Dienste doppelt neu startet; (b) der Job `deploy` hat keine Serialisierung; (c) im CI-Pfad läuft
  kein Post-Deploy-Selbsttest; (d) „bereits ausgeliefert" ist von „deployed" nicht unterscheidbar.

## Source

- **File:** `.github/workflows/ci.yml` (Job `deploy`); Fremd-Repo-Datei
  `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh`
- **Identifier:** Job `deploy` (Schritte nach `gate`); Shell-Skript `deploy-gregor-prod.sh`
  (Idempotenz-Kurzschluss)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/ci_prod_gate.sh` / Step `gate` (aus #2516) | Skript/Step | Liefert `open=true\|false`; bleibt unverändert |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Skript (Fremd-Repo, sofort live) | Erhält den Idempotenz-Kurzschluss; muss VOR dem ci.yml-PR in henemm-infra committet und gepusht sein |
| `.claude/last_prod_deploy.json` | Datei | Quelle von `deployed_commit` für den Kurzschluss |
| `.claude/hooks/prod_selftest.py` | Hook | Post-Deploy-Selbsttest, läuft künftig auch im CI-Pfad |
| `tests/test_ci_prod_gate.py` (aus #2516) | Test | Darf durch diese Änderung nicht rot werden |
| `docs/adr/0006-*.md` | ADR | Wird durch das neue ADR ergänzt, nicht abgelöst |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY | Idempotenz-Kurzschluss im flock nach `git fetch origin`, Notausgang `GZ_FORCE_REDEPLOY=1` mit Eintrag in `.claude/deploy-overrides.log` (Patch: `docs/artifacts/fix-2047-s2-prod-gate/infra-idempotenz.patch`) |
| `/home/hem/henemm-infra/tests/test_deploy_gregor_prod_idempotenz.py` | CREATE | 4 Tests (bereits vorhanden und grün) |
| `.github/workflows/ci.yml` | MODIFY | `concurrency`, Selbsttest-Schritt, `already`-Erkennung, drei Telegram-Meldungen |
| `tests/tdd/test_ci_deploy_gate.py` | MODIFY | Wird in /40 neu geschrieben (`# doc-compliance-test`) |
| `tests/test_ci_wartet_auf_staging_nachweis.py` | DELETE | Prüfte das entfallene Warte-Skript |
| `scripts/ci_wait_for_verdict.sh` | DELETE | Nie ausgeliefert, entfällt ersatzlos (nur im Arbeitsbaum untracked) |
| `docs/adr/0085-ci-auto-deploy-nur-mit-echtem-e2e-verify-nachweis.md` | CREATE | Neues ADR (Nummer vor dem Anlegen per `git ls-tree origin/main docs/adr/` bestätigen; ist 0085 belegt, nächste freie Nummer) |
| `docs/adr/README.md` | MODIFY | Index-Eintrag; `tests/test_adr_index_drift.py` muss grün bleiben |
| `.claude/commands/e2e-verify.md` | MODIFY | Veralteter Dateiname `e2e_verified.json` (ca. Z.69) auf `.claude/e2e_verified/<sha>.json` |
| `docs/reference/operations_playbook.md` | MODIFY | Kurz: Selbsttest im CI-Pfad, Idempotenz, `concurrency` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Kurz: Notausgang `GZ_FORCE_REDEPLOY=1`, Telegram-Ausschluss |
| `docs/specs/modules/ci_wip_sicherung.md` | MODIFY | Nachtrag „CI-Aufrufer mit #2047 S2 entfallen" (nur falls nicht schon vorhanden) |

### Estimated Changes

- Files: 12 (davon 2 Löschungen, 1 Fremd-Repo-Skript + 1 Fremd-Repo-Test)
- LoC: +190/-120 (ohne Doku und gelöschte Dateien)

## Implementation Details

1. **Idempotenz (henemm-infra):** Im Deploy-Skript, innerhalb des `flock`, nach `git fetch origin`
   und vor jeder Dienstaktion: Ist `deployed_commit` aus `.claude/last_prod_deploy.json` gleich
   `git rev-parse origin/main`, meldet das Skript „bereits ausgeliefert" und beendet sich mit Exit 0,
   ohne Dienstaktion. Mit `GZ_FORCE_REDEPLOY=1` wird trotzdem ausgeliefert, und ein Eintrag landet in
   `.claude/deploy-overrides.log`. Rollout-Reihenfolge: infra-Commit und Push zuerst, dann der
   ci.yml-PR (das Skript wirkt sofort live).
2. **Serialisierung:** Job `deploy` erhält `concurrency: {group: prod-deploy, cancel-in-progress: false}`;
   ein zweiter Merge reiht sich ein, bricht den laufenden Deploy nicht ab.
3. **Selbsttest:** Nach dem Deploy-Schritt, nur bei `steps.gate.outputs.open == 'true'`, genau ein
   ssh-Aufruf `cd /home/hem/gregor_zwanzig && python3 .claude/hooks/prod_selftest.py`. Exit ≠ 0 lässt
   den Job rot werden (kein `|| true`, kein `set +e` ohne Weitergabe).
4. **already-Erkennung:** Der Deploy-Schritt erhält `id: deploy`, fängt die Skriptausgabe ab, gibt sie
   weiter aus und setzt Output `already=true`, wenn die Ausgabe „bereits ausgeliefert" enthält,
   sonst `already=false`. Der Skript-Exitcode bleibt maßgeblich.
5. **Telegram:** Drei sich ausschließende Schritte: „gregor20 deployed" bei
   `success() && open == 'true' && already != 'true'`; „bereits ausgeliefert" bei
   `success() && open == 'true' && already == 'true'`; „FEHLGESCHLAGEN" bei `failure()`. Bei `closed`
   keine Meldung (wie heute auf main). Commit-Message nur per `env:`, nie per `${{ }}` im Shell-Text.
6. **ADR:** Hält fest: CI schreibt nie einen Nachweis, prüft einmal, liefert idempotent aus und führt
   den Selbsttest aus; Ergänzung zu ADR-0006.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Infra (4 Tests, vorhanden): Kurzschluss bei gleichem Stand; Notausgang liefert trotzdem aus und
      protokolliert; älterer Stand liefert normal; Prüfung liegt innerhalb des flock.
- [ ] `tests/tdd/test_ci_deploy_gate.py` (mit `# doc-compliance-test`, `yaml.safe_load`, run-Texte mit
      Ersatz-ssh/curl real ausgeführt), je Test mit Mutation:
  - GIVEN ci.yml WHEN Job `deploy` geladen THEN `concurrency` mit Gruppe `prod-deploy` und
    `cancel-in-progress: false` (Mutation: Gruppe entfernt oder `true`).
  - GIVEN Schritt Selbsttest WHEN Schrittliste gelesen THEN steht er nach dem Deploy-Schritt, hat
    `if` auf `open`, enthält genau einen ssh-Aufruf mit `prod_selftest.py` (Mutation: `|| true`,
    zweiter ssh-Aufruf, `if` entfernt).
  - GIVEN Ersatz-ssh mit Exit 1 WHEN der Selbsttest-run-Text ausgeführt THEN Exit ≠ 0 (Mutation:
    Exitcode verschluckt).
  - GIVEN Ersatz-ssh, dessen Ausgabe „bereits ausgeliefert" enthält / nicht enthält WHEN der
    Deploy-run-Text ausgeführt THEN `already=true` bzw. `already=false` in `GITHUB_OUTPUT`
    (Mutation: Suchtext verändert).
  - GIVEN die `if`-Bedingungen der drei Telegram-Schritte WHEN alle Kombinationen aus Jobstatus
    (success, failure, cancelled) × open × already ausgewertet THEN feuert je Kombination höchstens
    ein Schritt, bei `closed` keiner, und „deployed" nie bei `already=true` (Mutation: Bedingung
    gelockert, sodass zwei Schritte gleichzeitig feuern).
- [ ] `tests/test_ci_prod_gate.py` (aus #2516) bleibt grün.
- [ ] `tests/test_adr_index_drift.py` bleibt grün.

## Expected Behavior

- **Input:** Merge nach `main`, CI grün, Gate `open` bzw. `closed`.
- **Output:** Bei `open`: Deploy (oder Kurzschluss „bereits ausgeliefert"), Selbsttest, genau eine
  Telegram-Meldung. Bei `closed`: wie heute, Notice und Step-Summary, keine Telegram-Meldung.
- **Side effects:** Kein zweiter Dienst-Neustart für denselben Stand.

## Acceptance Criteria

- [ ] **AC-1:** Given in `.claude/last_prod_deploy.json` steht `deployed_commit` gleich `git rev-parse origin/main` / When `deploy-gregor-prod.sh` läuft / Then meldet es „bereits ausgeliefert", beendet sich mit Exit 0 und führt keine einzige Dienstaktion (Restart, Build) aus.
- [ ] **AC-2:** Given derselbe Stand ist bereits ausgeliefert und `GZ_FORCE_REDEPLOY=1` ist gesetzt / When `deploy-gregor-prod.sh` läuft / Then liefert es trotzdem aus und schreibt einen Eintrag in `.claude/deploy-overrides.log`.
- [ ] **AC-3:** Given `deployed_commit` ist älter als `origin/main` / When `deploy-gregor-prod.sh` läuft / Then liefert es normal aus, und die Stand-Prüfung geschieht innerhalb des flock nach `git fetch origin`, also nie vor dem Lock.
- [ ] **AC-4:** Given der Job `deploy` in `ci.yml` / When die Workflow-Datei geparst wird / Then hat er `concurrency` mit Gruppe `prod-deploy` und `cancel-in-progress: false`, sodass zwei Merges nie gleichzeitig ausliefern und kein laufender Deploy abgebrochen wird.
- [ ] **AC-5:** Given das Gate meldet `open=true` und der Deploy ist durchgelaufen / When der Job weiterläuft / Then führt genau ein ssh-Aufruf `python3 .claude/hooks/prod_selftest.py` im Hauptordner aus, und ein Exit ≠ 0 des Selbsttests macht den Job rot.
- [ ] **AC-6:** Given das Gate meldet `open=false` / When der Job läuft / Then wird weder Deploy noch Selbsttest noch eine Telegram-Meldung ausgeführt, und die Notice samt Step-Summary aus #2516 bleibt erhalten.
- [ ] **AC-7:** Given die Ausgabe des Deploy-Skripts enthält „bereits ausgeliefert" / When der Deploy-Schritt endet / Then steht `already=true` im Step-Output, andernfalls `already=false`.
- [ ] **AC-8:** Given beliebige Kombination aus Jobstatus, `open` und `already` / When die `if`-Bedingungen der drei Telegram-Schritte ausgewertet werden / Then feuert höchstens ein Schritt je Lauf, „deployed" nie bei `already=true`, „FEHLGESCHLAGEN" nur bei `failure()`, und bei `closed` keiner.
- [ ] **AC-9:** Given `tests/test_ci_prod_gate.py` aus #2516 und das ADR-Index-Drift-Test / When sie nach dieser Änderung laufen / Then sind beide grün, und `tests/test_ci_wartet_auf_staging_nachweis.py` sowie `scripts/ci_wait_for_verdict.sh` existieren nicht mehr.
- [ ] **AC-10:** Given das neue ADR 0085 / When `docs/adr/README.md` und die ADR-Dateien verglichen werden / Then ist es als Ergänzung zu ADR-0006 im Index gelistet und hält fest: CI schreibt nie einen Nachweis, prüft einmal, liefert idempotent aus und führt den Selbsttest aus.
- [ ] **AC-11:** Given `.claude/commands/e2e-verify.md` und die Referenzdoku / When nach dieser Änderung gelesen / Then nennt `e2e-verify.md` den Nachweis-Pfad `.claude/e2e_verified/<sha>.json` statt `e2e_verified.json`, und Playbook bzw. Gate-Referenz erwähnen Selbsttest, Idempotenz mit Notausgang und `concurrency`.

## Known Limitations

- Der Normalfall bleibt `closed`: `/e2e-verify` läuft erst nach dem Merge, der CI-Job direkt danach.
  Die Auslieferung geschieht dann weiterhin per `/70-deploy` aus der Session; die CI liefert nur aus,
  wenn der Nachweis schon vorliegt (z. B. docs-only oder nachträglich wiederholter Lauf).
- Nächtliches Rot-Fenster: Der `test`-Job ist täglich 22:00-02:30 UTC strukturell rot; in dieser Zeit
  läuft `deploy` nicht, die Auslieferung geschieht per `/70-deploy`.
- Der Kurzschluss vergleicht nur `deployed_commit` mit `origin/main`; ein manuell verändertes
  `last_prod_deploy.json` würde ihn täuschen (Notausgang `GZ_FORCE_REDEPLOY=1` bleibt).

## Changelog

- 2026-10-06: Initial spec created (Fassung 1.0: CI wartet auf Nachweis)
- 2026-10-06: Überarbeitung auf Hauptstand nach PR #2516 (PO-Entscheid „Auf Hauptstand aufbauen"): Warte-Skript entfällt, Spec reduziert auf Delta (Idempotenz, Serialisierung, Selbsttest, Telegram-Ausschluss, ADR)
