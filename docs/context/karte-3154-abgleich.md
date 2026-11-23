# Context: karte-3154-abgleich (#3154, Epic #3122)

## Request Summary
Restpunkte von #3154: Die Karte „Was steht wo“ (Reiter Wetter, Trip und Orte) ist seit 19.11. live (PR #3142, `2b10e14a3`).
Offen ist allein AC-21 der Spec `docs/specs/modules/feat_3122_was_steht_wo.md`: Elementlisten-Abgleich Abschnitt
`was-steht-wo` mit `--strict` in DE und EN grün, Prüf-Agent (mockup-bildpruefer) Soll/Ist-Bild ohne offenen Befund
nach höchstens zwei Runden. Dazu: veraltete Besitzer-Einträge („noch nicht gebaut“) aus
`docs/context/einstellungen_neu/elementliste_besitzer.json` entfernen.

Erledigt bzw. abgelöst (nicht mehr Teil dieses Workflows):
- `ALTBESTAND_UEBER_UMRECHNUNG` umlegen: überholt, B6-Migration (#3157) hat alle Bestands-Abos auf `placements` gebracht;
  Entfernen des Altpfads samt Schalter macht #3237 (andere Sitzung, Phase 6, NICHT anfassen:
  `src/services/channel_list_resolver.py`, `placements.py`, Validator-Soll-Hooks).
- `_soll_aus_konfiguration.py` aus `placements`: #3218/#3242 erledigt, Rest #3273 (überschneidet sich mit #3237).
- „Kürzel erklärt“/Legende in der Elementliste: #3258 erledigt.

## Messung 22.11. (Staging = main `0b167519c`, Prüfkonto, Scope wetter/normal)
Aufruf: Seed `scripts/staging_pruefkonto_mockupdaten.py` → `ELEMENTLISTE_TRIP_ID=gz2967-gr221-mallorca`,
`ELEMENTLISTE_ORTE_ID=cp-ba40345c6360b8a7`, Login `GZ_PRUEFKONTO_USER/PASS` aus Staging-.env (Runbook
`docs/runbooks/staging_pruefkonto_seed.md`). Berichte: `docs/artifacts/karte-3154-abgleich/abgleich-vorher-{de,en}.json`.

| Sprache | abweichend gesamt | davon was-steht-wo Trip (Reihenfolge / nicht sichtbar) | Orte (Reihenfolge / nicht sichtbar) |
|---|---|---|---|
| DE | 290 | 171 / 19 | 60 / 25 |
| EN | 244 | 165 / 19 | 24 / 20 |

Übrige Abweichungen (kopf, vorlage, grenzen-*) gehören nicht zu #3154.

### Befundgruppen was-steht-wo (Hypothesen, in /20-analyse prüfen)
1. **Kaskade „Reihenfolge im Abschnitt“:** Der Abgleich (`frontend/e2e/elementliste_abgleich_logik.ts:1335-1369`)
   arbeitet mit einem gierigen Cursor; fehlt ein Element an seiner Stelle oder springt ein Treffer zu weit nach vorn,
   werden alle Folgeelemente „Reihenfolge“. Trip-Erstbruch: Nr. 23 „Tiefsttemperatur Nacht in E-Mail“ und Nr. 27
   „… im 3-Tages-Ausblick“ (live vermutlich gesperrte Zelle statt Haken, oder andere Zeilenfolge ab Nr. 28
   „Tages-Tiefsttemperatur (Gehzeit)“). Orte-Erstbruch: Nr. 77 „Gewitter in E-Mail“ / Nr. 79 „Einfach“.
   Frage: echter Unterschied live↔Mockup (Zellen/Zeilenfolge) oder Mockup-Daten ≠ Seed-Daten (Seed-Reihenfolge)?
2. **Beispielwerte nicht sichtbar:** Trip „Temp 14.4“, „Feels 11.0“, „Gust 50“, …; Orte „13°C / 4°C“, „R 1.8 mm“, …
   Live kommen Beispielwerte aus echter Vorhersage (B2 `cells[].example`) → datenabhängig. In #3258 wurden
   SMS-Beispielwerte als Muster behandelt; dasselbe Muster für Zellen-Beispielwerte prüfen.
