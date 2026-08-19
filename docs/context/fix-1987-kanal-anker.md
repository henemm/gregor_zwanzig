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

---

## Analysis (Phase 2)

### Type
Bug mit Umbaucharakter (Label `type:bug`, `triage:a` — nutzersichtbares Fehlverhalten), umgesetzt als
Erweiterung eines bestehenden Mechanismus (ADR-0056), nicht als Neubau.

### Der Schlüsselbefund: die #1629-Garantie hängt gar nicht am rollierenden Anker

Selbst nachgeprüft (`trip_report_scheduler.py:1543` und `:1651`): `_anchor_and_reset()` — und damit
`save()` + `save_dated()` — wird **zweimal unbedingt** aufgerufen: einmal im `except`-Zweig um den
Versandaufruf, einmal im regulären Weg außerhalb jeder `sent`-Verzweigung.

Daraus folgt die Auflösung des Zielkonflikts aus R1:

- **Tier 1** (datierter Briefing-Anker) trägt die #1629-Garantie gegen die stille Wache. Er bleibt
  unbedingt und kanalagnostisch — ohnehin zwingend, weil er zugleich die Radar-Unterdrückungs-Referenz
  ist (ADR-0056 AC-11).
- **Tier 2** (rollierender Alarm-Anker) kann daher **vollständig** kanalscharf und zustellungsgebunden
  werden, ohne die stille Wache zurückzuholen: fehlt einem Kanal sein Tier-2-Eintrag, fällt die Kette
  auf Tier 1 zurück, der taggleich immer vorhanden ist.

Das macht Variante (ii) aus der Vorüberlegung — ein zusätzlicher „technischer" kanalloser Anker —
überflüssig. Er existiert bereits.

### Gewählte Umsetzungsvariante: eine Datei je Kanal

`{trip_id}_alarm_anchor_{channel}.json` statt verschachteltem JSON.

Begründung: `weather_snapshot.py` führt seine drei Rollen bereits als drei separate Dateien
(`:104`, `:131`, `:215`), jede Methode überschreibt vollständig — es gibt **keinen** Merge-Pfad im Modul.
Verschachteltes JSON bräuchte einen neuen Read-Modify-Write-Mechanismus, weil die vier Kanäle nie
gleichzeitig geschrieben werden. Variante (a) verlängert das etablierte Muster um eine Achse.
Unterverzeichnis je Kanal bringt keinen Zusatznutzen.

Der vervierfachte Platzbedarf (der Anker hält vollständige Stundenreihen aller Etappen) ist **nicht**
vermeidbar und auch nicht durch verschachteltes JSON zu umgehen: divergierende Zustellung bedeutet
fachlich verschiedene Wetterstände je Kanal — genau der Zweck des Tickets. Deduplizierung wäre falsch.

### AC-4 (Bestandsdaten) — Korrektur zur Agenten-Empfehlung

Die strategische Bewertung schlug vor, die alte kanallose `{trip_id}_alarm_anchor.json` verwaisen zu
lassen (reiner Ableitungs-Cache). **Das widerspricht AC-4.** Richtig ist:
`load_alarm_anchor(trip_id, channel)` fällt auf die kanallose Altdatei zurück, wenn die kanalspezifische
fehlt — damit dient der Bestand beim ersten Lauf allen Kanälen als Ausgangsbasis, ohne Migrationsskript
und ohne Datenverlust. Der Rückfall ist zugleich der natürliche Zustand für jeden Kanal, der noch nie
zugestellt hat.

### Schwellengefilterte Kanäle (R4) — geklärt, keine Sonderregel nötig

Ein von `split_by_threshold()` entfernter Kanal (`trip_alert.py:1508-1511`) erscheint weder in
`sent_channels` noch in `failed_channels`, also nie in `delivered_channels`
(`notification_service.py:142-144`). Unter der zustellungsgebundenen Regel bekommt er damit von selbst
keinen frischen Merker — fachlich richtig, denn der Empfänger hat auf diesem Kanal nichts bekommen.

Die Fehlerquelle liegt in der Umsetzung, nicht im Konzept: iteriert der Schreibpfad versehentlich über
`effective_channels` statt `delivered_channels`, bricht die Zusicherung **still**. Das braucht einen
eigenen Test und ist ein Pflicht-Punkt der Mutations-Gegenprobe.

### AC-3 „frischester verfügbarer Stand" — Empfehlung (c)

