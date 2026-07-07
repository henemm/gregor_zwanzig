---
entity_id: user_tiers_overview
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.1"
tags: [tiers, monetization, channels, alerts, epic]
---

# Epic: Nutzerlevel (Free / Standard / Premium)

## Approval

- [ ] Approved (PO)

## Purpose

Gregor Zwanzig bekommt drei Nutzerlevel (Free, Standard, Premium), die sich zunächst NUR in zwei
Dimensionen unterscheiden: (1) welche Versand-Channel dem Nutzer zur Verfügung stehen und (2) wie
oft Alerts/Updates pro Tag maximal verschickt werden dürfen. Level ist sichtbar für den Nutzer und
kann per einfachem Formular zur Änderung beantragt werden (kein Self-Service-Upgrade, keine
Zahlungsanbindung in diesem Schnitt).

| Level | Channel | Alert-/Update-Frequenz |
|---|---|---|
| Free | E-Mail, Telegram | max. **2 pro Kalendertag** (harte Tages-Obergrenze, Mitternachts-Reset) |
| Standard | + SMS | max. **4 pro Kalendertag** (harte Tages-Obergrenze, Mitternachts-Reset) |
| Premium | + Premium-SMS (Garmin inReach, existiert noch nicht) | **Mindestabstand 15 Minuten** (kein Tageslimit — bei diesem Intervall ist ein Zähler kein zusätzlicher Schutz mehr) |

