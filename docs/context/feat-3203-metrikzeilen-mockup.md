# Context: #3203 Reiter Wetter, Metrik-Zeilen nach Mockup Fassung 4

## Request Summary
Issue #3203 (Epic #2913, Abspaltung aus #3151): 19 Besitzer-Einträge `#3203` in `docs/context/einstellungen_neu/elementliste_besitzer.json` (2 Abschnitt `metriken` Trip/Orte = Index 95/119; 17 `zusaetzlich` = Index 147-155, 159-165, 168). Mockup Fassung 4 ist Soll. Zählwächter: `tests/test_2913_c2_besitzerliste.py:141` (`"#3203": 19`).

**Hauptbefund:** Die Live-Texte entsprechen dem Mockup bereits fast vollständig (Katalog DE/EN vorhanden). Die Abweichungen sind überwiegend ein Messartefakt des Abgleichs: `frontend/e2e/elementliste-abgleich.staging.spec.ts:134` überspringt jedes Element unter `[aria-hidden="true"]`. Live versteckt genau die Skala-Zahlen, die Gewitter-Stufenwörter und den Trennpunkt „·“ vor Screenreadern, das Mockup nicht. Echte Inhaltsunterschiede sind nur Vorbote-Satz/„Kein Alarm“ (Orte) und „:00“ (beide fachlich begründet).

## Related Files
- Mockup: `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` Z. 380 (`band`: Gewitter-Ticks keins/mittel/hoch), Z. 426-445 (`why`, `greenText`), Z. 447-475 (`rowMetric`; Z. 470 Untertitel, Z. 471 `<span class="gr">· grün…</span>`), Z. 335-343 Orte-Metriken, Z. 523/672 Zeit-Inputs.
- Ist: `frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte` (Z. 57-66, „·“ mit `aria-hidden="true"` Z. 63), `.../AmpelLeiste.svelte` (Z. 41-52: `wt-marken` mit `aria-hidden="true"`, Stufen `wetter.gewitter.keins|mittel|hoch` Z. 44-46), `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` (`gruenZeile` Z. 293, `hinweisSchluessel` Z. 322, `untertitel` Z. 329, `erklaersatz` Z. 350), `.../shared/wetter-tab/ampelLeiste.ts` (Skala-Zahlen berechnet, `marken`), `frontend/src/lib/components/molecules/UhrzeitFeld.svelte:100` (festes „:00“), `.../organisms/wetter-tab/AnpassenKarte.svelte:32,35`.
- Katalog: `frontend/src/lib/i18n/messages/{de,en}/wetter.json` Z. 69-72 (`wetter.gruen.*`), 77-85 (`wetter.erklaer.*`), 86-88 (`wetter.gewitter.*`), 46-47 und 55 (Vorbote/kein Alarm), 57-68 (`wetter.hinweis.*`).
- Abgleich: `frontend/e2e/elementliste_abgleich_logik.ts`, `frontend/e2e/elementliste-abgleich.staging.spec.ts:124-140` (`sichtbareTexte`), Bericht `docs/artifacts/feat-3151-pruefkonto-abgleich/abgleich-de.json` (Stand vor der Umhängung).
- Metrik-Eigenschaften: `src/app/metric_catalog.py` Z. 1295-1346 (`_REITER_WETTER`), `is_precursor` bei humidity, rain_probability, wind_chill, dewpoint, cloud_total, pressure.
- Seed: `scripts/staging_pruefkonto_mockupdaten.py` (`_TRIP_REIHE` Z. 69-71, `_ORTE_METRIKEN` Z. 75-77, `soll_wetter`, `soll_vergleich`).

