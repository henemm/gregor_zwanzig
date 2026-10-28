# Context: refactor-2266-meteoalarm-edr-rueckbau

## Request Summary
Issue #2266 (Epic #2258): Die seit #1445 S3 nicht mehr registrierte EDR-Klasse `MeteoAlarmSource`
samt Index-/Budget-/Drossel-/Geometrie-Apparat entfernen; der geteilte CAP-Mapper bleibt, weil der
kontingentfreie Feed-Weg (`MeteoAlarmFeedSource`, IT/AT/DE) ihn nutzt. Zusätzlich Prüfpunkt Lizenz:
Feed-Cache-TTL 30 min vs. EUMETNET-Weitergabe-Auflage (5–10 min Verzug).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm.py` (1116 Z.) | EDR-Apparat (~:43–:503, :677–:1116) löschen; CAP-Mapper :475–:666 bleibt (`_TYPE_HAZARD_MAP`, `_DISCARDED_TYPES`, `_local_tag`, `_child_text`, `_find_parameter`, `_find_area_desc`, `_leading_int`, `_parse_iso`, `_pick_preferred_entry`, `_collect_cap_info_entries`, `_group_and_map_info_entries`, `_extract_alerts_from_cap`); Modul-Docstring :1–15 neu (verweist auf alten Spec-Pfad) |
| `src/services/official_alerts/meteoalarm_feed.py` | Feed-Weg; importiert aus meteoalarm.py nur `_group_and_map_info_entries` (:36); TTL über `warn_egress.cached_fetch`-Default (:256–270) |
| `src/services/official_alerts/meteoalarm_budget.py` | `MeteoAlarmBudgetGate` — einziger Nutzer meteoalarm.py → Folge-Totcode |
| `src/services/official_alerts/__init__.py:36–41` | Kommentar „bleibt für Äquivalenznachweis AC-5 erreichbar" — Nachweis seit f2cf05d0 über JSON-Snapshots erledigt |
| `src/services/warn_egress.py` | `RateLimitRetryPolicy` :248, `parse_ratelimit_reset` :230, `on_response`, `self_throttled`-Zweig :544 — einziger Produktivnutzer meteoalarm.py → Folge-Totcode (Abwägung: generisch oder entfernen) ; `WARN_SUCCESS_TTL=1800` :41 |
| `src/services/parallel_fetch.py:30` | `_DEFAULT_SLOTS["meteoalarm"]` tote Konfiguration |
| `src/app/egress_guard.py:43,46` · `internal/egress/inventory.go:34,37` | `api.meteoalarm.org`/`feeds.meteoalarm.org` als `BLOCKED` (= deklariert, in Test/Staging gesperrt; Prod No-Op). Drift-Wächter `tests/test_egress_inventory_drift.py` erzwingt Deckungsgleichheit |
| `internal/scheduler/warn_service_health.go:170–235,266,306` | Go spiegelt `meteoalarm_budget` (Env `GZ_METEOALARM_DAILY_BUDGET`) in `warn_service_health` des Scheduler-Status |
| `src/output/renderers/alert/official_alerts.py:117–118` | Schlüssel `"meteoalarm"` BLEIBT (Feed erzeugt `source="meteoalarm"`), nur Kommentar veraltet |
| `src/services/official_alerts/dpc.py:4,54` | nur Docstring-Erwähnungen |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:502–555` | **externer Konsument**: liest `warn_service_health.meteoalarm_budget` (tolerant `or {}`, :553) und schließt den Schlüssel bei der Dienstauswertung aus (:513) |

## Existing Patterns
- Rückbau-Muster: Ratschen-/Wächter-Einträge mitziehen (Stale-Check schlägt sonst fehl), Python- und Go-Egress-Inventar synchron halten.
- Warn-Abrufe laufen über `warn_egress.cached_fetch` (Erfolg 1800 s / Fehlschlag 60 s), Journal `data/diagnostics/warn_service_calls.jsonl`, Go kanonisiert Servicename bis zum ersten `:` (`meteoalarm` vs. `meteoalarm_feed`).
- Äquivalenz-Gates der Feed-Tests (AC-3 IT, AC-5 AT) vergleichen gegen eingefrorene Snapshots `tests/fixtures/meteoalarm_feed/edr_snapshot_{it,at}.json` — keine Laufzeitabhängigkeit von der EDR-Klasse.

