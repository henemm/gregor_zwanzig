---
entity_id: issue_1036_meteo_forets_source
type: feature
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
workflow: feature-1036-meteo-forets
tags: [compare, alerts, official-alerts, meteofrance, wildfire]
---

# Météo des forêts Source — Waldbrand-Gefahrenstufe (Slice 3)

## Approval

- [ ] Approved

## Purpose

Dritte Datenquelle für die in #1034 gebaute Official-Alerts-Registry: `MeteoForetsSource` ruft die
amtliche Météo-France-„Météo des forêts"-API ab und liefert die Waldbrand-Gefahrenstufe (1–4) pro
Département — nur während der Saison Juni–September, in der die Quelle überhaupt Werte liefert.
Relevant für den PO-Urlaub an der Côte d'Azur ab 2026-07-20 (Départements Var, Alpes-Maritimes,
Bouches-du-Rhône), Korsika gleichrangig über denselben generischen Département-Mapper abgedeckt.

## Source

- **File:** `src/services/official_alerts/meteo_forets.py`
- **Identifier:** `class MeteoForetsSource`

> **Schicht:** Python-Core/Domain-Backend (`src/services/`).

## Estimated Scope

- **LoC:** ~90–120 src-LoC (kein Zentroid-Tabellen-Overhead — `department_mapper.py` wird
  wiederverwendet, nicht dupliziert)
- **Files:** 1 neu (`meteo_forets.py`), 1 geändert (`official_alerts/__init__.py` — Registrierung)
- **Effort:** small–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::OfficialAlertSource` | Protocol (bindend, #1034) | `MeteoForetsSource` implementiert `name`/`covers()`/`fetch()` strukturell |
| `src/services/official_alerts/base.py::register_official_alert_source` | Registry (bindend, #1034) | Lazy-Registration bei Modul-Import (`__init__.py`) |
| `src/services/official_alerts/models.py::OfficialAlert` | Datentyp (bindend, #1034) | `fetch()` befüllt bestehende Felder, keine Schema-Änderung |
| `src/services/official_alerts/department_mapper.py::lookup_department` | Code-Wiederverwendung (#1035) | Gleicher Mapper wie Vigilance, keine Duplizierung |
| `src/services/radar_service.py:38-42` (`_AROME_FR_LAT_MIN/MAX/LON_MIN/MAX`) | Code-Wiederverwendung | Frankreich-Bbox als `covers()`-Vorfilter (identisch zu Vigilance) |
| `httpx` | Bestehende Dependency | HTTP-GET gegen `public-api.meteofrance.fr` |
| `GZ_METEOFRANCE_APIKEY` (ENV) | Zugangsdaten | Gleicher Header/gleiche ENV wie Vigilance (ein Schlüssel für alle Portal-APIs, Epic-Kommentar 2026-07-06) |
| `src/services/comparison_engine.py:184-190` | Integration | Ruft `get_official_alerts_for_location()` bereits generisch auf — **keine Codeänderung** |
| `src/output/renderers/comparison.py:418-420` | Integration | Text-Warnzeile bereits generisch über `alert.label` — **keine Codeänderung** |
| `src/output/renderers/email/compare_html.py:144-169` | Integration | HTML-Badge bereits generisch über `alert.level`/`alert.label` — **keine Codeänderung** |

**Korrektur zum Issue-Text (#1036):** Weder `src/services/comparison_renderers.py` (existiert
nicht) noch eine Änderung an `base.py` sind nötig. Registrierung erfolgt analog Vigilance in
`official_alerts/__init__.py`; beide Renderer sind bereits vollständig generisch über das
`OfficialAlert`-Modell und benötigen keine Anpassung für eine dritte Quelle.

## Implementation Details

**Verifizierter Endpunkt** (Epic #1033, Kommentar 2026-07-06, live getestet HTTP 200):
`GET https://public-api.meteofrance.fr/public/DPMeteoForets/v1/carte/departement/encours?format=json&echeance=J1&id-departement={dep}`,
Auth via HTTP-Header `apikey: <GZ_METEOFRANCE_APIKEY>` (kein OAuth2, kein Token-Provider — trotz
Issue-Text-Erwähnung eines OAuth2-Client-Wiedergebrauchs aus #1035 ist dies **nicht nötig**, da
Vigilance ebenfalls nur einen statischen API-Key-Header nutzt).

