---
entity_id: trip_alert
type: module
created: 2026-02-10
updated: 2026-08-16
status: draft
version: "3.0"
tags: [alert, trip, weather, change-detection, story3, fix-1916]
workflow: fix-1916-alarm-vergleichsbasis
---

# Trip Alert Service

## Approval

- [ ] Approved

> **Hinweis (2026-08-16):** Der Approval-Status wurde für diese Erweiterung
> (Issue #1916) bewusst auf unchecked zurückgesetzt. Die v2.0-Inhalte unten
> (Throttling, Scheduler-Integration, persistenter Throttle-Speicher) sind
> historisch bereits umgesetzt und produktiv — sie sind seit Februar 2026
> **erheblich weiterentwickelt** (u.a. #1447 Zeitbudget, #1661/#1697
> Tagesanker-Prüfung, #1444 Korridor-Alarme, #1170/#1467 Ortsvergleich-
> Bündelung), ohne dass diese Spec-Datei mitgezogen wurde. Diese Erweiterung
> aktualisiert NUR den für #1916 relevanten Ausschnitt (`_get_cached_weather`,
> Referenz-Zeitpunkt-Rendering) und dokumentiert ihn korrekt gegen den
> tatsächlichen Code-Stand; sie schreibt die restliche Historie nicht neu.

## Purpose

