# Context: Issue #811 — Briefing-Mail-Qualität erzwingen (Modus-Matrix-Vertragstest + Renderer-Gate)

## Request Summary

Erzwingungs-**Infrastruktur** (kein Inhalts-Fix), die Mail-Defekte wie #806/#807/#808/#810
künftig vor dem Merge fängt: (A) ein parametrisierter Vertragstest gegen die **echt
gerenderte** Briefing-Mail über die Matrix `{full, compact} × {Einfach, Roh}`, und (B) ein
**un-überspringbarer Renderer-Gate-Hook**, der Commits am Mail-Pfad blockiert, bis (A) grün
lief **und** `briefing_mail_validator.py` Exit 0 lieferte — der Nachweis workflow-gebunden
hinterlegt (C optional: Golden-HTML-Snapshots).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py::fmt_val` (Z.420-509) | **Bug-Quelle #810**: wind/gust/precip/pop → `if html:`-Ampel-Return VOR `use_friendly`-Prüfung (Z.446,460,500). Vorbild korrekt: cloud Z.465-467, sunshine Z.482-486, cape Z.504. |
| `src/output/renderers/email/__init__.py::render_email` (Z.32-140) | Zentrale Render-Funktion. `email_format="full"\|"compact"`, gibt `(html, plain)`. compact → `render_compact` (ASCII, keine Emojis), full → `render_html`+`render_plain`. |
| `src/output/renderers/email/helpers.py::build_format_modes` (Z.768-781) | `display_config` → `{col_key: format_mode}`; `_effective_format_mode` löst `format_mode`/`use_friendly_format`/Katalog-Default. |
| `src/output/renderers/email/helpers.py::ampel_dot` (Z.369-393) | SSoT 4-Stufen-Ampel 🟢🟡🟠🔴; `_AMPEL_EMOJIS` Z.789. |
| `tests/tdd/test_issue_759_email_ampel.py` (Z.78-91, 169-188) | **Test der den Bug zementiert** — assertiert `fmt_val("wind",20,html=True)=="🟢"` ohne Modus. Achse HTML×Roh für wind/gust/precip/pop nirgends getestet. |
| `.claude/hooks/briefing_mail_validator.py` (Z.186-281) | Kanonisches Acceptance-Gate Trip-Briefing-Mail. Dispatch über `X-GZ-Mail-Type`/`X-GZ-Format`. **Braucht echte IMAP-Mail** (`GZ_IMAP_*`, Staging). Exit 0/1/2. Schreibt Validation-Log nach `.claude/workflows/_log/`. |
| `.claude/hooks/pre_commit_gate.py` (Z.176-317) | Bash/`git commit`-Gate. Liest `git diff --cached --name-only` (Z.202-213). Exit 2 blockiert. Lädt aktiven Workflow (Z.310-317). Blockt bei AMBIGUOUS/BROKEN-Verdict. |
| `.claude/hooks/workflow_gate.py` (Z.145-336) | Edit/Write-Gate je Phase. Session-ID-Auflösung Z.277-290. AC-Format-Hard-Block Z.319-336. |
| `.claude/hooks/workflow_state_multi.py` (Z.139-512) | State-API: `get_active_workflow`, `set_phase`, `add_test_artifact`, `mark_*_test_done`. State-Felder: `test_artifacts[]`, `phase_transitions[]`, `adversary_verdict`, `affected_files[]`. |
| `.claude/settings.json` (Z.15-124) | Hook-Registrierung: PreToolUse Edit\|Write-Kette (workflow_gate, red_test_gate, post_implementation_gate, scope_guard …) + Bash-Kette (`pre_commit_gate`, secrets_guard, e2e_commit_gate …). |
| `openspec.yaml` (`protected_paths`, Z.40-58) | Regex-Pattern→spec_type. Heute geschützt: `src/.*\.py$`, `email_spec_validator.py`, `e2e_browser_test.py`. |

## Existing Patterns

- **Gate-Hook:** `red_test_gate.py` — Phase-Check + Artefakt-Check im State, Exit 2 + stderr-Message. Vorbild für `renderer_mail_gate.py`.
- **Nachweis im State:** Validatoren schreiben Erfolgs-Log nach `.claude/workflows/_log/` (briefing_mail_validator Z.254-281, write-log-Mechanik). `test_artifacts[]` mit `{phase,type,path}` (add_test_artifact).
- **Scope-Erkennung:** `pre_commit_gate.has_backend_changes()` + `detect_scope` (HEAD~1..HEAD, NICHT `--cached` nach Commit — bekannter Bug #734).
- **Mock-frei:** Mail-Render-Tests rufen `render_email`/`build_mime_message` echt auf; Validator gegen echte IMAP-Mail (kein Mock, kein Gmail).
- **Modus-Matrix-Fixture:** `_make_seg_table_with_values(wind,gust,precip,pop)` (test_issue_759 Z.45-68) + `build_default_display_config` + `dp_to_row`.

## Dependencies

- **Upstream (was der Gate nutzt):** Workflow-State (`.claude/workflows/<name>.json`), `GZ_ACTIVE_WORKFLOW`, git diff, `briefing_mail_validator.py`-Exit/Log, der neue Vertragstest.
- **Downstream (was der Gate beeinflusst):** Jeder Commit/Edit der `src/output/renderers/email/*`, `src/formatters/*`, Mail-Pfad in `src/services/trip_report_scheduler.py` berührt → blockiert bis Nachweis vorhanden.

## Existing Specs

- `docs/specs/_template.md` — Spec-Template (AC-N-Format Pflicht).
- Vorbild `email_spec_validator.py` (Orts-Vergleich-Mail) vs. `briefing_mail_validator.py` (Trip-Briefing) — Geltungsbereich strikt getrennt (CLAUDE.md).

## Risks & Considerations

- **AC-1 ist heute RED:** #810 ist OPEN → der Vertragstest (Roh ⇒ keine Ampel) schlägt fehl. Scope-Entscheidung nötig: (a) #810-Mini-Fix bündeln (Test wird echt GREEN) vs. (b) `@pytest.mark.xfail(strict=True, reason="#810")` (Test dokumentiert Vertrag, Suite bleibt grün, flippt nach #810-Fix). → **PO-Frage.**
- **briefing_mail_validator braucht IMAP/Staging** → kann NICHT synchron im lokalen Commit-Hook laufen. Gate muss **Nachweis** prüfen (Log/State-Feld), nicht live ausführen. Deckt sich mit AC-3 (workflow-gebundener Nachweis).
- **Vertrag des 759-Tests ändert sich** bei #810-Fix: `fmt_val("wind",20,html=True)` würde im Roh-Modus zur Zahl → der zementierende 759-Test (Z.78-91) müsste angepasst/ersetzt werden.
- **LoC-Limit 250:** Neuer Hook (~120) + Vertragstest (~120) + settings.json/openspec.yaml → wahrscheinlich Override nötig.
- **Kein globaler Bypass (AC-3):** Nachweis muss an aktiven Workflow + aktuellen Commit-Stand gebunden sein, sonst Gate-Erosion.
- **False-Positive-Gefahr:** Gate darf legitime Doku-/Test-only-Edits am Mail-Pfad nicht unnötig blocken (Scope-Filter wie pre_commit_gate).
