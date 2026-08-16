---
entity_id: fix_1912_scheduler_briefing_timeout
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [scheduler, monitoring, go, issue-1912]
---

# Scheduler: Briefing-Timeout meldet keinen Ausfall mehr

## Approval

- [ ] Approved

## Purpose

Der Go-Scheduler soll einen abgelaufenen HTTP-Timeout nicht länger mit einem
Briefing-Totalausfall verwechseln. Der Alarm „Trip-Briefing-Totalausfall (#1346)" darf nur
noch feuern, wenn der Versand nachweislich **nicht** stattgefunden hat.

## Source

- **File:** `internal/scheduler/scheduler.go` (Go-API), neu `internal/scheduler/briefing_slots.go`
- **Identifier:** `Scheduler.tripReports()`, `Scheduler.client`

Schicht: **Go-API** (`internal/`). Kein Python-Anteil — der Scheduler liest die Slot-Datei
direkt vom Dateisystem, wie `internal/scheduler/briefing_health.go` es für die
Provider-Diagnose bereits tut. Kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~180 Produktivcode, ~120 Tests → **~300 gesamt** (LoC-Limit 250 wird voraussichtlich
  gerissen, Override durch den PO nötig)
- **Files:** 4 (2 neu, 2 geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `internal/store` | genutzt | Nutzerliste (`ListUserIDs()`), user-scoped Pfad zur Datenwurzel |
| `src/services/briefing_slots.py` | gelesen | Schreibt `briefing_slots.json`; Format ist der Vertrag |
| `internal/notify/mq.go` | genutzt | MQ-Alarm an `infra` |
| `internal/scheduler/briefing_health.go` | Vorbild | Muster für direkten Dateizugriff aus Go |

## Implementation Details

### Der Defekt

`internal/scheduler/scheduler.go:115` trägt `Timeout: 120 * time.Second`. Die
Briefing-Generierung brauchte am 2026-08-16 real 278 s. `tripReports()` (Z. 271-304) wertet
den Timeout als `error` und feuert auf der ok→error-Flanke den MQ-Alarm.

`internal/handler/proxy.go:277` trägt seit #1756 für denselben Vorgang 300 s, mit dem
Kommentar „der reguläre Erfolgsfall braucht 3-4 Minuten". Der Scheduler war also nie lang
genug.

### Warum die naheliegende Lösung nicht reicht

Eine Nachfrage im Moment des Timeouts (18:02) findet den Slot noch ohne `outcome` — der
Versand endet erst 18:04:38. Die Positivkontrolle braucht deshalb einen **späteren**
Zeitpunkt, nicht nur einen Nachweis.

### Die Regel: Entwarnung nur mit Positivkontrolle

Jeder Trip, den ein Lauf anfasst, erhält beim Start einen **Claim** in `briefing_slots.json`
(`outcome: null`, `src/services/briefing_slots.py:153-176`); nach dem Versandversuch schreibt
`record_outcome()` (Z. 197-209) den Ausgang. Der Lauf weiß damit genau, welche Trips zu prüfen
sind.

```
Timeout beim Aufruf von /api/scheduler/trip-reports
  → Lauf gilt zunächst als UNENTSCHIEDEN (nicht error)
  → begrenztes Nachfassen: Slot-Datei je Nutzer erneut lesen
      Intervall 15 s, Obergrenze 120 s nach dem Timeout
  → Auswertung:
      alle Claims dieses Laufs tragen outcome == "sent"  → kein Alarm, Status "partial"
      irgendein Claim ohne "sent"                        → Alarm, Status "error"
      Datei fehlt / nicht lesbar / Slot unbekannt        → Alarm, Status "error"
      Nachfassfrist abgelaufen, noch offene Claims       → Alarm, Status "error"
```

Die Richtung ist bewusst asymmetrisch: **nur ein positiv belegtes `sent` unterdrückt.** Jede
Unsicherheit führt zum Alarm. Ein Wachhund, der im Zweifel schweigt, ist schlimmer als einer,
der im Zweifel bellt.

### Teil 1: Timeout

`scheduler.go:115` von 120 s auf 300 s, analog #1756. Der Client wird von drei Jobs geteilt
(`scheduler.go:415` Trip-Reports, `:547` Alert-Checks, `:594` Compare) — die Änderung wirkt
bewusst auf alle drei, weil alle denselben Core rufen. Die Overlap-Sperre in `recordRun()`
(`TryLock`, Z. 481-499) verhindert, dass ein langsamer Lauf den Folgetick blockiert.

## Expected Behavior

- **Input:** Ergebnis des HTTP-Aufrufs an `/api/scheduler/trip-reports` je Nutzer; Inhalt von
  `briefing_slots.json` je Nutzer
- **Output:** Job-Status in `/api/scheduler/status` (`ok` | `partial` | `error`); MQ-Alarm an
  `infra` nur bei `error` auf der ok→error-Flanke
- **Side effects:** MQ-Nachricht; keine Schreibzugriffe auf `briefing_slots.json` — der
  Scheduler liest ausschließlich

## Acceptance Criteria

- **AC-1:** Given der Aufruf an den Python-Core läuft in den Timeout / When die Slot-Datei für
  alle Trips dieses Laufs `outcome: "sent"` trägt / Then wird **kein** MQ-Alarm gesendet und
  der Job-Status ist `partial`, nicht `error`.
  - Test: Go-Test mit `httptest`-Server, der nicht antwortet, und vorbereiteter Slot-Datei mit
    `sent`; injizierter `notifier` zählt die Alarme — erwartet: 0.

- **AC-2:** Given der Aufruf läuft in den Timeout / When mindestens ein Claim dieses Laufs
  **kein** `outcome: "sent"` trägt / Then wird der MQ-Alarm „Trip-Briefing-Totalausfall (#1346)"
  mit `priority=high` an `infra` gesendet und der Job-Status ist `error`.
  - Test: wie AC-1, aber ein Claim mit `outcome: null` — erwartet: genau 1 Alarm an `infra`.

- **AC-3:** Given der Aufruf läuft in den Timeout / When die Slot-Datei fehlt, unlesbar ist
  oder keinen Eintrag für diesen Lauf enthält / Then wird alarmiert. Fehlende Information
  entwarnt **nie**.
  - Test: drei Go-Testfälle (Datei fehlt, kaputtes JSON, leere Einträge) — jeder erwartet
    einen Alarm.

- **AC-4:** Given ein echter Ausfall ohne Timeout (Python-Core antwortet mit Fehler) / When der
  Lauf endet / Then verhält sich der Alarm **unverändert** wie vor dieser Änderung — die
  Positivkontrolle greift ausschließlich im Timeout-Fall.
  - Test: bestehende Scheduler-Tests bleiben grün; zusätzlicher Test mit HTTP 500 erwartet
    weiterhin einen Alarm.

- **AC-5:** Given der Versand schließt während der Nachfassfrist ab / When der Slot erst nach
  dem Timeout auf `sent` wechselt / Then wird das erkannt und nicht alarmiert. Eine Prüfung
  ausschließlich im Moment des Timeouts erfüllt dieses AC nicht.
  - Test: Slot-Datei wird während der Nachfassphase auf `sent` geändert; erwartet: 0 Alarme.
    Zeitquelle injiziert, damit der Test nicht real 120 s wartet.

- **AC-6:** Given die Nachfassfrist von 120 s / When die Claims bis dahin offen bleiben / Then
  endet das Nachfassen und es wird alarmiert — der Scheduler hängt nicht unbegrenzt.
  - Test: Slot bleibt offen; erwartet: genau 1 Alarm, Laufzeit begrenzt durch injizierte
    Zeitquelle.

- **AC-7:** Given mehrere Nutzer / When der Lauf für Nutzer A erfolgreich, für Nutzer B im
  Timeout ohne `sent` endet / Then wird alarmiert, und die Prüfung erfolgt je Nutzer — der
  Erfolg von A entwarnt B nicht.
  - Test: zwei Nutzer im Store, Slot-Dateien getrennt; erwartet: Alarm.

- **AC-8:** Given der Slot ist nach **Ortstag** geschlüsselt, der Scheduler rechnet in
  Serverzeit / When beide auseinanderfallen / Then prüft die Positivkontrolle den Ortstag des
  Trips, nicht den Servertag.
  - Test: Trip in abweichender Zeitzone, Slot unter dem Ortstag abgelegt; erwartet: `sent`
    wird gefunden, kein Alarm.

## Known Limitations

- Der Timeout von 300 s ist weiterhin eine feste Zahl. Wächst die Generierungsdauer mit
  Nutzer-/Trip-Zahl über 300 s, greift künftig die Nachfass-Mechanik statt des Timeouts —
  der Fehlalarm bleibt aus, aber die Laufzeit sollte beobachtet werden.
- Die Timeout-Konstante bleibt an vier Stellen verstreut (`scheduler.go:115`, `proxy.go:108`,
  `proxy.go:277`, `compare_preset.go:676`). Eine gemeinsame Quelle ist sinnvoll, gehört aber
  als Nebenbefund nach #1199, nicht in diese Scheibe.
- Der #1346-Wachhund bleibt auf **Totalausfall** ausgelegt. Ein Teilausfall (einzelne Trips
  scheitern, andere nicht) wird durch AC-2 künftig ebenfalls alarmiert — das ist strenger als
  vorher und beabsichtigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche berührt (Kanäle, Provider, Datenmodell, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie bleiben unverändert). Der Scheduler liest eine
  bestehende Datei über ein bereits etabliertes Muster (`briefing_health.go`).

## Changelog

- 2026-08-16: Initial spec created (#1912)