## Dependencies
- Upstream (vom EDR-Apparat genutzt): `httpx`, `warn_egress` (RateLimitRetryPolicy, cached_fetch, Journal), `meteoalarm_budget`, `point_in_geometry`, `lookup_department`, radar_service-Konstanten.
- Downstream: keine Produktiv-Registrierung (nur Feed IT/AT/DE); Go-`warn_service_health` (Budget-Block) → infra `check-gregor20.sh`.

## Tests (Betroffenheit)
- **Ganz löschbar:** `tests/tdd/test_meteoalarm_index_coverage.py` (live), `tests/tdd/test_meteoalarm_budget_buchung_im_abrufpfad.py`.
- **Großteils löschbar, Mapper-Tests umziehen:** `tests/tdd/test_meteoalarm_source.py` (live; Mapper-Tests :206, :238, :313, :395, :540, :697, :786, :2346, :2380 bleiben fachlich relevant; gemischt :2251, :2306).
- **Einzeltest anpassen:** `test_meteoalarm_feed_italien.py:1230–1275` (AC-7 nutzt EDR-Klasse), `test_isolation_warn_services.py:56,133` (KeyError bei Inventar-Entfernung), `test_warn_service_health_journal.py:134` (importiert `_MeteoAlarmBudgetExhausted`), `test_avalanche_report_region_mapper.py:149–179` (nutzt Alias `meteoalarm._point_in_geometry`).
- **Bei Entfernen von `meteoalarm_budget.py`:** `tests/unit/test_meteoalarm_budget_gate.py`, `test_meteoalarm_budget_reserve_atomic.py`, `test_budget_reserve_lock_timeout_is_loud.py`, `test_file_lock_timeout.py:52,188–210`, Ratsche `test_output_timezone_guard.py:671–672` (Stale-Check :769), Go `warn_service_health_test.go:105–146`.
- **Bei Entfernen von `RateLimitRetryPolicy`:** `test_warn_service_egress.py:376–712`, `tests/unit/test_warn_egress_capture_id_after_retry.py`, `…_stale_after_failed_capture.py`.
- Unberührt: Mapper-Nutzer (`test_meteoalarm_lawine_cap.py`, `test_meteoalarm_feed_deutschland.py`, `test_avalanche_*`, `test_sms_official_alert_tokens.py`, `test_official_alert_allclear.py`), Ratsche `test_resolution_loss_guard.py:743,878` (`_collect_cap_info_entries` bleibt).
- Viele betroffene Dateien sind modulweit `pytest.mark.live` → nicht im Kern-CI; Löschung reduziert keine Kern-Abdeckung, aber Mapper-Tests daraus sollten in den Kern umziehen.
- Fixtures: `tests/fixtures/meteoalarm/` enthält EDR-only-Dateien (index_*, geometry_sample, at_publication_profile, cap_villach_heat*) und Mapper-Fixtures (cap_green_level1, cap_broken, cap_*_ro, cap_avalanche_plus_heat, feed_avalanche_type9). `tests/fixtures/meteoalarm_feed/` bleibt komplett.

