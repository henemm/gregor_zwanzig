# Kontext und Analyse #3258: SMS-Kürzel-Legende und SMS-Beispielwerte im Reiter Wetter

Refs #2913, #3250. Keine Produktänderung; nur Abgleich Elementliste, Mockup, Besitzer.

## 1. Live-App
- Legende: `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` Z. 211-218 (`Aufklapper` „Kürzel erklärt“, `<dl class="wsw-legende">`, je Eintrag `<dt>` Kürzel, `<dd>` Bedeutung). Titel: Katalog `wetter.wsw.legende.titel`.
- SMS-Beispielzeile: dieselbe Datei Z. 203-208 (`was-steht-wo-sms`), Katalog `wetter.wsw.sms.beispiel`/`.zeichen`, Text kommt aus `antwort.sms_example` (Server rendert die echte SMS aus dem Prüf-Trip).
- Aufbereitung: `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts`: `smsAus` Z. 133, `legendeAus` Z. 153.
- Werte-Herkunft: Kürzel und Bedeutung der Metriken (FN „N gefühlt“, FL „L gefühlt“, FD „D gefühlt“, TH, VS, FZ …) kommen aus der API-Antwort `legend.metrics[].kuerzel/meaning` (Server-Katalog, nur Metriken mit SMS-Haken). Feste Einträge (`legend.fixed`) werden über Katalog `wetter.wsw.legende.*` in `de|en/wetter.json` Z. 175-184 übersetzt (Stufe gelb/orange/rot, „amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr“, Warnung Wind, Warnung Starkregen, Lawinenstufe, Warnquelle nicht erreichbar) oder bringen die Bedeutung selbst mit (`O1`). Also: Kürzel/Bedeutung Server-Daten, feste Beispielwarnung Katalog, SMS-Werte (FN12, FD12/16) berechnet aus Prüf-Datensatz.
- Orte: gilt gleich. Dieselbe Karte (`context="route"|"vergleich"`, ADR-0104-Teilung). Bericht zeigt Orte nur mit Legendenkopf, Beispielwarnung und Warntexten (keine FN/FD-Werte, da Orte-SMS andere Token nutzt).

## 2. Mockup Fassung 4 (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`)
- KEINE Kürzel-Legende (kein „Kürzel erklärt“, keine Warnungs-Beispiele).
- SMS-Bezogenes vorhanden: Beispielzelle je Kanal in der Tabelle (`exCell` Z. 597, SMS-Token Trip Z. 556-571, z. B. `wind_chill: 'TF- FN7 FD7/12'`, Orte Z. 548-555), SMS-Beispielzeile `budgetZeile` Z. 611-613 („SMS-Beispiel: … · n von 160 Zeichen“), Kommentar Z. 536-537 „Beispielwerte sind echte Renderer-Ausgabe“, Telegram-Kurzstil/Premium-SMS in `kanalEinst` Z. 603-604, Wetter-Karte `was-steht-wo` Z. 650-658.
- Folge: SMS-Beispielzeile ist im Mockup abgedeckt (Mockup-Werte `FN7 FD7/12` weichen von Live `FN12 FD12/16` nur datensatzabhängig ab); die Legende fehlt.

## 3. Elementliste und Abgleich (Berichte stg3251 DE/EN, Trip + Orte, Reiter Wetter, Status `zusaetzlich`, Besitzer leer)
- DE Trip: „FN12“, „FD12/16“, ganze SMS-Zeile „Port d'And D14/18 … TF- FN12 FD12/16 …“, „Kürzel erklärt“, Kürzel „FN“/„FD“ (und als Fließtext „N gefühlt“, „D gefühlt“, „gefühlt“), „amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr“, „Warnung Wind“, „Warnung Starkregen“. DE Orte: „Kürzel erklärt“ + dieselben drei Warntexte.
- EN Trip: zusätzlich „TF- FN12 FD12/16“, „Abbreviations explained“, „official warning: thunderstorm, level high, from 2 pm“, „wind warning“, „heavy rain warning“, „warning source unreachable“. EN Orte: dieselben ohne SMS-Werte.
- Zusätzlich im Live, aber nur als Textknoten ohne Bezug zur Legende: Kürzel W, G, PR, R, TF, TH, TH+, VS, FZ, UV, SL, CL, N, AV4 u. a. (DE und EN, Teil der Legende, mit „zusaetzlich“).
- Bisherige Lösungen (`docs/context/einstellungen_neu/elementliste_besitzer.json`): Einträge mit `art: "zusaetzlich"` und `muster` (Platzhalter `{zahl}`, `{count}`, `{zeit}`, z. B. „{count} Kandidaten“, „{datum} · {etappen} · {km} km · ↑{hm} m“, „Fahrrad ({zahl} km/h)“), Pflichtfelder `grund` und `verweis` (`#NNNN`) bzw. in `ausnahmen` `grund` und `spec`. Datensatzabhängiges: „Mockup-Beispieldaten, hängt vom Prüf-Datensatz ab …“ mit Verweis `#2913`. #3251 (Abweichungszahl): kein Muster, sondern eigener Mockup-Zustand `vorlage-abweichung`, im Abgleich an Datensatz `mit_abweichung` gebunden (Tech-Lead-Entscheidung 21.11., Option B).

