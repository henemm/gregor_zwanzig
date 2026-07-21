---
entity_id: official_alerts_meteo_forets
type: module
created: 2026-07-06
updated: 2026-07-07
status: superseded
version: "1.0"
tags: [compare, alerts, official-alerts, meteofrance]
---

# Official Alerts — Météo des forêts (Waldbrand-Gefahrenstufe)

> **SUPERSEDED (2026-07-07):** Dies ist der Vor-Analyse-Entwurf für #1036, geschrieben bevor die
> Analyse-Phase den tatsächlichen API-Zugang klärte. Er beschreibt einen möglichen OAuth2-Pfad
> (`meteo_token_provider.py`) und einen CSV-Fallback über meteo.data.gouv.fr, die beide **nicht
> verwendet wurden** — real verifiziert wurde stattdessen ein einfacher `apikey`-HTTP-Header
> (identisch zu Vigilance) gegen den département-scoped JSON-Endpoint
> `.../DPMeteoForets/v1/carte/departement/encours`. Die verbindliche, implementierte Spec ist
> **`docs/specs/modules/issue_1036_meteo_forets_source.md`**. Diese Datei bleibt nur als
> Analyse-Historie erhalten, nicht als aktuelle Referenz.

## Approval

- [x] Approved (Vor-Analyse-Entwurf, superseded — siehe Banner oben)

## Purpose

Zweite Quelle in der Official-Alerts-Registry: Waldbrand-Gefahrenstufe (1–4) auf
Département-Ebene, Vorhersage für J+1/J+2. **Nur Juni–September verfügbar** — außerhalb der
Saison liefert die Quelle bewusst "kein Wert" statt Fehler. **Leitszenario:** Côte d'Azur (Var,
Alpes-Maritimes, Bouches-du-Rhône) — die Saison läuft jetzt, zweite Implementierungspriorität
nach Vigilance (#1035). Korsika über denselben landesweiten Département-Mapper mitgedeckt.

## Source

- **File:** `src/services/official_alerts/meteo_forets.py`
- **Identifier:** `MeteoForetsSource`

> Datenquelle: gleiches OAuth2-Portal wie Vigilance (`DonneesPubliquesMeteoForets`) oder
> auth-freier CSV-Export über meteo.data.gouv.fr — Entscheidung während Implementierung anhand
> tatsächlicher Antwortstruktur (CSV bevorzugt, falls stabil, da kein OAuth2-Overhead nötig).

## Estimated Scope

- **LoC:** ~100
- **Files:** 3 (1 neu, 2 geändert — siehe Issue #1036)
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py` (#1034) | Fundament | `OfficialAlertSource`-Protocol, Registry |
| `src/services/official_alerts/department_mapper.py` (#1035) | Wiederverwendung | Département-Zuordnung |
| `src/services/official_alerts/meteo_token_provider.py` (#1035) | Wiederverwendung (optional) | falls OAuth2-Pfad gewählt wird |

## Implementation Details

```python
class MeteoForetsSource:
    name = "meteofrance_forets"
    _SEASON_MONTHS = {6, 7, 8, 9}

    def covers(self, lat: float, lon: float) -> bool:
        if datetime.now().month not in self._SEASON_MONTHS:
            return False
        return _france_bbox_check(lat, lon)  # identisch zu VigilanceSource

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        dept = department_for(lat, lon)
        # Gefahrenstufe fuer dept laden -> OfficialAlert(hazard="wildfire_risk", level=1-4)
        ...
```

## Expected Behavior

- **Input:** Lat/Lon eines Ortes.
- **Output:** Liste mit maximal einem `OfficialAlert(hazard="wildfire_risk")` pro Ort, nur
  Juni–September, nur für Frankreich; leer außerhalb der Saison, außerhalb Frankreichs oder bei
  Quellen-Fehler.
- **Side effects:** HTTP-Call gegen Météo-France-Portal oder CSV-Download (nur wenn `covers()`
  true).

## Acceptance Criteria

- **AC-1:** Given aktuelles Datum liegt in Juni–September und ein Ort im Var (83) mit
  Gefahrenstufe 4 ("sehr hoch"), When die Compare-Mail generiert wird, Then zeigt die Mail für
  diesen Ort einen roten Badge "Waldbrand-Gefahr — Stufe 4".
  - Test: echter API-/CSV-Call mit einem zum Testzeitpunkt bekannten Département-Datensatz, kein
    Mock; Compare-Mail-HTML auf Badge prüfen.

- **AC-2:** Given aktuelles Datum liegt außerhalb Juni–September (z. B. Januar), When
  `get_official_alerts_for_location()` für einen französischen Ort aufgerufen wird, Then liefert
  `MeteoForetsSource.covers()` `False` und es wird kein Waldbrand-Badge angezeigt.
  - Test: `covers()` mit einem Datum außerhalb der Saison direkt aufrufen (Datum
    injizierbar/mockbar in der Prüfung selbst, nicht die Datenquelle), `False` erwarten.

- **AC-3:** Given die Datenquelle ist zum Abfragezeitpunkt nicht erreichbar (Netzwerkfehler),
  When die Compare-Mail generiert wird, Then läuft der Versand normal durch ohne
  Waldbrand-Badge für den betroffenen Ort.
  - Test: echten Compare-Lauf während eines Quellen-Ausfalls (z. B. durch temporär
    ungültige Endpoint-URL) durchführen, prüfen dass Mail vollständig generiert wird.

## Known Limitations

- Saisonfenster ist hart auf Kalendermonate 6–9 gesetzt, nicht auf offizielle Start-/Enddaten
  einzelner Jahre (die Météo-France-Saison kann geringfügig variieren) — akzeptiert als
  Vereinfachung für den MVP.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016 (siehe #1034 für Details)
- **Rationale:** Zweite Quelle nach demselben etablierten Interface, keine neue Entscheidung
  nötig.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1036)
- 2026-07-07: Superseded durch `issue_1036_meteo_forets_source.md` — Analyse-Phase klärte den
  tatsächlichen API-Zugang (kein OAuth2, `apikey`-Header wie Vigilance) und die Implementierung
  wurde gegen die vollständige Spec durchgeführt, Adversary VERIFIED.
