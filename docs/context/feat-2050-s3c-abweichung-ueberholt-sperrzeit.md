# Context: feat-2050-s3c-abweichung-ueberholt-sperrzeit

Issue #2050, Scheibe S3c · Anforderung **A-3** („Eine Verschaerfung ueberholt jede Sperre")
· Szenario 4 der Zwoelf-Szenarien-Tabelle.
Kartierung am 2026-08-23 auf `d6af0666` (Stand nach S3b), alle Aussagen mit Datei:Zeile belegt.

## Request Summary

Im **Abweichungs-Zweig** (`forecast_change`) bricht eine aktive Sperrzeit den Alarm heute hart
ab — ohne jeden Blick auf den Schweregrad. Eine Lage, die sich von „maessig" auf „schwer"
verschaerft, wird genauso geschluckt wie eine Wiederholung derselben Lage. S3c soll dort
dieselbe Eskalations-Ausnahme herstellen, die #2065 fuer den **Radar**-Zweig bereits gebaut hat.

## Der Ist-Zustand: die Gate-Kette des Abweichungs-Zweigs

`TripAlertService.check_and_send_alerts()` — `src/services/trip_alert.py:308-582`,
in Ausfuehrungsreihenfolge:

| # | Gate | Zeile | Bei Block | Protokolliert? |
|---|---|---|---|---|
| 1 | Kanal-Guard (kein SMTP **und** kein Telegram) | :331-333 | `return False` | nein |
| 2 | Aktive-Regeln-Guard | :345-368 | `return False` | nein |
| 3 | Ruhezeit | :372-380 | `return False` | ja — `REASON_QUIET_HOURS` |
| 4 | Briefing steht unmittelbar bevor | :388-390 | `return False` | **nein** |
| 5 | **Sperrzeit / Cooldown** ← Ziel von S3c | :393-400 | `return False` | ja — `REASON_COOLDOWN` |
| 6 | Tages-Obergrenze (`reason="forecast_change"`) | :405-414 | `return False` | ja — `REASON_DAILY_LIMIT` |
| 7 | Wetter-Abruf `_fetch_fresh_weather` (Methode :2053) | :417-422 | `return False` | nein |
| 8 | `DeviationAlertEngine.evaluate()` | :449-455 | — | — |
| 9 | Kein Treffer (`to_report` leer) | :456-471 | `return False` | **nein** (nur `logger.debug`) |
| 10 | Versand `_send_alert` | :500-503 | bei `not sent` :546-552 `return False` | nein |
| 11 | Erfolg: Protokoll :515-545 · Melde-Gedaechtnis :556-563 · **Throttle-Record :566** · Tageszaehler :568-570 · Anker :577-580 | | `return True` | ja |

## Der strukturelle Kern des Problems

**Die Schwere der neuen Lage entsteht erst NACH dem Sperrzeit-Gate.**

- Sperrzeit-Gate: `:393`
- Wetter-Abruf: `:417`
- Schwere-Bildung: `:449-455` (`DeviationAlertEngine.evaluate()` → `EvaluationResult.severity`)

Zum Zeitpunkt der Sperrprueffung existiert die Groesse strukturell nicht. Ein Parameter am Gate
kann sie nicht dorthin tragen. Genau dieselbe Falle wie in #2065 und #2050 S3b.

## Das tragfaehige Muster steht schon da (#2065, Radar-Zweig)

Nicht „Fetch vor das Gate ziehen", sondern: **Gate laeuft unveraendert, der Aufrufer merkt sich
den Block und entscheidet nach dem Abruf neu.**

| Baustein | Ort |
|---|---|
| `_sperrzeit_offen = not gate.allowed and gate.reason == REASON_COOLDOWN` | `trip_alert.py:1459-1461` |
| harter Stop nur noch fuer die Ruhezeit | `:1473` |
| nach dem Abruf: `if _sperrzeit_offen:` → Basis lesen, vergleichen, sonst `_protokolliere_radar_unterdrueckung` + `continue` | `:1604-1632` |
| **Tages-Obergrenze DANACH erneut pruefen** (sonst wird sie vom Durchbruch stillschweigend mit-uebersprungen) | `:1633-1654` |
| Vergleichsformel `radar_overtakes_cooldown(basis_mm, menge_mm)` — Faktor 2,0 **und** absolute Untergrenze 2,0 mm, `None` ⇒ `False` | `alert_gate.py:433-459` |
| Vergleichsbasis aus dem Sperrtopf `last_nowcast_precip_mm()` | `alert_gate.py:461-473` |
| Speicherung der Basis: `ThrottleStore.record(scope, key, now, precip_mm=None)` schreibt `{"at": iso, "precip_mm": float|null}` | `throttle_store.py:98-110`, Lesepfad `:73-83` |

