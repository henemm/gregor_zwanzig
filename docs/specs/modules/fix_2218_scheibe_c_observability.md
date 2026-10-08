---
entity_id: fix_2218_scheibe_c_observability
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.1"
tags: [observability, mail, scheduler, alerts, health, capture, track-resolution]
---

# Observability-Restposten (Issue #2218, Scheibe C, Epic #2505)

## Approval

- [ ] Approved — PO (Henning)

## Purpose

Sechs Beobachtbarkeits-Lücken aus dem Sammel-Issue #2218 bleiben nach den Scheiben A
(Zustellstatus) und B (Alarm-Abruf-Ausfälle) offen. Sie haben eines gemeinsam: Das
System tut etwas oder tut es nicht, und der Betreiber kann es hinterher nicht
nachweisen. Diese Scheibe schließt alle sechs in einem Zug, damit #2218 vollständig
erledigt ist und nichts abgespalten wird:

| Eintrag | Lücke heute |
|---|---|
| **C5-53** | Eine Mail gilt als „gesendet", im Log steht aber keine Message-ID. Ob und welche Mail zugestellt wurde, lässt sich nicht gegen das Postfach prüfen. |
| **C5-15** | `/api/scheduler/status` meldet `running: true` fest verdrahtet, auch wenn der Scheduler nie gestartet oder schon gestoppt wurde. |
| **C5-37** | Liefert GeoSphere INCA eine leere Antwort, bucht das Health-Journal `ok` statt `fallback`. |
| **B2-71** | Der Mitschnitt der Alarm-Eingangsdaten hält je Verzeichnis nur 50 Dateien; ein häufiger Schreiber verdrängt die Mitschnitte der übrigen Quellen binnen weniger Stunden. |
| **C5-47** | `implausible_measurement` schreibt in jeder 15-Minuten-Runde eine Zeile je Etappe, auch wenn sich nichts ändert (Journal-Rauschen). |
| **C5-02** | Der Alarm-Pfad ist im Betrieb blind: vier der fünf Alarm-Endpunkte sind auf Prod nicht per Admin-Proxy auslösbar, die Fenstergrenze einer Alarmprüfung wird nirgends protokolliert, und ein Nowcast-Ausfall im Trip-Radar-Alarm bucht keinen `alert_fetch`. |

Es ändert sich **nicht**, ob, wann oder worüber alarmiert wird, und es entsteht keine
neue Nutzermeldung. Einzige Außenwirkung: eine zusätzliche Kopfzeile `Message-ID` in
jeder ausgehenden Mail. Die Scheibe betrifft alle vier Kanäle gleichermaßen nicht
(Betreiber-Beobachtbarkeit); die Mail-Änderung (C5-53) betrifft nur den Kanal E-Mail.

## Source

- **Python-Core:** `src/output/channels/email.py` (C5-53),
  `src/services/radar_service.py` (C5-37), `src/services/alert_input_capture.py`
  (B2-71), `src/services/track_resolution.py` + `src/services/track_resolution_health.py`
  (C5-47), `src/services/trip_alert.py` (C5-02b/c)
- **Go-API:** `internal/scheduler/scheduler.go` (C5-15),
  `internal/scheduler/briefing_health.go` (nur Kommentar, C5-47),
  `internal/router/router.go` (C5-02a)
- **Doku:** `docs/reference/api_contract.md`
- **Identifier:** `EmailOutput.build_mime_message` / `EmailOutput.send` /
  `EmailOutput._dial_and_send`, `Scheduler.Start` / `Stop` / `Status`,
  `RadarNowcastService._fetch_geosphere_inca`, `alert_input_capture._prune`,
  `track_resolution._melde_unplausible_messung`,
  `track_resolution_health.record_track_resolution_failure`, `trip_alert._delta_event_window` /
  `aufenthaltsfenster_min`

**Schicht:** Python-Core und Go-API. Kein Frontend.

## Estimated Scope

