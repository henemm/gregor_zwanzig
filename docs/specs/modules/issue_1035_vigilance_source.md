---
entity_id: issue_1035_vigilance_source
type: feature
created: 2026-07-06
updated: 2026-07-06
status: implemented
version: "1.0"
workflow: feature-1035-vigilance-alerts
tags: [compare, alerts, official-alerts, meteofrance]
---

# Vigilance Source — Météo-France Amtliche Warnungen (Slice 2)

## Approval

- [x] Approved

## Purpose

Erste echte Datenquelle für die in #1034 gebaute Official-Alerts-Registry: `VigilanceSource`
ruft die amtliche Météo-France-Vigilance-API ab und liefert Gewitter-, Sturmböen- und
Extreme-Hitze-Warnungen für Frankreich (Metropole inkl. Korsika) im Orts-Vergleich — damit sieht
ein Nutzer im Compare erstmals eine echte behördliche Warnung statt der leeren Registry aus #1034.

## Source

- **File:** `src/services/official_alerts/vigilance.py`
- **Identifier:** `class VigilanceSource`

> **Schicht:** Python-Core/Domain-Backend (`src/services/`, `src/output/renderers/`).

## Estimated Scope

- **LoC:** ~150–220 src-LoC (Département-Zentroid-Tabelle zählt als Daten mit; Limit 250,
  ohne großen Puffer — bei Bedarf `loc_limit_override` erst nach Rückfrage beim User)
