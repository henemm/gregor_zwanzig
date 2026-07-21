---
entity_id: issue_1086_meteoalarm_source
type: feature
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
workflow: feat-1086-meteoalarm-source
tags: [compare, alerts, official-alerts, meteoalarm, austria, italy]
---

# MeteoAlarm-Quelle — Österreich/Italien Doppelabdeckung (Slice 2, Epic #1073)

## Approval

- [ ] Approved

## Purpose

`MeteoAlarmSource` ist die zweite Nicht-Frankreich-Quelle für die bestehende
Official-Alerts-Registry (#1034): sie ruft die amtliche OGC-EDR-API
`api.meteoalarm.org` ab und bringt **Italien** erstmals in die amtlichen
Warnungen (für IT praktisch die einzige frei verfügbare amtliche Quelle).
Zusätzlich deckt sie **Österreich redundant mit** `GeoSphereWarnSource`
(#1085) ab — PO-Entscheidung: beide Quellen bleiben für AT aktiv (Ausfall
einer Quelle wird durch die andere kompensiert), Duplikate werden über die
bestehende `dedupe_official_alerts()`-Identitäts-Dedup zu je EINER Warnung
pro Ort und Gefahr zusammengeführt, damit der Nutzer nicht zweimal dieselbe
Warnung sieht.

## Source

- **File:** `src/services/official_alerts/meteoalarm.py`
- **Identifier:** `class MeteoAlarmSource`

> **Schicht:** Python-Core/Domain-Backend (`src/services/official_alerts/`,
> `src/output/renderers/alert/`).

## Estimated Scope

- **LoC:** ~230–300 src-LoC (zweistufiger Abruf: Länder-Index → Punkt-in-
  Fläche-Filter → CAP-XML-Nachladen → Mapping — deutlich mehr als
  `geosphere_warn.py`, plus die kleine geteilte Normalisierungs-Funktion und
  die minimale `geosphere_warn.py`-Ergänzung für den Dedup-Kollisionsweg).
  Kann das 250-LoC-Workflow-Limit überschreiten; `loc_limit_override` erst
  nach expliziter Rückfrage beim User setzen (Projektregel — kein
  Override ohne Freigabe), nicht selbstständig während der Implementierung.
- **Files:** 3 neu (`meteoalarm.py`, Testdatei, versionierte Fixture-Dateien
  unter `tests/fixtures/meteoalarm/`), 3 geändert
  (`official_alerts/__init__.py`, `official_alerts/base.py`
  [Punkt-Kollaps in `get_official_alerts_for_location`],
  `output/renderers/alert/official_alerts.py` [nur `_SOURCE_LABELS`]).
  `geosphere_warn.py` wird NICHT mehr geändert (Korrektur nach F001/F002).
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::OfficialAlertSource` | Protocol (bindend, #1034) | `MeteoAlarmSource` implementiert `name`/`covers()`/`fetch()` strukturell |
| `src/services/official_alerts/base.py::register_official_alert_source` | Registry (bindend, #1034) | Lazy-Registration bei Modul-Import, NACH `GeoSphereWarnSource` (Reihenfolge relevant für Dedup-Tie-Break, s. u.) |
| `src/services/official_alerts/models.py::OfficialAlert` | Datentyp (bindend, #1034/#1217) | `fetch()` befüllt bestehende Felder inkl. `dedup_id` — keine Schema-Änderung |
| `src/output/renderers/alert/official_alerts.py::dedupe_official_alerts` | Bestehende Dedup-Logik (bindend, #1172/#1200/#1217/#1218) | Bleibt UNVERÄNDERT; der Cross-Source-Kollaps geschieht stattdessen pro Punkt in `get_official_alerts_for_location()` — nicht über `dedup_id` (Adversary F002) |
| `src/services/official_alerts/base.py::get_official_alerts_for_location` | Aggregations-Punkt (MODIFY) | Fasst pro einzelnem `(lat,lon)` Alerts gleicher `hazard` zu einem zusammen (höchste `level`, Tie-Break = zuerst registrierte Quelle); ortsübergreifende Kollision strukturell ausgeschlossen |
| `src/services/official_alerts/geosphere_warn.py::GeoSphereWarnSource` (#1085) | Unverändert | Bleibt gegenüber #1085 unangetastet (kein neues Feld, kein `dedup_id`) — behebt zugleich F001 |
| `src/services/radar_service.py:33-36,45-49` (`_INCA_*`, `_DPC_*`) | Code-Wiederverwendung | AT- (`_INCA_*`) ∪ IT-Bbox (`_DPC_*`) als `covers()`-Vorfilter (kein API-Call) |
| `httpx` | Bestehende Dependency | HTTP-GET gegen `api.meteoalarm.org` (Index) + CAP-XML-Nachladen (`hubLink`, auth-frei) |
| `xml.etree.ElementTree` (Standardlib) | Bestehendes Muster (keine neue Dependency) | CAP-XML-Parsing |
| `GZ_METEOALARM_APIKEY` (ENV) | Zugangsdaten | Bearer-Token für den Index-Call, bereits in Prod-/Staging-`.env` hinterlegt (verifiziert 2026-07-15) |

## Implementation Details

**Verifizierter Endpunkt** (echte Live-Proben 2026-07-15, siehe
`docs/context/feat-1086-meteoalarm-source.md`): OGC-API-EDR,
`https://api.meteoalarm.org/edr/v1`, Collection `warnings`. Die Collection
unterstützt **ausschließlich `data_queries: ['locations']`** — es gibt
**keine** Punktabfrage (`/position?coords=POINT(...)`), anders als im
ursprünglichen Issue-Text skizziert. Pro Land wird abgefragt:

```
GET /collections/warnings/locations/{AT|IT}?datetime=<start>/<end>
Authorization: Bearer <GZ_METEOALARM_APIKEY>
```

`datetime` ist Pflicht, Bereich MUSS < 24h sein (harter API-Fehler sonst),
filtert die **Sendezeit** (`sent_range`), nicht die Gültigkeit. Antwort ist
ein **Index**, max. 100 Features pro Land, **keine Pagination**
(`limit`-Erhöhung wirkungslos, kein `next`-Link, kein `numberMatched`). Pro
Feature: `properties` (`alertId`, `countryCode`, `geometryType: "bbox"`,
`hubTime`, `hubLink`), `geometry` = grobe Bbox, `links[]` mit u. a. `rel:
"geometry"` (exakte geo+json-Fläche) und `rel: "canonical"`/`"xml"`
(CAP-XML, identisch zu `properties.hubLink`). Die eigentlichen Warnfelder
stehen **erst in der nachgeladenen CAP-XML** (`hubLink`, präsignierte URL,
kein Auth):

- `<info xml:lang="…">` mehrsprachig, u. a. deutsch (bestätigt an echter
  AT-Warnung), mit `event`/`headline`, `areaDesc`, `onset`/`expires` (ISO-8601).
- CAP-`<parameter>` `awareness_level` (Format `"2; yellow; Moderate"`) und
  `awareness_type` (Format `"5; high-temperature"`) — jeweils führende
  Ganzzahl vor `;` ist der Schlüssel für Mapping/Filter.

**Sprachwahl (Known Limitation, s. u.):** bevorzugt `<info xml:lang="de*">`,
Fallback `xml:lang="en*"`, sonst der erste vorhandene `<info>`-Block —
italienische Warnungen liefern nicht sicher einen deutschen Text.

```python
# src/services/official_alerts/meteoalarm.py (Skizze, kein Volltext)
class MeteoAlarmSource:
    name = "meteoalarm"

    def covers(self, lat: float, lon: float) -> bool:
        return _in_at_bbox(lat, lon) or _in_it_bbox(lat, lon)

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        alerts: list[OfficialAlert] = []
        for country in ("AT", "IT"):
            index = _get_cached_index(country)  # per-Land-Cache, TTL 300s/60s
            if index is None:
                continue
            for feature in index.get("features", []):
                geometry = _fetch_geometry_link(feature)  # rel="geometry"
                if geometry is None or not _point_in_geometry(lat, lon, geometry):
                    continue
                cap = _fetch_cap(feature["properties"]["hubLink"])  # gecacht
                alerts.extend(_extract_alerts_from_cap(cap))
        return alerts
```

**Mapping (verbindlich, Tech-Lead-Entscheidung aus der Analyse):**

- `level = awareness_level` (führende Ganzzahl), 1:1 identisch zur
  App-Skala (1 grün … 4 rot, `models.py`) — **kein** `+1`-Offset wie bei
  GeoSphere. `level < 2` wird gefiltert (nicht als `OfficialAlert`
  zurückgegeben), analog Vigilance/GeoSphere.
- Hazard-Mapping (`awareness_type`-führende Ganzzahl → `hazard`, bestehendes
  Vokabular, kein Renderer-Hazard-Change):

  | awareness_type | hazard | Bemerkung |
  |---|---|---|
  | 1 (wind) | `wind_gust` | |
  | 2 (snow/ice) | `snow` | |
  | 3 (thunderstorm) | `thunderstorm` | |
  | 5 (high-temperature) | `extreme_heat` | |
  | 6 (low-temperature) | `extreme_cold` | |
  | 8 (forest-fire) | `wildfire_risk` | |
  | 10 (rain) | `rain` | |
  | 12 (rain-flood) | `rain` | Flut-Anteil bewusst verworfen, nur der Regen-Teil bleibt |
  | 4 (fog), 7 (coastal-event), 9 (avalanche), 11 (flood) | — | **übersprungen** (`continue`), keine App-Kategorie — analog unbekannter `warntypid` bei GeoSphere, kein Crash |

- `label` = deutsches (bzw. Fallback-)`event`/`headline` aus CAP.
- `region_label` = `areaDesc` aus CAP.
- `valid_from`/`valid_to` = CAP `onset`/`expires` (ISO-8601-Parser analog
  Vigilance).

**Punkt-in-Fläche-Filter:** einfache Ray-Casting-Implementierung gegen die
GeoJSON-`Polygon`/`MultiPolygon`-Geometrie des `rel="geometry"`-Links (keine
neue Geo-Dependency — konsistent mit dem bereits dependency-freien
`department_mapper.py`-Ansatz aus #1035). Reduziert MeteoAlarm-intern
mehrere Regionen pro Land/Gefahr (z. B. „Villach (Stadt)" + „Villach Land")
auf die real den Punkt enthaltende Region, bevor überhaupt ein
`OfficialAlert` entsteht.

**Cross-Source-Dedup AT (zentraler Design-Punkt dieser Spec — KORRIGIERT
nach Adversary-Befund F002, s. Changelog):** Die Zusammenführung geschieht
**pro einzelnem Ort/Punkt** in `get_official_alerts_for_location(lat, lon)`
(`src/services/official_alerts/base.py`) — NICHT über einen normalisierten
Gemeindenamen-Schlüssel in `dedupe_official_alerts()`.

Begründung (Adversary F002): `dedupe_official_alerts()` (#1172/#1200/#1217/
#1218) wird im Orts-Vergleich (`compare_official_alert.py::_detect`) über die
kombinierte Liste **mehrerer** Vergleichsorte aufgerufen. Ein
ortsübergreifender Schlüssel (etwa ein normalisierter Gemeindename) würde
zwei **verschiedene** Orte mit ähnlichem Namen („Villach (Stadt)" vs.
„Villach Land") fälschlich verschmelzen und über den State-Key
`f"official_alert:{region_label}:{hazard}"` einem Ort die Stufe/den Namen
eines ANDEREN Ortes zuschreiben. Ein Normalisieren des `region_label` bzw.
das Setzen einer normalisierten `dedup_id` ist deshalb **verboten** — es
konflatiert real verschiedene Gemeinden und korrumpiert den Orts-Vergleich
(reproduziert auch für reines GeoSphere, ganz ohne MeteoAlarm).

Verbindliche Lösung — **Kollaps genau dort, wo der Kontext EIN Punkt ist**:

1. `get_official_alerts_for_location(lat, lon)` sammelt wie bisher die Alerts
   aller zuständigen Quellen für DIESEN einen Punkt. NEU: unmittelbar vor
   dem Return werden Alerts mit demselben `hazard` zu genau EINEM
   zusammengefasst — höchste `level` gewinnt; bei gleichem `level` gewinnt
   die **zuerst registrierte** Quelle (Label-/`region_label`-Repräsentant).
   Da dieser Kollaps ausschließlich innerhalb eines einzelnen
   `(lat, lon)`-Aufrufs wirkt, ist eine ortsübergreifende Verwechslung
   strukturell ausgeschlossen.
2. **KEIN** `normalize_gemeinde_name`, **KEIN** `dedup_id` aus
   Gemeindenamen. `GeoSphereWarnSource` bleibt gegenüber #1085 **unverändert**
   (kein neues Feld, keine neue `None`-Fail-Path — behebt zugleich F001).
   `MeteoAlarmSource` setzt `dedup_id=None` (Default).
3. **Tie-Break-Reihenfolge (Label-Präferenz):** `get_official_alerts_for_location()`
   iteriert `_REGISTERED_SOURCES` in Registrierungsreihenfolge; der Kollaps
   behält bei gleichem `level` den ERSTEN. `MeteoAlarmSource` wird deshalb in
   `official_alerts/__init__.py` **NACH** `GeoSphereWarnSource` registriert →
   bei identischem `level` bleibt GeoSphere (gemeindegenaueres Label
   „Villach") Repräsentant; liefert MeteoAlarm eine HÖHERE Stufe, gewinnt
   MeteoAlarm (gewollt).
4. `dedupe_official_alerts()` und die Renderer-Logik bleiben **völlig
   unverändert** (nur `_SOURCE_LABELS` bekommt den `"meteoalarm"`-Eintrag).
   Da nach dem Punkt-Kollaps die `region_label` der Original-Strings erhalten
   bleiben, kollidieren verschiedene Vergleichsorte dort NICHT mehr — der
   ortsübergreifende Dedup-Pfad verhält sich exakt wie vor dieser Spec.
5. **Regressionsschutz:** Der Punkt-Kollaps in `get_official_alerts_for_location()`
   wirkt generisch (auch für die FR-Quellen). Ein Ort/eine Gefahr = ein Alert
   (höchste Stufe) ist eine korrekte Invariante; die bestehenden
   FR-Testfälle (#1035/#1036/#1037) MÜSSEN unverändert grün bleiben
   (AC-6), und die Mehr-Orte-Nicht-Kollision ist als AC-7 abgesichert.

**Fail-soft:** fehlende ENV `GZ_METEOALARM_APIKEY` → `_warn_once_missing_key()`-
Muster (analog `vigilance.py`), `fetch()` liefert `[]`, kein Call. HTTP-
Fehler/Timeout beim Index-Call, beim `geometry`-Link-Abruf oder beim
CAP-XML-Abruf → jeweils try/except, betroffenes Feature/Land wird
übersprungen, `fetch()` wirft nie. Kaputtes JSON (Index) oder kaputtes/
unparsebares XML (CAP) → dieselbe Fail-soft-Behandlung, andere
Features/Länder/Quellen bleiben unberührt (Fehlerisolation bereits durch
`get_official_alerts_for_location()` pro Quelle, hier zusätzlich pro
Feature innerhalb `fetch()`).

**Caching:** per-Land-Index-Cache (Dict-Key = Ländercode), Erfolgs-TTL 300s,
Failure-TTL 60s (F001-Lehre, analog `geosphere_warn.py`/`vigilance.py`).
Zusätzlich ein einfacher Cache für nachgeladene `geometry`-Links und
CAP-XML-Inhalte pro URL (gleiche TTLs) — vermeidet einen HTTP-Call-Sturm bei
wiederholten `fetch()`-Aufrufen für denselben Ort innerhalb des TTL-Fensters
(Known Limitation 3, Milderung). `TIMEOUT = 8.0` (analog bestehende
Quellen).

**Registrierung:** `official_alerts/__init__.py` importiert `meteoalarm`
und ruft `register_official_alert_source(MeteoAlarmSource())` **nach**
`register_official_alert_source(GeoSphereWarnSource())` auf (Reihenfolge
verbindlich, s. o.), plus Export in `__all__`.

**Kreis-Import-Verbot:** kein Import aus `services.comparison_engine`
(analog #1034/#1085). `_SOURCE_LABELS["meteoalarm"] = "MeteoAlarm"` in
`src/output/renderers/alert/official_alerts.py` — dies ist die EINZIGE
Änderung an dieser Datei; `dedupe_official_alerts()` selbst bleibt
unverändert (der Kollisionsweg läuft ausschließlich über `dedup_id`, s. o.).

**Renderer-Commit-Gate #811 (Achtung):** `src/output/renderers/alert/*.py`
ist Teil der gate-relevanten Pfade — der Commit von
`official_alerts.py` verlangt vorher einen grünen Lauf von
`tests/tdd/test_issue_811_mode_matrix.py` und einen frischen
`briefing_mail_validator.py`-Nachweis (bekanntes mechanisches
Gate-Verhalten, kein Bug — im Implementierungs-/Commit-Ablauf einplanen,
analog Implementation Notes in #1034).

## Expected Behavior

- **Input:** Lat/Lon eines verglichenen Ortes bzw. einer Trip-Etappe (via
  `get_official_alerts_for_location()`).
- **Output:** Liste von `OfficialAlert` mit `source="meteoalarm"`,
  `hazard∈{wind_gust,snow,thunderstorm,extreme_heat,extreme_cold,
  wildfire_risk,rain}`, `level∈{2,3,4}`, deutschem (Fallback englischem)
  `label`, `region_label` aus `areaDesc`, `valid_from`/`valid_to` aus
  CAP-`onset`/`expires`, `dedup_id=None` — leer, wenn
  keine Warnung vorliegt, der Ort außerhalb AT/IT liegt, oder die API
  fehlschlägt. Für AT-Orte, die zusätzlich von `GeoSphereWarnSource`
  abgedeckt sind, fasst `get_official_alerts_for_location()` je Gefahr
  bereits pro Punkt zu genau EINEM Alert zusammen (höchste Stufe), nicht zwei.
- **Side effects:** bis zu 2 HTTP-GETs (Index AT+IT) plus N `geometry`- und
  N CAP-XML-Nachlade-Calls pro Cache-TTL-Fenster (300s Erfolg/60s
  Fehlschlag) gegen `api.meteoalarm.org` bzw. `hubLink`-URLs; kein
  Schreiben, keine Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein Punkt in Südtirol (Italien, z. B. Bozen oder Cortina
  nahe der Grenze) mit einer zum Testzeitpunkt tatsächlich aktiven
  amtlichen MeteoAlarm-Warnung, When `MeteoAlarmSource.fetch()` für diesen
  Punkt live aufgerufen wird, Then liefert das Ergebnis mindestens einen
  `OfficialAlert` mit `source="meteoalarm"` und korrektem `hazard`/`level`
  gemäß der dokumentierten Mapping-Tabelle, abgeleitet aus den tatsächlich
  gelieferten `awareness_type`/`awareness_level`-Werten.
  - Test: Live-Marker-Test (kein Mock), echter Index-Call `/locations/IT`,
    echter Punkt-in-Fläche-Filter gegen die reale `geometry`-Antwort,
    echtes CAP-XML-Nachladen. Da die Warnlage tagesabhängig ist, MUSS der
    Test tolerant sein: primär gegen einen Punkt mit zum Testzeitpunkt
    tatsächlich vorliegender Warnung prüfen (Level/Hazard aus der echten
    Antwort ableiten, nicht hart vorgeben); liegt zum Testzeitpunkt keine
    Warnung vor, muss der Test stattdessen den strukturellen Vertrag
    (Index-Call liefert Features, Mapping-Funktion bildet eine
    synthetische, aus der Doku abgeleitete CAP-Struktur korrekt ab)
    nachweisen statt hart auf „nicht leer" zu bestehen.

- **AC-2:** Given ein österreichischer Punkt (z. B. Villach), für den zum
  Testzeitpunkt sowohl `GeoSphereWarnSource` als auch `MeteoAlarmSource`
  dieselbe Gefahr melden (bestätigtes Live-Muster: Hitze + Gewitter, beide
  Quellen, gleiche Stufe), When
  `get_official_alerts_for_location()` gefolgt von
  `dedupe_official_alerts()` für diesen Punkt aufgerufen wird, Then
  erscheint pro Gefahr genau EIN `OfficialAlert` (nicht zwei), mit der
  höchsten der beiden gemeldeten Stufen, und bei gleicher Stufe mit dem
  `region_label`/`label` der GeoSphere-Quelle (Registrierungsreihenfolge
  GeoSphere vor MeteoAlarm).
  - Test: Live-Marker-Test gegen den echten AT-Punkt (kein Mock) — beide
    Quellen real abfragen, `dedupe_official_alerts()` auf das kombinierte
    Ergebnis anwenden, Anzahl der Alerts pro Gefahr prüfen (=1) sowie
    Level/Label-Herkunft. Zusätzlich ein deterministischer Kern-Test mit
    einem synthetischen `GeoSphereWarnSource`-Alert (`region_label="Villach"`,
    `hazard="extreme_heat"`, `level=2`) und einem aus einer aufgezeichneten
    CAP-Fixture erzeugten `MeteoAlarmSource`-Alert (`region_label="Villach
    (Stadt)"`, `hazard="extreme_heat"`, `level=2`): beide erhalten über
    `normalize_gemeinde_name()` dieselbe `dedup_id`, `dedupe_official_alerts()`
    liefert genau einen Eintrag mit dem GeoSphere-Label.

- **AC-3:** Given eine aufgezeichnete CAP-Fixture mit
  `awareness_level="1; green; Minor"`, When die Mapping-Funktion diese CAP-
  Antwort verarbeitet, Then wird für diese Warnung KEIN `OfficialAlert`
  zurückgegeben (Level-1-Filter analog Vigilance/GeoSphere).
  - Test: Deterministischer Kern-Test gegen eine versionierte CAP-XML-
    Fixture mit `awareness_level` Präfix `"1;"`; Ergebnisliste der
    Mapping-Funktion für diese Warnung ist leer bzw. enthält sie nicht.

- **AC-4:** Given eine aufgezeichnete CAP-Fixture mit
  `awareness_type="9; avalanche"` (keine App-Hazard-Kategorie) neben einer
  zweiten Warnung desselben Punktes mit `awareness_type="5;
  high-temperature"`, When die Mapping-Funktion die Antwort verarbeitet,
  Then wird die Lawinen-Warnung übersprungen (kein Eintrag, kein Crash der
  gesamten `fetch()`-Antwort) und die Hitze-Warnung erscheint unverändert
  als `OfficialAlert` mit `hazard="extreme_heat"`.
  - Test: Deterministischer Kern-Test mit einer synthetischen, aus der
    CAP-Doku abgeleiteten Fixture, die beide `awareness_type`-Werte für
    denselben Punkt/dieselbe Region enthält; Ergebnisliste hat genau ein
    Element (Hitze), kein Fehler wird geworfen.

- **AC-5:** Given `GZ_METEOALARM_APIKEY` ist nicht gesetzt, ODER der Index-
  Call liefert einen HTTP-Fehler/Timeout, ODER eine nachgeladene CAP-XML
  ist strukturell kaputt (nicht parsebares XML), When
  `MeteoAlarmSource.fetch()` bzw. `get_official_alerts_for_location()`
  aufgerufen wird, Then liefert `fetch()` `[]` ohne Exception (jeweils
  einmalig eine Warning geloggt statt Retry-Loop), und andere registrierte
  Quellen (z. B. `GeoSphereWarnSource` für denselben AT-Punkt) liefern ihr
  Ergebnis unbeeinträchtigt weiter.
  - Test: Drei deterministische Kern-Tests (kein Mock der HTTP-Bibliothek,
    sondern reale Objektaufrufe mit fehlender ENV bzw. gegen einen lokal
    simulierten Fehlerpfad analog dem bestehenden `vigilance.py`/
    `geosphere_warn.py`-Testmuster): (a) ENV-Variable temporär entfernt →
    `fetch()` liefert `[]`, kein Call; (b) Index-Antwort mit kaputtem JSON
    → `[]`, kein Crash; (c) CAP-XML-Fixture mit absichtlich zerstörter
    XML-Struktur → die betroffene Warnung wird übersprungen, `fetch()`
    wirft nicht. Zusätzlich ein Test, der `get_official_alerts_for_location()`
    mit `MeteoAlarmSource` UND `GeoSphereWarnSource` gleichzeitig
    registriert aufruft und verifiziert, dass ein Fehlschlag der einen
    Quelle die Ergebnisliste der anderen nicht leert.

- **AC-6:** Given die bestehenden Météo-France-Quellen
  (`VigilanceSource`, `MeteoForetsSource`, `MassifClosureSource`) liefern
  wie vor dieser Spec Alerts für einen französischen Ort, When der volle
  Pfad (`get_official_alerts_for_location()` mit den real registrierten
  FR-Quellen, danach `dedupe_official_alerts()`) nach Einführung von
  `MeteoAlarmSource` und des Punkt-Kollaps in
  `get_official_alerts_for_location()` durchlaufen wird, Then ist das
  Ergebnis für den FR-Testfall wertidentisch zum Stand vor dieser Spec.
  **Begründung/Präzisierung (Adversary F003):** Der Punkt-Kollaps ist
  bewusst GENERISCH (ein Ort + eine Gefahrenart → ein Alert, höchste Stufe)
  — dieselbe Invariante, die `dedupe_official_alerts()` seit #1172 ohnehin
  anwendet. Er ist NICHT auf AT-Quellen beschränkt. Für die realen
  FR-Quellen ändert er faktisch nichts, weil `VigilanceSource`,
  `MeteoForetsSource` und `MassifClosureSource` an einem Punkt nie
  denselben `hazard`-Wert liefern (Wetter-Vigilance vs. `wildfire_risk` vs.
  `access_ban`) — es gibt also keinen FR-Kollaps-Auslöser. AC-6 verlangt
  den Nachweis dieser Wertgleichheit über den ECHTEN Registry-Pfad (nicht
  nur `dedupe_official_alerts()` mit vorgefertigten Listen).
  - Test: Bestehenden bzw. deterministischen Kern-Test mit den real
    genutzten FR-Testfällen aus #1035/#1036/#1037 (z. B. Massiv-Sperre +
    Waldbrand-Zone-Bündelung) vor und nach der Implementierung dieser Spec
    laufen lassen und die Ausgaben von `dedupe_official_alerts()`
    vergleichen — kein Dateiinhalt-Check, sondern Vergleich der
    zurückgegebenen `OfficialAlert`-Objekte/Gruppierung.

- **AC-7 (Adversary-Regression F002):** Given zwei VERSCHIEDENE
  Vergleichsorte, deren Warngebiets-/Gemeindenamen einander ähneln (z. B.
  „Villach (Stadt)" für Ort A mit Stufe 2 und „Villach Land" für Ort B mit
  Stufe 4), beide mit derselben Gefahr, When der Orts-Vergleich beide Orte
  über `get_official_alerts_for_location()` (je Punkt) und anschließend
  `dedupe_official_alerts()` (über die kombinierte Mehr-Orte-Liste)
  verarbeitet, Then behält JEDER Ort seine eigene korrekte Stufe und seinen
  eigenen `region_label` — Ort A bleibt Stufe 2 „Villach (Stadt)", Ort B
  bleibt Stufe 4 „Villach Land"; es findet KEINE ortsübergreifende
  Verschmelzung oder Stufen-/Label-Falschzuordnung statt (auch nicht für
  reines `GeoSphereWarnSource` ohne MeteoAlarm).
  - Test: Deterministischer Kern-Test mit zwei `OfficialAlert`-Objekten
    unterschiedlicher `region_label` (Villach-Stadt/Villach-Land),
    unterschiedlicher `level`, getaggt mit zwei verschiedenen `loc_id`s;
    nach `dedupe_official_alerts()` sind es ZWEI Ergebnisse mit je korrekter
    Stufe/Label; zusätzlich der State-Key-Pfad aus `compare_official_alert.py`
    (jeder `loc_id` behält seinen eigenen Wert). Dieser Test deckt die vom
    Adversary gefundene strukturelle Lücke (Mehr-Orte-`dedupe`-Fall).

## Known Limitations

- **100er-Cap ohne Pagination:** die EDR-Index-Antwort ist auf 100 Features
  pro Land begrenzt, es gibt keine Pagination (`limit`-Erhöhung wirkungslos,
  kein `next`-Link). Bei mehr als 100 gleichzeitig aktiven Warnungen im
  Abfragefenster für ein Land (v. a. Italien im Sommer realistisch) können
  Warnungen still verschluckt werden.
- **`datetime`-Fenster < 24h filtert Sendezeit, nicht Gültigkeit:** eine
  Warnung, die vor mehr als 24h publiziert wurde und noch gültig ist, kann
  im Index fehlen, weil das Pflicht-Zeitfenster auf `sent_range` filtert.
  MeteoAlarm republiziert Warnungen in der Praxis meist täglich neu, das
  Risiko ist real, aber gering.
- **CAP-Nachladen pro Treffer = N zusätzliche HTTP-Calls:** jeder im Index
  gefundene und geometrisch treffende Feature-Eintrag löst einen weiteren
  Call (Geometrie + CAP-XML) aus; ohne den beschriebenen Pro-URL-Cache
  entstünde ein Call-Sturm bei wiederholten Abfragen desselben Ortes
  innerhalb des TTL-Fensters.
- **Sprachfallback:** deutsche `event`/`headline`-Texte sind für AT-Warnungen
  bestätigt, für IT-Warnungen aber nicht garantiert — ohne deutschen
  `<info>`-Block wird englischer, sonst der erste vorhandene Text
  verwendet; ein Nutzer kann für Italien daher einen englischen/
  italienischen Warntext statt deutsch sehen.
- **`normalize_gemeinde_name()`-Heuristik ist bewusst einfach:** sie entfernt
  nur Klammer-Suffixe und eine kleine feste Menge deutschsprachiger
  Verwaltungs-Qualifizierer (`Stadt`, `Land`, `Bezirk`). Mehrwortige
  Gemeindenamen ohne solchen Qualifizierer (z. B. „Bad Ischl") bleiben
  unverändert und kollidieren korrekt; abweichende Schreibweisen ohne
  gemeinsames Präfix (z. B. eine völlig andere Ortsbezeichnung zwischen den
  Quellen) würden NICHT dedupliziert — dieses Risiko ist für das bestätigte
  Villach-Testmuster nicht relevant, aber kein Vollschutz gegen jede
  denkbare Namensdivergenz.
- **Ray-Casting-Punktfilter ohne Geo-Bibliothek:** analog zum
  dependency-freien Ansatz aus `department_mapper.py` (#1035) — korrekt für
  einfache Polygone/MultiPolygone, aber ohne die Kantenfall-Robustheit
  einer vollwertigen Geo-Bibliothek (Punkt exakt auf einer Kante ist ein
  bekannter Grenzfall, für Wetter-Warngebiete praktisch irrelevant).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec folgt vollständig dem in #1034/ADR-0016 bereits
  etablierten Registry-/Protocol-Muster (`OfficialAlertSource`,
  `register_official_alert_source()`) und implementiert eine weitere
  konkrete Quelle innerhalb dieses Vertrags. Die Cross-Source-Dedup nutzt
  ausschließlich das bereits in #1217/#1218 eingeführte `dedup_id`-Feld und
  die bestehende `dedupe_official_alerts()`-Funktion unverändert — keine
  neue Architektur-Entscheidung, kein neuer Mechanismus.

## Changelog

- 2026-07-15 (Rev 3, nach Adversary-Runde 2 AMBIGUOUS/F003): **Spec-
  Selbstwiderspruch behoben.** AC-6 sagte „wirkt ausschließlich auf die
  AT-Quellen", Implementation-Details Punkt 5 sagte „wirkt generisch". Der
  Code ist generisch (korrekte Invariante, wie `dedupe_official_alerts`).
  AC-6 präzisiert: Nachweis über den echten Registry-Pfad
  `get_official_alerts_for_location()` mit den realen FR-Quellen; der
  generische Kollaps ist gewollt und für FR faktisch folgenlos (keine
  geteilten `hazard`-Werte). Neuer Regressionstest deckt diesen Pfad ab.
  ACs inhaltlich unverändert.
- 2026-07-15 (Rev 2, nach Adversary-Befund BROKEN): **Dedup-Design korrigiert.**
  Der ursprüngliche Mechanismus (geteilte `normalize_gemeinde_name()` +
  normalisierte `dedup_id` in GeoSphere und MeteoAlarm) war fehlerhaft:
  (F001) `normalize_gemeinde_name(None)` crashte `GeoSphereWarnSource` bei
  Punkten ohne Gemeindenamen; (F002, CRITICAL) da `dedupe_official_alerts()`
  im Orts-Vergleich über MEHRERE Orte kombiniert aufgerufen wird, verschmolz
  der normalisierte Schlüssel zwei real verschiedene Orte („Villach (Stadt)"/
  „Villach Land") und schrieb einem Ort Stufe/Label eines anderen zu — auch
  ohne MeteoAlarm. Korrektur: kein `normalize_gemeinde_name`, kein
  Gemeinde-`dedup_id`; `geosphere_warn.py` bleibt unverändert. Der
  Cross-Source-Kollaps geschieht stattdessen pro einzelnem Punkt in
  `get_official_alerts_for_location()` (gleicher `hazard` → ein Alert,
  höchste Stufe, Tie-Break = zuerst registrierte Quelle). Neu: AC-7 sichert
  die Mehr-Orte-Nicht-Kollision ab. ACs 1–6 inhaltlich unverändert.
- 2026-07-15: Initial spec created (Epic #1073, Issue #1086, Slice 2 nach
  #1034/#1035/#1085-Fundament). Kernentscheidung aus der Analyse-Phase
  übernommen: MeteoAlarm deckt AT redundant zu GeoSphere UND IT ab;
  Cross-Source-Dedup verbindlich über eine geteilte
  `normalize_gemeinde_name()`-Funktion und eine kleine, in dieser Spec
  präzisierte Ergänzung an `geosphere_warn.py` gelöst (Analyse-Doc hatte
  den Kollisionsweg als „minimal-invasiv prüfen" offengelassen — hier als
  konkreter, testbarer Mechanismus festgelegt, inkl. Registrierungsreihenfolge
  für den Label-Tie-Break).
