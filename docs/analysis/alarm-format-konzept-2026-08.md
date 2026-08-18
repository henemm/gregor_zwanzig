# Alarm-Format-Konzept v3 — FREIGEGEBEN (#1948)

> Status: **Alle Entscheidungsfragen vom PO beantwortet (PO-Runde 4,
> 2026-08-17).** Ersetzt inhaltlich die pausierte Spec
> `docs/specs/modules/fix_1948_1939_alarm_sms_referenzzeitpunkt.md` (jetzt
> obsolet markiert, s. Abschnitt 8). Grundlage: Ist-Vokabular-Inventur
> (Kommentare in #1948), PO-Runde 3+4 (2026-08-17). Ortsvergleich bleibt in
> diesem Dokument durchgehend zurückgestellt (PO-Entscheid).
>
> **Aufgabenteilung zu Epic #1458** (Ergänzung #1493-Sitzung): #1458 (E1–E5 —
> Zweck, Dringlichkeit, Auslöser-Zahl, Bedienort, Ortsvergleich-Parität; die
> „Messlatte", WANN überhaupt alarmiert wird) ist an eine eigene Sitzung
> vergeben und NICHT Teil dieses Dokuments. #1948 behält E6 (Debug-Protokoll,
> Abschnitt 8 S1) und die Format-Frage (WIE eine ausgelöste Meldung aussieht).

## 0. Leitsatz (PO-Kern)

> **Format folgt dem Phänomen, nicht der Quelle.**

Der Empfänger einer Alarm-SMS interessiert sich nicht dafür, welcher
Programmteil ein Gewitter zuerst bemerkt hat — Δ-Vergleich zum letzten
Briefing, Regenradar-Nowcast oder amtliche Wetterwarnung. Er erwartet EIN
Standardformat, in der Sprache, die er aus dem täglichen Trip-Briefing bereits
kennt. Konkret: ein Gewitter heißt in ALLEN drei Alarm-Zweigen `TH:` mit
derselben Stufenleiter, die das Briefing bereits verwendet
(`LEVELS = {0: "-", 1: "L", 2: "M", 3: "H"}`, `src/output/tokens/metrics.py:14`).
Das amtliche Sonderformat — Trip-Präfix (`KHW403`), `AMT`-Kopf, numerische
Warnstufen-Notation (`GELB1/3`), ein von der Zeitfenster-Notation dominiertes
Erscheinungsbild — verschwindet aus Nutzersicht vollständig. Die zugrunde
liegende Datenherkunft (amtlicher Dienst vs. eigene Modellauswertung) bleibt
intern unterschiedlich; nur die Darstellung wird eins.

## 1. Zielbild je Phänomen (NUR Ist-Vokabular, mit Fundstellen)