Beispiel-Antwort (Var, 2026-07-05):
```json
[{"reference_time":"2026-07-05T14:50:04Z","dep_code":"83","niveau_j1":"3","dep_nom":"Var"}]
```
`niveau_j1` ist die Gefahrenstufe 1–4 als String — muss zu `int` gecastet werden, mit Fail-soft
bei nicht-parsbarem Wert (Alert einfach überspringen, kein Crash, analog Vigilance
`phenomenon_max_color_id`-Handling).

**Saison-Gate:** Anders als Vigilance liefert diese Quelle nur Juni–September Werte. Damit
`covers()` ohne Zeit-Mocks testbar bleibt, wird die Monats-Prüfung als reine Funktion extrahiert:

```python
_SEASON_MONTHS = {6, 7, 8, 9}

def _is_season(month: int) -> bool:
    return month in _SEASON_MONTHS

class MeteoForetsSource:
    name = "meteo_forets"

    def covers(self, lat: float, lon: float) -> bool:
        if not _is_season(datetime.now().month):
            return False
        return (_AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
                and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX)

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
            _warn_once_missing_key()
            return []
        dept = lookup_department(lat, lon)
        if dept is None:
            return []
        data = _get_cached_departement(dept)  # Modul-Level-Cache PRO Département, TTL 300s/60s
        if data is None:
            return []
        return _extract_alert(data, dept)
```

`_is_season(month: int) -> bool` wird direkt mit echten Integer-Werten getestet (kein Zeit-Mock
nötig, siehe AC-2) — der `covers()`-Aufruf selbst nutzt `datetime.now().month` unverändert zur
Laufzeit.

**Caching pro Département:** Anders als Vigilance (ein nationaler Call bedient alle Départements)
ist dieser Endpunkt bereits département-scoped (`id-departement={dep}` im Query-Parameter) — ein
nationaler Cache ist strukturell nicht möglich. Modul-Level-Cache als `Dict[str, dict]` mit
Timestamp pro Département, TTL 300s (Erfolg) / 60s (Fehlschlag), analog Vigilance-Konvention.
Konservativ genug, da die Quelle laut Issue nur ~1x/Tag (ca. 17 Uhr) aktualisiert.

**Kein Mindest-Schwellwert:** Anders als Vigilance (nur ab Farbstufe ≥2 sichtbar) liefert
`fetch()` **jede** Gefahrenstufe 1–4 als Badge — Waldbrand-Gefahr ist bereits bei Stufe 1
("gering") eine für Wanderer relevante Information, nicht wie Vigilance-Grün eine
Nicht-Warnung. Diese Design-Entscheidung ist Teil der Freigabe dieser Spec.

**Label-Format** (exakt wie im Issue-Beispiel AC-1): `f"Waldbrand-Gefahr — Stufe {level}"`.

Registrierung: `official_alerts/__init__.py` importiert `meteo_forets` und ruft
`register_official_alert_source(MeteoForetsSource())` beim Modul-Import auf (Lazy-Registration,
analog Vigilance-Zeile dort).

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes (via `get_official_alerts_for_location()`).
- **Output:** Liste von `OfficialAlert` mit `source="meteo_forets"`, `hazard="wildfire_risk"`,
  `level` (1–4), `label=f"Waldbrand-Gefahr — Stufe {level}"` — leer, wenn außerhalb der Saison
  (Oktober–Mai), die ENV fehlt, der Ort außerhalb Frankreichs liegt, oder die API nicht erreichbar
  ist.
- **Side effects:** höchstens ein HTTP-GET pro Département pro Cache-TTL-Fenster (300s Erfolg /
  60s Fehlschlag) gegen die Météo-France-API; kein Schreiben, keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given aktuelles Datum liegt in Juni–September und ein Ort im Var (83) mit
  Gefahrenstufe 4, When die Compare-Mail generiert wird, Then zeigt die Mail für diesen Ort einen
  roten Badge "Waldbrand-Gefahr — Stufe 4".
  - Test: Echter API-Call gegen die echte Météo-France-API (kein Mock), heutiges Datum liegt
    bereits in der Saison (Juli). Da sich die tatsächlich gemeldete Gefahrenstufe täglich ändern
    kann, MUSS der Test tolerant sein: Er iteriert über die Côte-d'Azur-/Korsika-Départements aus
    `DEPARTMENT_CENTROIDS`, findet das tatsächlich zum Testzeitpunkt gemeldete Level, und prüft
    den strukturellen Vertrag (Level ∈ {1,2,3,4}, `hazard="wildfire_risk"`, Label-Format korrekt)
    sowie — bei tatsächlich vorliegendem Level 4 — den konkreten roten Badge im gerenderten
    HTML-Output (`compare_html.py`-Farbe `G_DANGER` für Level 4). Liegt zum Testzeitpunkt kein
    Level-4-Département vor, beweist der Test stattdessen den Datenstruktur-Vertrag für ein
    beliebiges tatsächlich gemeldetes Level (kein hartes "muss Level 4 sein").

