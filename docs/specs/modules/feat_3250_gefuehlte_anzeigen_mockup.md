---
entity_id: feat_3250_gefuehlte_anzeigen_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3250-gefuehlte-anzeigen-mockup
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, "#3250", "#2913"]
---

# Reiter Wetter (Trip): Gefühlte Anzeige-Metriken Nacht/Tages-Tief/Tages-Hoch ins Mockup Fassung 4

## Approval

- [ ] Approved

## Purpose

Die App bietet im Trip-Reiter Wetter drei gefühlte Temperaturen als Nur-Anzeige-Zeilen an (`wind_chill_night`, `wind_chill_day_low`, `wind_chill_day_high`; SMS-Token FN/FL/FD). Sie sind PO-beauftragte Nutzerfunktion (#1660, #1728) und hängen automatisch an „Gefühlte Temperatur“. Im Mockup Fassung 4 fehlen sie, daher stehen sie im Live-Abgleich als herrenlose `zusaetzlich`-Einträge. Das Mockup wird ergänzt (Tech-Lead-Entscheidung Option A, Kommentar in Issue #3250, Vorbild #3204).

## Source

- **File:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (`TRIP_METRICS`, Z. 316-332; SMS-Beispiel `TF`, Z. 555-568; Kürzel-Legende)
- **Identifier:** `TRIP_METRICS` (drei neue Zeilen nach `wind_chill`)

> Schicht: Mockup (Soll), generierte Elementliste und Besitzerliste. Kein Go-API-/Python-Core-Code, kein Frontend-Produktcode; Metrik-Register (`src/app/metric_catalog.py`) und Katalog bleiben unverändert.
> Trip/Orts-Vergleich: Die Zeilen erscheinen nur im Trip; der Orts-Vergleich bietet Nacht-/Gehzeit-Größen bewusst nicht an (ADR-0011). Kein neuer Kontext-Zweig, Orte-Mockup unverändert.
> Kanäle: keine Änderung an Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unberührt; Token FN/FL/FD bleiben). Keine Nutzerdaten bewegt.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY | Drei Nur-Anzeige-Zeilen in `TRIP_METRICS`; Kürzel-Legende FN/FL/FD und SMS-Beispiel, soweit aus aktiven Metriken abgeleitet |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (generiert) | Per `scripts/elementliste_aus_mockup.ts` neu erzeugt, keine Handpflege |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | MODIFY | Prüfsumme mit Begründung „#3250: drei gefühlte Anzeige-Metriken ergänzt“ |
| `frontend/e2e/elementliste_gefuehlte_3250.test.ts` | CREATE | Elementlisten-Test (node --test) wie bei #3204 |
| `docs/artifacts/` (Abgleich-Bericht DE+EN vorher/nachher, Soll/Ist-Bild) | CREATE | Nachweis für Wirkung und PO |

### Estimated Changes

- Files: 5
- LoC: +40/-5 (ohne generierte Elementliste)
- Effort: low

**Im Scope**
- Mockup: drei Zeilen hinter „Gefühlte Temperatur“, Reihenfolge wie `_REITER_WETTER`: Temperatur, Tiefsttemperatur Nacht, Tages-Tief, Tages-Hoch, Gefühlte Temperatur, Gefühlte Tiefsttemperatur Nacht, Gefühlte Tages-Tiefsttemperatur (Gehzeit), Gefühlte Tages-Höchsttemperatur (Gehzeit). Form wie Windrichtung/#3204: Untertitel „°C · nur Anzeige, keine Ampel“, Zeilenmitte „keine Ampel, nur Anzeige“, Nur-Anzeige-Flag.
- Zähler im Mockup „9 von 18 Metriken lösen einen Alarm aus. 8 können keinen auslösen“ (aus aktiven Zeilen berechnet, alarmfähig bleiben 9).
- Kürzel-Legende FN/FL/FD und SMS-Beispielwerte nur dort, wo das Mockup sie aus aktiven Metriken ableitet.
- Elementliste per Generator, Prüfsumme begründet.
- Staging-Abgleich DE+EN, Soll/Ist-Bild Trip-Reiter Wetter, Gruppe Temperatur, für den PO.

