---
entity_id: compare_preset_zeitplan
type: feature
created: 2026-07-12
updated: 2026-07-12
status: draft
workflow: feat-1232-versand-tab-vergleich
---

# ComparePreset-Zeitplan-Reshape (Backend) — Scheibe 2a/3

- **Issue:** #1232 (Phase 4 — Editor-Konsolidierung, Sub-Issue von Epic #1230) · Scheibe 2a/3
- **Vorgänger:** #1232 Scheibe 1 (`docs/specs/modules/versand_tab_route.md`, live)
- **Nachfolger:** Scheibe 2b (Frontend `context="vergleich"`, eigener Workflow), Scheibe 3 (LayoutTab)

## Approval

- [ ] Approved

## Purpose

Das Zwei-Slot-Zeitplan-Modell des Trip-Briefings (Morgen/Abend, editierbare
Uhrzeiten, editierbare Laufzeit) wird additiv auf `ComparePreset` übertragen,
damit der Orts-Vergleich-Versand in Scheibe 2b denselben `VersandTab`-Organism
nutzen kann wie der Trip-Editor. Reines Backend-Reshape: fünf neue optionale
Felder + Migration + Scheduler-Umstellung von 06:00-Cron auf stündlichen
Slot-Check. Kein Frontend-Verhalten ändert sich in dieser Scheibe.

## Source

- **Files:**
  - `internal/model/compare_preset.go` — Struct-Erweiterung
  - `internal/store/compare_preset.go` — `LoadComparePresets` (Migration)
  - `internal/handler/compare_preset.go` — `UpdateComparePresetHandler`, `CreateComparePresetHandler`, `validateComparePreset`
  - `internal/scheduler/scheduler.go` — Cron-Eintrag `compare_presets_daily`
  - `src/services/scheduler_dispatch_service.py` — `run_compare_presets_daily`, `send_one_compare_preset`
- **Identifier:** `type ComparePreset struct`, `func (s *Store) LoadComparePresets`, `func UpdateComparePresetHandler`, `func run_compare_presets_daily`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` (morning_enabled/morning_time-Muster, Python `src/app/models.py:711-722`) | module | Vorbild für Feldnamen, Zeitformat (`time(7,0)` → JSON `"HH:MM:SS"`) und Slot-Semantik |
| `internal/store/compare_preset.go:35-37` (Weekday-Migration) | module | Vorbild für idempotente Load-Migration mit Pointer-Feldern |
| `internal/handler/compare_preset.go:216-251` (nil-Preserve-Muster `OfficialAlertsEnabled` etc.) | module | Vorbild für Read-Modify-Write beim PUT |
| `api/routers/scheduler.py:31-47` (`trigger_trip_reports`, Stunden-Parameter) | module | Vorbild für stündlichen Aufruf-Parameter `hour` |
| `services/report_config_resolver.py` (`resolve_compare_render_options`) | module | Bleibt unverändert — liest weiterhin Zeitfenster/Horizont/Top-N; Slot-Felder werden NICHT über den Resolver, sondern direkt in `run_compare_presets_daily` ausgewertet |
| Epic #1230 / Issue #1232 Scheibe 1 | workflow | Liefert das Zwei-Slot-Design, das hier datenseitig nachgezogen wird |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/compare_preset.go` | MODIFY | 5 neue Pointer-Felder (`morning_enabled/morning_time/evening_enabled/evening_time/end_date`) + Deprecated-Kommentar an `Schedule`/`Weekday` |
| `internal/store/compare_preset.go` | MODIFY | idempotente Load-Migration: Altdaten ohne Slot-Felder → `morning_enabled=true, morning_time="06:00:00", evening_enabled=false, evening_time="18:00:00"` |
| `internal/handler/compare_preset.go` | MODIFY | nil-Preserve für alle 5 Felder im PUT-Merge; POST-Defaults für neue Presets (`morning_enabled=true, morning_time="07:00:00", evening_enabled=false, evening_time="18:00:00"`); Zeit-/Datums-Validierung |
| `internal/scheduler/scheduler.go` | MODIFY | Cron `0 6 * * *` → `0 * * * *`, Job-ID `compare_presets_daily` bleibt unverändert |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `run_compare_presets_daily(hour=None, ...)`, Slot-Fälligkeitsprüfung, `target_date`-Parameter in `send_one_compare_preset`, Guards (`archived_at`, `end_date`), Slot-Fallback-Helper für Altdaten |
| `api/routers/scheduler.py` | MODIFY | Endpoint `/api/scheduler/compare-presets-daily` reicht `hour`-Query-Parameter durch (Muster `trigger_trip_reports`) |
| `internal/model/compare_preset_test.go` (oder Store-/Handler-Test-Pendant) | CREATE/MODIFY | Roundtrip + Migration + Validierung |
| `tests/tdd/test_compare_preset_slot_dispatch.py` (Name Beispiel, Namensregel beachten) | CREATE | Slot-Fälligkeit, Guards, Fallback, target_date |

