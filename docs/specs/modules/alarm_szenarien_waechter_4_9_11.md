---
entity_id: alarm_szenarien_waechter_4_9_11
type: feature
created: 2026-08-22
updated: 2026-08-22
status: draft
workflow: feat-2050-s3a-waechter-szenarien-4-9-11
version: "1.0"
tags: [alarm, testing, harness]
---

# Alarm-Szenarien 4, 9 und 11 als Wächter auf der Prüfstrecke (Scheibe S3a, Issue #2050)

## Approval

- [ ] Approved

## Purpose

Drei der zwölf Alarm-Szenarien aus Issue #2050 haben heute keinen Wächter, der die echte
Auslöseentscheidung über die `AlarmPruefstrecke` (S1) prüft: Szenario 4 (A-3, Verschärfung
überholt Sperrzeit — im deviation-Zweig, als Kontrast zum Radar-Zweig, den #2065 bereits
vollständig bewacht), Szenario 9 (B-2, Tagesbezug über Zeitzonen bei einem Ereignis, das über
Mitternacht in den Folgetag rutscht) und Szenario 11 (D-1/D-2, Mandantentrennung der vier
Alarm-Zustandsspeicher zwischen zwei Nutzern). Diese Scheibe liefert für alle drei genau die
Lücke, ohne Produktivcode zu ändern und ohne bestehende Tests anzufassen.

## Source

- **File (neu):** `tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py` (Wächter Sz 4),
  `tests/tdd/test_alarm_szenario_tagesbezug_zeitzone.py` (Wächter Sz 9),
  `tests/tdd/test_alarm_szenario_mandantentrennung.py` (Wächter Sz 11)
- **Identifier:** keine neuen Produktiv-Symbole — alle drei Dateien nutzen ausschließlich
  `AlarmPruefstrecke`/`AlarmPruefstreckeLauf` (`tests/helpers/alarm_pruefstrecke.py`) und
  bestehende produktive Lese-/Schreibwege (`ThrottleStore`, `alert_daily_limit`,
  `AlertStateService`, `alert_log`).

> Schicht: Python-Core-Testinfrastruktur (`tests/tdd/`) — kein Produktivcode in `src/`/`api/`
> wird geändert, kein Go-/Frontend-Anteil.

## Estimated Scope

- **LoC:** ~300-380 (drei Testdateien: Sz 4 schlank/~70-100 Zeilen da nur Kontrast statt
  Vollprüfung, Sz 9 ~100-140 Zeilen inkl. Radar-Frame-Aufbau, Sz 11 ~130-170 Zeilen da vier
  Zustandsspeicher je einzeln nachgewiesen werden). Kann das 250-LoC-Standardlimit reißen —
  ggf. `loc_limit_override` wie in S1/S2a nötig.
