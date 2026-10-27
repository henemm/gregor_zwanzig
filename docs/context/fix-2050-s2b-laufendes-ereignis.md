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

---

# Analysis

## Type

**Bug** (nutzersichtbares Fehlverhalten mit Vorfallbeleg vom 21.08.), geschnitten als Scheibe des
Enhancement-Tickets #2050.

## Die tragende Erkenntnis

Der gesamte Radar-Zweig setzt an **vier unabhaengigen Stellen** voraus, dass ein Radar-Ereignis in
der **Zukunft** liegt. Diese Praemisse steht seit dem Merge von #2020 S2 sogar ausformuliert im
Code (`render.py:497-511`: *"`OnsetEvent` kennt kein Vergangenheits-Kennzeichen (Radar blickt nach
vorn)"*). B-1 bricht genau diese Praemisse — und jede der vier Stellen muss mitziehen, sonst
ueberlebt der Defekt dort still weiter.

Alle vier haengen am selben Ausdruck `onset_minutes is not None`:

| # | Stelle | Verhalten bei `already_running=True, onset_minutes=None` | Schwere |
|---|---|---|---|
| 1 | `trip_alert.py:145-148` `radar_alert_due` | liefert `False` ⇒ **gar kein Alarm**, Renderer nie erreicht | sperrt den Fall komplett |
| 2 | `compare_radar_alert.py:64-79` `_identity_inputs` | `onset_at=None` ⇒ `_times_overlap` (`alert_gate.py:490-512`) findet nie einen Kandidaten ⇒ **Entdopplung wird stiller No-Op** | wirkt, sieht aber funktionsfaehig aus |
| 3 | `trip_alert.py:1382` / `project.py:509-511` | `now + timedelta(minutes=None)` ⇒ **Absturz** | laut |
| 4 | `project.py:494` | filtert laufende Orte vor dem `OnsetEvent`-Bau heraus ⇒ **Ortsvergleich schweigt** | still |

🔴 Nr. 2 ist der gefaehrlichste Punkt: Ein Test, der nur "laeuft UND regnet weiter" baut, sieht
davon nichts — dort ist `onset_minutes` gesetzt und alles verhaelt sich normal. Der Fall wird nur
sichtbar, wenn das Ereignis **innerhalb der laufenden Viertelstunde endet**. Dieselbe Fehlerfamilie
wie dreimal zuvor in diesem Ticket: ein Zweig wirkt grün, weil die Bedingung ihn nie erreicht.

## Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/radar_service.py` | MODIFY | Erkennung im `_derive_result`; `NowcastResult` um Laufend-Kennzeichen + Ende erweitern; `format_now_text` (`/jetzt`) |
| `src/output/renderers/alert/model.py` | MODIFY | `OnsetEvent` additiv um Laufend-Kennzeichen + Ende-Zeit + Tagesversatz |
| `src/output/renderers/alert/render.py` | MODIFY | geteilter Helfer neben `_onset_time_label`; Verzweigung in allen Onset-Formatierern (E-Mail einzeln/Buendel, Telegram-Langform, Betreff, SMS-Token) |
| `src/services/trip_alert.py` | MODIFY | `radar_alert_due` (:145), Zeitableitung + Dedup-Identitaet (:1382), `RadarAlertRequest`-Bau (:1498) |
| `src/services/compare_radar_alert.py` | MODIFY | `_identity_inputs` (:64-79) |
| `src/output/renderers/alert/project.py` | MODIFY | Filter (:494) und Zeitableitung (:509-511) im Compare-Buendel |
| `src/services/notification_service.py` | MODIFY | `RadarAlertRequest`: `onset_minutes` optional, neue Felder durchreichen |
| `src/services/radar_alert_service.py` | MODIFY? | Aufrufer beim Implementieren per Grep klaeren — moeglicherweise Legacy/Preview |
| `src/output/renderers/email/starkregen_hint.py` | MODIFY | Briefing-Kurzfristzeile |
| `src/services/validator_render_service.py` | MODIFY? | Replay-Payload-Schema, nur falls es die Felder tragen muss |
| `docs/specs/modules/alarm_szenario_laufendes_ereignis.md` | CREATE | Spec dieser Scheibe |
| `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` | CREATE | Waechter nach S2a-Muster ueber die Pruefstrecke |

## Scope Assessment

- Dateien: 10-12 (davon 2 neu)
- LoC produktiv: ~180-260 ⇒ **`loc_limit_override` auf 300** noetig (Default 250)
- LoC Test: ~150-250 ⇒ `test_loc_limit_override` vorsorglich setzen
- Risk Level: **MEDIUM-HIGH** — kritischer Alarmpfad, aber ausschliesslich additiv; der Normalfall
  (Ereignis liegt wirklich in der Zukunft) bleibt unveraendert und ist als Regressions-Invariante
  pruefbar.

## Technical Approach (Empfehlung)