## 4. Vorgeschichte
- #1660 (PO 9.8.): „ALLE Metriken für SMS einstellbar … genauso wie bei E-Mail und Telegram“; alle 14 fehlenden Metriken bekommen SMS-Token (FN/FD u. a.); „KEINE neue Fläche bauen“. Live seit Prod `39ba8a00`.
- #1728 (PO 11.8.): Tages-Tief/Hoch als eigene Größen mit Kürzeln K/D/FK/FD; „Vollmail zeigt immer die Spanne, keine Wahl“; Tief/Hoch sinnvoll für „SMS/Kurzform/Vorschau“.
- Zur Legende selbst gibt es keine eigene PO-Entscheidung in den gelesenen Texten; #3258 nennt sie „PO-gewollt (SMS-Kürzel #1660/#1728)“. Quelle: Live-Stand seit Spec ADR-0124 „Was steht wo“, nicht gegen das Mockup entschieden.
- Epic #2913 / ADR: Jede Abweichung Mockup gegen Staging „bekommt einen Besitzer (Sub-Issue, Issue oder Freigabe), nie ‚kommt später‘“; Ziel: Elementliste lückenlos DE+EN, Ganzseitenbild ohne Abweichung ohne Besitzer. ADR-0112 (docs/adr/0112-…) behandelt nur „Oberflächen nur aus Design-System-Bausteinen“ (Wächter, Ausnahme `audit:exempt` mit Begründung); „Mockup ist Soll“ steht in #2913. App-Elemente ohne Mockup-Pendant sind nirgends ausdrücklich geregelt, nur der Besitzer-Mechanismus.

## 5. Optionen
- A: Legende („Kürzel erklärt“ mit Kürzeln und festen Beispielen) im Mockup ergänzen, nach dem Muster der App (Aufklapper unter der SMS-Zeile), Beispielwerte (FN12, FD12/16, ganze SMS) als `muster`/Prüf-Datensatz-Besitzer führen. Aufwand mittel: Mockup (JS, Katalog-Texte DE/EN) plus Generator-Elemente, Besitzer-Einträge, Abgleich neu in DE/EN; Risiko: Mockup ist PO-freigegeben, Änderung ohne PO-Wissen; Mockup-Werte hängen an Fachkatalog (Kürzel wie A14/O1 sind Server-Daten), Drift droht.
- B: Als begründete Ausnahme mit Besitzer belassen (`zusaetzlich` mit `muster` für Warntexte und datensatzabhängige Werte, `verweis` #3258). Aufwand klein (nur `elementliste_besitzer.json`); Risiko gering, Mockup bleibt hinter der App zurück (Mockup-Soll nicht vollständig).
- C: Mischform: Legende bewusst ins Mockup, Beispielwerte (FN12, FD12/16, SMS-Zeile) nur als Muster/datensatzabhängig führen. Größter Nutzen, aber Aufwand wie A.
- Empfehlung Tech Lead: C (Legende als eigener Mockup-Abschnitt nach App-Muster, Werte datensatzabhängig). Ersatz bei Zeitdruck: B.
- PO-Entscheidung: Ja, einmalig, per AskUserQuestion: Die Legende ist live PO-gewollt, aber ob das Mockup (Soll) sie zeigen soll, ist offen und ändert das freigegebene Soll. Für die Beispielwerte reicht Tech-Lead-Entscheidung (datensatzabhängig, Präzedenz „Mockup-Beispieldaten, hängt vom Prüf-Datensatz ab“).
