---
spec_file: docs/specs/modules/auth_haertung_go_2163.md
spec_sha256: e3b84ca1f4f78af90c6aae0193b5b72cca4dea9a542d357445cf8782c45694fe
spec_frozen_sha256: c1e8ba99f1e99f3838c2be2635615139bc06b9522d416742f2ec4b9ac23bf43c
---

# PO-Briefing: feat-2163-s1-auth-haertung-go

- **Spec:** docs/specs/modules/auth_haertung_go_2163.md
- **Issue:** #2163
- **Erstellt:** 2026-10-31

## Was gebaut wird

Anmeldung und Passwort-vergessen verraten nicht mehr per Antwortzeit, ob ein Konto existiert; weitere kleine Sicherheitslücken werden geschlossen.

## Definition of Done

Auf Staging liefern Anmeldung, Passwort-vergessen und Webhooks die erwarteten Antworten, und alle Tests der Spec sind grün.

## Wie geprüft wird

Automatische Tests prüfen Mindestlaufzeiten, Proxy, Zahlen und Webhooks; gleiche Antwortzeit für bekannte und unbekannte Konten wird nicht nachgewiesen.

## Kritische Anmerkungen

- Registrierung verrät weiter, ob Name oder E-Mail vergeben ist; das Ticket verlangte Abhilfe, nur der Tech Lead entschied dagegen.
- Zusatz: Webhook-Geheimnisse für seven.io und Stalwart werden mitumgestellt, stehen nicht im Ticket; abtrennbar.

## Freigabe-Frage

Darf die Registrierung weiterhin melden, dass Benutzername oder E-Mail schon vergeben sind, obwohl das Ticket Abhilfe wollte?

## Ampel

Ampel: rot

## RED-Phase: festgelegte Symbole & Testdateien

Stand: 2026-10-31, HEAD 7b8a62fb7, Produktionscode unverändert. Artefakte:
`docs/artifacts/feat-2163-s1-auth-haertung-go/test-red-output-stufe1.txt` (Assertion-RED),
`docs/artifacts/feat-2163-s1-auth-haertung-go/test-red-output-stufe2.txt` (Build-RED „undefined“).

**Achtung Kompilierfalle:** Seit den Stufe-2-Dateien kompilieren die Testbinaries von `internal/handler`, `internal/router` und `internal/config` erst nach Phase 6 wieder. Die Stufe-1-Tests in diesen Paketen lassen sich bis dahin nicht erneut ausführen; ihr RED-Beleg ist das Stufe-1-Artefakt (vor Anlage der Stufe-2-Dateien gelaufen). `internal/scheduler` ist nicht betroffen.

Gegenprobe: Alle neuen Tests wurden in einer Wegwerf-Kopie außerhalb des Worktrees gegen eine Minimalumsetzung nach den Signaturen unten grün gefahren. Damit ist belegt, dass sie bestehbar sind.

### Festgelegte Symbole / Signaturen

| Bereich | Symbol | Bindung |
|---|---|---|
| Timing (AC-10) | `func dummyPasswordHash() []byte` in package `handler`, unexportiert; per `sync.Once` einmal erzeugt, Cost `bcrypt.DefaultCost` | test-bindend (`auth_dummy_hash_test.go`) |
| Config (AC-15/16) | `TelegramWebhookSecret`, `TelegramBotUsername`, `SevenWebhookPathSecret`, `SevenWebhookSigningKey`, `StalwartWebhookPathSecret`, `StalwartWebhookSecret` in `config.Config`, je `string`, Tag `envconfig:"<UNPRÄFIXIERTER_NAME>" default:""` (z. B. `envconfig:"TELEGRAM_WEBHOOK_SECRET"`) | test-bindend (Feldnamen + Env-Namen) |
| Scheduler (AC-14) | **kein neues Symbol.** `Start()` berechnet die Zahlen aus `s.cron.Entries()` und je Eintrag `entryJobsLocked` (Teiljobs zählen einzeln, Eintrag ohne Meta zählt 1), Format bleibt `[scheduler] Started: %d cron entries (%d jobs), timezone %s` | test-bindend (Logformat; Test liest Zeile per Regex) |
| Handler-Signaturen (Punkt 7) | Vorschlag: `TelegramWebhookHandler(pythonCoreURL, secret string)`, `InboundSMSWebhook(sched, publicHost, pathSecret, signingKey string, now func() time.Time)`, `InboundMailWebhook(sched, pathSecret, bearer string)`, `GetTelegramLinkHandler(s, ts, botUsername string)`; kein `os.Getenv` mehr in diesen Handlern | **nicht** test-bindend (Route-Tests laufen nur über `router.New`) |
| Proxy (Punkt 8) | Vorschlag: Helfer `stripUserIDQuery(raw string) string` in `proxy.go`, nur in `ProxyHandler` | nicht test-bindend |

