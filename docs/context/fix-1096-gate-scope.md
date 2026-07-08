# Context: fix-1096-gate-scope

**Issue:** #1096 — test_staging_gate.py::TestGateCheckModeB läuft gegen live Hauptrepo (flaky bei docs-only-HEAD) + operativer Folgeschaden: Scope-Marker klassifiziert echte Code-Deploys als `docs-only` (Kommentar vom 2026-07-08, Deploy #1097).

## Request Summary

Zwei verwandte Defekte mit gemeinsamer Wurzel (Scope-Erkennung gegen beweglichen, geteilten Zustand):

1. **Test-Fragilität:** 6 Tests in `TestGateCheckModeB` rufen `staging_gate.py --check` gegen das echte Hauptrepo auf, ohne `--scope`. Steht die Scope-Erkennung zufällig auf `docs-only`, greift der Skip-Zweig (Exit 0) VOR der eigentlich getesteten Prüflogik → Tests erwarten Exit 1 und werden rot ohne Code-Regress.
2. **Operative Gate-Erosion:** Beim Deploy von `3f5d3cfa` (#1097, reiner Frontend-Change) meldete der Post-Deploy-Selftest `Scope docs-only — Selftest übersprungen` und gab Exit 0 ohne zu prüfen. Auch die Attestation trägt `"scope": "docs-only"`.

## Kronbeweise (Stand 2026-07-08)

- `.claude/e2e_verified/3f5d3cfa….json`: `verified_at 07:29:25Z`, `scope: "docs-only"` — obwohl `git show --name-only 3f5d3cfa` ausschließlich `frontend/…` + `docs/…` zeigt (korrekt wäre `frontend-only`).
- `.claude/last_gate_scope.json` (mtime 07:30:20Z): `{"gate_scope_sha": "3f5d3cfa…", "gate_last_scope": "docs-only"}`.
- Selftest-Log 07:32Z: `INFO: Scope docs-only — Selftest übersprungen (kein Code-Deploy).`

## Root-Cause-Hypothesen (in Analyse zu verifizieren)

**H1 — Selbstvergiftung des Markers bei wiederholtem Gate-Lauf auf demselben HEAD:**
`_scope_diff_base()` liefert den Marker-SHA. Steht der Marker bereits auf HEAD (weil ein früherer Gate-Lauf für exakt diesen Commit lief), ist `git diff <HEAD>..HEAD` leer → `_detect_committed_scope()` gibt `docs-only` zurück (staging_gate.py:138-139). Der Skip-Zweig `gate_check()` (staging_gate.py:284-287) schreibt dieses `docs-only` dann in den Marker-Cache — und `prod_selftest._detect_committed_scope()` (prod_selftest.py:426-430, Cache aus #1084) gibt es fortan für diesen HEAD direkt zurück → falscher Selftest-Skip. Der #1084-Cache hat das HEAD..HEAD-Problem also nicht beseitigt, sondern den falschen Wert **persistiert**.

**H2 — Semantik-Fehler „leerer Diff = docs-only":** „Keine Änderungen seit dem letzten Gate-Lauf" ist NICHT dasselbe wie „dieses Deploy enthält keinen Code". Ein Re-Run/Re-Deploy desselben Code-Commits wird als docs-only durchgewunken.

**H3 — Scope-Override wird gecacht:** `gate_check()` schreibt bei `--scope=docs-only`-Override den Override-Wert in den Marker (Zeile 286: `write_last_gate_scope(…, scope)`), obwohl der Override nur für DIESEN Aufruf gemeint war und der HEAD ggf. mehr enthält.

Die exakte Ereignis-Sequenz beim #1097-Deploy (wer setzte den Marker vor 07:29 auf 3f5d3cfa?) ist offen — Analyse-Phase.

## Analysis (Phase 2, 2026-07-08)

### Type
Bug (Deploy-Gate-Erosion + Test-Fragilität, gemeinsame Wurzel)

### Forensisch bestätigte Root Cause (H-B + Asymmetrie-Befund)

Die Ereignis-Sequenz beim #1097-Deploy (belegt via `/tmp/gregor-deploy-gate.log`, Attestation-mtimes, Marker-mtime):

1. **07:15Z** — `3f5d3cfa` gepusht (Frontend-Change).
2. **~07:20-07:29Z** — Erster `gate_check()`-Lauf auf HEAD=`3f5d3cfa`: erkennt echten Scope, Gate besteht, schreibt Marker `{gate_scope_sha: 3f5d3cfa, gate_last_scope: <echt>}` (staging_gate.py:344).
3. **07:29:25Z** — `write_verdict()` (Validator): `_scope_diff_base()` = Marker-SHA = HEAD → `git diff HEAD..HEAD` leer → `"docs-only"` → **Attestation mit falschem Scope geschrieben**.
4. **07:30:20Z** — Zweiter `gate_check()`-Lauf: gleiche leere Diff-Logik → docs-only-Skip-Zweig (Z. 284-287) → **Marker-Cache mit `docs-only` überschrieben**.
5. **07:32Z** — `prod_selftest`: Cache-Guard (#1084) greift (SHA==HEAD) → liefert vergiftetes `docs-only` → **Selftest übersprungen, Exit 0 ohne Prüfung**.

Gleiches Muster bereits bei `b4620e97` (#1104, Attestation ebenfalls `docs-only` trotz Code). H-A (älterer Deploy) und H-C (expliziter `--scope=docs-only`-Override) forensisch widerlegt.

**Kern-Asymmetrie:** Der #1084-Cache-Guard (bei `gate_scope_sha == HEAD` den gecachten Scope zurückgeben statt zu diffen) existiert NUR in `prod_selftest.py::_detect_committed_scope()` (Z. 426-430) — `staging_gate.py::_detect_committed_scope()` (Z. 127-171) hat ihn nie bekommen. Die Schreibseite (staging_gate) vergiftet daher den Cache, den die Leseseite (prod_selftest) korrekt konsumiert.

**Zusatz-Befund Tests:** `TestGateCheckModeB` läuft mit `cwd=Hauptrepo` — Testläufe, die den vollen Check-Pfad bestehen, schreiben über Z. 344 in die ECHTE `.claude/last_gate_scope.json` (Tests mutieren produktiven Gate-State), zusätzlich zur Flakiness durch den docs-only-Skip-Vorrang.

### Technical Approach (Empfehlung Plan-Agent)

1. **Shared-Helper** `cached_scope_for_sha(repo_dir, sha)` in `_e2e_paths.py`: liefert `gate_last_scope` nur bei `gate_scope_sha == sha`, sonst `None` (Extraktion der prod_selftest-Logik).
2. `staging_gate.py::_detect_committed_scope()` prüft diesen Cache ZUERST, fällt sonst auf Diff-Logik zurück → Re-Run auf demselben HEAD liefert den echten Scope, nimmt den vollen Check-Pfad, Marker-Write bleibt idempotent korrekt. Selbstvergiftung strukturell unmöglich.
3. `prod_selftest.py` auf den Shared-Helper umstellen (Duplikat entfernen, Konvention „eine Quelle").
4. **Härtung:** docs-only-Skip-Zweig überschreibt einen bestehenden Nicht-docs-only-Cache-Eintrag für dieselbe SHA nicht mehr (deckt expliziten Override-Restfall ab).
5. **Test-Migration:** GANZE Klasse `TestGateCheckModeB` auf hermetisches Temp-Repo (Muster `test_issue_916_gate_scope_marker.py::_setup_repo`); Tests, die nicht die Scope-Erkennung testen, bekommen expliziten `--scope=backend`.
6. Verworfen: eigener „unchanged"-Zustand (unnötige dritte Semantik — Cache-Hit löst das Re-Deploy-Szenario sauber).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | +~8 LoC: `cached_scope_for_sha()` |
| `.claude/hooks/staging_gate.py` | MODIFY | +~8 LoC: Cache-Guard + Skip-Zweig-Härtung |
| `.claude/hooks/prod_selftest.py` | MODIFY | ~-5 LoC: Duplikat → Shared-Helper |
| `tests/tdd/test_staging_gate.py` | MODIFY | TestGateCheckModeB → hermetisches Temp-Repo |

### Scope Assessment
- Files: 4 (3 Hooks + 1 Testdatei)
- Estimated LoC (src, zählt gegen Limit): ~15-20 netto — weit unter 250
- Risk Level: HIGH (Deploy-Gate-Pfad), aber Änderungsrichtung konservativ (im Zweifel voller Check statt Skip)

### Dependencies
- `deploy-gregor-prod.sh` (henemm-infra) muss NICHT geändert werden (ruft `--check` ohne `--scope`; Fix macht Wiederholungsläufe selbst sicher).
- Doppel-Lauf pro Commit im Deploy-Gate-Log: Ursache unklar (parallele Deploys vs. Retry) → separater Folge-Issue, blockiert den Fix nicht.

### Open Questions
- Keine blockierenden. Verhaltensänderung Re-Deploy desselben Commits: statt fälschlichem Skip läuft der volle Check (Attestation muss gültig/frisch sein) — bewusst konservativer, in Spec als AC festhalten.

## Related Files

| File | Relevance |
|------|-----------|
| `tests/tdd/test_staging_gate.py` (358 LoC) | `TestGateCheckModeB` (Z. 85-195): 6 fragile Tests, hartkodiert `REPO_DIR=/home/hem/gregor_zwanzig`, `--check` ohne `--scope` |
| `.claude/hooks/staging_gate.py` (376 LoC) | `gate_check()` Z. 277-345 (docs-only-Skip VOR Prüfungen, Marker-Write Z. 286 + 344), `_detect_committed_scope()` Z. 127-171, `_scope_diff_base()` Z. 109-124 |
| `.claude/hooks/prod_selftest.py` | `_detect_committed_scope()` Z. 411-471 mit #1084-Scope-Cache (Z. 426-430), `run_selftest()` docs-only-Skip Z. 477-481 |
| `.claude/hooks/_e2e_paths.py` (141 LoC) | `write_last_gate_scope()` / `read_last_gate_scope_entry()` — Marker-Format `{gate_scope_sha, gate_last_scope}` |
| `tests/tdd/test_issue_916_gate_scope_marker.py` | **Vorbild-Muster** `_setup_repo()`: hermetisches Temp-Git-Repo mit kopierten Hook-Dateien (Z. 42-58) |
| `tests/tdd/test_bundle_e_gate_tooling.py` | Zweites etabliertes Hermetik-Muster |
| `tests/tdd/test_issue_1084_gate_scope_cache.py` | Tests des Scope-Caches — müssen bei Semantik-Änderung mitbetrachtet werden |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` Z. 104 | Aufrufer: `staging_gate.py --check` OHNE `--scope` (anderes Repo — Änderung dort nur falls nötig, dann MQ an `infra`) |

## Existing Patterns

- **Hermetisches Temp-Repo:** `_setup_repo(tmp_path)` — `git init`, Hook-Dateien nach `<repo>/.claude/hooks/` kopieren, Baseline-Commit, Gate via `subprocess` mit `cwd=repo`. Funktioniert, weil `REPO_DIR`-Auflösung in `staging_gate.py` dynamisch via `git rev-parse` aus cwd läuft (`_shared_repo_dir`/`_verified_repo_dir`).
- **Alternativ-Muster im Issue:** explizit `--scope=backend` an jeden `--check`-Aufruf → nimmt Scope-Erkennung aus der Testkette. (Schwächer: testet den Skip-Vorrang nicht mit.)
- **Marker-Historie:** #916 (Marker-SHA als Diff-Basis) → #988 (Robustheit) → #1084 (Scope-Cache-Feld `gate_last_scope`). Dieses Issue ist die dritte Iteration am selben Mechanismus.

## Dependencies

- **Upstream:** git-CLI (diff/rev-parse/cat-file), Marker-Datei `.claude/last_gate_scope.json` (geteilt, im Hauptrepo), Attestationen `.claude/e2e_verified/<sha>.json`.
- **Downstream:** `deploy-gregor-prod.sh` (Gate-Exit entscheidet Prod-Deploy), `prod_selftest.py` (Selftest-Skip-Entscheidung), staging-validator (`write_verdict` → `scope`-Feld der Attestation), Issue-Close-Regel (nur bei Selftest Exit 0).

## Existing Specs

- `docs/specs/modules/issue_1084_gate_scope_cache.md` — Scope-Cache (direkt betroffen)
- `docs/specs/modules/issue_916_988_gate_scope_robustness.md` — Marker-Mechanik
- `docs/specs/modules/issue_521_staging_validator.md` (falls vorhanden) — Ursprungs-ACs der Testdatei

## Risks & Considerations

- **Deploy-Gate = kritischster Pfad:** Jede Änderung an `gate_check()`-Semantik kann Deploys fälschlich blocken (Ops-Ärgernis) oder fälschlich durchwinken (Gate-Erosion). Fail-Richtung im Zweifel: blocken.
- **Gate-State-Dateien nie per Hand anfassen** (User-Stopp 2026-07-08): Der aktuell falsche Marker (`docs-only` für 3f5d3cfa) wird NICHT manuell korrigiert — nur via Tool/Fix.
- **Marker-Semantik ist doppelt belegt:** SHA = Diff-Basis für NÄCHSTEN Lauf (#916) UND Cache-Key für DENSELBEN Commit (#1084). Genau diese Doppelrolle kollidiert.
- **`.claude/`-Änderungen klassifizieren selbst als docs-only** → das Fix-Deploy dieses Workflows wird den Selftest regulär skippen; Verifikation muss anders erfolgen (hermetische Tests + gezielter Staging-Nachweis).
- **Tests laufen gegen die Hauptrepo-Kopie der Hooks:** Bei Umstellung auf Temp-Repo-Kopien testet man die Worktree-Kopie — Quelle beim Kopieren bewusst wählen (Muster von #916 nutzen).
- **Kein Fix von `deploy-gregor-prod.sh` in diesem Repo** — falls nötig, MQ-Nachricht an `infra`.
