# Context: feat-2051-s1-dauer-und-ende

**Issue:** #2051 — „Ereignis als Flaeche liefern: Dauer, raeumliche Ausdehnung, Reichweite der Quelle"
**Zuschnitt:** ausschliesslich **Scheibe S1** — Dauer und Ende mitliefern. S2 (raeumliche
Ausdehnung), S3 (Reichweite der Quelle), S4 (`/strecke`-Kommando) bleiben offen; das Ticket
bleibt als Scheiben-Ticket offen.
**Erstellt:** 2026-08-21 · Phase 1 (Kontext)

## Request Summary

Der Radar-/Nowcast-Pfad liest heute aus der abgerufenen Frame-Zeitreihe nur den **ersten**
nassen Zeitpunkt und verwirft den Rest. Der Nutzer erfaehrt, *wann* es anfaengt, aber nicht,
**wie lange es dauert und wann es endet**. S1 leitet Ende und Dauer des zusammenhaengenden
nassen Blocks aus **denselben, bereits abgerufenen Frames** ab (kein zusaetzlicher
Quellenabruf) und liefert sie in allen vier Kanaelen mit.

## Related Files

### Datenpfad (Ableitung)

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py:701` `_derive_result()` | **Kernstelle.** Baut `NowcastResult` aus den Frames. Die Onset-Schleife (`:716-727`) bricht beim ersten nassen Frame mit `break` ab — genau hier faellt die Information ueber Ende/Dauer weg. |
| `src/services/radar_service.py:197` `_accumulate_precip_mm()` | **Wichtigster Wiederverwendungs-Kandidat.** Von #2046 aus `_derive_result` extrahierter, parametrisierter Rechenkern: Frame-Dedup je Zeitstempel (hoeherer Wert gewinnt), Dauer je Frame aus dem *eigenen* naechsten Nachbarn (`bisect_right` ueber `all_ts_sorted`), Deckel `_MAX_FRAME_COVERAGE`, hartes Fensterende. Genau diese Mechanik braucht auch die Ende-Bestimmung. |
| `src/services/radar_service.py:134` `NowcastResult` | Traegt `frames` (**vollstaendige Zeitreihe, bereits vorhanden**), `onset_minutes`, `window_precip_mm`, `onset_precip_mm`, `max_rate_mm_h`. Additive, optionale Felder sind hier das etablierte Muster. |
| `src/services/trip_alert.py:144` `radar_alert_due()` | Auslöse-Gate: `onset <= threshold_min`. |
| `src/services/trip_alert.py:1349` / `src/services/compare_radar_alert.py:352` | Die **einzigen** zwei Anwender von `RADAR_ONSET_THRESHOLD_MIN` (ADR-0021, Trip + Ortsvergleich teilen den Code). |
| `src/services/notification_service.py:165` `RadarAlertRequest` | DTO Service → Renderer. Traegt `onset_minutes`, `onset_time`, `onset_day_offset`, `km_from/km_to`, `is_convective`, `intensity_label`, `source_label`, `tz`, `segment_id`, `onset_precip_mm`. **Kein** Ende-/Dauer-Feld. |
| `src/output/renderers/alert/model.py:38` `OnsetEvent` | Renderer-Modell, gleiche Felderlage. Additive Felder mit Default sind hier Standard (#1041, #1744, #2009, #2046). |
| `src/output/renderers/alert/project.py:368-398` | Baut das Mehr-Orte-Onset-Buendel (Ortsvergleich) aus `NowcastResult`. |

### Textpfad — alle Stellen, die den Onset ausformulieren

> Die Wirkkette endet **nicht** beim ersten Formatierer. Vollstaendige Liste, per Grep nach
> `onset_minutes` in den Ausgabe-Modulen erhoben:

| # | Stelle | Kanal / Nachrichtenart | Sichtbarer Text heute |
|---|---|---|---|
| 1 | `render.py:352` `_render_subject_onset` | E-Mail-Betreff | `[{trip}] {km} · {label} in {n} Min` |
| 2 | `render.py:389` `_render_email_onset_multi` | E-Mail, Mehr-Orte-Buendel (Ortsvergleich) | `in {n} Min` |
| 3 | `render.py:459` `_render_email_onset` | E-Mail, Trip | `{label} in {n} Min` |
| 4 | `render.py:528` `_render_telegram_onset` | Telegram (rich) | `{trip} · {km} · {label} in {n} Min` |
| 5 | `render.py:594+` `_render_sms_onset` | SMS · Premium-SMS · Telegram-Kurzstil | `Ziel: R2.5@18:00` bzw. `Ziel: TH@18:00 R2.5` |
| 6 | `output/renderers/email/starkregen_hint.py:27` `format_starkregen_hint` | **Briefing**-Kurzfristhinweis (#1439) | `{label} ab ca. {HH:MM} (in ~{n} Min).` |
| 7 | `services/radar_service.py:450` `format_now_text` | **Inbound-Kommando-Antwort** (`trip_command_processor.py:1537`) | `{label} ab ca. {HH:MM} (in ~{n} Min).` |

Stellen 1–5 liegen in `src/output/renderers/alert/render.py` (ADR-0011: ein Backend-Renderer);
6 und 7 liegen ausserhalb.

## Existing Patterns

1. **Additiv-optionales Feld durch die ganze Kette.** #2046 (`onset_precip_mm`) ist die frische,
   vollstaendig durchgezogene Blaupause: neues Feld an `NowcastResult` → `RadarAlertRequest` →
   `OnsetEvent` → Renderer, plus Vorschau-/Testeinspeiseweg (`api/routers/validator.py`,
   `src/services/validator_render_service.py`). Default `None`, Ausweichform ohne die Angabe.
   Commit `f9149858`, Spec `docs/specs/modules/fix_2046_onset_menge.md`.
2. **Eigener Fenstername statt geteilter Konstante.** `_ONSET_PRECIP_WINDOW_MIN = 60` steht
   bewusst neben `_OVERTAKE_COMPARE_WINDOW_MIN = 60` — gleiche Zahl, verschiedene Bezugspunkte
   und Zwecke. Eine Ende-/Dauer-Groesse braucht denselben Respekt vor dem Bezugspunkt.
3. **Frame-Deckung nie global schaetzen.** `_MAX_FRAME_COVERAGE = 15 min` (groebstes
   Produktivraster) plus Nachbar-Ableitung je Frame. Herleitung: #2020 Adversary-Runden 2/3
   (F006/F007/F010). Eine globale Kadenz-Schaetzung ist in beide Richtungen verfaelschbar.
4. **Trip und Ortsvergleich teilen den Code** (ADR-0021). Jede Aenderung am Onset muss in
   **beiden** Flaechen wirken; Paritaets-Tests existieren (`tests/tdd/test_onset_menge_kanalparitaet.py`).
5. **Mail-Bauform:** Fakten als Datenzeilen (`_datarow_html`, Label links / Wert rechts,
   Outlook-Kompatibilitaet), HTML und Klartext aus denselben Label-Wert-Tupeln (ADR-0052).

## Dependencies

- **Upstream:** Frames der Nowcast-Quellen (INCA/GeoSphere, AROME-FR, ICON-D2, ARPAE,
  Open-Meteo `minutely_15`); Raster 5–15 Min, Horizont bis 180 Min.
- **Downstream:** alle sieben Textstellen oben; Vorschau-/Validator-Weg
  (`api/routers/validator.py`, `src/services/validator_render_service.py`); Pydantic-Payload
  der Vorschau.
- **Konstanten:** `_NOWCAST_HORIZON_MIN = 180` (`:69`), `RADAR_ONSET_THRESHOLD_MIN = 55`
  (`:121`), `_DRY_THRESHOLD_MM_H = 0.1`, `_MAX_FRAME_COVERAGE = 15 min`,
  `_OVERTAKE_COMPARE_WINDOW_MIN = 60`, `_ONSET_PRECIP_WINDOW_MIN = 60`.

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/fix_2046_onset_menge.md` | **Naechster Nachbar** — Mengenangabe ab Ereignisbeginn, dieselbe Kette |
| `docs/specs/modules/fix_2020_alarm_ausloesung.md` | Mengen-Ueberholung, Herkunft von `_accumulate_precip_mm` |
| `docs/specs/modules/fix_1945_nowcast_horizon.md` | Anhebung 60 → 180 Min, direkt relevant fuer den offenen PO-Entscheid |
| `docs/specs/modules/fix_2009_nowcast_vorlauf.md` | Herkunft von `RADAR_ONSET_THRESHOLD_MIN = 55` |
| `docs/specs/modules/fix_2017_nowcast_messpunkt.md` | Messpunkt am Aufenthaltsort |
| `docs/specs/modules/radar_nowcast.md` (+ `_inca_fix`, `_icon_d2`, `_france`, `_italy_arpae_fallback`) | Quellen und Raster |
| `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` | Zielbild der Onset-Kurznachricht |
| ADR-0011, ADR-0021, ADR-0046, ADR-0052 | Ein Backend-Renderer · geteilter Code Trip/Compare · Kanal-Schwelle · Mail-Bauform |

