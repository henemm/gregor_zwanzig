---
entity_id: feat_2050_s3b_budget_und_unterdrueckungsgrund
type: feature
created: 2026-08-22
updated: 2026-08-22
status: draft
workflow: feat-2050-s3b-budget-und-unterdrueckungsgrund
version: "1.0"
tags: [alarm, nowcast, tageslimit, protokoll, eskalation]
---

# Budget-Durchbruch bei akuter Eskalation und benannter Unterdrückungsgrund (Issue #2050, Scheibe S3b)

## Approval

- [x] Approved — PO (Henning), 2026-08-22

## Purpose

Zwei Zusicherungen aus #2050, an bestehendem, absichtlich so gebautem Verhalten: **Szenario 10 /
Anforderung D-2** — jede Unterdrückung eines Alarms bekommt einen benannten, nachvollziehbaren
Grund samt der Werte, die zur Entscheidung führten; heute gilt das nur im Nowcast-/Radar-Zweig,
Änderungsalarm und amtliche Warnung protokollieren nichts (offene Lücken **O3**/**E3**). Und
**Szenario 7 / Anforderung D-3** — ein erschöpftes Tagesbudget darf eine sich akut verschärfende
Gewitterlage nicht verhungern lassen; heute schließt die Kette an der Tages-Obergrenze
kompromisslos ab, unabhängig davon, wie viel dringlicher die neue Lage gegenüber den bereits
verschickten Meldungen des Tages ist.

## Source

- **File:** `src/services/alert_daily_limit.py` (`is_allowed`, `increment`, neue Funktion
  `escalation_breaks_through`)
- **File:** `src/services/alert_gate.py` (`record_nowcast_sent`, unverändert: `check_nowcast_gate`)
- **File:** `src/services/trip_alert.py` (`check_radar_alerts`, `check_and_send_alerts`,
  `_send_official_alert_only`)
- **File:** `src/services/compare_alert.py`, `src/services/compare_official_alert.py`,
  `src/services/compare_radar_alert.py`
- **File:** `src/services/alert_log.py` (neue Konstante `REASON_DOUBLE_ALERT_GUARD`)
- **File:** `src/output/renderers/email/undelivered_hint.py` (neue Beschriftung)
- **Identifier:** siehe Implementation Details

Schicht: ausschließlich Python-Core (`src/services/`, `src/output/renderers/`). Kein Go-, kein
Frontend-Anteil.

## Estimated Scope

- **LoC:** ~+270 bis +400 (Produktivcode + Tests, ohne Doku) — deutlich über dem
  250-LoC-Standardlimit; `loc_limit_override 500` nötig, ggf. 550
- **Files:** ~14 — 8 Produktivdateien, 2-3 Testdateien, 3 Dokudateien
- **Effort:** high
- **Risiko:** HIGH — kritischer Alarmpfad, geteilte Bausteine (Trip + Ortsvergleich), zwei
  bestehende, kürzlich getestete Zusicherungen werden bewusst abgelöst

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_daily_limit.py::is_allowed`/`increment` | function | Bleiben in ihrer heutigen Bedeutung erhalten; `increment` bekommt zwei additive, optionale Parameter |
| `src/services/alert_gate.py::check_nowcast_gate` | function | Bleibt in Signatur UND Verhalten unverändert — die Eskalationsprüfung lebt, wie schon die Sperrzeit-Überholung aus #2065, im Aufrufer, nicht im geteilten Gate |
| `src/services/alert_gate.py::check_official_alert_gate` | function | Liefert bereits den passenden `GateResult.reason` — der amtliche Aufrufer muss ihn nur noch protokollieren statt zu verschlucken |
| `src/services/alert_urgency.py::exceeds`/`highest_urgency` | function | Bestehende Schwere-Skala, Grundlage der Eskalationsprüfung — kein dritter Eskalationsbegriff |
| `src/services/alert_log.py::append_suppressed_entry` | function | Bestehender Protokoll-Schreibpfad, an 9 neuen Stellen aufgerufen; `gate_reason` bleibt Pflichtfeld mit lautem Scheitern |
| `src/services/throttle_store.py::ThrottleStore` | class | Grundlage der bestehenden Sperrzeit (unverändert) |
| `src/services/alert_briefing_anchor.py::undelivered_since_last_briefing` | function | Liest die neu protokollierten Gründe automatisch mit — kein eigener Lesepfad nötig |
| `src/output/renderers/email/undelivered_hint.py::_REASON_LABELS`/`_REASON_BLOCK` | module data | Bekommt einen neuen Eintrag für `double_alert_guard`; die bereits vorhandenen Labels für `quiet_hours`/`daily_limit`/`cooldown` brauchen keine Änderung |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke` | test helper | Zeitreihen-Harness für beide Szenarien, Vorzustand über produktive Schreibfunktionen |
| `docs/adr/0021-shared-deviation-alert-engine.md` | doc | Trägt die feste Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze fest — Szenario 10 (amtlicher Pfad protokolliert) und Szenario 7 (Ausnahme an der Tages-Obergrenze) brauchen je einen datierten Nachtrag |
| `docs/specs/modules/alert_daily_limit.md`, `fix_2065_verschaerfung_ueberholt_sperre.md` | doc | Tragen je ein AC, das für den Eskalationsfall bewusst abgelöst wird |

## Implementation Details

### Szenario 10 — der benannte Grund (9 Stellen + 1 Sonderfall bleibt still)

Kein neues Muster: derselbe Protokoll-Aufruf, der im Radar-Zweig bereits an sieben Stellen läuft
(`alert_log.append_suppressed_entry`, Muster `_protokolliere_radar_unterdrueckung`,
`trip_alert.py:1251-1273`), wird an neun bislang stillen Stellen ergänzt:

- **Änderungsalarm, Trip** (`trip_alert.py:343/358/362`) — Ruhezeit, Sperrzeit, Tageslimit.
  `reason=alert_log.REASON_FORECAST_CHANGE`, `gate_reason` je nach Stufe
  `REASON_QUIET_HOURS`/`REASON_COOLDOWN`/`REASON_DAILY_LIMIT`.
- **Radar, Trip** (`trip_alert.py:1632`, Doppel-Alarm-Guard #818) — bislang ohne eigenen Grund.
  Neue Konstante `alert_log.REASON_DOUBLE_ALERT_GUARD = "double_alert_guard"`: die bestehenden
  sieben Gründe decken diesen Fall nicht ab (kein Cooldown auf `ThrottleStore`-Ebene, sondern ein
  eigenständiger, kanalübergreifender Wiederholungs-Schutz auf `AlertStateService`-Ebene). Braucht
  einen neuen Eintrag in `_REASON_LABELS`/`_REASON_BLOCK` (`undelivered_hint.py:48-70`), Block
  `"withheld"`, sonst erscheint im Briefing der rohe Code statt einer deutschen Beschriftung.
- **Amtlich, Trip** (`trip_alert.py:2193`, Lücke E3) — `check_official_alert_gate` liefert den
  `GateResult` mit passendem `.reason` (`REASON_QUIET_HOURS` oder `REASON_DAILY_LIMIT`) bereits
  heute; der Aufrufer muss ihn nur noch an `append_suppressed_entry` weiterreichen statt ihn zu
  verwerfen. `reason=alert_log.REASON_OFFICIAL_ALERT`.
- **Änderungsalarm, Compare** (`compare_alert.py:151/164/189`) — Sperrzeit, Tageslimit, Ruhezeit,
  analog zum Trip-Pfad, `entity_type="compare"`.
- **Amtlich, Compare** (`compare_official_alert.py:149`, Lücke E3 spiegelbildlich) — analog zum
  amtlichen Trip-Pfad.

**Der Briefing-Vorlauf protokolliert weiterhin bewusst NICHT** (`trip_alert.py:353/2204`,
`compare_alert.py:204`, `compare_official_alert.py:165`) — Bestandsschutz #1233/ADR-0009: die
Meldung wird ersetzt, nicht verschluckt, sie kommt Minuten später vollständig im Briefing an. Eine
Einbeziehung wäre ein Bruch mit einer bestehenden, dokumentierten Zusicherung und ist ausdrücklich
NICHT Teil dieser Scheibe (eigenes AC, s. u., statt stillem Mitnahmeeffekt).

### Szenario 7 — die Eskalations-Ausnahme am Tagesbudget

**Wichtiger Befund aus dieser Spec-Phase, der die ursprüngliche Analyse-Skizze korrigiert:** ein
optionaler Eskalations-Parameter direkt an `check_nowcast_gate()` funktioniert strukturell NICHT.
Sowohl `trip_alert.py::check_radar_alerts` (Gate-Aufruf `:1373`, Dringlichkeits-Ableitung erst
`:1770` NACH dem Nowcast-Fetch) als auch `compare_radar_alert.py::_check_one_preset`
(Gate-Aufruf `:182`, Dringlichkeits-Ableitung erst `:236` in `_detect_triggered_locations`) rufen
das Gate VOR dem Abruf auf, der die aktuelle Dringlichkeit erst liefert — zum Gate-Zeitpunkt ist
die für die Ausnahme nötige Information schlicht noch nicht bekannt. Das ist exakt dieselbe
strukturelle Lage, die #2065 für die Sperrzeit bereits gelöst hat, und die Spec übernimmt dessen
Muster statt es zu wiederholen:

1. **`check_nowcast_gate` bleibt in Signatur UND Verhalten unverändert.** Kein neuer Parameter,
   keine Signatur-Passagiere — dieselbe Begründung wie in #2065 (`fix_2065_…md`, „Verworfen").
2. **`alert_daily_limit.py`**, additiv im Zonen-Eintrag: `max_urgency_sent` (str, LOW/MODERATE/
   HIGH, Default fehlend = unbekannt) und `escalation_breakthroughs` (int, Default 0). Neue
   Funktion `escalation_breaks_through(user_id, now, zone, urgency) -> bool`: liest den
   Zonen-Eintrag, vergleicht `alert_urgency.exceeds(urgency, eintrag.get("max_urgency_sent") or
   "LOW")` UND `eintrag.get("escalation_breakthroughs", 0) < 1` — beide UND-verknüpft
   (Entscheidung 2 der Analyse: Eskalation UND eigener Deckel). `is_allowed`/`load` bleiben rein
   lesend und unverändert.
3. **`increment()`** bekommt zwei additive, optionale Parameter `urgency: str | None = None` und
   `is_escalation_breakthrough: bool = False`. Schreibt bei jedem Aufruf mit `urgency`
   `max_urgency_sent = alert_urgency.highest_urgency(bisheriger_wert_oder_"LOW", urgency)` fort —
   nicht nur im Durchbruchsfall, sondern bei JEDER erfolgreichen Nowcast-Zustellung, sonst wüsste
   die Zone nach einem normalen MODERATE-Alarm nie, dass „heute nichts über MODERATE hinausging".
   Erhöht `escalation_breakthroughs` um 1, wenn `is_escalation_breakthrough=True`. Weiterhin
   Read-Modify-Write des ganzen Zonen-Bestands, kein Replace — bestehende Felder anderer Zonen
   bleiben unangetastet, alte Einträge ohne die zwei neuen Felder bleiben lesbar (Default
   `None`/`0`).
4. **`alert_gate.py::record_nowcast_sent`** bekommt dieselben zwei Parameter, durchgereicht an
   `increment()` — exakt das Muster, mit dem #2065 dort bereits `precip_mm` ergänzt hat.
5. **`trip_alert.py::check_radar_alerts`**: neben dem bestehenden `_sperrzeit_offen`-Signal
   (#2065) ein zweites, unabhängiges Signal `_budget_erschoepft = not gate.allowed and
   gate.reason == alert_log.REASON_DAILY_LIMIT`. Bei `True` läuft der Fall — wie beim
   Sperrzeit-Fall — in den Fetch weiter statt sofort abzubrechen. Nach der bestehenden
   `_radar_urgency`-Ableitung (`:1770`) eine zusätzliche Prüfung
   `alert_daily_limit.escalation_breaks_through(self._user_id, now_utc, anchor_tz(trip, now_utc),
   _radar_urgency)`: nur bei `True` läuft der Versand weiter, sonst Protokoll mit
   `REASON_DAILY_LIMIT` und `continue`. Beide Ausnahmen (Sperrzeit-Überholung, Budget-Durchbruch)
   sind unabhängig — ein Lauf kann von beiden, einer oder keiner betroffen sein; die Reihenfolge
   Ruhezeit→Sperrzeit→Tages-Obergrenze bleibt dieselbe. Der bestehende `record_nowcast_sent`-Aufruf
   (`:1888`) reicht zusätzlich `urgency=_radar_urgency` und `is_escalation_breakthrough=` (gesetzt,
   wenn der Budget-Durchbruch den Fall getragen hat) durch.
6. **`compare_radar_alert.py::_check_one_preset`**: dieselbe Fallunterscheidung, neu für diesen
   Pfad (der bislang bei JEDEM `not gate.allowed` sofort abbricht, `:193-218`) — bei
   `gate.reason == REASON_DAILY_LIMIT` weiterlaufen in `_detect_triggered_locations`, je
   getriggertem Ort dieselbe `escalation_breaks_through`-Prüfung mit dem dort bereits abgeleiteten
   `urgency` (`:236`, `_identity_inputs`). Der bestehende `record_nowcast_sent`-Aufruf (`:364`)
   reicht analog `urgency=`/`is_escalation_breakthrough=` durch. Reichweite laut Entscheidung 3 der
   Analyse: **nur Nowcast/Radar**, Trip UND Compare — Änderungsalarm und amtlicher Pfad bekommen
   die Eskalations-Ausnahme in dieser Scheibe NICHT (keine Vergleichsbasis „was ging heute schon
   raus" für diese Zweige vorhanden, s. Known Limitations).

### Verworfen (aus der Analyse übernommen, nicht erneut zu prüfen)

- *Ein dritter Eskalationsbegriff* — verworfen, `alert_urgency` ist bereits in allen drei Zweigen
  ableitbar und dasselbe Vokabular wie an der Entdopplung (#1467 S4b).
- *`radar_overtakes_cooldown` für Sz 7 wiederverwenden* — verworfen, die Funktion vergleicht gegen
  eine `ThrottleStore`-Vergleichsbasis, die es außerhalb des Trip-Radar-Pfads gar nicht gibt.
- *Ein optionaler Parameter direkt an `check_nowcast_gate()`* — verworfen, s. o.: die zur
  Entscheidung nötige Dringlichkeit ist zum Gate-Zeitpunkt strukturell noch nicht bekannt.

## Expected Behavior

- **Input (Sz 10):** eine Unterdrückung an einer der neun bislang stillen Gate-Stellen, mit
  eingeschaltetem Kanal.
- **Output (Sz 10):** ein `not_delivered`-Eintrag im `alert_log` mit demselben E1-Wertesatz wie im
  Radar-Zweig (soweit an der jeweiligen Stelle bekannt) und einem konkreten `gate_reason`.
- **Input (Sz 7):** Tagesbudget erschöpft, Nowcast-Dringlichkeit übersteigt die höchste heute in
  dieser Zone bereits verschickte Stufe, kein Durchbruch dieser Zone heute bereits verbraucht.
- **Output (Sz 7):** Alarm wird trotz erschöpftem Budget zugestellt; `max_urgency_sent` und
  `escalation_breakthroughs` werden NUR nach erfolgreicher Zustellung fortgeschrieben
  (F001-Symmetrie).
- **Side effects:** neue Unterdrückungsgründe erscheinen im „nicht zugestellt"-Block der
  Briefing-E-Mail (`undelivered_since_last_briefing()`); SMS/Telegram bleiben unberührt.

## Acceptance Criteria

- **AC-1:** Given eine Ruhezeit ist aktiv, When ein Vorhersage-Änderungsalarm für einen Trip geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_QUIET_HOURS` und `reason == alert_log.REASON_FORECAST_CHANGE`; derselbe Lauf außerhalb der Ruhezeit zeigt einen tatsächlichen Versand (Positivkontrolle).

- **AC-2:** Given eine laufende Sperrzeit für einen Trip (über `ThrottleStore.record`, nicht gemockt), When ein Vorhersage-Änderungsalarm geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_COOLDOWN`; ohne Sperrzeit zeigt derselbe Lauf tatsächlichen Versand.

- **AC-3:** Given der Tageszähler eines Trip-Nutzers steht auf dem konfigurierten Limit (über `alert_daily_limit.increment` vorbelegt), When ein Vorhersage-Änderungsalarm geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_DAILY_LIMIT`; einen Zähler unter dem Limit zeigt derselbe Lauf tatsächlichen Versand.

- **AC-4:** Given der Doppel-Alarm-Guard (#818, `AlertStateService`) hält eine jüngere Meldung desselben Segments innerhalb des Cooldowns, When ein Radar-Alarm für einen Trip geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_DOUBLE_ALERT_GUARD`, und die gerenderte Briefing-Mail zeigt dafür eine deutsche Beschriftung (kein roher Code) im „nicht zugestellt"-Block; ohne den Guard-Eintrag zeigt derselbe Lauf tatsächlichen Versand.

- **AC-5:** Given `check_official_alert_gate` liefert für eine amtliche Warnung eines Trips `GateResult(False, REASON_QUIET_HOURS)` bzw. `GateResult(False, REASON_DAILY_LIMIT)`, When der amtliche Pfad geprüft wird, Then entsteht für BEIDE Fälle je ein `not_delivered`-Eintrag mit dem jeweiligen `gate_reason` und `reason == alert_log.REASON_OFFICIAL_ALERT`; ohne diese Blockade zeigt derselbe Lauf tatsächlichen Versand.

- **AC-6:** Given eine laufende Sperrzeit für ein Ortsvergleich-Preset, When ein Vorhersage-Änderungsalarm im Ortsvergleich geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `entity_type == "compare"` und `gate_reason == alert_log.REASON_COOLDOWN`; ohne Sperrzeit zeigt derselbe Lauf tatsächlichen Versand.

- **AC-7:** Given der Tageszähler eines Ortsvergleich-Nutzers steht auf dem konfigurierten Limit, When ein Vorhersage-Änderungsalarm im Ortsvergleich geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_DAILY_LIMIT`; unter dem Limit zeigt derselbe Lauf tatsächlichen Versand.

- **AC-8:** Given eine Ruhezeit ist für ein Ortsvergleich-Preset aktiv, When ein Vorhersage-Änderungsalarm im Ortsvergleich geprüft wird, Then entsteht ein `not_delivered`-Eintrag mit `gate_reason == alert_log.REASON_QUIET_HOURS`; außerhalb der Ruhezeit zeigt derselbe Lauf tatsächlichen Versand.

- **AC-9:** Given `check_official_alert_gate` liefert für eine amtliche Warnung im Ortsvergleich `GateResult(False, REASON_QUIET_HOURS)` bzw. `GateResult(False, REASON_DAILY_LIMIT)`, When der amtliche Ortsvergleich-Pfad geprüft wird, Then entsteht für BEIDE Fälle je ein `not_delivered`-Eintrag mit dem jeweiligen `gate_reason`, `entity_type == "compare"`; ohne diese Blockade zeigt derselbe Lauf tatsächlichen Versand.

- **AC-10:** Given ein geplantes Briefing steht für einen Trip oder Ortsvergleich unmittelbar bevor und wurde noch nicht versucht (`check_briefing_imminent` liefert `True`), When ein Änderungs- oder amtlicher Alarm geprüft wird, der ohne diese Bedingung zugestellt würde, Then entsteht KEIN `not_delivered`-Eintrag (Bestandsschutz #1233/ADR-0009 — die Meldung wird ersetzt, nicht verschluckt); ohne den Briefing-Vorlauf, sonst identische Lage, entsteht sehr wohl ein Zustellversuch oder ein Protokolleintrag mit anderem Grund (Positivkontrolle: die Bedingung unterscheidet wirklich, statt aus einem anderen Grund still zu bleiben).

- **AC-11:** Given seit dem letzten Briefing-Anker eines Trips wurde einer der neuen Unterdrückungsgründe protokolliert (z. B. `REASON_QUIET_HOURS` am Änderungsalarm), When `undelivered_since_last_briefing(...)` für diese Entität aufgerufen wird, Then enthält die Ergebnisliste genau diesen Eintrag mit dem korrekten `gate_reason`, und die gerenderte Briefing-E-Mail zeigt ihn im „nicht zugestellt"-Block unter der vorhandenen deutschen Beschriftung.

- **AC-12:** Given derselbe neu protokollierte Unterdrückungsgrund liegt vor, When die SMS- bzw. Telegram-Kurznachricht für denselben Trip im selben Zeitraum gerendert wird, Then bleibt deren Zeichenlänge und Inhalt gegenüber dem Stand vor dieser Änderung unverändert (kein `undelivered`-Bezug in `renderers/sms/`/`renderers/telegram*`).

- **AC-13:** Given diese Änderung ist umgesetzt, When `docs/adr/0021-shared-deviation-alert-engine.md` gelesen wird, Then trägt es einen datierten Nachtrag mit Bezug auf `#2050 S3b`, der beschreibt, dass der amtliche Pfad künftig Ruhezeit- und Tageslimit-Unterdrückungen protokolliert (Abweichung vom Nachtrag zu #1467 S3), einsortiert nach dem letzten bestehenden Nachtrag (#2065, 2026-08-22).

- **AC-14:** Given diese Änderung ist umgesetzt, When `docs/specs/modules/alert_daily_limit.md` (AC-1/AC-2) und `docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md` (AC-7) gelesen werden, Then tragen sie einen Vermerk, dass sie für den Eskalationsfall durch diese Spec abgelöst sind, mit Verweis auf `feat_2050_s3b_budget_und_unterdrueckungsgrund.md`.

- **AC-15:** Given der Tageszähler einer Zone ist erschöpft und `max_urgency_sent` dieser Zone steht — aus vorangegangenen ECHTEN Zustellungen desselben Tages (nicht direkt vorbelegt, sondern über reale Läufe mit `record_nowcast_sent(urgency=...)` entstanden) — auf `"MODERATE"`, When eine konvektive Nowcast-Lage (`is_convective=True`, folglich `alert_urgency.urgency_from_radar(...) == "HIGH"`) geprüft wird, Then wird der Alarm trotz erschöpftem Budget zugestellt, und nach dem Lauf steht `escalation_breakthroughs` dieser Zone auf `1`.

- **AC-16:** Given dieselbe Ausgangslage wie AC-15 (Budget erschöpft, `max_urgency_sent == "MODERATE"`), When eine NICHT-konvektive Lage geprüft wird, deren abgeleitete Dringlichkeit `"MODERATE"` NICHT übersteigt (`alert_urgency.exceeds(...) == False`), Then bleibt der Alarm aus, das Protokoll weist `gate_reason == alert_log.REASON_DAILY_LIMIT` aus, und `escalation_breakthroughs` bleibt unverändert bei `0` (Positivkontrolle: ohne echte Eskalation bricht das Budget weiterhin nicht durch).

- **AC-17:** Given in einer Zone hat heute bereits ein Durchbruch stattgefunden (`escalation_breakthroughs == 1`, aus einem vorangegangenen echten Lauf wie AC-15), When eine zweite, noch schwerere Eskalation in derselben Zone geprüft wird, Then bleibt der Alarm aus, das Protokoll weist `gate_reason == alert_log.REASON_DAILY_LIMIT` aus, und `escalation_breakthroughs` bleibt bei `1` (Deckel: höchstens ein Durchbruch pro Tag und Zone).

- **AC-18:** Given eine Durchbruchslage wie AC-15, aber ohne erreichbaren Zustellkanal (Zustellung scheitert), When der Lauf abgeschlossen ist, Then bleiben `max_urgency_sent` und `escalation_breakthroughs` dieser Zone gegenüber dem Stand vor dem Lauf unverändert (F001-Symmetrie: kein Buchen ohne Zustellung).

- **AC-19:** Given eine bestehende `alert_daily_count.json` im heutigen Schema ohne die zwei neuen Felder (`max_urgency_sent`, `escalation_breakthroughs`), When ein Lauf gegen diese Datei prüft und schreibt (normales Increment ODER Eskalations-Durchbruch), Then bleibt die Datei lesbar, bestehende Zonen-Einträge ANDERER Zonen bleiben unangetastet, und die zwei neuen Felder werden additiv im betroffenen Zonen-Eintrag ergänzt (Read-Modify-Write, kein Replace).

- **AC-20:** Given dieselbe Eskalationslage wie AC-15, aber im Ortsvergleich-Radarpfad (`compare_radar_alert.py` über den geteilten `check_nowcast_gate`/`escalation_breaks_through`-Mechanismus), When der Lauf geprüft wird, Then bricht der Alarm ebenso durch wie im Trip-Pfad — derselbe Mechanismus wirkt nachweislich in BEIDEN Flächen.

- **AC-21:** Given eine Ruhezeit ist aktiv UND eine extreme Eskalation liegt vor (konvektiv, weit über der bisherigen Höchststufe der Zone), When der Radar-Alarm geprüft wird, Then bleibt der Alarm dennoch aus, das Protokoll weist `gate_reason == alert_log.REASON_QUIET_HOURS` aus (PO-Ablehnung #1955 — die Ruhezeit bleibt unbrechbar, auch durch die neue Eskalations-Ausnahme).

- **AC-22:** Given `test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch` (`tests/tdd/test_radar_cooldown_overtake.py:492-552`) beschrieb bisher ein hartes, ausnahmsloses Stoppen am Tageslimit nach einem Sperrzeit-Durchbruch, When diese Scheibe ausgeliefert ist, Then ist der Test in drei benannte Nachfolgetests aufgelöst (`…stoppt_ohne_eskalation`, `…echte_eskalation_durchbricht_erschoepftes_budget`, `…eskalationsausnahme_hat_eigene_obergrenze`), die zusammen sowohl den unveränderten Normalfall (keine Eskalation bricht weiterhin nicht durch) als auch den neuen Eskalationsfall UND dessen eigenen Deckel abdecken — kein Test wird ersatzlos gelöscht.

## Messbarkeit auf Staging

| AC | Messbar auf Staging? | Wie |
|---|---|---|
| AC-1 bis AC-9 | **ja** | echten unterdrückten Lauf auslösen (S6-Rezept), dann `/home/hem/gregor_zwanzig_staging/data/users/<user_id>/alert_log.json` → `not_delivered[].channels_not_sent[].reason` bzw. `not_delivered[].reason` lesen |
| AC-10 | **nur Kern-Test** | zeitkritisches Fenster (Briefing-Vorlauf), auf Staging nicht zuverlässig reproduzierbar |
| AC-11 | **ja** | `briefing_mail_validator.py` gegen eine echte Briefing-Mail im Test-Postfach — „nicht zugestellt"-Block prüfen |
| AC-12 | **nur Kern-Test** | Zeichengleichheits-Vergleich, kein Staging-Postfach nötig |
| AC-13, AC-14 | **nur Kern-Test** | `# doc-compliance-test`, Dateiinhalt-Prüfung auf Doku ist hier zulässig (analog `fix_2065_…md` AC-14) |
| AC-15, AC-16, AC-17 | **nur Kern-Test** | braucht kontrollierte Radar-Einspeisung (konvektiv vs. nicht-konvektiv) — der Staging-Radar erlaubt das nicht; `alert-preview` stubbt Stundenreihe und Gate-Kette und beweist hier **nichts** |
| AC-18 | **nur Kern-Test** | dieselbe Einschränkung wie AC-15-17, zusätzlich ein gezielt unerreichbarer Kanal |
| AC-19 | **teilweise** | Datei-Struktur nach einem echten Tageslauf auf Staging einsehbar (`alert_daily_count.json` trägt additive Felder); der Roundtrip-Beweis mit vorbereiteter Alt-Datei selbst nur Kern-Test |
| AC-20 | **nur Kern-Test** | dieselbe Radar-Einspeisungs-Einschränkung wie AC-15 |
| AC-21 | **nur Kern-Test** | dieselbe Einschränkung wie AC-15 |
| AC-22 | **nur Kern-Test** | reine Prüfstrecken-Logik, kein Staging-Bezug |

## Known Limitations

- **Sz 7 nur Nowcast/Radar, nicht amtlich/Änderungsalarm** — dort gibt es heute keine
  Vergleichsbasis „was ging heute schon raus"; vorgemerkt für eine Folge-Scheibe, die
  `max_urgency_sent` wiederverwendbar macht.
- **Briefing-Vorlauf bleibt bewusst still** (4 Stellen, `trip_alert.py:353/2204`,
  `compare_alert.py:204`, `compare_official_alert.py:165`) — Bestandsschutz #1233/ADR-0009, kein
  Teil dieser Scheibe (AC-10 sichert genau diese Nicht-Änderung zu).
- **Szenario 4** läuft parallel als eigene Scheibe **S3a** (reine Testdateien, kein
  Produktivcode-Konflikt).
- **Sperrzeit-Überholung im Abweichungs-Zweig** (Änderungsalarm) ist als **S3c** ausgelagert und
  läuft NACH dieser Scheibe, auf derselben Gate-Kette.
- **Go-Seite unverändert**: `internal/store/log.go` liest weiterhin nur die sechs bestehenden
  Felder aus `entries`, nie `not_delivered` — die neuen Protokoll-Einträge bleiben dort
  unsichtbar, wie schon die bestehenden sieben Radar-Stellen.

## Risiken

1. **`trip_alert.py:1509-1548`** (der von #2065 gebaute Block) wird um eine zweite, unabhängige
   Ausnahme erweitert. Ein Fehler in der Verknüpfung der beiden Signale (`_sperrzeit_offen`,
   `_budget_erschoepft`) reißt den Alarmflut-Schutz für mehr als den Eskalationsfall auf.
2. **`alert_daily_limit.py:110-132`** — Schema-Erweiterung an einer Datei, die JEDEN Nutzer beim
   Alarmversand berührt. Ein Read-Modify-Write-Fehler korrumpiert den Tageszähler mandantenweit.
3. **`alert_log.py:563-569`** — `gate_reason` scheitert laut bei leerem Wert. Jede der 9 neuen
   Aufrufstellen (plus die neue `REASON_DOUBLE_ALERT_GUARD`-Konstante) muss garantiert einen
   nicht-leeren Grund liefern; das umgebende `try/except` federt ab, lässt den Alarm für diesen
   Nutzer in diesem Lauf aber ohne Protokoll aus — derselbe stille Fehlschlag, den #2073 bereits
   gefangen hat.
4. **Strukturelle Korrektur gegenüber der ursprünglichen Analyse-Skizze** (neu, in dieser
   Spec-Phase gefunden): `compare_radar_alert.py` und `src/output/renderers/email/
   undelivered_hint.py` fehlten in der Affected-Files-Liste der Analyse, sind für Sz 7 (Compare)
   bzw. AC-4 aber zwingend nötig — s. „Widerspruch/Ergänzung" unten.

## Abgelöste Zusicherungen

| Spec | AC | Sagt heute | Wird |
|---|---|---|---|
| `fix_2065_verschaerfung_ueberholt_sperre.md` | AC-7 | erschöpftes Budget stoppt den Sperrzeit-Durchbruch ausnahmslos | abgelöst für den Eskalationsfall, in drei Nachfolge-ACs aufgelöst (s. AC-22) |
| `alert_daily_limit.md` | AC-1/AC-2 | bei erreichtem Limit harte Unterdrückung, kein Protokolleintrag | AC-1/AC-2 bleiben für den Normalfall gültig; abgelöst NUR für den Eskalationsfall (Sz 7) UND ergänzt um den Protokolleintrag (Sz 10) |
| `fix_2065_…md` | AC-6 | Ruhezeit bleibt bei jeder Verschärfung unbrechbar | **unberührt** — PO-Ablehnung #1955 gilt weiter, s. AC-21 dieser Spec |
| ADR-0021 | Nachtrag zu #1467 S3 | amtlicher Pfad protokolliert nicht | Nachtrag nötig (AC-13) |

**Ablösung von `test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch`:** der Test wird
**umgeschrieben, nicht gelöscht**, damit die Ablösung nicht als „Schutz entfernt" missverstanden
wird. Drei Nachfolgetests (s. AC-22):

1. `…stoppt_ohne_eskalation` — der alte Test mit einer Rate UNTER der Eskalationsschwelle
   (nicht-konvektiv): normales Wachstum bricht das Budget weiterhin NICHT.
2. `…echte_eskalation_durchbricht_erschoepftes_budget` — konvektiv/HIGH, während heute nur
   LOW/MODERATE verschickt wurde ⇒ Alarm geht raus.
3. `…eskalationsausnahme_hat_eigene_obergrenze` — Deckel bereits erreicht, zweite, noch schwerere
   Eskalation ⇒ bleibt still, Grund `daily_limit`.

**Nachtrag 2026-08-23 (Umsetzung):** Zwei weitere Bestandstests mussten umgeschrieben werden, die
diese Spec beim Schreiben nicht benannt hatte. Beide bleiben — wie oben — an **derselben Fläche**
stehen und prüfen sie in der neuen Richtung, damit sich die Ablösung später nicht von einem still
entfernten Schutz unterscheiden lässt:

| Test | Sicherte zu | Wird | Warum |
|---|---|---|---|
| `test_official_alert_cooldown_entkopplung.py::test_ac11_…_bekommt_keinen_grund_ins_protokoll` | der amtliche Pfad protokolliert **keinen** Unterdrückungsgrund (Geltungsbereich Nowcast-only, Lücke E3 offen) | umgeschrieben zu `…_protokolliert_seinen_grund` — erwartet `quiet_hours` als Grund und `official_alert` als Auslöser | sicherte das **Gegenteil** von AC-5 zu; genau diese Beschränkung hebt Szenario 10 auf |
| `test_compare_radar_alert_daily_limit.py::test_erreichte_tages_obergrenze_verhindert_auch_den_nowcast_abruf` | bei erschöpftem Budget wird **gar nicht** abgerufen (Kostenzusicherung AC-1) | umgeschrieben zu `test_ruhezeit_verhindert_auch_den_nowcast_abruf` — dieselbe Kostenzusicherung, festgenagelt an der Ruhezeit | mit AC-20 strukturell unvereinbar: die Dringlichkeit, die über den Durchbruch entscheidet, entsteht **erst aus dem Abruf**. Die Kostenzusicherung gilt unverändert eine Stufe höher (Ruhezeit/Sperrzeit bleiben harte Stops vor dem Abruf); dass der teurere Abruf keine Meldungsflut einkauft, deckt `test_erreichte_tages_obergrenze_unterdrueckt_den_vergleichs_nowcast` mit derselben Lage ab |

**Nachtrag 2026-08-23 (Messgrößen-Ablösung durch #2050 S3c,
`docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md`):** S3c hat den harten
Abbruch am Sperrzeit-Gate des Trip-Änderungsalarms entfernt; der Lauf entscheidet dort jetzt
**nach** dem Wetterabruf. Der Stellvertreter „0 Wetterabrufe = gesperrt" trägt damit für die
Sperrzeit nicht mehr (für die vier bewusst stillen Vorlauf-Stellen dieser Spec trägt er
unverändert). Betroffen ist eine Vorbedingung von AC-10:

| Test | Sicherte zu | Wird | Warum |
|---|---|---|---|
| `test_alert_suppression_reason.py::test_ac10_briefing_vorlauf_am_trip_aenderungsalarm_bleibt_still` | Vorbedingung **beider** Trips: `Wetterabrufe == 0` | Vorlauf-Trip unverändert an der Abrufzahl (die Stufe sitzt weiter **vor** dem Abruf); Kontroll-Trip an ausbleibender **Zustellung** plus protokolliertem Grund `cooldown` | die Abrufzahl trennt die beiden Fälle nicht mehr. Beide Trips bekommen jetzt **dieselbe** alarmfähige Lage, was die Grenze zwischen stiller und scharfer Stelle schärfer zieht als zuvor |

Die Zusicherung von AC-10 ist unverändert: der Briefing-Vorlauf erzeugt **keinen** Eintrag, die
Sperrzeit sehr wohl. Gegenprobe belegt (2026-08-23): `_is_throttled_with_cooldown → False` macht
den Test rot.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (Nachtrag)
- **Rationale:** ADR-0021 hält fest, dass der amtliche Pfad in der geteilten Gate-Kette bewusst
  keine Unterdrückungsgründe protokolliert (Nachtrag zu #1467 S3). Szenario 10 dieser Scheibe
  weicht davon ab — jede Unterdrückung bekommt künftig einen Grund, auch amtlich und im
  Änderungsalarm. Nach der Projektregel („Abweichung ⇒ neues ADR bzw. datierter Nachtrag, Status
  „Abgelöst durch") braucht das einen eigenen Nachtrag (AC-13), zusätzlich zur Kennzeichnung der
  betroffenen ACs in `alert_daily_limit.md` und `fix_2065_…md` (AC-14). Szenario 7 führt keine
  neue Architektur ein — dieselbe Erweiterung des bestehenden `alert_daily_count.json`-Schemas,
  dasselbe Prüfen/Buchen-Muster, dieselbe Caller-seitige „Gate hält NICHT auf, Aufrufer
  entscheidet nach dem Fetch"-Struktur wie #2065 für die Sperrzeit.

## Changelog

- 2026-08-23: Nachtrag „Messgrößen-Ablösung durch #2050 S3c" — Vorbedingung des Kontroll-Trips in
  AC-10 von der Wetterabruf-Naht auf die Zustellung umgestellt; Zusicherung unverändert.
- 2026-08-22: Initial spec created (aus `docs/context/feat-2050-s3b-budget-und-unterdrueckungsgrund.md`,
  Analyse-Phase 2026-08-22). Struktureller Befund beim Spec-Schreiben: der in der Analyse
  skizzierte Ansatz „optionaler Eskalations-Parameter an `check_nowcast_gate()`" ist mit der
  tatsächlichen Aufrufreihenfolge (Gate vor Fetch) nicht umsetzbar — korrigiert auf das
  Caller-seitige Muster aus #2065 (s. Implementation Details, Risiko 4).
