# Laufzeiten vorher/nachher (#3316, AC-10)

2026-11-24 14:47:01 bis 14:49:17, Mac, je Datei ein eigener serieller Lauf (`-n 0`), ALT und NEU abwechselnd in 3 Runden,
Last (1 min) 2,4 bis 5,0. ALT = Fassung aus `origin/main` (per `git show` gesichert, kurzzeitig am Originalpfad, danach
zurückkopiert; SHA-1 aller vier Dateien vor und nach der Messung identisch, `filecmp` True).
Alle Läufe grün. NEU enthält die zusätzlichen Tests dieser Scheibe.

## Ganze Datei (Sekunden)

| Datei | ALT Runde 1 / 2 / 3 | NEU Runde 1 / 2 / 3 | Median ALT -> NEU | Tests ALT -> NEU |
|---|---|---|---|---|
| test_thunder_scale_local_copy_guard.py | 13,43 / 13,23 / 13,91 | 6,56 / 6,63 / 7,09 | 13,43 -> 6,63 | 79 -> 121 |
| test_repo_path_hardcoding_ratchet.py | 5,79 / 5,81 / 6,34 | 4,77 / 4,72 / 5,00 | 5,81 -> 4,77 | 32 -> 38 |
| test_test_suite_passes_user_id_explicitly.py | 3,20 / 3,15 / 3,39 | 2,08 / 2,15 / 2,13 | 3,20 -> 2,13 | 1 -> 7 |
| test_bezeichner_vorfilter.py | 3,45 / 3,33 / 3,50 | 3,49 / 3,67 / 3,64 | 3,45 -> 3,64 | 19 -> 19 |
| Summe der Mediane | | | 25,89 -> 17,17 | 131 -> 185 |

## Einzelne Phasen (Sekunden, `--durations`)

| Phase | ALT Runde 1 / 2 / 3 | NEU Runde 1 / 2 / 3 |
|---|---|---|
| thunder Setup `tests_baum_scan` | 7,24 / 7,08 / 7,64 | 1,79 / 1,82 / 1,92 |
| thunder Backend: AC-12 | 1,40 / 1,41 / 1,39 | 1,39 / 1,39 / 1,54 |
| thunder Backend: Marker-Lauf | 1,42 / 1,40 / 1,43 | 1,39 / 1,42 / 1,45 |
| thunder Backend: Basislinie bzw. Rohlauf | 1,41 / 1,41 / 1,45 | 1,46 / 1,47 / 1,59 |
| thunder Backend: ohne Whitelist | 1,50 / 1,47 / 1,53 | entfällt (abgeleitet) |
| repo_path AC-3 | 5,47 / 5,49 / 5,98 | 4,44 / 4,38 / 4,67 |
| user_id AC-10 | 3,02 / 2,98 / 3,24 | 1,90 / 1,98 / 1,96 |
| vorfilter: innerer Gruppenlauf | 0,95 / 0,93 / 0,95 | 1,02 / 1,08 / 1,05 |

Grenzen: nur Mac; CI protokolliert keine Einzelzeiten. Ein Lauf unmittelbar davor (14:44 bis 14:46, gleiche Methode,
Dateisummen wegen eines Auswertungsfehlers nicht erfasst) zeigte dieselben Größenordnungen (Baum-Setup 6,9 bis 7,4 -> 1,8).
Der CI-Beleg für das 30-s-Netz (AC-10) steht noch aus: grüner `test`-Job des PR.
