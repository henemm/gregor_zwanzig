# Context: feat-2587-compare-briefing-nachholen

## Request Summary
Issue #2587 (aus #2280, Adversary F-ADV6): Scheitert der automatische Zeitplan-Versand eines Ortsvergleichs auf allen Kanälen, wird er heute nur im Monitoring verbucht, aber nie nachgeholt — das Briefing ist für den Nutzer verloren. Ziel: Gleichstand mit dem Trip — Nachholen am selben Zieltag und Führung als offen in `briefing_health`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py` | Vorbild: `_write_pending_marker` :1060-1096, `_mark_briefing_undelivered` :1098-1121, `_clear_dispatch_error_marker` :1123, `_remove_pending_marker` :1144, `_bump_pending_marker_attempts` :1155, Nachhol-Schleife `_process_pending_markers` :913-1058 (Catch-up-Prefix „Nachgeliefert — …“ :997-1013), `_load_pending_entries` :446, `_write_pending_data` :464 (atomar) |
| `src/services/compare_slot_scheduler.py` | `presets_due_for_hour` :142-218 — exakte Stunde, Morgen (Offset 0) / Abend (Offset 1, Zieltag = morgen), Ortszeit je Preset, Guards silenced/end_date/Wochentag; kein Nachhol-Fenster (Docstring :152 → #1777) |
| `src/services/dispatch_orchestrator.py` | `TripDispatchStrategy.pre_pass` :71-80 (ruft Nachhol-Schleife); `CompareDispatchStrategy` :126-226, `pre_pass` :180 nur Auto-Pause, `dispatch_one` :195 |
| `src/services/scheduler_dispatch_service.py` | `_dispatch_due_preset` :149-190 schluckt Outcome (bool); `send_one_compare_preset` :460 — Fehler-Erkennung: except um `send_compare_report` :751-755, `channels_unreachable` :765-773 (#2280) |
| `src/services/alert_briefing_anchor.py` | `record_briefing_dispatch_failure` :110-139 (jsonl-Diagnose); `briefing_target_day_is_current` :142-186 — reine Funktion, Docstring sieht Wiederverwendung durch Compare-Nachholen ausdrücklich vor |
| `internal/store/pending_briefings.go` | `PendingBriefingEntry` :12-20 (an `trip_id` gebunden, kein `reason`), `LoadPendingBriefingsForUser` :29 — nur von BriefingHealth genutzt |
| `internal/scheduler/briefing_health.go` | `BriefingHealth()` :67-216 (globbt `users/*/pending_briefings.json` → `open_pending_briefings`, `oldest_pending_age_hours`, `degraded_segments_total`), `analyzeBriefingDispatchErrors` :414-470 |
| `internal/scheduler/scheduler.go` | Cron `0 * * * *` `briefingDispatch` :341/:747 → trip-reports :782, dann compare-presets-daily :1011; Exposition `briefing_health` in `/api/scheduler/status` :1491 |
| `api/routers/scheduler.py` | `/api/scheduler/trip-reports` :54, `/api/scheduler/compare-presets-daily` :289 |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | Konsument: :221-240 Alarm bei `open_pending_briefings > 0` und Alter > Schwelle; :701-731 Dispatch-Error-Streak (anderes Repo → ggf. MQ an `infra`) |

## Existing Patterns
- **Trip-Marker:** `pending_briefings.json` je Nutzer, `{"entries":[{trip_id, report_type, date, slot_hour, failed_segment_ids, attempts, created_at, reason?}]}`; `reason="dispatch_error"` kennzeichnet Versandfehler (#1662). Read-Modify-Write, ein Eintrag pro `trip_id`, atomares Schreiben, fail-soft Lesen.
- **Nachholen:** im `pre_pass` vor den regulären Slots; Marker erst entfernen, dann senden (kein Doppelversand bei Absturz); verfällt, wenn Zieltag vorbei (`briefing_target_day_is_current` mit Ortszeit-„heute“, ADR-0044/0051); ist der Trip in dieser Stunde ohnehin fällig, zählt der reguläre Versand als Nachholung.
- **Löschen bei Erfolg:** nur bei regulärem (`not on_demand`) erfolgreichem Versand, nur `dispatch_error`-Marker.
- **Handversand (`on_demand`)** schreibt nie Marker.
- **Code-Teilung Trip/Vergleich (ADR-0097, Pendant-Sperre):** Nachhol-Mechanik möglichst gemeinsam statt Compare-Kopie.

## Dependencies
- Upstream: `send_compare_report`, `outcome_from_result`, `briefing_target_day_is_current`, Preset-Loader `src/app/loader.py:310` (`data/users/<uid>/briefings/*.json`, `kind=="vergleich"`), Ortszeit-Auflösung `_preset_ortszeit`.
- Downstream: Go `BriefingHealth` → `/api/scheduler/status` → `check-gregor20.sh` (henemm-infra); Versand-Historie (#2281); Auto-Pause im Compare-`pre_pass`.

## Existing Specs
- `docs/specs/modules/fix_1662_versandfehler_nachliefern.md` — Trip-Nachholen; :73-76 klammert Compare ausdrücklich aus (jetzt Gegenstand)
- `docs/specs/modules/dispatch_orchestrator.md:95` — dokumentierte, PO-freigegebene Aufteilung: Trip-`pre_pass` = Nachholen, Compare-`pre_pass` = Auto-Pause (muss angepasst, nicht still umgangen werden)
- `docs/specs/modules/compare_preset_zeitplan.md`, `feat_2280_handversand_endpoint.md`, `feat_2281_vergleich_versand_historie.md`, `compare_dispatch_observability_telegram_guard.md`, `fix_1629_briefing_anker_versandfehler.md`, `fix_1725_faelligkeit_und_idempotenz.md`, `fix_1405_s4b_erfolg_heisst_wirkung.md`
- Archiv: `docs/specs/_archive/modules/issue_1114_briefing_health.md`
- ADRs: 0018 (Ausfall nicht verstecken), 0035 (ein Tagesfenster Trip+Compare), 0044/0051 (Ortszeit, drei Zeitbegriffe), 0097 (Code-Teilung)

## Existing Tests
- Trip: `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py` (:893-1290 Marker/`dispatch_error`), `test_erfolg_heisst_wirkung_s4b.py`, `test_versandpfade_folgen_ortszone.py:406`, `test_briefing_slot_faelligkeit_und_alarmsperre.py`
- Compare/#2280: `tests/tdd/test_compare_preset_send.py` (:484), `test_compare_briefing_anchor_survives_dispatch_failure.py`, `test_compare_dispatch_failed_tally.py`
- Go: `internal/scheduler/briefing_health_test.go`, `briefing_dispatch_health_test.go`, `briefing_health_corrupt_by_kind_test.go`
- Fixture-Helfer: `tests/helpers/briefing_imminent_fixtures.py:659-673`

## Risks & Considerations
- **Datenverlust durch Trip-Schleife:** `_process_pending_markers` löscht Einträge, deren `trip_id` keinen Trip findet (:962). Compare-Marker in derselben Datei ohne Diskriminator (`kind`) würden sofort gelöscht → Diskriminator + Filter in der Trip-Schleife, oder separate Datei (dann muss BriefingHealth sie mit globben).
- **Schlüssel:** ein Preset kann Morgen- und Abend-Slot haben (verschiedene Zieltage) — Schlüssel nur `preset_id` würde einen Marker überschreiben; Schlüssel mindestens `(preset_id, slot/target_date)` oder bewusste Entscheidung.
- **Ort des Hooks:** `_dispatch_due_preset` verwirft das Outcome → Marker-Schreiben gehört in `send_one_compare_preset` neben die zwei `record_briefing_dispatch_failure`-Stellen; Löschen nach `outcome == "sent"` und `not on_demand`.
- **Nicht erfasste Fehlschläge:** `no_channels` (:552), `no_weather` (:620-628) und durchschlagende Wetter-Exceptions werden heute nicht verbucht — Scope-Entscheidung, ob „alle Kanäle gescheitert“ diese einschließt (Issue nennt nur Kanal-Fehlschlag).
- **Go-Schema:** `PendingBriefingEntry` kennt kein `kind`/`preset_id` → Zählung ggf. trotzdem korrekt (zählt Einträge), aber Abwärtskompatibilität mit Bestandsdateien (Read-Modify-Write mit Merge, CLAUDE.md „Daten-Schema-Reworks“, Hook `data_schema_backup.py`).
- **Zieltag/Ortszeit:** Abend-Slot hat Zieltag = morgen → Nachholen bis Ende des Zieltags in Preset-Ortszeit; Verfall über `briefing_target_day_is_current`.
- **Doppelversand vermeiden:** Nachholen nicht in derselben Stunde, in der der reguläre Slot ohnehin feuert; Marker vor dem Senden entfernen (Trip-Muster).
- **Auto-Pause:** pausierte/stummgeschaltete/abgelaufene Presets dürfen nicht nachgeholt werden.
- **Nutzer-Isolation:** Marker strikt unter `data/users/<uid>/`, Test mit zwei Nutzern (CLAUDE.md-Pflicht).
- **Spec-Konflikt:** `dispatch_orchestrator.md:95` und `fix_1662…:73-76` beschreiben den Ist-Stand ohne Compare-Nachholen → in der neuen Spec ausdrücklich ablösen.
- **Infra-Konsument:** `check-gregor20.sh` zählt `open_pending_briefings`; Compare-Marker sollen dort mitzählen (Issue-Ziel) — wenn neues Feld nötig, MQ an `infra`.

## Analysis

### Type
Feature (Paritäts-Lücke Trip ↔ Ortsvergleich, Folge aus #2280 F-ADV6)

### Kernbefunde (gegen den Code verifiziert)
1. **Blocker gemeinsame Datei:** `_process_pending_markers` (`trip_report_scheduler.py:957-959`) ruft für Einträge ohne passenden Trip `_remove_pending_marker(trip_id)`; bei einem Compare-Eintrag ist `trip_id` None → `_remove_pending_marker(None)` löscht **alle** Compare-Marker. Der Cron ruft `trip-reports` **vor** `compare-presets-daily` (`scheduler.go:782/:1011`) → Compare sähe seine Marker nie. Pflicht: Diskriminator + Filter in allen Trip-Marker-Funktionen, mit rotem Test.
2. **Go/Infra brauchen keine Prod-Änderung:** `BriefingHealth` (`briefing_health.go:80-98`) zählt jeden Eintrag aus `users/*/pending_briefings.json`, liest `trip_id` nicht; `failed_segment_ids=[]` trägt 0 zu `degraded_segments_total` bei; `PendingBriefingEntry` ignoriert unbekannte Felder; Export-Erlaubnisliste `internal/store/user.go:467` führt die Datei schon. `check-gregor20.sh` zählt Compare-Marker automatisch mit → **kein MQ an `infra`**. Die Issue-Schätzung „Go-Store erweitern“ entfällt.
3. **`on_demand`-Lücke:** der `except`-Zweig um `send_compare_report` (`scheduler_dispatch_service.py` ~:751) prüft kein `on_demand` (nur der `channels_unreachable`-Zweig tut es). Marker-Schreiben dort braucht explizit `not on_demand`. Handversand und HEUTE/MORGEN-Befehle (:867) setzen `on_demand=True` → kein Marker.
4. **Hinweis-Transport:** Trip setzt „Nachgeliefert — …“ über `NotificationService._apply_prefixes/_prepend_hint` (`notification_service.py` ~:2360) nur in E-Mail (HTML + Plain, Compact-ASCII via `_ascii_hint`) und Telegram, **nicht** in SMS/Premium-SMS. `send_compare_report` (:1458) hat keinen Präfix-Parameter.

### Entscheidungen (Tech-Lead, keine PO-Frage)
- **Ablage:** dieselbe Datei `pending_briefings.json`, Compare-Einträge mit `kind: "vergleich"` + `preset_id` (kein `trip_id`). Eintrag ohne `kind` (Bestand) oder `kind == "route"` gehört dem Trip → rückwärtskompatibel, keine Migration. Separate Datei verworfen (Go-Glob, Export-Liste, Infra-Prüfung für denselben Effekt).
- **Code-Teilung (ADR-0097):** Marker-Operationen (laden, atomar schreiben, schreiben/ersetzen, entfernen, attempts hochzählen, dispatch_error räumen) in ein geteiltes Modul **ohne** `trip_`/`compare_`-Präfix (`src/services/pending_briefings.py`), parametrisiert über `kind` + Schlüssel. Trip-Methoden bleiben dünne Delegierer mit unveränderter Signatur; `_load_pending_entries`/`_write_pending_data` bleiben aus `trip_report_scheduler` importierbar (bestehende Tests). Nachhol-Schleifen bleiben getrennt (Trip: Segmente/Wetter; Compare: Preset), gemeinsam ist die Verfallsregel `briefing_target_day_is_current`. Umsetzung in zwei Schritten: reiner Extrakt mit grünen Trip-Tests, dann Compare.
- **Schlüssel:** `(preset_id, report_type)` (Morgen/Abend haben verschiedene Zieltage). Marker-Felder: `kind, preset_id, report_type, date` (Zieltag), `slot_hour`, `reason: "dispatch_error"`, `failed_segment_ids: []`, `attempts`, `created_at`.
- **Fehlerumfang:** Marker nur an den zwei bestehenden `record_briefing_dispatch_failure`-Stellen (Ausnahme, `channels_unreachable`), nur bei `not on_demand`. `no_channels` (Konfiguration, durch Nachholen nicht behebbar) und `no_weather` (beim Trip eigener #1012-Mechanismus) außerhalb → Nebenbefund #1199.
- **Nachhol-Schleife:** in `CompareDispatchStrategy.pre_pass` **nach** der Auto-Pause. Je Compare-Marker:
  - Preset fehlt / stillgelegt (`is_silenced`) / `end_date` abgelaufen → Marker verwerfen.
  - Zieltag vorbei (`briefing_target_day_is_current(date, today=preset_ortstag(preset, locs, now_utc))`) → verwerfen.
  - Ein Slot desselben Presets ist in dieser Stunde fällig **mit demselben Zieltag** → kein Catch-up; der reguläre Versand ist der letzte Versuch, der Marker überlebt bis zu dessen Erfolg (Trip #1662 AC-5). Damit ersetzt das reguläre Morgen-Briefing von D einen offenen Abend-Marker für D (kein inhaltsgleiches Doppel). Fällt nur ein Slot mit anderem Zieltag an, wird nachgeholt.
  - Sonst: Marker **vor** dem Senden entfernen (kein Doppelversand bei Absturz), dann senden mit Hinweis „Nachgeliefert — die Zustellung um HH:00 ist fehlgeschlagen“; scheitert es erneut, schreibt der Fehlerpfad einen frischen Marker.
  - Tagesbezug neu aus EINER Zeitabfrage: `tage_ab_ortstag = (date − preset_ortstag(now)).days` (Vertrag #1661); Slot (`report_type`) aus dem Marker durchreichen, damit `append_briefing_log` einen Abend-Nachholer nach Mitternacht nicht als „morning“ verbucht.
  - Zählung wie Trip: `sent` → `_success`, `no_channels` neutral, Rest → `_failed`.
- **Löschen bei Erfolg:** in `send_one_compare_preset` nach `outcome == "sent"` und `not on_demand`, nur `dispatch_error`-Marker desselben `(preset_id, report_type)`.
- **Hinweis-Kanäle:** wie Trip nur E-Mail (HTML + Plain, Compact-ASCII) und Telegram. Kein Renderer-Eingriff: Hinweis wird über den bestehenden Präfix-Baustein (`_prepend_hint`-Logik, geteilt statt kopiert) vor dem Versand angehängt. SMS/Premium-SMS ohne Nachhol-Hinweis ist eine **beidseitige** Lücke (Trip ebenso) → eigenes Issue/Nebenbefund, nicht hier ausweiten (160-Zeichen-Budget).
- **Spec-Ablösung:** `docs/specs/modules/dispatch_orchestrator.md:95` (Tabelle `pre_pass`: Compare = Auto-Pause **+** Nachholen) und `fix_1662_versandfehler_nachliefern.md:73-76` (Compare-Ausklammerung) ausdrücklich ablösen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/pending_briefings.py` | CREATE | Geteilte Marker-Operationen (kind-/schlüsselparametrisiert), atomares RMW |
| `src/services/trip_report_scheduler.py` | MODIFY | Delegierer auf geteiltes Modul; `kind`-Filter in `_process_pending_markers` und allen Marker-Funktionen (Blocker) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Marker schreiben an beiden Fehlerstellen (`not on_demand`), Löschen nach `sent`, Parameter Slot + Nachhol-Hinweis |
| `src/services/dispatch_orchestrator.py` | MODIFY | Compare-`pre_pass`: Nachhol-Schleife nach Auto-Pause, Zählung in `result()` |
| `src/services/notification_service.py` | MODIFY (klein) | Präfix-Baustein für Compare nutzbar machen (E-Mail/Telegram), falls nicht aufrufseitig lösbar |
| `docs/specs/modules/feat_2587_compare_briefing_nachholen.md` | CREATE | Spec mit ACs |
| `docs/specs/modules/dispatch_orchestrator.md`, `fix_1662_versandfehler_nachliefern.md` | MODIFY | Ablösung der Ist-Stand-Aussagen |
| `tests/tdd/test_compare_briefing_nachholen.py` (Name nach Verhalten) | CREATE | Marker bei Fehlschlag, kein Marker bei Handversand, Trip-Lauf lässt Compare-Marker stehen, Nachholen mit Hinweis, Verfall Zieltag, Abend nach Mitternacht, gleicher Zieltag fällig → kein Doppel, stillgelegt → verworfen, zwei Nutzer |
| `internal/scheduler/briefing_health_test.go` | MODIFY | Mischdatei (Trip- + Compare-Eintrag) zählt 2 |

### Scope Assessment
- Files: 6 Prod/Doku + 2 Tests
- Estimated LoC: Prod +250/−100 (≈100 davon Extrakt), Tests +400–500, Go nur Test (~30)
- Risk Level: MEDIUM — berührt den Trip-Nachholpfad (Extrakt + Filter), Datenschutz der gemeinsamen Datei; Go/Infra unberührt.

### Technical Approach (Reihenfolge)
1. Extrakt `pending_briefings.py`, Trip delegiert — Trip-Tests bleiben grün.
2. `kind`-Filter in Trip-Funktionen + roter Test „Compare-Marker überlebt Trip-Lauf“.
3. Marker-Hooks in `send_one_compare_preset` (beide Fehlerstellen, `not on_demand`) und Löschen nach `sent`.
4. Nachhol-Schleife im Compare-`pre_pass`, Hinweis E-Mail/Telegram, Zählung.
5. Spec-Ablösungen, Go-Mischdatei-Test.

### Dependencies
Upstream: `briefing_target_day_is_current`, `preset_ortstag`, `is_silenced`, `_load_presets_for_dispatch`, `outcome_from_result`, `SendOutcomeError`, `append_briefing_log`. Downstream: Go `BriefingHealth` → `/api/scheduler/status` → `check-gregor20.sh` (unverändert).

### Nebenbefunde (→ #1199)
- Nachhol-Hinweis fehlt in SMS/Premium-SMS bei Trip **und** Ortsvergleich (ADR-0095-Parität).
- Ortsvergleich `no_weather` wird nicht nachgeholt (Trip hat #1012-Mechanismus).

### Open Questions
- keine (alle Punkte technisch entschieden, s. oben)
