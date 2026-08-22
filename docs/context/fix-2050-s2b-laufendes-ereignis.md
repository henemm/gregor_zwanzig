# Context: fix-2050-s2b-laufendes-ereignis

Issue #2050, Scheibe **S2b** — Szenario 1, Anforderung **B-1**.
Erstellt 2026-08-22. Vorgaenger: S1 (Pruefstrecke) und S2a (Waechter Szenarien 2+3), beide geliefert.
Stand nach Rebase auf `origin/main` inkl. Merge `5e92e053` (#2020 Scheibe 2).

## Request Summary

Laeuft ein Niederschlags-/Gewitterereignis zum Zeitpunkt des Alarmlaufs **bereits**, darf die
Nachricht es nicht als bevorstehend melden ("Regen in 8 Min"). Sie muss es als laufend ausweisen
und das **Ende** nennen statt des Beginns — oder gar nicht ausloesen.

## Ursache (an Produktionsdaten belegt)

Zwei unabhaengig belegte Fakten ergeben zusammen den Defekt:

1. **Der Filter verwirft die laufende Viertelstunde.**
   `src/services/radar_service.py:712` — `window = [f for f in frames if f.timestamp >= now and ...]`.
   Frames tragen den **Slot-Start** als Zeitstempel (15-Min-Raster: `:00/:15/:30/:45`). Das Frame,
   das die *aktuelle* Viertelstunde beschreibt, liegt damit immer vor `now` und faellt heraus.
   `onset_minutes` (`:719-727`) wird ausschliesslich aus diesem `window` gebildet, danach
   `max(0, round(delta))` — ein "laeuft bereits" ist strukturell nicht darstellbar.

2. **Der Alarmtakt macht die Zahl konstant.**
   Cron `:07,:22,:37,:52` gegen Raster `:00/:15/:30/:45` ⇒ das verworfene Frame ist stets genau
   **7 Minuten alt**, das naechste stets genau **8 Minuten** entfernt. "in 8 Min" ist deshalb nicht
   der gemessene Wert, sondern der **einzige moegliche** Wert, wenn der Regen gerade laeuft.
   Der Vorfall vom 21.08. 18:37 zeigt exakt diese Zahl.

**Empirischer Beleg** (Prod-Mitschnitt, 2026-08-22): Datei
`/var/lib/gregor/debug/alert_input/nowcast/46.6843_12.4937_inca_20260822T071602783389.json` —
`captured_at = 07:16:02`, erstes Frame `timestamp = 07:15:00`. Das Frame der laufenden
Viertelstunde ist vorhanden und wird verworfen.

Der Mitschnitt wird von `_capture_nowcast_frames()` (`radar_service.py:918-935`, #1948 S1)
**vor** `_derive_result` geschrieben — die Rohdaten des Vorfalls waeren dort sichtbar gewesen.
Aufbewahrung: 50 Dateien je Ort (`alert_input_capture.py:38-44`), reicht keine 24 Stunden;
der Mitschnitt vom 21.08. ist bereits geloescht. Der Nachweis haengt nicht daran, weil der
Defekt in jedem Lauf strukturell sichtbar ist.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py:697-760` | `_derive_result` — Ursprung von `onset_minutes`, Filter + Klemme |
| `src/services/radar_service.py:137-190` | `NowcastResult` — Datenmodell, kennt keinen Laufend-Zustand |
| `src/services/radar_service.py:121` | `RADAR_ONSET_THRESHOLD_MIN = 55` — Meldeschwelle (gehoert zu A-1, **nicht** zu dieser Scheibe) |
| `src/services/radar_service.py:69` | `_NOWCAST_HORIZON_MIN = 180` — Sichtfenster |
| `src/services/radar_service.py:918-935` | `_capture_nowcast_frames` — Roh-Mitschnitt vor der Auswertung |
| `src/services/trip_alert.py:145,1365,1382` | `radar_alert_due`, Nowcast-Aufruf, `_onset_dt = now + onset_minutes` |
| `src/services/radar_alert_service.py:34-72` | Baut `OnsetEvent` aus `onset_minutes` |
| `src/services/compare_radar_alert.py:62-73,342` | Ortsvergleich: Dedup/Identity, kein eigener Text |
| `src/output/renderers/alert/model.py:72-110` | `OnsetEvent` — kennt kein Laufend-/Ende-Feld |
| `src/output/renderers/alert/render.py:497` | `_onset_time_label` — der B-1-Wirkort |
| `src/output/renderers/alert/project.py:360-430` | Ortsvergleich-Projektion, speist dieselben Renderer |
| `src/output/renderers/email/starkregen_hint.py:27` | Trip-Briefing, Kurzfrist-Zusatzzeile |
| `src/services/validator_render_service.py:100-270` | Replay-Weg, ruft die Renderer unveraendert auf |
| `tests/helpers/alarm_pruefstrecke.py` | Pruefstrecke aus S1 — Einspeisung + vier Kanaele |

## Wirkkette "in X Min" — sechs Formatierer

| Ort | Kanal | Form heute |
|---|---|---|
| `render.py:376` `_render_subject_onset` | Betreff (alle Kanaele) | `in {onset_minutes} Min` |
| `render.py:~525` `_render_email_onset_multi` | E-Mail Buendel/Ortsvergleich | `in {onset_minutes} Min` |
| `render.py:~599` `_render_email_onset` | E-Mail Ein-Ort | `ab {_onset_time_label(e)}` |
| `render.py:~665` `_render_telegram_onset` | Telegram (rich) | `in {onset_minutes} Min` |
| `email/starkregen_hint.py:27` | Trip-Briefing E-Mail | `ab ca. HH:MM (in ~N Min)` |
| `radar_service.py:450` `format_now_text` | `/jetzt`-Antwort (On-Demand) | `(in ~N Min)` |

`_render_sms_onset` nutzt seit #1948 S4 die **Zeitpunkt-Form** (`R@18:45`).
Telegram-Kurzform (`notification_service.py:1494`) und Premium-SMS
(`output/channels/premium_sms.py:19-21`) senden diesen SMS-Text unveraendert weiter.

🔴 **Wichtige Praezisierung:** Die Zeitpunkt-Form macht SMS/Premium-SMS/Telegram-Kurzform
**nicht** konform. `R@18:45` stammt aus demselben falschen `onset_minutes` und behauptet bei
laufendem Regen ebenso einen Beginn in der Zukunft — nur anders formuliert. Der Defekt sitzt
**unterhalb** der Formatierer. Alle vier Kanaele sind betroffen.

## Der Stand nach #2020 Scheibe 2 (Merge `5e92e053`)

Zwei Befunde, die den Zuschnitt bestimmen:

1. **Die neuen Ende-/Restmengen-Felder haengen am falschen Ereignistyp.**
   `remaining_mm`, `remaining_until_time`, `remaining_until_day_offset`, `remaining_until_weekday`,
   `window_end_time`, `window_end_day_offset` sitzen an **`AlertEvent`** (`model.py:50-70`) — dem
   Vorhersage-/Abweichungspfad. **`OnsetEvent`** (`model.py:72-110`, der Radar-Pfad) hat sie nicht.
   Der Zuschnitt von S2b schrumpft dadurch **nicht**; es gibt aber ein fertiges Vorbild fuer
   Benennung, Defaults und die Trennung "Projektion rechnet, Renderer setzt Worte".

2. **Die zu brechende Annahme steht jetzt ausformuliert im Code.**
   `_onset_time_label` (`render.py:497-511`) traegt den Kommentar:
   *"`OnsetEvent` kennt kein Vergangenheits-Kennzeichen (Radar blickt nach vorn), daher
   `is_past=False`."* Genau diese Praemisse ist falsch und ist der Kern von B-1. Der gemeinsame
   Baustein `_time_with_day(zeit, offset, is_past=...)` existiert bereits und wird von beiden
   Pfaden genutzt — der Laufend-Fall kann darauf aufsetzen statt einen eigenen Formatierer zu bauen.

## Existing Patterns

- **Pruefstrecke (S1):** `AlarmPruefstrecke(user_id=..., settings=...)`,
  `lauf(at=, zweig="radar"|"deviation"|"official", trip=, radar_service=, ...)` →
  `AlarmPruefstreckeLauf(triggered_count, mail, telegram, sms, premium_sms)`.
  Uhr ausschliesslich ueber `freeze_time(at)`. Kontinuitaet zwischen Laeufen kommt vom
  Datentraeger unter `get_data_dir(user_id)`, nicht von der Instanz.
- **Frame-Einspeisung:** eigener `RadarNowcastService` mit DI-Naht `frame_source=`, uebergeben
  als `radar_service=` (Muster aus S2a, Waechter 1).
- **Szenario-Waechter (S2a):** `tests/tdd/test_alarm_szenario_*.py` — `_uid()` mit uuid-Suffix,
  `_trip()`-Fabrik, `_stand(stunde)`-Wetterfabrik, ein Test je AC, Belege an der Wirkstelle
  gelesen (nicht am Aufrufer).
- **Additive Modell-Erweiterung** (#2009, #2046, #2036, #2020 S2): neues Feld mit Default, in der
  Projektion gerechnet, im Renderer nur Worte gesetzt — Normalfall byte-identisch.
- **Zeitpunkt-Form statt Countdown** ist im SMS-Zweig etabliert (#1948 S4) — Vorbild fuer die
  Formulierung des Laufend-Falls.

## Dependencies

- **Upstream:** Frame-Quellen (Brightsky/RADOLAN, GeoSphere INCA, AROME-FR-HD, ICON-D2, ARPAE,
  Open-Meteo `minutely_15`). Keine Quelle wird mit `past_minutes`/`past_hours`/`start_date`
  abgefragt; die Vergangenheit reicht genau so weit wie der laufende Rasterslot.
- **Downstream:** `trip_alert.py` (Trip-Alarme), `compare_radar_alert.py` (Ortsvergleich),
  `trip_report_scheduler.py` (Briefing-Zusatzzeile), `validator_render_service.py` (Replay),
  alle vier Kanal-Renderer.

## Existing Specs

- `docs/specs/modules/alarm_pruefstrecke.md` — S1, die Pruefstrecke.
- `docs/specs/modules/alarm_szenarien_waechter_2_3.md` — S2a, Szenarien 2 und 3.
- **Keine Spec zu B-1 / "laufendes Ereignis"** — S2b braucht eine neue.

## ADRs

Keine ADR zur Vorwarnzeit-Untergrenze und keine zum Laufend-Fall. `RADAR_ONSET_THRESHOLD_MIN`
und `_NOWCAST_HORIZON_MIN` sind reine Code-Konstanten. Es wird also **keine** dokumentierte
Entscheidung zurueckgenommen. Beruehrte Entscheidungsflaeche: ADR-0052 (Warnmail-Nowcast-Bauform),
ADR-0056 (rollierender Alarm-Anker) — vor der Spec gegenlesen.

## Risks & Considerations

- **R1 — Offene Produktfrage (PO-Entscheid).** Szenario 1 laesst zwei Ergebnisse zu: "als laufend
  melden mit Ende" **oder** "gar nicht ausloesen". Gehoert in die AC-Freigabe, nicht in eine
  technische Vorentscheidung.
- **R2 — Quellenreichweite.** Keine Quelle wird nach Vergangenheit gefragt. Die Erkennung
  "laeuft bereits" kann sich daher nur auf den laufenden Rasterslot stuetzen (max. 15 Min
  zurueck), nicht auf einen laengeren Rueckblick. Ein Ereignis, das vor mehr als einer
  Viertelstunde begann und noch laeuft, ist aus dem Nowcast allein nicht als "seit X laufend"
  belegbar — nur als "laeuft jetzt". Das begrenzt, was B-1 ueberhaupt zusichern kann.
- **R3 — "Ende" ist im Nowcast-Fenster nicht immer bestimmbar.** Das Sichtfenster endet nach
  180 Min (INCA liefert real ~11 Frames ≈ 165 Min). Regnet es bis ueber den Horizont hinaus,
  gibt es kein Ende zu nennen — der Fall braucht eine eigene Aussage, sonst entsteht wieder eine
  stille Falschbehauptung.
- **R4 — Testmasse.** Rund 15 Testdateien nageln den Wortlaut "in X Min" fest, weitere ~15
  haengen an `format_starkregen_hint`/`format_now_text`. Eine Wortlautaenderung zieht breite
  Testanpassung nach sich; das LoC-Budget ist entsprechend zu planen
  (`loc_limit_override` produktiv, `test_loc_limit_override` fuer Tests).
- **R5 — Abgrenzung.** `format_now_text` bedient `/jetzt` (On-Demand-Abfrage), nicht den
  proaktiven Alarm. Ob B-1 den Pfad mitmeint, ist in der Spec zu entscheiden. Ebenso liegt die
  55-Minuten-Meldeschwelle bei **A-1**, nicht bei B-1 — nicht mitverschieben.
- **R6 — Kurze Zeitfenster im Test.** Das Ziel-Segment hat einen erzwungenen 1-Stunden-Boden
  (`src/services/trip_segments.py:376-393`), Zwischensegmente nicht (`:242-306`). Ein
  "Regen laeuft schon"-Szenario baut man ueber ein Zwischensegment.
- **R7 — Nicht nur Regen.** `OnsetEvent.is_convective` deckt Gewitter/Hagel mit ab. Ein laufendes
  Gewitter faellt unter dieselbe Anforderung; die Spec darf nicht auf Niederschlag verengen.