**Die Trip-Briefing-SMS ist die lebende Referenz-Implementierung dieses
Zielbilds** (Ergänzung #1493-Sitzung) — kein reines Bauteil-Lager, sondern der
bereits produktiv laufende Beweis, dass `TH:M@14(H@18)` als Notation
funktioniert (`render_threshold_peak_value()`, `tokens/builder.py:392`,
`FORECAST_TH` + `LEVELS`). Das Alarm-System zieht auf genau dieses,
bereits bewährte Format nach — es entsteht nichts fachlich Neues.

Am Beispiel Gewitter, Ziel-Segment, PO-finalisierte Beispiele
(**PO-Entscheidung Runde 4: Trennzeichen `->`, KEIN Vorzeichen-Präfix** —
Begründung Abschnitt 3):

| Zweig | Zielbild-SMS | Bausteine (alle Ist-Vokabular, Fundstelle) |
|---|---|---|
| **a — Δ-Alarm** | `Ziel: TH:M->H@16` | Kopf `Ziel:` = `format_alert_location`/`_km_str` (`render.py:787`, bereits Ist-Zustand für Zweig a); Code `TH:` = Wetter-Register (`get_sms_code`, `metric_catalog.py`, genutzt von `render.py:93` UND `output/tokens/builder.py`); Stufen-Buchstaben `M`/`H` = `LEVELS`-Map (`output/tokens/metrics.py:14`, **heute nur vom Trip-Briefing-Builder genutzt, NICHT von `_sms_token()`** — Bauteil existiert, ist aber nicht verdrahtet, s. Abschnitt 9); `->`-Notation OHNE Vorzeichen-Präfix = finale PO-Entscheidung (Abschnitt 3); `@16` = `occurred_at`-Suffix (`_sms_token`, `render.py:712-713`, bereits Ist-Zustand) — Regel 5 (Abschnitt 2) legt fest: `@` markiert immer den BEGINN-Zeitpunkt |
| **c — Nowcast** | `Ziel: TH@15:40` | Kopf `Ziel:` = **fehlt heute** — `_render_sms_onset` baut eigenständig `km{a}-{b}:` (`render.py:346-349`), nutzt NICHT `format_alert_location`/`_km_str` wie Zweig a (Bauteil fehlt, s. Abschnitt 9); Code `TH` = Wetter-Register (bereits genutzt, `render.py:343`, aktuell als `TH!{n}`); Uhrzeit `15:40` = `OnsetEvent.onset_time` (Feld **existiert bereits**, wird in E-Mail/Telegram genutzt, `render.py:227,282,330`, aber NICHT in `_render_sms_onset` — PO-bestätigter Uhrzeit-statt-Countdown-Entscheid ist damit ohne neuen Datenpunkt umsetzbar, s. Ist-Vokabular-Inventur „Machbarkeit 1") — `@15:40` (mit Minuten) statt `@14` (nur Stunde), da Radar-Nowcast-Auflösung feiner ist als Stundenvorhersage (Regel 5) |
| **b — amtlich** | `Ziel: TH:H 13-22` | Kopf `Ziel:` = **fehlt heute** — `render_official_alert_sms` baut `{prefix} AMT {Stufenwort}{Pos}/3:` (`official_alerts.py:2070`), kennt `format_alert_location` nicht (Bauteil fehlt); Code `TH:` = Wetter-Register-Form (heute nutzt Zweig b das GETRENNTE Gefahren-Register `HAZARD_SMS_SYMBOLS`, `thunderstorm→TH` OHNE Doppelpunkt, `hazard_symbols.py:15` — Angleichung an `TH:` ist Teil der Kollisions-Bereinigung, Abschnitt 5); Stufenbuchstabe `H` = **PO-Entscheidung Option 1** (Abschnitt 4): GRÜN→`-`, GELB→`L`, ORANGE→`M`, ROT→`H`, für ALLE Gefahrenarten; Zeitfenster `13-22` = vereinfachte Form von `_tag_time` (`official_alerts.py:1896-1918`, heute `Fr06-20` mit Wochentag) — Wochentag entfällt hier, weil Gültigkeit laut Regel 2 (Abschnitt 2) heute beginnt |

**Vergleichszeitpunkt (`reference_at`) entfällt aus der SMS vollständig** —
keines der finalen Zielbilder trägt ein `@HH:MM`-Präfix im Kopf. Der
Von-Bis-Token selbst (`VS1400->280`) zeigt den Ausschlag bereits vollständig;
ein zusätzlicher Hinweis „verglichen mit HH:MM" wäre in der Kurzform
redundant. Das löst den ursprünglichen #1948-Auslöser-Bug durch **Entfernen**
statt durch Umformulieren (Details Abschnitt 8, Scheibe S3) — und macht
#1939 (Vergleichszeitpunkt schleicht sich in den kopflosen Compare-Pfad)
strukturell unmöglich, weil es in der SMS gar keinen Vergleichszeitpunkt mehr
gibt, der sich einschleichen könnte.

**Was NICHT im Zielbild vorkommt, weil es heute schon fehlt und hier nicht neu
erfunden wird:** ein Wiederholungs-Signal (PO-Entscheid: gestrichen, s.
Abschnitt 7).

## 2. Regeln (aus dem Leitsatz abgeleitet)

1. **Kein Trip-Name in Alarm-SMS.** Ausweitung von `fix_1935_1779_...md` AC-5
   (bereits für Zweig a Trip-Δ, teilweise Zweig c) auf Zweig b — der
   `KHW403`-Präfix in `render_official_alert_sms` entfällt.
2. **Wochentag nur, wenn die Gültigkeit NICHT heute beginnt.** Eine Regel für
   alle Zweige mit Zeitbezug (heute betrifft praktisch nur Zweig b, da Zweig a
   keine Wochentage zeigt und Zweig c auf eine Uhrzeit ohne Datum umgestellt
   wird). Baut auf `_tag_time` auf, ergänzt eine Bedingung, ersetzt die
   Funktion nicht.
3. **Etappen-/Segment-Kopf vorne, wie im Δ-Pfad.** Alle drei Zweige nutzen
   künftig `format_alert_location`/`_km_str` als EINZIGE Kopf-Quelle. Heute:
   Zweig a hat das bereits, Zweig c baut einen eigenen `km{a}-{b}:`-Kopf,
   Zweig b einen eigenen `AMT`-Kopf.
4. **Behörden-Warnstufe wird auf die `TH:`-/Gefahren-Stufenleiter abgebildet**
   — **PO-Entscheidung: Option 1** (Abschnitt 4), GRÜN→`-`, GELB→`L`,
   ORANGE→`M`, ROT→`H`, für alle Gefahrenarten.
5. **`@` markiert immer den BEGINN-Zeitpunkt eines Ereignisses; die Auflösung
   (Stunde vs. Stunde:Minute) folgt der Datenquelle, nicht dem Zweig**
   (Ergänzung #1493-Sitzung). Stundenvorhersage → `@14` (ohne führende Null,
   wie im Briefing, `sms_format.md:52`); Radar-Nowcast → `@15:40` (Minuten,
   da die Quelle minutengenau misst). Dieselbe Notation gilt identisch in
   Briefing-SMS UND Alarm-SMS — keine zweite `@`-Bedeutung entsteht.

## 3. Notations-Studie: `>` vs. Alternativen

**Ausgangslage:** `1400>280` (heutige #1935-Notation) liest sich als „größer
als" — PO-Kritik, zur Neuentscheidung gestellt. Sechs Kandidaten (Trennzeichen-
Varianten des bestehenden Von-Bis-Prinzips, keine neuen Codes), gegen sechs
Extremfälle geprüft. Zeichenkosten ohne Vorzeichen-Präfix/Code gezählt, wo
nicht anders vermerkt.

**Kandidaten:**

| # | Kandidat | GSM-7-Kosten |
|---|---|---|
| A | `von>bis` (Ist-Zustand, #1935) | Basis, 1 Septet je Zeichen |
| B | `von/bis` | Basis, 1 Septet je Zeichen |
| C | `von-bis` | Basis, 1 Septet je Zeichen |
| D | `von(bis)` | Basis — `(`/`)` sind GSM-7-BASIS-Zeichen, nicht Extension (verifiziert an `render.py:822-833`: die Extension-Ersetzungstabelle wandelt `[`/`{` GERADE IN `(` um, um die 2-Septet-Kosten der eckigen/geschweiften Klammern zu vermeiden) |
| E | `von zu bis` | Basis, aber mit Leerzeichen teurer |
| F | `von→bis` | **NICHT GSM-7** — jedes Vorkommen zwingt die GESAMTE SMS in UCS-2-Kodierung |

**Extremfälle × Kandidaten** (Format: gerenderter Token · Zeichen · Befund):

**1) Sicht 1.400→280 m (VS, fallend, großer Zahlenbereich)**
- A: `-VS1400>280` (11) — liest sich als „größer als" (Ausgangs-Kritik)
- B: `-VS1400/280` (11) — „/" evoziert eher Bruch/Oder, unüblich für Zeitreihen
- C: `-VS1400-280` (11) — 🔴 kollidiert mit der bestehenden km-Spannen-Notation (`km{a}-{b}`) — dieselbe Zeichenfolge bedeutet an anderer Stelle im System etwas anderes
- D: `-VS1400(280)` (12, +1) — Klammer trennt optisch klar, kein Kollisionsrisiko
- E: `-VS1400zu280` (12, +1, ohne Leerzeichen) / `-VS 1400 zu 280` (16, +5, mit Leerzeichen)
- F: `-VS1400→280` (11 Zeichen, aber UCS-2-Trigger für die GANZE SMS)

**2) Böen 30→80 km/h (G, steigend)**
- A: `+G30>80` (7) · B: `+G30/80` (7) · C: `+G30-80` (7, 🔴 dieselbe km-Kollision) · D: `+G30(80)` (8) · E: `+G30zu80` (8) · F: `+G30→80` (7, UCS-2-Trigger)

**3) Temperatur 5→−3 °C (Minus-Kollision, der schärfste Testfall)**
- A: `-D5>-3` (6) — 🔴🔴 der Alarm-Vorzeichen-Präfix „-" und der negative Zielwert „-3" stehen unmittelbar nach dem „>" — liest sich wie „5 größer als minus 3" oder verschmilzt zu „5>−3" ohne erkennbare Grenze zwischen Vorzeichen und Wert
- B: `-D5/-3` (6) — dieselbe Doppel-Minus-Unschärfe, unabhängig vom Trennzeichen
- C: `-D5--3` (6) — 🔴🔴🔴 ZWEI Minuszeichen direkt hintereinander, praktisch unlesbar
- D: `-D5(-3)` (7, +1) — Klammer trennt das negative Vorzeichen des Zielwerts optisch klar vom Alarm-Vorzeichen-Präfix — geringstes Verwechslungsrisiko aller Kandidaten bei diesem Testfall, trotz identischer Zeichen
- E: `-D5zu-3` (7, +1) — „zu" trennt ebenfalls eindeutig, kein Minus-Zusammenstoß
- F: `-D5→-3` (6, UCS-2-Trigger) — Pfeil trennt visuell klar, löst aber das Kodierungsproblem aus

