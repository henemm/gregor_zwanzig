# Messung Vorher/Nachher #3317 Scheibe A (24.11.2026)

Mac, 10 Kerne, dieselbe Sitzung, Dateien einzeln und verschränkt gemessen (vorher, dann nachher). Wanduhr des ganzen Aufrufs `uv run pytest <datei> [-n 4 --dist loadgroup] -p no:cacheprovider`. Vorher = Stand a6ccf6ca7 (alle vier Dateien UND `tests/helpers/wanduhr_matrix.py` per `git show` eingewechselt, danach zurück, Hash identisch). Last = 1-Minuten-Mittel vor/nach dem Lauf.

| Datei | Form | vorher | Last | nachher | Last | Ergebnis vorher / nachher |
|---|---|---|---|---|---|---|
| test_epic_129a_3_ui_removed | seriell | 31,4 s | 3,6/4,1 | 2,9 s | 4,1/4,0 | 6 grün / 5 grün |
| | -n 4 | 50,8 s | 3,1/2,9 | 6,3 s | 2,9/2,8 | 6 grün / 5 grün |
| test_dwd_thunder_parallel_fetch | seriell | 59,9 s | 4,0/5,6 | 50,0 s | 5,6/4,3 | 18 grün, 1 rot (ac1) / 19 grün, 1 rot (ac1) |
| | -n 4, vier Paare | 23,2 / 23,2 / 23,5 / 23,8 s | 2,8-3,9 | 21,4 / 20,8 / 21,3 / 21,4 s | 3,0-3,9 | 1-2 rot (ac1; in 2 von 4 auch test_ac2_budgetende_laesst_nur_hintere...) / 1 rot (ac1) |
| test_pytest_collection_and_timeout_safety | seriell | 254,5 s | 4,3/2,6 | 103,8 s | 2,6/2,2 | 14 grün, 1 übersprungen / 20 grün, 1 übersprungen |
| | -n 4 | 203,8 s | 3,2/3,5 | 55,9 s | 3,5/3,6 | 14 grün, 1 übersprungen / 20 grün, 1 übersprungen |
| test_radar_nowcast_segment_wanduhr_unabhaengig | seriell | 56,4 s | 2,2/3,1 | 28,5 s | 3,1/3,1 | 2 grün / 3 grün |
| | -n 4 | 37,5 s | 3,6/3,3 | 20,6 s | 3,3/3,5 | 2 grün / 3 grün |

Alle vier Dateien sind seriell und unter `-n 4` schneller. DWD unter `-n 4` nur um rund 2 s (4 von 4 Paaren), weil der 2-s-Test (10 s) und `ac1` (8 s) die Laufzeit bestimmen; belassen.

## Die 10,5 s des 2-s-Tests (vor dem Umbau gemessen)

`--durations` vor dem Umbau: `test_ac3_haengender_download_...` 10,57 s. `_raster_vorab_erzeugen` allein gemessen: 331 Raster (3 Läufe x 13 Zeitpunkte, 9 Größen, gleiche Werte einmal) in **7,13 s**, dazu 2 s Timeout und rund 1 s Rest. Ursache ist die Vorab-Erzeugung der Raster außerhalb der Zeitmessung, nicht `getfqdn` (dieser Anteil wird hier nicht umgebaut; nach dem Umbau 10,1 s). `getfqdn` kostete in dieser Sitzung nichts Messbares (ac1 vorher 8,4 s, nicht 40 s); der 35-s-Wert vom Vormittag ließ sich nicht wiederholen.

## Worker-Gruppe der Sammlungs-Datei (20-s-Regel)

Die eine Voll-Sammlung allein dauert unter `-n 4` **39,0 s** (Setup von `sammlung`, Last 6,4). Damit liegt die Datei nach dem Umbau über dem Richtwert 20 s: Ausweichfall, eigene Gruppe `sammlung`, eigene Sammlung im mtime-Test (Gruppe `echtdaten`). Vorher unter `-n 4`: bis zu vier Sammlungen je Worker plus mtime-Zweitlauf.

## Radar: gleichzeitig oder nacheinander (unter `-n 4`)

Alle Varianten mit wiederverwendeter Referenz, je zwei Runden, verschränkt; "Grundlast" = 10 rechnende Prozesse auf 10 Kernen.

| Variante | ohne Grundlast | mit Grundlast |
|---|---|---|
| nacheinander | 28,1 / 27,0 s (CPU 56 / 52 s) | 59,1 / 58,2 s (CPU 60 / 59 s) |
| gleichzeitig | 16,4 / 16,9 s (CPU 54 / 45 s) | 41,3 / 39,2 s (CPU 68 / 64 s) |

Gewinn in 4 von 4 Paaren, deshalb gleichzeitig. Grenze der Aussage: die Arbeit ist rechenlastig, die CPU-Summe bleibt gleich oder steigt unter Grundlast um rund 10 %. Auf einem 4-Kern-Runner mit vier ausgelasteten Workern verkürzt das die Einzeldatei, nicht zwingend die ganze Suite; dort nicht gemessen.

## Kein Timeout angehoben, keine Schwelle gesenkt (Vergleich a6ccf6ca7 / nachher)

| Datei | vorher | nachher |
|---|---|---|
| test_epic_129a_3_ui_removed | timeout(120) x1 | keine (Test entfällt) |
| test_dwd_thunder_parallel_fetch | timeout(30) x5, timeout(40) x10, timeout(60) x1; `<= 2.0 + 3.0`, `>= 10` je x1 | timeout(30) x5, timeout(40) x9 (10-s-Test entfällt), timeout(60) x3 (zwei neue Tests); `<= 2.0 + 3.0`, `>= 10` je x1 |
| test_pytest_collection_and_timeout_safety | timeout(180) x4, timeout(300) x3, Subprozess: 120 x2, 90 x5, 60 x4, 30 x3 | timeout(180) x4, timeout(300) x1, Subprozess: 120 x2, 90 x3 (Sammlung, mtime, AC-2-Beleg neu), 60 x2, 30 x2 |
| test_radar_nowcast_segment_wanduhr_unabhaengig | timeout(300) x1 | timeout(300) x1 |
| wanduhr_matrix | `_SUBPROC_TIMEOUT_SEC = 120` | unverändert |

`pyproject.toml` und `tests/conftest.py` unverändert. Der Kindprozess des Hänger-Tests hat weiter 60 s.

Zählung `timeout(300)`: gezählt ist Text im Quelltext einschließlich Docstring; die Modulgrenze `pytestmark = timeout(300)` ist unverändert, entfallen ist der 30-s-Hänger-Test mit eigenem `timeout(300)` (samt Nennung im Docstring).
