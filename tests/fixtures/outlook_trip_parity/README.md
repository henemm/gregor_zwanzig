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

## Nachgefuehrte Zellen

| Datum | Datei | Zelle | Alt | Neu | Grund |
|---|---|---|---|---|---|
| 2026-08-10 | `...html` | Zeile "Di", Spalte "Gew" | `–` | `mittel @16` | #1653/F002 |
| 2026-08-10 | `...txt` | Zeile "Mo", Gewitter-Feld | `⚡MED` | `⚡mittel` | #1653/F004 |
| 2026-08-10 | `...txt` | Zeile "Di", Gewitter-Feld | `⚡–` | `⚡mittel` | #1653/F004 |
| 2026-08-14 | `...html` | alle Zellen mit gelber/oranger Ampel-Toenung (Regenwahrsch./Gewitter, Zeilen "Mo"/"Di") | `#fbeeb8`/`#fad6b8` | `#fdf4cd`/`#fbe3cc` | #1801 S2 (design_tokens.tone_css() ist die geteilte Farbquelle von `render_outlook_table()`; `.txt`-Gegenstueck traegt keine Farben, unveraendert) |
| 2026-08-18 | `...txt` | Zeilen "Mo" und "Di", Gewitter-Feld | `⚡mittel` | `⚡mittel@16` | #1493 (AC-3: der Klartext-Ausblick fuehrt die Onset-Stunde wie HTML-Zelle, Telegram und SMS; `...html` traegt `mittel @16` bereits seit #1653 und ist unveraendert) |

Beide Eingabezeilen tragen `hourly_thunder` mit "mittel" um 16 Uhr — im
Tagesfenster 4-19 —, waehrend das Aggregat `thunder` einmal `MED` und einmal
`NONE` sagt. Die Di-Zeile ist damit dieselbe gegenlaeufige Konstellation in
beiden Kanaelen: der alte Wert (`–` im HTML, `⚡–` im Klartext) schrieb Fehler 1
aus Issue #1653 fest (Wort und Uhrzeit aus verschiedenen Zeitraeumen, das
Tagesgewitter verschwand). AC-1 der freigegebenen Spec verlangt beides aus
demselben Tagesfenster; das Wort kommt seither aus `thunder_day_token`. Die
Mo-Zeile aendert nur die Schreibweise mit: das Tagestoken fuehrt die deutschen
Stufenwoerter (`leicht`/`mittel`/`hoch`) statt der Programmnamen des Aggregats
— unvermeidliche Folge des Quellenwechsels, kein eigener Eingriff (#1654
bleibt fuer die uebrigen Fundstellen zustaendig). Der Rest beider Dateien ist
unveraendert.

Eine Nachfuehrung ist nur unter diesen Bedingungen zulaessig: der neue Wert
folgt aus einem freigegebenen AC, die Aenderung ist auf die davon betroffenen
Zellen begrenzt, und sie wird hier mit Grund eingetragen.
