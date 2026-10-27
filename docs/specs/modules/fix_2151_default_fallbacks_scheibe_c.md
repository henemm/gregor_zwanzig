---
entity_id: fix_2151_default_fallbacks_scheibe_c
type: feature
created: 2026-09-19
updated: 2026-09-19
status: implemented
workflow: fix-2151-c-python-signatur-defaults
issue: 2151
---

# Scheibe C: Python-Signatur-Defaults `user_id="default"` in `src/`/`tools/` entfernen (#2151)

## Approval

- [ ] Approved

## Purpose

Scheibe A hat den `"default"`-Rückfall in den Python-Sende-/Lesepfaden der Router entfernt,
Scheibe B den analogen Rückfall auf der Go-Store-Seite. Diese dritte Scheibe schließt die letzte
Lücke: In `src/` und `tools/` tragen noch 40 Funktions-/Konstruktor-Signaturen und ein
Dataclass-Feld den Default `user_id="default"` — ruft ein Aufrufer die Kennung nicht mit, arbeitet
der Code still auf dem Konto `default` statt sichtbar zu scheitern (ADR-0003, Cross-User-Risiko).
Diese Scheibe macht `user_id` in allen 40 Bestandsstellen zum Pflichtparameter, zieht alle
Produktiv- und Testaufrufer nach und leert die Ratsche `_SRC_BESTAND` in
`tests/test_user_id_default_guard.py` vollständig. Anders als Scheibe A/B ist dies laut der
verbindlichen Analyse kein Bugfix, sondern Härtung (Multi-User-Readiness, kein nutzersichtbares
Fehlverhalten heute) — daher `type: feature` statt `bugfix`. Konto `default` bleibt — wie in
Scheibe A festgelegt — ein gültiges, explizit aufrufbares Konto; verboten ist ausschließlich der
stille, implizite Rückfall.

## Source

- **File:** `src/app/loader.py`
- **Identifier:** `def load_trip` / `def get_snapshots_dir` / `def save_trip` (u.a. 10 weitere Funktionen, siehe Scope)

> **Schicht:** Python-Core (`src/app/`, `src/services/`, `tools/`) — kein Go, kein Frontend in
> dieser Scheibe.

## Estimated Scope

- **LoC:** ~+420/-90 (grob) — `loc_limit_override 500` setzen; wird 500 nicht erreicht, Schnitt in
  Folge-Workflows entlang derselben Funktionsgruppen (loader+tools → trip_command_processor+InboundMessage
  → übrige Services/NotificationService), kein willkürlicher Datei-Schnitt.
