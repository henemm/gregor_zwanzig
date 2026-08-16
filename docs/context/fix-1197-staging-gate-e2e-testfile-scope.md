# Context: fix-1197-staging-gate-e2e-testfile-scope

## Request Summary
Deploy-Gate (`staging_gate.py`, indirekt auch `prod_selftest.py`) stuft Playwright-E2E-Testdateien unter `frontend/e2e/**` fälschlich als echten Frontend-Code ein und verlangt dadurch nach reinen Doku-/Tooling-Merges eine volle Staging-Verifikation, obwohl CLAUDE.md dafür eine Ausnahme vorsieht. Auslöser: PO-Fund vom 2026-08-15 in Issue #1197 (Kommentar https://github.com/henemm/gregor_zwanzig/issues/1197#issuecomment-... zu Commits e58863e9..fe78d473).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/_e2e_paths.py` (`_detect_scope_from_git_diff`, Z.206-258) | Geteilte Klassifikationsfunktion — hier liegt der Bug. `frontend/`-Präfix zieht `has_frontend=True`, auch für `frontend/e2e/*.spec.ts` |
| `.claude/hooks/staging_gate.py` (`gate_check`, Z.495-624) | Ruft `_detect_scope_from_git_diff` sowohl direkt (Z.202) als auch in der Ancestor-Relaxierung (Z.621) auf — Aufrufer #1 des Bugs |
| `.claude/hooks/prod_selftest.py` (Z.673) | Ruft dieselbe Funktion für den Post-Deploy-Scope auf — Aufrufer #2, gleiche Schieflage möglich |
| `.claude/hooks/e2e_commit_gate.py` (`detect_scope`, Z.66-120) | **Separate, eigenständige Kopie** derselben Klassifikationslogik für den Pre-Commit-Pfad (`/e2e-verify`). Hat denselben `frontend/`-Präfix-Bug, ist aber NICHT vom gemeldeten Vorfall betroffen (der lief über den Deploy-Pfad `staging_gate.py`). Bewusst außerhalb des Scopes dieses Fixes — siehe Risks. |
| `tests/tdd/test_issue_1121_git_diff_returncode.py` | Zeigt das Test-Pattern: echtes Temp-Git-Repo, Hook-Dateien reinkopiert, keine Mocks. Wird als Vorlage für den neuen Test übernommen |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` | Vorgänger-Spec (AC-3 dort: "Zuwachs enthält Datei unter `frontend/` → Exit 1"). Unsere Änderung wirkt UNTERHALB dieser Logik (in der Klassifikationsfunktion selbst) und verändert, was als "Datei unter `frontend/`" im Sinne von echtem Code zählt |

## Existing Patterns
- **`tests/` bereits ausgenommen:** Die Funktion behandelt `path.startswith("tests/")` schon heute als Nicht-Code (Zeile 241) — dieselbe Begründung (Testinfrastruktur, kein Produktivcode, kein Deploy-Drift-Risiko) gilt symmetrisch für `frontend/e2e/`.
- **Fail-closed bei Unsicherheit:** Jede unbekannte/neue Pfad-Klasse fällt konservativ auf `has_backend=True` bzw. `has_frontend=True` (Else-Zweig, Zeile 249-250). Die Lösung muss diese Fail-closed-Haltung für echten Frontend-Code (`frontend/src/`, `frontend/static/` etc.) unverändert lassen — nur `frontend/e2e/` wird neu ausgenommen.
- **Präzedenz im selben Sammel-Issue:** Mehrere vorherige Fixes in #1197 (Ancestor-Scope, Verdict-Merge, prod_selftest-Internal-URL-Skip) folgten demselben Muster: eigene Spec unter `docs/specs/modules/fix_1197_*.md`, Prüfdatum +90 Tage, Adversary-Runde, Live-Kommentar im Issue nach Deploy.

## Dependencies
- **Upstream:** `_git_diff_names()` (liefert die geänderten Pfade als Liste; bei git-Fehler `None` → fail-closed `"backend"`, unverändert zu lassen).
- **Downstream:** `staging_gate.gate_check()` (Deploy-Hard-Gate, entscheidet Exit 0/1 für `deploy-gregor-prod.sh`) und `prod_selftest.py` (Post-Deploy-Verdict-Klassifikation). Eine zu breite Ausnahme hier würde also den Deploy-Gate für ALLE Sessions aufweichen — daher eng auf `frontend/e2e/` fassen, nicht auf ganz `frontend/`.

## Existing Specs
- `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` — Ancestor+Scope-Relaxierung (2026-07-16), definiert das aktuelle Verhalten bei gestapelten Commits.
- `docs/specs/modules/fix_1382_deploy_gate_evidence.md` — Grundlogik der commit-getaggten Attestation.
- `docs/specs/modules/fix_1197_prod_selftest_internal_url_skip.md` — Schwester-Fix im selben Issue (analoges Muster: bekannte Nicht-Risiko-Klasse von der strikten Prüfung ausnehmen).

## Risks & Considerations
- **Nicht in Scope, aber gleiche Bug-Klasse:** `e2e_commit_gate.py::detect_scope()` (Pre-Commit-Pfad) hat dieselbe `frontend/`-Präfix-Schwäche, ist aber eine separate Funktion und nicht Teil des gemeldeten Vorfalls. Wird NICHT mitgeändert (Scope-Disziplin) — als möglicher Nebenbefund für #1199/#1197 notieren, falls die Adversary-Runde ihn aufwirft.
- **Zu breite Ausnahme wäre ein Sicherheitsloch:** Nur `frontend/e2e/` (Playwright-Testspecs, nicht ausgeliefert) darf ausgenommen werden — nicht `frontend/` pauschal. Ein echter Frontend-Code-Change muss weiterhin `has_frontend=True` auslösen.
- **Zwei Aufrufstellen in `staging_gate.py`:** sowohl der direkte Scope-Detect (Z.202) als auch die Ancestor-Relaxierung (Z.621) nutzen dieselbe Funktion — ein Fix an der Quelle wirkt auf beide, muss aber für beide getestet werden (AC-Abdeckung).
- **Konsistenz mit AC-3 der Vorgänger-Spec:** Deren AC-3 sagt "Datei unter `frontend/` → Block". Das bleibt für echten Frontend-Code weiterhin korrekt; nur die Definition von "Datei unter `frontend/`, die als Code zählt" wird präzisiert. Die neue Spec sollte das explizit referenzieren, damit kein scheinbarer Widerspruch entsteht.

## Prüfdatum-Registrierung
Nach Live-Deploy: Eintrag in `docs/reference/gates_und_ratschen.md` Prüfdatum-Tabelle (Zeile ~181) ergänzen, analog zu den bisherigen #1197-Fixes.

## Analysis

### Type
Bug (Kategorie c — fälschlich blockierendes Gate). Bestätigt durch bug-intake-Agent: Root Cause exakt wie vermutet, Zeile 226-227 in `_e2e_paths.py::_detect_scope_from_git_diff` — jede Datei mit Präfix `frontend/` zieht `has_frontend=True`, ohne Ausnahme für Testverzeichnisse (im Gegensatz zu `tests/`, Zeile 241).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | `frontend/e2e/`-Präfix in den bestehenden neutralen `elif`-Block aufnehmen (dort wo `tests/` bereits steht), strukturell konsistent mit dem Backend-Test-Präzedenzfall, inkl. erklärendem Kommentar |
| `tests/tdd/test_e2e_frontend_scope_neutral.py` (neu, Name TBD in Spec-Phase) | CREATE | Kern-Schicht-Tests gegen echtes Temp-Git-Repo (kein Mock), Vorbild `test_issue_1121_git_diff_returncode.py` / `test_scope_tests_neutral.py` |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` | MODIFY (klein) | AC-3 um klarstellenden Verweis auf die neue Ausnahme ergänzen, damit kein scheinbarer Widerspruch entsteht |