- **LoC produktiv:** ca. +235 / −33 (v1.1: am Umsetzungsstand nachgemessen; v1.0 schätzte +75 / −10)
- **LoC mit Tests:** voraussichtlich über dem Limit 250 ⇒ vor `/50-implement`
  `workflow.py set-field loc_limit_override 500` (Begründung: sechs gleichrangige
  Einträge in einem Workflow, PO-Vorgabe „nichts abspalten"; Tests zählen mit)
- **Files:** 12 produktiv (3 Go inkl. 1 Kommentar-Änderung, 8 Python, 1 Doku; v1.1: zusätzlich `track_resolution_health.py`) + Testdateien
- **Acceptance Criteria:** 31
- **Effort:** medium · **Risiko:** MEDIUM (viele kleine, isolierte Änderungen;
  Außenwirkung nur der Message-ID-Header)

| Datei | Aktion | Schicht | LoC (ca.) |
|---|---|---|---|
| `src/output/channels/email.py` | MODIFY (Message-ID, Erfolgszeile) | Python-Core | +30 / −3 |
| `src/services/radar_service.py` | MODIFY (leerer INCA-Zweig) | Python-Core | +5 |
| `src/services/alert_input_capture.py` | MODIFY (Prune je `source_key` + Deckel) | Python-Core | +30 / −7 |
| `src/services/track_resolution.py` | MODIFY (Dämpfung, Docstring; Zeitstempel nur nach Schreiberfolg) | Python-Core | +20 / −5 |
| `src/services/track_resolution_health.py` | MODIFY (v1.1: `record_track_resolution_failure` liefert `True`/`False`) | Python-Core | +6 / −1 |
| `src/services/trip_alert.py` | MODIFY (Fenster-Logzeilen, `alert_fetch` im Nowcast-Zweig, `ok` nur bei verwertbaren Daten) | Python-Core | +45 |
| `internal/scheduler/scheduler.go` | MODIFY (`atomic.Bool`) | Go-API | +8 / −1 |
| `internal/scheduler/briefing_health.go` | MODIFY (nur Kommentar Z.215-225) | Go-API | Kommentar |
| `internal/router/router.go` | MODIFY (4 Proxy-Routen) | Go-API | +4 |
| `docs/reference/api_contract.md` | MODIFY (Doku, zählt nicht zum LoC-Limit) | Doku | — |

Testdateien (nach Verhalten benannt, nicht nach Issue):

| Datei | Aktion |
|---|---|
| `tests/tdd/test_mail_message_id_traceability.py` | CREATE (C5-53) |
| `tests/tdd/test_radar_inca_fallback_journal.py` | MODIFY (C5-37, Bestandsdatei erweitern) |
| `tests/unit/test_alert_input_capture_retention.py` | **ERSETZEN/ANPASSEN** (B2-71, s. u.) |
| `tests/tdd/test_track_resolution_failure_visibility.py` | MODIFY (C5-47, inkl. AC-31) |
| `tests/unit/test_briefing_recipient_logging.py`, `tests/unit/test_briefing_cross_tenant_recipient_isolation.py` | MODIFY (v1.1: Ersatzfunktionen für `_dial_and_send` um `message_ids=None` ergänzt) |
| `internal/router/admin_trigger_alert_routes_test.go`, `internal/scheduler/scheduler_running_lifecycle_test.go`, `internal/scheduler/track_resolution_streak_cadence_test.go` | CREATE (v1.1: Go-Tests zu AC-23/24, AC-8, AC-20) |
| `tests/tdd/test_alert_window_boundary_logging.py` | CREATE (C5-02b) |
| `tests/tdd/test_nowcast_alert_fetch_unavailable.py` | CREATE (C5-02c) |
| `internal/scheduler/scheduler_test.go` | MODIFY (C5-15) |
| `internal/router/admin_trigger_test.go` | MODIFY (C5-02a, `triggerPfade`) |
| `internal/router/core_auth_sweep_test.go` | PRÜFEN/ANPASSEN (Zählung) |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `providers.enrichment_health.log_enrichment_call` | intern | Health-Journal; `fallback`/`unavailable` + `unit` aus Scheibe B |
| `PATH_ALERT_FETCH` (`alert_fetch`) | intern | Pfad aus Scheibe B, hier für den Trip-Nowcast-Ausnahmezweig mitgenutzt |
| `utils.pii_masking.mask_addr_for_pii_log` | intern | Empfänger-Maskierung in Logzeilen (#2157) |
| `internal/scheduler/briefing_health.go` | Leser | `track_resolution_failure_streak_since`, Streak-Lücke 26 h |
| `scheduler_gate.go` (Staging: Scheduler aus) | intern | Erklärt `running=false` auf Staging |
| `henemm-infra/scripts/check-gregor20.sh` | Leser (extern) | Wertet `running`, `fallback`, Track-Resolution-Streak aus — **keine Änderung nötig**, s. Implementation Details |
| `docs/specs/modules/fix_2218_alarm_ausfaelle.md` | Vorgänger (Scheibe B) | Out-of-Scope-Liste nennt genau diese sechs Einträge |
| `docs/specs/modules/alarm_eingangsprotokoll.md` | Spec | Mitschnitt-Vertrag (B2-71 ändert nur die Aufbewahrung) |
| `docs/specs/modules/fix_2073_s2_sichtbarer_fehlschlag.md` | Spec | Hat die Dämpfung von `implausible_measurement` ausdrücklich als „eigene Scheibe" ausgelagert (Z.252-256) — C5-47 ist genau diese Scheibe |
| ADR-0018 „Fallback ohne Kaschieren" | Architektur | Leitlinie für C5-37, C5-47, C5-02 |

## Implementation Details

### 1. C5-53 — Message-ID und Erfolgsnachweis (`email.py`)

Befund (per grep verifiziert): `build_mime_message` setzt keine `Message-ID`;
`make_msgid` kommt im Repo nirgends vor. `send()` baut die Nachricht **einmal** pro
Aufruf (`email.py:797`), vor der Retry-Schleife. Der Retry (`email.py:847`ff.) und
der `[SMTP-FALLBACK]`-Pfad (zwei Stellen: `_handle_transient_dial_failure`, Zeile
~602, und der Zweig in `send()`, Zeile ~932) reichen **dasselbe** `msg`-Objekt an
`_dial_and_send` weiter — sie rufen `build_mime_message` **nicht** neu auf. Der Erfolg
des Erstversuchs wird nicht protokolliert (nur `attempt > 0` bzw. `[SMTP-FALLBACK]`).
`_dial_and_send` verwirft das Ergebnis von `sendmail`. Bei mehreren Empfängern
(#457/#1426) wird dasselbe `msg.as_string()` je Empfänger einzeln eingeliefert — ohne
Eingriff trügen also alle Empfänger-Zustellungen dieselbe Message-ID.

Entscheidungen:

1. **ID-Vergabe:** `email.utils.make_msgid(domain="henemm.com")` (die Absender-Domain
   der Resend-Mails). `build_mime_message` bekommt einen optionalen Parameter
   `message_id: str | None = None` und setzt `msg["Message-ID"]` (bei `None`:
   selbst erzeugen). Reiner Zusatz-Header; die `X-GZ-*`-Marker-Header und der
   Rest der Nachricht bleiben byte-identisch.
2. **Retry/Fallback tragen dieselbe ID.** Die ID wird einmal in `send()` vergeben,
   vor der Retry-Schleife. Ein Retry und der `[SMTP-FALLBACK]` derselben Zustellung
   senden dieselbe ID — sonst wäre die Logzeile wertlos, weil sie auf keine
   zugestellte Mail passt. (Heute entsteht das automatisch, weil `msg` einmal
   gebaut wird; die Spec macht es zur geprüften Zusicherung.)
3. **Je Empfänger eine eigene ID (#457).** `send()` vergibt vor der Retry-Schleife
   je Empfänger genau eine ID (`dict[Empfänger → ID]`). `_dial_and_send` bekommt
   dieses Dict; in der Einzel-Empfänger-Schleife wird vor jedem `sendmail` die
   Kopfzeile mit `msg.replace_header("Message-ID", …)` **ersetzt** (nie ein zweites
   `msg["Message-ID"] = …`, das eine zweite Kopfzeile anhängen würde). Bei nur einem
   Empfänger gilt die beim Bau gesetzte ID. Retry/Fallback derselben Zustellung
   verwenden je Empfänger weiterhin dieselbe ID.
4. **Erfolgs-Logzeile auch beim Erstversuch.** `_dial_and_send` (neuer Parameter
   `message_ids`, Rückgabe jetzt `list[str]` statt `None`) gibt die Liste der
   tatsächlich vom Postausgang **angenommenen** Empfänger zurück (bei Teil-Ablehnung
   nur diese; abgelehnte Empfänger bleiben im bestehenden `logger.error`). `send()`
   (und der Fallback-Zweig) schreibt je angenommenem Empfänger genau eine
   `logger.info`-Zeile mit Message-ID und `mask_addr_for_pii_log(empfänger)`, z. B.
   `Email accepted by SMTP: message_id=<…@henemm.com> to=h***@g***.com attempt=1 route=primary`
   (`route=fallback` im Ersatzweg). Die bestehenden Zeilen („succeeded after N
   attempt(s)", `[SMTP-FALLBACK]`) bleiben. Die Sammelzeilen in
   `trip_report_scheduler.py:1767/479` und `scheduler_dispatch_service.py:571` bleiben
   unverändert; die Message-ID-Zeile ist der Nachweis je Zustellung.
   Die Rückgabe dient **ausschließlich** der Erfolgs-Logzeile; Versand- und
   Fehlersemantik von `send()` bleiben unverändert. Bestandstests, die
   `_dial_and_send` ersetzen (`test_briefing_recipient_logging.py`,
   `test_briefing_cross_tenant_recipient_isolation.py`), tragen jetzt den Parameter
   `message_ids=None`; ihre Ersatzfunktionen liefern `None` ⇒ keine Erfolgszeile
   („Erfolg nie ohne Annahme").
   **Absender (v1.1):** Das Bestandsverhalten `from_addr = self._reply_to or self._from`
   (`email.py` ~Z.707) bleibt unverändert. Ist eine Antwortadresse konfiguriert, steht
   sie im `From`-Header; ein fester Absender wird **nicht** zugesichert.
5. **Aussagekraft ehrlich begrenzt.** „Accepted by SMTP" belegt die Annahme durch den
   Postausgang, nicht die Zustellung im Postfach. Die ID erlaubt erst den Abgleich
   (Resend-Dashboard, IMAP-Suche). Reicht Resend die ID nicht unverändert durch, ist
   die Log-ID die von uns vergebene (s. AC-7).
6. **Mail-Inhalts-Datei:** `email.py` löst das Renderer-Commit-Gate aus. Geplante
   Schritte: Modus-Matrix-Test und Validator frisch grün vor dem Commit —
   `briefing_mail_validator.py` (Pfad Trip-Briefing) und `email_spec_validator.py`
   (Pfad Ortsvergleich), jeweils gegen echt zugestellte Staging-Mail aus dem
   Stalwart-Test-Postfach, Exit 0.

### 2. C5-15 — `running` im Scheduler-Status echt (`scheduler.go`)

`Status()` liefert `"running": true` fest (Zeile ~1377). `Start()`/`Stop()` merken
keinen Zustand; `robfig/cron` hat keinen Getter. Neu: Feld `running atomic.Bool` am
`Scheduler`; `Start()` setzt es auf `true` (nach `s.cron.Start()`), `Stop()` auf
`false` (nach Ablauf von `ctx.Done()`); `Status()` liest `s.running.Load()`.

Einordnung des Risikos (verifiziert):
- Prod startet den Scheduler in `cmd/server/main.go` vor `router.New` ⇒ `running=true`.
- Staging hat den Scheduler per `scheduler_gate.go` aus ⇒ `running=false` ist dort
  **korrekt** (heute fälschlich `true`).
- `check-gregor20.sh` (Zeile ~170, „Scheduler nicht aktiv") fragt nur Prod (Port 8090).
  Ein Fehlalarm durch Staging ist ausgeschlossen, und Prod meldet weiter `true` ⇒
  **kein Infra-Gegenstück nötig.** Falsche Verdrahtung würde dort aber einen
  Prod-Alarm auslösen — deshalb prüft ein Go-Test den Zustand vor `Start()`, nach
  `Start()` und nach `Stop()`, und der Post-Deploy-Selftest prüft `running=true` auf
  Prod.
- Weitere Leser (`briefing_health_test.go:530`, `status_token_test.go:168`) prüfen nur
  Typ/Präsenz.

### 3. C5-37 — leere INCA-Antwort ist ein Fallback (`radar_service.py`)

In `_fetch_geosphere_inca` gibt der Zweig `if not ts or not ts.data: return []` (Zeile
~892) leise `[]` zurück; nur der `except`-Zweig setzt `_inca_unavailable_this_call`.
Das Journal (Zeilen ~606-616) bucht deshalb `ok`. Neu: der leere Zweig setzt
`self._inca_unavailable_this_call = True` und schreibt ein `logger.warning` (Muster
des `except`-Zweigs). Das Journal bucht dann `fallback` mit Quelle als Detail.

Abgrenzung (verifiziert):
- Trockenes Wetter liefert **keine** leere Liste (Nullwerte werden zu Trockenframes,
  Zeilen ~896-897); `ts.data` ist nur bei einer kaputten Antwort ohne Zeitstempel
  leer ⇒ kein Fehlalarm-Risiko.
- Der Offline-Fixture-Zweig (`_offline_fixture_active()` → `[]`, Zeile ~882) bleibt
  **unberührt**: kein Flag, kein WARN, Journal-Ausgang unverändert.
- Reine Observability: das Flag wird nur im Journal gelesen. Keine
  Provider-Umschaltung, keine Änderung der Frames oder der Alarmentscheidung.
- Leser: Go `radar_nowcast.last_fallback_at/_detail`, `check-gregor20.sh` Block
  2e-e — sie zeigen künftig mehr `fallback`, was ihrer Aufgabe entspricht.

### 4. B2-71 — Mitschnitt-Aufbewahrung je Quelle und nach Alter (`alert_input_capture.py`)

Befund: `_MAX_FILES_PER_DIR = 50` und `_prune(dir_path)` gelten je **Verzeichnis**
(Zeilen 32/41). Ein Verzeichnis enthält Dateien mehrerer `source_key`; der
Dateiname ist `{_safe_key(source_key)}_{ts}.json` mit `ts = %Y%m%dT%H%M%S%f` (fest
21 Zeichen). Der Nowcast schreibt auch bei Cache-Treffern (`radar_service.py`
~572) und wird von vier Aufrufern genutzt (Trip-Radar-Alarm, Ortsvergleich-Radar,
Briefing, Inbound-Befehle). Radar-Alarmläufe laufen alle 5 Minuten (`3-58/5`), also
bis zu 288 Dateien je Key und Tag. Im 50er-Fenster reicht das bei einem einzigen Key
für rund vier Stunden; bei mehreren Keys verdrängen sie sich gegenseitig, sodass
`latest_capture_id()` für eine Korrelation im `alert_log` ins Leere läuft.

**Zielgröße (zeitbasiert):** Der Mitschnitt eines `source_key` bleibt **mindestens
24 Stunden** abrufbar, solange der Gesamtdeckel nicht greift.

Neue Aufbewahrung, ersetzt `_prune`:
1. **Gruppierung je Key:** Key = Dateiname ohne die letzten 22 Zeichen (`_` +
   21-Zeichen-Zeitstempel). Das ist auch bei `_` im Key eindeutig, weil der
   Zeitstempel feste Länge hat. Dateien ohne passendes Namensmuster werden **nicht**
   gelöscht (nur der Gesamtdeckel kann sie treffen).
2. **Alter:** Dateien eines Keys, deren Änderungszeit älter als 24 h ist, werden
   entfernt — **die jüngste Datei je Key bleibt immer** (auch wenn älter als 24 h), damit
   ein seltener Key nicht vollständig verschwindet.
3. **Gesamtdeckel je Verzeichnis:** höchstens `_MAX_FILES_PER_DIR_TOTAL = 10000`
   Dateien **und** `_MAX_BYTES_PER_DIR = 256 MiB`; bei Überschreitung wird global die
   älteste Datei verdrängt (Reihenfolge `(mtime, name)` wie bisher), bis beide
   Grenzen eingehalten sind. Greift der Deckel, schreibt der Code ein
   `logger.warning` (Verzeichnis, Anzahl/Bytes) — der Verlust ist sichtbar, nicht
   still.
4. **Nachrechnung des Deckels:** Nowcast-Dateien sind ca. 12 KB, Dateien des
   Zweigs b (`official_alert/vigilance_*`) bis ca. 520 KB (gemessen im Datenbestand).
   - Nowcast: 288 Dateien/24 h je Key × 12 KB ≈ 3,5 MB/Tag/Key. 10000 Dateien tragen
     ≈ 34 Keys; der Bytedeckel (256 MiB) ≈ 75 Keys ⇒ der Dateideckel greift zuerst.
     Bei heute realistischen Beständen (einstellige bis niedrige zweistellige Zahl
     aktiver Etappenpunkte und Ortsvergleich-Orte) liegt Keys × 288 klar unter 10000.
   - Zweig b: ≤ 96 Dateien/24 h je Key (15-Minuten-Takt) × 520 KB ≈ 50 MB/Tag/Key;
     256 MiB tragen ≈ 5 Tage — das Alterslimit (24 h) greift lange vorher.
   - Zweig a (`forecast_change_*`, nur bei Änderungen, ≤ 96/Tag je Entität): unkritisch.
   Der ursprüngliche Vorschlag 2000 Dateien wurde verworfen: 2000 / 288 ≈ 7 Keys
   würden die 24-h-Zielgröße schon bei wenigen Nowcast-Keys verfehlen.
5. **Wirkt auf alle drei Capture-Zweige** (gemeinsamer `_prune`): Zweig a
   (`capture_user_scoped`, Aufrufer `trip_alert.py:~817`, Verzeichnis
   `users/<uid>/alert_input/`), Zweig b (`capture_system(branch="official_alert")`,
   Aufrufer `src/services/official_alerts/warn_egress.py:~494`) und der Nowcast
   (`capture_system(branch="nowcast")`, Aufrufer `radar_service.py:~1416`). Die
   Tests decken alle drei ab.
6. **`latest_capture_id()` bleibt kompatibel:** es filtert per JSON-Feld `source_key`
   und `max_age`, unabhängig von der Aufbewahrung. Signatur und Rückgabe unverändert.
7. **Bestandstest:** `tests/unit/test_alert_input_capture_retention.py` nagelt „50 pro
   Verzeichnis" fest und wird **ersetzt/angepasst** (nicht als „vorbestehend rot"
   liegengelassen): die Bestandsfälle werden auf die neue Zusicherung umgeschrieben
   (Alter je Key, jüngste je Key, Gesamtdeckel). `..._failopen.py`,
   `..._payload_schema.py`, `test_alert_log_capture_correlation.py`,
   `test_radar_service_capture.py` und `test_warn_egress_capture_*.py` bleiben grün.

### 5. C5-47 — Dämpfung von `implausible_measurement` (`track_resolution.py`)

Heute ruft Zeile ~342 `_melde_unplausible_messung` **vor** dem `_failed_lookups`-Check
(Zeile ~345) auf; der Docstring bezeichnet das als bewusst „ohne eigene Dämpfung".
Folge: jede 15-Minuten-Runde eine Zeile je betroffener Etappe in
`users/<uid>/diagnostics/track_resolution_failures.jsonl`.

Entscheidung: **zeitbasierte Dämpfung** je `(user_id, trip_id, stage_id)` mit
Intervall **12 h**. `_melde_unplausible_messung` schreibt nur, wenn für den Schlüssel
im Prozessspeicher noch keine Meldung existiert oder die letzte ≥ 12 h zurückliegt;
danach wird der Zeitpunkt aktualisiert. Die Uhr ist über eine kleine Funktion
(`_jetzt()`, Monotonic) austauschbar, damit der Test ohne Warten prüfen kann.

**Dämpfung erst nach Schreiberfolg (v1.1):** `record_track_resolution_failure`
(`track_resolution_health.py`) liefert `True`, wenn die Zeile wirklich geschrieben
wurde, sonst `False` (fail-soft bleibt: keine Ausnahme nach außen).
`_melde_unplausible_messung` setzt den Dämpfungszeitstempel **nur bei `True`**.
Scheitert das Schreiben, ist die Etappe nicht gedämpft, und die nächste Runde holt die
Zeile nach — nichts geht still verloren (ADR-0018).

Begründung des Intervalls: Der Go-Leser (`briefing_health.go`,
`trackResolutionFailureStreakGapThreshold = 26h`) lässt den Streak abreißen, wenn
zwischen zwei Zeilen mehr als 26 h liegen. 12 h < 26 h ⇒ der Streak reißt **nie** ab,
solange die Etappe unplausibel bleibt, und `check-gregor20.sh:611-621` schwellt nach
Streak-Alter (48 h), nicht nach Zeilenzahl; der 24-h-Zähler ist reine Anzeige. Die
Dämpfung senkt also keinen Alarm unter seine Schwelle. (Eine reine Prozess-Menge wie
`_failed_lookups` wäre falsch: sie schriebe eine Zeile und dann bis zum Neustart
nichts mehr ⇒ Streak risse nach 26 h ab.)

**Bewusste Entscheidung:** Die Dämpfung lebt im Prozessspeicher. Ein Neustart setzt
sie zurück ⇒ höchstens **eine Zusatzzeile je Neustart und Etappe**. Das ist
gewollt (kein Persistenzaufwand; eine Zusatzzeile schadet dem Streak nicht).

Doku-Anpassungen: Docstring von `_melde_unplausible_messung` (nicht mehr „OHNE eigene
Dämpfung", sondern „höchstens eine Zeile je Etappe und 12 h"); Kommentar in
`briefing_health.go` Zeilen ~215-225 (nennt heute `_failed_lookups` und „einmal je
Prozess" als Dämpfung; neu: zwei Schreiber-Dämpfungen — `_failed_lookups` für
Auflösungsfehler, 12-h-Takt für `implausible_measurement` — und der Bezug der
26-h-Lücke zum 12-h-Intervall). Der Go-Code selbst ändert sich nicht.

### 6. C5-02 — Alarm-Pfad im Betrieb sichtbar

**(a) Vier Admin-Proxy-Routen (`router.go`).** Der Go-Cron ruft fünf Python-Alarm-
Endpunkte; nur `alert-checks` hat heute einen Admin-Proxy (neben `trip-reports` und
`inbound-commands`, Zeilen ~324-328). Neu, mit `requireAdmin` und `ProxyPostHandler`
(Muster der Nachbarzeilen): `POST /api/scheduler/radar-alert-checks`,
`/api/scheduler/compare-alert-checks`, `/api/scheduler/compare-radar-alert-checks`,
`/api/scheduler/compare-official-alert-checks`. Damit entfällt die Einschränkung
„Debug-Trigger nur `GZ_ENV=staging`" für den Alarm-Pfad. Anpassungen:
`internal/router/admin_trigger_test.go` (`triggerPfade` um die vier Pfade erweitern),
`internal/router/core_auth_sweep_test.go` (der Sweep zählt selbsttätig über
`chi.Walk`; `minPythonCallsReached = 24` bei Ist 27 prüfen und, falls sich der
Ist-Wert ändert, Kommentar/Wert gemäß dessen Regel nachziehen — nie senken),
`docs/reference/api_contract.md` (Zeile ~271: Routenzahl gemäß echter
`chi.Walk`-Zählung, Stand Umsetzung **101 Pfade / 123 Registrierungen**, davon 4 nur bei
`GZ_ENV=staging` — ohne diese 97/119; Routentabelle um vier Zeilen; fehlende
Inventarzeile `/api/internal/premium-sms-learn` nachgetragen. Die v1.0-Zahl 84/104 war
falsch).

**Nachweis ohne Prod-Auslösung:** Ein Admin-Trigger auf Prod läuft über **alle**
Nutzer und kann echte Alarme versenden — ein verbotener Sammel-Versand. Der Nachweis
erfolgt deshalb **nur** über (i) Go-Routing-Tests mit Fake-Python-Ziel und
(ii) Staging-Kern-Port 8001 mit `X-GZ-Core-Auth` (Go-Trigger ist auf Staging
Admin-only und Staging hat keinen Admin ⇒ 403 dort ist erwartet).

**(b) Fenstergrenze protokollieren (`trip_alert.py`).** Genau **eine** Logzeile je
Alarmprüfung im Δ-Zweig (nach `_delta_event_window`, Zeile ~843) und genau eine je
Segment-Prüfung im Radar-Zweig (nach `aufenthaltsfenster_min`, Zeile ~2127, in der
Schleife je Segment). Level INFO, Inhalt: Trip-ID, Fenster-Start, Fenster-Ende,
Quelle (`delta` bzw. `radar`). **Keine** Koordinaten oder Adressen (PII). Gibt es
kein Fenster (Δ-Zweig ohne nasse Änderung), erscheint trotzdem eine Zeile mit
`fenster=keines`, damit „keine Grenze" von „nicht geprüft" unterscheidbar ist. Es
wird **keine Fensterlogik verändert**; die Trennung Alarm-/Anzeigefenster (#1599)
bleibt, `tests/unit/test_ziel_segment_anzeige_invarianz.py` läuft unverändert grün.

**(c) Trip-Nowcast bucht `alert_fetch` (`trip_alert.py`).** Im Ausnahmezweig des
ersten Nowcast-Abrufs (`except Exception`, Zeile ~2167, setzt `_p0_ausnahme`) wird
zusätzlich `alert_fetch`/`unavailable` mit `unit = f"{self._user_id}/{trip.id}"`
gebucht (wie in Scheibe B). `alert_fetch`/`ok` mit derselben `unit` bucht **nur** ein
Nowcast-Ergebnis mit verwertbaren Radardaten (v1.1), damit ein späterer Erfolg den
Ausfall ablöst. Ergebnisse mit `throttled` oder `data_unavailable` buchen weder `ok`
noch `unavailable`: sonst würde ein früherer Ausfall in `failed_units` fälschlich
gelöscht (ADR-0018; Muster Δ-Zweig `_versucht and fresh_weather`).
`RadarDeadlineExceeded` bucht nichts (Zeitgrenze ist weder Ausfall noch Entwarnung,
A-2 S2).
Rückgabe und Alarmentscheidung unverändert.

### 7. Doku (`docs/reference/api_contract.md`)

Abschnitt `GET /api/scheduler/status` (Zeilen ~1359-1505): `failed_units` je Pfad
(Scheibe B, bisher undokumentiert), Pfad `alert_fetch` in der Pfadliste und in der
Tabelle `enrichment_health.<path>.last_attempt_at`, `fallback` für `radar_nowcast`
auch bei **leerer** INCA-Antwort (bisher nur HTTP-Fehler beschrieben), `running` als
echter Zustand (auf Staging `false`), die vier neuen Admin-Routen samt Routenzahl.

## Expected Behavior

- **Input:** jede ausgehende Mail; jeder Scheduler-Statusabruf; jeder Nowcast-Abruf;
  jeder Mitschnitt-Schreibvorgang; jede 15-Minuten-Auflösungsrunde; jeder
  Alarmlauf (Trip-Δ, Trip-Radar).
- **Output:** Kopfzeile `Message-ID` in jeder Mail und je angenommenem Empfänger eine
  Logzeile mit dieser ID; ehrliches `running`; `fallback` statt `ok` bei leerer
  INCA-Antwort; Mitschnitte mindestens 24 h abrufbar; höchstens eine
  `implausible_measurement`-Zeile je Etappe und 12 h; vier zusätzliche
  Admin-Trigger; Fenster-Logzeile je Alarmprüfung; `alert_fetch`-Eintrag im
  Nowcast-Ausnahmezweig (`ok` nur bei verwertbaren Radardaten).
- **Side effects:** keine auf Alarmentscheidung, Versand, Drosselung oder
  Nutzermeldungen. Einzige sichtbare Folge für Empfänger: ein zusätzlicher
  technischer Mail-Header. Mehr `fallback`-WARN-Zeilen bei leerer INCA-Antwort
  (gewollt).

## Acceptance Criteria

Testebene: **Kern** = deterministisch ohne Netz/Live-Dienste; **Staging** = gegen
`https://staging.gregor20.henemm.com`; `NOT_MEASURABLE_ON_STAGING` = der
Staging-Datenbestand ist für den Nutzer `hem` nicht lesbar, der Nachweis liegt im Kern.

### C5-53 — Message-ID

- **AC-1:** Given eine ausgehende Mail (Trip-Briefing, Ortsvergleich oder Alarm) /
  When `send()` die Nachricht aufbaut und einliefert / Then trägt die eingelieferte
  Nachricht genau eine Kopfzeile `Message-ID` der Form `<…@henemm.com>`, und alle
  bisherigen Kopfzeilen (`Subject`, `From`, `To`, `Date`, `Reply-To`, `X-GZ-*`) sind
  unverändert (`From` bleibt Bestandsverhalten: Antwortadresse, falls gesetzt, sonst
  Standardabsender — `self._reply_to or self._from`).
  - Test (Kern): `test_mail_message_id_traceability.py` fängt an der Systemgrenze
    (aufzeichnende `smtplib.SMTP`-Attrappe, s. Test Plan) den Rohstring an `sendmail`
    ab und zählt die Kopfzeile. Die echte Zustellung belegt nur AC-6/AC-7 (Staging).

- **AC-2:** Given eine Mail, die beim ersten Versuch vom Postausgang angenommen wird /
  When `send()` zurückkehrt / Then steht im Log genau eine Info-Zeile je Empfänger mit
  der Message-ID aus der eingelieferten Nachricht und der **maskierten**
  Empfängeradresse (kein Klartext), ohne dass ein Retry nötig war.
  - Test (Kern): Log-Capture; ID aus Log == ID aus der abgefangenen Rohnachricht;
    Klartextadresse kommt im Log nicht vor.

- **AC-3:** Given der Postausgang scheitert transient, sodass `send()` wiederholt oder
  auf den Ersatzweg `[SMTP-FALLBACK]` ausweicht / When die Mail schließlich angenommen
  wird / Then tragen alle Einlieferungsversuche dieselbe Message-ID, und die
  Erfolgs-Logzeile nennt genau diese ID.
  - Test (Kern): Attrappe lehnt Versuch 1 (und im zweiten Fall den Primärweg ganz)
    mit 4xx ab; die abgefangenen Rohnachrichten werden verglichen.

- **AC-4:** Given eine Mail an drei Empfänger (Versand je Empfänger, #457/#1426) /
  When `send()` jeden Empfänger einzeln einliefert / Then trägt jede
  Empfänger-Zustellung eine **eigene** Message-ID, jede eingelieferte Nachricht hat
  genau **eine** `Message-ID`-Kopfzeile (keine doppelte), und das Log nennt je
  Empfänger die zu seiner Einlieferung gehörende ID.
  - Test (Kern): Attrappe sammelt die drei Rohnachrichten; IDs paarweise
    verschieden; Kopfzeilenzahl je Nachricht == 1.

- **AC-5:** Given drei Empfänger, von denen der Postausgang einen ablehnt / When
  `send()` abschließt / Then erhalten nur die zwei angenommenen Empfänger eine
  Erfolgs-Logzeile mit Message-ID; für den abgelehnten steht keine Erfolgszeile
  („Erfolg" wird nie ohne Annahme behauptet), die bestehende Fehlerzeile bleibt.
  - Test (Kern): Attrappe weist einen Empfänger mit 550 ab.

- **AC-6:** Given die geänderte Mail-Erzeugung / When die Mail-Validatoren gegen eine
  echt zugestellte Staging-Mail laufen / Then enden
  `briefing_mail_validator.py` (Trip-Briefing) und `email_spec_validator.py`
  (Ortsvergleich) jeweils mit Exit 0, und die Modus-Matrix-Tests des
  Renderer-Commit-Gates sind frisch grün.
  - Test (Staging): Wegwerf-Nutzer `gregor-test+…`, Postfach per IMAP,
    Validatoren aus `.claude/hooks/`.

- **AC-7:** Given eine über Staging an das Test-Postfach zugestellte Mail / When die
  Message-ID aus der Logzeile (Journal von `gregor-api-staging`/Python-Core) mit der
  Message-ID der per IMAP gelesenen Mail verglichen wird / Then wird das Ergebnis im
  Nachweis-Protokoll festgehalten: bei Gleichheit gilt „Resend reicht die ID
  durch"; bei Abweichung gilt „Resend schreibt die ID um", die Log-ID ist die von
  uns vergebene, und die Abweichung ist **dokumentiert und kein
  Implementierungsfehler** (Befund, nicht Fehlschlag).
  - Test (Staging): IMAP-Abruf, Vergleich, beide Werte im Protokoll.

### C5-15 — `running`

- **AC-8:** Given ein neu angelegter Scheduler / When der Status vor `Start()`, nach
  `Start()` und nach `Stop()` abgefragt wird / Then lautet `running` der Reihe nach
  `false`, `true`, `false`.
  - Test (Kern, Go): `scheduler_test.go`, echter `Scheduler`, kein Mock.

- **AC-9:** Given Staging (Scheduler per `scheduler_gate.go` aus) und Prod (Scheduler
  läuft) / When `GET /api/scheduler/status` mit Token abgefragt wird / Then meldet
  Staging `running: false` und Prod nach dem Deploy `running: true`, und
  `check-gregor20.sh` löst auf Prod keinen Alarm „Scheduler nicht aktiv" aus.
  - Test (Staging + Post-Deploy): Staging-Abruf; Prod-Abruf im Selftest/Monitor.

### C5-37 — leere INCA-Antwort

- **AC-10:** Given GeoSphere INCA antwortet ohne Zeitreihe oder ohne Datenpunkte /
  When ein Nowcast für einen Ort in Österreich abgerufen wird / Then bucht das
  Health-Journal für `radar_nowcast` den Ausgang `fallback` (nicht `ok`), und im Log
  steht eine Warnzeile zur leeren INCA-Antwort.
  - Test (Kern): `test_radar_inca_fallback_journal.py`, Fake-Provider an der
    Systemgrenze liefert `None` bzw. leere `data`; echte Journaldatei wird gelesen.
  - Staging: `NOT_MEASURABLE_ON_STAGING`.

- **AC-11:** Given INCA liefert Datenpunkte mit Nullniederschlag (trocken) / When der
  Nowcast abgerufen wird / Then bucht das Journal weiter `ok`, und es erscheint keine
  INCA-Warnzeile (trocken ist kein Ausfall).
  - Test (Kern): Gegenprobe zu AC-10 in derselben Testdatei.

- **AC-12:** Given der Offline-Fixture-Modus ist aktiv (`_offline_fixture_active()`) /
  When `_fetch_geosphere_inca` aufgerufen wird / Then bleibt das Flag
  `_inca_unavailable_this_call` ungesetzt, es erscheint keine Warnzeile, und der
  Journal-Ausgang ist unverändert gegenüber dem Stand vor der Änderung.
  - Test (Kern): Fixture-Modus über die vorhandene Umgebungsweiche.

### B2-71 — Mitschnitt-Aufbewahrung

- **AC-13:** Given Mitschnitte eines `source_key` mit Dateizeiten von 30 h, 25 h, 23 h
  und 1 h alter Änderungszeit / When ein weiterer Mitschnitt geschrieben wird / Then
  sind die Dateien älter als 24 h entfernt, die Dateien von 23 h und 1 h sowie die
  neue Datei bleiben, und `latest_capture_id` findet den jüngsten Eintrag.
  - Test (Kern): `test_alert_input_capture_retention.py` (ersetzt), `os.utime`
    setzt Alter, echtes Dateisystem im tmp-Verzeichnis.
  - Staging: `NOT_MEASURABLE_ON_STAGING`.

- **AC-14:** Given ein Key, dessen einzige und jüngste Datei älter als 24 h ist /
  When der Prune läuft / Then bleibt diese eine Datei erhalten (die jüngste je Key
  wird nie vom Alterslimit gelöscht).
  - Test (Kern): wie AC-13.

- **AC-15:** Given ein Verzeichnis mit einem häufig schreibenden Key (z. B. 120
  Dateien innerhalb der letzten Stunde) und drei seltenen Keys mit je einer Datei /
  When der Prune läuft / Then sind alle 120 Dateien des häufigen Keys erhalten
  (kein 50er-Fenster mehr) und keine der Dateien der seltenen Keys wurde
  verdrängt.
  - Test (Kern): Regression zum ursprünglichen Befund „Nowcast verdrängt sich
    selbst"; rot gegen den alten Verzeichnis-Prune.

- **AC-16:** Given ein Verzeichnis, das den Gesamtdeckel (Dateizahl) überschreitet /
  When der Prune läuft / Then liegt die Dateizahl danach höchstens am Deckel, die
  jeweils ältesten Dateien sind verdrängt, und eine Warnzeile nennt den Eingriff;
  ebenso greift der Bytedeckel bei wenigen sehr großen Dateien.
  - Test (Kern): Deckel per Modul-Konstante für den Test klein gesetzt (kein
    Zehntausend-Dateien-Test), jüngste Datei je Key bleibt außer bei Konflikt mit
    dem Deckel nicht geschützt (Deckel hat Vorrang vor „jüngste je Key").

- **AC-17:** Given Mitschnitte aus allen drei Zweigen (a: Nutzerverzeichnis
  `alert_input`, b: `debug/alert_input/official_alert`, c: `debug/alert_input/nowcast`)
  / When je Zweig mehr Dateien als das frühere 50er-Limit geschrieben werden / Then
  bleiben in jedem Zweig alle Dateien der letzten 24 h erhalten, und die
  Zweige beeinflussen sich nicht.
  - Test (Kern): jeweils über die echte Schreibfunktion des Zweigs
    (`capture_user_scoped`, `capture_system`).

- **AC-18:** Given ein `alert_log`-Eintrag, der per `latest_capture_id` einen Mitschnitt
  korreliert / When zwischen Mitschnitt und Korrelation 6 h und mehr als 50 weitere
  Mitschnitte anderer Keys liegen / Then liefert `latest_capture_id` weiterhin die
  `capture_id` des passenden Mitschnitts (Aufbewahrung ≥ 24 h).
  - Test (Kern): `test_alert_log_capture_correlation.py` bleibt grün, plus ein
    Fall mit Überfluss anderer Keys.

### C5-47 — Dämpfung `implausible_measurement`

- **AC-19:** Given eine Etappe mit unplausiblen gespeicherten Distanzen / When die
  Auflösung 48-mal im 15-Minuten-Takt läuft (12 h) / Then steht im Journal
  `track_resolution_failures.jsonl` für diese Etappe genau **eine** Zeile mit Grund
  `implausible_measurement`.
  - Test (Kern): `test_track_resolution_failure_visibility.py`, `_jetzt()` per
    echtem Zeitversatz-Parameter, keine Mock-Spiegelung; liest die echte Datei.
  - Staging: `NOT_MEASURABLE_ON_STAGING`.

- **AC-20:** Given dieselbe Etappe bleibt über 12 h hinaus unplausibel / When die
  Auflösung nach 12 h und danach erneut läuft / Then entsteht jeweils eine neue
  Zeile, sodass der Abstand benachbarter Zeilen nie 26 h erreicht und der
  Go-Streak (`track_resolution_failure_streak_since`) über einen Zeitraum von 72 h
  **nicht abreißt**.
  - Test (Kern): Python-Teil erzeugt die Zeilenfolge; ein Go-Test in
    `briefing_health_test.go` liest eine Zeilenfolge im 12-h-Abstand und prüft,
    dass der Streak seit der ersten Zeile besteht.

- **AC-21:** Given zwei Etappen desselben Trips und eine gleichnamige Etappe eines
  zweiten Nutzers, alle unplausibel / When die Auflösung läuft / Then wird jede
  `(user, trip, stage)` einzeln gedämpft: jede schreibt ihre erste Zeile,
  keine unterdrückt die andere, und die Zeilen landen im Journal des jeweils
  richtigen Nutzers (Mandantentrennung).
  - Test (Kern): zwei Nutzerverzeichnisse im tmp.

- **AC-22:** Given der Prozess startet neu (Dämpfungsspeicher leer) / When die erste
  Runde danach läuft / Then entsteht höchstens eine Zusatzzeile je Etappe — der
  bekannte, bewusst akzeptierte Neustart-Effekt — und die Folgerunden sind wieder
  gedämpft.
  - Test (Kern): Speicher des Moduls zurücksetzen, einmal und nochmals laufen lassen.

- **AC-31:** Given das Schreiben der Diagnose-Zeile für eine unplausible Etappe scheitert
  (Journal-Datei nicht schreibbar) / When die Auflösung in der nächsten
  15-Minuten-Runde erneut läuft und das Schreiben dann gelingt / Then wird in der
  ersten Runde keine Dämpfung gesetzt, die nächste Runde schreibt die Zeile nach, und
  erst danach greift die 12-h-Dämpfung.
  - Test (Kern): `test_track_resolution_failure_visibility.py::test_gescheitertes_schreiben_daempft_nicht_naechste_runde_schreibt`.

### C5-02 — Alarm-Pfad im Betrieb

- **AC-23:** Given ein angemeldeter Admin / When er `POST` auf jede der vier neuen
  Routen (`radar-alert-checks`, `compare-alert-checks`, `compare-radar-alert-checks`,
  `compare-official-alert-checks`) sendet / Then wird jeder Aufruf genau einmal an
  den passenden Python-Pfad weitergereicht und die Python-Antwort durchgereicht.
  - Test (Kern, Go): `admin_trigger_test.go`, `triggerPfade` erweitert, Fake-Python-Ziel
    zählt Aufrufe je Pfad.

- **AC-24:** Given ein Nicht-Admin (und ein nicht angemeldeter Aufrufer) / When er auf
  eine der vier neuen Routen `POST` sendet / Then lautet die Antwort 403
  `{"error":"forbidden"}` (bzw. 401 ohne Sitzung) auf **allen vier**, und am
  Python-Ziel kommt kein Aufruf an.
  - Test (Kern, Go): wie AC-23, zwei verschiedene Nutzer.

- **AC-25:** Given der Router mit den neuen Routen / When der Sweep
  `core_auth_sweep_test.go` alle Routen per `chi.Walk` durchläuft / Then bleibt er
  grün, `minPythonCallsReached` wird unverändert eingehalten, und die Routenzahl in
  `api_contract.md` (101 Pfade, 123 Registrierungen; ohne die 4 nur bei `GZ_ENV=staging`
  existierenden Routen 97/119) entspricht der echten `chi.Walk`-Zählung des Routers;
  das Inventar enthält auch die Zeile `/api/internal/premium-sms-learn`.
  - Test (Kern, Go): Sweep-Test; Zahlenabgleich im Review der Doku.

- **AC-26:** Given eine Δ-Alarmprüfung für einen Trip mit nasser Änderung / When sie
  läuft / Then erscheint **genau eine** Info-Logzeile mit Trip-ID, Fenster-Start,
  Fenster-Ende und Quelle `delta`, und weder Koordinaten noch Adressen stehen darin;
  ohne nasse Änderung erscheint die Zeile mit `fenster=keines`.
  - Test (Kern): `test_alert_window_boundary_logging.py`, Log-Capture über den
    echten Prüfpfad.
  - Staging: `NOT_MEASURABLE_ON_STAGING`.

- **AC-27:** Given eine Radar-Alarmprüfung mit drei Segmenten / When sie läuft / Then
  erscheint je Segment genau eine Info-Logzeile (Trip-ID, Fenster-Start/-Ende,
  Quelle `radar`), also drei Zeilen, und die Fenster selbst sind bit-gleich zum
  Stand vor der Änderung; `tests/unit/test_ziel_segment_anzeige_invarianz.py` läuft
  **unverändert** grün (#1599).
  - Test (Kern): neue Testdatei plus unveränderter Bestandstest.

- **AC-28:** Given der erste Nowcast-Abruf des Trip-Radar-Alarms wirft eine Ausnahme /
  When die Alarmprüfung läuft / Then steht im Journal ein Eintrag `alert_fetch`/
  `unavailable` mit `unit` aus Nutzer-ID und Trip-ID, und die Prüfung verhält sich
  sonst wie bisher (kein Alarm, keine Nutzermeldung); bei einem Abruf mit
  verwertbaren Radardaten steht `alert_fetch`/`ok` mit derselben `unit`; ein Ergebnis
  mit `throttled` oder `data_unavailable` bucht weder `ok` noch `unavailable` (ein
  früherer Ausfall bleibt in `failed_units` stehen); eine `RadarDeadlineExceeded` bucht
  **nichts**.
  - Test (Kern): `test_nowcast_alert_fetch_unavailable.py`, Fake-Nowcast-Dienst an
    der Systemgrenze wirft; echte Journaldatei; zwei Nutzer.
  - Staging: `NOT_MEASURABLE_ON_STAGING`.

- **AC-29:** Given Staging, auf dem der Go-Trigger nur für Admins offen ist und kein
  Admin existiert / When die Kern-Endpunkte der Alarm-Läufe über Port 8001 mit
  `X-GZ-Core-Auth` ausschließlich für den Test-Trip bzw. leeren Staging-Bestand
  aufgerufen werden / Then antworten sie mit 200 (Python-Pfade erreichbar), und
  **kein** Admin-Trigger auf Prod wird ausgelöst (kein Sammel-Versand).
  - Test (Staging): Aufruf über Kern-Port; Prod bleibt unberührt.

### Doku

- **AC-30:** Given `docs/reference/api_contract.md` / When ein Leser den Abschnitt
  `GET /api/scheduler/status` liest / Then sind `failed_units`, der Pfad
  `alert_fetch`, `fallback` bei leerer INCA-Antwort, `running` als echter
  Zustand (Staging `false`) und die vier neuen Admin-Routen samt korrigierter
  Routenzahl beschrieben.
  - Test (Kern): Abgleich der Doku mit dem Router (Review); kein Dateiinhalt-Test
    als Verhaltensnachweis.

## Test Plan

- **Schichtung:** alles Kern-deterministisch ohne Netz; Staging nur dort, wo der
  Datenbestand für `hem` lesbar bzw. die Zusicherung ohne Datenbestand messbar ist
  (AC-6, AC-7, AC-9, AC-29).
- **Kein Mock-Theater:** SMTP an der Systemgrenze durch eine aufzeichnende
  `smtplib.SMTP`-Attrappe ersetzt, die den Rohstring an `sendmail` festhält (v1.1,
  **Abweichung vom v1.0-Plan „echter lokaler SMTP-Testserver"**: `aiosmtpd` ist nicht
  verfügbar, und `_dial_and_send` erzwingt STARTTLS + Login). Journal und Mitschnitte gegen echte Dateien im tmp-Verzeichnis
  (`get_data_root()` pro Test umgebogen), Go-Tests mit echtem `Scheduler`/Router.
  Fakes nur an Systemgrenzen (GeoSphere-Provider, Nowcast-Dienst, Python-Ziel).
- **Prüfling relativ zur Testdatei:** Python-Tests lösen `src/` über den Pfad der
  eigenen Datei auf, nie über den festen Hauptrepo-Pfad.
- **Mutations-Gegenprobe (Pflicht, Adversary):** (a) `replace_header` durch Anhängen
  ersetzen ⇒ AC-4 rot; (b) Message-ID im Retry neu vergeben ⇒ AC-3 rot; (c) Maskierung
  entfernen ⇒ AC-2 rot; (d) `running` wieder `true` fest ⇒ AC-8 rot; (e) leeren
  INCA-Zweig ohne Flag ⇒ AC-10 rot; (f) Offline-Zweig setzt das Flag ⇒ AC-12 rot;
  (g) Prune wieder je Verzeichnis ⇒ AC-15 rot; (h) Alter auf 1 h verkürzen ⇒
  AC-13/AC-18 rot; (i) Dämpfungsintervall 30 h ⇒ AC-20 rot; (j) Dämpfung ohne Nutzer
  im Schlüssel ⇒ AC-21 rot; (k) eine der vier Routen ohne `requireAdmin` ⇒ AC-24 rot;
  (l) Logzeile in der Segmentschleife doppelt ⇒ AC-27 rot; (m) `alert_fetch` im
  Nowcast-Ausnahmezweig entfernen ⇒ AC-28 rot. Per String-Ersetzung mit externer
  Sicherungskopie, nie `git checkout/stash/reset`.
- **Leitfrage je Test:** Ist die Zusicherung dort geprüft, wo sie WIRKT — an der
  eingelieferten Rohnachricht, an der Journaldatei, an der HTTP-Antwort — und nicht
  nur dort, wo der Code steht?
- **Bestand:** `tests/unit/test_alert_input_capture_retention.py` wird ersetzt, nicht
  rot liegengelassen. Pflichtläufe (benannte Dateien, nie `uv run pytest` blank):
  die oben genannten Testdateien plus `test_mail_transport_dial_behaviour.py`,
  `test_mail_send_deadline.py`, `test_mail_fallback_guard.py`, `test_927_smtp_fallback.py`,
  `test_issue_457_email_per_recipient.py`, `test_egress_single_dial_point.py`,
  `test_issue_766_smtp_retry.py`, `test_briefing_recipient_logging.py`,
  `test_inca_fehlerstatus_journal.py`, `test_radar_nowcast_health_journal.py`,
  `test_track_resolution_legacy_trip.py`, `test_ziel_segment_anzeige_invarianz.py`;
  Go: `go test ./internal/scheduler/... ./internal/router/...`.
  Rückgabewert von `_dial_and_send` (bisher `None`) ändert sich — bestehende Tests
  dazu wurden im selben Zug angepasst (`message_ids=None` in den Ersatzfunktionen).
  Zusätzliche Mutation (n): Dämpfungszeitstempel auch bei `False` setzen ⇒ AC-31 rot.

## Staging-Nachweis

Deploy folgt dem normalen Weg (PR, Staging-Auto-Deploy, `/e2e-verify`, Prod-Deploy,
`prod_selftest.py`). Je Eintrag:

| Eintrag | Staging-Nachweis |
|---|---|
| C5-53 | Zugestellte Mail an Wegwerf-Nutzer `gregor-test+…` per IMAP lesen; `Message-ID` mit der Logzeile vergleichen und das Ergebnis protokollieren (AC-7: Gleichheit = Resend reicht durch; Abweichung = Befund, kein Fehlschlag); Validatoren Exit 0 (AC-6). Bestmessbarer Punkt. |
| C5-15 | Staging `/api/scheduler/status` ⇒ `running=false`; Prod nach Deploy ⇒ `true` (Selftest/Monitor). |
| C5-02a | Routing nur über Go-Tests; Staging-Go-Trigger liefert 403 (kein Admin); Nachweis der Python-Pfade über Kern-Port 8001 mit `X-GZ-Core-Auth`. **Kein Admin-Trigger auf Prod** (Sammel-Versand verboten). |
| C5-37 | `NOT_MEASURABLE_ON_STAGING` — nur Kern-Tests. |
| B2-71 | `NOT_MEASURABLE_ON_STAGING` — Datenbestand unter `data/debug/` für `hem` nicht lesbar; nur Kern-Tests. |
| C5-47 | `NOT_MEASURABLE_ON_STAGING` — Nutzer-Journale nicht lesbar; nur Kern-Tests. |
| C5-02b/c | `NOT_MEASURABLE_ON_STAGING` — Log/Journal der Alarmläufe nicht lesbar; nur Kern-Tests. |

**Commit-Schnitt (Rollback-Fähigkeit, v1.1):** ein Commit je Eintrag — C5-15, C5-02a,
C5-37, B2-71, C5-47, C5-53, C5-02b/c, Doku —, damit jeder Punkt einzeln zurücknehmbar
ist.

Nachweise, die nicht gemessen werden können, werden ausdrücklich als solche
ausgewiesen; ein „PASS" wird nie erfunden.

## Known Limitations

- **Message-ID belegt Annahme, nicht Zustellung im Postfach.** Sie ermöglicht den
  Abgleich; ob Resend sie unverändert durchreicht, misst AC-7 und hält es als Befund
  fest.
- **Dämpfung im Prozessspeicher (C5-47):** pro Neustart höchstens eine Zusatzzeile
  je Etappe; bewusst akzeptiert.
- **Aufbewahrung (B2-71):** Der Gesamtdeckel (10000 Dateien / 256 MiB je Verzeichnis)
  kann bei sehr vielen aktiven Nowcast-Keys (> ca. 34) die 24-h-Zielgröße
  unterschreiten; der Eingriff wird als Warnzeile sichtbar. Wachsen die Bestände
  dauerhaft, ist der Deckel neu zu bemessen.
- **Mail-Test an der Systemgrenze (v1.1):** Die Kern-Tests prüfen den Rohstring an einer
  `smtplib.SMTP`-Attrappe, keinen echten SMTP-Dialog. Die echte Zustellung inkl.
  Message-ID belegt ausschließlich der Staging-Nachweis (AC-6/AC-7).
- **`running` ist ein Prozesszustand,** keine Aussage über erfolgreiche Läufe; für
  letzteres gibt es `last_run` je Job.
- **Fenster-Logzeile (C5-02b)** protokolliert Grenzen, keine Begründung der
  Alarmentscheidung.
- **`check-gregor20.sh` bleibt unverändert** (Auswertung von `failed_units` aus
  Scheibe B ist weiterhin ein Folgeschritt in `henemm-infra`).

## Out of Scope

- Änderung der Alarmentscheidung, des Zeitpunkts, der Kanäle oder der Texte.
- Provider-Umschaltung bei leerer INCA-Antwort (nur Beobachtbarkeit).
- Persistenz der Dämpfung über Neustarts hinaus.
- Auswertung von `failed_units`, `alert_fetch` oder der neuen Logzeilen im
  Monitor-Skript (`henemm-infra`).
- Änderungen an den `X-GZ-*`-Mail-Headern oder am Mail-Inhalt.
- Auslösen der neuen Admin-Trigger auf Prod als Nachweis.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Umsetzung von ADR-0018 („Fallback ohne Kaschieren")
- **Rationale:** Alle sechs Einträge machen bestehendes Verhalten beobachtbar, ohne
  eine Grundsatzentscheidung zu ändern. Festgehalten sind die Einzelentscheidungen:
  eine Message-ID je Empfänger-Zustellung, stabil über Retry/Fallback; zeitbasierte
  statt prozessweiter Dämpfung, damit der 26-h-Streak nicht abreißt; Aufbewahrung je
  Quelle nach Alter mit Gesamtdeckel statt je Verzeichnis nach Anzahl; Nachweis der
  Admin-Trigger ohne Prod-Auslösung.

## Changelog

- 2026-10-08: Initial spec created (Issue #2218 Scheibe C, Analyse
  `docs/context/fix-2218-scheibe-c-observability.md`). Sechs Einträge in einer Spec:
  C5-53, C5-15, C5-37, B2-71, C5-47, C5-02 (a+b+c).
- 2026-10-08 (v1.1): An den Umsetzungsstand angeglichen (PO-Beschluss). C5-47: Dämpfung
  erst nach Schreiberfolg, `track_resolution_health.py` neu in Affected Files, neue AC-31;
  AC-1: Absender = Bestandsverhalten `_reply_to or _from`; AC-25: Routenzahl 101/123
  (97/119 ohne Staging-Routen) statt 84/104, Inventarzeile `premium-sms-learn`;
  C5-02c/AC-28: `ok` nur bei verwertbaren Radardaten, `throttled`/`data_unavailable`
  buchen nichts; Test-Plan: SMTP-Attrappe statt lokalem Testserver (offen benannt);
  `_dial_and_send`-Rückgabe nur für die Erfolgszeile; Commit-Schnitt je Eintrag;
  Scope +235/−33, 12 produktive Dateien.