| Option | Folge |
|---|---|
| (a) jüngster Merker eines **anderen** Kanals | Kontamination: SMS vergliche gegen einen Stand, den nur die E-Mail erhalten hat — unterläuft den Ticket-Zweck |
| (b) der aktuelle `fresh_weather` | Vergleich gegen sich selbst ⇒ strukturell Nulldifferenz ⇒ der Kanal meldet dauerhaft „keine Änderung": ein stiller Ausfall anderer Bauart |
| **(c) der taggleiche Tier-1-Briefing-Anker** | **empfohlen** — behauptet keine Zustellung, ist immer vorhanden, ist bereits Teil der bestehenden Kette; keine neue Logik |

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | `save_alarm_anchor` / `load_alarm_anchor` / `alarm_anchor_target_date` um `channel` erweitern; Dateinamensschema; Rückfall auf kanallose Altdatei (AC-4) |
| `src/services/trip_alert.py` | MODIFY | `_write_rolling_alarm_anchor` über `delivered_channels` schleifen; Tier-2-Schritt der Kette kanalscharf; `_effective_anchor_age` je Kanal |
| 5 Bestandstests (Dateiname/JSON direkt) | MODIFY | `test_alert_rolling_anchor.py`, `test_alert_anchor_day_guard.py`, `test_onset_anchor_fresh_window_symmetry.py`, `test_onset_shift_alert.py`, `test_compare_alert_anchor_unaffected.py` |
| 4 Bestandstests (nur API) | ggf. unverändert | überleben, wenn `channel` einen Default bekommt |
| neue Tests | CREATE | AC-1 bis AC-4 + Schwellenfilter-Fall |
| `docs/adr/ADR-0056` | MODIFY | Amendment (Weiterentwicklung desselben Mechanismus, keine Ablösung, kein neues ADR) |

**Refactoring-Oberfläche im Produktivcode ist klein:** außerhalb von `weather_snapshot.py` kennt nur
`trip_alert.py` den Anker (`:343`, `:432`, `:688`, `:796`, `:804`, `:819`).

### Scope Assessment
- Produktivdateien: 2
- Geschätzte LoC: +100 bis +160 (Limit 250; Tests und `docs/` zählen nicht)
- Risiko: **MITTEL** für Speicher- und Gating-Änderung (etabliertes Muster, dichtes Testnetz)

### Open Questions — PO-Entscheid nötig

1. **AC-2 wörtlich würde #1629 brechen.** AC-2 verweist auf den Briefing-Anker
   (`trip_report_scheduler.py:1527-1531`). Genau dieser unbedingte Write ist die #1629-Absicherung.
   Vorschlag: AC-2 gilt für den **rollierenden** Anker (Tier 2), Tier 1 bleibt unbedingt.
2. **Ein Evaluierungslauf oder einer je Kanal?** Heute wertet die Engine **einmal** gegen **einen**
   `cached`-Stand aus (`trip_alert.py:311-329`), das Ergebnis geht an alle Kanäle. Kanalscharfe Anker
   werfen die Frage auf, ob je Kanal getrennt ausgewertet wird. Vorschlag für S1: ein gemeinsamer Lauf;
   die Kanal-Präzision wirkt auf Schreib-/Lesepfad und die Nachweiszeile, nicht auf die
   Auslöse-Entscheidung.
3. **Scope-Grenze:** Der Briefing-Anker bleibt kanalagnostisch. Ein Kanal ohne eigenen Tier-2-Eintrag
   vergleicht gegen den Tagesstand, den er möglicherweise selbst nie erhalten hat.

### PO-Entscheide 2026-08-19 (Phase 2, Abschluss)

**E1 — AC-2 gilt nur für Ebene 2 (rollierender Alarm-Anker).**
Der Briefing-Anker (Tier 1) bleibt unbedingt und kanalagnostisch; #1629 wird nicht zurückgedreht,
die Radar-Unterdrückungs-Referenz bleibt unangetastet. Ein Kanal ohne eigenen Tier-2-Eintrag fällt
auf den Tagesstand zurück und bekommt weiterhin Alarme, nur mit gröberer Vergleichsbasis.

**E2 — Ein gemeinsamer Auswertungslauf, getrennte Merker.**
Die Auslöse-Entscheidung bleibt gemeinsam. Kanalgetrennt sind ausschließlich: (1) welcher Kanal seinen
Merker fortschreibt, (2) welcher Vergleichsstand im Text ausgewiesen wird (`reference_at`, #1916 AC-1..5).
Der geteilte `DeviationAlertEngine`-Pfad (ADR-0021), den auch amtliche Warnungen nutzen, wird nicht
angefasst. Eine getrennte Auswertung je Kanal wäre eine eigene Scheibe.

Damit sind die offenen Fragen 1 und 2 geschlossen; Frage 3 (Scope-Grenze) ist die dokumentierte Folge
von E1 und geht als solche in die Spec.
