# Mini-Spec: Kommando-Text-Drift (#1002 + #1008)

## Kontext

#882 ("PAUSE im Footer + SKIP", geschlossen) und #884 ("E-Mail/Desktop IST weicht vom SOLL ab",
geschlossen) haben den Kommando-Satz nachträglich geändert. Die Tests aus den älteren Issues
#731 (HTML-Kommando-Block) und #670 (Inbound-Keywords) wurden dabei nicht überall nachgezogen
und dokumentieren jetzt einen veralteten Soll-Zustand. Root Cause ist in beiden Fällen dieselbe
Test/Code-Drift-Klasse — der aktuelle Code ist der korrekte, produktiv gewollte Stand.

## Was ändert sich

- **#1002:** `src/output/renderers/email/html.py:334` — Command-Label
  `("HILFE / HELP", "Alle Kommandos")` → `("HELP", "Alle Kommandos")`.
  Grund: `test_issue_731_unified_commands.py::TestAC1HtmlCommandBlock::test_old_keywords_removed`
  verlangt (bereits korrekt auf #884-Stand), dass `"HILFE"` nicht mehr im HTML-Block steht —
  nur `"HELP"` gehört laut #884-Design in die 3x2-Grid.
- **#1008:** `tests/tdd/test_issue_670_inbound_keywords.py` — zwei veraltete Testerwartungen
  an den #731-Vor-#882/#884-Stand anpassen:
  - `TestAC4StatusHelp::test_help_lists_current_keywords`: `PAUSE`/`SKIP` aus der
    "darf nicht mehr enthalten"-Liste entfernen (seit #882 wieder gültige Befehle,
    stehen bewusst im Hilfetext, `src/services/trip_command_processor.py:947-948`).
  - `TestAC7EmailBlock::test_block_lists_all_keywords`: Keyword-Listen an das #884-Design
    angleichen (Vorbild: `_HTML_NEW_KEYWORDS`/`_HTML_REMOVED_KEYWORDS` in
    `test_issue_731_unified_commands.py`) — `PAUSE/SKIP/STOP/STATUS/CONFIG/HELP` erwarten,
    `HEUTE/MORGEN/JETZT/GEWITTER/WEITER/HILFE` nicht mehr im HTML-Block erwarten.

## Was darf sich nicht ändern

- Der tatsächlich unterstützte Befehlssatz (`_VALID_COMMANDS` in `trip_command_processor.py`)
  bleibt unverändert — nur Anzeigetext (HTML-Label) und Testerwartungen werden korrigiert.
- Keine Änderung an Plaintext-Renderer (`plain.py`) — dessen Tests (AC-2) sind bereits grün.

## Manuelle Test-Schritte

1. `uv run pytest tests/tdd/test_issue_731_unified_commands.py tests/tdd/test_issue_670_inbound_keywords.py -q`
   → alle Tests grün.
2. `uv run pytest tests/tdd/ -q` (Regressions-Sweep) → keine neuen Fehlschläge durch die
   Textänderung.

## Inline-Test (wird während Implementierung geschrieben/angepasst)

- [ ] `test_issue_731_unified_commands.py::TestAC1HtmlCommandBlock::test_old_keywords_removed` grün
- [ ] `test_issue_670_inbound_keywords.py::TestAC4StatusHelp::test_help_lists_current_keywords` grün
- [ ] `test_issue_670_inbound_keywords.py::TestAC7EmailBlock::test_block_lists_all_keywords` grün
