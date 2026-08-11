# Gewitter — Gesamtkonzept

**Stand:** 2026-08-08 · **Status:** **Final** — alle Grundsatzentscheidungen (E1–E9) vom PO
getroffen und in Abschnitt 10 eingetragen. Änderungen an den Entscheidungsflächen erfordern
künftig ein ADR, keine stille Anpassung.

Dieses Dokument beschreibt Gewitter in Gregor Zwanzig **Ende zu Ende**: was der Nutzer bekommt,
woraus es entsteht, was gemessen belegt ist und was nicht, und in welcher Reihenfolge gebaut
wird. Es ersetzt die verstreuten Einzelbetrachtungen als führende Beschreibung — bislang
existierten zwölf Kontext-Fragmente und vier ADRs, aber **kein Gesamtbild**.

Alle Zahlenangaben mit „gemessen" sind Live-Messungen vom 2026-08-07/08 gegen die echten
Dienste, keine Literaturübernahmen.

---

## 1. Wozu Gewitter in diesem Produkt

Die Zielgruppe sind Weitwanderer mit eingeschränkter Konnektivität. Gewitter ist für sie die
**entscheidungsrelevanteste Wetterlage überhaupt** — anders als Regen oder Wind bestimmt es, ob
eine Etappe über einen Grat überhaupt begehbar ist, und es entsteht schnell.

Drei Leitsätze, die alles Weitere binden:

1. **Daten, keine Empfehlung** (ADR-0007). Wir sagen „hoch", nicht „geh nicht los". Eine
   Stufeneinteilung ist erlaubt, eine Handlungsanweisung nicht.
