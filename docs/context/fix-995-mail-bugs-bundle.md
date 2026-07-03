# Context: fix-995-mail-bugs-bundle (Issue #995)

## Request Summary
Drei gemeldete E-Mail-/Briefing-Fehler aus einem Screenshot (Trip-Detail-Stundentabelle):
(1) Segment-Startzeitpunkt ignoriert eine geänderte Etappen-Startzeit, (2) der farbige
Zellhintergrund der Gust-Spalte füllt die Tabellenzelle in manchen Mail-Clients nicht
vollflächig aus, (3) Briefings werden trotz aktiviertem Trip-Detail-Pause-Button weiterhin
automatisch verschickt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_segments.py:77-102` | `convert_trip_to_segments()` — Prioritätskette für Segment-Startzeit. `wp1.time_window` (Z.86) hat Vorrang vor `stage.start_time` (Z.90-91). Gilt für ALLE Wegpunkte (Z.109 dieselbe Kette), nicht nur `i==0`. |
| `src/services/gpx_processing.py:125-146` | `segments_to_trip()` — setzt beim GPX-Import ein festes `TimeWindow` für JEDEN Wegpunkt, das später nie invalidiert wird. Kein Herkunfts-Flag. |
| `src/services/preview_service.py:73-110` | Zweiter Aufrufer von `convert_trip_to_segments()` — speist die Trip-Detail-Stundentabelle (Screenshot-Quelle laut Analyse). |
| `src/services/trip_command_processor.py:194-195`, `src/services/trip_alert.py:672-681` | Weitere Aufrufer derselben SSoT — müssen bei TDD-RED mit abgedeckt werden. |
| `src/output/renderers/email/html.py:586-590` | Tönungs-Kompensation `margin:-6px -6px;padding:6px 6px` innerhalb eines inneren `<span>` — fragiles Konstrukt. |
| `src/output/renderers/email/html.py:592` / `:521` | `<td style="{_td_grid}" data-label="{label}">` — `_td_grid` (Z.521) enthält NUR Border-Styles, kein inline-Padding/Background. Zelle verlässt sich für Padding komplett auf den globalen `<style>`-Block. |
| `src/output/renderers/email/html.py:1106-1117` | `_otd()` — bereits vorhandenes, bewährtes Muster: Background + Padding **direkt inline auf `<td>`**, kein Span/Negativ-Margin-Trick. Wird an anderer Stelle in derselben Datei für dasselbe visuelle Problem verwendet. |
| `tests/tdd/test_fix_911_visual_table.py:123-146` | Bestehender visueller Test (Playwright/Chromium) — prüft `backgroundColor`, aber KEINE Geometrie (Bounding-Box). Kann Outlook/Apple-Mail-spezifische Rendering-Eigenheiten nicht reproduzieren (Chromium respektiert `<style>` korrekt). |
| `src/services/trip_report_scheduler.py:262-303` | `_get_active_trips()` — prüft `rc.enabled` und `rc.paused_until`, **nicht** `trip.paused_at`. Einziger automatischer Dispatch-Pfad (verifiziert). |
| `src/services/trip_report_scheduler.py:380-402` | `send_test_report()` — manueller "Test senden"-Button, ruft `_send_trip_report()` DIREKT auf, umgeht `_get_active_trips()` komplett. Bleibt vom Fix unberührt (by design). |
| `src/app/trip.py:184-199` | `Trip`-Dataclass — hat `region`/`archived_at` (Issue #805, Go-Roundtrip-Felder), aber **kein `paused_at`**. |
| `src/app/loader.py:395-428` | `load_trip()` — baut `Trip` aus JSON; `archived_at=data.get("archived_at")` vorhanden (Z.427), `paused_at` fehlt komplett → Feld wird beim Python-Laden stillschweigend verworfen (verifiziert: keine Zeile dafür). |
| `src/app/loader.py:962-972`, `:1044-1045` | `load_all_trips()` filtert `archived_at` (Z.968) — **nicht** der richtige Ort für den `paused_at`-Filter (siehe Risiken). Schreib-Pfad für Roundtrip-Felder bei Z.1044-1045. |
| `internal/model/trip.go:104` | Go-Modell: `PausedAt *time.Time \`json:"paused_at,omitempty"\`` — Quelle der Wahrheit für den Trip-Detail-Pause-Button. |
| `internal/model/trip.go:69` (Kommentar) | Explizite Design-Annahme bei Epic #135: "Python-Loader liest Trips als Dict und ignoriert unbekannte Felder — keine Python-seitige Änderung nötig" — **diese Annahme war falsch für den Scheduler-Anwendungsfall.** |
| `internal/store/store.go:85,134-195` | Go schreibt in dieselbe JSON-Datei (`data/users/<user_id>/trips/<id>.json`), die Python liest — EIN gemeinsames File, kein Sync-Mechanismus nötig, nur eine fehlende Lese-Zuordnung auf Python-Seite. |
| `docs/specs/modules/epic_135_step2_trip_detail_actions.md:359` | **Explizit dokumentiert:** "Scheduler ignoriert pausierten Status... bewusst out of scope für Issue #153 — wird als separates Folge-Issue angelegt." Punkt 3 schließt also eine von Anfang an bekannte, bewusst zurückgestellte Lücke — keine Regression. |
| `frontend/src/lib/utils/tripStatus.ts:1-14` | `deriveTripStatus()` — UI-Status "Pausiert" basiert auf `trip.paused_at != null`. |
| `frontend/src/lib/components/compare/__tests__/issue_627_send_action.test.ts` | Betrifft Compare-Preset-Status (`subscriptionHelpers.ts`, `compare_presets.json`) — anderes Datenmodell, anderer Codepfad. **Keine Kollision** mit Punkt 3 (verifiziert). |

