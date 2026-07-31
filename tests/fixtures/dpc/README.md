# DPC-Fixtures (Issue #1427 S2)

Quelle: `https://raw.githubusercontent.com/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files/all/<YYYYMMDD>_<HHMM>_all.zip`
(oeffentlich, auth-frei). Jede Original-Zip-Datei ist ~4,6 MB; abgelegt wird
NUR die Auswahl, die die Tests brauchen (die beiden `_today.dbf`/`_tomorrow.dbf`
+ `Cap_<ts>.xml`), neu gepackt als kleineres Zip. Werte darin sind
**unveraendert** — reine Dateiauswahl, keine Wertaenderung.

## Echte Aufzeichnungen

### `ruhetag_20260730_1511.zip` — Ruhetag + Tagesversatz-Fall (AC-3)

Abgerufen am 2026-07-31 von `files/all/20260730_1511_all.zip`. Genau EINE
gewarnte Zone in der gesamten Datei: `Tren-A` ("Provincia Autonoma di
Bolzano"), Feld `Temporali` = `Ordinaria / ALLERTA GIALLA`, ausschliesslich im
`tomorrow`-Datensatz (Bezugstag 31.07.). Der `today`-Datensatz (Bezugstag
30.07.) ist vollstaendig `NESSUNA ALLERTA` — das macht dieses Bulletin zugleich
zum Tagesversatz-Testfall: wird es am 31.07. frueh abgefragt (Bulletin selbst
vom 30.07. 15:11, noch das neueste verfuegbare), MUSS die Warnung aus dem
`tomorrow`-Teil kommen; ein `today.dbf` lesender Code liefert faelschlich [].

Enthaelt: `20260730_1511_today.dbf`, `20260730_1511_tomorrow.dbf`,
`Cap_20260730_1511.xml`. Weggelassen: `.shp`/`.shx`/`.prj` (Laufzeit liest nur
die DBF, s. Spec "Implementation Details" Punkt 2), die PDF-Zusammenfassung
und die RNDT/DCAT-Metadaten-XML.

### `unwettertag_20260118_1515.zip` — Unwettertag mit ARANCIONE/ROSSA

Abgerufen am 2026-07-31 aus dem Archiv (`files/all/20260118_1515_all.zip`,
gefunden nach 10 Stichproben ueber Herbst/Winter 2025/26). Reichhaltigstes
Bulletin der Stichprobe:

- `today` (Bezugstag 18.01.): `Cala-6`/`Cala-7` (Kalabrien) ARANCIONE auf
  `Idrogeo`, `Temporali` UND `Idraulico` gleichzeitig; `Sici-A`/`Sici-H`/
  `Sici-I` GIALLA auf `Temporali`. Deckt den Test "eine Zone GIALLA
  Temporali, eine andere Zone ARANCIONE Idrogeo, selbes Bulletin" ab.
- `tomorrow` (Bezugstag 19.01.): `Sard-A`/`Sard-B`/`Sard-D`/`Sard-F`
  (Sardinien) ROSSA auf `Idrogeo` bei `Temporali` = NESSUNA — reiner
  Hochwasser/Erdrutsch-Fall auf Stufe 4; `Sard-E` ARANCIONE auf `Idrogeo`
  bei `Temporali` = NESSUNA — reiner Hochwasser/Erdrutsch-Fall auf Stufe 3;
  `Cala-6`/`Cala-7` weiterhin ARANCIONE.

Enthaelt: `20260118_1515_today.dbf`, `20260118_1515_tomorrow.dbf`,
`Cap_20260118_1515.xml`. Gleiche Auswahl-Begruendung wie oben.

**Suche dokumentiert (PO-Vorgabe "hoechstens ~10 Archiv-Abrufe"):** 10 Daten
aus Okt. 2025 - Feb. 2026 stichprobenartig abgerufen
(`files/all/<datum>_all.zip`) und auf `ARANCIONE`/`ROSSA` geprueft:
20251022 (27/21 ARANCIONE-Treffer today/tomorrow), 20251103 (0), 20251118 (0),
20251203 (6/43), 20251222 (0), 20260107 (0), **20260118 (8/24 ARANCIONE, 0/8
ROSSA — gewaehlt)**, 20260204 (0), 20260213 (16/30), 20260225 (0). 20260118
gewaehlt, weil es zusaetzlich zum ARANCIONE-Kriterium auch eine reine
Idrogeo-Warnung (ohne begleitende Temporali-Warnung derselben Zone) UND eine
ROSSA-Stufe enthaelt.

## Synthetische Fail-soft-Fixtures (AC-5, analog `cap_broken.xml` bei MeteoAlarm)

**Keine Aufzeichnungen** — bewusst konstruierte Robustheitstests, dokumentiert
als solche (Projektregel "aufgezeichnete Werte niemals von Hand aendern"
betrifft reale Aufzeichnungen, nicht absichtlich-synthetische Negativfixtures,
Praezedenzfall `tests/fixtures/meteoalarm/cap_broken.xml`).

- `synthetic_unknown_stufe_pattern.zip` — DBF mit derselben Feldstruktur wie
  die echten Bulletins (`Zona_all`/`Nome_zona`/`Criticita`/`Idrogeo`/
  `Temporali`/`Idraulico`), EIN Datensatz fuer die reale Zone `Abru-A`
  ("Bacini Tordino Vomano"), `Temporali` = `"Formato sconosciuto / STATO
  IMPREVISTO"` — ein Freitext, der NICHT dem Muster `<Kritikalitaet> /
  ALLERTA <FARBE>` entspricht.
- `synthetic_unknown_zone_code.zip` — DBF mit gueltigem Freitext-Muster
  (`Temporali` = `"Ordinaria / ALLERTA GIALLA"`), aber `Zona_all` = `"Xyz-9"`
  — ein Code, der in `dpc_zones.json` nicht existiert.

Beide erzeugt mit `pyshp` (Scratch-Werkzeug, nicht Teil des Projekts) im
selben Feldschema wie die echten DPC-Bulletins; Timestamp-Praefix
`20260115_1200` frei gewaehlt (kein realer Abrufzeitpunkt).

## Kaputtes/leeres Zip

Kein abgelegtes Fixture noetig — der Test erzeugt die kaputten Bytes
(`b"not a real zip"` bzw. leerer Body) direkt inline im Testcode ueber den
lokalen HTTP-Testserver (analog `_BrokenJSONHandler` in
`test_meteoalarm_source.py`).
