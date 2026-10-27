# Context: feat-2050-s3b-budget-und-unterdrueckungsgrund

Issue #2050, Scheibe **S3b**. Erstellt 2026-08-22 auf `origin/main` = `68927864`.

## Request Summary

Zwei Szenarien aus #2050, beide mit Produktivcode:

- **Szenario 7 / Anforderung D-3** — „Budget vormittags verbraucht, nachmittags akute
  Gewitterlage → akute Lage kommt durch." Das Tagesbudget darf bei der schwersten Lage nicht
  verhungern.
- **Szenario 10 / Anforderung D-2** — „Jede Unterdrückung hat einen benannten Grund samt der
  Werte, die zur Entscheidung führten." Der Teil „kein Schwall um 6:00" ist strukturell bereits
  erfüllt (es gibt keine Warteschlange); offen ist allein der benannte Grund.

**Nicht in dieser Scheibe:** Szenario 4 (läuft als S3a in einer Parallelsession, reine
Wächterarbeit) und die Sperrzeit-Überholung im Abweichungs-Zweig (neu als **S3c** angelegt,
läuft *nach* dieser Scheibe — dieselbe Gate-Kette).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_daily_limit.py` | Kern von Sz 7. `is_allowed` (:92-107), `increment` (:110-132), `_FORECAST_CHANGE_RESERVE` (:89) |
| `src/services/alert_gate.py` | Gate-Kette. `check_nowcast_gate` (:140-184), `check_official_alert_gate` (:187-240), `check_briefing_imminent` (:282-383), `radar_overtakes_cooldown` (:421-446), `check_event_identity_gate` (:679-763) |
| `src/services/alert_log.py` | Kern von Sz 10. `append_suppressed_entry` (:510-602), Gründe-Konstanten (:52-68), Lücken-Doku **O3** (:545-548), `read_undelivered` (:659+) |
| `src/services/trip_alert.py` | Beide Szenarien, Trip-Fläche. Änderungsalarm-Gates (:343-369), `_protokolliere_radar_unterdrueckung` (:1251-1273), nachgeholtes Tageslimit nach Sperrzeit-Durchbruch (:1509-1547), amtlicher Pfad (:2193-2206) |
| `src/services/compare_alert.py` | Änderungsalarm Ortsvergleich — vier unprotokollierte Gates (:151-212), `is_allowed` (:164) |
| `src/services/compare_radar_alert.py` | Radar Ortsvergleich, protokolliert bereits (:206, :255) |
| `src/services/compare_official_alert.py` | Amtlich Ortsvergleich (:149-157 stumm, :230 protokolliert) |
| `src/services/alert_urgency.py` | Vorhandene Schwere-Skala LOW/MODERATE/HIGH, `exceeds()`, `highest_urgency()` |
| `tests/helpers/alarm_pruefstrecke.py` | Die S1-Prüfstrecke — Einstieg für beide Szenarien |

## Existing Patterns

**Prüfen und Buchen sind getrennt.** `is_allowed` ist rein lesend; `increment` läuft
ausschließlich *nach* erfolgreicher Zustellung (`trip_alert.py:523`, `:2335`,
`compare_alert.py:371`, `compare_official_alert.py:318`, `alert_gate.record_nowcast_sent:406`).
Keine Stelle bucht ohne vorher zu prüfen. Diese Symmetrie ist mehrfach kommentiert und muss
erhalten bleiben.

**Der Zähler läuft je Zeitzone, nicht global** (#1726) — ein bewusster Preis, im Docstring
begründet.

**`gate_reason` ist Pflichtfeld mit lautem Scheitern** (`alert_log.py:563-569`): leer ⇒
`ValueError`, kein stiller Fallback. Grund: `_missed_channels()` deutet einen leeren Grund beim
Lesen sonst zu `REASON_DELIVERY_FAILED` um. Gute Grundlage für D-2.

**Protokoll-Schreiben ist fail-soft** — alle sieben Aufrufstellen liegen in
`try/except Exception` (Muster `fix_1479`): ein kaputter Eintrag darf den Stapellauf über alle
Nutzer nicht reißen.

**Zwei bestehende Eskalations-Begriffe, keiner am Tageslimit angeschlossen:**

| Begriff | Wo | Kriterium | Überholt heute |
|---|---|---|---|
| `radar_overtakes_cooldown` | `alert_gate.py:421-446` (#2065) | `menge >= basis * 2.0` **und** `menge >= 2.0 mm` | nur die **Sperrzeit** |
| `quantitative_escalation` / `alert_urgency.exceeds` | `alert_gate.py:679-763` (#2018) | Bool vom Aufrufer **oder** Stufensprung LOW→MODERATE→HIGH | nur die **Entdopplung** |

Die Stufenskala sättigt bei ca. 4 mm/h — im Code selbst vermerkt (`alert_gate.py:717-720`:
„eine Verdreifachung von 11 auf 30 mm/h ist zweimal HIGH … die Verschärfung ist an dieser
Stelle strukturell unsichtbar"). Ein Kriterium für Sz 7 darf sich darauf nicht allein stützen.

## Ist-Stand Szenario 7 — das Tageslimit

Sieben `is_allowed`-Aufrufstellen, davon sechs im Alarmversand:

| Stelle | Zweig · Fläche | `reason` | Bei `False` |
|---|---|---|---|
| `trip_alert.py:365` | Änderung · Trip | `forecast_change` | stiller `return False` |
| `trip_alert.py:1537` | Radar · Trip (nach Sperrzeit-Durchbruch) | `nowcast` | `continue` **+ Protokoll** |
| `alert_gate.py:178` | Radar · beide (geteilt) | `nowcast` | `GateResult` — Aufrufer protokolliert |
| `alert_gate.py:234` | amtlich · beide (geteilt) | `None` (volles Limit) | `GateResult` — Aufrufer **schweigt** (E3) |
| `compare_alert.py:164` | Änderung · Compare | `forecast_change` | stiller `continue` |
| `trip_report_scheduler.py:1823` | Briefing-Kurzfristhinweis | `nowcast` | rein lesend, bucht nie — **außerhalb des Alarmversands** |

**Der Kollisionspunkt:** `trip_alert.py:1509-1547` prüft das Tageslimit nach dem
Sperrzeit-Durchbruch aus #2065 ausdrücklich **erneut** und blockt hart. Kommentar dort: „Die
Tages-Obergrenze wurde wegen des Abbruchs an der Sperrzeit nie geprüft … der Durchbruch darf
sie nicht stillschweigend mit-überspringen." Festgeschrieben durch
`tests/tdd/test_radar_cooldown_overtake.py::test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch`
(:492-552).

Szenario 7 verlangt das Gegenteil. Dieser Test wird also **bewusst abgelöst**, nicht
versehentlich gebrochen — die Ablösung gehört als eigenes AC in die Spec.

## Ist-Stand Szenario 10 — der benannte Grund

Protokolliert wird heute **nur im Radar-/Nowcast-Zweig**, dort aber gut: sieben Aufrufstellen
von `append_suppressed_entry`, teils mit dem vollen E1-Wertesatz aus S6.

Unprotokollierte Unterdrückungen (13 Stellen):

| Stelle | Gate | Zweig · Fläche | Statt Protokoll |
|---|---|---|---|
| `trip_alert.py:343` | Ruhezeit | Änderung · Trip | `logger.debug` |
| `trip_alert.py:353` | Briefing-Vorlauf | Änderung · Trip | `logger.debug` *(Absicht, s.u.)* |
| `trip_alert.py:358` | Sperrzeit | Änderung · Trip | `logger.debug` |
| `trip_alert.py:362` | Tageslimit | Änderung · Trip | `logger.debug` |
| `trip_alert.py:1632` | Doppel-Alarm-Guard (#818) | Radar · Trip | `logger.debug` |
| `trip_alert.py:2193` | Ruhezeit \| Tageslimit | amtlich · Trip | **gar nichts** |
| `trip_alert.py:2204` | Briefing-Vorlauf | amtlich · Trip | `logger.debug` *(Absicht)* |
| `compare_alert.py:151` | Sperrzeit | Änderung · Compare | `logger.debug` |
| `compare_alert.py:164` | Tageslimit | Änderung · Compare | `logger.debug` |
| `compare_alert.py:189` | Ruhezeit | Änderung · Compare | `logger.debug` |
| `compare_alert.py:204` | Briefing-Vorlauf | Änderung · Compare | `logger.debug` *(Absicht)* |
| `compare_official_alert.py:149` | Ruhezeit \| Tageslimit | amtlich · Compare | **gar nichts** |
| `compare_official_alert.py:165` | Briefing-Vorlauf | amtlich · Compare | `logger.debug` *(Absicht)* |

**Nicht als Lücke zu werten** (jeweils an Ort und Stelle begründet): „nicht alarmwürdig"
(`trip_alert.py:1495-1507`), kein Kanal konfiguriert (Nutzerentscheidung), Horizont-/
Segment-Guards vor jeder Gate-Prüfung — dort steht noch gar kein Alarm zur Debatte.

Der **Briefing-Vorlauf** ist ein Sonderfall: Sein Protokoll-Verzicht ist keine Lücke, sondern
eine mit #1233 und ADR-0009 verknüpfte Zusicherung („ersetzt, nicht verschluckt" — die Meldung
geht gleich im Briefing raus, aus Nutzersicht schweigt nichts). Eine Einbeziehung wäre ein
bewusster Bruch mit dem Bestand und braucht ein eigenes AC, keinen stillen Mitnahmeeffekt.

Zwei Lücken sind bereits **im Code als offen dokumentiert**: **O3** (`alert_log.py:545-548`) und
**E3** (`alert_gate.py:224-226`). Änderungsalarm und amtlicher Zweig haben damit strukturell
0 % D-2-Abdeckung — nicht zufällig lückenhaft, sondern per Geltungsbereich „Nowcast-only".

## Die S1-Prüfstrecke — so wird gemessen

`tests/helpers/alarm_pruefstrecke.py`, Klasse `AlarmPruefstrecke(user_id, settings, throttle_hours)`,
Einstieg `.lauf(at=…, zweig="deviation"|"official"|"radar", trip=…, …)` → Lauf-Objekt mit
`triggered_count` und den vier Kanaltexten. Pro Lauf ein frischer `TripAlertService`; die
Kontinuität kommt vom Datenträger, die Uhr über `freeze_time(at)`.

**Vorzustand wird nicht über die Prüfstrecke gesetzt, sondern vor dem Lauf über die produktiven
Schreibfunktionen** — nie gemockt:

| Zustand | Schreibweg |
|---|---|
| Sperrzeit | `ThrottleStore(uid).record("trip", trip.id, <zeitpunkt>)` |
| Tageszähler | `alert_daily_limit.increment(user_id, now, zone)` |
| Briefing-Anker | `alert_briefing_anchor.record_briefing_sent(...)` |
| letzte Meldung | `alert_gate.record_event_identity(...)` |

Vorbild für den Testaufbau: `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` (S2b, 20 ACs)
mit `_uid()`-Fixture, `_aufraeumen` und `_lauf()`-Wrapper. Weitere Szenario-Dateien:
`test_alarm_szenario_briefing_ueberholung_zeitreihe.py`, `test_alarm_szenario_gewitter_vorverlegung.py`.

## Dependencies

- **Upstream:** `alert_urgency` (Schwere-Skala), `utils/timezone` (Ortstag/Zone),
  `get_data_dir(user_id)` (Mandantentrennung aller vier Zustandsspeicher)
- **Downstream:** `alert_briefing_anchor.undelivered_since_last_briefing()` liest über
  `read_undelivered()` mit — neue `gate_reason`-Werte tauchen dort auf. `_missed_channels()`
  filtert nur `channel_disabled` heraus, **alle anderen Gründe zählen als Vorfall**. Ein neu
  protokollierter Grund verändert also, was im nächsten Briefing als „nicht zugestellt"
  erscheint. Das ist der wichtigste Nebeneffekt dieser Scheibe.
- **Go-Seite:** `internal/store/log.go:48-58` liest nur sechs Felder aus `entries` und nie
  `not_delivered` (D4) — Protokoll-Erweiterungen bleiben dort unsichtbar, Änderungen müssen
  additiv sein.

## Existing Specs

- `docs/specs/modules/` — Alarm-Module (Gate, Tageslimit, Protokoll)
- Vorgänger-Kontexte: `docs/context/feat-2050-s1-pruefstrecke.md`,
  `fix-2050-s2b-laufendes-ereignis.md`, `feat-2050-s6-protokoll-vorwarnzeit.md`,
  `fix-2065-verschaerfung-durchbricht-sperrzeit.md`
- ADR-0009 (Briefing ersetzt Alarm), #1233 (Ruhezeit/Vorlauf schweigen protokollfrei)

## Risks & Considerations

1. **Sz 7 kehrt eine frische, getestete Entscheidung um.** #2065 ist wenige Tage live. Die
   Ablösung von `test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch` muss als AC benannt
   sein, sonst liest sie sich später wie eine Regression.
2. **Ein dritter Eskalations-Begriff wäre ein Fehler.** Es gibt bereits zwei nicht miteinander
   verdrahtete. Sz 7 sollte einen der beiden weiterverwenden statt einen neuen zu erfinden —
   mit dem Wissen, dass die Stufenskala bei 4 mm/h sättigt.
3. **Das Budget darf nicht löchrig werden.** Eine Ausnahme, die zu leicht greift, hebelt das
   Tageslimit faktisch aus. Es braucht eine Obergrenze für die Ausnahme selbst (wie oft pro Tag
   darf sie greifen?), sonst ist D-3 gegen D-2/C-1 erkauft.
4. **Reichweite ist die zentrale offene Frage beider Szenarien** — Nowcast-only (heutiger
   Geltungsbereich) oder alle drei Zweige? Das entscheidet über Umfang und über den Bruch mit
   O3/E3. Gehört als benannte Alternative in die Spec, nicht in eine stille Annahme.
5. **Nebeneffekt aufs Briefing:** neue Unterdrückungsgründe erscheinen über
   `undelivered_since_last_briefing()` im nächsten Briefing als Vorfall. Wird das nicht
   mitgedacht, wächst der „nicht zugestellt"-Block sprunghaft.
6. **LoC-Limit.** Beide Szenarien zusammen sprengen 250 LoC voraussichtlich; Override auf 500
   ist vorzusehen.
7. **Parallelsession.** `2050-s3a` fasst nur Testdateien an (Sz 4/9/11), kein Produktivcode —
   Kollisionsfreiheit bestätigt.

---

## Analysis

### Type

**Feature** — zwei neue Zusicherungen an bestehendem Verhalten. Kein Bugfix: beide heutigen
Verhaltensweisen sind absichtlich so gebaut und dokumentiert.

### Entscheidung 1 — Der Eskalations-Begriff für Szenario 7

**`alert_urgency`-Stufenskala (LOW/MODERATE/HIGH), nicht `radar_overtakes_cooldown`.**

`radar_overtakes_cooldown` lebt laut eigenem Docstring (`alert_gate.py:436-439`) bewusst NUR im
Trip-Radar-Pfad und vergleicht gegen die zuletzt gemeldete `precip_mm` aus dem `ThrottleStore` —
eine Vergleichsbasis, die es im amtlichen und im Änderungs-Zweig gar nicht gibt.

`alert_urgency` ist dagegen in allen drei Zweigen bereits ableitbar — `urgency_from_official_level()`
(amtliche Stufen 1-4), `urgency_from_radar()`, `urgency_from_changes()` — und ist dasselbe
Vokabular, das `check_event_identity_gate` schon für die Entdopplung benutzt. Ein dritter Begriff
wäre der im Risiko-Abschnitt benannte Fehler.

**Zur bekannten Sättigung bei ~4 mm/h:** Sie schadet hier weniger als bei der Entdopplung, weil
die Vergleichsbasis eine andere ist — nicht „die letzte Meldung", sondern **die höchste heute in
dieser Zone bereits verschickte Stufe**. Der legitime Fall lautet damit „heute ging nichts über
MODERATE hinaus, jetzt ist es HIGH". `urgency_from_radar()` hebt ein Gewitter (`is_convective`)
unabhängig von der Regenmenge sofort auf HIGH — genau die „akute Gewitterlage" aus Szenario 7.
Die Restlücke (zweites, noch schwereres HIGH) fängt der Deckel aus Entscheidung 2, nicht die
Stufenlogik.

### Entscheidung 2 — Das Budget darf nicht löchrig werden

Zwei **UND**-verknüpfte Bedingungen:

1. Aktuelle Stufe **übersteigt** die höchste heute in dieser Zone verschickte Stufe (`exceeds()`)
2. Die Ausnahme selbst ist gedeckelt: **ein Durchbruch pro Tag und Zone**

Beides additiv in der vorhandenen `alert_daily_count.json` — kein neuer Speicher. Sie hat bereits
exakt die richtige Lebensdauer (Reset am Ortstag, Merge auf Zonenebene, #1726):

```
{"zones": {"<tz>": {"date": …, "count": N,
                    "max_urgency_sent": "MODERATE", "escalation_breakthroughs": 0}}}
