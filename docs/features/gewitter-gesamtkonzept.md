# Gewitter — Gesamtkonzept

**Stand:** 2026-08-08 · **Status:** Entwurf, PO-Entscheidungen offen (Abschnitt 10)

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

**Genau zwei Größen erreichen den Nutzer.** Alles andere ist Zutat und bleibt unsichtbar.

| Größe | Frage | Werte | Status |
|---|---|---|---|
| **Gewitter-Stärke** (`thunder`) | Wie stark? | kein · leicht · mittel · hoch | existiert; wird heute **unvollständig** berechnet |
| **Hagel** (`hail_flag`) | Hagel dabei? | ja · unbekannt | existiert; eigenes Kennzeichen, **keine** Metrik (#1475) |

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

### 2.2 Warum die Zutaten unsichtbar bleiben

CAPE, Konvektionshemmung, Blitzdichte, Blitzpotenzial, Superzellen-Index sind **Zutaten** der
Stufe. Sie sind der Weg zur Antwort, nicht die Antwort. Zwei Gründe, warum sie keine eigenen
Spalten bekommen:

- **Gebietsabhängige Verfügbarkeit** — dieselbe Spalte trüge je nach Ort eine andere Größe oder
  wäre leer (s. Abschnitt 4).
- **Unvereinbare Skalen** — Blitzdichte liegt bei ~0,2, Blitzpotenzial bei ~88. Nebeneinander
  in einer Stundentabelle sind sie nicht lesbar, in einer SMS (≤ 160 Zeichen) gar nicht.

Heute ist genau **eine** Zutat sichtbar: CAPE — nicht weil das entschieden wurde, sondern weil
sie historisch zuerst im Katalog stand. ⇒ **CAPE wird unsichtbar** (`selectable=False`), aus
demselben Grund wie alle anderen Zutaten. Sie bleibt intern Teil der Berechnung.
Präzedenz: `confidence` (ADR-0005). Bestandsdaten laden still weiter, keine Migration.

---

## 3. Wie die Stärke entsteht

### 3.1 Das Verfahren heute

`thunder_level_from_signals()` (`metric_format.py:326`) übersetzt **jedes Signal einzeln** in
eine Stufe und nimmt dann **das schärfste**. Sind alle leer, ist das Ergebnis leer.

| # | Signal | Schwellen (leicht / mittel / hoch) | Beleglage |
|---|---|---|---|
| 1 | WMO-Wettercode | 95 / 96 / 99 | vom Anbieter geliefert |
| 2 | Blitzdichte (Blitze/km²/3 h) | 0,003 / 0,015 / **0,075** | ECMWF-Leitfaden; **0,075 nicht publiziert** |
| 3 | Blitzpotenzial LPI (J/kg) | 5 / **20** / 50 | DWD/Copernicus; **20 interpoliert** |
| 4 | CAPE (J/kg) | ≥ 1000 → nur „leicht", **deckelt** | Katalog-Risikoschwelle |

### 3.2 Die Annahmen darin — offen ausgesprochen

- **„Das schärfste Signal gewinnt."** Kein Mitteln, kein Gewichten. Sicherheitsgerichtet, aber
  ein einzelner Ausreißer hebt die Stufe.
- **Signale werden nicht kombiniert.** Hohe Energie *und* hohes Blitzpotenzial ergibt nicht mehr
  als Blitzpotenzial allein. Vereinfachung, keine Physik.
- **Zwei von acht Schwellen sind interpoliert**, nicht publiziert (0,075 und 20). Das ist
  faktisch Eigenkalibrierung im Bestand — dieselbe Sache, die als Verbot die Schließung von
  #1456 begründet hat. Beide stehen ehrlich als Kommentar im Code.
- **CAPE ist gedeckelt, weil die Gegengröße fehlt.** Viel Energie unter einem Deckel heißt: es
  passiert nichts. Da die Konvektionshemmung nie abgerufen wurde, wird CAPE vorsorglich nie
  höher als „leicht" gewertet. Das ist eine **Notbremse, kein Modell**.

### 3.3 Was fehlt — und was davon belegbar nachrüstbar ist

| Signal | Nutzen | Belegte Schwelle? | Verfügbar? |
|---|---|---|---|
| **Konvektionshemmung** `cin_ml` | macht CAPE erst verwertbar, ersetzt die Deckelung | ❌ keine publizierte Paarungsregel | ✅ ICON-D2 + ICON-EU |
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

---

## 4. Das ungelöste Kernproblem: die Stufe bedeutet je nach Ort etwas anderes

Dies ist der wichtigste Punkt des Konzepts und bislang nirgends adressiert.

Gewittersignale kommen je Gebiet aus verschiedenen Quellen mit **verschiedenen Größen**:

| Gebiet | Quelle | Signale, die ankommen |
|---|---|---|
| Frankreich/Korsika (**GR20**) | Météo-France AROME | Wettercode + **Blitzdichte** |
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

> **Messstand:** Am identischen Ausschnitt (DE/Alpen, 1020 Gitterpunkte, +15 h) war die
> Stichprobe an einem ruhigen Tag zu klein für eine Quantifizierung — nur 2 Punkte trugen
> überhaupt Werte, beide nur in ICON-EU. Die Richtung stimmt, der Betrag ist **offen**. Der
> strukturelle Befund folgt aus der Definition der Statistik, nicht aus dieser Messung.

⇒ Zu klären ist, ob `lpi_con_max` eine eigene Schwellenleiter braucht oder ein eigenes Feld.
Solange beides offen ist, ist die Stufe zwischen DWD-Gebieten nicht sauber vergleichbar.

**Optionen** (Entscheidung offen, s. Abschnitt 10):
- **(a) Hinnehmen und benennen** — die Stufe bleibt „bestes verfügbares Urteil vor Ort", und der
  Vergleich weist aus, dass die Grundlage je Ort verschieden ist.
- **(b) Kleinster gemeinsamer Nenner** — nur Signale nutzen, die überall verfügbar sind
  (praktisch: nur der Wettercode). Vergleichbar, aber deutlich schwächer.
- **(c) Herkunft mitführen** — die Stufe trägt sichtbar, worauf sie beruht (z. B. „hoch,
  Blitzdichte" vs. „hoch, Blitzpotenzial+Superzelle").

---

## 5. Beobachtung und Vorhersage — zwei getrennte Welten

Das Produkt weiß auch, was **gerade** passiert: Ein Radar-Nowcast ist angebunden, mit eigener
Quellenkette je Gebiet (`radar_service.py:280-313`): RADOLAN/BrightSky für Deutschland, INCA für
Österreich, Radar-DPC für Italien **inklusive Korsika**, AROME-HD für Frankreich, ICON-D2 für die
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

## 10. Offene Entscheidungen (PO)

| # | Frage | Empfehlung |
|---|---|---|
| E1 | Umgang mit der gebietsabhängigen Bedeutung der Stufe (Abschnitt 4) | **(a) hinnehmen + im Vergleich benennen** — (b) verschenkt die guten Signale, (c) ist teuer |
| E1b | Bekommt `lpi_con_max` eine eigene Schwellenleiter (Abschnitt 4.1)? | **Ja, sobald messbar** — vorher an ein paar echten Gewitterlagen den Versatz bestimmen; ohne Beleg keine erfundene Leiter |
| E2 | Wird CAPE unsichtbar, obwohl die Wahrscheinlichkeit als Ersatz entfällt? | **Ja** — die Begründung („Zutat ist nicht Antwort") gilt unabhängig; die Stärke bleibt als Antwort |
| E3 | Darf die Radar-Beobachtung die Stufe anheben (Abschnitt 5)? | **Ja** — sonst bleibt der Widerspruch „Radar sieht Gewitter, Stufe sagt kein Gewitter" bestehen. Regel liegt in #1419 §4 |
| E4 | Bleibt es dauerhaft bei EINER Gewitter-Metrik? | Ja, bis eine flächige publizierte Wahrscheinlichkeitsquelle existiert |
| E5 | Drei getrennte Gewitter-Alarme zusammenführen (Abschnitt 7.2)? | **Ja, mindestens entkoppeln** — für einen Wanderer mit knapper Verbindung sind drei Nachrichten zu einer Gefahr zu viel |
| E6 | DWD-Warndienst für Deutschland anbinden (Abschnitt 6)? | **Ja** — Frankreich, Italien und Österreich haben amtliche Warnungen, Deutschland nicht |
| E7 | Ausfallsichtbarkeit auch für den Radar-Pfad (Abschnitt 5)? | **Ja** — für die Vorhersagequellen ist es gebaut, für Radar fehlt es |

---

## 11. Umsetzung in Scheiben

Reihenfolge folgt einem Grundsatz: **erst eichen, dann erweitern.** Mehr Signale in eine Fusion
zu geben, deren bestehende Signale untereinander nicht vergleichbar sind, verschlimmert das
Problem, statt es zu lösen.

| Rang | Scheibe | Warum hier | Vorbedingung |
|---|---|---|---|
| **1** | **Eichung klären** (E1, E1b): Bedeutet „mittel" überall dasselbe? Braucht `lpi_con_max` eine eigene Leiter? | Fundament. Ohne das ist jede weitere Größe Rauschen auf schiefer Skala | PO-Entscheid |
| **2** | **CAPE unsichtbar** (`selectable=False`) | Klein, unabhängig, beendet den historischen Zufall. Im Kern ein Katalog-Kwarg — die Render-Pfade prüfen `selectable` bereits generisch | E2 |
| **3** | **Radar hebt die Stufe an** | Größter Nutzen ohne neue Quelle; beseitigt den Widerspruch aus Abschnitt 5 | E3 |
| **4** | **Fehlende DWD-Größen abrufen** (#1531) — Felder befüllen, mitlaufen lassen, **nicht** einstufen | Datensammlung als Voraussetzung für Rang 5. Spec liegt fertig vor | — |
| **5** | **Einstufung nachziehen**: `sdi_2` (publizierte Schwelle), `cin_ml` statt CAPE-Deckelung | Erst wenn Rang 4 echte Messwerte geliefert hat | Rang 4 + belegte Schwellen |
| **6** | **Alarme entkoppeln** (E5), **DWD-Warnungen** (E6), **Radar-Ausfallsichtbarkeit** (E7) | Unabhängig von der Signalkette, jederzeit einschiebbar | E5–E7 |

**Nicht geplant:** Gewitter-Wahrscheinlichkeit (keine Quelle, Abschnitt 2.1), `uh_max`-Einstufung
(keine übertragbare Zahl), `dbz_cmax`/`echotop` (falsch kalibriert bzw. falsche Größe).
