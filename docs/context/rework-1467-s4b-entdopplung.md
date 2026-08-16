# Context: rework-1467-s4b-entdopplung

Erhoben am 2026-08-16 für Issue #1467 Scheibe S4b (= #1744 Scheibe B).
Alle Zeilenangaben gegen `origin/main` @ `5ddb46e7`.

## Request Summary

Alarme sollen **quellenübergreifend nach Ereignis-Identität** entdoppelt werden: gleiche
Gefahrenart + gleicher Ortsbezug + überlappendes Zeitfenster ⇒ **eine** Meldung. Auslöser ist ein
gemessener Fall vom 2026-08-12: Radar-Nowcast „Gewitter in 8 Min" (16:22) und amtliche Warnung
„GELB Gewitter" (16:30) zum selben Gewitter, beide zugestellt — die Sperrzeiten liegen in
getrennten Töpfen je **Quelle** und können einander konstruktionsbedingt nicht sehen.

S4b ist die letzte Scheibe von #1467 und **schließt das Issue**.

## Kernbefund: Die drei Bestandteile der Ereignis-Identität existieren heute in je drei
## unvereinbaren Ausdrucksformen

Es sind **sechs** Alarmpfade (drei Alarmarten × zwei Flächen), nicht vier.

| Bestandteil | Änderungsalarm (Δ) | Radar-Nowcast | Amtliche Warnung |
|---|---|---|---|
| **Gefahrenart** | `WeatherChange.metric: str` — Summary-Feldnamen wie `thunder_level_max`, `gust_max_kmh` (`app/models.py:548`) | **kein Textfeld**; nur `NowcastResult.is_convective: bool` + `intensity_label` (Freitext, Anzeige) (`radar_service.py:84,87`) | `OfficialAlert.hazard: str` ohne Enum — `"thunderstorm"`, `"flood"`, `"wildfire_risk"`, quellenabhängig (`official_alerts/models.py:21`) |
| **Ortsbezug** | `WeatherChange.segment_id` (Trip) bzw. `location_id` (Compare) (`app/models.py:555`) | `segment_id` + Korridor-km `km_from`/`km_to` (`notification_service.py:172-185`) bzw. `loc.id` | `OfficialAlert.region_label` — **Freitext der fremden Quelle, eigene Geografie** (`official_alerts/models.py:27`) |
| **Zeitfenster** | `occurred_at: datetime\|None` — **Zeitpunkt** (`app/models.py:560`) | `onset_minutes`/`onset_time` — **Zeitpunkt**; der 60-Min-Horizont steckt nur in `radar_service.py:62`, nicht im Objekt | `valid_from`/`valid_to` — echtes **Intervall** (`official_alerts/models.py:24-25`) |

**Es gibt keine Umrechnung zwischen diesen Ausdrucksformen** — weder
`thunder_level_max` ↔ `is_convective=True` ↔ `"thunderstorm"`, noch Korridor-km/Segment-ID ↔
`region_label`. Koordinaten dienen nur dem Abruf und werden nirgends als gemeinsamer Schlüssel
abgelegt.

**Es gibt kein gemeinsames Ereignis-Objekt vor dem Versand.** Die sechs Pfade konvergieren erst
**nach** der Melde-Entscheidung auf `NotificationResult` (`notification_service.py:113-144`).
Bis dahin trägt jeder Pfad seine eigene Nutzlast (`List[WeatherChange]` /
`RadarAlertRequest` / `list[tuple[OfficialAlert, list[str]]]` und die drei Compare-Pendants).

## Messung am produktiven Alarmprotokoll (2026-08-16)

Quelle: `/var/lib/gregor/users/{default,henning,steffi}/alert_log.json`, 260 Einträge gesamt.
Auswertbar sind nur die **41 Einträge mit `reason`-Feld** — das Feld existiert erst seit S1, das
Messfenster ist damit **13 Tage** (2026-08-03 bis 2026-08-16), an allen 13 Tagen gab es Alarme.

**Der gemeldete Fall ist im Protokoll wiedergefunden:** `5f534011`, 2026-08-11 14:22 UTC
`nowcast` mit Metrik `thunder`, **+8,2 Minuten** später `official_alert` mit Hazard
`thunderstorm`. Das ist exakt der Vorfall aus der Issue-Meldung (16:22/16:30 Ortszeit).