- **Files:** 3 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke.lauf` | function | Der Harness selbst — alle drei Wächter rufen ausschließlich `.lauf(...)`, kein eigener Aufbau der Auslöseentscheidung |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstreckeLauf` | dataclass | Ergebnisobjekt (`triggered_count`, `mail`, `telegram`, `sms`, `premium_sms`) |
| `src/services/trip_alert.py::TripAlertService.check_and_send_alerts` (`:227-456`) | method | Einstiegspunkt Sz 4 (`zweig="deviation"`) — Cooldown-Gate `:306-308`, Buchung nach Versand `:451/453` |
| `src/services/trip_alert.py::TripAlertService.check_radar_alerts` | method | Einstiegspunkt Sz 9 (`zweig="radar"`) — Onset-Tagesbezug-Herleitung `:1606-1626` |
| `src/services/throttle_store.py::ThrottleStore.last_sent` (`:69-71`) | method | Liest den gebuchten Cooldown-Zeitstempel pro `user_id`/Scope — Grundlage für AC-2 (Sz 4) und AC-7 (Sz 11) |
| `src/services/alert_daily_limit.py::load` (`:74-81`) | function | Liest den Tageszähler pro `user_id`/Zone, reine Lesefunktion — Grundlage für AC-6 (Sz 11) |
| `src/services/alert_state.py::AlertStateService.load` (`:61-67`) | method | Liest das Melde-Gedächtnis pro `user_id`/`entity_id` — Grundlage für AC-8 (Sz 11) |
| `src/services/alert_log.py::read_undelivered` (`:536-...`) | function | Liest Unterdrückungs-Vorfälle EINER `user_id`/Kennung — Grundlage für AC-9 (Sz 11) |
| `src/utils/timezone.py::day_offset` (`:138-143`) | function | Berechnet den Kalendertag-Versatz, den `onset_day_offset` trägt — Grundlage für Sz 9 |
| `src/output/renderers/alert/render.py::_time_with_day`/`_sms_onset_time` (`:214-242`, `:758-771`) | function | Wortbildung des Tagesbezugs im Mail-/Telegram- bzw. SMS-Text — Grundlage für AC-3/AC-4 (Sz 9) |
| `tests/tdd/test_radar_cooldown_overtake.py` (nicht geändert) | reference | #2065 — bewacht den Radar-Zweig von Sz 4 bereits vollständig, wird hier NICHT dupliziert |
| `tests/tdd/test_alarm_szenario_gewitter_vorverlegung.py` (nicht geändert) | reference | Vorbild für den Zwei-Nutzer-Aufbau (sequenzielle Läufe, eigene `user_id` je Kontrollzweig) |
| `src/services/radar_cache.py::reset_shared_radar_cache_for_tests` (`:73-84`) | function | Wird von `.lauf()` automatisch aufgerufen; der Cache selbst ist prozessweit OHNE `user_id`-Schlüssel — Grund für sequenzielle statt parallele Läufe in Sz 11 |

## Implementation Details

**Wächter Sz 4 (`zweig="deviation"`), eine `AlarmPruefstrecke` auf einer `user_id`, zwei Läufe:**

1. Lauf 1 (Positivkontrolle): Trip ohne vorbelegte Sperrzeit, Wetterdaten mit alarmwürdigem
   Delta im Änderungs-Zweig → ein Alarm, Sperrzeit wird gebucht (`trip_alert.py:451`).
2. Lauf 2 (Kontrast): kurz danach, innerhalb desselben Sperrfensters, mit einer GEGENÜBER Lauf 1
   nochmals deutlich verschärften Lage → kein Alarm. Anders als im Radar-Zweig
   (`trip_alert.py:1438-1462`, bewacht durch `test_radar_cooldown_overtake.py`) kennt der
   Änderungs-Zweig KEINE Eskalations-Ausnahme: `_is_throttled_with_cooldown`
   (`trip_alert.py:306-308`) gibt bedingungslos `False` zurück, bevor überhaupt eine
   Verschärfung geprüft würde. Der Änderungs-Zweig schreibt bei dieser Unterdrückung KEINEN
   `alert_log`-Eintrag (kein `append_suppressed_entry`-Aufruf an dieser Stelle) — der Nachweis
   läuft deshalb über den unveränderten Sperrzeit-Zeitstempel in `ThrottleStore`, nicht über das
   Protokoll.

**Wächter Sz 9 (`zweig="radar"`), zwei unabhängige `AlarmPruefstrecke`-Instanzen (je eigene
`user_id`/Trip), je ein Lauf:**

1. Lauf A: gestellte Uhr 23:50 Ortszeit des Trips, Radar-Frame, dessen abgeleiteter Regenbeginn
   33 Minuten später auf 00:23 des Folgetags fällt (`onset_day_offset == 1`,
   `trip_alert.py:1606-1626`, Beispielwert exakt so im Bestandskommentar dort vermerkt) → ein
   Alarm, Text und SMS-Kurzform tragen den Tagesbezug.
2. Lauf B (Kontrast, eigene `user_id`): identischer Aufbau, aber Radar-Frame mit Regenbeginn
   NOCH AM SELBEN Ortstag (`onset_day_offset == 0`) → Text und SMS-Kurzform OHNE Tagesbezug/
   Suffix. Isoliert den Feldwert als Ursache des Unterschieds.

**Wächter Sz 11 (Mandantentrennung), zwei `AlarmPruefstrecke`-Instanzen (`user_id` A, B) auf
strukturell identischem Trip-Aufbau (gleiche Region, gleiche Alarmregeln), Läufe SEQUENZIELL
(nicht als Threads — `radar_cache.py` ist prozessweit und trägt keinen `user_id`-Schlüssel):**

