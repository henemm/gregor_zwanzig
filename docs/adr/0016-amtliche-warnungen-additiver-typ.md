# ADR-0016: Amtliche Warnungen als additiver externer Alert-Typ

- **Status:** Akzeptiert
- **Datum:** 2026-07-06
- **Bezug:** GitHub-Epic #1033 (Slices #1034–#1037)

## Kontext

Im Orts-Vergleich sollen zusätzlich amtliche Warnungen von Behörden gezeigt werden — für
Frankreich konkret Météo-France Vigilance (Wetterwarnungen), Météo des forêts
(Waldbrand-Gefahrenstufe) und Präfektur-Betretungsverbote einzelner Wander-Massive. Das Projekt
hat bereits zwei etablierte, aber unterschiedliche Konzepte, die auf den ersten Blick verwandt
wirken:

1. **`WeatherProvider`-Protokoll** (`src/providers/base.py`) — liefert Vorhersage-Zeitreihen
   (Temperatur, Wind, Niederschlag) von Wetterdiensten wie GeoSphere/Open-Meteo.
2. **Δ-Abweichungs-Alerts** (ADR-0009, `src/services/trip_alert.py`) — melden, wenn der aktuelle
   Nowcast wesentlich vom letzten versendeten Briefing abweicht; explizit **keine** absoluten
   Schwellen.

Amtliche Warnungen sind fachlich weder das eine noch das andere: Sie sind eine **absolute,
extern vorgegebene Behörden-Einstufung** (z. B. "Vigilance orange"), keine selbst berechnete
Wetter-Metrik und kein Vergleich gegen einen eigenen Snapshot. Sie ohne Weiteres in eines der
beiden bestehenden Modelle zu pressen, würde beide Konzepte verwässern: `WeatherProvider`
erwartet eine Zeitreihe mit Wetterwerten, keine Kategorie-Einstufung; das Δ-Alert-Modell aus
ADR-0009 hätte keinen sinnvollen "letzten Snapshot", gegen den eine amtliche Stufe verglichen
werden könnte — die Behörde liefert bereits die fertige Einstufung, kein Rohsignal.

## Entscheidung

Amtliche Warnungen bekommen einen **eigenen, additiven Datentyp** `OfficialAlert`
(`src/services/official_alerts/models.py`) und ein **eigenes schlankes Quellen-Interface**
(`OfficialAlertSource`, Registry-Muster analog `src/providers/base.py`), getrennt von
`WeatherProvider` und vom Δ-Alert-Modell.

- Jede Quelle liefert für einen Lat/Lon-Punkt eine Liste von `OfficialAlert` (Level 1–4,
  Hazard-Typ, Label, Gültigkeitsfenster, Quellen-URL).
- Ein **Geo-Scope-Vorfilter** (`covers(lat, lon)`) je Quelle folgt dem bereits etablierten
  Bounding-Box-Muster aus `src/services/radar_service.py:26-49` — vermeidet unnötige Calls
  außerhalb des jeweiligen Geltungsbereichs.
- Jede Quelle wird **einzeln fail-soft** aufgerufen: Fehler einer Quelle (Auth, Netzwerk,
  Saison-Ende) dürfen die Compare-Mail niemals blockieren.
- Integration erfolgt **additiv** in `ComparisonEngine.run()` (neues Feld
  `LocationResult.official_alerts`) und im Compare-Mail-Renderer — bestehende Δ-Alert- und
  Wetter-Vorhersage-Pfade bleiben unverändert.

## Verworfene Alternativen

- **Amtliche Warnung als weiterer `WeatherProvider`** — verworfen: das Protokoll ist auf
  Zeitreihen-Vorhersagen zugeschnitten (`fetch_forecast() -> NormalizedTimeseries`), eine
  Kategorie-Einstufung passt strukturell nicht hinein; hätte künstliche Zeitreihen-Wrapper
  erzwungen.
- **Amtliche Warnung als Spezialfall des Δ-Alert-Modells (ADR-0009)** — verworfen: das
  Δ-Alert-Modell braucht einen gespeicherten Vergleichs-Snapshot (letztes Briefing); eine
  amtliche Einstufung hat keinen sinnvollen "letzten Wert", gegen den sie abweichen könnte — sie
  ist bereits die fertige, absolute Aussage der Behörde.
- **Direkt in `ComparisonResult`/`LocationResult` als lose Dict-Felder** — verworfen: kein
  Registry-Mechanismus, keine einheitliche Fail-soft-Behandlung pro Quelle, jede neue Quelle
  hätte Ad-hoc-Code statt eines wiederverwendbaren Interfaces erzwungen.

## Konsequenzen

- **Positiv:** Neue amtliche Warnquellen (auch außerhalb Frankreichs, auch für andere Kanäle wie
  das Trip-Briefing) docken an dieselbe Registry an, ohne bestehende Provider- oder
  Alert-Pfade zu berühren. Ausfall einer Quelle ist strukturell isoliert (try/except pro Quelle).
- **Negativ / Preis:** Ein drittes paralleles "Warn-ähnliches" Konzept neben `WeatherProvider`
  und Δ-Alerts — erhöht die Zahl der Konzepte, die ein neuer Entwickler kennen muss. Rechtfertigt
  sich dadurch, dass die drei Konzepte fachlich tatsächlich verschieden sind (Vorhersage vs.
  Abweichung vs. amtliche Einstufung).
- **Folgepflichten:** Neue amtliche Warnquellen implementieren `OfficialAlertSource` und
  registrieren sich in der Registry (`src/services/official_alerts/base.py`) — nicht als
  `WeatherProvider` und nicht im Δ-Alert-Pfad. Jede neue Quelle MUSS `covers()` fail-soft
  implementieren und `fetch()`-Fehler intern abfangen, damit die Fail-soft-Garantie
  systemweit gilt.
