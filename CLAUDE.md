# CLAUDE.md - Gregor Zwanzig

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Channels:** E-Mail (MVP), spaeter SMS/Push

## Workflow

Dieses Projekt nutzt den **OpenSpec 4-Phasen-Workflow**:

| Phase | Command | Purpose |
|-------|---------|---------|
| 1 | `/analyse` | Request verstehen, Codebase recherchieren |
| 2 | `/write-spec` | Spezifikation erstellen |
| 3 | User: "approved" | Spec freigeben |
| 4 | `/implement` | Implementieren nach Spec |
| 5 | `/validate` | Validieren vor Commit |

**Hooks erzwingen diesen Workflow!** Edit/Write auf geschuetzte Dateien ist blockiert.

## Architektur

```
CLI -> Config -> Provider-Adapter -> Normalizer -> Risk Engine -> Formatter -> Channel
```

Siehe: `docs/features/architecture.md`

## Wichtige Referenzen

| Dokument | Beschreibung |
|----------|--------------|
| `docs/reference/api_contract.md` | Single Source of Truth: DTOs & Datenformate |
| `docs/reference/decision_matrix.md` | Provider-Auswahl (MET vs MOSMIX) |
| `docs/features/scope.md` | Projektvision & Ziele |

## CLI

```bash
python -m src.app.cli --report evening --channel email
python -m src.app.cli --report morning --channel none --dry-run
python -m src.app.cli --debug verbose
```

Konfigurations-Prioritaet: CLI > ENV > config.ini

## Tests

```bash
uv run pytest
```

## KEINE MOCKED TESTS! (KRITISCH!)

**Mocked Tests sind VERBOTEN in diesem Projekt!**

- Mocked Tests beweisen NICHTS - sie testen nicht das echte Verhalten
- **E-Mail-Tests:** Echte E-Mail via Gmail SMTP senden, via IMAP abrufen, Inhalt pruefen
- **API-Tests:** Echte API-Calls machen (Geosphere, etc.)
- Siehe `tests/tdd/test_html_email.py::TestRealGmailE2E` als Referenz

**NIEMALS `Mock()`, `patch()`, oder `MagicMock` fuer E-Mail/API Tests verwenden!**

## ECHTE E2E TESTS (NOCH KRITISCHER!)

**ICH (Claude) starte und restarte den Server - NICHT der User!**

**E2E Test Workflow:**

1. **ICH stoppe den alten Server** (falls laufend)
2. **ICH starte den Server neu** mit aktuellem Code
3. **ICH fuehre Browser-Test aus** mit Playwright
4. **ICH pruefe Screenshot** visuell
5. **ICH teste E-Mail** via SMTP senden + IMAP pruefen

**Benutze den E2E Hook:**
```bash
# Browser Test
uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --action "compare"

# Email Test
uv run python3 .claude/hooks/e2e_browser_test.py email --check "Feature" --send-from-ui
```

**VERBOTEN:**
- Python-Funktionen direkt aufrufen und als "E2E Test" bezeichnen
- User bitten den Server zu starten
- "E2E Test erfolgreich" sagen ohne gruenen Hook-Output

## E-MAIL SPEC VALIDATOR (ZWINGEND!)

**PFLICHT vor "E2E Test bestanden" bei E-Mail-Features:**

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Prueft: Struktur, Location-Anzahl, Plausibilitaet, Format, Vollstaendigkeit.

**NUR bei Exit 0 darfst du "E2E Test bestanden" sagen!**

Einfache String-Checks beweisen NICHTS - sie pruefen nicht ob Daten SINNVOLL sind!

## Specs

Alle Module benoetigen Specs vor Implementierung:
- Template: `docs/specs/_template.md`
- Location: `docs/specs/modules/[entity].md`

### Implementierte Module
- `cli` - Einstiegspunkt
- `smtp_mailer` - E-Mail-Versand
- `debug_buffer` - Debug-Sammlung

### Geplante Module (draft)
- `provider_met` - MET Norway Adapter
- `provider_mosmix` - DWD MOSMIX Adapter
- `risk_engine` - Risiko-Bewertung
- `report_formatter` - Report-Generierung

## Dokumentation

- `docs/specs/` - Entity-Spezifikationen
- `docs/features/` - Feature-Dokumentation
- `docs/reference/` - Technische Referenz
- `docs/project/` - Projekt-Management (Backlog)

## Pre-Test Validierung (PFLICHT!)

**BEVOR du den User zum Testen aufforderst, MUSST du validieren!**

```bash
python3 .claude/validate.py
```

### Was wird geprueft:
1. **Syntax-Check** auf alle geaenderten Python-Dateien
2. **Import-Check** - Module lassen sich importieren
3. **Server-Startup** - Web-UI startet fehlerfrei

### Workflow:
1. Code schreiben/aendern
2. `python3 .claude/validate.py` ausfuehren
3. Alle Checks gruen? -> User zum Testen auffordern
4. Checks rot? -> Fehler beheben, erneut validieren

### Nach erfolgreichem User-Test:
```bash
python3 .claude/validate.py --clear
```

**NIEMALS "teste es" oder "pruefe" sagen ohne vorherige Validierung!**

## NiceGUI Safari-Kompatibilitaet (KRITISCH!)

**Safari ist STRENGER als Chrome/Firefox!** NiceGUI's Python→JavaScript-Uebersetzung hat **Closure-Binding-Probleme in Safari**.

### Factory Pattern ist PFLICHT

**ALLE `ui.button(on_click=X)` MUESSEN Factory Pattern verwenden:**

Direkte Closure-Referenzen → Safari: Button reagiert nicht (keine Fehlermeldung)
Factory Pattern → Safari bindet Callable korrekt

**Naming:** `make_<action>_handler()` returns `do_<action>()`

### Test-Reihenfolge

1. Safari (strengste) - funktioniert Safari → funktioniert ueberall
2. Firefox
3. Chrome (permissivste)

**Nach jeder UI-Aenderung:** Safari Hard Reload (Cmd+Shift+R)

### Referenz

**Details & Templates:** `docs/reference/nicegui_best_practices.md`

Fixed Bugs: `docs/specs/bugfix/locations_add_button_fix.md`, `safari_subscriptions_fix.md`

---

Generated by OpenSpec Framework on 2025-12-27
