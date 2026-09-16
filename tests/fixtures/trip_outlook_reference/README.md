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

## Nachgefuehrte Zellen

| Datum | Datei | Zelle | Alt | Neu | Grund |
|---|---|---|---|---|---|
| 2026-08-18 | `outlook_block.txt` | Zeilen "Mo"/"Mi", Gewitter-Feld | `⚡mittel` / `⚡hoch` | `⚡mittel@10` / `⚡hoch@10` | #1493 AC-3 (freigegebene Spec `feat_1493_gewitter_onset_sichtbar.md`): der Klartext-Ausblick fuehrt die Onset-Stunde, wie HTML-Zelle, Telegram und SMS es laengst tun. `outlook_table.html` und `outlook_legend.html` sind unveraendert; die Di-Zeile (`⚡–`, kein Tagesgewitter) ebenfalls |
| 2026-08-20 | `outlook_block.txt`/`compact_block.txt`/`telegram_bubble.txt` | alle Temperatur-Zellen | `9–21°C`/`9-21C`/`9–21°C` u.a. | `9/21°C`/`9/21C`/`9/21°C` u.a. | #1848 A1 AC-9 (Altform-Klartext auf denselben Schraegstrich-Trenner wie die SMS-Schreibweise gezogen -- betrifft `format_trend_tokens()`, `temp_str`, `helpers.py:943`, wirkt in alle drei Klartext-Renderer durch; `outlook_table.html`/`outlook_legend.html` sind unveraendert, das HTML rendert N/D als getrennte Spalten ohne Trennzeichen) |
| 2026-09-15 | `outlook_table.html` | Spaltenkoepfe `N`/`D`/`R`/`PR`/`Wind`/`Böen`/`Gew` | `N`/`D`/`R`/`PR`/`Wind`/`Böen`/`Gew` | `Temp Minimum`/`Temp Maximum`/`Rain`/`Rain%`/`Wind`/`Gust`/`Thdr` | #2136/ADR-0068 -- neu aufgezeichnet mit `uv run python -m tests.helpers.trip_outlook_selection --force`; nachgemessen (`git diff`): ausschliesslich die acht `<th>`-Texte weichen ab, alle `<td>`-Zellen/Farben/Struktur zeichengleich. `outlook_legend.html` bleibt bewusst UNVERAENDERT (s. "Die EINE erlaubte Abweichung" oben) -- die AC-8-Korrektur betrifft nur die Stundentabellen-Legende, nicht die Ausblick-Spaltenkoepfe. |
| 2026-09-15 | `outlook_block.txt` | Zeilen "Mo"/"Di"/"Mi", alle vier Werte-Tokens | ohne `col_label`-Praefix | mit `col_label`-Praefix (`Temp …  Rain …  Wind …  Thdr …`) | #2136/ADR-0068 AC-4 -- neu aufgezeichnet mit demselben Werkzeug; Werte selbst unveraendert, nur die Praefixe kommen hinzu. |
| 2026-09-15 | `outlook_legend.html` | -- (Fixture selbst bleibt Byte fuer Byte stehen) | von zwei Tests gegen den Altbestand-Legendenblock (Pfad 1, `html.py`) geprueft | Fixture bewacht **nichts mehr** | Adversary-Fund F001 (#2136/ADR-0068, Phase-6-Nachbesserung): der eigene `<div>`-Legendenblock aus #1720/AC-8 widersprach seit der `col_label`-Umstellung den `<th>`-Koepfen direkt darueber (z. B. Block sagte `R Regen mm`, Tabelle zeigte bereits `Rain`) und wurde ersatzlos entfernt (`html.py:1411-1419`) -- die Spaltenlegende kommt seither ausschliesslich aus der geteilten Fusszeile (`build_column_legend(..., outlook_active=True)`). Die beiden Tests, die vorher gegen diese Datei pruefften, sind umgezogen auf `html_outlook_legend(html) is None` bzw. auf die Fusszeilen-Legende (`tests/tdd/test_trip_outlook_metric_selection.py`). Die Datei bleibt absichtlich liegen (kein Loeschzwang), traegt aber ab hier keine Testbedeutung mehr. |

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
