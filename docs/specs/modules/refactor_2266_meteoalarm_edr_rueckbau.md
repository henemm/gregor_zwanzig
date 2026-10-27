---
entity_id: refactor_2266_meteoalarm_edr_rueckbau
type: refactor
created: 2026-10-27
updated: 2026-10-27
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, rueckbau, egress, budget, epic-2258]
workflow: refactor-2266-meteoalarm-edr-rueckbau
---

<!-- Issue #2266 · Epic #2258 -->

# Rückbau der kontingentierten MeteoAlarm-EDR-Klasse + Lizenz-Prüfpunkt Feed-TTL

## Approval

- [ ] Approved

## Purpose

Die EDR-Klasse `MeteoAlarmSource` (Abruf gegen `api.meteoalarm.org`) ist seit #1445 S3 nicht
mehr registriert; amtliche Warnungen für AT, IT und DE kommen ausschließlich aus dem
kontingentfreien Feed (`MeteoAlarmFeedSource`). Diese Spec entfernt die Klasse samt Index-,
Budget-, Drossel- und Geometrie-Apparat, ohne den geteilten CAP-Mapper anzutasten, der den Feed-Weg
trägt. Zusätzlich wird der offene Lizenz-Prüfpunkt (Feed-TTL 30 min gegen die
EUMETNET-Weitergabe-Auflage) mit einem ehrlich dokumentierten Ergebnis geschlossen.

## Source

- **File:** `src/services/official_alerts/meteoalarm.py`
- **Identifier:** `class MeteoAlarmSource` (wird gelöscht); bleibender Rest: CAP-Mapper
  (`_group_and_map_info_entries`, `_extract_alerts_from_cap`, `_collect_cap_info_entries` und deren
  Hilfsfunktionen)

> **Schicht-Hinweis:** Python-Core (`src/services/`, `src/app/`) und Go-API (`internal/egress/`,
> `internal/scheduler/`). Kein Frontend-Anteil. Außerhalb des Repos: Konsument
> `/home/hem/henemm-infra/scripts/check-gregor20.sh` (nur Prüfung, optional Kommentarpflege).
>
> **Querschnitts-Prüfpunkte:** Trip/Ortsvergleich-Teilung: nicht betroffen (reiner Backend-Rückbau,
> beide Flächen nutzen weiter dieselbe Feed-Quelle). Mandantentrennung: keine Nutzerdaten bewegt.
> Kanäle: Briefing- und Alarm-Inhalt AT/IT/DE bleibt für E-Mail, Telegram, SMS und Premium-SMS
> unverändert (Verhaltensneutralität, AC-2).

## Kontext (Ziel)

Zielzustand nach dem Rückbau:

- Kein Code mehr, der `api.meteoalarm.org` anspricht oder dafür Kontingent bucht.
- `meteoalarm.py` enthält nur noch den CAP-Mapper, der vom Feed-Weg genutzt wird
  (`meteoalarm_feed.py:36` importiert `_group_and_map_info_entries`).
- Python- und Go-Egress-Inventar kennen `api.meteoalarm.org` nicht mehr; `feeds.meteoalarm.org`
  bleibt.
- Schnitt-Tiefe **C** (Entscheidung der Analyse, nicht umwerfen): EDR-Klasse + `meteoalarm_budget.py`
  + Go-Budget-Spiegel + `parallel_fetch`-Slot + `RateLimitRetryPolicy` samt 429-Retry-Zweig in
  `warn_egress.py`. Begründung: nach Entfernen der EDR-Klasse hat die Retry-Policy keinen
  Produktivnutzer mehr; ein Folge-Ticket nur für diesen Rest widerspricht der Regel „Epics
  themenweise abschließen".

## Scope

### In Scope

1. EDR-Apparat in `meteoalarm.py` löschen (ca. :43–:503 und :677–:1116), Modul-Docstring neu.
2. `meteoalarm_budget.py` löschen (einziger Nutzer war die EDR-Klasse).
3. `RateLimitRetryPolicy`, `parse_ratelimit_reset` und den 429-Retry-Zweig in `warn_egress.py`
   entfernen; **das Journal-Feld `self_throttled` bleibt** (siehe Risiken).
