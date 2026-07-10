---
entity_id: issue_1041b_compare_radar_alert_service
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [alerts, compare, radar, nowcast, epic-1095, issue-1041, slice-1b]
---

<!-- Issue #1041 — Slice 1b von 3. Nutzt den in Slice 1a (bereits LIVE) gebauten
     Baustein `NotificationService.send_multi_location_radar_alert()` /
     `to_multi_location_onset_alert_message()`
     (docs/specs/modules/issue_1041_multi_location_onset_alert.md) und verdrahtet ihn
     zu einem echten Compare-Radar-Alarm-Pfad: neuer CompareRadarAlertService,
     Preset-Konfig-Feld, Scheduler-Endpoint, Go-Cron. Gesamtdesign (Referenz):
     docs/specs/modules/issue_1041_compare_radar_alert.md. Slice 2 (Frontend-Schalter)
     folgt als eigenes Issue, NICHT Teil dieser Spec. -->

# Issue #1041 — Compare-Radar-Alarm-Service & Scheduler-Verdrahtung (Slice 1b/3)

## Approval

- [x] Approved — PO „go" 2026-07-10 (LoC-Override 400 freigegeben)

## Purpose

Ein neuer `CompareRadarAlertService`, der pro Orts-Vergleichs-Preset und pro
Ort den Radar-Nowcast prüft und bei Regen-Onset ≤ 20 Minuten (bzw. konvektiver
Gefahr bei ≤ 20 Minuten) automatisch alle 15 Minuten einen gebündelten
E-Mail-Alarm an die Preset-Empfänger versendet. Läuft als eigener
**Parallelpfad** neben den bestehenden Metrik-Abweichungs-Alarmen
(`CompareAlertService`/`DeviationAlertEngine`, Epic #1095) — Vorbild ist der
Trip-Radar-Alarm `TripAlertService.check_radar_alerts()`
(`src/services/trip_alert.py:628`). Nutzt den in Slice 1a bereits gelieferten
Versand-Baustein (`send_multi_location_radar_alert`), baut ihn aber **nicht
neu**. Gehört bewusst in die Compare-**Alerts**, nicht in die
Vergleichs-Briefing-Mail (PO-Scope-Pivot 2026-07-10,
`docs/context/1041-compare-nowcast.md`).

## Source

- **File:** `src/services/compare_radar_alert.py` (NEU, ~130–160 LoC) —
  `CompareRadarAlertService(user_id="default")`, öffentliche Einstiegsmethode
  `check_all_compare_presets() -> int`. Struktur-Vorbild
  `CompareAlertService.check_all_compare_presets()`
  (`src/services/compare_alert.py:60-115`) und `_detect_triggered_locations`
  (`compare_alert.py:117-138`, dort bereits `loc.lat`/`loc.lon` aufgelöst).
  Ablauf je Preset:
  1. Guard `preset.get("radar_alert_enabled", False)` — bei `False`/fehlendem
     Feld **kein** `get_nowcast`-Aufruf, kein Alarm (Default opt-in-aus,
     Netzwerkkosten je Ort).
  2. Cooldown-Check über `DeviationAlertEngine.is_cooldown_active()`
     (`src/services/deviation_alert_engine.py:85-97`) gegen einen eigenen
     Throttle-Store `data/users/<user_id>/compare_radar_alert_throttle.json`,
     keyed `preset_id` (Muster `_load_throttle_times`/`_save_throttle_times`,
     `compare_alert.py:219-235`).
  3. Je Ort im Preset: `RadarNowcastService().get_nowcast(loc.lat, loc.lon)`
     (`src/services/radar_service.py:118-132`) → `NowcastResult`
     (`radar_service.py:65-73`). Quiet-Hours-Check via
     `DeviationAlertEngine.is_quiet_hours()` (`deviation_alert_engine.py:71-83`).
     Auslösung: `radar_alert_due(result, threshold_min=20)`
     (`src/services/trip_alert.py:33-36`) — `is_convective` steuert
     ausschließlich das Text-Label (Gewitter/Hagel), keine eigene
     Auslöse-Bedingung in dieser Scheibe.
  4. Alle getriggerten Orte eines Preset-Laufs → EIN Versand über
     `NotificationService().send_multi_location_radar_alert(entities=[(name,
     NowcastResult), ...], effective_channels={"email"}, mail_sink=...)` —
     der bereits live gelieferte Slice-1a-Baustein
     (`docs/specs/modules/issue_1041_multi_location_onset_alert.md`). Bei
     GENAU EINEM getriggerten Ort fällt der Baustein automatisch auf das
     Einzel-Onset-Format zurück (1a AC-5).
  5. Dedup je getriggertem Ort über `AlertStateService`
     (`src/services/alert_state.py:34-71`), `entity_id =
     f"{preset_id}:{location_id}"` (Muster `compare_alert.py:149-151`).
     Throttle nach erfolgreichem Versand schreiben (Read-Modify-Write, kein
     Replace — Projektregel Daten-Schema-Reworks).
  6. Ortsauflösung mandantengetrennt über `load_all_locations(user_id=...)`
     (Muster `compare_alert.py:75`), Empfänger aus `preset.get("empfaenger")`
     (Muster `_notification_service_for`, `compare_alert.py:197-206`) — echte
     `user_id` durchgereicht, **niemals** `"default"`-Fallback.

- **File:** `api/routers/scheduler.py` (MODIFY, ~8–10 LoC) — neuer Endpoint
  `POST /api/scheduler/compare-radar-alert-checks` (Muster
  `trigger_compare_alert_checks`, `scheduler.py:60-67`, und
  `trigger_radar_alert_checks`, `scheduler.py:70-77`):
  `CompareRadarAlertService(user_id=user_id).check_all_compare_presets()`,
  Response `{"status": "ok", "count": count}`.

- **File:** `internal/model/compare_preset.go` (MODIFY, ~5 LoC) — neues Feld
  `RadarAlertEnabled *bool json:"radar_alert_enabled,omitempty"` auf
  `ComparePreset`, eingefügt direkt neben `OfficialAlertsEnabled`
  (`compare_preset.go:34-38`). Gleiches Pointer-Pattern (nil bei fehlendem
  JSON-Feld statt Zero-Value), aber **umgekehrter Default** zu
  `OfficialAlertsEnabled`: nil/fehlend = **aus** (Netzwerkkosten je Ort,
  bewusst konservativ — Kommentar im Code muss diese Umkehr explizit
  benennen, sonst Verwechslungsgefahr mit dem `official_alerts_enabled`-
  Default).

- **File:** `internal/handler/compare_preset.go` (MODIFY, ~4–5 LoC) —
  RMW-Nil-Merge im Update-Handler, exaktes Muster des bestehenden
  `OfficialAlertsEnabled`-Blocks (`compare_preset.go:217-219`):
  ```go
  if updated.RadarAlertEnabled == nil {
      updated.RadarAlertEnabled = original.RadarAlertEnabled
  }
  ```
  Ohne diesen Block geht der Feldwert bei jedem Preset-Save verloren, der das
  Feld nicht mitschickt (Datenverlust-Regel, CLAUDE.md).

- **File:** `internal/scheduler/scheduler.go` (MODIFY, ~15 LoC) — neuer
  `jobDef`-Eintrag `{"*/15 * * * *", s.compareRadarAlertChecks,
  "compare_radar_alert_checks", "Compare Radar Alert Checks (every 15 min)"}`
  in der `jobs`-Liste (Muster-Zeile `scheduler.go:100`, direkt neben
  `compareAlertChecks`), plus neue Methode
  ```go
  func (s *Scheduler) compareRadarAlertChecks() {
      s.recordRun("compare_radar_alert_checks", func() error {
          return s.runForAllUsers("compare_radar_alert_checks",
              "/api/scheduler/compare-radar-alert-checks")
      })
  }
  ```
  (byte-genaues Muster von `compareAlertChecks`, `scheduler.go:166-171`).
  `recordRun()` liefert `last_run`-Tracking im
  `/api/scheduler/status`-Endpoint automatisch mit — erfüllt die
  Projektregel „last_run-Tracking bei neuen Schedulern" ohne
  Zusatzaufwand.

- **File:** `tests/tdd/test_compare_radar_alert.py` (NEU, ~160–200 LoC) —
  Verhaltens-Tests, siehe Test Plan. Benannt nach Verhalten
  (Testnamensregel, CLAUDE.md), nicht nach Issue-Nummer.

> **Schicht-Hinweis:** 2 Dateien Python-Core (`src/services/`,
> `api/routers/`), 3 Dateien Go (`internal/model/`, `internal/handler/`,
> `internal/scheduler/`). Kein Frontend-Code in dieser Scheibe — der
> An/Aus-Schalter im Compare-Editor ist Slice 2 (eigenes, künftiges Issue)
> und liest hier NUR das Backend-Feld, Default aus. Keine Änderung an
> `src/output/renderers/alert/*.py` oder `notification_service.py` — der
> Versand-Baustein ist bereits in Slice 1a fertig geliefert und LIVE.

## Estimated Scope

- **LoC:** Produktivcode ~162–195 (Service ~130–160, Endpoint ~8–10, Go
  ~27–30 über 3 Dateien), Tests ~160–200 → Summe **~320–395**. Das
  **überschreitet das Standard-Limit von 250/Workflow**. Zwei Optionen für
  den PO bei der Freigabe (siehe „Risiken" unten für Details):
  1. `workflow.py set-field loc_limit_override 400` (Präzedenz #1169: 700 für
     eine deutlich größere Scheibe), gesamte Scheibe in einem Workflow, ODER
  2. Mikro-Slice: Go-Konfig+Cron (`compare_preset.go`, `compare_preset.go`
     Handler, `scheduler.go`, ~27–30 LoC + ein schlanker
     RMW-Roundtrip-Test) als eigener Vor-Schritt, danach
     `compare_radar_alert.py` + Python-Endpoint + Python-Tests als
     Hauptschritt (~290–365 LoC, liegt dann selbst noch über 250 — der
     Python-Kern ist der eigentliche Umfangstreiber, nicht Go). Option 2
     reduziert die Überschreitung also nur geringfügig; Option 1 ist die
     realistischere Empfehlung.
- **Files:** 2 NEU/MODIFY Python (`compare_radar_alert.py` neu,
  `api/routers/scheduler.py` modify), 3 MODIFY Go, 1 neue Testdatei.
- **Effort:** medium-high.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.notification_service.NotificationService.send_multi_location_radar_alert` | intern (Slice 1a, LIVE) | Fertiger Bündel-Versand-Baustein — wird genutzt, nicht neu gebaut |
| `output.renderers.alert.project.to_multi_location_onset_alert_message` | intern (Slice 1a, LIVE) | Fertige Onset-Nachrichtenkonstruktion — Aufrufer entsteht erst hier |
| `services.radar_service.RadarNowcastService.get_nowcast` | intern | Zentrale, koordinaten-generische Nowcast-Quelle — unverändert wiederverwendet |
| `services.trip_alert.radar_alert_due` | intern | Reine, koordinaten-agnostische Onset-Schwellenfunktion (≤20 Min) — 1:1 übernommen |
| `services.deviation_alert_engine.DeviationAlertEngine.is_quiet_hours`/`is_cooldown_active` | intern | Statische, location-generische Guards — 1:1 wiederverwendet |
| `services.compare_alert.CompareAlertService` | intern | Struktur-Vorbild (Preset-Iteration, Throttle-Muster, `user_id`-Isolation) — kein Code-Sharing, Musterübernahme |
| `services.alert_state.AlertStateService` | intern | Dedup-Store, bereits generisch (`entity_id`) |
| `app.loader.load_all_locations` | intern | Ortsauflösung je Nutzer, mandantengetrennt |
| `internal/model/compare_preset.go` (`OfficialAlertsEnabled`) | intern (Go) | Pointer-Pattern-Vorbild für `RadarAlertEnabled` (Default-Richtung umgekehrt) |
| `internal/scheduler/scheduler.go` (`compareAlertChecks`) | intern (Go) | Cron-Job-Registrierungs-Vorbild inkl. `recordRun`-Observability |
| `api/routers/scheduler.py` (`trigger_radar_alert_checks`, `trigger_compare_alert_checks`) | intern | Endpoint-Muster |
| ADR-0021 (Shared Deviation Engine) | Architektur | Hat den Radar-Pfad explizit als „separat zu betrachten, falls Compare ihn benötigt" benannt — diese Scheibe vollzieht das für den Radar-Alarm-Aufrufer |

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
  │    │     NotificationService.send_multi_location_radar_alert(entities, {"email"})  [Slice 1a, LIVE]
  │    └─ Throttle + AlertStateService-Dedup je getriggertem Ort schreiben (RMW)
```

### Auslöse-Regel (PO-bestätigt, 1:1 vom Trip-Pfad übernommen)

Auslösung genau dann, wenn `onset_minutes <= 20` (`radar_alert_due`,
`trip_alert.py:33-36`). Konvektive Gefahr (`is_convective=True`) ist **keine
eigene Auslöse-Bedingung** — sie steuert nur die Kennzeichnung im Text
(Gewitter/Hagel-Label statt Regen-Label). Ein konvektives Ereignis mit
Onset > 20 Min löst also (noch) nicht aus; sobald der Onset im 15-Min-Takt
auf ≤ 20 Min fällt, feuert der Alarm — dann mit korrektem Label.

### Konfig-Feld (Backend-Lesung, Default aus)

`preset.get("radar_alert_enabled", False)` — bewusst umgekehrter Default zu
`official_alerts_enabled` (dort: fehlend = an). Grund: Netzwerkkosten je Ort
(`get_nowcast` ruft die volle bbox-geroutete Provider-Kette,
`radar_service.py:201-234`, potenziell mehrfach je Compare-Preset mit ≥3
Orten). Der Wert kann in dieser Scheibe nur direkt in
`compare_presets.json` gesetzt werden — Slice 2 liefert den Editor-Toggle
(Known Limitation).

### Reihenfolge (atomar testbar)

1. `internal/model/compare_preset.go` (Feld) + `internal/handler/compare_preset.go`
   (RMW-Merge) + Go-Roundtrip-Test →
2. `src/services/compare_radar_alert.py` (Service, gegen echte Fixture-Presets
   und den `frame_source`-DI-Seam getestet) →
3. `api/routers/scheduler.py` (Endpoint) →
4. `internal/scheduler/scheduler.go` (Cron-Job + `recordRun`) →
5. Staging-E2E (manuelles Setzen von `radar_alert_enabled=true` in einem
   Test-Preset, Beobachtung über `/api/scheduler/status` + echte Test-Mail).

## Expected Behavior

- **Input:** `compare_presets.json` je Nutzer (mit optionalem, standardmäßig
  fehlendem Feld `radar_alert_enabled`), frisches Nowcast je Ort über
  `RadarNowcastService.get_nowcast(lat, lon)`, HTTP-Trigger `POST
  /api/scheduler/compare-radar-alert-checks?user_id=...` (vom Go-Cron alle
  15 Min pro Nutzer aufgerufen).
- **Output:** Bei mindestens einem Ort mit Regen-Onset ≤ 20 Min (und außerhalb
  Cooldown/Quiet-Hours) EINE gebündelte Radar-Alarm-E-Mail an die
  Preset-Empfänger, die alle gleichzeitig getriggerten Orte mit Onset-Zeit
  und Intensität nennt. Bei genau einem getriggerten Ort das Einzel-Onset-
  Format (Slice-1a-Rückfall). Ohne Auslösung/bei deaktiviertem Feld/innerhalb
  Cooldown/Quiet-Hours: kein Versand, kein Fehler; bei deaktiviertem Feld
  zusätzlich kein `get_nowcast`-Call.
- **Side effects:** neue Datei
  `data/users/<user_id>/compare_radar_alert_throttle.json` (RMW, keyed
  `preset_id`), neue `AlertStateService`-Dedup-Einträge (keyed
  `preset_id:location_id`), kein Pflichtfeld in `compare_presets.json`
  selbst (additiv/optional).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit `radar_alert_enabled=true` und genau
  einem Ort darin, dessen Nowcast einen Regen-Onset in ≤ 20 Minuten anzeigt /
  When `CompareRadarAlertService.check_all_compare_presets()` (bzw. der HTTP-
  Endpoint) läuft / Then geht EINE E-Mail (Einzel-Onset-Format) an die
  Preset-Empfänger raus, die genau diesen Ort samt Onset-Zeit nennt.
  - Test: echtes Fixture-Preset + echter `frame_source`-DI-Seam
    (`RadarNowcastService(frame_source=...)`, `radar_service.py:84-89`) mit
    aufgezeichneten `RadarFrame`-Daten (kein Mock), echter Lauf, Assertion
    über `mail_sink`: genau eine Mail mit Ortsname + Onset-Zeitangabe.

- **AC-2:** Given ein Preset mit `radar_alert_enabled=true`, dessen Orte alle
  trocken sind oder deren Onset > 20 Min liegt / When der Check-Lauf läuft /
  Then wird kein Alarm ausgelöst und kein Versand vorgenommen.
  - Test: echter Lauf mit trockenem/spätem Fixture-Frame-Set, Assertion
    `count == 0` und kein Aufruf des `mail_sink`.

- **AC-3:** Given zwei Orte EINES Presets, deren Nowcasts gleichzeitig
  auslösen (beide Onset ≤ 20 Min) / When der Check-Lauf läuft / Then geht
  GENAU EINE gebündelte Mail raus, die BEIDE Orte mit ihrem jeweiligen Namen
  und ihrer Onset-Zeit listet — kein Doppelversand.
  - Test: echter Lauf mit zwei Fixture-Orten, deren Frame-Sets beide
    auslösen; Assertion auf genau einen `mail_sink`-Aufruf UND dass der
    gerenderte Text beide Ortsnamen enthält (nutzt den in Slice 1a
    getesteten Bündel-Pfad als Consumer).

- **AC-4:** Given ein Preset, für das gerade erst ein Radar-Alarm versendet
  wurde (Cooldown-Fenster aktiv) / When derselbe Ort innerhalb des
  Cooldown-Fensters erneut auslösende Bedingungen zeigt und der Check-Lauf
  erneut läuft / Then wird KEIN zweiter Versand ausgelöst.
  - Test: zwei echte, zeitlich versetzte Läufe gegen denselben echten
    Throttle-Store innerhalb des Cooldown-Fensters; Assertion: genau ein
    Versand über den ersten Lauf, kein zweiter beim wiederholten Lauf.

- **AC-5:** Given Ruhezeiten (`alert_quiet_from`/`alert_quiet_to`) sind aktiv
  UND ein Ort zeigt einen auslösenden Onset / When der Check-Lauf während der
  Ruhezeit läuft / Then wird der Onset erkannt, der Alarm aber unterdrückt —
  kein Versand.
  - Test: echter Lauf mit gesetzter Systemzeit innerhalb des konfigurierten
    Ruhezeit-Fensters und auslösendem Fixture-Frame-Set; Assertion
    `count == 0` trotz erkanntem Onset, kein stiller Fehler/Exception.

- **AC-6:** Given ein Preset OHNE `radar_alert_enabled` (fehlendes Feld,
  Default) oder mit `radar_alert_enabled=false` / When der Check-Lauf läuft /
  Then wird `RadarNowcastService.get_nowcast()` für KEINEN Ort dieses
  Presets aufgerufen und kein Alarm ausgelöst.
  - Test: echter Lauf mit Fixture-Preset ohne das Feld; Assertion über einen
    zählenden, echten `frame_source`-Doppelgänger (kein Netzwerk-Call, kein
    Mock-Theater — der Zähler zählt reale Aufrufe des injizierten, echten
    Frame-Providers), dass der Zähler bei 0 bleibt.

- **AC-7 (Mandantenfähigkeit):** Given zwei verschiedene Nutzer mit je einem
  eigenen Compare-Preset, eigenen Orten und eigenen Empfängern / When der
  Check-Lauf für beide Nutzer läuft / Then nutzt der Alarm für Nutzer A
  ausschließlich A's Orte und A's konfigurierte Empfänger, Throttle-/
  Alert-State-Dateien liegen ausschließlich unter `data/users/A/...` bzw.
  `data/users/B/...`, und es gibt zu keinem Zeitpunkt einen
  `"default"`-Fallback im Code-Pfad.
  - Test: zwei echte `data/users/<uid>/`-Verzeichnisse mit je eigenem
    Preset/Empfänger; Assertion auf Datei-Pfad-Isolation UND
    Empfänger-Isolation (A's Mail enthält nie B's Adresse und umgekehrt).

- **AC-8 (Konvektiv-Kennzeichnung):** Given ein Ort mit konvektiver Gefahr
  (`is_convective=True`, Gewitter/Hagel) UND Regen-Onset ≤ 20 Min / When der
  Check-Lauf läuft / Then löst der Alarm aus und die versendete Nachricht
  kennzeichnet das Ereignis als konvektiv (Gewitter/Hagel-Label statt
  reinem Regen-Label).
  - Test: echter Lauf mit einem Frame-Fixture, dessen WMO-Code konvektiv ist
    (95/96/99, `radar_service.py:114-116`) und `onset_minutes <= 20`;
    Assertion auf Alarm-Auslösung UND Gewitter/Hagel-Label im gerenderten
    Text (nicht bloßes Regen-Label).

## Known Limitations

- **Kein Frontend-Schalter in dieser Scheibe.** `radar_alert_enabled` kann
  nur direkt in `compare_presets.json` gesetzt werden. Der editierbare
  An/Aus-Schalter im Compare-Editor ist Slice 2 (eigenes, künftiges Issue)
  und NICHT Teil dieser Spec.
- **Mehrort-Bündelformat ist noch nicht formal validator-abgesichert.**
  `radar_alert_mail_validator.py` (#830) kennt nur das alte
  Single-Location-Radar-Mail-Format (km-Range + Cooldown-Satz) und kann das
  neue Mehrort-Bündelformat strukturell noch nicht bestehen (Befund aus
  Slice 1a: fehlendes Segment-Label, fehlender Cooldown-Text). Die
  E2E-Staging-Acceptance dieser Scheibe nutzt daher den **Einzel-Ort-Fall**
  (AC-1, formal validierbar über den unveränderten Single-Onset-Pfad) für
  „E2E bestanden"; der Mehrort-Bündelfall (AC-3, AC-8-Kombination mit
  mehreren Orten) ist über Unit-/Verhaltenstest + Adversary-Review
  abgesichert, aber NICHT über den produktiven Mail-Validator. Die
  Validator-Erweiterung fürs Bündelformat ist ein eigener Folge-Workflow
  (Projektregel: Validator-Änderungen laufen nie im Feature-Workflow,
  `feedback_validator_changes_own_workflow.md`).
- **Netzwerkkosten je Ort bleiben real:** bei aktiviertem Radar-Alarm ruft
  jeder 15-Minuten-Check `get_nowcast()` für JEDEN Ort des Presets auf. Kein
  zusätzliches Anti-Sturm-Caching in dieser Scheibe (Default-aus mindert das
  Risiko strukturell; ein TTL-Cache wäre eine separate Optimierung, falls
  Provider-Quoten das erfordern).
- Alarmierung nur über den E-Mail-Kanal — analog zu #1169/#1170 und zum
  Slice-1a-Baustein selbst, da Compare-Presets heute keine Telegram-/
  SMS-Empfänger-Zuordnung besitzen.
- Kein neues `ComparePreset`-Konfig-Sub-Schema für Radar-Schwellen — die
  20-Minuten-Schwelle ist wie beim Trip-Pfad hartkodiert, keine
  UI-editierbare Sensitivität in dieser Scheibe.
- Konvektive Ereignisse mit Onset > 20 Min lösen — bewusst wie beim Trip —
  noch nicht aus. Der 15-Minuten-Check holt das nach, sobald der Onset in
  den Schwellenbereich fällt. Kein „Frühwarn"-Sonderpfad in dieser Scheibe.

## Risiken

1. **LoC-Limit überschritten** (Schätzung ~320–395 gesamt, siehe Estimated
   Scope). PO muss vor Implementierungsbeginn entweder
   `loc_limit_override` setzen (empfohlen: 400, Präzedenz #1169: 700 für
   eine deutlich größere Scheibe) oder den kleinen Mikro-Slice-Schnitt
   (Go-Konfig+Cron vorziehen) akzeptieren — Letzterer reduziert die
   Überschreitung nur geringfügig, da der Python-Service-Kern der
   eigentliche Umfangstreiber ist.
2. **Renderer-Commit-Gate (#811):** diese Scheibe ändert selbst KEINE Datei
   unter `src/output/renderers/alert/*.py` — das Gate sollte daher nicht
   triggern. Falls sich beim Implementieren doch eine Notwendigkeit zeigt,
   dort etwas anzufassen (z. B. weil der Slice-1a-Baustein doch angepasst
   werden muss), ist das ein Scope-Bruch gegen diese Spec und muss vorab
   eskaliert werden, nicht stillschweigend umgesetzt.
3. **Keine Mocks erlaubt** (CLAUDE.md) — Nowcast-Auslösung muss über den
   echten `frame_source`-DI-Seam (`RadarNowcastService(frame_source=...)`,
   `radar_service.py:84-89`) mit echten, aufgezeichneten `RadarFrame`-Daten
   getestet werden, kein Mock-Theater der Provider-Kette.
4. **Netzwerkkosten pro Ort:** Compare-Presets haben typischerweise ≥3 Orte;
   bei aktiviertem Radar-Alarm entsteht pro 15-Min-Zyklus ein
   `get_nowcast()`-Call je Ort. Default-aus (opt-in) mindert das Risiko in
   dieser Scheibe strukturell.
5. **Validator-Lücke fürs Bündelformat** (siehe Known Limitations) — muss
   bei der E2E-Verifikation bewusst über den Einzel-Ort-Fall geführt werden,
   sonst entsteht ein falsches „E2E bestanden"-Signal für den Mehrort-Fall.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Referenz, bereits akzeptiert) + ADR-0017 (Referenz,
  bereits akzeptiert) + ADR-0021 (Referenz, bereits akzeptiert) — **keine
  neue ADR nötig**.
- **Rationale:** Diese Scheibe führt keinen neuen Architektur-Baustein ein.
  Sie verdrahtet den bereits über ADR-0011/ADR-0017 gedeckten, in Slice 1a
  fertiggestellten Versand-Baustein (`send_multi_location_radar_alert`,
  `to_multi_location_onset_alert_message`) mit einem neuen, aber strukturell
  bereits etablierten Muster: eigener Radar-Alarm-Parallelpfad neben der
  Metrik-Deviation-Engine (Trip-Vorbild: `check_radar_alerts()` +
  `/radar-alert-checks`, separat von `/alert-checks`). ADR-0021 hat den
  Radar-Onset-Pfad explizit als „vorerst Trip-spezifisch ... eine
  Verallgemeinerung dieser Bausteine ist separat zu betrachten, falls
  Compare sie ebenfalls benötigt" benannt — diese Scheibe (zusammen mit dem
  bereits gelieferten Slice 1a) ist genau dieser separat betrachtete
  Vollzug, keine neue Architektur-Entscheidung.

## Test Plan

Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md) — echte
Preset-/Throttle-/State-Pfade und echte, aufgezeichnete `RadarFrame`-Fixtures
über den `frame_source`-DI-Seam (kein Mock der Provider-Kette). Vorbild:
`tests/tdd/test_issue_1169_compare_alert_consumer.py` (echte Preset-/
Snapshot-/State-Pfade, echte Zwei-Nutzer-Isolation).

