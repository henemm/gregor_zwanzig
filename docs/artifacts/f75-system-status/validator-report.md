# External Validator Report

**Spec:** `docs/specs/modules/system_status_redesign.md`
**Datum:** 2026-04-18T15:50:00+02:00
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `/settings` zeigt Dashboard mit 3 Sektionen: Reports, Account, Verfuegbarkeit | Screenshot zeigt ALTE Settings-Seite (Email SMTP, Signal, Telegram, Weather Provider, Default Location) | **FAIL** |
| 2 | Sektion "Deine Reports" mit user-freundlichen Job-Namen | Text "Deine Reports" nicht auf Seite gefunden (E2E Check) | **FAIL** |
| 3 | Sektion "Dein Account" mit Zaehlern und Kanal-Uebersicht | Text "Dein Account" nicht auf Seite gefunden (E2E Check) | **FAIL** |
| 4 | Sektion "Verfuegbarkeit" mit Ampel-Status | Text "Verfuegbarkeit" nicht auf Seite gefunden (E2E Check) | **FAIL** |
| 5 | Jobs `alert_checks` und `inbound_command_poll` ausgeblendet | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 6 | Zeitformat de-AT ("morgen um 07:00") | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 7 | Last-Run relatives Format ("vor X Minuten") | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 8 | Zaehler mit Links (Trips → /trips, Abos → /subscriptions, Locations → /locations) | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 9 | Benachrichtigungs-Kanaele aus Profile | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 10 | Wetter-Modelle pro Location (GeoSphere/OpenMeteo) | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 11 | Ampel: gruen = "System laeuft" | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 12 | Version dezent unter Ampel | Feature nicht deployed — nicht pruefbar | **FAIL** |
| 13 | Alte Config-Tabelle entfernt | ALTE Config-Tabelle (Weather Provider, Default Location) ist NOCH SICHTBAR | **FAIL** |
| 14 | Go/Python Health-Split entfernt | Feature nicht deployed — nicht pruefbar (alte Seite hat keinen Health-Split, aber auch kein neues Design) | **FAIL** |

## Findings

### Finding 1: Feature nicht deployed
- **Severity:** CRITICAL
- **Expected:** `/settings` zeigt neues 3-Sektionen-Dashboard (Deine Reports, Dein Account, Verfuegbarkeit)
- **Actual:** `/settings` zeigt die ALTE Account-Settings-Seite mit Email SMTP Konfiguration, Signal (Callmebot), Telegram (Bot API), Weather Provider Dropdown, Default Location (Innsbruck 47.2692/11.4041), SAVE-Button und Test-Buttons
- **Evidence:** Screenshot `/tmp/e2e_test_1776520067.png` — zeigt eindeutig die alte Seite. E2E-Checks auf "Deine Reports", "Dein Account", "Verfuegbarkeit" alle NEGATIV.

### Finding 2: API-Endpoints funktionieren
- **Severity:** INFO
- **Expected:** `/api/scheduler/status` und `/api/health` liefern Daten
- **Actual:** Beide Endpoints antworten korrekt mit validen JSON-Daten. scheduler/status liefert 5 Jobs (morning_subscriptions, evening_subscriptions, trip_reports_hourly, alert_checks, inbound_command_poll). health liefert status=ok, version=0.1.0.
- **Evidence:** WebFetch-Responses erfolgreich abgerufen

## Verdict: BROKEN

### Begruendung

Die `/settings`-Seite auf dem laufenden Server zeigt die **alte** Account-Konfigurationsseite. Keines der 14 erwarteten Behaviors aus der Spec ist implementiert oder deployed. Alle drei Haupt-Sektionen ("Deine Reports", "Dein Account", "Verfuegbarkeit") fehlen komplett. Die alte Konfigurations-Tabelle (Weather Provider, Default Location) ist noch sichtbar, obwohl sie laut Spec entfallen soll.

Die Backend-APIs (`/api/scheduler/status`, `/api/health`) funktionieren und liefern die korrekten Daten — das Problem liegt ausschliesslich im Frontend bzw. im Deployment.

**Moegliche Ursachen (als Validator stelle ich nur fest, diagnostiziere nicht):**
- Code wurde geaendert aber Server nicht neu gestartet
- Code wurde noch nicht committed/deployed
- Die Aenderungen sind auf einem anderen Branch
