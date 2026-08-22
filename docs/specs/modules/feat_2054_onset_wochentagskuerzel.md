---
entity_id: feat_2054_onset_wochentagskuerzel
type: module
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [alert, sms, premium-sms, telegram, nowcast, onset, zeitangabe]
---

# Onset-Kurznachricht: Wochentagskürzel statt Zahlensuffix

Issue: [#2054](https://github.com/henemm/gregor_zwanzig/issues/2054) · Milestone „Tour KHW 2026-08"
Basis: `origin/main` = `1e0ee151`

## Approval

- [x] Approved — PO (Henning), 2026-08-22

## Purpose

Die Alarm-Kurznachricht (SMS · Premium-SMS · Telegram-Kurzstil) schreibt eine Uhrzeit, die an einem
anderen Kalendertag liegt, heute als Zahlensuffix (`R2.5@0:23+1`). Der Empfänger muss selbst
rechnen. Künftig steht dort das **Wochentagskürzel** (`R2.5@Sa0:23`) — dieselbe Schreibweise, die
derselbe Kanal für Abweichungsalarme (`@Do15`, #2020 S2) und amtliche Warnungen (`Do12-22`,
#1948 S5) bereits führt.

**Der Zweck ist Vereinheitlichung, nicht Verschönerung.** Bis heute trägt der Kurzkanal zwei
Schreibweisen für denselben Sachverhalt nebeneinander. Danach kennt er genau eine. Diese
Zusicherung — die *Abwesenheit* der Altform — ist Teil der Akzeptanz (AC-8), nicht bloß eine
Nebenwirkung.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_sms_onset_time(onset_time, day_offset)` (`:729`)

Schicht: **Python-Core / Domain-Backend**. Frontend und Go-API sind nicht betroffen
(`grep onset internal/ cmd/` → keine Treffer).

## Estimated Scope

- **LoC:** ~140 (unter dem 250er-Limit, kein Override nötig)
- **Files:** 8 (7 MODIFY Produktivcode/API, 1 MODIFY Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `official_alerts.py:802` `_de_weekday_short(dt)` | **reuse** | liefert das Kürzel. Die #2020-Spec markiert es ausdrücklich als „**nicht** nachbauen" — eine zweite Tabelle wäre ein Verstoß gegen eine dokumentierte Entscheidung |
| `utils/timezone.py` `local_dt()` / `day_offset()` | reuse | Ortszeit-Auflösung; **dieselbe** `tz`-Instanz wie der Versatz |
| `project.py:37` `event_end_display()` | MODIFY | bereits geteilte Stelle beider Pfade — trägt den Wochentag des **Endes** als 4. Rückgabewert |
| `project.py:179` `_when_fields()` | Muster (kein Reuse) | liefert die Bildungsregel („nur bei Versatz ≠ 0", Wochentag aus `local_dt(target, tz)`); modulprivat und mit unnötigem `is_past` — übernommen wird die Regel, nicht die Funktion |
| `render.py:1276` `_sms_day_prefix()` | Muster (kein Reuse) | Darstellungsregel: Kürzel **vor** die Zeit; arbeitet aber mit Stunden-Granularität, der Onset braucht Stunde:Minute |
| `feat_2051_s1_dauer_und_ende.md` | Vorgänger | brachte das **zweite** Zeit-Token (Ende) an denselben Renderer-Aufruf |

## Implementation Details

**Modell** (`model.py`) — zwei Felder, drittes Glied der bestehenden Tripel-Konvention
(`<name>_time` + `<name>_day_offset` + `<name>_weekday`, wie `AlertEvent.occurred_*`):

```python
onset_weekday: str | None = None
event_end_weekday: str | None = None
```

**Drei Bildungsstellen** — überall dort, wo heute schon der Versatz entsteht:

| Zeitpunkt | Stelle | Deckt ab |
|---|---|---|
| Ende | `project.py:37` `event_end_display()` → 4. Rückgabewert | **beide** Pfade auf einen Schlag |
| Beginn (Trip) | `trip_alert.py:1512` | Trip-Radar-Alarm |
| Beginn (Ortsvergleich) | `project.py:544` | Ortsvergleich-Bündel |

Jeweils: `weekday = _de_weekday_short(local_dt(dt, tz)) if offset else None`

**Wirkort** (`render.py`) — dritter Parameter, Gate bleibt auf `day_offset`:

```python
def _sms_onset_time(onset_time: str, day_offset: int = 0, weekday: str | None = None) -> str:
    hour, sep, rest = onset_time.partition(":")
    base = onset_time if not sep else f"{hour.lstrip('0') or '0'}:{rest}"
    return f"{weekday or ''}{base}" if day_offset else base
```

Der **Versatz** entscheidet, ob ein Tagesbezug gezeigt wird; das Kürzel ist nur seine Darstellung.
Ein Gate auf den Wahrheitswert von `weekday` würde bei fehlendem Kürzel still den Tagesbezug
verschlucken.

**Durchreichung:** `RadarAlertRequest` (`notification_service.py:168`) und `OnsetPayload`
(`api/routers/validator.py:226`) bekommen die Felder additiv und optional — reiner Passthrough im
dreifach etablierten Muster (`onset_precip_mm`, `event_end_time`, `event_end_day_offset`).

## Expected Behavior

- **Input:** ein Onset-Alarm, dessen Regenbeginn und/oder Ereignis-Ende an einem anderen
  Kalendertag liegt als der Versandzeitpunkt (Ortszeit des Trips bzw. des Ortes).
- **Output:** Kurznachricht, in der jede betroffene Uhrzeit ein vorangestelltes Wochentagskürzel
  trägt. Uhrzeiten am Versandtag bleiben **unverändert**.
- **Side effects:** keine. Kein Versand, keine Persistenz, keine Schwellen- oder Auslöselogik wird
  berührt. E-Mail und Telegram-Langform bleiben bei ihrer Wortform („morgen 17:00").

### Zielform

| Fall | Kurznachricht |
|---|---|
| Beginn, kein Überlauf | `R2.5@18:00` *(unverändert)* |
| Beginn, Überlauf | `R2.5@Sa0:23` |
| Ende bekannt, kein Überlauf | `R2.5@18:00@20:00` *(unverändert)* |
| Ende bekannt, Überlauf | `R2.5@23:50@Sa0:40` |
| Ende als Untergrenze, Überlauf | `R2.5@23:50 >@Sa0:40` |
| Gewitter, Überlauf | `TH@Sa0:23 R2.5` |

## Acceptance Criteria

- **AC-1:** Given ein Trip-Radar-Alarm, dessen Regenbeginn hinter Mitternacht auf einen Samstag
  fällt / When die Kurznachricht erzeugt wird / Then trägt die Uhrzeit das vorangestellte Kürzel
  `Sa` und **kein** Zahlensuffix.
  - Test: Alarm über den echten Versandpfad auslösen, zugestellten `sms_body` prüfen — Token
    enthält `@Sa0:23`, nicht `@0:23+1`.

- **AC-2:** Given denselben Alarm, aber mit einem Regenbeginn **am Versandtag** / When die
  Kurznachricht erzeugt wird / Then ist sie zeichengleich zum heutigen Bestand — kein Kürzel, kein
  Suffix, keine sonstige Abweichung.
  - Test: Kontrollfall mit Versatz 0 gegen den festgeschriebenen Bestands-String; diese Eigenschaft
    macht die Umstellung regressionsfrei (ausdrücklich im Ticket-Kommentar gefordert).

- **AC-3:** Given einen Alarm, dessen **Ereignis-Ende** hinter Mitternacht fällt / When die
  Kurznachricht erzeugt wird / Then trägt auch die Endzeit das Kürzel.
  - Test: `event_end_day_offset=1` über den Renderer; Endzeit-Token zeigt `@Sa0:40`. Bewacht den
    zweiten Wirkort, den das Ticket nicht kennt.

- **AC-4:** Given einen Alarm, der um 23:50 beginnt und um 00:40 endet / When die Kurznachricht
  erzeugt wird / Then trägt **nur die Endzeit** ein Kürzel, die Beginnzeit nicht — beide Zeitpunkte
  werden unabhängig voneinander bewertet.
  - Test: Beginn-Versatz 0, Ende-Versatz 1 in einer Nachricht; Ergebnis `R2.5@23:50@Sa0:40`.

- **AC-5:** Given ein Ereignis, dessen Ende nur als **Untergrenze** bekannt ist („regnet mindestens
  bis"), und das hinter Mitternacht reicht / When die Kurznachricht erzeugt wird / Then bleibt das
  Untergrenzen-Zeichen `>` erhalten und das Kürzel steht dahinter.
  - Test: Ergebnis ` >@Sa0:40`. Ohne das `>` kippt die Aussage von „regnet mindestens bis" zu „hört
    auf um" (#2051 AC-20) — das Kürzel darf diese Unterscheidung nicht verdrängen.

- **AC-6:** Given einen **Gewitter**-Onset mit Mitternachts-Überlauf / When die Kurznachricht
  erzeugt wird / Then trägt die Uhrzeit das Kürzel genauso wie beim Regen.
  - Test: `is_convective=True`; Ergebnis `TH@Sa0:23 R2.5`. Das Ticket verlangt die Umstellung
    ausdrücklich für **beide** Zweige.

- **AC-7:** Given einen **Ortsvergleich**-Onset-Alarm mit Mitternachts-Überlauf / When die
  Kurznachricht erzeugt wird / Then trägt sie das Kürzel genauso wie der Trip-Alarm.
  - Test: über den Ortsvergleich-Versandpfad, nicht über gebaute Testdaten — bewacht die zweite
    Bildungsstelle, die sonst still ausbleibt.

- **AC-8:** Given **irgendeinen** Onset-Alarm in irgendeiner Zusammenstellung / When die
  Kurznachricht erzeugt wird / Then enthält sie **nirgends** ein Zahlensuffix hinter einer Uhrzeit.
  - Test: Negativprüfung `\d{1,2}:\d{2}\+\d+` über eine Fallmatrix (Beginn-Versatz × Ende-Versatz ×
    Ende-Form × Regen/Gewitter × läuft-bereits). Dies ist die Zusicherung „genau **eine**
    Schreibweise" — sie geht rot, egal an welcher Bildungsstelle eine Regression entsteht.

- **AC-9:** Given einen Ort, dessen Ortszeit von UTC abweicht, und einen Zeitpunkt kurz nach
  Mitternacht Ortszeit / When das Kürzel gebildet wird / Then nennt es den Wochentag der
  **Ortszeit**, nicht den der UTC-Zeit.
  - Test: Zeitzone mit Versatz (z. B. Europe/Vienna) und ein Zeitpunkt, an dem UTC- und Ortstag
    auseinanderfallen; erwartet wird der Ortstag. Verhindert einen um einen Tag falschen Wochentag
    bei korrektem Versatz.

- **AC-10:** Given ein Ereignis am Versandtag, bei dem versehentlich dennoch ein Wochentag am
  Datensatz hinterlegt ist / When die Kurznachricht erzeugt wird / Then erscheint **kein** Kürzel.
  - Test: `day_offset=0` zusammen mit gesetztem `weekday`; Ausgabe bleibt die nackte Uhrzeit. Sichert
    zu, dass der Versatz entscheidet und nicht das Vorhandensein des Kürzels.

- **AC-11:** Given den längsten Fall (Gewitter, Menge, Beginn **und** Ende mit Kürzel,
  Untergrenzen-Form) / When die Kurznachricht erzeugt wird / Then bleibt sie unter 160 Zeichen und
  besteht ausschließlich aus ASCII-Zeichen.
  - Test: Längen- und Zeichensatzprüfung am zusammengesetzten Ergebnis.

- **AC-12:** Given denselben Mitternachts-Überlauf / When die Alarm-**Vorschau** abgerufen wird
  / Then zeigt sie dieselbe Schreibweise wie der echte Versand.
  - Test: über `alert-preview` mit gesetztem Beginn-Versatz. Setzt voraus, dass Versatz und
    Wochentag in der Vorschau-Schnittstelle überhaupt ankommen — heute fehlt dort bereits der
    Versatz, weshalb die Vorschau den Sachverhalt gar nicht darstellen kann.

- **AC-14:** Given ein Ereignis, das **bereits läuft** (Kurzform zeigt `now` statt einer
  Beginnzeit) und dessen Ende hinter Mitternacht fällt / When die Kurznachricht erzeugt wird / Then
  trägt die Endzeit das Kürzel, und das `now` bleibt unverändert stehen.
  - Test: `already_running=True` mit Ende-Versatz 1; Ergebnis `R2.5 now >@Sa0:40`, kein `+1`.
    Nachgetragen am 2026-08-22: dieser dritte Renderzweig entstand durch #2050 S2b erst **nach**
    der Freigabe dieser Spec und erbt das Ende-Token über denselben Aufruf.

- **AC-13:** Given denselben Alarm / When E-Mail und Telegram-**Langform** erzeugt werden / Then
  schreiben sie den Tagesbezug unverändert als Wort („morgen 0:23"), nicht als Kürzel.
  - Test: Langform-Ausgabe gegen den Bestand. Kurzform = Kürzel, Langform = Wort ist eine bewusste
    Trennung und darf nicht angeglichen werden.

## Known Limitations

- **Ein Versatz von zwei oder mehr Tagen ist nicht darstellbar.** Der Nowcast schaut nur nach vorn,
  ein Onset kann also nicht zwei Tage entfernt liegen; das Kürzel bliebe in einem solchen Fall
  mehrdeutig (`Sa` ohne Angabe, welcher Samstag). Verhalten ist definiert — das Kürzel des
  Zieltages wird gezeigt —, ein Sonderfall wird bewusst **nicht** gebaut.
- **Der harte Zeichen-Schnitt der Kurznachricht bleibt bestehen.** Bei sehr langem Ortsnamen kann
  das Zeit-Token angeschnitten werden und eine falsche Uhrzeit ergeben. Von dieser Arbeit **nicht
  verursacht** (die Umstellung ist zeichenneutral) und deshalb hier nicht behoben → **#2078**.
- **Die Onset-Uhrzeit ist gelegentlich eine Minute zu früh** (Sekunden werden abgeschnitten statt
  gerundet). Anderer Fehlermechanismus, bleibt getrennt → **#2063**.
- **`build_onset_alert_message`** (`radar_alert_service.py:31`) zieht nicht nach — reiner
  Debug-Endpoint, der schon die `event_end_*`-Felder nicht kennt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Entscheidungsfeld. Die Grundsatzentscheidung („Wochentagskürzel für
  beide Zweige, damit es genau eine Schreibweise gibt") ist bereits gefallen und in
  `fix_2020_alarm_blickrichtung.md`, Abschnitt „Zur Entscheidung mit der Freigabe", festgehalten;
  vom PO am 2026-08-21 freigegeben. Diese Spec setzt sie um, sie trifft sie nicht.

## Changelog

- 2026-08-22: Initial spec created
- 2026-08-22: **AC-14 nachgetragen** — `#2050 S2b` (Merge `d2c7c86a`, nach der Freigabe) fügte den
  dritten Renderzweig „Ereignis läuft bereits" hinzu, der das Ende-Token über denselben Aufruf
  erbt. Additive Erweiterung der freigegebenen Richtung, keine neue Entscheidung; Fallmatrix in
  AC-8 entsprechend erweitert. Basis auf `1e0ee151` nachgezogen.
