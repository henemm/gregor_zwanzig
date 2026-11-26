---
entity_id: feat_3419_elementliste_nachzug
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: paket-3419-elementliste-nachzug
tags: [was-steht-wo, elementliste, abgleich, mockup, seed, "#3419", "#3420", "#3421", "#3422", "#3037", "#2795"]
---

# Elementlisten-Nachzug „Was steht wo“ (Paket #3419, #3420, #3421, #3422)

## Approval

- [ ] Approved

## Purpose

Die Abnahme #3037 (Lauf `--abnahme --scope wetter/normal`) fand 185 (Deutsch) bzw. 173 (Englisch) Abweichungen ohne Besitzer. Die Live-Karte „Was steht wo“ ist richtig und bleibt unverändert. Ursachen liegen im Soll-Bild (Mockup Fassung 4 steht hinter freigegebenen Entscheidungen zurück), in drei Lücken des Prüfwerkzeugs (Kaskade bei Zellmustern, feste Grenzwerte im Prüfdatensatz, englische Gegenrichtung) und im Seed des Staging-Prüfkontos. Dieses Paket zieht alles nach, damit der Lauf für `wetter/normal` in beiden Sprachen ohne Abweichung ohne Besitzer endet. Es ist ein Paket für vier Issues: #3419 (Hauptissue), #3420, #3421, #3422; alle sind Nebenbefunde der Abnahme #3037 und Teil von #2795.

## Source

- **File:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, `docs/context/einstellungen_neu/elementliste.json`, `docs/context/einstellungen_neu/elementliste_besitzer.json`, `frontend/e2e/elementliste_abgleich_logik.ts`, `scripts/elementliste_aus_mockup.ts`, `scripts/staging_pruefkonto_mockupdaten.py`
- **Identifier:** Abgleich `bewerteAbschnitt` (Cursor `zuletzt`), `wetterOverrides`, `erwartungGegenrichtung` / `beispielForm`, `findeZusaetzliche`; Mockup `sperre()`, `LEG_TRIP` / `LEG_ORTE`, `blockEinst()`, `kanalEinst()`, `TRIP_METRICS` / `ORTE_METRICS`; Seed `display_config.region`

Schicht: Test-/Werkzeug-Schicht (Skripte, E2E-Hilfen, Mockup-Dokument, Seed). Kein Frontend-Produktcode, kein Go, kein Python-Core. Live-Referenz (nur lesen, nicht ändern): `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`, `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts`, `src/services/placements_view_service.py`.

Querschnitt: Trip/Ortsvergleich-Teilung unberührt (keine neue Komponente). Mandantentrennung: Der Seed schreibt nur in das Staging-Prüfkonto, `user_id` kommt aus dem Login, nie `"default"`; Read-Modify-Write, nie Prod. Kanäle: Alle vier bleiben Gegenstand des Soll-Bilds, es ändert sich kein Ausgabeinhalt.

## Estimated Scope

