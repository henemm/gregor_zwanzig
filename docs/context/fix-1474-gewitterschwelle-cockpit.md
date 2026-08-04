# Context: fix-1474-gewitterschwelle-cockpit

## Request Summary

Folge-Scheibe zu #1474 (vierte Gewitterstufe „leicht", live seit `9e97bb4b`). Zwei
Punkte, die dort bewusst offen blieben: (1) Das Cockpit färbt „leicht" heute wie
„kein Risiko" grün — PO-Entscheidung 2026-08-03: **gelb, wie „mittel"**. (2) Der
Prosa-Satz „Gewitter ab HH:00" in der Mail ist fest an `ThunderLevel.MED` gebunden,
während das SMS-Kürzel `TH:` schon ab „leicht" meldet — dieselbe Mail sagt zwei
verschiedene Dinge.

## Ausgangsbefund (gemessen, nicht vermutet)

### Wie „ab welcher Stufe wird gemeldet" heute an drei Stellen beantwortet wird

| Stelle | Quelle der Schwelle | Wirkung heute |
|---|---|---|
| SMS-/Telegram-Kürzel `TH:` | `spec.threshold` aus `MetricConfig.sms_threshold`, sonst `DEFAULTS["TH:"] = 1.0` (`tokens/builder.py:84,119-120`) | **pro Trip einstellbar**, Standard „ab leicht" |
| Mail-Trend-Block | `threshold=1.0` **fest verdrahtet** (`email/helpers.py:865`) | „ab leicht", aber **nicht** einstellbar |
| Mail-Prosa-Pille „Gewitter ab HH:00" | Vergleich fest gegen `ThunderLevel.MED` (`email/helpers.py:1567`) | „ab mittel", **nicht** einstellbar |

🔴 **Korrektur einer früheren Annahme:** Der Trend-Block folgt **nicht** der
eingestellten Schwelle — er ist auf `1.0` festgenagelt und stimmt nur zufällig mit
dem Standardwert überein. Nur das SMS-Kürzel ist wirklich konfigurierbar.

### 🔴 Falle 1 — der `thresholds`-Parameter ist tot

`_pill_for_metric(metric_id, thresholds, all_dps, ...)` (`email/helpers.py:1361`)
liest `thresholds` **kein einziges Mal** im Rumpf (Zeilen 1361-1630). Die eigene
Docstring sagt es: *„unbenutzt seit #795 … bleibt im Signatur-Vertrag für
Rückwärtskompatibilität"* (`helpers.py:1642-1644`). Die drei Aufrufer
(`html.py:1365-1369`, `plain.py:168-172`, `compact.py:154-158`) füllen dort
`mc.alert_threshold` ein — also **Alarm**-Schwellen, nicht Erwähnungs-Schwellen.
Tests übergeben `{}` (`test_thunder_mail_prosa_low_binding.py:58`).

⇒ Es gibt **keinen** fertigen Weg, über den eine pro-Trip konfigurierte
Erwähnungs-Schwelle den Prosa-Satz erreicht. Sie muss neu durchgereicht werden.
Der tote Parameter ist der naheliegende Andockpunkt — **aber Achtung auf den
Schlüsselraum:** `_pill_for_metric` denkt in `metric_id` (`"thunder"`),
`trip_report.py:264` in SMS-Symbolen (`"TH:"`).

### 🔴 Falle 2 — `RiskLevel.LOW` ist der Default für „gar kein Risiko"

Die naheliegende Ein-Zeilen-Änderung `_RISK_TO_COLOR[RiskLevel.LOW] = "yellow"`
(`stage_weather.py:32`) wäre **falsch**: Sie färbt jede risikofreie Etappe gelb.

- `risk_engine.py:113-116` — `get_max_risk_level()` liefert bei **leerer**
  Risikoliste ebenfalls `RiskLevel.LOW`.
- `stage_weather.py:98-102` — `max_level` startet auf `RiskLevel.LOW` und steigert nur.

