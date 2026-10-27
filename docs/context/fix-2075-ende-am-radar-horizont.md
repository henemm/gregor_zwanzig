# Context: fix-2075-ende-am-radar-horizont

Issue: [#2075](https://github.com/henemm/gregor_zwanzig/issues/2075) — `priority:high`, `bug`,
Milestone „Tour KHW 2026-08". Basis-Stand: `1e0ee151`.

## Request Summary

Endet der Regen innerhalb der letzten Deckungsspanne (15 Min) vor dem Ende der Radar-Reichweite,
meldet der Dienst `Regen mindestens bis <Horizont>` statt des echten, vom Radar belegten Endes —
bis zu 14 Minuten Regen zu viel, und eine belegte Aussage wird als bloße Untergrenze ausgegeben.
Gemessen auf Staging bei der Verifikation von #2051 Scheibe 1.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py:325` | **Fundstelle.** `coverage_end = min(ts + _MAX_FRAME_COVERAGE, horizon)` — der direkt darunter ermittelte `next_ts` (Z. 326-327) fließt nicht ein |
| `src/services/radar_service.py:233-276` | `_accumulate_precip_mm` — das Geschwister, das die Nachbar-Deckung **korrekt** rechnet (`min(next_ts_full, ts + _MAX_FRAME_COVERAGE, end)`, Z. 272) |
| `src/services/radar_service.py:352-382` | `_laufendes_frame` (#2050 S2b) — drittes Geschwister, rechnet den Nachbarn ebenfalls **korrekt** ein (Z. 377-379) |
| `src/services/radar_service.py:1011-1037` | Aufrufstellen: Onset-Zweig (#2051 S1) **und** `already_running`-Zweig (#2050 S2b, seit `ade992df` live) |
| `src/output/renderers/alert/render.py`, `.../project.py`, `.../model.py` | Textkonsumenten von `event_end_minutes` / `event_ongoing_beyond_horizon` (Langform + Kurzform) |
| `src/output/renderers/email/starkregen_hint.py` | Briefing-Kurzfristhinweis |
| `src/services/validator_render_service.py`, `src/services/trip_alert.py` | Weitere Konsumenten der beiden Felder |

## Existing Patterns

- **Deckung je Frame** ist im Modul dreimal umgesetzt und soll überall gleich lauten:
  `min(eigener nächster Nachbar, +_MAX_FRAME_COVERAGE, Fensterende)`. Zwei von drei Stellen tun das;
  `_derive_wet_block_end` lässt den Nachbarn aus.
- Keine neue Toleranzzahl einführen — beide Konstanten (`_MAX_FRAME_COVERAGE = 15 min`,
  `_DRY_THRESHOLD_MM_H = 0.1`) sind gesetzt und durch Tests fixiert
  (`test_nowcast_blockende_datenluecke.py::test_deckungskonstante_ist_fuenfzehn_minuten`).
- Tests lösen ihren Prüfling relativ zur eigenen Testdatei auf
  (`test_prueling_stammt_aus_diesem_arbeitsbaum` in allen Blockende-Tests).

## Dependencies

- **Upstream:** `frames` + `all_ts_sorted` aus `_derive_result`; die Konstanten oben.
- **Downstream:** `NowcastResult.event_end_minutes` / `.event_ongoing_beyond_horizon` → alle vier
  Kanäle (E-Mail-Langform, Telegram, SMS-Kurzform ` >@HH:MM`, Premium-SMS), Briefing-Hinweis,
  Kommando-Antwort, Validator-Render-Service.
- **Querschnitt:** der `already_running`-Zweig aus **#2050 S2b** ruft denselben Helfer auf und
  nimmt `max(_end_ts, _laufend[3])`. Eine Änderung am Helfer wirkt dort mit.

## Existing Specs

- `docs/specs/modules/feat_2051_s1_dauer_und_ende.md` — **Implementation Details** schreiben die
  Nachbar-Deckung ausdrücklich vor: „`min(nächster Frame, +_MAX_FRAME_COVERAGE, Horizontende)` —
  dieselbe Nachbar-Deckungslogik wie in `_accumulate_precip_mm`". Der Code weicht davon ab.
  ⇒ **Es ist ein Umsetzungsfehler gegen die eigene Spec, keine offene Entwurfsfrage.**
- `docs/specs/modules/alarm_szenario_laufendes_ereignis.md` — #2050 S2b, nutzt denselben Helfer.

## Bestehende Wächter (Regressionsfläche)

| Test | Deckt |
|---|---|
| `tests/tdd/test_nowcast_blockende_ableitung.py` | AC-1 (Ende am letzten nassen Frame), AC-2 (zwei Blöcke verschmelzen nicht) |
| `tests/tdd/test_nowcast_blockende_datenluecke.py` | AC-3 (Lücke ≤ Deckung), AC-4 (Lücke > Deckung → Deckungsgrenze) |
| `tests/tdd/test_nowcast_blockende_horizont_waechter.py` | AC-5 (a–d): Block bis zum Horizont nass · abgeschnittene Zeitreihe · Untergrenzen-Text in E-Mail, SMS, Briefing |
| `tests/tdd/test_nowcast_blockende_tagesfenster.py`, `..._tagesversatz.py` | Tagesfenster/Datumsversatz |
| `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` | #2050 S2b — `already_running`-Zweig über denselben Helfer |

## Risks & Considerations

1. **Der Ticket-Vorschlag (`coverage_end = min(coverage_end, next_ts)`) hält der Gegenprobe stand.**
   Durchgerechnet gegen AC-5: bei einer bis zum Horizont nassen Reihe ist `next_ts` entweder
   ≥ `horizon` oder `None` — in beiden Fällen bleibt `coverage_end == horizon`, der Wächter-Zweig
   greift unverändert. Auch AC-3/AC-4 bleiben rechnerisch gleich. Das ist eine Herleitung, kein
   Nachweis — die Analyse muss sie am laufenden Code messen.
2. **#2050 S2b ist die eigentliche Regressionsfläche**, nicht #2051. Im `already_running`-Zweig kann
   der Block künftig vor dem Horizont enden, wo er bisher immer den Horizont zurückgab.
   Die dortige Konvention „nenne die **Deckungsgrenze** des letzten Frames, nie dessen Zeitstempel"
   muss erhalten bleiben (sonst läge das gemeldete Ende in der Vergangenheit).
3. **Die AC-Lücke ist der eigentliche Befund:** AC-1 prüft ein Ende *deutlich vor* dem Horizont,
   AC-5 eine Reihe, die *bis zum* Horizont nass bleibt. Die Zone dazwischen — Ende zwischen
   `horizon - 15 min` und `horizon` — kommt in keinem der 20 Kriterien vor. Der neue Wächter muss
   **diese Zone** abdecken (Ende bei `horizon - 14min` … `horizon - 2min`), nicht nur den einen
   gemeldeten Zeitpunkt.
4. **Wortlaut ist entschieden und nicht neu vorzulegen:** `letzter Regen gegen HH:MM` /
   `Regen mindestens bis HH:MM`, Kurzform ` >@HH:MM`; die SMS-Kurzform ist **englisch**.
   Diese Arbeit ändert **keinen** Text — nur, welcher der beiden bestehenden Texte gewählt wird.
5. **Keine Sicherheitsrichtung:** der Fehler übertreibt die Regendauer, verharmlost sie nie.
   Der Fix dreht die Richtung nicht um — er darf kein Ende behaupten, das das Radar nicht belegt.
6. **Parallel-Session-Kopplung:** #2050 S2b ist seit `ade992df` in `main`, #2073 S1 seit `1e0ee151`.
   Beide Nachbar-Sessions haben #2075 ausdrücklich freigegeben. `render.py` ist wieder frei.

---

## Analysis

### Type

**Bug** — Umsetzungsfehler gegen die eigene Spec (`feat_2051_s1_dauer_und_ende.md`,
Implementation Details: `min(nächster Frame, +_MAX_FRAME_COVERAGE, Horizontende)`).
Keine Entwurfsfrage, kein neuer Text, keine neue Toleranzzahl.

### Gemessen, nicht hergeleitet

Alle Werte am laufenden Code im Arbeitsbaum gemessen (`now=10:35`, `horizon=13:35`,
Beginn 10:55, 2-Min-Raster). T = Zeitstempel des letzten nassen Frames.

**Die fehlerhafte Zone:**

| T | IST | Fix-1 (Ticket-Vorschlag) | Fix-2 (empfohlen) |
|---|---|---|---|
| 13:33 | `13:35 / ongoing` | `13:35 / ongoing` ❌ | **`13:33 / Ende`** ✅ |
| 13:31 … 13:21 | `13:35 / ongoing` ❌ | `T / Ende` ✅ | `T / Ende` ✅ |
| 13:19 und früher | `T / Ende` ✅ | unverändert | unverändert |

Die Zone beginnt exakt bei `T = 13:21`; ab dort behauptet der Dienst bis zu **14 Minuten**
Regen zu viel und wählt die Untergrenzen-Form, obwohl das Radar ein echtes Ende belegt.

### Befund: der Fix aus dem Ticket schließt die Zone nicht ganz

Der im Ticket vorgeschlagene Einzeiler (`coverage_end = min(coverage_end, next_ts)`) repariert
**13:31 bis 13:21**, lässt aber **T = 13:33 unrepariert**. Grund: der nächste Frame liegt dann
exakt **auf** dem Horizont, `coverage_end` bleibt damit `== horizon`, und der Zweig
`if coverage_end >= horizon: return horizon, True` greift, **bevor** der trockene Frame bei 13:35
ausgewertet werden kann.

Nötig ist deshalb ein zweiter Halbsatz: der Horizont-Zweig darf nur greifen, wenn **kein Frame
innerhalb des Fensters mehr folgt**.

```python
if next_ts is not None:
    coverage_end = min(coverage_end, next_ts)
...
if coverage_end >= horizon and (next_ts is None or next_ts > horizon):
    return horizon, True
```

Das ist genau das, was die Begründung des Tickets fordert („danach greift der Horizont-Zweig nur
noch, wenn wirklich kein Frame innerhalb des Horizonts mehr folgt") — der dort vorgeschlagene
Code leistet es nur nicht vollständig.

### Gegenprobe: Fix-2 verändert keinen Bestandsfall

Alle sechs gemessen, IST und Fix-2 identisch:

| Fall | Ergebnis (beide) |
|---|---|
| Durchgehend nass bis zum Horizont (AC-5 a) | `13:35 / ongoing` |
| Abgeschnittene Zeitreihe (AC-5 b) | `13:14 / ongoing` |
| Datenlücke 25 Min (AC-4) | Deckungsgrenze, kein ongoing |
| Datenlücke 10 Min (AC-3) | Block läuft weiter |
| Zwei getrennte Blöcke (AC-2) | verschmelzen nicht |
| Nächster Frame **jenseits** des Horizonts (13:40) | `13:35 / ongoing` |
| Nasser Frame **exakt auf** dem Horizont | `13:35 / ongoing` (kippt nicht) |

**Basislinie:** die fünf Blockende-Testdateien laufen im IST-Zustand mit **25 grün, 0 rot**.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/radar_service.py` | MODIFY | `_derive_wet_block_end`: Nachbar in die Deckungsgrenze einrechnen, Horizont-Zweig an „kein Folge-Frame im Fenster" binden (~3 LoC) |
| `tests/tdd/test_nowcast_blockende_zone_vor_horizont.py` | CREATE | Wächter über die **ganze** Zone `horizon−14min … horizon−2min`, inklusive des Falls „Trockenframe exakt auf dem Horizont" |

### Scope Assessment

- Dateien: 2 (1 MODIFY, 1 CREATE)
- Geschätzte LoC: +~90 / −2 (davon ~85 Test)
- Risiko: **MEDIUM** — Kernpfad des Alarm-Inhalts in allen vier Kanälen, aber eng begrenzte
  Änderung mit gemessener Nicht-Wirkung auf alle Bestandsfälle

### Technical Approach

Die Deckungsrechnung an die beiden funktionierenden Geschwister (`_accumulate_precip_mm`,
`_laufendes_frame`) angleichen — kein neuer Mechanismus, keine neue Zahl. Der Wächter-Test muss
die **Zone** abdecken, nicht den einzelnen gemeldeten Zeitpunkt: genau daran ist #2051 S1
gescheitert (AC-1 prüft weit vor dem Horizont, AC-5 direkt am Horizont, die Fläche dazwischen kam
in keinem der 20 Kriterien vor).

### Regressionsfläche (kartiert)

- **Zwei Aufrufer:** der Onset-Zweig (#2051 S1) und der `already_running`-Zweig (#2050 S2b).
  Letzterer maximiert das Ergebnis gegen die Deckungsgrenze des laufenden Frames
  (`max(_end_ts, _laufend[3])`, `radar_service.py:1034`) — damit nie ein Ende in der Vergangenheit
  genannt wird.
- **Die Text-Weiche sitzt an genau zwei Stellen:** `alert/render.py:580` (Langform) und
  `alert/render.py:822` (Kurzform); beide entscheiden allein an `event_ongoing_beyond_horizon`.
  Sieben Textstellen hängen daran, alle über `event_end_display()` (`alert/project.py:37-67`).
- **#2050 S2b ist nachgerechnet NICHT betroffen.** Erste Vermutung war, dessen AC-5 (Lage B,
  „läuft ohne Ende") hänge am `(horizon, True)`-Rückgabepfad. Am Fixture nachgerechnet stimmt das
  nicht: alle drei Lagen (A/B/C) haben denselben 15-Min-Raster mit dem letzten Frame 37 Minuten
  **vor** dem Horizont, und im offenen Intervall `(Horizont−15 min, Horizont]` liegt in keiner Lage
  ein Frame. Lage B verlässt die Funktion deshalb über den Zweig **`next_ts is None`**
  (`return coverage_end, True`, 14:45 lokal = Deckungsgrenze), nicht über den Horizont-Zweig — und
  läuft zudem über den **Onset**-Zweig, nicht über `already_running`. Beide Zweige lässt der Fix
  unberührt. Lage C (der einzige echte `already_running`-Fall) endet am Trockenframe, ebenfalls
  unberührt.
- **Nebenbefund (kein eigenes Issue, → #1199):** Die Konvention „im Laufend-Fall die Deckungsgrenze
  nennen, nie den Frame-Zeitstempel" steht **nur** in einem Code-Kommentar
  (`radar_service.py:1020-1030`) und im Test-Docstring von AC-4b — die Spec
  `alarm_szenario_laufendes_ereignis.md` beschreibt an dieser Stelle noch den verworfenen
  Feld-Satz (`running_until_minutes`). Für #2075 genügt der Code-Anker; die Spec-Nachführung
  gehört zu #2050.

### Open Questions

Keine. Wortlaut, Kanalreichweite und die Untergrenzen-Konvention sind entschieden
(PO-Entscheid 2026-08-22); diese Arbeit ändert keinen Text, nur die Wahl zwischen zwei
bestehenden Formen.
