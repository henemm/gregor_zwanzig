# Context: feat-1468-onset-verschiebung

**Issue:** #1468 — Alarm, wenn sich der Beginn eines Ereignisses deutlich verschiebt
(Gewitter 17 Uhr → 15 Uhr)
**Track:** Full Process (Intake-Score 6/6) · **Erstellt:** 2026-08-18

## Request Summary

Der Änderungs-Wächter vergleicht heute ausschließlich **Aggregate je Segment**
(`thunder_level_max`, `precip_sum_mm`, …). Verschiebt sich ein Gewitter von 17 auf 15 Uhr,
bleibt jedes Aggregat unverändert ⇒ Delta 0 ⇒ **kein Alarm**. Der Wanderer plant weiter mit
17 Uhr. #1468 soll den **Beginn** eines Ereignisses zu einer vergleichbaren Größe machen und
bei deutlicher Verschiebung alarmieren.

## PO-Entscheide (2026-08-18, Intake)

| Frage | Entscheid |
|---|---|
| Für welche Größen? | **Gewitter UND Starkregen zusammen** (nicht nur Gewitter) |
| Wie wird der Beginn vergleichbar? | **Neues Feld im Datenmodell**, mitgespeichert — nicht zur Laufzeit aus der Stundenreihe abgeleitet |
| Ab wann gilt Regen als „Starkregen"? | **≥ 4,0 mm/h — dieselbe Grenze wie im Radar** (`INTENSITY_HEAVY`, `radar_service.py:77`). Bewusst kein neues Vokabular: „Starker Regen" bedeutet auf beiden Wegen dasselbe. Basis ist die stündliche Intensität `precip_rate_mmph`, nicht die Menge. |
| Richtung der Verschiebung | **Asymmetrisch — früher ist gefährlicher.** Ein früherer Beginn meldet bei kleinerer Verschiebung als ein späterer. Begründung: Wer um 15 statt 17 Uhr ins Gewitter läuft, ist bereits im Gelände. Erfordert Neu-Mechanik (Risiko 3). |

## Kernbefund: Die Vorarbeit liefert weniger als angenommen

Das Issue nimmt an, #1419 S7 / #1493 liefere „genau die fehlende Größe". **Tut es nicht.**
Die Onset-Stunde ist eine reine **Render-Ableitung**: `render_threshold_peak_value()`
(`src/output/tokens/metrics.py:29-67`) sucht bei jedem Rendern die erste Stunde über einer
Schwelle und baut daraus ein transientes String-Token (`"mittel@14"`). Danach existiert die
Information nirgends mehr.

- `SegmentWeatherSummary` (`src/app/models.py:414-500`) führt 31 Felder — **kein Zeitfeld**.
  Für Gewitter nur `thunder_level_max` (:425) und `thunder_level_max_signals` (:430).
- Weder `weather_change_detection.py` noch `deviation_alert_engine.py` kennen den Begriff
  `onset` (grep: keine Treffer im Forecast-Pfad).

