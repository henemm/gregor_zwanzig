---
entity_id: fix_1407_compare_versand_ueberwachung
type: bug
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [rueckbau, compare, monitoring, issue-1407]
---

# Mini-Spec: Rückbau der verwaisten Heartbeat-Funktion (#1407)

**Track:** Fast Track (Rückbau toten Codes, kein neues Verhalten)

## Ausgangslage

`api/routers/scheduler.py:147-167 _ping_heartbeat_compare()` wurde für einen Versandpfad gebaut (`compare_subscription.py`, Spec `issue_253_compare_email.md` — nie freigegeben, Status „superseded"), der mit **#1131** vollständig entfernt wurde. Der einzige vorgesehene Aufrufer existiert nicht mehr.

Die Funktion ist der Grund, warum #1407 als „muss nur angeschlossen werden" angelegt wurde. Sie anzuschließen wäre falsch: der aktive Compare-Versand hängt seit **#1346** an der gemeinsamen Überwachung von Trip und Vergleich; ein zweiter, eigener Ping würde die Konsolidierung zurückdrehen und einen Trip-Ausfall wieder verdecken können.

Die eigentliche Überwachungslücke (Heartbeat nie konfiguriert, MQ-Ersatzmeldung seit 2026-06-22 stumm) liegt in der Infrastruktur: **henemm/henemm-infra#149**.

## Was sich ändert

- `_ping_heartbeat_compare()` entfällt ersatzlos.
- Die Tests, die ausschließlich diese Funktion prüfen, entfallen mit ihr.
- Nicht mehr benötigte Importe/Konstanten, die nur sie brauchte, entfallen.

## Was sich nicht ändern darf

- **Der aktive Versandweg** `trigger_compare_presets_daily` → `run_briefing_dispatch` → `dispatch_orchestrator.py` bleibt unberührt.
- **Die gemeinsame Überwachungsanbindung** aus #1346 bleibt unberührt — kein zweiter Ping, keine geänderte Erfolgsbedingung.
- `/api/scheduler/status` liefert weiterhin für `trip_reports_hourly` und `compare_presets_daily` Zeit, Status und Fehler. Das ist die Grundlage, auf der infra#149 aufsetzt — geht sie verloren, ist die geplante Überwachung wertlos.

## Acceptance Criteria

- **AC-1:** Given die verwaiste Funktion `_ping_heartbeat_compare` existiert heute in `api/routers/scheduler.py` / When der Rückbau gelaufen ist / Then verweist **kein Code** mehr darauf — keine Definition, kein Aufruf, kein Import, kein Test, der sie ausführt.
  **Ausdrückliche Ausnahme (präzisiert 2026-07-30 nach dem Rückbau):** Die synthetischen Fixtures in `tests/test_success_status_guard.py` (`_write_unwired_heartbeat_surface`, AC-10/AC-11 jenes Wächters) dürfen den Namen als **Textbeispiel** behalten. Sie bauen den Fehlertyp „nicht verdrahtete Heartbeat-Fläche" in einer eigenen `tmp_path`-Datei nach, um zu beweisen, dass der Wächter ihn erkennt — sie importieren und rufen nichts. Dort zu löschen würde den Wächter seines eigenen Prüffalls berauben. Die zuerst gewählte Formulierung „kein einziger Treffer" war zu wörtlich; maßgeblich ist der Code-Verweis, nicht die Zeichenkette.
- **AC-2:** Given `tests/test_success_status_guard.py` führt die Funktion heute als Eintrag eines Ratschen-Wächters (B13, aus #1405) / When der Eintrag mit der Funktion entfernt wird / Then bleibt der Wächter grün und seine Sollzahl ist **kleiner** als vorher — eine Ratsche darf durch einen Rückbau nur schrumpfen, niemals wachsen, und der Eintrag verschwindet nicht stillschweigend, sondern mit sichtbar verringerter Zahl.
- **AC-3:** Given der aktive Versandweg läuft über `trigger_compare_presets_daily` → `run_briefing_dispatch` → `dispatch_orchestrator.py` / When der Rückbau gelaufen ist / Then ist an diesem Weg und an der gemeinsamen Überwachungsanbindung aus #1346 keine Zeile geändert — kein zweiter Ping, keine veränderte Erfolgsbedingung.
- **AC-4:** Given die Infrastruktur-Reparatur infra#149 setzt darauf auf, dass der Server je Auftrag Zeit, Status und Fehler meldet / When der Rückbau gelaufen ist / Then liefert `/api/scheduler/status` weiterhin sowohl `trip_reports_hourly` als auch `compare_presets_daily` mit diesen Feldern — geht das verloren, ist die geplante Überwachung wertlos.
- **AC-5:** Given der Rückbau entfernt Code und Tests / When die betroffenen Modul-Suiten laufen / Then sind sie grün, ohne dass eine Erwartung abgeschwächt oder ein Test übersprungen wurde.

## Nachweis

1. **Vor dem Löschen:** belegen, dass niemand ruft — Suche über `src/`, `api/`, `internal/`, `tests/` und `frontend/`, Ergebnis im Workflow festhalten. Ein einziger Treffer außerhalb der Definition und der zugehörigen Tests stoppt den Rückbau.
2. **Nach dem Löschen:** betroffene Modul-Suiten grün (kein Vollsuite-Lauf — die versendet echte Mails).
3. `/api/scheduler/status` liefert lokal weiterhin beide Briefing-Aufträge.

## Nicht in diesem Umfang

Die Überwachung selbst (infra#149), die fehlenden Umgebungsvariablen, jede Änderung an der Erfolgsbedingung.

## Umfang

Rückbau, ~40–70 Zeilen **entfernt**, keine neuen. Weit unter dem Limit.