```

`is_allowed`/`load` bleiben rein lesend; die neuen Felder schreibt ausschließlich `increment()` —
**nach** erfolgreicher Zustellung, damit die bestehende Prüfen/Buchen-Symmetrie erhalten bleibt.
Sonst bucht ein abgewiesener Lauf eine Eskalation, die nie stattfand.

⚠️ `alert_daily_limit.py` ist damit schema-relevant: Read-Modify-Write mit Merge, **nie Replace**.

### Entscheidung 3 — Reichweite

| Szenario | Reichweite | Begründung |
|---|---|---|
| **Sz 7** Budget-Durchbruch | **nur Nowcast/Radar**, dort aber Trip **und** Compare | Die PO-Formulierung beschreibt eine sich entwickelnde Live-Lage, nicht eine Vorhersage-Revision. `check_nowcast_gate` ist bereits der geteilte Baustein für beide Flächen — ein optionaler `escalation`-Parameter dort erreicht beide ohne Mehraufwand. Amtlich/Änderung haben heute **keine** Vergleichsbasis „was ging heute schon raus"; die müsste erst geschaffen werden. Dieselbe konservative Grenze zog #2065 bereits. |
| **Sz 10** benannter Grund | **vollständig** — Änderung **und** amtlich, Trip **und** Compare | D-2 sagt „jede Unterdrückung". Eine halbe Abdeckung wäre ein Flickenteppich; die 9 echten Lücken sind mechanisch gleichartig. |
| **Briefing-Vorlauf** (4 Stellen) | **bleibt außen vor** | Bestandsschutz #1233 / ADR-0009: „ersetzt, nicht verschluckt". `alert_gate.py:329-335` führt „kein `alert_log`-Eintrag" als *Eigenschaft*, nicht als Lücke. Aus Nutzersicht schweigt dort nichts — die Meldung kommt im Briefing. |

**Vorgemerkt für eine Folge-Scheibe:** Sz 7 für den amtlichen und den Änderungs-Zweig. Die
`max_urgency_sent`-Struktur aus dieser Scheibe wäre dort wiederverwendbar.

### Entscheidung 4 — ADR-Nachtrag ist Pflicht

`docs/adr/0021-shared-deviation-alert-engine.md:199-203` hält ausdrücklich fest: „der amtliche
Pfad protokolliert dafür weiterhin nichts" (Ruhezeit/Tageslimit). Szenario 10 weicht davon ab.
Nach der Projektregel („Abweichung ⇒ neues ADR, Status *Abgelöst durch*") braucht diese Scheibe
einen **ADR-Nachtrag zu ADR-0021** — sonst wird eine dokumentierte Entscheidung still
rückgängig gemacht. Gleiches gilt auf Spec-Ebene für zwei ACs (s. Spec-Drift).

### Spec-Drift — was bewusst abgelöst wird

| Spec | AC | Sagt heute | Wird |
|---|---|---|---|
| `fix_2065_verschaerfung_ueberholt_sperre.md` | **AC-7** (:205-212) | erschöpftes Budget stoppt den Sperrzeit-Durchbruch | abgelöst, in drei Nachfolge-ACs aufgelöst |
| `alert_daily_limit.md` | **AC-1/AC-2** (:117-121) | bei erreichtem Limit harte Unterdrückung, kein Protokolleintrag | abgelöst für den Eskalationsfall |
| `fix_2065_…md` | **AC-6** (:199-203) | Ruhezeit bleibt bei jeder Verschärfung unbrechbar | **unberührt** — PO-Ablehnung #1955 gilt weiter |
| ADR-0021 | :199-203 | amtlicher Pfad protokolliert nicht | Nachtrag nötig |

### Ablösung des #2065-Tests — drei statt einem

`test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch` (:492-552) wird **umgeschrieben, nicht
gelöscht**, damit die Ablösung nicht „Schutz entfernt" bedeutet:

1. **`…stoppt_ohne_eskalation`** — der alte Test mit einer Rate *unter* der Eskalationsschwelle
   (nicht-konvektiv): normales Wachstum bricht das Budget weiterhin **nicht**
2. **`…echte_eskalation_durchbricht_erschoepftes_budget`** — konvektiv/HIGH, während heute nur
   LOW/MODERATE verschickt wurde ⇒ Alarm geht raus
3. **`…eskalationsausnahme_hat_eigene_obergrenze`** — Deckel erreicht, zweite, noch schwerere
   Eskalation ⇒ bleibt still, Grund `daily_limit`

### Der Briefing-Nebeneffekt — entschärft

Neue Unterdrückungsgründe erscheinen im „nicht zugestellt"-Block der Briefing-**E-Mail**
(`renderers/email/undelivered_hint.py`, eingebunden in `html`/`plain`/`compact`/`compare_html`/
`comparison`). Drei Bremsen greifen bereits:

1. Zeitfilter `since=last_briefing_at(...)` (`alert_log.py:701`)
2. Entdopplung `DEDUP_WINDOW = 2 min` (`alert_log.py:613`)
3. Gruppierung identischer 5-Tupel zu einer Zeile mit `(n×)` plus `MAX_LINES_PER_BLOCK = 5`
   je Block (`undelivered_hint.py:129-142`, :38), Rest als „… und N weitere"

20 unterdrückte Alarme werden damit zu **einer** Zeile `(20×)` oder höchstens 5 Zeilen plus
Sammelhinweis — nie 20 Zeilen. Die deutschen Beschriftungen für `quiet_hours`, `daily_limit` und
`cooldown` liegen in `_REASON_LABELS`/`_REASON_BLOCK` (:48-70) bereits fertig, obwohl heute kein
Änderungsalarm sie je setzt: **der Renderer braucht keine Änderung.**

**Kurznachrichten sind nicht betroffen** — kein `undelivered`-Bezug in `renderers/sms/` oder
`renderers/telegram*`; `feat_1461_s3b1_briefing_sichtbarkeit.md` AC-10 sichert sogar
Zeichengleichheit zu. Trotzdem braucht der Nebeneffekt einen **eigenen Test auf
`undelivered_since_last_briefing()`**, nicht nur auf den Schreibpfad.

Es gibt **keinen** Weg, innerhalb von `alert_log.json` still zu protokollieren — `read_undelivered()`
liest beide Top-Level-Listen. Wer stillschweigen will, nutzt `logger.debug` oder eine eigene
Diagnose-Spur (Muster: `briefing_dispatch_failures.jsonl`).

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/alert_daily_limit.py` | MODIFY | Schema additiv um `max_urgency_sent` + `escalation_breakthroughs`; `increment()` schreibt sie fort; Durchbruchs-Prüfung |
| `src/services/alert_gate.py` | MODIFY | `check_nowcast_gate` um optionalen Eskalations-Parameter |
| `src/services/trip_alert.py` | MODIFY | Sz 7: Umbau :1509-1548. Sz 10: 5 Protokoll-Stellen (:343, :358, :362, :1632, :2193) |
| `src/services/compare_alert.py` | MODIFY | Sz 10: 3 Protokoll-Stellen (:151, :164, :189) |
| `src/services/compare_official_alert.py` | MODIFY | Sz 10: 1 Protokoll-Stelle (:149) |
| `tests/tdd/test_alarm_szenario_budget_und_grund.py` | CREATE | Szenario-Tests über die S1-Prüfstrecke |
| `tests/tdd/test_radar_cooldown_overtake.py` | MODIFY | `test_ac7_…` in drei Nachfolge-Tests aufgelöst |
| `docs/adr/0021-shared-deviation-alert-engine.md` | MODIFY | Nachtrag: amtlicher Pfad protokolliert künftig |
| `docs/specs/modules/alert_daily_limit.md`, `fix_2065_…md` | MODIFY | abgelöste ACs als abgelöst kennzeichnen |

