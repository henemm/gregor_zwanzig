# Context + Analyse: Amtliche Alerts Slice 3 — Météo des forêts (#1036)

## Request Summary
Dritte Quelle in der Official-Alerts-Registry (nach #1034 Fundament, #1035 Vigilance):
Waldbrand-Gefahrenstufe (1–4) pro Département, nur relevant Juni–September. Analog
zu `VigilanceSource`, gleiches Registry-/Fail-soft-Pattern, gleicher Département-Mapper.

## Related Files
| File | Relevanz |
|------|----------|
| `src/services/official_alerts/vigilance.py` | 1:1-Vorbild für Struktur, Caching, Fail-soft, Logging |
| `src/services/official_alerts/base.py` | `OfficialAlertSource`-Protocol, Registry (`covers`/`fetch`), keine Änderung nötig |
| `src/services/official_alerts/__init__.py` | **Hier** (nicht `base.py` wie im Issue-Text!) erfolgt die Registrierung neuer Quellen — Import + `register_official_alert_source(MeteoForetsSource())` ergänzen |
| `src/services/official_alerts/department_mapper.py` | `lookup_department(lat, lon) -> Optional[str]` — direkt wiederverwendbar, keine Änderung |
| `src/services/official_alerts/models.py` | `OfficialAlert`-Dataclass — keine Änderung, `hazard="wildfire_risk"` ist neuer Wert im bestehenden freien `str`-Feld |
| `src/services/radar_service.py` | `_AROME_FR_LAT_MIN/MAX/LON_MIN/MAX` — Frankreich-Bbox, identisch zu Vigilance importieren |
| `src/services/comparison_engine.py:184-190` | Ruft `get_official_alerts_for_location()` bereits generisch auf — **keine Änderung nötig**, neue Quelle wird automatisch mit abgefragt |
| `src/output/renderers/comparison.py:418-420` | Plain-Text-Warnzeile pro `alert.label` — bereits generisch, **keine Änderung nötig** |
| `src/output/renderers/email/compare_html.py:144-169` | HTML-Badge, Farbe nach `alert.level` (1-2 grün, 3 orange, 4 rot) — bereits generisch, **keine Änderung nötig** |
| `tests/tdd/test_issue_1035_vigilance_source.py` | Test-Vorbild: Struktur, Fixtures, No-Mock-Pattern, AC-Reihenfolge |

**Korrektur zum Issue-Text:** Issue #1036 nennt `src/services/comparison_renderers.py` (existiert nicht) und
Registrierung in `base.py`. Tatsächlich: Renderer sind bereits vollständig generisch über das `OfficialAlert`-Modell
(Label + Level) und brauchen **keine Änderung**. Registrierung erfolgt in `__init__.py` (Vorbild: Vigilance-Zeile dort).

## Existing Patterns
- **Registry-Pattern**: jede Quelle implementiert `name`/`covers()`/`fetch()`, wird bei Modul-Import registriert (`__init__.py`).
- **Fail-soft**: fehlender API-Key ODER Netzwerkfehler → `fetch()` liefert `[]`, kein Crash (`get_official_alerts_for_location()` fängt zusätzlich jede Exception pro Quelle ab).
- **Caching**: Vigilance cached den nationalen Call 300s (Erfolg) / 60s (Fehlschlag) im Modul-Dict, um einen Call-Sturm pro verglichenem Ort zu verhindern. Météo des forêts hat **keinen nationalen Call** — der bestätigte Endpunkt ist bereits pro Département (`id-departement={dep}`), d.h. Caching muss **pro Département** erfolgen (TTL analog: Datenquelle aktualisiert laut Issue nur 1x/Tag ca. 17 Uhr — 300s-TTL ist konservativ genug, kein Grund für längere TTL).
- **Département-Mapping**: `lookup_department(lat, lon)` gemeinsam mit Vigilance nutzen, kein Korsika-Sonderfall im Code (AC-4-Analogon in Vigilance-Tests: `assert '"2A"' not in src`).
- **No-Mock-Tests**: echte API-Calls gegen Météo-France; AC für "kein Fehler bei Netzwerkausfall" testet echtes Verhalten (ENV-Variable temporär entfernen), nicht `patch()`.

## API-Details (verifiziert, Epic #1033 Kommentar 2026-07-06)
- **Kein OAuth2, kein Token-Provider nötig** — Header `apikey: <GZ_METEOFRANCE_APIKEY>` (identisch zu Vigilance-Header, andere ENV-Semantik als vermutet: gleiche ENV-Variable wie Vigilance, `GZ_METEOFRANCE_APIKEY`, EIN Schlüssel für alle Portal-APIs).
- **Endpunkt (live verifiziert, HTTP 200)**:
  `GET https://public-api.meteofrance.fr/public/DPMeteoForets/v1/carte/departement/encours?format=json&echeance=J1&id-departement={dep}`
- **Beispiel-Antwort** (Var, 2026-07-05):
  ```json
  [{"reference_time":"2026-07-05T14:50:04Z","dep_code":"83","niveau_j1":"3","dep_nom":"Var"}]
  ```
  → `niveau_j1` ist die Gefahrenstufe 1–4 als String, `dep_code` bestätigt das Département.
- Kein nationaler Bulk-Endpunkt für JSON (nur CSV `carte/encours` – lt. Epic-Kommentar als Fallback verworfen,
  da der Département-Endpunkt bereits live verifiziert und einfacher ist).

## Saison-Gate (Juni–September) — Testbarkeits-Design
`covers()` muss zusätzlich zur Frankreich-Bbox prüfen, ob der aktuelle Monat in {6,7,8,9} liegt.
Da Mocks/Patches verboten sind und das heutige Datum (2026-07-07) mitten in der Saison liegt, kann
AC-2 ("außerhalb Juni–September") nicht über eine gemockte Systemzeit bewiesen werden. Lösung nach
Vorbild "pure function extrahieren, real mit echten Werten testen" (kein Zeit-Mock nötig):

```python
_SEASON_MONTHS = {6, 7, 8, 9}

def _is_season(month: int) -> bool:
    return month in _SEASON_MONTHS

class MeteoForetsSource:
    def covers(self, lat: float, lon: float) -> bool:
        return _is_season(datetime.now().month) and <FR-Bbox-Check>
```
Test ruft `_is_season(1)` (Januar) direkt mit echtem Integer auf → beweist reales Verhalten ohne jede
Manipulation von `datetime`/Systemzeit. Zusätzlich: strukturaler `covers()`-Test mit echtem `datetime.now().month`
(läuft heute, Juli, durch die Saison-Bedingung `True`).

## Dependencies
- **Upstream:** `httpx` (bereits Projekt-Dependency, s. vigilance.py), `department_mapper.lookup_department`,
  `radar_service`-FR-Bbox-Konstanten, `os.environ["GZ_METEOFRANCE_APIKEY"]`.
- **Downstream:** `comparison_engine.py` (generischer Aufruf), beide Renderer (generisch) — keine Anpassung nötig.

## Existing Specs
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Registry-Fundament
- `docs/specs/modules/issue_1035_vigilance_source.md` — direktes Vorbild, gleiche Struktur

## Risks & Considerations
- **Level-Typ:** API liefert `niveau_j1` als String ("3") — muss zu `int` gecastet werden (analog Vigilance
  `phenomenon_max_color_id`), inkl. Fail-soft bei nicht-parsbarem Wert (kein Crash, Alert einfach überspringen).
- **Label-Text für AC-1:** Issue erwartet Badge-Text "Waldbrand-Gefahr — Stufe 4". Da der HTML-Renderer
  `alert.label` direkt anzeigt, muss `label` bereits so formatiert sein, z.B. `f"Waldbrand-Gefahr — Stufe {level}"`.
- **Kein nationaler Cache möglich** — Cache-Schlüssel muss pro Département sein (Dict statt Einzelwert wie
  bei Vigilance). Bei N verglichenen Orten im selben Département nur 1 Call (TTL-Fenster), bei unterschiedlichen
  Départements mehrere Calls — das ist unvermeidbar, da der Endpunkt selbst schon département-scoped ist (kein
  Overhead gegenüber der API-Struktur).
- **`echeance=J1` vs. `J2`:** Issue verlangt nur "Vorhersage für J+1/J+2" als Beschreibung, AC-1 prüft nur den
  aktuellen Tag — J1 (heute/nächster Tag) ist ausreichend für diesen Slice; J2 nicht zwingend für die ACs.
- **Level < irgendein Schwellwert?** Anders als Vigilance (nur ab Farbstufe 2) gibt es im Issue keine Erwähnung
  eines Mindest-Schwellwerts für Waldbrand — vermutlich soll **jede Stufe 1–4** als Badge erscheinen (Waldbrand-
  Gefahr ist auch bei Stufe 1 "gering" relevant für Wanderer, anders als Vigilance-Grün das keine Handlung
  erfordert). Für die Spec-Phase klären/festlegen: adressiert als offene Frage.

## Nächster Schritt
`/30-write-spec` — vollständige Spec inkl. AC-Test-Mapping, Klärung Level-Schwellwert.
