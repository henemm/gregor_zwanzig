---
entity_id: feat_1427_dpc_warn_fallback
type: module
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "2.0"
tags: [official-alerts, meteoalarm, dpc, italy, additive-source]
workflow: feat-1427-dpc-fallback
---

<!-- Issue #1427 -->

# Amtliche Italien-Warnungen: Zivilschutz (DPC) als eigenständige zweite Quelle (Issue #1427)

## Approval

- [x] Approved — PO-„go" 2026-07-31 auf Fassung 2.0 (alle 7 ACs, additiver
  Zuschnitt, zwei Scheiben). Die Freigabe der Fassung 1.0 (Fallback-Zuschnitt,
  8 ACs) ist damit gegenstandslos.

## Purpose

Die ursprüngliche Annahme dieses Issues — MeteoAlarm-Italien sei nur eine
Zweitschrift des Zivilschutzes DPC, DPC also nur bei MeteoAlarm-Ausfall
sinnvoll — ist **widerlegt**. Live erhoben am 31.07.2026 über den
öffentlichen, auth-freien Feed `https://feeds.meteoalarm.org/api/v1/warnings/
feeds-italy` (verbraucht das EDR-Tageskontingent nicht), 398 aktive
IT-Warnungen ausgewertet:

- `sender` = `aerocnmca.1sv.prv1@aeronautica.difesa.it`, `senderName` =
  „Italian Air Force National Meteorological Service" — durchgehend, alle 398.
- Alle 398 `description`-Felder enthalten wörtlich: „METEOALARM information
  do not provide the assessment of impact on the territory and **they do not
  represent the Official Alerts messages that are issued by the National
  Civil Protection Service**".
- Vorkommende `awareness_type` in IT: nur Wind (1), Gewitter (3), Hitze (5),
  Regen (10). **Kein Hochwasser (11), kein hydrogeologisches Risiko.**

MeteoAlarm-IT (italienische Luftwaffe) warnt vor Wind/Gewitter/Hitze/Regen und
beurteilt die *Intensität der Phänomene*. DPC (Zivilschutz) warnt vor
Gewitter/Hochwasser/hydrogeologischem Risiko und beurteilt die *Auswirkung auf
das Gelände*. Überschneidung ausschließlich bei Gewitter. DPC ist eine
eigenständige, komplementäre Quelle — keine Zweitschrift.

**PO-Entscheid 2026-07-31: DPC läuft dauerhaft additiv mit**, nicht mehr „nur
bei MeteoAlarm-Ausfall". Begründung: Hochwasser-/Erdrutschwarnungen wären
sonst nur während einer MeteoAlarm-Störung sichtbar (Ungereimtheit); zudem
wäre eine Rücknahme des Hinweises „amtliche Warnungen nicht abrufbar" bei
greifendem Fallback sachlich falsch gewesen, weil Hitze-/Windwarnungen bei
MeteoAlarm-Ausfall trotzdem fehlen würden — Details dazu bei AC-7.

Betroffen sind reale Touren mit Punkten auf italienischem Boden (z.B. KHW 403,
Karnischer Höhenweg), für die GeoSphere Austria live mit HTTP 404 ablehnt —
Italien hat sonst nur eine amtliche Quelle. DPC deckt dabei nur drei
Risikoarten ab (Gewitter, Hochwasser, Erdrutsch) und liefert nur „heute +
morgen" — eine bewusst unvollständige, aber zusätzliche Quelle.

## Source

