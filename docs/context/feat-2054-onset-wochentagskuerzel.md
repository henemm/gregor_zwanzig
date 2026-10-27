# Context: feat-2054-onset-wochentagskuerzel

Issue: [#2054](https://github.com/henemm/gregor_zwanzig/issues/2054) · Milestone „Tour KHW 2026-08" ·
Label `enhancement` · Basis `origin/main` = `5c8ece93`

## Request Summary

Die Onset-Kurznachricht (SMS · Premium-SMS · Telegram-Kurzstil) hängt bei Mitternachts-Überlauf
heute ein Zahlensuffix an die Uhrzeit (`R2.5@0:23+1`). Der Empfänger muss selbst rechnen, welcher
Tag gemeint ist. Ersetzt wird es durch das **Wochentagskürzel** (`R2.5@Sa0:23`) — dieselbe
Schreibweise, die derselbe Kanal für Abweichungs- und amtliche Warn-Alarme bereits führt.

## Der eigentliche Zweck: EINE Schreibweise, nicht bloß eine bessere

Der Ursprung der Entscheidung steht in `docs/specs/modules/fix_2020_alarm_blickrichtung.md`,
Abschnitt „Zur Entscheidung mit der Freigabe" (Z. 418-434) — nicht im Ticket:

> **Zieht der Radar-Onset-Kurzform-Zweig nach?** Er schreibt denselben Sachverhalt heute als
> Zahlensuffix. Bleibt er so, trägt der Kurzkanal **zwei Schreibweisen für „Uhrzeit an einem
> anderen Tag" nebeneinander**.
> **Empfehlung:** Wochentagskürzel für beide Zweige — dann gibt es genau eine Schreibweise.

Die zu prüfende Zusicherung ist damit nicht „das Kürzel erscheint", sondern **„der Kurzkanal kennt
danach nur noch eine Schreibweise für Tagesbezug"**. Ein Test, der nur das neue Token prüft, ohne
die Abwesenheit der Altform zu belegen, bewacht die Entscheidung nicht.

> ⚠️ `docs/specs/modules/fix_2020_alarm_zeitangaben.md` trägt `status: superseded` — dort **nicht**
> nachschlagen.

## Der Zuschnitt ist größer als das Ticket ihn beschreibt

Das Ticket nennt einen Wirkort (den Regenbeginn). Tatsächlich sind es **drei** — beide Zuwächse
entstanden am selben Tag, nach der Ticket-Erstellung:

| Aufrufer | Datei:Zeile (Stand `1e0ee151`) | Token |
|---|---|---|
| Beginn | `render.py:854` | `R2.5@18:00` |
| **Ende** (#2051 S1, Merge `5c8ece93`) | `render.py:825` (`_sms_onset_ende`) | `@20:00` bzw. ` >@20:00` |
| **Ereignis läuft bereits** (#2050 S2b, Merge `d2c7c86a`) | `render.py:862` | `R2.5 now >@20:00` — kein Beginn-Token, **aber** ein Ende-Token |

> ⚠️ Der dritte Zweig kam **nach** der Spec-Freigabe hinzu. Er zeigt `now` statt einer Beginnzeit,
> erbt das Ende-Token aber über denselben Aufruf — ein über Mitternacht laufendes Ereignis trägt
> dort heute `+1`. Abgedeckt durch das nachgetragene AC-14.

Beide Zeitpunkte tragen einen **eigenen** Tagesversatz — Beginn 23:50 (Versatz 0) und Ende 00:40
(Versatz 1) liegen an verschiedenen Kalendertagen; #2051 hat das in seinem AC-6 festgenagelt.
Die Umstellung wirkt über den geteilten Aufruf automatisch auf beide. **Ein Kürzel, das nur am
Beginn geprüft wird, ginge am Ende still schief.**

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:729` | `_sms_onset_time(onset_time, day_offset)` — **der Wirkort**. Modulprivat, genau zwei Aufrufer (`:796`, `:825`), kein Test importiert sie direkt |
| `src/output/renderers/alert/render.py:1276` | `_sms_day_prefix(day_offset, weekday)` — die **Darstellungs-Vorlage** aus #2020 S2 |
| `src/output/renderers/alert/official_alerts.py:93,802` | `_DE_WEEKDAYS` / `_de_weekday_short(dt)` — die Kürzel-Tabelle. #2020-Spec markiert sie ausdrücklich als „reuse — **nicht** nachbauen" |
| `src/output/renderers/alert/project.py:179-193` | `_when_fields(target_utc, now_utc, tz) -> (offset, is_past, weekday)` — der **Bildungs-Baustein**. Nutzt `_de_weekday_short` (Import `project.py:23`); wird für `OnsetShiftEvent` und `_remaining_fields` verwendet, **aber nicht für `OnsetEvent`** |
| `src/output/renderers/alert/model.py:97,~113` | `OnsetEvent.onset_day_offset` / `.event_end_day_offset` — beide **ohne** Wochentags-Pendant |
| `src/output/renderers/alert/project.py:544` | Konstruktion Ortsvergleich-Bündel — `datetime` + `loc_tz` lokal vorhanden |
| `src/services/trip_alert.py:1509` | Baut `RadarAlertRequest`; `_onset_dt` + `tz` liegen unmittelbar davor (`:1434`) — hier entsteht heute `onset_day_offset` |
| `src/services/notification_service.py:168-218` | `RadarAlertRequest` — trägt `onset_day_offset`, `event_end_day_offset`, **kein** Wochentagsfeld |
| `src/services/notification_service.py:1338` | Baut daraus das `OnsetEvent` (Trip-Versandpfad) |
| `api/routers/validator.py:226` | `OnsetPayload` — **trägt `onset_day_offset` überhaupt nicht** (verifiziert) |
| `src/services/validator_render_service.py:116` | Vorschau-Konstruktion; setzt `onset_day_offset` nicht ⇒ bleibt still auf `0` |
| `tests/tdd/test_alert_onset_day_rollover.py:115-139,286-321` | **Nagelt die `+1`-Form als erwarteten String fest** — muss umgeschrieben werden, ist zugleich die Struktur-Vorlage für RED |

## Existing Patterns

**Das Muster existiert dreifach im Repo — es wird nichts erfunden.**

1. **Modell-Konvention:** pro Zeitangabe ein Tripel `<name>_time` + `<name>_day_offset` +
   `<name>_weekday` (`AlertEvent.occurred_*`, `.remaining_until_*`, `model.py:44-69`).
   `OnsetEvent` hat heute zweimal nur die ersten beiden Glieder.
2. **Bildung:** `_when_fields()` liefert alle drei Größen aus einer Hand — bewusst, „damit
   Kalendertag und Vergangenheits-Kennzeichen nie aus verschiedenen Zonen stammen". Der Wochentag
   entsteht aus `local_dt(target_utc, tz)`, also in **Trip-Ortszeit**, und nur bei Versatz ≠ 0.
3. **Darstellung Kurzform:** `_sms_day_prefix()` setzt das Kürzel **vor** die Zeit (`@Do15`) und
   entfällt am Versandtag ersatzlos.

**Abweichung, die die Spec entscheiden muss:** Die Vorlage arbeitet mit **Stunden**-Granularität
(`e.occurred_at[:2]` → `@Do15`), der Onset mit **Stunde:Minute** (`@0:23`). Die Kürzel-*Position*
ist übertragbar, die Zeit*form* nicht — sonst verlöre die Onset-Angabe ihre Minuten.

**Langform bleibt unberührt:** E-Mail/Telegram schreiben den Tagesbezug als Wort aus
(`_time_with_day` → „morgen 17:00"). Kurzform = Kürzel, Langform = Wort ist eine bewusste
Trennung, keine Inkonsistenz.

## Dependencies

- **Upstream:** `_de_weekday_short` · `_when_fields` · `day_offset()`/`local_dt()`
  (`src/utils/timezone.py`) · `event_end_display()` (`project.py:37`, aus #2051 S1)
- **Downstream:** `_render_sms_onset` (SMS · Premium-SMS · Telegram-Kurzstil) und über den
  geteilten Aufruf `_sms_onset_ende`

## Existing Specs

| Spec | Bedeutung |
|---|---|
| `docs/specs/modules/fix_2020_alarm_blickrichtung.md` | **Ursprung der PO-Entscheidung** (Z. 418-434); markiert `_de_weekday_short` als reuse |
| `docs/specs/modules/fix_2009_nowcast_vorlauf.md` | führte den abzulösenden `+1`-Suffix ein |
| `docs/specs/modules/feat_2051_s1_dauer_und_ende.md` | der zweite Wirkort (Ende-Token), AC-6 = eigener Tagesversatz |
| `docs/specs/modules/fix_2046_onset_menge.md` | AC-9 = 160-Zeichen-Budget der Kurznachricht |

## Risks & Considerations

1. **🔴 Der Vorschau-Weg ist blind für diesen Sachverhalt — verifiziert.**
   `OnsetPayload` (`api/routers/validator.py:226`) kennt `onset_day_offset` nicht; der Vorschau-Bau
   setzt es nicht, es bleibt auf `0`. **`alert-preview` kann einen Mitternachts-Überlauf beim
   Beginn strukturell nicht zeigen** — weder die Alt- noch die Neuform. Ein nur dort geprüftes
   Kriterium wäre grün, ohne etwas zu bewachen. Das ist dasselbe Muster, das bei #2020 elf von
   vierzehn Kriterien unmessbar machte (#2069).
   → **Empfehlung für die Spec:** `OnsetPayload` um die fehlenden Felder erweitern. Schließt
   zugleich eine bestehende stille Lücke. Sonst: ACs auf Kern-Ebene und die Grenze ausdrücklich
   als SKIP buchen, nicht schönreden.
2. **Zwei Herkünfte, ein Konstruktor.** Trip-Pfad (`trip_alert.py:1509` → `RadarAlertRequest` →
   `notification_service.py:1338`, nur Strings/Ints) und Ortsvergleich-Pfad (`project.py:544`,
   `datetime` lokal). Der Wochentag muss in **beiden** dort gebildet werden, wo heute schon
   `day_offset()` entsteht — ein vergessener Pfad rendert still die Altform.
3. **Bestandstest nagelt die Altform fest — zwei Stellen.** `test_alert_onset_day_rollover.py`
   erwartet wörtlich `"TH@0:23+1"` (`:120`, Trip-Pfad) und `"R@0:23+1"` (`:313`,
   Ortsvergleich-Bündel) und prüft zusätzlich `"+1" not in control_sms` (`:139`, bleibt grün).
   Umschreiben, nicht löschen — die Datei bringt 160-Zeichen-Grenze, Token-Zeichensatzprüfung und
   Kontrollfall schon mit.
   ⚠️ **Falle:** Der Token-Regex `r"(TH|R)@\d{1,2}:\d{2}(?:\+\d+)?"` (`:128`) matcht ein Kürzel
   zwischen `@` und Stunde **nicht**. Er muss zuerst erweitert werden, sonst scheitert der Test an
   `token_match is None`, bevor die eigentliche Zusicherung überhaupt greift — der Test wäre aus
   dem falschen Grund rot.
4. **Zeichenbudget — nachgerechnet, für #2054 unkritisch.**
   Die Umstellung ist **zeichenneutral**: `0:23+1` und `Sa0:23` sind beide sechs Zeichen.
   `_render_sms_onset` rendert zudem nur `msg.events[0]` — auch im Ortsvergleich-Bündel steht
   genau **ein** Zeit-Token in der Nachricht. Der längste Token-Fall (Gewitter, beide Kürzel,
   Untergrenzen-Form, Menge) misst rund 26 Zeichen.
   ⚠️ **Korrektur einer früheren Annahme dieser Analyse:** Der längste Fall entstand mit #2051 S1
   (zweites Zeit-Token), **nicht** mit #2054. #2054 vergrößert ihn nicht. Ein Absichern des
   Schnitts gehört daher **nicht** in dieses Ticket — siehe Punkt 9.
   Bezug bleibt AC-9 in `fix_2046_onset_menge.md` (160-Zeichen-Grenze). `140` ist im Produktivcode
   dreifach als Default dupliziert, ohne zentrale Konstante.
9. **🔴 Bestandsrisiko, eigenes Ticket: der Kopf wird nicht gekappt, der Schnitt ist hart.**
   `_render_sms_onset` bildet `head = _ascii_alert_location(...)` **ohne jede Längenbegrenzung**
   — anders als die Nachbarzweige, die auf `[:16]`/`[:24]` kürzen (`_render_sms_corridor_only`).
   Am Ende steht `return body if len(body) <= limit else body[:limit]` (`render.py:844`), ein
   harter Schnitt mitten durch den Text. Bei ausreichend langem Ortsnamen wird das **Zeit-Token
   angeschnitten oder ganz abgeschnitten**: aus `@Sa0:40` wird `@Sa0:4` oder `@Sa` — keine
   gekürzte, sondern eine **falsche** Aussage, auf dem einzigen Kanal, der auf der Hütte am
   Karnischen Höhenweg ankommt und wo kein zweiter Kanal sie richtigstellt.
   Latent und von #2054 **nicht verursacht**, aber durch das zweite Zeit-Token aus #2051
   näher an die Grenze gerückt. Gehört als eigenes Issue erfasst (Nebenbefund-Triage Fall (a):
   nutzersichtbares Fehlverhalten), nicht in die Sammelliste #1199.
5. **GSM-7 ist geklärt** (PO-Kommentar im Ticket): Die amtliche Warn-SMS versendet die Kürzel seit
   #1948 S5 über denselben Kanal. Reines ASCII, kein offener Punkt für #2054.
   *Nebenbefund (kein Ticket-Ziel):* Es gibt einen geteilten Validator
   `tests/tdd/_gsm7_charset.py::assert_gsm7_clean`, der gegen den **Onset-Pfad nicht** verwendet
   wird — dort prüft nur `sms.isascii()`, was Extension-Zeichen (`[`, `]`, `{`, `}`, `\`, `^`,
   `~`, `|`, `€`) durchlässt, die real zwei Septets kosten. Kandidat für #1199, nicht für diese
   Arbeit.
6. **`day_offset >= 2` ist strukturell ausgeschlossen** (der Nowcast schaut nur nach vorn), aber es
   braucht ein *definiertes* Verhalten statt stiller Fehlausgabe.
7. **Abgrenzung `build_onset_alert_message`** (`radar_alert_service.py:31`): hängt nur am
   Debug-Endpoint (`api/routers/debug.py:110`) und kennt schon heute die `event_end_*`-Felder
   nicht. **Nicht mitziehen.**
8. **Getrennt bleibt #2063** (Onset-Uhrzeit oft eine Minute zu früh — Sekunden werden abgeschnitten
   statt gerundet, `src/utils/timezone.py:133`). Berührt dieselbe Zeile, ist aber ein anderer
   Fehlermechanismus mit anderer Beweisführung. Preis: die Zeile geht ein zweites Mal auf.

## Koordination mit Parallelsitzungen

`_sms_onset_time` ist dieser Session zugesagt: Session `2051` (#2051, geliefert) und
`gregor-zwanzig-42` (#2050 S2b) halten sich dort raus. #2049, #2073 und #2065 arbeiten in anderen
Dateien. `gregor-zwanzig-42` bearbeitet `render.py` im Bereich `_onset_time_label` (~:502) —
Langform, von dieser Arbeit unberührt.

---

## Analysis

### Type

**Feature** (Label `enhancement`, PO-freigegebene Änderung an bestehendem Verhalten). Kein
Bug-Intake nötig.

### Technical Approach

**Grundsatz: kein neues Muster.** Die Kürzel-Tabelle (`_de_weekday_short`), die Bildungsregel
(„nur bei Versatz ≠ 0", Wochentag aus `local_dt(target, tz)`) und die Darstellungsregel (Kürzel
**vor** die Zeit) existieren. #2054 zieht `OnsetEvent` auf die Konvention nach, die `AlertEvent`
längst erfüllt.

**Zwei neue Modellfelder** (`model.py`): `onset_weekday: str | None = None` und
`event_end_weekday: str | None = None` — das jeweils dritte Glied der bestehenden Tripel-Konvention
`<name>_time` + `<name>_day_offset` + `<name>_weekday`.

> *Verworfen:* den Wochentag im Renderer aus `day_offset` + Versandzeit zurückrechnen (spart die
> Felder). Verliert, weil der Renderer weder `now` noch `tz` kennt — eine zweite „jetzt"-Quelle
> bricht genau die Invariante, die `_when_fields()` im Docstring einfordert („Kalendertag und
> Vergangenheits-Kennzeichen nie aus verschiedenen Zonen").

**Bildungsstellen — drei, nicht eine:**

| Zeitpunkt | Stelle | Anmerkung |
|---|---|---|
| Ende | `project.py:37` `event_end_display()` | bereits **geteilt** für beide Pfade → 4. Rückgabewert ergänzen, deckt Trip und Ortsvergleich auf einen Schlag |
| Beginn (Trip) | `trip_alert.py:1512` | braucht neuen Import `_de_weekday_short` + `local_dt` |
| Beginn (Ortsvergleich) | `project.py:544` | |

> *Verworfen:* `_when_fields()` direkt wiederverwenden. Verliert, weil sie modulprivat in
> `project.py` liegt, ein hier unnötiges `is_past` mitliefert und `trip_alert.py` sie
> modulübergreifend importieren müsste. Wiederverwendet wird stattdessen ihr **Baustein**
> `_de_weekday_short` — genau wie die #2020-Spec es vorschreibt.

**Der Wirkort** (`_sms_onset_time`) bekommt einen dritten Parameter. Entscheidend: **das Gate
bleibt `day_offset`, nicht der Wahrheitswert von `weekday`.** Der Versatz ist die Quelle der
Wahrheit, das Kürzel nur seine Darstellung.

### Zielform

| Fall | Token |
|---|---|
| Beginn, kein Überlauf | `R2.5@18:00` *(unverändert)* |
| Beginn, Überlauf | `R2.5@Sa0:23` |
| Ende bekannt, kein Überlauf | `R2.5@18:00@20:00` *(unverändert)* |
| Ende bekannt, Überlauf | `R2.5@23:50@Sa0:40` |
| Ende als Untergrenze, Überlauf | `R2.5@23:50 >@Sa0:40` |
| Gewitter, Überlauf | `TH@Sa0:23 R2.5` |

### 🔴 Der gefährlichste Fehlermodus: die Lücke ist stiller als die Altform

Wird eine der beiden Beginn-Bildungsstellen vergessen, bleibt `onset_day_offset` korrekt
(Bestandscode), aber `onset_weekday` bleibt `None`. Mit dem Gate auf `day_offset` rendert
`_sms_onset_time` dann die **nackte Uhrzeit ohne jeden Tagesbezug** — also exakt die
Mehrdeutigkeit, die #2009 ursprünglich beseitigen sollte, und schlimmer als ein Rückfall auf `+1`.

**Folge für die Testführung:** Ein Test, der nur die *Abwesenheit* von `+N` prüft, fängt das
**nicht**. Jeder Matrix-Fall braucht zusätzlich die **positive** Zusicherung des erwarteten
Kürzel-Tokens. Und mindestens ein Fall muss über den **echten Versandpfad** laufen
(`TripAlertService.check_radar_alerts()` bzw. der Ortsvergleich-Pfad), nicht nur über handgebaute
`OnsetEvent`-Fixtures — sonst bleibt eine vergessene Bildungsstelle unsichtbar. Genau dieser
Fehler ist bei #2009 schon einmal passiert und im Fix-Loop F001 der Bestandstestdatei dokumentiert
(`test_alert_onset_day_rollover.py:141-165`).

### „Genau EINE Schreibweise" prüfbar machen

Negativ-Zusicherung als reine Ausgabeprüfung über den echten Renderer-Einstieg (`render_sms()`):

```python
assert not re.search(r"\d{1,2}:\d{2}\+\d+", sms)
```

Geht rot, sobald irgendwo wieder ein Zahlensuffix entsteht — unabhängig davon, an welcher der
Bildungsstellen die Regression passiert.

> *Verworfen:* Quelltext-Grep auf `+{day_offset}`. Verliert doppelt: Dateiinhalt-Checks sind als
> Verhaltensnachweis untersagt, und der Test würde bei jeder Umformulierung falsch anschlagen.

### Affected Files

| Datei | Art | LoC | Beschreibung |
|---|---|---|---|
| `src/output/renderers/alert/model.py` | MODIFY | +12 | zwei Wochentagsfelder am `OnsetEvent` |
| `src/output/renderers/alert/project.py` | MODIFY | +18 | `event_end_display()` 4. Rückgabewert; Ortsvergleich-Bündel |
| `src/services/trip_alert.py` | MODIFY | +10 | Import + Bildung am Trip-Beginn |
| `src/services/notification_service.py` | MODIFY | +12 | `RadarAlertRequest` + Durchreichung |
| `src/output/renderers/alert/render.py` | MODIFY | +15 | **Wirkort**: `_sms_onset_time`, beide Aufrufer |
| `api/routers/validator.py` | MODIFY | +10 | `OnsetPayload` (siehe unten) |
| `src/services/validator_render_service.py` | MODIFY | +6 | Durchreichung Vorschau |
| `tests/tdd/test_alert_onset_day_rollover.py` | MODIFY | +55 | Regex-Fix, Umstellung, Matrix, echter-Pfad-Fall |

**~140 LoC** — unter dem 250er-Limit, kein `loc_limit_override` nötig.

### Entscheidung: Vorschau-Felder werden mitgezogen

`OnsetPayload` kennt `onset_day_offset` heute nicht; für #2054 kämen die beiden Wochentagsfelder
hinzu. Der Vorschaudienst rechnet nichts selbst, er reicht nur durch — die Felder wären reiner
Passthrough im bereits dreifach etablierten Muster (`onset_precip_mm`, `event_end_time`,
`event_end_day_offset`). Aufwand: ~16 LoC.

**Begründung:** Es ist derselbe Fehlermodus, der bei #2069 elf von vierzehn und bei #2036 dreizehn
von fünfzehn Kriterien strukturell unmessbar gemacht hat — beide Male, weil `alert-preview` ein
Feld nicht kennt, das der Versandpfad längst führt. Diese Falle für ~16 LoC ein drittes Mal zu
bauen, wäre nicht sparsam, sondern fahrlässig.

### Abgrenzungen

- **`build_onset_alert_message`** (`radar_alert_service.py:31`) wird **nicht** mitgezogen — nur
  Debug-Endpoint, kennt schon die `event_end_*`-Felder nicht.
- **Der harte 140-Schnitt** (Risiko 9) bekommt ein eigenes Issue — #2054 verursacht ihn nicht.
- **#2063** (Onset-Uhrzeit eine Minute zu früh) bleibt getrennt.
- **Go-Seite** ist nicht betroffen (`grep onset internal/ cmd/` → keine Treffer).

### Reihenfolge

1. **Zuerst den Token-Regex** im Bestandstest (`:128`) auf die Kürzel-Form erweitern — sonst ist
   der erste rote Lauf aus dem falschen Grund rot (`token_match is None`).
2. Modellfelder (Fundament für alle Konstruktionen).
3. `event_end_display()` (eine Stelle, beide Pfade).
4. Beide Beginn-Bildungsstellen.
5. DTO-Durchreichung.
6. **Der Renderer zuletzt** — erst wenn 2–5 echte Werte liefern, wird der RED-Test aus dem
   richtigen Grund grün.
7. Vorschau-Zweig (unabhängig, vor der Staging-Verifikation).

### Open Questions

Keine offenen Fragen an den PO. Alle Design-Entscheidungen sind aus dokumentierten Vorgaben
ableitbar (#2020-Spec, Tripel-Konvention, Nebenbefund-Triage) und oben mit verworfenen
Alternativen begründet.
