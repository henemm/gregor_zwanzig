---
entity_id: fix_1197_staging_gate_e2e_scope
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
workflow: fix-1197-staging-gate-e2e-testfile-scope
---

# Deploy-Gate: Frontend-E2E-Testdateien nicht als Programmcode klassifizieren

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „Frontend-E2E-Testdateien werden als Programmcode gezählt"
- **Typ:** Gate-Fix (Kategorie c — fälschlich blockierendes Gate)
- **Prüfdatum (Regel-Budget):** 2026-11-15
- **Vorgänger-Spec:** `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` (Ancestor+docs-only-Relaxierung von `staging_gate.gate_check`) — dort definiert AC-3 "Zuwachs enthält Datei unter `frontend/` → Block". Diese Spec präzisiert UNTERHALB dieser Logik, was als "Datei unter `frontend/`" im Sinne von echtem, ausgeliefertem Code zählt; das Verhalten von AC-3 der Vorgänger-Spec bleibt für echten Frontend-Code unverändert korrekt.

## Approval

- [ ] Approved

## Problem

`.claude/hooks/_e2e_paths.py::_detect_scope_from_git_diff` (Zeile 206-258) ist die
gemeinsame Scope-Klassifikationsfunktion für den Deploy-Gate (`staging_gate.py`,
Aufruf Zeile 202 direkt und Zeile 621 in der Ancestor-Relaxierung) sowie für
`prod_selftest.py` (Aufruf Zeile 673). Sie behandelt **jede** Datei mit Präfix
`frontend/` als `has_frontend=True` (Zeile 226-227) — auch Playwright-E2E-
Testdateien unter `frontend/e2e/**` (Specs, Setup-Dateien, Configs, Fixtures,
Test-Helfer), die keinen ausgelieferten Produktivcode darstellen. Backend-Tests
unter `tests/` sind in derselben Funktion bereits als Nicht-Code ausgenommen
(Zeile 241), Frontend-E2E-Tests haben kein analoges Pendant.

**Live erlebt am 2026-08-15:** PR-Stack #1736/#1852/#1881/#1882 änderte u.a.
`frontend/e2e/trip-preview-thunder-origin.staging.spec.ts` (Umbenennung). Der
Scope wurde dadurch `frontend-only` statt `docs-only` klassifiziert, obwohl kein
Produktivcode betroffen war. Der Deploy-Gate (`staging_gate.py`, aufgerufen von
`deploy-gregor-prod.sh`) blockte daraufhin mit der irreführenden Meldung
„vermutlich hat eine parallele Sitzung deployt" — der eigentliche Grund war die
falsche Scope-Klassifikation, nicht eine parallele Sitzung.

## Purpose

`_detect_scope_from_git_diff` liefert korrekt `docs-only` (statt `frontend-only`
oder `full-stack`), wenn ein Diff ausschließlich `frontend/e2e/`-Dateien betrifft,
ohne die Fail-closed-Klassifikation für echten Frontend-Code (`frontend/src/`
etc.) oder Backend-Code aufzuweichen. Dadurch greifen die CLAUDE.md-Regeln für
reine Doku-/Tooling-Änderungen (kein Deploy-Zwang, Ancestor-Relaxierung) auch
dann korrekt, wenn ein PR-Stack nur Playwright-Testinfrastruktur ändert.

## Source

- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** `def _detect_scope_from_git_diff(base, target, repo_dir) -> str` (Zeile 206-258)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/staging_gate.py::gate_check` | caller | Ruft die Funktion Zeile 202 (direkte Scope-Ermittlung) und Zeile 621 (Ancestor-Relaxierung) auf — Deploy-Hard-Gate für `deploy-gregor-prod.sh`; profitiert automatisch von der Korrektur an der Quelle |
| `.claude/hooks/prod_selftest.py` | caller | Ruft dieselbe Funktion Zeile 673 für den Post-Deploy-Scope auf; profitiert automatisch von der Korrektur |
| `.claude/hooks/e2e_commit_gate.py::detect_scope` | separater Pfad, NICHT geändert | Eigenständige Kopie derselben Klassifikationslogik für den Pre-Commit-Pfad (`/e2e-verify`), hat denselben `frontend/`-Präfix-Bug, aber anderer Aufrufer und nicht Teil des gemeldeten Vorfalls — siehe Known Limitations |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` | Vorgänger-Spec | AC-3 dort bleibt für echten Frontend-Code gültig; wird um einen klarstellenden Halbsatz ergänzt |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | `_detect_scope_from_git_diff`: `frontend/e2e/`-Präfix als zusätzliche Bedingung im bestehenden neutralen `elif`-Block (analog `tests/`, Zeile 241) aufnehmen — Prüfung MUSS vor der generischen `path.startswith("frontend/")`-Bedingung greifen, damit `frontend/e2e/*` NICHT `has_frontend=True` setzt, während `frontend/src/...` etc. weiterhin `has_frontend=True` setzt |
| `tests/tdd/test_e2e_frontend_scope_neutral.py` (neu) | CREATE | Kern-Schicht-Tests gegen echtes Temp-Git-Repo (kein Mock), Vorbild `tests/tdd/test_issue_1121_git_diff_returncode.py` und `tests/tdd/test_scope_tests_neutral.py` |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` | MODIFY (klein) | AC-3 um einen kurzen klarstellenden Halbsatz/Verweis auf diese Spec ergänzen (keine Verhaltensänderung an AC-3 selbst, nur Präzisierung: "Datei unter `frontend/`" meint ausgelieferten Code, nicht `frontend/e2e/`) |

### Estimated Changes
- Files: 3
- LoC: +~10/-0 (Produktivcode ~3-6 Zeilen inkl. Kommentar; Tests ~80-150 Zeilen; Spec-Ergänzung ~2-3 Zeilen — Doku/Tests zählen laut CLAUDE.md nicht ins LoC-Limit)

## Implementation Details

Aktuelle Struktur der Schleife in `_detect_scope_from_git_diff` (Zeile 223-250):

```
for path in changed:
    if path.startswith("frontend/"):
        has_frontend = True
    elif (backend-Präfixe: src/, api/, internal/, cmd/):
        has_backend = True
    elif (neutral: docs/, .claude/, .md, README, .gitignore, tests/, openspec.yaml):
        pass
    else:
        has_backend = True