- **LoC:** ~350 netto handgeschrieben, dazu mechanisch neu erzeugte Elementliste
- **Files:** ~9 handgeschrieben
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/paket-3419-elementliste-nachzug.md` | Kontext | Ursachenanalyse und Rohberichte (verbindlich) |
| `docs/specs/modules/feat_3154_karte_abgleich.md` | Spec | Vorbild (Mockup angleichen, Elementliste neu erzeugen, Seed, `{wert}`-Muster) |
| `docs/specs/modules/feat_3037_was_steht_wo_abnahme.md` | Spec | Abnahme-Werkzeug, Soll/Ist-Bild, Lauf `--abnahme` |
| #3373 | Issue | Temperatur in SMS im Trip gesperrt („kein Kürzel“) |
| #3284 | Issue | Kürzel-Legende zusammengeführt |
| #3036 | Issue | Kurz-Zusammenfassung und Großwetterlage als eigene Trip-Blöcke |
| #3059 | Issue | E-Mail-Format-Zeile auch bei Orten |
| #3364 | Issue | Kennzeichnung „nur morgens“ / „nur abends“ |
| #3192 | Issue | Gültigkeitsregel der Grenzen (AC-1 bleibt erfüllt) |
| `docs/context/einstellungen_neu/daten/metrik_namen.json` | Daten | EN-Metriknamen-Schnappschuss (#3154) |
| `docs/runbooks/staging_pruefkonto_seed.md` | Runbook | Seed-Aufruf, Prüfkonto-Login |
| mockup-bildpruefer | Agent | Soll/Ist-Bild-Abnahme |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY | Soll-Nachzug: Sperrzelle Temperatur-SMS, Legende, Trip-Blöcke, E-Mail-Format bei Orten, SMS-Beispielzeile, „nur morgens/abends“, Briefing-Beschriftung bei Orten |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (generiert) | Neu erzeugt mit `scripts/elementliste_aus_mockup.ts`, keine Handpflege |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Nur falls nötig: Besitzer-Eintrag mit Begründung und Verweis (Briefing-Beschriftung, falls Generator sie nicht aufnimmt) |
| `scripts/elementliste_aus_mockup.ts` | MODIFY (bedingt) | Nur falls für die Briefing-Beschriftung nötig |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | Zeilenbindung der Zellmuster (#3420), Grenzen aus Mockup-Werten (#3421), EN-Gegenrichtung (#3422), Beispielwerte als erklärt (#3419 Nr. 6) |
| `frontend/e2e/elementliste_abgleich_logik.test.ts` | MODIFY | node --test Kern-Schicht zu AC-1 bis AC-6 |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY | Grenzen-Prüfdatensatz aus Mockup-Werten |
| `scripts/staging_pruefkonto_mockupdaten.py` | MODIFY | Region „Münsterland“; Vorlagen-Abweichung des Seed-Trips beheben |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` | MODIFY | Test zu Region und Vorlagen-Übereinstimmung |
| bestehende Elementlisten-Tests (`elementliste_aktuell`, `_en_zuordnung_2968`, `_uebersicht_2969`, `test_2913_c2_besitzerliste`) | MODIFY (bei Bedarf) | Nachziehen an die neu erzeugte Liste |

Nicht im Scope: Live-Karte, Backend, Produktcode jeder Art.

## Definition of Done

- [ ] Spec freigegeben, Tests rot vor Umsetzung, dann grün
- [ ] Mockup nachgezogen, Elementliste neu erzeugt, Diff nur in den erwarteten Abschnitten
- [ ] Seed angepasst und auf Staging neu gelaufen (idempotent, nie Prod)
- [ ] Staging-Lauf `--abnahme --scope wetter/normal` in DE und EN: 0 ohne Besitzer, Vorher/Nachher als Artefakt unter `docs/artifacts/paket-3419-elementliste-nachzug/`
- [ ] Adversary mit Mutationsprobe (Zeilenbindung, verbrauchte Beispieltexte nur für gefundene `{wert}`-Elemente derselben Seite, Grenzen-Datensatz) rötet je einen Test
- [ ] PR mit allen 6 CI-Checks grün, Deploy, Selftest, Issues #3419 bis #3422 geschlossen

## Implementation Details