**Aber:** Der rollierende Alarm-Anker speichert die **volle Stundenreihe** bereits mit.
`_serialize_segment()` (`src/services/weather_snapshot.py:376-409`) schreibt neben
`aggregated` auch `hourly` und iteriert generisch über `vars(p)` — es landet also **jedes**
nicht-leere Feld von `ForecastDataPoint` im Anker, inklusive `thunder_level` (als `.name`,
z.B. `"MED"`), `precip_1h_mm`, `precip_rate_mmph`, `pop_pct`. Die Rohdaten für „wann fing es
im alten Stand an" liegen vor — sie werden von `detect_changes()` nur nicht gelesen
(dort wird ausschließlich `aggregated` ausgewertet).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/models.py:414-500` | `SegmentWeatherSummary` — hier entsteht das neue Onset-Feld |
| `src/app/models.py:99-126` | `ForecastDataPoint` — Stundenreihe, Quelle der Onset-Berechnung |
| `src/app/models.py:556ff` | `WeatherChange` DTO — `old_value`/`new_value`/`delta`/`threshold`/`severity`/`direction`, alle `float` |
| `src/app/models.py:1118-1138` | `AlertMetric`-Enum — braucht neue Werte |
| `src/app/models.py:1142-1166` | `AlertRule` — `kind`/`metric`/`threshold`/`unit`/`sensitivity_level` |
| `src/app/models.py:805` | `metric_alert_levels` — Nutzer-Empfindlichkeit je Metrik |
| `src/app/metric_catalog.py:28-85` | `MetricDefinition` — Katalog-Eintrag je Metrik |
| `src/app/metric_catalog.py:365-373` | Katalogeintrag `precipitation` (nur Summe, keine Intensität) |
| `src/app/metric_catalog.py:1258-1288` | `format_metric_value()` — Zahl→Text, kennt keine Uhrzeit |
| `src/services/weather_change_detection.py:38-62` | Feldlisten `_ALERT_METRIC_TO_SUMMARY_FIELD`, `_ALERT_DELTA_METRIC_TO_FIELDS` |
| `src/services/weather_change_detection.py:581-735` | `detect_changes()` — Kernvergleich `abs(delta) > threshold` |
| `src/services/weather_change_detection.py:761-786` | `_ordinal_change_triggers()` — Vorbild für einen zweiten Vergleichstyp |
| `src/services/weather_change_detection.py:268-340` | `_peak_occurred_at()` — einziger vorhandener Zeitstempel-Bezug |
| `src/services/alert_preset.py:43-56` | `_PRESET_TABLE` — die Stufen-Tabelle, Andockpunkt der Stunden-Schwelle |
| `src/services/alert_preset.py:96-107` | `ORDINAL_LEVEL_BOUNDS`, `ORDINAL_LEVEL_METRICS` |
| `src/services/alert_preset.py:145ff` | `expand_per_metric_levels()` — (Metrik, Stufe) → `AlertRule` |
| `src/services/weather_snapshot.py:179-252` | `save_alarm_anchor()`/`load_alarm_anchor()` — der Vergleichsanker |
| `src/services/weather_snapshot.py:340-409` | Serialisierung Summary + Stundenreihe |
| `src/services/deviation_alert_engine.py` | Auswertungskern: Filter, Severity, Ruhezeiten, Cooldown |
| `src/services/alert_state.py` | Melde-Gedächtnis `{"<metric>:<segment_id>": {...}}` |
| `src/output/renderers/alert/project.py:66-104` | `to_alert_message()` — `WeatherChange` → `AlertEvent` |
| `src/output/renderers/alert/project.py:56-63` | `_fmt_occurred_at()` — **Vorbild** für Zeitpunkt-Formatierung |
| `src/output/renderers/alert/render.py:40-74` | `_val()`/`_num()` — würden bei Uhrzeiten Unfug liefern |
| `src/output/renderers/alert/render.py:731-820` | `render_sms()` — Zeichenbudget, Token-Kürzung |
| `src/output/tokens/metrics.py:29-67` | `render_threshold_peak_value()` — bestehende Onset-Berechnung (Anzeige) |
| `src/output/renderers/email/helpers.py:978, 1011-1018` | Aufrufstellen Regen (`"R"`, 0,5 mm) und Gewitter (`"TH"`, Tag/Nacht) |
| `src/services/radar_service.py:147-164` | `intensity_to_text()` — **einzige** Starkregen-Definition im System (≥ 4,0 mm/h) |
| `src/services/alert_log.py` | #1954: liest `old_value`/`new_value`/`delta`/`segment_id`, entscheidet über `abs(delta)` |

## Existing Patterns

- **Stufen → Schwelle ist eine Tabelle, kein Rechenwerk.** `_PRESET_TABLE`
  (`alert_preset.py:43-56`) ist eine Liste von Tupeln
  `(AlertMetric, AlertRuleKind, entspannt, standard, sensibel)` mit hart kodierten Zahlen,
  z.B. `(WIND_GUST, DELTA, 35, 20, 12)` in km/h. `expand_per_metric_levels()` macht nur
  Spalten-Lookup. Eine Zeile `(…_ONSET, DELTA, 3, 2, 1)` in Stunden fügt sich ohne neues
  Steuerkonzept ein — genau wie das Issue es verlangt.
- **Zweiter Vergleichstyp existiert bereits.** `thunder_level_max` läuft nicht über
  `abs(delta) > threshold`, sondern über Niveau-Grenzen (`ORDINAL_LEVEL_BOUNDS`,
  `_ordinal_change_triggers()`). Der Weg dorthin: `AlertRule.sensitivity_level` →
  `_ordinal_levels` im Konstruktor (`weather_change_detection.py:386-402`) →
  eigenes Prädikat. **Strukturelles Vorbild** für einen Zeitpunkt-Vergleich.
- **Einheiten kommen aus dem Katalog**, nicht aus dem Renderer (`render.py:49`, `:101`
  lesen `get_metric(...).unit`).
- **Zeitpunkte werden separat formatiert**, wenn es sie gibt: `_fmt_occurred_at()`
  (`project.py:56-63`) geht über `local_fmt(value, tz)` → `"HH:MM"`, nicht über
  `format_metric_value()`.
- **Snapshot ist feld-generisch:** `_deserialize_summary()`
  (`weather_snapshot.py:357-373`) filtert über `dataclasses.fields(SegmentWeatherSummary)`.
  Ein neues Feld ist damit automatisch anker-tauglich, alte Dateien ohne das Feld bleiben
  lesbar (Read-Modify-Write-Vorgabe erfüllt).

## Dependencies

**Upstream** (was wir brauchen)
- Stundenreihe `SegmentWeatherData.timeseries` mit `thunder_level` bzw. Regenfeldern je Stunde
- Schwellen-Logik aus `render_threshold_peak_value()` (erste Stunde über Schwelle)
- Metrik-Katalog für Einheit, Label, Aggregation
- Tagesfenster-Filter (Gewitter-Token wird bereits Tag/Nacht-getrennt gebaut, `helpers.py:1011-1018`)

**Downstream** (was auf uns aufsetzt)
- `weather_change_detection.detect_changes()` → `deviation_alert_engine` → `trip_alert` /
  Compare-Pfad → alle **vier** Kanäle (E-Mail, Telegram, SMS, Premium-SMS)
- **`src/services/alert_log.py` (#1954, noch nicht auf main):** liest `new_value`,
  `old_value`, `delta`, `segment_id` aus jeder `WeatherChange` und protokolliert sie.
  `_ist_extremer()`/`_norm_pairs()` gruppieren nach `(metric_id, aggregation)` und
  entscheiden **innerhalb** einer Gruppe über `abs(delta)`.
- `alert_state` Melde-Gedächtnis (Schlüssel `<metric>:<segment_id>`)
- Alerts-Tab im Frontend (`AlarmeTab.svelte`, `AlertCard.svelte`) — zeigt nur Metriken aus
  `ALERTABLE_METRICS`

## Existing Specs

| Spec | Bindung für #1468 |
|---|---|
| `docs/specs/modules/weather_change_detection.md` (v2.2, approved) | Zentral. `WeatherChange`-DTO-Form, Algorithmus rein über `{summary_field: threshold}`. **Kein Sonderpfad für Zeitpunkte vorgesehen.** |
| `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` (v1.2, approved) | Steuerungsschicht: Kanäle, Ruhezeiten, Cooldown, Tageslimit, Gedächtnis-Reset. Ein neuer Metrik-Typ läuft **automatisch** mit, wenn er über den Katalog eingehängt wird. Invariante: *„Der gefährlichste Fehler ist der ausbleibende Alarm."* AC-7/7b: Compare-SMS trägt Ortsnummern, keine Namen. |
| `docs/specs/modules/feat_1493_gewitter_onset_sichtbar.md` (approved 2026-08-18) | AC-9: Trip und Ortsvergleich müssen dieselbe Onset-Stunde in derselben Schreibweise zeigen (Teilungs-Invariante). SSoT für Stufenwörter ist `THUNDER_LABEL_DE` (`src/output/metric_format.py:246-251`). PO-Linie: **keine doppelte Textform für dieselbe Information.** |
| `docs/specs/modules/feat_864_859_alert_presets.md` (draft, nicht approved) | AC-1/2: Alerts-Tab zeigt Metriken aus `ALERTABLE_METRICS` mit 4-Stufen-Regler. AC-3: Schwellwert-Anzeige ist fest `"Δ ≥ {wert} {einheit}"` — eine Stunden-Schwelle passt strukturell, `einheit` müsste `"h"` liefern. |
| `docs/specs/modules/weather_config.md` (v2.0) | SSoT-Spec für den Metrik-Katalog — neuer Katalog-Eintrag gehört dort dokumentiert. |

## Risks & Considerations

1. **🔴 „Starkregen" ist im Vorhersage-Pfad nicht definiert.** Der PO-Entscheid verlangt
   Gewitter **und** Starkregen. Für Gewitter gibt es eine Stufenleiter (`ThunderLevel`), für
   Regen **nicht**. Die bestehende Regen-Onset-Ableitung (`helpers.py:978`) nutzt
   `_DEFAULT_PRECIP_THR = 0.5` mm — das ist „irgendein messbarer Regen", **keine**
   Starkregen-Schwelle. Die einzige Starkregen-Definition im System ist die
   Radar-Nowcast-Klassifikation `INTENSITY_HEAVY` ab **≥ 4,0 mm/h**
   (`radar_service.py:77, 147-164`). Zusätzlich: `precip_rate_mmph` existiert **nur
   stündlich**, es gibt kein aggregiertes Intensitäts-Feld und keine `AlertMetric` dafür.
   ⇒ **Offener PO-Entscheid, gehört in die Spec.**

2. **Uhrzeit durch den Zahlen-Formatierer = Unfug.** `_val()` (`render.py:40-54`) rundet und
   hängt die Katalog-Einheit an; `_HANDLED_UNITS` kennt weder `"h"` noch `"Uhr"`. Ergebnis
   wäre `"15 h"` statt `"15:00"`, und ein negatives Delta würde als `"−2 h"` erscheinen statt
   „2 Stunden früher". Braucht einen eigenen Formatierpfad nach dem Vorbild
   `_fmt_occurred_at()`.

3. **Richtungs-Asymmetrie ist nicht modellierbar ohne Neubau.** Früher = gefährlicher als
   später. `AlertRule` hat **kein** Richtungsfeld; `AlertRuleKind` kennt nur `ABSOLUTE`,
   `DELTA` (meldet beide Richtungen über `abs(delta)`), `THRESHOLD_CROSSING`. Eine
   asymmetrische Schwelle (z.B. 1 h früher meldet, 3 h später meldet) braucht entweder einen
   neuen `AlertRuleKind` oder zwei Regeln.

4. **Kollision mit dem Alarm-Protokoll (#1954).** `_ist_extremer()` vergleicht `abs(delta)`
   **innerhalb** eines Register-Paars `(metric_id, aggregation)`. Löst der Onset-Change auf
   dasselbe Paar auf wie die Wert-Änderung derselben Größe, konkurrieren „2 Stunden
   Verschiebung" und „30 Prozentpunkte" um denselben Protokolleintrag — der größere nackte
   Betrag gewänne. **Vorgabe: eigenes Register-Paar für den Onset-Change.** (Abgestimmt mit
   Session #1954, 2026-08-18.)

5. **Doppelmeldung.** Ändert sich Beginn *und* Stufe gleichzeitig (Gewitter kommt früher und
   wird stärker), entstehen zwei Änderungen für dieselbe Größe. Zu klären: zwei Alarme, ein
   zusammengefasster Alarm, oder Vorrang einer Seite. Berührt die PO-Linie „keine doppelte
   Textform für dieselbe Information" aus `feat_1493`.

6. **Erster Lauf hat nichts zu vergleichen.** Bestandsanker ohne Onset-Feld dürfen keinen
   Fehlalarm erzeugen (`None` → kein Alarm, nicht „von 0 auf 15"). Bestandsdaten müssen
   lesbar bleiben (Read-Modify-Write mit Merge, CLAUDE.md-Pflicht).

7. **Ereignis verschwindet / erscheint.** Beginn alt = 17:00, neu = gar kein Gewitter (oder
   umgekehrt). Das ist keine Verschiebung, sondern ein Auftauchen/Verschwinden — bereits von
   der Stufen-Änderung abgedeckt. Der Onset-Vergleich darf hier **nicht** zusätzlich feuern.

8. **Tagesgrenze.** Beginn 23:00 → 01:00 ist eine Verschiebung um 2 Stunden über die
   Kalendergrenze, nicht um 22 Stunden zurück. Der Vergleich braucht echte Zeitpunkte, keine
   nackten Stundenzahlen.

9. **Zeichenbudget SMS.** `render_sms()` schneidet notfalls hart auf `limit` (`render.py:813`).
   Ein Onset-Token muss kurz sein und darf bestehende Tokens nicht verdrängen.

10. **Vier Kanäle sind gleichrangig** (CLAUDE.md). Der neue Alarm muss E-Mail, Telegram, SMS
    **und** Premium-SMS erreichen — und in beiden Flächen (Trip **und** Ortsvergleich).

## Abgrenzung (aus dem Issue)

- Die **Darstellung** der Anfangszeit im Briefing ist #1493 — hier nicht.
- Der **Nowcast**-Weg (Radar, „in ~20 Minuten") bleibt unverändert.
- Steuerung/Bedienoberfläche → #1462.

## Session-Koordination (2026-08-18)

- **#1948 S2** — keine Überschneidung. Fasst `api/routers/validator.py`,
  `src/services/validator_render_service.py`, `src/services/radar_service.py` an.
  Sperrzone `official_alerts.py:1896-2104` (#1929, fremde Session) notiert.
- **#1954** — **auf `main` seit 2026-08-18** (Merge `e677aee2`, PR #1963, Prod-Selftest PASS).
  Keine Dateikollision (nur `src/services/alert_log.py`), aber Kopplung über die
  `WeatherChange`-Feldform, siehe Risiko 4 und Analyse-Abschnitt „Register-Paar".

---

# Analysis (Phase 2, 2026-08-18)

## Type

**Feature** — neue Alarm-Größe, kein Fehlverhalten bestehenden Codes.

## Die drei Entwurfs-Entscheidungen

### E1 — Der Beginn wird ein eigenes Summary-Feld je Größe

Zwei neue Felder in `SegmentWeatherSummary`, befüllt in
`WeatherMetricsService.compute_basis_metrics()` (`src/services/weather_metrics.py:397-470`)
nach dem Muster der bestehenden `_compute_*`-Methoden:

| Feld | Bedeutung | Schwelle |
|---|---|---|
| `thunder_onset_utc` | erste Stunde mit `thunder_level >= LOW` | `ThunderLevel.LOW` (wie `render_threshold_peak_value("TH", …, threshold=1.0)`) |
| `precip_heavy_onset_utc` | erste Stunde mit `precip_rate_mmph >= 4.0` | **4,0 mm/h** — PO-Entscheid, identisch mit `INTENSITY_HEAVY` (`radar_service.py:77`) |

Typ: `Optional[datetime]` (UTC, naiv — Hausnorm `src/utils/timezone.py:107-109`).
**Nicht** eine nackte Stundenzahl: Die Verschiebung 23:00 → 01:00 ist 2 Stunden, nicht 22
(Risiko 8). Nur ein echter Zeitstempel rechnet das richtig.

**Warum ein eigenes Feld je Größe und nicht ein gemeinsames:** Das Alarm-Protokoll bildet
sein Register-Paar über `metric_and_aggregation_for_field(c.metric)`
(`src/app/metric_catalog.py:1166-1196`) — Schlüssel ist der **Summary-Feldname**. Ein eigenes
Feld ergibt automatisch ein eigenes Paar `("thunder", "onset")` und damit die von #1954
geforderte Trennung von der Stufen-Änderung `("thunder", "max")`. Ohne eigenen
Katalog-Eintrag liefert der Reverse-Lookup `None` und die Beginn-Änderung fällt **still**
aus dem Protokoll (`alert_log.py:132-134`) — Fehlerfall ohne Fehlermeldung, gehört bewacht.

**Compare erbt automatisch:** `summarize_points()` (`weather_metrics.py:1108-1160`) ist ein
dünner Wrapper um `compute_basis_metrics()`. Trip und Ortsvergleich teilen den Code, die
Teilungs-Invariante ist ohne Zusatzarbeit erfüllt.

**Bestandsdaten:** `_deserialize_summary()` (`weather_snapshot.py:357-373`) filtert über
`dataclasses.fields()`. Alte Anker ohne die Felder laden weiter, das Feld ist dann `None`.

### E2 — Der Beginn ist eine LOKALE, tagesfenster-gefilterte Größe

**🔴 Die Falle:** Die Aggregation ist heute **zeitzonen- und fensterblind**
(`weather_metrics.py:397-470` kennt weder `tz` noch `day_window_*`). Das Tagesfenster
(Default 4–19 Uhr, `src/app/day_window.py:20-21`) wird erst in der Render-Schicht angewendet
(`helpers.py:1005-1007`). Ein naiv in der Aggregation berechnetes Onset wäre die erste
Überschreitung **im gesamten Zeitraum inklusive Nachtstunden**.

Das ergäbe zwei verschiedene Zahlen, die beide „Gewitterbeginn" heißen: Das Briefing zeigt
„Gewitter mittel ab 14:00" (gefiltert), der Alarm meldete „03:00 → 01:00" (ungefiltert). Der
Wanderer bekäme einen Alarm über eine Verschiebung, die in seinem Briefing nie stand.

**Entscheidung:** Der Alarm vergleicht **dieselbe Zahl, die im Briefing steht.** Der Zweck
des Tickets ist wörtlich *„das Briefing hat 17 Uhr geschrieben und der Forecast ändert sich
auf 15 Uhr"* — eine andere Bezugsgröße macht den Alarm unbrauchbar. Zeitzone und
Tagesfenster müssen die Onset-Berechnung also erreichen.

**Absicherung als AC (Muster von #1493 AC-9):** Aus **derselben Fixture** muss die
Onset-Stunde im gerenderten Briefing und der Wert im Summary-Feld **gleich** sein — geprüft
als Gleichheit beider Größen, nicht als zwei getrennte Textprüfungen. Driften Anzeige und
Alarm auseinander, wird der Test rot.

**Wichtig:** Ein global berechnetes Onset lässt sich **nicht** nachträglich in ein
fenster-gefiltertes umrechnen — die erste Überschreitung nachts und die erste im Tagesfenster
sind verschiedene Stunden. Nachrüsten geht also nicht; das muss von Anfang an stimmen.

### E3 — Asymmetrie über eine dritte Weiche, kein neuer Regeltyp

`detect_changes()` hat bei `weather_change_detection.py:692-696` bereits genau die Weiche,
die gebraucht wird:

```python
level = self._ordinal_levels.get(metric)
if level is not None:
    triggered = self._ordinal_change_triggers(old_value, new_value, level)
