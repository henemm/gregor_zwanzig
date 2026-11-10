---
entity_id: fix_2598_ortsvergleich_alarm_kopfzeile
type: bugfix
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
workflow: fix-2598-ortsvergleich-alarm-kopfzeile
tags: [alert, renderer, ortsvergleich, kanalparitaet, i18n]
---

# Ortsvergleich-Alarm: Ortsname einmal, kein "km 0-0" (Issue #2598)

## Approval

- [ ] Approved

## Purpose

Ortsvergleich-Alarme nennen in Betreff und Telegram-Kopf den Ortsnamen doppelt (`Ort Eins · Ort Eins · ↑ Böen`) und zeigen an Stelle des Ortes eine sinnlose Kilometerangabe `km 0–0`. Der Fix lässt die Doppelung weg und zeigt in Ereigniszeilen den Ortsnamen, in allen Kanälen und für Änderungs- wie Radar-Alarme; Trip-Alarme bleiben unverändert.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `render_subject`, `render_telegram`, `_km_str`, `_render_subject_onset`, `_render_telegram_onset`, `_onset_shift_where`, `_km_str_onset`, SMS-Kopf in `render_sms`
- **Zweite Datei:** `src/output/renderers/alert/project.py`, Funktion `to_multi_location_onset_alert_message`

> **Schicht:** Python-Core (`src/output/renderers/alert/`). Kein Frontend, keine Go-API.
>
> **Trip/Ortsvergleich-Teilung:** Trip und Ortsvergleich nutzen bereits denselben Alarm-Renderer. Es entsteht kein Compare-eigener Baustein; die Korrektur ist an `msg.location_label` gekoppelt, das nur der Ortsvergleich setzt.
>
> **Mandantentrennung:** Keine Nutzerdaten bewegt, reine Darstellung.
>
> **Kanäle:** E-Mail (Betreff + Körper), Telegram (rich + Kurzform), SMS, Premium-SMS und Vorschau sind einzeln geprüft (siehe ACs).

## Estimated Scope

