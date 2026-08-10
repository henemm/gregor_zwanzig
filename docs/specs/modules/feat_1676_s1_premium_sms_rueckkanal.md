---
entity_id: feat_1676_s1_premium_sms_rueckkanal
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.3"
tags: [sms, inbound, premium, garmin, seven-io, dual-stack]
---

<!-- Issue #1676 (Scheibe S1) -- Premium-SMS Rueckkanal: Inbound-Polling und
     gelernte Garmin-Rueckadresse. Verwandt: #735 (SMS-Inbound, offen),
     #1533 (Generalprobe auf dem Geraet, offen). -->

# Premium-SMS Rückkanal — S1: Inbound-Polling und gelernte Garmin-Rückadresse

## Approval

- [ ] Approved

## Purpose

Premium-SMS an den Garmin inReach braucht einen Rückkanal: Das Gerät antwortet
über eine von Garmin **je Gespräch neu vergebene** Rufnummer, nicht über die
gemietete Dienst-Nummer `4916092172595`. Diese Scheibe holt eingehende SMS aus
dem seven.io-Journal ab, erkennt darunter die Garmin-Nachrichten anhand des
Kennzeichens `inreachlink.com` und speichert die aktuellste erkannte
Rückadresse pro Premium-Nutzer mit Zeitstempel. **Nur** Empfangen, Erkennen,
Lernen, Speichern — keine Befehlsausführung, keine Bestätigungs-SMS, kein
Frontend (folgt in S2/S3).

## Source

- **File:** `src/services/inbound_sms_reader.py` (NEU, ~135 LoC) — `InboundSmsReader.poll_and_process(settings) -> int`, Python-Core, Vorbild `src/services/inbound_email_reader.py:37-92`
- **File:** `api/routers/scheduler.py` (MODIFY, +~15 LoC) — neuer globaler Trigger-Endpoint `POST /api/scheduler/inbound-sms`, neben `trigger_inbound()` (Zeile 110-124)
- **File:** `internal/scheduler/scheduler.go` (MODIFY, +~10 LoC) — neuer Cron-Eintrag `*/5 * * * *` analog `inboundCommands()` (Zeile 379-383), `s.recordRun("premium_sms_poll", ...)`
- **File:** `internal/model/user.go` (MODIFY, +4 LoC) — zwei neue optionale Felder neben Zeile 17-18
- **File:** `internal/handler/premium_sms_connect.go` (NEU, ~100 LoC) — localhost-only Schreib-Endpoint mit Dry-Run-Zweig, Vorbild `internal/handler/telegram_connect.go:169-209`
- **File:** `internal/router/router.go` (MODIFY, +1 Zeile) — Routing-Eintrag für den neuen Endpoint

## Estimated Scope