4. `parallel_fetch._DEFAULT_SLOTS["meteoalarm"]` entfernen.
5. `api.meteoalarm.org` aus `src/app/egress_guard.py` und `internal/egress/inventory.go` synchron
   entfernen.
6. Go-Budget-Spiegel `meteoalarm_budget` aus `internal/scheduler/warn_service_health.go` entfernen.
7. Tests: Mapper-Tests in den Kern umziehen, EDR-/Budget-/Retry-Tests löschen, Bezüge anpassen.
8. Fixtures: EDR-only-Fixtures löschen; Aufzeichnungsskript-Verweis in der README streichen.
9. Doku und Lizenz-Prüfergebnis.

### Out of Scope

- Änderung der Feed-TTL (`WARN_SUCCESS_TTL = 1800`, `warn_egress.py:41`) oder des Auffrischrasters.
- Umbenennen von `meteoalarm.py` oder des Mappers; Änderung am Mapping-Verhalten.
- Änderungen am Feed-Weg (`meteoalarm_feed.py`), an `GeoSphereWarnSource`, `dpc.py` (nur Docstring).
- Entfernen von `self_throttled` aus Journal oder `enrichment_health` (anderer Kontext).
- Neue Warnquellen oder neue Kanäle.

## Affected Files

Alle Pfade und Symbole wurden per Grep/Glob gegen den Stand des Worktrees geprüft. Zeilenangaben
sind Richtwerte aus diesem Stand.

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm.py` | MODIFY | EDR-Apparat löschen (u. a. `METEOALARM_BASE_URL`:43, `_rate_limit_retry_policy`:81, `_MeteoAlarmBudgetExhausted`:133, `_meteoalarm_budget_gate`:148, Alias `_point_in_geometry`:1011, `MeteoAlarmSource.fetch`). CAP-Mapper bleibt. Modul-Docstring :1–15 neu (verweist auf alten Spec-Pfad, nennt `api.meteoalarm.org`) |
| `src/services/official_alerts/meteoalarm_budget.py` | DELETE | `MeteoAlarmBudgetGate`, kein weiterer Nutzer |
| `src/services/official_alerts/warn_egress.py` | MODIFY | `parse_ratelimit_reset` (:230), `RateLimitRetryPolicy` (:248), Parameter `rate_limit_retry` in `cached_fetch` (:408) und Helfer (:522), 429-Retry-Zweig entfernen; Zweig `self_throttled` (:544) und Journal-Feld (:330/:360) bleiben |
| `src/services/official_alerts/__init__.py` | MODIFY | Kommentar :36–41 („bleibt für Äquivalenznachweis AC-5 erreichbar") entfernen/neu fassen |
| `src/services/parallel_fetch.py` | MODIFY | Slot `"meteoalarm": 1` in `_DEFAULT_SLOTS` (:30) entfernen |
| `src/app/egress_guard.py` | MODIFY | Eintrag `api.meteoalarm.org` (:43) entfernen; `feeds.meteoalarm.org` (:46) bleibt |
| `internal/egress/inventory.go` | MODIFY | Eintrag `api.meteoalarm.org` (:34) entfernen; `feeds.meteoalarm.org` (:37) bleibt |
| `internal/scheduler/warn_service_health.go` | MODIFY | Budget-Spiegel entfernen (Funktion `meteoalarmBudgetSnapshot` :195, Aufrufe :266 und :306, Kommentare :170–:235); Dienst-Journalauswertung bleibt |
| `internal/scheduler/warn_service_health_test.go` | MODIFY | Budget-Test (AC-6-Block :105–:146) entfernen bzw. auf „Block fehlt" umstellen |
| `internal/scheduler/forecast_budget_health.go` | MODIFY | nur Kommentar :183 („analog meteoalarm_budget") |
| `src/services/file_lock.py` | MODIFY | nur Docstring :5 (Verweis auf `meteoalarm_budget.py`) |
| `src/services/official_alerts/dpc.py` | MODIFY | nur Docstring-Erwähnungen (:4, :54) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | nur veralteter Kommentar um :117; Schlüssel `"meteoalarm"` BLEIBT (Feed erzeugt `source="meteoalarm"`) |
| `tests/tdd/test_meteoalarm_cap_mapper.py` | CREATE | Mapper-Tests ohne `live`-Marker (Kern) |
| `tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py` | CREATE | ungemarkerter Kern-Nachweis der Feed-Äquivalenz IT/AT gegen die eingefrorenen Snapshots |
| `tests/tdd/test_meteoalarm_source.py` | DELETE | nach Umzug der Mapper-Tests; Rest ist EDR-only (modulweit `live`) |
| `tests/tdd/test_meteoalarm_index_coverage.py` | DELETE | EDR-Index, `live` |
| `tests/tdd/test_meteoalarm_budget_buchung_im_abrufpfad.py` | DELETE | Budget-Buchung im EDR-Abrufpfad |
| `tests/tdd/test_meteoalarm_budget_reserve_atomic.py` | DELETE | Budget-Modul entfällt |
| `tests/tdd/test_budget_reserve_lock_timeout_is_loud.py` | DELETE | Budget-Modul entfällt |
| `tests/unit/test_meteoalarm_budget_gate.py` | DELETE | Budget-Modul entfällt |
| `tests/unit/test_warn_egress_capture_id_after_retry.py` | DELETE | testet 429-Retry-Pfad |
| `tests/unit/test_warn_egress_capture_id_stale_after_failed_capture.py` | DELETE | geprüft 2026-10-27: einziger Test (`test_ac5_…`) baut auf `RateLimitRetryPolicy` + 429-Antwort auf (:52–:82) — Zusicherung entfällt mit dem Retry-Pfad. `test_warn_egress_capture_id_passthrough.py` bleibt unberührt, sofern kein Retry-Bezug |
| `tests/tdd/test_warn_service_egress.py` | MODIFY | Retry-Policy-Tests (ca. :376–:712) entfernen; übrige Egress-Tests bleiben |
| `tests/tdd/test_meteoalarm_feed_italien.py` | MODIFY | Einzeltest um :1230–:1275 (nutzt EDR-Klasse) umstellen oder entfernen; Rest unberührt |
| `tests/tdd/test_isolation_warn_services.py` | MODIFY | Zugriffe auf Inventar-Eintrag `api.meteoalarm.org` (ca. :56, :133) anpassen (sonst KeyError) |
| `tests/tdd/test_warn_service_health_journal.py` | MODIFY | Import von `_MeteoAlarmBudgetExhausted` (ca. :134) entfernen, Fall auf Journal-Verhalten ohne Budget umstellen |
| `tests/test_avalanche_report_region_mapper.py` | MODIFY | Nutzung des Alias `meteoalarm._point_in_geometry` (ca. :149–:179) auf `point_in_geometry` aus dem Ursprungsmodul umstellen |
| `tests/tdd/test_file_lock_timeout.py` | MODIFY | Budget-Bezüge (ca. :52, :188–:210) entfernen |
| `tests/test_output_timezone_guard.py` | MODIFY | Ratsche-Einträge zu `meteoalarm.py`/`meteoalarm_budget.py` (ca. :671–:672) ziehen; Stale-Check (ca. :769) muss grün bleiben |
| `tests/fixtures/meteoalarm/` | DELETE (teilweise) | EDR-only: `index_*`, `geometry_sample`, `at_publication_profile`, `cap_villach_heat*`; Mapper-Fixtures bleiben (`cap_green_level1`, `cap_broken`, `cap_*_ro`, `cap_avalanche_plus_heat`, `feed_avalanche_type9`). Vor dem Löschen je Datei per Grep prüfen, dass kein bleibender Test sie referenziert |
| `tests/fixtures/meteoalarm_feed/README.md` | MODIFY | Verweise auf `MeteoAlarmSource.fetch()` (:30, :156) als Herkunft: Aufzeichnungsskript existierte nie im Repo (Ad-hoc-Lauf) und wird dokumentiert gestrichen; Snapshots sind eingefroren |
| `tests/fixtures/meteoalarm_feed/*.json` | KEEP | `edr_snapshot_{it,at}.json`, `feed_*_equivalence.json`, `zamg_snapshot_at.json`, Samples bleiben unverändert |
| `docs/specs/data_sources.md` | MODIFY | Antrag #2 (~:285–:302): `api.meteoalarm.org` als zurückgebaut vermerken; Lizenz-Prüfergebnis |
| `docs/adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md` | MODIFY | Vermerk: Rückbau erledigt (#2266) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | Budget-Erwähnungen als historisch kennzeichnen |
| `docs/adr/0074-auffrischraster-meteoalarm-feed-deutschland.md` | MODIFY | Abschnitt Lizenz-Prüfergebnis zur Feed-TTL |
| `docs/features/architecture.md` | MODIFY | Eintrag um :795 |
| `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md`, `warn_service_consumption.md`, `egress_guard.md` | MODIFY | Hinweis „zurückgebaut durch #2266" im Kopf/Changelog, soweit sie EDR/Budget beschreiben |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | PRÜFEN (optional Kommentarpflege) | liest den Block tolerant (:553 `or {}`), schließt den Schlüssel in :513 aus; keine Pflichtänderung |

## Estimated Scope

- Files: ca. 30 (ca. 15 Tests, ca. 8 Doku)
- LoC: ca. -1550 / +40 Produktivcode, zuzüglich Test-Umzug
- Effort: medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.meteoalarm._group_and_map_info_entries` | function | bleibt; einzige Verbindung des Feed-Wegs (`meteoalarm_feed.py:36`) zu `meteoalarm.py` |
| `services.official_alerts.meteoalarm_feed.MeteoAlarmFeedSource` | class | Produktiver Ersatz (IT/AT/DE), unverändert |
| `services.official_alerts.warn_egress.cached_fetch` | function | Abrufweg des Feeds; verliert nur den Parameter `rate_limit_retry` |
| `tests/test_egress_inventory_drift.py` | test | Drift-Wächter Python↔Go, muss nach dem synchronen Entfernen grün sein |
| `tests/fixtures/meteoalarm_feed/edr_snapshot_{it,at}.json` | fixture | Eingefrorene Referenz für die Äquivalenz (AC-2) |
| `internal/scheduler/warn_service_health.go` → `check-gregor20.sh` | consumer | Status-Konsument in henemm-infra, liest tolerant |

## Implementierungsreihenfolge

1. **Mapper-Tests in den Kern** (`test_meteoalarm_cap_mapper.py`) und Kern-Äquivalenztest
   (`test_meteoalarm_feed_aequivalenz_snapshots.py`) anlegen; beide laufen grün gegen den
   **unveränderten** Stand. Erst dann weiter.
2. `meteoalarm.py` auf den CAP-Mapper kürzen; Alias `_point_in_geometry` und Test
   `test_avalanche_report_region_mapper.py` mitziehen.
3. `meteoalarm_budget.py`, Go-Budget-Spiegel, `parallel_fetch`-Slot entfernen; Python- und
   Go-Egress-Inventar **im selben Commit** bereinigen.
4. `RateLimitRetryPolicy`, `parse_ratelimit_reset`, 429-Retry-Zweig aus `warn_egress.py`.
5. Tests, Ratschen und Fixtures nachziehen (siehe Affected Files); EDR-/Budget-/Retry-Tests löschen.
6. Doku und Lizenz-Prüfergebnis; `check-gregor20.sh`-Verträglichkeit prüfen.

## Implementation Details

- **CAP-Mapper bleibt vollständig.** Beizubehalten sind `_TYPE_HAZARD_MAP`, `_DISCARDED_TYPES`,
  `_local_tag`, `_child_text`, `_find_parameter`, `_find_area_desc`, `_leading_int`, `_parse_iso`,
  `_pick_preferred_entry`, `_collect_cap_info_entries`, `_group_and_map_info_entries`,
  `_extract_alerts_from_cap`. `_extract_alerts_from_cap`/`_collect_cap_info_entries` haben nach dem
  Rückbau keinen Produktivaufrufer, bleiben aber als dokumentierte CAP-XML-Schnittstelle, weil Tests
  und die Ratsche `test_resolution_loss_guard.py` (ca. :743, :878) sie nutzen. Das wird im neuen
  Modul-Docstring genannt.
- **`self_throttled` bleibt im Warn-Journal** (`warn_egress.py`, Schreibfunktion mit Feld
  `self_throttled`; Go-Auswertung `warn_service_health.go:26/:278` liest es). Es ist danach
  konstant `False`, wird aber aus Gründen der Schema-Stabilität nicht entfernt.
- **Go-Status:** `warn_service_health` liefert weiterhin die Dienste (`dpc`, `meteoalarm`,
  `meteoalarm_feed`, …) aus dem Journal; nur der Sonderschlüssel `meteoalarm_budget` und die
  Env-Variable `GZ_METEOALARM_DAILY_BUDGET` entfallen.
- **Lizenz-Prüfpunkt (Ergebnis, keine Code-Änderung):**
  - Im Repo liegt **keine Primärquelle** für die EUMETNET-Weitergabe-Auflage („5–10 min Verzug")
    vor; auch die Recherche lieferte nur „Verzug gegenüber meteoalarm.eu möglich", keine
    Minutenangabe. Das wird in der Doku so benannt und nicht als gesichert dargestellt.
  - Die Auflage verlangt, soweit bekannt, einen **Mindest**-Verzug. Der 30-min-Cache
    (`WARN_SUCCESS_TTL = 1800`) liefert mehr Verzug, nicht weniger; eine Obergrenze ist nicht belegt.
  - Die 30 min sind eine bewusste, in ADR-0074 festgehaltene Entscheidung. **Keine TTL-Änderung**
    (sonst wäre ein neues ADR ohne Beleg nötig). Wiedervorlage nur, wenn eine Primärquelle
    auftaucht.

## Test Plan

### Automated Tests (TDD RED)

Hinweis: Dies ist ein Rückbau. „RED" heißt hier: die beiden neuen Kern-Testdateien existieren vor
dem Löschen, sind sofort grün gegen den Altstand und müssen es nach jedem Rückbauschritt bleiben
(Absicherung statt Fehlschlag-Beweis). Die Prüfung der Löschung selbst erfolgt über
Verhaltenstests (AC-1, AC-4, AC-5), nicht über Dateiinhalt.

**Neu / umgezogen (alle OHNE `live`-Marker, ohne Netz, echte aufgezeichnete Fixtures, kein Mock-Theater):**

- [ ] `tests/tdd/test_meteoalarm_cap_mapper.py`: GIVEN eine CAP-Fixture (grüne Stufe 1, defekte
  Eingabe, RO-Varianten, Lawine plus Hitze, Typ 9) WHEN der Mapper sie verarbeitet THEN entstehen
  dieselben Warnungen wie im bisherigen `test_meteoalarm_source.py`. Umzuziehen sind die Mapper-Tests
  um :206, :238, :313, :395, :540, :697, :786, :2346, :2380; die gemischten Tests um :2251 und :2306
  werden auf den Mapper-Anteil entmischt.
- [ ] `tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py`: GIVEN die Feed-Aufzeichnungen
  `feed_italy_equivalence.json`/`feed_austria_equivalence.json` (+ `zamg_snapshot_at.json`) und die
  eingefrorenen Snapshots `edr_snapshot_{it,at}.json` WHEN `MeteoAlarmFeedSource("IT"/"AT")` je
  Trip-Punkt über die vorhandene lokale Fake-Server-Injektion (wie in
  `test_meteoalarm_feed_italien.py`/`_oesterreich.py`, kein neuer Mock-Mechanismus) abruft THEN ist
  die Feed-Menge je Punkt gleich dem Snapshot im Sinne der bisherigen Äquivalenzprüfung (Obermenge,
  `pruefe_obermenge`-Logik der AT-Datei). Die Logik wird aus den bestehenden `live`-Tests
  (IT ca. :752, AT ca. :981) übernommen, die Datei trägt bewusst keinen `live`-Marker.
- [ ] DE-Kontrolle: GIVEN `feed_germany_sample.json` WHEN `MeteoAlarmFeedSource` abruft THEN gleiches
  Ergebnis wie vor dem Rückbau — über die bestehende `tests/tdd/test_meteoalarm_feed_deutschland.py`
  (geprüft 2026-10-27: ungemarkert, läuft über den Cache-Weg ohne Netz im Kern; bleibt unverändert grün).

**Gelöscht (Zusicherung entfällt mit dem Code):**
`test_meteoalarm_source.py` (nach Umzug), `test_meteoalarm_index_coverage.py`,
`test_meteoalarm_budget_buchung_im_abrufpfad.py`, `test_meteoalarm_budget_reserve_atomic.py`,
`test_budget_reserve_lock_timeout_is_loud.py`, `tests/unit/test_meteoalarm_budget_gate.py`,
`test_warn_egress_capture_id_after_retry.py`, `test_warn_egress_capture_id_stale_after_failed_capture.py`.

**Angepasst:** siehe Affected Files (`test_isolation_warn_services`, `test_warn_service_health_journal`,
`test_avalanche_report_region_mapper`, `test_file_lock_timeout`, `test_warn_service_egress`,
`test_meteoalarm_feed_italien`, `test_output_timezone_guard`, Go `warn_service_health_test.go`).

**Verhaltenstests für die Rückbau-Zusicherungen:**

- [ ] Go: GIVEN ein Journal mit Warn-Abrufen und eine vorhandene Datei `meteoalarm_budget.json`
  im Diagnoseordner WHEN `warn_service_health` berechnet wird THEN enthält das Ergebnis den Schlüssel
  `meteoalarm_budget` nicht, die Dienste `dpc`, `meteoalarm` usw. mit `last_success_at`,
  `last_attempt_at`, `self_throttled` unverändert.
- [ ] Python: GIVEN ein Aufruf der Journal-Schreibfunktion ohne Retry-Policy WHEN ein Abruf
  fehlschlägt THEN steht im Journal eine Zeile mit allen bisherigen Feldern inklusive
  `self_throttled` (False).
- [ ] Drift: `tests/test_egress_inventory_drift.py` grün; GIVEN Python- und Go-Inventar WHEN
  verglichen THEN identische Host-Mengen ohne `api.meteoalarm.org`, mit `feeds.meteoalarm.org`.

### AC-zu-Test-Mapping

| AC | Nachweis |
|----|----------|
| AC-1 | Kern-Testlauf der betroffenen Dateien (`uv run pytest <benannte Dateien>`) grün; Import `from services.official_alerts.meteoalarm import MeteoAlarmSource` scheitert mit `ImportError` (Verhaltenstest per `pytest.raises`, nicht per Dateiinhalt); `RateLimitRetryPolicy` aus `warn_egress` nicht importierbar; `meteoalarm_budget` nicht importierbar |
| AC-2 | `test_meteoalarm_feed_aequivalenz_snapshots.py` |
| AC-3 | `test_meteoalarm_cap_mapper.py`, Marker-Prüfung per `--collect-only` ohne `-m live` |
| AC-4 | `tests/test_egress_inventory_drift.py`, `test_isolation_warn_services.py`, Go-Test im Paket `internal/egress` |
| AC-5 | Go-Test `warn_service_health_test.go` + Trockenlauf des Auswertungsblocks aus `check-gregor20.sh` mit einer Statusantwort ohne `meteoalarm_budget` |
| AC-6 | Python-Journal-Test + Go-Test (Felder inkl. `self_throttled`) |
| AC-7 | `doc-compliance-test` nur für die README (kein `src/`-Quelltext) bzw. manuelle Review |
| AC-8 | `doc-compliance-test` für Doku-Vermerk in ADR-0074 / `data_sources.md` |

## Expected Behavior

- **Input:** unverändert (Trip-/Ortsvergleich-Punkte in AT, IT, DE; CAP-XML-Eingaben für Tests).
- **Output:** identische amtliche Warnungen wie vor dem Rückbau; `warn_service_health` ohne
  `meteoalarm_budget`.
- **Side effects:** keine Abrufe und keine Schreibvorgänge mehr für `meteoalarm_budget.json`; eine
  bereits vorhandene Altdatei auf Produktion/Staging bleibt unbeachtet liegen (kein Löschzwang,
  keine Bestandsdaten-Migration nötig).

## Acceptance Criteria

- **AC-1:** Given der Rückbau ist abgeschlossen / When die betroffenen Kern-Testdateien laufen und
  `MeteoAlarmSource`, `meteoalarm_budget` und `RateLimitRetryPolicy` importiert werden sollen /
  Then sind alle Kern-Tests grün und die drei Importe schlagen mit ImportError fehl, weil die
  EDR-Klasse, das Budget-Modul und die Retry-Policy nicht mehr existieren.
  - Test: Verhaltenstest mit `pytest.raises(ImportError)` plus grüner Kernlauf der benannten Dateien.

- **AC-2:** Given Trip- oder Vergleichspunkte in Österreich, Italien und Deutschland mit den
  aufgezeichneten Feed-Daten / When der Feed-Weg die amtlichen Warnungen je Punkt liefert / Then sind
  die Warnungen für jeden Punkt gleich den eingefrorenen Snapshots `edr_snapshot_it.json` und
  `edr_snapshot_at.json` (Feed-Menge deckt die Snapshot-Menge vollständig ab), und zwar in einem
  ungemarkerten Kern-Test ohne Netz.
  - Test: `tests/tdd/test_meteoalarm_feed_aequivalenz_snapshots.py` läuft ohne `live`-Marker und
    schlägt an, wenn eine Snapshot-Warnung im Feed-Ergebnis fehlt.

- **AC-3:** Given die CAP-Mapper-Tests lagen bisher in einer modulweit als `live` markierten Datei /
  When der normale Kern-Testlauf ohne Live-Marker gesammelt und ausgeführt wird / Then laufen die
  Mapper-Tests in `tests/tdd/test_meteoalarm_cap_mapper.py` mit und prüfen Stufen, Gefahrenarten,
  verworfene Typen, Lawinen-Typ 9 und defekte Eingaben, sodass ein versehentliches Löschen des
  Mappers einen Kern-Test rot macht.
  - Test: `--collect-only` zeigt die Tests ohne `-m live`; Mutation (Mapper-Zweig verfälscht) macht
    mindestens einen dieser Tests rot.

- **AC-4:** Given das Python-Egress-Inventar (`src/app/egress_guard.py`) und das Go-Inventar
  (`internal/egress/inventory.go`) / When der Drift-Wächter und die Isolations-Tests laufen / Then
  ist `api.meteoalarm.org` in beiden Inventaren weder erlaubt noch referenziert,
  `feeds.meteoalarm.org` bleibt in beiden als gesperrter Host für Test/Staging erhalten, und der
  Drift-Wächter ist grün.
  - Test: `tests/test_egress_inventory_drift.py`, `tests/tdd/test_isolation_warn_services.py` und das
    Go-Paket `internal/egress`.

- **AC-5:** Given die Go-API wertet das Warn-Journal aus / When der Scheduler-Status
  `warn_service_health` abgerufen wird / Then enthält er keinen Block `meteoalarm_budget` mehr, die
  übrigen Dienste mit ihren Feldern sind unverändert, und die Auswertung von `check-gregor20.sh`
  (liest `meteoalarm_budget` tolerant über `or {}` und überspringt den Schlüssel) meldet auf einer
  solchen Antwort keinen Fehler.
  - Test: Go-Test `warn_service_health_test.go`; Trockenlauf des Python-Auswertungsblocks aus
    `check-gregor20.sh` (:502–:555) mit einer Statusantwort ohne den Block, erwartet: keine
    `ext_issues`.

- **AC-6:** Given ein Warn-Abruf wird journalisiert / When er fehlschlägt oder gelingt / Then enthält
  jede Journal-Zeile weiterhin das Feld `self_throttled` (konstant False), und die Go-Auswertung
  liefert es unverändert im Dienststatus.
  - Test: Python-Journal-Test auf die geschriebene Zeile plus Go-Test auf das Statusfeld; kein
    Dateiinhalt-Check am Quelltext.

- **AC-7:** Given das Aufzeichnungsskript der Snapshots nie im Repo lag / When die README der
  Feed-Fixtures gelesen wird / Then steht dort dokumentiert, dass die Snapshots eingefroren sind und
  kein Aufzeichnungsskript existiert, und alle Fixtures in `tests/fixtures/meteoalarm_feed/` sind
  weiterhin vorhanden und von den Tests nutzbar.
  - Test: `# doc-compliance-test` nur auf die README; Nutzbarkeit der Fixtures wird durch AC-2
    bewiesen.

- **AC-8:** Given die Lizenz-Frage zur Feed-TTL von 30 Minuten gegen die EUMETNET-Weitergabe-Auflage /
  When ADR-0074 und `docs/specs/data_sources.md` gelesen werden / Then ist dort vermerkt, dass die
  TTL unverändert bei 1800 Sekunden bleibt, dass ein Cache von 30 Minuten einen Mindest-Verzug
  erfüllt und keine Obergrenze belegt ist, und ausdrücklich, dass im Repo keine Primärquelle für die
  Auflage vorliegt.
  - Test: `# doc-compliance-test` auf die beiden Doku-Dateien; zusätzlich Verhaltenstest, dass
    `WARN_SUCCESS_TTL` weiterhin 1800 Sekunden beträgt (Wert, nicht Quelltext).

## Risiken

- **CAP-Mapper darf nicht mitgelöscht werden.** Er trägt die Warnungen AT/IT/DE; ein Verlust würde
  amtliche Warnungen still ausfallen lassen (Fehlerart Epic #2505). Gegenmaßnahmen: Kern-Tests
  (AC-2, AC-3) vor dem ersten Löschen grün; Mutations-Gegenprobe des Adversary auf den Mapper-Zweig
  `_group_and_map_info_entries` (String-Ersetzung mit externer Sicherungskopie, kein
  `git checkout/stash/reset`).
- Ratschen-Stale-Checks (`test_output_timezone_guard.py`) und Python↔Go-Inventar-Drift brechen bei
  unvollständigem Rückbau: beide Inventare im selben Commit, Ratschen-Einträge in derselben Scheibe.
- `rate_limit_retry` ist ein Parameter von `cached_fetch`: vor dem Entfernen per Grep belegen, dass
  kein anderer Warndienst ihn übergibt (laut Analyse keiner).
- Fixture-Löschung: je Datei prüfen, dass kein bleibender Test sie lädt, sonst Kern-Test rot.
- Staging-/Prod-Altdatei `meteoalarm_budget.json` bleibt liegen: unschädlich, da nichts mehr liest.
- Externer Konsument `check-gregor20.sh`: tolerant (`or {}`), Verträglichkeit wird in AC-5 geprüft;
  Kommentarpflege dort ist optional und in `henemm-infra` zu committen.

## Doku-Änderungen

`docs/specs/data_sources.md` (Antrag #2), ADR-0039 (Rückbau erledigt), ADR-0044 (Budget historisch),
ADR-0074 (Lizenz-Prüfergebnis), `docs/features/architecture.md` (~:795), Hinweise in den
Vorläufer-Specs (`fix_1397_meteoalarm_coverage_budget.md`, `warn_service_consumption.md`,
`egress_guard.md`), README der Feed-Fixtures. Neuer ADR nicht nötig (Rückbau einer bereits
abgelösten Quelle, keine neue Entscheidung; TTL unverändert).

## Hinweis LoC-Override

Das Löschvolumen liegt bei ca. 1550 Produktivzeilen und überschreitet das Limit von 250 pro
Workflow. Vor `/50-implement` ist `workflow.py status` zu prüfen und
`workflow.py set-field loc_limit_override 500` zu setzen, bei Bedarf höher (z. B. 1700). Tests und
Doku zählen nicht. Nur Hinweis, keine Vorgabe zur Umgehung anderer Gates.

## Known Limitations

- Der Äquivalenznachweis stützt sich auf eingefrorene Snapshots eines einzelnen Zeitfensters
  (Aufzeichnung 2026-08-01); er beweist Verhaltensgleichheit für diese Trip-Punkte, nicht für
  zukünftige Warnlagen.
- Die Lizenz-Auflage ist mangels Primärquelle nicht abschließend verifiziert (siehe AC-8).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (bestehend: ADR-0039, ADR-0044, ADR-0074 werden ergänzt)
- **Rationale:** Rückbau einer seit #1445 S3 nicht mehr registrierten Quelle ist die in ADR-0039
  (:42) vorgesehene Folgearbeit; die TTL-Entscheidung aus ADR-0074 bleibt unverändert.

## Changelog

- 2026-10-27: Initial spec created (Issue #2266, Epic #2258)
