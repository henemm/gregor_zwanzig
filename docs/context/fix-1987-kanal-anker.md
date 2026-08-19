# Context: fix-1987-kanal-anker

**Issue:** #1987 — Alarm-Vergleichsbasis: ein Merker je Kanal, nur bei tatsächlicher Zustellung
**Scope dieser Session:** ausschließlich **Scheibe S1 (Trip)**. Scheibe S2 (Ortsvergleich) bleibt PO-zurückgestellt.
**Track:** Full Process (Intake-Score 5/6)
**Erstellt:** 2026-08-19

## Request Summary

Die Vergleichsbasis eines Abweichungsalarms soll fachlich das sein, was der Empfänger **auf diesem Kanal
zuletzt tatsächlich zugestellt bekommen hat** (PO-Entscheid 2026-08-19). Heute gibt es genau einen
kanallosen Merker je Trip, und er wird auch dann fortgeschrieben, wenn nichts zugestellt wurde.

## Ist-Zustand: drei Snapshot-Dateien, nicht zwei

Das Ticket spricht von „Alarm-Anker und Briefing-Anker". Tatsächlich existieren **drei** Dateien mit
unterschiedlichen Rollen — alle unter `data/users/<user_id>/weather_snapshots/`
(`src/app/loader.py:1171-1173`, produktiv `GZ_DATA_DIR=/var/lib/gregor`):

