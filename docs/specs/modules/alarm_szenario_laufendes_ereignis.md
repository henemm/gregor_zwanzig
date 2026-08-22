---
entity_id: alarm_szenario_laufendes_ereignis
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
workflow: fix-2050-s2b-laufendes-ereignis
version: "1.0"
tags: [alarm, radar, nowcast, rendering]
---

# Laufendes Regen-/Gewitterereignis wird als laufend gemeldet (Scheibe S2b, Issue #2050)

## Approval

- [x] Approved — Product Owner, 2026-08-22 ("go"). Produktentscheidung: melden mit Ende;
      Variante "gar nicht melden" verworfen.

## Purpose

Läuft ein Regen- oder Gewitterereignis zum Zeitpunkt des Alarmlaufs bereits, meldet Gregor es
heute fälschlich als bevorstehend ("Regen in 8 Min") statt als laufend. Ursache: Der Radar-Zweig
geht an vier unabhängigen Stellen davon aus, dass ein Ereignis in der Zukunft liegt (Vorfall vom
21.08., Prod-Mitschnitt belegt). Diese Scheibe stellt das Ereignis als bereits laufend dar, nennt
das voraussichtliche Ende — oder sagt ausdrücklich, dass keines im Sichtfenster erkennbar ist —
und stellt sicher, dass der Alarm dabei weiterhin verschickt wird, entdoppelt bleibt und über
alle vier Kanäle sowie im Ortsvergleich korrekt erscheint.

## Source

- **File:** `src/services/radar_service.py` (`_derive_result`, `NowcastResult`, `format_now_text`)
- **Identifier:** `class NowcastResult`, `def _derive_result`

> Schicht: Python-Core (`src/services/`, `src/output/renderers/`) — kein Go-/Frontend-Anteil.
> Betroffen sind Domain-Logik (Radar-Nowcast, Trip- und Ortsvergleichs-Alarme) und deren
> Text-Renderer für alle vier Kanäle.

## Estimated Scope

- **LoC:** produktiv ~180-260 (⇒ `loc_limit_override` auf 300 nötig, Standardlimit 250), Tests
  ~150-250 (⇒ `test_loc_limit_override` vorsorglich setzen)
- **Files:** 10-12 (davon 2 neu: diese Spec, ein neuer Wächter-Testfile)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py::_derive_result` (`:700-`) | function | Ursprung von `onset_minutes`; hier entsteht die Laufend-Erkennung, wo Frames/Fenster/`now` bereits zusammenliegen |
| `src/services/radar_service.py::NowcastResult` (`:137-190`) | dataclass | Trägt die neuen additiven Roh-Felder für Laufend-Zustand und Ende |
| `src/services/radar_service.py::format_now_text` (`:~430-451`) | method | `/jetzt`-Antwort — muss dieselbe Laufend-Aussage tragen |
| `src/output/renderers/alert/model.py::OnsetEvent` (`:72-110`) | dataclass | Renderer-Vertrag; additive Felder analog `AlertEvent.remaining_until_time`/`window_end_time` (`:60-69`, Vorbild aus #2020 S2) |
| `src/output/renderers/alert/render.py::_time_with_day` (`:214-`) | function | Geteilter Tageswort-Baustein, den der neue Laufend-/Ende-Formatierer wiederverwendet statt einen eigenen zu bauen |
| `src/output/renderers/alert/render.py::_onset_time_label` (`:497-511`) | function | Trägt heute den fälschlichen Kommentar "Radar blickt nach vorn, daher `is_past=False`" — die zu brechende Prämisse |
| `src/output/renderers/alert/render.py` (`_render_subject_onset:474`, `_render_email_onset_multi:513`, `_render_email_onset`, `_render_telegram_onset:660`, `_render_sms_onset:711`) | function | Alle sechs Formatierer der Wirkkette "in X Min" — jeder muss verzweigen |
| `src/services/trip_alert.py::radar_alert_due` (`:145-148`) | function | Bruchstelle 1 — liefert heute `False` bei `onset_minutes is None`, sperrt den Alarm komplett |
| `src/services/trip_alert.py` (`:1382`, `:~1498`) | code | Bruchstelle 3 — Zeitableitung `now_utc + timedelta(minutes=result.onset_minutes)` stürzt bei `None` ab; `RadarAlertRequest`-Bau muss neue Felder durchreichen |
| `src/services/compare_radar_alert.py::_identity_inputs` (`:64-79`) | function | Bruchstelle 2 — `onset_at=None` macht die Entdopplung zum stillen No-Op |
| `src/output/renderers/alert/project.py` (`:494`, `:509-511`) | code | Bruchstelle 4 — Ortsvergleich-Filter `nc.onset_minutes is not None` wirft laufende Orte vor dem `OnsetEvent`-Bau heraus |
| `src/output/renderers/email/starkregen_hint.py::format_starkregen_hint` (`:18-27`) | function | Trip-Briefing-Kurzfristzeile, dieselbe "ab ca. HH:MM"-Aussage |
| `src/services/notification_service.py::RadarAlertRequest` | dataclass | `onset_minutes` wird optional, neue Felder müssen durchgereicht werden |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke.lauf` | function | Prüfstrecke aus S1 — alle Wächter dieser Scheibe fahren ausschließlich darüber, kein eigener Aufbau der Auslöseentscheidung |
| `docs/specs/modules/alarm_szenarien_waechter_2_3.md` | reference | Vorgänger-Scheibe S2a — Ton, Wächter-Muster und Fixture-Vorbilder (`_uid()`, `_trip()`, `frozen_active_window()`) |

