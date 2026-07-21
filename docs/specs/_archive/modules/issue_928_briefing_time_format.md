# Spec: Stundentabelle-Zeitformat zurück auf `HH` (Issue #928)

- **Issue:** #928
- **Workflow:** fix-928-plaintext-hh-format
- **Typ:** Bug / Korrektur (Format-Regression)
- **created:** 2026-06-30

## Kontext / Root Cause (korrigiert)

Die Briefing-Stundentabelle zeigt die Uhrzeit-Spalte als `HH:00` (z.B. `20:00`,
`08:00`). Das Issue vermutete als Ursache #911 (`2205639e`) — **falsch**. Tatsächlich
stammt das Format aus Commit `2505711a` (#838): „Fix time format in HTML briefing
table cells (HH:00 instead of HH)". #838 stellte bewusst auf `HH:00` um, weil der
`briefing_mail_validator` (seit #807, `_distinct_hours`) `HH:00` in den
`<td data-label="Time">`-Zellen **verlangte**.

Der Zeilenbauer ist **geteilt**: `src/formatters/trip_report.py` erzeugt die Row-Dicts
(`_aggregate_night_block`, `_dp_to_row`) mit `"time"`-Zelle und gibt sie via
`render_email()` an **beide** Renderer weiter — Plain (`plain.py`) und HTML (`html.py`).
Deshalb erscheint `HH:00` in beiden Mail-Varianten.

Zwei Tests in `tests/tdd/test_bug_397_output_localtime.py` (AC-2 `test_night_block_first_row_is_local_arrival`,
AC-5 `test_utc_header_and_rows_unchanged`) erwarten das alte `HH`-Format und sind rot.

## PO-Entscheidung

**Beide Mail-Varianten** (Plain **und** HTML) zeigen die Stunde wieder als reine `HH`
(z.B. `20`, `08`) — **ohne** `:00`. Das macht die #838-Änderung bewusst rückgängig.
Dafür muss zusätzlich der `briefing_mail_validator` angepasst werden, sodass er `HH`
akzeptiert statt `HH:00` zu erzwingen — **ohne** die substanzielle Distinct-Hours-Prüfung
aufzuweichen.

## Acceptance Criteria

**AC-1:** Given ein gerendertes Abend-Briefing (`email_plain`) mit einem Nacht-Block
bei lokaler Ankunft 20 Uhr, When die Plain-Text-Tabelle erzeugt wird, Then zeigt die
erste Datenzeile des Nacht-Blocks die Stunde `20` (ohne `:00`) und die Stunde `18`
taucht nicht als Datenzeile auf. (deckt `test_bug_397` AC-2 ab)

**AC-2:** Given ein gerendertes Briefing im UTC-Fallback (`email_plain`) mit Daten bei
08/09/10 UTC, When die Plain-Text-Tabelle erzeugt wird, Then zeigen die ersten drei
Datenzeilen die Stunden `08`, `09`, `10` (jeweils ohne `:00`). (deckt `test_bug_397` AC-5 ab)

**AC-3:** Given ein gerendertes HTML-Briefing (`email_html`) mit Stunden-Tabelle, When
die `<td>`-Zeit-Zellen erzeugt werden, Then enthalten sie die Stunde im Format `HH`
(z.B. `08`) und **nicht** `HH:00`.

**AC-4:** Given eine real zugestellte HTML-Briefing-Mail mit Zeit-Zellen im `HH`-Format,
When `briefing_mail_validator.py` darauf läuft, Then liefert er Exit 0 (akzeptiert `HH`).
Die Distinct-Hours-Prüfung bleibt wirksam: eine Mail, deren Tabellenzeilen alle dieselbe
Stunde tragen, wird weiterhin mit Exit ≠ 0 abgelehnt.

**AC-5:** Given die Golden-Vergleichs-Suite (`test_email_plain_golden.py`,
`test_email_html_golden.py`), When sie nach der Änderung läuft, Then ist sie grün, weil
die Golden-Dateien das `HH`-Format widerspiegeln.

## Betroffene Dateien

- `src/formatters/trip_report.py` — `:02d}:00"` → `:02d}"` an zwei Stellen (Zeilen ~321, ~403)
- `.claude/hooks/briefing_mail_validator.py` — Zeit-Zellen-Prüfung akzeptiert `HH` statt `HH:00` zu erzwingen; Distinct-Hours-Logik bleibt
- `tests/golden/email/*-plain.txt`, `tests/golden/email/*-html.txt` — neu erzeugt (Zeitspalte `HH`)
- Validator-Fixture-Tests mit hartem `HH:00`: `tests/tdd/test_issue_733_briefing_mail_validator.py`, ggf. `tests/tdd/test_briefing_mail_inhalt.py` — auf `HH` angleichen bzw. beide Formate zulassen

## Was bleibt unverändert

- Die Lokalzeit-Logik (Bug #398 „2 h zu früh") — nur das **Anzeigeformat** ändert sich, nicht welche Stunde gezeigt wird
- Die Distinct-Hours-Qualitätsprüfung des Validators (Substanz)
- Segment-Header-Zeiten (`local_fmt(...)`, z.B. „08:00–10:00" in Überschriften) — betrifft nur die Datenzeilen-Spalte, nicht die Bereichs-Labels
- SMS-/Telegram-Pfade

## Mocking-Verbot

Tests laufen gegen echte gerenderte Reports bzw. die real zugestellte Staging-Mail
(`gregor-test@henemm.com`, IMAP). Kein Mock, kein Gmail.
