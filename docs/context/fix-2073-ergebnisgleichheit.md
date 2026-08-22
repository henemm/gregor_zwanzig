# Context: fix-2073-ergebnisgleichheit (Issue #2073, Scheibe 1)

## Request Summary

`resolve_stage_track_km()` gibt auf, sobald **mehr als eine** GPX-Datei innerhalb der Toleranz auf
die Wegpunkte einer Etappe passt. Geprüft wird damit die **Anzahl der Dateien**, nicht ob die
Kandidaten zu **verschiedenen Kilometerwerten** führen. Scheibe 1 stellt die Regel auf
Ergebnisgleichheit um: liefern alle Kandidaten praktisch dieselbe Wegstrecke, darf die Auflösung
sich entscheiden; nur bei wirklich abweichenden Ergebnissen bleibt `None`.

Scheibe 2 (Sichtbarkeit des stillen Fehlschlags) ist **nicht** Teil dieses Workflows — PO-Entscheid
2026-08-22: nach der KHW-Tour.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/track_resolution.py:59-98` | `resolve_stage_track_km()` — die zu ändernde Regel (`:92-95` bricht bei zweitem Treffer ab) |
| `src/services/track_resolution.py:38-56` | `_match_track()` — Vollständigkeitsregel (AC-12), bleibt unverändert |
| `src/services/track_resolution.py:109-178` | `backfill_stage_distances()` — Aufrufer, Read-Modify-Write via `save_trip` |
| `tests/tdd/test_track_resolution_legacy_trip.py` | 11 Tests; `test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis` bewacht heute die alte Regel |
| `tests/fixtures/data_root/users/default/gpx/` | 4 versionierte GR221-GPX (Tag 1–4), Basis aller Fixtures |
| `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` | Quelle von AC-11/AC-12 und der 10-m-Schwelle |
| `src/core/gpx_parser.py:137-159` | `_extract_points()` — `distance_from_start_km` kumuliert ab Track-Anfang, `round(..., 4)` |
| `src/app/models.py:364,382` | `GPXPoint.distance_from_start_km` (float, Default `0.0`), `GPXTrack.points` |

## Existing Patterns

- **Alles oder nichts je Track** (`_match_track`): ein einziger Wegpunkt > 10 m abseits verwirft den
  ganzen Kandidaten. Diese Regel ist unstrittig und bleibt.
- **Fail-soft**: jeder Fehler in `backfill_stage_distances` lässt den Trip unverändert — eine
  fehlende Kilometerangabe ist ein Schönheitsfehler, ein ausgefallener Alarm nicht.
- **Prozess-Sperre** `_failed_lookups`: erfolglose Suchen werden je `(user_id, trip_id, stage_id)`
  gemerkt, damit nicht jeder Alarmlauf den ganzen GPX-Bestand neu parst.
- **Deterministische Reihenfolge**: `sorted(directory.glob("*.gpx"))` — die Kandidatenliste ist
  reproduzierbar, eine Auswahl daraus ist kein Zufall.

## Dependencies

- **Upstream:** `core.gpx_parser.parse_gpx`, `utils.geo.haversine_km`, `app.loader.get_data_dir` /
  `save_trip`.
- **Downstream:** `TripAlertService._resolve_alert_segment` (`trip_alert.py:1165-1168`) und
  `TripReportSchedulerService._convert_trip_to_segments` (`trip_report_scheduler.py:1983-1990`).
  Von dort über `TripSegment.distance_measured` → `renderers/alert/project.py:244,359` →
  `renderers/alert/segments.py::format_alert_location()`, das bei `km_measured=True` `km A-B`
  statt `Segment N` zeigt. Betrifft #2036 (Ortsangabe) und #2042 (Ankunftszeiten).

## Existing Specs

- `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` — **AC-11** (Eindeutigkeit),
  **AC-12** (Vollständigkeit), Abschnitt „Festgelegte Schwellenwerte" (10 m Zuordnungstoleranz,
  Rundung der Anzeige auf **ganze Kilometer**). AC-11 kennt die Möglichkeit gleicher Ergebnisse
  noch nicht — genau das ist die Lücke von #2073.

## Messung am Produktivbestand (2026-08-22)

Gemessen mit dem echten GPX-Bestand `/var/lib/gregor/users/henning/gpx/` (20 Dateien) gegen die
Etappen-Wegpunkte der Produktivtrips „GR221 Mallorca" (4 Etappen) und „KHW 403" (13 Etappen).
Verfahren identisch zu `_match_track`: je Wegpunkt der nächstgelegene Trackpunkt, Toleranz 10 m.

### Befund 1 — die Ticket-Prämisse trifft in einem Punkt nicht zu

Das Ticket nennt die zwei getrennten Aufzeichnungen von Mallorca Tag 2 als Fall, den ein reiner
Prüfsummen-Vergleich weiterhin verwerfen würde. **Gemessen passt die zweite Aufzeichnung gar nicht
auf die Wegpunkte:** ihr schlechtester Wegpunkt liegt **111,1 m** ab und wird bereits von der
Vollständigkeitsregel (AC-12) ausgesiebt, bevor die Eindeutigkeitsregel überhaupt greift.

| Etappe | Treffer ≤ 10 m | nächstbester verworfener Kandidat |
|---|---|---|
| Mallorca Tag 1 | **2** (Original + `test.gpx`, beide 0,0 m) | 4.672,6 m (Tag 2) |
| Mallorca Tag 2 | 1 (0,0 m) | **111,1 m** (zweite Aufzeichnung vom 2026-02-14) |
| Mallorca Tag 3 | 1 (0,0 m) | 8.780,3 m |
| Mallorca Tag 4 | 1 (0,0 m) | 6.088,6 m |
| KHW 403, alle 13 Etappen | je 1 (0,0 m) | mindestens **4.732,6 m** |

### Befund 2 — der real auftretende Mehrdeutigkeitsfall ist die byte-identische Dublette

Mallorca Tag 1 ist die einzige gemessene Etappe mit zwei Treffern: das Original und `test.gpx`
(byte-identische Kopie, 62.893 Bytes, gleiche md5-Größe). Beide liefern **identische** km-Werte:

```
2026-01-17_..._Tag 1_ von Valldemossa nach Deià.gpx   km = [0.0, 2.9345, 6.1364, 9.6067]
test.gpx                                              km = [0.0, 2.9345, 6.1364, 9.6067]
-> maximale Abweichung: 0,0 m  (Etappenspanne 9,61 km)
```

Nach heutiger Regel fällt Mallorca Tag 1 damit auf `Segment N` zurück, obwohl es nichts zu raten
gibt. Das ist der Fall, den Scheibe 1 auflösen muss.

### Befund 3 — die Trennschärfe ist dreifach belegt

| Größenordnung | Beispiel | max. km-Abweichung zwischen Kandidaten |
|---|---|---|
| identisches Ergebnis | Dublette Mallorca Tag 1 | **0,0 m** |
| dieselbe Strecke, andere Aufzeichnung | Mallorca Tag 2, 2026-01-17 vs. 2026-02-14 | **bis 144 m** (9,390 vs. 9,246 km) |
| andere Etappe | jede Nachbaretappe | **Kilometer** |

Zwischen 0 m und 144 m liegen mehr als eine Größenordnung Luft. Eine Schwelle in der Größenordnung
der bereits festgelegten Zuordnungstoleranz (10 m) trennt sicher.

### Wirkung auf die laufende Tour

**KHW 403 gewinnt durch Scheibe 1 heute keine Etappe** — alle 13 Etappen haben seit der
Dublettenlöschung aus #2070 genau einen Treffer. Der Fix ist dort Vorsorge: eine erneut hochgeladene
Kopie eines KHW-Tracks würde die Etappe künftig nicht mehr ausfallen lassen. Unmittelbar wirksam ist
er für „GR221 Mallorca" Tag 1.

## Risks & Considerations

- **Der bewachende Test kippt.** `test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis` kopiert
  dieselbe Fixture-Datei zweimal und erwartet `None`. Genau dieses Verhalten wird abgeschafft. Der
  Test muss auf zwei Kandidaten mit **wirklich abweichenden** Ergebnissen umgestellt werden, sonst
  verliert AC-11 seinen Wächter ersatzlos. Die Regel darf nicht stillschweigend entfallen — nur ihr
  Auslöser ändert sich.
- **Vollständige Schleife statt Früh-Abbruch.** Für den Ergebnisvergleich müssen alle Kandidaten
  gesammelt werden; der heutige `return None` bei zwei Treffern (`:94-95`) entfällt. Der Alarmlauf
  hat eine Zeitobergrenze (Kommentar bei `_failed_lookups`), der Bestand umfasst 20 Dateien — im
  gemessenen Fall parst die Schleife ohnehin fast alle, der Mehraufwand ist begrenzt.
- **Mehr als zwei Kandidaten.** Passen drei Dateien, von denen zwei gleich und eine abweichend ist,
  muss `None` herauskommen. Ergebnisgleichheit muss also für **alle** Kandidaten gelten, nicht nur
  für ein Paar.
- **Welcher Kandidat gewinnt?** Bei Ergebnisgleichheit ist die Wahl fachlich beliebig, aber sie darf
  nicht zufällig sein — `sorted(...)` gibt eine stabile Reihenfolge vor.
- **Relative Schwelle wäre die schlechtere Wahl.** 1 % einer 9,6-km-Etappe sind 96 m und würden
  echte Wegunterschiede durchwinken; bei einer 1-km-Etappe wären es 10 m. Die Größe, um die es hier
  geht, ist ein Ortsabstand, keine Proportion.
- **Keine Schema-Änderung.** Scheibe 1 fasst weder Datenmodell noch Persistenz an; der
  Rückschreibweg (`save_trip`, Read-Modify-Write) bleibt unberührt.
- **`test.gpx` bleibt liegen.** Der im Ticket genannte Aufräum-Rest wird durch Scheibe 1
  gegenstandslos, aber nicht gelöscht — Produktivdaten des PO werden nicht angefasst.