1. Lauf A1 (`zweig="deviation"`): löst aus, bucht Sperrzeit, Tageszähler und Melde-Gedächtnis
   unter `get_data_dir(uid_a)`.
2. Lauf B1 (`zweig="deviation"`, `uid_b`): löst ebenso aus, bucht seine EIGENEN Speicher unter
   `get_data_dir(uid_b)`.
3. Lauf B2 (`zweig="radar"`, `uid_b`, innerhalb von B's Sperrfenster): wird unterdrückt,
   schreibt einen `alert_log`-Unterdrückungs-Eintrag für `uid_b`
   (`_protokolliere_radar_unterdrueckung`, `trip_alert.py:1181-1196`).
4. Nach jedem B-Lauf wird A's Zustand in allen vier Speichern erneut gelesen und mit dem Stand
   nach A1 verglichen — muss unverändert sein.

## Expected Behavior

- **Input:** je Wächter ein `Trip`-Fixture, zweigspezifische Eingangsdaten
  (`cached_weather`/`fresh_weather` bzw. Radar-Frames), gestellte Uhrzeiten.
- **Output:** `AlarmPruefstreckeLauf` je Lauf (`triggered_count`, vier Kanal-Inhalte); bei Sz 11
  zusätzlich direkte Lesezugriffe auf die vier produktiven Speicher-APIs
  (`ThrottleStore.last_sent`, `alert_daily_limit.load`, `AlertStateService.load`,
  `alert_log.read_undelivered`) je `user_id`.
- **Side effects:** reale Schreibvorgänge in die Zustandsspeicher unter dem pro-Test isolierten
  `get_data_dir(user_id)` — kein echter Mail-/SMS-/Telegram-Versand.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne aktive Sperrzeit, dessen Wetterdaten im Änderungs-Zweig eine
  deutliche, alarmwürdige Verschärfung zeigen, When ein Prüflauf über den deviation-Zweig fährt,
  Then löst der Lauf genau einen Alarm aus und bucht dabei eine Sperrzeit für den Trip.
  - Test: `AlarmPruefstrecke.lauf(zweig="deviation", cached_weather=..., fresh_weather=...)` auf
    frischem `user_id`/Trip ohne Vorlauf; `triggered_count == 1`; anschließend
    `ThrottleStore(user_id).last_sent("trip", trip.id)` liefert einen Zeitstempel ≠ `None`.
    Positivkontrolle für AC-2: ohne diesen Nachweis wäre unklar, ob die Verschärfung selbst
    überhaupt auslösefähig ist.

- **AC-2:** Given dieselbe Sperrzeit ist noch aktiv (aus AC-1 gebucht) und der zweite Prüflauf
  bietet eine gegenüber AC-1 nochmals deutlich verschärfte Lage an, When der zweite Prüflauf
  innerhalb des Sperrfensters über den deviation-Zweig fährt, Then bleibt der Lauf ohne Alarm
  (`triggered_count == 0`) — anders als im Radar-Zweig (bewacht durch
  `tests/tdd/test_radar_cooldown_overtake.py`, Issue #2065) gibt es im Änderungs-Zweig keine
  Eskalations-Ausnahme.
  - Test: zweiter `.lauf(zweig="deviation", ...)` mit höherem Delta als in AC-1, `at` innerhalb
    des Sperrfensters aus AC-1; `triggered_count == 0`;
    `ThrottleStore(user_id).last_sent("trip", trip.id)` bleibt exakt der Zeitstempel aus AC-1
    (kein neuer Versand hat ihn überschrieben) — Nachweis, dass der Cooldown-Gate früh griff,
    nicht dass zufällig ein anderer Gate zuschlug.

- **AC-3:** Given ein Prüflauf um 23:50 Ortszeit des Trips mit einem Radar-Frame, dessen
  abgeleiteter Regenbeginn auf 00:23 des Folgetags fällt (`onset_day_offset == 1`), When der
  Lauf über den Radar-Zweig fährt und auslöst, Then trägt der Mail- oder Telegram-Text der
  Beginnzeit einen erkennbaren Tagesbezug statt einer nackten Uhrzeit ohne Tagesbezug (laut
  `_time_with_day()`, `render.py:214-242`, voraussichtlich das Wort „morgen" bei
  `day_offset == 1` — exakter Wortlaut wird beim Testbau am echten Renderer-Output verifiziert).
  - Test: `.lauf(zweig="radar", at=<23:50 Ortszeit>, radar_service=<Frame mit Onset 33 Min
    später>)`; `triggered_count == 1`; Text in `lauf.mail` oder `lauf.telegram` enthält sowohl
    den beim Bau ermittelten Tagesbezugs-Baustein als auch die Uhrzeit `00:23`.

- **AC-4:** Given denselben auslösenden Lauf wie in AC-3, When der SMS-Text gelesen wird, Then
  trägt die Kurzform den additiven Tagessuffix (`_sms_onset_time()`, `render.py:758-771` — bei
  `day_offset == 1` das Suffix `+1`), unterscheidbar von einer taggleichen Beginnzeit ohne
  Suffix.
  - Test: `lauf.sms` aus AC-3 enthält die Uhrzeit mit `+1`-Suffix (exakte Kurzform beim Testbau
    am Renderer-Output ermittelt), NICHT dieselbe Uhrzeit ohne Suffix.

- **AC-5:** Given ein zweiter, unabhängiger Prüflauf mit identischem Aufbau, aber einem
  Radar-Frame, dessen abgeleiteter Regenbeginn noch am selben Ortstag liegt
  (`onset_day_offset == 0`), When dieser Lauf über den Radar-Zweig fährt und auslöst, Then trägt
  weder der Mail-/Telegram-Text noch der SMS-Text einen Tagesbezug oder Suffix — der
  Unterschied zu AC-3/AC-4 kommt ausschließlich vom Feldwert, nicht von einer anderen
  Textvorlage.
  - Test: eigener Trip/`user_id`, `.lauf(zweig="radar", at=<Uhrzeit sodass Onset vor
    Mitternacht liegt>, ...)`; Text ohne Tageswort, SMS-Kurzform ohne `+`-Suffix.

- **AC-6:** Given zwei Nutzer A und B mit strukturell identischem Trip-Aufbau auf getrennten
  `AlarmPruefstrecke`-Instanzen, When Nutzer A einmal auslöst und anschließend Nutzer B
  ebenfalls auslöst (sequenziell, A dann B), Then bleibt Nutzer A's Tageszähler bei dem Stand,
  den A's eigener Lauf gesetzt hat — unverändert durch B's Auslösung.
  - Test: `alert_daily_limit.load(uid_a, at, zone)` nach A's Lauf notieren, B's Lauf ausführen
    (`.lauf(zweig="deviation", ...)` auf `uid_b`), danach erneut
    `alert_daily_limit.load(uid_a, at, zone)` lesen — identischer Wert; B's eigener Zähler
    zeigt B's Buchung (Positivkontrolle, dass B's Lauf tatsächlich etwas gebucht hat).

- **AC-7:** Given denselben Aufbau wie AC-6 nach A's erstem Lauf (Sperrzeit gebucht), When
  Nutzer B auslöst und danach ein zweiter, unterdrückter Lauf von B im selben Sperrfenster
  läuft, Then bleibt Nutzer A's gebuchte Sperrzeit unverändert — Zeitstempel weicht nicht von
  dem ab, was A's eigener Lauf gesetzt hat.
  - Test: `ThrottleStore(uid_a).last_sent("trip", trip.id)` vor und nach B's zwei Läufen
    vergleichen — identischer Zeitstempel; `ThrottleStore(uid_b).last_sent(...)` zeigt B's
    eigenen, davon verschiedenen Zeitstempel (Positivkontrolle, dass B's Speicher überhaupt
    beschrieben wurde). Zusätzlich (Fix-Loop-Ergänzung nach Finding F001, s. Changelog):
    `ThrottleStore(uid_a).last_sent("radar", radar_trip_b.id)` liest B's radar-Schlüssel
    unter A's Kennung — muss `None` sein, sonst würde eine `get_data_dir()`-Regression von
    AC-7 unbemerkt bleiben, obwohl AC-6/AC-8 sie bereits fangen.

- **AC-8:** Given A und B lösen je einen Alarm mit derselben Metrik/Segment-Kombination aus
  (identischer `entity_id`/Metrikschlüssel möglich, da Trip-Aufbau gleich), When B's Lauf nach
  A's Lauf fährt, Then enthält `AlertStateService(uid_a).load(trip.id)` weiterhin ausschließlich
  den von A's eigenem Lauf gemeldeten Wert — nicht den von B gemeldeten.
  - Test: `AlertStateService(uid_a).load(trip.id)` nach A's Lauf lesen (enthält A's
    `last_reported_value`), B's Lauf ausführen, erneut `AlertStateService(uid_a).load(trip.id)`
    lesen — identischer Inhalt; `AlertStateService(uid_b).load(trip.id)` zeigt B's eigenen,
    unabhängigen Eintrag (Positivkontrolle, dass B's Speicher überhaupt beschrieben wurde).

- **AC-9:** Given A's erster Lauf hat ausgelöst und B's zwei Läufe (einer ausgelöst, einer durch
  Sperrzeit unterdrückt und protokolliert) sind danach gefahren, When
  `alert_log.read_undelivered(uid_a, entity_id=trip.id, entity_type="trip", since=...)` gelesen
  wird, Then enthält das Ergebnis keinen der Einträge, die B's unterdrückter Lauf erzeugt hat —
  A's Protokoll bleibt auf A's eigene Vorfälle beschränkt.
  - Test: nach der vollständigen Lauf-Sequenz (A1, B1, B2) `alert_log.read_undelivered(uid_a,
    ...)` aufrufen — Ergebnisliste leer oder ausschließlich A-eigene Vorfälle;
    `alert_log.read_undelivered(uid_b, ...)` zeigt B's Unterdrückungs-Eintrag (Positivkontrolle,
    dass der Schreibweg selbst funktioniert und geprüft wird). Zusätzlich (Fix-Loop-Ergänzung
    nach Finding F001, s. Changelog): derselbe Lesevorgang unter `uid_a`, aber mit
    `entity_id=radar_trip_b.id` — muss leer sein, sonst würde eine `get_data_dir()`-Regression
    von AC-9 unbemerkt bleiben.

