---
entity_id: fix_1482_th_plus_metrik_luecke
type: bugfix
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [sms, thunder, kurznachricht, telegram-kurzform]
workflow: fix-1482-thplus-metrik-luecke
---

# Fix #1482 — `TH+:` ignoriert Metrik-Auswahl UND kann nie eine Datenlücke melden

## Approval

- [x] Approved (PO, 2026-08-04, inkl. AC-6)

## Purpose

Das SMS-/Telegram-Kurzform-Kürzel `TH+:` (Gewitter der Folge-Etappe) soll sich exakt wie sein
Geschwister-Kürzel `TH:` (Gewitter der berichteten Etappe) verhalten — Grundregel gemäß
PO-Entscheidung 2026-08-03 (#1415). Aktuell verletzt `TH+:` diese Regel in zwei Punkten: (1) es
bleibt stehen, obwohl die Metrik „Gewitter" im Trip abgewählt wurde, und (2) es zeigt bei einer
echten Datenlücke für den Folgetag fälschlich `-` (Entwarnung) statt `?` (unbekannt) — eine
sicherheitsrelevante Fehl-Entwarnung, weil eine Wanderin denkt, es sei geprüft und unauffällig,
obwohl schlicht keine Daten vorlagen.

## Source

- **File:** `src/output/tokens/builder.py`
- **Identifier:** `build_token_line()` (Aufrufstelle `TH+:`, Zeile ~290-295), `_mk_metric()`

## Estimated Scope

- **LoC:** ~40-60 (Mangel 2 braucht ein echtes Lücken-Signal von `trip_report_scheduler.py` bis
  zum SMS-Renderer, nicht nur einen Parameter-Pass)
- **Files:** 4 Code-Dateien + 1 Referenz-Doku (`docs/reference/sms_format.md`) + 1 neue Testdatei
  = 5-6
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricConfig` / `display_config.metrics` | Datenmodell | Trip-Editor: Metrik „Gewitter" ein/aus + Schwellwert (#624) |
| `SMS_MULTI_SYMBOLS_BY_METRIC` (`src/output/renderers/sms_trip.py`) | Bestehendes Muster | Metrik→Kürzel-Bindung für „eine Wettergröße, mehrere SMS-Kürzel" (Vorbild `temperature`→`N,K,D`) |
| `DailyForecast.has_data_gap` (`src/output/tokens/dto.py`) | DTO-Feld | Trägt das Gap-Signal bis zu `_mk_metric()` |
| `multi_day_trend` / `_collect_future_stage_weather` (`src/services/trip_report_scheduler.py`) | Datenbeschaffung | Liefert (oder liefert eben NICHT) die Gewitterdaten der Folge-Etappe |
| `Trip.get_future_stages()` (`src/app/trip.py:270`) | Datenmodell | Einziges Mittel, um zu unterscheiden „kein Folgetag" vs. „Folgetag existiert, Daten fehlen" |
| `SMSTripFormatter.format_sms()` | Downstream-Konsument | Wird auch von der Telegram-Kurzform genutzt (`display_config.telegram_style="kurzform"`) — regulärer, kostenloser Live-Prüfweg für diesen Fix (keine echte SMS nötig) |

## Implementation Details

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `src/output/renderers/sms_trip.py` | `SMS_MULTI_SYMBOLS_BY_METRIC["thunder"] = ("TH:", "TH+:")` ergänzen; `format_sms()` setzt `has_data_gap=True` für `tomorrow_day`, wenn `"+1"` in `thunder_forecast.get("_gap_offsets", ())` liegt |
| `src/output/tokens/builder.py` | Aufruf `_mk_metric(FORECAST_THP, ...)` bekommt zusätzlich `has_gap=tomorrow.has_data_gap` |
| `src/services/trip_report_scheduler.py` | `_build_thunder_forecast_from_trend_or_fetch()` markiert echte Lücken (Folgetag existiert laut `trip.get_future_stages()`, aber weder Trend noch Fallback-Fetch liefern Daten) unter dem neuen Schlüssel `forecast["_gap_offsets"]` |
| `src/output/renderers/trip_report.py` | NUR falls AC-6 (Schwellwert, optional) angenommen wird: `_sms_thr["TH+:"]` zusätzlich aus `m.sms_threshold` setzen, wenn `m.metric_id == "thunder"` |
| `docs/reference/sms_format.md` §2 | Abschnitt „Bekannte Ist-Abweichungen" — Punkt „Metrik-Bindung fehlt" und Punkt „nur R/PR/W/G/TH: haben `?`-Form" streichen bzw. `TH+:` als abgedeckt ergänzen; Changelog-Zeile |
| `tests/tdd/test_th_plus_follows_thunder_metric_and_gap.py` (neu) | Nach Verhalten benannt (KEIN `test_issue_1482*`/`test_1482*`, Test-Namensregel CLAUDE.md) |

### Mangel 1 — Metrik-Bindung (Fix)

`build_token_line()` (`builder.py:291`) sucht `by_sym.get(FORECAST_THP) or by_sym.get("TH+")` in
der aus `config`/`disabled_specs` gebauten `by_sym`-Map. Diese Map entsteht in
`trip_report.py:285-289` aus `SMS_MULTI_SYMBOLS_BY_METRIC` — für `"thunder"` existiert dort aktuell
KEIN Eintrag (nur `"TH:"` über die Grammatik-Ausnahme `_SMS_SYMBOL_GRAMMAR["thunder"]` in
`sms_trip.py:84`, die in die separate 1:1-Tabelle `SMS_SYMBOL_BY_METRIC` fließt). Deshalb ist
`spec` für `TH+:` immer `None`, `_visible(None, rt)` ist per Default `True` (`builder.py:88-90`) —
Abwahl der Metrik wirkt nie.

**Fix:** In `SMS_MULTI_SYMBOLS_BY_METRIC` (`sms_trip.py:109-112`) den Eintrag
`"thunder": ("TH:", "TH+:")` ergänzen. Der bestehende Mechanismus in `trip_report.py:285-289`
erzeugt dann automatisch für beide Kürzel eine gleichgeschaltete `MetricSpec(enabled=...)`. Ein
zusätzlicher Eintrag für dieselbe `metric_id` in beiden Tabellen (`SMS_SYMBOL_BY_METRIC` UND
`SMS_MULTI_SYMBOLS_BY_METRIC`) ist unproblematisch, weil beide Tabellen unterschiedliche Zwecke
verfolgen — laut Kommentar `sms_trip.py:91-108`: `SMS_SYMBOL_BY_METRIC` ist 1:1 UND wird zusätzlich
für Schwellwerte (#624) gelesen, `SMS_MULTI_SYMBOLS_BY_METRIC` transportiert bewusst KEINE
Schwellwerte, nur enabled/disabled-Bindung. Verifiziert am Code (nicht nur vermutet): beide Tabellen
werden an unterschiedlichen, unabhängigen Stellen konsumiert (`_sms_thr`-Aufbau vs.
`_disabled_sms_specs`-Aufbau, `trip_report.py:263-267` bzw. `285-289`) — keine Kollision.

### Mangel 2 — Datenlücke kann nie `?` werden (Fix)

**Zwei Ursachen für ein fehlendes `"+1"` in `thunder_forecast`, die NICHT verwechselt werden
dürfen:**

- **(a) Normalfall — kein Folgetag:** Die berichtete Etappe ist die letzte Etappe des Trips.
  `trip.get_future_stages(target_date)` liefert für diesen Offset keine Etappe. Das ist kein
  Datenausfall. Heute rendert das `TH+:-` (Kommentar `sms_trip.py:419`: „Bug #874: TH+: immer als
  days[1] einbauen — TH+:- wenn kein Gewitter (Spec-Pflicht)"). MUSS unverändert `TH+:-` bleiben.
- **(b) Echte Lücke — Folgetag existiert, Daten fehlen:** `trip.get_future_stages(target_date)`
  enthält eine Etappe an diesem Datum, aber weder `multi_day_trend`
  (`_build_thunder_forecast_from_trend_or_fetch()`, `trip_report_scheduler.py:1469-1519`) noch der
  Fallback-Einzelfetch (`_collect_future_stage_weather` + `_build_thunder_forecast`) konnten dafür
  Daten liefern. DAS ist die im Issue gemeinte Fehl-Entwarnung und MUSS neu `TH+:?` werden.

**Fix (drei Stellen):**

1. `_build_thunder_forecast_from_trend_or_fetch()` (`trip_report_scheduler.py:1469-1519`): nach dem
   bestehenden Trend+Fallback-Lauf für jeden Offset (+1/+2), dessen `key` NICHT im `forecast`-Dict
   gelandet ist, prüfen, ob `fc_date` in `{s.date for s in trip.get_future_stages(target_date)}`
   liegt. Wenn ja: echte Lücke → `key` in ein neues Set unter dem Top-Level-Schlüssel
   `forecast["_gap_offsets"]` aufnehmen (z. B. `{"+1"}`). Dieser Marker liegt AUSDRÜCKLICH NICHT
   unter den Schlüsseln `"+1"`/`"+2"` selbst, weil `email/html.py:1268-1274` und
   `email/plain.py:277-281` per `for key in ("+1", "+2"): if key in thunder_forecast: fc =
   thunder_forecast[key]` iterieren und dabei `fc['date']`/`fc['text']` lesen — ein Eintrag ohne
   diese Felder würde dort crashen oder falsch rendern. `"_gap_offsets"` matcht das literal
   iterierte Tupel `("+1", "+2")` nie, wird von beiden E-Mail-Renderern also nie berührt: die
   E-Mail-Gewitter-Vorschau bleibt unverändert, nur der SMS-Pfad liest den neuen Schlüssel. Damit
   bleibt der Fix bewusst auf den im Issue beschriebenen SMS-/Telegram-Kurzform-Pfad begrenzt.
2. `SMSTripFormatter.format_sms()` (`sms_trip.py:419-437`): wenn `"+1"` NICHT in `thunder_forecast`
   liegt, aber `"+1"` in `thunder_forecast.get("_gap_offsets", ())`, dann
   `tomorrow_day = DailyForecast(thunder_hourly=(), has_data_gap=True)` bauen. Andernfalls
   (Normalfall a, oder Daten vorhanden) unverändertes Verhalten — `has_data_gap=False` wird dabei
   nur explizit statt implizit über den DTO-Default gesetzt, keine Verhaltensänderung.
3. `builder.py:290-295`: den Aufruf um den fehlenden Parameter ergänzen:
   `_mk_metric(FORECAST_THP, tomorrow.thunder_hourly, spec, report_type, is_level=True,
   has_gap=tomorrow.has_data_gap)`. Die eigentliche Gap→`?`-Logik existiert bereits unverändert in
   `_mk_metric()` (`builder.py:126-127`).

### Mangel 3 — Schwellwert-Weitergabe (optional, siehe AC-6)

Auch nach Fix von Mangel 1 bleibt der im Trip-Editor konfigurierte Gewitter-Schwellwert (#624) auf
`TH:` beschränkt: `trip_report.py:263-267` baut `_sms_thr` NUR aus `SMS_SYMBOL_BY_METRIC` (der
1:1-Tabelle), die für `"thunder"` nur `"TH:"` liefert. `SMS_MULTI_SYMBOLS_BY_METRIC` transportiert
laut Kommentar (`sms_trip.py:91-98`) bewusst KEINE Schwellwerte. `TH+:` fällt also strukturell immer
auf den hartkodierten Default zurück (`builder.py:85`: `DEFAULTS[FORECAST_THP] = 1.0`), unabhängig
vom Editor-Wert. Falls angenommen: in `trip_report.py:263-267` zusätzlich
`_sms_thr["TH+:"] = m.sms_threshold` setzen, wenn `m.metric_id == "thunder"` und
`m.sms_threshold is not None` — dieselbe Codestelle, ~2 zusätzliche Zeilen.

## Expected Behavior

- **Input:** Trip mit Metrik „Gewitter" aktiviert/deaktiviert (`display_config.metrics`); Etappe
  mit oder ohne existierendem Folgetag; Folgetag mit oder ohne beschaffbaren Wetterdaten.
- **Output:** Der SMS-/Telegram-Kurzform-Text enthält `TH+:` bzw. lässt es weg — synchron mit
  `TH:` — und zeigt bei einer echten Datenlücke der Folge-Etappe `TH+:?` statt `TH+:-`.
- **Side effects:** Keine Änderung am E-Mail-Renderer (Gewitter-Vorschau bleibt unverändert,
  siehe Known Limitations). Keine Änderung an `TH:` selbst.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit abgewählter Metrik „Gewitter" (`display_config.metrics` enthält
  keinen Eintrag mit `metric_id == "thunder"`) / When das Briefing (SMS oder Telegram-Kurzform) für
  eine Etappe mit existierendem Folgetag gerendert wird / Then fehlt sowohl `TH:` als auch `TH+:`
  vollständig im gerenderten Text.
  - Test: Rendert `SMSTripFormatter().format_sms(...)` mit `disabled_specs`, die „Gewitter"
    ausschließen, für Segmente + `thunder_forecast["+1"]` mit einem Gewitter-Eintrag — Assertion
    prüft, dass weder das Substring `"TH:"` noch `"TH+:"` im zurückgegebenen String vorkommt
    (Verhalten des Renderers, kein Dateiinhalt-Check).

- **AC-2 (Gegenprobe zu AC-1):** Given derselbe Trip, aber mit AKTIVIERTER Metrik „Gewitter" /
  When das Briefing gerendert wird / Then erscheinen `TH:` und `TH+:` beide im Text (wie im
  heutigen Bestandsverhalten).
  - Test: Derselbe Aufbau wie AC-1, nur mit `enabled=True`-Spec (bzw. ganz ohne `disabled_specs`)
    — Assertion prüft, dass beide Kürzel im gerenderten Text vorkommen.

- **AC-3:** Given eine berichtete Etappe mit einem ECHTEN Folgetag (`trip.get_future_stages()`
  liefert eine Etappe an `target_date + 1 Tag`), für den weder der Trend-Pfad noch der
  Fallback-Einzelfetch Wetterdaten beschaffen konnten / When das Briefing gerendert wird / Then
  zeigt der Text `TH+:?`, NICHT `TH+:-`.
  - Test: Baut einen Trip mit einer Folge-Etappe an einem Datum, ruft
    `_build_thunder_forecast_from_trend_or_fetch()` mit leerem `multi_day_trend` und einem
    Fallback-Fetch auf, der für dieses Datum keine Daten liefert (simulierter Fetch-Fehlschlag),
    und prüft am Ende des vollen Renderpfads (`format_sms()`), dass `"TH+:?"` im Text steht.

- **AC-4 (Regressions-Schutz, WICHTIG):** Given die berichtete Etappe ist die letzte Etappe des
  Trips (kein Folgetag existiert, `trip.get_future_stages()` liefert leer) / When das Briefing
  gerendert wird / Then zeigt der Text weiterhin `TH+:-`, NICHT `TH+:?`.
  - Test: Derselbe Testaufbau wie AC-3, aber mit einem Trip, dessen letzte Etappe die berichtete
    ist (kein Datum danach) — Assertion prüft `"TH+:-"` im Text UND explizit die Abwesenheit von
    `"TH+:?"`. Der Test muss beide Fälle (AC-3 und AC-4) im selben Modul gegenüberstellen, sonst
    ist die Unterscheidung „kein Folgetag" vs. „Folgetag ohne Daten" nicht bewiesen.

- **AC-5 (Mutations-Gegenprobe, PFLICHT):** Given die Implementierung aus AC-1 bis AC-4 / When der
  Adversary in Phase 6 gezielt (a) die Metrik-Bindung (z. B. `SMS_MULTI_SYMBOLS_BY_METRIC["thunder"]`
  entfernen) und (b) die Lücken-Weitergabe (z. B. `has_gap=tomorrow.has_data_gap` durch
  `has_gap=False` ersetzen) verfälscht / Then muss für JEDE der beiden Verfälschungen mindestens
  ein Test aus AC-1..AC-4 an der Wirkstelle rot werden. Die Fehl-Entwarnung (`TH+:-` statt `TH+:?`
  bei Mutation b) ist explizit die sicherheitsrelevante Richtung, die geprüft sein muss — findet
  der Adversary eine Verfälschung, die kein Test fängt, ist das ein Finding, kein bestandener Lauf.
  - Test: Kein eigener Test-Fall — dies ist die Pflichtvorgabe an den Adversary-Dialog in Phase 6
    (String-Ersetzung mit externer Sicherungskopie, siehe `.claude/agents/implementation-validator.md`
    Sektion „Step 3b").

- **AC-6 (PO-bestätigt bei Freigabe 2026-08-04, s. Mangel 3):** Given ein im Trip-Editor
  gesetzter Gewitter-Schwellwert (`m.sms_threshold` für `metric_id == "thunder"`) / When das
  Briefing gerendert wird / Then verwendet `TH+:` denselben konfigurierten Schwellwert wie `TH:`
  (nicht den hartkodierten Default 1.0). Ursprünglich eine Nebenwirkung von Mangel 1, keine
  Kernforderung des Issues — vom PO bei der Spec-Freigabe ausdrücklich als Pflichtteil bestätigt.
  - Test: Rendert mit einem konfigurierten Schwellwert (z. B. 2.0) für
    „Gewitter" und einem Gewitter-Sample knapp über dem Default (1.0), aber unter dem
    konfigurierten Wert (2.0) — Assertion prüft, dass `TH+:` NICHT auslöst (Wert unter dem
    konfigurierten Schwellwert), während es ohne diesen Fix bei 1.0 ausgelöst hätte.

## Known Limitations

- Die E-Mail-Gewitter-Vorschau (`src/output/renderers/email/html.py`,
  `src/output/renderers/email/plain.py`) bekommt durch diesen Fix KEIN Lücken-Signal — der neue
  `"_gap_offsets"`-Marker wird dort bewusst nicht gelesen (siehe Implementation Details, Mangel 2,
  Punkt 1). Das „Ausblick verschwindet wortlos"-Thema ist eigenständig und gehört zu Issue #1486,
  nicht in diesen Fix.
- Stages jenseits des Open-Meteo-Forecast-Horizonts (`is_within_forecast_horizon`) werden nicht
  gesondert behandelt. Praktisch unwahrscheinlich, weil +1/+2-Tage fast immer innerhalb des
  Horizonts liegen — theoretisch könnte so ein Fall fälschlich als „echte Lücke" (`TH+:?`) markiert
  werden statt als „außerhalb des Horizonts, strukturell nicht abrufbar". Falls das in der Praxis
  auffällt, gehört es als Nebenbefund in das Sammel-Issue #1199, nicht in diesen Fix.
- Bestehende Tests `tests/tdd/test_bug_874_th_plus_sms.py` (AC-3/AC-4 dort, andere Nummerierung als
  in dieser Spec) fixieren `thunder_forecast=None`/`{}` → `TH+:-`. Diese Tests bleiben unverändert
  grün — sie decken exakt den Normalfall (a) aus dieser Spec ab und dürfen durch den Fix nicht
  brechen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix erweitert ausschließlich bestehende, etablierte Muster
  (`SMS_MULTI_SYMBOLS_BY_METRIC` für Metrik→Kürzel-Bindung, `DailyForecast.has_data_gap` für das
  Gap→`?`-Signal) um den bereits vorgesehenen Fall `thunder`/`TH+:`. Es entsteht keine neue
  Architektur, kein neuer Kanal, keine neue Datenquelle — daher kein ADR nötig.

## Changelog

- 2026-08-04: Initial spec created
- 2026-08-04: PO-Freigabe erteilt, AC-6 (Schwellwert-Weitergabe) auf Empfehlung als Pflichtteil bestätigt
