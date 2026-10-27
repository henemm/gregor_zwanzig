# Context: feat-2050-s4c-ein-ereignis-ein-alarm

**Issue:** #2050, Scheibe **S4c** · Szenario **5** · Anforderung **C-2**
**Stand der Kartierung:** `origin/main` = `791ef6bc` (23.08.2026)

## Request Summary

Melden amtliche Warnung, Vorhersage-Abweichung und Radar dieselbe Gewitterzelle, soll **eine**
Nachricht herausgehen statt zwei bis drei — danach nur noch Verschärfungen. Heute greift die
quellenübergreifende Entdopplung nur zwischen **Radar** und **amtlich**; der **Abweichungs-Zweig
(Δ)** ist an sie nicht angeschlossen und meldet an ihr vorbei.

## Zuschnitt-Vorgeschichte

Der ursprüngliche Schnitt „S4 = Szenarien 5, 6, 12" ist beim Intake (23.08.) aufgeteilt worden,
weil Szenario 6 zu diesem Zeitpunkt bereits in einer Parallelsitzung lief:

| Scheibe | Szenario | Stand |
|---|---|---|
| S4a | 6 — Radar-Teilausfall (B-4) | läuft, Branch `feat-2050-s4a-radar-teilausfall` |
| **S4c** | **5 — ein Ereignis, ein Alarm (C-2)** | **diese Scheibe**, Full Process |
| S4b | 12 — nie stilles Nichts (D-2/E-1) | offen, vom PO nachrangig gestellt |

## Der Ist-Zustand — was bereits existiert

