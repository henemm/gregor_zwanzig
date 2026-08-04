---
entity_id: fix_1474b_gewitterschwelle_cockpit
type: bugfix
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.0"
tags: [gewitter, cockpit, mail, sms, issue-1474]
---

# Gewitterschwelle vereinheitlicht, Cockpit unterscheidet „leicht" von „kein Risiko" (Issue #1474, Folge-Scheibe)

## Approval

- [ ] Approved

## Purpose

Schließt zwei Lücken, die #1474 (S3, vierte Gewitterstufe „leicht") bewusst offen gelassen
hat. **Hälfte A:** Drei Stellen beantworten heute unterschiedlich, ab welcher Gewitterstufe
gemeldet wird (SMS-Kürzel `TH:` konfigurierbar, Mail-Trend-Block und Mail-Prosa-Satz fest
verdrahtet) — künftig lesen alle drei dieselbe, pro Trip einstellbare Erwähnungsschwelle,
Standardwert „ab leicht". **Hälfte B:** Das Cockpit zeigt „leicht" heute wie „kein Risiko"
(beides grün) — künftig zeigt eine Etappe mit mindestens einem „leichten" Risiko Gelb, wie
mittleres Risiko, ohne eine vierte Cockpit-Farbe einzuführen.

## Source

- **File:** `src/output/renderers/email/helpers.py`, `src/output/renderers/email/html.py`,
  `src/output/renderers/email/plain.py`, `src/output/renderers/email/compact.py`,
  `src/services/stage_weather.py`
- **Identifier:** `_sms_mention_threshold()`, `_pill_for_metric()`,
  `build_metrics_summary_pills()`, `format_trend_tokens()`, `_compute_one_stage()`

**Schicht:** ausschließlich Python-Core (`src/output/`, `src/services/`). **Kein Go, kein
Frontend.** Die Go-Seite (`internal/handler/`) proxyt die Cockpit-Farbe nur durch (kein
eigenes `stage_weather.go`, s. Vorgänger-Spec); das Frontend kennt bereits genau
`'green'|'yellow'|'red'|null` (`frontend/src/lib/types.ts:543`) und braucht keine Änderung,
weil diese Scheibe bewusst KEINEN vierten Wert einführt, sondern „leicht" die bestehende
Gelb-Farbe teilen lässt.

## Estimated Scope

- **LoC:** ~45-55 Quellcode + ~150-180 Tests ≈ 200-235 gesamt — **nah am 250-LoC-
  Workflow-Limit.** Reißt es beim Implementieren, entscheidet der PO über
  `workflow.py set-field loc_limit_override 500`; keine Selbst-Anhebung.
