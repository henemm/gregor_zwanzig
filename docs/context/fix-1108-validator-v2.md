# Context: fix-1108-validator-v2

## Request Summary

Issue #1108: `.claude/hooks/email_spec_validator.py` (Gate für Ortsvergleich-Mails) auf den
v2-Mail-Vertrag aus #1110 umstellen. Der Validator prüft heute noch den ALTEN
Ski-Vergleich-Vertrag (Winner-Box/„Recommendation"-Pflicht, 8 englische Zeilen-Labels,
`class="matrix-table"`) — strukturell unbestehbar gegen die seit Commit `a1c48572`
(2026-07-08) auf main liegende v2-Mail. Erst nach diesem Issue kann #1110 E2E-verifiziert
und deployed werden (PO-Umscoping 2026-07-08, dokumentiert in #1110/#1108-Kommentaren).

## Vorgeschichte / Warum eigener Workflow

Gate-Dateien werden NIE im Feature-Workflow editiert (PO-Stopp 2026-07-08,
Memory `feedback_validator_changes_own_workflow`, #997-Muster). Hier ist der Validator das
Deliverable. Der Harness-Prompt „sensitive file" beim Edit ist erwartet und legitim.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/email_spec_validator.py` | Das Deliverable — Kernfunktionen `validate_structure` (Pflicht-Sektionen inkl. „Recommendation/Empfehlung", Z. ~236–244), Zeilen-Label-Vertrag (Z. ~214–224), `_find_matrix_table_html`/`extract_table_rows` (matrix-table-Klasse, Z. 119–172), `validate_hourly_table` (Z. 354ff), Marker `X-GZ-Mail-Type: compare` |
| `tests/tdd/test_issue_1046_email_validator_table_contract.py` | Vertrags-Tests des Validators — v2-Umschreibung liegt fertig im Scratchpad: `/tmp/claude-1000/-home-hem-gregor-zwanzig/cc3ec65f-e0c1-4b71-ab55-917189e8dfbb/scratchpad/test_issue_1046_v2_rewrite_fuer_1108.py` (in #1110 zurückgestellt, gehört hierher) |
| `tests/tdd/test_issue_1110_compare_mail_v2.py::test_ac9_validate_structure_akzeptiert_v2_html_fehlerfrei` | Fertiger RED-Test, skip-markiert („AC-9 → #1108") — hier entskippen |
| `src/output/renderers/email/compare_html.py` | Quelle der Wahrheit für den v2-Vertrag (auf main, a1c48572): Übersichtstabelle Metriken×Orte, erste Datenzeile „Amtliche Warnungen", Stundentabellen ALLER Orte mit 8 Spalten (Zeit/Temp/Gef./Wind/Böen/Regen/Wolken/UV), alphabetisch, kein Winner/Score |
| `docs/reference/mail_validators.md` | Doku des Compare-Gate-Vertrags — muss mitgezogen werden (in #1110 bewusst NICHT angefasst) |
| `docs/specs/modules/issue_1110_compare_mail_v2.md` §8 | Beschreibt die delegierte Validator-Anforderung (kein „Recommendation"-Pflicht-Check; Übersichtstabelle mit Warn-Zeile als erster Datenzeile; Stundentabellen für alle gelisteten Orte per Namensabgleich; Plausibilität statt String-Presence; Marker bleibt) |

## Verwandte Issues

- #1055 (Validator-Sprachvertrag komplett veraltet — wird hiermit im Compare-Teil erledigt)
- #1038 (fehlende Sektionen/Winner-Box — Winner-Box-Erwartung durch v2 bewusst überholt; prüfen ob nach #1108 schließbar)
- #1107 (Validator config-bewusst — FOLGE-Scope, nicht hier: hier nur der statische v2-Vertrag)

## Gold-Standard-Prinzip (PFLICHT, Memory project_issue_997_bundle_done)

Der neue Vertrag muss beweisen: (1) echte v2-Mail (von `render_compare_html` auf main
erzeugt bzw. echt zugestellte Staging-Mail) → Exit 0; (2) Alt-Struktur (Winner-Box/
matrix-table-Fixture) → Fehler. Kein bloßer String-Presence-Check.

## Risks & Considerations

1. **Sensitive-File-Prompt:** Edit an `.claude/hooks/` löst Harness-Berechtigungsdialog aus —
   der PO weiß das und erwartet ihn in DIESEM Workflow.
2. **Anti-Stale-Mechanik:** email_spec_validator läuft gegen echt zugestellte Staging-Mail
   (`gregor-test@henemm.com`, GZ_TEST_IMAP_* bevorzugt); Staging muss erst den
   #1110-Stand deployen (~5 Min nach Push a1c48572), bevor eine v2-Mail ausgelöst werden kann
   (Compare-Preset-Versand via interner Python-API Port 8001, vgl. Memory
   reference_staging_briefing_trigger_internal_port / Alert-Preview-HowTo).
3. **E2E-Kopplung:** Nach GREEN hier → gemeinsame Staging-E2E für #1108+#1110 → ein
   `/e2e-verify` → Prod-Deploy (PO-'go') → beide Issues schließen.
4. **IMAP-Falle:** Fetch ohne .PEEK markiert \Seen (Memory reference_imap_fetch_implicit_seen).
5. Scope klein halten: NUR Compare-Zweig des Validators; Trip-Briefing-Validator
   (briefing_mail_validator.py) ist NICHT Scope.