3. **SMS-Beispielzeile und Zeichenzahl:** „SMS-Beispiel: · 123 von 160 Zeichen“, Beispieltext — echter Renderer,
   datenabhängig (AC-27 verlangt Renderer-Zeile) → Muster statt Wortlaut.
4. **Orte „Einfach“-Knöpfe nicht sichtbar** (mehrfach) — Darstellung je Stelle live anders vorbelegt als im Mockup
   (Seed setzt Formate?) oder Knopf zeigt anderen Text.
5. **Orte Hinweissatz** „Bei 3 Orten passen die letzten 5 Metriken nicht mehr …“ — Wortlaut/Zahl live anders.
6. **Schalter vs. Titel 3-Tages-Ausblick** (Kommentar #3203 in #3122): live `Switch` + `aria-hidden`-Titel,
   Mockup `sw(...)` + Text in `.chk` — prüfen, ob noch abweichend.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | Karte (384 Z.) |
| `frontend/src/lib/components/**/EinstellTabelle.svelte` | Tabellen-Baustein (B3a) |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (`wasStehtWo()` ab Z.670, `blockEinst()` Z.661) | Soll-Bild |
| `docs/context/einstellungen_neu/elementliste.json` / `elementliste_besitzer.json` | Elementliste + Besitzer (veraltete #3122-Einträge „noch nicht gebaut“) |
| `scripts/elementliste_aus_mockup.ts` | erzeugt Elementliste aus dem Mockup (Muster für datenabhängige Werte) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | Bewertung, Muster, Reihenfolge |
| `scripts/staging_pruefkonto_mockupdaten.py` | Seed der Mockup-Daten (Metrikfolge/Formate des Prüf-Trips) |
| `frontend/e2e/was-steht-wo-karte.spec.ts`, `was-steht-wo.helpers.ts` | bestehende Browser-Fälle WS-* |

## Existing Patterns
- #3258: datenabhängige Werte (SMS-Beispiel) als Muster in der Elementliste, Fixture für Live-Legende.
- #3251: Vorlage-Abweichungen per Muster/Besitzer.
- Besitzer-Einträge nur für echte, offene Abweichungen mit Verweis auf offenes Issue.

## Risks & Considerations
- Nicht in die Dateien von #3237 greifen (Backend-Resolver, Validator-Soll).
- Mockup ist Soll; Änderungen am Mockup nur, wo es Beispieldaten betrifft (kein stilles Umdeuten des Soll-Bilds).
- Abgleich dauert je Sprache ~7 min; strict nur für Abschnitt was-steht-wo nötig.

## Analysis

**Type:** Abgleich-Befund, kein Fehler der Karte. Hauptursache ist der Prüf-Datensatz (Seed) plus ein veraltetes Soll-Bild (Mockup) und zwei Lücken im Abgleich-Werkzeug. `WasStehtWoKarte.svelte` und `EinstellTabelle.svelte` müssen nicht geändert werden (Ausnahme: Gruppe 6, nur als Fallback).

**Methode (belegt):** Staging-DOM des Prüfkontos mit der echten Sammelregel `sichtbareTextBloecke` gelesen (Trip und Orte, Stand 22.11., Profilsprache EN) und `bewerteAbschnitt` offline darüber laufen lassen: Ergebnis ist Eintrag für Eintrag identisch mit `abgleich-vorher-en.json` (0 Abweichungen). Damit ist die Kaskade reproduziert. DE nicht neu gemessen (hätte die Profilsprache des geteilten Kontos überschrieben); die Mechanik ist sprachunabhängig. GET `placements` beider Abos: `stored: false`.

### Wie die Kaskade entsteht (gilt für alle Gruppen)
`bewerteAbschnitt` (`frontend/e2e/elementliste_abgleich_logik.ts:1348-1366`) nimmt je Element den ersten Text NACH dem Cursor (`nachher`, Z.1355); gibt es ihn nur davor (`irgendwo`, Z.1356), heißt es „Reihenfolge im Abschnitt“ (Z.1364), der Cursor bleibt stehen. Springt ein Treffer zu weit nach vorn, ist alles Folgende „Reihenfolge“. Verschärfend: Muster mit Platzhalter (`{metrik} in E-Mail`, `Format von {name}: {form}`) passen auf den Text einer SPÄTEREN Zeile; so „gelingt“ ein Element scheinbar und der Cursor springt weiter. Das „vor Element Nr. N-1“ im Bericht ist nur der Normaltext der Meldung, nie die Ursache.

### Gruppe 1: Trip-Kaskade (DE 171 / EN 165) — Ursache: Zeilenfolge und gesperrte Zellen, belegt
- **Erstbruch Nr. 22/23:** Live-Reihenfolge ist die Standardfolge der Grundauswahl, nicht die Mockup-Folge: Temperatur, Tages-Tief/-Hoch (Gehzeit), Wind, Böen, Regenwahrscheinlichkeit, Niederschlag, Gefühlte (4), Gewitter, Sicht, Nullgrad, UV, Schneefall, Tiefe Wolken und **„Tiefsttemperatur Nacht“ ganz am Ende**. Mockup (`mockup-hub-fassung4.html:316-336`): Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte (4), Wind … Schneefall. Nr. 22 „Tiefsttemperatur Nacht“ findet den Zeilennamen erst am Tabellenende; der Cursor springt dorthin. Nr. 23 (`{metrik} in E-Mail`) und Nr. 27 (`… im 3-Tages-Ausblick`) gibt es nur davor, danach nur noch Telegram/SMS/„N14“ (Nr. 24-26 gefunden). Ab Nr. 28 liegt alles vor dem Cursor: 171 Folgen.
- **Warum die Folge anders ist:** Der Seed schreibt keine `placements` (`scripts/staging_pruefkonto_mockupdaten.py`: kein Treffer für „placements“; `soll_wetter()` Z.252-257 setzt nur `metrics`/`ampel`; `_TRIP_REIHE` Z.69 kennt die fünf Nur-Anzeige-Zeilen aus #3204/#3250 nicht). Ohne gespeicherte Tabelle kommt die Reihenfolge aus `grundauswahl()` (`src/services/channel_list_resolver.py:225-241`; nur benannt, Tabu): abgeleitete Größen hängen hinter ihrem Elter, die Nacht am Ende. Die Mockup-Folge erzwingt nur gespeicherte `placements`.
- **Gesperrte Zellen (echte Mockup-Abweichung von der Spec):** Live sperrt für Nacht, Tages-Tief/-Hoch und die drei gefühlten Fensterwerte E-Mail („keine eigene Spalte“, `src/app/metric_catalog.py:1343-1358` `stellen_sperre`) und 3-Tages-Ausblick („kein Tageswert“). Das schreibt die freigegebene Spec vor (`feat_3122_was_steht_wo.md` Nr. 5, AC-7 „Tiefsttemperatur Nacht in der Stundentabelle der Trip-Mail“). Das Mockup zeichnet dort normale Haken (`wasStehtWo()` Z.683-693; `xcell` kennt nur „kein Stundenwert“ für Sonnenstunden). Live fehlen deshalb die Texte „… in E-Mail“/„… im 3-Tages-Ausblick“ (gesperrter Haken ist `role="img"`, sein Name zählt nicht als Text; sichtbar nur der Grundtext).
- **Korrektur:** (a) Seed: `PUT /api/briefings/gz2967-gr221-mallorca/placements?kind=route` mit Mockup-Folge (18 Zeilen), alle Haken an, Formate wie Mockup (`defFmt` Z.578: Roh, außer Windrichtung/Gewitter/Bewölkung/Sonne = Einfach), `outlook_reports` wie Mockup; `If-Match` darf fehlen (`internal/handler/etag.go:54-57`); GET, vergleichen, PUT (idempotent). (b) Mockup: die sechs Fensterzeilen in E-Mail und Ausblick als gesperrt mit Grund zeichnen (`.nix` + Grundtext wie bei Sonnenstunden). Dann Elementliste neu erzeugen.

### Gruppe 2: Beispielwerte „Text nicht sichtbar“ (Trip 19, Orte 6 + Zellen)
- **Hypothese korrigiert:** Die Beispielwerte sind NICHT vorhersageabhängig. Sie kommen aus dem festen Datensatz `src/services/placements_beispiel.py` (`TAG = 2026-07-14`, ohne Wetterabruf, `example_version`; Vertrag `docs/reference/api_contract.md:1497`). Sie weichen ab, weil das Mockup eigene Zahlen hat (`TF`/`OD`, Z.558-575) und E-Mail-Beispiele mit Spaltenkürzel versieht (`COLL`, Z.360: „Temp 14.4“); live steht nur „14.3“.
- **Belegt:** Muster `Temp {zahl}` (`elementliste.json`, trip Nr. 16) passt nicht auf „14.3“; „Wind 36“ wird nur zufällig von der Legende getroffen. Einfach-Zellen haben live gar keinen Text (HTML-Ampelpunkt ist `role="img"`): „Thdr ● gelb“, „Gust 50“ u. a. entfallen größtenteils mit Roh/Einfach aus dem Seed (Gruppe 1 a); Gewitter-E-Mail in Einfach bleibt ohne Text (Rest, siehe unten).
- **Korrektur (Werkzeug, Muster wie #3258):** Alle Beispielzellen (E-Mail, Telegram, SMS; bei Orten auch die Gewitter-Zelle) als `{wert}`-Muster erzeugen: `scripts/elementliste_aus_mockup.ts` (Rolle erkennen, `baueElemente` ~Z.616; bisher macht `ZAHL` Z.581 nur Zahlen zu `{zahl}`), `{wert}` in `frontend/e2e/elementliste_abgleich_logik.ts` (`musterAlsRegExp` Z.209 passt auf `.+?`; `neutralMuster` Z.846 kennt nur `{zahl}`; `gegenMuster` für die Gegenrichtung). `{wert}` braucht eine Negativvorschau gegen Zellennamen (`… in/im E-Mail|Telegram|SMS|Stundenverlauf|3-Tages-Ausblick`, `Darstellung …`/`Format of …`), sonst verschluckt ein fehlender Beispieltext den nächsten Zellennamen und es entsteht still eine neue Kaskade. Alternative (nicht empfohlen): Mockup-Zahlen auf den festen Datensatz umschreiben (~100 Werte plus SMS-Kürzungslogik, bricht bei jeder Datensatz-Version).

### Gruppe 3: SMS-Beispielzeile und Zeichenzahl — Struktur plus Format
- **Zeichenzahl (Struktur, belegt):** Mockup `budgetZeile()` (Z.611-613): `SMS-Beispiel: <b>…</b> · 123 von 160 Zeichen` in einem Textblock. Live (`WasStehtWoKarte.svelte:207`): Zahl in eigenem `<span data-testid="was-steht-wo-sms-zeichen">`, also zwei Texte „SMS-Beispiel: ·“ und „145 von 160 Zeichen“ (zusätzlich-Liste des Staging-Laufs). Das Muster `SMS-Beispiel: · {n} von {max} Zeichen` kann so nie passen. **Korrektur:** im Mockup die Zahl in ein `<span>` setzen (optisch identisch, Live-Code und seine Tests unverändert); der Generator liefert dann zwei Elemente, das zweite `{n} von {max} Zeichen` (Katalogschlüssel vorhanden, #3258).
- **Zeile selbst (datenabhängig):** `{wert}` wie Gruppe 2. Trip-Altlast zusätzlich: Mockup „GR221 E2: …“ mit Doppelpunkt, live „Port d'And D14/18 …“ ohne (#3174, `sms_format.md` v2.48); mit `{wert}` kein Befund mehr.
- **Orte (echte Mockup-Altlast, belegt):** Mockup zeichnet die Alt-Form „Orte 18.11.: Münster D 13C L 4C W 30 km/h … +5; Telgte …“ (`smsCalc` Z.582-595). Seit #3172/ADR-0125 (19.11., `sms_format.md` §5b, v2.47) ist die Orte-SMS eine Token-Zeile „O1 D19 W30@10(43@16) … O2 …“, Zellen „W30@10(43@16)“ statt „W 30 km/h“, ohne `+N`. Betrifft Orte Nr. 22, 35, 51, 68, 85, 99, 112, 130, 137. **Korrektur:** Mockup-Orte-SMS auf die Token-Form umstellen (feste Tokenstrings des Beispieldatensatzes genügen); Zellen dann als `{wert}`.

### Gruppe 4: Orte „Einfach“-Knöpfe (DE 11, EN 9-11) — zwei Ursachen
1. **Seed (belegt):** Orte-Formate stehen live auf `raw` für Bewölkung, Sonnenstunden und Gewitter-E-Mail (GET `placements?kind=vergleich`: `formats` alles `raw`, `stored: false`); Mockup-Vorgabe ist Einfach (`defFmt`). Betrifft Nr. 79 (Gewitter E-Mail), 106/109/116/119 (Bewölkung), 123/127/135 (Sonne). Behebt der Seed per `PUT …/placements?kind=vergleich` mit `formats` Einfach.
2. **Echte Mockup-Abweichung von der Spec (belegt):** Mockup zeigt für Gewitter einen Einfach-Knopf auch in Telegram, Stundenverlauf und Ausblick (Nr. 82, 89, 92; Trip analog; `HASF` Z.577 gilt für alle Stellen). Spec Teil A Nr. 4 (Tabelle): Gewitter hat die zweite Form nur in der E-Mail. Live ist richtig (kein Knopf). **Korrektur:** Mockup: Knopf für Gewitter nur in E-Mail (Stellenliste je Metrik statt globalem `HASF`).

### Gruppe 5: Orte-Hinweissatz (Nr. 138) und SMS-Marken
Wortlaut plus Datenabhängigkeit. Mockup: „… passen die letzten 5 Metriken nicht mehr in die SMS. **Dafür steht „+5“ je Ort.** Zieh nach oben, …“ (`budgetZeile` Z.613). Live (`wetter.json:173`, `wetter.wsw.sms_orte_passt_nicht.other`): „Bei {orte} Orten passen die letzten {count} Metriken nicht mehr in die SMS. Zieh nach oben, …“; „+N je Ort“ gibt es seit #3172 nicht mehr (`api_contract.md:5406`). Die Zahl 4 statt 5 ist datenabhängig (Muster mit `{zahl}` existiert). **Korrektur:** Mockup-Satz „Dafür steht …“ streichen.
Orte-Erstbruch ist eigentlich Nr. 69 „passt nicht mehr“ (Niederschlag-SMS): live gibt es den Marker erst bei Gewitter (4 Metriken gekürzt, SMS 149 Zeichen). Nr. 69 trifft den Gewitter-Marker, der Cursor springt etwa 20 Texte nach vorn, platzhalter-Muster (Nr. 70-75) „gelingen“ weiter hinten; ab Nr. 76 „Gewitter“ liegt alles davor: Reihenfolge bis Nr. 135 (DE 60). Mit der Token-SMS im Mockup (Gruppe 3) liegen die Marker an gleicher Stelle. Marker sind Ausgabe-abhängig und bewusst NICHT als Muster zu entschärfen.

### Gruppe 6: Schalter vs. Titel 3-Tages-Ausblick (#3203) — noch abweichend, belegt
Nr. 237 „Ausblick im Morgen-Briefing“ und Nr. 239 „… Abend-Briefing“ (Trip, Reihenfolge). Mockup (`blockEinst()` Z.664): `<span class="chk">` mit eigenem Text „Morgen-Briefing“, Schalter-Name kommt danach; Elementliste: Titel, dann Schalter-Name. Live (`WasStehtWoKarte.svelte:228-231`): Schalter zuerst, Titel als `aria-hidden`-Kind; Staging-Texte „Outlook in the morning briefing“ vor „Morning briefing“. **Korrektur (bevorzugt, kein Live-Eingriff):** Mockup-Markup wie live schreiben (Titel als `aria-hidden`-Span hinter dem Schalter), optisch identisch. Fallback, falls der Generator (`ausleseImBrowser`) `aria-hidden` anders liest als `sichtbareTextBloecke` (nach Neuerzeugung prüfen): live den Titel als eigenen Textknoten des `wsw-wahl`-Spans setzen.

### Gruppe 7 (zählt für `--strict`): EN-Lücken und DE/EN-Unterschied
`exitCode` (Z.141) zählt `nicht_pruefbar` mit; EN hat im Abschnitt 9 (Trip) und 12 (Orte). Echte Generator-Lücken ohne EN-Katalogtext: Zeilennamen „Regenwahrscheinlichkeit“, „Tiefe Wolken“, „UV-Index“, „Bewölkung“ (live „Rain probability“, „Low clouds“, „UV index“, „Cloud cover“; stehen als „zusätzlich“ im EN-Bericht). Übrige EN-Lücken sind Beispielzellen/SMS-Zeilen (Gruppe 2/3, entfallen mit `{wert}`). **Korrektur:** Metrik-Namen DE→EN als Schnappschuss aus dem Metrik-Register (wie `daten/kuerzel_bedeutung.json`, #3258) in `ermittleEn` einhängen.
DE 60 vs EN 24 (Orte, Schluss aus dem Code, nicht gemessen): EN-Lücken-Elemente werden ohne Regexp übersprungen (Z.1350-1353) und EN-Muster sind großzügiger, der Cursor findet früher zurück; die Kaskade selbst ist in beiden Sprachen dieselbe.

### Besitzer (`elementliste_besitzer.json`)
- **Veraltet, entfernen:** die zwei `abschnitt`-Einträge `was-steht-wo` (Trip ~Z.550-557, Orte ~Z.702-709), Grund „noch nicht gebaut“, Verweis #3122. Sie decken heute 275 Abweichungen als „besitzt“ ab.
- **Bleibt (nicht #3154):** Zustellung-Lücken (`trip/orte.zustellung.luecken…`), „Orte“-Erklärtext (Katalog `vergleich.hub.kopf.orte_erklaer` ist noch der alte Text), Orte-Kopfzeile „Vergleichstabelle“ (live noch vorhanden, `aktionen.kopf.vergleichstabelle`), Zustellung-Übergangsblock (#2795).
- `--strict` zählt Besitzer-Einträge nicht als erledigt (`exitCode` Z.141): Abweichungen müssen verschwinden, nicht abgedeckt werden. Neue Einträge nur für Echtes, das nach den Korrekturen übrig bleibt, mit offenem Issue.

### Rest-Risiko (nach Neumessung klären)
- Gewitter-E-Mail in Einfach (Trip „Thdr ● gelb“): live nur Ampelpunkt ohne Text, Mockup zeichnet „● gelb“ als Text. Mockup-Zelle ohne Text zeichnen (Punkt als Element mit Namen) oder Zelle als optional behandeln; nach Neumessung entscheiden.
- Telegram-Marke „nur Tageswert“: live zählt die 7 Telegram-Spalten inklusive der Fensterzeilen (Marke ab „Gefühlte Temperatur“ in der Standardfolge); Mockup zählt nur Metriken mit `TF[…].tg` (`tgCut` Z.676). Mit Mockup-Folge kann die Marke auf anderer Zeile landen; dann `tgCut` an die Renderer-Zählung angleichen.
- Orte-Temperatur: Mockup zeigt Max und Min („13°C / 4°C“, „D 13C L 4C“); Seed hat nur `("temperature","max")` (`_ORTE_METRIKEN` Z.75); live „19°C“, „D19“. Hypothese: Seed braucht zusätzlich Min; per Staging-Lauf prüfen.
- Orte-Ausblick: Abo hat nur Morgen (`outlook_reports: ["morning"]`), Mockup Abend; im selben `PUT` setzen (wirkt aufs Soll/Ist-Bild, nicht auf den Textabgleich).
- „zusätzlich“ (Live-Texte ohne Mockup-Pendant, z. B. Beispiele in der Stundenverlauf-/Ausblick-Spalte „15°“, „12/25“): zählen nicht für `--strict`, nur für `--abnahme`.

### Affected Files
- MODIFY `scripts/staging_pruefkonto_mockupdaten.py` (+~60 LoC: Soll-`placements` Trip/Orte, GET-vergleichen-PUT, Orte-Temperatur Min) und sein Test.
- MODIFY `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (~40-60 Zeilen: gesperrte Fensterzellen, Gewitter-Knopf nur E-Mail, Orte-SMS Token-Form, Zeichenzahl-Span, Hinweissatz, Ausblick-Schalter-Markup).
- MODIFY `scripts/elementliste_aus_mockup.ts` (+~40 LoC: `{wert}`-Rolle, Metrik-Namen-Schnappschuss); CREATE `docs/context/einstellungen_neu/daten/metrik_namen.json`.
- MODIFY `frontend/e2e/elementliste_abgleich_logik.ts` (+~25 LoC: `{wert}` in `erwartung`/`neutralMuster`/`gegenMuster`) plus `node --test`-Tests (`{wert}` mit Negativvorschau, Kaskaden-Schutz).
- REGENERATE `docs/context/einstellungen_neu/elementliste.json` (mechanisch, groß; `elementliste_aktuell.test.ts` zieht Prüfsumme nach).
- MODIFY `docs/context/einstellungen_neu/elementliste_besitzer.json` (-16 Zeilen).
- Tabu, nur benannt: `src/services/channel_list_resolver.py` (Ursprung der Standardfolge), `src/services/placements.py`. Live-Karte unverändert (Fallback Gruppe 6).

### Scope / Risiko
- Handgeschrieben etwa 8 Dateien, ~250 LoC netto, plus regenerierte Elementliste. Kein Backend, kein Datenschema, kein Live-Frontend.
- Risiko niedrig bis mittel: (1) Seed schreibt auf das Staging-Prüfkonto (kein Prod; Read-Modify-Write nur an `display_config.placements`). (2) `{wert}` ist ein Platzhalter für beliebigen Text: ohne Negativvorschau neue stille Kaskaden. (3) Mockup-Änderungen berühren das Soll-Bild; alle sind Angleichung an freigegebene Spec/ADR (Sperren, Gewitter-Knopf, Orte-SMS ADR-0125) oder reines Markup. (4) Abnahme braucht je Sprache einen vollen Lauf (~7 min) und den Bildprüfer.

### Technischer Ansatz (eine Empfehlung)
1. Seed: gespeicherte `placements` in Mockup-Folge und -Formaten für Trip und Orte (Gruppen 1, 4, Rest-Risiko).
2. Mockup auf Spec/ADR-Stand bringen: gesperrte Zellen, Gewitter-Knopf, Orte-SMS Token-Form samt Hinweissatz, Zeichenzahl-Span, Ausblick-Schalter-Markup.
3. Abgleich-Werkzeug: `{wert}` (mit Negativvorschau) für Beispielzellen und SMS-Zeilen, Metrik-Namen-Schnappschuss für EN.
4. Elementliste neu erzeugen, die zwei veralteten Besitzer-Einträge streichen.
5. `--strict` je Sprache für `was-steht-wo`; jeden verbleibenden Treffer einer Gruppe oben zuordnen (nie „kommt später“), dann Bildprüfer.

### Offene Fragen
keine (alle Korrekturen folgen aus Spec Nr. 4/5, AC-7, ADR-0125 und früheren PO-Vorgaben).
