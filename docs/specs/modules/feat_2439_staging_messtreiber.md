---
entity_id: feat_2439_staging_messtreiber
type: module
created: 2026-10-21
updated: 2026-10-21
status: draft
version: "1.0"
workflow: feat-2439-staging-messtreiber
tags: [tooling, staging, befehle, antwortzeit, e2e-verify, messung, 2439]
---

# Staging-Messtreiber für die Befehls-Antwortzeit-Serien (#2439)

## Approval

- [ ] Approved

## Purpose

Die Live-Tests in `tests/e2e/test_push_eingang_befehle_staging.py` werten nur das Staging-Journal aus und verlangen, dass vorher jemand die Befehlsserien (HELP/CODES/STATUS je Eingang, kalte HEUTE/MORGEN für DE und Korsika, das HEUTE-dann-HELP-Paar) ausgelöst und drei Umgebungswerte (`GZ_STAGING_MESSLAUF_SEIT`, `GZ_STAGING_TRIP_DE`, `GZ_STAGING_TRIP_KORSIKA`) bereitgestellt hat. Diesen Treiber gibt es nicht; ohne ihn bleiben die Zielgrößen aus `feat_2439_befehle_antwortzeit` (AC-3/4/5/12) und `feat_2439_push_eingang_prod_scharf` (AC-12/15) unbelegt und #2439 kann nicht geschlossen werden. Diese Spec liefert ein reines Auslöse-Werkzeug für Staging. Es **wertet nicht selbst aus** — Auswertung und Schwellen bleiben ausschließlich im Test.

## Source

