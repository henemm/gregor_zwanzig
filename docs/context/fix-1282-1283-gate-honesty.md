# Context: fix-1282-1283-gate-honesty

## Request Summary

Zwei Gate-/Tooling-Bugs mit gemeinsamem Muster **„ein Wächter meldet Erfolg, ohne
zu prüfen"** in einem Workflow beheben:

- **#1282** — Renderer-Mail-Gate (#811) ist für **Compare-Mails wirkungslos**: der
  `briefing_mail_validator` No-Op schreibt `passed: true`, das Gate akzeptiert das,
  und es existiert kein Compare-Zweig, der den zuständigen `email_spec_validator`
  verlangt. Zweitbefund: beide Validatoren schreiben ihr Log **worktree-relativ**,
  das Gate liest **shared-repo** → aus Worktrees sind Nachweise unsichtbar.
- **#1283** — `prod_selftest.py` überspringt echte Code-Deploys als **„docs-only"**,
  wenn ein fremder Doku-Commit obenauf liegt: der `HEAD~1`-Fallback greift, sobald
  beide Self-Reference-Guards (`deployed_commit`, Gate-Marker) auf HEAD zeigen.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `.claude/hooks/briefing_mail_validator.py` | **#1282-A**: Z. 498–501 No-Op-Zweig `return True` für `compare`/`deviation-alert`; Z. 643 → `passed: bool(success)`. **#1282-C**: `_write_validation_log` Z. 631–632 schreibt `__file__`-relativ (`hooks_dir.parent/workflows/_log`) → worktree-blind. Hat bereits `--mail-type`/`--subject-contains`-Filter (Z. 658–661). |