Neue Testdatei: `tests/tdd/test_compare_radar_alert.py`

- `test_single_location_onset_triggers_bundled_alert` (AC-1) — echtes
  Fixture-Preset + `frame_source`-DI mit aufgezeichnetem nassen Frame-Set,
  echter `CompareRadarAlertService`-Lauf, Assertion: eine Mail mit
  Ortsname + Onset-Zeitangabe.
- `test_no_alert_when_all_locations_dry_or_late_onset` (AC-2) — trockenes/
  spätes Frame-Set, `count == 0`, kein `mail_sink`-Aufruf.
- `test_two_simultaneous_locations_bundled_into_one_mail` (AC-3) — zwei
  auslösende Fixture-Orte, Assertion `count == 1`, beide Ortsnamen im
  gerenderten Text.
- `test_cooldown_suppresses_repeat_alert_within_window` (AC-4) — zwei
  zeitlich versetzte echte Läufe gegen echten Throttle-Store, genau ein
  Versand.
- `test_quiet_hours_suppress_alert_despite_detected_onset` (AC-5) —
  Systemzeit innerhalb Ruhezeit-Fenster, `count == 0` trotz erkanntem Onset.
- `test_disabled_or_missing_flag_skips_nowcast_fetch_entirely` (AC-6) —
  zählender echter `frame_source`-Doppelgänger, Assertion `call_count == 0`
  bei fehlendem/`false` Feld.
- `test_two_users_isolated_locations_and_recipients` (AC-7) — zwei echte
  `data/users/<uid>/`-Verzeichnisse mit je eigenem Preset/Empfänger,
  Datei-Pfad- UND Empfänger-Isolation, kein `"default"`-Fallback im
  Code-Pfad.
- `test_convective_event_labeled_when_triggering` (AC-8) — konvektives
  Frame-Fixture (WMO 95/96/99) mit `onset_minutes <= 20`, Assertion auf
  Auslösung UND Gewitter/Hagel-Label im gerenderten Text.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1041, Slice 1b von 3 (Backend-
  Service, Konfig-Feld, Scheduler-Verdrahtung; nutzt den in Slice 1a
  gelieferten Bündel-Versand-Baustein).