**4) Gewitterstufe M→H (nicht-numerisch, `LEVELS`-Buchstaben)**
- A: `+TH:M>H` (7) · B: `+TH:M/H` (7) · C: `+TH:M-H` (7) · D: `+TH:M(H)` (8) · E: `+TH:Mzu H`? — Buchstabe+Wort ohne Trennzeichen kaum scannbar, mit Leerzeichen `+TH:M zu H` (10) · F: `+TH:M→H` (7, UCS-2-Trigger)
- Befund: bei Buchstaben-Stufen ist die „>"-Ambiguität („größer als") deutlich SCHWÄCHER als bei Zahlen — ein Leser liest „M größer als H" seltener fehl als „1400 größer als 280", weil Buchstaben keine Zahlenordnung suggerieren, die mit realen Messwerten verwechselt werden könnte

**5) Regen 0,2→14,5 mm (Dezimalstellen)**
- A: `+R0.2>14.5` (10) · B: `+R0.2/14.5` (10) · C: `+R0.2-14.5` (10, 🔴 km-Kollisionsrisiko geringer da Dezimalpunkt unüblich in km-Spannen, aber strukturell dasselbe Zeichen) · D: `+R0.2(14.5)` (11) · E: `+R0.2zu14.5` (11) · F: `+R0.2→14.5` (10, UCS-2-Trigger)

