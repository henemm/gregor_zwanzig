# Context: fix-1150-compare-validator-hourly

## Request Summary
`email_spec_validator.py` verlangt für **jeden** gelisteten Ort zwingend eine Stundentabelle.
Bei einer Compare-Mail mit bewusst abgeschaltetem Stundenverlauf (`hourly_enabled=false`, Issue
#1107) meldet der Validator sie deshalb fälschlich als kaputt. Der Validator soll den bereits
existierenden Marker-Header `X-GZ-Compare-Hourly-Enabled` lesen und die Stundentabellen-Pflicht
bei `false` überspringen — ohne die Prüfung bei `true` aufzuweichen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/email_spec_validator.py` | **Einzige Code-Änderung.** Fetch-Refactor (`_fetch_latest_message`/`_extract_html_body`), `validate_structure(body, hourly_enabled=True)`, `run_validation()` liest Header |
| `docs/specs/modules/issue_1107_compare_hourly_toggle.md` | Enthält den fertigen Code-Entwurf (Zeilen 286–384) — 1:1 als Ausgangspunkt |
| `src/output/channels/email.py:151-191` | Setzt bereits den Header `X-GZ-Compare-Hourly-Enabled: true\|false` (Feature-Seite fertig) |
| `tests/tdd/test_issue_972_974_975_tooling.py:128` | **Regressionsschutz:** `fetch_latest_email()` muss `str` bleiben (öffentlicher Vertrag) |
| `tests/tdd/test_issue_1107_compare_sections.py:370-385` | Belegt, dass der Header korrekt gesetzt wird (bestehende grüne Tests) |

## Existing Patterns
- **Optionaler MIME-Header lesen:** `briefing_mail_validator.py::validate_message()` liest
  `msg["X-GZ-Mail-Type"]` — Vorbild, wie ein Hook-Validator Header statt nur Body prüft.
- **Sicherer Default:** `msg.get(header) != "false"` → `True` bei fehlendem Header (Alt-Mails)
  bleibt das strenge Bestandsverhalten (Präzedenz: alle Bestandsaufrufer mit Default `True`).
- **Cross-Location-Konsistenz-Block** (Bestand Zeile 245–292) wandert komplett unter
  `if hourly_enabled:` — bei `False` entfällt Tabellen-Vorhandensein, Spalten-Vertrag UND
  Cross-Location-Konsistenz.

## Dependencies
- **Upstream:** `app.config.Settings` (IMAP-Creds, Test-Postfach priorisiert), Stalwart-Test-
  Postfach `gregor-test@henemm.com`. Header wird von `email.py` gesetzt (bereits live).
- **Downstream:** Wird als Hook/CLI vor „E2E bestanden" für Compare-Mails aufgerufen
  (`X-GZ-Mail-Type: compare`). Kein Code importiert `validate_structure` außer Tests.

## Existing Specs
- `docs/specs/modules/issue_1107_compare_hourly_toggle.md` — Mutter-Spec, Validator-Teil ausgelagert.

## Risks & Considerations
- **Gate-Erosion (Kernrisiko):** Der Skip darf NUR bei echtem `X-GZ-Compare-Hourly-Enabled: false`
  greifen. Gold-Standard-Negativfall: Header `true` + tatsächlich fehlende Stundentabelle MUSS
  weiterhin als Fehler erkannt werden.
- **Prozess:** Datei liegt unter `.claude/hooks/*` → `edit_gate` blockt normal. Braucht
  **USER-Override-Token** ([[feedback_validator_changes_own_workflow]]). Genau dafür wurde #1150
  von #1107 abgespalten — Validator-Änderung im eigenen Workflow, nicht im geprüften.
- **Öffentlicher Vertrag:** `fetch_latest_email() -> str` unverändert lassen (Test #972).
- **`validate_hourly_table()` bleibt unverändert** — liefert bei fehlenden Tabellen ohnehin keine
  Fehler (`if table is None: continue`), verifiziert per AC-Test statt Code-Annahme.
- **Nachweis-Pflicht:** zwei echte Versände (`false`/`true`) gegen Stalwart-Test-Postfach, kein Mock.