| Datei | Geschrieben von | Rolle |
|---|---|---|
| `{trip_id}_{YYYY-MM-DD}.json` | `save_dated()`, `weather_snapshot.py:110-138` | **Priorität 1** der Anker-Kette **und** eingefrorene Briefing-Referenz der Radar-Unterdrückung (#818/#1667) |
| `{trip_id}_alarm_anchor.json` | `save_alarm_anchor()`, `weather_snapshot.py:190-219` | rollierender Alarm-Anker (#1916 / ADR-0056) |
| `{trip_id}.json` | `save()`, `weather_snapshot.py:72-108` | undatierter Rückfall; trägt als einzige Datei `briefing_backed` |

**Korrektur zu einer Zwischenannahme:** `save_alarm_anchor()` schreibt **kein** `briefing_backed`-Feld
(`weather_snapshot.py:204-212` — nachgelesen, nicht vermutet). Nur `save()` tut das. Das ist für die
Migration relevant: die drei Dateien haben nicht dasselbe Schema.

Die **doppelte Rolle der datierten Datei** ist der wichtigste Befund dieser Phase: `save_dated()` ist
zugleich Vergleichsbasis und Radar-Unterdrückungs-Referenz. ADR-0056 hält ausdrücklich fest, dass ein
rollierender Schreibvorgang sie **niemals** verändern darf (`weather_snapshot.py:194-199`, AC-11,
abgesichert durch `tests/tdd/test_alert_anchor_radar_isolation.py`). Eine Kanal-Auffächerung darf diese
zweite Aufgabe nicht mitreißen.

### Anker-Prioritätskette (`trip_alert.py:672-763`)

1. `load_dated(trip.id, heute)` → sofort zurück, **ohne** weitere Prüfung (`trip_alert.py:676-678`)
2. `load_alarm_anchor(trip.id)` → nur wenn `alarm_anchor_target_date() == heute`
   (Tagesgrenze #823, AC-10; `trip_alert.py:688-697`)
3. `load(trip.id)` undatiert → Herkunftsprüfung `briefing_backed` (#1699), dann Datum,
   ersatzweise Altersnetz ≤ `_MAX_UNDATED_ANCHOR_AGE` (`trip_alert.py:700-763`)

Verwerfen heißt `None` — und `None` bedeutet **kein Alarm**, nicht „ungenauer Alarm".

### Schreibpfade

| Auslöser | Ort | Bedingung |
|---|---|---|
| Alarm zugestellt | `trip_alert.py:429-434` | `delivered = notif_result.sent` (`trip_alert.py:403`) — **aggregiertes Bool über alle Kanäle** |
| Alterungs-Ceiling | `trip_alert.py:334-345` | kein Alarm gefeuert **und** `_effective_anchor_age > _ALARM_ANCHOR_CEILING` |
| Briefing | `trip_report_scheduler.py:1505-1512` (`_write_briefing_anchor`) | schreibt **beide** Briefing-Dateien; aufgerufen über `_anchor_and_reset()`, `trip_report_scheduler.py:1651` — **unbedingt** |

Grenzwerte: `_ALARM_ANCHOR_CEILING = timedelta(hours=4)` (`trip_alert.py:80`),
`_MAX_UNDATED_ANCHOR_AGE = timedelta(hours=26)` (`trip_alert.py:70`).
`_effective_anchor_age()` (`trip_alert.py:808-826`) nimmt das **jüngere** von Briefing- und rollierendem Anker.

## Das Rohsignal je Kanal liegt bereits vor

`NotificationResult` (`notification_service.py:114-144`):

| Feld | Bedeutung |
|---|---|
| `sent: bool` | mindestens ein konfigurierter Kanal war erreichbar |
| `sent_channels: list[str]` | Kanäle, die **betreten** wurden (Best-Effort, auch bei Transportfehler) |
| `failed_channels: list[str]` | Teilmenge davon, die technisch nicht angekommen ist |
| `blocked_channels` / `blocked_reason_codes` | bewusst nicht betretene Kanäle mit Grund |
| **`delivered_channels`** (Property, Z. 142-144) | `[c for c in sent_channels if c not in failed_channels]` |

`delivered_channels` wird **heute schon** benutzt — aber nur fürs Protokoll
(`trip_alert.py:397` → `alert_log.append_entry(sent_channels=…)`), nicht für den Anker-Write daneben
(`trip_alert.py:429-434`). Der Umbau verwendet vorhandene Daten an einer zweiten Stelle.

Kanal-Bezeichner sind projektweit einheitlich, ohne Enum:
`_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")` (`alert_log.py:70`).
Keine Varianten wie `mail` oder `garmin`.

Kanal-Auflösung für Trip-Alarme: `TripAlertService._effective_alert_channels()` (`trip_alert.py:1810`).
Danach filtert `alert_channel_threshold.split_by_threshold()` (`trip_alert.py:1508-1511`) nach
Dringlichkeitsschwelle — der Notification-Service sieht nur die gefilterte Menge.

## Dependencies

- **Upstream:** `WeatherSnapshotService`, `NotificationResult`, `trip_local_today()`/`anchor_tz()` (Ortszeit, ADR-0051), `alert_log`
- **Downstream:** `DeviationAlertEngine.evaluate()` bekommt `cached=` aus `_get_cached_weather()`; amtliche Warnungen (`check_official_alert_triggers`) nutzen dieselbe Funktion mit `tagesgleicher_anker_noetig=False`

## Existing Specs & ADRs

- **ADR-0056** (Akzeptiert, 2026-08-16) — rollierender Anker, Hybrid-Trigger (a) Alarmversand / (b) 4h-Ceiling. Nicht abgelöst.
- **ADR-0009** — Alerts als Abweichungs-Wächter; Snapshot nur beim Briefing. Durch ADR-0056 in der Persistenz ausgeweitet.
- **ADR-0051** (Vorgeschlagen) — Ortszeit statt Server-Zone; gilt für die Tagesgrenzen-Prüfung.
- **ADR-0021** — geteilte `DeviationAlertEngine`, location-generisch.
- `docs/specs/modules/trip_alert.md` (v3.0) — drei Snapshot-Typen, Hybrid-Trigger, AC-Gruppen A/B
- `docs/specs/modules/weather_snapshot.md` (v1.0) — Persistierungs-API
- `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md` — Tagesgrenzen-Guard

## Bestehende Tests am Anker (9 Dateien)

`tests/tdd/`: `test_alert_rolling_anchor.py`, `test_alert_anchor_no_memory_reset.py`,
`test_alert_anchor_day_guard.py`, `test_alert_anchor_day_boundary.py`,
`test_alert_anchor_radar_isolation.py`, `test_alert_trend_detection_regression.py`,
`test_onset_anchor_fresh_window_symmetry.py`, `test_onset_shift_alert.py`,
`test_compare_alert_anchor_unaffected.py`

Eine Recherche-Einschätzung besagt, die ersten vier würden bei einer zusätzlichen Kanal-Ebene brechen.
**Das ist noch nicht verifiziert** und hängt von der gewählten Umsetzungsvariante ab (Dateiname je Kanal
vs. verschachteltes JSON vs. Default-Parameter). In Phase 2 gegenzuprüfen, nicht zu übernehmen.

## Risks & Considerations

### R1 — Zielkonflikt mit #1629 (der zentrale Punkt)

AC-2 verlangt: kein Kanal zugestellt ⇒ kein Merker. Genau das Gegenteil wurde in **#1629** bewusst
eingeführt (`trip_report_scheduler.py:1527-1531`, Kommentar): ein nicht zustellbares Briefing schreibt
den Anker „seit jeher", weil am 08.08.2026 ein gescheiterter Versand einen **ganzen Tag** Abweichungsalarm
gekostet hat.

Die Schärfe liegt in der Kette: existiert kein tagesgleicher Anker, liefert `_get_cached_weather()` `None`
— die Wache ist dann **still**, nicht bloß ungenau. AC-2 wörtlich umgesetzt kann also einen stillen Ausfall
zurückbringen, den ein früheres Ticket beseitigt hat. Die Spec muss das explizit auflösen; ein Rückfall in
#1629 wäre eine Regression, kein Nebeneffekt.

### R2 — Doppelrolle der datierten Datei

Kanal-Auffächerung von `save_dated()` würde die Radar-Unterdrückungs-Referenz (#818/#1667) mit verändern.
Muss getrennt bleiben (ADR-0056 AC-11).

### R3 — Alterung je Kanal (AC-3)

`_effective_anchor_age()` nimmt heute das Maximum zweier Zeitstempel. Je Kanal gerechnet braucht es eine
prüfbare Definition von „frischester verfügbarer Stand": jüngster Anker eines anderen Kanals, oder der
aktuelle Wetterstand? Entscheidungsvorlage für die Spec.

### R4 — Schwellenfilter vor dem Versand

`split_by_threshold()` entfernt Kanäle **unterhalb** der Dringlichkeitsschwelle vor dem Versand
(`trip_alert.py:1508-1511`). Ein so gefilterter Kanal ist weder „zugestellt" noch „fehlgeschlagen".
Was passiert mit seinem Merker? Ungeklärt, muss in die Spec.

### R5 — Bestandsdaten ohne Inspektionsmöglichkeit

Das produktive Datenverzeichnis `/var/lib/gregor` ist für diese Session nicht lesbar (Rechte).
Die Migration muss also ohne vorherige Bestandsaufnahme sicher sein — Read-Modify-Write, kein Replace
(CLAUDE.md „Daten-Schema-Reworks"). AC-4 fordert genau das.

### R6 — Berührungspunkte anderer Sessions (abgefragt 2026-08-19)

- `gregor-zwanzig-15` (#1971): erweitert `AlertEvaluationConfig` in `point_weather.py` und
  `expand_per_metric_levels()` in `deviation_alert_engine.py`, beides additiv mit Default `False`.
  Textkollision möglich, falls wir dieselben Signaturen anfassen.
- `#1948 S4`: nur Alarm-**Renderer** (`src/output/renderers/alert/`), keine Überschneidung.

## Offene Fragen für Phase 2

1. Wie wird der #1629-Zielkonflikt aufgelöst, ohne die stille Wache zurückzuholen? (R1)
2. Umsetzungsvariante der Kanal-Dimension: eigene Datei je Kanal, verschachteltes JSON, oder Verzeichnisebene? Welche hält die 9 Bestandstests am Leben?
3. Definition „frischester verfügbarer Stand" für AC-3. (R3)
4. Behandlung schwellengefilterter Kanäle. (R4)
5. Bekommt der Briefing-Pfad überhaupt eine Kanal-Dimension, oder nur der rollierende Anker? (R2)