## Implementation Details

**1. Erkennung** in `_derive_result`: Ein Ereignis läuft, wenn das Frame, dessen 15-Minuten-Slot
`now` enthält, über der Trockenschwelle liegt (Vorwärts-Konvention, wie sie `_accumulate_precip_mm`
für die Mengenrechnung bereits verwendet — keine neue Annahme, siehe "Offengelegte Annahme"
unten). `onset_minutes` bleibt unangetastet: Es behält seine Rolle als Torwächter und
Dedup-Bestandteil. Der Laufend-Zustand (`already_running: bool`) liegt additiv daneben und wird
unabhängig davon gesetzt, ob `onset_minutes` (weil der Regen in ein künftiges Frame hinein
andauert) noch einen Wert trägt oder `None` ist (weil der Regen innerhalb der laufenden
Viertelstunde endet).

**2. Ende:** das erste trockene Frame nach der laufenden nassen Strecke, als Minutenwert
(`running_until_minutes`) auf `NowcastResult`, nur gesetzt wenn `already_running`. Reicht der
Regen bis über den tatsächlichen Datenhorizont der Quelle hinaus (INCA liefert real ~165 Min,
nicht die vollen 180), bleibt `running_until_minutes` `None` und stattdessen wird die reale
Reichweite der Quelle als `nowcast_horizon_minutes` gesetzt — damit der Renderer "kein Ende
erkennbar (bis HH:MM)" sagen kann, ohne eine Dauer zu erfinden.

**3. `OnsetEvent`** (Renderer-Vertrag) bekommt dieselben Informationen als Klartext-Felder,
gebaut über den bestehenden Baustein `_time_with_day`: `already_running: bool = False`,
`running_until_time: str | None = None`, `running_until_day_offset: int = 0`,
`horizon_time: str | None = None`, `horizon_day_offset: int = 0`. Namensgebung analog zum
fertigen Vorbild `AlertEvent.remaining_until_time`/`window_end_time` aus #2020 Scheibe 2 — dort
ist dieselbe Unterscheidung "Ende bestimmbar" vs. "nur Fenster-Reichweite nennbar" bereits gelöst.