## Abstimmung mit Parallelsitzungen (2026-08-21)

| Sitzung | Ergebnis |
|---|---|
| `feat-2050-s1-pruefstrecke` (#2050, Phase 6) | **B-1 liegt dort NICHT im Zuschnitt** (ist dort S2, ausdruecklich „Nicht Ziel"). Deren Diff sind zwei reine Testdateien, keine Produktivdatei. Der im Ticket-Body vermutete gemeinsame Bau entfaellt — kein Wartegrund. Angebot: die Pruefstrecke steht S1 danach zur Auslöse-Verifikation offen. |
| `fix-2020-zeitangaben-wortlaut` (#2020 S2, Phase 5) | Arbeitet im **Δ-/Abweichungszweig**, nicht im Nowcast-Onset-Zweig. Beruehrungspunkte: `_onset_time_label()` (Tagesversatz-Wortlaut, wirkt auch auf den Nowcast-Pfad) und der Δ-Teil von `_render_sms_body`. **Zusage dieser Sitzung: beide Funktionen bleiben unangetastet**, und der Wortlaut fuer das Ereignisende wird uebernommen statt neu erfunden — Langform `letzter Regen gegen HH:MM`, Kurzform `@HH` hinter dem Mengen-Token. Jene Sitzung haengt zusaetzlich an #2036 und meldet sich mit dem endgueltigen Wortlaut, sobald S2 in `main` ist. |

## Risks & Considerations

**R1 — Der Realfall im Ticket stammt nicht aus dem Alarmzweig.** „Regen bei km 10 in 90 Minuten"
kann aus dem Onset-**Alarm** gar nicht kommen: `radar_alert_due()` deckelt hart bei 55 Min.
Ungedeckelt bis 180 Min sind dagegen der **Briefing-Kurzfristhinweis** (`format_starkregen_hint`,
gespeist ueber `src/services/trip_report_scheduler.py:1808-1815`, das den fehlenden Grenzwert
ausdruecklich als bewusste Entscheidung dokumentiert) und die **Inbound-Kommando-Antwort**
(`format_now_text`). Vor dem Zuschnitt der Spec ist zu klaeren, welche Nachrichtenart der
Ausgangsfall war — sonst baut S1 Ende/Dauer in einen Pfad, der den geschilderten Fall nicht
erzeugt hat. Sicherste Auslegung: **alle sieben Textstellen** bedienen.
Befund beigesteuert von der Sitzung `intake-2020-scheibe2`.

**R2 — Der offene PO-Entscheid ist anders gelagert als im Ticket beschrieben.** Der Kommentar
vom 18:35 stellt „Horizont auf 60 Min kappen" gegen „voller Horizont mit Guete-Kennzeichnung".
Fuer den **Alarm**zweig existiert die Kappung bereits (55 Min) — Option (a) waere dort weitgehend
wirkungslos. Zugleich wuerde ein Absenken von `_NOWCAST_HORIZON_MIN` auf 60 die Entscheidung aus
**#1945** zuruecknehmen (dort auf 180 angehoben, weil der 60-Min-Deckel den Alarm praktisch immer
erst ~8 Min vorher ausloesen liess) und ausserdem `window_precip_mm`/`onset_precip_mm`
beschneiden. Der Entscheid betrifft also faktisch die **ungedeckelten** Pfade 6 und 7.

**R3 — Tagesfenster vs. Nowcast-Horizont.** #2020 S2 rechnet Restmenge und Ende strikt im
Tagesfenster der Etappe (`resolve_configured_window`, Default 4–19, effektives Ende 20:00
Ortszeit — Begruendung `src/services/segment_weather.py:292-308`: sonst nennt der Alarm eine
andere Stunde als das Briefing). Ein aus Nowcast-Frames abgeleitetes Ende reicht bei 180 Min
Horizont **regelmaessig** darueber hinaus. Ob S1 das Ende am Fensterende kappt oder darueber
hinaus nennt, ist eine bewusste Entscheidung und gehoert in die Spec.

**R4 — „Ende" ist bei abgeschnittener Zeitreihe nicht dasselbe wie „Ende des Ereignisses".**
Wenn der letzte nasse Frame der letzte verfuegbare Frame ist, ist das Ereignis **nicht** zu Ende
— die Daten sind zu Ende. Beide Faelle duerfen nicht denselben Text erzeugen (verwandt mit S3:
Reichweite der Quelle als Datum). Dasselbe gilt bei Datenluecken mitten im nassen Block:
ein einzelner fehlender Frame darf den Block nicht faelschlich beenden.

**R5 — Zeichenbudget SMS/Premium-SMS.** 140 Zeichen GSM-7. Die Kurzform traegt seit #2046
bereits ein Mengen-Token. Eine zusaetzliche Ende-Angabe muss ins Budget passen oder eine
Ausweichform haben. Auf der Huette (nur Satellit) ist Premium-SMS die einzige ankommende
Fassung — die Verdichtung entscheidet dort ueber den Nutzwert.

**R6 — Bevormundungs-Grenze.** Nur Daten ueber das Wetter, keine Rechnungen ueber den Nutzer
(PO-Ansage, zweifach geschaerft). „Nass bis 16:30" ist erlaubt; „bei Planzeit bist du um 15:40
bei km 9" ist verboten.

**R7 — Merge-Reihenfolge in `render.py`.** #2036 (Phase 6, noch nicht in `main`) und #2020 S2
fassen dieselbe Datei an. Vor dem Schreiben an `render.py` auf den jeweils aktuellen Stand
nachziehen.

## Stand des Worktrees

Branch `feat-2051-s1-dauer-und-ende`, per Vorwaertsspulen auf `origin/main` = `d908160d`
gezogen (enthaelt #2046). Keine eigenen Commits.

---

# Analysis (Phase 2)

## Type

**Feature** (Issue-Label `enhancement`), Scheibe eines Scheiben-Tickets.

## Korrekturen an Phase 1

- Die sieben Textstellen sind **vollzaehlig**. `_render_email_onset_shift_only` /
  `_render_sms_onset_shift_only` (`render.py:311-341`) rendern `OnsetShiftEvent` aus dem
  prognosebasierten Abweichungspfad (#1468, `project.py:115` nimmt `WeatherChange` entgegen) und
  tragen keine Nowcast-Minutenangabe — anderer Ereignistyp, nicht Teil der Flaeche.
- **Der Briefing-Pfad (Stelle 6) bekommt kein `NowcastResult`, sondern zwei Skalare.**
  `starkregen_nowcast: tuple[str, int] | None` (`notification_service.py:110`), gebaut in
  `trip_report_scheduler.py:1870` als `return (result.intensity_label, result.onset_minutes)`,
  ausgepackt `:366`, verbraucht von `format_starkregen_hint(intensity_label, onset_minutes, tz)`.
  Fuer Dauer/Ende muss dort die **Datenform** aufgemacht werden (Tupel erweitern oder durch ein
  kleines Objekt ersetzen) — vier Stellen statt einer.
- **Stelle 7 dagegen ist billig:** `format_now_text(result, ...)` bekommt das vollstaendige
  `NowcastResult` (`radar_service.py:400`).
- **Zwei Pydantic-Modelle** muessen ein neues Feld kennen: `RadarAlertRequest`
  (`notification_service.py:165`) und `OnsetPayload` (`api/routers/validator.py:~240`). Bei #2046
  war genau das der Adversary-Fund F002 — hier vorab bekannt.
- **Der Nowcast-Pfad kennt heute kein Tagesfenster.** `_derive_result(self, frames, source,
  now=None)` arbeitet rein auf Frames und einem Zeitpunkt; die Tagesfenster-Tests
  (`test_onset_respects_configured_day_window.py`, `test_onset_compare_day_window.py`) gehoeren
  zur prognosebasierten Beginn-Verschiebung (#1468), nicht hierher. Ein Kappen am Tagesfenster
  waere eine **Neueinfuehrung**, die Trip-Konfiguration bis in den Radar-Dienst durchreichen
  muesste.

## Technischer Ansatz

Die Onset-Schleife (`radar_service.py:724-729`) laeuft bereits ueber das sortierte Fenster und
bricht beim ersten nassen Frame ab. Die Blockende-Bestimmung ist dieselbe Schleife **ohne** den
Abbruch. Der Kern ist die Unterscheidung zweier Faelle — und **beide brauchen keine neue
Toleranzzahl**:

| Fall | Bedeutung | Behandlung |
|---|---|---|
| Frame vorhanden, `precip_mm_h < 0.1` | Quellenaussage „hier hat es aufgehoert" | beendet den Block **real**. Nicht ueberbruecken — sonst verschmelzen zwei getrennte Ereignisse und die Dauer wird ueberschaetzt. |
| Frame **fehlt** (Raster-Luecke, Drosselung, Ausfall) | keine Beobachtung | Der letzte nasse Frame deckt ohnehin nur bis `min(naechster Frame, +_MAX_FRAME_COVERAGE, Fensterende)`. Luecken bis 15 Min sind damit **implizit** toleriert; groessere Luecken setzen das Ende an der Deckungsgrenze. |

Neuer Helfer als **Geschwister** von `_accumulate_precip_mm`, nicht als dessen Erweiterung
(dessen Aufgabe ist Summieren in einem bekannten Fenster, nicht Grenzen finden):
`_derive_wet_block_end(frames, all_ts_sorted, onset_ts, horizon) -> tuple[datetime, bool]`.

**Neue Felder an `NowcastResult`** (additiv, optional, Muster `onset_precip_mm`):

- `event_end_minutes: Optional[int] = None` — Minuten ab jetzt bis Blockende, analog `onset_minutes`.
- `event_ongoing_beyond_horizon: bool = False` — der **R4-Waechter**: Frames bzw. der 180-Min-Horizont
  sind ausgegangen, waehrend der letzte bekannte Frame noch nass war. `False` = „das echte Ende ist
  bekannt", konsistent mit `throttled`/`data_unavailable`.

**Keine** gespeicherte `event_duration_minutes` — sie ist `event_end_minutes - onset_minutes`, ein
drittes Feld koennte auseinanderlaufen. Downstream braucht `event_end_time` /
`event_end_day_offset` als Pendants zu `onset_time`/`onset_day_offset`, berechnet ueber
**dieselbe** Zeitversatz-Logik (#2009-Muster), nicht neu implementiert.

## Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/radar_service.py` | MODIFY | Grenz-Helfer, zwei Felder, Verdrahtung in `_derive_result`; Stelle 7 (`format_now_text`) |
| `src/output/renderers/alert/model.py` | MODIFY | Felder an `OnsetEvent` |
| `src/services/notification_service.py` | MODIFY | `RadarAlertRequest` (Pydantic), Weitergabe; Aufruf Stelle 6 |
| `src/services/trip_alert.py` | MODIFY | Ende-Zeit + Tagesversatz berechnen, durchreichen |
| `src/services/compare_radar_alert.py` | MODIFY | Paritaet Ortsvergleich (ADR-0021) |
| `src/output/renderers/alert/project.py` | MODIFY | Mehr-Orte-Buendel |
| `src/output/renderers/alert/render.py` | MODIFY | Textstellen 1–5 |
| `src/output/renderers/email/starkregen_hint.py` | MODIFY | Stelle 6, Signatur |
| `src/services/trip_report_scheduler.py` | MODIFY | Datenform des Briefing-Tupels |
| `api/routers/validator.py` | MODIFY | `OnsetPayload` (Pydantic) |
| `src/services/validator_render_service.py` | MODIFY | Vorschau-/Replay-Weg |
| `tests/tdd/…` | CREATE/MODIFY | Blockende inkl. Luecken-Fall, Tagesversatz fuers Ende, Kanalparitaet, SMS-Budget-Grenzfall |

## Scope Assessment

- Dateien: 11 Produktiv + ~10–12 Test
- Geschaetzte LoC: **~200–240 produktiv**, ~150–220 Tests bei voller Reichweite
- **Ueber dem 250-LoC-Workflow-Limit** → `loc_limit_override` einplanen
- Risiko: **MEDIUM**

## Risiken (ueber Phase 1 hinaus)

- **Groesstes inhaltliches Risiko ist R4.** Ohne den `event_ongoing_beyond_horizon`-Waechter
  behauptet der Text ein festes Ende, obwohl das Ereignis nachweislich ueber den
  Beobachtungshorizont hinausreicht. Das waere **schlechter als der heutige Zustand**, der ueber
  das Ende gar nichts behauptet — eine falsche Tatsachenbehauptung, kein Rundungsfehler. Jeder
  Text-Konsument muss den Waechter pruefen, bevor er ein Ende formuliert.
- **SMS-Budget nicht aus #2046 fortschreiben.** AC-9 dort prueft das Budget nur fuer den damaligen
  Token-Umfang. S1 braucht einen **neuen** kombinierten Grenzfall (langer Ortsname + Extremmenge +
  Ende-Token), keine Annahme, die alte Marge gelte weiter.
- **Mitternachtsueberlauf asymmetrisch:** Das Ende kann auf den Folgetag fallen, auch wenn der
  Beginn es nicht tut (Beginn 23:50, Ende 00:40). Eigenes `event_end_day_offset` noetig.

## Reihenfolge

`render.py` wird von drei Vorhaben gleichzeitig angefasst. Empfehlung:

1. **Datenschicht zuerst** (`radar_service.py`, `model.py`, `notification_service.py`,
   `trip_alert.py`/`compare_radar_alert.py`, Vorschauweg) — keine Abhaengigkeit von `render.py`,
   kann sofort entstehen.
2. #2036 (Phase 6) und #2020 S2 (Phase 5) mergen lassen.
3. Auf beide nachziehen, **dann** die Textstellen 1–5 schreiben.

## Open Questions — gehen mit den ACs zur PO-Freigabe

**(E1) Reichweite.** *Empfehlung: alle sieben Textstellen.* Der Ticket-Text rahmt das Problem als
„Das Alarmsystem meldet heute einen Punkt" — ein Zuschnitt ohne die Alarmtexte adressiert die
eigene Problemstellung des Tickets nicht. Vor allem: Stelle 6 ist **E-Mail-only**
(`renderers/email/`), Stelle 7 ist eine Antwort auf aktive Nachfrage. Ein Zuschnitt auf 6+7
liesse **SMS und Premium-SMS ohne die Angabe** — und auf der Huette (nur Satellit) ist
Premium-SMS die einzige ankommende Fassung. Gegenargument, das die Empfehlung nicht kippt: die
strategische Bewertung riet zu 6+7, um `render.py`-Konflikte und das LoC-Limit zu vermeiden. Der
Wartezeit-Teil des Arguments traegt nicht — der zu uebernehmende Wortlaut steht bereits fest.
Falls der PO frueher liefern will, ist „Datenschicht + 6 + 7 jetzt, Alarmtexte als zweite
Scheibe" der saubere Schnitt.

**(E2) Tagesfenster.** *Empfehlung: NICHT kappen, das echte Ende aus den Frames nennen.* Drei
Gruende: (a) Der Nowcast-Pfad spricht heute schon ausserhalb des Tagesfensters — `onset_time`
wird nirgends gekappt, ein Alarm um 19:40 nennt problemlos einen Beginn um 20:35. Nur das *Ende*
zu kappen waere in sich unstimmig. (b) Die Briefing-Konsistenz-Begruendung aus
`segment_weather.py:292-308` gilt dem Δ-Alarm, der gegen **Briefing-Zahlen** vergleicht; fuer das
Nowcast-Ende gibt es keine Briefing-Entsprechung, mit der es sich widersprechen koennte. (c) Ein
still gekapptes „Ende gegen 20:00" bei Regen bis 22:00 ist eine **falsche Aussage** — dieselbe
Fehlerklasse wie R4, nur selbst verursacht. Die strategische Bewertung schlug einen Mittelweg vor
(kappen + Fortsetzungs-Hinweis „haelt ueber das Tagesfenster hinaus an"); der fuehrt einen Begriff
ein, den der Nowcast sonst nirgends kennt, und erkauft nichts, was das echte Ende nicht auch
liefert.

**(E3) Horizont — der im Issue offene PO-Entscheid.** *Empfehlung: (b) voller Horizont mit
Guete-Kennzeichnung; `_NOWCAST_HORIZON_MIN` bleibt bei 180.* Eine Kappung auf 60 wuerde die
#1945-Entscheidung still zuruecknehmen (dort bewusst 60 → 180, weil der Deckel den Alarm
praktisch immer erst ~8 Min vorher ausloesen liess). Der **Alarm**zweig waere von der Kappung
ohnehin kaum betroffen, weil er bereits hart bei 55 Min deckelt; treffen wuerde sie
`window_precip_mm`, `onset_precip_mm`, den Briefing-Hinweis und die Kommando-Antwort — also
genau die Pfade, aus denen der geschilderte Realfall stammt. Der
`event_ongoing_beyond_horizon`-Waechter **ist** bereits die vom PO erwogene Guete-Kennzeichnung.

## Horizont-Drift in Nutzertexten — **gehoert in S1**, als eigenes AC

Seit #1945 (`_NOWCAST_HORIZON_MIN` 60 → 180) sind **zwei** Textstellen nicht nachgezogen worden:

| Stelle | Text heute | Wahrheit |
|---|---|---|
| `src/services/radar_service.py:431` (Trockenzweig von `format_now_text`) | „In den naechsten 2 Stunden kein Regen erwartet." | geprueft werden **3 Stunden** |
| `src/output/renderers/email/starkregen_hint.py:4` (Docstring) | „60-Minuten-Nowcast-Fenster (`NOWCAST_HORIZON_MIN`)" | 180 Minuten |

**Entscheidung:** kein eigenes Issue, kein Sammel-Eintrag — **eigenes AC in dieser Spec**, mit
Test und eigenem Commit. Begruendung: eine falsche Zahl in nutzersichtbarem Text ist mehr als
kosmetisch, aber S1 fasst genau diese Funktion ohnehin an; ein eigenes Ticket waere
Backlog-Inflation, eine stille Nebenreparatur waere ein Nachweis-Loch. Zusaetzlicher Grund: sobald
der Nass-Zweig derselben Funktion ein bis zu 3 Stunden entferntes Ende nennt, steht die falsche
„2 Stunden"-Aussage des Trockenzweigs unmittelbar daneben.
Der Docstring-Teil ist reine Doku und faellt nicht unter das LoC-Limit.
