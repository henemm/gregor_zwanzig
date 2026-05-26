# Context: issue-353-meteofrance-trend-400

## Request Summary

Der Mehrtages-Trend-Pfad (`_build_stage_trend`, Quelle `trend`) erzeugt im Normalbetrieb
eine ~19 % HTTP-400-Quote ausschließlich auf dem Météo-France-Endpoint (`/v1/meteofrance`,
AROME). Ursache: Für französische Ziele (z. B. GR20) wählt der Provider AROME (höchste
Auflösung), dessen nutzbarer Vorhersagehorizont kürzer ist als die angefragten zukünftigen
Etappen → Anfrage liegt jenseits des Modellzeitraums → 400. Folge: Lücken in der
Mehrtages-Vorschau für FR-Ziele, verschwendete Abrufe, Fehler-Rauschen in der Diagnose.

## Fehlerpfad (End-to-End)

```
trip_report_scheduler._build_stage_trend (über zukünftige Etappen iterierend)
  → _fetch_weather(segments)
    → SegmentWeatherService.fetch_segment_weather
      → OpenMeteoProvider.fetch_forecast(location, start, end)
        → select_model(lat, lon)  → AROME (meteofrance_arome) für FR-Gebiet
        → _request("/v1/meteofrance", params)  → 400 wenn end_date > AROME-Horizont
          → ProviderRequestError("openmeteo", "API error: 400 - ...")
```

## Related Files

| File | Relevanz |
|------|----------|
| `src/services/trip_report_scheduler.py:881` | `_build_stage_trend` — iteriert über `trip.get_future_stages(target_date)`, ruft pro Etappe `_fetch_weather`. try/except fängt Fehler aus `format_stage_summary` (warning + skip). |
| `src/services/trip_report_scheduler.py:666` | `_fetch_weather` — **fängt JEDE Provider-Exception** als `logger.error(...)` (Z.697) und hängt einen **Error-Placeholder** (`has_error=True`) an. Das ist die ERROR-Rauschquelle UND die Lücken-Quelle (has_error-Segment statt echter Daten). |
| `src/providers/openmeteo.py:705` | `fetch_forecast` — baut Forecast-Params, setzt `start_date`/`end_date`; **kein** `forecast_days`-Limit, **keine** Horizont-Klemmung pro Modell. |
| `src/providers/openmeteo.py:355` | `select_model` — wählt nach `REGIONAL_MODELS`-Prioritätsreihenfolge. AROME = Prio 1 für lat 38–53 / lon −8…10 (deckt ganz FR). |
| `src/providers/openmeteo.py:103` | `REGIONAL_MODELS` — Modell-Tabelle. Enthält bounds + grid_res + priority, aber **kein max-Horizont-Feld**. ECMWF (Prio 5) = globaler Fallback mit längstem Horizont. |
| `src/providers/openmeteo.py:431` | `_request` — wirft bei `raise_for_status()` `ProviderRequestError`. **400 ist nicht retryable** (nur 502/503/504, korrekt). |
| `src/providers/openmeteo.py:307` | `_find_fallback_model` — existierender Fallback-Mechanismus, aber nur für **fehlende Metriken**, nicht für Horizont-Überschreitung. |
| `docs/specs/modules/multi_day_trend.md` | Spec v3.0 (F3) des Trend-Algorithmus. |

## Existing Patterns

- **Provider-Fehler werden im Scheduler geschluckt** (`_fetch_weather`, WEATHER-04): Statt
  auslassen → `has_error=True`-Placeholder. Gedacht für den Hauptbericht (eine kaputte
  Etappe soll nicht den ganzen Report killen). Für den **Trend** ist das suboptimal:
  Der 400 ist hier *erwartbar* (Horizont), kein echter Fehler → falsches ERROR-Log-Level.
- **Modell-Fallback existiert** (`_find_fallback_model` + `_merge_fallback`), aber nur für
  Metrik-Verfügbarkeit (WEATHER-05a), nicht für Horizont.