2. **Eine Aussage für alle Kanäle** (ADR-0025). Dieselbe Etappe ergibt in E-Mail, SMS, Telegram
   und Ortsvergleich dieselbe Stufe, aus denselben Rohdaten und mit derselben Fensterung auf die
   Wanderzeit. Abweichungen davon waren dreimal derselbe Bug (#874, #1275 zweifach).
3. **„Leer" heißt „keine Aussage", nie „keine Gefahr"** (#1377). Eine fehlende Quelle darf nie
   wie Entwarnung aussehen.

---

## 2. Was der Nutzer sieht — die Antwort

**Genau zwei gewitter-eigene Größen erreichen den Nutzer.** Alle Zutaten der Berechnung bleiben
unsichtbar.

| Größe | Frage | Werte | Status |
|---|---|---|---|
| **Gewitter-Stärke** (`thunder`) | Wie stark? | kein · leicht · mittel · hoch | existiert; wird heute **unvollständig** berechnet |
| **Hagel** (`hail_flag`) | Hagel dabei? | ja · unbekannt | existiert; eigenes Kennzeichen, **keine** Metrik (#1475) |

Davon zu unterscheiden sind **Böen** und **Starkregen**: Sie sind eigenständige Wettermetriken,
die auch ohne Gewitter existieren, und bleiben es (E9). Sie erscheinen also ebenfalls, aber
nicht als Gewitteraussage — die vollständige Liste steht in 2.1b.

### 2.1 Die Wahrscheinlichkeit entfällt — gemessen, nicht vermutet

Geplant war eine zweite Achse „Gewitter-Wahrscheinlichkeit 0–100 %". **Es gibt dafür keine
tragfähige Quelle.** Alle vier Wege wurden live geprüft:

| Weg | Messergebnis |
|---|---|
| Anteil der Ensemble-Läufe mit Gewittercode | **0,04 %** Treffer in 53.760 Werten; in allen 9 Stunden mit Gewitter im Hauptlauf zeigten **0 von 40** Läufen Gewitter |
| Open-Meteo `thunderstorm_probability` | Name akzeptiert, bei **allen 11** Modellen leere Reihen — Scheinparameter |
| DWD MOSMIX `wwT` | echte Prozentwerte, aber vom DWD **selbst abgekündigt** (Newsletter 25.06.2025: „empfehlen … auf andere Produkte umzusteigen"); im Alpenraum nur 6 von 14 Stationen befüllt; nächste Station zum GR20-Kamm auf **10 m Höhe, 31 km** entfernt |
| CAPE je Ensemble-Lauf | verfügbar — aber eine Prozentskala daraus wäre Eigenkalibrierung (verboten, #1456) |

⇒ **Das Produkt zeigt vorerst EINE Gewitter-Metrik, nicht zwei.** Die Unsicherheit trägt
niemand — das ist eine bewusste Lücke, keine vergessene. Sollte je eine flächige, publizierte
Quelle auftauchen, ist das Feld `thunder_probability_pct` bereits vorbereitet.

### 2.1b Alle gewitterbezogenen Größen im Überblick

Damit nichts durchs Raster fällt — das Produkt kennt **elf** Größen mit Gewitterbezug:

| Größe | Beantwortet | Status | Verfügbar |
|---|---|---|---|
| **Gewitter-Stärke** `thunder` | wie stark | ✅ **sichtbar** | überall |
| **Hagel** `hail_flag` | Hagel dabei? | ✅ **sichtbar**, eigenes Kennzeichen | nur DWD-Gebiet |
| **Böen** `gust` | Sturm im Gewitter | ✅ **sichtbar**, eigene Metrik — **bewusst nicht verrechnet** (E9) | überall |
| **Starkregen** `precipitation` | Sturzbäche | ✅ **sichtbar**, eigene Metrik — **bewusst nicht verrechnet** (E9) | überall |
| CAPE | Energie | Zutat ⇒ unsichtbar (E2) | überall |
| Konvektionshemmung `cin_ml` | hält der Deckel? | Zutat, ersetzt die CAPE-Notbremse | DWD-Gebiet |
| Blitzdichte | Blitzaktivität (FR) | Zutat | nur Frankreich inkl. Korsika |
| Blitzpotenzial `lpi`/`lpi_max`/`lpi_con_max` | Blitzaktivität (DWD) | Zutat | DWD-Gebiete |
| **Superzellen-Index** `sdi_2` | gefährlichste Form | **Zutat** (E8) — hebt die Stufe, kein eigenes Kennzeichen | nur ICON-D2 |
| Updraft-Helizität `uh_max*` | Rotation | Zutat, vorerst ohne Schwelle | nur ICON-D2 |
| Gewitter-Wahrscheinlichkeit | wie sicher | **entfällt** — keine Quelle (2.1) | — |

Dazu kommt `thunder_squall` als **amtlicher Warntyp** aus den Wetterdienst-Meldungen
(Gewitterböe) — eine Aussage, die es bereits gibt, aber aus der Behördenmeldung stammt, nicht
aus unserer Berechnung (Abschnitt 6).

**E8 — Superzellen bleiben Zutat, kein eigenes Kennzeichen.** Fachlich wäre ein Kennzeichen
konsistent zu Hagel (beide beantworten „was für ein Gewitter", nicht „wie stark"). Ausschlag
gab die Verfügbarkeit: Den Index gibt es **nur im ICON-D2-Gebiet**. In **ganz Frankreich**
— und damit auf dem GR20 — erschiene er strukturell nie, und „kein Hinweis" läse sich dort als
„keine Superzelle". Als Zutat hebt er die Stufe, ohne ein Schweigen zu erzeugen, das nach
Entwarnung aussieht.

**E9 — Böen und Starkregen bleiben getrennte Metriken.** Der DWD stuft Gewitter zwar genau nach
diesen Größen ein, aber er warnt **wirkungsbasiert**, wir beschreiben **Wetter**. Eine
kombinierte Gefahrenstufe wäre bereits Bewertung und verstieße gegen ADR-0007 („Daten statt
Empfehlungen"). Der Nutzer sieht beide Zahlen und kombiniert selbst — das ist die Zielgruppe.

⚠️ Zu beachten: **Unsere Böen-Schwellen sind bewusst schärfer als die amtlichen.** Wir werten ab
60 km/h „rot", der DWD beginnt seine Warnstufe 1 bei 50 und Stufe 2 erst bei 65 km/h. Richtig
so — die Zielgruppe steht auf einem Grat, nicht in der Fußgängerzone. Es heißt aber auch: Eine
Eichung „wie der DWD" wäre für dieses Produkt zu lasch.

### 2.2 Warum die Zutaten unsichtbar bleiben

CAPE, Konvektionshemmung, Blitzdichte, Blitzpotenzial, Superzellen-Index sind **Zutaten** der
Stufe. Sie sind der Weg zur Antwort, nicht die Antwort. Zwei Gründe, warum sie keine eigenen
Spalten bekommen:

- **Gebietsabhängige Verfügbarkeit** — dieselbe Spalte trüge je nach Ort eine andere Größe oder
  wäre leer (s. Abschnitt 4).
- **Unvereinbare Skalen** — Blitzdichte liegt bei ~0,2, Blitzpotenzial bei ~88. Nebeneinander
  in einer Stundentabelle sind sie nicht lesbar, in einer SMS (≤ 160 Zeichen) gar nicht.

Bis 2026-08-10 war genau **eine** Zutat sichtbar: CAPE — nicht weil das entschieden wurde,
sondern weil sie historisch zuerst im Katalog stand. ⇒ **CAPE ist seit #1585 (2026-08-10,
adversary-verifiziert) unsichtbar** (`selectable=False`), aus demselben Grund wie alle anderen
Zutaten. Sie bleibt intern Teil der Berechnung. Präzedenz: `confidence` (ADR-0005).
Bestandsdaten laden still weiter, keine Migration.

---

## 3. Wie die Stärke entsteht

### 3.1 Das Verfahren heute

`thunder_level_from_signals()` (`metric_format.py:326`) übersetzt **jedes Signal einzeln** in
eine Stufe und nimmt dann **das schärfste**. Sind alle leer, ist das Ergebnis leer.

| # | Signal | Schwellen (leicht / mittel / hoch) | Beleglage |
|---|---|---|---|
| 1 | WMO-Wettercode | 95 / 96 / 99 | vom Anbieter geliefert |
| 2 | Blitzdichte (Blitze/km²/3 h) | 0,003 / 0,015 / **0,075** | ECMWF-Leitfaden; **0,075 nicht publiziert** |
| 3 | Blitzpotenzial LPI (J/kg) | 5 / **20** / 50 | DWD/Copernicus; **20 interpoliert** ⇒ ersetzbar durch 1/30/50, s. 3.5b |
| 4 | CAPE (J/kg) | ≥ 1000 → nur „leicht", **deckelt** | Katalog-Risikoschwelle |

### 3.2 Die Annahmen darin — offen ausgesprochen

- **„Das schärfste Signal gewinnt."** Kein Mitteln, kein Gewichten. Sicherheitsgerichtet, aber
  ein einzelner Ausreißer hebt die Stufe.
- **Signale werden nicht kombiniert.** Hohe Energie *und* hohes Blitzpotenzial ergibt nicht mehr
  als Blitzpotenzial allein. Vereinfachung, keine Physik.
- **Zwei von acht Schwellen sind interpoliert**, nicht publiziert (0,075 und 20). Das ist
  faktisch Eigenkalibrierung im Bestand — dieselbe Sache, die als Verbot die Schließung von
  #1456 begründet hat. Beide stehen ehrlich als Kommentar im Code.
  ⇒ Für die LPI-Zwischenstufe gibt es inzwischen Ersatz: **30 J/kg ist publiziert**
  (s. 3.5b), die interpolierte 20 kann entfallen.
- **CAPE ist gedeckelt, weil die Gegengröße fehlt.** Viel Energie unter einem Deckel heißt: es
  passiert nichts. Da die Konvektionshemmung nie abgerufen wurde, wird CAPE vorsorglich nie
  höher als „leicht" gewertet. Das ist eine **Notbremse, kein Modell**.

### 3.3 Was fehlt — und was davon belegbar nachrüstbar ist

| Signal | Nutzen | Belegte Schwelle? | Verfügbar? |
|---|---|---|---|
| **Konvektionshemmung** `cin_ml` | macht CAPE erst verwertbar, ersetzt die Deckelung | ✅ **50 J/kg belegt** (s. 3.5) | ✅ ICON-D2 + ICON-EU |
| **Superzellen-Index** `sdi_2` | einziges Signal für die gefährlichste Gewitterform | ✅ **DWD: 0,0003 / 0,003 1/s** | ✅ nur ICON-D2 |
| **Updraft-Helizität** `uh_max*` | Rotationsstärke | ❌ US-Werte 2019 vom Betreiber selbst verworfen | ✅ nur ICON-D2, drei Schichten |
| **Blitzpotenzial-Maximum** `lpi_max` | Spitzenwert statt Momentanwert | wie LPI | ✅ ICON-D2 |
| **Radar-Beobachtung** | „passiert gerade" statt „wird vorhergesagt" | ✅ Regel in #1419 §4 | ✅ angebunden, fließt aber **nicht** ein (Abschnitt 5) |

**Nicht nachrüstbar** (recherchiert 2026-08-07, nicht erneut zu prüfen): Reflektivität
`dbz_cmax` (Faustregeln gelten für gemessenes Radar, unser Wert ist Modellsimulation),
Zellhöhe `echotop` (DWD liefert 18 dBZ = Wolkenoberkante, kein Intensitätsmaß).

### 3.4 Realitätsdämpfer zum Superzellen-Index

Gemessen über das gesamte ICON-D2-Gitter lag das Feldmaximum bei **0,00074** — über der
minimalen Schwelle (0,0003), aber **weit unter der signifikanten** (0,003). In dieser Lage hätte
`sdi_2` also höchstens die mittlere Stufe ausgelöst. Ob die obere Schwelle in echten
Superzellenlagen erreicht wird, ist offen. Zudem nennt der DWD den Index selbst ein
**„experimentelles Produkt"** auf Basis „einiger weniger Fallstudien", kalibriert für COSMO-DE
(2,8 km) — die Übertragung auf ICON-D2 (2,2 km, feiner) ist plausibel, aber nicht validiert.

⇒ Deshalb: **erst Felder befüllen und mitlaufen lassen, dann einstufen.** Nicht umgekehrt.

### 3.4b ✅ CAPE ≠ CAPE — eine Schwelle auf unvergleichbare Werte (gemessen 2026-08-08, → #1592, BEHOBEN für die Fusion)

**CAPE ist ein modellabhängiges Konstrukt, kein Messwert.** Die Modelle unterscheiden sich in
der Parcel-Wahl: ICON liefert **Mixed-Layer**-CAPE (`CAPE_ML`), Météo-France **Most-Unstable**
(`CAPE_INS`), GFS **Surface-Based**. Open-Meteo reicht die native Variable je Modell durch —
**ohne zu harmonisieren und ohne es zu dokumentieren**.

Unser Code holt `cape_jkg` über Open-Meteo (`openmeteo.py:870`) und prüft es gegen **eine**
Schwelle von 1000 J/kg (`metric_format.py::_cape_low_min_jkg`), unabhängig vom Modell. Gemessen
am selben Ort, zur selben Stunde:

| Südfrankreich | CAPE-Maximum | P90 | Anteil Stunden ≥ 1000 J/kg |
|---|---|---|---|
| **AROME** (unser Modell für Frankreich, Priorität 1) | 840 | 460 | **0,0 %** |
| ICON-D2 | 1730 | 1340 | 17,3 % |
| ICON-EU | 2560 | 1850 | 31,9 % |
| ECMWF | 3670 | 3520 | **65,3 %** |
| GFS | 2530 | 2130 | 40,3 % |

Dieselbe Schwelle löst je nach Modell **nie** oder in **zwei Dritteln** aller Stunden aus. Auch
auf Korsika erreicht AROME an keiner Stunde 1000 J/kg, während ICON-EU dort 29 % meldet.

⇒ **Das CAPE-Signal ist in der Gewitterfusion für Frankreich faktisch wirkungslos.** Eines der
vier Signale trägt dort nichts bei — nicht weil keine Energie da wäre, sondern weil eine
Schwelle aus einer anderen Modellwelt angelegt wird. Das ist unabhängig von allem anderen in
diesem Konzept zu beheben:

- entweder **Perzentil- statt Absolutschwelle** („CAPE > 95. Perzentil **dieses** Modells"),
- oder **je Modell eine eigene Schwelle**, geeicht wie in 4.5 beschrieben,
- oder CAPE nur dort werten, wo die Schwelle belegt gilt.

Dieselbe Falle gilt für jede künftige Modellgröße: **Feste Schwellen nie über Modellgrenzen
tragen.**

> **✅ Stand 2026-08-08 — für die Fusion behoben und live** (#1592 Scheibe B0+C0+C1, ADR-0048).
> Gewählt wurde der zweite Weg, aber als **Perzentil-Eichung** statt geratener Einzelwerte:
> Schwelle je Modell × Gebiet = 95. Perzentil der CAPE-Klimatologie dieses Modells in diesem
> Gebiet über eine Konvektionssaison (April–September), mindestens 300 J/kg. Die Werte stehen
> als statische Tabelle in `src/app/model_registry.py`; erzeugt von
> `scripts/eichung_cape_schwelle.py` gegen die Historical Forecast API — einmalig, keine
> Laufzeit-Abhängigkeit. Auf dem GR20 gilt jetzt **300 statt 1000**, ein realer AROME-Wert von
> 840 J/kg ergibt dort „leicht" statt „kein Gewitter".
>
> **Beim Eichen fiel eine zweite Ebene desselben Fehlers auf:** Unser Code ruft Open-Meteo über
> **Endpunkte** ab, nicht über benannte Modellvarianten. `/v1/meteofrance` liefert
> `meteofrance_seamless`, nicht `arome_france_hd` — ein erster Eichlauf gegen die falsche
> Variante hätte für Rest-Europa **gar keinen Eintrag** erzeugt und CAPE dort dauerhaft stumm
> gelassen. Die Zuordnung Endpunkt → Variante ist deshalb empirisch ermittelt (Wert-für-Wert-
> Vergleich) und im Eichskript dokumentiert. **Wer neu eicht, prüft sie zuerst nach.**
>
> ✅ **Auch RiskEngine und Δ-Alarme sind inzwischen umgestellt** (Scheiben C2/C3 unter #1592,
> Vollzugsvermerk in ADR-0048). Der RiskEngine-Pfad zählte CAPE bis C2 ein zweites Mal gegen
> die feste 1000/2000 — obendrauf zur bereits gedeckelten Fusion; diese zweite Regel ist
> gestrichen. Die Δ-Alarm-Schwellen rechneten bis C3 die nominale Empfindlichkeitsstufe
> (1200/600/200) unverändert gegen jedes Modell; sie übersetzen die Stufe seither in dieselbe
> Modellwelt wie die Fusion. Ortsvergleich und Schnappschuss-Reload führen weiterhin strukturell
> keine Modell-Herkunft, dort trägt CAPE dauerhaft nicht bei — das bleibt unverändert.
>
> ✅ **#1601 (2026-08-09): Modellwechsel zwischen zwei Läufen löst keinen CAPE-Änderungsalarm
> mehr aus.** Wechselt das liefernde Modell zwischen dem gespeicherten Anker und dem frischen
> Wert (`cape_model_id` alt ≠ neu, `None` zählt als Abweichung), unterbleibt der Alarm — die
> Modellwelt-Umrechnung aus C3 gilt nur innerhalb derselben Modellwelt. Betrifft beide
> Alarmwege (Trip, Ortsvergleich) über die geteilte `DeviationAlertEngine`.

### 3.5 Die CAPE-Deckelung ist belegt ersetzbar (Recherche 2026-08-08)

Die heutige Notbremse („CAPE eskaliert nie über *leicht*") existiert nur, weil uns die
Gegengröße fehlt. Für die CIN-Grenze gibt es einen über mehrere unabhängige Quellen
konsistenten Korridor, darunter zwei Primärquellen:

| Quelle | Aussage | Kategorie |
|---|---|---|
| **Penn State / COMET-Lehrmaterial** | „rank CIN values between 0 and minus 25 … as **weak** inhibition" · „between minus 25 and minus 50 … **moderate**" · „minus 50 … minus 100 …, think **large** inhibition" | belegt |
| **SPC (NOAA)**, STP-Formel | CIN-Term `((mlCIN + 200) / 150)`, gedeckelt: bei CIN schwächer als **−50** kein Malus, bei **−200** fällt der Beitrag auf **null** | belegt |
| **SPC**, Effective Inflow Layer | Schichten mit CIN unter **−250 J/kg** fallen ganz aus der Betrachtung | belegt |
| **ECMWF** Forecast User Guide | ab **50 J/kg** wird CAPE auf Karten grau maskiert — eine **Darstellungs**schwelle, keine Kausalregel | belegt |
| **DWD** | „Je größer die CIN-Werte sind, desto unwahrscheinlicher ist die Auslöse von Gewittern" — **ohne Zahl** | qualitativ |

⇒ Belegte Eckpunkte sind **−25 / −50 / −100 / −200 J/kg**. Vorschlag für die Paarung:
schwächer als −25 → CAPE zählt voll · −25 bis −50 → leicht gedämpft · −50 bis −100 → stark
gedämpft, nur mit kräftigem Auslöser · unter −100 → kein Beitrag.

🔴 **Korrektur einer verbreiteten Angabe:** Die kursierenden Werte „CIN > −10 = frei
auslösbar" und „genau −50 als Schaltschwelle" sind **so nicht belegt** — sie klingen präzise,
haben aber keine Quelle. Die tatsächlich belegten Grenzen sind die vier oben.

🔴 **Gegenbefund, der mitgeschrieben gehört:** Rasmussen & Blanchard (1998), die
meistzitierte Klimatologie dazu, findet **CIN als eigenständigen Schwere-Prädiktor nur schwach**
— der stärkste Diskriminator war die LCL-Höhe. Für unseren Zweck trägt es trotzdem: Wir
brauchen CIN als **Auslöse-Filter** („wird die Energie überhaupt abgerufen"), nicht als
Schweremaß. Diese Unterscheidung muss in der Spec stehen, sonst wird daraus stillschweigend
ein Schwere-Signal.

### 3.5b Zwei weitere Leitern lassen sich belegen statt raten

**LPI — die interpolierte Zwischenstufe wird überflüssig.** Bína et al. (Atmospheric Research
2022 und ASR/Copernicus 2022, COSMO-D2, 2,2 km — dieselbe Modellfamilie wie ICON-D2):

> „for 2-moment cloud microphysics a skilful forecast was reached at scales around 90 km for
> LPI thresholds **30, 40 and 50 J/kg**" · als Nachweisschwelle: **„LPI > 1 J/kg"**

⇒ Statt der heutigen Leiter **5 / 20 / 50** (mit interpolierter 20) ist **1 / 30 / 50**
durchgehend belegt. Zu prüfen: ob die untere Grenze auf 1 sinken soll (mehr Meldungen) oder
die operative DWD-Zahl 5 bleibt.

**CAPE — es gibt eine echte Leiter, wir nutzen nur eine Stufe.** Mehrfach unabhängig bei NWS
und SPC: „Weak instability: less than 1000 J/kg · Moderate: 1000 to 2500 · Strong: 2500–4000 ·
Extreme: greater than 4000". Heute wertet das Produkt CAPE nur binär (≥ 1000 → „leicht",
gedeckelt). Zusammen mit der Hemmung aus 3.5 könnte CAPE eine vollwertige, belegte Leiter
tragen — **1000 / 2500 / 4000 J/kg**.

### 3.6 Wo es weiterhin nichts gibt: Blitzdichte

Für die Blitz**dichte pro km²** — die Korsika-Größe — existiert **keine publizierte
Stufenskala** (mehrfach gesucht, deutsch und englisch). Gefunden wurden nur:
zellbezogene Blitzraten (Lightning-Jump-Verfahren: 5/10/15 Blitze/min, aber **relativ** zum
Zellverlauf, keine feste Stufe) und die LAL-Skala der US-Feuerwehrbehörden (1–2 / 2–3 / > 3
Erdblitze/min) — Beobachtungsgrößen aus dem Feuerwetter-Kontext, nicht auf Modell-Blitzdichte
je km² übertragbar.

Auch die **Wetterdienste selbst quantifizieren Blitz nicht**: Der DWD führt Gewitter in seinen
Warnkriterien nur qualitativ als „elektrische Entladung"; die Stufen 2–4 hängen an Böen
(105–140 km/h), Starkregen (25–40 l/m²/h) und Hagelkorngröße — **keine Blitzrate**. Météo-France
veröffentlicht seine Vigilance-Kriterien gar nicht.

⇒ Die heutigen Blitzdichte-Schwellen (0,003 / 0,015 / 0,075) bleiben teilweise interpoliert.
Das ist keine Nachlässigkeit, sondern der Stand der Veröffentlichungen — es muss aber als
solches gekennzeichnet bleiben.

---

### 3.7 🎯 Das Zielverfahren — wie alle Zutaten zusammenwirken

Dies ist die vollständige Rechenvorschrift, wenn alles aus diesem Konzept umgesetzt ist. Sie
ersetzt die heutige Fassung aus 3.1.

### Schritt 1 — Jede Zutat wird für sich in eine Stufe übersetzt

| Zutat | kein | leicht | mittel | hoch | Beleg |
|---|---|---|---|---|---|
| **WMO-Wettercode** | < 95 | 95 | 96 | 99 | Anbieter |
| **Blitzdichte** (Frankreich inkl. Korsika, Blitze/km²/3 h) | < 0,003 | ≥ 0,003 | ≥ 0,015 | ≥ 0,075 | ECMWF; **oberste Grenze interpoliert** |
| **Blitzpotenzial ICON-D2** (J/kg) | < 1 | ≥ 1 | ≥ 30 | ≥ 50 | Bína et al., COSMO-D2 — **alle drei belegt** |
| **Blitzpotenzial ICON-EU** (J/kg) | eigene Leiter — **zu eichen** (Rang 7), bis dahin nicht gleichwertig | | | | Faktor 235 gemessen |
| **CAPE, gepaart mit Hemmung** | s. Schritt 2 | | | | NWS/SPC + Penn State |
| **Superzellen-Index** (Betrag, 1/s) | < 0,0003 | — | ≥ 0,0003 | ≥ 0,003 | DWD publiziert |
| **Radar-Beobachtung** | nicht konvektiv | — | konvektiv | — | #1419 §4 |
| **Updraft-Helizität** | trägt vorerst **nichts** bei — keine übertragbare Schwelle | | | | — |

Der Superzellen-Index kennt bewusst **kein „leicht"**: Der DWD nennt ihn ein experimentelles
Produkt mit zwei Schwellen; eine dritte zu erfinden wäre Eigenkalibrierung.

### Schritt 2 — CAPE zählt nur so weit, wie die Hemmung es zulässt

Heute wird CAPE pauschal auf „leicht" gedeckelt, weil die Gegengröße fehlt. Künftig entscheidet
die Konvektionshemmung, **wie viel** von der Energie überhaupt zählt:

🔴 **Korrektur 2026-08-11 (Umsetzung #1679 CIN-Teil):** Die Grenzen unten waren beim Schreiben
absichtlich unscharf formuliert ("0 bis −25" ohne Klarheit, welche Seite den Randwert bekommt).
Implementierung und die freigegebenen Acceptance Criteria (`feat_1679_cin_paarung_cape_leiter.md`
AC-4/AC-5/AC-6, adversary-VERIFIED per Mutationsprobe) legen den Randwert jeweils ins **stärker
dämpfende** Band — Tabelle unten entsprechend präzisiert, an der fachlichen Bedeutung ändert sich
nichts.

| Hemmung (CIN) | Bedeutung | CAPE darf höchstens |
|---|---|---|
| über −25 J/kg (d. h. `cin > -25`) | schwacher Deckel | **voll wirken** — Leiter 1000 / 2500 / 4000 J/kg |
| −50 bis −25 J/kg (d. h. `-50 < cin <= -25`) | moderat | **eine Stufe weniger** |
| −100 bis −50 J/kg (d. h. `-100 <= cin <= -50`) | großer Deckel | **höchstens „leicht"** (heutiges Verhalten) |
| unter −100 J/kg (d. h. `cin < -100`) | Deckel hält | **kein Beitrag** |
| Hemmung unbekannt | keine Aussage | **höchstens „leicht"** — die heutige Notbremse bleibt als sicherer Rückfall |

⚠️ **Ausdrücklich:** Die Hemmung ist ein **Auslöse-Filter**, kein Schweremaß. Rasmussen &
Blanchard (1998) zeigen, dass CIN die Schwere nur schwach vorhersagt — sie darf die Stufe
deshalb **dämpfen, aber nie anheben**.

### Schritt 3 — Fusion: das schärfste Signal gewinnt

Unverändert. Alle vorhandenen Einzelstufen werden verglichen, die höchste zählt. Sind **alle**
Zutaten leer, ist das Ergebnis leer — „keine Aussage", nicht „keine Gefahr".

Bewusst **keine** Mittelung und **keine** Gewichtung: Ein Signal, das Gefahr meldet, wiegt
schwerer als drei, die schweigen. Der Preis ist bekannt — ein einzelner Ausreißer hebt die
Stufe.

### Schritt 4 — Beobachtung darf anheben, nie senken

Meldet das Radar für die Etappenzeit Konvektion, wird die Stufe auf mindestens „mittel"
gehoben (E3). Umgekehrt gilt es nicht: Ein ruhiges Radarbild senkt eine hohe Vorhersagestufe
**nicht** — das Gewitter kann noch entstehen.

### Schritt 5 — Die Stufe trägt ihre Herkunft mit

Jede Stufe merkt sich, **welche Zutat sie ausgelöst hat** (E1). Im Ortsvergleich wird damit
erkennbar, dass Korsika und die Alpen auf verschiedenen Größen fußen — statt zwei Zahlen
nebeneinanderzustellen, die vergleichbar aussehen und es nicht sind.

### Was das je Gebiet konkret bedeutet

Die Gebietsgrenzen sind **ganze Länderregionen**, nicht einzelne Touren: „FR" umfasst
41,3–51,1° N / −5,2–9,7° O, also **ganz Frankreich einschließlich Korsika**
(`thunder_routing.py:63-67`).

| | **Frankreich inkl. Korsika** | **DE / Alpen / AT** | **Übriges Europa** |
|---|---|---|---|
| **Auflösung der Grundvorhersage** | **AROME 1,3 km — die feinste im System** | ICON-D2 2,0–2,2 km | ICON-EU / global, ab 6,5 km |
| Wettercode (überall wirksam) | ✅ aus dem feinsten Modell | ✅ | ✅ |
| Blitzsignal | Blitz**dichte** | Blitz**potenzial** (2,2 km) | Blitzpotenzial (6,5 km, eigene Leiter) |
| CAPE + Hemmung | CAPE ja, **Hemmung nein** ⇒ bleibt gedeckelt | ✅ beides | ✅ beides |
| Superzellen | ❌ nicht verfügbar | ✅ | ❌ |
| Hagel-Kennzeichen | ❌ (→ #1507) | ✅ | ❌ |
| Radar | ⚠️ nur Modell (ARPAE ICON-2I, seit #1648 kein echtes Radar mehr für IT/Korsika) | ✅ | ✅ (global) |

⚠️ **Signalanzahl ist nicht Vorhersagegüte — die beiden bitte nicht verwechseln.** Frankreich
und Korsika haben die **wenigsten Zusatzsignale**, aber die **feinste Grundvorhersage**:
AROME läuft mit 1,3 km und steht im Modellkatalog auf Priorität 1
(`openmeteo.py:118-126`), feiner als ICON-D2 (2,0 km) und mehr als viermal feiner als ICON-EU.
Der WMO-Wettercode — das einzige Signal, das überall wirkt und in der Fusion unmittelbar eine
Stufe setzt — kommt dort also aus dem besten verfügbaren Modell, und bei 1,3 km wird Konvektion
feiner aufgelöst als anderswo. Praxiserfahrung des PO aus dem Vorgängerprojekt bestätigt hohe
Trefferqualität für Korsika.

**Was für Frankreich/Korsika wirklich fehlt**, ist enger gefasst: die **Zusatz**signale
(Superzellen-Index, Hagel-Kennzeichen, Konvektionshemmung) und eine belegte oberste Schwelle
für die Blitzdichte. Wer das schließen will, muss bei Météo-France ansetzen (#1507 für Hagel,
Energiegrößen offen) — dort kostet jede Größe allerdings einen Abruf **je Stunde**, anders als
beim kostenlosen DWD. Die Kosten-Nutzen-Abwägung ist deshalb eine andere als beim DWD, und sie
ist offen.

---

## 4. Das ungelöste Kernproblem: die Stufe bedeutet je nach Ort etwas anderes

Dies ist der wichtigste Punkt des Konzepts und bislang nirgends adressiert.

Gewittersignale kommen je Gebiet aus verschiedenen Quellen mit **verschiedenen Größen**:

| Gebiet | Quelle | Signale, die ankommen |
|---|---|---|
| **Frankreich inkl. Korsika** (Region FR: 41,3–51,1 N / −5,2–9,7 O) | Météo-France AROME, **1,3 km** | Wettercode + **Blitzdichte** |
| Deutschland/Alpen/Österreich | DWD ICON-D2 | Wettercode + **Blitzpotenzial** + Hagel |
| Übriges Europa | DWD ICON-EU | Wettercode + **Blitzpotenzial**, kein Hagel |

Daraus folgt: **„mittel" auf Korsika entsteht aus einer anderen Größe als „mittel" in den
Alpen.** Auf Korsika trägt es die Blitzdichte, in den Alpen das Blitzpotenzial — zwei Größen auf
unvereinbaren Skalen, jede mit eigener, teils interpolierter Schwellenleiter.

Konsequenzen, die eine Entscheidung brauchen:

- **Im Ortsvergleich stehen diese Stufen nebeneinander in einer Tabelle** und suggerieren
  Vergleichbarkeit, die sie nicht haben. Ein Vergleich Korsika ↔ Alpen vergleicht faktisch zwei
  verschiedene Messverfahren.
- **`sdi_2` verschärft das**: Es gibt ihn nur im ICON-D2-Gebiet. Wird er eingehängt, kann eine
  Etappe in den Alpen „hoch" erreichen, eine identisch gefährliche auf Korsika aber nicht —
  weil dort das Signal schlicht fehlt.

### 4.1 Verschärfend: dasselbe Feld trägt zwei verschiedene Statistiken

Innerhalb des DWD-Zweigs gibt es einen zweiten, bisher unbenannten Bruch. ICON-D2 liefert `lpi`,
ICON-EU liefert `lpi_con_max`. Beide werden über denselben Signalschlüssel auf **dasselbe Feld**
`lightning_potential_lpi_jkg` gelegt (`dwd_eu.py:96`) und mit **derselben Schwellenleiter**
(5 / 20 / 50 J/kg) bewertet — mit der Begründung, es sei „fachlich dieselbe Größe".

Der Code selbst dokumentiert aber den Unterschied: `lpi_con_max` ist laut GRIB-Kopf ein
**Maximum über die letzten 60 Minuten** (`dwd_eu.py:43-45`), `lpi` ein **Momentanwert**.

Ein Stundenmaximum ist per Definition **immer ≥** dem Momentanwert derselben Größe. Dieselbe
Schwellenleiter auf beide anzuwenden heißt: **Rest-Europa wird bei gleicher Wetterlage
systematisch höher eingestuft als Deutschland und die Alpen** — nicht weil dort mehr Gefahr
herrscht, sondern weil anders gemessen wird.

Gegenläufig wirkt die Auflösung: ICON-EU (6,5 km) mittelt stärker als ICON-D2 (2,2 km) und
dämpft Spitzenwerte. Welcher Effekt überwiegt, ist **nicht bekannt**.

### 4.2 Der Bruch ist vermessen — und größer als erwartet

Messung 2026-08-08, ICON-D2-Gebiet, Zeitschritte +15/16/17 h, 3,77 Mio. bzw. 459 Tsd.
Gitterwerte. Anteil der Punkte, die die **gemeinsame** Schwellenleiter überschreiten:

| Schwelle | ICON-D2 `lpi` | ICON-EU `lpi_con_max` | Faktor |
|---|---|---|---|
| ≥ 5 („leicht") | 0,007 % | 1,72 % | **235×** |
| ≥ 20 („mittel") | 0,003 % | 0,47 % | **137×** |
| ≥ 50 („hoch") | 0,001 % | 0,053 % | **57×** |

An 5631 Punkten der Vereinigungsmenge (mindestens eine Quelle mit Signal) trug ICON-D2 nur in
**5 %** der Fälle einen Wert > 0, ICON-EU in **97 %**; ICON-EU war an **96 %** der Punkte größer.

⇒ **Ein Ort im ICON-EU-Gebiet bekommt bei gleicher Wetterlage rund zweihundertmal häufiger die
Stufe „leicht" als einer im ICON-D2-Gebiet.** Das ist keine Feinheit, das ist ein struktureller
Fehler mit direkter Alarmwirkung.

### 4.3 Zwei Ursachen — eine davon ist behebbar

**Ursache 1: verschiedene Statistik.** `lpi` ist ein Momentanwert, `lpi_con_max` ein
Stundenmaximum. Vergleicht man stattdessen `lpi_max` (ICON-D2 bietet es an, wird mit #1531
ohnehin geholt) mit `lpi_con_max`, also **Maximum gegen Maximum**, schrumpft der Bruch um
Faktor 5:

| Schwelle | Momentan ↔ Maximum | Maximum ↔ Maximum |
|---|---|---|
| ≥ 5 | 235× | **51×** |
| ≥ 20 | 137× | **27×** |
| ≥ 50 | 57× | **8,7×** |

**Ursache 2: verschiedene Physik — nicht behebbar, nur berücksichtigbar.** Der Rest steckt im
Namen: `lpi_**con**_max`. ICON-EU (6,5 km) **parametrisiert** Konvektion, ICON-D2 (2,2 km)
**löst sie explizit auf**. Das sind zwei grundverschiedene Darstellungen desselben Vorgangs. Die
Annahme im Code, es sei „fachlich dieselbe Größe" (`dwd_eu.py:90-95`), trifft damit nicht zu.

### 4.4 Warum ein reiner Häufigkeits-Abgleich hier nicht reicht

Das naheliegende Verfahren — nicht die Zahl übertragen, sondern die **Seltenheit** (so hat der
US-Dienst SPC 2019 feste Schwellen durch Perzentile ersetzt) — wurde gerechnet und liefert für
ICON-EU eine „leicht"-Schwelle von **155 J/kg**, während der DWD 5 J/kg als Grenze für „blitzt
es überhaupt" nennt. Die drei geeichten Werte lägen zudem eng beieinander (155 / 176 / 208) —
ein sicheres Zeichen, dass im dünnen Ausläufer der Verteilung gerechnet wurde.

**Der Grund ist die Datenbasis, nicht das Verfahren:** eine einzelne, ruhige Wetterlage ist
keine Klimatologie. Nötig ist mindestens **eine Konvektionssaison (April–September)**.

🟢 **Und dafür braucht es kein eigenes Archiv:** Open-Meteo stellt mit der **Historical
Forecast API / Previous Runs API** genau diese historischen Modellläufe bereit. Die Eichung ist
damit **sofort rechenbar** und nicht, wie zuvor angenommen, durch wochenlanges Sammeln
blockiert. Das verschiebt die Feineichung (Rang 7) nach vorn.

⇒ **Antwort auf E1b: ja, ICON-EU braucht eine eigene Leiter** — aber sie wird nicht geraten,
sondern aus gesammelten Daten geeicht. Bis dahin darf die ICON-EU-Stufe nicht so behandelt
werden, als wäre sie mit der ICON-D2-Stufe gleichbedeutend.

### 4.5 Die Lösung steht bei den Wetterdiensten — Bedeutung harmonisieren, nicht Zahlen

Genau dieses Problem haben die europäischen Wetterdienste bei ihren Warnstufen, und sie lösen
es nicht durch einheitliche Zahlen. EMMA/Meteoalarm-Konferenzpapier (ECMWF 2008, ZAMG-Autoren):

> „4-level matrix for impact, advice, return periods and meteorological thresholds.
> **The meteorological thresholds differ from region to region due to the climatology of
> extreme events.**"

Harmonisiert sind **Farbcode, Bedeutungsebene und Verhaltensempfehlung**. Die Zahlenschwellen
legt jeder nationale Dienst selbst fest, kalibriert über **Wiederkehrperioden** auf seine
Klimatologie. Unabhängig bestätigt die LPI-Verifikationsliteratur dasselbe Prinzip für unsere
Größe: die verlässliche LPI-Schwelle hängt von Auflösung und akzeptiertem räumlichen
Toleranzradius ab (ASR 2022, COSMO-D2 2,2 km — dort **LPI > 1 J/kg** als Nachweisschwelle).

⚠️ **Grenze dieses Vorbilds:** Übernommen wird das **Prinzip**, nicht die Methode. Die
Wetterdienste stufen **wirkungsbasiert** ein (Böen in km/h, Regen in l/m², Hagelkorngröße) und
kalibrieren über Wiederkehrperioden extremer Ereignisse. Wir stufen **modellparameterbasiert**
ein. Eine „wie der DWD"-Rechtfertigung für unsere vier Stufen gibt es also nicht — der DWD
stuft nach Wirkung, nicht nach CAPE oder Blitzpotenzial.

⇒ **Leitlinie: je Quelle eine eigene Schwellenleiter, geeicht auf dieselbe Bedeutung.** Nicht
dieselbe Zahl überall. Das ist kein Notbehelf, sondern der Stand der Praxis.

**Optionen** (Entscheidung offen, s. Abschnitt 10):
- **(a) Hinnehmen und benennen** — die Stufe bleibt „bestes verfügbares Urteil vor Ort", und der
  Vergleich weist aus, dass die Grundlage je Ort verschieden ist.
- **(b) Kleinster gemeinsamer Nenner** — nur Signale nutzen, die überall verfügbar sind
  (praktisch: nur der Wettercode). Vergleichbar, aber deutlich schwächer.
- **(c) Herkunft mitführen** — die Stufe trägt sichtbar, worauf sie beruht (z. B. „hoch,
  Blitzdichte" vs. „hoch, Blitzpotenzial+Superzelle").
- **(d) Je Quelle eichen** *(neu, nach dem Meteoalarm-Vorbild)* — eigene Schwellen je
  Modell/Auflösung, kalibriert auf gleiche Überschreitungshäufigkeit. Braucht mehrere Wochen
  Daten (fällt mit Rang 4 ohnehin an) und ist mit (c) kombinierbar.

---

## 5. Beobachtung und Vorhersage — zwei getrennte Welten

Das Produkt weiß auch, was **gerade** passiert: Ein Radar-Nowcast ist angebunden, mit eigener
Quellenkette je Gebiet (`radar_service.py:280-313`): RADOLAN/BrightSky für Deutschland, INCA für
Österreich, ARPAE ICON-2I für Italien **inklusive Korsika** (seit #1648 — der frühere Radar-DPC
war ersatzlos zu streichen, er lieferte nur Vergangenheitsbilder), AROME-HD für Frankreich, ICON-D2 für die
Alpen, `minutely_15` als globaler Rückfall. Ob es gewittert, kommt aus dem WMO-Code 95/96/99 je
Einzelbild (`radar_service.py:151-153`).

🔴 **Diese Beobachtung fließt an keiner Stelle in die Gewitterstufe ein.**
`thunder_level_from_signals()` hat gar keinen Parameter dafür (`metric_format.py:326-370`), und
`thunder_level_max` ist schlicht das Maximum über die vorhergesagten Stundenwerte
(`weather_metrics.py:589-601`). Vorhersage und Beobachtung sind zwei Datenströme, die einander
nicht kennen — sie benutzen nur zufällig dieselbe Codenummer für „konvektiv".

Praktisch heißt das: Das Radar kann eine Gewitterzelle über der Etappe sehen, während die
Stufe im Briefing „kein Gewitter" sagt. Beides ist für sich korrekt, zusammen ist es ein
Widerspruch für den Nutzer.

Der Nowcast erreicht ihn heute auf zwei Wegen: über das `/jetzt`-Kommando
(`trip_command_processor.py:1293`) und über einen eigenen Radar-Alarm (Abschnitt 7).

**Schwachstelle:** Fällt die Gewitterprüfung im Nowcast aus, erscheint „Gewitter-Check nicht
verfügbar." **nur** im `/jetzt`-Text (`radar_service.py:268-269`) — im Alarm-Pfad gibt es
dafür keine Entsprechung. Für die Vorhersage-Quellen ist die Ausfallsichtbarkeit dagegen
sauber gebaut (Abschnitt 6.1).

---

## 6. Amtliche Warnungen

Warnungen der Wetterdienste kommen aus sieben registrierten Quellen
(`official_alerts/__init__.py:36-42`): Vigilance und Meteo-Forêts für Frankreich,
Massif-Sperrungen, GeoSphere für Österreich, MeteoAlarm-Feeds für Italien und Österreich, DPC
für Italien. Gewitter erscheint dort als `hazard="thunderstorm"`.

🔴 **Für Deutschland ist kein Warndienst registriert.** Der DWD betreibt einen amtlichen
Warndienst, wir binden ihn nicht an. Wer in Deutschland unterwegs ist, bekommt also
Gewitterwarnungen der Behörde nicht — anders als in Frankreich, Italien und Österreich.

**Für E6 gibt es bereits Tickets — kein neues anlegen** (geprüft 2026-08-08):

| Issue | Inhalt | Stand |
|---|---|---|
| **#1440** | DWD-CAP-Warnungen als `OfficialAlertSource` (Deutschland) | PO-beauftragt 2026-07-31, `needs-po-approval`, `priority:low` |
| #1442 | MeteoAlarm-Ländererweiterung (CH → Skandinavien → Rest-EU) | hängt am Budget-Refactor #1397 |
| **#1445** | MeteoAlarm via MQTT statt REST-Polling | 🔴 `priority:critical`, `status:deferred` |

### 🟢 Der Weg ist bereits gebaut — E6 ist eine Länder-Ergänzung, kein Projekt

**Das Kontingentproblem aus #1445 ist gelöst.** `MeteoAlarmFeedSource`
(`services/official_alerts/meteoalarm_feed.py`) läuft produktiv für Italien und Österreich und
ersetzt laut eigenem Modul-Kopf den kontingentierten Weg:

> „**kontingentfreier CAP-Feed** … Ersetzt den kontingentierten EDR-Index-Weg (`meteoalarm.py`)
> durch `feeds.meteoalarm.org` — eine Momentaufnahme ALLER aktuell gültigen Warnungen des
> jeweiligen Landes mit vollem CAP-Inhalt **in einem einzigen, unauthentifizierten Abruf**."

Der paginierte EDR-Weg ist seit #1445 S3 **nicht mehr registriert**
(`official_alerts/__init__.py:30-35`). Die 100-Requests-Grenze betrifft ihn, nicht den Feed.

**Für Deutschland gemessen (2026-08-08):**

| | Abruf | Größe | Gewitterwarnungen |
|---|---|---|---|
| Italien *(produktiv)* | 0,5 s | 2,1 MB | — |
| Österreich *(produktiv)* | 1,0 s | 3,1 MB | — |
| **Deutschland** | **4,0 s** | **13,5 MB** | **878** |

Der DE-Feed liefert dieselbe JSON-Struktur, die der bestehende Code verarbeitet, mit
`EMMA_ID`-Geocodes (Zonenauflösung wie bei IT/AT) und der **vollen DWD-Abstufung** im
Ereignistext: `GEWITTER` · `STARKES GEWITTER` · `SCHWERES GEWITTER mit HEFTIGEM STARKREGEN und
HAGEL` · `SCHWERES GEWITTER mit ORKANBÖEN, HEFTIGEM STARKREGEN und HAGEL`.

⇒ **E6 = `MeteoAlarmFeedSource("DE")` ergänzen**: ein Eintrag in `_FEED_PATHS`
(`/api/v1/warnings/feeds-germany`), die `Literal`-Signatur erweitern, registrieren — plus die
Punkt→Zone-Auflösung für Deutschland, die der nicht-triviale Teil ist (Italien nutzt reine
Geometrie, Österreich die gecachte ZAMG-Antwort).

⚠️ **Einziger echter Vorbehalt: die Größe.** 13,5 MB gegen 2–3 MB bei IT/AT, **ohne gzip**
(gemessen: `Accept-Encoding: gzip` ändert nichts). Das Zeitbudget von 15 s
(`meteoalarm_feed.py:55`) trägt die gemessenen 4 s, ist aber knapper als bei den Nachbarn —
bei schlechter Netzlage zu beobachten.

**Damit entfallen zwei frühere Annahmen dieses Konzepts:** Der Meteoalarm-Weg ist *nicht*
verkontingentiert, und die DWD-Stufen 3 und 4 fallen im Feed *nicht* zusammen — beides steht im
Ereignistext. **#1440** (DWD-Einzelanbindung über BrightSky) wird dadurch womöglich
überflüssig; das ist dort zu entscheiden.

Auch hier gilt: **Die amtliche Warnung ist mit der berechneten Stufe nicht verknüpft.** In
`official_alerts.py` (1919 Zeilen) kommt `thunder_level` kein einziges Mal vor. Die beiden
Aussagen stehen unverbunden nebeneinander.

### 6.1 Wenn eine Gewitterquelle ausfällt

Fällt eine Direktquelle aus, springt eine Vertretung ein: DWD-D2 → ICON-EU, Météo-France →
ICON-EU; für ICON-EU selbst gibt es keine (`thunder_routing.py:88-92`). Das geschieht **nicht
stillschweigend** — der Nutzer bekommt eine Klartextzeile („Gewitterdaten von Ersatzquelle: DWD
Europa (gröbere Auflösung)", `fallback_notice.py:87`), eingebunden in HTML-, Text- und
Kompakt-Mail sowie Telegram. Das ist vorbildlich gelöst (ADR-0047) und der Maßstab, an dem sich
die Radar-Seite messen lassen muss.

---

## 7. Alarme — wann meldet sich das System von selbst

### 7.1 Der Regler

Gewitter ist die **einzige Gefahrenstufen-Größe** des Produkts. Der Nutzer stellt keine
Zahlenschwelle ein, sondern eine **Empfindlichkeitsstufe** je Metrik (ADR-0043). Bei Gewitter
wirkt sie über das erreichte Niveau (`alert_preset.py:102-106`):

| Stufe | Es meldet sich, wenn … |
|---|---|
| entspannt | die Stufe den vollen Weg von „kein" auf „hoch" springt |
| standard | die Höchststufe erreicht oder verlassen wird |
| sensibel | sich die Stufe überhaupt ändert (ab „mittel") |

Trip und Ortsvergleich nutzen dieselbe Maschinerie (`compare_alert.py:63-107`) — nur der
Ablageort der Einstellung unterscheidet sich. Das entspricht der Teilungspflicht.

### 7.2 🔴 Drei getrennte Alarme für dasselbe Gewitter

Zum selben Gewitter kann der Nutzer **drei voneinander unabhängige Nachrichten** bekommen:

| # | Alarm | Auslöser | Versand |
|---|---|---|---|
| 1 | Änderungsalarm | die berechnete Stufe ändert sich | `send_location_deviation_alert` |
| 2 | Radar-Alarm | Beobachtung sieht Konvektion aufziehen (≤ 20 min) | `send_radar_alert` |
| 3 | Amtliche Warnung | Behörde warnt neu oder höher | `send_official_alert` |

Die drei Wege werden **nie zusammengeführt**. Es gibt zwar eine gemeinsame
Dringlichkeitsableitung (`alert_urgency.py:52-57`), die aber nur das Maximum für Protokoll und
Schweregrad bildet — die Inhalte bleiben getrennt.

Für einen Wanderer mit knapper Verbindung ist das relevant: Drei Nachrichten zu einer Gefahr
kosten Aufmerksamkeit und Datenvolumen, und sie können sich widersprechen (Radar meldet
Gewitter, die Stufe sagt „kein" — siehe Abschnitt 5).

---

## 8. Wo Gewitter erscheint — neun Ausgabeorte

Eine Wettermetrik hat in diesem Produkt **diverse Ausgabeorte, alle müssen bedient werden**
(PO-Vorgabe 2026-08-05; bei Hagel wurden 5 von 9 vergessen).

| # | Ort | Fundstelle |
|---|---|---|
| 1 | E-Mail-Zusammenfassungszeile (Pill) | `email/helpers.py:1670` |
| 2 | Trip-Stundentabelle | `email/helpers.py:185` |
| 3 | Nachtblock | `email/helpers.py:154-236` |
| 4 | Kurzzusammenfassung | `compact_summary.py:571` |
| 5 | SMS-Token | `sms_trip.py:280` |
| 6 | Telegram-Fußzeile | `narrow.py:210` |
| 7 | GEWITTER-Kommando + Telegram-Drilldown | `trip_command_processor.py:228, 114, 126, 980` |
| 8 | Ortsvergleich (drei Unterstellen) | `compare_html.py:158, 331, 600` |
| 9 | Mehrtages-Vorschau | `outlook.py:200, 371`; `trip_report_scheduler.py:1820` |

---

## 9. Was bewusst NICHT gemacht wird

| Nicht | Grund |
|---|---|
| Fließtext, Sätze, formulierte Warnungen | Das Produkt gibt Metriken, Stufen, Spalten und Kurz-Token aus — keine Sätze (PO 2026-08-07) |
| Go/No-Go-Empfehlung, Timing-Rat | ADR-0007: Daten statt Empfehlungen |
| Zweite Achse „möglich/wahrscheinlich/akut" **in der Stufe** | Die Stufe ist eine **Stärke**-Skala. Unsicherheit ist eine andere Achse und wird nicht hineingemischt |
| Eigene Kalibrierung von Schwellen | PO-Verbot (#1456). Bestandsausnahmen (0,075 / 20) sind Altlast, kein Präzedenzfall |
| Hagel als Rang der Stufe | Eigenes Kennzeichen, kann kein „nein" (#1475) |
| Rohwerte als eigene Spalten | Abschnitt 2.2 |

---

## 10. Entscheidungen

### 10.1 Getroffen (PO, 2026-08-08)

| # | Frage | **Entscheidung** |
|---|---|---|
| **E2** | CAPE unsichtbar, obwohl die Wahrscheinlichkeit als Ersatz entfällt? | **Ja.** `selectable=False`. Die Begründung „Zutat ist nicht Antwort" gilt unabhängig davon, ob je ein Ersatz kommt |
| **E3** | Darf die Radar-Beobachtung die Stufe anheben? | **Ja.** Beobachtung hebt die Stufe — auch wenn die Vorhersage schweigt. Beseitigt den Widerspruch aus Abschnitt 5 |
| **E4** | Bleibt es bei EINER sichtbaren Gewitter-Metrik? | **Ja**, bis eine flächige publizierte Wahrscheinlichkeitsquelle existiert |
| **E5** | Die drei getrennten Gewitter-Alarme zusammenführen? | **Teilweise: amtliche Warnung und Änderungsalarm werden zusammengeführt, der Radar-Nowcast bleibt getrennt.** Fachlich stimmig — die beiden ersten beruhen auf Vorhersage und teilen den Zeithorizont; der Nowcast ist eine akute Beobachtung mit eigener Dringlichkeit und darf nicht in einer Sammelnachricht untergehen |
| **E6** | DWD-Warndienst für Deutschland anbinden? | **Ja — über `MeteoAlarmFeedSource("DE")`.** Der kontingentfreie Feed-Weg läuft bereits produktiv für IT/AT (#1445 S1/S3); Deutschland ist eine Länder-Ergänzung. Gemessen: 878 Gewitterwarnungen, volle DWD-Abstufung |
| **E7** | Ausfallsichtbarkeit für den Radar-Pfad? | **Nein**, vorerst nicht. Bleibt als bekannte Schwachstelle dokumentiert (Abschnitt 5) |
| **E1** | Umgang mit der ortsabhängigen Bedeutung der Stufe? | **Je Quelle eichen + Herkunft mitführen.** Eigene Schwellen je Modell, geeicht auf gleiche Häufigkeit (Prinzip der Wetterdienste); zusätzlich trägt die Stufe sichtbar, worauf sie beruht |
| **E1b** | Eigene Schwellenleiter für das ICON-EU-Stundenmaximum? | **Ja** — Faktor 235 gemessen (4.2). Sofort wirksam ohne Kalibrierung: gleiche Statistik verwenden (`lpi_max`), das nimmt Faktor 5 heraus |
| **E8** | Superzellen: Zutat oder eigenes Kennzeichen? | **Zutat.** Hebt die Stufe, bleibt unsichtbar — weil es den Index nur im DWD-Gebiet gibt und ein Schweigen auf dem GR20 wie Entwarnung aussähe (2.1b) |
| **E9** | Böen und Starkregen in die Gewitterstufe einrechnen? | **Nein, getrennt lassen.** Eine kombinierte Gefahrenstufe wäre Bewertung statt Beschreibung (ADR-0007) |

### 10.2 Offen

Keine offenen Grundsatzfragen mehr. Was bleibt, ist **Arbeit, nicht Entscheidung**:

| Was | Braucht |
|---|---|
| Feineichung der Schwellen je Quelle (E1b, Rang 7) | mehrere Wochen Messdaten über verschiedene Wetterlagen — fällt mit Rang 1 an |
| Einstufung des Superzellen-Index (Rang 8) | Beobachtung, wie oft er überhaupt anschlägt |

## 11. Umsetzung in Scheiben

Reihenfolge folgt einem Grundsatz: **erst eichen, dann erweitern.** Mehr Signale in eine Fusion
zu geben, deren bestehende Signale untereinander nicht vergleichbar sind, verschlimmert das
Problem, statt es zu lösen.

| Rang | Scheibe | Warum hier | Vorbedingung |
|---|---|---|---|
🔴 **Korrektur 2026-08-10 (gemessen, nicht nur gelesen):** Die Zeilen unten markierten
Ränge 2/3/4/5/7/10 als „✅" — das Kürzel verweist aber auf die **Entscheidung** (Abschnitt
10.1), nicht auf eine geprüfte Umsetzung. Direkter Codeabgleich (2026-08-10) zeigt: `cape`
hat weiterhin kein `selectable=False` (Rang 5), `lpi_max` wird nirgends abgerufen (Rang 3),
die LPI-Schwellen stehen weiterhin auf 5/20/50 statt der belegten 1/30/50 (Rang 2), keine
Herkunfts-Kennzeichnung der Stufe gefunden (Rang 4), `MeteoAlarmFeedSource("DE")` existiert
nicht (Rang 10) — nur Rang 0 ist tatsächlich im Code verifiziert. Diese Tabelle braucht eine
vollständige Nachmessung, bevor ihr wieder vertraut wird.

✅ **Nachtrag, noch 2026-08-10:** Rang 5 ist inzwischen tatsächlich umgesetzt — Issue **#1585**,
adversary-VERIFIED, Spec `docs/specs/modules/feat_1585_cape_selectable_false.md`. Damit ist der
Unterschied zwischen „✅ E2" (nur Entscheidung, Stand des Korrektur-Fundes oben) und „✅ erledigt"
(geprüfte Umsetzung, s. Stand-Spalte unten) an Rang 5 selbst nachvollziehbar. Die übrigen hier
genannten Lücken (Rang 2/3/4/7/10) sind davon unberührt und bleiben offen.

🟡 **Zweiter Nachtrag, ebenfalls 2026-08-10:** Der LPI-Teil von Rang 2 ist inzwischen ebenfalls
umgesetzt — Issue **#1679**, adversary-VERIFIED, Spec
`docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md`: `app.model_registry.LPI_THRESHOLDS_JKG`
liefert DE_ALPEN (ICON-D2) jetzt die belegte 1/30/50-Leiter (Bína et al.), EU_REST (ICON-EU)
bleibt bewusst auf dem Interim-Wert 5/20/50 bis #1678. Die beiden ANDEREN Teile von Rang 2 — CAPE-
Ladder 1000/2500/4000 statt binär und die CIN-Paarung −25/−50/−100/−200 — sind davon NICHT
betroffen und bleiben offen (CIN hängt zusätzlich an #1531). Rang 2 ist damit nur **teilweise**
erledigt — die weiterhin offenen Ränge sind 2 (CAPE-Ladder/CIN-Rest), 3, 4, 7, 10.

Zur Eichung selbst (Rang 7): Abschnitt 4.4 stellt bereits richtig, dass die Historical
Forecast API die Eichung **sofort rechenbar** macht — kein wochenlanges Sammeln nötig, keine
Abhängigkeit von #1531 (das andere Felder holt). Tracking-Ticket: **#1678**.

| Rang | Scheibe | Warum hier | Stand |
|---|---|---|---|
| **0** | ✅ **CAPE-Schwelle modellabhängig gemacht** (3.4b, **#1592**, ADR-0048) | **Fusion, RiskEngine und Δ-Alarme erledigt und live**: Schwelle je Modell × Gebiet, geeicht am 95. Perzentil der Modellklimatologie (mind. 300 J/kg). Auf dem GR20 gilt jetzt 300 statt 1000 — CAPE trägt dort erstmals bei. RiskEngine zählt CAPE nicht mehr doppelt (C2), Δ-Alarme rechnen die Empfindlichkeitsstufe in dieselbe Modellwelt um (C3). Vollzugsvermerk: ADR-0048 | ✅ erledigt |
| **1** | ✅ **Fehlende DWD-Größen abrufen** (#1531) — Felder befüllen, **nicht** einstufen | Liefert `lpi_max` (gleiche Statistik) und `cin_ml` (ersetzt die Deckelung). **CIN gibt es bei Open-Meteo nicht für ICON/AROME** — der Direktabruf ist der einzige Weg | ✅ **erledigt** (2026-08-11, live) |
| **2** | ✅ **Belegte Leitern übernehmen**: LPI **1/30/50** statt 5/**20**/50 · CAPE **1000/2500/4000** statt binär · CIN-Paarung **−25/−50/−100/−200** statt Deckelung | Beseitigt eine der beiden erfundenen Zahlen und macht CAPE zu einem vollwertigen Signal. Alles belegt (3.5, 3.5b) | ✅ **erledigt** — LPI-Teil **#1679** (adversary-VERIFIED); CAPE-Ladder + CIN-Paarung ebenfalls **#1679** (`feat_1679_cin_paarung_cape_leiter.md`, 2026-08-11, adversary-VERIFIED für AC-3/AC-5 mit Mutationsprobe, restliche ACs durch 24 RED-Tests grün) |
| **3** | **Gleiche Statistik**: `lpi_max` statt `lpi` gegen `lpi_con_max` | Nimmt allein **Faktor 5** aus dem Gebietsbruch — ohne jede Kalibrierung | ✅ E1 |
| **4** | **Herkunft mitführen** — die Stufe trägt sichtbar, worauf sie beruht | Macht im Ortsvergleich erkennbar, dass Korsika und Alpen auf verschiedenen Größen fußen | ✅ E1 |
| **5** | ✅ **CAPE unsichtbar gemacht** (`selectable=False`, **#1585**) | **Umgesetzt und live** (2026-08-10): CAPE (`cape_jkg`) ist an jeder Nutzerkontakt-Stelle unsichtbar (Trip-Editor, E-Mail, SMS, Ortsvergleich inkl. Alt-Vergleich, Aktivitäts-Vorlagen, Wertebereichs-Korridor, jede Alarmwirkung inkl. #1592 Delta-Alarm) und bleibt ausschließlich interne Zutat der Fusion. Adversary-VERIFIED | ✅ erledigt |
| **6** | **Radar hebt die Stufe an** | Beseitigt den Widerspruch aus Abschnitt 5 | ✅ E3 |
| **7** | **Feineichung je Quelle** (E1b): eigene Leiter für `lpi_con_max`, kalibriert auf gleiche Überschreitungshäufigkeit | Sofort rechenbar über die Historical Forecast API (4.4) — unabhängig von #1531 | 🔴 offen, Ticket **#1678** |
| **8** | **`sdi_2` einhängen** | Publizierte DWD-Schwelle vorhanden; erst sinnvoll, wenn die Skala geeicht ist | nach Rang 7 |
| **9** | **Amtliche Warnung + Änderungsalarm zusammenführen** (E5); Radar-Nowcast bleibt eigener Kanal | Unabhängig von der Signalkette | ✅ E5 |
| **10** | **Deutschland an den Meteoalarm-Feed** — `MeteoAlarmFeedSource("DE")` | Der Weg läuft produktiv für IT/AT und ist kontingentfrei. Offen: Punkt→Zone-Auflösung für DE, und 13,5 MB je Abruf ohne gzip | ✅ E6 |

**Nicht geplant:** Gewitter-Wahrscheinlichkeit (keine Quelle, Abschnitt 2.1),
`dbz_cmax`/`echotop` (falsch kalibriert bzw. falsche Größe), Ausfallsichtbarkeit im Radar-Pfad
(E7 zurückgestellt).

**In Prüfung, entscheidet Rang 1:** Ob sich die Signale seriös auf die vier groben Stufen
abbilden lassen. Die bisherige Haltung „keine exakt publizierte Schwelle, also gar keine
Einstufung" war womöglich zu streng — eine vierstufige Skala braucht keine
Präzisionskalibrierung, sondern eine belastbare Zuordnung „ab hier wird es ernst".