## Existing Patterns
- Trip/Orte teilen EINE Komponente (`MetrikZeile`, `AmpelLeiste`); jeder Fix gilt automatisch für beide, kein Kontext-Zweig nötig (Ratsche `context_herkunft_zweige_eingefroren`).
- Texte nur über Katalog (ADR-0104); Elementlisten-Muster `· grün: {von} bis {bis} {einheit}`.
- Besitzer-Einträge werden beim Beheben abgeräumt, Zählwächter neu gesetzt (Vorbild #3202, Kommentar in `tests/test_2913_c2_besitzerliste.py` Z. 133-136).
- Bewusste Abweichungen gehen in `ausnahmen` des Besitzer-JSON, je mit `spec`.

## Dependencies
Abgleich-Lauf gegen Staging (Playwright, Prüfkonto-Seed). `elementliste.json` bleibt unverändert (Mockup = Soll). Kein Backend, keine Datenänderung.

## Existing Specs/ADRs
- ADR-0112 (Mockup-getriebene Scheiben, Bildprüfung), ADR-0104 (i18n), ADR-0095 (hier nicht berührt).
- `docs/specs/modules/fix_2913_metrikliste_mockup.md`, `feat_2794_s3a_teil2_leiste.md`, `feat_2794_s3a_teil3_wetter.md`, `feat_2913_scheibe_c_wetter_rest.md` (Punkt 3/AC-5: Stundenraster mit fester Minute 00, Quelle des „:00“), `feat_2913_abgleich_ganzseite.md`, `feat_3151_pruefkonto_abgleich.md`.
- #2799 (offen, Ampel weitere Metriken, ADR-0106 Pkt. 5/6) und #2867 (offen, „Vorboten-Markierung an Konzept angleichen“). #2867 ist im Code erledigt (wind_chill, dewpoint, cloud_total, pressure tragen `is_precursor=True`), das Issue steht nur noch offen. Keine der beiden Entscheidungen legt die Position des Satzes „Nur im Briefing gefärbt …“ fest; sie bestimmen, WELCHE Metriken Vorboten sind.

## Risks
- aria-hidden entfernen ändert die Screenreader-Ausgabe (Zahlen/Stufenwörter werden vorgelesen). Segmente haben bereits `role="img"` mit Farbname; vertretbar, da das Mockup (PO-Soll) kein aria-hidden hat. Die Alternative (Abgleich zählt aria-hidden mit) schwächt den Wächter.
- Bestehende Tests, die das aria-hidden voraussetzen könnten: `frontend/src/lib/components/organisms/__tests__/fix2913_metrikliste_mockup.test.ts` (Z. 16, 257: „grün“-Span mit Trennpunkt), `frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts` (Z. 117, 373), `s3a2794-teil3-zeilen|gewitter|design.spec.ts`. Vor dem Umbau lesen.
- Design-Wächter (Kontrast): keine neuen Farben/Token, nur Sichtbarkeit für Hilfstechnik.
- Zählwächter muss in derselben Änderung angepasst werden.

## Analysis
### Type: Feature (Angleich an Mockup; reine Darstellung plus Besitzerliste)

### Root Cause je Punkt
1. **Grünbereich (14 Einträge, DE 7 + EN 7; Index 148-154, 159-165):** Soll `· grün: 2 bis 27 °C` ist EIN Text im `<span class="gr">` (Mockup Z. 471). Live rendert `MetrikZeile.svelte:63` `<span aria-hidden="true">·</span> grün: …`; der Abgleich verwirft den Punkt, Ist = „grün: …“ (Listeneintrag „nicht sichtbar“, Live-Text „zusätzlich“). Katalog `wetter.gruen.*` ist korrekt ohne Punkt. Fix: aria-hidden am „·“ entfernen. Reine Darstellung.
2. **Gewitter-Stufen keins/mittel/hoch (je 3 pro Kontext und Zustand, Besitzer = Abschnitt-Eintrag):** Live vorhanden (`AmpelLeiste.svelte:44-46`, EN none/medium/high), aber im Container `wt-marken--stufen` mit `aria-hidden="true"`. Stufen sind feste drei Zonen (`gewitterLeiste`), Wörter aus dem Katalog, keine neuen Daten. Fix: aria-hidden vom Container entfernen.
3. **Skala-Zahlen -10 / -15 (Trip Ordnung 11, Orte 11):** Zahlen werden berechnet (`leisteVon` aus den Vorlagen-Grenzen), nicht fest. Positive Zahlen werden zufällig in anderem Text („über 30 °C“) „gefunden“, negative nicht, daher nur diese gemeldet. Ursache wieder aria-hidden an `wt-marken` (Z. 49).
4. **Alarm-Text-Reihenfolge (Trip 13, Orte 13):** Folgefehler von 3: Element 12 (z. B. „-3“) wird erst im Alarm-Satz („unter -3 °C“) gefunden, daher Satz 13 „vor Element 12“. Verschwindet mit Fix 3 (im Abgleich-Lauf bestätigen).
5. **Vorbote-Satz (Trip 106, Orte 84, „Reihenfolge“):** Echter Inhaltsunterschied, anders als im Issue beschrieben. Mockup: jede Metrik mit `m[7]===null` bekommt „Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.“, auch Tiefe Wolken (Trip) und Sonnenstunden (Orte). Live (`ampelModell.ts:351`): Satz nur bei `is_precursor && !alertable`; `cloud_low` und `sunshine` sind `alertable=false`, aber keine Vorboten (`_REITER_WETTER`, `metric_catalog.py`) und zeigen „Kein Alarm. Die Farbe erscheint nur im Briefing.“ (`wetter.erklaer.nie`). Der Trip-Satz steht dadurch „an anderer Stelle“ (Eintrag 106 fehlt live bei Tiefe Wolken, wird bei einer früheren Vorbote-Zeile gefunden). Fachlich ist Live richtiger. Label „kein Alarm“ vs. „kein Alarm (Vorbote)“ stimmt zwischen Mockup und Live überein.
6. **„Kein Alarm. Die Farbe erscheint nur im Briefing.“ (Orte, DE+EN, Index 155/168):** Folge von 5 (Sonnenstunden live „nie“). Im Trip fällt es nicht auf, weil der Satz dort durch UV-Index (Elementliste 112) schon vorkommt. Gleiche Entscheidung wie 5.
7. **„:00“ (Index 147, Tagesfenster in der Anpassen-Karte):** Live = `UhrzeitFeld` im Stundenraster mit festem Text „:00“ (Spec `feat_2913_scheibe_c_wetter_rest.md` Punkt 3/AC-5, Felder `day_window_*_hour`); Mockup Z. 523 zeigt Inputs „06:00“/„20:00“. Beabsichtigte, freigegebene Abweichung, fachlich nicht Teil der Metrik-Zeilen.

Besitzer je Punkt: Abschnitt `metriken` 2 (Trip, Orte; tragen Gewitter-Stufen, Skala, Reihenfolge, Vorbote); „:00“ 1; Grünbereich 14; „Kein Alarm“ Orte 2 (DE+EN). Summe 19.

### Affected Files (with changes)
- `frontend/src/lib/components/organisms/wetter-tab/AmpelLeiste.svelte`: aria-hidden an beiden `wt-marken`-Containern entfernen (ca. 2 LoC).
- `frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte`: aria-hidden am „·“ entfernen (1 LoC).
- `docs/context/einstellungen_neu/elementliste_besitzer.json`: 2 Abschnitt- und 14 Grün-Einträge abräumen; „:00“ und (je nach Entscheidung) Vorbote/„Kein Alarm“ als `ausnahmen` mit `spec` eintragen (ca. 40 LoC).
- `tests/test_2913_c2_besitzerliste.py:141`: `"#3203": 0` plus Kommentar (3 LoC).
- Neuer Test (RED zuerst, Nutzersicht): Skala-Zahlen, Gewitter-Stufenwörter und „·“ liegen nicht unter `[aria-hidden]`, z. B. in `fix2913_metrikliste_mockup.test.ts` (ca. 40 LoC); vorhandene Erwartungen bei Bedarf anpassen (ca. 10 LoC).
- Variante „Mockup korrigieren“ (Vorbote-Satz): `mockup-hub-fassung4.html` Z. 428 auf `m[2].includes('Vorbote')`, `elementliste.json` neu erzeugen (`scripts/elementliste_aus_mockup.ts`).
- i18n-Katalog: keine Änderung (alle Schlüssel DE+EN vorhanden).

### Scope Assessment
Rund 5-6 Dateien, ca. 100-130 LoC (ohne generierte Elementliste), unter 250 LoC. Die Punkte hängen zusammen (ein Abgleich-Lauf, ein Besitzer-Abbau): keine Aufteilung nötig. Nur wenn „Mockup korrigieren“ gewählt wird, den Vorbote-Teil (Mockup plus generierte Elementliste) als eigenes Kind-Issue abspalten.

### Technical Approach
1. Spec `docs/specs/modules/feat_3203_metrikzeilen_mockup.md` mit ACs (Given Reiter Wetter Trip/Orte, When Zeile gerendert, Then Skala-Zahlen, Gewitter-Stufenwörter und „·“ sind sichtbarer Text; Abgleich DE+EN meldet keinen #3203-Eintrag mehr).
2. RED: Test auf aria-hidden-Freiheit (Renderer-DOM, Nutzersicht).
3. GREEN: aria-hidden entfernen (3 Stellen), Besitzer abräumen, Ausnahmen eintragen, Zählwächter anpassen.
4. Abgleich DE+EN gegen Staging neu laufen lassen: erwartet 0 `#3203`, keine herrenlosen Einträge. Mutationsprobe: aria-hidden wieder setzen muss Test röten.
5. ADR-0112-Bildprüfung Reiter Wetter, Trip und Orte (Soll/Ist-Bild an Henning).

### Befunde gegen den Plan
- Das Issue beschreibt „Gewitter-Stufen fehlen“, „Skala“, „Reihenfolge“ als Darstellungsfehler; tatsächlich sind sie vorhanden, nur für den Abgleich ausgeblendet. Der Fix ist kleiner als gedacht.
- #2867 ist im Code bereits umgesetzt, Issue offen: beim Abschluss prüfen und schließen. Der Satz-Unterschied betrifft `cloud_low`/`sunshine`, nicht die in #2867 genannten Metriken.
- Der Bericht `docs/artifacts/feat-3151-pruefkonto-abgleich/` stammt von vor der Umhängung; Einzelstatus nach Neulauf prüfen.
- „:00“ gehört fachlich zum Tagesfenster, liegt nur wegen der Besitzerliste hier.

### Open Questions
1. Vorbote-Satz bei Tiefe Wolken (Trip) und Sonnenstunden (Orte): Live „Kein Alarm. Die Farbe erscheint nur im Briefing.“, Mockup „Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.“. Empfehlung: Live behalten (beide sind keine Vorboten) und das Mockup in dieser Zeile korrigieren (Textentscheidung für Henning per AskUserQuestion). Alternative: Mockup bleibt Soll, Live-Satz wird angeglichen (fachlich ungenau, da „Vorboten“ falsch bezeichnet).
2. „:00“: keine PO-Frage nötig. Empfehlung: Ausnahme mit Verweis auf die freigegebene Stundenraster-Spec; nur falls Henning das Mockup auf Stundenraster umstellen will, abräumen.

## Entscheidungen (21.11.2026)
1. **PO:** Vorboten-Satz bleibt wie live (nur echte Vorboten); Tiefe Wolken/Sonnenstunden behalten „Kein Alarm. Die Farbe erscheint nur im Briefing.“ → Mockup Fassung 4 an dieser Stelle angleichen, Elementliste neu erzeugen.
2. **Tech-Lead:** aria-hidden NICHT aus dem Produkt entfernen (Screenreader-Ausgabe der Segmente mit role=img bleibt). Stattdessen den Elementlisten-Abgleich (frontend/e2e/elementliste-abgleich.staging.spec.ts:134) so korrigieren, dass sichtbarer Text unter aria-hidden zählt (Sichtbarkeit statt Barrierefreiheits-Attribut), ohne neues Rauschen durch reine Icons/SVG. Wirkung vorher/nachher im Abgleich messen (alle Reiter, keine neuen Abweichungen außerhalb #3203).
3. **Tech-Lead:** „:00“ (Tagesfenster) = begründete Ausnahme laut Stundenraster-Spec feat_2913_scheibe_c_wetter_rest.md.