| Konstellation (gleiche Entität, ≤ 60 Min) | Anzahl in 13 Tagen |
|---|---|
| **Quellenübergreifend**, verschiedene `reason` | **6** — davon 4× `nowcast`↔`official_alert`, 2× `forecast_change`↔`official_alert` |
| **Gleiche Quelle**, identische Gefahrenart-Menge | **3** — 2× `forecast_change`/`thunder` (+45 / +60 Min), 1× `official_alert`/`thunderstorm` (+30 Min) |

Also rund **eine Doppelmeldung alle 1,5 Tage**. Bemerkenswert: die Doppelung tritt auch
**innerhalb derselben Quelle** auf — der amtliche Fall (+30 Min bei identischer Hazard-Menge) ist
die Kehrseite der bewusst cooldown-freien Eskalation.

**Das Vokabular-Problem ist empirisch belegt**, nicht nur im Code:

| `reason` | Gefahrenart steht in | gemessene Werte |
|---|---|---|
| `forecast_change` | `metrics[].metric_id` (`hazards` immer leer) | `thunder` ×17, `cape` ×3, `gust` ×2, `temperature` ×1 |
| `nowcast` | `metrics[].metric_id` (`hazards` immer leer) | `precipitation` ×5, `thunder` ×1 |
| `official_alert` | `hazards` (`metrics` immer leer) | `thunderstorm` ×11, `extreme_heat` ×4 |

Dasselbe Gewitter heißt je nach Pfad `thunder`, `precipitation`, `cape` oder `thunderstorm` — in
zwei verschiedenen Feldern. Eine Entdopplung braucht also zwingend eine Zuordnungstabelle; ein
String-Vergleich findet die gemessenen Paare **nicht**.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `src/services/alert_gate.py` (374 Z.) | Geteilter Baustein aus S3/S4a: `check_nowcast_gate` (L114-158, Ruhezeit→Sperrzeit→Tageslimit), `check_official_alert_gate` (L161-214, Ruhezeit→Tageslimit, **kein** Cooldown-Parameter), `check_briefing_imminent` (L256-357), `record_nowcast_sent` (L360-374). Wahrscheinlicher Einhängepunkt für S4b. |
| `src/services/trip_alert.py` (1624 Z.) | Drei Trip-Pfade: Δ `check_and_send_alerts():303`, Radar `check_radar_alerts():1057`, amtlich `check_official_alert_triggers():1450`. Enthält den **einzigen bestehenden Cross-Alarmart-Guard** (s.u.). |
| `src/services/compare_alert.py` (591) | Compare-Δ: `_evaluate_one_location():427`, Versand `:279` |
| `src/services/compare_radar_alert.py` (294) | Compare-Nowcast: `_detect_triggered_locations():262`, Versand `:204` |
| `src/services/compare_official_alert.py` (342) | Compare-amtlich: `_detect():271`, Versand `:192` |
| `src/services/throttle_store.py` | Sperrzeiten je `(scope, key)`, Datei `throttle_state.json` je Nutzer. Reale Scopes: `trip`, `radar`, `compare_preset`, `compare_radar` (bewusst eigener Scope, Docstring L44-50). |
| `src/services/alert_state.py` | Melde-Gedächtnis je Entität, `alert_state/<entity_id>.json`, Schema `{"<metric>:<segment_id>": {...}}`. `reset()` beim Briefing-Versand schont den `official_alert:`-Präfixraum (L73-100). |
| `src/services/alert_log.py` | Protokoll mit `entity_id`/`entity_type` (seit S1). `append_suppressed_entry()` (L253-326) schreibt Unterdrückungen — **nur** für die beiden Nowcast-Pfade. |
| `src/output/renderers/alert/official_alerts.py` | `dedupe_official_alerts()` — das **etablierte Dedup-Muster**, aber nur *innerhalb* der amtlichen Warnungen. |
| `src/output/renderers/alert/…format_segment_reference()` | Ergebnis von #1744 Scheibe A: gemeinsame **Anzeige**-Formatierung des Ortsbezugs. |

## Existing Patterns

