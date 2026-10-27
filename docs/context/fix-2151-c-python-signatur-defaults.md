# Context: fix-2151-c-python-signatur-defaults

## Request Summary
#2151 Scheibe C: die restlichen 40 Python-Signatur-Defaults `user_id="default"` in `src/` entfernen
(Pflichtargument), alle Aufrufer nachziehen und die Ratsche `_SRC_BESTAND` in
`tests/test_user_id_default_guard.py` leeren. Scheibe A (Python-Router, PR #2365) und B (Go-Store,
PR #2372) sind live. PO-Entscheid aus A: Konto `default` bleibt gültig, verboten ist nur der
automatische Rückfall (ADR-0003).

## Related Files
| File | Relevance |
|------|-----------|
| `tests/test_user_id_default_guard.py` | AST-Wächter; `_SRC_BESTAND` (40 Einträge) muss am Ende leer sein |
| `src/app/loader.py` | 11 Einträge (`load_trip`, `get_*_dir`, `load_all_*`, `save_*`, `delete_*`) |
| `src/services/trip_command_processor.py` | 12 Einträge inkl. Dataclass-Feld `InboundMessage.user_id` |
| `src/services/preview_service.py` | 4 Einträge (`_load_trip`, `render_*_preview`) |
| `src/services/notification_service.py:439` | `NotificationService.__init__` → `Settings().with_user_profile(user_id)` |
| `src/services/inbound_email_reader.py:72`, `inbound_telegram_reader.py:108` | `NotificationService()` ohne user_id (Konstruktor liest `users/default/user.json`) |
| `src/services/{alert_state,compare_alert,compare_official_alert,compare_radar_alert,compare_weather_snapshot,trip_alert,trip_report_scheduler,weather_extractor,weather_snapshot,scheduler_dispatch_service}.py` | je 1 Konstruktor-/Funktions-Default |
| `tools/weather_validation.py:88/89/219/220/301` | Einzige Produktivaufrufer, die den Default WIRKLICH nutzen (lesen `users/default`) |
| `src/app/cli.py:217`, `loader.py:1512`, `preview_service.py:88`, `trip_report_scheduler.py:341` | `load_trip(...)` ohne user_id — Default wirkungslos (user_id nur auf `data_dir`-Pfad gelesen, loader.py:426) |

## Aufrufer-Karte (Kurz)
- **11 Produktivaufrufe ohne user_id**, alle anderen (~180) übergeben ihn bereits.
  - 4× `load_trip` — nur Signatur, Default heute wirkungslos
  - 2× `NotificationService()` in Inbound-Readern — nur Konstruktor; die genutzten Methoden bekommen
    `user_settings` explizit, lesen weder `self._settings` noch `self._user_id`
  - 5× `tools/weather_validation.py` — echter Rückfall, braucht CLI-Argument/Parameter
- **Versteckte Rückfälle** (`or "default"`, `.get("user_id","default")`, Hardcode-Pfad) in `src/`/`api/`:
  keine mehr. `scripts/cleanup_1265_prod_testdata.py` verdrahtet `users/"default"` fest (einmaliges
  Aufräum-Script, außerhalb Scope).
- **Tests:** 277 Aufrufe ohne user_id in 81 Dateien (Top: `test_corridor_persistence.py` 14,
  `test_weather_snapshot.py` 13, `test_befehlspfade_folgen_ortszone.py` 11). Davon `load_trip` 79
  (fast alle wirkungslos), `TripReportSchedulerService` 60, `save_trip` 37, `TripAlertService` 31,
  `WeatherSnapshotService` 29, `InboundMessage` 11.
- **Einziger Test, der den Default bewusst prüft:** `tests/integration/test_weather_snapshot.py:600`
  `test_get_snapshots_dir_default` → umschreiben/löschen.
- `InboundMessage`: Default entfernen ist ohne Umsortieren gültig (6 Pflichtfelder vor 2 Default-Feldern).

## Existing Patterns
- Scheibe A: `Query(...)` statt Default in Routern; AST-Wächter mit schrumpfender Ratsche.
- Scheibe B: fail-closed (`ErrInvalidUserID`) statt Rückfall.
- Übliche Übergabe: Keyword `user_id=` (fast alle Produktivaufrufer).

## Dependencies
- Upstream: `Settings.with_user_profile`, `get_data_root`.
- Downstream: Scheduler, Alarm-Dienste, Inbound-Reader (E-Mail/Telegram/SMS), Vorschau, CLI, `tools/`.

## Existing Specs
- `docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md` (Ratsche, AC-8/10/11)
- `docs/specs/modules/fix_2151_default_fallbacks_scheibe_b.md`
- `docs/context/fix-2151-default-fallbacks-entfernen.md` (Gesamtplan)

## Risks & Considerations
- Übersehener Aufrufer ⇒ TypeError im Laufzeitpfad (Scheduler/Inbound) statt still falsches Konto —
  statische Karte + voller Kernlauf nötig; dynamische Erzeugung wurde per AST gesucht, keine gefunden.
- Mechanischer Test-Umbau in ~81 Dateien ⇒ LoC-Limit 250 wird überschritten (Tests zählen) ⇒ Override 500.
- `load_trip`: Designfrage, ob user_id nur für den `data_dir`-Pfad Pflicht wird (Signatur-Split)
  oder überall Pflicht.
- `NotificationService` in den Readern: nutzerlos erzeugen (Konstruktor ohne Profil-Laden) vs.
  pro Nachricht mit echter user_id erzeugen.
- Renderer-Commit-Gate kann bei Änderung an `notification_service.py`/`preview_service.py` greifen.

## Analysis

### Type
Feature/Härtung (Multi-User-Readiness, ADR-0003) — kein nutzersichtbarer Bug.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` | MODIFY | 10 Funktionen: `user_id` Pflicht; `load_trip`: `user_id: str \| None = None`, ValueError nur auf `data_dir`-Pfad (Z. 426) |
| `src/services/notification_service.py` | MODIFY | `user_id` ohne `"default"`; ohne `settings` und ohne `user_id` ⇒ ValueError; `self._user_id`-Nutzung fail-closed (Vorbild Scheibe B `requireUser`) |
| `src/services/inbound_email_reader.py`, `inbound_telegram_reader.py` | MODIFY | `NotificationService` in `poll_and_process(settings)` mit `settings=settings` statt nutzerlos im `__init__` |
| `src/services/trip_command_processor.py` | MODIFY | 11 Methoden + `InboundMessage.user_id` Pflicht |
| `src/services/preview_service.py` | MODIFY | 4 Einträge Pflicht |
| 10 weitere Service-Dateien | MODIFY | je 1 Konstruktor-/Funktions-Default Pflicht |
| `tools/weather_validation.py` | MODIFY | `--user-id` Pflicht-Argument, durchreichen an 5 Aufrufe |
| `tests/test_user_id_default_guard.py` | MODIFY | `_SRC_BESTAND` leer; neu: kein Literal `"default"` als `user_id`-Argument an Aufrufstellen in `src/`/`api/`/`tools/` |
| `tests/**` (~81 Dateien) | MODIFY | ~277 Aufrufe explizit mit `user_id` (Tests dürfen das Konto `default` explizit benutzen) |
| `tests/integration/test_weather_snapshot.py` | MODIFY | `test_get_snapshots_dir_default` löschen (prüft abgeschafftes Verhalten) |

### Scope Assessment
- Files: ~17 src/tools + ~81 Tests
- Estimated LoC: src ~+120/-60, Tests ~+300 (mechanisch) ⇒ `loc_limit_override 500`
- Risk Level: MEDIUM (übersehener Aufrufer ⇒ TypeError statt stillem Falschkonto)

### Technical Approach
1. **Ein PR, Schnitt entlang der Funktionsachse** (nicht Code vs. Tests): Signatur + alle Prod- UND Testaufrufer +
   Ratschen-Einträge gemeinsam, sonst ist der Kern rot bzw. AC-10 (bidirektional) rot. Commit-Reihenfolge
   loader+tools → trip_command_processor+InboundMessage → übrige Services/NotificationService.
   Reicht 500 LoC nicht, wird entlang derselben Gruppen in Folge-Workflows geschnitten.
2. **Kein Literal `"default"` als Nutzer im Produktivcode** — auch nicht handgeschrieben an Aufrufstellen
   (sonst wäre der Rückfall nur verschoben). Wächter-Erweiterung auf Aufruf-Argumente. Heute 0 solche
   Stellen in `src/`/`api/`/`tools/` (grep verifiziert) ⇒ AC sicher.
3. `load_trip`: Die Legacy-CLI (`cli.py:217`) lädt eine Datei ohne Nutzerbezug; dort ist `user_id` inhaltlich
   bedeutungslos. Daher `None`-Default + lauter Fehler nur dort, wo er gebraucht wird (Dateipfad unter
   `data_dir`) — strikt sicherer als ein still greifendes `"default"`.
4. `NotificationService` in den Readern: nutzt heute nur Methoden mit explizitem `settings`; Service wird
   mit dem übergebenen `settings` gebaut ⇒ `with_user_profile` wird auf diesem Pfad nie aufgerufen.
5. Test-Migration mechanisch mit `user_id="default"` (Konto bleibt gültig) bzw. vorhandener Test-Kennung.
   Vollständigkeitsnachweis per AST-Inventar über ALLE `tests/**` (auch `live`/`email`-markierte, die CI
   nicht ausführt) — 0 Aufrufe der betroffenen Funktionen ohne `user_id`.

### Dependencies
Upstream `Settings.with_user_profile`, `get_data_root`. Downstream Scheduler, Alarm-Dienste, Inbound-Reader,
Vorschau, Legacy-CLI, `tools/`. Keine Go-/Frontend-Änderung.

### Open Questions
- keine PO-Fragen (technische Entscheidungen oben begründet)
