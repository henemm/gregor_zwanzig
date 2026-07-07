# Epic 1033: Amtliche Alerts im Orts-Vergleich

**Status:** Slice 1 (#1034), Slice 2 (#1035), Slice 3 (#1036) und Slice 5 (#1040) implementiert (alle Adversary
VERIFIED) — Slice #1037 offen. Bei #1034 aufgedeckte Nebenbefunde: #1046 (Validator-Vertrag
für Compare-Mail ist veraltet, betrifft die Tabellen-Zählannahme), #1048 (kleinere Politur
F003/F005). Bei #1035 aufgedeckter Nebenbefund: #1056 (Level-2/Gelb wird in `compare_html.py`
fälschlich grün gerendert, kein Scope-Fix in #1035).
**Epic Scope:** Compare-Mail (2 Tabellen + Winner-Box, ≥3 Orte) zeigt zusätzlich amtliche
Behörden-Warnungen pro Ort, sofern eine Datenquelle für den Ort zuständig ist; die Anzeige ist
pro Orts-Vergleich ein-/ausschaltbar (Slice 5, #1040).
**Related Specs:**
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` (Slice 1 — Fundament)
- `docs/specs/modules/issue_1035_vigilance_source.md` (Slice 2 — Météo-France Vigilance,
  implementiert; ersetzt den veralteten Vor-Analyse-Entwurf
  `issue_1035_official_alerts_vigilance.md`, siehe dessen Superseded-Hinweis)
- `docs/specs/modules/issue_1040_alerts_toggle.md` (Slice 5 — Konfiguration/Checkbox, implementiert;
  ersetzt den veralteten Vor-Analyse-Entwurf `issue_1040_official_alerts_config_toggle.md`, siehe
  dessen Superseded-Hinweis)
- `docs/specs/modules/issue_1036_meteo_forets_source.md` (Slice 3 — Météo des forêts,
  implementiert; ersetzt den veralteten Vor-Analyse-Entwurf
  `issue_1036_official_alerts_meteo_forets.md`, siehe dessen Superseded-Hinweis)
- `docs/specs/modules/issue_1037_official_alerts_massif_closure.md` (Slice 4 — Massiv-Sperrungen)

**Related ADR:** `docs/adr/0016-amtliche-warnungen-additiver-typ.md`

**Child Issues:** #1034, #1035, #1040, #1036, #1037 (alle Teil von Epic #1033)

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

Zusätzlich (PO-Anforderung 2026-07-06): Die amtlichen Warnungen müssen **pro Orts-Vergleich
ein-/ausschaltbar** sein — eine Checkbox im Editor (Slice 5, Issue #1040).

**Nutzerfall:** Ein Nutzer vergleicht vor einer Reise mehrere mögliche Orte. Neben der reinen
Wetterprognose sieht er sofort, ob für einen Ort eine amtliche Wetterwarnung gilt, hohe
Waldbrandgefahr herrscht oder ein zugehöriges Wander-Massiv aktuell gesperrt ist — ohne eine
zweite Quelle konsultieren zu müssen. Wer die Warnungen nicht sehen möchte, schaltet sie im
Editor mit einer Checkbox ab.

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
├── department_mapper.py     # Lat/Lon → Département, landesweit, inkl. Korsika 2A/2B (Slice 2)
├── vigilance.py              # VigilanceSource (Slice 2, implementiert)
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
| `src/output/renderers/comparison.py` (`render_comparison_text`) | Plain-Text-Parität (Slice 2, implementiert) |

### Konfigurierbarkeit (Slice 5, PO-Anforderung 2026-07-06)

Amtliche Warnungen sind pro Orts-Vergleich ein-/ausschaltbar, Default an:

- **Preset-Feld:** `internal/model/compare_preset.go` (`ComparePreset.OfficialAlertsEnabled *bool`,
  Pointer-Muster analog dem bestehenden `Weekday *int` — `nil` = "im JSON nicht gesetzt", Default
  `true` wird beim Lesen interpretiert, nie beim Schreiben erzwungen).
- **Merge-Pflicht:** `internal/handler/compare_preset.go` (`UpdateComparePresetHandler`) muss das
  Feld nach demselben Read-Modify-Write-Muster behandeln wie `ForecastHours`/`PreviousSchedule`
  (bereits im Handler vorhanden) — sonst Datenverlust bei Clients, die das Feld nicht kennen.
- **Python-Engine:** `ComparisonEngine.run()` bekommt `include_official_alerts: bool = True`; bei
  `False` wird `get_official_alerts_for_location()` für keine Location aufgerufen — **kein
  Fetch**, nicht nur ein ausgeblendeter Renderer-Block. `send_one_compare_preset()`
  (`src/services/scheduler_dispatch_service.py`, gemeinsamer Pfad für täglichen Scheduler-Lauf
  und manuellen "Senden"-Button) liest das Flag aus dem Preset-Dict und reicht es durch.
- **Frontend:** Checkbox im Compare-Editor (`frontend/src/lib/components/compare/`), wiederverwendet
  ein bestehendes Form-Atom (`atoms/Switch.svelte` oder `ui/checkbox`) — keine neue
  UI-Architektur.
- **Wichtige Abgrenzung:** Der Legacy-Pfad `CompareSubscription`/`compare_subscriptions.json`
  (Issue #456, `/api/subscriptions/{id}/send`) ist außerhalb des produktiven Scheduler-/
  Editor-Flusses und wird von Slice 5 nicht angefasst — die einzige Quelle der Wahrheit für den
  Orts-Vergleich ist `compare_presets.json` (Go-Modell, editiert im Frontend).

### Aus Vorgängerprojekt wiederverwendbare Muster (nur als Referenz, nicht kopiert)

Ein früheres, nicht in Produktion befindliches Projekt (`weather_email_autobot`) enthält bereits
funktionierende Bausteine für Vigilance-Zugriff und Département-Mapping. Diese Muster flossen
als Vorlage in Slice 2 ein — **committete Zugangsdaten aus diesem Projekt sind ungültig und
dürfen nicht übernommen werden**, es braucht eine frische Météo-France-Portal-Registrierung.
**Korrektur (Analyse-Phase #1035):** Das ursprünglich angenommene OAuth2-Client-Credentials-
Verfahren existiert für den tatsächlich genutzten Endpoint nicht — Vigilance authentifiziert
über einen einfachen `apikey`-HTTP-Header (`GZ_METEOFRANCE_APIKEY`), kein
`meteo_token_provider.py` nötig.

---

## Slices

### Slice 1: Fundament (Issue #1034) — implementiert (2026-07-06, Adversary VERIFIED)

Datenmodell, Registry, Geo-Scope-Vorfilter, Verdrahtung in `ComparisonEngine`/`LocationResult`,
Renderer-Block in der Compare-Mail. Noch keine echte Quelle registriert — Plumbing wird mit
einer Test-Fake-Quelle bewiesen. **Abweichung vom ursprünglichen Vorschlag:** Fundament und
Vigilance wurden getrennt (statt in einem Slice), weil beides zusammen das LoC-Budget von ±250
gesprengt hätte.

Neues Paket `src/services/official_alerts/` (`models.py`: `OfficialAlert`-Dataclass; `base.py`:
`OfficialAlertSource`-Protocol, Registry, fail-soft `get_official_alerts_for_location()`).
`LocationResult.official_alerts` (transient, keine Persistenz) wird im Erfolgszweig von
`ComparisonEngine.run()` angereichert. `_render_official_alerts_block()` in `compare_html.py`
rendert div/span-Badges (kein `<table>`) vor der Vergleichsmatrix, farbcodiert über die
bestehenden `G_SUCCESS`/`G_WARNING`/`G_DANGER`-Tokens. Spec:
`docs/specs/modules/issue_1034_official_alerts_foundation.md`.

**Nebenbefunde bei der Adversary-Prüfung:**
- **#1046:** Der bei der Analyse zugrunde gelegte Validator-Vertrag für die Compare-Mail
  (`email_spec_validator.py`, „exakt 2 `<table>`-Tags") war bereits seit Issue #460 veraltet —
  betrifft nur die Spec-Formulierung der ACs (korrigiert, siehe AC-2), nicht die Slice-1-Logik
  selbst.
- **#1048:** Kleinere Politur-Punkte F003/F005 aus dem Adversary-Dialog, ohne AC-Bezug — separat
  nachgezogen.

### Slice 2: Météo-France Vigilance (Issue #1035) — implementiert (2026-07-06, Adversary VERIFIED)

Erste echte Quelle: Wetterwarnungen (Gewitter, Sturmböen, extreme Hitze) über die amtliche
Météo-France-Vigilance-API (`GET .../DPVigilance/v1/cartevigilance/encours`, `apikey`-Header,
kein OAuth2 — siehe Korrektur oben). `VigilanceSource` liefert Alerts ab Level ≥2 (gelb) für
Phänomene Sturmböen/Gewitter/Extreme Hitze. Bringt `department_mapper.py` (Nearest-Centroid,
volle Metropole + Korsika 2A/2B) mit, das Slice 3 wiederverwendet. Text-Renderer-Parität in
`render_comparison_text()` ergänzt (HTML-Badge war bereits aus Slice 1 verdrahtet). Spec:
`docs/specs/modules/issue_1035_vigilance_source.md`.

**Nebenbefund bei der Adversary-Prüfung:**
- **#1056:** `compare_html.py` (`_render_official_alerts_block()`, aus Slice 1) mappt Level 1–2
  fälschlich auf Grün, obwohl Level 2 (gelb) bereits ein Warnsignal ist — bewusst kein Scope-Fix
  in #1035, separates Folge-Issue.

### Slice 3: Météo des forêts (Issue #1036) — implementiert (2026-07-07, Adversary VERIFIED)

Dritte Quelle: Waldbrand-Gefahrenstufe (1–4) auf Département-Ebene, nur Juni–September verfügbar
(außerhalb der Saison liefert `covers()` `False`, keine API-Calls). `MeteoForetsSource` ruft den
département-scoped JSON-Endpoint `.../DPMeteoForets/v1/carte/departement/encours` ab (gleicher
`apikey`-Header wie Vigilance, kein OAuth2, kein CSV-Fallback nötig) und liefert
`OfficialAlert(hazard="wildfire_risk", level=1-4)` — ohne Mindest-Schwellwert (jede Stufe 1–4
erscheint als Badge, anders als Vigilance ab Level ≥2). Baut auf #1034 (Registry-Plumbing) und
#1035 (Département-Mapping) auf. Badge-Renderer aus Slice 1 verdrahtet, fail-soft bei fehlender
API-Authentifizierung oder Netzwerkfehler. Spec: `docs/specs/modules/issue_1036_meteo_forets_source.md`.

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

### Slice 5: Konfiguration — „Amtliche Warnungen anzeigen" (Issue #1040) — implementiert (2026-07-07, Adversary VERIFIED)

Full-Stack-Slice (Go-Modell/Handler + Python-Engine + Svelte-Editor): bool-Feld
`ComparePreset.OfficialAlertsEnabled *bool` (Pointer-Muster, Default `true`), Read-Modify-Write-
Merge im `UpdateComparePresetHandler`, `ComparisonEngine.run(official_alerts_enabled=True)`
überspringt bei ausgeschaltetem Flag den Fetch komplett (nicht nur die Anzeige), Checkbox in
`Step5Versand.svelte` (Vorbild `ChannelToggle`). Baut nur auf #1034 auf, ist aber erst nach #1035
sinnvoll nutzbar (siehe Details oben unter "Konfigurierbarkeit"). Spec:
`docs/specs/modules/issue_1040_alerts_toggle.md`.

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
- **Slice 5 berührt drei Schichten parallel** (Go-Preset-Modell + Python-Engine +
  Svelte-Editor) — Read-Modify-Write-Merge im Go-Handler ist Pflicht (Projektregel
  Daten-Schema-Reworks), sonst Risiko eines Datenverlusts bei anderen Preset-Feldern.

## Out of Scope

- FR-Alert (Cell-Broadcast, keine Pull-API) und franceinfo (reines Medien-Frontend von
  Vigilance) — beide keine geeignete Datenquelle.
- Trip-Briefing-Integration — Architektur ist vorbereitet (gemeinsame Registry mit Lat/Lon-Input),
  die tatsächliche Anbindung ist ein separater Folge-Ausbau.
- Andere Länder (Österreich, Deutschland, Schweiz) — Geo-Scope bewusst auf Frankreich begrenzt.
- Echte Polygon-basierte Massiv-Grenzen (FlatGeobuf) — siehe Slice 4.
- **Nowcast-/Radar-Alerts für Trips** (`src/services/trip_alert.py`, ADR-0009/0011) haben bereits
  eine eigene Alert-Konfiguration (Alert-Config-UI, Issue #586) und sind von diesem Epic
  vollständig unberührt — die Slice-5-Checkbox betrifft ausschließlich amtliche Warnungen im
  Orts-Vergleich, keine Trip-Δ-Alerts.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-06 | Epic angelegt, 4 Slices gescoped, ADR-0016 geschrieben, Issues #1033–#1037 erstellt. |
| 2026-07-06 | Scope-Korrektur (PO): Côte d'Azur wird Leitszenario statt GR20, zeitliche Priorität (~2 Wochen bis Urlaub) ergänzt, Slice 4 auf generischen département-basierten Mechanismus umgestellt (keine GR20-Hartkodierung). |
| 2026-07-06 | Neue PO-Anforderung: Slice 5 (#1040) hinzugefügt — amtliche Warnungen pro Orts-Vergleich ein-/ausschaltbar (Full-Stack: Go-Preset-Modell, Python-Engine-Flag mit Fetch-Skip, Svelte-Checkbox), Out-of-Scope-Abgrenzung zu Trip-Alert-Config (#586) ergänzt. |
| 2026-07-06 | Slice 1 (#1034) implementiert, Adversary VERIFIED. Nebenbefunde als Folge-Issues erfasst: #1046 (veralteter Validator-Vertrag, entdeckt bei der Analyse), #1048 (Politur F003/F005 aus dem Adversary-Dialog). |
| 2026-07-06 | Slice 2 (#1035) implementiert, Adversary VERIFIED. Analyse-Korrektur: OAuth2-Client-Credentials-Verfahren verworfen zugunsten von einfachem `apikey`-Header (kein `meteo_token_provider.py`); Endpoint auf `cartevigilance/encours` (nationale Antwort statt Punkt-Bulletin) korrigiert. Nebenbefund #1056 (Level-2/Gelb-Farbmapping in `compare_html.py`) erfasst. |
| 2026-07-07 | Slice 5 (#1040) implementiert, Adversary VERIFIED. Analyse-Korrektur ggü. Vor-Analyse-Entwurf: Engine-Parametername `official_alerts_enabled` (statt `include_official_alerts`), Checkbox in `Step5Versand.svelte` (statt `Step4Layout.svelte`). |
| 2026-07-07 | Slice 3 (#1036) implementiert, Adversary VERIFIED. Analyse-Korrektur ggü. Vor-Analyse-Entwurf: kein OAuth2/CSV-Pfad, sondern gleicher `apikey`-Header wie Vigilance gegen den département-scoped JSON-Endpoint `carte/departement/encours`. MeteoForetsSource registriert in `__init__.py`, liefert Waldbrand-Gefahrenstufe 1–4 für französische Orte Juni–September (außerhalb Saison `covers()` = False), ohne Mindest-Schwellwert, fail-soft bei fehlender API oder Netzwerkfehler. Badge-Renderer bereits aus Slice 1 verdrahtet, keine neuen Renderer-Dateien nötig. |
