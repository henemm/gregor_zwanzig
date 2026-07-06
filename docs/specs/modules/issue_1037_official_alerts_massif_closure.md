---
entity_id: official_alerts_massif_closure
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.1"
tags: [compare, alerts, official-alerts]
---

# Official Alerts — Massiv-Betretungsverbote (Côte d'Azur / Korsika)

## Approval

- [ ] Approved

## Purpose

Dritte Quelle: Präfektur-Zugangssperren einzelner Wander-Massive bei akuter Waldbrandgefahr.
**Leitszenario:** Côte d'Azur — Départements Var (83), Alpes-Maritimes (06),
Bouches-du-Rhône (13). Korsika (2A/2B, GR20-Kontext) ist ein zweiter, gleichrangig
unterstützter Anwendungsfall über denselben Mechanismus. Feinste verfügbare Granularität der
drei Slices — laut PO hoher konkreter Urlaubs-Mehrwert im Var. Dritte Implementierungspriorität,
architektonisch der aufwendigste Slice.

## Source

- **File:** `src/services/official_alerts/massif_closure.py`, `massif_zones.py`
- **Identifier:** `MassifClosureSource`

> Datenquelle: kein offizielles API, aber stabiler undokumentierter JSON-Endpoint (live
> verifiziert 2026-07-06 für Var, PO-Beispiel `risque-prevention-incendie.fr/var/`):
> `https://www.risque-prevention-incendie.fr/static/{DEPT}/import_data/{YYYYMMDD}.json`
> (Var `DEPT=83`, Alpes-Maritimes `DEPT=06`, Bouches-du-Rhône `DEPT=13`, Korsika `DEPT=20` — ob
> Korsika weiterhin zusammengefasst oder bereits nach 2A/2B getrennt geführt wird, ist während
> der Implementierung gegen die Live-Antwort zu verifizieren). Struktur:
> `massifs[<massiv_id>] = [niveau_j1, niveau_j2]`, Niveau 1=grün…4/5=rot. Auth-frei. Lizenz
> unklar — kein Attribution-Zwang bekannt, aber Betriebsrisiko (Struktur kann sich ändern)
> mittel-hoch.

## Estimated Scope

