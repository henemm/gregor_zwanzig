# Context: feat-2186-tagesaggregat-ab-jetzt

**Issue:** #2186 — Tages-Aggregate im Ad-hoc-Abruf rechnen die vergangenen Stunden mit
(Teil A aus Scheibe S2 von Epic #2133)
**Track:** Full Process
**Erstellt:** 2026-09-08

## Request Summary

Wer mittags `glance`, `heute_gewitter` oder `timeline_heute` abruft, bekommt den bereits
vergangenen Vormittag mitgerechnet — der Regen von 08:00 fließt in den Tageswert ein. Der
Abruf beantwortet den Kalendertag, nicht das verbleibende Fenster. Für **morgen** darf sich
dagegen nichts ändern: ein noch nicht begonnener Tag wird durch „ab jetzt" nicht eingeschränkt.

Der stündliche Einzelgrößen-Verlauf ist bereits gefenstert (S1, #2134, `_day_window`) — nur die
**Tages-Aggregate** hängen noch am vollen Kalendertag.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py:1304` | `_aggregate_day()` — der Prüfling. Aggregiert `TimelinePoint.metrics` über den ganzen Ortstag |
| `src/services/trip_command_processor.py:1381` | `_fmt_glance()` — Leser (heute + morgen, zwei Aufrufe `:1395`/`:1396`) |
| `src/services/trip_command_processor.py:1410` | `_fmt_gewitter()` — Leser (nur heute, `:1420`) |
| `src/services/trip_command_processor.py:1508` | `_timeline_buttons()` — Leser (beide Tage, `:1513`) |
| `src/services/trip_command_processor.py:1448` | `_fmt_timeline()` — **filtert eigenständig** auf Kalendertag, ruft `_aggregate_day` NICHT. Eigene Behandlung nötig |
| `src/services/trip_command_processor.py:761` | `_handle_query()` — einziger Aufrufer aller vier Formatierer, hält `received_at` (`:762`), berechnet Tage/Zonen (`:781-785`) |
| `src/services/trip_command_processor.py:1133` | `_day_window()` — bestehende Fensterlogik der Drilldowns |
| `src/app/day_window.py:89` | `segment_window_points(start_time, end_time, points)` — generischer Stundenschnitt, beliebige Grenzen |
| `src/services/weather_metrics.py:462` | `compute_basis_metrics()` — geteilte Stunden→Aggregat-Rechnung |
| `src/services/weather_extractor.py:80-116` | `timeline()`/`_punkte()` — baut `TimelinePoint` aus Snapshot; **reicht die Stundenreihe nicht durch** |
| `src/services/weather_snapshot.py:484` | `_serialize_segment()` — schreibt `entry["hourly"]` |
| `src/services/weather_snapshot.py:546` | `_deserialize_timeseries()` — rekonstruiert die Reihe beim Laden |
| `src/app/models.py:103` | `ForecastDataPoint` — Stundenpunkt, `ts` ist **naive UTC** |
| `src/app/models.py:443` | `SegmentWeatherSummary` — das fertige Etappen-Aggregat |

## Gemessener Ist-Stand (2026-09-08, echte Prod-Snapshots)

Gemessen an `/var/lib/gregor/users/henning/weather_snapshots/` (`5f534011.json`,
`5f534011_2026-08-30.json`, `5f534011_alarm_anchor.json`).

### Die Stundenreihe liegt im Bestand vor

Alle geprüften Snapshots, alle Segmente: `hourly` mit **24 Punkten**, Spanne `00:00`–`23:00`
UTC. Die Reihe überlebt den JSON-Roundtrip. Die Lösungsform „aus Stundenreihen rechnen" ist
also tragfähig — nicht nur laut Typ-Annotation, sondern im Bestand.

### 🔴 Die Stundenreihe deckt den GANZEN Tag, das Aggregat nur die Gehzeit

Das ist der zentrale Befund. Pro Segment liegt die **volle Tagesreihe** der Segment-Position,
das gespeicherte `aggregated` ist aber auf das **Etappenfenster** beschnitten:

| Segment (Tour 05.09.) | Etappenfenster | Stunden im Fenster | gespeichert `t_max` | über alle 24 h |
|---|---|---|---|---|
| 1 | 06:00–07:20 | 1 | 16.8 °C | 20.7 °C |
| 2 | 07:20–09:22 | 2 | 18.2 °C | 20.0 °C |
| 3 | 09:22–11:23 | 2 | 22.7 °C | 24.2 °C |
| 4 | 11:23–12:09 | 1 | 27.2 °C | 28.1 °C |
| Ziel | 12:09–19:00 | 6 | 28.0 °C | 28.0 °C |

**Folge:** Ein Fix, der `_aggregate_day` naiv auf die rohen Stundenreihen umstellt, zieht die
**Nachtstunden** ins Tagesaggregat. Das ist genau der unter #1653 abgewehrte Fehler („das
24 h-Aggregat erfindet ein Tagesgewitter, das im Tagesfenster nie stattfand") und widerspricht
dem dreifach bestätigten PO-Entscheid „strikt nur Tagesfenster" (#1841/#1848 A3).

Das korrekte Fenster ist die **Schnittmenge**: `Etappenfenster ∩ [jetzt … Ortsmitternacht]`.

### Der Stundenschnitt hat eine exakte Rundungsregel — nicht selbst nachbauen

`segment_window_points()` rundet beide Grenzen auf volle Stunden ab und schließt die Endstunde
aus (`[start_floor, end_floor)`, Bug #806; Sonderfall Ein-Stunden-Segment, Bug #856). Eine
naive Nachrechnung mit `start <= ts < end` wich in der Messung um 1,3 °C ab (18.1 statt 16.8),
weil sie die Stunde 07:00 des 06:00–07:20-Segments mitnahm. Der Helfer ist Pflicht.

### `hail_flag` fehlt in den Stundenpunkten des Bestands

In allen drei geprüften Snapshots trägt **kein** Stundenpunkt `hail_flag` (die Serialisierung
lässt `None` weg), und auch `aggregated.hail_flag` fehlt. Der Hagel-Pfad ist im Bestand also
durchgehend „unbekannt" — heute wie nach dem Fix. Kein Regressionsrisiko, aber auch **kein
Beweisträger**: ein Test, der Hagel über echte Snapshots prüfen will, misst nichts.

### `pop_max_pct` ist nicht in `compute_basis_metrics`

`pop_max_pct` entsteht nur in `compute_extended_metrics()` (`weather_metrics.py:1156`), und
die läuft **ausschließlich im Fetch-Pfad** (`segment_weather.py:314`), nie beim Snapshot-Laden.
Wer die Tageswerte über `compute_basis_metrics()` neu rechnet, bekommt dort still `None` — und
`None` sieht in der Ausgabe aus wie „keine Daten", nicht wie ein Fehler.

**Aber:** der Rohwert `pop_pct` liegt in jedem Stundenpunkt vor. Die Größe ist aus der
Stundenreihe direkt herleitbar; sie braucht nur eine ausdrückliche Behandlung.

## Existing Patterns

- **`_day_window()` (`:1133`)** ist das etablierte Muster für „welches Fenster meint dieses
  Tages-Token". Es unterscheidet bereits richtig: `today` → ab `received_at`, `morgen` → ab
  Ortsmitternacht. Es liefert für `today` allerdings eine **Dauer von 12 Stunden**, keine
  Kalendertagsgrenze (ausführlich begründet `:1144-1149`) — siehe Risiken.
- **`_local_midnight(date, tz)`** ist der vorgesehene Weg zur Ortsmitternacht. Rohe
  `.astimezone()`/`date.today()`-Aufrufe sind durch den CI-Wächter
  `tests/tdd/test_output_timezone_guard.py` gesperrt (Auflage aus `fix_1795`).
- **Eine Rechnung, nicht zwei:** `_aggregate_day` bildet Stufe und tragende Zutat aus
  *derselben* gefilterten Punktliste (`:1334-1348`, #1680 Spec D6). Der Quelltext markiert eine
  dritte Eigenimplementierung derselben Regel ausdrücklich als Fehler (#1480). Für die
  Zutaten-Vereinigung und die Hagel-Priorität existieren geteilte Helfer
  (`union_of_max_carriers`, `hail_priority`, `thunder_ordinal` in `output/metric_format`).
- **Zwei-Zonen-Test:** `fix_1795` AC-4 prüft `_fmt_glance` mit heute in neuseeländischer und
  morgen in korsischer Zone in **einem** Durchgang. Dieses Muster trägt den vom Ticket
  geforderten Nachweis „ab jetzt fasst morgen nicht an".

## Dependencies

**Upstream (was wir benutzen):**
- `WeatherSnapshotService.load()` → `List[SegmentWeatherData]` mit `timeseries` + `aggregated`
- `weather_extractor.timeline()` → `TimelineResult` mit `TimelinePoint(arrival_time, metrics)`
- `segment_window_points()`, `compute_basis_metrics()`, `output.metric_format.*`
- `services.trip_day`: `trip_local_now`, `anchor_tz`, `display_tz`, `local_dt`, `_local_midnight`

**Downstream (was uns benutzt):**
- Telegram: `/glance` `/s` `/status`, `/hg` `/gewitter`, `/th`, `/tm` — je als Freitext-Kommando
  **und** als Button-Callback (`### query: …`)
- **E-Mail:** `glance` und `gewitter` sind über `_BARE_KEYWORD_MAP` (`:104`, `:111`) auch per
  E-Mail-Freitext erreichbar. `timeline_heute`/`timeline_morgen` sind Telegram-only.
  → **Der Fix betrifft zwei Kanäle.** Eine reine Telegram-Prüfung misst die halbe Wirkung.
- **Nicht betroffen:** die Mail-Renderer (`output/renderers/day_window.py`, `narrow.py`,
  `compact_summary.py`, `outlook.py`) haben eine eigene, feste 04–19-Uhr-Fensterlogik. SMS-Tokens
  (`tokens/builder.py`) lesen das Etappen-Aggregat, nicht `_aggregate_day`.

## Existing Specs

| Spec | Berührung |
|---|---|
| `docs/specs/modules/fix_1818_timeline_tagesaufloesung.md` | Gestufte Quellenauflösung für alle vier Formatierer. AC-1/3/4 bleiben gültig (prüfen Quellenwahl, nicht Tagesgrenze). AC-5 (`glance` unterscheidet heute/morgen) ist berührt |
| `docs/specs/modules/fix_1795_timeline_ortszeit.md` | AC-2/3/4/5 binden den Filter an den **Ortstag** von `arrival_time`. Der Filter wandert auf `ts` — die ACs müssen mitgezogen werden. Auflage: kein rohes `.astimezone()`, CI-Wächter aktiv |
| `docs/specs/modules/fix_1470_drilldown_ortszeit.md` | Bestätigend. AC-4: Fenstergrenze und Beschriftung stammen aus **derselben** Zonen-Auflösung — diese Pflicht erbt `_aggregate_day`, sobald es die Fensterung übernimmt |
| `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md` | Sagt ausdrücklich: „Ortstag bleibt unverändert. Diese Spec baut das nicht neu." (`:157-159`) |
| `docs/specs/modules/feat_2185_verlauf_wechselpunkte.md` | Grenzt das „ab jetzt"-Fenster der drei Tages-Aggregat-Antworten ausdrücklich aus — das ist #2186 |

**Es gibt keine Spec, die „Tages-Aggregat ab Anfragezeitpunkt" bereits festschreibt.** Freies
Feld, nichts wird still überschrieben.

## Risks & Considerations

1. **🔴 Nachtstunden-Falle.** Rohe Stundenreihen statt Etappen-Aggregate verbreitern das
   Tagesfenster still auf 24 h (siehe Messung oben). Muss als Schnittmenge gebaut und als
   eigene AC bewacht werden. Fixtures mit kurzen Reihen fangen diesen Fehler **nicht**.

2. **🔴 „Morgen" darf sich nicht ändern.** Ein Test, der nur „heute" prüft, fängt den Fehler
   nicht — das Ticket sagt das ausdrücklich. Nachweisform steht bereit (`fix_1795` AC-4,
   Zwei-Zonen-Aufbau).

3. **🔴 Fünf Ausgabestellen, vier davon über `_aggregate_day`, eine daneben.** `_fmt_timeline`
   (`:1448`) filtert selbst. Ein Fix, der nur `_aggregate_day` erreicht, lässt `timeline_heute`
   falsch — das Ticket nennt das die naheliegende Mutationsfalle.

4. **Offene Entscheidung: Was heißt „ab jetzt" für heute — bis Ortsmitternacht oder 12 Stunden
   Dauer?** `_day_window("today")` liefert heute eine **Dauer von 12 Stunden**, die abends in
   den Folgetag ragt. Für ein Tages-Aggregat geht das nicht: `glance` stellt „heute" und
   „morgen" nebeneinander, bei 12 h Dauer überlappten beide Zeilen ab dem Nachmittag.
   **Empfehlung: `jetzt … Ortsmitternacht`.** Bekannte Folge, die in die Spec-Freigabe gehört:
   Ein Abruf um 22:00 zeigt für „heute" nur noch zwei Stunden. Ob dann eine Fehlanzeige oder
   ein Zwei-Stunden-Wert erscheinen soll, ist eine Produktentscheidung.
   *Keine Spec-Deckung für die 12-Stunden-Regel gefunden — nur ein Quelltext-Kommentar.*

5. **`pop_max_pct` würde still `None`.** Braucht eine eigene AC, sonst verschwindet die
   Regenwahrscheinlichkeit unbemerkt aus der Ausgabe.

6. **Signaturänderung an vier Formatierern.** `received_at` muss durch `_fmt_glance`,
   `_fmt_gewitter`, `_timeline_buttons`, `_fmt_timeline` und `_aggregate_day` gereicht werden.
   Wächter liegen erfahrungsgemäß in **fremden** Testdateien → vor dem Commit `grep -rln` über
   `tests/`.

7. **Zeitzonen-Randfall.** Die Stundenreihe eines Snapshots deckt den **UTC**-Kalendertag ab
   (00:00–23:00). Bei großem Zonenversatz (die `fix_1795`-Tests benutzen Neuseeland, UTC+12)
   liegen Teile des **Orts**tages außerhalb dieser Reihe. Zu klären: ob der Ortstag-Rand dann
   Punkte verliert und ob die gestufte Quellenauflösung aus `fix_1818` das auffängt.

8. **Reichweite prüfen, nicht annehmen.** Der Ortsvergleich hat eigene Snapshots
   (`compare_weather_snapshots/`). Ob dort dieselben Ad-hoc-Abrufe existieren, ist noch nicht
   gemessen — Ortsvergleich-Themen sind ohnehin zurückgestellt, aber die Aussage „nicht
   betroffen" braucht einen Beleg statt einer Vermutung.

---

# Analysis (Phase 2, 2026-09-08)

## Type

**Feature** (Label `enhancement`). Kein Bug: das heutige Verhalten ist spezifiziert
(Kalendertag-Filter, `fix_1795`), es wird bewusst geändert.

## Der Angriffspunkt liegt stromaufwärts

`_aggregate_day` hat **keinen Zugriff auf die Stundenreihe** — nach
`weather_extractor.timeline()` sind nur noch fertige Etappen-Aggregate übrig
(`_punkte()`, `weather_extractor.py:102-116`: `metrics=seg.aggregated`). Die Stundenreihe
liegt genau **eine Zeile vorher** noch vor und wird dort verworfen.

Daraus folgt der Ansatz: **Die Fensterung gehört in `_punkte()`, nicht in `_aggregate_day`.**

```
timeline(trip_id, target_date, from_time=None)
  └─ _punkte(segments, from_time)
       für jedes Segment:
         beschnitten = max(seg.start_time, from_time)
         wenn beschnitten <= seg.start_time  → seg.aggregated UNVERÄNDERT übernehmen
         wenn beschnitten >= seg.end_time    → Segment entfällt (ganz vergangen)
         sonst                                → Aggregat NEU über [beschnitten, seg.end)
```

### Warum das die Mutationsfalle des Tickets auflöst

`_handle_query` ruft `extractor.timeline(trip.id)` **genau einmal**
(`trip_command_processor.py:802`/`:806`) und reicht dasselbe Objekt an alle fünf
Ausgabestellen. Ein Eingriff in `_punkte()` erreicht damit alle fünf — auch `_fmt_timeline`
(`:1462` liest `p.metrics` aus derselben `timeline`), das sonst separat hätte gefixt werden
müssen. Das Ticket nennt „ein Fix, der nur einen Leser erreicht" als naheliegende
Mutationsfalle; dieser Ansatz macht sie strukturell unmöglich.

**Folge: Risiko 6 des Kontextteils entfällt.** Die Signaturänderung an vier Formatierern wird
nicht gebraucht — sie bleiben unverändert, `received_at` muss nicht durchgereicht werden. Statt
elf Testdateien wegen einer Signaturkaskade sind nur die Tests betroffen, die das *Verhalten*
prüfen.

## Die drei stillen Regressionen, die der Ansatz mitbringt

Sie sind der eigentliche Inhalt der Spec — ohne eigene ACs treten sie garantiert ein.

### 1. Neu rechnen heißt: die GANZE Kette, nicht ihre erste Hälfte

Im Abruf-Pfad läuft das Segment-Aggregat über **zwei** Schritte
(`segment_weather.py:310` → `:314`): `compute_basis_metrics()` und danach
`compute_extended_metrics()`, wobei der zweite die Felder des ersten weiterträgt
(`weather_metrics.py:1009-1011`).

`compute_extended_metrics` bildet **18 weitere Felder**: `pop_max_pct`, `cape_max_jkg`,
`uv_index_max`, `dewpoint_avg_c`, `pressure_avg_hpa`, `wind_chill_min/max_c`, `snow_depth_cm`,
`freezing_level_m`, `snowfall_limit_m`, `cloud_low/mid/high_avg_pct`, `precip_type_dominant`,
`wind_direction_avg`, `confidence_pct`, Frischschnee.

Wer nur `compute_basis_metrics()` aufruft, leert sie alle still. `None` sieht in der Ausgabe
aus wie „keine Daten", nicht wie ein Fehler. → **AC-Pflicht: dieselbe Kette in derselben
Reihenfolge.**

### 2. Unbeschnittene Segmente dürfen NICHT neu gerechnet werden

Der naheliegende Vereinfachungsvorschlag lautet: `from_time` immer setzen, für morgen sei
`max(seg.start, from_time)` ohnehin ein No-Op. Für die *Fenstergrenze* stimmt das — für den
*Inhalt* nicht: Ein neu gerechnetes Aggregat ist nicht zwingend wertgleich mit dem
gespeicherten (Snapshot-Meta trägt `model="snapshot"`, `aggregation_config` kann abweichen).
„Morgen bleibt unberührt" wäre dann nur zufällig wahr.

**Regel: Nur wenn tatsächlich beschnitten wird, wird neu gerechnet.** Damit ist die
Unberührtheit von „morgen" strukturell garantiert und nicht bloß rechnerisch wahrscheinlich —
und sie ist prüfbar (Identität des Objekts/der Werte).

### 3. Fehlende Stundenreihe braucht einen Enthaltungs-Zweig

`SegmentWeatherData.timeseries` ist `Optional` (`None` bei Provider-Fehler, und Alt-Snapshots
könnten sie nicht tragen). `compute_extended_metrics` wirft bei leerer Reihe `ValueError`
(`weather_metrics.py:958`).

**Regel: keine Stundenreihe → `seg.aggregated` unverändert übernehmen.** Lieber ein
ungefenstertes Aggregat wie heute als ein falsches oder ein Absturz. Das muss eine eigene AC
tragen, sonst fällt der Fix im Bestand still auf die Nase.

## Entscheidungsbedarf: Was heißt „ab jetzt" — und was NICHT

Gemessen an einer echten Tour laufen die Etappen von 06:00 (Aufbruch) bis 19:00 (das letzte
Segment „Ziel" endet am Tagesfensterende). Das heutige Tagesaggregat umfasst also faktisch
`[Aufbruch … Tagesfensterende]` — **nicht** den Kalendertag.

| Option | Fenster für „heute" | Bewertung |
|---|---|---|
| **A (empfohlen)** | `[max(jetzt, Aufbruch) … Tagesfensterende]` | Kleinster Eingriff. Schneidet nur die Vergangenheit weg, lässt unberührt, *was* ein Tageswert bedeutet |
| B | `[max(jetzt, 04:00) … 19:00]` (ADR-0035) | Vereinheitlichte Semantik, aber zieht Stunden **vor dem Aufbruch** neu herein — eigene Produktänderung |
| C | `[jetzt … Ortsmitternacht]` | Zieht die **Nachtstunden** herein. Widerspricht dem 3× bestätigten PO-Entscheid „strikt nur Tagesfenster" (#1841/#1848) und der Abwehr aus #1653 |
| D | `[jetzt … +12 h]` | Die Vorgabe aus dem #2185-Kontextdokument. **Nicht tragfähig:** `glance` zeigt heute und morgen nebeneinander; ab dem Nachmittag enthielten beide Zeilen dieselben Stunden |

**Empfehlung A.** Sie ist die einzige Option, die keine zweite Entscheidung mitschmuggelt.
Bekannte Folge, die in die Freigabe gehört: Ein Abruf **nach** Tagesfensterende hat ein leeres
Fenster für „heute" — was dann erscheint (Fehlanzeige oder letzter bekannter Wert), ist eine
Produktentscheidung, keine technische.

*Für D gibt es keine gültige Deckung: die einzige AC mit 12 Stunden
(`telegram_tier3_drilldown.md` AC-1) ist seit 2026-09-07 durch #2185 abgelöst; die Begründung
in `trip_command_processor.py:1144-1149` ist ein Quelltext-Kommentar, keine freigegebene
Zusicherung.*

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/weather_extractor.py` | MODIFY | `timeline()` erhält `from_time`; `_punkte()` rechnet beschnittene Segmente neu (volle Kette), lässt unbeschnittene unangetastet, enthält sich ohne Stundenreihe |
| `src/services/trip_command_processor.py` | MODIFY | `from_time=received_at` an den `timeline()`-Aufruf (`:802`/`:806`) |
| `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py` | CREATE | Verhaltensnachweis: Vormittag fällt raus, morgen unberührt (Zwei-Zonen-Aufbau nach `fix_1795` AC-4) |
| `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py` | CREATE | Nachweis gegen die drei stillen Regressionen (volle Kette, unbeschnitten = unverändert, Enthaltung ohne Stundenreihe) |
| `tests/unit/test_weather_extractor.py` | MODIFY | `timeline()`-Signatur, Rückwärtskompatibilität ohne `from_time` |
| bestehende Tests | PRÜFEN | `grep -rln` über `tests/` nach `.timeline(`; laut Messung 4 Dateien, alle ohne `from_time` → Default `None` bricht sie nicht |

## Scope Assessment

- Produktivdateien: **2**
- Geschätzte LoC: Produktivcode **+40/-5**, Tests **+150–200**
- Risk Level: **MEDIUM** — kleiner Eingriff, aber an einer Stelle, die fünf Ausgaben und zwei
  Kanäle speist; die Gefahr liegt nicht im Umfang, sondern in den drei stillen Regressionen

## Open Questions (für die Spec-Freigabe)

- [ ] **Fensterwahl A/B/C/D** — Empfehlung A, siehe Tabelle oben (Produktentscheidung)
- [ ] **Abruf nach Tagesfensterende:** Fehlanzeige oder letzter bekannter Wert?
      (Produktentscheidung)
- [ ] Zeitzonen-Randfall (Kontext-Risiko 7): Die Stundenreihe deckt den **UTC**-Tag ab. Bei
      großem Zonenversatz kann der Ortstag-Rand außerhalb liegen. Mit Option A entschärft, weil
      das Fenster ohnehin innerhalb der Etappen liegt — im TDD-RED trotzdem mit der
      neuseeländischen Zone aus `fix_1795` nachzumessen
- [ ] Ortsvergleich (Kontext-Risiko 8): „nicht betroffen" ist noch Vermutung. Belegen oder in
      der Spec als bewusst außerhalb führen (Ortsvergleich-Themen sind zurückgestellt)

## Nächster Schritt

`/30-write-spec` — Spec mit ACs auf Deutsch, Freigabe durch den PO. Die vier offenen Punkte
oben gehören ausdrücklich in die Freigabe.
