# Context: fix-2554-dwd-gewitterabruf-budget

## Request Summary
Der DWD-Gewitterabruf (`DwdDirectProvider.fetch_thunder_signals_named`) schöpfte am 12.10.2026 (14:27–18:52 UTC)
bei jedem Aufruf das 150-s-Budget aus; je Gewittergröße kamen nur 1–2 von ~12 Zeitpunkten an. Berichte wurden
dadurch ~150 s langsamer, `/e2e-verify` für #1405 S1 scheiterte an Timeouts. Refs #1405.

## Messung 12.10. ~19:45–19:55 UTC (Intake, dieser Workflow)
- Erste Messung: `lpi`, `grau_gsp` laufen in den 60-s-Timeout, `cin_ml` 5,2 s, übrige Größen < 0,02 s.
- Direkt danach, zweimal wiederholt: alle Downloads 0,02–0,06 s. Dekodieren (`bz2` + rasterio-Fenster) 0,02–0,21 s je Datei — **nicht** der Engpass.
- Echte Funktion, Punkt (47.14, 11.04), 12-h-Fenster: **10,3 s**, 12/12 Zeitpunkte für 8 von 9 Größen; zweiter Aufruf 0,0 s (Punkt-Fenster-Cache #2465 greift).
- Ergebnis: Störung war zeitweilig (DWD-seitig), zum Messzeitpunkt nicht mehr reproduzierbar.
- Nebenbefund geklärt: `cin_ml` = 0/12 ist gewollt — `_filtere_fuellwert` verwirft `<= -999.9` (Fehlwert bei ~46 % der Gitterpunkte, #1531); der Punkt liegt in diesem Bereich. Kein Defekt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/dwd.py:130` | `THUNDER_FETCH_DEADLINE_SECONDS = 150.0` (fest, einmal je Abruf gebildet) |
| `src/providers/dwd.py:70-75` | `TIMEOUT = 30.0`, `RETRY_ATTEMPTS = 5`, Backoff 2–60 s, retry nur bei 500/502/503/504, `ConnectError`, `ReadTimeout` |
| `src/providers/dwd.py:504` | `_request`: Timeout je Versuch = `min(TIMEOUT, Restzeit)` über `capped_timeout_or_raise` |
| `src/providers/dwd.py:553` | `_thunder_point`: ein Download je (Größe, Zeitschritt); Cache-Treffer vor Download |
| `src/providers/dwd.py:618` | `fetch_thunder_signals_named`: Schleife Zeitschritt → Größen (9 × bis zu 12 ≈ 108 Abrufe), Abbruch bei erschöpftem Budget |
| `src/providers/dwd.py:359` | `_PointWindowCache` (#2465), 512 URLs / 8 Fenster je URL |
| `src/providers/http.py:73` | `capped_timeout_or_raise`, `stop_at_deadline`, `make_deadline_before_hook` |
| `src/providers/thunder_enrichment.py` | Aufrufer (Anreicherung, Health-Journal) |
| `src/providers/dwd_eu.py:406` | Schwester-Quelle (ICON-EU) mit eigenem Budget — gleiche Bauart |

## Existing Patterns
- Festes, nicht rollendes Zeitbudget (Lehre #1448), Prüfung vor jedem Einzel-Call (#2302 S2).
- Reihenfolge der Größen = Ausfallreihenfolge bei Budget-Ende (`lpi`, `grau_gsp`, `cin_ml` vorn; #1531 AC-7).
- Auslegung von 150 s beruht auf 0,24 s/Abruf (Kommentar `dwd.py:120-130`); ein hängender Abruf kostet bis zu 30 s.
- Tests: `tests/tdd/test_dwd_thunder_signal_fetch.py`, `test_dwd_thunder_new_signals_fetch.py`, `test_dwd_eu_thunder_time_budget.py`, `tests/unit/test_dwd_thunder_raster_cache.py`, `tests/tdd/test_provider_request_deadline.py`.

## Dependencies
- Upstream: `opendata.dwd.de` (ICON-D2 GRIB2.bz2, jede Datei = ganzes Modellgebiet, kein Punkt-Query), `httpx`, `tenacity`, `rasterio`.
- Downstream: Trip-Briefings und Alarmläufe (Gewittersignale), Health-Journal (#2218), `/e2e-verify` Telegram/Mail-Live-Tests.

## Existing Specs
- `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md` — 9 Größen, Reihenfolge, Budget 150 s
- `docs/specs/modules/fix_2302_s2_dwd_zeitbudget.md` — Zeitbudget-Bausteine, Wanduhr-Tests
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md`
- Cache #2465: Commit `edfea482a` (Spec/Tests: `tests/unit/test_dwd_thunder_raster_cache.py`)

## Risks & Considerations
- Ursache der Störung nicht belegt (nur Messung aus dem Ticket, keine Server-Logs des DWD): DWD-Latenz/Drosselung ist die plausible Lesart; heute nicht mehr nachstellbar.
- Strukturelle Schwäche bleibt: ~108 sequentielle Downloads gegen 150 s Budget, ein hängender Abruf kostet bis 30 s (+ Retry bei ConnectError/ReadTimeout) — wenige Hänger leeren das Budget, und dank der Reihenfolge (je Zeitschritt alle Größen) fehlen dann alle späteren Stunden.
- Jede Änderung am Budget/Timeout berührt Spec #2302 S2 (Wanduhr-Tests) und #1531 (Ausfallreihenfolge) — Verhalten bei knappem Budget muss erhalten bleiben (best effort, wirft nie).
- Alle vier Kanäle sind betroffen (Gewittersignale in jedem Bericht); Alarme dürfen nicht langsamer werden.
- Mail-/Renderer-Dateien werden voraussichtlich nicht berührt (Renderer-Gate nicht erwartet).
