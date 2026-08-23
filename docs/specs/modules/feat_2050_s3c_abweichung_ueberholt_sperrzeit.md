---
entity_id: feat_2050_s3c_abweichung_ueberholt_sperrzeit
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: feat-2050-s3c-abweichung-ueberholt-sperrzeit
version: "1.0"
tags: [alarm, abweichung, sperrzeit, tageslimit, eskalation]
---

# Verschärfung überholt die Sperrzeit im Abweichungs-Zweig (Issue #2050, Scheibe S3c)

## Approval

- [x] Approved — PO-Freigabe der ACs am 2026-08-23 ("go")

## Purpose

Anforderung **A-3** aus #2050 ("Eine Verschärfung überholt jede Sperre", Szenario 4) ist im
**Abweichungs-Zweig** (`forecast_change`, Vorhersage-Änderungsalarm) heute unerfüllt: eine aktive
Sperrzeit bricht dort jeden Alarm hart ab, ohne jeden Blick auf den Schweregrad — eine Lage, die
sich von „mäßig" auf „schwer" verschärft, wird genauso geschluckt wie eine reine Wiederholung.
#2065 hat dieselbe Anforderung bereits für den **Radar**-Zweig gelöst, #2050 S3b hat den
Eskalations-Durchbruch dort zusätzlich aufs erschöpfte Tagesbudget ausgeweitet. Diese Scheibe
überträgt beide Bausteine auf den Abweichungs-Zweig — mit einem Rangvergleich statt einer
Faktor-Formel, weil hier mehrere heterogene Metriken (°C, km/h, mm) statt einer einzelnen
physikalischen Menge im Spiel sind.

## Source

- **File:** `src/services/throttle_store.py` (`ThrottleStore.record`, neue Lesemethode
  `last_sent_with_urgency`)
- **File:** `src/services/alert_gate.py` (neue Funktion `deviation_overtakes_cooldown`, neuer
  Basis-Leser, als Schwestern von `radar_overtakes_cooldown`/`last_nowcast_precip_mm`)
- **File:** `src/services/trip_alert.py` (`TripAlertService.check_and_send_alerts`, Umbau der
  Gate-Kette `:393-414`, wiederverwendete Budget-Brücke `_eskalation_bricht_budget`)
- **Identifier:** siehe Implementation Details

