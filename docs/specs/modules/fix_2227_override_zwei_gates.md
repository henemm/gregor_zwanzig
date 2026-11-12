---
entity_id: fix_2227_override_zwei_gates
type: module
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
tags: [gate, hooks, testlauf, override, sicherheit]
---

# Override-Ausgang des Testlauf-Gates streichen (#2227)

## Approval

- [ ] Approved

## Purpose

Das Freigabe-Wort `override` (im Plugin an den Workflow-Namen gebunden, nicht an eine Sperre) öffnet heute auch die Projekt-Sperre gegen breite Testläufe (`broad_test_run_gate.py`). Genau so lief am 2026-08-10 (#1660 B) ein pytest ohne Socket-Sperre, der Weg des Produktiv-Versands aus #1477. Seit #1755 gibt es den sicheren Offline-Volllauf; der Override-Ausgang wird deshalb ersatzlos gestrichen (Gate-Audit-Linie #1197 „Fang-Nachweis oder raus").

## Source

- **File:** `.claude/hooks/broad_test_run_gate.py`
- **Identifier:** `_has_valid_override`, `_OVERRIDE_TTL`, `_check_raw`, `main`, `_block`, Modul-Docstring (Ausgang 4)

> Schicht: Projekt-Hook (`.claude/hooks/`) und Doku. Kein Frontend, keine Go-API, kein Python-Core. Kein Trip/Vergleich-Pendant, keine Nutzerdaten, keine Kanalinhalte betroffen.

## Scope

- **Drin:** Override-Ausgang des Testlauf-Gates (`broad_test_run_gate.py`) streichen, neuer Verhaltenstest, Doku `gates_und_ratschen.md` bereinigen, Kreuzbindungs-Anforderung als Kommentar in #2125.
- **Nicht drin:** Prod-Versand-Wächter (`prod_send_gate.py`) und seine Override-Logik (#2125), Plugin-Erzeuger und Plugin-Verbraucher des Tokens, vorbestehende Gate-Grenzen (#2856).

## Estimated Scope

- **LoC:** Gate etwa -40, Test etwa +90, Doku etwa ±10
- **Files:** 4 (Gate, neuer Test, `gates_und_ratschen.md`, diese Spec)
- **Effort:** low (Risiko mittel: Gate-Code, Adversary mindestens 2 Runden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/hook_utils.py` (Shim auf Plugin) | Modul | `find_project_root`, `get_active_workflow_name`, `get_tool_input`; bleibt, wird nur nicht mehr für das Token genutzt |
| `.claude/user_override_token.json` (Plugin-Format v2) | Datei | wird vom Testlauf-Gate nicht mehr gelesen; Plugin-Verbraucher unverändert |
| `.claude/hooks/prod_send_gate.py` | Hook | bleibt unverändert (siehe Abgrenzung) |
| #2125 | Issue | erhält die Kreuzbindungs-Anforderung als Kommentar |

## Implementation Details

Entfernen in `.claude/hooks/broad_test_run_gate.py` (Zeilen gegen den heutigen Stand geprüft):

- Modul-Docstring „4. **Menschliche Freigabe** …" (Z. 51-54)
- `_OVERRIDE_TTL = timedelta(hours=1)` (Z. 84)
- `_has_valid_override(workflow_name)` samt Docstring (Z. 123-148) und `_active_workflow_name()` (Z. 116-120), sofern danach ungenutzt
- Aufruf in `_check_raw`: `if _has_valid_override(_active_workflow_name()): sys.exit(0)` (Z. 415-416)
- Aufruf in `main`: `if _has_valid_override(_active_workflow_name()): continue` (Z. 446-447)
- Hinweiszeile in `_block`: `"  4. Freigabe des Users: er tippt woertlich 'override' im Chat."` (Z. 395)
- danach ungenutzte Imports (`datetime`, `timedelta`, `timezone`; `json` nur, wenn sonst ungenutzt) und ggf. `_project_root`

Unverändert bleiben: Offline-Volllauf-Freigabe (`_offline_form_is_safe`, `_OFFLINE_CALLS`), benannte Testdateien, `_SAFE_FLAGS` (`--collect-only` usw.), Block-Logik und Exit-Codes.

Doku `docs/reference/gates_und_ratschen.md`:

- Z. 216 (Test-Politik-Absatz): Aufzählung „Erlaubt" ohne „Einmal-Freigabe … `override`"
- Z. 241-242 (Abschnitt „Breiter Testlauf gesperrt"): „Einmal-Freigabe, die nur der User …" streichen; der Satz „Prüfdatum 2026-11-01" (abgelaufen) entfällt, stattdessen kurzer Hinweis: „`override` wirkt auf dieses Gate nicht mehr (#2227)"
- Prüfdatum-Tabellenzeile „Breiter Testlauf gesperrt | 2026-11-01" (Z. 741): bereinigen bzw. neu datieren (+90 Tage) mit Verweis auf den neuen Fang-Nachweis
- Z. 699 (Prod-Send-Gate, Override-Spalte) bleibt unverändert

Abgrenzung Prod-Versand-Wächter (#2125): `prod_send_gate.py` liest dasselbe Token, verbraucht es aber einmalig und wirkt im Worktree heute gar nicht (#2125, offen). Dieser Fix ändert das Prod-Send-Gate und seine Tests nicht. Die Kreuzbindung (ein „override" für das LoC-Limit gibt auch einen Prod-Versand frei) wird als Anforderung in #2125 vermerkt: wer dort den Override wirksam macht, muss ihn an das Prod-Send-Gate binden. Nicht still mitgelöst.

Verworfen: sperrenspezifisches Token im Plugin (Querschnittsumbau in fremdem Repo für einen nicht mehr benötigten Ausgang); eigenes Stichwort nur für das Testlauf-Gate (neuer Mechanismus ohne Bedarf, ein breiter Lauf mit Netz ist genau der #1477-Weg).

## Expected Behavior

- **Input:** Bash-Hook-Payload (JSON mit `tool_input.command`), optional mit gültigem Override-Token im Projekt-Root.
- **Output:** Breiter pytest-Lauf (ohne benannte Testdateien, ohne `--collect-only`, nicht die wörtliche Offline-Zeile) endet immer mit Exit 2, mit oder ohne Token. Benannte Dateien, `--collect-only` und die Offline-Zeile enden mit Exit 0.
- **Side effects:** keine; Token-Datei wird weder gelesen noch verändert.

## Acceptance Criteria

- **AC-1:** Given ein gültiges, frisches Override-Token für den aktiven Workflow liegt im Projekt-Root / When der Hook einen breiten Lauf `uv run pytest` bzw. `uv run pytest tests/` (normaler Pfad, zerlegbar) erhält / Then endet er mit Exit 2 und blockt, das Token wirkt nicht mehr.
  - Test: Hook als Subprozess mit JSON-Payload, Token im v2-Format (`tokens.<workflow>.created` = jetzt) unter temporärem Projekt-Root; Exit 2. Vor dem Fix Exit 0 (RED).

- **AC-2:** Given dasselbe gültige Override-Token / When der Hook den breiten Lauf im Roh-Scan-Pfad erhält, z. B. `sh -c "uv run pytest"` / Then endet er mit Exit 2 und blockt.
  - Test: Subprozess-Aufruf wie AC-1 mit Kommando `sh -c "uv run pytest"`; Exit 2.

- **AC-3:** Given die wörtliche Offline-Volllauf-Zeile (`OFFLINE_CALL`, auch mit ` > datei 2>&1`) oder ein Aufruf mit benannten Testdateien (`uv run pytest tests/tdd/x.py`) oder `--collect-only` / When der Hook sie erhält, jeweils mit und ohne gültiges Token / Then endet er mit Exit 0, die erlaubten Wege bleiben unverändert.
  - Test: Subprozess, parametrisiert über Kommando x (Token vorhanden, kein Token); Exit 0.

- **AC-4:** Given ein blockierter breiter Lauf / When der Hook den Hinweistext ausgibt / Then nennt dieser keinen Freigabe- oder `override`-Ausgang mehr, sondern nur die drei erlaubten Wege (Dateien benennen, `--collect-only`, Offline-Volllauf-Zeile).
  - Test: stderr des blockierten Laufs enthält weder `override` noch „Freigabe des Users", enthält aber die Offline-Zeile.

- **AC-5:** Given der Fix ist umgesetzt / When `prod_send_gate.py` und seine bestehenden Tests (`tests/tdd/test_issue_1148_prod_send_gate.py`) laufen / Then sind Hook und Tests unverändert und grün; die Kreuzbindungs-Anforderung steht als Kommentar in #2125.
  - Test: bestehende Prod-Send-Tests grün (benannte Datei); `git diff` zeigt keine Änderung an `prod_send_gate.py`; Issue-Kommentar in #2125 vorhanden.

- **AC-6:** Given die Doku `docs/reference/gates_und_ratschen.md` / When man den Test-Politik-Absatz und den Abschnitt „Breiter Testlauf gesperrt" liest / Then ist die Einmal-Freigabe für breite Läufe gestrichen und das abgelaufene Prüfdatum 2026-11-01 für diesen Ausgang bereinigt.
  - Test: `# doc-compliance-test`: Doku nennt unter „Erlaubt" keine Einmal-Freigabe mehr; Prüfdatum-Zeile bereinigt. Nur ergänzend, kein Verhaltensnachweis.

## Definition of Done

- AC-1 bis AC-5 durch den neuen Test und die bestehenden Gate-Tests grün belegt, AC-6 per Doku-Prüfung.
- Mutationsprobe aus dem Test Plan: jede der drei Rück-Mutationen macht mindestens einen Test rot.
- Bestehende Gate-Tests und Prod-Send-Tests grün; Kommentar in #2125 gesetzt.

## Test Plan

- Datei `tests/tdd/test_broad_test_run_gate_ignores_override.py` (neu), Muster der bestehenden Gate-Tests: echter Hook per `subprocess.run([sys.executable, HOOK])`, JSON-Payload auf stdin, kein Mock.
- Token-Datei im v2-Format unter temporärem Projekt-Root; Projekt-Root über `CLAUDE_PROJECT_DIR` lenken (so tun es `test_broad_test_run_gate_offline_form.py`), Workflow-Name über die Mechanik von `hook_utils.get_active_workflow_name` (in RED klären, z. B. Workflow-State im Temp-Root).
- Wichtig: der Test muss belegen, dass das Token tatsächlich gelesen würde (Kontrollfall: gleiche Anordnung vor dem Fix ergibt Exit 0), sonst wäre Exit 2 ein Zufallstreffer.
- **Mutationsprobe (beide Pfade, String-Ersetzung mit externer Sicherung, nie `git checkout/stash/reset`):**
  1. Aufruf `if _has_valid_override(_active_workflow_name()): continue` in `main` wieder einsetzen: AC-1 muss rot werden.
  2. Aufruf `if _has_valid_override(_active_workflow_name()): sys.exit(0)` in `_check_raw` wieder einsetzen: AC-2 muss rot werden.
  3. Hinweiszeile „4. Freigabe des Users" wieder einsetzen: AC-4 muss rot werden.
- Bestehende Tests müssen grün bleiben: `test_broad_test_run_gate_offline_form.py`, `test_broad_test_run_gate_pytest_word_position.py`, `test_pytest_collection_and_timeout_safety.py`.

## Known Limitations

- Das Token selbst wird weiter vom Plugin erzeugt und von dessen `edit_gate`/`bash_gate` sowie von `prod_send_gate.py` gelesen; die Kreuzbindung dort ist Gegenstand von #2125, nicht dieses Fixes.
- Vorbestehende Grenzen des Gates (#2856: unbekannte Wert-Optionen, `python -mpytest`) bleiben.
- Wer künftig einen breiten Lauf mit Netz braucht, hat keinen Ausgang; gewollt (#1477).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rückbau eines ungenutzten, ungetesteten Ausgangs innerhalb einer bestehenden Gate-Regel; macht das Gate nur strenger, keine neue Entscheidungsfläche.

## Changelog

- 2026-11-12: Initial spec created (#2227)
- 2026-11-12: Abschnitte Scope, Definition of Done, Test Plan ergänzt (Spec-Gate)
