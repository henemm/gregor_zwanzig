# #3151 Teil C: Klassifizierung der 247 `#2967`-Besitzer-Einträge (Stand 2026-11-20)

Quelle: frische Abgleich-Berichte nach dem Seed mit Kanalauswahl (`abgleich-de.json`, `abgleich-en.json`,
voller Umfang, je Exit 0, Schreib-Tripwire 0, Leckprüfung grün). Die Besitzerliste ist **nicht** verändert;
je Eintrag stehen Status DE/EN, Klasse und Gruppe in `klassifizierung-2967.json`.

Regeln der Auswertung:
- **element** (103): Status des Eintrags im Bericht je Sprache. A = DE gefunden und EN gefunden; DE gefunden und
  EN-Lücke („kein Katalogtext“, Kandidat #3194) zählt ebenfalls als A (Gruppe „EN-Lücke“).
- **zusaetzlich** (142, Text/Muster): A = in keinem der beiden Berichte trifft noch ein zusätzlicher Live-Text
  (Matching wie `trifftZiel` der Abgleich-Logik); B = trifft in DE und/oder EN weiter.
- **abschnitt** (2, `metriken` Trip/Orte): A nur, wenn alle Elemente des Abschnitts gefunden; sonst B (aufteilen).

## Zahlen

| Klasse | Anzahl |
|---|---|
| A aufgelöst | 181 (179 + 2 EN-Lücke „Mallorca Frühling“ im Trip, DE gefunden) |
| B echte Abweichung | 66 |

A nach Ort: Zustellung Kanäle 70 (u. a. „Briefings über 2 Kanäle · Alarme über 4 Kanäle“, „Alarme über
Telegram/SMS/Premium-SMS“, Stufen gering/mittel/hoch: durch die Kanalauswahl jetzt gefunden), Zustellung
zusätzlich 19, Laufzeit 4, Wetter zusätzlich 86 (Metrik-Zeilen der Kontovorlage), Trip-Vorlagen-Auswahl 2.

| Gruppe (B) | Anzahl |
|---|---|
| Kanalzeile Zustellung | 23 |
| Grünbereich „· grün:“ | 14 |
| Anzeige-Metriken (Trip) | 10 |
| nur-EN-Zusatztexte | 6 |
| gesperrt-Grund | 4 |
| Abschnitt `metriken` (aufteilen) | 2 |
| sonstige (Kein-Alarm-Hinweis) | 2 |
| Vorlagen-Auswahl Orte | 2 |
| alpen-trekking Skala/Zurücksetzen | 2 |
| „:00“ | 1 |
| Gewitter-Stufen, Vorbote | 0 als eigener Eintrag (stecken im Abschnitt `metriken`, s. u.) |

## Gruppen mit Beispielen (DE-Soll laut Mockup vs. Ist auf Staging)

**Kanalzeile Zustellung (23, Trip+Orte, Zustände normal/lädt/fehler/lücken)**
- Soll „bestätigt · henning@… · +1 Empfänger“ vs. Ist „bestätigt · `<Prüfkonto-Adresse>`“ (Adresse voll, ohne „+1 Empfänger“).
- Soll „verbunden · `@henning`“ vs. Ist „verbunden · 2967000001“ (Chat-ID statt Telegram-Name).
- Soll „bestätigt · +49 171 …“ vs. Ist „bestätigt · +491713920967“ (Nummer ungekürzt).
- Zustand „lücken“: Soll „unbestätigt · +49 171 …“, „inReach · Rückadresse verfallen“ vs. Ist nicht gefunden.

**Grünbereich „· grün:“ (14, je 7 Muster DE und EN)**
- Soll „· grün: 2 bis 27 °C“ (Trip) vs. Ist „grün: 2 bis 27 °C“ als eigener Text ohne Element (auch „0 bis 28 °C“ Orte).
- Soll „· grün: bis 30 km/h“ vs. Ist „grün: bis 30 km/h“; EN „green: up to 30 km/h“ ebenso zusätzlich.

**Anzeige-Metriken Trip (10, DE+EN)**
- Ist zusätzlich „Tages-Tiefsttemperatur (Gehzeit)“, „Tages-Höchsttemperatur (Gehzeit)“ (EN „Daytime low/high (walking hours)“); im Mockup nicht vorhanden.
- Ist zusätzlich „°C · nur Anzeige, keine Ampel“, „keine Ampel, nur Anzeige“, „Nur Anzeige: keine Ampel und kein Alarm. …“ (EN analog).

**nur-EN-Zusatztexte (6)**: „Cloud cover“, „Rain probability“, „UV index“, „mm · total“, „°C · daily high · daily low“,
„m · minimum“ (Trip) sind in EN zusätzlich sichtbar, die DE-Gegenstücke sind aufgelöst (Kandidat #3194).

**gesperrt-Grund (4)**: Soll „gesperrt“ (Zustand „lücken“, je 2 Zeilen Trip/Orte) vs. Ist nicht gefunden
(Kandidat #3122 „gesperrt: {grund}“; die Muster-Regel selbst trifft nicht mehr).

**Abschnitt `metriken` (2, Trip/Orte)**: DE 28/294 (Trip) bzw. 24/196 (Orte) Elemente abweichend, EN 54 bzw. 50
(davon 8 bzw. 6 EN-Lücke, 14 bzw. 18 „+ Metrik“ nicht prüfbar). Aufteilung DE je Abschnitt: Grünbereich 16/12,
Skala-Zahl „-10“/„-15“ 2/2, Alarm-Text in anderer Reihenfolge („Alarm, wenn der Wert … über 30 °C steigt“ vor
Element Nr. 12) 2/2, **Gewitter-Stufen** „keins/mittel/hoch“ 6/6, **Vorbote** („Nur im Briefing gefärbt. Vorboten
lösen keinen Alarm aus.“ vor Element Nr. 105) 2/2.

**Vorlagen-Auswahl Orte (2)**: Soll „Mallorca Frühling“ (eigene Vorlage) vs. Ist im Orts-Vergleich nicht gefunden
(DE abweichend, EN „kein Katalogtext“); im Trip gefunden.

**alpen-trekking Skala/Zurücksetzen (2)**: Ist zusätzlich „Auf "Alpen-Trekking" zurücksetzen“ bzw.
„Reset to "Alpine trekking"“ (Trip); in der Elementliste ohne Eintrag.

**sonstige (Kein-Alarm-Hinweis, 2)**: Ist zusätzlich „Kein Alarm. Die Farbe erscheint nur im Briefing.“ /
„No alert. The colour only appears in the briefing.“ (Orte).

**„:00“ (1)**: Ist zusätzlich „:00“ (Trip und Orte, DE und EN) neben der Uhrzeit-Auswahl.
