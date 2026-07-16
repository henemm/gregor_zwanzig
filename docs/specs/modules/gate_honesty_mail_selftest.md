---
entity_id: gate_honesty_mail_selftest
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [hooks, gates, mail-validators, prod-selftest, bugfix]
---

<!-- Fix-Workflow fix-1282-1283-gate-honesty — Issues #1282, #1283 -->

# Gate Honesty: Renderer-Mail-Gate für Compare-Mails + prod_selftest Scope-Diff-Basis

## Approval

- [x] Approved (PO „freigabe" 2026-07-16)

## Purpose

Zwei unabhängige Gate-Bugs mit dem gemeinsamen Muster **„ein Wächter meldet
Erfolg, ohne zu prüfen"** beheben. (1) Das Renderer-Mail-Gate (#811) ist für
Compare-Mails wirkungslos: ein No-Op-Validator schreibt `passed: true` und das
Gate akzeptiert einen fachlich falschen Nachweis — Compare-Mail-Bugs können
so ungeprüft in Prod gelangen (#1282). (2) `prod_selftest.py` überspringt
echte Code-Deploys fälschlich als „docs-only", sobald ein reiner
Doku-Commit über einem Code-Commit liegt — Verifikation entfällt dann
komplett für den ausgelieferten Code (#1283). Beide Fixes machen die
jeweiligen Gates strenger und ehrlicher, ohne bestehende legitime Nachweise
zu brechen.

## Source

- **File:** `.claude/hooks/renderer_mail_gate.py` — Identifier: neue Funktionen `_is_compare_file`, `_compare_validator_log_ok`, neue Konstante `_COMPARE_PATTERNS`, Wiring in `_do_hook`
- **File:** `.claude/hooks/briefing_mail_validator.py` — Identifier: No-Op-Zweig für `mail_type in ("compare", "deviation-alert")`, `_write_validation_log`
- **File:** `.claude/hooks/email_spec_validator.py` — Identifier: log_dir-Ermittlung vor dem `_write_validation_log`-Aufruf
- **File:** `.claude/hooks/radar_alert_mail_validator.py` — Identifier: log_dir-Ermittlung vor dem `_write_validation_log`-Aufruf
- **File:** `.claude/hooks/official_alert_mail_validator.py` — Identifier: log_dir-Ermittlung vor dem `_write_validation_log`-Aufruf
- **File:** `.claude/hooks/prod_selftest.py` — Identifier: `_scope_diff_base`
- **File:** `henemm-infra/scripts/deploy-gregor-prod.sh` (Cross-Repo) — Identifier: Marker-Write-Block, der `last_prod_deploy.json` schreibt

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | Neuer Compare-Zweig (`_COMPARE_PATTERNS`, `_compare_validator_log_ok`, spiegelt `_official_validator_log_ok`); `compare_html.py` raus aus `briefing_staged`; geteilte Helfer verlangen beide Nachweise |
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | No-Op-Zweig (compare/deviation-alert) schreibt `passed: false, skipped: true` und beendet mit Exit ≠ 0 statt `return True`; log_dir auf `shared_repo_dir()` umgestellt |
| `.claude/hooks/email_spec_validator.py` | MODIFY | log_dir auf `shared_repo_dir()` umgestellt (Fail-soft-Fallback auf `__file__`-relativ) |
| `.claude/hooks/radar_alert_mail_validator.py` | MODIFY | log_dir auf `shared_repo_dir()` umgestellt (gleicher Bug wie oben) |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | log_dir auf `shared_repo_dir()` umgestellt (gleicher Bug wie oben) |
| `.claude/hooks/prod_selftest.py` | MODIFY | Neuer `previous_commit`-Zweig in `_scope_diff_base` mit höchster Priorität, `git cat-file -e`-Guard, `≠HEAD`-Guard; bestehende Fallback-Kette (#1121 Fail-closed) bleibt erhalten |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY (Cross-Repo) | Marker-JSON schreibt zusätzlich `previous_commit: $LOCAL` (Vor-Deploy-Commit, bereits als `$LOCAL` erfasst) |
| `tests/tdd/test_renderer_gate_compare_dispatch.py` | CREATE | Kern-Tests: Compare-Zweig-Erkennung, Ausschluss aus `briefing_staged`, geteilte-Helfer-Regel |
| `tests/tdd/test_briefing_validator_noop_not_pass.py` | CREATE | Kern-Tests: No-Op ≠ Pass, `skipped`-Feld, Exit-Code |
| `tests/tdd/test_validator_log_shared_repo_path.py` | CREATE | Kern-Tests: alle 4 Validatoren schreiben nach shared-repo `_log`, Fail-soft-Fallback |
| `tests/tdd/test_prod_selftest_scope_diff_base.py` | CREATE | Kern-Tests: Diff-Basis-Regressionsmatrix (5 Szenarien) |

## Estimated Scope

- **LoC:** ~95–120 Produktionscode (Kern); generierte/Test-Dateien zählen nicht gegen das 250-LoC-Budget
- **Files:** 7 Produktionsdateien (6× `gregor_zwanzig` + 1× `henemm-infra`) + 4 Kern-Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/_e2e_paths.py::shared_repo_dir()` | intern | git-common-dir-Auflösung — Ziel-Verzeichnis für Validator-Log-Schreiben (Fix C); wird vom Gate selbst bereits für das Lesen genutzt |
| `.claude/hooks/_e2e_paths.py::head_sha()` / `read_last_gate_scope*()` | intern | bestehende Scope-Diff-Fallback-Kette in `prod_selftest.py`; `previous_commit` reiht sich mit höchster Priorität davor ein |
| `git` (`git cat-file -e`, `git diff --cached`, `git rev-parse`) | extern | Existenz-Check für `previous_commit`, Diff-Berechnung für Gate und Selftest |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | cross-repo | schreibt `previous_commit` in `last_prod_deploy.json` — Voraussetzung für AC-7; eigener Commit + MQ an `infra` (siehe Cross-Repo-Hinweis) |
| `docs/reference/mail_validators.md` | doc | beschreibt die bestehende Dispatch-Tabelle briefing vs. compare; wird durch diesen Fix nicht neu erfunden, nur korrekt durchgesetzt |
| `tests/tdd/test_issue_1084_gate_scope_cache.py` | Vorbild | Muster für die temp-git-Fixture, die die neue Diff-Basis-Regressionsmatrix nutzt |

## Implementation Details

### Fix B — Compare-Zweig im Renderer-Mail-Gate (#1282)

`_COMPARE_PATTERNS` (analog `_RADAR_PATTERNS`/`_OFFICIAL_PATTERNS`) erfasst
`compare_html.py`. Eine neue `_compare_validator_log_ok()` spiegelt
`_official_validator_log_ok()`: sie verlangt ein frisches
`*_email_validation.yaml` (Quelle: `email_spec_validator.py`) mit
`passed: true` und `validated_at` jünger als die mtime der gestagten
Mail-Datei. In `_do_hook` wird `compare_html.py` aus der `briefing_staged`-
Menge entfernt — sie darf NICHT länger (nur) einen `briefing_validation.yaml`-
Nachweis verlangen, sonst bleibt das Gate für Compare-Änderungen strukturell
unbestehbar (Gate-Erosion in die andere Richtung). Geteilte Renderer-Helfer
(`helpers.py`, `design_tokens.py`, `profile_signature.py`) werden zusätzlich
in eine neue `shared_staged`-Menge aufgenommen: ein Commit, der einen dieser
Helfer staged, verlangt BEIDE Nachweise (briefing UND compare), weil beide
Renderer-Pfade sie importieren.

### Fix A — No-Op ≠ Pass in `briefing_mail_validator.py` (#1282)

Der bestehende No-Op-Zweig für `mail_type in ("compare", "deviation-alert")`
gibt aktuell `return True` zurück, was in ein `passed: true`-YAML mündet.
Er wird umgestellt: Exit-Code ≠ 0, YAML trägt `passed: false` UND
`skipped: true`. Das Gate wertet `passed: false` grundsätzlich als
unzureichenden Nachweis — `skipped` dient nur der Diagnose im Log. Diese
Härtung schließt zusätzlich ein Briefing-False-Green-Loch, unabhängig vom
neuen Compare-Zweig (Fix B).

### Fix C — Worktree-Sichtbarkeit aller vier Validatoren (#1282)

Alle vier Validatoren (`briefing_mail_validator.py`,
`email_spec_validator.py`, `radar_alert_mail_validator.py`,
`official_alert_mail_validator.py`) ermitteln ihr Log-Zielverzeichnis
aktuell `__file__`-relativ (`hooks_dir.parent/workflows/_log`). Das Gate
selbst liest über `_shared_repo_root()` aus dem shared-repo (git-common-dir).
Läuft ein Validator in einem Worktree, schreibt er dort — das Gate im
Hauptrepo sieht den Nachweis nie (False-Block/Worktree-Selbst-DoS). Fix:
alle vier stellen ihren log_dir über `_e2e_paths.shared_repo_dir()` her,
mit Fail-soft-Fallback auf die bisherige `__file__`-relative Berechnung,
falls `shared_repo_dir()` `None` liefert (z. B. außerhalb eines Git-Repos).

### Fix #1283 — `previous_commit`-Zweig in `prod_selftest.py` + Deploy-Script

`deploy-gregor-prod.sh` erfasst den Vor-Deploy-Commit bereits als `$LOCAL`
(vor `git reset --hard origin/main`), verwirft ihn aber beim Schreiben des
Markers — dort steht nur `deployed_commit` (= HEAD nach dem Deploy). Der Fix
ergänzt den Marker-Write-Block um `previous_commit: $LOCAL`. In
`_scope_diff_base` wird ein neuer Zweig mit HÖCHSTER Priorität eingezogen
(vor dem bestehenden `deployed_commit`-Zweig): liegt `previous_commit` im
Marker vor, ist er ≠ HEAD und via `git cat-file -e <sha>` auflösbar, wird er
als Diff-Basis genutzt — der gesamte seit dem letzten Prod-Deploy
ausgerollte Bereich wird geprüft, auch wenn obenauf ein reiner Doku-Commit
liegt. Fehlt `previous_commit` (alter Marker vor diesem Fix, oder
Erst-Deploy), greift unverändert die bestehende Fallback-Kette
(`deployed_commit`≠HEAD → Gate-Marker≠HEAD → `HEAD~1`), die bereits
fail-closed konzipiert ist (#1121).

## Expected Behavior

- **Input:** Ein gestagter Commit mit Compare-Mail-Renderer- oder
  geteilter-Helfer-Änderung; ODER ein Deploy-Zyklus, bei dem zwischen zwei
  Prod-Deploys ein Doku-Commit über einem Code-Commit liegt.
- **Output:** Das Renderer-Mail-Gate blockt zuverlässig, wenn kein frischer
  compare-spezifischer Nachweis vorliegt (statt einen wirkungslosen
  Briefing-No-Op als Pass zu werten). `prod_selftest.py` erkennt den vollen
  seit dem letzten Deploy ausgelieferten Code-Scope und überspringt die
  Prüfung nur bei einem tatsächlichen docs-only-Deploy.
- **Side effects:** Alle vier Validator-YAMLs landen künftig im shared-repo
  `_log`-Verzeichnis (auch aus Worktrees heraus sichtbar für das Gate).
  `deploy-gregor-prod.sh` schreibt ein zusätzliches Feld in
  `last_prod_deploy.json` (Cross-Repo-Änderung, eigener Commit in
  `henemm-infra`).

## Acceptance Criteria

- **AC-1:** Given ein Commit staged `src/output/renderers/email/compare_html.py` / When das Renderer-Mail-Gate läuft / Then verlangt es einen frischen `*_email_validation.yaml`-Nachweis (`email_spec_validator`, `passed: true`, `validated_at` jünger als die Mail-Datei-mtime) und NICHT (nur) `briefing_validation.yaml`; `compare_html.py` ist aus `briefing_staged` ausgeschlossen.
  - Test: `tests/tdd/test_renderer_gate_compare_dispatch.py` — staged-Datei-Liste mit `compare_html.py` führt zu Anforderung des Compare-Nachweises, ein reiner Briefing-Nachweis reicht NICHT.

- **AC-2:** Given `briefing_mail_validator.py` läuft gegen eine Mail mit `X-GZ-Mail-Type: compare` oder `deviation-alert` / When der No-Op-Zweig greift / Then endet er mit Exit ≠ 0 und schreibt `passed: false` plus `skipped: true` — das Gate wertet dieses YAML als NICHT ausreichenden Nachweis.
  - Test: `tests/tdd/test_briefing_validator_noop_not_pass.py` — No-Op-Aufruf für `mail_type=compare` liefert Exit-Code ≠ 0 und ein YAML mit `passed: false`.

- **AC-3:** Given ein Commit staged einen geteilten Renderer-Helfer (`helpers.py`, `design_tokens.py` oder `profile_signature.py`) / When das Gate läuft / Then verlangt es BEIDE Nachweise (briefing UND compare), weil ein compare-spezifischer Bruch in geteilten Helfern sonst durch einen reinen Briefing-Nachweis schlüpfen könnte.
  - Test: `tests/tdd/test_renderer_gate_compare_dispatch.py` — staged-Datei-Liste mit `helpers.py` verlangt beide YAMLs gleichzeitig als Voraussetzung fürs Bestehen.

- **AC-4:** Given alle vier Validatoren (briefing, email_spec, radar, official) laufen in einem git-Worktree / When sie ihr Validation-YAML schreiben / Then landet es im shared-repo `_log` (git-common-dir, via `_e2e_paths.shared_repo_dir()`), das das Gate liest — Nachweise aus Worktrees sind sichtbar; liefert `shared_repo_dir()` `None`, greift der bisherige `__file__`-relative Fallback.
  - Test: `tests/tdd/test_validator_log_shared_repo_path.py` — Validator-Aufruf aus simuliertem Worktree schreibt ins Hauptrepo-`_log`-Verzeichnis, nicht ins Worktree-lokale.

- **AC-5:** Given der ursprüngliche Fehlpfad (nur `compare_html.py` ändern, nur ein Briefing-No-Op läuft grün) / When das Renderer-Mail-Gate den Commit prüft / Then blockiert es mit „Nachweis unvollständig" statt den Commit durchzuwinken.
  - Test: `tests/tdd/test_renderer_gate_compare_dispatch.py` — End-to-End-Szenario: nur Briefing-No-Op-YAML vorhanden, kein Compare-YAML → Gate-Exit ≠ 0.

- **AC-6:** Given `deploy-gregor-prod.sh` führt einen Prod-Deploy aus / When der Marker `last_prod_deploy.json` geschrieben wird / Then enthält er zusätzlich `previous_commit` = der vor dem Deploy live laufende Commit (`$LOCAL`), neben dem bestehenden `deployed_commit`.
  - Test: manuelle Verifikation im Cross-Repo-Commit (henemm-infra hat eigene Testinfrastruktur); im gregor_zwanzig-Kern wird der Marker-Konsument (AC-7) getestet.

- **AC-7:** Given `last_prod_deploy.json` enthält `previous_commit`, es ist ≠ HEAD und via `git cat-file -e` auflösbar / When `_scope_diff_base` läuft / Then nutzt es `previous_commit` mit höchster Priorität als Diff-Basis — der gesamte seit dem letzten Prod-Deploy ausgerollte Bereich wird geprüft, auch wenn ein reiner Doku-Commit obenauf liegt.
  - Test: `tests/tdd/test_prod_selftest_scope_diff_base.py` — temp-git-Fixture mit stacked-docs-on-code-Historie liefert `previous_commit` als Diff-Basis, Scope-Ergebnis ist `full-stack`/`backend`, nicht `docs-only`.

- **AC-8:** Given die Regressions-Matrix aus fünf Szenarien (stacked-docs-on-code, normaler Ein-Code-Commit, echter docs-only-Deploy, No-op-Re-Deploy mit `LOCAL==NEW`, Erst-Deploy ohne Marker) / When `_scope_diff_base` je Szenario läuft / Then liefert es deterministisch: (a) läuft (full-stack/backend), (b) läuft, (c) übersprungen, (d) fällt sicher durch ohne leeren `HEAD..HEAD`-Diff, (e) fällt auf `HEAD~1` zurück, bei Unauflösbarkeit fail-closed `backend`.
  - Test: `tests/tdd/test_prod_selftest_scope_diff_base.py` — fünf parametrisierte Fälle auf derselben temp-git-Fixture (Vorbild `test_issue_1084_gate_scope_cache.py`).

- **AC-9:** Given `previous_commit` ist im Marker abwesend oder unauflösbar / When `_scope_diff_base` läuft / Then wird NIEMALS fälschlich `docs-only` angenommen — die bestehende Fail-closed-Fallback-Kette (#1121) bleibt intakt und greift unverändert.
  - Test: `tests/tdd/test_prod_selftest_scope_diff_base.py` — Marker ohne `previous_commit`-Feld führt zu identischem Verhalten wie vor diesem Fix (Rückwärtskompatibilitäts-Fall).

## Invarianten (was sich NICHT ändern darf)

- `renderer_mail_gate.py` triggert weiterhin NICHT auf `.claude/hooks/*`-Änderungen
  (nur `src/output/renderers|channels/...`) — der Fix-Commit selbst bleibt
  ungeblockt vom eigenen Gate.
- Bestehende briefing/radar/official-Validation-YAMLs mit `passed: true` und
  ohne `skipped`-Feld bleiben gültige Nachweise (Rückwärtskompatibilität) —
  das Gate darf sie nicht nachträglich als ungültig werten.
- `prod_selftest.py` bleibt rückwärtskompatibel bei fehlendem
  `previous_commit`-Feld im Marker: Fallback auf die bestehende Kette
  (`deployed_commit` → Gate-Marker → `HEAD~1`), kein Hard-Break für alte
  Marker-Dateien.
- Bestehende Test-/Doc-Politik gilt unverändert: KEINE issue-nummerierten
  neuen Testdateien (Verhaltensnamen, siehe Affected-Files-Tabelle); echte
  Mail-Zustellung bleibt Live-Schicht und wird NICHT im Kern-Test simuliert
  oder gemockt.

## Cross-Repo-Hinweis

Die Änderung an `henemm-infra/scripts/deploy-gregor-prod.sh` (Ergänzung von
`previous_commit` im Marker) liegt in einem anderen Repository als der
restliche Fix. Sie erfordert einen **eigenen Commit im Repo
`henemm-infra`** (nicht Teil dieses `gregor_zwanzig`-Workflows) sowie eine
**Inter-Instance-Nachricht an `infra`** (Claude MQ, siehe
`~/.claude/CLAUDE.md` → „Inter-Instance Messaging"), damit die dortige
Claude-Instanz die Änderung übernimmt. Ohne diesen Cross-Repo-Fix bleibt
AC-6 unerfüllt und AC-7/AC-8 laufen im gregor_zwanzig-Kern nur gegen
simulierte Marker-Fixtures, nicht gegen den echten Deploy-Pfad.

## Considered & Deferred

- **D — Subject/Token-Bindung in `email_spec_validator.py`:** echte Härtung
  gegen Cross-Workflow-Postfach-Kontamination (der Validator wählt aktuell
  die neueste Compare-Mail per Header, ohne Subject/Token-Filter). Koppelt
  aber Renderer und Test enger und ist ein eigenständiges Härtungsthema —
  **deferred** als Follow-up, nicht Teil dieses Fixes.
- **AST-deklarierte Mail-Typen pro Renderer** statt handgepflegter
  Regex-Listen (`_RADAR_PATTERNS`, `_OFFICIAL_PATTERNS`, `_COMPARE_PATTERNS`):
  interessante Architektur-Alternative, die das Muster „ein neuer Renderer =
  eine neue Pattern-Liste" auflösen würde. Erfordert aber einen eigenen
  Architektur-Entscheid und fällt unter das Regel-Budget (PO-go
  2026-07-09) — **jetzt nicht**, konsistent mit dem etablierten
  radar/official-Muster, das dieser Fix lediglich um einen vierten Zweig
  erweitert statt neu zu erfinden.

## Known Limitations

- Der neue `previous_commit`-Zweig setzt voraus, dass ab dem ersten Deploy
  nach diesem Fix konsequent geschrieben wird; Marker aus Deploys VOR dem
  Fix haben kein `previous_commit`-Feld und fallen auf die alte
  (bekannt-lückenhafte) Kette zurück — das ist der bewusst akzeptierte
  Übergangszustand, kein neuer Bug.
- Der Gate-Marker-Fallback (`last_gate_scope.json`) bleibt bekannt
  UNZUREICHEND für das gemeldete Szenario (falscher Anker, an
  Staging-Kadenz statt Prod-Deploy-Kadenz gebunden, wird für einen
  übersprungenen Doku-Commit gar nicht neu geschrieben) — er wird NICHT
  entfernt (dient anderen Zwecken), aber auch NICHT als zusätzliches
  Sicherheitsnetz für dieses Problem behandelt („kein
  belt-and-suspenders"). Nur `deployed_commit`/`previous_commit` ist
  strukturell korrekt für diese Diff-Basis-Frage.
- Die geteilte-Helfer-Regel (Fix B, AC-3) erhöht die Kopplung: ein Commit an
  `helpers.py`/`design_tokens.py`/`profile_signature.py` braucht künftig
  BEIDE Test-Mails (briefing und compare) statt einer — bewusst in Kauf
  genommen, um denselben Bug nicht eine Datei weiter offen zu lassen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** n/a (Bugfix an bestehenden Gates, keine neue
  Architektur-Entscheidung)
- **Rationale:** Beide Fixes erweitern etablierte, bereits vorhandene
  Muster (Gate-Dispatch nach Datei-Pattern + `_<typ>_validator_log_ok`;
  Fallback-Kette in `_scope_diff_base`) um jeweils einen zusätzlichen Zweig
  mit höherer Priorität. Es wird keine neue Architektur eingeführt, kein
  neuer Mechanismus-Typ, keine neue Abhängigkeit — die AST-Alternative
  (die eine echte Architektur-Entscheidung wäre) ist explizit deferred
  (siehe „Considered & Deferred").

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_renderer_gate_compare_dispatch.py` — GIVEN ein Commit staged `compare_html.py` WHEN das Gate läuft THEN wird der Compare-Nachweis (nicht Briefing) verlangt; GIVEN ein Commit staged einen geteilten Helfer WHEN das Gate läuft THEN werden beide Nachweise verlangt; GIVEN nur ein Briefing-No-Op-YAML liegt vor WHEN das Gate den ursprünglichen Fehlpfad prüft THEN blockiert es (AC-1, AC-3, AC-5)
- [ ] `tests/tdd/test_briefing_validator_noop_not_pass.py` — GIVEN eine Mail mit `X-GZ-Mail-Type: compare` WHEN der No-Op-Zweig greift THEN ist Exit ≠ 0 und `passed: false, skipped: true` im YAML (AC-2)
- [ ] `tests/tdd/test_validator_log_shared_repo_path.py` — GIVEN ein Validator läuft in einem simulierten Worktree WHEN er sein YAML schreibt THEN landet es im shared-repo `_log`, mit Fail-soft-Fallback bei fehlendem git-common-dir (AC-4)
- [ ] `tests/tdd/test_prod_selftest_scope_diff_base.py` — GIVEN die fünf Regressions-Szenarien (stacked-docs-on-code, normaler Code-Commit, echter docs-only-Deploy, No-op-Re-Deploy, Erst-Deploy ohne Marker) WHEN `_scope_diff_base` je Fall läuft THEN liefert es das erwartete deterministische Ergebnis inkl. Fail-closed bei fehlendem/unauflösbarem `previous_commit` (AC-7, AC-8, AC-9)

Alle vier Testdateien sind Kern-Tests (deterministisch, temp-git-Fixture,
kein Netzwerk, keine echte Mail-Zustellung — Vorbild
`tests/tdd/test_issue_1084_gate_scope_cache.py`). Echte Mail-Zustellung
gegen das Stalwart-Test-Postfach bleibt Live-Schicht und ist nicht Teil
dieser Suite.

## Changelog

- 2026-07-16: Initial spec erstellt — Issues #1282, #1283, Fix-Workflow `fix-1282-1283-gate-honesty`
