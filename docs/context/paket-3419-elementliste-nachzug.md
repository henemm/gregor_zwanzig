# Kontext + Analyse: Paket #3419–#3422 (Elementlisten-Nachzug „Was steht wo“)

Workflow `paket-3419-elementliste-nachzug`, Score 2 (Kontext und Analyse in einem Dokument). Teil von #2795,
Befund der Abnahme #3037 (Lauf `--abnahme --scope wetter/normal`, 26.11.2026). Rohberichte:
`docs/artifacts/paket-3419-elementliste-nachzug/vorher/elementliste-{de,en}/` (Kopie aus dem #3037-Worktree).

## Ausgangslage (Rohbericht)

DE: 185 ohne Besitzer (159 abweichend, 49 zusätzlich), EN: 173. Ohne Besitzer gruppiert:

| Gruppe | DE | EN | Ursache | Issue |
|---|---|---|---|---|
| Trip was-steht-wo „Reihenfolge im Abschnitt“ | 136 | 121 | ein Fehltreffer „Temperatur in SMS“ (live gesperrt, #3373) lässt den Cursor zur nächsten Zeile springen | #3420 (+ Mockup #3419) |
| Trip Legende „Tagestiefstwert“, „Tageshöchstwert“, „FL“, „L gefühlt“, „D gefühlt“ nicht sichtbar; live „Tagestiefstwert/Tageshöchstwert“, „L gefühlt/D gefühlt“ zusätzlich | 5+2 | 5+2 | #3284 Legende zusammengeführt | #3419 |
| Orte Legende „Tageshöchstwert“ / live „Tagestiefstwert/Tageshöchstwert“ | 1+1 | 1+1 | #3284 | #3419 |
| Trip „Feels 11.0“, „TF 6.8-11.7“ (kein Beispieltext vor nächstem Zellennamen) | 2 | 2 | vermutlich Folge der Kaskade; nach Fix neu messen | #3420/#3419 |
| Grenzen „-10“, „-8“, „-15“, „-300“, „-500“ (Trip 5, Orte 1) | 6 | 6 | Prüf-Datensatz `wetterOverrides` setzt feste positive Werte (lower 1/2/3, upper 10/20/30) | #3421 |
| Orte Kopf „Orte · Münsterland“ | 1 | 1 | Seed `display_config.region = "Westfalen"` (`scripts/staging_pruefkonto_mockupdaten.py` ~335) | #3419 |
| Trip zusätzlich „Kurz-Zusammenfassung“, „Großwetterlage“ + Hinweise | 4 | 4 | #3036 eigene Schalter, fehlen im Mockup | #3419 |
| Orte zusätzlich „E-Mail: Format“ + Hinweis + „Ausführlich (HTML)“/„Kompakt (Nur-Text)“ | 4 | 4 | #3059; Mockup `kanalEinst()` zeigt die Zeile nur bei `!O()` | #3419 |
| Orte zusätzlich „Morgen-Briefing“, „Abend-Briefing“ | 2 | 2 | sichtbare `aria-hidden`-Beschriftung neben den Ausblick-Schaltern; Generator überspringt `[aria-hidden="true"]` (`scripts/elementliste_aus_mockup.ts:514`), der Abgleich zählt sie seit #3203; im Trip deckt das Test-Menü (Morgen-/Abend-Briefing) dieselben Texte zufällig | #3419 |
| Trip zusätzlich „1 Abweichung“ (Vorlagen-Picker) | 1 | 1 | Seed-Trip weicht in einem Punkt von „Alpen-Trekking“ ab, Mockup sagt „unverändert“ | #3419 |
| Trip „kein Kürzel“ zusätzlich | 1 | 1 | #3373 Sperrzelle fehlt im Mockup | #3419 |
| Beispielwerte zusätzlich (Trip „R 0.0-1.3@16“, „TH mittel“, „🌤️“, „CL 🌤️-⛅@19“, „UV …“, „FZ 3300“, „SL 2900“, SMS-Zeile „E1 …“; Orte „D15/19“, „Gewitter mittel“, „⛅“, „Wolken ⛅“, „Sonne freundlich“, SMS-Zeile „O1 …“) | ~20 | ~20 | Gegenrichtung erklärt `{wert}`-Texte nur in der Form des Mockup-Beispiels (`beispielForm`); echte Prognosewerte haben andere Form (Uhrzeit-Marke, Wort, Emoji) | #3419 Nr. 6 |
| EN Orte „Gusts 62 km/h“, „Rain 3.4 mm“, „Thunderstorm medium“, „Rain probability 70%“, „Clouds ⛅“, „Sun fair“ | – | ~6 | Gegenrichtung baut EN-Form aus `text_de` (`erwartungGegenrichtung` → `beispielForm(e.text_de)`) | #3422 |

## Betroffene Dateien

- `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` — Soll-Bild (TF/OF-Beispiele, `sperre()`, `LEG_TRIP`/`LEG_ORTE`, `blockEinst()`, `kanalEinst()`, CTX-Kopf).
- `docs/context/einstellungen_neu/elementliste.json` — aus dem Mockup erzeugt (`scripts/elementliste_aus_mockup.ts`, Spec `frontend/e2e/elementliste-generator.mockup.spec.ts`), DE/EN-Zuordnung über Katalog.
- `docs/context/einstellungen_neu/elementliste_besitzer.json` — Besitzer-Einträge (element/abschnitt/zusaetzlich).
- `frontend/e2e/elementliste_abgleich_logik.ts` — `bewerteAbschnitt` (Cursor `zuletzt`, ~1375–1430), `wetterOverrides` (~498), `erwartungGegenrichtung`/`beispielForm` (~901–916), `findeZusaetzliche` (~1098), `ZELLEN_QUELLE`/`ZELLENNAME` (~823).
- `frontend/e2e/elementliste_abgleich_logik.test.ts` — `node --test` Kern-Schicht (kein Vitest).
- `frontend/e2e/elementliste-abgleich.staging.spec.ts` — Staging-Lauf (Prüfkonto, Grenzen-Prüfdatensatz).
- `scripts/staging_pruefkonto_mockupdaten.py` + `tests/tdd/test_staging_pruefkonto_mockupdaten.py` — Seed.
- Live-Referenz (unverändert): `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`, `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts`, `src/services/placements_view_service.py`.

## Bestehende Muster

- Vorbild #3154 (Commit 57e3a291b): Mockup an freigegebene Entscheidungen angleichen, Elementliste neu erzeugen,
  Seed nachziehen, Staging `--strict` je Abschnitt. Optisches Soll sonst unverändert.
- `{wert}`-Beispieltexte: Hinrichtung sucht nur bis zum nächsten Zellennamen, Cursor bleibt bei Fehltreffer stehen (#3154 AC-9) — genau dieses Prinzip fehlt für `{metrik}`-Zellmuster (#3420).
- `kontoTexte`: Texte aus Kontodaten sind in der Gegenrichtung erklärt (`findeZusaetzliche`).
- EN-Metriknamen-Schnappschuss `docs/context/einstellungen_neu/daten/metrik_namen.json` (#3154).

## Analyse / Lösungsansatz

1. **#3420 Kaskade:** Zellmuster-Elemente (Muster `{metrik} in|im <Stelle>`) gehören zu einer Tabellenzeile.
   Zeile im Soll = gleicher Metrikteil im `text_de` (Liste ist immer DE-erzeugt). Ist das vorige Zellmuster-Element
   derselben Zeile gefunden, muss der Live-Treffer denselben Metrikteil tragen wie dessen Live-Treffer; sonst
   „Text nicht sichtbar“ für genau dieses Element, Cursor bleibt stehen. Test: ein künstlich fehlendes Kästchen
   ⇒ genau eine Abweichung (DE und EN).
2. **#3421 Grenzen:** Prüf-Datensatz aus den Mockup-Werten statt fester Zahlen (Mockup-Grenzen stehen in der
   Elementliste bzw. im Mockup `TRIP_METRICS`/`ORTE_METRICS`); Alternative Muster `{zahl}` verwirft den Wertvergleich,
   daher nachrangig. Gültigkeitsregel #3192 AC-1 (aufsteigend, lower unter upper, `allowed_sides`) muss halten.
3. **#3422 EN-Gegenrichtung:** EN-Form aus der englischen Beispielform: Metriknamen-Teil per Schnappschuss
   übersetzen (DE-Name → EN-Name), Zahlen beliebig.
4. **#3419 Beispielwerte (Nr. 6):** Live-Texte, die die Hinrichtung bereits als `{wert}`-Beispiel einer gefundenen
   Zelle angenommen hat, gelten in der Gegenrichtung als erklärt (wie Kontotexte). Begründung: die Werte sind echte
   Prognosen und ändern Form täglich (Uhrzeit-Marke, Wort, Emoji); eine Besitzer-Liste je Text wäre bei jedem
   Lauf veraltet. Das Element selbst ist in der Hinrichtung geprüft.
5. **#3419 Mockup:** Temperatur-SMS als Sperrzelle „kein Kürzel“ (Trip), Legende zusammengeführt
   („Tagestiefstwert/Tageshöchstwert“, „L gefühlt/D gefühlt“, „FL“ entfällt; Orte „Tagestiefstwert/Tageshöchstwert“
   wie live), Kurz-Zusammenfassung + Großwetterlage als Trip-Blöcke, E-Mail-Format auch bei Orten, nach #3364
   Kennzeichnung „nur morgens“/„nur abends“ (Live-Stand prüfen), SMS-Beispielzeile in Live-Form.
6. **#3419 Seed:** Region „Münsterland“; die eine Vorlagen-Abweichung des Seed-Trips finden und beheben (Seed an
   Vorlage) oder, falls live korrekt, Mockup angleichen; Seed auf Staging neu laufen lassen (idempotent).
7. **Morgen-/Abend-Briefing (Orte):** Ausblick-Beschriftungen ins Soll aufnehmen, Rolle wie live (sichtbar,
   `aria-hidden`); kleinster Eingriff: Generator nimmt sichtbare `aria-hidden`-Beschriftungen mit Buchstaben
   nur für diese Schalter-Beschriftung auf, oder Besitzer-Eintrag mit Begründung — Entscheid in der Spec.

## Risiken

- Elementliste wird vollständig neu erzeugt: unbeabsichtigte Änderungen außerhalb „Wetter“ ⇒ Diff auf
  geänderte Abschnitte prüfen; bestehende Elementlisten-Tests (`elementliste_aktuell`, `_en_zuordnung_2968`,
  `_uebersicht_2969`, `test_2913_c2_besitzerliste`) laufen mit.
- Abgleich-Logik ist Prüfwerkzeug: zu lockere Regeln verstecken echte Fehler ⇒ Mutationsprobe Pflicht
  (Zeilenbindung, verbrauchte Beispieltexte nur für gefundene `{wert}`-Elemente derselben Seite).
- Seed läuft gegen Staging-Prüfkonto (nie Prod), idempotent, Read-Modify-Write.
- Live-Karte bleibt unverändert (kein Produktcode).