### Scope Assessment

- Dateien: 9 (5 Produktivcode, 2 Test, 2 Doku)
- Geschätzte LoC: **+250 bis +350** — Sz 10 ≈ 90-130 (9 Stellen à 10-15), Sz 7 ≈ 65-90, Tests der Rest
- **LoC-Override auf 500 nötig**
- Risiko: **HIGH**

### Risiken

1. **`trip_alert.py:1509-1548`** — genau der Block, den #2065 gebaut hat, wird in sein Gegenteil
   verkehrt. Ein Fehler reißt den Alarmflut-Schutz nach dem Sperrzeit-Durchbruch komplett auf,
   nicht nur für den Eskalationsfall.
2. **`alert_daily_limit.py:110-132`** — Schema-Erweiterung an einer Datei, die **jeden** Nutzer
   beim Alarmversand berührt. Ein Read-Modify-Write-Fehler korrumpiert den Tageszähler
   mandantenweit.
3. **`alert_log.py:563-569`** — `gate_reason` scheitert laut bei leerem Wert. Jede der 9 neuen
   Aufrufstellen muss garantiert einen nicht-leeren Grund liefern. Das `try/except` federt ab,
   aber dann bleibt der Alarm für diesen Nutzer in diesem Lauf aus — ein stiller Fehlschlag
   genau der Art, die #2073 schon einmal gefangen hat.