- **LoC:** Produktivcode +30/-15, Tests +200
- **Files:** 2 Produktiv, 2 Doku, 1 neue Testdatei, 2 bis 5 angepasste Bestandstests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `format_alert_location` (`segments.py`) | function | SSOT der Ortsauflösung (Stufenfolge); bleibt unverändert, bekommt nur das vorhandene Label |
| `_location_of`, `_where_when` | function | Ereignis-Ort; bekommen Fallback `e.location_label or msg.location_label` |
| `to_multi_point_alert_message` (`project.py`) | function | Projektion Compare-Δ; setzt `trip_short` und `location_label` (Invariante #1169 AC-7) |
| `to_multi_location_onset_alert_message` (`project.py`) | function | Projektion Compare-Radar |
| `send_multi_location_deviation_alert`, `_dispatch_alert_message` (`notification_service.py`) | service | echter Versandweg, Konsument der Renderer, unverändert |
| `compare_alert_preview_service.py`, `validator_render_service.py` | service | Vorschau und Validator-Render, gleiche Renderer |
| i18n-Katalog `t(...)` | module | keine neuen Schlüssel |
| #1467 K-1/K-2, #1767, #1169 AC-7, #1041 AC-5 | Vorgänger | Präzedenz "Name nur einmal", Mehrort-Radar, Invarianten |

## Implementation Details

Ursache: `to_multi_point_alert_message` setzt `trip_short` UND `location_label` auf dieselbe Sammelbezeichnung. `_km_str` liefert über `format_alert_location` bei gesetztem `location_label` den Ortsnamen; die Kopfzeilen bauen `trip_short · km · …` (Telegram) bzw. `[trip_short] km · …` (Betreff), also steht der Name zweimal. `km 0–0` entsteht, wo der Telegram-Einzelereignis-Zweig `_where_when(e)` ohne Label aufruft und die Events `km_from=km_to=0.0` tragen (Stufe 4 von `format_alert_location`). Die Mail macht es schon richtig (`e.location_label or msg.location_label`).

Fix im Renderer, nicht in der Projektion von `trip_short`:

1. **Kriterium Punkt-Kontext:** `msg.location_label` ist gesetzt. Eine Hilfsfunktion "Ortsteil der Kopfzeile" liefert dann leer (der Name steht schon im `trip_short`-Slot), sonst wie bisher die Kilometer-/Etappenangabe. Genutzt von `render_subject` (Δ-Zweige, Bündel), `render_telegram` (Kopf), `_render_subject_onset` und `_render_telegram_onset`.
2. **Ereigniszeilen:** Ort mit Fallback `e.location_label or msg.location_label` im Telegram-Einzelzweig (wie Mail), in `_onset_shift_where` (Fallback durchreichen) und in `_km_str_onset` für den Einzelort-Radar.
3. **Projektion Radar:** `to_multi_location_onset_alert_message` setzt bei genau einer Gruppe das nachrichtenweite `location_label=<Ort>`. Per-Event-`location_label` bleibt `None` (Invariante #1041 AC-5). `_render_sms_onset` bleibt unberührt (geprüft: es liest nur das per-Event-`e.location_label` und erkennt den Einzelort an `COMPARE_RADAR_SOURCE`; das nachrichtenweite `msg.location_label` liest es nicht). Der Docstring-Satz „bei GENAU einer Gruppe bleibt `location_label=None`" in `to_multi_location_onset_alert_message` wird bewusst präzisiert: gilt fortan für das per-Event-Feld; das nachrichtenweite Feld trägt den Ortsnamen (Punkt-Kontext-Kennzeichen, #2598).
4. **SMS-Kopf ohne `location_positions`** (`render.py` ca. 1933): kein doppelter Name. Im echten Versand nicht erreichbar (Kopf entfällt per `location_positions`, #1467), aber Vorschau und Validator-Render sollen nie doppelt zeigen.
5. `format_alert_location` bleibt unverändert.

Trip-Alarme setzen `location_label` nie (`None`); jede neue Verzweigung ist an dessen Gesetztheit gekoppelt, daher bleibt der Trip-Pfad byte-identisch.

Zielbild (Beispiel-Ausgaben, DE):

- Betreff: `[Ort Eins] ↑ Böen: 30 km/h→60 km/h`; Telegram: `<b>Ort Eins · ↑ Böen</b>`, Zeile `Ort Eins · stärkste Stunde 14:00`
- Bündel: `[Ort Eins, Ort Zwei] 2 Änderungen seit dem Briefing`, `<b>Ort Eins, Ort Zwei · 2 Änderungen seit dem Briefing</b>`
- Beginn-Verschiebung: Betreff `[Ort Eins] …-Beginn 10:00 (2 h früher)`, Zeile `…-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)`
- Radar 1 Ort: `[Ort Eins] Regen in 30 Min`, `<b>Ort Eins · Regen in 30 Min</b>`, Mail `Wo & wann: Ort Eins · ab 14:30`

## Expected Behavior

- **Input:** Ortsvergleich-Alarm (Δ oder Radar) mit einem oder mehreren Orten, beliebiger Kanal, DE oder EN.
- **Output:** Ortsname genau einmal in Kopfzeilen; in Ereigniszeilen der Ortsname statt `km 0–0`; Trip-Alarme unverändert.
- **Side effects:** keine; neue Nutzertexte entfallen, Protokoll-Token (`sms_code`, `compact_label`, Kürzel) bleiben.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Hilfsfunktion Kopfzeilen-Ortsteil; Betreff-, Telegram-, Onset-Köpfe; Ereignis-Ort-Fallback; SMS-Kopf |
| `src/output/renderers/alert/project.py` | MODIFY | Radar mit genau einer Gruppe setzt nachrichtenweites `location_label` |
| `tests/tdd/test_fix_2598_ortsvergleich_alarm_kopfzeile.py` | CREATE | neue Tests über echte Projektionen und Renderer |
| `tests/tdd/test_alert_location_vocabulary.py` | MODIFY | Test um Zeile 405–435 (Docstring „nennt heute 'km 0–0'", Assert `"[Toulon] km 0–0 · Regen in 30 Min"`) friert `km 0–0` ein, auf Zielbild `"[Toulon] Regen in 30 Min"` umstellen |
| `tests/fixtures/alarm_kette/ortsvergleich_radar_verdopplung_vor_2848.json` | MODIFY | Golden-Snapshot ERWARTETER Ausgabe (gelesen von `test_radar_verschaerfung_kennzeichnung_mehrlauf.py::test_ac8_…`, Byte-Vergleich); enthält `[Verschaerfungsdorf] km 0–0 …` und `Wo & wann: km 0–0 · …` → nur diese Ortsteile auf Zielbild ändern (`[Verschaerfungsdorf] Regen in 8 Min …`, `Wo & wann: Verschaerfungsdorf · ab 12:08 …`), alles andere byte-gleich; der Wächter-Zweck von AC-8 #2848 (kein Verschärfungs-Hinweis) bleibt unberührt |
| weitere Bestandstests Compare-Alarm (`test_issue_1169_*`, `test_issue_1170_*`, `test_alert_preview_compare_paritaet.py`, `test_compare_alert_telegram_per_location.py`, `test_fix_1767_*`) | MODIFY (nur falls nötig) | nur, wenn sie die Doppelung wörtlich erwarten; Developer ermittelt per gezieltem Lauf |
| `docs/reference/telegram_format.md`, `docs/reference/renderer_email_spec.md` | MODIFY | Beispiele Ortsvergleich-Kopf ohne Doppelung und ohne km |

### Nicht im Scope

- "Änderung unter" bei Regel "über" (#1895) wird ausdrücklich nicht angefasst.
- Roher `stand_at` in der Probe ist ein Probe-Artefakt, kein Fehler.
- Keine Änderung am Trip-Pfad, an `format_alert_location`, an Protokoll-Token oder am Katalog.
- Keine Änderung des Telegram-Fan-outs je Ort oder des Versandwegs.

### Estimated Changes

- Files: ca. 10
- LoC: Produktivcode +30/-15, Tests +200 (gesamt ca. +230/-15)

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `tests/tdd/test_fix_2598_ortsvergleich_alarm_kopfzeile.py`. Die Tests bauen Nachrichten über die echten Projektionen `to_multi_point_alert_message` und `to_multi_location_onset_alert_message` und rendern mit den echten Renderern (`render_subject`, `render_telegram` rich und Kurzform, `render_email`, `render_sms`, Premium-SMS). Kein Mock, kein Patch (Projekt-Test-Politik: kein Mock-Theater). Vor dem Fix müssen sie rot sein.

- [ ] Test 1: GIVEN 1 Ort/1 Metrik WHEN alle Kanäle gerendert THEN Betreff `[Ort Eins] ↑ Böen: …`, Telegram-Kopf `Ort Eins · ↑ Böen`, Zeile `Ort Eins · stärkste Stunde 14:00`, kein `km 0–0`
- [ ] Test 2: GIVEN 1 Ort/2 Metriken WHEN Betreff und Telegram THEN Name einmal (`[Ort Eins] ↑ 1 über Schwelle: …`)
- [ ] Test 3: GIVEN 2 Orte (Bündel/Vorschau) WHEN Betreff und Telegram THEN Namensliste genau einmal
- [ ] Test 4: GIVEN 1 Ort nur Beginn-Verschiebung WHEN Betreff, Telegram, Mail THEN kein `km 0–0`, Zeile `(2 h früher · Ort Eins)`
- [ ] Test 5: GIVEN Compare-Radar 1 Ort WHEN Betreff, Telegram, Mail THEN `[Ort Eins] Regen in 30 Min`, Kopf ohne km, `Wo & wann: Ort Eins · ab 14:30`
- [ ] Test 6: GIVEN Compare-Radar 2 Orte WHEN gerendert THEN Ausgabe unverändert gegen #1767-Erwartung
- [ ] Test 7: GIVEN beliebiger Ortsvergleich-Alarm (parametrisiert über alle Fälle und Kanäle inkl. Vorschau) WHEN gerendert THEN weder `km 0–0` noch derselbe Ortsname zweimal hintereinander
- [ ] Test 8: GIVEN SMS ohne `location_positions` WHEN `render_sms` THEN Kopf ohne Doppelung
- [ ] Test 9: GIVEN Trip-Δ und Trip-Radar WHEN alle Kanäle THEN Ausgabe byte-identisch zur festen Referenz vor dem Fix (Referenzstrings im Test)
- [ ] Test 10: GIVEN Sprache DE und EN WHEN alle Fälle THEN gleiche Regeln; Protokoll-Token unverändert
- [ ] Test 11: GIVEN umgestellte Bestandstests (`test_alert_location_vocabulary.py`) WHEN Lauf THEN grün auf Zielbild

Gezielte Läufe (nie `uv run pytest` ohne Dateinamen): neue Datei plus `test_alert_location_vocabulary.py`, `test_alert_preview_compare_paritaet.py`, `test_compare_alert_telegram_per_location.py`, `test_fix_1767_nowcast_mehrort_kurzform.py`, `test_issue_1169_*`, `test_issue_1170_*`.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich-Änderungsalarm für genau einen Ort ("Ort Eins") mit genau einer Metrik (Böen 30 → 60 km/h) / When der Alarm als Betreff, Telegram-Nachricht und Mail gerendert wird / Then lautet der Betreff `[Ort Eins] ↑ Böen: 30 km/h→60 km/h`, der Telegram-Kopf `<b>Ort Eins · ↑ Böen</b>` und die Ereigniszeile `Ort Eins · stärkste Stunde 14:00`, der Ortsname steht also nie doppelt und es erscheint kein `km 0–0`
  - Test: Echte Projektion `to_multi_point_alert_message` mit einer Gruppe, gerendert über `render_subject`, `render_telegram`, `render_email`; Ausgabe wird auf die genannten Zeilen geprüft

- **AC-2:** Given ein Ortsvergleich-Änderungsalarm für einen Ort mit mehreren geänderten Metriken / When Betreff und Telegram-Kopf gerendert werden / Then steht der Ortsname genau einmal, z. B. `[Ort Eins] ↑ 1 über Schwelle: …` und `<b>Ort Eins · 1 über Schwelle</b>`
  - Test: Projektion mit einer Gruppe und zwei Metriken, Betreff und Telegram-Kopf werden auf genau ein Vorkommen des Namens geprüft

- **AC-3:** Given ein gebündelter Ortsvergleich-Alarm für zwei Orte (Vorschau und Betreff) / When Betreff und Telegram-Vorschau gerendert werden / Then erscheint die Namensliste nur einmal, z. B. `[Ort Eins, Ort Zwei] …` und `<b>Ort Eins, Ort Zwei · 2 Änderungen seit dem Briefing</b>`
  - Test: Projektion mit zwei Gruppen, Betreff und Telegram-Kopf; `Ort Eins, Ort Zwei` kommt genau einmal vor

- **AC-4:** Given ein Ortsvergleich-Alarm für einen Ort, bei dem sich nur der Beginn verschoben hat (zwei Stunden früher) / When Betreff, Telegram und Mail gerendert werden / Then enthält der Betreff kein `km 0–0` und die Beginn-Zeile lautet in Telegram und Mail `…-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)`
  - Test: Projektion mit einer Gruppe und nur Beginn-Verschiebung, drei Kanäle werden auf Zeile und Fehlen von `km 0–0` geprüft

- **AC-5:** Given ein Ortsvergleich-Radar-Alarm (Regen in 30 Minuten) für genau einen Ort / When Betreff, Telegram und Mail gerendert werden / Then lautet der Betreff `[Ort Eins] Regen in 30 Min`, der Telegram-Kopf `<b>Ort Eins · Regen in 30 Min</b>` ohne Kilometerangabe und die Mail zeigt `Wo & wann: Ort Eins · ab 14:30`
  - Test: Echte Projektion `to_multi_location_onset_alert_message` mit einer Gruppe, gerendert über alle drei Renderer

- **AC-6:** Given ein Ortsvergleich-Radar-Alarm für zwei Orte / When er in allen Kanälen gerendert wird / Then bleibt die Ausgabe unverändert korrekt gegenüber dem Stand von #1767 (Mehrort-Kopf ohne Namens-Join, kein `km 0–0`)
  - Test: Projektion mit zwei Gruppen, Ausgabe wird gegen die bestehenden #1767-Erwartungen und gegen eine feste Referenz geprüft

- **AC-7:** Given jeder Ortsvergleich-Alarm (Änderung und Radar, ein und mehrere Orte) / When er in jedem Kanal gerendert wird (Betreff, Mail, Telegram rich und Kurzform, SMS, Premium-SMS, Vorschau) / Then enthält keine Ausgabe `km 0–0` und keine Ausgabe nennt denselben Ortsnamen zweimal hintereinander
  - Test: Parametrisierter Test über alle Fälle und Kanäle, Prüfung per Regex auf `km 0–0` und auf unmittelbare Namenswiederholung

- **AC-8:** Given der SMS-Kopf-Zweig ohne `location_positions` (Vorschau oder Validator-Render) für einen Ortsvergleich-Alarm / When `render_sms` aufgerufen wird / Then steht der Ortsname im Kopf genau einmal (nicht `Ort Eins Ort Eins: G30->60@14`)
  - Test: `render_sms` über die echte Projektion ohne `location_positions`; Kopf wird auf einmaligen Namen geprüft

- **AC-9:** Given Trip-Alarme (Änderung und Radar) / When sie nach dem Fix in allen Kanälen gerendert werden / Then ist jede Ausgabe byte-identisch zum Stand vor dem Fix, z. B. `[GR20] Segment 3 · ↑ Böen…` und `Segment 3 · stärkste Stunde …`
  - Test: Trip-Projektionen werden gegen im Test hinterlegte Referenzstrings aus dem Stand vor dem Fix auf Gleichheit geprüft

- **AC-10:** Given ein Nutzer mit Sprache Deutsch und einer mit Englisch / When Ortsvergleich-Alarme gerendert werden / Then gilt das Zielbild in beiden Sprachen gleichermaßen, es entstehen keine neuen Katalog-Texte und Protokoll-Token (`sms_code`, `compact_label`, Kürzel) bleiben unverändert
  - Test: Alle Fälle in DE und EN; Prüfung auf Zielbild, auf unveränderte Token und darauf, dass der Katalog keine neuen Schlüssel erhalten hat

- **AC-11:** Given Bestandstests, die Doppelung oder `km 0–0` als Bestandsverhalten einfrieren (`tests/tdd/test_alert_location_vocabulary.py` Test um Zeile 405–435; Golden-Snapshot `tests/fixtures/alarm_kette/ortsvergleich_radar_verdopplung_vor_2848.json`) / When der Fix geliefert wird / Then sind diese Tests bewusst auf das Zielbild umgestellt, die Beispiele in `telegram_format.md` und `renderer_email_spec.md` zeigen Ortsvergleich-Köpfe ohne Doppelung und ohne km, und alle genannten Bestandstests laufen grün
  - Test: Gezielter Lauf der umgestellten Bestandstests und der Compare-Alarm-Tests (siehe Test Plan); grün auf Zielbild

## Definition of Done

- AC-1 bis AC-11 erfüllt; neue Testdatei rot vor dem Fix, grün danach (Kern-Schicht ohne Netz).
- Kein Ortsvergleich-Alarm (Änderung, Beginn-Verschiebung, Radar; 1 Ort und Bündel; DE und EN) enthält in Betreff, Mail, Telegram, SMS, Premium-SMS oder Vorschau „km 0–0“ oder den Ortsnamen doppelt hintereinander.
- Trip-Alarme byte-identisch zum Stand vor dem Fix (eigener Kontrolltest).
- Umgestellte Bestandstests und der Golden-Snapshot grün; Doku-Beispiele angepasst.
- Alle 6 CI-Checks grün; auf Staging ein echter Ortsvergleich-Alarm (Mail und Telegram) ohne Doppelung und ohne „km 0–0“ nachgewiesen; Deploy und Selftest ohne Befund.

## Known Limitations

- "Änderung unter" bei Regel "über" (#1895) bleibt bestehen.
- Der unerreichbare SMS-Kopf-Zweig wird nur wegen Vorschau und Validator-Render bereinigt; der echte Versand entfällt den Kopf weiter per `location_positions`.
- Einzelort-Radar-SMS (`_render_sms_onset`) wird nicht verändert; AC-7 deckt das ab.

## Risiken

- **MEDIUM:** zentraler Alarm-Renderer aller Alarmarten. Schutz: Bedingung an `msg.location_label` gekoppelt, das Trip nie setzt; eigener Byte-Gleichheitstest für Trip (AC-9).
- Mail-Validatoren (`email_spec_validator.py`, Briefing-Validator) lesen den Betreff nur per Fragment; das `[Name]`-Präfix bleibt.
- Das Projektions-Invariant #1169 AC-7 (eine Gruppe byte-identisch zu `to_point_alert_message`) und #1041 AC-5 bleiben gewahrt.
- Bestandstests mit wörtlicher Doppelung müssen bewusst umgestellt werden (AC-11).

## Verworfene Alternativen

- `trip_short` auf einen Sammelbegriff ändern: bricht #1169-AC-7-Invariante und die Betreff-Hausform `[Name]`.
- `location_label` nur im Telegram-Zweig unterdrücken: Betreff und Mail blieben doppelt bzw. km-fehlerhaft, Kanalparität verletzt.
- `format_alert_location` ändern: SSOT mit eigener Stufenfolge, andere Aufrufer wären betroffen; die Korrektur liefert ihr nur das vorhandene Label.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Darstellungsfehler; das Zielbild folgt aus der Trip-Analogie und aus dem bereits richtigen Mail-Körper. Keine Entscheidungsfläche (Kanäle, Provider, Datenmodell) wird verändert. Kanalparität bleibt gemäß ADR-0095 gewahrt.

## Changelog

- 2026-11-09: Initial spec created