### Estimated Changes

- Files: ~7
- LoC: +350/-30 (Rahmen aus Analyse: 350–450 LoC gesamt für Scheibe 2a)

## Implementation Details

**1. Modell (additiv, Pointer-Pattern wie `OfficialAlertsEnabled`):**

```go
MorningEnabled *bool   `json:"morning_enabled,omitempty"`
MorningTime    *string `json:"morning_time,omitempty"` // "HH:MM:SS"
EveningEnabled *bool   `json:"evening_enabled,omitempty"`
EveningTime    *string `json:"evening_time,omitempty"`
EndDate        *string `json:"end_date,omitempty"` // "YYYY-MM-DD", nil = bis auf Weiteres
```

`Schedule`/`PreviousSchedule` bleiben unverändert bestehen — sie tragen ab
sofort ausschließlich die Pause-Semantik (#611: `schedule=="manual"` =
pausiert, `PreviousSchedule` konserviert den Rhythmus über die Pause hinweg).
`Weekday` bleibt als deprecated Altdaten-Träger stehen (kein neuer Schreibpfad
mehr, nur noch Lesbarkeit für Altdaten/Migration).

**2. Load-Migration** (`LoadComparePresets`, analog Weekday-Zeile 35-37):
Für jedes Preset ohne `MorningTime` (nil-Check als Marker "Slot-Felder nie
gesetzt") werden die 5 Felder abhängig vom Alt-Wert von `Schedule` gesetzt:

| Alt-Wert `schedule` | Migrations-Ergebnis |
|---|---|
| `daily`, `weekly`, `manual`, leer/unbekannt | `morning_enabled=true, morning_time="06:00:00", evening_enabled=false, evening_time="18:00:00"` (verhaltensidentisch zum 06:00-Cron) |
| `daily_morning` | wie oben (Nutzer-Intention Morgen; heute wegen Wertemengen-Mismatch NIE versendet — vorbestehender Bug, s. KL-6) |
| `daily_evening` | `morning_enabled=false, morning_time="06:00:00", evening_enabled=true, evening_time="18:00:00"` (Nutzer-Intention Abend; heute NIE versendet — KL-6) |

`Schedule` selbst bleibt unverändert erhalten (Pause-Prüfung: nur exakt
`manual` = pausiert; `daily_morning`/`daily_evening` zählen als aktiv).
Migration ist idempotent: ein bereits migriertes Preset (MorningTime gesetzt)
wird nicht erneut angefasst, auch kein explizites `morning_enabled=false`
wird überschrieben.

**3. PUT-Handler** (`UpdateComparePresetHandler`, Muster Zeile 216-251):
Für jedes der 5 Felder gilt nil-Preserve — fehlt das Feld im Request-Body
(nil nach Decode), wird der Original-Wert übernommen. `MorningTime`/
`EveningTime` werden gegen `^\d{2}:\d{2}(:\d{2})?$` geprüft (400 bei
Mismatch, kein Persist); intern wird bei fehlenden Sekunden `:00` ergänzt.
`EndDate` gegen `^\d{4}-\d{2}-\d{2}$` (ISO-Datum), 400 bei Mismatch.
POST-Handler (`CreateComparePresetHandler`): fehlende Slot-Felder bekommen
die Neu-Preset-Defaults (`07:00`/an, `18:00`/aus, `end_date=nil`) — siehe
Scope-Tabelle.

**4. Go-Cron** (`internal/scheduler/scheduler.go:97`): Eintrag
`{"0 6 * * *", s.comparePresetsDaily, "compare_presets_daily", ...}` →
`{"0 * * * *", ...}`. Job-ID und Handler-Funktion bleiben unverändert
(Observability/Heartbeat-Kontinuität, `s.recordRun("compare_presets_daily", ...)`
bleibt unangetastet).

**5. Python-Dispatch** (`run_compare_presets_daily`, Muster
`trigger_trip_reports` in `api/routers/scheduler.py:31-47`):
Signatur bekommt optionalen `hour`-Parameter (Default: aktuelle Stunde
Europe/Vienna). Pro Preset:
1. `schedule == "manual"` → skip (Pause).
2. `archived_at` gesetzt → skip (heute fehlender Guard, Altlast).
3. `end_date` vorhanden und `< heute` (Europe/Vienna) → skip.
4. Slot-Werte lesen: Preset-Dict hat evtl. keine Slot-Felder (Python liest
   `compare_presets.json` seit Issue #1250 Scheibe 1 über den zentralen Loader
   `load_compare_presets()`/`compare_preset_to_dict()` — `compare_preset_to_dict()`
   liefert weiterhin den unveränderten Roh-Dict, keine Normalisierung; die
   Go-Migration materialisiert die Slot-Felder erst beim nächsten Go-Save).
   Slot-Fallback-Helper liefert bei fehlenden Feldern dieselben Defaults wie
   die Go-Migration (`morning_enabled=true, morning_time="06:00:00",
   evening_enabled=false, evening_time="18:00:00"`).
5. `morning_enabled` und `morning_time.hour == hour` → Versand mit
   `target_date = heute`.
6. `evening_enabled` und `evening_time.hour == hour` → Versand mit
   `target_date = heute + 1 Tag`.
7. Kein Slot fällig → kein Versand (kein Fehler, kein Log-Noise über Debug
   hinaus).

`send_one_compare_preset` bekommt einen `target_date`-Parameter (Default
`date.today()` für Rückwärtskompatibilität mit dem Einzelversand-Pfad
`send_compare_preset`, der `schedule` weiterhin ignoriert) und reicht ihn an
`ComparisonEngine.run(target_date=...)` durch statt hart `date.today()` zu
verwenden.

Dedup: reine Stunden-Gleichheit (`slot_time.hour == hour`), kein Abgleich
gegen `letzter_versand` — identisch zum bestehenden Trip-Muster, Doppel-Versand
in derselben Stunde ist strukturell ausgeschlossen, solange der Cron nur
einmal pro Stunde feuert.

**6. openapi.yaml:** enthält aktuell kein `ComparePreset`-Schema (verifiziert:
kein Treffer für `ComparePreset`/`compare_preset` in `openapi.yaml`) —
Punkt 6 aus dem Auftrag entfällt ersatzlos, keine Änderung nötig.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Go-Store: GIVEN ein Alt-Preset ohne Slot-Felder in `compare_presets.json` WHEN `LoadComparePresets` läuft THEN sind `morning_enabled=true/morning_time="06:00:00"/evening_enabled=false/evening_time="18:00:00"` gesetzt, `end_date=nil`.
- [ ] Go-Store: GIVEN ein bereits migriertes Preset mit `morning_enabled=false` WHEN `LoadComparePresets` erneut läuft THEN bleibt `morning_enabled=false` erhalten (Idempotenz, kein Re-Überschreiben).
- [ ] Go-Handler: GIVEN ein bestehendes Preset mit gesetzten Slot-Feldern WHEN PUT ohne diese 5 Felder im Body geschickt wird THEN bleiben alle 5 Werte nach dem Save unverändert (kein Nullen).
- [ ] Go-Handler: GIVEN ein PUT-Body mit `morning_time="9:5"` (ungültiges Format) WHEN die Validierung läuft THEN antwortet der Handler mit 400 und das Preset wird NICHT persistiert (Datei unverändert).
- [ ] Go-Handler: GIVEN ein POST ohne Slot-Felder WHEN das Preset angelegt wird THEN sind die Neu-Preset-Defaults (`morning_enabled=true/"07:00:00"`, `evening_enabled=false/"18:00:00"`, `end_date=nil`) gesetzt.
- [ ] Python: GIVEN ein Preset mit `morning_enabled=true, morning_time="06:00:00"` WHEN `run_compare_presets_daily(hour=6)` läuft THEN wird mit `target_date=heute` versendet; bei `hour=7` wird NICHT versendet.
- [ ] Python: GIVEN ein Preset mit `evening_enabled=true, evening_time="18:00:00"` WHEN `run_compare_presets_daily(hour=18)` läuft THEN wird mit `target_date=morgen` versendet.
- [ ] Python: GIVEN ein Preset mit `schedule="manual"` und fälliger Slot-Stunde WHEN der Dispatch läuft THEN wird NICHT versendet.
- [ ] Python: GIVEN ein Preset mit `archived_at` gesetzt und fälliger Slot-Stunde WHEN der Dispatch läuft THEN wird NICHT versendet.
- [ ] Python: GIVEN ein Preset mit `end_date` in der Vergangenheit und fälliger Slot-Stunde WHEN der Dispatch läuft THEN wird NICHT versendet; GIVEN `end_date=null` WHEN dieselbe Stunde fällig ist THEN wird versendet.
- [ ] Python: GIVEN ein Alt-Preset-Dict ohne Slot-Felder im rohen JSON WHEN der Dispatch bei `hour=6` läuft THEN greift der Slot-Fallback-Helper und versendet wie ein migriertes Preset (Go-Migration/Python-Fallback-Drift-Schutz).

### Fixtures

- Kern-Schicht: statische JSON-Fixtures für Alt-/Neu-Presets (kein Netz, kein Live-Mail-Versand in den pytest-Tests — `send_one_compare_preset` wird bis zum E-Mail-Versand durchlaufen gelassen oder an der Grenze zu `EmailOutput.send` mit echter Recorded-Fixture geprüft, kein Mock-Theater).

## Acceptance Criteria

**AC-1:** Given ein Compare-Preset mit gesetzten Zeitplan-Feldern (Morgen/Abend-Uhrzeit, Laufzeit) / When ich das Preset über die API speichere ohne diese Felder im Request mitzuschicken / Then bleiben die zuvor gesetzten Werte nach dem Speichern unverändert erhalten — kein Datenverlust durch Teil-Updates.

**AC-2:** Given ich lege ein neues Compare-Preset ohne explizite Zeitplan-Angaben an / When das Preset angelegt wird / Then hat es einen sinnvollen Start-Zeitplan (Morgen-Versand aktiv, Abend-Versand inaktiv, Laufzeit unbegrenzt), der sofort funktionsfähig ist.

**AC-3:** Given ein bestehendes Compare-Preset aus der Zeit vor diesem Reshape (kein neuer Zeitplan gespeichert) / When das System es das erste Mal nach dem Deploy liest / Then verhält sich ein bisher funktionierendes Preset beim Versand exakt wie zuvor (weiterhin ein täglicher Morgen-Versand zur bisherigen Uhrzeit); ein Preset, das wegen des Wertemengen-Mismatch nie versendete (`daily_morning`/`daily_evening`, KL-6), beginnt gemäß der damals gewählten Nutzer-Intention (Morgen- bzw. Abend-Slot) zu versenden.

**AC-4:** Given ein Compare-Preset mit aktivem Morgen-Versand zu einer bestimmten Uhrzeit / When diese Uhrzeit erreicht ist / Then wird der Vergleich für den heutigen Tag verschickt; außerhalb dieser Uhrzeit wird nichts verschickt.

**AC-5:** Given ein Compare-Preset mit aktivem Abend-Versand zu einer bestimmten Uhrzeit / When diese Uhrzeit erreicht ist / Then wird der Vergleich für den FOLGETAG verschickt (Abend-Briefing kündigt morgen an); außerhalb dieser Uhrzeit wird nichts verschickt.

**AC-6:** Given ein Compare-Preset ist pausiert / When eine seiner konfigurierten Versandzeiten erreicht wird / Then wird trotzdem nichts verschickt, bis die Pause aufgehoben wird.

**AC-7:** Given ein Compare-Preset hat ein Laufzeit-Ende in der Vergangenheit / When eine konfigurierte Versandzeit erreicht wird / Then wird nichts mehr verschickt; ein Preset ohne gesetztes Laufzeit-Ende versendet unbegrenzt weiter.

**AC-8:** Given ein Compare-Preset wurde archiviert / When eine seiner konfigurierten Versandzeiten erreicht wird / Then wird nichts verschickt — Archivierung stoppt den Versand vollständig, unabhängig vom Zeitplan.

**AC-9:** Given ich sende eine ungültige Uhrzeit oder ein ungültiges Datum beim Speichern eines Compare-Presets / When die Eingabe validiert wird / Then wird die Änderung abgelehnt (Fehlermeldung) und der bisherige Zeitplan bleibt unangetastet gespeichert.

**AC-10:** Given der alte Orts-Vergleich-Editor (vor Scheibe 2b) ist noch im Einsatz / When er ein Preset speichert wie bisher (ohne die neuen Zeitplan-Felder zu kennen) / Then funktioniert das weiterhin unverändert — kein Pflichtfeld wurde neu eingeführt, kein bestehender Speichervorgang bricht.

**AC-11:** Given zwei verschiedene Nutzer haben je ein Compare-Preset mit unterschiedlichem Zeitplan / When der Versand-Check zur jeweils konfigurierten Uhrzeit läuft / Then wird jedes Preset nur für seinen eigenen Nutzer und nur an dessen eigene Empfänger verschickt — keine Vermischung zwischen den Nutzern.

## Known Limitations

- **KL-1 · Wöchentlicher Rhythmus entfällt:** `weekly`-Presets versenden nach diesem Reshape TÄGLICH statt am gewählten Wochentag. Der PO hat am 2026-07-11 festgestellt, dass der Wochenrhythmus im Compare-Versand ein erfundenes Feature war (nicht Teil des Designs) — dies ist eine bewusste, nutzersichtbare Verhaltensänderung. Prod-Bestand mit `schedule="weekly"` wird vor dem Deploy gesichtet.
- **KL-2 · Minuten-Granularität ignoriert:** Der Fälligkeits-Check vergleicht nur die volle Stunde (wie beim Trip-Versand), Minutenangaben in der gespeicherten Uhrzeit werden beim Dispatch nicht ausgewertet.
- **KL-3 · Mail-Footer zeigt Alt-Label:** Der Abo-Footer (#1110) zeigt weiterhin das alte `schedule`-Label ("daily"/"weekly"). Kosmetisch, wird in Scheibe 2b mit dem Frontend nachgezogen.
- **KL-4 · Altes Frontend zeigt weiterhin alte Versandzeit-Buttons ohne Wirkung:** Bis Scheibe 2b bietet das Frontend die neuen Felder nicht an; die alten Versandzeit-Buttons (`schedule='daily_morning'|'daily_evening'`) wirken nur noch auf das reine Pause-Feld `schedule` und haben keinen Effekt mehr auf die tatsächliche Slot-Uhrzeit. Das ist akzeptiert bis 2b, weil die Migration das bisherige Versandverhalten konserviert (AC-3) und die Buttons keinen Datenverlust verursachen.
- **KL-5 · Gleiche Stunde für Morgen und Abend möglich:** Wenn `morning_time.hour == evening_time.hour`, gehen zwei Mails in derselben Stunde raus (wie bei Trips) — das wird nicht verboten oder speziell behandelt.
- **KL-6 · Vorbestehender Bug wird durch Migration behoben (nutzersichtbar):** Presets, deren Versandzeit über die heutigen UI-Buttons gewählt wurde (`schedule='daily_morning'|'daily_evening'`), wurden vom Python-Dispatch NIE versendet (der kennt nur exakt `daily`/`weekly`). Die Migration übersetzt diese Werte in funktionierende Morgen- bzw. Abend-Slots — betroffene Bestandspresets beginnen nach dem Deploy erstmals tatsächlich zu versenden. Das ist eine gewollte Bug-Behebung, keine Regression; Prod-Bestand wird vor Deploy zusammen mit KL-1 gesichtet.
- **KL-7 · `end_date` kann per API nicht auf „unbegrenzt" zurückgestellt werden (Adversary-Fund F003, 2026-07-12):** Die Pointer-Merge-Semantik des PUT-Handlers kann „Feld fehlt" nicht von „Feld explizit null" unterscheiden — ein einmal gesetztes Laufzeit-Ende bleibt daher bestehen, bis ein neues Datum gesetzt wird. Identisches, projektweit bestehendes Muster (vgl. Sammel-Issue #1199, PUT-null-Semantik). Auflösung (z. B. Löschen-Sentinel) kommt mit dem Frontend in Scheibe 2b, das den Bedienfall „bis auf Weiteres" anbietet.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Abend-Versand am Monatsletzten | `target_date` = 1. des Folgemonats (reine Datumsarithmetik, keine Sonderbehandlung nötig) |
| `end_date` == heute | Versand findet heute noch statt; erst ab morgen greift der Guard |
| Preset ohne Empfänger und ohne `mail_to`-Fallback | bestehender `ValueError`-Skip-Pfad bleibt unverändert (kein neues Verhalten) |
| Alt-Preset-JSON ohne Slot-Felder, direkt vom Python-Dispatch gelesen (vor dem nächsten Go-Save) | Slot-Fallback-Helper liefert dieselben Defaults wie die Go-Migration — kein Drift zwischen Go und Python |
| `morning_time` und `evening_time` in derselben Stunde | beide Mails werden verschickt (KL-5) |
| Preset mit `schedule="weekly"` und gesetztem `weekday` (Altdaten) | `weekday` wird beim Dispatch nicht mehr ausgewertet (KL-1); Feld bleibt nur als deprecated Altdaten-Träger im Modell |

## Out of Scope

- Frontend (`context="vergleich"`-Zweig von `VersandTab`, Step5Versand-Ablösung) — Scheibe 2b, eigener Workflow.
- LayoutTab-Extraktion (Zeitfenster/Horizont/Top-N/Stundenverlauf als `CompareReportContentSection`) — Scheibe 3.
- Echtes `briefings[]`-Array / `BriefingSubscription`-Modell — Epic #29 Phase 3, nicht dieser Reshape (bewusst additiv statt strukturell, siehe Implementation Details).
- Trip-seitige Lücke bei `morning_enabled`/`evening_enabled`-Feature-Parität — nicht Gegenstand dieser Spec.
- Mail-Footer-Label-Update (#1110-Anzeige) — folgt mit dem Frontend in 2b.
- Migration bestehender `hour_from`/`hour_to`/`forecast_hours`/Top-N/Stundenverlauf-Felder — bleiben unverändert bestehen, werden von dieser Scheibe nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** additive Pointer-Feld-Erweiterung folgt einem bereits etablierten, mehrfach genutzten Muster (Weekday/OfficialAlertsEnabled/RadarAlertEnabled/HourlyEnabled) im selben Modul — keine neue Architekturentscheidung, sondern konsistente Fortführung.

## Test-Nachweis

- Kern: Go-Tests (Store-Migration, Handler nil-Preserve/Validierung, deterministisch, kein Netz) + Python-pytest (Slot-Fälligkeit, Guards, `target_date`, Fallback-Helper, mit statischen Fixtures) — 100% grün als Commit-Gate.
- RED-Phase: Python-Tests unter `tests/tdd/` (Namensregel: Verhalten, nicht Issue-Nummer) + Go-Test im mark-red-Mechanismus (Go/FE-Testdateien sind in RED per `edit_gate` gesperrt, Freischaltung über den etablierten Workflow-Mechanismus).
- Staging-E2E (`/60-validate`): echter Versand eines Test-Presets an `gregor-test@henemm.com` über den neuen stündlichen Dispatch-Pfad, geprüft mit `email_spec_validator.py` (Mail-Typ `compare`, Marker-Header `X-GZ-Mail-Type: compare`).

## Changelog

- 2026-07-13 (Doku-Nachzug, Issue #1250 Scheibe 1): Implementation Details Punkt 5.4
  präzisiert — Python liest `compare_presets.json` nicht mehr direkt roh, sondern über
  den zentralen Loader `load_compare_presets()`/`compare_preset_to_dict()`
  (`src/app/loader.py`). Verhalten/Fallback-Defaults unverändert, reine
  Mechanismus-Korrektur, kein neuer AC.
- 2026-07-12: Initial spec created
- 2026-07-12 (vor Freigabe): Migrations-Tabelle um `daily_morning`/`daily_evening` erweitert + KL-6 (vorbestehender Nie-Versand-Bug wird behoben); AC-3 entsprechend präzisiert. PO-„go" erfolgte auf diesem Stand.
- 2026-07-12 (nach Freigabe, Adversary-Runde): KL-7 ergänzt — `end_date` per API nicht auf „unbegrenzt" rückstellbar (F003, bestehendes Pointer-Merge-Muster, Auflösung in 2b). Reine Dokumentation eines Ist-Verhaltens, kein AC geändert.
