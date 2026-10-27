# Context: fix-2065-verschaerfung-durchbricht-sperrzeit

Erhoben am 2026-08-22 fuer Issue #2065. Alle Zeilenangaben gegen `origin/main` @ `5e92e053`.

## Request Summary

Eine sich deutlich verschaerfende Wetterlage erreicht den Nutzer nicht, weil die Sperrzeit
des vorangegangenen Alarms sie aufhaelt. Das verletzt Anforderung **A-3** aus #2050
(„Eine Verschaerfung ueberholt jede Sperre") und ist dort **Szenario 4**.

Gemessen auf der Alarm-Pruefstrecke (#2050 S2a) gegen die echte Ausloeseentscheidung
`TripAlertService.check_radar_alerts()`: Lauf 1 (11 mm/h, ~10 mm) loest aus und bucht
120 Min Sperrzeit; Lauf 3 nach 90 Min (30 mm/h, ~27,5 mm) schweigt mit Protokollgrund
`cooldown`.

## Kernbefund 1 — die Sperre steht vor der Eskalationspruefung

Die Gate-Kette des Trip-Radar-Zweigs laeuft in dieser Reihenfolge:

| # | Stufe | Ort | Kennt Verschaerfung? |
|---|---|---|---|
| 1 | Ruhezeit | `alert_gate.py:170-175` (in `check_nowcast_gate`) | nein — soll sie auch nicht (#1955) |
| 2 | **Sperrzeit** | `alert_gate.py:177-181` | **nein** |
| 3 | Tages-Obergrenze | `alert_gate.py:183-188` | nein |
| 4 | Briefing-Ueberholung | `trip_alert.py:1410-1414` | **ja** (Menge gegen Menge, #2020 S1) |
| 5 | Entdopplung / Ereignis-Identitaet | `trip_alert.py:1540` → `alert_gate.py:617-692` | **ja** (Stufenvergleich, #1467 S4b) |

`check_nowcast_gate()` (`alert_gate.py:140-190`) nimmt **keinen Parameter entgegen, ueber den
es von einer Verschaerfung erfahren koennte** — es kennt nur Zeit, Ruhezeit und Zaehler. Der
Aufrufer bricht bei `not gate.allowed` mit `continue` ab (`trip_alert.py:1279-1300`), Stufe 4
und 5 werden nie erreicht.

## Kernbefund 2 — Umsortieren allein wuerde den gemessenen Fall NICHT beheben

Naheliegende Lesart: „Stufe 5 kann Verschaerfung, sie kommt nur zu spaet — also umsortieren."
Das traegt nicht. Die vorhandene Eskalationspruefung vergleicht auf der **dreistufigen**
Skala `LOW`/`MODERATE`/`HIGH` (`alert_urgency.exceeds`, `alert_urgency.py:65-72`). Fuer Radar
entsteht die Stufe aus `intensity_to_text` (`radar_service.py:279-296`), und die **saettigt
bei 4,0 mm/h** (`HEAVY_RAIN_THRESHOLD_MM_H`, `radar_service.py:78`):

| Lauf | Rate | `intensity_label` | `severity` |
|---|---|---|---|
| 1 | 11 mm/h | `Starker Regen` | `HIGH` |
| 3 | 30 mm/h | `Starker Regen` | `HIGH` |

`exceeds("HIGH", "HIGH")` ist `False`. Die bestehende Leiter ist oben zu und kann eine
Verdreifachung nicht sehen. **Eine quantitative Vergleichsbasis muss neu dazu; sie laesst
sich nicht aus dem Bestand borgen.**

## Kernbefund 3 — die Vergleichsbasis (C-3) hat eine PO-freigegebene Praezedenz

Anforderung C-3 („Die Vergleichsbasis ist definiert und protokolliert") ist fuer die
**Briefing**-Ueberholung bereits beantwortet, entschieden am 2026-08-21 (#2020 F008):

```
_overtaking = (
    _briefing_announced
    and result.window_precip_mm >= _briefing_precip * _BRIEFING_OVERTAKE_FACTOR   # 2,0
    and result.window_precip_mm >= _OVERTAKE_MIN_ABSOLUTE_MM                       # 2,0 mm
)
```
`trip_alert.py:1410-1414`, Konstanten `:88` und `:99`.

Entscheidend ist die **Messgrundlage**: verglichen wird **Menge gegen Menge**
(`window_precip_mm` = akkumulierte mm im 60-Min-Vergleichsfenster ab `now`,
`_OVERTAKE_COMPARE_WINDOW_MIN = 60`, `radar_service.py:84`, Rechnung `:779-800`) — bewusst
**nicht** ueber eine Spitzenrate. Begruendung im Code (`trip_alert.py:80-99`): anhaltender,
nicht-spitzer Regen (3,9 mm/h ueber 50 Min = 3,575 mm gegen 1,0 mm Ankuendigung, 3,6-fach)
wurde von der alten Ratenschwelle ausgesperrt, obwohl er die Ankuendigung real ueberholte.

Diese Regel rechnet den gemessenen #2065-Fall korrekt durch:
`27,5 mm >= 10 mm × 2,0` ✓ und `27,5 mm >= 2,0 mm` ✓ → Alarm.

Zur Abgrenzung: `max_rate_mm_h` (`radar_service.py:158-180`) ist seit #2020/F008 **rein
beschreibend, ohne Leser in der Alarmregel**; `intensity_label` entsteht dagegen aus der Max-Rate
im **180-Min**-Nowcast-Fenster (`radar_service.py:731-743`) — drei verschiedene Groessen, die
nicht verwechselt werden duerfen.

## Kernbefund 4 — die zuletzt gemeldete MENGE wird heute nirgends gespeichert

| Ablage | Datei | Inhalt | taugt als Vergleichsbasis? |
|---|---|---|---|
| `ThrottleStore` | `data/users/<uid>/throttle_state.json` | `{scope: {key: ISO-Zeitstempel}}` | **nein** — nur Zeitstempel (`throttle_store.py:67-87`) |
| Tageszaehler | `alert_daily_count.json` | `{zones: {zone: {date, count}}}` | nein |
| Ereignis-Identitaet | `alert_state/<entity_id>.json` | u.a. `severity` (LOW/MODERATE/HIGH) | nur grob — saettigt (Kernbefund 2) |
| Abweichungs-Register (#816) | `alert_state/<entity_id>.json`, Schluessel `<metric>:<segment_id>` | `last_reported_value: float` | Vorbild fuer die Bauform, aber anderer Alarmtyp |

Es fehlt also genau ein Wert: die zuletzt **gemeldete** `window_precip_mm` je
(`throttle_scope`, `throttle_key`). Der natuerliche Buchungsort ist `record_nowcast_sent()`
(`alert_gate.py:386-400`) — dort werden Tageszaehler und Sperrzeit heute schon gemeinsam und
**nur nach erfolgreicher Zustellung** gebucht (F001-Symmetrie), und beide Flaechen
(Trip + Ortsvergleich) laufen darueber.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_gate.py` | `check_nowcast_gate` (:140), `record_nowcast_sent` (:386), `check_event_identity_gate` (:617) — geteilter Baustein Trip+Vergleich |
| `src/services/trip_alert.py` | Radar-Zweig: Gate-Aufruf :1269, Briefing-Ueberholung :1410, Entdopplung :1540, Buchung :1637 |
| `src/services/throttle_store.py` | Sperrzeit-Persistenz; muesste die gemeldete Menge mittragen |
| `src/services/radar_service.py` | `NowcastResult.window_precip_mm` (:137-190), Fensterrechnung (:779-800), Intensitaets-Schwellen (:78, :279-296) |
| `src/services/alert_urgency.py` | 3-Stufen-Skala + `exceeds` — erklaert, warum der Bestand nicht reicht |
| `src/services/compare_radar_alert.py` | zweiter Produktiv-Aufrufer von `check_nowcast_gate` (:169) — Ortsvergleich, **zurueckgestellt** |
| `src/services/alert_daily_limit.py` | Tages-Obergrenze inkl. Reserve-Mechanik `_FORECAST_CHANGE_RESERVE` (:88) |
| `src/services/user_tier.py` | `daily_alert_limit` (:45): premium → `None` (kein Limit), standard → 4, free → 2 |
| `tests/helpers/alarm_pruefstrecke.py` | Zeitreihen-Harness (#2050 S1): `AlarmPruefstrecke(user_id, settings, throttle_hours=2)`, `.lauf(at=, zweig=, trip=, radar_service=)` → `AlarmPruefstreckeLauf(triggered_count, mail, telegram, sms, premium_sms)` |
| `tests/tdd/test_alarm_szenario_briefing_ueberholung_zeitreihe.py` | Helfer `_uid/_dauerregen/_radar/_briefing_anker/_aufbau/_settings_all_channels/_clean_user`; die ausgelassene AC-3-Stelle ist ab :270 dokumentiert |

## Existing Patterns

- **Ueberholung als UND-Verknuepfung** (Faktor **und** absolute Untergrenze), damit die Regel
  fuer feste Vergleichsbasis in beiden Groessen monoton bleibt — `trip_alert.py:1405-1414`.
- **Buchen nur nach Zustellung** (F001-Symmetrie): `record_nowcast_sent` /
  `record_event_identity` stehen hinter dem Versand, nicht davor.
- **Benannte Konstante statt Hartverdrahtung** fuer jede Schwelle (ADR-0021-Muster, #2009).
- **Geteilter Baustein mit `context_label`-Parameter** statt zweier Kopien fuer Trip/Vergleich.

## Existing Specs & ADRs

| Quelle | Kernaussage | Bedeutung hier |
|---|---|---|
| **ADR-0021**, Nachtrag (`docs/adr/0021-shared-deviation-alert-engine.md:106-112`) | Die Reihenfolge **Ruhezeit → Sperrzeit → Tages-Obergrenze** ist als geteilter Baustein festgeschrieben, fuer Trip **und** Ortsvergleich | Eine Ausnahme in dieser Kette ist eine Aenderung an einer dokumentierten Entscheidung → **datierter ADR-Nachtrag noetig** (Praezedenz: der S4b-Nachtrag, bewacht von `test_ac21_adr_0021_traegt_einen_datierten_s4b_nachtrag`) |
| **ADR-0009** Alarme als Abweichungs-Waechter | Alarme messen Abweichung, nicht absolute Schwellen | Stuetzt die Bauform „gegen die zuletzt gemeldete Lage", nicht „ab X mm" |
| `docs/specs/modules/rework_1467_s3_nowcast.md` | Spec der geteilten Gate-Kette | Muss den neuen Zweig mitfuehren |
| `docs/specs/modules/rework_1467_s4b_entdopplung.md` | Ereignis-Identitaet inkl. V2-Eskalation | Erklaert die bestehende, saettigende Stufenpruefung |
| `docs/specs/modules/alarm_pruefstrecke.md`, `alarm_szenarien_waechter_2_3.md` | Harness + Szenarien 2/3 | Der rote Test haengt hier an |

## Dependencies

- **Upstream:** `NowcastResult.window_precip_mm` (Radar-Dienst), `ThrottleStore`,
  `alert_daily_limit`, `AlertStateService`.
- **Downstream (Aufrufer, die eine Signaturaenderung sehen):**
  `trip_alert.py:1269` (Trip-Radar) und `compare_radar_alert.py:169` (Ortsvergleich-Radar).
  Der Ortsvergleich ist PO-seitig zurueckgestellt → die Erweiterung muss dort **wirkungslos**
  bleiben (optionaler Parameter, Default „keine Verschaerfungsinformation").

## Betroffene Tests

| Datei | Relevanz |
|---|---|
| `tests/tdd/test_alert_gate.py` | `test_ac11_ruhezeit_stoppt_vor_der_sperrzeit_pruefung` (:88), `test_ac11_sperrzeit_stoppt_vor_der_tages_obergrenze` (:129), `test_ac11_freie_bahn_wird_durchgelassen` (:163) bewachen die Reihenfolge; `test_ac20_…signatur_bleibt_ohne_cooldown_parameter` (:1045) zeigt, dass Signaturen hier bewacht werden |
| `tests/tdd/test_alarm_szenario_briefing_ueberholung_zeitreihe.py` | Heimat der Helfer; die ausgelassene AC-3-Stelle |
| `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py` | patcht `check_nowcast_gate` (:304-310) — reagiert auf Signaturaenderungen |
| `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` | Zonenfuehrung durch dieselbe Kette |
| `tests/tdd/test_issue_1088_official_alert_triggers.py` | prueft die Aufrufreihenfolge `check_nowcast_gate` → `check_event_identity_gate` → Versand (:788-822) |
| `tests/tdd/test_nowcast_briefing_overtake.py` | die Briefing-Ueberholung aus #2020 S1 — Einzelaufrufe ohne Sperrzeit-Gedaechtnis; muss unveraendert gruen bleiben |
| `tests/tdd/test_nowcast_suppression_logging.py` | prueft die `alert_log`-Eintraege bei Gate-Abweisung — ein neuer Durchbruchsgrund beruehrt sie |

Ergaenzungen zur Pruefstrecke: `Zweig = Literal["deviation", "official", "radar"]`
(`alarm_pruefstrecke.py:40`); Zeit ausschliesslich ueber `freeze_time(at)` in `lauf()` (`:162`),
`now_utc=` ist bewusst nicht durchgereicht. Weitere Helfer in der Szenario-Datei:
`_kurze_spitze(rate_mm_h)` (:96-108) und `_gelesene_briefing_werte(uid, trip, seit)` (:60-79) —
letzterer liest die Vergleichswerte aus `alert_log.read_undelivered()`, statt sie
nachzurechnen.

Die feste Reihenfolge ist zusaetzlich in `docs/specs/modules/rework_1467_s3_nowcast.md:12-20`
niedergeschrieben (Abbruch bei der ersten greifenden Stufe) — die Spec muss also mitgezogen
werden, nicht nur die ADR.

## Risks & Considerations

1. **Alarmflut statt Schweigen.** Die Fehlerrichtung kippt: eine zu weiche Ueberholungsregel
   macht aus der Sperrzeit eine Attrappe. Die absolute Untergrenze ist der Schutz dagegen und
   darf nicht entfallen.
2. **Kettenreaktion.** Wenn jeder durchgebrochene Alarm die neue Vergleichsbasis hochsetzt,
   braucht die naechste Verschaerfung wieder den Faktor — das bremst von selbst. Nur wenn die
   Basis **nicht** mitgefuehrt wird, entsteht Wiederholungsgefahr. Muss AC-gedeckt sein.
3. **Ruhezeit bleibt unangetastet** (#1955, PO-Ablehnung) — die Ausnahme darf ausdruecklich
   **nicht** an Stufe 1 vorbei.
4. **Ortsvergleich zurueckgestellt** — Signaturaenderung ja, Verhaltensaenderung dort nein.
5. **Schema-Aenderung an `throttle_state.json`**: Bestandsdaten muessen weiterlesbar bleiben
   (Read-Modify-Write, alter Reinstring als gueltiger Eintrag). `throttle_store.py` faellt
   unter die Schema-Backup-Regel.
6. **ADR-0021 nicht still zuruecknehmen** — datierter Nachtrag ist Pflicht.
7. **Tageslimit ist tierabhaengig**: `premium → None`. Fuer den PO ist die Tageslimit-Haelfte
   von A-3 heute wirkungslos; die akute Luecke ist eindeutig die Sperrzeit.
8. **Ueberschneidung mit #2050 S2b** (Parallelsitzung): dort wird `trip_alert.py:1382`
   (`_onset_dt`-Berechnung) angefasst. Abgesprochen 2026-08-22: **#2065 zuerst**, S2b rebast
   darauf.

---

# Analysis (Phase 2, 2026-08-22)

## Type

**Bug.** Nutzersichtbares Fehlverhalten: ein Alarm ueber eine deutliche Verschaerfung bleibt aus.

## Befund A — hinter der Sperrzeit steht eine ZWEITE Wand (GEMESSEN)

Der wichtigste Analyse-Ertrag, unabhaengig zweifach hergeleitet (eigene Messung + Challenger)
und **empirisch belegt**, nicht nur gerechnet. Aufruf der echten Entdopplung mit der
Konstellation der Pruefstrecke (Lauf 1 meldet bei T+5 mit `HIGH`, Lauf 3 prueft 90 Min spaeter
bei T+95 mit `HIGH`):

```
Lauf 3 (HIGH gegen HIGH):       allowed=False  reason='event_duplicate'
Gegenprobe (Eintrag MODERATE):  allowed=True   reason=None
```

Die **Gegenprobe ist der Beweis, dass die Eskalationsstelle erreicht wird** — ohne sie koennte
„blockiert" auch heissen, der Zweig sei gar nicht ausgewertet worden.

Rechenweg (`alert_gate.py:458-467`, `:489-494`, `:601-614`, `NOWCAST_HORIZON_MIN = 180`,
`radar_service.py:69`):

| Schritt | Wert | Ergebnis |
|---|---|---|
| Zeitabstand der Ereigniszeitpunkte | 90 Min ≤ 180 Min | Treffer im Register |
| Eskalation `exceeds("HIGH","HIGH")` | `2 > 2` | False |
| V1-Ausnahme `_covers_materially_more` | abgedeckt bis T+275, noetig T+365 | greift nicht |
| **Ergebnis** | | `REASON_EVENT_DUPLICATE` |

**Konsequenz:** Ein Fix, der nur die Sperrzeit oeffnet, macht den roten Test **nicht** gruen —
er wechselt nur den Protokollgrund von `cooldown` auf `event_duplicate`. Die Zuschnitt-Option
„nur Sperrzeit" ist damit nicht eine schwaechere Variante, sondern **keine Loesung**.

Beide Sperren scheitern an **derselben** Ursache: einer Schwere-Skala, die bei 4 mm/h zumacht.
Das ist eine Ursache, nicht zwei — und deshalb ein Fix, nicht zwei.

## Befund B — die Menge existiert zum Zeitpunkt der Sperrpruefung noch nicht

`check_nowcast_gate` laeuft in `trip_alert.py:1269`, der Nowcast-Abruf erst in `:1365`. Die
Groesse, an der Verschaerfung gemessen wird (`window_precip_mm`), entsteht also **nach** dem
Gate. Ein gesperrter Lauf holt heute gar keine Daten (`continue` bei `:1303`).

Daraus folgt zwingend: im Sperrzeit-Fall muss **zusaetzlich** abgerufen werden. Keine Bauform
kommt daran vorbei. Kosten: Prueftakt 15 Min (`scheduler.go`), Sperrzeit-Vorgabe 2 h,
Radar-Cache-TTL 300 s (`radar_cache.py:67`) → bis zu **7 zusaetzliche Abrufe je Sperrfenster
und Tour**, gegen ein Tagesbudget von 9000 (`forecast_budget.py:40`). Unkritisch, gehoert aber
in den PR benannt. Die Invariante „genau EIN `get_nowcast` je Trip" (`trip_alert.py:1305`,
#1329) bleibt gewahrt, wenn der Sperrzeit-Fall in denselben Abruf laeuft statt einen zweiten
auszuloesen.

## Befund C — ein zweiter Schreiber teilt sich den Sperrzeit-Topf

`trip_report_scheduler.py:1574` bucht dieselbe `radar`-Sperre fuer den Kurzfristhinweis im
Briefing — **ohne** Mengenangabe. Die Vergleichsbasis kann also legitim fehlen. Regel:
**fehlende Vergleichsbasis ⇒ kein Durchbruch** (konservativ). Das ist die richtige
Fehlerrichtung — Alarmflut zu vermeiden wiegt schwerer als Durchlaessigkeit, und ein Durchbruch
ohne Vergleichsbasis waere ein Durchbruch ohne Nachweis.

## Technischer Ansatz (Entscheidung)

**Eine geteilte Vergleichsfunktion, zwei Wirkorte.** Die Definition von „deutlich schlimmer"
existiert genau **einmal** (Anforderung C-3) und wird an beiden blockierenden Stellen benutzt:

| # | Baustein | Wirkung |
|---|---|---|
| 1 | Neuer Helfer in `alert_gate.py`, Nachbarschaft `record_nowcast_sent` | Vergleicht aktuelle Menge gegen gespeicherte Vergleichsbasis. Faktor **und** absolute Untergrenze, UND-verknuepft — Muster der Briefing-Ueberholung, aber **eigene benannte Konstanten** (andere Vergleichsbasis) |
| 2 | `trip_alert.py::check_radar_alerts` | Bei `gate.reason == REASON_COOLDOWN` **kein sofortiges `continue`** mehr: in den Abruf laufen, dann den Helfer befragen. Kein Treffer → unveraendert unterdruecken (Protokollgrund bleibt `cooldown`) |
| 3 | `check_event_identity_gate` | Optionaler Parameter, der die quantitative Verschaerfung in den **bestehenden ersten Eskalationszweig** (`alert_gate.py:669`) einspeist — ODER-verknuepft mit `exceeds(...)`. Struktur „Eskalation zuerst" bleibt unangetastet |
| 4 | `ThrottleStore` | Eintrag von reinem ISO-String auf `{"at": …, "precip_mm": …}` erweitern; alter Reinstring bleibt gueltig lesbar (`_parse`, `throttle_store.py:161-172`). Neue Lesemethode statt Ueberladung von `last_sent` (15+ Aufrufer) |
| 5 | `record_nowcast_sent` | Optionaler Mengen-Parameter, durchgereicht an `.record()`. Buchung weiterhin **nur nach erfolgreicher Zustellung** (F001-Symmetrie) |

**`check_nowcast_gate` bleibt in Signatur und Verhalten unveraendert.** Damit bleiben die drei
Ordnungstests (`test_alert_gate.py:88/129/163`) und der Ortsvergleich (`compare_radar_alert.py`)
unberuehrt — der Helfer taucht dort schlicht nicht im Aufrufgraphen auf. Das ist die sauberste
Erfuellung der PO-Rueckstellung: keine Signatur-Passagiere, kein toter Default.

**Verworfen:**
- *Gates umsortieren* — behebt den gemessenen Fall nicht (Befund A und Kernbefund 2).
- *Vergleich in `check_nowcast_gate` selbst* — zoege den Speicherzugriff in den geteilten
  Baustein und beruehrte Ortsvergleich und Ordnungstests am falschen Ort.
- *Die bestehende `LOW/MODERATE/HIGH`-Leiter um eine vierte Stufe erweitern* — aendert die
  Bedeutung einer Groesse, die an vielen Stellen gelesen wird (Kanal-Schwellen ADR-0046,
  amtliche Warnstufen), fuer einen lokalen Zweck. Grosse Flaeche, kleiner Ertrag.

## Verfall der Vergleichsbasis

Die Vergleichsbasis lebt **im selben Eintrag** wie der Sperrzeit-Zeitstempel und wird bei jeder
erfolgreichen Zustellung ueberschrieben. Keine zweite Uhr. Gelesen wird sie ohnehin nur, solange
die Sperre laeuft.

Fehlerrichtung, die das bewusst in Kauf nimmt: nach einem durchgebrochenen 27,5-mm-Alarm braucht
die naechste Verschaerfung im selben Fenster den vollen Faktor **gegen 27,5 mm**, nicht mehr
gegen die alten 10 mm. Das ist erwuenschtes Selbstbremsen und genau der Schutz gegen die
Kettenreaktion aus Risk 2 — keine Luecke.

## Zuschnitt (Entscheidung)

**Sperrzeit + Entdopplung. Tageslimit NICHT.**

- *Sperrzeit* — der gemessene Fall.
- *Entdopplung* — **zwingend**, sonst wird der rote Test nicht gruen (Befund A). Nicht
  Scope-Ausweitung, sondern Teil derselben Ursache.
- *Tageslimit* — bewusst ausgelassen, mit Begruendung: bei `tier=premium` ohnehin `None`
  (`user_tier.py:45-64`), also fuer den akuten Fall wirkungslos; es ist als Szenario 7 /
  Anforderung D-3 bereits eigener Scheibe S3 in #2050 zugeordnet; und die Kette bricht bei
  Sperrzeit ab, bevor das Tageslimit ueberhaupt geprueft wurde.

**Wichtig und AC-pflichtig:** Weil `check_nowcast_gate` bei Sperrzeit kurzschliesst, wurde das
Tageslimit im Ueberholungsfall **noch nie geprueft**. Der Durchbruch darf es nicht stillschweigend
mit ueberspringen — im Override-Pfad ist es erneut zu pruefen und bleibt hartes Stop. Sonst
raeumte dieser Fix eine zweite Sperre ab, ohne es zu sagen.

A-3 wird damit **teilweise** erfuellt (zwei von drei Sperren). Das gehoert so in die Spec — nicht
als „A-3 erledigt" verbuchen.

## Scope Assessment

| | |
|---|---|
| Produktivdateien | 4 (`alert_gate.py`, `trip_alert.py`, `throttle_store.py`, ggf. Konstanten) |
| Geschaetzte LoC (Produktivcode) | ~+140 / −20 — **eng am 250er-Limit**, Doku zaehlt nicht mit |
| Testdateien | Zeitreihen-Szenario (neu), `test_alert_gate.py`, `test_throttle_store.py`, `test_nowcast_suppression_logging.py` |
| Doku | ADR-0021 datierter Nachtrag · `docs/specs/modules/rework_1467_s3_nowcast.md` Nachtrag |
| Risiko | **HIGH** — kritischer Alarmpfad, geteilter Baustein, Schema-Aenderung |

## Umsetzungsreihenfolge

1. `throttle_store.py`: Schema-Erweiterung + Rueckwaerts-Lesbarkeit, Roundtrip-Test.
2. `alert_gate.py`: Vergleichs-Helfer + benannte Konstanten + Mengen-Parameter an
   `record_nowcast_sent` + optionaler Eskalations-Parameter am Entdopplungs-Gate.
3. ADR-0021-Nachtrag und Spec-Nachtrag (inkl. Satz, **warum** der Ortsvergleich nicht mitkommt).
4. `trip_alert.py`: Kontrollfluss im Sperrzeit-Fall, Weitergabe an beide Wirkorte, erneute
   Tageslimit-Pruefung im Override-Pfad.
5. Zeitreihen-Szenario auf der Pruefstrecke (Reproduktion 11 → 30 mm/h).
6. Protokoll-Test fuer den neuen Durchbruchsgrund.

## Adversary-Schwerpunkte (fuer spaeter vormerken)

- Fehlende Vergleichsbasis (`precip_mm=None` durch den Briefing-Schreiber, Befund C) muss
  **konservativ** entscheiden — gezielt mutieren.
- Untergrenze entfernen → muss rot werden. Faktor verfaelschen → muss rot werden.
- Der Entdopplungs-Zweig: pruefen, dass die Gegenprobe den Zweig auch **erreicht** (siehe die
  MODERATE-Gegenprobe oben) — sonst beweist ein gruener Test nichts.
- Ruhezeit muss weiterhin **unbrechbar** sein (#1955).
- Tageslimit im Override-Pfad muss weiterhin greifen.

## Open Questions

Keine blockierenden. Die im Ticket offen gelassene Vergleichsbasis-Frage (C-3) ist durch die
PO-freigegebene Praezedenz aus #2020 F008 beantwortet; die konkreten Schwellenwerte gehen als
ACs auf Deutsch in die Spec und werden dort freigegeben.

## Nebenbefund

#2050 nennt als Herkunft von Szenario 4 die Nummer **#1445** — dort steht aber „MeteoAlarm via
MQTT-Stream". Fuer Szenario 4 existiert also **kein** dokumentierter historischer Vorfall; der
einzige Beleg ist die Messung aus #2050 S2a. Kein Handlungsbedarf, nur zur Einordnung der
Behauptung „jedes Szenario ist einmal wirklich passiert".
