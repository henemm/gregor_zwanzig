---
entity_id: feat_2051_s2a_raeumliche_ausdehnung
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.0"
tags: [alarm, nowcast, radar, ausdehnung, zone]
---

# Räumliche Ausdehnung des Regenereignisses — #2051 Scheibe S2a

## Approval

- [x] Approved — PO-Freigabe 2026-08-23 ("go", alle 16 ACs)

## Purpose

Ein Regenereignis wird heute als **Punkt** gemeldet ("Regen bei km 10 in 90
Minuten"). Der Nutzer erfährt nichts über die **räumliche Ausdehnung** entlang
der Reststrecke. S2a legt den Kern dafür: mehrere Abfragepunkte statt einem,
eine Nass/Trocken-Zonenbildung daraus, und **eine** Textstelle (E-Mail-Trip-
Langform) als End-to-End-Beweis. Die restlichen sechs Textstellen, die
Kanal-Kaskade und die Darstellung für unvermessene Etappen folgen in S2b.

Grundprinzip aus dem Ticket (unverändert bindend): **nur Daten über das
Wetter, keine Rechnung über den Nutzer.** Die Planposition darf intern
bestimmen, *wo* gemessen wird (gelebte Praxis seit #2017) — verboten ist
allein, dem Nutzer eine Zeit-Ort-Rechnung über ihn selbst auszugeben.

## Source

- **File:** `src/services/trip_segments.py` (Punktbildung), neues Modul
  `src/services/rain_extent.py` (Zonenbildung), `src/services/trip_alert.py`
  (Andockstelle, `:1408-1472`)
- **Identifier:** `points_along_remaining_route()` (neu, `trip_segments.py`),
  `derive_rain_zones()` (neu, `rain_extent.py`), `RainZone` (neu,
  `rain_extent.py`)

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Core
> (`src/services/`, `src/output/renderers/alert/`) — kein Go-API-, kein
> Frontend-Anteil.

## Estimated Scope

- **LoC:** ~180-220 produktiv, ~150 Tests — **über dem 250-LoC-Workflow-
  Limit** in Summe, `workflow.py set-field loc_limit_override 500` vor
  `/40-tdd-red` einplanen (Muster wie S1/S3).
- **Files:** `trip_segments.py`, `src/services/rain_extent.py` (neu),
  `trip_alert.py`, `src/services/notification_service.py` (Trip-Onset-
  Eventbau `:1386` + `RadarAlertRequest` `:177` — verifizierte Fundstelle,
  s. Implementation Details), `src/output/renderers/alert/model.py`,
  `src/output/renderers/alert/render.py`
  + `tests/tdd/test_issue_822_radar_nowcast_segment.py` (Umbau),
  `tests/unit/test_radar_nowcast_cache_sharing.py` (Prüfung),
  1-2 neue Testdateien.
- **Effort:** medium-high — neue Geometrie- und Zonenlogik, aber nur eine
  Andockstelle und eine Textstelle.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `position_at_time()` | function (`trip_segments.py:555`) | Liefert die interpolierte Position je Abfragepunkt — Baustein der neuen Punktbildung. |
| `haversine_km()` | function (`src/utils/geo.py`) | Luftlinien-Abstand für die Punkt-**Platzierung** (zulässig, da nie als Zahl ausgegeben — nur die ausgegebene km-Zahl braucht echte Messung). |
| `compare_radar_alert.py:382-392` | function (`_detect_triggered_locations`) | Bestehendes Muster für mehrere `get_nowcast`-Aufrufe in einer Schleife — S2a übernimmt die Sequenzierung, **rührt die Datei selbst nicht an** (kein Streckenkonzept im Ortsvergleich). |
| `ForecastBudgetGate` | class (`forecast_budget.py:36-74`) | Greift automatisch je Aufruf, unverändert — kein neues Gate für S2a. |
| `RadarNowcastCacheService` | class | TTL 300s, Schlüssel = Koordinate auf 4 Nachkommastellen — mehr Punkte bedeuten mehr Schlüssel, keine Änderung an der Cache-Logik selbst. |
| `TripSegment.distance_measured` / `km_measured` | field/concept (#2036) | Gate für die **Ausgabe** von km-Zahlen — S2a-Zonen tragen km-Werte nur auf vermessenen Etappen im gerenderten Text (AC-8/AC-9). |
| `fix_2017_nowcast_messpunkt.md` AC-12 | spec (existing) | "Genau ein `get_nowcast`-Aufruf je Trip" — wird durch S2a bewusst auf eine Obergrenze abgelöst (dokumentiert, siehe Abschnitt unten), nicht stillschweigend zurückgenommen. |

## Getroffene Entscheidungen (E1–E4, aus Phase 2 — nicht erneut vorlegen)

**E1 — Abrufbudget: 2 km Abstand, Deckel 6 Punkte, Priorität `polling`.**
Ein fester Abstand statt einer festen Punktzahl, weil Etappen 5-13 km lang
sind (Median 9,2 km) — eine feste Zahl würde kurze Etappen zu dicht und
lange zu grob abtasten. 2 km liegt über der feinsten Rasterauflösung (INCA
1 km) und liefert dort unterscheidbare Werte; 2 km läge bei ICON-D2/ARPAE
(2 km Zellen) an der Grenze, aber diese Quellen sind nicht der KHW-Pfad.
Deckel 6 Punkte deckt bis zu 12 km Reststrecke ab (über dem Etappen-Median)
und hält das Abrufvolumen weit unter dem 9000er-Tagesbudget (Ist-Werte
68-161 echte Fetches/Tag, Multiplikator ≈95×(N-1)/Trip/Tag — bei N=6 also
weit unkritisch). Priorität bleibt `polling` (drosselbar bei Budget-Druck,
unverändert gegenüber dem heutigen Einzelabruf) — kein Nutzer-Briefing, das
nie gedrosselt werden dürfte. Untergrenze 1 Punkt bei Reststrecke < 2 km:
dort bleibt das heutige Verhalten (ein Abruf an der Fenstermitte-Position)
exakt erhalten, kein Sonderfall in der Wirkkette.

**E2 — Zonentrennung: ein trockener Punkt trennt, er überbrückt nicht.**
Der Punktabstand liegt bereits an der Auflösungsgrenze der Quelle — ein
trockener Messpunkt ist echtes Signal, kein Rauschen. Würde ein trockener
Punkt zwischen zwei nassen überbrückt, entstünde eine Hülle, die trockene
Strecke als nass ausweist — eine erfundene Aussage über das Wetter, die dem
Ticket-Grundprinzip widerspräche.

**E3 — Unvermessene Etappen: gemessen wird überall, ausgegeben nur bei
`km_measured`.** `position_at_time()` braucht kein
`distance_from_start_km` — die Platzierung der Punkte läuft über
`haversine_km` und funktioniert auf allen 13 KHW-Etappen. Die
**ausgegebene** km-Zahl einer Zone erscheint aber nur, wenn die aktive
Etappe `distance_measured=True` trägt (#2036-Muster) — auf 9 von 13
KHW-Etappen also vorerst gar nicht (AC-8). Die Beschriftung dieser Etappen
über Wegpunktnamen ist ausdrücklich **S2b**, keine stille Lücke dieser
Scheibe.

**E4 — Teilausfall: Punkte ohne Daten fallen aus der Zonenbildung.** Ein
Punkt, für den `get_nowcast()` keine verwertbaren Frames liefert (Fehler,
`data_unavailable`, Providerlücke an genau diesem Punkt), wird **weder als
nass noch als trocken** gewertet — er trennt keine Zone und erweitert
keine, er ist eine echte Lücke. Totalausfall (kein Punkt liefert Daten)
ergibt weiterhin keinen S2a-Text, wie heute beim Einzelpunkt-Ausfall.

## Abgelöste Zusicherung (AC-12 aus `fix_2017_nowcast_messpunkt.md`)

Die #2017-Spec (`created: 2026-08-20`) legt "genau **ein**
`get_nowcast()`-Aufruf je Trip" als Test-Invariante fest und lehnte eine
Mehrfach-Abfrage ausdrücklich als unverhältnismäßig ab (Variante 3). Das
Ticket #2051 (2026-08-21, einen Tag jünger) beauftragt genau diese
Mehrfach-Abfrage — die Ablösung erfolgt hiermit **bewusst und dokumentiert**,
keine stille Rücknahme.

Betroffen sind ausschließlich Tests am `trip_alert.py`-Aufrufort (S2a rührt
nur diese Andockstelle an, **nicht** `trip_report_scheduler.py`):

| Test | Datei:Zeile | Alter Assert | Neuer Assert |
|---|---|---|---|
| `test_ac3_nowcast_called_at_segment_coordinates` | `test_issue_822_radar_nowcast_segment.py:532` | `call_count == 1` (`:611`) | `<= MAX_NOWCAST_CALLS_PER_TRIP_RUN` + Koordinaten-Assert |
| `test_2017_ac12_genau_ein_get_nowcast_aufruf_je_lauf` | `test_issue_822_radar_nowcast_segment.py:1282` | `== 1` (`:1304`, `:1308`) | `<=` an BEIDEN Seams (`dienst.calls`, `frames.call_count`) |
| `test_2017_fadv1_...` | `test_issue_822_radar_nowcast_segment.py:1329` | `call_count == 1` gemeinsam gezählt (`:1417`) | pro Trip GETRENNT gezählt (AC-14) |

**Nicht betroffen** (S2a ändert `trip_report_scheduler.py` nicht):
`test_ac12_starkregen_hinweis_ruft_get_nowcast_genau_einmal`
(`test_trip_report_scheduler_starkregen_hint.py:331`) bleibt bei `== 1` —
der Briefing-Kurzfristhinweis läuft über einen anderen Aufrufort und ist
S2b-Scope.

**Zu prüfen, nicht Teil des Testumbaus:**
`test_end_to_end_trip_and_compare_radar_paths_share_one_fetch`
(`tests/unit/test_radar_nowcast_cache_sharing.py:329`) setzt voraus, dass
eine Trip-Koordinate exakt auf der Compare-Koordinate liegt. Im Ein-Punkt-
Regime (Reststrecke < 2 km) bleibt das unverändert möglich; im
Mehr-Punkt-Regime (N > 1) ist eine zufällige Koordinatenübereinstimmung
strukturell unwahrscheinlich. Das ist eine erwartete Konsequenz von S2a,
keine Regression — der Test muss beim Implementieren auf den Ein-Punkt-Fall
verengt oder als bekannte Einschränkung dokumentiert werden (siehe Known
Limitations).

## Implementation Details

**Neue Punktbildung** (`trip_segments.py`, additiv, pure Funktion):

```python
RADAR_ZONE_POINT_SPACING_KM = 2.0
RADAR_ZONE_MAX_POINTS = 6
# Issue #2051 S2a: Abstand ueber der INCA-Zellgroesse (1 km), Deckel deckt
# bis zu 12 km Reststrecke ab (ueber dem Etappen-Median 9,2 km). Downstream-
# Leser referenzieren die MODUL-Variable, kein Bindezeit-Import.

def points_along_remaining_route(
    trip, active, segment_date, at: datetime,
) -> list[GPXPoint]:
    """Bis zu RADAR_ZONE_MAX_POINTS Punkte im Abstand
    RADAR_ZONE_POINT_SPACING_KM entlang der Reststrecke der AKTIVEN Etappe
    ab `at`. Reststrecke < 2 km -> genau 1 Punkt (heutiges Verhalten
    unveraendert). Platzierung ueber Luftlinie zulaessig (nie ausgegeben),
    siehe E3."""
```

**Neues Modul** `src/services/rain_extent.py` (Zonenbildung, kein
bestehender Baustein — siehe #2051-Kontext R3/R8):

```python
@dataclass(frozen=True)
class RainZone:
    km_from: float
    km_to: float
    onset_minutes: int
    event_end_minutes: int | None

def derive_rain_zones(
    points: list[GPXPoint], results: list[NowcastResult | None],
) -> list[RainZone]:
    """Benachbarte NASSE Punkte (onset_minutes gesetzt) verschmelzen zu
    einer Zone; ein TROCKENER Punkt trennt (E2). Punkte ohne Daten
    (results[i] is None) fallen aus der Bildung heraus (E4). Zeitangabe je
    Zone: fruehester onset_minutes, spaetester event_end_minutes unter den
    Punkten DIESER Zone (keine globale Spanne)."""
```

**Andockstelle** (`trip_alert.py:1408-1472`): Der heutige Einzelabruf wird
durch eine Schleife über `points_along_remaining_route(...)` ersetzt, nach
dem Muster von `compare_radar_alert.py:382-392` (sequenziell, `priority=
"polling"`, kein Bulk-Request). `get_nowcast()` bleibt Ein-Punkt-API — keine
Signaturänderung an `radar_service.py`. Ergebnisse gehen an
`derive_rain_zones()`.

**Neues Feld auf `OnsetEvent`** (`model.py`, additiv, Default leer — R6:
`km_from`/`km_to` bleiben unangetastet die Segment-Lage):

```python
rain_zones: tuple[RainZone, ...] = ()
# Issue #2051 S2a: eigenes Feld fuer die Ereignis-Ausdehnung. km_from/km_to
# bleiben die Segment-Grenzen (#2017 Known Limitation 5) -- zwei
# Bedeutungen, zwei Namen.
```

**Eine Textstelle** (`render.py`, Muster `_onset_end_suffix`): neuer Helfer
`_onset_extent_suffix(e) -> str` — `" · Nass km 8-12"` bei einer Zone,
`" · Nass km 2-4, km 9-11"` bei mehreren, leer wenn `rain_zones` leer ODER
die aktive Etappe unvermessen ist (AC-8). Angehängt an der bestehenden
E-Mail-Trip-Langform-Stelle (`render.py:~601`, dieselbe wie S3s
`_onset_reach_suffix`). Die übrigen sechs Textstellen bleiben in S2a
unangetastet.

**Datenweg außerhalb der Renderer** *(zweifach korrigiert, Stand verifiziert
in der RED-Phase — die ursprüngliche Spec-Angabe `project.py` und die erste
Korrektur `radar_alert_service.py` waren BEIDE falsch)*:

Der produktive Trip-Onset-Draht lautet
`trip_alert.py:1831` (`self._notification_service.send_radar_alert(...)`)
→ `notification_service.py:1374` (`send_radar_alert`, gefüttert über
`RadarAlertRequest`, `notification_service.py:177`, befüllt in
`trip_alert.py:1726`) → `notification_service.py:1386` (`OnsetEvent(...)`).
**Dort** wird `rain_zones` befüllt, was neue Felder auf `RadarAlertRequest`
plus Durchreichung in `send_radar_alert` bedeutet.

`radar_alert_service.py:31` (`build_onset_alert_message`) ist **nicht** der
Produktivpfad: einziger Aufrufer ist der Debug-Endpunkt
`api/routers/debug.py:110`. Eine Implementierung dort wäre wirkungslos.

Der Ortsvergleich-Bündel-Pfad (`project.py:621`,
`to_multi_location_onset_alert_message`) setzt `rain_zones` nie (AC-15, kein
Streckenkonzept). Die Zusicherungen AC-7/AC-15 sind von beiden Korrekturen
unberührt.

**Draht-Lücke `km_measured` (in der RED-Phase belegt, S2a-Scope):**
Der Trip-Onset-Pfad setzt `km_measured` heute **nie** — das Feld bleibt auf
dem Default `False`. Ohne Behebung wäre AC-9 auf Renderer-Ebene erfüllbar,
die Ausdehnung erschiene aber in Produktion auf **keiner** Etappe, auch
nicht auf den 4 vermessenen. S2a verdrahtet daher
`TripSegment.distance_measured` → `OnsetEvent.km_measured` mit. Der
Draht-Test `test_ac9_draht_km_measured_erreicht_das_gerenderte_onset_event`
belegt die Lücke: er scheitert mit `AssertionError` (nicht `ImportError`),
erreicht also den Renderer und findet die Zeile nicht.

**Offener Umbaupunkt für die GREEN-Phase (in RED nicht angefasst):**
`tests/tdd/test_radar_alert_follows_ortstag.py:240` (`_assert_messpunkt`,
gemeinsamer Helfer, Aufrufstellen `:317`, `:393`, `:994`, `:1016`) assertet
`len(calls) == 1` generisch für den Nowcast-Abruf über
`check_radar_alerts()`. Die Datei ist heute grün (34 Tests) und wird durch
S2a rot, sobald die dortigen Etappen ≥ 2 km Reststrecke haben — dann mit
demselben `<=`-Muster umbauen wie die Tests der Ablösungstabelle.

## Expected Behavior

- **Input:** aktive Etappe mit Reststrecke ab der Fensterzeit, N
  Nowcast-Ergebnisse (eines je Abfragepunkt), `distance_measured`-Flag der
  Etappe.
- **Output:**
  - `rain_zones` ist eine Liste getrennter, nie zu einer Hülle vereinter
    Zonen mit eigenen km- und Zeitgrenzen.
  - Die E-Mail-Trip-Langform trägt die Zusatzzeile nur bei vermessener
    Etappe; sonst byte-identisch zum Stand vor dieser Spec.
  - Die übrigen sechs Textstellen und der Ortsvergleich bleiben unverändert
    (S2b).
- **Side effects:** zusätzliche `get_nowcast`-Aufrufe je Trip-Lauf (gedeckelt
  auf `RADAR_ZONE_MAX_POINTS`), unverändert `priority="polling"`. Keine
  Persistenz betroffen, keine Änderung an der Auslöseregel.

## Acceptance Criteria

- **AC-1:** Given eine aktive Etappe mit einer Reststrecke von 12,0 km ab
  der aktuellen Fensterzeit / When die Abfragepunkte entlang der
  Reststrecke gebildet werden / Then entstehen genau 6 Punkte bei km 0, 2,
  4, 6, 8, 10 — der Deckel `RADAR_ZONE_MAX_POINTS=6` greift, die letzten 2 km
  der Reststrecke bleiben unabgefragt.
  - Test: Unit-Test gegen `points_along_remaining_route` mit synthetischer
    12-km-Etappe, Assert auf exakt diese 6 km-Werte in dieser Reihenfolge.

- **AC-2:** Given dieselbe Etappe, aber mit einer Reststrecke von 1,9 km
  (unterhalb der 2-km-Schwelle) / When die Abfragepunkte gebildet werden /
  Then entsteht GENAU EIN Punkt an der heutigen Fenstermitte-Position —
  unverändertes Verhalten gegenüber dem Stand vor dieser Spec.
  - Test: Gleicher Testaufbau wie AC-1, nur die Reststrecke auf 1,9 km
    verschoben; Anzahl kippt von 6 auf 1 (Positivkontrolle zu AC-1).

- **AC-3:** Given eine Reststrecke von 8,0 km / When die Abfragepunkte
  gebildet werden / Then liegen alle 5 Punkte (km 0/2/4/6/8) auf der
  interpolierten Streckengeometrie der aktiven Etappe und keine zwei
  Koordinaten sind identisch.
  - Test: Unit-Test mit 8-km-Etappe, Assert auf 5 unterschiedliche
    Koordinaten, jede gegen die erwartete Interpolationsposition geprüft.

- **AC-4:** Given 6 Abfragepunkte mit dem Nass/Trocken-Muster Nass, Nass,
  Trocken, Nass, Nass, Trocken (Positionen km 0, 2, 4, 6, 8, 10) / When die
  Zonenbildung läuft / Then entstehen genau zwei Zonen: km 0-2 und km 6-8.
  - Test: Unit-Test gegen `derive_rain_zones` mit synthetischen
    NowcastResults, Assert auf genau die zwei km-Spannen.

- **AC-5:** Given 3 Abfragepunkte mit dem Muster Nass, Trocken, Nass (km 0,
  2, 4) / When die Zonenbildung läuft / Then entstehen ZWEI getrennte Zonen
  (km 0-0 und km 4-4), NIEMALS eine Hülle km 0-4 — der trockene Mittelpunkt
  widerlegt eine durchgehende Nässe.
  - Test: Unit-Test mit genau diesem Dreier-Muster, Assert auf zwei Zonen
    mit den exakten Grenzen; Negativ-Assert, dass keine Zone gleichzeitig
    `km_from=0` und `km_to=4` trägt.

- **AC-6:** Given zwei Zonen aus AC-4 mit unterschiedlichen Onset-/Ende-
  Zeiten je Punkt (Zone A: onset 10 Min / Ende 20 Min, Zone B: onset 45 Min
  / Ende 60 Min) / When die Zonenbildung die Zeitspanne ableitet / Then
  trägt Zone A `onset_minutes=10` und Zone B `onset_minutes=45` — jede Zone
  bekommt ihre eigene früheste/späteste Zeit, keine globale Spanne über
  beide Zonen.
  - Test: Unit-Test mit den vier Zeitwerten aus dem AC, beide Zonen einzeln
    auf ihre Min/Max-Werte geprüft.

- **AC-7:** Given ein `OnsetEvent` mit gesetzten `km_from`/`km_to`
  (Segment-Lage, unverändert) UND gesetzten Zonen aus der neuen
  Ausdehnungs-Logik / When das Event gebaut wird / Then bleiben
  `km_from`/`km_to` unverändert die Segment-Grenzen, während die Zonen unter
  dem eigenen Feld `rain_zones` liegen — kein Test darf beide Bedeutungen
  über denselben Namen lesen.
  - Test: Unit-Test, der ein `OnsetEvent` mit beiden Wertepaaren
    konstruiert und prüft, dass `event.km_from`/`km_to` den Segmentwerten
    entsprechen, `event.rain_zones[0].km_from`/`km_to` den Zonenwerten.

- **AC-8:** Given eine aktive Etappe mit `distance_measured=False`
  (unvermessen) UND einer erkannten Nass-Zone / When die E-Mail-Trip-
  Langform gerendert wird / Then erscheint KEINE zusätzliche
  Ausdehnungs-Zeile — der Text bleibt byte-identisch zum Stand vor dieser
  Spec.
  - Test: Unit-Test mit `distance_measured=False`, Volltextvergleich des
    gerenderten E-Mail-Abschnitts gegen den Stand vor dieser Spec.

- **AC-9:** Given eine aktive Etappe mit `distance_measured=True` und einer
  einzelnen Nass-Zone km 8-12 / When die E-Mail-Trip-Langform gerendert
  wird / Then enthält der Text die Zusatzzeile mit exakt `Nass km 8-12`.
  - Test: Unit-Test gegen die Trip-E-Mail-Renderfunktion mit konstruiertem
    Event, Substring-Prüfung auf den exakten String `Nass km 8-12`.
  - **Zusätzlicher Draht-Test (Befund Kartierung):** derselbe Nachweis über
    `check_radar_alerts` mit einer Etappe, die `distance_measured=True`
    trägt — belegt, dass `km_measured` im Trip-Onset-Pfad überhaupt aus der
    Etappe abgeleitet wird. Ohne ihn prüft AC-9 nur den Renderer, nicht die
    Stelle, an der die Zusicherung wirkt.

- **AC-10:** Given zwei getrennte Zonen (km 2-4 und km 9-11) auf einer
  vermessenen Etappe / When dieselbe E-Mail-Langform gerendert wird / Then
  zeigt der Text beide Zonen getrennt (`Nass km 2-4, km 9-11`), NIEMALS eine
  zusammengefasste Hülle `km 2-11`.
  - Test: Unit-Test mit zwei Zonen, Substring-Prüfung auf den getrennten
    String, Negativ-Prüfung dass `km 2-11` nicht vorkommt.

- **AC-11:** Given 5 Abfragepunkte, von denen einer keine Nowcast-Daten
  liefert (Providerfehler an genau diesem Punkt, die übrigen vier liefern
  normal) / When die Zonenbildung läuft / Then wird der datenlose Punkt
  weder als nass noch als trocken gewertet und fällt aus der
  Zonengrenzenbildung heraus.
  - Test: Unit-Test mit `results[2] = None` bei 5 Punkten, Assert dass die
    umgebenden Zonen identisch zu einem Vergleichslauf ohne den Ausfall
    bleiben.

- **AC-12:** Given eine Etappe mit Reststrecke 12 km (wie AC-1) / When
  `trip_alert.check_radar_alerts` läuft / Then ist die Anzahl der
  `get_nowcast`-Aufrufe UND die Anzahl der `frame_source`-Aufrufe je Trip
  `<= MAX_NOWCAST_CALLS_PER_TRIP_RUN` (aus derselben Modulreferenz gelesen,
  nicht als Literal dupliziert), und alle abgefragten Koordinaten liegen auf
  der erwarteten Reststrecke ohne Duplikate.
  - Test: Umbau von `test_2017_ac12_genau_ein_get_nowcast_aufruf_je_lauf`
    (und `test_ac3_nowcast_called_at_segment_coordinates`) auf `<=`-Vergleich
    an beiden Seams (`dienst.calls`, `frames.call_count`) plus neuem
    Koordinaten-Assert.

- **AC-13:** Given dieselbe Testkonstruktion wie AC-12, aber mit
  Reststrecke 1,9 km (unterhalb der 2-km-Schwelle, wie AC-2) / When derselbe
  Ablauf läuft / Then bleibt die Aufrufzahl exakt 1.
  - Test: Gleicher Testaufbau wie AC-12 mit 1,9-km-Reststrecke, Assert
    `== 1` statt `<=` (Positivkontrolle — ohne diesen Fall misst AC-12
    nicht, ob überhaupt gedeckelt wird).

- **AC-14:** Given zwei Trips, wobei die Positionsbestimmung
  (`position_at_time`) für Trip A wirft, während Trip B eine normale
  Reststrecke von 8 km hat / When der Lauf durch beide Trips geht / Then
  verbraucht Trip A keinen einzigen `get_nowcast`-Aufruf, während Trip B
  alle 5 erwarteten Punkte abfragt.
  - Test: Umbau von `test_2017_fadv1_...` auf zwei getrennt gezählte Trips
    (bisher gemeinsam gezählt), Assert 0 für Trip A, 5 für Trip B.

- **AC-15:** Given denselben Nowcast-Abruf über den Ortsvergleich-Pfad
  (`compare_radar_alert.py`) / When das Event für den Ortsvergleich gebaut
  wird / Then bleibt `rain_zones` leer (`()`) — S2a ändert
  `compare_radar_alert.py` nicht.
  - Test: Regressionslauf des bestehenden Ortsvergleich-Tests, zusätzlicher
    Assert `event.rain_zones == ()`.

- **AC-16:** Given einen beliebigen gerenderten Text mit gesetzten Zonen /
  When der Text auf Formulierungen mit einer Ankunftszeit-Rechnung oder
  einer Handlungsempfehlung geprüft wird / Then enthält er keine solche
  Formulierung — nur Wetter-km-Spannen und -Zeiten, keine Aussage darüber,
  wann der Nutzer eine Zone erreicht.
  - Test: Unit-Test mit Negativ-Prüfung auf eine Liste verbotener Muster
    (Muster wie S3-AC-15).

## Known Limitations

- **Nur eine von sieben Textstellen wired.** Betreff, Telegram rich/Kurzstil,
  SMS/Premium-SMS, Briefing-Kurzfristhinweis, `/jetzt`-Kommando bekommen
  in S2a keine Ausdehnungs-Angabe — das ist S2b.
- **Kanal-Kaskade nicht entschieden.** Ob und wie die SMS-Kurzform eine
  Zonen-Spanne trägt (harter 140-Zeichen-Schnitt), entscheidet S2b.
- **Unvermessene Etappen bleiben stumm.** 9 von 13 KHW-Etappen zeigen in
  S2a keine Ausdehnung (AC-8) — die Wegpunktnamen-Darstellung ist S2b.
- **Cache-Sharing zwischen Trip- und Compare-Pfad gilt nur im
  Ein-Punkt-Regime.** `test_end_to_end_trip_and_compare_radar_paths_
  share_one_fetch` muss beim Implementieren auf den Reststrecke-<2-km-Fall
  verengt werden; bei N > 1 ist eine zufällige Koordinatenübereinstimmung
  nicht mehr zu erwarten — das ist eine erwartete Folge, keine Regression.
- **GeoSphere INCA bleibt ungegated** (R5 aus dem Kontextdokument). Der
  Deckel auf 6 Punkte hält das Abrufvolumen konservativ, S2a führt aber kein
  eigenes Gate für den INCA-Pfad ein.

## Nicht-Ziele

- Die restlichen sechs Textstellen (Betreff, Telegram rich/Kurzstil,
  SMS/Premium-SMS, Briefing-Kurzfristhinweis, `/jetzt`) — S2b.
- Kanal-Kaskade und SMS-Zonenkappung — S2b.
- Wegpunktnamen-Darstellung für unvermessene Etappen — S2b.
- Änderungen am Ortsvergleich (`compare_radar_alert.py` hat kein
  Streckenkonzept, neue Felder bleiben dort leer, AC-15).
- Signaturänderung an `get_nowcast()` — bleibt Ein-Punkt-API.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Feld-Durchreichung entlang derselben, bereits in
  S1/S3 etablierten Wirkkette (`OnsetEvent` → Renderer), plus eine neue
  reine Geometrie-/Zonenfunktion ohne bestehenden Baustein. Berührt keine
  der vier Entscheidungsflächen, die ein neues ADR verlangen würden:
  ADR-0011 (ein Backend-Renderer) bleibt gültig; ADR-0021 (geteilter Code
  Trip/Compare) wird angewendet, nicht verändert (Ortsvergleich bekommt
  bewusst keine Zonen, AC-15); kein neuer Kanal, kein neuer Provider, keine
  Persistenz-Änderung.

## Changelog

- 2026-08-23: Initial spec created (#2051 Scheibe S2a, räumliche Ausdehnung
  — Mehrpunktabfrage, Zonenbildung, eine Textstelle als E2E-Beweis).
