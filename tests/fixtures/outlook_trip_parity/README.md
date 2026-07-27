# Golden-Referenz: Trip-Ausblick VOR dem Umbau (#1361 Befund 2 / #1368)

Aufgezeichnet am 2026-07-27 auf Basis-Stand `8eb15981`, erzeugt aus
`tests/tdd/test_trip_outlook_parity.py::parity_rows()` ueber
`render_outlook_table(rows, show_acc=True)` bzw.
`render_outlook_plain(rows, show_acc=True)`.

Zweck: `src/output/renderers/email/outlook.py` ist der vollstaendig geteilte
Ausblick-Baustein von Trip UND Ortsvergleich. Die Spec
(`docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md`, AC-11)
verbietet jede Aenderung an der Trip-Mail; erlaubt sind nur additive, per
Default-Parameter abgeschirmte Erweiterungen.

**Diese Dateien werden NICHT neu erzeugt.** Wird
`tests/tdd/test_trip_outlook_parity.py` rot, hat sich die Trip-Mail veraendert
— das ist der Befund, nicht ein veralteter Referenzstand.
