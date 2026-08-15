---
entity_id: fix_1851_alarm_tests_vorlaufsperre
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
workflow: fix-1851-alarm-zeitfenster-fixtures
version: "1.0"
tags: [issue-1851, tests, fixtures, alerts, briefing-vorlauf, adr-0009]
---

# Alarm-Zeitfenster-Tests: Vorbedingung „kein fälliges Briefing" herstellen

## Approval

- [ ] Approved

## Purpose

Drei Tests in `tests/unit/test_alarm_zeitfenster_ziel.py`
(`test_ac1_gewitter_17_uhr_am_tagesziel_wird_zugestellt`,
`test_ac2a_gewitter_1845_knapp_vor_fensterende_wird_zugestellt`,
`test_ac3_spaetankunft_2030_faellt_nicht_aus_der_ueberwachung`) schlagen
abhängig von der realen Wanduhr fehl (`assert []`, keine Mail zugestellt).
Ursache ist **kein** Produktdefekt, sondern eine fehlende Vorbedingung in der
Testfixture: die Alarm-Vorlaufsperre aus #1594 unterdrückt den Alarm
planmäßig, sobald für den Test-Trip zufällig ein Briefing fällig ist — die
Meldung wird dann korrekt ERSETZT statt verschluckt (ADR-0009), nur eben
nicht als eigenständiger Alarm zugestellt, was die Tests nicht erwarten.
Diese Spec beschreibt, wie die drei Tests (und der bislang aus dem falschen
Grund grüne Grenzfall `test_ac2b_…`) die Vorbedingung „für diesen Trip steht
kein Briefing an" **aktiv herstellen**, statt sie vom Zufall der Uhrzeit
abhängig zu machen.

## Source

- **File:** `tests/unit/test_alarm_zeitfenster_ziel.py`
- **Identifier:** `_trip()` (Zeile 113-150) — gemeinsamer Fixture-Konstruktor
  für alle zwölf Testfälle der Datei

