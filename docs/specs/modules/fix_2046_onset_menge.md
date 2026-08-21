---
entity_id: fix_2046_onset_menge
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [alarm, sms, nowcast, radar, format]
---

# Radar-Onset-Kurznachricht bekommt eine Mengenangabe — #2046

## Approval

- [x] Approved — PO Henning, 2026-08-21 ('go' auf alle 12 Akzeptanzkriterien)

## Purpose

Der Radar-Onset-Alarm (Zweig c: Gewitter-/Regen-Anmarsch) ist heute der einzige
Alarmzweig, dessen Kurzform (`Ziel: R@18:00`) keinerlei Wert nennt — nur Kürzel und
Uhrzeit. Diese Spec ergänzt eine Mengenangabe, gemessen über die 60 Minuten **ab dem
Beginn** (nicht ab „jetzt"), und reicht sie additiv durch alle Wirkketten (Trip-Pfad,
Ortsvergleich-Bündel, Vorschau-/Testeinspeiseweg) bis in `_render_sms_onset`.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_render_sms_onset()` (Z. 553-581)

Begleitend: `src/services/radar_service.py` (`_derive_result`, Z. 636-779;
`NowcastResult`, Z. 129-172), `src/services/trip_alert.py` (`check_radar_alerts`,
Z. 1330-1479), `src/services/notification_service.py` (`RadarAlertRequest` Z. 165-194,
`send_radar_alert` Z. 1272-1314), `src/output/renderers/alert/model.py` (`OnsetEvent`
Z. 38-62), `src/output/renderers/alert/project.py`
(`to_multi_location_onset_alert_message`, Z. 397-405), `src/services/
validator_render_service.py` (`render_alert_preview` Z. 108-121, `_render_nowcast_replay`
Z. 220-261), `api/routers/validator.py` (`OnsetPayload`, Z. 226-239).

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Core
> (`src/services/`, `src/output/`, `api/routers/`) — kein Go-API-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~90–130 (additives Feld über sechs Dateien + Rechenlogik in
  `_derive_result` + Token-Zusammenbau in `_render_sms_onset`, unter dem
  250-LoC-Workflow-Limit)
- **Files:** 6 Produktivdateien (`radar_service.py`, `model.py`, `trip_alert.py`,
  `notification_service.py`, `project.py`, `render.py`, `validator_render_service.py`,
  `api/routers/validator.py` — de facto 8, aber mehrere nur Ein-Zeiler) + 8
  Bestandstestdateien fortgeschrieben + mind. 1 neues Testmodul (TDD-RED)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NowcastResult.window_precip_mm` | field (`radar_service.py:157-160`) | Bestehendes Mengenfeld, misst 60 Min **ab jetzt** — bleibt für die #2020-Auslöseregel unangetastet, ist NICHT die neue Anzeige-Zahl |
| `_derive_result` | method (`radar_service.py:636-779`) | Ort der neuen Rechnung; besitzt bereits die komplette Akkumulationsmechanik (Frame-Dedup Z. 739-743, Deckelung `_MAX_FRAME_COVERAGE` Z. 752, Fensterende als harte Grenze Z. 752) — wird für das neue Fenster wiederverwendet, nicht neu erfunden |
| `RADAR_ONSET_THRESHOLD_MIN` | constant (`radar_service.py:113`, Wert 55) | Erklärt die Lücke: Alarm feuert bis 55 Min vor Beginn, `window_precip_mm`-Fenster deckt aber nur die ersten 60 Min ab jetzt — bei spätem Beginn fast nur Trockenzeit |
| `OnsetEvent` | dataclass (`model.py:38-62`) | Trägt heute `intensity_label` (Text), kein numerisches Feld — bekommt additiv-optionales `onset_precip_mm` |
| `RadarAlertRequest` | DTO (`notification_service.py:165-194`) | Trip-Pfad-Transport; bekommt additiv-optionales `onset_precip_mm` |
| `_fmt_num` / `LEVELS` | function/dict (`src/output/tokens/metrics.py:14,17-19`) | Referenz-Zahlformat (`R{value:.1f}`) und Stufen-Grammatik (`TH:` reserviert Position für L/M/H) — Begründung für die getrennte Stellung bei Gewitter |
| `to_multi_location_onset_alert_message` | function (`project.py:319-410`) | Ortsvergleich-Bündelpfad, baut `OnsetEvent` direkt aus `NowcastResult` — zweiter Leser der neuen Zahl |
| `render_alert_preview` / `_render_nowcast_replay` | function (`validator_render_service.py:71-159,220-261`) | Vorschau-/Testeinspeiseweg; `_render_nowcast_replay` ruft `_derive_result` direkt und rekursiv `render_alert_preview` — beide Stellen müssen die Zahl durchreichen |
| `OnsetPayload` | Pydantic-Model (`api/routers/validator.py:226-239`) | API-Payload-Schema für den direkten Vorschauweg (nicht Replay) — bekommt additiv-optionales Feld, Muster `segment_id` |

