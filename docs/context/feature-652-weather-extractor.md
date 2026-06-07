# Context: feature-652-weather-extractor

## Request Summary
Teil 3/6 von Epic #639 (Ad-Hoc Telegram Dialog): eine schlanke **Datenschicht**, die
gezielt Wetter-Metriken aus vorhandenen Snapshots zieht — ohne vollen Report-Build.
Liefert (a) eine vertikale Timeline pro Wegpunkt (Naismith-Ankunftszeit), (b) einen
stündlichen Single-Metric-Drilldown und (c) einen sauberen Leer-/Fehlerzustand.
Reine Daten, **keine** Telegram-Formatierung (die liegt in #653/#654).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_snapshot.py` | Persistiert/lädt Snapshots. **Speichert heute NUR `aggregated` (SegmentWeatherSummary) pro Segment, `timeseries=None` nach load.** Muss additiv um stündliche Punkte erweitert werden (für AC-2). |
| `src/app/models.py` | DTOs: `SegmentWeatherData`, `SegmentWeatherSummary`, `TripSegment`, `ForecastDataPoint`, `NormalizedTimeseries`, `ThunderLevel`. |
| `src/core/segment_builder.py` | Naismith-Segmentbau: jedes Segment hat `start_time`/`end_time` (UTC) + start/end-Point mit Höhe → Wegpunkt-Ankunftszeiten. |
| `src/services/trip_report_scheduler.py:512` | Ruft `WeatherSnapshotService().save(...)` nach Report-Versand mit frisch gefetchtem `segment_weather` (timeseries befüllt). |
| `src/services/trip_alert.py:143,239` | Nutzt `snapshot.save`/`load` für Alert-Vergleich — verlässt sich **nur auf `aggregated`**. Darf durch Erweiterung NICHT brechen. |
| `src/services/trip_command_processor.py` | Bestehender Channel-agnostischer Command-Prozessor (lesende Abfragen kommen in #651). |

## Existing Patterns
- **Snapshot pro Trip:** `data/users/<uid>/snapshots/<trip_id>.json`, ein Snapshot = ein Report-Tag (`target_date`), Liste von Segmenten.
- **Enum-Serialisierung:** `_serialize_summary`/`_deserialize_summary` mappen Enums auf `.name`/zurück; None-Werte werden ausgelassen.
- **User-Scoping:** `WeatherSnapshotService(user_id=...)` → `get_snapshots_dir(user_id)`. Mandantentrennung Pflicht.
- **Segment = Wegpunkt-Intervall:** `end_point`+`end_time` eines Segments ≙ Ankunft am nächsten Wegpunkt (Naismith).

## Dependencies
- Upstream: `WeatherSnapshotService.load`, Modelle, `app.loader` (snapshots dir).
- Downstream: #653 (Timeline-Formatierung), #654 (Drilldown-Formatierung) konsumieren die DTOs dieser Schicht.

## Existing Specs
- `docs/specs/modules/weather_snapshot.md` (v1.0) — Snapshot-Persistenz, muss um stündliche Reihe ergänzt werden.

## Kernbefund (architekturprägend)
Der heutige Snapshot speichert **nur aggregierte Pro-Segment-Werte**, keine stündliche
Reihe. AC-1 (Timeline pro Wegpunkt) lässt sich aus den aggregierten Werten + Naismith-
Zeiten direkt bedienen. AC-2 (stündlicher Drilldown) braucht echte Stundenwerte, die es
nirgends persistiert gibt. **Tech-Lead-Entscheidung:** Snapshot-Format **additiv** um eine
kompakte stündliche Reihe pro Segment erweitern (`hourly[]` mit `ts` + metrik-relevanten
Feldern, begrenzt auf das Segment-Zeitfenster). `load` bleibt rückwärtskompatibel (alte
Snapshots ohne `hourly` → Drilldown liefert Leerzustand statt Crash). Der aggregierte
Pfad bleibt unangetastet → Alert-Vergleich unberührt.

## Risks & Considerations
- **Alert-Regression:** `trip_alert` darf nicht brechen — `aggregated` bleibt unverändert, `hourly` ist rein additiv.
- **Snapshot-Größe:** Stundenwerte nur fürs Segment-Zeitfenster persistieren (nicht ganze Tagesreihe ×N Segmente dupliziert).
- **Daten-Schema:** Snapshot ist ein abgeleiteter Cache (wird bei Datumsänderung gelöscht), kein Nutzer-Kernbestand → geringeres Verlust-Risiko, aber Rückwärtskompatibilität beim Laden zwingend.
- **Drilldown-Fenster:** Snapshot deckt nur den Wander-Zeitraum des Report-Tags ab; „nächste 6–12 h" liefert nur, was vorhanden ist (Teil-Reihe statt Crash).
- **LoC:** Snapshot-Erweiterung + Extractor-Modul + DTOs + mock-freie Tests könnten das 250-LoC-Limit knapp überschreiten → ggf. PO-Freigabe für höheres Budget oder Split.