**Bewusste Verortung:** die Formel liegt NICHT im geteilten `check_nowcast_gate()`, sondern im
Trip-Pfad-Aufrufer — damit der PO-zurueckgestellte Ortsvergleich die Ausnahme nicht automatisch
erbt (`alert_gate.py:448-451`). Fuer S3c gilt dasselbe: die Ausnahme gehoert in
`trip_alert.check_and_send_alerts`, **nicht** in `DeviationAlertEngine` — die Engine ist mit dem
Ortsvergleich geteilt (`compare_alert.py:509`).

## Was im Abweichungs-Zweig fehlt

### 1. Es gibt keine gespeicherte Vergleichsbasis

`ThrottleStore.record("trip", trip.id, now)` wird an **beiden** Schreibstellen ohne vierten
Parameter gerufen — `trip_alert.py:566` (Abweichung) und `trip_alert.py:2480` (amtlicher Zweig).
`precip_mm` bleibt strukturell immer `None`; `last_sent_with_precip("trip", key)` liefert heute
stets `(timestamp, None)`.

⇒ **Kein Speicher haelt fest, wie schwer der Alarm war, der die laufende Sperrzeit gesetzt hat.**
Ohne eine zusaetzlich geschriebene Vergleichsgroesse kann eine Ueberholung nie greifen.

⚠️ **Beide Schreiber teilen denselben Schluessel** (`scope="trip"`, `key=trip.id`): ein
zugestellter **amtlicher** Alarm setzt dieselbe Sperruhr, die den Abweichungs-Zweig gatet. Fuer
den amtlichen Schreiber gibt es keine Abweichungs-Schwere ⇒ fehlende Basis ⇒ konservativ kein
Durchbruch. Direktes Gegenstueck zu AC-8 aus #2065 (Kurzfristhinweis bucht ohne Menge).

### 2. Der Schwere-Begriff existiert, der VERGLEICH fehlt

Die ordinale Ableitung ist vollstaendig vorhanden und geteilt:

- `ChangeSeverity` — `src/app/models.py:568-573`, Enum `MINOR`/`MODERATE`/`MAJOR`
- `DeviationAlertEngine._highest_severity()` — `deviation_alert_engine.py:250-262`, `max()` ueber
  `{MINOR:0, MODERATE:1, MAJOR:2}`, uebersetzt nach `"LOW"/"MODERATE"/"HIGH"`
- `alert_urgency.urgency_from_changes(changes)` — `alert_urgency.py:47-52`, delegiert 1:1 dorthin
- `alert_urgency.exceeds(a, b)` — `:63-69`, echtes `>` auf `_RANK = {LOW:0, MODERATE:1, HIGH:2}`

Genutzt wird das im Abweichungs-Zweig heute **nur nachgelagert**: `trip_alert.py:520-521` bildet
die Dringlichkeit erst beim Schreiben des Protokolleintrags, **nach** erfolgtem Versand.
`alert_urgency.exceeds()` wird im Abweichungs-Zweig **nirgends** aufgerufen — nur im Radar-Zweig
(`alert_gate.py:752`) und im Budget-Zweig (`alert_daily_limit.py:158`).

Hinweis: `trip_alert.py` liest `eval_result.severity` **nirgends** (per grep verifiziert) —
derselbe Wert wird bei :521 aus `urgency_from_changes(to_report)` neu gebildet.

**Unterschied zu #2065:** dort ist die Vergleichsgroesse EINE physikalische Menge (mm/h), die
eine Faktor-Formel erlaubt. Der Abweichungs-Zweig traegt potenziell mehrere heterogene Metriken
gleichzeitig (Temperatur, Wind, Regen …) — ein Faktor darauf ist nicht definierbar. Das
naheliegende Muster ist der **Rangvergleich** ueber `alert_urgency.exceeds()`, exakt wie
`alert_daily_limit.escalation_breaks_through()` (`:124-158`) ihn fuer das Budget schon nutzt.