**Weg der Config-Werte in den Router:** `router.New(Deps)` bekommt `deps.Config *config.Config` schon heute. Der Router reicht beim Aufbau `deps.Config.TelegramWebhookSecret` usw. als Parameter an die Handler-Konstruktoren durch. Gelesen wird einmal bei `config.Load()` (`GZ_<NAME>` vor `<NAME>`), nicht pro Anfrage. Ein leerer Wert ergibt 503 (fail-closed), beim Telegram-Link wie bisher 500.

**Proxy-Regel:** Die Roh-Query wird an `&` getrennt. Entfernt wird ein Segment genau dann, wenn sein Schlüssel (Teil vor dem ersten `=`, auch ohne `=`) nach `url.QueryUnescape` exakt `user_id` ist. Damit fallen auch `user_id`, `user_id=` und `user%5Fid=x` weg. Groß/Klein: Nur der exakte Schlüssel zählt, `USER_ID=x` und `Userid=x` bleiben stehen. Ohne Treffer geht die Roh-Query byte-identisch weiter. Bleibt nach dem Entfernen nichts übrig, wird kein `?` angehängt. Kein `Encode()`, kein Umsortieren.

**Diskriminator Route-Tests (AC-17/18), bewusste Auslegung von „ohne os.Setenv“:** Die richtigen Werte kommen ausschließlich aus dem Config-Feld, das nach `config.Load()` gesetzt wird. In die Umgebung werden per `t.Setenv` nur falsche Köder-Werte gelegt (unpräfixiert und `GZ_`). Erwartet wird: Köder-Wert ergibt 403, leeres Config-Feld ergibt trotz Köder 503. So fällt ein Handler auf, der noch `os.Getenv` liest. Ein Test, der nur die Umgebung leert, würde diese Mutation nicht fangen.

### Testdateien und Stand heute