- **AC-2:** Given aktuelles Datum liegt außerhalb Juni–September (z.B. Januar), When
  `get_official_alerts_for_location()` für einen französischen Ort aufgerufen wird, Then liefert
  `MeteoForetsSource.covers()` `False` und es wird kein Waldbrand-Badge angezeigt.
  - Test: Da das heutige Testdatum (2026-07-07) mitten in der Saison liegt und Zeit-Mocks laut
    Projektkonvention verboten sind, wird die extrahierte reine Funktion `_is_season(month: int)`
    direkt mit echten Integer-Werten getestet: `_is_season(1)` (Januar) == `False`,
    `_is_season(7)` (Juli) == `True`, sowie alle 12 Monate strukturell gegen `{6,7,8,9}` geprüft.
    Zusätzlich beweist ein Live-Aufruf `covers()` heute (Juli) == Frankreich-Bbox-Ergebnis (reale
    Laufzeit-Integration der Funktion, kein Mock der Systemzeit nötig).

- **AC-3:** Given die Datenquelle ist zum Abfragezeitpunkt nicht erreichbar (Netzwerkfehler),
  When die Compare-Mail generiert wird, Then läuft der Versand normal durch ohne Waldbrand-Badge
  für den betroffenen Ort (fail-soft).
  - Test: Echter `ComparisonEngine.run()`-Aufruf mit temporär entfernter/leerer
    `GZ_METEOFRANCE_APIKEY`-ENV-Variable (realer Fehlerpfad, kein Netzwerk-Mock) für einen Ort mit
    `covers()==True`; prüfen, dass das Ergebnis vollständig ist, `official_alerts` für diesen Ort
    leer bleibt, und `fetch()` keine Exception wirft.

## Known Limitations

- Kein Mindest-Schwellwert: jede Stufe 1–4 erscheint als Badge (bewusste Abweichung von Vigilance,
  siehe Implementation Details) — falls das im Betrieb zu viel „Grün-Rauschen" erzeugt, wäre ein
  Schwellwert ein separates Folge-Issue, kein Teil dieser Spec.
- Département-Mapper-Näherung (Nearest-Centroid) identisch zu Vigilance — an Grenzen sind seltene
  Fehlnachbarn möglich.
- Kein nationaler Bulk-Call möglich (Endpunkt ist bereits département-scoped) — bei N verglichenen
  Orten in unterschiedlichen Départements entsprechend N HTTP-Calls pro Cache-Fenster (kein
  Overhead gegenüber der API-Struktur selbst, aber mehr als Vigilance).
- Etalab-2.0-Lizenz-Attribution im Mail-Footer (im Epic #1033 als Risiko genannt) ist bereits bei
  #1035 (Vigilance) nicht umgesetzt worden und wird auch in diesem Slice nicht nachgeholt (Scope-
  Konsistenz mit #1035) — Folge-Issue nach Abschluss dieses Slices vorgesehen.
- `echeance=J1` (nächster Tag) wird abgefragt, `J2` nicht — ausreichend für die ACs dieses Slices.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec folgt vollständig dem in #1034/ADR-0016 und #1035 bereits etablierten
  Registry-/Protocol-Muster (`OfficialAlertSource`, `register_official_alert_source()`) und
  implementiert lediglich eine weitere konkrete Quelle innerhalb dieses Vertrags — keine neue
  Architektur-Entscheidung nötig.

## Changelog

- 2026-07-07: Initial spec created (Epic #1033, Issue #1036, Slice 3 nach #1034-Fundament und
  #1035-Vigilance).
