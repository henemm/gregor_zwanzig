---
entity_id: fix_2286_compare_betrieb_health
type: bugfix
created: 2026-10-21
updated: 2026-10-21
status: draft
version: "1.0"
issue: 2286
epic: 2345
workflow: fix-2286-compare-betrieb-health
tags: [scheduler, ortsvergleich, observability, briefing_health, monitoring]
---

# Fix #2286 — Ortsvergleich-Versand: gleiche Betriebs-Beobachtbarkeit wie der Trip-Versand

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich-Versand (Cron-Job `compare_presets_daily`) fällt heute **still** aus, wo der Trip-Versand
laut Alarm schlägt. Vier konkrete Lücken, alle im selben Themenfeld (Epic #2345, Etappe P4):

1. **Keine Job-weite Meldung.** Der Trip-Versand meldet „Totalausfall" und „wieder OK" per MQ an `infra`;
   der Vergleichs-Versand bucht nur den Lauf (`recordRun`), eine Flanke gibt es nicht.
2. **Provider-Störung wird als Erfolg gezählt.** Haben alle Orte eines Vergleichs keine Wetterdaten, geht im Cron
   trotzdem eine Mail aus lauter Fehlerzellen raus und zählt als „sent". Nur der Handversand macht daraus ein
   `no_weather`. Damit könnte eine Totalausfall-Meldung im Hauptszenario („Provider-Störung") nie feuern.
3. **Eine kaputte Datei legt alle Vergleiche eines Nutzers still.** Trips und Vergleiche liegen im selben Ordner
   `briefings/`. Eine einzige unlesbare Datei (auch ein Trip) lässt den strengen Lader werfen; der Dispatch liefert
   `(0,0)`, Go sieht „ok". Der Trip-Pfad überspringt dagegen nur die kaputte Datei.
4. **Korrupt-Zählung falsch etikettiert.** Unlesbare Dateien werden als „Kaputter Trip" gemeldet, auch wenn es ein
   Vergleich war; ein lesbares, aber strukturell kaputtes Vergleichs-Preset wird gar nicht gezählt.

Dazu zwei Angleichungen: gleiche Feldmenge beider Sub-Jobs in `/api/scheduler/status` und im Python-Body, und
gleicher Job-Zuschnitt bei amtlichen Warnungen (beim Trip laufen sie im `alert_checks`-Job mit, beim Vergleich
bisher in einem eigenen Job). Der Unterschied beim `smtp_guard` bleibt bewusst bestehen und wird begründet.

## Scope

**In Scope**

- Job-weite Flanke (Totalausfall / wieder OK) für `compare_presets_daily`, als geteilter Helper mit dem Trip-Pfad.
- Cron-Versand: „alle Orte ohne Daten" ⇒ `no_weather` ⇒ `failed` (gleiche Regel wie Handversand).
- Toleranter Lader im Compare-Dispatch: kaputte Datei überspringen, übrige Vergleiche versenden.
- Korrupt-Zählung nach Art (`trip` / `vergleich` / `unbekannt`), inkl. strukturell kaputter Vergleichs-Presets;
  MQ-Betreff je Art.
- `briefing_health`: zusätzlich `corrupt_briefings_total` und `corrupt_briefings_by_kind`.
- Compare-Body ergänzt `duration_s`; gleiche Feldmenge beider Sub-Jobs.
- `compare_official_alert_checks` geht in `compare_alert_checks` auf; Infra-Skript-Gegenstück.
- `smtp_guard`-Begründung im Code, WARNING-Log im Trip-Guard.

**Out of Scope**

- Pending/Nachlieferung für Vergleiche und `open_pending{kind}` für Compare — bleibt **#1777** (Vergleich kennt
  strukturell kein Pending; `compare_slot_scheduler.py` prüft nur Stundengleichheit).
- `dataWriteSelftest()` — zweite Flankenvorlage, bleibt unberührt.
- Umbenennung oder Entfernen von `corrupt_trips_*` in `briefing_health` (Monitoring-Vertrag, nur Ergänzung).
- Änderungen am Trip-Versandverhalten außer dem WARNING-Log im Guard.

## Source

- **Dateien:** `internal/scheduler/scheduler.go`, `internal/scheduler/briefing_health.go`,
  `src/services/trip_report_scheduler.py`, `src/services/scheduler_dispatch_service.py`,
  `src/app/loader.py`, `src/services/dispatch_orchestrator.py`, `api/routers/scheduler.py`
- **Identifier:** `tripReports()`, `comparePresetsDaily()`, `briefingDispatch()`, `Status()`,
  `aggregateCorruptTrips`, `record_corrupt_trip_observability`, `load_compare_presets`,
  `_load_presets_for_dispatch`, `send_one_compare_preset`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/scheduler/trip-reports` · Compare-Pendant · `compare-alert-checks` (Python-Core) | Upstream-Endpoint | Liefern `{status,count,failed,duration_s}` je Nutzer an den Go-Scheduler |
| `load_compare_presets` (`src/app/loader.py`) | Upstream-Funktion | Laden der Vergleichs-Presets aus `briefings/` |
| MQ-Notifier (`/home/hem/claude-mq/send.sh` → `infra`) | Upstream-Dienst | Totalausfall-/Recovery- und Korrupt-Meldungen |
| `GET /api/scheduler/status` (`statusGuard`, `GZ_STATUS_TOKEN`) | Downstream-Vertrag | Liefert `jobs[]` und `briefing_health` an den externen Monitor |
| `henemm-infra/scripts/check-gregor20.sh` | Downstream-Konsument | Liest `jobs[].last_run.*`, `SOFORT_ALARM_JOBS`, `ALARM_JOB_IDS` |
| #2149 Nutzer-Flankenalarme (`sendBundledUserAlerts`) | Bestehendes Verhalten | Bleibt unverändert, läuft parallel zur Job-Flanke |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; gestützt auf ADR-0018 (Provider-Fallback ohne Kaschieren) und ADR-0023 (gemeinsames Briefing-Subscription-Modell)
- **Rationale:** Die Änderung gleicht den Vergleichs-Versand an bereits bestehende Trip-Muster an (Flanke, Korrupt-Beobachtbarkeit, Job-Zuschnitt) und wendet ADR-0018 im Cron so an wie schon im Handversand. Keine Entscheidungsfläche wird neu entschieden oder rückgängig gemacht; der smtp_guard-Unterschied bleibt bestehen und wird nur im Code begründet.

## Estimated Scope

- **Files:** 7 produktive Dateien (Go 2, Python 5) + 1 Infra-Skript + ca. 5 Testdateien + 3 Doku-Dateien
- **LoC produktiv:** ca. +190 / -60; Tests zusätzlich. Das Limit 250/Workflow wird voraussichtlich überschritten,
  deshalb vor `/50-implement` `workflow.py set-field loc_limit_override 500` (Entscheidung: ein Workflow für das
  ganze Zielbild, keine Rest-Abspaltung).
- **Risiko:** MEDIUM — zentraler Versandpfad und Monitoring-Vertrag; sichtbare Verhaltensänderung bei
  Provider-Totalausfall (keine Fehlerzellen-Mail mehr, stattdessen Meldung).

## Betroffene Dateien

| Datei | Änderungstyp | Inhalt |
|---|---|---|
| `internal/scheduler/scheduler.go` | MODIFY | Flanken-Helper aus `tripReports()` herausziehen (Parameter: jobID, MQ-Betreff, Texte); `comparePresetsDaily()` nutzt ihn; Job und Handler `compare_official_alert_checks` entfernen |
| `internal/scheduler/briefing_health.go` | MODIFY | `by_kind` aus `corrupt_trips.json` aggregieren → `corrupt_briefings_total`, `corrupt_briefings_by_kind` |
| `src/services/trip_report_scheduler.py` | MODIFY | Scanner klassifiziert Art, prüft Vergleichs-Struktur, schreibt `by_kind`, MQ-Betreff je Art |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Tolerantes Laden im Dispatch; Cron: alle Orte fehlerhaft ⇒ `no_weather` ⇒ failed |
| `src/app/loader.py` | MODIFY | toleranter Modus für `load_compare_presets` (überspringen statt werfen) |
| `src/services/dispatch_orchestrator.py` | MODIFY | Begründungs-Kommentar `smtp_guard`; WARNING-Log im Trip-Guard |
| `api/routers/scheduler.py` | MODIFY | Compare-Body + `duration_s`; `compare-alert-checks` führt auch den Official-Service aus; Official-Endpoint entfällt |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | MODIFY (infra) | `compare_official_alert_checks` aus `ALARM_JOB_IDS` (Zeile ca. 865) entfernen — **infra zuerst** |
| `tests/tdd/test_compare_preset_loader.py` | MODIFY | `:303-327` von „`(0,0)` + ERROR-Log" auf „übrige Presets laufen, kaputte Datei übersprungen" umstellen |
| `docs/specs/modules/dispatch_orchestrator.md`, `scheduler_multi_user.md`, `docs/reference/api_contract.md` | MODIFY | Doku-Nachzug |

## Implementierungsdetails

### 1. Flanken-Helper (Go)

Die Logik aus `tripReports()` (`lastHardStatus`-Map, MQ high „Totalausfall" bei Wechsel nach `error`, MQ normal
„wieder OK" bei `error`→`ok`, `partial` überschreibt den gespeicherten Status nicht) wird als Helper mit den
Parametern jobID, Betreff und Texten herausgezogen. Beide Sub-Jobs rufen ihn auf. Compare-Texte:
„Vergleichs-Briefing-Totalausfall (#2286)" und „Vergleichs-Briefing wieder OK (#2286)". „error" bedeutet wie beim
Trip: **mindestens ein Nutzer** hat `failed>0` (HTTP ≥ 400, Transportfehler oder `failed>0` im Body); Rangfolge
`error > partial > ok` bleibt. Der Nutzer-Flankenalarm aus #2149 (`sendBundledUserAlerts`) gilt bereits für beide
Sub-Jobs und bleibt unverändert; die Job-weite Meldung geht an `infra`, der Nutzeralarm an den Nutzer — zwei
Meldungen pro Störung mit verschiedenen Empfängern sind gewollt (beim Trip heute identisch).

### 2. Provider-Totalausfall im Cron (Python)

In `send_one_compare_preset` wird dieselbe Regel wie im Handversand angewandt (`weather_failure_as_outcome`):
haben **alle** Orte keine Daten, ist das Ergebnis `no_weather`, es wird **keine** Mail gerendert/versendet und der
Preset zählt als `failed`. Einzelne fehlende Orte bei sonst vorhandenen Daten bleiben wie bisher (Mail mit
Hinweis). Begründung: ADR-0018 (Fallback nicht kaschieren); ohne diese Regel ist die Flanke für ihr eigenes Motiv
nicht erreichbar.

### 3. Toleranter Lader (Python)

`load_compare_presets` bekommt einen toleranten Modus (kaputte Datei überspringen, WARNING-Log mit Dateiname,
übrige Dateien laden). `_load_presets_for_dispatch` nutzt ihn. Das Überspringen zählt **nicht** als `failed`;
sichtbar bleibt die Datei über Korrupt-Zähler und MQ (nicht über `SOFORT_ALARM_JOBS`). Der Trip-Pfad verhält sich
bereits so (`loader.py:1666-1675`).

### 4. Korrupt-Zählung nach Art (Python)

Es bleibt bei **einem** Scanner und **einem** Dedup-Stand (`record_corrupt_trip_observability`,
`diagnostics/corrupt_trips.json` `{notified, last_skipped_count, last_run}`), verallgemeinert:

- Jede Datei in `briefings/` wird als `trip`, `vergleich` oder `unbekannt` klassifiziert.
- Unparsbare Datei: Rohtext-Heuristik — Muster `"kind"\s*:\s*"vergleich"` ⇒ `vergleich`, sonst `unbekannt`
  (kein Raten; ein ehrliches `unbekannt`).
- Parsbares Vergleichs-Preset: zusätzliche Strukturprüfung per `compare_preset_from_dict`; scheitert sie ⇒
  `vergleich`.
- Parsbarer Trip mit kaputter Struktur ⇒ `trip` (wie bisher).
- `corrupt_trips.json` bekommt **zusätzlich** das Feld `by_kind` (`{"trip":n,"vergleich":n,"unbekannt":n}`);
  die alten Felder bleiben.
- MQ-Betreff je Art: `trip` → „Kaputter Trip", `vergleich` → „Kaputter Vergleich", `unbekannt` →
  „Kaputte Briefing-Datei". Dedup weiter per Dateiname in `notified`, also keine Doppelmeldung — auch weil beide
  Sub-Jobs nacheinander laufen (`briefingDispatch()`), nie gleichzeitig.

### 5. `briefing_health` (Go)

`aggregateCorruptTrips` liest zusätzlich `by_kind` und liefert `corrupt_briefings_total` sowie
`corrupt_briefings_by_kind{trip,vergleich,unbekannt}` — **nur Zahlen** (Datenschutz #252: keine Nutzer-IDs,
keine Dateinamen). `corrupt_trips_*` bleibt unverändert (Monitoring-Vertrag, nur Ergänzung). Fehlt `by_kind`
(Altbestand), zählt der Rest als `unbekannt`.

### 6. Gleiche Feldmenge der Sub-Jobs

Compare-Body wird `{status,count,failed,duration_s}` wie beim Trip. `/status` führt beide Jobs bereits mit
derselben Struktur (`last_run.*`, `deadline_aborts`); `deadline_aborts` bleibt bei Compare praktisch 0, weil der
Body kein `reason` trägt — das ist kein Schemaunterschied.

### 7. Job-Zuschnitt amtliche Warnungen

`compare_official_alert_checks` geht in `compare_alert_checks` auf (Muster Trip: amtliche Warnungen laufen im
`alert_checks`-Job mit). Der Endpoint `compare-alert-checks` führt beide Services nacheinander aus, **jeden in
eigenem try-Block** (Fehlerisolation), und summiert `count`/`failed`; wirft einer, läuft der andere trotzdem und der
Fehler zählt als `failed`. Go-Job und Handler `compare_official_alert_checks` (`scheduler.go:343-356`, `:820-854`)
sowie der Python-Endpoint entfallen. Infra: `check-gregor20.sh` entfernt die ID aus `ALARM_JOB_IDS`, sonst meldet
der Monitor nach dem Deploy einen fehlenden Job.

### 8. smtp_guard

Der Unterschied bleibt (`dispatch_orchestrator.py`: Trip `smtp_guard=True`, Compare `False`) und wird im Code
begründet: Compare zählt pro Preset (Altverhalten #1207) und versendet an die Empfänger des Nutzers, Sendefehler
zählen dort als `failed`; der Trip-Guard prüft die **globale** SMTP-Konfiguration, deren Fehlen ein Deploy-Fehler
ist (fangen `/api/health` und `prod_selftest`). „Kein SMTP ⇒ failed" würde
`test_dispatch_orchestrator.py:310-348` brechen (CI hat kein SMTP). Neu: der Trip-Guard schreibt bei fehlendem SMTP
ein WARNING-Log statt still `(0,0)` zu liefern.

## Acceptance Criteria

**AC-1:** (Totalausfall-Meldung) Given der Vergleichs-Versand läuft für mindestens zwei Nutzer und bei einem davon
scheitert der Versand eines fälligen Vergleichs (Fehler bei Wetterdaten, E-Mail oder Fälligkeitsprüfung) /
When der Job `compare_presets_daily` durchläuft und vorher zuletzt „ok" war / Then geht genau eine Meldung
„Vergleichs-Briefing-Totalausfall" mit hoher Dringlichkeit an `infra` (nicht pro Nutzer, sondern Job-weit), und der
Job steht in `/api/scheduler/status` auf „error"; die Meldung enthält keine Nutzerkennung.

**AC-2:** (Recovery und partial) Given der Vergleichs-Versand hat zuletzt „Totalausfall" gemeldet /
When der nächste Lauf ohne Fehler endet, Then geht genau eine Meldung „Vergleichs-Briefing wieder OK" (normale
Dringlichkeit) an `infra`; endet der Lauf dagegen nur „teilweise" (partial, z. B. Zeitbudget), bleibt der gespeicherte
Status „error" und es geht weder eine Recovery- noch eine neue Totalausfall-Meldung raus; ein weiterer Fehler-Lauf
im Zustand „error" erzeugt keine zweite Totalausfall-Meldung (nur der Wechsel meldet).

**AC-3:** (Doppelmeldung bewusst) Given ein Nutzer hat dauerhaft fehlschlagende Vergleichs-Versände und die
#2149-Nutzer-Flanke greift / When der Job-weite Totalausfall ebenfalls auslöst / Then gehen beide Meldungen
unabhängig raus — die Job-weite an `infra`, der Nutzeralarm an die Kanäle genau dieses Nutzers —, und ein zweiter,
unbeteiligter Nutzer erhält keinen Nutzeralarm (Mandantentrennung, Test mit zwei verschiedenen Nutzern).

**AC-4:** (Provider-Totalausfall im Cron) Given ein Vergleich mit mehreren Orten, bei dem der Wetter-Provider für
**alle** Orte keine Daten liefert / When der Cron den Vergleich zur fälligen Stunde versendet / Then wird keine Mail
aus lauter Fehlerzellen verschickt, der Vergleich zählt als „fehlgeschlagen" (`failed`) mit Grund „keine
Wetterdaten" — exakt wie beim Handversand —, und der Ausfall fließt in AC-1 ein; fehlen nur einzelne Orte, geht die
Mail wie bisher mit Hinweis raus.

**AC-5:** (kaputte Datei legt nicht mehr alle still) Given ein Nutzer hat drei gültige, fällige Vergleiche und eine
unlesbare JSON-Datei im Ordner `briefings/` (egal ob Trip oder Vergleich) / When der Cron-Versand für diesen Nutzer
läuft / Then werden die drei gültigen Vergleiche versendet, die kaputte Datei wird übersprungen (WARNING-Log mit
Dateiname), der Lauf zählt für sie **nicht** als `failed`, und die Vergleiche eines zweiten Nutzers ohne kaputte
Datei sind in keiner Weise betroffen.

**AC-6:** (Korrupt-Zählung nach Art) Given ein Nutzer hat je eine kaputte Datei, die (a) unlesbar ist und
`"kind": "vergleich"` enthält, (b) unlesbar ohne erkennbare Art ist, (c) ein lesbares Vergleichs-Preset mit kaputter
Struktur ist, und (d) ein kaputter Trip ist / When der Scanner läuft / Then zählt `by_kind` (a) und (c) als
„vergleich", (b) als „unbekannt" und (d) als „trip"; die MQ-Meldung trägt je Art den passenden Betreff („Kaputter
Vergleich", „Kaputte Briefing-Datei", „Kaputter Trip"); jede Datei wird nur einmal gemeldet (kein Duplikat durch
den zweiten Sub-Job, gleiche Datei im nächsten Lauf löst keine neue Meldung aus); der Stand wird je Nutzer geführt
und vermischt sich nicht mit dem eines zweiten Nutzers.

**AC-7:** (briefing_health nur ergänzt, nur Zahlen) Given zwei Nutzer mit zusammen mehreren kaputten Dateien
verschiedener Art / When `/api/scheduler/status` (mit `X-GZ-Status-Token`) abgerufen wird / Then enthält
`briefing_health` zusätzlich `corrupt_briefings_total` und `corrupt_briefings_by_kind` mit den Summen über beide
Nutzer, die bisherigen Felder `corrupt_trips_*` sind unverändert vorhanden, und die Antwort enthält weder
Nutzerkennungen noch Dateinamen (Datenschutz).

**AC-8:** (gleiche Feldmenge der Sub-Jobs) Given der Scheduler hat beide Sub-Jobs (`trip_reports_hourly`,
`compare_presets_daily`) mindestens einmal ausgeführt / When `/api/scheduler/status` und der Python-Antwort-Body
beider Endpoints gelesen werden / Then besitzen beide Jobs in `/status` dieselbe Feldmenge (`last_run.*`,
`deadline_aborts`), und beide Python-Bodies enthalten `status`, `count`, `failed` und `duration_s`.

**AC-9:** (amtliche Warnungen im Compare-Alarm-Job) Given der Scheduler ist gestartet / When die Jobliste
(`/status`) gelesen wird und `compare_alert_checks` läuft / Then existiert der Job `compare_official_alert_checks`
nicht mehr, `compare_alert_checks` prüft im selben Lauf Regen-/Radar-Alarme **und** amtliche Warnungen, und wirft
einer der beiden Teile einen Fehler, wird der andere trotzdem ausgeführt und der Fehler zählt als `failed`
(Fehlerisolation); die Alarme erreichen weiterhin nur die Empfänger des jeweiligen Nutzers.

**AC-10:** (Infra-Gegenstück) Given der Job `compare_official_alert_checks` ist entfernt / When der externe Monitor
`check-gregor20.sh` nach dem Deploy läuft / Then meldet er keinen fehlenden Job, weil die ID aus `ALARM_JOB_IDS`
entfernt wurde — die Änderung in `henemm-infra` ist **vor** dem Prod-Deploy live, und `compare_alert_checks` sowie
`compare_presets_daily` bleiben überwacht.

**AC-11:** (smtp_guard begründet) Given der Trip-Versand läuft ohne vollständige SMTP-Konfiguration / When der
Trip-Guard greift / Then liefert er weiterhin keinen Fehler-Zähler (`(0,0)`), schreibt aber ein WARNING-Log; der
Compare-Versand bleibt ohne globalen Guard und zählt Sendefehler pro Vergleich als `failed`; die Begründung für
den Unterschied steht als Kommentar an beiden Stellen im Code.

## Testplan

Kern-Tests (deterministisch, ohne Netz/Live-Dienste), benannt nach Verhalten:

**Go (`internal/scheduler/`)**

- `compare_totalausfall_flanke_test.go`: Totalausfall-Meldung beim Wechsel ok→error (AC-1); Recovery error→ok;
  partial ändert den gespeicherten Status nicht; zweiter Fehler-Lauf ohne neue Meldung (AC-2); Meldung ohne
  Nutzerkennung; Zusammenspiel mit Nutzeralarm, zwei verschiedene Nutzer, nur der betroffene wird alarmiert
  (AC-3). Trip-Flanke läuft durch denselben Helper weiter grün (Regression: `timeout_kein_ausfall_test.go`).
- `briefing_health_corrupt_by_kind_test.go`: Aggregation `corrupt_briefings_*` über zwei Nutzer; Altbestand ohne
  `by_kind` ⇒ `unbekannt`; `corrupt_trips_*` unverändert; keine IDs/Dateinamen in der Ausgabe (AC-7;
  ergänzt `scheduler_status_privacy_test.go`).
- `status_beide_subjobs_gleiche_felder_test.go`: Feldmengen-Vergleich `trip_reports_hourly` vs.
  `compare_presets_daily` (AC-8); `compare_official_alert_checks` nicht mehr registriert (AC-9).

**Python (`tests/tdd/`)**

- `test_compare_preset_loader.py` — **geändert** (`:303-327`): statt `(0,0)` + ERROR-Log bei `{not valid json`
  jetzt „übrige Presets werden geladen, kaputte Datei übersprungen, WARNING-Log" (AC-5).
- `test_compare_cron_provider_totalausfall.py`: alle Orte ohne Daten ⇒ `no_weather`, keine Mail, `failed=1`;
  ein Ort fehlt ⇒ Mail geht raus (AC-4); Parität zur Handversand-Regel.
- `test_compare_dispatch_korrupte_datei_toleranz.py`: drei gültige Vergleiche + kaputte Datei ⇒ drei versendet,
  `failed=0`; zweiter Nutzer unberührt (AC-5, zwei Nutzer).
- `test_corrupt_briefings_by_kind.py`: vier Fälle (a)-(d) aus AC-6, MQ-Betreff je Art, Dedup über beide Läufe,
  Nutzer-Isolation, Rückwärtskompatibilität der Altfelder von `corrupt_trips.json`.
- `test_scheduler_body_gleiche_felder.py`: beide Endpoints liefern `status,count,failed,duration_s` (AC-8).
- `test_compare_alert_checks_faltet_amtliche_warnungen.py`: beide Services laufen; wirft der eine, läuft der
  andere; Summierung `count`/`failed`; Official-Endpoint existiert nicht mehr (AC-9).
- `test_dispatch_orchestrator.py` (ergänzt): Trip-Guard ohne SMTP ⇒ `(0,0)` **und** WARNING-Log; Compare ohne
  Guard unverändert (AC-11; bestehender Test `:310-348` bleibt grün).

**Mutations-Gegenprobe (Adversary, Pflicht):** Flanken-Bedingung invertieren; `partial` überschreibt Status;
`by_kind`-Zuordnung vertauschen; Toleranz im Lader wieder auf `strict`; `no_weather`-Regel entfernen;
Official-Teil nicht in eigenem try — jeweils muss ein benannter Test rot werden.

## Staging-Verifikation

- Wegwerf-Nutzer `gregor-test+…` anlegen (Hauptkonto schickt an `gregor-staging@`); `id` ist Pflicht,
  Vergleich zusätzlich `schedule`.
- Fall A: Vergleich mit unauflösbaren Orten ⇒ Sammellauf (Kern 8001 + `X-GZ-Core-Auth`, da Go-Trigger Admin-only
  und Staging keinen Admin hat) ⇒ `failed>0`, keine Mail aus Fehlerzellen.
- Fall B: zusätzlich eine kaputte JSON-Datei in `briefings/` des Wegwerf-Nutzers (Staging-Datenbestand ist für
  `hem` nicht lesbar ⇒ Anlage über die API, sonst `NOT_MEASURABLE_ON_STAGING` benennen) ⇒ gültige Vergleiche
  werden versendet.
- `GET /api/scheduler/status` mit `X-GZ-Status-Token`: `briefing_health.corrupt_briefings_*` vorhanden,
  `corrupt_trips_*` unverändert, beide Sub-Jobs mit gleichen Feldern, `last_run` aktuell, Job
  `compare_official_alert_checks` fehlt.
- Mail-Änderung: Test-Mail über Wegwerf-Nutzer, IMAP-Verifikation mit `briefing_mail_validator.py` bzw. für
  Vergleich `email_spec_validator.py` (nur Exit 0 zählt).
- Zwei verschiedene Nutzer im selben Lauf: Meldungen und Zähler bleiben je Nutzer getrennt.

## Risiken

- **Monitoring-Vertrag:** `check-gregor20.sh` liest `jobs[].last_run.*`, `deadline_aborts`,
  `SOFORT_ALARM_JOBS={trip_reports_hourly, compare_presets_daily}` und mehrere `briefing_health`-Felder (nicht
  `corrupt_trips_*`). Es werden nur Felder ergänzt, nichts umbenannt. Entfernt wird allein der Job
  `compare_official_alert_checks` — dafür ist die Infra-Änderung nötig.
- **Reihenfolge — Infra zuerst:** Der Arbeitsbaum von `henemm-infra` ist sofort live (Cron läuft aus dem Repo).
  Die ID-Entfernung wird daher **vor** dem Prod-Deploy gemacht: Zwischen Infra-Änderung und Deploy läuft der alte
  Job nur unbeobachtet weiter; in umgekehrter Reihenfolge würde der Monitor den weggefallenen Job als fehlend
  melden. Mutationen am Skript nur in einer Kopie.
- **Alarm-Lautstärke:** Provider-Totalausfall zählt künftig als `failed` und löst über `SOFORT_ALARM_JOBS` sofort
  Alarm aus — gewollt (kein stilles Verwerfen), aber spürbare Verhaltensänderung. Die kaputte Datei zählt bewusst
  **nicht** als `failed` (nur Korrupt-Zähler + MQ).
- **Doppelmeldung** Job-weite Flanke + Nutzeralarm: bewusst (verschiedene Empfänger), wie beim Trip.
- **Datenschutz/Mandanten:** `/status` nur Zahlen und Zeitstempel; Dedup-Stand pro Nutzer unter
  `data/users/<user_id>/diagnostics/`; kein Fallback auf `"default"`.
- **Rohtext-Heuristik** kann einen unlesbaren Vergleich als `unbekannt` führen — bewusst ehrlich statt geraten.
- **Datenstand:** Persistenzänderung ist nur das zusätzliche Feld `by_kind` in `corrupt_trips.json`
  (Read-Modify-Write mit Merge, alte Felder bleiben; Altbestand ohne `by_kind` bleibt lesbar).

## Doku-Nachzug

- `docs/specs/modules/dispatch_orchestrator.md` (`smtp_guard`-Begründung, Cron-`no_weather`-Regel),
  `docs/specs/modules/scheduler_multi_user.md` (Compare-Flanke, Job-Zuschnitt), `docs/reference/api_contract.md`
  (Compare-Body `duration_s`, `briefing_health.corrupt_briefings_*`, entfallener Official-Endpoint/Job).
- Issue #2286 erst nach Staging-Verifikation, Prod-Deploy und Selftest-Exit 0 schließen; PR-Text „Refs #2286".

## Changelog

- 2026-10-21: Erstfassung (Entwurf, wartet auf PO-Freigabe der ACs).
