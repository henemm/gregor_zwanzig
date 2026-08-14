---
workflow: fix-1727-s5b-versandpfade
issue: 1727
epic: 1722
created: 2026-08-14
base_head: 1e5e0be9
---

# Context: fix-1727-s5b-versandpfade

## Request Summary

Die Fundstellen aus #1727, die den Kalendertag noch aus der Umgebungsuhr (`date.today()`)
statt aus der Ortszone bestimmen und dabei auf **versendete Briefing-Inhalte** wirken, folgen
künftig dem Ortstag. Scheibe S5b von #1727 (Epic #1722, ADR-0044/ADR-0051).

## Type

Bugfix gegen eine bereits getroffene Entscheidung (ADR-0044 „Akzeptiert"). Keine offene
Produktfrage.

---

## Die neun Fundstellen — gemessen, nicht aus dem Ticket übernommen

Ticketstand `1e5e0be9`. Zeilennummern aus `KNOWN_VIOLATIONS` waren durchweg verschoben; die
Angaben hier sind am Code nachgezählt.

| # | Fundstelle | Codezeile | Prod-Aufrufer | Test-Aufrufstellen |
|---|---|---|---|---|
| 1 | `trip_report_scheduler.py:871` `select_test_stage` | `today = date.today()` | 1 | 10 |
| 2 | `trip_report_scheduler.py:1103` `_send_trip_report_outcome` | `if allow_test_fallback and target_date < date.today():` | 6 | 47 |
| 3 | `trip_report_scheduler.py:1708` `_clamp_segments_to_today` | `delta_days = (date.today() - from_date).days` | 1 | **0** |
| 4 | `trip_report_scheduler.py:2023` `_build_stage_trend` | `today = date.today()` | 2 | 27 |
| 5 | `trip_report_scheduler.py:2416` `_collect_future_stage_weather` | `today = date.today()` | 1 | 6 |
| 6 | `alert_briefing_anchor.py:169` `briefing_target_day_is_current` | `heute = today or date.today()` | 1 | **0** |
| 7 | `scheduler_dispatch_service.py:79` `_auto_pause_expired_presets` | `expired = date.fromisoformat(end_date_str) < date.today()` | 1 | **0** |
| 8 | `notification_service.py:1717` `_target_date_from_report` | `return _date.today()` | 1 (Kette) | **0** |
| 9 | `scheduler_dispatch_service.py:369` `send_one_compare_preset` | `target_date = date.today()` (Einzelversand-Zweig) | 2 | 67 — **aber keine davon betroffen**, s.u. |

### Wirkung je Fundstelle

| # | Was der Wert entscheidet | Auf VERSENDETEN Inhalt? |
|---|---|---|
| 1 | Welche Etappe der Test-Versand nimmt, wenn am Zieltag keine liegt (`s.date >= today`) | ja — Etappenwahl |
| 2 | Ob die Segmentzeiten für den Wetterabruf auf heute geklemmt werden | ja — Wetter-Input des Test-Fallbacks |
| 3 | Um wie viele Tage geklemmt wird | mittelbar (Rechenweg von #2) |
| 4 | Welche künftigen Etappen im Vorhersagehorizont liegen → welche Trendzeilen in die Mail gehen | **ja — Ausblick** |
| 5 | Dasselbe für den Gewitter-Ausblick (Rückfall, wenn der Trend nicht lädt) | **ja — Gewitter-Ausblick** |
| 6 | Ob ein Versandfehler-Vermerk verfällt oder nachgeliefert wird | **ja — ob überhaupt zugestellt wird** |
| 7 | Ob ein Compare-Preset wegen `end_date` pausiert wird | **ja — ob überhaupt versendet wird** |
| 8 | Datum im Test-/On-Demand-/Catchup-/Teilausfall-Präfix | ja — Text in Mail/SMS/Telegram |
| 9 | Zieltag des Compare-Einzelversands (Engine, Betreff, Δ-Anker-Versatz) | **ja — Mailinhalt des Ortsvergleichs** |

Damit ist die Ticketaussage „S5b: sichtbar, aber ohne Versand- oder Alarmwirkung" für die
Restliste widerlegt. Korrektur bereits im Ticket gebucht
(Kommentar vom 2026-08-14).

### Fundstelle 2 ist ein in sich widersprüchlicher Vergleich

`target_date` stammt an dieser Stelle bereits aus `_get_target_date` → `trip_local_today`
(`trip_report_scheduler.py:815`), ist also **Ortstag**. Verglichen wird er gegen `date.today()`,
also den **Servertag**. Zwei Tagesbegriffe in einem `<`-Vergleich — genau die Bruchstelle, vor
der `docs/context/fix-1697-ortstag-statt-servertag.md` warnt.

### Fundstellen 4 und 5: keine Ausnahme, sondern echter Fix

Beide speisen `is_within_forecast_horizon(stage_date, reference_date)`
(`src/providers/openmeteo.py:172-178`) — eine reine Funktion
`(stage_date - reference_date).days <= OPENMETEO_MAX_FORECAST_DAYS`. `stage_date` ist ein
**Etappentag** (Ortstag-Semantik). Ein Servertag als `reference_date` mischt zwei
Tagesbegriffe. Die naheliegende Vermutung „Anbieter-Fenster, also UTC richtig — wie
`forecast_budget._today_utc`" trägt hier **nicht**: dort zählt ein Kontingent, hier wird ein
Nutzerdatum verglichen. Keine PO-Frage.

### Fundstelle 9: das Paar `(target_date, tage_ab_ortstag)` läuft heute schon auseinander

Der Einzelversand-Zweig (`scheduler_dispatch_service.py:366-370`) setzt
`target_date = date.today()` (**Servertag**) und `tage_ab_ortstag = 0` (**Versatz gegen den
Ortstag**). Genau das Auseinanderlaufen, das der Kontrakt aus #1661 F003 verhindern sollte —
der `ValueError` darüber fängt nur den Fall „eines von beiden übergeben", nicht den Fall
„beide intern aus verschiedenen Tagesbegriffen gebildet".

### Fundstelle 7: welche Zone gilt für ein Preset mit mehreren Orten?

Ein Compare-Preset hat mehrere Orte mit je eigener Zone. Präzedenzfall vorhanden:
`first_resolvable_tz()` (aus #1726) und die Referenzzonen-Auflösung in
`run_compare_presets_daily` (`scheduler_dispatch_service.py:171-184`). Entscheidung gehört in
die Spec, nicht zum PO — sie folgt dem bestehenden Muster.

---

## 🔴 Der Zuschnitt-Entscheid: Regel 3 hat zwei Hälften, und nur eine ist bezahlbar

ADR-0051 Regel 3 (`docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md:67-69`) im Wortlaut:

> **Regel 3 — Keine Umgebungsuhr.**
> `date.today()`, `datetime.now()` ohne `tz`, `time.Local` und `new Date()` ohne explizite Zone
> sind im Produktivcode verboten. „Jetzt" wird als Zeitpunkt-Parameter hereingereicht.

Das sind **zwei** Zusicherungen:

- **(a) Kein Servertag-Datum.** Erfüllt, sobald `date.today()` durch
  `trip_local_today(trip, …)` ersetzt ist. Genau das prüft Muster A des Wächters, und genau das
  leert die Ausnahmeliste.
- **(b) „Jetzt" kommt vom Aufrufer.** Verlangt `now_utc` als Pflichtparameter.

**Gemessene Kosten von (b):** Die vier Fundstellen 1, 2, 4, 5 haben überall ein `trip`-Objekt
im Zugriff, aber **kein** `now_utc`. `_send_trip_report_outcome` löst seines inline auf
(`:1074-1077`, nicht an eine Variable gebunden, in Fundstelle 2 also nicht verfügbar). Ein
Pflichtparameter an allen vieren kostet **90 Test-Aufrufstellen** (47 + 10 + 27 + 6) über rund
20 Dateien. Ein `now_utc: datetime | None = None` mit internem Rückfall wäre der billige Weg —
und genau die Falle aus #1726 F002: unter `freeze_time` ist nicht unterscheidbar, ob der
Aufrufer durchreicht oder die Funktion still auf die Uhr zurückfällt.

### 🔴 Korrektur: das „Millisekunden-Rennen" gilt nur für 1, 2 und 3

Die erste Fassung dieser Analyse stufte die gesamte (b)-Restlücke als „Rennen von
Millisekunden zwischen zwei `now()`-Aufrufen" ein. Das ist für die Fundstellen 1 und 2
richtig — sie stehen **vor** jedem Netzabruf (`_convert_trip_to_segments` ist ein reiner
Delegator auf `services.trip_segments`, `:1683-1694`).

Für 4 und 5 ist es **falsch**. Zwischen der Zeitauflösung bei `:1074-1077` und
`_build_stage_trend` (`:2023`) liegen:

- `self._fetch_weather(...)` (`:1131`) mit echtem Retry-Backoff — `FETCH_RETRY_ATTEMPTS = 2`,
  `FETCH_RETRY_BACKOFF_SECONDS = 1` (`:72-73`), `time_module.sleep(...)` bei transienten
  Fehlern (`:1775`, `:1795`), je Segment und aufsummiert
- amtliche Warnungen je Ort (`:1136-1164`), Ensemble-Anreicherung (`:1208-1209`),
  `_fetch_night_weather` (`:1232`)
- `_build_stage_trend` holt danach in seiner eigenen Schleife nochmals Wetter (`:2024-2053`);
  `_collect_future_stage_weather` ist ein **Rückfall dahinter** (`:2213-2216`), also noch später

**Das Projekt hat dieselbe Kette bereits einmal ausgemessen und schriftlich festgehalten** —
`dispatch_orchestrator.py:157-163` zum Compare-Pfad: „zwischen `collect_due` und diesem Aufruf
liegen Wetterabruf, Rendering und die 2s-Warteschlange je vorangehendem Preset, und damit
**möglicherweise eine Mitternacht**." Auf eine strukturgleiche Kette die
Millisekunden-Einordnung anzuwenden, war eine Vermutung gegen einen eigenen, gemessenen
Präzedenzfall.

**Folge für den Zuschnitt:** Bei 4 und 5 genügt (a) nicht. Wird dort ein *eigenes*
`datetime.now()` aufgelöst, kann es nach einem langen Abruf bereits den **nächsten Ortstag**
tragen, während `target_date` noch auf dem alten steht — derselbe Zwei-Tagesbegriffe-Bruch,
nur eine Ebene tiefer. Beide bekommen `now_utc` deshalb als Pflichtparameter.

### Entscheid

| Fundstelle | (a) Ortstag | (b) Zeitpunkt vom Aufrufer | Kosten |
|---|---|---|---|
| 1 `select_test_stage` | ✅ | ✅ Pflichtparameter | 10 Test-Aufrufstellen |
| 2 `_send_trip_report_outcome:1103` | ✅ | teilweise — `now_utc` **einmal oben binden** statt inline bei `:1076` | 0 |
| 3 `_clamp_segments_to_today` | ✅ | ✅ Tag kommt vom Aufrufer | 0 |
| 4 `_build_stage_trend` | ✅ | ✅ Pflichtparameter | 27 Test-Aufrufstellen |
| 5 `_collect_future_stage_weather` | ✅ | ✅ Pflichtparameter | 6 Test-Aufrufstellen |
| 6 `briefing_target_day_is_current` | ✅ | ✅ `now_utc` liegt am Aufrufort | 0 |
| 7 `_auto_pause_expired_presets` | ✅ | ✅ `now_utc` liegt am Aufrufort | 0 |
| 8 `_target_date_from_report` | ✅ | teilweise — Zone aus `request.trip_tz` | 0 |
| 9 `send_one_compare_preset` | ✅ | teilweise — interne Auflösung, Reihenfolge korrigiert | 0 |

**Verbleibende (b)-Lücke: nur noch die Fundstellen 2, 8 und 9** — dort wird „jetzt" weiterhin
innerhalb der Funktion aufgelöst, aber jeweils **vor** jedem Netzabruf. Das ist der
Millisekunden-Fall, für den die Einordnung trägt. Zusammen mit
`send_on_demand_report` (`trip_report_scheduler.py:966`) bildet er die (b)-Folgescheibe.

Gesamtkosten der Parameter-Durchreichung: **43 Test-Aufrufstellen**, je eine Zeile.

### Wo (b) gratis ist

- **#6:** `_process_pending_markers(self, now_utc: datetime, …)` hat den Parameter
  (`trip_report_scheduler.py:495`), und `trip` steht an der Fundstelle im Zugriff (`:530`).
  `briefing_target_day_is_current(entry.get("date"), today=trip_local_today(trip, now_utc))`
  erfüllt (a) **und** (b) in einer Zeile.
- **#7:** `pre_pass(self, now_utc: "datetime", due: list)`
  (`dispatch_orchestrator.py:146`) hat `now_utc` und reicht es **nicht** weiter
  (`:151`). Durchreichen kostet eine Zeile, 0 Test-Aufrufstellen.
- **#3:** `_clamp_segments_to_today(segments, from_date)` hat gar kein `trip` — der Tag muss
  ohnehin vom Aufrufer (`:1104`) kommen, der ihn dort bereits ortsrichtig hat. 0 Aufrufstellen.
- **#8:** `TripReportRequest` trägt `trip: "Trip"` **und** `trip_tz: ZoneInfo`
  (`notification_service.py:65/68`) — die Zone liegt bereits aufgelöst am Fundort.

---

## Nicht in dieser Scheibe

- **`trip_report_scheduler.py:966` `send_on_demand_report`** — löst intern
  `datetime.now(timezone.utc)` auf. Der Tag ist bereits **richtig** (über `_get_target_date` →
  `trip_local_today`), es fehlt nur (b). **Für Muster A unsichtbar**, weil `datetime.now()` dort
  ein `tz`-Argument trägt — der Schrumpf-Test deckt diese Stelle nicht ab. Gehört in die
  (b)-Scheibe.
- **Die Go-Seite** (225 × `time.Now()`) — unverändert eigener Befund, s. Ticketkörper.

---

## Existing Patterns — erprobt und gehärtet

| Vorlage | Fundort | Was sie zeigt |
|---|---|---|
| `trip_local_today(trip, now_utc) -> date` | `src/services/trip_day.py:90` | Der geteilte Baustein. Delegiert auf `trip_local_now(trip, now_utc).date()`. **Keine Kopie bauen** (ADR-0044: kein Zweitauflöser). |
| `_get_target_date` | `trip_report_scheduler.py:795`, Auflösung `:815` | `now_utc` als Parameter, `trip_local_today` im Rumpf |
| `_get_active_trips` | `trip_report_scheduler.py:736`, `:763` | Tagesbestimmung **in** der Schleife, je Tour (#1724) |
| `_collect_due_trips` | `trip_report_scheduler.py:390`, `:442` | `trip_local_now(trip, now_utc)` direkt |
| `run_compare_presets_daily` | `scheduler_dispatch_service.py:171-184` | `now_utc` atomar ermitteln, dann durchreichen (#1724) |
| `first_resolvable_tz()` | `src/utils/timezone.py` (#1726) | Zonenwahl bei mehreren Orten |

---

## Nachweisführung

Vollständig **offline** belegbar (Kern-Schicht): `freeze_time` + In-Memory-`Trip`/`Stage`/
`Waypoint`. Keine Staging-Mail nötig — geprüft wird die Tagesbestimmung, nicht der Transport.

### Vorbedingungs-Anker ist Pflicht

Muster aus S5a (`tests/tdd/test_befehlspfade_folgen_ortszone.py:619-636`): der Test misst
**zuerst**, dass Ortstag und Servertag bei seiner Fixtur wirklich auseinanderfallen, und dass
`freeze_time` im Prüfprozess überhaupt greift:

```python
assert erwartet_parameter != erwartet_systemuhr, (
    "Testaufbau nicht diskriminierend: … der Fall kann nichts belegen")
...
assert tag_uhr != tag_param, (
    "Testaufbau: Uhr und Parameter muessen auf verschiedene ORTSTAGE fallen, "
    "nicht nur auf verschiedene Uhrzeiten")
assert datetime.now(tz=timezone.utc) == FROST_UTC, (
    "Testaufbau: freeze_time greift nicht …")
```

Ohne diesen Anker ist die Hauptzusicherung strukturell nie falsifizierbar (#1726 F002).

### 🔴 Die Nachweis-Grenze dieser Scheibe muss benannt bleiben

Der S5a-Wächter gegen „Parameter behalten, im Rumpf ignorieren" (Adversary F001,
`reference_freeze_time_macht_parameter_vs_systemuhr_unfalsifizierbar`) ist an den Fundstellen
1, 2, 4, 5 **nicht anwendbar**, weil es dort keinen Parameter gibt, gegen den man die Uhr
stellen könnte. Geprüft wird dort ausschließlich (a): unter `freeze_time` liefert eine Tour in
Neuseeland (UTC+12) bzw. an der US-Westküste einen anderen Ortstag als den Servertag. Das ist
falsifizierbar und ausreichend für die Zusicherung, die diese Scheibe macht — aber es beweist
**nicht** die zweite Hälfte von Regel 3. Wer den Wächter später sucht: er kommt mit der
(b)-Scheibe, nicht hier.

### Testfixturen

23 von 24 Fixtur-Dateien liegen in Mitteleuropa (Offset-Fenster 2 h/Tag) und können den Fehler
strukturell nicht zeigen. Verfügbar:

- `_trip_two_zones` — Wellington + Korsika, mit S5a nach `tests/tdd/conftest.py` gehoben
- Drei-Zonen-Fixtur Pago Pago (−11) / Korsika (+2) / Kiritimati (+14) aus S5a
- `tests/unit/test_trip_local_today.py` — Vorbedingungs-Anker-Muster (`:60-63`)

---

## Bestehende Wächter

| Wächter | Wirkung auf diese Scheibe |
|---|---|
| `tests/test_output_timezone_guard.py::test_no_unlisted_output_timezone_violations` | Neue Funde blocken |
| `…::test_known_violations_only_shrink` | **Die neun Einträge müssen im selben Commit entfallen**, sonst rot. Schlüssel: `datei::funktion::ordinal`. Achtung Ordinal-Rückverschiebung bei `_build_stage_trend` (`::2` → `::1`) |
| `touched_tests_gate.py` | Tests der berührten Dateien müssen grün bleiben |
| `test_naming_gate.py` | Testdatei nach Verhalten benennen, nie `test_issue_1727*` |
| LoC-Limit 250 | S5a brauchte 800 (670 Nachweis) für 5 Stellen — **Override ist absehbar, wird vom PO eingeholt** |

---

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` (Akzeptiert) | Ortstag statt Servertag; Verbot eines Zweitauflösers |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` (Vorgeschlagen) | Regel 3, s.o. |
| `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md` | Vorgängerscheibe, 10 ACs — Vorbild für Aufbau und Nachweisform |
| `docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md` | Muster „Tagesbestimmung in der Schleife" |
| `docs/specs/modules/fix_1726_ruhezeit_und_zaehler_ortszone.md` | `first_resolvable_tz()`, Mehrzonen-Wahl |
| `docs/context/fix-1697-ortstag-statt-servertag.md` | Warum ein halber Schnitt gefährlicher ist als keiner |

### 🔴 Nebenbefund: die ADR-0044-Restliste ist unvollständig

`docs/adr/0044-kalendertage-folgen-der-ortszeit.md:151-153` führt unter „Noch nicht umgesetzt"
nur `preview_service.py`, `api/routers/debug.py` und `tools/weather_validation.py`. **Keine**
der acht Fundstellen dieser Scheibe steht dort — obwohl fünf davon auf versendete Inhalte
wirken. Das ist die vierte unvollständige Aufzählung in diesem Epic (nach den drei aus #1726).
Die Liste wird mit dieser Scheibe mitgezogen.

---

## Risks & Considerations

- **Fundstelle 2 ändert den Test-Fallback-Pfad.** Im Mismatch-Fenster kann der Klemm-Zweig
  künftig greifen, wo er vorher nicht griff (und umgekehrt). Betrifft nur
  `allow_test_fallback=True`, also den Test-Versand — kein regulärer Scheduler-Pfad.
- **Fundstelle 4 hat einen zweiten Aufrufer in `preview_service.py:218`**, das laut Zuschnitt
  in eine spätere Scheibe gehört. Der Fix ist funktionsintern (`trip` liegt vor), der
  Vorschau-Pfad erbt ihn ohne eigene Änderung — kein Scheibenbruch, aber in der Spec zu nennen.
- **Fundstelle 5 kann `trip=None` bekommen** (Vorschau-Pfad, #1498) — der None-Zweig
  (`:2409-2413`) muss vor der Zonen-Auflösung greifen.
- **Fundstelle 7 schreibt Persistenz** (`paused_at` in `briefings/<id>.json`). Read-Modify-Write
  mit Merge, kein Replace.
- **Mehrzonen-Touren:** Restfehler = Zonendifferenz zweier benachbarter Etappen am Wechseltag.
  Unverändert bewusst offen (ADR-0044, PO-Entscheidung).

---

# Analysis

## Type

Bug — Verstoß gegen die akzeptierte ADR-0044. Keine offene Produktfrage.

## 🔴 Zwei eigene Zuschnitt-Entscheide sind der Nachmessung nicht standgehalten

Beide stammen aus der Kontextphase dieses Workflows, beide wurden vom `analysis-challenger`
und einer eigenen Codemessung gekippt:

1. **„Das Millisekunden-Rennen gilt für die ganze (b)-Lücke."** Falsch für die Fundstellen 4
   und 5 — dort liegt ein Wetterabruf mit Retry-Backoff dazwischen. Widerlegt durch den
   **eigenen, bereits schriftlich festgehaltenen Präzedenzfall** in
   `dispatch_orchestrator.py:157-163` („möglicherweise eine Mitternacht"). Details oben.
2. **„`send_one_compare_preset` kostet 67 Test-Aufrufstellen, also eigene Scheibe."** Die Zahl
   stimmt, die Schlussfolgerung nicht: sie gilt für eine **Signaturänderung**, die dieser Fix
   gar nicht braucht. Der `date.today()`-Zweig (`:366-370`) steht nur zufällig **vor** der
   Ortsauflösung (`location_ids` `:387`, `order_locations_by_ids(...)` `:399`); beide werden
   ohnehin immer geladen. Block nach oben ziehen, `first_resolvable_tz(locations)` anwenden —
   **null** berührte Aufrufstellen, externer Vertrag unverändert.

Gemeinsames Muster: aus einer plausiblen Struktur auf eine Kostengröße geschlossen, statt sie
zu messen. Beim ersten Mal gegen einen Präzedenzfall im eigenen Repo, beim zweiten Mal gegen
die Zeilenreihenfolge in der Funktion selbst.

## Technischer Ansatz

Ein Muster, neunmal angewandt — kein neuer Baustein, keine neue Abstraktion:

| Lage am Fundort | Vorgehen | Fundstellen |
|---|---|---|
| `trip` vorhanden, `now_utc` vom Aufrufer erreichbar | `now_utc` als Pflichtparameter, `trip_local_today(trip, now_utc)` | 1, 4, 5 |
| `trip` vorhanden, `now_utc` nur intern (vor jedem I/O) | `now_utc` **einmal** oben binden, dann `trip_local_today(trip, now_utc)` | 2 |
| Weder `trip` noch `now_utc` | Fertigen Tag vom Aufrufer hereinreichen | 3 |
| `now_utc` liegt ungenutzt am Aufrufort | Durchreichen, `trip_local_today(trip, now_utc)` | 6, 7 |
| Zone bereits aufgelöst im DTO | `local_dt(now_utc, request.trip_tz).date()` | 8 |
| Mehrere Orte, Zone auflösbar | Reihenfolge korrigieren, `first_resolvable_tz(locations)` | 7, 9 |

Fundstelle 2 bindet den Zeitpunkt, den 1, 4 und 5 dann als Parameter bekommen — **eine**
Zeitabfrage für den gesamten Briefing-Aufbau. Damit verschwindet auch der Fall „Mitternacht
während des Wetterabrufs", ohne dass `_send_trip_report_outcome` selbst die Signatur ändert.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_report_scheduler.py` | MODIFY | Fundstellen 1–5; `now_utc` einmal binden und an drei Helfer durchreichen; Aufruf von `briefing_target_day_is_current` (#6) |
| `src/services/alert_briefing_anchor.py` | MODIFY | #6 — Pflicht-`today` statt Systemuhr-Rückfall |
| `src/services/scheduler_dispatch_service.py` | MODIFY | #7 `now_utc`-Parameter; #9 Ortsauflösung vor den Zweig ziehen |
| `src/services/dispatch_orchestrator.py` | MODIFY | #7 — vorhandenes `now_utc` aus `pre_pass` durchreichen |
| `src/services/notification_service.py` | MODIFY | #8 — Ortstag aus `request.trip_tz` |
| `tests/test_output_timezone_guard.py` | MODIFY | Neun `KNOWN_VIOLATIONS`-Einträge entfernen |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | Restliste nachziehen (s. Nebenbefund oben) |
| ~20 Bestandstestdateien | MODIFY | 43 Aufrufstellen auf die neuen Signaturen, je eine Zeile |
| `tests/tdd/test_<verhalten>.py` | CREATE | Verhaltenstests aller neun Fundstellen |

## Scope Assessment

- **Produktivcode:** ~+70/−30
- **Bestandstests:** ~43 geänderte Zeilen
- **Neue Tests:** ~450–600 (S5a brauchte 670 für fünf Fundstellen; hier teilen sich 1/2/4/5
  eine Fixtur und einen `freeze_time`-Rahmen)
- **Gesamt: ~600–700 → LoC-Override auf 800 nötig**, vom PO einzuholen, sobald die Testfläche
  steht. Pro Fundstelle günstiger als S5a (~75 statt ~160 Zeilen).
- **Risiko: MEDIUM.** Fünf der neun Stellen wirken auf versendete Inhalte, aber jede Änderung
  ist lokal und ersetzt einen Tagesbegriff durch einen anderen — keine Strukturänderung, keine
  Persistenz-Migration.

## Risiken

- **Fundstelle 7 schreibt Persistenz** (`paused_at` in `briefings/<id>.json`) —
  Read-Modify-Write mit Merge, kein Replace.
- **Fundstelle 9 ändert die Anweisungsreihenfolge** in einer Versandfunktion. Der
  `ValueError` für fehlende Empfänger (`:389-393`) und der für unauflösbare Orte (`:400`)
  feuern dann in anderer Reihenfolge relativ zur Datumssetzung. Beides sind Fehlerpfade ohne
  Nebenwirkung; die Reihenfolge der beiden zueinander bleibt unverändert. In der Spec als
  ausdrückliche Invariante festzuhalten.
- **Ungezählt:** ob unter den 67 Aufrufstellen von `send_one_compare_preset` welche den
  Servertag im `target_date=None`-Pfad ausdrücklich behaupten. Bei mitteleuropäischen Fixturen
  fällt der Unterschied meist nicht an — vor der Umsetzung auszuzählen, nicht zu schätzen.
- **Fundstelle 5 kann `trip=None` bekommen** (Vorschau-Pfad, #1498) — der None-Zweig
  (`:2409-2413`) muss vor der Zonen-Auflösung greifen.

## Offene Punkte für die Spec

1. Zonenwahl für Fundstelle 7 (Preset mit mehreren Orten) — `first_resolvable_tz()`, dem
   #1726-Muster folgend. Keine PO-Frage.
2. Ob Fundstelle 8 den Tag aus `request.trip_tz` ableitet oder den bereits bekannten
   `target_date` durchgereicht bekommt (sauberer, aber ein Feld mehr im DTO).
3. Die (b)-Restlücke (Fundstellen 2, 8, 9 + `send_on_demand_report`) läuft als weitere
   S5-Scheibe im bestehenden Ticket, nicht als eigenes Issue — sie blockiert nichts und ist
   ohne den Kontext dieses Epics nicht verständlich.
