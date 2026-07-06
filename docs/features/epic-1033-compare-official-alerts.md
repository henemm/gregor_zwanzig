# Epic 1033: Amtliche Alerts im Orts-Vergleich

**Status:** Geplant (Slices #1034–#1037 offen — 2026-07-06)
**Epic Scope:** Compare-Mail (2 Tabellen + Winner-Box, ≥3 Orte) zeigt zusätzlich amtliche
Behörden-Warnungen pro Ort, sofern eine Datenquelle für den Ort zuständig ist.
**Related Specs:**
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` (Slice 1 — Fundament)
- `docs/specs/modules/issue_1035_official_alerts_vigilance.md` (Slice 2 — Météo-France Vigilance)
- `docs/specs/modules/issue_1036_official_alerts_meteo_forets.md` (Slice 3 — Météo des forêts)
- `docs/specs/modules/issue_1037_official_alerts_massif_closure.md` (Slice 4 — Massiv-Sperrungen)

**Related ADR:** `docs/adr/0016-amtliche-warnungen-additiver-typ.md`

**Child Issues:** #1034, #1035, #1036, #1037 (alle Teil von Epic #1033)

---

## Overview

Der Orts-Vergleich vergleicht Wetterdaten für ≥3 Orte in einer E-Mail (2 Tabellen + Winner-Box).

**Leitszenario (PO):** Urlaub an der **Côte d'Azur in ca. 2 Wochen** (Ziel-Zeitraum ab
2026-07-20), Vergleich von Orten in den Départements **Var (83)**, **Alpes-Maritimes (06)** und
**Bouches-du-Rhône (13)**. Behörden können dort unabhängig vom Wetterbericht Warnungen und sogar
Zugangssperren aussprechen — die reine Wetter-Metrik reicht nicht. **GR20/Korsika ist ein
zweiter, gleichrangig unterstützter Anwendungsfall** (und Quelle wiederverwendbarer Vorarbeit aus
einem früheren Projekt), nicht mehr das primäre Zielbild.

Dieses Epic bringt drei amtliche französische Datenquellen additiv in die Compare-Mail:

1. **Météo-France Vigilance** — Wetterwarnungen (Gewitter, Sturmböen, extreme Hitze) — höchste
   Priorität, deckt den größten Alltagsnutzen für einen Sommerurlaub ab
2. **Météo des forêts** — Waldbrand-Gefahrenstufe (nur Juni–September, **aktuell laufende
   Saison**) — zweite Priorität
3. **Massiv-Betretungsverbote** — Präfektur-Zugangssperren einzelner Wander-Massive (Var,
   Alpes-Maritimes, Bouches-du-Rhône, Korsika) — dritte Priorität, aber hoher konkreter
   Urlaubs-Mehrwert im Var; architektonisch der aufwendigste Slice

**Nutzerfall:** Ein Nutzer vergleicht vor einer Reise mehrere mögliche Orte. Neben der reinen
Wetterprognose sieht er sofort, ob für einen Ort eine amtliche Wetterwarnung gilt, hohe
Waldbrandgefahr herrscht oder ein zugehöriges Wander-Massiv aktuell gesperrt ist — ohne eine
zweite Quelle konsultieren zu müssen.

---

## Architecture

### Warum ein neuer, additiver Datentyp (nicht Wiederverwendung bestehender Alert-Systeme)

Das Projekt kennt bereits zwei Alert-verwandte Konzepte:

- **`WeatherProvider`** (`src/providers/base.py`) — Zeitreihen-Vorhersagen von Wetterdiensten.
- **Δ-Abweichungs-Alerts** (ADR-0009, `src/services/trip_alert.py`) — melden Abweichung vom
  letzten Briefing-Snapshot, keine absoluten Schwellen.

Amtliche Warnungen sind fachlich ein drittes Konzept: eine **absolute, extern fertige
Behörden-Einstufung** (siehe ADR-0016 für die vollständige Abgrenzung und verworfene
Alternativen). Deshalb: eigener Datentyp `OfficialAlert`, eigenes Quellen-Interface
`OfficialAlertSource`, eigene Registry — additiv, ohne bestehende Pfade zu verändern.

### Modul-Struktur

```
src/services/official_alerts/
├── __init__.py
├── models.py              # OfficialAlert-Dataclass
├── base.py                # Protocol + Registry + get_official_alerts_for_location()
├── meteo_token_provider.py  # OAuth2-Client-Credentials (Slice 2, Wiederverwendung Slice 3)
├── department_mapper.py     # Lat/Lon → Département, landesweit, inkl. Korsika 2A/2B (Slice 2)
├── vigilance.py              # VigilanceSource (Slice 2)
├── meteo_forets.py           # MeteoForetsSource (Slice 3)
├── massif_zones.py            # generische Département → Massiv-Zonen-Tabelle (Slice 4)
└── massif_closure.py          # MassifClosureSource (Slice 4)
```

### Geo-Wirkungsrahmen-Muster (wiederverwendet)

Analog zu `src/services/radar_service.py:26-49` (RADOLAN/INCA/AROME-Bounding-Boxen) und
`src/services/comparison_engine.py:262-277` (`_select_provider_for_location`): jede
`OfficialAlertSource` implementiert `covers(lat, lon) -> bool` als billigen Vorfilter, bevor
`fetch()` (potenziell teurer HTTP-Call) aufgerufen wird. Für Météo des forêts kommt zusätzlich
ein Saisonalitäts-Check hinzu (`covers()` liefert außerhalb Juni–September `False`).

### Registry & Fail-soft-Garantie

```python
# src/services/official_alerts/base.py
def get_official_alerts_for_location(lat: float, lon: float) -> list[OfficialAlert]:
    results: list[OfficialAlert] = []
    for source in _REGISTERED_SOURCES:
        if not source.covers(lat, lon):
            continue
        try:
            results.extend(source.fetch(lat, lon))
        except Exception:
            logger.warning("official_alerts: %s fetch failed", source.name, exc_info=True)
            continue  # eine ausgefallene Quelle blockiert nie die anderen
    return results
```

Diese Fail-soft-Garantie ist die zentrale Eigenschaft des ganzen Epics: eine tote Quelle, ein
Auth-Fehler, eine Saison-Pause — nichts davon darf die Compare-Mail verhindern. Sie zeigt dann
schlicht keine zusätzliche amtliche Warnung für den betroffenen Ort.

### Integrationspunkte

| Datei | Änderung |
|---|---|
| `src/app/user.py` (`LocationResult`) | additives Feld `official_alerts: list[OfficialAlert]` |
| `src/services/comparison_engine.py` (`ComparisonEngine.run()`) | pro Location `get_official_alerts_for_location(loc.lat, loc.lon)` aufrufen |
| `src/output/renderers/email/compare_html.py` (`render_compare_html`) | Badge/Zeile pro Ort, farbcodiert nach Level |
| `src/services/comparison_renderers.py` (`render_comparison_text`) | Plain-Text-Parität |

### Aus Vorgängerprojekt wiederverwendbare Muster (nur als Referenz, nicht kopiert)

Ein früheres, nicht in Produktion befindliches Projekt (`weather_email_autobot`) enthält bereits
funktionierende Bausteine für Vigilance-OAuth2 und Département-Mapping. Diese Muster fließen
in Slice 2 als Vorlage ein — **committete Zugangsdaten aus diesem Projekt sind ungültig und
dürfen nicht übernommen werden**, es braucht eine frische Météo-France-Portal-Registrierung
(siehe Epic #1033, Abschnitt "Voraussetzung").

---

## Slices

### Slice 1: Fundament (Issue #1034)

Datenmodell, Registry, Geo-Scope-Vorfilter, Verdrahtung in `ComparisonEngine`/`LocationResult`,
Renderer-Block in der Compare-Mail. Noch keine echte Quelle registriert — Plumbing wird mit
einer Test-Fake-Quelle bewiesen. **Abweichung vom ursprünglichen Vorschlag:** Fundament und
Vigilance wurden getrennt (statt in einem Slice), weil beides zusammen das LoC-Budget von ±250
gesprengt hätte.

### Slice 2: Météo-France Vigilance (Issue #1035)

Erste echte Quelle: Wetterwarnungen (Gewitter, Sturmböen, extreme Hitze) über OAuth2-Portal-API.
Bringt OAuth2-Token-Provider und Département-Mapping (inkl. Korsika 2A/2B) mit, die Slice 3
wiederverwendet.

### Slice 3: Météo des forêts (Issue #1036)

Waldbrand-Gefahrenstufe, nur Juni–September verfügbar. Baut auf #1034 und #1035
(Département-Mapping, ggf. OAuth2-Client) auf.

### Slice 4: Massiv-Betretungsverbote (Issue #1037)

Präfektur-Zugangssperren einzelner Wander-Massive über einen inoffiziellen JSON-Endpoint.
**Bewusst ohne neue FlatGeobuf/Geometrie-Abhängigkeit** — statt echter Point-in-Polygon-Prüfung
wird eine statische Zentrum+Radius-Zonentabelle je Massiv verwendet.

**Scope-Korrektur 2026-07-06:** Der ursprüngliche Entwurf hatte diese Tabelle GR20-spezifisch
kodiert (reine Portierung von `gr20_zone_massif_ids.py`). Das ist korrigiert: der Mechanismus ist
jetzt **département-generisch** (`MASSIF_ZONES: dict[str, list[MassifZone]]`, keyed by
Département-Code über denselben `department_mapper.py` aus Slice 2). Die Korsika-Daten aus dem
Vorgängerprojekt sind nur die Datenquelle für die 2A/2B-Einträge dieser generischen Tabelle; für
Var (83), Alpes-Maritimes (06) und Bouches-du-Rhône (13) müssen die Massiv-Zonen in diesem Slice
neu recherchiert werden (kein wiederverwendbares Vorarbeit-Material vorhanden). Deckt damit
sowohl das primäre Côte-d'Azur-Szenario als auch GR20/Korsika über denselben Code-Pfad ab;
Erweiterung auf weitere Départements oder echte Polygon-Geometrie ist inkrementell möglich, ohne
den Mechanismus zu ändern.

---

## Risiken

- **Inoffizieller Endpoint (Slice 4):** kein dokumentiertes API, Struktur kann sich ändern —
  defensives Parsing + Monitoring/`last_run` sind Teil der Slice-4-Spec.
- **Saisonalität (Slice 3):** Météo des forêts liefert nur Juni–September.
- **Lizenz:** Météo-France-Daten unter Etalab 2.0 — Attribution im Mail-Footer nötig, sobald eine
  amtliche Warnung angezeigt wird.
- **Betreiber-Voraussetzung:** Vigilance + Météo des forêts benötigen einen kostenlosen
  Météo-France-Portal-Account (einmalige Registrierung durch den Betreiber, keine Codearbeit) —
  angesichts der ~2-Wochen-Frist zeitnah anzustoßen.
- **Neue Recherche-Unsicherheit (Slice 4):** Massiv-Zonen für Var/Alpes-Maritimes/
  Bouches-du-Rhône müssen erstmals kuratiert werden (anders als Korsika, wo bereits fachlich
  verifiziertes GR20-Material vorliegt).

## Out of Scope

- FR-Alert (Cell-Broadcast, keine Pull-API) und franceinfo (reines Medien-Frontend von
  Vigilance) — beide keine geeignete Datenquelle.
- Trip-Briefing-Integration — Architektur ist vorbereitet (gemeinsame Registry mit Lat/Lon-Input),
  die tatsächliche Anbindung ist ein separater Folge-Ausbau.
- Andere Länder (Österreich, Deutschland, Schweiz) — Geo-Scope bewusst auf Frankreich begrenzt.
- Echte Polygon-basierte Massiv-Grenzen (FlatGeobuf) — siehe Slice 4.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-06 | Epic angelegt, 4 Slices gescoped, ADR-0016 geschrieben, Issues #1033–#1037 erstellt. |
| 2026-07-06 | Scope-Korrektur (PO): Côte d'Azur wird Leitszenario statt GR20, zeitliche Priorität (~2 Wochen bis Urlaub) ergänzt, Slice 4 auf generischen département-basierten Mechanismus umgestellt (keine GR20-Hartkodierung). |
