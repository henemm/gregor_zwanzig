# Context: fix-1275-sms-thunder-today

Issue: [#1275](https://github.com/henemm/gregor_zwanzig/issues/1275) — wieder geöffnet 2026-07-16
Track: Standard (Intake-Score 2) · Vorgänger-Fix: `e08a51c8` (nur TH+, `sms_trip.py` nicht angefasst)

## Request Summary

Der PO meldet: SMS `E7: … R5.2@8 PR43%@9 W- G40@8(47@9) TH:- TH+:H@12` widerspricht der
E-Mail derselben Etappe („Gewitter ab 08:00 · stärkste 08:00", SEG 1 um 08 Uhr `Thdr ⚡⚡`).
Zwei Fehler: `TH:` hat **gar keine Datenanbindung**, und die Stunde in `TH+:` ist **erfunden**.

**Beweis, dass beide Kanäle dieselbe Etappe beschreiben:** SMS `R5.2@8` und `G40@8(47@9)`
entsprechen exakt der E-Mail-Tabelle (SEG 1, 08 Uhr Rain 5.2 / Gust 40; 09 Uhr Gust 47).
Die Frage „welcher Tag" ist damit ohne Rückfrage beantwortet.

## PO-Entscheidungen (2026-07-16)

- **E1 — Semantik (bestätigt, war nie strittig):** `TH:` = berichtete Etappe, `TH+:` = die
  danach. Morgen-Briefing: heute / morgen. Abend-Briefing: **morgen / übermorgen**.
  Deckt sich mit `trip_report_scheduler.py:533` („today for morning, tomorrow for evening").
- **E2 — Rechenweg:** **Eine gemeinsame Quelle für alle Kanäle.** Nicht nur die zwei Fehler
  flicken — genau die Konstruktion beseitigen, die den Bug erzeugt hat (Lessons Learned aus
  #1275, `known_issues.md:26`).
- **E3 — Zeichenbudget:** Dass `TH:` von 2 auf bis zu 13 Zeichen wächst, ist **gewollt**:
  „Gewitter ist wichtiger. Und faktisch ist genug Zeichen Platz." Keine Sonderarbeit.
- **E4 — Telegram:** wird **mitrepariert** (Fund A) — Kanal wie SMS und E-Mail.
- **E5 — LoC:** Override auf **400** freigegeben (Testarbeit ist der teure Teil).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/sms_trip.py:70-166` | **Kern-Defekt**: `_segments_to_normalized_forecast()` sammelt `rain/wind/gust/pop` aus `seg.timeseries` (Z. 113-122), liest `dp.thunder_level` **nie**; `thunder_hourly` fehlt im `DailyForecast` (Z. 157-165) → Default `()`. |
| `src/output/tokens/metrics.py:47-48` | `render_threshold_peak_value()` gibt bei leeren Samples sofort `"-"` → **`TH:` ist strukturell immer `-`**. |
| `src/output/renderers/sms_trip.py:221-229` | `_TH_VAL` + `HourlyValue(12, …)` — die **hartkodierte Stunde**. `thunder_forecast["+1"]` liefert nur `level`. |
| `src/output/renderers/email/helpers.py:1350-1367` | **Die funktionierende Referenz**: Inline-Schleife über `dp.thunder_level`; „erste" = erster mit `thunder_ordinal ≥ 1`, „stärkste" = striktes `>` (erstes Maximum gewinnt). Kein wiederverwendbarer Helper — Gewitter ist der einzige Sonderfall, weil `_first_and_peak()` (`:1125-1139`) rein numerisch arbeitet. |
| `src/output/tokens/metrics.py:29-67` | `render_threshold_peak_value()` erzeugt bereits `M@16(H@18)` — **exakt die „ab/stärkste"-Semantik der E-Mail**. Die Formate passen konzeptionell schon zusammen. |
| `src/output/tokens/builder.py:196,203-208` | `TH:` aus `today.thunder_hourly`, `TH+:` aus `tomorrow.thunder_hourly`, beide `is_level=True`. Default-Threshold 1.0 (`:59`). |
| `src/services/trip_report_scheduler.py:1495-1583,1641-1719` | Die drei `thunder_forecast`-Erzeuger nach `e08a51c8`. Rückgabe je `"+1"`/`"+2"`: `{date, level, text}` — **die Stunde steckt nur im `text`-String**, niemand parst sie. |
| `src/output/metric_format.py:199-210` | Kanonische Ordnung `thunder_ordinal()` NONE=0/MED=1/HIGH=2. |
| `src/app/models.py:33-37,105,350` | `ThunderLevel` = NONE/MED/HIGH (**kein LOW**), Feld `dp.thunder_level`, Aggregat `thunder_level_max`. |
| `docs/reference/sms_format.md:95-96,99` | Format-Vertrag `TH:{level}@{h}({max}@{h})`. **Zwei Doku-Fehler**: „heute/morgen" absolut statt report-relativ; `L = low` dokumentiert, obwohl das Enum kein LOW kennt. |
| `docs/specs/bugfix/fix_1275_sms_th_mismatch.md:177-197` | Known Limitations des Vormittags-Fix: `trend[0]`-vs-Kalendertag-Semantik **offen gelassen**; `_TH_VAL`-Sonderordnung als Nebenbefund vertagt. Beides schlägt jetzt zurück. |
| `docs/project/known_issues.md:8-27` | BUG-1275-TH-MISMATCH, Status RESOLVED — muss revidiert werden. |

## Existing Patterns

- **Threshold+Peak-Rendering ist bereits vereinheitlicht** (`render_threshold_peak_value`)
  — `R`, `PR`, `W`, `G` nutzen es, `TH` würde es nutzen, sobald Samples ankommen.
- **Sammel-Schleife über `seg.timeseries`** (`sms_trip.py:113-122`) — das Muster für
  Gewitter existiert bereits dreimal daneben (rain/wind/gust/pop). Nachziehen ist mechanisch.
- **`_dedup_by_hour`** greift schon; Gewitter-Samples brauchen keinen Sonderweg.

## Dependencies

- **Upstream:** `dp.thunder_level` (`models.py:105`), `seg.timeseries`, `thunder_forecast`
  aus dem Scheduler.
- **Downstream:** SMS-Token-Zeile; Telegram erbt über `trip_report.py:154/231`;
  E-Mail-Vorschau-Block (`email/html.py:1083-1087`, `email/plain.py:233-237`) nutzt
  `thunder_forecast["text"]`.
- **Nicht betroffen:** `src/output/adapters/trip_result.py:72` (`thunder_hourly=()`) — reiner
  CLI-/`text_report`-Pfad (`cli.py:25`), Wintersport-DTO hat kein Gewitterfeld. Kein Bug.

## Risks & Considerations

1. **LANDMINE — zwei Zahlenskalen für dieselbe Sache.** `_TH_VAL` (SMS) = `{NONE:0, MED:2,
   HIGH:3}` zielt auf die Builder-Label-Skala `LEVELS = {1:'L', 2:'M', 3:'H'}`
   (`tokens/metrics.py:60-62`). Die Trend-/Scheduler-Pfade nutzen `{0,1,2}`
   (`trip_report_scheduler.py:1429,1560,1670`) = Sortier-Ordnung. **Beide landen in
   `HourlyValue.value`.** Ein MED-Sample aus dem Trend (value=1) rendert der Builder als
   `L`. Wer beim „eine Quelle"-Umbau naiv `thunder_ordinal()` einsetzt, macht aus MED ein L
   und aus HIGH ein M — stiller Fehler, den kein bestehender Test fängt.
2. **Golden-Tests bestätigen toten Code.** `tests/golden/test_sms_golden.py:69-122` und
   `tests/unit/test_renderers_sms.py:50-53` speisen `DailyForecast(thunder_hourly=…)`
   **direkt in den Builder** und umgehen `_segments_to_normalized_forecast()`. Die Snapshots
   zeigen `TH:M@16(H@18)` (`tests/golden/sms/gr20-summer-evening.txt`), die Produktion
   liefert `TH:-`. **Das ist die QA-Versagens-Ursache** — grün ohne Aussagekraft.
   `tests/tdd/test_sms_preview_matches_sent.py:107` assertiert sogar `"TH:" not in
   token_line` — grün aus dem falschen Grund.
3. **Kein Test durch den echten Pfad.** Kein einziger Test ruft `format_sms()` mit
   `SegmentWeatherData` inkl. `timeseries` und gesetztem `dp.thunder_level`. Fixture fehlt;
   `tests/tdd/test_bug_874_th_plus_sms.py` hat Segment-Bauer, aber ohne Gewitter.
   **Der Repro-Test muss genau diese Lücke schließen** — sonst ist der Fix nicht bewiesen.
4. **Stunde für `TH+` muss durchgereicht werden.** `thunder_forecast`-Entry hat keine
   `hour`. Ohne Erweiterung bleibt `TH+` stundenlos (oder erfunden).
5. **SMS-Zeichenbudget (160).** `TH:M@16(H@18)` ist länger als `TH:-` — bei voller Zeile
   kann das Budget kippen. Prüfen, ob die Kappungslogik greift.
6. **Doku ist an zwei Stellen falsch** (s. `sms_format.md`) — gehört mit korrigiert, sonst
   liest der nächste „heute/morgen" und baut den Bug erneut.
7. **`known_issues.md` sagt RESOLVED** für BUG-1275 — irreführend, solange `TH:` tot ist.

## Aufwand (Schätzung aus der Recherche)

| Teil | LoC |
|---|---|
| `sms_trip.py` — Gewitter-Samples sammeln + `thunder_hourly` setzen | ~12 |
| Kanonischer `thunder_label_value()` in `metric_format.py`, ersetzt `_TH_VAL` | ~10 |
| `thunder_forecast`-Entry um `hour` erweitern (2 Erzeuger) + SMS nutzt sie | ~8 |
| Optional: `helpers.py:1350-1367` auf gemeinsamen Helper heben (echte Ein-Quellen-Parität) | ~15 |
| **Tests** (der teure Teil): `format_sms()` mit echter Zeitreihe + Gewitter | ~60-80 |

## Analysis (Phase 2, 2026-07-16)

### Type

**Bug** — nutzersichtbarer Widerspruch zwischen zwei Kanälen, sicherheitsrelevant.

### Härterer Beweis als der Zahlenvergleich

`trip_report.py:148` (`render_email(segments=segments)`) und `:224`
(`SMSTripFormatter().format_sms(segments, …)`) bekommen **dieselbe Python-Variable
`segments`** innerhalb **eines** `format_email()`-Aufrufs. SMS und E-Mail **können** in
Produktion gar nicht auf verschiedene Etappen zeigen — das folgt aus dem Aufrufbaum, nicht
aus einer Zahlen-Heuristik. (Der Zahlenvergleich `R5.2@8`/`G40@8(47@9)` bleibt als
Zusatz-Indiz gültig.)

### Fund A (NEU, Challenger) — der übersehene fünfte Rechenweg: Telegram

`render_telegram_bubbles()` (`narrow.py:359-371`) hat **kein** `thunder_forecast`-Argument;
`trip_report.py:189-201` übergibt es auch nicht. Telegram rechnet eigenständig:
- `narrow.py:164-216` (`_tg_day_footer`) — „⚡ kein/MED/HIGH" aus `agg.thunder_level_max`
- `narrow.py:284-326` (`_overview_line`) — eigener `_thunder_severity()`

**Zwei Konsequenzen:**
1. **Die Vormittags-Spec ist faktisch falsch.** `fix_1275_sms_th_mismatch.md` AC-2 +
   Dependencies-Tabelle (Z. 54) behaupten, Telegram konsumiere `thunder_forecast` über
   `notification_service.py:222`. Tatsächlich fließt `request.thunder_forecast` nur in
   `render_email()` (`trip_report.py:154`) und `format_sms()` (`:231`). **Kein Test des
   Vormittags-Fix erwähnt Telegram** → AC-2 wurde nie gegen den echten Renderpfad geprüft.
   Das ist derselbe Fehlermodus wie beim `TH:`-Pfad: gegen eine Spec geprüft, die die
   Wirklichkeit falsch beschreibt. → **Errata-Nachtrag nötig** (Spec-Status ist `implemented`).
2. **Latente Divergenz, unabhängig von diesem Bug:** `agg.thunder_level_max` wird in
   `weather_metrics.py:596-598` (`_compute_thunder_level`) über die **ungefensterte**
   `timeseries.data` berechnet — ohne die `start_h <= h <= end_h`-Fensterung, die SMS
   (`sms_trip.py:106-110`) und E-Mail (`trip_report.py:269-275`) anwenden. **Ein Gewitter
   außerhalb der Wanderzeit (z.B. nachts) zeigt Telegram als HIGH, während SMS/E-Mail
   korrekt schweigen.** Nur unentdeckt, weil bisher nur SMS↔E-Mail verglichen wurde.

### Fund B (Challenger) — NICHT im Scope, entgegen erster Vermutung

Die Known Limitation der Vormittags-Spec (`fix_1275_sms_th_mismatch.md:179-190`,
„`trend[0]` vs. Kalendertag bei Ruhetagen") ist **bereits sauber gelöst**:
`_build_thunder_forecast_from_trend_or_fetch()` matcht explizit über
`trend_by_date[fc_date]` mit `fc_date = target_date + timedelta(days=offset)`
(`trip_report_scheduler.py:1514-1526`) — nicht über Listenindex. Kein latenter Bug.
**Nicht mitreparieren.**

### Fund C (Challenger) — Zeichenbudget: KEIN Risiko (PO-Entscheid E3)

`TH:` belegt heute 2 Zeichen (`-`), nach dem Fix bis zu ~13 (`M@16(H@18)`).

**PO-Entscheid E3 (2026-07-16):** „Ja, das ist korrekt so! Gewitter ist wichtiger. Und
faktisch ist genug Zeichen Platz." → **Kein Befund, keine Sonderarbeit.**

Deckt sich mit dem Code: `builder.py:41` gibt `TH:` Priorität 10 und `TH+:` Priorität 9;
`render.py:73-83` droppt **aufsteigend** nach Priorität — Gewitter fliegt also als
**Letztes**, `PR`(5), `R`(7), `W`/`G`(8) zuerst. Die gewünschte Rangfolge ist bereits
korrekt verdrahtet. Keine Budget-Fixture im Scope.

### Skalen-Landmine — entschärft (Risiko 1 revidiert)

Weniger gefährlich als angenommen: `LEVELS = {0:'-',1:'L',2:'M',3:'H'}`
(`tokens/metrics.py:14`) wird **ausschließlich** von `sms_trip.py:228` gefüttert; die
Golden-Fixtures nutzen bereits die {0,2,3}-Skala (`test_sms_golden.py:79,92,119,138`).
`format_trend_tokens()` (`email/helpers.py:759-871`) nutzt `render_threshold_peak_value()`
schon heute — mit Ordinal-Skala **plus** `level_labels={1:"MED",2:"HIGH"}`-Override, umgeht
`LEVELS` also sauber.

**Wichtig:** `render_threshold_peak_value()` (`tokens/metrics.py:47-67`) und die
E-Mail-Prosa-Schleife (`helpers.py:1350-1367`) sind **nachweislich derselbe Algorithmus**
(Peak: strikt `>`, frühestes Maximum gewinnt; Threshold: erster `>= 1`; None wird
übersprungen). Die Kanäle divergieren **nicht** im Algorithmus — nur die SMS sammelt keine
Daten. Das verkleinert „eine gemeinsame Quelle" auf: **gleiche Rohdaten + gleiche Skala**.

→ **Kein Umbau von `LEVELS`** (bräche alle Golden-Snapshots ohne Sicherheitsgewinn).
Stattdessen kanonischer Producer `thunder_label_value()` in `metric_format.py` neben
`thunder_ordinal()`, mit Docstring-Kontrast der zwei Skalen; ersetzt `_TH_VAL`
(`sms_trip.py:221`).

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/metric_format.py` | MODIFY | `thunder_label_value(level) -> int` neu (NONE=0/MED=2/HIGH=3), additiv, Docstring grenzt gegen `thunder_ordinal()` ab. |
| `src/output/renderers/sms_trip.py:113-122,157-165` | MODIFY | **Kern-Fix**: `dp.thunder_level` in der bestehenden Schleife mitsammeln (Muster wie rain/wind/gust), `thunder_hourly=` im `DailyForecast` setzen. `_TH_VAL` (:221) → Helper. `HourlyValue(12,…)` (:227) → echte Stunde. ⚠️ **löst `renderer_mail_gate` aus** (`renderer_mail_gate.py:44`). |
| `src/services/trip_report_scheduler.py:1580,1711` | MODIFY | `hour: Optional[int]` ins `thunder_forecast`-Entry. Stunde ist in beiden Erzeugern bereits berechnet (`min(hours)` bzw. `_local(earliest_ts)`), wird nur nicht zurückgegeben. |
| `src/output/renderers/narrow.py:164-216,284-326` | MODIFY | **Telegram (PO-Entscheid)**: auf dieselbe gefensterte Gewitter-Quelle wie SMS/E-Mail umstellen statt `agg.thunder_level_max` (ungefenstert). |
| `tests/tdd/<verhaltensbenannt>.py` | CREATE | Repro **durch `format_sms()`** mit echter `SegmentWeatherData`-Zeitreihe inkl. `dp.thunder_level`; Vorlage `tests/tdd/test_bug_874_th_plus_sms.py:45-98` (`_dp()`/`_segment()`, mock-frei). Plus: `TH+`-Stunde echt, Telegram-Konsistenz (gefenstert). **Keine** Budget-Fixture (E3). |
| `docs/reference/sms_format.md:95-102` | MODIFY | „heute/morgen" → report-relativ (E1). `L = low` streichen — `ThunderLevel` kennt kein LOW (`models.py:33-37`), und `openmeteo.py:524-538` liefert nur HIGH oder NONE. |
| `docs/project/known_issues.md:8-27` | MODIFY | BUG-1275: Status RESOLVED revidieren, Datenanbindungs-Defekt + Telegram ergänzen. |
| `docs/specs/bugfix/fix_1275_sms_th_mismatch.md` | MODIFY | **Errata**: AC-2 beschreibt einen nicht existenten Telegram-Konsumpfad. |

### Scope Assessment

- Dateien: **8** (1 CREATE Test, 4 MODIFY Source, 3 MODIFY Docs)
- LoC: Source ~60–70, Tests ~100–120 → **Gesamt nahe/über 250** (Docs zählen nicht)
- Risiko: **MEDIUM–HIGH** — `sms_trip.py` + `narrow.py` sind Ausgabe-Pfade für zwei Kanäle;
  Mail-Gate blockiert den Commit bis echte Test-Mails grün sind.

### Reihenfolge

1. `thunder_label_value()` — fundamental, isoliert, keine Abhängigen.
2. `hour`-Feld im Scheduler — additiv, unabhängig von (1).
3. `sms_trip.py` — konsumiert (1)+(2); hier greift das Mail-Gate.
4. `narrow.py` (Telegram) — zuletzt, findet die Quelle dann etabliert vor.
5. Repro-Tests parallel zu (3)/(4) — TDD: erst rot.
6. Docs + Errata zum Schluss.

### Offene Punkte

- **LoC-Limit:** Standard 250 wird durch die Testarbeit voraussichtlich gerissen →
  Override auf 400 nötig (PO-Erlaubnis erforderlich).
- **Mail-Gate:** vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün +
  `briefing_mail_validator.py` erfolgreich (echte Staging-Testmail).
