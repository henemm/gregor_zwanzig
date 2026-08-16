---
entity_id: fix_1896_cin_baender_icon
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [gewitter, cin, icon, schwellen, eichung]
---

# CIN-Baender fuer ICON auf die naechstliegende belegte Quelle umstellen (#1896)

## Approval

- [ ] Approved

## Purpose

Die Konvektionshemmung CIN daempft die aus CAPE abgeleitete Gewitterstufe. Die dafuer benutzten Baender
stammen aus US-Vorhersagepraxis fuer eine CIN-Definition, die ICON nicht verwendet. Diese Spec stellt sie
auf die naechstliegende publizierte Quelle um, die fuer europaeische Modelle und fuer ICONs
Mischschichttiefe gilt — und loest damit die als „Known Limitation" festgehaltene Nicht-Eichung aus #1760
ab.

## Source

- **File:** `src/output/metric_format.py` (Python-Core / Domain-Backend)
- **Identifier:** `_gedaempft_durch_cin()` (Z. 325–376), aufgerufen aus `_signal_levels()` (Z. 416)

## Ausgangslage (gemessen 2026-08-16)

| CIN-Betrag | heutiges Verhalten | Herkunft der Zahl |
|---|---|---|
| < 25 | keine Daempfung | Penn State/COMET, SPC — **MLCIN ueber 100 hPa, pseudoadiabatisch** |
| 25 – < 50 | eine Stufe herunter | dieselbe US-Quelle |
| 50 – 100 | Deckel auf `LOW` | dieselbe US-Quelle |
| > 100 | `NONE` — CAPE traegt nichts bei | dieselbe US-Quelle |
| `None` | Notbremse: hoechstens `LOW` | Bestandsverhalten, unabhaengig von der Eichung |

