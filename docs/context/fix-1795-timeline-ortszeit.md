# Context: fix-1795-timeline-ortszeit

**Issue:** [#1795](https://github.com/henemm/gregor_zwanzig/issues/1795) · **Typ:** bug ·
**Track:** Full Process · **Stand der Messung:** 2026-08-13, HEAD `dbad9614`

## Request Summary

Die Telegram-/E-Mail-Antworten der Query-Familie (`glance`, `heute_gewitter`, `timeline_heute`,
`timeline_morgen`, `heute`, `morgen`) bestimmen ihren Kalendertag über den **Weltzeit**-Tag der
eingehenden Nachricht, und die Timeline gibt die Ankunftszeit **roh in Weltzeit** aus. Beides
muss auf die Ortszeit der Tour (ADR-0044) — und zwar **gemeinsam**, weil Filter und Anzeige
heute konsistent UTC sind.

Herausgeschnitten aus #1727 S5a mit ausdrücklicher Begründung
(`docs/context/fix-1727-s5a-befehlspfade.md:55-79`, `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md:105-113`).

## Der Befund in einem Satz

`_handle_query` berechnet `today`/`tomorrow` **einmal** (`trip_command_processor.py:503-504`,
`received_at.date()`) und speist damit **sieben** Verbraucher; `_fmt_timeline` formatiert den
UTC-Zeitstempel ungewandelt (`:948`, `:950`). Auf Korsika steht bei 08:00 Ortszeit `06:00`;
in Neuseeland liegt der Tag zwölf Stunden lang daneben.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py:503-504` | **Ursprung** — `today = received_at.date()`, der einzige verbliebene Rohzugriff im Modul |
| `src/services/trip_command_processor.py:812` | Tagesfilter `_aggregate_day`: `p.arrival_time.date() == target_date` |
| `src/services/trip_command_processor.py:938-941` | Tagesfilter `_fmt_timeline`, identisches Muster |
| `src/services/trip_command_processor.py:943, 948, 950` | Anzeige: Kopfzeile + zwei rohe `f"🕐 {p.arrival_time:%H:%M}"` |
| `src/services/trip_command_processor.py:879-897` | `_fmt_glance` — `{today:%d.%m}`-Beschriftung ×4 |
| `src/services/trip_command_processor.py:898` | `_fmt_gewitter` — dito |
| `src/services/trip_command_processor.py:980-985` | `_timeline_buttons`, filtert indirekt über `_aggregate_day` |
| `src/services/trip_command_processor.py:274-306` | `_fetch_and_save_snapshot` — schreibt `target_date` als **Schlüssel** (s. „Gemeinsamer Datenträger") |
| `src/services/trip_command_processor.py:566-597`, `:240-272` | `_trigger_on_demand` / `_on_demand_failure_body` — Datum nur im Fehlertext |
| `src/services/trip_report_scheduler.py:922` | `send_on_demand_report` — soll den benutzten Zieltag **zurückgeben** |
| `src/services/trip_report_scheduler.py:1040-1042` | `_send_trip_report_outcome` kennt den Zieltag bereits (ortszeitrichtig seit #1724) |
| `src/services/trip_day.py:29-96` | Die geteilten Bausteine — `trip_tz`, `display_tz`, `anchor_tz`, `trip_local_now`, `trip_local_today` |
| `src/utils/timezone.py:106-125` | `_as_utc`, `local_dt`, `local_hour`, `local_fmt` |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Die Regel — **Restliste ist veraltet** (s. „Risks") |

## Existing Patterns — das Muster liegt fertig da

**Im selben Modul, eine Bildschirmseite weiter oben:** `_day_window` (`:740-779`) löst
`anchor_tz(trip, received_at)` auf, leitet daraus `day_date` und `display_tz(trip, day_date)`
ab und **gibt die Zone im Tupel zurück** (`(from_time, hours, day_date, tz)`), damit Aufrufer
sie durchreichen statt sie ein zweites Mal zu holen (Docstring `:763-766`). Konsument:
`_format_drilldown:800` — `local_fmt(pt.ts, tz)`. Genau das fehlt der Timeline-Seite.

**Identisches Feld, bereits ortszeitrichtig:** `src/output/renderers/trip_report.py:159` —
`arrival_date = local_dt(last_seg.segment.end_time, self._tz).date()`. Das ist dasselbe
`segment.end_time`, das als `TimelinePoint.arrival_time` in die Timeline geht.

Weitere Vorlagen: `src/output/renderers/day_window.py:153-156` · `src/services/briefing_slots.py:228`
· `src/output/renderers/email/compare_html.py:1135`.

**Eine eigene Kopie der Zonen-Auflösung ist laut ADR-0044 ein Regelverstoß.** `trip_local_now`
(`trip_day.py:74-88`) existiert genau dafür, Tag und Ortsstunde aus **einer** Auflösung zu ziehen.
Die Importe stehen bereits (`trip_command_processor.py:23-24`).

## Datenmodell — gemessen, nicht aus Annotationen gelesen

- `TimelinePoint` (`weather_extractor.py:39-43`): `arrival_time`, `elevation_m`, `label`, `metrics`.
  **Kein `ts`** — das gibt es nur am `DrilldownPoint`.
- `arrival_time = seg.segment.end_time` (`weather_extractor.py:95`) ist **aware UTC**:
  `trip_segments.py:183-192` stempelt die Ortszone auf die Wanduhrzeit und rechnet nach UTC;
  `TripSegment` hat kein `__post_init__`, das die `tzinfo` strippt; die Serialisierung
  (`weather_snapshot.py:269-270/345-346`) erhält sie. Empirisch in einer echten Snapshot-Datei:
  `"start_time": "2026-08-12T06:00:00+00:00"`.
- **Die Hausnorm „naive UTC" (#1345) gilt hier NICHT** — sie betrifft `ForecastDataPoint.ts`
  (`app/models.py:211-222`).
- `local_dt` verträgt beides: `_as_utc` (`utils/timezone.py:106-110`) deutet naive Werte als UTC,
  aware Werte werden konvertiert. Der Ortstag-Filter ist damit für `arrival_time` und `ts`
  identisch schreibbar.
- `timeline()` liest die **undatierte** Datei `{trip_id}.json` und enthält Segmente **beider**
  Tage; die Tagestrennung passiert erst beim Formatieren — also genau an den zwei Filterstellen.

## 🔴 Gemeinsamer Datenträger — der Punkt, den das Ticket nicht nennt

`_fetch_and_save_snapshot` schreibt `WeatherSnapshotService.save(trip.id, …, today)`
(`:304`), und `save()` stempelt `target_date` in die **undatierte Ankerdatei** `{trip_id}.json`
(`weather_snapshot.py:73, 82`). Dieselbe Datei schreibt der Scheduler
(`trip_report_scheduler.py:1300`) — dort aber mit dem **Ortstag** (seit #1724). Gelesen wird sie
vom Alarm-Pfad: `trip_alert._get_cached_weather` vergleicht `load_target_date()` gegen
`trip_local_today()` und verwirft bei Ungleichheit mit `reason="wrong_day"`
(`trip_alert.py:616-637`). Der undatierte Anker ist dabei **kein Notnagel, sondern der reguläre
Nachtpfad** (#1661).

**Zwei Schreiber derselben Datei mit zwei Tagesbegriffen.** Damit ist die Lage strukturell
anders als die von S5a beschriebene „Anzeige-Divergenz ohne gemeinsamen Datenträger"
(`fix_1727_s5a_befehlspfade_ortstag.md:262-267`) — jene Aussage galt für den S5a-Zuschnitt und
bleibt dort richtig, trifft aber auf `_handle_query` nicht zu.

### ✅ Empirisch belegt (Analyse-Phase, Wegwerf-Probe ohne Netz)

Trip in Wellington (`Pacific/Auckland`, im August UTC+12, kein DST), `now_utc = 2026-08-13T13:00Z`
⇒ UTC-Tag `2026-08-13`, `trip_local_today()` `2026-08-14` (echtes Mismatch-Fenster).

- Anker mit `target_date = now_utc.date()` (der Weg, den `_fetch_and_save_snapshot` heute nimmt)
  ⇒ `_get_cached_weather(..., tagesgleicher_anker_noetig=True)` liefert **`None`**, Log:
  `Alarm-Anker … verworfen (wrong_day) — falscher Tag: target_date=2026-08-13, heute ist 2026-08-14`.
- Gegenprobe mit `target_date` = Ortstag ⇒ Anker kommt durch (1 Segment).

Die Kette schlägt also tatsächlich durch, nicht nur am Code gelesen.

**Ehrliche Eingrenzung des Schadens:** `_fetch_and_save_snapshot` läuft **nur**, wenn kein
Snapshot ladbar ist (`:518` `if not timeline.available`). Im Regelfall legt der Befehlspfad
deshalb einen Anker an, wo keiner war — er überschreibt keinen guten. Die Folge ist dann nicht
„Alarm bricht weg, wo er vorher lief", sondern: der neu angelegte Anker trägt im Mismatch-Fenster
einen Tag, den der Alarm-Pfad sofort verwirft — eine verpasste Reparatur, kein Rückschritt.

🔴 **Diese Entwarnung gilt nicht absolut.** `WeatherSnapshotService.load()` (`weather_snapshot.py:196-226`)
gibt bei **jeder** Lesestörung `None` zurück (`JSONDecodeError`, `ValueError`, `KeyError`, `OSError`),
nicht nur bei fehlender Datei — und `save()` (`:61-86`) schreibt **nicht atomar**
(`filepath.write_text(...)`, kein Temp-File mit Rename). Eine an sich gute, korrekt datierte
Ankerdatei, die gerade unlesbar ist, führt damit ebenfalls auf `not timeline.available` und wird
überschrieben. Schmaler, **vorbestehender** Fall, nicht durch #1795 verursacht — aber „überschreibt
keinen guten Anker" ist als Absolutsatz falsch.

## Dependencies

**Upstream (was wir benutzen):** `services.trip_day` (`anchor_tz`, `display_tz`,
`trip_local_today`, `trip_local_now`) · `utils.timezone` (`local_dt`, `local_fmt`) ·
`WeatherExtractor.timeline` · `WeatherSnapshotService`.

**Downstream (was von uns abhängt):**

- **Zwei Einstiege, beide über `TripCommandProcessor.process`:** Telegram
  (`inbound_telegram_reader.py:191-245`) und E-Mail (`inbound_email_reader.py:144-153`).
  **SMS/Premium-SMS haben keinen Kommandopfad** (`inbound_sms_reader.py`, Kommentar
  `trip_command_processor.py:967-968`). Eine Umstellung in `_handle_query` deckt beide ab.
- `received_at` stammt in beiden Fällen von der **Serveruhr** (`datetime.now(tz=timezone.utc)`),
  nicht vom Telegram-`date`-Feld — aware UTC.
- **Callback-Buttons tragen kein Datum:** `tl_today`/`tl_tomorrow` werden über
  `_CALLBACK_QUERY_MAP` (`inbound_telegram_reader.py:61-62`) in `### query: …` übersetzt und
  mit **frischem** `now_utc` (`:320`) erneut durch `_handle_query` geschickt. Ein Ortstagwechsel
  zwischen Anzeige und Klick verschiebt die Antwort also gewollt-relativ; es gibt keinen
  eingefrorenen Token, der nachgezogen werden müsste.
- `send_on_demand_report` hat **genau einen** Produktiv-Aufrufer
  (`trip_command_processor.py:580`, Behandlung `if outcome != "sent"`), dazu 8 Test-Aufrufstellen;
  eine davon ist eine Signatur-/Vertragsliste (`tests/tdd/test_briefing_slot_idempotenz.py:1087`).

## Existing Specs & ADRs

- `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` — die Regel
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` — Regel 3: kein Systemuhr-Default
- `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md` — Vorgänger-Scheibe, „Nicht in dieser Scheibe" `:105-113`
- `docs/context/fix-1727-s5a-befehlspfade.md` — Zuschnitt-Entscheid `:55-79`, offene Punkte `:277-307`
- `docs/context/fix-1697-ortstag-statt-servertag.md` — Fundstellen-Karte nach Wirkung

## Bestehende Wächter — was mitgezogen werden muss

| Wächter | Bindung | Verhalten bei #1795 |
|---|---|---|
| `tests/test_success_status_guard.py:1622-1632`, `:1839`, `:1930` | Schlüssel `pfad::funktion::**ordinal**` — **keine Zeilennummern** (`_number_findings`, `:1312-1345`) | **Kein Nachzug**, solange `_handle_query` seine **vier** `success=True`-Rückgaben in gleicher Reihenfolge behält (`return` bei `:525`, `:534`, `:542`, `:551`). Nur ein neuer **literaler** `success=True` verschiebt Ordinale — ein `success=<Variable>` wird vom Detektor gar nicht erfasst (`_asserts_constant_success`, `:691-724`; `False` fehlt in `_SUCCESS_LITERALS`, `:220`). 🔴 **Spec-Auflage: `_handle_query` NICHT zerlegen** — bei sieben `tz`-Argumenten ist das verführerisch und bricht `:1622-1632` + `:1839` (=4) + Summenprüfung `:1930` (33/42) auf einen Schlag |
| `tests/test_output_timezone_guard.py` | 9 AST-Muster + Aufrufstellen-Prüfung; `trip_command_processor.py` steht auf der Scanfläche (`:111`) | **Keine `KNOWN_VIOLATIONS`-Einträge mehr** für die Datei — S5a hat die letzten zwei entfernt. Also: nichts zu streichen, aber **nichts Neues einführen** (kein rohes `.astimezone()`, kein `date.today()`, kein Zonenliteral) |
| — | — | **Warum der Wächter #1795 nicht sehen konnte:** ein `ast.JoinedStr` ohne Umrechnung ist keins der neun Muster. Der Fehler ist eine *fehlende* Operation, und Abwesenheit ist syntaktisch nicht von „Wert ist schon lokal" zu unterscheiden (Modul-Docstring `:66-77`) |

**Keine der berührten Dateien steht in `.github/ci_tdd_excludes.txt`** — alle einschlägigen
Wächter laufen in CI.

## 🔴 Tests, die durch die TAG-Umstellung rot werden

**Drei** Bestandsdateien, nicht zwei — die dritte fiel erst in der Analyse-Phase auf. Alle sind
**echte Folgearbeit**, kein Kollateralschaden zum Wegdrücken:

| Datei | Warum | Wirkung |
|---|---|---|
| `tests/tdd/test_thunder_origin_four_places.py:206-236` | Fixtur `kommando` nutzt `datetime.now(tz=timezone.utc)` und legt die Etappe auf den **UTC**-Tag; Koordinaten `47.0, 12.0` (`:91`) = Europe/Vienna | `_aggregate_day` findet nichts. Trifft `:423`, `:435`, `:492`, `:509`, `:526`, `:705` |
| `tests/tdd/test_thunder_origin_trip.py:192-219` | **Dritte Fixtur, gleiches Muster**, Koordinaten `:64`, Segmente 06:00–17:00 UTC (`:108-122`) | Zusicherungen `:249`, `:286`, `:343`, `:395`, `:400`, `:424` auf `⛈ Gewitter heute ({heute:%d.%m})` mit `heute` = UTC-Tag |
| `tests/tdd/test_issue_1007_heute_voll_briefing.py` | `date.today()` an sieben Stellen (`:248`, `:280`, `:294`, `:322`, `:343`, `:365-366`, `:397`, `:446`), dazu `assert today_str in html` (`:280-283`); Koordinaten `47.2692, 11.4041` | Trägt `pytestmark = pytest.mark.email` (`:43`) — **fällt in der Standard-Lane nicht auf**. Ist im selben Fenster **schon heute** brüchig, weil `_get_target_date` seit #1724 den Ortstag nimmt; #1795 macht es nur sichtbar |

**Das Mismatch-Fenster ist jahreszeitabhängig:** für Europe/Vienna im **Sommer** (CEST, UTC+2)
22:00–24:00 UTC, im **Winter** (CET, UTC+1) nur 23:00–24:00 UTC. Die Breite ist stets
|UTC-Offset| Stunden. Dass `date.today()` auf diesem Rechner dem UTC-Tag entspricht, ist belegt:
Server steht auf `Etc/UTC` (`timedatectl`), CI läuft auf `ubuntu-latest` (Default UTC), und der
Code sagt es an drei Stellen unabhängig (`trip_command_processor.py:1143`,
`trip_report_scheduler.py:786-787`, `compare_location_weather_source.py:79`).

**Die Reparatur ist in allen drei Fällen dieselbe:** auf einen festen, zonensicheren Zeitpunkt
einfrieren statt `datetime.now()`. Das ist derselbe Fixturen-Fehler, den ADR-0044 und #1726 F002
beschreiben — nur diesmal in der Gegenrichtung sichtbar.

Die 🕐-**Uhrzeit** macht dagegen keinen Bestandstest rot: `_timeline_gewitter`
(`test_thunder_origin_four_places.py:242-249`) liest nur Zeilen mit `⛈` **und** `🌡`, nie die
🕐-Zeile, und keine Assertion im Repo greift auf `Timeline ·` zu.

## Nachweis-Bausteine, die schon existieren

- `tests/tdd/conftest.py:51-76` — `WP_NZ` (Wellington, im August UTC+12), `WP_KORSIKA` (UTC+2),
  `trip_two_zones(day0)` mit drei Etappen über zwei Zonen.
- `tests/tdd/test_befehlspfade_folgen_ortszone.py:49-70` — `PAGO` (UTC−11), `KIRITIMATI` (UTC+14),
  `LA`, sowie `NACHTS_UTC` / `MITTAGS_UTC` (Mismatch-Fenster). **Liegen lokal, nicht in der
  conftest** — beim Wiederverwenden heben statt kopieren.
- `_anker(now_utc, zone, erwarteter_ortstag)` (`:100-118`) — Pflicht-Vorbedingung, die misst,
  dass Ortstag ≠ Weltzeit-Tag **und** ≠ `date.today()` (Fehlerklasse #1726 F002).
- `test_befehlspfade_folgen_dem_parameter_nicht_der_systemuhr` (`:517-670`) — die Vorlage gegen
  „Parameter behalten, im Rumpf ignorieren": zwei literal getrennte Erwartungen, Selbstprüfung
  auf Verschiedenheit (`:637`), `freeze_time`-Wirksamkeitsanker (`:651`).

## Risks & Considerations

- **🔴 Sommerzeit ist hier schärfer als in S5a.** S5a durfte sich auf einen exemplarischen Tag
  beschränken, weil es eine reine *Datums*bestimmung war (`fix-1727-s5a-befehlspfade.md:270-275`).
  #1795 stellt zusätzlich die **Uhrzeit-Anzeige** um — ADR-0044 verlangt dafür ausdrücklich
  **beide** Wechseltage. Die S5a-Suite deckt **keinen** ab (alle Daten 19.–23.08.2026).
- **Der gefährliche Schnitt geht in BEIDE Richtungen** (Challenger-Befund — das Ticket warnt nur
  vor einer). Wird nur der **Tag** gezogen, vergleicht der Filter einen Ortstag gegen
  UTC-Zeitstempel ⇒ „Keine Etappe geplant", der Bruch aus #1697. Wird nur die **Uhrzeit**
  lokalisiert, bleibt die Punktmenge zwar stimmig, aber die Nachricht trägt dann zwei
  Zeitbegriffe: Kopfzeile `📋 Timeline · Heute (20.08.)` (UTC-Tag, `:945`) über Zeilen
  `🕐 00:30` (Ortszeit, `:948`). Vorher UTC-konsistent-aber-falsch, nachher
  lokal-korrekt-aber-tagesinkonsistent — genau wovor ADR-0051 warnt.
- **Zone einmal auflösen und durchreichen.** Fünf Formatierer (`_aggregate_day`, `_fmt_glance`,
  `_fmt_gewitter`, `_fmt_timeline`, `_timeline_buttons`) haben heute **keinen** `tz`-Parameter.
  Eine zweite Auflösung im Rumpf wäre der von ADR-0044 verbotene Zweitauflöser.
- **`send_on_demand_report` ist mit `-> bool` annotiert, liefert aber einen Outcome-String**
  (`trip_report_scheduler.py:922` gegen Docstring `:934-940`). Die Annotation ist seit #1007
  falsch. Sie wird für den Rückgabe-Zieltag ohnehin angefasst.
- **Nur zwei Outcomes rendern überhaupt ein Datum:** `no_weather` (`:250-254`) und
  `no_stage`/Default (`:272`). `no_channels` und `channels_unreachable` nicht, der Erfolgsfall
  auch nicht.
- 🔴 **Die Begründung für den Rückgabe-Zieltag war falsch dokumentiert** (Challenger-Befund).
  Sie lautete „sonst entsteht eine zweite `today`-Definition" — das stimmt seit S5a nicht mehr:
  `_trigger_on_demand` (`:566-597`) bekommt `target_date` als **Parameter** und löst nichts
  selbst auf. Die tatsächliche Begründung ist eine andere: `_send_trip_report_outcome`
  bestimmt seinen Zieltag intern über `datetime.now(timezone.utc)` zum **Ausführungs**zeitpunkt
  (`trip_report_scheduler.py:1040-1042`), nicht über `received_at`. Trifft eine Nachricht knapp
  vor und der Versand knapp nach der Ortsmitternacht, nennt der Antworttext einen anderen Tag
  als den versandten. Der Rückgabe-Zieltag schließt genau diese Lücke.
- **ADR-0044s Restliste ist veraltet:** sie führt `_show_status`, `_show_now` und `command_date`
  noch als offen, obwohl S5a genau die geliefert hat (letzte Änderung am ADR: `fa53c4a3`/#1726).
  Das ADR warnt selbst davor — „eine unvollständige Restliste liest sich wie eine vollständige".
  Mit #1795 nachziehen.
- **Nachweiskosten über Implementierungskosten.** S5a: Produktivcode +74/−20, Gesamt-LoC 800.
  Hier kommen beide Sommerzeittage und die Reparatur zweier Bestandsfixturen dazu — **LoC-Limit
  250 wird nicht reichen**, Override früh und begründet einplanen statt dreimal nachschätzen.
- `data/` muss untracked bleiben.

---

# Analysis

## Type

**Bug.** Nutzersichtbares Fehlverhalten (falsche Uhrzeit, falscher Tag) mit einem
Persistenz-Anteil (Anker-Schlüssel). Kein Feature.

## 🔴 Neuer Befund der Analyse-Phase: der Anker deckt strukturell nur EINEN Tag ab

Gemessen mit einer Wegwerf-Probe: `_send_trip_report_outcome` berechnet **genau einen**
`target_date` (`trip_report_scheduler.py:1040-1043`) und schreibt daraus **ein** Tages-Set in die
undatierte Ankerdatei (`:1300`). `_fetch_and_save_snapshot` ist der **einzige** Schreiber, der
beide Tage holt (`trip_command_processor.py:297-299`) — und er läuft nur, wenn gar kein Snapshot
ladbar ist (`:518`).

**Folge:** Sobald der Scheduler einmal einen Anker geschrieben hat, wird der Zwei-Tage-Abruf nie
wieder ausgelöst. Der Anker trägt dann je nach letztem Lauf entweder heute (Morgen-Briefing) oder
morgen (Abend-Briefing) — **nie beides**. Probe bestätigt: `timeline_morgen` antwortet
„Morgen (14.08): Keine Etappe geplant", obwohl die Etappe im Trip existiert.

**Das ist ein eigenständiger, vorbestehender Defekt — keine Regression durch #1795**, und die
Ortstag-Umstellung verschiebt nur, *welcher* der beiden Tage fehlt.

🔴 **Konsequenz für die Spec:** Ein AC der Form „`timeline_morgen` zeigt nach dem Fix die morgige
Etappe" wäre mit einem gewöhnlichen Scheduler-Anker **strukturell nie grün** — unabhängig von
einer korrekten Implementierung. Die ACs müssen sich auf die **Filter- und Formatierlogik**
beziehen (welcher Tag wird verglichen, welche Zone wird angezeigt), und der Testaufbau muss den
Anker explizit mit beiden Tagen bestücken. Der Defekt selbst gehört in ein **eigenes Issue**
(Triage a: nutzersichtbares Fehlverhalten).

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `_handle_query` (eine Auflösung, zwei Zonen), `_trigger_on_demand`, `_aggregate_day`, `_fmt_glance`, `_fmt_gewitter`, `_fmt_timeline`, `_timeline_buttons`, `_fetch_and_save_snapshot` |
| `src/services/trip_report_scheduler.py` | MODIFY | `OnDemandErgebnis`-NamedTuple, `send_on_demand_report`, optionaler `target_date`-Parameter an `_send_trip_report_outcome` |
| `tests/tdd/test_timeline_folgt_der_ortszeit.py` | CREATE | Neue Suite (~17 Tests) |
| `tests/tdd/conftest.py` | MODIFY | DST-Fixtur (Europe/Paris, beide Wechseltage) heben |
| `tests/tdd/test_thunder_origin_four_places.py` | MODIFY | Fixtur einfrieren |
| `tests/tdd/test_thunder_origin_trip.py` | MODIFY | Fixtur einfrieren |
| `tests/tdd/test_issue_1007_heute_voll_briefing.py` | MODIFY | `date.today()` an sieben Stellen einfrieren |
| `tests/tdd/test_briefing_slot_idempotenz.py`, `tests/tdd/test_issue_1087_trip_official_alerts.py` | MODIFY | Rückgabetyp nachziehen (`.outcome`) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | Restliste nachziehen (zählt nicht auf LoC) |

## Scope Assessment

- **Produktivcode:** ≈ **+100/−35** (`trip_command_processor.py` +73/−29, `trip_report_scheduler.py` +27/−6)
- **Testcode:** ≈ **760** (neue Suite ~650, Bestandsreparaturen ~110)
- **Gesamt ≈ 900 gezählte Zeilen** ⇒ **LoC-Override 1000** (Reserve für Adversary-Nachforderungen;
  S5a lag bei 848 und brauchte zwei nachträgliche Wächter)
- **Risiko: MEDIUM–HIGH** — kritischer Pfad, breite Anzeigeänderung, Persistenz-Anteil

## Technical Approach (Empfehlung)

**Zone einmal auflösen, als Pflichtparameter durchreichen** — Variante (a), nach dem Muster von
`_format_drilldown` (`:781-785`, dessen Docstring den Pflichtparameter ausdrücklich begründet):

```
local_now = trip_local_now(trip, received_at)      # EINE Auflösung
today     = local_now.date();  tomorrow = today + timedelta(days=1)
tz_heute  = display_tz(trip, today)
tz_morgen = display_tz(trip, tomorrow)
```

Die zwei `display_tz`-Aufrufe sind **keine** verbotene Zweitauflösung — genau das tut
`_day_window:770-779` heute schon (Anker bestimmt den Tag, `display_tz` die Anzeige *dieses*
Tages). Verboten ist die Kopie der Auflösungslogik im Rumpf eines Formatierers.

**Warum nicht Instanzzustand (`self._tz`):** damit lässt sich einem Formatierer im Test keine
*falsche* Zone unterschieben — „liest das Feld" und „löst selbst auf" sind von außen nicht
unterscheidbar. Mit explizitem Parameter greift die fertige S5a-Vorlage
`test_befehlspfade_folgen_dem_parameter_nicht_der_systemuhr` unverändert.

**`send_on_demand_report`:** `target_date: date | None = None` als optionaler Parameter an
`_send_trip_report_outcome` (**eine** Stelle, `:1039-1042`) statt die 465-Zeilen-Funktion
umzubauen; Rückgabe als NamedTuple `OnDemandErgebnis(outcome, zieltag)`. Ein NamedTuple ist nicht
`True` und fällt im Normalisierer `test_briefing_slot_idempotenz.py:1098-1103` in den else-Zweig
⇒ **laut rot, nicht still falsch**. Nebengewinn: `_trigger_on_demand` verliert seinen
`target_date`-Parameter, der `heute`/`morgen`-Zweig braucht `today`/`tomorrow` gar nicht mehr.

**Vier `_aggregate_day`-Aufrufstellen**, nicht drei: `:885`, `:886`, `:904`, `:985`. Eine
übersehene filtert weiter nach UTC und fällt nur im Mismatch-Fenster auf.

## Schnitt: EINE Scheibe

- **Tag zuerst** = der #1697-Bruch selbst. Ausgeschlossen.
- **Uhrzeit zuerst** = zwei Zeitbegriffe in einer Nachricht (s. Risks). Ausgeschlossen.
- **Entlang der Kommandos** = zwei `today`-Definitionen in `_handle_query`. Ausgeschlossen.
- **Rückgabe-Zieltag abtrennen** wäre technisch sauber (≈ +35/−10 Produktiv), kauft aber genau
  die Divergenz zurück, die S5a nach #1795 verwiesen hat, plus eine zweite Spec-, RED-,
  Adversary- und Staging-Runde. Der Override auf 1000 ist billiger.

## Nutzersichtbare Verhaltensänderungen (alle GEWOLLT, gehören in die Spec)

1. **Die 🕐-Spalte verschiebt sich für jeden Nutzer, jeden Tag** um den UTC-Offset (Korsika +2 h) —
   nicht nur im Mismatch-Fenster. Kein Golden-Test greift darauf zu; ohne ausdrückliche Nennung
   liest der nächste Leser das als Regression.
2. Die vier Query-Kommandos nennen im Mismatch-Fenster einen anderen Tag. Damit **endet** die
   Divergenz zu `/status`, die `fix_1727_s5a_befehlspfade_ortstag.md:260-266` als Known Limitation
   führt.
3. `_fetch_and_save_snapshot` schreibt den Anker künftig mit dem Ortstag ⇒ der Alarm-Leser
   verwirft ihn nicht mehr. Das **schaltet Alarme frei, die vorher nicht liefen** — ein Nutzer
   kann im Mismatch-Fenster nach einem `glance` plötzlich eine Alarm-Meldung bekommen.
   Zu **belegen**, nicht zu behaupten.

## Open Questions

- [x] Eigenes Issue für die einspurige Anker-Abdeckung angelegt: **#1818** (Triage a),
      Rückverweis in #1795 gebucht (`issuecomment-5281861125`).

## Offene Entscheidungen für die Spec

1. **Welche Zone für den Filter?** `anchor_tz(trip, received_at)` bestimmt den *Kalendertag*;
   für die *Anzeige* eines konkreten Tages ist `display_tz(trip, day_date)` das Vorbild
   (`_day_window:770-779` nutzt beide). Vorschlag: exakt dem `_day_window`-Muster folgen, damit
   Timeline und Drilldown derselben Nachricht garantiert denselben Tag meinen.
2. **`_fetch_and_save_snapshot`:** fällt der `target_date`-Schlüssel automatisch mit um (er hängt
   an derselben `today`-Variablen) — oder braucht er eine eigene AC, weil er ein
   **Persistenz**-Schlüssel ist und nicht nur eine Anzeige? Vorschlag: eigene AC, mit Bezug auf
   den Alarm-Leser.
3. **Rückgabe von `send_on_demand_report`:** Tupel `(outcome, target_date)` oder Dataclass?
   Trifft einen Produktiv-Aufrufer und acht Testaufrufe, davon eine Vertragsliste.
4. **Sommerzeit-Umfang:** beide Wechseltage × welche Zonen? Vorschlag: beide Tage in **einer**
   Zone mit Umstellung (Europe/Paris) plus die Zonenspreizung über Wellington/Korsika für den
   Tagesversatz — nicht das Kreuzprodukt.
5. **Bestandsfixturen einfrieren:** in dieser Scheibe mitreparieren (nötig für Grün) — aber als
   eigene ACs sichtbar machen, damit der Aufwand nicht als „Nebenbei" verschwindet.