## Implementation Details

**1. Neues Feld auf `NowcastResult` (`radar_service.py`, nahe `window_precip_mm`,
Z. 157-160):**

```python
onset_precip_mm: Optional[float] = None
# Issue #2046: akkumulierte Menge der 60 Minuten AB `onset_minutes` (nicht ab
# jetzt wie window_precip_mm) -- Grundlage der SMS-Mengenangabe. None wenn
# onset_minutes None ist ODER im Fenster ab dem Beginn keine Frames liegen.
# Eigenes Fenster, dieselbe Akkumulationsmechanik wie window_precip_mm
# (Frame-Dedup, _MAX_FRAME_COVERAGE-Deckel, Fensterende als harte Grenze).
```

**2. Rechnung in `_derive_result`** (`radar_service.py`, nach der bestehenden
`window_precip_mm`-Schleife, Z. 745-754): dieselbe Struktur wie die
`compare_window`/`compare_window_by_ts`-Berechnung (Z. 719-754), aber mit
`onset_horizon = onset_time_dt + timedelta(minutes=60)` als Fensterende und
`onset_time_dt` (aus `onset_minutes`, das bereits oben berechnet wird) als
Fensterstart statt `now`. Nur wenn `onset_minutes is not None`; sonst bleibt
`onset_precip_mm = None`. Kein zweiter Frame-Abruf — dieselbe `frames`-Liste, die
auch `window_precip_mm` speist (AC-12).