ICON rechnet CIN ueber eine **50-hPa**-Mischschicht, **reversibel**, **ohne Entrainment**. Dieselbe Zahl
bedeutet damit etwas anderes als in der Quelle der Baender — dieselbe Fehlerklasse wie ADR-0048
(„CAPE != CAPE"), eine Ebene tiefer.

## Belegte Grundlage der Aenderung

**Primaerquelle:** Groenemeijer, P., Pucik, T., Tsonevsky, I., Bechtold, P. (2019): *An overview of CAPE and
CIN provided by NWP models for operational forecasting*, ECMWF Technical Memorandum No. 852, Figure 2:
*"CIN (hatched areas where CIN > 50 J/kg, contour at CIN = 100 J/kg)"*.
https://www.ecmwf.int/en/elibrary/81131

Warum diese Quelle besser passt als die heutige:

| Eigenschaft | ICON | TM852 / ESSL | heutige US-Quelle |
|---|---|---|---|
| Mischschichttiefe | 50 hPa | **50 hPa** ✅ | 100 hPa ❌ |
| Entrainment | keines | **keines** ✅ | keines ✅ |
| Adiabatik | reversibel | pseudoadiabatisch ❌ | pseudoadiabatisch ❌ |

TM852 trifft **zwei von drei** Definitionsbestandteilen, die heutige Quelle nur **einen**. TM852 ist zudem
europaeische operationelle Praxis (ESSL fuer ECMWF) statt US-Praxis.

**Richtung der verbleibenden Abweichung, belegt:** Reversibel gerechnete CIN ist betragsmaessig **groesser**
als pseudoadiabatische — qualitativ TM852 Abschnitt 4.3.3, quantitativ Murdzek, S.S., Markowski, P.M.,
Richardson, Y.P., Kumjian, M.R. (2021), *J. Atmos. Sci.* 78(10) (Differenzen > 100 J/kg im Realfall, bis
~5x in Idealsimulation, fallabhaengig bis „fast identisch"). **Ein fester Umrechnungsfaktor existiert
nicht.** Eine 1:1-Uebernahme von 50/100 wuerde deshalb tendenziell **zu frueh** daempfen — dem begegnet
diese Spec ueber die **Struktur** der Kaskade, nicht ueber eine erfundene Korrekturzahl (siehe unten).

**Ausgeschlossen und dokumentiert** (kein verwertbarer Beleg): Huntrieser et al. 1997 (ICONs eigene Quelle
fuer die 50 hPa — nennt keine Schwellen), Pucik et al. 2015 (rechnet kein CIN), Taszarek et al. 2021 ERA5
(behandelt CIN nicht), DWD-ICON-D2-Datenbankbeschreibung (nur GRIB-Feldname), DWD-Glossar (keine
Definition). Vollstaendige Suchspur: `docs/context/fix-1896-cin-eichung-icon.md`.

## Implementation Details

Neue Kaskade in `_gedaempft_durch_cin()`:

```
cin_jkg is None      -> hoechstens LOW        (Notbremse, UNVERAENDERT)
betrag < 50          -> keine Daempfung       (TM852: Hemmung beginnt bei 50)
betrag <= 100        -> eine Stufe herunter   (TM852: "hatched where CIN > 50")
betrag > 100         -> hoechstens LOW        (TM852: Kontur "starker Deckel")
```

Das Band `NONE` („CAPE traegt gar nichts mehr bei") **entfaellt ersatzlos**. Begruendung: Es ist die
staerkste denkbare Daempfung und braeuchte den staerksten Beleg; die ICON-nahe Quelle kennt oberhalb von
100 keinen weiteren Stuetzpunkt. Der bisherige vierte Eckpunkt 200 stammt aus der SPC-STP-Formel und ist im
Code ohnehin nie implementiert gewesen.

Ein Grenzwert gehoert weiterhin ins **staerker** daempfende Band (`<= 100` faellt in „eine Stufe").

**Warum 50 nur eine Stufe nimmt statt sofort auf `LOW` zu deckeln:** Weil ICON reversibel rechnet und fuer
dieselbe Wetterlage hoehere Zahlen liefert als die pseudoadiabatisch kalibrierten 50/100, ist die 1:1-Lesart
nachweislich zu streng. Die zurueckhaltendere Abbildung wirkt dieser belegten Verzerrung entgegen, ohne eine
Zahl zu erfinden. Sie ist zugleich die sichere Fehlerrichtung: weniger Daempfung heisst hoehere
Gewitterstufe, und ein Briefing, nach dem am Berg ueber einen Passuebergang entschieden wird, darf eher zu
viel als zu wenig warnen.

**Eine Leiter fuer beide ICON-Modelle** (ICON-D2 und ICON-EU) trotz ADR-0048: Beide teilen denselben
ICON-Code und damit dieselbe CIN-Definition. Der gemessene Anteilsunterschied ist ein Gebiets-, kein
Definitionsunterschied — anders als bei CAPE, wo verschiedene Modellfamilien verschiedene Parzelvarianten
rechnen. ADR-0048 verbietet das Tragen einer Schwelle ueber **Modellgrenzen**; hier liegt keine vor.

## Expected Behavior

- **Input:** `basis: ThunderLevel` (aus der CAPE-Leiter), `cin_jkg: Optional[float]` (Betrag oder
  vorzeichenbehaftet; die Funktion vergleicht weiterhin `abs()`)
- **Output:** `ThunderLevel`, nie hoeher als `basis`
- **Side effects:** keine. Wirkt sich ueber die fusionierte Gewitterstufe auf alle vier Kanaele (E-Mail,
  Telegram, SMS, Premium-SMS), den Ortsvergleich und die Gewitteralarme aus.

**Gemessene Wirkung** (Fenster 2026-06-27 – 2026-08-14, nur Stunden mit CAPE >= 1000 J/kg):

| Modell | n | Daempfung greift heute | Daempfung greift neu |
|---|---|---|---|
| ICON-D2 | 106 | 18,9 % | 3,8 % |
| ICON-EU | 315 | 21,3 % | 8,9 % |

## Acceptance Criteria

- **AC-1:** Given ein Datenpunkt mit CAPE oberhalb der HIGH-Stufe und einem ICON-CIN-Betrag unter 50 J/kg
  (z. B. der real gemessene ICON-D2-Wert 26,07 J/kg vom Karnischen Hoehenweg) / When die Gewitterstufe
  fusioniert wird / Then bleibt die aus CAPE abgeleitete Stufe **unveraendert** — sie wird nicht mehr wie
  bisher um eine Stufe gesenkt.
  - Test: Fusion ueber `thunder_level_from_signals()` mit dem echten Messwert; Vergleich der ausgegebenen
    Stufe gegen die CAPE-Leiter ohne Hemmung.

- **AC-2:** Given ein Datenpunkt mit CAPE-Stufe HIGH und einem CIN-Betrag zwischen 50 und einschliesslich
  100 J/kg / When die Gewitterstufe fusioniert wird / Then wird sie um **genau eine** Stufe gesenkt (HIGH
  wird MED) und nicht auf LOW gedeckelt.
  - Test: Fusion mit 50,0 / 75,0 / 100,0 J/kg fuer die Basen HIGH, MED und LOW; jeweils genau ein
    Leitersprung nach unten, LOW faellt auf NONE.

- **AC-3:** Given ein Datenpunkt mit CAPE-Stufe HIGH und einem CIN-Betrag ueber 100 J/kg (z. B. der real
  gemessene ICON-EU-Wert 104,47 J/kg aus den Abruzzen) / When die Gewitterstufe fusioniert wird / Then ist
  die Stufe hoechstens LOW.
  - Test: Fusion mit 104,47 und 767,8 J/kg; Ergebnis LOW statt wie bisher NONE.

- **AC-4:** Given einen beliebig grossen CIN-Betrag / When die Gewitterstufe fusioniert wird / Then wird das
  CAPE-Signal **nie** vollstaendig auf NONE gesetzt, solange die Basis mindestens LOW ist — das frühere
  Band „CAPE traegt gar nichts bei" existiert nicht mehr.
  - Test: Fusion mit 101, 200, 1000 und 10000 J/kg bei Basis HIGH/MED/LOW; Ergebnis nie unter LOW.

- **AC-5:** Given einen Datenpunkt, dessen CIN unbekannt ist (`None`, strukturell der Fall im
  Meteo-France-Gebiet, sowie nach dem Filtern des DWD-Fehlwerts -999,9) / When die Gewitterstufe fusioniert
  wird / Then greift unveraendert die Notbremse „hoechstens LOW".
  - Test: Fusion mit `cin_jkg=None` bei Basis HIGH; Ergebnis LOW. Zusaetzlich ueber den Provider-Pfad, dass
    der Fehlwert -999,9 weiterhin vor der Funktion zu `None` gefiltert wird.

- **AC-6:** Given eine beliebige Kombination aus Basisstufe und CIN-Wert / When gedaempft wird / Then ist
  das Ergebnis **niemals hoeher** als die Basis — die Hemmung daempft ausschliesslich und hebt nie an
  (Rasmussen & Blanchard 1998, Gesamtkonzept 3.7).
  - Test: parametrisierte Gegenprobe ueber alle vier Basisstufen und eine Wertereihe von 0 bis 10000 J/kg
    inklusive `None`; Ordinalvergleich Ergebnis <= Basis.

- **AC-7:** Given denselben CIN-Betrag / When er einmal aus ICON-D2 und einmal aus ICON-EU stammt / Then
  fuehrt er zur **gleichen** Daempfung — beide Modelle teilen eine Baenderleiter.
  - Test: Fusion mit identischem Wert ueber beide Provider-Pfade (`dwd`/`dwd_eu`); identische Ausgabestufe.

- **AC-8:** Given das positive Vorzeichen, mit dem ICON `cin_ml` liefert, und das negative der US-Modelle /
  When derselbe Betrag einmal positiv und einmal negativ hereinkommt / Then ist das Ergebnis identisch — die
  Betragslogik aus #1760 bleibt wirksam.
  - Test: Parameterpaare (+x / −x) fuer x in 10, 49, 50, 100, 150; jeweils gleiche Ausgabestufe.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/providers/dwd.py` / `dwd_eu.py` | upstream | liefern `cin_ml` (positiver Betrag), filtern -999,9 zu `None` |
| `src/providers/thunder_enrichment.py` | upstream | Feldmapping und Fusion, einziger produktiver Einstieg |
| `docs/features/gewitter-gesamtkonzept.md` 3.5/3.7 | doc | fachlicher Rahmen, muss auf die neue Belegquelle umgestellt werden |
| `docs/specs/modules/fix_1760_cin_vorzeichen.md` | doc | dessen Known Limitation wird durch diese Spec abgeloest |
| `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md` | adr | Rahmen fuer die „eine Leiter fuer beide ICON-Modelle"-Begruendung |

## Estimated Scope

- **LoC:** ~+150 / −80 in zaehlenden Dateien, realistisch bis ~300 (der Nachweis kostet mehr als der
  Mechanismus). Reisst das Limit 250, wird ein Override beim PO angefragt.
- **Files:** 5 (2 mit Code, 3 Dokumentation)
- **Effort:** medium

## Known Limitations

- 🔴 **Keine echte ICON-Eichung.** Diese Spec waehlt die naechstliegende publizierte Quelle; sie behauptet
  nicht, an ICON-Daten geeicht zu sein. Die verbleibende Abweichung ist die Adiabatik (reversibel statt
  pseudoadiabatisch), Richtung belegt, Betrag unbekannt.
- 🔴 **Eine eigene Klimatologie-Eichung ist derzeit unmoeglich.** Die Open-Meteo Historical Forecast API
  fuehrt `convective_inhibition` fuer ICON erst ab 2026-06-26/27; davor durchgaengig leer (Gegenprobe: CAPE
  im selben Abruf vollstaendig). Eine Saisonmessung nach dem #1592-Muster ist fruehestens nach der
  Konvektionssaison 2027 moeglich.
- 🔴 **Einzelbeleg.** Dass ICON CIN reversibel rechnet, stuetzt sich allein auf TM852 Table 1; ICON-Quellcode
  und COSMO-Physikdoku geben dazu oeffentlich nichts her.
- **Die Wirkungsmessung ist ein 49-Tage-Hochsommerfenster**, keine Saison. Sie beziffert Groessenordnungen.
- **Reichweite:** Auf dem GR20 (Meteo-France-Gebiet) wirkt die Eichung nicht — dort fehlt CIN strukturell
  und es greift allein die Notbremse. Auch am Karnischen Hoehenweg trugen nur 13 von 72 Datenpunkten einen
  echten CIN-Wert.
- **Nicht Gegenstand dieser Spec:** dass die Notbremse bei unbekanntem CIN haeufiger deckelt als saemtliche
  Baender zusammen. Als offene Frage im Kontextdokument vermerkt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0048 traegt den Rahmen
- **Rationale:** ADR-0048 verbietet, feste Schwellen ueber **Modellgrenzen** zu tragen. Genau das korrigiert
  diese Spec: Sie ersetzt eine aus fremder Modellwelt uebernommene Leiter durch die naechstliegende, fuer
  ICONs Mischschichttiefe belegte. Die Anwendung derselben Leiter auf ICON-D2 und ICON-EU ist keine
  Modellgrenze im Sinne des ADR (gleicher Modellcode, gleiche CIN-Definition) und ist oben begruendet.

## Changelog

- 2026-08-16: Initial spec created (#1896)