**Nicht im Scope**
- Produktcode, Katalog-Texte, Metrik-Register, SMS-Token, Orte-Mockup (ADR-0011), #3091 (Gehzeit vs. Tagesfenster), #3086, #2867.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | mockup | Soll des Reiters Wetter, um drei Zeilen ergänzt |
| `scripts/elementliste_aus_mockup.ts` | script | Erzeugt `elementliste.json` deterministisch |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | test | Prüfsumme der Elementliste |
| `src/app/metric_catalog.py` (`_REITER_WETTER`, Z. 299-335, 1311-1313) | module | Quelle von Reihenfolge und Nur-Anzeige-Einstufung (nur gelesen) |
| `src/app/loader.py` (`_DERIVED_METRIC_RULES`) | module | Ableitung der drei Kinder aus `wind_chill` (nur gelesen) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Besitzerliste; die drei Metriken haben dort keinen Besitzer, kein Eintrag nötig |
| `tests/test_2913_c2_besitzerliste.py` | test | Zählwächter; kein neuer Besitzer `#3250`, Wächter muss grün bleiben |
| `scripts/staging_pruefkonto_mockupdaten.py` | system | Prüfkonto-Seed für Abgleich-Lauf DE+EN |
| `feat_3204_anzeige_metriken_mockup.md` | spec | Direktes Vorbild, gleiche Mechanik |
| ADR-0011, ADR-0112 | adr | Gehzeit-/Nacht-Exklusivität im Trip, Mockup-Bildprüfung |

## Implementation Details

1. **Mockup:** drei Zeilen nach `wind_chill` in `TRIP_METRICS` einfügen (`wind_chill_night`, `wind_chill_day_low`, `wind_chill_day_high`), Format der Zeilen `temperature_day_low/high` (Einheit `°C`, Hinweis „nur Anzeige, keine Ampel“, keine Grenzen, kein Alarm, Nur-Anzeige-Flag). Anfangszustand **aktiv** (`on=true`), wie in #3204: Nur so stehen Untertitel, Zeilenmitte und Zähler im Mockup und damit in der Elementliste; das Prüfkonto zeigt sie live ebenfalls aktiv (Ableitung aus `wind_chill`). Gruppe `Temperatur`. Namen wortgleich zur App (`wertebereiche.json`).
2. **Legende und Beispiel:** Kürzel-Legende FN/FL/FD („N gefühlt“, „L gefühlt“, „D gefühlt“) und SMS-Beispiel (Mockup-Rechnung, bisher `TF- FN7 FD7/12` bei `wind_chill`) nur ergänzen bzw. angleichen, soweit sie aus den nun aktiven Metriken abgeleitet werden; bestehende Beispielwerte nicht frei erfinden.
3. **Zähler:** die Berechnung (alarmfähige von aktiven) bleibt; Ergebnis 9 von 18, 8 ohne Alarm.
4. **Elementliste und Prüfsumme:** Generator laufen lassen; Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Kommentar „#3250: drei gefühlte Anzeige-Metriken ergänzt“ nachziehen.
5. **Besitzerliste:** Die drei Metriken sind herrenlos, daher kein Eintrag `#3250` und keine Zählwächter-Änderung. Erfolgsmaß ist der Live-Abgleich: die `zusaetzlich`-Einträge dieser drei Metriken (DE und EN) verschwinden, keine neue Abweichung ohne Besitzer.
6. **Wirkung messen:** Staging-Abgleich DE+EN Reiter Wetter vorher/nachher, Soll/Ist-Bild (Mockup gegen Staging, Trip-Reiter Wetter, Gruppe Temperatur) dem PO zeigen.

## Expected Behavior

- **Input:** Mockup Fassung 4, Staging-Seite Reiter Wetter (Trip), Prüfkonto-Seed.
- **Output:** Abgleich meldet die drei gefühlten Metriken (DE und EN) samt Untertitel, Zeilenmitte und Zähler ohne Abweichung; keine herrenlosen Einträge dieser Metriken.
- **Side effects:** Wechsel `zusaetzlich`→`gefunden` in verwandten Einträgen (Kürzel-Legende, Beispiel) ist erlaubt; eine neue Abweichung ohne Besitzer ist es nicht. Produktverhalten unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Elementlisten-Test (node --test, `elementliste_gefuehlte_3250.test.ts`): `elementliste.json` des Trips Reiter Wetter enthält die drei Metrik-Namen mit Untertitel „°C · nur Anzeige, keine Ampel“ und Zeilenmitte „keine Ampel, nur Anzeige“; Orte enthalten sie nicht. Rot vor der Mockup-Änderung.
- [ ] Reihenfolge-Test: Gruppe Temperatur im Mockup lautet Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte, Gefühlte Nacht, Gefühlte Tages-Tief, Gefühlte Tages-Hoch.
- [ ] Zähler-Test: Mockup-Satz „9 von 18 Metriken lösen einen Alarm aus. 8 können keinen auslösen“ steht in der Elementliste.
- [ ] `elementliste_uebersicht_2969.test.ts` grün mit begründeter neuer Prüfsumme.
- [ ] `tests/test_2913_c2_besitzerliste.py` bleibt grün, keine herrenlosen Einträge hinzugekommen.
- [ ] Staging-Abgleich Reiter Wetter DE+EN vorher/nachher: Diff enthält nur das Verschwinden der `zusaetzlich`-Einträge der drei Metriken (und ableitbarer Legendenzeilen), keine neue Abweichung ohne Besitzer.

## Acceptance Criteria

