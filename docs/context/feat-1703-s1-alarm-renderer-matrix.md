# Context: #1703 Scheibe 1 — Alarm-Renderer × alle `_METRICS`

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 1. Deckt Fläche 1 aus
     docs/reference/metric_output_matrix.md §4.1. Scheibe 3 (Blindstelle
     get_all_metrics()-vs-_METRICS) ist Voraussetzung und seit PR #1710
     erledigt — diese Scheibe baut darauf auf. -->

## Request Summary

Die vier Alarm-Renderer (`render_subject`/`render_email`/`render_telegram`/`render_sms`
in `src/output/renderers/alert/render.py`) bekommen eine Matrix-Achse im bestehenden,
bereits budgetierten Wächter `tests/tdd/test_channel_metric_matrix.py` (#1677 B,
Option C aus `metric_output_matrix.md` §5). Zusätzlich soll erzwungen werden, dass keine
alarmfähige Metrik unbenannt in den `_HANDLED_UNITS`-Ersatzpfad (`render.py:35/49`) fällt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py` | Prüfling: die vier Renderer + `_val`/`_num`/`_unit_display`/`_code`/`_HANDLED_UNITS` |
| `src/output/renderers/alert/model.py` | `AlertEvent:11`, `OnsetEvent:30`, `CorridorEvent:48` — die drei Ereignistypen |
| `src/app/metric_catalog.py` | `_METRICS:92-590` (28 Einträge), `format_metric_value:1004`, `get_alert_label:988`, `get_sms_code:959`, `get_decimals:968` |
| `src/services/weather_change_detection.py:82-99` | `_ALERT_METRIC_TO_CATALOG_ID` — 13 Keys, zwei OR-Tupel |
| `src/app/models.py:1040-1060` | `AlertMetric`-Enum, 14 Werte |
| `tests/tdd/test_channel_metric_matrix.py` | **Zieldatei** — hier kommt die neue Achse hinein (Bestand: AC-13/14/15 aus #1677 B, AC-1..AC-8 aus Scheibe 3) |
| `tests/helpers/hourly_columns.py` | **Vorbild** für „Soll aus dem Katalog rechnen, Ausnahmen aus dem Produktivmodul lesen" |
| `docs/reference/metric_output_matrix.md` | Fläche 1 (§4.1) + Scheibenbeschreibung (§6); Definition of Done: Zelle umtragen |

### Produktive Aufrufer der vier Renderer (gemessen, außerhalb Tests)

| Aufrufer | Renderer |
|---|---|
| `src/services/notification_service.py:1166-1171` (`_dispatch_alert_message`, ab `:1116`) | alle vier; zusätzlich `render_alert_telegram(single_msg)` bei `:1289` (Mehrort-Fan-out) |
| `src/services/radar_alert_service.py:93-94` | `render_subject`, `render_email` |
| `src/services/validator_render_service.py:138-141` | alle vier (Validator-Vorschau) |

## Existing Patterns

**Wie eine Metrik in die vier Renderer gelangt** (gemessen): `AlertEvent.metric_id`
(`model.py:14`) → lokale Helfer → Katalogfunktionen. Kein Renderer ruft die
Katalogfunktionen direkt auf, mit **einer** Ausnahme: `_datablock_single`
(`render.py:365`) liest `get_metric(e.metric_id).unit` direkt und umgeht damit
`_unit_display()` — der `thunder`-Sonderfall (`render.py:84-85`, `unit=""` → `"%"`)
greift dort **nicht**.

**Welcher Renderer welchen Helfer nutzt** (das ist die entscheidende Asymmetrie):

| Helfer | `render_subject` | `render_email` | `render_telegram` | `render_sms` |
|---|---|---|---|---|
| `_val()` (Einheit, `_HANDLED_UNITS`) | ja (`:308`) | ja (`:355`, `:370`, `:374`) | ja (via `_email_line:338`) | **nein** |
| `_num()`/`_unit_display()` (Multi-Zeile, #978) | ja (`:320`) | ja (`:481-505`) | ja (`:574-578`) | **nein** |
| `_code()` → `get_sms_code()` | nein | nein | nein | **nur hier** (`:597`, `:136`) |
| `_label()` → `get_alert_label()` | ja | ja | ja | nein |

→ **`render_sms` ist strukturell ein anderer Prüffall** als die drei übrigen: es kennt
weder Einheit noch Alarm-Kürzel, nur `sms_code`. Eine Assertion-Familie „für alle vier
gleich" wäre falsch.

**Soll-Mengen rechnen statt tippen** (`tests/helpers/hourly_columns.py:100-158`): Soll =
Katalog minus benannte Ausnahmen, die per `getattr` **aus dem Produktivmodul** gelesen
werden (`hourly_excluded_metric_ids():41-61` bricht mit `pytest.fail()` ab, wenn das
Produktivmodul keine benannte Ausnahmekonstante führt), plus Vakuum-Schutz
(`assert_soll_menge_ist_plausibel():130-158` prüft Katalog-Mindestgröße und
Nicht-Leerheit). Das ist das Muster, das die neue Achse übernehmen muss.

**Zwei Bauwege für Alarm-Nachrichten** koexistieren in den Bestandstests, ohne geteilte
Fixture: (a) direkte Dataclass-Instanziierung (`AlertEvent(metric_id=…)`), (b) der echte
Projektionsweg `to_alert_message()` über `WeatherChange`
(`test_issue_917_alert_renderer.py:70-95`, `test_alert_renderer_format_bugs.py:30-59`,
`test_issue_919_radar_alert_canonical.py:199-222`).

## Dependencies

- **Upstream:** `app.metric_catalog` (Label, Kürzel, Einheit, Nachkommastellen),
  `output.renderers.email.design_tokens`, `utils.ascii_fold`, `alert.model`
- **Downstream:** die drei Aufrufer oben — d.h. jede Änderung am Renderer wirkt auf
  Wetter-Alarm-Versand, Radar-Alarm und Validator-Vorschau gleichzeitig

## Gemessener Ist-Stand: Katalog × Alarmfähigkeit

`_METRICS` hat **28** Einträge; **15** sind alarmfähig (nicht-leeres `alert_metrics`
**oder** nicht-leeres `alert_label`): `temperature`, `temperature_cold`, `humidity`,
`wind`, `gust`, `precipitation`, `rain_probability`, `thunder`, `cape`, `snowfall_limit`,
`visibility`, `uv_index`, `freezing_level`, `snow_depth`, `fresh_snow`.

**Die fünf alarmfähigen Metriken, deren Einheit NICHT in `_HANDLED_UNITS` steht** — sie
laufen heute in den Ersatzpfad `render.py:51-52`:

| metric_id | unit | decimals | über `AlertMetric` erreichbar? |
|---|---|---|---|
| `thunder` | `""` | 0 | ja (`THUNDER_LEVEL`) |
| `cape` | `"J/kg"` | 0 | Enum-Wert existiert, aber `selectable=False` → s. offene Frage 1 |
| `uv_index` | `""` | 0 | `alert_metrics={}` — nur `alert_label`, kein Enum-Wert |
| `snow_depth` | `"cm"` | 0 | `alert_metrics={}` — nur `alert_label`, kein Enum-Wert |
| `fresh_snow` | `"cm"` | 0 | ja (`FRESH_SNOW`) |

**Der eigentliche Konstruktionsfehler** (gemessen, nicht vermutet): `_HANDLED_UNITS`
(`render.py:35`) ist eine **wortgleiche Kopie** der sieben Einheiten, die
`format_metric_value()` (`metric_catalog.py:1016-1024`) tatsächlich mit Suffix
formatiert — `m`, `km`, `hPa`, `%`, `km/h`, `°C`, `mm`. Der `else`-Zweig dort
(`:1025-1026`) liefert `str(value)` **ohne Einheit**; der Ersatzpfad in `_val()` ist
also eine bewusste Reparatur, kein Defekt. Fragil ist die **Doppelung**: wird
`format_metric_value()` um eine Einheit erweitert, ohne `_HANDLED_UNITS` mitzuziehen,
bleibt der Alarm-Renderer still im Ersatzpfad — und verliert dort die deutsche
Zahlformatierung (kein Tausenderpunkt, Dezimalpunkt statt Komma).

`AlertMetric` (`models.py:1040-1060`) hat 14 Werte, `_ALERT_METRIC_TO_CATALOG_ID` 13 Keys.
`HUMIDITY` ist ein bewusst toter Eintrag (Kommentar `models.py:1057-1060`:
Deserialisierbarkeit alt-persistierter `AlertRules`). Zwei OR-Tupel:
`TEMPERATURE_MIN → ("temperature_cold", "temperature")`,
`SNOW_LINE → ("snowfall_limit", "freezing_level")`. Kein `alert_metrics`-Wert im Katalog
zeigt ins Leere. `SNOW_LINE` wird von keiner Katalog-Metrik selbst deklariert — es
existiert nur als Rückwärtsabbildung.

## Gemessener Ist-Stand: Testabdeckung (= die unbewachte Fläche)

18 Testdateien rufen die vier Renderer auf. **Keine einzige** parametrisiert über
`_METRICS` oder `get_all_metrics()`. Über alle Alarm-Renderer-Tests hinweg kommen
insgesamt **8 verschiedene** `metric_id`-Werte vor: `gust`, `temperature_cold`,
`precipitation`, `cape`, `thunder`, `rain_probability`, `visibility`, `freezing_level`
— von 15 alarmfähigen Katalogeinträgen. **Sieben alarmfähige Metriken werden in keinem
Alarm-Renderer-Test je gerendert.**

Das Nächstliegende ist `test_issue_919_radar_alert_canonical.py:234-247`
(`test_ac8_deviation_all_four_renderers_run`) — ruft alle vier Renderer nacheinander
auf, aber nur für `gust`, und nur als Nicht-Leer-Smoketest.

**`_HANDLED_UNITS` wird in keinem Test als Bezeichner gelesen**
(`grep -rln "_HANDLED_UNITS" tests/ src/` trifft nur `render.py` selbst). Der Ersatzpfad
ist ausschließlich für `cape`/`J/kg` geprüft:
`test_952_alert_mail_design_fidelity.py:51-62` testet `_val()` direkt
(`assert _val(event, 1230.0) == "1230 J/kg"`), `test_957_alert_mail_literal_structure.py:149-156`
prüft `"500 J/kg" in html`. Für `cm` (`snow_depth`, `fresh_snow`), `""` (`thunder`,
`uv_index`), `°` (`wind_direction`), `h` (`sunshine`) existiert **keine** Prüfung des
Ersatzpfads.

## Existing Specs

- `docs/specs/modules/fix_1703_s3_selectable_metrics.md` — Vorgänger-Scheibe, liefert
  `_METRICS`-statt-`get_all_metrics()`-Iterationsbasis und das Spec-Format
- `docs/specs/modules/fix_1677_sms_reihenfolge.md` — AC-13/14/15, das budgetierte Gate,
  in das die neue Achse eingehängt wird
- `docs/reference/metric_output_matrix.md` §4.1 „Fläche 1", §6 „Scheibe 1"

## Risks & Considerations

1. **`render_sms` gehört strukturell nicht in dieselbe Assertion-Familie.** Es kennt
   weder Einheit noch `alert_label`, nur `sms_code`. Wer „alle vier gleich" prüft, prüft
   `render_sms` gegen eine Zusicherung, die dort nicht gilt.
2. **Prüfort = Wirkort.** `_val()` direkt zu testen (wie
   `test_952_alert_mail_design_fidelity.py:51-62`) prüft die Hilfsfunktion, nicht die
   Verdrahtung. Die Zusicherung „keine alarmfähige Metrik fällt unbenannt in den
   Ersatzpfad" wirkt in `render_subject`/`render_email`/`render_telegram` — dort muss
   sie gemessen werden. (Memory: `reference_pruefort_muss_dem_wirkort_entsprechen`)
3. **`temperature_cold`/`TEMPERATURE_MIN` hat zwei verwechselbare Schutzmechanismen.**
   `is_alert_metric_active()` trägt das Ergebnis über das OR-Tupel (`temperature`),
   **nicht** über `_SELECTABLE_GATE_EXEMPT` — die Exemption wird dort nie gelesen. Genau
   diese Verwechslung war Adversary-Finding F001 in Scheibe 3. Eine Behauptung „X wirkt
   wegen der Exemption" auf dem Alarmpfad ist ein Verdachtsfall.
   (Memory: `reference_selectable_gate_collateral_damage_pattern`)
4. **Ein Wächter über den Ersatzpfad darf nicht zur Schwellen-Manipulation verleiten.**
   Der Ersatzpfad ist heute inhaltlich korrekt (er hängt die Einheit an, was
   `format_metric_value()` unterlassen würde). Der Wächter muss die **Doppelung**
   bewachen, nicht den Ersatzpfad verbieten.
5. **Keine geteilte Alarm-Fixture vorhanden.** Eine neue, katalogweit parametrisierte
   Achse braucht einen Fixture-Bauweg — Entscheidung „direkte Dataclass" vs.
   „Projektionsweg `to_alert_message()`" steht in der Analyse an und hat direkte
   Auswirkung darauf, was der Test überhaupt beweisen kann.
6. **Pfadfehler im Epic-Issue und im Matrix-Dokument:** beide nennen
   `tests/tdd/test_compare_hourly_catalog_columns.py:122` als Vorbild. Die Datei liegt
   unter `tests/unit/test_compare_hourly_catalog_columns.py`; das eigentliche Muster
   steckt in `tests/helpers/hourly_columns.py`.

## Analysis

### Type

Feature (Wächter-Ausbau) — kein Bug-Fix-Auftrag. Wie Scheibe 3: neue Achse in einer
bestehenden, budgetierten Testdatei. Die Analyse hat allerdings drei Widersprüche im
Prüfling **gemessen**, die den Zuschnitt berühren (s. „Gemessene Widersprüche").

### Die Soll-Menge, gerechnet statt getippt

Drei Kandidatenmengen, gemessen unterschiedlich groß:

| Menge | Größe | Inhalt |
|---|---|---|
| `alert_label != ""` **oder** `alert_metrics != {}` | 15 | die 15 aus dem Kontext-Abschnitt |
| in `_ALERT_METRIC_TO_CATALOG_ID` erreichbar | **11** | ohne `humidity`, `rain_probability`, `uv_index`, `snow_depth` |
| davon produktiv im Trip-Alarm erzeugbar | **10** | zusätzlich ohne `cape` |

Gemessen, warum die vier wegfallen: `humidity` und `rain_probability` sind
`is_precursor=True` (Katalog-Docstring: „ignoriert von `from_display_config`/
`from_alert_rules`"); `uv_index` und `snow_depth` haben weder `alert_metrics` noch
einen Eintrag in `_ALERT_METRIC_TO_CATALOG_ID` (`weather_change_detection.py:82-99`).

→ **Die Soll-Menge ist rechenbar** (`alert_metrics`/`is_precursor` aus dem Katalog +
`_ALERT_METRIC_TO_CATALOG_ID` aus dem Produktivmodul), ganz ohne getippte Liste. Die
vier Ausschlüsse tragen ihre Begründung im Produktivcode — das `hourly_columns.py`-
Muster ist also anwendbar, ohne eine neue Ausnahme-Konstante erfinden zu müssen.

### Renderer-Zuschnitt: drei plus eins, nicht vier gleich

`render_subject`/`render_email`/`render_telegram` teilen `_val()`/`_label()`
(`get_alert_label`). `render_sms` teilt davon **nichts** — nur `_code()`
(`get_sms_code`). Zwei Assertion-Familien, nicht eine.

`OnsetEvent` gehört **nicht** in die Matrix: die Dataclass hat kein `metric_id`-Feld
(`model.py:30-46`), alle drei produktiven Konstruktoraufrufe
(`radar_alert_service.py:59-68`, `notification_service.py:1085-1094`,
`validator_render_service.py:102-110`) setzen keinen Katalogbezug, und der Renderer
verzweigt binär über `is_convective` mit hartcodierten Literalen (`render.py:146/225/276/285`).
Strukturell metrik-los.

`CorridorEvent` trägt zwar `metric_id` (`model.py:54`), ist aber ein **toter Pfad**:
`evaluate_corridor_thresholds()` (`corridor_threshold.py:68`) hat keinen Aufrufer in
`src/`/`api/`, und der einzige produktive `_send_alert()` (`trip_alert.py:296`) übergibt
`corridor_hits` nicht — Default `None` → `[]` (`trip_alert.py:1225/1271`). Entsprechend
baut **keine einzige** Testdatei im Repo je ein `CorridorEvent`
(`grep -rln "CorridorEvent" tests/` → 0). Gehört mangels Wirkung nicht in diese Scheibe.

### Gemessene Widersprüche im Prüfling

Alle drei sind **gemessen** (echte Renderer-Aufrufe), nicht aus Code geschlossen:

1. **Gewitter erscheint im Bündel-Alarm als Prozent, im Einzel-Alarm ohne Einheit.**
   Einzel: `Gewitter: 10→20`; Bündel: `Gewitter 10→20%`. Ursache: der Einzelpfad liest
   `get_metric().unit` (`""`) direkt (`render.py:47`, `:365`), der Bündelpfad nutzt
   `_unit_display()`, das für `thunder` hart `"%"` liefert (`render.py:84-85`).
   **Das `%` widerspricht der PO-Entscheidung #1585** (2026-08-07): `thunder` ist die
   **Stärke** (`kein·leicht·mittel·hoch`), die Prozent-Achse wäre `thunder_probability`.
   `alert_metrics={"max": "thunder_level"}` (`metric_catalog.py:340`) bestätigt: der
   Alarmwert ist eine Stufe. „Stufe 3" als „3 %" auszugeben ist nutzersichtbar falsch,
   und Gewitter ist die sicherheitskritischste Größe des Produkts.
   Der Code-Kommentar (`render.py:78-83`) beruft sich auf eine Design-Vorlage aus #978 —
   also auf einen Stand **vor** der PO-Entscheidung. Fachlich verwandt: #1480
   („Wächter gegen lokale Kopien der Gewitter-Stufenskala"), zurückgestellt hinter #1488.

2. **Zwei Metrikpaare sind in drei von vier Kanälen byte-identisch.**
   `temperature`/`temperature_cold` teilen `alert_label="Temp"`,
   `snow_depth`/`fresh_snow` teilen `alert_label="Schnee"`. Betreff, E-Mail und Telegram
   sind für die Paare **byte-identisch**; nur der SMS-Code trennt sie (`D`/`N` bzw.
   `SD`/`NS`). Produktiv entsteht daraus heute keine Verwechslung (`snow_depth` erreicht
   den Alarmpfad nicht; bei `temperature_cold`/`temperature` meinen beide denselben
   Min-Temperatur-Alarm, s. OR-Tupel). **Für den Wächter ist es dennoch entscheidend:**
   eine Mutation, die `metric_id` zwischen den Paaren vertauscht, bliebe in drei von
   vier Kanälen grün. Die Mutations-Gegenprobe muss das wissen.

3. **Tausenderpunkt fehlt im Ersatzpfad.** `_val()` liefert `1500 J/kg`, `_num()` für
   denselben Wert `1.500` (`render.py:51` hat keine Tausenderlogik, `:66-72` schon).
   Betrifft alle fünf Ersatzpfad-Metriken ab Wert 1000. Produktiv praktisch
   unerreichbar: `cape` erreicht den Trip-Alarm nicht, `thunder` läuft auf Stufe 0–3,
   `uv_index`/`snow_depth` erreichen den Alarmpfad nie, `fresh_snow` bräuchte 10 m
   Neuschnee.

**Zusätzlich gemessen — `cape` ist nicht überall blockiert:** Im Trip-Pfad ja
(`display_config` und `metric_alert_levels` sind gekoppelt, `trip_alert.py:265-274`).
Im **Compare-Pfad** nicht: `_display_config_from_active_metrics()` gibt für
nicht-migrierte Alt-Presets `None` zurück (`compare_alert.py:500-501`), und
`alert_preset.py:278` ruft den `is_alert_metric_active`-Filter **nur bei gesetztem**
`display_config` auf — `_STANDARD_METRIC_LEVELS` enthält `cape` (`compare_alert.py:44`).
Ob ein solcher Alt-Preset produktiv existiert, ist **nicht gemessen** (lokal keine
`kind="vergleich"`-Datei vorhanden). Der Validator-Vorschau-Endpoint
(`POST /api/trips/{id}/alert-preview`) ist ungefiltert, aber kein Nutzer-Versandweg.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | neue Achse: Alarm-Renderer × rechenbare Soll-Menge |
| `docs/reference/metric_output_matrix.md` | MODIFY | Fläche 1 auf den neuen Wächter umtragen (Definition of Done) |
| `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md` | CREATE | Spec |
| `src/output/renderers/alert/render.py` | MODIFY *(nur bei Scope-Variante B)* | `_unit_display()`-Sonderfall `thunder` |

### Scope Assessment

- Dateien: 3 (Variante A) bzw. 4 (Variante B)
- Geschätzte LoC: +180/-0 (A) bzw. +195/-3 (B) — unter dem 250er-Limit
- Risiko: **MITTEL**. Der Wächter selbst ist risikoarm (Testdatei). Variante B fasst den
  Alarm-Renderer an, der von drei Diensten geteilt wird.

### Technical Approach

Neue Achse in `test_channel_metric_matrix.py`, parametrisiert über die **gerechnete**
Soll-Menge. Zwei Assertion-Familien: (a) Betreff/E-Mail/Telegram gegen
`get_alert_label()`, (b) SMS gegen `get_sms_code()` mit token-grenzen-bewusstem Match
(die Präfix-Kollision `N` ⊂ `NL`/`NS` macht eine reine Teilstring-Prüfung unbrauchbar —
im Bestand ist der einzige kollisionssichere Alarm-SMS-Test die Vollstring-Gleichheit
`test_alert_sms_location_positions.py:454`). Zusätzlich ein Wächter gegen die
**Doppelung** `_HANDLED_UNITS` ↔ `format_metric_value()`: für jede Einheit prüfen, ob
die Whitelist mit dem tatsächlichen Formatierungsverhalten übereinstimmt — das ist
maschinell prüfbar und fängt genau den lautlosen Drift, den das Epic beschreibt.

Ausnahmen folgen dem `_NIGHT_SCALAR_IDS`-Muster (`channel_layout.py:85-89` ↔
`test_channel_metric_matrix.py:57-60`): **kein `pytest.skip`**, sondern ein invertierter
Assertion-Zweig in derselben parametrisierten Funktion.

### Open Questions

- [x] **Scope-Entscheidung PO (2026-08-11): Variante B — Gewitter-Prozent wird in dieser
      Scheibe mitrepariert.** `_unit_display()`s `thunder`-Sonderfall (`render.py:84-85`)
      fällt; der Bestandstest aus #978, der `"Gewitter 10→20%"` erwartet
      (`test_978_deviation_line_readability.py:232`, ebenso `:218` im Betreff), prüft
      damit veraltetes Verhalten und wird auf den Sollzustand nachgezogen — nicht
      gelöscht, weil er die Bündel-Zeile im Übrigen weiter bewacht. Maßgeblich ist die
      spätere Entscheidung #1585 (2026-08-07) gegen die frühere Design-Vorlage #978.