### 3. Die Waende hinter der Sperrzeit — anders als im Radar-Zweig

| Wand | Radar-Zweig | Abweichungs-Zweig |
|---|---|---|
| Entdopplung `check_event_identity_gate` | ja, `:1915` — brauchte in #2065 die `quantitative_escalation`-Ausnahme (`alert_gate.py:713, :752`) | **existiert nicht** — im gesamten Abweichungs-Zweig kein Aufruf (belegt: nur `:1915` Radar, `:2368`/`:2495` amtlich) |
| Melde-Gedaechtnis-Dedup | — | `_filter_against_alert_state`, `deviation_alert_engine.py:233-248`, laeuft **innerhalb** `evaluate()` |
| Tages-Obergrenze | nach dem Durchbruch erneut geprueft, `:1633-1654` | Gate 6, steht **hinter** der Sperrzeit ⇒ wird heute nie erreicht |

**Wichtig fuer den Zuschnitt:** Der Dedup im Abweichungs-Zweig ist **deltabasiert**, nicht
identitaetsbasiert: `abs(change.new_value - last_reported_value) >= change.threshold`
(`deviation_alert_engine.py:246`). Eine echte Verschaerfung erzeugt ein groesseres Delta und
sollte diese Wand daher von selbst passieren. **Das ist eine Vermutung aus der Lektuere und in
der Analyse-Phase zu messen** — #2065 hat genau an dieser Stelle gelernt, dass hinter der
Sperrzeit eine zweite Wand steht, die den roten Test gruen zu machen verhindert und bloss den
Unterdrueckungsgrund wechselt.

Die reale zweite Wand duerfte hier die **Tages-Obergrenze** sein: sie steht direkt hinter dem
Sperrzeit-Gate, und der Eskalations-Durchbruch aus S3b (`_eskalation_bricht_budget`,
`trip_alert.py:1320-1341`) ist fuer `reason="forecast_change"` **nicht verdrahtet**.

## Bestandstests

### Umzudrehen — genau EINER

`tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py::test_ac2_verschaerfung_innerhalb_der_sperrzeit_bleibt_ohne_alarm`
(Z.90-147, aus S3a / `eed94a8f`). Der Dateikopf (Z.21-28) sagt die AblOese selbst an:
Lauf 1 (2,0 → 18,0 mm) bucht die Sperrzeit, Lauf 2 nach 30 Min mit staerkerem Delta
(2,0 → 45,0 mm) erwartet heute `triggered_count == 0` (Z.133-137) und einen **unveraenderten**
`ThrottleStore.last_sent` (Z.139-145). Nach S3c: `== 1` und ein **neu gebuchter** Zeitstempel.

### Muessen gruen bleiben — aktive Gegenproben gegen eine zu weite Loesung

- `test_alarm_pruefstrecke_selbstschutz.py::test_ac1_zweiter_lauf_liest_den_von_lauf_eins_gebuchten_cooldown`
  (Z.105-132) — beide Laeufe mit **identischen** Werten (2,0 → 18,0). Wird eine Implementierung
  gebaut, die „jeder Folgelauf durchbricht" statt „nur eine deutliche Verschaerfung durchbricht",
  muss genau dieser Test rot werden.
