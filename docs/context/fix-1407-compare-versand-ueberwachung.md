# Kontext: fix-1407-compare-versand-ueberwachung — Compare-Versand ohne Ueberwachung

Issue #1407 (`priority:high`, `bug`), Nebenbefund B13 aus der #1405-Bestandsaufnahme
("Erfolg heisst Wirkung"). Beschreibt `_ping_heartbeat_compare` als "gebaut, aber
nirgends verdrahtet" und fragt nach Anschluss an die Ueberwachung.

**Analysis-First — kein Fix, kein Versand, kein echter Heartbeat-Ping ausgeloest.**

## Analysis

### Type
Bug (Betrieb/Observability), keine Ausgabe-Logik. Haengt an keiner Etappe
von Epic #1372/#1374 (PO-Kommentar 2026-07-29 auf #1407).

### Kernbefund: die im Issue benannte Funktion ist toter Code, nicht "unwired"

`api/routers/scheduler.py:147-167` `_ping_heartbeat_compare()` ist vollstaendig
implementiert (liest `GZ_HEARTBEAT_COMPARE`, pingt fail-soft), hat aber **null
Aufrufer** in der gesamten Scanflaeche (bestaetigt per `grep`). Grund: die
Funktion wurde fuer einen laengst abgeschalteten Versandpfad gebaut.

**Herkunftskette (belegt):**
1. Spec `docs/specs/_archive/modules/issue_253_compare_email.md` (erstellt
   2026-05-20) definiert `_ping_heartbeat_compare()` fuer
   `_run_subscriptions_by_schedule()` in `src/services/compare_subscription.py`
   — der einzige vorgesehene Aufrufer. **Approval-Checkbox der Spec ist bis
   heute leer** (`- [ ] Approved`), Status `superseded_by: issue_1110_compare_mail_v2.md`.
2. Issue #1131 ("Alt-Pfad compare_subscription.py entfernen", CLOSED) hat genau
   diesen Alt-Pfad vollstaendig entfernt: `compare_subscription.py` existiert
   nicht mehr (`find` liefert keinen Treffer), `CompareSubscription`-Modell weg
   (`src/app/loader.py:1682`: `# entfernt — Legacy-Drittstack CompareSubscription
   stillgelegt (#1131)`), Go-Pendant ebenfalls entfernt
   (`internal/scheduler/scheduler.go:536-538`).
3. `_ping_heartbeat_compare()` selbst wurde beim Entfernen **uebersehen** und
   blieb als Waise zurueck — sie ruft niemand mehr an, weil ihr einziger
   vorgesehener Aufrufer nicht mehr existiert. Sie gehoert fachlich zu keinem
   heute aktiven Versandweg.