- **Files:** 5 geändert (0 neu im Produktivcode), 1 Testdatei geändert + 2 neue Testdateien
- **Effort:** medium — kleine, aber an mehreren Stellen verteilte Änderungen; die
  eigentliche fachliche Schwierigkeit liegt im sauberen Umgang mit den zwei in den Fallen
  beschriebenen Fehlerquellen (toter Parameter, LOW-als-Default-Kollision), nicht im
  Umfang.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` | Vorgänger-Scheibe | führt `ThunderLevel.LOW` ein und hält beide hier behandelten Punkte als „bewusst offen" fest (Abschnitt 4 „nicht derselbe Fall", Known Limitations) |
| `docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md` | bindende Abgrenzung | die Erwähnungsschwelle dieser Scheibe ist NICHT die dort geregelte Alarm-Empfindlichkeit — zwei verschiedene Achsen, nicht vermischen |
| `src/output/tokens/builder.py:84-120` (`DEFAULTS`, `_mk_metric`) | Bestehendes Muster | Vorrang `spec.threshold ?? DEFAULTS[symbol]`; unverändert, liefert weiter die SMS-/Telegram-Schwelle |
| `src/output/renderers/email/outlook.py:402-411`, `src/services/trip_report_scheduler.py:1433-1443` | Bereits vorhandene Verdrahtung | übersetzen `dc.metrics[].sms_threshold` bereits generisch (nicht thunder-spezifisch) in `row["sms_threshold_thunder"]` — der Trend-Block muss das nur noch LESEN, keine neue Verdrahtung nötig |
| `src/app/models.py:570` (`MetricConfig.sms_threshold`) | Quelle | bereits vorhanden, bereits UI-editierbar (`WeatherMetricsTab.svelte:202,1282-1292`, `thunder` ist in `SMS_THRESHOLD_METRIC_IDS`) — kein Datenmodell-/Frontend-Feld fehlt |
| `src/services/risk_engine.py:113-135` (`get_max_risk_level`, `_check_thunder`) | Ursache der Falle 2 | `get_max_risk_level()` liefert bei leerer Risikoliste ebenfalls `RiskLevel.LOW` — diese Doppeldeutigkeit ist der eigentliche Gegenstand von Hälfte B |

## Implementation Details

### Hälfte A.1 — `_sms_mention_threshold()` wird trip-bewusst (die EINE Stelle, an der `metric_id` in `sms_threshold` übersetzt wird)

```python
def _sms_mention_threshold(
    metric_id: str, configured: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """... (Docstring ergänzt um `configured`-Parameter) ..."""
    if configured is not None and configured.get(metric_id) is not None:
        return configured[metric_id]
    from output.tokens.builder import DEFAULTS
    _id_to_sms_symbol = {
        "wind": "W", "gust": "G", "precipitation": "R",
        "rain_probability": "PR", "thunder": "TH:",
    }
    sym = _id_to_sms_symbol.get(metric_id)
    if sym is not None:
        return DEFAULTS.get(sym)
    if metric_id == "visibility":
        return 2.0
    if metric_id == "humidity":
        return 90.0
    return None
```

`configured` ist bewusst in `metric_id`-Raum gehalten (nicht SMS-Symbol) — die drei
Aufrufer (`html.py`/`plain.py`/`compact.py`) haben bereits `dc.metrics` in genau diesem
Raum, brauchen also KEINE eigene Übersetzung. Nur diese Funktion übersetzt intern auf das
SMS-Symbol für den `DEFAULTS`-Fallback — exakt EINE Übersetzungsstelle (Falle 1, zweiter
Teil). Nur der `"thunder"`-Aufruf bekommt künftig `configured` mitgegeben; Wind/Böen/Regen/
Regen-W. bleiben unverändert (rufen ohne zweites Argument, bit-identisch — s. Known
Limitations).

### Hälfte A.2 — toter Parameter ersatzlos entfernt, neuer klar benannter Parameter daneben

`_pill_for_metric()` und `build_metrics_summary_pills()` verlieren den seit #795 toten
Parameter `thresholds: dict` (aktuell mit `mc.alert_threshold` — einer ANDEREN Achse,
ADR-0043 — gefüllt und nie gelesen) und bekommen stattdessen
`sms_mention_thresholds: dict[str, float]` (Vorbelegung `{}`), gefüllt aus
`mc.sms_threshold`. Die drei Aufrufer ändern sich identisch, z. B. `html.py:1364-1369`:

```python
# vorher (tot, ADR-0043-fremde Achse):
_pill_thresholds = {
    mc.metric_id: mc.alert_threshold
    for mc in dc.metrics if mc.alert_enabled and mc.alert_threshold is not None
}
# nachher (Erwaehnungsschwelle, dieselbe Achse wie SMS):
_sms_mention_thresholds = {
    mc.metric_id: mc.sms_threshold
    for mc in dc.metrics if mc.sms_threshold is not None
}
```

Analog in `plain.py:154-158` und `compact.py:168-172`. Die neue Variable wird an derselben
Position an `build_metrics_summary_pills()` übergeben wie zuvor `_pill_thresholds`.

### Hälfte A.3 — Prosa-Satz nutzt die konfigurierte Schwelle statt eines an `MED` gebundenen Literals

`_pill_for_metric()`, Zweig `metric_id == "thunder"` (aktuell Zeilen 1554-1580): der
Vergleich `thunder_ordinal(lvl) >= thunder_ordinal(ThunderLevel.MED)` wird ersetzt durch
`thunder_ordinal(lvl) >= _mention_thr`, wobei
`_mention_thr = _sms_mention_threshold("thunder", sms_mention_thresholds)`. Ohne
Trip-Einstellung liefert das `DEFAULTS["TH:"] = 1.0` — die Stufe „leicht" (Ordinal 1) löst
den Satz künftig aus, wo sie es vorher nicht tat (PO-Entscheidung 2026-08-03, s. AC-5/AC-8).

### Hälfte A.4 — Trend-Block liest die längst vorhandene, aber bisher ignorierte Verdrahtung

`format_trend_tokens()` (`helpers.py:838-867`): analog zu `sms_threshold_precip`/`_wind`/
`_gust` (Zeilen 848-850) wird `thunder_thr = stage.get("sms_threshold_thunder", 1.0)`
gelesen und als `threshold=thunder_thr` (statt fest `1.0`) an `render_threshold_peak_value`
für `"TH"` übergeben. Der Schlüssel `sms_threshold_thunder` existiert im `stage`-Dict
bereits produktiv (`outlook.py:409`, `trip_report_scheduler.py:1433-1443`) — diese Hälfte
braucht **keine neue Verdrahtung**, nur das fehlende `.get(...)`.

### Hälfte B — Cockpit unterscheidet „kein Risiko vorhanden" von „Risiko der Stufe leicht"

`_compute_one_stage()` (`stage_weather.py:97-117`): statt nur der Höchststufe wird
zusätzlich erfasst, ob IRGENDEIN Segment ein nicht-leeres `RiskAssessment.risks` hatte:

```python
engine = RiskEngine()
max_level = RiskLevel.LOW
has_any_risk = False
for sw in ok:
    assessment = engine.assess_segment(sw, exposed)
    if assessment.risks:
        has_any_risk = True
    level = engine.get_max_risk_level(assessment)
    if _LEVEL_ORDER[level] > _LEVEL_ORDER[max_level]:
        max_level = level
...
if max_level == RiskLevel.HIGH:
    risk_color = "red"
elif max_level == RiskLevel.MODERATE or has_any_risk:
    risk_color = "yellow"
else:
    risk_color = "green"
```

`has_any_risk` unterscheidet „keine Segmente hatten Risiken" (weiterhin grün) von
„mindestens ein Segment hatte ein Risiko der Stufe LOW" (jetzt gelb) — genau die
Unterscheidung, die `get_max_risk_level()`s eigener `LOW`-Fallback (`risk_engine.py:116`)
sonst verdeckt (Falle 2). Bewusst NICHT thunder-spezifisch formuliert — falls künftig eine
andere Regel ebenfalls `RiskLevel.LOW` erzeugt, greift dieselbe Logik ohne Anpassung (s.
Known Limitations zur heutigen Alleinstellung von Gewitter).

## Expected Behavior

- **Input:** Trip mit/ohne konfigurierter `MetricConfig.sms_threshold` für `"thunder"`
  (Standard: keine Einstellung); Etappen-Wetterdaten mit `ThunderLevel` je Stunde.
- **Output:** E-Mail (Prosa-Satz + Trend-Block), SMS/Telegram (`TH:`-Kürzel) und
  Cockpit-Farbe (`green`/`yellow`/`red`) spiegeln dieselbe, konfigurierbare
  Erwähnungsschwelle für „ab wann wird Gewitter erwähnt" wider — mit Ausnahme des
  Cockpits, das keine Schwelle kennt, sondern binär „Risiko vorhanden ja/nein" je Stufe.
- **Side effects:** keine neuen Persistenz-Felder, keine API-Vertragsänderung — die
  Cockpit-Antwortstruktur (`risk: string`) bleibt exakt dieselben drei Werte plus `null`.

## Acceptance Criteria

**Regressions-ACs (PFLICHT, aus dem Kontext-Dokument)**

- **AC-1 (SMS/Telegram bleiben am Standard-Trip bit-identisch):** Given ein Trip OHNE eigene
  Gewitter-Schwellen-Einstellung / When das SMS-Kürzel `TH:` und die Telegram-Fußzeile für
  eine Etappe mit gemischten Gewitterstufen gerendert werden / Then ist der erzeugte Text
  exakt derselbe wie vor dieser Änderung.
  - Test: bestehende SMS-/Telegram-Gewitter-Tests (`tests/tdd/test_sms_daywindow_aggregation.py`,
    `tests/tdd/test_daywindow_configurable.py`) laufen ohne Codeänderung an diesen Dateien
    unverändert grün.

- **AC-2 (Cockpit: eine risikofreie Etappe bleibt grün):** Given eine Etappe ohne jedes
  erkannte Risiko (kein Gewitter, kein Wind-/Regen-/Sicht-Risiko) / When die
  Cockpit-Etappenfarbe berechnet wird / Then bleibt sie „grün" — unverändert.
  - Test: der bestehende `tests/tdd/test_stage_weather_parity.py::
    test_ac4_wind_exposition_escalates_vs_non_exposed` (erwartet `"green"` für das
    nicht-exponierte Segment, Zeile 223) bleibt OHNE Anpassung grün. Gegenprobe: wird er
    rot, ist die Umsetzung falsch, nicht der Test (CLAUDE.md-Vorgabe).

**Hälfte B — Cockpit**

- **AC-3 (Cockpit zeigt „leicht" künftig als Gelb):** Given eine Etappe, deren einziges
  erkanntes Risiko ein leichtes Gewitter ist (`ThunderLevel.LOW`, sonst keine Risiken) /
  When die Cockpit-Etappenfarbe berechnet wird / Then zeigt sie „gelb" — nicht mehr „grün"
  wie vor dieser Änderung, aber auch keine neue, vierte Farbe.
  - Test: Fixture mit ausschließlich `ThunderLevel.LOW` über `compute_stage_weather()`
    geschleust, `results[stage_id]["risk"] == "yellow"` geprüft. Gegenprobe: bleibt
    `_RISK_TO_COLOR` ohne die „hat überhaupt ein Risiko vorgelegen"-Unterscheidung
    (`has_any_risk`), liefert dieselbe Fixture fälschlich `"green"` — der Test muss das
    fangen.

- **AC-4 (Cockpit: „mittel"/„hoch" bleiben unverändert gelb/rot):** Given Etappen mit
  mittlerem bzw. hohem Gewitter-Risiko / When die Cockpit-Etappenfarbe berechnet wird /
  Then bleiben sie „gelb" bzw. „rot" — unverändert gegenüber vor dieser Änderung.
  - Test: zwei Fixtures (`ThunderLevel.MED`, `ThunderLevel.HIGH`) über
    `compute_stage_weather()`, Ergebnisse `"yellow"` bzw. `"red"` geprüft.

**Hälfte A — Mail/SMS-Konsistenz**

- **AC-5 (Prosa-Satz meldet am Standard-Trip künftig schon ab „leicht"):** Given ein Trip
  OHNE eigene Gewitter-Schwellen-Einstellung, dessen Stundenreihe für eine Etappe NUR
  „leicht" (nie „mittel"/„hoch") erreicht / When die Mail-Pille „Gewitter" gerendert wird /
  Then erscheint der Satz „Gewitter ab HH:00 · stärkste HH:00" — anders als vor dieser
  Änderung, wo er bei reinem „leicht" stumm blieb.
  - Test: `_pill_for_metric("thunder", {}, dps_nur_low, tz=TZ)` liefert einen Text MIT
    „Gewitter ab". Ersetzt die alte Erwartung in
    `test_ac3_nur_leicht_loest_den_uhrzeit_satz_nicht_aus` (s. Abschnitt „Betroffene
    Bestands-Tests").

- **AC-6 (Erwähnungsschwelle ist pro Trip einstellbar UND wirkt gleichzeitig auf Prosa-Satz
  UND Trend-Block):** Given ein Trip, dessen Gewitter-Erwähnungsschwelle explizit auf den
  Ordinalwert von „mittel" (2.0) gestellt ist — dieselbe Einstellung
  (`MetricConfig.sms_threshold`), die heute schon das SMS-Kürzel steuert — UND eine Etappe,
  deren Stundenreihe nur „leicht" erreicht / When sowohl die Mail-Prosa-Pille als auch der
  Mail-Trend-Block für dieselbe Etappe gerendert werden / Then bleibt der Uhrzeit-Satz in
  der Pille stumm UND der Trend-Block zeigt keinen Gewitter-Auslöser über die eingestellte
  Schwelle hinaus — beide Ausgaben respektieren dieselbe eingestellte Schwelle, nicht nur
  eine davon.
  - Test: eine Fixture mit `sms_mention_thresholds={"thunder": 2.0}` durch
    `_pill_for_metric` UND eine Fixture mit `stage["sms_threshold_thunder"] = 2.0` durch
    `format_trend_tokens` geschleust; beide Ausgaben auf „kein Auslösen bei reinem leicht"
    geprüft.

- **AC-7 (Trend-Block war bisher NICHT konfigurierbar — jetzt schon):** Given ein Trip,
  dessen Gewitter-Erwähnungsschwelle einmal auf den Ordinalwert von „leicht" (1.0, Standard)
  und einmal auf „mittel" (2.0) gestellt ist / When der Mail-Trend-Block für dieselbe
  Etappe mit gemischten Stufen gerendert wird / Then unterscheidet sich die im Text
  gezeigte „ab HH:00"-Uhrzeit zwischen beiden Einstellungen — vor dieser Änderung hatte die
  Trip-Einstellung dort KEINE Wirkung (der Wert war fest auf `1.0` verdrahtet).
  - Test: zwei Aufrufe von `format_trend_tokens()` mit identischer Stundenreihe, aber
    unterschiedlichem `sms_threshold_thunder`, liefern unterschiedliche `thunder_token`-
    Werte. Gegenprobe: bleibt der Literal `threshold=1.0` unverändert fest verdrahtet, sind
    beide Ergebnisse identisch — der Test muss das fangen.

## Betroffene Bestands-Tests

| Datei | Test | Auswirkung dieser Scheibe |
|---|---|---|
| `tests/tdd/test_thunder_mail_prosa_low_binding.py:50` | `test_ac3_nur_leicht_loest_den_uhrzeit_satz_nicht_aus` | 🔴 **wird bewusst rot, dann umgeschrieben.** Der Test schrieb die alte Produktentscheidung fest (Prosa-Satz bindet an `MED`). Der PO hat diese Entscheidung am 2026-08-03 geändert — der Test wird auf die neue Erwartung „leicht löst den Satz JETZT aus (Standard-Trip)" umgeschrieben, nicht gelöscht oder übersprungen. |
| `tests/tdd/test_thunder_mail_prosa_low_binding.py:65` | `test_ac3_mittel_loest_den_uhrzeit_satz_aus` | bleibt grün — „mittel" löst weiterhin aus (`thunder_ordinal(MED)=2 >= 1.0`-Standardschwelle war immer wahr, bleibt wahr). |
| `tests/tdd/test_stage_weather_parity.py:197` | `test_ac4_wind_exposition_escalates_vs_non_exposed` | **muss grün bleiben** (Zeile 223 erwartet `"green"` für ein risikofreies Segment) — Wächter gegen Falle 2, s. AC-2. |
| 13 Dateien mit `_pill_for_metric(...)`/`build_metrics_summary_pills(...)`-Aufrufen (u. a. `test_issue_664_metrics_summary.py`, `test_issue_912_pill_textformat.py`, `test_renderer_katalog_schwellen.py`) | diverse | bleiben unverändert grün — sie übergeben den (bisher toten, künftig umbenannten) zweiten Positionsparameter durchweg als `{}` oder mit Werten für Metriken außer `"thunder"`, die weiterhin ignoriert werden (bit-identisches Verhalten, da nur der `"thunder"`-Zweig den neuen Parameter liest). |

## Known Limitations

- **Wind/Böen/Regen/Regen-W.-Mail-Pillen bleiben NICHT trip-konfigurierbar.** Nur Gewitter
  wird in dieser Scheibe an `sms_mention_thresholds` angebunden — die vier anderen
  Klasse-1-Metriken lesen weiterhin ausschließlich `DEFAULTS` (vorbestehende Lücke, nicht
  Gegenstand dieser Scheibe).
- **Ortsvergleich (Compare) bekommt die konfigurierte Schwelle nicht.**
  `compare_html.py:1052` ruft `build_outlook_row()` ohne `sms_thresholds=` auf; Compare
  bleibt beim Trend-Block-Standard `1.0` („ab leicht") — keine Regression (unverändert zum
  bisherigen Verhalten), aber auch keine neue Konsistenz zum Trip-Pfad. Eine Angleichung
  wäre eine eigene Folge-Scheibe.
- **Das Cockpit unterscheidet weiterhin NICHT zwischen „leicht" und „mittel"** (beide
  Gelb) — wer die genaue Stufe sehen will, braucht das Trip-Detail (Stundenzeile). Eine
  eigene vierte Cockpit-Farbe ist eine Design-Entscheidung außerhalb dieser Scheibe (PO
  hat sich am 2026-08-03 ausdrücklich GEGEN eine vierte Farbe entschieden).
- **„Leicht" bleibt die einzige real erzeugte `RiskLevel.LOW`-Instanz im System.** Die neue
  `has_any_risk`-Unterscheidung in `stage_weather.py` ist allgemein implementiert (nicht
  gewitter-spezifisch), wirkt aber faktisch nur für Gewitter, solange keine andere
  RiskEngine-Regel `RiskLevel.LOW` erzeugt.
- **Renderer-Commit-Tor #811 ist Pflicht:** sobald `email/helpers.py` angefasst wird, müssen
  vor dem Commit `tests/tdd/test_issue_811_mode_matrix.py` grün UND ein frischer
  `briefing_mail_validator.py`-Lauf vorliegen (Marker-Header
  `X-GZ-Mail-Type: trip-briefing`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe bleibt innerhalb ADR-0043 (Erwähnungsschwelle ist
  ausdrücklich NICHT die dort geregelte Alarm-Empfindlichkeit — zwei getrennte Achsen,
  hier nur die Erwähnungsschwelle betroffen) und innerhalb ADR-0025 (Sortier-/Render-Skala
  unverändert). Die Entfernung des toten `thresholds`-Parameters und seine Ersetzung durch
  einen klar benannten `sms_mention_thresholds`-Parameter ist eine additive Aufräumarbeit
  an einer bestehenden Funktionssignatur, keine neue Architektur-Entscheidungsfläche. Die
  Cockpit-Farblogik bleibt eine reine Python-Wahrheit (unverändert ggü. der
  Vorgänger-Spec), die Go-Seite bleibt unverändert reiner Proxy.

## Changelog

- 2026-08-03: Initial spec created (Issue #1474, Folge-Scheibe zu S3).
