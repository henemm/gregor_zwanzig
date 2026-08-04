# Context + Analyse: Fix #1482 — `TH+:` ignoriert Metrik-Auswahl und Datenlücke

## Request Summary

Zwei Mängel am selben Kürzel `TH+:` (Gewitter der Folge-Etappe) in der SMS/Kurznachricht:
1. Wird die Metrik „Gewitter" im Trip abgewählt, verschwindet `TH:` korrekt, `TH+:` bleibt stehen.
2. Bei einer Datenlücke im Vorhersage-Fenster der Folge-Etappe kann `TH+:` strukturell nie `?`
   werden — es zeigt `-` (Fehl-Entwarnung, sicherheitsrelevant).

Soll: `TH+:` verhält sich exakt wie `TH:` (Grundregel PO-Entscheidung 2026-08-03, #1415).

## Related Files

| File | Relevanz |
|------|----------|
| `src/output/tokens/builder.py:16-17,111-133,277-295` | `FORECAST_THP`-Konstante; `_mk_metric()` (Gap→`?`-Logik nur hier); Aufrufstelle für `TH:` (mit `has_gap`) vs. `TH+:` (ohne `has_gap`, ohne Bindungssuche) |
| `src/output/renderers/sms_trip.py:74-112,395-437` | `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` (Metrik→Kürzel-Bindung); `format_sms()` baut `tomorrow_day = DailyForecast(thunder_hourly=tomorrow_thunder)` **ohne** `has_data_gap` |
| `src/output/renderers/trip_report.py:259-304` | `_disabled_sms_specs` — hier werden abgewählte Metriken in `MetricSpec(enabled=False)` übersetzt; `TH+:` fehlt in beiden Bindungstabellen |
| `src/output/tokens/dto.py:45` | `DailyForecast.has_data_gap: bool = False` |
| `src/services/notification_service.py:207-240` | `compute_has_gap()` — EINZIGER Berechnungspunkt für die Ziel-Datenlücke, arbeitet ausschließlich auf den `segment_weather`/`night_weather` der **berichteten** Etappe (`target_date`), nicht auf die Folge-Etappe |
| `src/services/trip_report_scheduler.py:1469-1583` | `_build_thunder_forecast_from_trend_or_fetch()` — baut `thunder_forecast["+1"/"+2"]` aus `multi_day_trend` (bevorzugt) oder Fallback-Einzelfetch; **kein Gap-Signal im Rückgabewert** |
| `docs/reference/sms_format.md` §2 „Bekannte Ist-Abweichungen" | Dokumentiert beide Mängel als IST, nicht SOLL — muss nach Fix aktualisiert werden |
| `tests/tdd/test_bug_874_th_plus_sms.py` | Bestehende AC-1..AC-4 für `TH+:` — AC-3/AC-4 legen fest: kein `thunder_forecast` bzw. `level=NONE` ⇒ `TH+:-` (**Spec-Pflicht**, das Token darf nie ganz fehlen) |
| `tests/unit/test_token_builder.py:174` | Positions-Reihenfolge-Test, listet `TH+:` |

## Bestätigter Befund (Mangel 1 — Metrik-Bindung)

`builder.py:291`: `spec = by_sym.get(FORECAST_THP) or by_sym.get("TH+")` — sucht einen Eintrag
für `"TH+:"`/`"TH+"` in `by_sym`. Weder `SMS_SYMBOL_BY_METRIC` noch `SMS_MULTI_SYMBOLS_BY_METRIC`
in `sms_trip.py` enthalten einen solchen Eintrag (nur `"TH:"` über `_SMS_SYMBOL_GRAMMAR["thunder"]`).
`_disabled_sms_specs` in `trip_report.py` kann also nie eine `MetricSpec(symbol="TH+:", enabled=False)`
erzeugen ⇒ `spec` ist immer `None` ⇒ `_visible(None, rt)` ist immer `True` (Default-Verhalten
für „keine Spec übergeben", siehe `N`/`FN` bei Direktaufrufen) ⇒ Abwahl wirkt nie.

**Fix (klar, gering riskant):** `"thunder"` in `SMS_MULTI_SYMBOLS_BY_METRIC` aufnehmen (analog zu
`"temperature": ("N","K","D")`) mit den zwei Kürzeln `("TH:", "TH+:")` — dann entsteht über den
bestehenden Mechanismus in `trip_report.py:285-289` automatisch eine `MetricSpec(symbol="TH+:",
enabled=...)`, gleichgeschaltet mit `TH:`. **Wichtig:** `"thunder"` ist heute NICHT in
`SMS_SYMBOL_BY_METRIC` (1:1-Tabelle), weil `_SMS_SYMBOL_GRAMMAR` es dort schon als Sonderfall führt
(Kommentar `sms_trip.py:75-77`: „Ausdrücklich NICHT durch #1435 E3b aufgehoben"). Ein zusätzlicher
Eintrag in `SMS_MULTI_SYMBOLS_BY_METRIC` widerspricht dem nicht — die beiden Tabellen dienen
unterschiedlichen Zwecken (1:1 inkl. Schwellwert-Lookup vs. reine enabled/disabled-Bindung ohne
Schwellwert-Semantik, siehe Kommentar `sms_trip.py:91-108`).

Nebeneffekt (vom PO im Issue erwartet): der Gewitter-Schwellwert (#624) wirkt danach automatisch
auch auf `TH+:` — **nicht**, weil `SMS_MULTI_SYMBOLS_BY_METRIC` Schwellwerte transportiert (tut es
laut Kommentar ausdrücklich nicht), sondern weil `TH+:` schon heute in `builder.py:290-295`
denselben `DEFAULTS`-Fallback nutzt wie `TH:` — zu verifizieren, ob ein im Editor gesetzter
Schwellwert für „Gewitter" überhaupt getrennt für `TH+:` ankommt, oder ob beide always denselben
Wert teilen (aktuell: `by_sym.get(FORECAST_THP)` fände nie einen Threshold-Eintrag, weil kein
Eintrag existiert — nach dem Fix über `SMS_MULTI_SYMBOLS_BY_METRIC` weiterhin **kein** Threshold,
nur enabled/disabled). Diese Frage braucht Klärung in der Spec-Phase.

## Bestätigter Befund (Mangel 2 — Datenlücke) — GRÖSSER als die Issue-Beschreibung nahelegt

Das Issue beschreibt es als reines Weiterreichen: „`has_gap` wird nur an einer Stelle
durchgereicht ... der Parameter fällt auf `False` zurück". Das trifft die Wirkung, aber nicht die
Ursache vollständig. Recherche zeigt:

- `compute_has_gap()` (`notification_service.py:207`) — der EINZIGE Ort, der eine Datenlücke
  überhaupt berechnet — arbeitet ausschließlich mit `request.segment_weather`/`night_weather` der
  **berichteten** Etappe. Für die Folge-Etappe (`+1`) gibt es **keinen** äquivalenten Aufruf.
- `tomorrow_day = DailyForecast(thunder_hourly=tomorrow_thunder)` (`sms_trip.py:434`) wird ohne
  `has_data_gap` konstruiert — der Parameter existiert im DTO (Default `False`), aber es gibt
  aktuell **keinen Aufrufer, der ihn setzt**. Selbst wenn `builder.py:292` `has_gap=tomorrow.has_data_gap`
  ergänzt, bleibt der Wert strukturell `False`, solange `sms_trip.py` ihn nie befüllt.
- Ein enger, aber genau prüfbarer Fall existiert bereits im Code: Wenn weder der `multi_day_trend`
  noch der Fallback-Einzelfetch einen Wert für das `+1`-Datum liefern
  (`_build_thunder_forecast_from_trend_or_fetch`, `missing_dates` bleibt nach Fallback unaufgelöst),
  fehlt der Schlüssel `"+1"` im zurückgegebenen `dict` komplett. `sms_trip.py:425`
  (`if thunder_forecast and "+1" in thunder_forecast`) behandelt das identisch zu „kein
  `thunder_forecast` übergeben" ⇒ `TH+:-`. **Genau das ist die im Issue gemeinte Fehl-Entwarnung.**
- ⚠️ Eine zweite, legitime Ursache für ein fehlendes `"+1"` existiert ebenfalls: die berichtete
  Etappe ist die **letzte** Etappe des Trips (`trip.get_future_stages(target_date)` liefert leer).
  Dieser Fall ist **kein** Datenausfall, sondern korrektes Verhalten — heute rendert er ebenfalls
  `TH+:-` (laut Kommentar „Bug #874 Spec-Pflicht: TH+: immer als days[1] einbauen"), und die
  bestehenden Tests AC-3/AC-4 (`test_bug_874_th_plus_sms.py`) fixieren dieses Verhalten für
  `thunder_forecast=None`/`{}` explizit auf `TH+:-`.

**Offene Design-Frage für die Spec-Phase:** „`+1`-Schlüssel fehlt" ist heute nicht danach
unterscheidbar, *warum* er fehlt (kein nächster Tag vs. Abruf fehlgeschlagen). Eine Lösung, die
„jedes fehlende `+1`" pauschal zu `TH+:?` macht, würde für **jede letzte Etappe jedes Trips** neu
einen `?`-Marker erzeugen, wo bisher korrekt `-` stand — eine sichtbare Verhaltensänderung, die
über das Issue hinausgeht und die bestehenden AC-3/AC-4-Tests bricht. Der scheduler-seitige Code
(`_build_thunder_forecast_from_trend_or_fetch`) kennt den Unterschied bereits (`future_stages`
leer vs. `missing_dates` nach Fallback nicht aufgelöst) — dieses Wissen muss bis zum Renderer
durchgereicht werden (z. B. explizites `thunder_gap: bool` neben `thunder_forecast`, gesetzt genau
dann, wenn ein realer Folge-Tag existierte, aber keine Daten dafür beschafft werden konnten).

**Konsequenz für Scope/Track:** Mangel 2 ist kein reines Parameter-Durchreichen, sondern eine
neue Unterscheidung im Scheduler (`trip_report_scheduler.py`) plus ein neuer Parameter durch
`NotificationService`/`format_sms()`/`format_email()` bis zu `DailyForecast.has_data_gap` für den
Folgetag. Größer als ursprünglich geschätzt (~25 Zeilen), aber weiterhin lokal auf einen bekannten
Pfad begrenzt — der Standard Track (keine neue Architektur, kein neuer Kanal) bleibt angemessen;
die Spec muss die Abgrenzung „kein nächster Tag" vs. „Abruf fehlgeschlagen" explizit als
Akzeptanzkriterium führen, sonst wiederholt sich der Fehler von #1467 S2 AG6 (Spec behauptet
Wirkung, die der Code nicht trägt).

## Existing Patterns

- **Metrik→Kürzel-Bindung:** `SMS_MULTI_SYMBOLS_BY_METRIC` ist das etablierte Muster für „eine
  Wettergröße, mehrere SMS-Kürzel" (`temperature` → `N,K,D`; `wind_chill` → `FN,FK,FD,WC`,
  ergänzt durch #1450). `thunder` → `TH:,TH+:` folgt exakt demselben Muster.
- **Gap→`?`-Logik:** existiert nur in `_mk_metric()` (`builder.py:126-127`), ausgelöst durch den
  `has_gap`-Parameter. Kein Sonderfall nötig, nur der Parameter muss beim `TH+:`-Aufruf ankommen
  *und* vorher korrekt gesetzt sein.
- **Fail-soft bei Scheduler-Fetches:** `_collect_future_stage_weather` fängt Exceptions bereits
  ab (`trip_report_scheduler.py:1463` `except Exception as e: logger.warning(...); continue`) —
  ein expliziter Gap-Marker fügt sich in dieses bestehende Fail-soft-Muster ein.

## Dependencies

- Upstream: `MetricConfig`/`display_config.metrics` (Trip-Editor, Metrik „Gewitter" ein/aus),
  `multi_day_trend`/`_collect_future_stage_weather` (Datenbeschaffung Folge-Etappe).
- Downstream: `SMSTripFormatter.format_sms()` wird auch von der Telegram-Kurzform genutzt
  (`display_config.telegram_style="kurzform"`, s. Memory `reference_telegram_kurzform_ist_der_sms_pruefweg`)
  — das ist der reguläre, kostenlose Live-Prüfweg für diesen Fix.

## Existing Specs

- Keine dedizierte `docs/specs/modules/`-Spec für `TH+:` selbst; die Referenz ist
  `docs/reference/sms_format.md` (kein Modul-Spec-Template, lebendes Referenzdokument).
- `docs/specs/modules/bug_874_th_plus_sms.md` (Herkunft des `TH+:`-Tokens, AC-1..AC-4 s. o.).

## Risks & Considerations

- **Renderer-Commit-Gate (#811):** `sms_trip.py` steht auf der Gate-Liste
  (`src/output/renderers/{trip_report,sms_trip,...}.py`) — Commit blockiert ohne grünen
  `tests/tdd/test_issue_811_mode_matrix.py` + frischen `briefing_mail_validator.py`-Lauf. Der
  hier betroffene Pfad ist der SMS-Renderer, nicht das Mail-Template — trotzdem gilt das Gate,
  weil die Datei in der Liste steht.
- **Sicherheitsrelevante Richtung:** Die Fehl-Entwarnung (`TH+:-` statt `TH+:?`) ist laut Issue
  die Richtung, die zwingend einen Test an der Wirkstelle braucht (Mutations-Gegenprobe-Pflicht).
- **Bestehende Tests dürfen nicht falsch brechen:** AC-3/AC-4 in `test_bug_874_th_plus_sms.py`
  fixieren `TH+:-` für „kein nächster Tag / kein thunder_forecast" — das SOLL bleiben unverändert
  richtig; nur der Fall „nächster Tag existiert, Abruf fehlgeschlagen" soll neu `TH+:?` werden.
- **Test-Namensregel:** `test_bug_874_th_plus_sms.py` ist Bestand (nicht neu) und daher vom
  Namens-Gate ausgenommen; neue Tests für #1482 müssen nach Verhalten benannt werden, nicht nach
  Issue-Nummer (z. B. `test_th_plus_follows_thunder_metric_selection.py` o. ä. — Namen final in
  der Spec-Phase).
