# AC-1-Referenz: Trip-Ausblick VOR der Lieferung #1720 Scheibe 1

Aufgezeichnet am **2026-08-14** aus dem unveraenderten Produktivcode von

    dd86a85362fa1eb5d9715cbed4c88c65b8549e8a   (Branch feat-1720-vorschau-metriken, = origin/main)

Erzeugt mit

    uv run python -m tests.helpers.trip_outlook_selection

Der Aufruf geht ueber den **echten Aufrufpfad** `render_email()` ->
`render_html()`/`render_plain()` -> Ausblick-Block, nicht ueber den
isolierten `render_outlook_table()`-Aufruf (den deckt bereits
`tests/tdd/test_trip_outlook_parity.py` ab -- und genau der durchlaeuft die
neue Verdrahtung in `html.py:1357`/`plain.py:338` nie).

| Datei | Inhalt |
|---|---|
| `outlook_table.html` | die Ausblick-Tabelle des HTML-Teils, Sieben-Spalten-Kopf `Tag N D R PR Wind Böen Gew` + `ACC` |
| `outlook_legend.html` | die Abkuerzungs-Legende unter der Tabelle, **im Wortlaut von heute** (`N Nacht-Tief …`) |
| `outlook_block.txt` | der Klartext-Ausblick-Block inkl. 26-Zeichen-Namensfeld und Notizzeile |

## Die EINE erlaubte Abweichung

`outlook_legend.html` traegt bewusst den **heutigen, fehlerhaften** Wortlaut
`N Nacht-Tief`. Der Test wendet vor dem Vergleich genau eine dokumentierte
Ersetzung auf die Referenz an (`N Nacht-Tief` -> `N Tagestief`, AC-8,
PO-Entscheid 2026-08-14): die Spalte zeigt `summary.temp_min_c`, das
Tages-Minimum **innerhalb des Wanderfensters**, nicht das naechtliche Tief
(Beleg-Kette im Kontextdokument bis `weather_metrics.py:509-514`).

Die Aufzeichnung bleibt damit authentisch (roher Ist-Stand) und die
Abweichung steht zitierbar im Testcode statt still in der Fixture.

## Diese Dateien werden NICHT nachgezogen

Wird ein Test gegen diese Referenz rot, hat sich die Trip-Mail veraendert --
das ist der Befund, nicht der Anlass, die Dateien neu zu erzeugen. Das
Aufzeichnungs-Werkzeug schreibt deshalb nur ueber eine vorhandene
Aufzeichnung, wenn ihm ausdruecklich `--force` uebergeben wird.

## Ausnahme 2026-08-14 (#1801, PO-freigegeben)

`outlook_table.html` wurde manuell auf die neue Warnstufen-Palette (#1801)
nachgezogen. Nachgemessen per Hex-Maskierung (Ist gegen Alt-Referenz):
gleiche Laenge, gleiche Anzahl Farbwerte, nach Maskierung zeichengleich --
es weichen ausschliesslich drei Flaechenfarben ab (`#fbeeb8`->`#fdf4cd`,
`#fad6b8`->`#fbe3cc`, `#f6c5bf`->`#f7d3e2`). Keine Struktur-, Text- oder
Zahlenaenderung. `outlook_legend.html` und `outlook_block.txt` sind von
#1801 nicht betroffen (keine Hex-Werte / unveraendert) und bleiben
unangetastet.