- `test_alarm_pruefstrecke_selbstschutz.py::test_ac7_vorbelegter_cooldown_unterdrueckt_einen_sonst_faelligen_alarm`
  (Z.323-344) — bucht die Sperrzeit **ohne** Vergleichsgroesse. Spiegelt S3c das konservative
  Radar-Verhalten („Basis fehlt ⇒ kein Durchbruch"), bleibt der Test korrekt bei `0`.

Unbeteiligt: `test_alarm_szenario_mandantentrennung.py`, `test_alert_log_ereignisgroessen.py`,
`test_alarm_szenario_gewitter_vorverlegung.py` (nutzen `zweig="deviation"`, aber ohne Sperrbezug).

### Vorlage fuer die neuen Tests

`tests/tdd/test_radar_cooldown_overtake.py` (14 Tests, #2065) und
`tests/tdd/test_daily_budget_escalation.py` (7 Tests, S3b) — beide ueber die
`AlarmPruefstrecke` (#2050 S1) gegen die echte Service-Kette, kein Mock.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py` | Gate-Kette :308-582 (Wirkort) · Cooldown-Adapter :1106 · Throttle-Schreiber :566 und :2480 · Radar-Vorlage :1459-1461/:1604-1654 · Budget-Bruecke :1320-1341 |
| `src/services/alert_gate.py` | Vorlage `radar_overtakes_cooldown` :433-459, `last_nowcast_precip_mm` :461-473 · Verortungs-Begruendung :448-451 |
| `src/services/throttle_store.py` | Eintragsformat :52 · `record(..., precip_mm=None)` :98-110 · `last_sent_with_precip` :73-83 — hier entsteht die neue Vergleichsbasis |
| `src/services/alert_urgency.py` | `exceeds` :63-69 · `urgency_from_changes` :47-52 · `highest_urgency` |
| `src/services/alert_daily_limit.py` | `escalation_breaks_through` :124-158 · Deckel `_MAX_ESCALATION_BREAKTHROUGHS = 1` :117-121 · `increment` :163-210 |
| `src/services/deviation_alert_engine.py` | `evaluate` :264-323 · `_highest_severity` :250-262 · Dedup `_filter_against_alert_state` :233-248 · **geteilt mit dem Ortsvergleich** |
| `src/app/models.py` | `ChangeSeverity` :568-573, `WeatherChange` |
| `docs/adr/0021-shared-deviation-alert-engine.md` | schreibt die Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze fest (:27-29, :87, :118f, :214-216); Nachtrag #2065 :256-283, Nachtrag S3b :284-320 |
| `tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py` | der umzudrehende Waechter |
| `tests/helpers/alarm_pruefstrecke.py` | Pruefstrecke aus S1 |

## Dependencies

- **Upstream:** `ThrottleStore` (Sperrtopf `trip`), `AlertStateService` (Melde-Gedaechtnis, Datei
  je Trip, Schluessel `metric:segment_id` → `{last_reported_value, reported_at}`),
  `alert_daily_limit` (Zaehler je Zone), `DeviationAlertEngine`, `alert_urgency`.
- **Downstream:** alle vier Kanaele ueber `_send_alert`; `alert_log` (S6-Groessen); der
  **amtliche** Zweig teilt sich den Sperrtopf-Schluessel.

## Existing Specs

- `docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md` — AC-1..AC-14, Radar-Vorlage
- `docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md` — AC-15..AC-22, enthaelt
  die Vorlage fuer den Abschnitt „Abgeloeste Zusicherungen" (:274-280)
- `docs/specs/modules/alarm_pruefstrecke.md` — S1
- `docs/specs/modules/rework_1467_s3_nowcast.md` — nur die Grundreihenfolge, keine Ausnahmen

## Risks & Considerations

1. **Mehrkosten am Wetter-Abruf.** Ein geoeffnetes Sperrzeit-Gate heisst: bei jedem Prueflauf
   innerhalb der Sperrzeit wird abgerufen, um ueberhaupt vergleichen zu koennen. #2065 hat das
   fuer den Radar-Zweig auf bis zu 7 Abrufe je Sperrfenster und Tour beziffert (Tagesbudget
   9000). Fuer den Abweichungs-Zweig ist die Zahl neu zu bestimmen.
2. **Die Tages-Obergrenze muss nach dem Durchbruch erneut geprueft werden** — sonst
   ueberspringt der Sperrzeit-Durchbruch sie stillschweigend mit (Lehre `:1633-1654`).
   Ob dabei die S3b-Ausnahme fuer `forecast_change` mitgezogen wird, ist eine Spec-Frage.
3. **Die Ausnahme darf nicht in `DeviationAlertEngine` landen** — sonst erbt der
   PO-zurueckgestellte Ortsvergleich sie automatisch.
4. **ADR-0021 braucht einen datierten Nachtrag** (dritter nach #2065 und S3b); die Spec braucht
   eine Tabelle „Abgeloeste Zusicherungen" fuer AC-2 aus S3a.
5. **Zwei offene Produktfragen** (aus dem Issue-Kommentar vom 22.08., in der Spec zu
   entscheiden): (a) Was heisst „deutlich schlimmer" hier — Rangsprung ueber
   `alert_urgency.exceeds`, oder braucht es eine Mindest-Delta-Groesse? (b) Gilt die Ueberholung
   nur gegen die Sperrzeit, oder auch gegen die Tages-Obergrenze?
6. **Nebenbefund (nicht zwingend in Scope):** Faellt ein Alarm im Abweichungs-Zweig am
   Melde-Gedaechtnis-Dedup (`suppressed_reason="alert_state_dedup"`, `:456-471`), entsteht
   **kein** Protokolleintrag — nur `logger.debug`. Der Radar-Zweig protokolliert denselben
   fachlichen Fall als `REASON_DOUBLE_ALERT_GUARD` (`trip_alert.py:1779`). Das ist eine
   verbliebene D-2-Luecke aus S3b. Triage nach CLAUDE.md: Sammel-Issue #1199, sofern die Spec
   sie nicht bewusst mitnimmt.
7. **Rollout waehrend laufender Tour** (KHW-Start 2026-08-23). Die Aenderung oeffnet eine
   bislang harte Sperre — eine zu weite Loesung erzeugt Alarm-Schwaelle. Die beiden
   gruen-bleibenden Gegenproben oben sind der Schutz davor.

---

# Analysis

Phase 2, 2026-08-23. Drei Kartierungen plus **eine empirische Messung** gegen die echte
Service-Kette (Sonde im Session-Scratchpad, drei Laeufe gruen, kein Produktivcode angefasst).

## Type

**Feature** — die Anforderung A-3 ist heute im Abweichungs-Zweig unerfuellt; es ist kein
Regressionsdefekt, sondern eine nie gebaute Ausnahme.

## Gemessen, nicht gelesen

Die Vorgaenger-Lehre aus #2065 lautet: hinter der Sperrzeit steht eine zweite Wand, und ein
reiner Sperrzeit-Fix wechselt bloss den Unterdrueckungsgrund. Diese Frage wurde hier
**gemessen**, nicht aus der Lektuere geschlossen.

| Messpunkt | Ergebnis |
|---|---|
| **M1 — Melde-Gedaechtnis-Dedup** ist **keine** zweite Wand | Nach Sperrzeit-Ablauf: Verschaerfung 2,0 → 45,0 mm ⇒ `triggered_count = 1`; identische Wiederholung 2,0 → 18,0 mm ⇒ `triggered_count = 0`. Der Dedup ist deltabasiert (`deviation_alert_engine.py:246`) und laesst eine echte Verschaerfung von selbst durch. |
| **M2 — die Tages-Obergrenze IST die zweite Wand** | Zaehler erschoepft, Sperrzeit abgelaufen, echte Eskalation 2,0 → 45,0 mm ⇒ `triggered_count = 0`, Protokolleintrag `reasons=('daily_limit',)`. Ein Fix, der nur `:393-400` oeffnet, wechselt den Grund von `cooldown` auf `daily_limit`. |
| **M3 — das effektive Limit ist 2, nicht 4** | `is_allowed(reason="forecast_change")` rechnet `limit − _FORECAST_CHANGE_RESERVE[limit]` (`alert_daily_limit.py:105, :108-123`). Tier `standard`: Limit 4, Reserve 2 ⇒ **2 Abweichungs-Alarme pro Tag und Zone**. Gemessen: bei Zaehler 2 ist `forecast_change` gesperrt, `None` noch erlaubt. |
| **M4 — Fetch-Mehrkosten: 7 zusaetzliche Abrufe je Sperrfenster und Tour** | Scheduler-Takt `*/15` (`internal/scheduler/scheduler.go:192`), Default-Sperrzeit 120 Min (`throttle_hours=2`, `trip_alert.py:245`, Fallback `:1121-1124`). 120/15 = 8 Laeufe, der erste liefert ohnehin. Heute sind es **0**, weil der Abruf hinter dem Gate liegt. Deckungsgleich mit der #2065-Zahl. |
| **M5 — geteilter Sperrtopf bestaetigt** | Ein von aussen gesetzter Eintrag `("trip", trip.id)` (simuliert den amtlichen Schreiber `:2480`) sperrt den Abweichungs-Lauf: `triggered_count = 0`, Grund `cooldown`. |

**Folge aus M2:** Die Ausnahme muss **beide** Waende adressieren. Sonst ist A-3 im
Abweichungs-Zweig weiterhin nur zu einem Drittel erfuellt — genau der Zustand, den #2065 fuer
den Radar-Zweig ausdruecklich als „A-3 nur zu 2/3" in seiner Spec vermerkt hat.

## Technical Approach

**1. Vergleichsbasis — additives Feld im Sperrtopf.**
`ThrottleStore.record()` bekommt einen vierten Parameter `urgency: Optional[str] = None`; der
Eintrag wird `{"at": iso, "precip_mm": …, "urgency": str|null}`. Lesepfad als Schwester zu
`last_sent_with_precip()` (`throttle_store.py:73-83`). Altformat bleibt lesbar, Schreibweg ist
Read-Modify-Write.
Verworfen: eine eigene Vergleichsbasis nach dem `max_urgency_sent`-Muster
(`alert_daily_limit.py:124-158`) — die ist **Tag+Zone**-skaliert und wird am Ortstag
zurueckgesetzt, waehrend die Sperrzeit-Basis ein Momentanwert je Sperrschluessel ist. Andere
Semantik ⇒ zweiter paralleler Speicher ohne Gegenwert.

**2. Vergleichsformel — ordinaler Rangsprung.**
Neue Funktion `deviation_overtakes_cooldown(*, basis_urgency, urgency)` als Schwester von
`radar_overtakes_cooldown` in `alert_gate.py` (nicht in `check_nowcast_gate`, dieselbe
Verortungs-Begruendung `:448-451`): `False` bei fehlender Basis, sonst
`alert_urgency.exceeds(urgency, basis_urgency)` (`:63-69`).
Kein Faktor-Kanal wie im Radar-Zweig: dort gibt es EINE physikalische Menge, hier mehrere
heterogene Metriken (°C, km/h, mm) ohne gemeinsame Skala.
**Bekannte Grenze, bewusst nicht gefangen:** die Skala saettigt bei `HIGH`. Eine Lage, die von
`HIGH` auf noch schlimmer geht, erzeugt keinen Rangsprung und bricht nicht durch. #2065 hatte
dasselbe Saettigungsproblem und loeste es mit dem zusaetzlichen mm-Kanal
(`alert_gate.py:746-760`) — hier fehlt dafuer die Normierung. Gehoert als benannte Grenze in
Spec und ADR-Nachtrag, nicht in diese Scheibe.

**3. Kontrollfluss — das #2065-Muster, an zwei getrennte Gates angepasst.**
Der Radar-Zweig hat EIN kombiniertes Gate mit `gate.reason`; der Abweichungs-Zweig hat zwei
sequentielle Gates. Skizze:

- `:393` — `_sperrzeit_offen = self._is_throttled_with_cooldown(trip)` statt hartem `return False`
- `:405` — Tages-Obergrenze nur pruefen, wenn `not _sperrzeit_offen` (sonst spaeter, nach dem Abruf)
- `:417` — Abruf laeuft jetzt auch bei offener Sperrzeit; das ist die Voraussetzung fuer den Vergleich
- `:449` — `evaluate()`, danach die Dringlichkeit **einmal** bilden (`urgency_from_changes(to_report)`)
  und an die heutige Spaetberechnung `:520-521` weiterreichen statt sie doppelt zu rechnen
- danach: bei `_sperrzeit_offen` Basis lesen, vergleichen; keine Ueberholung ⇒ **derselbe**
  Protokollaufruf wie heute (`REASON_FORECAST_CHANGE` / `REASON_COOLDOWN`), nur zeitlich
  verschoben, dann `return False`
- bei Ueberholung: Tages-Obergrenze **real nachholen** (sonst ueberspringt der Durchbruch sie
  still — Lehre `:1633-1654`)

`DeviationAlertEngine` bleibt unangetastet — sie ist mit dem PO-zurueckgestellten Ortsvergleich
geteilt (`compare_alert.py:509`).

**4. Tages-Obergrenze — die S3b-Bruecke wird mitgezogen.**
Nach dem Sperrzeit-Durchbruch darf ein erschoepftes Budget ueber die bestehende Bruecke
`_eskalation_bricht_budget` (`trip_alert.py:1320-1341` → `alert_daily_limit.escalation_breaks_through`)
ebenfalls durchbrochen werden. Begruendung: die Bruecke ist generisch (Zone + Dringlichkeit,
kein Radar-Spezifikum) und existiert bereits; ohne sie kaeme dieselbe Schwere im Radar-Zweig
durch und im Abweichungs-Zweig nicht — genau die Asymmetrie zwischen den Zweigen, die S3b
schliessen sollte. Das Risiko ist gedeckelt: `_MAX_ESCALATION_BREAKTHROUGHS = 1`
(`alert_daily_limit.py:117-121`) gilt **pro Zone und Tag ueber beide Zweige hinweg** — Radar und
Abweichung teilen sich denselben einen Durchbruch, sie addieren sich nicht.

## Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/throttle_store.py` | MODIFY | vierter Parameter `urgency`, Lesepfad `last_sent_with_urgency` |
| `src/services/alert_gate.py` | MODIFY | `deviation_overtakes_cooldown` + Basis-Leser |
| `src/services/trip_alert.py` | MODIFY | Umbau der Gate-Kette `:393-414`, Entscheidung nach `evaluate()`, Budget-Nachpruefung, `record(..., urgency=…)` bei `:566` |
| `tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py` | MODIFY | AC-2 aus S3a umdrehen |
| `tests/tdd/test_deviation_cooldown_overtake.py` | CREATE | neue Waechter, Vorlage `test_radar_cooldown_overtake.py` |
| `docs/adr/0021-shared-deviation-alert-engine.md` | MODIFY | dritter datierter Nachtrag (nach #2065 und S3b) |
| `docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md` | CREATE | Spec inkl. Tabelle „Abgeloeste Zusicherungen" |

**Unberuehrt:** `deviation_alert_engine.py` · `compare_*.py` · der Radar-Block
`check_radar_alerts` :1205-1797 · `alert_daily_limit.py` (nur Nutzung, keine Aenderung) ·
`alert_log.py` · Go-Seite.

## Scope Assessment

- Dateien: 3 Produktivcode, 2 Test, 2 Doku
- Geschaetzte LoC: **≈ +335 / −25** ⇒ ueber dem 250-Limit. `loc_limit_override 500` vor
  `/40-tdd-red` setzen (#2065 und S3b liefen ebenso).
- **Risk Level: HIGH** — kritischer Pfad, oeffnet eine bislang harte Sperre, Rollout waehrend
  einer laufenden Tour.

## Risks

1. **Alarm-Schwall bei zu weiter Loesung.** Schutz sind nicht die Formel, sondern die zwei
   gruen bleibenden Gegenproben: identische Wiederholung darf **nicht** durchbrechen
   (`test_alarm_pruefstrecke_selbstschutz.py` Z.105-132), fehlende Vergleichsbasis darf
   **nicht** durchbrechen (ebd. Z.323-344).
2. **7 zusaetzliche Wetter-Abrufe je Sperrfenster und Tour** (M4) — gegenueber heute 0. Bei
   Tagesbudget 9000 unkritisch, gehoert aber beziffert in die Spec.
3. **Der amtliche Zweig schreibt weiter ohne Dringlichkeit** in denselben Sperrtopf
   (`:2480`). Er bleibt unveraendert; sein Eintrag traegt `urgency: null` und faellt damit
   konservativ als „keine Basis" durch. Gegenstueck zu AC-8 aus #2065.
4. **ADR-0021 schreibt die Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze fest** (:27-29, :87,
   :118f, :214-216). Der Umbau beruehrt sie ⇒ datierter Nachtrag ist Pflicht, kein Nice-to-have.
5. **Die Ruhezeit bleibt unbrechbar** — PO-Ablehnung #1955 gilt unveraendert. Gate 3 wird nicht
   angefasst.

## Open Questions

Beide werden in der Spec **entschieden vorgelegt**, nicht als Frage weitergereicht:

- [x] „Deutlich schlimmer" = ordinaler Rangsprung ueber `alert_urgency.exceeds`; Saettigung bei
      `HIGH` bewusst nicht gefangen und als Grenze dokumentiert.
- [x] Die Ueberholung gilt gegen Sperrzeit **und** Tages-Obergrenze (ueber die bestehende
      S3b-Bruecke, gedeckelt auf einen Durchbruch pro Zone und Tag), **nicht** gegen die Ruhezeit.

## Nebenbefund

Faellt ein Alarm im Abweichungs-Zweig am Melde-Gedaechtnis-Dedup
(`suppressed_reason="alert_state_dedup"`, `:456-471`), entsteht **kein** Protokolleintrag — nur
`logger.debug`. Der Radar-Zweig protokolliert denselben fachlichen Fall als
`REASON_DOUBLE_ALERT_GUARD` (`:1779`). Verbliebene D-2-Luecke aus S3b. Nicht in dieser Scheibe;
Triage nach CLAUDE.md ⇒ Sammel-Issue #1199.
