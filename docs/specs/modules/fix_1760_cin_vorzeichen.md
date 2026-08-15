# Fix #1760: CIN-Dämpfung feuert nie — zwei Vorzeichen-Konventionen ohne Normalisierung

- **Issue:** #1760 · **Bezug:** #1679 (Ursprung), #1419 (Epic), ADR-0048
- **created:** 2026-08-11
- **Typ:** Bug · **Status:** Spec, wartet auf Freigabe

## Problem

Die mit #1679 eingeführte Dämpfung der CAPE-Zutat durch die Konvektionshemmung (CIN) **feuert im
Produktivpfad nie** und wirkt invertiert: Je stärker der real gemessene Deckel, desto höher die
ausgegebene Gewitterstufe.

Ursache: Der DWD liefert `cin_ml` als **positiven Betrag**, `_gedaempft_durch_cin()`
(`src/output/metric_format.py:315-341`) erwartet **negative** Werte. Die erste Bedingung
`if cin_jkg > -25: return basis` ist bei jedem positiven Wert wahr ⇒ volle Stufe, immer.

**Wirkung, gemessen** (ICON-D2 Alpen, Lauf 2026-08-11 03Z +12 h, 906 390 Gitterpunkte): CAPE
erzeugt HIGH bei **3,88 %** der Punkte; mit wirksamer Dämpfung wären es **1,44 %** — rund
**2,7-mal so viele „hoch"-Einstufungen wie beabsichtigt**, im gesamten DWD-Gebiet (DE/Alpen/AT,
einschließlich Karnischer Höhenweg). Richtung: Über-Warnung.

## Belegte Konventionen (recherchiert 2026-08-11, nicht angenommen)

| Quelle | Vorzeichen | Beleg |
|---|---|---|
| **DWD ICON `CIN_ML`** | **positiv** | ICON-Quellcode `src/atm_phy_nwp/mo_opt_nwp_diagnostics.f90:3957-3958`: `! make CIN positive` / `cin(jc) = ABS(cin(jc) - cin_help(jc))` |
| **GRIB2-Standard** (0/7/7) | **keines definiert** | WMO-Registry 4.2/0-7-7 und NCEP-Tabelle nennen nur Name und `J kg⁻¹`. Das Vorzeichen ist **modellspezifisch** — GFS negativ, ICON positiv |
| **US-Literatur** (Penn State, SPC) | negativ | Quelle unserer Bänder −25/−50/−100/−200; bezogen auf **MLCIN über 100 hPa** |
| Open-Meteo (ICON-Domänen) | positiv | nur indirekt über den `-1`-Fehlwert erschlossen — **nicht ausdrücklich belegt** |

Die DWD-*Datenbankbeschreibung* (Tab. 5.6) dokumentiert das Vorzeichen **nicht**; belegt wird es
allein durch den Modellcode.

**Herkunft der drei Prüfwerte** (damit niemand sie für erfunden hält): **7,29** und **104,47** J/kg
sind belegte Fixture-Werte aus `tests/tdd/test_dwd_thunder_new_signals_fetch.py:31` bzw.
`test_dwd_eu_thunder_energy_signals_fetch.py:17`. **767,8** ist **kein** Fixture-Wert, sondern das
gemessene Maximum aus dem ICON-D2-Alpen-Feld (Lauf 2026-08-11 03Z +12 h, 906 390 Gitterpunkte) —
also der stärkste real beobachtete Deckel, nicht eine gegriffene Zahl.

### 🔴 Falle: −999,9 heißt „kein Auslösepunkt", nicht „extremer Deckel"

ICON-Code Z. 2700: `missing_value = -999.9_wp ! Missing value for CIN (if no LFC/CAPE was found)`.
Der **einzige** legitime negative Wert in `CIN_ML` ist der Fehlwert. Ein blindes `abs()` oder ein
schlichter Vorzeichenwechsel macht daraus **+999,9 = stärkster denkbarer Deckel** — genau verkehrt
herum. Der bestehende Filter (`dwd.py:240`, `dwd_eu.py:261`, Konstante `dwd.py:206`) fängt ihn
**vor** jeder Umrechnung ab; diese Reihenfolge ist Teil des Fixes und muss bewacht werden.

## Entscheidung: Vergleich über den Betrag, am Wirkort

Die Dämpfung vergleicht künftig den **Betrag** der Hemmung gegen die Bänder 25/50/100/200,
statt auf ein Vorzeichen zu vertrauen. Begründung gegenüber den Alternativen:

- **Nicht** beim Einlesen umdrehen: Das Feld `convective_inhibition_jkg` wird in Wetter-Schnappschüsse
  persistiert (`src/services/weather_snapshot.py:287-296`). Ein Vorzeichenwechsel dort erzeugt
  Altdaten mit positiven und Neudaten mit negativen Werten in derselben Datei-Familie — eine stille
  Zweideutigkeit ohne Migration.
- **Am Wirkort** liegt die einzige Stelle, die den Wert *interpretiert*. Sie schützt damit gegen
  **jede** Provider-Konvention (GFS negativ, ICON positiv), nicht nur gegen die heute bekannte.
