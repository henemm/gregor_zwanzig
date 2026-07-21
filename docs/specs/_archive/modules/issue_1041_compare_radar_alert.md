---
entity_id: compare_radar_alert
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [alerts, compare, radar, nowcast, epic-1095]
---

<!-- Issue #1041 — GESAMT-/REFERENZ-SPEC für den Backend-Radar-Alarm im Orts-Vergleich.
     Die Umsetzung ist geschnitten (PO-Entscheidung 2026-07-10, „erst der Mail-Baustein, dann der Alarm"):
       - Slice 1a (AKTIV): Mehrort-fähiger Onset-Alarm-Renderer + Bündel-Nachricht (E-Mail).
         → docs/specs/modules/issue_1041_multi_location_onset_alert.md
       - Slice 1b (FOLGE): CompareRadarAlertService + Konfig-Feld + Scheduler, nutzt den Baustein aus 1a.
       - Slice 2 (FOLGE): Frontend-Schalter im Compare-Editor.
     Dieses Dokument beschreibt das Gesamt-Backend-Design und dient 1b als Referenz. NICHT der aktive Freigabe-Gegenstand.

     VORBEDINGUNG FÜR 1b (Befund aus 1a, 2026-07-10): `radar_alert_mail_validator.py` (#830) kennt nur das
     alte Single-Location-Radar-Mail-Format (km-Range + Cooldown-Satz) und kann das neue Mehrort-Bündelformat
     strukturell NICHT bestehen (fehlendes Segment-Label P-1, fehlender Cooldown-Text P-4). Sobald 1b einen
     echten Aufrufer für `send_multi_location_radar_alert` verdrahtet, blockiert das Renderer-Commit-Gate (#811)
     den Commit, bis dieser Validator das Bündelformat versteht. Der Validator MUSS dafür in einem EIGENEN
     Validator-Änderungs-Workflow (Projektregel: Validator-Änderungen nie im Feature-Workflow) erweitert werden —
     vor oder als erster Schritt von 1b. In 1a wurde der Gate-Nachweis regelkonform über den byte-identischen
     Single-Location-Pfad erbracht (der neue Bündel-Pfad hat in 1a keinen Aufrufer). -->

# Issue #1041 — Radar-/Regen-Kurzfrist-Alarm für den Orts-Vergleich (Backend-Gesamtdesign / 1b-Referenz)

## Approval

- [ ] Approved

## Purpose

Ein neuer Radar-/Regen-Kurzfrist-**Alarm** für Orts-Vergleichs-Presets: „An einem
deiner Vergleichsorte fängt es gleich an zu regnen / Gewitter zieht auf." Er läuft
als eigener **Parallelpfad** neben den bestehenden Metrik-Abweichungs-Alarmen des
Orts-Vergleichs (`CompareAlertService`/`DeviationAlertEngine`, Epic #1095) — Vorbild
ist der Trip-Radar-Alarm `TripAlertService.check_radar_alerts()`
(`src/services/trip_alert.py:628`). Gehört bewusst in die **Alerts**, nicht in die
Vergleichs-Briefing-Mail (PO-Entscheidung, Scope-Pivot 2026-07-10,
`docs/context/1041-compare-nowcast.md`).

## Source

- **File:** `src/services/compare_radar_alert.py` (NEU, ~150–190 LoC) —
  `CompareRadarAlertService(user_id="default")`, öffentliche Einstiegsmethode
  `check_all_compare_presets() -> int` (Muster `CompareAlertService.check_all_compare_presets()`,
  `src/services/compare_alert.py:60-115`). Iteriert Presets + je Ort (Muster
  `_detect_triggered_locations`, `compare_alert.py:117-138`, mit bereits aufgelösten
  `loc.lat`/`loc.lon`). Für jedes Preset zuerst Guard
  `preset.get("radar_alert_enabled", False)` — bei `False`/fehlendem Feld **kein**
  `get_nowcast`-Call, kein Alarm (Default opt-in-aus). Je Ort:
  `RadarNowcastService().get_nowcast(loc.lat, loc.lon)` (`src/services/radar_service.py:118`)
  → `NowcastResult` (`radar_service.py:65-73`). Auslöse-Regel:
  `radar_alert_due(result, threshold_min=20)` (`src/services/trip_alert.py:33-36`) —
  1:1 wie beim Trip: Auslösung genau dann, wenn `onset_minutes <= 20`. Konvektive
  Gefahr (`is_convective=True`) ist in dieser Scheibe **keine eigene Auslöse-
  Bedingung** (der Trip-Pfad kennt sie nur als Ausnahme von der Briefing-
  Unterdrückung, die es in Compare Slice 1 nicht gibt), sondern steuert nur die
  **Kennzeichnung** im gerenderten Text (Gewitter/Hagel-Label statt Regen-Label).
  Quiet-Hours/Cooldown:
  `DeviationAlertEngine.is_quiet_hours()`/`is_cooldown_active()`
  (`src/services/deviation_alert_engine.py:72-97`) — statisch, location-generisch,
  1:1 wiederverwendet, keine Kopie. Throttle-Store
  `data/users/<user_id>/compare_radar_alert_throttle.json`, keyed `preset_id`
  (Muster `_load_throttle_times`/`_save_throttle_times`, `compare_alert.py:219-235`).
  Dedup zusätzlich über bestehenden `AlertStateService`
  (`src/services/alert_state.py:34-71`), `entity_id = f"{preset_id}:{location_id}"`
  (Muster `compare_alert.py:149-151`).
- **File:** `src/output/renderers/alert/model.py` (MODIFY, ~3–5 LoC) — additives,
  optionales Feld `OnsetEvent.location_label: str | None = None`
  (`model.py:30-40`), analog dem bereits existierenden `AlertEvent.location_label`
  (`model.py:12-27`, Issue #1170). Trip-Pfad setzt es nie → bit-identische
  Trip-Radar-Alert-Ausgabe (Regressions-Invariante).
- **File:** `src/output/renderers/alert/project.py` (MODIFY, ~35–45 LoC) — neue
  `to_multi_location_onset_alert_message(groups, *, tz, stand_at) -> AlertMessage`
  neben `to_multi_point_alert_message()` (`project.py:68-105`): `groups =
  list[(location_name, NowcastResult)]`, baut je Ort ein `OnsetEvent` mit
  `km_from=km_to=0.0` (kein Etappen-km, Muster `to_multi_point_alert_message:98`)
  und `location_label=location_name` (bei genau einer Gruppe `None`, analog Zeile
  99 der Vorlage), `AlertMessage.source` auf einen festen Marker (z. B.
  `"compare-radar"`) gesetzt, damit `render_*` weiterhin über den Onset-Zweig
  (`msg.source is not None`) routet.
- **File:** `src/output/renderers/alert/render.py` (MODIFY, ~70–100 LoC) — die vier
  Onset-Renderer (`_render_subject_onset:111-115`, `_render_email_onset:118-168`,
  `_render_telegram_onset:171-177`, `_render_sms_onset:180-186`) nehmen aktuell
  ausschließlich `e = msg.events[0]` an (Single-Event, kein Multi-Onset-Zweig
  existiert bislang — anders als beim Deviation-Pfad, der bereits `len(evs) == 1`
  vs. Mehrfach unterscheidet, `render_email:301-352`). Jede der vier Funktionen
  bekommt einen `len(msg.events) > 1`-Zweig, der je Event `e.location_label`
  voranstellt (Muster `loc_prefix`, `render_email:328-333`) und alle Orte
  auflistet, statt nur `events[0]` zu zeigen. **Dies ist die eigentliche
  Portierungsarbeit** — der bestehende Onset-Renderer ist bislang strikt
  Ein-Ort/Ein-Segment gebaut.
- **File:** `src/services/notification_service.py` (MODIFY, ~30–40 LoC) — neue
  Methode `send_multi_location_radar_alert(entities: list[tuple[str,
  "NowcastResult"]], effective_channels: set[str], mail_sink=None) ->
  NotificationResult`, baut über `to_multi_location_onset_alert_message()` EINE
  `AlertMessage` für alle gebündelt ausgelösten Orte EINES Preset-Laufs und
  delegiert an den unveränderten `_dispatch_alert_message()`-Kern
  (`notification_service.py:397-…`, Muster
  `send_multi_location_deviation_alert:369-400`, `mail_type="radar-alert"` wie
  beim Trip-Pfad, `radar_alert_service.py:100`).
- **File:** `api/routers/scheduler.py` (MODIFY, ~10 LoC) — neuer Endpoint
  `POST /api/scheduler/compare-radar-alert-checks` (Muster
  `trigger_compare_alert_checks`, `scheduler.py:60-67`, und
  `trigger_radar_alert_checks`, `scheduler.py:70-77`):
  `CompareRadarAlertService(user_id=user_id).check_all_compare_presets()`.
- **File:** `internal/model/compare_preset.go` (MODIFY, ~5 LoC) — neues Feld
  `RadarAlertEnabled *bool json:"radar_alert_enabled,omitempty"` auf
  `ComparePreset` (`compare_preset.go:38`, direkt neben `OfficialAlertsEnabled`,
  gleiches Pointer-Pattern: nil/fehlend = **Default false/aus**, im Unterschied
  zu `OfficialAlertsEnabled`, wo nil/fehlend = an bedeutet — hier ist opt-in
  bewusst umgekehrt wegen Netzwerkkosten pro Ort).
- **File:** `internal/handler/compare_preset.go` (MODIFY, ~5 LoC) — RMW-Nil-Merge
  im Update-Handler (Muster `OfficialAlertsEnabled`-Block, `compare_preset.go:214-219`):
  `if updated.RadarAlertEnabled == nil { updated.RadarAlertEnabled =
  original.RadarAlertEnabled }`.
- **File:** `internal/scheduler/scheduler.go` (MODIFY, ~15 LoC) — neuer
  `jobDef`-Eintrag `*/15 * * * *` → `compareRadarAlertChecks` (Muster
  `compareAlertChecks`, `scheduler.go:98,100,166-171`), ruft
  `runForAllUsers("compare_radar_alert_checks",
  "/api/scheduler/compare-radar-alert-checks")` über `s.recordRun(...)` — Letzteres
  liefert `last_run`-Tracking im Scheduler-Status-Endpoint automatisch mit (keine
  zusätzliche Observability-Arbeit nötig, Projektregel „last_run-Tracking" ist
  durch `recordRun()` bereits erfüllt).
- **File:** `tests/tdd/test_compare_radar_alert.py` (NEU) — Verhaltens-Tests,
  siehe Test Plan. Benannt nach Verhalten (Testnamensregel, CLAUDE.md), nicht
  nach Issue-Nummer.

> **Schicht-Hinweis:** 6 von 9 Dateien sind Python-Core (`src/services/`,
> `src/output/renderers/`, `api/routers/`); 3 Dateien sind Go
> (`internal/model/`, `internal/handler/`, `internal/scheduler/`). Kein
> Frontend-Code in dieser Scheibe — der An/Aus-Schalter im Editor ist Slice 2
> (#1041-Frontend, noch kein Issue) und liest hier NUR das Backend-Feld,
> Default aus.

## Estimated Scope

- **LoC:** Produktivcode ~320–420, Tests ~200–280 → Summe ~520–700. **Überschreitet
  das Standard-Limit von 250/Workflow deutlich** — vergleichbare Größenordnung wie
  #1169 (~330–400 Prod + ~150–250 Tests, dort PO-Override 700). Zwei Optionen für
  den PO bei der Freigabe:
  1. `workflow.py set-field loc_limit_override 700` (Präzedenz #1169), gesamte
     Scheibe in einem Workflow, ODER
  2. Vorziehen des Renderer-Teils (`model.py`+`project.py`+`render.py`, die vier
     Multi-Onset-Renderer-Zweige, ~110–150 LoC + eigene Tests) als eigenen
     Mini-Slice VOR `compare_radar_alert.py`/`notification_service.py`/
     Scheduler-Verdrahtung — das ist der Teil mit dem größten Regressions-
     risiko (geteilter Trip-Radar-Renderer) und ist unabhängig testbar
     (Snapshot: Trip-Radar-Alert-Ausgabe bit-identisch vor/nach).
- **Files:** 9 (2 NEU Python, 4 MODIFY Python, 3 MODIFY Go) + 1 neue Testdatei
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.radar_service.RadarNowcastService.get_nowcast` | intern | Zentrale, bereits koordinaten-generische Nowcast-Quelle — unverändert wiederverwendet |
| `services.trip_alert.radar_alert_due` | intern | Reine, koordinaten-agnostische Onset-Schwellenfunktion (≤20 Min) — 1:1 übernommen |
| `services.deviation_alert_engine.DeviationAlertEngine.is_quiet_hours`/`is_cooldown_active` | intern | Statische, location-generische Guards — 1:1 wiederverwendet, kein Neubau |
| `services.compare_alert.CompareAlertService` | intern | Struktur-Vorbild (Preset-Iteration, Throttle-Muster, `user_id`-Isolation) — kein Code-Sharing, aber 1:1 Musterübernahme |
| `services.alert_state.AlertStateService` | intern | Dedup-Store, bereits generisch (`entity_id`) |
| `services.notification_service.NotificationService._dispatch_alert_message` | intern | Geteilter Versand-Kern (ADR-0017/ADR-0021), unverändert |
| `output.renderers.alert.model.AlertMessage`/`OnsetEvent` | intern | Kanonisches Alert-Datenmodell (ADR-0011) — additiv erweitert |
| `services.radar_alert_service.build_onset_alert_message` | intern | Trip-Vorbild für die Onset-`AlertMessage`-Konstruktion — NICHT wiederverwendet (trip-verdrahtet), sondern Vorlage für den neuen Compare-Pfad in `project.py` |
| `app.loader.load_all_locations` | intern | Ortsauflösung je Nutzer, mandantengetrennt |
| `internal/model/compare_preset.go` (`OfficialAlertsEnabled`) | intern (Go) | Pointer-Pattern-Vorbild für `RadarAlertEnabled` |
| `internal/scheduler/scheduler.go` (`compareAlertChecks`) | intern (Go) | Cron-Job-Registrierungs-Vorbild inkl. `recordRun`-Observability |
| ADR-0011 (Single Backend Renderer) | Architektur | `render.py` bleibt der einzige Alert-Renderer für alle vier Kanäle — auch für den neuen Multi-Onset-Zweig |
| ADR-0017 (Output-Paket-Konsolidierung) | Architektur | `NotificationService` bleibt der einzige Versand-Orchestrierer |
| ADR-0021 (Shared Deviation Engine) | Architektur | Hat den Radar-Pfad explizit als „separat zu betrachten, falls Compare ihn benötigt" benannt — diese Scheibe ist dieser Vollzug für den Radar- (nicht Deviation-)Pfad |
| Slice 2 (#1041-Frontend, künftiges Issue) | Folge-Issue | Editierbarer An/Aus-Schalter im Compare-Editor — NICHT Teil dieser Scheibe |

## Implementation Details

### Architekturschnitt

```
CompareRadarAlertService.check_all_compare_presets()
  ├─ für jedes Preset (preset.get("radar_alert_enabled", False) == False → skip, kein Fetch)
  │    ├─ Cooldown-Check (Throttle-Store, keyed preset_id) → aktiv → skip
  │    ├─ für jeden Ort im Preset:
  │    │     ├─ NowcastResult = RadarNowcastService().get_nowcast(loc.lat, loc.lon)
  │    │     ├─ Quiet-Hours-Check (DeviationAlertEngine.is_quiet_hours) → aktiv → skip Ort
  │    │     └─ radar_alert_due(result, 20) → getriggert (is_convective steuert nur das Label)
  │    ├─ ≥1 getriggerter Ort → EINE Bündel-Mail:
  │    │     NotificationService.send_multi_location_radar_alert(entities, {"email"})
  │    │       → to_multi_location_onset_alert_message() → _dispatch_alert_message()
  │    └─ Throttle + AlertStateService-Dedup je getriggertem Ort schreiben (RMW)
```

### Auslöse-Regel (PO-bestätigt 2026-07-10)

Identisch zum Trip-Pfad („1:1 übernehmen", PO): Auslösung genau bei Regen-Onset
≤ 20 Minuten (`radar_alert_due`, `trip_alert.py:33-36`). Konvektive Gefahr
(Gewitter/Hagel, `NowcastResult.is_convective`) ist **keine eigene Auslöse-
Bedingung** in dieser Scheibe: Der Trip-Pfad nutzt `is_convective` nur als
Ausnahme von der Briefing-Unterdrückung (`trip_alert.py:716`), die in Compare
Slice 1 nicht existiert. `is_convective` steuert hier ausschließlich die
**Kennzeichnung** im Text (Gewitter/Hagel-Label statt Regen-Label, analog
`RadarNowcastService.intensity_to_text()`, `radar_service.py:95-112`). Ein
konvektives Ereignis mit Onset > 20 Min löst also — wie beim Trip — (noch) nicht
aus; sobald der Onset im 15-Min-Takt auf ≤ 20 Min fällt, feuert der Alarm.

### Bündelung mehrerer Orte (Portierungsarbeit)

Der bestehende Trip-Onset-Renderer (`render.py:111-186`) ist bislang strikt auf
GENAU EIN `OnsetEvent` gebaut (`e = msg.events[0]`, kein Multi-Zweig). Der
Deviation-Pfad hat diesen Multi-Zweig bereits (`render_email:301-352`,
`_sorted`, `over_thr`, `loc_prefix`). Diese Scheibe überträgt dasselbe Muster
auf den Onset-Zweig: `OnsetEvent` bekommt ein additives `location_label`-Feld
(analog `AlertEvent.location_label`, Issue #1170), und alle vier Renderer-
Funktionen (Subject/E-Mail/Telegram/SMS) bekommen einen `len(msg.events) > 1`-
Zweig, der je Ort eine Zeile mit `location_label` + Onset-Zeit + Intensität
zeigt. Bei GENAU EINEM getriggerten Ort bleibt der bestehende Single-Event-Pfad
unverändert aktiv (`location_label=None`) — **Trip-Radar-Alert-Ausgabe bleibt
bit-identisch**, das ist eine Hard-Gate-Regressions-Invariante (AC-9 unten).

### Konfig-Feld (Backend-Lesung, Default aus)

`preset.get("radar_alert_enabled", False)` — bewusst umgekehrter Default zu
`official_alerts_enabled` (dort: fehlend = an). Grund: Netzwerkkosten je Ort
(`get_nowcast` ruft die volle bbox-geroutete Provider-Kette,
`radar_service.py:201-234`, potenziell mehrfach je Compare-Preset mit ≥3 Orten).
Das Go-Feld `RadarAlertEnabled *bool` wird in dieser Scheibe bereits angelegt
(RMW-Merge im Handler, Datenverlust-Schutz), aber ohne Frontend-Schalter — der
Wert kann nur direkt in `compare_presets.json` gesetzt werden, bis Slice 2 den
Editor-Toggle liefert (dokumentiert unter Known Limitations).

### Reihenfolge (atomar testbar)

1. `model.py` (`OnsetEvent.location_label`) + Snapshot-Test bestehender
   Trip-Radar-Ausgabe (muss vor UND nach grün bleiben) →
2. `project.py` (`to_multi_location_onset_alert_message`) + `render.py`
   (Multi-Onset-Zweige) + Regressions-Test →
3. `notification_service.py` (`send_multi_location_radar_alert`) →
4. `compare_radar_alert.py` (Integration: Preset-Iteration, Cooldown,
   Quiet-Hours, Throttle, Zwei-Nutzer-Test) →
5. Go: `compare_preset.go` (Modell + Handler-RMW) →
6. Go: `scheduler.go` (Cron-Job + `recordRun`) + Python-Endpoint
   (`api/routers/scheduler.py`) → Staging-E2E.

## Expected Behavior

- **Input:** `compare_presets.json` je Nutzer (mit optionalem, standardmäßig
  fehlendem Feld `radar_alert_enabled`), frisches Nowcast je Ort über
  `RadarNowcastService.get_nowcast(lat, lon)`, HTTP-Trigger `POST
  /api/scheduler/compare-radar-alert-checks?user_id=...` (vom Go-Cron alle
  15 Min pro Nutzer aufgerufen).
- **Output:** Bei mindestens einem Ort mit Regen-Onset ≤20 Min oder konvektiver
  Gefahr (und außerhalb Cooldown/Quiet-Hours) EINE gebündelte Radar-Alarm-E-Mail
  an die Preset-Empfänger, die alle gleichzeitig getriggerten Orte mit Onset-Zeit
  und Intensität nennt. Ohne Auslösung/bei deaktiviertem Feld/innerhalb Cooldown:
  kein Versand, kein Fehler, kein `get_nowcast`-Call bei deaktiviertem Feld.
- **Side effects:** neue Datei `data/users/<user_id>/compare_radar_alert_throttle.json`
  (RMW, keyed `preset_id`), neue `AlertStateService`-Dedup-Einträge (keyed
  `preset_id:location_id`), kein neues Feld in `compare_presets.json` selbst
  erzwungen (additiv/optional).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit `radar_alert_enabled=true` und ein Ort
  darin, dessen Nowcast einen Regen-Onset in ≤20 Minuten anzeigt / When
  `CompareRadarAlertService.check_all_compare_presets()` bzw. der HTTP-Endpoint
  läuft / Then geht EINE E-Mail an die Preset-Empfänger raus, die genau diesen
  Ort samt Onset-Zeit („Regen ab ca. HH:MM") nennt.
  - Test: echtes Fixture-Preset + echter `frame_source`-DI-Seam
    (`RadarNowcastService(frame_source=...)`, `radar_service.py:84-88`) mit
    aufgezeichneten `RadarFrame`-Daten (kein Mock), echter Lauf, echte
    Mail-Zustellungsprüfung (mail_sink/IMAP je nach Testschicht).

- **AC-2:** Given ein Preset mit `radar_alert_enabled=true`, dessen Orte alle
  trocken sind oder deren Onset >20 Min liegt und nicht konvektiv ist / When
  der Check-Lauf läuft / Then wird kein Alarm ausgelöst und kein Versand
  vorgenommen.
  - Test: echter Lauf mit trockenem/spätem Fixture-Frame-Set, Assertion
    `count == 0` / kein Mail-Sink-Aufruf.

- **AC-3:** Given ein Ort mit konvektiver Gefahr (`is_convective=True`,
  Gewitter/Hagel) UND Regen-Onset ≤ 20 Min / When der Check läuft / Then löst der
  Alarm aus und die Nachricht kennzeichnet das Ereignis als konvektiv
  (Gewitter/Hagel-Label statt reinem Regen-Label).
  - Test: echter Lauf mit einem Frame-Fixture, dessen WMO-Code konvektiv ist
    (95/96/99, `radar_service.py:114-116`) und `onset_minutes <= 20`; Assertion
    auf Alarm-Auslösung UND Gewitter/Hagel-Label (nicht bloßes Regen-Label) im
    gerenderten Text.

- **AC-4:** Given zwei Orte EINES Presets, deren Nowcasts gleichzeitig auslösen
  (beide ≤20 Min Onset oder konvektiv) / When der Check-Lauf läuft / Then geht
  GENAU EINE gebündelte Mail raus, die BEIDE Orte mit ihrem jeweiligen
  `location_label` listet — kein Doppelversand, keine zwei separaten Mails.
  - Test: echter Lauf mit zwei Fixture-Orten, deren Frame-Sets beide auslösen;
    Assertion auf `count == 1` (bzw. genau ein Mail-Sink-Aufruf) UND dass der
    gerenderte Text beide Ortsnamen enthält.

- **AC-5:** Given ein Preset, für das gerade erst ein Radar-Alarm versendet
  wurde (Cooldown-Fenster aktiv) / When derselbe Ort im Cooldown-Fenster erneut
  auslösende Bedingungen zeigt und der Check-Lauf erneut läuft / Then wird
  KEIN zweiter Versand ausgelöst.
  - Test: zwei echte, zeitlich versetzte Läufe gegen denselben echten
    Throttle-Store innerhalb des Cooldown-Fensters; Assertion: genau ein
    Versand über den ersten Lauf, kein zweiter.

- **AC-6:** Given Ruhezeiten (`alert_quiet_from`/`alert_quiet_to`) sind aktiv
  UND ein Ort zeigt einen auslösenden Onset / When der Check-Lauf während der
  Ruhezeit läuft / Then wird der Onset zwar erkannt (kein stiller Fehler), der
  Alarm aber unterdrückt — kein Versand.
  - Test: echter Lauf mit gesetzter Systemzeit innerhalb des konfigurierten
    Ruhezeit-Fensters und auslösendem Fixture-Frame-Set; Assertion `count == 0`
    trotz erkanntem Onset (Log/Debug-Nachweis, keine Exception).

- **AC-7:** Given ein Preset OHNE `radar_alert_enabled` (fehlendes Feld,
  Default) oder mit `radar_alert_enabled=false` / When der Check-Lauf läuft /
  Then wird `RadarNowcastService.get_nowcast()` für KEINEN Ort dieses Presets
  aufgerufen und kein Alarm ausgelöst.
  - Test: echter Lauf mit Fixture-Preset ohne das Feld; Assertion über einen
    zählenden Test-Doppelgänger des `frame_source`-DI-Seams (kein echter
    Netzwerk-Call, kein Mock-Theater — Zähler zählt reale Aufrufe des
    injizierten, echten Frame-Providers), dass der Zähler bei 0 bleibt.

- **AC-8 (Mandantenfähigkeit):** Given zwei verschiedene Nutzer mit je einem
  eigenen Compare-Preset, eigenen Orten und eigenen Empfängern / When der
  Check-Lauf für beide Nutzer läuft / Then nutzt der Alarm für Nutzer A
  ausschließlich A's Orte und A's konfigurierte Empfänger, Throttle-/
  Alert-State-Dateien liegen ausschließlich unter `data/users/A/...` bzw.
  `data/users/B/...`, und es gibt zu keinem Zeitpunkt einen `"default"`-
  Fallback im Code-Pfad.
  - Test: zwei echte `data/users/<uid>/`-Verzeichnisse mit je eigenem
    Preset/Empfänger; Assertion auf Datei-Pfad-Isolation UND
    Empfänger-Isolation (A's Mail enthält nie B's Adresse und umgekehrt).

- **AC-9 (Regressions-Invariante):** Given der bestehende, produktive
  Trip-Radar-Alarm-Renderpfad (`render.py:111-186`, EIN `OnsetEvent`,
  `location_label=None`) / When er nach Einführung des additiven
  `OnsetEvent.location_label`-Felds und der neuen Multi-Onset-Renderer-Zweige
  erneut mit denselben Eingaben läuft / Then ist die gerenderte Ausgabe
  (Subject/E-Mail/Telegram/SMS) byte-identisch zum Stand vor dieser Scheibe.
  - Test: Vorher/Nachher-Snapshot-Vergleich eines bestehenden
    Trip-Radar-Alert-Fixtures (identischer Text vor/nach dieser Scheibe, kein
    manuelles Abgleichen).

## Known Limitations

- **Kein Frontend-Schalter in dieser Scheibe.** `radar_alert_enabled` kann in
  Slice 1 nur direkt in `compare_presets.json` gesetzt werden. Der editierbare
  An/Aus-Schalter im Compare-Editor ist Slice 2 (eigenes, künftiges Issue) und
  NICHT Teil dieser Spec.
- Alarmierung nur über den E-Mail-Kanal — analog zu #1169/#1170, da
  Compare-Presets heute keine Telegram-/SMS-Empfänger-Zuordnung besitzen.
- Netzwerkkosten je Ort bleiben real: bei aktiviertem Radar-Alarm ruft jeder
  15-Minuten-Check `get_nowcast()` für JEDEN Ort des Presets auf. Kein
  zusätzliches Anti-Sturm-Caching in dieser Scheibe (Default-aus mindert das
  Risiko strukturell; ein TTL-Cache wäre eine separate Optimierung, falls
  Provider-Quoten das erfordern).
- Die Quellen-Entscheidung (radar_service-Wiederverwendung vs. neuer
  MF-AROME-PI-Radar-Client) bleibt bei „Wiederverwendung" — kein neuer
  Météo-France-Direktzugriff in dieser Scheibe (siehe Analyse,
  `docs/context/1041-compare-nowcast.md`, Risiko 1).
- Kein neues `ComparePreset`-Konfig-Sub-Schema für Radar-Schwellen — die
  20-Minuten-Schwelle ist wie beim Trip-Pfad hartkodiert, keine
  UI-editierbare Sensitivität in dieser Scheibe.
- Konvektive Ereignisse mit Onset > 20 Min lösen — bewusst wie beim Trip — noch
  nicht aus (nur Onset ≤ 20 Min triggert). Der 15-Minuten-Check holt das nach,
  sobald der Onset in den Schwellenbereich fällt. Kein „Frühwarn"-Sonderpfad für
  konvektive Ereignisse in dieser Scheibe.

## Risiken

1. **LoC-Limit deutlich überschritten** (Schätzung ~320–420 Prod + ~200–280
   Test-LoC, siehe Estimated Scope) — PO muss vor Implementierungsbeginn
   entweder `loc_limit_override` setzen (Präzedenz #1169, 700) oder den
   Renderer-Teil als Mini-Slice vorziehen lassen.
2. **Regressionsrisiko am geteilten Alert-Renderer:** `render.py`/`model.py`
   werden auch vom produktiven Trip-Radar-Alert-Pfad genutzt — additives,
   optionales `location_label`-Feld hält das Risiko strukturell klein, ein
   Snapshot-Test auf unveränderte Trip-Ausgabe ist trotzdem Hard-Gate (AC-9).
3. **Renderer-Commit-Gate (#811):** Änderungen an
   `src/output/renderers/alert/*.py` triggern das Radar-/Alert-Mailgate
   (`renderer_mail_gate.py`) — vor Commit müssen sowohl ein Verhaltens-Test
   grün sein als auch (bei betroffenen Trip-Briefing-Pfaden)
   `briefing_mail_validator.py` erfolgreich laufen.
4. **Keine Mocks erlaubt** (CLAUDE.md) — Nowcast-Auslösung muss über den
   echten `frame_source`-DI-Seam (`RadarNowcastService(frame_source=...)`,
   `radar_service.py:84-88`) mit echten, aufgezeichneten `RadarFrame`-Daten
   getestet werden, kein Mock-Theater der Provider-Kette.
5. **Netzwerkkosten pro Ort:** Compare-Presets haben typischerweise ≥3 Orte;
   bei aktiviertem Radar-Alarm entsteht pro 15-Min-Zyklus ein
   `get_nowcast()`-Call je Ort. Default-aus (opt-in) mindert das Risiko in
   dieser Scheibe strukturell.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Referenz, bereits akzeptiert) + ADR-0017 (Referenz,
  bereits akzeptiert) + ADR-0021 (Referenz, bereits akzeptiert) — **keine neue
  ADR nötig**.
- **Rationale:** Diese Scheibe führt keinen neuen Architektur-Baustein ein,
  sondern überträgt ein bereits etabliertes Muster (Trip: Deviation-Alarm UND
  eigener Radar-Alarm-Parallelpfad, letzterer NICHT in der gemeinsamen Engine)
  auf den Compare-Kontext. ADR-0021 hat den Radar-Onset-Pfad explizit als
  „vorerst Trip-spezifisch ... eine Verallgemeinerung dieser Bausteine ist
  separat zu betrachten, falls Compare sie ebenfalls benötigt" benannt — diese
  Scheibe ist genau dieser separat betrachtete Vollzug, keine neue
  Architektur-Entscheidung. ADR-0011 (ein gemeinsamer Backend-Renderer für
  alle vier Kanäle) und ADR-0017 (`NotificationService` als einziger
  Versand-Orchestrierer) bleiben unverändert gültig und werden additiv
  erweitert, nicht gebrochen.

## Test Plan

Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md) — echte
Preset-/Throttle-/State-Pfade und echte, aufgezeichnete `RadarFrame`-Fixtures
über den `frame_source`-DI-Seam (kein Mock der Provider-Kette). Vorbild:
`tests/tdd/test_issue_1169_compare_alert_consumer.py` (echte Preset-/
Snapshot-/State-Pfade, echte Zwei-Nutzer-Isolation).

Neue Testdatei: `tests/tdd/test_compare_radar_alert.py`

- `test_bundled_radar_alert_sent_when_onset_within_threshold` (AC-1) — echtes
  Fixture-Preset + `frame_source`-DI mit aufgezeichnetem nassen Frame-Set,
  echter `CompareRadarAlertService`-Lauf, Assertion: eine Mail mit
  Onset-Zeitangabe für den betroffenen Ort.
- `test_no_alert_when_all_locations_dry_or_late_onset` (AC-2) — trockenes/
  spätes Frame-Set, `count == 0`.
- `test_convective_event_always_triggers_and_labeled` (AC-3) — konvektives
  Frame-Fixture (WMO 95/96/99) mit `onset_minutes > 20`, Assertion auf
  Auslösung UND Gewitter/Hagel-Label im gerenderten Text.
- `test_two_simultaneous_locations_bundled_into_one_mail` (AC-4) — zwei
  auslösende Fixture-Orte, Assertion `count == 1`, beide Ortsnamen im
  gerenderten Text.
- `test_cooldown_suppresses_repeat_alert_within_window` (AC-5) — zwei
  zeitlich versetzte echte Läufe gegen echten Throttle-Store, genau ein
  Versand.
- `test_quiet_hours_suppress_alert_despite_detected_onset` (AC-6) —
  Systemzeit innerhalb Ruhezeit-Fenster, `count == 0` trotz erkanntem Onset.
- `test_disabled_or_missing_flag_skips_nowcast_fetch_entirely` (AC-7) —
  zählender echter `frame_source`-Doppelgänger, Assertion `call_count == 0`
  bei fehlendem/`false` Feld.
- `test_two_users_isolated_locations_and_recipients` (AC-8) — zwei echte
  `data/users/<uid>/`-Verzeichnisse mit je eigenem Preset/Empfänger,
  Datei-Pfad- UND Empfänger-Isolation, kein `"default"`-Fallback im Code-Pfad.
- `test_trip_radar_alert_rendering_unchanged_after_multi_onset_extension`
  (AC-9) — Vorher/Nachher-Snapshot-Vergleich eines bestehenden
  Trip-Radar-Alert-Fixtures.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1041, Slice 1 von 2 (Backend, E2E)
