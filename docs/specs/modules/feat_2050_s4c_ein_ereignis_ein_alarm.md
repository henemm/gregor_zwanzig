---
entity_id: feat_2050_s4c_ein_ereignis_ein_alarm
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: feat-2050-s4c-ein-ereignis-ein-alarm
version: "1.0"
tags: [alarm, entdopplung, ereignis-identitaet, abweichung, nowcast]
---

# Ein Ereignis, ein Alarm — Abweichungs-Zweig anschließen (Issue #2050, Scheibe S4c)

## Approval

- [x] Approved (PO, 2026-08-23)

## Purpose

Issue #2050, Szenario 5, Anforderung **C-2**: Melden amtliche Warnung, Vorhersage-Abweichung
(Δ) und Radar dieselbe Gewitter-/Regenzelle, soll **eine** Nachricht herausgehen statt zwei bis
drei — danach nur noch Verschärfungen. Die quellenübergreifende Ereignis-Identität
(`check_event_identity_gate()`/`record_event_identity()`, #1467 S4b, erweitert #2018/#2065) ist
bereits gebaut und in Betrieb, gilt aber bislang nur zwischen **Radar** und **amtlich**. Der
**Abweichungs-Zweig** ruft sie weder zum Prüfen noch zum Registrieren auf und meldet an ihr
vorbei — dokumentierte, bewusst zurückgestellte Lücke (`rework_1467_s4b_entdopplung.md:382`).
Diese Scheibe schließt den Δ-Zweig an denselben, unveränderten Mechanismus an: ein dritter
Auflösungsweg von Metrik-Änderungen zur Gefahrenklasse, ein aus Segmentfenstern gebildeter
Zeitbezug (statt eines meist fehlenden Einzelzeitpunkts) und ein expliziter Quellenvermerk
`"deviation"`. Zugleich löst sie den seit #818 halb toten Doppel-Alarm-Wächter
(`trip_alert.py:1835-1861`) ab, der dieselbe Paarung bisher einseitig und ohne
Eskalations-Ausnahme behandelt hat.

## Non-Goals

- **Ortsvergleich.** `compare_alert.py` bleibt unangetastet (Entscheidung 3) — Ortsvergleich-
  Themen sind PO-seitig zurückgestellt. Die Anschlussstellen sind kartiert
  (`docs/context/feat-2050-s4c-ein-ereignis-ein-alarm.md`, Entscheidung 3) und gehen als benannte
  Folgescheibe ins Issue. AC-19 sichert die Unberührtheit als Wächter zu.
- **Keine neuen Alarmarten.** Es entsteht kein neuer Alarm-Trigger, nur eine zusätzliche
  Anbindung des Δ-Zweigs an einen bestehenden Entdopplungs-Mechanismus.
- **Keine Änderung an Sperrzeit, Tagesbudget oder Ruhezeit.** Diese Stufen (#2065, #2050 S3b/S3c)
  laufen VOR der Ereignis-Identität und bleiben strukturell unverändert.
- **Kein Flicken des toten `precip:`-Schlüssels** im Doppel-Alarm-Wächter (Befund D). Der
  Wächter wird abgelöst, nicht repariert (Entscheidung 2) — ein bloßer Namens-Fix würde eine seit
  Jahren stumme Bremse ohne Eskalations-Ausnahme scharf schalten.
- **Keine Aufteilung gebündelter Meldungen in Teilnachrichten.** `to_report` bleibt eine
  atomare Sendeeinheit; es gibt kein Muster, einzelne Änderungen vor dem Versand
  herauszufiltern (Entscheidung 1).

## Source

- **File:** `src/services/alert_gate.py` — `resolve_hazard_class()` (`:547`, dritter
  Auflösungsweg über Metrik-Liste), `check_event_identity_gate()` (`:736`, expliziter
  `source`-Parameter, erweiterte Nachtrags-Richtung), `record_event_identity()` (`:823`,
  expliziter `source`-Parameter statt Ableitung aus `point_at`)
- **File:** `src/services/trip_alert.py` — `check_and_send_alerts()` (`:310-657`, Gate-Aufruf vor
  `_send_alert` bei `:558`, Registrierung nach erfolgreicher Zustellung bei `:617`), Radar-Zweig
  `check_radar_alerts()` (`:1990-2039`, quellenabhängige Nachtrags-Formulierung), Doppel-Alarm-
  Wächter (`:1835-1861`, ENTFERNT)
- **File:** `src/output/renderers/email/undelivered_hint.py` — `_REASON_LABELS`/`_REASON_BLOCK`
  (`:48-77`, neuer Eintrag `event_duplicate`)
- **Identifier:** siehe Implementation Details

Schicht: ausschließlich Python-Core (`src/services/`, `src/output/renderers/email/`). Kein Go-,
kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~+150 / −30 (Produktivcode + Tests, ohne Doku) — voraussichtlich innerhalb des
  250-LoC-Standardlimits; falls überschritten `loc_limit_override 500` vor `/40-tdd-red` setzen
- **Files:** 3 Produktivdateien (`alert_gate.py`, `trip_alert.py`, `undelivered_hint.py`) + 3
  Testdateien (1 CREATE, 2 MODIFY) + 1 ADR-Nachtrag
- **Effort:** high
- **Risiko:** HIGH — es entsteht eine neue Unterdrückungsregel im Abweichungs-Zweig, und die
  Tour des PO läuft bereits (Start 2026-08-23)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_gate.py::check_event_identity_gate`/`record_event_identity` | function | Bestehender, unveränderter Kernmechanismus — wird um einen dritten Aufrufer (Δ-Zweig) UND einen expliziten `source`-Parameter erweitert |
| `src/services/alert_gate.py::resolve_hazard_class` | function | Bekommt einen dritten Auflösungsweg über eine Metrik-Liste; Radar (`is_convective`) und amtlich (`hazard`) bleiben unverändert |
| `src/services/alert_gate.py::_find_matching_entry`/`_times_overlap`/`_covers_materially_more` | function | Unverändert wiederverwendet — Fail-soft- und V1-Verhalten gilt automatisch auch für Δ-Kandidaten |
| `src/services/alert_urgency.py::exceeds`/`urgency_from_changes`/`highest_urgency` | function | Geteilte Rangordnung — dieselbe Dringlichkeit, die bereits Sperrzeit (#2050 S3c) und Tagesbudget (#2050 S3b) entscheidet, wird für die Eskalations-Prüfung (V2) wiederverwendet, nicht neu berechnet |
| `src/services/trip_alert.py::check_and_send_alerts` | method | Δ-Zweig — neuer Gate-Aufruf vor `_send_alert`, neue Registrierung nach erfolgreicher Zustellung, Entfernung des Doppel-Alarm-Wächters |
| `src/services/trip_alert.py::check_radar_alerts` | method | Bestehender Aufrufer der Ereignis-Identität — Nachtrags-Formulierung wird quellenabhängig statt hartkodiert „amtlich" |
| `src/services/alert_log.py::REASON_EVENT_DUPLICATE`/`append_suppressed_entry`/`append_entry` | constant/function | Bestehender Grund-Code und Protokollpfad — kein neuer Code, nur ein neuer Aufrufer |
| `src/services/deviation_alert_engine.py::evaluate` | function | Bleibt UNVERÄNDERT — mit dem PO-zurückgestellten Ortsvergleich geteilt (`compare_alert.py:509`); die Ereignis-Identität wird ausschließlich im Trip-Caller angeschlossen |
| `src/services/compare_alert.py::check_all_compare_presets`/`_evaluate_one_location` | function | Bleibt UNVERÄNDERT (Non-Goal) — AC-19 sichert das als Wächter zu |
| `src/output/renderers/email/undelivered_hint.py::_REASON_LABELS`/`_REASON_BLOCK` | constant | Neuer Eintrag `event_duplicate` → Block „ZURÜCKGEHALTEN", analog dem bestehenden Eintrag `double_alert_guard` (#2050 S3b) |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke` | test helper | Zeitreihen-Harness gegen die echte Service-Kette (#2050 S1) — Werkzeug für alle Mehrläufer-Szenarien dieser Spec |
| `docs/adr/0021-shared-deviation-alert-engine.md` | doc | Trägt bereits Nachträge zu #2018 (Nachtragsform), #2065 und #2050 S3c (Sperrzeit-Überholung); braucht einen weiteren, datierten Nachtrag für den Δ-Anschluss und den expliziten `source`-Parameter |

## Implementation Details

### 1. Dritter Auflösungsweg — Metrik-Liste statt `is_convective`/`hazard`

`resolve_hazard_class()` bekommt einen dritten, optionalen Parameter `metrics: Optional[Iterable[str]]
= None`. Neue Konstante `_WET_METRICS = frozenset({"precip_sum_mm", "precip_heavy_onset_utc",
"thunder_level_max", "thunder_onset_utc"})` — eigener Kanon, NICHT identisch mit `_WET_HAZARDS`
(das sind amtliche Hazard-**Strings**, ein anderer Namensraum). Regel (Entscheidung 1): die
Klasse ist nur dann `"wet"`, wenn die übergebene Metrik-Liste nicht leer ist UND **jede** Metrik
in ihr zum `_WET_METRICS`-Kanon gehört; sonst `None`. Schnee-Metriken (`snow_depth_cm`,
`snow_new_sum_cm`, `snowfall_limit_m`) gehören ausdrücklich nicht dazu (AC-7) — physikalisch
Niederschlag, aber außerhalb des T2-Kanons.

### 2. Zeitintervall aus Segmentfenstern statt `occurred_at`

`WeatherChange.occurred_at` ist in drei von vier Erzeugungspfaden `None` (Befund B) und daher als
Zeitbezug ungeeignet. Der Δ-Zweig bildet `window_start`/`window_end` stattdessen aus den
Start-/Endzeitpunkten der betroffenen Segmente (Trip-Streckenabschnitte der NASSEN Änderungen,
s. Punkt 4). `point_at` bleibt für den Δ-Zweig immer `None` — sonst würde der Bestandscode den
Eintrag fälschlich als `nowcast` einordnen (Befund C). Lässt sich für keine der nassen Änderungen
ein Segment mit Start-/Endzeit auffinden, bleiben beide Werte `None`; `_times_overlap()` liefert
dafür fail-soft `False` — kein Match (AC-9).

### 3. Expliziter Quellenvermerk statt Ableitung aus `point_at`

`check_event_identity_gate()` und `record_event_identity()` bekommen einen expliziten Parameter
`source: str` mit den Werten `"official"` | `"nowcast"` | `"deviation"`. Die bestehende Ableitung
`"nowcast" if point_at is not None else "official"` (`alert_gate.py:794`, `:858`) bleibt als
Fallback für Aufrufer, die (wie Radar und amtlich unverändert) keinen expliziten Wert übergeben —
Signaturänderung additiv, kein Bruch der beiden Bestandsaufrufer. Der Δ-Zweig übergibt IMMER
`source="deviation"` explizit. **Signaturänderung ⇒ Referenzfeger** (`grep -rln` über `tests/`)
vor dem Commit Pflicht.

### 4. Kontrollfluss im Δ-Zweig — streng prüfen, großzügig registrieren

In `check_and_send_alerts()`, nach `DeviationAlertEngine.evaluate()` und vor `_send_alert`
(`:558`):

- `wet_changes = [c for c in to_report if c.metric in _WET_METRICS]`.
- **Prüfung (streng, Entscheidung 1):** Gefahrenklasse ist nur dann `"wet"`, wenn `to_report`
  NICHT leer ist und JEDE Änderung (nicht nur die nassen) zum `wet`-Kanon gehört — ein einziger
  nicht-nasser Anteil macht die Klasse `None` (AC-5). Nur bei Klasse `"wet"` wird
  `check_event_identity_gate()` überhaupt aufgerufen; sonst (AC-6) entfällt der Aufruf
  vollständig, kein `AlertStateService.load()`. Segmente/Zeitfenster für den Aufruf kommen aus
  den (in diesem Fall ausschließlich nassen) Änderungen.
- Ergebnis `not allowed` ⇒ derselbe Unterdrückungs-Protokollpfad wie bei Radar/amtlich
  (`alert_log.append_suppressed_entry(..., gate_reason=alert_log.REASON_EVENT_DUPLICATE)`),
  `return False` (AC-1).
- **Registrierung (großzügig, Entscheidung 1):** NACH erfolgreicher Zustellung (`:617`, nach dem
  bestehenden `delivered`-Guard), unabhängig vom Ergebnis der Prüfung oben: ist `wet_changes`
  nicht leer, wird EIN `record_event_identity(..., hazard_class="wet", segment_ids=<Segmente der
  nassen Änderungen>, severity=<Dringlichkeit dieses Laufs, bereits vorhanden als `_urgency`>,
  source="deviation", window_start=…, window_end=…)` geschrieben (AC-2). Ist `wet_changes` leer,
  entfällt die Registrierung — es gibt nichts Nasses zu vermerken (AC-6/AC-7 konsistent
  fortgesetzt). Lässt sich für die nassen Änderungen kein Zeitfenster bilden, entfällt die
  Registrierung ebenfalls (nichts Sinnvolles zu schreiben).

### 5. Ablösung des Doppel-Alarm-Wächters (Befund D, Entscheidung 2)

`trip_alert.py:1835-1861` (der `precip:`/`thunder_level_max:`-Wächter, seit #818 zur Hälfte toter
Code) wird ENTFERNT, nicht repariert. Die Paarung Radar→vorheriger-Δ-Alarm läuft ab jetzt
AUSSCHLIESSLICH über `check_event_identity_gate()` im bestehenden Radar-Aufruf (`:1995`) — der
sieht dank Punkt 4 jetzt auch Δ-Registereinträge. Der protokollierte Grund wechselt für diese
Paarung von `double_alert_guard` auf `event_duplicate` (AC-14); eine Verschärfung, die der alte
Wächter geschluckt hätte, kommt jetzt durch (AC-15, Verbindung zu A-3/#2065/#2050 S3c). Der
bestehende Grund-Code `double_alert_guard` selbst bleibt in `alert_log.py`/`undelivered_hint.py`
erhalten (historische Einträge, andere Aufrufstellen betroffen dieser Wächter nicht).

### 6. Quellenabhängige Nachtrags-Formulierung

`check_radar_alerts()` (`:2033-2039`) formuliert den Nachtrags-Bezug heute hartkodiert als
„Ergänzung zur amtlichen Warnung", unabhängig von `_identity_gate.addendum_source`. Das ist für
einen Δ-Vorgänger falsch (AC-13: keine amtliche Warnung lag vor). Die Formulierung wird
quellenabhängig: `addendum_source == "official"` ⇒ unverändert „Ergänzung zur amtlichen
Warnung", `addendum_source == "deviation"` ⇒ neue Bezeichnung „Ergänzung zur gemeldeten
Wetterabweichung". Dazu wird `addendum_direction` in `check_event_identity_gate()` (`:795`) um
den Fall `match["source"] == "deviation" and new_source == "nowcast"` erweitert — bisher nur
`match["source"] == "official"`.

### 7. Beschriftung `event_duplicate`

`undelivered_hint.py`: `_REASON_LABELS["event_duplicate"] = "bereits als anderes Ereignis
gemeldet"` (Formulierung final beim Implementieren gegen den bestehenden Wortlaut abzustimmen),
`_REASON_BLOCK["event_duplicate"] = "withheld"` — analog dem bestehenden Eintrag
`double_alert_guard` (#2050 S3b), damit der Nutzer keinen Fehler liest, wo bewusst entdoppelt
wurde (AC-16).

## Expected Behavior

- **Input:** ein Abweichungs-Alarm-Lauf (`check_and_send_alerts`) mit mindestens einer Änderung
  aus dem `wet`-Kanon, für ein Segment/Zeitfenster, für das bereits ein Ereignis-Identitäts-
  Registereintrag (beliebiger Quelle) existiert.
- **Output:** bei gleicher oder niedrigerer Dringlichkeit und rein nassem Bündel: Stille,
  `gate_reason=event_duplicate` im Protokoll, kein Kanalversand. Bei Verschärfung, gemischtem
  Bündel, fehlendem/kaputtem Registereintrag oder fehlendem Zeitbezug: normaler Versand wie
  heute. Nach erfolgreicher Zustellung mit Nass-Anteil: genau ein neuer Registereintrag mit
  `source="deviation"`.
- **Side effects:** der Doppel-Alarm-Wächter entfällt als Codepfad; ein nachfolgender Radar-
  Alarm derselben Zelle kann jetzt durch einen Δ-Registereintrag zum Nachtrag statt zum
  Vollalarm werden; das Briefing zeigt zurückgehaltene Δ-Alarme im Block „ZURÜCKGEHALTEN" statt
  gar nicht bzw. als Fehler.

## Acceptance Criteria

- **AC-1:** Given ein amtlicher Alarm hat für Segment S bereits ein Ereignis der Gefahrenklasse
  `wet` registriert (Quelle `official`, überlappendes Zeitfenster), When im Abweichungs-Zweig ein
  Alarm ausschließlich mit nassen Änderungen (Metriken aus dem `wet`-Kanon) für dasselbe Segment
  mit überlappendem Zeitfenster und NICHT höherer Dringlichkeit als der Registereintrag geprüft
  wird, Then bleibt der Abweichungs-Alarm unterdrückt — kein Versand auf irgendeinem der vier
  Kanäle, `triggered_count == 0`, im Protokoll ein Eintrag mit `gate_reason == "event_duplicate"`.
  - Test: `AlarmPruefstrecke`, zwei Läufe (`zweig="official"` dann `zweig="deviation"`) gegen die
    echte Service-Kette, kein Mock.

- **AC-2:** Given ein Abweichungs-Alarm mit mindestens einer nassen Änderung wird erfolgreich auf
  mindestens einem Kanal zugestellt, When das Ereignis-Identitäts-Register danach gelesen wird,
  Then existiert GENAU EIN neuer Eintrag mit `source == "deviation"`, dessen `segment_ids`
  ausschließlich die Segmente der NASSEN Änderungen dieses Laufs trägt (nicht-nasse Änderungen
  desselben Bündels fehlen darin), dessen `severity` der Dringlichkeit dieses Laufs entspricht
  und dessen Zeitintervall (`window_start`/`window_end`) aus den betroffenen Segmenten gebildet
  ist.
  - Test: gemischtes Bündel (eine nasse + eine nicht-nasse Änderung, zwei verschiedene
    Segmente), Registereintrag danach gegen `AlertStateService` gelesen und feldweise geprüft —
    erwartete `severity` über `alert_urgency.urgency_from_changes(to_report)` abgeleitet, kein
    Literal.

- **AC-3:** Given ein Abweichungs-Alarm mit Nass-Anteil wurde erfolgreich zugestellt und
  registriert, When danach ein Radar-Alarm für dieselbe Zelle (überlappendes Segment/Zeitfenster)
  OHNE höhere Dringlichkeit als der Registereintrag geprüft wird, Then bleibt der Radar-Alarm als
  vollständige zweite Nachricht aus — er geht höchstens als Nachtrag (AC-13), niemals als
  zweiter voller Versand mit eigenem Kanal-Zuwachs auf allen Kanälen (heute ginge er ungebremst
  raus, der tote `precip:`-Schlüssel, Befund D).
  - Test: `AlarmPruefstrecke`, Lauf `zweig="deviation"` gefolgt von Lauf `zweig="radar"`,
    Kanal-Zustellungen des zweiten Laufs gezählt und gegen `triggered_count == 0` bzw. Nachtrag
    geprüft.

- **AC-4:** Given ein Ereignis-Identitäts-Registereintrag (gleich welcher Quelle) mit einer
  bestimmten Dringlichkeit existiert für Segment/Zeitfenster, When ein Abweichungs-Alarm mit
  einer ECHT höheren Dringlichkeit als der Registereintrag für dasselbe Segment/Zeitfenster
  geprüft wird, Then wird dieser Alarm IMMER zugestellt — unabhängig davon, ob ein passender
  Registereintrag existiert.
  - Test: Registereintrag mit Dringlichkeit `MODERATE`, Folgelauf mit Änderungen, deren
    abgeleitete Dringlichkeit `HIGH` ist; `triggered_count == 1`, Positivkontrolle über einen
    gleichrangigen Kontroll-Lauf ohne Durchbruch.

- **AC-5:** Given ein Abweichungs-Alarm bündelt mindestens eine NICHT-nasse Änderung (z. B.
  `wind_max_kmh` oder `temp_max_c`) neben nassen Änderungen für ein Segment, für das bereits ein
  passender Registereintrag existiert, When dieser Alarm geprüft wird, Then wird er NIE
  unterdrückt — die Gefahrenklasse des Laufs ist `None`, `triggered_count` steigt wie ohne
  Registereintrag.
  - Test: gemischtes Bündel gegen einen vorbereiteten passenden Registereintrag geprüft;
    Kontroll-Lauf mit rein nassem Bündel (identische nasse Änderung) bleibt still —
    Positivkontrolle, dass allein die Beimischung entscheidet.

- **AC-6:** Given ein Abweichungs-Alarm enthält AUSSCHLIESSLICH nicht-nasse Änderungen (kein
  Metrik-Schlüssel aus dem `wet`-Kanon), When dieser Alarm geprüft wird, Then liefert die
  Gefahrenklassen-Auflösung `None`, das Ereignis-Identitäts-Register wird für diesen Lauf gar
  nicht gelesen (kein `AlertStateService.load()`-Aufruf für die Ereignis-Identität), und die
  Meldung geht durch.
  - Test: Bündel nur mit `wind_max_kmh`/`temp_max_c`; Zähl-Spion auf `check_event_identity_gate`
    (NICHT auf `AlertStateService.load` — die Ladefunktion wird im selben Lauf ohnehin für das
    Melde-Gedächtnis gerufen und könnte den Befund nicht trennen), Zähler bleibt `0`, Zustellung
    geprüft. Positivkontrolle: derselbe Aufbau mit einer nassen Änderung ruft das Gate genau
    einmal.

- **AC-7:** Given ein Abweichungs-Alarm enthält ausschließlich Schnee-Änderungen
  (`snow_depth_cm`, `snow_new_sum_cm` oder `snowfall_limit_m`), When dieser Alarm geprüft wird,
  Then gehören diese Metriken NICHT zum `wet`-Kanon, die Gefahrenklasse ist `None`, und die
  Meldung wird nie durch die Ereignis-Identität unterdrückt — auch nicht bei passendem
  Registereintrag.
  - Test: `resolve_hazard_class(metrics=["snow_depth_cm"])` direkt gegen `None` geprüft, plus ein
    End-zu-End-Lauf mit Schnee-Bündel gegen einen vorbereiteten passenden Registereintrag.

- **AC-8:** Given der Ereignis-Identitäts-Registereintrag für ein Segment ist kaputt oder
  unvollständig (z. B. fehlendes `segment_ids`- oder unparsbares Zeitfeld), When ein
  Abweichungs-Alarm für dieses Segment geprüft wird, Then unterdrückt dieser Eintrag NICHTS
  (fail-soft) — die Meldung geht durch, wie im Bestand für Radar/amtlich.
  - Test: manipulierter `throttle`-/`alert_state`-Registereintrag mit fehlendem Feld, danach ein
    Δ-Lauf gegen die echte Service-Kette; Zustellung geprüft, kein Absturz.

- **AC-9:** Given eine nasse Änderung referenziert eine `segment_id`, die im Trip nicht
  auffindbar ist (kein Start-/Endzeitpunkt bildbar), When aus den nassen Änderungen dieses Laufs
  ein Zeitintervall gebildet werden soll, Then entsteht KEIN Zeitintervall (`window_start`/
  `window_end` bleiben `None`), die Ereignis-Identitäts-Prüfung erzeugt dadurch fail-soft KEIN
  Match, und die Meldung geht durch.
  - Test: `WeatherChange` mit einer im Trip nicht existierenden `segment_id`, danach ein Lauf
    gegen einen vorbereiteten passenden Registereintrag (der ohne die Lücke gematcht hätte).

- **AC-10:** Given ein Registereintrag deckt ein Zeitfenster ab, When ein Abweichungs-Alarm
  dasselbe Segment betrifft, in Dringlichkeit nicht höher ist, aber ein Zeitfenster meldet, das
  WESENTLICH mehr Zeit abdeckt als der Registereintrag (V1-Ausnahme, mehr als der
  Nowcast-Horizont über das bereits abgedeckte Ende hinaus), Then kommt dieser Alarm trotzdem
  durch.
  - Test: Registereintrag mit kurzem `window_end`, Δ-Lauf mit deutlich späterem `window_end`
    (Segmentfenster reicht wesentlich weiter), `triggered_count == 1`.

- **AC-11:** Given ein Abweichungs-Alarm mit Nass-Anteil wird erfolgreich zugestellt, When der
  zugehörige Registereintrag gelesen wird, Then trägt er `source == "deviation"` — NICHT
  `"official"` — auch wenn er (wie ein amtlicher Eintrag) ein Zeitintervall statt eines
  Einzelzeitpunkts trägt.
  - Test: Registereintrag nach einem Δ-Lauf feldweise gelesen, `source`-Feld gegen
    `"deviation"` geprüft, Gegenprobe gegen die ALTE Ableitung (`point_at is not None`), die hier
    fälschlich `"official"` liefern würde.

- **AC-12:** Given ein Bestandseintrag im Register wurde vor dieser Scheibe geschrieben und
  trägt kein `source`-Feld, When dieser Eintrag als Kandidat für einen neuen Alarm gelesen wird,
  Then bleibt er lesbar, seine Quelle wird weiterhin fail-soft aus der Anwesenheit von `point_at`
  bzw. `window_*` abgeleitet, und sein Unterdrückungs-/Match-Verhalten ist gegenüber dem Stand
  vor dieser Scheibe UNVERÄNDERT.
  - Test: vorbereiteter Alt-Registereintrag (Format vor #2018, ohne `source`-Feld) gegen einen
    Radar- UND einen amtlichen Folgelauf geprüft — beide Bestandswächter bleiben grün.

- **AC-13:** Given ein Abweichungs-Alarm mit Nass-Anteil wurde registriert (`source ==
  "deviation"`), When danach ein Radar-Alarm derselben Zelle mit ECHTER Verschärfung (höhere
  Dringlichkeit) geprüft wird, Then geht er in NACHTRAGSFORM heraus (wie nach einer
  vorangegangenen amtlichen Warnung, #2018) — mit einer korrekten deutschen Bezeichnung für die
  Vorhersage-Abweichung als Quelle im Nutzertext (NICHT „Ergänzung zur amtlichen Warnung", wenn
  keine amtliche Warnung vorlag).
  - Test: `AlarmPruefstrecke`, Δ-Lauf gefolgt von eskalierendem Radar-Lauf; gerenderter
    Alarm-Text auf die neue, quellenabhängige Formulierung geprüft (Code-Referenz:
    `src/services/trip_alert.py:2033-2039`, `addendum_source` aus `check_event_identity_gate()`).

- **AC-14:** Given der Doppel-Alarm-Wächter (`src/services/trip_alert.py:1835-1861`) ist aus dem
  Code entfernt, When ein Radar-Alarm auf einen zuvor registrierten Abweichungs-Alarm für
  dieselbe Zelle trifft, Then läuft die Paarung ausschließlich über die Ereignis-Identität, und
  der protokollierte Unterdrückungsgrund lautet `event_duplicate` — der alte Grund
  `double_alert_guard` entsteht für diese Paarung nicht mehr neu.
  - Test: `tests/tdd/test_issue_818_radar_briefing_integration.py` umgeschrieben (nicht
    gelöscht) auf die neue Grund-Erwartung; Quellcode-Grep bestätigt das Fehlen der Zeilen
    `1835-1861` im alten Wortlaut.

- **AC-15:** Given eine Gewitter-Verschärfung, die der alte Doppel-Alarm-Wächter (ohne
  Eskalations-Ausnahme) geschluckt hätte, When dieselbe Verschärfung nach der Ablösung geprüft
  wird, Then kommt sie DURCH — Verbindung zu Anforderung A-3 (#2065/#2050 S3c), keine Sperre
  bricht hier mehr eine echte Eskalation.
  - Test: Δ-Lauf mit `thunder_level_max`-Eskalation innerhalb des alten Wächter-Cooldown-Fensters
    (Gewitterstufe steigt gegenüber dem vorherigen Registereintrag); Zustellung geprüft.

- **AC-16:** Given ein Abweichungs-Alarm wurde wegen `event_duplicate` zurückgehalten, When das
  Trip-Briefing den Abschnitt „was hat dich nicht erreicht" rendert, Then erscheint der Vorfall
  im Block „ZURÜCKGEHALTEN" mit einer deutschen Beschriftung für `event_duplicate` — NICHT im
  Block „FEHLGESCHLAGEN" bzw. als „Versand fehlgeschlagen" (heute fällt der Grund mangels
  Eintrag in `_REASON_LABELS` genau darauf zurück).
  - Test: `UndeliveredIncident` mit `reasons=["event_duplicate"]` gegen `has_undelivered()`,
    `_incident_block()`/Rendering geprüft — Block und Beschriftungstext.

- **AC-17:** Given ein Abweichungs-Alarm mit Nass-Anteil hat keinen einzigen zustellbaren Kanal
  (`notif_result.sent == False`), When der Lauf abgeschlossen ist, Then entsteht KEIN neuer
  Ereignis-Identitäts-Registereintrag — Registrierung bleibt an erfolgreiche Zustellung gebunden
  (F001-Symmetrie).
  - Test: Trip ohne konfigurierte Empfänger auf allen Kanälen, Δ-Lauf mit nasser Änderung,
    Register vor/nach dem Lauf verglichen — keine neue `event_identity:`-Schlüssel.

- **AC-18:** Given zwei Nutzer A und B mit Trips in derselben geografischen Zone, von denen A
  einen Ereignis-Identitäts-Registereintrag für ein Segment hinterlassen hat, When B einen
  inhaltsgleichen Abweichungs-Alarm für sein eigenes, gleich benanntes Segment prüft, Then bleibt
  B's Alarm UNBEEINFLUSST von A's Registereintrag — eigener Registerpfad unter
  `data/users/<user_id_b>/`, kein Cross-User-Datenleck.
  - Test: zwei getrennte `AlarmPruefstrecke`-Instanzen mit unterschiedlichen `user_id`, A's
    Registereintrag geschrieben, dann B's inhaltsgleicher Lauf geprüft — `triggered_count == 1`
    für B.

- **AC-19:** Given der Ortsvergleich (`compare_alert.py`) ist von dieser Scheibe nicht betroffen,
  When `check_all_compare_presets()`/`_evaluate_one_location()` nach dieser Änderung laufen, Then
  rufen sie WEDER `check_event_identity_gate()` NOCH `record_event_identity()` auf — unverändert
  gegenüber dem Stand vor dieser Scheibe, geprüft durch einen Signatur-/Aufruf-Wächter.
  - Test: Aufruf-Spion (kein Mock des Verhaltens, nur Zählung) um `check_event_identity_gate`/
    `record_event_identity` während eines vollständigen Ortsvergleich-Laufs; Zähler bleibt `0`.

## Known Limitations

- **Gebündelte Δ-Meldungen bleiben atomar.** Fällt nur ein Teil eines Bündels unter ein
  registriertes Ereignis, wird die GANZE Meldung nicht unterdrückt, solange auch nur eine
  Änderung nicht zum `wet`-Kanon gehört (AC-5) — bewusste Entscheidung (Entscheidung 1), kein
  Mechanismus für Teil-Unterdrückung existiert.
- **Zwei parallele Reihenfolgen der Δ-Prüfung.** Die Ereignis-Identität sitzt strukturell NACH
  Sperrzeit/Tagesbudget/Ruhezeit (unverändert) — eine Δ-Meldung, die dort bereits unterdrückt
  wird, erreicht die Ereignis-Identität gar nicht. Das ist Bestandsverhalten, keine neue
  Einschränkung dieser Scheibe.
- **Rollout-Effekt am Deploy-Tag (bewusst in Kauf genommen).** Der Doppel-Alarm-Wächter entfällt
  sofort mit dem Deploy, aber das Ereignis-Register kennt zu diesem Zeitpunkt noch keinen einzigen
  Abweichungs-Eintrag — registriert wird erst ab dem ersten zugestellten Δ-Alarm nach dem Deploy.
  In diesem Übergangsfenster ist die Paarung „Δ meldete Gewitter, Radar zieht nach" **ungebremst**,
  ein zusätzlicher Radar-Alarm ist möglich. Das ist die **sichere Richtung** (eine Nachricht zu
  viel, keine zu wenig) und gilt nur bis zum nächsten zugestellten Abweichungs-Alarm desselben
  Trips. Dieselbe Abwägung wie beim Rollout von #2050 S3b.
- **Die V1-Ausnahme („wesentlich mehr Zeit") bleibt unverändert übernommen** — für den Δ-Zweig
  bedeutet das: ein Δ-Alarm mit deutlich weiter reichendem Segmentfenster als der
  Registereintrag kommt durch, auch ohne Dringlichkeits-Sprung (AC-10). Diese Grenze war bereits
  vor dieser Scheibe für Radar/amtlich so definiert und wird nur vererbt.

## Abgelöste Zusicherungen

| Spec/Code | Sagt heute | Wird |
|---|---|---|
| `src/services/trip_alert.py:1835-1861` (Doppel-Alarm-Wächter, #818) — Testdatei `tests/tdd/test_issue_818_radar_briefing_integration.py` | Radar liest `precip:<segment_id>`/`thunder_level_max:<segment_id>` gegen einen eigenen Cooldown-Topf, unabhängig von der Ereignis-Identität; kein Eskalations-Durchbruch möglich | **entfernt, nicht repariert** (Entscheidung 2) — dieselbe Paarung läuft künftig ausschließlich über `check_event_identity_gate()`, Grund `event_duplicate` statt `double_alert_guard`; Testdatei umgeschrieben, nicht gelöscht (AC-14/AC-15) |
| `src/services/alert_gate.py:858` (Kommentar „kein neuer Parameter, Signatur unveraendert", Issue #2018) | Quelle wird ausschließlich aus der Anwesenheit von `point_at` abgeleitet — kein expliziter Parameter | **um einen expliziten, additiven `source`-Parameter erweitert** — Radar/amtlich rufen weiterhin ohne den Parameter auf (Fallback bleibt identisch), der Δ-Zweig übergibt ihn immer explizit (AC-11/AC-12) |
| `src/services/trip_alert.py:2034` (hartkodiert „Ergänzung zur amtlichen Warnung") | jeder Nachtrag wird unabhängig von `addendum_source` als Ergänzung zur amtlichen Warnung formuliert | **quellenabhängig formuliert** — Δ-Vorgänger erzeugen eine eigene, korrekte Bezeichnung statt einer falschen Behauptung über eine nie vorliegende amtliche Warnung (AC-13) |

**Müssen unverändert grün bleiben** (aktive Gegenproben gegen eine zu weite Lösung):

- Bestehende Radar/amtlich-Ereignis-Identitäts-Tests in `tests/tdd/test_alert_gate.py`
  (AC-1…AC-19 der Bestandsscheibe #1467 S4b) — der Fallback ohne expliziten `source`-Parameter
  muss identisch bleiben.
- `tests/tdd/test_compare_radar_alert_event_identity.py`,
  `tests/tdd/test_compare_official_alert_event_identity.py` — unverändert, Ortsvergleich bleibt
  außen vor (AC-19).
- `tests/tdd/test_cooldown_quellenuebergreifend.py` — Textzusicherung „Cooldown gilt nur
  quelleneigen" darf durch den Δ-Anschluss der Ereignis-Identität nicht widersprüchlich werden
  (unterschiedliche Mechanismen: Sperrzeit bleibt quelleneigen, Ereignis-Identität war schon vor
  dieser Scheibe quellenübergreifend).

## Risks

1. **🔴 Die gefährlichste Fehlerrichtung ist der ausbleibende Alarm.** Diese Scheibe baut eine
   NEUE Unterdrückungsregel im Abweichungs-Zweig, während die Tour des PO bereits läuft (Start
   2026-08-23). Jede AC dieser Spec sichert explizit eine Gegenrichtung mit ab (AC-4/AC-5/AC-6/
   AC-7/AC-8/AC-9/AC-10) — keine AC prüft nur die Unterdrückung ohne Positivkontrolle.
2. **Signaturänderung an `check_event_identity_gate()`/`record_event_identity()`.** Der neue
   `source`-Parameter zieht einen Referenzfeger über `tests/` nach sich (`grep -rln` über die
   Testbäume) — Signatur-Wächter für diese Funktionen liegen in fremden Testdateien
   (`test_compare_radar_alert_event_identity.py`, `test_compare_official_alert_event_identity.py`
   u. a.).
3. **Berührung mit der Parallelscheibe S4a.** Beide Scheiben fassen `alert_log.py`
   (Grund-Register) und `undelivered_hint.py` (Beschriftungen) an. Vor dem Merge gegen
   `origin/main` rebasen und den Diff auf gelöschte Fremdarbeit prüfen
   (`git diff origin/main --diff-filter=D`).
4. **Zwei Mechanismen für dieselbe Paarung während der Übergangsphase.** Solange der
   Doppel-Alarm-Wächter noch nicht entfernt ist (Zwischenstand innerhalb der Implementierung),
   existieren kurzzeitig zwei Wächter für Radar↔Δ — die Reihenfolge in dieser Scheibe entfernt
   den alten VOR dem ersten grünen Lauf, damit kein uneindeutiger Protokollgrund entsteht.
5. **Prüfstrecken-Grenze.** `alert_state.reset()` verwirft `event_identity:`-Schlüssel still
   (`src/services/alert_state.py:38-45`) — Szenarien über eine Briefing-Grenze verlieren ihre
   Vorbelegung unbemerkt. Bei Mehrläufer-Tests mit `AlarmPruefstrecke` beachten.
6. **Gebündelte Δ-Meldungen sind nicht teilbar** (s. Known Limitations) — eine falsch verstandene
   Teil-Unterdrückung wäre ein neuer Mechanismus mit eigener Fehlerfläche und ist ausdrücklich
   nicht Ziel dieser Scheibe.

## Test Plan

Kern-Schicht (deterministisch, kein Netz/Live-Dienst), Werkzeug `AlarmPruefstrecke`
(`tests/helpers/alarm_pruefstrecke.py`, #2050 S1) für alle Mehrläufer-Zeitreihen-Szenarien gegen
die echte Service-Kette — kein Mock.

| Testdatei | Änderung | Deckt |
|---|---|---|
| `tests/tdd/test_alarm_szenario_ein_ereignis_ein_alarm.py` | CREATE | AC-1, AC-3, AC-4, AC-5, AC-9, AC-10, AC-13, AC-15, AC-18 (Szenario-5-Wächter über die Prüfstrecke) |
| `tests/tdd/test_alert_gate.py` | MODIFY | AC-2, AC-6, AC-7, AC-8, AC-11, AC-12, AC-17 (dritter Auflösungsweg, expliziter `source`-Parameter, Fail-soft-Regression) |
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | MODIFY | AC-14 (Doppel-Alarm-Wächter-Ablösung, umgeschriebener Wortlaut statt Löschung) |
| `tests/tdd/test_undelivered_hint.py` (oder bestehende Äquivalent-Datei) | MODIFY | AC-16 (Beschriftung/Block für `event_duplicate`) |
| `tests/tdd/test_compare_alert_event_identity_unberuehrt.py` | CREATE oder Ergänzung in bestehender Compare-Testdatei | AC-19 (Aufruf-Spion, Ortsvergleich unberührt) |

Testdateien werden nach Verhalten benannt (`test_alarm_szenario_ein_ereignis_ein_alarm.py`),
NICHT nach Issue-Nummer. Jede AC hat mindestens einen Test mit Positivkontrolle (ein Aufbau, der
ohne die geprüfte Bedingung tatsächlich anders ausgehen würde) — Muster aus #2050 S1/S2b/S3c.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (weiterer Nachtrag, nach #2065, #2050 S3b und #2050 S3c)
- **Rationale:** ADR-0021 hält bereits die quellenübergreifende Ereignis-Identität als geteilten
  Baustein für Trip und Ortsvergleich fest (Nachträge zu #1467 S4b-1/S4b-2 und #2018). Diese
  Scheibe fügt keine neue Architektur hinzu, sondern schließt einen bisher nicht angeschlossenen
  dritten Aufrufer (Δ-Zweig) an denselben, unveränderten Mechanismus an — mit einem additiven
  dritten Auflösungsweg für die Gefahrenklasse (Metrik-Liste statt `is_convective`/`hazard`) und
  einem additiven expliziten `source`-Parameter. Nach der Projektregel („Abweichung ⇒ neues ADR
  bzw. datierter Nachtrag") braucht das einen weiteren, datierten Nachtrag, der den
  Δ-Anschluss, den `wet`-Metrik-Kanon, die Ablösung des Doppel-Alarm-Wächters und die
  Nicht-Betroffenheit des Ortsvergleichs festhält — einsortiert nach dem letzten bestehenden
  Nachtrag (#2050 S3c, 2026-08-23).

## Changelog

- 2026-08-23: Initial spec created (aus
  `docs/context/feat-2050-s4c-ein-ereignis-ein-alarm.md`, Analyse-Phase 2026-08-23, Befunde A-E,
  Entscheidungen 1-3).
