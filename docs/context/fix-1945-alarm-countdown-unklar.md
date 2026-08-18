# Context: fix-1945-alarm-countdown-unklar (#1945 „Alarm unklar")

## Request Summary
Nutzer erhielt zwei Radar-Nowcast-Alarme (15:52 und 17:07, 75 Min auseinander) mit demselben
Countdown-Wert "8". Root Cause: `_NOWCAST_HORIZON_MIN` in `src/services/radar_service.py` deckelt
den Suchhorizont künstlich auf 60 Minuten, obwohl die GeoSphere-INCA-API (Endpunkt
`nowcast-v1-15min-1km`) live bis zu 180 Minuten Vorschau im 15-Min-Raster liefert. Der Scheduler
prüft alle 15 Min, immer ~8 Min vor dem nächsten Rasterpunkt — der Alarm feuert fast immer erst
beim NÄCHSTEN Rasterpunkt, daher praktisch immer ≈8 Minuten Countdown.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/radar_service.py:62` | `_NOWCAST_HORIZON_MIN = 60` → wird zu `180` |
| `src/services/radar_service.py:514-536` (`_derive_result`) | Sucht ersten nassen Frame im Horizont-Fenster |
| `tests/tdd/test_radar_alert_follows_ortstag.py:412-436` | Hartcodierte Annahme Horizont==60, Fern-Fall 90 Min |
| `tests/tdd/test_starkregen_kurzfristhinweis.py:338-346` | Hartcodierte Annahme Horizont==60, Fern-Fall 90 Min |

## Existing Patterns
Zwei-Cooldown-Architektur (Trip-Scope + segment-lokaler Guard) funktioniert bereits korrekt und
ist NICHT Teil dieses Fixes. Segment-Auswahl (`resolve_current_segment()`) und ETA-Modell
(Naismith-Pace) sind bereits korrekt verdrahtet, keine Änderung nötig.

## Dependencies
- Upstream: GeoSphere-INCA-Provider (`src/providers/geosphere.py`), Scheduler-Cron
  (`internal/scheduler/scheduler.go`, Takt `7,22,37,52 * * * *`).
- Downstream: `trip_alert.py` (Horizont-Guard nutzt denselben Alias `NOWCAST_HORIZON_MIN`).

## Existing Specs
- `docs/specs/modules/fix_1945_nowcast_horizon.md` (diese Spec)
- `docs/specs/modules/rework_1467_s4b_entdopplung.md` — Ereignis-Identität (nicht betroffen)

## Risks & Considerations
- Reine Konstanten-Änderung, aber zwei Bestandstests brechen ohne Anpassung ihres Fern-Fall-Offsets
  (90 → >180 Min), da eine reine Zahlenänderung im Assert die Testsemantik kippen würde.
- Scope bewusst klein gehalten — Format/Rendering (#1948), Frühwarnung (#1493) und amtliche
  Warnungen (#1929) sind explizit ausgeschlossen und gehören anderen, bereits vergebenen Tickets.
- Ursprünglicher Worktree wurde durch fremden Cleanup-Lauf gelöscht; dieses Dokument ist eine
  inhaltsgleiche Rekonstruktion im neuen Worktree `replicated-cuddling-sphinx`.
