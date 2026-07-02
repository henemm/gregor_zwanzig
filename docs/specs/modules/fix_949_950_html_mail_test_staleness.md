---
entity_id: fix_949_950_html_mail_test_staleness
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [test-staleness, html-mail, regression]
---

# HTML-Mail-Test-Staleness-Fix (#949 + #950)

## Approval

- [ ] Approved

## Purpose

Zwei Unit-Tests prüfen veraltete String-Erwartungen für den HTML-Mail-Renderer und
schlagen seit zwei späteren, freigegebenen Design-Fidelity-Änderungen (#884, #911) fehl,
obwohl der Renderer korrekt arbeitet. Die Tests werden an die aktuelle, freigegebene
Darstellung angepasst.

## Source

- **File:** `tests/unit/test_destination_segment.py` (Test `test_html_contains_ziel_label`, Zeile 128)
- **File:** `tests/unit/test_trip_report_formatter.py` (Test `test_structural_columns_always_visible`, Zeile 187)
- **Referenz (wird NICHT geändert):** `src/output/renderers/email/html.py:875-892` (Ziel-Sektion),
  `src/output/renderers/email/html.py:483` (Time-Header)

> **Schicht-Hinweis:** Reine Python-Backend-Unit-Tests (`tests/unit/`), keine Schicht-Verwechslung möglich —
> es gibt keine Frontend- oder Go-API-Berührung in diesem Fix.

## Estimated Scope

- **LoC:** ~4 (zwei Assertions ersetzt/ergänzt)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/html.py` | source (unverändert) | Liefert die aktuelle, freigegebene HTML-Struktur, gegen die die Assertions geprüft werden |

## Implementation Details

**#949 — `test_html_contains_ziel_label`** (`tests/unit/test_destination_segment.py:128-141`):

Aktuell (stale):
```python
assert "Ziel" in result.email_html, (
    "HTML must contain 'Ziel' label for destination segment"
)
```

Neu — prüft die seit #884 tatsächlich gerenderte Uppercase-Eyebrow/-Headline
(`src/output/renderers/email/html.py:890+892`, exakter String `"WETTER AM ZIEL"`):
```python
assert "WETTER AM ZIEL" in result.email_html, (
    "HTML must contain the uppercase 'WETTER AM ZIEL' destination label "
    "(design fidelity #884)"
)
```

**#950 — `test_structural_columns_always_visible`** (`tests/unit/test_trip_report_formatter.py:187-198`):

Aktuell (stale):
```python
html = report.email_html
assert "<th>Time</th>" in html
assert "Segment" in html  # segment header always shown
```

Neu — prüft strukturell (Regex auf Tag + Inhalt statt exaktem String), damit die
Assertion unabhängig von künftigen reinen Style-Attribut-Änderungen bleibt, aber bei
einem tatsächlich fehlenden Time-Header rot wird:
```python
import re

html = report.email_html
assert re.search(r"<th[^>]*>Time</th>", html), (
    "HTML must contain a Time column header <th> (with or without inline style, "
    "see #911 Outlook-Kompatibilität)"
)
assert "Segment" in html  # segment header always shown
```

## Expected Behavior

- **Input:** Ein `TripReportFormatter.format_email(...)`-Aufruf, der eine Ziel-Etappe
  (`segment_id == "Ziel"`) bzw. eine Stundentabelle rendert.
- **Output:** `result.email_html` enthält weiterhin nachweislich die Ziel-Sektion
  (Uppercase-Label) bzw. die Time-Spalte (mit Inline-Style).
- **Side effects:** keine — reine Testanpassung, kein Produktionscode betroffen.

## Acceptance Criteria

- **AC-1:** Given ein gerenderter Trip-Report mit einer Ziel-Etappe (`segment_id == "Ziel"`),
  When `test_html_contains_ziel_label` läuft, Then muss die Assertion auf den tatsächlich
  im HTML vorkommenden Uppercase-String `"WETTER AM ZIEL"` prüfen und grün sein.
  - Test: `uv run pytest tests/unit/test_destination_segment.py::TestFormatterDestinationRendering::test_html_contains_ziel_label -v`
    muss PASSED liefern; manuelle Kontrollprobe: Ersetzt man den Renderer-String testweise
    durch einen anderen Wortlaut (z.B. `"WETTER"` entfernen), muss die Assertion rot werden
    (keine Tautologie).

- **AC-2:** Given ein gerenderter Trip-Report mit deaktivierten Metrik-Spalten (temperature,
  wind_chill), When `test_structural_columns_always_visible` läuft, Then muss die Assertion
  per Regex `<th[^>]*>Time</th>` prüfen, dass die Time-Spalte strukturell vorhanden ist
  — unabhängig vom exakten Inline-Style-Attribut aus #911.
  - Test: `uv run pytest tests/unit/test_trip_report_formatter.py::TestMetricsFiltering::test_structural_columns_always_visible -v`
    muss PASSED liefern; Kontrollprobe: Entfernt man testweise den gesamten `<th>Time</th>`-Header
    aus dem Renderer-Output, muss die Assertion rot werden.

- **AC-3:** Given der vollständige Testlauf des Projekts, When
  `uv run pytest tests/unit/test_destination_segment.py tests/unit/test_trip_report_formatter.py`
  ausgeführt wird, Then müssen beide vormals rot markierten Tests (#949, #950) grün sein und
  keine anderen Tests in diesen beiden Dateien durch die Änderung brechen.
  - Test: Vollständiger Lauf beider Testdateien, Exit-Code 0, keine neuen Failures gegenüber
    dem Stand vor dem Fix (Vergleich der übrigen Testfälle unverändert grün).

## Known Limitations

- Der Renderer-Code (`src/output/renderers/email/html.py`) wird nicht angefasst — sollte sich
  die Ziel-Sektion oder der Time-Header künftig erneut ändern (neues Design-Fidelity-Update),
  müssen diese Tests erneut nachgezogen werden. Das ist ein bekanntes, akzeptiertes Muster in
  diesem Projekt (siehe #926/#867/#820/#797/#815/#625).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testkorrektur an bereits freigegebenem, unverändertem Produktionscode —
  keine Architektur- oder Designentscheidung getroffen.

## Changelog

- 2026-07-02: Initial spec created
