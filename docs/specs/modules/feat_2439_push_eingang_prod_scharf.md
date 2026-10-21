---
entity_id: feat_2439_push_eingang_prod_scharf
type: module
created: 2026-10-20
updated: 2026-10-20
status: implemented
version: "1.0"
tags: [befehle, push-eingang, webhook, seven-io, stalwart, prod-betrieb, live-tests, "#2439"]
---

# Push-Eingang für Befehle in Produktion scharf schalten + Live-Tests korrigieren

## Approval

- [ ] Approved

## Purpose

Der Sofort-Weg für Befehle (seven.io-Webhook für Premium-SMS, Stalwart-Webhook für E-Mail; der
5-Minuten-Poll bleibt Fallback) ist im Code seit 19.10. live, in Produktion aber nicht eingeschaltet:
dort ist kein Hook registriert, seit 15.10. kam kein einziger Aufruf an. Diese Spec schaltet ihn
kontrolliert ein, belegt die Wirkung je Kanal und korrigiert die Live-Tests, die zu Unrecht rot
werden. Sie ist die Restarbeit von Issue #2439 und ergänzt die Specs
`docs/specs/modules/feat_2439_befehle_push_eingang.md` und
`docs/specs/modules/feat_2439_befehle_antwortzeit.md` (beide werden nicht geändert, nur referenziert).

**Kanalregel:** Alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) sind gleichrangig. Hier
betroffen sind der Premium-SMS- und der E-Mail-Eingang (Push) sowie die Antwortzeit-Messung für
Telegram. Signal existiert nicht mehr.

## Source

- **Files:** siehe „Affected Files"
- **Identifier:** `scripts/seven_hooks.sh`, `.claude/tools/befehl_antwortzeit.py`,
  `.claude/tools/befehl_messlogik.py`, `tests/e2e/test_push_eingang_befehle_staging.py`,
  `MeteoFranceProvider` in `src/providers/meteofrance.py`

> **Schicht-Hinweis:** Einzige Produktcode-Änderung liegt im **Python-Core** (`src/providers/meteofrance.py`,
> Provider `fr_direct`). Go-API (`internal/handler/inbound_webhooks.go`, `internal/scheduler/push_kick.go`)
> bleibt unverändert. Alles andere sind Betriebs-Skripte, Lese-Werkzeuge, Doku und Tests.

## Estimated Scope

