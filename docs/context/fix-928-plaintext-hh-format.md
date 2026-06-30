# Context: fix-928-plaintext-hh-format

## Aufgabe
Issue #928 — Stundentabelle-Zeitformat im Briefing zurück von `HH:00` auf `HH`.
Zwei Tests in `tests/tdd/test_bug_397_output_localtime.py` (AC-2, AC-5) sind rot,
weil das angezeigte Zeitformat von `HH` auf `HH:00` wechselte.

## Root Cause (verifiziert)
- Format `HH:00` stammt aus Commit `2505711a` (#838), **nicht** aus #911 (Issue-Diagnose falsch).
- #838 stellte bewusst auf `HH:00` um, weil `briefing_mail_validator` (seit #807,
  `_distinct_hours`) `HH:00` in `<td data-label="Time">`-Zellen verlangte.
- Geteilter Zeilenbauer: `src/formatters/trip_report.py`
  - `_aggregate_night_block` (~Zeile 321): `{"time": f"{block_hour:02d}:00"}`
  - `_dp_to_row` (~Zeile 403): `{"time": f"{local_hour(dp.ts, self._tz):02d}:00"}`
- Beide Renderer (`src/output/renderers/email/plain.py`, `.../html.py`) rendern `r["time"]`
  verbatim → `HH:00` erscheint in Plain UND HTML.

## PO-Entscheidung
Beide Varianten (Plain + HTML) zurück auf `HH`. Validator wird angepasst, sodass er
`HH` akzeptiert (Distinct-Hours-Substanz bleibt). Reverts #838 bewusst.

## Betroffene Dateien
- `src/formatters/trip_report.py` (2 Format-Strings)
- `.claude/hooks/briefing_mail_validator.py` (Zeit-Zellen-Format-Erwartung)
- `tests/golden/email/*-{plain,html}.txt` (Neu-Erzeugung)
- `tests/tdd/test_issue_733_briefing_mail_validator.py`, ggf. `tests/tdd/test_briefing_mail_inhalt.py` (HH:00-Fixtures)

## Abhängigkeiten / Gates
- `renderer_mail_gate`: trip_report.py ist Mail-Content-Datei → Commit braucht frischen
  `test_issue_811_mode_matrix.py`-Lauf + erfolgreichen `briefing_mail_validator`-Lauf gegen Staging-Mail.
