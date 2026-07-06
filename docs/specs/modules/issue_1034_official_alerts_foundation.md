---
entity_id: official_alerts_foundation
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [compare, alerts, official-alerts]
---

# Official Alerts — Fundament (Modell, Registry, Compare-Mail-Integration)

## Approval

- [ ] Approved

## Purpose

Fundament für amtliche Alerts im Orts-Vergleich: Datentyp `OfficialAlert`, ein schlankes
Quellen-Interface mit Geo-Scope-Vorfilter und Registry, sowie die additive Verdrahtung in
`ComparisonEngine`/`LocationResult` und der Compare-Mail-Renderer. Noch keine echte Datenquelle
(folgt in #1035); die Registry ist zunächst leer, Plumbing wird mit einer Test-Fake-Quelle
bewiesen.

## Source

- **File:** `src/services/official_alerts/models.py`, `src/services/official_alerts/base.py`
- **Identifier:** `OfficialAlert`, `OfficialAlertSource`, `get_official_alerts_for_location()`

## Estimated Scope

- **LoC:** ~220
- **Files:** 6 (4 neu: `__init__.py`, `models.py`, `base.py`; 2 geändert: `src/app/user.py`,
  `src/services/comparison_engine.py`, `src/output/renderers/email/compare_html.py` — insgesamt
  4 neu + 3 geändert = 7 Dateien, siehe GitHub-Issue #1034 für exakte Liste)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/base.py` | Muster-Referenz | Registry-Pattern (Protocol + register/get) |
| `src/services/radar_service.py` | Muster-Referenz | Geo-Wirkungsrahmen (Bounding-Box + Geltungsbereichs-Prädikat) |
| `src/app/user.py::LocationResult` | Integration | additives Feld `official_alerts` |
| `src/services/comparison_engine.py::ComparisonEngine.run()` | Integration | Aufrufstelle pro Location |
| `src/output/renderers/email/compare_html.py::render_compare_html()` | Integration | Renderer-Block |

## Implementation Details

```python
# src/services/official_alerts/models.py
@dataclass(frozen=True)
class OfficialAlert:
    source: str            # z.B. "meteofrance_vigilance"
    hazard: str            # z.B. "thunderstorm", "wind_gust", "extreme_heat"
    level: int              # 1=gruen ... 4=rot
    label: str               # deutschsprachiges Anzeige-Label
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    url: str | None = None
    region_label: str | None = None


# src/services/official_alerts/base.py
class OfficialAlertSource(Protocol):
    @property
    def name(self) -> str: ...
    def covers(self, lat: float, lon: float) -> bool: ...
    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]: ...

_REGISTERED_SOURCES: list[OfficialAlertSource] = []

def register_official_alert_source(source: OfficialAlertSource) -> None:
    _REGISTERED_SOURCES.append(source)

def get_official_alerts_for_location(lat: float, lon: float) -> list[OfficialAlert]:
    results: list[OfficialAlert] = []
    for source in _REGISTERED_SOURCES:
        if not source.covers(lat, lon):
            continue
        try:
            results.extend(source.fetch(lat, lon))
        except Exception:
            logger.warning("official_alerts: %s fetch failed", source.name, exc_info=True)
    return results
```

`ComparisonEngine.run()` ruft pro `LocationResult` additiv
`get_official_alerts_for_location(loc.lat, loc.lon)` auf und hängt das Ergebnis an. Der Renderer
`render_compare_html()` zeigt bei leerer Liste identisches HTML wie heute (Regressionsschutz).

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes.
- **Output:** Liste von `OfficialAlert` (leer, wenn keine Quelle zuständig ist oder alle
  zuständigen Quellen fehlschlagen).
- **Side effects:** keine (reine Lese-Aufrufe gegen externe Quellen, kein Schreiben).

## Acceptance Criteria

- **AC-1:** Given eine `CompareSubscription` mit ≥3 Orten und leerer Official-Alert-Registry,
  When die Compare-Mail gerendert wird, Then ist das HTML byte-identisch zum aktuellen Stand.
  - Test: Snapshot-Vergleich der gerenderten Compare-Mail vor/nach diesem Slice bei leerer
    Registry — kein Dateiinhalt-Check, sondern Vergleich des tatsächlich generierten HTML-Strings.

- **AC-2:** Given eine Test-Fake-Quelle ist in der Registry registriert und liefert für einen der
  verglichenen Orte einen `OfficialAlert(level=3, hazard="thunderstorm", ...)`, When die
  Compare-Mail gerendert wird, Then erscheint für genau diesen Ort ein farbcodierter Badge mit
  dem Label der Warnung, für die anderen Orte nicht.
  - Test: Fake-Quelle über `register_official_alert_source()` registrieren, echten
    `ComparisonEngine.run()` + `render_compare_html()` Aufruf durchführen, HTML-Ausgabe auf
    Vorhandensein des Badges für den betroffenen Ort und Abwesenheit bei den anderen prüfen.

- **AC-3:** Given eine Test-Fake-Quelle wirft beim `fetch()`-Aufruf eine Exception, When
  `ComparisonEngine.run()` läuft, Then wird die Compare-Mail trotzdem vollständig generiert
  (kein Absturz, kein fehlender Ort) und die betroffene Location hat eine leere
  `official_alerts`-Liste.
  - Test: Fake-Quelle mit `fetch()` das eine Exception wirft, echten `ComparisonEngine.run()`
    Aufruf durchführen, prüfen dass alle Locations im Ergebnis vorhanden sind und keine Exception
    nach außen dringt.

## Known Limitations

- Registry ist in diesem Slice leer (keine echte Quelle) — reale Wirkung erst ab #1035.
- Text-Renderer-Parität (`comparison_renderers.py`) folgt erst mit #1035, sobald es echten Inhalt
  zum Rendern gibt.

## Hinweis (Scope-Korrektur 2026-07-06)

Primäres Leitszenario des Gesamt-Epics ist nun ein Côte-d'Azur-Urlaub (Var, Alpes-Maritimes,
Bouches-du-Rhône), GR20/Korsika ist Zweitfall. Dieses Fundament-Slice ist davon unberührt — die
Registry/das `covers()`-Muster war von Anfang an ortsagnostisch (Lat/Lon-Input, keine
GR20-Bezüge). Details: `docs/features/epic-1033-compare-official-alerts.md`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016
- **Rationale:** Amtliche Warnungen sind ein eigenes fachliches Konzept (absolute
  Behörden-Einstufung), weder `WeatherProvider` noch Δ-Abweichungs-Alert (ADR-0009) — daher
  eigener additiver Datentyp und eigenes Registry-Interface statt Wiederverwendung bestehender
  Alert-/Provider-Modelle.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1034)