else:
    triggered = abs(delta) > threshold
```

Der Beginn-Vergleich fügt sich als dritter Zweig nach demselben Muster ein (eigenes
`_onset_levels`-Dict, eigenes Prädikat), Severity analog bei `:705-708`. **Kein neuer
`AlertRuleKind`** nötig — das spart die Verzweigungsstellen bei `:513/517/535` und
`loader.py:376`.

Die Asymmetrie selbst ist echtes Neuland (das Muster „zwei Schwellen je nach Vorzeichen"
existiert nirgends). Sie sitzt in der Preset-Tabelle, die pro Stufe **zwei** Werte trägt:

| Stufe | früher (vorgezogen) | später (verschoben) |
|---|---|---|
| entspannt | ab 2 h | ab 4 h |
| standard | ab 1 h | ab 3 h |
| sensibel | ab 1 h | ab 2 h |

*(Vorschlag — die Zahlen gehören in die Spec-Freigabe. Ausgangspunkt ist der Issue-Text
„entspannt ab 3 h, standard ab 2 h, sensibel ab 1 h", nach vorn verschärft und nach hinten
gelockert.)*

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/app/models.py` | MODIFY | 2 Summary-Felder, 2 `AlertMetric`-Werte |
| `src/services/weather_metrics.py` | MODIFY | 2 `_compute_*_onset()`, Aufruf in `compute_basis_metrics`, Regel in `aggregate_stage` |
| `src/app/metric_catalog.py` | MODIFY | `summary_fields`/`alert_metrics` um `"onset"` erweitern (`thunder`, `precipitation`), `alert_label`, `sms_code` |
| `src/services/weather_change_detection.py` | MODIFY | `_ALERT_METRIC_TO_SUMMARY_FIELD`, `_ALERT_METRIC_TO_CATALOG_ID`, `_ALERTABLE_METRIC_VALUES`, Onset-Weiche + Prädikat + Severity |
| `src/services/alert_preset.py` | MODIFY | `_PRESET_TABLE` (zwei Schwellen je Stufe), `ONSET_METRICS`-Set, `_make_rule` |
| `src/output/renderers/alert/project.py` | MODIFY | Zeitpunkt-Wert nach Vorbild `_fmt_occurred_at()` (`:56-63`) |
| `src/output/renderers/alert/render.py` | MODIFY | eigener Formatierpfad — `_val()` würde „15 h" statt „15:00" liefern |
| `internal/model/trip.go` | MODIFY | Go-Spiegel: `AlertMetric`-Konstanten, `AlertableMetrics`, `DefaultDeltaThreshold` |
| `frontend/src/lib/generated/alertPresetThresholds.generated.json` | REGENERATE | `scripts/generate_alert_preset_table.py` |
| `scripts/generate_alert_metric_mapping.py`-Ausgaben | REGENERATE | sonst reißt `tests/tdd/test_alert_metric_mapping_parity.py` |
| `frontend/…/alerts-tab/alertMetricTable.ts` | MODIFY | `METRIC_DEFAULTS`, `ALL_ALERT_METRICS`, `ALERTABLE_METRICS`, `_METRIC_UNITS`, `CATALOG_TO_ALERT_METRICS` |
| `frontend/src/lib/utils/alertMetricLabels.ts` | MODIFY | Label + Reverse-Mapping (nicht generiert, separat gepflegt) |
| `tests/…` | CREATE | Verhaltenstests, siehe unten |