- **Files:** ~17 Quell-/Tool-Dateien + ~81 Testdateien (mechanisch)
- **Effort:** high (großer Aufrufer-Fan-out, aber technisch mechanisch — siehe Aufrufer-Karte im Kontext-Dokument)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0003 (Multi-Tenant-Isolation) | ADR | Grundsatz: kein `"default"`-Rückfall in authentifiziertem/produktivem Pfad |
| `docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md` | Spec (PO-freigegeben) | PO-Entscheid „`default` bleibt gültiger Kontoname" gilt unverändert; legt die Ratsche `_SRC_BESTAND` und den Wächter-Aufbau an, den diese Scheibe leert und erweitert |
| `docs/specs/modules/fix_2151_default_fallbacks_scheibe_b.md` | Spec (implementiert) | Vorbild „fail-closed" (`requireUser()`) für den Go-Store; diese Scheibe überträgt dasselbe Prinzip auf `NotificationService`/Loader in Python |
| `tests/test_user_id_default_guard.py` | Bestandscode | AST-Wächter mit `_SRC_BESTAND`; wird in dieser Scheibe geleert und um die Prüfung „kein Literal `\"default\"` als Aufruf-Argument" erweitert |
| `docs/context/fix-2151-c-python-signatur-defaults.md` | Analyse (verbindlich) | Vollständige Aufrufer-Karte (40 Signaturen, ~277 Testaufrufe in 81 Dateien), Designentscheidungen zu `load_trip`/`NotificationService`, Risiken |
| `src/services/inbound_email_reader.py` (bestehendes Muster für unbekannten Absender, #2147/Scheibe A) | Vorbild-Code | Zeigt das Zielmuster „unbekannt = `None`" — hier nur als Abgrenzung relevant, diese Scheibe ändert die Sentinel-Logik nicht erneut |
| `src/services/inbound_sms_reader.py:346-383` | Bestandscode (bereits konform) | Konstruiert `InboundMessage`/`NotificationService` schon heute ausschließlich mit explizitem `user_id`, nie mit dem Literal `"default"` — Referenz für AC-7, wird nur verifiziert, nicht geändert |
| `tests/test_output_timezone_guard.py` | Test-Muster | Vorbild für AST-basierten Struktur-Wächter (bereits von Scheibe A übernommen) |
| `.claude/hooks/renderer_mail_gate.py` (`_MAIL_PATTERNS`, Z. 42-47) | Gate-Code (verifiziert) | Prüft `src/output/renderers/...` und `src/output/channels/email.py` — `src/services/notification_service.py` und `src/services/preview_service.py` liegen außerhalb dieser Muster, das Renderer-Commit-Gate greift bei dieser Scheibe nicht (siehe Risiken) |

## Implementation Details

**1. Loader + Tools zuerst (`src/app/loader.py`, `tools/weather_validation.py`).** Zehn Funktionen
in `loader.py` (`get_data_dir`, `get_locations_dir`, `get_briefings_dir`, `get_snapshots_dir`,
`load_all_locations`, `save_location`, `delete_location`, `load_all_trips`, `save_trip`,
`delete_trip`) verlieren den Default; `user_id` wird Pflichtparameter, ein Aufruf ohne Kennung
wirft `TypeError` (Python-Standardverhalten bei fehlendem Pflichtargument). `load_trip` erhält
eine Sonderrolle: die Legacy-CLI (`src/app/cli.py:217`) lädt eine Datei ohne Nutzerbezug, dort ist
`user_id` inhaltlich bedeutungslos. Die Signatur wird auf `user_id: str | None = None` gesetzt; der
Fehler (`ValueError`) entsteht ausschließlich auf dem Zweig, der `user_id` tatsächlich für einen
Dateipfad unter `data_dir` braucht (`loader.py:426`), nicht beim Laden aus Dict oder explizitem
Dateipfad. Das ist strikt sicherer als ein still greifender `"default"`-Wert, weil der
nutzerbezogene Zweig ohne Kennung nie mehr lesen/schreiben kann, während der nutzerlose Zweig
(Legacy-CLI) unverändert funktioniert. `tools/weather_validation.py` erhält ein Pflicht-Argument
`--user-id` (argparse `required=True`); die fünf Aufrufstellen (Z. 88/89/219/220/301) reichen den
geparsten Wert durch — das ist der einzige Produktivpfad, der den Default heute wirklich nutzt
(liest `users/default/*` unabhängig vom aufrufenden Nutzer).

**2. `trip_command_processor.py` + `InboundMessage`.** Elf Methoden von `TripCommandProcessor`
sowie das Dataclass-Feld `InboundMessage.user_id` verlieren den Default. Die Dataclass bleibt gültig
ohne Feld-Umsortierung, weil sechs Pflichtfelder vor den zwei bisherigen Default-Feldern stehen
(kein Reihenfolge-Konflikt bei `@dataclass`). Ein `InboundMessage(...)`-Aufruf ohne `user_id` wirft
danach `TypeError`. Von den drei Inbound-Readern konstruieren `inbound_email_reader.py` und
`inbound_telegram_reader.py` `InboundMessage` an Stellen, die nach dieser Änderung `user_id`
explizit mitgeben müssen (siehe Punkt 3); `inbound_sms_reader.py` konstruiert `InboundMessage`
bereits heute an allen drei Aufrufstellen (`_verarbeite_befehl`, Z. 346-350/364-367/370-374) mit
explizitem `user_id=user_id` — hier ist keine Codeänderung nötig, nur die Verifikation, dass diese
Datei weiterhin fehlerfrei durchläuft.

**3. Übrige Services + `NotificationService`.** Zehn Service-Dateien mit je einem
Konstruktor-/Funktions-Default (`AlertStateService`, `CompareAlertService`,
`CompareOfficialAlertService`, `CompareRadarAlertService`, `CompareWeatherSnapshotService`,
`TripAlertService`, `TripReportSchedulerService`, `WeatherExtractor`, `WeatherSnapshotService`,
`scheduler_dispatch_service.run_compare_presets_daily`) sowie `PreviewService` (vier Einträge)
verlieren den Default; fehlende Kennung ⇒ `TypeError` beim Konstruktor-/Funktionsaufruf, bevor
irgendein Datei- oder Netzwerkzugriff läuft. `NotificationService.__init__` erhält zusätzlich eine
fail-closed-Prüfung nach dem Vorbild von Scheibe B (`requireUser()`): fehlt sowohl `settings` als
auch `user_id`, wirft der Konstruktor `ValueError`, statt intern `Settings().with_user_profile("default")`
aufzurufen. Zugriffe, die `self._user_id` benötigen, scheitern fail-closed statt mit einem stillen
`"default"`-Rückgriff. Die beiden Konstruktions-Stellen in `inbound_email_reader.py:72` und
`inbound_telegram_reader.py:108` werden von „nutzerlos im `__init__`" auf „mit dem in
`poll_and_process(settings)` bereits vorhandenen `settings`-Objekt" umgestellt
(`NotificationService(settings=settings)`); die von den Readern tatsächlich genutzten Methoden
lesen ohnehin nur das explizit übergebene `user_settings`, nie `self._settings`/`self._user_id` —
dieser Umbau ändert daher kein sichtbares Verhalten der Reader, entfernt aber den impliziten
`with_user_profile("default")`-Aufruf beim Konstruieren. **Hinweis Gate-Prüfung:** Beide Dateien
sowie `notification_service.py`/`preview_service.py` liegen außerhalb der `_MAIL_PATTERNS` des
Renderer-Commit-Gates (`.claude/hooks/renderer_mail_gate.py:42-47`, verifiziert per Grep) — das
Gate blockt diese Commits nicht.

**4. Wächter-Erweiterung.** `tests/test_user_id_default_guard.py` wird um eine zweite Prüfebene
ergänzt (AST, kein String-Grep): Neben Signatur-Defaults (bestehend, AC-8/AC-10 aus Scheibe A)
sucht ein neuer Sammler nach `Call`-Knoten in `src/`, `api/`, `tools/`, die das Literal `"default"`
als Nutzerkennung übergeben. Die Erkennungsregel ist bewusst eng und ohne generische
Signaturauflösung entscheidbar: (a) jedes Keyword-Argument `user_id="default"` an einem
beliebigen Aufruf, unabhängig vom Funktionsnamen; (b) ein positionelles erstes Argument
`"default"` ausschließlich bei einem Aufruf, dessen Funktionsname (`Attribute.attr` oder
`Name.id`) `with_user_profile` lautet — das ist die einzige heute im Code vorkommende Stelle, an
der die Nutzerkennung positionell statt per Keyword übergeben wird
(`Settings().with_user_profile(user_id)`, siehe Dependencies). Neue Funktionsziele mit positionellem
`user_id` fängt der Wächter nicht generisch ab — das ist eine bewusste Scope-Grenze (siehe Known
Limitations). Heute existieren null Stellen, die diese Regel träfen (grep-verifiziert in der
Analyse) — der neue Test startet grün und bewacht künftig, dass der Rückfall nicht von der
Signatur an die Aufrufstelle verschoben wird. `_SRC_BESTAND` wird auf `frozenset()` gesetzt; der
bestehende Test `test_ac10_src_bestand_stimmt_exakt_mit_dem_code_ueberein` verifiziert damit
automatisch, dass keine der 40 Stellen mehr existiert, während der bestehende Empfindlichkeitstest
`test_ac10_ratsche_schlaegt_in_beide_richtungen_an` unverändert und grün bleibt, weil er ausschließlich
gegen einen unter `tmp_path` gepflanzten Baum prüft, nie gegen den echten (dann leeren) `_SRC_BESTAND`.
Neue Testfunktionen für die Aufrufstellen-Prüfung erhalten wie das Bestandsmodul den Kommentar
`# doc-compliance-test` in Zeile 1.

**6. Keyword-only-Signaturen, wo vorher `settings=None` stand.** Bei `TripAlertService`,
`CompareAlertService`, `CompareOfficialAlertService`, `CompareRadarAlertService` und
`TripReportSchedulerService` steht `*,` unmittelbar vor `user_id` in der Parameterliste
(`def __init__(self, settings: Optional[Settings] = None, *, user_id: str, ...)`). Das ist
technisch zwingend, nicht stilistisch: `settings` hat einen Default-Wert und steht vor `user_id` in
der Signatur — ohne `*,` würde Python `user_id` selbst nach Entfernen des `="default"`-Defaults
weiterhin als optional-positionell nach einem bereits defaulteten Parameter ablehnen
(`SyntaxError: non-default argument follows default argument`). Der `*,` erzwingt Keyword-only für
`user_id` und macht es damit trotz vorausgehendem Default-Parameter zum echten Pflichtargument.
`CompareWeatherSnapshotService`, `WeatherExtractor`, `WeatherSnapshotService` und `AlertStateService`
brauchen dieses Muster nicht, weil sie kein `settings`-Feld vor `user_id` führen.

**7. Inbound-Reader bauen `NotificationService` lazy statt in `poll_and_process`.** Sowohl
`inbound_email_reader.py` als auch `inbound_telegram_reader.py` konstruieren den
`NotificationService` nicht mehr beim Einstieg von `poll_and_process(settings)`, sondern über eine
neue private Methode `_ensure_notification_service(settings)`, die am Anfang von
`_process_single`/`_process_update` (E-Mail) bzw. `_process_start_command` (Telegram) aufgerufen
wird und das Attribut nur bei Bedarf setzt. Grund: Bestandstests rufen diese inneren
Verarbeitungsmethoden direkt auf, ohne vorher `poll_and_process` zu durchlaufen — eine
Konstruktion ausschließlich in `poll_and_process` hätte diese Tests mit einem fehlenden
`NotificationService`-Attribut brechen lassen. Die Lazy-Init hält das Verhalten für beide
Aufrufwege (voller Poll-Zyklus und direkter Testaufruf) identisch.

**8. `NotificationService._require_user()` nach Go-Vorbild.** Analog zu `requireUser()` aus
Scheibe B (Go-Store) bündelt `_require_user()` die fail-closed-Prüfung an einer Stelle: Jede
interne Operation, die `self._user_id` braucht (z. B. `WeatherSnapshotService(user_id=...)`,
Notification-Log-Einträge), ruft `self._require_user()` statt direkt `self._user_id` zu lesen. Fehlt
die Kennung, wirft `_require_user()` einen eindeutigen Fehler an genau der Stelle, an der sie
gebraucht wird — kein stiller Rückgriff auf `"default"` an verstreuten Zugriffsstellen.

**5. Test-Migration.** ~277 Testaufrufe in ~81 Dateien werden mechanisch auf explizite `user_id`
umgestellt — überwiegend `user_id="default"` (Konto bleibt laut Scheibe-A-Entscheid gültig) oder auf
eine bereits im jeweiligen Test verwendete andere Kennung, wo das dem Testzweck besser entspricht.
Der Vollständigkeitsnachweis läuft nicht test-für-test, sondern per AST-Inventar über **alle**
`tests/**/*.py` (auch `live`-/`email`-markierte Dateien, die CI nicht ausführt) gegen die Liste der
40 betroffenen Funktionen/Konstruktoren/Dataclass — null verbleibende Aufrufe ohne `user_id`.
`tests/integration/test_weather_snapshot.py::test_get_snapshots_dir_default` prüft explizit das
abgeschaffte Rückfallverhalten und wird gelöscht statt umgeschrieben. Neue Testdateien dieser
Scheibe liegen flach unter `tests/` bzw. `tests/integration/`, analog zum bestehenden Bestand
(`tests/test_preview_service_user_isolation.py`, `tests/test_scheduler_router_requires_user_id.py`)
— es gibt keine Unterordner `tests/app/` oder `tests/services/` (verifiziert per `ls tests/`),
`pyproject.toml` sammelt ausschließlich `testpaths = ["tests"]`.

## Expected Behavior

- **Input:** Ein Aufruf einer der 40 betroffenen Funktionen/Konstruktoren/`InboundMessage` ohne
  `user_id`-Argument.
- **Output:** `TypeError` (fehlendes Pflichtargument) bzw. bei `load_trip`/`NotificationService`
  ein `ValueError` genau dort, wo die Kennung tatsächlich für einen Dateizugriff gebraucht wird —
  nie ein stiller Zugriff auf `users/default/`.
- **Side effects:** Keine Datei unter `users/default/` entsteht/verändert sich als Nebenwirkung
  eines Aufrufs, der die Kennung eines anderen Kontos meinte, aber vergessen hat sie zu übergeben.

## Risiken

- **Übersehener Aufrufer.** Bei ~40 geänderten Signaturen und ~277 Testaufrufen ist das Hauptrisiko
  ein vergessener Aufrufer im Laufzeitpfad (Scheduler, Inbound-Reader) — der schlägt dann als
  `TypeError`/`ValueError` durch statt still auf ein falsches Konto zu greifen (Risk Level MEDIUM,
  laut Analyse), ist also fail-closed statt fail-silent, aber ein Betriebsvorfall, wenn er
  Produktivcode statt Testcode trifft. Gegenmaßnahme: Umsetzung strikt entlang der in der Analyse
  dokumentierten, vollständigen Aufrufer-Karte (nicht ad hoc), plus vollständiger grüner Kernlauf
  (Test 14) vor jedem Commit-Schritt dieser Scheibe.
- **Renderer-Commit-Gate — verifiziert nicht einschlägig.** Die Analyse nannte als offenes Risiko,
  dass das Renderer-Commit-Gate (#811) bei Änderungen an `notification_service.py`/
  `preview_service.py` greifen könnte, weil beide als „Mail-Inhalts-Dateien" gelten. Diese Spec hat
  das gegen `.claude/hooks/renderer_mail_gate.py:42-47` (`_MAIL_PATTERNS`) geprüft: Das Gate matcht
  ausschließlich `src/output/renderers/**/*.py` und `src/output/channels/email.py` — beide in dieser
  Scheibe geänderten Dateien liegen unter `src/services/` und treffen kein Muster. Das Gate blockt
  diese Commits also nicht; sollte sich `_MAIL_PATTERNS` bis zur Implementierung ändern, ist die
  Prüfung vor dem ersten betroffenen Commit erneut mit `grep _MAIL_PATTERNS` zu wiederholen.
- **LoC-Fan-out in Tests.** Die mechanische Umstellung von ~277 Aufrufen in ~81 Testdateien ist der
  Hauptteil der geschätzten LoC und lässt sich schlecht weiter reduzieren, ohne die
  Vollständigkeitsprüfung (AC-10) zu gefährden — deshalb `loc_limit_override 500` von Anfang an
  einplanen statt erst bei Überschreitung.

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/loader.py` | MODIFY | 10 Funktionen `user_id` Pflicht; `load_trip`: `user_id: str \| None = None`, `ValueError` nur auf dem `data_dir`-Zweig (Z. ~426) |
| `tools/weather_validation.py` | MODIFY | `--user-id` Pflicht-CLI-Argument, an 5 Aufrufstellen (Z. 88/89/219/220/301) durchgereicht |
| `src/services/trip_command_processor.py` | MODIFY | 11 Methoden + Dataclass-Feld `InboundMessage.user_id` Pflicht |
| `src/services/inbound_email_reader.py` | MODIFY | `InboundMessage(...)` mit aufgelöster `user_id`; `NotificationService(settings=settings)` statt nutzerlosem `__init__` |
| `src/services/inbound_telegram_reader.py` | MODIFY | analog zu `inbound_email_reader.py` |
| `src/services/inbound_sms_reader.py` | VERIFY (keine Codeänderung erwartet) | Konstruiert `InboundMessage`/`NotificationService` bereits heute mit explizitem `user_id`; Kernlauf verifiziert, dass die Datei nach den Signaturänderungen weiter fehlerfrei importiert und getestet wird |
| `src/services/preview_service.py` | MODIFY | 4 Einträge (`_load_trip`, `render_email_preview`, `render_sms_preview`, `render_telegram_preview`) Pflicht |
| `src/services/notification_service.py` | MODIFY | `__init__` ohne `"default"`-Default; ohne `settings` UND ohne `user_id` ⇒ `ValueError`; `self._user_id`-Nutzung fail-closed |
| `src/services/alert_state.py` | MODIFY | `AlertStateService.__init__` Pflicht |
| `src/services/compare_alert.py` | MODIFY | `CompareAlertService.__init__` Pflicht |
| `src/services/compare_official_alert.py` | MODIFY | `CompareOfficialAlertService.__init__` Pflicht |
| `src/services/compare_radar_alert.py` | MODIFY | `CompareRadarAlertService.__init__` Pflicht |
| `src/services/compare_weather_snapshot.py` | MODIFY | `CompareWeatherSnapshotService.__init__` Pflicht |
| `src/services/trip_alert.py` | MODIFY | `TripAlertService.__init__` Pflicht |
| `src/services/trip_report_scheduler.py` | MODIFY | `TripReportSchedulerService.__init__` Pflicht |
| `src/services/weather_extractor.py` | MODIFY | `WeatherExtractor.__init__` Pflicht |
| `src/services/weather_snapshot.py` | MODIFY | `WeatherSnapshotService.__init__` Pflicht |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `run_compare_presets_daily` Pflicht |
| `tests/test_user_id_default_guard.py` | MODIFY | `_SRC_BESTAND` → `frozenset()`; neuer Sammler „kein Literal `\"default\"` als `user_id`-Aufruf-Argument" (Keyword überall, positionell nur bei `with_user_profile`) in `src/`/`api/`/`tools/` |
| `tests/integration/test_weather_snapshot.py` | MODIFY | `test_get_snapshots_dir_default` löschen (prüft abgeschafftes Verhalten) |
| `tests/**` (~79 weitere Dateien, flach unter `tests/` bzw. `tests/integration/`) | MODIFY | ~277 Aufrufe mechanisch auf explizite `user_id` umgestellt (mehrheitlich `user_id="default"`) |

**Out of Scope (mit Begründung):**
- `scripts/cleanup_1265_prod_testdata.py` — verdrahtet `users/"default"` fest als einmaliges
  Aufräum-Script außerhalb des Produktivpfads; keine Signatur mit Default, kein ADR-0003-Risiko.
- Go-Seite (`internal/`, `cmd/`) — vollständig in Scheibe B abgeschlossen.
- `internal/handler/cockpit.go`/`archive_stats.go` (verschluckte Store-Fehler) — bereits in Scheibe B
  als bekannt dokumentiert, Nacharbeit läuft über Sammel-Issue #1199, betrifft ohnehin Go nicht Python.
- Keine allgemeine Ausweitung des Wächters auf beliebige `None`-Defaults oder andere
  sicherheitsrelevante Parameter — Scope bleibt exakt `user_id="default"` (Signatur) und
  `user_id="default"` (Aufrufstelle), wie in #2151 gefordert.

### Estimated Changes
- Files: ~17 Quell-/Tool-Dateien (davon 1 nur verifiziert, nicht geändert), ~81 Testdateien (davon 1 mit gelöschtem Test)
- LoC: src/tools ~+120/-60, Tests ~+300 (mechanisch) ⇒ Gesamt ~+420/-90, `loc_limit_override 500`
  setzen. Reicht das nicht, wird **entlang der in Implementation Details Punkt 1–3 beschriebenen
  Funktionsgruppen** (loader+tools → trip_command_processor+InboundMessage → übrige
  Services/NotificationService) in Folge-Workflows geschnitten — nicht willkürlich nach Datei.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (`tests/test_user_id_default_guard.py::test_ac10_src_bestand_stimmt_exakt_mit_dem_code_ueberein`,
  bestehend): GIVEN `_SRC_BESTAND` ist auf `frozenset()` gesetzt, WHEN der Wächter über `src/`
  läuft, THEN findet er keine verbleibende `user_id="default"`-Signatur mehr — der Test wird ohne
  Codeänderung an ihm selbst grün, sobald alle 40 Stellen entfernt sind.
- [ ] Test 2 (neu, in `tests/test_user_id_default_guard.py`, `# doc-compliance-test`): GIVEN der
  aktuelle Quellbaum unter `src/`, `api/`, `tools/` nach dieser Änderung, WHEN der neue
  Aufrufstellen-Sammler nach dem Literal `"default"` als `user_id`-Keyword-Argument (überall) bzw.
  positionell (nur bei `with_user_profile(...)`) sucht, THEN findet er keine einzige Stelle.
- [ ] Test 3 (neu, in `tests/test_user_id_default_guard.py`, Mutations-Fixture unter `tmp_path`):
  GIVEN ein gepflanzter Baum mit einem Aufruf `save_trip(trip, user_id="default")` und einem
  Aufruf `Settings().with_user_profile("default")`, WHEN der Aufrufstellen-Sammler läuft, THEN
  findet und benennt er beide Stellen — der Wächter fängt neue Fälle, nicht nur die bekannten.
- [ ] Test 4 (`tests/test_loader_requires_user_id.py`, neu): GIVEN ein Aufruf von `save_trip` bzw.
  `get_snapshots_dir` ohne `user_id`-Argument, WHEN die Funktion ausgeführt wird, THEN wirft sie
  `TypeError` und es entsteht keine Datei unter `users/default/`.
- [ ] Test 5 (`tests/test_loader_requires_user_id.py`, neu): GIVEN ein Trip wird per `load_trip`
  aus einem Dict oder einem expliziten Dateipfad geladen (kein `data_dir`-Zugriff), WHEN
  `load_trip` ohne `user_id` aufgerufen wird, THEN gelingt das Laden unverändert (Legacy-CLI-Pfad
  bleibt funktionsfähig).
- [ ] Test 6 (`tests/test_loader_requires_user_id.py`, neu): GIVEN `load_trip` wird mit einem
  `data_dir` aufgerufen, das den Trip anhand der Nutzerkennung lokalisieren muss, WHEN `user_id`
  fehlt, THEN wirft die Funktion `ValueError`, bevor irgendein Datei-Zugriff unter `users/` erfolgt.
- [ ] Test 7 (`tests/test_notification_service_requires_identity.py`, neu): GIVEN
  `NotificationService()` wird ohne `settings` und ohne `user_id` konstruiert, WHEN der Konstruktor
  läuft, THEN wirft er `ValueError` und liest zu keinem Zeitpunkt `users/default/user.json`.
- [ ] Test 8 (`tests/test_notification_service_requires_identity.py`, neu): GIVEN ein
  `NotificationService`, das mit `settings` aber ohne `user_id` konstruiert wurde, WHEN eine
  Operation aufgerufen wird, die `self._user_id` benötigt, THEN scheitert der Aufruf fail-closed mit
  einem eindeutigen Fehler statt mit einem stillen `"default"`-Rückgriff.
- [ ] Test 9 (`tests/test_inbound_reader_no_default_settings_lookup.py`, neu): GIVEN ein Poll-Zyklus
  von `InboundEmailReader.poll_and_process(settings)` mit zwei verschiedenen echten Testkonten
  `nutzer_a` und `nutzer_b`, WHEN je eine eingehende Befehls-Mail von beiden Konten verarbeitet
  wird, THEN sendet der Reader die Bestätigung an das jeweils richtige Konto, ohne dass
  `Settings().with_user_profile(...)` je für ein drittes/nicht angefragtes Konto aufgerufen wird.
- [ ] Test 10 (`tests/test_inbound_reader_no_default_settings_lookup.py`, neu): GIVEN dieselbe
  Prüfung für `InboundTelegramReader.poll_and_process(settings)`, WHEN eine Nachricht von einem
  verknüpften Chat verarbeitet wird, THEN läuft die Bestätigung über das übergebene `settings` ohne
  zusätzliches `with_user_profile`-Lookup.
- [ ] Test 11 (`tests/test_trip_command_processor_requires_user_id.py`, neu): GIVEN
  `InboundMessage(...)` wird ohne `user_id`-Argument konstruiert, WHEN die Konstruktion ausgeführt
  wird, THEN wirft sie `TypeError`.
- [ ] Test 12 (`tests/test_weather_validation_requires_user_id.py`, neu): GIVEN
  `tools/weather_validation.py` wird ohne `--user-id` aufgerufen, WHEN das Skript startet, THEN
  bricht `argparse` mit Exit-Code ≠ 0 ab, bevor irgendein Trip gelesen wird; mit `--user-id nutzer_a`
  liest das Skript ausschließlich die Trips von `nutzer_a`.
- [ ] Test 13 (AST-Inventar, `tests/test_test_suite_passes_user_id_explicitly.py`, neu,
  `# doc-compliance-test`): GIVEN alle Dateien unter `tests/**/*.py` (inklusive `live`-/
  `email`-markierter, die CI nicht ausführt), WHEN ein AST-Scan nach Aufrufen der 40 betroffenen
  Funktionen/Konstruktoren/`InboundMessage` ohne `user_id`-Argument sucht, THEN findet er keinen
  einzigen verbleibenden Aufruf.
- [ ] Test 14 (vollständiger Kernlauf): GIVEN alle Produktiv- und Testaufrufer sind nachgezogen,
  WHEN `uv run pytest` (Kernschicht, ohne `live`/`email`) läuft, THEN ist der komplette Lauf grün —
  kein durch diese Änderung neu rot gewordener Test, und `inbound_sms_reader.py`-Tests laufen
  unverändert durch (Beleg für „VERIFY, keine Codeänderung").

Alle neuen Tests laufen ohne `Mock()`/`patch()` auf echten Fixture-Verzeichnissen (`tmp_path` +
zwei echte Testkonten, Muster aus Scheibe A), lösen den Prüfling relativ zur eigenen Testdatei auf
und sind nach Verhalten benannt, nicht nach Issue-Nummer. Tests 9/10 sind die geforderte
Zwei-Nutzer-Belegung des datenbewegenden Inbound-Pfads (ADR-0003).

## Acceptance Criteria

- **AC-1:** Given `_SRC_BESTAND` im Wächter-Test ist auf `frozenset()` geleert und alle 40 bisherigen Bestandsstellen sind in `src/` und `api/` auf ein Pflichtargument umgestellt / When der bestehende Wächter-Test `test_ac10_src_bestand_stimmt_exakt_mit_dem_code_ueberein` sowie der bestehende Empfindlichkeitstest `test_ac10_ratsche_schlaegt_in_beide_richtungen_an` laufen / Then ist Ersterer grün, weil keine verbleibende `user_id="default"`-Signatur mehr existiert, und Letzterer bleibt unverändert grün, weil er ausschließlich gegen einen unter `tmp_path` gepflanzten Baum prüft und nicht durch die geleerte Liste überflüssig wird.
- **AC-2:** Given der neue Aufrufstellen-Sammler durchsucht `src/`, `api/` und `tools/` nach dem Literal `"default"` als Nutzerkennung — als Keyword-Argument `user_id="default"` an jedem beliebigen Aufruf, sowie positionell ausschließlich bei Aufrufen der Funktion `with_user_profile` / When ein Test-Baum mit je einer testweise gepflanzten Stelle beider Formen unter `tmp_path` geprüft wird / Then benennt der Wächter genau diese gepflanzten Stellen, während der echte Produktivbaum ohne Fund bleibt.
- **AC-3:** Given ein Dienst wie `TripAlertService`, `NotificationService`, die Funktion `save_trip(trip)` oder `get_snapshots_dir()` wird ohne `user_id`-Argument aufgerufen / When der Aufruf ausgeführt wird / Then scheitert er sofort mit `TypeError` bzw. `ValueError`, bevor irgendein Lese- oder Schreibzugriff unter `users/default/` stattfindet.
- **AC-4:** Given `load_trip` wird mit einem Dict oder einem expliziten Dateipfad aufgerufen (kein `data_dir`-Zugriff, wie im heutigen Legacy-CLI-Pfad `python -m src.app.cli`) / When der Aufruf ohne `user_id` erfolgt / Then gelingt das Laden unverändert; wird `load_trip` dagegen mit `data_dir` aufgerufen und fehlt `user_id`, wirft die Funktion `ValueError`.
- **AC-5:** Given `NotificationService` wird weder mit `settings` noch mit `user_id` konstruiert / When der Konstruktor ausgeführt wird / Then wirft er `ValueError`; wird stattdessen eine Operation aufgerufen, die die interne Nutzerkennung braucht, ohne dass diese je gesetzt wurde, scheitert auch dieser Aufruf mit einem eindeutigen Fehler statt eines stillen Rückgriffs auf `"default"`.
- **AC-6:** Given ein Befehl trifft per E-Mail oder Telegram für ein bekanntes Konto ein / When der jeweilige Inbound-Reader die Nachricht verarbeitet und dabei intern einen `NotificationService` aufbaut / Then geschieht das ausschließlich mit dem bereits vorliegenden `settings`-Objekt des anfragenden Kontos, die Bestätigung geht an genau dieses Konto hinaus, und zu keinem Zeitpunkt wird `Settings().with_user_profile(...)` für ein Nicht-Konto oder `users/default/user.json` aufgerufen.
- **AC-7:** Given `InboundMessage` wird ohne `user_id`-Argument konstruiert / When die Konstruktion versucht wird / Then wirft Python `TypeError`; alle drei Inbound-Reader (E-Mail, Telegram, Premium-SMS) übergeben nach dieser Änderung durchgängig die zuvor aufgelöste Kennung — für den Premium-SMS-Reader ist das bereits heute der Fall und wird durch den Kernlauf nur bestätigt, für E-Mail und Telegram wird es durch diese Änderung hergestellt.
- **AC-8:** Given `tools/weather_validation.py` wird ohne das Argument `--user-id` aufgerufen / When das Skript startet / Then bricht es mit einem `argparse`-Fehler und Exit-Code ungleich 0 ab, bevor irgendein Trip gelesen wird; mit gesetztem `--user-id` liest es ausschließlich die Trips des übergebenen Kontos.
- **AC-9:** Given ein Aufruf einer der 40 betroffenen Funktionen/Konstruktoren mit explizit `user_id="default"` / When dieser Aufruf ausgeführt wird / Then funktioniert er unverändert wie vor dieser Änderung, weil das Konto `default` als bewusst übergebener Wert weiterhin gültig ist (PO-Entscheid aus Scheibe A, nicht erneut vorzulegen).
- **AC-10:** Given alle Dateien unter `tests/**/*.py`, einschließlich derer, die mit `live` oder `email` markiert sind und die CI regulär nicht ausführt / When ein AST-Inventar nach Aufrufen der 40 betroffenen Funktionen/Konstruktoren/`InboundMessage` ohne `user_id`-Argument sucht / Then findet es keinen einzigen verbleibenden Aufruf, und der veraltete Test `test_get_snapshots_dir_default` (prüft das abgeschaffte Rückfallverhalten) existiert nicht mehr.
- **AC-11:** Given der vollständige Kern-Testlauf (alle Testdateien ohne `live`/`email`/`staging`-Marker, gate-konform aufgerufen) nach Abschluss aller Änderungen dieser Scheibe / When der Lauf ausgeführt wird / Then ist er zu 100 % grün, ohne dass ein Test wegen dieser Änderung neu rot geworden ist.
- **AC-12:** Given der produktive Scheduler-Versand eines Trip-Briefings auf Staging / When ein Testversand nach dieser Änderung ausgelöst wird / Then kommt die Mail zugestellt an, und `briefing_mail_validator.py` sowie die Vorschau-Endpunkte (`/api/preview/...`) antworten unverändert mit Exit 0 bzw. HTTP 200.

## Known Limitations

- `scripts/cleanup_1265_prod_testdata.py` behält den fest verdrahteten Wert `users/"default"` —
  einmaliges Aufräum-Script außerhalb des Produktivpfads, kein ADR-0003-Risiko, bewusst außerhalb
  des Scopes (siehe Scope, Out of Scope).
- Die verschluckten Store-Fehler in `internal/handler/cockpit.go`/`archive_stats.go` (Go, bereits in
  Scheibe B dokumentiert) werden hier nicht behoben — Nacharbeit im Sammel-Issue #1199, betrifft
  eine andere Sprache/Schicht als diese Scheibe.
- Reicht das LoC-Budget (500 mit Override) nicht für alle 17 Quell-/Tool-Dateien plus alle
  81 Testdateien in einem Workflow, wird entlang der in Implementation Details beschriebenen
  Funktionsgruppen (loader+tools → trip_command_processor+InboundMessage → übrige
  Services/NotificationService) in einen oder mehrere Folge-Workflows geschnitten; die Ratsche
  `_SRC_BESTAND` bleibt bis zum letzten Teil-Workflow entsprechend teilbefüllt.
- Der Aufrufstellen-Wächter (AC-2) prüft das Literal `"default"` als `user_id`-Keyword überall,
  positionell aber ausschließlich bei `with_user_profile` — eine neue Funktion mit rein
  positionellem `user_id`-Parameter, die künftig mit `"default"` aufgerufen würde, fängt der
  Wächter nicht automatisch. Das ist eine bewusste Scope-Grenze (Entscheidbarkeit ohne
  Signaturauflösung geht vor Vollständigkeit), keine Lücke im Sinne von #2151, weil im
  Produktivcode nach Umsetzung dieser Scheibe alle Aufrufer ausschließlich per Keyword übergeben
  (siehe Aufrufer-Karte in der Analyse).

## Regel-Budget

Die Wächter-Erweiterung aus Punkt 4 der Implementation Details (Aufrufstellen-Prüfung, AC-2)
ersetzt keine bestehende Regel — sie ist eine notwendige Erweiterung des in Scheibe A eingeführten
Wächters, ohne den der in dieser Scheibe entfernte Signatur-Rückfall einfach an die Aufrufstelle
verschoben werden könnte. Prüfdatum analog zur Ursprungsregel aus Scheibe A: **2026-12-18** — kein
nachweisbarer Fang bis dahin ⇒ Rückbau prüfen (Tabelle: `docs/reference/gates_und_ratschen.md`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Multi-Tenant-Isolation, bestehend)
- **Rationale:** Diese Scheibe schließt die letzte Python-seitige Lücke aus #2151 und setzt ADR-0003
  konsequent um: kein automatischer Rückfall auf eine implizite Kennung bei fehlender Identität,
  weder in der Funktionssignatur noch (neu, AC-2) an der Aufrufstelle. Sie widerspricht nicht dem
  PO-Entscheid aus Scheibe A, dass `"default"` als expliziter, bewusst vergebener Kontoname gültig
  bleibt (AC-9) — hier geht es ausschließlich um den stillen, unbeabsichtigten Rückfall. Kein neues
  ADR nötig, keine Abweichung von Scheibe A/B.

## Changelog

- 2026-09-19: Initial spec created (Scheibe C von #2151, Analyse aus
  `docs/context/fix-2151-c-python-signatur-defaults.md`; Vorgänger Scheibe A `PR #2365`, Scheibe B
  `PR #2372`)
- 2026-09-19: Implementiert. Adversary-Verdict **VERIFIED** — 8 von 8 Mutationen gefangen. Nebenbefund
  ohne eigenes Issue (Sammel-Issue **#1199**): `tools/weather_validation.py:226` — die interne
  Helper-Funktion `_get_target_date` führt in ihrer Signatur weiterhin einen Parameter, der nicht an
  den neuen Pflicht-`user_id`-Fluss der fünf Aufrufstellen gekoppelt ist; kein nutzersichtbares
  Fehlverhalten, kein Datenverlust-/Sicherheitsrisiko, daher nur Sammel-Eintrag statt eigenes
  Ticket.