## Existing Specs
- `docs/specs/_archive/modules/issue_1086_meteoalarm_source.md` (Ursprung EDR)
- `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md`, `fix_1397_s4_it_grenze.md`, `warn_service_consumption.md`, `warn_service_isolation.md`, `egress_guard.md`, `fix_1422_warn_ausfall_alarm.md`
- Feed: `feat_1445_s1_feed_bestandsquelle.md`, `feat_1445_s3_oesterreich_feed.md`, `feat_1681_meteoalarm_de.md`, `fix_1430_meteoalarm_lawine.md`
- `docs/specs/data_sources.md` Antrag #2 (~:285–302): `api.meteoalarm.org` + `meteo.fra1.digitaloceanspaces.com` noch als genehmigt/„Code bleibt bis Äquivalenznachweis"
- ADR-0039 (:42 „Rückbau ist eigene Folgearbeit"), ADR-0044 (:48, :199, :279 Budget), ADR-0074 (Feed-TTL DE), `docs/features/architecture.md:795`

## Offene Punkte für die Analyse
1. **Schnitt-Tiefe:** nur `meteoalarm.py`-EDR, oder auch Folge-Totcode (`meteoalarm_budget.py`, Go-Budget-Spiegel, `RateLimitRetryPolicy`, `parallel_fetch`-Slot)? Folge-Totcode erhöht den Umfang deutlich (Go + infra-Konsument).
2. **Egress-Inventar:** Ticket-AC-3 will `api.meteoalarm.org` „weder erlaubt noch referenziert". Da undeklarierte Hosts ohnehin gesperrt werden, ist Entfernen verhaltensneutral; `test_isolation_warn_services.py` muss mit.
3. **Aufzeichnungsskript:** existiert nicht im Repo (Ad-hoc-Lauf mit `MeteoAlarmSource.fetch()`, README `tests/fixtures/meteoalarm_feed/README.md:28–30,154–156`) → dokumentiert streichen, README anpassen.
4. **Lizenz-TTL:** Keine Lizenzquelle im Repo; nur Latenzangabe „REST 10 min verzögert" (`docs/context/fix-1397-wiederanlauf-ausbruch.md:145`). Feed-TTL 1800 s (`warn_egress.py:41`), Alarm-Scheduler `*/15` (`internal/scheduler/scheduler.go:345,354`). Die Auflage (falls sie gilt) verlangt einen *Mindest*-Verzug bei Weitergabe — 30 min Cache bedeutet *mehr* Verzug, nicht weniger; zu klären, ob die Auflage überhaupt eine Obergrenze nennt (Primärquelle: MeteoAlarm-Nutzungsbedingungen).
5. **Externer Konsument:** `check-gregor20.sh` liest `meteoalarm_budget` tolerant — Entfernen des Blocks ist dort unschädlich, Kommentarpflege in henemm-infra ggf. nachziehen.

## Risks & Considerations
- Zu weit gezogene Löschung trifft den CAP-Mapper → amtliche Warnungen AT/IT/DE fallen still aus (genau die Fehlerart aus Epic #2505). Kern-Tests für den Mapper müssen vor dem Löschen grün und im Kern (nicht nur `live`) liegen.
- `_extract_alerts_from_cap`/`_collect_cap_info_entries` haben nach dem Rückbau keinen Produktivaufrufer mehr, bleiben aber wegen Tests/Ratsche — prüfen, ob das selbst toter Code wird.
- Ratschen-Stale-Checks (`test_output_timezone_guard.py`) und Python↔Go-Inventar-Drift brechen bei unvollständigem Rückbau.
- LoC-Limit: Löschung von ~1000+ Zeilen → `loc_limit_override` nötig.

## Analysis

### Type
Feature (Rückbau/Refactor, verhaltensneutral für Nutzer)

### Entscheidung Schnitt-Tiefe (Tech Lead)
| Variante | Umfang | LoC (grob) | Go/infra |
|---|---|---|---|
| A | nur EDR-Klasse/Index/Geometrie in `meteoalarm.py` + Inventar | ca. −900/+30 | Go-Inventar; Budget-Spiegel bliebe Waise |
| B | A + `meteoalarm_budget.py` + Go-Budget-Spiegel + `parallel_fetch`-Slot | ca. −1450/+40 | `warn_service_health.go` |
| **C (gewählt)** | B + `RateLimitRetryPolicy`/`parse_ratelimit_reset`/429-Retry-Zweig in `warn_egress.py` | ca. −1550/+40 | wie B |

**Gewählt: C in EINEM Workflow.** Begründung: Nach A/B ist die 429-Retry-Logik ebenfalls ohne Produktivnutzer (einziger Aufrufer `meteoalarm.py:81,724`). Ein Folge-Ticket nur für diesen Rest widerspricht der Regel „Epics themenweise abschließen, nie Reste abspalten". Risiko gering: kein anderer Warndienst übergibt `rate_limit_retry`. `self_throttled` im Journal bleibt (Feld wird von `enrichment_health.py` in anderem Kontext genutzt; im Warn-Journal nur noch konstant `False` → prüfen, ob Feld erhalten bleibt, um Journal-Schema/Go-Auswertung nicht zu brechen — Default: Feld bleibt).
LoC: Löschvolumen übersteigt 500 → in Phase 3 `workflow.py status` prüfen; `loc_limit_override` setzen. Tests/Docs zählen nicht.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm.py` | MODIFY | EDR-Apparat löschen, nur CAP-Mapper behalten (inkl. `_extract_alerts_from_cap`/`_collect_cap_info_entries` als dokumentierte CAP-XML-Schnittstelle für Tests/Ratsche), Modul-Docstring neu; KEIN Umbenennen |
| `src/services/official_alerts/meteoalarm_budget.py` | DELETE | einziger Nutzer war EDR |
| `src/services/official_alerts/warn_egress.py` | MODIFY | `RateLimitRetryPolicy`, `parse_ratelimit_reset`, 429-Retry-Zweig entfernen |
| `src/services/official_alerts/__init__.py` | MODIFY | veralteter Kommentar :36–41 |
| `src/services/parallel_fetch.py` | MODIFY | Slot `meteoalarm` :30 |
| `src/app/egress_guard.py` · `internal/egress/inventory.go` | MODIFY | `api.meteoalarm.org` synchron entfernen; `feeds.meteoalarm.org` bleibt |
| `internal/scheduler/warn_service_health.go` (+ `_test.go`) | MODIFY | Budget-Spiegel `meteoalarm_budget` entfernen |
| `src/services/file_lock.py`, `internal/scheduler/forecast_budget_health.go`, `dpc.py`, `output/renderers/alert/official_alerts.py:117` | MODIFY | nur Kommentare/Docstrings |
| `tests/tdd/test_meteoalarm_cap_mapper.py` | CREATE | Mapper-Tests aus `test_meteoalarm_source.py` (:206, :238, :313, :395, :540, :697, :786, :2346, :2380; :2251/:2306 entmischt) OHNE `live`-Marker in den Kern |
| `tests/tdd/test_meteoalarm_source.py`, `test_meteoalarm_index_coverage.py`, `test_meteoalarm_budget_buchung_im_abrufpfad.py`, `tests/unit/test_meteoalarm_budget_*`, `test_budget_reserve_lock_timeout_is_loud.py`, `tests/unit/test_warn_egress_capture_id_*` | DELETE | EDR/Budget/Retry-only |
| `test_meteoalarm_feed_italien.py:1230–1275`, `test_isolation_warn_services.py:56,133`, `test_warn_service_health_journal.py:134`, `test_avalanche_report_region_mapper.py:149–179`, `test_file_lock_timeout.py:52,188–210`, `test_warn_service_egress.py:376–712`, Ratsche `test_output_timezone_guard.py:671–672` | MODIFY | Bezüge auf Gelöschtes entfernen/umstellen |
| `tests/fixtures/meteoalarm/` | DELETE (teilweise) | EDR-only: `index_*`, `geometry_sample`, `at_publication_profile`, `cap_villach_heat*`; Mapper-Fixtures bleiben |
| `tests/fixtures/meteoalarm_feed/README.md` | MODIFY | Aufzeichnungsskript existiert nicht → dokumentiert streichen |
| `docs/specs/data_sources.md` Antrag #2, ADR-0039, ADR-0044, ADR-0074, `docs/features/architecture.md:795` | MODIFY | Rückbau + Lizenz-Prüfergebnis vermerken |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:502–555` | (MODIFY optional) | liest `meteoalarm_budget` tolerant (`or {}`) — keine Pflichtänderung, Kommentarpflege |

### Scope Assessment
- Dateien: ca. 30 (davon ~15 Tests, ~8 Doku)
- LoC: ca. −1550 / +40 Produktivcode, zzgl. Test-Umzug
- Risk Level: MEDIUM — reine Löschung, aber nahe am CAP-Mapper, der AT/IT/DE-Warnungen trägt (Fehlerart Epic #2505)

### Technical Approach
Reihenfolge: (1) Mapper-Tests in den Kern umziehen, grün gegen heutigen Stand; (2) `meteoalarm.py` auf Mapper kürzen; (3) Budget-Modul, Go-Spiegel, Slot, Inventar (Py+Go gleichzeitig) entfernen; (4) Retry-Policy aus `warn_egress.py`; (5) Tests/Ratschen/Fixtures nachziehen; (6) Doku. Nachweis AC-2 über bestehende Feed-Äquivalenz-Snapshots `tests/fixtures/meteoalarm_feed/edr_snapshot_{it,at}.json` (keine EDR-Laufzeitabhängigkeit). Achtung: Feed-Tests IT/AT sind `live` — Kern-Nachweis für AC-2 muss in einem ungemarkerten Test liegen (Fixture-basiert, ohne Netz).

### Lizenz-Prüfpunkt (Ergebnis)
- Im Repo keine Primärquelle für eine EUMETNET-Verzugsauflage; Websuche liefert nur „Verzug gegenüber meteoalarm.eu möglich", keine Minutenangabe.
- 30 min Feed-Raster ist bewusste, dokumentierte Entscheidung (ADR-0074: 1800 s Erfolg / 60 s Fehlschlag).
- Eine Auflage „mindestens 5–10 min Verzug" ist durch 30 min Cache erfüllt; eine Obergrenze ist nicht belegt.
- **Entscheidung:** keine TTL-Änderung (sonst neues ADR nötig ohne Beleg). Prüfergebnis in ADR-0074 bzw. `data_sources.md` dokumentieren.

### Dependencies
Feed-Weg (`meteoalarm_feed.py:36`) hängt nur an `_group_and_map_info_entries`. Go-`warn_service_health` → infra `check-gregor20.sh` (tolerant). Egress-Drift-Wächter Python↔Go.

### Open Questions
- keine PO-Fragen; Journal-Feld `self_throttled` im Warn-Journal bleibt erhalten (Schema-Stabilität) — in Spec festhalten.

### Übergabe Phase 5 → 6 (RED, 2026-10-27)
- **RED (müssen grün werden):** `tests/tdd/test_meteoalarm_edr_rueckbau.py` (AC-1, AC-4),
  `tests/tdd/test_meteoalarm_rueckbau_doku.py` (AC-7/AC-8, doc-compliance), Go
  `internal/egress/inventory_meteoalarm_test.go`, `internal/scheduler/warn_service_health_no_budget_test.go`.
- **Go-RED-Dateien sind bewusst UNGETRACKT** (touched_tests_gate blockt kompilierbare Go-RED-Tests) —
  erst mit GREEN committen. Go liegt unter `/usr/local/go/bin`.
- **Sicherungsnetz (grün am Altstand, muss grün bleiben):** `test_meteoalarm_cap_mapper.py`,
  `test_meteoalarm_feed_aequivalenz_snapshots.py`, `test_warn_journal_felder.py` (AC-6 + TTL 1800).
- **Abweichung von der Spec (Test Plan AC-2):** Äquivalenz speist Feed/ZAMG über den Cache-Weg
  (`meteoalarm_feed._cache`, `geosphere_warn._cache`) wie `test_meteoalarm_feed_deutschland.py`,
  NICHT über den lokalen Fake-Server — der braucht einen Socket und ist unter `--disable-socket`
  nicht lauffähig (Grund, warum die IT/AT-Originale `live` sind).
- **Compile-Falle Go:** `warn_service_health_test.go` importiert `strconv` nur für den Budget-Test;
  beim Löschen des Tests Import mit entfernen. Helfer `newWarnServiceHealthTestScheduler` und
  `writeWarnServiceCallsJournal` bleiben.
- **Doku-Tests verlangen:** ADR-0074-Abschnitt mit „Lizenz" in der Überschrift; dort und in
  `data_sources.md` (Abschnitt „Antrag #2"): „EUMETNET", „1800 s" nahe „unverändert"/„bleibt",
  „Mindest…Verzug", verneinte Aussage nahe „Obergrenze" und nahe „Primärquelle"; Zeile mit
  `api.meteoalarm.org` enthält „zurückgebaut" + „2266", nicht mehr „Code bleibt". README: in jedem
  `edr_snapshot_*`-Abschnitt „eingefroren" + verneinte Aussage zum Aufzeichnungsskript;
  `MeteoAlarmSource.fetch()` komplett raus.
- **Offen für /50 bzw. /60:** AC-5-Trockenlauf des Auswertungsblocks `check-gregor20.sh` (:502–:555)
  mit Statusantwort ohne `meteoalarm_budget` (erwartet keine `ext_issues`) — manueller Nachweis,
  kein Kern-Test (Pfad fehlt in CI). LoC-Override vor /50 setzen (Spec-Hinweis).
- Mutationsprobe (in-memory, `-p mutplug`): Stufen-+1 und Entfernen von Typ 5 im Mapper machen
  Mapper- UND Äquivalenztests rot.