1. **#3420 Zeilenbindung:** Zellmuster-Elemente (`{metrik} in|im <Stelle>`) gehören zu einer Tabellenzeile; die Zeile im Soll ist der gleiche Metrikteil im `text_de` (die Liste ist immer DE-erzeugt). Ist das vorige Zellmuster-Element derselben Zeile gefunden, muss der Live-Treffer denselben Metrikteil tragen wie dessen Live-Treffer. Sonst meldet genau dieses Element „Text nicht sichtbar“, der Cursor `zuletzt` bleibt stehen. So entsteht keine Kaskade „Reihenfolge im Abschnitt“ mehr.
2. **#3421 Grenzen:** `wetterOverrides` setzt die Grenzwerte des Mockups (wie in Elementliste und Mockup `TRIP_METRICS`, `ORTE_METRICS`, inklusive Minuswerte) statt fester 1/2/3 bzw. 10/20/30. Gültigkeitsregel #3192 AC-1 (aufsteigend, untere unter oberer Grenze, `allowed_sides`) bleibt erfüllt. Eine Metrik ohne Mockup-Wert behält einen gültigen Ersatz.
3. **#3422 EN-Gegenrichtung:** Für `{wert}`-Beispiele im EN-Lauf wird die Form aus der englischen Form gebildet: Der Metriknamen-Teil wird über den Schnappschuss `metrik_namen.json` (DE-Name zu EN-Name) übersetzt, Zahlen sind beliebig (Beispiel: „Gusts 62 km/h“).
4. **#3419 Nr. 6 Beispielwerte:** Live-Texte, die die Hinrichtung als `{wert}`-Beispiel eines gefundenen Elements angenommen hat, gelten in der Gegenrichtung als erklärt (wie Kontotexte), nur für dieselbe Seite (Kontext und Reiter). Begründung: Echte Prognosewerte ändern ihre Form täglich (Uhrzeit-Marke, Wort, Emoji), eine Besitzerliste je Text wäre bei jedem Lauf veraltet. Ein nicht angenommener Text bleibt „zusätzlich“.
5. **#3419 Mockup** (optisches Soll sonst unverändert, Vorgehen wie #3154):
   - Temperatur in SMS im Trip als Sperrzelle „kein Kürzel“ (#3373, live `placements_view_service.py` ~301 bis 318).
   - Kürzel-Legende wie live zusammengeführt (#3284: „Tagestiefstwert/Tageshöchstwert“, „L gefühlt/D gefühlt“, „FL“ entfällt; Orte wie live).
   - Kurz-Zusammenfassung und Großwetterlage als eigene Trip-Blöcke mit Hinweistexten wie live (#3036, `WasStehtWoKarte.svelte`).
   - E-Mail-Format-Zeile auch bei Orten (#3059, `kanalEinst()` nicht mehr nur bei `!O()`).
   - SMS-Beispielzeile in Live-Form.
   - Kennzeichnung „nur morgens“ / „nur abends“ (#3364 ist live; Live-Stand im Code nachsehen und abbilden).
   - Morgen-/Abend-Briefing-Beschriftung neben den Ausblick-Schaltern bei Orten: kleinster sauberer Weg ins Soll, damit der Abgleich sie kennt. Überspringt der Generator `aria-hidden` (`elementliste_aus_mockup.ts` ~514), ist ein Besitzer-Eintrag mit Begründung zulässig.
   - Danach Elementliste neu erzeugen (`scripts/elementliste_aus_mockup.ts`), bestehende Elementlisten-Tests nachziehen.
6. **#3419 Seed:** Region „Münsterland“ statt „Westfalen“ (`staging_pruefkonto_mockupdaten.py` ~335). Die eine Vorlagen-Abweichung des Seed-Trips gegenüber „Alpen-Trekking“ ist ermittelt: Bewölkung (`cloud_total`) ist in der Vorlage an, im freigegebenen Soll-Bild im Trip aber unter „Nicht im Briefing“ (Mockup `TRIP_OFF`), der Seed folgt dem Soll-Bild. Die Metrik-Auswahl des Soll-Bilds bleibt unverändert (PO-freigegeben); stattdessen zeigt der Vorlagen-Picker des Soll-Bilds im Trip „1 Abweichung“, wie live (Tech-Lead-Entscheid 26.11.2026: das Soll folgt dem eigenen Zustand, die Vorlage wird nicht still verändert). Seed auf Staging neu laufen lassen (idempotent, Read-Modify-Write, nie Prod).
7. **Abschluss:** Staging-Lauf `--abnahme --scope wetter/normal` ohne Abweichung ohne Besitzer; verbleibende Reste nur mit begründetem Besitzer-Eintrag und Verweis.

## Expected Behavior

- **Input:** Mockup Fassung 4 (nachgezogen), neu erzeugte Elementliste, angepasster Abgleich, neu befülltes Staging-Prüfkonto.
- **Output:** Lauf `--abnahme --scope wetter/normal` meldet in DE und EN keine Abweichung ohne Besitzer.
- **Side effects:** Das Staging-Prüfkonto wird neu befüllt (Region, Vorlage). Kein Produktivsystem betroffen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Abgleich (node --test): GIVEN ein künstlich fehlendes Kästchen in einer Zellmuster-Zeile WHEN bewertet wird (DE und EN) THEN entsteht genau eine Abweichung, keine Reihenfolge-Kaskade
- [ ] Abgleich (node --test): GIVEN der Live-Treffer hat einen anderen Metrikteil als der Vorgänger derselben Zeile WHEN bewertet wird THEN meldet genau dieses Element „Text nicht sichtbar“ und der Cursor bleibt stehen
- [ ] Abgleich (node --test): GIVEN die Mockup-Grenzwerte inklusive Minuswerte WHEN der Prüfdatensatz gebaut wird THEN enthält er diese Werte und erfüllt die Gültigkeitsregel #3192 AC-1; Metrik ohne Mockup-Wert bekommt einen gültigen Ersatz
- [ ] Abgleich (node --test): GIVEN der EN-Beispieltext „Gusts 62 km/h“ WHEN die EN-Gegenrichtung läuft THEN gilt er als erklärt; ein EN-Text mit falschem Metriknamen bleibt „zusätzlich“
- [ ] Abgleich (node --test): GIVEN ein von der Hinrichtung angenommener `{wert}`-Text WHEN die Gegenrichtung läuft THEN gilt er als erklärt, aber nur auf derselben Seite; ein nicht angenommener Text und ein gleicher Text auf anderer Seite bleiben „zusätzlich“
- [ ] Generator/Liste (node --test): GIVEN das nachgezogene Mockup WHEN die Elementliste erzeugt wird THEN enthält sie Sperrzelle „kein Kürzel“, zusammengeführte Legende, Trip-Blöcke Kurz-Zusammenfassung und Großwetterlage, E-Mail-Format bei Orten; Prüfsummen-Test grün
- [ ] Seed (pytest `tests/tdd/test_staging_pruefkonto_mockupdaten.py`): GIVEN der Seed WHEN der Payload gebaut wird THEN lautet die Region „Münsterland“, der Seed-Trip weicht von „Alpen-Trekking“ genau in Bewölkung ab (wie das Soll-Bild) und das Soll-Bild zeigt im Trip-Picker „1 Abweichung“

## Acceptance Criteria

- **AC-1:** Given in einer Tabellenzeile der Karte fehlt im Live-Bild genau ein Kästchen / When der Elementlisten-Abgleich den Abschnitt „Was steht wo“ prüft / Then meldet er in Deutsch und in Englisch genau eine Abweichung für dieses Kästchen und keine Folge-Abweichungen für die übrigen Zeilen.
  - Test: node --test in `elementliste_abgleich_logik.test.ts` mit künstlich entferntem Kästchen (DE und EN); Mutationsprobe: ohne Zeilenbindung entsteht wieder die Kaskade.

- **AC-2:** Given der Abgleich prüft die Grenzen-Abschnitte mit dem Prüfdatensatz / When der Datensatz die Grenzwerte des Soll-Bilds (auch negative Werte wie -10 oder -300) übernimmt / Then erscheinen diese Zahlen live in der Form des Soll-Bilds (Vorzeichen und Zahlmuster; der Abgleich prüft Grenzwerte bewusst als Muster `{zahl}`), der Datensatz bleibt nach der Gültigkeitsregel #3192 zulässig, und stimmt eine Metrik ganz mit der Vorlage überein, rückt ihr Rot um 1 nach außen, damit live wie im Soll-Zustand „mit Abweichung“ der Satz „Abweichend von der Vorlage“ erscheint (Tech-Lead-Entscheid 26.11.2026, Adversary F004).
  - Test: node --test auf den Datensatz-Aufbau (Mockup-Werte, Minuswerte, Gültigkeit, Ersatz bei fehlendem Mockup-Wert); Staging-Lauf der Grenzen-Abschnitte ohne Abweichung.

- **AC-3:** Given der Abgleich läuft auf Englisch und ein Beispielwert steht live als „Gusts 62 km/h“ / When die Gegenrichtung die englische Form bildet / Then gilt dieser Text als erklärt, während ein Text mit falschem Metriknamen weiterhin als zusätzlich gemeldet wird.
  - Test: node --test mit EN-Beispieltext „Gusts 62 km/h“ und einem Negativfall; Mutationsprobe: ohne Namensübersetzung bleibt der Text zusätzlich.

- **AC-4:** Given die Hinrichtung hat einen Live-Text als Beispielwert eines gefundenen Elements angenommen / When die Gegenrichtung nach zusätzlichen Texten sucht / Then gilt dieser Text auf derselben Seite als erklärt, ein nicht angenommener Text sowie derselbe Text auf einer anderen Seite bleibt zusätzlich.
  - Test: node --test mit drei Fällen (angenommen und gleiche Seite, nicht angenommen, andere Seite); Mutationsprobe: gelockerte Regel rötet den Negativfall.

- **AC-5:** Given das nachgezogene Soll-Bild / When Temperatur in SMS im Trip, die Kürzel-Legende, die Blöcke Kurz-Zusammenfassung und Großwetterlage, die E-Mail-Format-Zeile bei Orten, die SMS-Beispielzeile, die Kennzeichnung „nur morgens/nur abends“ (nur wo sie im Zustand des Prüfkontos sichtbar ist; im Seed führen beide Briefings dieselben Metriken, daher erscheint sie dort nicht und wird nicht abgebildet, Adversary F005) und die Briefing-Beschriftung bei Orten betrachtet werden / Then zeigt das Soll-Bild sie so, wie die Live-Karte sie heute zeigt, und die Elementliste enthält sie.
  - Test: node --test auf die neu erzeugte Elementliste (Elemente vorhanden, Prüfsumme stimmt); Soll/Ist-Bild-Abnahme (Trip, Orte) durch mockup-bildpruefer ohne offenen Befund.

- **AC-6:** Given das Staging-Prüfkonto wird neu befüllt / When der Seed zweimal läuft / Then lautet die Region der Orte „Münsterland“, der Seed-Trip weicht von der Vorlage „Alpen-Trekking“ genau in Bewölkung ab, das Soll-Bild zeigt dazu im Trip „1 Abweichung“ wie die Seite, und der zweite Lauf ändert nichts.
  - Test: pytest `tests/tdd/test_staging_pruefkonto_mockupdaten.py` (Region, Vorlagen-Übereinstimmung, Idempotenz); Live-Sicht auf Staging im Trip und bei den Orten.

- **AC-7:** Given alle Änderungen sind auf Staging ausgeliefert / When der Lauf `--abnahme --scope wetter/normal` für Deutsch und Englisch läuft / Then meldet er in „was-steht-wo“, „kopf“ und den Grenzen-Abschnitten keine Abweichung ohne Besitzer, insgesamt 0 ohne Besitzer, verbleibende Reste nur mit begründetem Besitzer-Eintrag und Verweis.
  - Test: Staging-Lauf im /e2e-verify mit Rohbericht je Sprache unter `docs/artifacts/paket-3419-elementliste-nachzug/nachher/`; Vergleich mit dem Rohbericht „vorher“ (185 DE, 173 EN).

## Known Limitations

- Die Gegenrichtung erklärt Beispielwerte nur über die Hinrichtung; ein Beispielwert, der live erscheint, aber dessen Element im Soll fehlt, bleibt zusätzlich.
- Die Briefing-Beschriftung bei Orten kann ersatzweise per Besitzer-Eintrag gedeckt werden, falls der Generator `aria-hidden` nicht aufnimmt.
- Werte der Elementliste bleiben DE-erzeugt; EN wird über den Namens-Schnappschuss abgeleitet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Prüfwerkzeug, Soll-Bild und Seed werden an bestehende Entscheidungen angeglichen (ADR-0124/0125, #3154); keine Entscheidungsfläche des Produkts ändert sich.

## Changelog

- 2026-11-26: Initial spec created