- **LoC:** ca. +250 / −40 (Skript ~90, Testkorrekturen ~60, Messlogik + Werkzeug ~70, `fr_direct` ~10, `.env.example` ~8). Werkzeuge unter `.claude/`, Skripte und Doku zählen voraussichtlich nicht ins LoC-Limit (vor `/40` mit `workflow.py status` klären; sonst `loc_limit_override 500`).
- **Files:** 13
- **Effort:** medium (Betriebsänderung an Prod, wenig Code)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/inbound_webhooks.go` | Go-Handler | Annahme der Hooks: Abweisung 403 + `rejected_total`, gültig → `received_total` + Poll-Weckruf. Unverändert. |
| `internal/scheduler/push_kick.go` | Go-Scheduler | Zähler, `missed`-Zählung im Cron-Poll. Unverändert. |
| `internal/scheduler/scheduler_kick_test.go:633` | Test | `TestPushMissed_CronLaufMitBefehlenOhneKickZaehltAlsVerpasst` bewacht die `missed`-Zählung. |
| `/api/scheduler/status` (Header `X-GZ-Status-Token`) | Status-Endpoint | Push-Zähler je Job (`received_total`, `rejected_total`, `missed_total`, `last_received`, `last_run`). |
| seven.io Hooks-API (`gateway.seven.io/api/hooks`) | Extern | Registrierung `sms_mo`, Zugang `GZ_SEVEN_API_KEY` (belegt: sieht die Servicenummer). |
| Stalwart-Admin (v0.16.26) | Extern | Webhook-Event `message-ingest.ham`. |
| henemm-infra `nginx/*.conf`, `scripts/check-gregor20.sh:962-1028` | Infra | Nginx-Locations (live) und `missed`-Check (scharf seit 19.10.). Unverändert. |
| `.claude/tools/seven_journal.py` | Lese-Werkzeug | Vorlage für das seven.io-Journal (inbound/outbound). |
| `scripts/telegram_set_webhook.sh` | Skript | Stilvorlage für `seven_hooks.sh`. |
| `src/providers/dwd.py:893` | Produktcode | Vorlage der Kalt-Zeile (`downloads=N`). |

## Implementation Details

### 1. Reihenfolge der Inbetriebnahme (PO-Entscheid 20.10.)

Die Prod-Hooks werden **erst nach Spec-Freigabe und grünen Kern-Tests** registriert („regulär im Ablauf").
Bis dahin zählt jeder per Cron verarbeitete Prod-Befehl als `missed` und löst eine Alarm-Mail aus (siehe
Risiken) — das ist vom PO hingenommen. Reihenfolge:

1. Herkunftssperre auf Staging bestätigen (AC-1).
2. seven.io-Hook für Prod per `scripts/seven_hooks.sh set` registrieren (AC-2).
3. Stalwart-Hook für Prod im Stalwart-Admin registrieren, Empfängerfilter prüfen (AC-3).
4. Hook-IDs beider Umgebungen ins Runbook (AC-4).
5. Je Kanal ein echter Befehl, Zähler vor/nach (AC-5, AC-6).

### 2. `scripts/seven_hooks.sh` (neu)

Aufrufe `list | set | delete`, Stil wie `scripts/telegram_set_webhook.sh` (`set -euo pipefail`, `require`,
`usage` aus dem Kopfkommentar). Pflicht-Env: `GZ_SEVEN_API_KEY`; für `set`: Zielhost, Pfad-Secret
(`SEVEN_WEBHOOK_PATH_SECRET`) und Event-Filter (Servicenummer ohne „+“). Verhalten:

- `set`: liest zuerst `GET /api/hooks`; existiert schon ein Hook mit gleicher Ziel-URL **und** gleichem
  Event (`sms_mo`), wird nichts angelegt („übersprungen, ID …“). Sonst `POST /api/hooks`
  (`event_type=sms_mo`, `event_filter=<Servicenummer>`, `request_method=POST`).
- `list`: zeigt ID, Event, Filter, Ziel-URL, Angelegt-am.
- `delete <id>`: entfernt genau diesen Hook (Rollback).
- Jede Ausgabe maskiert das Pfad-Secret in der Ziel-URL (`…/api/webhooks/sms/****`) und gibt nie den
  API-Schlüssel oder den Signing-Key aus.
- Der Hook-Schlüssel zum Signieren (`SEVEN_WEBHOOK_SIGNING_KEY`) kommt weiter aus dem seven.io-Dashboard
  und wird vom Skript nicht angefasst.

### 3. Runbook `docs/runbooks/inbound-webhooks.md`

- Hook-IDs: Staging seven.io 4750 und Staging-Stalwart `jjsl7jjqacaa` (belegt), dazu die neuen
  Prod-IDs; Aufruf von `seven_hooks.sh`.
- **Signatur-Aussage (Z. 37-43) korrigieren:** Die dort genannte Nachweisdatei
  `docs/artifacts/feat-2439-befehle-push-eingang/seven-signatur-nachweis.md` existiert nicht; die
  Fixture ist ein Testvektor, kein Mitschnitt. Tatsächlicher Beleg: echte Staging-Zustellung am 15.10.
  wurde akzeptiert (`rejected_total` blieb 0); für Prod der Beleg aus AC-5.
- **Variablenname:** Das Runbook nennt `PUBLIC_HOST`. Der Go-Code liest die Variable über das Präfix
  `GZ` (`internal/config/config.go:60,87` → `GZ_PUBLIC_HOST`), in Prod- und Staging-`.env` ist
  `GZ_PUBLIC_HOST` gesetzt. Runbook-Tabelle und Inbetriebnahme-Schritt 1 nennen künftig `GZ_PUBLIC_HOST`.
- Hinweis zum Stalwart-Empfängerfilter und zur Zuordnungs-Grenze (AC-3).
- Hinweis „`missed` bleibt bedingungslos (Nicht-Ziel)“ mit Verweis auf den Bewacher-Test.

### 4. `.env.example`

Die vier Variablen `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_PATH_SECRET`,
`STALWART_WEBHOOK_SECRET` mit Ein-Zeilen-Erklärung (wofür, fehlt ⇒ Endpunkt antwortet 503) und
Platzhalterwerten; zusätzlich `GZ_PUBLIC_HOST` (Basis der signierten URL).

### 5. Kalt-Signal für `fr_direct` (einzige Produktcode-Änderung)

In `src/providers/meteofrance.py`, Methode `_fetch_coverage_signals_multi` (Fenster-Schleife ab ca. Z. 700),
wird je Abruf eine Abschlusszeile geschrieben, analog zu `dwd_fenster` (`src/providers/dwd.py:893`):

```
fr_direct_fenster fenster_s=%.2f downloads=%d cache_treffer=%d
```

`downloads` = tatsächlich über das Netz geholte Fenster (Zweig `raw is None` → `_request_once` erfolgreich),
`cache_treffer` = aus dem gemeinsamen Fenster-Zwischenspeicher bediente Fenster. Die Zeile erscheint auch
beim Totalausfall und bei Budgetabbruch (ein Eintrag je Abruf, vor jedem `return`). **Bewusst anderer Präfix
als DWD** (`fr_direct_fenster`), damit die DWD-Auswertung (`_ZEILE_DWD`) sie nicht fälschlich als DWD-Download
zählt. Keine Änderung an Rückgabewerten oder Ausnahmeverhalten.

### 6. Reine Auswertelogik in `.claude/tools/befehl_messlogik.py` (neu)

Funktionen ohne Netz/Journal-Zugriff, von Live-Test **und** Prod-Werkzeug gemeinsam genutzt:

- `paare_heute_help(laeufe, kanaele, max_abstand_s)`: paart ein `HEUTE` nur mit dem **ersten** nachfolgenden
  `HELP` desselben Eingangs, wenn (a) der HELP **innerhalb von `max_abstand_s` nach dem HEUTE-Start**
  liegt und (b) **kein anderer Befehl desselben Eingangs dazwischen** liegt; ein HEUTE ohne Partner wird
  übersprungen (nicht als Fehler gewertet).
- `kalt_laeufe(laeufe, fenster_zeilen)`: wie `_kalt`, aber über die DWD- **oder** `fr_direct_fenster`-Zeile.
- `antwortzeit_aus_journalen(eingang_ts, ausgang_ts)`: Differenz Eingang → Antwort.

### 7. Prod-Lese-Werkzeug `.claude/tools/befehl_antwortzeit.py` (neu, nur lesend)

Aufruf z. B. `uv run python3 .claude/tools/befehl_antwortzeit.py --since 2026-10-20 [--kanal premium_sms|telegram|email]`.
Liest (1) das seven.io-Journal inbound/outbound (über dieselbe Konfiguration wie `seven_journal.py`,
Schlüssel nie ausgegeben, Nummern auf drei Ziffern gekürzt), (2) die Dauer-Zeilen
`befehl=… kanal=… trip=… dauer_ms=…` aus dem Prod-Journal `gregor-python`, (3) den Push-Status von Prod
(`/api/scheduler/status`, Token aus der Konfiguration, nie ausgegeben). Es gibt je Befehl aus: Befehl, Kanal,
Eingangszeit, Antwortzeit, Dauer, ob `last_received` zeitlich zum Eingang passt (Push-Zuordnung), sowie
Maximum/Median je Befehl. Versendet nichts, schreibt nichts.

### 8. Live-Tests `tests/e2e/test_push_eingang_befehle_staging.py` (korrigieren)

| Test | Korrektur |
|------|-----------|
| `test_ac1_sms_last_run_sekunden_nach_webhook` | Prüft zuerst, ob die Messung noch gültig ist: liegt `last_run` nach einem *späteren* `*/5`-Tick (nicht der Poll-Lauf nach dem Webhook), ist das keine Aussage über den Sofort-Weg ⇒ `pytest.skip` mit Hinweis „Messung überholt, direkt nach der SMS erneut fahren“ statt falschem Rot. Der Grenzwert 60 s bleibt. |
| `test_ac3_…`, `test_ac4_…`, `test_ac12_…` | Eingang `premium_sms` entfällt auf Staging (die Herkunftssperre lässt dort keine Premium-SMS-Antwort zu): `NOT_MEASURABLE_ON_STAGING` mit Verweis auf `.claude/tools/befehl_antwortzeit.py` (Prod-Messweg). E-Mail und Telegram bleiben Pflicht. |
| `test_ac12_…` | Paarung über `paare_heute_help` (Zeitfenster nach HEUTE-Start, kein Zwischenbefehl, HEUTE ohne Partner überspringen). Behebt das heutige falsche Rot („813 s“). |
| `test_ac5_…` | Wertet nur **kalte** Korsika-Läufe aus (`_kalt` bzw. `kalt_laeufe` mit `fr_direct_fenster`-Zeile), nicht jeden Lauf des Trips. |

### 9. Telegram HEUTE/MORGEN (Antwortzeit AC-4) — Festlegung

Das verwaiste Staging-Konto `e2ek71785826879` teilt die `telegram_chat_id` mit `tg-live-e2e` und gewinnt
die Zuordnung (`src/app/loader.py:1446-1498`). Leeren wäre über die reguläre Profil-API möglich
(`internal/handler/auth.go:1354`, `telegram_chat_id: ""`), verlangt aber eine Anmeldung als dieses Konto.
Dessen Zugangsdaten sind weder im Repo noch ableitbar (zufällig vom E2E-Treiber erzeugt, `claude-gregor`-Daten
für `hem` nicht lesbar). **Festlegung:** keine Bereinigung auf Staging; die Telegram-Messung für HEUTE/MORGEN
läuft über Prod mit demselben Lese-Werkzeug (Dauer-Zeilen `kanal=telegram` im Prod-Journal) am nächsten
echten Telegram-Befehl (kein Sammelversand, kein künstlich erzeugter Prod-Nutzer). Staging-Telegram bleibt
`NOT_MEASURABLE_ON_STAGING` mit diesem Verweis.

## Expected Behavior

- **Input:** Freigegebene Spec; vorhandene Zugänge (`GZ_SEVEN_API_KEY`, Stalwart-Admin, `GZ_STATUS_TOKEN`).
- **Output:** Ein registrierter Prod-Hook je Kanal (IDs im Runbook), ein belegter Push-Eingang je Kanal
  (E-Mail, Premium-SMS) in Prod, korrigierte Live-Tests, ein Prod-Lese-Werkzeug, ein Kalt-Signal für Korsika.
- **Side effects:** Ein seven.io-Hook auf dieselbe Servicenummer weckt **beide** Umgebungen (Staging 4750 und
  Prod); die Doppelantwort verhindert allein die Herkunftssperre auf Staging (AC-1). Ein Stalwart-Hook weckt
  den Prod-Poll auf jede gemeldete Mail (Mail-Handler filtert nicht nach Empfänger,
  `internal/handler/inbound_webhooks.go:146-164`).

## Acceptance Criteria

Messarten: **Kern** = deterministischer Test ohne Netz, **Staging** = Live-Test gegen Staging,
**Prod-Messung** = Lese-Werkzeug bzw. Statusabfrage gegen Produktion. Der PO wird nicht zum Tester gemacht.

- **AC-1:** Given der seven.io-Hook 4750 weckt Staging und der neue Prod-Hook
  weckt Produktion auf dieselbe Servicenummer / When vor der Prod-Registrierung ein eingehender
  Premium-SMS-Webhook auf Staging ankommt (bzw. der Staging-Poll läuft) / Then verschickt Staging
  **keine** Antwort-SMS (kein Treffer in `seven_journal.py outbound` aus Staging im Messfenster) und
  `push.received_total` von Staging steigt trotzdem.
  Messung: **Staging** + Lese-Werkzeug; ohne dieses Ergebnis wird der Prod-Hook nicht registriert.

- **AC-2:** Given `scripts/seven_hooks.sh` und der Prod-Zugang /
  When `set` mit Prod-Host, Pfad-Secret und Servicenummer zweimal hintereinander ausgeführt wird / Then
  legt der erste Lauf genau einen Hook mit Event `sms_mo` und Prod-Ziel-URL an, der zweite meldet
  „übersprungen“ (weiterhin genau ein Prod-Hook, Staging-Hook 4750 unberührt), und keine Ausgabe enthält das
  Pfad-Secret, den API-Schlüssel oder den Signing-Key im Klartext.
  Messung: **Kern** für Skript-Logik (Test mit aufgezeichneten Hooks-API-Antworten als Fixture gegen den
  Skript-Ablauf, z. B. `tests/test_seven_hooks_idempotent_maskiert.py` über ein lokales Antwort-Double,
  das echte Antwortformen liefert); **Prod-Messung** `seven_hooks.sh list` nach dem echten `set`.

- **AC-3:** Given der Stalwart-Admin / When der Prod-Hook mit Ziel
  `https://gregor20.henemm.com/api/webhooks/mail/<Secret>`, Bearer-Authentifizierung und Event
  `message-ingest.ham` angelegt wird / Then wird bei der Registrierung geprüft, ob der Hook einen
  Empfängerfilter erlaubt. Gibt es einen, wird er auf die Befehlsadresse gesetzt; gibt es keinen, gilt die
  zeitliche Zuordnung aus AC-5 als Beleg, und die Grenze („fremde Mails an andere Postfächer zählen als
  `received` und können ein echtes `missed` im 5-Minuten-Fenster verdecken“) steht im Runbook. Das Ergebnis
  der Prüfung ist im Runbook dokumentiert.
  Messung: **Prod-Messung** (Stalwart-Admin, Statusabfrage); das Runbook-Ergebnis wird im Abschluss gegengelesen.
  Bekannter Stand: im Runbook/Code ist ein Filter **nicht** erwähnt.