- **Retry-Klassifikation** (`_is_retryable_error`): 400 bewusst nicht retrybar.
- **Pro-Metrik-Horizont (#342, `derive_horizon`/`visible_cols`)** ist NICHT der API-Modell-
  horizont, sondern Anzeige-Filter (today/tomorrow/day_after). **Nicht wiederverwendbar** für
  „auf Modellhorizont klemmen".

## Dependencies

- **Upstream (was der Trend nutzt):** `OpenMeteoProvider`, `SegmentWeatherService`,
  `CompactSummaryFormatter`, `trip.get_future_stages()`.
- **Downstream (was den Trend nutzt):** `generate_trip_report` (Z.380) packt `multi_day_trend`
  in den `TripForecastResult`; gerendert in E-Mail-/SMS-Report.

## Existing Specs

- `docs/specs/modules/multi_day_trend.md` (v3.0) — Trend-Algorithmus (F3).
- `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` — Pro-Metrik-Anzeige-Horizont
  (verwandt im Namen, anderes Konzept).

## Lösungsrichtungen (Detail-Abwägung → Phase 2)

| Option | Wirkung | Aufwand |
|--------|---------|---------|
| **A — Graceful skip + Log-Level** | 400 vom Trend-Pfad als „kein Datum verfügbar" behandeln statt `logger.error`; Etappe sauber überspringen. Behebt **Rauschen**, Lücke bleibt. | Klein |
| **B — Horizont klemmen** | Forecast-`end_date` vor dem Call auf Modellhorizont begrenzen → 400 entsteht gar nicht, Call gespart. Braucht **neue Modell→max-Tage-Tabelle**. Lücke bleibt für ferne Tage. | Mittel |
| **C — Modell-Fallback im Trend** | Bei Horizont-Überschreitung auf gröberes Modell mit längerem Horizont (ICON-EU/ECMWF) ausweichen → **keine Lücke**, Nutzer bekommt Trend-Daten (gröber, aber vorhanden). Beste UX. | Größer |

Issue empfiehlt A (primär) + B (optional). C ist Tech-Lead-Ergänzung (Nutzer-Lücke schließen).

### PO-Entscheidung (2026-05-25): **Option C — Modell-Fallback im Trend**

Für ferne Etappen bei FR-Zielen soll das System auf ein weiter reichendes (gröberes)
Modell ausweichen statt eine Lücke zu lassen. Der Wanderer bekommt für die Planung eine
— wenn auch ungenauere — Vorschau statt gar nichts. Implizit enthalten: das ERROR-Rauschen
muss ebenfalls weg (der Fallback ist der Normalfall, kein Fehler).

## Empirischer Befund (2026-05-25, echte Diagnose-Calls — KEINE Mocks)

**Die Issue-Hypothese „AROME-Horizont kürzer als andere Modelle" ist WIDERLEGT.**

Test (Korsika 42,9; volle hourly-Variablenliste wie `fetch_forecast`):

| Endpoint | +14 Tage | +16 Tage | Reichweite |
|----------|----------|----------|------------|
| `/v1/meteofrance` | 200 OK | 400 | bis today+15 |
| `/v1/dwd-icon` | 200 OK | 400 | bis today+15 |
| `/v1/ecmwf` (global!) | 200 OK | 400 | bis today+15 |
| `/v1/gfs` (global) | 200 OK | 400 | bis today+15 |

400-Grund (maschinen-lesbar): `Parameter 'start_date' is out of allowed range from
<today-92> to <today+15>`. Die Grenze ist **endpoint-übergreifend identisch** — Open-Meteo
validiert `start_date` gegen ein globales Fenster `[today-92, today+15]`, **bevor** das
modellspezifische Processing greift.

### Konsequenzen

1. **Der Fehler ist NICHT FR-/AROME-spezifisch.** Jedes Ziel mit einer Trend-Etappe
   >15 Tage in der Zukunft löst den 400 aus. „Nur meteofrance" im #338-Messfenster war ein
   **Stichproben-Artefakt**: nur die langen FR-Trips (GR20, 14 Etappen) hatten so ferne
   Etappen; kürzere DE/AT-Trips blieben unter der Grenze.
2. **Modell-Fallback (Option C) ist technisch UNMÖGLICH** für die betroffenen Etappen:
   kein Open-Meteo-Modell — auch kein gröberes, globales — reicht weiter als ~16 Tage.
   Jenseits davon existieren schlicht keine Daten. Eine Tour-Etappe >2 Wochen entfernt ist
   grundsätzlich nicht vorhersagbar (physikalische Grenze numerischer Wettervorhersage).
   → **PO-Entscheidung „gröbere Vorschau statt Lücke" lässt sich für diese Etappen nicht
   erfüllen.** Neuvorlage an PO nötig.
3. Realistischer Lösungsraum reduziert sich auf:
   - **A** — Etappe >15 Tage sauber als „Vorhersage reicht noch nicht so weit" behandeln
     (statt `logger.error` + has_error-Placeholder), Rauschen weg.
   - **B** — `end_date` vor dem Call auf `today+15` klemmen → 400 entsteht gar nicht, Call
     gespart; für eine Etappe komplett jenseits +15 bleibt es trotzdem ein Skip.
   - A und B sind **kombinierbar** und ergänzen sich.

## Finales Lösungsdesign (PO-bestätigt 2026-05-26: „ferne Etappe weglassen")

**Proaktive Horizont-Vorprüfung im Trend-Pfad — minimaler, klar abgegrenzter Eingriff.**

- Neue Provider-Konstante `OPENMETEO_MAX_FORECAST_DAYS = 15` (empirisch bestätigt,
  endpoint-übergreifend; Begründung im Code-Kommentar).
- Reine, deterministisch testbare Hilfsfunktion (KEINE Mocks nötig), z. B.
  `is_within_forecast_horizon(stage_date, reference_date) -> bool`.
- In `_build_stage_trend`: pro Etappe **vor** `_fetch_weather` prüfen — liegt `stage.date`
  jenseits `today + OPENMETEO_MAX_FORECAST_DAYS`, dann `continue` (kein API-Call, keine
  Trend-Zeile, `logger.debug` statt `logger.error`).

**Warum nur im Trend-Pfad (nicht im Provider):** Der Hauptbericht-Pfad
(`generate_trip_report` → `_fetch_weather`) fragt nur heute/morgen ab, nie >15 Tage — er
löst den 400 nie aus und braucht den `has_error`-Placeholder (WEATHER-04) unverändert.
Der Trend ist der einzige Pfad mit fernen Abfragen. Eingriff dort = kein Risiko für den
Hauptbericht, kleinster LoC-Footprint.

**Wirkung:** kein verschwendeter Call, kein 400, kein ERROR-Rauschen, keine Zeile für
nicht-vorhersagbare Etappen. Etappen ≤ today+15 unverändert. Sobald die Tour näher rückt,
fällt eine Etappe automatisch wieder in den Horizont.

## Risks & Considerations

- **AROME-Horizont ist nicht im Code dokumentiert.** Open-Meteo `/v1/meteofrance` bündelt
  AROME-HD + ARPEGE; der nutzbare Tage-Horizont muss in Phase 2 empirisch/aus Open-Meteo-Doku
  bestätigt werden (für Option B kritisch).
- **KEINE Mocks** (CLAUDE.md): Tests müssen echte API-Calls oder echte Fixtures (#263
  FixtureProvider) nutzen. 400-Reproduktion braucht ein FR-Ziel mit fernem Datum.
- **Backward-Compat:** Hauptbericht-Pfad nutzt `_fetch_weather` ebenfalls — Log-Level-/
  Fehler-Handling-Änderung darf den `has_error`-Placeholder im Hauptbericht NICHT brechen
  (WEATHER-04). Trend-spezifische Behandlung sauber abgrenzen.
- **Datenverlust-Regel:** rein lese-/Abruf-seitiger Bug, keine Persistenz-Struktur betroffen.