- **AC-1:** Given der Trip-Reiter Wetter in Deutsch / When der Nutzer die Gruppe Temperatur liest / Then stehen dort nach „Gefühlte Temperatur“ die Zeilen „Gefühlte Tiefsttemperatur Nacht“, „Gefühlte Tages-Tiefsttemperatur (Gehzeit)“ und „Gefühlte Tages-Höchsttemperatur (Gehzeit)“, und das Mockup Fassung 4 zeigt dieselbe Reihenfolge.
  - Test: Staging-Abgleich Trip DE meldet alle drei Namen als gefunden; Elementlisten-Test belegt die Reihenfolge im Mockup.

- **AC-2:** Given der Trip-Reiter Wetter in Englisch / When der Nutzer die Gruppe Temperatur liest / Then erscheinen „Feels-like night low“, „Feels-like daytime low (walking hours)“ und „Feels-like daytime high (walking hours)“ und stimmen mit dem Mockup überein.
  - Test: Staging-Abgleich Trip EN meldet die drei englischen Namen als gefunden.

- **AC-3:** Given eine der drei gefühlten Metriken im Trip-Reiter Wetter / When der Nutzer die Zeile betrachtet / Then zeigt sie den Untertitel „°C · nur Anzeige, keine Ampel“ und in der Mitte „keine Ampel, nur Anzeige“, ohne Ampel-Grenzen und ohne Alarm-Auswahl, wie Windrichtung und die Gehzeit-Zeilen.
  - Test: Elementlisten-Test; Staging-Abgleich DE und EN ohne Abweichung für Untertitel und Zeilenmitte.

- **AC-4:** Given der Trip mit aktiver „Gefühlte Temperatur“ / When der Nutzer den Zähler über der Metrikliste liest / Then lautet er „9 von 18 Metriken lösen einen Alarm aus. 8 können keinen auslösen“ im Mockup und auf Staging gleich.
  - Test: Elementlisten-Test auf den Zählersatz; Staging-Abgleich meldet ihn als gefunden.

- **AC-5:** Given der Orts-Vergleich / When der Nutzer dort die Metrikliste öffnet / Then erscheinen die drei gefühlten Anzeige-Metriken weiterhin nicht (ADR-0011), und das Mockup der Orte bleibt unverändert.
  - Test: Elementlisten-Test: Orte enthalten die Namen nicht; Staging-Abgleich Orte ohne neue Abweichung.

- **AC-6:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then enthalten die Berichte keine `zusaetzlich`-Einträge mehr für die drei gefühlten Metriken, keine neue Abweichung ohne Besitzer, und der Zählwächter der Besitzerliste bleibt grün.
  - Test: Abgleich DE+EN vorher/nachher; `tests/test_2913_c2_besitzerliste.py` grün.

- **AC-7:** Given Bestandstrips mit aktiver gefühlter Temperatur / When der Nutzer seinen Trip öffnet / Then bleiben Auswahl, SMS-Kürzel FN/FL/FD und Briefing unverändert, denn nur Mockup und Prüflisten ändern sich.
  - Test: bestehende Metrik-/SMS-Tests laufen unverändert grün; kein Diff in `src/app/metric_catalog.py` und im Frontend-Produktcode.

- **AC-8:** Given der Trip-Reiter Wetter als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild der Gruppe Temperatur ansieht / Then stimmen beide in den drei neuen Zeilen und im Zähler sichtbar überein.
  - Test: Bildabgleich Mockup gegen Staging (ADR-0112) wird dem PO als Soll/Ist-Bild vorgelegt.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Abgleich-Bericht Reiter Wetter DE+EN vorher/nachher als Artefakt abgelegt
- [ ] Mutationsprobe: eine der drei Mockup-Zeilen entfernt färbt rot den Elementlisten-Test
- [ ] Elementliste per Generator erzeugt, Prüfsumme begründet nachgezogen, PR mit allen 6 CI-Checks grün, Deploy, Selftest
- [ ] Soll/Ist-Bild an den PO

## Known Limitations

- #3091 (Gehzeit vs. Tagesfenster) kann die Bedeutung des Namenszusatzes „(Gehzeit)“ später ändern; unabhängig von dieser Spec.
- Das SMS-Beispiel im Mockup ist Mockup-Rechnung; Zeilen, die erst durch #3205/#3122 geklärt werden, bleiben bei deren Besitzern.
- Das Mockup bleibt ein Auszug: weitere Katalog-Metriken ohne Mockup-Zeile sind nicht Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ausführung bestehender Entscheidungen (ADR-0011 Exklusivität im Trip, ADR-0112 Mockup-getriebene Scheiben mit Bildprüfung, PO-Aufträge #1660/#1728); die Nutzerfunktion bleibt, es wird nur das Soll ergänzt.

## Changelog

- 2026-11-21: Initial spec created (Option A: Mockup um drei gefühlte Nur-Anzeige-Metriken ergänzen; Funktion bleibt, Orte unverändert)