**6) Mehrfach-Ereignis in einer SMS** (`Segment 2-3, Ziel: {Token1} {Token2}`, Beispiel Böen + Sicht)
- A: `+G30>80@15 -VS1400>280@14` (25) — zwei „>"-Zeichen nebeneinander im Fließtext erschweren das Scannen, technisch aber je Token eindeutig zuordenbar (Code-Präfix trennt)
- B: `+G30/80@15 -VS1400/280@14` (25) — dieselbe Scan-Schwierigkeit
- C: entfällt strukturell (km-Kollision UND Doppel-Minus-Risiko gelten pro Token, addieren sich)
- D: `+G30(80)@15 -VS1400(280)@14` (28, +3) — Klammern grenzen jedes Token optisch klarer ab, auch im Mehrfach-Fall
- E: `+G30zu80@15 -VS1400zu280@14` (28, +3)
- F: `+G30→80@15 -VS1400→280@14` (25 Zeichen, aber die GESAMTE SMS inkl. Kopf UND aller anderen Tokens wechselt zu UCS-2 — bei Mehrfach-Ereignis trifft die Kodierungs-Verteuerung ALLE Tokens der Nachricht, nicht nur das eine mit dem Pfeil)

**Zusatzbefund für Zweig b (amtlich), Quelle: Messung der #1929-Sitzung:**
Das 140-Zeichen-Budget kippt im amtlichen Pfad nie sichtbar als abgeschnittener
Text — `_sms_pack` droppt bei Überlauf GANZE Tokens mit `+N`-Marker
(`official_alerts.py:1933-1945`), statt einzelne Tokens zu kürzen. Zeichenkosten
eines längeren Kopfes (z. B. `Ziel:`/`Segment N:` statt des heutigen
`AMT`-Kopfes) zahlen sich dort also nicht in abgeschnittenem Text aus, sondern
in UNSICHTBAR wegfallenden Warnungen — eine Warnung verschwindet ganz, statt
gekürzt zu erscheinen. Gemessener engster Fall aktuell: 118 von 140 Zeichen.
**Konsequenz für die Notations-Wahl in Zweig b:** die Zeichenkosten der
Kandidaten A-F (oben) sind für den amtlichen Zweig nicht nur gegen Lesbarkeit,
sondern gegen diese Dropp-Schwelle zu rechnen — ein teurerer Kandidat (z. B. D
mit +1 bis +3 Zeichen je Token) kann bei mehreren gleichzeitigen Warnungen
dazu führen, dass eine zusätzliche Warnung komplett aus der SMS fällt, die mit
Kandidat A noch hineingepasst hätte. Diese Abwägung gilt zusätzlich zur
Notations-Wahl selbst und ist Teil der PO-Entscheidung in Abschnitt 3, nicht
gesondert zu entscheiden.

**Zusammenfassender Befund (Fakten, keine Vorschlags-Bindung):**
- Kandidat **C** (`-`) scheidet strukturell aus zwei unabhängigen Gründen aus:
  Kollision mit der bestehenden km-Spannen-Notation UND Doppel-Minus bei
  fallenden negativen Werten (Fall 3).
- Kandidat **F** (`→`) löst die Lesbarkeits-Ambiguität am klarsten, hat aber
  eine **Kostenfolge außerhalb der reinen Zeichenzählung**: jedes Vorkommen
  erzwingt UCS-2 für die komplette Nachricht — bei Premium-SMS (Garmin
  inReach, kostenpflichtig je Segment, ADR-0049) eine direkte Mehrkosten-Frage,
  nicht nur eine Geschmacksfrage.
- Kandidat **D** (`alt(neu)`) ist über alle sechs Fälle hinweg konsistent
  GSM-7-günstig (+1 bis +3 Zeichen ggü. A) und zeigt beim schärfsten Testfall
  (Minus-Kollision, Fall 3) das geringste Verwechslungsrisiko aller
  GSM-7-Basis-Kandidaten.
- Kandidat **E** (`zu`) ist bei Buchstaben-Stufen (Fall 4) ohne Leerzeichen
  schwer scannbar, bei Zahlen mit Leerzeichen am teuersten.

### PO-Entscheidung Runde 4: `->` (ASCII-Pfeil), OHNE Vorzeichen-Präfix

**Gewählt: `->`** — zwei GSM-7-Basis-Zeichen (`-` gefolgt von `>`), keiner der
sechs oben studierten Kandidaten wörtlich, aber eine Synthese aus F
(Pfeil-Richtung, Lesbarkeit) und A/B (GSM-7-Sicherheit, kein UCS-2-Trigger).
**Zusätzlich entfällt der Vorzeichen-Präfix `+`/`-` vollständig** — PO-
Begründung: der Präfix trug nur die ZAHLENRICHTUNG, die im Pfeil bereits
steckt, führte aber bei „gut/schlecht" in die Irre (`-TH:H->M` sähe wie eine
Verschärfung aus, ist aber eine Entwarnung; `-SL2200->1400` [Schneehöhe]
sähe entwarnend aus, ist aber eine Verschärfung — das Vorzeichen spiegelte
nie die Handlungsrelevanz, nur die Arithmetik).