**Gewaehlt: den Laufend-Zustand erkennen und durchreichen** — nicht: die Ausloesung unterdruecken.

1. **Erkennung** in `_derive_result` (`radar_service.py:~700`), wo Frames, Fenster und `now` bereits
   zusammenliegen. Ein Ereignis laeuft, wenn das Frame, dessen Gueltigkeitsintervall `now` enthaelt,
   ueber der Trockenschwelle liegt. Die Vorwaerts-Konvention ist keine Neuerfindung: die
   Mengenrechnung `_accumulate_precip_mm` (`radar_service.py:200-242`, `_MAX_FRAME_COVERAGE`)
   rechnet heute schon so. Damit werden Ausloeseentscheidung und Mengenrechnung deckungsgleich.
2. **Ende** = erstes trockenes Frame nach der laufenden nassen Strecke. Regnet es bis ueber den
   Sichthorizont hinaus (INCA real ~165 Min), gibt es **kein** Ende zu nennen — dann wird das
   ausdruecklich gesagt, statt eine Dauer zu erfinden.
3. **`onset_minutes` bleibt unangetastet.** Es behaelt seine Rolle als Torwaechter und
   Dedup-Bestandteil; der Laufend-Zustand liegt additiv daneben. Das haelt die Gate-Kette, an der
   #2065 parallel arbeitet, aus dem Spiel.
4. **Die vier Stellen aus der Tabelle ziehen mit** — jede einzeln als Akzeptanzkriterium, sonst
   bewacht sie kein Test (Praezedenz: `onset_precip_mm` musste bei #2046 an denselben Stellen
   nachgezogen werden).
5. **Renderer**: ein geteilter Helfer neben `_onset_time_label`, aufgesetzt auf den bestehenden
   Baustein `_time_with_day(zeit, offset, is_past=)`. Alle vier Kanaele verzweigen an ihrer
   vorhandenen Stelle. **Pflicht, nicht Kuer:** ohne Textaenderung liest der Nutzer sonst
   "Regen in 0 Min" — der Fix waere schlimmer als der Bug.

**Verworfen: Ausloesung unterdruecken** ("gar nicht melden", von Szenario 1 ausdruecklich erlaubt).
Begruendung: widerspricht dem Produktgrundsatz *NUR Daten, keine Bevormundung* — ob ein bereits
laufender Regen fuer ihn wichtig ist, entscheidet der Wanderer; ein stiller Nicht-Alarm ist zudem
von einem technischen Ausfall nicht unterscheidbar (Anforderung D-2 verlangt fuer jede
Unterdrueckung einen benannten Grund). **Diese Wahl ist die eine echte PO-Entscheidung dieser
Scheibe** und wird bei der AC-Freigabe vorgelegt.

## Flut-Gegenprobe

Kein neues Risiko. `check_nowcast_gate` (`alert_gate.py:140-184`) ist ein reiner Cooldown auf der
Trip-/Preset-Kennung, laeuft **vor** `radar_alert_due` und ist von `onset_minutes` unabhaengig. Ein
durchregnender Nachmittag loest daher hoechstens im Cooldown-Takt aus, nicht alle 15 Minuten. Die
Entdopplung wirkt als zweite Sperre — aber erst, wenn Punkt 2 der Tabelle behoben ist.

## Selbst entschieden (keine PO-Fragen)

- **`/jetzt` ist im Scope.** Die Sofort-Abfrage macht dieselbe Falschaussage aus derselben
  Datenbasis; sie auszunehmen hiesse, den Bug halb zu beheben.
- **Kein Ende absehbar ⇒ genau das sagen**, keine erfundene Mindestdauer.
- **Gewitter ist eingeschlossen**, nicht nur Niederschlag (`is_convective`).
- **Die 55-Minuten-Meldeschwelle bleibt unberuehrt** — sie gehoert zu Anforderung A-1, nicht zu B-1.

## Open Questions

- [ ] **PO:** Laeuft der Regen beim Alarmlauf bereits — melden (mit Angabe, bis wann er anhaelt)
      oder in diesem Fall gar nichts schicken? *Empfehlung: melden.*
- [ ] **Beim Implementieren zu klaeren:** Hat `radar_alert_service.py:build_onset_alert_message`
      noch produktive Aufrufer, oder ist es Legacy/Preview? (Grep auf Aufrufer.)
- [ ] **Beim Implementieren zu klaeren:** Traegt das Replay-Payload-Schema
      (`validator_render_service.py`) die neuen Felder, oder reicht Durchreichen?

## Ungeprueft geblieben (bewusst offengelegt)

Welche Intervall-Konvention die drei Datenquellen **extern** zusichern, ist aus dem Code nicht
belegbar. Wir uebernehmen die Konvention, nach der die App bereits ihre Mengen rechnet. Das ist
in sich konsistent, aber eine Annahme — nachpruefbar nur ueber einen Live-Abgleich von
Frame-Zeitstempel gegen tatsaechliche Messzeit.