## Known Limitations

- **Sz 4 schreibt bei Cooldown-Unterdrückung kein Protokoll.** Anders als der Radar-Zweig
  (`_protokolliere_radar_unterdrueckung`, `trip_alert.py:1181-1196`) ruft der Änderungs-Zweig bei
  `_is_throttled_with_cooldown` (`:306-308`) kein `append_suppressed_entry` auf — AC-2 kann sich
  deshalb nicht auf einen Protokoll-Grund stützen, sondern weist den unveränderten
  `ThrottleStore`-Zeitstempel nach. Das ist eine bestehende Asymmetrie zwischen den Zweigen, kein
  Fehler dieser Scheibe — eine eigene Protokollierung für den Änderungs-Zweig wäre
  Produktivcode und damit außerhalb dieses Zuschnitts.
- **AC-1/AC-2 halten den IST-Zustand fest, nicht das Soll aus Anforderung A-3.** Der PO hat am
  2026-08-22 entschieden ([#2050, Kommentar](https://github.com/henemm/gregor_zwanzig/issues/2050#issuecomment-5382394308)),
  dass „eine Verschärfung überholt jede Sperre" auch im **Änderungs-Zweig** gilt, nicht nur im
  Radar-Zweig. Heute existiert diese Überholung dort nicht (`trip_alert.py:306-308`, harter
  `return False` bei `_is_throttled_with_cooldown`, ohne jede Schweregrad-Prüfung). Geschlossen
  wird die Lücke durch **Scheibe S3c (#2050)**; mit ihr kehrt sich AC-2 um (dann: Alarm löst aus,
  Sperrzeit-Zeitstempel wird neu gebucht) und der Wächter ist mit-umzuschreiben. Ein nach S3c
  rotes AC-2 ist der erwartete Befund, keine Regression.
- Sollte einer der drei Wächter beim Bau rot bleiben (Produktivverhalten weicht vom AC ab), gilt
  dieselbe Regel wie in S2a: gemessen rot dokumentieren, NICHT stillschweigend anpassen oder
  auslassen, und den betroffenen AC explizit als „gemessen rot, ausgelagert nach Issue …"
  markieren.
- **Finding F001 (behoben, s. Changelog):** Die ursprüngliche Fassung von AC-7/AC-9 prüfte A's
  Zustand ausschließlich unter A's eigenem Schlüssel. Eine `get_data_dir()`-Regression (Nutzer-
  Trennung an der Wurzel aufgehoben) wäre dort NICHT eigenständig aufgefallen, weil B's
  radar-Aktivität unter einem eigenen `trip_id` läuft, der nie mit A kollidiert — nur AC-6/AC-8
  hätten die Mutation gefangen. Der Fix-Loop hat beide ACs um eine zusätzliche Gegenlesung von
  B's Schlüssel unter A's Kennung ergänzt (siehe AC-7/AC-9-Testzeilen oben); die Mutations-
  Gegenprobe wurde danach eigenständig wiederholt und bestätigt den Fang.

## Nicht Ziel

- Der Radar-Zweig-Nachweis für Szenario 4 (Anforderung A-3) — bereits vollständig durch
  `tests/tdd/test_radar_cooldown_overtake.py` (Issue #2065) erbracht, wird hier NICHT
  dupliziert.
- Echte Nebenläufigkeit (Threads) für Szenario 11 — Läufe sind bewusst sequenziell, weil
  `radar_cache.py:73-84` ein prozessweiter Cache OHNE `user_id`-Schlüssel ist.
- Der exakte Wortlaut des Tagesbezugs wird nicht vorab über alle sechs `*_day_offset`-Felder aus
  `src/output/renderers/alert/model.py` behauptet — nur das vom gewählten Testfall
  (`onset_day_offset`) tatsächlich durchlaufene Feld wird geprüft.
- Jede Änderung an Produktivcode (`src/`, `api/`).
- Änderungen an `tests/tdd/test_radar_cooldown_overtake.py`,
  `tests/tdd/test_alarm_szenario_gewitter_vorverlegung.py` (nur lesen/als Vorbild verwenden).
- Die verbleibenden neun der zwölf Alarm-Szenarien aus #2050 (spätere Scheiben).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur ohne Produktivcode-Änderung, keine neue Route, kein
  neues Datenmodell, keine Rücknahme einer bestehenden Architekturentscheidung. Kein
  ADR-würdiger Grundsatzentscheid.

## Changelog

- 2026-08-22: Initial spec created (Scheibe S3a aus #2050, verdichtet aus
  `docs/context/feat-2050-s3a-waechter-szenarien-4-9-11.md`).
- 2026-08-22: Aufspaltung nach S3c festgehalten — Anforderung A-3 gilt laut PO-Entscheid auch im
  Änderungs-Zweig; S3a bleibt reiner Wächter des Ist-Zustands (AC-1/AC-2 unverändert), die
  Verhaltensänderung übernimmt Scheibe S3c (#2050). Siehe „Known Limitations".
- 2026-08-22: Nach dem Bau — 9/9 Wächter grün, kein Produktivcode geändert
  (`docs/artifacts/feat-2050-s3a-waechter-szenarien-4-9-11/test-green-output.txt`).
  Adversary-Verdict zunächst AMBIGUOUS (Finding F001: AC-7/AC-9 ohne eigenständige Fangkraft
  gegenüber einer `get_data_dir()`-Regression, transitiv nur über AC-6/AC-8 abgesichert),
  Fix-Loop hat AC-7/AC-9 um eine Gegenlesung von B's Schlüssel unter A's Kennung ergänzt (s.
  „Known Limitations" und AC-7/AC-9 oben), eigenständig mit wiederholter Mutations-Gegenprobe
  nachgewiesen. Finales Verdict: **VERIFIED**
  (`docs/artifacts/feat-2050-s3a-waechter-szenarien-4-9-11/adversary-dialog.md`).