Schicht: ausschließlich Python-Core (`src/services/`). Kein Go-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~+335 / −25 (Produktivcode + Tests, ohne Doku) — deutlich über dem 250-LoC-
  Standardlimit; `loc_limit_override 500` vor `/40-tdd-red` setzen (#2065 und S3b liefen ebenso)
- **Files:** 3 Produktivdateien (`throttle_store.py`, `alert_gate.py`, `trip_alert.py`) + 2
  Testdateien (1 MODIFY, 1 CREATE) + 2 Dokudateien (ADR-0021-Nachtrag, diese Spec)
- **Effort:** high
- **Risiko:** HIGH — kritischer Alarmpfad, öffnet eine bislang harte Sperre, Rollout während
  laufender Tour (KHW-Start 2026-08-23)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_gate.py::radar_overtakes_cooldown` | function | Unmittelbares Vorbild (#2065) — dieselbe Grundform (Basis fehlt ⇒ `False`), andere Vergleichsformel (Rang statt Faktor) |
| `src/services/alert_urgency.py::exceeds`/`urgency_from_changes` | function | Bestehende Rang-Skala `LOW`/`MODERATE`/`HIGH` — kein dritter Eskalationsbegriff, dieselbe Skala wie im Budget-Zweig (S3b) |
| `src/services/throttle_store.py::ThrottleStore.record`/`last_sent_with_precip` | method | Vorbild für den additiven vierten Parameter und den Schwester-Lesepfad (#2065-Muster) |
| `src/services/alert_daily_limit.py::escalation_breaks_through` | function | Bestehende, generische Budget-Brücke (S3b) — wird für den Abweichungs-Zweig NUR aufgerufen, nicht verändert |
| `src/services/trip_alert.py::_eskalation_bricht_budget` | method | Bestehender dünner Wrapper (S3b, Radar-Zweig) — wird im Abweichungs-Zweig wiederverwendet, damit sich der eine Durchbruch je Zone/Tag über beide Zweige teilt |
| `src/services/deviation_alert_engine.py::evaluate`/`_highest_severity` | function | Bleibt UNVERÄNDERT — mit dem PO-zurückgestellten Ortsvergleich geteilt (`compare_alert.py:509`), die Ausnahme darf dort nicht mit-erben |
| `src/services/alert_log.py::REASON_FORECAST_CHANGE`/`REASON_COOLDOWN`/`REASON_DAILY_LIMIT` | constant | Bestehende Gründe, kein neuer Code — die Kette protokolliert bei Nicht-Überholung weiter wie heute (S3b) |
| `docs/adr/0021-shared-deviation-alert-engine.md` | doc | Trägt die feste Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze fest; Nachtrag #2065 und Nachtrag S3b bereits vorhanden — braucht einen dritten, datierten Nachtrag |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke` | test helper | Zeitreihen-Harness gegen die echte Service-Kette, Vorlage `test_radar_cooldown_overtake.py`/`test_daily_budget_escalation.py` |

## Implementation Details

### 1. Vergleichsbasis — additives Feld im Sperrtopf

`ThrottleStore.record()` bekommt einen vierten, optionalen Parameter `urgency: Optional[str] =
None`; der geschriebene Eintrag wird `{"at": iso, "precip_mm": float|null, "urgency": str|null}`.
Neue Lesemethode `last_sent_with_urgency(scope, key)` als Schwester zu `last_sent_with_precip()`
(`throttle_store.py:73-83`) — eigene Methode statt Überladung, aus demselben Grund wie beim
`precip_mm`-Feld (viele bestehende Aufrufer erwarten ein einzelnes `datetime`). Altformat
(reiner ISO-String, ODER das `#2065`-Zwischenformat ohne `urgency`) bleibt lesbar; `record()`
schreibt ausschließlich das neue, vollständige Format (Read-Modify-Write über `_update()`, kein
Replace).

**Verworfen:** eine eigene Vergleichsbasis nach dem `max_urgency_sent`-Muster
(`alert_daily_limit.py:124-158`) — die ist Tag+Zone-skaliert und wird am Ortstag zurückgesetzt,
während die Sperrzeit-Basis ein Momentanwert je Sperrschlüssel ist. Andere Semantik, zweiter
paralleler Speicher ohne Gegenwert.

### 2. Vergleichsformel — ordinaler Rangsprung statt Faktor

Neue Funktion `deviation_overtakes_cooldown(*, basis_urgency: Optional[str], urgency: str) ->
bool` in `alert_gate.py`, als Schwester von `radar_overtakes_cooldown` (:433-459) — **nicht** in
einem geteilten Gate (der Abweichungs-Zweig hat ohnehin kein `check_nowcast_gate`-Äquivalent).
`False` bei fehlender Basis (`basis_urgency is None`), sonst `alert_urgency.exceeds(urgency,
basis_urgency)`.

**Verworfen:** eine Faktor-Formel wie im Radar-Zweig — dort gibt es EINE physikalische Menge
(mm/h), der Abweichungs-Zweig trägt potenziell mehrere heterogene Metriken (Temperatur, Wind,
Regen) gleichzeitig; ein gemeinsamer Faktor ist auf ihnen nicht definierbar. Der Rangvergleich
über `alert_urgency.exceeds()` ist bereits an zwei Stellen etabliertes Vokabular
(`alert_gate.py:752`, `alert_daily_limit.py:158`) — kein dritter Eskalationsbegriff.

**Bekannte Grenze, bewusst nicht gefangen:** die Skala sättigt bei `HIGH` — eine Lage, die von
`HIGH` auf noch schlimmer geht, erzeugt keinen Rangsprung und bricht nicht durch (s. Known
Limitations).

### 3. Kontrollfluss — das #2065-Muster, für zwei sequentielle Gates

Der Radar-Zweig hat EIN kombiniertes Gate mit `gate.reason`; der Abweichungs-Zweig hat zwei
sequentielle Gate-Stufen in `check_and_send_alerts` (`trip_alert.py:308-582`). Umbau:

- **Sperrzeit-Gate (`:393-400`):** bricht nicht mehr sofort ab, sondern setzt
  `_sperrzeit_offen = True` und läuft weiter.
- **Tages-Obergrenze (`:405-414`):** wird bei `_sperrzeit_offen` zunächst ÜBERSPRUNGEN — sie
  kann zu diesem Zeitpunkt noch nicht sinnvoll geprüft werden, weil eine Sperrzeit-Überholung sie
  ohnehin real nachholen muss (s. u.).
- **Wetter-Abruf (`:417-422`) und `DeviationAlertEngine.evaluate()` (`:449-455`)** laufen
  UNVERÄNDERT — auch bei offener Sperrzeit, das ist die Voraussetzung für den Vergleich.
- **Dringlichkeit einmal bilden.** Nach `evaluate()`, sobald `to_report` feststeht, wird
  `alert_urgency.urgency_from_changes(to_report)` EINMAL berechnet und für zwei Zwecke
  weitergereicht: (a) die Überholungs-Entscheidung, (b) die heutige Späteberechnung bei `:520-521`
  (dort ersetzt, nicht doppelt gerechnet — derselbe Wert, garantiert keine zweite,
  möglicherweise abweichende Berechnung).
- **Bei `_sperrzeit_offen`:** Vergleichsbasis über `last_sent_with_urgency("trip", trip.id)`
  lesen, `deviation_overtakes_cooldown(basis_urgency=…, urgency=…)` befragen.
  - **Keine Überholung** ⇒ derselbe Protokollaufruf wie heute (`reason=REASON_FORECAST_CHANGE`,
    `gate_reason=REASON_COOLDOWN`, kein neuer Grund-Code), dann `return False`.
  - **Überholung** ⇒ die Tages-Obergrenze wird jetzt REAL nachgeholt (sie wurde oben
    übersprungen, sonst überspringt der Durchbruch sie stillschweigend mit — Lehre aus
    #2065/`trip_alert.py:1633-1654`). Ist sie noch nicht erschöpft: normal weiterlaufen. Ist sie
    erschöpft: die bestehende S3b-Brücke `_eskalation_bricht_budget(trip, now_utc, urgency)`
    entscheidet — `False` ⇒ Protokoll `gate_reason=REASON_DAILY_LIMIT`, `return False`; `True`
    ⇒ weiterlaufen, und der spätere `alert_daily_limit.increment(...)`-Aufruf bekommt
    `is_escalation_breakthrough=True` mitgegeben.
- **Nach erfolgreichem Versand (`:566`):** `self._throttle_store.record("trip", trip.id, now,
  urgency=<die oben einmal gebildete Dringlichkeit>)` — die Sperrzeit wird jetzt MIT der
  abgeleiteten Dringlichkeit neu gebucht (Selbstbremsung wie im Radar-Zweig: eine erneute
  identische Wiederholung überholt die eigene, gerade gesetzte Basis nicht mehr).

`DeviationAlertEngine` bleibt UNANGETASTET — sie ist mit dem PO-zurückgestellten Ortsvergleich
geteilt (`compare_alert.py:509`); der Ortsvergleich darf die Ausnahme nicht erben.

**Der amtliche Zweig (`trip_alert.py:2480`) bleibt ebenfalls unverändert** und schreibt weiter
ohne `urgency` in denselben Sperrtopf-Schlüssel (`scope="trip"`, `key=trip.id` — beide Zweige
teilen sich den Schlüssel). Folge: nach einem amtlichen Alarm fehlt die Vergleichsbasis für den
Abweichungs-Zweig ⇒ konservativ kein Durchbruch. Gewollt, direktes Gegenstück zu AC-8 aus #2065.

**Verworfen:** die Ausnahme in `DeviationAlertEngine` selbst zu bauen — sie ist mit dem
Ortsvergleich geteilt und würde die Ausnahme dort automatisch mit einführen. Ebenso verworfen:
die Dringlichkeit an zwei Stellen unabhängig neu zu berechnen (Sperrzeit-Entscheidung UND
Protokoll `:520-521`) — Risiko einer stillen Abweichung zwischen beiden Werten.

### 4. Tages-Obergrenze — die S3b-Brücke wird geteilt, nicht dupliziert

`_eskalation_bricht_budget` (`trip_alert.py:1320-1341`) ist bereits generisch (Zone +
Dringlichkeit, kein Radar-Spezifikum) und wird unverändert wiederverwendet. Der Deckel
`_MAX_ESCALATION_BREAKTHROUGHS = 1` (`alert_daily_limit.py:117-121`) gilt pro Zone und Tag ÜBER
BEIDE Zweige hinweg — Radar und Abweichung teilen sich denselben einen Durchbruch, sie addieren
sich nicht. Begründung: dieselbe Zone, derselbe Zähler, derselbe `_load_zones`-Eintrag; ohne
Teilung könnte eine Lage, die abwechselnd im Radar- und im Abweichungs-Zweig eskaliert, das
Tagesbudget mehrfach aufreißen — genau das Risiko, gegen das der Deckel in S3b eingeführt wurde.

## Expected Behavior

- **Input:** eine aktive Sperrzeit im Abweichungs-Zweig eines Trips (`ThrottleStore`, Scope
  `trip`, Schlüssel `trip.id`), gebucht mit einer gespeicherten Vergleichsdringlichkeit; ein
  neuer Prüflauf mit einer Wetteränderung, deren abgeleitete Dringlichkeit die gespeicherte
  Basis ECHT übersteigt.
- **Output:** bei Rangsprung (und, falls die Tages-Obergrenze zusätzlich erschöpft ist, bei
  zusätzlicher Eskalationsberechtigung über die geteilte Budget-Brücke) ein zugestellter Alarm
  über alle konfigurierten Kanäle, mit frisch gebuchter Sperrzeit und fortgeschriebener
  Dringlichkeit; sonst unverändert Stille mit demselben Protokollgrund wie heute (`cooldown` oder
  `daily_limit`).
- **Side effects:** ein zusätzlicher Wetter-Abruf bei jedem Prüflauf innerhalb einer offenen
  Sperrzeit (bisher fand dort gar kein Abruf statt); bei Durchbruch übers Budget Fortschreibung
  von `max_urgency_sent`/`escalation_breakthroughs` der Zone (geteilt mit dem Radar-Zweig); bei
  gescheiterter Zustellung keine Fortschreibung von Sperrzeit-Basis oder Budget-Feldern
  (F001-Symmetrie, unverändert).

## Acceptance Criteria

- **AC-1:** Given eine laufende Sperrzeit aus Lauf 1 eines Trips im Abweichungs-Zweig (2,0 → 18,0
  mm, bucht die Sperrzeit MIT der daraus abgeleiteten Dringlichkeit), When Lauf 2 nach 30 Minuten
  innerhalb desselben Sperrfensters eine gegenüber Lauf 1 deutlich stärker verschärfte Lage
  (2,0 → 45,0 mm, höherer Rang) meldet, Then geht der Alarm raus (`triggered_count == 1`) und
  `ThrottleStore.last_sent("trip", trip.id)` zeigt danach einen NEU gebuchten Zeitstempel
  gegenüber Lauf 1 — die Umkehrung des bisherigen Ist-Zustands (`test_ac2_…` aus S3a).
  - Test: `AlarmPruefstrecke`, zwei Läufe `zweig="deviation"` gegen die echte Service-Kette,
    kein Mock; Positivkontrolle ist die im selben AC geprüfte tatsächliche Zustellung von Lauf 2
    gegenüber der bisherigen Stille.

- **AC-2:** Given dieselbe laufende Sperrzeit wie AC-1, When Lauf 2 mit IDENTISCHEN
  Eingangswerten (kein Rangsprung gegenüber der gespeicherten Basis) innerhalb des Sperrfensters
  geprüft wird, Then bleibt der Lauf still (`triggered_count == 0`), `gate_reason ==
  REASON_COOLDOWN`, der Sperrzeit-Zeitstempel bleibt unverändert; eine Kontrolle desselben
  Aufbaus OHNE die vorbelegte Sperrzeit (anderer Nutzer, identischer Zeitpunkt, identische Werte)
  löst tatsächlich aus (Positivkontrolle — die Stille kommt vom Cooldown, nicht von den
  Eingangsdaten).
  - Test: Gegenprobe gegen eine zu weite Lösung; deckt zugleich den bestehenden Wächter
    `test_alarm_pruefstrecke_selbstschutz.py::test_ac1_zweiter_lauf_liest_den_von_lauf_eins_gebuchten_cooldown`
    ab, der unverändert grün bleiben muss.

- **AC-3:** Given eine laufende Sperrzeit, gebucht mit einer hohen Dringlichkeit (starke
  Verschärfung, Rang HIGH), When ein nachfolgender Lauf innerhalb des Sperrfensters eine
  ABGESCHWÄCHTE Lage meldet (Rang gleich oder niedriger als die gespeicherte Basis), Then bleibt
  der Lauf still (`triggered_count == 0`), der Sperrzeit-Zeitstempel bleibt unverändert; dieselbe
  abgeschwächte Lage OHNE laufende Sperrzeit würde für sich genommen sehr wohl auslösen
  (Positivkontrolle — die Lage ist an sich alarmfähig, nur nicht stark genug, um zu überholen).
  - Test: `AlarmPruefstrecke`, drei Läufe (auslösend hoher Rang → Sperrzeit → abgeschwächter
    Lauf innerhalb der Sperrzeit → Kontroll-Lauf mit derselben abgeschwächten Lage ohne Sperrzeit).

- **AC-4:** Given ein Sperrzeit-Eintrag im ALTEN Format (reiner ISO-Zeitstempel ohne
  `urgency`-Feld, z. B. aus Bestandsdaten vor dieser Änderung), When eine beliebig starke
  Verschärfung innerhalb dieses Sperrfensters geprüft wird, Then bleibt der Lauf still
  (`triggered_count == 0`), `gate_reason == REASON_COOLDOWN` (fehlende Basis ⇒ konservativ kein
  Durchbruch); dieselbe Lage gegen eine im NEUEN Format mit niedriger Dringlichkeit gebuchte
  Sperrzeit bricht durch (Positivkontrolle — die Formel selbst funktioniert, nur der Altbestand
  bremst konservativ).
  - Test: vorbereitete `throttle_state.json` mit Alt-Format-Eintrag, dann Lauf gegen die echte
    Service-Kette.

- **AC-5:** Given die Sperrzeit wurde vom AMTLICHEN Zweig gebucht (`trip_alert.py:2480`,
  `ThrottleStore.record` ohne `urgency`), sodass keine Vergleichsbasis existiert, When eine
  beliebig starke Abweichungs-Verschärfung im selben Sperrfenster geprüft wird, Then bleibt der
  Lauf still (`triggered_count == 0`), `gate_reason == REASON_COOLDOWN`; dieselbe Lage gegen eine
  vom Abweichungs-Zweig selbst gesetzte Basis mit niedrigerer Dringlichkeit bricht durch
  (Positivkontrolle). Direktes Gegenstück zu AC-8 aus #2065.
  - Test: Sperre über `ThrottleStore.record("trip", trip.id, at, urgency=None)` gebucht (simuliert
    den amtlichen Schreiber), anschließend Lauf im Abweichungs-Zweig.

- **AC-6:** Given ein durchbrechender Lauf wie AC-1, When der Sperrtopf-Eintrag nach dem Lauf
  gelesen wird, Then trägt sein `urgency`-Feld exakt den Wert, den
  `alert_urgency.urgency_from_changes(to_report)` für die TATSÄCHLICH gemeldeten Änderungen
  dieses Laufs geliefert hat — nicht ein im Test vorgegebenes Literal — und derselbe Wert
  erscheint auch als `severity`-Bestandteil im `alert_log`-Eintrag desselben Laufs (ein Wert, kein
  zweiter, potenziell abweichender Berechnungspfad).
  - Test: erwarteten Wert im Test selbst über `alert_urgency.urgency_from_changes(...)` aus den
    tatsächlich verwendeten `WeatherChange`-Objekten ableiten und gegen den gelesenen
    Sperrtopf-Eintrag UND den `alert_log`-Eintrag vergleichen — kein hartkodierter String.

- **AC-7:** Given ein `throttle_state.json` im alten Format, When ein Lauf gegen diese Datei
  prüft und anschließend selbst schreibt (egal ob durchbrechend oder unterdrückend), Then bleibt
  die Datei lesbar, ALLE anderen Bestandseinträge (andere `scope`/`key`) bleiben unverändert, und
  nur der betroffene Schlüssel wird auf das neue, vollständige Format
  (`{"at", "precip_mm", "urgency"}`) überschrieben (Read-Modify-Write, kein Replace).
  - Test: vorbereitete Alt-Datei mit mehreren Einträgen unterschiedlicher `scope`/`key`, danach
    ein Lauf gegen genau einen Schlüssel; die übrigen Einträge werden byteweise/wertweise auf
    Unverändertheit geprüft.

- **AC-8:** Given eine laufende Sperrzeit wird durch eine Verschärfung überholt (Rangsprung
  erfüllt), UND die Tages-Obergrenze ist erschöpft, UND diese Dringlichkeit übersteigt die heute
  in dieser Zone bereits zugestellte Höchststufe NICHT (keine echte Tages-Eskalation), When der
  Lauf geprüft wird, Then bleibt der Alarm dennoch aus, `gate_reason == REASON_DAILY_LIMIT` (der
  Grund wechselt von `cooldown` auf `daily_limit`, statt den Alarm zuzustellen), der
  Sperrzeit-Zeitstempel bleibt unverändert; derselbe Aufbau MIT freiem Tageszähler lässt den
  Alarm durch (Positivkontrolle — die Sperrzeit-Überholung allein genügt nicht, das Budget wirkt
  als reale zweite Wand, wie in der Analyse gemessen).
  - Test: Tageszähler über `alert_daily_limit.increment` auf das effektive Limit vorbelegt
    (Tier `standard`: 2), dann ein Sperrzeit-überholender, aber nicht Zonen-eskalierender Lauf.

- **AC-9:** Given eine laufende Sperrzeit wird überholt UND die Tages-Obergrenze ist erschöpft UND
  diese Dringlichkeit übersteigt ECHT die heute in dieser Zone bereits zugestellte Höchststufe
  (`max_urgency_sent`, entstanden aus vorangegangenen ECHTEN Zustellungen, nicht direkt
  vorbelegt) UND der eine Durchbruch des Tages ist in dieser Zone noch frei, When der Lauf
  geprüft wird, Then wird der Alarm trotz erschöpftem Budget zugestellt, und
  `escalation_breakthroughs` dieser Zone steht danach auf `1`.
  - Test: `AlarmPruefstrecke`-Läufe, die den Tageszähler und `max_urgency_sent` über reale
    Zustellungen aufbauen (kein direktes Vorbelegen der abgeleiteten Felder), dann ein
    eskalierender Lauf innerhalb einer überholten Sperrzeit.

- **AC-10:** Given wie AC-9, aber ein Durchbruch dieser Zone hat heute bereits stattgefunden
  (`escalation_breakthroughs == 1`), When ein zweiter, noch schwererer Lauf am selben Tag in
  derselben Zone geprüft wird, Then bleibt der Alarm aus, `gate_reason == REASON_DAILY_LIMIT`,
  `escalation_breakthroughs` bleibt bei `1` (Deckel: höchstens ein Durchbruch pro Tag und Zone).
  - Test: Fortsetzung von AC-9 mit einem dritten Lauf gleicher oder höherer Dringlichkeit.

- **AC-11:** Given der eine Durchbruch einer Zone wurde heute bereits im RADAR-Zweig verbraucht
  (`escalation_breakthroughs == 1`, aus einem echten Radar-Lauf derselben Zone), When danach eine
  ebenso eskalierende Lage im ABWEICHUNGS-Zweig derselben Zone geprüft wird (Sperrzeit überholt,
  Budget erschöpft, echte Eskalation), Then bleibt dieser Abweichungs-Alarm dennoch aus,
  `gate_reason == REASON_DAILY_LIMIT` — der Deckel gilt gemeinsam über beide Zweige, er wird
  nicht getrennt gezählt.
  - Test: ein echter Radar-Durchbruch (Vorlage `test_daily_budget_escalation.py`) gefolgt von
    einem Abweichungs-Lauf derselben Zone/desselben Tages.

- **AC-12:** Given eine Ruhezeit ist aktiv UND eine extreme Verschärfung liegt vor, die sowohl
  die Sperrzeit als auch ein erschöpftes Tagesbudget überholen würde, When der Lauf geprüft wird,
  Then bleibt der Alarm dennoch aus, `gate_reason == REASON_QUIET_HOURS` (PO-Ablehnung #1955 —
  die Ruhezeit bleibt unbrechbar, auch durch diese neue Ausnahme); außerhalb der Ruhezeit, sonst
  identischer Aufbau, geht derselbe Alarm durch (Positivkontrolle).
  - Test: `AlarmPruefstrecke`-Lauf mit `now` innerhalb der konfigurierten Ruhezeit, Kontroll-Lauf
    außerhalb.

- **AC-13:** Given ein geplantes Briefing steht für den Trip unmittelbar bevor und wurde noch
  nicht versucht (`_is_briefing_imminent(...) == True`), UND eine extreme Verschärfung liegt vor,
  When der Lauf geprüft wird, Then bleibt der Alarm aus (kein Zustellversuch — Bestandsschutz
  #1594, die Meldung kommt Minuten später vollständig im Briefing an); ohne den
  Briefing-Vorlauf, sonst identischer Aufbau, geht derselbe Alarm durch (Positivkontrolle — die
  Bedingung unterscheidet wirklich).
  - Test: Lauf mit gesetztem `_is_briefing_imminent`-Zustand, Kontroll-Lauf ohne.

- **AC-14:** Given dieselbe eskalierende Lage wie AC-1, aber im ORTSVERGLEICH-Pfad
  (`DeviationAlertEngine`/`compare_alert.py`, unverändert), When ein Ortsvergleich-Lauf während
  einer laufenden Sperrzeit desselben Presets geprüft wird, Then bleibt der Vergleichs-Alarm
  unterdrückt wie vor dieser Änderung — `DeviationAlertEngine.evaluate()` zeigt gegenüber dem
  Stand vor dieser Scheibe keine Signatur- oder Verhaltensänderung.
  - Test: bestehende Ortsvergleich-Tests laufen unverändert grün; zusätzlich ein
    Signatur-/Verhaltens-Wächter, der belegt, dass `DeviationAlertEngine.evaluate()` keinen
    neuen Parameter ohne Default entgegennimmt und für dieselbe eskalierende Eingangslage
    dasselbe Ergebnis liefert wie vor dieser Änderung.

- **AC-15:** Given zwei Nutzer mit identischer Zeitzone/Zone, von denen Nutzer A den einen
  Durchbruch seiner Zone heute bereits verbraucht hat (`escalation_breakthroughs == 1` in A's
  `alert_daily_count.json`), When Nutzer B eine ebenso eskalierende Lage in derselben Zone prüft,
  Then bricht Nutzer B's Alarm trotzdem durch (eigener Zähler unter `data/users/<user_id_b>/`,
  unabhängig von A) — kein Cross-User-Datenleck über den geteilten Zonen-Schlüssel.
  - Test: zwei getrennte `AlarmPruefstrecke`-Instanzen mit unterschiedlichen `user_id`, gleiche
    Zone; A's Zähler verbrauchen, dann B's Lauf prüfen.

- **AC-16:** Given diese Änderung ist umgesetzt, When
  `docs/adr/0021-shared-deviation-alert-engine.md` gelesen wird, Then trägt es einen DRITTEN
  datierten Nachtrag mit Bezug auf `#2050 S3c`, der beschreibt: Reichweite (Abweichungs-Zweig),
  Rangvergleich statt Faktor-Formel (Begründung: heterogene Metriken), geteilter
  Durchbruch-Deckel mit dem Radar-Zweig (nicht addiert), die Sättigungs-Grenze bei `HIGH`, und
  dass die Ruhezeit sowie das Briefing-Vorlauf-Gate unberührt bleiben — einsortiert nach dem
  letzten bestehenden Nachtrag (#2050 S3b, 2026-08-23).
  - Test: `# doc-compliance-test`, analog `test_ac21_adr_0021_traegt_einen_datierten_s4b_nachtrag`
    (`tests/tdd/test_alert_gate.py:1067`) — Nachtrag mit Bezug auf `#2050 S3c` nach dem
    S3b-Nachtrag einsortiert.

## Known Limitations

- **Die Rang-Skala sättigt bei `HIGH`.** Eine Lage, die von `HIGH` auf noch schlimmer eskaliert,
  erzeugt keinen Rangsprung und bricht die Sperrzeit nicht durch. #2065 hatte dasselbe
  Sättigungsproblem im Radar-Zweig und löste es mit einem zusätzlichen mm-Kanal
  (`alert_gate.py:746-760`) — dafür fehlt hier die Normierung über heterogene Metriken (°C,
  km/h, mm). Bewusst nicht in dieser Scheibe gefangen.
- **7 zusätzliche Wetter-Abrufe je Sperrfenster und Tour** (Takt `*/15`, Default-Sperrzeit
  120 Min) gegenüber heute 0, weil der Abruf jetzt auch bei offener Sperrzeit läuft. Bei
  Tagesbudget 9000 unkritisch, aber real und im PR zu nennen (deckungsgleich mit der
  #2065-Zahl für den Radar-Zweig).
- **Der amtliche Zweig schreibt weiter ohne Dringlichkeit** in denselben Sperrtopf-Schlüssel
  (`:2480`). Sein Eintrag trägt `urgency: null` und fällt damit konservativ als „keine Basis"
  durch — Gegenstück zu AC-8 aus #2065 (AC-5 dieser Spec).
- **Die verbliebene D-2-Lücke aus S3b bleibt bestehen:** fällt ein Alarm im Abweichungs-Zweig am
  Melde-Gedächtnis-Dedup (`suppressed_reason="alert_state_dedup"`, `:456-471`), entsteht weiterhin
  kein Protokolleintrag — nur `logger.debug`. Nicht Teil dieser Scheibe; Triage nach CLAUDE.md
  ⇒ Sammel-Issue #1199.

## Abgelöste Zusicherungen

| Spec/Test | Sagt heute | Wird |
|---|---|---|
| `docs/specs/modules/alarm_szenarien_waechter_4_9_11.md` (AC-2) — Testdatei `tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py::test_ac2_verschaerfung_innerhalb_der_sperrzeit_bleibt_ohne_alarm` (Z.90-147) | eine Verschärfung innerhalb der Sperrzeit bleibt IMMER ohne Alarm, unabhängig vom Schweregrad — hielt bewusst den Ist-Zustand fest, nicht das Soll (die Spec selbst kündigt die eigene Ablösung durch S3c bereits an) | **umgeschrieben, nicht gelöscht** — dieselbe Testdatei/dieselbe Fläche prüft künftig das Gegenteil: eine echte Verschärfung überholt die Sperrzeit (s. AC-1 dieser Spec); Grund für die Ablösung als solche kennzeichnen, damit sie nicht als „Schutz entfernt" missverstanden wird |
| `fix_2065_verschaerfung_ueberholt_sperre.md` (AC-6, „Ruhezeit bleibt unbrechbar") | gilt für den Radar-Zweig | **unberührt** — AC-12 dieser Spec sichert dieselbe Zusicherung für den Abweichungs-Zweig zusätzlich zu, keine Ablösung |
| ADR-0021, Nachtrag zu #2065/#2050 S3b | Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze und deren zwei bestehende Ausnahmen (Sperrzeit-Überholung Radar, Budget-Durchbruch Radar) | dritter Nachtrag ergänzt dieselbe Reihenfolge um die Ausnahme im Abweichungs-Zweig (AC-16) — keine Widerruf der bestehenden zwei Nachträge |
| `tests/helpers/briefing_imminent_fixtures.py::trip_change_alert_run()` — Stellvertreter „0 Wetterabrufe = gesperrt" | die Abrufzahl misst jede Sperrstufe des Trip-Änderungsalarms, weil alle vor dem Abruf abbrechen | **eingeschränkt, nicht abgeschafft** — gilt weiter für Vorlauf-Sperre (#1594), Ruhezeit und alle übrigen Stufen vor dem Abruf; gilt **nicht mehr** für die Sperrzeit, die seit dieser Scheibe nach dem Abruf entscheidet. Neuer Messweg `trip_change_alert_lauf()` (`(Abrufe, Zustellungen)`), Geltungsbereich im Modul-Docstring des Helfers vermerkt |
| `rework_1467_s4a_amtlich.md` (AC-5 zweite Hälfte) — `test_official_alert_cooldown_entkopplung.py::test_ac5_nachfolgender_aenderungsalarm_bleibt_wie_bisher_gesperrt` | „der nachfolgende Änderungsalarm ist gesperrt", gemessen als `Wetterabrufe == 0` | **Messgröße umgestellt, Zusicherung unverändert** — derselbe Test misst jetzt die ausbleibende ZUSTELLUNG bei alarmfähiger Lage; Kontroll-Nutzer stellt dieselbe Lage zu. Gegenprobe: `_is_throttled_with_cooldown → False` macht ihn rot |
| `rework_1467_s4a_amtlich.md` (AC-6) — `test_official_alert_cooldown_entkopplung.py::test_ac6_aenderungsalarm_drosselung_unveraendert` | frische Sperrzeit sperrt / keine und abgelaufene lassen durch, alle drei an der Abrufzahl gemessen | **Messgröße umgestellt, Zusicherung unverändert** — alle drei Nutzer bekommen dieselbe alarmfähige Lage und werden an der Zustellung gemessen; die beiden Durchlass-Fälle sind zugleich Positivkontrolle. Gegenprobe: `_is_throttled_with_cooldown → False` macht ihn rot |
| `feat_2050_s3b_budget_und_unterdrueckungsgrund.md` (AC-10, Trip-Änderungsalarm) — `test_alert_suppression_reason.py::test_ac10_briefing_vorlauf_am_trip_aenderungsalarm_bleibt_still` | Vorbedingung beider Trips: `Wetterabrufe == 0` | **Messgröße nur für den Kontroll-Trip umgestellt** — der Vorlauf-Trip bleibt an der Abrufzahl (Stufe sitzt weiter vor dem Abruf), der Kontroll-Trip wird an ausbleibender Zustellung + protokolliertem Grund `cooldown` gemessen. Beide bekommen dieselbe Lage, was die Grenze schärfer zieht als zuvor |

**Müssen unverändert grün bleiben** (aktive Gegenproben gegen eine zu weite Lösung, geprüft
gegen die Analyse-Messung M1/M5):

- `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py::test_ac1_zweiter_lauf_liest_den_von_lauf_eins_gebuchten_cooldown`
  (Z.105-132) — zwei Läufe mit IDENTISCHEN Werten; wird eine Implementierung gebaut, die „jeder
  Folgelauf durchbricht" statt „nur ein Rangsprung durchbricht", muss genau dieser Test rot
  werden (s. AC-2).
- `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py::test_ac7_vorbelegter_cooldown_unterdrueckt_einen_sonst_faelligen_alarm`
  (Z.323-344) — bucht die Sperrzeit über `ThrottleStore.record(...)` OHNE `urgency`; spiegelt das
  konservative „Basis fehlt ⇒ kein Durchbruch"-Verhalten (s. AC-5).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (dritter Nachtrag, nach #2065 und #2050 S3b)
- **Rationale:** ADR-0021 hält die feste Reihenfolge Ruhezeit → Sperrzeit → Tages-Obergrenze als
  geteilten Baustein für Trip und Ortsvergleich fest und trägt bereits zwei Nachträge: #2065
  (Sperrzeit-Überholung im Radar-Zweig durch quantitative Verschärfung) und #2050 S3b
  (Budget-Durchbruch durch akute Eskalation, ebenfalls Radar-Zweig, plus benannte
  Unterdrückungsgründe). Diese Scheibe überträgt beide Ausnahmen auf den Abweichungs-Zweig — mit
  einer strukturell anderen Vergleichsformel (Rangvergleich statt Faktor, weil heterogene
  Metriken statt einer einzelnen physikalischen Menge) und einem geteilten, nicht addierten
  Durchbruch-Deckel. Nach der Projektregel („Abweichung ⇒ neues ADR bzw. datierter Nachtrag")
  braucht das einen dritten, datierten Nachtrag (AC-16), einsortiert nach dem S3b-Nachtrag.
  `DeviationAlertEngine` selbst bleibt unverändert — keine neue Architektur für den geteilten
  Ortsvergleich-Baustein, nur eine Caller-seitige Ausnahme im Trip-Pfad, exakt wie schon bei
  #2065 und S3b für den Radar-Zweig.

## Changelog

- 2026-08-23: Initial spec created (aus
  `docs/context/feat-2050-s3c-abweichung-ueberholt-sperrzeit.md`, Analyse-Phase 2026-08-23,
  inkl. empirischer Messung M1-M5 gegen die echte Service-Kette).