- Der Betragsvergleich ist **idempotent gegenüber den Bestandstests**: Alle vorhandenen Fälle
  speisen Werte ≤ 0 ein, deren Betrag dieselbe Bandzuordnung ergibt. Kein Bestandstest ändert sich.

## Acceptance Criteria

- **AC-1:** Given der DWD liefert für eine Etappe eine Konvektionshemmung als positiven Betrag
(real gemessen: 7,29 · 104,47 · 767,8 J/kg), When die Gewitterstufe aus den Signalen fusioniert
wird, Then dämpft die Hemmung die CAPE-Zutat nach denselben Bändern wie bei negativer Eingabe —
also 7,29 ohne Dämpfung (Betrag < 25), 104,47 und 767,8 beide auf „kein Beitrag" (Betrag > 100).

  ⚠️ **Korrektur 2026-08-11 nach der Umsetzung:** Hier stand zuerst „104,47 auf höchstens
  ‚leicht'". Das war **falsch** und widersprach der Bänder-Tabelle, auf die dieses AC sich beruft:
  Das Band „auf leicht deckeln" reicht bis Betrag 100 **einschließlich**; 104,47 liegt darüber und
  fällt damit in „Deckel hält, kein Beitrag". Der Developer hat die dokumentierte Bandlogik
  implementiert statt der fehlerhaften Prosa zu folgen und den Widerspruch gemeldet — richtig so.
  Ein Wert im Band „höchstens leicht" wäre z. B. 75.

- **AC-2:** Given eine Konvektionshemmung mit negativem Vorzeichen (Bestandsverhalten, US-Konvention),
When die CAPE-Zutat gedämpft wird, Then bleibt die Zuordnung unverändert zum Stand vor diesem Fix —
kein bestehender Testfall ändert sein Ergebnis.

- **AC-3:** Given der DWD meldet den Fehlwert −999,9 („kein Auslösepunkt gefunden"), When der Wert
eingelesen wird, Then erreicht er die Dämpfung nicht, sondern wird zu „unbekannt", und die
CAPE-Zutat fällt auf die Notbremse „höchstens leicht" — **niemals** auf „stärkster Deckel" und
niemals auf „kein Deckel".

- **AC-4:** Given ein Entwickler liest die Dämpfungsfunktion, When er die Vorzeichenfrage klären will,
Then steht am Code, dass das Vorzeichen modellabhängig ist (DWD/ICON positiv, GFS/US negativ, GRIB2
legt keines fest), mit Quellenangabe — die Annahme ist damit belegt statt stillschweigend.

- **AC-5:** Given die Änderung ist umgesetzt, When ein Test die real gemessenen DWD-Werte durch den
Produktivpfad schickt, Then war dieser Test vor dem Fix rot und ist danach grün — geprüft wird die
**fusionierte Stufe**, nicht nur die Dämpfungsfunktion für sich.

- **AC-6:** Given die Gewitterstufe eines Trips im DWD-Gebiet, When ein Briefing gerendert wird,
Then fällt die Stufe gegenüber dem Stand vor dem Fix **nur** dort, wo eine Hemmung vorliegt, und
steigt nirgends — die Dämpfung dämpft ausschließlich.

## Known Limitations (bewusst NICHT in dieser Scheibe)

🔴 **Die Bänder sind für ICON nicht geeicht.** Die Beträge 25/50/100/200 stammen aus US-Praxis für
**MLCIN über 100 hPa**; ICON mischt über **50 hPa** (ICON-Code Z. 2701-2702: *„Depth of mixed
surface layer: 50hPa following Huntrieser, 1997"*), rechnet **reversibel** statt pseudoadiabatisch
und **ohne Entrainment** (ECMWF TM 852, Groenemeijer et al. 2019). Das ist dieselbe Fehlerklasse
wie ADR-0048 („CAPE ≠ CAPE"), eine Ebene tiefer.

Dieser Fix stellt her, dass die Dämpfung **überhaupt** wirkt — mit Schwellen in der richtigen
Größenordnung. Er behauptet **nicht**, dass sie geeicht sind. Die Eichung an ICON-Daten gehört zur
Feineichungs-Familie (E1b, #1678) und wird dort vermerkt.

Ebenfalls nicht in dieser Scheibe: Prüfung, ob **weitere** DWD-Größen dieselbe stille
Konventions-Annahme tragen (`sdi_2`, `uh_max`, `grau_gsp`).

## Test-Nachweis

- **Rot vor Fix:** Fusion mit `cin_jkg=104.47` und CAPE oberhalb der HIGH-Sprosse liefert heute
  „hoch", erwartet wird „leicht".
- **Mutations-Gegenprobe (Pflicht):** Betragsbildung entfernen ⇒ AC-1-Test muss rot werden.
  Sentinel-Filter entfernen ⇒ AC-3-Test muss rot werden.
- Bestandssuite `tests/tdd/test_cape_cin_pairing.py` muss **unverändert** grün bleiben (AC-2).
