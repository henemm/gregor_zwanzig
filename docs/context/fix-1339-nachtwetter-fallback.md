# Context + Analyse: Fix #1339 — Zieldaten-Ausfall wird still durch Segment-Startwetter ersetzt

## Request Summary

Schlägt der Wetterabruf fürs Nachtlager (Zielort) fehl, liefert `fetch_night_weather()` heute
einen Fallback auf die Zeitreihe der letzten Etappe (Segment-Start-Geografie) statt `None`. Weil
die Lückenerkennung (`compute_has_gap`) nur auf `None`/leere Daten reagiert, sieht sie diesen
Fallback als „vollständige Daten" — alle vier Versandkanäle geben eine positive Entwarnung fürs
Nachtlager ab, obwohl dort in Wahrheit keine Zieldaten vorlagen. Sicherheitsrelevant: die
Fehl-Entwarnung betrifft ausgerechnet die Nachtlager-Wetterlage.

## Bestätigter Befund (Code gegengeprüft)

Die im Issue genannte Fundstelle (`trip_report_scheduler.py:1282-1287`) ist veraltet — seit Fix
#1315 (Vorschau=Versand für die Nacht-Sektion) wurde die Beschaffung in eine **geteilte** Funktion
ausgelagert. Der Bug sitzt jetzt hier:

`src/services/segment_weather.py:395-455`, konkret der `except`-Block `443-455`:

```python
try:
    active_provider = provider or get_provider("openmeteo")
    service = SegmentWeatherService(active_provider)
    night_data = service.fetch_segment_weather(night_segment, enrich_ensemble=False)
    return night_data.timeseries
except Exception as e:
    logger.warning(f"Failed to fetch night weather: {e}")
    # Fallback: use last segment's timeseries (evening hours only)
    if last_segment.timeseries and last_segment.timeseries.data:
        return last_segment.timeseries   # <- BUG: Segment-Start-Geografie, nicht Zielort
    return None
```

**Fix:** die beiden Fallback-Zeilen (452-454) entfernen, der `except`-Block liefert nur noch
`None`.

## Zwei Aufrufer, BEIDE betroffen (geteilte Funktion, kein Duplikat)

