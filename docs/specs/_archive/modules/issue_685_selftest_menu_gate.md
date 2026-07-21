---
entity_id: issue_685_selftest_menu_gate
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [prod-selftest, telegram, bot-menu, deploy-gate, bugfix, tooling]
---

# prod_selftest: Bot-Menü-Check umgebungsunabhängig machen (Issue #685)

## Approval

- [x] Approved (2026-06-09, PO — „go")

## Purpose

**#685 — der Bot-Menü-Deploy-Wächter (#671 AC-4) greift in Produktion nie.**

`prod_selftest.py` wird beim Deploy mit dem **System-`python3`** gestartet
(`python3 .claude/hooks/prod_selftest.py`). Sein `_load_bot_commands()` macht
`from outputs.telegram import BOT_COMMANDS`; das lädt das Paket `outputs/__init__.py`,
welches eager `outputs.sms → app.config → from pydantic import Field` importiert.
`pydantic` ist im System-Python nicht installiert → `ModuleNotFoundError` →
das breite `except Exception: return None` verschluckt den Fehler →
`_check_bot_menu_prod()` liefert `SKIPPED — BOT_COMMANDS nicht ladbar`.

Beleg: `docs/artifacts/issue-671-bot-menu-autoset/prod-selftest.md` zeigt genau
diese Zeile, obwohl der Prod-Token lesbar und das Live-Menü korrekt war. Damit ist
die Schutzfunktion wirkungslos: fällt das Live-Menü künftig aus, schlägt das Gate
trotzdem nicht an.

**Fix:** `BOT_COMMANDS` dependency-frei laden — die Quelldatei `src/outputs/telegram.py`
mit `ast` parsen und die Top-Level-Zuweisung `BOT_COMMANDS = [...]` per
`ast.literal_eval` materialisieren. Kein Paket-Import, keine schweren Deps; der Check
läuft damit in der echten Deploy-Umgebung (System-Python). Single Source of Truth
bleibt `telegram.py`.

Zusätzlich F001 (kosmetisch): Der Fazit-Text in `_render_full_report` koppelt sich an
den tatsächlichen Verdict (FAIL statt fälschlich „PARTIAL", wenn ein Menü-FAIL den
Verdict auf FAIL gesetzt hat).

## Source

- **File (Fix):** `.claude/hooks/prod_selftest.py`
  - `_load_bot_commands()` → AST-`literal_eval` statt Import.
  - `_render_full_report()` → Fazit-Text an Verdict koppeln (F001).
- **File (Test, neu):** `tests/tdd/test_issue_685_selftest_menu_gate.py`
- **Unter Test, nicht verändert:** `src/outputs/telegram.py` (`BOT_COMMANDS`-Literal).

## Estimated Scope

- **LoC:** ~20 Fix + ~90 Test = ~110
- **Files:** 1 berührt (prod_selftest.py) + 1 neu (Test)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/prod_selftest.py` | Hook | Post-Deploy-Gate; enthält den Menü-Check |
| `src/outputs/telegram.py` | Output | `BOT_COMMANDS`-Literal (Single Source) |

## Implementation Details

**`_load_bot_commands()` (dependency-frei):**
- Quelltext von `REPO_DIR/src/outputs/telegram.py` lesen.
- `ast.parse`; über die Top-Level-Knoten iterieren, `ast.Assign`/`ast.AnnAssign`
  finden, dessen Target `BOT_COMMANDS` heißt.
- Wert per `ast.literal_eval` materialisieren → `list[dict[str,str]]`.
- Kein `import` der `outputs`-Pakete; keine Ausführung von Modul-Code.
- Bei JEDEM Fehler (Datei fehlt, kein BOT_COMMANDS, nicht-literal) → `None`
  zurückgeben (weiterhin fail-soft; ein Tool-Defekt darf den Deploy nicht blocken,
  aber er darf auch keinen falschen PASS vortäuschen → SKIPPED).

**F001 — `_render_full_report` Fazit:**
- Der `else`-Zweig beschriftet das Fazit anhand des übergebenen `verdict`: bei
  `FAIL` ein FAIL-Text (Menü-/AC-Regression, Issue NICHT schließen), bei `PARTIAL`
  der bisherige PARTIAL-Text.

**Mock-frei nach Projekt-Standard:**
- AC-1 reproduziert die echte Deploy-Bedingung: `_load_bot_commands()` wird in einem
  **Subprozess mit System-`python3` ohne pydantic** ausgeführt (das prod_selftest-Modul
  via `spec_from_file_location` geladen) und muss die 7 echten Befehle liefern — nicht None.
- AC-2/AC-3: echter lokaler `http.server`-Socket beantwortet `getMyCommands`;
  `check_bot_menu` wird gegen diesen Socket gefahren. Keine Mocks.

## Expected Behavior

- **Input:** Post-Deploy-Lauf unter System-Python; Live-Bot-Menü via getMyCommands.
- **Output:** Menü-Check-Status PASS/FAIL/SKIPPED + Verdict; Bericht-Fazit passend.
- **Side effects:** keine (reiner Lese-/Prüf-Pfad).

## Acceptance Criteria

- **AC-1:** Given die echte Deploy-Umgebung (System-`python3`, in der `pydantic`
  NICHT importierbar ist) /
  When `_load_bot_commands()` in einem Subprozess mit genau diesem Interpreter
  aufgerufen wird /
  Then liefert es die vollständige `BOT_COMMANDS`-Liste (7 Befehle, command-Namen
  identisch zur Quelle in `telegram.py`) — **nicht** `None` und ohne
  `ModuleNotFoundError`, weil es per AST aus der Quelldatei liest statt zu importieren.

- **AC-2:** Given ein lokaler Socket, der bei `getMyCommands` exakt die
  `BOT_COMMANDS` zurückgibt /
  When `check_bot_menu(token, BOT_COMMANDS, api_base=<socket>)` läuft, wobei
  `BOT_COMMANDS` über das gefixte `_load_bot_commands()` bezogen wurde /
  Then ist das Ergebnis `status == "PASS"` (nicht `SKIPPED`) — der Wächter greift,
  auch wenn alle übrigen AC-Findings SKIPPED sind.

- **AC-3:** Given ein Live-Menü, das von `BOT_COMMANDS` abweicht (alter
  `briefing/wetter`-Stand) /
  When der Menü-Check im Selftest dies feststellt und den Verdict auf `FAIL` setzt /
  Then ist der Menü-Check-Status `FAIL` UND der von `_render_full_report` erzeugte
  Fazit-Text beschreibt einen FAIL (nicht „PARTIAL") — F001 behoben.

- **AC-4:** Given die Quelldatei ist nicht parsebar bzw. enthält kein
  literal-auswertbares `BOT_COMMANDS` /
  When `_load_bot_commands()` aufgerufen wird /
  Then gibt es `None` zurück (fail-soft, kein Crash) und der Menü-Check meldet
  `SKIPPED` statt einen falschen PASS vorzutäuschen.

## Known Limitations

- Wird `BOT_COMMANDS` jemals dynamisch (nicht-literal) zusammengesetzt, scheitert
  `literal_eval` → sauberes `None`/SKIPPED. Aktuell ist es ein reines Literal.

## Changelog

- 2026-06-09: Initial spec (Issue #685 — Menü-Wächter umgebungsunabhängig + F001).