**Zielnotation an den sechs Extremfällen:**

| Fall | Neue Notation | Vergleich zu Kandidat A (Ist, mit Präfix) |
|---|---|---|
| Sicht 1.400→280 | `VS1400->280` (11) | **gleiche Länge** wie `-VS1400>280` (11) — Präfix-Wegfall UND Pfeil-Verlängerung heben sich auf |
| Böen 30→80 | `G30->80` (7) | gleiche Länge wie `+G30>80` (7) |
| Temperatur 5→−3 | `D5->-3` (6) | gleiche Länge wie `-D5>-3` (6), **aber nur noch EIN Minuszeichen** vor der 3 statt der Doppel-Minus-Unschärfe aus Fall 3 — der Präfix-Wegfall löst genau das schärfste Problem der Studie |
| Gewitterstufe M→H | `TH:M->H` (7) | gleiche Länge wie `+TH:M>H` (7) |
| Regen 0,2→14,5 | `R0.2->14.5` (10) | gleiche Länge wie `+R0.2>14.5` (10) |
| Mehrfach-Ereignis | `G30->80@15 VS1400->280@14` (24) | 1 Zeichen KÜRZER als `+G30>80@15 -VS1400>280@14` (25) — zwei eingesparte Präfixe, zwei verlängerte Pfeile, Netto-Ersparnis 1 Zeichen |

Diese Notation gilt für Zweig a (Δ-Alarm) direkt. Für Zweig b (amtlich) gilt
zusätzlich der Zusatzbefund oben (Dropp-Schwelle statt Kürzung) — die
Zeichenkosten von `->` (gleich bis günstiger als der Ist-Zustand) wirken sich
dort tendenziell POSITIV aus, nicht negativ.

## 4. Warnstufen-Mapping — PO-Entscheidung: Option 1

Heute: Behörden-Warnstufe ist vierstufig (GRÜN/GELB/ORANGE/ROT,
`_LEVEL_WORDS`, `official_alerts.py:44-48`), die `TH:`-Stufenleiter aus dem
Briefing ist ebenfalls vierstufig (`LEVELS = {0:"-", 1:"L", 2:"M", 3:"H"}`,
`output/tokens/metrics.py:14`). Zahlenmäßig passt 4-zu-4 — die Frage ist,
WELCHE Behördenstufe auf WELCHEN Buchstaben abgebildet wird, und ob dabei
Information verloren geht.

| Option | Mapping | Informationsverlust |
|---|---|---|
| **1 — direkte Übersetzung** | GRÜN→`-`, GELB→`L`, ORANGE→`M`, ROT→`H` | keiner, 1:1 |
| **2 — verschobene Übersetzung** | GRÜN→`-`, GELB→`-`(keine Meldung wert), ORANGE→`M`, ROT→`H` (GELB wird nicht separat gezeigt, da GELB-Warnungen laut heutigem Sicherheits-Filter `MIN_SMS_LEVEL=3` = ORANGE ohnehin nicht per SMS verschickt werden, `hazard_symbols.py:37`) | GELB als eigene Stufe geht in der SMS-Darstellung verloren — deckt sich aber mit dem bereits bestehenden Versand-Filter (GELB wird heute SCHON nicht per SMS verschickt) |
| **3 — Positions-Zahl bleibt zusätzlich sichtbar** | Buchstabe UND Positions-Ziffer, z.B. `M/3` statt nur `M` (analog zur heutigen `GELB1/3`-Notation, nur mit Buchstabe statt Wort) | keiner, aber widerspricht dem Leitsatz „ein Standardformat" teilweise — Zweig b behielte ein eigenes Zusatzelement |

**PO-Entscheidung Runde 4: Option 1 — direkte Übersetzung**, für ALLE
Gefahrenarten (nicht nur Gewitter): GRÜN→`-`, GELB→`L`, ORANGE→`M`, ROT→`H`.
Damit trägt jede Gefahrenart dieselbe vierstufige Leiter wie `TH:` im
Briefing (Regel 4, Abschnitt 2) — GELB bleibt als eigene Stufe `L` sichtbar,
auch wenn der heutige Sicherheits-Filter `MIN_SMS_LEVEL=3` GELB-Warnungen
weiterhin nicht per SMS verschickt (dieser Filter ist unverändert, nur die
DARSTELLUNG einer tatsächlich verschickten Warnung ändert sich).

## 5. Kollisions-Bereinigung

