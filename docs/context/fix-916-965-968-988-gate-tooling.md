# Context: Gate-Tooling-Robustheit-Bündel (#916, #988 — Workflow-Scope nach Split)

## Request Summary

Ursprünglich 4 gebündelte Gate-/Tooling-Bugs (#916, #965, #968, #988, Label
`bundle:K-gate-tooling-robustheit`). Nach Recherche auf 2 verbleibende Fixes
reduziert:

- **#968** bereits gefixt (Plugin `agent-os-openspec`, Commit `b7e108d`,
  Regressionstest grün) — verifiziert und geschlossen, kein Code nötig.
- **#965** betrifft `adversary_dialog.py` im separaten Repo
  `/home/hem/agent-os-openspec` (Plugin-Quelle) — PO-Entscheidung: außerhalb
  dieses gregor_zwanzig-Workflows behandeln (eigene Gates/LoC-Tracking dort
  greifen nicht sinnvoll aus diesem Workflow heraus).
- **#916 + #988** verbleiben im Scope dieses Workflows (beide Fixes liegen in
  `gregor_zwanzig/.claude/hooks/`).

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py:102-145` | `_detect_committed_scope()` — Scope-Klassifikation nur über `git diff HEAD~1 HEAD` (#916 Kernbug) |
| `.claude/hooks/prod_selftest.py:386-433` | Gespiegelte Kopie derselben Funktion (Issue #786) — muss identisch mitgefixt werden |
| `.claude/hooks/_e2e_paths.py` | Gemeinsame reine Helfer-Funktionen für staging_gate/prod_selftest (Pattern für neuen Shared-Helper) |
| `.claude/hooks/renderer_mail_gate.py:314-323` | Golden-Email-Check (seit `84c8b254` / #930) — bricht bei fehlendem `tests/golden/email/` (#988 Kernbug) |
| `tests/tdd/test_issue_811_renderer_gate.py:196` (`test_pass_with_both_evidences`) | Roter Test, baut Fixture-Repo unter `/tmp` ohne `tests/golden/` |
| `tests/tdd/test_issue_811_renderer_gate.py:57-84` (`_setup_repo`) | Fixture-Repo-Aufbau — kein `pyproject.toml`, kein `tests/golden/` |
| `.claude/e2e_verified/*.json` (Hauptrepo, 20 Dateien, Retention-geprunt) | Bestehende commit-getaggte Attestationen — Quelle für "letzter verifizierter Commit" |

## Existing Patterns

- **Scope-Erkennung dupliziert:** `staging_gate.py` und `prod_selftest.py` haben
  bewusst getrennte Kopien derselben `_detect_committed_scope()`-Logik (Kommentar
  in prod_selftest.py: "eigene Scope-Erkennung, damit ein docs-only-/tooling-Deploy
  nicht an einer stale Singleton-Attestation scheitert"). Ein Fix muss **beide**
  Kopien identisch anpassen (wie schon bei Einführung praktiziert) — Codeverdopplung
  ist hier bewusstes Design, kein Cleanup-Kandidat.
- **Attestation-Historie bereits vorhanden:** Jede erfolgreiche Staging-Verifikation
  schreibt `.claude/e2e_verified/<sha>.json` mit `verified_commit` + `verified_at`
  (Issue #666, Retention 20). Das liefert bereits eine natürliche, **rein
  gregor_zwanzig-interne** Referenz für "zuletzt verifizierter/deployter Stand" —
  keine Notwendigkeit, das henemm-infra-Deploy-Script (`deploy-gregor-prod.sh`)
  anzufassen, obwohl das dortige `LOCAL=$(git rev-parse HEAD)` (Zeile 88, vor
  `reset --hard origin/main`) technisch auch als Basis dienen könnte.
- **Fail-open bei Infrastruktur-Fehlern:** Der Golden-Check in
  `renderer_mail_gate.py` fängt bereits `Exception` ab und wertet das als
  `golden_ok=True` (Kommentar: "fail-open bei uv/pytest-Infrastrukturproblem").
  Ein regulärer non-zero-Returncode (kein Python-Exception) durchläuft diesen
  Pfad nicht — das ist die Lücke.

## Dependencies

- **#916-Fix hängt ab von:** `_e2e_paths.py` (neuer Shared-Helper dort, analog
  zu `commit_e2e_path`/`head_sha`), Attestation-Verzeichnis `.claude/e2e_verified/`
- **#988-Fix hängt ab von:** nichts extern — reine Existenzprüfung vor
  `subprocess.run`
- **Downstream:** `deploy-gregor-prod.sh` (henemm-infra) ruft `staging_gate.py --check`
  nach `git reset --hard origin/main` auf (Zeile 104) — Verhalten des Gates
  ändert sich, aber der Call selbst bleibt unverändert (kein henemm-infra-Touch
  nötig)

## Existing Specs

- Keine vorhandene Spec zu diesen beiden Funktionen — neue Mini-/Vollspec nötig.
- Verwandt: `docs/specs/modules/issue_811_mail_quality_gate.md` (Renderer-Gate
  Grundlage für #988), Issue #786 (Ursprung der gespiegelten Scope-Erkennung).

## Verifizierte Root Causes (reproduziert 2026-07-07)

**#916:** `_detect_committed_scope()` in beiden Dateien nutzt hart
`git diff --name-only HEAD~1 HEAD`. Bei einem Multi-Commit-Push, dessen letzter
Commit docs-only ist, aber frühere Commits im selben Push Code ändern, liefert
die Funktion fälschlich `docs-only` → Staging-Gate und Prod-Selftest werden
übersprungen.

**#988:** `test_pass_with_both_evidences` schlägt reproduzierbar fehl (`rc=2`
statt `0`). Ursache: Golden-Check läuft `uv run pytest tests/golden/email/ -q`
im Fixture-Repo unter `/tmp`, das kein `tests/golden/` besitzt. Tatsächlicher
Returncode in dieser Umgebung: **`4`** ("file or directory not found" — pytest
Usage-Error), nicht `5` wie im Issue vermutet. Das bestätigt: eine
Returncode-Sonderbehandlung wäre brüchig (unterschiedliche pytest/uv-Versionen
liefern unterschiedliche Codes) — robuster ist eine **Existenzprüfung** von
`tests/golden/email/` vor dem Subprocess-Aufruf.

## Analysis

### Type
Bug (beide: #916, #988)

### Strategische Gegenprüfung (Plan/Sonnet-Agent)

Unabhängige Bewertung des ursprünglichen Fix-Vorschlags ergab zwei wichtige
Verschärfungen — beide übernommen:

**#916 — verworfen: "jüngste Attestation nach mtime" als Diff-Basis.**
Grund: `.claude/e2e_verified/` ist ein **geteiltes, multi-purpose Verzeichnis**
(sieben parallele Worktrees schreiben dort während ihrer jeweiligen
Staging-Verifikation). Eine Attestation von einem unrelaten Feature-Branch
könnte als Basis gewählt werden → `git diff` gegen einen Nicht-Vorfahren von
HEAD liefert irreführende/falsche Ergebnisse. mtime ist zudem kein verlässlicher
Sortierschlüssel (Backups/Checkouts verfälschen ihn).

**Neuer Ansatz:** Dedizierter Single-Purpose-Marker `.claude/last_gate_scope.json`
im shared Repo-Verzeichnis, **ausschließlich** von `gate_check()` selbst
geschrieben (nicht von `/e2e-verify`). Bei Exit 0 (egal ob durch docs-only-Skip
oder vollständige Prüfung) wird der aktuelle HEAD-SHA hineingeschrieben. Der
NÄCHSTE Aufruf von `_detect_committed_scope()` liest diesen Marker als Diff-Basis
(`git diff --name-only <marker-sha> HEAD`) statt `HEAD~1..HEAD`. Da
`gate_check()` nur im tatsächlichen Deploy-Baum läuft (flock-serialisiert,
linearer Verlauf auf `origin/main`), ist der Marker nie von anderen
Worktrees/Branches kontaminiert — kein Ancestor-Check-Overhead nötig für den
Regelfall. Defensiv trotzdem: existiert der Marker-Commit nicht mehr im Repo
(z.B. nach History-Rewrite) → Fallback auf `HEAD~1..HEAD` (heutiges Verhalten).
Fehlt der Marker komplett (Erstlauf) → ebenfalls Fallback auf `HEAD~1..HEAD`.

**#988 — verschärft: Existenzprüfung allein reicht nicht.**
Grund: Eine reine `tests/golden/email/`-Existenzprüfung würde auch im ECHTEN
Repo fälschlich grün durchwinken, falls das Verzeichnis dort aus einem echten
Fehler heraus fehlt (versehentlich gelöscht, kaputtes `.gitignore`) — genau die
Fehlerklasse, vor der der Golden-Check eigentlich schützen soll.

**Neuer Ansatz:** Zusätzliche Unterscheidung über `pyproject.toml`:
- `tests/golden/email/` existiert → Check läuft wie bisher (inkl. bestehendem
  fail-open bei Exceptions).
- `tests/golden/email/` fehlt, aber `pyproject.toml` existiert (= echtes
  gregor_zwanzig-Repo) → `golden_ok = False` (fail-closed — echter Fehlerzustand).
- Beides fehlt (= Fixture-/Tooling-Repo ohne eigenes uv-Projekt, wie im
  Gate-Selbsttest) → `golden_ok = True` (Check ergibt keinen Sinn, übersprungen).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | Neuer Helper: `last_gate_scope_path()`, `read_last_gate_scope()`, `write_last_gate_scope()` |
| `.claude/hooks/staging_gate.py` | MODIFY | `_detect_committed_scope()` nutzt Marker-Basis statt `HEAD~1`; `gate_check()` schreibt Marker bei Exit 0 |
| `.claude/hooks/prod_selftest.py` | MODIFY | Identischer Fix in der gespiegelten Kopie (liest denselben Marker, schreibt ihn NICHT selbst — nur `staging_gate.gate_check()` ist Schreiber, sonst doppelte Schreiblogik) |
| `.claude/hooks/renderer_mail_gate.py` | MODIFY | Golden-Check: `pyproject.toml`-Zusatzprüfung vor Existenzprüfung |
| `tests/tdd/test_issue_916_gate_scope_marker.py` | CREATE | Regressionstest (Subprocess-Pattern, echtes Temp-Git-Repo) |
| `tests/tdd/test_issue_811_renderer_gate.py` | MODIFY | Bestehenden Test ergänzen um Gegenprobe "pyproject.toml vorhanden, golden fehlt → weiterhin block" |

### Scope Assessment
- Files: 6 (4 MODIFY, 1 CREATE, 1 MODIFY-mit-Ergänzung)
- Estimated LoC: ~+140/-10 (Hooks ~50 LoC, Tests ~100 LoC)
- Risk Level: MEDIUM (Blast Radius: steuert Deploy-Gate für alle künftigen Prod-Deploys — falsche Logik könnte Deploys fälschlich blocken ODER fälschlich durchlassen)

### Technical Approach
Siehe oben (Analysis-Abschnitt) — dedizierter Gate-Marker für #916, doppelte
Existenzprüfung (Verzeichnis + `pyproject.toml`) für #988.

### Dependencies
- `_e2e_paths.py`-Erweiterung ist Voraussetzung für den #916-Fix in beiden
  Gate-Dateien.
- #988 ist unabhängig, keine gemeinsame Code-Basis mit #916.

### Reihenfolge
Unabhängig voneinander implementierbar. Empfehlung des Plan-Agenten: #988
zuerst (kleiner, kein neuer Shared-Helper, geringeres Risiko), danach #916.

### Open Questions
- [x] Soll `prod_selftest.py` den Marker selbst schreiben oder nur lesen? →
  Nur lesen (ein Schreiber vermeidet Inkonsistenzen zwischen den zwei Kopien).

## Risks & Considerations

- **#916-Fix:** Muss den Fallback korrekt behandeln, wenn noch **keine** vorherige
  Attestation existiert (Erst-Verifikation) — dann bleibt `HEAD~1..HEAD` die
  einzig sinnvolle Basis. Muss außerdem die **eigene** HEAD-Attestation (falls
  bereits von `/e2e-verify` für den aktuellen Commit geschrieben) beim Rückwärtssuchen
  überspringen, sonst diffed die Funktion HEAD gegen sich selbst (leere Diff →
  fälschlich `docs-only`).
- **#988-Fix:** Muss weiterhin fail-closed bleiben, wenn `tests/golden/email/`
  im ECHTEN Repo existiert, aber die Tests selbst rot sind (Renderer-Drift) —
  nur die Fixture-Situation (Verzeichnis fehlt komplett) soll `golden_ok=True`
  ergeben.
- **Kein Prod-Deploy nötig:** Beide Fixes sind reines `.claude/hooks/`-Tooling
  (Regel aus #968-Analogie: "kein Produktcode, kein Prod-Deploy nötig").
  Regressionstests (mock-frei, Subprocess-Pattern) sind aber Pflicht.