```

Der `if path.startswith("frontend/")`-Zweig steht VOR dem neutralen `elif`-Block
und greift daher für jede `frontend/`-Datei zuerst — auch für `frontend/e2e/*`.
Die Reihenfolge der Bedingungen in der Schleife muss so geändert werden, dass
`frontend/e2e/` VOR dem generischen `frontend/`-Zweig geprüft wird (z.B. als
eigene `if`-Bedingung vor dem bestehenden `if path.startswith("frontend/")`, die
bei Treffer `continue`/`pass` auslöst, oder durch Umsortierung der `elif`-Kette
so, dass `frontend/e2e/` zuerst abgefragt wird). `frontend/src/`, `frontend/static/`
und alle anderen `frontend/`-Unterpfade bleiben unverändert `has_frontend=True`.

Verzeichnis-Präfix (`frontend/e2e/`), nicht Datei-Endungs-Filter: durch Grep
verifiziert, `frontend/e2e/` enthält ausschließlich `*.spec.ts`,
`*.staging.setup.ts`, `playwright.*.config.ts` (u.a. `frontend/playwright.config.ts`
fixiert `testDir: 'e2e'` stabil), Shell-Skripte (`ci-stack.sh`, `e2e-env.sh`,
`start-preview.sh`), Test-Fixtures (`.gpx`) und Test-Helfer (`helpers.ts`,
`apiProxyTarget.ts`, `prodUrlGuard.ts`) — kein Import von dort in produktiven
`frontend/src/**`-Code. Ein Verzeichnis-Präfix statt Endungs-Filter erfasst auch
Helfer/Fixtures/Configs mit, sonst blockten reine Testinfra-Änderungen weiter.

Ein erklärender Kommentar analog zum bestehenden `tests/`-Kommentarblock
(Zeile 241-247) sollte die Begründung (Testinfrastruktur, kein Produktivcode,
kein Deploy-Drift-Risiko, symmetrisch zu `tests/`) im Code festhalten.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht, deterministisch: echtes temporäres Git-Repo (`git init`, echte
Commits mit echten Dateipfaden), Hook-Dateien aus dem aktuellen Arbeitsverzeichnis
(Worktree) in das Temp-Repo kopiert — **kein Mock** von `subprocess`/git, analog
`tests/tdd/test_issue_1121_git_diff_returncode.py` und
`tests/tdd/test_scope_tests_neutral.py`. Neue Datei
`tests/tdd/test_e2e_frontend_scope_neutral.py`.

- [ ] Test 1 (AC-1): GIVEN ein Commit ändert ausschließlich eine Datei unter
      `frontend/e2e/` (z.B. `frontend/e2e/foo.spec.ts`) WHEN
      `_detect_scope_from_git_diff` läuft THEN Rückgabe `docs-only`
- [ ] Test 2 (AC-2): GIVEN ein Commit ändert sowohl `frontend/e2e/foo.spec.ts`
      als auch `frontend/src/routes/+page.svelte` WHEN
      `_detect_scope_from_git_diff` läuft THEN Rückgabe `frontend-only`
      (keine Verwässerung bei echtem Frontend-Code)
- [ ] Test 3 (AC-3): GIVEN ein Commit ändert sowohl `frontend/e2e/foo.spec.ts`
      als auch eine Backend-Datei (`src/app/cli.py`) WHEN
      `_detect_scope_from_git_diff` läuft THEN Rückgabe `backend`, NICHT
      `full-stack`
- [ ] Test 4 (AC-4): GIVEN ein Commit ändert `frontend/e2e/foo.spec.ts` sowie
      `docs/README.md` und `tests/tdd/test_bar.py` WHEN
      `_detect_scope_from_git_diff` läuft THEN Rückgabe `docs-only`
- [ ] Test 5 (AC-5): GIVEN ein Ancestor-Commit ist mit VERIFIED-Attestation
      getaggt und der Zuwachs zum HEAD enthält ausschließlich
      `frontend/e2e/*`-Änderungen WHEN `staging_gate.gate_check` end-to-end
      läuft THEN Exit 0 (Ancestor-Relaxierung greift korrekt)
- [ ] Test 6 (AC-6): GIVEN ein Commit ändert ausschließlich echten Frontend-Code
      (`frontend/src/lib/foo.ts`), KEINE `frontend/e2e/`-Datei WHEN
      `_detect_scope_from_git_diff` läuft THEN Rückgabe weiterhin
      `frontend-only` (Regressionsschutz, Bestandsverhalten unverändert)

## Acceptance Criteria

- **AC-1:** Given ein Diff enthält ausschließlich Dateien unter `frontend/e2e/`
  (z.B. `frontend/e2e/foo.spec.ts`, `frontend/e2e/helpers.ts`), When
  `_detect_scope_from_git_diff` auf diesem Diff läuft, Then liefert die Funktion
  `docs-only`.
  - Test: `test_e2e_frontend_scope_neutral.py::test_ac1_e2e_only_is_docs_only`
    gegen echtes Temp-Git-Repo mit committeter `frontend/e2e/foo.spec.ts`.

- **AC-2:** Given ein Diff enthält sowohl eine Datei unter `frontend/e2e/` als
  auch eine Datei unter `frontend/src/` (echter Frontend-Code), When
  `_detect_scope_from_git_diff` läuft, Then liefert die Funktion weiterhin
  `frontend-only` (keine Verwässerung bei echtem Frontend-Code).
  - Test: `test_ac2_e2e_plus_frontend_src_is_frontend_only` mit beiden Pfaden im
    selben Commit.

- **AC-3:** Given ein Diff enthält sowohl eine Datei unter `frontend/e2e/` als
  auch eine Backend-Datei (`src/`, `api/`, `internal/` oder `cmd/`), When
  `_detect_scope_from_git_diff` läuft, Then liefert die Funktion weiterhin
  `backend`, NICHT `full-stack`.
  - Test: `test_ac3_e2e_plus_backend_is_backend_not_full_stack` mit
    `frontend/e2e/foo.spec.ts` + `src/app/cli.py` im selben Commit.

- **AC-4:** Given ein Diff enthält eine Datei unter `frontend/e2e/` zusammen mit
  Dateien unter `docs/` und `tests/`, When `_detect_scope_from_git_diff` läuft,
  Then liefert die Funktion `docs-only`.
  - Test: `test_ac4_e2e_plus_docs_plus_tests_is_docs_only` mit allen drei Pfad-
    Klassen im selben Commit.

- **AC-5:** Given ein Ancestor-Commit trägt eine VERIFIED-Attestation und der
  Zuwachs zum HEAD enthält ausschließlich Änderungen unter `frontend/e2e/`,
  When `staging_gate.gate_check` (bzw. dessen `--detect-scope`/Ancestor-Pfad)
  end-to-end gegen ein echtes Temp-Repo läuft, Then liefert `gate_check` Exit 0
  (Ancestor-Relaxierung greift jetzt korrekt, keine irreführende
  Parallel-Sitzungs-Meldung mehr).
  - Test: `test_ac5_gate_check_ancestor_relaxation_with_e2e_only_increment`
    reproduziert den Live-Vorfall vom 2026-08-15 (PR-Stack #1736/#1852/#1881/#1882)
    im Kleinformat.

- **AC-6:** Given ein Diff enthält ausschließlich echten Frontend-Code unter
  `frontend/src/` (keine `frontend/e2e/`-Datei), When
  `_detect_scope_from_git_diff` läuft, Then liefert die Funktion weiterhin
  `frontend-only` — keine Regression am Bestandsverhalten.
  - Test: `test_ac6_frontend_src_only_still_frontend_only_no_regression`.

## Test-Politik

Ausschließlich echte temporäre Git-Repos mit echten Commits (`git init`,
`git add`, `git commit`) — kein Mock von `subprocess`, `git`, oder der
Klassifikationsfunktion selbst. Vorbild: `tests/tdd/test_issue_1121_git_diff_returncode.py`
(Hook-Dateien werden aus dem aktuellen Arbeitsverzeichnis/Worktree in das
Temp-Repo kopiert, nicht aus dem Hauptrepo hartkodiert — sonst falsches Grün aus
dem Worktree) und `tests/tdd/test_scope_tests_neutral.py` (Muster für das
bereits bestehende `tests/`-Pendant dieser Ausnahme). Getestet wird
Verhalten der echten Funktion gegen echte Dateipfade in echten Commits, nicht
Dateiinhalt-Checks.

## Known Limitations

- `e2e_commit_gate.py::detect_scope()` (Pre-Commit-Pfad für `/e2e-verify`) hat
  dieselbe `frontend/`-Präfix-Schwäche unabhängig dupliziert, ist aber eine
  separate Funktion mit anderem Aufrufer und war nicht Teil des gemeldeten
  Vorfalls (der lief über den Deploy-Pfad `staging_gate.py`). Wird in diesem Fix
  bewusst NICHT mitgeändert (Scope-Disziplin) — als möglicher Folge-Befund für
  #1199/#1197 zu notieren, falls die Adversary-Runde ihn aufwirft.
- Der Ancestor-Walk in `staging_gate.gate_check` ist auf eine feste Obergrenze
  an Commits begrenzt (siehe Vorgänger-Spec); dieser Fix ändert daran nichts.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Korrektur einer bestehenden Klassifikationsfunktion
  (Verzeichnis-Präfix-Ausnahme analog zum bereits bestehenden `tests/`-Präzedenzfall
  in derselben Funktion) — keine neue Architekturentscheidung, kein neues
  Entscheidungsfeld (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie) betroffen.

## Changelog

- 2026-08-15: Initial spec created
