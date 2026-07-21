---
entity_id: issue_1150_compare_validator_hourly
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [validator, compare, hourly-toggle, hooks, issue-1150, issue-1107]
---

# Compare-Validator: Stundentabellen-Pflicht abhängig von `X-GZ-Compare-Hourly-Enabled`

## Approval

- [ ] Approved

## Purpose

`email_spec_validator.py` prüft reale Compare-Mails vor jedem "E2E bestanden" gegen den v2-Mail-Vertrag. Der Validator verlangt bisher für jeden gelisteten Ort zwingend eine Stundentabelle — auch dann, wenn der Nutzer den Stundenverlauf über den (bereits live ausgelieferten) Toggle aus Issue #1107 bewusst abgeschaltet hat (`hourly_enabled=false`). Dadurch meldet der Validator eine korrekte Mail fälschlich als Spec-Verstoß. Diese Änderung lässt den Validator den bereits von `src/output/channels/email.py` gesetzten Marker-Header `X-GZ-Compare-Hourly-Enabled` lesen und überspringt die Stundentabellen-Pflicht ausschließlich bei explizitem `false` — bei `true` oder fehlendem Header bleibt die Prüfung unverändert streng.

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `fetch_latest_email`, `validate_structure`, `run_validation` (Refactor + neue Helfer `_fetch_latest_message`, `_extract_html_body`)

> **Schicht-Hinweis:** Dies ist eine reine Tooling-/Hook-Änderung (`.claude/hooks/`), kein `src/`-Code. Sie betrifft weder Frontend, Go-API noch Python-Core-Backend — die Feature-Seite (Header setzen) ist bereits über Issue #1107 in `src/output/channels/email.py:151-191` live. Deshalb läuft diese Änderung bewusst im eigenen Workflow (`fix-1150-compare-validator-hourly`), getrennt vom geprüften Feature-Workflow — Validator-Änderungen dürfen niemals im selben Workflow wie der Code stattfinden, den sie prüfen sollen.

## Estimated Scope