- **AC-4:** Given das Runbook `docs/runbooks/inbound-webhooks.md` / When
  die Registrierung abgeschlossen ist / Then stehen dort die Hook-IDs beider Umgebungen (Staging seven.io
  4750, Staging-Stalwart `jjsl7jjqacaa`, Prod beider), die Signatur-Aussage verweist nicht mehr auf eine
  nicht vorhandene Datei, sondern nennt den tatsächlichen Beleg (Staging-Zustellung 15.10., `rejected_total`
  0, plus Prod-Beleg aus AC-5), und der Variablenname heißt `GZ_PUBLIC_HOST`.
  Messung: Doku-Prüfung im Abschluss (`# doc-compliance-test` nur für Verweise innerhalb von `docs/`, nie auf
  `src/`). Die Hook-IDs selbst sind per `seven_hooks.sh list` gegenprüfbar.

- **AC-5:** Given beide Prod-Hooks sind registriert und es gibt
  keinen Deploy/Neustart zwischen den Messungen (die Zähler leben nur im Speicher) / When Claude über ein
  Testkonto eine Befehlsmail (z. B. `HELP` an einen Test-Trip, kein Sammelversand) an die Prod-Befehlsadresse
  schickt / Then steigt `received_total` des Prod-Jobs `inbound_command_poll` um genau diesen Eingang,
  `last_received` liegt innerhalb weniger Sekunden um die Sendezeit, `rejected_total` bleibt 0, `last_run`
  liegt wenige Sekunden danach (nicht am 5-Minuten-Raster), und die Antwort ist im Testkonto zugestellt.
  Messung: **Prod-Messung** — Statusabfrage vorher/nachher (`/api/scheduler/status`, Header
  `X-GZ-Status-Token`) plus IMAP-Beleg der Antwort. „`received_total` steigt“ allein genügt nicht, weil
  der Mail-Handler nicht nach Empfänger filtert; die zeitliche Zuordnung zum konkreten Befehl ist Pflicht.

