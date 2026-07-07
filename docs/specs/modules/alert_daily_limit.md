---
entity_id: alert_daily_limit
type: feature
created: 2026-07-07
updated: 2026-07-07
status: draft
workflow: tiers-3-alert-frequency
version: "1.0"
tags: [epic-1067, tiers, alerts]
---

# Alert-Tages-Obergrenze nach Nutzerlevel

## Approval

- [ ] Approved

## Purpose

Führt eine harte Tages-Obergrenze für proaktive Alerts (Deviation-Watcher und
Radar/Onset) pro Nutzerlevel ein: Free 2/Tag, Standard 4/Tag, Premium kein
Tageslimit (nur der bestehende 15-Min-Mindestabstand gilt weiter). Ein
persistierter Tageszähler pro Nutzer mit Mitternachts-Reset in Europe/Vienna
verhindert, dass Free-/Standard-Nutzer über einen der beiden Alert-Pfade das
Limit umgehen. Planmäßige Trip-Briefings (morning/evening) sind explizit NICHT
betroffen (PO-Entscheidung 2026-07-07).

## Source

- **File:** `src/services/alert_daily_limit.py`
- **Identifier:** `load(user_id, now)`, `is_allowed(user_id, now)`, `increment(user_id, now)`

> **Schicht-Hinweis:** Neues Modul und beide Modify-Ziele liegen im Python-Core
> unter `src/services/` (FastAPI-Domain-Backend). Einzige Go-Änderung ist die
> Cron-Frequenz in `internal/scheduler/scheduler.go` (Scheduler-Ebene, kein
> Domain-Code).

## Estimated Scope

