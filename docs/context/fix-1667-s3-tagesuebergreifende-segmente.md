# Context: fix-1667-s3-tagesuebergreifende-segmente

**Issue:** [#1667](https://github.com/henemm/gregor_zwanzig/issues/1667) — Scheibe **S3**
**Workflow:** `fix-1667-s3-tagesuebergreifende-segmente` (Full Process, Intake-Score 4)
**Erstellt:** 2026-08-10 · Basis-HEAD `ffb82a40` (enthält S1 `db14acd3` und S2 `8d36dc8c`)
**Vorgänger-Kontext:** `docs/context/fix-1667-arrival-midnight-wrap.md` (S1/S2 — gilt weiter, wird hier nicht wiederholt)

## Request Summary

Nach S2 werden Segmente einer Etappe mit Ankunft nach Mitternacht **korrekt gebaut** — die
Alarm-Pipeline **findet sie aber nicht**, weil sie ausschließlich den heutigen Kalendertag
abfragt. S3 soll die Etappenauswahl tagesübergreifend machen, damit ein Wanderer mit
Abendstart seine Radar-/NowCast-Überwachung behält (heute: bis zu 11 h 50 min Verlust) und
damit bei Mehr-Etappen-Trips nicht still der falsche Ort abgefragt wird.

## Ist-Stand, am Code gemessen

### Die eine Zeile, an der alles hängt

`src/services/trip_alert.py:739,745`:

```python
today = date_type.today()          # 739
...
segments = convert_trip_to_segments(trip, today)   # 745
if not segments:
    continue
```

`convert_trip_to_segments` löst über `Trip.get_stage_for_date` (`src/app/trip.py:268-272`)
per **striktem `==`** auf und liefert `[]`, wenn keine Etappe genau dieses Datum trägt.
Eine gestrige Etappe, deren Segmente real bis heute Mittag laufen, ist damit unauffindbar.

Zwei gemessene Folgen um 02:00 UTC am Folgetag:

| Trip-Form | Verhalten heute | Wirkung |
|---|---|---|
| **Ein-Etappen-Trip** | `[]` → `continue` | **null Alarme**, obwohl die Segmente korrekt gebaut würden |
| **Mehr-Etappen-Trip** | heutige Etappe liefert Segmente, aber keines ist aktiv ⇒ `now_utc < segments[0].start_time` ⇒ `active = segments[0]` | **stille Falsch-Ortung**: Radar für den Startpunkt der *nächsten* Etappe (gemessen: Wanderer `(42.34, 8.94)`, Abfrage `(42.42, 9.02)`) |

### Was S2 bereits richtig macht — S3 muss hier nichts nachrechnen

Der PO-Beschluss „Überwachung bis Tagesfenster-Ende" ist im Ziel-Segment
(`src/services/trip_segments.py:264-290`) **bereits erfüllt**: `arrival_local_date` leitet
sich aus der Ankunfts-**Ortszeit** ab, bei 22:00-Start also aus dem Folgetag; `window_end`
liegt dann auf Folgetag 19:00 Ortszeit. Die Segmente von gestern reichen real bis in den
heutigen Nachmittag. S3 ist deshalb reine **Auswahl**, keine neue Zeitrechnung.

## Related Files

### Die drei Kopien der Aktiv-Segment-Auswahl (nicht zwei)

| Datei:Zeile | Funktion | Verhalten wenn nichts aktiv |
|---|---|---|
| `src/services/trip_alert.py:749-764` | `check_radar_alerts` | `now < segments[0].start_time` → `segments[0]`; sonst `continue` (**S3-Kern**) |
| `src/services/trip_report_scheduler.py:1341-1350` | `_build_starkregen_hint` | identische Logik, dann `return None` |
| `api/routers/debug.py:76-83` | Staging-Debug-Seam | **kein** Vergangenheits-Abbruch, fällt immer auf `segments[0]` |

⚠️ Der Docstring bei `trip_report_scheduler.py:1333` verweist auf „trip_alert.py:730-745" —
**veraltet**, die Stelle sitzt bei 745-764. Beim Anfassen mitziehen.

⚠️ **Wichtiger Unterschied zwischen den beiden Produktivkopien:** `check_radar_alerts` ist
eine **Now-Schleife über alle Trips** und löst das Datum selbst auf.
`_build_starkregen_hint` bekommt die Segmentliste dagegen **von außen** gereicht
(`trip_report_scheduler.py:1060-1062`), gebaut zum Briefing-`target_date`
(`_get_target_date`: morgens `today`, abends `today+1`). Die Datumsauflösung sitzt dort
also gar nicht in der Kopie — „beide Kopien fixen" ist deshalb **nicht** dasselbe wie
„zweimal dieselbe Zeile ändern". Das ist eine Analyse-Frage, keine Implementierungsfrage.

### Die fünf „Segment vorbei"-Guards — mit Scope-Bewertung

| Datei:Zeile | Was unterdrückt wird | S3-relevant? |
|---|---|---|
| `src/services/trip_alert.py:756-764` | Radar-/NowCast-Alarm komplett | **ja — Kern** |
| `src/services/trip_alert.py:1005-1010` | `_fetch_fresh_weather`: `end_time < now_utc` → skip; `start_time.date() > today_utc` → skip | **zu prüfen** — arbeitet auf gecachten Segmenten, nicht auf der Datumsauflösung |
| `src/services/trip_alert.py:1155-1158` | `check_official_alert_triggers`: `end_time < now_utc` → skip | **zu prüfen** — dito |
| `src/services/trip_report_scheduler.py:1346-1350` | Kein Nowcast-Call im Briefing-Pfad | **ja**, aber s. o. (Datum kommt vom Aufrufer) |
| `src/services/corridor_threshold.py:84-87` | Korridor-/Schwellentreffer | **nein** — `evaluate_corridor_thresholds` hat **keinen Produktions-Aufrufer**, nur Tests (`tests/tdd/test_corridor_threshold_evaluation.py:79`, `tests/tdd/test_alert_log_metrics.py:97`). Anfassen wäre Scope ohne Nutzerwirkung |

Nur eine Debug-Warnung, **kein** Skip: `src/services/segment_weather.py:386-392`.

### Alle Aufrufer der Segmentbildung (Datum-Argument je Stelle)

| Datei:Zeile | Funktion | Datum |
|---|---|---|
| `src/services/trip_alert.py:745` | `check_radar_alerts` | `date.today()` |
| `src/services/trip_report_scheduler.py:424` | `_process_pending_markers` | Marker-Datum |
| `src/services/trip_report_scheduler.py:858` | `_send_trip_report_outcome` | `_get_target_date()` |
| `src/services/trip_report_scheduler.py:868` | `_send_trip_report_outcome` | `select_test_stage().date` |
| `src/services/trip_report_scheduler.py:1761` | `_build_stage_trend` | `stage.date` |
| `src/services/trip_report_scheduler.py:2153` | `_collect_future_stage_weather` | `stage.date` |
| `src/services/trip_command_processor.py:296-297` | `_ensure_fresh_snapshot` | **`today` UND `tomorrow`**, Ergebnis addiert |
| `src/services/preview_service.py:143` | Preview | `target` |
| `src/services/stage_weather.py:49` | `_segments_for_stage` | `stage.date` (Scoped Trip) |
| `api/routers/debug.py:63,70` | Debug-Seam | `today`, dann Fallback über **alle** Stages |
| `tools/weather_validation.py:99` | Validierungswerkzeug | `_get_target_date()` |

## Existing Patterns

### Es gibt bereits zwei Präzedenzfälle für „mehr als ein Tag"

1. **`trip_command_processor.py:296-297`** — `segments + segments_tomorrow`, also schlichte
   Addition zweier Tage. Vorbild für die *Form* eines additiven Fallbacks; Richtung ist
   allerdings vorwärts, nicht rückwärts.
2. **`api/routers/debug.py:70`** — Fallback-Schleife über alle Stages, nimmt die erste, die
   Segmente liefert. Nur Staging-Debug, aber der einzige existierende „Datum-egal"-Pfad.

**Kein** Produktivpfad löst heute die Etappe des **Vortags** auf. Tagesübergreifende
Segmente entstehen ausschließlich intern über den `wp_days`-Offset
(`trip_segments.py:150-158`, #1091/#1098).

### Gegenrichtung — nicht verwechseln

`trip_report_scheduler.py:1422-1444` (`_clamp_segments_to_today`, #1325) verschiebt
vergangene Segmentzeiten **vorwärts auf heute** — reiner Test-Fallback
(`allow_test_fallback`). Das ist die Umkehrung dessen, was S3 tut, und darf nicht
angefasst oder als Vorbild genommen werden.

### Test-Uhr: zwei Hausmuster, beide vorhanden

| Muster | Produktivnaht | Testbeispiel |
|---|---|---|
| **`now_fn`-Fabrik im Konstruktor** | `src/services/radar_service.py:127` — `self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))` | `tests/unit/test_radar_nowcast_cache_sharing.py:126-128` |
| **`now=`-Parameter** durchgereicht | `alert_gate`, Budget-Gates, `check_nowcast_gate` | `tests/tdd/test_alert_gate.py:108`, `tests/unit/test_forecast_budget_gate.py:326` |
| **`freeze_time`** (seit S1 Dev-Dependency) | — | `tests/unit/test_arrival_window_fixtures.py:256-261` |

`TripAlertService.check_radar_alerts` hat **keine** von beiden — `now_utc` und `today`
kommen roh aus der Wanduhr. Die Wahl zwischen `_now_fn` und `freeze_time` ist eine
Analyse-Entscheidung; beide sind Hauskonvention, `freeze_time` ist seit S1 verfügbar und
bräuchte **keine** Produktivcode-Naht.

## Dependencies

- **Upstream:** `naismith.py` (Ankunft, seit S2 mit Modulo-Wrap) → `trip_segments.py`
  (Segmentbau inkl. `wp_days`-Rollover und Ziel-Segment nach #1584) → `Trip.get_stage_for_date`
- **Downstream:** Radar-/NowCast-Alarme (`check_radar_alerts`), Briefing-Starkregenhinweis
  (`_build_starkregen_hint`), und über den geteilten Freigabe-Baustein `check_nowcast_gate`
  (#1467 S3) die Ruhezeit-/Sperrzeit-/Tagesgrenzen-Kette (`alert_daily_limit`, `ThrottleStore`)

## Existing Specs & ADRs

| Dokument | Kernaussage für S3 |
|---|---|
| `docs/specs/modules/fix_1667_s2_naismith_wrap.md:362-367` | Known Limitation formuliert die S3-Aufgabe wörtlich: „`trip_alert.py:745` fragt weiterhin nur den heutigen Tag ab. Behoben erst durch S3." |
| `docs/specs/modules/fix_1584_alarm_zeitfenster.md:310-323` | 🔴 **Abgrenzung:** Ein *konfiguriertes Tagesfenster über Mitternacht* (22–2 Uhr) ist am Zielsegment bewusst ausgeschlossen. Das ist **nicht** derselbe Fall wie eine *Etappe mit Ankunft nach Mitternacht*. `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` muss grün bleiben |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Kalendertage folgen der Ortszeit — relevant, weil `trip_alert.py:739` `date.today()` (Server-Lokalzeit) nutzt, nicht die Ortszeit der Etappe |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | Ein Auflöser `resolve_configured_window()`, Default 4–19 |
| `docs/reference/api_contract.md:905,917,933` | `arrival_calculated` bleibt reiner `HH:MM`-String — von S3 unberührt |

## Bestehende Wächter — was nicht brechen darf

| Test | Zusichert | Läuft in CI? |
|---|---|---|
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:232` (`test_ac2_segment_selection_by_time`, Fall a) | aktives Segment wird gewählt | **nein** (`ci_tdd_excludes.txt`) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:313` (Fall c) | **alle Segmente vorbei ⇒ kein Alarm** | **nein** |
| `tests/tdd/test_issue_818_radar_briefing_integration.py:419` (`test_ac5_past_segment_no_alert_guard_test`) | dasselbe, NZ-Zone, Fenster 0–1 | **nein** |
| `tests/unit/test_alarm_zeitfenster_ziel.py:527` (`test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`) | Umkehrrichtung: Spätankunft darf **nicht** in „alle vorbei" fallen | **ja** |
| `tests/unit/test_alarm_zeitfenster_ziel.py:605` (`test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`) | PO-Entscheidung 2026-08-08 | **ja** |
| `tests/unit/test_alarm_zeitfenster_ziel.py:420-724` (12 Tests, AC-1…AC-6 aus #1584) | Tagesfenster am Ziel | **ja** |
| `tests/unit/test_arrival_window_fixtures.py` (10 Tests) | S1-Helfer + Segmentbau unter `freeze_time` nie „alle vorbei" | **ja** |
| `tests/tdd/test_fixture_wallclock_ratchet.py` (13 Tests) | S1-Ratsche gegen Wanduhr-Fixtures | **ja** |
| `tests/tdd/test_naismith_midnight_wrap_segments.py`, `test_naismith_hhmm_wrap_parity.py` | S2 | **ja** |
| `tests/tdd/test_starkregen_kurzfristhinweis.py:277-626` (AC-1…AC-8) | Briefing-Starkregenhinweis; **kein** eigener Test für den Zweig „alle vorbei → `return None`" | **ja** |

🔴 **Der wichtigste Befund aus der Testkartierung:** Genau die beiden Tests, die die von S3
zu ändernde Zusicherung („alle Segmente vorbei ⇒ kein Alarm") ausdrücklich festschreiben,
stehen **beide** in `.github/ci_tdd_excludes.txt` und laufen nicht in CI. Ein S3, das sie
anpasst und nur lokal grün prüft, ändert eine Zusicherung, die in CI von **niemandem**
bewacht wird. Der neue Nachweis muss CI-laufend sein.

## Risks & Considerations

1. 🔴 **Die Vorrangregel ist die eigentliche Designentscheidung — und die naive Fassung
   greift zu kurz.** „Heute gewinnt, gestern nur wenn heute nichts liefert" behebt den
   Ein-Etappen-Fall, **nicht** die Falsch-Ortung: Beim Mehr-Etappen-Trip *liefert* heute
   sehr wohl Segmente (die Etappe ab 08:00), es ist nur keines aktiv, und die
   Vorstart-Regel (`now < segments[0].start_time → segments[0]`) greift zu. Der Fallback
   muss also **vor** der Vorstart-Regel ausgewertet werden. Formulierung, die beides trifft:
   *ein aktives Segment von heute gewinnt; erst danach ein aktives Segment von gestern; erst
   danach die Vorschau auf heute.* Gehört als eigenes AC in die Spec.
2. **Doppel-Aktivierung.** Nach S2 überlappen Ziel-Segment von gestern (bis ~19:00 Ortszeit)
   und Etappe von heute (ab 08:00) real. Was passiert zwischen 08:00 und 19:00, wenn beide
   aktiv sind? Regel muss deterministisch und begründet sein, nicht Listenreihenfolge + `break`.
3. **Zwei Kopien, aber nicht symmetrisch.** Die Datumsauflösung sitzt nur in
   `check_radar_alerts`; im Scheduler kommt sie vom Aufrufer (`_get_target_date`). Ob der
   Briefing-Pfad überhaupt einen Vortags-Fallback *will* (das Briefing gilt einem Zieltag),
   ist offen — abends baut er sogar `today+1`.
4. **Alarm-Häufigkeit / Kontingent.** Ein zusätzlich gefundenes aktives Segment heißt
   zusätzliche Radar-/NowCast-Abrufe. `check_nowcast_gate` (#1467 S3) drosselt per
   `trip.id` — ein zweites Segment desselben Trips erzeugt keinen zweiten Alarm, aber
   möglicherweise Abrufe. Gegen `alert_daily_limit` und `ThrottleStore` zu prüfen.
5. **`date.today()` ist Server-Lokalzeit, nicht Ortszeit** (`trip_alert.py:739`). Server
   läuft auf `Etc/UTC`, deshalb heute deckungsgleich mit UTC — aber es ist eine
   undokumentierte Kopplung und steht quer zu ADR-0044. Ob S3 das mitzieht oder als
   Known Limitation benennt, ist eine Zuschnitt-Entscheidung.
6. **Kein Nachweis ohne Uhr.** Der Kernbeweis („um 02:00 UTC werden die Koordinaten des
   tatsächlich begangenen Segments abgefragt") braucht eine gestellte Uhr. `freeze_time`
   ist seit S1 verfügbar und bräuchte keine Produktivnaht; `_now_fn` wäre die
   explizitere, aber invasivere Variante.
7. **Ein Test auf „Alarm entsteht" hätte die Falsch-Ortung nie gefunden.** Der Nachweis
   muss auf die **Koordinaten** des gewählten Segments zielen, nicht auf einen Zähler.
8. **`corridor_threshold.py` nicht anfassen** — kein Produktions-Aufrufer. Ein Fix dort
   wäre unbelegbare Arbeit.
9. **LoC-Limit 250**, `tests/` zählt mit. Geschätzt ~120–130 Produktiv+Test; der
   CI-laufende Ersatznachweis für die zwei ausgeschlossenen Tests kommt obendrauf.
10. **Rückwärts-Suche darf nicht unbegrenzt sein.** „Gestern" heißt genau ein Tag;
    ein Trip mit Lücken oder eine mehrtägige Rückwärtssuche wäre neuer Scope.

---

## Analysis (Phase 2)

### Type
**Bug.** Sicherheitsrelevant: Verlust der Radar-/NowCast-Überwachung. Kein neues Verhalten,
sondern die Wiederherstellung einer Zusicherung, die #822 bereits gegeben hat.

### Was die Gegenprüfung bestätigt hat

| Behauptung | Ergebnis |
|---|---|
| Ein-Etappen-Trip 02:00 UTC ⇒ null Radar-Alarme | **hält** — `get_stage_for_date` strikt `==` (`src/app/trip.py:268-272`) |
| Mehr-Etappen-Trip ⇒ echter Radar-Abruf für den falschen Ort | 🔴 **ÜBERHOLT durch #1697 — siehe Delta-Abschnitt am Dateiende.** Der damalige Befund („zwischen Auswahl und `get_nowcast` liegt **kein** Horizont-/Näheguard, `NOWCAST_HORIZON_MIN` kommt in `trip_alert.py` nicht vor") stimmt seit #1697 nicht mehr: der Guard sitzt jetzt bei `trip_alert.py:940-955`. Der falsche Abruf findet nur noch im **letzten 60-Minuten-Fenster vor dem Start der Folgeetappe** statt |
| Ziel-Segment von gestern läuft real bis ~19:00 Ortszeit heute | **hält für den Normalfall** — `arrival_local_date` = Folgetag, `09:21 < 19:00` ⇒ regulärer Zweig, kein Mindestfenster (`trip_segments.py:275-297`). **Nicht** für Etappen, deren Ankunft nach dem Folgetags-Fensterende liegt (Gehzeit > 21 h ab 22:00-Start) — dort greift weiter das 1-h-Mindestfenster |
| `corridor_threshold.py` ohne Produktions-Aufrufer | **hält** — nur Definition + 2 Tests; `trip_alert.py:29` importiert nur das Dataclass `CorridorHit`, passend zu `trip_alert.py:52-56` („#1460 P1a: KEIN Alarm-Auslöser mehr"). Dokumentiert in `docs/specs/modules/rework_1460_t1_relevanzfilter.md:45` |
| Die zwei „alle Segmente vorbei"-Wächter laufen nicht in CI | **hält** — `.github/ci_tdd_excludes.txt:77-78`. Kein CI-laufender Ersatz gefunden: `test_alarm_zeitfenster_ziel.py` und `test_arrival_window_fixtures.py` konstruieren ihre Fixtures bewusst so, dass Ortsdatum == Etappendatum bleibt, prüfen den datumsübergreifenden Fall also gerade nicht |

### 🔴 Nachgemessen: `date.today()` bricht auch ohne Nacht-Etappe — in beide Richtungen

`trip_alert.py:739` nutzt `date.today()` (Serverzeit = UTC), die Etappe trägt aber ein
**Ortsdatum**. Für eine völlig gewöhnliche Etappe 08:00–19:00 Ortszeit gemessen:

| Zone | Etappe läuft in UTC | `date.today()` trifft die Etappe |
|---|---|---|
| Europe/Paris (UTC+2) | 06:00–17:00 desselben Tages | **immer** |
| America/Los_Angeles (UTC−7) | 15:00 bis 02:00 des Folgetags | **die letzten 2 h nicht** — dort ist die Etappe *gestern* ⇒ **vom Vortags-Fallback mitgeheilt** |
| Pacific/Auckland (UTC+12) | **20:00 des Vortags** bis 07:00 | **die ersten 4 h nicht** — dort ist die Etappe *morgen* ⇒ **ein Vortags-Fallback hilft nicht** |

Ein Wanderer in Neuseeland verliert damit die ersten ~4 von 11 Stunden **jedes** Etappentags
— ohne jede Nacht-Etappe, bei ganz normalem 08:00-Start. Vorbestehend, von S3 weder erzeugt
noch (in der Rückwärts-Variante) behoben. Ob S3 den Vorwärts-Zweig mitnimmt, ist eine
Zuschnitt-Entscheidung des PO (s. Open Questions).

### Technischer Ansatz

Zwei Funktionen in `src/services/trip_segments.py`, getrennt entlang der Asymmetrie der Aufrufer:

```python
select_active_segment(segments, now_utc) -> Optional[TripSegment]
resolve_current_segment(trip, now_utc, today) -> Optional[tuple[TripSegment, date]]
```

- **`select_active_segment`** ist die heutige Regel 1:1 (aktiv → `segments[0]` wenn `now <
  segments[0].start_time` → `None`). Ersetzt beide Kopien verhaltensidentisch.
- **`resolve_current_segment`** löst zusätzlich das Datum auf und trägt die Vorrangkette.
  Nur `check_radar_alerts` braucht sie.
- **Segment statt Segmentliste, und mit Datum.** Eine zusammengeführte Liste
  (`gestern + heute`) degradiert die Vorrangregel zu „Listenreihenfolge + `break`" — in der
  Überlappung stünde das Ziel-Segment von gestern vorn und gewönne. Die Liste kann die Regel
  also gar nicht tragen.
- **Vortagsbau lazy** — nur wenn heute kein aktives Segment liefert.

**Vorrangkette:** (1) aktives Segment von heute → (2) aktives Segment von gestern →
(3) Vorschau `heute[0]` → (4) nichts. Aus gestern wird **nie** eine Vorschau genommen.

**Begründung für „heute gewinnt bei echter Überlappung"** (der Punkt, den die Analyse vorher
nur behauptet hat):
1. *Fachlich:* Das Ziel-Segment von gestern ist ein **ortsfestes** Fenster an der Unterkunft
   (`trip_segments.py:264-290` — Startkoordinate = Ankunftspunkt). Läuft heute ein Segment,
   ist der Wanderer in Bewegung; diese Koordinate ist die informativere.
2. *Technisch:* Solange heute ein aktives Segment existiert, ist das Ergebnis **bitgleich**
   zum Ist-Zustand. Genau das macht die Änderung nachweisbar additiv.

### 🔴 Der nicht offensichtliche Teil: das Schnappschuss-Datum muss mitwandern

`trip_alert.py:829` lädt `WeatherSnapshotService(...).load_dated(trip.id, today)` und
`_briefing_precip_for_onset` (`:690-717`) matcht auf `segment_id`. Stammt das gewählte
Segment von gestern, trifft der Vergleich auf den **gleichnamigen** Eintrag des heutigen
Schnappschusses (`segment_id="Ziel"` bzw. `1,2,3…`) und kann den gerade erst gewonnenen
Alarm still unterdrücken (`_briefing_announced and not result.is_convective` → `continue`).
**Ohne diese Mitnahme wäre S3 in genau dem Fall wirkungslos, für den es gebaut wird.**
Gleiche Klasse, aber nur ein Cooldown-Fenster weit: der Doppel-Alarm-Guard-Schlüssel
`precip:{segment_id}` (`trip_alert.py:846`) — als Known Limitation benennen, nicht reparieren.

### Test-Uhr: `freeze_time`, keine Produktivnaht

`_now_fn` auf `TripAlertService` wäre eine **halbe** Uhr: die Wanduhr wird in diesem Pfad an
mindestens vier Stellen gelesen (`trip_alert.py:739,740,850` plus
`RadarNowcastService._now_fn`, `radar_service.py:127`) — eine Naht nur im Alarmdienst ließe
Radar-Service und Cache auf der echten Uhr. `freeze_time` ersetzt `datetime`/`date` global,
ist seit S1 Dev-Dependency und friert in `tests/unit/test_arrival_window_fixtures.py:256,284`
bereits denselben Code ein. Koordinaten-Nachweis über `CountingFrameSource`
(`tests/helpers/nowcast_gate_fixtures.py:175-190`, protokolliert `(lat, lon)`).

**Auflage:** Radar-Cache ist Prozess-Singleton mit TTL 300 s (`radar_cache.py:106-120`) —
unter eingefrorener Uhr läuft er nie ab; pro Test `reset_radar_cache()`.
**Nicht anfassen:** `_radar_mails_fuer_spaetankunft` (`test_alarm_zeitfenster_ziel.py:356-417`)
ist absichtlich wanduhrgebunden und von der S1-Ratsche bewacht.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/trip_segments.py` | MODIFY | `select_active_segment` + `resolve_current_segment` |
| `src/services/trip_alert.py` | MODIFY | `:739-764` auf den Baustein; `:829` Schnappschuss-Datum mitziehen |
| `src/services/trip_report_scheduler.py` | MODIFY | `:1341-1350` auf den Selektor; veralteten Docstring `:1332-1333` korrigieren |
| `tests/unit/test_tagesuebergreifende_segmentauswahl.py` | CREATE | CI-laufender Nachweis mit `freeze_time` + Koordinaten-Assertion |

Ablage in `tests/unit/` ist **Absicht**: `tests/tdd/` läuft grundsätzlich in CI, aber genau
die beiden einschlägigen Altwächter stehen auf der Ausnahmeliste.

### Scope Assessment
- Dateien: 3 MODIFY + 1 CREATE
- LoC: ~60 netto Produktivcode, ~130 Tests ⇒ **~190 netto** (Limit 250)
- Risiko: **MEDIUM** — heißer Alarmpfad, aber bitgleich, solange heute ein aktives Segment existiert

### Risiken, die in die Spec gehören
- **Tagesbudget-Konkurrenz:** Ein Wrap-Trip, der bisher gar nichts verbrauchte, kann jetzt
  das Tagesbudget des Nutzers belegen (`alert_daily_limit.py:61-74`) und andere Trips
  verdrängen. Gewollte Wirkung, aber zu benennen.
- **Provider-Last:** weiterhin **ein** `get_nowcast` pro Trip pro Lauf
  (`trip_alert.py:801-806`); Mehrlast nur bei Trips, die bisher `continue` nahmen
  (≤ 1 Abruf je 15-Min-Zyklus). Gedämpft durch Radar-Cache und `ForecastBudgetGate`
  (`priority="polling"`).
- **Die zwölf #1584-Tests:** elf bekommen ihre Segmente vom Test selbst
  (`test_alarm_zeitfenster_ziel.py:200-207`) und sind strukturell unberührt.
  `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` hängt allein an der
  Ziel-Segment-Rechnung, die S3 **nicht** anfasst — Voraussetzung: S3 führt nirgends
  „Fensterende auf den Folgetag schieben" ein, sondern nimmt Segmente, wie sie gebaut wurden.

### Known Limitations (Entwurf für die Spec)
- **Ostzonen-Spiegelbild** (s. Messung oben) — je nach PO-Entscheidung offen oder mit erledigt.
- **Sehr lange Nacht-Etappen** (Ankunft nach dem Folgetags-Fensterende) behalten das
  1-h-Mindestfenster. Das ist die von #1584 AC-3 ausdrücklich abgenommene Spätankunfts-
  Behandlung, kein neuer Mangel — aber im S3-Kontext bisher nirgends benannt.
- **Deviations-/Schnappschuss-Pfad** (`_get_cached_weather`, `trip_alert.py:484-492`) lädt
  ebenfalls nur den heutigen Schnappschuss. Gleiche Fehlerklasse, anderer Pfad, nicht S3.
- **Doppel-Alarm-Guard-Schlüssel** `precip:{segment_id}` kollidiert über den Tageswechsel.

### PO-Entscheidung 2026-08-10 — S3 zurückgestellt hinter #1697

Die Frage „nur rückwärts oder symmetrisch (auch morgen)?" ist **anders beantwortet worden
als gestellt**, und zu Recht: Ein Vorwärts-Zweig wäre Herumbauen um eine falsch gestellte
Frage gewesen. Der Ostzonen-Befund ist kein Zuschnitt-Detail von S3, sondern ein eigener
Fehler mit eigener Ursache — `date.today()` ist die **Serveruhr**, die Etappe trägt ein
**Ortsdatum**. Er ist als **[#1697](https://github.com/henemm/gregor_zwanzig/issues/1697)**
gebucht und wird **vor** S3 behoben.

Die Messung, die die beiden trennt:

| Fall | Server-Datum trifft | Ortsdatum trifft |
|---|---|---|
| Neuseeland, normale Etappe 08–19 | 2/4 | **4/4** |
| Kalifornien, normale Etappe 08–19 | 3/4 | **4/4** |
| Paris, Nacht-Etappe 22:00→10:00 (**der S3-Fall**) | 2/5 | **1/5 — schlechter** |

Fehler A (Zeitzone) wird durch die richtige Datumsauflösung **vollständig** behoben.
Fehler B (Etappe überlebt ihren Kalendertag) wird durch **kein** Datum behoben — dafür ist
der Vortags-Rückgriff da, und nur dafür.

**Für S3 ändert sich inhaltlich nichts.** Ein Vortags-Rückgriff rechnet relativ zu „heute",
unabhängig davon, wie „heute" bestimmt wird. Diese Analyse bleibt vollständig gültig und wird
nach #1697 unverändert aufgenommen. Kein Rework, keine Abhängigkeit außer der Reihenfolge.

### Open Questions
*(keine offenen — S3 ist analysiert und wartet auf #1697)*

---

## Delta-Messung 2026-08-11 — Wiederaufnahme nach #1697

Basis neu: `origin/main` `e21f4f48`. Zwischenzeitlich ausgeliefert: **#1697** (Ortstag statt
Serverdatum im Alarm-Pfad, Merge `596a7cd8`) und **#1724** (Briefing-Fälligkeit folgt der
Ortszone). Jede Aussage unten am aktuellen Code gemessen.

### Was unverändert trägt

| Analyse-Aussage | Fundort heute |
|---|---|
| Es wird genau **ein** Kalendertag abgefragt — Kernbefund | `trip_alert.py:911` `today = trip_local_today(trip, now_utc)`, `:913` `convert_trip_to_segments(trip, today)` |
| Aktiv-Auswahl mit `continue` bei „alle vorbei" | `trip_alert.py:917-932` (vorher `:749-764`) |
| Zweite Kopie im Scheduler | `trip_report_scheduler.py:1401-1413`; **veralteter Docstring-Verweis** „trip_alert.py:730-745" jetzt bei `:1395-1396` |
| Dritte Kopie, Staging-Debug | `api/routers/debug.py:61` — weiterhin `date_type.today()`, von #1697 **nicht** umgestellt. Bleibt aus dem Scope |
| Schnappschuss-Pfad | `load_dated(trip.id, today)` jetzt `:1020`; `_briefing_precip_for_onset` `:858`, `segment_id`-Match `:874`; Guard-Schlüssel `precip:{segment_id}` `:1037` |
| `corridor_threshold.evaluate_corridor_thresholds` ohne Produktions-Aufrufer | `:68` + zwei Testdateien, sonst nichts |
| Die zwei Altwächter laufen nicht in CI | `.github/ci_tdd_excludes.txt:77-78` |

Ebenfalls unverändert gültig: die Vorrangkette und die Begründung „heute gewinnt bei echter
Überlappung". Präzisierung: „gestern" heißt `today - 1` relativ zu dem bereits
ortstag-korrigierten `today` aus `trip_local_today` (`trip_day.py:90-96`), nicht relativ zu
einem Serverdatum. Der Satz „aus gestern wird nie eine Vorschau genommen" ist strukturell
ohnehin unverletzbar: `get_stage_for_date` löst strikt per `==` auf (`trip.py:268-273`), ein
Segment von `today - 1` kann bei `now_utc` nie in der Zukunft liegen.

### 🔴 Was überholt ist — der Horizont-Guard existiert jetzt

#1697 hat bei `trip_alert.py:940-955` einen Horizont-Guard eingebaut: beginnt das gewählte
Segment mehr als `NOWCAST_HORIZON_MIN` (60 min) in der Zukunft, wird kein Nowcast abgerufen.

**Folge für den zweiten Kernbefund (stille Falsch-Ortung):** Er ist **nicht entkräftet, aber
auf ein Zeitfenster verengt**. Im ursprünglich gemessenen Beispiel (02:00 UTC, Folgeetappe
startet 06:00 UTC) greift der Guard — 240 min > 60 ⇒ kein Abruf, reiner Überwachungsverlust.
Sobald der Start der Folgeetappe aber **≤ 60 min** entfernt ist, greift der Guard nicht und
`get_nowcast` läuft mit den Koordinaten der Folgeetappe, während der Wanderer nach einer
Ankunft nach Mitternacht real noch an der Vortages-Koordinate steht.

Das verschiebt die Beweislast: Ein AC darf nicht zeigen wollen, dass „kein Abruf für den
falschen Ort" passiert — das erledigt der Guard in den meisten Fällen schon. Es muss zeigen,
dass **in genau diesem ≤60-Minuten-Fenster die richtige (gestrige, noch aktive) Koordinate**
abgefragt wird.

### 🔴 Neu vorhanden: ein CI-laufender Nachbar-Wächter

`tests/tdd/test_radar_alert_follows_ortstag.py` (755 Zeilen) entstand mit #1697 und steht
**nicht** auf der CI-Ausnahmeliste. Gegengemessen: 28/28 grün
(`--disable-socket --allow-hosts=127.0.0.1`).

**Kollisionsprüfung — kein Test dieser Datei bricht durch S3:**

- **AC-3** (`:264-391`) ist der einzige Kandidat: Uhr 22:30 UTC, Korsika, Ortstag = Folgetag,
  `assert not frame_source.calls`. Nachgerechnet an `trip_segments.py:265-297` +
  `day_window.py:20ff.`: Ankunft 16:00 Ortszeit < Fensterende 19:00 ⇒ Mindestfenster-Zweig
  greift nicht ⇒ `dest_end_time = 17:00 UTC`. Um 22:30 UTC ist auch das Ziel-Segment des
  Vortags seit 5,5 h vorbei ⇒ Stufe (2) der Vorrangkette greift nicht, Stufe (3) liefert
  unverändert die Folgetags-Etappe. **Bleibt grün.**
- **AC-1, AC-2, AC-4, AC-5, F001, F002** bauen alle **Ein-Etappen-Trips** — es gibt keinen
  Vortag, auf den zurückgegriffen werden könnte.

**Die Kehrseite:** Genau deshalb exerziert **keiner** dieser sieben Tests den S3-Kernfall. Der
Nachweis muss vollständig neu gebaut werden; Regressionsgefahr gegen diese Datei besteht nicht.

### Konsequenz für den Test-Zuschnitt — Ablage geändert

Die ursprüngliche Empfehlung `tests/unit/test_tagesuebergreifende_segmentauswahl.py` beruhte
darauf, dass `tests/tdd/` teilweise CI-ausgeschlossen ist. Der eigentliche Punkt war „nicht auf
der Excludeliste landen", nicht „unit statt tdd" — und `test_radar_alert_follows_ortstag.py`
belegt, dass eine `tests/tdd/`-Datei sehr wohl CI-laufend sein kann.

**Neue Empfehlung:** den Nachweis als weiteres AC in `test_radar_alert_follows_ortstag.py`
bauen (oder als Geschwisterdatei daneben). Begründung: Er braucht genau die Helfer, die dort
schon liegen — `make_trip`, `trip_stage`, `CountingFrameSource`, `reset_radar_cache` aus
`tests/helpers/nowcast_gate_fixtures.py`, bereits für mehrstufige Trips mit exakten
Ankunftszeiten erweitert. Eine neue `tests/unit/`-Datei müsste denselben Helfer importieren
(dann ist „unit" irreführend) oder ihn duplizieren (LoC gegen das 250er-Limit).
`freeze_time` statt `_now_fn`-Naht bleibt gültig — die Datei nutzt genau dieses Muster bereits.

### Schnappschuss-Datum: AC-5 wird präzisiert, nicht gebrochen

`:1020` lädt `load_dated(trip.id, today)` mit der Anker-Variable aus `:911`, unabhängig davon,
aus welchem Tag das gewählte Segment stammt; `_briefing_precip_for_onset` matcht nur auf
`segment_id` (`:873-874`), nicht auf ein Datum. Stammt `active` von gestern, trifft der
Vergleich den gleichnamigen Eintrag des heutigen Schnappschusses und unterdrückt den gerade
gewonnenen Alarm still.

AC-5 (`:461-524`) sichert heute zu, dass Segmentwahl und Schnappschuss **denselben Ortstag**
lesen — bewiesen aber nur am Ein-Etappen-Trip ohne Gestern-Verzweigung. Die Zusicherung muss
lauten: *dasselbe Datum wie das, dem das tatsächlich gewählte Segment entstammt*. Umsetzung:
`resolve_current_segment` gibt `tuple[TripSegment, date]` zurück, `:1020` nutzt das
Segment-Datum. AC-5s eigene Fixture bleibt davon unberührt.

### Briefing-Pfad: ausdrücklich KEIN Vortags-Fallback

Die in der Analyse offen gelassene Frage ist entschieden — **ausschließen**, mit Begründung:

- `_get_target_date` (`trip_report_scheduler.py:689-713`) ist strikt vorwärtsgerichtet:
  morgens Ortstag, abends `today + 1`.
- `_build_starkregen_hint` bekommt Segmente, die für `target_date` gebaut wurden (`:907`,
  `:1483`); Kopfdaten kommen aus `trip.get_stage_for_date(target_date)` (`:1054-1056`). Ein
  Vortags-Fallback dort erzeugte ein Briefing mit heutiger Etappe im Kopf und gestriger
  Koordinate im Regenhinweis — ein **neuer** Inkonsistenzfehler, keine Reparatur.
- Live-Überwachung eines noch laufenden Vortagssegments ist Aufgabe von `check_radar_alerts`
  (alle ~15 min), nicht der zweimal täglichen Briefing-Erzeugung.

Im Scheduler bleibt damit nur die Docstring-Korrektur `:1395-1396` (und optional die
Deduplizierung über den geteilten `select_active_segment`-Baustein, falls das LoC-Limit es
hergibt).

### Risiken — gemessen, gegenüber der Analyse präzisiert

- **`alert_daily_limit`** (`:61-74`) ist **user-scoped**, nicht trip-scoped, mit Reset nach
  Wiener Kalendertag (unabhängig vom Ortstag — eigene Altlast, nicht S3). Ein Wrap-Trip, der
  bisher nichts verbrauchte, kann jetzt das geteilte Tagesbudget belegen. Gewollt, zu benennen.
- **Provider-Last:** unverändert **ein** `get_nowcast` pro Trip pro Lauf — die Vorrangkette
  liefert höchstens ein Segment.
- **Doppel-Aktivierung:** kein Risiko bei sequenzieller Kette mit Kurzschluss. Der
  Throttle-Schlüssel ist ohnehin `trip.id` (`alert_gate.py:71-111`), nicht das Segment.
- **`check_nowcast_gate` (#1467 S3):** unberührt — S3 ändert nur, *ob* ein Segment in die
  Gate-Prüfung eintritt, nicht die Gate-Logik.

### Zuschnitt-Fazit

Der technische Ansatz der Analyse trägt unverändert. Geändert haben sich: die **Begründung**
des zweiten Kernbefunds (verengtes 60-Minuten-Fenster statt durchgängiger Falsch-Ortung), die
**Test-Ablage** (CI-laufende `tests/tdd/`-Datei statt neuer `tests/unit/`-Datei) und die
**Entscheidung zum Briefing-Pfad** (ausgeschlossen statt offen). Scope-Schätzung ~190 LoC
bleibt plausibel, eher am unteren Rand, weil #1697 den Horizont-Guard in beiden Kopien und
`trip_local_today` als geteilten Baustein bereits mitgebracht hat.