- **AC-6:** Given beide Prod-Hooks registriert, kein Deploy/Neustart
  dazwischen / When der nächste **echte** Premium-SMS-Befehl eintrifft / Then steigt `received_total` von
  `premium_sms_poll` um 1, `last_received` passt zum Eingangszeitpunkt aus dem seven.io-Journal,
  `rejected_total` bleibt 0 und die Antwort steht im seven.io-Journal outbound.
  Messung: **Prod-Messung** mit `.claude/tools/befehl_antwortzeit.py` (siehe „Offene Abhängigkeit“). Eine
  echte eingehende Premium-SMS ist per API nicht erzeugbar (von der zweiten Nummer kommt nur eine InfoSMS an);
  der Weg ist daher der nächste ohnehin eintreffende Befehl, nicht der PO als Tester.

- **AC-7:** Given ein per Cron verarbeiteter Befehl ohne
  vorherigen Weckruf / When der Poll läuft / Then zählt er weiterhin als `missed` (keine Kopplung an „mindestens
  ein `received` seit Start“, auch nicht bei komplett ausgefallenem Push).
  Messung: **Kern** — bestehender Test
  `internal/scheduler/scheduler_kick_test.go:633` `TestPushMissed_CronLaufMitBefehlenOhneKickZaehltAlsVerpasst`
  bleibt grün und unverändert. Siehe Nicht-Ziele.