- **LoC:** ~250
- **Files:** 4 (3 neu, 1 geändert — siehe Issue #1037)
- **Effort:** medium-high (obere Grenze durch Neu-Recherche für 3 zusätzliche Départements)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py` (#1034) | Fundament | `OfficialAlertSource`-Protocol, Registry |
| `src/services/official_alerts/department_mapper.py` (#1035) | Wiederverwendung | landesweiter Koordinate → Département-Mapper, keine Neuentwicklung |
| Vorgänger-Projekt `gr20_zone_massif_ids.py` (nur Referenz, nur für Korsika-Daten) | Fachliche Datenquelle | liefert die Korsika-Einträge der generischen Zonen-Tabelle, ist aber NICHT die Architektur |
| Öffentliche Karte/JSON auf risque-prevention-incendie.fr | Neu-Recherche | Massiv-Namen/Zentren für Var/Alpes-Maritimes/Bouches-du-Rhône (kein Vorarbeit-Material vorhanden) |

## Architektur-Entscheidung 1: Keine FlatGeobuf-Abhängigkeit für den MVP

Die Quelle liefert zusätzlich Polygon-Geometrien als FlatGeobuf
(`static/{DEPT}/massifs_{DEPT}.fgb`) für exaktes Point-in-Polygon. Diese Geometrie-Auswertung zur
**Laufzeit** ist für den MVP bewusst nicht Teil dieses Slices — ein FlatGeobuf-Parser +
Geometrie-Bibliothek als neue Python-Abhängigkeit ist laut Projektregel ("keine neuen
Dependencies ohne Freigabe") kein Selbstläufer. Stattdessen: statische Zentrum+Radius-Zonentabelle
je Massiv (Näherung statt exakter Grenze).

**Die `.fgb`-Datei wird trotzdem genutzt — aber einmalig, offline, während der Implementierung:**
für Var (`static/83/massifs_83.fgb`) liest der Entwickler die Datei einmalig mit einem
Wegwerf-Skript oder externen Tool (z. B. `ogr2ogr`/QGIS, außerhalb der Produktions-Codebasis) aus,
um Massiv-Namen und grobe Zentrum-Koordinaten zu gewinnen, und trägt das Ergebnis von Hand als
Konstanten in `massif_zones.py` ein. Zur Laufzeit liest die Anwendung nie ein `.fgb`-File und
braucht dafür keine Bibliothek — nur die vorab kuratierte Tabelle.

## Architektur-Entscheidung 2 (Scope-Korrektur 2026-07-06): Département-generischer Mechanismus, KEINE GR20-Hartkodierung

Der ursprüngliche Entwurf hatte den Lookup GR20-spezifisch kodiert (reine Portierung von
`gr20_zone_massif_ids.py` als Kernmechanik). Das ist korrigiert, weil das primäre Leitszenario
jetzt Côte d'Azur ist, nicht GR20:

- **Generische Datenstruktur**, keyed by Département-Code:

```python
@dataclass(frozen=True)
class MassifZone:
    massif_id: str
    name: str
    center_lat: float
    center_lon: float
    radius_km: float

MASSIF_ZONES: dict[str, list[MassifZone]] = {
    "83": [...],   # Var — neu recherchiert
    "06": [...],   # Alpes-Maritimes — neu recherchiert
    "13": [...],   # Bouches-du-Rhône — neu recherchiert
    "2A": [...],   # Corse-du-Sud — aus Vorgänger-Datenquelle (gr20_zone_massif_ids.py)
    "2B": [...],   # Haute-Corse — aus Vorgänger-Datenquelle
}
```

- `covers(lat, lon)` nutzt den **landesweiten** `department_mapper.py` aus #1035, um das
  Département zu bestimmen, und prüft dann nur, ob dieses Département einen Eintrag in
  `MASSIF_ZONES` hat. Kein Sonderfall-Code für Korsika oder für Côte d'Azur — dieselbe Logik für
  jedes unterstützte Département.
- **Datenbefüllung ist getrennte Recherche-Arbeit, Mechanik ist gemeinsam:** Korsika-Zonen kommen
  aus dem fachlich bereits verifizierten Vorgängerprojekt (nur als Datenquelle, nicht als
  Architektur-Vorbild). Var/Alpes-Maritimes/Bouches-du-Rhône-Zonen müssen in diesem Slice neu
  kuratiert werden — Massiv-Namen/IDs aus der öffentlichen Karte bzw. den JSON-Keys ableiten,
  grobe Zentrum-Koordinate von Hand bestimmen. Umfang: mindestens die Massive, die die konkret
  vom PO verglichenen Côte-d'Azur-Orte abdecken — keine vollständige Département-Abdeckung nötig.
- **Trade-off (unverändert):** Orte außerhalb der kuratierten Zonen liefern keine
  Sperr-Information (fail-soft, kein Fehler). Weitere Départements oder echte Polygon-Auswertung
  sind inkrementell nachrüstbar, ohne den Mechanismus zu ändern.

```python
class MassifClosureSource:
    name = "massif_closure"

    def covers(self, lat: float, lon: float) -> bool:
        dept = department_for(lat, lon)  # aus #1035, landesweit
        return dept in MASSIF_ZONES

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        dept = department_for(lat, lon)
        zone = _nearest_zone_within_radius(lat, lon, MASSIF_ZONES.get(dept, []))
        if zone is None:
            return []
        data = _load_cached_daily_json(dept)  # Tages-Cache, ein Download pro Tag
        if not data or "massifs" not in data or zone.massif_id not in data["massifs"]:
            logger.warning("massif_closure: unerwartete Struktur fuer dept=%s", dept)
            return []
        niveau = data["massifs"][zone.massif_id][0]  # J1
        return [OfficialAlert(hazard="access_ban", level=niveau, region_label=zone.name, ...)]
```

**Monitoring:** leichtgewichtiger Modul-Level-Status (letzter erfolgreicher Fetch, letzter
Fehler) in `massif_closure.py` — Projektregel "kein Job ohne Observability"; kein neuer Service
nötig, spätere Anbindung an den Scheduler-Status-Endpoint ist ein Folge-Schritt.

## Expected Behavior

- **Input:** Lat/Lon eines Ortes.
- **Output:** Liste mit maximal einem `OfficialAlert(hazard="access_ban")` pro Ort, wenn der Ort
  in einem unterstützten Département liegt, dort ein kuratiertes Massiv in Reichweite liegt und
  für dieses Massiv aktuell eine Sperrstufe gemeldet ist; leer sonst.
- **Side effects:** HTTP-Call gegen den JSON-Endpoint des ermittelten Départements (mit
  Tages-Cache, um nicht bei jedem Compare-Lauf neu zu laden).

## Acceptance Criteria

- **AC-1:** Given ein kartierter Ort im Var nahe dem Massif des Maures oder dem Massif de
  l'Estérel mit aktuell gesperrtem Massiv (im Juli realistisch Niveau ≥2 im Live-JSON, da beide
  Gebiete saisonal regelmäßig eingeschränkt/gesperrt werden), When die Compare-Mail generiert
  wird, Then zeigt die Mail für diesen Ort einen Badge "Zugang gesperrt — [Massiv-Name]".
  - Test: echter Call gegen den Live-Endpoint für DEPT=83 mit einem zum Testzeitpunkt bekannten
    Massiv/Niveau, kein Mock; Compare-Mail-HTML auf Badge prüfen.

- **AC-2:** Given ein kartierter Ort auf Korsika mit aktuell gesperrtem Massiv, When die
  Compare-Mail generiert wird, Then funktioniert dieselbe Logik identisch wie für den Var-Ort in
  AC-1 (derselbe Code-Pfad, kein Korsika-Sonderfall).
  - Test: identischer Ablauf wie AC-1, aber gegen DEPT=20/2A/2B; Diff der aufgerufenen
    Code-Pfade zeigt keine département-spezifische Verzweigung außer der Datentabelle selbst.

- **AC-3:** Given ein Ort liegt in einem Département ohne `MASSIF_ZONES`-Eintrag (z. B. Paris),
  When `get_official_alerts_for_location()` aufgerufen wird, Then liefert `MassifClosureSource`
  keinen Badge.
  - Test: `covers()` mit Koordinaten in einem nicht kuratierten Département aufrufen, `False`
    erwarten.

- **AC-4:** Given der JSON-Endpoint liefert eine unerwartete/fehlerhafte Struktur (z. B.
  fehlendes `massifs`-Feld), When `fetch()` aufgerufen wird, Then wird eine Warnung geloggt und
  `[]` zurückgegeben, kein Absturz der Compare-Mail-Generierung.
  - Test: `fetch()` gegen eine präparierte Antwort mit fehlendem `massifs`-Feld aufrufen (echter
    HTTP-Mechanismus, aber gegen einen kontrollierten Testfall/Fixture-Response — kein
    Verhaltens-Mock der Kernlogik selbst), leere Liste + Log-Eintrag prüfen.

## Known Limitations

- `MASSIF_ZONES` deckt nur kuratierte Départements/Massive ab (Var, Alpes-Maritimes,
  Bouches-du-Rhône, Korsika 2A/2B) — keine echte Polygon-Geometrie, daher keine Abdeckung
  außerhalb dieser Zonen und keine Abdeckung weiterer Départements ohne Datentabellen-Erweiterung.
- Massiv-Grenzen können sich ändern, ohne dass die statische Tabelle automatisch nachzieht —
  jährliche Stichprobe vor der Sommersaison empfohlen (Betriebs-Playbook-Notiz, kein
  Code-Bestandteil dieses Slices).
- Var/Alpes-Maritimes/Bouches-du-Rhône-Zonen sind neu kuratiert (anders als die bereits fachlich
  verifizierten Korsika-Daten) — Genauigkeit hängt von der Qualität der öffentlich zugänglichen
  Karten-/JSON-Informationen zum Implementierungszeitpunkt ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0016 (siehe #1034 für Details zum übergeordneten additiven Alert-Typ)
- **Rationale:** Die FlatGeobuf-Abweichung und die Département-Generizität sind slice-lokale
  Scoping-/Architektur-Entscheidungen (Dependency-Vermeidung, Vermeidung einer
  GR20-Hartkodierung angesichts des jetzt primären Côte-d'Azur-Szenarios), keine eigene
  ADR-würdige Grundsatzfrage — dokumentiert hier und im Epic-Feature-Dokument
  (`docs/features/epic-1033-compare-official-alerts.md`).

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1037)
- 2026-07-06: Scope-Korrektur (PO): Côte d'Azur (Var/Alpes-Maritimes/Bouches-du-Rhône) als
  primäres Leitszenario, Mechanismus auf generischen Département-Lookup umgestellt
  (`MASSIF_ZONES` statt GR20-hartkodierter `massif_ids.py`), Korsika-Daten aus dem
  Vorgängerprojekt sind nur noch Dateninhalt, nicht Architektur.
- 2026-07-06: Präzisierung: AC-1 mit konkretem Var-Beispiel (Massif des Maures/Estérel,
  Juli-Plausibilität Niveau ≥2), FlatGeobuf-Nutzung als einmalige Offline-Ableitung (kein
  Laufzeit-Parser) explizit dokumentiert.
