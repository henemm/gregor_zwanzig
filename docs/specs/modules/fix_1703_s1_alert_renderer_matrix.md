---
entity_id: fix_1703_s1_alert_renderer_matrix
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [metrics, alert-renderer, matrix-test, epic-1703, thunder, units]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 1. Deckt Flaeche 1 aus
     docs/reference/metric_output_matrix.md §4.1. Voraussetzung Scheibe 3
     (PR #1710) ist erledigt -- die Iterationsbasis _METRICS statt
     get_all_metrics() steht damit bereits. -->

# Alarm-Renderer × alle alarmfähigen Metriken (#1703 Scheibe 1)

## Approval

- [x] Approved — PO-Freigabe 2026-08-11 („go"), ACs auf Deutsch vorgelegt und bestätigt.
  Enthaltene Scope-Entscheidung: Gewitter-Prozentzeichen wird in dieser Scheibe
  mitrepariert (Variante B, s. AC-5).

## Purpose

Die vier Alarm-Renderer (`render_subject`/`render_email`/`render_telegram`/`render_sms`)
sind heute für **8 von 11** produktiv erreichbaren Alarm-Metriken ungeprüft: kein
einziger Test iteriert über den Katalog, und ein alarmfähiger Katalogeintrag ohne
Alarm-Ausgabe fällt nirgends auf. Diese Scheibe hängt eine Matrix-Achse in den
bestehenden, budgetierten Wächter `tests/tdd/test_channel_metric_matrix.py` (#1677 B) —
und repariert dabei einen gemessenen Widerspruch, der die sicherheitskritischste Größe
des Produkts betrifft (PO-Entscheidung 2026-08-11, s. AC-5).

## Source

- **File:** `src/output/renderers/alert/render.py` (Prüfling), `tests/tdd/test_channel_metric_matrix.py` (Wächter)
- **Identifier:** `render_subject:292` · `render_email:448` · `render_telegram:549` · `render_sms:617` · `_unit_display:75` · `_HANDLED_UNITS:35`

Schicht: **Python-Core** (`src/output/renderers/`, `src/services/`). Keine Go-, keine
Frontend-Berührung.

## Estimated Scope

- **LoC:** ~195 (+192 Test/Doku, −3 Produktivcode)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/app/metric_catalog.py` | Katalog | `get_alert_label()`, `get_sms_code()`, `format_metric_value()`, `_METRICS` |
| `src/services/weather_change_detection.py:82-99` | Produktivmodul | `_ALERT_METRIC_TO_CATALOG_ID` — **die Soll-Mengen-Quelle** |
| `src/output/renderers/alert/model.py` | Datentypen | `AlertEvent`, `AlertMessage` |
| `tests/tdd/test_channel_metric_matrix.py` | Wächter (Bestand) | Zieldatei, wird erweitert |
| `tests/helpers/hourly_columns.py` | Vorbild | Muster „Soll rechnen, nicht tippen" |

## Implementation Details

### Die Soll-Menge (gemessen 2026-08-11, nicht getippt)

```python
# Quelle: das Produktivmodul selbst, nicht der Test.
from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID
soll = {cid for ids in _ALERT_METRIC_TO_CATALOG_ID.values() for cid in ids}
# -> 11 IDs: cape, freezing_level, fresh_snow, gust, precipitation,
#            snowfall_limit, temperature, temperature_cold, thunder,
#            visibility, wind
```

Warum **11** und nicht die 15 Metriken mit `alert_label`/`alert_metrics`: `humidity` und
`rain_probability` sind `is_precursor=True` (Vorboten-Größen, laut Katalog-Docstring von
`from_display_config`/`from_alert_rules` ignoriert); `uv_index` und `snow_depth` tragen
zwar ein `alert_label`, haben aber weder `alert_metrics` noch einen Eintrag im Mapping —
sie können strukturell nie ein `AlertEvent` erzeugen. Ein Wächter, der sie mitprüfte,
müsste sie sofort wieder ausnehmen; ein Wächter, der über `_ALERT_METRIC_TO_CATALOG_ID`
rechnet, braucht **gar keine Ausnahmeliste**.

### Der Gewitter-Fix (AC-5)

```python
# render.py:75-86 -- ENTFAELLT ersatzlos:
def _unit_display(e: AlertEvent) -> str:
    if e.metric_id == "thunder":
        return "%"          # <- diese zwei Zeilen fallen
    return get_metric(e.metric_id).unit
```

`thunder` trägt `alert_metrics={"max": "thunder_level"}` (`metric_catalog.py:340`) — der
Alarmwert ist eine **Stufe** (0–3), keine Prozentzahl. Der Sonderfall stammt aus einer
Design-Vorlage zu #978 und wurde von PO-Entscheidung #1585 (2026-08-07, „genau zwei
Gewitter-Metriken: `thunder` = Stärke, `thunder_probability` = Wahrscheinlichkeit")
überholt. Nach dem Wegfall liefert `_unit_display()` für `thunder` `""` — identisch zu
dem, was der Einzel-Event-Pfad (`render.py:47`, `:365`) ohnehin schon liest.

### Zwei Assertion-Familien, nicht eine

`render_subject`/`render_email`/`render_telegram` beziehen die Beschriftung aus
`get_alert_label()`. `render_sms` kennt weder Beschriftung noch Einheit, nur
`get_sms_code()`. Die SMS-Prüfung braucht einen **token-grenzen-bewussten** Vergleich:
`N` (temperature_cold) ist Wortanfang von `NL` (freezing_level) und `NS` (fresh_snow) —
eine reine Teilstring-Suche schlüge falsch an. Vorbild für die Token-Grammatik:
`test_channel_metric_matrix.py:194-207`; das Token-Format des Alarm-Pfads ist
`{vorzeichen}{kürzel}{wert}[@HH]` (`render.py:596-597`).

### Ausnahme-Muster

Nach `_NIGHT_SCALAR_IDS` (`channel_layout.py:85-89` ↔ `test_channel_metric_matrix.py:57-60`):
**kein `pytest.skip`**, sondern ein invertierter Assertion-Zweig in derselben
parametrisierten Funktion.

## Expected Behavior

- **Input:** ein `AlertMessage` mit genau einem `AlertEvent` je Katalog-Metrik aus der
  gerechneten Soll-Menge (bzw. zwei Events für die Bündel-Prüfung)
- **Output:** in Betreff, E-Mail und Telegram erscheint die Beschriftung der Größe; in
  der Kurznachricht ihr Kürzel als abgegrenzter Token
- **Side effects:** keine. Der Wächter rendert nur, er versendet nichts.

## Acceptance Criteria

- **AC-1:** Gegeben ein Alarm zu genau einer der 11 alarmfähigen Wettergrößen, wenn
  Betreff, E-Mail und Telegram-Nachricht erzeugt werden, dann nennt **jede** der drei
  Ausgaben die Größe mit der Beschriftung, die der Katalog für sie führt.
  - Test: parametrisiert über die gerechnete Soll-Menge; je Größe werden die drei echten
    Renderer aufgerufen und auf die Katalog-Beschriftung geprüft — die Beschriftung wird
    aus `get_alert_label()` gelesen, nie im Test getippt.

- **AC-2:** Gegeben derselbe Alarm, wenn die Kurznachricht erzeugt wird, dann enthält
  sie das Kürzel dieser Größe als eigenständigen Token — und **nicht** bloß als
  zufälligen Wortanfang eines fremden Kürzels.
  - Test: parametrisiert über dieselbe Soll-Menge, mit Token-Grammatik statt
    Teilstring-Suche. Gegenprobe: für das Kürzel `N` darf ein Alarm, der nur
    Nullgradgrenze (`NL`) oder Neuschnee (`NS`) enthält, **keinen** Treffer liefern.

- **AC-3:** Gegeben der Wächter läuft, wenn die Menge der zu prüfenden Größen bestimmt
  wird, dann stammt sie ausschließlich aus dem Produktivmodul
  (`_ALERT_METRIC_TO_CATALOG_ID`) und ist niemals im Test aufgezählt.
  - Test: die Soll-Menge wird im Test aus dem Produktivmodul gelesen; ein
    Plausibilitäts-Wächter schlägt fehl, wenn sie leer ist oder unter 8 Einträge fällt
    (Vakuum-Schutz nach dem Muster `hourly_columns.py:130-158`) — ein Wächter, der über
    eine leere Menge iteriert, ist immer grün und bewacht nichts.

- **AC-4:** Gegeben die Einheiten-Liste des Alarm-Renderers (`_HANDLED_UNITS`), wenn sie
  gegen das tatsächliche Formatierungsverhalten des Katalogs gehalten wird, dann stimmen
  beide für jede im Katalog vorkommende Einheit überein.
  - Test: für jede Katalog-Einheit wird gemessen, ob die Katalog-Formatierung die
    Einheit tatsächlich anhängt; das Ergebnis muss der Zugehörigkeit zur Liste
    entsprechen — in beide Richtungen. Damit fällt auf, wenn eine der beiden Listen
    erweitert wird und die andere zurückbleibt (heute gemessen deckungsgleich).

- **AC-5:** Gegeben ein Gewitter-Alarm, wenn irgendeine der vier Ausgaben erzeugt wird,
  dann erscheint der Gewitter-Wert **ohne** Prozentzeichen — und zwar unabhängig davon,
  ob der Alarm allein oder gebündelt mit anderen Größen auftritt.
  - Test: Gewitter-Alarm einzeln **und** gebündelt mit einer zweiten Größe rendern; in
    beiden Fällen darf an den Gewitter-Wert kein Prozentzeichen angehängt sein. Heute
    schlägt der Bündel-Fall fehl (gemessen: `Gewitter 10→20%`) — das ist der einzige
    rote Anteil dieser Scheibe.

- **AC-6:** Gegeben der Gewitter-Fix ist eingespielt, wenn Alarme zu den übrigen zehn
  Größen erzeugt werden, dann bleiben ihre Ausgaben unverändert.
  - Test: die Einheiten-Darstellung der anderen zehn Größen wird im gebündelten Fall
    geprüft (Prozentzeichen bleibt bei Feuchte/Regenwahrscheinlichkeit erhalten, wo es
    hingehört) — der Fix darf nicht über sein Ziel hinausschießen.

- **AC-7:** Gegeben zwei Größen teilen sich dieselbe Beschriftung, wenn der Wächter über
  sie läuft, dann ist diese Doppeldeutigkeit im Wächter ausdrücklich benannt statt
  stillschweigend übergangen.
  - Test: für `temperature` und `temperature_cold` (beide „Temp") greift ein eigener,
    umgekehrter Prüfzweig, der festhält, dass Betreff/E-Mail/Telegram die beiden **nicht**
    unterscheiden können und allein das Kurznachrichten-Kürzel (`D` gegen `N`) sie trennt.
    Kein Überspringen — der Zweig prüft, was dort tatsächlich gilt.

## Known Limitations

1. **Der Wertebereichs-Alarm (`CorridorEvent`) bleibt außen vor.** Er trägt zwar eine
   Metrik-Kennung, ist aber ein toter Pfad: `evaluate_corridor_thresholds()`
   (`corridor_threshold.py:68`) hat keinen Aufrufer in `src/`/`api/`, und der einzige
   produktive `_send_alert()` (`trip_alert.py:296`) übergibt `corridor_hits` nicht.
   Entsprechend baut keine Testdatei im Repo je ein solches Ereignis. Ein Wächter über
   einen toten Pfad bewacht nichts.
2. **Der Radar-Beginn-Alarm (`OnsetEvent`) ist strukturell metrik-los.** Die Datenstruktur
   hat kein `metric_id`-Feld (`model.py:30-46`), alle drei produktiven Erzeuger setzen
   keinen Katalogbezug, und der Renderer verzweigt binär über `is_convective` mit festen
   Wörtern (`render.py:146/225/276/285`). Er ist kein Punkt in einer Metrik×Kanal-Matrix.
3. **Die Tausenderpunkt-Abweichung wird nicht repariert.** Gemessen liefert der
   Einzel-Alarm `1500 J/kg`, der Bündel-Alarm `1.500` für denselben Wert
   (`render.py:51` hat keine Tausenderlogik, `:66-72` schon). Produktiv praktisch
   unerreichbar: die betroffenen Größen erreichen entweder den Alarmweg nicht
   (`cape` im Trip-Pfad, `uv_index`, `snow_depth`) oder haben nie Werte über 1000
   (`thunder` = Stufe 0–3, `fresh_snow` bräuchte 10 m Neuschnee). → Sammel-Eintrag #1199.
4. **`cape` ist nur im Trip-Pfad sicher blockiert.** Im Ortsvergleich gibt
   `_display_config_from_active_metrics()` für nicht-migrierte Alt-Vorlagen `None`
   zurück (`compare_alert.py:500-501`), und der Aktivitäts-Filter läuft nur bei
   gesetzter Konfiguration (`alert_preset.py:278`); `_STANDARD_METRIC_LEVELS` enthält
   `cape` (`compare_alert.py:44`). Ob eine solche Alt-Vorlage produktiv existiert, ist
   **nicht gemessen** — lokal liegt keine Vergleichs-Datei vor. → Sammel-Eintrag #1199,
   getrennt von dieser Scheibe.
5. **Der Wächter prüft Anwesenheit, nicht Richtigkeit des Werts.** Dass die Beschriftung
   erscheint, beweist nicht, dass der Zahlenwert stimmt. Zellwert-Vollständigkeit ist
   ausdrücklich Scheibe 5 des Epics.

## Prüfhinweis für den Adversary

**Die Mutations-Gegenprobe hat hier eine bekannte blinde Stelle.** `temperature` und
`temperature_cold` tragen dieselbe Beschriftung („Temp"). Eine Mutation, die die
Metrik-Kennung zwischen diesen beiden vertauscht, lässt Betreff, E-Mail und Telegram
**byte-identisch** — nur die Kurznachricht ändert sich (`D` gegen `N`). Wer nur die drei
erstgenannten Kanäle mutiert und grün bleibt, hat **nicht** bewiesen, dass der Wächter
wirkt. Belastbare Mutationen für diese Scheibe:

- `_unit_display()`s `thunder`-Zweig wieder einsetzen → AC-5 muss rot werden
- eine ID aus der Soll-Menge entfernen → AC-3s Vakuum-Schutz muss anschlagen
- eine Einheit zu `_HANDLED_UNITS` hinzufügen, die der Katalog nicht anhängt (z. B. `cm`)
  → AC-4 muss rot werden
- in der SMS-Prüfung die Token-Grammatik durch eine reine Teilstring-Suche ersetzen →
  AC-2s Gegenprobe (`N` gegen `NL`/`NS`) muss rot werden

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Register, kein neues Pflicht-Gate — die Achse erweitert das
  bereits budgetierte Gate #1677 B (Option C aus `metric_output_matrix.md` §5). Der
  Gewitter-Fix vollzieht eine bestehende PO-Entscheidung (#1585) nach, statt eine neue
  zu treffen.

## Definition of Done

Zusätzlich zu den ACs: die Zelle „Fläche 1" in `docs/reference/metric_output_matrix.md`
§4.1 wird von „unbewacht" auf den neuen Wächter umgetragen, und §6 „Scheibe 1" auf
erledigt gesetzt — das Dokument ist laut Epic-Leitplanke Teil der Definition of Done
jeder Scheibe.

## Changelog

- 2026-08-11: Initial spec created (Epic #1703 Scheibe 1)