### Scope Assessment
- Files: 3 (1 Produktivdatei, 1 neue Testdatei, 1 Spec-Ergänzung)
- Estimated LoC: Produktivcode ~3-6 Zeilen; Tests ~80-150 Zeilen (mehrere Szenarien)
- Risk Level: LOW für die Änderung selbst (eng gefasste Verzeichnis-Ausnahme, durch Grep verifiziert: `frontend/e2e/` enthält ausschließlich `*.spec.ts`, `*.setup.ts`, `playwright.*.config.ts`, Shell-Skripte, Fixtures und Test-Helfer — kein Import von dort in `frontend/src/**` produktiv). Blast Radius bleibt HOCH eingestuft, weil die Funktion von zwei Deploy-Gate-Aufrufern geteilt wird — daher weiterhin volle Spec+Adversary-Pflicht.

### Technical Approach
Reine Verzeichnis-Präfix-Ergänzung (`frontend/e2e/`) im bestehenden neutralen `elif`-Zweig neben `tests/` — kein Playwright-Config-Parsing nötig (`testDir: 'e2e'` ist stabil per Konvention in `frontend/playwright.config.ts` verankert). Verzeichnis-Präfix statt Datei-Endungs-Filter, damit auch Helfer/Fixtures/Configs in `frontend/e2e/` mit abgedeckt sind (sonst blockten reine Testinfra-Änderungen weiter).

### Dependencies
- Downstream unverändert: `staging_gate.py` (Zeile 202, 621) und `prod_selftest.py` (Zeile 673) profitieren beide automatisch von der Korrektur an der Quelle.
- `fix_1197_deploy_gate_ancestor_scope.md` AC-3 braucht einen klarstellenden Verweis (kein Widerspruch, nur Präzisierung "Code" vs. "Testcode").
- `e2e_commit_gate.py::detect_scope()` hat denselben Bug unabhängig dupliziert, ist aber ein separater Pre-Commit-Pfad ohne direkten Deploy-Block-Effekt — als Known Limitation in der neuen Spec vermerken, nicht mitfixen.

### Open Questions
- [ ] Keine offenen Fragen — Ansatz ist eindeutig, durch zwei unabhängige Agenten (bug-intake, Plan) bestätigt.
