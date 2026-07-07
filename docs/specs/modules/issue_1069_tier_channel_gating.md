---
entity_id: issue_1069_tier_channel_gating
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [tiers, channels, gating]
---

# Issue #1069: Channel-Gating nach Nutzerlevel

## Approval

- [ ] Approved

## Purpose

Setzt serverseitig durch, dass SMS nur an Nutzer mit Level `standard` oder `premium` verschickt
wird — unabhängig davon, was `report_config.send_sms` sagt oder ob Kontaktdaten (Handynummer)
hinterlegt sind. Bisher prüft `src/services/trip_report_scheduler.py` an beiden Versand-Enforcement-
Stellen nur `config.send_sms`, ohne das Level des Nutzers zu kennen — ein Nutzer könnte
`send_sms=true` direkt per API setzen und bekäme trotzdem SMS, obwohl sein Level das nicht erlaubt
(Frontend-Gating allein ist kein Zugriffsschutz). Das Frontend bekommt außerdem einen korrekten
Unterschied zwischen "Handynummer fehlt" und "ab Standard verfügbar" sowie einen sichtbaren,
aber deaktivierten Slot für den noch nicht existierenden Kanal "Premium-SMS" (Garmin inReach).
Das ist Slice 2 aus Epic #1067 (`docs/specs/modules/epic_user_tiers_overview.md`), aufbauend auf
dem in Slice 1 (Issue #1068, gemergt) eingeführten `Tier`-Feld.

## Source

- **File:** `internal/model/tier.go` (neu)
- **Identifier:** Tier→Channel-Tabelle/Helper (z.B. `SmsAllowed(tier string) bool`)

> **PFLICHT — Schicht-Hinweis:** Betrifft alle drei Schichten in diesem Slice:
> - **Go-API** (`internal/model/tier.go`, `internal/handler/auth.go`) — Source of Truth für die
>   Tier→Channel-Regel, Ausgabe über `profileResponse.sms_allowed`.
> - **Python-Core** (`src/services/trip_report_scheduler.py`, neues Modul
>   `src/services/user_tier.py`) — eigene, gespiegelte Durchsetzung am tatsächlichen
>   Versand-Zeitpunkt, da Python den Go-Code nicht importieren kann.
> - **Frontend** (`frontend/src/lib/components/edit/EditReportConfigSection.svelte`,
>   `frontend/src/lib/types.ts`) — liest ausschließlich `profile.sms_allowed`, dupliziert die
>   Tier→Channel-Logik NICHT selbst.

## Estimated Scope

- **LoC:** ~150-200 (+ ~20-30 Nachtrag für AC-8/`trip_alert.py`)
- **Files:** 7 (Nachtrag: `src/services/trip_alert.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issue_1068_tier_model_display` (Slice 1) | spec (module) | Liefert das `Tier`-Feld auf `internal/model.User`, `profileResponse.Tier` und den Frontend-Typ `UserTier` — Grundlage für dieses Slice |
| `docs/specs/modules/epic_user_tiers_overview.md` | spec (epic) | Gesamtkontext, PO-Entscheidung "Go ist Source of Truth", Slice-Schnitt |
| `internal/model/user.go` (`type User struct`) | module | Liefert `u.Tier` als Eingabe für die neue Tier→Channel-Tabelle |
| `src/app/config.py` (`Settings.with_user_profile`) | module | Etabliertes Muster für direktes Lesen von `data/users/<user_id>/user.json` als rohes Dict in Python — wird für den neuen Tier-Lookup übernommen, nicht verändert |

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/tier.go` | ADD (neu) | Tier→Channel-Tabelle bzw. Helper-Funktion, z.B. `SmsAllowed(tier string) bool`, die für `"standard"` und `"premium"` `true` liefert, sonst `false` (inkl. leerer String / unbekannter Wert = `false`, analog zum Default-Fallback-Prinzip aus Slice 1) |
| `internal/handler/auth.go:362-372` (`profileResponse`) | MODIFY | Neues Feld `SmsAllowed bool \`json:"sms_allowed"\`` |
| `internal/handler/auth.go:383-413` (`toProfileResponse()`) | MODIFY | Berechnet `SmsAllowed` aus dem bereits ermittelten `tier`-Wert über die neue Helper-Funktion aus `tier.go` |
| `src/services/user_tier.py` (neu) | ADD | Kleines Modul mit `sms_allowed(user_id: str) -> bool` — liest `data/users/<user_id>/user.json` als rohes Dict (Muster wie `Settings.with_user_profile` in `src/app/config.py:197-225`), `profile.get("tier", "free")`, gespiegelte Tier→Channel-Tabelle (kein Import aus Go-Code, keine Kopplung an ein Python-`User`-Objekt) |
| `src/services/trip_report_scheduler.py:623` (`_send_trip_report_outcome`) | MODIFY | `send_sms=config is not None and config.send_sms` wird um den Tier-Check ergänzt: `send_sms=config is not None and config.send_sms and sms_allowed(self._user_id)` |
| `src/services/trip_report_scheduler.py:835` (`_build_trip_report_request`) | MODIFY | Dieselbe Ergänzung wie oben, an der zweiten Enforcement-Stelle |
| `frontend/src/lib/types.ts` | MODIFY (Zusatz) | Neues optionales Feld `sms_allowed?: boolean` — entweder direkt am `Profile`-Interface in `EditReportConfigSection.svelte` (siehe unten) oder, falls dort kein zentraler Typ existiert, als Kommentar-verknüpfte Ergänzung zu `UserTier` |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte:82-93` (`interface Profile`, `availableChannels`) | MODIFY | `interface Profile` bekommt `sms_allowed?: boolean`; `availableChannels.sms` wird zu `!!profile?.sms_to && profile?.sms_allowed !== false` (Bestandsnutzer ohne das Feld im Response — z.B. während eines Rollouts — dürfen nicht fälschlich gesperrt werden, daher expliziter `!== false`-Vergleich statt Truthy-Check) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte:416-420` (Hinweistext SMS) | MODIFY | Neue Fallunterscheidung: wenn `profile?.sms_allowed === false` → Hinweis "SMS ab Level Standard verfügbar" (PRIORITÄT vor dem Kontakt-Hinweis, auch wenn zusätzlich die Handynummer fehlt); sonst wenn `!profile?.sms_to` → bestehender Hinweis "Handynummer fehlt — im Account einrichten" unverändert |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (neue Zeile nach dem SMS-Block, ~421) | ADD | Neue, immer deaktivierte Menüzeile "Premium-SMS (Garmin inReach) — bald verfügbar", unabhängig vom Tier des Nutzers (rein informativ, keine Checkbox-Funktionslogik, kein `onChannelChange`-Callback) |
| `src/services/trip_alert.py:~808-810` (Radar-Nowcast-Alert-Dispatch, inline `effective_channels`-Aufbau) | MODIFY (Nachtrag, Adversary-Fund F001) | `if can_sms and config and getattr(config, "send_sms", False):` wird um `and sms_allowed(self._user_id)` ergänzt — derselbe Tier-Check wie im Scheduler-Pfad, hier vor dem `effective_channels.add("sms")` |
| `src/services/trip_alert.py:~933-964` (`_effective_alert_channels`) | MODIFY (Nachtrag, Adversary-Fund F001) | Vor dem `return` (in beiden Zweigen: Legacy-Pfad ohne aktive `alert_rules` UND dem Pfad mit `rule.channels`/geerbten Briefing-Kanälen) wird `"sms"` aus dem berechneten Kanal-Set entfernt, falls `not sms_allowed(self._user_id)` — ein einziger Prüfpunkt vor dem Rückgabewert deckt sowohl den impliziten `config.send_sms`-Pfad (`_briefing_channels`) als auch den expliziten `rule.channels=["sms"]`-Bypass ab |

## Implementation Details

**Go — Source of Truth (`internal/model/tier.go`):** Eine kleine, neue Datei mit einer Tabelle oder
Helper-Funktion, die für ein gegebenes `tier`-String (`"free"`/`"standard"`/`"premium"`/leer)
entscheidet, ob SMS erlaubt ist. Beispielform:

```go
package model

var smsAllowedTiers = map[string]bool{
    "standard": true,
    "premium":  true,
}

func SmsAllowed(tier string) bool {
    return smsAllowedTiers[tier]
}
```

`toProfileResponse()` in `internal/handler/auth.go` ruft diese Funktion mit dem bereits ermittelten
`tier`-Wert (nach dem "free"-Fallback aus Slice 1) auf und setzt das Ergebnis in das neue
`profileResponse.SmsAllowed`-Feld. Damit bleibt die Tier→Channel-Regel an genau einer Stelle im
Code definiert.

**Python — gespiegelte Durchsetzung (`src/services/user_tier.py`):** Da Python den Go-Code nicht
importieren kann, bekommt dieses Modul eine eigene, kleine Kopie derselben Regel (zwei Stellen im
Code statt einer dritten im Frontend — etabliertes Muster, siehe Tier-Typ-Spiegelung Go→TS aus
Slice 1). Tier-Lookup erfolgt wie in `Settings.with_user_profile` (`src/app/config.py:197-225`)
durch direktes Lesen von `data/users/<user_id>/user.json` als rohes JSON-Dict — **kein** neues
Python-`User`-Objekt, kein ORM-Layer:

```python
def sms_allowed(user_id: str) -> bool:
    profile_path = Path(f"data/users/{user_id}/user.json")
    if not profile_path.exists():
        return False
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return profile.get("tier", "free") in ("standard", "premium")
```

Beide Enforcement-Stellen in `trip_report_scheduler.py` (Zeilen 623 und 835) rufen diese Funktion
mit `self._user_id` auf und verUNDen das Ergebnis mit dem bestehenden `config.send_sms`-Ausdruck.
Ein Nutzer mit Level `free`, der `send_sms=true` in seiner Konfiguration gesetzt hat, bekommt damit
serverseitig trotzdem keine SMS — unabhängig vom Frontend-Zustand.

**Frontend (`EditReportConfigSection.svelte`):** `availableChannels.sms` prüft zusätzlich
`profile.sms_allowed`. Der Hinweistext unter der SMS-Checkbox unterscheidet zwei Sperrgründe und
zeigt bei Konflikt (Level zu niedrig UND Handynummer fehlt) ausschließlich den Level-Hinweis, weil
das Eintragen einer Handynummer für einen `free`-Nutzer ohnehin wirkungslos wäre. Der neue
"Premium-SMS"-Menüpunkt ist ein reiner UI-Slot ohne Checkbox-Funktion (kein `send_`-State, kein
`onChannelChange`) — er signalisiert nur, dass ein weiterer Kanal geplant ist, unabhängig vom Level
des aktuell eingeloggten Nutzers.

## Expected Behavior

- **Input:** `report_config.send_sms = true` bei einem Trip, dessen Besitzer laut `user.json` das
  Level `free` (oder kein `tier`-Feld) hat; Aufruf des Report-Versands (Scheduler-Cron oder
  On-Demand). Zusätzlich: `GET /api/auth/profile` für Nutzer mit unterschiedlichen Leveln.
- **Output:** Der tatsächlich an den `NotificationService` übergebene `send_sms`-Wert ist `False`,
  obwohl `config.send_sms == True` war. `GET /api/auth/profile` liefert zusätzlich zum bestehenden
  `tier`-Feld ein Feld `sms_allowed` (`true` für `standard`/`premium`, `false` für `free`/leer). Die
  Trip-Bearbeitungsseite zeigt bei `free`-Nutzern die SMS-Checkbox deaktiviert mit dem Hinweis
  "SMS ab Level Standard verfügbar" und darunter einen deaktivierten "Premium-SMS"-Menüpunkt mit
  "bald verfügbar"-Hinweis.
- **Side effects:** Keine Persistenzänderung an bestehenden `user.json`-Dateien — reine
  Lese-/Auswertungslogik an den bestehenden Versand- und Anzeige-Pfaden.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Besitzer das Level `free` hat (kein `tier`-Feld in dessen
  `user.json`) und dessen `report_config.send_sms` auf `true` gesetzt ist / When der reguläre
  Report-Versand für diesen Trip ausgelöst wird (z.B. per On-Demand-Trigger über den internen
  Versand-Endpoint) / Then wird über den konfigurierten Kanal tatsächlich keine SMS verschickt,
  obwohl die Konfiguration SMS aktiviert hatte.
  - Test: Echter Trip mit `send_sms=true` und einem Test-User ohne `tier`-Feld anlegen, echten
    Versand auslösen (Staging-internal, kein Mock auf `sms_allowed`/`trip_report_scheduler`), und
    im tatsächlich an den Notification-/SMS-Versandpfad übergebenen Request prüfen, dass
    `send_sms == False` ankommt (Beweis über das reale Verhalten des gebauten Requests, nicht über
    Quelltext-Inspektion).

- **AC-2:** Given ein zweiter Trip mit identischer `send_sms=true`-Konfiguration, dessen Besitzer
  ein `user.json` mit `"tier": "standard"` hat / When derselbe Versand-Trigger für diesen Trip
  ausgelöst wird / Then wird `send_sms == True` an den Versandpfad übergeben — SMS bleibt für
  berechtigte Nutzer unverändert funktionsfähig.
  - Test: Echter zweiter Test-User mit präpariertem `tier: standard` in seiner `user.json`, echter
    Versand-Trigger, Prüfung des tatsächlich gebauten Requests. Zusammen mit AC-1 als
    Zwei-Nutzer-Test gegen versehentliche Generalsperre abgesichert.

- **AC-3:** Given ein eingeloggter Nutzer mit Level `free` / When `GET /api/auth/profile` für
  diesen Nutzer aufgerufen wird / Then enthält die JSON-Antwort `"sms_allowed": false`; für einen
  Nutzer mit Level `standard` oder `premium` enthält sie `"sms_allowed": true`.
  - Test: Echter HTTP-Call gegen `/api/auth/profile` mit zwei präparierten Test-Usern
    (`tier` fehlend/`free` vs. `standard`), Prüfung des geparsten JSON-Felds `sms_allowed` im
    Response-Body gegen die Staging-API (kein Mock, kein Datei-Read).

- **AC-4:** Given ein eingeloggter Nutzer mit Level `free`, dessen Handynummer im Account bereits
  hinterlegt ist / When dieser Nutzer die Trip-Bearbeitungsseite öffnet / Then ist die
  SMS-Checkbox deaktiviert und der sichtbare Hinweistext lautet sinngemäß "ab Standard verfügbar"
  (NICHT "Handynummer fehlt") — der Level-Hinweis hat Vorrang, obwohl Kontaktdaten vorhanden sind.
  - Test: Playwright-E2E gegen Staging als eingeloggter `free`-Test-Nutzer mit hinterlegter
    Handynummer: Trip-Bearbeitungsseite öffnen, SMS-Checkbox-Zustand (`disabled`) und den
    gerenderten Hinweistext (`page.getByTestId('channel-sms-hint')` bzw. äquivalent) im echten DOM
    prüfen — kein Quelltext-Check.

- **AC-5:** Given ein eingeloggter Nutzer mit Level `standard` oder `premium`, dessen Handynummer
  im Account NICHT hinterlegt ist / When dieser Nutzer die Trip-Bearbeitungsseite öffnet / Then
  ist die SMS-Checkbox deaktiviert und der Hinweistext lautet weiterhin "Handynummer fehlt — im
  Account einrichten" (unverändertes Altverhalten, weil hier der Kontakt-Grund und nicht das Level
  die Sperre verursacht).
  - Test: Playwright-E2E gegen Staging als eingeloggter `standard`-Test-Nutzer ohne hinterlegte
    Handynummer: Trip-Bearbeitungsseite öffnen, prüfen dass der Hinweistext weiterhin
    "Handynummer fehlt" lautet (echtes DOM, kein Quelltext-Check).

- **AC-6:** Given ein beliebiger eingeloggter Nutzer, unabhängig von dessen Level / When dieser
  Nutzer die Trip-Bearbeitungsseite mit den Kanal-Checkboxen öffnet / Then ist zusätzlich zu
  E-Mail/Telegram/SMS ein sichtbarer, aber dauerhaft deaktivierter Menüpunkt
  "Premium-SMS (Garmin inReach)" mit einem "bald verfügbar"-Hinweis erkennbar — auch für
  `premium`-Nutzer, da der Kanal selbst noch nicht existiert.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer (beliebiges Level): Trip-Bearbeitungs-
    seite öffnen, prüfen dass ein Element mit Text "Premium-SMS" bzw. "Garmin inReach" sichtbar UND
    im deaktivierten Zustand ist (`toBeVisible()` + `toBeDisabled()` gegen das echte DOM).

- **AC-7:** Given ein Bestandsnutzer, dessen `user.json` kein `tier`-Feld enthält (Alt-Account vor
  Epic #1067) / When für diesen Nutzer sowohl `GET /api/auth/profile` aufgerufen als auch ein
  Report-Versand mit `send_sms=true` ausgelöst wird / Then verhält sich das System exakt wie ein
  `free`-Nutzer (`sms_allowed: false` in der Profile-Antwort, keine tatsächlich verschickte SMS) —
  kein Absturz, kein impliziter Premium-Zugriff durch das fehlende Feld.
  - Test: Echter Test-User mit `user.json` ohne `tier`-Feld (Bestandsdaten-Simulation), sowohl
    HTTP-Call gegen `/api/auth/profile` als auch echter Versand-Trigger; Prüfung beider Ergebnisse
    (`sms_allowed == false`, `send_sms == False` im gebauten Request) gegen dieselbe reale Datei.

- **AC-8 (Nachtrag 2026-07-07, Adversary-Fund F001):** Given ein Trip, dessen Besitzer das Level
  `free` hat, mit einer aktiven Alert-Regel bzw. Briefing-Konfiguration, die SMS als Kanal
  vorsieht (`report_config.send_sms=true` und/oder `alert_rules[].channels` enthält `"sms"`) /
  When ein Wetter-Abweichungs-Alert (`TripAlertService._send_alert` /
  `_effective_alert_channels`) oder ein Radar-Nowcast-Alert (`TripAlertService.check_radar_alerts`)
  für diesen Trip ausgelöst wird / Then enthält das tatsächlich für den Versand berechnete
  Kanal-Set KEIN `"sms"`, unabhängig davon, was `report_config.send_sms` oder `rule.channels`
  vorsehen — dieselbe Level-Sperre wie im Scheduler-Report-Pfad (AC-1) gilt auch hier. Für
  `standard`/`premium`-Nutzer bleibt SMS in beiden Alert-Pfaden unverändert nutzbar (Regressions-
  Guard, analog AC-2).
  - Test: Echter Aufruf von `TripAlertService._effective_alert_channels(trip)` bzw. des
    Radar-Alert-Dispatch-Codepfads mit einem echten `user.json` (Tier `free` vs. `standard`) und
    einer Trip-Konfiguration, die SMS über `report_config.send_sms` UND separat über
    `alert_rules[].channels=["sms"]` aktiviert — Prüfung des zurückgegebenen Kanal-Sets
    (`"sms" not in channels` für `free`, `"sms" in channels` für `standard`). Kein Mock auf
    `TripAlertService` oder `sms_allowed` selbst.

## Known Limitations

- **Kein Enforcement für Alert-/Update-Frequenz-Limits.** Dieses Slice betrifft ausschließlich den
  Kanal-Zugriff (SMS ja/nein). Wie oft ein Nutzer pro Tag Alerts/Updates bekommt, ist explizit
  NICHT Teil dieses Scopes — folgt in Slice 3 (Issue #1070,
  `docs/specs/modules/epic_user_tiers_overview.md`).
- **Kein Level-Änderungs-Antrag.** Ein Nutzer kann sein Level in diesem Slice weiterhin nicht selbst
  ändern oder eine Änderung beantragen — das ist Slice 4 (Issue #1071).
- **Premium-SMS (Garmin inReach) existiert als Kanal nicht.** Dieses Slice legt nur den sichtbaren,
  deaktivierten UI-Slot an. Die tatsächliche Anbindung (F9, `docs/features/scope.md`) ist ein
  eigenes, noch nicht spezifiziertes Folge-Issue — unabhängig vom Nutzerlevel bleibt der Menüpunkt
  bis dahin für ALLE Nutzer deaktiviert, auch für Premium.
- **Kein Admin-Werkzeug.** Level-Zuweisung erfolgt weiterhin ausschließlich manuell durch direktes
  Setzen von `tier` in der jeweiligen `user.json` durch den Product Owner (unverändert seit
  Slice 1).
- **Zwei-Stellen-Duplizierung der Tier→Channel-Regel (Go + Python) ist bewusst in Kauf genommen.**
  Eine dritte Kopie im Frontend wird durch das `sms_allowed`-Feld auf `profileResponse` vermieden;
  Go bleibt Source of Truth, Python spiegelt nur, weil ein Cross-Language-Import nicht möglich ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** PO-bestätigte Architektur-Entscheidung (siehe Team-Auftrag): Go ist Source of
  Truth für die Tier→Channel-Regel, Python spiegelt sie in einer eigenen kleinen Funktion (kein
  Cross-Language-Import möglich), Frontend liest ausschließlich das bereits berechnete
  `sms_allowed`-Feld. Additive Erweiterung bestehender Strukturen (neue kleine Go-Datei, neues
  kleines Python-Modul, ein zusätzliches Response-Feld) — keine neue Architektur-Schicht, kein
  eigenständiges ADR-Dokument nötig.

## Changelog

- 2026-07-07: Initial spec created
- 2026-07-07: Nachtrag AC-8 nach Adversary-Fund F001 — Tier-Gate greift zusätzlich in
  `src/services/trip_alert.py` (Radar-Nowcast-Alert-Dispatch + `_effective_alert_channels`),
  nicht nur im Scheduler-Report-Pfad. PO-Entscheidung: sofort in dieses Arbeitspaket
  aufgenommen statt als separates Folge-Issue.
