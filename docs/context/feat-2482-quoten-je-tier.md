# Context: feat-2482-quoten-je-tier

## Request Summary
S5 von #2153 (Epic #2138): Obergrenzen je Tier (free/standard/premium) für die Anzahl an Trips, Ortsvergleichen, Orten und „Empfängerkanälen". Überschreitung beim **Neuanlegen** → Fehlerantwort, Bestand bleibt unangetastet. Zwei-Nutzer-Test Pflicht.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/tier.go` | `EffectiveTier()` (:35, fail-closed auf `free`), `SmsAllowed`/`PremiumSmsAllowed` — naheliegende Ablage für Quoten-Tabelle |
| `internal/model/user.go:22` | `Tier`-Feld, `RequestedTier`, `Disabled` |
| `internal/store/user.go:53` | `LoadUser` (ungescopter Store) — Tier-Lookup-Muster wie `sms_verify.go:211-225` |
| `internal/handler/trip.go:158` | `CreateTripHandler` — Client-ID, **upsert ohne Existenzprüfung** → Quote nur zählen, wenn `LoadTrip(id)==nil` |
| `internal/handler/compare_preset.go:193` | `CreateComparePresetHandler` — Server-ID, jeder POST = Neuanlage |
| `internal/handler/location.go:63` | `CreateLocationHandler` — ID aus Namen, 409 `conflict` bei Dublette |
| `internal/handler/briefing_subscription.go:131` | `POST /api/briefings` delegiert an Trip-/Preset-Create → Prüfung MUSS in den Create-Handlern liegen |
| `internal/store/trip.go:127`, `compare_preset.go:121`, `location.go:18` | Zähl-Quellen `LoadTrips`/`LoadComparePresets`/`LoadLocations` (Trips inkl. archivierter) |
| `internal/handler/group.go:36`, `metric_preset.go:138` | weitere Create-Pfade (Gruppen, Metrik-Presets) — Scope-Frage |
| `src/services/user_tier.py` | Python-Tier-Tabellen (`_DAILY_SMS_LIMIT` …) |
| `frontend/src/lib/api.ts:137-141` | wirft `{error, detail, status}`; Anlege-UIs zeigen `detail ?? error` (TripNewEditor :448, compareWizardState :184, locations/+page :54, LocationNewModal :71, Step2Orte, gpx-upload) |
| `frontend/src/routes/account/+page.svelte:1083-1112` | „x von N"-Zähleranzeige aus S4; `+page.server.ts:21` lädt Trips/Presets/Orte bereits |
| `internal/handler/admin_users.go:107` | Admin setzt Tier (#2155) |

## Existing Patterns
- Tier-Gate in Go: `LoadUser` → `model.EffectiveTier(user.Tier)` → Fehler-JSON `{"error":code}` (z. B. `sms_not_allowed`).
- Fehler-Body-Konvention: `{"error": code, "detail": text}`; kein zentraler Helper. Deutscher `detail` erscheint ohne Frontend-Änderung in allen Anlege-UIs.
- Statuscodes in Gebrauch: 409 `conflict`/`name_exists`, 412, 429 `rate_limit_exceeded`, 400 `validation_error`.
- S4 (#2412): Tier-Limit-Tabelle in Python, Go proxyt; Anzeige „x von N" auf `/account`.
- Zwei-Nutzer-Tests: `internal/handler/user_scoped_test.go:23-40` (`addUserToContext`, alice/bob in tmpDir); Tier-Fixtures in `auth_tier_change_test.go`, `sms_verification_test.go`.

## Dependencies
- Upstream: Store (`WithUser`, `LoadUser`), `model.EffectiveTier`.
- Downstream: Trip-Anlegen (`/trips/new`, GPX-Upload), Compare-Anlegen (Wizard), Orte-Anlegen (Liste, Modal, Wizard-Schritt), `POST /api/briefings`, Konto-Seite.

## Existing Specs
- `docs/specs/modules/epic_user_tiers_overview.md` — Tier-Tabelle (:25-46), noch ohne Mengengrenzen
- `docs/specs/modules/sms_daily_limit.md`, `sms_daily_usage_anzeige.md` (S4)
- `docs/specs/modules/sms_nummer_verifikation.md` (S3), `docs/specs/bugfix/profile_mail_ratelimit.md` (S2)
- ADRs: 0003 (Mandantentrennung), 0015 (Domänenlogik → Python), 0031 (Persistenz), 0075/0076 (Kontingent-Entscheidung in Python), 0078 (Admin)

## Risks & Considerations
- **„Empfängerkanäle" existieren nicht als zählbare Liste:** Profil hat genau eine Adresse je Kanal (MailTo, SmsTo, TelegramChatID, PremiumSmsReplyTo); `ComparePreset.Empfaenger` ist inert (#1452). → Teilaspekt vermutlich gegenstandslos; Kanal-Zugang ist bereits per Tier-Gate geregelt. In Analyse/Spec klären, nicht stillschweigend weglassen.
- **Trip-Upsert:** POST mit bestehender ID überschreibt — Quote darf Bearbeiten/erneutes Speichern bestehender Trips nicht blockieren.
- **Archivierte Trips:** zählen sie mit? Produktentscheidung (Vorschlag: nein, sonst sperrt Archiv die Neuanlage; Scheduler-Last entsteht nur durch aktive).
- **Bestand über Grenze:** Nutzer behalten alles, nur Neuanlage blockiert; Bearbeiten/Archivieren/Löschen bleiben frei.
- **Grenzwerte unbelegt:** Prod-Bestände (`/var/lib/gregor`) für `hem` nicht lesbar → Zahlen als Vorschlag in die Spec, PO entscheidet; Admin-Nutzer/PO selbst darf nicht ausgesperrt werden (PO-Konto Tier prüfen).
- **ADR-Abwägung:** 0075/0076 legen Kontingente nach Python; Mengen-Quoten betreffen aber Go-Store-eigene Entitäten → Prüfung in Go ist begründbar, als Abwägung in Spec dokumentieren (ggf. ADR).
- **Race:** zwei parallele POSTs können Grenze um 1 überschreiten — Akzeptabel oder Store-Lock? In Analyse bewerten.
- Gruppen/Metrik-Presets: nicht im Issue-Auftrag; Scope-Entscheidung in der Analyse.

## Analysis

### Type
Feature (S5 von #2153, Epic #2138)

### Verifizierte Befunde
- **Neuanlage läuft ausschließlich über drei Go-Handler:** `CreateTripHandler` (`internal/handler/trip.go:158`), `CreateComparePresetHandler` (`compare_preset.go:193`), `CreateLocationHandler` (`location.go:63`). `POST /api/briefings` (`briefing_subscription.go:131`) delegiert an Trip-/Preset-Create und erbt die Prüfung. Python legt nichts neu an: `trip_command_processor.py` schreibt nur bestehende Trips um (`dataclasses.replace`), `save_location` wird in Python nirgends aufgerufen. Kein Copy/Duplicate/Import-Endpoint. `POST /api/gpx/parse` persistiert nicht.
- **Bearbeiten geht per PUT** (`api.put('/api/trips/{id}')` in TripHeader/TripTabs/BriefingScheduleTab/WaypointsPanel); POST nur aus `TripNewEditor.svelte:445`. POST mit bestehender ID überschreibt heute still (Upsert).
- **Archiv:** Trips und Presets haben `archived_at` (PATCH `.../state`), Orte kein Archiv.
- **ADR-Lage:** ADR-0015 ordnet Persistenz/Mandantentrennung/Rate-Limiting Go zu. ADR-0075/0076 betreffen nur das geteilte Wetter-Kontingent. (Ein Explore-Bericht behauptete „ADR-0015: Mengengrenzen → Python" — **falsch**, im ADR-Text nicht vorhanden.) Mengenquote auf Go-Store-Entitäten gehört nach Go; Python spiegelt die Tabelle nicht (Regel 3).
- **Admin** = `GZ_ADMIN_USER_IDS` (`config.ParseAdminUserIDs`, `router.go:42`), kein Feld in `model.User` → Admin-Menge muss in die Create-Handler durchgereicht werden.
- **Locks:** `store.LockBriefing(id)` (`briefing_lock.go`, Paket-Map mit Refcount je UserID+ID) schützt nicht die Zählung (verschiedene IDs). Kein Per-User-Lock vorhanden.
- **Frontend:** alle Anlege-UIs zeigen `detail ?? error` (api.ts:137, TripNewEditor:449, LocationNewModal:71, locations/+page:103, compareWizardState:191) → deutscher `detail` erscheint ohne UI-Umbau.
- **Fehlercode-Konvention:** `writeJSONError(w,status,code)` (`passkey.go:43`); Tier-Gate `sms_not_allowed` (400); 409 `conflict` bei Orts-Dublette.
- **Testmuster:** `addUserToContext` (`user_scoped_test.go:23`), `newTestStore`/`seedTrip` (`trip_write_test.go:15-19`), `s.SaveUser` für Tier-Fixture.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/tier.go` | MODIFY | Quoten-Tabelle je Tier (`QuotaFor(tier)`: Trips/Presets/Orte) |
| `internal/store/quota_lock.go` (o. ä.) | CREATE | Per-User-Lock (Muster `briefing_lock.go`), Zählen+Speichern atomar |
| `internal/handler/trip.go` | MODIFY | Quote prüfen nur bei echter Neuanlage (ID existiert nicht); aktive (nicht archivierte) zählen |
| `internal/handler/compare_preset.go` | MODIFY | Quote prüfen, aktive zählen |
| `internal/handler/location.go` | MODIFY | Quote prüfen, alle zählen |
| `internal/router/router.go` | MODIFY | Admin-Menge an Create-Handler durchreichen |
| `internal/handler/auth.go` (~`toProfileResponse`) | MODIFY | Grenzen im Profil ausliefern (Admin: unbegrenzt) |
| `frontend/src/routes/account/+page.svelte` | MODIFY | „x von N" für Trips/Vergleiche/Orte |
| `internal/handler/*_quota_test.go` | CREATE | Grenze exakt, Bestand-über-Grenze bearbeitbar, Archiv schafft Platz, Admin frei, Zwei-Nutzer, Race, /api/briefings |
| `docs/specs/modules/epic_user_tiers_overview.md` | MODIFY | Mengengrenzen in Tier-Tabelle |

### Scope Assessment
- Files: ~10
- Estimated LoC: ~+150 Produktion, ~+250 Tests
- Risk Level: MEDIUM

### Technical Approach (Empfehlung)
1. Quoten-Tabelle in Go `model/tier.go`, Eingabe `EffectiveTier` (fail-closed free).
2. Prüfung in den drei Create-Handlern unter Per-User-Quota-Lock (Lock-Reihenfolge: Quota-Lock vor `LockBriefing`).
3. Antwort **409** `{"error":"quota_exceeded","detail":"<deutsch>","resource":…,"limit":N,"current":M}`. 422 ist für Validierung belegt, 403 kollidiert mit Rollen-/Tier-Gates. **Meldungstext sagt „Trip/Trips", nie „Tour"** (Bewertungsvorschlag enthielt „Touren").
4. Zählung: Trips/Presets nur nicht archivierte (Archivieren schafft Platz); Orte alle. Prüfung nur bei Neuanlage (`count >= limit`), nie bei PUT/PATCH/DELETE.
5. Trip-Upsert: Quote gilt nur, wenn ID für diesen Nutzer nicht existiert; POST auf bestehende ID bleibt Upsert (kein Verhaltenswechsel — `global.setup.ts:75-77` macht DELETE+POST, viele E2E-Specs POSTen Trips; ein Wechsel auf 409 `already_exists` wäre eigenes Thema).
6. Admin (`GZ_ADMIN_USER_IDS`) unbegrenzt — PO-Konto nicht aussperrbar.
7. Grenzen im Profil ausliefern, `/account` zeigt „x von N".
8. **Empfängerkanäle: gegenstandslos** — Profil hat genau eine Adresse je Kanal, `ComparePreset.Empfaenger` inert (#1452), Kanal-Zugang schon per Tier (`SmsAllowed`/`PremiumSmsAllowed`). In der Spec explizit begründet ausweisen, nicht still weglassen.

### Grenzwert-Vorschlag (PO-Freigabe in der Spec)
| | free | standard | premium |
|---|---|---|---|
| Trips (aktiv) | 3 | 15 | 50 |
| Ortsvergleiche (aktiv) | 2 | 10 | 30 |
| Orte | 10 | 50 | 200 |
Prod-Bestände für `hem` nicht lesbar → Werte nicht belegbar; Bestand über Grenze bleibt unberührt.

### Risiken
- **CI-/Staging-E2E-Nutzer:** 61 E2E-Specs legen Trips per POST an. Hat der E2E-/Staging-Testnutzer Tier `free` (oder leer → fail-closed free) und wird nicht aufgeräumt, blockiert die Quote die Ampel (`e2e`) bzw. `/e2e-verify`. In der Spec klären: Testnutzer-Tier/Admin-Status im CI-Stack und auf Staging prüfen, ggf. Testnutzer als Admin oder premium führen.
- Archiv-Missbrauch (anlegen+archivieren unbegrenzt) — Rest-Risiko, optional Gesamtdeckel; PO-Entscheidung in Spec.
- Python-`tests/tdd/*` POSTen Trips (teils gegen laufende Server) — vor GREEN prüfen.
- Daten-Schema: keine Persistenz-Änderung (nur Lesen/Zählen) → kein Migrationsbedarf.

### Open Questions (Produktentscheidungen → als Vorschlag in die Spec, PO gibt mit ACs frei)
- [ ] Grenzwerte je Tier (Vorschlag oben)
- [ ] Zählen archivierte Trips/Vergleiche mit? (Vorschlag: nein)
- [ ] Empfängerkanäle als gegenstandslos aus dem Scope (Vorschlag: ja, begründet)

## Hinweise für /50-implement (aus /40-tdd-red, 2026-10-02)

**RED-Tests:** `internal/handler/mengen_quote_test.go` (AC-1..9, 15), `internal/router/mengen_quote_route_test.go` (AC-10, 11, 13 Backend), `internal/model/mengen_quote_test.go` (Tabelle), `internal/config/quota_exempt_test.go` (Env), `frontend/src/lib/utils/mengenQuoteHelpers.test.ts` (AC-13). Beleg: `docs/artifacts/feat-2482-quoten-je-tier/test-red-output.txt`.

**Festgelegte Verträge (aus den Tests):**
- `model.Quota{Trips, ComparePresets, Locations int}`, `model.QuotaFor(tier)` — auch `""`/unbekannt ⇒ free (ohne vorheriges `EffectiveTier`).
- `config.Config.QuotaExemptUserIDs` (`envconfig:"QUOTA_EXEMPT_USER_IDS" default:""`).
- Handler-Signaturen `CreateTripHandler(s)` usw. bleiben in den Handler-Tests UNVERÄNDERT aufrufbar (ohne Policy ⇒ niemand ausgenommen). Admin-/Ausnahme-Menge muss trotzdem im Router ankommen (Router-Test). Umsetzungsweg frei (z. B. variadischer Parameter oder Kontext), aber KEIN Umbau der ~80 bestehenden Aufrufstellen.
- Profil: `"quota": {"trips": N|null, "compare_presets": N|null, "locations": N|null}`, null = unbegrenzt.
- Frontend: `countActive(list)` (ohne `archived_at`), `formatQuotaUsage(count, limit)` ⇒ „x von N“ bzw. „x“.
- Test-Naht `var quotaBeforeSave func()` im Paket `handler` (Muster `profileUpdateBeforeFreshReload`, auth.go): im Betrieb nil, der Quoten-Helfer ruft sie zwischen Zählen und Speichern INNERHALB des Per-User-Locks auf. Der Race-Test (AC-8) setzt sie auf 10 ms Schlaf.
- Gate-Hinweis: `touched_tests_gate.py` hat keine RED-Ausnahme; der Handler-Test ist daher bis `model.QuotaFor`/`quotaBeforeSave` existieren ein Übersetzungsfehler (Verhaltens-Probe im Artefakt angehängt).
- 409-Body: `error`, `detail` (enthält z. B. „3 von 3 Trips“, „Ortsvergleich…“, „Orte“), `resource`, `limit`, `current`.

**Bestandstests, die nach GREEN rot würden:**
- `internal/handler/compare_preset_test.go:647` `TestCreateComparePreset_ValidForecastHours_Accepted` — 3 Presets für `user1` in einem Store ⇒ 3. wird 409. Fix: je Iteration frischer Store/Nutzer.
- `compare_preset_test.go:668` `..._InvalidForecastHours_Rejected` — 7× 400; bleibt nur grün, wenn **Validierung VOR der Quote** läuft (ohnehin Spec-konform: Orts-Dublette `conflict` hat ebenfalls Vorrang).
- `frontend/e2e/ci-stack.sh:63-70`: `GZ_ADMIN_USER_IDS` fehlt ⇒ Seed-Konto `admin` ist free ⇒ `GZ_ADMIN_USER_IDS=admin` ergänzen (Spec AC-14).
- Staging: `GZ_QUOTA_EXEMPT_USER_IDS=default` in der Staging-Env eintragen (Spec AC-14), Prod bleibt leer.
