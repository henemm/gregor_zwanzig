---
entity_id: feat_1758_geosphere_cape_cin
status: draft
type: module
created: 2026-08-18
updated: 2026-08-18
version: "1.0"
tags: [gewitter, provider, geosphere, arome, 1758, 1419]
---

# GeoSphere liefert cape/cin — zweite, additive Gewittersignal-Quelle für Österreich

## Approval

- [x] Approved — PO-Freigabe „go" am 2026-08-18

## Purpose

Der GeoSphere-Provider (AROME, Österreich, 2,5 km) fragt heute weder `cape` noch `cin` ab,
obwohl der Dienst beide Größen führt (#1758, Eltern-Epic #1419). PO-Entscheid vom 2026-08-18:
**voll wirksam** — die Werte sollen im Normalbetrieb entstehen, nicht nur im
Open-Meteo-Totalausfall. Damit gehört neben dem reinen Abruf auch die
Gewitter-Zuständigkeit zur Arbeit: `thunder_routing.py` kennt heute genau eine Quelle je
Gebiet (`first-match-wins`); Österreich bekommt sein Gewittersignal ausschließlich vom DWD
(`de_direct`, Blitzpotenzial). GeoSphere-CAPE/CIN soll dort **zusätzlich** entstehen, ohne den
DWD zu verdrängen.

## Source

- **File:** `src/providers/geosphere.py`, `src/providers/thunder_routing.py`,
  `src/providers/thunder_enrichment.py`, `src/app/models.py`
- **Identifier:** `GeoSphereProvider.fetch_thunder_signals_named`, `_REGIONS`/`thunder_provider_for`,
  `_SIGNAL_ZU_FELD`, `_bekannte_felder`, `ForecastDataPoint`

Schicht: **Python-Core** (`src/providers/`, `src/app/`). Kein Go, kein Frontend (Mitpflege-Kette
live geprüft, #1531-Felder existieren dort nicht — dieselbe Schicht gilt für #1758).

## Vorbedingung — bereits geklärt (live gemessen 2026-08-18)

Die Namensfalle aus #1457 S2a (erfundener Parametername lief lautlos in 404 bei 24 grünen
Tests) ist für diese Spec **vorab ausgeschlossen**. Gemessen gegen `GET
/nwp-v1-1h-2500m/metadata` und echte Punktabrufe:

| Prüfung | Ergebnis |
|---|---|
| Metadata-Endpoint | 19 Parameter, darunter `cape` (Einheit `m2 s-2`) und `cin` (Einheit `J kg-1`); Gitter-`bbox = [42.981, 5.498, 51.819, 22.102]` |
| Punkt 46.66/12.74 (Karnischer Höhenweg), 56 h | `cape` 0,5 … 380,8, Nachmittagsanstieg vorhanden · `cin` 0,0 bis −0,1 |
| Punkt außerhalb des Modellgitters (42.22/9.07, Korsika) | HTTP 400 `"Requested point ... is outside of dataset bounds!"` |
| Unbekannter Parametername im selben Abruf | HTTP 400 `"Parameters {'gibtesnicht'} do not exist or access is denied"` — **der gesamte Abruf scheitert** |
| Antwortzeit je Abruf | ~7 s gemessen |

**Einheiten-Falle:** `m2 s-2` und `J kg-1` sind dimensionsgleich (1 J/kg = 1 m²/s²). Die Zahlen
sind identisch, es darf **nicht** umgerechnet werden.

**Gitter-Falle:** Das AROME-Gitter (`bbox = [42.981, 5.498, 51.819, 22.102]`, Metadata-Endpunkt,
gemessen 2026-08-18) ist deutlich kleiner als das `DE_ALPEN`-Zuständigkeitsrechteck aus
`thunder_routing._REGIONS` (`43.17…58.09 lat, −3.95…20.35 lon`) — Punkte wie Hamburg (53,55 N)
oder Berlin (52,5 N) liegen in `DE_ALPEN`, aber außerhalb des AROME-Gitters.

Rohdaten der Messung liegen im Kontext-Dokument `docs/context/feat-1758-geosphere-cape-cin.md`.

## Scope-Abgrenzung

**In dieser Spec, zwei Scheiben, beide in diesem Auftrag (B unmittelbar nach A):**

- **Scheibe A — Beschaffung.** Zweiter, gekapselter GeoSphere-Abruf für `cape`/`cin` (Vorbild
  `fetch_snowgrid`, `geosphere.py:303-328`); zwei neue Felder an `ForecastDataPoint`;
  `GeoSphereProvider` erfüllt `fetch_thunder_signals_named`; zwei neue Zeilen in
  `_SIGNAL_ZU_FELD`. **Kein** Eintrag in `thunder_routing` — diese Scheibe allein ändert nichts
  am Live-Verhalten und ist deshalb isoliert testbar (AC-1 bis AC-5).
- **Scheibe B — Wirksamkeit.** `thunder_routing` weist Österreich zusätzlich zu `de_direct`
  eine zweite Quelle zu, begrenzt auf das tatsächliche AROME-Gitter (nicht das gesamte
  `DE_ALPEN`-Rechteck); der Fill-only-Wächter in `enrich_thunder` wird von "irgendein bekanntes
  Feld befüllt" auf "diese Quelle hat bereits geliefert" umgestellt; der Zusatzabruf bekommt ein
  eigenes Zeitbudget; neues ADR. Dadurch entstehen GeoSphere-CAPE/CIN im Normalbetrieb (AC-6
  bis AC-13).

**Nicht in dieser Spec:**

- **Keine Schwellen, keine Eichung, keine Stufenbildung** für GeoSphere-CAPE. GeoSphere
  archiviert AROME nicht rückwirkend (`GET /v1/datasets`), eine Eichung ist heute nicht
  herstellbar — Projektprinzip "keine Aussage statt geratener Schwelle".
- **Keine Behebung der Modellnamen-Kollision** `model="AROME"` → `meteofrance_arome`
  (`model_registry.py:43`). Das ist ein bestehender, latenter Nebenbefund, gebucht in #1199.
  Diese Spec umgeht ihn nur durch eigene Felder (Invariante 3 unten), behebt ihn nicht.
- Kein neuer Vertretungs-Eintrag für GeoSphere-Ausfall in `_VERTRETUNG`
  (`thunder_routing.py:105-109`, ADR-0047) — GeoSphere bleibt bei echtem Ausfall einfach leer,
  fail-soft, wie jede Quelle ohne Eintrag dort heute auch.

## Invarianten (gelten für beide Scheiben)

1. **Die Grundvorhersage darf nie kippen.** Fällt der cape/cin-Abruf aus, bleiben die zwei
   Felder leer und Temperatur/Wind/Schnee kommen unverändert. Live belegt: ein unbekannter
   Parametername lässt bei GeoSphere den **gesamten** Abruf mit HTTP 400 scheitern — deshalb
   ist der getrennte, gekapselte Request Pflicht, nicht Geschmack (AC-2).
2. **Keine Umrechnung.** `cape` (`m2 s-2`) und `cin` (`J kg-1`) sind dimensionsgleich; Zahlen
   unverändert übernehmen (AC-3).
3. **Eigene Felder, kein Mitbenutzen von `cape_jkg`.** Sonst zieht `effective_cape_model_id`
   wegen `reihe.meta.model="AROME"` die Météo-France-Eichleiter (`model_registry.py:43`) —
   Fehlertyp #1678 (AC-10).
4. **Keine Einstufung, keine Fusion, keine Ausgabeänderung.** Ausgabe-Invarianz wie #1531 AC-9:
   keine neue Spalte, kein neues Token, keine geänderte Gewitterstufe in E-Mail, SMS, Telegram,
   Premium-SMS oder Ortsvergleich. GeoSphere-CAPE darf `dp.thunder_level` auf keinem Weg
   beeinflussen — das schützt ADR-0025 (AC-9).
5. **Leer bleibt leer, nie 0.** "Keine Aussage" ist nicht "keine Gefahr" (AC-4).
6. **Der DWD bleibt für AT die Blitzpotenzial-Quelle.** GeoSphere kommt additiv hinzu und
   ersetzt nichts (AC-7).
7. **Eine Zusatzquelle gilt nur innerhalb ihres eigenen Modellgitters**, nicht im gesamten
   Gebietsrechteck der Primärquelle. Das AROME-Gitter (Metadata-Endpunkt, gemessen 2026-08-18:
   `bbox = [42.981, 5.498, 51.819, 22.102]`) ist kleiner als `DE_ALPEN` — Punkte außerhalb des
   Gitters (z. B. Hamburg, Berlin) bekommen `geosphere` gar nicht erst als zuständig zugewiesen,
   statt bei jedem Lauf einen von vornherein aussichtslosen HTTP-400-Abruf zu erzeugen (AC-12).
8. **Der Zusatzabruf hat ein eigenes Zeitbudget** und darf das Budget der Primärquelle (DWD,
   `THUNDER_FETCH_DEADLINE_SECONDS`, `dwd.py`) weder teilen noch aufzehren — Vorbild dort.
   Scheitert oder verzögert sich der Zusatzabruf, bleiben nur seine eigenen Felder leer; die
   Primärquelle und der Gesamtlauf bleiben unberührt (AC-13).

## Implementation Details

### 1. Scheibe A — zweiter, gekapselter Abruf (`geosphere.py`)

Eigene Parameterliste und eigener Request, analog `fetch_snowgrid` — **nicht** Teil von
`NWP_PARAMS`/`fetch_nwp_forecast`, damit ein künftiger Namenswechsel bei `cape`/`cin` niemals
die Grundvorhersage (Temperatur/Wind/Schnee) mitreißt (Invariante 1):

```python
CAPE_CIN_PARAMS = ["cape", "cin"]

def fetch_thunder_signals_named(
    self, location, start=None, end=None,
) -> Dict[str, Dict[int, Optional[float]]]:
    """#1758: cape/cin als benannte Gewittersignale, additiv zu DWD."""
    try:
        data = self._request(
            ENDPOINTS["nwp"], location.latitude, location.longitude,
            CAPE_CIN_PARAMS, start, end,
        )
    except httpx.HTTPStatusError:
        return {"cape": {}, "cin": {}}
    return self._parse_cape_cin_response(data, start)
```

`_parse_cape_cin_response` liest `cape`/`cin` analog zu `_parse_nwp_response` (sichere
Indizierung, fehlender Wert bleibt `None`) und bildet Zeitstempel auf Stunden-Offsets ab dem
`_bezugszeitpunkt` der aufrufenden Reihe ab (dasselbe Offset-Schema wie
`thunder_enrichment._hole_eintraege` erwartet — siehe Implementation Details Punkt 4 unten zur
Offset-Konvention).

### 2. Zwei neue Felder (`models.py`)

```python
# Gewittersignale GeoSphere AROME Oesterreich (#1758, additiv zu #1457 S2b):
# CAPE und CIN sind bei GeoSphere dimensionsgleich zu J/kg (m2 s-2 == J/kg,
# 1 J/kg = 1 m^2/s^2) -- NICHT umrechnen. Eigene Felder statt cape_jkg /
# convective_inhibition_jkg mitzubenutzen: reihe.meta.model="AROME" wuerde
# ueber normalize_model_id() sonst die Meteo-France-CAPE-Eichleiter ziehen
# (model_registry.py:43), Fehlertyp #1678. Diese Scheibe reicht nur
# Rohwerte durch -- keine Einstufung.
cape_geosphere_jkg: Optional[float] = None                   # J/kg, AROME (GeoSphere)
convective_inhibition_geosphere_jkg: Optional[float] = None  # J/kg, AROME (GeoSphere)
```

Namenswahl `*_geosphere_jkg` statt `cape_ml_jkg`/`convective_inhibition_jkg` (die DWD-Felder
aus #1531): eine dritte Quelle für dieselbe fachliche Größe, die bestehenden Namen sind bereits
vergeben und würden bei Wiederverwendung Invariante 3 verletzen.

### 3. Signal→Feld-Zuordnung (`thunder_enrichment.py:36-50`)

```python
"cape": "cape_geosphere_jkg",
"cin": "convective_inhibition_geosphere_jkg",
```

Zwei neue Paare in `_SIGNAL_ZU_FELD`. Der bestehende Dispatch (`setattr(dp, feld, wert)` nur
bei `wert is not None`) bleibt unverändert — Scheibe A rührt `thunder_enrichment.py` nur an
dieser einen Tabelle an.

### 4. Offset-Konvention — verbindlich für den GeoSphere-Parser

`thunder_enrichment._bezugszeitpunkt` (Zeilen 76-93) legt fest: die Stunden-Offsets beginnen
bei **1**, der Nullpunkt liegt eine Stunde VOR dem ersten gewünschten Zeitpunkt. Gesetzt wird
über `dp = nach_ts.get(basis + timedelta(hours=offset))` (Zeile 343). `_parse_cape_cin_response`
MUSS dieselbe Konvention anwenden — ein naiver `enumerate()`-ab-0-Parser verschiebt jeden Wert
um eine Stunde, ohne dass ein reiner Wertevergleich (AC-1/AC-3) das bemerken würde (AC-11 prüft
genau das).

### 5. Scheibe B — mehrere Quellen je Gebiet, nur innerhalb des tatsächlichen Modellgitters
   (`thunder_routing.py`, `geosphere.py`)

`_REGIONS` liefert heute genau einen Providernamen je Gebiet (`thunder_provider_for`,
first-match-wins). Für Österreich braucht es **zwei** gleichzeitig gültige Quellen
(`de_direct` UND `geosphere`), ohne die bestehende Zuordnung für FR/DE_ALPEN/EU_REST zu
verändern.

**GeoSphere gilt NICHT für das gesamte `DE_ALPEN`-Rechteck**, sondern nur innerhalb des
tatsächlichen AROME-Gitters (gemessen am Metadata-Endpunkt, 2026-08-18: `bbox = [42.981,
5.498, 51.819, 22.102]`) — deutlich kleiner als `DE_ALPEN` (`43.17…58.09 lat, −3.95…20.35 lon`)
und schließt z. B. Hamburg (53,55 N) und Berlin (52,5 N) aus. Ein Punkt außerhalb des
AROME-Gitters bekommt `geosphere` deshalb gar nicht erst als zuständig zugewiesen — derselbe
Grundsatz wie in `thunder_provider_for` für Gebiete ganz ohne Quelle ("kein Abruf ausserhalb
eines Zustaendigkeitsgebiets"), jetzt zusätzlich für eine einzelne Zusatzquelle innerhalb eines
größeren Primärquellen-Rechtecks angewendet (Invariante 7, AC-12). Umsetzung analog zum
bestehenden `snowgrid_covers()` (`geosphere.py:96-99`, dort von `openmeteo.py:184` importiert):
eine eigene Bounds-Prüfung (z. B. `arome_grid_covers(lat, lon)` in `geosphere.py`, von
`thunder_routing` importiert) statt "einfach abrufen und HTTP 400 abfangen" — Letzteres würde
bei jedem Lauf für jeden Punkt außerhalb des Gitters sinnlose Last erzeugen.

Der Zusatzabruf bekommt ein **eigenes Zeitbudget**, das die Primärquelle (DWD,
`THUNDER_FETCH_DEADLINE_SECONDS`, `dwd.py`) weder teilt noch aufzehrt (Invariante 8). Gemessen
wurden ~7 s je GeoSphere-Abruf; verzögert oder scheitert er, bleiben nur die GeoSphere-Felder
leer, DWD wird nicht berührt und der Gesamtlauf bricht nicht ab (AC-13).

Die bestehende Funktion `thunder_provider_for()` (Rückgabetyp `Optional[str]`, genutzt von
`_fetch_lightning_density` für die **primäre** Quelle und von `thunder_vertretung_for`) bleibt
für Bestandsaufrufer unverändert und liefert weiterhin die primäre Quelle. Zusätzlich entsteht
eine Abfrage aller zuständigen Quellen eines Gebiets (Rückgabe als Liste/Tupel), die
`_fetch_lightning_density` durchläuft — Datenstruktur der Tabelle ist Implementierungsdetail der
TDD-Phase, die beobachtbare Zuständigkeit ist es nicht: **ein Punkt innerhalb des AROME-Gitters
muss danach beide, `de_direct` und `geosphere`, als zuständig ausweisen; ein Punkt in
`DE_ALPEN`, aber außerhalb des Gitters, nur `de_direct`** (AC-6, AC-12).

### 6. Fill-only-Wächter je Quelle (`thunder_enrichment.py:222-231`)

Der heutige Wächter prüft global über `_bekannte_felder()` — sobald IRGENDEIN bekanntes Signal
gefüllt ist, bricht die gesamte Anreicherung ab. Bei zwei Quellen je Gebiet käme die zweite
Quelle dadurch **nie** zum Zug, sobald die erste ein Feld gefüllt hat. Der Wächter muss je
Quelle geführt werden: für jede zuständige Quelle wird nur geprüft, ob **deren eigene** Felder
(die Teilmenge von `_SIGNAL_ZU_FELD`, die diese Quelle beim benannten Abruf zurückgibt, bzw.
`_EINZELWERT_FELD` beim Einzelwert-Weg) bereits belegt sind — nicht die Felder einer anderen
Quelle. Betrifft nur den Fill-only-Kurzschluss; die Fusion (`_fuse_thunder_levels`) bleibt
unverändert und liest weiterhin ausschließlich `cape_jkg`/`convective_inhibition_jkg`/
`lightning_potential_lpi_jkg` — **nicht** die neuen GeoSphere-Felder (Invariante 3/4).

### 7. Neues ADR

`docs/adr/0057-mehrere-gewitter-signalquellen-je-gebiet.md` (nächste freie Nummer, gegengeprüft
gegen den Index — höchste bestehende ist 0056): "Mehrere Gewitter-Signalquellen je Gebiet sind
additiv erlaubt." Grenzt sich ab von:

- **ADR-0025** ("eine Gewitter-Quelle für alle Briefing-Kanäle") — betrifft die
  **Kanal**-Ebene: alle Kanäle lesen dieselbe Rohgröße `dp.thunder_level`. Mehrere
  Beschaffungs-Quellen widersprechen dem nicht, solange am Ende weiterhin genau ein
  `dp.thunder_level` steht (Invariante 4). Kein "Abgelöst durch".
- **ADR-0047** (Vertretung zwischen Direktquellen bei echtem Ausfall) — ein anderer Mechanismus
  (`_VERTRETUNG`) und bleibt unberührt; GeoSphere bekommt dort bewusst keinen Eintrag (siehe
  Scope-Abgrenzung).

## Expected Behavior

- **Input:** Ort + Zeitfenster wie heute; keine neue Schnittstelle nach außen
- **Output:** zwei zusätzlich befüllte Felder je `ForecastDataPoint` für Orte im AROME-Gitter
  (v. a. Österreich), zusätzlich zu den bereits vom DWD befüllten Blitzpotenzial-Feldern
- **Side effects:** ein zusätzlicher HTTP-Abruf gegen `dataset.api.hub.geosphere.at` je
  Anreicherung eines Punkts **innerhalb des AROME-Gitters**, begrenzt durch ein eigenes
  Zeitbudget; **keine** Änderung an irgendeiner Nutzerausgabe

## Acceptance Criteria

> **Hinweis zur Testart:** Scheibe A ist reiner Datenabruf, Scheibe B reine
> Zuständigkeits-/Anreicherungslogik — beide dürfen per Invariante 4 **keine** Ausgabe
> verändern, ein Nachweis über Mail/SMS/Compare ist deshalb für die meisten ACs strukturell
> unmöglich und wäre ein Widerspruch zum Scope. Beobachtbares Verhalten ist hier: *die
> Anreicherung ausführen und den entstandenen Datenpunkt bzw. die Zuständigkeitstabelle
> befragen.* Tests laufen gegen aufgezeichnete GeoSphere-API-Antworten (JSON-Fixtures, analog
> den GRIB-Fixtures aus #1531) und gegen den echten `enrich_thunder`-Ablauf. **Kein** Test liest
> Quelltext oder prüft Dateiinhalte per `read_text()`.

- **AC-1:** Given ein Ort im AROME-Gitter (z. B. Karnischer Höhenweg) mit veröffentlichtem Lauf
  / When der GeoSphere-Anbieter nach benannten Gewittersignalen befragt wird / Then liefert er
  `cape` und `cin` mit denselben Zahlen, die die aufgezeichnete GeoSphere-Antwort an diesem
  Gitterpunkt enthält.
  - Test: `GeoSphereProvider.fetch_thunder_signals_named()` gegen eine aufgezeichnete
    JSON-Antwort ausführen; Rückgabewerte gegen unabhängig aus derselben Datei ausgelesene
    Werte vergleichen — nicht gegen eine im Test notierte Konstante.

- **AC-2:** Given der cape/cin-Abruf scheitert (z. B. unbekannter Parametername oder HTTP 400)
  / When dieselbe Reihe trotzdem Temperatur, Wind und Schnee enthält / Then bleiben
  `cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg` `None`, und `t2m_c`,
  `wind10m_kmh`, `snow_new_acc_cm` sind an denselben Datenpunkten unverändert befüllt.
  - Test: `fetch_combined`/`enrich_thunder` mit einer gestubbten fehlschlagenden
    cape/cin-Antwort ausführen; Grundvorhersage-Felder mit einem Lauf ohne den Zusatzabruf
    zeichenweise vergleichen — sie müssen identisch sein.

- **AC-3:** Given `cape` und `cin` liegen in der GeoSphere-Antwort in `m2 s-2` bzw. `J kg-1` vor
  / When die Werte am Datenpunkt gespeichert werden / Then entspricht die gespeicherte Zahl
  exakt dem Rohwert aus der Antwort, ohne Faktor.
  - Test: Aufgezeichneter Wert (z. B. `cape=380.8`) muss unverändert als `380.8` am
    Datenpunkt stehen — jede Umrechnung (z. B. ×1000, /9.81) würde den Test rot machen.

- **AC-4:** Given ein Punkt außerhalb des AROME-Gitters (live gemessen: HTTP 400 "outside of
  dataset bounds") / When die Anreicherung läuft / Then bleiben beide GeoSphere-Felder `None`
  und keines trägt `0` oder `0.0`.
  - Test: Abruf für einen Punkt außerhalb des Gitters (gestubbte HTTP-400-Antwort) ausführen;
    beide Felder müssen `None` sein — Gegenprobe im selben Test mit einem Punkt im Gitter, der
    reale Werte behält, sonst würde ein Filter, der pauschal alles verwirft, ebenfalls grün.

- **AC-5:** Given `GeoSphereProvider` implementiert `fetch_thunder_signals_named` / When
  `thunder_enrichment._hole_eintraege` die Quelle `"geosphere"` befragt / Then erkennt sie den
  benannten Weg (nicht den Einzelwert-Weg) und ordnet `cape`/`cin` über `_SIGNAL_ZU_FELD` den
  Feldern `cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg` zu.
  - Test: `_hole_eintraege("geosphere", ...)` gegen den echten Provider mit gestubbter
    HTTP-Antwort ausführen; Rückgabe muss die zwei erwarteten Feld-Wert-Paare enthalten.

- **AC-6:** Given ein Ort in Österreich innerhalb des AROME-Gitters / When die
  Gewitter-Zuständigkeit dieses Orts abgefragt wird / Then weist sie **beide** Quellen aus,
  `de_direct` und `geosphere` — nicht nur eine.
  - Test: Zuständigkeitsabfrage für einen AT-Punkt (z. B. Karnischer Höhenweg) ausführen; das
    Ergebnis muss beide Providernamen enthalten. Mutations-Gegenprobe: würde `geosphere` aus
    der Zuordnung entfernt, MUSS der Test rot werden — sonst prüft er nichts.

- **AC-7:** Given ein AT-Punkt, an dem der DWD bereits `lightning_potential_lpi_jkg` gefüllt hat
  / When `enrich_thunder` erneut auf derselben Reihe läuft / Then wird `geosphere` trotzdem
  noch abgerufen und füllt `cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg` — der
  Fill-only-Wächter bricht nicht mehr global ab, sobald irgendeine Quelle geliefert hat.
  - Test: `enrich_thunder()` gegen eine Reihe ausführen, deren DWD-Felder bereits vorbelegt
    sind (simuliert einen vorherigen Aufruf); danach müssen die GeoSphere-Felder befüllt sein.
    Mutations-Gegenprobe: der alte globale Wächter (`any(... for feld in _bekannte_felder())`)
    MUSS diesen Test rot machen, wenn er wiederhergestellt wird — sonst beweist AC-7 nichts.

- **AC-8:** Given ein AT-Punkt / When die Anreicherung vollständig durchläuft / Then trägt
  `lightning_potential_lpi_jkg` weiterhin den DWD-Wert (unverändert zum Stand ohne GeoSphere),
  und GeoSphere schreibt an keiner Stelle in dieses Feld.
  - Test: Anreicherung für einen AT-Punkt einmal mit und einmal ohne den GeoSphere-Eintrag in
    der Zuständigkeitstabelle ausführen; `lightning_potential_lpi_jkg` muss in beiden Läufen
    identisch sein.

- **AC-9:** Given ein Trip-Briefing, ein Ortsvergleich und eine SMS für einen AT-Punkt werden
  erzeugt / When die GeoSphere-Felder befüllt sind / Then ist keine einzige Ausgabe anders als
  vorher — keine neue Spalte, kein neues Token, keine geänderte Gewitterstufe.
  - Test: Briefing-Mail, Compare-Mail und SMS aus identischen Eingangsdaten erzeugen — einmal
    mit befüllten GeoSphere-Feldern, einmal mit leeren — und die erzeugten Ausgaben
    zeichenweise vergleichen. Sie müssen identisch sein.

- **AC-10:** Given ein Datenpunkt mit `reihe.meta.model="AROME"` (GeoSphere-Herkunft) und
  befüllten GeoSphere-cape/cin-Feldern / When `_fuse_thunder_levels` läuft / Then bleibt
  `dp.cape_jkg` (das Open-Meteo-Feld) unverändert `None` bzw. unangetastet, und die
  CAPE-Fusion liest ausschließlich `dp.cape_jkg`, nicht `dp.cape_geosphere_jkg`.
  - Test: Datenpunkt mit gesetztem `cape_geosphere_jkg`, aber leerem `cape_jkg` durch die
    Fusion laufen lassen; `thunder_level` darf sich gegenüber einem Lauf ohne
    `cape_geosphere_jkg` nicht ändern — Nachweis, dass die Météo-France-Eichleiter
    (`model_registry.py:43`) nicht versehentlich auf GeoSphere-Werte angewendet wird.

- **AC-11:** Given eine aufgezeichnete GeoSphere-Antwort, in der `cape` über die Stunden einen
  eindeutig identifizierbaren Verlauf hat (z. B. Tagesgang mit einem einzigen klaren Maximum am
  Nachmittag) / When die Anreicherung die Werte an die Datenpunkte der Reihe legt / Then steht
  das Maximum an **demselben Zeitstempel**, den die aufgezeichnete Antwort dafür ausweist —
  nicht eine Stunde davor oder danach.
  - Test: Zeitstempel des Maximums unabhängig aus der Fixture auslesen (nicht als Konstante im
    Test notieren) und mit dem `ts` des Datenpunkts vergleichen, der den Maximalwert trägt.
    **Mutations-Gegenprobe Pflicht:** eine Verschiebung der Offset-Abbildung um ±1 Stunde MUSS
    diesen Test rot machen — genau der Fehlertyp aus #874/#1275 (Wert aus der falschen
    Stunde/Etappe), der ein reiner Wertevergleich (AC-1/AC-3) nicht fängt.

- **AC-12:** Given ein Punkt innerhalb des Gebiets `DE_ALPEN`, aber außerhalb des AROME-Gitters
  (Hamburg, 53.55/9.99) / When die zuständigen Gewitterquellen für diesen Punkt ermittelt
  werden / Then ist `geosphere` nicht darunter, und es wird kein GeoSphere-Abruf versucht.
  - Test: Zuständigkeitsabfrage für Hamburg ausführen — `geosphere` darf nicht enthalten sein.
    Gegenprobe im selben Test mit einem Punkt im Gitter (Karnischer Höhenweg), der `geosphere`
    enthalten muss; sonst wäre auch ein Filter grün, der pauschal alles verwirft.

- **AC-13:** Given der GeoSphere-Zusatzabruf antwortet nicht innerhalb seiner Zeitgrenze / When
  die Anreicherung läuft / Then bleiben beide GeoSphere-Felder leer, die Felder der
  Primärquelle (DWD) sind vollständig befüllt, und der Gesamtlauf bricht nicht ab.
  - Test: Zusatzabruf mit einer verzögerten Antwort ausführen; DWD-Felder müssen vollständig
    sein, GeoSphere-Felder `None`, kein Abbruch.

## Estimated Scope

**Scheibe A:**
- **LoC:** ~60–90 (Produktivcode) + Tests
- **Files:** `geosphere.py` (+~50 LoC: `CAPE_CIN_PARAMS`, `fetch_thunder_signals_named`,
  `_parse_cape_cin_response`), `models.py` (+~6 LoC: zwei Felder + Kommentar),
  `thunder_enrichment.py` (+~2 LoC: zwei `_SIGNAL_ZU_FELD`-Zeilen)
- **Effort:** low

**Scheibe B:**
- **LoC:** ~70–110 (Produktivcode) + Tests + ADR-Datei (zählt nicht gegen das LoC-Limit,
  `docs/`)
- **Files:** `thunder_routing.py` (+~35–45 LoC: Mehrfach-Zuständigkeit + AROME-Bounds-Prüfung +
  Docstring-Update), `geosphere.py` (+~10 LoC: `arome_grid_covers()`, analog
  `snowgrid_covers()`), `thunder_enrichment.py` (+~25–40 LoC: Fill-only-Wächter je Quelle,
  Schleife über zuständige Quellen samt eigenem Zeitbudget in `_fetch_lightning_density`),
  `docs/adr/0057-*.md` (neu)
- **Effort:** medium (Fill-only-Umbau berührt den gemeinsamen Anschlusspunkt für alle Gebiete,
  Regressionsrisiko für FR/DE_ALPEN/EU_REST — deshalb AC-7 als Mutationstest Pflicht)

**Gesamt:** ~130–200 LoC Produktivcode, voraussichtlich über dem Standard-Workflow-Limit
(250 inkl. Tests) — `loc_limit_override` ist wahrscheinlich nötig.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `dataset.api.hub.geosphere.at` (AROME NWP) | extern | Datenquelle für `cape`/`cin`, live gemessen |
| `thunder_routing.py` | intern | Gebietszuständigkeit — wird in Scheibe B erweitert |
| `thunder_enrichment.py` | intern | einziger Anreicherungspunkt — Fill-only-Wächter wird in Scheibe B umgebaut |
| `model_registry.py` | intern | CAPE-Eichleiter — unverändert, Invariante 3 verhindert Berührung |
| ADR-0025 | Konzept | eine Gewitter-Quelle je Kanal-Ausgabe — bleibt unberührt (Kanal- ≠ Beschaffungsebene) |
| ADR-0047 | Konzept | Vertretung bei echtem Dienstausfall — bleibt unberührt |
| #1419 §2a/§3.2/§5 | Konzept | Größenliste je Gebiet, `None`-Kontrakt |
| feat_1531_s1_dwd_gewittergroessen | Spec | direktes Vorbild für Zuschnitt, Testart, Ausgabe-Invarianz |

## Known Limitations

- **Kein bekannter Sentinel-Wert bei GeoSphere gemessen.** Für DWD ist `9999,0`/`-999,9`
  dokumentiert (#1531); für GeoSphere ist an einem Punkt über 56 h kein Fehlwert aufgetreten
  (`cin` durchgängig 0,0 bis −0,1). Ob GeoSphere innerhalb des Gitters einen eigenen
  Fehlwert-Marker verwendet, ist ungemessen — in der TDD-Phase an mehreren Punkten prüfen,
  bevor ein zusätzlicher Sentinel-Filter gebaut wird.
- **Offset-Konvention ist scharf und fehleranfällig.** Die Stunden-Offsets in
  `thunder_enrichment._bezugszeitpunkt` beginnen bei 1, der Nullpunkt liegt eine Stunde VOR dem
  ersten gewünschten Zeitpunkt (`_hole_eintraege`/`_fetch_lightning_density`, Zeile 343). Der
  neue GeoSphere-Parser (`_parse_cape_cin_response`) muss exakt dieselbe Konvention einhalten —
  ein Off-by-one verschiebt jeden Wert um eine Stunde, ohne dass ein reiner Wertevergleich das
  zeigt (AC-11 ist deshalb Pflicht, nicht Kür; Präzedenzfehler #874/#1275).
- **Jeder Punkt innerhalb des AROME-Gitters kostet einen zusätzlichen HTTP-Abruf je
  Anreicherung**, begrenzt durch das eigene Zeitbudget des Zusatzabrufs (Invariante 8). Gemessen
  ~7 s je Abruf — bei einem System mit bestehenden Timeout-Problemen (#1839, #1539) ist das ein
  eigenständiges Ausfallrisiko, das AC-13 absichert, aber nicht beseitigt.
- **Modellnamen-Kollision bleibt bestehen.** `geosphere.py:501` setzt weiterhin
  `model="AROME"`; diese Spec umgeht die Kollision nur durch eigene Feldnamen (Invariante 3),
  behebt sie nicht. Nebenbefund bleibt in #1199 gebucht.
- **Fill-only-Umbau ist ein gemeinsamer Anschlusspunkt.** Die Umstellung von global auf je
  Quelle wirkt auch auf FR/DE_ALPEN/EU_REST, auch wenn diese Gebiete (noch) nur eine Quelle
  haben — Regressionsrisiko, deshalb ist AC-7 als Mutationstest Pflicht, nicht Kür.
- **Kein Vertretungs-Eintrag für GeoSphere.** Fällt GeoSphere aus, bleiben die zwei Felder
  einfach leer (fail-soft) — keine automatische Ersatzquelle, analog zu jeder anderen Quelle
  ohne Eintrag in `_VERTRETUNG` heute.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0057 (neu, "Mehrere Gewitter-Signalquellen je Gebiet (additiv)")
- **Rationale:** Bisher galt implizit first-match-wins mit genau einer Quelle je Gebiet
  (`thunder_routing._REGIONS`). Der PO-Entscheid "voll wirksam" verlangt für Österreich zwei
  gleichzeitig gültige Quellen, ohne die bestehende Ein-Quelle-Garantie für andere Gebiete
  anzutasten oder ADR-0025 (eine Quelle je **Kanal**-Ausgabe, `dp.thunder_level`) zu verletzen.
  Das neue ADR hält fest: additive Beschaffung ist erlaubt, solange am Ende weiterhin genau ein
  `dp.thunder_level` aus der Fusion entsteht.

## Changelog

- 2026-08-18: Initial spec created
- 2026-08-18: AC-11 (zeitliche Zuordnung, Offset-Konvention) nach Team-Lead-Review ergänzt —
  Lücke: AC-1/AC-3 prüften nur Werte, nicht die Stunde ihrer Zuordnung (Präzedenz #874/#1275)
- 2026-08-18: AC-12/AC-13 sowie Invarianten 7/8 ergänzt — Entwurfsfehler aus der
  Implementierung: AROME-Gitter ist kleiner als das `DE_ALPEN`-Zuständigkeitsrechteck (gemessen
  `bbox = [42.981, 5.498, 51.819, 22.102]`), Zusatzabruf braucht ein eigenes Zeitbudget
