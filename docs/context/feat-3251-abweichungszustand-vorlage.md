# Kontext und Analyse #3251: Abweichungszustand der Vorlagenkarte

## Befund
- Mockup (docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html Z. 494/516/517): `devs` ist KEIN Zustandsschalter (`data-zst` kennt nur normal, laedt, fehler, luecken), sondern Bedien-Zustand je Seite. Er steigt bei Klick auf Metrik an/aus (`data-rm`/`data-add`, Z. 767/768), Grenzen (Z. 784/786), Alarm (Z. 782) und Dialog (Z. 800). Ab `devs>0` zeigt die Karte "▾ N Abweichung(en)" und "Auf „{vorlage}“ zurücksetzen".
- Live: VorlageKarte.svelte `abweichungen > 0` (Z. 59, 79, 161), gleiche Bedingung.

## 1. Generator (scripts/elementliste_aus_mockup.ts)
- ZUSTAENDE = normal, laedt, fehler, luecken (Z. 586), je Kontext (trip, orte) und Reiter ein frischer Seitenaufruf (`frisch`, Z. 629) mit Klick auf `data-zst`. Ein dritter Seiten-Zustand "abweichung" verdoppelte die Seite (alle Reiter x 2 Kontexte x 1 Zustand) und ist unnötig, weil `devs` Bedienzustand ist.
- Der Generator kennt bereits Script-Zustände INNERHALB des Wetter-Reiters (Z. 640-690: `grenzen-<id>` nach Klick auf `data-edit`, `vorlage-auswahl`, `vorlage-bestaetigung`, `vorlage-speichern`, `vorlage-speichern-fehler`), gelesen mit `lies(..., { nur: '<abschnitt>' })`. Ein Abschnitt "vorlage-abweichung" (frische Seite, eine Metrik per `data-rm` abwählen, dann `#content` mit `nur: 'vorlage-abweichung'` lesen) ist ein Block von etwa 5 Zeilen. Aufwand klein, nur Wetter, nur normal.
- Folge: Elementliste bekommt einen Abschnitt (Picker "▾ 1 Abweichung", Zurücksetzen-Zeile, Verlust-Satz in der Bestätigung); mockup_hash und elementliste.json werden neu erzeugt, der Rest bleibt unverändert (Identität enthält den Abschnitt).

## 2. Abgleich (elementliste-abgleich.staging.spec.ts, elementliste_abgleich_logik.ts)
- Zuordnung rein nach Namen: `routenPlan(zustand)` (Logik Z. 365): normal = keine Umleitung, laedt = hängen, fehler = 500, luecken = Konto-Antwort umschreiben. Der Abgleich "weiß" den Live-Zustand nicht, er stellt ihn her (und prüft bei luecken `herstellungsGrund`).
- Für Wetter-Bedien-Abschnitte gibt es schon eine zweite Achse: `datensatzFuerAbschnitt` (Z. 474: `grenzen-*` -> Prüf-Datensatz `mit_abweichung`, sonst `ohne_abweichung`), Anlage in `wetterPruefDaten`/`wetterPruefPayload` (Z. ~600-660), Seiten-ID über `seitenIdFuer`. Ein neuer Abschnitt "vorlage-abweichung" wird dort einfach auf `mit_abweichung` gelegt; der Datensatz existiert schon und hat laut Payload Overrides (= Abweichungen).

## 3. Prüfkonto (scripts/staging_pruefkonto_mockupdaten.py)
- `soll_wetter()` (Z. 252): Vorlage alpen-trekking, aber `wind_direction` aus und eigene ampel.metrics je Metrik -> live 1 Abweichung. Es ist also Absicht/Nebenwirkung der Mockup-Datenangleichung, nicht Zufall.
- Berichte st3250 (Trip/Wetter/normal, Vorlage): de: "▾ unverändert" abweichend (#2913), en: nicht_pruefbar (#2913); live steht "1 Abweichung" bzw. "1 change" als zusaetzlich (de: "1 Abweichung" ohne Besitzer, #2913-Besitzer bei "▾", "−"); Zurücksetzen-Zeile ist über die pauschale Ausnahme (muster `Auf "{vorlage}" zurücksetzen` / `Reset to "{vorlage}"`, spec feat_3205) abgedeckt. Gesamt de: 1473 gefunden / 483 abweichend / 198 nicht_pruefbar / 142 zusaetzlich; en: 1427 / 427 / 300 / 168.
- Weg A (Prüfkonto auf unverändert): "▾ unverändert" würde gefunden, "1 Abweichung" und Marken (Abweichungsmarke "●", "−") entfielen als zusaetzlich; Zurücksetzen verschwindet live (Ausnahme wäre dann überflüssig, aber auch die Zurücksetzen-Abdeckung weg). Nebenwirkung: Wetter-Seiten mit Overrides (Grenzen/Was-steht-wo) sind auf dem Prüfkonto-Trip an wind_direction/ampel.metrics gekoppelt, ein Umbau verschiebt dort Werte; Vorher/Nachher-Abgleich beider Sprachen nötig, Seeds anderer Specs (#3150, #3151) betroffen.

## 4. Optionen
- A Prüfdaten ändern: mittlerer Aufwand, mittleres Risiko (Seiteneffekte auf andere Abschnitte, Seed-Tests); löst nur den Picker-Text, nicht das Zurücksetzen (das braucht den Abweichungszustand im Soll ohnehin).
- B neuer Seiten-Zustand "abweichung" nur für Vorlagenkarte: als dritter globaler Zustand teuer (verdoppelt Seite), aber als Script-Abschnitt "vorlage-abweichung" (siehe 1/2) klein: Generator +5 Zeilen, Abgleich +1 Zuordnung, Elementliste neu erzeugen, Ausnahmen (beide Sprachen, plus Z.-511-Hinweis) streichen. Mittlerer Aufwand, geringes Risiko.
- C Ausnahme belassen, aber eng machen (nur Zurücksetzen, nur trip/wetter, Z. 514 korrigieren): minimaler Aufwand, hält die Lücke offen.

## Empfehlung (Tech Lead)
B als Script-Abschnitt (kein globaler Zustand), mit Datensatz `mit_abweichung`; "▾ unverändert" bleibt Normalzustand mit Datensatz `ohne_abweichung`. Danach beide Ausnahmen streichen. Keine Produktentscheidung nötig, reine Prüfwerkzeug-Mechanik. Vorher prüfen: ob die Zurücksetzen-Zeile beim `mit_abweichung`-Datensatz live erscheint (abweichungen>0) und wie `Abweichung(en)`-Plural im Picker verglichen wird.
