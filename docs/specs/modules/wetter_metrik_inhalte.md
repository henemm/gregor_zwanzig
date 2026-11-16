---
entity_id: wetter_metrik_inhalte
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
workflow: feature-2955-wetter-metrik-inhalte
tags: [wetter-tab, metriken, mockup-fassung-3, i18n, epic-2913]
---

# Reiter Wetter: Metrik-Inhalte an Mockup Fassung 3 angleichen

## Approval

- [ ] Approved

## Purpose

Der Reiter Wetter (Trip und Orts-Vergleich, DE/EN) zeigt Vorbote-Kennzeichnung, Gewitter-Erklärsatz, Zeilenreihenfolge, Metrik-Namen und Kopfzähler anders als das angenommene Mockup Fassung 3. Diese Spec gleicht die Inhalte an (Issue #2955, gebündelt mit #3012 „Stufenwort groß“, Teil von Epic #2913). Layout, Alarmlogik und Mail-Spaltenreihenfolge bleiben unverändert.

## Source

- **File:** `src/app/metric_catalog.py` (Katalog, `_REITER_WETTER`, `reiter_wetter_eigenschaften()`), `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts`
- **Identifier:** `MetricDefinition.is_precursor`, `reiter_wetter_eigenschaften`, `zeilenGruppen`, `gewitterSatz`, `alarmZaehler`

> **Schicht:** Python-Core (`src/app/`, `api/routers/config.py`) für Katalogdaten und `/api/metrics`; Frontend (`frontend/src/lib/...`, geteilt unter `shared/wetter-tab/` und `organisms/wetter-tab/`) für Anzeige. Die Go-API wird nicht geändert.
>
> **Trip/Ortsvergleich-Teilung:** Alle Frontend-Änderungen liegen im geteilten Code (`context="route"|"vergleich"`), keine einseitige Neuanlage.
>
> **Kanäle:** Nur der Anzeigename (`label_de`) dreier Metriken wirkt auf Briefing-Inhalte in E-Mail, Telegram, SMS und Premium-SMS (derselbe Name, kanalgerechte Form). Kürzel, `sms_code`, `alert_label` und die Spaltenreihenfolge bleiben unverändert.

## Estimated Scope

- **LoC:** +60/-30 ohne Goldens; zusätzlich ~20–30 Test-/Golden-Dateien (Textersatz bzw. Neuerzeugung)
- **Files:** ~10–12 Quelldateien
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/app/metric_catalog.py | MODIFY | `is_precursor=True` für wind_chill, cloud_total, dewpoint, pressure; `_REITER_WETTER` in Mockup-Reihenfolge; Feld `rang` in `reiter_wetter_eigenschaften()`; `label_de` temperature_night, wind_chill_night, humidity |
| api/routers/config.py | MODIFY (ggf.) | `rang` läuft über `**reiter_wetter_eigenschaften(m)` durch; nur prüfen/anpassen |
| frontend/src/lib/components/shared/wetter-tab/ampelModell.ts | MODIFY | `MetrikEigenschaften.rang`; `zeilenGruppen()` sortiert stabil nach `rang`; `gewitterSatz()` mit Token „mittel oder hoch“; `alarmZaehler()` m = alle ausgewählten |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | Stufenwort im Erklärsatz über `alarme.alarm_ab.stufe.*` |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | `wetter.gewitter.mittel_ab`; Zähler-Platzhalter/Text |
| frontend/src/lib/i18n/messages/de/{wertebereiche,alarme,vergleich,mail}.json | MODIFY | Namens-Kopien angleichen |
| tests/tdd/test_metrik_katalog_reiter_wetter_felder.py | MODIFY | Vorbote-Flags, Rang |
| frontend/src/lib/components/organisms/__tests__/ (ampelModell, fix2913_metrikliste_mockup, wetter_tab_bausteine, deutsch_unveraendert, nicht_im_briefing_kontextkatalog, wertebereiche_sprache) | MODIFY | Erwartungen Zähler, Gewitter-Satz, Reihenfolge, Stufenwort, Namen |
| tests/unit/test_mail_metric_name_forms.py, test_metric_catalog_englische_namen.py, test_compare_metric_catalog_endpoint.py u. a. | MODIFY | neuer Name |
| tests/golden/**, tests/fixtures/einstellung_gleich_mail/** | MODIFY | Goldens mit neuem Namen neu erzeugen |
| frontend/e2e/ (Staging-Spec Reiter Wetter, Trip + Orte, DE/EN) | CREATE | Staging-E2E zu AC-1 bis AC-6 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0010 | ADR | Liste der Vorboten (humidity, dewpoint, rain_probability, cloud_total, pressure, wind_chill) |
| ADR-0095 / ADR-0104 | ADR | Kanal-Parität; Zweisprachigkeit, Texte nur über Katalog |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Mockup | Soll-Reihenfolge, -Texte, Zähler (Z. ~279–470) |
| `docs/context/einstellungen_neu/elementliste.json` | Datei | Soll-Texte DE/EN (`wetter.erklaer.gewitter`, `wetter.alarm_ab.zaehler`) |
| `weather_change_detection.py`, `from_display_config()` | Modul | Leser von `is_precursor`; ignoriert Vorboten erst nach threshold-None-Skip, keine Verhaltensänderung |
| `alarme.alarm_ab.stufe.*` | i18n-Schlüssel | Stufenwörter Nie/Gelb/Orange/Rot (DE/EN), bereits vorhanden |
| Epic #2913, Issues #2955, #3012 | Tracking | Einordnung |
| Renderer-Commit-Gate (Modus-Matrix + Mail-Validator) | Gate | gilt für den Namen-Teil (eigener Commit) |

## Implementation Details

1. **Vorbote:** Katalogflag `is_precursor=True` für wind_chill, cloud_total, dewpoint, pressure (humidity und rain_probability haben es schon). Eine Quelle, kein reiter-eigenes Flag. cloud_low („Gipfel in Wolken“) bleibt Nicht-Vorbote. Die vier Metriken haben `default_change_threshold=None` und sind im Reiter schon `alertable=False`; Risk-Engine, `from_alert_rules` und Renderer lesen das Flag nicht ⇒ keine Alarm-/Kanal-Wirkung. UI-Texte (`wetter.untertitel.vorbote`, `wetter.erklaer.vorbote`, `wetter.alarm_ab.vorbote`) existieren bereits.
2. **Gewitter-Satz:** Token `wetter.gewitter.mittel_ab` („mittel oder hoch“ / „medium or high“; die Elementliste führt EN nur als Muster `{gewitter_stufe}`, das EN-Stufenwort kommt aus dem Katalog), verwendet nur, wenn die Stufe „mittel“ die Alarmstufe erreicht; sonst bleibt „hoch“. Skala-Ticks „keins · mittel · hoch“ existieren bereits.
3. **Reihenfolge:** `_REITER_WETTER` ist Python-Quelle der Mockup-Reihenfolge (thunder vor rain_probability, Himmel-Block). `reiter_wetter_eigenschaften()` liefert daraus `rang`; `/api/metrics` reicht ihn durch; `zeilenGruppen()` sortiert je Gruppe stabil nach `rang` (gleicher Rang bzw. fehlender Rang ⇒ Auswahl-Reihenfolge). Keine Frontend-Rangtabelle (AC-27 aus #2794). `_METRICS` und `ampel_templates` bleiben unverändert.
   - **Geklärte Frage „Kann der Nutzer die Reihenfolge ändern?“:** Codesuche in `organisms/wetter-tab/` (Verschieben, Umordnen, Drag) findet keine Funktion; die Zeilenfolge entsteht ausschließlich aus Auswahl-Reihenfolge und Gruppenfolge. Der Rang-Sortierer überschreibt daher keine Nutzerentscheidung. Bestätigung per RED-Test (AC-3); sollte der Test eine Nutzer-Umordnung finden, hat diese Vorrang und die Spec ist vor Umsetzung nachzuziehen.
4. **Namen:** `label_de` temperature_night „Tiefsttemperatur Nacht“, wind_chill_night „Gefühlte Tiefsttemperatur Nacht“, humidity „Luftfeuchte“; ein Name überall (Reiter, Mail, Alarme, Wertebereiche). EN-Namen, Kürzel, `sms_code`, `alert_label` unverändert. Goldens werden neu erzeugt; eigener Commit.
5. **Kopfzähler:** „{n} von {m} Metriken … {k} können keinen auslösen“, m = alle ausgewählten Metriken, k = nicht alarmfähige (Vorboten + reine Anzeige), n = alarmfähige mit Stufe ≠ „nie“. „A5“ im Mockup ist ein Abgleich-Tag und kein Produkttext, wird nicht nachgebaut.
6. **Stufenwort (#3012):** Der Erklärsatz nutzt `alarme.alarm_ab.stufe.*` (groß: „Orange“); `wetter.farbe.*` (klein) bleibt für Screenreader-Texte.
7. **Mandantentrennung:** `/api/metrics` liefert Katalogdaten ohne Nutzerdaten; der Endpoint ist nutzerunabhängig. Das neue Feld `rang` kommt aus dem statischen Katalog.

## Expected Behavior

- **Input:** Nutzer öffnet im Trip-Editor oder im Orts-Vergleich-Editor den Reiter Wetter (DE oder EN).
- **Output:** Zeilen, Untertitel, Erklärsätze, Namen und Kopfzähler entsprechen Mockup Fassung 3.
- **Side effects:** Keine Änderung an Alarm-Erzeugung, Kanälen, Mail-/SMS-Spaltenreihenfolge. Einzige Kanal-Wirkung: drei neue Anzeigenamen.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, ohne Netz, keine Mocks):

- [ ] GIVEN Katalog WHEN `reiter_wetter_eigenschaften()` für wind_chill, cloud_total, dewpoint, pressure, humidity, rain_probability THEN `is_precursor` True; für cloud_low und thunder False.
- [ ] GIVEN Katalog WHEN `reiter_wetter_eigenschaften()` THEN `rang` von thunder < `rang` von rain_probability; Ränge eindeutig.
- [ ] GIVEN `_METRICS` und `ampel_templates` WHEN vor/nach der Änderung verglichen THEN Reihenfolge identisch (Mail-/SMS-Spalten unverändert).
- [ ] GIVEN `from_display_config`/`from_alert_rules` mit gesetzter Gefühlter Temperatur WHEN Alarme erzeugt THEN Ergebnis wie vor der Änderung.
- [ ] GIVEN Auswahl [rain_probability, thunder] WHEN `zeilenGruppen()` mit `rang` THEN thunder vor rain_probability; gleicher Rang ⇒ Auswahl-Reihenfolge (stabil).
- [ ] GIVEN `gewitterSatz()` WHEN Alarmstufe mittel bzw. hoch, DE und EN THEN „mittel oder hoch“ bzw. „hoch“ (EN „medium or high“ / „high“).
- [ ] GIVEN `alarmZaehler()` mit 13 ausgewählten, 3 nicht alarmfähigen, 9 mit Stufe ≠ nie THEN n=9, m=13, k=3.
- [ ] GIVEN Erklärsatz einer Zeile mit Stufe orange WHEN gerendert DE/EN THEN „Orange“/„Orange“ groß, über `alarme.alarm_ab.stufe.*`.
- [ ] GIVEN `label_de` WHEN Mail-Zeilenkopf, Alarme-Seite, Wertebereiche THEN neue Namen; EN-Namen, `sms_code`, `alert_label` unverändert.
- [ ] GIVEN `/api/metrics` WHEN zwei verschiedene Nutzer abfragen THEN identische Metrikdaten inkl. `rang`, keine Nutzerdaten enthalten.

Staging-E2E (nur `/e2e-verify`/Deploy): Reiter Wetter im Trip (Vorlage Alpen-Trekking) und im Orts-Vergleich (Vorlage Allgemein), DE und EN, prüft Sichtbares aus den ACs 1–6.

## Acceptance Criteria

- **AC-1:** Given ein Trip oder ein Orts-Vergleich mit Gefühlter Temperatur, Bewölkung, Taupunkt oder Luftdruck im Reiter Wetter / When der Nutzer den Reiter öffnet / Then jede dieser Zeilen zeigt den Untertitel „Vorbote, kein Alarm“, die Erklärung „Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.“ und rechts „kein Alarm (Vorbote)“ (EN: „precursor, no alert“, „no alert (precursor)“), während „Gipfel in Wolken“ (cloud_low) kein Vorbote ist und „kein Alarm“ zeigt.
  - Test: Nutzer sieht im Reiter Wetter (Trip und Orte, DE und EN) bei allen Vorboten die drei Texte; Katalog setzt `is_precursor` für alle ADR-0010-Vorboten, nicht für cloud_low.

- **AC-1b:** Given ein Nutzer mit bestehenden Alarm-Einstellungen inklusive Gefühlter Temperatur / When Briefing und Alarme nach der Änderung erzeugt werden / Then entstehen dieselben Alarme in denselben Kanälen (E-Mail, Telegram, SMS, Premium-SMS) wie vorher; die Vorbote-Kennzeichnung ändert nur die Anzeige im Reiter.
  - Test: Alarm-Erzeugung mit identischer Eingabe vor/nach liefert gleiche Ergebnisse; kein Renderer liest `is_precursor`.

- **AC-2:** Given eine Gewitter-Zeile, bei der bereits die Stufe „mittel“ die Alarmstufe erreicht / When der Nutzer den Erklärsatz liest / Then lautet er „… auf mittel oder hoch steigt (Orange)“ (EN: „… rises to medium or high (Orange) …“), und greift der Alarm erst bei „hoch“, steht dort weiter „auf hoch“; die Skala zeigt unverändert „keins · mittel · hoch“.
  - Test: Zeile Gewitter in Trip und Orte, DE und EN, bei Alarmstufe mittel und bei Alarmstufe hoch; Skala-Ticks als Regressionsschutz.

- **AC-3:** Given ein Trip mit Vorlage Alpen-Trekking oder ein Orts-Vergleich mit Vorlage Allgemein / When der Nutzer den Reiter Wetter öffnet / Then steht Gewitter vor Regenwahrscheinlichkeit und die übrigen Zeilen folgen der Mockup-Reihenfolge, ohne dass E-Mail- oder SMS-Spaltenreihenfolge davon abhängt.
  - Test: Zeilenreihenfolge im Reiter (Trip und Orte) gegen Mockup; Vergleichs-Mail und SMS einer unveränderten Konfiguration haben dieselbe Spaltenreihenfolge wie vorher; die Reihenfolge stammt aus dem von `/api/metrics` gelieferten `rang`, nicht aus einer Frontend-Tabelle.

- **AC-3b:** Given der Reiter Wetter bietet dem Nutzer keine Möglichkeit, Zeilen selbst umzusortieren / When die Rang-Sortierung greift / Then überschreibt sie keine Nutzerentscheidung, und Metriken mit gleichem Rang bleiben in der Reihenfolge der Auswahl.
  - Test: Auswahl in beliebiger Eingangsreihenfolge ergibt dieselbe sichtbare Reihenfolge; gleicher Rang behält die Auswahl-Reihenfolge; Metriken unter „Nicht im Briefing“ erscheinen in derselben Rangfolge.

- **AC-4:** Given ein Nutzer mit Nacht-Tiefsttemperatur, Gefühlter Nacht-Tiefsttemperatur und Luftfeuchte / When er den Reiter Wetter, die Wertebereiche, die Alarme-Seite oder eine Mail ansieht / Then heißen die Metriken überall „Tiefsttemperatur Nacht“, „Gefühlte Tiefsttemperatur Nacht“ und „Luftfeuchte“, während englische Namen, Kürzel, SMS-Codes und Alarm-Kurzlabel unverändert bleiben.
  - Test: Namen im Reiter, in Wertebereichen, Alarme-Seite und zugestellter Staging-Mail (Trip und Vergleich); SMS/Telegram/Premium-SMS-Texte behalten Kürzel und `sms_code`; EN-Oberfläche zeigt die bisherigen englischen Namen.

- **AC-5:** Given ein Reiter Wetter mit 13 ausgewählten Metriken, davon 3 ohne Alarmfähigkeit (Vorboten und reine Anzeige) und 9 alarmfähigen mit Stufe ungleich „nie“ / When der Nutzer den Kopf „Alarm ab für alle“ liest / Then steht dort „9 von 13 Metriken … 3 können keinen auslösen (Vorboten und reine Anzeige)“ (EN sinngemäß), wobei die Zahl 13 alle ausgewählten Metriken meint und kein Abgleich-Tag „A5“ erscheint.
  - Test: Zähler im Reiter Wetter bei Trip und Orte, DE und EN; Änderung einer Stufe auf „nie“ senkt nur die erste Zahl.

- **AC-6:** Given eine Metrik-Zeile mit Alarmstufe Orange (#3012) / When der Nutzer den Erklärsatz liest / Then steht das Stufenwort groß in Klammern („(Orange)“), in DE und EN, aus den vorhandenen Texten der Alarm-Stufen (Nie, Gelb, Orange, Rot).
  - Test: Erklärsätze für Gelb, Orange und Rot im Trip- und Orte-Reiter in DE und EN zeigen das große Stufenwort.

- **AC-7:** Given zwei verschiedene angemeldete Nutzer / When beide die Metrik-Liste (`/api/metrics`) mit dem neuen Feld `rang` abrufen / Then erhalten beide dieselben nutzerunabhängigen Katalogdaten, und keine Antwort enthält Daten des anderen Nutzers.
  - Test: Zwei Nutzer rufen den Endpoint auf; Antworten sind gleich, kein Fallback auf „default“, Rang vorhanden.

## Definition of Done

- AC-1, AC-1b und AC-7 durch Kern-Tests am Katalog und an /api/metrics belegt (Vorbote-Flags, unveränderte Alarm-Erzeugung, zwei Nutzer), Kern-Schicht grün
- AC-2, AC-3, AC-3b, AC-5 und AC-6 durch Frontend-Kern-Tests (node --test) belegt, DE und EN
- AC-4 durch Katalog- und Mail-Namenstests plus neu erzeugte Goldens belegt; Renderer-Gate (Modus-Matrix, Mail-Validator gegen echt zugestellte Staging-Mail) grün
- Elementlisten-Abgleich im strikten Modus meldet für die betroffenen Texte keine Abweichung mehr (Akzeptanz #3012)
- Staging-E2E Trip und Orte, DE und EN, zeigt Vorbote-Texte, Gewitter-Satz, Reihenfolge, Namen und Kopfzähler wie im Mockup
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Known Limitations

- Die Zähler-Zahlen 9/13/3 aus dem Mockup gelten für Mockup-Daten; auf Staging hängen sie von der gewählten Vorlage ab.
- Das Issue #2955 nennt „Tiefe Wolken“ als Vorbote; maßgeblich ist das Mockup (cloud_low kein Vorbote, Vorbote ist cloud_total „Bewölkung“).
- Issue #3012 nennt die Namensrichtung umgekehrt („Luftfeuchtigkeit“ statt „Luftfeuchte“). Gegengeprüft am 16.11.2026: Mockup Fassung 3 (Z. 295, 307) und Elementliste (Chip „+ Luftfeuchte“, kein Vorkommen von „Luftfeuchtigkeit“) schreiben „Luftfeuchte“; der Issue-Akzeptanztext verlangt Übereinstimmung mit der Elementliste ⇒ Soll „Luftfeuchte“.

## Nicht-Ziele

- Kein Layout-Umbau des Reiters.
- Keine Änderung der Mail-/SMS-/Telegram-Spaltenreihenfolge (`_METRICS`, `ampel_templates`, `CV2_ZEILEN`).
- Keine Änderung der Alarmlogik, Alarm-Erzeugung, Kanal-Auswahl oder Schwellen.
- Keine Änderung englischer Namen, Kürzel, `sms_code`, `alert_label`.
- Kein Nachbau des Abgleich-Tags „A5“.
- `confidence_pct` bleibt unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung bestehender Entscheidungen (ADR-0010 Vorboten, ADR-0104 Zweisprachigkeit, AC-27 #2794 eine Python-Quelle für Reiter-Eigenschaften); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-16: Initial spec created (Issue #2955 gebündelt mit #3012, Epic #2913)
