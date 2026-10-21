# No Mocked Tests Standard

**Domain:** Test-Politik Gregor Zwanzig. Maßgeblich ist `CLAUDE.md` → „Test-Politik: Zwei
Schichten"; Durchsetzung und Ausnahme-Syntax: `docs/reference/gates_und_ratschen.md`. Dieses
Dokument fasst nur zusammen — bei Abweichung gilt CLAUDE.md.

## Verboten: Mock-Theater

- `Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme zurückspiegeln, beweisen nichts.
- Dateiinhalt-Checks (`assert 'xyz' in file.read_text()`) sind kein Verhaltensnachweis
  (Ausnahme: `# doc-compliance-test`).
- Ein Test, der nur prüft, dass ein String im Rückgabewert vorkommt, ist kein E2E-Nachweis.

## Zwei Schichten

| Schicht | Was | Wann | Regel bei Rot |
|---|---|---|---|
| **Kern (deterministisch)** | ohne Netz/Live-Dienste/echte Postfächer; echte **aufgezeichnete** API-/Mail-Daten als versionierte Fixtures erwünscht (`GZ_TEST_FIXTURE_DIR`, `scripts/refresh-openmeteo-fixtures.sh`) | jeder Testlauf; Commit-Gate | 100 % grün: sofort fixen oder löschen |
| **Live-E2E** | echte API-Calls, echte Staging-Mails via IMAP (Stalwart, `gregor-test@henemm.com`, nie Gmail), Playwright gegen Staging (Marker `live`/`email`/`staging`) | nur `/e2e-verify` bzw. Deploy | Flake → Retry; erst reproduzierbares Scheitern ist ein Befund |

Bug-Nachweis: mindestens ein Test reproduziert den Bug aus Nutzersicht (rot vor Fix, grün
nach Fix).

## Ausführen

- `uv run pytest` **nur mit benannten Testdateien** — der breite Lauf ist gesperrt (#1477,
  `broad_test_run_gate.py`).
- Ein Test löst seinen Prüfling relativ zur eigenen Testdatei auf, nie über den festen
  Hauptrepo-Pfad.
- **Nie** den lokalen Live-Server stoppen/neu starten, um zu testen — Verifikation läuft
  nach dem Push gegen Staging (`/e2e-verify`, #339).

## E2E-Nachweis vor „E2E bestanden"

Pfadrichtiger Mail-Validator gegen echt zugestellte Staging-Mail (Tabelle in `CLAUDE.md` →
„Mail-Validatoren & Renderer-Gate", Details `docs/reference/mail_validators.md`); nur bei
Exit 0. UI: `staging-validator`-Agent bzw. `/e2e-verify` Schritt 3a.