- **Files:** 4 neu (`vigilance.py`, `department_mapper.py`, Testdateien), 2 geändert
  (`official_alerts/__init__.py`, `output/renderers/comparison.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::OfficialAlertSource` | Protocol (bindend, #1034) | `VigilanceSource` implementiert `name`/`covers()`/`fetch()` strukturell |
| `src/services/official_alerts/base.py::register_official_alert_source` | Registry (bindend, #1034) | Lazy-Registration bei Modul-Import |
| `src/services/official_alerts/models.py::OfficialAlert` | Datentyp (bindend, #1034) | `fetch()` befüllt bestehende Felder, keine Schema-Änderung |
| `src/services/radar_service.py:38-42` (`_AROME_FR_LAT_MIN/MAX/LON_MIN/MAX`) | Code-Wiederverwendung | Frankreich-Bbox als `covers()`-Vorfilter (kein API-Call) |
| `httpx` | Bestehende Dependency | HTTP-GET gegen `public-api.meteofrance.fr` |
| `GZ_METEOFRANCE_APIKEY` (ENV) | Zugangsdaten | `apikey`-Header, bereits in Prod-/Staging-`.env` hinterlegt |
| `src/output/renderers/comparison.py::render_comparison_text()` | Integration | Text-Zeile pro Ort mit `official_alerts` |

## Implementation Details

**Verifizierter Endpunkt** (echter API-Call durchgeführt, 2026-07-06):
`GET https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours`,
Auth via HTTP-Header `apikey: <GZ_METEOFRANCE_APIKEY>` (kein OAuth2). Eine einzige nationale
JSON-Antwort für alle Départements: `product.periods[]` mit `echeance` (`"J"`=heute,
`"J1"`=morgen), je Periode `begin_validity_time`/`end_validity_time` und
`timelaps.domain_ids[]` (`{"domain_id": "83", "max_color_id": 1, "phenomenon_items": [...]}`).

Phänomen-ID-Mapping (Scope nur `1`, `3`, `6`):
`1`=Vent violent → `hazard="wind_gust"`, `3`=Orages → `hazard="thunderstorm"`,
`6`=Canicule → `hazard="extreme_heat"`. Level-Skala 1=grün/2=gelb/3=orange/4=rot; **geliefert
werden Alerts ab Level ≥2**.

```python
# src/services/official_alerts/vigilance.py (Skizze, kein Volltext)
class VigilanceSource:
    name = "meteofrance_vigilance"

    def covers(self, lat: float, lon: float) -> bool:
        return (_AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
                and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX)

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
            _warn_once_missing_key()
            return []
        dept = lookup_department(lat, lon)
        if dept is None:
            return []
        data = _get_cached_cartevigilance()  # TTL ~5-10 Min, Modul-Level-Cache
        return _extract_alerts(data, dept)   # filtert phenomenon_id in {1,3,6}, level>=2
```

`department_mapper.py`: statische Zentroid-Tabelle (`Dict[str, tuple[float, float]]`), volle
Metropole (~96 Einträge) plus Korsika als zwei normale Zeilen (`"2A"`, `"2B"`) — keine
Sonderfall-Logik. `lookup_department(lat, lon)` sucht per euklidischer Nächste-Nachbar-Distanz
den passenden Code (kein Geo-Package-Dependency). Datenquelle: öffentliche INSEE-Zentroid-Daten,
während der Implementierung einzubetten.

Caching: einfacher In-Memory-Modul-Level-Cache (Dict mit Timestamp, TTL 5–10 Min) — kein neues
Framework, keine Wiederverwendung von `WeatherCacheService` (typisiert auf `SegmentWeatherData`).

`valid_from`/`valid_to` (bestehende `OfficialAlert`-Felder) werden je Alert aus
`begin_validity_time`/`end_validity_time` der jeweiligen Periode (`J` oder `J1`) befüllt — beide
Horizonte werden abgebildet.

Registrierung: `official_alerts/__init__.py` importiert `vigilance` und ruft
`register_official_alert_source(VigilanceSource())` beim Modul-Import auf (Lazy-Registration,
analog Provider-Pattern in `providers/base.py`).

Text-Renderer-Parität: `render_comparison_text()` fügt pro `loc_result` mit nicht-leerer
`official_alerts`-Liste eine zusätzliche Zeile ein — Einhängepunkt direkt nach der bestehenden
"Layer:"-Zeile (`comparison.py:416`), vor dem abschließenden Leerzeilen-Separator
(`comparison.py:417`), z.B. `"   ⚠️ Amtliche Warnung: {alert.label}"`. Für Orte ohne Alerts
bleibt der Text-Block unverändert (Regressionsschutz analog AC-1 aus #1034).

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes (via `get_official_alerts_for_location()`).
- **Output:** Liste von `OfficialAlert` mit `source="meteofrance_vigilance"`,
  `hazard∈{wind_gust,thunderstorm,extreme_heat}`, `level` (Météo-France-Farbstufe 2–4),
  deutschem `label`, `valid_from`/`valid_to` aus der jeweiligen Periode — leer, wenn kein
  Alert vorliegt, die ENV fehlt, oder der Ort außerhalb Frankreichs liegt.
- **Side effects:** höchstens ein HTTP-GET pro Cache-TTL-Fenster (5–10 Min) gegen die
  Météo-France-API; kein Schreiben, keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein Ort an der Côte d'Azur (Var/Alpes-Maritimes/Bouches-du-Rhône) und eine
  aktuell gültige Vigilance-Warnung für Gewitter mit Level ≥3 (orange) zum Testzeitpunkt, When
  die Compare-Mail gerendert wird, Then zeigt genau dieser Ort einen orangen Badge
  ("Gewitter — Vigilance orange") und die anderen verglichenen Orte ohne diese Warnstufe nicht.
  - Test: Echter API-Call gegen die echte Météo-France-API (kein Mock). Da sich der Live-Zustand
    täglich ändert, MUSS der Test tolerant sein: primär gegen einen Ort mit zum Testzeitpunkt
    tatsächlich vorliegender Warnstufe ≥2 prüfen (Level und `hazard` aus der echten Antwort
    ableiten, nicht hart auf "orange"/Gewitter festlegen) und zusätzlich den strukturellen
    Vertrag beweisen (Badge erscheint nur für den betroffenen Ort, `level`/`hazard`/`label`
    entsprechen der von der API gelieferten Kombination). Liegt zum Testzeitpunkt kein Level ≥2
    vor, muss der Test dies erkennen und stattdessen den Datenstruktur-Vertrag (korrektes
    Level/Hazard-Mapping bei einem beliebigen tatsächlich vorliegenden Département-Eintrag)
    nachweisen — niemals ein hartes "es muss orange sein" voraussetzen.

- **AC-2:** Given `GZ_METEOFRANCE_APIKEY` ist nicht gesetzt oder leer, When Compare für einen
  französischen Ort läuft, Then wird die Compare-Mail trotzdem vollständig und ohne Fehler
  versendet, kein Badge/keine Textzeile für diesen Ort, und es wird nur einmalig eine Warnung
  geloggt (kein Crash, kein Retry-Loop).
  - Test: Echter `ComparisonEngine.run()`-Aufruf mit temporär entfernter/leerer ENV-Variable
    für einen Ort mit `covers()==True`; prüfen, dass das Ergebnis vollständig ist, die
    `official_alerts`-Liste für diesen Ort leer bleibt, und `fetch()` keine Exception wirft.

- **AC-3:** Given ein Ort außerhalb Frankreichs (z.B. ein Ort in Österreich), When
  `get_official_alerts_for_location()` für diesen Ort aufgerufen wird, Then wird
  `VigilanceSource.fetch()` NICHT aufgerufen (nur `covers()` liefert `False`).
  - Test: `VigilanceSource`-Instanz mit einem Aufruf-Zähler-Spy um `fetch()` (kein Mock der
    API selbst, sondern ein echtes Objekt mit Call-Counter) gegen einen österreichischen
    Lat/Lon-Wert aufrufen; verifizieren, dass der Zähler bei 0 bleibt und `covers()` `False`
    zurückgibt.

- **AC-4:** Given ein Ort auf Korsika (Département 2A oder 2B) mit einer zum Testzeitpunkt
  tatsächlich vorliegenden Vigilance-Warnung (Level ≥2), When Compare für diesen Ort läuft,
  Then funktioniert die Warnungs-Anzeige identisch zu einem Côte-d'Azur-Ort — gleicher Mapper
  (`lookup_department`), gleiche Quelle (`VigilanceSource`), kein Sonderfall-Code-Pfad.
  - Test: Echter API-Call für einen Korsika-Ort (z.B. Ajaccio oder Bastia, Lat/Lon bekannt);
    prüfen, dass `lookup_department()` `"2A"` bzw. `"2B"` liefert und `fetch()` denselben
    Codepfad wie für Metropole-Départements durchläuft (kein `if department in ("2A","2B")`
    im Produktionscode — geprüft per Code-Grep im Test oder Verhaltensvergleich mit einem
    Metropole-Fall).

- **AC-5:** Given ein verglichener Ort hat eine nicht-leere `official_alerts`-Liste, When
  `render_comparison_text()` aufgerufen wird, Then enthält der Text-Output für diesen Ort eine
  zusätzliche Warnzeile mit dem `label` der Warnung; für Orte ohne `official_alerts` ist der
  Text-Output byte-identisch zur Baseline ohne Alert-Feature.
  - Test: Echten `ComparisonResult` mit einer `LocationResult`, deren `official_alerts` per
    Test-Fake-Quelle (registriert über `register_official_alert_source()`, analog #1034-Muster)
    befüllt ist, durch `render_comparison_text()` rendern; Textzeile für den betroffenen Ort
    prüfen, Abwesenheit für die anderen Orte, und Vergleich mit einer Baseline-Renderung ohne
    registrierte Quelle (identischer Text bis auf die neue Zeile).

## Known Limitations

- Der Département-Mapper ist eine Nearest-Centroid-Näherung (keine Polygon-Genauigkeit) — an
  Département-Grenzen kann in seltenen Randfällen der falsche Nachbar-Code ermittelt werden;
  für Vigilance (das selbst nur Département-Granularität kennt) ausreichend genau.
- Scope ist auf Phänomene `1` (Sturmböen), `3` (Gewitter), `6` (Extreme Hitze) begrenzt — andere
  Phänomene (Starkregen, Schnee/Glätte, Lawinen, etc.) werden bewusst ignoriert.
- Überseeische Départements sind out of scope (durch die Frankreich-Bbox aus `radar_service.py`
  strukturell ausgeschlossen).
- Das Level-Farb-Mapping in `compare_html.py` (`_render_official_alerts_block()`, aus #1034)
  bildet Level 1–2 fälschlich auf Grün ab, obwohl Level 2 (gelb) bereits ein Warnsignal ist. Diese
  Spec verlangt keinen Fix an `compare_html.py` (explizit außerhalb des #1035-Scopes) — Folge-Issue
  #1056 wurde während der Analyse-Phase angelegt.
- Rate-Limit (60 req/min laut Météo-France) ist durch den einzigen gecachten National-Call pro
  TTL-Fenster praktisch irrelevant, aber nicht explizit hart durchgesetzt (kein Retry-/Backoff-
  Mechanismus in diesem Slice).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec folgt vollständig dem in #1034/ADR-0016 bereits etablierten
  Registry-/Protocol-Muster (`OfficialAlertSource`, `register_official_alert_source()`) und
  implementiert lediglich eine konkrete Quelle innerhalb dieses Vertrags — keine neue
  Architektur-Entscheidung nötig.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1035, Slice 2 nach #1034-Fundament).
- 2026-07-06: Implementiert und Adversary VERIFIED. Nebenbefund #1056 (Level-2/Gelb-Farbmapping
  in `compare_html.py`, aus #1034) als Folge-Issue angelegt, kein Scope-Fix in diesem Slice.
