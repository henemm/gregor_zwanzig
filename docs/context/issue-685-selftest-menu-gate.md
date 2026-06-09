# Context: Issue #685 — prod_selftest Bot-Menü-Check greift nicht

## Request Summary
Der Post-Deploy-Bot-Menü-Check (`check_bot_menu`, AC-4 aus #671) meldet in
Produktion immer `SKIPPED — BOT_COMMANDS nicht ladbar` und schützt damit nie.
Ursache ist NICHT der ursprünglich vermutete Early-Return, sondern ein
fehlschlagender Import von `BOT_COMMANDS` in der System-Python-Umgebung.

## Verifizierter Root-Cause (Reproduktion)
- Der Deploy ruft den Selftest als `python3 .claude/hooks/prod_selftest.py` auf
  → **System-`python3`**, nicht die uv-venv.
- `_load_bot_commands()` macht `from outputs.telegram import BOT_COMMANDS`.
  Das lädt das Paket `outputs/__init__.py`, das eager `outputs.sms` →
  `app.config` → `from pydantic import Field` importiert.
- `pydantic` ist im System-Python **nicht installiert** →
  `ModuleNotFoundError: No module named 'pydantic'`.
- Das breite `except Exception: return None` in `_load_bot_commands` verschluckt
  den Fehler → `_check_bot_menu_prod` liefert `SKIPPED — BOT_COMMANDS nicht ladbar`.
- Beleg: `docs/artifacts/issue-671-bot-menu-autoset/prod-selftest.md` → Bot-Menü-Check
  `Status: SKIPPED — BOT_COMMANDS nicht ladbar` (obwohl Prod-Token lesbar + Menü live korrekt).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/prod_selftest.py` | `_load_bot_commands` (395), `_check_bot_menu_prod` (373), `check_bot_menu` (244), `run_selftest` (300), `_render_full_report` (197) |
| `src/outputs/telegram.py` | `BOT_COMMANDS` = reines Literal (Zeile 14), Single Source |
| `src/outputs/__init__.py` | eager-importiert sms→app.config→pydantic (die Bruchstelle) |

## Existing Patterns
- Andere Hooks laden Code dependency-frei via `importlib.util.spec_from_file_location`
  bzw. lesen Literale ohne Paket-Import (siehe `_e2e_paths.py`-Shims, Tests
  laden `prod_selftest.py` per spec_from_file_location).
- `ast.literal_eval` auf eine Top-Level-Zuweisung ist der saubere Weg, ein reines
  Daten-Literal ohne Code-Ausführung/Imports zu extrahieren.

## Lösungsskizze
`_load_bot_commands()` soll `BOT_COMMANDS` **ohne Import** lesen:
1. Quelltext `src/outputs/telegram.py` einlesen.
2. Mit `ast.parse` die Top-Level-Zuweisung `BOT_COMMANDS = [...]` finden.
3. Wert per `ast.literal_eval` materialisieren (reine Liste aus dict[str,str]).
4. Bei jedem Fehler weiterhin fail-soft → SKIPPED (kein Deploy-Block durch Tool-Defekt).

Damit läuft der Check in der echten Deploy-Umgebung (System-Python) und greift:
FAIL bei Live-Menü-Abweichung, PASS bei Übereinstimmung — auch wenn sonst alle
AC-Findings SKIPPED sind (der häufige backend-only-Fall).

**F001 (kosmetisch):** Der `else`-Zweig in `_render_full_report` (Zeile 234) beschriftet
das Fazit hart als „PARTIAL", auch wenn der Verdict durch einen Menü-FAIL `FAIL` ist.
Text an den tatsächlichen Verdict koppeln.

## Risks & Considerations
- Single-Source-of-Truth: BOT_COMMANDS bleibt einzig in telegram.py; der Hook liest
  es daraus (kein Duplikat).
- AST-Parsing bricht, falls BOT_COMMANDS je nicht-literal wird (z. B. dynamisch
  zusammengesetzt) — dann sauberes SKIPPED statt Crash. Aktuell reines Literal.
- Mock-frei testbar: echtes prod_selftest-Modul via spec_from_file_location laden,
  echte telegram.py-Quelle parsen, echter lokaler http.server-Socket für getMyCommands.
- Scope klein: nur `.claude/hooks/prod_selftest.py`. Tooling-only → kein Prod-Deploy nötig
  (greift ab origin/main beim nächsten Deploy).
