# Context: fix-2009-nowcast-vorlauf

**Issue:** #2009 „Gewitter in 8 min — geht es nicht früher?" (type:bug, priority:high, area:alerts)
**Erstellt:** 2026-08-20
**Branch:** `fix-2009-nowcast-vorlauf` (auf `origin/main` @ `ddcacdbe`)

## Request Summary

Der Radar-/Nowcast-Gewitteralarm meldet praktisch immer „in 8 Min" Vorlauf. Der PO fragt, ob
das ein fester Wert ist („hinterfrage das maximal kritisch") und ob nicht früher gewarnt werden
kann. Belegt: die 8 ist der **einzige Wert, der überhaupt einen Alarm auslösen kann** — kein
Zufall, kein Wetterbefund.

## Root Cause — beweisbar, nicht vermutet

Drei Konstanten erzwingen zusammen genau den Wert 8:

| Baustein | Ort | Wirkung |
|---|---|---|
| Scheduler-Takt `7,22,37,52 * * * *` | `internal/scheduler/scheduler.go:199` (Trip), `:202` (Vergleich) | Prüfzeitpunkt liegt **immer 7 Min nach** einem Viertelstundenpunkt |
| Frame-Raster 15 Min auf `:00/:15/:30/:45` | `src/services/radar_service.py:554-564` (INCA-Umrechnung `:386-387`, Open-Meteo `:461-462`) | Erster Frame mit `timestamp >= now` ist immer der nächste Viertelstundenpunkt → `delta ≈ 7,5–7,9` → `round()` = **8** |
| Alarmschwelle `onset <= 20` | `src/services/trip_alert.py:126-129` + Aufruf `:1270` (`threshold_min=20`); `src/services/compare_radar_alert.py:53` (`_RADAR_ONSET_THRESHOLD_MIN = 20`), Aufruf `:346` | Von den möglichen Rasterwerten **8, 23, 38, 53 …** passiert nur die 8 |

`15 − 7 = 8`. Alles andere wird verworfen.

**Verstärker:** `radar_service.py:556` filtert `f.timestamp >= now` — der **laufende** Frame ist
ausgeschlossen. Selbst bei bereits tobendem Gewitter ist der gemeldete Onset der nächste
Rasterpunkt, nie 0.

**Live-Positivkontrolle (2026-08-20, 13:38 UTC, 46.65/12.85):** GeoSphere INCA
(`nowcast-v1-15min-1km`) liefert 11 Zeitpunkte im 15-Min-Raster bis **+142 Min**. Am Messpunkt
regnete es zu diesem Zeitpunkt bereits (13:30-Frame: 2,34 mm/15min) — der berechnete Onset wäre
trotzdem +7 Min gewesen. Rohdaten: Scratchpad `inca.json`.

### Warum #1945 das nicht behoben hat

#1945 („Alarm unklar", CLOSED 2026-08-18) hat exakt dieses Symptom analysiert und
`_NOWCAST_HORIZON_MIN` von 60 auf 180 angehoben (`src/services/radar_service.py:67`, auf
Produktion aktiv). Die Änderung **kann nicht wirken**: der Horizont bestimmt nur, wie weit
`_derive_result()` nach einem nassen Frame *sucht*; das 20-Minuten-Tor dahinter verwirft jeden
Fund > 20 Min. Die Erwartung der damaligen Spec („Countdown verteilt sich über 23/38/53 …",
`docs/specs/modules/fix_1945_nowcast_horizon.md:82-85`) war rechnerisch unmöglich.

**Lehre für diese Runde:** Eine Änderung an *einer* Stelle der Kette muss gegen die *ganze*
Kette simuliert werden, bevor sie als Fix gilt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py:126-129, 1270` | Schwellenfunktion + Trip-Aufrufstelle (Literal 20) |
| `src/services/compare_radar_alert.py:53, 346` | Ortsvergleich-Konstante + Aufrufstelle |
| `src/services/radar_service.py:543-565` | `_derive_result()` — einzige Quelle von `onset_minutes` |
| `src/services/alert_gate.py:117-166` | `check_nowcast_gate()` — Ruhezeit, Sperrzeit, Tageslimit |
| `src/services/alert_gate.py:559-628` | Ereignis-Identität — **die kritische Nebenwirkung**, s.u. |
| `src/output/renderers/alert/render.py:288, 315, 367, 371, 418, 435-463` | Betreff, E-Mail-H1, „Wo & wann", Telegram, SMS-Token |
| `internal/scheduler/scheduler.go:199, 202` | Cron-Takt beider Radar-Jobs |
| `tests/helpers/nowcast_gate_fixtures.py:179, 193` | Default `onset_minutes=8` in der halben Testsuite |

## Existing Patterns

- **Geteilter Pfad Trip ↔ Ortsvergleich:** Beide Flächen nutzen `check_nowcast_gate()` und
  dieselbe Ereignis-Identität; ADR-0021 (Nachtrag #1461 S3b-2b) hat den Radar-Onset-Pfad
  ausdrücklich vom Trip-Sonderweg zum geteilten Weg gemacht. Eine Änderung nur auf einer Seite
  wäre ein Rückfall.
- **Nutzerseitige Alarmschärfe** wird nach ADR-0043 als **Niveau** („entspannt/standard/sensibel")
  ausgedrückt, nicht als zweiter Alarmtyp. `ONSET_SHIFT_BOUNDS` (`src/services/alert_preset.py:136-140`)
  ist das lebende Beispiel.
- **Alarme melden Sprünge, keine Absolutwerte** (ADR-0009) — der Nowcast-Alarm ist bewusst die
  Ausnahme davon (absolute Auslösung).

## Konfigurierbarkeit heute

Es gibt **kein** nutzerseitiges Feld für die Vorwarnzeit. Konfigurierbar sind nur:

| Feld | Python | Go | Frontend |
|---|---|---|---|
| `alert_cooldown_minutes` (Sperrzeit, Default 120) | `src/app/trip.py:194`, `src/app/models.py:1292` | `internal/model/trip.go:118` | `types.ts:337` |
| `alert_quiet_from`/`_to` (Ruhezeit) | `src/app/trip.py:195` | `internal/model/trip.go:119` | `types.ts:338` |
| `radar_alert_enabled` (nur an/aus, **nur** Vergleichs-Presets, Default AUS) | `src/app/models.py:1290` | `internal/model/compare_preset.go:60` | `AlarmeTab.svelte:437-442` |

Für Trips gibt es nicht einmal einen An/Aus-Schalter — der Trip-Radar-Alarm läuft immer.
Die „höchstens einmal in 30 Minuten"-Zeile der Nutzer-Mail ist reine Anzeige des gesetzten
`alert_cooldown_minutes` (`trip_alert.py:1320-1325`, gerendert `render.py:324-330`).

## Dependencies

**Upstream:** GeoSphere INCA `nowcast-v1-15min-1km` (15-Min-Raster, ~2,5 h Vorschau) ·
BrightSky/RADOLAN (5-Min-Raster, nur DE) · Open-Meteo `minutely_15` (Fallback-Kette
`radar_service.py:327-357`) · `ForecastBudgetGate` (Drosselung bei API-Budgetdruck).

**Downstream:** `OnsetEvent` (`src/services/radar_alert_service.py:59-63`) →
`output/renderers/alert/project.py:392-396` → alle vier Kanäle. Premium-SMS teilt den
SMS-Renderer (`notification_service.py:23`).

## 🔴 Risiken & Nebenwirkungen einer Fensteröffnung

1. **Ereignis-Identität schluckt den Folge-Alarm.** `check_event_identity_gate()`
   (`alert_gate.py:559-628`) merkt sich einen zugestellten Alarm mit Fenster
   `point_at ± NOWCAST_HORIZON_MIN` = **±180 Min**. Ein zweiter Alarm zur selben Gefahrenklasse
   (`"wet"`) im selben Segment kommt nur durch bei (a) **höherer Dringlichkeit**
   (`:605-606`) oder (b) wesentlich größerer Abdeckung (`_covers_materially_more`, `:541-557`).
   Die Dringlichkeit hängt **nur** an Konvektion/Intensität, nicht am Onset
   (`src/services/alert_urgency.py:32-44`) — eine Zelle, die einfach näher kommt, eskaliert
   also **nicht**. Folge: Vorwarnung „in 90 Min" gesendet ⇒ der Akut-Alarm „in 8 Min" wird als
   Dublette unterdrückt. **Eine reine Schwellen-Anhebung tauscht den späten Alarm gegen einen
   frühen, statt beide zu liefern.**
2. **Briefing-Unterdrückung greift öfter.** `trip_alert.py:1276-1292` (#818): hat das Briefing
   für die Onset-Stunde ≥ 0,5 mm angekündigt, entfällt der Radar-Alarm — Ausnahme nur bei
   Konvektion (#883-Override, `:1288`). Je weiter das Fenster, desto häufiger trifft der Onset
   eine bereits angekündigte Stunde.
3. **Uhrzeit ohne Datum.** `render.py:371` „Wo & wann: … ab {onset_time}" und der SMS-Token
   (`:435-455`) formatieren reines `%H:%M` (`utils/timezone.py:133`). Bei > 60 Min Vorlauf kann
   der Zeitpunkt über Mitternacht rutschen und wird mehrdeutig.
4. **Kein Segment-Bezug des Onsets.** Nirgends wird geprüft, ob `_onset_dt` noch vor
   `active.end_time` liegt. Bei 120–180 Min Vorlauf käme eine Warnung für einen Abschnitt, den
   der Nutzer längst hinter sich hat.
5. **Betreff signalisiert Akutheit.** „Gewitter in 150 Min" im Betreff ist formal korrekt, aber
   die Bauform (ADR-0052, #919-Format) ist auf „jetzt gleich" gemünzt.
6. **Veraltete Doku, die mitgezogen werden muss:** `src/output/renderers/email/starkregen_hint.py:1-27`
   behauptet noch „60-Minuten-Nowcast-Fenster"; `radar_service.py:292-293` sagt „In den nächsten
   2 Stunden kein Regen erwartet."; `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md:344`
   begründet eine Ausnahme mit „Regen-Onset ≤ 20 min inhärent 'jetzt'" — trägt dann nicht mehr.
7. **API-Budget.** `docs/reference/decision_matrix.md:242-263`: der Radar-Pfad dominiert bereits
   den API-Verbrauch. Mehr Alarme heißt nicht mehr Abrufe (Takt bleibt), aber mehr Zustellungen.

## Was NICHT existiert (Annahme widerlegt)

Ein absoluter Frühwarn-Pfad „Gewitter wahrscheinlich ab 14:00" aus der Stundenvorhersage
existiert **nicht**. Der Satz war der ursprüngliche #1493-Vorschlag und wurde vom PO verworfen
(`docs/specs/modules/feat_1493_gewitter_onset_sichtbar.md:35-38`) — umgesetzt wurde nur die
Anzeige in Briefing-Pille und Ausblick.

Der zweite, gröbere Alarmpfad ist der **Onset-Verschiebungs-Alarm #1468** (seit 2026-08-18 live):
Quelle Stundenvorhersage, Auslösung **relativ** (Verschiebung ≥ 1–4 h gegenüber dem Anker,
`src/services/weather_change_detection.py:800-845`, Schwellen `alert_preset.py:136-140`). Steht
der Gewitterbeginn stabil bei 14:00, schweigt dieser Pfad — er kann die fehlende Vorwarnung
also **nicht** ersetzen. Zwischen ihm und dem Nowcast-Alarm gibt es keine gemeinsame
Entdopplung.

## Existing Specs

| Pfad | Inhalt |
|---|---|
| `docs/specs/modules/radar_nowcast.md:19, 75, 94` | **Quelle der 20:** „Onset ≤ Schwelle (Default 20 min)" (#656) — muss mitgeändert werden |
| `docs/specs/modules/fix_1945_nowcast_horizon.md` | Horizont 60 → 180; Rendering + Frühwarnung ausdrücklich ausgeschlossen |
| `docs/specs/modules/rework_1467_s4b_entdopplung.md` | Ereignis-Identität (Gefahrenklasse, Dringlichkeit, Onset-Zeitpunkt) |
| `docs/specs/modules/issue_883_acute_danger_override.md` | Konvektion durchbricht die Briefing-Unterdrückung |
| `docs/specs/modules/feat_1468_onset_verschiebung_alarm.md` | Verschiebungs-Alarm aus der Stundenvorhersage |
| `docs/adr/0043-…`, `0046-…`, `0052-…`, `0021-…`, `0009-…` | Niveau-Muster, Kanal-Schwellen, Nowcast-Mailbauform, geteilte Engine, Sprung-Prinzip |

## Testlast

- **Bleiben grün:** `tests/helpers/nowcast_gate_fixtures.py:179, 193` (`onset_minutes=8` ist
  Beispielwert, kein Sollwert) und ~14 Testdateien, die ihn nur als auslösenden Wert nutzen.
- **Werden rot bei Schwellen-Anhebung:**
  - `tests/tdd/test_feature_656_radar_nowcast.py:233-243` — `assert radar_alert_due(later, threshold_min=20) is False` bei `onset_minutes=45` (Schwelle explizit im Assert, 3×)
  - `tests/tdd/test_compare_radar_alert.py:400-436` — Negativtest mit `_wet_frame(45)`, `assert sent == 0`; rot sobald Schwelle > 45
- **Zementieren das Textformat (schwellenunabhängig):**
  `test_issue_919_radar_alert_canonical.py:92,95,164`, `test_alert_sms_onset_zeitpunkt.py:436-452`,
  `test_multi_location_onset_alert.py:172,221,388`, `test_alert_location_vocabulary.py:129`.
- **Blindstelle:** Kein einziger Test prüft, dass `onset_minutes` überhaupt **variieren** kann.
  Der Default 8 maskiert das Problem suiteweit.

## Offene Produktentscheidung (für `/30-write-spec`)

Nicht technisch, sondern PO-Sache: **ein früherer Alarm — oder zwei Alarme (Vorwarnung + akut)?**
Variante 1 ist eine Zahl, Variante 2 verlangt zusätzlich eine Eskalationsregel in der
Ereignis-Identität (Näherrücken muss als Verschärfung zählen). Dazu kommt die Frage, wie weit
das Fenster reicht (Datenquelle gibt ~150 Min her) und ob die Vorwarnung auf konvektive Lagen
beschränkt bleibt. Vorlage mit gemessenen Zahlen erfolgt in der Spec-Phase.