4. `tests/test_success_status_guard.py:1432-1438` (Ratchet-Baseline aus #1405)
   fuehrt genau diesen Fund bereits als `KNOWN_VIOLATIONS["api/routers/scheduler.py:147"]`
   mit Kommentar: *"MELDEN ja, REPARIEREN nein: der Fix laeuft ausschliesslich
   in Issue #1407"* — #1407 wurde also gezielt fuer diesen Ratchet-Eintrag
   angelegt.

**Der heute aktive Compare-Versandpfad ist ein anderer:**
`api/routers/scheduler.py:129-144 trigger_compare_presets_daily()` →
`src/services/scheduler_dispatch_service.py:120-152 run_compare_presets_daily()`
→ `src/services/dispatch_orchestrator.py:83-148 CompareDispatchStrategy` /
`run_briefing_dispatch("vergleich", ...)`. Dieser Pfad hat **eigene**,
funktionierende Monitoring-Anbindung — nicht ueber `_ping_heartbeat_compare()`.

### Die tatsaechliche aktuelle Ueberwachung (Go-Seite, seit #1346)

`internal/scheduler/scheduler.go:185-205 briefingDispatch()` ist seit Issue
#1346 (gemerged 2026-07-23) der EINE stuendliche Cron-Einstieg (`"0 * * * *"`),
der `tripReports()` UND `comparePresetsDaily()` nacheinander ausloest und danach
**einen gemeinsamen** Heartbeat pingt:

```go
if tripLR != nil && tripLR.Status == "ok" &&
   compareLR != nil && compareLR.Status == "ok" {
    s.pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)
}
```

- `tripLR`/`compareLR` kommen aus `recordRun()` (`:341-359`): `Status="ok"`
  nur wenn `runForAllUsers()` (`:148-183`) fuer JEDEN Nutzer keinen Fehler
  liefert.
- `triggerEndpointForUser()` (`:371-399`) wertet den `failed`-Zaehler aus dem
  Python-Response aus (`parsed.Failed > 0` → Fehler) — das ist die Readiness-
  Bedingung, nicht nur HTTP-200/Liveness.
- **Das ist inhaltlich sauber (Readiness statt Liveness)** — s. Punkt 4 unten.

`/api/scheduler/status` (live abgefragt, kein Versand ausgeloest) fuehrt
`compare_presets_daily` bereits als eigene Zeile mit `last_run.status`/`time`
(`internal/scheduler/scheduler.go:472-534`, Expansion des unified Cron-Entrys
zu 2 Sub-Job-Zeilen). Die Projektregel "last_run-Tracking fuer jeden Job"
ist damit fuer den AKTIVEN Compare-Job bereits erfuellt — unabhaengig vom
Heartbeat-Thema.

### Der reale Betriebsbefund: die Meldeleitung selbst ist in Produktion leer

Direkter Blick in die produktiv geladene Konfiguration (2026-07-30):

- `/home/hem/gregor_zwanzig/.env` (systemd `EnvironmentFile` von `gregor-api.service`)
  enthaelt **keine einzige** `GZ_HEARTBEAT_*`-Variable (`grep` ueber alle
  Variablennamen: 41 `GZ_*`-Keys, keiner heisst `HEARTBEAT`). Damit ist
  `cfg.HeartbeatComparePresets` (`internal/config/config.go:19`,
  `envconfig:"HEARTBEAT_COMPARE_PRESETS" default:""`) leer.
- Bei leerer URL ruft `pingHeartbeat()` (`:428-441`) nur
  `warnMissingHeartbeatOnce()` (`:445-470`) — einmalig pro Prozess eine
  MQ-Nachricht an `infra`.
- **Auch dieser Fallback ist unwirksam:** `internal/notify/mq.go:35-40`
  `SendMQ()` gibt fail-soft `nil` zurueck und ueberspringt den POST komplett,
  wenn `CLAUDE_MQ_SECRET` (Prozess-Env) leer ist. Genau dieselbe `.env`
  enthaelt **kein** `CLAUDE_MQ_SECRET`. Produktions-Logauszug (`journalctl -u
  gregor-api`, taeglich 04:00 UTC, 22.06.–06.07.2026, danach kein
  Leseberechtigung fuer neuere Eintraege dieses Dienstes von diesem Konto aus):

  ```
  [notify] CLAUDE_MQ_SECRET unset, skipping MQ send (subject="Heartbeat-URL für Job \"compare_presets_daily\" nicht konfiguriert")
  [scheduler] WARN: Heartbeat URL empty for compare_presets_daily — MQ sent
  ```

  (Jobname noch `compare_presets_daily` — diese Logs sind vor der #1346-
  Konsolidierung vom 23.07., danach heisst der Job `briefing_dispatch`; das
  Verhalten selbst — leere URL, kein MQ-Send moeglich — aendert sich dadurch
  nicht.)

**Konsequenz:** Weder fuer Compare NOCH fuer Trip feuert aktuell ein echter
BetterStack-Ping ueber diesen internen Mechanismus, UND die als Kompensation
gedachte MQ-Notiz ist ebenfalls stumm. Das ist kein Compare-spezifisches,
sondern ein Konfigurationsproblem der gesamten `briefing_dispatch`-Kette.
Externes HTTP-Health-Monitoring (`henemm-infra/check-gregor20.sh`) laeuft
unabhaengig davon weiter, prueft aber Endpoint-Erreichbarkeit, nicht ob ein
Compare-Briefing tatsaechlich zugestellt wurde.

### BetterStack-Kontingent ist voll (live geprueft, kein Testping ausgeloest)

`GET /api/v2/heartbeats` liefert exakt 10 Eintraege (Kontingent lt.
`~/.claude/CLAUDE.md` = 10): Backup (woechentlich), Auto-Deploy (5 Min),
Claude MQ Health, Server Monitor, Gregor20 Core, n8n Workflows, Mail E2E,
Stalwart Versions-Check, henemm-security (taeglich), Gregor20 Wetterquellen.
**Keiner davon deckt `briefing_dispatch`/Compare ab.** Ein neuer Monitor kann
nicht angelegt werden, ohne einen bestehenden zu ersetzen oder das Kontingent
zu erweitern — PO-Entscheidung noetig, nicht rein technisch loesbar.

### Teilerfolg (Q3): Definition existiert bereits, ist bewusst so gewollt

`src/services/notification_service.py:710-796 send_compare_report()` (AC-5,
Issue #1270): E-Mail-Fehler propagiert ungefangen (zaehlt als `failed` beim
Preset), Telegram-/SMS-Fehler werden geloggt und geschluckt (`:768-794`,
`except Exception: logger.error(...)`, kein `raise`) — zaehlen NICHT als
Fehlschlag. D.h. "Mail zugestellt, Telegram gescheitert" gilt heute schon als
Versand-Erfolg (`_dispatch_due_preset` → `True` → `CompareDispatchStrategy._success`
→ kein `failed`-Inkrement → Go sieht `failed=0` → Job "ok"). Das ist keine
neue Frage, sondern bereits getroffene, dokumentierte Entscheidung (E-Mail =
tragender Kanal, Telegram/SMS = Kuer, identisches Zaehl-Verhalten wie
Trip-Berichte bei `no_weather`).

### Reale Datenlage (Q4, live gemessen, kein Versand ausgeloest)

`data/users/*/compare_presets.json`: 4 Nutzerverzeichnisse insgesamt, nur
`henning` hat Presets (5 Stueck: 4× `schedule=manual`, 1× `schedule=daily`),
`default` hat 0. Ein Ping pro einzelnem Vergleich waere bei dieser Fallzahl
schon unnoetig fein und skaliert nicht (Kontingent=10). Das bestaetigt die
Team-Lead-Vermutung: **ein gemeinsamer Heartbeat fuer den ganzen stuendlichen
Dispatch-Tick** ist der einzig tragfaehige Zuschnitt — genau das Muster, das
`briefingDispatch()` bereits umsetzt.

### Asymmetrie Trip vs. Compare (neuer, eigener Befund — nicht #1407-Scope)

`tripReports()` (`internal/scheduler/scheduler.go:207-246`) hat einen
EIGENEN, edge-getriggerten MQ-Alarm bei Status-Wechsel ok→error (`:231-237`,
Prioritaet `high`, sofort). `comparePresetsDaily()` (`:331-339`) hat **keinen**
solchen eigenen Alarm — ein Compare-Totalausfall wuerde (sobald die Heartbeat-
Kette einmal konfiguriert ist) nur durch die AUSBLEIBENDE BetterStack-Meldung
sichtbar (Timeout-basiert), nicht sofort per MQ wie ein Trip-Ausfall. Das ist
eine echte, aber ANDERE Luecke als die im Issue beschriebene — gehoert in die
Nebenbefund-Triage (#1199) oder ein eigenes kleines Issue, nicht in den Scope
von #1407.

### Affected Files (falls PO den Fix freigibt — NICHT jetzt angefasst)

| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/scheduler.py:147-167` | DELETE | `_ping_heartbeat_compare()` — toter Code, gehoert zu abgeschaltetem Pfad (#1131) |
| `tests/tdd/test_compare_html_email.py:250-267` | DELETE/MODIFY | Test ruft die Funktion isoliert auf (AC-7) — pruefte nie den echten Aufrufpfad, muss mit der Funktion verschwinden oder auf den aktiven Pfad umgezogen werden |
| `tests/test_success_status_guard.py:1432-1438` | MODIFY | `KNOWN_VIOLATIONS`-Eintrag B13 entfernen, sobald der Fund aufgeloest ist |
| `docs/specs/_archive/modules/issue_253_compare_email.md` | — | bleibt Archiv, keine Aenderung noetig |
| *(ausserhalb Repo)* BetterStack | NEU (PO-Entscheidung) | Heartbeat-Monitor fuer `briefing_dispatch` anlegen — Kontingent 10/10 voll, Ersatz oder Erweiterung noetig |
| `/home/hem/gregor_zwanzig/.env` (Prod), Staging-Aequivalent | ADD (Infra, ausserhalb Repo-Scope) | `GZ_HEARTBEAT_COMPARE_PRESETS=<neue URL>` + `CLAUDE_MQ_SECRET=<Wert>` eintragen, Dienste neu starten |

### Scope Assessment

- Repo-seitig: 1 Datei loeschen (Funktion), 2 Testdateien anpassen — deutlich
  unter 250 LoC (eher Abbau als Zuwachs).
- **Der wirksame Teil des Fixes liegt ausserhalb des Repos** (BetterStack-
  Monitor anlegen + zwei Env-Dateien pflegen + Dienste neu starten) — das ist
  kein Python-/Go-Code-Fix, sondern eine Infra-/Konfigurationsaenderung nach
  `~/.claude/CLAUDE.md`-Konventionen (Heartbeat anlegen, `henemm-infra`).
- Risk Level: NIEDRIG fuer die Code-Aenderung (Entfernen von totem Code),
  MITTEL fuer die Konfigurationsaenderung (Prod-`.env` + Neustart zweier
  Dienste, PO-Entscheidung zum Kontingent noetig).

### Empfohlene Reihenfolge

1. PO-Entscheidung: welcher bestehende BetterStack-Monitor weicht (oder
   Kontingent-Erweiterung) — Voraussetzung fuer alles Weitere.
2. `CLAUDE_MQ_SECRET` in Prod-`.env` ergaenzen (unabhaengig vom Kontingent,
   sofort moeglich) — stellt wenigstens den Fail-Soft-Fallback wieder her.
3. Neuen Heartbeat anlegen, `GZ_HEARTBEAT_COMPARE_PRESETS` in Prod + Staging
   eintragen, Dienste neu starten, echten Lauf abwarten und Ping im
   BetterStack-Protokoll bestaetigen.
4. `_ping_heartbeat_compare()` + zugehoerige Tests entfernen (Aufraeumen des
   toten Codes, Ratchet-Eintrag B13 aufloesen).
5. Asymmetrie Trip/Compare (fehlender edge-getriggerter Compare-Alarm) als
   eigenen, kleinen Nebenbefund einordnen (#1199 oder eigenes Issue) — nicht
   Teil von #1407.

### Risiko-Notizen (falsch beruhigender Ping)

- Ein kuenftiger Entwickler koennte versucht sein, Compare separat und
  bedingungslos zu pingen, um den fehlenden Alarm (Punkt "Asymmetrie") zu
  "reparieren" — das wuerde die #1346-Konsolidierung rueckgaengig machen und
  einen Trip-Ausfall wieder verdecken. Nicht tun; stattdessen einen
  eigenstaendigen Compare-Alarm nach Trip-Vorbild ergaenzen, OHNE den
  gemeinsamen Heartbeat zu entkoppeln.
- "Erfolg" ist Job-Ebene (kein Preset schlug fehl), nicht Kanal-Ebene: ein
  Telegram-/SMS-Fehlschlag zaehlt bewusst nicht als Fehler (#1270 AC-5). Wer
  das nicht kennt, haelt es leicht faelschlich fuer eine Monitoring-Luecke.
- "0 faellige Presets in dieser Stunde" zaehlt als Erfolg (korrekt, die
  meisten Presets sind `schedule=manual` oder nur zu bestimmten Stunden
  faellig) — aber missverstaendlich, wenn jemand das als Beleg fuer
  tatsaechlich zugestellte Mails liest statt als "Job lief fehlerfrei durch".
- Nur `CLAUDE_MQ_SECRET` zu setzen, OHNE die BetterStack-URL zu konfigurieren,
  erzeugt trügerische Sicherheit: die MQ-Nachricht kommt dann nur bei FEHLENDER
  Konfiguration (einmalig), NICHT bei einem echten Job-Fehler — ein realer
  Compare-Ausfall bliebe weiterhin ohne sofortige Meldung.

### Open Questions

- [ ] Welcher der 10 bestehenden BetterStack-Monitore weicht, oder wird das
      Kontingent erweitert (Kostenfrage, PO-Entscheidung)?
- [ ] Soll Compare einen eigenen edge-getriggerten MQ-Alarm nach Trip-Vorbild
      bekommen (separates Issue) oder reicht der gemeinsame Heartbeat plus
      BetterStack-Timeout-Erkennung?
