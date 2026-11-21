---
entity_id: feat_3204_anzeige_metriken_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3204-anzeige-metriken-mockup
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, "#3204", "#2913"]
---

# Reiter Wetter (Trip): Anzeige-Metriken Tages-Tief/-Hoch ins Mockup Fassung 4

## Approval

- [ ] Approved

## Purpose

Die zehn Besitzer-Einträge `#3204` (Epic #2913) entstehen, weil die zwei Gehzeit-Metriken `temperature_day_low` und `temperature_day_high` in der App-Trip-Metrikliste stehen, im Mockup Fassung 4 aber fehlen. Die Metriken sind PO-beauftragte Nutzerfunktion (#1728) und bleiben. Das Mockup wird ergänzt (Tech-Lead-Entscheidung Option A, Kommentar in Issue #3204), und der Erklärsatz der App folgt dem Mockup-Wortlaut.

## Source

- **File:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (`TRIP_METRICS`, Z. 316-331; Erklärsatz Z. 427)
- **Identifier:** `TRIP_METRICS` und Schlüssel `wetter.erklaer.anzeige` in `frontend/src/lib/i18n/messages/{de,en}/wetter.json`

> Schicht: Mockup (Soll), Frontend-Textkatalog, generierte Elementliste und Besitzerliste. Kein Go-API-/Python-Core-Code; das Metrik-Register (`src/app/metric_catalog.py`) bleibt unverändert.
> Trip/Orts-Vergleich: Die Nur-Anzeige-Zeile ist geteilter Code (`MetrikZeile`, `ampelModell.ts`), der Erklärsatz gilt damit für beide Kontexte. Die zwei Metriken erscheinen nur im Trip; der Orts-Vergleich bietet sie bewusst nicht an (ADR-0011, Gehzeit-Exklusivität). Das ist Katalog-Verhalten, kein neuer Kontext-Zweig.
> Kanäle: keine Änderung an Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unberührt; SMS-Token L/D bleiben wie sie sind). Keine Nutzerdaten bewegt.

## Scope

**Im Scope**
- Mockup: Zeilen „Tages-Tiefsttemperatur (Gehzeit)“ und „Tages-Höchsttemperatur (Gehzeit)“ in `TRIP_METRICS`, Gruppe Temperatur, Reihenfolge wie in der App: Temperatur, Tiefsttemperatur Nacht, Tages-Tief, Tages-Hoch, Gefühlte Temperatur. Form wie Windrichtung (Nur-Anzeige-Flag): Untertitel „°C · nur Anzeige, keine Ampel“, Zeilenmitte „keine Ampel, nur Anzeige“.
- App: Erklärsatz `wetter.erklaer.anzeige` DE und EN an den Mockup-Wortlaut angleichen („… unten unter „Was steht wo“ ein.“). Nur über den Katalog (ADR-0104, `docs/reference/i18n_konventionen.md`).
- `elementliste.json` per `scripts/elementliste_aus_mockup.ts` neu erzeugen; Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Begründung nachziehen.
- Besitzerliste: zehn Einträge `#3204` abräumen; Zählwächter `tests/test_2913_c2_besitzerliste.py` auf `"#3204": 0`.
- Staging-Abgleich Reiter Wetter DE+EN und Soll/Ist-Bild des Trip-Reiters Wetter für den PO.

**Nicht im Scope**
- #3086 (Luftdruck „nur Anzeige“ vs. „nur im Briefing gefärbt“), #3091 (Gehzeit vs. Tagesfenster), Metrik-Logik, SMS-Token, Orte-Mockup (bleibt unverändert, ADR-0011), Metrik-Register und Namen im Katalog `wertebereiche.json`.

## Estimated Scope