## Existing Patterns

- **Go↔Python-Feld-Roundtrip (#805-Muster):** Feld in `Trip`-Dataclass ergänzen (`src/app/trip.py`),
  beim Laden durchreichen (`loader.py` `data.get(...)`), beim Speichern zurückschreiben
  (`loader.py:1044-1045`). Für Punkt 3 exakt zu wiederholen für `paused_at`.
- **`_otd()`-Inline-Style-Pattern (html.py:1106-1117):** bereits etablierte, robustere Alternative
  zum Span/Negativ-Margin-Trick — für Punkt 2 zu übernehmen.
- **Zeitprioritätskette:** Bereits DREIMAL angefasst (Bugfix `trips_time_window_lost.md`,
  Issue #783 Commit `1eac69d8`, Issue #802) — `time_window` wurde dabei jedes Mal bewusst OBEN
  belassen (keine reine Vernachlässigung). Grund vermutlich: kein Herkunfts-Flag vorhanden, um
  "GPX-Import-Artefakt" von "bewusst gesetzt" zu unterscheiden — anders als `arrival_override`,
  das bereits ein `origin`-Feld trägt (Issue #303, `manual`/`algorithmic`).

## Dependencies

- **Punkt 1 (Segmentierung):** SSoT `convert_trip_to_segments()` hat 4 Aufrufer: Briefing-
  Scheduler, `preview_service.py` (Trip-Detail-Stundentabelle), `trip_command_processor.py`,
  `trip_alert.py`. Ein Fix betrifft alle vier gleichzeitig — TDD-RED muss alle vier abdecken.
- **Punkt 2 (Zellhintergrund):** Isoliert auf `html.py`, keine Fremdabhängigkeiten.
- **Punkt 3 (Pause):** Downstream vom Go-Handler `PATCH /trips/{id}/state`. Automatischer
  Versand-Pfad ausschließlich `api/routers/scheduler.py` → `send_reports_for_hour()` →
  `_get_active_trips()`. Go-Cron-Scheduler iteriert korrekt pro User (verifiziert,
  `multi_user_test.go`) — Mandanten-Trennung ist NICHT die Fehlerursache.

## Existing Specs

- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` (§ Zeile 359) — hält die
  Scheduler-Pause-Lücke bereits als bekannt und bewusst zurückgestellt fest.
- `docs/specs/modules/issue_783_776_778_briefing_fixes.md` — dokumentiert die aktuelle (unvollständige)
  Prioritätskette `time_window > arrival_override > stage.start_time > arrival_calculated`.
- `docs/specs/modules/issue_802_fahrrad_segment_zeit.md:95-109` — bestätigt `time_window`/
  `arrival_override` bleiben bei `ComputeStageArrivals` bewusst unberührt (idempotent-Designentscheidung).
- Kein Spec-Dokument für die HTML-Zell-Tönung selbst — nur in Commit-Historie (#911, #888/#896/#902).

## Analysis

### Type
Bug (Bündel aus 3 unabhängigen, im selben Issue gemeldeten Fehlern).

### Technischer Ansatz je Punkt

**Punkt 1 — Startzeitpunkt:**
Kein reiner Prioritäts-Swap (Challenger-Verdict: NEEDS REVIEW — dritter Patch an derselben
Kette in 5 Monaten, `time_window` bisher immer bewusst oben belassen). Empfehlung: `TimeWindow`
bzw. `Waypoint` um ein Herkunfts-Flag ergänzen (analog `arrival_override.origin`), das GPX-Import
als nicht-autoritativ markiert. Priorität dann: bewusst gesetztes `time_window` weiterhin oben,
importiertes `time_window` unterhalb von `stage.start_time`. Muss für ALLE Wegpunkte einer Etappe
gelten (nicht nur `i==0`) und an allen 4 SSoT-Aufrufern verifiziert werden.

**Punkt 2 — Zellhintergrund:**
Kein `cellpadding="0"`-Fix (Challenger-Verdict: NEEDS REVIEW — Richtung der Abweichung ungeklärt,
zwei frühere Teil-Fixes an derselben Stelle deuten auf architektonisches Problem). Empfehlung:
Span/Negativ-Margin-Trick durch das bereits bewährte `_otd()`-Muster ersetzen — Background +
Padding direkt inline auf `<td>`, kein CSS-Abhängigkeit auf den globalen `<style>`-Block mehr.
Zusätzlich TDD-RED um einen Geometrie-Test erweitern (`span`/`td`-`getBoundingClientRect()`-
Vergleich), da der bestehende Test nur `backgroundColor` prüft. Finale Bestätigung zwingend über
den echten Mail-Client-Versand (Projekt-Pflicht `briefing_mail_validator.py` gegen Staging-Testpostfach) —
Playwright/Chromium kann Outlook/Apple-Mail-Eigenheiten nicht reproduzieren.

**Punkt 3 — Pausierte Trips:**
Challenger-Verdict: CONFIRMED. `paused_at` nach #805-Muster ins Python-Modell aufnehmen
(`trip.py`, `loader.py` Lesen+Schreiben) und als zusätzliche Sperre **gezielt in
`_get_active_trips()`** einbauen — NICHT in `load_all_trips()` (sonst würden Alerts über
`trip_alert.py` unbeabsichtigt mit unterdrückt, da diese `load_all_trips()` direkt aufrufen).
AC muss explizit machen: manueller Test-Versand (`send_test_report()`) und Alert-Dispatch bleiben
unberührt. Formulierung als "schließt bekannte, bewusst zurückgestellte Lücke (Issue #153)".

### Scope Assessment
- Dateien: ~8-10 (3x Produktionscode je Punkt + korrespondierende Tests)
- Geschätzte LoC: Punkt 1 ~25-40 (Origin-Flag + Kettenlogik, 4 Call-Sites), Punkt 2 ~15-25
  (Refactor auf `_otd()`-Muster), Punkt 3 ~10-15 (Feld-Roundtrip + Filter) → Produktionscode
  gesamt ~50-80 LoC. Tests zusätzlich (zählen mit, siehe LoC-Limit-Regel) — realistisch
  100-150 LoC für Visual-/Unit-/Integrationstests über alle 3 Punkte. **Risiko: LoC-Limit 250
  könnte knapp werden** — ggf. `loc_limit_override` nötig (nur mit User-Freigabe).
- Risk Level: MEDIUM (Punkt 1 hat breiten Blast-Radius über 4 SSoT-Aufrufer; Punkt 3 berührt
  Versand-Gate-Logik; Punkt 2 ist isoliert und risikoarm)

### Dependencies
Keine Reihenfolge-Zwänge zwischen den drei Punkten — unabhängig implementierbar, aber im selben
Workflow gebündelt (ein Issue, ein PO-Freigabe-Zyklus).

### Open Questions
- [ ] Punkt 2: tatsächlicher Mail-Client aus dem #995-Screenshot nicht verifizierbar — Fix wird
      nach bestem Wissen (robusteres Inline-Pattern) umgesetzt, endgültige Bestätigung nur via
      echtem Testversand möglich.
