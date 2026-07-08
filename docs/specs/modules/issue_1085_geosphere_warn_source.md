---
entity_id: issue_1085_geosphere_warn_source
type: feature
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
workflow: feat-1085-geosphere-warn
tags: [compare, alerts, official-alerts, geosphere, austria]
---

# GeoSphere-Warn-Quelle — Österreich (Slice 1, Epic #1073)

## Approval

- [ ] Approved

## Purpose

`GeoSphereWarnSource` ist die erste Nicht-Frankreich-Quelle für die bestehende
Official-Alerts-Registry (#1034): sie ruft die amtliche GeoSphere-Warn-API
(Österreich) ab und liefert Sturm-, Regen-, Schnee-, Glatteis-, Gewitter-,
Hitze- und Kälte-Warnungen — additiv überall dort, wo
`get_official_alerts_for_location()` konsumiert wird (Orts-Vergleich +
Trip-Briefings, gemeinsamer Renderer seit #1087).

## Source

- **File:** `src/services/official_alerts/geosphere_warn.py`
- **Identifier:** `class GeoSphereWarnSource`

> **Schicht:** Python-Core/Domain-Backend (`src/services/official_alerts/`).

## Estimated Scope

- **LoC:** ~120–160 src-LoC (analog `vigilance.py`, ohne Département-Mapper-
  Äquivalent, da die Quelle direkt pro Koordinate abfragt)
- **Files:** 2 neu (`geosphere_warn.py`, Testdatei), 1 geändert
  (`official_alerts/__init__.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::OfficialAlertSource` | Protocol (bindend, #1034) | `GeoSphereWarnSource` implementiert `name`/`covers()`/`fetch()` strukturell |
| `src/services/official_alerts/base.py::register_official_alert_source` | Registry (bindend, #1034) | Lazy-Registration bei Modul-Import |
| `src/services/official_alerts/models.py::OfficialAlert` | Datentyp (bindend, #1034) | `fetch()` befüllt bestehende Felder, keine Schema-Änderung |
| `src/services/radar_service.py:33-36` (`_INCA_LAT_MIN/MAX/_INCA_LON_MIN/MAX`) | Code-Wiederverwendung | Österreich-Bbox als `covers()`-Vorfilter (kein API-Call) |
| `httpx` | Bestehende Dependency | HTTP-GET gegen `warnungen.zamg.at/wsapp/api` |
| `src/output/renderers/alert/official_alerts.py` | Konsument (unverändert) | rendert Badges nur aus `label`/`level` — kein Renderer-Change nötig |

## Implementation Details

**Verifizierter Endpunkt** (echter API-Call durchgeführt, 2026-07-08):
`GET https://warnungen.zamg.at/wsapp/api/getWarningsForCoords?lat={lat}&lon={lon}&lang=de`,
auth-frei, JSON-GeoJSON-Feature. Antwort-Struktur:
`properties.location.properties.name` (Gemeindename, z. B. "Innsbruck") +
`properties.warnings[]`, je Warnung ein `properties`-Objekt mit `warntypid`,
`warnstufeid`, `begin`/`end` (deutsches Format `TT.MM.JJJJ HH:MM`) sowie
`rawinfo.start`/`end` (Unix-Epoch-Strings — **diese werden geparst**, nicht
`begin`/`end`, um die Zeitzonen-Falle des deutschen Formats zu vermeiden).
Koordinaten außerhalb Österreichs liefern HTTP 404
`{"type":"Error","msg":"Could not find municipal for coords."}`.

Level-Mapping (amtlich verifiziert via OpenAPI-Schema `WarnLevel`,
`https://openapi.hub.geosphere.at/warnapi/v1/openapi.json`): GeoSphere
`warnstufeid` 1=gelb, 2=orange, 3=rot. `OfficialAlert.level` ist die
Vigilance-Skala 1=grün…4=rot (models.py) → `level = warnstufeid + 1`
(Ergebnis 2/3/4). Damit greift das bestehende Renderer-Farbmapping
(`official_alerts.py`: ≤2 → G_SUCCESS, 3 → G_WARNING, ≥4 → G_DANGER) identisch
zur Vigilance-Semantik — kein Renderer-Change.

Hazard-Mapping (amtlich verifiziert via OpenAPI-Schema `WarnType`, enum 1–7),
`warntypid` → `(hazard, label)`:

| warntypid | hazard | label (de) |
|-----------|--------|------------|
| 1 | `wind_gust` | "Sturm" |
| 2 | `rain` | "Starkregen" |
| 3 | `snow` | "Schneefall" |
| 4 | `black_ice` | "Glatteis" |
| 5 | `thunderstorm` | "Gewitter" |
| 6 | `extreme_heat` | "Hitze" |
| 7 | `extreme_cold` | "Kälte" |

`wind_gust`/`thunderstorm`/`extreme_heat` sind bewusst dieselben Bezeichner
wie in `vigilance.py` (Konsistenz für nachgelagerte Filter); `rain`, `snow`,
`black_ice`, `extreme_cold` sind neue Hazard-Bezeichner. Ein unbekanntes
`warntypid` (nicht in 1–7) wird pro Warnung übersprungen, nicht als Crash
behandelt.

```python
# src/services/official_alerts/geosphere_warn.py (Skizze, kein Volltext)
class GeoSphereWarnSource:
    name = "geosphere_warn"

    def covers(self, lat: float, lon: float) -> bool:
        return (_INCA_LAT_MIN <= lat <= _INCA_LAT_MAX
                and _INCA_LON_MIN <= lon <= _INCA_LON_MAX)

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        cached = _get_cached_warnings(lat, lon)  # pro-Koordinate-Cache
        if cached is None:
            return []
        return _extract_alerts(cached)
```

Caching unterscheidet sich bewusst von `vigilance.py`: dort ist EIN
nationaler Call für alle Orte ausreichend, hier liefert der Endpunkt pro
Koordinate — daher Cache **pro gerundetem `(lat, lon)`-Schlüssel** (4
Nachkommastellen, analog `meteo_forets.py`-Pro-Region-Cache), Erfolgs-TTL
300s, Failure-TTL 60s (F001-Lehre: kein Call-pro-Wiederholung-Sturm).
Modul-globaler Cache-Dict, Timeout 8.0s (analog `vigilance.py`).

Kein ENV-Zweig nötig (auth-frei) — anders als bei `VigilanceSource` gibt es
keinen "fehlender API-Key"-Pfad. Fail-soft deckt stattdessen: HTTP-Fehler
(inkl. 404 "Could not find municipal for coords."), Timeout, kaputtes JSON,
fehlende erwartete Felder (`properties`, `warnings`, `location`) → `fetch()`
liefert `[]`, loggt eine Warning, wirft nie.

Registrierung analog #1035: `official_alerts/__init__.py` importiert
`geosphere_warn` und ruft `register_official_alert_source(GeoSphereWarnSource())`
beim Modul-Import auf (Lazy-Registration), plus Export in `__all__`.

Kreis-Import-Verbot: kein Import aus `services.comparison_engine`. Der
gemeinsame Renderer (`src/output/renderers/alert/official_alerts.py`,
#1087) wird **nicht** angefasst — er konsumiert bereits generisch
`label`/`level`/`region_label` unabhängig von der Quelle.

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes bzw. einer Trip-Etappe (via
  `get_official_alerts_for_location()`).
- **Output:** Liste von `OfficialAlert` mit `source="geosphere_warn"`,
  `hazard∈{wind_gust,rain,snow,black_ice,thunderstorm,extreme_heat,extreme_cold}`,
  `level∈{2,3,4}`, deutschem `label`, `valid_from`/`valid_to` aus
  `rawinfo.start`/`end`, `region_label` aus dem Gemeindenamen — leer, wenn
  keine Warnung vorliegt, der Ort außerhalb Österreichs liegt, oder die API
  fehlschlägt.
- **Side effects:** höchstens ein HTTP-GET pro Koordinate und Cache-TTL-
  Fenster (300s Erfolg / 60s Fehlschlag) gegen `warnungen.zamg.at`; kein
  Schreiben, keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein österreichischer Ort mit einer zum Testzeitpunkt
  tatsächlich aktiven amtlichen Warnung, When die Staging-Trip-Briefing-Mail
  für einen Trip mit diesem Ort echt versendet und via IMAP abgerufen wird,
  Then enthält die Mail einen Warn-Badge mit korrektem Typ-Label
  (aus der Hazard-Mapping-Tabelle) und der zur Warnstufe passenden
  Badge-Farbe (Level 2→G_SUCCESS-Rand, 3→G_WARNING, 4→G_DANGER).
  - Test: Echter Live-Call gegen die GeoSphere-API (kein Mock), echter
    Trip-Briefing-Versand über Staging, echte IMAP-Prüfung der zugestellten
    Mail (`briefing_mail_validator.py`-kompatibler Pfad). Der Compare-Pfad
    nutzt dieselbe Registry und wird strukturell mitbewiesen, wird aber
    wegen der parallelen Compare-Mail-Umstellung in #1110 nicht als
    primärer E2E-Beweis herangezogen.

- **AC-2:** Given ein Ort außerhalb Österreichs (z. B. in Deutschland oder
  Frankreich), When `get_official_alerts_for_location()` für diesen Ort
  aufgerufen wird, Then macht `GeoSphereWarnSource` keinen API-Call
  (`covers()` liefert `False`, `fetch()` wird nie erreicht) und liefert keine
  Badges; Given ein österreichischer Ort ohne aktive amtliche Warnung zum
  Testzeitpunkt, When dieselbe Funktion aufgerufen wird, Then liefert
  `fetch()` eine leere Liste ohne Fehler.
  - Test: Echte `GeoSphereWarnSource`-Instanz mit einem Aufruf-Zähler-Spy um
    `fetch()` (kein Mock der API) gegen einen deutschen/französischen
    Lat/Lon-Wert; Zähler bleibt 0, `covers()` liefert `False`. Zweiter Test
    mit einem echten AT-Lat/Lon außerhalb bekannter Warngebiete: echter
    API-Call, Ergebnis ist eine leere Liste, keine Exception.

- **AC-3:** Given der GeoSphere-Endpoint liefert einen HTTP-Fehler (z. B.
  404 "Could not find municipal for coords." bei einer Koordinate knapp
  außerhalb einer österreichischen Gemeinde, aber innerhalb der AT-Bbox),
  einen Timeout, oder eine strukturell kaputte JSON-Antwort, When `fetch()`
  aufgerufen wird, Then wird eine Warning geloggt, `fetch()` liefert `[]`
  ohne Exception, und eine nachgelagerte Trip-Briefing- bzw. Compare-Mail-
  Erzeugung läuft ohne Absturz durch.
  - Test: Echter API-Call gegen eine reale Koordinate innerhalb der AT-Bbox
    (`_INCA_LAT_MIN/MAX`, `_INCA_LON_MIN/MAX`), die real außerhalb einer
    österreichischen Gemeinde liegt (z. B. Schweizer Grenzgebiet innerhalb
    der Box), und Prüfung, dass `fetch()` `[]` liefert statt zu werfen;
    zusätzlich `get_official_alerts_for_location()` mit dieser Koordinate
    aufrufen und verifizieren, dass die Gesamtfunktion nicht wirft.

- **AC-4:** Given eine echte GeoSphere-API-Antwort mit mindestens einer
  Warnung, When die Antwort durch die interne Mapping-Logik geparst wird,
  Then wird jedes `warnstufeid` (1/2/3) korrekt auf `level` (2/3/4)
  abgebildet, jedes `warntypid` (1–7) korrekt auf das dokumentierte
  `(hazard, label)`-Paar, und ein unbekanntes `warntypid` (außerhalb 1–7)
  führt zum Überspringen dieser einzelnen Warnung statt zu einem Crash der
  gesamten `fetch()`-Antwort.
  - Test: Echter API-Call gegen einen Ort mit tatsächlich vorliegender
    Warnung (Struktur-/Mapping-Beweis anhand der real gelieferten
    `warnstufeid`/`warntypid`-Werte); zusätzlich ein Unit-Test auf der
    reinen Parse-/Mapping-Funktion mit einer synthetisch zusammengesetzten,
    aber strukturell echten JSON-Antwort (kein Netzwerk-Mock der Bibliothek
    — nur eine als Testdaten deklarierte, aus der Doku abgeleitete
    Beispielstruktur), die alle sieben `warntypid`-Werte sowie ein
    unbekanntes `warntypid` abdeckt.

## Known Limitations

- Der Endpunkt ist der `wsapp`-App-Backend-Endpunkt (nicht die offizielle
  `warnapi/v1`-Route des OpenAPI-Hubs) — Struktur und Enum-Semantik sind über
  das OpenAPI-Schema verifiziert, die Basis-URL selbst folgt aber der
  Live-Verifikation vom 2026-07-08, nicht der offiziellen API-Dokumentation.
  Bricht die `wsapp`-Route künftig, ist ein Wechsel auf `warnapi/v1` ein
  Folge-Issue, kein Scope dieser Spec.
- `begin`/`end` (deutsches Lokalformat) werden bewusst ignoriert zugunsten
  von `rawinfo.start`/`end` (Unix-Epoch) — sollte `rawinfo` in einer
  Antwort fehlen, bleibt `valid_from`/`valid_to` `None` (kein zusätzlicher
  Parse-Versuch auf das deutsche Format in diesem Slice).
- Live-Testfenster für AC-1/AC-4 hängt von der tatsächlichen Warnlage zum
  Testzeitpunkt ab (aktive Hitzewarnungen AT mind. bis 2026-07-11 bekannt);
  Tests dürfen laut Vorgabe nicht hart auf eine bestimmte Warnlage
  voraussetzen — ein warnungsfreier Ort liefert korrekt eine leere Liste.
- Die Compare-Mail wird durch die parallele Arbeit in #1110 umgebaut; diese
  Spec verlangt keinen E2E-Beweis über den Compare-Pfad, da derselbe
  Registry-Aufruf (`get_official_alerts_for_location`) verwendet wird und
  damit automatisch profitiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec folgt vollständig dem in #1034/ADR-0016 bereits
  etablierten Registry-/Protocol-Muster (`OfficialAlertSource`,
  `register_official_alert_source()`) und implementiert lediglich eine
  weitere konkrete Quelle innerhalb dieses Vertrags — keine neue
  Architektur-Entscheidung nötig.

## Changelog

- 2026-07-08: Initial spec created (Epic #1073, Issue #1085, Slice 1 —
  erste Nicht-Frankreich-Quelle nach #1034/#1035-Fundament).