**Ursachenkette (gemessen, s. `docs/context/fix-1851-alarm-zeitfenster-fixtures.md`,
Abschnitt „Analysis (Phase 2)"):**

1. `src/services/trip_alert.py:241` — `_is_briefing_imminent(trip, now_utc)`
   wird vor jedem Abruf gefragt; bei `True` bricht `check_and_send_alerts()`
   mit `Alert suppressed: briefing imminent for trip …` ab (Zeile 242-243).
2. `_is_briefing_imminent()` (`trip_alert.py:715-741`) ruft
   `check_briefing_imminent()` (`src/services/alert_gate.py:200`) mit dem
   Prädikat `trip_briefing_due_at` (`src/services/trip_report_scheduler.py:135`).
3. `trip_briefing_due_at()` ist wahr, wenn irgendwann in
   `[jetzt, jetzt + BRIEFING_VORLAUF_MINUTEN]` (60 min) ein geplantes
   Briefing fällig ist **und** noch nicht versucht wurde
   (`trip_report_scheduler.py:135-201`).
4. `_trip()` (`tests/unit/test_alarm_zeitfenster_ziel.py:141-143`) setzt ein
   aktives `TripReportConfig` mit den Vorgabezeiten `morning_time=07:00`,
   `evening_time=18:00` (Default, `src/app/models.py:1042-1043`) — je nach
   echter Wanduhr fällt der Testlauf in eines der beiden 3-Stunden-
   Nachholfenster (`NACHHOL_FENSTER_STUNDEN=3`,
   `trip_report_scheduler.py:106,188-189`) und der Alarm wird planmäßig
   unterdrückt.

**Produktivcode ist korrekt und bleibt unverändert.** Die drei Tests stammen
aus #1584 und wurden geschrieben, bevor die Sperre aus #1594 existierte; sie
sichern zu „Gewitter am Tagesziel ⇒ Alarm wird zugestellt", ohne die
Vorbedingung „und es steht kein Briefing an" herzustellen.

> **Schicht-Hinweis:** Ausschließlich `tests/unit/test_alarm_zeitfenster_ziel.py`.
> **Kein** Eingriff in `src/`, `api/`, `internal/`, `frontend/`, `cmd/` — die
> Sperre aus #1594 verhält sich korrekt und wird nicht angefasst (s. AC-5).

## Scope

### Gewählte Lösung: `report_config.enabled = False`

`trip_briefing_due_at()` prüft drei unabhängige, ODER-freie Aktiv-Filter, von
denen jeder allein genügt, das Prädikat dauerhaft falsch zu machen
(`trip_report_scheduler.py:167-178`, Docstring Zeile 153-156):
`trip.paused_at`, `report_config.enabled`, `report_config.paused_until`.

Gewählt wird **`report_config.enabled = False`** (Zeile 171:
`if rc.enabled is False: return False`), nicht `trip.paused_at` oder
`paused_until`. Begründung:

1. **Kein Nebeneffekt außerhalb der Briefing-Fälligkeit.** `report_config.enabled`
   wird im gesamten `src/`-Baum ausschließlich für die
   Briefing-Fälligkeitsprüfung gelesen (`trip_report_scheduler.py:171,891`,
   `app/loader.py:628-629,1608` — reine Persistenz/Anzeige). `trip.paused_at`
   dagegen bedeutet fachlich „der ganze Trip ist pausiert" und wird an
   anderer Stelle roundtrip-persistiert (`app/loader.py:1486-1487`) — eine
   unpassende Nebenbedeutung für einen Test, der ausdrücklich NUR das
   Briefing abschalten will, während der Alarmpfad weiter aktiv sein soll.
2. **Absicht ist lesbar.** `TripReportConfig(..., enabled=False)` liest sich
   im Testcode unmittelbar als „für diesen Trip ist kein Briefing geplant" —
   exakt die Vorbedingung, die hergestellt werden soll.
3. **`paused_until` wäre gleichwertig, aber unnötig komplexer** (verlangt
   einen Zeitstempel in der Zukunft statt eines Bool). Kein fachlicher Vorteil
   gegenüber `enabled=False` für diesen Zweck.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `tests/unit/test_alarm_zeitfenster_ziel.py` | MODIFY | `_trip()`: `report_config.enabled=False` setzen und Absicht kommentieren; `test_ac2b_…` unverändert lassen (besteht danach aus dem richtigen Grund, s. AC-4); neue Testfunktion für die Gegenprobe (AC-2) |
| Produktivcode (`src/`, `api/`, `internal/`, `frontend/`, `cmd/`) | — | **unverändert** (AC-5) |

### Estimated Changes

- Files: 1
- LoC: Produktiv +0/−0, Test ca. +25/−1

## Implementation Details

**1. `_trip()` (Zeile 141-143) ergänzen:**

```
trip.report_config = TripReportConfig(
    trip_id=trip_id, send_email=True, alert_on_changes=True,
    enabled=False,  # #1851: kein Briefing geplant -> Alarm ist die
                    # einzige Zustellform, unabhaengig von der Wanduhr
)
```

Damit ist `trip_briefing_due_at()` für jeden mit `_trip()` gebauten Trip zu
jedem `moment` `False` (Zeile 171 greift zuerst, vor jeder Zeitrechnung) —
`_is_briefing_imminent()` liefert nie mehr `True`, die Sperre kann die drei
betroffenen Tests nicht mehr treffen, unabhängig von der Wanduhr beim
Testlauf.

**2. `test_ac2b_gewitter_1915_knapp_nach_fensterende_bleibt_aus` bleibt
unverändert im Code**, profitiert aber automatisch von derselben
Fixture-Änderung (nutzt `_alarm_mails()` → `_trip()`). Sein
`assert not mails` ist danach aus dem fachlich richtigen Grund grün: das
Gewitter um 19:15 Ortszeit liegt außerhalb des Tagesfensters — nicht, weil
irgendein Alarm generell unterdrückt würde. Beleg dafür ist der Vergleich mit
`test_ac2a_…` (identische Fixture-Familie, Gewitter 18:45 **innerhalb** des
Fensters, erwartet `mails`) — beide Tests zusammen zeigen, dass die Fixture
zwischen „drin" und „draußen" unterscheidet, nicht pauschal unterdrückt
(s. AC-4).

**3. Neue Testfunktion für die Gegenprobe (AC-2):** baut zwei Varianten
desselben AC-1-Szenarios (Ankunft 13:18 Ortszeit, Gewitter 17:00 Ortszeit,
`ALPEN_LAT`/`ALPEN_LON`):

- **Variante A (unrepariert simuliert):** `report_config.enabled=True`
  (Ausgangszustand vor dieser Scheibe) UND zusätzlich `morning_time` auf die
  aktuelle Ortsstunde des Trips gesetzt — `stunde =
  trip_local_now(trip, datetime.now(timezone.utc)).hour`, dann
  `rc.morning_time = time(stunde, 0)`. Da `_slot_stunde()`
  (`trip_report_scheduler.py:123-132`) nur `.hour` liest und
  `trip_briefing_due_at()` das Nachholfenster `[stunde, stunde+3)` gegen die
  **Ortsstunde des Testlaufs selbst** prüft (Zeile 188-189), trifft dieses
  Fenster garantiert den Testlauf-Zeitpunkt — unabhängig davon, wann der Test
  tatsächlich läuft, weil die Stunde relativ zu `datetime.now()` berechnet
  wird, nicht fest verdrahtet ist. Das stellt „ein Briefing wäre unmittelbar
  fällig" **aktiv her**, ohne auf eine Tageszeit zu warten.
- **Variante B (repariert):** identischer Trip, aber `report_config.enabled=False`
  (die Fixture-Änderung dieser Scheibe).

Beide Varianten laufen über `_alarm_mails()`/`check_and_send_alerts()` mit
demselben Gewitter (17:00 Ortszeit). Erwartung: Variante A liefert **keine**
Mail (Beleg, dass die Vorlaufsperre für diese Konfiguration real greift —
nicht nur behauptet), Variante B liefert eine Mail (Beleg, dass die Scheibe
die Sperre für die Test-Fixtures tatsächlich neutralisiert).

## Beweiskette geschlossen (nachgemessen 2026-08-15)

Die Vorgabe-Briefingzeiten sind **07:00 und 18:00 Ortszeit**
(`src/app/models.py:1042-1043`), das Fälligkeitsfenster ist drei Stunden breit
(`NACHHOL_FENSTER_STUNDEN`, `src/services/trip_report_scheduler.py`). Damit
erklären sich **beide** Beobachtungen mit demselben Mechanismus:

| Lauf | Ortszeit (Europe/Vienna) | Briefing fällig? | Ergebnis |
|---|---|---|---|
| CI auf `main`, 2026-08-14 20:22 UTC | 22:22 | nein (Abendfenster 18:00–21:00 zu) | **grün** |
| CI auf PR #1853, 2026-08-15 05:29 UTC | 07:29 | ja (Morgenfenster 07:00–10:00 offen, nicht versucht) | **rot** |

Es gibt also keine unerklärte „Kippkante" mehr, die noch zu vermessen wäre.

## Acceptance Criteria

- **AC-1 (alle Fälle wanduhrunabhängig grün):** Given die drei betroffenen
  Testfälle (`test_ac1_…`, `test_ac2a_…`, `test_ac3_…`) nach der
  Fixture-Änderung dieser Scheibe / When
  `uv run pytest tests/unit/test_alarm_zeitfenster_ziel.py -v --allow-hosts=127.0.0.1,::1 -p no:randomly`
  läuft / Then sind alle 12 Testfälle der Datei grün, unabhängig von der
  realen Wanduhrzeit beim Lauf.
  - Test: kompletter Lauf der Datei; Assert Exit 0, keine `assert []`-Fehlschläge
    mehr in den drei genannten Funktionen. Da `report_config.enabled=False`
    die Fälligkeitsprüfung strukturell abschaltet (kein Zeitvergleich mehr
    beteiligt, Zeile 171 greift vor jeder Zeitrechnung), genügt EIN Lauf als
    Nachweis — es gibt keine Kippkante mehr, die zu einer bestimmten Uhrzeit
    erneut prüfbar wäre.

- **AC-2 (Gegenprobe — Sperre aktiv herstellen statt abwarten, wichtigster AC):**
  Given ein Testfall baut Variante A (`report_config.enabled=True`,
  `morning_time` auf die aktuelle Ortsstunde des Trips gesetzt — berechnet
  relativ zu `datetime.now()` im Testlauf, s. Implementation Details Punkt 3)
  und Variante B (`report_config.enabled=False`) desselben AC-1-Szenarios
  (Ankunft 13:18 Ortszeit, Gewitter 17:00 Ortszeit) / When beide Varianten
  über `_alarm_mails()` laufen / Then bleibt Variante A ohne zugestellte Mail
  (die Vorlaufsperre greift nachweislich — der Mechanismus ist real, nicht
  nur vermutet) und Variante B liefert eine zugestellte Mail (der Fix
  neutralisiert die Sperre für die Test-Fixtures tatsächlich) — beides ohne
  auf eine bestimmte Tageszeit zu warten oder eine Test-Uhr zu stellen.
  - Test: neue Testfunktion mit beiden Varianten; `assert not mails_a`,
    `assert mails_b`. Kein `freeze_time`, keine Wartezeit — die
    Briefingzeit von Variante A wird aus der Ortsstunde zum Ausführungszeitpunkt
    selbst abgeleitet und ist damit bei jedem Lauf diskriminierend.

- **AC-3 (Zusicherung aus #1584 bleibt inhaltlich erhalten):** Given die vier
  Testfälle `test_ac1_…`, `test_ac2a_…`, `test_ac2b_…`, `test_ac3_…` nach
  dieser Scheibe / When sie ausgeführt werden / Then prüfen sie unverändert
  dieselbe fachliche Aussage wie in #1584 spezifiziert — Gewitter
  **innerhalb** des Tagesfensters ⇒ Alarm wird zugestellt, Gewitter
  **außerhalb** ⇒ kein Alarm — nur mit korrigierter Vorbedingung, nicht mit
  abgeschwächter Zusicherung.
  - Test: Diff-Review der vier `assert`-Zeilen gegen den Stand vor dieser
    Scheibe (`git diff`); Assert die Assertions selbst (nicht nur die
    Fixture) sind unverändert bzw. semantisch gleichwertig.

- **AC-4 (`test_ac2b` besteht aus dem richtigen Grund):** Given
  `test_ac2b_gewitter_1915_knapp_nach_fensterende_bleibt_aus` und
  `test_ac2a_gewitter_1845_knapp_vor_fensterende_wird_zugestellt` nutzen
  nach dieser Scheibe dieselbe gehärtete Fixture (`_trip()` mit
  `enabled=False`) / When beide Tests im selben Lauf ausgeführt werden /
  Then liefert `test_ac2a_…` eine zugestellte Mail (Gewitter 18:45 Ortszeit,
  innerhalb) und `test_ac2b_…` liefert keine (Gewitter 19:15 Ortszeit,
  außerhalb) — das Paar beweist, dass `test_ac2b_…` wegen der
  Tagesfenster-Grenze grün ist, nicht weil unter der gehärteten Fixture
  generell keine Alarme mehr entstehen.
  - Test: beide Tests im selben `pytest`-Lauf; Assert `test_ac2a_…` grün UND
    `test_ac2b_…` grün. Wären beide aus „genereller Unterdrückung" grün,
    müsste `test_ac2a_…` (das eine Mail erwartet) rot sein — sein Grün-Status
    ist der Beleg.

- **AC-5 (Nicht-Wirkung, Produktivcode unangetastet):** Given der
  vollständige Diff dieser Scheibe / When
  `git diff --stat origin/main...HEAD -- src/ api/ internal/ frontend/ cmd/`
  ausgeführt wird / Then ist die Ausgabe leer — die Scheibe belegt damit
  selbst, dass die Sperre aus #1594 unverändert bleibt und nur die
  Testfixture angepasst wurde.
  - Test: `git diff --stat` gegen den Merge-Basis-Commit über exakt diese
    fünf Verzeichnisse; Assert leere Ausgabe (manueller Nachweis im PR, kein
    neuer Pytest-Test nötig — repo-strukturelle Prüfung).

## Test Plan

### Automated Tests (TDD RED)

- [ ] AC-2 (Gegenprobe): Neue Testfunktion `test_gegenprobe_vorlaufsperre_wird_durch_fix_neutralisiert` (Arbeitsname) — Variante A rot vor dem Fix (Alarm bleibt aus trotz Gewitter im Fenster, weil `enabled=True` + fällige Briefingzeit), Variante B grün nach dem Fix.
- [ ] AC-1/AC-3/AC-4: Die drei bestehenden roten Tests werden durch die Fixture-Änderung grün, ohne dass ihre `assert`-Aussagen sich ändern; `test_ac2b_…` bleibt unverändert im Code und wird im selben Lauf gegen `test_ac2a_…` als Paar geprüft.

## Known Limitations

- **Die Sperre selbst (#1594) wird nicht angefasst.** Sie verhält sich
  korrekt (ADR-0009: ersetzen, nicht verschlucken) — diese Scheibe ändert
  nichts an ihrem Verhalten, nur an der Testvorbedingung.
- **Kein neuer Wächter gegen „Verhaltensänderung im Alarmpfad kippt
  bestehende Alarm-Tests".** Der Nebenbefund aus der Analyse — die eigene
  CI-Ampel von #1594 lief abends und sah die Kippung der drei Tests nicht,
  weil der Effekt nur innerhalb der Briefing-Vorlauffenster sichtbar wird —
  ist damit **nicht behoben**, sondern nur benannt. Gehört in die
  Nebenbefund-Sammlung (#1199), nicht in diese Scheibe.
- **Andere Testdateien der Wanduhr-Familie (#1709) bleiben unberührt.** Nur
  `tests/unit/test_alarm_zeitfenster_ziel.py` ist Gegenstand dieser Scheibe.

## Nicht in dieser Scheibe

- Kein Eingriff in `src/services/trip_alert.py`, `alert_gate.py` oder
  `trip_report_scheduler.py`.
- Kein neues Gate/keine neue Dauerregel gegen zukünftige Kollisionen
  zwischen Alarm-Zeitsteuerungs-Änderungen und bestehenden Alarm-Tests.
- Keine Sanierung weiterer, möglicherweise ähnlich betroffener Testdateien
  außerhalb der genannten Datei — nicht durchsucht, nicht Teil dieser Spec.

## Changelog

- 2026-08-15: Initial spec created