- **AC-8:** Given aufgezeichnete Journal-Daten
  (versionierte Fixture mit seven.io-inbound/-outbound und Prod-Dauer-Zeilen, z. B. unter
  `tests/fixtures/befehl_antwortzeit/`) / When `.claude/tools/befehl_antwortzeit.py` bzw. dessen Auswertelogik
  sie verarbeitet / Then liefert sie je Befehl Eingangszeit, Antwortzeit, Dauer und die Push-Zuordnung, ordnet
  einen Eingang nur dem zeitlich passenden Befehl zu, und meldet Maximum und Median je Befehl korrekt.
  Messung: **Kern** (`tests/test_befehl_antwortzeit_auswertung.py`, echte aufgezeichnete Form, kein Mock der
  eigenen Annahme).

- **AC-9:** Given AC-8 grün und beide Prod-Hooks
  registriert / When der nächste echte Premium-SMS-Befehl eintrifft (weckt Staging **und** Prod) / Then liegen
  vor: Prod-Antwortzeit (Antwortzeit-AC-3/-4/-12 für Premium-SMS) und der Staging-SMS-Nachversuch 0/3/8 s ohne
  EOF (Antwortzeit-AC-14, `test_ac14…` und `test_ac1…` grün, Aufruf direkt nach dem Befehl).
  Messung: **Prod-Messung** + **Staging**. Erst diese Messung erlaubt das Schließen des Issues (siehe unten).