Zwei im Ist-Vokabular gefundene Symbol-Kollisionen (Details: Ist-Vokabular-
Inventur, Kommentare in #1948):

**Kollision 1 — `TH`/`FL`/`W`/`CL` doppelt belegt in zwei getrennten
Registern** (Wetter-Register `metric_catalog.py` vs. Gefahren-Register
`hazard_symbols.py`), mit unterschiedlicher Bedeutung je Register (z. B.
Wetter-`FL` = gefühlte Tiefsttemperatur vs. Warn-`FL` = Hochwasser).

| Option | Beschreibung |
|---|---|
| **1 — Gefahren-Register auf Wetter-Register-Kürzel umstellen, wo eine Entsprechung existiert** | `thunderstorm` trägt bereits `TH` in beiden Registern (keine Änderung nötig für Gewitter, das Zielbild-Beispiel); für `flood`/`wind_gust`/`access_ban` müsste ein NEUES, kollisionsfreies Kürzel gefunden werden — das widerspricht „keine neuen Codes" teilweise, wäre aber auf die drei Kollisionsfälle begrenzt |
| **2 — Kollision bewusst stehen lassen, weil beide Register nie in derselben Token-Position auftreten** | Wetter-Kürzel stehen immer im Δ-/Briefing-Kontext, Gefahren-Kürzel immer nach dem `!`-Präfix (Briefing) bzw. im AMT-Block (heute) — Kontext macht die Bedeutung eindeutig, auch wenn das Zeichen gleich ist |
| **3 — Nur die im Zielbild TATSÄCHLICH zusammentreffenden Kürzel bereinigen** (aktuell nur `TH`, das aber schon identisch ist) | kleinster Eingriff, verschiebt die Bereinigung der übrigen Kollisionen auf einen Zeitpunkt, an dem sie tatsächlich im selben Format zusammentreffen |

**Kollision 2 — Symbol `!` positionsabhängig zweideutig**: Zweig a
Corridor-Token `!{code}{wert}` (`!` VOR dem Code, z. B. `!G55`) vs. Zweig c
Onset-Token `{code}!{minuten}` (`!` NACH dem Code, z. B. `TH!8`).

| Option | Beschreibung |
|---|---|
| **1 — löst sich durch das Zielbild selbst auf** | Zweig c wechselt laut Zielbild (Abschnitt 1) von `TH!{minuten}` auf `TH@{Uhrzeit}` — das `!`-Symbol verschwindet aus Zweig c vollständig, die Kollision entfällt ohne eigene Entscheidung |
| **2 — zusätzlich Corridor-Token (Zweig a) umbenennen** | falls der PO das verbleibende `!` in `!G55` (reiner Grenzwert-Alarm, kein Δ-Vergleich) ebenfalls für missverständlich hält — bislang keine PO-Beschwerde dazu vorliegend |

**Empfehlung des Planers (keine Bindung):** Kollision 2 löst sich durch das
ohnehin beschlossene Nowcast-Zielbild von selbst — keine gesonderte
Entscheidung nötig. Kollision 1 ist am Zielbild-Beispiel (nur `TH` betroffen)
bereits kollisionsfrei; Option 3 vermeidet, ungefragt neue Kürzel für Fälle
einzuführen, die noch nicht zusammentreffen.

## 6. Verhältnis zu #1929 — PO-Entscheidung: mitlaufen lassen (Option 1)

#1929 (läuft aktuell separat, ändert `official_alerts.py:1896-2104`,
`_tag_time`/`render_official_alert_sms`, Spec freigegeben, TDD-RED-Stand laut
letztem Stand) baut eine Korrektur INNERHALB des heutigen amtlichen
Sonderformats (Minuten-Suffix, Kalendertag im Ganztags-Token). Dieses Konzept
ersetzt das gesamte amtliche SMS-Format perspektivisch (Abschnitt 1, Zweig b).

| Option | Beschreibung | Konsequenz |
|---|---|---|
| **1 — #1929 zuerst ausliefern, danach umbauen** | #1929 liefert seinen kleinen, bereits spezifizierten Fix aus; Scheibe „Zweig b Zielbild" (Abschnitt 8) baut danach auf dem #1929-korrigierten `_tag_time` auf, soweit dessen Grundlogik (Zeitfenster-Berechnung, nicht die Darstellung) weiterverwendet wird | kein verlorener Aufwand — #1929 behebt einen Datenkorrektheits-Bug (Melde-Zeitraum ≠ Anzeige-Zeitraum), unabhängig vom Anzeigeformat |
| **2 — PO stoppt #1929, Zweig-b-Zielbild-Scheibe übernimmt beides** | vermeidet, `official_alerts.py` zweimal kurz hintereinander anzufassen | die #1929-Sitzung hat bereits Spec + TDD-RED-Vorarbeit investiert, die verfallen würde; #1929 behebt zusätzlich einen Bug, der unabhängig vom Format besteht (falsche Zeitraum-Zuordnung bleibt bestehen, wenn nur gewartet wird) |

**PO-Entscheidung Runde 4 (formal bestätigt): Option 1 — #1929 läuft
mit.** #1929 liefert seinen Fix an der Zeitraum-BERECHNUNG aus, bevor Zweig-b-
Zielbild-Scheibe (Abschnitt 8, S5) die DARSTELLUNG umbaut — kein verlorener
Aufwand, kein Doppel-Zugriff auf dieselben Zeilen zur gleichen Zeit.

## 7. Wiederholungs-Signal — gestrichen (PO-Entscheid, zur Dokumentation)

