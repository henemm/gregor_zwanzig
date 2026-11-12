# Context: fix-2503-red-tests-gate

## Request Summary
Issue #2503: Das Commit-Gate `touched_tests_gate.py` blockiert in der TDD-RED-Phase den
Commit neu angelegter, per Assertion roter Tests (beobachtet bei Go, #2261 A-2 S2). Es
unterscheidet nicht zwischen „Änderung macht bestehenden Test rot“ und „neuer RED-Test ist
erwartungsgemäß rot“. Folge: RED-Tests bleiben uncommittet oder werden absichtlich
nicht-kompilierbar geschrieben (belohnt schlechtere RED-Tests).

## Ursache (belegt)
- `.claude/hooks/touched_tests_gate.py` `main()`: Fehlschläge nach dem Lauf werden gegen
  `_vorzustand_messen()` abgeglichen (Wegwerf-Worktree von `HEAD`). Ein Test, der in `HEAD`
  noch gar nicht existiert, kann dort nicht rot sein → landet in `neu_rot` → Exit 2.
- Go (`_lauf_go`): Paket-weiter `go test`; neue Testfunktion → `--- FAIL: TestX` nur im
  Arbeitsstand. Kompiliert der Test nicht, liefert `_lauf_go` eine Störung → durchgelassen
  (genau die im Issue beschriebene Fehlanreiz-Lücke).
- Python (`_lauf_python`, nur `tests/unit/`): neue Testfunktion in bestehender Datei → dasselbe
  Problem. Neue Testdatei: im Vorzustand fehlt sie → pytest Exit 4 → `vorher_stoerung` →
  durchgelassen (zufällig).
- Frontend (`_lauf_frontend`): gleiche Logik über `not ok N - <name>`.
- Das Gate wird nur ausgelöst, wenn eine Quelldatei der drei Schichten gestagt ist
  (Go: `internal/`, `cmd/` inkl. `_test.go`).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/touched_tests_gate.py` | Zu ändern: Klassifikation neu_rot vs. neu angelegt |
| `tests/tdd/test_touched_tests_gate.py` | Bestehende Verhaltenstests mit Wegwerf-Repos (Python + ein Go-Fall `test_ac1d_…`) |
| `docs/specs/modules/feat_1481a_touched_tests_gate.md` | Ursprungs-Spec (#1481 Scheibe A), ACs 1–12 |
| `.claude/settings.json` (Z. 65) | Registrierung als PreToolUse-Bash-Hook |
| `.claude/hooks/broad_test_run_gate.py` | Muster: `hook_utils.get_active_workflow_name()` über den Shim |
| Plugin `core/hooks/workflow.py` `read_active_workflow_fast()` | Muster (tdd_enforcement): `(name, state)`; Phase in `state["current_phase"]` |

## Existing Patterns
- Hook-Vertrag: Exit 0 durchlassen, Exit 2 blockieren; eigene Störungen blockieren NIE (AC-7).
- Projekt-Hooks importieren `hook_utils` über den Shim in `.claude/hooks/` (sys.path-Erweiterung).
- Phasenabhängige Hooks lesen den aktiven Workflow (worktree-bewusst, `resolve_active_workflow`).
- Vorzustand wird gemessen, nie aus gepflegter Liste geglaubt (Adversary F001/F001b).

## Dependencies
- Upstream: git (diff --cached, worktree add), go test, pytest, node --test; ggf. hook_utils/workflow.
- Downstream: jeder `git commit` in jeder Sitzung mit gestagten Quelldateien.

## Lösungsrichtungen (für Analyse)
1. Phasen-Ausnahme (Issue-Vorschlag): nur bei `current_phase == phase5_tdd_red` dürfen Tests,
   die im Vorzustand nicht existierten, rot sein.
2. Existenz im Vorzustand messen: Fehlschlag, dessen Test in `HEAD` nicht existiert, ist „neu
   angelegt“. Ermittlung z. B. über `git grep -w <Testname> HEAD -- <Paket/Datei>` oder über die
   Menge der im Vorzustand gelaufenen Tests (`go test -v` → `=== RUN`).
   Kombination 1+2 ist die engste Lockerung.

## Risks & Considerations
- Aufweichen darf keinen Umgehungsweg öffnen: bestehenden roten Test umbenennen/löschen und
  neu anlegen → wäre „neu“. Gegenprobe im Adversary.
- Phase stammt aus Workflow-State; ohne aktiven Workflow (z. B. Fast Track) gilt keine Ausnahme.
- Go-Subtests (`TestA/sub`) und Python-Parametrisierungen (`test_x[a]`) beim Namensabgleich.
- Risiko-Stufe hoch (Gate-Code) → mindestens 2 Adversary-Runden.

## Analysis

### Type
Bug (Gate-Fehlklassifikation: neu angelegter RED-Test wird als Regression gewertet)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/touched_tests_gate.py` | MODIFY | Läufer liefern zusätzlich die Menge der GELAUFENEN Tests; Klassifikation `neu_rot` / `neu_angelegt_rot` / `vorbestehend`; Phasenabfrage über `hook_utils` |
| `tests/tdd/test_touched_tests_gate.py` | MODIFY | Neue Verhaltensfälle mit Wegwerf-Repos (Python + Go, inkl. Subtest), Workflow-State-Datei im Wegwerf-Repo |
| `docs/specs/modules/fix_2503_red_tests_gate.md` | CREATE | Mini-Spec mit ACs (Erweiterung von feat_1481a) |

### Scope Assessment
- Files: 3 (2 Code, 1 Spec)
- Estimated LoC: Gate +50/-10, Tests +130
- Risk Level: MEDIUM — Gate läuft bei jedem Commit mit gestagten Quelldateien; ein Fehler lockert eine Ratsche oder blockiert Arbeit. Mindestens 2 Adversary-Runden.

### Technical Approach (Empfehlung: Kombination 1+2, engste Lockerung)
1. **Existenz im Vorzustand MESSEN, nicht per Namenssuche raten.** Die Läufer geben
   `(fehlgeschlagen, gelaufen, störung)` zurück. Der Vorzustandslauf liefert die Menge der
   Tests, die in `HEAD` überhaupt existierten:
   - Go: `go test -v` → `=== RUN <Name>` (inkl. `Parent/sub`).
   - Python: `-rA` → `PASSED|FAILED|ERROR|SKIPPED|XFAIL <id>`-Zeilen; neue Datei im Vorzustand
     → Exit 4 bleibt Störungspfad (heutiges Verhalten, durchlassen).
   - Frontend: TAP `ok N - name` / `not ok N - name`.
   `git grep` verworfen: Namensgleichheit in Kommentaren/anderen Paketen täuscht Existenz vor
   (Muster „gemessen statt geglaubt“, F001).
2. **Klassifikation** je Fehlschlag `f`:
   - `f` in vorher_rot → vorbestehend (unverändert).
   - `f` nicht in vorher_gelaufen → **neu angelegt rot**.
   - sonst → `neu_rot` (blockiert, unverändert).
   - Go-Elternfunktion: `--- FAIL: TestA` ist entschuldigt, wenn sie fehlschlagende Subtests hat
     und ALLE davon neu angelegt sind (neuer Subtest in bestehender Funktion). Sonst `neu_rot`.
3. **Phasen-Ausnahme:** „neu angelegt rot“ lässt den Commit NUR durch, wenn der aktive Workflow
   (`hook_utils.get_active_workflow_name()` + State `current_phase`, worktree-bewusst) in
   `phase5_tdd_red` steht; Ausgabe als Hinweis „neu angelegt rot (TDD-RED, blockiert nicht)“ mit
   Testnamen. In jeder anderen Phase oder ohne Workflow blockiert er wie bisher, mit eigener
   Meldung („neu angelegter Test ist rot — nur in Phase TDD-RED erlaubt“). Phase nicht lesbar ⇒
   keine Ausnahme (fehlende Erlaubnis, kein Störungsfall des Gates).
4. Zweiter Lauf entsteht weiterhin nur, wenn etwas rot ist (Kosten unverändert).

### Befunde gegen den Plan / Restrisiken
- **Umbenennungs-Umgehung:** In Phase RED einen bestehenden grünen Test umbenennen und rot machen
  ⇒ gilt als „neu“. Begrenzt durch Phasenbindung (RED-Phase erlaubt per Hook ohnehin nur
  Test-Schreibzugriffe); jeder so durchgelassene Test wird namentlich gemeldet. Gegenprobe im Adversary.
- **Geänderter bestehender Test in RED** (Assertion verschärft) bleibt blockiert — bewusst außer
  Scope (Issue betrifft neu angelegte Tests).
- **Go-Übersetzungsfehler** bleibt Störung → durchlassen (AC-7 der Ursprungs-Spec); der Fehlanreiz
  entfällt, weil kompilierbare rote Tests jetzt committbar sind.
- `go test -v` rückt Subtest-Zeilen ein: Fehlschlag-Muster muss führende Leerzeichen zulassen
  (`^\s*--- FAIL:`); heutiges `^--- FAIL:` übersieht eingerückte Subtests.

### Dependencies
- `hook_utils` (Plugin-Shim) für Workflow-Name; Workflow-State `.claude/workflows/<name>.json`.
- Downstream: jeder `git commit` mit gestagten Quelldateien der drei Schichten.

### Open Questions
- keine (Verhalten durch Issue #2503 und Ursprungs-Spec feat_1481a festgelegt; reine
  Tooling-Entscheidung, kein PO-Thema)