- **LoC:** ~95-120 (Produktionscode, ohne Tests)
- **Files:** 4 Produktionsdateien + 1 neue Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/user_tier.py` | module | Liefert `daily_alert_limit(user_id)` neben bestehendem `sms_allowed(user_id)`; liest `tier` aus `data/users/<user_id>/user.json`, Default `free` |
| `src/services/trip_alert.py` | module | `TripAlertService` — beide Alert-Sende-Pfade (`check_and_send_alerts`, `check_radar_alerts`); Gate + Increment werden hier verdrahtet |
| `data/users/<user_id>/user.json` | data | Quelle für `tier`-Feld |
| `data/users/<user_id>/alert_throttle.json` | pattern | Etabliertes State-File-Muster (Read-Modify-Write), das der neue Tageszähler exakt nachbildet |
| `internal/scheduler/scheduler.go` | module | Cron-Definition `alertChecks` (Zeile 93), Frequenzänderung 30→15 Min |

## Implementation Details

**Neues Modul `src/services/alert_daily_limit.py`:**
- `load(user_id, now) -> int`: liest `data/users/<user_id>/alert_daily_count.json`
  (`{"date": "YYYY-MM-DD", "count": N}`). Konvertiert `now` (UTC) nach
  `ZoneInfo("Europe/Vienna")`, nimmt davon `.date()`. Ist das gespeicherte
  `date` ungleich dem heutigen Vienna-Datum, liefert `load` `0` zurück — reine
  Load-Semantik, kein Schreibzugriff bei Reset.
- `is_allowed(user_id, now) -> bool`: holt `daily_alert_limit(user_id)` aus
  `user_tier.py`. `None` (Premium) → immer `True`. Sonst: `load(user_id, now) < limit`.
- `increment(user_id, now) -> None`: Read-Modify-Write der Zählerdatei nach
  demselben Vienna-Datumsvergleich wie `load` (neuer Tag → Zähler startet bei 1
  statt fortlaufend zu erhöhen).
- `now` ist durchgehend ein Funktionsparameter (Zeit-Injektion). Kein
  Zeit-Mock, keine `datetime.now()`-Aufrufe im Modul selbst.

**`src/services/user_tier.py` (MODIFY):**
- Neue Funktion `daily_alert_limit(user_id) -> int | None` neben
  `sms_allowed(user_id)`. Mapping: `free` → `2`, `standard` → `4`,
  `premium` → `None`. Liest `profile.get("tier", "free")` aus `user.json`,
  identisches Default-Verhalten wie `sms_allowed`.

**`src/services/trip_alert.py` (MODIFY), zwei Stellen:**
1. Deviation-Pfad `check_and_send_alerts` (~Zeile 147 ff.): nach dem
   bestehenden `_is_throttled_with_cooldown`-Gate, vor teurem
   Fetch/Nowcast, zusätzlicher Gate-Check `alert_daily_limit.is_allowed(...)`.
   Increment `alert_daily_limit.increment(...)` strikt hinter dem
   bestehenden Recording (~Zeile 206-208), also nur wenn `delivered` truthy war.
2. Radar-Pfad `check_radar_alerts` (~Zeile 711 ff.): analog nach
   `_is_radar_throttled`-Gate, Increment hinter dem bestehenden
   `_append_alert_log`/Recording (~Zeile 832-849).
   Beide Pfade nutzen dasselbe `self._user_id` → derselbe Zähler, kein
   Umgehungspfad zwischen Deviation- und Radar-Alerts.

**`internal/scheduler/scheduler.go` (MODIFY):**
- Zeile 93: Cron-Ausdruck `"0,30 * * * *"` → `"*/15 * * * *"` für den
  `alertChecks`-Job, inklusive Anpassung des begleitenden Kommentartexts.
  Ermöglicht, dass Premium-Nutzer (kein Tageslimit, nur 15-Min-Cooldown)
  tatsächlich viertelstündlich beliefert werden können.

## Expected Behavior

- **Input:** `user_id`, aktueller Zeitpunkt `now` (UTC), Nutzer-Tier aus
  `user.json`, bestehender Alert-Auslöser (Deviation- oder Radar-Bedingung
  erfüllt, Cooldown-Gate bereits passiert).
- **Output:** Alert wird versendet und Zähler in
  `data/users/<user_id>/alert_daily_count.json` erhöht, ODER Alert wird
  unterdrückt (kein Versand, kein Increment, kein neuer `alert_log`-Eintrag),
  wenn das Tageslimit erreicht ist.
- **Side effects:** Schreibt/aktualisiert `alert_daily_count.json` nur bei
  tatsächlich erfolgreichem Versand (Increment hinter `delivered`-Guard).
  Kein Schreibzugriff bei reinem Reset-Load. Cron-Job `alertChecks` läuft ab
  Deploy viertelstündlich statt halbstündlich für alle Nutzer.

## Acceptance Criteria

- **AC-1:** Given ein Free-Nutzer (`tier: "free"`) hat am aktuellen Vienna-Kalendertag bereits 2 Alerts erhalten / When ein dritter Deviation- oder Radar-Alert ausgelöst wird / Then wird dieser unterdrückt — kein neuer `alert_log`-Eintrag, kein `mail_sink`-Eintrag, Zähler bleibt bei 2.
  - Test: Zählerdatei mit heutigem Vienna-Datum und `count=2` vorseeden, echten `check_and_send_alerts`- bzw. `check_radar_alerts`-Lauf über bestehende DI-Seams (`mail_sink`, `radar_service`) ausführen; danach prüfen, dass `mail_sink` leer ist und die Zählerdatei weiterhin `count=2` enthält (kein Mock, echter Dateizustand).

- **AC-2:** Given ein Standard-Nutzer (`tier: "standard"`) hat am aktuellen Vienna-Kalendertag bereits 4 Alerts erhalten / When ein fünfter Alert ausgelöst wird / Then wird dieser unterdrückt, während derselbe Ablauf bei nur 3 vorherigen Alerts einen vierten noch zulässt.
  - Test: Zwei echte Läufe mit vorgeseedeter Zählerdatei (`count=3` bzw. `count=4`), Standard-Tier in `user.json`; Assert über tatsächlichen Versand (`mail_sink` gefüllt vs. leer) und den resultierenden Zählerstand in der Datei.

- **AC-3:** Given ein Premium-Nutzer (`tier: "premium"`) hat am aktuellen Vienna-Kalendertag bereits 6 Alerts erhalten / When ein weiterer Alert ausgelöst wird (Cooldown-Gate bereits passiert) / Then wird dieser trotzdem versendet, weil für Premium kein Tageslimit gilt.
  - Test: Zählerdatei mit `count=6` vorseeden, Premium-Tier setzen, echten Alert-Lauf ausführen; Assert, dass `mail_sink` einen neuen Eintrag enthält und der Zähler weiter erhöht wird (kein Deckel).

- **AC-4:** Given ein Free-Nutzer hat sein Tageslimit von 2 Alerts erreicht, während gleichzeitig der Kalendertag in Europe/Vienna wechselt (nicht in UTC) / When ein weiterer Alert nach dem Vienna-Mitternachts-Übergang ausgelöst wird / Then ist das volle Tagesbudget wieder verfügbar.
  - Test: `now`-Parameter auf `2026-07-07 23:30 UTC` (= `2026-07-08 01:30` Vienna) injizieren nach vorherigem Erschöpfen des Budgets an `2026-07-07`; echter Lauf zeigt erneuten Versand und Zählerstand `1` in der neu geschriebenen Datei — beweist die Vienna- statt UTC-Grenze.

- **AC-5:** Given ein Free-Nutzer hat sein Tageslimit bereits über den Radar-Alert-Pfad ausgeschöpft / When derselbe Nutzer einen Deviation-Alert auslöst (und umgekehrt) / Then wird auch dieser unterdrückt, weil beide Pfade denselben Zähler teilen.
  - Test: Zählerdatei über einen echten Radar-Alert-Lauf auf `count=2` bringen, danach echten `check_and_send_alerts`-Lauf für denselben `user_id` ausführen; Assert, dass `mail_sink` für den Deviation-Pfad leer bleibt und kein neuer `alert_log`-Eintrag entsteht (schließt die Umgehungslücke beweisbar für beide Richtungen).

- **AC-6:** Given ein Alert passiert das Tageslimit-Gate, bricht aber danach durch einen anderen bestehenden Filter ab (kein Change / `alert_state` unverändert / briefing-suppression / kein zustellbarer Kanal, `delivered` falsy) / When der Lauf beendet ist / Then bleibt der Tageszähler unverändert.
  - Test: Bedingungen so konstruieren, dass das Gate passiert wird, aber `delivered` am Ende falsy bleibt (z.B. kein zustellbarer Kanal konfiguriert); echter Lauf zeigt unveränderten Zählerstand in `alert_daily_count.json` vor und nach dem Lauf — beweist F001-Symmetrie (nur tatsächlicher Versand zählt).

- **AC-7:** Given der Go-Scheduler ist mit der neuen Cron-Definition deployt / When der Scheduler-Status abgefragt wird / Then läuft der `alertChecks`-Job im 15-Minuten-Takt statt im 30-Minuten-Takt.
  - Test: Echter Scheduler-Start (oder `/api/scheduler/status`-Abfrage gegen laufenden Prozess) zeigt für `alertChecks` einen `next_run`-Abstand von 15 Minuten zum vorherigen Lauf, nicht 30 Minuten.

## Known Limitations

- **Bestands-Test-Kompatibilität (Watch-Item, offen):** Der `free`-Default bei
  fehlendem `user.json` (Limit 2) kann bestehende Deviation-/Radar-Tests
  brechen, die für einen Default-User ohne `user.json` mehr als 2 Alerts pro
  Tag erwarten. Muss in der TDD-Phase gegen die tatsächlichen Bestands-Fixtures
  geprüft werden — dort Tier explizit setzen oder Fixture anpassen, wo bisher
  kein Tier vorgesehen war.
- Bewusst NICHT in Scope: rückwirkende Migration eines etwaigen eigenen,
  unabhängigen Throttle-Pfads außerhalb von `trip_alert.py` — falls beim
  Implementieren ein solcher Pfad gefunden wird, gehört das in ein eigenes
  Folge-Issue statt in diesen Slice.
- Race-Bedingungen bei parallelen Läufen desselben Nutzers werden nicht
  gesondert behandelt (Scheduler ruft pro Nutzer sequentiell, siehe Kontext R4)
  — analog zur bestehenden `alert_throttle.json`-Handhabung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der neue Tageszähler folgt exakt dem bereits etablierten
  Muster für Alert-State-Persistenz pro Nutzer (`alert_throttle.json`,
  `AlertStateService`/`alert_state`) — reines JSON-Read-Modify-Write unter
  `data/users/<user_id>/`, keine neue Persistenz-Technologie, kein neuer
  Architektur-Layer. Der Tier→Limit-Lookup reiht sich in die bestehende
  `user_tier.py`-Fassade neben `sms_allowed()` ein. Es entsteht kein
  strukturell neues Architekturmuster, das eine ADR rechtfertigen würde.

## Changelog

- 2026-07-07: Initial spec created
