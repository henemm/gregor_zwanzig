---
entity_id: issue_916_988_gate_scope_robustness
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [gate, tooling, bugfix, deploy]
---

# Gate-Tooling-Robustheit — Scope-Erkennung + Golden-Check-Selbsttest (#916, #988)

## Approval

- [ ] Approved

## Purpose

Behebt zwei unabhängige Bugs im Deploy-Gate-Tooling: (1) `_detect_committed_scope()`
klassifiziert bei einem Multi-Commit-Push fälschlich als `docs-only`, wenn nur der
letzte Commit docs-only ist, obwohl frühere Commits im selben Push Code ändern —
dadurch werden Staging-Gate und Prod-Selftest fälschlich übersprungen (#916). (2) Der
Golden-Email-Check in `renderer_mail_gate.py` bricht mit einem harten Fehler ab,
sobald `tests/golden/email/` fehlt (z.B. in Fixture-/Test-Repos ohne eigenes
uv-Projekt), statt zwischen "Fixture-Repo ohne Golden-Bestand" (soll grün sein) und
"echtes Repo mit versehentlich fehlendem Golden-Bestand" (soll blocken) zu
unterscheiden (#988).

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `def _detect_committed_scope`, `def gate_check`
- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `def _detect_committed_scope` (gespiegelte Kopie)
- **File:** `.claude/hooks/renderer_mail_gate.py`
- **Identifier:** Golden-Check-Block vor `sys.exit(0)` (Zeilen ~314-323)
- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** neue Funktionen `last_gate_scope_path`, `read_last_gate_scope`,
  `write_last_gate_scope`

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen in `.claude/hooks/` —
> reines Deploy-/Test-Tooling, kein Produktcode in `frontend/`, `cmd/server/`,
> `internal/`, `api/` oder `src/`. Kein Prod-Deploy für diesen Workflow nötig
> (analog #968-Präzedenzfall).

## Estimated Scope

- **LoC:** ~+140/-10
- **Files:** 6 (4 MODIFY, 1 CREATE, 1 MODIFY-mit-Ergänzung)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths.py` | module | Bestehender Shared-Helper (`shared_repo_dir`, `head_sha`, `commit_e2e_path`), wird um die neuen Marker-Funktionen ergänzt — Voraussetzung für den #916-Fix in beiden Gate-Dateien |
| `.claude/e2e_verified/<sha>.json` | data | Bestehende, geteilte Attestation-Historie — bewusst NICHT als Diff-Basis genutzt (Kontaminationsgefahr durch parallele Worktrees), aber als Referenzmuster für "commit-getaggtes Artefakt im shared Repo-Verzeichnis" |
| `deploy-gregor-prod.sh` (henemm-infra) | script | Ruft `staging_gate.py --check` unverändert weiter auf; Verhalten des Gates ändert sich, kein Touch am Script nötig |
| `tests/tdd/test_issue_811_renderer_gate.py` | test | Bestehende Testdatei (`_setup_repo`, `test_pass_with_both_evidences`), wird um Gegenprobe für #988 ergänzt |

## Implementation Details

### Fix 1 — Issue #916: dedizierter Gate-Marker statt `HEAD~1..HEAD`

**Neuer Helper in `_e2e_paths.py`** (pure Funktionen, Pattern analog zu
`commit_e2e_path`/`head_sha`):

- `last_gate_scope_path(repo_dir) -> Path`: liefert
  `<repo_dir>/.claude/last_gate_scope.json`.
- `write_last_gate_scope(repo_dir, sha) -> None`: schreibt `{"gate_scope_sha": sha}`
  nach `last_gate_scope_path(repo_dir)`. Schreibfehler (z.B. read-only Dateisystem)
  werden geschluckt — das Gate-Ergebnis selbst darf davon nicht beeinflusst werden.
- `read_last_gate_scope(repo_dir) -> str | None`: liest die Datei, gibt `gate_scope_sha`
  zurück oder `None` bei fehlender/kaputter Datei.

**`staging_gate.py::_detect_committed_scope()`:** ermittelt zunächst über
`_e2e_paths.read_last_gate_scope(shared_repo_dir())` den Marker-SHA. Ist er
vorhanden UND per `git cat-file -e <sha>` im Repo auflösbar, wird
`git diff --name-only <marker-sha> HEAD` statt `git diff --name-only HEAD~1 HEAD`
als Basis für die Datei-Liste verwendet. Fehlt der Marker (Erstlauf) oder ist der
Commit nicht mehr auflösbar (History-Rewrite/Force-Push), greift der bisherige
Fallback `HEAD~1..HEAD` unverändert.

**`staging_gate.py::gate_check()`:** schreibt bei JEDEM `return 0`-Pfad (sowohl
`scope == "docs-only"`-Skip als auch vollständige Prüfung bestanden, aktuell
Zeilen 257-259 bzw. 315-316) den aktuellen HEAD-SHA über
`_e2e_paths.write_last_gate_scope(shared_repo_dir(), head)`. Bei jedem `return 1`
(Fehlerpfad) wird NICHT geschrieben — ein fehlgeschlagener Gate-Lauf darf die
Diff-Basis für den nächsten Versuch nicht verschieben.

**`prod_selftest.py::_detect_committed_scope()`:** identische Logik zur
Marker-basierten Diff-Ermittlung (liest über `_e2e_paths.read_last_gate_scope`),
schreibt den Marker aber NICHT — `staging_gate.py` bleibt der einzige Schreiber,
um konkurrierende/inkonsistente Schreibvorgänge zwischen den zwei gespiegelten
Kopien zu vermeiden.

### Fix 2 — Issue #988: `pyproject.toml`-Zusatzprüfung im Golden-Check

In `renderer_mail_gate.py` vor dem bestehenden
`subprocess.run(["uv", "run", "pytest", "tests/golden/email/", ...])`-Aufruf
(aktuell Zeilen ~314-323) wird die Existenzprüfung um eine Fallunterscheidung
ergänzt:

1. `tests/golden/email/` existiert im Ziel-Repo (`repo`) → Check läuft
   unverändert wie bisher, inklusive dem bestehenden `try/except Exception:
   golden_ok = True` (fail-open bei uv/pytest-Infrastrukturproblem).
2. `tests/golden/email/` fehlt UND `pyproject.toml` im Ziel-Repo existiert
   (= echtes gregor_zwanzig-Repo mit fehlendem/gelöschtem Golden-Bestand) →
   `golden_ok = False` (NEU: fail-closed — echter Fehlerzustand, der aktuell
   fälschlich grün durchgewunken würde, weil der `subprocess.run`-Aufruf einen
   Usage-Error-Returncode ≠ 0 liefert, der schon heute korrekt als
   `golden_ok = False` gewertet würde — die Änderung macht diesen Pfad
   explizit statt implizit/versionsabhängig).
3. Beides fehlt (Fixture-/Tooling-Repo ohne eigenes uv-Projekt, z.B.
   `tests/tdd/test_issue_811_renderer_gate.py::_setup_repo`) →
   `golden_ok = True` (Check ergibt dort keinen Sinn, wird übersprungen).

## Expected Behavior

- **Input:** ein oder mehrere Git-Commits seit dem letzten erfolgreichen
  `staging_gate.py --check`-Lauf; für Fix 2 der Dateibaum eines beliebigen
  Ziel-Repos (echtes Repo oder Fixture-Repo).
- **Output:** `_detect_committed_scope()` liefert einen der vier Werte
  (`frontend-only`, `backend`, `full-stack`, `docs-only`) basierend auf ALLEN
  Commits seit dem Marker (statt nur dem letzten Commit); `golden_ok` liefert
  `True`/`False` gemäß der Dreifachunterscheidung aus Fix 2.
- **Side effects:** `staging_gate.py::gate_check()` schreibt bei Exit 0 die Datei
  `.claude/last_gate_scope.json` im shared Repo-Verzeichnis (überschreibt den
  vorherigen Inhalt). Kein anderer Prozess schreibt diese Datei.

## Acceptance Criteria

- **AC-1:** Given ein temporäres Git-Repo mit Marker-Datei, die auf Commit A
  zeigt / When zwei weitere Commits folgen — Commit B ändert `src/foo.py`,
  Commit C ändert nur `docs/bar.md` — und `_detect_committed_scope()` auf
  Commit C als HEAD ausgeführt wird / Then liefert die Funktion `backend` (oder
  `full-stack` bei zusätzlicher Frontend-Änderung), NICHT `docs-only`.
  - Test: Subprocess-Test gegen ein echtes Temp-Git-Repo (`git init`, echte
    Commits), der die Python-Funktion `_detect_committed_scope()` importiert
    und mit `cwd`/Marker auf das Temp-Repo zeigend aufruft; Assertion auf den
    zurückgegebenen String, kein Dateiinhalt-Check.

- **AC-2:** Given ein frisches Temp-Git-Repo ohne existierende
  `.claude/last_gate_scope.json` / When `_detect_committed_scope()` aufgerufen
  wird / Then wird intern auf `git diff --name-only HEAD~1 HEAD` zurückgefallen
  und liefert exakt das bisherige (Vor-Fix-)Ergebnis für denselben Commit-Fall.
  - Test: Subprocess-Test, der denselben Commit-Aufbau wie im Vorher-Zustand
    (ein einzelner Commit mit Backend-Änderung nach initialem Commit) ohne
    Marker-Datei durchspielt und `backend` als Ergebnis erwartet — beweist
    Regressionsfreiheit.

- **AC-3:** Given ein Temp-Git-Repo mit einer Marker-Datei, die auf einen SHA
  zeigt, der nach einem simulierten History-Rewrite (`git commit --amend` +
  Force-Reset auf neuen Verlauf) nicht mehr im Repo existiert / When
  `_detect_committed_scope()` aufgerufen wird / Then fällt die Funktion ohne
  Exception auf `HEAD~1..HEAD` zurück und liefert ein valides Scope-Ergebnis
  (keiner der vier Werte fehlt, kein Absturz/Traceback).
  - Test: Subprocess-Test, der `git cat-file -e <nicht-existenter-sha>`
    scheitern lässt (echter Git-Aufruf, kein Mock) und prüft, dass die Funktion
    trotzdem einen der vier gültigen Scope-Strings zurückgibt.

- **AC-4:** Given ein Temp-Git-Repo ohne Marker-Datei / When
  `staging_gate.gate_check()` zweimal nacheinander aufgerufen wird — erst mit
  `scope_override="docs-only"` (Skip-Pfad), dann nach einem echten Commit mit
  vollständiger Prüfung (gültiges `e2e_verified.json` vorhanden) — Then existiert
  nach BEIDEN Aufrufen die Datei `.claude/last_gate_scope.json` mit dem jeweils
  aktuellen HEAD-SHA als Inhalt.
  - Test: Subprocess-/Direktaufruf-Test gegen echtes Temp-Repo, der nach jedem
    `gate_check()`-Call den Exit-Code UND den tatsächlichen Marker-Dateiinhalt
    (geparstes JSON, Feldwert gegen `git rev-parse HEAD` verglichen) prüft —
    kein reiner String-in-Datei-Check, sondern Vergleich gegen den echten
    aktuellen Commit-SHA des Repos.

- **AC-5:** Given ein Fixture-Repo unter `/tmp` ohne `tests/golden/` UND ohne
  `pyproject.toml` (wie `test_issue_811_renderer_gate.py::_setup_repo`
  aufbaut), mit Briefing-Mail-Dateien staged und allen anderen
  Gate-Voraussetzungen erfüllt / When `renderer_mail_gate.py` als Subprocess
  gegen dieses Repo läuft / Then terminiert der Prozess mit Exit-Code 0
  (`test_pass_with_both_evidences` wird grün).
  - Test: bestehender `subprocess.run`-Testfall in
    `tests/tdd/test_issue_811_renderer_gate.py`, der den kompletten Hook als
    echten Prozess gegen das Fixture-Repo startet und den Returncode prüft.

- **AC-6:** Given dasselbe Fixture-Repo, ergänzt um eine leere
  `pyproject.toml`-Datei, weiterhin ohne `tests/golden/email/` / When
  `renderer_mail_gate.py` als Subprocess läuft / Then terminiert der Prozess mit
  einem non-zero Exit-Code (Gate blockt, `golden_ok=False`-Pfad greift).
  - Test: neuer Subprocess-Testfall (Gegenprobe zu AC-5) in
    `tests/tdd/test_issue_811_renderer_gate.py`, der `_setup_repo` um das
    Anlegen einer `pyproject.toml` erweitert und einen non-zero Returncode
    sowie eine Blocker-Meldung im stdout/stderr des echten Prozesses erwartet.

## Known Limitations

- Der Marker-Mechanismus aus Fix 1 (#916) funktioniert korrekt NUR im
  offiziellen, linearen Deploy-Baum (`/home/hem/gregor_zwanzig`,
  flock-serialisiert über `deploy-gregor-prod.sh`). In isolierten
  Test-Repos/Worktrees, die `gate_check()` nicht in diesem Ablauf aufrufen,
  existiert entweder kein Marker (Erstlauf-Fallback greift) oder ein Marker aus
  einem unrelaten Kontext — für diesen Fall ist der Ancestor-Check
  (`git cat-file -e`) die einzige Absicherung; ein vollständiger
  "ist-Vorfahre-von-HEAD"-Check wird bewusst NICHT implementiert (siehe
  Kontext-Dokument, Abschnitt "verworfen" — Regelfall braucht ihn nicht, da
  `gate_check()` nur seriell im Deploy-Baum schreibt).
- `prod_selftest.py` liest den Marker, schreibt ihn aber nie — läuft
  `prod_selftest.py` isoliert (ohne vorherigen `staging_gate.py --check`-Lauf im
  selben Repo-Zustand), bleibt der Marker ggf. auf einem älteren Commit stehen
  und die Diff-Basis ist entsprechend älter (kein Fehlerzustand, nur ein
  breiterer Diff-Scan als nötig).
  - **Update (2026-07-07, Issue #1084):** Der ursprünglich hier beschriebene
    Grenzfall — `prod_selftest.py` läuft unmittelbar nach einem erfolgreichen
    `staging_gate.py --check`-Lauf im selben Repo-Zustand, der Marker steht
    bereits auf HEAD, `git diff HEAD..HEAD` ist leer und liefert fälschlich
    `docs-only` — wurde konkret beobachtet (#1080-Deploy-Pipeline) und über
    einen Scope-Cache im Marker selbst behoben: `write_last_gate_scope()`
    speichert zusätzlich den bereits berechneten Scope (`gate_last_scope`),
    `prod_selftest.py::_detect_committed_scope()` nutzt diesen Cache-Wert bei
    exakter Commit-Übereinstimmung, statt ihn selbstreferenziell neu
    herzuleiten. Details: `docs/specs/modules/issue_1084_gate_scope_cache.md`.
- Fix 2 (#988) unterscheidet ausschließlich über die Existenz von
  `pyproject.toml` — ein Repo, das `pyproject.toml`, aber absichtlich (aus
  legitimen Gründen) keine Golden-Tests führt, würde weiterhin fälschlich
  blockieren. Dieser Fall ist im aktuellen Projekt nicht vorgesehen (jedes
  echte gregor_zwanzig-Repo hat `tests/golden/email/`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Bugfix-Tooling innerhalb bestehender Gate-Skripte
  (`.claude/hooks/`) — keine neue Architektur-Entscheidung, kein neues
  Subsystem, keine Änderung an Produktcode oder Datenmodellen. Es wurde geprüft:
  keine der 20 vorhandenen ADRs (`docs/adr/0001`–`0017`) behandelt
  Deploy-Gate-Mechanik oder Scope-Erkennung.

## Changelog

- 2026-07-07: Initial spec created