- **LoC (Produktivcode):** ~265 (6 Dateien) — gegenüber der ursprünglichen Schätzung (~220) gestiegen durch AC-10 (Trockenlauf-Schalter, s.u.), der sowohl den Python-Reader als auch den Go-Endpoint um einen zusätzlichen Zweig erweitert.
- **LoC (Tests):** zusätzlich ~280-320 über zwei neue Testdateien (siehe Test Coverage), inklusive der neuen Dry-Run-Tests.
- **Gate-Warnung:** Produktivcode allein liegt bereits nahe am 250-LoC-Gate-Limit pro Workflow, zusammen mit Tests deutlich darüber (das Limit zählt Tests mit). Der Developer-Agent braucht in der Implementierungsphase mit hoher Wahrscheinlichkeit `workflow.py set-field loc_limit_override 500` (nur mit PO-Erlaubnis, siehe `[[feedback_no_loc_override_without_permission]]`) oder muss die Go-Handler-Tests straffen. Ausdrücklich benannt, nicht verschwiegen.
- **Files:** 6 Produktivdateien (5 MODIFY, 2 NEU) + 2 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/inbound_email_reader.py` | Vorbild | `poll_and_process(settings) -> int`-Muster, Struktur der Poll-Schleife |
| `src/app/config.py::Settings` | module | `seven_api_key`, `seven_sandbox_key`, `is_test_mode` — bestehende Felder, keine neuen nötig |
| `src/app/origin_guard.py::classify_origin` | module | Herkunftsklassifikation (production/staging/test); **wird importiert, NICHT verändert** (s. Implementation Details) |
| `src/app/loader.py::get_data_root` | module | Pfadbasis für den Dedup-Zeiger unter `diagnostics/` |
| `src/app/egress_guard.py` | module | `gateway.seven.io` bereits als `TEST_ACCESS` inventarisiert (Zeile 52) — kein neuer Eintrag nötig |
| `internal/model/tier.go::EffectiveTier` | module | Premium-Kandidaten-Filter, serverseitige zweite Verteidigungslinie (R3) |
| `internal/store/store.go::ListUserIDs/LoadUser/SaveUser` | module | Nutzer-Iteration + Read-Modify-Write mit Merge (Go bleibt einziger Schreiber von `user.json`) |
| `internal/handler/telegram_connect.go` | Vorbild | localhost-only-Sperre, Handler-Aufbau |
| `GZ_SKIP_FRONTEND_BROWSER_GATE` (Konvention, `staging_gate.py`) | Vorbild | lauter, exakter Env-Var-Schalter mit stderr-Meldung — Muster für `GZ_PREMIUM_SMS_POLL_DRYRUN` |
| `docs/adr/0015-dual-stack-zielarchitektur.md` | ADR | Zuständigkeitsgrenze Python-Core (Fachlogik, Polling) vs. Go-API (Persistenz, `user.json`) |

## Implementation Details

### Ablauf (Python-Core: `InboundSmsReader.poll_and_process`)

```
1. origin = running_origin(). origin=="production" -> dry_run=False, weiter.
   origin!="production" und ENV GZ_PREMIUM_SMS_POLL_DRYRUN!="1" -> return 0,
   WARN, kein HTTP-Call (AC-7 unveraendert). origin!="production" und =="1"
   -> lauter stderr-Hinweis (Vorbild GZ_SKIP_FRONTEND_BROWSER_GATE),
   dry_run=True, weiter (AC-10: Abruf findet statt, Schreiben bleibt zu).
2. seven_api_key fehlt -> return 0.
3. last_seen_id aus diagnostics/premium_sms_inbound.json laden (Default 0).
4. GET journal/inbound?limit=100, Header X-Api-Key (kein date_from, s.u.).
5. Fehler (HTTP/Netzwerk) -> loggen, return 0, last_seen_id unveraendert.
6. Nachrichten mit id > last_seen_id aufsteigend sortieren (aeltest zuerst).
7. Je Nachricht ohne Garmin-Kennzeichen: last_seen_id-Kandidat auf
   max(bisher, msg.id) anheben (sonst Dauer-Reevaluation). Fuer eine
   Nachricht MIT Kennzeichen entscheidet Schritt 9 ueber das Anheben --
   NICHT mehr bedingungslos (Fix F001, v1.2, s.u.).
8. Kein "inreachlink.com" im Text -> ignorieren, naechste Nachricht (R1).
9. "inreachlink.com" im Text -> POST premium-sms-learn {"from": msg.from,
   "dry_run": dry_run}, 5s Timeout.
   - HTTP 200: last_seen_id-Kandidat anheben. dry_run=False -> Zaehler
     "gelernt" +1. dry_run=True -> kein Zaehler (kein echter Lernvorgang),
     Ergebnis nur geloggt (maskierte Nummer aus der Antwort).
   - HTTP 4xx (bewusste Ablehnung, insbesondere 409-Mehrdeutigkeit AC-5):
     last_seen_id-Kandidat TROTZDEM anheben -- abschliessende Entscheidung,
     kein Wiederholungsgrund. WARN-Log, kein Zaehler.
   - Netzwerkfehler/Exception ODER HTTP 5xx (VORUEBERGEHEND): Zaehler
     "fehlgeschlagen" +1, WARN-Log, **Schleife abbrechen** -- der
     last_seen_id-Kandidat bleibt VOR dieser (und allen im aktuellen
     Journal-Fenster nachfolgenden) Nachricht(en) stehen (Fix F001, v1.2).
10. last_seen_id atomar schreiben (tempfile + os.rename) -- auf dem Stand
    NACH Schritt 9, also ggf. vor der zuletzt abgebrochenen Nachricht.