- **LoC:** ca. +25/-15 (ohne generierte Elementliste)
- **Files:** 7 (Mockup, `de/wetter.json`, `en/wetter.json`, generierte `elementliste.json`, `elementliste_uebersicht_2969.test.ts`, `elementliste_besitzer.json`, `tests/test_2913_c2_besitzerliste.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | mockup | Soll des Reiters Wetter, hier um zwei Zeilen ergänzt |
| `scripts/elementliste_aus_mockup.ts` | script | Erzeugt `elementliste.json` deterministisch aus dem Mockup |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | catalog | Erklärsatz `wetter.erklaer.anzeige` (genutzt in `shared/wetter-tab/ampelModell.ts`) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Besitzer-Einträge `#3204` |
| `tests/test_2913_c2_besitzerliste.py` | test | Zählwächter je Besitzer |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | test | Prüfsumme der Elementliste |
| `src/app/metric_catalog.py` (`_REITER_WETTER`) | module | Quelle von Reihenfolge und Nur-Anzeige-Einstufung (nur gelesen) |
| Staging + Prüfkonto-Seed (`scripts/staging_pruefkonto_mockupdaten.py`) | system | Abgleich-Lauf DE+EN |
| `feat_3203_metrikzeilen_mockup.md` | spec | Vorgänger, gleiche Elementlisten-Mechanik |
| ADR-0011, ADR-0104, ADR-0112 | adr | Gehzeit-Exklusivität, Katalog-Texte, Mockup-Bildprüfung |

## Implementation Details

1. **Mockup:** zwei Zeilen nach `temperature_night` einfügen, im Format der Windrichtung-Zeile (Einheit `°C`, Hinweis „nur Anzeige, keine Ampel“, keine Grenzen, kein Alarm, Nur-Anzeige-Flag gesetzt). Anfangszustand **aktiv** (`on=true`): Nur so stehen Untertitel, Zeilenmitte, Erklärsatz und Reihenfolge im Mockup und damit in der Elementliste, wie AC-1/AC-2 es verlangen; das Prüfkonto zeigt sie live ebenfalls als aktive Zeilen (RED-Befund 21.11.). Gruppe `Temperatur`. Namen wortgleich zur App (`wertebereiche.json`).
2. **Katalog:** `wetter.erklaer.anzeige` DE: „Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein.“; EN sinngemäß mit dem englischen Abschnittsnamen aus `wetter.json` (Schlüssel für „Was steht wo“ im EN-Katalog verwenden, nicht neu erfinden).
3. **Elementliste und Prüfsumme:** Generator laufen lassen, keine Handpflege; die Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Kommentar „#3204: zwei Anzeige-Metriken ergänzt“ nachziehen.
4. **Besitzerliste:** zehn Einträge `#3204` entfernen; Zählwächter auf `"#3204": 0` mit Kommentar wie bei #3203.
5. **Wirkung messen:** Staging-Abgleich DE+EN Reiter Wetter vorher/nachher vergleichen; Soll/Ist-Bild (Mockup gegen Staging) erzeugen und dem PO zeigen.

## Expected Behavior

- **Input:** Mockup Fassung 4, Katalog DE/EN, Staging-Seite Reiter Wetter (Trip), Prüfkonto-Seed.
- **Output:** Abgleich meldet für Namen, Untertitel, Zeilenmitte und Erklärsatz der beiden Metriken keine Abweichung; keine herrenlosen Besitzer-Einträge.
- **Side effects:** Wechsel abweichend→gefunden in anderen Besitzern ist erlaubt; neue Abweichung ohne Besitzer ist es nicht. Produktverhalten (Metrik-Wahl, SMS L/D) unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Katalog-Test (Pflicht-Schlüssel DE/EN): `wetter.erklaer.anzeige` enthält „Was steht wo“ bzw. den englischen Abschnittsnamen und nicht mehr „je Liste“ (rot vor der Änderung).
- [ ] Elementlisten-Test (node --test): `elementliste.json` des Trips Reiter Wetter enthält die zwei Metrik-Namen, den Untertitel „°C · nur Anzeige, keine Ampel“ und die Zeilenmitte „keine Ampel, nur Anzeige“; Orte enthalten sie nicht.
- [ ] Reihenfolge-Test: Gruppe Temperatur im Mockup lautet Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte.
- [ ] `elementliste_uebersicht_2969.test.ts` grün mit begründeter neuer Prüfsumme.
- [ ] `tests/test_2913_c2_besitzerliste.py`: `"#3204": 0`, keine herrenlosen Einträge.
- [ ] Staging-Abgleich Reiter Wetter DE+EN vorher/nachher: Diff enthält nur Einträge `#3204` (abweichend→gefunden).

## Acceptance Criteria

- **AC-1:** Given der Trip-Reiter Wetter in Deutsch / When der Nutzer die Gruppe Temperatur liest / Then stehen dort „Tages-Tiefsttemperatur (Gehzeit)“ und „Tages-Höchsttemperatur (Gehzeit)“ zwischen Tiefsttemperatur Nacht und Gefühlter Temperatur, und das Mockup Fassung 4 zeigt dieselbe Reihenfolge.
  - Test: Staging-Abgleich Trip DE meldet beide Namen als gefunden; Elementlisten-Test belegt die Reihenfolge im Mockup.

- **AC-2:** Given eine der beiden Gehzeit-Metriken im Trip-Reiter Wetter / When der Nutzer die Zeile betrachtet / Then zeigt sie den Untertitel „°C · nur Anzeige, keine Ampel“ und in der Mitte „keine Ampel, nur Anzeige“, ohne Ampel-Grenzen und ohne Alarm-Auswahl, wie die Windrichtung.
  - Test: Staging-Abgleich DE und EN (englische Katalogtexte) ohne Abweichung für Untertitel und Zeilenmitte; Mockup-Bildprüfung.

- **AC-3:** Given eine Nur-Anzeige-Metrik im Reiter Wetter (Trip, Deutsch oder Englisch) / When der Nutzer den Erklärsatz liest / Then verweist er auf den Abschnitt „Was steht wo“ (englisch der entsprechende Abschnittsname) statt „je Liste“, wortgleich zum Mockup.
  - Test: Katalog-Test beider Sprachen; Staging-Abgleich meldet den Erklärsatz als gefunden.

- **AC-4:** Given der Orts-Vergleich / When der Nutzer dort die Metrikliste öffnet / Then erscheinen Tages-Tief und Tages-Hoch weiterhin nicht (ADR-0011), und das Mockup der Orte bleibt unverändert.
  - Test: Elementlisten-Test: Orte enthalten die Namen nicht; Staging-Abgleich Orte ohne neue Abweichung.

- **AC-5:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then meldet er keinen Eintrag mit Besitzer `#3204`, keine neue Abweichung ohne Besitzer, und der Zählwächter steht auf 0.
  - Test: Abgleich DE+EN vorher/nachher; `tests/test_2913_c2_besitzerliste.py` grün.

- **AC-6:** Given Bestandstrips mit aktivierten Tages-Tief/-Hoch-Metriken / When der Nutzer seinen Trip öffnet / Then bleiben Auswahl, SMS-Kürzel L/D und Briefing unverändert, denn nur Mockup, Erklärsatz und Prüflisten ändern sich.
  - Test: bestehende Metrik-/SMS-Tests laufen unverändert grün; kein Diff in `src/app/metric_catalog.py`.

- **AC-7:** Given der Trip-Reiter Wetter als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild ansieht / Then stimmen beide in den zwei neuen Zeilen und im Erklärsatz sichtbar überein.
  - Test: Bildabgleich Mockup gegen Staging (ADR-0112) wird dem PO als Soll/Ist-Bild vorgelegt.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Abgleich-Bericht Reiter Wetter DE+EN vorher/nachher als Artefakt abgelegt
- [ ] Mutationsprobe: Erklärsatz im Katalog auf alten Wortlaut zurückgesetzt röntet den Katalog-Test
- [ ] Prüfsumme begründet nachgezogen, Besitzerliste und Zählwächter angepasst, PR mit allen 6 CI-Checks grün, Deploy, Selftest
- [ ] Soll/Ist-Bild an den PO

## Known Limitations

- #3091 (Gehzeit vs. Tagesfenster) kann die Bedeutung des Namenszusatzes „(Gehzeit)“ später ändern; das ist unabhängig von dieser Spec.
- #3086 (Luftdruck-Widerspruch bei „nur Anzeige“) bleibt offen; der Nur-Anzeige-Wortlaut darf dort nicht geändert werden.
- Das Mockup bleibt ein Auszug: weitere Katalog-Metriken ohne Mockup-Zeile (z. B. Niederschlagsart, mittlere/hohe Wolken) sind nicht Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ausführung bestehender Entscheidungen (ADR-0011 Gehzeit-Exklusivität, ADR-0104 Texte nur über Katalog, ADR-0112 Mockup-getriebene Scheiben mit Bildprüfung); die Nutzerfunktion bleibt, es wird nur das Soll ergänzt.

## Changelog

- 2026-11-21: Initial spec created (Option A: Mockup ergänzen und App-Erklärsatz angleichen; Metriken bleiben, Orte unverändert)