Frühere Konzept-Fassungen sahen ein sichtbares „neu/wiederholt"-Signal in der
Nachricht vor (frühere Kommentare in #1948, Scheibe S4). PO-Entscheid Runde 3:
**gestrichen.** Begründung: reine Wiederholungen werden bereits heute nie
gesendet (Entprellung/Dedup existiert in allen drei Zweigen, s.
Ist-Vokabular-Inventur). Jede tatsächlich gesendete Nachricht IST per
Definition eine Änderung und zeigt das bereits über ihren Inhalt (z. B.
`M>H` — der Stufensprung selbst ist der Beweis der Neuigkeit). Eine doppelte,
inhaltlich identische Zustellung wäre ein Bug, kein normaler Fall — dessen
Nachweis führt das Debug-Protokoll aus Scheibe S1 (Abschnitt 8), nicht ein
zusätzliches Nachrichten-Element. Damit: **kein neu erfundenes Element** in
diesem Konzept, wie vom PO gefordert.

## 8. Scheiben-Reihenfolge — PO-Entscheidung Runde 4: Debug zuerst

> **PO-Vorgabe, wörtlich:** „Debug ist der erste Schritt, um schon mal Daten
> zu sammeln." Die Reihenfolge ist damit NICHT mehr „schnellster sichtbarer
> Fix zuerst", sondern **Beobachtbarkeit vor Korrektur**.

**Leitprinzip (als Satz ins Dokument, gilt für S3 und alle Folgescheiben):**
Jede Format-Scheibe ab S3 wird mit ECHTEN, in S1 aufgezeichneten Meldungen
verifiziert, die über S2 (Testmeldungs-Einspeisung) reproduzierbar in die
Renderer eingespeist werden — nicht nur mit von Hand konstruierten Fixtures.
S1 liefert die Rohdaten, S2 den Einspeisungsweg, S3+ nutzen beides als
Verifikations-Grundlage zusätzlich zu den üblichen Unit-Tests.

| # | Inhalt | Umfang | Status |
|---|---|---|---|
| **S1 — Debug-Eingangs-Protokoll** | Rollierendes Protokoll des rohen Eingangszustands aller drei Alarm-Zweige. Einhängepunkte: Zweig b (amtlich) **direkt am API-Eingang** `warn_egress.cached_fetch` (`geosphere_warn.py:99`, deckt GeoSphere+MeteoAlarm+DPC); Zweig a (Δ) nach der Delta-Berechnung, vor `_send_alert` (`trip_alert.py`, ~Zeile 352); Zweig c (Nowcast) vor `_derive_result` (`radar_service.py`, ~Zeile 167-210). Retention-Vorlage `WeatherSnapshotService._prune_dated_snapshots` (`weather_snapshot.py:165`). Antwort auf #1458 E6/B3. Details: neue Spec, Abschnitt „Nächster Schritt" unten. | 3-4 Dateien | **spec-bereit, nächster Schritt** |
| **S2 — Testmeldungs-Einspeisung** | `/api/trips/{trip_id}/alert-preview` um dritten Payload-Typ (amtliche Warnung) erweitern, analog `OnsetPayload`/`ChangePayload`. Nutzt S1-Aufzeichnungen als Eingabequelle für reproduzierbare Testläufe. | 2-3 Dateien | folgt S1 |
| **S3 — SMS-Sofortfix** | Δ-Alarm-SMS (Zweig a): Vergleichszeitpunkt-Präfix (`@HH:MM`) komplett aus dem Kopf entfernen (löst #1948-Auslöser-Bug UND #1939 strukturell, s. Abschnitt 1); `->`-Notation ohne Vorzeichen-Präfix einführen (Abschnitt 3); `LEVELS`-Stufenbuchstaben in `_sms_token()` verdrahten. **Ersetzt die alte, jetzt obsolete Spec `fix_1948_1939_alarm_sms_referenzzeitpunkt.md` vollständig** — deren Notations-ACs (`@HH:MM`-Umformulierung) sind durch „entfernen statt umformulieren" überholt. Verifiziert an ECHTEN S1-Aufzeichnungen sobald verfügbar (Leitprinzip oben), sonst an Fixtures. | 1 Datei + Tests | folgt S1/S2 |
| **S4 — Zweig-c-Zielbild (Nowcast)** | `_render_sms_onset` auf `format_alert_location`/`_km_str`-Kopf umstellen, Token von `TH!{min}` auf `TH@{onset_time}` (Feld existiert bereits, Regel 5). Löst Kollision 2 (Abschnitt 5) nebenbei auf. **Leitplanke (aus #1599, Prod `ba1bec92`):** `src/app/day_window.py` trennt bewusst Alarm-Fenster (Alarm-Randstunde 19-20 Uhr wird bewertet) von Anzeige-Fenster (`display_end_time()` nimmt die Alarm-Zusatzstunde für Stundentabelle/Kopfzeilen/Kurzformen zurück, bewacht durch `tests/unit/test_ziel_segment_anzeige_invarianz.py` AC-10–18). Ein Umbau der Kurzform-Ausgabe darf die Alarm-Randstunde NICHT in die Anzeige ziehen — `display_end_time()` ist die Trennstelle. | 1 Datei + Tests | folgt S3 |
| **S5 — Zweig-b-Zielbild (amtlich)** | `render_official_alert_sms` auf gemeinsamen Kopf umstellen, Warnstufen-Mapping Option 1 (Abschnitt 4) verdrahten, Wochentag-Regel (Regel 2) ergänzen, kein Trip-Präfix mehr (Regel 1). Startet NACH #1929 (Abschnitt 6, PO-Entscheid: mitlaufen lassen). | 1-2 Dateien + Tests | folgt #1929-Auslieferung |
| **S6 — Telegram-Parität** | Prüfen, ob Telegram nach Wegfall des SMS-Vergleichszeitpunkts (S3) noch einen eigenen Angleich braucht — offene Detailfrage, s. u. | klein | folgt S3 |
| **S7 — E-Mail-Struktur (#1737)** | Δ-Alarm-E-Mail auf Briefing-Stundenzeile/Stufen-Darstellung umstellen. Eigene, größere Initiative, NICHT Teil dieses Dokuments im Detail — nur als Folge-Scheibe vorgemerkt. | größer, eigene Spec | eigenständig |

**Offene Detailfrage für S6 (nicht vom PO entschieden, da erst durch S3
entstanden):** Bisher war „Telegram zeigt `reference_at` gar nicht, E-Mail
zeigt ihn als vollständigen Satz" eine Paritäts-Lücke. Da S3 den
Vergleichszeitpunkt jetzt auch aus der SMS entfernt (Abschnitt 1), ist offen,
ob Telegram (a) dem NEUEN SMS-Verhalten folgt (auch keinen
Vergleichszeitpunkt mehr zeigt) oder (b) beim E-Mail-Verhalten bleibt
(voller Satz, da Telegram kein Zeichenlimit hat). Wird in der S6-Spec als
Entscheidungsfrage vorgelegt, nicht hier vorentschieden.

**Entfallen aus dem vorherigen Konzept-Stand:** die separate „Frage 1 /
Wiederholungs-Signal"-Scheibe (jetzt Abschnitt 7, gestrichen).

## 9. Bauteile-Inventur — was existiert, was fehlt (Zusammenfassung)

| Baustein | Existiert? | Fundstelle |
|---|---|---|
| `LEVELS`-Stufenbuchstaben (`-`/`L`/`M`/`H`) | ✅ existiert, ungenutzt in `_sms_token()` | `output/tokens/metrics.py:14` |
| `format_alert_location`/`_km_str`-Kopf | ✅ existiert für Zweig a, fehlt für b/c | `render.py:787` |
| `OnsetEvent.onset_time` (konkrete Uhrzeit) | ✅ existiert, ungenutzt in `_render_sms_onset` | `model.py:41`, genutzt in `render.py:227,282,330` |
| Segment-Projektion amtlicher Warnungen | ✅ existiert für Trip, fehlt für Compare (zurückgestellt) | `trip_alert.py:1570-1596`, `official_alerts.py:2120-2179` |
| Wetter-Register (`TH:` etc.) | ✅ existiert, EIN Quell-Ort | `metric_catalog.py` |
| Gefahren-Register (`TH` ohne Doppelpunkt) | ✅ existiert, GETRENNTER Quell-Ort | `hazard_symbols.py` |
| Warnstufen→Buchstaben-Mapping | ❌ existiert nicht, PO-Entscheidung Option 1 liegt vor | — (Abschnitt 4) |
| Notation für Von-Bis-Änderung | ✅ entschieden: `->` ohne Vorzeichen-Präfix | Abschnitt 3 |
| Debug-Eingangs-Protokoll (alle 3 Zweige) | ❌ existiert nicht, Mount-Points identifiziert | Abschnitt 8, S1 |

## Konzept-Historie

- 2026-08-17: v1/v2 (Kommentare in #1948) — Wurzelbefund, Issue-Landkarte,
  Positionierung zu #1458.
- 2026-08-17: S1-Spec `fix_1948_1939_alarm_sms_referenzzeitpunkt.md`
  geschrieben, danach vom PO pausiert (Grundsatzrunde gefordert).
- 2026-08-17: Ist-Vokabular-Inventur (Kommentare in #1948).
- 2026-08-17: v3 (dieses Dokument) — Leitsatz „Format folgt dem Phänomen",
  Notations-Studie, Warnstufen-Mapping und Kollisions-Bereinigung als
  Entscheidungsfragen, Wiederholungs-Signal gestrichen.
- 2026-08-17: PO-Runde 4 — alle Entscheidungsfragen beantwortet: Notation
  `->` ohne Vorzeichen-Präfix, Warnstufen-Mapping Option 1, #1929 läuft mit,
  Vergleichszeitpunkt entfällt aus der SMS vollständig, Scheiben-Reihenfolge
  auf „Debug zuerst" umgestellt (S1 Debug-Protokoll, S2 Testmeldungs-
  Einspeisung, S3 SMS-Sofortfix, S4+ Format-Konsolidierung je Zweig).
  Ergänzungen #1493-Sitzung: `@`-Regel (Regel 5), Briefing-SMS als lebende
  Referenz-Implementierung, Aufgabenteilung zu #1458 dokumentiert. Dokument
  gilt als freigegeben; alte S1-Spec obsolet markiert.