| `.claude/hooks/renderer_mail_gate.py` | **#1282-B**: kennt nur `_RADAR_PATTERNS`/`_OFFICIAL_PATTERNS`; `compare_html.py` fällt in `briefing_staged` (Z. 351–353) → verlangt `briefing_validation.yaml`. **Kein Compare-Zweig.** Liest Logs via `_shared_repo_root()` (git-common-dir → Hauptrepo, Z. 89–108). `_validator_log_ok` Z. 163–203 prüft nur `passed: true` + Freshness. |
| `.claude/hooks/email_spec_validator.py` | **#1282-B**: der fachlich zuständige Compare-Validator. Schreibt `*_email_validation.yaml` mit `passed: bool(success)` (Z. 59, 65). **#1282-C**: log_dir ebenfalls `__file__`-relativ (Z. 49–51) → worktree-blind. **#1282-D**: wählt Compare-Mail per Header `X-GZ-Mail-Type: compare` (newest-compare, Z. 105/160) — **kein Subject/Token-Filter**. |
| `.claude/hooks/prod_selftest.py` | **#1283**: `_scope_diff_base` Z. 432–477. Bevorzugt `last_prod_deploy.json.deployed_commit` **nur wenn ≠ HEAD** (#1109-Zweig), sonst Gate-Marker **nur wenn ≠ HEAD** (F002-Guard), sonst `HEAD~1`. |
| `.claude/hooks/_e2e_paths.py` | Helfer: `head_sha`, `read_last_gate_scope`, `read_last_gate_scope_entry`, `shared_repo_dir()` (git-common-dir, Z. 188), `worktree_repo_dir()`. Kandidat, um Validator-Log-Schreiben (#1282-C) auf shared-repo umzustellen. |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | **#1283 cross-repo**: Z. 113 `LOCAL=$(git rev-parse HEAD)` (Vor-Deploy-Commit, bereits erfasst!), Z. 114 `git reset --hard origin/main`, Z. 115 `NEW`. Z. 253–256 schreibt Marker **nach** Deploy mit `deployed_commit: $(git rev-parse HEAD)` = HEAD — **`$LOCAL` wird verworfen**. |

## Existing Patterns

- **Gate-Dispatch nach Datei-Muster** (`renderer_mail_gate.py`): `_RADAR_PATTERNS`,
  `_OFFICIAL_PATTERNS` + je ein `_<typ>_validator_log_ok`, das das passende
  `*_<typ>_validation.yaml` verlangt. Vorbild für einen neuen Compare-Zweig
  (`_COMPARE_PATTERNS` = `compare_html.py`, `_compare_validator_log_ok` →
  `*_email_validation.yaml`).
- **Validator-Log-YAML** (`briefing`/`radar`/`official`/`email`): einheitliches
  Schema `{validator, validated_at, workflow_id, passed, errors}`, atomar via
  `mkstemp`+`os.rename` geschrieben.
- **Fail-closed bei unsicherer Scope-Basis** (#1121): lieber „backend"/prüfen als
  fälschlich „docs-only". Muss beim #1283-Fix erhalten bleiben.
- **Shared-repo-Auflösung** über `git rev-parse --git-common-dir` — sowohl das Gate
  (`_shared_repo_root`) als auch `_e2e_paths.shared_repo_dir()` machen das bereits.
  Die Validatoren machen es **nicht** → genau die Worktree-Diskrepanz (#1282-C).

## Dependencies

- **Upstream:** Gate/Validatoren hängen an git (`--git-common-dir`, `diff --cached`),
  `OPENSPEC_ACTIVE_WORKFLOW`, dem Stalwart-Test-Postfach (echte Mails). `prod_selftest`
  an `last_prod_deploy.json` + Gate-Marker + git-Historie.
- **Downstream:** `renderer_mail_gate` blockiert **jeden Commit** mit Mail-Renderer-
  Datei → strengeres Verhalten muss präzise sein, sonst blockt es legitime Commits.
  `prod_selftest` gatet **Issue-Close + Prod-Deploy** („nur bei Exit 0") → der Fix
  lässt es **öfter laufen** (strenger, sicher), darf aber keine Endlos-Blockade
  erzeugen.

## Existing Specs / Referenzen

- CLAUDE.md → „Mail-Validatoren & Renderer-Gate (ZWINGEND)" (Dispatch-Tabelle
  compare vs. trip-briefing), „Renderer-Commit-Gate (#811)".
- CLAUDE.md → „E2E-Verifikation": „Issue-Close nur bei Selftest-Exit 0".
- `docs/reference/mail_validators.md`, `docs/reference/operations_playbook.md`.
- Verwandt/offen: #1281 (Gate-Regexe lesen die falsche Stelle) — gleiches Meta-Muster.

## Risks & Considerations

- **Selbst-modifizierende Gates:** Wir ändern genau die Wächter, die unsere Commits/
  Deploys gaten. Beide Änderungen machen sie **strenger** (erlaubt/erwünscht) — kein
  Aufweichen. `renderer_mail_gate` triggert bei `.claude/hooks/*`-Edits **nicht**
  (nur `src/output/renderers/...`), unser eigener Commit bleibt also frei.
- **Cross-Repo (#1283):** saubere Lösung berührt `henemm-infra` (Deploy-Script) —
  eigener Commit dort + MQ an `infra`. Änderung ist minimal (`$LOCAL` ist schon da).
- **Falscher-Validator-Falle:** Der Compare-Zweig muss `compare_html.py` **aus
  `briefing_staged` ausschließen**, sonst verlangt das Gate weiterhin (auch) den
  Briefing-Validator und wird strukturell nie bestehbar (Gate-Erosion andersherum).
- **Testbarkeit (Kern, ohne Netz):** Gate-/Validator-Logik deterministisch testbar
  (Branch-Auswahl, `skipped`≠`passed`, Diff-Basis-Ableitung). Echte Mail-Zustellung
  ist Live-Schicht — der Kern-Test darf sie nicht brauchen.
- **`skipped` vs. `passed` Semantik:** No-Op muss ein Feld liefern, das das Gate als
  **nicht ausreichend** wertet — rückwärtskompatibel zu bestehenden YAMLs (die kein
  `skipped` haben, aber `passed: true` legitim tragen).

## Analysis

### Type
Bug (zwei unabhängige Gate-Bugs, gemeinsames Muster „Gate meldet Erfolg ohne Prüfung").
Root-Cause beider **verifiziert** (inkl. Live-Beweis für #1283: `deployed_commit ==
gate_scope_sha` im Hauptrepo aktuell identisch). Zwei unabhängige Analyse-Agenten
(Plan/Sonnet + analysis-challenger) bestätigen die Diagnose und **erweitern den
Fix-Scope** in vier Punkten (unten).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | **B:** `_COMPARE_PATTERNS`, `_is_compare_file`, `_compare_validator_log_ok` (spiegelt `_official_validator_log_ok`), Wiring in `_do_hook`. compare-exklusive Datei (`compare_html.py`) aus `briefing_staged` ausschließen; geteilte Helfer verlangen **beide** Nachweise. |
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | **A:** No-Op-Zweig (compare/deviation-alert) → `passed:false` + `skipped:true`, **Exit 2** statt grün. **C:** log_dir via `_e2e_paths.shared_repo_dir()`. |
| `.claude/hooks/email_spec_validator.py` | MODIFY | **C:** log_dir via `shared_repo_dir()`. (Optional **D** deferred.) |
| `.claude/hooks/radar_alert_mail_validator.py` | MODIFY | **C:** log_dir via `shared_repo_dir()` (Z.132–133 gleicher Bug — vom Challenger gefunden). |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | **C:** log_dir via `shared_repo_dir()` (Z.214–215 gleicher Bug). |
| `.claude/hooks/prod_selftest.py` | MODIFY | **#1283:** `previous_commit`-Zweig in `_scope_diff_base` (höchste Priorität, `cat-file`-Guard, `≠HEAD`-Guard), #1121-Fail-closed erhalten. |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY (**cross-repo**) | **#1283:** Marker-JSON zusätzlich `previous_commit: $LOCAL` (Z.113 bereits erfasst). Eigener Commit im Infra-Repo + MQ an `infra`. |
| Tests (Kern, deterministisch) | CREATE | Gate-Branch-Auswahl, `skipped≠passed`, Diff-Basis-Matrix (temp-git-Fixture, Vorbild `test_issue_1084_gate_scope_cache.py`). |

### Scope-Erweiterungen aus der Adversary-Analyse (in die Spec)
1. **C betrifft ALLE 4 Validatoren** (briefing, email_spec, radar, official) — nicht nur die zwei ursprünglich genannten. Alle vier schreiben `__file__`-relativ; das Gate liest shared-repo.
2. **Geteilte Renderer-Helfer** (`helpers.py`, `design_tokens.py`, `profile_signature.py`) speisen **briefing UND compare** (beide importieren sie). Regel: staged geteilter Helfer ⇒ **beide** Nachweise (briefing *und* compare) — sonst schlüpft compare-spezifischer Bruch durch den reinen Briefing-Nachweis (derselbe Bug, eine Datei weiter). Kosten: höhere Kopplung (Helfer-Commit braucht künftig beide Test-Mails) — bewusst in Kauf genommen.
3. **#1283 = 6. Fix in dieser Funktionsklasse** (#916/#1084/#1096/#1109/#1121/#1130, davon 2 echte Prod-Vorfälle). Deshalb **Regressions-Test-Matrix** statt Einzel-Repro: stacked-docs-on-code · normaler Ein-Code-Commit · echter docs-only-Deploy · No-op-Re-Deploy (`LOCAL==NEW`) · Erst-Deploy (kein Marker). Spec hält fest: **Gate-Marker-Fallback ist bekannt-unzureichend** (falscher Anker, an Staging-Kadenz gebunden), kein redundantes Sicherheitsnetz — nur `deployed_commit`/`previous_commit` ist strukturell korrekt.
4. **Zwei Fehlermodi bei #1282** je Ausführungskontext: Hauptrepo → **False-Pass** (Bug B), Worktree → **False-Block** (Bug C). Beide müssen getestet werden. **B ohne C = Worktree-Selbst-DoS** → C ist Voraussetzung, nicht Kür.

### Scope Assessment
- Dateien: 7 (6× `gregor_zwanzig` + 1× `henemm-infra`) + Kern-Tests.
- Geschätzte LoC (Produktionscode, Kern): ~95–120 (Tests zählen nicht) → innerhalb 250-Budget.
- Risk Level: **MEDIUM** — strengere Gates (gewollt); Hauptrisiko ist Worktree-Regression bei B ohne C (adressiert) + erhöhte Renderer↔Validator-Kopplung.

### Technical Approach
- **#1282-Kern = B + C** (nicht A): B behebt den strukturellen Defekt (falscher Validator), C ist Voraussetzung für Worktree-Betrieb. A ist Härtung (schließt zusätzlich ein Briefing-False-Green-Loch) und kommt mit B.
- **#1283:** `previous_commit`-Weg ist die sauberste Lösung; self-contained (nur `prod_selftest.py`) ist **nicht** präzise+sicher möglich (`$LOCAL` existiert nur zur Deploy-Laufzeit) → Infra-Änderung zwingend. Read ist rückwärtskompatibel (fehlendes Feld → bestehende Kette).

### Considered & Deferred
- **D (Subject/Token-Bindung in email_spec_validator):** echte Härtung gegen Cross-Workflow-Postfach-Kontamination, koppelt aber Renderer/Test → **deferred** (Follow-up).
- **AST-deklarierte Mail-Typen pro Renderer** statt handgepflegter Regex-Listen: interessante Architektur-Alternative (löst Challenge-1 elegant), aber eigener Architektur-Entscheid + Regel-Budget → **jetzt nicht**, konsistent mit etabliertem radar/official-Muster.

### Open Questions (für PO / Spec)
- [ ] Geteilte-Helfer-Regel (Punkt 2) im Kern mitnehmen oder als dokumentiertes Follow-up? Empfehlung Tech-Lead: **mitnehmen** (sonst bleibt derselbe Bug eine Datei weiter offen).
- [ ] #1281 (qa_gate-Regex) ist **separat** (Plugin `core/hooks`, kein Datei-Overlap) — nur Meta-Muster geteilt. Bleibt eigenes Issue.
