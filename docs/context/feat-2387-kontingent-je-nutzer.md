# Context: feat-2387-kontingent-je-nutzer

**Issue:** #2387 (Scheibe S1 von #2150, Epic #2138) · **Track:** Full Process · Stand 2026-09-20

## Request Summary

Das Open-Meteo-Tageskontingent wird heute global gezaehlt: ein Nutzer, der viel abruft, treibt
den gemeinsamen Zaehler ueber die Schwellen und schaltet damit die Alarm-Pruefung **aller
anderen** Nutzer ab. S1 soll dafuer sorgen, dass der Verbrauch eines Nutzers nicht mehr die
Alarme der uebrigen drosselt.

## Ist-Stand des Zaehlers

| Was | Wo |
|---|---|
| Gate-Klasse `ForecastBudgetGate` | `src/services/forecast_budget.py` (216 Zeilen, eine Klasse) |
| Schwellen | `DAILY_BUDGET = 9000` (nicht ENV-uebersteuerbar), `POLLING_THRESHOLD = 0.80`, `BRIEFING_ONLY_THRESHOLD = 0.95` (`:40-42`) |
| Konstruktor | `__init__(data_root: Optional[Path] = None)` (`:44-50`) — **kein `user_id`** |
| Ablage | eine Datei fuer alle: `get_data_root()/diagnostics/forecast_budget.json` |
| Format | `{"date": "...", "calls": {"openmeteo": N}, "cache_hits": N, "cache_misses": N}` — `calls` ist eine Provider-Map |
| Oeffentliche API | `allow(priority, now=None)` · `record_call()` · `record_cache_hit()` · `record_cache_miss()` · `snapshot()` |
| Prioritaeten | `user_briefing` nie gedrosselt (ohne Dateizugriff, `:64-65`) · `polling` ab 80 % · `alert_check` ab 95 % · unbekannt -> nie |
| Schreibmechanik | `_safe_update` (`:175-215`): fcntl-Sidecar-Lock (`<datei>.lock`), Timeout 2 s, Reload-Merge-Write, `mkstemp`+`os.replace` |
| Tagesreset | lazy, `_today_utc(now)` (`:123`), Uhr injizierbar; **nie** `date.today()` (Adversary-Fund F002). Datumswechsel liefert frische Nullstruktur, ohne die Datei zu ersetzen |
| Fail-open | sechs Stellen, u.a. Lesefehler -> `allow()==True`, Lock-Timeout -> WARNING + stiller Zaehlverlust, `snapshot()` -> `status: "unavailable"` |

## 🔴 Vier Randbedingungen, die den Zuschnitt bestimmen

### 1. Das Kontingent ist ein Konto-Limit, keine Nutzer-Berechtigung

Open-Meteo sieht **ein** Konto fuer das ganze Deployment; `DAILY_BUDGET = 9000` ist die
Sicherheitsmarge unter dessen 10k-Limit. Ein reiner Zaehler je Nutzer mit je 9000 wuerde bei
N Nutzern N x 9000 Upstream-Calls erlauben. Das Repo argumentiert genau das fuer den
Schwesterzaehler: `src/services/official_alerts/meteoalarm_budget.py:76-77` — „Ein einfaches
Tagesbudget UEBER ALLE Laender -- kein pro-Land-Zaehler, das Tageskontingent ist ein Konto
der API."

**Folge fuer die Spec:** Der globale Zaehler bleibt als Schutz des Kontos. Zusaetzlich entsteht
ein Zaehler **je Nutzer**, der entscheidet, **wen** die Drosselung trifft, sobald es eng wird —
den Vielverbraucher, nicht alle. Gegenbeispiel fuer einen legitim nutzerbezogenen Zaehler:
`src/services/alert_daily_limit.py:110`, dort ist das Limit eine Tarif-Berechtigung.