- **File:** `src/services/official_alerts/dpc.py` (neue Quelle, S2)
- **Identifier:** neue Klasse `DpcSource`, implementiert das bestehende
  `OfficialAlertSource`-Protocol unverändert (kein `fallback_for`, keine
  Sonderbehandlung)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`,
> `src/output/tokens/`, `src/output/renderers/`). Kein Go-, kein Frontend-Anteil.
> `base.py` wird von dieser Arbeit **nicht angefasst** — DPC ist eine ganz
> normale sechste Quelle in der bestehenden Registry.

## Estimated Scope

- **LoC:** ~145–200 Produktiv + ~160 Test, aufgeteilt auf zwei Scheiben (siehe
  unten); jede Scheibe einzeln unter dem 250-LoC-Limit
- **Files:** ~7 (5 Produktiv-, 1 generierte Datendatei, 3 Testdateien, davon
  eine Datei in beiden Scheiben modifiziert)
- **Effort:** medium (S1) bis high (S2, neuer Parser + Geometrie)

## Scheiben (verbindliche Reihenfolge S1 → S2)

S2 braucht die Gefahrenart aus S1 — die Reihenfolge ist deshalb zwingend.

| Scheibe | Inhalt | Dateien | LoC (Produktiv/Test) | Eigenständiger Nutzen |
|---|---|---|---|---|
| **S1** | Neue Gefahrenart „Hochwasser/Erdrutsch" (`flood`) im SSOT-Katalog + deutsches Anzeige-Label + MeteoAlarm-Typen **11, 12 und 13** auf `flood` abgebildet (Typ 12 wird dabei von der bisherigen **Fehlabbildung auf `rain`** korrigiert, Typ 13 war unabgebildet) | `src/output/tokens/hazard_symbols.py` (MODIFY), `src/output/renderers/alert/official_alerts.py` `_HAZARD_LABELS` Z. 56–73 (MODIFY), `src/output/renderers/email/compare_html.py` `_warn_short()` Z. 392–401 (MODIFY), `src/services/official_alerts/meteoalarm.py` `_TYPE_HAZARD_MAP` Z. 475–484 (MODIFY) | ~25–40 / ~40 | **Behebt eine aktive Fehlanzeige:** Hochwasserwarnungen (Typ 12 `flooding`) werden heute als „Regen" ausgegeben, Typ 13 (`rain-flood`) fällt ganz weg. Beides kommt real vor — Messung s.u. Zusätzlich notwendige Vorarbeit für S2 (DPC braucht ein Ziel im Vokabular) |
| **S2** (war S3) | DPC-Quelle: Zip laden (`warn_egress.cached_fetch`), DBF lesen, Bezugstag aus Dateinamen-Zeitstempel ableiten, Zone→Stufe→`OfficialAlert`, Zonen-Geometrie aus generierter Datendatei, Registrierung **nach** MeteoAlarm ohne `fallback_for`, Herkunfts-Label | `src/services/official_alerts/dpc.py` (CREATE), `src/services/official_alerts/data/dpc_zones.json` (CREATE, generiert — zählt nicht zum LoC-Limit), `src/services/official_alerts/__init__.py` (MODIFY, Registrierung Z. 21–28), `src/output/renderers/alert/official_alerts.py` `_SOURCE_LABELS` Z. 89–103 (MODIFY) | ~120–160 / ~120 | Das eigentliche Versprechen von #1427: Italien bekommt Hochwasser-/Erdrutsch-Warnungen aus einer eigenständigen, dauerhaft mitlaufenden Quelle — nicht nur während eines MeteoAlarm-Ausfalls |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.base.get_official_alerts_with_status` Zwei-Pass-Partitionierung (`base.py:153-176`) | function | „Beste Quelle je Gefahr" (höchstes `level`, Gleichstand → zuerst registrierte Quelle) — unverändert genutzt, um Gewitterwarnungen von DPC und MeteoAlarm nie doppelt zu zeigen (S2, AC-6) |
| `services.official_alerts.warn_egress.cached_fetch` (`warn_egress.py:257` s. Kontext) | module | TTL-Cache + `If-None-Match`/ETag für den 4,6-MB-DPC-Abruf (S2) |
| `services.official_alerts.warn_egress.observe_fetch_failure`/`mark_fetch_incomplete` (`warn_egress.py:60-95`) | module | Fehlschlags-Signal für fail-soft Verhalten der DPC-Quelle selbst (S2) |
| `services.official_alerts.geo_ray_cast._point_in_ring` (`geo_ray_cast.py:12`) | function | Punkt-in-Fläche-Test für die 187 DPC-Zonenpolygone, wiederverwendet ohne neue Geo-Bibliothek (S2) |
| `services.official_alerts.meteoalarm._TYPE_HAZARD_MAP` (`meteoalarm.py:475-484`) | data | Erhält `11: "flood"`, `12: "flood"` (**ersetzt die bisherige Fehlabbildung `12: "rain"`**), `13: "flood"` (bisher unabgebildet). Der Code-Kommentar Z. 472–474, der nur Typ 11 als „flood" führt, ist gegen die gemessene Wirklichkeit zu korrigieren (S1) |
| `output.tokens.hazard_symbols.HAZARD_SMS_SYMBOLS`/`HAZARD_ORDER` | data | SSOT-Katalog der Gefahrenarten — neuer Eintrag `flood` (S1) |
| `output.renderers.email.compare_html._warn_short` (`compare_html.py:392-401`) | function | Einziges hartkodiertes if/elif für Warn-Kurztexte (Bug-Muster #1239) — muss `flood` kennen (S1) |
| `output.renderers.alert.official_alerts._SOURCE_LABELS` (`official_alerts.py:89-103`) | data | Herkunfts-Fußzeile (ADR-0034) — neuer Eintrag `"dpc": "Protezione Civile (DPC)"` (S2) |
| `services.official_alerts.__init__` Registrierungsreihenfolge (`__init__.py:21-28`) | module | DPC wird NACH MeteoAlarm registriert, ohne `fallback_for` — eine normale additive Quelle wie GeoSphere/Vigilance/MeteoForets (S2) |
| `services.radar_service` `_DPC_LAT/LON_MIN/MAX` (`radar_service.py:48-51`) | data | Vorhandene Italien-BBox, wiederverwendbar als grober `covers()`-Vorfilter (S2) |
| `output.renderers.alert.official_alerts._HAZARD_LABELS` (`official_alerts.py:56-73`) | data | Deutsches Anzeige-Label je Gefahrenart (Mail HTML + Klartext, Betreff, Telegram) — braucht den Eintrag `flood` → „Hochwasser/Erdrutsch" (S1) |

## Implementation Details

Technischer Ansatz aus der Analyse (siehe
`docs/context/feat-1427-dpc-fallback.md` Abschnitt „Technical Approach",
angepasst auf den additiven Zuschnitt):

1. **Geometrie offline, Stufen zur Laufzeit.** Die 187 Zonen-Polygone werden
   einmalig aus dem DPC-Shapefile extrahiert und als `data/dpc_zones.json`
   eingecheckt (etabliertes Muster, analog `massif_polygons.json`/
   `department_polygons.json`, geladen analog `massif_zones.py`).
   Punkt-in-Fläche läuft über das vorhandene `geo_ray_cast._point_in_ring`.
   **Keine neue Geo-Abhängigkeit** — Präzedenzfall `rasterio` (#1162) legte
   beim Deploy Staging 14 Minuten lahm, das wird nicht wiederholt.
2. **Laufzeit liest die DBF, nicht die CAP-XML.** Die DBF trägt garantiert
   alle 187 Zonen (`Zona_all`, `Nome_zona`, `Criticita`, `Idrogeo`,
   `Temporali`, `Idraulico`); die CAP-XML nennt nur *gewarnte* Zonen und
   wurde nur an einem Stichprobentag mit einer einzigen gewarnten Zone
   geprüft — zu dünn als alleiniger Beleg.
3. **Bezugstag aus dem Dateinamen-Zeitstempel ableiten**,
   `<YYYYMMDD>_<HHMM>_today.*` bzw. `_tomorrow.*`, nie `today.dbf` blind als
   „heute" interpretieren (Tagesversatz-Falle, s. AC-3).
4. **Egress:** `warn_egress.cached_fetch()` mit TTL + `If-None-Match`/`ETag`
   (Bulletin ändert sich ~1×/Tag ⇒ sonst 304-Antwort statt vollem Download).
5. **Registrierung als normale additive Quelle** (kein `fallback_for`, keine
   Sonderschleife) — DPC wird bei jedem Aufruf für einen abdeckenden Punkt
   abgefragt, genau wie jede andere Quelle. Die bestehende „beste Quelle je
   Gefahr"-Partitionierung (`base.py:153-176`, unverändert seit #1086/#1245)
   löst die Gewitter-Überschneidung mit MeteoAlarm: höchstes `level`
   gewinnt, bei Gleichstand die zuerst registrierte Quelle.
6. **Stufen-Abbildung:** Freitext-Muster `<Kritikalität> / ALLERTA <FARBE>`.
   `NESSUNA` → keine Warnung erzeugen, `GIALLA` → Level 2, `ARANCIONE` →
   Level 3, `ROSSA` → Level 4. `Temporali` kennt laut DPC-README kein
   `ROSSA`.
7. **Gefahren-Abbildung:** `Temporali` → `thunderstorm` (bestehende
   Kategorie); `Idrogeo` UND `Idraulico` → die in S1 neu geschaffene
   Kategorie `flood`.

## Expected Behavior

- **Input:** Aufrufe von `get_official_alerts_with_status(lat, lon, ...)` für
  Punkte in Italien — unabhängig vom Erfolg/Ausfall von MeteoAlarm.
- **Output:** DPC wird bei jedem Aufruf für einen abdeckenden italienischen
  Punkt zusätzlich zu MeteoAlarm abgefragt und liefert seine Warnungen
  (Gewitter/Hochwasser/Erdrutsch, „heute + morgen") mit korrekt aufgelöstem
  Bezugstag und der italienischen Zivilschutzbehörde als Quelle. Meldet DPC
  eine Gewitterwarnung für dieselbe Zone/denselben Zeitraum wie MeteoAlarm,
  erscheint im Ergebnis nur die Warnung der Quelle mit dem höheren `level`
  (bestehende Partitionierung, keine neue Logik). Fällt MeteoAlarm aus, bleibt
  `unavailable=True` bestehen — DPC ersetzt nicht die bei MeteoAlarm-Ausfall
  fehlenden Hitze-/Wind-/Regenwarnungen (s. Nicht-Ziele, AC-7).
- **Side effects:** Ein zusätzlicher HTTP-Abruf (4,6 MB, gecacht) gegen die
  DPC-Rohdaten-URL bei jedem Warn-Abruf für einen italienischen Punkt.

## Nicht-Ziele

- **DPC ersetzt MeteoAlarm nicht.** Hitze, Wind, Schnee, Waldbrand kommen im
  DPC-Bulletin überhaupt nicht vor — DPC ist ein Zivilschutz-Kritikalitätsbulletin
  mit genau drei Risikoarten, kein allgemeines Wetterwarnungs-Bulletin. Fällt
  MeteoAlarm aus, bleibt der Hinweis „amtliche Warnungen nicht abrufbar"
  deshalb bewusst bestehen (AC-7) — das ist keine Lücke, sondern korrekt,
  weil DPC diese Warnarten strukturell nicht liefert.
- **Lawinenwarnungen sind ausdrücklich NICHT Teil dieser Arbeit.** Das ist ein
  eigenständiger Nebenbefund (`_TYPE_HAZARD_MAP` verwirft MeteoAlarm-Typ 9 still)
  und gehört zu Issue #1430.
- **Kein rollierendes Mehrtagesfenster.** DPC liefert strukturell nur „heute +
  morgen", 1×/Tag aktualisiert — kein mehrtägiges Ausblicksfenster wie MeteoAlarm.
- **Keine neue Geo-Fremdbibliothek.** Die Zonen-Geometrie wird offline extrahiert
  und als Datendatei eingecheckt; zur Laufzeit reicht das vorhandene
  `geo_ray_cast._point_in_ring` — keine `pyshp`/`fiona`/`shapely`-Abhängigkeit.

## Test Plan

Kern-Tests laufen deterministisch gegen **aufgezeichnete echte** Fixtures (echte
DPC-Zips unter `tests/fixtures/dpc/` abgelegt) — kein Mock-Theater, keine
Dateiinhalt-Checks als Verhaltensnachweis. Testdateien sind nach Verhalten benannt,
nicht nach Issue-Nummer.

**Fixture-Beschaffung (geprüft 2026-07-31):** Das DPC-Archiv ist vollständig und
per Zeitstempel adressierbar — `…/files/all/<YYYYMMDD>_<HHMM>_all.zip` liefert
HTTP 200 auch für zurückliegende Bulletins (verifiziert an `20260730_1511`),
Dateinamen sind über die GitHub-Contents-API von `files/shp` auflistbar. **Zwei
verschiedene echte Bulletins aufzeichnen:**

1. ein **ruhiger Tag** (nur `NESSUNA ALLERTA` bzw. eine einzelne `GIALLA`) — der
   bereits geprüfte Stand `20260730_1511` erfüllt das (genau eine gewarnte Zone:
   `Tren-A`, `Temporali`, `Ordinaria / ALLERTA GIALLA`, im `tomorrow`-Datensatz) und
   trägt zugleich den **Tagesversatz-Fall** in sich;
2. ein **Unwettertag** mit mindestens einer `ARANCIONE`-Zone und möglichst einer
   `Idrogeo`- oder `Idraulico`-Warnung, aus dem Archiv gezogen.

Ein Fixture mit ARANCIONE-Stufen darf **nicht** aus dem Ruhetags-Bulletin
zusammengeschnitten werden — das wäre eine erfundene Aufzeichnung. Findet sich im
Archiv kein passender Tag, ist der betreffende Test entsprechend zu verkleinern und
die Lücke offen zu benennen, statt Daten zu erfinden.

**Gemessene Warnart-Nummern statt Code-Kommentar (31.07.2026, 8 Länder über den
öffentlichen Feed `https://feeds.meteoalarm.org/api/v1/warnings/feeds-<land>` —
auth-frei, unabhängig vom EDR-Tagesbudget):**

| `awareness_type` | Vorkommen | heutige Abbildung | korrekt |
|---|---:|---|---|
| `11; flood` | 0 | (keine) | `flood` |
| `12; flooding` | **14** | **`rain` — falsch** | `flood` |
| `13; rain-flood` | **6** | (keine, fällt weg) | `flood` |

Der Kommentar in `meteoalarm.py:472-474` führt nur Typ 11 als „flood" — die realen
Hochwasser-Nummern sind **12 und 13**, und Typ 12 landet heute als „Regen" beim
Nutzer. Die Fixture-Beschaffung zielt daher auf Typ 12/13, nicht auf 11.

**🔴 Verbleibende Einschränkung beim Wirkungsnachweis:** Alle am 31.07.2026 aktiven
Typ-12/13-Warnungen tragen `awareness_level = 1; green; Minor`. Der Bestandscode
filtert `level < 2` heraus, bevor eine Warnung den Nutzer erreicht — ein
*durchgehender* Nachweis „grüne Wiese bis Briefing" ist damit heute nicht möglich.
Der Nachweis wird deshalb an der Abbildungsstelle geführt (aufgezeichnete echte
CAP-Werte → `hazard == "flood"`), und die Lücke bis zu einer real gelben
Hochwasserwarnung ausdrücklich benannt. **Nicht zulässig:** `awareness_level` oder
`awareness_type` in einer Aufzeichnung von Hand hochsetzen — das wäre keine
Aufzeichnung mehr.

### Automated Tests (TDD RED)

- [ ] **S1** `tests/tdd/test_meteoalarm_source.py` (erweitert): GIVEN eine
  aufgezeichnete echte MeteoAlarm-Warnung vom `awareness_type` **12 (`flooding`)**
  bzw. **13 (`rain-flood`)** (Aufzeichnung aus dem öffentlichen Feed, Werte
  unverändert), WHEN die Gefahren-Zuordnung darauf läuft, THEN ergibt sie
  `hazard == "flood"` — statt wie bisher `"rain"` (Typ 12) bzw. gar nichts
  (Typ 13).
- [ ] **S1** `tests/tdd/test_hazard_symbols.py` (erweitert oder neu): GIVEN der
  SSOT-Katalog `HAZARD_SMS_SYMBOLS`, WHEN nach dem Kürzel für `flood` gefragt wird,
  THEN liefert `sms_symbol_for("flood")` ein eigenes, mit keinem anderen Kürzel
  kollidierendes Symbol (Bug-Präzedenz #1239: fehlendes Mapping erscheint sonst als
  Fallback-Buchstaben).
- [ ] **S2** `tests/tdd/test_dpc_bulletin_source.py` (CREATE, Bug-Repro-Charakter):
  GIVEN ein aufgezeichnetes DPC-Zip, dessen Dateiname einen Vortags-Zeitstempel
  trägt (Bulletin von 15:11 des Vortags, abgerufen um 04:57 UTC am Folgetag), WHEN
  `DpcSource.fetch()` für einen Punkt in einer gewarnten Zone läuft, THEN basiert
  die zurückgegebene Warnung auf dem für HEUTE zutreffenden Teil des Bulletins
  (`tomorrow`-Datensatz des Vortags-Bulletins), nicht auf dessen `today`-Datensatz
  (der die Lage von gestern zeigt).
- [ ] **S2** `tests/tdd/test_dpc_bulletin_source.py`: GIVEN ein aufgezeichnetes
  DPC-Zip mit einer Zone in Stufe `ALLERTA GIALLA` bei `Temporali` und einer
  weiteren Zone mit `ALLERTA ARANCIONE` bei `Idrogeo`, WHEN `DpcSource.fetch()` für
  Punkte in beiden Zonen läuft, THEN liefert die erste eine `thunderstorm`-Warnung
  Level 2 und die zweite eine `flood`-Warnung Level 3.
- [ ] **S2** `tests/tdd/test_dpc_bulletin_source.py`: GIVEN eine DPC-Warnung, WHEN
  sie im Briefing/der Herkunfts-Fußzeile angezeigt wird, THEN nennt
  `official_alert_source_label()` die italienische Zivilschutzbehörde, nicht
  „MeteoAlarm".
- [ ] **S2** `tests/tdd/test_dpc_bulletin_source.py`: GIVEN ein DPC-Bulletin, dessen
  Freitext-Stufe vom bekannten Muster `<Kritikalität> / ALLERTA <FARBE>` abweicht
  ODER dessen Zip/DBF defekt ist, WHEN `DpcSource.fetch()` läuft, THEN wirft es
  keine Exception, liefert fail-soft „keine Warnung erkannt" für die betroffene
  Zone, und ein unbekannter Zonencode (`Zona_all` ohne Eintrag in
  `dpc_zones.json`) wird geloggt statt kommentarlos übersprungen.
- [ ] **S2** `tests/tdd/test_dpc_bulletin_source.py` (Integrations-Ergänzung):
  GIVEN sowohl DPC als auch MeteoAlarm melden für denselben italienischen Punkt
  und Zeitraum eine Gewitterwarnung (verschiedene Level), WHEN
  `get_official_alerts_with_status()` läuft, THEN erscheint in `results` genau
  EIN Gewitter-Eintrag für diesen Punkt/Zeitraum — der mit dem höheren `level` —
  nie zwei Karten für dasselbe Ereignis.
- [ ] **S2** `tests/tdd/test_official_alerts_unavailable_hint.py` (erweitert):
  GIVEN MeteoAlarm fällt für einen italienischen Punkt aus, DPC liefert aber
  erfolgreich Warnungen für denselben Punkt, WHEN
  `get_official_alerts_with_status()` läuft, THEN bleibt `unavailable == True`
  bestehen — DPC nimmt den Hinweis „amtliche Warnungen nicht abrufbar" NICHT
  zurück, weil bei MeteoAlarm-Ausfall weiterhin Hitze-/Wind-/Regenwarnungen fehlen.

## Acceptance Criteria

- **AC-1 (S1):** Given eine amtliche Warnung vor Überschwemmung erreicht das
  System (MeteoAlarm-Warnart `flooding` oder `rain-flood`, oder eine
  Hochwasser-/Erdrutschwarnung des italienischen Zivilschutzes), When daraus
  eine Warnung für den Nutzer entsteht, Then trägt sie die eigene Bezeichnung
  „Hochwasser/Erdrutsch" — statt wie bisher als „Regen" ausgegeben zu werden
  oder ganz zu verschwinden.

- **AC-2 (S2):** Given der italienische Zivilschutz warnt für eine Zone in
  Italien am Bezugstag (Gewitter oder Hochwasser/Erdrutsch), When der Nutzer
  ein Briefing für einen Ort in dieser Zone erhält, Then enthält das Briefing
  die entsprechende Warnung mit der zutreffenden Stufe — unabhängig davon, ob
  MeteoAlarm für denselben Ort ebenfalls erreichbar ist.

- **AC-3 (S2, Tagesversatz):** Given das zum Abrufzeitpunkt neueste verfügbare
  DPC-Bulletin wurde am Vortag veröffentlicht (Alltagsfall am frühen Morgen, belegt
  30.07. 15:11 Uhr noch aktuell um 31.07. 04:57 UTC), When am Morgen ein Briefing
  für einen betroffenen italienischen Ort abgerufen wird, Then zeigt es die für
  HEUTE gültige Warnlage, nicht die Warnlage von gestern.

- **AC-4 (S2, ADR-0034):** Given eine Warnung im Briefing stammt vom
  italienischen Zivilschutz, When der Nutzer die Herkunftsangabe der Warnung
  sieht, Then weist sie die italienische Zivilschutzbehörde (Protezione
  Civile) als Quelle aus, nicht MeteoAlarm.

- **AC-5 (S2, Fail-soft, ADR-0018):** Given das DPC-Bulletin weicht vom bekannten
  Stufen-Freitext-Muster ab oder die abgerufene Datei ist beschädigt, When das
  Briefing für einen davon betroffenen Ort trotzdem gerendert wird, Then stürzt der
  Abruf nicht ab und behauptet nicht fälschlich eine Warnung — er verhält sich wie
  „keine Warnung von dieser Quelle erkannt"; ein dabei auftretender unbekannter
  Zonencode wird im Diagnose-Log sichtbar, statt kommentarlos zu verschwinden.

- **AC-6 (S2, Gewitter-Überschneidung):** Given sowohl der italienische
  Zivilschutz als auch MeteoAlarm melden für dieselbe Zone/denselben Zeitraum
  eine Gewitterwarnung, When der Nutzer sein Briefing für den betroffenen Ort
  erhält, Then enthält es genau EINE Gewitterkarte für dieses Ereignis — die
  mit der höheren Warnstufe —, nie zwei.

- **AC-7 (S2, `unavailable` bleibt bestehen):** Given MeteoAlarm ist für einen
  Ort in Italien nicht abrufbar, der italienische Zivilschutz liefert aber
  erfolgreich Warnungen für denselben Ort, When der Nutzer sein Briefing
  erhält, Then steht dort weiterhin der Hinweis „amtliche Warnungen aktuell
  nicht abrufbar" — DPC deckt Hitze-, Wind- und Regenwarnungen strukturell
  nicht ab, der Hinweis bleibt also sachlich richtig.

## Known Limitations

- DPC deckt nur drei von acht relevanten Risikoarten ab (Gewitter, Hochwasser,
  Erdrutsch) — Hitze-, Wind-, Schnee- und Waldbrandwarnungen für Italien kommen
  weiterhin ausschließlich von MeteoAlarm.
- Rückschau/Ausblick ist auf „heute + morgen" begrenzt, 1×/Tag aktualisiert — kein
  Ersatz für die mehrtägige MeteoAlarm-Rückschau.
- DPC liefert nur italienischsprachigen Freitext; die Übersetzung der Stufen-/
  Risikoart-Texte ist ein fester, kleiner Satz Textbausteine (Kritikalität ×
  Farbe je Risikoart), keine generische Übersetzung.
- Lawinenwarnungen (MeteoAlarm-Typ 9) bleiben unabhängig von dieser Arbeit
  weiterhin verworfen — eigenes Issue #1430.
- Bekannter, PO-akzeptierter Preis der bestehenden „beste Quelle je Gefahr"-
  Regel (unverändert seit #1086/#1245, `base.py:225-227`): meldet bei einer
  Gewitterwarnung ausschließlich die NICHT-beste Quelle (niedrigeres `level`)
  eine bestimmte Periode exklusiv, fällt diese Periode weg — Folge der „nie
  doppelt"-Entscheidung, keine neue Nebenwirkung dieser Arbeit.
- Ist DPC selbst nicht erreichbar (Netzfehler, HTTP-Fehler), liefert es
  fail-soft keine Warnung — es entsteht keine Fehlermeldung, aber auch kein
  Ersatz für einen gleichzeitigen MeteoAlarm-Ausfall.

## Architektur-Entscheidung (ADR)

**Kein neues ADR nötig.** DPC als zusätzliche additive Quelle ist genau das
Modell, das **ADR-0016** bereits für amtliche Warnungen festlegt: jede
registrierte, abdeckende Quelle wird abgefragt, Konkurrenz wird erst
nachträglich über „beste Quelle je Gefahr" aufgelöst (`base.py:153-176`).
Präzedenzfall: GeoSphere Austria und MeteoAlarm laufen für Österreich bereits
seit #1086 additiv parallel, mit derselben Zwei-Pass-Partitionierung für den
Überschneidungsfall. Diese Arbeit reiht sich unverändert in dieses Modell ein
— der ursprünglich geplante Fallback-Mechanismus (optionales `fallback_for`,
zweiter Schleifendurchlauf) entfällt damit ersatzlos.

Weiterhin einzuhaltende Randbedingungen aus bestehenden ADRs: **ADR-0034**
(Herkunftsfußzeile nennt die reale Quelle, s. AC-4) und **ADR-0018**
(Fail-soft statt Kaschieren, s. AC-5).

## Changelog

- 2026-07-31: Initial spec created (Issue #1427, Scheiben S1–S3, Fallback-Modell)
- 2026-07-31 v2.0: Zuschnitt geändert — DPC ist keine Zweitschrift von
  MeteoAlarm (Luftwaffe vs. Zivilschutz, live belegt), daher additive Quelle
  statt Fallback; Fallback-Mechanik und neues ADR entfallen ersatzlos; drei
  Scheiben auf zwei reduziert.