Die quellenübergreifende Entdopplung ist **gebaut und in Betrieb** (#1467 S4b-1, erweitert durch
#2018 und #2065). Sie ist von Anfang an entitätsparametrisiert, gilt also für Trip **und**
Ortsvergleich.

| Baustein | Ort |
|---|---|
| Leseprüfung | `src/services/alert_gate.py:736` `check_event_identity_gate()` |
| Registrierung nach Zustellung | `src/services/alert_gate.py:823` `record_event_identity()` |
| Gefahrenklassen-Auflösung | `src/services/alert_gate.py:547` `resolve_hazard_class()` |
| Kandidatensuche | `src/services/alert_gate.py:634` `_find_matching_entry()` |
| Zeitüberlappung | `src/services/alert_gate.py:589` `_times_overlap()` |
| Wesentlich-mehr-Abdeckung (V1) | `src/services/alert_gate.py:720` `_covers_materially_more()` |

**Wie zwei Meldungen als „dasselbe Ereignis" gelten** — alle drei Bedingungen zugleich:

1. **Gefahrenklasse gleich.** Es gibt genau eine: `HAZARD_CLASS_WET` (`:543`). PO-Entscheid
   2026-08-16: konvektiv/nicht-konvektiv unterscheidet nur die Erscheinungsform derselben Zelle.
   Unbekannte Gefahrenart ⇒ `None` ⇒ **nie** entdoppelt (`:779-780`).
2. **Ortsbezug überlappt.** Schnittmenge der `segment_ids` nicht leer (`:670`, `isdisjoint`).
   Leere Menge auf einer der beiden Seiten ⇒ **nie** Match (`:657-659`).
3. **Zeitbezug überlappt.** Punkt gegen Punkt / Punkt gegen Intervall (mit Nowcast-Horizont als
   Puffer) / Intervall gegen Intervall (`:589-631`).

**Reihenfolge nach einem Treffer, strukturell fest** (`:761-770`):
Eskalation (V2, immer zuerst) → V1-Ausnahme „deckt wesentlich mehr Zeit ab" → Unterdrückung mit
`REASON_EVENT_DUPLICATE`.

Bereits verdrahtet an vier Stellen:

| Zweig | Prüfung | Registrierung |
|---|---|---|
| Radar/Trip | `src/services/trip_alert.py:1995` | `:2120` |
| Amtlich/Trip | `src/services/trip_alert.py:2448` | `:2575` |
| Radar/Compare | `src/services/compare_radar_alert.py:245` | `:396` |
| Amtlich/Compare | `src/services/compare_official_alert.py:222` | `:346` |

## Die Lücke

Der **Δ-Zweig ruft weder die Prüfung noch die Registrierung**:

- Trip: `src/services/trip_alert.py:310` `check_and_send_alerts()` — kein Aufruf im ganzen Block
  `:310-657`
- Ortsvergleich: `src/services/compare_alert.py:122` `check_all_compare_presets()` /
  `:471` `_evaluate_one_location()` — ebenso nicht

Das ist **dokumentiert und bewusst zurückgestellt**, nicht übersehen:
`docs/specs/modules/rework_1467_s4b_entdopplung.md:382` — „Änderungsalarm (Δ) als dritte
Prüfrichtung bleibt offen, S4b-3".

**Folge im Szenario** (amtlich 10:00 → Δ 11:15 → Radar 12:30, dieselbe Zelle): Der amtliche Alarm
geht raus und registriert sich. Der Δ-Alarm um 11:15 sieht das Register nicht und geht als zweite
volle Nachricht raus — und registriert sich auch nicht. Der Radar-Alarm um 12:30 wird vom
**amtlichen** Eintrag gefangen (sofern Segment und Zeitfenster passen) und kommt als Nachtrag.
Ergebnis heute: **zwei** Nachrichten statt einer, und das Register kennt den Δ-Alarm nicht.

## Zwei Stellen, an denen der Δ-Zweig strukturell anders ist

### a) Die Gefahrenklasse ist über Metriken zu bestimmen

`resolve_hazard_class()` kennt genau zwei Eingänge: `is_convective` (Radar) und `hazard`
(amtlich). Der Δ-Zweig hat weder das eine noch das andere — er trägt **Metrik-Änderungen**
(`change.metric`, `src/services/trip_alert.py:621`). Ein dritter Auflösungsweg ist nötig, und mit
ihm die Festlegung, welche Metriken zum `wet`-Kanon gehören. Alles außerhalb ⇒ `None` ⇒ nie
entdoppelt; das ist die sichere Richtung und deckt sich mit AC-4 der Bestandsscheibe.

### b) Δ meldet gebündelt — mehrere Segmente, mehrere Metriken in EINER Nachricht

`to_report` ist eine Liste; ein Alarm kann mehrere Streckenabschnitte und mehrere Metriken
zugleich tragen (sichtbar an `unique_or_none(...)` in `src/services/trip_alert.py:574-575`, das
genau deshalb existiert). Die Ereignis-Identität ist auf Segment-**Mengen** ausgelegt (Schnittmenge
genügt), das passt strukturell — aber die Zeitangabe muss aus mehreren Änderungen gebildet werden,
und die Frage „was, wenn nur ein Teil der Bündelung ein Duplikat ist?" hat der Bestand noch nie
beantworten müssen. Das ist die zentrale Entwurfsfrage dieser Scheibe.

### c) Der Quellenvermerk wird heute aus der Zeitform abgeleitet

`src/services/alert_gate.py:794` und `:858`: `"nowcast" if point_at is not None else "official"`.
Ein Δ-Eintrag, der (wie ein amtlicher) ein Zeit**intervall** trägt, würde damit fälschlich als
`official` registriert. Das beeinflusst die Nachtrags-Richtung (`:795`) und die Auswertbarkeit des
Protokolls. Ein expliziter `source`-Parameter ist der saubere Weg — **Signaturänderung**, also mit
Referenzfeger über `tests/` (siehe Risiken).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_gate.py` | Ereignis-Identität: Prüfung, Registrierung, Gefahrenklasse, Quellenvermerk |
| `src/services/trip_alert.py` | Δ-Zweig `check_and_send_alerts():310-657`; Einbauorte: Prüfung vor `:538`, Registrierung nach `:617` |
| `src/services/compare_alert.py` | Δ-Pendant im Ortsvergleich (`:122`, `:471`, `_finalize_triggered_state`) |
| `src/services/deviation_alert_engine.py` | gemeinsamer Auswertungskern des Δ-Zweigs (`:264` `evaluate()`) |
| `src/services/alert_state.py` | Registerablage, Präfix `event_identity:` (`:44`) |
| `src/services/alert_log.py` | `REASON_EVENT_DUPLICATE` (`:63`), Protokolleintrag |
| `src/output/renderers/email/undelivered_hint.py` | `_REASON_LABELS`/`_REASON_BLOCK` (`:48-77`) — `event_duplicate` fehlt dort |
| `src/services/alert_urgency.py` | geteilte Rangordnung `exceeds()` / `highest_urgency()` |

## Existing Patterns

- **Prüfen vor dem Versand, registrieren erst nach erfolgreicher Zustellung** (F001-Symmetrie zu
  `record_nowcast_sent`) — bei allen vier Bestandsstellen gleich.
- **Eskalation bricht immer durch**, als strukturell erster Zweig mit eigenem `return`
  (`alert_gate.py:797`). Dieselbe Politik wie Sperrzeit-Überholung (#2065, #2050 S3c).
- **Fail-soft im Register:** kaputter Eintrag ⇒ überspringen und protokollieren, nie Absturz
  (`:696-708`).
- **Read-Modify-Write mit Merge** beim Registerschreiben (`:837-840`) — Pflicht laut CLAUDE.md.
- **Caller-seitige Entscheidung nach dem Wetterabruf** statt hartem Abbruch im Gate — das Muster
  aus #2065 / S3b / S3c, das auch hier trägt.

## Dependencies

- **Upstream:** `AlertStateService` (Registerablage), `alert_urgency` (Rangordnung),
  `alert_daily_limit`, `ThrottleStore`, Wetter-Anker über `_get_cached_weather()`
- **Downstream:** alle vier Kanäle über `_send_alert()`; `alert_log` (Protokoll, von der Go-Seite
  gelesen — `internal/store/log.go` liest nur bestehende Felder, Ergänzungen nur additiv);
  E-Mail-Baustein `undelivered_hint.py`

## Existing Specs

- `docs/specs/modules/rework_1467_s4b_entdopplung.md` — die Bestandsscheibe samt der ausdrücklich
  offen gelassenen dritten Prüfrichtung (`:382`)
- `docs/specs/modules/alarm_pruefstrecke.md` — Prüfstrecke aus #2050 S1
- `docs/specs/modules/alarm_szenarien_waechter_4_9_11.md`, `alarm_szenario_laufendes_ereignis.md` —
  Muster für Szenario-Wächter
- `docs/specs/modules/feat_2050_s4a_radar_teilausfall.md` — Parallelscheibe, berührt
  `alert_log.py` und `undelivered_hint.py`

## Risks & Considerations

1. **🔴 Die gefährlichste Fehlerrichtung ist der ausbleibende Alarm.** Diese Scheibe baut eine
   **Unterdrückungs**-Regel, und die Tour des PO läuft ab heute (23.08.). Jede AC muss die
   Gegenrichtung mitsichern: Verschärfung kommt durch, unbekannte Gefahrenart wird nie entdoppelt,
   leere Segmentmenge erzeugt nie ein Match, kaputter Registereintrag unterdrückt nichts.
2. **Zwei Mechanismen für dieselbe Paarung.** Der Doppel-Alarm-Guard
   (`src/services/trip_alert.py:1835-1861`) verbindet Radar und Δ bereits — aber nur in einer
   Richtung (Radar liest, was Δ geschrieben hat). Wird Δ zusätzlich an die Ereignis-Identität
   angeschlossen, gibt es zwei Wächter für dieselbe Paarung. Das Verhältnis muss die Spec klären,
   sonst entsteht eine doppelte Unterdrückung, deren Grund im Protokoll uneindeutig ist.
3. **Gebündelte Δ-Meldungen sind nicht teilbar.** Fällt ein Teil der Bündelung unter ein
   registriertes Ereignis und ein anderer nicht, darf die Unterdrückung nicht die ganze Nachricht
   verschlucken. Entwurfsentscheidung mit Nutzerwirkung.
4. **Ortsvergleich-Fernwirkung.** `entity_id` ist dort `f"{preset_id}:{location_id}"` — der
   Namensraum ist bereits kompatibel. Trotzdem gilt die Trip/Compare-Teilungsvorgabe: gemeinsame
   Auflösung, kein zweiter Mechanismus.
5. **Signaturänderung an `record_event_identity()` / `resolve_hazard_class()`** zieht einen
   Referenzfeger über `tests/` nach sich (`grep -rln` über die Testbäume) — Signatur-Wächter
   liegen in fremden Testdateien.
6. **Berührung mit der Parallelscheibe S4a:** beide fassen `alert_log.py` (Grund-Register) und
   `undelivered_hint.py` (Beschriftungen) an. Kleine, aber reale Merge-Berührung — vor dem Merge
   gegen `origin/main` rebasen und den Diff auf gelöschte Fremdarbeit prüfen.
7. **Prüfstrecken-Grenze:** `alert_state.reset()` verwirft `event_identity:`-Schlüssel still
   (`src/services/alert_state.py:38-45`). Szenarien über eine Briefing-Grenze verlieren ihre
   Vorbelegung unbemerkt — bei Zeitreihen-Tests beachten.
8. **Nebenbefund (nicht Ziel dieser Scheibe):** `event_duplicate` fehlt in `_REASON_LABELS` von
   `undelivered_hint.py` und fällt dort auf „Versand fehlgeschlagen" zurück — der Nutzer liest
   einen Fehler, wo bewusst entdoppelt wurde. Kandidat für diese Scheibe, weil sie den Grund
   erstmals im Δ-Zweig auslöst.

## Analysis (Phase 2, 23.08.2026)

### Type

**Feature** — Anschluss eines bestehenden, in Betrieb befindlichen Mechanismus an einen bisher
nicht angeschlossenen Zweig. Kein Neubau.

### Befund A — Der Metrik-Kanon ist abschließbar

`change.metric` ist **nie Freitext**: Ein Metrik-Schlüssel, der sich nicht als `AlertMetric`
parsen lässt, erzeugt gar keine Alarm-Regel (`src/services/alert_preset.py:236-252`) und kann
`to_report` nicht erreichen. Die real erreichbaren Werte stammen aus `_METRICS`
(`src/app/metric_catalog.py:111ff`).

**Dem `wet`-Kanon zuzuordnen (vier Schlüssel):**
`precip_sum_mm` · `precip_heavy_onset_utc` · `thunder_level_max` · `thunder_onset_utc`

**Ausdrücklich nicht:** Temperatur (`temp_*`), Wind (`wind_max_kmh`, `gust_max_kmh`), Sicht,
UV, Nullgradgrenze sowie **Schnee** (`snow_depth_cm`, `snow_new_sum_cm`, `snowfall_limit_m`) —
Schnee ist physikalisch Niederschlag, steht aber nicht im T2-Kanon `_WET_HAZARDS`
(`src/services/alert_gate.py:544`) und bleibt deshalb außen vor. `cape_max_jkg` ist im Live-Pfad
unerreichbar (`selectable=False`, #710).

Nicht verwendbar wäre `MetricDefinition.category` — dort liegen `snowfall_limit` und
`rain_probability` mit unter `"precipitation"`, was nicht deckungsgleich mit dem Kanon ist.

### Befund B — Der Zeitbezug muss aus dem Segmentfenster kommen, nicht aus `occurred_at`

`WeatherChange.occurred_at` (`src/app/models.py:603`) ist der Zeitpunkt des Spitzenwerts, **aber
in drei von vier Erzeugungspfaden gar nicht gesetzt**: Beginn-Verschiebung setzt ausdrücklich
`None` (`weather_change_detection.py:951`), Absolut-Regeln (`:1048-1059`) und
Schwellwert-Unterschreitung (`:1090-1099`) übergeben es nie.

Ein Zeitbezug aus `occurred_at` liefe deshalb überwiegend leer — `_times_overlap()` gibt ohne
Zeitbezug `False` zurück, es käme nie zu einem Match. Der Δ-Zweig muss daher das
**Zeitintervall** übergeben (`window_start`/`window_end`), gebildet aus den Segmenten der
betroffenen Änderungen. Das ist zugleich semantisch richtig: Der Δ-Zweig sagt „in diesem
Streckenabschnitt", nicht „um 14:12".

Zusätzlich zwingend: `point_at` **darf nicht** gesetzt werden, denn daraus leitet der Bestand
heute den Quellenvermerk ab (`alert_gate.py:794`, `:858`).

### Befund C — Der Quellenvermerk muss ein echter Parameter werden

Heute: `"nowcast" if point_at is not None else "official"`. Ein Δ-Eintrag ohne `point_at` würde
damit als **`official`** registriert. Folge: Ein späterer Radar-Alarm käme als „Nachtrag zur
amtlichen Warnung", obwohl nie eine amtliche Warnung vorlag — eine **falsche Aussage im
Nutzertext** (Verstoß gegen B-2). `record_event_identity()` und `check_event_identity_gate()`
brauchen deshalb einen expliziten `source`-Parameter mit dem dritten Wert `"deviation"`.
Signaturänderung ⇒ Referenzfeger über `tests/` ist Pflicht.

### Befund D — Der bestehende Doppel-Alarm-Wächter ist halb tot und hat keine Eskalations-Ausnahme

`src/services/trip_alert.py:1839` liest zwei Schlüssel: `precip:<segment_id>` und
`thunder_level_max:<segment_id>`. Geschrieben wird das Melde-Gedächtnis aber als
`f"{change.metric}:{change.segment_id}"` (`:621`) — und **`"precip"` ist kein Metrik-Schlüssel**;
der reale Name lautet `precip_sum_mm`. Im gesamten `src/`-Baum existiert kein Schreiber für
`precip:`. Der Niederschlags-Teil dieses Wächters ist damit **seit seiner Einführung (#818) toter
Code**; nur die Gewitter-Hälfte wirkt.

Praktische Folge heute: Meldet der Δ-Zweig Regen und zieht danach der Radar nach, geht die
zweite Nachricht ungebremst raus — **genau der Doppel-Alarm, den Szenario 5 verhindern soll.**

Zweiter, gewichtigerer Punkt: Der Wächter kennt **keine Eskalations-Ausnahme**. Er vergleicht nur
Zeitabstand gegen die Sperrzeit. Eine echte Verschärfung schluckt er — Verstoß gegen A-3, die in
S3c gerade erst für den Abweichungs-Zweig hergestellt wurde.

### Befund E — Die Richtung „Radar/amtlich bremst den Abweichungs-Alarm" entsteht neu

Bisher gibt es sie nicht: Der Doppel-Alarm-Wächter liest ausschließlich im Radar-Zweig. Ein
zuerst gesendeter Radar- oder amtlicher Alarm bremst heute **nie** einen nachfolgenden
Δ-Alarm. Mit dem Anschluss entsteht dieses Verhalten — es ist der Kern von C-2, aber es ist eine
**neue Unterdrückung** und braucht die volle Absicherung der Gegenrichtung.

Kein bestehender Test sichert zu, dass der Δ-Alarm unabhängig von Radar/amtlich herausgeht — die
Unabhängigkeit war bisher nur ein Nebeneffekt des fehlenden Anschlusses.

### Entscheidung 1 — Gemischte Bündel werden nie unterdrückt

`to_report` kann mehrere Streckenabschnitte **und** mehrere Messgrößen zugleich tragen, und es
gibt **kein** bestehendes Muster, einzelne Änderungen vor dem Versand herauszufiltern
(`_send_alert` bekommt die Liste als Ganzes, `trip_alert.py:561`). Eine teilweise Unterdrückung
wäre also ein neuer Mechanismus mit eigener Fehlerfläche.

**Regel:** Die Gefahrenklasse ist nur dann `wet`, wenn **jede** Änderung im Bündel zum
`wet`-Kanon gehört. Trägt das Bündel auch nur eine nicht-nasse Änderung (Wind, Temperatur,
Schnee …), ist die Klasse `None` und die Nachricht geht **immer** durch — sie enthält
Information, die kein Radar- und kein amtlicher Alarm je gemeldet hat.

**Registriert** wird dagegen großzügiger: Jede zugestellte Nachricht mit Nass-Anteil hinterlässt
einen Eintrag über **die Segmente ihrer nassen Änderungen** — damit ein späterer Radar-Alarm für
dieselbe Zelle überhaupt etwas findet. Streng prüfen, großzügig registrieren: Beide Richtungen
zeigen von der Unterdrückung weg.

### Entscheidung 2 — Der Doppel-Alarm-Wächter wird abgelöst, nicht repariert

Der tote `precip:`-Schlüssel wird **nicht** geflickt. Stattdessen übernimmt die Ereignis-Identität
diese Paarung vollständig, und der Wächter entfällt. Begründung: Zwei Wächter für dieselbe
Paarung machen den Unterdrückungsgrund im Protokoll uneindeutig, und der ältere kennt keine
Eskalations-Ausnahme — er würde eine Verschärfung schlucken, die der neue durchließe. Ein bloßes
Reparieren des Schlüsselnamens würde eine seit Jahren stumme Bremse ohne Eskalations-Ausnahme
scharf schalten; das ist die falsche Richtung.

### Entscheidung 3 — Diese Scheibe liefert die Trip-Fläche

Der Ortsvergleich bleibt außen vor, mit demselben Schnitt wie in S3c („Der Ortsvergleich erbt die
Ausnahme nicht"). Gründe: Ortsvergleich-Themen sind vom PO zurückgestellt, der Umfang bliebe sonst
nicht beherrschbar, und die Trip-Fläche ist die, auf der die laufende Tour stattfindet. Die
Anschlussstellen im Ortsvergleich sind kartiert (`compare_alert.py`: Prüfung vor dem Versand
`:312-334`, Registrierung nach `_finalize_triggered_state` `:405`, `entity_id=f"{preset_id}:{loc.id}"`,
`segment_ids=[loc.id]`) und gehen als benannte Folgescheibe ins Issue.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/alert_gate.py` | MODIFY | dritter Auflösungsweg Metrik→Gefahrenklasse; expliziter `source`-Parameter mit Wert `deviation`; Nachtrags-Richtung um Δ erweitern |
| `src/services/trip_alert.py` | MODIFY | Gate-Aufruf vor `_send_alert` (`:558`), Registrierung nach erfolgreicher Zustellung (`:617`); Doppel-Alarm-Wächter `:1835-1861` entfernen |
| `src/output/renderers/email/undelivered_hint.py` | MODIFY | `event_duplicate` beschriften (fällt heute auf „Versand fehlgeschlagen" zurück) |
| `tests/tdd/test_alarm_szenario_ein_ereignis_ein_alarm.py` | CREATE | Szenario-5-Wächter über die Prüfstrecke |
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | MODIFY | Wächter des abgelösten Doppel-Alarm-Guards umstellen |
| `tests/tdd/test_alert_gate.py` | MODIFY | neue Auflösung + Quellenparameter |

### Scope Assessment

- Dateien: 3 Produktivdateien, 3–4 Testdateien
- Geschätzte LoC: **+150/−30** Produktivcode ⇒ LoC-Limit 250 reicht voraussichtlich, sonst
  `set-field loc_limit_override 500`
- Risiko: **HOCH** — es entsteht eine neue Unterdrückungsregel, und die Tour läuft

### Open Questions (mit der Spec zur PO-Freigabe)

- [ ] Kommt ein Radar-Alarm, der auf einen Abweichungs-Alarm für dieselbe Zelle folgt, als
      **Nachtrag** (kurze Zusatzmeldung mit Bezug auf die frühere) oder wird er ganz
      unterdrückt? Empfehlung: **Nachtrag** — dieselbe Behandlung wie bei einer vorangegangenen
      amtlichen Warnung (#2018), weil die Radar-Beobachtung die konkretere Information ist.

## Bestehende Testabdeckung

- `tests/tdd/test_alert_gate.py` (AC-1…AC-19 zur Ereignis-Identität, ab `:394`)
- `tests/tdd/test_compare_radar_alert_event_identity.py`,
  `tests/tdd/test_compare_official_alert_event_identity.py`
- `tests/tdd/test_alert_addendum_failsoft.py`, `test_alert_addendum_sms.py` (#2018-Nachtrag)
- `tests/tdd/test_cooldown_quellenuebergreifend.py` — sichert die Textzusicherung „Cooldown gilt
  nur quelleneigen"; muss beim Anschluss des Δ-Zweigs auf Widerspruchsfreiheit geprüft werden
- `tests/tdd/test_issue_818_radar_briefing_integration.py` — Doppel-Alarm-Guard
- **Nicht abgedeckt:** kein `test_alarm_szenario_*` für Szenario 5