**Praezedenz im Haus:** ADR-0070 (#2149 Scheibe B, 16.09.) hat genau dieses Muster fuer die
Zeit eingefuehrt — „Budget je Nutzer + Gesamtbudget je Lauf", inklusive **Rotation der
Nutzerreihenfolge**, „damit nicht immer derselbe Nutzer hinten steht". Dieselbe Fairness-Frage,
andere Ressource.

### 2. Die Nutzerkennung liegt an 8 von 13 Aufrufpfaden bereits bereit — an 5 nicht

Instanziiert wird das Gate produktiv an genau **zwei** Stellen: `segment_weather.py:128-130`
und `radar_service.py:509-510` (beide ohne Argument). Gereicht wird `priority` ueber zwei
Einstiege: `SegmentWeatherService.fetch_segment_weather(..., priority=)` und
`RadarNowcastService.get_nowcast(..., priority=)`, beide mit Default `user_briefing`.

| # | Aufrufer | Prioritaet | `user_id` da? | Quelle |
|---|---|---|---|---|
| 1-3 | `trip_alert.py:1810`, `:1844`, `:2464` | polling / alert_check | ✅ | `self._user_id` (`:348/367`) |
| 4 | `compare_radar_alert.py:475` | polling | ✅ | `self._user_id` (`:114/119`) |
| 5 | `trip_report_scheduler.py:1984` | polling | ✅ | `self._user_id` (`:417/427`) |
| 10 | `trip_report_scheduler.py:2212` | user_briefing | ✅ | `self._user_id` |
| 7-8 | `trip_command_processor.py:2530` (`_show_strecke`) | user_briefing / polling | ✅ | Parameter `user_id` (`:2439`) |
| 6 | `trip_command_processor.py:2422` (`_show_now`, `/jetzt`) | user_briefing | ⚠️ eine Ebene hoeher | `msg.user_id` an `:920` — Signatur erweitern |
| 9 | `compare_location_weather_source.py:174` | alert_check | ❌ | Aufrufer haetten sie (`compare_alert.py:500`, `scheduler_dispatch_service.py:776`); beruehrt das Protocol `point_weather.py:67-84` |
| 11 | `segment_weather.py:533` (`fetch_night_weather`) | user_briefing | ❌ | Aufrufer haetten sie (`trip_report_scheduler.py:2293`, `preview_service.py:242`) |
| 12 | `stage_weather.py:56` (`_fetch_one`) | user_briefing | ❌ | Aufrufer `api/routers/internal.py:77` hat sie als Pflicht-Query-Param |
| 13 | `thunder_enrichment.py:255` via `providers/openmeteo.py:1166/1289/1303` | user_briefing | ❌ **teuerster Fall** | Die Provider-Schicht ist bewusst nutzerfrei |

Ein Rueckfall auf `"default"` ist gesperrt: `tests/test_user_id_default_guard.py:286` ist eine
AST-Ratsche ueber `src/`, `api/`, `tools/`. Fuer #13 ist zu entscheiden: Durchreichung durch die
Provider-Schicht **oder** eine bewusst unattributierte Buchung in den globalen Topf — dort ist
die Prioritaet ohnehin `user_briefing`, also nie gedrosselt; betroffen waere nur die Zaehlung.

### 3. Ein Go-Leser haengt am globalen Pfad und faellt still aus

- `internal/scheduler/forecast_budget_health.go:119-127` baut `<DataDir>/diagnostics/forecast_budget.json`
- `internal/scheduler/scheduler.go:1168` stellt das als `forecast_budget` an `/api/scheduler/status`
- Fehlt die Datei: `status: "unavailable"` (`:54-64`) — ein Pfadwechsel schaltet das Betriebssignal
  **still** ab statt laut zu brechen. Konsument: `check-gregor20.sh` (Infra-Monitoring).
- `forecast_budget_health.go:13/22/23` spiegelt die drei Konstanten; `TestForecastBudgetConstantsMatchPython`
  (`forecast_budget_health_test.go:256`) **liest den Python-Quelltext zur Laufzeit** und wird rot,
  sobald eine Konstante verschoben oder umbenannt wird.
- ⚠️ Der Status-Endpunkt ist **ohne Anmeldung** erreichbar (`internal/middleware/auth.go:50`) —
  Nutzerkennungen dort auszuweisen waere eine neue Informationspreisgabe. Aggregat statt Liste.

### 4. Es gibt gar kein ADR zum Budget-Gate — der Verweis im Code ist eine Nummernkollision

`forecast_budget.py:38` beruft sich auf „ADR-0032"; `docs/adr/0032-...md` ist aber die
Wizard-Abschaffung. Ursache: `docs/specs/modules/fix_1329_forecast_cache_budget.md:426` trug
ADR-0032 als *Vorschlag* ein, die Nummer war vergeben, das ADR wurde nie angelegt. Die einzigen
bindenden Entscheidungstexte stehen in dieser Spec (`:424-441`):

- Budget-Steuerung ueber **statische Prioritaetsklassen mit festen Schwellen**, kein adaptiver Rate-Limiter
- Produktgrundsatz: **„kein Nutzer-Briefing wird je wegen Budget verworfen"**
- Beide Entscheidungen sind an die **Ein-Prozess-Topologie** gebunden
- Go-Vertrag (`:290-317`): „Python bleibt Single Source of Truth fuer die Schwellenwerte — Go
  berechnet nur zur Anzeige, keine eigene Entscheidungslogik"

**Folge:** S1 braucht ein neues ADR (Nummer >= 0075), das zugleich diese Luecke schliesst und den
Fehlverweis im Code korrigiert. Auch die **Fail-open-Semantik je Nutzer** ist heute nirgends
entschieden („fremder Nutzer-Topf unlesbar -> global weiterzaehlen oder durchlassen?").

## Bindende ADRs

| ADR | Bindung fuer S1 |
|---|---|
| **ADR-0003** Mandantentrennung | Hoechste. Echte `user_id` durchreichen, kein `"default"`; seit #2156 maschinell durchgesetzt (`store_scope_call_guard_test.go`, `tests/test_router_user_id_required.py`). Zwei-Nutzer-Test ist Pflicht |
| **ADR-0031** Dateibasierte Persistenz | Zielverzeichnis `data/users/<id>/`; **Read-Modify-Write mit Merge, nie Replace**; Schema-Aenderungen brauchen idempotente Migrationsskripte |
| **ADR-0070** Wartebudget je Nutzeraufruf | Praezedenz fuer „je Nutzer + Gesamtdeckel" inkl. Reihenfolge-Rotation |
| **ADR-0039** kontingentfreier MeteoAlarm-Feed | Lehrstueck: Kontingent-Zusammenbruch mit Rueckkopplung, „keine Effizienz-, sondern eine Sicherheitsfrage" |
| **ADR-0029** Open-Meteo als Standard | „ein Kontingent-Modell"; Folgepflicht: neue Abruf-Pfade gegen das Kontingent denken |

## Zu uebernehmende Muster (nichts neu erfinden)

| Zweck | Vorlage |
|---|---|
| Konstruktor-Umstellung | `ThrottleStore.__init__(user_id, data_dir=None)` (`throttle_store.py:60-68`) — `forecast_budget.py` nennt es bereits als kopiertes Muster; Ziel: `ForecastBudgetGate(user_id, data_dir=None)` |
| Pflicht-Parameter ohne Default | `alert_daily_limit.py:89-93` („ein Default waere ein stiller Rueckfall") · `loader.py:426-430` (#2151-Wurf) |
| Schreibmechanik | `throttle_store.py:197-245` — Sidecar-Lock + Reload-Merge-Write (hat `forecast_budget` schon; nur der Pfad wechselt, je Nutzer ein Lockfile -> weniger Contention) |
| Nutzerpfad + Validierung | `loader.py:1169-1183` (`get_data_dir`), `VALID_USER_ID_RE` (`:1154`), Paritaet zu Go: `tests/unit/test_user_id_pattern_parity.py` |
| Migration | `ThrottleStore._migrate_if_needed()` (`:247-268`) — idempotent, Merge innerhalb des Locks, `setdefault` statt Ueberschreiben. Alternativ der etablierte Praezedenzfall „global stehen lassen, je Nutzer frisch beginnen" (`track_resolution_health.py:24-28`); bei einem Tageszaehler laeuft der Bestand binnen 24 h aus |
| Isolationstest | `tests/tdd/test_alarm_szenario_mandantentrennung.py:152` — **inklusive Gegenlesung** (B's Schluessel unter A's Kennung lesen, Abwesenheit zusichern) **und Positivkontrolle** unter B. Ohne Gegenlesung faengt der Test einen faelschlich geteilten Pfad nicht (Fund F001, `:215-230`) |

## Tests, die S1 beruehrt

- `tests/unit/test_forecast_budget_gate.py` — 12 Tests (Schwellen, Fail-open, UTC-Tageswechsel, E2E ueber `SegmentWeatherService`)
- ⚠️ `tests/unit/test_radar_budget_and_priority.py:363` `test_openmeteo_funnel_records_against_shared_budget_counter`
  — **bricht zwangslaeufig**: er sichert woertlich die Zaehlung „gegen den *geteilten* Budget-Zaehler" zu
- `tests/tdd/test_file_lock_timeout.py` — parametrisierter Zweig `"forecast_budget"` mit `data_root=tmp_path` (`:178-182`)
- `tests/tdd/test_strecke_abrufpriorisierung.py`, `tests/tdd/test_radar_nowcast_health_journal.py`,
  `tests/unit/test_radar_upstream_failure.py` — praeparieren die Zaehlerdatei als Kulisse
- AST-Waechter: `tests/test_output_timezone_guard.py:656` (Allowlist `forecast_budget.py::_today_utc::0`,
  Begruendung „kein Nutzerdatum" wird bei Nutzer-Partitionierung anfechtbar),
  `tests/test_success_status_guard.py` (nutzt `snapshot()` als kanonisches Positivbeispiel)
- Go: 9 Tests in `internal/scheduler/forecast_budget_health_test.go`

## Risiken

1. **Blinde Flecken machen die Trennung wertlos.** Drei Pfade umgehen Cache **und** Gate
   vollstaendig (`comparison_engine.py`, `forecast.py`, `trip_forecast.py` —
   `fix_1329_forecast_cache_budget.md:415-422`, bewusster Scope-Schnitt damals). Zusaetzlich
   erfasst der Verbrauchslog `openmeteo_calls.jsonl` den Radar-Pfad nicht, obwohl dieser den
   Verbrauch dominiert (#1329, `decision_matrix.md:268-274`). Die Spec muss sagen, was gezaehlt wird.
2. **Stiller Ausfall der Betriebssicht** bei Pfadwechsel ohne Go-Anpassung.
3. **Neue Informationspreisgabe**, wenn der unauthentifizierte Status-Endpunkt Nutzerkennungen ausweist.
4. **Durchreichung ohne Rueckfall:** jede Stelle ohne echte `user_id` muss laut brechen; #13
   (Provider-Schicht) braucht eine dokumentierte Entscheidung.
5. **Lost Update** bei parallelen Laeufen — die Sidecar-Lock-Mechanik mitnehmen.
6. **LoC:** Kern + 5 Signaturen + Go + Tests sprengt das 250er-Limit -> `loc_limit_override`.

## Analysis

### Type

**Bugfix** — Issue #2387 trägt `bug`, Triage `[triage:a]` (nutzersichtbares Fehlverhalten:
Alarme unbeteiligter Nutzer fallen aus). S1 von vier Scheiben aus #2150, Epic #2138.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/forecast_budget.py` | MODIFY | Kern: `ForecastBudgetGate(user_id, data_dir=None)` nach Muster `ThrottleStore`; Zählerdatei von `diagnostics/` nach `data/users/<id>/`; fairer Anteil + Gesamtdeckel; idempotente Migration; Fehlverweis „ADR-0032" korrigieren |
| `src/services/segment_weather.py` | MODIFY | Instanziierung `:128-130` bekommt `user_id`; `fetch_night_weather` `:533` (Pfad 11) Signatur erweitern |
| `src/services/radar_service.py` | MODIFY | Zweite produktive Instanziierung `:509-510` |
| `src/services/compare_location_weather_source.py` | MODIFY | Pfad 9 (`alert_check`, `:174`) — `user_id` von `compare_alert.py:500` / `scheduler_dispatch_service.py:776` durchreichen |
| `src/services/point_weather.py` | MODIFY | Protocol `:67-84` — von Pfad 9 zwingend mitberührt |
| `src/services/stage_weather.py` | MODIFY | Pfad 12 (`_fetch_one`, `:56`) |
| `api/routers/internal.py` | MODIFY | `:77` reicht die bereits vorhandene Pflicht-Query-`user_id` an Pfad 12 weiter |
| `src/services/trip_command_processor.py` | MODIFY | Pfad 6 (`_show_now`, `/jetzt`, `:2422`) — `msg.user_id` von `:920` eine Ebene tiefer reichen |
| `src/services/thunder_enrichment.py` | MODIFY | Pfad 13 (teuerster Fall) — laut Spec E4 **bewusst unattributiert** im globalen Topf, Provider-Schicht bleibt nutzerfrei |
| `internal/scheduler/forecast_budget_health.go` | MODIFY | `:119-127` liest den alten globalen Pfad — muss über Nutzer-Töpfe aggregieren, sonst fällt `/api/scheduler/status` **still** auf `unavailable` (Konsument: `check-gregor20.sh`). Aggregat, **nie** Nutzer-Liste (Endpunkt ist unauthentifiziert) |
| `docs/adr/0075-*.md` | CREATE | ADR-0075: Budget je Nutzer + Gesamtdeckel, Fail-open-Semantik je Nutzer, Ablösung des Fehlverweises |
| `tests/unit/test_forecast_budget_gate.py` | MODIFY | 12 Bestandstests auf den Nutzer-Konstruktor umschreiben |
| `tests/unit/test_radar_budget_and_priority.py` | MODIFY | ⚠️ `:363` sichert wörtlich den **geteilten** Zähler zu — bricht zwangsläufig, muss umformuliert werden |
| `tests/tdd/test_file_lock_timeout.py` | MODIFY | Parametrisierter Zweig `"forecast_budget"` `:178-182` |
| `tests/test_output_timezone_guard.py` | MODIFY | Allowlist `:656` — Begründung „kein Nutzerdatum" wird durch die Partitionierung anfechtbar; neue Begründung: Schnitt ist bewusst UTC (Konto-Limit), nicht nutzerlos |
| `tests/tdd/test_budget_mandantentrennung.py` | CREATE | Zwei-Nutzer-Isolation nach Muster `test_alarm_szenario_mandantentrennung.py:152` — **inkl. Gegenlesung** (B's Schlüssel unter A lesen, Abwesenheit zusichern) **und Positivkontrolle** unter B; ohne Gegenlesung fängt der Test einen fälschlich geteilten Pfad nicht (F001) |
| `internal/scheduler/forecast_budget_health_test.go` | MODIFY | 9 Tests; `TestForecastBudgetConstantsMatchPython` `:256` liest den Python-Quelltext zur Laufzeit und wird rot, sobald eine Konstante wandert |

### Scope Assessment

- **Files:** ~17 (10 produktiv inkl. Go, 5 Test-MODIFY, 2 CREATE)
- **Estimated LoC:** ~+320–370
- **Risk Level: HIGH**
  - berührt die Mandantentrennung (ADR-0003, seit #2156 maschinell durchgesetzt)
  - berührt ein Drosselungs-Gate auf dem Alarm-Pfad — ein Fehler schaltet Alarme ab
  - Pfadwechsel kann das Betriebssignal `/api/scheduler/status` **still** abschalten
  - 🔴 **`loc_limit_override` ist vor der Implementierung zu setzen** — das 250-LoC-Limit wird strukturell gerissen

### Technical Approach

Empfehlung: **kopiertes Muster statt Neuerfindung.** `forecast_budget.py` nennt `ThrottleStore`
bereits als Vorlage — dieselbe Umstellung nachziehen:

1. `ForecastBudgetGate(user_id, data_dir=None)` mit **Pflicht-Parameter ohne Default**
   (`alert_daily_limit.py:89-93`: „ein Default wäre ein stiller Rückfall"). Der Rückfall auf
   `"default"` ist ohnehin durch die AST-Ratsche `tests/test_user_id_default_guard.py:286` gesperrt.
2. Ablage `data/users/<id>/…` über `loader.get_data_dir` (`:1169-1183`) mit `VALID_USER_ID_RE`
   (`:1154`); Schreibmechanik bleibt Sidecar-Lock + Reload-Merge-Write (`throttle_store.py:197-245`)
   — je Nutzer ein Lockfile, also **weniger** Contention als heute.
3. **Zwei Schwellen statt einer:** fairer Anteil `DAILY_BUDGET / N` je Nutzer **plus** globaler
   Gesamtdeckel als Kontoschutz gegenüber Open-Meteo. Präzedenz: ADR-0070 (Wartebudget je
   Nutzeraufruf, „je Nutzer + Gesamtdeckel").
4. Migration idempotent nach `ThrottleStore._migrate_if_needed()` (`:247-268`, Merge im Lock,
   `setdefault`) — alternativ der etablierte Präzedenzfall „global stehen lassen, je Nutzer frisch
   beginnen" (`track_resolution_health.py:24-28`); bei einem **Tages**zähler läuft der Bestand
   binnen 24 h ohnehin aus.
5. Go-Seite aggregiert über die Nutzer-Töpfe und behält die vier bekannten Felder bei; Python
   bleibt Single Source of Truth für die Schwellen (Go-Vertrag `fix_1329…:290-317`).

### Dependencies

Bindend: **ADR-0003** (Mandantentrennung, höchste Bindung — Zwei-Nutzer-Test Pflicht) ·
**ADR-0031** (Dateibasierte Persistenz: `data/users/<id>/`, Read-Modify-Write mit Merge, **nie
Replace**) · **ADR-0070** (Präzedenz je Nutzer + Gesamtdeckel) · **ADR-0029** (Kontingent-Modell).
Module: `throttle_store.py`, `loader.py`, `alert_daily_limit.py`, `forecast_budget_health.go`.

### Open Questions

- [ ] 🔴 **PO-Entscheid vor der Spec-Freigabe (Scope-Frage, nicht technisch):** Bei **100 %
      Gesamtverbrauch** drosselt AC-8 **jeden** Nutzer — auch einen, der weit unter seinem fairen
      Anteil liegt. Das ist genau die Kernbeschwerde des Tickets, und sie bleibt damit teilweise
      stehen. Der faire Anteil ist zudem eine **Momentaufnahme**, die sinkt, wenn im Tagesverlauf
      weitere Nutzer aktiv werden — wer früh am Tag allein unterwegs war, kann viel verbraucht
      haben, und die Spätankömmlinge zahlen dafür. Frage an den PO: ist dieses Restverhalten für
      **S1** akzeptabel, oder braucht es eine Reservierung für noch nicht aktive Nutzer — in S1
      oder in einer benannten späteren Scheibe von #2150?
- [x] Fall #13 (`thunder_enrichment.py`, teuerster Pfad): **entschieden** — bewusst unattributiert
      im globalen Topf (Spec E4), Provider-Schicht bleibt nutzerfrei. Priorität dort ist ohnehin
      `user_briefing`, wird also nie gedrosselt; betroffen ist allein die Zählung.
- [x] Fail-open-Semantik je Nutzer („fremder Topf unlesbar → global weiterzählen oder
      durchlassen?"): heute nirgends entschieden, **wird in ADR-0075 festgelegt**.
- [x] Go-Status-Endpunkt: **Aggregat statt Nutzer-Liste** — der Endpunkt ist unauthentifiziert
      (`internal/middleware/auth.go:50`), eine Liste wäre neue Informationspreisgabe.

### Hinweis für `/30-write-spec`

- Spec-Entwurf liegt bereits auf der Platte: `docs/specs/modules/forecast_budget_je_nutzer.md`
  (22 KB, `## Acceptance Criteria` vorhanden). Im Workflow-State ist sie noch **nicht**
  registriert (`Spec: Not created`) — das muss `/30-write-spec` nachholen.
- PO-Briefing liegt vor: `docs/briefings/feat-2387-kontingent-je-nutzer.md`.
  🔴 **`set-briefing` erst registrieren, wenn der Spec-Text steht** — das Gate ist SHA256-an den
  Spec-**Inhalt** gebunden; ändert der PO wegen der offenen AC-8-Frage etwas, verfällt die
  Registrierung und ein neuer `po-briefer`-Lauf wird fällig.
