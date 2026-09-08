---
entity_id: fix_1948_s4_nowcast_sms_zielbild
type: feature
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [alarm, sms, nowcast, format]
---

# Nowcast/Onset-SMS-Zielbild (Zweig c) — #1948 Scheibe S4

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-19, alle 11 Akzeptanzkriterien.

## Purpose

Die Nowcast-/Onset-Kurznachricht (Zweig c: Gewitter- und Regen-Anmarsch) zieht auf das
einheitliche Alarm-Format nach: Der Kopf spricht künftig die gemeinsame Ortsauflösung
(`format_alert_location`, Segment-Sprache statt selbstgebauter km-Notation), und das
Ereignis-Token wechselt vom Countdown (`TH!8`, „in 8 Minuten") auf einen konkreten
Zeitpunkt (`TH@15:40`, „ab 15:40 Uhr"). PO-Zielbild (Konzept v3, §1): **`Ziel: TH@15:40`**
— heute lautet dieselbe Nachricht `km8-8: TH!8`. Zusätzlich heilt diese Scheibe den
Ortsvergleich-Sonderfall mit genau einem Ort, der heute strukturell keinen Ortsnamen
zeigen kann.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_render_sms_onset()` (Z. 422-438)

Begleitend: `src/output/renderers/alert/project.py` (`to_multi_location_onset_alert_message`,
Z. 319-398 — neue benannte Konstante statt Freitext-Marker `"compare-radar"`).

## Estimated Scope

- **LoC:** ~120–170 (Renderer-Logik + Marker-Konstante + Testanpassungen, unter dem
  250-LoC-Workflow-Limit)
- **Files:** 2 Produktivdateien (`render.py`, `project.py`) + 7 Bestandstestdateien
  fortgeschrieben + mind. 1 neues Testmodul (TDD-RED)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OnsetEvent` | dataclass (`src/output/renderers/alert/model.py:37-56`) | Liefert `onset_time` (`str`, nie `None`), `onset_minutes`, `segment_id`, `location_label` — Grundlage jedes Onset-Tokens |
| `format_alert_location()` | function (`src/output/renderers/alert/segments.py:91-111`) | Die eine gemeinsame Ortsauflösung (`location_label` → Segment → km), die auch Trip-Δ/E-Mail/Telegram nutzen |
| `_location_of()` | function (`render.py:123-135`) | Ruft `format_alert_location` mit der km-Spanne eines Event-Tupels auf — Baustein des neuen Kopfes |
| `_ascii_alert_location()` | function (`render.py:989+`) | Entfernt Piktogramme (`🏁`) VOR der ASCII-Faltung — die einzig korrekte Trennstelle für SMS-Text (Verwechslungsgefahr mit `_ascii()`, s. Known Limitations) |
| `to_multi_location_onset_alert_message()` | function (`project.py:319-398`) | Baut die Ortsvergleich-Onset-`AlertMessage`; Quelle des Freitext-Markers `"compare-radar"`, der diese Scheibe zur benannten Konstante anhebt |
| `POST /api/trips/{trip_id}/alert-preview` | Endpunkt (S2, `alarm_testeinspeisung.md`) | Einspeiseweg für den Verifikationsnachweis über `nowcast_frames`, nutzt denselben `_derive_result` wie der Live-Pfad |
| `notification_service.render_sms`-Aufrufer | — (`src/services/notification_service.py:1373`) | Einziger Produktiv-Aufruf; Ergebnis geht an SMS **und** Premium-SMS mit gemeinsamem `limit=140` |

## Implementation Details

Neuer Funktionskörper für `_render_sms_onset` (Muster übernommen vom bereits produktiven
Trip-Δ-Kopf, `render.py:916`):

```python
COMPARE_RADAR_SOURCE = "compare-radar"  # in project.py definiert, hier importiert

def _render_sms_onset(msg: AlertMessage, limit: int = 140) -> str:
    e = msg.events[0]
    token = f"TH@{e.onset_time}" if e.is_convective else f"R@{e.onset_time}"
    if getattr(e, "location_label", None):
        # Mehr-Orte-Compare-Bündel: Kopf = Ortsname des führenden Events.
        head = _ascii_alert_location(e.location_label)
    elif msg.source == COMPARE_RADAR_SOURCE:
        # Ein-Ort-Compare (PO-Entscheid 3a): location_label bleibt laut
        # Invariante None, der Ortsname steht in msg.trip_short.
        head = _ascii_alert_location(msg.trip_short)
    else:
        # Trip-Radar: dieselbe Ortsauflösung wie Betreff/E-Mail/Telegram.
        head = _ascii_alert_location(_location_of((e,), None))
    body = f"{head}: {token}"
    return body if len(body) <= limit else body[:limit]
```

Begründung der Bausteinwahl (übernommen aus der Analyse):

- **Nicht** `_km_str_onset(e)` — die unterdrückt `location_label` absichtlich und wird von
  Telegram/Betreff mitbenutzt (`render.py:416`, Betreff-Zweig); eine Änderung dort würde
  ungefragt zwei weitere Kanäle mitverändern. `_km_str_onset` bleibt unangetastet.
- **Nicht** `_km_str(msg)` — liest `msg.location_label`, das für Onset-Nachrichten von
  keinem Konstruktor je gesetzt wird und damit strukturell immer `None` ist.
- Ein **lokaler** `_location_of((e,), …)`-Aufruf lässt die geteilten Bausteine unangetastet.

**Marker-Härtung (PO-Entscheid 3a).** `to_multi_location_onset_alert_message` setzt heute
den Freitext-Marker `source="compare-radar"` (`project.py:397`) ohne Vertrag. Diese Scheibe
hebt ihn zu einer benannten Konstante (`COMPARE_RADAR_SOURCE`) an und referenziert sie an
**beiden** Stellen — Setzen in `project.py`, Lesen in `render.py`. Ein künftiges Umbenennen
bricht damit sichtbar (Import-Fehler oder Konstanten-Vergleich schlägt fehl), statt die
Ortsanzeige unbemerkt auf `km 0–0` zurückfallen zu lassen (AC-7 sichert das ab).

**Testfalle — Wanduhr-Abhängigkeit (nicht Teil der Implementierung, aber Pflicht für die
Testanpassung):** `test_alert_sms_location_positions.py` und
`test_alert_preview_nowcast_replay.py` prüfen künftig `onset_time` (eine aus der aktuellen
Wanduhr abgeleitete Uhrzeit) statt der bisherigen Minutenzahl. Ein fester Goldstring wäre
zeitabhängig rot — beide Tests brauchen ein Zeitfenster-Toleranzband (z. B. Regex `\d{2}:\d{2}`
plus Plausibilitätsprüfung gegen `datetime.now()`) statt eines exakten Textvergleichs.

## Expected Behavior

- **Input:** `AlertMessage` mit `source` gesetzt (Onset-Zweig) und genau einem führenden
  `OnsetEvent` — Trip-Radar (`source="radar"`, `location_label=None`), Ortsvergleich-Bündel
  mit >1 Ort (`location_label` gesetzt), oder Ortsvergleich mit genau 1 Ort
  (`source=COMPARE_RADAR_SOURCE`, `location_label=None`).
- **Output:** `render_sms()` liefert für den Onset-Zweig einen String der Form
  `{Ortsangabe}: TH@{HH:MM}` bzw. `{Ortsangabe}: R@{HH:MM}` — Ortsangabe je nach obiger
  Fallunterscheidung Segmentname, km-Rückfall, oder Ortsname (Bündel- bzw. Ein-Ort-Compare).
  Kein `+N`-Zähler, keine Countdown-Minuten, keine Piktogramme.
- **Side effects:** keine — reine Renderer-Formatierung; kein Datenmodell-Wandel, keine
  Persistenz betroffen. E-Mail-, Telegram- und Betreff-Rendering des Onset-Zweigs bleiben
  unverändert (nutzen weiterhin `_km_str_onset`).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Onset-Alarm mit einem konvektiven Ereignis (`is_convective=True`,
  `onset_time="15:40"`, ohne `location_label`) / When `render_sms(msg)` über den Onset-Zweig
  gerendert wird / Then enthält der Text exakt das Token `TH@15:40`, jedoch nirgends mehr
  `TH!` oder eine Minutenzahl als Countdown.
  - Test: Unit-Test gegen `_render_sms_onset` mit konstruiertem `OnsetEvent`, Substring-Vergleich
    auf `TH@15:40` und Abwesenheit von `TH!`.

- **AC-2:** Given denselben Aufbau wie AC-1, aber mit `is_convective=False` und
  `onset_time="14:35"` (Regen-Anmarsch statt Gewitter) / When `render_sms(msg)` erneut über
  denselben Onset-Zweig gerendert wird / Then enthält der Text exakt das Token `R@14:35` und
  nirgends mehr `R!` oder eine Minutenzahl als Countdown.
  - Test: Unit-Test, gespiegelt zu AC-1, Substring-Vergleich auf `R@14:35`.

- **AC-3:** Given einen Trip-Onset-Alarm, dessen führendes Ereignis eine Segment-Kennung
  trägt (`segment_id="Ziel"`, kein `location_label`, konvektiv mit `onset_time="15:40"`) /
  When die SMS über den echten Einspeiseweg (S2-Endpunkt) gerendert wird / Then lautet der
  Kopf exakt `Ziel: TH@15:40` — dieselbe Segment-Sprache, die `format_alert_location` Stufe 2
  auch für Betreff und E-Mail liefert, statt der alten `km8-8: TH!8`-Notation.
  - Test: Endpunkt-Test über `POST /api/trips/{trip_id}/alert-preview?user_id=…` mit
    `nowcast_frames`, die einen konvektiven Frame am Segment „Ziel" erzeugen; Antwortfeld
    `sms` auf den exakten Kopf geprüft.

- **AC-4:** Given einen Trip-Onset-Alarm, dessen führendes Ereignis keine verwertbare
  Segment-Kennung trägt (`segment_id=None`, Altdaten-Fall ohne `location_label`) / When
  `render_sms(msg)` über den Onset-Zweig ohne Segment-Kennung gerendert wird / Then fällt der
  Kopf weiterhin auf die km-Spanne zurück (`format_alert_location` Stufe 3, z. B.
  „km 5–18: "), keine Segment-Sprache erscheint an dieser Stelle.
  - Test: Unit-Test gegen `_render_sms_onset` mit `segment_id=None`, Substring-Vergleich auf
    den km-Rückfall.

- **AC-5:** Given einen Ortsvergleich-Bündel-Onset-Alarm mit mehr als einem Ort, bei dem das
  führende Ereignis ein gesetztes `location_label` trägt (z. B. „Zermatt") / When
  `render_sms(msg)` über den gebündelten Ortsvergleich-Onset-Zweig gerendert wird / Then
  beginnt der Kopf exakt mit „Zermatt: ", enthält weder ein `+N`-Suffix noch eine
  `km0-0`-Spanne.
  - Test: Unit-Test über `to_multi_location_onset_alert_message` mit zwei Orts-Gruppen,
    gerendertes `sms` auf Kopf und Abwesenheit von `+` bzw. `km0` geprüft.

- **AC-6:** Given einen Ortsvergleich-Onset-Alarm mit genau einem Ort (Invariante:
  `location_label=None`, `msg.source=COMPARE_RADAR_SOURCE`, Ortsname ausschließlich in
  `msg.trip_short`) / When `render_sms(msg)` über denselben Ein-Ort-Compare-Zweig gerendert
  wird / Then nennt der Kopf den Ortsnamen aus `trip_short` statt der bisherigen
  `km0-0`-Spanne — der heute unmögliche Sonderfall (PO-Entscheid 3a) ist damit geschlossen.
  - Test: Unit-Test über `to_multi_location_onset_alert_message` mit genau einer Gruppe,
    gerendertes `sms` gegen den erwarteten Ortsnamen geprüft (Regressionsnachweis: derselbe
    Aufbau lieferte vor S4 `km0-0: …`).

- **AC-7:** Given eine `AlertMessage`, deren `source`-Feld NICHT der Compare-Radar-Konstante
  entspricht, aber inhaltlich sonst identisch zum Ein-Ort-Compare-Fall aus AC-6 ist
  (`location_label=None`, km_from=km_to=0.0, Ortsname in `trip_short`) / When
  `render_sms(msg)` mit diesem manipulierten `source`-Wert gerendert wird / Then fällt der
  Kopf auf „km 0–0" zurück statt den Ortsnamen zu zeigen — dieser Test beweist, dass die
  Fallunterscheidung tatsächlich an der Konstante hängt, nicht an einer zufälligen
  String-Übereinstimmung, und muss rot schlagen, sobald Setz- und Lesestelle auseinanderdriften.
  - Test: Unit-Test (Wächter), der bewusst einen abweichenden `source`-Wert setzt und den
    km-Rückfall als feste Erwartung prüft — kein Dateiinhalt-Check, echter Renderer-Aufruf.

- **AC-8:** Given einen Trip-Onset-Alarm mit Segment-Kennung „Ziel" (führt über
  `format_alert_location` zu `🏁 Ziel`) / When der Kopf über `_ascii_alert_location`
  gerendert wird / Then enthält der resultierende SMS-Text weder das Zeichen `🏁` noch dessen
  Transliteration `:checkered_flag:` — nur das Wort „Ziel" bleibt stehen, die Ausgabe ist
  GSM-7-rein.
  - Test: Unit-Test, gerenderten String auf Abwesenheit beider verbotener Zeichenketten
    geprüft; Mutations-Kandidat für die Adversary-Runde ist das Vertauschen von
    `_ascii_alert_location` gegen `_ascii`.

- **AC-9:** Given zwei strukturell identische Onset-`AlertMessage`s, die sich nur in
  `location_label`/`source` unterscheiden — eine echter Trip-Radar-Alarm (kein Ortsname),
  eine Ortsvergleich-Bündel-Alarm (Ortsname gesetzt) / When beide über `render_sms`
  gerendert werden / Then trägt NUR das Compare-Ergebnis den Ortsnamen im Kopf, während das
  Trip-Ergebnis weiterhin direkt mit der aufgelösten Ortsangabe ohne Namenspräfix beginnt —
  die Zusicherung ist der Vergleich beider Ergebnisse, keine isolierte Einzelprüfung.
  - Test: Vergleichstest — Fortschreibung von
    `test_alert_sms_segment_head.py::test_ac12_trip_radar_sms_verliert_den_namen_compare_radar_sms_behaelt_ihn`
    auf das neue `TH@`/`R@`-Format, die Differenzlogik zwischen beiden Ergebnissen bleibt
    erhalten.

- **AC-10:** Given der geänderte Onset-Renderpfad in `_render_sms_onset` / When dieselben
  Eingaben zusätzlich über `_render_email_onset`, `_render_telegram_onset` und
  `_render_subject_onset` gerendert werden / Then bleiben deren Ausgaben byte-identisch zum
  Vor-S4-Zustand, weil `_km_str_onset`/`_km_str` von dieser Scheibe nicht angefasst werden und
  `src/app/day_window.py`/`display_end_time()` weiterhin außerhalb der Aufrufkette liegen
  (#1599-Leitplanke).
  - Test: Vergleichstest — bestehende E-Mail-/Telegram-/Betreff-Onset-Regressionstests laufen
    unverändert grün (Verhaltensnachweis); ergänzend ein struktureller Importe-Check, dass
    `render.py` `app.day_window` nicht importiert (kein Verhaltensnachweis, nur Nicht-Berührung).

- **AC-11:** Given einen Onset-Alarm, dessen `onset_time` in eine Vormittagsstunde mit führender
  Null fällt (Feldwert `"09:05"`, wie ihn `strftime("%H:%M")` an allen Setzstellen erzeugt) /
  When derselbe Alarm einmal über `render_sms` und einmal über `_render_email_onset` bzw.
  `_render_telegram_onset` gerendert wird / Then trägt allein die Kurznachricht die Stunde **ohne**
  führende Null (`TH@9:05`, Zeichenbudget), während E-Mail und Telegram die volle Form `09:05`
  behalten — die Minuten bleiben in allen Kanälen zweistellig, und das Feld `onset_time` selbst
  wird nicht verändert, nur seine Darstellung in der Kurznachricht.
  - Test: Vergleichstest über alle drei Renderer mit demselben `OnsetEvent` (`onset_time="09:05"`);
    geprüft wird `TH@9:05` in der SMS **und** `09:05` in E-Mail und Telegram — ein Test, der beide
    Seiten gegeneinander stellt, damit eine Kürzung an der falschen Stelle rot schlägt.
    PO-Entscheid 2026-08-19, `issuecomment-5345456988`.

## Zusätzliche Prüfpunkte (aus der Abhängigkeitsanalyse, Phase 2 Step 2a)

**Bestehender ASCII-Wächter muss grün bleiben.** `tests/tdd/test_ascii_folding.py:101-123` prüft am
gerenderten SMS-Text: `sms.isascii()`, `len(sms) <= 140` und dass **gefaltete Ortsnamen** tatsächlich
erscheinen (`"Hyeres" in sms`, `"Muenchen" in sms`). Das ist kein Goldstring des alten Formats,
sondern der bestehende Wächter für dieselbe Zusicherung wie AC-8 — er wird **nicht angepasst** und
muss den Umbau unverändert überstehen. Wird er rot, ist der Kopf-Umbau falsch verdrahtet.

**Premium-SMS erbt das Format ungeprüft.** `docs/specs/modules/feat_1701_alarm_premium_sms.md`
beschreibt Premium-SMS als vierten Kanal, der denselben `render_sms`-Aufruf mitbenutzt
(`notification_service.py:1373` rendert **einmal**, `:1543` und `:1558` versenden dasselbe Ergebnis).
Vor Abschluss ist zu prüfen, dass `tests/unit/test_premium_sms_versand.py` und
`tests/unit/test_alert_channel_premium_sms.py` keine Onset-Token-Goldstrings festhalten — nach
bisheriger Sichtung prüfen sie nur Versand-Infrastruktur, aber das ist als Prüfpunkt zu bestätigen,
nicht als Annahme zu führen.

**Warum AC-7 nötig ist — belegt.** Kein einziger Test prüft heute den String `"compare-radar"`
direkt; `msg.source` wird an vier Stellen (`render.py:442/622/757/890`) nur auf `is not None`
geprüft. Ein Auseinanderdriften von Setz- und Lesestelle der neuen Konstante würde daher von
**keinem** Bestandstest bemerkt. AC-7 schließt genau diese Lücke.

**Zwei Agenten-Fehlmeldungen, gegengeprüft und verworfen** (damit ihnen niemand nachläuft):
`tests/tdd/test_compare_radar_alert.py` enthält keine relevante Fundstelle. Und
`compare_preview_service.py:111` / `preview_service.py:349` sind **Definitionen** einer eigenen
Methode `render_sms_preview`, keine Aufrufe des Alarm-Renderers — es besteht keine
Preview-Abhängigkeit vom Onset-Pfad.

## Abgelöste Zusicherungen

- **`tests/tdd/test_alert_location_vocabulary.py:573-585`
  (`test_kurznachricht_des_nowcasts_nennt_keinen_ort`)** fordert wörtlich das Gegenteil des
  S4-Zielbilds: `"Segment" not in sms`, `"Ziel" not in sms`, `"🏁" not in sms`, und einen
  verpflichtenden `km\d`-Treffer. Der Docstring selbst benennt die künftige Ablösung
  („der Betreff wechselt auf '🏁 Ziel', die Kurznachricht bleibt bei 'km8-8'" — genau diese
  Trennung entfällt mit S4). Der PO-Entscheid (Analyse-Tabelle, Frage 2) löst den Test
  **bewusst** ab: die Kurznachricht spricht künftig dieselbe Segment-Sprache wie der Betreff.
  Präzedenz: S3 hat für Zweig a `#1744 AC-5` in derselben Weise abgelöst. Der Test wird
  **fortgeschrieben** (Docstring + Assertions auf das neue Verhalten umgestellt), nicht
  gelöscht — er bleibt als Regressionsschutz relevant, gilt aber nach S4 nicht mehr für den
  Onset-/Nowcast-Pfad.
- **`docs/specs/modules/fix_1948_s3_sms_sofortfix.md` AC-7** sichert ausdrücklich zu, dass
  `_render_sms_onset` byte-identisch zum Vor-S3-Zustand bleibt. Diese Zusicherung läuft mit
  S4 **planmäßig aus** — S4 ist genau die Scheibe, die `_render_sms_onset` gezielt ändert.
  AC-7 aus S3 gilt ab dieser Spec als abgelöst, nicht als gebrochen.

## Known Limitations

- **Gewitter-Pfad mit echten Aufzeichnungen nicht verifizierbar.** Von 56 echten
  Zweig-c-Mitschnitten auf Prod (50) und Staging (6) enthält **keiner** einen konvektiven
  Frame (17 mit Regen, 0 mit Gewitter). AC-1/AC-3/AC-8 sind deshalb nur über konstruierte
  bzw. abgeleitete `nowcast_frames`/`OnsetEvent`-Fixtures plus Unit-Tests verifizierbar, nicht
  über einen echten End-to-End-Mitschnitt. Sobald eine echte konvektive Aufzeichnung entsteht,
  gehört ein Nachtrag in eine Folge-Scheibe oder #1199.
- **`format_alert_location` Stufe 1 kappt lange Ortsnamen nicht.** Geerbtes Risiko — der
  Trip-Δ-Pfad (`render.py:916`) trägt dieselbe Lücke. Bei einem 35-Zeichen-Ortsnamen wächst
  die Compare-SMS ungekappt (gemessen: +18 Zeichen gegenüber dem alten, hart auf 16 Zeichen
  gekürzten `trip`-Präfix). Wird in S4 nicht gelöst.
  - **Längen-Budget insgesamt unkritisch** (Limit 140, harter Endschnitt `body[:limit]`):
    Trip mit Segmentnamen +3 Zeichen, Trip-km-Rückfall +4 Zeichen, Compare mit kurzem
    Ortsnamen −4 Zeichen (kürzer als vorher), nur der lange Ortsname wächst nennenswert.
  - **2026-08-23 geschlossen (#2078):** Der harte Endschnitt `body[:limit]` konnte bei
    ausreichend langem Ortsnamen mitten ins Zeit-Token schneiden (`Sa0:40` → `Sa0:4`,
    liest sich wie eine andere echte Uhrzeit). Fix in
    `docs/specs/modules/fix_2078_onset_sms_zeit_token_schnitt.md`: Kopf-Anteil wird jetzt
    VOR dem Zusammenbau auf 24 Zeichen gekappt (analog `_render_sms_corridor_only`), der
    harte Endschnitt bleibt als Sicherheitsnetz bestehen.
- **Kurznachricht wertet weiterhin nur das führende Event aus** — kein `+N`-Zähler, PO-Entscheid
  3b. Bei mehreren gleichzeitig auslösenden Orten verschweigt die Nachricht die übrigen; das
  ist gewollt (ein Zähler würde Vollständigkeit versprechen, die er nicht einlöst), gehört aber
  als bekannte Grenze dokumentiert.
- **AC-10 ist in der Umsetzung geschlossen** — der ursprünglich erwartete Lückenbefund
  („kein eigener dedizierter Test") ist überholt. `tests/tdd/test_alert_sms_onset_zeitpunkt.py`
  enthält jetzt zwei dedizierte AC-10-Tests: `test_ac10_email_telegram_betreff_bleiben_am_countdown_format`
  (Zeile 432, Verhaltensnachweis über Betreff/E-Mail/Telegram am unveränderten Countdown-Format)
  und `test_ac10_render_modul_importiert_day_window_nicht` (Zeile 463, struktureller
  Nicht-Berührungs-Nachweis über `app.day_window`).

## Verifikation

- **Endpunkt-Nachweis (S2-Einspeiseweg):**
  `POST /api/trips/{trip_id}/alert-preview?user_id=…` mit Payload
  `{"nowcast_frames": {source, frames[], km_from, km_to}}` → die Antwort trägt
  `onset_detected` und das gerenderte `sms`-Feld. Der Replay nutzt dasselbe `_derive_result`
  wie der Live-Pfad, keinen Test-Sonderweg — geeignet für AC-1/AC-2/AC-4/AC-10/AC-11 und als
  zusätzlicher Regen-Nachweis mit echten Frame-Daten.
- **Kern-Unit-Tests:** direkte Aufrufe von `_render_sms_onset` mit konstruierten
  `OnsetEvent`/`AlertMessage`-Fixtures für alle zehn ACs, deterministisch, ohne Netz.
- **Grenze:** Für den konvektiven Zweig existiert kein echter S1-Mitschnitt (s. Known
  Limitations) — der Endpunkt-Nachweis nutzt deshalb konstruierte, nicht
  aufgezeichnete `nowcast_frames`.
- 🔴 **Grenze des Endpunkts — korrigiert am 2026-08-20 nach der Staging-Messung:**
  Eine frühere Fassung dieser Sektion behauptete, der Endpunkt sei „geeignet für AC-3
  (Segment-Sprache)". **Das trifft nicht zu.** Der Endpunkt kann **keine Segment-Kennung
  transportieren**: `OnsetPayload` (`api/routers/validator.py:226-234`) hat kein
  Segment-Feld, und der Frame-Replay baut das Onset-Objekt ausschließlich aus
  `km_from`/`km_to` (`src/services/validator_render_service.py:245-254`). Damit fällt der
  Kopf über diesen Weg **immer** auf die km-Spanne zurück — unabhängig vom Trip.
  Auf Staging messbar sind deshalb nur AC-1, AC-2, AC-4, AC-10 und AC-11; **AC-3 und AC-8
  ruhen allein auf Kern-Unit-Tests**, AC-5 bis AC-9 zusätzlich mangels
  Compare-seitigem Einspeiseweg.

  **Es ist ein Versehen aus S2, keine Designentscheidung:** der Geschwister-Zweig
  `OfficialAlertPayload` (ebenda, Z. 237-251) trägt sehr wohl `segment_ids: list[str]`,
  und die Produktivseite kann es ohnehin — `OnsetEvent.segment_id` existiert seit #1744 A1
  und wird vom Live-Pfad gesetzt (`src/services/trip_alert.py:1283`). Es fehlt allein die
  Durchreichung im Testeinspeiseweg (~10 Zeilen). **Als Vorbedingung für S5 vorgemerkt**,
  damit Segment-Sprache in künftigen Alarm-Scheiben am lebenden System prüfbar wird.

## Nicht Teil dieser Scheibe

- **Zweig b (amtliche Warnungen, `official_alerts.py`)** — eigene Scheibe S5.
- **Telegram-Parität** (`_render_telegram_onset` bleibt unverändert, nutzt weiterhin
  `_km_str_onset`) — eigene Scheibe S6.
- Die führende-Null-Frage im Stunden-Suffix (aus S3 offen gelassen) — betrifft den Trip-Δ-Pfad,
  nicht den Onset-Pfad dieser Scheibe, weiterhin nicht vorentschieden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Renderer-Formatänderung plus eine additive Konstanten-Härtung
  innerhalb eines bereits PO-freigegebenen Konzepts (`docs/analysis/alarm-format-konzept-2026-08.md`).
  Kein neues Datenmodell, keine neue Architekturentscheidungsfläche (kein neuer Kanal, kein
  neuer Provider, keine Persistenz-Änderung).

## Changelog

- 2026-08-19: Initial spec created (S4 des Alarm-Format-Konzepts #1948, Zweig c
  Nowcast/Onset-SMS-Zielbild).