Sendet sofortige Alerts (E-Mail/Telegram/SMS/Premium-SMS) bei signifikanten
Wetteränderungen (severity >= moderate) sowie bei Schwellen-/Korridor-Treffern
und Radar-Onset-Ereignissen. Nutzt `WeatherChangeDetectionService` für die
Δ-Erkennung und die geteilte Alert-Renderer-Pipette (`output/renderers/alert/`)
für alle vier Kanäle. **Issue #1916:** Die Vergleichsbasis für den
Abweichungsalarm wird als "Briefing-Anker" ausschließlich beim erfolgreichen
Trip-Briefing-Versand geschrieben; scheitert dieses (vgl. #1897), bleibt die
Basis bis zu 24h alt und der Δ-Vergleich vergleicht gegen einen stillen,
veralteten Stand. Diese Erweiterung macht den Referenz-Zeitpunkt sichtbar und
lässt die Basis rollierend nachziehen, ohne die #823-Tagesgrenze, die
Radar-Unterdrückung (#818/#1667) oder die Trend-Erkennung zu brechen.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService`, insb. `_get_cached_weather()` (Zeile
  540-661), `check_all_trips()` (Zeile 387-538), `check_and_send_alerts()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_change_detection.py` | module | Erkennt signifikante Änderungen |
| `src/services/weather_snapshot.py` | module | `WeatherSnapshotService` — Briefing-Anker (`save_dated`/`load_dated`), undatierter Fallback (`save`/`load`/`load_target_date`); Issue #1916: dritter, rollierender Anker-Typ kommt hier hinzu |
| `src/services/trip_report_scheduler.py` | module | `_write_briefing_anchor()` — bisher einziger Schreibpfad des Δ-Vergleichs-Ankers |
| `src/services/alert_briefing_anchor.py` | module | `write_anchor_and_reset_memory()` koppelt Anker-Schreiben mit Melde-Gedächtnis-Reset — Issue #1916 braucht einen zweiten, schlankeren Schreibpfad ohne diesen Reset |
| `src/services/notification_service.py` | module | `send_deviation_alert()`/`send_multi_location_deviation_alert()` — bauen `stand_at` bisher aus `datetime.now()` statt der Vergleichsbasis |
| `src/output/renderers/alert/model.py` | module | `AlertMessage`-DTO, kanonisch über alle vier Kanäle |
| `src/output/renderers/alert/project.py` | module | `to_alert_message()`/`to_multi_point_alert_message()` — Trip- und Compare-Δ-Alarme geteilt |
| `src/output/renderers/alert/render.py` | module | Rendering aller vier Kanäle; hartcodierter Footer-Text "verglichen mit dem letzten Briefing" (Zeile ~517/562/807) |
| `internal/scheduler/scheduler.go:145` | module | Cron `*/15 * * * *` — Abweichungs-Alarm-Check-Intervall (verifiziert: 15 Min, nicht die im Python-Docstring genannten 30 Min) |

## Scope (Issue #1916)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/weather_snapshot.py` | MODIFY | Neuer, dritter Anker-Typ: eigener Speicherort/Methodenpaar (z.B. `save_alarm_anchor()`/`load_alarm_anchor()`), undatiert, eigene Alterslogik. KEIN Umwidmen von `save_dated`/`load_dated` (sonst bricht #818/#1667) |
| `src/services/trip_alert.py` | MODIFY | `_get_cached_weather()` um dritte Quelle (rollierender Anker) erweitert; neuer Schreibpfad nach jedem Check-Lauf (Hybrid-Trigger a/b, s.u.); Referenz-Zeit (Anker-`fetched_at`) an `check_and_send_alerts()`/`_send_alert()`/`notification_service` durchreichen |
| `src/services/notification_service.py` | MODIFY | `send_deviation_alert()` (Zeile ~628-667) und `send_multi_location_deviation_alert()` (Zeile ~691-739): `stand_at` nicht mehr aus `datetime.now()`, sondern aus dem Referenz-Zeitpunkt der Vergleichsbasis; neuer Parameter für den Referenz-Zeitpunkt |
| `src/output/renderers/alert/model.py` | MODIFY | `AlertMessage` bekommt neues, additives Feld für den Referenz-Zeitpunkt (Name z.B. `reference_at: str \| None`, Default `None` — Regressions-Invariante wie `location_label`/`corridor_events`) |
| `src/output/renderers/alert/project.py` | MODIFY | `to_alert_message()`/`to_multi_point_alert_message()` reichen den neuen Referenz-Zeitpunkt durch |
| `src/output/renderers/alert/render.py` | MODIFY | Footer-Text "verglichen mit dem letzten Briefing" (Zeile ~517, ~562, ~807) ersetzt durch Referenz-Zeitpunkt-Text; SMS/Premium-SMS-Zweig mit ≤160-Zeichen-Budget angepasst; amtliche Warnungen/Radar-Onset (Zeile ~222/277/480, kein `reference_at`) bleiben unverändert bei "Stand: heute HH:MM" |
| `src/services/compare_alert.py` | MODIFY | **Nachtrag (Fix-Loop nach Adversary-Runde 1, F001):** AC-4 verlangt den Referenz-Zeitpunkt auch im Compare-Δ-Alarm — `_evaluate_one_location()` extrahiert `anchor_fetched_at` aus dem bereits geladenen Compare-Snapshot, der Versand-Loop baut daraus `reference_at` und reicht es an `send_multi_location_deviation_alert()` durch. **Wichtig, Abgrenzung zu AC-13:** dies ist AUSSCHLIESSLICH die Sichtbarkeits-Durchreichung (Slice 1/AC-4) — der dritte, rollierende Anker-Typ (Slice 2, `save_alarm_anchor`/`load_alarm_anchor`) wird NICHT in `compare_alert.py` aufgerufen (AC-13 bleibt erfüllt, eigener Test `test_compare_alert_anchor_unaffected.py` verifiziert Call-Count 0) |
| Kern-Tests (neu) | CREATE | Golden-Message je Kanal (E-Mail/Telegram/SMS/Premium-SMS, Trip + Compare), Trend-Regressionstest, #823/#818-Interaktionstests, Anker-Prioritätskette (Briefing-Anker vs. rollierender Anker vs. undatierter Fallback), Compare-Wiring-Test (AC-4) + Compare-Isolations-Test (AC-13) |

### Estimated Changes

- Files: 6-8 Produktionsdateien (siehe oben) + Kern-Tests
- LoC: ~800-1200 gesamt inkl. Tests über beide AC-Gruppen (aus Phase-2-Analyse; TDD-Red ist Pflicht, Repo hat ausführliche Docstring-Kultur)
- Effort: medium-high (AC-Gruppe A: low; AC-Gruppe B: medium-high wegen #823/#818/Trend-Interaktion)

## Implementation Details (Issue #1916)

**AC-Gruppe A — Sichtbarkeit:** Nutzt ausschließlich bereits vorhandene Daten
(`SegmentWeatherData.fetched_at` trägt den Referenz-Zeitstempel der geladenen
Vergleichsbasis bereits, kein neues Snapshot-Feld nötig). Der Referenz-
Zeitpunkt wird an der Stelle bestimmt, wo `_get_cached_weather()` die
Vergleichsbasis lädt (`trip_alert.py`), und von dort über
`check_and_send_alerts()` → `notification_service.send_deviation_alert()` →
`to_alert_message()` → `AlertMessage.reference_at` bis zum Renderer
durchgereicht. Betrifft AUCH den Compare-Δ-Alarm (geteilter Renderer,
`send_multi_location_deviation_alert()`), da dort dieselbe `AlertMessage`/
`render.py`-Pipeline läuft — dessen eigene, undatierte Snapshot-Quelle liefert
den Referenz-Zeitpunkt analog über deren `fetched_at`.

**AC-Gruppe B — Rollierende Basis:** Baut auf Gruppe A auf. Ein dritter,
separater Snapshot-Typ (nicht `save_dated`/`load_dated`, s. Risiko #818/#1667)
wird mit einem Hybrid-Schreibzeitpunkt gefüllt:

- (a) bei jedem TATSÄCHLICH versendeten Alarm (verallgemeinert #816 von "nur
  Briefing" auf "jeder erfolgreiche Alarmversand") — **supersedes #816 (B)**
  ("kein Snapshot-Write mehr bei Alarmversand, Referenz bleibt bis zum
  nächsten Briefing stabil", `trip_alert.py:353-354` alte Fassung). Siehe
  ADR-Abschnitt unten.
- (b) opportunistisch, wenn der aktuell wirksame Anker (Briefing- ODER
  rollierender Anker, der jüngere von beiden) eine Alterungs-Ceiling
  überschreitet, auch ohne ausgelösten Alarm. Ceiling-Vorschlag: **4 Stunden**
  (Mittelwert des im Kontext-Dokument vorgeschlagenen Bereichs 3-6h; verifiziert
  gegen das tatsächliche Check-Intervall von 15 Minuten, `scheduler.go:145` —
  4h ≈ 16 Check-Läufe, groß genug um das Δ-Fenster nicht auf einen einzelnen
  Lauf zu verkleinern, klein genug um das ~24h-Symptom aus #1916 zuverlässig zu
  kappen). Als benannte Konstante mit Kommentar im Code, nicht hart verdrahtet.

Der neue Schreibpfad ruft explizit NICHT `write_anchor_and_reset_memory()`
auf (das koppelt Schreiben mit Melde-Gedächtnis-Reset), sondern einen neuen,
schlankeren Pfad, der nur den rollierenden Anker schreibt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/.../test_alert_reference_timestamp.py` — AC-1 bis AC-5 (Sichtbarkeit, alle vier Kanäle + Compare)
- [ ] `tests/.../test_alert_rolling_anchor.py` — AC-6 bis AC-8 (Hybrid-Schreibtrigger a/b)
- [ ] `tests/.../test_alert_trend_detection_regression.py` — AC-9 (kritischer Regressionstest)
- [ ] `tests/.../test_alert_anchor_day_boundary.py` — AC-10 (#823-Interaktion)
- [ ] `tests/.../test_alert_anchor_radar_isolation.py` — AC-11 (#818/#1667-Interaktion)
- [ ] `tests/.../test_alert_anchor_no_memory_reset.py` — AC-12 (Melde-Gedächtnis)
- [ ] `tests/.../test_compare_alert_anchor_unaffected.py` — AC-13 (Compare-Scope-Grenze)

## Acceptance Criteria

### AC-Gruppe A — Sichtbarkeit (Slice 1, risikoarm)

- **AC-1:** Given ein Abweichungs-Alarm für einen Trip wird per E-Mail versendet / When die Alarmnachricht gerendert wird / Then zeigt der Footer den Referenz-Zeitpunkt der tatsächlich verglichenen Vergleichsbasis (Ortszeit, "HH:MM") statt des generischen Texts "verglichen mit dem letzten Briefing".
  - Test: E-Mail-Golden-Message mit fixiertem Anker-`fetched_at` prüft den gerenderten Footer-Text auf den erwarteten Zeitstempel, nicht auf Dateiinhalts-Presence.

- **AC-2:** Given die Vergleichsbasis stammt von einem anderen Kalendertag (Ortszeit) als der aktuelle Check-Zeitpunkt / When die Alarmnachricht formatiert wird / Then enthält der Referenz-Zeitpunkt einen expliziten Tagesbezug (z.B. "gestern 18:03 Uhr"), nicht nur eine nackte Uhrzeit.
  - Test: Fixture mit Anker vom Vortag erzeugt einen Alarm um 06:00 Ortszeit; der gerenderte Text unterscheidet sich nachweisbar vom Fall "Anker von heute".

- **AC-3:** Given ein Abweichungs-Alarm wird als SMS oder Premium-SMS versendet / When der Referenz-Zeitpunkt-Text in die Kurznachricht eingefügt wird / Then bleibt die Gesamtlänge der Nachricht in jedem getesteten Szenario ≤160 Zeichen — die bestehende Kürzungslogik hat Vorrang, der Referenz-Zeitpunkt wird notfalls weiter verkürzt statt das Budget zu überschreiten.
  - Test: SMS-Renderer wird mit einem Alarm mit maximaler Event-Anzahl UND Referenz-Zeitpunkt-Text aufgerufen; `len(sms_text) <= 160` wird assertiert.

- **AC-4:** Given ein gebündelter Ortsvergleich-Alarm (Compare, ≥2 Orte) nutzt dieselbe geteilte Alert-Renderer-Pipeline / When die Nachricht über alle vier Kanäle gerendert wird / Then zeigt auch dort der Footer korrekt den Referenz-Zeitpunkt der Compare-eigenen Snapshot-Quelle, ohne dass ein Kanal abweicht oder ausfällt.
  - Test: Golden-Message-Regressionstest für Compare-E-Mail und Compare-SMS mit fixierter Compare-Snapshot-`fetched_at`.

- **AC-5:** Given amtliche Warnungen oder Radar-Onset-Alarme (kein Δ-Vergleich gegen eine Vergleichsbasis) / When sie über dieselbe Renderer-Pipeline gerendert werden / Then bleibt deren Footer unverändert bei "Stand: heute HH:MM" (aktuelle Abrufzeit) — Slice 1 berührt ausschließlich Δ-Vergleichs-Alarme.
  - Test: Bestandstest für `_render_email_corridor_only`/Radar-Onset-Pfad bleibt byte-identisch grün (Regressions-Invariante).

### AC-Gruppe B — Rollierende Basis (Slice 2, baut auf Gruppe A auf)

- **AC-6:** Given der Abweichungs-Alarm-Check läuft alle 15 Minuten (`check_all_trips`) und stellt einen tatsächlichen Alarm fest (Δ über Schwelle) / When der Versand über mindestens einen Kanal erfolgreich war / Then wird ein neuer rollierender Anker-Snapshot mit aktuellem Wetterstand und Zeitstempel geschrieben, unabhängig davon ob zuvor ein Briefing erfolgreich war.
  - Test: Alarm-Check-Lauf ohne vorheriges Briefing löst Alarm aus; anschließend liefert `load_alarm_anchor()` einen frischen Zeitstempel.

- **AC-7:** Given seit dem jüngeren der beiden Anker (Briefing-Anker oder rollierender Anker) sind mehr als die Alterungs-Ceiling (4h) vergangen UND der aktuelle Check-Lauf löst KEINEN Alarm aus / When der Check-Lauf durchläuft / Then wird trotzdem opportunistisch ein neuer rollierender Anker mit dem aktuellen Wetterstand geschrieben.
  - Test: Fixture mit 5h altem Anker und unterschwelligem Δ; nach dem Lauf ist ein neuer rollierender Anker vorhanden, obwohl `check_and_send_alerts()` `False` zurückgab.

- **AC-8:** Given ein gescheitertes Briefing (Konstellation wie #1897) hinterlässt einen >24h alten Anker / When nachfolgende Check-Läufe die Alterungs-Ceiling überschreiten / Then wird die Vergleichsbasis binnen der Ceiling automatisch aufgefrischt, ohne manuellen Eingriff und ohne ein erneut erfolgreiches Briefing — das ursprüngliche #1916-Symptom (~24h alter Vergleichswert) tritt nicht mehr auf.
  - Test: End-to-End-Fixture simuliert einen ausgefallenen Briefing-Lauf über mehrere Stunden; nach Überschreiten der Ceiling ist die Anker-Alter-Obergrenze eingehalten.

- **AC-9 (kritischer Regressionstest — Trend-Erkennung):** Given ein Messwert steigt über mehrere aufeinanderfolgende 15-Minuten-Check-Läufe kontinuierlich an, wobei jeder Einzelschritt unter der Alarm-Schwelle bleibt, aber die kumulierte Änderung seit dem zuletzt GESCHRIEBENEN Anker die Schwelle überschreitet / When mehrere derartige Check-Läufe nacheinander laufen, ohne dass die Alterungs-Ceiling zwischenzeitlich erreicht wurde und ohne dass ein Alarm ausgelöst wurde / Then löst ein späterer Lauf trotzdem einen Alarm aus, sobald die kumulierte Differenz zur unverändert gebliebenen Vergleichsbasis die Schwelle überschreitet.
  - Test: Sequenz von z.B. 6 Check-Läufen mit je unterschwelligem 15-Min-Delta, aber überschwelligem Gesamt-Delta seit dem letzten Anker; der letzte Lauf muss einen Alarm auslösen. Mutations-Gegenprobe: ein "Anker bei jedem Lauf ohne Alarm überschreiben" MUSS diesen Test rot machen.

- **AC-10:** Given die #823-Tagesgrenze gilt für den Δ-Vergleich (`tagesgleicher_anker_noetig=True`) / When der wirksame Anker (Briefing- oder rollierender Anker) für den Abweichungsalarm gelesen wird / Then unterliegt der rollierende Anker derselben Tagesprüfung wie der Briefing-Anker — ein rollierender Anker vom falschen Kalendertag (Ortszeit) wird verworfen statt gegen "heute" verglichen zu werden.
  - Test: Rollierender Anker mit `target_date = gestern` wird um 00:05 Ortszeit gelesen; `_get_cached_weather(tagesgleicher_anker_noetig=True)` gibt `None` oder verwirft den Anker nachweisbar (kein "heute gegen gestern"-Δ).

- **AC-11:** Given die Radar-Alert-Unterdrückung (#818/#1667) liest weiterhin ausschließlich den Briefing-Anker über `load_dated()` als eingefrorene Prognose / When der neue rollierende Anker-Schreibpfad läuft / Then bleibt die Briefing-Anker-Datei (`{trip_id}_{date}.json`) davon unberührt — der rollierende Anker liegt in einem eigenen Speicherort und wird nie über `save_dated()` geschrieben.
  - Test: Radar-Unterdrückungs-Bestandstest (`trip_alert.py:1068-1070`) bleibt grün, während parallel rollierende Anker geschrieben werden; Dateisystem-Assertion, dass die Briefing-Anker-Datei unverändertes `mtime`/Inhalt hat.

- **AC-12:** Given ein Wert wurde bereits in einem früheren Alarm über das Melde-Gedächtnis (`alert_briefing_anchor.py`) als gemeldet vermerkt / When der rollierende Schreibpfad (Trigger a oder b) einen neuen Anker schreibt / Then wird das Melde-Gedächtnis dabei NICHT zurückgesetzt — bereits gemeldete Werte werden beim nächsten Vergleich nicht erneut als "neu" gemeldet.
  - Test: Melde-Gedächtnis wird vor dem rollierenden Schreibvorgang mit einem Eintrag vorbelegt; nach dem Schreiben ist der Eintrag unverändert vorhanden (kein Reset-Aufruf nachweisbar, z.B. per Spy/Call-Count auf die schlankere Schreibfunktion statt `write_anchor_and_reset_memory()`).

- **AC-13:** Given der Ortsvergleich-Pfad (`compare_alert.py`/`CompareWeatherSnapshotService`) nutzt eine eigene, undatierte Snapshot-Mechanik ohne #823-Tagesgrenze / When AC-Gruppe B implementiert wird / Then bleibt dieser Pfad vollständig unverändert — die rollierende Trip-Basis (dritter Anker-Typ, Hybrid-Trigger, Ceiling) wird nicht auf Compare übertragen.
  - Test: Bestehende Compare-Alarm-Bestandstests bleiben byte-identisch grün; kein neuer Aufruf des rollierenden Trip-Anker-Codes aus dem Compare-Modul nachweisbar (Import-/Aufruf-Grep als Adversary-Check).

## Known Limitations (Issue #1916)

- Die exakte Alterungs-Ceiling (hier: 4h) ist eine begründete Empfehlung, kein
  vom PO bestätigter Fixwert — bei der Implementierung als benannte Konstante
  mit Kommentar ablegen, nicht in Tests hart verdrahten, falls sich der Wert
  nach Praxiserfahrung noch ändert.
- AC-Gruppe B ist bewusst auf den Trip-Pfad beschränkt (AC-13); der
  Ortsvergleich-Δ-Alarm bleibt bei seiner heutigen, stabilen Referenz.
- Slice 1 und Slice 2 sind unabhängig lieferbar; sollte aus Kapazitätsgründen
  nur Slice 1 umgesetzt werden, bleibt das ursprüngliche #1916-Symptom
  (bis zu 24h alte Basis nach gescheitertem Briefing) formal weiter bestehen —
  nur sichtbar gemacht, nicht behoben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** [ADR-0056](../../adr/0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md)
  (2026-08-16, Status: Akzeptiert).
- **Rationale:** AC-Gruppe B revidiert bewusst einen Teil der dokumentierten
  Architekturentscheidung ADR-0009 ("Snapshot wird ausschließlich beim
  Briefing-Versand persistiert, ohne Briefing kein Anker"). PO-Entscheid
  2026-08-16: "Handle als Tech Lead nach Best-Practice-Regeln" — gemäß
  CLAUDE.md-Vorgabe ("Abweichung ⇒ neues ADR, Status 'Abgelöst durch'") wurde
  ADR-0056 angelegt und ADR-0009 auf "Teilweise abgelöst durch ADR-0056"
  gesetzt (das Grundprinzip "Abweichungs-Wächter, keine absolute Schwelle"
  aus ADR-0009 bleibt unverändert gültig).

---

## Historie (v1.0–v2.0, Februar 2026)

> Die folgenden Abschnitte beschreiben den ursprünglichen Entwurf (Phase 1-3,
> Feb 2026). Sie sind historisch und teilweise durch spätere Issues
> überholt (siehe Approval-Hinweis oben); sie werden hier unverändert
> belassen, damit die Herkunft der Klasse nachvollziehbar bleibt.

## Architecture

```
TripAlertService
    |
    +-- check_and_send_alerts(trip: Trip, cached_weather: list[SegmentWeatherData])
    |       |
    |       +-- 1. Fetch fresh weather for segments
    |       +-- 2. Compare: WeatherChangeDetectionService.detect_changes()
    |       +-- 3. Filter: severity in [MODERATE, MAJOR]
    |       +-- 4. Throttle: check _last_alert_times[trip.id]
    |       +-- 5. Format: TripReportFormatter(type="alert", changes=...)
    |       +-- 6. Send: EmailOutput.send()
    |       +-- 7. Update: _last_alert_times[trip.id] = now
    |
    +-- _last_alert_times: dict[str, datetime]  # In-memory throttle store
    +-- _throttle_hours: int = 2
```

## Configuration

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| throttle_hours | 2 | Min. Zeit zwischen Alerts pro Trip |
| severity_filter | MODERATE, MAJOR | Welche Severities triggern Alert |

## Known Limitations (v2.0, historisch)

- Kein SMS-Versand (nur Email im MVP, Phase 4-6) — **überholt:** alle vier
  Kanäle sind seit ADR-0049 verdrahtet.
- Keine User-Config für Throttle-Zeit (hardcoded 2h)
- check_all_trips() braucht cached weather - aktuell kein zentraler Cache
  verfügbar — **überholt:** `_get_cached_weather()` liest heute den
  Briefing-Anker über `WeatherSnapshotService`.

## Phase 3: Scheduler Integration + Persistent Throttle (v2.0)

Neuer APScheduler-Job (historisch; die tatsächliche Cron-Registrierung liegt
heute in `internal/scheduler/scheduler.go:145`, `*/15 * * * *`):

```python
_scheduler.add_job(
    run_alert_checks,
    CronTrigger(minute="0,30", timezone=TIMEZONE),
    id="alert_checks",
    name="Alert Checks (every 30 min)",
)
```

Persistenter Throttle-Speicher: `data/users/{user_id}/alert_throttle.json`,
JSON-Mapping `trip_id -> ISO-Zeitstempel`.

## Changelog

- 2026-02-10: v1.0 Initial spec created (Feature 3.4)
- 2026-02-13: v2.0 Phase 3: Scheduler integration, persistent throttle, check_all_trips(), from_trip_config() passthrough
- 2026-08-16: v3.0 (Issue #1916) — Entscheidung: bestehende `trip_alert.md`
  aktualisiert statt neuer Spec-Datei, da dieselbe Entity (`TripAlertService`)
  und derselbe Kern-Mechanismus (`_get_cached_weather()`) betroffen sind —
  eine neue Datei hätte die Vergleichsbasis-Logik künstlich über zwei
  Spec-Dokumente gespalten. Ergänzt zwei AC-Gruppen: (A) Referenz-Zeitpunkt
  sichtbar machen in Alarmnachrichten aller vier Kanäle inkl. Compare
  (Slice 1, risikoarm), (B) rollierende Vergleichsbasis mit Hybrid-
  Schreibtrigger, die #816 (Teil B) bewusst revidiert, unter Erhalt von
  #823 (Tagesgrenze), #818/#1667 (Radar-Unterdrückung) und der
  Trend-Erkennungs-Invariante (Slice 2, baut auf Slice 1 auf). Approval auf
  unchecked zurückgesetzt, ADR-Bedarf für die #816-Revision als offene Frage
  markiert.