11. Rueckgabe: Anzahl in diesem Lauf ECHT gelernter Rueckadressen -- im
    Dry-Run strukturell immer 0, weil dry_run=True nie einen Zaehler-Hit
    ausloest (Schritt 9). Die Anzahl vorruebergehend fehlgeschlagener
    Lernaufrufe steht danach im Instanzfeld `last_failed_count` (Fix F001,
    v1.2) -- der Trigger-Endpunkt (`api/routers/scheduler.py`) leitet seinen
    `status`-Feldwert daraus ab (Hausnorm `dispatch_orchestrator.run_briefing_dispatch`),
    statt bedingungslos "ok" zu melden. HTTP bleibt dabei 200 -- Hausnorm der
    Nachbar-Endpunkte `trigger_trip_reports`/`trigger_compare_presets_daily`
    (Issue #766/#1290), die denselben `status: "partial"`-bei-HTTP-200-Vertrag
    verwenden; ein Fehlerstatuscode waere eine falsche Aussage ueber die
    HTTP-Ebene. Die Sichtbarkeit fuer den Zeitplaner entsteht stattdessen auf
    der GO-Seite (Fix F002, v1.3): `internal/scheduler/scheduler.go::premiumSmsPoll()`
    ruft den Endpunkt NICHT mehr ueber das generische `triggerGlobalEndpoint()`
    auf, sondern ueber ein lokales `triggerPremiumSmsPollEndpoint()`, das den
    Antwortkoerper auswertet (wie `triggerEndpointForUser()` es fuer die
    Nutzer-Fan-out-Jobs bereits tut): `failed > 0` bzw. `status == "partial"`
    liefert einen Fehler an `recordRun()`, der DAUERHAFTE Fehlschlaege (im
    Unterschied zu voruebergehenden, die sich durch Fix F001 im naechsten Lauf
    von selbst heilen) in `/api/scheduler/status` sichtbar macht.
    `triggerGlobalEndpoint()` selbst bleibt unveraendert -- daran haengen
    `inbound_command_poll` und weitere Jobs, die dieses Verhalten nicht
    wollen (dieselbe Luecke dort ist ein separater, hier NICHT behobener
    Nebenbefund).
```

**Fix F001 (v1.2, Adversary-Fund #1676 S1):** Version 1.1 hob den
last_seen_id-Kandidaten in Schritt 7 IMMER an, auch fuer eine erkannte
Garmin-Nachricht, deren Lernaufruf fehlschlug — dann wanderte der Zeiger
ueber die Nachricht hinweg und sie wurde nie wieder betrachtet. Da sich das
Garmin-Geraet im Wesentlichen EINMAL pro Tour meldet, macht ein Fehlschlag
in genau diesem 5-Minuten-Fenster (z.B. ein Deploy-Neustart der Go-API) die
Rueckadresse DAUERHAFT verloren, ohne dass irgendwo eine Fehlermeldung
entsteht (`trigger_inbound_sms()` antwortete bedingungslos `{"status": "ok"}`).
Die Korrektur unterscheidet VORUEBERGEHENDE Fehlschlaege (Netzwerk/Timeout/5xx
— Zeiger bleibt stehen, naechster Lauf versucht dieselbe Nachricht erneut)
von BEWUSSTEN Ablehnungen (HTTP 4xx, insbesondere die 409-Mehrdeutigkeit aus
AC-5 — abschliessende Entscheidung, Zeiger wandert weiter, sonst warnt das
System alle 5 Minuten ueber etwas, das sich von selbst nicht aendert). Die
ACs bleiben woertlich unveraendert; betroffen ist ausschliesslich das interne
Ablaufdetail in Schritt 7/9/11 und der Trigger-Endpoint.

Schritt 1 kennt — anders als `sms.py`s Sandbox-Guard — keinen
Sandbox-Key-Sonderfall: der Journal-**Lesepfad** ist gemessen NICHT isoliert
(Sandbox-Key liefert dasselbe Journal wie der Prod-Key), es gibt also keinen
sicheren Ersatzschlüssel wie beim Senden. Der Dry-Run-Zweig öffnet deshalb
NUR das Lesen (Journal-Abruf + R1-Erkennung + simulierte R3-Auflösung),
niemals das Schreiben — s. AC-10 und den Go-Endpoint unten. Schritt 4
verzichtet bewusst auf `date_from`, weil dessen Antwortformat in den
gemessenen Daten nicht geprüft ist; die Antwortgröße wird ausschließlich
über `limit` begrenzt, Dedup läuft vollständig über die id-Zeigerdatei.
Schritt 6 macht keinen Unterschied zwischen Erstlauf (`last_seen_id=0`) und
Folgelauf — R2 gilt für beide identisch. Weil Nachrichten aufsteigend
abgearbeitet werden und jeder reale (`dry_run=False`) Aufruf von
`premium-sms-learn` den zuvor gespeicherten Wert vollständig überschreibt
(Go-Endpoint, s.u.), gewinnt automatisch die zeitlich letzte als Garmin
erkannte Nachricht — R2 braucht keine eigene Vergleichslogik im
Python-Reader.

### Herkunftssperre: lokale Tiefe-2-Variante statt Änderung an `origin_guard.py`

`origin_guard.running_origin()` geht fest von der Tiefe eines
Kanal-Moduls unter `src/output/channels/<datei>.py` aus (`parents[3]`,
Kommentar in `origin_guard.py:25-27`). `src/services/inbound_sms_reader.py`
liegt eine Ebene höher (`src/services/<datei>.py`, `parents[2]`). Um den
bestehenden, sicherheitsrelevanten Vertrag für die drei existierenden
Aufrufer (SMS/Telegram/Mail-Kanäle) unangetastet zu lassen, importiert der
neue Reader nur die tiefen-unabhängige `classify_origin(root)` und bildet
die Wurzel lokal:

```python
from app.origin_guard import classify_origin

def _origin() -> str:
    root = Path(__file__).resolve().parents[2]  # services/src/<wurzel>
    return classify_origin(root)
```

`origin_guard.py` selbst wird **nicht verändert** — Ausweg, der in der
Estimated-Scope-Zählung (6 statt 7 Dateien) bereits berücksichtigt ist.

### Go: neuer Endpoint `POST /api/internal/premium-sms-learn`

Request: `{"from": "<Absendernummer>", "dry_run": <bool, optional>}`.
Localhost-only-Sperre identisch zu `telegram_connect.go:174-178`.

```
1. remoteHost nicht 127.0.0.1/::1 -> 403. body.From leer -> 400.
2. Alle Nutzer laden (ListUserIDs + LoadUser), Kandidatenmenge = Nutzer mit
   model.EffectiveTier(user.Tier) == "premium" (zweite Verteidigungslinie).
3. Unter den Kandidaten: existiert einer mit user.PremiumSmsReplyTo ==
   body.From -> das ist der Treffer (R3, gespeicherte Adresse gewinnt).
4. Sonst: Kandidatenmenge hat GENAU 1 Eintrag -> das ist der Treffer.
   Sonst (0 oder >1 ohne Treffer aus Schritt 3) -> kein Treffer.
5. body.DryRun == true -> der SaveUser-Aufruf wird strukturell NIE erreicht
   (eigener Code-Zweig, keine Bedingung die scheitern könnte). Treffer ->
   200 {"status":"dry_run","outcome":"would_learn","user_id":...,
   "masked_from":"...xyz"}. Kein Treffer -> 200 {"status":"dry_run",
   "outcome":"would_skip","reason":"no_unique_premium_candidate"}.
6. body.DryRun == false, kein Treffer -> 409 {"status":"skipped",
   "reason":"no_unique_premium_candidate"}, nichts geschrieben, kein
   Fallback auf "default".
7. body.DryRun == false, Treffer -> Read-Modify-Write mit Merge:
   PremiumSmsReplyTo = body.From, PremiumSmsReplyAt = &now (s. Known
   Limitations), SaveUser(*user). 200, {"status":"ok","user_id":user.ID}.
```

Die Dry-Run-Sperre in Schritt 5 ist rein strukturell (kein `if`, das
umgangen werden könnte, sondern ein eigener Rückgabepfad, der vor dem
`SaveUser`-Aufruf endet) — das gilt unabhängig davon, ob der Go-Prozess
selbst auf Produktion oder Staging läuft. `dry_run=true` wird ausschließlich
von einem nicht-produktiven Python-Core gesendet (Schritt 1 oben); ein
produktiver Python-Core sendet ihn nie.

### `internal/model/user.go` — neue Felder

```go
PremiumSmsReplyTo string     `json:"premium_sms_reply_to,omitempty"`
PremiumSmsReplyAt *time.Time `json:"premium_sms_reply_at,omitempty"`
```

Pointer bei `PremiumSmsReplyAt` aus demselben Grund wie `RequestedAt`/
`EmailVerifiedAt` (Zeile 27/32) — `omitempty` greift bei `time.Time`-Structs
nicht. Keine Migration nötig (neue Felder, alte `user.json`-Dateien laden
unverändert mit leerem Wert).

### Dedup-Zeiger

`get_data_root()/diagnostics/premium_sms_inbound.json`:

```json
{"last_seen_id": 4711}
```

Analog `forecast_budget.py:44-50` (Verzeichnis `diagnostics/` unter
`get_data_root()`, NICHT `data/last_sms_id.txt` wie im veralteten
Vorlagecode). Fail-open beim Lesen (kaputte/fehlende Datei -> 0), atomarer
Write beim Schreiben. Der Zeiger wird auch im Dry-Run fortgeschrieben —
er ist globaler Diagnose-State, kein Nutzerdatensatz, und verhindert, dass
derselbe Dry-Run jeden Poll dieselben Nachrichten erneut protokolliert.

## Expected Behavior

- **Input:** seven.io-Journal (`GET journal/inbound`), gepollt alle 5 Minuten via Go-Cron
- **Output:** bei mindestens einer neuen, als Garmin erkannten Nachricht: aktualisierte `premium_sms_reply_to`/`premium_sms_reply_at`-Felder in genau einem `data/users/<uid>/user.json` — **nur in Produktion**; außerhalb Produktion mit `GZ_PREMIUM_SMS_POLL_DRYRUN=1` stattdessen ausschließlich ein Log-Eintrag mit maskierter Nummer
- **Side effects:** Dedup-Zeigerdatei wird bei jedem Lauf mit neuen Journal-Einträgen aktualisiert (Produktion wie Dry-Run); `/api/scheduler/status` zeigt `last_run` für `premium_sms_poll`

## Acceptance Criteria

- **AC-1:** Given eine bislang unbekannte Nummer schickt eine SMS mit dem Text `"... inreachlink.com/g-0Xy... (Koordinaten)"` an die Dienst-Nummer, und genau ein Nutzer hat Tier `premium` / When der Poll läuft / Then steht danach `premium_sms_reply_to` dieses Nutzers auf der Absendernummer und `premium_sms_reply_at` ist gesetzt — geprüft am tatsächlich persistierten `user.json`, nicht an einer Zwischengröße.
  - Test: `poll_and_process()` gegen eine aufgezeichnete Journal-Fixture mit erfundener Nummer laufen lassen, danach den gespeicherten Nutzerdatensatz lesen.

- **AC-2:** Given eine eingehende SMS enthält NICHT das Kennzeichen `inreachlink.com` (z.B. eine private SMS an dieselbe Dienst-Nummer) / When der Poll läuft / Then bleibt `premium_sms_reply_to` in jedem Nutzerdatensatz unverändert — weder neu gesetzt noch überschrieben.
  - Test: Fixture ohne Kennzeichen, danach `user.json` vor/nach vergleichen — muss identisch sein.

- **AC-3:** Given ein Nutzer hat bereits eine gespeicherte `premium_sms_reply_to` von einer früheren Garmin-Session / When eine neue, als Garmin erkannte Nachricht von einer ANDEREN Nummer eintrifft / Then überschreibt die neue Nummer den alten Wert vollständig, inklusive aktualisiertem `premium_sms_reply_at` — auch wenn der alte Wert "neuer aussieht" als das Speicherdatum, gewinnt die inhaltlich neueste Garmin-Nachricht.
  - Test: Zwei Fixture-Läufe nacheinander mit unterschiedlichen erfundenen Absendernummern, jeweils mit Kennzeichen; nach Lauf 2 muss der Wert aus Lauf 2 stehen.

- **AC-4:** Given genau ein Nutzer mit Tier `premium` existiert (kein gespeicherter Treffer für den Absender) / When eine als Garmin erkannte Nachricht eintrifft / Then wird sie diesem einen Nutzer zugeordnet, kein anderer Nutzer wird verändert.
  - Test: Fixture mit zwei Nutzern (einer `free`, einer `premium`) im Store, Endpoint aufrufen, nur den `premium`-Nutzer als verändert prüfen.

- **AC-5:** Given es existieren zwei Nutzer mit Tier `premium`, KEINER hat bereits eine passende `premium_sms_reply_to` gespeichert / When eine als Garmin erkannte Nachricht eintrifft / Then wird bei KEINEM der beiden Nutzer `user.json` verändert, der Endpoint antwortet mit einem Fehlerstatus statt 200, und es gibt keinen Fallback auf einen Default-Nutzer.
  - Test: Zwei-Nutzer-Fixture (beide `premium`), Endpoint aufrufen, beide `user.json`-Dateien vor/nach vergleichen — müssen identisch sein; HTTP-Status prüfen.

- **AC-6:** Given ein Premium-Nutzer hat bereits `premium_sms_reply_to = X` gespeichert, und mittlerweile existiert ein zweiter Premium-Nutzer ohne gespeicherten Wert / When erneut eine Garmin-Nachricht von genau Nummer X eintrifft / Then wird sie weiterhin dem ursprünglichen Nutzer zugeordnet — die "genau ein Premium-Nutzer"-Regel (AC-4) greift hier nicht mehr, die gespeicherte Adresse hat Vorrang.
  - Test: Zwei-Premium-Nutzer-Fixture, einer mit vorbelegtem `PremiumSmsReplyTo`, Nachricht von exakt dieser Nummer senden, nur der vorbelegte Nutzer darf sich (im Zeitstempel) ändern.

- **AC-7:** Given der Python-Core läuft aus einem Nicht-Produktions-Checkout (Test/Staging/Worktree) UND `GZ_PREMIUM_SMS_POLL_DRYRUN` ist NICHT exakt `1` gesetzt / When `poll_and_process()` aufgerufen wird / Then wird KEIN HTTP-Call gegen `gateway.seven.io` ausgeführt, die Funktion liefert 0, und eine Warnung wird geloggt — unabhängig davon, ob ein Sandbox-Key konfiguriert ist, weil dieser dasselbe Produktiv-Journal liest. Mit gesetztem Schalter gilt stattdessen AC-10.
  - Test: `poll_and_process()` ohne die Env-Var in einer Nicht-Prod-Origin aufrufen, prüfen dass kein Request erfolgt ist und der Rückgabewert 0 ist.

- **AC-8:** Given eine Garmin-Nachricht wurde in einem früheren Poll bereits verarbeitet (ihre `id` ist ≤ der gespeicherten `last_seen_id`) / When sie im nächsten Poll erneut im Journal-Fenster auftaucht / Then löst sie KEINEN erneuten Aufruf des Lern-Endpoints aus und zählt nicht im Rückgabewert des zweiten Laufs.
  - Test: Zweimal `poll_and_process()` mit derselben Fixture aufrufen; beim zweiten Lauf muss der Lern-Endpoint (bzw. dessen Fake/Double) unaufgerufen bleiben.

- **AC-9:** Given der neue Cron-Job `premium_sms_poll` ist registriert / When `GET /api/scheduler/status` nach einem Lauf abgefragt wird / Then erscheint der Job mit einem frischen `last_run`-Zeitstempel und Status — allein durch `s.recordRun(...)`, ohne dass der neue Code selbst Observability-Felder pflegt.
  - Test: Go-Scheduler-Test, der einen Tick auslöst und `Status()` danach auf den neuen Job-Eintrag prüft (Vorbild: bestehende `recordRun`-Tests für `inbound_command_poll`).

- **AC-10:** Given der Python-Core läuft aus einem Nicht-Produktions-Checkout UND die Umgebungsvariable `GZ_PREMIUM_SMS_POLL_DRYRUN=1` ist exakt gesetzt / When `poll_and_process()` aufgerufen wird und das Journal eine als Garmin erkannte Nachricht enthält / Then wird der HTTP-Abruf gegen `journal/inbound` tatsächlich ausgeführt und die Nutzer-Auflösung (R3) läuft bis zum simulierten Ergebnis durch, ABER kein einziges `user.json` verändert sich — die Sperre aus AC-7 öffnet sich nur für das Lesen, das Schreiben bleibt strukturell unerreichbar, weil der Code-Pfad, der `SaveUser` aufruft, im Dry-Run-Zweig nie betreten wird.
  - Test: `poll_and_process()` mit gesetzter Env-Var und Fixture aufrufen, den HTTP-Mock auf einen tatsächlichen Aufruf gegen `journal/inbound` prüfen, danach alle `user.json`-Snapshots vor/nach vergleichen (müssen identisch sein) — PLUS ein Go-Handler-Test, der den Endpoint direkt mit `{"dry_run": true}` aufruft (sowohl für den Fall mit eindeutigem Treffer als auch für den Mehrdeutigkeits-Fall aus AC-5) und in beiden Fällen `SaveUser` nachweislich nie aufgerufen wird.

## Known Limitations

- **Erkennungszeichen ist einfach belegt, nicht bewiesen.** Beleg ist genau eine gemessene Garmin-Nachricht (2026-08-10). Dass JEDE Geräte-Nachricht `inreachlink.com` trägt, ist plausibel, aber ungeprüft — Nachweis gehört in die Generalprobe #1533, nicht in diese Scheibe.
- **"Genau ein Premium-Nutzer" ist eine Übergangsregel, kein echtes Pairing.** Solange genau ein Premium-Nutzer existiert, kann theoretisch eine fremde SMS mit `inreachlink.com` im Text die Rückadresse setzen. Das Kennzeichen senkt das Risiko deutlich, beseitigt es nicht. Sobald ein zweiter Premium-Nutzer real hinzukommt, ist eine echte Kopplung (Pairing, z.B. Bestätigungscode) zwingend nötig — dieser Fall wird von AC-5 bewusst auf "verwerfen statt raten" abgebildet, nicht gelöst. Folgearbeit als eigenes Issue.
- **Zeitstempel ist die Empfangszeit des Go-Endpoints, nicht der von seven.io gemeldete SMS-`timestamp`.** Dessen Format ist in den gemessenen Journal-Daten nicht spezifiziert genug, um es blind zu parsen; die bewusst einfachere Wahl vermeidet eine unbelegte Format-Annahme.
- **Origin-Guard lässt außerhalb "production" nur einen Trockenlauf zu** (`GZ_PREMIUM_SMS_POLL_DRYRUN=1`, AC-10): Abruf und Erkennung (R1) sowie die simulierte Nutzer-Auflösung (R3) sind auf Staging/Worktree beobachtbar, ein echter Schreibvorgang bleibt Produktion vorbehalten. #1533 (Generalprobe) muss deshalb weiterhin production-nah arbeiten, um den vollständigen Schreibpfad zu prüfen — der Trockenlauf deckt nur die Beobachtbarkeit von R1/R3 ab, nicht den echten Effekt auf `user.json`.
- **Kein Frontend, keine Sichtbarkeit für den Nutzer.** Die gelernte Adresse ist in dieser Scheibe nirgends im UI sichtbar (folgt in S3).
- **Keine Befehlsausführung.** Eine erkannte Garmin-Nachricht löst in S1 ausschließlich das Lernen der Rückadresse aus, keine Verarbeitung ihres Inhalts als Befehl (#735 kann darauf aufsetzen).

## Test Coverage

- `tests/unit/test_inbound_sms_reply_learning.py` (Python, Kern-Schicht, deterministisch, ohne echtes Netz — aufgezeichnete Journal-Fixtures mit erfundenen Rufnummern):
  - `test_garmin_marker_message_learns_reply_address` (AC-1)
  - `test_message_without_marker_is_ignored` (AC-2)
  - `test_newest_garmin_message_overwrites_older_stored_value` (AC-3)
  - `test_dedup_pointer_prevents_reprocessing` (AC-8)
  - `test_non_production_origin_blocks_poll_without_dryrun_switch` (AC-7)
  - `test_dryrun_switch_polls_journal_but_writes_nothing` (AC-10)
  - `test_dryrun_switch_warns_loudly_on_stderr` (Vorbild `GZ_SKIP_FRONTEND_BROWSER_GATE`)
  - `test_fetch_uses_x_api_key_header_and_limit_param` (Abruf-Vertrag: `X-Api-Key`, `limit`, kein `date_from`)
- `internal/handler/premium_sms_connect_test.go` (Go, mit echtem Store gegen temporäres Testverzeichnis, zwei Nutzer wie von CLAUDE.md für datenbewegende Endpoints gefordert):
  - `TestLearnSetsReplyAddressForSoleUnambiguousPremiumUser` (AC-4)
  - `TestLearnRejectsWhenTwoPremiumUsersAndNoStoredMatch` (AC-5, kein Cross-User-Leck)
  - `TestLearnPrefersStoredMatchOverSoleCandidateRule` (AC-6)
  - `TestLearnRejectsNonLocalhostCaller` (localhost-Sperre, Vorbild `telegram_connect.go`)
  - `TestLearnDryRunNeverCallsSaveUser` (AC-10, beide Zweige: eindeutiger Treffer und Mehrdeutigkeit)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (bestehendes ADR-0015 reicht)
- **Rationale:** ADR-0015 (Dual-Stack-Zielarchitektur) weist Fachlogik/Polling dem Python-Core und Persistenz/`user.json`-Schreibzugriff dem Go-Backend zu. Diese Scheibe hält sich exakt daran: der Python-Reader trifft die fachlichen R1/R2/R3-Entscheidungen, schreibt aber nie direkt in `user.json` — das bleibt ausschließlich Go über den neuen internen Endpoint vorbehalten (Tech-Lead-Entscheid 2026-08-10, im Kontextdokument protokolliert). Der Dry-Run-Zweig (AC-10) ändert daran nichts: auch die Simulation läuft über denselben Go-Endpoint, nur ohne den `SaveUser`-Aufruf zu erreichen.

## Changelog

- 2026-08-10: Initial spec erstellt — Issue #1676, Scheibe S1
- 2026-08-10: v1.1 — AC-10 (Trockenlauf-Schalter `GZ_PREMIUM_SMS_POLL_DRYRUN`) ergänzt, Known Limitations zum Origin-Guard entsprechend angepasst (Team-Lead-Nachtrag: Totalsperre hätte den Reader bis zum Produktivlauf unbeobachtbar gemacht)
- 2026-08-10: v1.2 — Fix F001 (Adversary-Fund): verlorene Rückadresse bei
  vorübergehendem Lernfehler (Deploy-Neustart der Go-API als realistischer
  Auslöser, da sich das Garmin-Gerät im Wesentlichen einmal pro Tour meldet).
  Schritt 7/9/11 korrigiert — der Dedup-Zeiger wandert nur noch bei Erfolg
  oder bewusster Ablehnung (HTTP 4xx) über eine erkannte Garmin-Nachricht
  hinweg, nicht mehr bei einem vorübergehenden Fehlschlag (Netzwerk/Timeout/
  5xx). `trigger_inbound_sms()` meldet den Status jetzt aus dem tatsächlichen
  Fehlschlag-Zähler statt bedingungslos "ok". ACs wörtlich unverändert.
- 2026-08-10: v1.3 — Fix F002 (Nachbesserung F001): ein vorübergehender
  Fehlschlag heilt sich durch den F001-Zeiger-Fix von selbst, ein
  DAUERHAFTER (Lern-Endpunkt dauerhaft unerreichbar, Fehlkonfiguration) blieb
  aber weiterhin unsichtbar, weil `trigger_inbound_sms()` trotz `failed > 0`
  HTTP 200 meldete und niemand den Antwortkörper auswertete. Erster Entwurf
  (HTTP 503 vom Python-Endpunkt) wurde noch am selben Tag zurückgezogen: drei
  Nachbar-Endpunkte in derselben Datei (`trigger_trip_reports`/
  `trigger_compare_presets_daily`, Issue #766/#1290) melden `status:
  "partial"` bewusst MIT HTTP 200 — das ist die Hausnorm, ein Fehlerstatus
  wäre falsch auf HTTP-Ebene und ein Alleingang gegenüber den Nachbarn.
  `api/routers/scheduler.py` bleibt deshalb unverändert (200,
  `status`/`count`/`failed` im Body). Die Sichtbarkeit entsteht stattdessen
  auf der Go-Seite: `premiumSmsPoll()` ruft den Endpunkt über ein neues,
  lokales `triggerPremiumSmsPollEndpoint()` statt über das generische
  `triggerGlobalEndpoint()` auf und wertet den Antwortkörper aus (wie
  `triggerEndpointForUser()` es für die Nutzer-Fan-out-Jobs bereits tut) —
  `failed > 0` bzw. `status == "partial"` liefert einen Fehler an
  `recordRun()`, sichtbar in `/api/scheduler/status`.
  `triggerGlobalEndpoint()` selbst bleibt unangetastet (daran hängen
  `inbound_command_poll` u. a.). ACs wörtlich unverändert.
