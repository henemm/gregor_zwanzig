# Context: feature-1986-paritaets-bestandsaufnahme

## Request Summary
Bestandsaufnahme (keine Sanierung): Alle Paritäts-Tests des Repos auflisten, je bewachtes Paar mit `Datei:Zeile` beidseitig, je Paar ein Verdikt (zusammenführbar / begründet getrennt / unklar), bekannte Doppelungen außerhalb der Tests einsammeln. Ergebnis als priorisierte Liste im Body von Issue #1986, nicht als Datei im Repo.

## Related Files
| Datei | Relevanz |
|---|---|
| `tests/tdd/test_*parit*.py`, `tests/unit/*parit*` | Menge der Paritäts-Tests (Python): ca. 35 in tdd, weitere in unit. Im Issue "zwölf" genannt, tatsächlich mehr (87 Treffer im Dateinamen-Suchlauf inkl. Artefakte und Specs) |
| `internal/scheduler/scheduler_unify_test.go` | Go-Paritätswächter Trip↔Compare |
| `frontend/e2e/*paritaet*.spec.ts`, `frontend/src/lib/components/**/__tests__/*paritaet*.test.ts` | Frontend-Paritätstests |
| Issue-Kommentar 2026-09-09 (Aufmaß #1374) | Fertige Liste ungedeckter Paare Frontend/Go/Python, mit Folge-Issues #2277 bis #2288 |

## Existing Patterns
- Issue zählt nur 3 echte Trip↔Compare-Wächter (`test_compare_hourly_trip_parity`, `test_compare_preview_hourly_parity`, `scheduler_unify_test.go`); die übrigen ca. 21 prüfen Kanal-/Format-/Sprach-Parität innerhalb eines Bereichs.
- Pendant-Sperre (#1481) und Vokabular-Ratsche (#1406 B) existieren; Klon-Detektor ausdrücklich zurückgestellt.
- Folge-Issues zu einzelnen Paaren existieren teils schon (#2277, #2278, #2279, #2280, #2284, #2285, #2288) und sind nicht doppelt anzulegen.

## Dependencies
- Upstream: nur Lesen von Tests und Code. Schreiben: Issue-Body #1986, Kopfzeilen in Tests bei "begründet getrennt", neue Folge-Issues bei "zusammenführbar".
- Downstream: Klon-Detektor-Entscheidung (#1197), Epic #1230.

## Existing Specs
- `docs/specs/modules/compare_metric_parity.md`, `briefing_parity_night_thunder.md`, `feat_2347_*_paritaets_e2e.md` (nur Lesehilfe)

## Risks & Considerations
- AC-1 verlangt Vollständigkeit gegen die tatsächliche Testmenge (Zähler im Issue); die Zahl "zwölf" im Titel ist überholt, der Zähler muss die echte Menge belegen.
- AC-5: kein Produktivcode ändern, nur Test-Kopfzeilen (Kommentare).
- Größe: ca. 35 bis 40 Dateien lesen. Analyse auf Teilmengen verteilen (Python tdd, Python unit und Go, Frontend).
- Issue-Body wird überschrieben: Read-Modify-Write, bestehenden Text und ACs erhalten.

## Analysis

### Type
Feature (Bestandsaufnahme, kein Produktivcode, AC-5). Ergebnis geht in den Body von Issue #1986 (Read-Modify-Write, Text und ACs bleiben).

### Tatsächliche Testmenge (AC-1-Zähler)
Nicht "zwölf", sondern **~65 Paritäts-Testdateien**: Python 35, Go 13, Frontend 17. Viele bewachen dasselbe Paar in mehreren Sprachen (Naismith, Empfänger-Regeln, Entitäts-ID, Ampel); nach Paar zusammengefasst ca. 45 Paare. Vollständigkeitsbeleg: `git ls-files | grep -iE 'parit|parity'` (118 Treffer inkl. Doku/Fixtures) plus Go-Funde per `grep -rliE 'parit' internal --include=*_test.go`. Beleg-Kommando in den Issue-Body schreiben.

### Verdikt-Ergebnis (Vorschlag der Lese-Agenten; Kopf-only-Dateien in Phase 3 gegen Code stichprobenprüfen)
**Zusammenführbar (Folge-Tickets, AC-4):**
1. `OnsetEvent`-Bau doppelt: `src/services/notification_service.py:1932` (Trip, `send_radar_alert`) ↔ `src/output/renderers/alert/project.py:645` (Vergleich). Tests: `test_onset_ende_kanalparitaet`, `test_onset_menge_kanalparitaet`, `test_onset_reichweite_guete_kanalparitaet`.
2. Vorschau ↔ Versand doppelt verdrahtet: `src/services/preview_service.py:198, 224-319` ↔ `src/services/trip_report_scheduler.py:1671, 1784-1814`. Tests: `test_preview_parity_without_outlook`, `test_preview_render_options_parity`, `test_thunder_night_addendum_parity`. Dazu (unklar/Z): `compare_alert_preview_service.py:38` ↔ `notification_service.py:1188/1266/1674`; `validator_render_service.py:421` ↔ `compare_html.py:1703`.
3. Klartext-Labels Vergleichs-Mail: `comparison.py:78,112,154` (`_PLAIN_ROWS`) ↔ `email/compare_html.py:1703`.
4. Zweiter Ortsformatierer: `alert/official_alerts.py:887, 2464` ↔ `alert/segments.py:94`.
5. Trip-Metriken ↔ Vergleichs-Metriken getrennt gepflegt (`test_compare_metric_parity`; `compare_metric_ids.py:195`).
6. Segmentbestimmung (#1982, geschlossen, Rest offen): Inline-Kopien `api/routers/debug.py:85`, `trip_report_scheduler.py:2273`, `trip_segments.py:491/499`; Baustein `select_active_segment` (`trip_segments.py:437`) nur intern genutzt.
7. Frontend: `TAB_DEFS` `TripNewEditor.svelte:116` ↔ `CompareNewEditor.svelte:221`; Standardwerte-Ergänzer `tripNewLogic.ts:309` ↔ Reiter-Effekte `VersandTab.svelte`; Ampel-Logik TS ↔ Python (`ampelModell.ts:152,97,338` ↔ `src/app/ampel.py:245,176`); `COMPARE_METRIC_KEYS` `corridorEditorState.ts:512` ↔ `compare_metric_catalog.py:366`; `formatHHMM` TS/Py/Go (geringer Gewinn); Kanalfunktionen `heroKanaele`/`reportChannels`/`presetChannels` (kein Test bewacht).
8. Go: Fehlertext `kind_required` (`briefing_send.go:40` ↔ `api/routers/briefings_send.py:126`, mittelfristig); `alert_metric_channels` Trip-Feld ↔ `compare_preset.go:292-300`.
9. Bekannter Drift: `ValidEntityIDRe` (`internal/store/pathsafe.go:64`) strenger als `VALID_ENTITY_ID_RE` (`src/app/loader.py:1334`), #2961.

**Begründet getrennt (Begründung als Kopfzeile in den Test, AC-3):** Python↔Go (Empfänger-Regelwerk, Naismith, Trip-Schema-Drift, User-/Entitäts-ID-Muster, Budget-Konstanten): zwei Prozesse/Sprachen, Fixture ist der Zwang. DE↔EN-Kataloge (6 Tests). Kanal↔Kanal (Regen-Ausdehnung, Vorlauf, Amtlicher Zusatz, Hiking-Window, Etappennummer). Generierte Kopien (`alert_metric_mapping`, `alert_preset_table`, 2794 Auswahl). Bereits zusammengeführt, Test nur Regressionswächter (Anlege-Rahmen, Hub-Kopf ×2, Wetter-Metriken-Versand-Panel, Home-Hero, Subscription-Kachel, Alert-Kanal-Auflösung #2279, Compare-Hourly, Trip-Outlook-Golden, Scheduler-Unify, Metric-Catalog-Loader, E2E-Compare-Wächter).
**Unklar:** `test_briefing_parity_night_thunder` (html.py:1168/1287 ↔ plain.py:309/212), `test_channel_origin_guard_parity`, `hub-anlegen-paritaet-flaechen.spec.ts`, `standardwerte_payload_paritaet_compare.test.ts`, `briefing_route_get_lock_etag_test.go`. Möglichst technisch selbst entscheiden.
**Name täuscht (keine Doppelung):** `btn-feature-parity.spec.ts`, `test_702_alerts_mobile_parity.py`, `test_alert_preview_compare_paritaet_drossel_frei.py`, `test_stage_weather_parity.py`.

### Startpunkte aus Issue
#1982 siehe 6. #1911 behoben (`compareMetricCatalogLoader.ts`; ungeprüfte Reste `types.ts`, `corridorEditorState.ts`, `compareMetricSelection.ts`). #1480 Python behoben mit Wächter `test_thunder_scale_local_copy_guard.py`, Frontend ungeschützt (Wächter scannt nur `src/`, `api/`). #1848 behoben (`compare_outlook_metric_ids.py:197`), Restfeld `outlook_metrics` (`models.py:866`).

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| GitHub-Issue #1986 Body | MODIFY | priorisierte Liste, Zähler, Verdikte (Read-Modify-Write) |
| ca. 25 Paritäts-Testdateien | MODIFY (nur Kommentar) | Begründung bei "begründet getrennt" |
| neue GitHub-Issues | CREATE | je zusammenführbarem Paar mit `priority:*`; bestehende #2277-#2288 verlinken, nicht doppeln |

### Scope Assessment
- Files: ~25 Testdateien (Kommentar), 0 Produktiv
- Estimated LoC: +~150 Kommentarzeilen
- Risk Level: LOW (nur Kommentare; Kopfzeilen-Edits können Test-/Pendant-Gates auslösen, Doku-Ausnahme prüfen)

### Technical Approach
Spec: (a) Liste im Issue-Body nach Priorität (Alarm-/Versandpfade high, Frontend-Kopien medium, `formatHHMM` low), (b) Zähler-Beleg per Befehl, (c) Kopfzeilen nur Kommentar mit einheitlichem Marker, Prüftest, dass jede "begründet getrennt"-Datei den Marker trägt, (d) Folge-Issues anlegen. Vor Eintrag Stichprobe der Agenten-Verdikte gegen Code.

### Dependencies
Klon-Detektor (#1197), Epic #1230, Folge-Issues #2277-#2280, #2284, #2285, #2288.

### Open Questions
- [ ] Prioritätsraster der Folge-Tickets (Vorschlag oben).
- [ ] Marker-Format der Kopfzeile (Spec).
- [ ] Fünf Unklar-Fälle technisch entscheiden oder an PO.