## Scope Assessment

- **Dateien:** ~12 produktiv + 2 generierte + Tests
- **LoC produktiv:** geschätzt **+200 bis +250** — das **LoC-Limit von 250 wird voraussichtlich
  gerissen**, `loc_limit_override 500` ist einzuplanen
- **Risiko: HIGH** — Alarm-Pfad, Persistenz-Schema, Go/Python-Parität, 4 Kanäle, 18+
  Registrierungsstellen

## Offene Punkte für die Spec

1. **Doppelmeldung** (Risiko 5): Gewitter kommt früher **und** wird stärker ⇒ zwei
   `WeatherChange`. Vorschlag: beide melden, aber im Text zusammenfassen — die PO-Linie aus
   `feat_1493` verbietet doppelte Textform für dieselbe Information.
2. **Erscheinen/Verschwinden** (Risiko 7): `None → 15:00` ist kein Beginn-Alarm, sondern
   von der Stufen-Änderung abgedeckt. Vorschlag: Onset-Vergleich feuert **nur**, wenn beide
   Seiten gesetzt sind.
3. **Melde-Gedächtnis** (`deviation_alert_engine.py:242`): filtert über
   `abs(new_value - last)`. Bei Uhrzeiten läuft das über die Tagesgrenze falsch — zweite
   Stelle mit demselben Fehler wie der Vergleich selbst.