- **AC-10:** Given die Festlegung in Abschnitt 9 / When ein echter
  Telegram-Befehl `HEUTE` bzw. `MORGEN` in Prod beantwortet wurde / Then weist das Lese-Werkzeug die
  Telegram-Antwortzeit aus der Prod-Dauer-Zeile aus, und gemessen wird gegen die Grenzen aus Antwortzeit-AC-4
  (kalt: Maximum < 60 s, Median < 45 s); Staging-Telegram steht als `NOT_MEASURABLE_ON_STAGING` mit
  Verweis auf diesen Weg.
  Messung: **Prod-Messung**.

- **AC-11:** Given `last_run` des Jobs wurde durch einen späteren
  `*/5`-Tick überschrieben / When `test_ac1_sms_last_run_sekunden_nach_webhook` läuft / Then wird er mit
  Hinweis übersprungen (`skip`), statt fälschlich rot zu werden; liegt der Poll-Lauf dagegen direkt hinter dem
  Webhook, wird er wie bisher gegen 60 s geprüft und bleibt rot, wenn die Grenze verletzt ist.
  Messung: **Kern** für die Gültigkeitsentscheidung (Funktion aus `befehl_messlogik.py`,
  `tests/test_befehl_messlogik_messung_ueberholt.py`) und **Staging** für den Test selbst.

- **AC-12:** Given Staging hat die Kanalgruppe
  `premium_sms` strukturell nicht (Herkunftssperre) / When die drei Tests laufen / Then fordern sie
  `premium_sms` dort nicht mehr, sondern melden `NOT_MEASURABLE_ON_STAGING` mit Verweis auf
  `.claude/tools/befehl_antwortzeit.py`; E-Mail und Telegram bleiben Pflicht und rot bei Verletzung.
  Messung: **Staging**.

- **AC-13:** Given eine Dauer-Zeilenfolge mit mehreren HEUTE und HELP
  (darunter ein HEUTE ohne HELP im Zeitfenster und ein HEUTE mit Zwischenbefehl) / When `paare_heute_help`
  auswertet / Then entstehen nur Paare aus einem HEUTE und dem ersten folgenden HELP desselben Eingangs
  innerhalb des Zeitfensters nach HEUTE-Start und ohne Zwischenbefehl; unpaarige HEUTE werden übersprungen,
  und eine Folge ohne jedes gültige Paar ergibt „nicht messbar“ statt eines absurden Abstands (der frühere
  Fehlwert 813 s entsteht nicht mehr).
  Messung: **Kern** (`tests/test_befehl_messlogik_paarung.py` mit aufgezeichneter Dauer-Zeilenfolge als
  versionierter Fixture).

- **AC-14:** Given ein Korsika-Trip (`fr_direct`) / When ein Wetterabruf Fenster
  tatsächlich über das Netz lädt / Then schreibt der Provider genau eine Zeile
  `fr_direct_fenster fenster_s=… downloads=N cache_treffer=M` je Abruf mit `N` = geladene Fenster; kommen alle
  Fenster aus dem Zwischenspeicher, steht `downloads=0` (dann gilt der Lauf als nicht kalt); beim Abbruch
  durch Zeitbudget oder Totalausfall wird die Zeile trotzdem geschrieben. Die Zeile wird von der
  DWD-Auswertung nicht als DWD-Download gezählt.
  Messung: **Kern** (`tests/test_meteofrance_fenster_zeile.py` über den echten Provider mit aufgezeichneter
  Server-Antwort bzw. dem vorhandenen Fenster-Zwischenspeicher, `caplog`, kein Mock der eigenen Annahme).

- **AC-15:** Given Korsika-Läufe, kalte und warme gemischt / When
  `test_ac5…` auswertet / Then zählen nur Läufe mit `fr_direct_fenster … downloads>0` im Befehlsfenster
  (mindestens 3 je Befehl, jeder < 60 s); sind weniger als 3 kalte Läufe vorhanden, ist das Ergebnis „nicht
  belegt“ mit Anzahl, kein stilles Grün.
  Messung: **Kern** (`kalt_laeufe` mit Fixture, `tests/test_befehl_messlogik_paarung.py`) und **Staging**.

