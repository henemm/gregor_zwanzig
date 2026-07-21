# ADR-0021: Gemeinsame `DeviationAlertEngine` für Trip- und künftige Compare-Alarme

- **Status:** Akzeptiert (PO-„go" 2026-07-09)
- **Datum:** 2026-07-09
- **Bezug:** GitHub-Issue #1168 (Scheibe 1/3, Epic #1095), Spec
  `docs/specs/_archive/modules/issue_1168_alert_engine_extract.md`, Architektur-Gegenüberstellung
  `docs/context/feat-1095-compare-alerts.md` (Abschnitt „Architektur-Gegenüberstellung
  Trip ↔ Compare"); verwandt [ADR-0011](0011-alert-render-single-backend-renderer.md)
  (kanonischer Alert-Renderer), [ADR-0017](0017-output-paket-konsolidierung.md)
  (`NotificationService` als einziger Versand-Orchestrierer); Folge-Issues #1169
  (Scheibe 2 — Compare-Anbindung, live seit 2026-07-09), #1170 (Scheibe 3 — Config-UI, offen)

## Kontext

Der Orts-Vergleich (Epic #1095) soll künftig eigene Abweichungs-Alarme auslösen können,
analog zu den bestehenden Trip-Alarmen (Issue #816 ff.). Der heutige
Deviation-Alert-Auswertungskern lebt vollständig in `TripAlertService`
(`src/services/trip_alert.py`) und liest an mehreren Stellen `trip.*`-Felder direkt
(Cooldown, Ruhezeiten, Alarmregeln, Kanäle). Eine Analyse des Kerns zeigt jedoch, dass
die eigentliche Entscheidungslogik — Change-Detection, Filter significant,
Filter-gegen-Melde-Gedächtnis, Severity-Bestimmung, Quiet-Hours (inkl.
Mitternachts-Wrap), Cooldown, Kanalwahl — bereits **location-generisch** ist: sie
operiert auf Wetterdaten-pro-Punkt + Konfigurationswerten, nicht auf `Trip`-,
`Stage`- oder `Waypoint`-Strukturen. Rendering (ADR-0011) und Versand (ADR-0017) sind
bereits als geteilte Services etabliert — nur der Auswertungskern selbst war noch nicht
herausgelöst.

## Entscheidung

Der Deviation-Alert-Auswertungskern wird in einen eigenständigen Shared-Service
extrahiert: `DeviationAlertEngine` (`src/services/deviation_alert_engine.py`), der auf
generischen DTOs operiert (`PointWeatherData`, `AlertEvaluationConfig`, beide in
`src/services/point_weather.py`) und **kein** `Trip`-Objekt kennt.
`TripAlertService` wird zum dünnen Adapter: er baut `AlertEvaluationConfig` aus
Trip-Feldern, wandelt `List[SegmentWeatherData]` verlustfrei über
`TripSegmentWeatherAdapter` in `List[PointWeatherData]`, ruft
`DeviationAlertEngine.evaluate(...)` auf und delegiert Rendering/Versand unverändert
weiter. Ein künftiger Compare-Adapter (Scheibe 2, #1169) baut dieselbe
`AlertEvaluationConfig` aus einem `ComparePreset` und ruft dieselbe Engine — ohne die
Auswertungslogik zu duplizieren.

Das Alert-Melde-Gedächtnis (`AlertStateService`, Issue #816) wird parallel auf einen
generischen `entity_id`-Parameter umgestellt (statt `trip_id`); das Dateipfad-Schema
`data/users/<user_id>/alert_state/<entity_id>.json` bleibt unverändert, sodass
bestehende `<trip_id>.json`-Dateien ohne Migration gültig bleiben.

Diese Scheibe (#1168) ist ein reiner Umbau ohne Verhaltensänderung: Trip-Alarme
verhalten sich danach bit-identisch. Die Compare-Anbindung selbst ist NICHT Teil
dieser Scheibe (Scheibe 2, #1169).

## Verworfene Alternativen

- **Separate Compare-Engine duplizieren** — verworfen: eine zweite,
  eigenständige Auswertungs-Engine für den Orts-Vergleich hätte Change-Detection,
  Filter-, Severity- und Quiet-Hours-/Cooldown-Logik dupliziert. Jede künftige
  Korrektur (z. B. an der Severity-Klassifikation oder der Mitternachts-Wrap-Logik)
  müsste dann an zwei Stellen synchron gehalten werden — ein bekanntes
  Divergenzrisiko (vgl. die bereits konsolidierten Renderer-/Versand-Schichten in
  ADR-0011/ADR-0017).
- **`TripAlertService` direkt um Compare-Fälle erweitern (Trip-Objekt optional
  machen)** — verworfen: hätte `Trip`-Kopplung tief in den Auswertungskern
  hineingezogen (z. B. `trip.display_config`-Backfill-Logik) und die Abgrenzung
  zwischen „location-generischem Kern" und „Trip-spezifischem Adapter" verwischt.
- **Nichts tun, bis Scheibe 2 (#1169) beginnt** — verworfen: die Extraktion selbst
  ist eine unabhängig verifizierbare Einheit (bit-identisches Trip-Verhalten als
  Hard-Gate) und reduziert das Risiko für Scheibe 2, da die Engine bereits gegen
  echte Trip-Alarm-Läufe (AC-1/AC-2/AC-4) verifiziert ist, bevor ein zweiter
  Consumer angeschlossen wird.

## Konsequenzen

- **Positiv:** Ein gemeinsames „Alarm-Gehirn" für Trip und künftigen Compare;
  Korrekturen an Severity/Quiet-Hours/Cooldown/Filter-Logik wirken künftig für beide
  Consumer gleichzeitig. `TripAlertService` wird spürbar dünner (Change-Detection,
  Filter-gegen-State und Severity-Bestimmung sind nicht mehr in `trip_alert.py`
  dupliziert).
- **Preis:** Ein interner Adapter (`_PointShim`/`_SegmentIdShim` in
  `deviation_alert_engine.py`) übersetzt zwischen dem generischen `PointWeatherData`
  und dem von `WeatherChangeDetectionService.detect_changes()` erwarteten
  Attribut-Shape (`.segment.segment_id`/`.start_time`/`.end_time`), damit
  `PointWeatherData` selbst frei von `TripSegment`-Kopplung bleibt. Trip-spezifische
  Detektor-Wahl (`_select_change_detector`, abhängig von `trip.display_config`) bleibt
  bewusst im Adapter — die Engine erhält den fertigen Detektor als Override-Parameter,
  statt die Weather-Tab-Aktivierungs-Nuancen selbst nachzubilden.
- **Folgepflichten:** Scheibe 2 (#1169, live seit 2026-07-09) hat den Compare-Adapter gebaut
  (`CompareAlertService`/`compare_alert.py`, eigener `AlertEvaluationConfig`-Builder mit
  hartkodierten Defaults, `compare_location_weather_source.py` als
  `LocationWeatherSource`-Implementierung) und den Orts-Vergleich als **zweiten, realisierten
  Consumer** an dieselbe Engine angeschlossen — siehe
  `docs/specs/_archive/modules/issue_1169_compare_alert_consumer.md`. Scheibe 3 (#1170, offen) ergänzt
  die Config-UI. Tageslimit (`alert_daily_limit`), Alert-Log und Radar-Onset-Pfad
  bleiben vorerst Trip-spezifisch im Adapter (siehe „Known Limitations" der Spec) —
  eine Verallgemeinerung dieser Bausteine ist separat zu betrachten, falls Compare
  sie ebenfalls benötigt.