4. **Aktivierungs-Kopplung:** Der Alarme-Tab zeigt nur Metriken, deren Katalog-Größe im
   Wetter-Tab aktiv ist (`activeAlertMetricsFromCatalog.ts:22-29`,
   `weather_change_detection.is_alert_metric_active()`). Da der Beginn an den bestehenden
   Katalog-IDs `thunder`/`precipitation` hängt, erbt er deren Gate — gewollt: wer Gewitter
   nicht beobachtet, will auch keinen Gewitterbeginn-Alarm.
5. **Konkrete Stundenwerte** der Preset-Tabelle (siehe E3).

## Test-Strategie (Kern, deterministisch)

- **Verschiebung meldet:** Anker 17:00, neuer Stand 15:00, Stufe standard ⇒ genau ein Alarm.
- **Gegenprobe Richtung:** dieselbe Verschiebung nach hinten (17:00 → 19:00) ⇒ **kein**
  Alarm bei standard (2 h < 3 h Schwelle für später). Bewacht die Asymmetrie.
- **Tagesgrenze:** 23:00 → 01:00 ⇒ 2 h Verschiebung, nicht 22 h.
- **Anzeige-Gleichheit (E2):** dieselbe Fixture ⇒ Onset im Briefing-Text == Summary-Feld.
- **Bestandsanker:** Anker ohne das Feld ⇒ kein Alarm, keine Ausnahme.
- **Erscheinen:** `None → 15:00` ⇒ kein Beginn-Alarm.
- **Protokoll-Trennung:** Stufen- und Beginn-Änderung derselben Größe erzeugen **zwei**
  getrennte Protokoll-Einträge (Register-Paare `("thunder","max")` vs. `("thunder","onset")`).
- **Textform:** „15:00", nicht „15 h"; „2 h früher", nicht „−2 h".
- **Vier Kanäle:** Beginn-Alarm erscheint in E-Mail, Telegram, SMS und Premium-SMS.
