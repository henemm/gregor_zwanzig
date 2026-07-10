---
entity_id: multi_location_onset_alert
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [alerts, radar, nowcast, renderer, epic-1095, issue-1041]
---

<!-- Issue #1041 — Slice 1a von 3. Fundament: macht den Onset-Alarm-Renderer + die
     Nachricht-Konstruktion mehrort-fähig (E-Mail), damit Slice 1b (CompareRadarAlertService)
     mehrere Vergleichsorte in EINE Alarm-Mail bündeln kann. Kein Compare-Wiring, keine Konfig,
     kein Scheduler in dieser Scheibe. Gesamtdesign: issue_1041_compare_radar_alert.md. -->

# Issue #1041 — Mehrort-fähiger Onset-Alarm-Renderer & Bündel-Nachricht (Slice 1a/3)

## Approval

- [x] Approved — PO „Go" 2026-07-10

## Purpose

Der bestehende Onset-Alarm-Renderpfad (Radar-„Regen fängt gleich an") ist strikt auf
**genau einen Ort/ein Segment** gebaut (`e = msg.events[0]`). Um später (Slice 1b)
mehrere Vergleichsorte, die gleichzeitig auslösen, in **eine** Alarm-Mail zu bündeln,
muss dieser Baustein mehrort-fähig werden — für den **E-Mail-Kanal** (Orts-Vergleichs-
Alarme sind E-Mail-only). Diese Scheibe liefert die Bündel-Fähigkeit isoliert und mit
Hard-Gate-Regressionssicherung, dass die **produktive Trip-Radar-Alarm-Ausgabe
byte-identisch bleibt**. Sie ändert **kein** Nutzerverhalten für sich genommen
(Fundament-Scheibe, Muster wie #1168) — der eigentliche Compare-Radar-Alarm kommt in
Slice 1b.

## Source

- **File:** `src/output/renderers/alert/model.py` (MODIFY, ~3–5 LoC) — additives,
  optionales Feld `OnsetEvent.location_label: str | None = None` (`model.py:30-40`),
  exakt analog zum bereits existierenden `AlertEvent.location_label` (`model.py:12-27`,
  Issue #1170). Bestehende Aufrufer (Trip-Radar) setzen es nie → Default `None`.
- **File:** `src/output/renderers/alert/project.py` (MODIFY, ~35–45 LoC) — neue
  `to_multi_location_onset_alert_message(groups, *, tz, stand_at) -> AlertMessage`
  neben `to_multi_point_alert_message()` (`project.py:68-105`). `groups =
  list[(location_name: str, NowcastResult)]`. Baut je Gruppe ein `OnsetEvent`
  (Onset-Zeit/Intensität aus `NowcastResult`) mit `km_from=km_to=0.0` (kein
  Etappen-km, Muster `to_multi_point_alert_message:98`) und
  `location_label=location_name` — bei **genau einer** Gruppe `location_label=None`
  (fällt damit auf den unveränderten Single-Onset-Pfad zurück, analog Zeile 99 der
  Vorlage). `AlertMessage.source` auf festen Marker `"compare-radar"`, damit die
  Renderer weiterhin über den Onset-Zweig (`msg.source is not None`) routen.
- **File:** `src/output/renderers/alert/render.py` (MODIFY, ~35–45 LoC) — **nur der
  E-Mail- und Subject-Onset-Renderer** bekommen einen `len(msg.events) > 1`-Zweig:
  - `_render_subject_onset` (`render.py:111-115`): bei mehreren Events ein
    Sammel-Betreff (z. B. „Regen-Alarm: N Orte") statt des Ein-Ort-Betreffs.
  - `_render_email_onset` (`render.py:118-168`): bei mehreren Events je Ort eine
    Zeile mit `location_label` + Onset-Zeit + Intensität (Muster `loc_prefix`,
    `render_email:328-333` im Deviation-Pfad), statt nur `events[0]`.
  - `_render_telegram_onset` (`:171-177`) und `_render_sms_onset` (`:180-186`)
    bleiben **unverändert** (Trip-only, Single-Location; Compare-Radar ist
    E-Mail-only). Bei genau einem Event (`location_label=None`) bleiben auch
    Subject/E-Mail bit-identisch zum heutigen Trip-Radar-Pfad.
- **File:** `src/services/notification_service.py` (MODIFY, ~25–35 LoC) — neue
  Methode `send_multi_location_radar_alert(entities: list[tuple[str,
  "NowcastResult"]], effective_channels: set[str], *, tz=None, stand_at=None,
  mail_sink=None) -> NotificationResult`. Baut über
  `to_multi_location_onset_alert_message()` **eine** `AlertMessage` für alle
  gebündelten Orte und delegiert an den unveränderten `_dispatch_alert_message()`-
  Kern (`notification_service.py:397-…`), `mail_type="radar-alert"` wie der
  Trip-Radar-Pfad (`radar_alert_service.py:100`). Muster:
  `send_multi_location_deviation_alert` (`notification_service.py:369-400`).
- **File:** `tests/tdd/test_multi_location_onset_alert.py` (NEU) — Verhaltens- und
  Regressionstests, siehe Test Plan. Benannt nach Verhalten (Testnamensregel), nicht
  nach Issue-Nummer.

> **Schicht-Hinweis:** Alle vier Produktivdateien sind Python-Core
> (`src/output/renderers/alert/`, `src/services/`). Kein Go, kein Frontend in dieser
> Scheibe. `RadarNowcastService.get_nowcast`-Aufrufe, das Konfig-Feld
> `radar_alert_enabled` und der Scheduler-Endpoint gehören zu Slice 1b.

## Estimated Scope

- **LoC:** Produktivcode ~100–130, Tests ~90–120 → Summe ~190–250. Innerhalb des
  250/Workflow-Limits (E-Mail-only-Zuschnitt statt aller vier Kanäle hält es klein).
- **Files:** 4 MODIFY Python + 1 neue Testdatei.
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.model.AlertMessage`/`OnsetEvent` | intern | Kanonisches Alert-Datenmodell (ADR-0011) — additiv um `location_label` erweitert |
| `output.renderers.alert.project.to_multi_point_alert_message` | intern | Struktur-Vorbild für die neue Onset-Bündel-Nachricht |
| `output.renderers.alert.render._render_email_onset` | intern | Onset-E-Mail-Renderer — bekommt den Multi-Location-Zweig |
| `services.notification_service._dispatch_alert_message` | intern | Geteilter Versand-Kern (ADR-0017), unverändert |
| `services.notification_service.send_multi_location_deviation_alert` | intern | Muster für die neue `send_multi_location_radar_alert` |
| `services.radar_service.NowcastResult` | intern | Datenträger je Ort (onset_minutes/intensity_label/is_convective) — Eingang der Bündel-Nachricht |
| `services.radar_alert_service.build_onset_alert_message` | intern | Trip-Single-Onset-Vorbild (trip-verdrahtet) — bleibt unverändert, ist die Regressions-Referenz |
| ADR-0011 (Single Backend Renderer) | Architektur | `render.py` bleibt der einzige Alert-Renderer — auch für den neuen Multi-Onset-E-Mail-Zweig |
| ADR-0017 (Output-Paket-Konsolidierung) | Architektur | `NotificationService` bleibt einziger Versand-Orchestrierer |
| ADR-0021 (Shared Deviation Engine) | Architektur | Benennt den Radar-Onset-Pfad explizit als „separat zu verallgemeinern, falls Compare ihn benötigt" — diese Scheibe ist der erste Schritt dieses Vollzugs |
| Slice 1b (CompareRadarAlertService, `issue_1041_compare_radar_alert.md`) | Folge | Einziger künftiger Consumer von `send_multi_location_radar_alert` |

## Implementation Details

### Kern der Änderung

```
Heute:  Onset-Renderer nimmt strikt events[0]  → EIN Ort/Segment
1a:     OnsetEvent.location_label (optional, Default None)
        + to_multi_location_onset_alert_message(groups) baut N Events
        + _render_subject_onset / _render_email_onset: len(events) > 1 -> alle Orte auflisten
        + send_multi_location_radar_alert(entities, channels): EINE gebündelte Mail
Invariante: len(events) == 1 && location_label is None  ⇒  Ausgabe byte-identisch zu heute
```

### Regressions-Invariante (Hard Gate)

Der bestehende Trip-Radar-Alarm nutzt denselben Renderpfad und läuft produktiv.
Der Multi-Zweig darf ausschließlich bei `len(msg.events) > 1` greifen; im
Single-Event-Fall (`location_label=None`) muss die gerenderte Ausgabe für
**Subject, E-Mail, Telegram und SMS** byte-identisch zum Stand vor dieser Scheibe
bleiben. Nachweis: Vorher/Nachher-Snapshot eines echten Trip-Radar-Alert-Fixtures
(AC-2 + AC-3). Telegram/SMS werden gar nicht angefasst — ihr Regressionsnachweis
ist trivial, aber Teil des Snapshots.

## Expected Behavior

- **Input:** Eine Liste `entities = [(ort_name, NowcastResult), …]` (in Slice 1b von
  `CompareRadarAlertService` je Preset-Lauf gefüllt; in dieser Scheibe direkt im Test
  konstruiert) plus Ziel-Kanäle (`{"email"}`).
- **Output:** Genau **eine** `AlertMessage`, die — bei mehreren Einträgen — im
  E-Mail-Body alle Orte mit Onset-Zeit und Intensität auflistet und einen
  Sammel-Betreff trägt; bei genau einem Eintrag die unveränderte Ein-Ort-Onset-Mail.
  `send_multi_location_radar_alert` versendet sie über den geteilten Dispatch-Kern an
  die übergebenen Empfänger/Kanäle.
- **Side effects:** keine neuen Persistenz-Dateien in dieser Scheibe (State/Throttle
  gehören zu Slice 1b). Nur Mailversand über den bestehenden Kern.

## Acceptance Criteria

- **AC-1:** Given eine Bündel-Onset-Nachricht, die für **zwei oder mehr** Orte
  gebaut wird (je Ort ein Onset ≤ 20 Min, `location_label` gesetzt) / When sie in
  den E-Mail-Kanal gerendert und über `send_multi_location_radar_alert` versendet
  wird / Then geht **eine** E-Mail raus, deren Body **jeden** Ort mit seinem eigenen
  Namen, seiner Onset-Zeit und Intensität auflistet (nicht nur der erste Ort).
  - Test: echte `NowcastResult`-Fixtures für zwei benannte Orte, echter
    `send_multi_location_radar_alert`-Lauf gegen ein `mail_sink`; Assertion: genau
    ein Versand UND beide Ortsnamen samt Onset-Angabe im gerenderten Body.

- **AC-2:** Given ein bestehendes Trip-Radar-Alarm-Fixture mit **genau einem**
  Onset-Event (`location_label=None`) / When es nach Einführung des additiven
  `OnsetEvent.location_label`-Felds und des Multi-Onset-E-Mail-Zweigs erneut
  gerendert wird / Then sind **Subject und E-Mail-Body byte-identisch** zum Stand
  vor dieser Scheibe.
  - Test: Vorher/Nachher-Snapshot desselben Single-Onset-Fixtures (fixierter
    erwarteter Text im Repo), exakter String-Vergleich Subject + Body.

- **AC-3:** Given dasselbe Single-Onset-Fixture / When es in **Telegram und SMS**
  gerendert wird / Then ist die Ausgabe byte-identisch zum Stand vor dieser Scheibe
  (diese Renderer werden nicht angefasst — der Test sichert das ab).
  - Test: Vorher/Nachher-Snapshot der Telegram- und SMS-Onset-Ausgabe, exakter
    String-Vergleich.

- **AC-4:** Given eine Bündel-Nachricht, in der einer der Orte konvektiv ist
  (`is_convective=True`, Gewitter/Hagel) / When sie in E-Mail gerendert wird / Then
  trägt die Zeile dieses Orts das Gewitter/Hagel-Label (nicht bloß „Regen"), die
  Zeilen der übrigen Orte ihr jeweils korrektes Regen-Label.
  - Test: zwei Fixtures (einer konvektiv via WMO 95/96/99, `radar_service.py:114-116`,
    einer normaler Regen); Assertion, dass beide Orts-Zeilen ihr korrektes,
    unterschiedliches Label zeigen.

- **AC-5:** Given eine Bündel-Nachricht mit **genau einem** Ort (`groups` der Länge 1,
  `location_label=None`) / When sie gerendert wird / Then ist die Ausgabe identisch
  zum Ein-Ort-Onset-Pfad (kein Multi-Zweig, keine „N Orte"-Sammelform).
  - Test: `to_multi_location_onset_alert_message` mit einer einzigen Gruppe →
    gerenderte E-Mail entspricht der Single-Onset-Referenz (kein Sammel-Betreff,
    kein Listen-Layout).

## Known Limitations

- Nur der **E-Mail-Kanal** wird mehrort-fähig; Telegram/SMS-Onset bleiben
  Single-Location (Compare-Radar-Alarme sind E-Mail-only, wie #1169/#1170). Falls
  künftig Compare-Telegram-/SMS-Empfänger existieren, wäre der Multi-Zweig dort
  nachzuziehen.
- Diese Scheibe hat **keinen produktiven Aufrufer** — `send_multi_location_radar_alert`
  wird erst durch Slice 1b (`CompareRadarAlertService`) genutzt. Getestet wird sie in
  dieser Scheibe direkt (Fundament-Scheibe, kein Nutzerverhalten für sich).
- Kein Konfig-Feld, kein Scheduler, kein `get_nowcast`-Aufruf, keine Throttle-/
  Quiet-Hours-Logik in dieser Scheibe — alles Slice 1b.

## Risiken

1. **Regressionsrisiko am geteilten Alert-Renderer:** `render.py`/`model.py` werden
   auch vom produktiven Trip-Radar-Alarm genutzt. Additives, optionales
   `location_label` + strikter `len(events) > 1`-Guard halten das Risiko klein; die
   byte-identische Snapshot-Sicherung (AC-2/AC-3) ist Hard Gate.
2. **Renderer-Commit-Gate (#811):** Änderungen an `src/output/renderers/alert/*.py`
   triggern das Radar-/Alert-Mailgate. Vor Commit muss der Verhaltens-/Regressionstest
   dieser Scheibe grün sein (und ggf. der zugehörige Alert-Validator laufen).
3. **Keine Mocks** (CLAUDE.md): Bündel- und Regressionstests laufen gegen echte
   `NowcastResult`-Fixtures und den echten Renderer/Dispatch-Kern (`mail_sink`), kein
   Mock-Theater.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 + ADR-0017 + ADR-0021 (alle bereits akzeptiert) — **keine neue
  ADR nötig**.
- **Rationale:** Additive Erweiterung bestehender, ADR-gedeckter Bausteine (ein
  gemeinsamer Renderer, ein Versand-Orchestrierer). ADR-0021 hat die Verallgemeinerung
  des Radar-Onset-Pfads für Compare bereits explizit vorgesehen; diese Scheibe ist der
  erste, isolierte Schritt davon und bricht keine bestehende Entscheidung.

## Test Plan

Alle Tests folgen „keine Mocks" — echte `NowcastResult`-Fixtures, echter Renderer,
echter Dispatch-Kern über `mail_sink`. Neue Datei:
`tests/tdd/test_multi_location_onset_alert.py`

- `test_bundled_email_lists_all_locations` (AC-1) — zwei Orts-Fixtures, ein
  `send_multi_location_radar_alert`-Lauf, genau eine Mail, beide Orte samt Onset im
  Body.
- `test_single_onset_email_and_subject_byte_identical` (AC-2) — Vorher/Nachher-
  Snapshot des Single-Onset-Fixtures (Subject + Body exakt).
- `test_single_onset_telegram_sms_byte_identical` (AC-3) — Snapshot Telegram + SMS
  unverändert.
- `test_bundle_labels_convective_location_distinctly` (AC-4) — konvektiver + normaler
  Ort in einer Bündel-Mail, je korrektes Label.
- `test_single_group_falls_back_to_single_onset_layout` (AC-5) — Bündel-Nachricht der
  Länge 1 rendert wie der Ein-Ort-Pfad.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1041, Slice 1a von 3 (Mehrort-Onset-
  Renderer + Bündel-Nachricht, E-Mail).