**PO-Entscheidung 2026-07-07 (beantwortet Frage 1 aus v1.0):** Free/Standard sind echte
Tages-Obergrenzen mit Mitternachts-Reset, KEIN reiner Mindestabstand — ein Nutzer bekommt an
einem Tag maximal N Alerts/Updates, unabhängig vom zeitlichen Abstand dazwischen. Premium bleibt
ein reiner Mindestabstand (Intervall-Semantik von „alle 15 Minuten"), ohne Tageszähler.

## Bestehende Systeme, die wir nutzen (Befund)

- **Nutzerverwaltung existiert bereits, keine neue Persistenz nötig.** Ein Nutzer ist ein
  JSON-Objekt `model.User` (`internal/model/user.go:10-22`), persistiert unter
  `data/users/<id>/user.json`, geladen/gespeichert über `internal/store/user.go:48-79`
  (`Store.LoadUser` / `Store.SaveUser`). Python liest dieselbe Datei direkt als Dict, z.B.
  `src/app/loader.py:818-825` (`lookup_user_by_email`) — kein zweites Datenmodell. Ein neues
  `Tier`-Feld reiht sich hier nur ein, keine YAML-Datei nötig (die vom PO erwähnte "YAML o.ä."
  Option ist durch das bestehende JSON-per-User-Schema bereits erfüllt).
- **Anzeige des eigenen Profils existiert bereits** unter `/account`
  (`frontend/src/routes/account/+page.svelte:566-604`, Card „Dein Account" mit
  Benachrichtigungs-Badges), gespeist von `GET /api/auth/profile`
  (`internal/handler/auth.go:412-425`, Response-Typ `profileResponse` in
  `internal/handler/auth.go:363-373`). Tier-Anzeige reiht sich hier als weiteres Badge ein.
- **Channel-Verfügbarkeits-Gating existiert bereits, aber nur "Kontaktdaten vorhanden?", nicht
  "Level erlaubt?"**: `frontend/src/lib/components/edit/EditReportConfigSection.svelte:89-93`
  berechnet `availableChannels` rein aus `profile.mail_to`/`telegram_chat_id`/`sms_to`. Es gibt
  bereits das UI-Pattern für "Channel gesperrt + Hinweistext" (Zeilen 405-419, `!availableChannels.sms`
  → Hinweis „Handynummer fehlt — im Account einrichten"). Dieses Pattern wird um eine
  Level-Bedingung erweitert, keine neue UI-Mechanik nötig.
- **Serverseitiger Versand-Enforcement-Punkt existiert bereits**: der eigentliche Report-Versand
  baut den Request in `src/services/trip_report_scheduler.py` an zwei Stellen
  (`_send_trip_report_outcome` um Zeile 623, `_build_trip_report_request` um Zeile 835) jeweils mit
  `send_sms=config is not None and config.send_sms`. Hier fehlt heute jede Tier-Prüfung — ein Nutzer
  ohne Standard/Premium-Level könnte `send_sms=true` direkt per API setzen und bekäme trotzdem SMS.
  Das ist der Punkt, an dem Slice 2 serverseitig durchsetzen muss (Frontend-Gating allein reicht
  nicht — Analogie zum Cross-User-Datenleck-Grundsatz: UI-Gating ist kein Zugriffsschutz).
- **Alert-Frequenz wird heute bereits gedrosselt, aber pro Trip via Mindestabstand, nicht pro
  Nutzerlevel und nicht als Tageszähler**: `src/services/radar_alert_service.py` hat ein
  Cooldown-System (`AlertService.__init__(throttle_hours=2, ...)` Zeile 55,
  `_is_throttled_with_cooldown` Zeile 411-432) mit optionalem Per-Trip-Override
  `trip.alert_cooldown_minutes` (`internal/model/trip.go:98`, `0` = kein Limit, `None` = globaler
  Default). Der Scheduler ruft `check_all_trips()` (Kommentar Zeile 298: „Called by scheduler every
  30 minutes") über Cron-Jobs in `internal/scheduler/scheduler.go:92-98` auf: `alertChecks` alle 30
  Min, `radarAlertChecks` bereits alle 15 Min. Für Premium (Mindestabstand 15 Min) reicht die
  vorhandene Cron-Granularität von `radarAlertChecks`; für Free/Standard (Tages-Obergrenze) muss
  zusätzlich ein **persistenter Tageszähler pro Nutzer** eingeführt werden — der bestehende
  Cooldown-Mechanismus kennt nur "Zeit seit letztem Alert", keine "Anzahl heute". Analog zum bereits
  etablierten Muster `THROTTLE_FILE = Path(f"data/users/{user_id}/alert_throttle.json")`
  (`src/services/radar_alert_service.py:76`) und `alert_state.py:36`
  (`Path(f"data/users/{user_id}/alert_state")`) lebt der neue Tageszähler ebenfalls unter
  `data/users/<user_id>/`, z.B. `data/users/<user_id>/alert_daily_count.json` mit `{"date":
  "YYYY-MM-DD", "count": N}` — Read-Modify-Write bei jedem tatsächlich versendeten Alert/Update,
  Reset sobald `date` nicht mehr dem aktuellen Kalendertag entspricht. Zusätzlich muss die
  Cron-Frequenz von `alertChecks` auf 15 Min angehoben werden, damit Premium-Nutzer überhaupt
  öfter als alle 30 Min beliefert werden können.
- **Zeitzonen-Konvention: Europe/Vienna ist bereits etabliert, nicht Europe/Berlin.**
  `internal/config/config.go:20` setzt `SchedulerTimezone` mit `default:"Europe/Vienna"` — das ist
  die Zeitzone, in der der Go-Scheduler bereits alle Cron-Jobs auswertet
  (`internal/scheduler/scheduler.go`, `time.LoadLocation(cfg.SchedulerTimezone)`). Der
  Mitternachts-Reset des Tageszählers verwendet dieselbe, bereits etablierte Zeitzone
  (Europe/Vienna), NICHT Europe/Berlin — beide liegen zwar in derselben Zeitzone
  (CET/CEST), aber es gibt keinen Grund, eine zweite Konvention einzuführen, wenn eine
  projektweite bereits existiert.
- **Der bestehende Per-Trip-Cooldown (`trip.alert_cooldown_minutes`) gilt zusätzlich weiter, das
  strengere Limit gewinnt.** Ein Alert wird nur verschickt, wenn (a) der Per-Trip-Cooldown seit dem
  letzten Alert für diesen Trip abgelaufen ist UND (b) der Tages-Zähler des Nutzers das
  Tier-Limit noch nicht erreicht hat (Free/Standard) bzw. der Tier-Mindestabstand eingehalten ist
  (Premium). Beide Prüfungen sind unabhängig und additiv — keine ersetzt die andere.
- **Kein konkurrierendes Tier/Plan/Subscription-Konzept im Code gefunden.** `subscription.go` /
  `CompareSubscription` (`internal/store/subscription.go:1-16`) sind Orts-Vergleichs-Abos
  (Ziel-Feature #438), inhaltlich unabhängig von Nutzerleveln — Namenskollision "Subscription" ist
  rein zufällig, keine Wiederverwendung sinnvoll.
- **Premium-SMS (Garmin inReach) existiert als Kanal noch nicht.** Bereits als Zukunfts-Feature F9
  dokumentiert (`docs/project/strategic-directions.md:31`, `docs/features/scope.md:41`: „Garmin
  inReach Email-Bridge, geplant Q2 2026, setzt Kompakt-Summary F2 voraus"). Dieser Epic legt nur
  das *Level*-Konzept und den *Slot* für „Premium-SMS" an (als Wert im Datenmodell + gesperrter
  Menüpunkt mit „bald verfügbar"-Hinweis), NICHT die tatsächliche inReach-Anbindung — die bleibt
  ein eigenes Folge-Issue, weil der Kanal selbst noch nicht gebaut ist.
- **Keine Admin-Oberfläche für Nutzerverwaltung vorhanden.** Level-Änderung nach Antrag erfolgt
  manuell durch den PO (direktes Setzen von `tier` im `user.json` bzw. später ein minimales
  Script) — das deckt sich mit der PO-Anforderung „technisch minimal gelöst".

## Vorgeschlagener Schnitt (4 Slices, je klein genug für 1 Workflow-Durchlauf)

1. **Slice 1 — Datenmodell + Anzeige** (`internal/model/user.go`, `internal/handler/auth.go`,
   `frontend/src/routes/account/+page.svelte`, `frontend/src/lib/types.ts`): `Tier`-Feld auf
   `User` (Default „free" wenn leer/fehlend — kein Zwangs-Rewrite bestehender `user.json`-Dateien),
   Ausgabe in `profileResponse`, Badge auf `/account`. ~4 Dateien, ~80-120 LoC.
2. **Slice 2 — Channel-Gating nach Level** (`internal/model/` neue kleine Datei mit
   Tier→Channel-Tabelle, `src/services/trip_report_scheduler.py` (serverseitige Durchsetzung an
   den zwei o.g. Stellen), `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
   (Hinweistext „ab Standard verfügbar" statt „Handynummer fehlt", wenn Grund das Level ist)). ~4
   Dateien, ~150-200 LoC. Premium-SMS-Menüpunkt nur als deaktivierter Slot mit Hinweis, keine
   Funktionslogik.
3. **Slice 3 — Alert-/Update-Frequenz nach Level (Tages-Obergrenze + Mindestabstand)**:
   - Neuer persistenter Tageszähler pro Nutzer (`data/users/<user_id>/alert_daily_count.json`,
     Read-Modify-Write, Reset bei Kalendertag-Wechsel in Europe/Vienna — siehe Befund oben), z.B.
     als kleines neues Modul `src/services/alert_daily_limit.py` (Load/Increment/Check).
   - Tier→Limit-Tabelle: Free = 2/Tag, Standard = 4/Tag, Premium = kein Tageslimit (nur
     Mindestabstand 15 Min, weiterhin über den bestehenden Cooldown-Mechanismus).
   - Verdrahtung in `_is_throttled_with_cooldown` bzw. dem Aufrufpfad in
     `src/services/radar_alert_service.py:411-432` — Alert wird nur verschickt, wenn sowohl der
     bestehende Per-Trip-Cooldown (`trip.alert_cooldown_minutes`) abgelaufen ist ALS AUCH
     (Free/Standard) der Tageszähler das Limit noch nicht erreicht hat; das strengere Kriterium
     gewinnt, keines ersetzt das andere.
   - Anhebung von `alertChecks` in `internal/scheduler/scheduler.go:92-98` auf `*/15 * * * *`,
     damit Premium-Nutzer überhaupt öfter als alle 30 Min beliefert werden können.
   - ~4-5 Dateien, **~180-250 LoC** (nach oben korrigiert gegenüber v1.0: Tageszähler-Persistenz
     mit Kalendertag-Reset ist mehr Aufwand als ein reiner Tier→Cooldown-Deckel-Wert).
   **Bewusst NICHT in Scope:** rückwirkende Migration des generischen Deviation-Watcher-Throttle-
   Pfads (`trip_alert.py`), falls sich beim Implementieren herausstellt, dass dort eine eigene,
   unabhängige Cooldown-Logik existiert statt der geteilten Funktion — dann eigenes Folge-Issue
   statt Slice-Sprengung.
4. **Slice 4 — Level-Änderungs-Antrag (bestätigt, technisch minimal)** (`internal/handler/auth.go`
   neuer Endpoint `POST /api/auth/tier-change-request`, `internal/model/user.go` Felder
   `RequestedTier`/`RequestedAt`, `frontend/src/routes/account/+page.svelte` Formular
   „Level-Wechsel beantragen"). Antrag wird im `user.json` vermerkt (Read-Modify-Write, kein
   Datenverlust) UND löst eine Benachrichtigungsmail über den bestehenden Mail-Versand
   (`internal/mail/sender.go`) an den PO aus. Keine Antragsliste, keine Genehmigungs-UI, keine
   Zahlungsanbindung — Freigabe erfolgt weiterhin manuell durch direktes Setzen von `tier` im
   betroffenen `user.json`. ~3 Dateien, ~100 LoC.

Jeder Slice bleibt unter dem 250-LoC-/4-5-Dateien-Limit (Slice 3 bewegt sich am oberen Rand, siehe
oben). Premium-SMS/inReach-Anbindung selbst ist explizit NICHT Teil dieses Epics (siehe oben) —
eigenes Folge-Issue nach F9-Fahrplan.

## PO-Entscheidungen 2026-07-07 (beantworten die drei offenen Fragen aus v1.0)

1. **Alert-Häufigkeit = harte Tages-Obergrenze** für Free (2/Tag) und Standard (4/Tag), mit
   Mitternachts-Reset in der bereits etablierten Server-Zeitzone Europe/Vienna
   (`internal/config/config.go:20`) — kein reiner Mindestabstand. Premium bleibt Mindestabstand
   15 Minuten ohne Tageslimit. Umgesetzt in Slice 3 (Details siehe oben, inkl. Tageszähler-
   Persistenz und Zusammenspiel mit dem bestehenden Per-Trip-Cooldown: das strengere Limit
   gewinnt, keines ersetzt das andere).
2. **Level-Änderungs-Antrag:** Variante „Vermerk in `user.json` + E-Mail-Benachrichtigung an den
   PO" ist bestätigt. Keine Antragsliste, keine Genehmigungs-UI.
3. **Default-Level:** „free" für neue UND bestehende Nutzer bestätigt (Feld fehlt im `user.json`
   → wird als „free" behandelt, kein Zwangs-Rewrite bestehender Dateien).

## Changelog

- 2026-07-07: Slice 1 (#1068) implementiert und validiert.
- 2026-07-07: Epic-Overview erstellt (Slice-Schnitt, Systemrecherche)
- 2026-07-07: PO-Antworten eingearbeitet — Alert-Frequenz Free/Standard auf harte
  Tages-Obergrenze mit Mitternachts-Reset (Europe/Vienna, bereits etablierte Konvention statt der
  ursprünglich vom PO genannten Europe/Berlin) umgestellt, Tageszähler-Persistenz unter
  `data/users/<user_id>/` spezifiziert, Slice-3-Aufwand nach oben korrigiert (~180-250 statt
  ~100-150 LoC), Level-Änderungs-Antrag und Default-Level bestätigt.
