---
entity_id: fix_1275_sms_thunder_today
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
workflow: fix-1275-sms-thunder-today
tags: [bug, sms, thunder, telegram, email, sicherheitsrelevant]
---

# Fix #1275 (Nachtrag): SMS `TH:` ohne Datenanbindung + erfundene Stunde + Telegram-Divergenz

## Approval

- [x] Approved — PO-Freigabe („Go") am 2026-07-16, inklusive der Known Limitations
      (Mail-Gate blockiert den Commit bis zur echten Staging-Testmail; die Golden-Tests
      behalten ihren blinden Fleck und werden nur kompensiert; ein MED-Testfall ist
      provider-abhängig, da `openmeteo.py:524-538` nur HIGH oder NONE liefert).

## Purpose

Diese Spec ERGÄNZT `docs/specs/bugfix/fix_1275_sms_th_mismatch.md` (Vormittags-Fix,
`status: implemented`), behebt aber einen davon unabhängigen, tieferliegenden Defekt: Die
SMS meldet für ihre eigene, berichtete Etappe `TH:-` (kein Gewitter), während die E-Mail
derselben Etappe „Gewitter ab 08:00 · stärkste 08:00" zeigt — weil der `TH:`-Pfad in
`sms_trip.py` niemals `dp.thunder_level` liest. Zusätzlich ist die Stunde in `TH+:H@12`
erfunden (hartkodierte 12 statt der tatsächlich berechneten Stunde), und Telegram rechnet
das Gewitter-Signal eigenständig und ungefenstert, statt dieselbe Datenquelle wie SMS/E-Mail
zu nutzen. Der Fix stellt sicher, dass alle drei Kanäle (SMS, Telegram, E-Mail) für
dieselbe Etappe dieselbe Gewitter-Aussage treffen.

## Source

- **File:** `src/output/renderers/sms_trip.py`
- **Identifier:** `_segments_to_normalized_forecast()` (Zeile 113-165), `_TH_VAL` +
  `HourlyValue(12, …)` (Zeile 221-229)

> **Schicht-Hinweis:** Betroffener Code liegt in `src/output/renderers/` und
> `src/output/tokens/` (Python-Core, SMS-/Telegram-Rendering) sowie
> `src/services/trip_report_scheduler.py` (Datenerzeugung `thunder_forecast`). Kein Go-API-,
> kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~60-70 Source (`metric_format.py`, `sms_trip.py`, `trip_report_scheduler.py`,
  `narrow.py`) + ~100-120 Tests → Gesamt nahe/über 250. **Override auf 400 PO-bestätigt
  (E5: „Testarbeit ist der teure Teil")**.
- **Files:** 8 (1 CREATE Test, 4 MODIFY Source, 3 MODIFY Docs)
- **Effort:** medium-high — Ausgabe-Pfade für zwei Kanäle (SMS, Telegram), Mail-Gate greift.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dp.thunder_level` (`src/app/models.py:105`) | field | Rohdaten-Quelle für Gewitter je Zeitpunkt der Segment-Zeitreihe |
| `ThunderLevel` Enum (`src/app/models.py:33-37`) | enum | NONE/MED/HIGH — **kein LOW** |
| `render_threshold_peak_value()` (`src/output/tokens/metrics.py:29-67`) | function | Bestehender Threshold+Peak-Renderer (Peak strikt `>`, frühestes Maximum gewinnt); wird für `TH:` nutzbar, sobald Samples ankommen — unverändert |
| `thunder_ordinal()` (`src/output/metric_format.py:199-210`) | function | Bestehende Sortier-Skala NONE=0/MED=1/HIGH=2 — bleibt unverändert, NICHT für Label-Rendering verwenden |
| `LEVELS` Label-Skala (`src/output/tokens/metrics.py:14`) | constant | `{0:'-',1:'L',2:'M',3:'H'}` — bleibt unverändert, Golden-Snapshots hängen daran |
| `thunder_forecast`-Erzeuger (`src/services/trip_report_scheduler.py:1495-1583,1641-1719`) | function | Liefert `{"+1"/"+2": {date, level, text}}`; wird um `hour` erweitert, Stunde ist dort bereits berechnet (`min(hours)` bzw. `_local(earliest_ts)`) |
| `render_email()` / `format_sms()` Aufrufkette (`src/output/renderers/trip_report.py:148,224`) | function | Beweis, dass SMS und E-Mail dieselbe `segments`-Variable in einem Aufruf erhalten — SMS/E-Mail können strukturell nicht auf verschiedene Etappen zeigen |
| `render_telegram_bubbles()` (`src/output/renderers/narrow.py:359-371`) | function | Telegram-Renderer — bekommt aktuell kein `thunder_forecast`-Argument, rechnet eigenständig |
| `agg.thunder_level_max` / `_compute_thunder_level()` (`src/services/weather_metrics.py:596-598`) | field/function | Telegrams heutige (ungefensterte) Gewitter-Quelle — wird durch die gefensterte SMS/E-Mail-Quelle ersetzt |
| `_dp()`/`_segment()` Test-Helper (`tests/tdd/test_bug_874_th_plus_sms.py:45-98`) | test helper | Vorlage für mock-freie `SegmentWeatherData`-Fixtures mit `dp.thunder_level` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/metric_format.py` | MODIFY | Neuer kanonischer Producer `thunder_label_value(level) -> int` (NONE=0/MED=2/HIGH=3), additiv neben `thunder_ordinal()`. Docstring grenzt die zwei Skalen (Label vs. Sortierung) explizit gegeneinander ab. |
| `src/output/renderers/sms_trip.py` | MODIFY | Kern-Fix: `dp.thunder_level` in der bestehenden Sammel-Schleife (analog rain/wind/gust) mitsammeln, `thunder_hourly=` im `DailyForecast` setzen. `_TH_VAL` durch `thunder_label_value()` ersetzen. `HourlyValue(12, …)` durch die echte Stunde aus `thunder_forecast["+1"]["hour"]` ersetzen. |
| `src/services/trip_report_scheduler.py` | MODIFY | `hour: Optional[int]` ins `thunder_forecast`-Entry (beide Erzeuger, Zeile ~1580/1711) — additiv, Stunde ist bereits berechnet, wird nur nicht zurückgegeben. |
| `src/output/renderers/narrow.py` | MODIFY | Telegram (`_tg_day_footer` Zeile 164-216, `_overview_line`/`_thunder_severity` Zeile 284-326) auf dieselbe gefensterte Gewitter-Quelle wie SMS/E-Mail umstellen statt `agg.thunder_level_max` (ungefenstert). |
| `tests/tdd/<verhaltensbenannt>.py` | CREATE | Repro-Test **durch `format_sms()`** mit echter `SegmentWeatherData`-Zeitreihe inkl. `dp.thunder_level` (Vorlage `tests/tdd/test_bug_874_th_plus_sms.py:45-98`, mock-frei). Plus: `TH+`-Stunde echt, Telegram-Konsistenz (gefenstert), Telegram-Schweigen bei Gewitter außerhalb der Wanderzeit. Kein Zeichenbudget-Test (E3). |
| `docs/reference/sms_format.md:95-102` | MODIFY | Format-Vertrag: „heute/morgen" absolut → report-relativ (E1: TH:=berichtete Etappe, TH+:=danach). `L = low` streichen — `ThunderLevel` kennt kein LOW. |
| `docs/project/known_issues.md:8-27` | MODIFY | BUG-1275: Status `RESOLVED` revidieren, fehlende Datenanbindung + Telegram-Divergenz als eigenständigen Defekt ergänzen. |
| `docs/specs/bugfix/fix_1275_sms_th_mismatch.md` | MODIFY (Errata) | AC-2 + Dependencies-Zeile 54 behaupten einen nicht existenten Telegram-Konsumpfad über `notification_service.py:222`. Wird als Errata-Changelog-Eintrag DORT ergänzt, nicht neu geschrieben (siehe eigener Abschnitt unten). |

## Implementation Details

**Drei unabhängige Defekte, ein gemeinsamer Fix-Ansatz (PO E2: eine gemeinsame Quelle statt
Flickwerk):**

1. **`TH:` strukturell immer `-`.** `_segments_to_normalized_forecast()`
   (`sms_trip.py:113-122`) sammelt `rain`/`wind`/`gust`/`pop` aus `seg.timeseries`, aber nie
   `dp.thunder_level`. `thunder_hourly` fehlt im gebauten `DailyForecast` (Zeile 157-165) →
   Default `()`. `render_threshold_peak_value()` (`tokens/metrics.py:47-48`) gibt bei leeren
   Samples sofort `"-"` zurück, unabhängig vom tatsächlichen Wetter. Fix: Gewitter-Samples in
   derselben Schleife wie rain/wind/gust mitsammeln (mechanisches Nachziehen eines
   bestehenden Musters), `thunder_hourly` im `DailyForecast` setzen. Ab dann läuft `TH:` durch
   denselben bereits korrekten `render_threshold_peak_value()`-Pfad wie `R`/`PR`/`W`/`G`.

2. **Erfundene Stunde in `TH+`.** `HourlyValue(12, …)` (`sms_trip.py:227`) ist eine
   Konstante, keine Ableitung aus Daten. Die echte Stunde ist in beiden
   `thunder_forecast`-Erzeugern im Scheduler bereits berechnet
   (`trip_report_scheduler.py:1564-1570` `min(hours)`, `:1701-1704` `_local(earliest_ts)`),
   wird aber nicht zurückgegeben — nur in den `text`-String eingebettet, den niemand parst.
   Fix: `hour`-Feld additiv ins `thunder_forecast`-Dict aufnehmen; SMS nutzt es statt der
   Konstante.

3. **Telegram rechnet eigenständig UND ungefenstert.** `narrow.py:164-216,284-326` nutzt
   `agg.thunder_level_max`, berechnet in `weather_metrics.py:596-598` über die
   **ungefensterte** Zeitreihe der ganzen Etappe. SMS (`sms_trip.py:106-110`) und E-Mail
   (`trip_report.py:269-275`) fenstern dagegen korrekt auf die geplante Wanderzeit
   (`start_h <= h <= end_h`). Folge: Ein Gewitter außerhalb der Wanderzeit (z. B. nachts) kann
   Telegram als HIGH melden, während SMS/E-Mail zu Recht schweigen — unabhängig vom
   ursprünglich gemeldeten Bug, aber derselbe Fehlermodus (fehlende gemeinsame
   Datengrundlage). Fix: Telegram liest dieselbe gefensterte Quelle wie SMS/E-Mail statt
   `agg.thunder_level_max` neu zu berechnen.

**Skalen-Konsolidierung (Landmine, entschärft):** Zwei Zahlenskalen existieren nebeneinander
und MÜSSEN es auch bleiben — sie bedeuten Verschiedenes: `LEVELS = {0:'-',1:'L',2:'M',3:'H'}`
(`tokens/metrics.py:14`) ist die **Render-Label-Skala** (wird nicht angetastet, sonst brechen
alle Golden-Snapshots ohne Sicherheitsgewinn). `thunder_ordinal()` `{NONE:0,MED:1,HIGH:2}`
(`metric_format.py:199-210`) ist die **Sortier-Ordnung** für Vergleiche/Peak-Ermittlung. Statt
eine der beiden umzubauen, entsteht ein dritter, kanonischer Producer
`thunder_label_value(level) -> int` (NONE=0/MED=2/HIGH=3) in `metric_format.py`, der exakt auf
`LEVELS` zielt und `_TH_VAL` (`sms_trip.py:221`) ersetzt. Der Docstring MUSS die drei Skalen
(Label, Ordinal, `thunder_label_value`) gegeneinander abgrenzen — sonst baut die nächste
Änderung MED→1→'L' und produziert einen stillen Fehler, den kein bestehender Test fängt.

**Warum keine Prosa-Schleifen-Vereinheitlichung nötig ist:** `render_threshold_peak_value()`
und die E-Mail-Prosa-Schleife (`email/helpers.py:1350-1367`) sind nachweislich derselbe
Algorithmus (Peak strikt `>`, frühestes Maximum gewinnt; Threshold erster Wert `>= 1`). Die
Kanäle divergieren nicht im Algorithmus, sondern ausschließlich in den Rohdaten, die bei SMS
bisher gar nicht ankamen. Der Fix reduziert sich damit auf: gleiche Rohdaten (Fix 1+2) + gleiche
Skala (Konsolidierung) + gleiche Fensterung (Fix 3) — kein neuer gemeinsamer Renderer nötig.

## Expected Behavior

- **Input:** `SegmentWeatherData` mit `timeseries` inkl. `dp.thunder_level` je Zeitpunkt
  (SMS/E-Mail), `thunder_forecast`-Dict mit `hour`-Feld (SMS `TH+`), dieselbe gefensterte
  Zeitreihe für Telegram.
- **Output:** `TH:{level}@{h}({max}@{h})` bzw. `TH:-` nur wenn im Wanderfenster wirklich kein
  Gewitter auftritt; `TH+:{level}@{h}(...)` mit echter Stunde statt der Konstante 12; Telegram
  meldet für dieselbe Etappe dieselbe Aussage wie SMS/E-Mail, schweigt bei Gewitter außerhalb
  der Wanderzeit.
- **Side effects:** SMS-Zeilenlänge für `TH:` wächst im Gewitterfall von 2 auf bis zu ~13
  Zeichen (PO-akzeptiert, E3). Keine zusätzlichen API-Calls — alle drei Fixes konsumieren
  bereits vorhandene, nur bisher ungenutzte bzw. unvollständig durchgereichte Daten.

## Acceptance Criteria

- **AC-1 (Bug-Nachweis):** Given ein Abend-Briefing für eine Etappe, deren E-Mail
  „Gewitter ab 08:00 · stärkste 08:00" zeigt (SEG 1, 08 Uhr) / When die SMS für dieselbe
  Etappe erzeugt wird / Then zeigt die SMS `TH:H@8` statt `TH:-` — passend zur
  E-Mail-Aussage, kein Widerspruch mehr zwischen den beiden Kanälen für dieselbe Etappe.
  - Test: Reproduktion **durch `format_sms()`** mit einer echten `SegmentWeatherData`-Zeitreihe
    (mind. 2 Segmente), bei der `dp.thunder_level=HIGH` genau um 08:00 gesetzt ist —
    NICHT durch direkten Aufruf von `build_token_line()` mit vorgefertigtem
    `DailyForecast(thunder_hourly=…)`. Diese Abkürzung (vgl.
    `tests/golden/test_sms_golden.py:63-122`) hat den Bug bisher überleben lassen, weil sie
    `_segments_to_normalized_forecast()` umgeht — genau die Funktion, die den Defekt enthält.

- **AC-2:** Given eine Etappe, in der während der gesamten geplanten Wanderzeit kein
  einziger Gewitter-Datenpunkt über `NONE` liegt / When die SMS für diese Etappe erzeugt
  wird / Then zeigt `TH:-` — kein fälschlich erfundenes Gewitter-Signal, wo keins ist.
  - Test: `format_sms()` mit `SegmentWeatherData`, deren gesamte Zeitreihe
    `thunder_level=NONE` trägt; Assertion `"TH:-"` im Token-String.

- **AC-3:** Given eine Folge-Etappe, deren Gewitter-Maximum tatsächlich um 6 Uhr auftritt
  (nicht um 12) / When die SMS `TH+:` für diese Folge-Etappe erzeugt wird / Then zeigt
  `TH+:H@6` — niemals die hartkodierte Stunde 12, wenn das echte Gewitter zu einer anderen
  Zeit beginnt.
  - Test: `format_sms()` mit `thunder_forecast["+1"]["hour"]=6` gesetzt, Assertion auf `@6`
    im `TH+`-Token, nicht `@12`.

- **AC-4:** Given einen Trip-Report mit Gewitter innerhalb der geplanten Wanderzeit einer
  Etappe / When SMS, Telegram und E-Mail für dieselbe Etappe im selben Versand erzeugt
  werden / Then zeigen alle drei Kanäle dasselbe Gewitter-Level (und dieselbe ungefähre
  Uhrzeit) — kein Kanal widerspricht einem anderen.
  - Test: Denselben Fixture-Trip aus AC-1 durch SMS-, Telegram- und
    E-Mail-Formatierungspfad schicken, Gewitter-Level in allen drei Ausgaben vergleichen
    (Vergleich der gerenderten Ausgaben gegeneinander, kein reiner Dict-Inhalts-Check).

- **AC-5:** Given eine Etappe mit einem Gewitter-Ereignis ausschließlich außerhalb der
  geplanten Wanderzeit (z. B. nachts, 02:00) / When Telegram, SMS und E-Mail für diese
  Etappe erzeugt werden / Then meldet Telegram ebenfalls kein Gewitter — analog zu SMS
  `TH:-` und der E-Mail ohne Gewitter-Hinweis; kein Kanal warnt vor einem Ereignis, das
  außerhalb der Wanderzeit liegt.
  - Test: Fixture mit `dp.thunder_level=HIGH` ausschließlich bei Stunden außerhalb
    `[start_h, end_h]`, alle drei Kanäle rendern, Assertion dass keiner Gewitter meldet.

- **AC-6:** Given einen beliebigen Trip-Report / When SMS und E-Mail für dieselbe Etappe im
  selben Versand-Aufruf erzeugt werden / Then können sich beide strukturell nicht
  widersprechen, weil sie aus derselben Segment-Zeitreihe berechnet werden — geprüft an
  einem Fixture mit `dp.thunder_level=HIGH` um eine feste Stunde, bei dem SMS `TH:H@<h>`
  und die E-Mail-Prosa dieselbe Stunde nennen.
  - Test: `render_email()` und `format_sms()` aus derselben `segments`-Variable im selben
    Testlauf aufrufen (Nachbau von `trip_report.py:148/224`), Stunde in beiden Ausgaben
    vergleichen.

## Known Limitations

- `renderer_mail_gate` (`renderer_mail_gate.py:44`) blockiert jeden Commit, der
  `sms_trip.py` staged, bis `tests/tdd/test_issue_811_mode_matrix.py` grün ist UND ein
  `briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail erfolgreich war —
  eingeplante Pflichtarbeit vor dem Commit dieses Fixes.
- Die Golden-Snapshots (`tests/golden/sms/gr20-summer-evening.txt` zeigt `TH:M@16(H@18)`)
  bleiben gültig — Builder/`tokens/metrics.py` werden nicht verändert. Sie testen aber
  weiterhin nur die Builder-Schicht, nicht den Glue (`_segments_to_normalized_forecast()`),
  der Gegenstand dieses Fixes ist. Die Golden-Tests allein hätten den Bug nie fangen können.
- `openmeteo.py:524-538` liefert nur HIGH oder NONE (WMO-Codes 95/96/99) — ein MED-Testfall
  ist damit provider-abhängig und wird in diesem Fix nicht gegen einen echten Provider
  verifiziert, nur gegen synthetische Fixture-Daten.

## Out of Scope

- **Zeichenbudget** — PO-Entscheid E3: `TH:` darf von 2 auf bis zu 13 Zeichen wachsen,
  „Gewitter ist wichtiger, faktisch ist genug Platz." Die Kappungs-Reihenfolge ist bereits
  korrekt (`builder.py:41`: `TH:`=Priorität 10, `TH+:`=9, gedroppt wird aufsteigend nach
  Priorität → Gewitter fliegt zuletzt). Keine Budget-Fixture in diesem Fix.
- **`trend[0]` vs. Kalendertag / Ruhetage** — die Known Limitation der Vormittags-Spec
  (`fix_1275_sms_th_mismatch.md:179-190`) ist bereits sauber gelöst:
  `trip_report_scheduler.py:1514-1526` matcht explizit über `trend_by_date[fc_date]`, nicht
  über Listenindex. Kein latenter Bug, nicht anfassen (Fund B der Analyse).
- **`src/output/adapters/trip_result.py:72`** (`thunder_hourly=()`) — reiner
  CLI-/`text_report`-Pfad (`cli.py:25`), das Wintersport-DTO hat kein Gewitterfeld. Kein Bug.
- **E-Mail-Prosa-Schleife auf gemeinsamen Helper heben** — kein belegbarer Mehrwert, der
  Algorithmus ist bereits nachweislich identisch zu `render_threshold_peak_value()`; die
  Schleife (`email/helpers.py:1350-1367`) liegt zudem im gate-geschützten Renderer-Code.
  Separates Hardening-Ticket, falls je gewünscht.
- **`LEVELS[1]='L'` entfernen** — unerreichbar, da `ThunderLevel` (`models.py:33-37`) kein
  LOW kennt und `openmeteo.py:524-538` nur HIGH oder NONE liefert. Bleibt stehen, wird nur
  dokumentiert (Doku-Korrektur in `sms_format.md`), nicht aus dem Code entfernt.

## Errata zur Vormittags-Spec

`docs/specs/bugfix/fix_1275_sms_th_mismatch.md` (Status `implemented`) enthält in AC-2 und
in der Dependencies-Tabelle (Zeile 54) eine faktisch falsche Behauptung: Telegram konsumiere
`thunder_forecast` über `notification_service.py:222`. Tatsächlich hat
`render_telegram_bubbles()` (`narrow.py:359-371`) **kein** `thunder_forecast`-Argument, und
`trip_report.py:189-201` übergibt es auch nicht — `request.thunder_forecast` fließt
ausschließlich in `render_email()` (`trip_report.py:154`) und `format_sms()` (`:231`). Kein
Test des Vormittags-Fix erwähnt Telegram, folglich wurde AC-2 nie gegen den echten
Renderpfad geprüft.

**Arbeitspaket dieser Spec:** Nach erfolgreicher Implementierung dieses Fixes wird
`fix_1275_sms_th_mismatch.md` NICHT neu geschrieben, sondern erhält einen
Errata-Changelog-Eintrag, der (a) AC-2 als „nie gegen den echten Renderpfad geprüft, siehe
Fund A in `fix-1275-sms-thunder-today`" markiert und (b) die Dependencies-Zeile 54 auf den
tatsächlichen Zustand vor diesem Fix (kein Telegram-Konsumpfad) korrigiert. Die inhaltliche
Behebung (Telegram liest jetzt dieselbe gefensterte Quelle) ist Teil dieser Spec (AC-4/AC-5),
nicht der alten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** Die ADR-Datei wird parallel vom Hauptkontext geschrieben (nicht Teil dieser
  Spec-Arbeit). Architektur-relevant ist die Entscheidung, Gewitter-Daten über alle drei
  Ausgabe-Kanäle (SMS, Telegram, E-Mail) aus derselben gefensterten Rohdatenquelle und
  derselben kanonischen Label-Skala (`thunder_label_value()`) abzuleiten, statt jeden Kanal
  eigenständig rechnen zu lassen — die Wurzelursache, die #1275 zweimal produziert hat.

## Changelog

- 2026-07-16: Initial spec created — ergänzt `fix_1275_sms_th_mismatch.md` nach
  Wiedereröffnung von #1275 (Track: Standard, Intake-Score 2). Deckt die vom
  Vormittags-Fix (`e08a51c8`) nicht berührten Defekte in `sms_trip.py` (kein
  `TH:`-Datenpfad, erfundene `TH+`-Stunde) sowie die neu gefundene Telegram-Divergenz
  (Fund A) ab.
