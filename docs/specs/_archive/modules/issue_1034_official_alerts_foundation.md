---
entity_id: official_alerts_foundation
type: module
created: 2026-07-06
updated: 2026-07-06
status: implemented
version: "1.2"
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

- **LoC:** ~110–140 src-LoC (Limit 250 — Puffer)
- **Files:** 6 (3 neu: `src/services/official_alerts/{__init__,models,base}.py`; 3 geändert:
  `src/app/user.py`, `src/services/comparison_engine.py`,
  `src/output/renderers/email/compare_html.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/base.py` | Muster-Referenz | Registry-Pattern (Protocol + register/get) |
| `src/services/radar_service.py` | Muster-Referenz | Geo-Wirkungsrahmen (Bounding-Box + Geltungsbereichs-Prädikat) |
| `src/app/user.py::LocationResult` (Zeile 147) | Integration | additives Feld `official_alerts: list[OfficialAlert] = field(default_factory=list)` (transient, keine Persistenz betroffen) |
| `src/services/comparison_engine.py::ComparisonEngine.run()` | Integration | Anreicherung NUR im Erfolgszweig (Zeile 180); Fehlerzweige (Zeile 70, Zeile 201) behalten den Default `[]` |
| `src/output/renderers/email/compare_html.py::render_compare_html()` | Integration | neue `_render_official_alerts_block()`, Slot bei Zeile 646 hinter `warnings_html` (Zeile 597), vor `matrix_html` (Zeile 599) |
| `src/output/renderers/email/design_tokens.py` (Zeile 25–27) | Farb-Referenz | `G_SUCCESS`/`G_WARNING`/`G_DANGER` für Level-Farbcodierung, keine neuen Tokens |

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
        # Name VOR dem try-Block capturen: `source.name` kann selbst werfen
        # (z.B. defekte Quellen-Implementierung) — ein ungeschuetzter Zugriff
        # im except-Handler wuerde die zweite Exception ungefangen propagieren.
        try:
            source_name = str(source.name)
        except Exception:
            source_name = repr(source.__class__.__name__)
        try:
            if not source.covers(lat, lon):
                continue
            results.extend(source.fetch(lat, lon))
        except Exception:
            logger.warning("official_alerts: %s fetch failed", source_name, exc_info=True)
    return results
```

`ComparisonEngine.run()` ruft pro `LocationResult` additiv
`get_official_alerts_for_location(loc.lat, loc.lon)` auf — **nur im Erfolgszweig** (Zeile 180,
nach erfolgreichem `fetch_forecast_for_location`); die beiden Fehlerzweige (Zeile 70: Provider
liefert `error`; Zeile 201: Exception) bauen `LocationResult` ohne diesen Aufruf, `official_alerts`
bleibt beim Feld-Default `[]`. Der Renderer `render_compare_html()` zeigt bei leerer Liste
identisches HTML wie heute (Regressionsschutz).

### Renderer-Constraints (hart, PFLICHT)

- `_render_official_alerts_block()` MUSS ausschließlich `<div>`/`<span>` erzeugen — **kein
  `<table>`**. `email_spec_validator.py` erwartet in der Compare-Mail exakt 2 `<table>`-Tags
  (Vergleichstabellen); ein zusätzliches `<table>` im neuen Block lässt den Validator fehlschlagen.
- Der Block MUSS im Dokumentfluss **nach** der ersten Vergleichstabellen-Position eingehängt
  werden (Slot bei `compare_html.py:646`, hinter `warnings_html`, vor `matrix_html`) — der
  Validator greift die erste `<table>` im HTML als Vergleichstabelle; ein Block davor würde diese
  Zuordnung verfälschen.
- Bei leerer Alert-Liste liefert `_render_official_alerts_block()` einen leeren String
  (identisches Muster wie `warnings_html` bei leerer `warnings`-Liste, `compare_html.py:597`)
  → dies ist der strukturelle Beweis für AC-1 (byte-identisches HTML).
- Level-Farb-Mapping ausschließlich über bestehende Tokens (`design_tokens.py:25-27`, keine neuen
  Tokens): Level 1–2 → `G_SUCCESS`, Level 3 → `G_WARNING`, Level 4 → `G_DANGER`.

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes.
- **Output:** Liste von `OfficialAlert` (leer, wenn keine Quelle zuständig ist oder alle
  zuständigen Quellen fehlschlagen).
- **Side effects:** keine (reine Lese-Aufrufe gegen externe Quellen, kein Schreiben).

## Acceptance Criteria

- **AC-1:** Given eine `CompareSubscription` mit ≥3 Orten und leerer Official-Alert-Registry,
  When die Compare-Mail gerendert wird, Then ist das HTML byte-identisch zum aktuellen Stand
  (der neue Alert-Block liefert bei leerer Liste einen leeren String, analog zum
  `warnings_html`-Muster in `compare_html.py:597`).
  - Test: Snapshot-Vergleich der gerenderten Compare-Mail vor/nach diesem Slice bei leerer
    Registry — kein Dateiinhalt-Check, sondern Vergleich des tatsächlich generierten HTML-Strings.

- **AC-2:** Given eine Test-Fake-Quelle ist in der Registry registriert und liefert für einen der
  verglichenen Orte einen `OfficialAlert(level=3, hazard="thunderstorm", ...)`, When die
  Compare-Mail gerendert wird, Then erscheint für genau diesen Ort ein farbcodierter Badge
  (div/span-basiert, kein `<table>`; Level 3 → `G_WARNING`-Token) mit dem Label der Warnung, im
  Dokumentfluss direkt VOR der Vergleichsmatrix (`matrix-table`) an der Position des bestehenden
  Warn-Banner-Slots (konsistent mit den Implementation Details), für die anderen Orte nicht.
  Die Anzahl der `<table>`-Tags ist identisch zur Baseline ohne registrierte Quellen — der Block
  fügt keine Tabelle hinzu. (Korrigiert mit PO-Freigabe 2026-07-06: der frühere Wortlaut „exakt 2
  Tabellen" entstammte dem seit #460 veralteten Validator-Vertrag, siehe Issue #1046.)
  - Test: Fake-Quelle über `register_official_alert_source()` registrieren, echten
    `ComparisonEngine.run()` + `render_compare_html()` Aufruf durchführen, HTML-Ausgabe auf
    Vorhandensein des Badges für den betroffenen Ort und Abwesenheit bei den anderen prüfen; dabei
    verifizieren, dass die `<table>`-Anzahl exakt der Baseline-Ausgabe ohne Alerts entspricht
    (Badge fügt keine Tabelle hinzu) und der Badge-Block im Dokument VOR der Vergleichsmatrix
    (`matrix-table`) liegt. (Positions-Wortlaut 2026-07-06 korrigiert: „nach der Matrix" war ein
    Übertragungsfehler aus der veralteten Validator-Analyse; maßgeblich ist der in den
    Implementation Details spezifizierte Slot vor der Matrix — für den Validator irrelevant, da
    der Block kein `<table>` ist.)

- **AC-3:** Given eine Test-Fake-Quelle wirft beim `fetch()`-Aufruf eine Exception, When
  `ComparisonEngine.run()` läuft, Then wird die Compare-Mail trotzdem vollständig generiert
  (kein Absturz, kein fehlender Ort) und die betroffene Location hat eine leere
  `official_alerts`-Liste (Fehler wird pro Quelle in `get_official_alerts_for_location()`
  abgefangen, nicht in `ComparisonEngine`).
  - Test: Fake-Quelle mit `fetch()` das eine Exception wirft, echten `ComparisonEngine.run()`
    Aufruf durchführen, prüfen dass alle Locations im Ergebnis vorhanden sind und keine Exception
    nach außen dringt.

## Known Limitations

- Registry ist in diesem Slice leer (keine echte Quelle) — reale Wirkung erst ab #1035.
- Text-Renderer-Parität (`render_comparison_text`, `src/output/renderers/comparison.py:331`)
  folgt erst mit #1035, sobald es echten Inhalt zum Rendern gibt.

## Out of Scope

- **Text-Renderer-Parität:** `render_comparison_text()` (`src/output/renderers/comparison.py:331`)
  bleibt in diesem Slice unangetastet — folgt mit #1035, sobald echte Quellen Inhalt liefern.
- **JSON-Ausgabe von `api/routers/compare.py`:** `official_alerts` wird NICHT in die JSON-Response
  aufgenommen. Epic-Scope ist Mail-only; der Go-native `/api/compare/run`
  (`internal/compare`) ist ohnehin eine separate Engine — Teil-Sichtbarkeit nur in einem der beiden
  Pfade wäre inkonsistent.
- **Echte Datenquellen:** folgen in #1035–#1037 (z. B. Météo-France Vigilance).
- **Config-Checkbox** (an/aus je Nutzer): folgt in #1040.

## Hinweis (Scope-Korrektur 2026-07-06)

Primäres Leitszenario des Gesamt-Epics ist nun ein Côte-d'Azur-Urlaub (Var, Alpes-Maritimes,
Bouches-du-Rhône), GR20/Korsika ist Zweitfall. Dieses Fundament-Slice ist davon unberührt — die
Registry/das `covers()`-Muster war von Anfang an ortsagnostisch (Lat/Lon-Input, keine
GR20-Bezüge). Details: `docs/features/epic-1033-compare-official-alerts.md`.

## Implementation Notes

- **Kein Kreis-Import:** `src/services/official_alerts/` importiert ausschließlich Typen aus
  `src/app/user.py` — niemals aus `src/services/comparison_engine.py` (Import-Richtung bleibt
  `comparison_engine.py` → `official_alerts`, nicht umgekehrt).
- **Fail-soft ausschließlich in `get_official_alerts_for_location()`:** try/except pro Quelle
  innerhalb der Registry-Funktion, nicht in `ComparisonEngine`. Die Funktion wirft nie —
  `ComparisonEngine.run()` ruft sie ungeschützt auf.
- **Renderer-Commit-Gate #811:** `renderer_mail_gate.py` matcht auch
  `src/output/renderers/email/compare_html.py`. Ein Commit dieser Datei verlangt zwingend
  vorher (a) einen grünen Lauf von `tests/tdd/test_issue_811_mode_matrix.py` und (b) einen
  frischen `briefing_mail_validator.py`-Nachweis — bekanntes mechanisches Gate-Verhalten
  (bezieht sich fachlich auf Trip-Briefing-Modi, greift aber pfadbasiert auch hier), kein Bug.
  Im Implementierungs-/Commit-Ablauf einplanen.
- **TDD-Reihenfolge:** AC-1 (byte-identisch bei leerer Registry) → AC-3 (Fail-soft bei werfender
  Fake-Quelle) → AC-2 (farbcodierter Badge). Implementierungsreihenfolge: `models.py` →
  `base.py`/Registry → Engine-Wiring (`comparison_engine.py`) → Renderer-Block
  (`compare_html.py`).
- **Kein Mock-Missbrauch:** Die Test-Fake-Quelle ist ein echtes, über
  `register_official_alert_source()` registriertes Objekt im echten Codepfad (Seam analog zum
  Fake-Radar-Muster) — kein `Mock()`/`patch()`.
- **Mandanten-Pflicht:** Wo die Tests nutzerbezogen sind (z. B. `CompareSubscription`-Fixtures),
  mit zwei verschiedenen Nutzern testen — kein Cross-User-Leck.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016
- **Rationale:** Amtliche Warnungen sind ein eigenes fachliches Konzept (absolute
  Behörden-Einstufung), weder `WeatherProvider` noch Δ-Abweichungs-Alert (ADR-0009) — daher
  eigener additiver Datentyp und eigenes Registry-Interface statt Wiederverwendung bestehender
  Alert-/Provider-Modelle.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1034)
- 2026-07-06: Spec nach Analyse-Phase präzisiert — Datei-Liste korrigiert (6 statt 7, keine
  `comparison_renderers.py`), harte Renderer-Constraints (div/span statt `<table>`, Slot nach
  Vergleichstabelle) als AC-Bestandteil ergänzt, Out-of-Scope-Abschnitt hinzugefügt,
  Implementation Notes (Kreis-Import-Verbot, Fail-soft-Ort, Renderer-Gate #811, TDD-Reihenfolge,
  Mandanten-Pflicht) ergänzt. Keine neuen ACs, keine inhaltliche Änderung der drei bestehenden.
- 2026-07-06: F004 (Adversary R2): name-Capture vor try — das Pseudocode-Beispiel in Implementation
  Details griff im except-Handler ungeschützt auf `source.name` zu; eine werfende `name`-Property
  hätte diese zweite Exception ungefangen propagiert (Widerspruch zur Fail-soft-Garantie in AC-3).
  Fix: `source_name` wird vor dem eigentlichen try-Block in einem eigenen Mini-try/except
  abgesichert erfasst und im Warning-Log verwendet. ACs unverändert.
- 2026-07-06: Status auf `implemented` gesetzt — Adversary-Verdict VERIFIED, AC-1/AC-2/AC-3 grün.
  Zwei Nebenbefunde als Folge-Issues erfasst (kein Rückbezug auf diese drei ACs): #1046
  (Validator-Vertrag der Compare-Mail seit #460 veraltet, Formulierung „exakt 2 Tabellen" bereits
  in AC-2 korrigiert) und #1048 (Politur F003/F005). Details:
  `docs/features/epic-1033-compare-official-alerts.md`.