### Reihenfolge

**Szenario 10 zuerst, Szenario 7 danach.** Sz 10 ist mechanisch und risikoarm — keine
Gate-Entscheidung ändert sich, nur Zusatz-Protokollierung — und ergibt einen grünen
Zwischenstand als Rückzugspunkt. Sz 7 baut darauf auf: sein negativer Ausgang (Eskalation
erkannt, aber Deckel erreicht) braucht ohnehin einen Protokolleintrag mit Grund `daily_limit`,
den Sz 10 an derselben Stelle einführt.

### Messbarkeit auf Staging

| Baustein | Nachweis |
|---|---|
| Sz 10, alle 9 Protokoll-Stellen | **voll staging-messbar**, S6-Rezept: echten unterdrückten Lauf auslösen, dann `/home/hem/gregor_zwanzig_staging/data/users/<id>/alert_log.json` → `not_delivered[].channels_not_sent[].reason` lesen |
| Briefing-Nebeneffekt | **staging-messbar** über `briefing_mail_validator.py` gegen eine echte Briefing-Mail im Test-Postfach |
| Sz 7, Zähler und Deckel | **staging-messbar**: `alert_daily_count.json` vorbelegen, Zählerstand vor/nach einem echten Lauf lesen |
| Sz 7, **die genaue Eskalationsschwelle** | **nur im Kern-Test**, falls der Staging-Radar keine kontrollierte Einspeisung erlaubt. Dann als SKIP ehrlich buchen — `alert-preview` stubbt Stundenreihe und Gate-Kette und beweist hier **nichts** |
| Ablösung `test_ac7_…` | nur Kern-Test, reine Prüfstrecken-Logik |

### Open Questions

- [ ] **Reichweite Sz 7** — Nowcast-only ist meine begründete Empfehlung; „akute Gewitterlage"
      ließe sich auch als „inklusive amtlicher Warnung" lesen. Wird mit den ACs vorgelegt.
