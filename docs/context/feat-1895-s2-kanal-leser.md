# Context: feat-1895-s2-kanal-leser

> Scheibe **S2** von Issue #1895. Scheibe S1 (`alert_metric_channels` als reiner
> Speicherweg) ist seit 2026-09-22 live (`dfc13d9d`, PR #2402).

## Request Summary

Die Alarm-Kanal-Auflösung soll die in S1 angelegte Zuordnung `alert_metric_channels`
tatsächlich **lesen**, sodass eine Metrik ihren eigenen Kanal-Satz bekommt statt des
abo-weiten. Im selben Zug wandern die Kanäle von der wirkungslosen Regel-Entität
(`alert_rules[].channels`) in das neue Feld.

## Scheibenschnitt (bindend aus der S1-Spec, `docs/specs/modules/alert_metric_channels.md:221-238`)

| Scheibe | Inhalt | Stand |
|---|---|---|
| S1 | Feld, Persistenz, Roundtrip, Doku, ADR-0077 | ✅ live `dfc13d9d` |
| **S2** | **Leser im Alarm-Pfad + Migration `alert_rules[].channels` → neues Feld** | **diese Scheibe** |
| S3 | Editor-Spalte im Frontend — darf laut ADR-0043 **erst nach S2** | offen |
| S4 | Rückbau von `alert_rules` | offen |

Ausdrücklich **nicht** Teil von S2: Frontend/`.svelte`, Rückbau von `alert_rules`,
Validierung der Metrik-Schlüssel. `has_active_rules` bleibt unangetastet — weder S1
noch S2–S4 fassen es an (ein Wegfall würde `alert_on_changes=False` überstimmen).

## Der heutige Auflöser (selbst gemessen)

`src/services/alert_channels.py` (126 Zeilen) ist die **eine** Auflösung für Trip und
Ortsvergleich (Issue #2279 S1, ADR-0021/ADR-0023):

- `resolve_alert_channels(override, inherited, rule_channel_sets, user_id) -> set[str]`
  (`:28`) — reiner Kern, vier Schritte:
  1. `override is not None` ⇒ ersetzt `inherited` **vollständig** durch die truthy
     gesetzten Kanäle — auch wenn das Ergebnis leer ist (`:49-50`)
  2. keine aktiven Regeln ⇒ Ergebnis ist `inherited` (`:52-53`)
  3. aktive Regeln ⇒ **Union je Regel**; nicht-leeres `rule_channels` gewinnt für diese
     Regel, sonst fällt die Regel auf `inherited` zurück (`:54-60`)
  4. Tier-Gates genau einmal am Ende: `sms` / `premium_sms` je nach
     `sms_allowed()` / `premium_sms_allowed()` (`:62-65`)
- `effective_alert_channels(subscription, settings, user_id)` (`:113`) — Dispatcher,
  unterscheidet am Typ: Rohdict ⇒ Ortsvergleich (`_compare_channel_inputs`, `:96`),
  sonst Trip (`_trip_channel_inputs`, `:86`)
- `settings` ist dokumentiert **inert** (`:12-15`) — die Sendezeit-Readiness bleibt in
  `notification_service.py`

## Wertform, die S1 tatsächlich persistiert (selbst gemessen)

`internal/handler/trip_alert_metric_channels_test.go:111-112`:

```go
alice := map[string]interface{}{"rain": map[string]interface{}{"telegram": true}}
bob   := map[string]interface{}{"wind": map[string]interface{}{"email": true}}
```

Also `{metrik: {kanal: bool}}` — **zeichengleich die Form, die `resolve_alert_channels`
schon als `override` erwartet** (`alert_channels.py:50` liest `override.get(ch)`).
Das ist kein Zufall: S1 hat den Go-Typ `map[string]interface{}` gewählt, damit der
bestehende `mergeConfigMap`-Mechanismus greift (Muster `DisplayConfig`).

Go-Feld: `internal/handler/trip.go:265`
(`AlertMetricChannels *map[string]interface{} \`json:"alert_metric_channels,omitempty"\``).
Python-Leser: `src/app/trip.py:231`, `src/app/models.py:1362`,
`src/app/loader.py:292/708/1645`.

## Aufrufstellen des Auflösers (selbst gemessen, 10 Stück)

| Datei | Zeile(n) | Weg |
|---|---|---|
| `src/services/trip_alert.py` | 400, 552, 1072, 1671, 2509, 2726 | über `self._effective_alert_channels(trip)` (`:2876`, dünner Delegat auf `:2889`) |
| `src/services/compare_alert.py` | 110, 601 | direkt `effective_alert_channels(preset, …)` |
| `src/services/compare_official_alert.py` | 472 | über Methode |
| `src/services/compare_radar_alert.py` | 168 | direkt |

## Risks & Considerations

- **🔴 R2 „stille Kanal-Abschaltung" wird von genau dieser Scheibe scharf gestellt.**
  S1 war dagegen *bauartbedingt* immun (kein Leser ⇒ konnte nicht feuern). Eine
  Zuordnung je Metrik, die die heutige **Union über alle aktiven Regeln** (`:54-60`)
  ersetzt, ist strukturell eine **Kanal-Verengung**. Die Zusicherung „kein Kanal
  verschwindet still" gehört in die ACs, gemessen **an der Versandstelle** und in
  **beiden** Flächen, Premium-SMS eingeschlossen — nicht am Rückgabewert des Auflösers.
  Bindend dazu: #1701 („Alarme müssen **alle** Kanäle erreichen"), Paritäts-Audit #1533
  (Premium-SMS als Alarm-Kanal in beiden Flächen, alle Alarmarten, über dieselbe
  geteilte Auflösung).
- **Metrikfreie Alarmarten.** Amtliche Warnungen und Radar-/Regen-Alarme haben
  strukturell keine Metrik aus dem Katalog. Sie müssen den abo-weiten Satz behalten,
  sonst verschwinden dort Kanäle — offen bis der Aufrufstellen-Befund vorliegt.
- **Bestandsdaten.** Read-Modify-Write mit Merge, niemals Replace (BUG-DATALOSS-GR221,
  #102). Die Migration `alert_rules[].channels` → `alert_metric_channels` fasst
  Persistenz an und löst den Pre-Snapshot-Hook `data_schema_backup.py` aus.
- **Mandantentrennung.** `user_id` geht bereits in den Auflöser (`:32`, Tier-Gates);
  jeder neue Lesepfad muss die echte `user_id` durchreichen, nie `"default"`.

## 🔴 Drei Metrik-Vokabulare, die auseinanderlaufen

Das ist der Kern-Befund dieser Kontext-Phase. Es gibt im Bestand **drei** Schlüsselmengen:

| Menge | Ort | Beispiel-Schlüssel |
|---|---|---|
| (a) Metrik-Katalog `MetricDefinition.id` | `src/app/metric_catalog.py:30`, Registry ab `:113` | `gust`, `precipitation`, `temperature`, `thunder`, `freezing_level` |
| (b) `display_config.metric_alert_levels` | `src/app/models.py:859` | **identisch mit (a)** — belegt über `loader.py:741-753` und `metric_catalog.py:668` |
| (c) `alert_rules[].metric` (`AlertMetric`-Enum) | `src/app/models.py:1212-1249` | `wind_gust`, `precipitation_sum`, `temperature_min`/`_max`, `thunder_level`, `snow_line` |

(a) und (b) sind dieselbe Menge. **(c) ist ein drittes, semantisch andersartiges Vokabular** —
teils aggregations-gesplittet (`temperature_min`/`temperature_max` aus `temperature`),
teils umbenannt (`wind_gust` vs. `gust`, `precipitation_sum` vs. `precipitation`,
`thunder_level` vs. `thunder`). Nur `fresh_snow`, `cape`, `visibility`, `freezing_level`
sind zeichengleich in beiden Mengen.

Abgelöst: `snow_line` → `freezing_level` (Migration `loader.py:741-753`, Read-Modify-Write,
vorhandener `freezing_level`-Eintrag gewinnt). Der Enum-Wert `SNOW_LINE` bleibt für
alt-persistierte Regeln bestehen (`weather_change_detection.py:44-48,92-103` behandelt ihn
als OR über `snowfall_limit` + `freezing_level`), wird aber nicht neu vergeben.

### Der Widerspruch, den /20-analyse auflösen muss

ADR-0077 Punkt 3 lässt die Schlüsselmenge für `alert_metric_channels` **bewusst offen** und
ordnet die Entscheidung **S3** zu (Begründung: Validierung in S1/S2 wäre Scope-Creep und
würde Bestandsdaten mit `snow_line` brechen). S2 baut aber den **Leser** — und ein Leser muss
nachschlagen, also die Schlüssel kennen. Die Entscheidung ist damit faktisch nach S2
vorgezogen, ohne dass S2 sie validieren darf.

Das ist keine Formalie: Die Empfindlichkeitsstufe (b) ist laut ADR-0043 der **einzige**
Alarm-Auslöser. Eine Metrik, die alarmiert, trägt also einen Schlüssel aus (a)/(b). Die
Kanäle, die S2 migrieren soll, hängen aber an (c). Wer Menge (c) als Schlüssel nimmt, findet
beim Nachschlagen nichts, weil der Auslöser mit (a) arbeitet — und umgekehrt verliert eine
Migration aus (c) die Zuordnung, wenn sie nicht `wind_gust` → `gust` übersetzt.

## Migration: Wertform ändert sich, nicht nur der Ablageort

`alert_rules[].channels` ist durchgehend eine **Liste von Kanal-Strings**
(`["email","sms"]`), leer = Vererbung:

- Go: `internal/model/trip.go:66` (`Channels []string`)
- Python: `src/app/models.py:1254` (`list[str]`), Lader `loader.py:197`, Schreiber `loader.py:1729`
- Frontend: `frontend/src/lib/components/alert-rules-editor/alertChannels.ts:13-31`,
  Typ `frontend/src/lib/types.ts:108-109` (`channels?: string[]`)

Das neue Feld trägt `{kanal: bool}`. Die Migration muss also **Liste → Dict-of-bool**
umformen, nicht nur umhängen — und dabei die leere Liste („erbt") von einem explizit leeren
Dict („nichts", das laut `alert_channels.py:49-50` den geerbten Satz vollständig ersetzt)
unterscheiden. Diese zwei Fälle sehen im Ziel-Format gleich aus, bedeuten aber das Gegenteil.

## Bindende Zusicherungen, die S2 nicht brechen darf

| Quelle | Zusicherung |
|---|---|
| `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` AC-1 | **Parität**: identische Kanal-Konfiguration liefert für `route` und `vergleich` dieselbe Kanalmenge über alle 16 Kombinationen; AC-4 Tier-Gates genau einmal; AC-5 `settings` inert |
| ADR-0046 | Kanal-Ebene regelt, **auf welchem Weg** eine ausgelöste Meldung ankommt, nicht **ob** — eine fehlende Metrik-Zuordnung darf niemals unterdrücken |
| ADR-0077 Punkt 4 | fehlender Metrik-Schlüssel = **Nicht-Abweichung**, erbt den abo-weiten Satz |
| ADR-0043 | keine Konfigurationsfläche ohne sichtbare Wirkung — begründet „S2 vor S3" |
| ADR-0021 / ADR-0023 | geteilter Auswertungskern, `kind`-Diskriminator — S2 darf keine zweite Kanal-Prüfkette je `kind` einziehen |
| `docs/specs/modules/feat_1701_alarm_premium_sms.md` | jeder Alarm-Pfad (Trip-Änderung/Radar/amtlich + Vergleichs-Pendants) muss **alle vier** Kanäle erreichen können |

## Doku-Drift-Gates, die grün bleiben müssen

- `tests/test_adr_index_drift.py` — ADR-Datei ↔ Index-Eintrag + Status-Zeile
- `tests/test_api_contract_drift.py` — jede `/api/`-Route und jedes JSON-Tag der Kern-Structs
  steht in `docs/reference/api_contract.md`; `alert_metric_channels` ist dort schon
  dokumentiert (`:925-940`, inkl. Merge-Regel) und muss bei Semantik-Änderung nachgezogen werden
- `tests/test_user_id_default_guard.py` (ADR-0003) — AST-Wächter gegen stillen
  `user_id`-Fallback auf `"default"`; trifft jeden neuen Lesepfad
- `tests/test_router_user_id_required.py` — `user_id` ist Pflichtparameter an FastAPI-Endpunkten
- `tests/tdd/test_issue_316_docs_cleanup.py` — erst für S3 relevant (S2 fasst kein Frontend an)

## Kartierung der zehn Aufrufstellen — nur zwei sind metrikbehaftet

| Aufrufstelle | Alarmart | Metrik-Bindung | Wirkung |
|---|---|---|---|
| `trip_alert.py:552` (`check_and_send_alerts` → `AlertEvaluationConfig`) | Abweichungs-/Delta-Alarm | **MEHRERE METRIKEN** | **nur Log** — `eval_result.channels` wird nirgends weiterverwendet, erscheint nur im Protokoll (`:730`) |
| `trip_alert.py:2509` (`_send_alert`) | Abweichungs-/Delta-Alarm | **MEHRERE METRIKEN** (`changes: List[WeatherChange]`, je `.metric`) | **echter Versand** → `split_by_threshold` → `send_deviation_alert(effective_channels=allowed)` (`:2531`) |
| `compare_alert.py:601` (`_build_eval_config`) | Vergleichs-Delta-Alarm | **MEHRERE METRIKEN** | **echter Versand** — `config.channels` wird **nicht** erneut aufgelöst, sondern direkt durchgereicht (`:283` → `:280-281` → `send_multi_location_deviation_alert`, `:333-335`) |
| `trip_alert.py:400` (`_protokolliere_unterdrueckung`) | gemischt (Delta **und** amtlich, über `reason`) | metrikfrei | nur Log (`:402`) |
| `trip_alert.py:1072` (`_get_cached_weather`) | keine — Anker-Lesehelfer für beide Alarmarten | metrikfrei (bewusst) | reiner Lesepfad, `kanaele` ist Iterationsschlüssel (`:1077-1080`) |
| `trip_alert.py:1671` (`check_radar_alerts`) | Radar-/Nowcast (Starkregen-Onset) | metrikfrei | echter Versand (`:2338`) |
| `trip_alert.py:2726` (`_send_official_alert_only`) | amtliche Warnung | metrikfrei — Gefahrenart steht in `hazards`, nicht in `metrics` (`:2818-2819`) | echter Versand (`:2796-2799`) |
| `compare_alert.py:110` | Unterdrückungs-Protokoll | metrikfrei | nur Log (`:108-112`) |
| `compare_official_alert.py:472` (Aufrufer `:166`, `:203`) | amtliche Warnung (Vergleich) | metrikfrei (`:307-308`) | `:166` nur Log · `:203` echter Versand (`:282-284`) |
| `compare_radar_alert.py:168` | Radar-/Nowcast (Vergleich) | metrikfrei (Modul-Docstring `:5-10`: Parallelpfad **neben** den Metrik-Abweichungsalarmen) | echter Versand (`:342-343`) |

### Was daraus folgt

1. **S2 berührt genau zwei Alarmarten:** den Trip-Abweichungsalarm und den
   Vergleichs-Abweichungsalarm. Radar und amtliche Warnungen sind **strukturell**
   metrikfrei und müssen den abo-weiten Satz unverändert behalten — täte S2 dort etwas,
   wäre das genau die stille Kanal-Abschaltung aus Risiko R2.
2. **🔴 Beide metrikbehafteten Stellen bündeln heute mehrere Metriken in EINEN Aufruf.**
   Metrik-Genauigkeit heißt also nicht „anderes Argument übergeben", sondern den Aufruf
   **aufbrechen**: Kanalwahl je `change.metric` statt einmal pro Lauf. Das ist der
   eigentliche Umbau von S2.
3. **🔴 Die Trip-Seite löst zweimal auf, die Vergleichs-Seite einmal.** Bei `trip_alert.py:552`
   ist das Ergebnis reine Protokoll-Zierde — der Versand löst bei `:2509` unabhängig neu auf.
   Beim Vergleich reicht `:601` direkt zum Versand durch. **Folge für die Tests:** Ein Test,
   der bei `:552` grün wird, beweist über den Trip-Versand **nichts**. Die Zusicherung muss
   an `:2509` bzw. `compare_alert.py:335` gemessen werden — das ist die Stelle, an der sie wirkt.
4. **Ein Alarm kann mehrere Metriken tragen.** Wenn zwei Metriken mit *verschiedenen*
   Kanal-Zuordnungen in derselben Nachricht stecken, ist offen, was gilt: Nachricht
   aufteilen, Union bilden, oder je Kanal filtern. Das ist die zentrale Entwurfsfrage für
   `/20-analyse` — und der Punkt, an dem eine falsche Wahl Kanäle verliert.

### Der Ortsvergleich alarmiert sehr wohl pro Metrik

Der Docstring-Satz „Der Vergleich kennt keine Alarm-Regeln" (`alert_channels.py:100-102`)
meint ausschließlich das Fehlen von `AlertRule`-Objekten — deshalb `rule_channel_sets=[]`
(`:109`). Pro Metrik alarmiert der Vergleich über denselben `DeviationAlertEngine`-Kern wie
der Trip: `metric_alert_levels` aus `preset.display_config` (`compare_alert.py:594-598`),
Metrik-Auswahl über `_display_config_from_active_metrics` (`:614-660`), und jede erkannte
Änderung ist ein `WeatherChange` mit `.metric` (`:570`). `_SUMMARY_KEY_TO_CATALOG_ID`
(`:62-72`) mappt die Compare-Summary-Keys auf **dieselben Katalog-IDs** wie beim Trip.

**Korrektur (nachgemessen):** Eine erste Lesart dieser Kontext-Phase lautete
„`WeatherChange.metric` trägt die Katalog-ID". Das ist **falsch** — siehe den Abschnitt
„Vier Vokabulare" unten. Die Schlüsselmengen-Frage ist damit nicht kleiner, sondern größer
geworden.

## Bestehende Wächter der Kanal-Auflösung

- `tests/tdd/test_alert_channel_resolution_parity.py` — Kern + Parität (#2279 S1):
  leeres Override ersetzt vollständig (`:166`), `override=None` lässt `inherited` unberührt
  (`:185`), Union mit Regel-Rückfall (`:202`), **AC-1 Parität über 16 Kombinationen** (`:225`),
  Legacy-Preset (`:275`), Tier-Gate beidseitig (`:314`), `settings` inert (`:353`, `:379`)
- `tests/tdd/test_compare_alert_channels.py` — Delegations-Nachweise (AC-6) für **alle vier**
  Konsumenten (`:188`, `:229`, `:258`, `:288`) plus Briefing-Dispatch (`:343`) und
  „`user_id` nie `default`" (`:377`)
- `tests/tdd/test_meteoalarm_feed_deutschland.py:699-701` — echter Konsument im Szenario

Die weiteren Kanal-Tests (`test_trip_alert_channel_precedence.py`,
`test_alert_channel_threshold*.py`, `test_alert_channel_premium_sms.py` …) prüfen
Kanal-*Verhalten* über die Service-Klassen, bewachen aber nicht die Auflösung selbst.


## 🔴 Korrektur: es sind VIER Vokabulare, nicht drei

Die Messung an der Definition (nicht an der Verwendung) dreht die Schlüsselmengen-Frage um:

`src/app/models.py:602` — `metric: str  # e.g., "temp_max_c", "wind_max_kmh"`

`WeatherChange.metric` trägt also **weder** eine Katalog-ID **noch** einen
`AlertMetric`-Wert, sondern den **rohen Summary-Key** der Wetter-Aufbereitung. Das ist eine
vierte Menge:

| Menge | Ort | Beispiel |
|---|---|---|
| (a) Katalog-IDs | `metric_catalog.py` | `gust`, `precipitation` |
| (b) `metric_alert_levels` | `models.py:859` | identisch (a) |
| (c) `AlertMetric` (`alert_rules[].metric`) | `models.py:1212-1249` | `wind_gust`, `precipitation_sum` |
| **(d) `WeatherChange.metric`** | **`models.py:602`** | **`temp_max_c`, `wind_max_kmh`** |

Die Kette ist damit: (b) → `expand_per_metric_levels(levels: dict[str,str]) -> list[AlertRule]`
(`alert_preset.py:178-182`) → Regeln in Vokabular (c) → der Detektor meldet Änderungen in
Vokabular **(d)**.

### Die Asymmetrie, die S2 tragen muss

Ein Übersetzer (d) → (a) existiert — aber **nur auf der Vergleichs-Seite**:
`_SUMMARY_KEY_TO_CATALOG_ID` (`compare_alert.py:62`, 10 Schlüssel; abgesichert gegen
Katalog-Drift in `src/output/renderers/compare_metric_catalog.py:209-213`).

Auf der **Trip-Seite gibt es ihn nicht**: `grep temp_max_c src/services/trip_alert.py`
liefert **null** Treffer. Die Trip-Versandstelle (`:2509`) hält also `changes` in Vokabular (d)
und hat keinen Weg nach (a). Wer in S2 metrik-genau nachschlagen will, muss diesen Übersetzer
auf der Trip-Seite erst bereitstellen — oder das neue Feld auf (d) schlüsseln, was es an ein
internes Detektor-Detail bindet statt an den Katalog, den der Editor in S3 anzeigen wird.

**Das ist die zentrale Entwurfsentscheidung für `/20-analyse`** — und sie ist genau die, die
ADR-0077 Punkt 3 nach S3 verschoben hat, die S2 aber beantworten muss, um überhaupt
nachschlagen zu können.

## Die Zusicherung, die jeden Entwurf aussiebt

ADR-0046 und ADR-0077 Punkt 4 sagen: die Kanal-Ebene regelt, **auf welchem Weg** eine
ausgelöste Meldung ankommt, **nie ob**. Der kritische Fall ist deshalb nicht „zwei Metriken
mit verschiedenen Kanälen in einer Nachricht", sondern:

> Eine Metrik ist einem Kanal zugeordnet, den das Abo überhaupt nicht trägt.

Dann erreicht dieser Alarm **niemanden** — und die Kanal-Ebene hätte über das *Ob*
entschieden. Das verstößt gegen ADR-0046 und gegen #1701 („Alarme müssen **alle** Kanäle
erreichen"). Diese Zusicherung gehört als AC in die Spec und siebt die naive Lesart
„Metrik-Eintrag = vollständiges Override" aus, unabhängig davon, welcher Entwurf gewinnt.

## Möglicher Ansatzpunkt: die vorhandene Partitionsstelle

Beide echten Versandstellen teilen den Kanal-Satz heute schon auf, an genau einer Funktion:

`src/services/alert_channel_threshold.py:20-35` —
`split_by_threshold(channels: set[str], urgency: str, thresholds) -> (allowed, suppressed)`,
rein mengenbasiert, ohne Zustand, ohne Metrik-Bezug.

Genutzt bei `trip_alert.py:2522` und `compare_alert.py:280-281`. Wenn die metrik-genaue
Verengung an dieser Partitionsstelle ansetzen kann, entfällt das Aufteilen der Nachricht —
und damit bleiben Drosselung, Tages-Obergrenze und der Doppel-Alarm-Guard unberührt. Ob das
trägt, ist in `/20-analyse` zu prüfen: `split_by_threshold` kennt heute keine Metrik, und die
Versandstelle hält mehrere Metriken gleichzeitig.

## Herkunft dieser Scheibe

- Park-Bedingung des PO-Entscheids vom 2026-09-21 („sobald #1230 entsperrt wird") ist am
  2026-09-22 **gemessen erfüllt**: #1230 trägt kein `status:deferred` mehr. Scheibe S1 ist
  am selben Tag unter diesem Ticket ausgeliefert worden. Die veralteten Marker am Ticket
  (Titel-Präfix `[GEPARKT bis #1230]`, Label `status:deferred`) wurden beim Intake entfernt.

---

# Analysis

> Erzeugt von `/20-analyse` am 2026-09-22. Die Kontext-Phase oben hat die Fläche
> vollständig und messbelegt kartiert (10 Aufrufstellen, 4 Vokabulare, Wächter, Gates).
> Die drei Explore-Fan-outs und der Plan-Agent aus dem Phasen-Ablauf sind deshalb
> **bewusst nicht gefahren**: ihr Auftrag (betroffene Dateien / bestehende Specs /
> Abhängigkeiten) steht oben bereits gemessen auf der Platte, ein zweiter Durchlauf
> hätte ihn nur reproduziert und Kontext gekostet. Die strategische Bewertung
> (Entwurf A/B) ist stattdessen unten mit der ADR-Begründung ausgeschrieben, die ein
> Plan-Agent ohne ADR-0021-Kenntnis nicht liefern kann.

## Type

**Bugfix** (Issue #1895, Label `bug`) — ausgeliefert in Scheiben. S2 ist der Leser.

## Die vier offenen Fragen der Kontext-Phase — beantwortet

### F1 „Nachricht aufteilen, Union bilden, oder je Kanal filtern?" → **Union je Metrik**

Das ist **keine freie Wahl**, sondern von ADR-0077 Punkt 4 erzwungen: *kein Eintrag = die
Metrik erbt den abo-weiten Satz.* Trägt ein Alarm Metrik X (Eintrag `{telegram}`) und
Metrik Y (kein Eintrag), muss Y den vollen geerbten Satz erreichen — die Nachricht muss
also mindestens Y's Satz tragen. Das **ist** die Union.

Und die verlangte Semantik steht schon wörtlich im Bestand, `alert_channels.py:56-60`:

```python
for rule_channels in rule_channel_sets:
    if rule_channels:  channels.update(rule_channels)
    else:              channels.update(inherited)
```

S2 ist damit eine **Um-Schlüsselung derselben Mechanik**: dieselbe Schleife, Schlüssel
`Metrik` statt `Regel`. Kein neuer Algorithmus.

**Verworfen: „je Kanal filtern + Nachricht aufteilen".** Nicht aus Geschmack, sondern
weil es die Kanal-je-Änderung-Filterung an zwei Versandstellen **getrennt** aufbauen
müsste — der Vergleich hat die Kanal-Gruppierung aus #1461 S3b-2b
(`compare_alert.py:283-305`), der Trip hat sie nicht. Das ist genau die „zweite
Kanal-Prüfkette je `kind`", die ADR-0021/ADR-0023 verbieten. Zusätzlich fasste es
`_last_below_threshold_channels`, das Alarm-Protokoll (`sent_channels`/`failed_channels`),
`_record_official_alert_state` und die Ergebnis-Zusammenführung an — die Fläche, auf der
still etwas kaputtgeht. Preis der Union: eine auf Telegram verengte Metrik erreicht
E-Mail trotzdem, **wenn sie mit einer nicht-verengten Metrik im selben Alarm steckt**.
Das ist ADR-0046-konform (Kanal-Ebene regelt den Weg, nie das Ob) und die Richtung, in
der ein Fehler harmlos ist: zu viel Zustellung, nie zu wenig.

### F2 Schlüsselmenge → **Katalog-`metric_id`, und zwar die WÄHLBARE**

Prüfbares Prinzip statt „(a) ist gleich (b)":

> **Der Kanal-Schlüssel ist dieselbe `metric_id`, unter der der Alarm die Änderung
> rendert** (`AlertEvent.metric_id`, `project.py:362`).

Damit ist die Zuordnung Ende-zu-Ende prüfbar (der Nutzer liest „Böen", der Kanal hängt an
`gust`), S3's Editor zeigt genau diese Schlüssel, und (c)/(d) werden zu reinen
Übersetzungsfragen.

**Gemessener Tie-Break-Zwang.** Die zwei vorhandenen Übersetzer widersprechen sich bei
`temp_min_c`: `_resolve_metric_id` (`project.py:123`) disambiguiert per `direction`
(steigendes Minimum ⇒ `temperature`), `_SUMMARY_KEY_TO_CATALOG_ID:64` mappt unbedingt auf
`temperature_cold`. Nachgemessen im Katalog: `temp_min_c` steht in **zwei**
`summary_fields` — `temperature` (`metric_catalog.py:121`) und `temperature_cold`
(`:147`). Und `temperature_cold` trägt `selectable=False` (`:149`).

Nicht wählbar sind genau drei Katalog-Größen (gemessen): `temperature_cold`,
`confidence`, `cape`.

**Tie-Break-Entscheid: bei mehreren Kandidaten gewinnt der `selectable=True`-Kandidat;
gibt es nur einen Kandidaten, gewinnt dieser** (deckt `cape` ab, das keine wählbare
Alternative hat). Begründung steht im Bestand, nicht in dieser Analyse:

- `metric_catalog.py:124-125`: „beide Richtungen haengen an der SICHTBAREN Groesse; die
  interne Pseudo-Groesse temperature_cold bleibt ohne Deklaration"
- `weather_change_detection.py:91-92`: „the second id (`temperature`) is the Weather-Tab
  metric the user actually toggles (there is **no separate** `temperature_cold` toggle)"

Ohne diesen Tie-Break wäre ein Kältealarm-Eintrag **strukturell unerreichbar**:
`temperature_cold` kann im Editor (S3) nie angeboten werden, also nie einen Eintrag
bekommen, also nie verengen — eine Bedienfläche mit unsichtbarem Loch.

**Fail-soft ist Pflicht, nicht Bequemlichkeit.** `_resolve_metric_id` **wirft**
(`KeyError` bei unbekanntem Feld, `ValueError` bei Mehrdeutigkeit ohne cmp-Treffer). Im
Kanalpfad wäre das ein Totalausfall des Alarms. Der Leser braucht eine Hülle:
unbekannt oder unauflösbar ⇒ **kein Eintrag ⇒ erbt** (ADR-0077 Punkt 4).

### F3 Metrikfreie Alarmarten → **strukturell immun, nicht per Prüfung**

Nicht „der Leser prüft, ob die Alarmart metrikbehaftet ist" — sondern **der Parameter
existiert an den acht metrikfreien Aufrufstellen gar nicht**:

```python
effective_alert_channels(subscription, settings, user_id, metrics=None)
```

Radar, amtliche Warnungen und die vier Protokoll-Pfade rufen **unverändert** auf ⇒ der
neue Arm kann dort bauartbedingt nicht feuern. Nur `trip_alert.py:2509` und
`compare_alert.py:601` reichen Metriken durch. Das ist mutations-prüfbar: ein
Metrik-Argument an einer Radar-Stelle ergänzen ⇒ ein Test muss rot werden. Risiko R2
(„stille Kanal-Abschaltung bei metrikfreien Alarmen") wird damit von einer
Verhaltenszusage zu einer **Bauform**.

Der reine Kern bleibt primitiv (dokumentiertes Muster `alert_channels.py:9-10`) — das
Nachschlagen macht der Adapter am Rand.

### F4 Migration → **kopieren, Leser gibt dem Eintrag Vorrang je Metrik**

`alert_rules[].channels` bleibt in S2 **unangetastet stehen** (Rückbau ist S4). Der Leser
staffelt **je Metrik** in drei Armen: **Eintrag vorhanden ⇒ gewinnt · sonst die Kanäle
der aktiven Regel(n), die auf DIESE Metrik abbilden · sonst geerbt.** Rollback-sicher
(ein Zurückrollen des Codes findet die alten Regel-Kanäle unverändert vor), Wirkung
sofort da, und S4 entfernt nur den mittleren Arm.

**🔴 Der mittlere Arm ist je Metrik aufzulösen, nicht als heutige Gesamt-Union.** Heute
liefert `_trip_channel_inputs:92` `[rule.channels for rule in active_rules]` **ohne
Metrik-Bezug** — ein preset-weiter Wert. Nimmt der mittlere Arm diesen Wert, zieht eine
einzige Metrik ohne Eintrag die volle Regel-Union ins Ergebnis und hebt die Verengung
aller anderen Metriken wieder auf; das wäre genau die unten verworfene Variante „beide
Quellen weiter unionieren" und S2 hätte keine Wirkung (ADR-0043). Die Abbildung
`Metrik → Regel(n)` ist vorhanden und gemessen (`alert_rules[].metric` über
`_ALERT_METRIC_TO_CATALOG_ID`), also **filtert der Adapter am Rand die Regeln auf die
Metrik** — der reine Kern bleibt unverändert primitiv. Nach der Migration ist der
mittlere Arm deckungsgleich mit dem Eintrags-Arm, weshalb S4 ihn folgenlos entfernen kann.

Verworfen: **verschieben** (kopieren + `channels` leeren) — fasst `alert_rules` an, was
nominell S4 ist, und ein Deploy-Rollback ließe Nutzer mit leeren Regel-Kanälen zurück.
Verworfen: **kopieren und beide Quellen weiter unionieren** — die Regel-Union re-weitet
die Verengung sofort wieder auf, die Zuordnung hätte keine Wirkung (ADR-0043).

Benanntes Muster für die Mechanik liegt im Haus: die `snow_line`→`freezing_level`-
Migration in `loader.py:741-753` (Read-Modify-Write, vorhandener Eintrag gewinnt).

## Der Befund, der in die PO-Freigabe gehört

**Die Migration ändert für Bestandsnutzer die Kanalmenge — nach unten.**

Heute unioniert `_trip_channel_inputs:92` die Kanäle **aller aktiven Regeln**, unabhängig
davon, welche Metriken der laufende Alarm betrifft. Hat ein Trip eine Regel auf A
(`telegram`) und eine auf B (`email`), erreicht ein Alarm über **A allein** heute
`telegram ∪ email`. Nach der Migration erreicht er nur noch `telegram`.

Das ist **die Reparatur, nicht ein Regress**: #1895 sagt, die heutige Kanalzuordnung
hängt an der falschen Entität. Aber es ist eine Verhaltensänderung an Bestandsdaten
**ohne Nutzerhandlung** und gehört als solche in die deutschen ACs, die der PO in `/30`
freigibt — nicht in eine Fußnote.

Die Gegen-Zusicherung, die jeden Entwurf aussiebt — **präzise formuliert, weil zwei
Bestandszusicherungen sie einschränken**:

> **Der Metrik-Arm allein darf eine nicht-leere Kanalmenge nicht auf leer bringen.**
> Wird die Menge durch den Metrik-Arm leer, während sie ohne ihn nicht leer wäre, gilt der
> Satz ohne Metrik-Arm. Diese Prüfung liegt **VOR** den Tier-Gates.

Warum nicht „die Kanalmenge darf nie leer werden": das wäre gegen den Bestand formuliert.

- Ein **explizit leeres `override`** ersetzt heute vollständig, auch ins Leere
  (`alert_channels.py:49-50`), und genau das ist testbewacht
  (`test_alert_channel_resolution_parity.py:166`). Eine Nie-leer-Regel machte diesen Test
  rot.
- Läge die Prüfung **nach** den Tier-Gates, erzeugte ein Free-Tier-Nutzer mit dem
  Metrik-Eintrag `{sms: true}` einen Rückfall auf den vollen geerbten Satz — das
  Tier-Gate hätte damit eine **Kanal-Erweiterung** ausgelöst und AC-4 aus #2279 S1
  („Tier-Gates genau einmal") wäre verletzt. Entfernt ein Tier-Gate den letzten Kanal,
  bleibt die Menge leer: das ist Tier-Politik, nicht Kanal-Politik.

Die drei Migrations-Varianten, damit `/30` sie nicht neu erfinden muss:

| | Was in den Eintrag geschrieben wird | Verengung ggü. heute | Nutzer-Absicht |
|---|---|---|---|
| **M1 (empfohlen)** | die Kanäle der Regel(n) dieser Metrik | ja — das ist der Fix | erhalten |
| M2 | der heute wirksame Satz (geerbt ∪ alle Regeln) | keine | verworfen |
| M3 | nichts — S2 nur Leser, Feld bleibt leer | keine | nichts zu migrieren |

**Empfehlung M1.** Die heutigen Regel-Kanäle *sind* die geäußerte Absicht des Nutzers;
#1895 sagt genau, dass diese Absicht an der falschen Stelle hängt. M2 wirft sie weg
(Regel A „nur Telegram" bekäme plötzlich alles), M3 verschiebt die Frage nur und ließe S4
die Kanäle still fallen lassen.

## Vier Migrations-Fallen (gemessen, keine davon stand in der Kontext-Phase)

1. **(c)→(a) ist eins-zu-vielen.** `_ALERT_METRIC_TO_CATALOG_ID`
   (`weather_change_detection.py:96-118`) bildet auf **Tupel** ab:
   `TEMPERATURE_MIN → ("temperature_cold","temperature")`,
   `SNOW_LINE → ("snowfall_limit","freezing_level")`. Eine Regel migriert also auf
   **mehrere** Einträge — bei `TEMPERATURE_MIN` greift der Wählbarkeits-Tie-Break aus F2
   (⇒ nur `temperature`), bei `SNOW_LINE` sind **beide** wählbar (⇒ beide Einträge,
   #961-OR-Politik).
2. **Kollisionen sind real, nicht theoretisch.** Auf `temperature` fallen drei
   `AlertMetric`-Werte (`TEMPERATURE_MIN`, `TEMPERATURE_MAX`, `TEMPERATURE_CHANGE`), auf
   `precipitation` drei (`PRECIPITATION_SUM`, `_CHANGE`, `_HEAVY_ONSET`), auf `thunder`
   zwei (`THUNDER_LEVEL`, `THUNDER_ONSET`). **Merge-Regel: Union** — Union kann nicht
   unterdrücken.
3. **Leere Regel-Kanalliste ⇒ Schlüssel WEGLASSEN, nicht `{}` schreiben.** Unter
   ADR-0077 Punkt 4 ist „kein Eintrag" das Erben. Ein `{}` ist die Einladung für jeden
   späteren Leser, es als vollständiges Override zu lesen — und
   `alert_channels.py:49-50` zeigt, dass genau diese Lesart im Haus existiert
   (leeres Override ersetzt vollständig, auch ins Leere).
4. **Deaktivierte Regeln nicht mitmigrieren.** `_trip_channel_inputs:89` filtert auf
   `r.enabled`. Wanderten die Kanäle einer abgeschalteten Regel mit, würde eine heute
   wirkungslose Einschränkung aktiv = stille Verengung. Nur `enabled`-Regeln migrieren,
   als AC festhalten.

## ADR-0077 Punkt 3 — Präzisierung, nicht stille Abweichung

Punkt 3 ordnet die verbindliche Schlüsselmenge **S3** zu. S2 legt nun eine Lesart fest.
CLAUDE.md ist hart: „Eine dokumentierte Entscheidung wird nie still rückgängig gemacht."

Der tragfähige Schnitt: **S2 legt das LESE-Vokabular fest** (Katalog-IDs, wählbarkeits-
disambiguiert, unbekannt ⇒ erbt, **keine Validierung**); die **verbindliche, validierte**
Menge samt Editor-Anzeige und Bestandsdaten-Prüfung bleibt **S3**.

Entscheidend entschärfend, und messbelegt: **im neuen Feld existieren heute keine
Bestandsdaten.** `alert_metric_channels` wird außerhalb der Go-Handler-Tests nirgends
geschrieben — kein Frontend, kein Service, kein Migrationslauf (Fundstellen-Sweep über
`src/ api/ internal/ cmd/ frontend/src/`). Die Punkt-3-Begründung („würde Bestandsdaten
mit `snow_line` brechen") betraf die **Regel**-Metriken, nicht das neue Feld. Die
Schlüsselmengen-Entscheidung ist damit frei von Alt-Zwängen.

`/30` muss entscheiden, ob das eine ADR-0077-**Ergänzung** braucht (Punkt 3 um den Satz
„das Lese-Vokabular legt S2 fest, die verbindliche Menge S3") — meine Empfehlung: ja, als
Ergänzung am bestehenden ADR, **kein** neues ADR, weil die Entscheidung nicht umgedreht
sondern geschärft wird. `tests/test_adr_index_drift.py` bleibt davon unberührt (kein
Status-Wechsel).

## 🔴 Die Asymmetrie der zwei Aufrufstellen (nachgemessen)

Die beiden metrikbehafteten Stellen sind **nicht** symmetrisch, und ein „Metriken als
Parameter durchreichen" funktioniert nur auf einer von ihnen:

| | Trip | Ortsvergleich |
|---|---|---|
| Kanal-Satz entsteht | `trip_alert.py:2509`, **mit** `changes` in der Hand | `compare_alert.py:186` (über `_build_eval_config`, Auflöser-Aufruf `:601`) |
| Metriken erstmals verfügbar | dieselbe Stelle | erst `:287` (`t["changes"]`), nach `_detect_triggered_locations` (`:256`) |
| Folge | ein Parameter genügt | `:601` **kann** die Metriken nicht tragen |

`AlertEvaluationConfig.channels` ist ein **Feld**, das einmal je Preset entsteht und
direkt zum Versand durchgereicht wird (`:285` → `:298` → `:333-335`) — zum Zeitpunkt
seiner Entstehung ist noch nicht bekannt, welche Metriken auslösen.

**Der symmetrische Schnitt:** der metrik-bewusste Aufruf gehört auf der Vergleichs-Seite
in die bestehende **Ortsschleife** (`:286-293`), wo `t["changes"]` vorliegt — also
derselbe geteilte Auflöser, nur **je Ort** statt je Alarm. Das ist die Parität zu
`trip_alert.py:2509` (dort: je Alarm) und braucht **keine** zweite Kanal-Prüfkette
(ADR-0021 gewahrt). `:601` bleibt unverändert und liefert weiter den preset-weiten Satz —
er ist der Rückfall und der Startwert.

**Implementierungs-Falle an derselben Stelle:** `ids_by_channel` wird bei `:285` aus
`config.channels` vorbelegt und bei `:293` per `ids_by_channel[c]` beschrieben. Ein
Metrik-Eintrag kann — nach dem Hausmuster der Regel-Kanäle, die heute auch nicht
geschnitten werden — einen Kanal **hinzufügen**, der nicht in `config.channels` steht.
Dann wirft `:293` einen `KeyError` und der ganze Vergleichs-Alarm fällt aus. Die
Vorbelegung muss die Vereinigung über alle Orte abdecken (oder auf ein
`defaultdict(list)` wechseln). Gehört als eigener RED-Test in `/40`.

## Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | Rückwärts-Lookup `summary_field → Kandidaten` als **eine** Primitive; der Katalog besitzt `summary_fields` bereits. Plus wählbarkeits-Tie-Break. |
| `src/services/alert_channels.py` | MODIFY | 5. Eingabe `metric_channel_sets` im reinen Kern (Schleifen-Form aus `:56-60`), Adapter lesen `alert_metric_channels`, Leer-Rückfall-Guard, `metrics=None`-Default im Dispatcher |
| `src/services/trip_alert.py` | MODIFY | nur `:2509` (`_send_alert`) reicht die Metriken der `changes` durch; `:552` bleibt unberührt (reine Protokoll-Zierde) |
| `src/services/compare_alert.py` | MODIFY | **nicht** `:601` — dort sind die Metriken noch unbekannt. Der metrik-bewusste Aufruf gehört in die Ortsschleife `:286-293` (s. „Die Asymmetrie…") |
| `src/app/loader.py` | MODIFY | Migration `alert_rules[].channels` → `alert_metric_channels`, Read-Modify-Write nach Muster `:741-753` |
| `src/output/renderers/alert/project.py` | MODIFY | `_resolve_metric_id` + `_resolve_corridor_metric_id` delegieren auf die Katalog-Primitive (Verbot einer zweiten Kopie, #1481) — **löst das Renderer-Mail-Gate aus**, s. unten |
| `docs/reference/api_contract.md` | MODIFY | Semantik-Nachtrag am schon dokumentierten Feld (`:925-940`) — `tests/test_api_contract_drift.py` |
| `docs/adr/0077-*.md` | MODIFY | Ergänzung an Punkt 3 (Lese- vs. verbindliches Vokabular) |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | S2-ACs |
| `tests/tdd/test_alert_metric_channel_reader.py` | CREATE | Leser, Tie-Break, Leer-Rückfall, metrikfreie Immunität, Trip/Vergleich-Parität |
| `tests/tdd/test_alert_metric_channel_migration.py` | CREATE | vier Migrations-Fallen + Roundtrip |

**Nicht angefasst** (Scheibenschnitt): alles unter `frontend/`, `internal/`, `cmd/`
(S1 ist fertig, S3 ist Frontend), `has_active_rules`, `alert_rules` als Entität (S4),
`split_by_threshold` (die Union braucht keine Partitionsstelle — der in der Kontext-Phase
erwogene Ansatzpunkt entfällt mit Entwurf A).

## Scope Assessment

- Dateien: 6 produktiv + 2 Test + 3 Doku
- Geschätzte LoC: **+180 / −15** produktiv — **eng am 250er-Limit**. Vor `/40`
  `workflow.py status` lesen; wird es knapp, `workflow.py set-field loc_limit_override 500`
  statt die RED-Abdeckung zu verengen.
- Risiko: **MITTEL-HOCH**

Was das Risiko trägt: (1) die Verhaltensänderung an Bestandsdaten (M1, PO-freigabepflichtig),
(2) Persistenz-Migration ⇒ Pre-Snapshot-Hook `data_schema_backup.py`, Read-Modify-Write
zwingend (BUG-DATALOSS-GR221 #102), (3) die Fläche ist der Alarm-Versand — ein Fehler
heißt „Alarm erreicht niemanden".

(4) die Asymmetrie der zwei Aufrufstellen — auf der Vergleichs-Seite wandert die
Auflösung in die Ortsschleife, dort liegt die `KeyError`-Falle bei `:293`.

Was das Risiko senkt: der neue Arm ist eine **Um-Schlüsselung einer vorhandenen
Schleife**, kein neuer Algorithmus; die metrikfreien Pfade sind **bauartbedingt** immun;
AC-1-Parität über 16 Kombinationen ist schon testbewacht
(`tests/tdd/test_alert_channel_resolution_parity.py:225`) und fängt ein Auseinanderlaufen
von Trip und Vergleich sofort.

## Technical Approach

Formulierungsvorlagen für `/30` — **noch keine ACs**, aber so gemessen, dass sie welche
werden können. Jede nennt die Stelle, an der sie **wirkt**, nicht die, an der der Code steht:

1. **Union je Metrik, dreiarmig, jeder Arm je Metrik aufgelöst.** Ein Alarm über
   Metriken M erreicht
   `⋃_{m∈M} (Eintrag(m) · sonst Kanäle der aktiven Regel(n) DIESER Metrik · sonst geerbt)`.
   Ausdrücklich **nicht** „sonst das heutige preset-weite Ergebnis" — das hob die
   Verengung wieder auf. Gemessen am Rückgabewert des Kerns **und** an
   `trip_alert.py:2509` / `compare_alert.py:335` — ein Test, der bei `trip_alert.py:552`
   grün wird, beweist über den Trip-Versand **nichts** (dort ist das Ergebnis reine
   Protokoll-Zierde, der Versand löst bei `:2509` unabhängig neu auf).
2. **Der Metrik-Arm allein bringt eine nicht-leere Menge nicht auf leer.** Prüfung
   **vor** den Tier-Gates; ein explizit leeres `override` bleibt leer
   (`alert_channels.py:49-50`, bewacht bei
   `test_alert_channel_resolution_parity.py:166`), und ein Tier-Gate darf weiterhin auf
   leer führen. Gemessen an den beiden Versandstellen, für alle vier Kanäle (#1701,
   Paritäts-Audit #1533).
3. **Metrikfreie Alarme bleiben byte-gleich.** Radar, amtliche Warnungen und die vier
   Protokoll-Pfade liefern dieselbe Kanalmenge wie vor der Scheibe — und zwar weil sie
   den Parameter nicht übergeben. **Mutations-Gegenprobe mit Vorbedingung:** Die Fixture
   MUSS eine Zuordnung für eine Metrik tragen, die im Radar-/amtlichen Alarm **nicht**
   vorkommt, und diese Zuordnung muss von der abo-weiten Menge abweichen. Sonst ist die
   Mutation (Metrik-Argument an einer Radar-Aufrufstelle ergänzen) bei leerem
   `alert_metric_channels` strukturell unbeobachtbar und bleibt grün.
4. **Ein Schlüssel, eine Übersetzung, zwei Flächen.** Derselbe Summary-Key ergibt in Trip
   und Vergleich denselben Kanal-Schlüssel; `temp_min_c` ⇒ `temperature` (wählbar), nie
   `temperature_cold`. Gemessen als Erweiterung der bestehenden 16er-Paritätsmatrix.
5. **Unauflösbarer Schlüssel erbt.** Unbekannter oder mehrdeutiger Summary-Key wirft
   nicht, sondern führt zum geerbten Satz.
6. **Migration verliert nichts und erfindet nichts.** Eins-zu-vielen wird ausgerollt,
   Kollisionen unionieren, leere Kanallisten erzeugen **keinen** Schlüssel, deaktivierte
   Regeln wandern **nicht** mit, und ein Trip ohne Regel-Kanäle bekommt kein Feld
   (`omitempty` bleibt wirksam). Roundtrip über Go-Handler **und** Python-Lader.
7. **Mandantentrennung.** Der neue Lesepfad reicht die echte `user_id` durch, nie
   `"default"`; mit **zwei** verschiedenen Nutzern getestet
   (`tests/test_user_id_default_guard.py`, ADR-0003).

## Dependencies

- **S1 (live, `dfc13d9d`)** liefert Feld, Persistenz und Merge-Kontrakt — Vorbedingung erfüllt.
- **Blockiert S3** (Editor-Spalte) per ADR-0077 Punkt 5.
- **Eingang für S4** (Rückbau `alert_rules`): erst wenn der Eintrags-Arm trägt, darf der
  mittlere Arm fallen.
- Grün bleiben müssen: `test_adr_index_drift.py`, `test_api_contract_drift.py`,
  `test_user_id_default_guard.py`, `test_router_user_id_required.py`,
  `test_alert_channel_resolution_parity.py`, `test_compare_alert_channels.py`.

### 🔴 Gate-Befund, der den Ablauf ändert

`src/output/renderers/alert/project.py` fällt unter das **Renderer-Mail-Gate**:
`renderer_mail_gate.py:45` (`src/output/renderers/alert/.*\.py$`) und `:56`
(`_RADAR_PATTERNS` = alle `alert/*.py` außer `official_alerts.py`). Ein Commit an dieser
Datei verlangt einen **frischen Radar-/Deviation-Alert-Mail-Nachweis**
(`radar_alert_mail_validator.py`) gegen eine **echt zugestellte Staging-Mail** — obwohl
die Änderung ein reiner Delegations-Refactor ohne Inhaltswirkung ist.

Zwei Wege, `/30` entscheidet:
- **(i) empfohlen:** Datei anfassen, Nachweis führen. Es ist der einzige Weg, der ohne
  zweite Kopie der Übersetzung auskommt (#1481, ADR-0021). Kosten: ein Staging-Mail-Lauf
  im `/60`/`/70`-Pfad, planbar.
- (ii) `project.py` in S2 unberührt lassen und die Katalog-Primitive nur vom neuen Leser
  nutzen. Spart den Nachweis, hinterlässt aber zwei Fassungen desselben
  Rückwärts-Lookups — genau die Wiederholungs-Klasse, die #1481 verbietet. Nur mit
  dokumentierter Begründung in der Spec und einem S4-Nachzug.

## Open Questions

Keine, die `/30` blockiert. Drei Punkte gehören ausdrücklich in die Spec, damit `/30` sie
nicht ungesehen erbt:

- [ ] **M1 gegen M2/M3** — die Verengung für Bestandsnutzer ist eine
      nutzer-sichtbare Verhaltensänderung und muss als deutsche AC in die PO-Freigabe.
      Empfehlung steht oben (M1).
- [ ] **Renderer-Gate-Weg (i) oder (ii)** — Empfehlung (i).
- [ ] **ADR-0077-Ergänzung an Punkt 3** ja/nein — Empfehlung: ja, Ergänzung am
      bestehenden ADR, kein neues.
