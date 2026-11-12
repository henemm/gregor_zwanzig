# Context: fix-2227-override-zwei-gates

## Request Summary
Issue #2227 (Triage C4-09 aus #1199, Kriterium b: Sicherheitsrisiko): Tippt der PO „override", um
eine Sperre freizugeben (typisch: LoC-Limit im Plugin-`edit_gate`), öffnet dasselbe Token auch die
Projekt-Sperre gegen breite Testläufe (`broad_test_run_gate`) und den Prod-Versand-Wächter
(`prod_send_gate`). Am 2026-08-10 (#1660 B) fuhr ein Subagent deshalb pytest ohne Socket-Sperre —
genau der Weg, auf dem #1477 echte Telegram-Nachrichten an den Produktiv-Chat verschickt hat.

## Mechanik (gemessen am Stand origin/main acb368cc8)
- **Erzeuger (Plugin, anderes Repo):** `agent-os-openspec/core/hooks/phase_listener.py:504` —
  UserPromptSubmit; Schlüsselwort `override` (Konfig `override_token.keywords`, leading_only,
  wenige Zusatzwörter) → `override_token.create_token(<aktiver Workflow>|"__global__")`.
  Datei: `<Haupt-Repo>/.claude/user_override_token.json` (v2: `tokens.<workflow>.created`,
  TTL 1 h, `find_project_root()` löst Worktrees auf Haupt-Repo auf). Token ist **nicht** an eine
  Sperre gebunden, nur an den Workflow-Namen.
- **Verbraucher im Plugin:** `edit_gate.py` (LoC-Limit, Config-/Infra-Schutz, `_has_override_token`
  Z. 696 ff.), `bash_gate.py` (`_any_override_token`, main-Push, Autonomie-Env, Abhängigkeiten …).
  Plugin-Verbraucher sind nicht Gegenstand dieses Issues.
- **Verbraucher im Projekt:**
  - `.claude/hooks/broad_test_run_gate.py:123` `_has_valid_override` — **nicht verbrauchend**
    (bewusst, Docstring), gilt 1 h für beliebig viele breite pytest-Läufe; Ausgang 4 der Regel
    (Docstring Z. 51). Pfad über `hook_utils.find_project_root()` → liest dieselbe Datei wie der
    Schreiber.
  - `.claude/hooks/prod_send_gate.py:330` `_has_valid_override` — verbrauchend (Einmal), Pfad über
    eigenes `_project_root()` (CLAUDE_PROJECT_DIR / git toplevel) → im Worktree divergierend
    (#2125 Defekt 1), Name aus `GZ_ACTIVE_WORKFLOW`/`OPENSPEC_ACTIVE_WORKFLOW`.
  - `.claude/hooks/staging_gate.py`: Treffer nur `scope_override` (anderes Konzept, nicht betroffen).

## Wesentliche Beobachtung
Seit #1755 (geschlossen) gibt es einen **sicheren Offline-Volllauf** (wörtliche Zeile mit
`--disable-socket … --loopback-own-ports`), der ohne Freigabe erlaubt ist. Damit ist der
Override-Ausgang des Testlauf-Gates fachlich kaum noch nötig; die Doku
(`docs/reference/gates_und_ratschen.md` Abschnitt „Breiter Testlauf gesperrt", Z. ~241) trägt für
genau diesen Ausgang ein **abgelaufenes Prüfdatum 2026-11-01**. Kandidat: Ausgang ersatzlos
streichen statt umbauen (Gate-Audit-Linie #1197 „Fang-Nachweis oder raus").

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/broad_test_run_gate.py` | Override-Ausgang (Z. 51-54 Doku, 123-146, 395, 415, 446) |
| `.claude/hooks/prod_send_gate.py` | teilt das Token (Z. 24, 312-358, 368, 393) |
| `docs/reference/gates_und_ratschen.md` | Z. 216, 241-242 (Prüfdatum), 699 |
| `docs/specs/modules/gate_1148_prod_send_deny.md` | Spec des Prod-Send-Gates, AC-3 Override einmalig |
| `tests/tdd/test_broad_test_run_gate_offline_form.py`, `test_broad_test_run_gate_pytest_word_position.py`, `test_pytest_collection_and_timeout_safety.py` | bestehende Gate-Tests |
| `tests/tdd/test_issue_1148_prod_send_gate.py` | Override-Tests des Prod-Send-Gates |
| Plugin `core/hooks/phase_listener.py`, `override_token.py` | Erzeuger (anderes Repo, nur lesen) |

## Existing Patterns
- Projekt-Gates lesen das Plugin-Token mit eigenem Mini-Reader (kein Plugin-Import), Format v2.
- Gate-Tests rufen den Hook als Subprozess mit JSON-Payload auf (kein Mock).
- „Fang-Nachweis oder raus" (#1197): Ausgänge ohne Nutzen werden zurückgebaut.

## Dependencies
- Upstream: Plugin-Token-Datei und -Format, `hook_utils.find_project_root/get_active_workflow_name`.
- Downstream: Doku (gates_und_ratschen, CLAUDE.md-Zeile „uv run pytest gesperrt"), Gate-Meldung
  „4. Freigabe des Users", Specs.

## Existing Specs
- `docs/specs/modules/gate_1148_prod_send_deny.md`
- Spec zum Testlauf-Gate: in der Analyse suchen (#1477/#1755).

## Risks & Considerations
- #2125 (offen): Prod-Send-Override wirkt im Worktree gar nicht (Pfad-/Namens-Divergenz, Schreiber
  feuerte am 30.08. nicht). Ein Umbau des Prod-Send-Overrides berührt #2125 — Abgrenzung in der
  Analyse festlegen (nicht still mitlösen, nicht verschlimmern).
- Plugin liegt in einem anderen Repo; eine sperrenspezifische Freigabe im Plugin wäre ein
  Querschnittsumbau. Projekt-lokale Lösung bevorzugen.
- Gate-Code = hohes Risiko → Adversary mindestens 2 Runden.
- Wegfall eines Ausgangs darf keinen legitimen Arbeitsweg verbauen (Offline-Volllauf muss bleiben).

## Analysis

### Type
Bug (Sicherheitsrisiko: Freigabe für eine Sperre öffnet eine fremde Sperre)

### Befund (gemessen im Worktree, Stand nach Merge origin/main)
- `broad_test_run_gate.py` hat den Override-Ausgang an zwei Stellen: `_check_raw` (Z. ~415) und
  `main` (Z. ~446), Leser `_has_valid_override` Z. 123–146 (nicht verbrauchend, 1 h gültig für
  beliebig viele breite Läufe), Hinweistext Z. 395, Docstring Ausgang 4 Z. 51–54.
- **Kein einziger Test** deckt den Override-Ausgang des Testlauf-Gates ab (`user_override_token`
  kommt in `tests/` nur in `test_issue_1148_prod_send_gate.py` vor). Der Ausgang ist weder
  gefangen noch bewacht.
- Seit #1755 gibt es den sicheren Offline-Volllauf (wörtliche Zeile, Socket-Sperre + nur eigene
  Loopback-Ports) — der einzige legitime Grund für einen breiten Lauf ist damit ohne Freigabe
  abgedeckt. Doku-Prüfdatum für den Ausgang (2026-11-01) ist abgelaufen.
- Das Token ist im Plugin an den Workflow-Namen gebunden, nicht an eine Sperre. Eine
  sperrenspezifische Freigabe bräuchte einen Plugin-Umbau (anderes Repo, Querschnitt).

### Entscheidung (Tech Lead)
**Override-Ausgang des Testlauf-Gates ersatzlos streichen** (Gate-Audit-Linie #1197 „Fang-Nachweis
oder raus", abgelaufenes Prüfdatum). Verworfen:
- *Sperrenspezifisches Token im Plugin* — Querschnittsumbau in fremdem Repo für einen Ausgang, den
  niemand mehr braucht.
- *Eigenes Stichwort nur für das Testlauf-Gate* — neuer Mechanismus ohne Bedarf; ein breiter Lauf
  MIT Netz ist genau der #1477-Weg und soll nicht freigebbar sein.

Danach gilt: ein breiter Lauf ist NUR noch über benannte Dateien, `--collect-only` oder die
wörtliche Offline-Zeile möglich; „override" wirkt auf dieses Gate nicht mehr.

### Abgrenzung Prod-Versand-Wächter (#2125)
`prod_send_gate.py` liest dasselbe Token, verbraucht es aber (Einmal) und wirkt im Worktree heute
gar nicht (#2125, offen). Dieser Fix ändert das Prod-Send-Gate **nicht** (nicht still mitlösen).
Die Kreuzbindung (LoC-„override" gibt auch einen Prod-Versand frei) wird als Anforderung in #2125
vermerkt: wer dort den Override wirksam macht, muss ihn an das Prod-Send-Gate binden.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/broad_test_run_gate.py` | MODIFY | `_has_valid_override`, `_OVERRIDE_TTL`, beide Aufrufe, Hinweis „4. Freigabe", Docstring-Ausgang 4 entfernen; ungenutzte Imports (`datetime`) |
| `tests/tdd/test_broad_test_run_gate_ignores_override.py` | CREATE | Verhaltenstest: gültiges Token + breiter Lauf (normaler Pfad UND Roh-Scan-Pfad `sh -c`) → Exit 2; Offline-Zeile/benannte Datei mit Token weiterhin Exit 0 |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Test-Politik-Absatz und Abschnitt „Breiter Testlauf gesperrt": Einmal-Freigabe streichen, Prüfdatum-Satz anpassen |
| `docs/specs/modules/fix_2227_override_zwei_gates.md` | CREATE | Spec |

### Scope Assessment
- Files: 4 (2 Code/Test, 2 Doku)
- Estimated LoC: +~90 (Test) / −~40 (Gate), Doku ±10
- Risk Level: MEDIUM — Gate-Code; Wegfall eines Ausgangs macht nur strenger. Risiko ist ein
  verbauter Arbeitsweg: geprüft, Offline-Volllauf und benannte Dateien bleiben.

### Test-Hinweise für RED
- Hook als Subprozess mit JSON-Payload (Muster der bestehenden Gate-Tests), Token-Datei im
  v2-Format (`tokens.<workflow>.created` = jetzt) unter einem temporären Projekt-Root; Projekt-Root
  und Workflow-Name über die Mechanik von `hook_utils.find_project_root` /
  `get_active_workflow_name` lenken (in RED klären, wie die bestehenden Tests das tun).
- RED-Nachweis: heute Exit 0 mit Token → nach Fix Exit 2.
- Mutationsprobe: Override-Aufruf an einer der zwei Stellen wieder einsetzen → Test muss rot werden
  (daher beide Pfade testen).

### Dependencies
- Plugin-Token-Format (nur gelesen, unverändert); `hook_utils`.
- Bestehende Gate-Tests (`test_broad_test_run_gate_offline_form.py`,
  `..._pytest_word_position.py`, `test_pytest_collection_and_timeout_safety.py`) müssen grün bleiben.

### Open Questions
- keine (technische Entscheidung, keine Produktfrage)
