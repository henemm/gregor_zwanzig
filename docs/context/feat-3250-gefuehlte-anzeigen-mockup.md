# Kontext und Analyse #3250: Gefühlte-Temperatur-Anzeigen im Reiter Wetter (Trip) gegen Mockup Fassung 4

Refs #2913, #3151, #3204 (direktes Vorbild), #1660, #1728. Nur Analyse, kein Code.

## 1. Herkunft im Code
- Register `src/app/metric_catalog.py`: `wind_chill_night` (Z. 299, Kürzel FN/TFN, #1660 Scheibe A, Commit 94a38b181, 2026-08-09, PO-Anfrage vom selben Tag: "Gefühlte Temperatur soll dieselbe Behandlung bekommen" wie Nacht/Tages-Tief), `wind_chill_day_low` (Z. 323, FL) und `wind_chill_day_high` (Z. 335, FD), beide #1728 Scheibe 1 (c18f8eb7c, 2026-08-15; PO-Beobachtung 11.08.: "Gilt auch für gefühlte Temperatur"). Alle drei: **kein** `trip_default_rank`, keine `summary_fields`, keine Alarm-Deklaration; reine Sichtbarkeits-Gates für die SMS-Token FN/FL/FD. EN-Labels `metric_catalog.py:994-996` (#2662).
- Einstufung "nur Anzeige": `_REITER_WETTER` (Z. 1311-1313): `("temperature", False, None, True)` = Gruppe Temperatur, nicht alarmfähig, keine Ampelseite, display_only. Seit #2794 S3a; Reihenfolge-Rang #2955.
- Ableitung: `src/app/loader.py:970-977` `_DERIVED_METRIC_RULES` und Spiegel `frontend/.../trip-detail/metricsEditor.ts:318` (#2454): die drei Kinder hängen ausschließlich am `enabled` der Elternmetrik `wind_chill` (Gefühlte Temperatur). Ist sie an, sind sie an.
- Wirkung: Mail-Tabellenspalte nein; SMS/Telegram/Premium-SMS ja (Token FN, FL, FD, siehe Live-Zeilen "FN12 FD12/16", Kürzel-Legende). Orts-Vergleich: nein, Gehzeit-/Nachtgrößen sind dort bewusst nicht angeboten (ADR-0011, #2944).
- PO-Wunsch: ja, ausdrücklich (#1660, #1728), also Nutzerfunktion, kein Altlast-Rest.

## 2. Warum das Prüfkonto sie aktiv zeigt
`scripts/staging_pruefkonto_mockupdaten.py` (Z. 69-72, 253-254) legt nur die Mockup-Metriken fest, darunter `wind_chill` (an). Die drei Kinder stehen nicht im Skript; sie entstehen beim Laden/Editieren automatisch aus der Elternregel (`wind_chill` an => FN/FL/FD an). Es ist also das Standardverhalten der App, nicht eine Prüfkonto-Besonderheit. Das erklärt den Zähler: Live "9 von 18 … 8" = Mockup "9 von 15 … 5" plus 3 Nur-Anzeige-Zeilen (alarmfähig bleiben 9). Die zwei gemessenen Gehzeit-Zeilen (`temperature_day_low/high`) sind seit #3204 im Mockup und deshalb schon in den 15.

## 3. Live-Einträge im Abgleichbericht (Trip, Reiter wetter, `zusaetzlich`, ohne Besitzer)
Quelle: `/tmp/claude-1000/-home-hem-gregor-zwanzig/7a8960eb-7126-4b2a-86ef-33b398712053/scratchpad/st3205/{de,en}/bericht.json`
- Metrik-Namen (je 3): DE "Gefühlte Tiefsttemperatur Nacht" (zus:trip/wetter/f9a9e721a201), "Gefühlte Tages-Tiefsttemperatur (Gehzeit)" (b7a06860cdb0), "Gefühlte Tages-Höchsttemperatur (Gehzeit)" (9e6bde1a9872); EN "Feels-like night low" (1b467b1e64b5), "Feels-like daytime low (walking hours)" (7d138ed2ffa6), "Feels-like daytime high (walking hours)" (fe8658d3ba84).
- Untertitel, Zeilenmitte und Erklärsatz der drei Zeilen tauchen NICHT als eigene Einträge auf: Der Bericht dedupliziert nach Text, und dieselben Texte ("°C · nur Anzeige, keine Ampel", "keine Ampel, nur Anzeige", "Nur Anzeige: …") sind seit #3204 für die Gehzeit-Zeilen als Besitzer-Einträge geführt (bzw. durch Windrichtung im Mockup gedeckt). Nach dem Mockup-Ergänzen entfallen sie nicht neu, sie werden nur hier mitgedeckt.
- Was-steht-wo / Kürzel-Zeilen (SMS-Beispiel "FN12 FD12/16", Legende "FN … N gefühlt" / "FL … L gefühlt" / "FD … D gefühlt", DE+EN; ids 63a5f58a3b19, 287762483392, 280c80844f01 und Texte 51626fabd2e8, 57cfaafb99c3, 366e90c14b80, EN f871c056ad10, 663aea05253e, 115e5ff97166; Beispiel 8c2e35afc66e, 4 weitere "FN12"/"FD12/16" b4c3d324a6bb, 5c8d5febad74) stehen ebenfalls als `zusaetzlich`. Sie gehören zur SMS-Kurzform und teils zum Beispiel-Block (#3205/#3122-Linie); die Kürzelzeilen FN/FL/FD folgen dem Mockup, wenn dieses die drei Metriken kennt (SMS-Beispiel dort ist Mockup-Rechnung, daher dort prüfen).
- Zähler: Der Satz "9 von 15 Metriken lösen einen Alarm aus. 5 können keinen auslösen" steht im Mockup als `gefunden` (Z. 507: nAl von onM.length). Live kommt 18/8; der Bericht führt ihn als `gefunden` (Textform gleich). Nach Option A ist Mockup 18/8 und der Wert gleich.

## 4. Frühere PO-Entscheidungen
#1660 (PO 09.08.): gefühlte Nacht/Tief/Hoch einzeln wählbar. #1728 (PO 11.08.): Tages-Tief/-Hoch als eigene Größen, ausdrücklich auch gefühlt. #2454: Kurzform zeigt gewählte gefühlte Temperatur. #3204 (erledigt): gleiche Frage für gemessene Gehzeit-Temperaturen, Entscheidung A. #2867 (offen) betrifft nur die Vorboten-Markierung. Kein Beschluss "gehört nicht in den Reiter" gefunden.

## 5. Optionen
- **A: Mockup ergänzen** (Gruppe Temperatur hinter "Gefühlte Temperatur": Nacht, Tages-Tief, Tages-Hoch; an, nur Anzeige, Untertitel "°C · nur Anzeige, keine Ampel"; Zähler im Mockup 18/8). Keine Funktion verloren, keine Migration, löst 6 Namen plus Folgezeilen auf.
- **B: aus Reiter entfernen.** Nimmt PO-beauftragte Wahl (#1660/#1728) und die SMS-Token FN/FL/FD weg, Bestandstrips verwaisen; abzulehnen.
- **C: Mischform** (im Reiter hinter Aufklapper/nur unter "Nicht im Briefing"): Mehraufwand ohne Gewinn; Mockup-Zeilenform `m[11]` trägt es schon.

## 6. Empfehlung (Tech Lead)
**A**, analog #3204. Die Ableitung aus `wind_chill` ist das gewollte Standardverhalten, das Mockup ist ein Auszug. Reihenfolge nach `_REITER_WETTER`: Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte, Gefühlte Nacht, Gefühlte Tages-Tief, Gefühlte Tages-Hoch. Abgleich mit Soll/Ist-Bild an Henning.
**Produktentscheidung des PO nötig: nein** (Funktion durch #1660/#1728 festgelegt, Nur-Anzeige-Form durch das Mockup selbst). Unabhängig davon bleibt #3091 (Gehzeit gegen Tagesfenster) offen.