- **Files:**
  - `.claude/tools/staging_messlauf.py` (neu, Kommandozeilenwerkzeug)
  - `.claude/tools/staging_befehl_pruefen.py` (klein ändern: `baue_trip` um Ort parametrisieren)
  - `tests/tdd/test_staging_messlauf.py` (neu, deterministische Kern-Tests)
  - `docs/reference/operations_playbook.md` (Runbook-Abschnitt #2439)
- **Identifier:** `main()` im Werkzeug; Ablauf-Funktionen für Probelauf, Serien, Aufräumen und Startprüfung.
- **Konsument (unverändert):** `tests/e2e/test_push_eingang_befehle_staging.py` (Env-Vertrag Z. 191–197, Schwellen Z. 167–197).

> Schicht-Hinweis: Reine Werkzeug- und Test-Schicht (`.claude/`, `tests/`, Doku). `src/`, `api/`, `internal/`, `frontend/` bleiben unverändert; Deploy-Ausnahme für reine Tooling-Änderungen greift.

## Estimated Scope

- **Files:** 4 (2 CREATE, 1 MODIFY Code, 1 MODIFY Doku)
- **LoC:** Werkzeug ca. +400, Kern-Tests ca. +250, `baue_trip` ca. +20, Runbook (zählt nicht). Gesamt ca. 600–700. **Ankündigung: vor `/50` `workflow.py set-field loc_limit_override 700` setzen** (Limit 250 wäre überschritten).
- **Risk:** MEDIUM — kein Produktcode, aber Live-Lauf gegen Staging (Last, Aufräumen, Kontingent).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/tools/staging_befehl_pruefen.py` (`StagingApi`/`Api`, `baue_trip`, `baue_befehlsmail`, `liefere_ein`, `finde_antwort`, `_fahre_befehl`, `loese_poll_aus`, `http_transport`) | Upstream (wiederverwendet, `baue_trip` klein geändert) | Wegwerf-Nutzer, Trip-Anlage, Mail-Einlieferung Port 25, Antwort per IMAP, Poll-Auslöser |
| Staging-Go-API `127.0.0.1:8091` bzw. öffentliche Staging-URL | Upstream | Registrierung, Trip anlegen/ändern/löschen, `account/delete`. **Port 8090 ist Produktion und wird nie angesprochen.** |
| Staging-Kern Port 8001 + `X-GZ-Core-Auth` | Upstream | Poll sofort auslösen |
| Stalwart Port 25 / IMAP (`GZ_TEST_IMAP_*`) | Upstream | E-Mail-Befehle einliefern, Antworten lesen |
| `/home/hem/gregor_zwanzig_staging/.env` | Upstream | `TELEGRAM_WEBHOOK_SECRET`, `GZ_CORE_SHARED_SECRET`, Zugangsdaten (nie im Klartext ausgeben) |
| Go `internal/handler/telegram_webhook.go`, `api/routers/webhook.py` | Upstream (nur lesen) | Webhook-Eingang mit Header `X-Telegram-Bot-Api-Secret-Token`, Deduplizierung nach `update_id` |
| Go `GetTelegramLinkHandler` und `POST /api/internal/telegram-connect` (nur `127.0.0.1`, `coreAuth`) | Upstream | Verknüpfung der simulierten `chat_id` mit dem Wegwerf-Nutzer; alternativ `/start TOKEN` als simuliertes Update |
| `src/providers/dwd.py`, `src/providers/meteofrance.py`, `thunder_window_cache.py` | Upstream (nur lesen) | Kalt-Marker `dwd_fenster`/`fr_direct_fenster … downloads=N`; Cache-Verhalten bestimmt die Ortswahl bzw. den Abstand |
| `src/services/trip_command_processor.py` | Upstream (nur lesen) | Dauerzeile `befehl=… kanal=… trip=<Trip-ID> dauer_ms=…` |
| `.claude/tools/befehl_messlogik.py` | Downstream-Referenz | Auswertung (nicht im Treiber) |
| `tests/e2e/test_push_eingang_befehle_staging.py`, `/e2e-verify`, Close #2439 | Downstream | Konsumenten |

## Implementation Details

Ein Aufruf des Werkzeugs führt die komplette Messung seriell aus. Es nutzt genau **einen** Wegwerf-Nutzer `gzp-<tag>` und genau **zwei** Trips (DE, Korsika; Kontingent 2 von 3).

1. **Startprüfung:** Ortszeit Europe/Vienna darf nicht in 23:45–00:15 liegen; die geschätzte Laufzeit (ca. 2–2,5 h) darf keinen Tageswechsel überspannen. Sonst Abbruch Exit 2 vor jeder Änderung.
2. **Anlage:** Nutzer registrieren und verifizieren, Trip DE und Trip Korsika anlegen (`baue_trip` mit Ortsparameter, Default unverändert).
3. **Probelauf (vor der Serie):** je 1× HEUTE und MORGEN DE sowie 1× Korsika; danach Journal auf `downloads>0` prüfen. Bleibt ein Lauf warm, Abbruch mit Befund, Exit 1, keine Serie.
4. **E-Mail-Kurzbefehle:** je 5× HELP, CODES, STATUS.
5. **Telegram-Kurzbefehle:** simulierte Webhook-Updates (Secret-Header aus Staging-`.env`) mit erkennbar ungültiger, eindeutiger `chat_id` (kein Wert, der einen echten Kontakt treffen kann) und eindeutigen `update_id`s; zuvor Verknüpfung der `chat_id` mit dem Wegwerf-Nutzer. 5× HELP, CODES, STATUS.
6. **Kälte DE (Variante A):** ein Trip; vor jedem Lauf wird per Read-Modify-Write (Trip laden, nur Etappen-Orte für heute und morgen ändern, speichern) auf einen neuen Ort gesetzt. 10 Orte aus einer festen Liste, paarweise mindestens 120 km Abstand, alle im DWD-Fenstergebiet. 5× HEUTE + 5× MORGEN, alle per E-Mail.
7. **Korsika (Variante E):** gleicher Trip, Abstand zwischen den Läufen mehr als 600 s (Météo-France-Cache TTL 600 s, 2°-Kachel). 3× HEUTE + 3× MORGEN, ca. 70 min.
8. **AC-12-Paar:** HEUTE per E-Mail einliefern und, solange HEUTE noch läuft, HELP per E-Mail nachschieben (nicht auf die HEUTE-Antwort warten).
9. **Ausgabe:** drei Zeilen `GZ_STAGING_MESSLAUF_SEIT=<ISO-UTC>`, `GZ_STAGING_TRIP_DE=<Trip-ID>`, `GZ_STAGING_TRIP_KORSIKA=<Trip-ID>`, sofort verwendbar per `export`/`eval`.
10. **`finally`:** beide Trips und Wegwerf-Nutzer löschen, auch bei Abbruch; bleibt etwas stehen, Befund mit Kennung ausgeben (nie still). Der bestehende Prüfweg löscht Trips nicht im `finally`; das wird hier korrigiert.

Der Treiber zählt, wertet und urteilt nicht. Er liefert die Ereignisse im Journal und die Env-Werte.

## Messvorbehalt Telegram

Gemessen wird bei Telegram die **Verarbeitung** (Webhook-Eingang bis Dauerzeile) und der **schnelle Sendefehler** der Antwort an die erkennbar ungültige `chat_id` (Fehler werden in `notification_service.py` verschluckt), **nicht** eine echte Zustellung an ein Telegram-Konto. Die Dauerzeile entsteht dennoch, weil Verarbeitung und Messung vor dem Versand liegen. Das gehört in das Runbook und in den Issue-Beleg. Telegram HEUTE/MORGEN bleibt auf Staging NOT_MEASURABLE (Spec `push_eingang_prod_scharf` §9) und wird nicht ausgelöst.

## Bekannte Risiken und Spikes

- **Telegram-Verknüpfung** (Link-Token plus `telegram-connect` auf `127.0.0.1:8091` bzw. `/start TOKEN`) ist nur aus dem Code gelesen. Spike in `/50`. **Folge bei Scheitern:** der Treiber meldet einen ehrlichen Befund (AC-3 Telegram bleibt mit Begründung offen, Exit 1), lässt die Telegram-Serie nie still weg und färbt das Ergebnis nicht schön.
- **Kälte HEUTE/MORGEN:** Ob die MORGEN-Etappe eigene Downloads auslöst und ob sich Zeitschritte mit HEUTE überschneiden, ist unverifiziert. Der Probelauf ist Pflicht. **Folge bei Scheitern:** Abbruch Exit 1; AC-4 bleibt unbelegt, Ortsliste/Abstand wird in einem Folge-Schritt angepasst.
- **Fremdlast auf Staging** kann Orte ungewollt wärmen: Orte abseits der Staging-Test-Trips wählen; der Probelauf zeigt es.
- **DWD-Last:** rund 415 Dateien je kaltem Lauf, deshalb strikt seriell.
- **Neustart `gregor-python-staging`** ist für `hem` nicht erlaubt; Kälte entsteht nur über neue Orte bzw. Abstand.

## Acceptance Criteria

**AC-1:** Given ein Messlauf startet und der Probelauf (je 1× HEUTE/MORGEN DE, 1× Korsika) wird ausgeführt, When das Journal für mindestens einen dieser Läufe kein `downloads>0` (also warm) zeigt, Then bricht der Treiber mit Befund und Exit 1 ab, löst keine der Serien aus und räumt auf. _[Probelauf]_

**AC-2:** Given ein DE-Trip mit weiteren, dem Treiber unbekannten Feldern, When der Treiber vor jedem der 10 DE-Läufe (5× HEUTE, 5× MORGEN) die Etappen-Orte für heute und morgen auf einen neuen Ort aus der Ortsliste setzt, Then geschieht das per Read-Modify-Write (geladen, nur Orte geändert, gespeichert), kein anderes Trip-Feld geht verloren, und je zwei Läufe nutzen Orte mit mindestens 120 km Abstand. _[Kälte DE per Ortswechsel]_

**AC-3:** Given der Korsika-Trip, When der Treiber 3× HEUTE und 3× MORGEN auslöst, Then liegen zwischen aufeinanderfolgenden Läufen mehr als 600 Sekunden (Météo-France-Cache-TTL), und die Wartezeit ist über eine injizierbare Uhr prüfbar. _[Korsika-Abstand]_

**AC-4:** Given der Wegwerf-Nutzer mit verifizierter Plus-Adresse, When der Treiber die E-Mail-Serie fährt, Then werden HELP, CODES und STATUS je genau 5-mal über den echten Port-25-Weg an `gregor-staging@henemm.com` eingeliefert und die Antwort jeweils abgewartet, bevor der nächste Befehl folgt. _[E-Mail-Kurzbefehle]_

**AC-5:** Given eine erkennbar ungültige, eindeutige `chat_id` (nicht in der Wertemenge echter Kontakte) und für jedes Update eine eindeutige `update_id`, When der Treiber die Telegram-Serie fährt, Then postet er HELP, CODES und STATUS je 5-mal als simulierte Webhook-Updates mit dem Secret-Header aus der Staging-`.env`, und keine `update_id` wiederholt sich (kein Dedup-Treffer). _[Telegram-Kurzbefehle]_

**AC-6:** Given die `chat_id` muss mit dem Wegwerf-Nutzer verknüpft werden, When die Verknüpfung scheitert, Then endet der Lauf mit einem ausdrücklichen Befund „Telegram nicht verknüpfbar" und Exit 1; die Telegram-Serie wird nie still weggelassen und der Lauf nie als vollständig gemeldet. _[Telegram-Verknüpfung ehrlich]_

**AC-7:** Given ein per E-Mail eingeliefertes HEUTE, das noch läuft, When der Treiber das HELP-Paar auslöst, Then wird die HELP-Mail eingeliefert, bevor die HEUTE-Antwort vorliegt, über denselben Kanal E-Mail, und beide Zeitpunkte sind für den Test im Journal erkennbar. _[AC-12-Paar]_

**AC-8:** Given beliebig viele geplante Befehle, When der Treiber sie ausführt, Then läuft zu jedem Zeitpunkt höchstens ein Befehl gleichzeitig (Ausnahme: das bewusst überlappende HELP aus AC-7), und der Poll-Auslöser wird nie parallel gestartet. _[seriell]_

**AC-9:** Given ein erfolgreicher Lauf, When der Treiber endet, Then gibt er auf stdout genau die drei Zeilen `GZ_STAGING_MESSLAUF_SEIT=<ISO-8601-UTC>`, `GZ_STAGING_TRIP_DE=<Trip-ID>` und `GZ_STAGING_TRIP_KORSIKA=<Trip-ID>` aus, wobei die Trip-IDs genau die sind, die in der Dauerzeile (`trip=`) erscheinen, und die Startzeit vor dem ersten ausgelösten Befehl liegt. _[Env-Ausgabe]_

**AC-10:** Given der Lauf bricht ab (Probelauf-Befund, Fehler, Unterbrechung), When der Treiber beendet, Then sind beide Trips und der Wegwerf-Nutzer gelöscht; scheitert das Löschen, steht ein Befund mit Nutzer-Kennung in der Ausgabe und der Exit-Code ist nicht 0. _[Aufräumen im finally]_

**AC-11:** Given die Ortszeit Europe/Vienna liegt zwischen 23:45 und 00:15 oder die geschätzte Laufzeit überspannt einen Tageswechsel, When der Treiber startet, Then bricht er vor jeder Änderung an Staging mit Exit 2 und klarer Meldung ab. _[Startprüfung Zeitfenster]_

**AC-12:** Given die drei Ausgänge eines Laufs, When er endet, Then bedeutet Exit 0 vollständig ausgelöst, Exit 1 ein Befund (z. B. Probelauf warm, Telegram nicht verknüpfbar), Exit 2 ein Umgebungsfehler (fehlende Env, Staging nicht erreichbar, Zeitfenster-Sperre). _[Exit-Codes]_

**AC-13:** Given beliebige Konfiguration oder Umgebungswerte, When der Treiber eine API-Adresse bestimmt, Then lehnt er Port 8090 und jede Produktions-Adresse (`gregor20.henemm.com` ohne `staging.`) mit Exit 2 ab, bevor irgendeine Anfrage abgeht. _[niemals Produktion]_

**AC-14:** Given das Trip-Kontingent von 3 je Nutzer, When der Treiber die Trips anlegt, Then legt er genau 2 Trips an (DE und Korsika) und nie mehr, auch nicht in Wiederholungen. _[Kontingent]_

**AC-15:** Given auf Staging existieren Trips anderer Nutzer, When der Treiber Poll und Befehle auslöst, Then wirken alle Befehle ausschließlich auf die eigenen zwei Trips des Wegwerf-Nutzers; es gibt keinen Sammel-Versand und keinen Zugriff auf fremde Trips. _[kein Sammelversand]_

**AC-16:** Given ein beendeter Lauf, When der Test `test_push_eingang_befehle_staging.py` mit den ausgegebenen Env-Werten startet, Then trifft er seine Schwellen-Entscheidung allein aus dem Journal; der Treiber enthält keine Schwellenwerte (30 s / 60 s / 45 s) und keine Pass/Fail-Aussage zur Antwortzeit. _[Treiber wertet nicht aus]_

## Test Plan

### Automated Tests (TDD RED)

Alle Kern-Tests in `tests/tdd/test_staging_messlauf.py`: deterministisch, ohne Netz, mit Ersatzklassen und Fabriken (`smtp_factory`, `imap_factory`, `transport`, Uhr) statt `Mock()`/`patch`. Der Live-Lauf findet ausschließlich in `/e2e-verify` statt.

- [ ] Test AC-1: GIVEN eine Ersatz-Journalquelle mit einem warmen Probelauf WHEN der Ablauf läuft THEN Exit 1, keine Serien-Einlieferung, Aufräumen aufgerufen.
- [ ] Test AC-2: GIVEN ein Ersatz-Trip-Speicher mit Zusatzfeldern WHEN 10 Ortswechsel laufen THEN bleiben alle Zusatzfelder erhalten, nur Orte ändern sich, Orte-Abstand mindestens 120 km.
- [ ] Test AC-3: GIVEN eine Ersatz-Uhr WHEN die Korsika-Serie läuft THEN liegt jeder Abstand über 600 s.
- [ ] Test AC-4: GIVEN eine Ersatz-Einlieferung WHEN die E-Mail-Serie läuft THEN je Befehl genau 5 Einlieferungen, jeweils nach der Antwort des Vorgängers.
- [ ] Test AC-5: GIVEN ein Ersatz-Webhook-Transport WHEN die Telegram-Serie läuft THEN 15 Updates mit Secret-Header, erkennbar ungültiger `chat_id`, paarweise verschiedenen `update_id`s.
- [ ] Test AC-6: GIVEN eine scheiternde Verknüpfung WHEN der Ablauf läuft THEN Befund „Telegram nicht verknüpfbar", Exit 1, Serie nicht still ausgelassen.
- [ ] Test AC-7: GIVEN Ersatz-Uhr und -Einlieferung WHEN das Paar läuft THEN HELP eingeliefert, bevor die HEUTE-Antwort vorliegt, beide über E-Mail.
- [ ] Test AC-8: GIVEN eine Ersatz-Einlieferung, die Überlappung zählt WHEN alle Serien laufen THEN höchstens 1 gleichzeitiger Befehl außerhalb des AC-7-Paars.
- [ ] Test AC-9: GIVEN ein erfolgreicher Ersatz-Lauf WHEN er endet THEN stdout enthält genau die drei Env-Zeilen, Startzeit ISO-UTC vor dem ersten Befehl, Trip-IDs wie angelegt.
- [ ] Test AC-10: GIVEN Abbruch an jeder Stufe WHEN der Ablauf endet THEN Trips und Nutzer gelöscht; gescheitertes Löschen liefert Befund und Exit ungleich 0.
- [ ] Test AC-11: GIVEN Ersatz-Uhren um 23:50, 00:10 und 22:30 WHEN die Startprüfung läuft THEN Exit 2 bei den ersten beiden, Start erlaubt nur bei der dritten bei Laufzeitfenster ohne Tageswechsel.
- [ ] Test AC-12: GIVEN je ein Szenario Erfolg, Befund, Umgebungsfehler WHEN `main()` endet THEN Exit 0, 1, 2.
- [ ] Test AC-13: GIVEN Basis-URLs mit Port 8090 und Produktions-Host WHEN der Treiber startet THEN Exit 2 ohne Anfrage.
- [ ] Test AC-14: GIVEN ein Ersatz-Trip-Speicher WHEN ein kompletter Lauf endet THEN genau 2 Trip-Anlagen.
- [ ] Test AC-15: GIVEN Ersatz-Speicher mit fremden Trips WHEN der Lauf endet THEN keine Anfrage berührt fremde Trip-IDs.
- [ ] Test AC-16: GIVEN der Quelltext-freie Verhaltenstest WHEN ein Lauf endet THEN enthält die Ausgabe keine Schwellen- oder Urteilsaussage zur Antwortzeit.
- [ ] Test Rückwärtskompatibilität: GIVEN `baue_trip` ohne Ortsargument WHEN aufgerufen THEN identisches Ergebnis wie vor der Änderung (Koordinaten 47.10/11.00); bestehende `tests/tdd/test_staging_befehl_pruefweg*.py` bleiben grün.

### Live-Nachweis

Nur in `/e2e-verify`: Treiber gegen Staging laufen lassen, Env-Werte exportieren, `GZ_STAGING_E2E=1 uv run pytest tests/e2e/test_push_eingang_befehle_staging.py` mit benannter Datei; das Ergebnis steht als Beleg im Issue #2439.

## Out of Scope

- Auswertung der Antwortzeiten und Schwellen (bleibt im Test und in `befehl_messlogik.py`).
- Änderungen an `src/`, `api/`, `internal/`, `frontend/`; Neustart von `gregor-python-staging`.
- Echte Telegram-Zustellung und Telegram HEUTE/MORGEN auf Staging.
- Messung auf Produktion (Prod-Lese-Werkzeug `befehl_antwortzeit.py` bleibt separat).

## Known Limitations

- Telegram wird nur bis zur Verarbeitung und zum schnellen Sendefehler gemessen (Abschnitt Messvorbehalt).
- Laufzeit 2–2,5 h; Fremdlast auf Staging kann Orte wärmen (Probelauf deckt es auf).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — reines Staging-Messwerkzeug unter `.claude/tools/`; berührt keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Test-/Deploy-Strategie).

## Changelog

- 2026-10-21: Initial spec created (Staging-Messtreiber, #2439)