- **AC-16:** Given `.env.example` / When ein Entwickler eine neue Umgebung
  aufsetzt / Then sind `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`,
  `STALWART_WEBHOOK_PATH_SECRET`, `STALWART_WEBHOOK_SECRET` und `GZ_PUBLIC_HOST` mit Erklärung aufgeführt;
  ein fehlendes Webhook-Secret führt weiterhin zu 503 des jeweiligen Endpunkts.
  Messung: **Kern** für das 503-Verhalten (bestehende Go-Handler-Tests); die Doku-Zeilen sind
  Dokumentation und werden im Abschluss gegengelesen.

## Nicht-Ziele

- Die `missed`-Zählung wird **nicht** aufgeweicht (nicht an „mindestens ein `received` seit Start“ gekoppelt):
  ein kompletter Push-Ausfall — genau der heutige Prod-Zustand — bliebe sonst dauerhaft stumm, und jeder
  Neustart setzt `received` auf 0. Bewacht durch `scheduler_kick_test.go:633`.
- `.claude/hooks/prod_selftest.py` wird **nicht** erweitert (Regel-Budget); die Push-Zähler werden über das
  Lese-Werkzeug und die Statusabfrage belegt.
- Keine Änderung am Go-Handler, Scheduler oder an henemm-infra (Vorschlag fürs Infra-Backlog, nicht hier:
  `check-gregor20.sh` könnte `received_total` mitlesen).
- Keine künstliche Erzeugung eingehender Premium-SMS und kein Prod-Testnutzer für Telegram.
- Kein Sammelversand über alle Trips; Befehle in Tests laufen nur gegen Test-Trips.

## Offene Abhängigkeit

AC-6, AC-9 und AC-10 brauchen einen **echten** Premium-SMS- bzw. Telegram-Befehl in Prod, der nicht
künstlich erzeugt werden kann. Er wird abgewartet (der nächste ohnehin eintreffende Befehl; er weckt
Staging und Prod zugleich und liefert damit auch die Staging-Messung zu Antwortzeit-AC-14). **Das Issue #2439
wird erst nach dieser Messung geschlossen**; bis dahin bleibt es offen, auch wenn Code, Hooks und Tests
ausgeliefert sind. Die Messung selbst erfolgt mit `.claude/tools/befehl_antwortzeit.py` (nur lesend); der PO
muss dafür nichts tun.

## Affected Files

| Datei | Change | Beschreibung |
|-------|--------|--------------|
| `scripts/seven_hooks.sh` | CREATE | `list\|set\|delete`, idempotent, Secrets maskiert, Stil wie `telegram_set_webhook.sh` |
| `docs/runbooks/inbound-webhooks.md` | MODIFY | Hook-IDs beider Umgebungen, Signatur-Aussage korrigieren, `GZ_PUBLIC_HOST`, Stalwart-Filter/Grenze |
| `tests/e2e/test_push_eingang_befehle_staging.py` | MODIFY | `test_ac1`, `test_ac3/4/12`, `test_ac5` korrigieren; Paarung über gemeinsame Logik |
| `.claude/tools/befehl_messlogik.py` | CREATE | reine Paarungs-/Auswertefunktionen (kein Netz) |
| `.claude/tools/befehl_antwortzeit.py` | CREATE | Prod-Lese-Werkzeug (seven.io-Journal, Prod-Dauer-Zeilen, Push-Status) |
| `src/providers/meteofrance.py` | MODIFY | Zeile `fr_direct_fenster … downloads=N` (Python-Core, Provider `fr_direct`) |
| `.env.example` | MODIFY | vier Webhook-Variablen + `GZ_PUBLIC_HOST` |
| `tests/test_befehl_messlogik_paarung.py` | CREATE | Kern: Paarung HELP/HEUTE, `kalt_laeufe` |
| `tests/test_befehl_messlogik_messung_ueberholt.py` | CREATE | Kern: Gültigkeit der `test_ac1`-Messung |
| `tests/test_befehl_antwortzeit_auswertung.py` | CREATE | Kern: Werkzeug-Auswertung mit Fixture |
| `tests/test_seven_hooks_idempotent_maskiert.py` | CREATE | Kern: Skript-Ablauf gegen aufgezeichnete Hooks-API-Antworten |
| `tests/test_meteofrance_fenster_zeile.py` | CREATE | Kern: Kalt-Zeile des Providers |
| `tests/fixtures/befehl_antwortzeit/` | CREATE | versionierte aufgezeichnete Journal-/Dauer-Zeilen-Daten |

## Geplante Tests

Alle Kern-Tests sind deterministisch, ohne Netz und ohne echte Postfächer; Namen nach Verhalten:

