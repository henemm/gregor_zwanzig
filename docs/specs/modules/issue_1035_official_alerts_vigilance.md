---
entity_id: official_alerts_vigilance
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [compare, alerts, official-alerts, meteofrance]
---

# Official Alerts — Météo-France Vigilance (Wetterwarnungen)

## Approval

- [ ] Approved

## Purpose

Erste echte Quelle in der Official-Alerts-Registry (#1034): Météo-France Vigilance liefert
Wetterwarnungen (Gewitter, Sturmböen, extreme Hitze) auf Département-Ebene. **Leitszenario:**
Côte d'Azur (Var 83, Alpes-Maritimes 06, Bouches-du-Rhône 13); Korsika (2A/2B-Split) als
gleichrangig unterstützter Zweitfall über denselben landesweiten Département-Mapper. Höchste
Implementierungspriorität der drei Quellen-Slices (PO-Urlaub in ca. 2 Wochen, ab 2026-07-20).

## Source

- **File:** `src/services/official_alerts/vigilance.py`, `meteo_token_provider.py`,
  `department_mapper.py`
- **Identifier:** `VigilanceSource`

> Datenquelle: offizielle REST-API über `portail-api.meteofrance.fr`, OAuth2
> Client-Credentials-Flow, Endpoint `/vigilance/public/bulletin?lat=<lat>&lon=<lon>`,
> `timelaps[].max_colors[].phenomenon_max_color_id` (1=grün, 2=gelb, 3=orange, 4=rot).
> Lizenz Etalab 2.0 — Attribution im Mail-Footer erforderlich, sobald ein Vigilance-Badge
> angezeigt wird.

## Estimated Scope

- **LoC:** ~180
- **Files:** 5 (4 neu, 1 geändert — siehe Issue #1035 für exakte Liste)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py` (#1034) | Fundament | `OfficialAlertSource`-Protocol, Registry |
| `src/services/radar_service.py` (`_AROME_FR_*`) | Muster-Referenz | Frankreich-Bbox für `covers()` |
| `src/services/comparison_renderers.py::render_comparison_text` | Integration | Text-Renderer-Parität |
| Météo-France-Portal-Account (Betreiber-Aktion) | Voraussetzung | OAuth2-Zugangsdaten |

## Implementation Details

```python
class VigilanceSource:
    name = "meteofrance_vigilance"
    _FRANCE_BBOX = {"min_lat": 41.0, "max_lat": 51.5, "min_lon": -5.5, "max_lon": 10.0}
    _RELEVANT_PHENOMENA = {"thunderstorm", "wind_gust", "extreme_heat"}  # PO-Scope

    def covers(self, lat: float, lon: float) -> bool:
        return (self._FRANCE_BBOX["min_lat"] <= lat <= self._FRANCE_BBOX["max_lat"]
                and self._FRANCE_BBOX["min_lon"] <= lon <= self._FRANCE_BBOX["max_lon"])

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        token = get_meteofrance_token()  # None wenn ENV fehlt -> fail-soft
        if token is None:
            return []
        # Bulletin abrufen, phenomenon_max_color_id -> OfficialAlert.level mappen,
        # nur _RELEVANT_PHENOMENA beruecksichtigen
        ...
```

Zugangsdaten via ENV, fehlend → `fetch()` liefert `[]`, keine Exception, einmalig geloggte
Warnung (nicht bei jedem Aufruf, um Log-Spam zu vermeiden).

## Expected Behavior

- **Input:** Lat/Lon eines Ortes.
- **Output:** Liste von `OfficialAlert` mit `hazard` in {thunderstorm, wind_gust, extreme_heat}
  für gültige Vigilance-Warnungen des Départements; leer außerhalb Frankreichs, bei fehlenden
  Zugangsdaten oder bei API-Fehlern.
- **Side effects:** HTTP-Call gegen Météo-France-Portal (nur wenn `covers()` true).

## Acceptance Criteria

- **AC-1:** Given ein Ort mit Lat/Lon an der Côte d'Azur (Var, Alpes-Maritimes oder
  Bouches-du-Rhône) und eine aktuell gültige Vigilance-Warnung Stufe orange für "Gewitter", When
  die Compare-Mail für diesen Ort generiert wird, Then zeigt die Mail einen orangen Badge
  "Gewitter — Vigilance orange" für genau diesen Ort.
  - Test: echter API-Call gegen den Météo-France-Endpoint mit einem zum Testzeitpunkt bekannten
    Ort/Datum, kein Mock; Compare-Mail-HTML auf Badge-Vorhandensein und Farbe prüfen.

- **AC-2:** Given fehlende oder ungültige Zugangsdaten (ENV leer), When die Compare-Mail
  generiert wird, Then läuft der Versand normal durch, ohne Fehler und ohne Vigilance-Badge.
  - Test: ENV-Variablen für Zugangsdaten temporär entfernen, echten Compare-Lauf durchführen,
    prüfen dass Mail vollständig generiert wird und kein Vigilance-Badge erscheint.

- **AC-3:** Given ein Ort außerhalb Frankreichs (z. B. Österreich), When
  `get_official_alerts_for_location()` aufgerufen wird, Then wird `VigilanceSource.fetch()`
  nicht aufgerufen.
  - Test: `covers()` direkt mit österreichischen Koordinaten aufrufen und `False` erwarten;
    zusätzlich per Call-Counter/Log nachweisen, dass bei einem vollen
    `get_official_alerts_for_location()`-Lauf für einen österreichischen Ort kein HTTP-Call an
    die Vigilance-API erfolgt.

- **AC-4:** Given ein Ort auf Korsika (2A oder 2B), When die Compare-Mail generiert wird, Then
  funktioniert die Warnungs-Anzeige über denselben Département-Mapper und dieselbe
  `VigilanceSource`-Logik wie für Côte-d'Azur-Orte, ohne Sonderfall-Code.
  - Test: identischen Compare-Lauf wie AC-1, aber mit einem korsischen Ort, gleiche
    Code-Pfad-Abdeckung nachweisen (kein separater Korsika-Zweig im Diff).

## Known Limitations

- Nur die 3 vom PO explizit gescopten Phänomene (Gewitter, Sturmböen, extreme Hitze) — andere
  Vigilance-Kategorien (Glatteis, Schnee, Hochwasser, ...) werden ignoriert.
- Token-Caching ohne Persistenz über Prozess-Neustarts hinaus (In-Memory reicht für den
  Scheduler-Anwendungsfall).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016 (siehe #1034 für Details)
- **Rationale:** Fundament bereits entschieden; dieser Slice implementiert nur die erste konkrete
  Quelle nach dem etablierten Interface.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1035)