**4. Renderer:** ein geteilter Helfer neben `_onset_time_label`, der bei `already_running=True`
"läuft bereits" plus Ende-Aussage statt der Beginn-Angabe liefert. Alle sechs Formatierer der
Wirkkette (Betreff, E-Mail Einzelort/Bündel, Telegram-Langform, SMS-Token, `/jetzt`,
Briefing-Kurzfristzeile) verzweigen an ihrer bestehenden Stelle. Telegram-Kurzform und
Premium-SMS senden den SMS-Text unverändert weiter (bestehendes Muster seit #1948 S4) und
erhalten die Aussage damit automatisch mit.

**5. Die vier Bruchstellen** (`radar_alert_due`, `_identity_inputs`, die Zeitableitung in
`trip_alert.py`/`project.py`, der Ortsvergleich-Filter in `project.py`) müssen den
`already_running`-Fall explizit behandeln statt implizit über `onset_minutes is not None` zu
entscheiden — sonst bleibt der Fix auf halbem Weg stehen (Präzedenz: `onset_precip_mm` musste bei
#2046 an denselben Stellen nachgezogen werden).

**Offengelegte Annahme:** Welche Intervall-Konvention die Datenquellen (Brightsky/RADOLAN,
GeoSphere INCA, AROME-FR-HD, ICON-D2, ARPAE, Open-Meteo `minutely_15`) *extern* zusichern, ist aus
dem Code nicht belegbar. Die Erkennung übernimmt die Konvention, nach der die App ihre
Mengenrechnung bereits heute betreibt (ein Frame mit Zeitstempel T gilt vorwärts für das
Intervall ab T) — das ist in sich konsistent, aber eine Annahme, nicht extern zugesichert.

## Expected Behavior

- **Input:** Radar-Frames aus `_fetch_frames_with_fallback`, `now` (injizierbar über `_now_fn`),
  Sichtfenster `_NOWCAST_HORIZON_MIN`.
- **Output:** `NowcastResult` mit den additiven Feldern `already_running`,
  `running_until_minutes`, `nowcast_horizon_minutes`; daraus abgeleitet ein `OnsetEvent` mit
  `already_running`, `running_until_time`/`_day_offset`, `horizon_time`/`_day_offset`; darauf
  aufbauend Alarmtexte über alle vier Kanäle, die "läuft bereits" statt einer Beginn-Angabe
  zeigen.
- **Side effects:** keine neuen — Alarmversand, Cooldown-Buchung und Alarmprotokoll laufen über
  dieselben bestehenden Schreibwege wie heute; lediglich der `already_running`-Fall darf dabei
  nicht mehr stumm herausfallen.

## Acceptance Criteria

- **AC-1:** Given ein Regen- oder Gewitterereignis läuft im Zielsegment bereits, wenn der
  Alarmlauf prüft (das den aktuellen Rasterslot deckende Frame liegt über der
  Trockenschwelle), When der Alarmlauf die Nachricht baut, Then meldet die Nachricht das
  Ereignis als bereits laufend ("läuft bereits") statt mit einer Beginn-Angabe ("in X Min").
  - Test: `AlarmPruefstrecke.lauf(zweig="radar", ...)` mit Frames, die den aktuellen Rasterslot
    als nass ausweisen; der Alarminhalt (mind. ein Kanal) enthält die Laufend-Formulierung und
    NICHT "in {N} Min".

- **AC-2:** Given im Zielsegment regnet es zum Prüfzeitpunkt noch nicht, aber ein künftiges
  Frame im Sichtfenster liegt über der Trockenschwelle (unveränderter Normalfall), When der
  Alarmlauf die Nachricht baut, Then bleibt der Wortlaut unverändert wie bisher (Beginn-Angabe
  mit Minuten bzw. Uhrzeit) — byte-identisch zum bisherigen Verhalten.
  - Test: `AlarmPruefstrecke.lauf(zweig="radar", ...)` mit trockenem Startframe und nassem
    Frame erst später; der Alarminhalt enthält weiterhin "in {N} Min" bzw. die bestehende
    Beginn-Uhrzeit-Form, unverändert zum Vor-Fix-Verhalten (Regressions-Invariante).

- **AC-3:** Given ein konvektives Ereignis (Gewitter) läuft im Zielsegment bereits, When der
  Alarmlauf die Nachricht baut, Then wird auch das laufende Gewitter als bereits laufend
  gemeldet — nicht nur laufender Regen.
  - Test: wie AC-1, aber mit `is_convective=True`-Frame; der Alarminhalt trägt die
    Laufend-Formulierung für das Gewitter-Kürzel/-Wort statt einer Beginn-Angabe.

- **AC-4:** Given ein laufendes Ereignis, das innerhalb des Sichtfensters wieder aufhört (ein
  späteres Frame ist trocken), When die Nachricht gebaut wird, Then nennt die Nachricht den
  Zeitpunkt, bis zu dem das Ereignis voraussichtlich anhält.
  - Test: Frames mit nassem aktuellem Slot und einem trockenen Frame vor Ende des Sichtfensters;
    der Alarminhalt enthält eine konkrete Uhrzeit als Ende-Angabe.

- **AC-5:** Given ein laufendes Ereignis, das bis über die tatsächliche Reichweite der
  Radarquelle hinaus anhält (kein Frame im gesamten verfügbaren Datenbestand ist mehr trocken),
  When die Nachricht gebaut wird, Then sagt die Nachricht ausdrücklich, dass kein Ende im
  Sichtfenster erkennbar ist, und nennt die Reichweite des Sichtfensters (Uhrzeit) — ohne eine
  Dauer zu erfinden.
  - Test: Frames durchgängig nass bis zum letzten verfügbaren Frame; der Alarminhalt enthält
    eine "kein Ende erkennbar"-Formulierung samt der Uhrzeit des letzten verfügbaren Frames,
    aber KEINE erfundene Enddauer.

- **AC-6:** Given ein laufendes Ereignis an einem einzelnen Ort/Trip, When die Alarm-E-Mail
  gerendert wird, Then sagt die E-Mail "läuft bereits" statt "ab ca. HH:MM (in ~N Min)".
  - Test: `lauf.mail` aus dem Prüfstrecken-Ergebnis von AC-1 auf die Laufend-Formulierung
    prüfen; die alte Beginn-Form fehlt.

- **AC-7:** Given dasselbe laufende Ereignis, When die Telegram-Langform gerendert wird, Then
  sagt sie ebenfalls "läuft bereits" statt "in X Min".
  - Test: `lauf.telegram` aus AC-1 auf dieselbe Laufend-Formulierung prüfen.

- **AC-8:** Given dasselbe laufende Ereignis, When SMS und Premium-SMS gerendert werden, Then
  macht die heutige Zeitpunkt-Form (`R@HH:MM`) den Laufend-Fall kenntlich (z. B. eigenes
  Kürzel/Präfix), statt weiterhin unverändert einen künftigen Beginn zu behaupten — innerhalb
  des bestehenden Zeichenbudgets.
  - Test: `lauf.sms` und `lauf.premium_sms` aus AC-1 enthalten die Laufend-Kennzeichnung und
    NICHT die unveränderte `R@HH:MM`-Form für einen Beginn in der Zukunft; Zeichenlänge bleibt
    innerhalb des bestehenden SMS-Limits.

- **AC-9:** Given dasselbe laufende Ereignis, When die Telegram-Kurzform gerendert wird, Then
  trägt sie denselben Laufend-Text wie die SMS (geerbtes Verhalten seit #1948 S4).
  - Test: bei `telegram_style="kurzform"` (Trip-Fixture nach S2a-Vorbild) den Telegram-Inhalt
    aus dem Prüfstrecken-Ergebnis auf dieselbe Laufend-Kennzeichnung wie AC-8 prüfen.

- **AC-10:** Given der Regen läuft und hört noch innerhalb der laufenden Viertelstunde auf (kein
  künftiges Frame im Sichtfenster ist nass, ein künftiger Beginn ist also nicht bestimmbar),
  When der Alarmlauf prüft, ob ausgelöst wird, Then wird TROTZDEM ein Alarm verschickt (heute
  fällt der Alarm in genau diesem Fall ersatzlos aus, weil `radar_alert_due` bei
  `onset_minutes is None` `False` liefert).
  - Test: Frames mit nassem aktuellem Slot und ausschließlich trockenen künftigen Frames (kein
    Frame erfüllt die Schwelle); `AlarmPruefstreckeLauf.triggered_count == 1`.

- **AC-11:** Given ein laufendes Ereignis hat bereits einen Alarm ausgelöst, und die Lage ist
  beim zweiten Prüflauf kurz danach unverändert (weiterhin laufend, weiterhin kein künftiger
  Beginn bestimmbar), When der zweite Prüflauf durchläuft, Then wird KEIN zweiter Alarm
  verschickt — die Entdopplung erkennt das laufende Ereignis als bereits gemeldet, statt bei
  `onset_minutes is None` stillschweigend jede Entdopplung zu unterlassen.
  - Test: zwei aufeinanderfolgende `AlarmPruefstrecke.lauf(zweig="radar", ...)`-Aufrufe mit
    identischen, durchgängig laufenden Eingangsdaten (Muster aus AC-10); erster Lauf
    `triggered_count == 1`, zweiter Lauf `triggered_count == 0`.
  - 🔴 **Pflicht zur Wirksamkeit dieses Wächters:** Die Sperrzeit muss für diesen Test
    ausgeschaltet sein (`trip.alert_cooldown_minutes = 0`, Muster aus S2a). Sonst verhindert
    schon der Cooldown die zweite Nachricht, der Test wird aus dem falschen Grund grün und
    misst die Entdopplung überhaupt nicht. Gegenprobe für den Adversary: Wird die
    Entdopplungs-Zeitableitung verfälscht, MUSS dieser Test rot werden — bleibt er grün,
    entscheidet in Wahrheit der Cooldown und der Wächter ist wertlos.

- **AC-12:** Given ein Ortsvergleich mit mehreren Orten, von denen an mindestens einem Ort das
  Ereignis bereits läuft (ohne bestimmbaren künftigen Beginn) und an einem anderen Ort ein
  künftiger Beginn vorliegt, When das Bündel gebaut wird, Then erscheint der laufende Ort in der
  Sammelnachricht mit der Laufend-Aussage, statt vor dem Nachrichtenbau herauszufallen.
  - Test: Ortsvergleichs-Bündel mit zwei Orten (einer laufend ohne `onset_minutes`, einer mit
    künftigem Beginn) über den Compare-Zweig der Prüfstrecke bauen; die Sammelnachricht enthält
    Zeilen für BEIDE Orte, die laufende Zeile trägt die Laufend-Formulierung.

- **AC-13:** Given ein laufendes Ereignis, für das kein künftiger Beginn bestimmbar ist
  (`onset_minutes` ist `None`), When die Zeitableitung für Dedup-Identität und Alarmversand
  rechnet, Then stürzt der Lauf NICHT ab und die Nachricht wird trotzdem korrekt mit der
  Laufend-Aussage gebaut.
  - Test: derselbe Eingangsfall wie AC-10/AC-11 läuft ohne Exception durch
    `AlarmPruefstrecke.lauf(...)`; das Ergebnis enthält gültige Kanal-Inhalte für alle vier
    Kanäle.

- **AC-14:** Given ein Nutzer fragt per Telegram-Befehl `/jetzt` die aktuelle Regenlage ab,
  während das Ereignis am abgefragten Ort bereits läuft, When die Antwort gebaut wird, Then
  meldet die Antwort das Ereignis als bereits laufend statt mit einer Beginn-Angabe
  ("ab ca. HH:MM (in ~N Min)").
  - Test: `RadarNowcastService.format_now_text(...)` (bzw. der zugrundeliegende
    `NowcastResult` mit `already_running=True`) direkt aufrufen; der Antworttext enthält die
    Laufend-Formulierung und nicht die Beginn-Form.

- **AC-15:** Given das planmäßige Trip-Briefing enthält die Starkregen-Kurzfristzeile für ein
  Ereignis, das zum Zeitpunkt der Briefing-Erstellung bereits läuft, When die Zeile gerendert
  wird, Then weist sie das Ereignis als bereits laufend aus statt mit der Beginn-Form
  "ab ca. HH:MM (in ~N Min)".
  - Test: `format_starkregen_hint(...)` mit einem `already_running=True`-Eingang aufrufen; der
    Rückgabetext enthält die Laufend-Formulierung.

## Nachtrag 2026-08-22: Abhängigkeit von #2051 S1 und Wortlaut-Entscheid

Nach der Freigabe dieser Spec stellte sich heraus, dass **Issue #2051 Scheibe S1**
(`feat-2051-s1-dauer-und-ende`, PR #2074) die **Ende-Aussage bereits gebaut hat** — inklusive
`NowcastResult.event_end_minutes`, `event_ongoing_beyond_horizon`, `_derive_wet_block_end()`,
geteilter Anzeigefassung und Verzweigung in allen sechs Formatierern.

**Folgen für diese Scheibe:**

1. **Der Ende-Wortlaut wird NICHT hier erfunden**, sondern von #2051 S1 übernommen:
   | Fall | Langform | Kurznachricht |
   |---|---|---|
   | Ende bekannt | `letzter Regen gegen HH:MM` | `R2.5@18:00@20:00` — zweites Zeit-Token **ohne** `>` |
   | kein Ende absehbar | `Regen mindestens bis HH:MM` | `R2.5@18:00 >@20:00` — Leerzeichen, `>`, Zeit-Token |
   | kein Ende ableitbar | Angabe entfällt | `R2.5@18:00` |
   | Gewitter | wie oben | `TH@18:00@20:00 R2.5` |

   🔴 Das `>` ist **kein** Schmuck: `@20:00` heisst „hört um 20:00 auf", ` >@20:00` heisst „hört
   frühestens um 20:00 auf". Gegensätzliche Aussagen — beim einen kann man danach loslaufen,
   beim anderen weiss man nur, dass es vorher nicht aufhört. Alle Zeit-Token sind
   **minutengenau** (INCA/AROME liefern im 15-Minuten-Raster; `20:45` auf `20` zu kürzen wäre
   bis zu 45 Minuten daneben).

   Der PO hatte bei der Freigabe dieser Spec einen abweichenden Wortlaut ausgewählt
   (`endet voraussichtlich HH:MM` / `kein Ende im Sichtfenster (bis HH:MM)`), ohne zu wissen,
   dass er am selben Tag für #2051 S1 bereits eine andere Fassung derselben Aussage freigegeben
   hatte. **PO-Entscheid 2026-08-22 nach Vorlage des Konflikts: die #2051-Fassung gilt.**
   Begründung: dort bereits breiter verdrahtet und vom Vorhersage-Pfad mitbenutzt
   (`render.py:298`) — eine Sprache im Produkt statt zweier.

2. **Reihenfolge:** #2051 S1 wird zuerst gemerged, danach rebast diese Scheibe darauf.
   Die Ende-Rechnung wird **nicht nachgebaut**, sondern deren `event_end_*`-Felder genutzt.

3. **Was hier echte, eigene Arbeit bleibt:** `already_running` existiert auf deren Branch nicht.
   Vor allem: deren `event_end_minutes` ist per Definition `None`, sobald `onset_minutes`
   `None` ist (dort AC-19, freigegeben, getestet, Adversary-geprüft — auf Anfrage bewusst nicht
   aufgeweicht). Genau der Fall dieser Scheibe fällt dort also heraus: **Ereignis läuft jetzt
   und endet noch in der laufenden Viertelstunde** — kein künftiger Beginn, aber ein
   bestimmbares Ende. Dazu die vier Stellen, die Zukunft voraussetzen (AC-10 bis AC-13),
   die bei #2051 S1 unangetastet bleiben.

4. **Fremdbefund, nicht Teil dieser Scheibe:** Issue **#2063** — die Onset-Uhrzeit ist in etwa
   jedem zweiten Lauf eine Minute zu früh, weil `local_fmt` (`src/utils/timezone.py:133`)
   Sekunden abschneidet statt zu runden. Betrifft jede über diesen Weg gebildete Uhrzeit,
   Ende-Angaben eingeschlossen. Scheitert ein Wächter dieser Scheibe an genau einer Minute,
   ist das die erste Spur — **nicht** ein Anlass, eine Zusicherung aufzuweichen.

## Known Limitations

- **Nicht Teil dieser Scheibe:** die 55-Minuten-Meldeschwelle (`RADAR_ONSET_THRESHOLD_MIN`,
  gehört zu Anforderung A-1) und die Sperrzeit-/Überholungslogik von `check_nowcast_gate`
  (Issue #2065, läuft parallel in einer anderen Session — dort ist Anforderung A-3 gemessen
  verletzt, unabhängig vom Laufend-Fall dieser Scheibe).
- **Beim Implementieren zu klären, nicht vorab entschieden:** ob
  `radar_alert_service.py::build_onset_alert_message` noch einen produktiven Aufrufer im
  Alarm-Versandpfad hat. Ein Grep zeigt aktuell nur `scripts/send_gate_test_mails.py` und
  `api/routers/debug.py` als Aufrufer — beides Debug-/Test-Werkzeuge, kein Treffer in
  `trip_alert.py`. Trifft das beim Implementieren erneut zu, muss die Funktion die neuen
  `OnsetEvent`-Felder nicht zwingend selbst befüllen (Default `already_running=False` reicht für
  Debug-Zwecke); ist doch ein produktiver Aufrufer vorhanden, zieht er mit.
- **Beim Implementieren zu klären:** ob das Replay-Payload-Schema in
  `validator_render_service.py` die neuen Felder explizit tragen muss oder ob reines
  Durchreichen der `NowcastResult`/`OnsetEvent`-Instanz genügt.
- **R2 aus der Analyse bleibt bestehen:** Keine Datenquelle wird nach Vergangenheit gefragt
  (kein `past_minutes`/`past_hours`/`start_date`-Parameter). Die Erkennung "läuft bereits" stützt
  sich daher ausschließlich auf den aktuellen Rasterslot (max. 15 Minuten Rückblick), nicht auf
  einen längeren Rückblick — ein Ereignis, das vor mehr als einer Viertelstunde begann und noch
  läuft, ist aus dem Nowcast allein nicht als "seit X laufend" belegbar, nur als "läuft jetzt".
  Diese Scheibe zusichert entsprechend "läuft bereits", nicht "seit HH:MM".
- Rund 15 Testdateien nageln heute den Wortlaut "in X Min" fest (Regressionsschutz für AC-2),
  weitere ~15 hängen an `format_starkregen_hint`/`format_now_text` — eine Wortlautänderung im
  Laufend-Zweig zieht KEINE Anpassung dieser Bestandstests nach sich, solange der
  Normalfall-Zweig (Ereignis liegt wirklich in der Zukunft) byte-identisch bleibt.

## Nicht Ziel

- Die 55-Minuten-Meldeschwelle (`RADAR_ONSET_THRESHOLD_MIN`) — Anforderung A-1, andere Scheibe.
- Die Sperrzeit-/Überholungslogik von `check_nowcast_gate` — Issue #2065, parallele Session.
- Ein "seit HH:MM läuft es schon"-Rückblick über mehr als eine Viertelstunde — aus den
  verfügbaren Nowcast-Quellen nicht belegbar (s. Known Limitations, R2).
- Die Option, den Alarm beim Laufend-Fall gar nicht zu verschicken — vom Product Owner
  ausdrücklich verworfen (widerspräche dem Produktgrundsatz NUR Daten, keine Bevormundung, und
  ein stiller Nicht-Alarm wäre von einem technischen Ausfall nicht unterscheidbar).
- Die verbleibenden Alarm-Szenarien aus #2050 außer Szenario 1/Anforderung B-1 (spätere Scheiben).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein additive Modellerweiterung (neue Felder mit Default auf `NowcastResult`
  und `OnsetEvent`, byte-identischer Normalfall) nach dem bereits etablierten Muster aus
  #2009/#2046/#2036/#2020 S2 — kein neues Datenmodell, keine neue Route, keine Rücknahme einer
  bestehenden Architekturentscheidung. Berührt, aber nicht zurückgenommen: ADR-0052
  (Warnmail-Nowcast-Bauform) und ADR-0056 (rollierender Alarm-Anker) — beide bleiben in Kraft,
  diese Scheibe ändert nur, WELCHER Text bei WELCHEM Zustand gerendert wird, nicht die
  Bauform/den Anker-Mechanismus selbst.

## Changelog

- 2026-08-22: Initial spec created (Scheibe S2b aus #2050, Anforderung B-1, verdichtet aus
  `docs/context/fix-2050-s2b-laufendes-ereignis.md`).
