---
entity_id: fix_2096_tagesbezug_testwaechter
type: module
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [tests, ci, tagesbezug, alarm]
---

# Fix #2096 — Tagesbezug-Testwächter (CI-Ampel abends rot)

## Approval

- [x] Approved — PO-Freigabe 2026-08-23

## Purpose

Acht CI-Tests hängen an der Wanduhr und werden ab ~21:05 UTC rot, obwohl der ausgelieferte
Alarmtext korrekt ist: Fällt eine Uhrzeitangabe (Quellen-Reichweite, Ereignis-Ende, Onset) auf den
Folgetag, stellt der Renderer korrekt einen Tagesbezug voran (`morgen 00:12` statt `00:12`,
Kurzform-Wochentagskürzel `So1:35`), aber die Test-Anker greifen per nackter `HH:MM`-Regex und
treffen dann nicht mehr. Diese Spec liefert einen geteilten Test-Helfer, der den Tagesbezug
erstmals **bewacht** statt umgeht, stellt die Uhr in den betroffenen Tests fest statt sie laufen zu
lassen, und ergänzt je Mechanismus einen eigenen Spätuhr-Testfall, der den Tagesübergang tatsächlich
durchläuft. Kein Produktivcode wird geändert.

## Source

- **File:** `tests/tdd/test_onset_reichweite_guete_kanalparitaet.py`,
  `tests/tdd/test_onset_ende_kanalparitaet.py`, `tests/tdd/test_alert_preview_nowcast_replay.py`,
  `tests/tdd/test_onset_ende_textstellen.py`, `tests/tdd/test_952_onset_alert_fidelity.py` (alle
  MODIFY) sowie ein neuer Helfer unter `tests/helpers/` (CREATE)
- **Identifier:** neue Funktion `extract_day_and_time(...)` (Text → `(Tagesbezug, "HH:MM")`) und
  Gegenstück `expected_day_and_time(...)` (Ziel-UTC + Jetzt-UTC + Trip-Zone →
  `(Tagesbezug, "HH:MM")`), Ort: neue Datei in `tests/helpers/`

## Estimated Scope

- **LoC:** ~+220 / -70 — nah am 250er-Limit, `workflow.py set-field loc_limit_override 500`
  vermutlich nötig
- **Files:** 5 Testdateien MODIFY + 1 Helfer CREATE (plus 1–2 latente Zwillinge MODIFY, nur falls
  der Helfer sie ohnehin abdeckt)
- **Effort:** medium

### Affected Files

| File | Change Type | Schicht | Description |
|------|-------------|---------|-------------|
| `tests/helpers/<neuer Helfer>.py` | CREATE | Test-Infrastruktur | `extract_day_and_time()` + `expected_day_and_time()` für Lang- und Kurzform |
| `tests/tdd/test_onset_reichweite_guete_kanalparitaet.py` | MODIFY | Test | Anker auf Helfer umgestellt, Uhr per `frozen_active_window()` gestellt, Spätuhr-Fall für Quellen-Reichweite (Mechanismus A) |
| `tests/tdd/test_onset_ende_kanalparitaet.py` | MODIFY | Test | Anker auf Helfer umgestellt, Uhr gestellt, Spätuhr-Fall für Ereignis-Ende (Mechanismus A) |
| `tests/tdd/test_alert_preview_nowcast_replay.py` | MODIFY | Test | Anker auf Helfer umgestellt, Uhr gestellt, Spätuhr-Fall für den Replay-Weg (Mechanismus A) |
| `tests/tdd/test_onset_ende_textstellen.py` | MODIFY | Test | `_LANGFORM_RE`-Anker auf Helfer umgestellt, Uhr gestellt, Spätuhr-Fall (Mechanismus A) |
| `tests/tdd/test_952_onset_alert_fidelity.py` | MODIFY | Test | `_trip_with_active_segment()` leitet das Fixture-Datum aus der Ortszeit statt `date_type.today()` ab (Mechanismus B); Spätuhr-Regressionsfall |
| `tests/tdd/test_starkregen_kurzfristhinweis.py` | MODIFY (falls günstig) | Test | Uhr per `frozen_active_window()` gestellt, damit der Mitternachtsgrenze-Skip entfällt (Mechanismus C) |