| Aufrufer | Datei:Zeile | Pfad |
|---|---|---|
| `TripReportSchedulerService._fetch_night_weather()` | `trip_report_scheduler.py:1234-1247` | reiner Delegator seit #1315, ruft `segment_weather.fetch_night_weather()` |
| `preview_service.py:217` | `preview_service.py` | Web-Vorschau, ruft dieselbe Funktion mit optionalem `provider` (Demo-Modus: `FixtureProvider`, #483) |

Der eigentliche Versandpfad (`trip_report_scheduler.py:873`) ruft `_fetch_night_weather()` auf,
deren Rückgabewert direkt in `compute_has_gap()` (`notification_service.py:212-240`) einfließt.

## Warum die Lückenerkennung dann automatisch korrekt greift

`build_day_window_points()` (`src/output/renderers/day_window.py:105-168`) dokumentiert bereits
selbst: „`night_weather=None` -> fail-soft" (Zeile 119) — die Stunden des Anzeige-Fensters, die
sonst aus `night_weather` stammen (`DAY_WINDOW_END_HOUR` **ausschließlich** aus `night_weather`,
Zeile 117), fehlen dann in den gerenderten Punkten. `compute_has_gap()` prüft
`expected.issubset(rendered)` — fehlen Fenster-Stunden, wird `has_gap=True`. Der Mechanismus
existiert also bereits vollständig und korrekt (Fix #1331/#1334, Option C: „Erkennung == Anzeige
per Konstruktion") — er bekommt nur aktuell im Fehlerfall die falsche Eingabe.

**Konsequenz:** Dieser Fix braucht keine Änderung an der Lückenerkennung oder an einem der vier
Renderer — nur die Rückgabe von `fetch_night_weather()` muss ehrlich sein.

## Related Files

| File | Relevanz |
|------|----------|
| `src/services/segment_weather.py:395-455` | `fetch_night_weather()` — die Fix-Stelle |
| `src/services/trip_report_scheduler.py:873,1234-1247` | Versandpfad-Aufrufer (Delegator) |
| `src/services/preview_service.py:217` | Vorschau-Aufrufer |
| `src/services/notification_service.py:212-240` | `compute_has_gap()` — liest `night_weather`, unverändert |
| `src/output/renderers/day_window.py:105-168` | `build_day_window_points()` — fail-soft bei `None` bereits vorhanden |

## Existing Patterns

- **Fail-soft auf `None` statt Fallback-Daten** ist im Projekt der etablierte Umgang mit
  Teilausfällen (vgl. `day_window.py:119` für `night_weather=None`, generell „keine Aussage" statt
  erfundener Werte, siehe Memory `reference_gewitter_rohwerte_kommen_nicht_von_openmeteo` und
  ähnliche Fälle). Der hier zu entfernende Fallback ist die Ausnahme, nicht die Regel.
- **Demo-Vertrag (#483):** `fetch_night_weather(provider=...)` — im Demo-/Vorschau-Modus wird ein
  `FixtureProvider` durchgereicht, kein Live-Call. Der Fix darf diesen Vertrag nicht berühren (der
  Fallback-Zweig betrifft nur echte Exceptions, nicht den Demo-Pfad).

## Dependencies

- **Upstream:** `SegmentWeatherService.fetch_segment_weather()` (kann werfen: Netz-/
  Kontingentfehler, real belegt durch #1329).
- **Downstream:** `compute_has_gap()` (unverändert, reagiert korrekt auf `None`),
  `build_day_window_points()` (unverändert, fail-soft bei `None` bereits vorhanden), alle vier
  Renderer (unverändert — sie lesen nur `has_gap`, nicht `night_weather` direkt für die
  Lücken-Anzeige).
- **Kein Vorschau/Versand-Divergenz-Risiko:** beide Aufrufer nutzen dieselbe Funktion, der Fix
  wirkt identisch auf beide.

## Existing Specs

- Keine dedizierte Modul-Spec für `fetch_night_weather()` selbst; die Herkunfts-Dokumentation
  liegt in den Commit-Messages/Kommentaren zu #1315 (Konsolidierung) und #1331/#1334
  (Lückenerkennung).

## Risks & Considerations

- **Sicherheitsrelevante Richtung:** Die Fehl-Entwarnung (falsches Wetter als sicher ausgegeben)
  ist die Richtung, die laut Projektregel zwingend eine Mutations-Gegenprobe braucht — wird der
  Fallback wieder eingebaut, muss mindestens ein Test rot werden.
- **Regressionsgefahr: GERING, verifiziert.** Vier Tests referenzieren den Fallback
  (`test_notification_service.py::test_non_covering_night_weather_fallback_*`,
  `test_day_window_gap_detection.py::test_night_weather_covering_only_pre_arrival_hours_is_a_gap`)
  — sie bauen aber alle eine SYNTHETISCHE `NormalizedTimeseries` per Hand und rufen
  `fetch_night_weather()` NICHT auf; sie testen nur, dass `compute_has_gap()` einen
  nicht-abdeckenden Zeitraum generisch als Lücke erkennt (Verteidigung in der Tiefe). Diese Tests
  bleiben unverändert gültig und grün. Kein Test im Repo ruft `fetch_night_weather()` auf und
  erwartet dabei den Fallback-Rückgabewert (`test_preview_night_block.py:166` ruft die Funktion
  zwar direkt auf, aber nur den Erfolgspfad mit einem funktionierenden `_SpyProvider`).
- **Kein Netzausfall provozierbar in Unit-Tests ohne Mock-Theater:** Der Test muss die Exception im
  `try`-Block auslösen, ohne echte Netzwerkabhängigkeit — am saubersten über einen Provider-Double,
  der bei `fetch_segment_weather()` bewusst wirft (kein Mock-Theater, weil es reales
  Fehlerverhalten eines Providers simuliert, kein zurückgespiegeltes Sollverhalten).