**Muster 1 — `dedupe_official_alerts()` (kanonisch, aus #1217/#1218/#1245).**
Identitäts-Präzedenz `dedup_id > region_label > label`; Schlüssel
`(ident, hazard, valid_from, valid_to)`; unterschiedliche Zeiträume bleiben bewusst getrennt, nur
exakte Dubletten kollabieren, das höchste Level gewinnt. Dazu die Regel „nie doppelt" (#1086): je
Gefahrenart wird die **beste Quelle behalten**, nicht über Quellen hinweg gemerged.
Einschränkung: wirkt nur zwischen mehreren *amtlichen* Quellen, nicht über die drei Alarmarten.

**Muster 2 — Doppel-Alert-Guard `trip_alert.py:1081-1099` (aus #818 AC-4).**
Der einzige real existierende quellenübergreifende Guard: Der Radar-Pfad liest gezielt die
`AlertStateService`-Schlüssel `precip:<segment_id>` und `thunder_level_max:<segment_id>` — vom
**Änderungsalarm desselben Trips** geschrieben — und unterdrückt den Radar-Alarm, wenn sie jünger
als `cooldown_min` sind. Aber: Trip-intern, fest verdrahtete Schlüsselnamen, liest den State
direkt statt über `alert_gate.py`, **kein Compare-Pendant**. Verallgemeinerbar, nicht
wiederverwendbar wie er ist.

**Muster 3 — Gate-Bausteine aus S3/S4a.** `GateResult(allowed, reason)` als NamedTuple, `reason`
ist eine `alert_log`-Konstante; Prüfungen brechen bei der ersten Stufe ab; Zusicherungen werden als
**Eigenschaft des Funktionstyps** gebaut (S4a AC-3: `check_official_alert_gate` kennt strukturell
keinen Cooldown-Parameter), nicht als Disziplin der Aufrufstelle.

## Dependencies

- **Upstream:** `DeviationAlertEngine` (ADR-0021), `OfficialAlertSource`-Quellen (ADR-0016/0039),
  `radar_service` (INCA/GeoSphere), `ThrottleStore`, `AlertStateService`, `alert_daily_limit`,
  `is_quiet_hours`.
- **Downstream:** `NotificationService` (sechs Versand-Einstiegspunkte), `alert_log` und dessen
  Leseseite `read_undelivered()` (Anzeige-Dedup-Fenster 2 Min, `alert_log.py:337`), Go-Zählung
  `AlertCountByTrip()`, Cockpit/Frontend-Anzeige der Alarme.

## Existing Specs

- `docs/specs/modules/rework_1467_s1_alarm_kennung.md` — eine Kennung `entity_id` + `entity_type`
  ∈ {trip, compare}. **Jede Entdopplung muss auf diesem Kennungsschema aufsetzen.**
- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — Δ-Pfad vereinheitlicht; Pausiert-/
  Archiviert-Riegel `is_silenced` bleibt Compare-eigen.
- `docs/specs/modules/rework_1467_s3_nowcast.md` — Nowcast auf `check_nowcast_gate`;
  Unterdrückungsgründe protokolliert **nur** für Nowcast (AC-9).
- `docs/specs/modules/rework_1467_s4a_amtlich.md` — amtlicher Pfad auf `check_official_alert_gate`.
- `docs/specs/modules/fix_1744_alarm_format_angleichen.md` — Scheibe A: **nur** gemeinsame
  Anzeige-Formatierung, ausdrücklich „Nicht Gegenstand: die quellenübergreifende Entdopplung".
- ADRs: 0009 (Δ-Wächter), 0013 (threshold = Δ-Sensitivität), 0016 (amtlich additiv),
  0021 (gemeinsame Engine, 5 Nachträge), 0039 (MeteoAlarm, drei Zustände strikt trennen),
  0043 (Empfindlichkeitsstufe als einziger Regler, symmetrisch), 0046 (Kanal-Schwelle regelt
  **wie**, nicht **ob**).

## Risks & Considerations

1. **„Alarm bleibt aus" ist die gefährliche Fehlerrichtung.** Vierfach dokumentiert (#1233/F002,
   S2 Z.353f., rework_1460_t1, S4a AC-3): Die amtliche Eskalation bleibt **cooldown-frei**. Eine
   Entdopplung darf keine getarnte Zeitsperre werden — eine echte GELB→ORANGE-Verschärfung muss
   durchkommen. Symmetrisch gilt das für den Nowcast: ein Δ-Alarm um 16:00 darf „Gewitter in 8 Min"
   um 16:22 nicht schlucken.
2. **S4a hat die Gegenrichtung ausdrücklich an S4b übergeben** (Known Limitations): Ein amtlicher
   Alarm schreibt weiterhin in den `"trip"`-Sperrtopf und kann so einen nachfolgenden
   Änderungsalarm drosseln. Das ist mit **Ereignis-Identität** zu ersetzen — nicht mit einer neuen
   Zeitsperre.
3. **Der Ortsbezug ist der teuerste Teil.** Scheibe A hat nur das Rendering vereinheitlicht; das
   Δ-/Onset-Datenmodell trägt die Segment-Kennung **nicht als strukturiertes Feld**. S4b muss
   entweder auf dem Ausgabetext von `format_segment_reference()` aufsetzen (fragil, Anzeigeschicht
   als Identitätsquelle) oder strukturierte Felder nachziehen. Und selbst dann bleibt
   `region_label` die Geografie einer **fremden Quelle** — Segment-ID ↔ Warnregion ist keine
   Gleichsetzung, sondern eine Zuordnung mit eigener Unsicherheit.
4. **Zeitpunkt vs. Intervall.** „Überlappendes Zeitfenster" ist zwischen einem Onset-Zeitpunkt und
   einem Gültigkeitsintervall nicht definiert, solange der Nowcast-Horizont nicht im Objekt steckt.
5. **Drei getrennte Gedächtnisräume** (`<metrik>:<segment>` / kein dokumentierter Nowcast-Schlüssel
   / `official_alert:<ident>:<hazard>:<valid_from>:<valid_to>`) müssen für einen Identitätsvergleich
   erstmals zueinander in Beziehung gesetzt werden, ohne das `reset()`-Verhalten beim
   Briefing-Versand zu brechen (`official_alert:` überlebt den Reset bewusst).
6. **Umfang.** Sechs Pfade, ein neues Identitäts-Konzept, Datenmodell-Erweiterung: sprengt das
   250-Zeilen-Budget deutlich. S4b braucht selbst einen Zuschnitt.
7. **Mandantentrennung:** mit zwei verschiedenen Nutzern testen (alle Zustandsdateien liegen unter
   `get_data_dir(user_id)`).
8. **Trip/Compare-Teilungsregel:** eine Compare-eigene Zweitfassung der Entdopplung wäre ein
   Verstoß.

## Analysis

### Type
Feature (Rework mit bewussten Verhaltensänderungen)

### Der Ortsbezug ist billiger als befürchtet — selbst am Code geprüft

Die Risiko-Einschätzung oben (Punkt 3: „teuerstes Teilproblem") ist nach eigener Nachprüfung
**zu pessimistisch**. Alle drei Trip-Alarmarten führen bereits dieselbe Segment-Kennung mit:

- **Nowcast:** `active.segment_id` steht an der Entscheidungsstelle zur Verfügung
  (`trip_alert.py:1069`, `:1085`) und geht als `normalize_segment_id(active.segment_id)` in den
  Versand (`:1149`). Der Kommentar dort sagt den Zweck ausdrücklich: *„Issue #1744 A1: … nur
  zusaetzlich mit ihrer Kennung, damit der Nowcast denselben Ort benennt wie die amtliche
  Warnung."*
- **Amtlich:** `str(segment.segment_id)` wird je Koordinaten-Gruppe an die Warnung angehängt
  (`trip_alert.py:1423`, `:1432`) — die Zuordnung Warnung→Segment läuft über den
  **Abruf-Koordinaten-Cluster**, nicht über den Freitext `region_label`.
- **Δ-Alarm:** `WeatherChange.segment_id` (`app/models.py:555`).
- **Compare:** durchgängig `loc.id` (`compare_radar_alert.py:273`, `compare_official_alert.py:244`).

`normalize_segment_id()` (`output/renderers/alert/segments.py:17-29`) ist reines
`str(value).strip() or None` — die rohe und die normalisierte Form sind wertgleich. **Einzige
Bruchstelle:** leere Kennung wird zu `None` (amtlich: bleibt `""`). Ortsbezug-Vergleich =
nicht-leere Schnittmenge der Segment-/Ortskennungen; bei fehlender Kennung darf **kein** Match
entstehen (fail-soft Richtung „senden").

Damit braucht S4b **kein neues Datenmodell** — nur einen Gefahrenart-Kanon, ein
Zeitfenster-Prädikat und eine Registerabfrage.

### Technischer Ansatz (Empfehlung)

Neue Funktion **`check_event_identity_gate()` in `src/services/alert_gate.py`** — Verallgemeinerung
des heute schon existierenden, aber Trip-internen und fest verdrahteten Doppel-Alert-Guards
(`trip_alert.py:1081-1099`). Fügt sich als **letzte** Stufe in die bestehende `GateResult`-Kette
(Ruhezeit → Sperrzeit → Tageslimit → Ereignis-Identität), `reason` als neue `alert_log`-Konstante.

Verworfen: (a) ein normalisiertes Ereignis-Objekt vor dem Versand für alle sechs Pfade — baut die
Datenflüsse vor der `NotificationResult`-Konvergenz um, hohes Risiko in der Fehlerrichtung „Alarm
bleibt aus", und unnötig, da die Identitätsbestandteile an den Versandstellen bereits nativ
vorliegen. (c) nur das eine gemessene Paar hart verdrahten — lässt Compare und Starkregen sofort
als Folgebug liegen.

**Gefahrenart-Kanon:** Nur zwei Klassen sind nötig, weil der Nowcast strukturell nur zwei
kennt (`is_convective: bool` + Intensität): *konvektiv/Gewitter* (`thunder`, `cape`,
`is_convective=True`, `thunderstorm`) und *Niederschlag* (`precipitation`, `flood`). Alles andere
kann mit einem Nowcast gar nicht kollidieren.

**Zeitfenster:** Punkt gegen Intervall → `punkt ∈ [valid_from − 60, valid_to + 60]` mit der
bestehenden Konstante `NOWCAST_HORIZON_MIN = 60` (`radar_service.py:65`). Punkt gegen Punkt →
Differenz ≤ vorhandener `cooldown_minutes`. Fehlender Zeitbezug → kein Match → senden.

**Eskalations-Bypass:** erster Zweig mit `return`, vor jeder Unterdrückungslogik. Vorbild
existiert: `official_alert_revision_verdict()` (`output/renderers/alert/official_alerts.py`).

### Scope Assessment

| Teilscheibe | Inhalt | Python | Tests | Schließt #1467? |
|---|---|---|---|---|
| **S4b-1** | `check_event_identity_gate()` + Kanon + Zeitprädikat, verdrahtet in **beide** Trip-Richtungen (`check_radar_alerts`, `check_official_alert_triggers`) | ~90–120 | ~180–220 | **ja** |
| **S4b-2** | Ortsvergleich-Parität — derselbe Baustein, zweite Verdrahtung | ~40–60 | ~100–140 | nein (Folge-Issue) |
| **S4b-3** | Δ-Alarm als dritte Richtung + restliche Gefahrenarten | offen | offen | nein (optional) |

Risk Level: **HIGH** (Alarmpfad, Fehlerrichtung „Alarm bleibt aus"). S4b-1 sprengt das
250-Zeilen-Budget und braucht `loc_limit_override`.

### Risiko-Absicherung (strukturell, nicht per Disziplin)

- Eskalations-Test als erster Zweig mit `return` — die Funktion kennt keinen Weg, eine
  Verschärfung zu blockieren (Muster aus S4a AC-3).
- Fail-soft bei fehlenden/unvergleichbaren Daten fällt **immer** Richtung „senden".
- `alert_state.reset()` schont den `official_alert:`-Präfixraum bewusst (`alert_state.py:73-100`) —
  für das neue Register ist ausdrücklich zu entscheiden, ob es den Briefing-Reset überlebt.
- Mutations-Gegenprobe muss zeigen, welcher Test rot wird, wenn der Eskalations-Bypass entfällt.

### Open Questions (PO-Entscheidung, gehen in die Spec)
- [ ] Wer gewinnt bei gleichem Ereignis: zeitliche Priorität (wer zuerst meldet) oder feste
      Quellen-Hierarchie? Offener Punkt dabei: die amtliche Warnung trägt ein **längeres**
      Gültigkeitsintervall als der 60-Minuten-Nowcast.
- [ ] Verschärfung durchbricht die Entdopplung — bestätigt?
- [ ] Kanalübergreifend statt je Kanal — bestätigt?