| Datei | Testfunktion | AC | heute |
|---|---|---|---|
| `internal/handler/auth_timing_test.go` | `TestLoginNichtTreffer_BrauchtMindestensBcryptLaufzeit_AC2_bis_AC5` (5 Fälle: `../x`, kaputte user.json, unbekannt, ohne Hash, Hash `"kaputt"`) | AC-2..5 | **rot** (gemessen 5–20 µs < 20 ms) |
| | `TestForgotNichtTreffer_BrauchtMindestensBcryptLaufzeit_AC6_AC7` | AC-6/7 | **rot** (3–5 µs) |
| | `TestLoginNichtTreffer_AntwortByteGleich_AC8` | AC-8 | grün: Charakterisierung, Werte am Code gemessen (401, `{"error":"invalid credentials"}` ohne `\n`, Header nur `Content-Type: application/json`, kein Cookie) |
| | `TestForgotNichtTreffer_AntwortByteGleich_AC8` | AC-8 | grün: Charakterisierung (200, `{"status":"ok"}`, Header nur Content-Type) |
| | `TestForgotUnbekannterNutzer_KeinTokenKeinNutzer_AC7` | AC-7 (kein Versand) | grün: Wächter. Kein `password_reset.json`, auch nicht außerhalb des Baums (Muster #2140), kein Nutzer angelegt |
| | `TestLoginErfolgspfadUnveraendert_FalschesPasswort401_AC9` | AC-9 | grün: Charakterisierung (DefaultCost-Hash, 200 + `gz_session` HttpOnly; falsches Passwort 401 byte-gleich) |
| `internal/handler/register_conflict_characterization_test.go` | `TestRegisterKonto_VergebenerNameUndEmail_409Unveraendert_AC1`, `TestRegisterPasskeyBegin_VergebenerNameUndEmail_409Unveraendert_AC1` | AC-1 | grün: Charakterisierung (`user already exists`/`email_taken` ohne `\n`; Passkey `user_already_exists`/`email_taken` mit `\n`). Passkey-Finish-409 decken bestehende Tests ab (`TestPasskeyRegisterPublicFinish_UsernameRace`, `address_uniqueness_write_paths_test.go`). Der Kommentar an den 409-Stellen ist nur im Review prüfbar (kein Quelltext-Test laut Test-Politik) |
| `internal/handler/proxy_user_id_strip_test.go` | `TestProxyHandler_OhneUserID_QueryByteIdentisch_AC11`, `TestProxyHandler_OhneQuery_KeinFragezeichen_AC11` | AC-11 | grün: Wächter gegen eine `Encode()`-Umsetzung |
| | `TestProxyHandler_UserIDSegmenteEntfernt_RestUnveraendert_AC12` (9 Fälle), `TestProxyHandler_NurUserID_LeereQueryOhneFragezeichen_AC12` | AC-12 | **rot** (user_id kommt beim Core an) |
| `internal/router/proxy_user_id_two_users_test.go` | `TestProxyRouten_ZweiNutzer_FremdeUserIDErreichtCoreNie_AntwortGleich_AC13` (5 Routen × alice↔bob, Core spiegelt die Query in den Body) | AC-13 | **rot** |
| `internal/scheduler/startup_log_counts_test.go` | `TestSchedulerStartlog_NenntRegistrierteEintraegeUndStatuszeilen_AC14` (8/9), `TestSchedulerStartlog_ZusaetzlicheEintraegeAendernZahl_AC14` (+2 Einträge, einer mit 2 Teiljobs, also 10/12, nie zufällig 9/10) | AC-14 | **rot** (Log meldet fest 9/10) |
| `internal/handler/auth_dummy_hash_test.go` | `TestDummyPasswordHash_CostIstDefaultCost_EinmalErzeugt_AC10` | AC-10 | **Build-RED** `undefined: dummyPasswordHash` |
| `internal/config/webhook_secrets_config_test.go` | `TestLoad_WebhookSecrets_UnpraefixiertGelesen_AC15`, `..._GZPraefixHatVorrang_AC15`, `..._NurGZPraefix_AC15`, `..._OhneVariablen_KeinFehlerLeereFelder_AC16` (echtes Unset beider Schreibweisen) | AC-15/16 | **Build-RED** (Felder fehlen) |
| `internal/router/webhook_secrets_config_route_test.go` | `TestTelegramWebhook_SecretAusConfig_Falsch403_Richtig200_Leer503_AC17`, `TestTelegramLink_BotNameAusConfig_AC17`, `TestSevenWebhook_SecretsAusConfig_Falsch403_Richtig200_Leer503_AC18`, `TestStalwartWebhook_SecretsAusConfig_Falsch403_Richtig200_Leer503_AC18` | AC-17/18 | **Build-RED** (Felder fehlen) |

Abtrennbarer Punkt-7-Block: Er besteht genau aus `webhook_secrets_config_test.go` und `webhook_secrets_config_route_test.go`. `auth_dummy_hash_test.go` gehört zum Timing-Block.

### Umzustellende Bestandstests (Phase 6, Developer)

Spec-Zeile 74 korrigiert: Die beiden Route-Tests liegen unter `internal/router/`, nicht unter `internal/handler/`. Grundlage war ein Grep nach allen sechs Variablennamen über `internal/` und `cmd/`.

- `internal/handler/telegram_webhook_test.go`: `TestTelegramWebhookHandler_ValidSecretForwardsAndReturns200`, `TestTelegramWebhookHandler_WrongSecretReturns403NoForward` (`os.Setenv` und direkter Aufruf `TelegramWebhookHandler(url)`)
- `internal/handler/telegram_webhook_secret_test.go`: `TestTelegramWebhookHandler_SecretMatrix`
- `internal/handler/telegram_webhook_secret_forwarding_test.go`: `TestTelegramWebhookForwardsSecretHeaderToPythonCore`
- `internal/handler/inbound_webhooks_test.go`: Helfer `neuerSMSAufbau` (:236-237) und `neuerMailAufbau` (:458-459), dazu `TestSMSWebhook_503_EnvFehlt` (:421) und `TestMailWebhook_503_EnvFehlt` (:533); alle direkten Aufrufe von `InboundSMSWebhook`/`InboundMailWebhook`
- `internal/handler/account_deletion_leftovers_test.go`: `TestTelegramLink_SpeicherfehlerLiefert500StattNieGespeichertemToken` (:668), `TestTelegramLink_LaedtNutzerErstUnterDemMutex` (:826), `TestTelegramLink_HaeltMutexUeberTokenAusgabe` (:885) (`TELEGRAM_BOT_USERNAME` und `GetTelegramLinkHandler`)
- `internal/router/inbound_webhooks_route_test.go`:
  - **`TestInboundWebhooks_SitzungsfreiErreichbar_FalschesSecretIst403` bricht sicher.** Er setzt die Umgebung erst nach `s2Router`, liefert mit Config-Werten also 503 statt 403. In der Gegenprobe bestätigt.
  - `TestInboundWebhooks_EnvFehlt_503StattSitzungsabweisung` bleibt grün, wird aber wirkungslos (leert die Umgebung erst nach dem Aufbau) und gehört umgestellt.
  - `TestInboundWebhooks_SMS_GueltigSigniertDurchEchtenRouter_200UndKick` setzt die Umgebung vor `s2Router` und funktioniert über den unpräfixierten Fallback weiter.
- `internal/router/telegram_webhook_inbound_route_test.go`: `tgRouter` setzt die Umgebung vor `s2Router` und funktioniert über den Fallback weiter. Umstellen auf Config-Wert ist optional, aber konsistent.

**Diese Test-Helfer müssen die Umstellung überleben** (oder in eine gemeinsame `_test.go` wandern), sonst kompilieren die neuen Tests nicht:
- `tgPost` und `tgHeader` (`telegram_webhook_inbound_route_test.go`)
- `sevenSignaturUnabhaengig` (`inbound_webhooks_route_test.go`)
- `sessionIDFor` und `sessionCookieFor` (`briefing_subscription_test.go`)
- `s2Router`, `s2Optionen` und `s2Token` (`status_token_test.go`)
- `findFilesOutsideUsersTree` (`internal/handler/auth_traversal_test.go`) und `newTestStore`
- `syncWriter` (`internal/scheduler/disabled_users_filter_test.go`) und `testStore`

**Falle aus der Gegenprobe:** Die Secrets gehen beim Bau des Handlers hinein. Der `nonceCache` von `InboundSMSWebhook` muss je Handler-Instanz bestehen bleiben und darf nie je Anfrage neu entstehen. Ein Wrapper, der den Handler pro Anfrage neu baut, schaltet den Replay-Schutz ab; `TestSMSWebhook_Abgewiesen_WiederverwendeteNonce` wird dann rot.

**Hinweis AC-5:** Einen eigenen Zweig für leeren oder kaputten Hash gibt es heute nicht, `CompareHashAndPassword` scheitert dort sofort. Zwei Umsetzungen sind möglich:
- vorher mit `bcrypt.Cost` prüfen (so in der Gegenprobe gemacht), oder
- den Dummy-Vergleich ausführen, sobald der Fehler nicht `ErrMismatchedHashAndPassword` ist.