- `tests/test_befehl_messlogik_paarung.py` — beweist: nur HEUTE→HELP-Paare im Zeitfenster ohne Zwischenbefehl;
  unpaarige HEUTE werden übersprungen; kalte Korsika-/DWD-Läufe werden korrekt erkannt (AC-13, AC-15).
- `tests/test_befehl_messlogik_messung_ueberholt.py` — beweist: überholte `last_run`-Messung ergibt Skip,
  frische Messung wird geprüft (AC-11).
- `tests/test_befehl_antwortzeit_auswertung.py` — beweist: Eingang→Antwort-Zuordnung, Push-Zuordnung,
  Maximum/Median aus aufgezeichneten Daten (AC-8).
- `tests/test_seven_hooks_idempotent_maskiert.py` — beweist: zweimaliges `set` legt einen Hook an,
  Secrets erscheinen nie in der Ausgabe (AC-2).
- `tests/test_meteofrance_fenster_zeile.py` — beweist: Zeile mit korrektem `downloads`/`cache_treffer`,
  auch bei Abbruch, nicht als DWD gezählt (AC-14).
- Bestehend, unverändert grün: `internal/scheduler/scheduler_kick_test.go:633` (AC-7), Go-Handler-Tests für 503/403.
- Live (nur `/e2e-verify`): `tests/e2e/test_push_eingang_befehle_staging.py` korrigiert (AC-1, AC-11, AC-12, AC-15).
- Prod-Messung (Lese-Werkzeug, kein Test): AC-3, AC-5, AC-6, AC-9, AC-10.

## Known Limitations

- Die Zähler (`received_total` etc.) leben nur im Speicher: Neustart/Deploy zwischen Vorher-/Nachher-Messung
  entwertet den Beleg (AC-5/AC-6 daher ohne Deploy dazwischen).
- IP-Allowlist von seven.io steht nur in Nginx; ändert seven.io die Adressen, entsteht ein stiller 403, sichtbar
  erst über `missed`.
- Fremde Mails können ohne Empfängerfilter im 5-Minuten-Fenster ein echtes `missed` verdecken (AC-3 hält die
  Grenze im Runbook fest).
- Der Treiber, der Befehle für die Staging-Messläufe sendet, liegt nicht im Repo; die Live-Tests lösen nichts aus.

## Risiken

1. **Fehlalarm bis zur Registrierung:** Der `missed`-Check ist seit 19.10. scharf, die Prod-Hooks fehlen. Jeder
   per Cron verarbeitete Prod-Befehl (SMS oder Mail) zählt als `missed` und löst eine Alarm-Mail aus (einmal je
   Zuwachs). Stand 20.10. 09:15: noch 0. Vom PO hingenommen; Registrierung deshalb unmittelbar nach Freigabe
   und grünen Tests.
2. **Doppelantwort:** Ein Hook auf dieselbe Servicenummer weckt beide Umgebungen; Schutz allein durch die
   Herkunftssperre auf Staging ⇒ AC-1 vor Prod-Registrierung.
3. **Stiller 403** bei Signatur-/IP-Fehlern ⇒ nach Registrierung `rejected_total` beobachten (AC-5/AC-6).
4. **Falscher Stalwart-Eventname** = stille Nicht-Zustellung; verifiziert ist `message-ingest.ham` (v0.16.26).
5. **Zähler nur im Speicher** (siehe Known Limitations).
6. **Echte Premium-SMS nicht erzeugbar** ⇒ Abschluss hängt am nächsten echten Befehl.
7. **Einzige Produktcode-Änderung** ist eine Log-Zeile im Provider; Risiko gering, Kern-Test bewacht Rückgabe
   unverändert.

## Rollback

- seven.io: `scripts/seven_hooks.sh delete <Prod-ID>` entfernt den Hook; der 5-Minuten-Poll übernimmt wieder
  allein (Zustand vor dieser Spec).
- Stalwart: Webhook im Admin deaktivieren/löschen; derselbe Poll-Fallback.
- Code: Revert des PR (Log-Zeile, Tests, Werkzeuge); kein Datenschema berührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0088 („Push weckt Poll, Poll bleibt Wahrheit“, vgl.
  `tests/test_adr_0088_push_weckt_poll_bleibt_wahrheit_doku.py`) nur umsetzend.
- **Rationale:** Es wird eine bestehende Entscheidung in Produktion eingeschaltet, keine Grundsatzentscheidung
  geändert; `missed` bleibt bedingungslos (konsistent mit ADR-0088).

## Changelog

- 2026-10-20: Initial spec created (Restarbeit #2439)