⇒ „keine Risiken" und „Gewitter leicht" (`risk_engine.py:132-135`, seit #1474) sind
auf Etappen-Ebene **nicht unterscheidbar**. Die Farbgebung braucht ein zusätzliches
Merkmal — z. B. „liegt überhaupt ein Risiko-Eintrag vor?" statt nur die Höchststufe.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/helpers.py:1554-1578` | Prosa-Satz, feste MED-Bindung (Zeile 1567) |
| `src/output/renderers/email/helpers.py:1361,1638-1644` | `_pill_for_metric` + toter `thresholds`-Parameter |
| `src/output/renderers/email/helpers.py:865` | Trend-Block, `threshold=1.0` fest |
| `src/output/renderers/email/{html,plain,compact}.py` | die drei Aufrufer, füllen `alert_threshold` ein |
| `src/output/renderers/trip_report.py:263-267` | einziger Ort, der `sms_threshold` einsammelt (Schlüssel = SMS-Symbol) |
| `src/output/tokens/builder.py:84,119-120` | `DEFAULTS` + Vorrang `spec.threshold` |
| `src/services/stage_weather.py:31-32,98-102,117` | Cockpit-Farbe + die LOW-Default-Falle |
| `src/services/risk_engine.py:113-116,132-135` | `get_max_risk_level`, Gewitter-Regel mit LOW |
| `api/routers/internal.py:24,77,84` | Endpunkt, der die Farbe ausliefert |
| `internal/handler/proxy.go:197-201` | Go ist reiner Durchreicher, kennt die Farbwerte nicht |
| `frontend/src/lib/types.ts:543`, `utils/stageRisk.ts:10,20-22` | Frontend kennt genau `'green'|'yellow'|'red'|null` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:202` | Gewitter ist als einstellbare Schwelle in der Oberfläche |

## Existing Patterns

- **Erwähnungsschwelle aus EINER Quelle** — `_sms_mention_threshold()`
  (`helpers.py:1141-1161`) ist der etablierte Weg, damit Mail und SMS dieselbe
  Schwelle benutzen. Der Regen-Zweig nutzt ihn, der Gewitter-Zweig nicht.
  Er liest allerdings nur `DEFAULTS`, keine Trip-Konfiguration.
- **Vorrang-Muster** `spec.threshold ?? DEFAULTS[symbol]` (`builder.py:119-120`) —
  Trip-Einstellung schlägt Standardwert.
- **Cockpit-Farbe ist Python-Wahrheit**, Go proxyt nur; das Frontend erwartet drei
  Werte plus `null` (Typ-Union, keine Laufzeitprüfung — ein vierter Wert fiele still
  in den grün/`null`-Zweig).

## Dependencies

- **Upstream:** `MetricConfig.sms_threshold` (`models.py:570`, #624),
  `loader.py:170-172,789,825,858` (Persistenz), `ThunderLevel`/`thunder_ordinal`
  (`metric_format.py`), `RiskLevel`/`RiskEngine`.
- **Downstream:** alle drei Mail-Formate (`html`/`plain`/`compact`), Cockpit-Startseite,
  Trip-Detail-Zeilen (`TripStageRow.svelte`, `StageDetailRow.svelte`).

## Existing Specs

- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` — Vorgänger; Abschnitt 2
  und „Known Limitations" halten **beide** Punkte ausdrücklich als bewusst offen fest
  (MED-Bindung als Produktentscheidung, Cockpit-Farbe als Designentscheidung).
- `docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md` —
  Alarm-Empfindlichkeit ist eine **andere** Achse als die Erwähnungsschwelle; nicht vermischen.

## Betroffene Bestands-Tests

| Datei | Test | Erwartung |
|---|---|---|
| `tests/tdd/test_thunder_mail_prosa_low_binding.py:50` | `test_ac3_nur_leicht_loest_den_uhrzeit_satz_nicht_aus` | **schreibt die MED-Bindung fest** — wird bei Senkung auf „leicht" rot |
| `tests/tdd/test_thunder_mail_prosa_low_binding.py:65` | `test_ac3_mittel_loest_den_uhrzeit_satz_aus` | bleibt grün |
| `tests/tdd/test_stage_weather_parity.py:197` | `test_ac4_wind_exposition_escalates_vs_non_exposed` | erwartet `"green"` für ein Segment **ohne** Risiken (Zeile 223) — wird bei naivem `LOW: "yellow"` rot |
| `tests/tdd/test_sms_daywindow_aggregation.py` | 7 Tests (345/376/505/542/562/585/631) | assertieren „Gewitter ab HH:00 · stärkste HH:00" im Klartext |
| `tests/tdd/test_daywindow_configurable.py:328` | `test_event_at_inclusive_window_end_...` | dito |
| `frontend/.../stageRisk.test.ts:25,29,33,37-38` | drei distinkte Töne | bleibt unberührt, solange kein vierter Farbwert entsteht |

## Risks & Considerations

1. 🔴 **Cockpit:** `RiskLevel.LOW` == „kein Risiko" — ohne zusätzliches Merkmal färbt
   die Änderung alles gelb. Das ist der eigentliche Kern dieser Hälfte, nicht die
   Farbzuordnung.
2. 🔴 **Prosa-Satz:** Der Weg für eine konfigurierte Schwelle existiert nicht und muss
   gebaut werden. Zwei Schlüsselräume (`metric_id` vs. SMS-Symbol) treffen aufeinander.
3. **Renderer-Commit-Tor #811** greift, sobald `email/helpers.py` angefasst wird:
   Mode-Matrix-Test grün **und** frischer `briefing_mail_validator`-Lauf sind Pflicht
   vor dem Commit.
4. **Ein Bestands-Test schreibt die alte Produktentscheidung ausdrücklich fest**
   (`test_thunder_mail_prosa_low_binding.py`). Er wird angepasst, nicht umgangen —
   die Entscheidung dahinter hat der PO am 2026-08-03 geändert.
5. **Kein vierter Farbwert** ins Frontend einführen (Typ-Union, stiller Rückfall auf grün).
6. Der Trend-Block (`helpers.py:865`) ist die dritte Kopie derselben Frage. Wird er
   nicht mitgezogen, bleibt eine vierte Sonderregel stehen — Aufnahme in den Scope
   ist zu entscheiden.