`src/output/renderers/alert/render.py` (`_time_with_day()`) und
`src/output/renderers/alert/project.py` (`source_reach_day_offset`) sind **nicht** Bestandteil
dieses Scopes — sie erscheinen unten in AC-13/AC-14 ausschließlich als temporäre
Mutations-Gegenprobe (String-Ersetzung mit externer Sicherungskopie, danach vollständig
zurückgesetzt), nicht als Änderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frozen_active_window(hour_utc=...)` (`tests/helpers/nowcast_gate_fixtures.py:438-473`) | test helper | Stellt die Systemuhr per `freezegun`, damit Fälle nahe der Mitternachtsgrenze deterministisch werden |
| `trip_local_today()` (`src/services/trip_day.py:90-96`, ADR-0044) | Produktivfunktion | Referenz für „heute" in Ortszeit — Vorbild für die Herleitung in `expected_day_and_time()` |
| `_time_with_day()` (`src/output/renderers/alert/render.py:214-240`) | Produktivfunktion | Erzeugt den Tagesbezug in der Langform — Zielverhalten, das der Helfer nachvollzieht, nicht ändert |
| `source_reach_day_offset` (`src/output/renderers/alert/project.py`) | Produktivfeld | Bisher ungetesteter Zweig, den dieser Zuschnitt erstmals bewacht |
| Spec `feat_2051_s3_reichweite_und_guete.md` | vorausgehende Spec | Definiert `source_reach_day_offset`, dessen Lücke hier geschlossen wird |

## Implementation Details

Vier Bausteine, die nur zusammen wirken:

1. **Geteilter Test-Helfer statt nackter `HH:MM`-Regexe.** Neue Datei unter `tests/helpers/` mit
   zwei Funktionen:
   - `extract_day_and_time(text, style="langform"|"kurzform")` zieht aus dem gerenderten Text ein
     Paar `(Tagesbezug, "HH:MM")`. Langform erkennt `morgen`/`heute`/`gestern`/`in N Tagen` vor der
     Uhrzeit (fehlt das Wort, ist der Tagesbezug `None`). Kurzform erkennt das
     Wochentagskürzel-Präfix im Güte-Zeichen-Token (`So1:35` → `("So", "1:35")`; `23:25?` ohne
     Kürzel → `(None, "23:25")`).
   - `expected_day_and_time(target_utc, now_utc, trip_timezone)` bildet das **erwartete** Paar aus
     dem Datumsvergleich zwischen `target_utc` und `now_utc`, beide auf die Trip-Zeitzone
     projiziert: gleicher lokaler Kalendertag → `None`, ein Tag später → `"morgen"`, ein Tag früher
     → `"gestern"`. Der erwartete Wert wird **hergeleitet**, nie als Literal im Testaufbau
     hinterlegt (vgl. `reference_test_setzt_das_abgeleitete_als_literal`).
2. **Uhr stellen statt Wanduhr.** In den fünf betroffenen Dateien `frozen_active_window()`
   einsetzen, damit die bestehenden (bislang wanduhr-abhängigen) Fälle deterministisch werden.
3. **Eigener Spätuhr-Testfall je Mechanismus.** Punkt 2 friert den Tagesübergangs-Zweig sonst weg
   und Punkt 1 bewachte allein nichts Neues — jeder Anker (Quellen-Reichweite, Ereignis-Ende in
   zwei Dateien, Onset/Replay) braucht mindestens einen Fall mit gestellter Uhr kurz vor
   Mitternacht, der den Überlauf-Zweig tatsächlich durchläuft und Tagesbezug **und** Uhrzeit prüft.
4. **Fixture-Datum aus der Ortszeit ableiten.** In `test_952_onset_alert_fidelity.py:172`
   (`_trip_with_active_segment`) das Etappendatum aus derselben Ortszeit-Logik ableiten, die
   `_active_window` (`:125-148`) bereits für die Fensterberechnung verwendet, statt aus
   `date_type.today()` (Systemdatum).

**Ausdrücklich verworfen:** eine bloße Regex-Aufweichung (`(?:morgen )?`). Sie macht die Ampel
grün, lässt den Tagesbezug aber ungeprüft — das Muster „Test prüft die Form statt des Werts", das
in dieser Scheibe bereits viermal zugeschlagen hat.

## Expected Behavior

- **Input:** Gerenderte Alarmtexte (Langform und Telegram-Kurzstil) aus Trip- und
  Ortsvergleichs-Pfad, jeweils mit und ohne Tagesübergang; eine gestellte Systemuhr zu
  verschiedenen Tageszeiten (u. a. 12:00, 21:06, 22:50, 23:58 UTC).
- **Output:** Alle betroffenen Testdateien laufen zu jeder Tageszeit grün, ohne stillen Skip. Wird
  der `day_offset == 1`-Zweig im Renderer oder `source_reach_day_offset` im Projektionscode
  verfälscht, wird mindestens ein Test rot.
- **Side effects:** keine — reine Test-Infrastruktur, kein Produktivpfad wird berührt.

## Acceptance Criteria

### Geteilter Test-Helfer (neu unter `tests/helpers/`)

- **AC-1:** Given der Langform-Text `... · Radar reicht bis morgen 00:12 · ...` / When der Helfer
  die Reichweite zieht / Then liefert er das Paar `("morgen", "00:12")`; beim Text
  `... · Radar reicht bis 23:47 · ...` liefert er `(None, "23:47")`.
  - Test: `extract_day_and_time()` gegen beide Textvarianten aufgerufen, Rückgabepaar auf Gleichheit
    geprüft — kein Dateiinhalt-Check.

- **AC-2:** Given der Kurzform-Text `Seg 1: R3.0@23:25@So1:35?` / When der Helfer das
  Güte-Zeichen-Token zieht / Then liefert er das Paar `("So", "1:35")`; beim Token `@23:25?` ohne
  Wochentagskürzel liefert er `(None, "23:25")`.
  - Test: `extract_day_and_time(..., style="kurzform")` gegen beide Tokenvarianten aufgerufen,
    Rückgabepaar geprüft.

- **AC-3:** Given eine Ziel-UTC-Zeit, eine Jetzt-UTC-Zeit und die Trip-Zeitzone / When der Helfer
  das ERWARTETE Paar bildet / Then ist das Tageswort `None` bei gleichem lokalen Kalendertag,
  `"morgen"` bei einem Tag Versatz und `"gestern"` bei minus einem Tag — hergeleitet aus dem
  Datumsvergleich, nicht als Literal gesetzt.
  - Test: `expected_day_and_time()` mit drei Datumskombinationen (gleicher Tag, +1 Tag, -1 Tag)
    aufgerufen, jeweils gegen das erwartete Tageswort geprüft.

- **AC-4:** Given ein Text, dessen Uhrzeit stimmt, dessen Tageswort aber falsch ist (`heute 00:12`
  statt `morgen 00:12`) / When der Helfer-Vergleich läuft / Then schlägt er fehl.
  - Test: Positivkontrolle — `extract_day_and_time()` auf den absichtlich falschen Text angewendet
    und das Ergebnis gegen `expected_day_and_time()` verglichen; der Vergleich muss fehlschlagen,
    sonst prüft der Helfer nichts.

### Paritäts-Tests auf den Helfer umgestellt

- **AC-5:** Given ein Radar-Alarm, dessen Quellen-Reichweite auf den Folgetag fällt / When Trip und
  Ortsvergleich in der Langform gerendert werden / Then nennen BEIDE Flächen dasselbe Paar aus
  Tagesbezug und Uhrzeit.
  - Test: `test_onset_reichweite_guete_kanalparitaet.py`, beide gerenderten Texte durch den Helfer
    gezogen und die Paare auf Gleichheit verglichen.

- **AC-6:** Given denselben Aufbau im Telegram-Kurzstil / When beide Alarme abgesetzt werden / Then
  trägt das Güte-Zeichen in BEIDEN Flächen dasselbe Paar aus Wochentagskürzel und Uhrzeit.
  - Test: `test_onset_reichweite_guete_kanalparitaet.py`, Kurzform-Zweig über den Helfer verglichen.

- **AC-7:** Given ein Radar-Alarm, dessen Ereignis-Ende auf den Folgetag fällt / When Trip und
  Ortsvergleich in Lang- und Kurzform gerendert werden / Then nennen beide Flächen in beiden Formen
  dasselbe Ende-Paar.
  - Test: `test_onset_ende_kanalparitaet.py` und `test_onset_ende_textstellen.py`, je Form ein
    Helfer-Vergleich.

- **AC-8:** Given ein Alarm-Replay, dessen Reichweite auf den Folgetag fällt / When der Replay-Weg
  gerendert wird / Then nennt er Reichweite und Güte-Grenze mit demselben Tagesbezug wie der
  Live-Weg.
  - Test: `test_alert_preview_nowcast_replay.py`, Replay-Text und Live-Text über den Helfer
    verglichen.

- **AC-9:** Given ein Mehr-Orte-Bündel, dessen führender Ort sein Ende am Folgetag hat / When der
  Text gerendert wird / Then nennt er das Ende mit Tagesbezug.
  - Test: bestehender Mehr-Orte-Fall in `test_onset_ende_textstellen.py`/
    `test_onset_ende_kanalparitaet.py`, Ende-Paar über den Helfer geprüft statt per nackter Regex.

### Zeitunabhängigkeit

- **AC-10:** Given die gestellte Uhr auf 12:00, 21:06, 22:50 und 23:58 UTC / When alle betroffenen
  Testdateien laufen / Then sind sie in ALLEN VIER Läufen grün, mit null übersprungenen Tests.
  - Test: die 5 Testdateien je einmal mit `frozen_active_window(hour_utc=...)` für jeden der vier
    Zeitpunkte ausgeführt, Exit-Code und Skip-Zähler geprüft.

- **AC-11:** Given eine gestellte Uhr kurz vor Mitternacht / When
  `tests/tdd/test_starkregen_kurzfristhinweis.py` läuft / Then läuft er durch, statt sich mit
  „Testzeitpunkt zu nah an einer Mitternachtsgrenze" selbst zu überspringen.
  - Test: Testlauf mit gestellter Uhr nahe Mitternacht, Prüfung dass kein `SKIPPED` mit diesem
    Meldungstext im Ergebnis erscheint.

### Der Tagesübergang ist tatsächlich bewacht

- **AC-12:** Given eine gestellte Uhr, bei der die Zeitangabe auf den Folgetag fällt / When der
  Alarm gerendert wird / Then existiert je Mechanismus (Langform-Reichweite, Langform-Ende,
  Kurzform) ein eigener Testfall, der den Überlauf-Zweig durchläuft und Tagesbezug UND Uhrzeit
  prüft.
  - Test: je Mechanismus mindestens ein dedizierter Testfall mit gestellter Uhr, der über den
    Helfer sowohl das Tageswort als auch die Uhrzeit gegen `expected_day_and_time()` verifiziert.

- **AC-13:** Given man entfernt in `src/output/renderers/alert/render.py` den
  `day_offset == 1`-Zweig von `_time_with_day()`, so dass `00:12` statt `morgen 00:12` gerendert
  wird / When die Testsuite läuft / Then wird mindestens ein Test ROT.
  - Test: Mutations-Gegenprobe — temporäre String-Ersetzung (mit externer Sicherungskopie),
    betroffene Testdateien laufen lassen, mindestens ein Fehlschlag beobachten, danach
    zurücksetzen. Heute fängt das kein Test.

- **AC-14:** Given man setzt `source_reach_day_offset` in
  `src/output/renderers/alert/project.py` fest auf `0` / When die Testsuite läuft / Then wird
  mindestens ein Test ROT.
  - Test: Mutations-Gegenprobe wie AC-13. Heute liefert `grep -rn "source_reach_day_offset" tests/`
    null Treffer.

### Fixture-Datum aus der Ortszeit

- **AC-15:** Given eine gestellte Uhr nach 22:00 UTC, bei der Systemdatum und Ortsdatum des Trips
  auseinanderfallen / When `check_radar_alerts()` in
  `tests/tdd/test_952_onset_alert_fidelity.py` läuft / Then liefert es einen Alarm, nicht null.
  - Test: Testlauf mit `frozen_active_window(hour_utc=22 oder später)`, Rückgabewert von
    `check_radar_alerts()` auf Nicht-Null geprüft.

- **AC-16:** Given man leitet das Etappendatum wieder aus `date.today()` statt aus der Ortszeit ab
  / When der Test bei gestellter Uhr nach 22:00 UTC läuft / Then wird er ROT.
  - Test: Mutations-Gegenprobe — temporäre String-Ersetzung in `_trip_with_active_segment()` (mit
    externer Sicherungskopie), Testlauf beobachtet mindestens einen Fehlschlag, danach
    zurückgesetzt.

## Known Limitations

- Der Zuschnitt ändert bewusst keinen Produktivcode — das ausgelieferte Verhalten
  (`_time_with_day()`, `source_reach_day_offset`) ist korrekt und bleibt unverändert. Geliefert
  wird ausschließlich Test-Infrastruktur, die diesen Zweig erstmals bewacht.
- Die beiden latenten Zwillinge `tests/tdd/test_onset_kurzform_menge.py` und
  `tests/tdd/test_onset_reichweite_guete_sms.py` ankern onset-nah (+20 Min) und kippen erst in den
  letzten 20 Minuten vor Mitternacht. Sie sind heute noch grün und werden nur mitgenommen, wenn der
  neue Helfer sie ohnehin abdeckt — kein eigener Testfall wird für sie zwingend neu geschrieben.
- Mechanismus C (`test_starkregen_kurzfristhinweis.py`, stiller Skip nahe der
  Mitternachtsgrenze) verschwindet als Nebeneffekt von Baustein 2 (Uhr stellen): bei gestellter Uhr
  gibt es den „zu nah an Mitternacht"-Zufall nicht mehr, den der Wächter abfangen müsste. Ob es
  weitere solcher Selbst-Skips im Repo gibt, ist ein offener Nebenbefund für das Sammel-Issue #1199,
  nicht Teil dieses Scopes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur ohne Berührung einer Entscheidungsfläche (Kanäle,
  Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie). Kein
  Produktivverhalten ändert sich.

## Changelog

- 2026-08-22: Initial spec created