**3. Additive Felder auf `OnsetEvent`** (`model.py`, Muster `onset_day_offset`
#2009, Z. 56-62): `onset_precip_mm: float | None = None`.

**4. Durchreichung entlang der Wirkkette** (alle additiv, Default `None`,
Muster `segment_id`/`onset_day_offset`):

- `RadarAlertRequest` (`notification_service.py:165-194`) — neues Feld.
- `trip_alert.py:1330-1479` (`check_radar_alerts`) — `result.onset_precip_mm` aus
  dem `NowcastResult` in den `RadarAlertRequest`-Konstruktoraufruf übernehmen
  (analog `is_convective=result.is_convective`).
- `notification_service.py:1272-1314` (`send_radar_alert`) —
  `onset_precip_mm=request.onset_precip_mm` in den `OnsetEvent`-Konstruktoraufruf.
- `project.py:397-405` (`to_multi_location_onset_alert_message`) —
  `onset_precip_mm=nc.onset_precip_mm` in den `OnsetEvent`-Konstruktoraufruf (`nc`
  ist das `NowcastResult` je Ort).
- `validator_render_service.py:108-121` (`render_alert_preview`, has_onset-Zweig) —
  `onset_precip_mm=getattr(body.onset, "onset_precip_mm", None)`, Muster
  `segment_id` Z. 118-120.
- `validator_render_service.py:220-261` (`_render_nowcast_replay`) —
  `onset_precip_mm=result.onset_precip_mm` in den `onset_ns`-`SimpleNamespace`
  (Z. 246-256).
- `api/routers/validator.py:226-239` (`OnsetPayload`) —
  `onset_precip_mm: float | None = None`.

**5. Token-Zusammenbau in `_render_sms_onset`** (`render.py:553-581`):

```python
kuerzel = "TH" if e.is_convective else "R"
menge = _fmt_num("R", e.onset_precip_mm) if e.onset_precip_mm is not None else None
zeit = f"@{_sms_onset_time(e.onset_time, e.onset_day_offset)}"
if kuerzel == "TH":
    token = f"TH{zeit}" + (f" R{menge}" if menge is not None else "")
else:
    token = f"{kuerzel}{f'{menge}' if menge is not None else ''}{zeit}"
```

`_fmt_num` importiert aus `output.tokens.metrics` (bereits Briefing-Referenz für
die Zahlform, eine Nachkommastelle). Kopf-Fallunterscheidung (`location_label`
vs. `COMPARE_RADAR_SOURCE` vs. Trip-km-Rückfall) bleibt unverändert — diese Spec
ändert nur den Token-Teil hinter dem Doppelpunkt.

**Ausweichform (AC-4):** `onset_precip_mm is None` **oder** kleiner als eine
belastbare Untergrenze in Größenordnung von `_DRY_THRESHOLD_MM_H` (0,1 mm/h über
60 Min ≈ 0,1 mm) führt zur heutigen Form ohne Zahl — dieselbe Schwelle, die
bereits `_derive_result` für „trocken" verwendet (Z. 655, `_DRY_THRESHOLD_MM_H`).
`onset_precip_mm == 0.0` wird dabei wie `None` behandelt: die Anzeige unterscheidet
nicht zwischen „nicht berechenbar" und „berechnet, aber null" — beides ergibt die
zahlenlose Form, damit niemals `R0.0@` entsteht.

## Expected Behavior

- **Input:** `NowcastResult` mit gesetztem `onset_minutes` und Frames, die bis
  mindestens in die erste Minute nach dem Beginn reichen.
- **Output:** `render_sms()` liefert für den Onset-Zweig `{Kopf}: R{menge}@{HH:MM}`
  (Regen) bzw. `{Kopf}: TH@{HH:MM} R{menge}` (Gewitter), `menge` mit einer
  Nachkommastelle; ohne belastbare Zahl unverändert `{Kopf}: R@{HH:MM}` bzw.
  `{Kopf}: TH@{HH:MM}`.
- **Side effects:** keine — reine additive Feld-Durchreichung plus
  Renderer-Formatierung. Kein Datenmodell-Bruch (alle neuen Felder optional mit
  Default `None`), keine Persistenz betroffen. E-Mail- und Telegram-Langform-
  Rendering bleiben unverändert (nutzen weiterhin `intensity_label` als Wort,
  lesen `onset_precip_mm` nicht).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Onset-Alarm mit einem nicht-konvektiven Ereignis
  (`is_convective=False`, `onset_time="18:00"`, `onset_precip_mm=2.5`) / When
  `render_sms(msg)` über den Onset-Zweig gerendert wird / Then enthält der Text
  exakt das Token `R2.5@18:00` — Kürzel, Zahl mit einer Nachkommastelle und
  Uhrzeit ohne Trennzeichen dazwischen.
  - Test: Unit-Test gegen `_render_sms_onset` mit konstruiertem `OnsetEvent`,
    Substring-Vergleich auf `R2.5@18:00`.

- **AC-2:** Given denselben Aufbau wie AC-1, aber konvektiv
  (`is_convective=True`, `onset_time="18:00"`, `onset_precip_mm=2.5`) / When
  `render_sms(msg)` über denselben Onset-Zweig gerendert wird / Then enthält der
  Text exakt `TH@18:00 R2.5` — die Zahl steht als eigenes Token NACH dem
  Zeit-Token, getrennt durch ein Leerzeichen, und hinter `TH` selbst steht
  niemals eine Ziffer (Stufen-Position bleibt frei für L/M/H).
  - Test: Unit-Test, gespiegelt zu AC-1, prüft sowohl das Vorhandensein von
    `TH@18:00 R2.5` als auch die Abwesenheit von `TH2` bzw. `TH2.5`.

- **AC-3:** Given ein `NowcastResult`, dessen `onset_minutes=50` ist (Beginn in
  50 Minuten, unter der 55-Minuten-Auslöseschwelle) und dessen Frames VOR dem
  Beginn durchgängig trocken sind (0 mm/h), AB dem Beginn aber 12 mm/h liefern /
  When `_derive_result` sowohl `window_precip_mm` (60 Min ab jetzt) als auch
  `onset_precip_mm` (60 Min ab Beginn) berechnet / Then weist `window_precip_mm`
  nur rund 2 mm aus (10 trockene Minuten + 50 Minuten bei 12 mm/h, aber vom
  60-Minuten-Fenster ab jetzt nur die letzten 10 Minuten mit Regen erfasst,
  exakter Wert von der Frame-Kadenz abhängig, GRÖSSENORDNUNG deutlich unter 12
  mm), während `onset_precip_mm` rund 12 mm ausweist (volle Stunde ab Beginn bei
  12 mm/h) — die neue Zahl entwertet den Alarm nicht durch Untertreibung, weil
  sie am Beginn ausgerichtet ist, nicht an „jetzt".
  - Test: Unit-Test gegen `_derive_result` mit konstruierten Frames (Kadenz z. B.
    5-Minuten-Raster, Regen erst ab Minute 50), Vergleich beider Feldwerte
    gegeneinander — Wächter, der rot schlägt, sollte `onset_precip_mm`
    versehentlich wieder ab „jetzt" statt ab dem Beginn gerechnet werden.

- **AC-4:** Given ein `OnsetEvent` ohne belastbare Zahl — drei Varianten:
  (a) `onset_precip_mm=None` (keine Frames im Fenster ab Beginn), (b)
  `onset_precip_mm=0.0` (Menge unterhalb der Trockenschwelle), (c) ein
  `NowcastResult` mit `data_unavailable=True` bzw. `throttled=True` / When
  `render_sms(msg)` in allen drei Fällen gerendert wird / Then bleibt die
  heutige Form ohne Zahl (`R@18:00` bzw. `TH@18:00`) erhalten — in keinem Fall
  entsteht `R0.0@18:00`.
  - Test: Drei Unit-Tests (a/b/c) gegen `_render_sms_onset`, jeweils Abwesenheit
    jeder Ziffernfolge unmittelbar hinter `R` bzw. `TH` geprüft.

- **AC-5:** Given `onset_precip_mm=2.0` (glatte Zahl ohne Nachkommaanteil) und
  `onset_precip_mm=12.34` (zwei Nachkommastellen) / When beide über
  `render_sms(msg)` gerendert werden / Then erscheint die Zahl in beiden Fällen
  mit genau einer Nachkommastelle und Punkt als Trennzeichen (`R2.0@…`,
  `R12.3@…`), niemals mit Einheit („mm") im Text — identisch zur
  Briefing-Zahlform aus `output.tokens.metrics._fmt_num`.
  - Test: Unit-Test, zwei Eingaben, Regex-Vergleich auf `R\d+\.\d@` und
    Abwesenheit von `mm` im Token-Teil.

- **AC-6:** Given einen Ortsvergleich-Bündel-Onset-Alarm mit zwei Orten, bei dem
  das führende Ereignis `onset_precip_mm=1.8` trägt / When
  `to_multi_location_onset_alert_message` das Ergebnis baut und `render_sms(msg)`
  darauf gerendert wird / Then enthält der Text `R1.8@…` — dieselbe Zahl und
  Formatregel wie im Trip-Pfad (AC-1), nicht bloß eine leere Kurzform mit
  Ortsnamen.
  - Test: Unit-Test über `to_multi_location_onset_alert_message` mit zwei
    Orts-`NowcastResult`s (führender Ort mit gesetzter Menge), gerendertes `sms`
    auf die Zahl geprüft.

- **AC-7:** Given dieselben Onset-Ereignisse für SMS, Premium-SMS und Telegram im
  Kurzstil / When `send_radar_alert(...)` alle drei konfigurierten Kanäle
  bedient / Then zeigen alle drei Kanäle denselben Token-Text inklusive Menge,
  weil sie denselben gerenderten `sms_body` erhalten
  (`notification_service.py:1461-1476`) — kein Kanal zeigt eine andere Zahl oder
  lässt sie aus.
  - Test: Vergleichstest — ein `_dispatch_alert_message`-Aufruf mit allen drei
    Kanälen aktiv, `sent`-Payloads von SMS/Premium-SMS/Telegram-Kurzstil auf
    identischen Text geprüft.

- **AC-8:** Given denselben Onset-Alarm, einmal über `render_sms` und einmal über
  `_render_email_onset` bzw. `_render_telegram_onset` (Langform) gerendert /
  Then bleiben E-Mail- und Telegram-Langform-Ausgabe bit-identisch zum
  Vor-#2046-Zustand — sie zeigen weiter `intensity_label` als Wort, `
  onset_precip_mm` hat dort keinen Leser.
  - Test: Vergleichstest — bestehende E-Mail-/Telegram-Langform-Regressionstests
    laufen unverändert grün; ergänzend ein struktureller Test, dass
    `_render_email_onset`/`_render_telegram_onset` `onset_precip_mm` nicht
    referenzieren (Grep-Nicht-Berührungs-Nachweis, kein Verhaltensersatz).

- **AC-9:** Given ein Onset-Alarm mit langem Ortsnamen UND `onset_precip_mm=99.9`
  (Extremfall, maximale Zeichenlänge der Zahl) / When `render_sms(msg, limit=140)`
  gerendert wird / Then bleibt der resultierende Text unter 140 Zeichen ohne dass
  der harte Schnitt `body[:limit]` (`render.py:580-581`) im Normalfall greift —
  die zusätzliche Zahl (max. 5 Zeichen: `99.9` plus Trennzeichen) verbraucht
  Zeichenbudget, reißt es aber bei realistischen Ortsnamen nicht.
  - Test: Unit-Test mit einem 30-Zeichen-Ortsnamen und `onset_precip_mm=99.9`,
    `len(sms) <= 140` geprüft; kein Goldstring-Vergleich, reine Längenprüfung.

- **AC-10:** Given der direkte Vorschau-Payload (`OnsetPayload` mit
  `onset_precip_mm=3.1`) UND der Replay-Payload (`nowcast_frames`, aus dem
  `_derive_result` intern `onset_precip_mm` berechnet) / When beide über
  `POST /api/trips/{trip_id}/alert-preview` gerendert werden / Then trägt das
  Antwortfeld `sms` in beiden Fällen dieselbe Zahl-Grammatik — der
  Testeinspeiseweg erzeugt dieselbe Ausgabe wie der Produktivpfad, keine der
  beiden Payload-Varianten verliert die Zahl auf dem Weg zum Renderer.
  - Test: Zwei Endpunkt-Tests (direkter `onset`-Payload, `nowcast_frames`-Replay)
    gegen `POST /api/trips/{trip_id}/alert-preview?user_id=…`, `sms`-Feld auf
    Vorhandensein der erwarteten Zahl geprüft.

- **AC-11:** Given bestehende Aufrufer von `RadarAlertRequest`, `OnsetEvent` und
  `OnsetPayload`, die das neue Feld `onset_precip_mm` nicht setzen (Default
  `None`) / When dieselben Eingaben wie vor #2046 über den kompletten Pfad bis
  `render_sms` laufen / Then ist die Ausgabe bit-identisch zum Vor-#2046-Zustand
  — additives Feld mit Default, keine Pflichtangabe, kein Bruch für Alt-Aufrufer.
  - Test: Regressionslauf der acht in „Test-Plan" gelisteten Bestandstestdateien
    ohne inhaltliche Anpassung an ihren Fixtures (nur Format-Anpassung, wo der
    Goldstring selbst betroffen ist, s. Test-Plan) — kein Bestandstest darf
    wegen des neuen Feldes allein rot werden.

- **AC-12:** Given die Frame-Liste, aus der `_derive_result` sowohl
  `onset_minutes` als auch `window_precip_mm` ableitet / When `onset_precip_mm`
  berechnet wird / Then verwendet die Rechnung DIESELBE Frame-Liste (kein
  zweiter Provider-Abruf, kein zweiter `RadarNowcastService`-Aufruf) und
  verändert weder `onset_minutes` noch `window_precip_mm` noch `max_rate_mm_h`
  noch die #2020-Auslöseregel (`radar_alert_due`, `trip_alert.py:1382-1383`
  bleibt unverändert).
  - Test: Unit-Test, der `_derive_result` einmal aufruft und alle vier Felder
    (`onset_minutes`, `window_precip_mm`, `max_rate_mm_h`, `onset_precip_mm`)
    aus demselben Ergebnisobjekt prüft — kein zweiter Mock-Abruf im Test
    selbst, der einen zweiten Produktiv-Abruf verschleiern würde.

## Known Limitations

- **Frame-Abdeckung reicht nicht immer bis `onset_time + 60 min`.** Deckt die
  verfügbare Quelle das volle Stunden-Fenster ab dem Beginn nicht ab (Datenausfall,
  Provider-Grenze), wird über die tatsächlich vorhandenen Frames gerechnet — die
  Menge fällt dann eher zu klein als zu groß aus. Das ist bewusst konservativ,
  dieselbe Richtung wie die bestehende `window_precip_mm`-Deckelung
  (`radar_service.py:700-707`, `_MAX_FRAME_COVERAGE`).
- **Kein zweiter Regel-Leser.** `onset_precip_mm` ist wie `max_rate_mm_h`
  (seit #2020) rein beschreibend/anzeigend — es fließt NICHT in
  `radar_alert_due()` oder die Überholungsprüfung (`trip_alert.py:1382-1383`)
  ein. Eine künftige Verknüpfung wäre eine eigene, separat zu spezifizierende
  Entscheidung.
- **Extremfall doppelte Zahl bei sehr langem Ortsnamen** bleibt ungelöst
  (geerbtes Risiko aus #1948 S4, `format_alert_location` Stufe 1 kappt lange
  Ortsnamen nicht) — durch AC-9 nur für den Normalfall abgesichert, der harte
  Schnitt `body[:limit]` bleibt die letzte Verteidigungslinie.

## Nicht-Ziele

- **Keine Änderung an der Auslöseschwelle** (`RADAR_ONSET_THRESHOLD_MIN = 55`)
  oder an der #2020-Überholungsprüfung — diese Spec ändert ausschließlich die
  Anzeige, nicht die Entscheidung, ob ein Alarm gesendet wird.
- **Keine Änderung an E-Mail- oder Telegram-Langform** — beide bleiben bei
  `intensity_label` als Wort.
- **Keine neue Datenquelle, kein zweiter Provider-Abruf** — die neue Zahl
  entsteht ausschließlich aus den Frames, die `_derive_result` ohnehin schon
  erhält.
- **Kein Umbau des Ortskopfs** derselben Zeile — das ist der Gegenstand des
  parallelen, noch nicht gemergten #2036 (`fix_2036_alarm_kilometer_
  ortsangabe.md`). Beide Änderungen betreffen unterschiedliche Teilstrings
  derselben Zeile (Kopf vor dem Doppelpunkt vs. Token danach) und werden per
  Rebase zusammengeführt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Feld-Durchreichung entlang einer bestehenden
  Wirkkette plus eine reine Renderer-Formaterweiterung. Kein neues
  Datenmodell-Konzept (das additive-optionale-Feld-Muster ist bereits über
  `location_label`/`segment_id`/`onset_day_offset` etabliert), keine neue
  Architekturentscheidungsfläche (kein neuer Kanal, kein neuer Provider,
  keine Persistenz-Änderung, keine Änderung an der Auslöseregel).

## Test-Plan

**Bestehende Tests, die den heutigen zahlenlosen Token festnageln — laufen
unverändert grün oder werden am Goldstring fortgeschrieben:**

- `tests/tdd/test_alert_sms_onset_zeitpunkt.py` — Goldstrings ohne Menge bleiben
  gültig, solange die Fixtures `onset_precip_mm` nicht setzen (AC-11); wo
  Fixtures künftig eine Menge tragen sollen, Ergänzung um neue Testfälle statt
  Änderung bestehender.
- `tests/tdd/test_alert_onset_day_rollover.py` — Tagesüberlauf-Suffix bleibt
  unberührt vom Mengen-Token, reiner Regressionsnachweis.
- `tests/tdd/test_alert_preview_nowcast_replay.py` — Replay-Pfad, Kandidat für
  AC-10 (Endpunkt-Nachweis), muss `onset_precip_mm` aus `_derive_result`
  durchreichen.
- `tests/tdd/test_952_onset_alert_fidelity.py` — Datenblock-Zeile (E-Mail),
  Regressionsnachweis für AC-8.
- `tests/tdd/test_alert_sms_location_positions.py` — Kopf-Positionen, muss mit
  dem neuen Token-Teil nach dem Doppelpunkt kompatibel bleiben.
- `tests/tdd/test_alert_addendum_sms.py` — Nachtrags-Zeile, Regressionsnachweis
  gegen ungewollte Kollision mit dem Mengen-Token.
- `tests/tdd/test_issue_919_radar_alert_canonical.py` — kanonischer
  Radar-Alarm-Pfad, Regressionsnachweis für AC-11.
- `tests/tdd/test_multi_location_onset_alert.py` — Ortsvergleich-Bündelpfad,
  Kandidat für AC-6.

**Neue Testdateien, benannt nach Verhalten (nicht nach Issue-Nummer):**

- `tests/tdd/test_onset_kurzform_menge.py` — AC-1/AC-2/AC-4/AC-5 (Regen- und
  Gewitter-Token mit/ohne Menge, Zahlformat).
- `tests/tdd/test_onset_menge_ab_beginn_nicht_ab_jetzt.py` — AC-3 (Messgrundlage,
  durchgerechnetes Gegenbeispiel), AC-12 (ein Aufruf, vier Felder).
- `tests/tdd/test_onset_menge_kanalparitaet.py` — AC-7 (SMS/Premium-SMS/Telegram
  identisch), AC-9 (Zeichenlimit mit langem Ortsnamen + Extremwert).

## Changelog

- 2026-08-21: Initial spec created (#2046, Radar-Onset-Kurznachricht mit
  Mengenangabe).
