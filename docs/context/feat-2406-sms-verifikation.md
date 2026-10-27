# Context: feat-2406-sms-verifikation

## Request Summary
Scheibe S3 von #2153 (Epic #2138): Die SMS-Nummer im Profil (`sms_to`) wird heute roh gespeichert und ist sofort wirksam. Künftig: E.164-Formatprüfung beim Speichern und Bestätigungscode per SMS, bevor an eine neue Nummer etwas verschickt wird. Ziel ist, den Versand an fremde Nummern auf Betreiberkosten zu verhindern.

## Related Files

### Go-API
| Datei | Relevanz |
|------|-----------|
| `internal/model/user.go:17` | `SmsTo string`: roher String, keine Verifikationsfelder. `:32` `EmailVerifiedAt`, `:50-51` `PendingContactAddress/Field` sind die Vorlage |
| `internal/model/user.go:66-72` | `EmailVerificationToken{TokenHash, ExpiresAt, Address}` liegt in eigener Datei, nicht auf User. Vorlage für den SMS-Code |
| `internal/model/tier.go:3-10` | `SmsAllowed(tier)`: nur standard/premium |
| `internal/handler/auth.go:853` | `UpdateProfileHandler`. Decode-Struct `:864-874` (`SmsTo *string` `:868`). E-Mail-Pending-Logik `:1010-1066`. **`sms_to` roh übernommen `:1067-1069`.** Limiter-Prüfung `:1098` vor `SaveUser` `:1106` |
| `internal/handler/auth.go:1139-1159` | `issueVerificationToken`: 32 Byte, bcrypt, 24h, adressgebunden. `store.SaveVerificationToken` (`internal/store/user.go:204`, Datei `data/users/<id>/email_verification.json`) |
| `internal/handler/auth.go:523-663` | `VerifyEmailHandler`: Ablauf prüfen, bcrypt, Adress-Lock, Pending befördern, Token löschen |
| `internal/handler/auth.go:774/798/801` | `toProfileResponse`, die **einzige** Go-Stelle, die `SmsTo` liest (plus `sms_allowed`) |
| `internal/handler/profile_mail_ratelimit.go` | `MailFloodLimiter` (#2404) mit Nutzer- und Adress-Bucket, `Allow`/`AllowAddressOnly`/`RetryAfterHeader`. Router `:78` `NewMailFloodLimiter(10, time.Hour)` |
| `internal/handler/premium_sms_link_code.go` | Bestehender **Code-Handshake** (Code erzeugen, bcrypt, prüfen) für Premium-SMS. Nächster Präzedenzfall für einen SMS-Code |
| `internal/handler/staging_verify_token.go:31` | `StagingVerificationTokenHandler`: Staging-Weg, um an einen Token zu kommen (für E2E) |
| `internal/router/router.go` | IP-Limiter je Auth-Route. `/api/notify/test` Proxy `:199`. `PremiumSmsRateLimiter` `:31`, `:105-110` |
| `internal/egress/inventory.go:40` | `gateway.seven.io` nur als Egress-Eintrag. **Go hat keinen seven.io-Client** |

### Python-Core
| Datei | Relevanz |
|------|-----------|
| `src/app/config.py:218, 394-445` | `with_user_profile` liest `user.json` und setzt `sms_to` (`:429`, kein globaler Fallback seit #2144). **Hier greift die Wirkung**: alle SMS-Versände laufen darüber |
| `src/app/config.py:447-453` | `can_send_sms()` braucht Gateway, Key und `sms_to` |
| `src/output/channels/sms.py:41-50` | `_resolve_recipient()` gibt `settings.sms_to` ungeprüft zurück |
| `src/output/channels/seven_io_base.py:108-187` | Transport plus Test-Schutz (Sandbox-Key-Zwang #1336, Code-Herkunft #1476). Maskierung `:36` |
| `src/app/egress_guard.py:51,142` | Host-Guard (TEST_ACCESS), in Prod ohne Wirkung |
| `src/services/user_tier.py:9-42` | Tier-Gates `sms_allowed`/`premium_sms_allowed` |
| `src/services/alert_channels.py`, `compare_alert_channels.py`, `trip_report_scheduler.py:~1726-1779` | Geteilte Kanalauflösung für Alarme, Compare und Trip |
| `src/services/channel_test_service.py:12-44` | `/api/notify/test`, nur E-Mail/Telegram, immer `for_testing()`, also **kein** echter SMS-Versand |
| `src/output/channels/email.py:239-293` | Resend-Allowlist nur für verifizierte Adressen. Konzeptuelles Gegenstück, für SMS fehlt es |

### Frontend
| Datei | Relevanz |
|------|-----------|
| `frontend/src/routes/account/+page.svelte:30, 353-372, 614-625` | Eingabe `sms_to` (`type="tel"`), Speichern per `PUT /api/auth/profile` |
| `frontend/src/routes/account/+page.svelte:587-611` | E-Mail-Pending-Hinweis (`data-testid="pending-address-notice"`) mit Nachversand-Knopf. Vorlage für den SMS-Pending-Zustand |
| `frontend/src/lib/components/shared/wizardHelpers.ts:87-98` | `maskPhone` (nur Anzeige) |
| `versand-tab/channelConnectionStatus.ts:27,60`, `VTBriefingChannels.svelte:90`, `channelContactLabel.ts:30`, `edit/EditReportConfigSection.svelte:119`, `WeatherMetricsTab.svelte:244` | Lesen „SMS hinterlegt" für die Kanal-Anzeige. Müssen „bestätigt" von „nur eingetragen" unterscheiden |

## Existing Patterns
- **Pending-Adresse (E-Mail, #2147 B2):** Ein bestätigtes Konto wird nie auf eine ungeprüfte Adresse umgebogen. Die neue Adresse wartet als Pending-Feld, bis der Bestätigungsschritt sie befördert. Genau dieses Verhalten fordert #2406 für `sms_to`.
- **Token in eigener Datei:** bcrypt-Hash, Ablauf, an die zu beweisende Adresse gebunden, nach Erfolg gelöscht.
- **Code-Handshake (Premium-SMS):** Code erzeugen, bcrypt, prüfen. Schon für SMS-Kontext gebaut.
- **Mengenbremse (#2404):** Nutzer- und Ziel-Bucket, geprüft **vor** `SaveUser` (kein Teilzustand), 429 plus `Retry-After`.
- **Versand nur im Python-Core:** Go versendet nie selbst, sondern ruft Python-Endpunkte. Sandbox-Key-Zwang schützt Staging/Tests.
- **Staging-Hintertür für Tokens:** `StagingVerificationTokenHandler`, damit E2E ohne echtes Postfach läuft.

## Dependencies
- Upstream: seven.io (über `SevenIoChannelBase`), `store.SaveUser`, `MailFloodLimiter`-Bauart, `model.SmsAllowed`.
- Downstream: alle SMS-Versände (Trip-Briefing, Compare-Briefing, Trip-/Compare-/Radar-/Amtliche Alarme) über `with_user_profile` + `can_send_sms()`. Profil-Antwort und Frontend-Kanalanzeige.

## Existing Specs
- `docs/specs/bugfix/profile_mail_ratelimit.md` (#2404)
- `docs/specs/modules/adresswechsel_nach_bestaetigung.md` (#2147 B2, Pending-Muster)
- `docs/specs/modules/egress_guard_sms.md`
- `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` (Code-Handshake)
- `docs/specs/_archive/modules/issue-609-sms-profil-feld.md` (ursprüngliches `sms_to`)
- `docs/specs/_archive/modules/issue_608_sms_seven_io.md`, `issue_1069_tier_channel_gating.md`

## Risks & Considerations
1. **Aussperr-Falle für Bestandsnummern** (wie bei #2271): Heute eingetragene Nummern haben keinen Verifikationsstand. Wird „nur verifizierte Nummer wird beliefert" hart eingeführt, verstummt SMS für jedes bestehende Konto, auch das des PO, mitten in einer Tour. Braucht eine bewusste Übergangsregel (z. B. Bestandsnummern gelten als bestätigt, oder eine einmalige Migration). Prod-Daten unter `/var/lib/gregor` sind aus der Sitzung nicht lesbar.
2. **Wo greift die Sperre?** Speichert Go nur Pending, ist Go der Schutz. Die Zusicherung muss aber dort wirken, wo versendet wird: in `with_user_profile` (`config.py:429`) darf nur eine **bestätigte** Nummer als `sms_to` ankommen, analog zur Resend-Allowlist. Sonst reicht ein direkt editiertes `user.json` oder ein zweiter Schreibweg.
3. **Kein SMS-Versand aus Go:** Der Code muss über einen neuen internen Python-Endpunkt verschickt werden (seven.io-Transport, Sandbox-Schutz und Maskierung bleiben an einer Stelle), oder Go bekommt den ersten eigenen seven.io-Client. Tendenz: Python-Endpunkt, Go erzeugt und prüft den Code.
4. **Die Bestätigungs-SMS kostet selbst Geld.** Mengenbremse je Nutzer **und** je Zielnummer (Bauart #2404) ist Pflicht, sonst verschiebt sich der Missbrauch nur vom Briefing auf den Code. Code-Versand nur für Tiers mit `SmsAllowed`, damit Free-Konten keine SMS auslösen.
5. **Staging kann keinen Code empfangen:** Der Sandbox-Key stellt nie zu. Für E2E braucht es einen Staging-Weg zum Code, analog `StagingVerificationTokenHandler`.
6. **Brute-Force auf den Code:** Kurze Zahlencodes brauchen begrenzte Fehlversuche, kurzen Ablauf und Bindung an die Nummer.
7. **Bestehende Tests** speichern Nicht-E.164-Werte (`"+49151TESTXXXX"` in `profile_test.go:161-275`) und brechen bei einer Formatprüfung. Anpassen, nicht löschen.
8. **Frontend-Kanalanzeige** zeigt heute „SMS hinterlegt". Sie muss „eingetragen, aber unbestätigt" sichtbar machen, sonst glaubt der Nutzer, SMS sei aktiv.
9. **Premium-SMS unberührt:** eigenes Feld `premium_sms_reply_to`, eigener Handshake. Nicht vermischen.
10. **Mandantentrennung:** Zwei-Nutzer-Test Pflicht (B trägt A's Nummer ein, B's Versand bleibt gesperrt, Code geht nur an die Nummer). Kein `"default"`-Fallback.
11. **LoC-Limit 250** wird bei Go + Python + Frontend sehr wahrscheinlich überschritten. In der Analyse Zuschnitt prüfen (z. B. Backend-Sperre + Code-Flow zuerst, Frontend-Anzeige eigene Scheibe) oder `loc_limit_override`.

## Analysis

### Type
Feature (Sicherheitsrisiko, priority:high). Scheibe S3 aus #2153, Epic #2138.

### Verifizierte Vorbilder (per `ls`/`grep` gegen `origin/main` a4943ed5 geprüft)
- Zwei-Stufen-Muster E-Mail: `docs/specs/modules/email_verify_vorbereitung_2304.md` (Backfill + Feld) → `docs/specs/modules/email_verify_scharfschaltung_2271.md` (Sperre scharf). Backfill-Skript `scripts/backfill_2271_email_verified.py` (Dry-Run-Default, `--execute` mit tar.gz-Backup, Read-Modify-Write, idempotent, KEINE Lesepfad-Ausnahme „Feld fehlt ⇒ gilt als bestätigt").
- Selbstheilung nur bei bewiesenem Kanal: `selfHealEmailVerification` (`internal/handler/auth.go:1171`).
- Versand-seitige Sperre E-Mail: `src/output/channels/email.py:294` (`if not profile.get("email_verified_at")`). Für SMS fehlt das Gegenstück (`src/app/config.py:429` übernimmt `sms_to` roh, `can_send_sms()` `:447-453` prüft keine Bestätigung).
- Einziger Schreibweg für `sms_to`: `internal/handler/auth.go:1068`.
- Go↔Python: Header `X-GZ-Core-Auth` (`internal/coreauth/transport.go:27`), Python erzwingt ihn auf `/api/_internal/*` (ADR-0062). Go hat keinen seven.io-Client.
- Code-Erzeugung Premium-SMS: `internal/handler/premium_sms_link_code.go:48-74` (crypto/rand, bcrypt, Datei je Nutzer). Wird dem Nutzer angezeigt, nicht versandt; kein Ablauf-Feld.
- Staging-Weg: `internal/handler/staging_verify_token.go:31`, nur bei `GZ_ENV=staging` registriert (`router.go:87`), anmeldepflichtig.
- Keine E.164-Prüfung im Repo (weder Go noch Python).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/user.go` | MODIFY | Neue Felder (Vorschlag): `SmsVerifiedNumber string` (die bewiesene Nummer, s. Designpunkt 1), `SmsVerifiedAt *time.Time`, `PendingSmsTo string`, alle `omitempty`. Code-Struktur `SmsVerificationCode{CodeHash, ExpiresAt, Number, FailedAttempts}` in eigener Datei. **Schema-relevant** ⇒ Pre-Snapshot-Hook, Read-Modify-Write mit Merge |
| `internal/store/user.go` | MODIFY | Speichern/Laden/Löschen `users/<id>/sms_verification.json` (analog `SaveVerificationToken` `:204`) |
| `internal/handler/auth.go` | MODIFY | `UpdateProfileHandler` `:1067-1069`: E.164-Prüfung (400), Pending statt Sofort-Umbiegen, Code-Versand anstoßen. Mengenbremse vor `SaveUser` |
| `internal/handler/sms_verify.go` | CREATE | Code bestätigen (`POST /api/auth/sms/verify`), Code erneut senden. Fehlversuch-Zähler, Ablauf, Nummernbindung |
| `internal/handler/sms_flood_limiter.go` (oder Wiederverwendung `profile_mail_ratelimit.go`) | CREATE/MODIFY | Bremse je Nutzer + je Zielnummer, 429 + `Retry-After` (Bauart #2404) |
| `internal/handler/staging_sms_code.go` | CREATE | Staging-Weg zum Klartext-Code für E2E (nur `GZ_ENV=staging`, anmeldepflichtig, NICHT unter `/api/debug/`) |
| `internal/router/router.go` | MODIFY | Routen + Limiter registrieren |
| `internal/handler/auth.go` `toProfileResponse` `:774-801` | MODIFY | `sms_verified`, `pending_sms_to` ausliefern |
| `api/routers/…` (neuer interner Router) | CREATE | `POST /api/_internal/sms/verification-code`: sendet eine einzige SMS über `SMSOutput`/`SevenIoChannelBase` (Sandbox-Zwang + Maskierung bleiben dort) |
| `src/app/config.py:429` | MODIFY | **Wirkstelle:** `sms_to` nur übernehmen, wenn `sms_verified_number == sms_to` (und gesetzt). Fail-closed |
| `scripts/backfill_2406_sms_verified.py` | CREATE | Einmal-Skript nach Vorbild `backfill_2271_email_verified.py`: setzt `sms_verified_number = sms_to` + `sms_verified_at` für alle Konten mit nicht-leerem `sms_to` |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Code-Eingabe, Pending-Hinweis (Vorlage `:587-611`), Fehlermeldung E.164/429 |
| Kanal-Anzeige (`channelConnectionStatus.ts`, `VTBriefingChannels.svelte`, `channelContactLabel.ts`, `EditReportConfigSection.svelte`, `WeatherMetricsTab.svelte`) | MODIFY | „eingetragen, aber unbestätigt" ≠ „SMS aktiv" |
| Tests Go/Python/Playwright | CREATE/MODIFY | u. a. Zwei-Nutzer-Test; `profile_test.go:171-190` (`"+49151TESTXXXX"` über PUT) auf gültiges E.164 umstellen. Direkt geschriebene Fixtures (`data_export_test.go:240`, `display_name_642_test.go:235`, `profile_passkey_prompt_test.go:68`) laufen nicht durch PUT und bleiben gültig, solange nur der Schreibweg prüft |

### Designpunkte (für `/30-write-spec` bindend zu klären)
1. **Bestätigung an die Nummer binden, nicht nur an einen Zeitstempel.** Ein bloßes `sms_verified_at` würde jede später (über einen zweiten Weg oder direkt in `user.json`) eingesetzte Nummer als bestätigt durchlassen. Deshalb speichert das Konto die **bewiesene Nummer** (`sms_verified_number`), und die Sperre in `config.py` vergleicht sie mit `sms_to`. Das prüft die Zusicherung dort, wo sie wirkt (Versand), nicht nur dort, wo geschrieben wird. Vorbild: Adressbindung von `EmailVerificationToken{…, Address}`.
2. **Pending-Verhalten:** Hat das Konto bereits eine bestätigte Nummer, bleibt sie beim Ändern wirksam; die neue wartet als `pending_sms_to` bis zur Code-Bestätigung (Issue: „kein Sofort-Umbiegen"). Ohne bestätigte Nummer wird die neue eingetragen, bleibt aber bis zur Bestätigung für den Versand gesperrt (Designpunkt 1 erledigt das automatisch).
3. **Code:** 6 Ziffern (Web-Eingabe, kurz per SMS), crypto/rand, bcrypt, Ablauf 10 Min, max. 5 Fehlversuche ⇒ Code verfällt. Versand nur für Tiers mit `SmsAllowed` (`internal/model/tier.go:3-10`), sonst lösen Free-Konten kostenpflichtige SMS aus.
4. **Versandweg:** Go erzeugt und prüft den Code; der Versand läuft über einen neuen internen Python-Endpunkt (einziger seven.io-Transport mit Sandbox-Zwang). Kein zweiter seven.io-Client in Go.
5. **Mengenbremse:** je Nutzer UND je Zielnummer, geprüft vor dem Speichern (kein Teilzustand), 429 + `Retry-After`. Konkrete Zahlen in der Spec.
6. **Bestandsnummern (Aussperr-Falle):** Backfill-Skript schreibt für jede heute eingetragene Nummer den Bestätigungsstand, **bevor** die Sperre in `config.py` wirksam wird. Keine Lesepfad-Ausnahme. **Deploy-Reihenfolge ist Bestandteil der Spec:** (a) Code mit neuen Feldern deployen (alte Go-Version würde unbekannte Felder beim Speichern verwerfen, deshalb Backfill nie vor dem Deploy), (b) Backfill `--execute` auf Prod + Staging, (c) erst dann ist die Sperre in Kraft. Das Fenster zwischen (a) und (b) ist zu schließen, z. B. indem die Sperre per Schalter erst nach dem Backfill aktiv wird oder der Backfill unmittelbar im Deploy-Schritt läuft. Die Wahl trifft die Spec.
7. **Bekannte Grenze:** Der Backfill übernimmt auch eine heute schon fremd eingetragene Nummer. Die Lücke schließt sich nur für künftige Änderungen, wie beim E-Mail-Vorbild. Prod-Daten sind aus der Sitzung nicht lesbar (`/var/lib/gregor`).
8. **Mandantentrennung:** Zwei-Nutzer-Test Pflicht: Nutzer B trägt A's Nummer ein ⇒ keine Zustellung an diese Nummer aus B's Konto, bis der Code bestätigt ist, den nur das Gerät mit A's Nummer erhält. Kein `"default"`-Fallback in neuen Endpunkten.
9. **Premium-SMS unberührt** (`premium_sms_reply_to`, eigener Handshake).

### Scope Assessment
- Files: ~15–18 (Go ~7, Python ~3, Frontend ~6, Skript 1) plus Tests
- Estimated LoC: Go ~200, Python ~70, Frontend ~100, Skript ~80, plus Tests. Liegt klar über 250 ⇒ `loc_limit_override` (Referenz #2271 brauchte 500). Welche Dateien der Zähler einrechnet, zeigt `workflow.py status` (`LoC-Delta`) bei der Implementierung; hier nicht vorab festgelegt.
- Risk Level: **HIGH**. Berührt den Versandweg aller SMS-Flächen (Trip, Compare, Alarme) und bringt eine Aussperr-Falle für Bestandsnummern mit.

### Technical Approach
EIN Workflow/EINE Spec für #2406 (der Scheibenschnitt ist vom PO festgelegt: nur S4/S5 sind draußen). Innerhalb der Spec gilt die Reihenfolge des E-Mail-Vorbilds (#2304 → #2271) als **Deploy-Reihenfolge**, nicht als Aufteilung in zwei Tickets: Felder + E.164 + Code-Flow + Frontend + Backfill ⇒ Sperre erst wirksam, wenn der Backfill gelaufen ist.

### Dependencies
- Upstream: seven.io über `SevenIoChannelBase`, `store.SaveUser` (Merge), Bremse-Bauart #2404, `model.SmsAllowed`, `X-GZ-Core-Auth`.
- Downstream: alle SMS-Versände über `with_user_profile`; Profil-Antwort; Frontend-Kanalanzeige an 5 Stellen.

### Open Questions
- [ ] (technisch, in `/30` zu entscheiden) Wie wird das Fenster zwischen Deploy und Backfill geschlossen: Schalter oder Backfill als Deploy-Schritt?
- [ ] (technisch) Falls der Umfang über 500 LoC geht: Aufteilung in zwei Lieferungen innerhalb von #2406, Vorbereitung additiv und Scharfschaltung inklusive Frontend. Nur als Rückfallebene, nicht als Default.

## RED-Befunde für /50-implement (Phase 5, 2026-09-22)

RED-Tests liegen **uncommittet** im Arbeitsbaum auf Branch `feat-2406-sms-verifikation`
(`touched_tests_gate.py` blockt jeden Commit, solange sie rot sind — dokumentierter Normalfall).
Sicherungskopie: `…/scratchpad/red-2406/red-2406.tar.gz` plus die infra-Testdatei
`/home/hem/henemm-infra/tests/test_gregor_sms_backfill_deploy_order.py` (dort ebenfalls uncommittet).
RED-Artefakte: `docs/artifacts/feat-2406-sms-verifikation/test-red-output*.txt` (4 registriert).

1. **AC-16 ist mit §4 der Spec mechanisch nicht erfüllbar.** Nach Wechsel auf eine dritte Nummer
   liefert der bcrypt-Vergleich für den alten Code `invalid_code`, nicht `code_expired` — ein
   abgelöster Code ist von einem Rateversuch nur unterscheidbar, wenn der alte Hash zusätzlich
   persistiert wird. Der RED-Test akzeptiert beide Fehlercodes und sichert den Kern (alter Code
   bestätigt nichts, neuer bestätigt). In /50 entscheiden: Fehlercode der AC angleichen
   (Änderung der Spec + Changelog) oder zweiten Hash speichern.
2. **`WeatherMetricsTab` ist ungeguarded:** dort fordert die Spec nur eine Typ-Erweiterung
   (`sms_verified`/`pending_sms_to`); es gibt keine SMS-Statusfläche, also fängt kein Test ein
   Vergessen. Der Dual-Context-Nachweis (AC-14) läuft vollständig über `VTBriefingChannels`.
3. **§4 muss die Nummernbindung beim Bestätigen explizit prüfen** (`SmsVerificationCode.Number`
   gegen die Zielnummer) — AC-4c verlangt das, die Implementation Details nennen es nicht.
4. **Von den Tests festgelegte Verträge** (so umsetzen): Staging-Weg antwortet `{"code":"<6 Ziffern>"}`;
   `sms_verified` erscheint auch als `false` in der Profil-Antwort (kein `omitempty`);
   Kontoseite: `sms-pending-notice`, `sms-code-input`, Knöpfe „Code erneut senden" / „… bestätigen";
   Kanalstatus-Text „eingetragen, unbestätigt" bei `channel-status-sms`.
5. **Kollateral in /50 nachziehen:** `frontend/e2e/issue-609-sms-profil.spec.ts:~44-54` erwartet, dass
   eine unbestätigte Nummer den SMS-Schalter aktiv lässt — bricht durch AC-14 planmäßig.
6. **Python-Testlauf braucht `--allow-unix-socket`** zusätzlich zu `--disable-socket`
   (FastAPI-TestClient, wie im Bestandstest `tests/tdd/test_internal_loaded_endpoint.py`).
7. **LoC-Override steht auf 700** (Spec veranschlagt ~700).