- **LoC:** ~50 (Refactor + neuer Parameter + Header-Lesen, keine neue Datei)
- **Files:** 1 (`.claude/hooks/email_spec_validator.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/channels/email.py:151-191` | module | Setzt bereits den Marker-Header `X-GZ-Compare-Hourly-Enabled: true\|false` (Feature-Seite fertig, Issue #1107) |
| `app.config.Settings` | module | IMAP-Zugangsdaten, Test-Postfach (`test_imap_user`/`test_imap_pass`) priorisiert vor Produktiv-Postfach (Issue #972) |
| Stalwart-Test-Postfach `gregor-test@henemm.com` | infra | Reale Ziel-Mailbox für alle Nachweise (kein Mock) |
| `briefing_mail_validator.py::validate_message` | pattern | Vorbild für "optionalen MIME-Header lesen" (`msg["X-GZ-Mail-Type"]`) |
| `tests/tdd/test_issue_972_974_975_tooling.py::test_email_spec_validator_prefers_test_creds` | test | Regressionsschutz: `fetch_latest_email()` muss weiterhin `str` liefern |
| `tests/tdd/test_issue_1107_compare_sections.py:370-385` | test | Belegt bereits, dass `email.py` den Header korrekt setzt (grün, unverändert) |

## Implementation Details

**1. Fetch-Refactor** — bisher liefert `fetch_latest_email()` nur den Body-String, `run_validation()` liest keine Header. Neu: gemeinsamer IMAP-Fetch als geparstes `email.message.Message`, aus dem sowohl Body als auch Header derselben IMAP-Runde entnommen werden. Der öffentliche Vertrag `fetch_latest_email() -> str` bleibt exakt erhalten (delegiert nur noch intern):

```python
def _fetch_latest_message():
    """Gemeinsamer IMAP-Fetch: laedt die neueste Mail als geparstes
    email.message.Message (Body UND Header aus derselben IMAP-Runde)."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from app.config import Settings
    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")
    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    imap.select('INBOX')
    _, data = imap.search(None, 'ALL')
    all_ids = data[0].split()
    if not all_ids:
        raise ValueError("Keine E-Mails gefunden")
    _, msg_data = imap.fetch(all_ids[-1], '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])
    imap.close()
    imap.logout()
    return msg


def _extract_html_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            return part.get_payload(decode=True).decode('utf-8')
    return ''


def fetch_latest_email() -> str:
    """Fetch latest sent email HTML body. Unveraenderter oeffentlicher Vertrag."""
    return _extract_html_body(_fetch_latest_message())
```

**2. `validate_structure()` neuer optionaler Parameter** — Default `True` erhält das strikte Bestandsverhalten für alle bestehenden Aufrufer/Tests (die weiterhin einparametrig aufrufen). Bei `hourly_enabled=False` entfällt der gesamte bestehende `for name in locations:`-Block (Bestand Zeile 245–292: Tabellen-Vorhandensein, Mindestspalten-Regel, Spalten-Teilmengen-Vertrag, Cross-Location-Konsistenz):

```python
def validate_structure(body: str, hourly_enabled: bool = True) -> List[str]:
    errors: List[str] = []
    rows = extract_table_rows(body)
    # ... Uebersichtstabellen-Checks UNVERAENDERT ...

    locations = extract_locations(body)
    if rows and not locations:
        errors.append("STRUKTUR: Keine Orte in der Uebersichtstabelle-Kopfzeile gefunden")

    # Issue #1107/#1150: bei abgeschalteter Stundenverlauf-Sektion entfaellt
    # die gesamte Pflicht-Pruefung -- eine bewusst abgeschaltete Sektion darf
    # weder Tabellen enthalten noch ist ihr Fehlen ein Fehler.
    if hourly_enabled:
        occurrence_counts: dict = {}
        reference_cols: list | None = None
        reference_name: str | None = None
        for name in locations:
            # ... UNVERAENDERTER Bestandsblock (Tabellen-Suche, Mindestspalten-
            # Regel, Teilmengen-Vertrag, Cross-Location-Konsistenz) ...
            pass

    score_match = _SCORE_WINNER_RE.search(body)
    if score_match:
        errors.append(...)
    return errors
```

**3. `run_validation()` liest den Header aus derselben Nachricht**, aus der auch der Body extrahiert wird (kein zweiter IMAP-Roundtrip):

```python
def run_validation(min_locations: int = 3) -> Tuple[bool, List[str]]:
    try:
        msg = _fetch_latest_message()
    except Exception as e:
        return False, [f"FEHLER: E-Mail konnte nicht geladen werden: {e}"]

    body = _extract_html_body(msg)
    # Fehlender Header (Alt-Mails vor diesem Feature) oder Wert != "false"
    # => True (bisheriges strenges Verhalten bleibt der sichere Default).
    hourly_enabled = msg.get("X-GZ-Compare-Hourly-Enabled") != "false"

    all_errors = []
    all_errors.extend(validate_structure(body, hourly_enabled=hourly_enabled))
    all_errors.extend(validate_location_count(body, min_locations))
    all_errors.extend(validate_plausibility(body))
    all_errors.extend(validate_format(body))
    all_errors.extend(validate_hourly_table(body))
    return len(all_errors) == 0, all_errors
```

**4. `validate_hourly_table()` bleibt unverändert.** Bei `hourly_enabled=False` existieren keine Orts-Stundentabellen im HTML; `_find_location_hour_table()` liefert für jeden Ort `None`, die Funktion überspringt diese Fälle bereits heute (`if table is None: continue`, Kommentar "bereits von `validate_structure()` gemeldet") ohne Fehler zu erzeugen. Kein Code-Edit nötig — verifiziert durch AC-1/AC-3-Test statt Code-Annahme.

**5. `_find_location_hour_table()`-Härtung (Adversary-Fund F001, während Implementierung entdeckt).** Beim Umsetzen von AC-3 zeigte der Adversary einen **vorbestehenden** Mechanismus-Fehler (unabhängig vom `hourly_enabled`-Feature, im unveränderten HEAD reproduzierbar): Die Funktion nahm bisher die *erste* `<table>` nach dem `ORT`-Kopf. Beim **letzten** Ort (kein nachfolgender `ORT`-Kopf → Suchgrenze = Body-Ende) griff sie bei fehlender Stundentabelle fälschlich die nächste Fremdtabelle (Abo-Footer) und meldete statt „nicht gefunden" eine irreführende „Mindestspalten"-Meldung — die korrekte Erkennung war nur zufällig (Footer hat nie „Zeit" als erste Spalte). Das widerspricht dem freigegebenen Erosionsschutz AC-3. **Fix (gate-verschärfend, kein Aufweichen):** Die Stundentabelle wird jetzt über ihr *stabiles* Merkmal identifiziert — innerhalb des Vorwärts-Bounds (`body[match.end():section_end]`) wird über alle `<table>` iteriert und die erste zurückgegeben, deren Kopfzeile erste Zelle `== "Zeit"` ist (Renderer-Vertrag `_render_hour_table`, „Zeit" ist fest verdrahtete erste Spalte); sonst `None`. Adversary Runde 2 (VERDICT HOLDS) bestätigte per Scan: keine andere Tabelle im echten Compare-Render hat „Zeit" als erste Zelle → keine Maskierung möglich. Abgedeckt durch Zusatztests `test_last_location_missing_table_is_flagged` / `test_first_location_missing_table_is_flagged`.

## Expected Behavior

- **Input:** Reale, über Resend versendete und in Stalwart zugestellte Compare-Mail im Test-Postfach `gregor-test@henemm.com`, mit oder ohne Header `X-GZ-Compare-Hourly-Enabled`.
- **Output:** `run_validation()` liefert `(True, [])` bei spec-konformer Mail (inkl. bewusst abgeschaltetem Stundenverlauf), `(False, [Fehlerliste])` bei jeder echten Struktur-Verletzung — unabhängig vom Header-Zustand. CLI-Exit-Code 0 bzw. 1 wie bisher.
- **Side effects:** Ein IMAP-Read gegen das Test-Postfach pro Lauf (unverändert), strukturiertes YAML-Log unter `.claude/workflows/_log/` (unverändert, `_write_validation_log`).

## Acceptance Criteria

- **AC-1:** Given eine real versendete Compare-Mail mit Header `X-GZ-Compare-Hourly-Enabled: false` und ohne jegliche Orts-Stundentabellen im HTML / When `email_spec_validator.py` gegen das Stalwart-Test-Postfach läuft / Then der Validator terminiert mit Exit-Code 0 (keine Struktur-Fehler zur Stundentabelle).
  - Test: Echter Compare-Mail-Versand mit `hourly_enabled=false` an `gregor-test@henemm.com` über den produktiven Sendepfad, anschließend realer CLI-Lauf von `email_spec_validator.py` gegen dieses Postfach, Exit-Code-Prüfung `== 0`. Kein Mock, keine Dateiinhalt-Assertion.

- **AC-2:** Given eine real versendete Compare-Mail mit Header `X-GZ-Compare-Hourly-Enabled: true` und vollständigen, spec-konformen Orts-Stundentabellen / When der Validator läuft / Then Exit-Code 0 (unverändertes strenges Verhalten bleibt für den aktivierten Fall bestehen).
  - Test: Echter Versand mit `hourly_enabled=true` an `gregor-test@henemm.com`, realer CLI-Lauf, Exit-Code-Prüfung `== 0`. Regressionsschutz gegen bestehendes v2-Vertragsverhalten.

- **AC-3:** Given echt gerendertes v2-Compare-HTML mit einer gezielt fehlenden Stundentabelle für mindestens einen Ort / When `validate_structure(html, hourly_enabled=True)` aufgerufen wird / Then mindestens ein `STRUKTUR:`-Fehler zur fehlenden Stundentabelle wird gemeldet und benennt den betroffenen Ort.
  - Test: Gold-Standard-Negativfall nach dem etablierten Muster von `test_issue_1106`/`test_issue_1110` — HTML wird über den **echten** Renderer (`render_compare_html`) erzeugt und die Stundentabelle eines Ortes real entfernt, dann die reale Parse-Funktion `validate_structure(html, hourly_enabled=True)` ausgeführt (kein Mock, kein Patch — es läuft der echte Parser). Assertion: nicht-leere Fehlerliste, die den Ortsnamen nennt. Bewusst so gebaut, dass ein globales Aufweichen der Stundentabellen-Pflicht (z.B. `if hourly_enabled:` versehentlich entfernt/invertiert) den Test rot macht — Erosionsschutz. Vorbereiteter Stub: `tests/tdd/test_issue_1107_compare_sections.py::TestValidatorHourlyEnabledGating::test_hourly_enabled_true_still_flags_missing_table_for_one_location` (aktuell `skip`, in diesem Workflow zu aktivieren/übernehmen). Ergänzend belegen AC-1/AC-2 den vollständigen Pfad per echter Zustellung + CLI-Lauf ans Test-Postfach.

- **AC-4:** Given echt gerendertes v2-Compare-HTML mit fehlender Stundentabelle für einen Ort / When `validate_structure(html)` OHNE das `hourly_enabled`-Kwarg aufgerufen wird (Bestandsaufruf, wie ihn `run_validation()` bei fehlendem Header über den Default `True` erzeugt) / Then der Fehler wird weiterhin gemeldet (Exit-Code-Pfad 1), weil der sichere Default `True` greift.
  - Test: Realer Renderer erzeugt HTML mit fehlender Ortstabelle; einparametriger Aufruf `validate_structure(html)` (== Bestandsvertrag) liefert eine nicht-leere Fehlerliste. Beweist, dass eine Alt-Mail ohne den Header (→ `run_validation` setzt `hourly_enabled=True`) unverändert streng geprüft wird. Kein Mock.

- **AC-5:** Given der bestehende öffentliche Vertrag `fetch_latest_email() -> str` / When die Funktion nach dem Refactor gegen eine reale Mail im Test-Postfach aufgerufen wird / Then sie liefert weiterhin einen nicht-leeren `str` (kein Tupel, kein `Message`-Objekt).
  - Test: `tests/tdd/test_issue_972_974_975_tooling.py::test_email_spec_validator_prefers_test_creds` läuft unverändert grün gegen eine reale Mail; Assertion `isinstance(html, str) and html` bleibt bestehen und wird nach dem Refactor erneut ausgeführt (kein neuer Test nötig, reiner Regressionsnachweis).

## Known Limitations

- Der Header-Vertrag ist rein additiv-defensiv: Fehlt der Header (z.B. bei Alt-Mails vor Issue #1107 oder bei Nicht-Compare-Mail-Typen, die den Header nie setzen), greift automatisch der strenge Default `True`. Es gibt keine Möglichkeit, den Skip ohne expliziten `X-GZ-Compare-Hourly-Enabled: false`-Header auszulösen.
- Diese Spec ändert ausschließlich den Validator (Prüf-Seite). Die Feature-Seite (Header setzen in `src/output/channels/email.py`, Frontend-Toggle) ist bereits über Issue #1107 vollständig implementiert und live — kein Teil dieses Workflows.
- `validate_hourly_table()` wird nicht angepasst, da sie bei fehlenden Tabellen bereits fail-safe ist (`continue` statt Fehler). Sollte sich dieses Verhalten künftig ändern, muss AC-1 erneut geprüft werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Tooling-/Hook-Korrektur ohne Architektur-Auswirkung auf Produktionscode, Datenmodell oder API-Verträge. Der zu lesende Header existiert bereits (Issue #1107), es wird kein neuer Vertrag eingeführt, sondern ein bestehender vollständig konsumiert.

## Changelog

- 2026-07-09: Initial spec created (Issue #1150, abgespalten von #1107 gemäß Regel "Validator-Änderungen im eigenen Workflow")
- 2026-07-09: AC-3/AC-4-Test-Nachweis präzisiert (echtes Renderer-HTML statt unmöglicher „inkonsistenter Zustellung", Muster #1106/#1110)
- 2026-07-09: Implementation-Detail 5 ergänzt — `_find_location_hour_table()`-Härtung nach Adversary-Fund F001 (letzter Ort, vorbestehender Bug); Fix gate-verschärfend, Verdict Runde 2 HOLDS
