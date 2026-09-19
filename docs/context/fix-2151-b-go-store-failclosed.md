# Context: fix-2151-b-go-store-failclosed

## Request Summary
Issue #2151, Scheibe B (Go). Der Go-Server soll nie still auf das Konto `default` zurückfallen:
- Der Config-Default `UserID="default"` entfällt.
- Der Basis-Store verweigert nutzerbezogene Pfade bei leerer Kennung (fail-closed).
- Das Seed-Konto entsteht nur noch bei explizit gesetztem `GZ_USER_ID`.

Das Konto `default` bleibt als Bestandskonto gültig (PO-Entscheid aus Scheibe A). Vorgänger-Plan:
`docs/context/fix-2151-default-fallbacks-entfernen.md` (Abschnitt Analysis/Scheibenschnitt).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/config/config.go:31` | `UserID envconfig:"USER_ID" default:"default"` — Default fällt |
| `cmd/server/main.go:62` | Basis-Store `store.New(cfg.DataDir, cfg.UserID)` → Scheduler + Router |
| `cmd/server/main.go:73-89` | Seed: `UserExists(cfg.UserID)` + `SaveUser` (**Rückgabewert ignoriert**), Log „Seed user '…' created" auch bei Fehlschlag |
| `internal/store/store.go:14-28` | `WithUser("")` = No-Op (bleibt; Kommentar nachziehen) |
| `internal/store/location.go:14` | `LocationsDir()` exportiert, kein error |
| `internal/store/metric_preset.go:14,130` | `PresetsFile()` exportiert, kein error; `SaveMetricPresets` |
| `internal/store/briefing_subscription.go:19,25` | `briefingsDir()`/`BriefingsDir()` kein error |
| `internal/store/group.go:14,134` | `groupsFile()` kein error; `saveGroups` |
| `internal/store/log.go:23,63` | `LoadBriefingLog`/`LoadAlertLog` bauen Pfad aus `s.UserID` |
| `internal/store/briefing_lock.go:30-33` | `LockBriefing` — Sperrschlüssel `s.UserID+"\x00"+id` (kein Pfad) |
| `internal/store/trip.go`, `compare_preset.go`, `briefing_fingerprint.go` | abgeleitete Pfade über die Helfer |
| `internal/handler/cockpit.go:21-22`, `archive_stats.go:21-22` | verschlucken Store-Fehler (`_`) — nur mit Auth erreichbar |
| `cmd/migrate2154/main.go:19` | `store.New(*dataDir, "default")` — Kennung für Pfad bedeutungslos (nur ListUserIDs/LoadUser/SaveUser) |
| `internal/config/config_test.go:28-29` | erwartet `"default"` → bricht sicher |
| `internal/handler/data_export_test.go:103-113, 403-409` | Begründung nimmt Config-Default `"default"` an (Code explizit, bricht nicht) |
| `frontend/e2e/ci-stack.sh:66` | einzige Stelle, die `GZ_USER_ID` setzt (`admin`), aus `ci.yml:372` |

## Existing Patterns
- Nutzerbezogene Handler: `s := s.WithUser(middleware.UserIDFromContext(r.Context()))`. Alle Produktiv-Aufrufer der Methoden mit `s.UserID`-Pfad liegen dahinter (Liste in Explore-Befund: group/location/trip/compare_preset/briefing_subscription/weather_config/metric_preset/cockpit/archive_stats/briefing_history).
- Kennung als Parameter statt `s.UserID` (user.go, sessions.go, address_owner.go, pending_briefings.go …) mit `ValidUserID(param)` — lehnt `""` ab (`ErrInvalidUserID`). Diese Methoden laufen auch mit Basis-UserID `""`.
- Leer-Prüfung mit 401 in `briefing_history.go:18`, `data_export.go:28`.

## Dependencies
- **Upstream:** `middleware.UserIDFromContext`, `store.ValidUserID` (`pathsafe.go`), envconfig.
- **Downstream:**
  - Scheduler: bekommt den Basis-Store, ruft nie `WithUser`. Er nutzt nur `ListUserIDs`, `LoadUser(uid)`, `LoadPendingBriefingsForUser(DataDir, uid)` und `DataDir`; uid stammt aus Verzeichnisnamen → **unberührt**.
  - Öffentliche Routen (`auth.go:41-59`): keine ruft eine Methode mit `s.UserID`-Pfad.

## Existing Specs
- `docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md:125-130` — dokumentiert `WithUser("")` als No-Op (bleibt so)
- `docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md`
- `docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md:43` — Scheibe B als Folgearbeit
- ADR-0003 (kein `default`-Rückfall)

## Risks & Considerations
- **Seed auf Prod/Staging (Hauptrisiko):**
  - Prod/Staging setzen `GZ_AUTH_PASS` (operations_playbook.md:155), aber nicht `GZ_USER_ID`.
  - Fällt nur der Default weg, liefe `SaveUser(ID:"")` in `ErrInvalidUserID`, der Fehler würde verschluckt und „Seed user '' created" geloggt.
  - ⇒ Der Seed-Block muss an `cfg.UserID != ""` hängen, und der `SaveUser`-Fehler muss behandelt werden.
  - Das Bestandskonto `default` liegt schon auf der Platte und bleibt unberührt.
- **Umgebungsdateien der Server nicht im Repo:** Ob Prod/Staging `GZ_USER_ID` doch setzen, ist nur auf dem Server messbar (`/home/hem/gregor_zwanzig_staging/.env`, Prod-Env). Das Verhalten ist in beiden Fällen korrekt, nur der Seed-Log unterscheidet sich.
- **Helfer ohne error-Rückgabe:**
  - `LocationsDir`/`PresetsFile`/`BriefingsDir`/`groupsFile` würden bei `""` über `filepath.Join` still `data/users/locations` o.ä. bauen.
  - Produktiv werden sie außerhalb des Stores nie aufgerufen, in 9 Handler-Testdateien aber schon. Eine Signaturänderung erzeugt Test-Fan-out.
  - Alternative: Die Leer-Prüfung liegt in den error-liefernden Aufrufern, die Helfer bleiben unverändert.
- **`LockBriefing`:** Bei leerer Kennung teilen sich alle denselben Schlüssel. Das ist unkritisch, weil kein Pfad entsteht und es produktiv nur hinter `WithUser` aufgerufen wird. Bewusst entscheiden, ob auch hier eine Sperre nötig ist.
- **Verschluckte Fehler** in cockpit/archive_stats: Mit fail-closed Store würde ein künftiger Aufruf ohne Auth still leere Daten zeigen statt 500/401. Das ist heute nicht erreichbar (Auth-Pflicht).
- **Tests:** `config_test.go:28` bricht. 26 Testdateien nutzen `New(…,"default")` explizit und bleiben grün. 7 Tests mit `store.New(cfg.DataDir, cfg.UserID)` arbeiten mit eigenen Nutzern und sollten grün bleiben (verifizieren).
- `cmd/migrate2154` nutzt `"default"` hart. Das ist fachlich harmlos (Einmal-Migration, Kennung ungenutzt), bewusst stehen lassen oder auf `""` umstellen.
- Kommentare, die das alte Verhalten beschreiben: `data_export.go:19-24`, `premium_sms_link_code.go:13`, `premium_sms_connect.go:28`, `preview_proxy.go:24`, `user.go:309`, `store.go:14-20`.

## Analysis

### Type
Bug (Mandantentrennung, ADR-0003) — Verteidigungslinie; kein heute erreichbarer Produktivpfad liest/schreibt über den Basis-Store ins Konto `default`. Echte Betriebsfalle: Seed-Block (siehe Risiken).

### Technical Approach (Tech-Lead-Entscheid)
1. **Zentrale Prüfung `func (s *Store) requireUser() error`** (`ValidUserID(s.UserID)` sonst `ErrInvalidUserID`, pathsafe.go:20/26) als erste Zeile jeder error-liefernden Methode, die einen Pfad aus `s.UserID` baut. Die Helfer ohne error (`LocationsDir`, `PresetsFile`, `BriefingsDir`/`briefingsDir`, `groupsFile`) bleiben unverändert.
   **Warum nicht Helfer-Signaturen ändern:** `LoadLocations` (location.go:21-27), `LoadTrips` (trip.go:118-121), `LoadComparePresets` (compare_preset.go:92-95) schlucken `ReadDir`-Fehler und liefern „leer, nil" — ein Fehler im Helfer käme beim Aufrufer als „noch keine Daten" an. `BriefingCountByTrip`/`AlertCountByEntity` (log.go:97-121) schlucken den Fehler ihres Load-Aufrufs ein zweites Mal → brauchen eigenen Guard.
2. **Wächter gegen künftige Methoden:** Reflection-Register im Store-Paket. Jede exportierte Methode von `*Store` muss entweder als „guarded" (Aufruf auf `New(dir, "")` liefert Fehler, UND es entsteht keine Datei unter `dir/users/` außerhalb eines Nutzerordners) oder als „exempt" (mit Begründung: explizite Kennung als Parameter / kein Pfad) eingetragen sein. Neue Methode ohne Eintrag → Test rot. „Guarded" = jede exportierte Methode, die direkt ODER transitiv einen Pfad aus `s.UserID` baut — jede muss **einzeln** fehlschlagen; damit wird die Annahme „Schreibpfade (`SaveGroup`, `DeleteGroup`, `SaveComparePresets` …) sind über den Load-Guard mitgedeckt" gemessen statt behauptet.
   **Dokumentierter Rest:** `LocationsDir`/`PresetsFile`/`BriefingsDir` sind exportiert, bauen aus `s.UserID` und liefern keinen Fehler → nur „exempt" möglich. Produktiv außerhalb des Stores nie aufgerufen (nur 9 Handler-Testdateien). Bewusst nicht umgebaut.
3. **Seed:** `seedAdminUser(s, cfg)` aus `main()` extrahieren (Vorbild `installGuards`, main.go:34-37). Seed nur bei `cfg.UserID != ""` (zuerst geprüft) und `AuthPass != ""` und Konto fehlt. `SaveUser`-Fehler wird geloggt („failed: …"), kein Fail-fast; „created" nur bei Erfolg. Bestandskonto `users/default/` bleibt unberührt.
4. **Config:** `default:"default"` am `UserID`-Feld entfällt.
5. **Nicht angefasst:** `WithUser("")` bleibt No-Op (Prämisse aus `fix_2140_pfad_traversal_nutzer_kennung.md:125-130` ändert sich nur darin, dass die Basis-Kennung jetzt leer ist — Satz in der Spec ergänzen); `LockBriefing` (kein Pfad, immer vor guardeter Methode); `cmd/migrate2154` (Kennung ungenutzt); verschluckte Fehler in `cockpit.go`/`archive_stats.go` (nur mit Auth erreichbar → Sammel-Issue #1199).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/pathsafe.go` | MODIFY | `requireUser()` |
| `internal/store/location.go`, `metric_preset.go`, `group.go`, `briefing_subscription.go`, `trip.go`, `compare_preset.go`, `briefing_fingerprint.go`, `log.go` | MODIFY | Guard am Methodenanfang (~21 Stellen) |
| `internal/store/store.go`, `user.go:308-309` | MODIFY | Kommentare nachziehen |
| `internal/config/config.go` | MODIFY | Default entfernen |
| `cmd/server/main.go` | MODIFY | `seedAdminUser` extrahieren + Logik |
| `internal/handler/data_export.go:19-24`, `data_export_test.go:403-408` | MODIFY | Kommentare (Begründung nennt Config-Default) |
| `internal/config/config_test.go:28-29` | MODIFY | erwartet leer statt `default` |
| `internal/store/user_scope_guard_test.go` | CREATE | Reflection-Register-Wächter |
| `cmd/server/main_test.go` | MODIFY | Seed-Tests |

### Scope Assessment
- Files: ~16 · Estimated LoC: +245–275 (Prod ~110, Tests ~140) → `loc_limit_override 500` gesetzt, Wächter wird NICHT verschlankt.
- Risk Level: MEDIUM — Scheduler/öffentliche Routen/Startpfad verifiziert unberührt (nur `ListUserIDs`/`LoadUser(uid)`/`DataDir`); 7 Tests mit `store.New(cfg.DataDir, cfg.UserID)` rufen keine guardete Methode auf dem Basis-Store.

### Dependencies
Upstream `ValidUserID`/`ErrInvalidUserID`; Downstream alle Handler hinter `WithUser(UserIDFromContext)` (erzwungen durch `internal/handler/store_scope_guard_test.go`).

### Open Questions
- keine PO-Fragen; Prod/Staging-Env (`GZ_USER_ID` gesetzt?) wird beim Staging-Nachweis über den Startlog gemessen.
